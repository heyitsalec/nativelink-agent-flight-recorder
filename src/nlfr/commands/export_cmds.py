"""Projection export commands."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from nlfr.db.connection import UnreadableDatabaseError, connect_readonly
from nlfr.projectors import (
    export_action_graph,
    export_in_toto_statement,
    export_proof_packet,
    export_validation_runway,
)
from nlfr.projectors.common import write_or_print
from nlfr.projectors.in_toto import EmptySubjectError
from nlfr.projectors.pr_comment import (
    build_pr_comment_summary,
    pr_comment_exit_code,
    render_pr_comment_markdown,
)
from nlfr.projectors.proof_markdown import export_proof_markdown, proof_markdown_exit_code
from nlfr.projectors.timeline import build_timeline_projection


def export_graph(args: argparse.Namespace) -> int:
    """Export an action graph projection for a run group."""

    try:
        conn = connect_readonly(args.db)
    except UnreadableDatabaseError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    write_or_print(export_action_graph(conn, run_group=args.run_group), args.output)
    return 0


def export_runway(args: argparse.Namespace) -> int:
    """Export a validation runway projection for a run group."""

    try:
        conn = connect_readonly(args.db)
    except UnreadableDatabaseError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    write_or_print(export_validation_runway(conn, run_group=args.run_group), args.output)
    return 0


def export_proof(args: argparse.Namespace) -> int:
    """Export a proof packet projection for a run group."""

    try:
        conn = connect_readonly(args.db)
    except UnreadableDatabaseError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.format == "in-toto":
        # Unsigned, DSSE-ready in-toto Statement over the run group's recorded
        # artifacts; existing json/markdown behavior is untouched. A zero-subject
        # export is a HARD ERROR (a signable-but-vacuous attestation is dangerous)
        # unless --allow-empty-subject is passed.
        try:
            statement = export_in_toto_statement(
                conn,
                run_group=args.run_group,
                allow_empty_subject=args.allow_empty_subject,
            )
        except EmptySubjectError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        write_or_print(statement, args.output)
        return 0
    proof = export_proof_packet(conn, run_group=args.run_group)
    if args.format == "markdown":
        projection_paths = {}
        if args.graph_projection:
            projection_paths["Graph JSON"] = args.graph_projection
        if args.proof_projection:
            projection_paths["Proof JSON"] = args.proof_projection
        if args.runway_projection:
            projection_paths["Runway JSON"] = args.runway_projection
        markdown = export_proof_markdown(
            proof,
            db_path=args.db,
            manifest_path=args.manifest,
            projection_paths=projection_paths or None,
            repo_root=args.repo_root,
        )
        _write_or_print_text(markdown, args.output)
        if args.fail_on_validation:
            return proof_markdown_exit_code(proof)
        return 0

    write_or_print(proof, args.output)
    return 0


def export_proof_comment(args: argparse.Namespace) -> int:
    """Render a COMPACT, redacted PR-comment summary plus its JSON sidecar.

    Issue #87. Unlike ``proof export --format markdown`` (the verbose per-block
    renderer), this emits the scannable summary that lands in a PR/review surface:
    status, cache economics, the artifact-integrity rollup (local + remote_*
    tiers), agent-receipt provenance presence, and an optional in-toto ref. Both
    the markdown and the machine-readable JSON are routed through
    :mod:`nlfr.redaction`, so a ``nlfr redact --check`` over either output is clean.
    """

    try:
        conn = connect_readonly(args.db)
    except UnreadableDatabaseError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    proof = export_proof_packet(conn, run_group=args.run_group)
    in_toto = _resolve_in_toto(args)
    summary = build_pr_comment_summary(proof, in_toto=in_toto)
    markdown = render_pr_comment_markdown(summary)

    _write_or_print_text(markdown, args.output)

    # The JSON sidecar (CI artifact). When --json-output is omitted but a markdown
    # --output path is given, derive a sibling ``<stem>.json`` so both paired
    # artifacts land by default; with neither path we only stream markdown.
    json_output = args.json_output
    if not json_output and args.output:
        json_output = str(Path(args.output).with_suffix(".json"))
    if json_output:
        json_path = Path(json_output)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    if args.fail_on_validation:
        return pr_comment_exit_code(summary)
    return 0


def export_timeline(args: argparse.Namespace) -> int:
    """Export the merged timeline projection for one or more evidence DBs."""

    from pathlib import Path as _Path

    db_paths: list[str] = list(args.db or [])
    if args.db_root:
        root = _Path(args.db_root)
        if not root.is_dir():
            print(f"--db-root is not a directory: {root}", file=sys.stderr)
            return 2
        for child in sorted(root.iterdir()):
            candidate = child / "nlfr.sqlite"
            if child.is_dir() and candidate.is_file():
                db_paths.append(str(candidate))
    if not db_paths:
        db_paths = ["data/nlfr/nlfr.sqlite"]

    sources = []
    try:
        for db_path in db_paths:
            label = _Path(db_path).parent.name or _Path(db_path).stem
            sources.append((label, connect_readonly(db_path)))
        write_or_print(build_timeline_projection(sources), args.output)
    except UnreadableDatabaseError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    finally:
        for _, conn in sources:
            conn.close()
    return 0


def _resolve_in_toto(args: argparse.Namespace) -> dict[str, object]:
    """Resolve the honest in-toto attestation reference to cite (never fabricated).

    ``--in-toto PATH`` cites a content digest of the *actually exported* file (so
    the ref proves the attestation exists without leaking its filesystem path); a
    missing path honestly reports ``exported: false``. ``--in-toto-ref REF`` cites
    a caller-supplied string (redacted downstream). Neither flag -> not exported.
    """

    path = getattr(args, "in_toto", None)
    if path:
        file_path = Path(path)
        if file_path.is_file():
            digest = hashlib.sha256(file_path.read_bytes()).hexdigest()
            return {"exported": True, "ref": f"sha256:{digest[:12]}"}
        return {"exported": False, "ref": None}
    ref = getattr(args, "in_toto_ref", None)
    if ref:
        return {"exported": True, "ref": str(ref)}
    return {"exported": False, "ref": None}


def _write_or_print_text(text: str, output: str | None) -> None:
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


def add_export_command(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    name: str,
    handler: object,
    help_text: str,
) -> None:
    """Add a shared ``export`` subcommand with run-group and DB flags."""

    parser = subparsers.add_parser(
        name,
        help=help_text,
        description=help_text.capitalize() + ".",
    )
    parser.add_argument(
        "--run-group",
        default="latest",
        help="run group id to export",
    )
    parser.add_argument(
        "--db",
        default="data/nlfr/nlfr.sqlite",
        help="SQLite database path",
    )
    parser.add_argument(
        "--output",
        help="output path for JSON projection",
    )
    parser.set_defaults(handler=handler)


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register graph, runway, and proof export command groups."""

    graph = subparsers.add_parser(
        "graph",
        help="graph projection commands",
        description="Graph projection commands.",
    )
    graph_subparsers = graph.add_subparsers(dest="graph_command", metavar="command", required=True)
    add_export_command(graph_subparsers, "export", export_graph, "export graph projection JSON")

    runway = subparsers.add_parser(
        "runway",
        help="runway projection commands",
        description="Runway projection commands.",
    )
    runway_subparsers = runway.add_subparsers(dest="runway_command", metavar="command", required=True)
    add_export_command(runway_subparsers, "export", export_runway, "export runway projection JSON")

    timeline = subparsers.add_parser(
        "timeline",
        help="timeline projection commands",
        description="Timeline projection commands (the replayable flight record).",
    )
    timeline_subparsers = timeline.add_subparsers(
        dest="timeline_command", metavar="command", required=True
    )
    timeline_export = timeline_subparsers.add_parser(
        "export",
        help="export a chronological, truth-labeled event timeline",
        description=(
            "Merge one or more evidence databases into a single chronological "
            "timeline projection (runs, evaluation verdicts, agent receipts) "
            "with derived repair-loop chapters. Renders in the canvas Replay "
            "lens; recorded timestamps only, never wall-clock."
        ),
    )
    timeline_export.add_argument(
        "--db",
        action="append",
        default=None,
        help="SQLite database path; repeatable to merge several databases",
    )
    timeline_export.add_argument(
        "--db-root",
        help=(
            "an `nlfr record` layout root: every immediate subdirectory "
            "containing an nlfr.sqlite is merged (same discovery as compare)"
        ),
    )
    timeline_export.add_argument("--output", help="output path for JSON projection")
    timeline_export.set_defaults(handler=export_timeline)

    proof = subparsers.add_parser(
        "proof",
        help="proof packet commands",
        description="Proof packet commands.",
    )
    proof_subparsers = proof.add_subparsers(dest="proof_command", metavar="command", required=True)
    _add_proof_export_command(proof_subparsers)
    _add_proof_comment_command(proof_subparsers)


def _add_proof_export_command(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Add ``proof export`` with JSON and markdown formats."""

    parser = subparsers.add_parser(
        "export",
        help="export proof packet JSON or PR markdown",
        description="Export proof packet JSON or redacted PR markdown.",
    )
    parser.add_argument(
        "--run-group",
        default="latest",
        help="run group id to export",
    )
    parser.add_argument(
        "--db",
        default="data/nlfr/nlfr.sqlite",
        help="SQLite database path",
    )
    parser.add_argument(
        "--output",
        help="output path (JSON or markdown depending on --format)",
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown", "in-toto"),
        default="json",
        help=(
            "output format (default: json). 'in-toto' emits an unsigned, "
            "DSSE-ready in-toto Statement over recorded artifacts."
        ),
    )
    parser.add_argument(
        "--manifest",
        help="artifact manifest path to cite in markdown export",
    )
    parser.add_argument(
        "--graph-projection",
        help="graph projection JSON path to cite in markdown export",
    )
    parser.add_argument(
        "--proof-projection",
        help="proof projection JSON path to cite in markdown export",
    )
    parser.add_argument(
        "--runway-projection",
        help="runway projection JSON path to cite in markdown export",
    )
    parser.add_argument(
        "--repo-root",
        help="replace this prefix with <repo> in markdown path citations",
    )
    parser.add_argument(
        "--fail-on-validation",
        action="store_true",
        help="exit 1 when validation failures are present (markdown only)",
    )
    parser.add_argument(
        "--allow-empty-subject",
        action="store_true",
        help=(
            "in-toto only: export an empty-subject Statement (exit 0, stderr "
            "warning) instead of failing hard when the run group has no recorded "
            "artifacts. For automation edge cases; a signed empty attestation "
            "proves nothing."
        ),
    )
    parser.set_defaults(handler=export_proof)


def _add_proof_comment_command(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Add ``proof comment`` — the compact PR-comment / CI-artifact summary."""

    parser = subparsers.add_parser(
        "comment",
        help="render a compact redacted PR-comment summary + JSON sidecar",
        description=(
            "Render a COMPACT, redacted proof-packet summary for a PR comment "
            "(markdown) plus a machine-readable JSON sidecar for CI attachment. "
            "Distinct from 'proof export --format markdown', which emits every "
            "block; this is the scannable review-surface summary."
        ),
    )
    parser.add_argument(
        "--run-group",
        default="latest",
        help="run group id to summarize",
    )
    parser.add_argument(
        "--db",
        default="data/nlfr/nlfr.sqlite",
        help="SQLite database path",
    )
    parser.add_argument(
        "--output",
        help="markdown output path (default: stdout). A sibling <stem>.json "
        "sidecar is written alongside it unless --json-output overrides.",
    )
    parser.add_argument(
        "--json-output",
        help="explicit path for the machine-readable JSON sidecar",
    )
    parser.add_argument(
        "--in-toto",
        help="path to an exported in-toto attestation to cite by content digest "
        "(a missing path is reported honestly as not exported)",
    )
    parser.add_argument(
        "--in-toto-ref",
        help="literal in-toto attestation reference string to cite "
        "(redacted before it reaches the output)",
    )
    parser.add_argument(
        "--fail-on-validation",
        action="store_true",
        help="exit 1 when validation failures are present",
    )
    parser.set_defaults(handler=export_proof_comment)
