"""Unsigned in-toto Statement export for proof packets (GitHub issue #26).

`nlfr proof export --format in-toto` emits a bare, DSSE-ready in-toto attestation
Statement (spec v1) whose subjects are the run group's SHA-256'd manifest
artifacts and whose predicate carries the truth-labeled proof packet, the
independent artifact-integrity verification summary, and agent-receipt provenance
(hashes only). These tests prove:

* the Statement matches the in-toto v1 shape;
* subjects carry the manifest sha256s EXACTLY (recorded, not recomputed);
* the predicate carries truth labels + the verification summary;
* two exports are byte-identical (deterministic);
* raw-prompt keys are structurally absent even with an agent receipt present;
* a run WITH mismatched/missing artifacts still exports honestly with counts.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from nlfr.agent_receipt import FORBIDDEN_PROMPT_KEYS
from nlfr.cli import main
from nlfr.db import connect, initialize
from nlfr.db.ingest import (
    upsert_artifact,
    upsert_proof_block,
    upsert_run,
)
from nlfr.ingest.bazel import parse_bazel_bep
from nlfr.ingest.sqlite import ingest_evidence_bundle
from nlfr.projectors import export_in_toto_statement
from nlfr.projectors.common import write_or_print
from nlfr.projectors.in_toto import (
    IN_TOTO_STATEMENT_TYPE,
    PREDICATE_TYPE,
    EmptySubjectError,
)

ROOT = Path(__file__).resolve().parents[1]

RUN_GROUP = "in-toto-demo"
RUN_STABLE_KEY = "in-toto-demo:cache-only:2026-07-06T00:00:00.000000Z"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_bep(tmp_path: Path) -> None:
    """A BEP referencing all four verification outcomes, wired into the DB."""

    good_bytes = b"verified artifact bytes\n"
    good_path = tmp_path / "good.txt"
    good_path.write_bytes(good_bytes)

    bad_path = tmp_path / "bad.txt"
    bad_path.write_bytes(b"the bytes on disk\n")

    missing_path = tmp_path / "missing.txt"  # intentionally never created

    files = [
        {
            "name": "good.txt",
            "uri": good_path.as_uri(),
            "digest": _sha256(good_bytes),
            "length": str(len(good_bytes)),
        },
        {
            "name": "bad.txt",
            "uri": bad_path.as_uri(),
            "digest": "0" * 64,  # deliberately wrong -> local_mismatch
            "length": "18",
        },
        {
            "name": "remote.bin",
            "uri": "bytestream://remote.buildbuddy.io/blobs/deadbeefdeadbeef/1024",
            "digest": "deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef0",
            "length": "1024",
        },
        {
            "name": "missing.txt",
            "uri": missing_path.as_uri(),
            "digest": _sha256(b"never written"),
            "length": "13",
        },
    ]
    events = [
        {"id": {"started": {}}, "started": {"command": "build"}},
        {"id": {"namedSetOfFiles": {"id": "0"}}, "namedSetOfFiles": {"files": files}},
    ]
    (tmp_path / "bazel.bep.json").write_text(
        "\n".join(json.dumps(event) for event in events) + "\n"
    )


def _agent_provenance_payload() -> dict[str, object]:
    """A recorded agent_provenance block payload — hashes only, no raw prompt.

    Mirrors the shape produced by nlfr run/record (nlfr.agent_provenance.v1): the
    receipt summary carries only ids, hashes, and token counts.
    """

    prompt_sha = _sha256(b"a prompt whose bytes are never stored")
    response_sha = _sha256(b"the model response text, stored elsewhere as an artifact")
    receipt_sha = _sha256(b"the full receipt json")
    return {
        "schema_version": "nlfr.agent_provenance.v1",
        "generated_at": "2026-07-06T00:00:01.000000Z",  # recorded at record time
        "scenario_id": "agent-change",
        "title": "Bounded agent change with hashed prompt provenance",
        "agent": {
            "kind": "cursor_adapter_v1",
            "name": "cursor-agent-change",
            "input_signal": "redacted: prompt withheld, hash retained",
            "model": "claude-opus-4-8",
            "model_label_operator": "claude-opus-4-8",
            "prompt_sha256": prompt_sha,
            "provenance_class": "receipt_verified_v1",
            "receipt": {
                "schema_version": "nlfr.agent_receipt.v1",
                "status": "success",
                "captured_at": "2026-07-06T00:00:00.500000Z",
                "session_id": "sess-abc123",
                "model_resolved": "claude-opus-4-8",
                "model_requested": "opus",
                "prompt_sha256": prompt_sha,
                "response_sha256": response_sha,
                "receipt_sha256": receipt_sha,
                "usage": {"input_tokens": 1200, "output_tokens": 350},
                "num_turns": 1,
                "cli_name": "claude",
                "cli_version": "1.0.0",
                "live": True,
            },
        },
        "change": {"change_class": "bounded_agent_v1", "affected_paths": ["src/x.py"]},
        "run_group": RUN_GROUP,
        "mode": "generic",
        "source_kind": "collectable_v1",
        "confidence": "high",
        "evidence_refs": [f"prompt:sha256:{prompt_sha}"],
        "redaction_state": "safe",
    }


def seed_db(tmp_path: Path):
    """Build a run group with recorded artifacts, BEP references, and an agent block."""

    conn = initialize(connect(tmp_path / "nlfr.sqlite"))
    run_id = upsert_run(
        conn,
        stable_key=RUN_STABLE_KEY,
        run_group=RUN_GROUP,
        scenario="in-toto",
        mode="cache-only",
        status="ingested",
        started_at="2026-07-06T00:00:00.000000Z",
        ended_at="2026-07-06T00:00:05.000000Z",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["run:in-toto-demo"],
        redaction_state="safe",
    )

    # NLFR's own captured evidence manifest -> in-toto subjects. Real byte hashes.
    run_json = b'{"run": "in-toto-demo"}\n'
    stdout_txt = b"bazel build //...\nINFO: Build completed successfully\n"
    manifest = [
        ("run.json", run_json, "application/json"),
        ("bazel.stdout.txt", stdout_txt, "text/plain"),
    ]
    subject_digests: dict[str, str] = {}
    for key, data, content_type in manifest:
        digest = _sha256(data)
        subject_digests[key] = digest
        upsert_artifact(
            conn,
            stable_key=f"{RUN_STABLE_KEY}:artifact:{key}",
            run_id=run_id,
            artifact_key=key,
            artifact_path=key,
            manifest_path="artifact_manifest.json",
            sha256=digest,
            size_bytes=len(data),
            content_type=content_type,
            producer_command=["nlfr", "record"],
            source_kind="collectable_v1",
            confidence="high",
            evidence_refs=[f"manifest:{key}"],
            redaction_state="safe",
        )

    # BEP-referenced build outputs -> artifact_verification (verified/mismatch/
    # missing/remote), computed by the real verification path.
    _write_bep(tmp_path)
    bundle = parse_bazel_bep(tmp_path / "bazel.bep.json", source_kind="collectable_v1")
    ingest_evidence_bundle(
        conn,
        run_id=run_id,
        run_stable_key=RUN_STABLE_KEY,
        bundle=bundle,
    )

    # Recorded agent provenance block (hashes only).
    upsert_proof_block(
        conn,
        stable_key=f"{RUN_STABLE_KEY}:block:agent_provenance",
        run_id=run_id,
        block_key="agent_provenance",
        block_kind="agent_provenance",
        title="Agent Provenance",
        summary="Bounded agent change with hashed prompt provenance.",
        payload=_agent_provenance_payload(),
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["prompt:sha256"],
        redaction_state="safe",
    )
    return conn, subject_digests


def _iter_keys(obj: object):
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield key
            yield from _iter_keys(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _iter_keys(item)


def test_statement_matches_in_toto_v1_shape(tmp_path: Path) -> None:
    conn, _ = seed_db(tmp_path)
    statement = export_in_toto_statement(conn, run_group=RUN_GROUP)

    # Exactly the in-toto v1 Statement envelope.
    assert set(statement) == {"_type", "subject", "predicateType", "predicate"}
    assert statement["_type"] == IN_TOTO_STATEMENT_TYPE == "https://in-toto.io/Statement/v1"
    assert statement["predicateType"] == PREDICATE_TYPE
    assert statement["predicateType"].startswith(
        "https://github.com/heyitsalec/nativelink-agent-flight-recorder/attestation"
    )
    assert isinstance(statement["subject"], list) and statement["subject"]
    for subject in statement["subject"]:
        assert set(subject) >= {"name", "digest"}
        assert set(subject["digest"]) == {"sha256"}
        digest = subject["digest"]["sha256"]
        assert len(digest) == 64 and int(digest, 16) >= 0  # lowercase hex


def test_subjects_carry_recorded_manifest_sha256s_exactly(tmp_path: Path) -> None:
    conn, subject_digests = seed_db(tmp_path)
    statement = export_in_toto_statement(conn, run_group=RUN_GROUP)

    by_name = {s["name"]: s["digest"]["sha256"] for s in statement["subject"]}
    # Every recorded manifest artifact is a subject with its recorded digest.
    assert by_name == subject_digests
    assert by_name["run.json"] == subject_digests["run.json"]
    assert by_name["bazel.stdout.txt"] == subject_digests["bazel.stdout.txt"]


def test_predicate_carries_truth_labels_and_verification_summary(tmp_path: Path) -> None:
    conn, _ = seed_db(tmp_path)
    predicate = export_in_toto_statement(conn, run_group=RUN_GROUP)["predicate"]

    assert predicate["predicate_schema_version"] == 1
    assert predicate["run_group"] == RUN_GROUP
    assert predicate["builder"]["id"].endswith("nativelink-agent-flight-recorder")

    # Positioning guardrail is present and does NOT overclaim.
    positioning = predicate["positioning"].lower()
    assert "safety case" in positioning or "provenance stack" in positioning
    assert "auditor" in positioning and "no claim" in positioning
    joined = json.dumps(predicate).lower()
    assert "auditor-accepted" not in joined
    assert "compliance certification" not in joined or "no claim of auditor" in positioning

    # Every proof block carries the four truth-label fields.
    for block in predicate["proof_packet"]["blocks"]:
        assert set(block) >= {
            "source_kind",
            "confidence",
            "evidence_refs",
            "redaction_state",
        }

    # Independent artifact-integrity verification: rollup + per-reference presence.
    verification = predicate["artifact_verification"]
    assert verification["summary"] == {
        "total": 4,
        "verified_count": 1,
        "present_unverified": 0,
        "mismatched": 1,
        "missing": 1,
        "unverified_remote": 1,
        # Remote-verification tiers stay 0 with no CAS probe injected (issue #81 A).
        "remote_verified": 0,
        "remote_present": 0,
        "remote_mismatch": 0,
        "remote_missing": 0,
    }
    presence = {ref["name"]: ref["presence"] for ref in verification["references"]}
    assert presence["good.txt"] == "local_verified"
    assert presence["bad.txt"] == "local_mismatch"
    assert presence["missing.txt"] == "missing"
    assert presence["remote.bin"] == "unverified_remote_reference"

    # run identity is carried with truth labels.
    (identity,) = predicate["run_identity"]
    assert identity["run_group"] == RUN_GROUP
    assert identity["source_kind"] == "collectable_v1"


def test_agent_provenance_class_present_hashes_only(tmp_path: Path) -> None:
    conn, _ = seed_db(tmp_path)
    predicate = export_in_toto_statement(conn, run_group=RUN_GROUP)["predicate"]

    (agent,) = predicate["agent_provenance"]
    assert agent["provenance_class"] == "receipt_verified_v1"
    assert agent["model"] == "claude-opus-4-8"
    # prompt_sha256 is a 64-hex digest, not a prompt.
    assert len(agent["prompt_sha256"]) == 64
    assert agent["receipt"]["live"] is True
    assert agent["receipt"]["session_id"] == "sess-abc123"


def test_no_raw_prompt_keys_anywhere_in_statement(tmp_path: Path) -> None:
    conn, _ = seed_db(tmp_path)
    statement = export_in_toto_statement(conn, run_group=RUN_GROUP)

    keys = set(_iter_keys(statement))
    assert keys.isdisjoint(FORBIDDEN_PROMPT_KEYS)
    # The only prompt evidence present is the hash-suffixed key name.
    assert "prompt_sha256" in keys
    for forbidden in FORBIDDEN_PROMPT_KEYS:
        assert forbidden not in keys


def test_export_is_deterministic_byte_identical(tmp_path: Path) -> None:
    conn, _ = seed_db(tmp_path)

    first = export_in_toto_statement(conn, run_group=RUN_GROUP)
    second = export_in_toto_statement(conn, run_group=RUN_GROUP)
    assert first == second

    # Serialized exactly as the CLI writes it (sort_keys, no wall-clock).
    out_a = tmp_path / "a.intoto.json"
    out_b = tmp_path / "b.intoto.json"
    write_or_print(first, str(out_a))
    write_or_print(second, str(out_b))
    assert out_a.read_bytes() == out_b.read_bytes()

    # The export-time wall-clock 'generated_at' of the proof packet is dropped
    # (recorded timestamps inside stored block payloads are recorded evidence and
    # are legitimately retained — they are stable in the DB across exports).
    assert "generated_at" not in first["predicate"]["proof_packet"]
    assert "generated_at" not in first["predicate"]


def test_failing_evidence_still_exports_honestly_with_counts(tmp_path: Path) -> None:
    """An attestation over failing evidence is still an honest attestation.

    local_mismatch and missing are surfaced in the verification summary, never
    hidden; the Statement still validates as an in-toto v1 envelope.
    """

    conn, _ = seed_db(tmp_path)
    statement = export_in_toto_statement(conn, run_group=RUN_GROUP)
    summary = statement["predicate"]["artifact_verification"]["summary"]

    assert summary["mismatched"] == 1
    assert summary["missing"] == 1
    # The honest-limits note explicitly says failing evidence is surfaced.
    limits = " ".join(statement["predicate"]["limits"]).lower()
    assert "local_mismatch" in limits and "missing" in limits
    assert "honest attestation" in limits
    # Envelope is still structurally an in-toto v1 Statement.
    assert statement["_type"] == "https://in-toto.io/Statement/v1"


def test_empty_run_group_is_a_hard_error_by_default(tmp_path: Path) -> None:
    """A zero-subject in-toto export is a HARD ERROR, not a silent warning.

    An empty-subject Statement is schema-valid and cosign will sign AND verify it,
    yet it proves nothing. Rather than emit that trap, the export raises
    EmptySubjectError whose message names the empty run group and lists the run
    groups that ARE present — turning the failure into guidance.
    """

    conn, _ = seed_db(tmp_path)  # has RUN_GROUP recorded, but not 'ghost-group'

    with pytest.raises(EmptySubjectError) as excinfo:
        export_in_toto_statement(conn, run_group="ghost-group")

    error = excinfo.value
    assert error.run_group == "ghost-group"
    message = str(error)
    assert "run group 'ghost-group' has no recorded artifacts" in message
    assert "empty subject" in message
    # The message lists the run group that IS present, so the operator can recover.
    assert RUN_GROUP in message
    # And it explicitly debunks the '--run-group latest' foot-gun.
    assert "no 'latest'" in message
    assert "--allow-empty-subject" in message


def test_allow_empty_subject_restores_warn_but_export(tmp_path: Path, capsys) -> None:
    """--allow-empty-subject is the opt-in escape hatch for automation edge cases.

    It restores the old behavior: warn on stderr, but still emit a structurally
    valid (empty) in-toto v1 Statement instead of failing hard.
    """

    conn = initialize(connect(tmp_path / "empty.sqlite"))
    statement = export_in_toto_statement(
        conn, run_group="ghost-group", allow_empty_subject=True
    )

    err = capsys.readouterr().err
    assert "nlfr: run group 'ghost-group' has no recorded artifacts" in err
    assert "empty subject" in err
    assert "--allow-empty-subject" in err

    # Still a structurally valid in-toto v1 Statement envelope, just empty.
    assert set(statement) == {"_type", "subject", "predicateType", "predicate"}
    assert statement["_type"] == IN_TOTO_STATEMENT_TYPE
    assert statement["predicateType"] == PREDICATE_TYPE
    assert statement["subject"] == []
    assert statement["predicate"]["run_identity"] == []


def test_non_empty_run_group_exports_without_warning_or_error(
    tmp_path: Path, capsys
) -> None:
    """The non-empty path is unaffected: no warning, no error, subjects intact."""

    conn, _ = seed_db(tmp_path)
    statement = export_in_toto_statement(conn, run_group=RUN_GROUP)

    err = capsys.readouterr().err
    assert "no recorded artifacts" not in err
    assert "empty subject" not in err
    assert statement["subject"]  # non-empty, as recorded


def test_cli_empty_subject_exits_nonzero_and_lists_run_groups(
    tmp_path: Path, capsys
) -> None:
    """`nlfr proof export --format in-toto` over an empty run group exits nonzero.

    The wrong-args scenario from issue #43 (a run-group that matches nothing) now
    fails with a nonzero exit and a stderr message that lists the run groups
    actually present in the DB.
    """

    seed_db(tmp_path)  # records RUN_GROUP into tmp_path/nlfr.sqlite (committed)
    db_path = tmp_path / "nlfr.sqlite"

    code = main(
        [
            "proof",
            "export",
            "--db",
            str(db_path),
            "--run-group",
            "latest",  # the classic foot-gun: a literal match, not a resolver
            "--format",
            "in-toto",
        ]
    )

    assert code != 0
    err = capsys.readouterr().err
    assert "run group 'latest' has no recorded artifacts" in err
    assert RUN_GROUP in err  # lists the run group that IS present
    assert "compare index" in err  # points at the command that lists them


def test_cli_allow_empty_subject_exits_zero(tmp_path: Path, capsys) -> None:
    """--allow-empty-subject makes the CLI export succeed (exit 0) over empties."""

    seed_db(tmp_path)
    db_path = tmp_path / "nlfr.sqlite"

    code = main(
        [
            "proof",
            "export",
            "--db",
            str(db_path),
            "--run-group",
            "latest",
            "--format",
            "in-toto",
            "--allow-empty-subject",
        ]
    )

    assert code == 0
    err = capsys.readouterr().err
    assert "empty subject (--allow-empty-subject)" in err


def test_cli_nonexistent_db_fails_without_traceback(tmp_path: Path) -> None:
    """A wrong/nonexistent --db path fails cleanly and FABRICATES NOTHING (#47).

    Previously (PR #46) the reader auto-created an empty database and then the
    empty-subject check fired. Now the missing --db is refused up front by the
    read-only opener: exit 2, a guiding error, and — critically — no database
    file is left behind, so a path typo can never conjure a zero-value result.
    """

    missing_db = tmp_path / "does" / "not" / "exist" / "nlfr.sqlite"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "nlfr",
            "proof",
            "export",
            "--db",
            str(missing_db),
            "--run-group",
            "latest",
            "--format",
            "in-toto",
        ],
        cwd=ROOT,
        env={**__import__("os").environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "Traceback (most recent call last)" not in result.stderr
    # The reader refuses the missing DB instead of auto-creating an empty one.
    assert "no NLFR database at" in result.stderr
    assert "refusing to read" in result.stderr
    assert "never creates or migrates a database" in result.stderr
    # No file (and no parent dirs) were fabricated on the way to failing.
    assert not missing_db.exists()
    assert not missing_db.parent.exists()


def test_predicate_contract_parses_and_matches_style(tmp_path: Path) -> None:
    payload = json.loads(
        (ROOT / "contracts" / "in_toto_proof_predicate.v1.json").read_text()
    )
    assert payload["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert payload["title"].startswith("NLFR")
    assert payload["type"] == "object"
    # The Statement wrapper is documented and pins the exact predicateType.
    statement_def = payload["$defs"]["in_toto_statement"]
    assert statement_def["properties"]["_type"]["const"] == IN_TOTO_STATEMENT_TYPE
    assert statement_def["properties"]["predicateType"]["const"] == PREDICATE_TYPE


def test_run_group_with_runs_but_zero_artifacts_is_also_a_hard_error(tmp_path: Path) -> None:
    """A run group whose runs recorded NO artifacts must hard-error too.

    Subjects come from the artifacts table, not runs — a runs-row-only group
    exporting subject: [] with exit 0 would be the #43 bug surviving through a
    second door. The emptiness check keys on subjects regardless of why they
    are empty, and the guidance listing must include the artifact-less group.
    """

    conn, _ = seed_db(tmp_path)
    upsert_run(
        conn,
        stable_key="run:artifactless",
        run_group="artifactless-group",
        status="completed",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["run:artifactless"],
        redaction_state="safe",
    )

    with pytest.raises(EmptySubjectError) as excinfo:
        export_in_toto_statement(conn, run_group="artifactless-group")

    message = str(excinfo.value)
    assert "run group 'artifactless-group' has no recorded artifacts" in message
    # Both the artifact-less group and the real one appear in the guidance list.
    assert "artifactless-group" in message
    assert RUN_GROUP in message


def test_predicate_contract_presence_enum_covers_verification_vocabulary() -> None:
    """Drift guard (found by downstream contract consumers, 2026-07-17): the
    exporter emits every presence marker ``ingest.verification`` can produce,
    so the predicate contract's ``presence`` enum must be a superset of that
    vocabulary. The remote_* markers (issue #81 part A) shipped in the code
    without extending the enum — real cluster-recorded exports then failed
    downstream schema validation while nlfr's own local fixtures (which never
    probe a CAS) kept passing."""

    from nlfr.ingest import verification as v

    contract = json.loads(
        (ROOT / "contracts" / "in_toto_proof_predicate.v1.json").read_text()
    )
    enum = set(
        contract["$defs"]["artifact_reference"]["properties"]["presence"]["enum"]
    )
    vocabulary = {
        value
        for name, value in vars(v).items()
        if name.startswith("PRESENCE_") and isinstance(value, str)
    }
    assert vocabulary, "verification module must expose PRESENCE_* markers"
    missing = vocabulary - enum
    assert not missing, (
        f"contract presence enum is missing markers the code can emit: {sorted(missing)}"
    )
