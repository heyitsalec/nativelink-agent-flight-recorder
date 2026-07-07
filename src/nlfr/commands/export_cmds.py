"""Projection export commands."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from nlfr.db import connect, initialize
from nlfr.projectors import (
    export_action_graph,
    export_in_toto_statement,
    export_proof_packet,
    export_validation_runway,
)
from nlfr.projectors.common import write_or_print
from nlfr.projectors.in_toto import EmptySubjectError
from nlfr.projectors.proof_markdown import export_proof_markdown, proof_markdown_exit_code


def export_graph(args: argparse.Namespace) -> int:
    """Export an action graph projection for a run group."""

    conn = initialize(connect(args.db))
    write_or_print(export_action_graph(conn, run_group=args.run_group), args.output)
    return 0


def export_runway(args: argparse.Namespace) -> int:
    """Export a validation runway projection for a run group."""

    conn = initialize(connect(args.db))
    write_or_print(export_validation_runway(conn, run_group=args.run_group), args.output)
    return 0


def export_proof(args: argparse.Namespace) -> int:
    """Export a proof packet projection for a run group."""

    conn = initialize(connect(args.db))
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

    proof = subparsers.add_parser(
        "proof",
        help="proof packet commands",
        description="Proof packet commands.",
    )
    proof_subparsers = proof.add_subparsers(dest="proof_command", metavar="command", required=True)
    _add_proof_export_command(proof_subparsers)


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
