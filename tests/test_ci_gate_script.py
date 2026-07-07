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


def test_non_strict_scrubs_and_only_the_mirror_is_blessed(tmp_path) -> None:
    """(b) non-strict + a planted secret => SCRUB: mirror is the upload target."""
    evidence = tmp_path / "evidence"
    _plant(evidence, leaky=True)

    code, out = _run_gate(tmp_path, evidence=evidence, strict=False)

    assert code == 0
    assert out["redact-status"] == "scrubbed"
    mirror = Path(out["upload-path"])
    assert mirror == evidence.parent / f"{evidence.name}-redacted"
    assert mirror != evidence, "the raw tree is never the upload target when scrubbing"
    # The scrubbed mirror no longer carries the secret...
    scrubbed = (mirror / "runs" / "abc" / "artifacts" / "bazel.stdout.txt").read_text()
    assert FAKE_AWS_KEY not in scrubbed
    # ...while the raw tree still does (proving the mirror, not the raw tree, is uploaded).
    raw = (evidence / "runs" / "abc" / "artifacts" / "bazel.stdout.txt").read_text()
    assert FAKE_AWS_KEY in raw


def test_clean_tree_passes_strict_and_blesses_the_tree(tmp_path) -> None:
    """(c) strict + a clean tree => PASS: exit 0, the tree itself is blessed."""
    evidence = tmp_path / "evidence"
    _plant(evidence, leaky=False)

    code, out = _run_gate(tmp_path, evidence=evidence, strict=True)

    assert code == 0
    assert out["redact-status"] == "clean"
    assert Path(out["upload-path"]) == evidence


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
