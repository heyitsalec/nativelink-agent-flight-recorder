import json
import os
import subprocess
import sys
from pathlib import Path

from nlfr.db import connect, initialize
from nlfr.db.ingest import upsert_cache_event, upsert_proof_block, upsert_run, upsert_target
from nlfr.projectors.compare import export_history_projection, list_run_group_index

ROOT = Path(__file__).resolve().parents[1]


def run_nlfr(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "nlfr", *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _seed_group(
    conn,
    *,
    run_group: str,
    scenario: str,
    status: str,
    cache_hits: int,
    cache_misses: int,
    agent_provenance: bool,
) -> None:
    run_id = upsert_run(
        conn,
        stable_key=f"run:{run_group}",
        run_group=run_group,
        scenario=scenario,
        mode="cache-only",
        status=status,
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=[f"run:{run_group}"],
        redaction_state="safe",
    )
    target_id = upsert_target(
        conn,
        stable_key=f"target:{run_group}",
        run_id=run_id,
        label="//tasks:priority_test",
        target_kind="py_test",
        status="passed",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["bep:target-completed"],
        redaction_state="safe",
    )
    for index in range(cache_hits):
        upsert_cache_event(
            conn,
            stable_key=f"cache:{run_group}:hit:{index}",
            run_id=run_id,
            target_id=target_id,
            event_key=f"hit-{index}",
            event_kind="action_cache",
            hit=True,
            source_kind="derived_v1",
            confidence="medium",
            evidence_refs=[f"execution-log:{run_group}"],
            redaction_state="safe",
        )
    for index in range(cache_misses):
        upsert_cache_event(
            conn,
            stable_key=f"cache:{run_group}:miss:{index}",
            run_id=run_id,
            target_id=target_id,
            event_key=f"miss-{index}",
            event_kind="action_cache",
            hit=False,
            source_kind="derived_v1",
            confidence="medium",
            evidence_refs=[f"execution-log:{run_group}"],
            redaction_state="safe",
        )
    if agent_provenance:
        upsert_proof_block(
            conn,
            stable_key=f"{run_group}:agent-provenance",
            run_id=run_id,
            block_key=f"agent-provenance:{scenario}",
            block_kind="agent_provenance",
            title="Agent Provenance: history-fixture-agent",
            summary="Bounded agent provenance recorded for history fixture.",
            payload={
                "scenario_id": scenario,
                "agent": {
                    "name": "history-fixture-agent",
                    "model": "composer-2.5",
                    "prompt_sha256": "b" * 64,
                },
            },
            source_kind="collectable_v1",
            confidence="high",
            evidence_refs=[f"agent-provenance:{run_group}"],
            redaction_state="safe",
        )


def test_history_projection_summarizes_indexed_groups(tmp_path) -> None:
    conn = initialize(connect(tmp_path / "nlfr.sqlite"))
    _seed_group(
        conn,
        run_group="older-group",
        scenario="cold-cache",
        status="completed",
        cache_hits=1,
        cache_misses=2,
        agent_provenance=False,
    )
    _seed_group(
        conn,
        run_group="newer-group",
        scenario="warm-cache",
        status="environment_blocker",
        cache_hits=3,
        cache_misses=0,
        agent_provenance=True,
    )

    history = export_history_projection(conn)

    assert history["projection_kind"] == "run_history"
    assert history["source_kind"] == "derived_v1"
    assert history["redaction_state"] == "safe"
    assert history["summary"]["run_groups"] == 2
    assert history["summary"]["total_runs"] == 2
    assert history["claims"]
    assert "projection:run-history" in history["evidence_refs"]
    assert history["retention_policy"]["discovery"] == "index_only"
    assert history["retention_policy"]["purge"] == "no_auto_purge"

    by_group = {item["run_group"]: item for item in history["run_groups"]}
    assert set(by_group) == {"older-group", "newer-group"}

    for entry in history["run_groups"]:
        assert entry["source_kind"] == "derived_v1"
        assert entry["evidence_refs"] == [f"run_group:{entry['run_group']}"]
        assert entry["redaction_state"] == "safe"
        assert "proof_summary" in entry
        assert "cache_metrics" in entry
        assert "status_counts" in entry

    assert by_group["older-group"]["status_counts"]["completed"] == 1
    assert by_group["newer-group"]["status_counts"]["environment_blocker"] == 1
    assert by_group["older-group"]["cache_metrics"]["hits"] == 1
    assert by_group["newer-group"]["cache_metrics"]["hits"] == 3
    assert by_group["older-group"]["agent_provenance_present"] is False
    assert by_group["newer-group"]["agent_provenance_present"] is True
    assert by_group["newer-group"]["scenario"] == "warm-cache"


def test_history_projection_respects_limit(tmp_path) -> None:
    conn = initialize(connect(tmp_path / "nlfr.sqlite"))
    for name in ("alpha", "beta", "gamma"):
        _seed_group(
            conn,
            run_group=name,
            scenario=name,
            status="completed",
            cache_hits=0,
            cache_misses=0,
            agent_provenance=False,
        )

    index = list_run_group_index(conn)
    history = export_history_projection(conn, limit=2)

    assert history["summary"]["run_groups"] == 2
    assert history["summary"]["limit"] == 2
    assert history["summary"]["total_indexed"] == 3
    assert len(history["run_groups"]) == 2
    assert history["run_groups"][0]["run_group"] == index[0]["run_group"]


def test_compare_history_cli_exports_json(tmp_path) -> None:
    db_path = tmp_path / "nlfr.sqlite"
    output_path = tmp_path / "run-history.json"
    conn = initialize(connect(db_path))
    _seed_group(
        conn,
        run_group="alpha",
        scenario="alpha",
        status="completed",
        cache_hits=0,
        cache_misses=0,
        agent_provenance=False,
    )
    _seed_group(
        conn,
        run_group="beta",
        scenario="beta",
        status="completed",
        cache_hits=0,
        cache_misses=0,
        agent_provenance=False,
    )

    result = run_nlfr(
        "compare",
        "history",
        "--db",
        str(db_path),
        "--output",
        str(output_path),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(output_path.read_text())
    assert payload["projection_kind"] == "run_history"
    assert payload["summary"]["run_groups"] == 2
    groups = {item["run_group"] for item in payload["run_groups"]}
    assert groups == {"alpha", "beta"}


def test_compare_history_cli_limit(tmp_path) -> None:
    db_path = tmp_path / "nlfr.sqlite"
    conn = initialize(connect(db_path))
    for name in ("alpha", "beta"):
        _seed_group(
            conn,
            run_group=name,
            scenario=name,
            status="completed",
            cache_hits=0,
            cache_misses=0,
            agent_provenance=False,
        )

    result = run_nlfr(
        "compare",
        "history",
        "--db",
        str(db_path),
        "--limit",
        "1",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["summary"]["run_groups"] == 1
    assert payload["summary"]["limit"] == 1
    assert payload["summary"]["total_indexed"] == 2
