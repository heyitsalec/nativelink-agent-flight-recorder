#!/usr/bin/env bash
set -euo pipefail

# Two-act live spark — the recorder catches a real agent being wrong.
#
# Act 1: a headless Claude Code agent authors a module from an UNDERSPECIFIED
#   task spec (demo/scenarios/two-act-underspec.json). A hidden Bazel test in a
#   TEMP COPY of the demo workspace encodes the full requirement the agent
#   cannot see. Real `bazel test` through the NativeLink cache catches the gap:
#   red validation leg, recorded with a verifiable CLI receipt.
# Act 2: the agent receives the RECORDED failure evidence (excerpt of Act 1's
#   flight-recorder artifacts) and produces the fix: green leg with warm
#   NativeLink cache hits on unchanged targets.
#
# Honesty rules enforced here:
# - the demo workspace is never mutated; all edits land in a mktemp copy
# - the agent CLI runs in an empty scratch cwd; it can never read the hidden test
# - a failed/unauthenticated CLI records a truth-labeled environment blocker;
#   nothing is faked
# - raw prompts exist only in mktemp space and are deleted; receipts carry
#   prompt SHA-256 only; an in-script scan gate fails the run if prompt text
#   leaks into any output artifact
#
# Stub mode (mechanics proof without a live LLM):
#   NLFR_SPARK_CLAUDE_BIN=scripts/spark-stub-claude.sh \
#   NLFR_TWO_ACT_OUTPUT=$PWD/data/two-act-spark-stub ./scripts/two-act-spark-proof.sh
# Stub receipts are labeled simulated_v1 and the agent leg is downgraded to
# stub_receipt_v1; validation/cache legs remain collectable_v1.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${NLFR_TWO_ACT_OUTPUT:-"$ROOT/data/two-act-spark"}"
DB="$OUT/nlfr.sqlite"
PROJECTIONS="$OUT/projections"
RECEIPTS="$OUT/receipts"
RESPONSES="$OUT/responses"
SCENARIO_FILE="${NLFR_SPARK_SCENARIO:-"$ROOT/demo/scenarios/two-act-underspec.json"}"
CLAUDE_BIN="${NLFR_SPARK_CLAUDE_BIN:-claude}"
SPARK_MODEL="${NLFR_SPARK_MODEL:-}"
RUN_GROUP_PREFIX="${NLFR_SPARK_RUN_GROUP_PREFIX:-two-act-spark}"
ACT1_GROUP="$RUN_GROUP_PREFIX-act1"
ACT2_GROUP="$RUN_GROUP_PREFIX-act2"
CONFIG="${NLFR_NATIVELINK_CONFIG:-"$ROOT/demo/nativelink/cache-only.json"}"
REMOTE_CACHE="${NLFR_REMOTE_CACHE:-"grpc://127.0.0.1:50051"}"
NATIVELINK_BIN="${NLFR_NATIVELINK_BIN:-$(command -v nativelink || command -v native-link || true)}"
BAZEL_BIN="${NLFR_BAZEL_BIN:-$(command -v bazel || command -v bazelisk || true)}"
CACHE_ROOT="${NLFR_SPARK_CACHE_ROOT:-/tmp/nlfr-nativelink/cache-only}"
AGENT_TIMEOUT="${NLFR_SPARK_AGENT_TIMEOUT:-900}"

cd "$ROOT"
rm -rf "$OUT"
mkdir -p "$OUT" "$PROJECTIONS" "$RECEIPTS" "$RESPONSES"
export PYTHONPATH="$ROOT/src"

write_blocker() {
  local reason="$1"
  local receipt_ref="${2:-}"
  REASON="$reason" RECEIPT_REF="$receipt_ref" OUT_PATH="$OUT/environment-blocker.json" python3 - <<'PY'
import json
import os
from pathlib import Path

evidence = ["script:two-act-spark-proof.sh"]
receipt_ref = os.environ.get("RECEIPT_REF")
if receipt_ref:
    evidence.append(receipt_ref)
payload = {
    "status": "environment_blocker",
    "reason": os.environ["REASON"],
    "source_kind": "collectable_v1",
    "confidence": "high",
    "redaction_state": "safe",
    "evidence_refs": evidence,
}
path = Path(os.environ["OUT_PATH"])
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
print(f"environment blocker recorded: {path}")
PY
}

if [[ -z "$NATIVELINK_BIN" ]]; then
  write_blocker "missing nativelink or native-link on PATH; run this inside nix develop"
  exit 2
fi
if [[ -z "$BAZEL_BIN" ]]; then
  write_blocker "missing bazel or bazelisk on PATH; run this inside nix develop"
  exit 2
fi

TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/nlfr-two-act.XXXXXX")"
WS="$TMP_ROOT/workspace"
NL_PID=""
cleanup() {
  if [[ -n "$NL_PID" ]] && kill -0 "$NL_PID" >/dev/null 2>&1; then
    kill "$NL_PID" >/dev/null 2>&1 || true
    wait "$NL_PID" >/dev/null 2>&1 || true
  fi
  rm -rf "$TMP_ROOT"
}
trap cleanup EXIT

echo "== Prepare temp workspace copy (demo workspace is never mutated) =="
WS="$WS" SCENARIO_FILE="$SCENARIO_FILE" ROOT="$ROOT" uv run python - <<'PY'
import os
import shutil
from pathlib import Path

from nlfr.spark import apply_workspace_setup, load_spark_scenario

root = Path(os.environ["ROOT"])
ws = Path(os.environ["WS"])
scenario = load_spark_scenario(os.environ["SCENARIO_FILE"])
template = root / scenario["workload"]["repo_root"]
shutil.copytree(
    template,
    ws,
    ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "bazel-*"),
)
written = apply_workspace_setup(scenario, ws)
for rel, digest in sorted(written.items()):
    print(f"workspace setup wrote {rel} sha256:{digest[:12]}")
PY

invoke_agent() {
  # invoke_agent ACT PROMPT_PATH -> writes receipts/responses, act invoke JSON
  local act="$1"
  local prompt_path="$2"
  local scratch="$TMP_ROOT/scratch-$act"
  mkdir -p "$scratch"
  local invoke_rc=0
  local model_args=()
  if [[ -n "$SPARK_MODEL" ]]; then
    model_args=(--model "$SPARK_MODEL")
  fi
  uv run python -m nlfr agent-invoke \
    --prompt-file "$prompt_path" \
    --receipt-output "$RECEIPTS/$act-receipt.json" \
    --response-output "$RESPONSES/$act-response.md" \
    --claude-bin "$CLAUDE_BIN" \
    --cwd "$scratch" \
    --timeout "$AGENT_TIMEOUT" \
    "${model_args[@]}" \
    --json </dev/null >"$OUT/$act-invoke.json" || invoke_rc=$?
  if [[ "$invoke_rc" -ne 0 ]]; then
    local detail
    detail="$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get('detail') or d.get('status'))" "$OUT/$act-invoke.json" 2>/dev/null || echo "agent-invoke failed")"
    write_blocker "headless agent CLI invocation failed in $act: $detail (receipt kept as evidence)" "receipt:$RECEIPTS/$act-receipt.json"
    exit 2
  fi
}

echo "== Act 1: build deterministic underspecified prompt (temp only, hash recorded) =="
WS="$WS" SCENARIO_FILE="$SCENARIO_FILE" PROMPT_PATH="$TMP_ROOT/act1-prompt.txt" uv run python - <<'PY'
import os
from pathlib import Path

from nlfr.spark import build_act1_prompt, load_spark_scenario

scenario = load_spark_scenario(os.environ["SCENARIO_FILE"])
prompt = build_act1_prompt(scenario, os.environ["WS"])
Path(os.environ["PROMPT_PATH"]).write_text(prompt, encoding="utf-8")
PY

echo "== Act 1: headless agent invocation (receipt captured) =="
invoke_agent act1 "$TMP_ROOT/act1-prompt.txt"

echo "== Act 1: apply agent-authored module to temp workspace =="
WS="$WS" SCENARIO_FILE="$SCENARIO_FILE" RESPONSE_PATH="$RESPONSES/act1-response.md" \
  HASHES_PATH="$TMP_ROOT/act1-hashes.json" uv run python - <<'PY'
import hashlib
import json
import os
from pathlib import Path

from nlfr.spark import extract_python_file, load_spark_scenario

scenario = load_spark_scenario(os.environ["SCENARIO_FILE"])
target_rel = scenario["workload"]["target_file"]
target = Path(os.environ["WS"]) / target_rel
content = extract_python_file(Path(os.environ["RESPONSE_PATH"]).read_text(encoding="utf-8"))
before = (
    hashlib.sha256(target.read_bytes()).hexdigest() if target.exists() else None
)
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(content, encoding="utf-8")
after = hashlib.sha256(target.read_bytes()).hexdigest()
Path(os.environ["HASHES_PATH"]).write_text(
    json.dumps({"path": target_rel, "before": before, "after": after}) + "\n"
)
print(f"act1 wrote {target_rel} sha256:{after[:12]}")
PY

echo "== Start NativeLink cache-only server (fresh cache root) =="
rm -rf "$CACHE_ROOT"
mkdir -p "$CACHE_ROOT"
"$NATIVELINK_BIN" "$CONFIG" >"$OUT/nativelink.stdout.txt" 2>"$OUT/nativelink.stderr.txt" &
NL_PID=$!

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

write_sidecar() {
  # write_sidecar ACT SIDECAR_PATH HASHES_PATH
  local act="$1"
  local sidecar_path="$2"
  local hashes_path="$3"
  ACT="$act" SIDECAR_PATH="$sidecar_path" HASHES_PATH="$hashes_path" \
    RECEIPT_PATH="$RECEIPTS/$act-receipt.json" python3 - <<'PY'
import json
import os
from pathlib import Path

receipt = json.loads(Path(os.environ["RECEIPT_PATH"]).read_text())
hashes = json.loads(Path(os.environ["HASHES_PATH"]).read_text())
model = receipt.get("model", {}).get("resolved") or receipt.get("model", {}).get("requested") or "unresolved"
payload = {
    "schema_version": "nlfr.agent_provenance.sidecar.v1",
    "adapter": "two-act-spark-proof.sh",
    "change_class": "bounded_agent_v1",
    "agent": {
        "kind": "claude_code_adapter_v1",
        "name": f"two-act-spark-{os.environ['ACT']}",
        "model": model,
        "prompt_sha256": receipt["prompt_sha256"],
        "input_signal": "redacted: prompt withheld, hash retained",
    },
    "change_before_hashes": {hashes["path"]: hashes["before"]},
}
Path(os.environ["SIDECAR_PATH"]).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
PY
}

run_act() {
  # run_act ACT RUN_GROUP -> $OUT/$ACT-run.json; returns nlfr run exit code
  local act="$1"
  local run_group="$2"
  local hashes_path="$TMP_ROOT/$act-hashes.json"
  local sidecar_path="$TMP_ROOT/$act-sidecar.json"
  write_sidecar "$act" "$sidecar_path" "$hashes_path"
  local change_path
  change_path="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['path'])" "$hashes_path")"
  local rc=0
  uv run python -m nlfr run \
    --mode cache-only \
    --skip-nativelink \
    --scenario "two-act-underspec-$act" \
    --run-group "$run_group" \
    --workspace "$WS" \
    --output-dir "$OUT" \
    --bazel-executable "$BAZEL_BIN" \
    --remote-cache "$REMOTE_CACHE" \
    --bazel-startup-arg=--output_base="$OUT/bazel-output-$act" \
    --bazel-arg=--test_output=errors \
    --change-path "$change_path" \
    --provenance-sidecar "$sidecar_path" \
    --agent-receipt "$RECEIPTS/$act-receipt.json" \
    --json \
    //... </dev/null >"$OUT/$act-run.json" || rc=$?
  return "$rc"
}

attach_and_ingest() {
  # attach_and_ingest ACT RUN_GROUP — attach response + nativelink logs, ingest bazel evidence
  local act="$1"
  local run_group="$2"
  local artifact_root run_key
  artifact_root="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['artifact_root'])" "$OUT/$act-run.json")"
  run_key="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['run_key'])" "$OUT/$act-run.json")"
  ACT="$act" ARTIFACT_ROOT="$artifact_root" OUT_ROOT="$OUT" uv run python - <<'PY'
import os
from pathlib import Path

from nlfr.artifacts import write_artifact

act = os.environ["ACT"]
artifact_root = Path(os.environ["ARTIFACT_ROOT"])
out_root = Path(os.environ["OUT_ROOT"])
attachments = (
    ("agent-response.md", out_root / "responses" / f"{act}-response.md", "collectable_v1"),
    ("nativelink.stdout.txt", out_root / "nativelink.stdout.txt", "collectable_v1"),
    ("nativelink.stderr.txt", out_root / "nativelink.stderr.txt", "collectable_v1"),
)
for artifact_key, source, source_kind in attachments:
    if not source.exists():
        continue
    write_artifact(
        artifact_root,
        artifact_key=artifact_key,
        data=source.read_bytes(),
        producer_command=["scripts/two-act-spark-proof.sh"],
        config_hash=None,
        redaction_state="safe",
        source_kind=source_kind,
        confidence="high",
        evidence_refs=["script:two-act-spark-proof.sh", artifact_key],
    )
PY
  uv run python -m nlfr ingest "$artifact_root" \
    --database "$DB" \
    --run-key "$run_key" \
    --run-group "$run_group" \
    --source-kind collectable_v1 \
    --json >"$OUT/$act-ingest.json"
  uv run python -m nlfr graph export \
    --db "$DB" \
    --run-group "$run_group" \
    --output "$PROJECTIONS/$act-action-graph.json"
  uv run python -m nlfr proof export \
    --db "$DB" \
    --run-group "$run_group" \
    --output "$PROJECTIONS/$act-proof.json"
}

echo "== Act 1: real bazel test through NativeLink (red expected) =="
ACT1_RC=0
run_act act1 "$ACT1_GROUP" || ACT1_RC=$?
ACT1_STATUS="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['status'])" "$OUT/act1-run.json")"
echo "act1 status: $ACT1_STATUS (nlfr run rc=$ACT1_RC)"
attach_and_ingest act1 "$ACT1_GROUP"

SPARK_OUTCOME="two_act_complete"
if [[ "$ACT1_STATUS" == "completed" ]]; then
  # Honest first-pass success: record it, keep everything, no act 2 failure to fix.
  SPARK_OUTCOME="first_pass_success"
  echo "act1 passed on first attempt; recording honestly (retry policy: rerun = new run group)"
elif [[ "$ACT1_STATUS" != "failed" ]]; then
  write_blocker "act1 validation ended in unexpected status: $ACT1_STATUS (expected failed or completed)"
  exit 2
else
  echo "== Act 1 honesty gate: the red must be the hidden requirement failing =="
  # A toolchain/startup failure (wrong bazel version, missing workspace, ...)
  # must never be presented as "the recorder caught the agent being wrong".
  ACT1_ARTIFACT_ROOT="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['artifact_root'])" "$OUT/act1-run.json")"
  CLASSIFY_RC=0
  ARTIFACT_ROOT="$ACT1_ARTIFACT_ROOT" SCENARIO_FILE="$SCENARIO_FILE" \
    CLASSIFY_PATH="$OUT/act1-failure-classification.json" uv run python - <<'PY' || CLASSIFY_RC=$?
import json
import os
from pathlib import Path

from nlfr.spark import classify_validation_failure, load_spark_scenario

scenario = load_spark_scenario(os.environ["SCENARIO_FILE"])
verdict = classify_validation_failure(
    os.environ["ARTIFACT_ROOT"],
    hidden_target=scenario["hidden_validation"]["bazel_target"],
)
Path(os.environ["CLASSIFY_PATH"]).write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n")
print(json.dumps(verdict, indent=2, sort_keys=True))
raise SystemExit(0 if verdict["honest_scenario_failure"] else 1)
PY
  if [[ "$CLASSIFY_RC" -ne 0 ]]; then
    write_blocker "act1 red was not an honest scenario failure (see act1-failure-classification.json); refusing to spin the two-act story on a toolchain error"
    exit 2
  fi
fi

if [[ "$SPARK_OUTCOME" == "two_act_complete" ]]; then
  echo "== Act 2: extract RECORDED failure evidence from Act 1 artifacts =="
  ACT1_ARTIFACT_ROOT="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['artifact_root'])" "$OUT/act1-run.json")"
  ARTIFACT_ROOT="$ACT1_ARTIFACT_ROOT" EXCERPT_PATH="$OUT/act1-failure-excerpt.txt" uv run python - <<'PY'
import os
from pathlib import Path

from nlfr.spark import failure_excerpt

excerpt = failure_excerpt(os.environ["ARTIFACT_ROOT"])
Path(os.environ["EXCERPT_PATH"]).write_text(excerpt, encoding="utf-8")
print(f"failure excerpt: {len(excerpt.splitlines())} lines from recorded artifacts")
PY

  echo "== Act 2: build fix prompt from recorded evidence (temp only, hash recorded) =="
  WS="$WS" SCENARIO_FILE="$SCENARIO_FILE" PROMPT_PATH="$TMP_ROOT/act2-prompt.txt" \
    EXCERPT_PATH="$OUT/act1-failure-excerpt.txt" uv run python - <<'PY'
import os
from pathlib import Path

from nlfr.spark import build_act2_prompt, load_spark_scenario

scenario = load_spark_scenario(os.environ["SCENARIO_FILE"])
target = Path(os.environ["WS"]) / scenario["workload"]["target_file"]
prompt = build_act2_prompt(
    scenario,
    act1_file_content=target.read_text(encoding="utf-8"),
    failure_evidence=Path(os.environ["EXCERPT_PATH"]).read_text(encoding="utf-8"),
)
Path(os.environ["PROMPT_PATH"]).write_text(prompt, encoding="utf-8")
PY

  echo "== Act 2: headless agent invocation (receipt captured) =="
  invoke_agent act2 "$TMP_ROOT/act2-prompt.txt"

  echo "== Act 2: apply agent fix to temp workspace =="
  WS="$WS" SCENARIO_FILE="$SCENARIO_FILE" RESPONSE_PATH="$RESPONSES/act2-response.md" \
    HASHES_PATH="$TMP_ROOT/act2-hashes.json" uv run python - <<'PY'
import hashlib
import json
import os
from pathlib import Path

from nlfr.spark import extract_python_file, load_spark_scenario

scenario = load_spark_scenario(os.environ["SCENARIO_FILE"])
target_rel = scenario["workload"]["target_file"]
target = Path(os.environ["WS"]) / target_rel
content = extract_python_file(Path(os.environ["RESPONSE_PATH"]).read_text(encoding="utf-8"))
before = hashlib.sha256(target.read_bytes()).hexdigest()
target.write_text(content, encoding="utf-8")
after = hashlib.sha256(target.read_bytes()).hexdigest()
Path(os.environ["HASHES_PATH"]).write_text(
    json.dumps({"path": target_rel, "before": before, "after": after}) + "\n"
)
print(f"act2 wrote {target_rel} sha256:{after[:12]}")
PY

  echo "== Act 2: real bazel test through NativeLink (green + warm hits expected) =="
  ACT2_RC=0
  run_act act2 "$ACT2_GROUP" || ACT2_RC=$?
  ACT2_STATUS="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['status'])" "$OUT/act2-run.json")"
  echo "act2 status: $ACT2_STATUS (nlfr run rc=$ACT2_RC)"
  attach_and_ingest act2 "$ACT2_GROUP"

  echo "== Export M9 compare projection (failure vs fix) =="
  uv run python -m nlfr compare export \
    --db "$DB" \
    --left "$ACT1_GROUP" \
    --right "$ACT2_GROUP" \
    --output "$PROJECTIONS/compare-act1-vs-act2.json"
fi

echo "== Prompt redaction scan gate (no prompt text in any output) =="
OUT_DIR="$OUT" SCENARIO_FILE="$SCENARIO_FILE" uv run python - <<'PY'
import json
import os
from pathlib import Path

from nlfr.spark import load_spark_scenario

scenario = load_spark_scenario(os.environ["SCENARIO_FILE"])
needles = [
    # Prompt template scaffolding only ever rendered into prompts:
    "You are a coding agent completing one bounded task in a Bazel Python monorepo.",
    "You are a coding agent fixing your previous change in a Bazel Python monorepo.",
    "OUTPUT CONTRACT:",
    # Full task spec text (prompt body) must never appear in evidence outputs:
    scenario["task_spec"],
]
out = Path(os.environ["OUT_DIR"])
leaks = []
for path in sorted(out.rglob("*")):
    if not path.is_file():
        continue
    if "bazel-output-" in path.as_posix():
        continue  # bazel internal output bases are not recorded evidence
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        continue
    for needle in needles:
        if needle in text:
            leaks.append(f"{path}: {needle[:48]!r}")
print(json.dumps({"scanned_root": str(out), "leaks": leaks}, indent=2))
if leaks:
    raise SystemExit("prompt text leaked into recorded outputs")
print("redaction gate clean: no prompt text in recorded outputs")
PY

echo "== Assemble two-act summary =="
SUMMARY_ROOT="$OUT" ACT1_GROUP="$ACT1_GROUP" ACT2_GROUP="$ACT2_GROUP" \
  SPARK_OUTCOME="$SPARK_OUTCOME" CLAUDE_BIN_NAME="$(basename "$CLAUDE_BIN")" \
  SCENARIO_FILE="$SCENARIO_FILE" uv run python - <<'PY'
import json
import os
from pathlib import Path

root = Path(os.environ["SUMMARY_ROOT"])
outcome = os.environ["SPARK_OUTCOME"]


def load(name):
    path = root / name
    return json.loads(path.read_text()) if path.exists() else None


def receipt_summary(act):
    payload = load(f"receipts/{act}-receipt.json")
    if not payload:
        return None
    return {
        "status": payload.get("status"),
        "cli": payload.get("cli", {}).get("name"),
        "cli_version": payload.get("cli", {}).get("version"),
        "model_resolved": payload.get("model", {}).get("resolved"),
        "session_id": payload.get("session_id"),
        "prompt_sha256": payload.get("prompt_sha256"),
        "response_sha256": payload.get("response_sha256"),
        "usage": payload.get("usage"),
        "num_turns": payload.get("num_turns"),
        "source_kind": payload.get("source_kind"),
        "confidence": payload.get("confidence"),
        "redaction_state": payload.get("redaction_state"),
    }


def cache_metrics(act):
    proof = load(f"projections/{act}-proof.json")
    if not proof:
        return {}
    for block in proof.get("blocks", []):
        if block.get("id") == "cache":
            return block.get("metrics") or {}
    return {}


def agent_node(act):
    graph = load(f"projections/{act}-action-graph.json")
    if not graph:
        return None
    for node in graph.get("nodes", []):
        if node.get("kind") == "agent":
            payload = node.get("payload") or {}
            return {
                "label": node.get("label"),
                "source_kind": node.get("source_kind"),
                "provenance_class": payload.get("provenance_class"),
                "receipt_verified": payload.get("receipt_verified"),
                "model": payload.get("model"),
            }
    return None


act1_run = load("act1-run.json") or {}
act2_run = load("act2-run.json") or {}
act1_status = act1_run.get("status")
act2_status = act2_run.get("status")
act1_cache = cache_metrics("act1")
act2_cache = cache_metrics("act2")
act1_receipt = receipt_summary("act1")
act2_receipt = receipt_summary("act2")
agent_live = bool(act1_receipt and act1_receipt.get("cli") == "claude")

checks = {
    "act1_receipt_present": act1_receipt is not None,
    "act1_agent_node_in_graph": agent_node("act1") is not None,
}
if outcome == "two_act_complete":
    classification = load("act1-failure-classification.json") or {}
    checks.update(
        {
            "act1_validation_red": act1_status == "failed",
            "act1_red_attributed_to_hidden_target": classification.get("honest_scenario_failure") is True,
            "act2_validation_green": act2_status == "completed",
            "act2_receipt_present": act2_receipt is not None,
            "act2_warm_cache_hits": int(act2_cache.get("hits") or 0) > 0,
            "compare_projection_exported": (root / "projections" / "compare-act1-vs-act2.json").exists(),
        }
    )

summary = {
    "scenario_id": "two-act-underspec",
    "scenario_path": os.environ["SCENARIO_FILE"],
    "spark_outcome": outcome,
    "agent_cli": os.environ["CLAUDE_BIN_NAME"],
    "agent_leg_source_kind": (act1_receipt or {}).get("source_kind"),
    "agent_leg_live": agent_live,
    "validation_leg_source_kind": "collectable_v1",
    "act1": {
        "run_group": os.environ["ACT1_GROUP"],
        "status": act1_status,
        "run_id": act1_run.get("run_id"),
        "receipt": act1_receipt,
        "cache_metrics": act1_cache,
        "agent_node": agent_node("act1"),
        "ingest": load("act1-ingest.json"),
    },
    "act2": {
        "run_group": os.environ["ACT2_GROUP"],
        "status": act2_status,
        "run_id": act2_run.get("run_id"),
        "receipt": act2_receipt,
        "cache_metrics": act2_cache,
        "agent_node": agent_node("act2"),
        "ingest": load("act2-ingest.json"),
        "failure_evidence_source": "act1 recorded artifacts (act1-failure-excerpt.txt)",
    },
    "checks": checks,
    "source_kind": "collectable_v1",
    "confidence": "high",
    "redaction_state": "safe",
    "evidence_refs": [
        "act1-run.json",
        "act1-failure-classification.json",
        "act2-run.json",
        "receipts/act1-receipt.json",
        "receipts/act2-receipt.json",
        "act1-failure-excerpt.txt",
        "projections/act1-proof.json",
        "projections/act2-proof.json",
        "projections/compare-act1-vs-act2.json",
        "nativelink.stdout.txt",
        "nativelink.stderr.txt",
    ],
}
(root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
print(json.dumps(summary, indent=2, sort_keys=True))
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit(f"two-act spark checks failed: {failed}")
PY

echo "two-act spark complete: $OUT/summary.json"
