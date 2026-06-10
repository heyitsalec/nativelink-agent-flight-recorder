"""Headless Claude Code invocation with verifiable receipt capture.

``nlfr agent-invoke`` runs ``claude -p <prompt> --output-format json`` with
stdin closed, captures the response text to a file, and writes a receipt
artifact (``nlfr.agent_receipt.v1``) carrying the server-resolved model id,
session id, token usage, response SHA-256, prompt SHA-256, timestamp, and CLI
version. The raw prompt is read from ``--prompt-file``, hashed, and never
written to any output, log, or artifact.

The invocation cwd defaults to a fresh empty scratch directory so the agent
cannot read workspace files (including hidden validation tests) through tools.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from nlfr.agent_receipt import build_receipt, receipt_sha256, sha256_text

PROMPT_PLACEHOLDER = "<prompt:sha256>"


def run(args: argparse.Namespace) -> int:
    """Invoke the headless CLI and write receipt + response outputs."""

    prompt_path = Path(args.prompt_file)
    if not prompt_path.is_file():
        print(f"error: prompt file not found: {prompt_path}", file=sys.stderr)
        return 2
    prompt_text = prompt_path.read_text(encoding="utf-8")
    prompt_sha = sha256_text(prompt_text)

    cli_name = Path(args.claude_bin).name
    cli_version = _cli_version(args.claude_bin)

    command = [args.claude_bin, "-p", prompt_text, "--output-format", "json"]
    sanitized_command = [args.claude_bin, "-p", PROMPT_PLACEHOLDER, "--output-format", "json"]
    if args.model:
        command.extend(["--model", args.model])
        sanitized_command.extend(["--model", args.model])
    for extra in args.claude_arg:
        command.append(extra)
        sanitized_command.append(extra)

    cwd = Path(args.cwd).resolve() if args.cwd else Path(tempfile.mkdtemp(prefix="nlfr-agent-scratch."))
    cwd.mkdir(parents=True, exist_ok=True)

    status = "success"
    detail: str | None = None
    cli_result: dict | None = None
    try:
        proc = subprocess.run(
            command,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            text=True,
            capture_output=True,
            timeout=args.timeout,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        status = "environment_blocker"
        detail = f"{type(exc).__name__}: CLI invocation did not complete"
        proc = None

    if proc is not None:
        try:
            cli_result = json.loads(proc.stdout)
        except json.JSONDecodeError:
            cli_result = None
        if cli_result is None:
            status = "invalid_output"
            detail = (
                f"CLI exit code {proc.returncode}; stdout was not JSON"
                if proc.returncode != 0
                else "CLI stdout was not JSON"
            )
        elif cli_result.get("is_error") or proc.returncode != 0:
            status = "api_error" if cli_result.get("api_error_status") else "cli_error"
            detail = _sanitize_detail(cli_result, prompt_text)

    receipt = build_receipt(
        cli_result=cli_result,
        prompt_sha256=prompt_sha,
        cli_name=cli_name,
        cli_version=cli_version,
        requested_model=args.model or None,
        sanitized_command=sanitized_command,
        status=status,
        detail=detail,
    )

    receipt_path = Path(args.receipt_output)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    response_path: Path | None = None
    if status == "success" and isinstance(cli_result, dict):
        response_text = cli_result.get("result") or ""
        response_path = Path(args.response_output)
        response_path.parent.mkdir(parents=True, exist_ok=True)
        response_path.write_text(response_text, encoding="utf-8")

    summary = {
        "status": status,
        "receipt_path": str(receipt_path),
        "receipt_sha256": receipt_sha256(receipt),
        "response_path": str(response_path) if response_path else None,
        "prompt_sha256": prompt_sha,
        "response_sha256": receipt.get("response_sha256"),
        "session_id": receipt.get("session_id"),
        "model_resolved": receipt.get("model", {}).get("resolved"),
        "cli_version": cli_version,
        "detail": detail,
        "source_kind": receipt["source_kind"],
        "confidence": receipt["confidence"],
        "redaction_state": "redacted",
    }
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"agent-invoke {status}: receipt {receipt_path}")
        if detail:
            print(f"detail: {detail}")

    return 0 if status == "success" else 3


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``agent-invoke`` command on ``subparsers``."""

    parser = subparsers.add_parser(
        "agent-invoke",
        help="run headless Claude Code and capture a verifiable receipt",
        description=(
            "Run claude -p with a prompt file and capture a receipt artifact. "
            "The raw prompt is hashed and never stored."
        ),
    )
    parser.add_argument(
        "--prompt-file",
        required=True,
        help="prompt text file; hashed locally, never stored or exported",
    )
    parser.add_argument(
        "--receipt-output",
        required=True,
        help="path for the nlfr.agent_receipt.v1 JSON receipt",
    )
    parser.add_argument(
        "--response-output",
        required=True,
        help="path for the agent response text (code; allowed to be stored)",
    )
    parser.add_argument(
        "--claude-bin",
        default="claude",
        help="Claude Code CLI executable (default: claude)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="optional model request passed to the CLI; receipt records the server-resolved id",
    )
    parser.add_argument(
        "--cwd",
        default=None,
        help="invocation cwd; defaults to a fresh empty scratch dir so workspace files stay hidden",
    )
    parser.add_argument(
        "--claude-arg",
        action="append",
        default=[],
        help="extra argument passed through to the CLI; repeatable",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=600.0,
        help="seconds before the invocation is recorded as an environment blocker",
    )
    parser.add_argument("--json", action="store_true", help="emit machine-readable summary")
    parser.set_defaults(handler=run)


def _cli_version(claude_bin: str) -> str | None:
    try:
        proc = subprocess.run(
            [claude_bin, "--version"],
            stdin=subprocess.DEVNULL,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    version = proc.stdout.strip() or proc.stderr.strip()
    return version or None


def _sanitize_detail(cli_result: dict, prompt_text: str) -> str:
    """Build a failure detail string guaranteed not to leak the prompt."""

    raw = str(cli_result.get("result") or cli_result.get("subtype") or "unknown CLI error")
    if prompt_text and prompt_text.strip() and prompt_text.strip() in raw:
        return "CLI error detail withheld: overlapped with prompt text"
    return raw[:400]
