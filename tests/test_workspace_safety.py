"""Workspace-safety + honest-default tests for W1-B (GitHub issue #23).

Covers:
- resolve_workspace() branches a/b/c (explicit wins; source-checkout demo default;
  cwd Bazel marker; hard error).
- nlfr run: --no-remote-cache suppresses remote-cache injection; default-endpoint
  TCP preflight vetoes fail-fast before Bazel; reachable endpoint runs Bazel.
- nlfr doctor --mode local-exec config precedence + nativelink_config_checked.

Real tmp files, real sockets, no mocks of SQLite (existing house style).
"""

import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from nlfr.commands.run_cmd import _endpoint_reachable
from nlfr.config import (
    DEMO_WORKSPACE_NOTICE,
    WorkspaceResolutionError,
    resolve_workspace,
    source_checkout_root,
)


ROOT = Path(__file__).resolve().parents[1]


def run_nlfr(*args: str, cwd: Path | None = None, env_extra: dict | None = None):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-m", "nlfr", *args],
        cwd=str(cwd) if cwd else str(ROOT),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _free_closed_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _bazel_shim(tmp_path: Path) -> Path:
    """An executable stand-in for bazel: records argv + a sentinel, exits 0."""

    shim = tmp_path / "bin" / "bazel"
    shim.parent.mkdir(parents=True, exist_ok=True)
    shim.write_text(
        "#!/usr/bin/env python3\n"
        "import os, sys, pathlib\n"
        "s = os.environ.get('BAZEL_SENTINEL')\n"
        "if s: pathlib.Path(s).write_text('invoked')\n"
        "a = os.environ.get('BAZEL_ARGS_FILE')\n"
        "if a: pathlib.Path(a).write_text(chr(10).join(sys.argv[1:]))\n"
        "sys.exit(0)\n"
    )
    shim.chmod(0o755)
    return shim


# --------------------------------------------------------------------------- #
# resolve_workspace() unit tests — branches a / b / c
# --------------------------------------------------------------------------- #


def test_resolve_workspace_explicit_wins(tmp_path: Path) -> None:
    target = tmp_path / "custom"
    workspace, notice = resolve_workspace(tmp_path, str(target))
    assert workspace == target.resolve()
    assert notice is None


def test_resolve_workspace_source_checkout_uses_demo(tmp_path: Path) -> None:
    root = source_checkout_root()
    assert root is not None, "tests must run from the NLFR source checkout"
    workspace, notice = resolve_workspace(root, None)
    assert workspace == (root / "demo" / "bazel-monorepo").resolve()
    assert notice == DEMO_WORKSPACE_NOTICE


def test_resolve_workspace_marker_uses_cwd(tmp_path: Path, monkeypatch) -> None:
    # Isolate from the real checkout so branch (a) cannot pre-empt branch (b).
    monkeypatch.setattr("nlfr.config.source_checkout_root", lambda: None)
    (tmp_path / "MODULE.bazel").write_text("")
    workspace, notice = resolve_workspace(tmp_path, None)
    assert workspace == tmp_path.resolve()
    assert notice == f"nlfr: using workspace {tmp_path.resolve()}"


@pytest.mark.parametrize("marker", ["MODULE.bazel", "WORKSPACE", "WORKSPACE.bazel"])
def test_resolve_workspace_recognizes_each_marker(tmp_path, monkeypatch, marker) -> None:
    monkeypatch.setattr("nlfr.config.source_checkout_root", lambda: None)
    (tmp_path / marker).write_text("")
    workspace, _ = resolve_workspace(tmp_path, None)
    assert workspace == tmp_path.resolve()


def test_resolve_workspace_no_marker_raises(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("nlfr.config.source_checkout_root", lambda: None)
    with pytest.raises(WorkspaceResolutionError) as exc:
        resolve_workspace(tmp_path, None)
    assert "no Bazel workspace found" in str(exc.value)
    assert str(tmp_path.resolve()) in str(exc.value)


def test_run_without_workspace_outside_repo_exits_2(tmp_path: Path) -> None:
    result = run_nlfr(
        "run",
        "--mode",
        "cache-only",
        "--output-dir",
        str(tmp_path / "out"),
        cwd=tmp_path,
    )
    assert result.returncode == 2
    assert "no Bazel workspace found" in result.stderr
    assert "pass --workspace" in result.stderr
    assert "Traceback" not in result.stderr


def test_run_without_workspace_marker_defaults_to_cwd(tmp_path: Path) -> None:
    (tmp_path / "MODULE.bazel").write_text("")
    result = run_nlfr(
        "run",
        "--mode",
        "cache-only",
        "--skip-nativelink",
        "--no-remote-cache",
        "--bazel-executable",
        "definitely-missing-bazel-for-nlfr",
        "--output-dir",
        str(tmp_path / "out"),
        "--json",
        "//...",
        cwd=tmp_path,
    )
    assert result.returncode == 1  # missing bazel -> honest environment_blocker
    assert f"nlfr: using workspace {tmp_path.resolve()}" in result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "environment_blocker"
    assert payload["workspace"] == str(tmp_path.resolve())


# --------------------------------------------------------------------------- #
# --no-remote-cache flag propagation into the composed Bazel command
# --------------------------------------------------------------------------- #


def _bazel_command_from_run(result: subprocess.CompletedProcess) -> list[str]:
    payload = json.loads(result.stdout)
    bazel = [r for r in payload["results"] if "bazel" in Path(r["command"][0]).name.lower()]
    assert bazel, f"no bazel result in payload: {payload['results']}"
    return bazel[0]["command"]


def test_no_remote_cache_suppresses_injection(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    result = run_nlfr(
        "run",
        "--mode",
        "cache-only",
        "--skip-nativelink",
        "--no-remote-cache",
        "--workspace",
        str(workspace),
        "--bazel-executable",
        "definitely-missing-bazel-for-nlfr",
        "--output-dir",
        str(tmp_path / "out"),
        "--json",
        "//...",
    )
    command = _bazel_command_from_run(result)
    assert not any(arg.startswith("--remote_cache") for arg in command)
    assert not any(arg.startswith("--remote_executor") for arg in command)


def test_explicit_remote_cache_is_injected(tmp_path: Path) -> None:
    # Positive control: an explicit endpoint IS injected (and never preflighted).
    workspace = tmp_path / "ws"
    workspace.mkdir()
    endpoint = "grpc://127.0.0.1:59999"
    result = run_nlfr(
        "run",
        "--mode",
        "cache-only",
        "--skip-nativelink",
        "--remote-cache",
        endpoint,
        "--workspace",
        str(workspace),
        "--bazel-executable",
        "definitely-missing-bazel-for-nlfr",
        "--output-dir",
        str(tmp_path / "out"),
        "--json",
        "//...",
    )
    command = _bazel_command_from_run(result)
    assert f"--remote_cache={endpoint}" in command


# --------------------------------------------------------------------------- #
# Default-endpoint TCP preflight
# --------------------------------------------------------------------------- #


def test_endpoint_reachable_closed_port() -> None:
    port = _free_closed_port()
    assert _endpoint_reachable(f"grpc://127.0.0.1:{port}", timeout=0.5) is False


def test_endpoint_reachable_listening_port() -> None:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    port = sock.getsockname()[1]
    try:
        assert _endpoint_reachable(f"grpc://127.0.0.1:{port}", timeout=0.5) is True
    finally:
        sock.close()


def test_endpoint_reachable_unparseable_returns_true() -> None:
    assert _endpoint_reachable("not-a-real-url") is True


def test_preflight_vetoes_unreachable_default_before_bazel(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    bazel_path = _bazel_shim(tmp_path)  # exists -> counts as "available"
    sentinel = tmp_path / "invoked.txt"
    port = _free_closed_port()
    result = run_nlfr(
        "run",
        "--mode",
        "cache-only",
        "--skip-nativelink",
        "--workspace",
        str(workspace),
        "--bazel-executable",
        str(bazel_path),
        "--output-dir",
        str(tmp_path / "out"),
        "--json",
        "//...",
        env_extra={
            "NLFR_REMOTE_CACHE_DEFAULT": f"grpc://127.0.0.1:{port}",
            "BAZEL_SENTINEL": str(sentinel),
        },
    )
    assert result.returncode == 2
    assert "unreachable" in result.stderr
    assert str(port) in result.stderr
    assert "--no-remote-cache" in result.stderr
    assert not sentinel.exists(), "bazel must not run when the preflight vetoes"


def test_preflight_allows_reachable_default(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    bazel_path = _bazel_shim(tmp_path)
    sentinel = tmp_path / "invoked.txt"
    args_file = tmp_path / "args.txt"
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]
    try:
        result = run_nlfr(
            "run",
            "--mode",
            "cache-only",
            "--skip-nativelink",
            "--workspace",
            str(workspace),
            "--bazel-executable",
            str(bazel_path),
            "--output-dir",
            str(tmp_path / "out"),
            "--json",
            "//...",
            env_extra={
                "NLFR_REMOTE_CACHE_DEFAULT": f"grpc://127.0.0.1:{port}",
                "BAZEL_SENTINEL": str(sentinel),
                "BAZEL_ARGS_FILE": str(args_file),
            },
        )
    finally:
        listener.close()
    assert result.returncode == 0, result.stderr
    assert sentinel.exists(), "reachable default endpoint should let bazel run"
    recorded = args_file.read_text().splitlines()
    assert f"--remote_cache=grpc://127.0.0.1:{port}" in recorded


# --------------------------------------------------------------------------- #
# doctor --mode local-exec config precedence + nativelink_config_checked
# --------------------------------------------------------------------------- #


def _doctor_local_exec(*args: str, cwd: Path | None = None) -> dict:
    result = run_nlfr("doctor", "--mode", "local-exec", "--json", *args, cwd=cwd)
    return json.loads(result.stdout)


def _write_nlfr_toml(workspace: Path, nativelink_config: str) -> None:
    (workspace / "nlfr.toml").write_text(
        "[nlfr]\n"
        "version = 1\n"
        "\n"
        "[nlfr.defaults]\n"
        f'nativelink_config = "{nativelink_config}"\n'
    )


def test_doctor_flag_nonexistent_reports_honest_failure(tmp_path: Path) -> None:
    missing = tmp_path / "nope.json5"
    payload = _doctor_local_exec("--nativelink-config", str(missing))
    assert payload["nativelink_config_checked"] == str(missing)
    check = next(c for c in payload["checks"] if c["name"] == "local-exec-config")
    assert check["ok"] is False
    assert str(missing) in check["detail"]


def test_doctor_flag_beats_toml(tmp_path: Path) -> None:
    _write_nlfr_toml(tmp_path, "from-toml.json5")
    flag = tmp_path / "from-flag.json5"
    payload = _doctor_local_exec("--workspace", str(tmp_path), "--nativelink-config", str(flag))
    assert payload["nativelink_config_checked"] == str(flag)


def test_doctor_toml_beats_demo_default(tmp_path: Path) -> None:
    _write_nlfr_toml(tmp_path, "workspace-nl.json5")
    payload = _doctor_local_exec("--workspace", str(tmp_path))
    checked = payload["nativelink_config_checked"]
    assert checked == str(tmp_path / "workspace-nl.json5")
    assert "local-execution.json5" not in checked  # not the bundled demo


def test_doctor_no_config_outside_checkout_is_honest_failure(tmp_path: Path) -> None:
    payload = _doctor_local_exec("--workspace", str(tmp_path))
    assert payload["nativelink_config_checked"] is None
    check = next(c for c in payload["checks"] if c["name"] == "local-exec-config")
    assert check["ok"] is False
    assert "no NativeLink local-execution config found" in check["detail"]


def test_doctor_demo_default_inside_checkout_reports_path() -> None:
    # Run from the source checkout with no flag/toml -> bundled demo config.
    payload = _doctor_local_exec(cwd=ROOT)
    checked = payload["nativelink_config_checked"]
    assert checked is not None
    assert checked.endswith("demo/nativelink/local-execution.json5")
