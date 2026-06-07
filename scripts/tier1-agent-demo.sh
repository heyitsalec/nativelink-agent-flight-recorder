#!/usr/bin/env bash
set -euo pipefail

# Tier 1 agent demo orchestrator — three acts via record-agent-change.sh recipes.
# Dry-run validates scenarios and adapter subprocesses without SQLite writes.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TIER1_DIR="$ROOT/demo/scenarios/tier1"
ADAPTER="$ROOT/scripts/record-agent-change.sh"
COMPARE="$ROOT/scripts/compare-agent-runs.sh"

DRY_RUN=false
JSON_OUT=false
SELECTED_ACT=""

usage() {
  cat <<'EOF'
Usage: tier1-agent-demo.sh [--dry-run] [--act N] [--json]

Options:
  --dry-run   Plan only; no SQLite writes; exit 0
  --act N     Run single act (1, 2, or 3); default all
  --json      Emit machine-readable plan on stdout (dry-run and live summary)
  -h, --help  Usage
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --act)
      SELECTED_ACT="$2"
      shift 2
      ;;
    --json)
      JSON_OUT=true
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

if [[ -n "$SELECTED_ACT" && ! "$SELECTED_ACT" =~ ^[123]$ ]]; then
  echo "error: --act must be 1, 2, or 3" >&2
  exit 2
fi

act_scenario_file() {
  case "$1" in
    1) echo "agent-bugfix-1.json" ;;
    2) echo "agent-feature-compare.json" ;;
    3) echo "agent-change-meta.json" ;;
    *) echo "error: invalid act $1" >&2; exit 2 ;;
  esac
}

declare -a ACT_LIST=()
if [[ -n "$SELECTED_ACT" ]]; then
  ACT_LIST=("$SELECTED_ACT")
else
  ACT_LIST=(1 2 3)
fi

validate_scenario() {
  local scenario_path="$1"
  python3 - <<'PY' "$scenario_path" "$TIER1_DIR"
import hashlib
import json
import sys
from pathlib import Path

scenario_path = Path(sys.argv[1])
tier1_dir = Path(sys.argv[2])

def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    sys.exit(1)

def walk_forbidden_prompt(obj, path: str = "") -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in {"prompt", "raw_prompt"}:
                fail(f"forbidden field {path}.{key} in {scenario_path.name}")
            walk_forbidden_prompt(value, f"{path}.{key}" if path else key)
    elif isinstance(obj, list):
        for index, item in enumerate(obj):
            walk_forbidden_prompt(item, f"{path}[{index}]")

payload = json.loads(scenario_path.read_text(encoding="utf-8"))
walk_forbidden_prompt(payload)

if payload.get("schema_version") != "nlfr.tier1.scenario.v1":
    fail(f"schema_version must be nlfr.tier1.scenario.v1 in {scenario_path.name}")

agent = payload.get("record", {}).get("agent", {})
if agent.get("kind") != "cursor_adapter_v1":
    fail(f"record.agent.kind must be cursor_adapter_v1 in {scenario_path.name}")

fixture_rel = agent.get("prompt_fixture", "")
fixture_path = tier1_dir / fixture_rel
if not fixture_rel or not fixture_path.is_file():
    fail(f"prompt_fixture not found under tier1/: {fixture_rel}")

expected_hash = agent.get("prompt_sha256", "")
actual_hash = hashlib.sha256(fixture_path.read_bytes()).hexdigest()
if expected_hash != actual_hash:
    fail(
        f"prompt_sha256 mismatch in {scenario_path.name}: "
        f"expected {expected_hash}, got {actual_hash}"
    )

print(json.dumps(payload, sort_keys=True))
PY
}

resolve_validation_command() {
  local scenario_json="$1"
  python3 - <<'PY' "$scenario_json"
import json
import os
import sys

payload = json.loads(sys.argv[1])
record = payload["record"]
if os.environ.get("NLFR_SKIP_BAZEL") == "1":
    print(record.get("validation_fallback") or record["validation_command"])
else:
    print(record["validation_command"])
PY
}

run_compare_dry() {
  if [[ -x "$COMPARE" ]]; then
    "$COMPARE" --dry-run --json
    return
  fi

  ROOT="$ROOT" NLFR_TIER1_GROUPS="${NLFR_TIER1_GROUPS:-record-proof,canvas-dev,agent-bugfix-1}" \
    python3 - <<'PY'
import json
import os

root = os.environ["ROOT"]
groups = os.environ.get("NLFR_TIER1_GROUPS", "record-proof,canvas-dev,agent-bugfix-1").split(",")
lookup = {
    "record-proof": os.environ.get("NLFR_RECORD_PROOF_OUTPUT", f"{root}/data/record-proof"),
    "canvas-dev": os.environ.get("NLFR_CANVAS_DEV_OUTPUT", f"{root}/data/canvas-dev"),
    "agent-bugfix-1": os.environ.get("NLFR_AGENT_BUGFIX_OUTPUT", f"{root}/data/agent-bugfix-1"),
    "agent-feature-compare": os.environ.get("NLFR_AGENT_FEATURE_OUTPUT", f"{root}/data/agent-feature-compare"),
    "agent-change": f"{root}/data/agent-change",
}
pairs = [
    (groups[0], groups[1]),
    (groups[1], groups[2]),
    (groups[0], groups[2]),
]
planned = []
for left, right in pairs:
    left_db = f"{lookup.get(left, f'{root}/data/{left}')}/nlfr.sqlite"
    right_db = f"{lookup.get(right, f'{root}/data/{right}')}/nlfr.sqlite"
    out = (
        f"{os.environ.get('NLFR_COMPARE_AGENT_OUTPUT', f'{root}/data/compare-agent-runs')}"
        f"/projections/compare-{left}-vs-{right}.json"
    )
    planned.append(
        {
            "left": left,
            "right": right,
            "left_db": left_db,
            "right_db": right_db,
            "output": out,
            "command": (
                f"nlfr compare export --left-db {left_db} --right-db {right_db} "
                f"--left {left} --right {right}"
            ),
        }
    )

payload = {
    "status": "dry_run",
    "run_groups": groups,
    "pair_count": len(pairs),
    "pairs": planned,
    "source_kind": "derived_v1",
}
print(json.dumps(payload, indent=2, sort_keys=True))
PY
}

run_compare_live() {
  if [[ ! -x "$COMPARE" ]]; then
    echo "error: compare script missing: $COMPARE" >&2
    exit 1
  fi
  "$COMPARE" ${JSON_OUT:+--json}
}

PLAN_FILE="$(mktemp "${TMPDIR:-/tmp}/tier1-plan.XXXXXX")"
ACTS_FILE="$(mktemp "${TMPDIR:-/tmp}/tier1-acts.XXXXXX")"
BLOCKERS_FILE="$(mktemp "${TMPDIR:-/tmp}/tier1-blockers.XXXXXX")"
cleanup() {
  rm -f "$PLAN_FILE" "$ACTS_FILE" "$BLOCKERS_FILE"
}
trap cleanup EXIT

: >"$BLOCKERS_FILE"

for act in "${ACT_LIST[@]}"; do
  scenario_file="$(act_scenario_file "$act")"
  scenario_path="$TIER1_DIR/$scenario_file"

  if [[ ! -f "$scenario_path" ]]; then
    echo "error: scenario file missing: $scenario_path" >&2
    exit 1
  fi

  scenario_json="$(validate_scenario "$scenario_path")"
  run_group="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["run_group"])' "$scenario_json")"
  scenario_id="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["scenario_id"])' "$scenario_json")"
  output_dir_rel="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["record"]["output_dir"])' "$scenario_json")"
  workspace_rel="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["record"]["workspace"])' "$scenario_json")"
  model="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["record"]["agent"]["model"])' "$scenario_json")"
  prompt_fixture_rel="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["record"]["agent"]["prompt_fixture"])' "$scenario_json")"
  prompt_file="$TIER1_DIR/$prompt_fixture_rel"

  change_paths="$(python3 -c 'import json,sys; print("\n".join(json.loads(sys.argv[1])["record"]["change_paths"]))' "$scenario_json")"

  if [[ "${NLFR_SKIP_BAZEL:-0}" == "1" ]]; then
    echo "act_${act}:using_validation_fallback" >>"$BLOCKERS_FILE"
  fi

  validation_cmd="$(resolve_validation_command "$scenario_json")"

  if [[ "$output_dir_rel" = /* ]]; then
    output_dir="$output_dir_rel"
  else
    output_dir="$ROOT/$output_dir_rel"
  fi

  if [[ "$workspace_rel" = /* ]]; then
    workspace="$workspace_rel"
  else
    workspace="$ROOT/$workspace_rel"
  fi

  declare -a act_commands=()

  while IFS= read -r change_path; do
    [[ -z "$change_path" ]] && continue

    adapter_cmd=(
      "$ADAPTER"
      --change-path "$change_path"
      --model "$model"
      --prompt-file "$prompt_file"
      --command "$validation_cmd"
      --output-dir "$output_dir"
      --workspace "$workspace"
      --scenario "$scenario_id"
      --run-group "$run_group"
    )

    if [[ "$DRY_RUN" == true ]]; then
      adapter_cmd+=(--dry-run)
      echo "== Act $act dry-run: $run_group ($change_path) ==" >&2
      if [[ "$JSON_OUT" == true ]]; then
        "${adapter_cmd[@]}" >&2
      else
        "${adapter_cmd[@]}"
      fi
      act_commands+=("${adapter_cmd[*]}")
    else
      if [[ ! -e "$ROOT/$change_path" && ! -e "$change_path" ]]; then
        echo "error: change path missing (apply edit before live record): $change_path" >&2
        exit 1
      fi
      echo "== Act $act live: $run_group ($change_path) =="
      export NLFR_AGENT_CHANGE_OUTPUT="$output_dir"
      export NLFR_AGENT_CHANGE_RUN_GROUP="$run_group"
      export NLFR_AGENT_CHANGE_SCENARIO="$scenario_id"
      export NLFR_AGENT_CHANGE_WORKSPACE="$workspace"
      "${adapter_cmd[@]}"
      act_commands+=("${adapter_cmd[*]}")
    fi
  done <<<"$change_paths"

  python3 - <<'PY' "$act" "$run_group" "${act_commands[@]}" >>"$ACTS_FILE"
import json
import sys

act = int(sys.argv[1])
run_group = sys.argv[2]
commands = sys.argv[3:]
print(json.dumps({"act": act, "run_group": run_group, "commands": commands}, sort_keys=True))
PY
done

COMPARE_PLAN_FILE="$(mktemp "${TMPDIR:-/tmp}/tier1-compare.XXXXXX")"
if [[ "$DRY_RUN" == true ]]; then
  echo "== Compare triple dry-run ==" >&2
  run_compare_dry >"$COMPARE_PLAN_FILE"
elif printf '%s\n' "${ACT_LIST[@]}" | grep -qx '3'; then
  echo "== Compare triple live =="
  run_compare_live
  printf '%s\n' '{"run_groups":["record-proof","canvas-dev","agent-bugfix-1"],"pair_count":3}' >"$COMPARE_PLAN_FILE"
else
  printf '%s\n' '{"run_groups":["record-proof","canvas-dev","agent-bugfix-1"],"pair_count":3}' >"$COMPARE_PLAN_FILE"
fi

DRY_RUN_FLAG="$DRY_RUN" JSON_OUT_FLAG="$JSON_OUT" PLAN_FILE="$PLAN_FILE" ACTS_FILE="$ACTS_FILE" \
  BLOCKERS_FILE="$BLOCKERS_FILE" COMPARE_PLAN_FILE="$COMPARE_PLAN_FILE" \
  python3 - <<'PY'
import json
import os
from pathlib import Path

plan_path = Path(os.environ["PLAN_FILE"])
acts = [json.loads(line) for line in Path(os.environ["ACTS_FILE"]).read_text(encoding="utf-8").splitlines() if line.strip()]
blockers = [line.strip() for line in Path(os.environ["BLOCKERS_FILE"]).read_text(encoding="utf-8").splitlines() if line.strip()]
compare_plan = json.loads(Path(os.environ["COMPARE_PLAN_FILE"]).read_text(encoding="utf-8"))
dry_run = os.environ.get("DRY_RUN_FLAG") == "true"

payload = {
    "status": "dry_run" if dry_run else "ok",
    "acts": acts,
    "compare_plan": {
        "run_groups": compare_plan.get("run_groups", ["record-proof", "canvas-dev", "agent-bugfix-1"]),
        "pair_count": compare_plan.get("pair_count", 3),
    },
    "blockers": blockers,
    "source_kind": "derived_v1",
}
plan_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
if os.environ.get("JSON_OUT_FLAG") == "true":
    print(json.dumps(payload, indent=2, sort_keys=True))
PY

if [[ "$JSON_OUT" != true ]]; then
  if [[ "$DRY_RUN" == true ]]; then
    echo "tier1-agent-demo dry-run complete"
  else
    echo "tier1-agent-demo live complete"
  fi
fi
