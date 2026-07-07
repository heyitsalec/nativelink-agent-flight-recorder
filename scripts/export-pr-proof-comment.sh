#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_GROUP="${NLFR_PR_PROOF_RUN_GROUP:-latest}"
DB="${NLFR_PR_PROOF_DB:-$ROOT/data/record-proof/nlfr.sqlite}"
OUT="${NLFR_PR_PROOF_OUTPUT:-$ROOT/data/pr-proof-comment/proof-comment.md}"
PROJECTIONS_DIR="${NLFR_PR_PROOF_PROJECTIONS:-$(dirname "$DB")/projections}"
MANIFEST="${NLFR_PR_PROOF_MANIFEST:-$(dirname "$DB")/artifact_manifest.json}"
COMPACT=0
JSON_OUT="${NLFR_PR_PROOF_JSON_OUTPUT:-}"
IN_TOTO="${NLFR_PR_PROOF_IN_TOTO:-}"

usage() {
  cat <<'EOF'
Export a redacted NLFR proof summary for PR comments.

Usage:
  ./scripts/export-pr-proof-comment.sh [--run-group GROUP] [--db PATH] [--output PATH]
  ./scripts/export-pr-proof-comment.sh --compact [--json-output PATH] [--in-toto PATH]

Modes:
  (default)   verbose per-block markdown  (nlfr proof export --format markdown)
  --compact   scannable PR-comment summary + JSON sidecar  (nlfr proof comment),
              then GATE both artifacts through `nlfr redact --check` before
              reporting success — a leak here is the #71 class and must never post.

Options:
  --run-group GROUP   run group (default: latest)
  --db PATH           SQLite path (default: data/record-proof/nlfr.sqlite)
  --output PATH       markdown output path
  --json-output PATH  (compact) JSON sidecar path (default: <output stem>.json)
  --in-toto PATH      (compact) exported in-toto attestation to cite by digest

Environment:
  NLFR_PR_PROOF_RUN_GROUP   run group (default: latest)
  NLFR_PR_PROOF_DB          SQLite path (default: data/record-proof/nlfr.sqlite)
  NLFR_PR_PROOF_OUTPUT      markdown output path
  NLFR_PR_PROOF_JSON_OUTPUT (compact) JSON sidecar path
  NLFR_PR_PROOF_IN_TOTO     (compact) in-toto attestation path
  NLFR_PR_PROOF_PROJECTIONS projection directory for path citations
  NLFR_PR_PROOF_MANIFEST    artifact manifest path

Exit codes:
  0  export succeeded; no validation failures (unsupported boundary labels are ok)
  1  export succeeded but validation failures were recorded
  2  missing database or CLI error
  3  compact only: the redact gate found a leak — the artifacts were NOT cleared
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
    --json-output)
      JSON_OUT="${2:?--json-output requires a value}"
      shift 2
      ;;
    --in-toto)
      IN_TOTO="${2:?--in-toto requires a value}"
      shift 2
      ;;
    --compact)
      COMPACT=1
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

cd "$ROOT"

if [[ ! -f "$DB" ]]; then
  echo "database missing: $DB" >&2
  exit 2
fi

mkdir -p "$(dirname "$OUT")"

if [[ "$COMPACT" -eq 1 ]]; then
  # Compact PR-comment summary + machine-readable JSON sidecar (issue #87).
  : "${JSON_OUT:=${OUT%.md}.json}"
  mkdir -p "$(dirname "$JSON_OUT")"

  COMPACT_ARGS=()
  [[ -n "$IN_TOTO" ]] && COMPACT_ARGS+=(--in-toto "$IN_TOTO")

  set +e
  set +u
  PYTHONPATH=src uv run python -m nlfr proof comment \
    --run-group "$RUN_GROUP" \
    --db "$DB" \
    --output "$OUT" \
    --json-output "$JSON_OUT" \
    --fail-on-validation \
    "${COMPACT_ARGS[@]}"
  set -u
  status=$?
  set -e

  if [[ $status -eq 2 ]]; then
    exit 2
  fi

  # Redact gate: the projection/redaction layer is the sharing boundary, so NEVER
  # post an artifact that has not cleared `nlfr redact --check`. This is the last
  # line of defense before a PR comment goes out.
  for artifact in "$OUT" "$JSON_OUT"; do
    if ! PYTHONPATH=src uv run python -m nlfr redact --check "$artifact"; then
      echo "redact gate FAILED for $artifact — refusing to clear it for posting" >&2
      exit 3
    fi
  done

  echo "wrote compact PR proof comment: $OUT"
  echo "wrote JSON sidecar: $JSON_OUT"
  echo "redact --check gate: OK for both artifacts"
  exit "$status"
fi

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
