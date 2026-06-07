import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "tier1-live-bazel-proof.sh"


def _path_without_bazel(original: str) -> str:
    kept: list[str] = []
    for part in original.split(":"):
        if not part:
            continue
        bindir = Path(part)
        if (bindir / "bazel").is_file() or (bindir / "bazelisk").is_file():
            continue
        kept.append(part)
    return ":".join(kept) if kept else "/usr/bin:/bin:/usr/sbin:/sbin"


@pytest.mark.skipif(
    os.environ.get("NLFR_RUN_TIER1_LIVE_BAZEL") != "1",
    reason="set NLFR_RUN_TIER1_LIVE_BAZEL=1 inside nix develop to run live tier1 acts 1+2",
)
def test_tier1_live_bazel_proof_live():
    result = subprocess.run(
        [str(SCRIPT)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    summary = ROOT / "data" / "tier1-live-bazel" / "summary.json"
    assert summary.is_file()
    payload = json.loads(summary.read_text(encoding="utf-8"))
    assert payload["status"] == "completed"
    assert payload["source_kind"] == "collectable_v1"
    assert payload["validation"] == "bazel"
    assert payload["acts"]["agent-bugfix-1"]["agent_demo"] == "completed"
    assert payload["acts"]["agent-feature-compare"]["agent_demo"] == "completed"


def test_tier1_live_bazel_blocker_without_bazel(tmp_path):
    out = tmp_path / "tier1-live-bazel"
    env = os.environ.copy()
    env["NLFR_TIER1_LIVE_BAZEL_OUTPUT"] = str(out)
    env.pop("NLFR_BAZEL_BIN", None)
    env["PATH"] = _path_without_bazel(env.get("PATH", ""))
    result = subprocess.run(
        [str(SCRIPT)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 2
    blocker = out / "environment-blocker.json"
    assert blocker.is_file()
    payload = json.loads(blocker.read_text(encoding="utf-8"))
    assert payload["status"] == "environment_blocker"
    assert payload["source_kind"] == "collectable_v1"
    assert payload["confidence"] == "high"
    assert payload["redaction_state"] == "safe"
    assert "script:tier1-live-bazel-proof.sh" in payload["evidence_refs"]
    assert payload["scenario_ids"] == ["agent-bugfix-1", "agent-feature-compare"]
    assert "bazel" in payload["reason"].lower()
