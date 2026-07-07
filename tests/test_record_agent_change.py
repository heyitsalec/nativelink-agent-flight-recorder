import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from nlfr.db import connect, initialize


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "record-agent-change.sh"


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        capture_output=True,
        check=check,
    )


def _init_git_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")


def _script_dry_run(
    workspace: Path,
    change_path: str,
    prompt_file: Path,
    baseline_ref: str | None = None,
) -> dict:
    """Run the adapter --dry-run and return its parsed JSON (carries the sidecar)."""

    argv = [
        str(SCRIPT),
        "--dry-run",
        "--workspace",
        str(workspace),
        "--change-path",
        change_path,
        "--model",
        "composer-2.5",
        "--prompt-file",
        str(prompt_file),
    ]
    if baseline_ref is not None:
        argv += ["--baseline-ref", baseline_ref]
    result = subprocess.run(
        argv,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def run_nlfr(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "nlfr", *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_record_agent_change_dry_run_emits_hashed_provenance(tmp_path: Path) -> None:
    prompt_file = tmp_path / "prompt.txt"
    prompt_text = "Add a leaf test for priority_band backlog.\n"
    prompt_file.write_text(prompt_text, encoding="utf-8")

    result = subprocess.run(
        [str(SCRIPT), "--dry-run", "--change-path", "README.md", "--model", "composer-2.5", "--prompt-file", str(prompt_file)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "dry_run"
    assert payload["model"] == "composer-2.5"
    assert payload["change_path"] == "README.md"
    assert payload["source_kind"] == "collectable_v1"

    sidecar = payload["sidecar"]
    assert sidecar["schema_version"] == "nlfr.agent_provenance.sidecar.v1"
    assert sidecar["adapter"] == "record-agent-change.sh"
    agent = sidecar["agent"]
    assert agent["model"] == "composer-2.5"
    assert agent["prompt_sha256"]
    assert "prompt" not in agent
    assert prompt_text not in result.stdout


def test_provenance_sidecar_shape_matches_bounded_patch_contract(tmp_path: Path) -> None:
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("bounded patch task\n", encoding="utf-8")

    dry = subprocess.run(
        [
            str(SCRIPT),
            "--dry-run",
            "--change-path",
            "tasks/priority_test.py",
            "--model",
            "demo-bounded-llm",
            "--prompt-file",
            str(prompt_file),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert dry.returncode == 0, dry.stderr
    sidecar = json.loads(dry.stdout)["sidecar"]

    scenario = json.loads((ROOT / "demo" / "scenarios" / "llm-bounded-patch.json").read_text())
    demo_agent = scenario["simulated_agent"]

    assert set(sidecar["agent"]) >= {"kind", "name", "model", "prompt_sha256"}
    assert sidecar["agent"]["model"] == demo_agent["model"] or sidecar["agent"]["model"] == "demo-bounded-llm"
    assert isinstance(sidecar["agent"]["prompt_sha256"], str)
    assert len(sidecar["agent"]["prompt_sha256"]) == 64


def test_generic_run_records_agent_provenance_from_sidecar(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "probe.txt"
    target.write_text("before\n", encoding="utf-8")

    sidecar_path = tmp_path / "sidecar.json"
    sidecar_path.write_text(
        json.dumps(
            {
                "schema_version": "nlfr.agent_provenance.sidecar.v1",
                "adapter": "test-record-agent-change",
                "agent": {
                    "kind": "cursor_adapter_v1",
                    "name": "test-cursor-agent",
                    "model": "composer-2.5",
                    "prompt_sha256": "abc123" * 10 + "abcd",
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    output_dir = tmp_path / "out"
    result = run_nlfr(
        "run",
        "--mode",
        "generic",
        "--scenario",
        "agent-sidecar-probe",
        "--run-group",
        "agent-sidecar",
        "--workspace",
        str(workspace),
        "--output-dir",
        str(output_dir),
        "--change-path",
        "probe.txt",
        "--provenance-sidecar",
        str(sidecar_path),
        "--command",
        f"{sys.executable} -c \"from pathlib import Path; Path('probe.txt').write_text('after\\\\n')\"",
        "--json",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    artifact_root = Path(payload["artifact_root"])
    provenance = json.loads((artifact_root / "agent-provenance.json").read_text())

    assert provenance["schema_version"] == "nlfr.agent_provenance.v1"
    assert provenance["source_kind"] == "collectable_v1"
    assert provenance["agent"]["model"] == "composer-2.5"
    assert provenance["agent"]["prompt_sha256"].startswith("abc123")
    assert "prompt" not in provenance["agent"]
    change = provenance["change"]
    assert change["affected_paths"] == ["probe.txt"]
    # patch_applied is DERIVED: probe.txt goes before -> after (bytes differ), so
    # the recorded hashes back a genuine change. This must never be a literal True.
    assert change["patch_applied"] is True
    assert change["paths"]["probe.txt"]["changed"] is True
    assert (
        change["paths"]["probe.txt"]["before_sha256"]
        != change["paths"]["probe.txt"]["after_sha256"]
    )

    conn = initialize(connect(output_dir / "nlfr.sqlite"))
    block = conn.execute(
        "SELECT block_kind, source_kind, payload FROM proof_blocks WHERE block_kind = ?",
        ("agent_provenance",),
    ).fetchone()
    assert block is not None
    assert block["source_kind"] == "collectable_v1"
    stored = json.loads(block["payload"])
    assert stored["agent"]["prompt_sha256"] == provenance["agent"]["prompt_sha256"]


# --------------------------------------------------------------------------- #
# Observation modes: what the adapter captures from git as a pre-edit baseline.
# The documented workflow edits FIRST, then records — so the recorder's own
# before/after window sees no change. The git object store still holds the
# committed pre-edit bytes; the adapter captures them into the sidecar as
# verifiable evidence. These tests pin what git can and cannot attest.
# --------------------------------------------------------------------------- #


def test_script_captures_git_baseline_for_tracked_edit_first(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    _init_git_repo(workspace)
    tracked = workspace / "leaf.py"
    tracked.write_text("value = 1\n", encoding="utf-8")
    _git(workspace, "add", "leaf.py")
    _git(workspace, "commit", "-qm", "baseline")
    head_sha = _git(workspace, "rev-parse", "HEAD").stdout.strip()
    committed_bytes = _git(workspace, "show", "HEAD:leaf.py").stdout.encode()
    baseline_sha = hashlib.sha256(committed_bytes).hexdigest()

    # EDIT FIRST — the documented order — then plan the record.
    tracked.write_text("value = 2  # agent edit\n", encoding="utf-8")
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("bump the value\n", encoding="utf-8")

    payload = _script_dry_run(workspace, "leaf.py", prompt)
    baseline = payload["sidecar"]["git_baseline"]["leaf.py"]
    assert baseline["baseline_sha256"] == baseline_sha
    assert baseline["source"]["kind"] == "git_head"
    assert baseline["source"]["commit"] == head_sha
    assert baseline["source"]["ref"] == "git:HEAD:leaf.py"


def test_script_no_baseline_for_untracked_file(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    _init_git_repo(workspace)
    # A committed file exists so HEAD is born, but the change path is untracked.
    (workspace / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(workspace, "add", "seed.txt")
    _git(workspace, "commit", "-qm", "seed")
    (workspace / "untracked.txt").write_text("edited before recording\n", encoding="utf-8")
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("p\n", encoding="utf-8")

    payload = _script_dry_run(workspace, "untracked.txt", prompt)
    # git cannot attest an untracked file's pre-edit state -> no baseline.
    assert "git_baseline" not in payload["sidecar"]


def test_script_no_baseline_for_non_git_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "plain"
    workspace.mkdir()
    (workspace / "file.txt").write_text("edited before recording\n", encoding="utf-8")
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("p\n", encoding="utf-8")

    payload = _script_dry_run(workspace, "file.txt", prompt)
    assert "git_baseline" not in payload["sidecar"]


def test_script_baseline_null_for_staged_file_absent_at_head(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    _init_git_repo(workspace)
    (workspace / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(workspace, "add", "seed.txt")
    _git(workspace, "commit", "-qm", "seed")
    # New file, staged (tracked) but absent at HEAD: agent created it.
    (workspace / "new.txt").write_text("created by agent\n", encoding="utf-8")
    _git(workspace, "add", "new.txt")
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("p\n", encoding="utf-8")

    payload = _script_dry_run(workspace, "new.txt", prompt)
    baseline = payload["sidecar"]["git_baseline"]["new.txt"]
    # Absent at HEAD but tracked -> git CAN attest it did not exist: null baseline.
    assert baseline["baseline_sha256"] is None
    assert baseline["source"]["kind"] == "git_head"


def test_git_tracked_edit_first_end_to_end_changed_true(tmp_path: Path) -> None:
    """THE regression for the review: git repo, edit FIRST, then record.

    The naive before/after derivation recorded changed=false for every documented
    (edit-first) invocation. With the git baseline, the same flow yields
    changed=true, evidence-backed and cross-checkable.
    """

    if shutil.which("uv") is None:
        pytest.skip("uv required for a full record-agent-change.sh run")

    workspace = tmp_path / "repo"
    _init_git_repo(workspace)
    tracked = workspace / "leaf.py"
    tracked.write_text("value = 1\n", encoding="utf-8")
    _git(workspace, "add", "leaf.py")
    _git(workspace, "commit", "-qm", "baseline")
    head_sha = _git(workspace, "rev-parse", "HEAD").stdout.strip()
    baseline_sha = hashlib.sha256(
        _git(workspace, "show", "HEAD:leaf.py").stdout.encode()
    ).hexdigest()

    # EDIT FIRST — the documented order — then record with --command as validation.
    tracked.write_text("value = 2  # agent edit\n", encoding="utf-8")
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("bump the value\n", encoding="utf-8")
    out = tmp_path / "out"

    result = subprocess.run(
        [
            str(SCRIPT),
            "--workspace",
            str(workspace),
            "--output-dir",
            str(out),
            "--change-path",
            "leaf.py",
            "--model",
            "composer-2.5",
            "--prompt-file",
            str(prompt),
            "--command",
            "true",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr + result.stdout

    run_payload = json.loads((out / "run.json").read_text())
    provenance = json.loads(
        (Path(run_payload["artifact_root"]) / "agent-provenance.json").read_text()
    )
    change = provenance["change"]
    entry = change["paths"]["leaf.py"]
    # Recorder's own window saw NO change (edit happened before recording began).
    assert entry["before_sha256"] == entry["after_sha256"]
    # The git baseline is the pre-edit HEAD bytes and makes changed TRUE.
    assert entry["baseline_sha256"] == baseline_sha
    assert entry["baseline_source"]["kind"] == "git_head"
    assert entry["baseline_source"]["commit"] == head_sha
    assert entry["changed"] is True
    assert entry["changed_basis"] == "git_baseline"
    assert change["patch_applied"] is True
    # Commit-pinned evidence ref a skeptic can verify.
    assert f"git:{head_sha}:leaf.py" in provenance["evidence_refs"]
    # Independent skeptic cross-check: git object bytes hash to baseline_sha256.
    shown = _git(workspace, "show", f"{head_sha}:leaf.py").stdout.encode()
    assert hashlib.sha256(shown).hexdigest() == entry["baseline_sha256"]


# --------------------------------------------------------------------------- #
# --baseline-ref: the attestation path for COMMIT-BEFORE-RECORD workflows.
# When the edit was already committed before recording, HEAD equals the final
# state, so the default HEAD baseline == after and the change is NOT attestable
# (R1). --baseline-ref names the true pre-edit ref (HEAD~1 / a commit sha).
# --------------------------------------------------------------------------- #


def test_script_baseline_ref_pins_prior_commit(tmp_path: Path) -> None:
    """--baseline-ref HEAD~1 captures the PRE-EDIT blob + commit, not HEAD's."""

    workspace = tmp_path / "repo"
    _init_git_repo(workspace)
    leaf = workspace / "leaf.py"
    leaf.write_text("value = 1\n", encoding="utf-8")  # pre-edit state
    _git(workspace, "add", "leaf.py")
    _git(workspace, "commit", "-qm", "pre-edit")
    pre_edit_sha = _git(workspace, "rev-parse", "HEAD").stdout.strip()
    pre_edit_baseline = hashlib.sha256(
        _git(workspace, "show", "HEAD:leaf.py").stdout.encode()
    ).hexdigest()
    # COMMIT the edit — now HEAD holds the final state, HEAD~1 the pre-edit state.
    leaf.write_text("value = 2  # agent edit\n", encoding="utf-8")
    _git(workspace, "add", "leaf.py")
    _git(workspace, "commit", "-qm", "agent edit")
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("bump the value\n", encoding="utf-8")

    payload = _script_dry_run(workspace, "leaf.py", prompt, baseline_ref="HEAD~1")
    baseline = payload["sidecar"]["git_baseline"]["leaf.py"]
    # Pinned to the PRE-EDIT commit + its blob hash, not HEAD's committed edit.
    assert baseline["baseline_sha256"] == pre_edit_baseline
    assert baseline["source"]["commit"] == pre_edit_sha
    assert baseline["source"]["ref"] == "git:HEAD~1:leaf.py"


def test_baseline_ref_attests_committed_change_end_to_end(tmp_path: Path) -> None:
    """R1 attestation path: edit COMMITTED before recording, changed=true via ref.

    Two commits: HEAD~1 = pre-edit, HEAD = committed agent edit. The working tree
    is clean (matches HEAD), so the recorder's own before/after window and even
    the default HEAD baseline would see NO change. --baseline-ref HEAD~1 pins the
    real pre-edit blob, the recorder re-verifies it, and changed comes out true —
    evidence-backed and cross-checkable against the pre-edit commit.
    """

    if shutil.which("uv") is None:
        pytest.skip("uv required for a full record-agent-change.sh run")

    workspace = tmp_path / "repo"
    _init_git_repo(workspace)
    leaf = workspace / "leaf.py"
    leaf.write_text("value = 1\n", encoding="utf-8")
    _git(workspace, "add", "leaf.py")
    _git(workspace, "commit", "-qm", "pre-edit")
    pre_edit_sha = _git(workspace, "rev-parse", "HEAD").stdout.strip()
    pre_edit_baseline = hashlib.sha256(
        _git(workspace, "show", "HEAD:leaf.py").stdout.encode()
    ).hexdigest()
    # COMMIT the agent edit — HEAD now equals the final on-disk state.
    leaf.write_text("value = 2  # agent edit\n", encoding="utf-8")
    _git(workspace, "add", "leaf.py")
    _git(workspace, "commit", "-qm", "agent edit")
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("bump the value\n", encoding="utf-8")
    out = tmp_path / "out"

    result = subprocess.run(
        [
            str(SCRIPT),
            "--workspace",
            str(workspace),
            "--output-dir",
            str(out),
            "--change-path",
            "leaf.py",
            "--model",
            "composer-2.5",
            "--prompt-file",
            str(prompt),
            "--baseline-ref",
            "HEAD~1",
            "--command",
            "true",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr + result.stdout

    run_payload = json.loads((out / "run.json").read_text())
    provenance = json.loads(
        (Path(run_payload["artifact_root"]) / "agent-provenance.json").read_text()
    )
    entry = provenance["change"]["paths"]["leaf.py"]
    # Working tree matches HEAD, so the recorder's own window saw no change ...
    assert entry["before_sha256"] == entry["after_sha256"]
    # ... but the pre-edit ref's blob differs from after -> changed TRUE.
    assert entry["baseline_sha256"] == pre_edit_baseline
    assert entry["baseline_source"]["commit"] == pre_edit_sha
    assert entry["changed"] is True
    assert entry["changed_basis"] == "git_baseline"
    assert provenance["change"]["patch_applied"] is True
    # Evidence pinned to the PRE-EDIT commit; a skeptic reruns git show to verify.
    assert f"git:{pre_edit_sha}:leaf.py" in provenance["evidence_refs"]
    shown = _git(workspace, "show", f"{pre_edit_sha}:leaf.py").stdout.encode()
    assert hashlib.sha256(shown).hexdigest() == entry["baseline_sha256"]
    # No commit-before-record warning: the ref made the change attestable.
    assert "--baseline-ref" not in result.stderr


def test_default_head_after_commit_warns_end_to_end(tmp_path: Path) -> None:
    """R1: default HEAD baseline after a committed edit is AMBIGUOUS, not silent.

    The edit is committed and the operator forgets --baseline-ref, so the HEAD
    baseline equals the final state (baseline == after). The record must complete
    with an explicit per-path note naming the commit + a stderr warning pointing
    at --baseline-ref — the exact silent-changed=false gap R1 closes.
    """

    if shutil.which("uv") is None:
        pytest.skip("uv required for a full record-agent-change.sh run")

    workspace = tmp_path / "repo"
    _init_git_repo(workspace)
    leaf = workspace / "leaf.py"
    leaf.write_text("value = 1\n", encoding="utf-8")
    _git(workspace, "add", "leaf.py")
    _git(workspace, "commit", "-qm", "pre-edit")
    # COMMIT the edit; do NOT pass --baseline-ref (the mistake this warns about).
    leaf.write_text("value = 2  # agent edit\n", encoding="utf-8")
    _git(workspace, "add", "leaf.py")
    _git(workspace, "commit", "-qm", "agent edit")
    head_sha = _git(workspace, "rev-parse", "HEAD").stdout.strip()
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("bump the value\n", encoding="utf-8")
    out = tmp_path / "out"

    result = subprocess.run(
        [
            str(SCRIPT),
            "--workspace",
            str(workspace),
            "--output-dir",
            str(out),
            "--change-path",
            "leaf.py",
            "--model",
            "composer-2.5",
            "--prompt-file",
            str(prompt),
            "--command",
            "true",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr + result.stdout

    run_payload = json.loads((out / "run.json").read_text())
    provenance = json.loads(
        (Path(run_payload["artifact_root"]) / "agent-provenance.json").read_text()
    )
    entry = provenance["change"]["paths"]["leaf.py"]
    assert entry["changed"] is False
    assert entry["changed_basis"] == "git_baseline"
    assert entry["note"].startswith("file matches HEAD")
    assert head_sha in entry["note"]
    assert provenance["change"]["patch_applied"] is False
    # LOUD, not silent: names the path and the --baseline-ref escape hatch.
    assert "leaf.py" in result.stderr
    assert "--baseline-ref" in result.stderr
