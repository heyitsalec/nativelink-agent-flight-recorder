#!/usr/bin/env bash
set -euo pipefail

# Promote tier1 pairwise compare JSON into committed canvas projections.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPARE_ROOT="${NLFR_COMPARE_AGENT_OUTPUT:-$ROOT/data/compare-agent-runs}"
PAIR="${NLFR_TIER1_COMPARE_PAIR:-canvas-dev-vs-agent-bugfix-1}"
SRC="$COMPARE_ROOT/projections/compare-${PAIR}.json"
DEST="${NLFR_TIER1_COMPARE_DEST:-$ROOT/apps/canvas/public/projections/compare-projection.json}"
REDACT=(python3 "$ROOT/scripts/redact-projection.py")

usage() {
  cat <<'EOF'
Usage: promote-tier1-compare.sh [--pair NAME] [--dry-run]

Publish data/compare-agent-runs/projections/compare-<pair>.json to
apps/canvas/public/projections/compare-projection.json for the canvas Compare
lens, through the SAME redaction gate record-canvas-build.sh uses: the source is
scrubbed by scripts/redact-projection.py (redact write-mode) and the published
file is re-scanned with --check, so any surviving secret/PII/abs-path finding
aborts the publish (issue #58). --dry-run runs the --check scan only, writes
nothing. Override the destination with NLFR_TIER1_COMPARE_DEST.

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
  # --check the SOURCE (scan only, writes nothing): a would-be publish that
  # carries a finding fails here loudly instead of at real promotion time.
  "${REDACT[@]}" --check "$SRC"
  echo "dry-run ok: would redact + publish $SRC -> $DEST"
  exit 0
fi

# Publish through redact + --check (the record-canvas-build.sh gate). redact
# write-mode scrubs and deliberately passes some findings through (a
# secret-shaped KEY is reported, never rewritten); the --check re-scan of the
# published file then aborts loudly (set -e -> non-zero) if any finding survives.
"${REDACT[@]}" "$SRC" "$DEST"
"${REDACT[@]}" --check "$DEST"
echo "promoted: $DEST <- $SRC (redacted + --check clean)"
