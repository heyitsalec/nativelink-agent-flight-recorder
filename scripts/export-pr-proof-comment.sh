#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_GROUP="${NLFR_PR_PROOF_RUN_GROUP:-latest}"
DB="${NLFR_PR_PROOF_DB:-$ROOT/data/record-proof/nlfr.sqlite}"
OUT="${NLFR_PR_PROOF_OUTPUT:-$ROOT/data/pr-proof-comment/proof-comment.md}"
PROJECTIONS_DIR="${NLFR_PR_PROOF_PROJECTIONS:-$(dirname "$DB")/projections}"
MANIFEST="${NLFR_PR_PROOF_MANIFEST:-$(dirname "$DB")/artifact_manifest.json}"

usage() {
  cat <<'EOF'
Export a redacted NLFR proof summary for PR comments.

Usage:
  ./scripts/export-pr-proof-comment.sh [--run-group GROUP] [--db PATH] [--output PATH]

Environment:
  NLFR_PR_PROOF_RUN_GROUP   run group (default: latest)
  NLFR_PR_PROOF_DB          SQLite path (default: data/record-proof/nlfr.sqlite)
  NLFR_PR_PROOF_OUTPUT      markdown output path
  NLFR_PR_PROOF_PROJECTIONS projection directory for path citations
  NLFR_PR_PROOF_MANIFEST    artifact manifest path

Exit codes:
  0  export succeeded; no validation failures (unsupported boundary labels are ok)
  1  export succeeded but validation failures were recorded
  2  missing database or CLI error
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --run-group)
      RUN_GROUP="${2:?--run-group requires a value}"
      shift 2
      ;;
    --db)
      DB="${2:?--db requires a value}"
      shift 2
      ;;
    --output)
      OUT="${2:?--output requires a value}"
      shift 2
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

cd "$ROOT"

if [[ ! -f "$DB" ]]; then
  echo "database missing: $DB" >&2
  exit 2
fi

mkdir -p "$(dirname "$OUT")"

GRAPH_PROJECTION="$PROJECTIONS_DIR/graph-projection.json"
PROOF_PROJECTION="$PROJECTIONS_DIR/proof-packet.json"
RUNWAY_PROJECTION="$PROJECTIONS_DIR/runway-projection.json"

OPTIONAL_ARGS=()
[[ -f "$MANIFEST" ]] && OPTIONAL_ARGS+=(--manifest "$MANIFEST")
[[ -f "$GRAPH_PROJECTION" ]] && OPTIONAL_ARGS+=(--graph-projection "$GRAPH_PROJECTION")
[[ -f "$PROOF_PROJECTION" ]] && OPTIONAL_ARGS+=(--proof-projection "$PROOF_PROJECTION")
[[ -f "$RUNWAY_PROJECTION" ]] && OPTIONAL_ARGS+=(--runway-projection "$RUNWAY_PROJECTION")

set +e
set +u
PYTHONPATH=src uv run python -m nlfr proof export \
  --format markdown \
  --run-group "$RUN_GROUP" \
  --db "$DB" \
  --output "$OUT" \
  --repo-root "$ROOT" \
  --fail-on-validation \
  "${OPTIONAL_ARGS[@]}"
set -u
status=$?
set -e

if [[ $status -eq 2 ]]; then
  exit 2
fi

echo "wrote PR proof comment: $OUT"
exit "$status"
