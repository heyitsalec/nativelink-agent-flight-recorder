#!/usr/bin/env bash
set -euo pipefail

# Flip demo/bazel-monorepo/tasks/priority_test.py between broken and fixed for Act 1.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="$ROOT/demo/bazel-monorepo/tasks/priority_test.py"
STATE=""
CHECK=false
RESTORE=false

usage() {
  cat <<'EOF'
Usage: tier1-bugfix-setup.sh [--state broken|fixed] [--check] [--restore]

  --state broken  Wrong backlog assertion (pytest fails)
  --state fixed   Correct backlog test (llm-bounded-patch hunk)
  --check         Run scenario validation (NLFR_SKIP_BAZEL=1 uses pytest fallback)
  --restore       git checkout priority_test.py
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

write_broken() {
  cat >"$TARGET" <<'PY'
from tasks.priority import describe_task, priority_band


def test_priority_band_marks_urgent_work():
    assert priority_band(95) == "urgent"


def test_describe_task_keeps_leaf_label_readable():
    assert describe_task("NLFR-3", 72) == "NLFR-3: normal"


def test_priority_band_marks_backlog_for_low_score():
    assert priority_band(10) == "urgent"
PY
}

write_fixed() {
  cat >"$TARGET" <<'PY'
from tasks.priority import describe_task, priority_band


def test_priority_band_marks_urgent_work():
    assert priority_band(95) == "urgent"


def test_describe_task_keeps_leaf_label_readable():
    assert describe_task("NLFR-3", 72) == "NLFR-3: normal"


def test_priority_band_marks_backlog_for_low_score():
    assert priority_band(10) == "backlog"
PY
}

run_check() {
  if [[ "${NLFR_SKIP_BAZEL:-0}" == "1" ]]; then
    (cd "$ROOT" && uv run pytest demo/bazel-monorepo/tasks/priority_test.py -q)
  else
    (cd "$ROOT/demo/bazel-monorepo" && bazel test //tasks:priority_test)
  fi
}

write_baseline() {
  cat >"$TARGET" <<'PY'
from tasks.priority import describe_task, priority_band


def test_priority_band_marks_urgent_work():
    assert priority_band(95) == "urgent"


def test_describe_task_keeps_leaf_label_readable():
    assert describe_task("NLFR-3", 72) == "NLFR-3: normal"
PY
}

if [[ "$RESTORE" == true ]]; then
  write_baseline
  echo "restored baseline: demo/bazel-monorepo/tasks/priority_test.py"
  exit 0
fi

if [[ -n "$STATE" ]]; then
  case "$STATE" in
    broken)
      write_broken
      ;;
    fixed)
      write_fixed
      ;;
    *)
      echo "error: --state must be broken or fixed" >&2
      exit 1
      ;;
  esac
  echo "wrote $STATE state to demo/bazel-monorepo/tasks/priority_test.py"
fi

if [[ "$CHECK" == true ]]; then
  run_check
fi
