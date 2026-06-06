#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${NLFR_RECORD_PROOF_OUTPUT:-"$ROOT/data/record-proof"}"
DB="$OUT/nlfr.sqlite"
PROJECTIONS="$OUT/projections"

cd "$ROOT"
mkdir -p "$OUT" "$PROJECTIONS"

echo "== Generic command record proof =="
PYTHONPATH=src uv run python -m nlfr run \
  --mode generic \
  --scenario record-proof \
  --run-group record-proof \
  --workspace "$ROOT" \
  --output-dir "$OUT" \
  --change-path README.md \
  --command "uv run pytest tests/test_generic_run.py -q --tb=no" \
  --json >"$OUT/run.json"

echo "== Export record-proof projections =="
PYTHONPATH=src uv run python -m nlfr graph export \
  --db "$DB" \
  --run-group record-proof \
  --output "$PROJECTIONS/action-graph.json"
PYTHONPATH=src uv run python -m nlfr runway export \
  --db "$DB" \
  --run-group record-proof \
  --output "$PROJECTIONS/runway.json"
PYTHONPATH=src uv run python -m nlfr proof export \
  --db "$DB" \
  --run-group record-proof \
  --output "$PROJECTIONS/proof.json"

SUMMARY_ROOT="$OUT" python3 - <<'PY'
import json
import os
from pathlib import Path

root = Path(os.environ["SUMMARY_ROOT"])
run_payload = json.loads((root / "run.json").read_text())
proof = json.loads((root / "projections" / "proof.json").read_text())

summary = {
    "status": run_payload["status"],
    "run_id": run_payload["run_id"],
    "run_group": run_payload["run_group"],
    "mode": run_payload["mode"],
    "artifact_root": run_payload["artifact_root"],
    "commands": run_payload["commands"],
    "results": [
        {
            "command": item["command"][:3],
            "status": item["status"],
            "exit_code": item["exit_code"],
        }
        for item in run_payload["results"]
    ],
    "projection_summary": proof.get("summary", {}),
    "source_kind": "collectable_v1",
    "confidence": "high",
    "redaction_state": "safe",
    "evidence_refs": [
        "run.json",
        "projections/action-graph.json",
        "projections/proof.json",
        "projections/runway.json",
    ],
}
(root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
print(json.dumps(summary, indent=2, sort_keys=True))
PY

echo "record-proof complete: $OUT/summary.json"
