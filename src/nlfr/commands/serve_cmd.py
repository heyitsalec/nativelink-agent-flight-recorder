"""Local projection server command shell."""

from __future__ import annotations

import argparse

from nlfr.commands.common import not_implemented


def run(args: argparse.Namespace) -> int:
    return not_implemented(args, "local projection server is pending the canvas consumer workstream")


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "serve",
        help="serve exported projection JSON locally",
        description="Serve exported projection JSON locally.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="bind host")
    parser.add_argument("--port", type=int, default=8080, help="bind port")
    parser.set_defaults(handler=run)
