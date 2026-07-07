"""PR-ready markdown export for proof packets."""

from __future__ import annotations

import json
import re
from typing import Any

_PROMPT_KEY_RE = re.compile(
    r'"(?:prompt(?:_text|_body|_content)?|raw_prompt|system_prompt|user_prompt)"\s*:\s*"[^"]*"',
    re.IGNORECASE,
)
_HOME_PATH_RE = re.compile(r"/(?:Users|home)/[^/\"\\\s]+")


def redact_text(text: str) -> str:
    """Redact absolute home paths from free text."""

    return _HOME_PATH_RE.sub("${HOME}", text)


def redact_repo_path(path: str | None, *, repo_root: str | None = None) -> str | None:
    """Replace repo-root prefixes with ``<repo>`` for committed samples."""

    if not path:
        return None
    text = str(path)
    if repo_root:
        normalized_root = str(repo_root).rstrip("/")
        if text.startswith(normalized_root):
            return "<repo>" + text[len(normalized_root) :]
    return redact_text(text)


def export_proof_markdown(
    proof: dict[str, Any],
    *,
    db_path: str | None = None,
    manifest_path: str | None = None,
    projection_paths: dict[str, str] | None = None,
    repo_root: str | None = None,
) -> str:
    """Render a proof packet as redacted PR comment markdown."""

    lines: list[str] = [
        "## NLFR Proof Summary",
        "",
        f"**Run group:** `{proof.get('run_group', 'unknown')}`  ",
        f"**Generated:** {proof.get('generated_at', 'unknown')}  ",
        "**Export labels:** `derived_v1` · `high` · `safe`",
        "",
    ]

    summary = proof.get("summary") or {}
    if summary:
        lines.append("| Metric | Count |")
        lines.append("|--------|------:|")
        for key in sorted(summary):
            lines.append(f"| {key} | {_render_summary_value(key, summary[key])} |")
        lines.append("")

    evidence_lines = _evidence_path_lines(
        db_path=db_path,
        manifest_path=manifest_path,
        projection_paths=projection_paths,
        repo_root=repo_root,
    )
    if evidence_lines:
        lines.append("### Evidence paths")
        lines.append("")
        lines.extend(evidence_lines)
        lines.append("")

    validation = validation_status(proof)
    lines.append("### Validation status")
    lines.append("")
    lines.append(f"- **Status:** {validation['status']}")
    lines.append(f"- **Failures:** {validation['failure_count']}")
    if validation["failure_count"]:
        lines.append(
            "- **Note:** validation failures are surfaced for reviewers; "
            "unsupported boundary labels do not block export."
        )
    lines.append("")

    lines.append("---")
    lines.append("")

    for block in proof.get("blocks") or []:
        lines.extend(_render_block(block))
        lines.append("")

    footer = (
        "_Projection export only. Claims carry `source_kind`, `confidence`, "
        "`evidence_refs`, and `redaction_state`. No raw prompts or private logs._"
    )
    lines.append(footer)
    lines.append("")

    text = "\n".join(lines)
    return _scrub_sensitive_markdown(text)


#: (summary key, human label) pairs for the artifact_verification rollup, in the
#: order they read best in the top-level metrics table.
_ARTIFACT_VERIFICATION_LABELS = (
    ("total", "total"),
    ("verified_count", "verified"),
    ("present_unverified", "present-unverified"),
    ("mismatched", "mismatched"),
    ("missing", "missing"),
    ("unverified_remote", "unverified-remote"),
)


def _render_summary_value(key: str, value: Any) -> str:
    """Render a top-level summary metric for the markdown table.

    The ``artifact_verification`` rollup is a dict; rendering it with ``str()``
    leaks a raw Python dict repr (``{'total': 3, ...}``) into the table. Render it
    as a readable ``·``-separated breakdown instead, and defensively flatten any
    other dict-valued metric so a raw repr never reaches a reader.
    """

    if key == "artifact_verification" and isinstance(value, dict):
        return _render_artifact_verification(value)
    if isinstance(value, dict):
        return " · ".join(f"{k}: {value[k]}" for k in value)
    return str(value)


def _render_artifact_verification(counts: dict[str, Any]) -> str:
    """Readable one-line breakdown of the artifact-integrity verification rollup."""

    parts = [
        f"{counts.get(field, 0)} {label}"
        for field, label in _ARTIFACT_VERIFICATION_LABELS
        if field in counts
    ]
    if not parts:
        # Unexpected shape: flatten rather than emit a raw dict repr.
        return " · ".join(f"{k}: {counts[k]}" for k in counts)
    return " · ".join(parts)


def validation_status(proof: dict[str, Any]) -> dict[str, Any]:
    """Summarize validation failures without treating boundary labels as errors."""

    failure_count = int((proof.get("summary") or {}).get("failures") or 0)
    for block in proof.get("blocks") or []:
        if block.get("id") != "validation":
            continue
        metrics = block.get("metrics") or {}
        failure_count = max(failure_count, int(metrics.get("failures") or 0))
        break
    return {
        "status": "failed" if failure_count else "ok",
        "failure_count": failure_count,
    }


def _evidence_path_lines(
    *,
    db_path: str | None,
    manifest_path: str | None,
    projection_paths: dict[str, str] | None,
    repo_root: str | None,
) -> list[str]:
    lines: list[str] = []
    redacted_db = redact_repo_path(db_path, repo_root=repo_root)
    if redacted_db:
        lines.append(f"- **DB:** `{redacted_db}`")
    redacted_manifest = redact_repo_path(manifest_path, repo_root=repo_root)
    if redacted_manifest:
        lines.append(f"- **Manifest:** `{redacted_manifest}`")
    for label, path in sorted((projection_paths or {}).items()):
        redacted = redact_repo_path(path, repo_root=repo_root)
        if redacted:
            lines.append(f"- **{label}:** `{redacted}`")
    return lines


def _render_block(block: dict[str, Any]) -> list[str]:
    block_id = block.get("id") or "unknown"
    title = block.get("title") or block_id
    source_kind = block.get("source_kind") or "unknown"
    confidence = block.get("confidence") or "unknown"
    redaction_state = block.get("redaction_state") or "unknown"

    lines = [
        f"### {title}",
        "",
        f"**Labels:** `{source_kind}` · `{confidence}` · `{redaction_state}`",
        "",
    ]

    summary = block.get("summary")
    if summary:
        lines.append(redact_text(str(summary)))
        lines.append("")

    metrics = block.get("metrics") or {}
    if metrics:
        lines.append("**Metrics:**")
        for key in sorted(metrics):
            value = metrics[key]
            if value is None:
                rendered = "—"
            elif isinstance(value, bool):
                rendered = "true" if value else "false"
            else:
                rendered = redact_text(str(value))
            lines.append(f"- `{key}`: {rendered}")
        lines.append("")

    claims = block.get("claims") or []
    if claims:
        lines.append("**Claims:**")
        for claim in claims:
            lines.append(
                f"- {redact_text(str(claim))} "
                f"(`{source_kind}` / `{confidence}`)"
            )
        lines.append("")

    payload = block.get("payload")
    if isinstance(payload, dict):
        lines.extend(_render_payload(block_id, payload))

    evidence_refs = block.get("evidence_refs") or []
    if evidence_refs:
        lines.append("**Evidence refs:** " + ", ".join(f"`{ref}`" for ref in evidence_refs))
        lines.append("")

    return lines


def _render_payload(block_id: str, payload: dict[str, Any]) -> list[str]:
    lines: list[str] = []

    unsupported = payload.get("unsupported_claims")
    if isinstance(unsupported, list) and unsupported:
        labels = ", ".join(f"`{item}`" for item in unsupported)
        lines.append(f"**Unsupported claims:** {labels}")
        lines.append(
            "_Boundary labels only — export continues; these are not validation failures._"
        )
        lines.append("")

    agent = payload.get("agent")
    if isinstance(agent, dict):
        lines.append("**Agent provenance (hash-only):**")
        if agent.get("name"):
            lines.append(f"- name: `{agent['name']}`")
        if agent.get("model"):
            lines.append(f"- model: `{agent['model']}`")
        prompt_hash = agent.get("prompt_sha256")
        if prompt_hash:
            prefix = str(prompt_hash)[:12]
            lines.append(f"- prompt_sha256: `{prefix}…`")
        lines.append("")

    legs = payload.get("legs")
    if isinstance(legs, list) and legs:
        lines.append("**Cache legs:**")
        for leg in legs:
            if not isinstance(leg, dict):
                continue
            scenario = leg.get("scenario") or leg.get("run_id") or "leg"
            hit_rate = leg.get("hit_rate")
            duration = leg.get("duration_seconds")
            lines.append(
                f"- `{scenario}`: hit_rate={hit_rate}, duration_seconds={duration}"
            )
        lines.append("")

    comparison = payload.get("comparison")
    if isinstance(comparison, dict) and comparison:
        lines.append("**Cold/warm comparison:**")
        for key in sorted(comparison):
            lines.append(f"- `{key}`: {comparison[key]}")
        lines.append("")

    if block_id == "remote_execution":
        endpoints = payload.get("remote_executor_endpoints")
        if isinstance(endpoints, list) and endpoints:
            lines.append("**Remote executor endpoints:**")
            for endpoint in endpoints:
                if not isinstance(endpoint, dict):
                    continue
                label = redact_text(str(endpoint.get("label") or "unknown"))
                lines.append(f"- `{label}`")
            lines.append("")

    return lines


def _scrub_sensitive_markdown(text: str) -> str:
    """Final pass: redact home paths and strip prompt-like JSON fragments."""

    text = redact_text(text)
    text = _PROMPT_KEY_RE.sub('"prompt_redacted": "<redacted>"', text)
    return text.rstrip() + "\n"


def proof_markdown_exit_code(proof: dict[str, Any]) -> int:
    """Return 1 when validation failed; 0 when only boundary labels are unsupported."""

    return 1 if validation_status(proof)["failure_count"] else 0
