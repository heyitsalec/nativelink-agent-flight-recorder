#!/usr/bin/env bash
set -euo pipefail

# M4 agent-loop closure proof.
# Applies a bounded agent patch to a copied workspace, runs Bazel through the
# NativeLink cache, ingests validation/cache evidence, and exports projections
# so the Action Graph shows: agent -> change -> run -> validation -> cache.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${NLFR_AGENT_LOOP_OUTPUT:-"$ROOT/data/agent-loop-proof"}"
DB="$OUT/nlfr.sqlite"
PROJECTIONS="$OUT/projections"
CONFIG="${NLFR_NATIVELINK_CONFIG:-"$ROOT/demo/nativelink/cache-only.json"}"
SCENARIO="${NLFR_AGENT_LOOP_SCENARIO:-llm-bounded-patch}"
RUN_GROUP="${NLFR_AGENT_LOOP_RUN_GROUP:-agent-loop}"
REMOTE_CACHE="${NLFR_REMOTE_CACHE:-"grpc://127.0.0.1:50051"}"
NATIVELINK_BIN="${NLFR_NATIVELINK_BIN:-$(command -v nativelink || command -v native-link || true)}"
BAZEL_BIN="${NLFR_BAZEL_BIN:-$(command -v bazel || command -v bazelisk || true)}"
CACHE_ROOT="${NLFR_AGENT_LOOP_CACHE_ROOT:-/tmp/nlfr-nativelink/agent-loop}"

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
    "evidence_refs": ["script:agent-loop-proof.sh"],
}
path = Path(os.environ["OUT_PATH"])
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
print(f"environment blocker recorded: {path}")
PY
}

if [[ -z "$NATIVELINK_BIN" ]]; then
  write_blocker "missing nativelink or native-link on PATH; run this inside nix develop or the devcontainer"
  exit 2
fi

if [[ -z "$BAZEL_BIN" ]]; then
  write_blocker "missing bazel or bazelisk on PATH; run this inside nix develop or the devcontainer"
  exit 2
fi

rm -rf "$CACHE_ROOT" "$OUT/nlfr.sqlite" "$OUT/workspaces" "$OUT/bazel-output-agent-loop"
mkdir -p "$CACHE_ROOT"

echo "== Start NativeLink cache-only server =="
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

deadline = time.time() + 15
while time.time() < deadline:
    sock = socket.socket()
    sock.settimeout(0.4)
    try:
        sock.connect(("127.0.0.1", 50051))
        raise SystemExit(0)
    except OSError:
        time.sleep(0.25)
    finally:
        sock.close()
raise SystemExit(1)
PY
then
  echo "NativeLink did not open 127.0.0.1:50051; stderr follows" >&2
  sed -n '1,120p' "$OUT/nativelink.stderr.txt" >&2 || true
  exit 1
fi

echo "== Simulate bounded agent patch and real run =="
PYTHONPATH=src uv run python -m nlfr simulate \
  --scenario "$SCENARIO" \
  --output-dir "$OUT" \
  --run-group "$RUN_GROUP" \
  --skip-nativelink \
  --bazel-executable "$BAZEL_BIN" \
  --remote-cache "$REMOTE_CACHE" \
  --bazel-startup-arg=--output_base="$OUT/bazel-output-agent-loop" \
  --json >"$OUT/simulate.json"

ARTIFACT_ROOT="$(
  ROOT_PATH="$OUT/simulate.json" python3 - <<'PY'
import json
import os
from pathlib import Path

payload = json.loads(Path(os.environ["ROOT_PATH"]).read_text())
build = payload["scenarios"][0]["build"]
artifact_root = build.get("artifact_root")
if not artifact_root:
    raise SystemExit("missing artifact_root in simulate.json")
print(artifact_root)
PY
)"

RUN_KEY="$(
  ROOT_PATH="$OUT/simulate.json" python3 - <<'PY'
import json
import os
from pathlib import Path

payload = json.loads(Path(os.environ["ROOT_PATH"]).read_text())
build = payload["scenarios"][0]["build"]
run_key = build.get("run_key")
if not run_key:
    raise SystemExit("missing run_key in simulate.json")
print(run_key)
PY
)"

echo "== Attach agent-loop evidence =="
OUT_ROOT="$OUT" ARTIFACT_ROOT="$ARTIFACT_ROOT" PYTHONPATH=src \
  uv run python - <<'PY'
import os
from pathlib import Path

from nlfr.artifacts import write_artifact

out_root = Path(os.environ["OUT_ROOT"])
artifact_root = Path(os.environ["ARTIFACT_ROOT"])
script_ref = "script:agent-loop-proof.sh"
attachments = (
    ("nativelink.stdout.txt", out_root / "nativelink.stdout.txt"),
    ("nativelink.stderr.txt", out_root / "nativelink.stderr.txt"),
)
for artifact_key, source_path in attachments:
    if not source_path.exists():
        continue
    write_artifact(
        artifact_root,
        artifact_key=artifact_key,
        data=source_path.read_bytes(),
        producer_command=["scripts/agent-loop-proof.sh"],
        config_hash=None,
        redaction_state="safe",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=[script_ref, artifact_key],
    )
PY

echo "== Ingest agent-loop validation evidence =="
PYTHONPATH=src uv run python -m nlfr ingest "$ARTIFACT_ROOT" \
  --database "$DB" \
  --run-key "$RUN_KEY" \
  --run-group "$RUN_GROUP" \
  --source-kind collectable_v1 \
  --json >"$OUT/ingest.json"

echo "== Export agent-loop projections =="
PYTHONPATH=src uv run python -m nlfr graph export \
  --db "$DB" \
  --run-group "$RUN_GROUP" \
  --output "$PROJECTIONS/action-graph.json"
PYTHONPATH=src uv run python -m nlfr runway export \
  --db "$DB" \
  --run-group "$RUN_GROUP" \
  --output "$PROJECTIONS/runway.json"
PYTHONPATH=src uv run python -m nlfr proof export \
  --db "$DB" \
  --run-group "$RUN_GROUP" \
  --output "$PROJECTIONS/proof.json"

SUMMARY_ROOT="$OUT" python3 - <<'PY'
import json
import os
from pathlib import Path

root = Path(os.environ["SUMMARY_ROOT"])
simulate = json.loads((root / "simulate.json").read_text())
graph = json.loads((root / "projections" / "action-graph.json").read_text())
ingest_path = root / "ingest.json"
ingest = json.loads(ingest_path.read_text()) if ingest_path.exists() else {}

scenario = simulate["scenarios"][0]
build = scenario["build"]

kinds = {}
for node in graph["nodes"]:
    kinds[node["kind"]] = kinds.get(node["kind"], 0) + 1
edge_kinds = {}
for edge in graph["edges"]:
    edge_kinds[edge["kind"]] = edge_kinds.get(edge["kind"], 0) + 1

chain_ok = (
    kinds.get("agent", 0) >= 1
    and kinds.get("change", 0) >= 1
    and "authored_change" in edge_kinds
    and "validated_by" in edge_kinds
)

summary = {
    "scenario_id": scenario["scenario_id"],
    "agent": scenario["agent"],
    "build_status": build["status"],
    "ingest": ingest,
    "graph_node_kinds": kinds,
    "graph_edge_kinds": edge_kinds,
    "chain_complete": chain_ok,
    "validation_tail": {
        "targets": kinds.get("target", 0),
        "actions": kinds.get("action", 0),
        "cache_events": kinds.get("cache_event", 0),
    },
    "source_kind": "collectable_v1",
    "confidence": "high",
    "redaction_state": "safe",
    "evidence_refs": [
        "simulate.json",
        "ingest.json",
        "projections/action-graph.json",
        "projections/proof.json",
        "nativelink.stdout.txt",
        "nativelink.stderr.txt",
    ],
}
(root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
print(json.dumps(summary, indent=2, sort_keys=True))
if not chain_ok:
    raise SystemExit("agent -> change -> validation chain incomplete in action graph")
PY
