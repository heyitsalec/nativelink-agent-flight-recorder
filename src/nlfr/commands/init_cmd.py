"""Project initialization command."""

from __future__ import annotations

import argparse

from nlfr.commands.common import not_implemented


def run(args: argparse.Namespace) -> int:
    return not_implemented(args, "project metadata layout is pending the data-spine workstream")


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "init",
        help="initialize recorder metadata for a workspace",
        description="Initialize recorder metadata for a workspace.",
    )
    parser.set_defaults(handler=run)
