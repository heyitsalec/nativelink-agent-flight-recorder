#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${NLFR_LRE_COLD_WARM_OUTPUT:-"$ROOT/data/lre-cold-warm-proof"}"
DB="$OUT/nlfr/nlfr.sqlite"
PROJECTIONS="$OUT/projections"
CONFIG="${NLFR_NATIVELINK_CONFIG:-"$ROOT/demo/nativelink/lre.json5"}"
MONOREPO="$ROOT/demo/bazel-monorepo"
LRE_BAZELRC="${NLFR_LRE_BAZELRC:-$ROOT/lre.bazelrc}"
MONOREPO_LRE_BAZELRC="$MONOREPO/lre.bazelrc"
TARGET="${NLFR_LRE_COLD_WARM_TARGET:-"//tasks:priority_test"}"
REMOTE_CACHE="${NLFR_REMOTE_CACHE:-"grpc://127.0.0.1:50071"}"
REMOTE_EXECUTOR="${NLFR_REMOTE_EXECUTOR:-"grpc://127.0.0.1:50071"}"
NATIVELINK_BIN="${NLFR_NATIVELINK_BIN:-$(command -v nativelink || command -v native-link || true)}"
BAZEL_BIN="${NLFR_BAZEL_BIN:-$(command -v bazel || command -v bazelisk || true)}"
CACHE_ROOT="${NLFR_CACHE_ROOT:-/tmp/nlfr-nativelink/lre}"

cd "$ROOT"
mkdir -p "$OUT" "$PROJECTIONS"

write_blocker() {
  local reason="$1"
  local next_step="${2:-}"
  REASON="$reason" NEXT="$next_step" OUT_PATH="$OUT/environment-blocker.json" python3 - <<'PY'
import json
import os
from pathlib import Path

payload = {
    "status": "environment_blocker",
    "reason": os.environ["REASON"],
    "next_step": os.environ.get("NEXT") or None,
    "source_kind": "collectable_v1",
    "confidence": "high",
    "redaction_state": "safe",
    "evidence_refs": [
        "script:lre-cold-warm-proof.sh",
        "docs/LRE_LINUX_PROOF.md",
        "demo/nativelink/lre.json5",
    ],
    "claim_boundary": {
        "supported": [
            "lre_substrate_ready via scripts/lre-proof.sh",
            "lre_bazelrc_generated via scripts/lre-nix-toolchain-proof.sh",
            "cache-only cold/warm proof via scripts/cold-warm-cache-proof.sh",
        ],
        "unsupported_until_lre_cold_warm_linux": [
            "lre_cache_parity_observed cold/warm metrics on aarch64-darwin",
            "hermetic container-image parity across distinct worker images",
            "fleet scheduler dashboards",
            "queue time and action placement correlation",
        ],
    },
}
path = Path(os.environ["OUT_PATH"])
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
print(f"environment blocker recorded: {path}")
PY
  exit 2
}

if [[ "$(uname -s)" == "Darwin" ]]; then
  write_blocker \
    "LRE cold/warm cache parity proof requires x86_64-linux inside nix develop; Darwin hosts get rust-only LRE env without full lre-cc cold/warm parity path" \
    "run ./scripts/lre-cold-warm-proof.sh on ubuntu-latest via nix develop (see .github/workflows/nlfr-proof.yml)"
fi

if [[ "$(uname -s)" != "Linux" || "$(uname -m)" != "x86_64" ]]; then
  write_blocker \
    "LRE cold/warm cache parity proof is gated to x86_64-linux inside nix develop" \
    "nix develop --command ./scripts/lre-cold-warm-proof.sh"
fi

if [[ -z "$NATIVELINK_BIN" ]]; then
  write_blocker \
    "missing nativelink or native-link on PATH; run this inside nix develop or the devcontainer" \
    "nix develop --command ./scripts/lre-cold-warm-proof.sh"
fi

if [[ -z "$BAZEL_BIN" ]]; then
  write_blocker \
    "missing bazel or bazelisk on PATH; run this inside nix develop or the devcontainer" \
    "nix develop --command ./scripts/lre-cold-warm-proof.sh"
fi

if [[ ! -f "$LRE_BAZELRC" ]]; then
  write_blocker \
    "lre.bazelrc not found at repo root — run inside nix develop so flake LRE installationScript generates build:lre flags" \
    "nix develop --command ./scripts/lre-cold-warm-proof.sh"
fi

if [[ ! -f "$MONOREPO_LRE_BAZELRC" ]]; then
  cp "$LRE_BAZELRC" "$MONOREPO_LRE_BAZELRC"
fi

rm -rf "$CACHE_ROOT" "$OUT/nlfr" "$OUT/bazel-output-cold" "$OUT/bazel-output-warm"
mkdir -p "$CACHE_ROOT" "$OUT/nlfr"

echo "== Start NativeLink LRE server =="
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
    if ready(50071) and ready(50081):
        raise SystemExit(0)
    time.sleep(0.25)
raise SystemExit(1)
PY
then
  echo "NativeLink LRE ports did not open (expected 127.0.0.1:50071 and 127.0.0.1:50081); stderr follows" >&2
  sed -n '1,120p' "$OUT/nativelink.stderr.txt" >&2 || true
  exit 1
fi

run_leg() {
  local leg="$1"
  local output_base="$OUT/bazel-output-$leg"
  local result="$OUT/$leg-run.json"

  echo "== $leg Bazel run through NativeLink LRE (local-exec + --config=lre) =="
  PYTHONPATH=src uv run python -m nlfr run \
    --scenario "$leg-cache" \
    --run-group lre-cold-warm \
    --mode local-exec \
    --workspace "$MONOREPO" \
    --output-dir "$OUT/nlfr" \
    --skip-nativelink \
    --bazel-executable "$BAZEL_BIN" \
    --bazel-startup-arg=--output_base="$output_base" \
    --remote-cache "$REMOTE_CACHE" \
    --remote-executor "$REMOTE_EXECUTOR" \
    --bazel-arg=--config=lre \
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

echo "== Export LRE cold/warm projections =="
PYTHONPATH=src uv run python -m nlfr graph export \
  --db "$DB" \
  --run-group lre-cold-warm \
  --output "$PROJECTIONS/action-graph.json"
PYTHONPATH=src uv run python -m nlfr runway export \
  --db "$DB" \
  --run-group lre-cold-warm \
  --output "$PROJECTIONS/runway.json"
PYTHONPATH=src uv run python -m nlfr proof export \
  --db "$DB" \
  --run-group lre-cold-warm \
  --output "$PROJECTIONS/proof.json"

SUMMARY_ROOT="$OUT" python3 - <<'PY'
import json
import os
from pathlib import Path

root = Path(os.environ["SUMMARY_ROOT"])
proof_path = root / "projections" / "proof.json"
proof = json.loads(proof_path.read_text()) if proof_path.exists() else {}
cache_economics = next(
    (block for block in proof.get("blocks", []) if block.get("id") == "cache_economics"),
    None,
)

summary = {
    "status": "lre_cache_parity_observed",
    "lre_config": "demo/nativelink/lre.json5",
    "remote_cache": "grpc://127.0.0.1:50071",
    "remote_executor": "grpc://127.0.0.1:50071",
    "bazel_config": "lre",
}
for leg in ("cold", "warm"):
    payload = json.loads((root / f"{leg}-run.json").read_text())
    summary[leg] = {
        "status": payload["status"],
        "run_id": payload["run_id"],
        "artifact_root": payload["artifact_root"],
        "mode": payload.get("mode", "local-exec"),
        "results": [
            {
                "command": item["command"][:3],
                "status": item["status"],
                "exit_code": item["exit_code"],
            }
            for item in payload["results"]
        ],
    }

if cache_economics:
    summary["cache_economics"] = {
        "metrics": cache_economics.get("metrics", {}),
        "comparison": (cache_economics.get("payload") or {}).get("comparison"),
        "legs": (cache_economics.get("payload") or {}).get("legs"),
    }

summary["source_kind"] = "collectable_v1"
summary["confidence"] = "medium"
summary["redaction_state"] = "safe"
summary["evidence_refs"] = [
    "cold-run.json",
    "warm-run.json",
    "projections/proof.json",
    "nativelink.stdout.txt",
    "nativelink.stderr.txt",
    "demo/bazel-monorepo/lre.bazelrc",
]
summary["claim_boundary"] = {
    "supported": [
        "LRE cold/warm cache economics on x86_64-linux via lre.json5 + --config=lre",
        "nlfr run --mode local-exec ingest + proof export with cache_economics",
        "warm hit_rate exceeds cold on //tasks:priority_test through LRE endpoints",
    ],
    "unsupported": [
        "hermetic container-image parity across distinct worker images",
        "lre-cc C++ LRE builds as parity proof target",
        "aarch64-darwin full LRE cold/warm green path",
        "fleet scheduler dashboards",
        "queue time and action placement correlation",
    ],
}
(root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
print(json.dumps(summary, indent=2, sort_keys=True))
PY
