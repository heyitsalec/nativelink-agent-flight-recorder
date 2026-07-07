"""``nlfr redact`` — scrub secrets/PII before you share evidence, three shapes.

Thin, packaged CLI over :mod:`nlfr.redaction`. An operator who installs nlfr gets
the same defense-in-depth redaction the repo uses — over a **JSON projection**, a
**plain-text log**, or a whole **evidence directory**.

Modes
-----
JSON / text file (auto-detected)::

    nlfr redact --check INPUT            # scan only; exit 1 on any finding
    nlfr redact INPUT OUTPUT             # write a scrubbed copy

    A single file is parsed as JSON when it parses, else scanned as PLAIN TEXT
    with the *same* detector registry (string-level spans; no JSON walk; text
    carries no ``redaction_state`` labels). ``--format json|text`` overrides the
    auto-detect. This is what lets ``--check`` gate a raw ``bazel.stdout.txt`` —
    the file type where build-output secrets actually land (issue #71) — instead
    of refusing every non-JSON file.

directory / tree (``INPUT`` is a directory)::

    nlfr redact --check EVIDENCE_DIR     # recursively scan every regular file
    nlfr redact EVIDENCE_DIR OUT_DIR     # write a redacted mirror

    Every regular file is scanned (check) or copied-and-redacted (write), each
    honoring the JSON/text auto-detect. Binaries are skipped honestly (null-byte
    sniff → reported ``skipped:binary`` — a secret in a binary is out of scope,
    and the report SAYS so) and SQLite databases are skipped as
    ``skipped:database`` (local evidence, not meant for upload). **Symlinks are
    never followed** — a directory or file link (at any depth) is reported as
    ``skipped:symlink`` and left out of the scan and the written mirror: an alias
    would double-count evidence and a link can smuggle out-of-scope filesystem
    content into a tree told to be "safe to share". Pass the real path explicitly
    if you mean to include it. ``--check`` exits 1 if ANY file has a finding;
    skips never fail the gate on their own (but the report always makes the
    non-scan visible).

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
from collections import Counter
from pathlib import Path

from nlfr.redaction import (
    RedactionConfig,
    RedactionResult,
    dumps,
    is_binary_bytes,
    is_sqlite_bytes,
    redact_payload,
    redact_text,
)

_SKIP_BINARY = "binary"
_SKIP_DATABASE = "database"
_SKIP_SYMLINK = "symlink"

_SKIP_NOTE = {
    _SKIP_BINARY: "binary — not scanned; a secret in a binary is out of scope",
    _SKIP_DATABASE: (
        "SQLite database — local evidence, not meant for upload; not scanned"
    ),
    _SKIP_SYMLINK: (
        "symlink — never followed; an alias would double-count evidence and a "
        "link can smuggle out-of-scope content into a shared mirror. Pass the "
        "real path explicitly if intended"
    ),
}


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


def _classify(data: bytes, fmt: str | None) -> str:
    """Decide how to treat a file's raw bytes: json / text / binary / database.

    The binary/DB *safety sniff always runs first* and outranks ``--format``: a
    SQLite database or a NUL-carrying binary is skipped honestly whatever the
    operator forced, because ``--format text`` over ``nlfr.sqlite`` would decode
    the database with ``errors="replace"`` and re-encode a CORRUPTED copy into
    the "safe" mirror (issue: ``--help`` promises "binaries and SQLite databases
    are always skipped"). ``--format`` only disambiguates text-vs-json for the
    files that pass the sniff; auto-detect (no ``--format``) is JSON when it
    parses, else plain text.
    """

    if is_sqlite_bytes(data):
        return _SKIP_DATABASE
    if is_binary_bytes(data):
        return _SKIP_BINARY
    if fmt == "json":
        return "json"
    if fmt == "text":
        return "text"
    text = data.decode("utf-8", errors="replace")
    try:
        json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return "text"
    return "json"


def _scan_bytes(
    data: bytes, kind: str, config: RedactionConfig
) -> tuple[RedactionResult, str]:
    """Redact one file's bytes as ``kind`` (json|text); return (result, serialized).

    ``serialized`` is the write-mode output body: canonical JSON for a JSON file,
    the redacted text otherwise. Raises :class:`json.JSONDecodeError` only when
    ``kind == "json"`` and the bytes do not parse (a forced ``--format json``).
    """

    text = data.decode("utf-8", errors="replace")
    if kind == "json":
        result = redact_payload(json.loads(text), config)
        return result, dumps(result.payload)
    result = redact_text(text, config)
    serialized = result.payload if isinstance(result.payload, str) else text
    return result, serialized


def redact(args: argparse.Namespace) -> int:
    """Scan (``--check``) or scrub a file or directory over :mod:`nlfr.redaction`."""

    target = Path(args.input)
    if target.is_dir():
        return _redact_tree(args, target)
    return _redact_file(args, target)


# --------------------------------------------------------------------------- file


def _redact_file(args: argparse.Namespace, path: Path) -> int:
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        print(f"nlfr redact: no such file: {path}", file=sys.stderr)
        return 2

    kind = _classify(data, args.format)
    if kind in _SKIP_NOTE:
        # A single file the operator explicitly named but we cannot scan: report
        # honestly (never silently), and don't claim a clean gate we didn't run.
        print(f"nlfr redact: skipped {path} ({_SKIP_NOTE[kind]}).", file=sys.stderr)
        return 0

    if args.check:
        config = _config_from_args(args, redact=False)
        try:
            result, _ = _scan_bytes(data, kind, config)
        except json.JSONDecodeError as exc:
            print(f"nlfr redact: {path} is not valid JSON: {exc}", file=sys.stderr)
            return 2
        if result.findings:
            print(
                f"nlfr redact --check: {len(result.findings)} finding(s) in {path}",
                file=sys.stderr,
            )
            for finding in result.findings:
                print(finding.format_line(), file=sys.stderr)
            return 1
        print(f"nlfr redact --check: OK, no findings in {path}")
        return 0

    if args.output is None:
        print(
            "usage: nlfr redact INPUT OUTPUT (or nlfr redact --check INPUT)",
            file=sys.stderr,
        )
        return 2

    config = _config_from_args(args, redact=True)
    try:
        result, serialized = _scan_bytes(data, kind, config)
    except json.JSONDecodeError as exc:
        print(f"nlfr redact: {path} is not valid JSON: {exc}", file=sys.stderr)
        return 2
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(serialized, encoding="utf-8")
    print(_summary(result.counts))
    return 0


# --------------------------------------------------------------------------- tree


def _has_symlink_ancestor(rel: Path, root: Path) -> bool:
    """True when any *ancestor directory* of ``root / rel`` (below root) is a link.

    Defense in depth so behaviour is identical across Python versions: even if a
    future ``rglob`` were to descend through a directory symlink (the
    ``follow_symlinks`` default has drifted across 3.12/3.13/3.14), an entry that
    lives *under* a symlinked directory is silently ignored here — the link
    itself is already reported once as ``skipped:symlink``; its subtree is never
    scanned, read, or copied.
    """

    cur = root
    for part in rel.parts[:-1]:  # ancestors only — never the leaf itself
        cur = cur / part
        if cur.is_symlink():
            return True
    return False


def _walk_tree(root: Path) -> tuple[list[Path], list[Path]]:
    """Return ``(files, symlinks)`` under ``root`` — links reported, never followed.

    ``root.rglob("*")`` in current pathlib does not descend into a directory
    symlink, but it DOES list the link entry, and a *file* symlink still satisfies
    ``is_file()`` — so the old ``if p.is_file()`` filter silently dropped a
    directory link (its content, reachable only through the alias, was never
    scanned: a false-clean gate) while FOLLOWING a file link (reading, and in
    write mode copying, out-of-scope target content into the "safe" mirror).

    This walk reports every symlink (directory or file, at any depth) exactly once
    as a ``skipped:symlink`` entry and never traverses, reads, or copies it. The
    :func:`_has_symlink_ancestor` guard makes the non-follow guarantee independent
    of pathlib's version-drifting ``follow_symlinks`` default.
    """

    files: list[Path] = []
    symlinks: list[Path] = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if path.is_symlink():
            symlinks.append(rel)
            continue
        if _has_symlink_ancestor(rel, root):
            continue
        if path.is_file():
            files.append(path)
    return files, symlinks


def _redact_tree(args: argparse.Namespace, root: Path) -> int:
    """Scan (check) or copy-and-redact (write) every regular file under ``root``.

    Symlinks are never followed: they are reported as ``skipped:symlink`` and
    excluded from both the scan and the written mirror (which therefore contains
    zero symlinks). Binaries and SQLite databases are likewise reported-and-
    skipped. Skips never fail the ``--check`` gate on their own, but the report
    always makes the non-scan visible.
    """

    check = args.check
    if not check and args.output is None:
        print(
            "usage: nlfr redact DIR OUTPUT_DIR (or nlfr redact --check DIR)",
            file=sys.stderr,
        )
        return 2

    out_root = Path(args.output) if args.output is not None else None
    config = _config_from_args(args, redact=not check)
    files, symlinks = _walk_tree(root)

    findings_by_file: list[tuple[Path, str, RedactionResult]] = []
    skipped: dict[str, list[Path]] = {
        _SKIP_BINARY: [],
        _SKIP_DATABASE: [],
        _SKIP_SYMLINK: list(symlinks),
    }
    parse_errors: list[tuple[Path, str]] = []
    wrote = {"json": 0, "text": 0}
    total = Counter()

    for path in files:
        rel = path.relative_to(root)
        data = path.read_bytes()
        kind = _classify(data, args.format)
        if kind in skipped:
            skipped[kind].append(rel)
            continue
        try:
            result, serialized = _scan_bytes(data, kind, config)
        except json.JSONDecodeError as exc:
            # Only reachable when --format json is FORCED over a non-JSON file.
            parse_errors.append((rel, str(exc)))
            continue
        total.update(result.counts)
        if check:
            if result.findings:
                findings_by_file.append((rel, kind, result))
        else:
            dest = out_root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(serialized, encoding="utf-8")
            wrote[kind] += 1

    if check:
        return _emit_tree_check(root, len(files), findings_by_file, skipped, parse_errors)
    return _emit_tree_write(out_root, wrote, skipped, total, parse_errors)


def _emit_tree_check(
    root: Path,
    scanned: int,
    findings_by_file: list[tuple[Path, str, RedactionResult]],
    skipped: dict[str, list[Path]],
    parse_errors: list[tuple[Path, str]],
) -> int:
    failed = bool(findings_by_file) or bool(parse_errors)
    stream = sys.stderr if failed else sys.stdout
    print(
        f"nlfr redact --check: scanned {scanned} file(s) under {root} — "
        f"{len(findings_by_file)} with finding(s), "
        f"{len(skipped[_SKIP_BINARY])} binary skipped, "
        f"{len(skipped[_SKIP_DATABASE])} database skipped, "
        f"{len(skipped[_SKIP_SYMLINK])} symlink skipped.",
        file=stream,
    )
    for rel, kind, result in findings_by_file:
        print(f"  {rel} [{kind}]: {len(result.findings)} finding(s)", file=sys.stderr)
        for finding in result.findings:
            print("  " + finding.format_line(), file=sys.stderr)
    for rel, exc in parse_errors:
        print(
            f"  {rel}: forced --format json but not valid JSON: {exc}",
            file=sys.stderr,
        )
    for kind in (_SKIP_BINARY, _SKIP_DATABASE, _SKIP_SYMLINK):
        if skipped[kind]:
            print(f"skipped:{kind} ({_SKIP_NOTE[kind]}):", file=stream)
            for rel in skipped[kind]:
                print(f"  {rel}", file=stream)
    return 1 if failed else 0


def _emit_tree_write(
    out_root: Path,
    wrote: dict[str, int],
    skipped: dict[str, list[Path]],
    total: Counter,
    parse_errors: list[tuple[Path, str]],
) -> int:
    spans = sum(total.values())
    parts = ", ".join(f"{n}={c}" for n, c in sorted(total.items())) or "none"
    print(
        f"nlfr redact: wrote {wrote['json'] + wrote['text']} redacted file(s) to "
        f"{out_root} ({wrote['json']} json, {wrote['text']} text); "
        f"redacted {spans} span(s) [{parts}]; skipped "
        f"{len(skipped[_SKIP_BINARY])} binary, {len(skipped[_SKIP_DATABASE])} "
        f"database, {len(skipped[_SKIP_SYMLINK])} symlink (not copied into the "
        "redacted mirror)."
    )
    for rel in skipped[_SKIP_BINARY]:
        print(f"  skipped:binary (not copied): {rel}")
    for rel in skipped[_SKIP_DATABASE]:
        print(f"  skipped:database (local evidence, not copied): {rel}")
    for rel in skipped[_SKIP_SYMLINK]:
        print(f"  skipped:symlink (never followed, not copied): {rel}")
    for rel, exc in parse_errors:
        print(
            f"  skipped ({rel}: forced --format json but invalid JSON): {exc}",
            file=sys.stderr,
        )
    return 0


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``redact`` command on ``subparsers``."""

    parser = subparsers.add_parser(
        "redact",
        help="scrub secrets/PII from a projection, log, or evidence tree before sharing",
        description=(
            "Scrub secrets/PII before you attach evidence to a PR or dashboard. "
            "Accepts a JSON projection, a plain-text log (stdout/stderr), or a "
            "whole evidence directory. Defense-in-depth, not a guarantee — review "
            "sensitive evidence at the source too."
        ),
    )
    parser.add_argument(
        "input",
        type=Path,
        help="projection JSON, plain-text file, or evidence DIRECTORY to scan/redact",
    )
    parser.add_argument(
        "output",
        type=Path,
        nargs="?",
        default=None,
        help="destination file (or directory, for a tree) — required unless --check",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="scan only; write nothing; exit 1 if any secret/PII shape is found",
    )
    parser.add_argument(
        "--format",
        choices=("json", "text"),
        default=None,
        help="force the input interpretation (default: auto — JSON if it parses, "
        "else text); binaries and SQLite databases are always skipped in a tree",
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
