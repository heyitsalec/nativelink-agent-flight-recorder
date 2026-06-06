#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${NLFR_COLD_WARM_OUTPUT:-"$ROOT/data/cold-warm-proof"}"
DB="$OUT/nlfr/nlfr.sqlite"
PROJECTIONS="$OUT/projections"
CONFIG="${NLFR_NATIVELINK_CONFIG:-"$ROOT/demo/nativelink/cache-only.json"}"
TARGET="${NLFR_COLD_WARM_TARGET:-"//tasks:priority_test"}"
REMOTE_CACHE="${NLFR_REMOTE_CACHE:-"grpc://127.0.0.1:50051"}"
NATIVELINK_BIN="${NLFR_NATIVELINK_BIN:-$(command -v nativelink || command -v native-link || true)}"
BAZEL_BIN="${NLFR_BAZEL_BIN:-$(command -v bazel || command -v bazelisk || true)}"
CACHE_ROOT="${NLFR_CACHE_ROOT:-/tmp/nlfr-nativelink/cache-only}"

cd "$ROOT"
mkdir -p "$OUT" "$PROJECTIONS"

write_blocker() {
  local reason="$1"
  REASON="$reason" OUT_PATH="$OUT/environment-blocker.json" python3 - <<'PY'
import json
import os
from pathlib import Path

payload = {
    "status": "environment_blocker",
    "reason": os.environ["REASON"],
    "source_kind": "collectable_v1",
    "confidence": "high",
    "redaction_state": "safe",
    "evidence_refs": ["script:cold-warm-cache-proof.sh"],
}
path = Path(os.environ["OUT_PATH"])
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
print(f"environment blocker recorded: {path}")
PY
}

if [[ -z "$NATIVELINK_BIN" ]]; then
  write_blocker "missing nativelink or native-link on PATH; run this inside nix develop or the devcontainer"
  exit 2
fi

if [[ -z "$BAZEL_BIN" ]]; then
  write_blocker "missing bazel or bazelisk on PATH; run this inside nix develop or the devcontainer"
  exit 2
fi

rm -rf "$CACHE_ROOT" "$OUT/nlfr" "$OUT/bazel-output-cold" "$OUT/bazel-output-warm"
mkdir -p "$CACHE_ROOT" "$OUT/nlfr"

echo "== Start NativeLink cache-only server =="
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

run_leg() {
  local leg="$1"
  local output_base="$OUT/bazel-output-$leg"
  local result="$OUT/$leg-run.json"

  echo "== $leg Bazel run through NativeLink cache =="
  PYTHONPATH=src uv run python -m nlfr run \
    --scenario "$leg-cache" \
    --run-group cold-warm \
    --workspace "$ROOT/demo/bazel-monorepo" \
    --output-dir "$OUT/nlfr" \
    --skip-nativelink \
    --bazel-executable "$BAZEL_BIN" \
    --bazel-startup-arg "--output_base=$output_base" \
    --remote-cache "$REMOTE_CACHE" \
    --json \
    "$TARGET" >"$result"
}

artifact_root_for_leg() {
  local leg="$1"
  LEG="$leg" ROOT="$OUT" python3 - <<'PY'
import json
import os
from pathlib import Path

payload = json.loads((Path(os.environ["ROOT"]) / f"{os.environ['LEG']}-run.json").read_text())
artifact_root = payload.get("artifact_root")
if not artifact_root:
    raise SystemExit(f"missing artifact_root in {os.environ['LEG']}-run.json")
print(artifact_root)
PY
}

ingest_leg() {
  local leg="$1"
  local artifact_root
  artifact_root="$(artifact_root_for_leg "$leg")"

  echo "== Ingest $leg Bazel evidence =="
  PYTHONPATH=src uv run python -m nlfr ingest "$artifact_root" \
    --database "$DB" \
    --source-kind collectable_v1 \
    --json >"$OUT/$leg-ingest.json"
}

run_leg cold
run_leg warm
ingest_leg cold
ingest_leg warm

echo "== Export cold/warm projections =="
PYTHONPATH=src uv run python -m nlfr graph export \
  --db "$DB" \
  --run-group cold-warm \
  --output "$PROJECTIONS/action-graph.json"
PYTHONPATH=src uv run python -m nlfr runway export \
  --db "$DB" \
  --run-group cold-warm \
  --output "$PROJECTIONS/runway.json"
PYTHONPATH=src uv run python -m nlfr proof export \
  --db "$DB" \
  --run-group cold-warm \
  --output "$PROJECTIONS/proof.json"

SUMMARY_ROOT="$OUT" python3 - <<'PY'
import json
import os
from pathlib import Path

root = Path(os.environ["SUMMARY_ROOT"])
summary = {}
for leg in ("cold", "warm"):
    payload = json.loads((root / f"{leg}-run.json").read_text())
    summary[leg] = {
        "status": payload["status"],
        "run_id": payload["run_id"],
        "artifact_root": payload["artifact_root"],
        "results": [
            {
                "command": item["command"][:3],
                "status": item["status"],
                "exit_code": item["exit_code"],
            }
            for item in payload["results"]
        ],
    }
summary["source_kind"] = "collectable_v1"
summary["confidence"] = "high"
summary["redaction_state"] = "safe"
summary["evidence_refs"] = ["cold-run.json", "warm-run.json", "nativelink.stdout.txt", "nativelink.stderr.txt"]
(root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
print(json.dumps(summary, indent=2, sort_keys=True))
PY
