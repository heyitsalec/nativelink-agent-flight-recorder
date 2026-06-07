#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${NLFR_LOCAL_EXEC_OUTPUT:-"$ROOT/data/local-exec-proof"}"
DB="$OUT/nlfr/nlfr.sqlite"
PROJECTIONS="$OUT/projections"
CONFIG="${NLFR_NATIVELINK_CONFIG:-"$ROOT/demo/nativelink/local-execution.json5"}"
TARGET="${NLFR_LOCAL_EXEC_TARGET:-"//tasks:priority_test"}"
REMOTE_CACHE="${NLFR_REMOTE_CACHE:-"grpc://127.0.0.1:50051"}"
REMOTE_EXECUTOR="${NLFR_REMOTE_EXECUTOR:-"grpc://127.0.0.1:50051"}"
NATIVELINK_BIN="${NLFR_NATIVELINK_BIN:-$(command -v nativelink || command -v native-link || true)}"
BAZEL_BIN="${NLFR_BAZEL_BIN:-$(command -v bazel || command -v bazelisk || true)}"
CACHE_ROOT="${NLFR_LOCAL_EXEC_CACHE_ROOT:-/tmp/nlfr-nativelink/local-exec}"
EXPECTED_WORKERS="${NLFR_EXPECTED_WORKERS:-1}"
BAZEL_ARGS=()
if [[ -n "${NLFR_BAZEL_ARGS:-}" ]]; then
  read -r -a BAZEL_ARGS <<<"$NLFR_BAZEL_ARGS"
fi

cd "$ROOT"
mkdir -p "$OUT" "$PROJECTIONS"

write_blocker() {
  local reason="$1"
  REASON="$reason" OUT_PATH="$OUT/environment-blocker.json" python3 - <<'PY'
import json
import os
from pathlib import Path

evidence_refs = ["script:local-exec-proof.sh"]
if (Path(os.environ["OUT_PATH"]).parent / "worker-readiness.json").exists():
    evidence_refs.append("worker-readiness.json")
payload = {
    "status": "environment_blocker",
    "reason": os.environ["REASON"],
    "source_kind": "collectable_v1",
    "confidence": "high",
    "redaction_state": "safe",
    "evidence_refs": evidence_refs,
}
path = Path(os.environ["OUT_PATH"])
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
print(f"environment blocker recorded: {path}")
PY
}

write_worker_readiness() {
  local phase="$1"
  local public_port="$2"
  local worker_api_port="$3"
  local -a readiness_cmd=(
    python3 "$ROOT/scripts/worker-readiness.py"
    --config "$CONFIG"
    --output "$OUT/worker-readiness.json"
    --expected-workers "$EXPECTED_WORKERS"
    --phase "$phase"
  )
  if [[ "$public_port" == "open" ]]; then
    readiness_cmd+=(--public-port-open)
  fi
  if [[ "$worker_api_port" == "open" ]]; then
    readiness_cmd+=(--worker-api-port-open)
  fi
  if [[ -f "$OUT/nativelink.stdout.txt" ]]; then
    readiness_cmd+=(--evidence-ref nativelink.stdout.txt)
  fi
  if [[ -f "$OUT/nativelink.stderr.txt" ]]; then
    readiness_cmd+=(--evidence-ref nativelink.stderr.txt)
  fi
  "${readiness_cmd[@]}"
}

if ! write_worker_readiness preflight closed closed; then
  exit 2
fi

if [[ -z "$NATIVELINK_BIN" ]]; then
  write_blocker "missing nativelink or native-link on PATH; run this inside nix develop or the devcontainer"
  exit 2
fi

if [[ -z "$BAZEL_BIN" ]]; then
  write_blocker "missing bazel or bazelisk on PATH; run this inside nix develop or the devcontainer"
  exit 2
fi

rm -rf "$CACHE_ROOT" "$OUT/nlfr" "$OUT/bazel-output-local-exec"
mkdir -p "$CACHE_ROOT" "$OUT/nlfr"

echo "== Start NativeLink one-process remote-executor smoke =="
"$NATIVELINK_BIN" "$CONFIG" >"$OUT/nativelink.stdout.txt" 2>"$OUT/nativelink.stderr.txt" &
NL_PID=$!
cleanup() {
  if kill -0 "$NL_PID" >/dev/null 2>&1; then
    kill "$NL_PID" >/dev/null 2>&1 || true
    wait "$NL_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

if ! python3 - <<'PY'
import socket
import time

def ready(port):
    sock = socket.socket()
    sock.settimeout(0.4)
    try:
        sock.connect(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        sock.close()

deadline = time.time() + 20
while time.time() < deadline:
    if ready(50051) and ready(50061):
        raise SystemExit(0)
    time.sleep(0.25)
raise SystemExit(1)
PY
then
  echo "NativeLink local execution ports did not open; stderr follows" >&2
  sed -n '1,160p' "$OUT/nativelink.stderr.txt" >&2 || true
  write_worker_readiness ports closed closed || true
  exit 1
fi

write_worker_readiness ports open open

echo "== Run Bazel through NativeLink local execution =="
RUN_CMD=(
  uv run python -m nlfr run
  --scenario local-exec-proof
  --run-group local-exec
  --mode local-exec
  --workspace "$ROOT/demo/bazel-monorepo"
  --output-dir "$OUT/nlfr"
  --skip-nativelink
  --bazel-executable "$BAZEL_BIN"
  --bazel-startup-arg=--output_base="$OUT/bazel-output-local-exec"
  --remote-cache "$REMOTE_CACHE"
  --remote-executor "$REMOTE_EXECUTOR"
  --json
)
if ((${#BAZEL_ARGS[@]} > 0)); then
  for arg in "${BAZEL_ARGS[@]}"; do
    RUN_CMD+=("--bazel-arg=$arg")
  done
fi
RUN_CMD+=("$TARGET")
PYTHONPATH=src "${RUN_CMD[@]}" >"$OUT/local-exec-run.json"

ARTIFACT_ROOT="$(
  ROOT_PATH="$OUT/local-exec-run.json" python3 - <<'PY'
import json
import os
from pathlib import Path

payload = json.loads(Path(os.environ["ROOT_PATH"]).read_text())
print(payload["artifact_root"])
PY
)"

echo "== Attach local-exec evidence =="
OUT_ROOT="$OUT" ARTIFACT_ROOT="$ARTIFACT_ROOT" PYTHONPATH=src \
  uv run python - <<'PY'
import os
from pathlib import Path

from nlfr.artifacts import write_artifact

out_root = Path(os.environ["OUT_ROOT"])
artifact_root = Path(os.environ["ARTIFACT_ROOT"])
attachments = (
    ("worker-readiness.json", out_root / "worker-readiness.json"),
    ("nativelink.stdout.txt", out_root / "nativelink.stdout.txt"),
    ("nativelink.stderr.txt", out_root / "nativelink.stderr.txt"),
)
for artifact_key, source_path in attachments:
    if not source_path.exists():
        continue
    write_artifact(
        artifact_root,
        artifact_key=artifact_key,
        data=source_path.read_bytes(),
        producer_command=["scripts/local-exec-proof.sh"],
        config_hash=None,
        redaction_state="safe",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["script:local-exec-proof.sh", artifact_key],
    )
PY

echo "== Ingest local execution Bazel evidence =="
PYTHONPATH=src uv run python -m nlfr ingest "$ARTIFACT_ROOT" \
  --database "$DB" \
  --source-kind collectable_v1 \
  --json >"$OUT/local-exec-ingest.json"

echo "== Export local execution projections =="
PYTHONPATH=src uv run python -m nlfr graph export \
  --db "$DB" \
  --run-group local-exec \
  --output "$PROJECTIONS/action-graph.json"
PYTHONPATH=src uv run python -m nlfr runway export \
  --db "$DB" \
  --run-group local-exec \
  --output "$PROJECTIONS/runway.json"
PYTHONPATH=src uv run python -m nlfr proof export \
  --db "$DB" \
  --run-group local-exec \
  --output "$PROJECTIONS/proof.json"

SUMMARY_ROOT="$OUT" python3 - <<'PY'
import json
import os
from pathlib import Path

root = Path(os.environ["SUMMARY_ROOT"])
payload = json.loads((root / "local-exec-run.json").read_text())
summary = {
    "status": payload["status"],
    "run_id": payload["run_id"],
    "artifact_root": payload["artifact_root"],
    "mode": payload["mode"],
    "source_kind": "collectable_v1",
    "confidence": "high",
    "redaction_state": "safe",
    "evidence_refs": [
        "local-exec-run.json",
        "local-exec-ingest.json",
        "worker-readiness.json",
        "nativelink.stdout.txt",
        "nativelink.stderr.txt",
    ],
}
readiness_path = root / "worker-readiness.json"
if readiness_path.exists():
    readiness = json.loads(readiness_path.read_text())
    summary["worker_readiness"] = {
        "status": readiness["status"],
        "expected_workers": readiness["expected_workers"],
        "configured_workers": readiness["configured_workers"],
        "unsupported_claims": readiness["unsupported_claims"],
    }
(root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
print(json.dumps(summary, indent=2, sort_keys=True))
PY
