"""Command registry for the nlfr CLI."""

from __future__ import annotations

import argparse

from nlfr.commands import agent_invoke_cmd
from nlfr.commands import compare_cmd
from nlfr.commands import db_cmd
from nlfr.commands import doctor
from nlfr.commands import export_cmds
from nlfr.commands import ingest_cmd
from nlfr.commands import init_cmd
from nlfr.commands import record_cmd
from nlfr.commands import redact_cmd
from nlfr.commands import run_cmd
from nlfr.commands import serve_cmd
from nlfr.commands import simulate_cmd


def register_commands(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register all nlfr CLI subcommands on ``subparsers``."""

    init_cmd.register(subparsers)
    doctor.register(subparsers)
    agent_invoke_cmd.register(subparsers)
    run_cmd.register(subparsers)
    record_cmd.register(subparsers)
    redact_cmd.register(subparsers)
    ingest_cmd.register(subparsers)
    export_cmds.register(subparsers)
    compare_cmd.register(subparsers)
    db_cmd.register(subparsers)
    serve_cmd.register(subparsers)
    simulate_cmd.register(subparsers)
