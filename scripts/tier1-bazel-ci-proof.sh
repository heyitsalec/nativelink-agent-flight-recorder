#!/usr/bin/env bash
set -euo pipefail

# Tier 1 Bazel validation — run inside `nix develop` (bazel + demo monorepo).
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${NLFR_TIER1_BAZEL_OUTPUT:-$ROOT/data/tier1-bazel-ci}"
MONOREPO="$ROOT/demo/bazel-monorepo"
TARGET="${NLFR_TIER1_BAZEL_TARGET:-//tasks:priority_test}"
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
    "evidence_refs": ["script:tier1-bazel-ci-proof.sh"],
    "scenario_ids": ["agent-bugfix-1", "agent-feature-compare"],
}
path = Path(os.environ["OUT_PATH"])
path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
print(f"environment blocker recorded: {path}")
PY
  exit 2
}

if [[ -z "$BAZEL_BIN" ]]; then
  write_blocker "missing bazel or bazelisk on PATH; run inside nix develop"
fi

if [[ ! -d "$MONOREPO" ]]; then
  write_blocker "demo/bazel-monorepo missing"
fi

run_bazel() {
  (cd "$MONOREPO" && "$BAZEL_BIN" test "$TARGET")
}

echo "== Tier1 Act 1 bugfix — fixed state + bazel test =="
"$ROOT/scripts/tier1-bugfix-setup.sh" --state fixed
BUGFIX_OK=false
if run_bazel; then
  BUGFIX_OK=true
fi
"$ROOT/scripts/tier1-bugfix-setup.sh" --restore

echo "== Tier1 Act 2 feature — policy retune + bazel test =="
"$ROOT/scripts/tier1-feature-setup.sh" --state feature
FEATURE_OK=false
if run_bazel; then
  FEATURE_OK=true
fi
"$ROOT/scripts/tier1-feature-setup.sh" --restore

if [[ "$BUGFIX_OK" != true || "$FEATURE_OK" != true ]]; then
  write_blocker "bazel test failed for bugfix and/or feature tier1 setup states"
fi

OUT="$OUT" NLFR_TIER1_BAZEL_TARGET="$TARGET" python3 - <<'PY'
import json
import os
from datetime import datetime, timezone
from pathlib import Path

out = Path(os.environ["OUT"])
summary = {
    "status": "completed",
    "source_kind": "collectable_v1",
    "confidence": "high",
    "redaction_state": "safe",
    "evidence_refs": [
        "script:tier1-bazel-ci-proof.sh",
        "scenario:agent-bugfix-1",
        "scenario:agent-feature-compare",
        f"bazel-target:{os.environ.get('NLFR_TIER1_BAZEL_TARGET', '//tasks:priority_test')}",
    ],
    "acts": {
        "agent-bugfix-1": {"bazel_test": "passed", "validation": "bazel"},
        "agent-feature-compare": {"bazel_test": "passed", "validation": "bazel"},
    },
    "recorded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
}
(out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
print(json.dumps(summary, indent=2))
PY

echo "tier1-bazel-ci-proof complete: $OUT/summary.json"
