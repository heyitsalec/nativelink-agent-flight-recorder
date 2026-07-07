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

FIXTURE_ROOT = Path(__file__).resolve().parents[0] / "fixtures" / "bazel"


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
        "present_unverified": 0,
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


def test_output_group_names_are_not_fabricated_as_artifacts() -> None:
    """Regression: a TargetComplete.output_group is {name, fileSets, inlineFiles}.

    The group ``name`` ("default", "_validation") is NOT a filename; the real files
    arrive via ``fileSets`` ids that resolve to separately-emitted namedSetOfFiles
    events. The pre-fix parser treated every OutputGroup dict as a File (it has a
    ``name`` key), fabricating one bogus artifact row per output group on every real
    build. Only the actual files (from namedSetOfFiles + OutputGroup.inlineFiles)
    may appear.
    """

    bundle = parse_bazel_bep(
        FIXTURE_ROOT / "bep-output-group.jsonl",
        source_kind="collectable_v1",
        evidence_ref="fixture:bep-output-group.jsonl",
    )
    names = {ref.name for ref in bundle.artifact_references}

    # Only the real files are referenced: the two namedSetOfFiles members plus the
    # inline file embedded in the _validation output group.
    assert names == {"app.bin", "validation.out", "inline.stamp"}

    # ZERO rows named after (or keyed on) an output group name.
    assert "default" not in names
    assert "_validation" not in names
    for ref in bundle.artifact_references:
        assert "default" not in ref.reference_key
        assert "_validation" not in ref.reference_key
        # None of the collected payloads is an OutputGroup (would carry a fileSets ref).
        assert ref.uri and ref.uri.startswith("bytestream://")
        assert ref.presence == "unverified_remote_reference"


def test_non_sha256_digest_function_skips_comparison_without_downgrade(tmp_path: Path) -> None:
    """A --digest_function=blake3 build declares digests NLFR cannot recompute.

    Comparing a recomputed SHA-256 against a BLAKE3 digest would fabricate an
    unconditional mismatch and wrongly downgrade honest evidence. The file is
    present, so presence is recorded as ``local_present`` with digest_verified=None
    and the truth label is NOT downgraded.
    """

    payload = b"blake3-configured build output\n"
    artifact = tmp_path / "out.bin"
    artifact.write_bytes(payload)

    events = [
        {
            "id": {"started": {}},
            "started": {
                "command": "build",
                "optionsDescription": "--digest_function=BLAKE3 --remote_cache=grpc://cache:443",
            },
        },
        {
            "id": {"namedSetOfFiles": {"id": "0"}},
            "namedSetOfFiles": {
                "files": [
                    {
                        # A real BLAKE3 digest is 64 hex chars too, but it is NOT the
                        # SHA-256 of the bytes; comparing would falsely mismatch.
                        "name": "out.bin",
                        "uri": artifact.as_uri(),
                        "digest": "abcd" * 16,
                        "length": str(len(payload)),
                    }
                ]
            },
        },
    ]
    bep_path = tmp_path / "blake3.bep.json"
    bep_path.write_text("\n".join(json.dumps(event) for event in events) + "\n")

    bundle = parse_bazel_bep(bep_path, source_kind="collectable_v1")
    (ref,) = bundle.artifact_references
    assert ref.presence == "local_present"
    assert ref.digest_verified is None
    assert ref.computed_digest is None
    # NOT downgraded: honest presence claim is preserved, not forced to derived_v1/low.
    assert ref.source_kind == "collectable_v1"
    assert ref.confidence == "medium"
    assert "BLAKE3" in (ref.verification_note or "")


def test_non_64_hex_declared_digest_skips_comparison(tmp_path: Path) -> None:
    """Defensive: a SHA-1 (40 hex) declared digest cannot be a SHA-256 comparison.

    Even with no --digest_function in the BEP, a declared digest that is not 64 hex
    chars is not recomputable as SHA-256, so the comparison is skipped rather than
    fabricating a mismatch.
    """

    payload = b"sha1-shaped digest declared\n"
    artifact = tmp_path / "legacy.bin"
    artifact.write_bytes(payload)

    events = [
        {"id": {"started": {}}, "started": {"command": "build"}},
        {
            "id": {"namedSetOfFiles": {"id": "0"}},
            "namedSetOfFiles": {
                "files": [
                    {
                        "name": "legacy.bin",
                        "uri": artifact.as_uri(),
                        "digest": "0" * 40,  # SHA-1 length, not SHA-256
                        "length": str(len(payload)),
                    }
                ]
            },
        },
    ]
    bep_path = tmp_path / "sha1.bep.json"
    bep_path.write_text("\n".join(json.dumps(event) for event in events) + "\n")

    bundle = parse_bazel_bep(bep_path, source_kind="collectable_v1")
    (ref,) = bundle.artifact_references
    assert ref.presence == "local_present"
    assert ref.digest_verified is None
    assert ref.source_kind == "collectable_v1"
    assert ref.confidence == "medium"
    assert "not a recomputable SHA-256" in (ref.verification_note or "")


def test_default_sha256_build_still_verifies_and_mismatches(tmp_path: Path) -> None:
    """The default (no --digest_function override) path is unchanged.

    A 64-hex SHA-256 digest is compared as before: a match verifies at high
    confidence, a wrong digest downgrades to local_mismatch.
    """

    good = b"real sha256 output\n"
    good_path = tmp_path / "good.bin"
    good_path.write_bytes(good)

    bad_path = tmp_path / "bad.bin"
    bad_path.write_bytes(b"the bytes on disk\n")

    events = [
        # optionsDescription present but names no --digest_function => default SHA-256.
        {
            "id": {"started": {}},
            "started": {"command": "build", "optionsDescription": "--config=ci"},
        },
        {
            "id": {"namedSetOfFiles": {"id": "0"}},
            "namedSetOfFiles": {
                "files": [
                    {
                        "name": "good.bin",
                        "uri": good_path.as_uri(),
                        "digest": _sha256(good),
                        "length": str(len(good)),
                    },
                    {
                        "name": "bad.bin",
                        "uri": bad_path.as_uri(),
                        "digest": "0" * 64,
                        "length": "18",
                    },
                ]
            },
        },
    ]
    bep_path = tmp_path / "default.bep.json"
    bep_path.write_text("\n".join(json.dumps(event) for event in events) + "\n")

    bundle = parse_bazel_bep(bep_path, source_kind="collectable_v1")
    refs = {ref.name: ref for ref in bundle.artifact_references}

    assert refs["good.bin"].presence == "local_verified"
    assert refs["good.bin"].digest_verified is True
    assert refs["good.bin"].confidence == "high"

    assert refs["bad.bin"].presence == "local_mismatch"
    assert refs["bad.bin"].digest_verified is False
    assert refs["bad.bin"].source_kind == "derived_v1"
    assert refs["bad.bin"].confidence == "low"
    # optionsDescription was visible and named no override, so no uncertainty caveat.
    assert "did not expose" not in (refs["bad.bin"].verification_note or "")
