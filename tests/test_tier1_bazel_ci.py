import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "tier1-bazel-ci-proof.sh"


@pytest.mark.skipif(
    os.environ.get("NLFR_RUN_BAZEL_CI") != "1",
    reason="set NLFR_RUN_BAZEL_CI=1 inside nix develop to run live Bazel tier1 proof",
)
def test_tier1_bazel_ci_proof_live():
    result = subprocess.run(
        [str(SCRIPT)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    summary = ROOT / "data" / "tier1-bazel-ci" / "summary.json"
    assert summary.is_file()
    payload = json.loads(summary.read_text(encoding="utf-8"))
    assert payload["status"] == "completed"
    assert payload["source_kind"] == "collectable_v1"
    assert payload["acts"]["agent-bugfix-1"]["bazel_test"] == "passed"


def test_tier1_bazel_ci_blocker_without_bazel(tmp_path, monkeypatch):
    out = tmp_path / "tier1-bazel-ci"
    monkeypatch.setenv("NLFR_TIER1_BAZEL_OUTPUT", str(out))
    monkeypatch.setenv("NLFR_BAZEL_BIN", str(tmp_path / "no-bazel-here"))
    result = subprocess.run(
        [str(SCRIPT)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 2
    blocker = out / "environment-blocker.json"
    assert blocker.is_file()
