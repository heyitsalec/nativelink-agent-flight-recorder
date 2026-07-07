"""Structure + safety-invariant tests for the packaged CI primitive (issue #82).

Two guarantees are enforced here:

1. ``action.yml`` and ``.buildkite/plugin/plugin.yml`` are **valid YAML** and
   declare the shape their CI systems require (a composite action; a plugin with
   a required ``command``). Validation uses whichever Python on the machine can
   ``import yaml`` — NLFR stays stdlib-only, so PyYAML is never a project
   dependency (the dev venv has none); this shells out to a yaml-capable
   interpreter (GitHub runners and typical dev boxes ship one) and skips
   honestly if none is found.

2. The **raw-tree-upload path cannot be reached without the redact gate
   passing.** This is the whole point of the primitive, so it is asserted by
   grepping the actual Action step and Buildkite hook: every upload references
   only the gate-blessed ``upload-path`` and is guarded against
   ``redact-status == blocked`` — never the raw ``output-dir`` / evidence dir.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ACTION_YML = ROOT / "action.yml"
PLUGIN_YML = ROOT / ".buildkite" / "plugin" / "plugin.yml"
HOOK = ROOT / ".buildkite" / "plugin" / "hooks" / "command"
GATE = ROOT / ".buildkite" / "plugin" / "lib" / "nlfr-ci-gate.sh"


def _yaml_capable_python() -> str | None:
    """Return a python executable that can ``import yaml``, or None."""
    candidates: list[str] = []
    import sys

    candidates.append(sys.executable)
    for name in ("python3", "python"):
        found = shutil.which(name)
        if found:
            candidates.append(found)
    candidates.extend(["/usr/bin/python3", "/opt/homebrew/bin/python3"])
    seen: set[str] = set()
    for py in candidates:
        if not py or py in seen:
            continue
        seen.add(py)
        probe = subprocess.run(
            [py, "-c", "import yaml"], capture_output=True, text=True
        )
        if probe.returncode == 0:
            return py
    return None


def _load_yaml(path: Path) -> dict:
    """Parse ``path`` as YAML via a yaml-capable interpreter → a Python dict.

    Skips the test (rather than falsely passing) when no interpreter on the
    machine can import yaml. A malformed YAML raises, failing the test.
    """
    py = _yaml_capable_python()
    if py is None:  # pragma: no cover - environment without PyYAML
        pytest.skip("no Python with PyYAML available to validate the CI YAML")
    proc = subprocess.run(
        [
            py,
            "-c",
            "import sys, json, yaml; json.dump(yaml.safe_load(open(sys.argv[1])), sys.stdout)",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"{path} is not valid YAML:\n{proc.stderr}"
    return json.loads(proc.stdout)


# --------------------------------------------------------------------------- action.yml


def test_action_yml_is_valid_composite_action() -> None:
    doc = _load_yaml(ACTION_YML)
    assert doc["runs"]["using"] == "composite"
    assert "command" in doc["inputs"], "the wrapped bazel command must be an input"
    assert doc["inputs"]["command"]["required"] is True
    # The strict-redact toggle exists and defaults to fail-closed.
    assert doc["inputs"]["strict-redact"]["default"] == "true"
    # Declared outputs the doc/how-to promises.
    for out in ("evidence-dir", "proof-path", "redact-status"):
        assert out in doc["outputs"], f"missing declared output: {out}"


def test_action_yml_uses_pinned_setup_and_upload_actions() -> None:
    steps = _load_yaml(ACTION_YML)["runs"]["steps"]
    uses = [s.get("uses", "") for s in steps]
    assert any(u.startswith("astral-sh/setup-uv@") for u in uses), "must set up uv"
    assert any(u.startswith("actions/upload-artifact@") for u in uses), "must upload via upload-artifact"


def test_action_yml_upload_is_gated_and_only_blesses_upload_path() -> None:
    """The upload step may never publish the raw tree without redact passing."""
    steps = _load_yaml(ACTION_YML)["runs"]["steps"]
    upload = next(s for s in steps if s.get("uses", "").startswith("actions/upload-artifact@"))
    guard = upload["if"]
    # Fail-safe for EVERY block reason (findings AND symlinks): a startsWith
    # deny on 'blocked' plus the authoritative empty-upload-path guard.
    assert "startsWith(steps.gate.outputs.redact-status, 'blocked')" in guard
    assert "!startsWith(steps.gate.outputs.redact-status, 'blocked')" in guard
    assert "steps.gate.outputs.upload-path != ''" in guard
    # The uploaded path is ONLY the gate-blessed upload-path — never inputs.output-dir.
    assert upload["with"]["path"] == "${{ steps.gate.outputs.upload-path }}"
    assert "output-dir" not in upload["with"]["path"]
    # Defense in depth: the uploader must not dereference a symlink either.
    assert upload["with"]["follow-symbolic-links"] is False


def test_action_yml_upload_guard_blocks_symlink_status() -> None:
    """`blocked-symlinks` must be denied by the guard just like `blocked`."""
    steps = _load_yaml(ACTION_YML)["runs"]["steps"]
    upload = next(s for s in steps if s.get("uses", "").startswith("actions/upload-artifact@"))
    guard = upload["if"]
    # startsWith(..., 'blocked') matches 'blocked' and 'blocked-symlinks'.
    for status in ("blocked", "blocked-symlinks"):
        assert status.startswith("blocked")
    assert "!startsWith(steps.gate.outputs.redact-status, 'blocked')" in guard


def test_action_yml_surfaces_the_recorded_build_result() -> None:
    """A red build must stay red: the last step re-applies record-exit, and both
    block reasons produce an error exit."""
    text = ACTION_YML.read_text(encoding="utf-8")
    assert 'exit "${RECORD_EXIT:-1}"' in text
    assert "blocked)" in text and "blocked-symlinks)" in text


# --------------------------------------------------------------------------- plugin.yml


def test_plugin_yml_is_valid_and_requires_command() -> None:
    doc = _load_yaml(PLUGIN_YML)
    assert doc["name"] == "nlfr-redact-gate"
    config = doc["configuration"]
    assert "command" in config["properties"]
    assert config["required"] == ["command"]
    assert "strict-redact" in config["properties"]


# --------------------------------------------------------------------------- shared safety invariant


def test_buildkite_hook_uploads_only_the_blessed_path_and_only_when_not_blocked() -> None:
    text = HOOK.read_text(encoding="utf-8")
    # There is exactly one artifact upload, and it targets $upload_path (the
    # gate-blessed path), never the raw $NLFR_OUTPUT_DIR / evidence dir.
    upload_lines = [ln for ln in text.splitlines() if "buildkite-agent artifact upload" in ln]
    assert len(upload_lines) == 1, "exactly one upload site, easy to audit"
    assert '"$upload_path' in upload_lines[0]
    assert "NLFR_OUTPUT_DIR" not in upload_lines[0]
    # The upload is guarded by the gate's block-check earlier in the hook — a
    # `blocked*` case that matches BOTH `blocked` (findings) and
    # `blocked-symlinks`, and exits before the upload line.
    assert "blocked*)" in text
    upload_idx = next(i for i, ln in enumerate(text.splitlines()) if "buildkite-agent artifact upload" in ln)
    block_idx = next(i for i, ln in enumerate(text.splitlines()) if "blocked*)" in ln)
    assert block_idx < upload_idx, "the block-check must precede (and can exit before) the upload"


def test_gate_script_blesses_raw_tree_only_after_a_passing_check() -> None:
    """Static proof over the gate: upload-path is set to the raw evidence dir
    ONLY inside the branch where ``redact --check`` succeeded."""
    text = GATE.read_text(encoding="utf-8")
    lines = text.splitlines()
    # Find every line that blesses the raw evidence dir for upload.
    raw_bless = [i for i, ln in enumerate(lines) if 'upload_path="$evidence_dir"' in ln]
    assert raw_bless, "expected the strict-clean branch to bless the evidence dir"
    for idx in raw_bless:
        # The nearest preceding control line must be the successful --check.
        preceding = "\n".join(lines[max(0, idx - 3): idx])
        assert "redact --check" in preceding and "if " in preceding, (
            "the raw tree may only be blessed inside the `if redact --check` success branch"
        )
    # The blocked branch never sets a non-empty upload_path.
    assert 'redact_status="blocked"' in text
    assert 'upload_path=""' in text


def test_gate_script_strict_mode_independently_detects_symlinks() -> None:
    """Strict mode must block the raw tree on ANY symlink — detected with its own
    `find -type l`, not merely trusting redact's skipped:symlink report."""
    text = GATE.read_text(encoding="utf-8")
    # Independent detection (not a parse of redact's output).
    assert 'find "$evidence_dir" -type l' in text
    # A distinct status + exit for the symlink block, with an empty upload-path.
    assert 'redact_status="blocked-symlinks"' in text
    assert "exit 4" in text
    # The symlink block sets an empty upload-path (nothing blessed).
    lines = text.splitlines()
    sym_idx = next(i for i, ln in enumerate(lines) if 'redact_status="blocked-symlinks"' in ln)
    assert 'upload_path=""' in lines[sym_idx + 1], "the symlink block must clear upload-path"
    # And the raw-tree bless is only reached AFTER the symlink check (in the elif).
    bless_idx = next(i for i, ln in enumerate(lines) if 'upload_path="$evidence_dir"' in ln)
    assert sym_idx < bless_idx, "symlink detection precedes any raw-tree bless"
