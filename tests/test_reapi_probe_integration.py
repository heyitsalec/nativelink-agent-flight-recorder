"""Integration tests: the CAS probe over REAL gRPC against an in-process server.

These tests are skipped without grpcio (``pytest.importorskip``) — the default
NLFR environment has no third-party runtime packages, and CI runs them in a
dedicated non-blocking job that installs the ``[reapi]`` extra
(``.github/workflows/reapi-probe.yml``).

The server here is a real ``grpc.server`` speaking the two REAPI methods the
probe uses, registered through generic method handlers with the SAME
fully-qualified method paths the probe dials — so these tests prove the wire
contract (paths, message encoding via the vendored stubs, deadline behavior),
not just the verdict logic (that is covered stdlib-only in
``tests/test_reapi_probe.py``). Every remote-verification label is produced
here from an actual RPC round-trip, including the SHA-256 mismatch case where
the store serves tampered bytes.
"""

from __future__ import annotations

import hashlib
import json
import socket
import time
from concurrent import futures
from pathlib import Path

import pytest

grpc = pytest.importorskip("grpc")

from nlfr.ingest.bazel import parse_bazel_bep  # noqa: E402
from nlfr.reapi._gen.build.bazel.remote.execution.v2 import (  # noqa: E402
    remote_execution_pb2 as re_pb2,
)
from nlfr.reapi._gen.google.bytestream import bytestream_pb2 as bs_pb2  # noqa: E402
from nlfr.reapi.probe import (  # noqa: E402
    BYTESTREAM_READ_METHOD,
    FIND_MISSING_BLOBS_METHOD,
    make_cas_probe,
)

_VERIFIED_BYTES = b"true remote blob bytes\n"
_MISMATCH_BYTES = b"bytes the BEP promised\n"
_TAMPERED_BYTES = b"tampered bytes the CAS actually serves\n"
_UNREAD_BYTES = b"present but never read\n"
_MISSING_BYTES = b"never uploaded\n"

_VERIFIED_DIGEST = hashlib.sha256(_VERIFIED_BYTES).hexdigest()
_MISMATCH_DIGEST = hashlib.sha256(_MISMATCH_BYTES).hexdigest()
_UNREAD_DIGEST = hashlib.sha256(_UNREAD_BYTES).hexdigest()
_MISSING_DIGEST = hashlib.sha256(_MISSING_BYTES).hexdigest()


class InProcessCas:
    """A minimal, real-gRPC CAS: FindMissingBlobs presence + ByteStream reads.

    ``blobs`` (hash -> bytes) defines presence; ``serve_overrides`` lets a test
    make the store serve DIFFERENT bytes than the digest promises — the
    tampered-store / failed-upload scenario NLFR must catch, not trust.
    """

    def __init__(
        self,
        blobs: dict[str, bytes],
        *,
        serve_overrides: dict[str, bytes] | None = None,
        delay_s: float = 0.0,
    ) -> None:
        self.blobs = blobs
        self.serve_overrides = serve_overrides or {}
        self.delay_s = delay_s
        self.find_requests: list = []
        self.read_requests: list = []

    def find_missing_blobs(self, request, context):
        if self.delay_s:
            time.sleep(self.delay_s)
        self.find_requests.append(request)
        missing = [
            digest for digest in request.blob_digests if digest.hash not in self.blobs
        ]
        return re_pb2.FindMissingBlobsResponse(missing_blob_digests=missing)

    def read(self, request, context):
        if self.delay_s:
            time.sleep(self.delay_s)
        self.read_requests.append(request)
        segments = request.resource_name.split("/")
        assert "blobs" in segments, request.resource_name
        blob_hash = segments[segments.index("blobs") + 1]
        data = self.serve_overrides.get(blob_hash, self.blobs.get(blob_hash))
        if data is None:
            context.abort(grpc.StatusCode.NOT_FOUND, "blob not found")
        chunk_size = 7  # force multiple stream messages
        for offset in range(0, len(data), chunk_size):
            yield bs_pb2.ReadResponse(data=data[offset : offset + chunk_size])


@pytest.fixture
def cas_server():
    """Start real gRPC servers for InProcessCas instances; stop them at teardown."""

    servers: list = []

    def start(cas: InProcessCas) -> str:
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
        cas_service = FIND_MISSING_BLOBS_METHOD.split("/")[1]
        bytestream_service = BYTESTREAM_READ_METHOD.split("/")[1]
        server.add_generic_rpc_handlers(
            (
                grpc.method_handlers_generic_handler(
                    cas_service,
                    {
                        "FindMissingBlobs": grpc.unary_unary_rpc_method_handler(
                            cas.find_missing_blobs,
                            request_deserializer=re_pb2.FindMissingBlobsRequest.FromString,
                            response_serializer=re_pb2.FindMissingBlobsResponse.SerializeToString,
                        )
                    },
                ),
                grpc.method_handlers_generic_handler(
                    bytestream_service,
                    {
                        "Read": grpc.unary_stream_rpc_method_handler(
                            cas.read,
                            request_deserializer=bs_pb2.ReadRequest.FromString,
                            response_serializer=bs_pb2.ReadResponse.SerializeToString,
                        )
                    },
                ),
            )
        )
        port = server.add_insecure_port("127.0.0.1:0")
        server.start()
        servers.append(server)
        return f"grpc://127.0.0.1:{port}"

    yield start
    for server in servers:
        server.stop(grace=None)


def _bep_fixture(tmp_path: Path, endpoint: str, files: list[dict]) -> Path:
    host_port = endpoint.removeprefix("grpc://")
    for file_payload in files:
        # Rewrite {host} placeholders so URIs carry the live server authority
        # (ignored for dialing, but realistic).
        file_payload["uri"] = file_payload["uri"].format(host=host_port)
    events = [
        {"id": {"started": {}}, "started": {"command": "build"}},
        {"id": {"namedSetOfFiles": {"id": "0"}}, "namedSetOfFiles": {"files": files}},
    ]
    bep_path = tmp_path / "bazel.bep.json"
    bep_path.write_text("\n".join(json.dumps(event) for event in events) + "\n")
    return bep_path


def _remote_file(name: str, digest: str | None, size: int, *, instance: str = "main") -> dict:
    prefix = f"/{instance}" if instance else ""
    payload = {
        "name": name,
        "uri": f"bytestream://{{host}}{prefix}/blobs/{digest or 'f' * 64}/{size}",
        "length": str(size),
    }
    if digest is not None:
        payload["digest"] = digest
    return payload


def test_all_remote_labels_from_real_grpc_calls(tmp_path: Path, cas_server) -> None:
    """One BEP, one real CAS: all four remote_* labels from actual RPCs.

    * remote_verified — blob present, streamed bytes hash to the declared digest;
    * remote_mismatch — blob present, but the store serves TAMPERED bytes;
    * remote_missing  — FindMissingBlobs confirms absence (bazel#23250 mode);
    * remote_present  — blob present but the BEP declared no digest (no read).
    """

    cas = InProcessCas(
        blobs={
            _VERIFIED_DIGEST: _VERIFIED_BYTES,
            _MISMATCH_DIGEST: _MISMATCH_BYTES,
            _UNREAD_DIGEST: _UNREAD_BYTES,
        },
        serve_overrides={_MISMATCH_DIGEST: _TAMPERED_BYTES},
    )
    endpoint = cas_server(cas)
    bep_path = _bep_fixture(
        tmp_path,
        endpoint,
        [
            _remote_file("verified.bin", _VERIFIED_DIGEST, len(_VERIFIED_BYTES)),
            _remote_file("mismatch.bin", _MISMATCH_DIGEST, len(_MISMATCH_BYTES)),
            _remote_file("missing.bin", _MISSING_DIGEST, len(_MISSING_BYTES)),
            _remote_file("unread.bin", None, len(_UNREAD_BYTES)),
        ],
    )
    # unread.bin needs a URI whose hash is its real CAS coordinate.
    content = bep_path.read_text().replace("f" * 64, _UNREAD_DIGEST)
    bep_path.write_text(content)

    probe = make_cas_probe(endpoint, timeout_s=5.0)
    bundle = parse_bazel_bep(bep_path, source_kind="collectable_v1", cas_probe=probe)
    refs = {ref.name: ref for ref in bundle.artifact_references}

    verified = refs["verified.bin"]
    assert verified.presence == "remote_verified"
    assert verified.digest_verified is True
    assert verified.computed_digest == _VERIFIED_DIGEST
    assert verified.source_kind == "collectable_v1"
    assert verified.confidence == "high"

    mismatch = refs["mismatch.bin"]
    assert mismatch.presence == "remote_mismatch"
    assert mismatch.digest_verified is False
    # The recomputed digest is the hash of what the store ACTUALLY served.
    assert mismatch.computed_digest == hashlib.sha256(_TAMPERED_BYTES).hexdigest()
    assert mismatch.source_kind == "derived_v1"
    assert mismatch.confidence == "low"

    missing = refs["missing.bin"]
    assert missing.presence == "remote_missing"
    assert missing.confidence == "low"
    assert "ABSENT" in (missing.verification_note or "")

    unread = refs["unread.bin"]
    assert unread.presence == "remote_present"
    assert unread.confidence == "medium"
    assert "no digest to cross-check" in (unread.verification_note or "")

    # The server really was asked: instance "main" arrived over the wire.
    assert {request.instance_name for request in cas.find_requests} == {"main"}
    # Only the two hash-checked blobs were streamed.
    read_hashes = {request.resource_name.split("/blobs/")[1].split("/")[0] for request in cas.read_requests}
    assert read_hashes == {_VERIFIED_DIGEST, _MISMATCH_DIGEST}

    stats = probe.stats.as_dict()
    assert stats["probed_references"] == 4
    assert stats["present_digest_recomputed"] == 2
    assert stats["present_not_read"] == 1
    assert stats["missing"] == 1
    assert stats["inconclusive"] == 0


def test_read_limit_is_honored_over_real_grpc(tmp_path: Path, cas_server) -> None:
    """An over-limit blob is confirmed present but never streamed."""

    cas = InProcessCas(blobs={_VERIFIED_DIGEST: _VERIFIED_BYTES})
    endpoint = cas_server(cas)
    bep_path = _bep_fixture(
        tmp_path,
        endpoint,
        [_remote_file("big.bin", _VERIFIED_DIGEST, len(_VERIFIED_BYTES))],
    )

    probe = make_cas_probe(endpoint, timeout_s=5.0, read_limit_bytes=4)
    bundle = parse_bazel_bep(bep_path, source_kind="collectable_v1", cas_probe=probe)

    (reference,) = bundle.artifact_references
    assert reference.presence == "remote_present"
    assert "read limit" in (reference.verification_note or "")
    assert cas.read_requests == []


def test_deadline_exceeded_is_honestly_unverified(tmp_path: Path, cas_server) -> None:
    """A CAS that cannot answer within the deadline yields NO verdict."""

    cas = InProcessCas(blobs={_VERIFIED_DIGEST: _VERIFIED_BYTES}, delay_s=1.5)
    endpoint = cas_server(cas)
    bep_path = _bep_fixture(
        tmp_path,
        endpoint,
        [_remote_file("slow.bin", _VERIFIED_DIGEST, len(_VERIFIED_BYTES))],
    )

    probe = make_cas_probe(endpoint, timeout_s=0.2)
    bundle = parse_bazel_bep(bep_path, source_kind="collectable_v1", cas_probe=probe)

    (reference,) = bundle.artifact_references
    assert reference.presence == "unverified_remote_reference"
    assert "no verdict" in (reference.verification_note or "")
    assert probe.stats.inconclusive == 1


def test_unreachable_endpoint_is_honestly_unverified(tmp_path: Path) -> None:
    """Nothing listening at the endpoint: every probe is inconclusive, never fake."""

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        free_port = sock.getsockname()[1]

    bep_path = _bep_fixture(
        tmp_path,
        f"grpc://127.0.0.1:{free_port}",
        [_remote_file("gone.bin", _VERIFIED_DIGEST, len(_VERIFIED_BYTES))],
    )

    probe = make_cas_probe(f"grpc://127.0.0.1:{free_port}", timeout_s=1.0)
    bundle = parse_bazel_bep(bep_path, source_kind="collectable_v1", cas_probe=probe)

    (reference,) = bundle.artifact_references
    assert reference.presence == "unverified_remote_reference"
    assert probe.stats.inconclusive == 1


def test_ingest_cli_end_to_end_with_real_cas(tmp_path: Path, capsys) -> None:
    """`nlfr ingest --cas-endpoint` against a live CAS: labels in SQLite plus
    a cas_probe_v1 provenance block recording endpoint and outcome counts."""

    import sqlite3

    from nlfr.cli import main

    cas = InProcessCas(blobs={_VERIFIED_DIGEST: _VERIFIED_BYTES})
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    server.add_generic_rpc_handlers(
        (
            grpc.method_handlers_generic_handler(
                FIND_MISSING_BLOBS_METHOD.split("/")[1],
                {
                    "FindMissingBlobs": grpc.unary_unary_rpc_method_handler(
                        cas.find_missing_blobs,
                        request_deserializer=re_pb2.FindMissingBlobsRequest.FromString,
                        response_serializer=re_pb2.FindMissingBlobsResponse.SerializeToString,
                    )
                },
            ),
            grpc.method_handlers_generic_handler(
                BYTESTREAM_READ_METHOD.split("/")[1],
                {
                    "Read": grpc.unary_stream_rpc_method_handler(
                        cas.read,
                        request_deserializer=bs_pb2.ReadRequest.FromString,
                        response_serializer=bs_pb2.ReadResponse.SerializeToString,
                    )
                },
            ),
        )
    )
    port = server.add_insecure_port("127.0.0.1:0")
    server.start()
    try:
        endpoint = f"grpc://127.0.0.1:{port}"
        bep_path = _bep_fixture(
            tmp_path,
            endpoint,
            [
                _remote_file("verified.bin", _VERIFIED_DIGEST, len(_VERIFIED_BYTES)),
                _remote_file("missing.bin", _MISSING_DIGEST, len(_MISSING_BYTES)),
            ],
        )
        database = tmp_path / "nlfr.sqlite"

        exit_code = main(
            [
                "ingest",
                "--bep",
                str(bep_path),
                "--database",
                str(database),
                "--run-key",
                "reapi-cli-e2e",
                "--cas-endpoint",
                endpoint,
                "--cas-instance",
                "main",
                "--json",
            ]
        )
        assert exit_code == 0

        payload = json.loads(capsys.readouterr().out)
        assert payload["cas_probe"]["endpoint"] == endpoint
        assert payload["cas_probe"]["presence_counts"]["remote_verified"] == 1
        assert payload["cas_probe"]["presence_counts"]["remote_missing"] == 1
        assert payload["cas_probe"]["outcomes"]["probed_references"] == 2

        conn = sqlite3.connect(database)
        conn.row_factory = sqlite3.Row
        try:
            block = conn.execute(
                "SELECT * FROM proof_blocks WHERE block_kind = 'cas_probe_v1'"
            ).fetchone()
            assert block is not None
            block_payload = json.loads(block["payload"])
            assert block_payload["endpoint"] == endpoint
            assert block_payload["presence_counts"]["remote_verified"] == 1
            presences = {
                row["presence"]
                for row in conn.execute("SELECT presence FROM artifact_references")
            }
            assert presences == {"remote_verified", "remote_missing"}
        finally:
            conn.close()
    finally:
        server.stop(grace=None)
