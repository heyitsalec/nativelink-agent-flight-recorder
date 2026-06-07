"""Multi-run compare commands."""

from __future__ import annotations

import argparse
import json
import sys

from nlfr.db import connect, initialize
from nlfr.projectors.common import write_or_print
from nlfr.projectors.compare import export_compare_projection, list_run_group_index


def export_compare(args: argparse.Namespace) -> int:
    conn = initialize(connect(args.db))
    payload = export_compare_projection(conn, args.left, args.right)
    write_or_print(payload, args.output)
    return 0


def index_run_groups(args: argparse.Namespace) -> int:
    conn = initialize(connect(args.db))
    groups = list_run_group_index(conn)
    payload = {
        "schema_version": 1,
        "kind": "run_group_index",
        "db": args.db,
        "run_groups": groups,
        "count": len(groups),
    }
    if args.json:
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
        help="SQLite database path",
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
        "--json",
        action="store_true",
        help="emit JSON instead of tab-separated rows",
    )
    index_parser.set_defaults(handler=index_run_groups)
