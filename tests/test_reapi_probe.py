"""Unit tests for the REAPI CAS probe (issue #81 part B) — stdlib only.

Everything here runs WITHOUT grpcio/protobuf installed: the probe module is
importable with the standard library alone, and the gRPC calls sit behind one
thin injectable transport (``CasTransport``). These tests cover the entire
verdict pipeline above that line — URI parsing, endpoint parsing, read-limit
honesty, verdict mapping through the ``nlfr.ingest.verification`` seam, and
the session statistics recorded into provenance. The real-transport paths are
exercised by ``tests/test_reapi_probe_integration.py`` against an in-process
gRPC server when grpcio is available.
"""

from __future__ import annotations

import hashlib

import pytest

from nlfr.ingest.verification import ProbeResult, build_reference
from nlfr.reapi.probe import (
    DEFAULT_READ_LIMIT_BYTES,
    BytestreamResource,
    blob_resource_name,
    make_cas_probe,
    parse_bytestream_uri,
    parse_cas_endpoint,
)

_HASH = hashlib.sha256(b"remote blob bytes\n").hexdigest()


# ---------------------------------------------------------------------------
# bytestream:// URI parsing
# ---------------------------------------------------------------------------


def test_parse_uri_without_instance() -> None:
    """The historical fixture form: no instance segment before ``blobs``."""

    resource = parse_bytestream_uri(f"bytestream://remote.buildbuddy.io/blobs/{_HASH}/1024")
    assert resource == BytestreamResource(
        instance_name="", blob_hash=_HASH, size_bytes=1024, compressed=False
    )


def test_parse_uri_with_instance() -> None:
    """The NativeLink demo config serves instance ``main``."""

    resource = parse_bytestream_uri(f"bytestream://127.0.0.1:50051/main/blobs/{_HASH}/11")
    assert resource is not None
    assert resource.instance_name == "main"
    assert resource.size_bytes == 11


def test_parse_uri_with_multi_segment_instance() -> None:
    """REAPI instance names may span multiple path segments."""

    resource = parse_bytestream_uri(f"bytestream://cas.example:8980/projects/x/blobs/{_HASH}/5")
    assert resource is not None
    assert resource.instance_name == "projects/x"


def test_parse_uri_compressed_blobs_is_presence_only() -> None:
    """compressed-blobs resources parse (hash/size are the CAS coordinate)."""

    resource = parse_bytestream_uri(
        f"bytestream://cas.example/main/compressed-blobs/zstd/{_HASH}/2048"
    )
    assert resource is not None
    assert resource.compressed is True
    assert resource.blob_hash == _HASH
    assert resource.size_bytes == 2048


def test_parse_uri_normalizes_hash_case() -> None:
    resource = parse_bytestream_uri(f"bytestream://h/blobs/{_HASH.upper()}/1")
    assert resource is not None
    assert resource.blob_hash == _HASH


@pytest.mark.parametrize(
    "uri",
    [
        "",
        f"https://cas.example/blobs/{_HASH}/1",  # wrong scheme
        f"bytestream://cas.example/{_HASH}/1",  # no blobs segment
        f"bytestream://cas.example/blobs/{_HASH}",  # missing size
        f"bytestream://cas.example/blobs/{_HASH}/notanint",  # non-int size
        f"bytestream://cas.example/blobs/{_HASH}/-1",  # negative size
        f"bytestream://cas.example/blobs/{_HASH}/1/extra",  # trailing junk
        "bytestream://cas.example/blobs//1",  # empty hash
        "bytestream://cas.example/blobs/nothex!/1",  # non-hex hash
        f"bytestream://cas.example/uploads/uuid-1/blobs/{_HASH}/1",  # upload resource
        f"bytestream://cas.example/main/compressed-blobs/{_HASH}/1",  # no compressor
    ],
)
def test_parse_uri_rejects_unsupported_shapes(uri: str) -> None:
    """Anything the probe cannot parse with confidence yields None (no guessing)."""

    assert parse_bytestream_uri(uri) is None


def test_blob_resource_name_with_and_without_instance() -> None:
    assert blob_resource_name("", _HASH, 9) == f"blobs/{_HASH}/9"
    assert blob_resource_name("main", _HASH, 9) == f"main/blobs/{_HASH}/9"


# ---------------------------------------------------------------------------
# endpoint parsing
# ---------------------------------------------------------------------------


def test_endpoint_grpc_scheme_is_plaintext() -> None:
    assert parse_cas_endpoint("grpc://127.0.0.1:50051") == ("127.0.0.1:50051", False)


def test_endpoint_grpcs_scheme_is_tls() -> None:
    assert parse_cas_endpoint("grpcs://cas.example:443") == ("cas.example:443", True)


def test_endpoint_bare_host_port_defaults_plaintext() -> None:
    assert parse_cas_endpoint("127.0.0.1:50051") == ("127.0.0.1:50051", False)


def test_endpoint_explicit_tls_overrides_scheme() -> None:
    assert parse_cas_endpoint("grpc://cas.example:443", tls=True) == ("cas.example:443", True)


@pytest.mark.parametrize(
    "endpoint",
    ["", "   ", "http://cas.example:443", "grpc://", "grpc://host:1/path", "host:1/path"],
)
def test_endpoint_rejects_unsupported_forms(endpoint: str) -> None:
    with pytest.raises(ValueError):
        parse_cas_endpoint(endpoint)


# ---------------------------------------------------------------------------
# probe verdicts over an injected fake transport (no grpc anywhere)
# ---------------------------------------------------------------------------


class FakeTransport:
    """Scriptable CasTransport double that records every call."""

    def __init__(
        self,
        *,
        missing: bool = False,
        digest: str | None = None,
        find_error: Exception | None = None,
        read_error: Exception | None = None,
    ) -> None:
        self.missing = missing
        self.digest = digest
        self.find_error = find_error
        self.read_error = read_error
        self.find_calls: list[tuple[str, str, int]] = []
        self.read_calls: list[tuple[str, str, int]] = []

    def find_missing(self, instance_name: str, blob_hash: str, size_bytes: int) -> bool:
        self.find_calls.append((instance_name, blob_hash, size_bytes))
        if self.find_error is not None:
            raise self.find_error
        return self.missing

    def read_sha256(self, instance_name: str, blob_hash: str, size_bytes: int) -> str:
        self.read_calls.append((instance_name, blob_hash, size_bytes))
        if self.read_error is not None:
            raise self.read_error
        assert self.digest is not None
        return self.digest


def _uri(size: int = 18, *, instance: str = "") -> str:
    prefix = f"/{instance}" if instance else ""
    return f"bytestream://cas.example:8980{prefix}/blobs/{_HASH}/{size}"


def test_present_blob_is_read_and_digest_returned() -> None:
    transport = FakeTransport(digest=_HASH)
    probe = make_cas_probe("grpc://cas.example:8980", transport=transport)

    result = probe(_uri(), _HASH, 18)

    assert result == ProbeResult(present=True, computed_digest=_HASH)
    assert transport.find_calls == [("", _HASH, 18)]
    assert transport.read_calls == [("", _HASH, 18)]
    assert probe.stats.present_digest_recomputed == 1


def test_missing_blob_reports_absence_without_reading() -> None:
    transport = FakeTransport(missing=True)
    probe = make_cas_probe("grpc://cas.example:8980", transport=transport)

    result = probe(_uri(), _HASH, 18)

    assert result == ProbeResult(present=False)
    assert transport.read_calls == []
    assert probe.stats.missing == 1


def test_find_missing_error_is_inconclusive_never_raises() -> None:
    transport = FakeTransport(find_error=RuntimeError("connection refused"))
    probe = make_cas_probe("grpc://cas.example:8980", transport=transport)

    assert probe(_uri(), _HASH, 18) is None
    assert probe.stats.inconclusive == 1


def test_read_error_after_presence_is_inconclusive() -> None:
    """Conflicting evidence never rounds up: present-then-read-failure is no verdict."""

    transport = FakeTransport(read_error=RuntimeError("stream reset"))
    probe = make_cas_probe("grpc://cas.example:8980", transport=transport)

    assert probe(_uri(), _HASH, 18) is None
    assert probe.stats.inconclusive == 1


def test_unsupported_uri_is_no_verdict() -> None:
    transport = FakeTransport(digest=_HASH)
    probe = make_cas_probe("grpc://cas.example:8980", transport=transport)

    assert probe("s3://bucket/key", _HASH, 18) is None
    assert transport.find_calls == []
    assert probe.stats.unsupported_uri == 1


def test_no_declared_digest_skips_read_with_honest_note() -> None:
    transport = FakeTransport()
    probe = make_cas_probe("grpc://cas.example:8980", transport=transport)

    result = probe(_uri(), None, None)

    assert result is not None
    assert result.present is True
    assert result.computed_digest is None
    assert "no digest to cross-check" in (result.note or "")
    assert transport.read_calls == []
    assert probe.stats.present_not_read == 1


def test_non_sha256_declared_digest_skips_read() -> None:
    transport = FakeTransport()
    probe = make_cas_probe("grpc://cas.example:8980", transport=transport)

    result = probe(_uri(), "ab" * 20, 18)  # 40 hex chars: SHA-1 shaped

    assert result is not None
    assert result.present is True
    assert result.computed_digest is None
    assert transport.read_calls == []


def test_over_read_limit_skips_read_with_honest_note() -> None:
    transport = FakeTransport()
    probe = make_cas_probe("grpc://cas.example:8980", read_limit_bytes=10, transport=transport)

    result = probe(_uri(size=11), _HASH, 11)

    assert result is not None
    assert result.present is True
    assert result.computed_digest is None
    assert "read limit" in (result.note or "")
    assert transport.read_calls == []
    assert probe.stats.present_not_read == 1


def test_at_read_limit_still_reads() -> None:
    transport = FakeTransport(digest=_HASH)
    probe = make_cas_probe("grpc://cas.example:8980", read_limit_bytes=11, transport=transport)

    result = probe(_uri(size=11), _HASH, 11)

    assert result == ProbeResult(present=True, computed_digest=_HASH)


def test_compressed_blobs_is_presence_check_only() -> None:
    transport = FakeTransport()
    probe = make_cas_probe("grpc://cas.example:8980", transport=transport)

    uri = f"bytestream://cas.example/main/compressed-blobs/zstd/{_HASH}/2048"
    result = probe(uri, _HASH, 2048)

    assert result is not None
    assert result.present is True
    assert result.computed_digest is None
    assert "compressed-blobs" in (result.note or "")
    assert transport.read_calls == []


def test_uri_instance_takes_precedence_over_flag() -> None:
    transport = FakeTransport(digest=_HASH)
    probe = make_cas_probe("grpc://cas.example:8980", instance="flag-inst", transport=transport)

    probe(_uri(instance="uri-inst"), _HASH, 18)

    assert transport.find_calls == [("uri-inst", _HASH, 18)]


def test_flag_instance_used_when_uri_has_none() -> None:
    transport = FakeTransport(digest=_HASH)
    probe = make_cas_probe("grpc://cas.example:8980", instance="main", transport=transport)

    probe(_uri(), _HASH, 18)

    assert transport.find_calls == [("main", _HASH, 18)]


def test_default_read_limit_is_64_mib() -> None:
    assert DEFAULT_READ_LIMIT_BYTES == 64 * 1024 * 1024


def test_describe_records_endpoint_limits_and_outcomes() -> None:
    transport = FakeTransport(missing=True)
    probe = make_cas_probe(
        "grpc://cas.example:8980", instance="main", read_limit_bytes=123, transport=transport
    )
    probe(_uri(), _HASH, 18)

    described = probe.describe()

    assert described["endpoint"] == "grpc://cas.example:8980"
    assert described["instance"] == "main"
    assert described["read_limit_bytes"] == 123
    assert described["outcomes"]["probed_references"] == 1
    assert described["outcomes"]["missing"] == 1


# ---------------------------------------------------------------------------
# verdict mapping through the real verification seam (still stdlib-only)
# ---------------------------------------------------------------------------


def _seam_reference(probe, *, declared_digest: str | None = _HASH, size: int = 18):
    reference = build_reference(
        {
            "name": "remote.bin",
            "uri": _uri(size=size),
            **({"digest": declared_digest} if declared_digest else {}),
            "length": str(size),
        },
        label="//pkg:remote",
        index=0,
        source_kind="collectable_v1",
        evidence_refs=["run:probe-unit"],
        artifact_base=None,
        cas_probe=probe,
    )
    assert reference is not None
    return reference


def test_seam_maps_probe_session_to_remote_verified() -> None:
    probe = make_cas_probe("grpc://cas.example:8980", transport=FakeTransport(digest=_HASH))
    reference = _seam_reference(probe)
    assert reference.presence == "remote_verified"
    assert reference.digest_verified is True
    assert reference.confidence == "high"


def test_seam_maps_probe_session_to_remote_mismatch() -> None:
    wrong = hashlib.sha256(b"tampered bytes\n").hexdigest()
    probe = make_cas_probe("grpc://cas.example:8980", transport=FakeTransport(digest=wrong))
    reference = _seam_reference(probe)
    assert reference.presence == "remote_mismatch"
    assert reference.digest_verified is False
    assert reference.source_kind == "derived_v1"


def test_seam_maps_probe_session_to_remote_missing() -> None:
    probe = make_cas_probe("grpc://cas.example:8980", transport=FakeTransport(missing=True))
    reference = _seam_reference(probe)
    assert reference.presence == "remote_missing"
    assert reference.confidence == "low"


def test_seam_carries_read_limit_note_into_evidence() -> None:
    """The honest over-cap reason lands verbatim in the verification note."""

    probe = make_cas_probe(
        "grpc://cas.example:8980", read_limit_bytes=10, transport=FakeTransport()
    )
    reference = _seam_reference(probe, size=11)
    assert reference.presence == "remote_present"
    assert reference.confidence == "medium"
    assert "read limit" in (reference.verification_note or "")
    assert "--cas-read-limit" in (reference.verification_note or "")


def test_seam_maps_transport_failure_to_unverified_remote() -> None:
    probe = make_cas_probe(
        "grpc://cas.example:8980",
        transport=FakeTransport(find_error=RuntimeError("unreachable")),
    )
    reference = _seam_reference(probe)
    assert reference.presence == "unverified_remote_reference"
    assert "no verdict" in (reference.verification_note or "")
