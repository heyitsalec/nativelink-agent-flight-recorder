"""`nlfr record` out-of-range Bazel version warning (GitHub issue #85).

``nlfr record`` warns when the Bazel that produced the evidence reports a major
outside NLFR's tested matrix anchors. Unlike ``doctor`` (which shells out to
``bazel version`` on the local env), ``record`` reads the version from the
INGESTED BEP's own ``started.buildToolVersion`` — the honest, evidence-backed
version. The warning is advisory: it never changes record's exit code (which
mirrors Bazel's) and never alters the recorded evidence.

These tests drive record end-to-end through a fake ``bazel`` shim that emits a
chosen BEP (``NLFR_CANNED_BEP``); the out-of-range BEP is a transient warning-
logic test input, NOT a committed version-coverage fixture.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _write_bazel_shim(bin_dir: Path) -> Path:
    """A fake ``bazel`` that copies NLFR_CANNED_BEP to the injected BEP path."""

    bin_dir.mkdir(parents=True, exist_ok=True)
    shim = bin_dir / "bazel"
    shim.write_text(
        "#!/usr/bin/env python3\n"
        "import os, shutil, sys\n"
        "args = sys.argv[1:]\n"
        "flag = '--build_event_json_file'\n"
        "bep = None\n"
        "for i, a in enumerate(args):\n"
        "    if a.startswith(flag + '='):\n"
        "        bep = a.split('=', 1)[1]\n"
        "    elif a == flag and i + 1 < len(args):\n"
        "        bep = args[i + 1]\n"
        "assert bep is not None, f'no BEP flag in {args}'\n"
        "shutil.copyfile(os.environ['NLFR_CANNED_BEP'], bep)\n"
        "sys.stdout.write('fake bazel ran\\n')\n"
        "sys.exit(0)\n",
        encoding="utf-8",
    )
    shim.chmod(0o755)
    return bin_dir


def _bep_with_version(path: Path, version: str | None) -> Path:
    started: dict = {"command": "test", "startTimeMillis": 1710000000000}
    if version is not None:
        started["buildToolVersion"] = version
    lines = [
        {"id": {"started": {}}, "started": started},
        {"id": {"buildFinished": {}}, "finished": {"exitCode": {"name": "SUCCESS", "code": 0}}},
    ]
    path.write_text("\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8")
    return path


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    (workspace / "MODULE.bazel").write_text('module(name = "demo")\n', encoding="utf-8")
    return workspace


def _run_record(*args: str, cwd: Path, bin_dir: Path, canned_bep: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    env["NLFR_CANNED_BEP"] = str(canned_bep)
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
    return subprocess.run(
        [sys.executable, "-m", "nlfr", "record", *args],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_record_warns_on_out_of_range_bazel_version(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    bin_dir = _write_bazel_shim(tmp_path / "bin")
    canned = _bep_with_version(tmp_path / "out-of-range.bep.jsonl", "8.0.0")

    result = _run_record(
        "--run-group", "rec-ver", "--json",
        "--", "bazel", "test", "//app:widget_test",
        cwd=workspace, bin_dir=bin_dir, canned_bep=canned,
    )

    # Exit code mirrors Bazel (success) — the version warning is non-blocking.
    assert result.returncode == 0, result.stderr
    assert "nlfr record:" in result.stderr
    assert "8.0.0" in result.stderr
    assert "tested version anchors" in result.stderr

    payload = json.loads(result.stdout)
    assert payload["bazel_version"] == "8.0.0"
    assert payload["bazel_version_warning"] is not None
    assert "8.0.0" in payload["bazel_version_warning"]


def test_record_no_warning_on_tested_anchor_version(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    bin_dir = _write_bazel_shim(tmp_path / "bin")
    canned = _bep_with_version(tmp_path / "anchor.bep.jsonl", "7.4.1")

    result = _run_record(
        "--run-group", "rec-anchor", "--json",
        "--", "bazel", "test", "//app:widget_test",
        cwd=workspace, bin_dir=bin_dir, canned_bep=canned,
    )

    assert result.returncode == 0, result.stderr
    assert "tested version anchors" not in result.stderr
    payload = json.loads(result.stdout)
    assert payload["bazel_version"] == "7.4.1"
    assert payload["bazel_version_warning"] is None


def test_record_silent_when_bep_declares_no_version(tmp_path: Path) -> None:
    # No buildToolVersion in the BEP -> version unknown -> no fabricated warning.
    workspace = _workspace(tmp_path)
    bin_dir = _write_bazel_shim(tmp_path / "bin")
    canned = _bep_with_version(tmp_path / "noversion.bep.jsonl", None)

    result = _run_record(
        "--run-group", "rec-nover", "--json",
        "--", "bazel", "test", "//app:widget_test",
        cwd=workspace, bin_dir=bin_dir, canned_bep=canned,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["bazel_version"] is None
    assert payload["bazel_version_warning"] is None
    assert "tested version anchors" not in result.stderr
