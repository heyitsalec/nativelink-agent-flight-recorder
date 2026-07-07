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


# --------------------------------------------------------------- symlink safety
#
# Regression pins for the three MAJORS in review W3-H (second consecutive PR
# where the symlink-blindness class recurred — see PR #72's --db-root, whose
# settled doctrine is "report, never follow, never silent"). The tree walk used
# ``if p.is_file()`` over ``rglob("*")``, which silently DROPPED directory links
# (their content, reachable only via the alias, was never scanned — a false-clean
# gate) while FOLLOWING file links (reading, and in write mode copying, the link
# TARGET's out-of-scope content into a mirror labelled "safe to share").


def test_dir_symlink_reachable_content_is_reported_not_silently_dropped(
    tmp_path, capsys
) -> None:
    """F1: a run-group dir reachable ONLY via a 'latest'-style directory symlink.

    ``rglob`` lists the link but does not descend, and the old ``is_file()``
    filter dropped it silently → ``scanned 0 files``, exit 0: a false-clean gate
    over a secret that exists. The fix keeps exit 0 (a skip is not a finding) but
    the link is now REPORTED, so the non-scan is visible.
    """

    root = tmp_path / "evidence"
    root.mkdir()
    # A real run-group dir OUTSIDE the scanned root, holding a planted secret.
    external = tmp_path / "external_runs" / "grp"
    external.mkdir(parents=True)
    (external / "leak.txt").write_text(f"leaked key {FAKE_AWS_KEY}\n", encoding="utf-8")
    # Reachable from inside `root` only through a directory symlink.
    (root / "latest").symlink_to(external, target_is_directory=True)

    code = main(["redact", "--check", str(root)])

    assert code == 0  # skip is not a finding — gate stays open
    out = capsys.readouterr().out
    assert "scanned 0 file(s)" in out  # the through-the-link content was NOT scanned
    # ...but the non-scan is now VISIBLE: the link is reported, never dropped.
    assert "skipped:symlink" in out
    assert "latest" in out
    # The planted secret never appears (its dir was never traversed).
    assert FAKE_AWS_KEY not in out


def test_file_symlink_to_outside_is_never_read_or_mirrored(tmp_path, capsys) -> None:
    """F2: an in-tree FILE symlink whose target is out-of-scope filesystem content.

    Old behaviour: ``is_file()``/``read_bytes()`` traversed the link, scanned the
    target, and in write mode copied it as a real file into the "safe" mirror —
    smuggling out-of-scope content out. The fix reports the link and never reads,
    scans, or copies it; the mirror contains zero symlinks.
    """

    root = tmp_path / "evidence"
    (root / "runs").mkdir(parents=True)
    (root / "runs" / "clean.txt").write_text("all clear\n", encoding="utf-8")
    # An OUTSIDE file with a staging credential, reachable via an in-tree link.
    outside = tmp_path / "outside" / "secrets.env"
    outside.parent.mkdir(parents=True)
    outside.write_text(
        f"staging_password=hunter2\naws_secret_access_key={FAKE_AWS_KEY}\n",
        encoding="utf-8",
    )
    (root / "runs" / "link.env").symlink_to(outside)

    out_dir = tmp_path / "mirror"
    code = main(["redact", str(root), str(out_dir)])

    assert code == 0
    # The link's target is never copied into the mirror.
    assert not (out_dir / "runs" / "link.env").exists()
    # No mirror file carries the outside content — not verbatim, not redacted.
    for path in out_dir.rglob("*"):
        if path.is_file():
            body = path.read_text(encoding="utf-8", errors="replace")
            assert "staging_password" not in body
            assert FAKE_AWS_KEY not in body
    # The mirror contains ZERO symlinks.
    assert not any(path.is_symlink() for path in out_dir.rglob("*"))
    # The clean real file WAS mirrored (the walk still processes real files).
    assert (out_dir / "runs" / "clean.txt").is_file()
    # And the skipped link is reported honestly.
    report = capsys.readouterr().out
    assert "skipped:symlink" in report
    assert "link.env" in report


def test_file_symlink_reported_under_check(tmp_path, capsys) -> None:
    """F2 (check mode): the link is reported and never read; gate stays exit 0."""

    root = tmp_path / "evidence"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text(f"secret {FAKE_AWS_KEY}\n", encoding="utf-8")
    (root / "alias.txt").symlink_to(outside)

    code = main(["redact", "--check", str(root)])

    assert code == 0
    out = capsys.readouterr().out
    assert "skipped:symlink" in out
    assert "alias.txt" in out
    assert FAKE_AWS_KEY not in out  # target never read


def test_format_text_on_tree_still_skips_sqlite(tmp_path, capsys) -> None:
    """F3: ``--format text`` must NOT override the DB safety sniff in a tree.

    Old ``_classify`` checked ``fmt`` before the sniff, so ``--format text`` over
    ``nlfr.sqlite`` decoded the database (``errors="replace"``) and re-encoded a
    CORRUPTED copy into the mirror — contradicting ``--help`` ("binaries and
    SQLite databases are always skipped in a tree"). The sniff now runs first.
    """

    root = tmp_path / "evidence"
    (root / "runs").mkdir(parents=True)
    (root / "runs" / "log.txt").write_text("INFO ok\n", encoding="utf-8")
    conn = sqlite3.connect(root / "nlfr.sqlite")
    conn.execute("CREATE TABLE runs(id TEXT)")
    conn.execute("INSERT INTO runs VALUES ('r1')")
    conn.commit()
    conn.close()
    db_before = (root / "nlfr.sqlite").read_bytes()

    out_dir = tmp_path / "mirror"
    code = main(["redact", "--format", "text", str(root), str(out_dir)])

    assert code == 0
    report = capsys.readouterr().out
    assert "skipped:database" in report
    assert "nlfr.sqlite" in report
    # No .sqlite in the mirror — and certainly not a corrupted copy.
    assert not (out_dir / "nlfr.sqlite").exists()
    assert not any(p.suffix == ".sqlite" for p in out_dir.rglob("*"))
    # The source DB is byte-identical and still openable (never rewritten).
    assert (root / "nlfr.sqlite").read_bytes() == db_before
    conn = sqlite3.connect(root / "nlfr.sqlite")
    assert conn.execute("SELECT id FROM runs").fetchone() == ("r1",)
    conn.close()


def test_format_text_on_tree_check_still_reports_sqlite_skip(tmp_path, capsys) -> None:
    """F3 (check mode): the DB is reported skipped under ``--format text`` too."""

    root = tmp_path / "evidence"
    root.mkdir()
    (root / "log.txt").write_text("INFO ok\n", encoding="utf-8")
    conn = sqlite3.connect(root / "nlfr.sqlite")
    conn.execute("CREATE TABLE t(x)")
    conn.commit()
    conn.close()

    code = main(["redact", "--check", "--format", "text", str(root)])

    assert code == 0
    out = capsys.readouterr().out
    assert "skipped:database" in out
    assert "nlfr.sqlite" in out


def test_format_text_on_single_sqlite_file_refuses_not_corrupts(tmp_path, capsys) -> None:
    """F3 (single file): ``--format text`` over a lone SQLite DB must refuse.

    The sniff outranks ``--format`` for a single file too: an honest skip naming
    the DB, never a corrupted decode-and-re-encode. Exit 0 is consistent with the
    existing single-file binary-skip convention (a skip is not a finding).
    """

    db = tmp_path / "nlfr.sqlite"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE t(x)")
    conn.commit()
    conn.close()
    before = db.read_bytes()

    # check: honest skip naming the DB sniff, NOT a false "OK, no findings".
    code = main(["redact", "--check", "--format", "text", str(db)])
    assert code == 0
    captured = capsys.readouterr()
    assert "skipped" in captured.err
    assert "SQLite database" in captured.err
    assert "OK, no findings" not in captured.out

    # write: refuses to emit a corrupted copy; nothing written; source untouched.
    out = tmp_path / "out.txt"
    code = main(["redact", "--format", "text", str(db), str(out)])
    assert code == 0
    assert not out.exists()
    assert db.read_bytes() == before


def test_tree_write_mirror_contains_zero_symlinks(tmp_path, capsys) -> None:
    """The written mirror is symlink-free even when the source tree is riddled.

    A directory link, a file link, a binary, and a database all coexist in the
    source; the mirror gets only the real, scannable, redacted files — no link
    of any kind, no binary, no database.
    """

    root = tmp_path / "evidence"
    (root / "runs").mkdir(parents=True)
    (root / "runs" / "real.txt").write_text(f"key {FAKE_AWS_KEY}\n", encoding="utf-8")
    (root / "runs" / "thumb.bin").write_bytes(b"\x00\x01binary")
    conn = sqlite3.connect(root / "nlfr.sqlite")
    conn.execute("CREATE TABLE t(x)")
    conn.commit()
    conn.close()
    # A directory symlink and a file symlink, both pointing outside the root.
    ext_dir = tmp_path / "ext" / "grp"
    ext_dir.mkdir(parents=True)
    (ext_dir / "hidden.txt").write_text(f"hidden {FAKE_AWS_KEY}\n", encoding="utf-8")
    (root / "latest").symlink_to(ext_dir, target_is_directory=True)
    ext_file = tmp_path / "ext" / "target.txt"
    ext_file.write_text(f"aliased {FAKE_AWS_KEY}\n", encoding="utf-8")
    (root / "runs" / "alias.txt").symlink_to(ext_file)

    out_dir = tmp_path / "mirror"
    code = main(["redact", str(root), str(out_dir)])

    assert code == 0
    # Every mirror entry is a real file or directory — never a symlink.
    for path in out_dir.rglob("*"):
        assert not path.is_symlink(), f"mirror leaked a symlink: {path}"
    # Only the one real scannable file made it in (redacted).
    mirrored = sorted(p.relative_to(out_dir).as_posix() for p in out_dir.rglob("*") if p.is_file())
    assert mirrored == ["runs/real.txt"]
    assert "[REDACTED:aws_access_key_id]" in (out_dir / "runs" / "real.txt").read_text()
    # The redacted mirror re-scans clean.
    capsys.readouterr()
    assert main(["redact", "--check", str(out_dir)]) == 0
