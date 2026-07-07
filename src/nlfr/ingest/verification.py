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
  presence claims — with no probe they are marked ``unverified_remote_reference``
  citing the upstream bug.

Remote verification is an INJECTABLE seam (GitHub issue #81, part A). ``_verify``
and ``build_reference`` accept an optional ``cas_probe`` callable; with no probe
(the default, and the only path any shipped caller uses today) a remote reference
keeps the historical ``unverified_remote_reference`` downgrade unchanged. When a
probe IS supplied, its result is mapped to honest remote-verification labels that
mirror the local_* symmetry (``remote_verified`` / ``remote_present`` /
``remote_mismatch`` / ``remote_missing``). The actual REAPI/gRPC probe backend —
an optional dependency extra plus vendored protos — is a documented follow-up
(#81 part B); NLFR ships NO probe and NO new runtime dependency in part A.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable
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

# Remote-verification presence markers (issue #81 part A), mirroring the local_*
# symmetry. These are ONLY ever produced when an optional CAS probe is injected
# into verification; with no probe (the default and the only path any shipped
# caller uses today) a remote reference stays PRESENCE_UNVERIFIED_REMOTE — today's
# exact behavior. Only remote_verified keeps a collectable_v1 / high claim.
PRESENCE_REMOTE_VERIFIED = "remote_verified"
PRESENCE_REMOTE_PRESENT = "remote_present"
PRESENCE_REMOTE_MISMATCH = "remote_mismatch"
PRESENCE_REMOTE_MISSING = "remote_missing"

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
# ``OutputGroup``, not a File — see ``iter_bep_file_references``. ``symlinkTargetPath``
# and ``contents`` are the other two members of File's ``file`` oneof (proto field 8
# and 3): a File may populate one of them INSTEAD of ``uri``, and neither ever
# appears on an OutputGroup, so listing them here keeps the structural rejection of
# output groups intact while no longer silently dropping symlink/inline File entries.
_FILE_SIGNAL_KEYS = ("uri", "digest", "pathPrefix", "length", "symlinkTargetPath", "contents")


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


@dataclass(frozen=True)
class ProbeResult:
    """Outcome of an injected CAS probe for one remote reference (issue #81).

    ``present`` is whether the content-addressable store reports the blob exists.
    ``computed_digest`` is the SHA-256 the probe recomputed from the CAS bytes (hex,
    no algorithm prefix) or ``None`` when the probe confirmed presence WITHOUT
    reading/hashing the bytes (e.g. a ``FindMissingBlobs`` existence check). A probe
    that cannot reach a verdict returns ``None`` (not a ``ProbeResult``), and NLFR
    then falls back to ``unverified_remote_reference`` rather than fabricating one.

    ``note`` (#81 part B, signature-compatible: defaults to ``None``) lets a probe
    record WHY it confirmed presence without hashing the bytes (read limit
    exceeded, no declared digest, compressed resource); the verifier appends it to
    the reference's ``verification_note`` so the evidence states the honest reason.
    """

    present: bool
    computed_digest: str | None = None
    note: str | None = None


# An injectable CAS probe: given the remote URI and the BEP-declared digest/size,
# it returns a ``ProbeResult``, or ``None`` when it cannot reach a verdict
# (unreachable endpoint, transient error, unsupported URI). An ordinary "blob not
# found" is ``ProbeResult(present=False)``, NOT an exception; a raised exception is
# caught by the verifier and treated exactly like ``None`` — honest fallback, never
# a fabricated claim. NLFR ships NO probe in part A: every current caller defaults
# ``cas_probe`` to ``None``. The gRPC/REAPI backend is #81 part B.
CasProbe = Callable[[str, "str | None", "int | None"], "ProbeResult | None"]


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
    cas_probe: CasProbe | None = None,
) -> ArtifactReferenceEvidence | None:
    """Verify a single BEP file payload and return an evidence record.

    Returns ``None`` when the payload carries neither a URI nor a name and thus
    cannot be turned into a stable reference. ``digest_function`` is what the BEP
    revealed about the build's configured digest function; NLFR only recomputes
    SHA-256, so a declared digest it cannot prove is SHA-256 is recorded as
    present-but-unchecked rather than mismatch-downgraded.

    ``cas_probe`` is an OPTIONAL injectable CAS probe (issue #81 part A). With no
    probe (the default) a remote reference keeps the historical
    ``unverified_remote_reference`` downgrade; when supplied, its verdict maps to
    the honest remote-verification labels. Local, symlink, and inline references
    never touch the probe — their bytes are already reachable.
    """

    name = _string_or_none(file_payload.get("name"))
    uri = _string_or_none(file_payload.get("uri"))
    symlink_target = _string_or_none(file_payload.get("symlinkTargetPath"))
    inline_contents = _string_or_none(file_payload.get("contents"))
    declared_digest = _declared_digest(file_payload)
    declared_size = _declared_size(file_payload)
    if uri is None and name is None and symlink_target is None and inline_contents is None:
        return None

    # File's ``file`` oneof is exactly one of uri / contents / symlinkTargetPath. A
    # uri (or bare name) goes through the local-path/remote verifier; a symlink or
    # inline-bytes entry has no local file to open at ``uri`` and is verified on its
    # own terms. We never fabricate a digest a symlink cannot carry, and we hash
    # inline bytes only when they are actually present.
    if uri is None and symlink_target is not None and inline_contents is None:
        verification = _verify_symlink(symlink_target, artifact_base, source_kind)
    elif uri is None and inline_contents is not None and symlink_target is None:
        verification = _verify_inline_contents(
            inline_contents, declared_digest, source_kind, digest_function
        )
    else:
        verification = _verify(
            uri,
            declared_digest,
            declared_size,
            artifact_base,
            source_kind,
            digest_function,
            cas_probe,
        )
    (
        presence,
        digest_verified,
        computed_digest,
        local_path,
        note,
        ref_source_kind,
        confidence,
    ) = verification

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
    declared_size: int | None,
    artifact_base: Path | None,
    source_kind: str,
    digest_function: DigestFunctionInfo,
    cas_probe: CasProbe | None = None,
) -> tuple[str, bool | None, str | None, str | None, str, str, str]:
    """Return the verification tuple for one reference.

    Tuple: (presence, digest_verified, computed_digest, local_path, note,
    source_kind, confidence).
    """

    local_path = _local_path(uri, artifact_base)

    if local_path is None:
        # No resolvable local path: either a remote CAS URI or a bare reference we
        # cannot open. Presence is unverifiable locally; hand it to the remote
        # verifier, which either folds in an injected probe's verdict or (the
        # default) returns the historical unverified_remote_reference downgrade.
        return _verify_remote(
            uri, declared_digest, declared_size, source_kind, digest_function, cas_probe
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


def _verify_remote(
    uri: str | None,
    declared_digest: str | None,
    declared_size: int | None,
    source_kind: str,
    digest_function: DigestFunctionInfo,
    cas_probe: CasProbe | None,
) -> tuple[str, bool | None, str | None, str | None, str, str, str]:
    """Verify (or honestly decline to verify) a remote/opaque reference.

    With NO probe supplied — the default, and the only path any shipped caller uses
    today — this returns the exact historical ``unverified_remote_reference``
    downgrade: NLFR does not claim local presence and does not probe remote CAS.
    When a probe IS injected and the URI is probeable, its verdict maps to the
    honest remote labels:

    * present + recomputed SHA-256 matches declared  -> ``remote_verified`` (high,
      the only remote tier that keeps a collectable_v1 claim);
    * present + recomputed SHA-256 contradicts declared -> ``remote_mismatch`` (low,
      downgraded);
    * present + no recomputable-SHA-256 cross-check -> ``remote_present`` (medium);
    * CAS confirms the blob ABSENT -> ``remote_missing`` (low, downgraded — the
      actual bazelbuild/bazel#23250 failure mode);
    * probe raised, returned ``None``, or returned a malformed / wrong-typed result
      -> ``unverified_remote_reference`` (never a fabricated verdict, never a crash).
    """

    if cas_probe is None or uri is None:
        return _unverified_remote_reference(source_kind)

    try:
        probe = cas_probe(uri, declared_digest, declared_size)
    except Exception:
        # A probe signals "blob not found" as ProbeResult(present=False); a raised
        # exception is an INCONCLUSIVE probe, never a fabricated absence/presence.
        return _unverified_remote_reference(source_kind, probe_attempted=True)

    if probe is None:
        return _unverified_remote_reference(source_kind, probe_attempted=True)

    # A probe is INJECTED code: validate the shape of what it handed back BEFORE
    # consuming it. A malformed result (not a ProbeResult, a non-bool ``present``, a
    # non-str ``computed_digest``) — or an object whose attribute access itself
    # raises — is INCONCLUSIVE, treated exactly like a None return. We never coerce
    # (``str(123456)`` would fabricate a digest to compare) and never crash ingest: a
    # bad probe can only ever weaken a claim to unverified_remote_reference.
    try:
        malformation = _probe_malformation(probe)
    except Exception:
        malformation = "attribute access raised"
    if malformation is not None:
        return _unverified_remote_reference(source_kind, malformation=malformation)

    if not probe.present:
        # The actual bazel#23250 failure mode: the BEP referenced the blob but the
        # CAS confirms it is ABSENT. Strongest downgrade — presence is contradicted.
        note = (
            "CAS probe reports the BEP-referenced blob is ABSENT from the remote "
            f"store; the cache upload likely FAILED ({BAZEL_UPLOAD_BUG_REF}). "
            "Presence is contradicted and the reference is downgraded."
        )
        return (
            PRESENCE_REMOTE_MISSING,
            None,
            None,
            None,
            note,
            _downgraded_source_kind(source_kind),
            "low",
        )

    computed = probe.computed_digest
    if computed is not None and declared_digest is not None:
        declared_prefix, declared_hex = _split_digest_prefix(declared_digest)
        non_sha256_function = (
            digest_function.options_available
            and digest_function.name is not None
            and digest_function.name != _SHA256_NAME
        )
        recomputable_sha256 = (
            not non_sha256_function
            and declared_prefix in (None, _SHA256_NAME)
            and _is_sha256_hex(declared_hex)
        )
        if recomputable_sha256:
            if _normalize_digest(computed) == declared_hex:
                note = (
                    "CAS probe read the blob; its recomputed SHA-256 matches the "
                    "BEP-declared digest. Remote presence is independently verified."
                )
                return (
                    PRESENCE_REMOTE_VERIFIED,
                    True,
                    computed,
                    None,
                    note,
                    source_kind,
                    "high",
                )
            note = (
                "CAS probe read the blob, but its recomputed SHA-256 does NOT match "
                "the BEP-declared digest; the remote bytes contradict the build "
                "tool's self-report. Presence downgraded."
            )
            return (
                PRESENCE_REMOTE_MISMATCH,
                False,
                computed,
                None,
                note,
                _downgraded_source_kind(source_kind),
                "low",
            )

    # Present, but no recomputable-SHA-256 cross-check was possible: the probe did
    # not hash the bytes, or the BEP declared no digest / a non-SHA-256 digest.
    # When the probe recorded WHY it did not hash the bytes (#81 part B), that
    # honest reason is appended verbatim to the evidence note.
    note = (
        "CAS probe reports the BEP-referenced blob is present, but its digest was "
        "not cross-checked as a recomputable SHA-256; presence is recorded, the "
        "digest is neither confirmed nor contradicted."
    )
    # ``note`` was already validated str-or-None by _probe_malformation, but a
    # hostile ProbeResult could re-read to a different value or a str subclass whose
    # ``__bool__`` raises. Read and test it once under a guard so appending the
    # probe's reason can only ever ADD context, never crash ingest — preserving the
    # invariant that a bad probe weakens a claim, never breaks the parse.
    try:
        probe_note = probe.note
        if isinstance(probe_note, str) and probe_note:
            note = f"{note} Probe: {probe_note}"
    except Exception:
        pass  # keep the base remote_present note; a hostile note never crashes ingest
    return (
        PRESENCE_REMOTE_PRESENT,
        None,
        computed,
        None,
        note,
        source_kind,
        "medium",
    )


def _probe_malformation(probe: Any) -> str | None:
    """Describe why ``probe`` is not a well-formed ``ProbeResult``, or ``None`` if it is.

    A probe is injected, untrusted code. Its return must be a ``ProbeResult`` whose
    ``present`` is a real ``bool``, whose ``computed_digest`` is ``str`` or ``None``,
    and whose ``note`` is ``str`` or ``None``. Anything else is malformed and must be
    treated as inconclusive rather than consumed: a non-str ``computed_digest`` would
    crash the SHA-256 compare, a bool-like ``int`` ``present`` would fabricate a
    presence verdict, and a non-str ``note`` (e.g. an object whose ``__bool__``
    raises) would crash the ``remote_present`` note-append. ``present`` is checked
    with ``isinstance(x, bool)`` precisely so ``1``/``0`` (``int``) and ``"yes"``
    (``str``) are rejected, not silently accepted as truthy. Attribute access may
    itself raise for a hostile ``ProbeResult`` subclass, so callers wrap this in
    ``try/except``. Only type is checked here — never truthiness — so a note whose
    ``__bool__`` raises is rejected by type without ever invoking ``__bool__``.
    """

    if not isinstance(probe, ProbeResult):
        return f"not a ProbeResult ({type(probe).__name__})"
    if not isinstance(probe.present, bool):
        return f"present: {type(probe.present).__name__}"
    computed = probe.computed_digest
    if computed is not None and not isinstance(computed, str):
        return f"computed_digest: {type(computed).__name__}"
    note = probe.note
    if note is not None and not isinstance(note, str):
        return f"note: {type(note).__name__}"
    return None


def _unverified_remote_reference(
    source_kind: str,
    *,
    probe_attempted: bool = False,
    malformation: str | None = None,
) -> tuple[str, bool | None, str | None, str | None, str, str, str]:
    """The historical remote downgrade tuple (no-probe default / inconclusive probe).

    The no-probe note is byte-for-byte the text NLFR has always emitted, so every
    existing caller and test sees the exact current behavior. ``probe_attempted``
    swaps in a note that records a probe was tried but reached no verdict.
    ``malformation`` names a wrong-typed / malformed probe result that was treated as
    inconclusive rather than consumed.
    """

    if malformation is not None:
        note = (
            "BEP references this artifact at a remote/opaque URI and the injected CAS "
            f"probe returned a malformed result ({malformation}); treated as "
            "inconclusive rather than consumed. The cache upload may have failed and "
            f"the bytes are not proven to exist ({BAZEL_UPLOAD_BUG_REF}). NLFR does "
            "not fabricate a presence claim."
        )
    elif probe_attempted:
        note = (
            "BEP references this artifact at a remote/opaque URI and the injected CAS "
            "probe returned no verdict (unreachable, errored, or unsupported); the "
            "cache upload may have failed and the bytes are not proven to exist "
            f"({BAZEL_UPLOAD_BUG_REF}). NLFR does not fabricate a presence claim."
        )
    else:
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


def _verify_symlink(
    symlink_target: str,
    artifact_base: Path | None,
    source_kind: str,
) -> tuple[str | None, bool | None, str | None, str | None, str, str, str]:
    """Verify a BEP ``File`` whose populated oneof is ``symlinkTargetPath``.

    A symlink entry declares no digest — there is nothing to recompute and nothing
    to cross-check — so ``digest_verified`` is always ``None`` and NLFR never
    fabricates a verified/collectable claim from it. Presence is taken honestly
    from an existence probe of the resolved target: ``local_present`` when the
    target is on disk, ``missing`` when a resolvable target is absent, and ``NULL``
    (presence not claimed) when the target path cannot be resolved locally.
    """

    target_path = _resolve_local_reference(symlink_target, artifact_base)
    if target_path is None:
        note = (
            "BEP declares a symlink output (symlinkTargetPath) whose target could not "
            "be resolved to a local path; a symlink carries no digest, so nothing was "
            "recomputed and presence is not claimed."
        )
        return (None, None, None, symlink_target, note, _downgraded_source_kind(source_kind), "low")

    if target_path.exists():
        note = (
            "BEP declares a symlink output; its target exists locally but a symlink "
            "carries no BEP digest to cross-check, so presence is recorded without a "
            "verified digest (digest_verified is null)."
        )
        return (PRESENCE_LOCAL_PRESENT, None, None, str(target_path), note, source_kind, "medium")

    note = (
        "BEP declares a symlink output whose target is not present on disk; presence "
        "downgraded and no digest could be recomputed (symlinks declare no digest)."
    )
    return (PRESENCE_MISSING, None, None, str(target_path), note, _downgraded_source_kind(source_kind), "low")


def _verify_inline_contents(
    contents: str,
    declared_digest: str | None,
    source_kind: str,
    digest_function: DigestFunctionInfo,
) -> tuple[str, bool | None, str | None, str | None, str, str, str]:
    """Verify a BEP ``File`` whose populated oneof is inline ``contents``.

    Inline bytes travel in the BEP itself (base64 per proto3 JSON), so NLFR can hash
    them directly — no filesystem access. When a recomputable SHA-256 digest is
    declared, the decoded bytes are hashed and cross-checked exactly like a local
    file; a non-SHA-256 or ill-shaped declared digest yields ``local_present`` with
    ``digest_verified=null`` rather than a fabricated mismatch.
    """

    raw = _decode_inline_contents(contents)
    if raw is None:
        note = (
            "BEP declares an inline-contents File whose bytes could not be base64-"
            "decoded; nothing was recomputed and presence is not claimed."
        )
        return (PRESENCE_MISSING, None, None, None, note, _downgraded_source_kind(source_kind), "low")

    computed_digest = hashlib.sha256(raw).hexdigest()

    if declared_digest is None:
        note = (
            "Hashed inline BEP contents (SHA-256); BEP declared no digest, so the "
            "value is self-attested rather than cross-checked."
        )
        return (PRESENCE_LOCAL_VERIFIED, None, computed_digest, None, note, source_kind, "medium")

    declared_prefix, declared_hex = _split_digest_prefix(declared_digest)

    non_sha256_function = (
        digest_function.options_available
        and digest_function.name is not None
        and digest_function.name != _SHA256_NAME
    )
    if non_sha256_function or declared_prefix not in (None, _SHA256_NAME) or not _is_sha256_hex(declared_hex):
        note = (
            "Inline BEP contents are present, but the BEP-declared digest is not a "
            "recomputable SHA-256 (v1 only recomputes SHA-256); presence is recorded, "
            "the digest is neither confirmed nor contradicted."
        )
        return (PRESENCE_LOCAL_PRESENT, None, computed_digest, None, note, source_kind, "medium")

    if _normalize_digest(computed_digest) == declared_hex:
        note = "Hashed inline BEP contents (SHA-256) match the BEP-declared digest."
        return (PRESENCE_LOCAL_VERIFIED, True, computed_digest, None, note, source_kind, "high")

    note = (
        "Hashed inline BEP contents (SHA-256) do NOT match the BEP-declared digest; "
        "the build tool's self-report is contradicted by the inlined bytes. Presence "
        "downgraded."
    )
    return (PRESENCE_LOCAL_MISMATCH, False, computed_digest, None, note, _downgraded_source_kind(source_kind), "low")


def _resolve_local_reference(reference: str, artifact_base: Path | None) -> Path | None:
    """Resolve a bare local path (e.g. a symlink target) to a filesystem path.

    Absolute paths are returned as-is; a relative path is joined onto
    ``artifact_base`` when one is available, and is otherwise unresolvable (``None``).
    """

    path = Path(reference)
    if path.is_absolute():
        return path
    if artifact_base is not None:
        return artifact_base / path
    return None


def _decode_inline_contents(contents: str) -> bytes | None:
    """Base64-decode BEP inline ``contents`` (proto3 JSON encodes bytes as base64).

    Returns ``None`` when the value is not valid base64 so the caller records the
    entry un-fabricated rather than hashing a guess.
    """

    try:
        return base64.b64decode(contents, validate=True)
    except (binascii.Error, ValueError):
        return None


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
    return any(
        key in value
        for key in ("uri", "name", "digest", "pathPrefix", "symlinkTargetPath", "contents")
    )


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
