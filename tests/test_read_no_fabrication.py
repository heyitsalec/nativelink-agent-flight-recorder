"""Read commands never fabricate a database (GitHub #47, #49).

Every read-side command — ``graph export``, ``runway export``, ``proof export``
(all formats), ``compare index``, ``compare history``, and ``compare export``
(single ``--db`` and cross ``--left-db``/``--right-db`` forms) — must refuse a
nonexistent, zero-byte, or non-SQLite ``--db`` instead of auto-creating an empty
schema and emitting a schema-valid, fully truth-labeled, zero-value projection:
"a confidently-labeled comparison of real data against nothing."

The load-bearing assertions here are (a) exit code 2, (b) an actionable stderr
message, and (c) NO database file (or parent directory) is left behind — a path
typo must fabricate nothing. Writers keep their auto-create behavior (regression
at the bottom).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from nlfr.db import connect, initialize
from nlfr.db.ingest import upsert_run, upsert_target

ROOT = Path(__file__).resolve().parents[1]


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


def _seed_group(db_path: Path, run_group: str) -> None:
    """Record one run + target for ``run_group`` into ``db_path`` (writer path)."""

    conn = initialize(connect(db_path))
    run_id = upsert_run(
        conn,
        stable_key=f"run:{run_group}",
        run_group=run_group,
        scenario=run_group,
        mode="cache-only",
        status="completed",
        started_at="2026-07-06T00:00:00.000000Z",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=[f"run:{run_group}"],
        redaction_state="safe",
    )
    upsert_target(
        conn,
        stable_key=f"target:{run_group}",
        run_id=run_id,
        label="//tasks:priority_test",
        target_kind="py_test",
        status="passed",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["bep:target-completed"],
        redaction_state="safe",
    )
    conn.commit()
    conn.close()


# Every read command that takes a single ``--db`` and must refuse a bad path.
SINGLE_DB_READ_COMMANDS: dict[str, list[str]] = {
    "graph-export": ["graph", "export", "--run-group", "latest"],
    "runway-export": ["runway", "export", "--run-group", "latest"],
    "proof-export-json": ["proof", "export", "--run-group", "latest"],
    "proof-export-markdown": [
        "proof",
        "export",
        "--run-group",
        "latest",
        "--format",
        "markdown",
    ],
    "proof-export-in-toto": [
        "proof",
        "export",
        "--run-group",
        "latest",
        "--format",
        "in-toto",
    ],
    "compare-index": ["compare", "index"],
    "compare-history": ["compare", "history"],
    "compare-export-same-db": ["compare", "export", "--left", "a", "--right", "b"],
}


@pytest.mark.parametrize(
    "argv", list(SINGLE_DB_READ_COMMANDS.values()), ids=list(SINGLE_DB_READ_COMMANDS)
)
def test_nonexistent_db_exits_2_and_fabricates_no_file(
    tmp_path: Path, argv: list[str]
) -> None:
    """A missing --db is a hard error that leaves NO file or parent dir behind."""

    missing = tmp_path / "typo" / "nested" / "nlfr.sqlite"

    result = run_nlfr(*argv, "--db", str(missing))

    assert result.returncode == 2, result.stderr
    assert "no NLFR database at" in result.stderr
    assert "refusing to read" in result.stderr
    assert "never creates or migrates a database" in result.stderr
    assert "Traceback" not in result.stderr
    # The anti-fabrication invariant: nothing was auto-created on the way out.
    assert not missing.exists()
    assert not missing.parent.exists()


@pytest.mark.parametrize(
    "argv", list(SINGLE_DB_READ_COMMANDS.values()), ids=list(SINGLE_DB_READ_COMMANDS)
)
def test_zero_byte_db_exits_2(tmp_path: Path, argv: list[str]) -> None:
    """A zero-byte file is the silent-empty trap (mode=ro opens it) — reject it."""

    zero = tmp_path / "nlfr.sqlite"
    zero.write_bytes(b"")

    result = run_nlfr(*argv, "--db", str(zero))

    assert result.returncode == 2, result.stderr
    assert "empty (0 bytes)" in result.stderr
    assert "Traceback" not in result.stderr
    # The empty file is not silently populated with a schema.
    assert zero.stat().st_size == 0


@pytest.mark.parametrize(
    "argv", list(SINGLE_DB_READ_COMMANDS.values()), ids=list(SINGLE_DB_READ_COMMANDS)
)
def test_non_sqlite_db_exits_2(tmp_path: Path, argv: list[str]) -> None:
    """A non-SQLite file (garbage/wrong file) is refused before a projector runs."""

    junk = tmp_path / "nlfr.sqlite"
    junk.write_text("this is not a sqlite database\n")

    result = run_nlfr(*argv, "--db", str(junk))

    assert result.returncode == 2, result.stderr
    assert "not a SQLite database" in result.stderr
    assert "Traceback" not in result.stderr


# --- compare export cross-DB: each side's DB validated independently ----------


def test_compare_export_missing_left_db_names_left_side(tmp_path: Path) -> None:
    right = tmp_path / "right.sqlite"
    _seed_group(right, "right-group")
    missing_left = tmp_path / "left.sqlite"

    result = run_nlfr(
        "compare",
        "export",
        "--left-db",
        str(missing_left),
        "--right-db",
        str(right),
        "--left",
        "left-group",
        "--right",
        "right-group",
    )

    assert result.returncode == 2, result.stderr
    assert "the left compare database could not be read" in result.stderr
    assert "no NLFR database at" in result.stderr
    assert not missing_left.exists()


def test_compare_export_missing_right_db_names_right_side(tmp_path: Path) -> None:
    left = tmp_path / "left.sqlite"
    _seed_group(left, "left-group")
    missing_right = tmp_path / "right.sqlite"

    result = run_nlfr(
        "compare",
        "export",
        "--left-db",
        str(left),
        "--right-db",
        str(missing_right),
        "--left",
        "left-group",
        "--right",
        "right-group",
    )

    assert result.returncode == 2, result.stderr
    assert "the right compare database could not be read" in result.stderr
    assert not missing_right.exists()


# --- compare export: run group with zero runs in an EXISTING DB ---------------


def test_compare_export_cross_db_missing_left_group_lists_present(
    tmp_path: Path,
) -> None:
    left = tmp_path / "left.sqlite"
    _seed_group(left, "left-group")
    right = tmp_path / "right.sqlite"
    _seed_group(right, "right-group")

    result = run_nlfr(
        "compare",
        "export",
        "--left-db",
        str(left),
        "--right-db",
        str(right),
        "--left",
        "ghost-left",
        "--right",
        "right-group",
    )

    assert result.returncode == 2, result.stderr
    assert "left run group 'ghost-left' has no recorded runs" in result.stderr
    # Lists the group actually present in the LEFT database (not the right).
    assert "left-group (1 run(s))" in result.stderr
    assert "compare index" in result.stderr


def test_compare_export_cross_db_missing_right_group_lists_present(
    tmp_path: Path,
) -> None:
    left = tmp_path / "left.sqlite"
    _seed_group(left, "left-group")
    right = tmp_path / "right.sqlite"
    _seed_group(right, "right-group")

    result = run_nlfr(
        "compare",
        "export",
        "--left-db",
        str(left),
        "--right-db",
        str(right),
        "--left",
        "left-group",
        "--right",
        "ghost-right",
    )

    assert result.returncode == 2, result.stderr
    assert "right run group 'ghost-right' has no recorded runs" in result.stderr
    # Lists the group actually present in the RIGHT database.
    assert "right-group (1 run(s))" in result.stderr


def test_compare_export_same_db_missing_group_lists_present(tmp_path: Path) -> None:
    db = tmp_path / "nlfr.sqlite"
    _seed_group(db, "only-group")

    result = run_nlfr(
        "compare",
        "export",
        "--db",
        str(db),
        "--left",
        "only-group",
        "--right",
        "ghost-group",
    )

    assert result.returncode == 2, result.stderr
    assert "right run group 'ghost-group' has no recorded runs" in result.stderr
    assert "only-group (1 run(s))" in result.stderr


# --- honesty: existing-but-empty DB stays a legitimate report -----------------


def test_compare_index_existing_empty_db_is_honest_exit_0(tmp_path: Path) -> None:
    db = tmp_path / "nlfr.sqlite"
    initialize(connect(db))  # existing file, real schema, zero run groups

    result = run_nlfr("compare", "index", "--db", str(db))

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "no run groups recorded"


def test_compare_index_existing_empty_db_json_is_honest_exit_0(tmp_path: Path) -> None:
    db = tmp_path / "nlfr.sqlite"
    initialize(connect(db))

    result = run_nlfr("compare", "index", "--db", str(db), "--json")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["count"] == 0
    assert payload["run_groups"] == []


def test_compare_history_existing_empty_db_is_honest_exit_0(tmp_path: Path) -> None:
    db = tmp_path / "nlfr.sqlite"
    initialize(connect(db))

    result = run_nlfr("compare", "history", "--db", str(db))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["projection_kind"] == "run_history"
    assert payload["summary"]["run_groups"] == 0


# --- real reads still work end-to-end -----------------------------------------


def test_graph_export_real_db_still_works(tmp_path: Path) -> None:
    db = tmp_path / "nlfr.sqlite"
    _seed_group(db, "g1")

    result = run_nlfr("graph", "export", "--db", str(db), "--run-group", "g1")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema_version"] >= 1


def test_proof_export_json_existing_db_missing_group_keeps_empty_payload(
    tmp_path: Path,
) -> None:
    """#46 scoping: json/markdown proof export keep empty-payload behavior when the
    DB EXISTS. Only the nonexistent-DB path hardened — a missing run group in an
    existing DB is NOT a hard error for the plain json format."""

    db = tmp_path / "nlfr.sqlite"
    _seed_group(db, "g1")

    result = run_nlfr("proof", "export", "--db", str(db), "--run-group", "ghost")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload  # structurally valid, just empty of runs
    assert payload["summary"]["runs"] == 0


def test_real_cross_db_compare_still_works(tmp_path: Path) -> None:
    left = tmp_path / "left.sqlite"
    _seed_group(left, "left-group")
    right = tmp_path / "right.sqlite"
    _seed_group(right, "right-group")
    out = tmp_path / "compare.json"

    result = run_nlfr(
        "compare",
        "export",
        "--left-db",
        str(left),
        "--right-db",
        str(right),
        "--left",
        "left-group",
        "--right",
        "right-group",
        "--output",
        str(out),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text())
    assert payload["projection_kind"] == "compare"
    assert payload["summary"]["left_runs"] == 1
    assert payload["summary"]["right_runs"] == 1


def test_real_same_db_compare_still_works(tmp_path: Path) -> None:
    db = tmp_path / "nlfr.sqlite"
    _seed_group(db, "left-group")
    _seed_group(db, "right-group")

    result = run_nlfr(
        "compare",
        "export",
        "--db",
        str(db),
        "--left",
        "left-group",
        "--right",
        "right-group",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["projection_kind"] == "compare"
    assert payload["summary"]["left_runs"] == 1
    assert payload["summary"]["right_runs"] == 1


# --- regression: writers still auto-create -----------------------------------


def test_writer_connect_still_auto_creates_db_and_schema(tmp_path: Path) -> None:
    """The WRITER path is unchanged: connect() creates parent dirs + schema."""

    db = tmp_path / "brand" / "new" / "nlfr.sqlite"
    assert not db.exists()

    conn = initialize(connect(db))
    try:
        assert db.exists()
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert "runs" in tables
    finally:
        conn.close()
