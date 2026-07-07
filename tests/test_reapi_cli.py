"""CLI wiring tests for `nlfr ingest --cas-endpoint` (issue #81 part B).

All stdlib-only: the probe is exercised through injected fake transports or a
subprocess that structurally blocks third-party imports, so this file runs (and
must pass) in the default zero-dependency environment. The real-gRPC CLI path
is covered in ``tests/test_reapi_probe_integration.py``.

The honesty contract under test:

* no ``--cas-endpoint``  -> exactly today's behavior (no probe, no new block);
* flag given, extra missing -> HARD error naming the install command (the
  operator asked for verification; silently downgrading would be a lie);
* flag given, endpoint invalid -> hard error;
* flag given, CAS unreachable -> ingest still succeeds, references stay
  honestly unverified, and stderr carries a prominent summary;
* probe outcomes + endpoint land in a ``cas_probe_v1`` proof block.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from nlfr.cli import main
from nlfr.reapi.probe import CasProbeSession

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

_BLOB_BYTES = b"remote blob bytes\n"
_BLOB_DIGEST = hashlib.sha256(_BLOB_BYTES).hexdigest()
_REMOTE_URI = f"bytestream://cas.example:8980/main/blobs/{_BLOB_DIGEST}/{len(_BLOB_BYTES)}"


def _write_bep(tmp_path: Path) -> Path:
    events = [
        {"id": {"started": {}}, "started": {"command": "build"}},
        {
            "id": {"namedSetOfFiles": {"id": "0"}},
            "namedSetOfFiles": {
                "files": [
                    {
                        "name": "remote.bin",
                        "uri": _REMOTE_URI,
                        "digest": _BLOB_DIGEST,
                        "length": str(len(_BLOB_BYTES)),
                    }
                ]
            },
        },
    ]
    bep_path = tmp_path / "bazel.bep.json"
    bep_path.write_text("\n".join(json.dumps(event) for event in events) + "\n")
    return bep_path


class FakeTransport:
    def __init__(self, *, missing: bool = False, digest: str | None = None,
                 find_error: Exception | None = None) -> None:
        self.missing = missing
        self.digest = digest
        self.find_error = find_error

    def find_missing(self, instance_name: str, blob_hash: str, size_bytes: int) -> bool:
        if self.find_error is not None:
            raise self.find_error
        return self.missing

    def read_sha256(self, instance_name: str, blob_hash: str, size_bytes: int) -> str:
        assert self.digest is not None
        return self.digest


def _patch_probe_factory(monkeypatch: pytest.MonkeyPatch, transport: FakeTransport) -> list[dict]:
    """Route the CLI's make_cas_probe through a fake transport, recording kwargs."""

    import nlfr.reapi.probe as probe_module

    calls: list[dict] = []

    def fake_factory(endpoint: str, **kwargs):
        calls.append({"endpoint": endpoint, **kwargs})
        kwargs.pop("transport", None)
        return CasProbeSession(endpoint, transport=transport, **kwargs)

    monkeypatch.setattr(probe_module, "make_cas_probe", fake_factory)
    return calls


def _ingest(tmp_path: Path, *extra_args: str) -> tuple[int, Path]:
    bep_path = _write_bep(tmp_path)
    database = tmp_path / "nlfr.sqlite"
    exit_code = main(
        [
            "ingest",
            "--bep",
            str(bep_path),
            "--database",
            str(database),
            "--run-key",
            "reapi-cli-test",
            "--json",
            *extra_args,
        ]
    )
    return exit_code, database


def test_without_flag_no_probe_and_no_probe_block(tmp_path: Path, capsys) -> None:
    """No --cas-endpoint: the historical downgrade, no cas_probe provenance."""

    exit_code, database = _ingest(tmp_path)
    assert exit_code == 0

    payload = json.loads(capsys.readouterr().out)
    assert "cas_probe" not in payload

    conn = sqlite3.connect(database)
    conn.row_factory = sqlite3.Row
    try:
        assert (
            conn.execute(
                "SELECT COUNT(*) AS n FROM proof_blocks WHERE block_kind = 'cas_probe_v1'"
            ).fetchone()["n"]
            == 0
        )
        (row,) = conn.execute("SELECT presence FROM artifact_references").fetchall()
        assert row["presence"] == "unverified_remote_reference"
    finally:
        conn.close()


def test_probe_outcomes_recorded_in_block_and_payload(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _patch_probe_factory(monkeypatch, FakeTransport(digest=_BLOB_DIGEST))

    exit_code, database = _ingest(
        tmp_path, "--cas-endpoint", "grpc://cas.example:8980", "--cas-instance", "main",
        "--cas-read-limit", "1048576",
    )
    assert exit_code == 0
    # The CLI forwarded the operator's exact configuration to the factory.
    assert calls == [
        {
            "endpoint": "grpc://cas.example:8980",
            "instance": "main",
            "read_limit_bytes": 1048576,
        }
    ]

    payload = json.loads(capsys.readouterr().out)
    assert payload["cas_probe"]["endpoint"] == "grpc://cas.example:8980"
    assert payload["cas_probe"]["presence_counts"]["remote_verified"] == 1
    assert payload["cas_probe"]["outcomes"]["probed_references"] == 1

    conn = sqlite3.connect(database)
    conn.row_factory = sqlite3.Row
    try:
        block = conn.execute(
            "SELECT * FROM proof_blocks WHERE block_kind = 'cas_probe_v1'"
        ).fetchone()
        assert block is not None
        block_payload = json.loads(block["payload"])
        assert block_payload["endpoint"] == "grpc://cas.example:8980"
        assert block_payload["instance"] == "main"
        assert block_payload["read_limit_bytes"] == 1048576
        assert block_payload["presence_counts"]["remote_verified"] == 1
        assert "verified" in block["summary"]
    finally:
        conn.close()


def test_unreachable_cas_keeps_ingest_green_with_prominent_stderr(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unreachable CAS: evidence recorded honestly, loud operator summary."""

    _patch_probe_factory(
        monkeypatch, FakeTransport(find_error=RuntimeError("connection refused"))
    )

    exit_code, database = _ingest(tmp_path, "--cas-endpoint", "grpc://down.example:1")
    assert exit_code == 0  # ingest still succeeds — the evidence is honest

    captured = capsys.readouterr()
    assert "CAS probe unreachable: 1 remote ref(s) left unverified" in captured.err
    payload = json.loads(captured.out)
    assert payload["cas_probe"]["outcomes"]["inconclusive"] == 1
    assert payload["cas_probe"]["presence_counts"]["unverified_remote_reference"] == 1

    conn = sqlite3.connect(database)
    conn.row_factory = sqlite3.Row
    try:
        (row,) = conn.execute(
            "SELECT presence, verification_note FROM artifact_references"
        ).fetchall()
        assert row["presence"] == "unverified_remote_reference"
        assert "no verdict" in row["verification_note"]
    finally:
        conn.close()


def test_invalid_endpoint_is_a_hard_error(tmp_path: Path, capsys) -> None:
    """A bad endpoint fails fast — before any parsing, before any grpc import."""

    exit_code, _database = _ingest(tmp_path, "--cas-endpoint", "http://cas.example:443")
    assert exit_code == 2
    assert "invalid --cas-endpoint" in capsys.readouterr().err


def test_missing_extra_is_a_hard_error_with_install_hint(tmp_path: Path) -> None:
    """--cas-endpoint without the [reapi] extra refuses with the exact command.

    Runs in a subprocess with third-party imports structurally blocked so the
    proof holds even where grpcio happens to be installed (the CI extra job).
    """

    bep_path = _write_bep(tmp_path)
    script = f"""
import sys

class Blocker:
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in ("grpc", "google"):
            raise ImportError(f"blocked: {{name}}")
        return None

sys.meta_path.insert(0, Blocker())

from nlfr.cli import main

sys.exit(
    main(
        [
            "ingest",
            "--bep",
            {str(bep_path)!r},
            "--database",
            {str(tmp_path / "nlfr.sqlite")!r},
            "--cas-endpoint",
            "grpc://127.0.0.1:1",
        ]
    )
)
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=ROOT,
        env={"PYTHONPATH": str(SRC), "PATH": "/usr/bin:/bin"},
    )
    assert result.returncode == 2, result.stderr
    assert 'pip install "nativelink-agent-flight-recorder[reapi]"' in result.stderr
    assert "unverified_remote_reference" in result.stderr  # states the fallback honestly
    # Hard error means NOTHING was ingested under a false pretense.
    assert not (tmp_path / "nlfr.sqlite").exists()
