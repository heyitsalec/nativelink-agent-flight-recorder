"""`nlfr receipt` — agent-receipt commands (import)."""

from __future__ import annotations

import argparse

from nlfr.commands.common import not_implemented


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``receipt`` command group."""

    parser = subparsers.add_parser(
        "receipt",
        help="agent receipt commands",
        description="Agent receipt commands.",
    )
    receipt_subparsers = parser.add_subparsers(
        dest="receipt_command", metavar="command", required=True
    )
    import_parser = receipt_subparsers.add_parser(
        "import",
        help="import an externally produced agent receipt",
        description="Import an externally produced agent receipt.",
    )
    import_parser.set_defaults(handler=not_implemented)
