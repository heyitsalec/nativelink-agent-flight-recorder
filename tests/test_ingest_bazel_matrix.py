"""BEP parser version matrix: Bazel 7.x LTS line and the current 9.x line.

The parsers were previously exercised against a single pinned-Bazel fixture set;
production A/V fleets run version RANGES (adoption blocker #6) and cross-major BEP
schema drift was untested. These tests pin parser behavior across proto-derived
fixtures for Bazel 7.4.1 and 9.0.0 (see ``tests/fixtures/bazel/matrix/README.md``
for per-fixture provenance and the exact ``build_event_stream.proto`` source tags):

* equivalent semantics parse to IDENTICAL normalized ingest across versions;
* genuine version differences are asserted explicitly (started/buildFinished field
  drift), so drift is documented rather than silent;
* the BEP ``buildToolVersion`` is surfaced (proof block + packet summary) when
  present and reported as unknown — never fabricated — when absent;
* a live-generation hook records real BEPs on a machine with Bazel; it is
  env-gated and skipped here because real Bazel is not available in this env.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from nlfr.ingest.bazel import extract_bep_tool_version, parse_bazel_bep
from nlfr.projectors import export_proof_packet

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "bazel"
MATRIX_ROOT = FIXTURE_ROOT / "matrix"

# The version matrix: every Bazel line whose proto-derived BEP shape is pinned.
MATRIX_VERSIONS = ["7.4.1", "9.0.0"]


def _bep(version: str) -> Path:
    return MATRIX_ROOT / version / "build.bep.jsonl"


def _events(version: str) -> list[dict]:
    return [
        json.loads(line)
        for line in _bep(version).read_text().splitlines()
        if line.strip()
    ]


def _started_event(version: str) -> dict:
    return next(event["started"] for event in _events(version) if "started" in event)


def _finished_event(version: str) -> dict:
    return next(event["finished"] for event in _events(version) if "finished" in event)


def _parse(version: str):
    # Identical source_kind + evidence_ref for both versions so any residual
    # difference between the two bundles is a REAL parser drift, not a
    # fixture-labeling artifact.
    return parse_bazel_bep(
        _bep(version),
        source_kind="collectable_v1",
        evidence_ref="matrix:build.bep.jsonl",
        verify_artifacts=True,
    )


def _normalized(bundle) -> dict:
    """Reduce a parsed bundle to comparable, order-independent normalized form."""

    return {
        "targets": sorted(
            (target.label, target.target_kind, target.status)
            for target in bundle.targets
        ),
        "actions": sorted(
            (action.action_key, action.target_label, action.mnemonic, action.status)
            for action in bundle.actions
        ),
        "failures": sorted(failure.failure_kind for failure in bundle.failures),
        "artifact_references": sorted(
            (ref.reference_key, ref.name, ref.uri, ref.presence, ref.digest_verified)
            for ref in bundle.artifact_references
        ),
    }


# --------------------------------------------------------------------------- #
# Equivalent semantics: identical normalized ingest across the matrix.
# --------------------------------------------------------------------------- #


def test_matrix_versions_parse_to_identical_normalized_ingest() -> None:
    normalized = {version: _normalized(_parse(version)) for version in MATRIX_VERSIONS}

    baseline_version = MATRIX_VERSIONS[0]
    baseline = normalized[baseline_version]
    for version in MATRIX_VERSIONS[1:]:
        assert normalized[version] == baseline, (
            f"BEP {version} normalized differently from {baseline_version}: "
            f"{normalized[version]!r} != {baseline!r}"
        )

    # Guard against a vacuous "both empty" pass by pinning the concrete shape the
    # equivalence certifies.
    assert baseline["targets"] == [("//app:widget_test", "py_test rule", "PASSED")]
    assert baseline["failures"] == []
    assert (
        "//app:widget_test:test:run=1:shard=1:attempt=1",
        "//app:widget_test",
        "BazelTest",
        "PASSED",
    ) in baseline["actions"]
    assert ("//app:widget_test:action:1", "//app:widget_test", "PyTestRunner", "SUCCESS") in (
        baseline["actions"]
    )
    assert len(baseline["artifact_references"]) == 2
    # Both File references point at file:///tmp/... paths absent on the test host,
    # so honest verification marks them missing (identically across versions).
    assert {ref[3] for ref in baseline["artifact_references"]} == {"missing"}


# --------------------------------------------------------------------------- #
# Recorded tool-version evidence: buildToolVersion surfaced / unknown.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("version", MATRIX_VERSIONS)
def test_extract_bep_tool_version_reads_build_tool_version(version: str) -> None:
    assert extract_bep_tool_version(_bep(version)) == version


def test_extract_bep_tool_version_absent_returns_none() -> None:
    # The pre-matrix fixture's started event declares no buildToolVersion; NLFR
    # reports unknown rather than fabricating a version.
    assert extract_bep_tool_version(FIXTURE_ROOT / "bep.jsonl") is None


def test_ingest_surfaces_build_tool_version_in_proof_packet(tmp_path) -> None:
    database_path = tmp_path / "nlfr.sqlite"
    result = _run_nlfr(
        "ingest",
        "--database",
        str(database_path),
        "--run-key",
        "matrix-741:cache-only",
        "--run-group",
        "bep-matrix",
        "--bep",
        str(_bep("7.4.1")),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["counts"]["proof_blocks"] == 1

    with sqlite3.connect(database_path) as conn:
        conn.row_factory = sqlite3.Row
        block = conn.execute(
            "SELECT block_kind, block_key, payload FROM proof_blocks"
        ).fetchone()
        proof = export_proof_packet(conn, run_group="bep-matrix")

    assert block["block_kind"] == "build_tool_identity_v1"
    assert block["block_key"] == "build-tool-identity"
    assert json.loads(block["payload"])["build_tool_version"] == "7.4.1"

    # Surfaced in the packet summary so an exported packet states which Bazel
    # produced the evidence.
    assert proof["summary"]["build_tool"] == {
        "tool": "bazel",
        "versions": ["7.4.1"],
        "recorded": True,
    }
    # And auto-surfaced as a proof block within the packet body.
    identity = next(
        block for block in proof["blocks"] if block.get("kind") == "build_tool_identity_v1"
    )
    assert identity["payload"]["build_tool_version"] == "7.4.1"
    assert identity["source_kind"] == "collectable_v1"


def test_proof_packet_reports_unknown_build_tool_when_absent(tmp_path) -> None:
    database_path = tmp_path / "nlfr.sqlite"
    result = _run_nlfr(
        "ingest",
        "--database",
        str(database_path),
        "--run-key",
        "no-version:cache-only",
        "--run-group",
        "no-version",
        "--bep",
        str(FIXTURE_ROOT / "bep.jsonl"),
        "--source-kind",
        "simulated_v1",
        "--json",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    # Nothing fabricated: no build-tool-identity proof block was created.
    assert payload["counts"].get("proof_blocks", 0) == 0

    with sqlite3.connect(database_path) as conn:
        conn.row_factory = sqlite3.Row
        proof = export_proof_packet(conn, run_group="no-version")

    assert proof["summary"]["build_tool"] == {
        "tool": "bazel",
        "versions": [],
        "recorded": False,
    }
    assert not any(
        block.get("kind") == "build_tool_identity_v1" for block in proof["blocks"]
    )


# --------------------------------------------------------------------------- #
# Explicit drift points (verified against build_event_stream.proto @ each tag).
# --------------------------------------------------------------------------- #


def test_started_event_field_drift_across_versions() -> None:
    started_74 = _started_event("7.4.1")
    started_90 = _started_event("9.0.0")

    # start_time_millis (proto 2, deprecated) vs start_time Timestamp (proto 9):
    # 7.4.x carries the deprecated millis alongside the Timestamp; 9.x drops it.
    assert "startTimeMillis" in started_74 and "startTime" in started_74
    assert "startTimeMillis" not in started_90 and "startTime" in started_90

    # host (proto 10) / user (proto 11) are NEW BuildStarted fields in 9.x.
    assert "host" not in started_74 and "user" not in started_74
    assert started_90["host"] and started_90["user"]

    # build_tool_version (proto 3) is present in both — the field NLFR surfaces.
    assert started_74["buildToolVersion"] == "7.4.1"
    assert started_90["buildToolVersion"] == "9.0.0"


def test_build_finished_exit_code_shape_drift_across_versions() -> None:
    finished_74 = _finished_event("7.4.1")
    finished_90 = _finished_event("9.0.0")

    # Both carry the structured exit_code (ExitCode{name,code}, proto 3) NLFR keys on.
    assert finished_74["exitCode"] == {"name": "SUCCESS", "code": 0}
    assert finished_90["exitCode"] == {"name": "SUCCESS", "code": 0}

    # 7.4.x still carries the deprecated overall_success bool (proto 1) and
    # finish_time_millis (proto 2); 9.x drops both for the exit_code/finish_time
    # Timestamp forms.
    assert finished_74["overallSuccess"] is True and "finishTimeMillis" in finished_74
    assert "overallSuccess" not in finished_90 and "finishTimeMillis" not in finished_90

    # Both SUCCESS builds ingest with zero build_finished failures (equivalent).
    for version in MATRIX_VERSIONS:
        assert [f.failure_kind for f in _parse(version).failures] == []


def test_test_result_duration_field_drift_across_versions() -> None:
    result_74 = next(
        event["testResult"] for event in _events("7.4.1") if "testResult" in event
    )
    result_90 = next(
        event["testResult"] for event in _events("9.0.0") if "testResult" in event
    )

    # test_attempt_duration_millis (proto 3, deprecated) vs test_attempt_duration
    # Duration (proto 11): 7.4.x emits millis, 9.x emits the Duration string.
    assert "testAttemptDurationMillis" in result_74
    assert "testAttemptDuration" in result_90 and "testAttemptDurationMillis" not in result_90

    # Status normalizes identically regardless of the duration field shape.
    assert result_74["status"] == result_90["status"] == "PASSED"


def test_build_finished_overall_success_only_is_exit_unknown(tmp_path) -> None:
    # Documented boundary: NLFR keys on buildFinished.exitCode (both 7.4.x and 9.x
    # emit it) and does NOT fall back to the long-deprecated overall_success bool.
    # A BEP carrying only overallSuccess (pre-exit_code Bazel, far older than 7.4)
    # is recorded as exit UNKNOWN, not SUCCESS — pinned here so the boundary is
    # explicit rather than silent.
    bep = tmp_path / "legacy.bep.jsonl"
    bep.write_text(
        json.dumps(
            {"id": {"started": {}}, "started": {"command": "build", "buildToolVersion": "0.29.1"}}
        )
        + "\n"
        + json.dumps({"id": {"buildFinished": {}}, "finished": {"overallSuccess": True}})
        + "\n"
    )

    bundle = parse_bazel_bep(bep, source_kind="collectable_v1", evidence_ref="legacy")
    finished_failures = [f for f in bundle.failures if f.failure_kind == "build_finished"]
    assert len(finished_failures) == 1
    assert "UNKNOWN" in finished_failures[0].message


# --------------------------------------------------------------------------- #
# Tier (c): env-gated live BEP generation for future machines (skipped here).
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(
    os.environ.get("NLFR_RUN_BEP_MATRIX_LIVE") != "1" or shutil.which("bazelisk") is None,
    reason=(
        "env-gated live BEP generation: set NLFR_RUN_BEP_MATRIX_LIVE=1 with bazelisk "
        "on PATH to record a real BEP (real Bazel is not available in this env)"
    ),
)
def test_live_bep_matrix_generation_hook(tmp_path) -> None:
    # Honest live hook: record a REAL BEP with the Bazel on PATH and assert NLFR
    # reads a real buildToolVersion from it. This is how a machine that has Bazel
    # promotes the proto-derived (tier b) fixtures to live (tier c) coverage.
    bep_path = tmp_path / "live.bep.jsonl"
    subprocess.run(
        [
            "bazelisk",
            "test",
            "//...",
            f"--build_event_json_file={bep_path}",
            "--nobuild_event_binary_file",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert bep_path.exists(), "bazelisk did not write a BEP"
    version = extract_bep_tool_version(bep_path)
    assert version is not None and version[:1].isdigit()


def _run_nlfr(*args: str) -> subprocess.CompletedProcess[str]:
    env = {"PYTHONPATH": str(ROOT / "src")}
    return subprocess.run(
        [sys.executable, "-m", "nlfr", *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
