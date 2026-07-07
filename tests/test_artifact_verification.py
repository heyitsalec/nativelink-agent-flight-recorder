"""Independent artifact-integrity verification (GitHub issue #25).

NLFR does not trust the build tool's self-reports. These tests exercise the four
verification outcomes for BEP-referenced artifacts:

(a) local file whose recomputed SHA-256 matches the BEP-declared digest -> verified
(b) local file whose declared digest is WRONG -> mismatch + truth-label downgrade
(c) bytestream:// remote-only reference -> unverified_remote_reference (bazel#23250)
(d) BEP-declared local file that is missing on disk -> missing + downgrade
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from nlfr.db import connect, initialize
from nlfr.db.ingest import upsert_run
from nlfr.ingest.bazel import parse_bazel_bep
from nlfr.ingest.sqlite import ingest_evidence_bundle
from nlfr.projectors import export_proof_packet


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_bep(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    """Create local fixture files and a BEP that references all four cases."""

    good_bytes = b"verified artifact bytes\n"
    good_path = tmp_path / "good.txt"
    good_path.write_bytes(good_bytes)
    good_digest = _sha256(good_bytes)

    bad_bytes = b"the bytes on disk\n"
    bad_path = tmp_path / "bad.txt"
    bad_path.write_bytes(bad_bytes)
    wrong_digest = "0" * 64  # deliberately not the real digest of bad.txt

    missing_path = tmp_path / "missing.txt"  # intentionally not created

    files = [
        {
            "name": "good.txt",
            "uri": good_path.as_uri(),
            "digest": good_digest,
            "length": str(len(good_bytes)),
        },
        {
            "name": "bad.txt",
            "uri": bad_path.as_uri(),
            "digest": wrong_digest,
            "length": str(len(bad_bytes)),
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
    bep_path = tmp_path / "bazel.bep.json"
    bep_path.write_text("\n".join(json.dumps(event) for event in events) + "\n")
    return bep_path, {"good_digest": good_digest, "bad_bytes": _sha256(bad_bytes)}


def test_parse_bep_verifies_local_digests_and_labels_remote_references(tmp_path: Path) -> None:
    bep_path, digests = _write_bep(tmp_path)

    bundle = parse_bazel_bep(bep_path, source_kind="collectable_v1")
    references = {ref.name: ref for ref in bundle.artifact_references}
    assert set(references) == {"good.txt", "bad.txt", "remote.bin", "missing.txt"}

    # (a) matching local digest -> verified, truth label preserved.
    good = references["good.txt"]
    assert good.presence == "local_verified"
    assert good.digest_verified is True
    assert good.computed_digest == digests["good_digest"]
    assert good.source_kind == "collectable_v1"
    assert good.confidence == "high"
    assert "matches" in (good.verification_note or "")

    # (b) wrong declared digest -> mismatch, downgraded, computed digest recorded.
    bad = references["bad.txt"]
    assert bad.presence == "local_mismatch"
    assert bad.digest_verified is False
    assert bad.computed_digest == digests["bad_bytes"]
    assert bad.declared_digest == "0" * 64
    assert bad.source_kind == "derived_v1"  # never collectable on contradiction
    assert bad.confidence == "low"
    assert "does NOT match" in (bad.verification_note or "")

    # (c) bytestream:// remote-only reference -> unverified, cites bazel#23250.
    remote = references["remote.bin"]
    assert remote.presence == "unverified_remote_reference"
    assert remote.digest_verified is None
    assert remote.computed_digest is None
    assert remote.source_kind == "derived_v1"
    assert remote.confidence == "low"
    assert "bazelbuild/bazel#23250" in (remote.verification_note or "")

    # (d) declared local file missing on disk -> missing, downgraded.
    missing = references["missing.txt"]
    assert missing.presence == "missing"
    assert missing.digest_verified is None
    assert missing.computed_digest is None
    assert missing.source_kind == "derived_v1"
    assert missing.confidence == "low"
    assert "not present on disk" in (missing.verification_note or "")


def test_proof_packet_surfaces_artifact_verification_summary(tmp_path: Path) -> None:
    bep_path, _ = _write_bep(tmp_path)

    conn = initialize(connect(tmp_path / "nlfr.sqlite"))
    run_id = upsert_run(
        conn,
        stable_key="verify-demo:cache-only:2026-07-06T00:00:00.000000Z",
        run_group="verify-demo",
        scenario="artifact-verify",
        mode="cache-only",
        status="ingested",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["run:verify-demo"],
        redaction_state="safe",
    )
    bundle = parse_bazel_bep(bep_path, source_kind="collectable_v1")
    counts = ingest_evidence_bundle(
        conn,
        run_id=run_id,
        run_stable_key="verify-demo:cache-only:2026-07-06T00:00:00.000000Z",
        bundle=bundle,
    )
    assert counts["artifact_references"] == 4

    proof = export_proof_packet(conn, run_group="verify-demo")

    # Top-level summary carries the verification rollup.
    assert proof["summary"]["artifact_references"] == 4
    summary = proof["summary"]["artifact_verification"]
    assert summary == {
        "total": 4,
        "verified_count": 1,
        "mismatched": 1,
        "missing": 1,
        "unverified_remote": 1,
    }

    # Dedicated proof block with the same metrics and an honest, cited claim.
    block = next(
        item for item in proof["blocks"] if item["id"] == "artifact_verification"
    )
    assert block["title"] == "Artifact Integrity Verification"
    assert block["metrics"] == summary
    assert any("bazelbuild/bazel#23250" in claim for claim in block["claims"])

    payload_by_name = {ref["name"]: ref for ref in block["payload"]["references"]}
    assert payload_by_name["good.txt"]["presence"] == "local_verified"
    assert payload_by_name["good.txt"]["digest_verified"] is True
    assert payload_by_name["bad.txt"]["presence"] == "local_mismatch"
    assert payload_by_name["bad.txt"]["digest_verified"] is False
    assert payload_by_name["remote.bin"]["presence"] == "unverified_remote_reference"
    assert payload_by_name["remote.bin"]["digest_verified"] is None
    assert payload_by_name["missing.txt"]["presence"] == "missing"

    # The scope block (index 0) must be unchanged: this feature only appends.
    assert proof["blocks"][0]["title"] == "Proof Scope"


def test_verification_can_be_disabled(tmp_path: Path) -> None:
    bep_path, _ = _write_bep(tmp_path)
    bundle = parse_bazel_bep(bep_path, verify_artifacts=False)
    assert bundle.artifact_references == []
