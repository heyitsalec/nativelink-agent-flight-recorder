"""`nlfr loop` — native evaluate → fix → revalidate loop driver."""

from __future__ import annotations

import argparse

from nlfr.commands.common import not_implemented


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``loop`` subcommand."""

    parser = subparsers.add_parser(
        "loop",
        help="drive the evaluate → fix → revalidate loop natively",
        description="Drive the evaluate → fix → revalidate loop natively.",
    )
    parser.set_defaults(handler=not_implemented)
