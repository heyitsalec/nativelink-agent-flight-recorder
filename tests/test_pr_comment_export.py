"""Compact PR-comment / CI-attachment exporter (`nlfr proof comment`, issue #87).

Renders a proof packet as a COMPACT redacted markdown summary (for a PR comment)
plus a machine-readable JSON sidecar (for a CI artifact). These tests prove the
exporter is honest at the sharing boundary: every output is redact-clean (no
abs_path / secret / raw prompt), carries truth labels, surfaces the local *and*
remote_* artifact-verification tiers, and never emits an over-claim string
(cost / cross-machine / scheduler assignment). A drift guard keeps the committed
compact samples byte-identical to the real exporter output.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

from nlfr.db import connect, initialize
from nlfr.db.ingest import (
    upsert_artifact_reference,
    upsert_cache_event,
    upsert_failure,
    upsert_invocation,
    upsert_proof_block,
    upsert_run,
    upsert_target,
)
from nlfr.projectors.pr_comment import (
    build_pr_comment_summary,
    pr_comment_exit_code,
    render_pr_comment_markdown,
)
from nlfr.projectors.proof import export_proof_packet
from nlfr.redaction import RedactionConfig, redact_payload, redact_text

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_MD = ROOT / "docs" / "proof-samples" / "pr-comment-compact-sample.md"
SAMPLE_JSON = ROOT / "docs" / "proof-samples" / "pr-comment-compact-sample.json"
SCRIPT = ROOT / "scripts" / "export-pr-proof-comment.sh"

CANONICAL_RUN_GROUP = "record-proof"
FIXED_TS = "2026-07-07T00:00:00.000000Z"
CANONICAL_IN_TOTO = {"exported": True, "ref": "sha256:deadbeefcafe"}

# Over-claim gate. A COMPACT proof comment must never assert cost figures, a
# cross-machine ("fleet") rollup, cache "savings", or scheduler assignment —
# these are exactly the incumbent-style claims NLFR refuses to fabricate. The
# gate fails on the *tokens themselves* (not only positive assertions), so the
# renderer avoids them even in disclaimers; that keeps the guard trivially
# auditable against future drift.
_FORBIDDEN = re.compile(r"dollar|fleet|\bsaved\b|\$\s?[0-9]|scheduler[ _-]assignment", re.IGNORECASE)


def _seed_canonical(
    db_path: Path,
    *,
    run_group: str = CANONICAL_RUN_GROUP,
    with_failure: bool = False,
    with_agent: bool = True,
) -> None:
    """Seed a proof DB exercising every compact-summary section.

    Cache hits+miss, artifact references across the local verified/missing tier
    AND the remote CAS-verified + unverified-remote tiers, an optional failure,
    and an optional hash-only agent-provenance block whose raw prompt must never
    reach the output.
    """

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
    for index, hit in enumerate((True, True, False)):
        upsert_cache_event(
            conn,
            stable_key=f"cache:{run_group}:{index}",
            run_id=run_id,
            target_id=target_id,
            event_key=f"cache-{index}",
            event_kind="action_cache",
            hit=hit,
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
        cwd=str(db_path.parent),
        exit_code=1 if with_failure else 0,
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["artifact:bazel.stdout.txt"],
        redaction_state="safe",
    )
    # References across verification tiers: local verified, local missing, an
    # independently CAS-verified remote reference, and an unverified remote one.
    references = [
        ("ref-verified", "local_verified", 1, "a" * 64),
        ("ref-missing", "missing", None, None),
        ("ref-remote-verified", "remote_verified", 1, "b" * 64),
        ("ref-remote-unverified", "unverified_remote_reference", None, None),
    ]
    for key, presence, verified, computed in references:
        upsert_artifact_reference(
            conn,
            stable_key=f"aref:{run_group}:{key}",
            run_id=run_id,
            target_id=target_id,
            reference_key=key,
            name=key,
            uri=f"bytestream://cas.example/{key}",
            declared_digest=("a" * 64 if presence != "remote_verified" else "b" * 64),
            declared_size_bytes=10,
            computed_digest=computed,
            digest_verified=verified,
            presence=presence,
            verification_note="seed",
            source_kind="collectable_v1",
            confidence="high",
            evidence_refs=[f"aref:{key}"],
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
    if with_agent:
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


def build_canonical_sample(tmp_path: Path) -> tuple[dict, str]:
    """Deterministic (summary, markdown) pair backing the committed samples.

    Shared by the drift-guard test AND ``scripts`` regeneration so the committed
    files can never silently diverge from the real exporter. The proof packet's
    dynamic ``generated_at`` is pinned to :data:`FIXED_TS` for reproducibility.
    """

    db_path = tmp_path / "nlfr.sqlite"
    _seed_canonical(db_path)
    proof = export_proof_packet(connect(db_path), run_group=CANONICAL_RUN_GROUP)
    proof["generated_at"] = FIXED_TS
    summary = build_pr_comment_summary(proof, in_toto=CANONICAL_IN_TOTO)
    markdown = render_pr_comment_markdown(summary)
    return summary, markdown


def _canonical_json_text(summary: dict) -> str:
    return json.dumps(summary, indent=2, sort_keys=True) + "\n"


# --------------------------------------------------------------------------- #
# Honest content
# --------------------------------------------------------------------------- #


def test_compact_summary_has_honest_sections(tmp_path: Path) -> None:
    summary, markdown = build_canonical_sample(tmp_path)

    # Machine-readable shape.
    assert summary["projection_kind"] == "pr_comment"
    assert summary["status"] == {"status": "ok", "failures": 0}
    assert summary["cache"]["hits"] == 2 and summary["cache"]["misses"] == 1
    av = summary["artifact_verification"]
    assert av["total"] == 4
    assert av["local"]["verified"] == 1 and av["local"]["missing"] == 1
    assert av["remote"]["verified"] == 1  # remote_* tier surfaced
    assert av["unverified_remote"] == 1
    assert summary["agent_receipt"]["present"] is True
    assert summary["in_toto"] == {"exported": True, "ref": "sha256:deadbeefcafe"}

    # Markdown renders every section a reviewer scans.
    assert "## NLFR Proof Summary" in markdown
    assert "**Status:** ok — 0 validation failure(s)" in markdown
    assert "**Cache economics:**" in markdown
    assert "**Artifact integrity verification** (4 reference(s)):" in markdown
    assert "remote (CAS): 1 verified" in markdown
    assert "1 unverified (no probe)" in markdown
    assert "**Agent receipt provenance:** present" in markdown
    assert "prompt_sha256 `aaaaaaaaaaaa…`" in markdown
    assert "**in-toto attestation:** exported · ref `sha256:deadbeefcafe`" in markdown
    assert "`derived_v1` · `high` · `safe`" in markdown


def test_compact_outputs_are_redact_clean(tmp_path: Path) -> None:
    summary, markdown = build_canonical_sample(tmp_path)

    json_findings = redact_payload(summary, RedactionConfig()).findings
    md_findings = redact_text(markdown, RedactionConfig()).findings
    assert json_findings == [], json_findings
    assert md_findings == [], md_findings

    # Belt-and-suspenders: no home path, abs path, or raw prompt survived.
    text = markdown + _canonical_json_text(summary)
    assert "/Users/" not in text
    assert "/private/tmp" not in text
    assert "SECRET PROMPT" not in text


def test_compact_outputs_have_no_overclaim_strings(tmp_path: Path) -> None:
    summary, markdown = build_canonical_sample(tmp_path)
    blob = markdown + "\n" + _canonical_json_text(summary)
    match = _FORBIDDEN.search(blob)
    assert match is None, f"forbidden over-claim string present: {match!r}"


def test_agent_receipt_absent_when_no_block(tmp_path: Path) -> None:
    db_path = tmp_path / "nlfr.sqlite"
    _seed_canonical(db_path, with_agent=False)
    proof = export_proof_packet(connect(db_path), run_group=CANONICAL_RUN_GROUP)
    summary = build_pr_comment_summary(proof)
    assert summary["agent_receipt"] == {"present": False, "count": 0, "agents": []}
    markdown = render_pr_comment_markdown(summary)
    assert "**Agent receipt provenance:** absent" in markdown
    # A run group with no in-toto export honestly reports so.
    assert summary["in_toto"] == {"exported": False, "ref": None}
    assert "**in-toto attestation:** not exported" in markdown


def test_fail_on_validation_exit_code(tmp_path: Path) -> None:
    ok_db = tmp_path / "ok.sqlite"
    fail_db = tmp_path / "fail.sqlite"
    _seed_canonical(ok_db, with_failure=False)
    _seed_canonical(fail_db, with_failure=True)

    ok = build_pr_comment_summary(export_proof_packet(connect(ok_db), run_group=CANONICAL_RUN_GROUP))
    failed = build_pr_comment_summary(
        export_proof_packet(connect(fail_db), run_group=CANONICAL_RUN_GROUP)
    )
    assert pr_comment_exit_code(ok) == 0
    assert failed["status"] == {"status": "failed", "failures": 1}
    assert pr_comment_exit_code(failed) == 1
    assert "**Status:** FAILED — 1 validation failure(s)" in render_pr_comment_markdown(failed)


def test_injected_abs_path_is_scrubbed_and_state_upgraded(tmp_path: Path) -> None:
    """A path leaking through the citable in-toto ref is scrubbed and relabelled.

    Proves the sharing boundary: a scrub anywhere in the summary upgrades the
    top-level ``redaction_state`` safe -> redacted, and the output stays clean.
    """

    db_path = tmp_path / "nlfr.sqlite"
    _seed_canonical(db_path)
    proof = export_proof_packet(connect(db_path), run_group=CANONICAL_RUN_GROUP)
    summary = build_pr_comment_summary(
        proof, in_toto={"exported": True, "ref": "/private/tmp/ci-runner/attest/in-toto.jsonl"}
    )
    assert summary["redaction_state"] == "redacted"
    assert summary["in_toto"]["ref"] == "[REDACTED:abs_path]/in-toto.jsonl"
    markdown = render_pr_comment_markdown(summary)
    assert redact_payload(summary, RedactionConfig()).findings == []
    assert redact_text(markdown, RedactionConfig()).findings == []
    assert "`derived_v1` · `high` · `redacted`" in markdown


# --------------------------------------------------------------------------- #
# CLI + script surface
# --------------------------------------------------------------------------- #


def test_cli_writes_markdown_and_json_sidecar(tmp_path: Path) -> None:
    db_path = tmp_path / "nlfr.sqlite"
    _seed_canonical(db_path)
    output = tmp_path / "pr-comment.md"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "nlfr",
            "proof",
            "comment",
            "--run-group",
            CANONICAL_RUN_GROUP,
            "--db",
            str(db_path),
            "--output",
            str(output),
            "--fail-on-validation",
        ],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    md_text = output.read_text(encoding="utf-8")
    # The JSON sidecar is auto-derived beside the markdown.
    sidecar = output.with_suffix(".json")
    assert sidecar.is_file(), "JSON sidecar was not written beside the markdown"
    payload = json.loads(sidecar.read_text(encoding="utf-8"))

    assert "## NLFR Proof Summary" in md_text
    assert payload["projection_kind"] == "pr_comment"
    assert "/Users/" not in md_text and "SECRET PROMPT" not in md_text
    assert "SECRET PROMPT" not in json.dumps(payload)


def test_script_syntax_is_valid() -> None:
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


def test_script_compact_mode_writes_and_gates(tmp_path: Path) -> None:
    db_path = tmp_path / "nlfr.sqlite"
    _seed_canonical(db_path)
    output = tmp_path / "compact.md"

    result = subprocess.run(
        [
            "bash",
            str(SCRIPT),
            "--compact",
            "--run-group",
            CANONICAL_RUN_GROUP,
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
    assert output.is_file()
    assert output.with_suffix(".json").is_file()
    md_text = output.read_text(encoding="utf-8")
    assert "## NLFR Proof Summary" in md_text
    assert "/Users/" not in md_text
    # The script asserts the redact gate ran clean.
    assert "redact --check" in result.stdout or "redact" in result.stdout.lower()


# --------------------------------------------------------------------------- #
# Committed-sample drift guard
# --------------------------------------------------------------------------- #


def test_committed_compact_samples_match_exporter(tmp_path: Path) -> None:
    """The committed compact samples are byte-identical to the real exporter.

    If this fails, regenerate the samples from the exporter (do not hand-edit):
        python -m pytest tests/test_pr_comment_export.py  # then use scripts/regen
    """

    assert SAMPLE_MD.is_file(), f"missing committed sample {SAMPLE_MD}"
    assert SAMPLE_JSON.is_file(), f"missing committed sample {SAMPLE_JSON}"

    summary, markdown = build_canonical_sample(tmp_path)
    assert SAMPLE_MD.read_text(encoding="utf-8") == markdown
    assert SAMPLE_JSON.read_text(encoding="utf-8") == _canonical_json_text(summary)


def test_committed_compact_samples_are_redact_clean() -> None:
    md_text = SAMPLE_MD.read_text(encoding="utf-8")
    json_text = SAMPLE_JSON.read_text(encoding="utf-8")
    assert redact_text(md_text, RedactionConfig()).findings == []
    assert redact_payload(json.loads(json_text), RedactionConfig()).findings == []
    assert _FORBIDDEN.search(md_text + json_text) is None
