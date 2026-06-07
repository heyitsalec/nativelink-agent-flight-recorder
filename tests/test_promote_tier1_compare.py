import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "promote-tier1-compare.sh"
COMPARE_SRC = (
    ROOT / "data" / "compare-agent-runs" / "projections" / "compare-canvas-dev-vs-agent-bugfix-1.json"
)


def test_promote_tier1_compare_dry_run():
    if not COMPARE_SRC.is_file():
        subprocess.run(["./scripts/compare-agent-runs.sh"], cwd=ROOT, check=True)
    result = subprocess.run(
        [str(SCRIPT), "--dry-run"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "dry-run ok" in result.stdout


def test_promote_tier1_compare_writes_public_projection(tmp_path, monkeypatch):
    if not COMPARE_SRC.is_file():
        subprocess.run(["./scripts/compare-agent-runs.sh"], cwd=ROOT, check=True)
    dest = tmp_path / "compare-projection.json"
    monkeypatch.setenv("NLFR_COMPARE_AGENT_OUTPUT", str(ROOT / "data" / "compare-agent-runs"))
    subprocess.run([str(SCRIPT)], cwd=ROOT, check=True)
    public = ROOT / "apps" / "canvas" / "public" / "projections" / "compare-projection.json"
    assert public.is_file()
    payload = json.loads(public.read_text(encoding="utf-8"))
    assert payload["projection_kind"] == "compare"
