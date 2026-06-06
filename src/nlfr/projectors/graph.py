"""Action Graph projection."""

from __future__ import annotations

from sqlite3 import Connection
from typing import Any

from nlfr.projectors.common import generated_at, rows, run_rows, status_counts, truth
from nlfr.projectors.remote_execution import (
    UNSUPPORTED_REMOTE_EXECUTION_CLAIMS,
    remote_execution_invocations,
    sanitize_remote_endpoint_args,
)


def export_action_graph(conn: Connection, *, run_group: str) -> dict[str, Any]:
    runs = run_rows(conn, run_group)
    run_ids = [run["id"] for run in runs]
    invocations = rows(conn, "invocations", run_ids)
    artifacts = rows(conn, "artifacts", run_ids)
    targets = rows(conn, "targets", run_ids)
    actions = rows(conn, "actions", run_ids)
    cache_events = rows(conn, "cache_events", run_ids)
    failures = rows(conn, "failures", run_ids)
    explicit_nodes = rows(conn, "graph_nodes", run_ids)
    explicit_edges = rows(conn, "graph_edges", run_ids)

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    for run in runs:
        nodes.append(_node(run["id"], "run", run.get("scenario") or run["stable_key"], run))
    for item in invocations:
        nodes.append(
            _node(
                item["id"],
                "invocation",
                item.get("invocation_kind") or item["stable_key"],
                item,
                status=item.get("exit_code") if item.get("status") is None else item.get("status"),
            )
        )
        edges.append(_edge(item["run_id"], item["id"], "recorded_invocation", item))
    for item in remote_execution_invocations(invocations):
        invocation = item["invocation"]
        config_id = f"remote_execution_config:{invocation['id']}"
        config_row = {
            "status": "configured",
            "source_kind": "derived_v1",
            "confidence": "high",
            "evidence_refs": item["evidence_refs"],
            "redaction_state": invocation.get("redaction_state") or "unknown",
            "endpoint_label": item["endpoint_label"],
            "endpoint_fingerprint": item["endpoint_fingerprint"],
            "endpoint_redacted": item["endpoint_redacted"],
            "remote_executor_arg_present": True,
            "remote_executor_arg_count": item["remote_executor_arg_count"],
            "configured_only": True,
            "unsupported_claims": list(UNSUPPORTED_REMOTE_EXECUTION_CLAIMS),
        }
        nodes.append(
            _node(config_id, "remote_execution_config", item["endpoint_label"], config_row)
        )
        edges.append(
            _edge(
                invocation["id"],
                config_id,
                "configured_remote_execution",
                config_row,
            )
        )
    for item in artifacts:
        nodes.append(_node(item["id"], "artifact", item.get("artifact_key") or item["id"], item))
        edges.append(_edge(item["run_id"], item["id"], "recorded_artifact", item))
    for item in targets:
        nodes.append(_node(item["id"], "target", item.get("label") or item["id"], item))
        edges.append(_edge(item["run_id"], item["id"], "evaluated_target", item))
    for item in actions:
        nodes.append(_node(item["id"], "action", item.get("mnemonic") or item["action_key"], item))
        parent = item.get("target_id") or item["run_id"]
        edges.append(_edge(parent, item["id"], "produced_action", item))
    for item in cache_events:
        label = item.get("event_kind") or item.get("digest") or item["id"]
        nodes.append(_node(item["id"], "cache_event", label, item))
        parent = item.get("action_id") or item.get("target_id") or item["run_id"]
        edges.append(_edge(parent, item["id"], "observed_cache_event", item))
    for item in failures:
        nodes.append(_node(item["id"], "failure", item.get("failure_kind") or "failure", item))
        edges.append(_edge(item["run_id"], item["id"], "observed_failure", item))

    for item in explicit_nodes:
        nodes.append(
            _node(
                item["id"],
                item.get("node_kind") or "graph_node",
                item.get("label") or item.get("node_key") or item["id"],
                item,
            )
        )
    for item in explicit_edges:
        edges.append(
            {
                "id": item["id"],
                "from": item.get("from_node_id") or item.get("from_node_key"),
                "to": item.get("to_node_id") or item.get("to_node_key"),
                "kind": item["edge_kind"],
                "payload": item.get("payload"),
                **truth(item),
            }
        )

    return {
        "schema_version": 1,
        "projection_kind": "action_graph",
        "generated_at": generated_at(),
        "run_group": run_group,
        "summary": {
            "runs": len(runs),
            "nodes": len(nodes),
            "edges": len(edges),
            "invocation_statuses": status_counts(invocations),
            "target_statuses": status_counts(targets),
            "cache_events": len(cache_events),
            "failures": len(failures),
        },
        "nodes": nodes,
        "edges": edges,
    }


def _node(
    node_id: str,
    node_kind: str,
    label: object,
    row: dict[str, Any],
    *,
    status: object | None = None,
) -> dict[str, Any]:
    return {
        "id": node_id,
        "kind": node_kind,
        "label": str(label),
        "status": status if status is not None else row.get("status"),
        "payload": _payload(row),
        **truth(row),
    }


def _edge(from_id: str, to_id: str, kind: str, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f"{kind}:{from_id}:{to_id}",
        "from": from_id,
        "to": to_id,
        "kind": kind,
        **truth(row),
    }


def _payload(row: dict[str, Any]) -> dict[str, Any]:
    excluded = {
        "id",
        "stable_key",
        "source_kind",
        "confidence",
        "evidence_refs",
        "redaction_state",
        "created_at",
        "updated_at",
    }
    payload = {
        key: value for key, value in row.items() if key not in excluded and value is not None
    }
    if "command" in payload:
        payload["command"] = sanitize_remote_endpoint_args(payload["command"])
    return payload
