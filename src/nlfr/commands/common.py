"""Shared helpers for CLI command modules."""

from __future__ import annotations

import argparse
import sys


def not_implemented(args: argparse.Namespace, detail: str) -> int:
    """Emit a consistent placeholder message for unimplemented commands."""

    print(f"nlfr {args.command}: not yet implemented - {detail}", file=sys.stderr)
    return 1
