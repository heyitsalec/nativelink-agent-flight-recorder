#!/usr/bin/env bash
set -euo pipefail

# Deterministic stand-in for the Claude Code CLI used by two-act-spark-proof.sh
# stub mode (NLFR_SPARK_CLAUDE_BIN) and tests. Emits claude-shaped result JSON.
#
# HONESTY: receipts produced from this stub are labeled simulated_v1 by
# nlfr agent-invoke (cli name is not "claude"), and the agent provenance leg is
# downgraded to stub_receipt_v1 / simulated_v1. The Act 1 implementation below
# is the same faithful best-effort a spec-following agent would produce — it
# genuinely fails the hidden second-window test under real bazel; it is not
# corrupted code. Act 2 applies the fix the recorded failure evidence implies.

if [[ "${1:-}" == "--version" ]]; then
  echo "stub-claude 1.0.0 (deterministic spark fixture)"
  exit 0
fi

PROMPT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    -p)
      PROMPT="$2"
      shift 2
      ;;
    --output-format|--model)
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done

PROMPT="$PROMPT" python3 - <<'PY'
import hashlib
import json
import os

prompt = os.environ["PROMPT"]

ACT1_FILE = '''"""Escalation tiers for the tasks triage library."""

from tasks import policy

_TIERS = ["p0", "p1", "p2"]
STALENESS_WINDOW_DAYS = 14


def escalation_tier(score, age_days):
    if score >= policy.URGENT_THRESHOLD:
        tier_index = 0
    elif score >= policy.NORMAL_THRESHOLD:
        tier_index = 1
    else:
        tier_index = 2
    if age_days >= STALENESS_WINDOW_DAYS:
        tier_index = max(tier_index - 1, 0)
    return _TIERS[tier_index]
'''

ACT2_FILE = '''"""Escalation tiers for the tasks triage library."""

from tasks import policy

_TIERS = ["p0", "p1", "p2"]
STALENESS_WINDOW_DAYS = 14
SECOND_STALENESS_WINDOW_DAYS = 60


def escalation_tier(score, age_days):
    if score >= policy.URGENT_THRESHOLD:
        tier_index = 0
    elif score >= policy.NORMAL_THRESHOLD:
        tier_index = 1
    else:
        tier_index = 2
    if age_days >= STALENESS_WINDOW_DAYS:
        tier_index = max(tier_index - 1, 0)
    if age_days >= SECOND_STALENESS_WINDOW_DAYS:
        tier_index = max(tier_index - 1, 0)
    return _TIERS[tier_index]
'''

is_act2 = "recorded failure evidence" in prompt
body = ACT2_FILE if is_act2 else ACT1_FILE
label = "act2" if is_act2 else "act1"
sentence = (
    "Corrected module adding the second escalation window the failure evidence shows."
    if is_act2
    else "Implemented escalation_tier per the spec with the 14-day staleness bump."
)
result_text = f"{sentence}\n\n```python\n{body}```\n"
prompt_digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

payload = {
    "type": "result",
    "subtype": "success",
    "is_error": False,
    "duration_ms": 1200,
    "duration_api_ms": 900,
    "num_turns": 1,
    "result": result_text,
    "session_id": f"stub-{label}-{prompt_digest[:12]}",
    "total_cost_usd": 0.0,
    "usage": {
        "input_tokens": len(prompt) // 4,
        "output_tokens": len(result_text) // 4,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
    },
    "modelUsage": {"stub-deterministic-model": {"output_tokens": len(result_text) // 4}},
}
print(json.dumps(payload))
PY
