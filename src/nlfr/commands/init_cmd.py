"""Project initialization command."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from nlfr.commands.doctor import ADOPTION_GUIDE, ADOPTION_HINT, DEV_ENVIRONMENT, FIRST_EVIDENCE_LOOP
from nlfr.config import resolve_defaults, scaffold_workspace


def run(args: argparse.Namespace) -> int:
    """Scaffold NLFR workspace metadata and local data directories."""

    cwd = Path(args.cwd).resolve()
    defaults = resolve_defaults(
        cwd,
        workspace=args.workspace,
        output_dir=args.output_dir,
        database=args.database,
        run_group=args.run_group,
    )
    result = scaffold_workspace(cwd, defaults, force=args.force)

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif result["idempotent"]:
        print("nlfr init: already initialized")
        print(f"config: {result['paths']['config']}")
        print(f"database: {result['paths']['database']}")
        print(f"workspace: {defaults.workspace}")
        print(f"run_group: {defaults.run_group}")
        _print_next_steps()
    else:
        print("nlfr init: scaffold created")
        for path in result["created"]:
            print(f"  + {path}")
        print(f"workspace: {defaults.workspace}")
        print(f"database: {result['paths']['database']}")
        print(f"run_group: {defaults.run_group}")
        _print_next_steps()

    return 0


def _print_next_steps() -> None:
    print("next: nlfr doctor --mode cache-only")
    print(f"  → adoption walkthrough: {FIRST_EVIDENCE_LOOP}")
    print(f"  → toolchain setup: {DEV_ENVIRONMENT}")
    print(f"  → overview: {ADOPTION_GUIDE}")
    print(f"  → {ADOPTION_HINT}")


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``init`` command on ``subparsers``."""

    parser = subparsers.add_parser(
        "init",
        help="initialize recorder metadata for a workspace",
        description=(
            "Create nlfr.toml plus data/.nlfr/ scaffold with workspace, database, "
            "and run-group defaults. Safe to run repeatedly."
        ),
    )
    parser.add_argument(
        "--cwd",
        default=".",
        help="workspace root to initialize (default: current directory)",
    )
    parser.add_argument(
        "--workspace",
        help="Bazel workspace path relative to --cwd (default: demo/bazel-monorepo when present)",
    )
    parser.add_argument(
        "--output-dir",
        help="directory for SQLite and run artifacts (default: data/nlfr)",
    )
    parser.add_argument(
        "--database",
        help="SQLite database path relative to --cwd (default: <output-dir>/nlfr.sqlite)",
    )
    parser.add_argument(
        "--run-group",
        help="default run-group label for exporters (default: latest)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="rewrite nlfr.toml and data/.nlfr/init.json when content differs",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit machine-readable scaffold metadata",
    )
    parser.set_defaults(handler=run)
