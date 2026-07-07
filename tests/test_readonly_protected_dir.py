"""Read-only opens survive a write-protected evidence directory (the NLFR case).

Every writer opens the spine in WAL journal mode, so a recorded database's header
says WAL. Opening such a file with ``mode=ro`` still makes SQLite try to create
the ``-shm``/``-wal`` sidecars to build a read snapshot — and in an UNWRITABLE
directory (``chmod 555``, exactly the protect-the-evidence scenario NLFR serves)
that sidecar creation fails with an uncaught ``attempt to write a readonly
database`` traceback and exit 1.

:func:`nlfr.db.connection.connect_readonly` retries with ``mode=ro&immutable=1``
when — and only when — the plain ``mode=ro`` open hits that readonly-write error.
``immutable=1`` reads the main file with no sidecars, and is sound precisely
there: a directory SQLite cannot write to cannot host a live writer, so its
"no concurrent writer" assumption already holds.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from nlfr.db import connect, initialize
from nlfr.db.ingest import upsert_artifact, upsert_run

ROOT = Path(__file__).resolve().parents[1]

# Running as root ignores 0o555 directory permissions, so the scenario cannot be
# reproduced and the fallback cannot be exercised — skip rather than pass vacuously.
_IS_ROOT = hasattr(os, "geteuid") and os.geteuid() == 0
pytestmark = pytest.mark.skipif(
    _IS_ROOT, reason="chmod 555 does not restrict root; cannot exercise the fallback"
)


def run_nlfr(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "nlfr", *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _seed_wal_db(db_path: Path) -> None:
    """Record a run + artifact into a WAL-mode spine, then drop the WAL sidecars.

    Dropping ``-shm``/``-wal`` after a clean close forces a fresh reader to try to
    recreate them — the exact trigger for the readonly-write error in a locked
    directory.
    """

    conn = initialize(connect(db_path))
    assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    run_id = upsert_run(
        conn,
        stable_key="run:g1",
        run_group="g1",
        scenario="g1",
        mode="cache-only",
        status="completed",
        started_at="2026-07-06T00:00:00.000000Z",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["run:g1"],
        redaction_state="safe",
    )
    upsert_artifact(
        conn,
        stable_key="run:g1:artifact:a",
        run_id=run_id,
        artifact_key="out/a.txt",
        artifact_path="out/a.txt",
        sha256="a" * 64,
        size_bytes=3,
        producer_command="bazel build //a",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["artifact:a"],
        redaction_state="safe",
    )
    conn.commit()
    conn.close()
    for sidecar in (db_path.with_name(db_path.name + "-wal"), db_path.with_name(db_path.name + "-shm")):
        sidecar.unlink(missing_ok=True)


@pytest.fixture
def protected_wal_db(tmp_path: Path) -> Iterator[Path]:
    """A WAL DB inside a ``chmod 555`` directory, restored to writable on teardown."""

    prot = tmp_path / "protected"
    prot.mkdir()
    db = prot / "nlfr.sqlite"
    _seed_wal_db(db)
    os.chmod(prot, 0o555)
    try:
        yield db
    finally:
        # Restore write permission so pytest can clean the tmp directory up.
        os.chmod(prot, 0o755)


def test_graph_export_reads_wal_db_in_readonly_dir(protected_wal_db: Path) -> None:
    result = run_nlfr("graph", "export", "--db", str(protected_wal_db), "--run-group", "g1")

    assert result.returncode == 0, result.stderr
    assert "readonly database" not in result.stderr
    assert "Traceback" not in result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema_version"] >= 1


def test_proof_export_reads_wal_db_in_readonly_dir(protected_wal_db: Path) -> None:
    result = run_nlfr("proof", "export", "--db", str(protected_wal_db), "--run-group", "g1")

    assert result.returncode == 0, result.stderr
    assert "readonly database" not in result.stderr
    assert "Traceback" not in result.stderr
    payload = json.loads(result.stdout)
    assert payload["summary"]["runs"] == 1
    assert payload["summary"]["artifacts"] == 1


def test_no_sidecar_files_created_in_readonly_dir(protected_wal_db: Path) -> None:
    """The immutable read must not (be able to) leave -shm/-wal behind."""

    run_nlfr("proof", "export", "--db", str(protected_wal_db), "--run-group", "g1")

    entries = {p.name for p in protected_wal_db.parent.iterdir()}
    assert entries == {"nlfr.sqlite"}


def test_normal_writable_dir_read_still_works(tmp_path: Path) -> None:
    """Regression: the fallback does not disturb the ordinary writable-dir read."""

    db = tmp_path / "nlfr.sqlite"
    _seed_wal_db(db)

    result = run_nlfr("graph", "export", "--db", str(db), "--run-group", "g1")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema_version"] >= 1


def test_db_upgrade_in_readonly_dir_refuses_cleanly(protected_wal_db: Path) -> None:
    """`nlfr db upgrade` against an unwritable directory: clean exit 2, no traceback.

    Upgrading writes, so it legitimately cannot proceed here — but the refusal
    must match the rest of the read-path UX (actionable message), never a raw
    sqlite3.OperationalError traceback. The evidence stays untouched either way.
    """

    result = run_nlfr("db", "upgrade", "--db", str(protected_wal_db))
    assert result.returncode == 2, result.stdout + result.stderr
    assert "cannot upgrade the database" in result.stderr
    assert "not writable" in result.stderr
    assert "Traceback" not in result.stderr
