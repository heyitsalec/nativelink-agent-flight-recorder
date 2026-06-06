#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${NLFR_DEMO_OUTPUT:-"$ROOT/data/demo-proof"}"
DB="$OUT/nlfr.sqlite"
PROJECTIONS="$OUT/projections"

cd "$ROOT"
mkdir -p "$OUT" "$PROJECTIONS" "$ROOT/apps/canvas/public/projections"

echo "== NLFR backend tests =="
uv run pytest tests -q

echo "== NLFR cache-only doctor =="
if PYTHONPATH=src uv run python -m nlfr doctor --mode cache-only --json >"$OUT/doctor.json"; then
  echo "doctor: cache-only environment ready"
else
  echo "doctor: cache-only environment blocker recorded at $OUT/doctor.json"
fi

echo "== NLFR real-tool smoke =="
if PYTHONPATH=src uv run python -m nlfr run \
  --scenario local-tool-check \
  --run-group tool-check \
  --workspace "$ROOT/demo/bazel-monorepo" \
  --output-dir "$OUT/tool-check" \
  --json \
  //tasks:priority_test >"$OUT/tool-check-run.json"; then
  echo "run: local Bazel/NativeLink smoke completed"
else
  echo "run: local smoke blocker recorded at $OUT/tool-check-run.json"
fi

echo "== NLFR cold/warm NativeLink proof =="
if NLFR_COLD_WARM_OUTPUT="$OUT/cold-warm" scripts/cold-warm-cache-proof.sh >"$OUT/cold-warm.log" 2>&1; then
  echo "cold/warm: NativeLink cache proof completed"
else
  echo "cold/warm: blocker or failure recorded at $OUT/cold-warm.log"
fi

echo "== NLFR local execution proof =="
if NLFR_LOCAL_EXEC_OUTPUT="$OUT/local-exec" scripts/local-exec-proof.sh >"$OUT/local-exec.log" 2>&1; then
  echo "local-exec: one-process remote-executor smoke completed; worker execution requires direct evidence"
else
  echo "local-exec: blocker or failure recorded at $OUT/local-exec.log"
fi

echo "== NLFR simulated-agent provenance =="
rm -rf "$OUT/agent-sim"
PYTHONPATH=src uv run python -m nlfr simulate \
  --scenario safe-leaf-change \
  --output-dir "$OUT/agent-sim" \
  --skip-run \
  --json >"$OUT/agent-sim.json"
PYTHONPATH=src uv run python -m nlfr proof export \
  --db "$OUT/agent-sim/nlfr.sqlite" \
  --run-group agent-sim \
  --output "$OUT/agent-sim-proof.json"

echo "== NLFR fixture-backed ingest =="
rm -f "$DB"
PYTHONPATH=src uv run python -m nlfr ingest \
  --database "$DB" \
  --run-key fixture-run:cache-only \
  --run-group latest \
  --bep "$ROOT/tests/fixtures/bazel/bep.jsonl" \
  --execution-log "$ROOT/tests/fixtures/bazel/execution-log.json" \
  --profile "$ROOT/tests/fixtures/bazel/profile.json" \
  --source-kind simulated_v1 \
  --json >"$OUT/fixture-ingest.json"

echo "== NLFR projection exports =="
PYTHONPATH=src uv run python -m nlfr graph export \
  --db "$DB" \
  --run-group latest \
  --output "$PROJECTIONS/action-graph.json"
PYTHONPATH=src uv run python -m nlfr runway export \
  --db "$DB" \
  --run-group latest \
  --output "$PROJECTIONS/runway.json"
PYTHONPATH=src uv run python -m nlfr proof export \
  --db "$DB" \
  --run-group latest \
  --output "$PROJECTIONS/proof.json"
cp "$PROJECTIONS/action-graph.json" "$ROOT/apps/canvas/public/projections/action-graph.json"
cp "$PROJECTIONS/runway.json" "$ROOT/apps/canvas/public/projections/runway.json"
cp "$PROJECTIONS/proof.json" "$ROOT/apps/canvas/public/projections/proof.json"

echo "== NLFR canvas build =="
if command -v npm >/dev/null 2>&1; then
  npm --prefix "$ROOT/apps/canvas" run build
else
  echo "canvas: npm missing; skipped canvas build"
fi

echo "== NLFR proof output =="
echo "database: $DB"
echo "projections: $PROJECTIONS"
echo "canvas projection: $ROOT/apps/canvas/public/projections/action-graph.json"
