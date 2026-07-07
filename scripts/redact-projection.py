#!/usr/bin/env python3
"""Redact secrets from projection JSON before it is committed / published.

This is a thin CLI over :mod:`nlfr.redaction`. It keeps the original
home-path scrubbing (``/Users/<name>`` / ``/home/<name>`` -> ``${HOME}``) and
adds a registry of named secret detectors plus a toggleable PII tier.

Modes
-----
default (redact + write)::

    redact-projection.py INPUT.json OUTPUT.json

    Scrubs INPUT, writes the redacted JSON to OUTPUT (2-space indent, sorted
    keys), upgrades ``redaction_state`` honestly where a redaction occurred, and
    prints a one-line summary of replacements by detector. Backward compatible
    with every existing caller.

check (scan only, CI gate)::

    redact-projection.py --check INPUT.json

    Scans INPUT and writes nothing. Exits 1 if any secret/PII shape is found,
    printing a report (detector, JSON path, masked excerpt -- never the raw
    secret). Exits 0 when clean.

Detectors
---------
Secret tier (always on): home_path, private_key_pem, aws_access_key_id,
aws_secret_access_key (under a credential-ish key *or* introduced by an in-text
``secret_access_key=…`` marker; never a bare hex digest, upper- or lowercase),
github_token (classic ``gh[pousr]_``), github_pat (fine-grained
``github_pat_``), gitlab_pat, slack_token, jwt, url_credentials,
authorization_credential.

This is defense-in-depth pattern matching, **not** a guarantee: a free-standing
high-entropy secret with no prefix and no contextual marker is not detectable by
regex without false-positiving over this corpus's SHA digests. See the module
docstring in ``src/nlfr/redaction.py`` and the redaction section of
``docs/wiki/reference/truth-labels.md``.

PII tier: email (on; --no-email) and ipv4 (on, loopback/link-local excluded;
--no-ip) are redacted by default. hostname is **opt-in** (--hostname): in this
corpus FQDN shapes collide with tool/file names (record-agent-change.sh,
receipt.v1), so default-on hostname redaction would block honest publishes
rather than protect anything. ``--no-pii`` disables the default email + ipv4.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow ``python3 scripts/redact-projection.py`` (no PYTHONPATH) to import the
# package: record-canvas-build.sh invokes this with a plain interpreter.
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from nlfr.redaction import RedactionConfig, dumps, redact_payload  # noqa: E402

import json  # noqa: E402


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="redact-projection.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
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
    return parser


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


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"redact-projection: no such file: {args.input}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"redact-projection: {args.input} is not valid JSON: {exc}", file=sys.stderr)
        return 2

    if args.check:
        result = redact_payload(payload, _config_from_args(args, redact=False))
        if result.findings:
            print(
                f"redact-projection --check: {len(result.findings)} finding(s) in {args.input}",
                file=sys.stderr,
            )
            for finding in result.findings:
                print(finding.format_line(), file=sys.stderr)
            return 1
        print(f"redact-projection --check: OK, no findings in {args.input}")
        return 0

    if args.output is None:
        print("usage: redact-projection.py INPUT.json OUTPUT.json", file=sys.stderr)
        return 2

    result = redact_payload(payload, _config_from_args(args, redact=True))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(dumps(result.payload), encoding="utf-8")
    print(_summary(result.counts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
