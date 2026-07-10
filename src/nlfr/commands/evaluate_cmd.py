"""`nlfr evaluate` — truth-labeled verdict + next steps for a run group.

Reads recorded evidence back (read-only), computes the deterministic
``nlfr.evaluation.v1`` verdict, and optionally (``--record``) writes it into
the evidence DB as an idempotent ``evaluation`` proof block so the reasoning
itself becomes part of the flight record — queryable by ``proof export``,
renderable by the canvas, and attestable alongside everything else.

Exit codes: 0 the evaluation ran (whatever the verdict says); 2 the evidence
could not be evaluated (unreadable DB, unknown run group); 1 only behind
``--fail-on-action-required`` when the verdict's first next step is anything
but ``none_complete`` — mirroring the ``--fail-on-validation`` convention.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from nlfr.db.connection import UnreadableDatabaseError, connect, connect_readonly
from nlfr.db.ingest import upsert_proof_block
from nlfr.evaluator import evaluate_run_group
from nlfr.projectors.common import run_rows, write_or_print
from nlfr.projectors.compare import MissingRunGroupError


def evaluate_exit_code(verdict: dict[str, Any]) -> int:
    """Return 1 when the verdict demands action; 0 when nothing is outstanding."""

    steps = verdict.get("next_steps") or []
    first = steps[0]["action"] if steps else None
    return 0 if first == "none_complete" else 1


def run(args: argparse.Namespace) -> int:
    try:
        conn = connect_readonly(args.db)
    except UnreadableDatabaseError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    try:
        verdict = evaluate_run_group(
            conn,
            args.run_group,
            artifact_root=args.artifact_root,
            attribution_target=args.attribution_target,
            workspace=args.workspace,
        )
        run_id = run_rows(conn, args.run_group)[-1]["id"]
    except MissingRunGroupError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    finally:
        conn.close()

    if args.record:
        writer = connect(args.db)
        try:
            upsert_proof_block(
                writer,
                stable_key=f"{run_id}:evaluation",
                run_id=run_id,
                block_key="evaluation",
                block_kind="evaluation",
                title="Evaluation verdict",
                summary=_one_line(verdict),
                payload=verdict,
                source_kind=verdict["source_kind"],
                confidence=verdict["confidence"],
                evidence_refs=verdict["evidence_refs"],
                redaction_state=verdict["redaction_state"],
            )
            writer.commit()
        finally:
            writer.close()

    if args.format == "markdown":
        _write_or_print_text(_render_markdown(verdict), args.output)
        if args.output:
            sidecar = Path(args.output).with_suffix(".json")
            sidecar.parent.mkdir(parents=True, exist_ok=True)
            sidecar.write_text(
                json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
    else:
        write_or_print(verdict, args.output)

    if args.fail_on_action_required:
        return evaluate_exit_code(verdict)
    return 0


def _one_line(verdict: dict[str, Any]) -> str:
    status = (verdict.get("status") or {}).get("status", "unknown")
    steps = verdict.get("next_steps") or []
    first = steps[0]["action"] if steps else "none"
    classification = (verdict.get("classification") or {}).get("classification")
    return f"status={status} · classification={classification} · next={first}"


def _render_markdown(verdict: dict[str, Any]) -> str:
    status = verdict.get("status") or {}
    classification = verdict.get("classification") or {}
    cache = verdict.get("cache") or {}
    lines = [
        f"## Evaluation verdict — `{verdict.get('run_group')}`",
        "",
        f"- **Status:** {status.get('status')} ({status.get('failure_count', 0)} failure(s))",
        f"- **Classification:** {classification.get('classification')}",
        f"- **Cache:** {cache.get('hits')} hit(s) / {cache.get('misses')} miss(es)",
        "",
        "### Next steps (precedence order)",
        "",
    ]
    for index, step in enumerate(verdict.get("next_steps") or [], start=1):
        lines.append(f"{index}. `{step['action']}` — {step['reason']}")
    lines += [
        "",
        f"_{verdict.get('source_kind')} · {verdict.get('confidence')} · "
        f"{verdict.get('redaction_state')}_",
        "",
    ]
    return "\n".join(lines)


def _write_or_print_text(text: str, output: str | None) -> None:
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``evaluate`` subcommand."""

    parser = subparsers.add_parser(
        "evaluate",
        help="evaluate recorded evidence into a truth-labeled verdict + next steps",
        description=(
            "Evaluate one run group's recorded evidence into a deterministic, "
            "truth-labeled verdict (nlfr.evaluation.v1) with a precedence-ordered "
            "next-steps list. The verdict is always derived_v1 — a computed "
            "judgment over already-labeled evidence, never a new observation."
        ),
    )
    parser.add_argument("--run-group", default="latest", help="run group id to evaluate")
    parser.add_argument("--db", default="data/nlfr/nlfr.sqlite", help="SQLite database path")
    parser.add_argument(
        "--artifact-root",
        help="recorded run artifact directory (enables failure classification "
        "and evidence excerpts from bazel.stderr/stdout.txt artifacts)",
    )
    parser.add_argument(
        "--attribution-target",
        help="Bazel label the failure must reference to count as honestly attributed",
    )
    parser.add_argument(
        "--workspace",
        help="validation workspace to inspect for pending (unvalidated) edits",
    )
    parser.add_argument("--output", help="output path (JSON, or markdown with --format)")
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
        help="output format (markdown writes a sibling .json sidecar when --output is set)",
    )
    parser.add_argument(
        "--record",
        action="store_true",
        help="also record the verdict into the DB as an idempotent 'evaluation' proof block",
    )
    parser.add_argument(
        "--fail-on-action-required",
        action="store_true",
        help="exit 1 when the first next step is anything but none_complete",
    )
    parser.set_defaults(handler=run)
