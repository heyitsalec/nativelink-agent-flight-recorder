import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "promote-tier1-compare.sh"

# Hermetic compare source. promote-tier1-compare.sh reads
# $NLFR_COMPARE_AGENT_OUTPUT/projections/compare-<pair>.json (default pair:
# canvas-dev-vs-agent-bugfix-1). On a clean checkout the live rollup under
# data/compare-agent-runs does not exist -- building it needs the canvas-dev
# SQLite DB, produced by record-canvas-build.sh via tsc/Node, which is absent
# without apps/canvas/node_modules. Point the promote script at a committed
# fixture instead so these tests exercise it without the recording pipeline.
#
# The fixture is kept byte-identical to apps/canvas/public/projections/
# compare-projection.json (the genuine promoted artifact for this pair), so the
# writes test copies it straight back to that tracked path with no working-tree
# churn. If you regenerate the public projection, refresh this fixture too.
COMPARE_FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "compare-agent-runs"
PUBLIC_PROJECTION = ROOT / "apps" / "canvas" / "public" / "projections" / "compare-projection.json"


def test_promote_tier1_compare_dry_run(monkeypatch):
    monkeypatch.setenv("NLFR_COMPARE_AGENT_OUTPUT", str(COMPARE_FIXTURE_ROOT))
    result = subprocess.run(
        [str(SCRIPT), "--dry-run"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "dry-run ok" in result.stdout


def test_promote_tier1_compare_writes_public_projection(monkeypatch):
    monkeypatch.setenv("NLFR_COMPARE_AGENT_OUTPUT", str(COMPARE_FIXTURE_ROOT))
    subprocess.run([str(SCRIPT)], cwd=ROOT, check=True)
    assert PUBLIC_PROJECTION.is_file()
    payload = json.loads(PUBLIC_PROJECTION.read_text(encoding="utf-8"))
    assert payload["projection_kind"] == "compare"
