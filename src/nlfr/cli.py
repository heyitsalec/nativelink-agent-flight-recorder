"""Command-line shell for NativeLink Agent Flight Recorder."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from nlfr.commands import register_commands


DESCRIPTION = "NativeLink Agent Flight Recorder"


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level ``nlfr`` argument parser and subcommands."""

    parser = argparse.ArgumentParser(
        prog="nlfr",
        description=DESCRIPTION,
    )
    parser.add_argument(
        "--version",
        action="version",
        version="nlfr 0.3.0",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        metavar="command",
        required=True,
    )
    register_commands(subparsers)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse CLI arguments and dispatch to the selected command handler."""

    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.error("command has no handler")
    return int(handler(args))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
