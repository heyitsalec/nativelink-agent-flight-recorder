#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LEFT_OUT="${NLFR_RECORD_PROOF_OUTPUT:-$ROOT/data/record-proof}"
RIGHT_OUT="${NLFR_CANVAS_DEV_OUTPUT:-$ROOT/data/canvas-dev}"
LEFT_GROUP="${NLFR_COMPARE_LEFT:-record-proof}"
RIGHT_GROUP="${NLFR_COMPARE_RIGHT:-canvas-dev}"
OUT="${NLFR_COMPARE_OUTPUT:-$ROOT/data/compare-proof}"
PROJECTIONS="$OUT/projections"

cd "$ROOT"
mkdir -p "$OUT" "$PROJECTIONS"

echo "== Compare proof summaries: $LEFT_GROUP vs $RIGHT_GROUP =="

LEFT_DB="$LEFT_OUT/nlfr.sqlite" \
RIGHT_DB="$RIGHT_OUT/nlfr.sqlite" \
LEFT_GROUP="$LEFT_GROUP" \
RIGHT_GROUP="$RIGHT_GROUP" \
OUT="$OUT" \
PYTHONPATH=src uv run python - <<'PY'
import json
import os
import sys
from pathlib import Path

from nlfr.db import UnreadableDatabaseError, connect_readonly
from nlfr.projectors.compare import (
    MissingRunGroupError,
    build_compare_projection,
    require_run_group,
)
from nlfr.projectors.common import run_rows
from nlfr.projectors.proof import export_proof_packet

left_db = Path(os.environ["LEFT_DB"])
right_db = Path(os.environ["RIGHT_DB"])
left_group = os.environ["LEFT_GROUP"]
right_group = os.environ["RIGHT_GROUP"]
out = Path(os.environ["OUT"])
projections = out / "projections"

if not left_db.is_file():
    print(f"left db missing: {left_db}", file=sys.stderr)
    sys.exit(1)
if not right_db.is_file():
    print(f"right db missing: {right_db}", file=sys.stderr)
    sys.exit(1)

# Read-only: comparing recorded evidence must never migrate or auto-create a
# database, and a zero-byte/typo'd path or missing run group must fail loudly —
# a schema-valid comparison of real data against nothing is fabrication (#47).
try:
    left_conn = connect_readonly(left_db)
    right_conn = connect_readonly(right_db)
    require_run_group(left_conn, "left", left_group)
    require_run_group(right_conn, "right", right_group)
except (UnreadableDatabaseError, MissingRunGroupError) as exc:
    print(str(exc), file=sys.stderr)
    sys.exit(1)

left_proof = export_proof_packet(left_conn, run_group=left_group)
right_proof = export_proof_packet(right_conn, run_group=right_group)
left_runs = run_rows(left_conn, left_group)
right_runs = run_rows(right_conn, right_group)

compare = build_compare_projection(
    left_proof,
    right_proof,
    left_group,
    right_group,
    left_runs=left_runs,
    right_runs=right_runs,
)

compare_path = projections / "compare-projection.json"
compare_path.write_text(json.dumps(compare, indent=2, sort_keys=True) + "\n", encoding="utf-8")

summary = {
    "status": "ok",
    "left_run_group": left_group,
    "right_run_group": right_group,
    "left_db": str(left_db),
    "right_db": str(right_db),
    "compare_projection": str(compare_path),
    "dimension_ids": [item["id"] for item in compare.get("dimensions", [])],
    "summary": compare.get("summary", {}),
    "source_kind": "derived_v1",
    "confidence": "medium",
    "redaction_state": "safe",
    "evidence_refs": compare.get("evidence_refs", []),
}
(out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(summary, indent=2, sort_keys=True))
PY

echo "compare-proof complete: $OUT/summary.json"
