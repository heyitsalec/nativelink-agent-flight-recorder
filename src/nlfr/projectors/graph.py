"""Action Graph projection."""

from __future__ import annotations

from sqlite3 import Connection
from typing import Any

from nlfr.projectors.common import generated_at, rows, run_rows, status_counts, truth
from nlfr.projectors.remote_execution import (
    remote_execution_invocations,
    sanitize_remote_endpoint_args,
    unsupported_claims_for_run,
    worker_identity_events_for_run,
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
    changes = rows(conn, "changes", run_ids)
    proof_blocks = rows(conn, "proof_blocks", run_ids)
    explicit_nodes = rows(conn, "graph_nodes", run_ids)
    explicit_edges = rows(conn, "graph_edges", run_ids)

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    for run in runs:
        nodes.append(_node(run["id"], "run", run.get("scenario") or run["stable_key"], run))

    agent_node_by_run = _project_agents(proof_blocks, nodes)
    for item in changes:
        nodes.append(_node(item["id"], "change", item.get("path") or item["id"], item))
        agent_node_id = agent_node_by_run.get(item["run_id"])
        if agent_node_id:
            edges.append(_edge(agent_node_id, item["id"], "authored_change", item))
        edges.append(_edge(item["id"], item["run_id"], "validated_by", item))
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
        run_id = str(invocation.get("run_id") or "")
        worker_events = worker_identity_events_for_run(run_id, proof_blocks)
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
            "worker_identity_observed": bool(worker_events),
            "unsupported_claims": unsupported_claims_for_run(run_id, proof_blocks),
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
        for event in worker_events:
            worker_name = str(event["worker_name"])
            worker_id = f"worker:{invocation['id']}:{worker_name}"
            worker_row = {
                "status": "observed",
                "source_kind": "collectable_v1",
                "confidence": "high",
                "evidence_refs": [str(event.get("evidence_ref") or "")],
                "redaction_state": invocation.get("redaction_state") or "safe",
                "worker_name": worker_name,
                "line_number": event.get("line_number"),
            }
            nodes.append(_node(worker_id, "worker", worker_name, worker_row))
            edges.append(
                _edge(
                    config_id,
                    worker_id,
                    "observed_worker_identity",
                    worker_row,
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
            "changes": len(changes),
            "agents": len(agent_node_by_run),
        },
        "nodes": nodes,
        "edges": edges,
    }


def _project_agents(
    proof_blocks: list[dict[str, Any]],
    nodes: list[dict[str, Any]],
) -> dict[str, str]:
    """Derive agent nodes from recorded agent_provenance proof blocks.

    Returns a mapping of run_id -> agent node id so changes recorded under the
    same run can be linked with an authored_change edge.
    """

    agent_node_by_run: dict[str, str] = {}
    for block in proof_blocks:
        if block.get("block_kind") != "agent_provenance":
            continue
        payload = block.get("payload") if isinstance(block.get("payload"), dict) else {}
        agent = payload.get("agent") if isinstance(payload.get("agent"), dict) else {}
        change = payload.get("change") if isinstance(payload.get("change"), dict) else {}
        build = payload.get("build") if isinstance(payload.get("build"), dict) else {}
        agent_name = str(agent.get("name") or block.get("block_key") or "agent")
        agent_node_id = f"agent:{block['id']}"
        # Carry only redacted, hash-level provenance into the node payload.
        # Never surface raw prompts: only the prompt hash and model label.
        agent_row = {
            "status": build.get("status"),
            "source_kind": block.get("source_kind"),
            "confidence": block.get("confidence"),
            "evidence_refs": block.get("evidence_refs"),
            "redaction_state": block.get("redaction_state"),
            "agent_kind": agent.get("kind"),
            "agent_name": agent_name,
            "model": agent.get("model"),
            "prompt_sha256": agent.get("prompt_sha256"),
            "input_signal": agent.get("input_signal"),
            "change_class": change.get("change_class"),
            "patch_sha256": change.get("patch_sha256"),
            "scenario_id": payload.get("scenario_id"),
        }
        nodes.append(_node(agent_node_id, "agent", agent_name, agent_row))
        run_id = block.get("run_id")
        if run_id is not None:
            agent_node_by_run[run_id] = agent_node_id
    return agent_node_by_run


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
