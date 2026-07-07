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


def _write_sidecar(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "schema_version": "nlfr.agent_provenance.sidecar.v1",
                "adapter": "test-record-agent-change",
                "agent": {
                    "kind": "cursor_adapter_v1",
                    "name": "test-cursor-agent",
                    "model": "composer-2.5",
                    "prompt_sha256": "abc123" * 10 + "abcd",
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _run_generic_with_change(
    tmp_path: Path,
    *,
    change_path: str,
    command: str,
    seed: dict[str, str] | None = None,
) -> tuple[subprocess.CompletedProcess[str], dict, Path]:
    """Run generic mode with an agent sidecar and return (result, provenance, out).

    ``seed`` maps workspace-relative paths to initial contents written before the
    run, so before/after hashes can be exercised across identical / edited /
    appeared / deleted / never-observed states.
    """

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    for rel, contents in (seed or {}).items():
        (workspace / rel).write_text(contents, encoding="utf-8")
    sidecar = _write_sidecar(tmp_path / "sidecar.json")
    output_dir = tmp_path / "out"

    result = run_nlfr(
        "run",
        "--mode",
        "generic",
        "--scenario",
        "patch-derive-probe",
        "--run-group",
        "patch-derive",
        "--workspace",
        str(workspace),
        "--output-dir",
        str(output_dir),
        "--change-path",
        change_path,
        "--provenance-sidecar",
        str(sidecar),
        "--command",
        command,
        "--json",
    )
    payload = json.loads(result.stdout)
    provenance = json.loads(
        (Path(payload["artifact_root"]) / "agent-provenance.json").read_text()
    )
    return result, provenance, output_dir


def test_patch_applied_false_on_identical_hash(tmp_path: Path) -> None:
    result, provenance, _ = _run_generic_with_change(
        tmp_path,
        change_path="stable.txt",
        command="true",
        seed={"stable.txt": "unchanged\n"},
    )

    assert result.returncode == 0, result.stderr
    change = provenance["change"]
    assert change["patch_applied"] is False
    assert change["paths"]["stable.txt"]["changed"] is False
    assert (
        change["paths"]["stable.txt"]["before_sha256"]
        == change["paths"]["stable.txt"]["after_sha256"]
    )


def test_patch_applied_true_on_edited_file(tmp_path: Path) -> None:
    command = (
        f"{sys.executable} -c "
        "\"from pathlib import Path; Path('edit.txt').write_text('after\\\\n')\""
    )
    result, provenance, _ = _run_generic_with_change(
        tmp_path,
        change_path="edit.txt",
        command=command,
        seed={"edit.txt": "before\n"},
    )

    assert result.returncode == 0, result.stderr
    change = provenance["change"]
    assert change["patch_applied"] is True
    assert change["paths"]["edit.txt"]["changed"] is True
    assert (
        change["paths"]["edit.txt"]["before_sha256"]
        != change["paths"]["edit.txt"]["after_sha256"]
    )


def test_patch_applied_true_on_appeared_file(tmp_path: Path) -> None:
    command = (
        f"{sys.executable} -c "
        "\"from pathlib import Path; Path('appeared.txt').write_text('new\\\\n')\""
    )
    result, provenance, _ = _run_generic_with_change(
        tmp_path,
        change_path="appeared.txt",
        command=command,
    )

    assert result.returncode == 0, result.stderr
    change = provenance["change"]
    assert change["paths"]["appeared.txt"]["before_sha256"] is None
    assert change["paths"]["appeared.txt"]["after_sha256"] is not None
    assert change["paths"]["appeared.txt"]["changed"] is True
    assert change["patch_applied"] is True


def test_patch_applied_true_on_deleted_file(tmp_path: Path) -> None:
    command = (
        f"{sys.executable} -c "
        "\"from pathlib import Path; Path('gone.txt').unlink()\""
    )
    result, provenance, _ = _run_generic_with_change(
        tmp_path,
        change_path="gone.txt",
        command=command,
        seed={"gone.txt": "doomed\n"},
    )

    assert result.returncode == 0, result.stderr
    change = provenance["change"]
    assert change["paths"]["gone.txt"]["before_sha256"] is not None
    assert change["paths"]["gone.txt"]["after_sha256"] is None
    assert change["paths"]["gone.txt"]["changed"] is True
    assert change["patch_applied"] is True


def test_change_path_never_observed_completes_with_note_and_warning(
    tmp_path: Path,
) -> None:
    result, provenance, output_dir = _run_generic_with_change(
        tmp_path,
        change_path="typo-does-not-exist.txt",
        command="true",
    )

    # The run must COMPLETE — recording an attempt honestly is valid — but the
    # evidence must say the path was never seen, and stderr must name it.
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "completed"
    assert "typo-does-not-exist.txt" in result.stderr
    assert "never observed on disk" in result.stderr

    change = provenance["change"]
    entry = change["paths"]["typo-does-not-exist.txt"]
    assert entry["before_sha256"] is None
    assert entry["after_sha256"] is None
    assert entry["changed"] is False
    assert entry["note"] == "path never observed on disk"
    assert change["patch_applied"] is False

    conn = initialize(connect(output_dir / "nlfr.sqlite"))
    run = conn.execute(
        "SELECT status FROM runs WHERE run_group = ?", ("patch-derive",)
    ).fetchone()
    assert run["status"] == "completed"


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
