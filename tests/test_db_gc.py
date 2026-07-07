"""Tests for ``nlfr db gc`` — operator-consented evidence retention.

The gc command deletes whole RUN GROUPS: SQLite rows (via ON DELETE CASCADE from
``runs``) plus the on-disk ``runs/<id>/`` artifact trees that ``nlfr record`` /
``nlfr run`` write next to the database. These tests seed a realistic multi-group
evidence store (DB + on-disk run dirs with ``run.json`` + artifact files), then
exercise: dry-run safety, per-mode selection, --apply deletion + VACUUM +
gc-report.json, the last-group refusal, combined-mode/usage errors, the
nonexistent/old-schema DB gates, and the out-of-tree-artifact refusal.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from nlfr.cli import main
from nlfr.db import connect, initialize
from nlfr.db.ingest import upsert_artifact, upsert_run
from nlfr.db.schema import MIGRATIONS
from nlfr.ids import stable_id


# --------------------------------------------------------------------------- seed


def _timestamp(dt: datetime) -> str:
    return dt.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _seed_group(
    evidence_root: Path,
    run_group: str,
    *,
    started_at: datetime,
    n_runs: int = 1,
    artifact_path_override: str | None = None,
) -> None:
    """Add ``n_runs`` runs for ``run_group`` to the evidence store at ``evidence_root``.

    Writes the DB rows AND the on-disk ``runs/<id>/artifacts`` tree (run.json +
    a payload artifact + manifest) exactly as ``nlfr record`` lays them out, so gc's
    run.json-driven directory discovery finds them.
    """

    db_path = evidence_root / "nlfr.sqlite"
    conn = initialize(connect(db_path))
    try:
        for index in range(n_runs):
            stamp = _timestamp(started_at + timedelta(seconds=index))
            run_key = f"{run_group}:run{index}:{stamp}"
            run_id = stable_id("run", run_key)
            artifact_root = evidence_root / "runs" / run_id / "artifacts"
            artifact_root.mkdir(parents=True, exist_ok=True)

            payload = f"stdout for {run_group} run {index}\n".encode("utf-8")
            (artifact_root / "stdout.txt").write_bytes(payload)
            sha = hashlib.sha256(payload).hexdigest()

            run_metadata = {
                "run_id": run_id,
                "run_key": run_key,
                "run_group": run_group,
                "artifact_root": str(artifact_root),
            }
            (artifact_root / "run.json").write_text(
                json.dumps(run_metadata, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            (artifact_root / "artifact_manifest.json").write_text(
                json.dumps({"schema_version": 1, "artifacts": []}) + "\n",
                encoding="utf-8",
            )

            run_row_id = upsert_run(
                conn,
                stable_key=run_key,
                run_group=run_group,
                scenario="record",
                mode="record",
                status="completed",
                started_at=stamp,
                ended_at=stamp,
                source_kind="collectable_v1",
                confidence="high",
                evidence_refs=[f"run:{run_id}"],
                redaction_state="safe",
            )
            upsert_artifact(
                conn,
                stable_key=f"{run_key}:artifact:stdout.txt",
                run_id=run_row_id,
                artifact_key="stdout.txt",
                artifact_path=artifact_path_override or "stdout.txt",
                manifest_path="artifact_manifest.json",
                sha256=sha,
                size_bytes=len(payload),
                content_type="text/plain",
                producer_command=["nlfr", "record"],
                config_hash=None,
                source_kind="collectable_v1",
                confidence="high",
                evidence_refs=[f"run:{run_id}"],
                redaction_state="safe",
            )
    finally:
        conn.close()


def _seed_null_age_group(evidence_root: Path, run_group: str) -> str:
    """Seed a run group whose one run has NO started_at (age-unknown).

    This is exactly what ``nlfr ingest`` records when the evidence carries no
    observable start time (no BEP ``started`` event) — the input the reviewer's C1
    repro exercises. Writes the DB row plus an on-disk run dir so gc's run.json
    discovery is realistic and the "left untouched" assertions are meaningful.
    Returns the run id.
    """

    db_path = evidence_root / "nlfr.sqlite"
    conn = initialize(connect(db_path))
    try:
        run_key = f"{run_group}:ingest:null-age"
        run_id = stable_id("run", run_key)
        artifact_root = evidence_root / "runs" / run_id / "artifacts"
        artifact_root.mkdir(parents=True, exist_ok=True)
        payload = f"stdout for {run_group}\n".encode("utf-8")
        (artifact_root / "stdout.txt").write_bytes(payload)
        (artifact_root / "run.json").write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "run_key": run_key,
                    "run_group": run_group,
                    "artifact_root": str(artifact_root),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        (artifact_root / "artifact_manifest.json").write_text(
            json.dumps({"schema_version": 1, "artifacts": []}) + "\n",
            encoding="utf-8",
        )
        upsert_run(
            conn,
            stable_key=run_key,
            run_group=run_group,
            scenario="ingest",
            mode="cache-only",
            status="ingested",
            # started_at intentionally omitted: age-unknown, exactly as ingest
            # records evidence that carries no observable start time.
            source_kind="collectable_v1",
            confidence="high",
            evidence_refs=[f"run:{run_id}"],
            redaction_state="safe",
        )
    finally:
        conn.close()
    return run_id


def _seed_three_groups(evidence_root: Path) -> dict[str, datetime]:
    """Seed old/mid/new groups with well-separated timestamps; return their stamps."""

    now = datetime.now(UTC)
    stamps = {
        "old": now - timedelta(days=100),
        "mid": now - timedelta(days=10),
        "new": now - timedelta(days=1),
    }
    for group, started in stamps.items():
        _seed_group(evidence_root, group, started_at=started)
    return stamps


def _run_ids(evidence_root: Path) -> set[str]:
    conn = connect(evidence_root / "nlfr.sqlite")
    try:
        return {row["id"] for row in conn.execute("SELECT id FROM runs")}
    finally:
        conn.close()


def _run_groups(evidence_root: Path) -> set[str]:
    conn = connect(evidence_root / "nlfr.sqlite")
    try:
        return {row["run_group"] for row in conn.execute("SELECT run_group FROM runs")}
    finally:
        conn.close()


def _artifact_count(evidence_root: Path) -> int:
    conn = connect(evidence_root / "nlfr.sqlite")
    try:
        return conn.execute("SELECT COUNT(*) AS c FROM artifacts").fetchone()["c"]
    finally:
        conn.close()


def _gc(*args: str) -> int:
    return main(["db", "gc", *args])


# --------------------------------------------------------------------------- dry run


def test_dry_run_deletes_nothing_and_plans_keep_last(tmp_path, capsys) -> None:
    _seed_three_groups(tmp_path)
    before_ids = _run_ids(tmp_path)
    before_dirs = sorted(p.name for p in (tmp_path / "runs").iterdir())

    code = _gc("--db", str(tmp_path / "nlfr.sqlite"), "--keep-last", "1", "--json")

    assert code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["applied"] is False
    assert report["mode"] == "dry_run"
    assert report["source_kind"] == "derived_v1"
    deleted = {entry["run_group"] for entry in report["deleted_groups"]}
    kept = {entry["run_group"] for entry in report["kept_groups"]}
    assert deleted == {"old", "mid"}
    assert kept == {"new"}
    assert report["totals"]["groups"] == 2
    # Each run dir holds 3 files (stdout.txt + run.json + manifest); 2 dirs -> 6.
    assert report["totals"]["files"] == 6
    # Nothing was touched: rows and on-disk dirs are all intact.
    assert _run_ids(tmp_path) == before_ids
    assert sorted(p.name for p in (tmp_path / "runs").iterdir()) == before_dirs
    assert not (tmp_path / "gc-report.json").exists()


def test_dry_run_plans_keep_days(tmp_path, capsys) -> None:
    _seed_three_groups(tmp_path)

    code = _gc("--db", str(tmp_path / "nlfr.sqlite"), "--keep-days", "30", "--json")

    assert code == 0
    report = json.loads(capsys.readouterr().out)
    deleted = {entry["run_group"] for entry in report["deleted_groups"]}
    kept = {entry["run_group"] for entry in report["kept_groups"]}
    # Only 'old' (100 days) is older than 30 days; 'mid' (10d) and 'new' (1d) stay.
    assert deleted == {"old"}
    assert kept == {"mid", "new"}
    assert _run_groups(tmp_path) == {"old", "mid", "new"}


def test_dry_run_plans_explicit_run_group(tmp_path, capsys) -> None:
    _seed_three_groups(tmp_path)

    code = _gc(
        "--db", str(tmp_path / "nlfr.sqlite"),
        "--run-group", "mid",
        "--run-group", "old",
        "--json",
    )

    assert code == 0
    report = json.loads(capsys.readouterr().out)
    assert {entry["run_group"] for entry in report["deleted_groups"]} == {"mid", "old"}
    assert {entry["run_group"] for entry in report["kept_groups"]} == {"new"}
    assert _run_groups(tmp_path) == {"old", "mid", "new"}


# --------------------------------------------------------------------------- apply


def test_apply_keep_last_deletes_rows_dirs_and_writes_report(tmp_path, capsys) -> None:
    _seed_three_groups(tmp_path)
    runs_root = tmp_path / "runs"

    # Capture the surviving group's on-disk bytes to prove byte-integrity later.
    conn = connect(tmp_path / "nlfr.sqlite")
    new_run_id = conn.execute(
        "SELECT id, stable_key FROM runs WHERE run_group = 'new'"
    ).fetchone()
    conn.close()
    kept_dir = next(
        d for d in runs_root.iterdir()
        if (d / "artifacts" / "run.json").is_file()
        and json.loads((d / "artifacts" / "run.json").read_text())["run_group"] == "new"
    )
    kept_bytes = (kept_dir / "artifacts" / "stdout.txt").read_bytes()
    deleted_dirs = [
        d for d in runs_root.iterdir()
        if (d / "artifacts" / "run.json").is_file()
        and json.loads((d / "artifacts" / "run.json").read_text())["run_group"] != "new"
    ]

    code = _gc("--db", str(tmp_path / "nlfr.sqlite"), "--keep-last", "1", "--apply", "--json")

    assert code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["applied"] is True
    assert report["mode"] == "apply"

    # DB: only the 'new' group survives, and only its rows.
    assert _run_groups(tmp_path) == {"new"}
    assert _artifact_count(tmp_path) == 1

    # On disk: deleted run dirs are gone; kept dir is byte-for-byte intact.
    for d in deleted_dirs:
        assert not d.exists()
    assert kept_dir.exists()
    assert (kept_dir / "artifacts" / "stdout.txt").read_bytes() == kept_bytes

    # gc-report.json is a durable, appendable record of the deletion.
    report_path = tmp_path / "gc-report.json"
    assert report_path.exists()
    document = json.loads(report_path.read_text())
    assert document["report_kind"] == "gc"
    assert len(document["gc_events"]) == 1
    event = document["gc_events"][0]
    assert {e["run_group"] for e in event["deleted_groups"]} == {"old", "mid"}
    assert event["totals"]["runs"] == 2
    # The report records identifying metadata, not resurrectable content.
    for entry in event["deleted_groups"]:
        assert entry["run_ids"]
        assert "rows_by_table" in entry
        assert "stdout" not in json.dumps(entry)  # no artifact bytes leaked

    # VACUUM ran and did not grow the file.
    vacuum = report["vacuum"]
    assert vacuum["ran"] is True
    assert vacuum["db_bytes_after"] <= vacuum["db_bytes_before"]
    assert vacuum["reclaimed_bytes"] >= 0

    assert new_run_id is not None  # sanity: the 'new' group existed pre-gc


def test_apply_run_group_is_idempotent_report_append(tmp_path) -> None:
    _seed_three_groups(tmp_path)

    assert _gc("--db", str(tmp_path / "nlfr.sqlite"), "--run-group", "old", "--apply") == 0
    assert _gc("--db", str(tmp_path / "nlfr.sqlite"), "--run-group", "mid", "--apply") == 0

    assert _run_groups(tmp_path) == {"new"}
    document = json.loads((tmp_path / "gc-report.json").read_text())
    # Two separate gc runs appended two events — the first record was not erased.
    assert len(document["gc_events"]) == 2
    assert {e["deleted_groups"][0]["run_group"] for e in document["gc_events"]} == {
        "old",
        "mid",
    }


# --------------------------------------------------------------------------- guards


def test_last_group_refused_without_allow_empty(tmp_path, capsys) -> None:
    _seed_group(tmp_path, "solo", started_at=datetime.now(UTC) - timedelta(days=1))

    code = _gc("--db", str(tmp_path / "nlfr.sqlite"), "--run-group", "solo", "--apply")

    assert code == 2
    assert "LAST remaining run group" in capsys.readouterr().err
    # Nothing deleted: the solo group and its dir survive.
    assert _run_groups(tmp_path) == {"solo"}
    assert list((tmp_path / "runs").iterdir())


def test_last_group_allowed_with_allow_empty(tmp_path) -> None:
    _seed_group(tmp_path, "solo", started_at=datetime.now(UTC) - timedelta(days=1))

    code = _gc(
        "--db", str(tmp_path / "nlfr.sqlite"),
        "--run-group", "solo",
        "--allow-empty",
        "--apply",
    )

    assert code == 0
    assert _run_groups(tmp_path) == set()
    assert list((tmp_path / "runs").iterdir()) == []


def test_keep_days_deleting_everything_refused_without_allow_empty(tmp_path, capsys) -> None:
    _seed_group(tmp_path, "ancient", started_at=datetime.now(UTC) - timedelta(days=365))

    code = _gc("--db", str(tmp_path / "nlfr.sqlite"), "--keep-days", "30", "--apply")

    assert code == 2
    assert "empty evidence database" in capsys.readouterr().err
    assert _run_groups(tmp_path) == {"ancient"}


def test_combined_selection_modes_exit_2(tmp_path, capsys) -> None:
    _seed_three_groups(tmp_path)

    code = _gc(
        "--db", str(tmp_path / "nlfr.sqlite"),
        "--keep-last", "1",
        "--keep-days", "5",
    )

    assert code == 2
    assert "mutually exclusive" in capsys.readouterr().err
    assert _run_groups(tmp_path) == {"old", "mid", "new"}


def test_no_selection_mode_exit_2(tmp_path, capsys) -> None:
    _seed_three_groups(tmp_path)

    code = _gc("--db", str(tmp_path / "nlfr.sqlite"))

    assert code == 2
    assert "exactly one selection mode" in capsys.readouterr().err


def test_nonexistent_db_exit_2_creates_no_file(tmp_path, capsys) -> None:
    missing = tmp_path / "nope" / "nlfr.sqlite"

    code = _gc("--db", str(missing), "--keep-last", "1")

    assert code == 2
    err = capsys.readouterr().err
    assert "refusing to create one" in err
    assert not missing.exists()
    assert not missing.parent.exists()


def test_old_schema_db_points_at_db_upgrade(tmp_path, capsys) -> None:
    # Build a genuine v1 database (only the first migration), one version behind.
    db_path = tmp_path / "nlfr.sqlite"
    v1_migration = next(m for m in MIGRATIONS if m.version == 1)
    conn = connect(db_path)
    with conn:
        conn.executescript(v1_migration.sql)
        conn.execute("PRAGMA user_version = 1")
    conn.close()

    code = _gc("--db", str(db_path), "--keep-last", "1")

    assert code == 2
    err = capsys.readouterr().err
    assert "schema v1" in err
    assert "nlfr db upgrade" in err


def test_out_of_tree_artifact_refuses_whole_group(tmp_path, capsys) -> None:
    # The evidence store lives in a subdir so 'outside' is genuinely outside its
    # evidence root. Give 'old' an artifact row whose ABSOLUTE path escapes that
    # root; gc must refuse the whole group and delete nothing.
    store = tmp_path / "store"
    store.mkdir()
    outside = tmp_path / "outside" / "evil.txt"
    outside.parent.mkdir(parents=True)
    outside.write_text("not ours to delete\n")

    _seed_group(store, "new", started_at=datetime.now(UTC) - timedelta(days=1))
    _seed_group(
        store,
        "old",
        started_at=datetime.now(UTC) - timedelta(days=100),
        artifact_path_override=str(outside),
    )

    before_ids = _run_ids(store)
    code = _gc("--db", str(store / "nlfr.sqlite"), "--run-group", "old", "--apply")

    assert code == 2
    err = capsys.readouterr().err
    assert "OUTSIDE the evidence root" in err
    assert "refusing" in err.lower()
    # Nothing deleted anywhere, and the out-of-tree file is untouched.
    assert _run_ids(store) == before_ids
    assert outside.exists()
    assert not (store / "gc-report.json").exists()


def test_keep_last_covering_all_is_a_noop(tmp_path, capsys) -> None:
    _seed_three_groups(tmp_path)

    code = _gc("--db", str(tmp_path / "nlfr.sqlite"), "--keep-last", "10", "--apply")

    assert code == 0
    out = capsys.readouterr().out
    assert "nothing to delete" in out
    assert _run_groups(tmp_path) == {"old", "mid", "new"}
    # A no-op apply leaves no gc-report.json (there was no deletion to record).
    assert not (tmp_path / "gc-report.json").exists()


def test_unknown_run_group_exit_2_lists_available(tmp_path, capsys) -> None:
    _seed_three_groups(tmp_path)

    code = _gc("--db", str(tmp_path / "nlfr.sqlite"), "--run-group", "ghost", "--apply")

    assert code == 2
    err = capsys.readouterr().err
    assert "ghost" in err
    assert "old" in err and "mid" in err and "new" in err
    assert _run_groups(tmp_path) == {"old", "mid", "new"}


# ------------------------------------------------ unknown age (C1 doctrine)


def test_keep_last_never_deletes_unknown_age_group(tmp_path, capsys) -> None:
    """The reviewer's C1 repro: an age-unknown group is never auto-deleted.

    record-ancient (400d) + record-recent (1m) + a NULL-age ingest group; with
    ``--keep-last 2 --apply`` the two age-known groups fill the keep slots and the
    NULL-age group is left untouched — NOT ranked as "oldest" and deleted first,
    as the pre-fix code did (silent, exit 0). The plan reports it instead.
    """

    now = datetime.now(UTC)
    _seed_group(tmp_path, "record-ancient", started_at=now - timedelta(days=400))
    _seed_group(tmp_path, "record-recent", started_at=now - timedelta(minutes=1))
    _seed_null_age_group(tmp_path, "ingest-null")

    before_ids = _run_ids(tmp_path)
    before_dirs = sorted(p.name for p in (tmp_path / "runs").iterdir())

    code = _gc(
        "--db", str(tmp_path / "nlfr.sqlite"),
        "--keep-last", "2",
        "--apply",
        "--json",
    )

    assert code == 0
    report = json.loads(capsys.readouterr().out)
    # Nothing deleted: the two age-known groups fill --keep-last 2, and the
    # age-unknown group is never a deletion candidate.
    assert report["deleted_groups"] == []
    assert {e["run_group"] for e in report["kept_groups"]} == {
        "record-ancient",
        "record-recent",
    }
    assert {e["run_group"] for e in report["unknown_age_groups"]} == {"ingest-null"}
    # The whole store survives: rows AND on-disk dirs untouched.
    assert _run_groups(tmp_path) == {"record-ancient", "record-recent", "ingest-null"}
    assert _run_ids(tmp_path) == before_ids
    assert sorted(p.name for p in (tmp_path / "runs").iterdir()) == before_dirs
    # No deletion happened, so no durable gc-report is written.
    assert not (tmp_path / "gc-report.json").exists()


def test_keep_last_plan_note_names_unknown_age_group(tmp_path, capsys) -> None:
    now = datetime.now(UTC)
    _seed_group(tmp_path, "record-ancient", started_at=now - timedelta(days=400))
    _seed_group(tmp_path, "record-recent", started_at=now - timedelta(minutes=1))
    _seed_null_age_group(tmp_path, "ingest-null")

    code = _gc("--db", str(tmp_path / "nlfr.sqlite"), "--keep-last", "2")

    assert code == 0
    out = capsys.readouterr().out
    assert "1 group(s) with unknown age — not auto-selected" in out
    assert "delete explicitly with --run-group" in out
    assert "ingest-null" in out


def test_keep_last_deletes_age_known_and_records_unknown_in_gc_report(
    tmp_path, capsys
) -> None:
    """Age-known groups still garbage-collect while unknown-age is reported, not deleted."""

    now = datetime.now(UTC)
    _seed_group(tmp_path, "old", started_at=now - timedelta(days=100))
    _seed_group(tmp_path, "mid", started_at=now - timedelta(days=10))
    _seed_group(tmp_path, "new", started_at=now - timedelta(days=1))
    _seed_null_age_group(tmp_path, "ingest-null")

    code = _gc(
        "--db", str(tmp_path / "nlfr.sqlite"),
        "--keep-last", "1",
        "--apply",
        "--json",
    )

    assert code == 0
    report = json.loads(capsys.readouterr().out)
    # Only age-known groups are ranked: keep the newest, delete the two older.
    assert {e["run_group"] for e in report["deleted_groups"]} == {"old", "mid"}
    assert {e["run_group"] for e in report["kept_groups"]} == {"new"}
    assert {e["run_group"] for e in report["unknown_age_groups"]} == {"ingest-null"}
    # The age-unknown group survives untouched despite --apply.
    assert _run_groups(tmp_path) == {"new", "ingest-null"}
    # The durable record carries the unknown-age note too.
    document = json.loads((tmp_path / "gc-report.json").read_text())
    event = document["gc_events"][0]
    assert {e["run_group"] for e in event["unknown_age_groups"]} == {"ingest-null"}


def test_keep_days_never_deletes_unknown_age_group(tmp_path, capsys) -> None:
    """keep-days regression pin: a NULL-age group can't be judged old, so it stays.

    Also pins the empty-store guard: deleting every age-known group while an
    age-unknown group remains does NOT trip the "would empty the store" refusal —
    the store is not empty, the unknown-age group is still there.
    """

    now = datetime.now(UTC)
    _seed_group(tmp_path, "ancient", started_at=now - timedelta(days=365))
    _seed_null_age_group(tmp_path, "ingest-null")

    code = _gc(
        "--db", str(tmp_path / "nlfr.sqlite"),
        "--keep-days", "30",
        "--apply",
        "--json",
    )

    assert code == 0
    report = json.loads(capsys.readouterr().out)
    assert {e["run_group"] for e in report["deleted_groups"]} == {"ancient"}
    assert {e["run_group"] for e in report["unknown_age_groups"]} == {"ingest-null"}
    # The age-unknown group remains; the store was not emptied.
    assert _run_groups(tmp_path) == {"ingest-null"}


# ---------------------------------------- VACUUM reclaim accuracy (issue #73)


def test_apply_reports_reclaimed_bytes_matching_real_file_delta(tmp_path, capsys) -> None:
    """`reclaimed_bytes` is the TRUE on-disk delta, not 0-by-construction (#73).

    Pre-fix, ``db_bytes_after`` was ``stat()``'d immediately after ``VACUUM`` with
    no subsequent checkpoint. In WAL mode VACUUM's rewrite lands in the WAL, not
    the main ``.sqlite`` file, so the "after" size read the *pre*-VACUUM size and
    ``reclaimed_bytes`` was always 0 even when real space was freed. This seeds a
    genuinely-shrinking store (a large group deleted, a small one kept), then
    asserts the report's number equals the file size the operator would ``stat``
    the instant the command returns.
    """

    db_path = tmp_path / "nlfr.sqlite"
    # A large group (deleted) and a small one (kept) so the DB genuinely shrinks
    # by more than one page after VACUUM.
    _seed_group(tmp_path, "bulk", started_at=datetime.now(UTC) - timedelta(days=100), n_runs=150)
    _seed_group(tmp_path, "keep", started_at=datetime.now(UTC) - timedelta(days=1), n_runs=2)

    size_before = db_path.stat().st_size
    code = _gc("--db", str(db_path), "--run-group", "bulk", "--apply", "--json")
    size_after = db_path.stat().st_size

    assert code == 0
    report = json.loads(capsys.readouterr().out)
    vacuum = report["vacuum"]

    # The DB really shrank on disk (not just claimed to).
    assert size_after < size_before
    real_delta = size_before - size_after
    assert real_delta > 0

    # The report's numbers ARE the real file sizes/delta — honest, not fabricated.
    assert vacuum["ran"] is True
    assert vacuum["db_bytes_before"] == size_before
    assert vacuum["db_bytes_after"] == size_after
    assert vacuum["reclaimed_bytes"] == real_delta
    assert vacuum["reclaimed_bytes"] > 0  # the specific #73 symptom is gone

    # The durable gc-report.json carries the same honest number.
    event = json.loads((db_path.parent / "gc-report.json").read_text())["gc_events"][0]
    assert event["vacuum"]["reclaimed_bytes"] == real_delta


# ---------------------------------------- guard-rail --json contract (issue #74)
#
# Every guard-rail/usage-error path must emit a structured object on STDOUT under
# --json (mirroring record --json's every-failure-path contract), so a CI-scripted
# retention job reading stdout JSON never gets empty output on a refusal. Exit
# codes are unchanged (still 2); only the OUTPUT SHAPE gains the --json branch.


def _gc_json_reject(capsys, *args: str) -> tuple[int, dict]:
    """Run gc with --json expecting a refusal; return (exit_code, parsed stdout)."""

    code = _gc(*args, "--json")
    out = capsys.readouterr().out
    return code, json.loads(out)


def test_json_reject_nonexistent_db(tmp_path, capsys) -> None:
    missing = tmp_path / "nope" / "nlfr.sqlite"

    code, obj = _gc_json_reject(capsys, "--db", str(missing), "--keep-last", "1")

    assert code == 2
    assert obj["status"] == "db_missing"
    assert obj["exit_code"] == 2
    assert "refusing to create one" in obj["gc_error"]
    assert not missing.exists()  # still creates no file


def test_json_reject_combined_selection_modes(tmp_path, capsys) -> None:
    _seed_three_groups(tmp_path)

    code, obj = _gc_json_reject(
        capsys, "--db", str(tmp_path / "nlfr.sqlite"), "--keep-last", "1", "--keep-days", "5"
    )

    assert code == 2
    assert obj["status"] == "mutually_exclusive_modes"
    assert "mutually exclusive" in obj["gc_error"]


def test_json_reject_no_selection_mode(tmp_path, capsys) -> None:
    _seed_three_groups(tmp_path)

    code, obj = _gc_json_reject(capsys, "--db", str(tmp_path / "nlfr.sqlite"))

    assert code == 2
    assert obj["status"] == "no_selection_mode"


def test_json_reject_last_group_would_empty_store(tmp_path, capsys) -> None:
    _seed_group(tmp_path, "solo", started_at=datetime.now(UTC) - timedelta(days=1))

    code, obj = _gc_json_reject(
        capsys, "--db", str(tmp_path / "nlfr.sqlite"), "--run-group", "solo", "--apply"
    )

    assert code == 2
    assert obj["status"] == "would_empty_store"
    assert "--allow-empty" in obj["gc_error"]
    # Refusal really refused: the group survives.
    assert _run_groups(tmp_path) == {"solo"}


def test_json_reject_unknown_run_group(tmp_path, capsys) -> None:
    _seed_three_groups(tmp_path)

    code, obj = _gc_json_reject(
        capsys, "--db", str(tmp_path / "nlfr.sqlite"), "--run-group", "ghost", "--apply"
    )

    assert code == 2
    assert obj["status"] == "unknown_run_group"
    assert "ghost" in obj["gc_error"]


def test_json_reject_old_schema(tmp_path, capsys) -> None:
    db_path = tmp_path / "nlfr.sqlite"
    v1_migration = next(m for m in MIGRATIONS if m.version == 1)
    conn = connect(db_path)
    with conn:
        conn.executescript(v1_migration.sql)
        conn.execute("PRAGMA user_version = 1")
    conn.close()

    code, obj = _gc_json_reject(capsys, "--db", str(db_path), "--keep-last", "1")

    assert code == 2
    assert obj["status"] == "schema_too_old"
    assert "nlfr db upgrade" in obj["gc_error"]


def test_json_reject_out_of_tree_evidence(tmp_path, capsys) -> None:
    store = tmp_path / "store"
    store.mkdir()
    outside = tmp_path / "outside" / "evil.txt"
    outside.parent.mkdir(parents=True)
    outside.write_text("not ours\n")
    _seed_group(store, "new", started_at=datetime.now(UTC) - timedelta(days=1))
    _seed_group(
        store,
        "old",
        started_at=datetime.now(UTC) - timedelta(days=100),
        artifact_path_override=str(outside),
    )

    code, obj = _gc_json_reject(
        capsys, "--db", str(store / "nlfr.sqlite"), "--run-group", "old", "--apply"
    )

    assert code == 2
    assert obj["status"] == "out_of_tree_evidence"
    assert "OUTSIDE the evidence root" in obj["gc_error"]
    assert outside.exists()  # nothing deleted


def test_text_reject_still_goes_to_stderr_without_json(tmp_path, capsys) -> None:
    # Without --json the guard rails still print human text to stderr (unchanged),
    # and stdout stays empty — no accidental JSON regression on the text path.
    missing = tmp_path / "nope.sqlite"

    code = _gc("--db", str(missing), "--keep-last", "1")

    assert code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "refusing to create one" in captured.err
