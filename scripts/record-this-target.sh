#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${1:-//tasks:priority_test}"
OUT="${NLFR_OUTPUT_DIR:-data/nlfr}"
WORKSPACE="${NLFR_WORKSPACE:-demo/bazel-monorepo}"
RUN_GROUP="${NLFR_RUN_GROUP:-latest}"
SCENARIO="${NLFR_SCENARIO:-record-this-target}"
MODE="${NLFR_MODE:-cache-only}"

cd "$ROOT"

echo "== NLFR init =="
PYTHONPATH=src uv run python -m nlfr init \
  --workspace "$WORKSPACE" \
  --output-dir "$OUT" \
  --run-group "$RUN_GROUP"

echo "== NLFR run $TARGET =="
PYTHONPATH=src uv run python -m nlfr run \
  --mode "$MODE" \
  --scenario "$SCENARIO" \
  --run-group "$RUN_GROUP" \
  --workspace "$ROOT/$WORKSPACE" \
  --output-dir "$ROOT/$OUT" \
  --target "$TARGET" \
  --json >"$ROOT/$OUT/record-this-target-run.json"

echo "record-this-target complete: $ROOT/$OUT/record-this-target-run.json"
