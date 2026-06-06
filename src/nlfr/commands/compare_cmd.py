"""Proof comparison command shell."""

from __future__ import annotations

import argparse

from nlfr.commands.common import not_implemented


def run(args: argparse.Namespace) -> int:
    return not_implemented(args, "comparison needs proof packet exports from recorded runs")


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "compare",
        help="compare two recorded proof packets",
        description="Compare two recorded proof packets.",
    )
    parser.add_argument("left", nargs="?", help="left proof packet JSON")
    parser.add_argument("right", nargs="?", help="right proof packet JSON")
    parser.set_defaults(handler=run)
