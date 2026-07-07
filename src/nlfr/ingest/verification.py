"""Independent artifact-integrity verification for ingested BEP references.

Doctrine: the recorder does not trust the build tool's self-reports. The Bazel
Build Event Protocol can reference an artifact at a ``bytestream://`` URI even
when the cache upload actually FAILED (bazelbuild/bazel#23250). Repeating BEP's
file references without checking them would let a proof packet claim evidence
that does not exist.

This module verifies what it can and explicitly labels what it cannot:

* local files (``file://`` or plain paths) get their SHA-256 recomputed and
  compared against the BEP-declared digest; a mismatch or a missing file
  downgrades the truth label and records an explicit note;
* remote-only references are never promoted to ``collectable_v1`` / ``high``
  presence claims — they are marked ``unverified_remote_reference`` citing the
  upstream bug.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from nlfr.ingest.models import ArtifactReferenceEvidence

BAZEL_UPLOAD_BUG_REF = "bazelbuild/bazel#23250"

# URI schemes whose bytes live in a remote CAS / server and cannot be verified
# locally without a REAPI/CAS probe (a documented follow-up, not part of v1).
_REMOTE_SCHEMES = frozenset(
    {"bytestream", "grpc", "grpcs", "http", "https", "remote", "actioncache"}
)

_HASH_CHUNK_BYTES = 1024 * 1024

# Presence markers surfaced on every artifact reference.
PRESENCE_LOCAL_VERIFIED = "local_verified"
PRESENCE_LOCAL_MISMATCH = "local_mismatch"
PRESENCE_MISSING = "missing"
PRESENCE_UNVERIFIED_REMOTE = "unverified_remote_reference"


def iter_bep_file_references(event: dict[str, Any]) -> list[dict[str, Any]]:
    """Yield raw BEP ``File`` payloads carried by a single build event.

    Covers the event shapes that name output files: ``namedSetOfFiles``,
    ``testResult.testActionOutput``, and ``completed.importantOutput``.
    """

    files: list[dict[str, Any]] = []

    named_set = event.get("namedSetOfFiles")
    if isinstance(named_set, dict):
        _collect_files(files, named_set.get("files"))

    test_result = event.get("testResult")
    if isinstance(test_result, dict):
        _collect_files(files, test_result.get("testActionOutput"))

    completed = event.get("completed")
    if isinstance(completed, dict):
        _collect_files(files, completed.get("importantOutput"))
        _collect_files(files, completed.get("outputGroup"))

    return files


def build_reference(
    file_payload: dict[str, Any],
    *,
    label: str | None,
    index: int,
    source_kind: str,
    evidence_refs: list[str],
    artifact_base: Path | None,
    redaction_state: str = "safe",
) -> ArtifactReferenceEvidence | None:
    """Verify a single BEP file payload and return an evidence record.

    Returns ``None`` when the payload carries neither a URI nor a name and thus
    cannot be turned into a stable reference.
    """

    name = _string_or_none(file_payload.get("name"))
    uri = _string_or_none(file_payload.get("uri"))
    declared_digest = _declared_digest(file_payload)
    declared_size = _declared_size(file_payload)
    if uri is None and name is None:
        return None

    presence, digest_verified, computed_digest, local_path, note, ref_source_kind, confidence = (
        _verify(uri, declared_digest, artifact_base, source_kind)
    )

    reference_key = _reference_key(label, name, uri, index)
    return ArtifactReferenceEvidence(
        source_kind=ref_source_kind,
        confidence=confidence,
        evidence_refs=list(evidence_refs),
        redaction_state=redaction_state,
        reference_key=reference_key,
        name=name,
        uri=uri,
        local_path=local_path,
        declared_digest=declared_digest,
        declared_size_bytes=declared_size,
        computed_digest=computed_digest,
        digest_verified=digest_verified,
        presence=presence,
        verification_note=note,
        target_label=label,
    )


def _verify(
    uri: str | None,
    declared_digest: str | None,
    artifact_base: Path | None,
    source_kind: str,
) -> tuple[str, bool | None, str | None, str | None, str, str, str]:
    """Return the verification tuple for one reference.

    Tuple: (presence, digest_verified, computed_digest, local_path, note,
    source_kind, confidence).
    """

    local_path = _local_path(uri, artifact_base)

    if local_path is None:
        # No resolvable local path: either a remote CAS URI or a bare reference
        # we cannot open. Either way, presence is unverifiable locally.
        note = (
            "BEP references this artifact at a remote/opaque URI; the cache upload "
            "may have failed and the bytes are not proven to exist "
            f"({BAZEL_UPLOAD_BUG_REF}). NLFR does not claim local presence and does "
            "not verify remote CAS in v1."
        )
        return (
            PRESENCE_UNVERIFIED_REMOTE,
            None,
            None,
            None,
            note,
            _downgraded_source_kind(source_kind),
            "low",
        )

    if not local_path.exists() or not local_path.is_file():
        note = (
            "BEP declares a local artifact that is not present on disk; presence "
            "downgraded and no digest could be recomputed."
        )
        return (
            PRESENCE_MISSING,
            None,
            None,
            str(local_path),
            note,
            _downgraded_source_kind(source_kind),
            "low",
        )

    computed_digest = _sha256_file(local_path)

    if declared_digest is None:
        note = (
            "Recomputed local SHA-256; BEP declared no digest, so the match is "
            "self-attested rather than cross-checked."
        )
        return (
            PRESENCE_LOCAL_VERIFIED,
            None,
            computed_digest,
            str(local_path),
            note,
            source_kind,
            "medium",
        )

    if _normalize_digest(computed_digest) == _normalize_digest(declared_digest):
        note = "Recomputed local SHA-256 matches the BEP-declared digest."
        return (
            PRESENCE_LOCAL_VERIFIED,
            True,
            computed_digest,
            str(local_path),
            note,
            source_kind,
            "high",
        )

    note = (
        "Recomputed local SHA-256 does NOT match the BEP-declared digest; the "
        "build tool's self-report is contradicted by the bytes on disk. Presence "
        "downgraded."
    )
    return (
        PRESENCE_LOCAL_MISMATCH,
        False,
        computed_digest,
        str(local_path),
        note,
        _downgraded_source_kind(source_kind),
        "low",
    )


def _local_path(uri: str | None, artifact_base: Path | None) -> Path | None:
    """Resolve a BEP URI to a local filesystem path, or ``None`` if not local."""

    if uri is None:
        return None

    parts = urlsplit(uri)
    scheme = parts.scheme.lower()

    if scheme in _REMOTE_SCHEMES:
        return None

    if scheme == "file":
        # file:///abs/path -> /abs/path ; file://host/path is uncommon locally.
        path = Path(unquote(parts.path))
        if not path.is_absolute() and artifact_base is not None:
            return artifact_base / path
        return path

    if scheme == "":
        # Bare path reference (relative or absolute).
        path = Path(uri)
        if not path.is_absolute() and artifact_base is not None:
            return artifact_base / path
        return path

    # Any other scheme is treated as remote/opaque.
    return None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_HASH_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _declared_digest(file_payload: dict[str, Any]) -> str | None:
    digest = file_payload.get("digest")
    if isinstance(digest, str) and digest.strip():
        return digest.strip()
    if isinstance(digest, dict):
        hash_value = digest.get("hash") or digest.get("sha256")
        if hash_value:
            return str(hash_value)
    sha256 = file_payload.get("sha256")
    if isinstance(sha256, str) and sha256.strip():
        return sha256.strip()
    return None


def _declared_size(file_payload: dict[str, Any]) -> int | None:
    for key in ("length", "sizeBytes", "size_bytes"):
        value = file_payload.get(key)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _normalize_digest(digest: str) -> str:
    text = digest.strip().lower()
    if ":" in text:
        text = text.split(":", 1)[1]
    return text


def _downgraded_source_kind(source_kind: str) -> str:
    """Never promote an unverified reference to a collectable presence claim."""

    return "derived_v1" if source_kind == "collectable_v1" else source_kind


def _reference_key(
    label: str | None,
    name: str | None,
    uri: str | None,
    index: int,
) -> str:
    owner = label or "build"
    discriminator = name or uri or str(index)
    return f"{owner}:artifact:{discriminator}"


def _collect_files(sink: list[dict[str, Any]], value: Any) -> None:
    if isinstance(value, dict):
        # completed.outputGroup may nest fileSets; only direct File dicts here.
        if any(key in value for key in ("uri", "name", "digest")):
            sink.append(value)
        return
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict) and any(
                key in item for key in ("uri", "name", "digest")
            ):
                sink.append(item)


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None
