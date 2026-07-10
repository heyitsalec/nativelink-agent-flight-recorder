#!/usr/bin/env bash
set -euo pipefail

# Agentic loop closure proof — NLFR evaluates its own truth data, reasons about
# the next step, and drives the fix.
#
# This is the native successor to the decision spine of
# scripts/two-act-spark-proof.sh: environment bring-up (NativeLink cache-only
# server) stays here, but every decision — red/green, honest-failure
# classification, what evidence the fixing agent receives, when to stop — is
# made by `nlfr loop` from recorded evidence and truth-labeled verdicts
# (`nlfr evaluate --record`). The bash below contains NO branching on build
# results.
#
# Stub mode (mechanics proof without a live LLM):
#   NLFR_LOOP_CLAUDE_BIN=scripts/spark-stub-claude.sh \
#   NLFR_LOOP_OUTPUT=$PWD/data/agentic-loop-stub ./scripts/agentic-loop-proof.sh
# Live mode uses the real `claude` CLI (receipt_verified_v1 agent legs).

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${NLFR_LOOP_OUTPUT:-"$ROOT/data/agentic-loop-proof"}"
SCENARIO="${NLFR_LOOP_SCENARIO:-two-act-underspec}"
CLAUDE_BIN="${NLFR_LOOP_CLAUDE_BIN:-claude}"
MODEL_ARGS=()
if [[ -n "${NLFR_LOOP_MODEL:-}" ]]; then
  MODEL_ARGS=(--model "$NLFR_LOOP_MODEL")
fi
CONFIG="${NLFR_NATIVELINK_CONFIG:-"$ROOT/demo/nativelink/cache-only.json"}"
REMOTE_CACHE="${NLFR_REMOTE_CACHE:-"grpc://127.0.0.1:50051"}"
NATIVELINK_BIN="${NLFR_NATIVELINK_BIN:-$(command -v nativelink || command -v native-link || true)}"
BAZEL_BIN="${NLFR_BAZEL_BIN:-$(command -v bazel || command -v bazelisk || true)}"
CACHE_ROOT="${NLFR_LOOP_CACHE_ROOT:-/tmp/nlfr-nativelink/loop-cache-only}"

cd "$ROOT"
rm -rf "$OUT"
mkdir -p "$OUT"
export PYTHONPATH="$ROOT/src"

write_blocker() {
  REASON="$1" OUT_PATH="$OUT/environment-blocker.json" python3 - <<'PY'
import json
import os
from pathlib import Path

payload = {
    "status": "environment_blocker",
    "reason": os.environ["REASON"],
    "source_kind": "collectable_v1",
    "confidence": "high",
    "redaction_state": "safe",
    "evidence_refs": ["script:agentic-loop-proof.sh"],
}
path = Path(os.environ["OUT_PATH"])
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
print(f"environment blocker recorded: {path}")
PY
}

if [[ -z "$NATIVELINK_BIN" ]]; then
  write_blocker "missing nativelink or native-link on PATH; run this inside nix develop"
  exit 2
fi
if [[ -z "$BAZEL_BIN" ]]; then
  write_blocker "missing bazel or bazelisk on PATH; run this inside nix develop"
  exit 2
fi

NL_PID=""
cleanup() {
  if [[ -n "$NL_PID" ]] && kill -0 "$NL_PID" >/dev/null 2>&1; then
    kill "$NL_PID" >/dev/null 2>&1 || true
    wait "$NL_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

echo "== Start NativeLink cache-only server (fresh cache root) =="
rm -rf "$CACHE_ROOT"
mkdir -p "$CACHE_ROOT"
"$NATIVELINK_BIN" "$CONFIG" >"$OUT/nativelink.stdout.txt" 2>"$OUT/nativelink.stderr.txt" &
NL_PID=$!

if ! python3 - <<'PY'
import socket
import time

deadline = time.time() + 15
while time.time() < deadline:
    sock = socket.socket()
    sock.settimeout(0.4)
    try:
        sock.connect(("127.0.0.1", 50051))
        raise SystemExit(0)
    except OSError:
        time.sleep(0.25)
    finally:
        sock.close()
raise SystemExit(1)
PY
then
  echo "NativeLink did not open 127.0.0.1:50051; stderr follows" >&2
  sed -n '1,120p' "$OUT/nativelink.stderr.txt" >&2 || true
  exit 1
fi

echo "== nlfr loop: evaluate → fix → revalidate, decisions from recorded evidence =="
LOOP_RC=0
uv run python -m nlfr loop \
  --scenario "$SCENARIO" \
  --mode cache-only \
  --skip-nativelink \
  --remote-cache "$REMOTE_CACHE" \
  --claude-bin "$CLAUDE_BIN" \
  --bazel-bin "$BAZEL_BIN" \
  "${MODEL_ARGS[@]}" \
  --run-group-prefix agentic-loop \
  --output-dir "$OUT" || LOOP_RC=$?

echo "== Redaction gate: no raw prompt text may appear in any output artifact =="
OUT_DIR="$OUT" SCENARIO_NAME="$SCENARIO" ROOT_DIR="$ROOT" python3 - <<'PY'
import json
import os
from pathlib import Path

root = Path(os.environ["ROOT_DIR"])
scenario_name = os.environ["SCENARIO_NAME"]
scenario_path = Path(scenario_name)
if scenario_path.suffix != ".json" or not scenario_path.is_file():
    scenario_path = root / "demo" / "scenarios" / f"{scenario_name}.json"
scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
needles = [
    "You are a coding agent",
    scenario["task_spec"][:80],
    scenario["output_contract"][:80],
]
leaks = []
for path in sorted(Path(os.environ["OUT_DIR"]).rglob("*")):
    if not path.is_file() or path.suffix not in {".json", ".md", ".txt"}:
        continue
    if path.name.endswith("-response.md"):
        continue  # agent OUTPUT is recorded evidence; prompts must not leak
    text = path.read_text(encoding="utf-8", errors="replace")
    for needle in needles:
        if needle and needle in text:
            leaks.append(f"{path}: {needle[:40]!r}")
print(f"redaction scan: leaks={leaks!r}")
if leaks:
    raise SystemExit("raw prompt text leaked into output artifacts")
PY

echo "== Loop summary =="
python3 -m json.tool "$OUT/loop-summary.json" | sed -n '1,60p'
echo "nlfr loop exit code: $LOOP_RC"
exit "$LOOP_RC"
