#!/usr/bin/env bash
set -euo pipefail

# LRE proof path — probe NativeLink Local Remote Execution readiness.
# Honest ceiling today: local-exec smoke unless demo/nativelink/lre.json5 exists.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${NLFR_LRE_OUTPUT:-$ROOT/data/lre-proof}"
LRE_CONFIG="${NLFR_LRE_CONFIG:-$ROOT/demo/nativelink/lre.json5}"
NATIVELINK_BIN="${NLFR_NATIVELINK_BIN:-$(command -v nativelink || command -v native-link || true)}"
BAZEL_BIN="${NLFR_BAZEL_BIN:-$(command -v bazel || command -v bazelisk || true)}"

mkdir -p "$OUT"

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
    "evidence_refs": ["script:lre-proof.sh", "docs/LRE_LINUX_PROOF.md"],
    "claim_boundary": {
        "supported": ["cache-only proof", "local-exec remote_executor smoke", "two-worker endpoints ready"],
        "unsupported_until_lre_config": [
            "hermetic Nix toolchain parity across local and remote",
            "LRE cache hit rates across repos",
            "fleet scheduler dashboards",
        ],
    },
}
path = Path(os.environ["OUT_PATH"])
path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
print(json.dumps(payload, indent=2))
PY
  exit 2
}

write_probe() {
  LRE_CONFIG="$LRE_CONFIG" OUT="$OUT" python3 - <<'PY'
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

out = Path(os.environ["OUT"])
lre = os.environ.get("LRE_CONFIG", "")
probe = {
    "status": "probe",
    "recorded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "nativelink_on_path": bool(shutil.which("nativelink") or shutil.which("native-link")),
    "bazel_on_path": bool(shutil.which("bazel") or shutil.which("bazelisk")),
    "lre_config_present": Path(lre).is_file() if lre else False,
    "lre_config_path": "demo/nativelink/lre.json5",
    "source_kind": "collectable_v1",
    "confidence": "high",
    "redaction_state": "safe",
    "evidence_refs": ["script:lre-proof.sh"],
}
(out / "probe.json").write_text(json.dumps(probe, indent=2, sort_keys=True) + "\n")
print(json.dumps(probe, indent=2))
PY
}

LRE_CONFIG="$LRE_CONFIG" OUT="$OUT" write_probe

if [[ -z "$NATIVELINK_BIN" ]]; then
  write_blocker \
    "nativelink binary not on PATH" \
    "run inside nix develop where nativelink 1.3.x is provisioned"
fi

if [[ -z "$BAZEL_BIN" ]]; then
  write_blocker \
    "bazel not on PATH" \
    "run inside nix develop"
fi

if [[ ! -f "$LRE_CONFIG" ]]; then
  write_blocker \
    "LRE config not present at demo/nativelink/lre.json5 — NLFR demo kit stops at local-exec smoke (see scripts/local-exec-proof.sh)" \
    "add TraceMachina LRE json5 + Nix toolchain wiring per demo/nativelink/README.md Future full-LRE section, then re-run lre-proof.sh"
fi

echo "== LRE config found — delegate to local-exec smoke with LRE substrate =="
NLFR_NATIVELINK_CONFIG="$LRE_CONFIG" \
NLFR_LOCAL_EXEC_OUTPUT="$OUT/local-exec" \
NLFR_LOCAL_EXEC_CACHE_ROOT="/tmp/nlfr-nativelink/lre" \
NLFR_REMOTE_CACHE="grpc://127.0.0.1:50071" \
NLFR_REMOTE_EXECUTOR="grpc://127.0.0.1:50071" \
  "$ROOT/scripts/local-exec-proof.sh" >"$OUT/local-exec-run.json"

export OUT
python3 - <<'PY'
import json
import os
from datetime import datetime, timezone
from pathlib import Path

out = Path(os.environ["OUT"])
local_exec_summary = out / "local-exec" / "summary.json"
local_exec_payload = {}
if local_exec_summary.is_file():
    local_exec_payload = json.loads(local_exec_summary.read_text(encoding="utf-8"))

summary = {
    "status": "lre_substrate_ready",
    "source_kind": "collectable_v1",
    "confidence": "medium",
    "redaction_state": "safe",
    "evidence_refs": [
        "script:lre-proof.sh",
        "script:local-exec-proof.sh",
        "demo/nativelink/lre.json5",
    ],
    "lre_config": "demo/nativelink/lre.json5",
    "remote_cache": "grpc://127.0.0.1:50071",
    "remote_executor": "grpc://127.0.0.1:50071",
    "local_exec_summary": local_exec_payload.get("status"),
    "recorded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "claim_boundary": {
        "supported": [
            "LRE NativeLink server substrate configured",
            "remote_executor smoke with lre.json5 endpoints",
            "worker_endpoints_ready for one local worker",
        ],
        "unsupported_until_nix_lre_toolchain": [
            "hermetic Nix toolchain parity across local and remote",
            "generated lre.bazelrc / --config=lre cache hit parity",
            "fleet scheduler dashboards",
            "queue time and action placement correlation",
        ],
    },
}
(out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
print(json.dumps(summary, indent=2))
PY

echo "lre-proof complete: $OUT/summary.json"
echo "Optional phase-3 Nix toolchain probe: ./scripts/lre-nix-toolchain-proof.sh (run inside nix develop)"
