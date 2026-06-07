#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${NLFR_DEMO_OUTPUT:-"$ROOT/data/demo-proof"}"
DB="$OUT/nlfr.sqlite"
PROJECTIONS="$OUT/projections"

cd "$ROOT"
mkdir -p "$OUT" "$PROJECTIONS"

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

echo "== NLFR agent-loop closure proof (collectable chain) =="
# Real Nix proof of the bounded-LLM agent loop: agent -> change -> run ->
# validation -> cache, asserting chain_complete=true. Outside nix develop this
# records a durable environment_blocker instead of a false success.
if NLFR_AGENT_LOOP_OUTPUT="$OUT/agent-loop" scripts/agent-loop-proof.sh >"$OUT/agent-loop.log" 2>&1; then
  echo "agent-loop: deterministic bounded-agent patch validated through collectable validation/cache chain (chain_complete=true)"
else
  echo "agent-loop: blocker or failure recorded at $OUT/agent-loop.log"
fi

echo "== NLFR simulated agent-loop provenance (fixture chain) =="
# Deterministic, no-Nix agent loop: a bounded agent patch is recorded, then
# fixture Bazel evidence is attached to the SAME run so the action graph shows
# agent -> change -> run -> validation -> cache. This fixture chain is
# simulated_v1; the collectable_v1 chain lives in scripts/agent-loop-proof.sh.
rm -f "$DB"
rm -rf "$OUT/workspaces" "$OUT/provenance" "$OUT/simulations"
AGENT_RUN_KEY="simulation:llm-bounded-patch:cache-only"
PYTHONPATH=src uv run python -m nlfr simulate \
  --scenario llm-bounded-patch \
  --output-dir "$OUT" \
  --run-group latest \
  --skip-run \
  --json >"$OUT/agent-sim.json"

echo "== NLFR fixture-backed validation ingest (joins agent run) =="
PYTHONPATH=src uv run python -m nlfr ingest \
  --database "$DB" \
  --run-key "$AGENT_RUN_KEY" \
  --run-group latest \
  --bep "$ROOT/tests/fixtures/bazel/bep.jsonl" \
  --execution-log "$ROOT/tests/fixtures/bazel/execution-log.json" \
  --profile "$ROOT/tests/fixtures/bazel/profile.json" \
  --source-kind simulated_v1 \
  --json >"$OUT/fixture-ingest.json"

echo "== NLFR projection exports (demo-proof only) =="
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

echo "demo fixture projections: $PROJECTIONS (simulated_v1 agent-loop chain)"
echo "default canvas uses apps/canvas/public/projections/ from record-canvas-build.sh — not overwritten here"

echo "== NLFR canvas build =="
if command -v npm >/dev/null 2>&1; then
  npm --prefix "$ROOT/apps/canvas" run build
else
  echo "canvas: npm missing; skipped canvas build"
fi

echo "== NLFR proof output =="
echo "database: $DB"
echo "projections: $PROJECTIONS"
echo "committed canvas default: $ROOT/apps/canvas/public/projections/ (canvas-dev collectable_v1)"
