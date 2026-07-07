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
        "redact",
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

    payload = json.loads(result.stdout)
    # Return code tracks overall readiness: 0 when every check passes (e.g.
    # inside nix develop with Bazel + NativeLink present), 1 when a tool is
    # absent. Both are valid; assert the code is consistent with the payload.
    assert result.returncode == (0 if payload["ok"] else 1)
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


def test_redact_command_scrubs_local_paths_to_output(tmp_path) -> None:
    """`nlfr redact INPUT OUTPUT` ships the module's redaction in the wheel."""
    source = tmp_path / "raw.json"
    dest = tmp_path / "out.json"
    source.write_text(
        json.dumps({"artifact_root": "/Users/example/proj/data/run/artifacts"}),
        encoding="utf-8",
    )
    result = run_nlfr("redact", str(source), str(dest))

    assert result.returncode == 0, result.stderr
    payload = json.loads(dest.read_text(encoding="utf-8"))
    assert "/Users/example" not in json.dumps(payload)


def test_redact_check_flags_findings_with_nonzero_exit(tmp_path) -> None:
    source = tmp_path / "raw.json"
    source.write_text(json.dumps({"home": "/Users/example/x/y"}), encoding="utf-8")
    result = run_nlfr("redact", "--check", str(source))

    assert result.returncode == 1
    assert "finding" in result.stderr
    # --check writes nothing.
    assert list(tmp_path.glob("*.out")) == []


def test_redact_check_clean_input_exits_zero(tmp_path) -> None:
    source = tmp_path / "clean.json"
    source.write_text(json.dumps({"label": "//tasks:x", "kind": "run"}), encoding="utf-8")
    result = run_nlfr("redact", "--check", str(source))

    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


def test_redact_help_available_from_packaged_module_entrypoint() -> None:
    # Packaging smoke: `nlfr redact` is reachable through the same `python -m
    # nlfr` entry point the wheel installs. No wheel-build test exists in this
    # repo, so this asserts the command is registered and its help renders.
    result = run_nlfr("redact", "--help")
    assert result.returncode == 0
    assert "redact" in result.stdout
    assert "--check" in result.stdout
