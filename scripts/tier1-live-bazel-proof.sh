#!/usr/bin/env bash
set -euo pipefail

# Tier 1 live Bazel proof — acts 1+2 via tier1-agent-demo with real Bazel validation.
# Run inside `nix develop` (bazel + demo monorepo on PATH).
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${NLFR_TIER1_LIVE_BAZEL_OUTPUT:-$ROOT/data/tier1-live-bazel}"
MONOREPO="$ROOT/demo/bazel-monorepo"
ACT1_OUT="$ROOT/data/agent-bugfix-1"
ACT2_OUT="$ROOT/data/agent-feature-compare"
BAZEL_BIN="${NLFR_BAZEL_BIN:-$(command -v bazel || command -v bazelisk || true)}"

mkdir -p "$OUT"

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
    "evidence_refs": ["script:tier1-live-bazel-proof.sh"],
    "scenario_ids": ["agent-bugfix-1", "agent-feature-compare"],
}
path = Path(os.environ["OUT_PATH"])
path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
print(json.dumps(payload, indent=2, sort_keys=True))
PY
  exit 2
}

if [[ -z "$BAZEL_BIN" ]]; then
  write_blocker "missing bazel or bazelisk on PATH; run inside nix develop"
fi

if [[ ! -d "$MONOREPO" ]]; then
  write_blocker "demo/bazel-monorepo missing"
fi

unset NLFR_SKIP_BAZEL

echo "== Tier1 Act 1 — bugfix setup + live agent demo =="
ACT1_OK=false
if "$ROOT/scripts/tier1-bugfix-setup.sh" --state fixed && \
   "$ROOT/scripts/tier1-agent-demo.sh" --act 1; then
  ACT1_OK=true
fi
"$ROOT/scripts/tier1-bugfix-setup.sh" --restore

echo "== Tier1 Act 2 — feature setup + live agent demo =="
ACT2_OK=false
if "$ROOT/scripts/tier1-feature-setup.sh" --state feature && \
   "$ROOT/scripts/tier1-agent-demo.sh" --act 2; then
  ACT2_OK=true
fi
"$ROOT/scripts/tier1-feature-setup.sh" --restore

if [[ "$ACT1_OK" != true || "$ACT2_OK" != true ]]; then
  write_blocker "tier1 agent demo act 1 and/or act 2 failed with live Bazel validation"
fi

if [[ ! -f "$ACT1_OUT/summary.json" || ! -f "$ACT2_OUT/summary.json" ]]; then
  write_blocker "missing act summary.json after live tier1 demo (agent-bugfix-1 and/or agent-feature-compare)"
fi

ROOT="$ROOT" OUT="$OUT" ACT1_OUT="$ACT1_OUT" ACT2_OUT="$ACT2_OUT" BAZEL_BIN="$BAZEL_BIN" python3 - <<'PY'
import json
import os
from datetime import datetime, timezone
from pathlib import Path

root = Path(os.environ["ROOT"])
out = Path(os.environ["OUT"])
act1_out = Path(os.environ["ACT1_OUT"])
act2_out = Path(os.environ["ACT2_OUT"])
act1 = json.loads((act1_out / "summary.json").read_text(encoding="utf-8"))
act2 = json.loads((act2_out / "summary.json").read_text(encoding="utf-8"))


def act_entry(act_summary: dict, output_dir: Path) -> dict:
    return {
        "agent_demo": "completed",
        "run_group": act_summary.get("run_group"),
        "run_id": act_summary.get("run_id"),
        "status": act_summary.get("status"),
        "validation": "bazel",
        "validation_source_kind": act_summary.get("validation_source_kind"),
        "output_dir": str(output_dir.relative_to(root)),
        "summary_path": str((output_dir / "summary.json").relative_to(root)),
    }


summary = {
    "status": "completed",
    "source_kind": "collectable_v1",
    "confidence": "high",
    "redaction_state": "safe",
    "validation": "bazel",
    "bazel_bin": os.environ.get("BAZEL_BIN", "bazel"),
    "evidence_refs": [
        "script:tier1-live-bazel-proof.sh",
        "scenario:agent-bugfix-1",
        "scenario:agent-feature-compare",
        "data/agent-bugfix-1/summary.json",
        "data/agent-feature-compare/summary.json",
    ],
    "acts": {
        "agent-bugfix-1": act_entry(act1, act1_out),
        "agent-feature-compare": act_entry(act2, act2_out),
    },
    "recorded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
}
(out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
print(json.dumps(summary, indent=2, sort_keys=True))
PY

echo "tier1-live-bazel-proof complete: $OUT/summary.json"
