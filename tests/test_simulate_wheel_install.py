"""End-to-end proof that ``nlfr simulate`` works from a BUILT wheel (issue #94).

This reproduces the exact air-gapped adopter journey: build the wheel, install it
into a fresh venv with no source checkout on the path, then resolve and run the
demo scenarios from a bare directory. It is heavy (a real ``uv build`` plus a
fresh venv), so it is gated behind ``NLFR_WHEEL_TEST=1`` to keep unit CI fast; the
fast resolution-order coverage lives in ``test_simulate_resources.py``.

Run it explicitly with::

    NLFR_WHEEL_TEST=1 uv run pytest -q tests/test_simulate_wheel_install.py
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from shutil import which

import pytest


ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(
    not os.environ.get("NLFR_WHEEL_TEST"),
    reason="heavy: builds a wheel and a fresh venv; set NLFR_WHEEL_TEST=1 to run",
)


def _run(*cmd: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(cmd),
        cwd=str(cwd) if cwd else None,
        check=True,
        capture_output=True,
        text=True,
    )


def test_simulate_resolves_and_runs_packaged_scenarios_from_installed_wheel(tmp_path) -> None:
    uv = which("uv")
    if uv is None:
        pytest.skip("uv is not on PATH")

    # 1. Build the wheel (force-includes demo fixtures into nlfr/data/).
    dist = tmp_path / "dist"
    _run(uv, "build", "--out-dir", str(dist), cwd=ROOT)
    wheels = list(dist.glob("*.whl"))
    assert wheels, "uv build produced no wheel"
    wheel = wheels[0]

    # 2. Install into a fresh venv with NO source checkout on the path.
    #    sys.executable is >=3.11 (project requires-python), a valid target.
    venv = tmp_path / "venv"
    _run(sys.executable, "-m", "venv", str(venv))
    venv_python = venv / "bin" / "python"
    nlfr = venv / "bin" / "nlfr"
    # --no-index proves the offline install claim: zero runtime deps to fetch.
    _run(str(venv_python), "-m", "pip", "install", "--no-index", str(wheel))

    baredir = tmp_path / "bare"
    baredir.mkdir()

    # 3. --list resolves scenarios from the PACKAGED location, not a checkout.
    listed = _run(str(nlfr), "simulate", "--list", "--json", cwd=baredir)
    payload = json.loads(listed.stdout)
    assert payload["resolved_from"] == "packaged"
    assert "site-packages" in payload["scenario_dir"]
    assert "safe-leaf-change" in payload["scenarios"]

    # 4. A full scenario run works end-to-end from the bare dir: the packaged
    #    demo workspace is used, the patch applies, provenance is recorded.
    run = _run(
        str(nlfr),
        "simulate",
        "--scenario",
        "safe-leaf-change",
        "--skip-run",
        "--output-dir",
        str(baredir / "out"),
        "--json",
        cwd=baredir,
    )
    result = json.loads(run.stdout)
    scenario = result["scenarios"][0]
    assert scenario["scenario_id"] == "safe-leaf-change"
    assert scenario["build"]["status"] == "simulated_only"
    assert Path(scenario["provenance_path"]).exists()
