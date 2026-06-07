#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${NLFR_COMPARE_AGENT_OUTPUT:-$ROOT/data/compare-agent-runs}"
PROJECTIONS="$OUT/projections"
TIER1_GROUPS_RAW="${NLFR_TIER1_GROUPS:-record-proof,canvas-dev,agent-bugfix-1}"
REQUIRE_DB="${NLFR_TIER1_REQUIRE_DB:-0}"
DRY_RUN=false
JSON_OUTPUT=false

usage() {
  cat <<'EOF'
Usage: compare-agent-runs.sh [--dry-run] [--json]

Roll up pairwise compare projections for tier1 run groups (default triple:
record-proof, canvas-dev, agent-bugfix-1).

Options:
  --dry-run   Emit planned pairs + DB paths; no writes; exit 0
  --json      Machine-readable summary on stdout
  -h, --help  Show this help

Environment:
  NLFR_COMPARE_AGENT_OUTPUT   Rollup output root (default: data/compare-agent-runs)
  NLFR_TIER1_GROUPS           Comma-separated run groups (default triple above)
  NLFR_RECORD_PROOF_OUTPUT    DB root for record-proof
  NLFR_CANVAS_DEV_OUTPUT      DB root for canvas-dev
  NLFR_AGENT_BUGFIX_OUTPUT    DB root for agent-bugfix-1
  NLFR_AGENT_FEATURE_OUTPUT   DB root for agent-feature-compare
  NLFR_TIER1_REQUIRE_DB       1 → exit non-zero if any group DB/run missing
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --json)
      JSON_OUTPUT=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

group_output_dir() {
  local group="$1"
  case "$group" in
    record-proof)
      echo "${NLFR_RECORD_PROOF_OUTPUT:-$ROOT/data/record-proof}"
      ;;
    canvas-dev)
      echo "${NLFR_CANVAS_DEV_OUTPUT:-$ROOT/data/canvas-dev}"
      ;;
    agent-bugfix-1)
      echo "${NLFR_AGENT_BUGFIX_OUTPUT:-$ROOT/data/agent-bugfix-1}"
      ;;
    agent-feature-compare)
      echo "${NLFR_AGENT_FEATURE_OUTPUT:-$ROOT/data/agent-feature-compare}"
      ;;
    agent-change)
      echo "${NLFR_AGENT_CHANGE_META_OUTPUT:-$ROOT/data/agent-change}"
      ;;
    *)
      echo "error: unknown run group for output lookup: $group" >&2
      exit 1
      ;;
  esac
}

IFS=',' read -r -a RUN_GROUPS <<< "$TIER1_GROUPS_RAW"
if ((${#RUN_GROUPS[@]} < 2)); then
  echo "error: NLFR_TIER1_GROUPS must list at least 2 run groups" >&2
  exit 1
fi

declare -a PAIRS=()
for ((i = 0; i < ${#RUN_GROUPS[@]} - 1; i++)); do
  PAIRS+=("${RUN_GROUPS[i]}:${RUN_GROUPS[i + 1]}")
done
if ((${#RUN_GROUPS[@]} >= 3)); then
  PAIRS+=("${RUN_GROUPS[0]}:${RUN_GROUPS[${#RUN_GROUPS[@]} - 1]}")
fi

pair_left() {
  echo "${1%%:*}"
}

pair_right() {
  echo "${1#*:}"
}

compare_filename() {
  local left right
  left="$(pair_left "$1")"
  right="$(pair_right "$1")"
  echo "compare-${left}-vs-${right}.json"
}

build_plan_json() {
  local pair left right left_out right_out compare_path
  local pairs_json="["
  local first=true
  for pair in "${PAIRS[@]}"; do
    left="$(pair_left "$pair")"
    right="$(pair_right "$pair")"
    left_out="$(group_output_dir "$left")"
    right_out="$(group_output_dir "$right")"
    compare_path="$PROJECTIONS/$(compare_filename "$pair")"
    if [[ "$first" == true ]]; then
      first=false
    else
      pairs_json+=","
    fi
    pairs_json+=$(printf '%s' "{\"left\":\"$left\",\"right\":\"$right\",\"left_db\":\"$left_out/nlfr.sqlite\",\"right_db\":\"$right_out/nlfr.sqlite\",\"compare_projection\":\"$compare_path\"}")
  done
  pairs_json+="]"
  RUN_GROUPS_JSON=$(printf '%s\n' "${RUN_GROUPS[@]}" | PYTHONPATH=src uv run python -c 'import json,sys; print(json.dumps([line.strip() for line in sys.stdin if line.strip()]))')
  PLAN_PAIRS_JSON="$pairs_json" PLAN_RUN_GROUPS_JSON="$RUN_GROUPS_JSON" PLAN_OUT="$OUT" PLAN_PAIR_COUNT="${#PAIRS[@]}" \
    PYTHONPATH=src uv run python - <<'PY'
import json
import os

payload = {
    "status": "dry_run",
    "run_groups": json.loads(os.environ["PLAN_RUN_GROUPS_JSON"]),
    "pair_count": int(os.environ["PLAN_PAIR_COUNT"]),
    "pairs": json.loads(os.environ["PLAN_PAIRS_JSON"]),
    "output_root": os.environ["PLAN_OUT"],
    "source_kind": "derived_v1",
}
print(json.dumps(payload, indent=2, sort_keys=True))
PY
}

if [[ "$DRY_RUN" == true ]]; then
  if [[ "$JSON_OUTPUT" == true ]]; then
    build_plan_json
  else
    echo "== Compare agent runs (dry-run) =="
    echo "Run groups: ${RUN_GROUPS[*]}"
    echo "Output root: $OUT"
    idx=1
    for pair in "${PAIRS[@]}"; do
      left="$(pair_left "$pair")"
      right="$(pair_right "$pair")"
      left_out="$(group_output_dir "$left")"
      right_out="$(group_output_dir "$right")"
      compare_path="$PROJECTIONS/$(compare_filename "$pair")"
      echo ""
      echo "Pair $idx/${#PAIRS[@]}: $left vs $right"
      echo "  left_db:  $left_out/nlfr.sqlite"
      echo "  right_db: $right_out/nlfr.sqlite"
      echo "  output:   $compare_path"
      idx=$((idx + 1))
    done
    echo ""
    echo "compare-agent-runs dry-run complete (${#PAIRS[@]} pairs planned)"
  fi
  exit 0
fi

cd "$ROOT"
mkdir -p "$OUT" "$PROJECTIONS"

echo "== Compare agent runs: ${RUN_GROUPS[*]} =="

LIVE_PAIRS_JSON="["
live_first=true
live_pair_count=0
for pair in "${PAIRS[@]}"; do
  left="$(pair_left "$pair")"
  right="$(pair_right "$pair")"
  left_out="$(group_output_dir "$left")"
  right_out="$(group_output_dir "$right")"
  left_db="$left_out/nlfr.sqlite"
  right_db="$right_out/nlfr.sqlite"
  compare_path="$PROJECTIONS/$(compare_filename "$pair")"

  if [[ ! -f "$left_db" || ! -f "$right_db" ]]; then
    msg="missing db for pair $left vs $right (left=$left_db right=$right_db)"
    if [[ "$REQUIRE_DB" == "1" ]]; then
      echo "error: $msg" >&2
      exit 1
    fi
    echo "warning: $msg" >&2
    continue
  fi

  if ! PYTHONPATH=src uv run python -m nlfr compare index --db "$left_db" --json | \
      PYTHONPATH=src uv run python -c "import json,sys; groups={g['run_group'] for g in json.load(sys.stdin)['run_groups']}; sys.exit(0 if '$left' in groups else 1)"; then
    echo "error: run group '$left' not found in compare index for $left_db" >&2
    exit 1
  fi
  if ! PYTHONPATH=src uv run python -m nlfr compare index --db "$right_db" --json | \
      PYTHONPATH=src uv run python -c "import json,sys; groups={g['run_group'] for g in json.load(sys.stdin)['run_groups']}; sys.exit(0 if '$right' in groups else 1)"; then
    echo "error: run group '$right' not found in compare index for $right_db" >&2
    exit 1
  fi

  if [[ "$live_first" == true ]]; then
    live_first=false
  else
    LIVE_PAIRS_JSON+=","
  fi
  LIVE_PAIRS_JSON+=$(printf '%s' "{\"left\":\"$left\",\"right\":\"$right\",\"left_db\":\"$left_db\",\"right_db\":\"$right_db\",\"compare_projection\":\"$compare_path\"}")
  live_pair_count=$((live_pair_count + 1))
done
LIVE_PAIRS_JSON+="]"

if [[ "$live_pair_count" -eq 0 ]]; then
  echo "error: no pairwise compares produced (all DBs missing?)" >&2
  exit 1
fi

LIVE_PAIRS_JSON="$LIVE_PAIRS_JSON" \
OUT="$OUT" \
RUN_GROUPS_CSV="$TIER1_GROUPS_RAW" \
PYTHONPATH=src uv run python - <<'PY'
import json
import os
import sys
from pathlib import Path

from nlfr.db import connect, initialize
from nlfr.projectors.compare import build_compare_projection
from nlfr.projectors.common import run_rows
from nlfr.projectors.proof import export_proof_packet

pair_specs = json.loads(os.environ["LIVE_PAIRS_JSON"])
out = Path(os.environ["OUT"])
run_groups = [item.strip() for item in os.environ["RUN_GROUPS_CSV"].split(",") if item.strip()]

pairwise_paths: list[str] = []
dimension_ids: list[str] = []

for spec in pair_specs:
    left_group = spec["left"]
    right_group = spec["right"]
    left_db = Path(spec["left_db"])
    right_db = Path(spec["right_db"])
    compare_path = Path(spec["compare_projection"])

    if not left_db.is_file():
        print(f"left db missing: {left_db}", file=sys.stderr)
        sys.exit(1)
    if not right_db.is_file():
        print(f"right db missing: {right_db}", file=sys.stderr)
        sys.exit(1)

    left_conn = initialize(connect(left_db))
    right_conn = initialize(connect(right_db))

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

    compare_path.write_text(json.dumps(compare, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    pairwise_paths.append(str(compare_path))
    if not dimension_ids:
        dimension_ids = [item["id"] for item in compare.get("dimensions", [])]

summary = {
    "status": "ok",
    "compare_count": len(pairwise_paths),
    "run_groups": run_groups,
    "pairwise_compares": pairwise_paths,
    "dimension_ids": dimension_ids,
    "source_kind": "derived_v1",
    "confidence": "medium",
    "redaction_state": "safe",
    "evidence_refs": [f"run_group:{group}" for group in run_groups],
}
(out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(summary, indent=2, sort_keys=True))
PY

echo "compare-agent-runs complete: $OUT/summary.json"
