#!/usr/bin/env python3
"""Assert a cosign DSSE bundle carries NLFR's Statement, unaltered (stdlib only).

Used by the attestation-smoke CI job. Two independent checks, either failing
LOUDLY with a nonzero exit (that is the drift signal the smoke exists to raise):

  1. DSSE payload byte-identity: base64-decode ``bundle.dsseEnvelope.payload``
     and assert it byte-equals the exported in-toto Statement. cosign's
     ``attest-blob --statement`` must wrap the COMPLETE Statement verbatim; if a
     future cosign re-serializes, re-nests, or strips subjects, these bytes
     diverge and this fails.

  2. (optional, ``--subject``) Subject-digest binding: assert the sha256 of the
     positionally-verified subject file is actually one of the Statement's
     recorded ``subject[].digest.sha256`` values. This guards the smoke's own
     fixture: if the seeder's pinned subject bytes ever drift from the fixture
     the tests build, cosign's full-claims verify could pass against bytes that
     are NOT a recorded subject -- this makes that impossible to miss.

Stdlib only, by design: this is CI tooling that must not perturb NLFR's
stdlib-only runtime, and it must decode/compare without trusting the same
serializer that produced the artifacts.

Usage:
  dsse_compare.py --bundle <bundle.json> --statement <stmt.json> [--subject <file>]
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
from pathlib import Path


def _fail(msg: str) -> int:
    sys.stderr.write(f"dsse_compare: FAIL: {msg}\n")
    return 1


def _statement_subject_digests(statement: dict) -> set[str]:
    digests: set[str] = set()
    for subject in statement.get("subject", []) or []:
        digest = (subject.get("digest") or {}).get("sha256")
        if isinstance(digest, str):
            digests.add(digest.lower())
    return digests


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--statement", required=True, type=Path)
    parser.add_argument(
        "--subject",
        type=Path,
        default=None,
        help="a recorded subject file; assert its sha256 is a Statement subject",
    )
    args = parser.parse_args(argv)

    try:
        bundle = json.loads(args.bundle.read_bytes())
    except (OSError, ValueError) as exc:
        return _fail(f"could not read/parse bundle {args.bundle}: {exc}")

    envelope = bundle.get("dsseEnvelope")
    if not isinstance(envelope, dict) or "payload" not in envelope:
        return _fail(
            "bundle has no .dsseEnvelope.payload -- cosign bundle shape changed "
            f"(top-level keys: {sorted(bundle)})"
        )

    try:
        payload = base64.b64decode(envelope["payload"], validate=True)
    except (ValueError, TypeError) as exc:
        return _fail(f"DSSE payload is not valid base64: {exc}")

    statement_bytes = args.statement.read_bytes()
    if payload != statement_bytes:
        return _fail(
            "DSSE payload is NOT byte-identical to the exported Statement "
            f"(payload={len(payload)}B, statement={len(statement_bytes)}B). "
            "cosign did not wrap NLFR's Statement verbatim."
        )
    print(
        f"OK: DSSE payload byte-identical to Statement ({len(payload)} bytes)"
    )

    if args.subject is not None:
        statement = json.loads(statement_bytes)
        subject_sha = hashlib.sha256(args.subject.read_bytes()).hexdigest()
        recorded = _statement_subject_digests(statement)
        if subject_sha not in recorded:
            return _fail(
                f"subject file sha256={subject_sha} is NOT a recorded Statement "
                f"subject (recorded: {sorted(recorded)}). Fixture drift: the "
                "smoke's subject bytes no longer match a recorded subject."
            )
        print(f"OK: subject sha256={subject_sha} is a recorded Statement subject")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
