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
    "evidence_refs": ["script:lre-proof.sh", "docs/dags/lre-proof.md"],
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

echo "== LRE config found — delegate to nlfr run local-exec with LRE config =="
NLFR_NATIVELINK_CONFIG="$LRE_CONFIG" \
NLFR_LOCAL_EXEC_OUTPUT="$OUT/local-exec" \
  "$ROOT/scripts/local-exec-proof.sh" >"$OUT/local-exec-run.json"

python3 - <<'PY'
import json
import os
from datetime import datetime, timezone
from pathlib import Path

out = Path(os.environ["OUT"])
summary = {
    "status": "completed",
    "source_kind": "collectable_v1",
    "confidence": "medium",
    "redaction_state": "safe",
    "evidence_refs": ["script:lre-proof.sh", "script:local-exec-proof.sh"],
    "lre_config": "demo/nativelink/lre.json5",
    "recorded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
}
(out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
print(json.dumps(summary, indent=2))
PY

echo "lre-proof complete: $OUT/summary.json"
