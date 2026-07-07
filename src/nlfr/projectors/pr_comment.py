"""Compact PR-comment / CI-attachment projection of a proof packet.

Issue #87: land NLFR's honest proof packet in the review surface where incumbent
BEP UIs (BuildBuddy / EngFlow) already sit. This projector renders a *compact*,
redacted summary of a proof packet — status, cache economics, the
artifact-integrity verification rollup (local **and** remote_* tiers),
agent-receipt provenance presence, and an optional in-toto attestation ref — in
two paired shapes:

* ``render_pr_comment_markdown`` -> a short markdown block to paste as a PR
  comment, and
* ``build_pr_comment_summary`` -> the machine-readable JSON sidecar behind it,
  suitable for upload as a CI artifact.

Both are built ONLY from recorded evidence already present in the proof packet
(which the proof projector redacts at its own sharing boundary). This is *not*
the verbose ``nlfr proof export --format markdown`` renderer — that emits every
block; this is the scannable summary. It never invents backend state, cost
figures, or cross-machine ("fleet") data, and it preserves NLFR's honest
boundary: remote-only references stay unverified unless an independent CAS probe
recorded a verdict.

The sharing boundary is enforced twice, honestly: every string that reaches the
output is routed through :mod:`nlfr.redaction` (``redact_payload`` for the JSON,
``redact_text`` for the markdown) so a ``nlfr redact --check`` over either
artifact is clean, and the summary's ``redaction_state`` is upgraded
``safe`` -> ``redacted`` if the scrubber actually changed anything.
"""

from __future__ import annotations

from typing import Any

from nlfr.projectors.proof_markdown import validation_status
from nlfr.redaction import RedactionConfig, redact_payload, redact_text

SCHEMA_VERSION = 1
PROJECTION_KIND = "pr_comment"

#: (packet field, human label) for the local artifact-verification tier.
_LOCAL_FIELDS = (
    ("verified_count", "verified"),
    ("present_unverified", "present-unverified"),
    ("mismatched", "mismatched"),
    ("missing", "missing"),
)

#: (packet field, human label) for the independent-CAS remote tier (issue #81).
#: ``unverified_remote`` is reported separately: it means "remote reference, no
#: CAS probe supplied" — neither confirmed present nor absent.
_REMOTE_FIELDS = (
    ("remote_verified", "verified"),
    ("remote_present", "present"),
    ("remote_mismatch", "mismatch"),
    ("remote_missing", "missing"),
)


def build_pr_comment_summary(
    proof: dict[str, Any],
    *,
    in_toto: dict[str, Any] | None = None,
    config: RedactionConfig | None = None,
) -> dict[str, Any]:
    """Build the redacted, machine-readable compact summary (the JSON sidecar).

    ``in_toto`` is an optional ``{"exported": bool, "ref": str | None}`` mapping
    describing whether an in-toto attestation was exported for this run group and,
    if so, a redactable reference to cite (e.g. a content digest prefix). It is
    NEVER fabricated: when omitted the summary honestly reports
    ``{"exported": false, "ref": null}``.

    The assembled dict is walked through :func:`nlfr.redaction.redact_payload`
    before it is returned, so every string value is scrubbed and the top-level
    ``redaction_state`` is honestly upgraded ``safe`` -> ``redacted`` if anything
    was changed. The result passes ``nlfr redact --check`` byte-for-byte.
    """

    summary = {
        "schema_version": SCHEMA_VERSION,
        "projection_kind": PROJECTION_KIND,
        "generated_at": proof.get("generated_at", "unknown"),
        "run_group": proof.get("run_group", "unknown"),
        # Compact-projection export labels, mirroring the verbose renderer's
        # "derived_v1 · high · safe" export line. ``redaction_state`` lives at the
        # TOP LEVEL (not nested) so redact_payload upgrades it safe -> redacted
        # when a scrub fires anywhere in the summary — the flag bubbles up to the
        # nearest ancestor carrying redaction_state, which is this object.
        "source_kind": "derived_v1",
        "confidence": "high",
        "redaction_state": "safe",
        "status": _status_section(proof),
        "cache": _cache_section(proof),
        "artifact_verification": _artifact_verification_section(proof),
        "agent_receipt": _agent_receipt_section(proof),
        "in_toto": _in_toto_section(in_toto),
        "build_tool": _build_tool_section(proof),
    }
    result = redact_payload(summary, config or RedactionConfig())
    return result.payload  # type: ignore[return-value]


def pr_comment_exit_code(summary: dict[str, Any]) -> int:
    """Return 1 when validation failures are present; 0 otherwise.

    Mirrors ``proof_markdown_exit_code``: unsupported *boundary* labels (worker
    identity, queue time, …) are NOT failures and never set exit 1.
    """

    return 1 if (summary.get("status") or {}).get("failures") else 0


# --------------------------------------------------------------------------- #
# Section builders (recorded evidence only — nothing invented)
# --------------------------------------------------------------------------- #


def _status_section(proof: dict[str, Any]) -> dict[str, Any]:
    status = validation_status(proof)
    return {"status": status["status"], "failures": status["failure_count"]}


def _cache_section(proof: dict[str, Any]) -> dict[str, Any]:
    metrics = (_block_by_id(proof, "cache") or {}).get("metrics") or {}
    section: dict[str, Any] = {
        "hits": int(metrics.get("hits") or 0),
        "misses": int(metrics.get("misses") or 0),
        "unknown": int(metrics.get("unknown") or 0),
        "hit_rate": metrics.get("hit_rate"),
        "cache_events": int((proof.get("summary") or {}).get("cache_events") or 0),
    }
    comparison = ((_block_by_id(proof, "cache_economics") or {}).get("payload") or {}).get(
        "comparison"
    )
    if isinstance(comparison, dict) and comparison:
        # Recorded cold/warm deltas only — never a dollar/cost figure.
        section["cold_warm"] = {
            "hit_rate_delta": comparison.get("hit_rate_delta"),
            "duration_delta_seconds": comparison.get("duration_delta_seconds"),
            "warm_hit_rate_higher": bool(comparison.get("warm_hit_rate_higher")),
            "warm_duration_lower": bool(comparison.get("warm_duration_lower")),
        }
    return section


def _artifact_verification_section(proof: dict[str, Any]) -> dict[str, Any]:
    counts = (proof.get("summary") or {}).get("artifact_verification") or {}
    return {
        "total": int(counts.get("total") or 0),
        "local": {label: int(counts.get(field) or 0) for field, label in _LOCAL_FIELDS},
        "remote": {label: int(counts.get(field) or 0) for field, label in _REMOTE_FIELDS},
        # A remote reference with no CAS probe: neither present nor absent proven.
        "unverified_remote": int(counts.get("unverified_remote") or 0),
    }


def _agent_receipt_section(proof: dict[str, Any]) -> dict[str, Any]:
    """Presence/absence of agent-receipt provenance — hash-only, never raw prompt."""

    agents: list[dict[str, Any]] = []
    for block in proof.get("blocks") or []:
        if block.get("kind") != "agent_provenance":
            continue
        payload = block.get("payload")
        agent = payload.get("agent") if isinstance(payload, dict) else None
        if not isinstance(agent, dict):
            continue
        entry: dict[str, Any] = {}
        if agent.get("name"):
            entry["name"] = str(agent["name"])
        if agent.get("model"):
            entry["model"] = str(agent["model"])
        prompt_hash = agent.get("prompt_sha256")
        if prompt_hash:
            entry["prompt_sha256_prefix"] = str(prompt_hash)[:12]
        agents.append(entry)
    return {"present": bool(agents), "count": len(agents), "agents": agents}


def _in_toto_section(in_toto: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(in_toto, dict):
        return {"exported": False, "ref": None}
    exported = bool(in_toto.get("exported"))
    ref = in_toto.get("ref")
    return {"exported": exported, "ref": str(ref) if exported and ref else None}


def _build_tool_section(proof: dict[str, Any]) -> dict[str, Any]:
    build_tool = (proof.get("summary") or {}).get("build_tool") or {}
    versions = build_tool.get("versions")
    return {
        "tool": str(build_tool.get("tool") or "bazel"),
        "versions": [str(v) for v in versions] if isinstance(versions, list) else [],
        "recorded": bool(build_tool.get("recorded")),
    }


def _block_by_id(proof: dict[str, Any], block_id: str) -> dict[str, Any] | None:
    for block in proof.get("blocks") or []:
        if block.get("id") == block_id:
            return block
    return None


# --------------------------------------------------------------------------- #
# Markdown rendering (compact) — reads the already-redacted summary
# --------------------------------------------------------------------------- #


def render_pr_comment_markdown(
    summary: dict[str, Any],
    *,
    config: RedactionConfig | None = None,
) -> str:
    """Render the compact PR-comment markdown from a summary dict.

    ``summary`` is expected to be the output of :func:`build_pr_comment_summary`
    (already redacted). The rendered markdown is routed through
    :func:`nlfr.redaction.redact_text` as a belt-and-suspenders pass so a
    ``nlfr redact --check`` over the file is clean regardless of the summary's
    provenance.
    """

    label_line = " · ".join(
        f"`{summary.get(key, 'unknown')}`"
        for key in ("source_kind", "confidence", "redaction_state")
    )

    lines: list[str] = [
        "## NLFR Proof Summary",
        "",
        (
            f"**Run group:** `{summary.get('run_group', 'unknown')}` · "
            f"**Generated:** {summary.get('generated_at', 'unknown')} · "
            f"**Export labels:** {label_line}"
        ),
        "",
        *_render_status_line(summary),
        "",
        *_render_cache_lines(summary),
        "",
        *_render_artifact_lines(summary),
        "",
        *_render_agent_lines(summary),
        "",
        *_render_in_toto_line(summary),
        "",
        *_render_build_tool_line(summary),
        "",
        (
            "> Recorded evidence only. This summary makes no claim about remote "
            "worker identity, action placement, or queue timing; remote-only "
            "references stay unverified unless an independent CAS probe recorded a "
            "verdict. No cost or cross-machine cache figures are asserted."
        ),
        "",
        (
            "_Compact projection — full per-block detail via "
            "`nlfr proof export --format markdown`. No raw prompts, private logs, "
            "or absolute paths (routed through `nlfr redact`)._"
        ),
    ]
    text = "\n".join(lines).rstrip() + "\n"
    return redact_text(text, config or RedactionConfig()).payload  # type: ignore[return-value]


def _render_status_line(summary: dict[str, Any]) -> list[str]:
    status = summary.get("status") or {}
    state = status.get("status", "unknown")
    failures = int(status.get("failures") or 0)
    marker = "FAILED" if state == "failed" else "ok"
    return [f"**Status:** {marker} — {failures} validation failure(s)"]


def _render_cache_lines(summary: dict[str, Any]) -> list[str]:
    cache = summary.get("cache") or {}
    lines = [
        (
            f"**Cache economics:** {int(cache.get('hits') or 0)} hit · "
            f"{int(cache.get('misses') or 0)} miss · "
            f"hit_rate {_fmt_rate(cache.get('hit_rate'))} · "
            f"{int(cache.get('cache_events') or 0)} cache event(s)"
        )
    ]
    cold_warm = cache.get("cold_warm")
    if isinstance(cold_warm, dict):
        notes = []
        if cold_warm.get("warm_hit_rate_higher"):
            notes.append("warm hit_rate higher")
        if cold_warm.get("warm_duration_lower"):
            notes.append("warm duration lower")
        if not notes:
            notes.append("no collectable warm-over-cold improvement")
        lines.append(
            f"- cold/warm: hit_rate Δ {_fmt_delta(cold_warm.get('hit_rate_delta'))} · "
            f"duration Δ {_fmt_delta(cold_warm.get('duration_delta_seconds'), unit='s')} "
            f"({'; '.join(notes)})"
        )
    return lines


def _render_artifact_lines(summary: dict[str, Any]) -> list[str]:
    av = summary.get("artifact_verification") or {}
    local = av.get("local") or {}
    remote = av.get("remote") or {}
    total = int(av.get("total") or 0)
    unverified_remote = int(av.get("unverified_remote") or 0)
    local_str = " · ".join(f"{int(local.get(label) or 0)} {label}" for _f, label in _LOCAL_FIELDS)
    remote_str = " · ".join(
        f"{int(remote.get(label) or 0)} {label}" for _f, label in _REMOTE_FIELDS
    )
    return [
        f"**Artifact integrity verification** ({total} reference(s)):",
        f"- local: {local_str}",
        f"- remote (CAS): {remote_str} · {unverified_remote} unverified (no probe)",
    ]


def _render_agent_lines(summary: dict[str, Any]) -> list[str]:
    agent = summary.get("agent_receipt") or {}
    if not agent.get("present"):
        return [
            "**Agent receipt provenance:** absent — no agent-invocation receipt "
            "recorded for this run group"
        ]
    count = int(agent.get("count") or 0)
    entries = agent.get("agents") or []
    detail_parts: list[str] = []
    for entry in entries:
        piece = []
        if entry.get("model"):
            piece.append(f"model `{entry['model']}`")
        if entry.get("prompt_sha256_prefix"):
            piece.append(f"prompt_sha256 `{entry['prompt_sha256_prefix']}…`")
        if piece:
            detail_parts.append(", ".join(piece))
    detail = f" — {'; '.join(detail_parts)}" if detail_parts else ""
    return [
        f"**Agent receipt provenance:** present — {count} receipt(s){detail} (hash-only; "
        "raw prompt never exported)"
    ]


def _render_in_toto_line(summary: dict[str, Any]) -> list[str]:
    in_toto = summary.get("in_toto") or {}
    if not in_toto.get("exported"):
        return ["**in-toto attestation:** not exported for this run group"]
    ref = in_toto.get("ref")
    ref_str = f" · ref `{ref}`" if ref else ""
    return [f"**in-toto attestation:** exported{ref_str}"]


def _render_build_tool_line(summary: dict[str, Any]) -> list[str]:
    build_tool = summary.get("build_tool") or {}
    tool = build_tool.get("tool", "bazel")
    versions = build_tool.get("versions") or []
    if build_tool.get("recorded") and versions:
        return [f"**Build tool:** {tool} {', '.join(versions)}"]
    return [f"**Build tool:** {tool} · version not recorded in BEP"]


def _fmt_rate(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "n/a"


def _fmt_delta(value: Any, *, unit: str = "") -> str:
    if value is None:
        return "n/a"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "n/a"
    return f"{number:+.2f}{unit}"
