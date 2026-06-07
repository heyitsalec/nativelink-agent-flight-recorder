#!/usr/bin/env bash
set -euo pipefail

# Flip shared policy module for Act 2 feature slice (shared-module-change alignment).
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
POLICY="$ROOT/demo/bazel-monorepo/tasks/policy.py"
STATE=""
CHECK=false
RESTORE=false

usage() {
  cat <<'EOF'
Usage: tier1-feature-setup.sh [--state baseline|feature] [--check] [--restore]

  --state baseline  URGENT_THRESHOLD=90 (repo default)
  --state feature   URGENT_THRESHOLD=85 (shared-module-change patch)
  --check           Run scenario validation fallback or Bazel
  --restore         git checkout policy.py
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --state)
      STATE="$2"
      shift 2
      ;;
    --check)
      CHECK=true
      shift
      ;;
    --restore)
      RESTORE=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

write_baseline() {
  cat >"$POLICY" <<'PY'
URGENT_THRESHOLD = 90
NORMAL_THRESHOLD = 50
PY
}

write_feature() {
  cat >"$POLICY" <<'PY'
URGENT_THRESHOLD = 85
NORMAL_THRESHOLD = 50
PY
}

run_check() {
  if [[ "${NLFR_SKIP_BAZEL:-0}" == "1" ]]; then
    (cd "$ROOT" && uv run pytest demo/bazel-monorepo/tasks/priority_test.py -q)
  else
    (cd "$ROOT/demo/bazel-monorepo" && bazel test //tasks:priority_test)
  fi
}

if [[ "$RESTORE" == true ]]; then
  write_baseline
  echo "restored baseline: demo/bazel-monorepo/tasks/policy.py"
  exit 0
fi

if [[ -n "$STATE" ]]; then
  case "$STATE" in
    baseline)
      write_baseline
      ;;
    feature)
      write_feature
      ;;
    *)
      echo "error: --state must be baseline or feature" >&2
      exit 1
      ;;
  esac
  echo "wrote $STATE state to demo/bazel-monorepo/tasks/policy.py"
fi

if [[ "$CHECK" == true ]]; then
  run_check
fi
