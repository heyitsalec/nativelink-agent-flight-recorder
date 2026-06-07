import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

from nlfr.config import load_defaults, resolve_defaults, scaffold_workspace


ROOT = Path(__file__).resolve().parents[1]


def run_nlfr(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "nlfr", *args],
        cwd=cwd or ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_init_creates_nlfr_toml_and_marker_dir(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    workspace.mkdir()
    (workspace / "demo" / "bazel-monorepo").mkdir(parents=True)

    result = run_nlfr("init", "--cwd", str(workspace))

    assert result.returncode == 0
    assert "scaffold created" in result.stdout
    assert (workspace / "nlfr.toml").exists()
    assert (workspace / "data" / ".nlfr" / "init.json").exists()
    assert (workspace / "data" / "nlfr").is_dir()

    payload = tomllib.loads((workspace / "nlfr.toml").read_text())
    defaults = payload["nlfr"]["defaults"]
    assert defaults["workspace"] == "demo/bazel-monorepo"
    assert defaults["output_dir"] == "data/nlfr"
    assert defaults["database"] == "data/nlfr/nlfr.sqlite"
    assert defaults["run_group"] == "latest"


def test_init_is_idempotent(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    workspace.mkdir()

    first = run_nlfr("init", "--cwd", str(workspace), "--json")
    second = run_nlfr("init", "--cwd", str(workspace), "--json")

    assert first.returncode == 0
    assert second.returncode == 0

    first_payload = json.loads(first.stdout)
    second_payload = json.loads(second.stdout)

    assert first_payload["idempotent"] is False
    assert second_payload["idempotent"] is True
    assert second_payload["created"] == []
    assert (workspace / "nlfr.toml").read_text() == (workspace / "nlfr.toml").read_text()


def test_init_json_output_reports_paths(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    workspace.mkdir()

    result = run_nlfr(
        "init",
        "--cwd",
        str(workspace),
        "--workspace",
        "services/build",
        "--output-dir",
        "data/custom",
        "--database",
        "data/custom/recorder.sqlite",
        "--run-group",
        "adopted",
        "--json",
    )

    payload = json.loads(result.stdout)
    assert payload["defaults"] == {
        "workspace": "services/build",
        "output_dir": "data/custom",
        "database": "data/custom/recorder.sqlite",
        "run_group": "adopted",
    }
    assert payload["paths"]["config"] == "nlfr.toml"
    assert payload["paths"]["marker_dir"] == "data/.nlfr"
    assert payload["paths"]["database"] == "data/custom/recorder.sqlite"


def test_scaffold_workspace_unit_idempotent(tmp_path: Path) -> None:
    defaults = resolve_defaults(
        tmp_path,
        workspace=".",
        output_dir="data/nlfr",
        database="data/nlfr/nlfr.sqlite",
        run_group="latest",
    )

    first = scaffold_workspace(tmp_path, defaults)
    second = scaffold_workspace(tmp_path, defaults)

    assert first["idempotent"] is False
    assert second["idempotent"] is True
    assert load_defaults(tmp_path) == defaults


def test_init_help_lists_workspace_flags() -> None:
    result = run_nlfr("init", "--help")

    assert result.returncode == 0
    for flag in ("--workspace", "--output-dir", "--database", "--run-group", "--json"):
        assert flag in result.stdout
