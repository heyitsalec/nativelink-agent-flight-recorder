"""``nlfr redact`` — scrub secrets/PII from projection JSON before you share it.

Thin, packaged CLI over :mod:`nlfr.redaction`, behaviourally identical to the
repo-side ``scripts/redact-projection.py`` (which predates this command). That
script is a dev-tree helper that never shipped in the wheel; this subcommand is
the adopter-facing entry point, so an operator who installs nlfr gets the same
defense-in-depth redaction the repo uses.

Modes
-----
default (redact + write)::

    nlfr redact INPUT.json OUTPUT.json

    Scrubs INPUT, writes redacted JSON to OUTPUT (2-space indent, sorted keys),
    honestly upgrades ``redaction_state`` where a redaction occurred, and prints
    a one-line summary of replacements by detector.

check (scan only, share/CI gate)::

    nlfr redact --check INPUT.json

    Scans INPUT and writes nothing. Exits 1 if any secret/PII shape is found,
    printing a report (detector, JSON path, masked excerpt — never the raw
    secret). Exits 0 when clean.

This is defense-in-depth pattern matching, **not** a guarantee: a free-standing
high-entropy secret with no prefix and no contextual marker is not detectable by
regex without false-positiving over this corpus's SHA digests. See the module
docstring in ``src/nlfr/redaction.py``. PII tier: email + ipv4 are redacted by
default (``--no-pii`` / ``--no-email`` / ``--no-ip`` to disable); ``hostname`` is
opt-in (``--hostname``) because FQDN shapes collide with tool/file names here.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from nlfr.redaction import RedactionConfig, dumps, redact_payload


def _config_from_args(args: argparse.Namespace, *, redact: bool) -> RedactionConfig:
    return RedactionConfig(
        redact=redact,
        enable_email=not (args.no_pii or args.no_email),
        enable_ip=not (args.no_pii or args.no_ip),
        enable_hostname=args.hostname,
    )


def _summary(counts) -> str:
    if not counts:
        return "no secrets detected (0 replacements)"
    parts = ", ".join(f"{name}={count}" for name, count in sorted(counts.items()))
    total = sum(counts.values())
    return f"redacted {total} span(s): {parts}"


def redact(args: argparse.Namespace) -> int:
    """Scan (``--check``) or scrub a projection JSON file over :mod:`nlfr.redaction`."""

    try:
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"nlfr redact: no such file: {args.input}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"nlfr redact: {args.input} is not valid JSON: {exc}", file=sys.stderr)
        return 2

    if args.check:
        result = redact_payload(payload, _config_from_args(args, redact=False))
        if result.findings:
            print(
                f"nlfr redact --check: {len(result.findings)} finding(s) in {args.input}",
                file=sys.stderr,
            )
            for finding in result.findings:
                print(finding.format_line(), file=sys.stderr)
            return 1
        print(f"nlfr redact --check: OK, no findings in {args.input}")
        return 0

    if args.output is None:
        print(
            "usage: nlfr redact INPUT OUTPUT (or nlfr redact --check INPUT)",
            file=sys.stderr,
        )
        return 2

    result = redact_payload(payload, _config_from_args(args, redact=True))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps(result.payload), encoding="utf-8")
    print(_summary(result.counts))
    return 0


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``redact`` command on ``subparsers``."""

    parser = subparsers.add_parser(
        "redact",
        help="scrub secrets/PII from projection JSON before sharing",
        description=(
            "Scrub secrets/PII from a projection JSON before you attach it to a "
            "PR or dashboard. Defense-in-depth, not a guarantee — review "
            "sensitive evidence at the source too."
        ),
    )
    parser.add_argument("input", type=Path, help="projection JSON to scan/redact")
    parser.add_argument(
        "output",
        type=Path,
        nargs="?",
        default=None,
        help="destination JSON (required unless --check)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="scan only; write nothing; exit 1 if any secret/PII shape is found",
    )
    parser.add_argument(
        "--no-pii",
        action="store_true",
        help="disable the default PII detectors (email + ipv4)",
    )
    parser.add_argument("--no-email", action="store_true", help="disable the email detector")
    parser.add_argument("--no-ip", action="store_true", help="disable the IPv4 detector")
    parser.add_argument(
        "--hostname",
        action="store_true",
        help="opt in to hostname redaction (off by default: FQDN shapes collide "
        "with tool/file names like record-agent-change.sh in this corpus)",
    )
    parser.set_defaults(handler=redact)
