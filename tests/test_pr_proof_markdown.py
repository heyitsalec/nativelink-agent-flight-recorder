import json
import subprocess
import sys
from pathlib import Path

from nlfr.db import connect, initialize
from nlfr.db.ingest import (
    upsert_cache_event,
    upsert_failure,
    upsert_invocation,
    upsert_proof_block,
    upsert_run,
    upsert_target,
)
from nlfr.projectors.proof import export_proof_packet
from nlfr.projectors.proof_markdown import (
    export_proof_markdown,
    proof_markdown_exit_code,
    redact_repo_path,
    validation_status,
)

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "docs" / "proof-samples" / "pr-proof-comment-sample.md"
SCRIPT = ROOT / "scripts" / "export-pr-proof-comment.sh"


def _seed_proof_db(db_path: Path, *, run_group: str, with_failure: bool = False) -> None:
    conn = initialize(connect(db_path))
    run_id = upsert_run(
        conn,
        stable_key=f"run:{run_group}",
        run_group=run_group,
        scenario="agent-loop",
        mode="cache-only",
        status="completed",
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
        status="failed" if with_failure else "passed",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["bep:target-completed"],
        redaction_state="safe",
    )
    upsert_cache_event(
        conn,
        stable_key=f"cache:{run_group}",
        run_id=run_id,
        target_id=target_id,
        event_key="cache-1",
        event_kind="action_cache",
        hit=True,
        source_kind="derived_v1",
        confidence="medium",
        evidence_refs=["execution-log:test"],
        redaction_state="safe",
    )
    upsert_invocation(
        conn,
        stable_key=f"invocation:{run_group}",
        run_id=run_id,
        invocation_kind="bazel",
        command=["bazel", "test", "//tasks:priority_test"],
        cwd=db_path.parent,
        exit_code=1 if with_failure else 0,
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["artifact:bazel.stdout.txt"],
        redaction_state="safe",
    )
    if with_failure:
        upsert_failure(
            conn,
            stable_key=f"failure:{run_group}",
            run_id=run_id,
            failure_kind="test_failed",
            message="target failed",
            source_kind="collectable_v1",
            confidence="high",
            evidence_refs=["bep:failure"],
            redaction_state="safe",
        )
    upsert_proof_block(
        conn,
        stable_key=f"{run_group}:agent-provenance",
        run_id=run_id,
        block_key=f"agent-provenance:{run_group}",
        block_kind="agent_provenance",
        title="Agent Provenance: demo-agent",
        summary="Bounded agent provenance for PR markdown export.",
        payload={
            "scenario_id": run_group,
            "agent": {
                "name": "demo-agent",
                "model": "composer-2.5",
                "prompt_sha256": "a" * 64,
                "prompt_text": "SECRET PROMPT BODY MUST NOT APPEAR",
            },
        },
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=[f"agent-provenance:{run_group}"],
        redaction_state="safe",
    )


def test_pr_proof_comment_sample_shape() -> None:
    sample = SAMPLE.read_text(encoding="utf-8")

    assert "## NLFR Proof Summary" in sample
    assert "**Export labels:** `derived_v1` · `high` · `safe`" in sample
    assert "**Labels:**" in sample
    assert "`collectable_v1`" in sample
    assert "`derived_v1`" in sample
    assert "prompt_sha256" in sample
    assert "SECRET PROMPT" not in sample
    assert "/Users/" not in sample
    assert "${HOME}" not in sample
    assert "<repo>" in sample
    assert "Unsupported claims" in sample
    assert "Boundary labels only" in sample


def test_export_proof_markdown_redacts_paths_and_prompts(tmp_path: Path) -> None:
    db_path = tmp_path / "nlfr.sqlite"
    _seed_proof_db(db_path, run_group="record-proof")

    conn = connect(db_path)
    proof = export_proof_packet(conn, run_group="record-proof")
    markdown = export_proof_markdown(
        proof,
        db_path=f"/Users/example/nlfr/data/record-proof/nlfr.sqlite",
        manifest_path=f"/Users/example/nlfr/data/record-proof/artifact_manifest.json",
        projection_paths={
            "Proof JSON": f"/Users/example/nlfr/data/record-proof/projections/proof-packet.json",
        },
        repo_root="/Users/example/nlfr",
    )

    assert "## NLFR Proof Summary" in markdown
    assert "**Run group:** `record-proof`" in markdown
    assert "<repo>/data/record-proof/nlfr.sqlite" in markdown
    assert "/Users/" not in markdown
    assert "SECRET PROMPT" not in markdown
    assert "prompt_sha256: `aaaaaaaaaaaa…`" in markdown
    assert "**Labels:** `collectable_v1` · `high` · `safe`" in markdown
    assert "does not claim remote worker assignment" in markdown
    assert "Unsupported claims" in markdown


def test_validation_exit_code_separates_failures_from_boundary_labels(tmp_path: Path) -> None:
    ok_db = tmp_path / "ok.sqlite"
    fail_db = tmp_path / "fail.sqlite"
    _seed_proof_db(ok_db, run_group="record-proof", with_failure=False)
    _seed_proof_db(fail_db, run_group="record-proof", with_failure=True)

    ok_proof = export_proof_packet(connect(ok_db), run_group="record-proof")
    fail_proof = export_proof_packet(connect(fail_db), run_group="record-proof")

    assert validation_status(ok_proof)["failure_count"] == 0
    assert validation_status(fail_proof)["failure_count"] == 1
    assert proof_markdown_exit_code(ok_proof) == 0
    assert proof_markdown_exit_code(fail_proof) == 1

    ok_markdown = export_proof_markdown(ok_proof)
    assert "Unsupported claims" in ok_markdown
    assert proof_markdown_exit_code(ok_proof) == 0


def test_markdown_renders_artifact_verification_summary_readably() -> None:
    """The artifact_verification rollup renders as readable markdown, not a dict repr.

    Regression for issue #44: the top-level metrics table used to print the
    ``artifact_verification`` summary as a raw Python dict repr
    (``{'total': 3, ...}``); render it as a ``·``-separated breakdown instead.
    """

    proof = {
        "run_group": "record-2026-07-06",
        "generated_at": "2026-07-06T00:00:00.000000Z",
        "summary": {
            "runs": 1,
            "artifacts": 2,
            "artifact_verification": {
                "total": 3,
                "verified_count": 1,
                "present_unverified": 0,
                "mismatched": 0,
                "missing": 1,
                "unverified_remote": 1,
            },
        },
        "blocks": [],
    }

    markdown = export_proof_markdown(proof)

    # The readable breakdown is present.
    assert "3 total" in markdown
    assert "1 verified" in markdown
    assert "1 missing" in markdown
    assert "1 unverified-remote" in markdown

    # The raw Python dict repr is gone from the artifact_verification row.
    verification_row = next(
        line for line in markdown.splitlines() if line.startswith("| artifact_verification")
    )
    assert "{'" not in verification_row
    assert "3 total · 1 verified" in verification_row


def test_redact_repo_path_replaces_root() -> None:
    assert (
        redact_repo_path("/Users/example/repo/data/nlfr.sqlite", repo_root="/Users/example/repo")
        == "<repo>/data/nlfr.sqlite"
    )


def test_proof_export_markdown_cli(tmp_path: Path) -> None:
    db_path = tmp_path / "nlfr.sqlite"
    _seed_proof_db(db_path, run_group="pr-proof")
    output = tmp_path / "comment.md"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "nlfr",
            "proof",
            "export",
            "--format",
            "markdown",
            "--run-group",
            "pr-proof",
            "--db",
            str(db_path),
            "--output",
            str(output),
            "--repo-root",
            str(tmp_path),
            "--manifest",
            str(tmp_path / "artifact_manifest.json"),
            "--proof-projection",
            str(tmp_path / "projections" / "proof-packet.json"),
        ],
        cwd=ROOT,
        env={**__import__("os").environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    text = output.read_text(encoding="utf-8")
    assert "pr-proof" in text
    assert "/Users/" not in text
    assert "SECRET PROMPT" not in text


def test_export_pr_proof_comment_script_syntax() -> None:
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_export_pr_proof_comment_script_writes_markdown(tmp_path: Path) -> None:
    db_path = tmp_path / "nlfr.sqlite"
    _seed_proof_db(db_path, run_group="record-proof")
    output = tmp_path / "proof-comment.md"

    result = subprocess.run(
        [
            "bash",
            str(SCRIPT),
            "--run-group",
            "record-proof",
            "--db",
            str(db_path),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    text = output.read_text(encoding="utf-8")
    assert "record-proof" in text
    assert "/Users/" not in text
    assert json.dumps({"prompt_text": "SECRET"}) not in text
