"""Contract tests for Action Graph canvas node cap (mirrors apps/canvas/src/pageModel.ts)."""

from __future__ import annotations

DEFAULT_MAX_VISIBLE_GRAPH_NODES = 8

WORKER_GRAPH_KINDS = frozenset({"worker", "worker_readiness", "remote_execution_config"})
CACHE_GRAPH_KINDS = frozenset({"cache_event"})


def graph_node_render_priority(kind: str) -> int:
    if kind == "failure":
        return 0
    if kind in WORKER_GRAPH_KINDS:
        return 1
    if kind in CACHE_GRAPH_KINDS:
        return 2
    return 3


def cap_visible_graph_nodes(
    nodes: list[dict[str, str]],
    max_visible: int = DEFAULT_MAX_VISIBLE_GRAPH_NODES,
    ensure_ids: list[str] | None = None,
) -> dict[str, object]:
    ensure_ids = ensure_ids or []
    if len(nodes) <= max_visible:
        return {"visible": nodes, "hidden_count": 0, "overflow": 0}

    by_id = {node["id"]: node for node in nodes}
    sorted_nodes = sorted(
        nodes,
        key=lambda node: (graph_node_render_priority(node["kind"]), node["id"]),
    )

    visible: list[dict[str, str]] = []
    visible_ids: set[str] = set()

    def push_visible(node: dict[str, str] | None) -> None:
        if node is None or node["id"] in visible_ids:
            return
        visible.append(node)
        visible_ids.add(node["id"])

    for node_id in ensure_ids:
        push_visible(by_id.get(node_id))

    for node in sorted_nodes:
        if len(visible) >= max_visible:
            break
        push_visible(node)

    hidden_count = len(nodes) - len(visible)
    return {"visible": visible, "hidden_count": hidden_count, "overflow": hidden_count}


def test_graph_node_render_priority_order() -> None:
    assert graph_node_render_priority("failure") < graph_node_render_priority("worker")
    assert graph_node_render_priority("worker") < graph_node_render_priority("cache_event")
    assert graph_node_render_priority("cache_event") < graph_node_render_priority("target")


def test_cap_visible_graph_nodes_returns_all_when_under_limit() -> None:
    nodes = [
        {"id": "run-1", "kind": "run"},
        {"id": "target-1", "kind": "target"},
    ]
    result = cap_visible_graph_nodes(nodes)
    assert result["overflow"] == 0
    assert [node["id"] for node in result["visible"]] == ["run-1", "target-1"]


def test_cap_visible_graph_nodes_prioritizes_failures_workers_cache() -> None:
    nodes = [
        {"id": "artifact-1", "kind": "artifact"},
        {"id": "cache-1", "kind": "cache_event"},
        {"id": "worker-1", "kind": "worker"},
        {"id": "failure-1", "kind": "failure"},
        {"id": "target-9", "kind": "target"},
        {"id": "target-8", "kind": "target"},
        {"id": "target-7", "kind": "target"},
        {"id": "target-6", "kind": "target"},
        {"id": "target-5", "kind": "target"},
        {"id": "target-4", "kind": "target"},
    ]
    result = cap_visible_graph_nodes(nodes)
    visible_kinds = [node["kind"] for node in result["visible"]]
    assert result["overflow"] == 2
    assert len(result["visible"]) == 8
    assert visible_kinds[0] == "failure"
    assert "worker" in visible_kinds
    assert "cache_event" in visible_kinds
    assert visible_kinds.count("target") == 4


def test_cap_visible_graph_nodes_ensures_selected_id() -> None:
    nodes = [{"id": f"target-{index}", "kind": "target"} for index in range(12)]
    nodes.append({"id": "failure-hidden", "kind": "failure"})
    result = cap_visible_graph_nodes(nodes, ensure_ids=["target-11"])
    visible_ids = {node["id"] for node in result["visible"]}
    assert "target-11" in visible_ids
    assert len(visible_ids) == 8


def test_action_graph_summary_exports_max_visible_nodes_hint(tmp_path) -> None:
    from nlfr.projectors import export_action_graph

    from test_projectors import seed_projection_db

    graph = export_action_graph(seed_projection_db(tmp_path), run_group="latest")
    assert graph["summary"]["nodes"] > 0
    assert graph["summary"]["max_visible_nodes"] == 8
    assert len(graph["nodes"]) == graph["summary"]["nodes"]
