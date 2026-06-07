#!/usr/bin/env bash
set -euo pipefail

# Audit GitHub Actions workflow YAML and run local CI substitutes while GHA is offline.
# Does NOT claim sustained green — see docs/GHA_RESTORE_RUNBOOK.md.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${NLFR_GHA_READINESS_OUTPUT:-"$ROOT/data/verify-gha-readiness"}"
WORKFLOWS_DIR="$ROOT/.github/workflows"

usage() {
  cat <<'EOF'
Usage: verify-gha-readiness.sh [--audit-only | --substitutes-only]

Audits workflow YAML syntax, lists jobs, and runs local CI substitute gates.

Environment:
  NLFR_GHA_READINESS_OUTPUT  Output dir (default: data/verify-gha-readiness)

Exit codes:
  0  audit + substitutes passed (or --audit-only with valid YAML)
  1  substitute gate failed
  2  usage / missing workflows
  3  workflow YAML audit failed
EOF
}

MODE="full"
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --audit-only)
      MODE="audit"
      shift
      ;;
    --substitutes-only)
      MODE="substitutes"
      shift
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

AUDIT_JSON="$OUT/workflow-audit.json"
audit_ok=true
substitutes_ok=true
sub_bash="skipped"
sub_pytest="skipped"
sub_cache_gate="skipped"

audit_workflows() {
  echo "== GHA workflow YAML audit =="
  if [[ ! -d "$WORKFLOWS_DIR" ]]; then
    echo "missing workflows dir: $WORKFLOWS_DIR" >&2
    audit_ok=false
    return 1
  fi

  if ! command -v ruby >/dev/null 2>&1; then
    echo "error: ruby required for workflow YAML audit" >&2
    audit_ok=false
    return 1
  fi

  WORKFLOWS_DIR="$WORKFLOWS_DIR" AUDIT_JSON="$AUDIT_JSON" ROOT="$ROOT" ruby -ryaml -rjson -e '
workflows_dir = ENV.fetch("WORKFLOWS_DIR")
audit_json = ENV.fetch("AUDIT_JSON")
root = ENV.fetch("ROOT")

files = Dir.glob(File.join(workflows_dir, "*.{yml,yaml}")).sort
if files.empty?
  warn "no workflow files under #{workflows_dir}"
  exit 1
end

workflows = []
errors = []
files.each do |path|
  rel = path.sub(%r{\A#{Regexp.escape(root)}/?}, "")
  entry = {"file" => rel, "workflow_name" => nil, "jobs" => [], "yaml_valid" => false}
  begin
    wf = YAML.load_file(path)
    raise "missing top-level name" unless wf.is_a?(Hash) && wf["name"]
    raise "missing jobs map" unless wf["jobs"].is_a?(Hash)

    entry["workflow_name"] = wf["name"]
    entry["yaml_valid"] = true
    wf["jobs"].each do |job_id, body|
      name = body.is_a?(Hash) ? (body["name"] || job_id) : job_id
      entry["jobs"] << {"id" => job_id, "name" => name}
    end
    puts "  OK  #{rel} — #{entry["workflow_name"]} (#{entry["jobs"].length} jobs)"
    entry["jobs"].each { |j| puts "      - #{j["id"]}: #{j["name"]}" }
  rescue StandardError => e
    entry["error"] = e.message
    errors << rel
    warn "  FAIL #{rel}: #{e.message}"
  end
  workflows << entry
end

payload = {
  "status" => errors.empty? ? "ok" : "yaml_audit_failed",
  "workflows" => workflows,
  "workflow_count" => workflows.length,
  "job_count" => workflows.sum { |w| w["jobs"].length },
}
File.write(audit_json, JSON.pretty_generate(payload) + "\n")
exit(errors.empty? ? 0 : 1)
'
}

run_substitutes() {
  echo "== Local CI substitutes (GHA offline) =="

  echo "-> bash -n scripts/*.sh"
  bash -n scripts/*.sh
  sub_bash="PASS"

  echo "-> uv run pytest -q"
  uv run pytest -q
  sub_pytest="PASS"

  echo "-> ./scripts/cache-only-ci-gate.sh"
  ./scripts/cache-only-ci-gate.sh
  sub_cache_gate="PASS"
}

if [[ "$MODE" != "substitutes" ]]; then
  if ! audit_workflows; then
    audit_ok=false
  fi
fi

if [[ "$MODE" != "audit" ]]; then
  if ! run_substitutes; then
    substitutes_ok=false
  fi
fi

export ROOT OUT MODE
export AUDIT_OK="$audit_ok" SUBSTITUTES_OK="$substitutes_ok"
export SUB_BASH="$sub_bash" SUB_PYTEST="$sub_pytest" SUB_CACHE_GATE="$sub_cache_gate"

python3 - <<'PY'
import json
import os
from datetime import datetime, timezone
from pathlib import Path

root = Path(os.environ["ROOT"])
out = Path(os.environ["OUT"])
audit_path = out / "workflow-audit.json"
audit = {}
if audit_path.exists():
    audit = json.loads(audit_path.read_text(encoding="utf-8"))

mode = os.environ.get("MODE", "full")
audit_ok = os.environ.get("AUDIT_OK", "true") == "true"
subs_ok = os.environ.get("SUBSTITUTES_OK", "true") == "true"

summary = {
    "status": "environment_blocker",
    "reason": "GitHub Actions offline — sustained green not observable from this host",
    "next_step": (
        "When Actions return: gh workflow run nlfr-proof.yml; "
        "complete GHA_RESTORE_RUNBOOK.md Phase 1–2"
    ),
    "proof_script": "verify-gha-readiness.sh",
    "observed_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    "gha_sustained_green": False,
    "workflow_audit": audit,
    "local_substitutes": {
        "bash_n_scripts": os.environ.get("SUB_BASH", "skipped"),
        "pytest": os.environ.get("SUB_PYTEST", "skipped"),
        "cache_only_ci_gate": os.environ.get("SUB_CACHE_GATE", "skipped"),
    },
    "source_kind": "collectable_v1",
    "confidence": "high",
    "redaction_state": "safe",
    "evidence_refs": [
        "script:verify-gha-readiness.sh",
        "docs/GHA_RESTORE_RUNBOOK.md",
        "docs/proof-samples/ci-offline-blocker-sample.json",
    ],
    "claim_boundary": {
        "supported": [
            "workflow YAML syntax valid locally",
            "local substitute gates pass on operator host",
            "honest negative claim: GHA sustained green not proven",
        ],
        "unsupported_until_gha_green": [
            "sustained green on nlfr-proof.yml (≥3 consecutive runs)",
            "Linux CI artifact promotion to proof-samples/",
            "CI badge as primary credibility path",
        ],
    },
}

if mode != "substitutes":
    summary["workflow_audit_status"] = "PASS" if audit_ok else "FAIL"
if mode != "audit":
    summary["local_substitutes_status"] = "PASS" if subs_ok else "FAIL"

if (
    (mode == "audit" and audit_ok)
    or (mode == "substitutes" and subs_ok)
    or (mode == "full" and audit_ok and subs_ok)
):
    summary["readiness_gate"] = "PASS_LOCAL_ONLY"
else:
    summary["readiness_gate"] = "FAIL"

(out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
print(f"Wrote {out / 'summary.json'}")
PY

if [[ "$audit_ok" != true ]]; then
  exit 3
fi
if [[ "$substitutes_ok" != true ]]; then
  exit 1
fi
