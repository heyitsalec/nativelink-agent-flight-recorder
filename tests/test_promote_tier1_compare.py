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


# A secret-shaped dict KEY: reported by redact --check but NEVER rewritten by
# write-mode (rewriting a key would break consumers), so it survives into the
# published file. Documented-fake, repeated-char fill -> not a live token shape,
# so it never trips GitHub push protection. Same construction as
# tests/test_redaction.py::FAKE_GH_TOKEN.
_SURVIVING_KEY = "ghp_" + "A" * 36


def test_promote_aborts_when_a_finding_survives_redaction(tmp_path, monkeypatch):
    """The publish gate aborts when a finding SURVIVES redact write-mode (#58).

    Seeds a secret-shaped KEY into the compare source. redact write-mode reports
    it but leaves keys intact, so it reaches the published file; the --check
    re-scan then fails the publish loudly (set -e -> non-zero). This mirrors the
    record-canvas-build.sh wiring proof — the gate is defense-in-depth, not a
    silent copy. Hermetic: destination is redirected to a temp path, so the
    tracked public projection is never touched.
    """

    src_root = tmp_path / "compare-agent-runs"
    proj_dir = src_root / "projections"
    proj_dir.mkdir(parents=True)
    fixture = json.loads(
        (COMPARE_FIXTURE_ROOT / "projections" / "compare-canvas-dev-vs-agent-bugfix-1.json").read_text(
            encoding="utf-8"
        )
    )
    fixture[_SURVIVING_KEY] = "surviving-finding-marker"
    (proj_dir / "compare-canvas-dev-vs-agent-bugfix-1.json").write_text(
        json.dumps(fixture, indent=2) + "\n", encoding="utf-8"
    )

    dest = tmp_path / "out" / "compare-projection.json"
    dest.parent.mkdir(parents=True)
    monkeypatch.setenv("NLFR_COMPARE_AGENT_OUTPUT", str(src_root))
    monkeypatch.setenv("NLFR_TIER1_COMPARE_DEST", str(dest))
    result = subprocess.run([str(SCRIPT)], cwd=ROOT, text=True, capture_output=True, check=False)

    assert result.returncode != 0, "publish must abort when a finding survives redaction"
    assert "github_token" in result.stderr  # --check named the surviving finding
    assert dest.resolve() != PUBLIC_PROJECTION.resolve()  # tracked file untouched


def test_promote_dry_run_scans_source_and_writes_nothing(tmp_path, monkeypatch):
    """--dry-run runs the --check scan on the SOURCE and never writes (#58)."""

    dest = tmp_path / "should-not-exist.json"
    monkeypatch.setenv("NLFR_COMPARE_AGENT_OUTPUT", str(COMPARE_FIXTURE_ROOT))
    monkeypatch.setenv("NLFR_TIER1_COMPARE_DEST", str(dest))
    result = subprocess.run(
        [str(SCRIPT), "--dry-run"], cwd=ROOT, text=True, capture_output=True, check=False
    )
    assert result.returncode == 0, result.stderr
    assert "dry-run ok" in result.stdout
    assert "OK, no findings" in result.stdout  # the --check gate actually ran
    assert not dest.exists()
