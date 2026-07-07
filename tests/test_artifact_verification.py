"""Independent artifact-integrity verification (GitHub issue #25).

NLFR does not trust the build tool's self-reports. These tests exercise the four
verification outcomes for BEP-referenced artifacts:

(a) local file whose recomputed SHA-256 matches the BEP-declared digest -> verified
(b) local file whose declared digest is WRONG -> mismatch + truth-label downgrade
(c) bytestream:// remote-only reference -> unverified_remote_reference (bazel#23250)
(d) BEP-declared local file that is missing on disk -> missing + downgrade
"""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

from nlfr.db import connect, initialize
from nlfr.db.ingest import upsert_run
from nlfr.ingest.bazel import parse_bazel_bep
from nlfr.ingest.sqlite import ingest_evidence_bundle
from nlfr.ingest.verification import ProbeResult, build_reference, iter_bep_file_references
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
        # Remote-verification tiers stay 0 with no CAS probe injected (issue #81 A).
        "remote_verified": 0,
        "remote_present": 0,
        "remote_mismatch": 0,
        "remote_missing": 0,
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


def test_symlink_file_is_captured_not_dropped(tmp_path: Path) -> None:
    """A BEP File whose oneof is ``symlinkTargetPath`` must be recorded, truthfully.

    Bazel's File proto lets a File populate ``symlink_target_path`` INSTEAD of
    ``uri`` — a symlink output carries no digest to recompute. An earlier fix that
    required uri/digest/pathPrefix/length alongside ``name`` structurally mistook a
    symlink-only entry for an OutputGroup and SILENTLY dropped it. It must now be
    captured: presence taken from an existence probe of the target, digest_verified
    null (a symlink declares no digest), and never promoted to a verified claim.
    """

    # The symlink's target exists on disk -> honest presence is local_present.
    target = tmp_path / "resolved" / "payload.bin"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"symlink target bytes\n")

    events = [
        {"id": {"started": {}}, "started": {"command": "build"}},
        {
            "id": {"namedSetOfFiles": {"id": "0"}},
            "namedSetOfFiles": {
                "files": [
                    {"name": "link-to-payload", "symlinkTargetPath": str(target)},
                    {"name": "dangling-link", "symlinkTargetPath": str(tmp_path / "nope.bin")},
                ]
            },
        },
    ]
    bep_path = tmp_path / "symlink.bep.json"
    bep_path.write_text("\n".join(json.dumps(event) for event in events) + "\n")

    # The parser no longer drops the symlink entries: both are collected as Files.
    named_set_event = events[1]
    collected = iter_bep_file_references(named_set_event)
    assert {f["name"] for f in collected} == {"link-to-payload", "dangling-link"}

    bundle = parse_bazel_bep(bep_path, source_kind="collectable_v1")
    refs = {ref.name: ref for ref in bundle.artifact_references}
    assert set(refs) == {"link-to-payload", "dangling-link"}

    # Target exists -> present, but no digest was (or could be) cross-checked.
    resolved = refs["link-to-payload"]
    assert resolved.presence == "local_present"
    assert resolved.digest_verified is None
    assert resolved.computed_digest is None
    assert resolved.source_kind == "collectable_v1"  # not overclaimed as verified
    assert "symlink" in (resolved.verification_note or "").lower()

    # Target absent -> missing, downgraded; still recorded rather than dropped.
    dangling = refs["dangling-link"]
    assert dangling.presence == "missing"
    assert dangling.digest_verified is None
    assert dangling.source_kind == "derived_v1"


def test_inline_contents_file_is_hashed_and_verified(tmp_path: Path) -> None:
    """A BEP File whose oneof is inline ``contents`` is hashable from the BEP itself.

    Inline bytes are base64 in proto3 JSON, so NLFR decodes and SHA-256s them with
    no filesystem access. A declared SHA-256 that matches verifies at high
    confidence; the entry must be captured, never dropped as an OutputGroup.
    """

    raw = b"inline artifact bytes\n"
    encoded = base64.b64encode(raw).decode("ascii")
    digest = _sha256(raw)

    events = [
        {"id": {"started": {}}, "started": {"command": "build"}},
        {
            "id": {"namedSetOfFiles": {"id": "0"}},
            "namedSetOfFiles": {
                "files": [
                    {
                        "name": "inline.stamp",
                        "contents": encoded,
                        "digest": digest,
                        "length": str(len(raw)),
                    }
                ]
            },
        },
    ]
    bep_path = tmp_path / "inline.bep.json"
    bep_path.write_text("\n".join(json.dumps(event) for event in events) + "\n")

    bundle = parse_bazel_bep(bep_path, source_kind="collectable_v1")
    (ref,) = bundle.artifact_references
    assert ref.name == "inline.stamp"
    assert ref.presence == "local_verified"
    assert ref.digest_verified is True
    assert ref.computed_digest == digest
    assert ref.confidence == "high"


def test_inline_contents_wrong_digest_downgrades(tmp_path: Path) -> None:
    """Inline bytes whose declared SHA-256 is wrong are a real mismatch, not dropped."""

    raw = b"the true inline bytes\n"
    encoded = base64.b64encode(raw).decode("ascii")

    events = [
        {"id": {"started": {}}, "started": {"command": "build"}},
        {
            "id": {"namedSetOfFiles": {"id": "0"}},
            "namedSetOfFiles": {
                "files": [
                    {"name": "inline.stamp", "contents": encoded, "digest": "0" * 64}
                ]
            },
        },
    ]
    bep_path = tmp_path / "inline-bad.bep.json"
    bep_path.write_text("\n".join(json.dumps(event) for event in events) + "\n")

    bundle = parse_bazel_bep(bep_path, source_kind="collectable_v1")
    (ref,) = bundle.artifact_references
    assert ref.presence == "local_mismatch"
    assert ref.digest_verified is False
    assert ref.source_kind == "derived_v1"
    assert ref.confidence == "low"


def test_output_group_still_rejected_alongside_symlink_signal_keys() -> None:
    """The structural OutputGroup rejection survives adding symlink/contents keys.

    Adding ``symlinkTargetPath``/``contents`` to the File-signal set must not let an
    OutputGroup ({name, fileSets, inlineFiles}) be mistaken for a File: an
    OutputGroup never carries either key, so a group-name dict is still dropped.
    """

    event = {
        "id": {"targetCompleted": {}},
        "completed": {
            "outputGroup": [
                {"name": "default", "fileSets": [{"id": "0"}]},
                {"name": "_validation"},  # bare group name, no File signals
            ]
        },
    }
    # No inlineFiles on either group -> zero Files harvested, no group name leaks in.
    assert iter_bep_file_references(event) == []


# --------------------------------------------------------------------------- #
# Injectable CAS probe seam (GitHub issue #81, part A)
#
# NLFR does not implement a gRPC/REAPI probe here (that is #81 part B, an optional
# dependency extra). Part A lands the label VOCABULARY and the injectable SEAM: a
# plain Python callable is passed in, its verdict is mapped to honest remote_*
# labels, and — crucially — with NO probe the historical
# ``unverified_remote_reference`` behavior is byte-for-byte unchanged. These tests
# use FAKE probes (no network, no dependency) to exercise every mapping.
# --------------------------------------------------------------------------- #

_REMOTE_URI = "bytestream://remote.buildbuddy.io/blobs/deadbeefdeadbeef/1024"
_REMOTE_DECLARED_DIGEST = _sha256(b"the true remote blob bytes\n")  # a real 64-hex SHA-256


def _build_remote_reference(cas_probe, *, declared_digest=_REMOTE_DECLARED_DIGEST):
    """Build ONE remote (bytestream://) reference through the injectable seam."""

    payload = {
        "name": "remote.bin",
        "uri": _REMOTE_URI,
        "digest": declared_digest,
        "length": "1024",
    }
    return build_reference(
        payload,
        label="//pkg:remote",
        index=0,
        source_kind="collectable_v1",
        evidence_refs=["run:probe-demo"],
        artifact_base=None,
        cas_probe=cas_probe,
    )


def test_cas_probe_present_and_matching_digest_verifies_remote() -> None:
    """present + recomputed SHA-256 matches declared -> remote_verified (high)."""

    def probe(uri, declared_digest, declared_size):
        return ProbeResult(present=True, computed_digest=_REMOTE_DECLARED_DIGEST)

    ref = _build_remote_reference(probe)
    assert ref.presence == "remote_verified"
    assert ref.digest_verified is True
    assert ref.computed_digest == _REMOTE_DECLARED_DIGEST
    # remote_verified is the ONLY remote tier that keeps a collectable_v1/high claim.
    assert ref.source_kind == "collectable_v1"
    assert ref.confidence == "high"
    assert "matches" in (ref.verification_note or "")


def test_cas_probe_present_but_wrong_digest_downgrades_to_remote_mismatch() -> None:
    """present + recomputed SHA-256 contradicts declared -> remote_mismatch (low)."""

    def probe(uri, declared_digest, declared_size):
        # The CAS bytes hash to something other than the BEP-declared digest.
        return ProbeResult(present=True, computed_digest=_sha256(b"different remote bytes\n"))

    ref = _build_remote_reference(probe)
    assert ref.presence == "remote_mismatch"
    assert ref.digest_verified is False
    assert ref.computed_digest == _sha256(b"different remote bytes\n")
    assert ref.source_kind == "derived_v1"  # never collectable on contradiction
    assert ref.confidence == "low"
    assert "does NOT match" in (ref.verification_note or "")


def test_cas_probe_present_without_crosscheck_records_remote_present() -> None:
    """present but nothing to hash-check -> remote_present (medium), digest unproven.

    Covers both no-cross-check shapes: the probe confirmed presence without hashing
    the bytes (computed_digest is None), and a present blob whose BEP declared no
    digest to compare against.
    """

    def existence_only_probe(uri, declared_digest, declared_size):
        return ProbeResult(present=True, computed_digest=None)

    ref = _build_remote_reference(existence_only_probe)
    assert ref.presence == "remote_present"
    assert ref.digest_verified is None
    assert ref.source_kind == "collectable_v1"  # honestly present, not downgraded
    assert ref.confidence == "medium"

    # No declared digest to cross-check against -> also remote_present, even though
    # the probe DID hash the bytes.
    def hashing_probe(uri, declared_digest, declared_size):
        return ProbeResult(present=True, computed_digest=_sha256(b"whatever\n"))

    ref_no_declared = _build_remote_reference(hashing_probe, declared_digest=None)
    assert ref_no_declared.presence == "remote_present"
    assert ref_no_declared.digest_verified is None
    assert ref_no_declared.confidence == "medium"


def test_cas_probe_absent_marks_remote_missing() -> None:
    """CAS confirms the blob ABSENT -> remote_missing (low) — the bazel#23250 mode."""

    def probe(uri, declared_digest, declared_size):
        return ProbeResult(present=False)

    ref = _build_remote_reference(probe)
    assert ref.presence == "remote_missing"
    assert ref.digest_verified is None
    assert ref.computed_digest is None
    assert ref.source_kind == "derived_v1"
    assert ref.confidence == "low"
    assert "bazelbuild/bazel#23250" in (ref.verification_note or "")
    assert "ABSENT" in (ref.verification_note or "")


def test_no_cas_probe_keeps_exact_unverified_remote_default() -> None:
    """With NO probe (the default) the historical downgrade is byte-for-byte unchanged."""

    ref = _build_remote_reference(None)
    assert ref.presence == "unverified_remote_reference"
    assert ref.digest_verified is None
    assert ref.computed_digest is None
    assert ref.source_kind == "derived_v1"
    assert ref.confidence == "low"
    note = ref.verification_note or ""
    assert "bazelbuild/bazel#23250" in note
    assert "does not verify remote CAS in v1" in note


def test_cas_probe_inconclusive_falls_back_to_unverified_remote() -> None:
    """A probe that returns None OR raises never fabricates a verdict -> unverified."""

    ref_none = _build_remote_reference(lambda uri, digest, size: None)
    assert ref_none.presence == "unverified_remote_reference"
    assert ref_none.source_kind == "derived_v1"
    assert ref_none.confidence == "low"
    assert "no verdict" in (ref_none.verification_note or "")

    def boom(uri, declared_digest, declared_size):
        raise RuntimeError("CAS endpoint unreachable")

    ref_raise = _build_remote_reference(boom)
    assert ref_raise.presence == "unverified_remote_reference"
    assert ref_raise.source_kind == "derived_v1"
    assert "no verdict" in (ref_raise.verification_note or "")


def test_cas_probe_is_threaded_through_parse_bazel_bep(tmp_path: Path) -> None:
    """The probe reaches remote references through parse_bazel_bep, never local ones.

    Proves the seam is wired end-to-end (parser -> build_reference -> _verify) and
    that local files are still verified locally without ever touching the probe.
    """

    good_bytes = b"local verified bytes\n"
    good_path = tmp_path / "good.txt"
    good_path.write_bytes(good_bytes)
    good_digest = _sha256(good_bytes)

    files = [
        {"name": "good.txt", "uri": good_path.as_uri(), "digest": good_digest, "length": str(len(good_bytes))},
        {"name": "remote.bin", "uri": _REMOTE_URI, "digest": _REMOTE_DECLARED_DIGEST, "length": "1024"},
    ]
    events = [
        {"id": {"started": {}}, "started": {"command": "build"}},
        {"id": {"namedSetOfFiles": {"id": "0"}}, "namedSetOfFiles": {"files": files}},
    ]
    bep_path = tmp_path / "bazel.bep.json"
    bep_path.write_text("\n".join(json.dumps(event) for event in events) + "\n")

    calls: list[tuple] = []

    def probe(uri, declared_digest, declared_size):
        calls.append((uri, declared_digest, declared_size))
        return ProbeResult(present=True, computed_digest=declared_digest)

    bundle = parse_bazel_bep(bep_path, source_kind="collectable_v1", cas_probe=probe)
    refs = {ref.name: ref for ref in bundle.artifact_references}

    # The local file is verified locally; the probe is NOT invoked for it.
    assert refs["good.txt"].presence == "local_verified"
    assert refs["good.txt"].digest_verified is True

    # The remote reference is verified via the injected probe.
    assert refs["remote.bin"].presence == "remote_verified"
    assert refs["remote.bin"].digest_verified is True
    assert refs["remote.bin"].confidence == "high"

    # The probe saw ONLY the remote reference, with its declared digest and size.
    assert calls == [(_REMOTE_URI, _REMOTE_DECLARED_DIGEST, 1024)]


def test_parse_bazel_bep_without_probe_is_unchanged(tmp_path: Path) -> None:
    """Default parse (no cas_probe) still labels remote refs unverified_remote_reference."""

    bep_path, _ = _write_bep(tmp_path)
    bundle = parse_bazel_bep(bep_path, source_kind="collectable_v1")  # no cas_probe
    refs = {ref.name: ref for ref in bundle.artifact_references}
    assert refs["remote.bin"].presence == "unverified_remote_reference"
    assert refs["remote.bin"].source_kind == "derived_v1"


def test_proof_summary_counts_remote_verification_tiers(tmp_path: Path) -> None:
    """The proof packet rolls up all four probe-derived remote tiers (issue #81 A).

    Ingests four remote references — one per verdict — through a fake probe, then
    asserts the ``artifact_verification`` summary/metrics count each remote tier and
    the block surfaces the honest remote claims.
    """

    files = [
        {"name": "rv.bin", "uri": "bytestream://cas/blobs/rv/1", "digest": _sha256(b"verified remote\n"), "length": "1"},
        {"name": "rp.bin", "uri": "bytestream://cas/blobs/rp/1", "digest": _sha256(b"present remote\n"), "length": "1"},
        {"name": "rm.bin", "uri": "bytestream://cas/blobs/rm/1", "digest": _sha256(b"declared digest\n"), "length": "1"},
        {"name": "rx.bin", "uri": "bytestream://cas/blobs/rx/1", "digest": _sha256(b"absent remote\n"), "length": "1"},
    ]
    events = [
        {"id": {"started": {}}, "started": {"command": "build"}},
        {"id": {"namedSetOfFiles": {"id": "0"}}, "namedSetOfFiles": {"files": files}},
    ]
    bep_path = tmp_path / "remote.bep.json"
    bep_path.write_text("\n".join(json.dumps(event) for event in events) + "\n")

    def probe(uri, declared_digest, declared_size):
        if uri.endswith("/rv/1"):
            return ProbeResult(present=True, computed_digest=declared_digest)  # verified
        if uri.endswith("/rp/1"):
            return ProbeResult(present=True, computed_digest=None)  # present, unchecked
        if uri.endswith("/rm/1"):
            return ProbeResult(present=True, computed_digest=_sha256(b"actual bytes differ\n"))  # mismatch
        return ProbeResult(present=False)  # missing

    conn = initialize(connect(tmp_path / "nlfr.sqlite"))
    run_id = upsert_run(
        conn,
        stable_key="remote-demo:cache-only:2026-07-06T00:00:00.000000Z",
        run_group="remote-demo",
        scenario="remote-verify",
        mode="cache-only",
        status="ingested",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["run:remote-demo"],
        redaction_state="safe",
    )
    bundle = parse_bazel_bep(bep_path, source_kind="collectable_v1", cas_probe=probe)
    counts = ingest_evidence_bundle(
        conn,
        run_id=run_id,
        run_stable_key="remote-demo:cache-only:2026-07-06T00:00:00.000000Z",
        bundle=bundle,
    )
    assert counts["artifact_references"] == 4

    proof = export_proof_packet(conn, run_group="remote-demo")
    summary = proof["summary"]["artifact_verification"]
    assert summary["total"] == 4
    assert summary["remote_verified"] == 1
    assert summary["remote_present"] == 1
    assert summary["remote_mismatch"] == 1
    assert summary["remote_missing"] == 1
    # The local_* rollups are untouched (no local references in this run).
    assert summary["verified_count"] == 0
    assert summary["unverified_remote"] == 0

    block = next(item for item in proof["blocks"] if item["id"] == "artifact_verification")
    assert block["metrics"] == summary
    joined = " ".join(block["claims"])
    assert "Independently verified 1 remote reference" in joined
    assert "Downgraded 1 remote reference(s) the CAS confirms are ABSENT" in joined


# --------------------------------------------------------------------------- #
# Malformed / hostile probe results (issue #81 part A — adversarial hardening)
#
# A cas_probe is INJECTED, untrusted code. ProbeResult carries type hints but no
# runtime enforcement, so a probe can hand back a wrong-typed result (int digest,
# non-bool present), a non-ProbeResult object (tuple/dict), or an object whose
# attribute access raises. Every such case must be treated EXACTLY like a
# probe-returned-None: unverified_remote_reference with an honest note naming the
# malformation — never an uncaught exception, never a stronger label, never a
# silently coerced digest compare. These use FAKE probes (no network, no dep).
# --------------------------------------------------------------------------- #


def _assert_inconclusive_malformed(ref, *, field_marker: str) -> None:
    """Every malformed-probe outcome degrades to the exact unverified state."""

    assert ref is not None
    assert ref.presence == "unverified_remote_reference"
    assert ref.digest_verified is None
    assert ref.computed_digest is None
    assert ref.source_kind == "derived_v1"  # never promoted off a malformed result
    assert ref.confidence == "low"
    note = ref.verification_note or ""
    assert "malformed" in note
    assert "inconclusive" in note
    assert field_marker in note
    assert "bazelbuild/bazel#23250" in note


def test_cas_probe_int_computed_digest_is_inconclusive_not_a_crash() -> None:
    """computed_digest as int -> unverified (would otherwise crash _normalize_digest)."""

    def probe(uri, declared_digest, declared_size):
        return ProbeResult(present=True, computed_digest=123456)  # type: ignore[arg-type]

    ref = _build_remote_reference(probe)
    _assert_inconclusive_malformed(ref, field_marker="computed_digest: int")


def test_cas_probe_non_bool_present_is_inconclusive() -> None:
    """present as a bool-like int or a string is malformed -> unverified.

    isinstance(x, bool) rejects 1/0 (int) and "yes" (str); NLFR must not accept a
    truthy non-bool as a real presence verdict.
    """

    def int_present(uri, declared_digest, declared_size):
        return ProbeResult(present=1, computed_digest=None)  # type: ignore[arg-type]

    _assert_inconclusive_malformed(
        _build_remote_reference(int_present), field_marker="present: int"
    )

    def str_present(uri, declared_digest, declared_size):
        return ProbeResult(present="yes", computed_digest=None)  # type: ignore[arg-type]

    _assert_inconclusive_malformed(
        _build_remote_reference(str_present), field_marker="present: str"
    )


def test_cas_probe_non_proberesult_return_is_inconclusive() -> None:
    """A plain tuple or dict (not a ProbeResult) is malformed -> unverified."""

    def tuple_probe(uri, declared_digest, declared_size):
        return (True, _REMOTE_DECLARED_DIGEST)  # type: ignore[return-value]

    _assert_inconclusive_malformed(
        _build_remote_reference(tuple_probe), field_marker="not a ProbeResult (tuple)"
    )

    def dict_probe(uri, declared_digest, declared_size):
        return {"present": True, "computed_digest": _REMOTE_DECLARED_DIGEST}  # type: ignore[return-value]

    _assert_inconclusive_malformed(
        _build_remote_reference(dict_probe), field_marker="not a ProbeResult (dict)"
    )


def test_cas_probe_attribute_access_that_raises_is_inconclusive() -> None:
    """A ProbeResult subclass whose attribute access RAISES -> unverified, never a crash.

    Constructed via object.__new__ to bypass the frozen-dataclass __init__ (a
    read-only property would otherwise reject the field assignment). isinstance()
    passes, so validation actually reads the throwing attribute — proving the
    consumption path, not just the call, is wrapped.
    """

    class _ThrowingProbe(ProbeResult):
        @property
        def present(self):  # type: ignore[override]
            raise RuntimeError("hostile probe: attribute access blows up")

    throwing = object.__new__(_ThrowingProbe)

    def probe(uri, declared_digest, declared_size):
        return throwing

    _assert_inconclusive_malformed(
        _build_remote_reference(probe), field_marker="attribute access raised"
    )
