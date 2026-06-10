"""Repo-wide scan gate: raw prompt text must never appear in recorded evidence.

AGENTS.md privacy rule: raw prompts are never stored or exported — SHA-256
hash only. This gate scans committed proof samples and any local two-act spark
proof output for (a) the deterministic prompt template scaffolding rendered by
``nlfr.spark`` builders and (b) the full task_spec text of the spark scenario.
The scenario JSON itself documents the spec for skeptics (that is design
documentation, not recorded evidence) and is excluded.
"""

import json
from pathlib import Path

from nlfr.agent_receipt import FORBIDDEN_PROMPT_KEYS
from nlfr.spark import load_spark_scenario

ROOT = Path(__file__).resolve().parents[1]
SCENARIO_PATH = ROOT / "demo" / "scenarios" / "two-act-underspec.json"

#: Strings that only ever exist inside a rendered agent prompt.
PROMPT_TEMPLATE_NEEDLES = [
    "You are a coding agent completing one bounded task in a Bazel Python monorepo.",
    "You are a coding agent fixing your previous change in a Bazel Python monorepo.",
    "--- recorded failure evidence ---",
    "OUTPUT CONTRACT:",
]

#: Evidence roots covered by the gate (recorded artifacts and promoted samples).
SCAN_ROOTS = [
    ROOT / "docs" / "proof-samples",
    *sorted(ROOT.glob("data/two-act-spark*")),
    *sorted(ROOT.glob("data/agent-*")),
]

#: Files that intentionally document the templates (source/docs), never evidence.
EXCLUDED_SUFFIXES = {".py", ".sh"}


def _needles() -> list[str]:
    needles = list(PROMPT_TEMPLATE_NEEDLES)
    if SCENARIO_PATH.exists():
        scenario = load_spark_scenario(SCENARIO_PATH)
        needles.append(scenario["task_spec"])
    return needles


def _scan_files():
    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix in EXCLUDED_SUFFIXES:
                continue
            if "bazel-output-" in path.as_posix():
                continue
            yield path


def test_no_prompt_text_in_recorded_evidence():
    needles = _needles()
    leaks: list[str] = []
    for path in _scan_files():
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for needle in needles:
            if needle in text:
                leaks.append(f"{path.relative_to(ROOT)}: {needle[:60]!r}")
    assert not leaks, "raw prompt text leaked into recorded evidence:\n" + "\n".join(leaks)


def test_no_forbidden_prompt_keys_in_recorded_receipts_and_provenance():
    """Any receipt/provenance JSON in evidence roots must be hash-only."""

    offenders: list[str] = []
    for path in _scan_files():
        if path.name not in {"agent-receipt.json", "agent-provenance.json"}:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if _contains_forbidden_key(payload):
            offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, f"raw prompt fields found in: {offenders}"


def _contains_forbidden_key(obj) -> bool:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in FORBIDDEN_PROMPT_KEYS and value:
                return True
            if _contains_forbidden_key(value):
                return True
    elif isinstance(obj, list):
        return any(_contains_forbidden_key(item) for item in obj)
    return False


def test_projection_exports_omit_prompt_template_text():
    """Graph/proof/compare projections under evidence roots carry hashes only."""

    needles = PROMPT_TEMPLATE_NEEDLES
    leaks: list[str] = []
    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        for path in sorted(root.rglob("projections/*.json")):
            text = path.read_text(encoding="utf-8", errors="ignore")
            for needle in needles:
                if needle in text:
                    leaks.append(f"{path.relative_to(ROOT)}: {needle[:60]!r}")
    assert not leaks, "prompt template text leaked into projections:\n" + "\n".join(leaks)
