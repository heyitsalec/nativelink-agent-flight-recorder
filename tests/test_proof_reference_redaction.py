"""Proof / in-toto artifact references pass the sharing boundary (PR #63, W3-C-fix2).

The abs_path detector shipped with #63 caught a REAL sibling of the #60 leak the
graph/runway projectors already scrub: the ``artifact_verification`` proof block
embeds each BEP file reference's raw ``file://`` URI under a block that
self-labels ``redaction_state: safe``. On an ordinary local Bazel build those
URIs are absolute local paths, so a fresh ``nlfr proof export`` — and the in-toto
export that consumes the proof predicate — failed the documented "gate ANY
projection with ``nlfr redact --check``" workflow with exit 1, while graph/runway
were already clean.

These tests are the reviewer's exact repro run through the shipped CLI: a fresh
DB (local ``file://`` references via ``as_uri()``), a real ``nlfr proof export``
(json and in-toto), then ``nlfr redact --check`` must exit 0. They also pin the
non-negotiable invariants of the fix: digest / presence / verification fields are
byte-unchanged by the scrub (a skeptic verifies references by digest + presence,
not by the recorder's local path), the block's ``redaction_state`` is honestly
upgraded ``safe`` -> ``redacted`` when a scrub occurred, and the in-toto export
stays byte-for-byte deterministic (the scrub must be deterministic).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Guarantee sibling test modules are importable regardless of pytest import mode.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from nlfr.cli import main  # noqa: E402
from nlfr.projectors import (  # noqa: E402
    export_action_graph,
    export_in_toto_statement,
    export_proof_packet,
    export_validation_runway,
)
from nlfr.projectors.common import row_to_dict  # noqa: E402
from nlfr.redaction import RedactionConfig, redact_payload  # noqa: E402
from test_in_toto_export import RUN_GROUP, RUN_STABLE_KEY, seed_db  # noqa: E402

# The publish/CI gate config — exactly what ``nlfr redact --check`` runs by
# default: secret tier always on, abs_path (path tier) on, email + ipv4 on,
# hostname off.
CHECK_CONFIG = RedactionConfig(redact=False)


def _artifact_verification_block(proof: dict) -> dict:
    return next(b for b in proof["blocks"] if b["id"] == "artifact_verification")


def _findings(payload: dict):
    return redact_payload(payload, CHECK_CONFIG).findings


# ---------------------------------------------------------------------------
# THE acceptance test: fresh export -> nlfr redact --check exit 0 (via the CLI)
# ---------------------------------------------------------------------------


def test_fresh_proof_export_passes_redact_check_via_cli(tmp_path: Path) -> None:
    """Reviewer's exact repro: fresh proof export, then ``nlfr redact --check`` == 0."""

    seed_db(tmp_path)
    db = tmp_path / "nlfr.sqlite"
    proof_json = tmp_path / "proof.json"

    assert main(
        ["proof", "export", "--db", str(db), "--run-group", RUN_GROUP, "--output", str(proof_json)]
    ) == 0
    # The whole point: the shared gate now passes on an ordinary local build.
    assert main(["redact", "--check", str(proof_json)]) == 0


def test_fresh_in_toto_export_passes_redact_check_via_cli(tmp_path: Path) -> None:
    """Same for the in-toto Statement, which embeds the proof predicate."""

    seed_db(tmp_path)
    db = tmp_path / "nlfr.sqlite"
    intoto_json = tmp_path / "statement.json"

    assert main(
        [
            "proof", "export", "--db", str(db), "--run-group", RUN_GROUP,
            "--format", "in-toto", "--output", str(intoto_json),
        ]
    ) == 0
    assert main(["redact", "--check", str(intoto_json)]) == 0


def test_proof_and_in_toto_have_zero_findings_in_process(tmp_path: Path) -> None:
    """Belt-and-suspenders in-process assertion mirroring the CLI gate."""

    conn, _ = seed_db(tmp_path)
    proof = export_proof_packet(conn, run_group=RUN_GROUP)
    statement = export_in_toto_statement(conn, run_group=RUN_GROUP)

    assert _findings(proof) == [], [f.format_line() for f in _findings(proof)]
    assert _findings(statement) == [], [f.format_line() for f in _findings(statement)]


# ---------------------------------------------------------------------------
# The scrub is honest: uri scrubbed, digest/presence untouched, label upgraded
# ---------------------------------------------------------------------------


def test_local_reference_uri_is_scrubbed_preserving_scheme_and_basename(tmp_path: Path) -> None:
    conn, _ = seed_db(tmp_path)
    proof = export_proof_packet(conn, run_group=RUN_GROUP)
    refs = {r["name"]: r for r in _artifact_verification_block(proof)["payload"]["references"]}

    # The three local file:// references are scrubbed to the basename-preserving,
    # scheme-preserving placeholder; no absolute local path survives.
    for name in ("good.txt", "bad.txt", "missing.txt"):
        assert refs[name]["uri"] == f"file://[REDACTED:abs_path]/{name}"

    # The remote bytestream:// reference is a remote authority, never a local
    # path, so it is left intact.
    assert refs["remote.bin"]["uri"] == "bytestream://remote.buildbuddy.io/blobs/deadbeefdeadbeef/1024"


def test_digest_presence_and_verification_fields_are_byte_unchanged(tmp_path: Path) -> None:
    """A skeptic verifies references by digest + presence; the scrub must not touch them."""

    conn, _ = seed_db(tmp_path)

    # Ground truth straight from the recorded SQLite rows (never scrubbed).
    run_ids = [r["id"] for r in conn.execute("SELECT id FROM runs WHERE run_group = ?", (RUN_GROUP,))]
    placeholders = ", ".join("?" for _ in run_ids)
    raw_rows = conn.execute(
        f"SELECT * FROM artifact_references WHERE run_id IN ({placeholders}) ORDER BY created_at, id",
        run_ids,
    ).fetchall()
    raw = {row_to_dict(r)["name"]: row_to_dict(r) for r in raw_rows}

    proof = export_proof_packet(conn, run_group=RUN_GROUP)
    projected = {r["name"]: r for r in _artifact_verification_block(proof)["payload"]["references"]}

    # Every field a skeptic relies on is identical to the recorded evidence.
    for name, ref in projected.items():
        assert ref["declared_digest"] == raw[name]["declared_digest"]
        assert ref["computed_digest"] == raw[name]["computed_digest"]
        raw_verified = raw[name]["digest_verified"]
        expected_verified = None if raw_verified is None else bool(raw_verified)
        assert ref["digest_verified"] == expected_verified
        assert ref["presence"] == raw[name]["presence"]
        assert ref["verification_note"] == raw[name]["verification_note"]
        assert ref["source_kind"] == raw[name]["source_kind"]
        assert ref["confidence"] == raw[name]["confidence"]
        # No placeholder ever bled into a digest / presence / note field.
        for field in ("declared_digest", "computed_digest", "presence", "verification_note"):
            assert "[REDACTED:abs_path]" not in str(ref[field])

    # And the verified good.txt digest is the real, unchanged 64-hex SHA-256.
    good = projected["good.txt"]
    assert good["digest_verified"] is True
    assert good["computed_digest"] == good["declared_digest"]
    assert len(good["computed_digest"]) == 64


def test_block_redaction_state_upgraded_safe_to_redacted(tmp_path: Path) -> None:
    """When a scrub occurred, the block must not keep claiming ``safe``."""

    conn, _ = seed_db(tmp_path)
    proof = export_proof_packet(conn, run_group=RUN_GROUP)
    block = _artifact_verification_block(proof)
    assert block["redaction_state"] == "redacted"


def test_no_scrub_leaves_state_safe_for_remote_only_references(tmp_path: Path) -> None:
    """A run whose references are all remote (no local file:// path) has nothing to
    scrub, so the block honestly stays ``safe`` rather than over-claiming redaction."""

    from nlfr.db import connect, initialize
    from nlfr.db.ingest import upsert_run
    from nlfr.ingest.bazel import parse_bazel_bep
    from nlfr.ingest.sqlite import ingest_evidence_bundle

    conn = initialize(connect(tmp_path / "remote.sqlite"))
    run_id = upsert_run(
        conn,
        stable_key="remote-only:cache-only:2026-07-06T00:00:00.000000Z",
        run_group="remote-only",
        scenario="remote",
        mode="cache-only",
        status="ingested",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["run:remote-only"],
        redaction_state="safe",
    )
    events = [
        {"id": {"started": {}}, "started": {"command": "build"}},
        {
            "id": {"namedSetOfFiles": {"id": "0"}},
            "namedSetOfFiles": {
                "files": [
                    {
                        "name": "remote.bin",
                        "uri": "bytestream://remote.buildbuddy.io/blobs/deadbeefdeadbeef/1024",
                        "digest": "deadbeef" * 8,
                        "length": "1024",
                    }
                ]
            },
        },
    ]
    bep = tmp_path / "remote.bep.json"
    bep.write_text("\n".join(json.dumps(e) for e in events) + "\n")
    bundle = parse_bazel_bep(bep, source_kind="collectable_v1")
    ingest_evidence_bundle(
        conn,
        run_id=run_id,
        run_stable_key="remote-only:cache-only:2026-07-06T00:00:00.000000Z",
        bundle=bundle,
    )

    proof = export_proof_packet(conn, run_group="remote-only")
    block = _artifact_verification_block(proof)
    assert block["redaction_state"] == "safe"  # nothing scrubbed -> no false upgrade
    assert _findings(proof) == []


# ---------------------------------------------------------------------------
# reference_key that embeds the uri (no name) is scrubbed too
# ---------------------------------------------------------------------------


def test_reference_key_embedding_uri_is_scrubbed(tmp_path: Path) -> None:
    """When a BEP file has no ``name``, ``reference_key`` embeds the ``uri`` — that
    path-bearing field is scrubbed by the same deep pass, not just the ``uri``."""

    from nlfr.db import connect, initialize
    from nlfr.db.ingest import upsert_run
    from nlfr.ingest.bazel import parse_bazel_bep
    from nlfr.ingest.sqlite import ingest_evidence_bundle

    payload = b"nameless local output\n"
    out = tmp_path / "nameless.bin"
    out.write_bytes(payload)

    conn = initialize(connect(tmp_path / "nameless.sqlite"))
    run_id = upsert_run(
        conn,
        stable_key="nameless:cache-only:2026-07-06T00:00:00.000000Z",
        run_group="nameless",
        scenario="nameless",
        mode="cache-only",
        status="ingested",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["run:nameless"],
        redaction_state="safe",
    )
    events = [
        {"id": {"started": {}}, "started": {"command": "build"}},
        {
            "id": {"namedSetOfFiles": {"id": "0"}},
            "namedSetOfFiles": {"files": [{"uri": out.as_uri()}]},  # no "name" key
        },
    ]
    bep = tmp_path / "nameless.bep.json"
    bep.write_text("\n".join(json.dumps(e) for e in events) + "\n")
    bundle = parse_bazel_bep(bep, source_kind="collectable_v1")
    ingest_evidence_bundle(
        conn,
        run_id=run_id,
        run_stable_key="nameless:cache-only:2026-07-06T00:00:00.000000Z",
        bundle=bundle,
    )

    proof = export_proof_packet(conn, run_group="nameless")
    (ref,) = _artifact_verification_block(proof)["payload"]["references"]
    # Both the uri and the reference_key that embedded it are scrubbed.
    assert "[REDACTED:abs_path]" in ref["uri"]
    assert str(tmp_path) not in ref["reference_key"]
    assert "[REDACTED:abs_path]" in ref["reference_key"]
    assert _findings(proof) == []


# ---------------------------------------------------------------------------
# Regression: graph / runway stay clean; in-toto stays deterministic
# ---------------------------------------------------------------------------


def test_graph_and_runway_projections_remain_clean(tmp_path: Path) -> None:
    conn, _ = seed_db(tmp_path)
    graph = export_action_graph(conn, run_group=RUN_GROUP)
    runway = export_validation_runway(conn, run_group=RUN_GROUP)
    assert _findings(graph) == [], [f.format_line() for f in _findings(graph)]
    assert _findings(runway) == [], [f.format_line() for f in _findings(runway)]


def test_in_toto_export_is_deterministic_with_the_scrub(tmp_path: Path) -> None:
    """The scrub must be deterministic: two exports of the same DB are byte-identical."""

    conn, _ = seed_db(tmp_path)
    first = json.dumps(export_in_toto_statement(conn, run_group=RUN_GROUP), sort_keys=True)
    second = json.dumps(export_in_toto_statement(conn, run_group=RUN_GROUP), sort_keys=True)
    assert first == second
    # And the scrubbed placeholder is present (proving the scrub ran, not that the
    # determinism holds vacuously over un-scrubbed content).
    assert "[REDACTED:abs_path]" in first
