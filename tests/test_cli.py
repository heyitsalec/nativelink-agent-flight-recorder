import os
import json
import sqlite3
import subprocess
import sys
import tomllib
from pathlib import Path


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


def test_module_help_lists_registered_commands() -> None:
    result = run_nlfr("--help")

    assert result.returncode == 0
    assert "NativeLink Agent Flight Recorder" in result.stdout
    for command in (
        "init",
        "doctor",
        "run",
        "ingest",
        "graph",
        "runway",
        "proof",
        "compare",
        "serve",
        "simulate",
    ):
        assert command in result.stdout


def test_unknown_command_returns_argparse_error() -> None:
    result = run_nlfr("bogus")

    assert result.returncode == 2
    assert "invalid choice" in result.stderr
    assert "bogus" in result.stderr
    assert "Traceback" not in result.stderr


def test_script_entrypoint_resolves_to_cli_main() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())

    assert pyproject["project"]["scripts"]["nlfr"] == "nlfr.cli:main"

    from nlfr.cli import main

    assert callable(main)


def test_doctor_local_exec_reports_config_and_tool_checks() -> None:
    result = run_nlfr("doctor", "--mode", "local-exec", "--json")

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    checks = {check["name"]: check for check in payload["checks"]}

    assert payload["mode"] == "local-exec"
    assert checks["python"]["ok"] is True
    assert checks["local-exec-config"]["ok"] is True
    assert "local-execution.json5" in checks["local-exec-config"]["detail"]
    assert "execution" in checks["local-exec-config"]["detail"]
    assert "worker_api" in checks["local-exec-config"]["detail"]
    assert isinstance(checks["bazel"]["ok"], bool)
    assert checks["bazel"]["detail"]
    assert isinstance(checks["nativelink"]["ok"], bool)
    assert checks["nativelink"]["detail"]


def test_run_records_environment_blockers_as_artifacts(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    output_dir = tmp_path / "nlfr-data"

    result = run_nlfr(
        "run",
        "--scenario",
        "agent-loop",
        "--workspace",
        str(workspace),
        "--output-dir",
        str(output_dir),
        "--nativelink-executable",
        "definitely-missing-nativelink-for-nlfr",
        "--bazel-executable",
        "definitely-missing-bazel-for-nlfr",
        "--json",
        "//tasks:priority_test",
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "environment_blocker"
    assert {item["status"] for item in payload["results"]} == {"environment_blocker"}

    artifact_root = Path(payload["artifact_root"])
    assert (artifact_root / "artifact_manifest.json").exists()
    assert (artifact_root / "run.json").exists()
    assert (artifact_root / "nativelink.stderr.txt").exists()
    assert (artifact_root / "bazel.stderr.txt").exists()

    with sqlite3.connect(output_dir / "nlfr.sqlite") as conn:
        conn.row_factory = sqlite3.Row
        run_row = conn.execute("SELECT status FROM runs").fetchone()
        artifact_count = conn.execute("SELECT COUNT(*) AS count FROM artifacts").fetchone()

    assert run_row["status"] == "environment_blocker"
    assert artifact_count["count"] >= 3


def test_local_exec_run_records_environment_blocker_with_executor_metadata(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    output_dir = tmp_path / "nlfr-data"

    result = run_nlfr(
        "run",
        "--scenario",
        "local-exec-check",
        "--mode",
        "local-exec",
        "--workspace",
        str(workspace),
        "--output-dir",
        str(output_dir),
        "--nativelink-executable",
        "definitely-missing-nativelink-for-nlfr",
        "--bazel-executable",
        "definitely-missing-bazel-for-nlfr",
        "--bazel-arg=--config=lre",
        "--bazel-arg=--remote_default_exec_properties=cpu_count=1",
        "--json",
        "//tasks:priority_test",
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "environment_blocker"
    assert payload["mode"] == "local-exec"
    assert payload["nativelink_config"].endswith("local-execution.json5")
    assert payload["bazel_args"] == [
        "--config=lre",
        "--remote_default_exec_properties=cpu_count=1",
    ]
    bazel_result = next(
        item
        for item in payload["results"]
        if item["command"][0] == "definitely-missing-bazel-for-nlfr"
    )
    assert "--remote_executor=grpc://127.0.0.1:50051" in bazel_result["command"]
    assert bazel_result["command"][-2:] == payload["bazel_args"]
