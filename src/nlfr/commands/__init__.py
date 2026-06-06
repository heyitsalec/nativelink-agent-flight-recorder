"""Command registry for the nlfr CLI."""

from __future__ import annotations

import argparse

from nlfr.commands import compare_cmd
from nlfr.commands import doctor
from nlfr.commands import export_cmds
from nlfr.commands import ingest_cmd
from nlfr.commands import init_cmd
from nlfr.commands import run_cmd
from nlfr.commands import serve_cmd
from nlfr.commands import simulate_cmd


def register_commands(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    init_cmd.register(subparsers)
    doctor.register(subparsers)
    run_cmd.register(subparsers)
    ingest_cmd.register(subparsers)
    export_cmds.register(subparsers)
    compare_cmd.register(subparsers)
    serve_cmd.register(subparsers)
    simulate_cmd.register(subparsers)
