"""Behavioral tests for the shared CI redact-gate (issue #82).

``.buildkite/plugin/lib/nlfr-ci-gate.sh`` is the single source of truth reused
by the GitHub composite Action, the Buildkite plugin, and the Jenkins snippet:
record a Bazel build's evidence, then GATE it through ``nlfr redact`` BEFORE
anything can be uploaded. These tests exercise that script end-to-end against
planted fixture evidence trees, proving the guarantee the whole primitive
exists for: **the raw tree is never blessed for upload unless the redact gate
passed.**

The gate calls ``nlfr`` via an overridable ``NLFR_CMD``. Here we point it at a
tiny stub whose ``record`` is a no-op (the test pre-plants the evidence tree and
chooses the recorded exit code) and whose ``redact`` delegates to the REAL local
``nlfr`` — so the safety-critical redaction path runs against genuine behavior,
offline, with no ``uvx``/PyPI round-trip.

The only "secret" is AWS's own documented-fake example key, never a live shape.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / ".buildkite" / "plugin" / "lib" / "nlfr-ci-gate.sh"

# AWS canonical documentation example key — never a live credential.
FAKE_AWS_KEY = "AKIAIOSFODNN7EXAMPLE"

_STUB = """#!/usr/bin/env bash
# record: no-op honoring STUB_RECORD_EXIT (test pre-plants the tree).
# redact: delegate to the real local nlfr so the true gate logic runs.
set -uo pipefail
sub="${1:-}"; shift || true
case "$sub" in
  record) exit "${STUB_RECORD_EXIT:-0}" ;;
  redact) exec "$REAL_NLFR_PY" -m nlfr redact "$@" ;;
  *) echo "stub: unexpected subcommand: $sub" >&2; exit 99 ;;
esac
"""


def _stub(tmp_path: Path) -> Path:
    path = tmp_path / "nlfr-stub.sh"
    path.write_text(_STUB, encoding="utf-8")
    path.chmod(0o755)
    return path


def _plant(root: Path, *, leaky: bool) -> None:
    """Lay down a recorded-evidence tree, optionally with a planted secret.

    Mirrors what ``nlfr record`` writes under ``--output-dir``: raw stdout under
    ``runs/<id>/artifacts`` and a proof projection under ``projections/``.
    """
    art = root / "runs" / "abc" / "artifacts"
    art.mkdir(parents=True, exist_ok=True)
    (root / "projections").mkdir(parents=True, exist_ok=True)
    leak = f"leaked: {FAKE_AWS_KEY}\n" if leaky else ""
    (art / "bazel.stdout.txt").write_text(
        f"INFO: Analyzed //app:t\n{leak}INFO: Build completed\n", encoding="utf-8"
    )
    (root / "projections" / "proof-G.json").write_text(
        '{"schema_version": 1, "redaction_state": "safe"}', encoding="utf-8"
    )


def _run_gate(
    tmp_path: Path,
    *,
    evidence: Path,
    strict: bool,
    record_exit: int = 0,
) -> tuple[int, dict[str, str]]:
    stub = _stub(tmp_path)
    ci_out = tmp_path / "ci-output.txt"
    ci_out.write_text("", encoding="utf-8")
    env = {
        "PATH": __import__("os").environ["PATH"],
        "REAL_NLFR_PY": sys.executable,
        "NLFR_CMD": str(stub),
        "STUB_RECORD_EXIT": str(record_exit),
        "NLFR_COMMAND": "bazel test //...",
        "NLFR_RUN_GROUP": "G",
        "NLFR_OUTPUT_DIR": str(evidence),
        "NLFR_STRICT": "true" if strict else "false",
        "NLFR_CI_OUTPUT": str(ci_out),
    }
    proc = subprocess.run(
        ["bash", str(GATE)], env=env, capture_output=True, text=True
    )
    outputs: dict[str, str] = {}
    for line in ci_out.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            outputs[key] = value
    return proc.returncode, outputs


def test_gate_script_exists_and_is_the_shared_source() -> None:
    assert GATE.is_file(), f"shared gate script missing at {GATE}"


def test_strict_mode_blocks_on_planted_finding_before_any_upload(tmp_path) -> None:
    """(a) strict + a planted secret => BLOCK: exit 3, no upload-path."""
    evidence = tmp_path / "evidence"
    _plant(evidence, leaky=True)

    code, out = _run_gate(tmp_path, evidence=evidence, strict=True)

    assert code == 3, "strict redact finding must fail the gate (exit 3)"
    assert out["redact-status"] == "blocked"
    assert out["upload-path"] == "", "nothing may be blessed for upload when blocked"


def test_non_strict_scrubs_and_blesses_a_symlink_free_copy(tmp_path) -> None:
    """(b) non-strict + a planted secret => SCRUB: upload-path is a scrubbed,
    materialized copy — never the raw tree, never the deterministic mirror path."""
    evidence = tmp_path / "evidence"
    _plant(evidence, leaky=True)

    code, out = _run_gate(tmp_path, evidence=evidence, strict=False)

    assert code == 0
    assert out["redact-status"] == "scrubbed"
    upload = Path(out["upload-path"])
    assert upload != evidence, "the raw tree is never the upload target"
    assert upload != evidence.parent / f"{evidence.name}-redacted", (
        "upload-path is a gate-private copy, not the deterministic mirror path"
    )
    # The blessed copy no longer carries the secret...
    scrubbed = (upload / "runs" / "abc" / "artifacts" / "bazel.stdout.txt").read_text()
    assert FAKE_AWS_KEY not in scrubbed
    # ...while the raw tree still does (proving the copy, not the raw tree, is uploaded).
    raw = (evidence / "runs" / "abc" / "artifacts" / "bazel.stdout.txt").read_text()
    assert FAKE_AWS_KEY in raw


def test_clean_tree_passes_strict_and_blesses_a_materialized_copy(tmp_path) -> None:
    """(c) strict + a clean tree => PASS: exit 0; upload-path is a materialized,
    symlink-free copy (NOT the live evidence dir), still holding the real files."""
    evidence = tmp_path / "evidence"
    _plant(evidence, leaky=False)

    code, out = _run_gate(tmp_path, evidence=evidence, strict=True)

    assert code == 0
    assert out["redact-status"] == "clean"
    upload = Path(out["upload-path"])
    assert upload != evidence, "the uploader never receives the live evidence dir"
    assert upload.is_dir()
    # The real evidence is present in the materialized copy...
    assert (upload / "runs" / "abc" / "artifacts" / "bazel.stdout.txt").is_file()
    assert (upload / "projections" / "proof-G.json").is_file()
    # ...and there are no symlinks in it.
    assert not any(p.is_symlink() for p in upload.rglob("*"))


def test_red_build_stays_red_the_gate_never_masks_the_result(tmp_path) -> None:
    """A failed build (record-exit=1) that passes redact still surfaces exit 1.

    The gate returns 0 (redact passed, upload may proceed) but carries the honest
    build result forward as ``record-exit`` so the caller re-fails the step — a
    red build never becomes a green action.
    """
    evidence = tmp_path / "evidence"
    _plant(evidence, leaky=False)

    code, out = _run_gate(tmp_path, evidence=evidence, strict=True, record_exit=1)

    assert code == 0, "the gate itself passes (redact clean); the caller re-applies the build code"
    assert out["record-exit"] == "1", "the wrapped build's exit code is surfaced faithfully"
    assert out["redact-status"] == "clean"


# --------------------------------------------------------------------------- symlink safety
#
# `nlfr redact --check` REPORTS a symlink (skipped:symlink) but exits 0 — it
# never follows it. Native artifact uploaders DO follow symlinks by default
# (actions/upload-artifact@v4 follow-symbolic-links, buildkite-agent, Jenkins
# archiveArtifacts), so a link planted in the well-known evidence dir pointing at
# an outside secret would ship unscanned target bytes inside a "gate-blessed"
# artifact. Strict mode must therefore BLOCK when it can't scan everything.


def test_strict_blocks_on_planted_symlink_to_outside_secret(tmp_path) -> None:
    """The reviewer's exact scenario: record → plant a symlink to an outside
    secret file → strict gate must BLOCK, upload nothing."""
    outside = tmp_path / "outside-secret.txt"
    outside.write_text(
        "aws_secret_access_key = wJalrXUtnFEMI/EXAMPLEKEY\n", encoding="utf-8"
    )
    evidence = tmp_path / "evidence"
    _plant(evidence, leaky=False)  # scannable content is clean...
    # ...but a symlink to an outside secret is planted in the artifacts dir.
    (evidence / "runs" / "abc" / "artifacts" / "leak.link").symlink_to(outside)

    code, out = _run_gate(tmp_path, evidence=evidence, strict=True)

    assert code == 4, "a symlink strict mode cannot scan must fail the gate (exit 4)"
    assert out["redact-status"] == "blocked-symlinks"
    assert out["upload-path"] == "", "nothing may be blessed when a symlink is present"


def test_strict_blocks_on_directory_symlink(tmp_path) -> None:
    """A DIRECTORY symlink is caught too (find -type l reports the link entry)."""
    outside_dir = tmp_path / "outside-dir"
    outside_dir.mkdir()
    (outside_dir / "secret.txt").write_text("token=abc", encoding="utf-8")
    evidence = tmp_path / "evidence"
    _plant(evidence, leaky=False)
    (evidence / "runs" / "abc" / "dirlink").symlink_to(outside_dir)

    code, out = _run_gate(tmp_path, evidence=evidence, strict=True)

    assert code == 4
    assert out["redact-status"] == "blocked-symlinks"
    assert out["upload-path"] == ""


def test_strict_blocks_on_deeply_nested_symlink(tmp_path) -> None:
    """A symlink nested several levels down is still detected."""
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    evidence = tmp_path / "evidence"
    _plant(evidence, leaky=False)
    nested = evidence / "runs" / "abc" / "artifacts" / "deep" / "deeper"
    nested.mkdir(parents=True)
    (nested / "buried.link").symlink_to(outside)

    code, out = _run_gate(tmp_path, evidence=evidence, strict=True)

    assert code == 4
    assert out["redact-status"] == "blocked-symlinks"
    assert out["upload-path"] == ""


def test_non_strict_mirror_excludes_symlink_and_its_target(tmp_path) -> None:
    """Non-strict is the disclosed escape hatch: the scrubbed mirror never copies
    a symlink, so the outside target's bytes never reach the uploaded artifact."""
    outside = tmp_path / "outside-secret.txt"
    outside.write_text("aws_secret_access_key = wJalrXUtnFEMI/EXAMPLEKEY\n", encoding="utf-8")
    evidence = tmp_path / "evidence"
    _plant(evidence, leaky=False)
    (evidence / "runs" / "abc" / "artifacts" / "leak.link").symlink_to(outside)

    code, out = _run_gate(tmp_path, evidence=evidence, strict=False)

    assert code == 0
    assert out["redact-status"] == "scrubbed"
    upload = Path(out["upload-path"])
    assert upload != evidence.parent / f"{evidence.name}-redacted", (
        "upload-path is a gate-private copy, not the deterministic mirror path"
    )
    # No symlink survives into the blessed copy...
    assert not any(p.is_symlink() for p in upload.rglob("*"))
    # ...and the outside secret's bytes appear nowhere in it.
    for path in upload.rglob("*"):
        if path.is_file():
            assert "wJalrXUtnFEMI" not in path.read_text(encoding="utf-8", errors="ignore")


def test_clean_tree_with_no_symlinks_still_passes_strict(tmp_path) -> None:
    """The symlink guard must not false-positive: a symlink-free clean tree passes."""
    evidence = tmp_path / "evidence"
    _plant(evidence, leaky=False)
    # Sanity: there really are no symlinks in the planted tree.
    assert not any(p.is_symlink() for p in evidence.rglob("*"))

    code, out = _run_gate(tmp_path, evidence=evidence, strict=True)

    assert code == 0
    assert out["redact-status"] == "clean"
    upload = Path(out["upload-path"])
    assert upload != evidence  # a materialized copy, not the live dir
    assert (upload / "runs" / "abc" / "artifacts" / "bazel.stdout.txt").is_file()


def test_strict_race_symlink_stripped_from_materialized_copy(tmp_path) -> None:
    """TOCTOU race: a symlink that appears AFTER the pre-check `find` (planted here
    when `redact --check` runs, as a detached build process would) races past the
    static block but is STRIPPED from the materialized upload copy — its target
    bytes never reach the uploader, and the gate never blesses the raw tree."""
    secret = tmp_path / "prod-creds.txt"
    secret.write_text("aws_secret_access_key = wJalrXUtnFEMI/RACEKEY\n", encoding="utf-8")
    evidence = tmp_path / "evidence"
    _plant(evidence, leaky=False)  # clean at pre-check time; no symlink yet

    # A stub whose `redact --check` plants the symlink into the dir being checked
    # (after the gate's pre-check find has already run), then delegates to real
    # redact — exactly the race window the materialize-strip closes.
    race_stub = tmp_path / "race-stub.sh"
    race_stub.write_text(
        "#!/usr/bin/env bash\n"
        "set -uo pipefail\n"
        'sub="${1:-}"; shift || true\n'
        "case \"$sub\" in\n"
        '  record) exit "${STUB_RECORD_EXIT:-0}" ;;\n'
        "  redact)\n"
        '    if [ "${1:-}" = "--check" ] && [ -n "${RACE_SECRET:-}" ] && [ -d "${2:-}" ]; then\n'
        '      ln -sf "$RACE_SECRET" "$2/raced.link" 2>/dev/null || true\n'
        "    fi\n"
        '    exec "$REAL_NLFR_PY" -m nlfr redact "$@" ;;\n'
        '  *) echo "stub: unexpected $sub" >&2; exit 99 ;;\n'
        "esac\n",
        encoding="utf-8",
    )
    race_stub.chmod(0o755)

    ci_out = tmp_path / "ci-output.txt"
    ci_out.write_text("", encoding="utf-8")
    env = {
        "PATH": __import__("os").environ["PATH"],
        "REAL_NLFR_PY": sys.executable,
        "NLFR_CMD": str(race_stub),
        "RACE_SECRET": str(secret),
        "NLFR_COMMAND": "bazel test //...",
        "NLFR_RUN_GROUP": "G",
        "NLFR_OUTPUT_DIR": str(evidence),
        "NLFR_STRICT": "true",
        "NLFR_CI_OUTPUT": str(ci_out),
    }
    proc = subprocess.run(["bash", str(GATE)], env=env, capture_output=True, text=True)
    out: dict[str, str] = {}
    for line in ci_out.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            out[k] = v

    # The symlink really did race into the raw evidence dir.
    assert (evidence / "raced.link").is_symlink(), "the race stub should have planted the symlink"
    # The gate passed (raced past the pre-check) but did NOT bless the raw tree...
    assert proc.returncode == 0
    assert out["redact-status"] == "clean"
    upload = Path(out["upload-path"])
    assert upload != evidence, "the raw dir (which now holds the raced symlink) is never uploaded"
    # ...the materialized copy has no symlink and no secret target bytes.
    assert not any(p.is_symlink() for p in upload.rglob("*")), "raced symlink stripped from copy"
    for path in upload.rglob("*"):
        if path.is_file():
            assert "wJalrXUtnFEMI" not in path.read_text(encoding="utf-8", errors="ignore")
