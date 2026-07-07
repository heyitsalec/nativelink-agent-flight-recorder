#!/usr/bin/env python3
"""Seed the in-toto attestation-smoke fixture (CI tooling, not runtime).

This deliberately REUSES the exact deterministic fixture the in-toto export
tests build (``tests/test_in_toto_export.py::seed_db``) rather than inventing
live evidence or a parallel fixture that could drift from what the tests prove.
It runs under ``uv run`` in CI (nlfr importable); it is NOT part of the
stdlib-only runtime and is never imported by ``src/nlfr``.

It writes:
  * ``<out>/nlfr.sqlite``      -- the seeded run-group DB (export input)
  * ``<out>/subject-run.json`` -- the recorded bytes of the ``run.json`` subject,
                                  so ``cosign verify-blob-attestation`` can run a
                                  full-claims check against a real subject file.

The ``run.json`` subject bytes are pinned here to the same literal the fixture
records. The compare helper independently re-checks that this file's sha256 is
actually one of the exported Statement's subject digests, so any drift from the
fixture fails LOUDLY instead of silently verifying the wrong bytes.

Usage:  attestation-smoke-seed.py <out_dir>
Prints the run group and the two paths, one ``key=value`` per line.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Reuse the test fixture builder verbatim (single source of truth).
sys.path.insert(0, str(ROOT / "tests"))

from test_in_toto_export import RUN_GROUP, seed_db  # noqa: E402

# Must match the ``run.json`` entry in test_in_toto_export.seed_db's manifest.
# Guarded downstream: dsse_compare.py --subject asserts this file's sha256 is a
# recorded subject digest, so a fixture change here fails the smoke, not passes.
SUBJECT_RUN_JSON_BYTES = b'{"run": "in-toto-demo"}\n'


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        sys.stderr.write("usage: attestation-smoke-seed.py <out_dir>\n")
        return 2
    out_dir = Path(argv[1]).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # seed_db writes <out_dir>/nlfr.sqlite and needs a scratch dir for its BEP.
    conn, _subject_digests = seed_db(out_dir)
    conn.close()

    db_path = out_dir / "nlfr.sqlite"
    subject_path = out_dir / "subject-run.json"
    subject_path.write_bytes(SUBJECT_RUN_JSON_BYTES)

    print(f"run_group={RUN_GROUP}")
    print(f"db={db_path}")
    print(f"subject={subject_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
