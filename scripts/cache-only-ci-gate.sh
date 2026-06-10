#!/usr/bin/env bash
set -euo pipefail

# PR-safe cache-only gate — nlfr doctor JSON contract + pytest smoke.
# Missing Bazel/NativeLink on PATH is an honest environment blocker, not a gate failure.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${NLFR_CACHE_GATE_OUTPUT:-"$ROOT/data/cache-only-ci-gate"}"

usage() {
  cat <<'EOF'
Usage: cache-only-ci-gate.sh

Runs nlfr doctor --mode cache-only (JSON contract) and a pytest smoke slice.

Environment:
  NLFR_CACHE_GATE_OUTPUT  Output dir (default: data/cache-only-ci-gate)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

mkdir -p "$OUT"
cd "$ROOT"

echo "== NLFR cache-only doctor =="
PYTHONPATH=src uv run python -m nlfr doctor --mode cache-only --json >"$OUT/doctor.json" || true

DOCTOR_PATH="$OUT/doctor.json" python3 - <<'PY'
import json
import os
import sys
from pathlib import Path

path = Path(os.environ["DOCTOR_PATH"])
payload = json.loads(path.read_text(encoding="utf-8"))

if payload.get("mode") != "cache-only":
    raise SystemExit(f"doctor mode must be cache-only, got {payload.get('mode')!r}")
if not isinstance(payload.get("ok"), bool):
    raise SystemExit("doctor payload missing boolean ok")
checks = payload.get("checks")
if not isinstance(checks, list) or not checks:
    raise SystemExit("doctor payload missing checks list")

names: set[str] = set()
for check in checks:
    for key in ("name", "ok", "detail"):
        if key not in check:
            raise SystemExit(f"doctor check missing {key!r}: {check!r}")
    if not isinstance(check["ok"], bool):
        raise SystemExit(f"doctor check ok must be boolean: {check!r}")
    names.add(check["name"])

required = {"python", "bazel", "nativelink"}
missing = sorted(required - names)
if missing:
    raise SystemExit(f"doctor checks missing required names: {', '.join(missing)}")

print(json.dumps({"doctor_ok": payload["ok"], "checks": sorted(names)}, indent=2, sort_keys=True))
PY

echo "== Pytest smoke =="
uv run pytest tests/test_doctor_cache_only_gate.py::test_doctor_cache_only_json_contract -q --tb=no

DOCTOR_PATH="$OUT/doctor.json" SUMMARY_PATH="$OUT/summary.json" python3 - <<'PY'
import json
import os
from pathlib import Path

doctor = json.loads(Path(os.environ["DOCTOR_PATH"]).read_text(encoding="utf-8"))
checks = {check["name"]: check for check in doctor["checks"]}
summary = {
    "status": "passed",
    "proof_script": "cache-only-ci-gate.sh",
    "mode": "cache-only",
    "doctor_ok": doctor["ok"],
    "doctor_checks": {
        name: {"ok": check["ok"], "detail": check["detail"]}
        for name, check in checks.items()
    },
    "source_kind": "collectable_v1",
    "confidence": "high",
    "redaction_state": "safe",
    "evidence_refs": [
        "doctor.json",
        "script:cache-only-ci-gate.sh",
        "tests/test_doctor_cache_only_gate.py",
    ],
    "claim_boundary": (
        "Gate validates doctor JSON contract and pytest smoke only; "
        "doctor_ok=false records an environment blocker, not a failed gate."
    ),
}
Path(os.environ["SUMMARY_PATH"]).write_text(
    json.dumps(summary, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
print(json.dumps(summary, indent=2, sort_keys=True))
PY

echo "cache-only CI gate passed: $OUT/summary.json"
