"""Multi-run compare projection from proof packet summaries."""

from __future__ import annotations

from sqlite3 import Connection
from typing import Any

from nlfr.projectors.common import (
    available_run_groups,
    generated_at,
    row_to_dict,
    run_rows,
    status_counts,
    truth,
)
from nlfr.projectors.proof import export_proof_packet
from nlfr.retention_policy import retention_policy_summary


class MissingRunGroupError(ValueError):
    """A compare side names a run group that has no recorded runs in its database.

    A compare over an empty side is schema-valid and fully truth-labeled, yet it
    compares real data against zero — the same silent-fabrication trap that a
    wrong ``--db`` triggers, arriving through the ``--left``/``--right`` door
    instead (GitHub #47). Rather than emit that confident zero-value delta, the
    exporter raises this hard error whose message names WHICH side is empty, the
    empty run group, and the run groups that ARE present in that database — so
    the failure becomes recovery guidance. Mirrors the in-toto ``EmptySubjectError``
    UX (GitHub #26 / PR #46). Note ``compare index``/``history`` do NOT raise this:
    an empty listing over an existing database is a legitimate, honest report.
    """

    def __init__(
        self, side: str, run_group: str, available: list[dict[str, Any]]
    ) -> None:
        self.side = side
        self.run_group = run_group
        self.available = available
        super().__init__(self._render())

    def _render(self) -> str:
        lines = [
            f"nlfr: {self.side} run group '{self.run_group}' has no recorded runs "
            "in its database — refusing to emit a compare against nothing.",
            "A compare with an empty side is schema-valid and fully truth-labeled, "
            "yet it compares real data against zero — so this is a hard error, not "
            "a silent zero-value result.",
        ]
        if self.available:
            lines.append("Run groups present in that database:")
            lines.extend(
                f"  - {item['run_group']} ({item['run_count']} run(s))"
                for item in self.available
            )
            lines.append(
                "Re-run with one of the above (literal match — there is no "
                "'latest' resolver)."
            )
        else:
            lines.append(
                "No run groups are recorded in that database. Record a build first "
                "(e.g. `nlfr record -- bazel test //...`), or point the --db / "
                "--left-db / --right-db at data/nlfr-record/<run-group>/nlfr.sqlite."
            )
        lines.append("List run groups any time with: `nlfr compare index --db <db>`.")
        return "\n".join(lines)


def require_run_group(conn: Connection, side: str, run_group: str) -> None:
    """Raise :class:`MissingRunGroupError` if ``run_group`` has no runs in ``conn``.

    ``side`` is ``"left"`` or ``"right"`` and is echoed in the error so a
    cross-DB compare names exactly which database is missing the group.
    """

    if run_rows(conn, run_group):
        return
    raise MissingRunGroupError(side, run_group, available_run_groups(conn))


def export_compare_projection(
    conn: Connection,
    left_run_group: str,
    right_run_group: str,
) -> dict[str, Any]:
    """Build a compare projection from two run groups in one database."""

    left_proof = export_proof_packet(conn, run_group=left_run_group)
    right_proof = export_proof_packet(conn, run_group=right_run_group)
    left_runs = run_rows(conn, left_run_group)
    right_runs = run_rows(conn, right_run_group)
    return build_compare_projection(
        left_proof,
        right_proof,
        left_run_group,
        right_run_group,
        left_runs=left_runs,
        right_runs=right_runs,
    )


def build_compare_projection(
    left_proof: dict[str, Any],
    right_proof: dict[str, Any],
    left_run_group: str,
    right_run_group: str,
    *,
    left_runs: list[dict[str, Any]],
    right_runs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Assemble compare dimensions from preloaded proof packets and run rows."""

    left_refs = [f"run_group:{left_run_group}"]
    right_refs = [f"run_group:{right_run_group}"]
    evidence_refs = [*left_refs, *right_refs]

    dimensions = [
        _run_counts_dimension(left_proof, right_proof, left_refs, right_refs),
        _cache_metrics_dimension(left_proof, right_proof, left_refs, right_refs),
        _worker_identity_dimension(left_proof, right_proof, left_refs, right_refs),
        _agent_provenance_dimension(left_proof, right_proof, left_refs, right_refs),
        _status_delta_dimension(left_runs, right_runs, left_refs, right_refs),
    ]

    return {
        "schema_version": 1,
        "projection_kind": "compare",
        "generated_at": generated_at(),
        "left_run_group": left_run_group,
        "right_run_group": right_run_group,
        "summary": {
            "dimensions": len(dimensions),
            "left_runs": len(left_runs),
            "right_runs": len(right_runs),
            "left_artifacts": left_proof.get("summary", {}).get("artifacts", 0),
            "right_artifacts": right_proof.get("summary", {}).get("artifacts", 0),
        },
        "dimensions": dimensions,
        "source_kind": "derived_v1",
        "confidence": "medium",
        "evidence_refs": evidence_refs,
        "redaction_state": "safe",
    }


def export_history_projection(
    conn: Connection,
    *,
    limit: int | None = None,
) -> dict[str, Any]:
    """Build a multi-run history projection from the retention index."""

    index = list_run_group_index(conn)
    return build_history_projection(conn, index, limit=limit)


def build_history_projection(
    conn: Connection,
    index_rows: list[dict[str, Any]],
    *,
    limit: int | None = None,
) -> dict[str, Any]:
    """Assemble multi-run history from preloaded index rows."""

    total = len(index_rows)
    rows = index_rows[:limit] if limit is not None else index_rows
    entries = [_history_run_group_entry(conn, row) for row in rows]
    evidence_refs = [f"run_group:{item['run_group']}" for item in entries]
    evidence_refs.append("projection:run-history")
    total_runs = sum(int(item.get("run_count") or 0) for item in entries)

    summary: dict[str, Any] = {
        "run_groups": len(entries),
        "total_runs": total_runs,
    }
    if limit is not None:
        summary["limit"] = limit
        summary["total_indexed"] = total

    claims = [
        "Run history is derived from the retention index and proof packet summaries only.",
        f"Indexed {len(entries)} run group(s) with {total_runs} total run(s).",
        "This projection does not claim scheduler assignment, queue time, or fleet trends.",
    ]
    if limit is not None and total > limit:
        claims.append(
            f"History export is limited to the newest {limit} of {total} indexed run group(s)."
        )

    return {
        "schema_version": 1,
        "projection_kind": "run_history",
        "generated_at": generated_at(),
        "retention_policy": retention_policy_summary(),
        "summary": summary,
        "claims": claims,
        "run_groups": entries,
        "source_kind": "derived_v1",
        "confidence": "medium",
        "evidence_refs": evidence_refs,
        "redaction_state": "safe",
    }


def list_run_group_index(conn: Connection) -> list[dict[str, Any]]:
    """Return run-group retention index rows from SQLite."""

    rows = conn.execute(
        """
        SELECT
            run_group,
            COUNT(*) AS run_count,
            MIN(started_at) AS first_started_at,
            MAX(started_at) AS last_started_at
        FROM runs
        GROUP BY run_group
        ORDER BY last_started_at DESC, run_group ASC
        """
    ).fetchall()
    return [
        {
            "run_group": item["run_group"],
            "run_count": item["run_count"],
            "first_started_at": item["first_started_at"],
            "last_started_at": item["last_started_at"],
        }
        for item in (row_to_dict(row) for row in rows)
    ]


def _history_run_group_entry(
    conn: Connection,
    index_row: dict[str, Any],
) -> dict[str, Any]:
    run_group = str(index_row["run_group"])
    proof = export_proof_packet(conn, run_group=run_group)
    runs = run_rows(conn, run_group)
    proof_summary = proof.get("summary") if isinstance(proof.get("summary"), dict) else {}
    latest_run = runs[-1] if runs else {}
    agent_blocks = _agent_provenance_blocks(proof)

    return {
        "run_group": run_group,
        "run_count": index_row.get("run_count"),
        "first_started_at": index_row.get("first_started_at"),
        "last_started_at": index_row.get("last_started_at"),
        "scenario": latest_run.get("scenario"),
        "mode": latest_run.get("mode"),
        "status_counts": status_counts(runs),
        "proof_summary": {
            "runs": int(proof_summary.get("runs") or 0),
            "artifacts": int(proof_summary.get("artifacts") or 0),
            "targets": int(proof_summary.get("targets") or 0),
            "actions": int(proof_summary.get("actions") or 0),
            "cache_events": int(proof_summary.get("cache_events") or 0),
            "failures": int(proof_summary.get("failures") or 0),
        },
        "cache_metrics": _block_metrics(proof, "cache"),
        "worker_identity_observed": _worker_identity_observed(proof),
        "agent_provenance_present": len(agent_blocks) > 0,
        "agent_provenance_block_count": len(agent_blocks),
        "source_kind": "derived_v1",
        "confidence": "medium",
        "evidence_refs": [f"run_group:{run_group}"],
        "redaction_state": "safe",
    }


def _derived_dimension(
    dimension_id: str,
    title: str,
    summary: str,
    *,
    left: dict[str, Any],
    right: dict[str, Any],
    delta: dict[str, Any],
    claims: list[str],
    evidence_refs: list[str],
    confidence: str = "medium",
) -> dict[str, Any]:
    return {
        "id": dimension_id,
        "title": title,
        "summary": summary,
        "left": left,
        "right": right,
        "delta": delta,
        "claims": claims,
        "source_kind": "derived_v1",
        "confidence": confidence,
        "evidence_refs": evidence_refs,
        "redaction_state": "safe",
    }


def _run_counts_dimension(
    left_proof: dict[str, Any],
    right_proof: dict[str, Any],
    left_refs: list[str],
    right_refs: list[str],
) -> dict[str, Any]:
    left_runs = int(left_proof.get("summary", {}).get("runs") or 0)
    right_runs = int(right_proof.get("summary", {}).get("runs") or 0)
    delta_runs = right_runs - left_runs
    claims = [
        f"Left run group recorded {left_runs} run(s).",
        f"Right run group recorded {right_runs} run(s).",
    ]
    if delta_runs:
        claims.append(f"Run count delta is {delta_runs:+d}.")
    else:
        claims.append("Run counts match between run groups.")
    return _derived_dimension(
        "run_counts",
        "Run Counts",
        "Recorded run counts from proof packet summaries.",
        left={"runs": left_runs, "run_group": left_proof.get("run_group")},
        right={"runs": right_runs, "run_group": right_proof.get("run_group")},
        delta={"runs": delta_runs},
        claims=claims,
        evidence_refs=[*left_refs, *right_refs],
    )


def _cache_metrics_dimension(
    left_proof: dict[str, Any],
    right_proof: dict[str, Any],
    left_refs: list[str],
    right_refs: list[str],
) -> dict[str, Any]:
    left_metrics = _block_metrics(left_proof, "cache")
    right_metrics = _block_metrics(right_proof, "cache")
    left_hits = int(left_metrics.get("hits") or 0)
    right_hits = int(right_metrics.get("hits") or 0)
    left_misses = int(left_metrics.get("misses") or 0)
    right_misses = int(right_metrics.get("misses") or 0)
    left_rate = left_metrics.get("hit_rate")
    right_rate = right_metrics.get("hit_rate")
    claims = [
        "Cache metrics are derived from proof packet cache blocks only.",
        f"Left: {left_hits} hit(s), {left_misses} miss(es).",
        f"Right: {right_hits} hit(s), {right_misses} miss(es).",
    ]
    if left_rate is not None and right_rate is not None:
        rate_delta = right_rate - left_rate
        claims.append(f"Hit rate delta is {rate_delta:+.2%}.")
    return _derived_dimension(
        "cache_metrics",
        "Cache Metrics",
        "Cache hit/miss counts and hit rates from recorded Bazel evidence.",
        left={"metrics": left_metrics},
        right={"metrics": right_metrics},
        delta={
            "hits": right_hits - left_hits,
            "misses": right_misses - left_misses,
            "hit_rate": (
                (right_rate - left_rate)
                if left_rate is not None and right_rate is not None
                else None
            ),
        },
        claims=claims,
        evidence_refs=[*left_refs, *right_refs],
    )


def _worker_identity_dimension(
    left_proof: dict[str, Any],
    right_proof: dict[str, Any],
    left_refs: list[str],
    right_refs: list[str],
) -> dict[str, Any]:
    left_observed = _worker_identity_observed(left_proof)
    right_observed = _worker_identity_observed(right_proof)
    claims = [
        "Worker identity is true only when direct worker admin evidence exists in the proof packet.",
        f"Left worker identity observed: {left_observed}.",
        f"Right worker identity observed: {right_observed}.",
    ]
    if left_observed != right_observed:
        claims.append("Worker identity observation differs between run groups.")
    else:
        claims.append("Worker identity observation matches between run groups.")
    return _derived_dimension(
        "worker_identity",
        "Worker Identity",
        "Whether direct worker identity evidence was observed in each proof packet.",
        left={"worker_identity_observed": left_observed},
        right={"worker_identity_observed": right_observed},
        delta={"worker_identity_observed_changed": left_observed != right_observed},
        claims=claims,
        evidence_refs=[*left_refs, *right_refs],
        confidence="high" if left_observed or right_observed else "medium",
    )


def _agent_provenance_dimension(
    left_proof: dict[str, Any],
    right_proof: dict[str, Any],
    left_refs: list[str],
    right_refs: list[str],
) -> dict[str, Any]:
    left_blocks = _agent_provenance_blocks(left_proof)
    right_blocks = _agent_provenance_blocks(right_proof)
    left_present = len(left_blocks) > 0
    right_present = len(right_blocks) > 0
    claims = [
        "Agent provenance presence is derived from agent_provenance proof blocks.",
        f"Left agent provenance block(s): {len(left_blocks)}.",
        f"Right agent provenance block(s): {len(right_blocks)}.",
    ]
    if left_present != right_present:
        claims.append("Agent provenance presence differs between run groups.")
    return _derived_dimension(
        "agent_provenance",
        "Agent Provenance",
        "Presence of bounded agent provenance blocks (model + prompt hash only).",
        left={
            "present": left_present,
            "block_count": len(left_blocks),
            "blocks": [_agent_provenance_summary(block) for block in left_blocks],
        },
        right={
            "present": right_present,
            "block_count": len(right_blocks),
            "blocks": [_agent_provenance_summary(block) for block in right_blocks],
        },
        delta={
            "present_changed": left_present != right_present,
            "block_count_delta": len(right_blocks) - len(left_blocks),
        },
        claims=claims,
        evidence_refs=[*left_refs, *right_refs],
    )


def _status_delta_dimension(
    left_runs: list[dict[str, Any]],
    right_runs: list[dict[str, Any]],
    left_refs: list[str],
    right_refs: list[str],
) -> dict[str, Any]:
    left_statuses = status_counts(left_runs)
    right_statuses = status_counts(right_runs)
    all_statuses = sorted(set(left_statuses) | set(right_statuses))
    per_status: dict[str, dict[str, int]] = {}
    for status in all_statuses:
        per_status[status] = {
            "left": left_statuses.get(status, 0),
            "right": right_statuses.get(status, 0),
            "delta": right_statuses.get(status, 0) - left_statuses.get(status, 0),
        }
    claims = [
        "Status deltas are derived from recorded run rows in SQLite.",
        f"Left statuses: {left_statuses or 'none'}.",
        f"Right statuses: {right_statuses or 'none'}.",
    ]
    changed = any(item["delta"] != 0 for item in per_status.values())
    if changed:
        claims.append("At least one run status count differs between run groups.")
    else:
        claims.append("Run status counts match between run groups.")
    return _derived_dimension(
        "status_deltas",
        "Status Deltas",
        "Per-status run counts compared between run groups.",
        left={"status_counts": left_statuses},
        right={"status_counts": right_statuses},
        delta={"by_status": per_status, "changed": changed},
        claims=claims,
        evidence_refs=[*left_refs, *right_refs],
    )


def _block_metrics(proof: dict[str, Any], block_id: str) -> dict[str, Any]:
    block = _proof_block(proof, block_id)
    metrics = block.get("metrics") if block else None
    return dict(metrics) if isinstance(metrics, dict) else {}


def _proof_block(proof: dict[str, Any], block_id: str) -> dict[str, Any] | None:
    for block in proof.get("blocks") or []:
        if block.get("id") == block_id:
            return block
    return None


def _worker_identity_observed(proof: dict[str, Any]) -> bool:
    block = _proof_block(proof, "remote_execution")
    if not block:
        return False
    metrics = block.get("metrics") or {}
    return bool(metrics.get("worker_identity_observed"))


def _agent_provenance_blocks(proof: dict[str, Any]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for block in proof.get("blocks") or []:
        kind = block.get("kind") or block.get("block_kind")
        if kind == "agent_provenance":
            blocks.append(block)
            continue
        if str(block.get("title") or "").startswith("Agent Provenance"):
            blocks.append(block)
    return blocks


def _agent_provenance_summary(block: dict[str, Any]) -> dict[str, Any]:
    payload = block.get("payload") if isinstance(block.get("payload"), dict) else {}
    agent = payload.get("agent") if isinstance(payload.get("agent"), dict) else {}
    receipt = agent.get("receipt") if isinstance(agent.get("receipt"), dict) else {}
    labels = truth(block)
    return {
        "id": block.get("id"),
        "title": block.get("title"),
        "model": agent.get("model"),
        "prompt_sha256_prefix": _hash_prefix(agent.get("prompt_sha256")),
        "provenance_class": agent.get("provenance_class"),
        "receipt_verified": bool(receipt.get("live")),
        "receipt_session_id": receipt.get("session_id"),
        **labels,
    }


def _hash_prefix(value: Any) -> str | None:
    if not value or not isinstance(value, str):
        return None
    return value[:12] if len(value) >= 12 else value
