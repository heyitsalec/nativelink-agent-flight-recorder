"""Deterministic evaluator: truth-labeled verdicts + next steps over evidence.

This is the closed-loop "brain". It reads back what the recorder already
captured — run status, failures, cache events, changes, agent provenance, raw
bazel log artifacts — and produces a versioned verdict (``nlfr.evaluation.v1``)
whose every claim is a reproducible function of that evidence:

* the verdict is ALWAYS ``source_kind: "derived_v1"`` (NLFR computed a
  judgment; it did not directly observe "readiness"), with confidence set by
  the weakest consulted input and ``evidence_refs`` unioned from every row it
  actually read;
* ``next_steps`` is a closed action vocabulary with an EXPLICIT precedence
  contract (``record_environment_blocker`` > ``rerun_validation`` >
  ``dispatch_fix_with_evidence`` > ``attach_missing_evidence`` >
  ``none_complete``) — callers branch on ``next_steps[0]`` only;
* degraded inputs degrade the verdict honestly: no raw logs means
  ``unclassified`` + ``attach_missing_evidence``, never a guess.

The failure classification and evidence-excerpt logic moved here from
:mod:`nlfr.spark` (which keeps thin delegating wrappers): it is loop
infrastructure, not demo-scenario code. No LLM is ever consulted for a
verdict — the deterministic rules below are the whole story.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nlfr.projectors.common import rows, run_rows
from nlfr.projectors.compare import require_run_group
from nlfr.projectors.proof import export_proof_packet
from nlfr.projectors.proof_markdown import validation_status
from nlfr.redaction import RedactionConfig, redact_payload, redact_text

EVALUATION_SCHEMA_VERSION = "nlfr.evaluation.v1"

#: Signatures of toolchain/startup failures that must NEVER count as an honest
#: scenario red — bazel died before evaluating the change under test.
TOOLCHAIN_FAILURE_SIGNATURES = (
    "Bazel compatibility check failed",
    "is not compatible with module",
    "Error computing the main repository mapping",
    "The command is only supported from within a workspace",
    "Error downloading",
    "command not found",
    "FATAL: bazel exited",
)

#: The next-step precedence contract. Tested, published, and load-bearing:
#: a pending on-disk edit must be re-validated before dispatching a NEW fix,
#: and an environment blocker preempts everything (retrying into a broken
#: toolchain fabricates agent-was-wrong narratives from environment noise).
NEXT_STEP_PRECEDENCE = (
    "record_environment_blocker",
    "rerun_validation",
    "dispatch_fix_with_evidence",
    "attach_missing_evidence",
    "none_complete",
)

_HOME_PATH = re.compile(r"(/Users/[^\s\"')(]+|/home/[^\s\"')(]+|/private/var/[^\s\"')(]*)")
_LOG_NAMES = ("bazel.stderr.txt", "bazel.stdout.txt")


def classify_validation_failure(
    artifact_root: str | Path,
    *,
    attribution_target: str | None = None,
    signatures: tuple[str, ...] = TOOLCHAIN_FAILURE_SIGNATURES,
) -> dict[str, Any]:
    """Classify a red validation leg from its recorded bazel log artifacts.

    A red is only an honest scenario failure when bazel actually evaluated the
    change under test: the recorded output must reference the attribution
    target and must not match toolchain/startup failure signatures. With no
    ``attribution_target`` the strongest honest claim is
    ``unattributed_failure`` (``attribution_target_referenced: None`` — there
    was nothing to attribute against, which is different from "checked and
    absent").
    """

    root = Path(artifact_root)
    text = ""
    for name in _LOG_NAMES:
        path = root / name
        if path.exists():
            text += path.read_text(encoding="utf-8", errors="replace")
    matched = [signature for signature in signatures if signature in text]
    referenced: bool | None
    if attribution_target is None:
        referenced = None
    else:
        referenced = attribution_target in text
    if matched:
        return {
            "classification": "toolchain_failure",
            "honest_scenario_failure": False,
            "matched_signatures": matched,
            "attribution_target_referenced": referenced,
        }
    if not referenced:
        return {
            "classification": "unattributed_failure",
            "honest_scenario_failure": False,
            "matched_signatures": [],
            "attribution_target_referenced": referenced,
        }
    return {
        "classification": "scenario_validation_failure",
        "honest_scenario_failure": True,
        "matched_signatures": [],
        "attribution_target_referenced": True,
    }


def failure_excerpt(artifact_root: str | Path, *, max_lines: int = 80) -> str:
    """Extract a redacted failure excerpt from recorded bazel log artifacts.

    Reads the recorded ``bazel.stderr.txt`` / ``bazel.stdout.txt`` artifacts of
    a red validation run and returns the failure region (first failure marker
    to the end, capped), with absolute host paths redacted. This is the
    dogfooding hook: fix-loop debugging context comes from the recorder's own
    immutable evidence, never from re-running anything.
    """

    root = Path(artifact_root)
    sections = []
    for name in _LOG_NAMES:
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
    # Redact with the FULL detector registry before returning: any hash a
    # caller computes over this excerpt must match the bytes that survive the
    # downstream redact_payload gate (which rewrites every multi-segment
    # absolute path — /nix/store, /private/tmp, execroot — not just home
    # paths), or the verdict would carry a false integrity claim.
    excerpt = "\n\n".join(sections) + "\n"
    return str(redact_text(excerpt, RedactionConfig()).payload)


def evaluate_run_group(
    conn: sqlite3.Connection,
    run_group: str,
    *,
    artifact_root: str | Path | None = None,
    attribution_target: str | None = None,
    workspace: str | Path | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Evaluate one run group's recorded evidence into a truth-labeled verdict.

    Scoping is deliberate: ``validation_status`` semantics are run-group-wide,
    so callers driving an iterative loop must give each iteration its own run
    group and evaluate that group explicitly (mixing a red and a green leg in
    one group keeps the group red — by design, not by accident).
    """

    require_run_group(conn, "evaluate", run_group)
    runs = run_rows(conn, run_group)
    run_ids = [run["id"] for run in runs]

    packet = export_proof_packet(conn, run_group=run_group)
    status = validation_status(packet)
    failed = status["status"] == "failed"

    target_rows = rows(conn, "targets", run_ids)
    failure_rows = rows(conn, "failures", run_ids)
    cache_rows = rows(conn, "cache_events", run_ids)
    change_rows = rows(conn, "changes", run_ids)
    proof_block_rows = rows(conn, "proof_blocks", run_ids)
    artifact_reference_rows = rows(conn, "artifact_references", run_ids)

    failed_labels = [
        row["label"]
        for row in target_rows
        if str(row.get("status") or "").upper() == "FAILED"
    ]
    failures = [
        {
            "failure_kind": row.get("failure_kind"),
            "message": row.get("message"),
            "span": row.get("span"),
            "attributed_targets": failed_labels,
        }
        for row in failure_rows
    ]

    logs_available = artifact_root is not None and any(
        (Path(artifact_root) / name).exists() for name in _LOG_NAMES
    )

    if not failed:
        classification: dict[str, Any] = {
            "classification": "first_pass_success",
            "honest_scenario_failure": None,
            "matched_signatures": [],
            "attribution_target_referenced": None,
        }
    elif logs_available:
        classification = classify_validation_failure(
            artifact_root,  # type: ignore[arg-type]
            attribution_target=attribution_target,
        )
    else:
        classification = {
            "classification": "unclassified",
            "reason": "raw_logs_unavailable",
            "honest_scenario_failure": None,
            "matched_signatures": [],
            "attribution_target_referenced": None,
        }

    failure_evidence: dict[str, Any] | None = None
    if failed and logs_available:
        try:
            excerpt = failure_excerpt(artifact_root)  # type: ignore[arg-type]
        except ValueError:
            excerpt = None
        if excerpt is not None:
            failure_evidence = {
                "excerpt": excerpt,
                "excerpt_sha256": hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
                "refs": [
                    f"artifact:{name}"
                    for name in _LOG_NAMES
                    if (Path(artifact_root) / name).exists()  # type: ignore[arg-type]
                ],
            }

    hits = sum(1 for row in cache_rows if row.get("hit") in (1, True))
    misses = sum(1 for row in cache_rows if row.get("hit") in (0, False))
    cache = {
        "hits": hits,
        "misses": misses,
        "hit_rate": (hits / (hits + misses)) if (hits + misses) else None,
    }

    provenance_classes: dict[str, int] = {}
    for row in proof_block_rows:
        if row.get("block_kind") != "agent_provenance":
            continue
        payload = row.get("payload") or {}
        agent = payload.get("agent") if isinstance(payload, dict) else None
        provenance_class = (agent or {}).get("provenance_class") or "unknown"
        provenance_classes[provenance_class] = provenance_classes.get(provenance_class, 0) + 1

    changed_paths = sorted({row["path"] for row in change_rows if row.get("path")})
    pending_paths = _pending_workspace_edits(change_rows, workspace)

    next_steps = _next_steps(
        failed=failed,
        classification=classification,
        failure_evidence=failure_evidence,
        logs_available=logs_available,
        pending_paths=pending_paths,
        changed_paths=changed_paths,
        attribution_target=attribution_target,
    )

    # Every table this evaluation actually read weighs into the truth quad:
    # the agent_provenance rollup consults proof_blocks and the
    # artifact_verification rollup consults artifact_references, so a low-
    # confidence row in either honestly drags the verdict's confidence down.
    consulted = [
        *runs,
        *target_rows,
        *failure_rows,
        *cache_rows,
        *change_rows,
        *proof_block_rows,
        *artifact_reference_rows,
    ]
    evidence_refs = [f"run-group:{run_group}"]
    for row in consulted:
        for ref in row.get("evidence_refs") or []:
            if ref not in evidence_refs:
                evidence_refs.append(ref)
    if failure_evidence:
        for ref in failure_evidence["refs"]:
            if ref not in evidence_refs:
                evidence_refs.append(ref)

    verdict = {
        "schema_version": EVALUATION_SCHEMA_VERSION,
        "generated_at": generated_at or _timestamp(),
        "run_group": run_group,
        "status": status,
        "failures": failures,
        "classification": classification,
        "failure_evidence": failure_evidence,
        "cache": cache,
        "artifact_verification": (packet.get("summary") or {}).get("artifact_verification"),
        "agent_provenance": {"classes": provenance_classes},
        "next_steps": next_steps,
        "source_kind": "derived_v1",
        "confidence": _weakest_confidence(consulted),
        "evidence_refs": evidence_refs,
        "redaction_state": "safe",
    }
    result = redact_payload(verdict, RedactionConfig())
    return result.payload  # type: ignore[return-value]


def _pending_workspace_edits(
    change_rows: list[dict[str, Any]], workspace: str | Path | None
) -> list[str]:
    """Directly observable pending edits: workspace bytes differ from the
    newest recorded after-hash for a changed path. Without a workspace to
    inspect, NLFR cannot observe pending edits and honestly reports none."""

    if workspace is None:
        return []
    root = Path(workspace)
    newest_by_path: dict[str, str] = {}
    for row in change_rows:  # rows() orders by created_at; last write wins
        path = row.get("path")
        after = row.get("after_hash")
        if path and after:
            newest_by_path[str(path)] = str(after)
    pending = []
    for path, after_hash in sorted(newest_by_path.items()):
        # Recorded change paths are workspace-relative; refuse anything that
        # would escape the workspace (absolute or ..-traversing) rather than
        # hash an arbitrary host file a crafted row points at.
        parts = Path(path)
        if parts.is_absolute() or ".." in parts.parts:
            continue
        candidate = root / path
        if not candidate.is_file():
            continue
        digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
        if digest != after_hash:
            pending.append(path)
    return pending


def _next_steps(
    *,
    failed: bool,
    classification: dict[str, Any],
    failure_evidence: dict[str, Any] | None,
    logs_available: bool,
    pending_paths: list[str],
    changed_paths: list[str],
    attribution_target: str | None,
) -> list[dict[str, Any]]:
    steps: dict[str, dict[str, Any]] = {}

    if classification["classification"] == "toolchain_failure":
        steps["record_environment_blocker"] = _step(
            "record_environment_blocker",
            "recorded logs match toolchain/startup failure signatures; "
            "retrying would fabricate an agent-failure narrative from "
            "environment noise",
            {"matched_signatures": classification["matched_signatures"]},
        )
    if pending_paths:
        steps["rerun_validation"] = _step(
            "rerun_validation",
            "workspace bytes differ from the newest recorded after-hash: an "
            "applied edit has not been validated yet",
            {"pending_paths": pending_paths},
        )
    if (
        failed
        and classification["classification"] == "scenario_validation_failure"
        and failure_evidence is not None
    ):
        steps["dispatch_fix_with_evidence"] = _step(
            "dispatch_fix_with_evidence",
            "validation red is honestly attributed to the target under test; "
            "recorded failure evidence is available to hand to a fixing agent",
            {
                "evidence_excerpt_sha256": failure_evidence["excerpt_sha256"],
                "changed_paths": changed_paths,
                "attribution_target": attribution_target,
            },
        )
    if failed:
        missing = []
        if not logs_available:
            missing.append("raw_validation_logs")
        elif failure_evidence is None:
            missing.append("failure_excerpt")
        if classification["classification"] == "unattributed_failure":
            missing.append("failure_attribution")
        if missing:
            steps["attach_missing_evidence"] = _step(
                "attach_missing_evidence",
                "evaluation is degraded; the named evidence is absent from "
                "the record",
                {"missing": missing},
            )
    if not failed:
        steps["none_complete"] = _step(
            "none_complete",
            "validation is green and nothing is outstanding",
            {},
        )

    return [steps[action] for action in NEXT_STEP_PRECEDENCE if action in steps]


def _step(action: str, reason: str, inputs: dict[str, Any]) -> dict[str, Any]:
    return {
        "action": action,
        "reason": reason,
        "inputs": inputs,
        "source_kind": "derived_v1",
        "confidence": "high",
        "evidence_refs": [],
        "redaction_state": "safe",
    }


def _weakest_confidence(consulted: list[dict[str, Any]]) -> str:
    """Mirror the proof-packet rollup rule: high only if every input is high,
    low if any input is low, else medium."""

    if not consulted:
        return "unknown"
    values = {row.get("confidence") for row in consulted}
    if values == {"high"}:
        return "high"
    if "low" in values:
        return "low"
    return "medium"


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
