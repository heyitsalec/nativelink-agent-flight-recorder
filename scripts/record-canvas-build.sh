#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${NLFR_CANVAS_DEV_OUTPUT:-"$ROOT/data/canvas-dev"}"
DB="$OUT/nlfr.sqlite"
PROJECTIONS="$OUT/projections"
PUBLIC="$ROOT/apps/canvas/public/projections"

cd "$ROOT"
mkdir -p "$OUT" "$PROJECTIONS" "$PUBLIC"

if [ ! -d "$ROOT/apps/canvas/node_modules" ]; then
  echo "== Install canvas deps (node_modules missing) =="
  npm ci --prefix "$ROOT/apps/canvas"
fi

echo "== Build canvas =="
npm --prefix apps/canvas run build

echo "== Record canvas build chain via generic run =="
PYTHONPATH=src uv run python -m nlfr run \
  --mode generic \
  --scenario canvas-build \
  --run-group canvas-dev \
  --workspace "$ROOT" \
  --output-dir "$OUT" \
  --change-path apps/canvas/src/App.tsx \
  --command "npm --prefix apps/canvas run build" \
  --command "uv run pytest tests/test_generic_run.py -q --tb=no" \
  --artifact apps/canvas/dist/index.html:canvas-dist \
  --json >"$OUT/run.json"

echo "== Export canvas-dev projections =="
PYTHONPATH=src uv run python -m nlfr graph export \
  --db "$DB" \
  --run-group canvas-dev \
  --output "$PROJECTIONS/action-graph.raw.json"
PYTHONPATH=src uv run python -m nlfr runway export \
  --db "$DB" \
  --run-group canvas-dev \
  --output "$PROJECTIONS/runway.raw.json"
PYTHONPATH=src uv run python -m nlfr proof export \
  --db "$DB" \
  --run-group canvas-dev \
  --output "$PROJECTIONS/proof.raw.json"

echo "== Redact and publish default canvas projections =="
python3 scripts/redact-projection.py "$PROJECTIONS/action-graph.raw.json" "$PUBLIC/action-graph.json"
python3 scripts/redact-projection.py "$PROJECTIONS/runway.raw.json" "$PUBLIC/runway.json"
python3 scripts/redact-projection.py "$PROJECTIONS/proof.raw.json" "$PUBLIC/proof.json"

# --check gate: redact mode deliberately passes some findings through (a
# secret-shaped KEY is reported, never rewritten). Re-scan each *published*
# file so any surviving finding aborts the publish loudly (set -e -> non-zero).
echo "== Verify published projections carry no surviving findings (--check gate) =="
for published in "$PUBLIC/action-graph.json" "$PUBLIC/runway.json" "$PUBLIC/proof.json"; do
  python3 scripts/redact-projection.py --check "$published"
done

echo "== Rebuild canvas so dist serves updated projections =="
npm --prefix apps/canvas run build

SUMMARY_ROOT="$OUT" python3 - <<'PY'
import json
import os
from pathlib import Path

root = Path(os.environ["SUMMARY_ROOT"])
run_payload = json.loads((root / "run.json").read_text())
proof = json.loads((root / "projections" / "proof.raw.json").read_text())

summary = {
    "status": run_payload["status"],
    "run_id": run_payload["run_id"],
    "run_group": run_payload["run_group"],
    "mode": run_payload["mode"],
    "artifact_root": run_payload["artifact_root"].replace(os.path.expanduser("~"), "${HOME}"),
    "commands": run_payload["commands"],
    "results": [
        {
            "command": item["command"][:4],
            "status": item["status"],
            "exit_code": item["exit_code"],
        }
        for item in run_payload["results"]
    ],
    "projection_summary": proof.get("summary", {}),
    "default_projection": "apps/canvas/public/projections/",
    "source_kind": "collectable_v1",
    "confidence": "high",
    "redaction_state": "safe",
    "evidence_refs": [
        "run.json",
        "projections/action-graph.raw.json",
        "projections/proof.raw.json",
        "projections/runway.raw.json",
        "apps/canvas/public/projections/action-graph.json",
    ],
}
(root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
print(json.dumps(summary, indent=2, sort_keys=True))
PY

echo "canvas-dev dogfood complete: $OUT/summary.json"
