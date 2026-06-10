"""Two-act spark helpers: prompt building, response extraction, failure evidence.

The two-act spark records a real agent being wrong, then fixing itself with the
recorder's own evidence:

* Act 1 — a headless Claude Code agent authors a module from an UNDERSPECIFIED
  task spec. A hidden Bazel test (never shown to the agent; the agent runs in
  an empty scratch cwd) encodes the full requirement. Real ``bazel test``
  through the NativeLink cache catches the gap: a red validation leg.
* Act 2 — the agent receives the RECORDED failure evidence (a bazel test
  output excerpt captured as a flight-recorder artifact) and produces the fix:
  a green validation leg with warm cache hits on unchanged targets.

Prompts are deterministic functions of the scenario JSON plus workspace file
contents, so a skeptic can rebuild the exact prompt and check its SHA-256
against the receipt. Raw prompts are never stored (AGENTS.md): hash only.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

SPARK_SCHEMA_VERSION = "nlfr.spark.scenario.v1"

#: Keys that must never appear in a spark scenario (raw prompt storage guard).
FORBIDDEN_SCENARIO_KEYS = frozenset({"prompt", "raw_prompt", "prompt_text"})

_FENCED_BLOCK = re.compile(r"```(?:python)?[ \t]*\n(.*?)```", re.DOTALL)
_HOME_PATH = re.compile(r"(/Users/[^\s\"')(]+|/home/[^\s\"')(]+|/private/var/[^\s\"')(]*)")


def load_spark_scenario(path: str | Path) -> dict[str, Any]:
    """Load and validate a two-act spark scenario JSON file."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"spark scenario must be a JSON object: {path}")
    if payload.get("schema_version") != SPARK_SCHEMA_VERSION:
        raise ValueError(
            f"spark scenario schema_version must be {SPARK_SCHEMA_VERSION}: {path}"
        )
    _reject_forbidden_keys(payload, path="scenario")
    for field in ("scenario_id", "task_spec", "output_contract"):
        if not isinstance(payload.get(field), str) or not payload[field]:
            raise ValueError(f"spark scenario missing string field {field}: {path}")
    workload = payload.get("workload")
    if not isinstance(workload, dict) or not workload.get("target_file"):
        raise ValueError(f"spark scenario missing workload.target_file: {path}")
    hidden = payload.get("hidden_validation")
    if not isinstance(hidden, dict) or not hidden.get("path") or not hidden.get("content_lines"):
        raise ValueError(f"spark scenario missing hidden_validation: {path}")
    return payload


def apply_workspace_setup(scenario: dict[str, Any], workspace: str | Path) -> dict[str, str]:
    """Write the hidden validation test and BUILD additions into a workspace copy.

    Returns a mapping of written relative paths to their SHA-256 hashes. The
    hidden test encodes the FULL requirement; it is written only into the
    temporary validation workspace and never into the agent's prompt or cwd.
    """

    root = Path(workspace)
    written: dict[str, str] = {}

    # Scenario-documented file overrides for the temp validation workspace
    # (e.g. stripping a demo-template module dependency the validation never
    # uses). Each override carries a "reason" in the scenario JSON so skeptics
    # can audit exactly how the validation workspace differs from the template.
    for override in scenario.get("workspace_overrides", []):
        override_path = root / str(override["path"])
        content = "\n".join(str(line) for line in override["content_lines"]) + "\n"
        override_path.parent.mkdir(parents=True, exist_ok=True)
        override_path.write_text(content, encoding="utf-8")
        written[str(override["path"])] = _sha256(content)

    hidden = scenario["hidden_validation"]
    hidden_path = root / str(hidden["path"])
    hidden_content = "\n".join(str(line) for line in hidden["content_lines"]) + "\n"
    hidden_path.parent.mkdir(parents=True, exist_ok=True)
    hidden_path.write_text(hidden_content, encoding="utf-8")
    written[str(hidden["path"])] = _sha256(hidden_content)

    build = scenario.get("build_additions")
    if isinstance(build, dict) and build.get("path") and build.get("content_lines"):
        build_path = root / str(build["path"])
        addition = "\n".join(str(line) for line in build["content_lines"]) + "\n"
        existing = build_path.read_text(encoding="utf-8") if build_path.exists() else ""
        if addition not in existing:
            build_path.write_text(existing + "\n" + addition, encoding="utf-8")
        written[str(build["path"])] = _sha256(build_path.read_text(encoding="utf-8"))

    return written


def build_act1_prompt(scenario: dict[str, Any], workspace: str | Path) -> str:
    """Deterministic Act 1 prompt: context files + underspecified task spec."""

    root = Path(workspace)
    sections = [
        "You are a coding agent completing one bounded task in a Bazel Python monorepo.",
        "Repository context (read-only):",
        "",
    ]
    for relative in scenario.get("workload", {}).get("context_files", []):
        content = (root / str(relative)).read_text(encoding="utf-8")
        sections.append(f"--- {relative} ---")
        sections.append(content.rstrip("\n"))
        sections.append("")
    sections.append("TASK:")
    sections.append(str(scenario["task_spec"]).rstrip("\n"))
    sections.append("")
    sections.append("OUTPUT CONTRACT:")
    sections.append(str(scenario["output_contract"]).rstrip("\n"))
    return "\n".join(sections) + "\n"


def build_act2_prompt(
    scenario: dict[str, Any],
    *,
    act1_file_content: str,
    failure_evidence: str,
) -> str:
    """Deterministic Act 2 prompt: spec + prior file + RECORDED failure evidence."""

    target_file = str(scenario["workload"]["target_file"])
    sections = [
        "You are a coding agent fixing your previous change in a Bazel Python monorepo.",
        "",
        "TASK (unchanged):",
        str(scenario["task_spec"]).rstrip("\n"),
        "",
        f"Your previously submitted {target_file}:",
        f"--- {target_file} ---",
        act1_file_content.rstrip("\n"),
        "",
        "The change was validated by running the project's Bazel test suite through",
        "a NativeLink-backed flight recorder. Validation FAILED. The recorded failure",
        "evidence (bazel test output captured as a flight-recorder artifact) follows:",
        "",
        "--- recorded failure evidence ---",
        failure_evidence.rstrip("\n"),
        "",
        f"Produce a corrected {target_file} that satisfies the recorded failing",
        "requirement while keeping the original task spec satisfied.",
        "",
        "OUTPUT CONTRACT:",
        str(scenario["output_contract"]).rstrip("\n"),
    ]
    return "\n".join(sections) + "\n"


def extract_python_file(response_text: str) -> str:
    """Extract the agent-authored file content from the first fenced code block."""

    match = _FENCED_BLOCK.search(response_text)
    if match is None:
        raise ValueError("agent response contained no fenced code block")
    content = match.group(1)
    if not content.strip():
        raise ValueError("agent response code block was empty")
    if not content.endswith("\n"):
        content += "\n"
    return content


#: Signatures of toolchain/startup failures that must NEVER count as an honest
#: act-1 red leg — bazel died before executing the agent's code.
TOOLCHAIN_FAILURE_SIGNATURES = (
    "Bazel compatibility check failed",
    "is not compatible with module",
    "Error computing the main repository mapping",
    "The command is only supported from within a workspace",
    "Error downloading",
    "command not found",
    "FATAL: bazel exited",
)


def classify_validation_failure(
    artifact_root: str | Path,
    *,
    hidden_target: str,
) -> dict[str, Any]:
    """Classify a red validation leg as honest scenario failure or toolchain blocker.

    An act-1 red is only honest when bazel actually evaluated the agent's code:
    the recorded output must reference the hidden validation target (test
    failure or its build failure) and must not match toolchain/startup failure
    signatures. Anything else is an environment problem and must be recorded as
    a truth-labeled blocker, never presented as "the recorder caught the agent".
    """

    root = Path(artifact_root)
    text = ""
    for name in ("bazel.stderr.txt", "bazel.stdout.txt"):
        path = root / name
        if path.exists():
            text += path.read_text(encoding="utf-8", errors="replace")
    matched = [sig for sig in TOOLCHAIN_FAILURE_SIGNATURES if sig in text]
    hidden_referenced = hidden_target in text
    if matched:
        return {
            "classification": "toolchain_failure",
            "honest_scenario_failure": False,
            "matched_signatures": matched,
            "hidden_target_referenced": hidden_referenced,
        }
    if not hidden_referenced:
        return {
            "classification": "unattributed_failure",
            "honest_scenario_failure": False,
            "matched_signatures": [],
            "hidden_target_referenced": False,
        }
    return {
        "classification": "scenario_validation_failure",
        "honest_scenario_failure": True,
        "matched_signatures": [],
        "hidden_target_referenced": True,
    }


def failure_excerpt(artifact_root: str | Path, *, max_lines: int = 80) -> str:
    """Extract a redacted bazel test failure excerpt from recorded run artifacts.

    Reads the recorded ``bazel.stderr.txt`` / ``bazel.stdout.txt`` artifacts of
    a red validation run and returns the failure region (from the first line
    mentioning a failure to the end), with absolute host paths redacted. This
    is the dogfooding hook: Act 2 debugging context comes from the recorder's
    own immutable evidence, not from re-running anything.
    """

    root = Path(artifact_root)
    sections = []
    for name in ("bazel.stderr.txt", "bazel.stdout.txt"):
        path = root / name
        if not path.exists():
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        markers = [
            index
            for index, line in enumerate(lines)
            if "FAIL" in line or "Error" in line or "error:" in line
        ]
        if not markers:
            continue
        start = markers[0]
        excerpt_lines = lines[start : start + max_lines]
        body = "\n".join(_HOME_PATH.sub("<redacted-path>", line) for line in excerpt_lines)
        sections.append(f"[artifact: {name}]\n{body}")
    if not sections:
        raise ValueError(f"no failure evidence found under {root}")
    # Both streams matter: bazel's summary lands on stderr while the failing
    # test's own output (e.g. unittest assertion detail) lands on stdout.
    return "\n\n".join(sections) + "\n"


def _reject_forbidden_keys(obj: Any, *, path: str) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in FORBIDDEN_SCENARIO_KEYS:
                raise ValueError(f"spark scenario must not store raw prompts: {path}.{key}")
            _reject_forbidden_keys(value, path=f"{path}.{key}")
    elif isinstance(obj, list):
        for index, item in enumerate(obj):
            _reject_forbidden_keys(item, path=f"{path}[{index}]")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
