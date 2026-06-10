#!/usr/bin/env bash
set -euo pipefail

# LRE Nix toolchain proof — phase 3.
# Probes Nix-generated lre.bazelrc after flake LRE module wiring.
# Honest ceiling: lre_bazelrc_generated (not cache parity or fleet correlation).
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${NLFR_LRE_NIX_OUTPUT:-$ROOT/data/lre-nix-toolchain-proof}"
MONOREPO="$ROOT/demo/bazel-monorepo"
LRE_BAZELRC="${NLFR_LRE_BAZELRC:-$ROOT/lre.bazelrc}"
MONOREPO_LRE_BAZELRC="$MONOREPO/lre.bazelrc"
BAZEL_BIN="${NLFR_BAZEL_BIN:-$(command -v bazel || command -v bazelisk || true)}"
TRY_BUILD="${NLFR_LRE_NIX_TRY_BUILD:-auto}"

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
    "evidence_refs": [
        "script:lre-nix-toolchain-proof.sh",
        "docs/LRE_LINUX_PROOF.md",
        "flake.nix",
    ],
    "claim_boundary": {
        "supported": [
            "lre_substrate_ready via scripts/lre-proof.sh",
            "flake.nix LRE module wiring when nix develop runs",
        ],
        "unsupported_until_lre_bazelrc": [
            "hermetic Nix --config=lre Bazel builds",
            "local and remote cache hit parity",
            "fleet scheduler dashboards",
            "queue time and action placement correlation",
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
  LRE_BAZELRC="$LRE_BAZELRC" MONOREPO_LRE_BAZELRC="$MONOREPO_LRE_BAZELRC" OUT="$OUT" python3 - <<'PY'
import json
import os
import platform
import shutil
from datetime import datetime, timezone
from pathlib import Path

out = Path(os.environ["OUT"])
lre = Path(os.environ["LRE_BAZELRC"])
mono = Path(os.environ["MONOREPO_LRE_BAZELRC"])
probe = {
    "status": "probe",
    "recorded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "platform": platform.system().lower(),
    "machine": platform.machine(),
    "in_nix_shell": bool(os.environ.get("IN_NIX_SHELL")),
    "bazel_on_path": bool(shutil.which("bazel") or shutil.which("bazelisk")),
    "lre_bazelrc_present": lre.is_file(),
    "lre_bazelrc_path": "lre.bazelrc",
    "monorepo_lre_bazelrc_present": mono.is_file(),
    "monorepo_lre_bazelrc_path": "demo/bazel-monorepo/lre.bazelrc",
    "source_kind": "collectable_v1",
    "confidence": "high",
    "redaction_state": "safe",
    "evidence_refs": ["script:lre-nix-toolchain-proof.sh"],
}
(out / "probe.json").write_text(json.dumps(probe, indent=2, sort_keys=True) + "\n")
print(json.dumps(probe, indent=2))
PY
}

write_probe

if [[ ! -f "$LRE_BAZELRC" ]]; then
  write_blocker \
    "lre.bazelrc not found at repo root — run inside nix develop so flake LRE installationScript generates build:lre flags" \
    "nix develop --command ./scripts/lre-nix-toolchain-proof.sh"
fi

if [[ ! -f "$MONOREPO_LRE_BAZELRC" ]]; then
  cp "$LRE_BAZELRC" "$MONOREPO_LRE_BAZELRC"
fi

BUILD_ATTEMPTED=false
BUILD_OK=false
BUILD_TARGET=""
BUILD_SKIP_REASON=""

should_try_build() {
  case "$TRY_BUILD" in
    0|false|no|skip) return 1 ;;
    1|true|yes|force) return 0 ;;
    auto)
      [[ "$(uname -s)" == "Linux" && "$(uname -m)" == "x86_64" ]]
      ;;
    *) return 1 ;;
  esac
}

if should_try_build; then
  if [[ -z "$BAZEL_BIN" ]]; then
    BUILD_SKIP_REASON="bazel not on PATH"
  elif [[ ! -d "$MONOREPO" ]]; then
    BUILD_SKIP_REASON="demo/bazel-monorepo missing"
  else
    BUILD_ATTEMPTED=true
    BUILD_TARGET="@local-remote-execution//examples:lre-cc"
    if (cd "$MONOREPO" && "$BAZEL_BIN" build --config=lre "$BUILD_TARGET"); then
      BUILD_OK=true
    fi
  fi
else
  BUILD_SKIP_REASON="optional build skipped (requires x86_64-linux; set NLFR_LRE_NIX_TRY_BUILD=1 to force)"
fi

export OUT BUILD_ATTEMPTED BUILD_OK BUILD_TARGET BUILD_SKIP_REASON
python3 - <<'PY'
import json
import os
import platform
from datetime import datetime, timezone
from pathlib import Path

out = Path(os.environ["OUT"])
build_attempted = os.environ.get("BUILD_ATTEMPTED") == "true"
build_ok = os.environ.get("BUILD_OK") == "true"
build_target = os.environ.get("BUILD_TARGET") or None
build_skip = os.environ.get("BUILD_SKIP_REASON") or None

summary = {
    "status": "lre_bazelrc_generated",
    "source_kind": "collectable_v1",
    "confidence": "medium",
    "redaction_state": "safe",
    "evidence_refs": [
        "script:lre-nix-toolchain-proof.sh",
        "flake.nix",
        "demo/bazel-monorepo/.bazelrc",
        "demo/bazel-monorepo/MODULE.bazel",
    ],
    "lre_bazelrc_path": "lre.bazelrc",
    "monorepo_lre_bazelrc_path": "demo/bazel-monorepo/lre.bazelrc",
    "platform": platform.system().lower(),
    "machine": platform.machine(),
    "recorded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "build_config_lre": {
        "attempted": build_attempted,
        "succeeded": build_ok if build_attempted else None,
        "target": build_target,
        "skip_reason": build_skip,
    },
    "claim_boundary": {
        "supported": [
            "Nix devShell generates lre.bazelrc with build:lre flags",
            "demo/bazel-monorepo try-imports generated lre.bazelrc",
            "MODULE.bazel resolves @local-remote-execution at pinned NativeLink rev",
        ],
        "unsupported": [
            "hermetic local and remote cache hit parity",
            "nlfr run --bazel-arg=--config=lre end-to-end ingest",
            "aarch64-darwin full lre-cc builds",
            "fleet scheduler dashboards",
            "queue time and action placement correlation",
        ],
    },
}
(out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
print(json.dumps(summary, indent=2))
PY

echo "lre-nix-toolchain-proof complete: $OUT/summary.json"
