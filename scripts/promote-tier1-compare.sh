#!/usr/bin/env bash
set -euo pipefail

# Promote tier1 pairwise compare JSON into committed canvas projections.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPARE_ROOT="${NLFR_COMPARE_AGENT_OUTPUT:-$ROOT/data/compare-agent-runs}"
PAIR="${NLFR_TIER1_COMPARE_PAIR:-canvas-dev-vs-agent-bugfix-1}"
SRC="$COMPARE_ROOT/projections/compare-${PAIR}.json"
DEST="$ROOT/apps/canvas/public/projections/compare-projection.json"

usage() {
  cat <<'EOF'
Usage: promote-tier1-compare.sh [--pair NAME] [--dry-run]

Copy data/compare-agent-runs/projections/compare-<pair>.json to
apps/canvas/public/projections/compare-projection.json for canvas Compare lens.

Default pair: canvas-dev-vs-agent-bugfix-1

Run ./scripts/compare-agent-runs.sh first (live or dry-run does not produce JSON).
EOF
}

DRY_RUN=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --pair)
      PAIR="$2"
      SRC="$COMPARE_ROOT/projections/compare-${PAIR}.json"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

if [[ ! -f "$SRC" ]]; then
  echo "error: compare projection missing: $SRC" >&2
  echo "hint: run ./scripts/compare-agent-runs.sh" >&2
  exit 1
fi

if [[ "$DRY_RUN" == true ]]; then
  python3 -c "import json; json.load(open('$SRC'))"
  echo "dry-run ok: would copy $SRC -> $DEST"
  exit 0
fi

cp "$SRC" "$DEST"
python3 -c "import json; json.load(open('$DEST'))"
echo "promoted: $DEST <- $SRC"
