"""BEP parser version matrix: Bazel 7.x LTS line and the current 9.x line.

The parsers were previously exercised against a single pinned-Bazel fixture set;
production A/V fleets run version RANGES (adoption blocker #6) and cross-major BEP
schema drift was untested. These tests pin parser behavior across proto-derived
fixtures for Bazel 7.4.1 and 9.0.0 (see ``tests/fixtures/bazel/matrix/README.md``
for per-fixture provenance and the exact ``build_event_stream.proto`` source tags
and the Java populators the fixtures were re-derived from):

* equivalent semantics parse to IDENTICAL normalized ingest across versions;
* the ONE genuine cross-version drift is asserted explicitly: ``BuildStarted``
  gains ``host`` (field 10) / ``user`` (field 11) in 9.x — nothing else changes;
* the genuine NON-drift is pinned as a stability tripwire: ``BuildFinished``,
  ``TestSummary`` and ``TestResult`` shapes are byte-stable across the range —
  the deprecated ``overall_success`` / ``finish_time_millis`` /
  ``*_millis`` / ``*_millis_epoch`` fields are STILL emitted in 9.x alongside
  their Timestamp/Duration successors (verified against the populating Java at
  each tag). If a future Bazel really drops them, these tests flag it and the
  matrix gains a real drift point;
* the BEP ``buildToolVersion`` is surfaced (proof block + packet summary) when
  present and reported as unknown — never fabricated — when absent, and a run
  group mixing two Bazel versions lists BOTH;
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

from nlfr.ingest.bazel import (
    TESTED_BAZEL_MAJORS,
    TESTED_BAZEL_VERSIONS,
    extract_bep_tool_version,
    out_of_range_bazel_warning,
    parse_bazel_bep,
    parse_bazel_execution_log,
    parse_bazel_profile,
)
from nlfr.projectors import export_proof_packet

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "bazel"
MATRIX_ROOT = FIXTURE_ROOT / "matrix"
# The real Bazel workspace in this repo (pins .bazelversion). The live hook must
# run Bazel here, not at ROOT — ROOT is not a Bazel workspace.
DEMO_WORKSPACE = ROOT / "demo" / "bazel-monorepo"

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


def _test_result_event(version: str) -> dict:
    return next(
        event["testResult"] for event in _events(version) if "testResult" in event
    )


def _test_summary_event(version: str) -> dict:
    return next(
        event["testSummary"] for event in _events(version) if "testSummary" in event
    )


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


def test_run_group_mixing_two_bazel_versions_lists_both(tmp_path) -> None:
    # A run group that mixes evidence from two Bazel versions (7.4.1 and 9.0.0,
    # ingested as two runs) rolls both up in summary.build_tool.versions — the
    # version is reported per observed BEP, never collapsed or fabricated.
    database_path = tmp_path / "nlfr.sqlite"
    for version, run_key in (
        ("7.4.1", "matrix-741:cache-only"),
        ("9.0.0", "matrix-900:cache-only"),
    ):
        result = _run_nlfr(
            "ingest",
            "--database",
            str(database_path),
            "--run-key",
            run_key,
            "--run-group",
            "bep-matrix-mixed",
            "--bep",
            str(_bep(version)),
            "--json",
        )
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["counts"]["proof_blocks"] == 1

    with sqlite3.connect(database_path) as conn:
        conn.row_factory = sqlite3.Row
        proof = export_proof_packet(conn, run_group="bep-matrix-mixed")

    build_tool = proof["summary"]["build_tool"]
    assert build_tool["tool"] == "bazel"
    assert build_tool["recorded"] is True
    # Both versions observed in the group; order-independent so the assertion does
    # not depend on proof-block row ordering.
    assert sorted(build_tool["versions"]) == ["7.4.1", "9.0.0"]


# --------------------------------------------------------------------------- #
# Version drift & stability — verified against build_event_stream.proto AND the
# populating Java (BuildStartingEvent / BuildCompletingEvent / TestAttempt /
# TestSummary) at each release tag. See tests/fixtures/bazel/matrix/README.md.
#
# The fixtures encode what Bazel ACTUALLY emits, re-derived from the populators.
# Two prior tests here asserted drift that does not exist (9.x "dropping"
# start_time_millis / overall_success / finish_time_millis / the *_millis test
# timing fields). The protos are byte-identical for BuildFinished/TestSummary/
# TestResult across 7.4.1..9.0.0, and the Java sets the deprecated fields in BOTH
# versions. The tests below assert that reality: exactly one drift point, plus
# stability tripwires for the fields that did NOT drift.
# --------------------------------------------------------------------------- #


def test_started_host_user_are_the_only_9x_drift() -> None:
    # The ONE genuine BuildStarted drift across the range: host (proto field 10)
    # and user (field 11) were added in 9.x. BuildStartingEvent.java @ 7.4.1 sets
    # neither; @ 9.0.0 it calls setHost(...)/setUser(...). Nothing else changes.
    started_74 = _started_event("7.4.1")
    started_90 = _started_event("9.0.0")

    assert "host" not in started_74 and "user" not in started_74
    assert started_90["host"] == "ci-runner-09" and started_90["user"] == "builder"

    # host/user are the ONLY keys that differ in shape between the two started
    # events — pins the drift at exactly one point rather than asserting invented
    # differences elsewhere.
    assert set(started_90) - set(started_74) == {"host", "user"}
    assert set(started_74) - set(started_90) == set()

    # start_time_millis (proto 2, deprecated) is STILL emitted in 9.x alongside
    # the start_time Timestamp (proto 9): BuildStartingEvent.java sets BOTH in
    # both versions. This is the field the earlier fixture wrongly dropped.
    assert "startTimeMillis" in started_74 and "startTime" in started_74
    assert "startTimeMillis" in started_90 and "startTime" in started_90

    # build_tool_version (proto 3) is present in both — the field NLFR surfaces.
    assert started_74["buildToolVersion"] == "7.4.1"
    assert started_90["buildToolVersion"] == "9.0.0"


def test_build_finished_shape_is_byte_stable_across_versions() -> None:
    # Stability tripwire (NOT drift). BuildFinished is byte-identical in the proto
    # across 7.4.1..9.0.0, and BuildCompletingEvent.java sets the same fields in
    # both: the deprecated overall_success (proto 1) and finish_time_millis
    # (proto 2) are STILL emitted in 9.x alongside exit_code (3) / finish_time (5).
    # If a future Bazel really drops the deprecated pair, this test fails and the
    # matrix gains a genuine drift point — that is the tripwire's job.
    finished_74 = _finished_event("7.4.1")
    finished_90 = _finished_event("9.0.0")

    expected_shape = {"overallSuccess", "exitCode", "finishTimeMillis", "finishTime"}
    assert set(finished_74) == expected_shape
    assert set(finished_90) == expected_shape

    # Structured exit_code (ExitCode{name,code}, proto 3) — the field NLFR keys on.
    assert finished_74["exitCode"] == {"name": "SUCCESS", "code": 0}
    assert finished_90["exitCode"] == {"name": "SUCCESS", "code": 0}
    # Deprecated-but-emitted overall_success present in BOTH versions.
    assert finished_74["overallSuccess"] is True
    assert finished_90["overallSuccess"] is True

    # Both SUCCESS builds ingest with zero build_finished failures (equivalent).
    for version in MATRIX_VERSIONS:
        assert [f.failure_kind for f in _parse(version).failures] == []


def test_test_timing_fields_are_byte_stable_across_versions() -> None:
    # Stability tripwire (NOT drift). TestResult and TestSummary are byte-identical
    # in the proto across the range, and TestAttempt.java / TestSummary.java each
    # set BOTH the deprecated *_millis(_epoch) fields AND their Timestamp/Duration
    # successors in both versions. The earlier fixture wrongly dropped the millis
    # forms from 9.x; here both forms are present in both versions.
    result_74 = _test_result_event("7.4.1")
    result_90 = _test_result_event("9.0.0")
    assert set(result_74) == set(result_90)
    for result in (result_74, result_90):
        # deprecated forms (proto 6 / 3) AND successors (proto 10 / 11), together.
        assert "testAttemptStartMillisEpoch" in result and "testAttemptStart" in result
        assert "testAttemptDurationMillis" in result and "testAttemptDuration" in result
        assert result["status"] == "PASSED"

    summary_74 = _test_summary_event("7.4.1")
    summary_90 = _test_summary_event("9.0.0")
    assert set(summary_74) == set(summary_90)
    for summary in (summary_74, summary_90):
        # deprecated millis (proto 7/8/9) AND Timestamp/Duration (proto 13/14/12).
        assert "firstStartTimeMillis" in summary and "firstStartTime" in summary
        assert "lastStopTimeMillis" in summary and "lastStopTime" in summary
        assert "totalRunDurationMillis" in summary and "totalRunDuration" in summary


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
    #
    # cwd MUST be the real Bazel workspace (demo/bazel-monorepo, which pins
    # .bazelversion and defines //tasks:...). Running at ROOT would fail before
    # writing any BEP because ROOT is not a Bazel workspace. //tasks/... resolves
    # to the demo py_test target set that actually exists there.
    assert (DEMO_WORKSPACE / "MODULE.bazel").exists(), "demo Bazel workspace missing"
    bep_path = tmp_path / "live.bep.jsonl"
    subprocess.run(
        [
            "bazelisk",
            "test",
            "//tasks/...",
            f"--build_event_json_file={bep_path}",
            "--nobuild_event_binary_file",
        ],
        cwd=DEMO_WORKSPACE,
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


# --------------------------------------------------------------------------- #
# The tested-anchor constant is the SINGLE source of truth (src/nlfr/ingest/
# bazel.py). The matrix fixture directories must mirror it exactly, so a fixture
# added/removed without updating the constant (or vice versa) fails loudly.
# --------------------------------------------------------------------------- #


def test_matrix_anchor_constant_matches_fixtures() -> None:
    fixture_versions = sorted(
        p.name for p in MATRIX_ROOT.iterdir() if p.is_dir()
    )
    assert fixture_versions == sorted(TESTED_BAZEL_VERSIONS)
    assert sorted(MATRIX_VERSIONS) == sorted(TESTED_BAZEL_VERSIONS)
    # The advertised majors match the anchor versions' majors.
    assert sorted(TESTED_BAZEL_MAJORS) == sorted(
        {int(v.split(".")[0]) for v in TESTED_BAZEL_VERSIONS}
    )


# --------------------------------------------------------------------------- #
# Execution-log matrix (SpawnExec JSON). spawn.proto's SpawnExec message is
# byte-identical across 7.4.1..9.0.0 (the only spawn.proto diffs are in
# ExecLogEntry, the COMPACT-log format NLFR does not parse), so the two exec-log
# fixtures are byte-identical and MUST parse to identical normalized cache
# evidence. See tests/fixtures/bazel/matrix/README.md for the SpawnExec source.
# --------------------------------------------------------------------------- #


def _exec_log(version: str) -> Path:
    return MATRIX_ROOT / version / "build.exec-log.jsonl"


def _profile(version: str) -> Path:
    return MATRIX_ROOT / version / "build.profile.json"


def _normalized_cache_events(bundle) -> list[tuple]:
    return sorted(
        (e.event_kind, e.hit, e.target_label, e.digest, e.source_kind, e.confidence)
        for e in bundle.cache_events
    )


def test_exec_log_fixtures_are_byte_identical_across_versions() -> None:
    # SpawnExec is byte-stable 7.4.1..9.0.0; the fixtures encode that as identity.
    # If a future Bazel changes the SpawnExec JSON shape, regenerate and this
    # tripwire earns a real drift row (mirrors the BEP byte-stable assertions).
    seven = _exec_log("7.4.1").read_bytes()
    nine = _exec_log("9.0.0").read_bytes()
    assert seven == nine, "SpawnExec JSON drifted across the matrix — update the doc"


@pytest.mark.parametrize("version", MATRIX_VERSIONS)
def test_exec_log_matrix_parses_cache_evidence(version: str) -> None:
    bundle = parse_bazel_execution_log(
        _exec_log(version), source_kind="collectable_v1", evidence_ref="matrix:exec-log"
    )
    by_label = {e.target_label: e for e in bundle.cache_events}
    # The remote-cache-hit test spawn: collectable_v1/high, digest cross-recorded.
    hit = by_label["//app:widget_test"]
    assert hit.event_kind == "remote_cache_hit"
    assert hit.hit is True
    assert hit.source_kind == "collectable_v1" and hit.confidence == "high"
    assert hit.digest and hit.digest.endswith("/196")  # Digest{hash, sizeBytes} form
    # The locally-run (non-cached) compile spawn: an honest cache_miss.
    miss = by_label["//app:widget"]
    assert miss.event_kind == "cache_miss"
    assert miss.hit is False


def test_exec_log_matrix_versions_parse_to_identical_normalized_ingest() -> None:
    normalized = {
        v: _normalized_cache_events(
            parse_bazel_execution_log(_exec_log(v), evidence_ref="matrix:exec-log")
        )
        for v in MATRIX_VERSIONS
    }
    baseline = normalized[MATRIX_VERSIONS[0]]
    for v in MATRIX_VERSIONS[1:]:
        assert normalized[v] == baseline, f"exec-log ingest drift {MATRIX_VERSIONS[0]}->{v}"


# --------------------------------------------------------------------------- #
# Profile matrix (JSON trace). The profile writer (Profiler.java TaskData.
# writeTraceData) emits action events with args {target, mnemonic} at 7.4.1; at
# 9.0.0 it adds an OPTIONAL args.configuration (verified against the Java at both
# tags). That is the ONE profile drift in the NLFR-consumed surface, and NLFR
# ignores it — so normalized ingest is identical. Real profile action events are
# named by their action description (never "cache hit") and carry NO digest, so
# NLFR yields action_cache_observed (derived_v1/low); it never FABRICATES a
# remote_cache_hit from a real profile.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("version", MATRIX_VERSIONS)
def test_profile_matrix_parses_action_evidence(version: str) -> None:
    bundle = parse_bazel_profile(_profile(version), evidence_ref="matrix:profile")
    labels = {e.target_label for e in bundle.cache_events}
    assert labels == {"//app:widget_test", "//app:widget"}
    # A real profile names events by description, not "cache hit" — NLFR records
    # action_cache_observed (derived_v1/low), never a fabricated remote hit.
    for e in bundle.cache_events:
        assert e.event_kind == "action_cache_observed"
        assert e.hit is None
        assert e.source_kind == "derived_v1" and e.confidence == "low"


def test_profile_matrix_versions_parse_to_identical_normalized_ingest() -> None:
    normalized = {
        v: _normalized_cache_events(
            parse_bazel_profile(_profile(v), evidence_ref="matrix:profile")
        )
        for v in MATRIX_VERSIONS
    }
    baseline = normalized[MATRIX_VERSIONS[0]]
    for v in MATRIX_VERSIONS[1:]:
        assert normalized[v] == baseline, f"profile ingest drift {MATRIX_VERSIONS[0]}->{v}"


def test_profile_configuration_is_the_only_9x_drift() -> None:
    # The one genuine profile drift: 9.0.0 adds args.configuration to action
    # events (Profiler.java @ 9.0.0 sets it; @ 7.4.1 it is absent). NLFR ignores
    # it, so ingest is unchanged — pinned here so a future args change is caught.
    def _action_args(version: str) -> list[dict]:
        payload = json.loads(_profile(version).read_text())
        return [
            e["args"]
            for e in payload["traceEvents"]
            if e.get("cat") == "action processing" and "args" in e
        ]

    args_74 = _action_args("7.4.1")
    args_90 = _action_args("9.0.0")
    assert all("configuration" not in a for a in args_74)
    assert all("configuration" in a for a in args_90)
    # Aside from configuration, the action args (target, mnemonic) are identical.
    strip = lambda args: [{k: v for k, v in a.items() if k != "configuration"} for a in args]
    assert strip(args_74) == strip(args_90)


# --------------------------------------------------------------------------- #
# Out-of-range Bazel version warning (non-blocking "untested version" signal).
# The pure helper is exercised here; doctor/record wiring lives in their tests.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("version", TESTED_BAZEL_VERSIONS)
def test_tested_anchor_versions_emit_no_out_of_range_warning(version: str) -> None:
    assert out_of_range_bazel_warning(version) is None


@pytest.mark.parametrize("version", ["6.5.0", "8.0.0", "10.1.2", "8.0.0-pre.20240101.1"])
def test_out_of_range_majors_emit_a_warning(version: str) -> None:
    warning = out_of_range_bazel_warning(version)
    assert warning is not None
    assert version.split("-")[0] in warning
    assert "tested version anchors" in warning
    for anchor in TESTED_BAZEL_VERSIONS:
        assert anchor in warning


@pytest.mark.parametrize("version", [None, "", "not-a-version", "dev"])
def test_unknown_version_stays_silent_never_fabricates_out_of_range(version) -> None:
    # Unknown/unparseable is NOT out-of-range: NLFR never invents an "untested"
    # claim from a version it could not read.
    assert out_of_range_bazel_warning(version) is None
