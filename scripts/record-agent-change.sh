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
BASELINE_REF="HEAD"
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
  --baseline-ref REF   Git ref holding the PRE-EDIT state (default: HEAD). Use a
                       pre-edit ref (e.g. HEAD~1 or a commit sha) when the edit
                       was already COMMITTED before recording — otherwise HEAD
                       equals the final state and the change is not attestable.
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
    --baseline-ref)
      BASELINE_REF="$2"
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

python3 - <<'PY' "$SIDECAR" "$MODEL" "$PROMPT_SHA256" "$WORKSPACE" "$CHANGE_PATH" "$BASELINE_REF"
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sidecar_path, model, prompt_sha256, workspace, change_path, baseline_ref = sys.argv[1:7]


def _git(*args, text=False):
    return subprocess.run(
        ["git", "-C", workspace, *args],
        capture_output=True,
        text=text,
        check=False,
    )


def git_baseline():
    """Capture the PRE-EDIT bytes of change_path from the git object store.

    The documented adapter workflow edits the file FIRST, then records — so the
    recorder's own before/after window sees no change (before == after). Git,
    however, still holds the committed pre-edit bytes: `git show <ref>:<path>`.
    That is verifiable EVIDENCE (a skeptic reruns it and matches the hash), not
    an operator assertion.

    ``baseline_ref`` (default HEAD, override via --baseline-ref) names the ref
    that holds the PRE-EDIT state. For the edit-first working-tree flow HEAD is
    correct. But if the edit was already COMMITTED before recording, HEAD now
    equals the final state, so the operator must pass a true pre-edit ref
    (HEAD~1 or a commit sha) — otherwise baseline == after and the change is not
    attestable. The ref is resolved to a concrete commit sha so the recorded
    evidence stays pinned even as branches move.

    Returns a baseline entry or None when git cannot attest (not a repo, the ref
    does not resolve, or an untracked path).
    """

    try:
        probe = _git("rev-parse", "--is-inside-work-tree", text=True)
        if probe.returncode != 0 or probe.stdout.strip() != "true":
            return None
        resolved = _git("rev-parse", "--verify", f"{baseline_ref}^{{commit}}", text=True)
        if resolved.returncode != 0:
            return None  # ref does not resolve (unborn HEAD, bad ref) — no baseline
        commit = resolved.stdout.strip()
        toplevel = _git("rev-parse", "--show-toplevel", text=True)
        if toplevel.returncode != 0:
            return None
        repo_root = Path(toplevel.stdout.strip())
        abs_path = (Path(workspace) / change_path).resolve()
        try:
            repo_rel = abs_path.relative_to(repo_root).as_posix()
        except ValueError:
            return None  # change path escapes the repo tree
        # source.ref carries the symbolic ref the operator named; source.commit is
        # the resolved sha the recorder re-verifies and pins as evidence.
        ref = f"git:{baseline_ref}:{repo_rel}"
        source = {"kind": "git_head", "commit": commit, "ref": ref}
        show = _git("show", f"{commit}:{repo_rel}")  # bytes at the pre-edit ref
        if show.returncode == 0:
            return {
                "baseline_sha256": hashlib.sha256(show.stdout).hexdigest(),
                "source": source,
            }
        # Absent at the ref: attestable only if git tracks it (staged-new). Untracked
        # files get no baseline — git cannot attest their pre-edit state.
        tracked = _git("ls-files", "--error-unmatch", "--", repo_rel)
        if tracked.returncode == 0:
            return {"baseline_sha256": None, "source": source}  # -> appeared
        return None
    except Exception:  # noqa: BLE001 — git absent/unusable is a non-fatal no-baseline
        return None


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
baseline = git_baseline()
if baseline is not None:
    payload["git_baseline"] = {change_path: baseline}
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
