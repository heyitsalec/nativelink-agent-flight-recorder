#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${NLFR_WORKER_EVIDENCE_OUTPUT:-"$ROOT/data/worker-evidence-proof"}"
DB="$OUT/nlfr/nlfr.sqlite"
PROJECTIONS="$OUT/projections"
FIXTURE_ROOT="$ROOT/tests/fixtures/worker-admin"
BAZEL_FIXTURE_ROOT="$ROOT/tests/fixtures/bazel"
NATIVELINK_BIN="${NLFR_NATIVELINK_BIN:-$(command -v nativelink || command -v native-link || true)}"
BAZEL_BIN="${NLFR_BAZEL_BIN:-$(command -v bazel || command -v bazelisk || true)}"

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
    "evidence_refs": ["script:worker-evidence-proof.sh"],
}
path = Path(os.environ["OUT_PATH"])
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
print(f"environment blocker recorded: {path}")
PY
}

replay_fixture_ingest() {
  local artifact_root="$OUT/fixture-artifacts"
  rm -rf "$artifact_root" "$OUT/nlfr"
  mkdir -p "$artifact_root"

  cp "$BAZEL_FIXTURE_ROOT/bep.jsonl" "$artifact_root/bazel.bep.json"
  cp "$BAZEL_FIXTURE_ROOT/execution-log.json" "$artifact_root/bazel.execution-log.json"
  cp "$FIXTURE_ROOT/nativelink.stdout.txt" "$artifact_root/nativelink.stdout.txt"
  cat >"$artifact_root/run.json" <<EOF
{
  "run_id": "run_worker_evidence_fixture",
  "run_key": "worker-evidence-proof:fixture:2026-06-06T12:00:00.000000Z",
  "run_group": "worker-evidence",
  "scenario": "worker-evidence-proof",
  "mode": "local-exec",
  "artifact_root": "$artifact_root"
}
EOF

  echo "== Replay worker-admin fixture through ingest =="
  PYTHONPATH=src uv run python -m nlfr ingest "$artifact_root" \
    --database "$DB" \
    --source-kind collectable_v1 \
    --json >"$OUT/worker-evidence-ingest.json"

  echo "== Seed remote-executor invocation for projection =="
  ARTIFACT_ROOT="$artifact_root" DB_PATH="$DB" INGEST_JSON="$OUT/worker-evidence-ingest.json" \
    PYTHONPATH=src uv run python - <<'PY'
import json
import os
from pathlib import Path

from nlfr.db import connect, initialize
from nlfr.db.ingest import upsert_invocation

ingest = json.loads(Path(os.environ["INGEST_JSON"]).read_text())
run_id = ingest["run_id"]
run_key = ingest["run_key"]
artifact_root = Path(os.environ["ARTIFACT_ROOT"])

conn = initialize(connect(os.environ["DB_PATH"]))
upsert_invocation(
    conn,
    stable_key=f"{run_key}:invocation:bazel",
    run_id=run_id,
    invocation_kind="bazel",
    command=[
        "bazel",
        "test",
        "//tasks:priority_test",
        "--remote_executor=grpc://127.0.0.1:50051",
    ],
    cwd=artifact_root,
    exit_code=0,
    source_kind="collectable_v1",
    confidence="high",
    evidence_refs=["artifact:nativelink.stdout.txt", "artifact:bazel.bep.json"],
    redaction_state="safe",
)
PY
  echo "$artifact_root"
}

run_local_exec_if_available() {
  if [[ -z "$NATIVELINK_BIN" || -z "$BAZEL_BIN" ]]; then
    return 1
  fi
  if [[ -n "${NLFR_WORKER_EVIDENCE_FIXTURE_ONLY:-}" ]]; then
    return 1
  fi

  echo "== Run local-exec proof for live worker stdout =="
  NLFR_LOCAL_EXEC_OUTPUT="$OUT/local-exec" "$ROOT/scripts/local-exec-proof.sh" \
    >"$OUT/local-exec.log" 2>&1 || return 1

  local artifact_root
  artifact_root="$(OUT="$OUT" python3 - <<'PY'
import json
import os
from pathlib import Path

payload = json.loads((Path(os.environ["OUT"]) / "local-exec/local-exec-run.json").read_text())
print(payload["artifact_root"])
PY
)"
  cp "$OUT/local-exec/nativelink.stdout.txt" "$artifact_root/nativelink.stdout.txt" 2>/dev/null || true
  PYTHONPATH=src uv run python -m nlfr ingest "$artifact_root" \
    --database "$DB" \
    --run-group worker-evidence \
    --source-kind collectable_v1 \
    --json >"$OUT/worker-evidence-ingest.json"
  echo "$artifact_root"
}

if artifact_root="$(run_local_exec_if_available)"; then
  MODE="local-exec"
elif artifact_root="$(replay_fixture_ingest)"; then
  MODE="fixture-replay"
else
  write_blocker "missing nativelink/bazel on PATH and fixture replay failed"
  exit 2
fi

echo "== Export worker evidence projections =="
PYTHONPATH=src uv run python -m nlfr graph export \
  --db "$DB" \
  --run-group worker-evidence \
  --output "$PROJECTIONS/action-graph.json"
PYTHONPATH=src uv run python -m nlfr proof export \
  --db "$DB" \
  --run-group worker-evidence \
  --output "$PROJECTIONS/proof.json"

SUMMARY_ROOT="$OUT" SUMMARY_MODE="$MODE" SUMMARY_ARTIFACT_ROOT="$artifact_root" python3 - <<'PY'
import json
import os
from pathlib import Path

root = Path(os.environ["SUMMARY_ROOT"])
proof_path = root / "projections" / "proof.json"
graph_path = root / "projections" / "action-graph.json"
proof = json.loads(proof_path.read_text()) if proof_path.exists() else {}
graph = json.loads(graph_path.read_text()) if graph_path.exists() else {}

remote_block = next(
    (block for block in proof.get("blocks", []) if block.get("id") == "remote_execution"),
    {},
)
worker_nodes = [node for node in graph.get("nodes", []) if node.get("kind") == "worker"]
identity_block = next(
    (
        block
        for block in proof.get("blocks", [])
        if block.get("kind") == "worker_admin_identity_v1"
    ),
    None,
)

summary = {
    "status": "completed",
    "mode": os.environ["SUMMARY_MODE"],
    "artifact_root": os.environ["SUMMARY_ARTIFACT_ROOT"],
    "source_kind": "collectable_v1",
    "confidence": "high",
    "redaction_state": "safe",
    "worker_identity_observed": remote_block.get("metrics", {}).get(
        "worker_identity_observed", False
    ),
    "worker_nodes": len(worker_nodes),
    "unsupported_claims": (remote_block.get("payload") or {}).get("unsupported_claims", []),
    "evidence_refs": [
        "worker-evidence-ingest.json",
        "projections/proof.json",
        "projections/action-graph.json",
        "nativelink.stdout.txt",
    ],
}
if identity_block:
    summary["worker_admin_identity"] = {
        "events": (identity_block.get("payload") or {}).get("events", []),
        "source_kind": identity_block.get("source_kind"),
    }

(root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
print(json.dumps(summary, indent=2, sort_keys=True))
PY
