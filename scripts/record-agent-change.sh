#!/usr/bin/env bash
set -euo pipefail

# M8 real agent adapter — record a bounded agent change with hashed prompt provenance.
# Never stores or exports the raw prompt; only prompt_sha256 is written to NLFR artifacts.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${NLFR_AGENT_CHANGE_OUTPUT:-"$ROOT/data/agent-change-proof"}"
WORKSPACE="${NLFR_AGENT_CHANGE_WORKSPACE:-"$ROOT"}"
SCENARIO="${NLFR_AGENT_CHANGE_SCENARIO:-agent-change}"
RUN_GROUP="${NLFR_AGENT_CHANGE_RUN_GROUP:-agent-change}"
CHANGE_PATH=""
MODEL=""
PROMPT_FILE=""
COMMAND="true"
DRY_RUN=false

usage() {
  cat <<'EOF'
Usage: record-agent-change.sh --change-path FILE --model LABEL --prompt-file FILE [options]

Record a bounded agent edit through nlfr run --mode generic with a provenance
sidecar that carries model + prompt_sha256 only (never the raw prompt).

Options:
  --change-path FILE   Workspace-relative path the agent edited (required)
  --model LABEL        Model label for provenance (required)
  --prompt-file FILE   Prompt text file; hashed locally, never exported (required)
  --command CMD        Validation command for generic run (default: true)
  --output-dir DIR     NLFR output directory (default: data/agent-change-proof)
  --workspace DIR      Workspace root (default: repo root)
  --scenario ID        Scenario label (default: agent-change)
  --run-group GROUP    Run group for projections (default: agent-change)
  --dry-run            Print sidecar + nlfr command without mutating files
  -h, --help           Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --change-path)
      CHANGE_PATH="$2"
      shift 2
      ;;
    --model)
      MODEL="$2"
      shift 2
      ;;
    --prompt-file)
      PROMPT_FILE="$2"
      shift 2
      ;;
    --command)
      COMMAND="$2"
      shift 2
      ;;
    --output-dir)
      OUT="$2"
      shift 2
      ;;
    --workspace)
      WORKSPACE="$2"
      shift 2
      ;;
    --scenario)
      SCENARIO="$2"
      shift 2
      ;;
    --run-group)
      RUN_GROUP="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
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

if [[ -z "$CHANGE_PATH" || -z "$MODEL" || -z "$PROMPT_FILE" ]]; then
  echo "error: --change-path, --model, and --prompt-file are required" >&2
  usage >&2
  exit 2
fi

if [[ ! -f "$PROMPT_FILE" ]]; then
  echo "error: prompt file not found: $PROMPT_FILE" >&2
  exit 2
fi

PROMPT_SHA256="$(
  python3 - <<'PY' "$PROMPT_FILE"
import hashlib
import sys
from pathlib import Path

path = Path(sys.argv[1])
print(hashlib.sha256(path.read_bytes()).hexdigest())
PY
)"

SIDECAR="$(mktemp "${TMPDIR:-/tmp}/nlfr-agent-provenance.XXXXXX").json"
cleanup() {
  rm -f "$SIDECAR"
}
trap cleanup EXIT

python3 - <<'PY' "$SIDECAR" "$MODEL" "$PROMPT_SHA256"
import json
import sys
from pathlib import Path

sidecar_path, model, prompt_sha256 = sys.argv[1:4]
payload = {
    "schema_version": "nlfr.agent_provenance.sidecar.v1",
    "adapter": "record-agent-change.sh",
    "change_class": "bounded_agent_v1",
    "agent": {
        "kind": "cursor_adapter_v1",
        "name": "cursor-agent-change",
        "model": model,
        "prompt_sha256": prompt_sha256,
        "input_signal": "redacted: prompt withheld, hash retained",
    },
}
Path(sidecar_path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
PY

NLFR_CMD=(
  uv run python -m nlfr run
  --mode generic
  --scenario "$SCENARIO"
  --run-group "$RUN_GROUP"
  --workspace "$WORKSPACE"
  --output-dir "$OUT"
  --change-path "$CHANGE_PATH"
  --provenance-sidecar "$SIDECAR"
  --command "$COMMAND"
  --json
)

if [[ "$DRY_RUN" == true ]]; then
  python3 - <<'PY' "$SIDECAR" "$CHANGE_PATH" "$MODEL" "$PROMPT_SHA256" "${NLFR_CMD[*]}"
import json
import sys
from pathlib import Path

sidecar = json.loads(Path(sys.argv[1]).read_text())
print(
    json.dumps(
        {
            "status": "dry_run",
            "change_path": sys.argv[2],
            "model": sys.argv[3],
            "prompt_sha256": sys.argv[4],
            "sidecar": sidecar,
            "nlfr_command": sys.argv[5],
            "source_kind": "collectable_v1",
            "confidence": "high",
            "redaction_state": "safe",
        },
        indent=2,
        sort_keys=True,
    )
)
PY
  exit 0
fi

cd "$ROOT"
mkdir -p "$OUT"
export PYTHONPATH="$ROOT/src"
"${NLFR_CMD[@]}" >"$OUT/run.json"

PROJECTIONS="$OUT/projections"
DB="$OUT/nlfr.sqlite"
mkdir -p "$PROJECTIONS"

PYTHONPATH=src uv run python -m nlfr graph export \
  --db "$DB" \
  --run-group "$RUN_GROUP" \
  --output "$PROJECTIONS/action-graph.json"
PYTHONPATH=src uv run python -m nlfr proof export \
  --db "$DB" \
  --run-group "$RUN_GROUP" \
  --output "$PROJECTIONS/proof.json"

SUMMARY_ROOT="$OUT" python3 - <<'PY'
import json
import os
from pathlib import Path

root = Path(os.environ["SUMMARY_ROOT"])
run_payload = json.loads((root / "run.json").read_text())
proof = json.loads((root / "projections" / "proof.json").read_text())
provenance = json.loads(
    (Path(run_payload["artifact_root"]) / "agent-provenance.json").read_text()
)

summary = {
    "status": run_payload["status"],
    "run_id": run_payload["run_id"],
    "run_group": run_payload["run_group"],
    "mode": run_payload["mode"],
    "change_path": provenance["change"]["affected_paths"],
    "agent": {
        "model": provenance["agent"]["model"],
        "prompt_sha256": provenance["agent"]["prompt_sha256"],
    },
    "agent_source_kind": provenance["source_kind"],
    "validation_source_kind": run_payload["source_kind"],
    "projection_summary": proof.get("summary", {}),
    "source_kind": "collectable_v1",
    "confidence": "high",
    "redaction_state": "safe",
    "evidence_refs": [
        "run.json",
        "agent-provenance.json",
        "projections/action-graph.json",
        "projections/proof.json",
    ],
}
(root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
print(json.dumps(summary, indent=2, sort_keys=True))
PY

echo "agent-change record complete: $OUT/summary.json"
