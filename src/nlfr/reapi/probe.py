"""REAPI CAS probe: independent verification of remote bytestream references.

This module is the #81 part B backend for the injectable ``cas_probe`` seam in
``nlfr.ingest.verification``. :func:`make_cas_probe` returns a callable matching
the seam's ``CasProbe`` signature exactly: ``(uri, declared_digest,
declared_size) -> ProbeResult | None``.

What the probe actually does, per remote reference:

1. Parse the ``bytestream://`` URI into ``(instance_name, hash, size)``. An URI
   this probe cannot parse yields ``None`` — the seam keeps the honest
   ``unverified_remote_reference`` downgrade.
2. ``ContentAddressableStorage/FindMissingBlobs`` — a cheap, authoritative
   presence check against the CAS the OPERATOR named (``--cas-endpoint``).
   CAS-confirmed absence is ``ProbeResult(present=False)`` — the actual
   bazelbuild/bazel#23250 failure mode, mapped to ``remote_missing``.
3. If present AND the BEP declared a recomputable SHA-256 AND the blob is
   within the read limit: ``ByteStream/Read`` the bytes, recompute SHA-256
   locally, and return it. The SEAM does the comparison — NLFR attests only
   what it recomputed itself, never the store's self-report.
4. Any transport error, timeout, or inconclusive state returns ``None``; the
   seam then records ``unverified_remote_reference`` with a probe-attempted
   note. The probe NEVER raises into ingest and NEVER fabricates a verdict.

Honest boundaries (also documented in docs/wiki/how-to/verify-remote-cas.md):

* This verifies that the CAS **the operator named** holds bytes matching the
  BEP-declared digest. It does not prove Bazel talked to that same store, and
  it does not verify ``compressed-blobs`` content (presence only).
* Blobs above the read limit are confirmed present but not hash-checked
  (``remote_present``), with the reason recorded — never a fake ``verified``.

Import posture: this MODULE imports only the standard library. gRPC and the
generated protobuf message classes are imported lazily inside
:func:`make_cas_probe` (via ``_GrpcTransport``); when the optional ``[reapi]``
extra is not installed that raises an ``ImportError`` naming the exact install
command. Unit tests inject a fake transport and exercise everything above the
transport line without grpcio installed.
"""

from __future__ import annotations

import hashlib
import logging
import string
from dataclasses import dataclass, field
from typing import Iterable, Protocol
from urllib.parse import unquote, urlsplit

from nlfr.ingest.verification import ProbeResult

logger = logging.getLogger("nlfr.reapi.probe")

# Default cap on how many bytes the probe will stream per blob to recompute its
# digest. Above the cap the blob is confirmed present but not hash-checked —
# recorded honestly as such, never as verified.
DEFAULT_READ_LIMIT_BYTES = 64 * 1024 * 1024

# Per-RPC deadline. A CAS that cannot answer in time yields an inconclusive
# probe (unverified_remote_reference), never a fabricated verdict.
DEFAULT_TIMEOUT_S = 10.0

# The honest install hint, surfaced verbatim when the optional extra is absent.
REAPI_INSTALL_HINT = 'pip install "nativelink-agent-flight-recorder[reapi]"'

_MISSING_EXTRA_MESSAGE = (
    "remote CAS verification requires the optional [reapi] extra "
    f"(grpcio + protobuf). Install it with: {REAPI_INSTALL_HINT}. "
    "Without it, nlfr ingest keeps the honest default: remote references are "
    "recorded as unverified_remote_reference, never fabricated."
)

# Fully-qualified gRPC method paths, invoked through the generic method API so
# a reviewer can check them directly against the REAPI / ByteStream specs
# instead of trusting generated service stubs.
FIND_MISSING_BLOBS_METHOD = (
    "/build.bazel.remote.execution.v2.ContentAddressableStorage/FindMissingBlobs"
)
BYTESTREAM_READ_METHOD = "/google.bytestream.ByteStream/Read"

_HEX_DIGITS = set(string.hexdigits)
_SHA256_HEX_LENGTH = 64
# REAPI reserved resource-name segments that mark a NON-download resource. A
# URI carrying one of these before ``blobs`` is not a plain blob download name;
# the probe refuses to guess and returns an unsupported-URI verdict (None).
_RESERVED_PREFIX_SEGMENTS = frozenset({"uploads", "operations", "actions"})


@dataclass(frozen=True)
class BytestreamResource:
    """A parsed ``bytestream://`` blob download resource.

    ``instance_name`` is the (possibly multi-segment, possibly empty) REAPI
    instance embedded in the URI path; ``compressed`` marks a
    ``compressed-blobs`` resource whose content the probe will not read
    (presence check only — NLFR does not decompress in v1). ``size_bytes`` is
    the blob's size per the resource name (for ``compressed-blobs`` this is the
    UNCOMPRESSED size, which is the CAS coordinate).
    """

    instance_name: str
    blob_hash: str
    size_bytes: int
    compressed: bool = False


def parse_bytestream_uri(uri: str) -> BytestreamResource | None:
    """Parse ``bytestream://host[:port]/[instance/]blobs/<hash>/<size>``.

    Returns ``None`` for anything this probe cannot parse with confidence —
    the caller then records the honest unverified downgrade rather than
    guessing. The URI's authority (host:port) is deliberately IGNORED for
    dialing: the operator's ``--cas-endpoint`` decides which CAS is asked, and
    that choice is recorded in the run's provenance.

    REAPI instance names may span multiple path segments; the first ``blobs``
    or ``compressed-blobs`` segment delimits them (instance names must not
    contain the reserved keywords). Upload/operation/action resource names are
    rejected — they are not blob download names.
    """

    if not uri:
        return None
    parts = urlsplit(uri)
    if parts.scheme != "bytestream":
        return None
    segments = [unquote(segment) for segment in parts.path.split("/") if segment]

    delimiter_index: int | None = None
    compressed = False
    for index, segment in enumerate(segments):
        if segment in ("blobs", "compressed-blobs"):
            delimiter_index = index
            compressed = segment == "compressed-blobs"
            break
    if delimiter_index is None:
        return None

    instance_segments = segments[:delimiter_index]
    if any(segment in _RESERVED_PREFIX_SEGMENTS for segment in instance_segments):
        return None

    trailing = segments[delimiter_index + 1 :]
    if compressed:
        # {instance}/compressed-blobs/{compressor}/{hash}/{size}
        if len(trailing) != 3:
            return None
        _compressor, blob_hash, raw_size = trailing
    else:
        # {instance}/blobs/{hash}/{size}
        if len(trailing) != 2:
            return None
        blob_hash, raw_size = trailing

    if not blob_hash or any(char not in _HEX_DIGITS for char in blob_hash):
        return None
    try:
        size_bytes = int(raw_size, 10)
    except ValueError:
        return None
    if size_bytes < 0:
        return None

    return BytestreamResource(
        instance_name="/".join(instance_segments),
        blob_hash=blob_hash.lower(),
        size_bytes=size_bytes,
        compressed=compressed,
    )


def parse_cas_endpoint(endpoint: str, tls: bool | None = None) -> tuple[str, bool]:
    """Resolve an operator-supplied endpoint into ``(grpc_target, use_tls)``.

    Accepted forms: ``grpc://host:port`` (plaintext), ``grpcs://host:port``
    (TLS), or a bare ``host:port`` (plaintext). An explicit ``tls`` argument
    overrides the scheme. Anything else raises ``ValueError`` with an honest
    description — the operator asked for verification, so a bad endpoint is a
    hard error, not a silent downgrade.
    """

    if not endpoint or not endpoint.strip():
        raise ValueError("empty CAS endpoint")
    endpoint = endpoint.strip()

    if "://" in endpoint:
        parts = urlsplit(endpoint)
        scheme = parts.scheme.lower()
        if scheme not in ("grpc", "grpcs"):
            raise ValueError(
                f"unsupported CAS endpoint scheme {parts.scheme!r} — use "
                "grpc://host:port, grpcs://host:port, or a bare host:port"
            )
        if not parts.netloc:
            raise ValueError(f"CAS endpoint {endpoint!r} has no host")
        if parts.path not in ("", "/") or parts.query or parts.fragment:
            raise ValueError(
                f"CAS endpoint {endpoint!r} must not carry a path, query, or fragment"
            )
        scheme_tls = scheme == "grpcs"
        return parts.netloc, scheme_tls if tls is None else tls

    if "/" in endpoint:
        raise ValueError(
            f"CAS endpoint {endpoint!r} must not carry a path — use "
            "grpc://host:port, grpcs://host:port, or a bare host:port"
        )
    return endpoint, bool(tls)


class CasTransport(Protocol):
    """The single thin seam between probe logic and gRPC.

    Everything above this line — URI parsing, verdict mapping, read-limit
    honesty, statistics — is pure stdlib and unit-tested with fakes. The only
    implementation that touches the network is :class:`_GrpcTransport`.
    """

    def find_missing(
        self, instance_name: str, blob_hash: str, size_bytes: int
    ) -> bool:
        """Return True when the CAS reports the blob MISSING (authoritative)."""
        ...

    def read_sha256(
        self, instance_name: str, blob_hash: str, size_bytes: int
    ) -> str:
        """Stream the blob and return the LOCALLY recomputed SHA-256 hex digest."""
        ...


def blob_resource_name(instance_name: str, blob_hash: str, size_bytes: int) -> str:
    """Build the ByteStream read resource name ``[instance/]blobs/<hash>/<size>``."""

    prefix = f"{instance_name}/" if instance_name else ""
    return f"{prefix}blobs/{blob_hash}/{size_bytes}"


@dataclass
class ProbeStats:
    """First-hand counters of what this probe session actually did.

    These are recorded into the run's provenance (the ``cas_probe_v1`` proof
    block) so an exported packet states what was probed and how each probe
    concluded — including the honest failure modes.
    """

    probed_references: int = 0
    unsupported_uri: int = 0
    missing: int = 0
    present_digest_recomputed: int = 0
    present_not_read: int = 0
    inconclusive: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "probed_references": self.probed_references,
            "unsupported_uri": self.unsupported_uri,
            "missing": self.missing,
            "present_digest_recomputed": self.present_digest_recomputed,
            "present_not_read": self.present_not_read,
            "inconclusive": self.inconclusive,
        }


class CasProbeSession:
    """A configured CAS probe. Instances match the seam's ``CasProbe`` signature.

    The session carries its own :class:`ProbeStats` plus the endpoint/instance
    configuration so callers (the ingest CLI) can record provenance and print
    an honest operator summary after parsing.
    """

    def __init__(
        self,
        endpoint: str,
        *,
        instance: str = "",
        timeout_s: float = DEFAULT_TIMEOUT_S,
        tls: bool | None = None,
        read_limit_bytes: int = DEFAULT_READ_LIMIT_BYTES,
        transport: CasTransport | None = None,
    ) -> None:
        if read_limit_bytes < 0:
            raise ValueError("read_limit_bytes must be >= 0")
        self.endpoint = endpoint
        self.instance = instance
        self.read_limit_bytes = read_limit_bytes
        self.timeout_s = timeout_s
        self.stats = ProbeStats()
        if transport is None:
            # Validates the endpoint and imports grpc + the generated protobuf
            # messages. Raises the honest ImportError when the extra is absent.
            transport = _GrpcTransport(endpoint, timeout_s=timeout_s, tls=tls)
        self._transport = transport

    def __call__(
        self,
        uri: str,
        declared_digest: str | None,
        declared_size: int | None,
    ) -> ProbeResult | None:
        """Probe one remote reference. Never raises; ``None`` means no verdict."""

        self.stats.probed_references += 1

        resource = parse_bytestream_uri(uri)
        if resource is None:
            self.stats.unsupported_uri += 1
            logger.info("CAS probe: unsupported remote URI shape, no verdict: %s", uri)
            return None

        instance_name = resource.instance_name or self.instance

        try:
            missing = self._transport.find_missing(
                instance_name, resource.blob_hash, resource.size_bytes
            )
        except Exception as exc:  # noqa: BLE001 — any transport failure is inconclusive
            self.stats.inconclusive += 1
            logger.warning(
                "CAS probe: FindMissingBlobs failed against %s (%s); reference "
                "stays unverified",
                self.endpoint,
                exc,
            )
            return None

        if missing:
            self.stats.missing += 1
            return ProbeResult(present=False)

        skip_reason = self._read_skip_reason(resource, declared_digest)
        if skip_reason is not None:
            self.stats.present_not_read += 1
            return ProbeResult(present=True, computed_digest=None, note=skip_reason)

        try:
            computed_digest = self._transport.read_sha256(
                instance_name, resource.blob_hash, resource.size_bytes
            )
        except Exception as exc:  # noqa: BLE001 — any transport failure is inconclusive
            # FindMissingBlobs said present but the read reached no verdict;
            # conflicting/incomplete evidence never rounds UP to a claim.
            self.stats.inconclusive += 1
            logger.warning(
                "CAS probe: ByteStream read failed against %s (%s); reference "
                "stays unverified",
                self.endpoint,
                exc,
            )
            return None

        self.stats.present_digest_recomputed += 1
        return ProbeResult(present=True, computed_digest=computed_digest)

    def _read_skip_reason(
        self, resource: BytestreamResource, declared_digest: str | None
    ) -> str | None:
        """Why the blob's bytes will NOT be read, or ``None`` to read them.

        Every skip keeps the reference at the honest ``remote_present`` tier
        (present per FindMissingBlobs, digest neither confirmed nor
        contradicted) with the reason recorded in the verification note.
        """

        if declared_digest is None:
            return (
                "BEP declared no digest to cross-check; presence confirmed via "
                "FindMissingBlobs, blob not read."
            )
        if resource.compressed:
            return (
                "bytestream URI names a compressed-blobs resource; NLFR does not "
                "decompress CAS content in v1. Presence confirmed via "
                "FindMissingBlobs, digest not cross-checked."
            )
        if not _is_recomputable_sha256(declared_digest):
            return (
                "BEP-declared digest is not a recomputable SHA-256; presence "
                "confirmed via FindMissingBlobs, blob not read."
            )
        if resource.size_bytes > self.read_limit_bytes:
            return (
                f"blob size {resource.size_bytes} bytes exceeds the probe read "
                f"limit of {self.read_limit_bytes} bytes; presence confirmed via "
                "FindMissingBlobs, digest not cross-checked. Raise "
                "--cas-read-limit to hash-verify this blob."
            )
        return None

    def describe(self) -> dict[str, object]:
        """Provenance payload: what was probed, with which limits, and outcomes."""

        return {
            "endpoint": self.endpoint,
            "instance": self.instance,
            "timeout_s": self.timeout_s,
            "read_limit_bytes": self.read_limit_bytes,
            "outcomes": self.stats.as_dict(),
        }


def make_cas_probe(
    endpoint: str,
    instance: str = "",
    timeout_s: float = DEFAULT_TIMEOUT_S,
    tls: bool | None = None,
    read_limit_bytes: int = DEFAULT_READ_LIMIT_BYTES,
    transport: CasTransport | None = None,
) -> CasProbeSession:
    """Build a CAS probe for the seam in ``nlfr.ingest.verification``.

    The returned session is a callable matching ``CasProbe`` exactly. With no
    injected ``transport`` this imports grpc + protobuf EAGERLY so a missing
    ``[reapi]`` extra fails here — at the moment the operator asked for
    verification — with an ImportError naming the install command, instead of
    silently downgrading every reference later.
    """

    return CasProbeSession(
        endpoint,
        instance=instance,
        timeout_s=timeout_s,
        tls=tls,
        read_limit_bytes=read_limit_bytes,
        transport=transport,
    )


def _is_recomputable_sha256(declared_digest: str) -> bool:
    """True when the declared digest can be cross-checked against a SHA-256.

    Mirrors the seam's rule (an optional ``algo:`` prefix plus 64 hex chars)
    WITHOUT importing its private helpers: reading bytes whose declared digest
    the seam will not compare as SHA-256 would be wasted I/O — the reference
    lands at ``remote_present`` either way.
    """

    digest = declared_digest.strip()
    if ":" in digest:
        prefix, _, digest = digest.partition(":")
        if prefix.strip().lower().replace("-", "").replace("_", "") != "sha256":
            return False
        digest = digest.strip()
    if len(digest) != _SHA256_HEX_LENGTH:
        return False
    return all(char in _HEX_DIGITS for char in digest)


class _GrpcTransport:
    """The only network-touching code path: two RPCs over one gRPC channel.

    Imports grpc and the generated protobuf message classes lazily, raising the
    honest ``[reapi]`` ImportError when absent. RPCs are invoked through the
    channel's generic method API with explicit, reviewer-checkable method
    paths; the messages come from the vendored proto subset (see
    third_party/reapi/README.md).
    """

    def __init__(self, endpoint: str, *, timeout_s: float, tls: bool | None) -> None:
        target, use_tls = parse_cas_endpoint(endpoint, tls)
        grpc, re_pb2, bs_pb2 = _import_reapi_extra()
        self._timeout_s = timeout_s
        self._re_pb2 = re_pb2
        self._bs_pb2 = bs_pb2
        if use_tls:
            channel = grpc.secure_channel(target, grpc.ssl_channel_credentials())
        else:
            channel = grpc.insecure_channel(target)
        self._channel = channel
        self._find_missing_blobs = channel.unary_unary(
            FIND_MISSING_BLOBS_METHOD,
            request_serializer=re_pb2.FindMissingBlobsRequest.SerializeToString,
            response_deserializer=re_pb2.FindMissingBlobsResponse.FromString,
        )
        self._read = channel.unary_stream(
            BYTESTREAM_READ_METHOD,
            request_serializer=bs_pb2.ReadRequest.SerializeToString,
            response_deserializer=bs_pb2.ReadResponse.FromString,
        )

    def find_missing(
        self, instance_name: str, blob_hash: str, size_bytes: int
    ) -> bool:
        request = self._re_pb2.FindMissingBlobsRequest(
            instance_name=instance_name,
            blob_digests=[
                self._re_pb2.Digest(hash=blob_hash, size_bytes=size_bytes)
            ],
        )
        response = self._find_missing_blobs(request, timeout=self._timeout_s)
        # The request named exactly one digest, so any returned entry can only
        # be that digest reported missing.
        return len(response.missing_blob_digests) > 0

    def read_sha256(
        self, instance_name: str, blob_hash: str, size_bytes: int
    ) -> str:
        request = self._bs_pb2.ReadRequest(
            resource_name=blob_resource_name(instance_name, blob_hash, size_bytes),
            read_offset=0,
            read_limit=0,
        )
        hasher = hashlib.sha256()
        responses: Iterable = self._read(request, timeout=self._timeout_s)
        for response in responses:
            hasher.update(response.data)
        # Only a COMPLETED stream reaches this line; a mid-stream error raises
        # out of the iterator and the caller records an inconclusive probe.
        return hasher.hexdigest()


def _import_reapi_extra():
    """Import grpc + the vendored generated messages, or raise the honest hint."""

    try:
        import grpc  # noqa: PLC0415 — lazy by design (optional extra)
        from nlfr.reapi._gen.build.bazel.remote.execution.v2 import (  # noqa: PLC0415
            remote_execution_pb2,
        )
        from nlfr.reapi._gen.google.bytestream import bytestream_pb2  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError(_MISSING_EXTRA_MESSAGE) from exc
    return grpc, remote_execution_pb2, bytestream_pb2
