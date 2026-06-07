import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from nlfr.db import connect, initialize
from nlfr.projectors import export_action_graph


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


def test_generic_run_records_passing_command(tmp_path: Path) -> None:
    output_dir = tmp_path / "generic-pass"
    result = run_nlfr(
        "run",
        "--mode",
        "generic",
        "--scenario",
        "pass-probe",
        "--run-group",
        "generic-test",
        "--workspace",
        str(ROOT),
        "--output-dir",
        str(output_dir),
        "--command",
        f"{sys.executable} -c \"print('generic-ok')\"",
        "--json",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "completed"
    assert payload["mode"] == "generic"
    assert payload["source_kind"] == "collectable_v1"

    conn = initialize(connect(output_dir / "nlfr.sqlite"))
    runs = conn.execute(
        "SELECT status, mode FROM runs WHERE run_group = ?",
        ("generic-test",),
    ).fetchall()
    assert len(runs) == 1
    assert runs[0]["status"] == "completed"
    assert runs[0]["mode"] == "generic"

    invocations = conn.execute("SELECT COUNT(*) AS count FROM invocations").fetchone()
    assert invocations["count"] == 1

    targets = conn.execute("SELECT COUNT(*) AS count FROM targets").fetchone()
    actions = conn.execute("SELECT COUNT(*) AS count FROM actions").fetchone()
    cache_events = conn.execute("SELECT COUNT(*) AS count FROM cache_events").fetchone()
    assert targets["count"] == 0
    assert actions["count"] == 0
    assert cache_events["count"] == 0

    graph = export_action_graph(conn, run_group="generic-test")
    kinds = {node["kind"] for node in graph["nodes"]}
    assert "run" in kinds
    assert "invocation" in kinds
    assert "artifact" in kinds
    assert "target" not in kinds
    assert "cache_event" not in kinds


def test_generic_run_records_failure_on_nonzero_exit(tmp_path: Path) -> None:
    output_dir = tmp_path / "generic-fail"
    result = run_nlfr(
        "run",
        "--mode",
        "generic",
        "--scenario",
        "fail-probe",
        "--run-group",
        "generic-fail",
        "--workspace",
        str(ROOT),
        "--output-dir",
        str(output_dir),
        "--command",
        f"{sys.executable} -c \"import sys; sys.exit(3)\"",
        "--json",
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "failed"

    conn = initialize(connect(output_dir / "nlfr.sqlite"))
    failures = conn.execute("SELECT failure_kind, message FROM failures").fetchall()
    assert len(failures) == 1
    assert failures[0]["failure_kind"] == "command_exit"


def test_generic_run_idempotent_rerun(tmp_path: Path) -> None:
    output_dir = tmp_path / "generic-idempotent"
    args = [
        "run",
        "--mode",
        "generic",
        "--scenario",
        "idempotent",
        "--run-group",
        "generic-idempotent",
        "--workspace",
        str(ROOT),
        "--output-dir",
        str(output_dir),
        "--command",
        f"{sys.executable} -c \"print(1)\"",
    ]
    first = run_nlfr(*args)
    second = run_nlfr(*args)
    assert first.returncode == 0
    assert second.returncode == 0

    conn = initialize(connect(output_dir / "nlfr.sqlite"))
    count = conn.execute("SELECT COUNT(*) AS count FROM runs").fetchone()["count"]
    assert count == 2


def test_generic_run_records_change_path(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "probe.txt"
    target.write_text("before\n", encoding="utf-8")
    output_dir = tmp_path / "out"

    run_nlfr(
        "run",
        "--mode",
        "generic",
        "--scenario",
        "change-probe",
        "--run-group",
        "generic-change",
        "--workspace",
        str(workspace),
        "--output-dir",
        str(output_dir),
        "--change-path",
        "probe.txt",
        "--command",
        f"{sys.executable} -c \"from pathlib import Path; Path('probe.txt').write_text('after\\\\n')\"",
    )

    conn = initialize(connect(output_dir / "nlfr.sqlite"))
    change = conn.execute(
        "SELECT before_hash, after_hash FROM changes WHERE path = ?",
        ("probe.txt",),
    ).fetchone()
    assert change is not None
    assert change["before_hash"] is not None
    assert change["after_hash"] is not None
    assert change["before_hash"] != change["after_hash"]
