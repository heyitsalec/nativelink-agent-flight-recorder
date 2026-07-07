"""Tests for ``nlfr redact`` text + tree modes (issue #71).

The redact gate used to be hard-scoped to JSON: a raw ``bazel.stdout.txt``
carrying a leaked credential could not even be scanned (``is not valid JSON``,
exit 2), so the CI raw-tree upload path bypassed redaction entirely. These tests
exercise the two additive modes that close that gap:

* **text mode** — a non-JSON file is scanned/redacted as PLAIN TEXT with the same
  detector registry (string-level spans, no JSON walk, no ``redaction_state``).
* **tree mode** — a DIRECTORY argument recursively scans (check) or
  copies-and-redacts (write) every regular file, honoring both formats, skipping
  binaries (``skipped:binary``) and SQLite databases (``skipped:database``)
  honestly rather than silently.

All "secrets" here are AWS's own documented-fake example key, never a live shape.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from nlfr.cli import main

# AWS canonical documentation example key — never a live credential.
FAKE_AWS_KEY = "AKIAIOSFODNN7EXAMPLE"


def _leaky_tree(root: Path) -> Path:
    """Build a recorded-evidence tree with a planted secret in raw stdout.

    Mirrors what ``nlfr record`` lays out under ``data/nlfr-record/<group>/``: a
    SQLite spine, a JSON manifest, raw stdout/stderr logs, and a binary artifact.
    The secret lands in ``bazel.stdout.txt`` — the file type where build-output
    credentials actually leak, and the one the old JSON-only gate could not scan.
    """

    artifacts = root / "runs" / "abc123" / "artifacts"
    artifacts.mkdir(parents=True)
    (artifacts / "bazel.stdout.txt").write_text(
        "INFO: Analyzed target //app:leaky_test.\n"
        f"leaked-looking line: {FAKE_AWS_KEY}\n"
        "INFO: Build completed, 1 test FAILED\n",
        encoding="utf-8",
    )
    (artifacts / "bazel.stderr.txt").write_text(
        "ERROR: //app:leaky_test failed\n", encoding="utf-8"
    )
    (artifacts / "artifact_manifest.json").write_text(
        json.dumps({"schema_version": 1, "artifacts": [], "redaction_state": "safe"}),
        encoding="utf-8",
    )
    # A genuine SQLite database (the local evidence spine).
    conn = sqlite3.connect(root / "nlfr.sqlite")
    conn.execute("CREATE TABLE runs(id TEXT)")
    conn.commit()
    conn.close()
    # A binary blob with an embedded NUL (git's binary heuristic) hiding a key.
    (artifacts / "thumb.bin").write_bytes(
        b"GIF89a\x00\x01" + FAKE_AWS_KEY.encode() + b"\x00binary"
    )
    return artifacts / "bazel.stdout.txt"


# --------------------------------------------------------------------------- text


def test_single_non_json_file_scans_as_text_and_fails_gate(tmp_path, capsys) -> None:
    """The exact #71 repro: --check on a raw stdout file, not JSON, must gate."""

    stdout_file = _leaky_tree(tmp_path)

    code = main(["redact", "--check", str(stdout_file)])

    assert code == 1  # NOT exit 2 "is not valid JSON" — the old broken behaviour
    err = capsys.readouterr().err
    assert "bazel.stdout.txt" in err
    assert "aws_access_key_id" in err
    assert "line 2" in err  # honest line number, not a JSON path
    assert "[REDACTED:aws_access_key_id]" in err
    assert FAKE_AWS_KEY not in err  # masked excerpt never leaks the raw secret


def test_clean_text_file_passes(tmp_path, capsys) -> None:
    src = tmp_path / "clean.log"
    src.write_text("INFO: build ok\ndigest a" + "0" * 63 + "\n", encoding="utf-8")

    code = main(["redact", "--check", str(src)])

    assert code == 0
    assert "OK" in capsys.readouterr().out


def test_text_write_mode_rewrites_span_in_place(tmp_path, capsys) -> None:
    src = tmp_path / "raw.log"
    dst = tmp_path / "scrubbed.log"
    src.write_text(f"prefix {FAKE_AWS_KEY} suffix\n", encoding="utf-8")

    code = main(["redact", str(src), str(dst)])

    assert code == 0
    body = dst.read_text(encoding="utf-8")
    assert body == "prefix [REDACTED:aws_access_key_id] suffix\n"
    assert FAKE_AWS_KEY not in body


def test_format_text_forces_json_file_to_be_scanned_as_text(tmp_path, capsys) -> None:
    # A JSON file whose STRING VALUE embeds a secret is caught either way, but
    # --format text proves the override reaches the plain-text scanner.
    src = tmp_path / "looks.json"
    src.write_text(json.dumps({"note": f"key {FAKE_AWS_KEY}"}), encoding="utf-8")

    code = main(["redact", "--check", "--format", "text", str(src)])

    assert code == 1
    err = capsys.readouterr().err
    assert "aws_access_key_id" in err
    assert "line 1" in err  # scanned as one text blob, not walked as JSON


# --------------------------------------------------------------------------- tree


def test_tree_check_gates_whole_evidence_dir(tmp_path, capsys) -> None:
    """`nlfr redact --check <dir>` — the CI upload gate — fails on the leak."""

    _leaky_tree(tmp_path)

    code = main(["redact", "--check", str(tmp_path)])

    assert code == 1
    err = capsys.readouterr().err
    # Names the offending file and the masked span.
    assert "bazel.stdout.txt" in err
    assert "[REDACTED:aws_access_key_id]" in err
    assert FAKE_AWS_KEY not in err
    # Skips are REPORTED, never silent.
    assert "skipped:binary" in err
    assert "thumb.bin" in err
    assert "skipped:database" in err
    assert "nlfr.sqlite" in err


def test_tree_check_clean_dir_passes_and_reports_skips(tmp_path, capsys) -> None:
    # A clean tree with only a binary + database still passes (skips don't fail
    # the gate) but honestly reports what it could not scan.
    artifacts = tmp_path / "runs" / "r1" / "artifacts"
    artifacts.mkdir(parents=True)
    (artifacts / "ok.txt").write_text("all clear\n", encoding="utf-8")
    (artifacts / "img.bin").write_bytes(b"\x00\x01\x02binary")
    conn = sqlite3.connect(tmp_path / "nlfr.sqlite")
    conn.execute("CREATE TABLE t(x)")
    conn.commit()
    conn.close()

    code = main(["redact", "--check", str(tmp_path)])

    assert code == 0
    out = capsys.readouterr().out
    assert "skipped:binary" in out
    assert "skipped:database" in out


def test_tree_write_mirrors_and_redacts_skipping_binary_and_db(tmp_path, capsys) -> None:
    _leaky_tree(tmp_path)
    out_dir = tmp_path.parent / "redacted-mirror"

    code = main(["redact", str(tmp_path), str(out_dir)])

    assert code == 0
    # Text/JSON files are redacted into the mirror, structure preserved.
    mirrored_stdout = out_dir / "runs" / "abc123" / "artifacts" / "bazel.stdout.txt"
    assert mirrored_stdout.is_file()
    assert "[REDACTED:aws_access_key_id]" in mirrored_stdout.read_text(encoding="utf-8")
    # The binary and the database are NOT copied into the shareable mirror.
    assert not (out_dir / "runs" / "abc123" / "artifacts" / "thumb.bin").exists()
    assert not (out_dir / "nlfr.sqlite").exists()
    # No raw secret survives anywhere in the mirror.
    for path in out_dir.rglob("*"):
        if path.is_file():
            assert FAKE_AWS_KEY not in path.read_text(encoding="utf-8", errors="replace")
    # The redacted mirror re-scans clean.
    capsys.readouterr()
    assert main(["redact", "--check", str(out_dir)]) == 0


def test_tree_write_requires_output_dir(tmp_path, capsys) -> None:
    _leaky_tree(tmp_path)

    code = main(["redact", str(tmp_path)])  # no output, no --check

    assert code == 2
    assert "OUTPUT_DIR" in capsys.readouterr().err


def test_binary_single_file_is_skipped_not_falsely_clean(tmp_path, capsys) -> None:
    blob = tmp_path / "art.bin"
    blob.write_bytes(b"\x00\x01" + FAKE_AWS_KEY.encode())

    code = main(["redact", "--check", str(blob)])

    assert code == 0
    err = capsys.readouterr().err
    # Honest: it says it SKIPPED the file, not that the file is clean.
    assert "skipped" in err
    assert "binary" in err
