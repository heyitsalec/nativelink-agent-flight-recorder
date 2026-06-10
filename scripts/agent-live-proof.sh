#!/usr/bin/env bash
set -euo pipefail

# M8 live agent E2E proof — wraps record-agent-change.sh with NLFR_AGENT_LIVE=1.
# Dry-run always works for CI. Without Cursor CLI, writes an honest environment blocker.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${NLFR_AGENT_LIVE_OUTPUT:-"$ROOT/data/agent-live-proof"}"
ADAPTER="$ROOT/scripts/record-agent-change.sh"
CHANGE_PATH="${NLFR_AGENT_LIVE_CHANGE_PATH:-adapters/cursor/README.md}"
MODEL="${NLFR_AGENT_LIVE_MODEL:-composer-2.5}"
PROMPT_FILE="${NLFR_AGENT_LIVE_PROMPT_FILE:-$ROOT/demo/scenarios/tier1/fixtures/prompt-meta.txt}"
COMMAND="${NLFR_AGENT_LIVE_COMMAND:-uv run pytest tests/test_record_agent_change.py -q --tb=no}"
SCENARIO="${NLFR_AGENT_LIVE_SCENARIO:-agent-live}"
RUN_GROUP="${NLFR_AGENT_LIVE_RUN_GROUP:-agent-live}"
DRY_RUN=false

usage() {
  cat <<'EOF'
Usage: agent-live-proof.sh [--dry-run]

Live M8 agent proof via record-agent-change.sh (collectable_v1, model + prompt_sha256 only).

Options:
  --dry-run   Plan only; always succeeds for CI (no Cursor CLI required)
  -h, --help  Show this help

Environment:
  NLFR_AGENT_LIVE=1              Set on live runs (wrapper exports this)
  NLFR_AGENT_LIVE_OUTPUT         Output dir (default: data/agent-live-proof)
  NLFR_AGENT_LIVE_FORCE_BLOCKER  Set to 1 to record environment-blocker.json (tests)
  NLFR_CURSOR_BIN                Override Cursor CLI probe path
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

mkdir -p "$OUT"

write_blocker() {
  local reason="$1"
  REASON="$reason" OUT_PATH="$OUT/environment-blocker.json" python3 - <<'PY'
import json
import os
from pathlib import Path

payload = {
    "status": "environment_blocker",
    "reason": os.environ["REASON"],
    "next_step": (
        "install Cursor CLI per adapters/cursor/README.md, "
        "or run ./scripts/agent-live-proof.sh --dry-run for CI regression"
    ),
    "proof_script": "agent-live-proof.sh",
    "nlfr_agent_live": True,
    "scenario_id": "agent-live",
    "run_group": "agent-live",
    "source_kind": "collectable_v1",
    "confidence": "high",
    "redaction_state": "safe",
    "evidence_refs": ["script:agent-live-proof.sh"],
    "claim_boundary": {
        "supported": [
            "dry-run adapter contract via agent-live-proof.sh --dry-run",
            "collectable_v1 agent provenance sidecar (model + prompt_sha256 only)",
            "generic validation via pytest fixture path without Cursor CLI",
        ],
        "unsupported_until_cursor_cli": [
            "live non-dry-run adapter invocation on host",
            "chain_complete=true from real Cursor session",
            "live LLM reasoning as validation proof",
        ],
    },
}
path = Path(os.environ["OUT_PATH"])
path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
print(json.dumps(payload, indent=2, sort_keys=True))
PY
  exit 2
}

adapter_args=(
  --change-path "$CHANGE_PATH"
  --model "$MODEL"
  --prompt-file "$PROMPT_FILE"
  --command "$COMMAND"
  --output-dir "$OUT"
  --workspace "$ROOT"
  --scenario "$SCENARIO"
  --run-group "$RUN_GROUP"
)

if [[ "$DRY_RUN" == true ]]; then
  export NLFR_AGENT_LIVE=1
  adapter_json="$(
    "$ADAPTER" --dry-run "${adapter_args[@]}"
  )"
  CHANGE_PATH="$CHANGE_PATH" MODEL="$MODEL" RUN_GROUP="$RUN_GROUP" SCENARIO="$SCENARIO" \
    ADAPTER_JSON="$adapter_json" python3 - <<'PY'
import json
import os

adapter = json.loads(os.environ["ADAPTER_JSON"])
payload = {
    "status": "dry_run",
    "proof_script": "agent-live-proof.sh",
    "nlfr_agent_live": True,
    "scenario_id": os.environ["SCENARIO"],
    "run_group": os.environ["RUN_GROUP"],
    "change_path": os.environ["CHANGE_PATH"],
    "model": os.environ["MODEL"],
    "prompt_sha256": adapter.get("prompt_sha256"),
    "adapter": adapter,
    "source_kind": "collectable_v1",
    "confidence": "high",
    "redaction_state": "safe",
    "evidence_refs": [
        "script:agent-live-proof.sh",
        "script:record-agent-change.sh",
    ],
}
print(json.dumps(payload, indent=2, sort_keys=True))
PY
  exit 0
fi

if [[ "${NLFR_AGENT_LIVE_FORCE_BLOCKER:-}" == "1" ]]; then
  write_blocker "NLFR_AGENT_LIVE_FORCE_BLOCKER=1 (test probe)"
fi

CURSOR_BIN="${NLFR_CURSOR_BIN:-$(command -v cursor || true)}"
if [[ -z "$CURSOR_BIN" || ! -x "$CURSOR_BIN" ]]; then
  write_blocker "cursor CLI unavailable on PATH; install Cursor CLI or run with --dry-run for CI"
fi

export NLFR_AGENT_LIVE=1
export NLFR_AGENT_CHANGE_OUTPUT="$OUT"
export NLFR_AGENT_CHANGE_RUN_GROUP="$RUN_GROUP"
export NLFR_AGENT_CHANGE_SCENARIO="$SCENARIO"
export NLFR_AGENT_CHANGE_WORKSPACE="$ROOT"

cd "$ROOT"
"$ADAPTER" "${adapter_args[@]}"

SUMMARY_ROOT="$OUT" CURSOR_BIN="$CURSOR_BIN" SCENARIO="$SCENARIO" RUN_GROUP="$RUN_GROUP" python3 - <<'PY'
import json
import os
from pathlib import Path

root = Path(os.environ["SUMMARY_ROOT"])
graph_path = root / "projections" / "action-graph.json"
proof_path = root / "projections" / "proof.json"
summary_path = root / "summary.json"

if not graph_path.is_file():
    raise SystemExit(f"missing action graph export: {graph_path}")

graph = json.loads(graph_path.read_text(encoding="utf-8"))
kinds: dict[str, int] = {}
for node in graph.get("nodes", []):
    kinds[node["kind"]] = kinds.get(node["kind"], 0) + 1
edge_kinds: dict[str, int] = {}
for edge in graph.get("edges", []):
    edge_kinds[edge["kind"]] = edge_kinds.get(edge["kind"], 0) + 1

chain_complete = (
    kinds.get("agent", 0) >= 1
    and kinds.get("change", 0) >= 1
    and kinds.get("run", 0) >= 1
    and "authored_change" in edge_kinds
    and "validated_by" in edge_kinds
)

base = {}
if summary_path.is_file():
    base = json.loads(summary_path.read_text(encoding="utf-8"))

summary = {
    **base,
    "status": base.get("status", "completed"),
    "proof_script": "agent-live-proof.sh",
    "nlfr_agent_live": True,
    "scenario_id": os.environ["SCENARIO"],
    "run_group": os.environ.get("RUN_GROUP") or base.get("run_group"),
    "chain_complete": chain_complete,
    "graph_node_kinds": kinds,
    "graph_edge_kinds": edge_kinds,
    "cursor_cli": os.environ["CURSOR_BIN"],
    "source_kind": "collectable_v1",
    "confidence": "high",
    "redaction_state": "safe",
    "evidence_refs": [
        "run.json",
        "agent-provenance.json",
        "projections/action-graph.json",
        "projections/proof.json",
        "script:agent-live-proof.sh",
    ],
}
if proof_path.is_file():
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    summary["projection_summary"] = proof.get("summary", summary.get("projection_summary", {}))

summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(summary, indent=2, sort_keys=True))
if not chain_complete:
    raise SystemExit("agent -> change -> run chain incomplete in action graph")
PY

echo "agent-live proof complete: $OUT/summary.json"
