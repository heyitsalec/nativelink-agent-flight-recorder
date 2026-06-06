"""Projection export commands."""

from __future__ import annotations

import argparse

from nlfr.db import connect, initialize
from nlfr.projectors import (
    export_action_graph,
    export_proof_packet,
    export_validation_runway,
)
from nlfr.projectors.common import write_or_print


def export_graph(args: argparse.Namespace) -> int:
    conn = initialize(connect(args.db))
    write_or_print(export_action_graph(conn, run_group=args.run_group), args.output)
    return 0


def export_runway(args: argparse.Namespace) -> int:
    conn = initialize(connect(args.db))
    write_or_print(export_validation_runway(conn, run_group=args.run_group), args.output)
    return 0


def export_proof(args: argparse.Namespace) -> int:
    conn = initialize(connect(args.db))
    write_or_print(export_proof_packet(conn, run_group=args.run_group), args.output)
    return 0


def add_export_command(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    name: str,
    handler: object,
    help_text: str,
) -> None:
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
    add_export_command(proof_subparsers, "export", export_proof, "export proof packet JSON")
