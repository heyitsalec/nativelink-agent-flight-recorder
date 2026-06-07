"""Multi-run compare commands."""

from __future__ import annotations

import argparse
import json
import sys

from nlfr.db import connect, initialize
from nlfr.projectors.common import run_rows, write_or_print
from nlfr.projectors.compare import (
    build_compare_projection,
    export_compare_projection,
    list_run_group_index,
)
from nlfr.projectors.proof import export_proof_packet


def export_compare(args: argparse.Namespace) -> int:
    """Export a compare projection for two run groups."""

    if args.left_db or args.right_db:
        if not (args.left_db and args.right_db):
            print(
                "error: --left-db and --right-db must both be set",
                file=sys.stderr,
            )
            return 2
        left_conn = initialize(connect(args.left_db))
        right_conn = initialize(connect(args.right_db))
        left_proof = export_proof_packet(left_conn, run_group=args.left)
        right_proof = export_proof_packet(right_conn, run_group=args.right)
        left_runs = run_rows(left_conn, args.left)
        right_runs = run_rows(right_conn, args.right)
        payload = build_compare_projection(
            left_proof,
            right_proof,
            args.left,
            args.right,
            left_runs=left_runs,
            right_runs=right_runs,
        )
    else:
        conn = initialize(connect(args.db))
        payload = export_compare_projection(conn, args.left, args.right)
    write_or_print(payload, args.output)
    return 0


def index_run_groups(args: argparse.Namespace) -> int:
    """List distinct run groups and run counts from SQLite."""

    conn = initialize(connect(args.db))
    groups = list_run_group_index(conn)
    payload = {
        "schema_version": 1,
        "kind": "run_group_index",
        "db": args.db,
        "run_groups": groups,
        "count": len(groups),
    }
    output_format = "json" if args.json else args.format
    if output_format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        if not groups:
            print("no run groups recorded")
            return 0
        for item in groups:
            print(
                f"{item['run_group']}\t{item['run_count']}\t"
                f"{item.get('last_started_at') or 'unknown'}"
            )
    return 0


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register ``compare`` subcommands on ``subparsers``."""

    parser = subparsers.add_parser(
        "compare",
        help="compare recorded run groups",
        description="Compare proof packet summaries across run groups.",
    )
    compare_subparsers = parser.add_subparsers(
        dest="compare_command",
        metavar="command",
        required=True,
    )

    export_parser = compare_subparsers.add_parser(
        "export",
        help="export compare projection JSON",
        description="Export a compare projection for two run groups.",
    )
    export_parser.add_argument(
        "--db",
        default="data/nlfr/nlfr.sqlite",
        help="SQLite database path when both run groups live in one DB",
    )
    export_parser.add_argument(
        "--left-db",
        help="SQLite database path for the left run group",
    )
    export_parser.add_argument(
        "--right-db",
        help="SQLite database path for the right run group",
    )
    export_parser.add_argument(
        "--left",
        required=True,
        help="left run group id",
    )
    export_parser.add_argument(
        "--right",
        required=True,
        help="right run group id",
    )
    export_parser.add_argument(
        "--output",
        help="output path for compare projection JSON",
    )
    export_parser.set_defaults(handler=export_compare)

    index_parser = compare_subparsers.add_parser(
        "index",
        help="list distinct run groups with run counts",
        description="Retention index of recorded run groups.",
    )
    index_parser.add_argument(
        "--db",
        default="data/nlfr/nlfr.sqlite",
        help="SQLite database path",
    )
    index_parser.add_argument(
        "--format",
        choices=("json", "table"),
        default="table",
        help="output format (default: table)",
    )
    index_parser.add_argument(
        "--json",
        action="store_true",
        help="emit JSON instead of tab-separated rows (alias for --format json)",
    )
    index_parser.set_defaults(handler=index_run_groups)
