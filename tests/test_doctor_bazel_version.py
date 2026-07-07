"""`nlfr doctor` out-of-range Bazel version warning (GitHub issue #85).

Doctor emits a NON-BLOCKING "untested Bazel version" signal when the local Bazel
major is outside NLFR's tested anchors (7.x / 9.x). These tests drive the real
detection path with a fake ``bazel`` shim on PATH (so ``bazel version`` is a real
subprocess), and pin the two honesty invariants:

* the warning is advisory — it appears in text (stderr) and JSON but NEVER
  changes doctor's exit code or the JSON ``ok`` field (those reflect the required
  tool checks only);
* an unknown/dev version (no ``Build label``) stays silent — NLFR never
  fabricates an "untested" claim from a version it could not read.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _write_bazel_shim(bin_dir: Path, version_output: str) -> None:
    """Create an executable fake ``bazel`` that prints ``version_output`` for `version`."""

    bin_dir.mkdir(parents=True, exist_ok=True)
    shim = bin_dir / "bazel"
    shim.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        f"OUT = {version_output!r}\n"
        "if len(sys.argv) > 1 and sys.argv[1] == 'version':\n"
        "    sys.stdout.write(OUT)\n"
        "    sys.exit(0)\n"
        "sys.exit(0)\n",
        encoding="utf-8",
    )
    shim.chmod(0o755)


def _run_doctor(bin_dir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
    return subprocess.run(
        [sys.executable, "-m", "nlfr", "doctor", "--mode", "cache-only", *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_out_of_range_version_warns_but_stays_exit_honest(tmp_path: Path) -> None:
    _write_bazel_shim(tmp_path / "bin", "Build label: 8.2.1\n")

    result = _run_doctor(tmp_path / "bin", "--json")
    payload = json.loads(result.stdout)

    bv = payload["bazel_version"]
    assert bv["detected"] == "8.2.1"
    assert bv["major"] == 8
    assert bv["in_tested_range"] is False
    assert bv["warning"] is not None and "8.2.1" in bv["warning"]
    assert bv["tested_versions"] == ["7.4.1", "9.0.0"]

    # Exit code and ``ok`` reflect the required checks ONLY — the advisory version
    # warning never flips them. Here bazel is present (shim) so ``ok`` follows the
    # remaining checks; the exit code must equal that, not be forced by the warning.
    assert result.returncode == (0 if payload["ok"] else 1)
    # bazel itself was detected as present, so it is not the reason for any failure.
    bazel_check = next(c for c in payload["checks"] if c["name"] == "bazel")
    assert bazel_check["ok"] is True


def test_out_of_range_warning_on_stderr_in_text_mode(tmp_path: Path) -> None:
    _write_bazel_shim(tmp_path / "bin", "Build label: 6.5.0\n")

    result = _run_doctor(tmp_path / "bin")
    assert "[warn]" in result.stderr
    assert "6.5.0" in result.stderr
    assert "tested version anchors" in result.stderr
    # The version line is informational on stdout; the warning is advisory stderr.
    assert "UNTESTED anchor" in result.stdout


@pytest.mark.parametrize("anchor", ["7.4.1", "9.0.0"])
def test_tested_anchor_version_emits_no_warning(tmp_path: Path, anchor: str) -> None:
    _write_bazel_shim(tmp_path / "bin", f"Build label: {anchor}\n")

    result = _run_doctor(tmp_path / "bin", "--json")
    bv = json.loads(result.stdout)["bazel_version"]
    assert bv["detected"] == anchor
    assert bv["in_tested_range"] is True
    assert bv["warning"] is None
    assert "[warn]" not in result.stderr


def test_dev_build_without_release_label_stays_silent(tmp_path: Path) -> None:
    # A source/dev Bazel prints an empty Build label; NLFR records the version as
    # unknown and emits no out-of-range warning (never fabricates one).
    _write_bazel_shim(tmp_path / "bin", "Build label: \nBuild time: no_stamp\n")

    result = _run_doctor(tmp_path / "bin", "--json")
    bv = json.loads(result.stdout)["bazel_version"]
    assert bv["detected"] is None
    assert bv["warning"] is None
    assert bv["in_tested_range"] is False
    assert "[warn]" not in result.stderr
