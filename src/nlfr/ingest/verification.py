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
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
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
PRESENCE_LOCAL_PRESENT = "local_present"
PRESENCE_MISSING = "missing"
PRESENCE_UNVERIFIED_REMOTE = "unverified_remote_reference"

# NLFR only recomputes SHA-256 in v1. Bazel's File.digest is the hex of the
# CONFIGURED --digest_function; a build that runs a non-default function (common
# in remote-execution shops) declares digests NLFR cannot recompute. Comparing a
# SHA-256 against, say, a BLAKE3 digest would fabricate an unconditional mismatch,
# so any digest we cannot prove is SHA-256 is recorded as present-but-unchecked
# rather than downgraded.
_SHA256_NAME = "sha256"
_SHA256_HEX_RE = re.compile(r"[0-9a-f]{64}")
_DIGEST_FUNCTION_RE = re.compile(r"--digest[_-]?function[=\s]+([A-Za-z0-9_.-]+)")

# A real Bazel BEP ``File`` always carries at least one of these fields alongside
# its ``name``. A dict that has only ``name`` (or a ``fileSets`` list) is an
# ``OutputGroup``, not a File — see ``iter_bep_file_references``.
_FILE_SIGNAL_KEYS = ("uri", "digest", "pathPrefix", "length")


@dataclass(frozen=True)
class DigestFunctionInfo:
    """What the BEP reveals about the build's configured digest function.

    ``name`` is the normalized function name (lowercase, dashes/underscores
    stripped: ``sha-256`` -> ``sha256``) or ``None`` when no ``--digest_function``
    override was seen. ``options_available`` is True when the BEP exposed a
    scannable command line at all: if it did and named no override, Bazel's
    default (SHA-256) is in effect and a mismatch is a real integrity signal; if
    it did not, the digest function is genuinely unconfirmed.
    """

    name: str | None
    options_available: bool
    raw: str | None = None


DIGEST_FUNCTION_UNKNOWN = DigestFunctionInfo(name=None, options_available=False)


def detect_digest_function(events: Iterable[dict[str, Any]]) -> DigestFunctionInfo:
    """Scan BEP events for the build's configured ``--digest_function``.

    Reads the ``started`` event's ``optionsDescription`` and any ``optionsParsed``
    command-line lists — the BEP fields that carry option strings — without
    parsing the full structured command line.
    """

    options_available = False
    for event in events:
        if not isinstance(event, dict):
            continue
        strings = _option_strings(event)
        if strings:
            options_available = True
        for text in strings:
            match = _DIGEST_FUNCTION_RE.search(text)
            if match:
                raw = match.group(1)
                return DigestFunctionInfo(
                    name=_normalize_function_name(raw),
                    options_available=True,
                    raw=raw,
                )
    return DigestFunctionInfo(name=None, options_available=options_available)


def _option_strings(event: dict[str, Any]) -> list[str]:
    strings: list[str] = []
    started = event.get("started")
    if isinstance(started, dict):
        description = started.get("optionsDescription")
        if isinstance(description, str):
            strings.append(description)
    options_parsed = event.get("optionsParsed")
    if isinstance(options_parsed, dict):
        for key in ("cmdLine", "explicitCmdLine", "startupOptions", "explicitStartupOptions"):
            value = options_parsed.get(key)
            if isinstance(value, list):
                strings.extend(item for item in value if isinstance(item, str))
    return strings


def _normalize_function_name(raw: str) -> str:
    return raw.strip().lower().replace("-", "").replace("_", "")


def iter_bep_file_references(event: dict[str, Any]) -> list[dict[str, Any]]:
    """Yield raw BEP ``File`` payloads carried by a single build event.

    Covers the event shapes that name output files: ``namedSetOfFiles``,
    ``testResult.testActionOutput``, and ``completed.importantOutput``.

    ``completed.outputGroup`` is deliberately NOT collected as files. Per Bazel's
    ``build_event_stream.proto`` a ``TargetComplete.output_group`` is a repeated
    ``OutputGroup`` of shape ``{name, fileSets: [NamedSetOfFilesId], incomplete,
    inlineFiles: [File]}``. The ``name`` is a GROUP name ("default", "_validation",
    ...), never a filename, and the actual files are reached indirectly through the
    ``fileSets`` ids, which resolve to ``namedSetOfFiles`` events that are emitted
    separately and already collected above. Treating each ``OutputGroup`` as a File
    (it has a ``name`` key) fabricated one artifact row per output group on every
    real build — a verification-count corruption the shipped fixture missed because
    it omitted ``outputGroup`` entirely. We resolve nothing here (v1 does not build
    a fileSet map for cross-attribution) and only harvest ``inlineFiles``, which are
    the sole real ``File`` objects an ``OutputGroup`` carries directly.
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
        for group in _as_list(completed.get("outputGroup")):
            if isinstance(group, dict):
                _collect_files(files, group.get("inlineFiles"))

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
    digest_function: DigestFunctionInfo = DIGEST_FUNCTION_UNKNOWN,
) -> ArtifactReferenceEvidence | None:
    """Verify a single BEP file payload and return an evidence record.

    Returns ``None`` when the payload carries neither a URI nor a name and thus
    cannot be turned into a stable reference. ``digest_function`` is what the BEP
    revealed about the build's configured digest function; NLFR only recomputes
    SHA-256, so a declared digest it cannot prove is SHA-256 is recorded as
    present-but-unchecked rather than mismatch-downgraded.
    """

    name = _string_or_none(file_payload.get("name"))
    uri = _string_or_none(file_payload.get("uri"))
    declared_digest = _declared_digest(file_payload)
    declared_size = _declared_size(file_payload)
    if uri is None and name is None:
        return None

    presence, digest_verified, computed_digest, local_path, note, ref_source_kind, confidence = (
        _verify(uri, declared_digest, artifact_base, source_kind, digest_function)
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
    digest_function: DigestFunctionInfo,
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

    if declared_digest is None:
        computed_digest = _sha256_file(local_path)
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

    declared_prefix, declared_hex = _split_digest_prefix(declared_digest)

    # (a) A non-SHA-256 digest function is explicitly configured for the build.
    # Recomputing SHA-256 and comparing it against, e.g., a BLAKE3 digest would be
    # an unconditional false mismatch, so the honest state is present-but-unchecked.
    if (
        digest_function.options_available
        and digest_function.name is not None
        and digest_function.name != _SHA256_NAME
    ):
        note = (
            "File is present locally, but the build configured "
            f"--digest_function={digest_function.raw}; NLFR only recomputes SHA-256 "
            "in v1, so the BEP-declared digest was not cross-checked. Presence is "
            "recorded; the digest is neither confirmed nor contradicted."
        )
        return (
            PRESENCE_LOCAL_PRESENT,
            None,
            None,
            str(local_path),
            note,
            source_kind,
            "medium",
        )

    # (b) The declared digest is not a 64-char hex SHA-256 (defensive: catches a
    # SHA-1/40, SHA-512/128, or base64-shaped digest, and any ``blake3:`` / ``sha1:``
    # algorithm prefix) even when the command line did not name a function.
    if declared_prefix not in (None, _SHA256_NAME) or not _is_sha256_hex(declared_hex):
        note = (
            "File is present locally, but the BEP-declared digest is not a "
            "recomputable SHA-256 (v1 only recomputes SHA-256): "
            f"{_digest_shape_detail(declared_prefix, declared_hex)}. Presence is "
            "recorded; the digest is neither confirmed nor contradicted."
        )
        return (
            PRESENCE_LOCAL_PRESENT,
            None,
            None,
            str(local_path),
            note,
            source_kind,
            "medium",
        )

    # (c) A 64-char hex digest with no non-SHA-256 signal: recompute and compare.
    # Theoretical caveat: SHA3-256 also produces 64 hex chars, so a hostile build
    # could in principle declare a SHA3-256 digest here; treated as SHA-256 in v1.
    computed_digest = _sha256_file(local_path)
    if _normalize_digest(computed_digest) == declared_hex:
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

    if digest_function.options_available:
        # The command line was visible and named SHA-256 or no override, so Bazel's
        # default (SHA-256) was in effect: this mismatch is a real integrity signal.
        note = (
            "Recomputed local SHA-256 does NOT match the BEP-declared digest; the "
            "build tool's self-report is contradicted by the bytes on disk. Presence "
            "downgraded."
        )
    else:
        # No command line in the BEP, so the digest function is unconfirmed. The
        # downgrade stands because a mismatch on Bazel's default function is
        # overwhelmingly a real integrity failure, but the uncertainty is explicit.
        note = (
            "Recomputed local SHA-256 does NOT match the BEP-declared digest; the "
            "build tool's self-report is contradicted by the bytes on disk. Presence "
            "downgraded. NOTE: the BEP did not expose the build's --digest_function, "
            "so an algorithm difference cannot be fully excluded; treated as an "
            "integrity signal because SHA-256 is Bazel's default digest function."
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
    """Append real BEP ``File`` dicts from ``value`` (a File, or a list of them).

    Structurally rejects ``OutputGroup``-shaped dicts so the caller cannot smuggle
    a group name in as a filename: an ``OutputGroup`` carries a ``fileSets`` list,
    or only a ``name`` with none of a File's identifying fields. This is
    defense-in-depth on top of ``iter_bep_file_references`` never passing an output
    group here.
    """

    for item in _as_list(value):
        if _is_file_payload(item):
            sink.append(item)


def _is_file_payload(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    if _looks_like_output_group(value):
        return False
    return any(key in value for key in ("uri", "name", "digest", "pathPrefix"))


def _looks_like_output_group(value: dict[str, Any]) -> bool:
    if "fileSets" in value:
        return True
    if "name" in value and not any(key in value for key in _FILE_SIGNAL_KEYS):
        return True
    return False


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _split_digest_prefix(declared_digest: str) -> tuple[str | None, str]:
    """Split ``sha256:abcd...`` into (normalized-prefix, lowercase-hex-or-body)."""

    text = declared_digest.strip()
    if ":" in text:
        prefix, rest = text.split(":", 1)
        return _normalize_function_name(prefix), rest.strip().lower()
    return None, text.lower()


def _is_sha256_hex(value: str) -> bool:
    return bool(_SHA256_HEX_RE.fullmatch(value))


def _digest_shape_detail(prefix: str | None, body: str) -> str:
    if prefix not in (None, _SHA256_NAME):
        return f"declared digest function prefix '{prefix}' is not sha256"
    return f"declared digest is not 64 hex chars (length {len(body)})"


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None
