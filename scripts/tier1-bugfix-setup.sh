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
  --restore       rewrite priority_test.py to the committed baseline content
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

if __name__ == "__main__":
    # py_test executes this file as a script: without a main block the
    # test functions above are DEFINED but never CALLED, so the target is
    # vacuously green no matter what breaks (found by the validation-layer
    # repair-loop work, which needed a lane that can actually go red).
    # Stdlib-only runner, same discipline as the rest of the repo.
    import sys
    import traceback

    _failures = 0
    for _name in sorted(list(globals())):
        if _name.startswith("test_") and callable(globals()[_name]):
            try:
                globals()[_name]()
                print(f"PASS {_name}")
            except Exception:  # noqa: BLE001 - report and count every failure
                traceback.print_exc()
                print(f"FAIL {_name}")
                _failures += 1
    sys.exit(1 if _failures else 0)
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

if __name__ == "__main__":
    # py_test executes this file as a script: without a main block the
    # test functions above are DEFINED but never CALLED, so the target is
    # vacuously green no matter what breaks (found by the validation-layer
    # repair-loop work, which needed a lane that can actually go red).
    # Stdlib-only runner, same discipline as the rest of the repo.
    import sys
    import traceback

    _failures = 0
    for _name in sorted(list(globals())):
        if _name.startswith("test_") and callable(globals()[_name]):
            try:
                globals()[_name]()
                print(f"PASS {_name}")
            except Exception:  # noqa: BLE001 - report and count every failure
                traceback.print_exc()
                print(f"FAIL {_name}")
                _failures += 1
    sys.exit(1 if _failures else 0)
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


if __name__ == "__main__":
    # py_test executes this file as a script: without a main block the
    # test functions above are DEFINED but never CALLED, so the target is
    # vacuously green no matter what breaks (found by the validation-layer
    # repair-loop work, which needed a lane that can actually go red).
    # Stdlib-only runner, same discipline as the rest of the repo.
    import sys
    import traceback

    _failures = 0
    for _name in sorted(list(globals())):
        if _name.startswith("test_") and callable(globals()[_name]):
            try:
                globals()[_name]()
                print(f"PASS {_name}")
            except Exception:  # noqa: BLE001 - report and count every failure
                traceback.print_exc()
                print(f"FAIL {_name}")
                _failures += 1
    sys.exit(1 if _failures else 0)
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
