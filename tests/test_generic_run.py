import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from nlfr.db import connect, initialize
from nlfr.projectors import export_action_graph


ROOT = Path(__file__).resolve().parents[1]


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


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        capture_output=True,
        check=True,
    )


def _init_git_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")


def _commit_file(repo: Path, rel: str, contents: str, message: str) -> tuple[str, str]:
    """Write+commit ``contents`` at ``rel`` and return (commit_sha, baseline_sha256).

    ``baseline_sha256`` is recomputed from the committed git object so it matches
    exactly what the recorder re-verifies via ``git show <commit>:<rel>``.
    """

    (repo / rel).write_text(contents, encoding="utf-8")
    _git(repo, "add", rel)
    _git(repo, "commit", "-qm", message)
    commit = _git(repo, "rev-parse", "HEAD").stdout.strip()
    shown = subprocess.run(
        ["git", "-C", str(repo), "show", f"{commit}:{rel}"],
        capture_output=True,
        check=True,
    ).stdout
    return commit, hashlib.sha256(shown).hexdigest()


def _git_baseline_block(
    change_path: str,
    commit: str,
    baseline_sha: str | None,
    *,
    ref_label: str = "HEAD",
) -> dict:
    return {
        change_path: {
            "baseline_sha256": baseline_sha,
            "source": {
                "kind": "git_head",
                "commit": commit,
                "ref": f"git:{ref_label}:{change_path}",
            },
        }
    }


def _invoke_generic(
    workspace: Path,
    output_dir: Path,
    *,
    change_path: str,
    command: str,
    sidecar: Path,
) -> tuple[subprocess.CompletedProcess[str], dict]:
    """Run generic mode against a PRE-BUILT workspace + sidecar (e.g. a git repo).

    R2 re-verifies sidecar git baselines against the workspace git object store,
    so baseline-mode tests must use a real repo whose objects the recorder can
    check — synthetic baselines in a non-git tmp dir now (correctly) fall back.
    """

    result = run_nlfr(
        "run",
        "--mode",
        "generic",
        "--scenario",
        "patch-derive-probe",
        "--run-group",
        "patch-derive",
        "--workspace",
        str(workspace),
        "--output-dir",
        str(output_dir),
        "--change-path",
        change_path,
        "--provenance-sidecar",
        str(sidecar),
        "--command",
        command,
        "--json",
    )
    payload = json.loads(result.stdout)
    provenance = json.loads(
        (Path(payload["artifact_root"]) / "agent-provenance.json").read_text()
    )
    return result, provenance


def test_generic_run_records_passing_command(tmp_path: Path) -> None:
    output_dir = tmp_path / "generic-pass"
    result = run_nlfr(
        "run",
        "--mode",
        "generic",
        "--scenario",
        "pass-probe",
        "--run-group",
        "generic-test",
        "--workspace",
        str(ROOT),
        "--output-dir",
        str(output_dir),
        "--command",
        f"{sys.executable} -c \"print('generic-ok')\"",
        "--json",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "completed"
    assert payload["mode"] == "generic"
    assert payload["source_kind"] == "collectable_v1"

    conn = initialize(connect(output_dir / "nlfr.sqlite"))
    runs = conn.execute(
        "SELECT status, mode FROM runs WHERE run_group = ?",
        ("generic-test",),
    ).fetchall()
    assert len(runs) == 1
    assert runs[0]["status"] == "completed"
    assert runs[0]["mode"] == "generic"

    invocations = conn.execute("SELECT COUNT(*) AS count FROM invocations").fetchone()
    assert invocations["count"] == 1

    targets = conn.execute("SELECT COUNT(*) AS count FROM targets").fetchone()
    actions = conn.execute("SELECT COUNT(*) AS count FROM actions").fetchone()
    cache_events = conn.execute("SELECT COUNT(*) AS count FROM cache_events").fetchone()
    assert targets["count"] == 0
    assert actions["count"] == 0
    assert cache_events["count"] == 0

    graph = export_action_graph(conn, run_group="generic-test")
    kinds = {node["kind"] for node in graph["nodes"]}
    assert "run" in kinds
    assert "invocation" in kinds
    assert "artifact" in kinds
    assert "target" not in kinds
    assert "cache_event" not in kinds


def test_generic_run_records_failure_on_nonzero_exit(tmp_path: Path) -> None:
    output_dir = tmp_path / "generic-fail"
    result = run_nlfr(
        "run",
        "--mode",
        "generic",
        "--scenario",
        "fail-probe",
        "--run-group",
        "generic-fail",
        "--workspace",
        str(ROOT),
        "--output-dir",
        str(output_dir),
        "--command",
        f"{sys.executable} -c \"import sys; sys.exit(3)\"",
        "--json",
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "failed"

    conn = initialize(connect(output_dir / "nlfr.sqlite"))
    failures = conn.execute("SELECT failure_kind, message FROM failures").fetchall()
    assert len(failures) == 1
    assert failures[0]["failure_kind"] == "command_exit"


def test_generic_run_idempotent_rerun(tmp_path: Path) -> None:
    output_dir = tmp_path / "generic-idempotent"
    args = [
        "run",
        "--mode",
        "generic",
        "--scenario",
        "idempotent",
        "--run-group",
        "generic-idempotent",
        "--workspace",
        str(ROOT),
        "--output-dir",
        str(output_dir),
        "--command",
        f"{sys.executable} -c \"print(1)\"",
    ]
    first = run_nlfr(*args)
    second = run_nlfr(*args)
    assert first.returncode == 0
    assert second.returncode == 0

    conn = initialize(connect(output_dir / "nlfr.sqlite"))
    count = conn.execute("SELECT COUNT(*) AS count FROM runs").fetchone()["count"]
    assert count == 2


def _write_sidecar(path: Path, git_baseline: dict | None = None) -> Path:
    payload = {
        "schema_version": "nlfr.agent_provenance.sidecar.v1",
        "adapter": "test-record-agent-change",
        "agent": {
            "kind": "cursor_adapter_v1",
            "name": "test-cursor-agent",
            "model": "composer-2.5",
            "prompt_sha256": "abc123" * 10 + "abcd",
        },
    }
    if git_baseline is not None:
        payload["git_baseline"] = git_baseline
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _run_generic_with_change(
    tmp_path: Path,
    *,
    change_path: str,
    command: str,
    seed: dict[str, str] | None = None,
) -> tuple[subprocess.CompletedProcess[str], dict, Path]:
    """Run generic mode with an agent sidecar and return (result, provenance, out).

    ``seed`` maps workspace-relative paths to initial contents written before the
    run, so before/after hashes can be exercised across identical / edited /
    appeared / deleted / never-observed states. This helper builds a NON-git
    workspace, so it exercises only the recorder-window path; git-baseline modes
    now require a real repo the recorder can re-verify (see ``_invoke_generic``).
    """

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    for rel, contents in (seed or {}).items():
        (workspace / rel).write_text(contents, encoding="utf-8")
    sidecar = _write_sidecar(tmp_path / "sidecar.json")
    output_dir = tmp_path / "out"

    result = run_nlfr(
        "run",
        "--mode",
        "generic",
        "--scenario",
        "patch-derive-probe",
        "--run-group",
        "patch-derive",
        "--workspace",
        str(workspace),
        "--output-dir",
        str(output_dir),
        "--change-path",
        change_path,
        "--provenance-sidecar",
        str(sidecar),
        "--command",
        command,
        "--json",
    )
    payload = json.loads(result.stdout)
    provenance = json.loads(
        (Path(payload["artifact_root"]) / "agent-provenance.json").read_text()
    )
    return result, provenance, output_dir


def test_patch_applied_false_on_identical_hash(tmp_path: Path) -> None:
    # before == after with NO git baseline is the flagship edit-first case: the
    # file was already at its final state when recording began, so the recorder
    # cannot attest a change. It must be a LOUD changed=false — note + stderr
    # warning — never a silent one (issue #52).
    result, provenance, _ = _run_generic_with_change(
        tmp_path,
        change_path="stable.txt",
        command="true",
        seed={"stable.txt": "unchanged\n"},
    )

    assert result.returncode == 0, result.stderr
    change = provenance["change"]
    assert change["patch_applied"] is False
    entry = change["paths"]["stable.txt"]
    assert entry["changed"] is False
    assert entry["before_sha256"] == entry["after_sha256"]
    assert entry["changed_basis"] == "recorder_window"
    assert entry["note"] == (
        "file already at its final state when recording began; change not "
        "observable in the recording window (no git baseline available)"
    )
    assert "stable.txt" in result.stderr
    assert "cannot attest" in result.stderr


def test_git_baseline_backs_changed_for_edit_first(tmp_path: Path) -> None:
    """THE observation-mode fix at the recorder level — VERIFIED against real git.

    Edit-first: the file is already at its final state when recording begins, so
    the recorder's own before == after (command is validation-only). The sidecar
    git baseline carries the PRE-EDIT commit bytes; R2 re-verifies it against the
    workspace git object store, and ``changed`` is derived against the (verified)
    baseline and comes out true — evidence-backed, not the silent always-false the
    naive before/after derivation produced.
    """

    workspace = tmp_path / "repo"
    _init_git_repo(workspace)
    commit, baseline_sha = _commit_file(workspace, "edit.txt", "pre-edit\n", "baseline")
    # EDIT FIRST — the working tree now differs from the committed baseline.
    (workspace / "edit.txt").write_text("final state\n", encoding="utf-8")
    sidecar = _write_sidecar(
        tmp_path / "sidecar.json",
        git_baseline=_git_baseline_block("edit.txt", commit, baseline_sha),
    )

    result, provenance = _invoke_generic(
        workspace,
        tmp_path / "out",
        change_path="edit.txt",
        command="true",  # validation only — does NOT touch the file
        sidecar=sidecar,
    )

    assert result.returncode == 0, result.stderr
    change = provenance["change"]
    entry = change["paths"]["edit.txt"]
    # Recorder's own window saw no change (edit-first) ...
    assert entry["before_sha256"] == entry["after_sha256"]
    # ... but the verified git baseline differs from after, so changed is TRUE,
    # derived against the baseline and labeled as such.
    assert entry["baseline_sha256"] == baseline_sha
    assert entry["baseline_source"]["kind"] == "git_head"
    assert entry["baseline_source"]["commit"] == commit
    assert entry["changed"] is True
    assert entry["changed_basis"] == "git_baseline"
    assert change["patch_applied"] is True
    # A skeptic gets a commit-pinned, verifiable evidence ref.
    assert f"git:{commit}:edit.txt" in provenance["evidence_refs"]
    # No unobservable / refusal warning when the baseline made the change observable.
    assert "cannot attest" not in result.stderr
    assert "IGNORED" not in result.stderr
    # Independent skeptic cross-check: the git object bytes hash to baseline_sha256.
    shown = subprocess.run(
        ["git", "-C", str(workspace), "show", f"{commit}:edit.txt"],
        capture_output=True,
        check=True,
    ).stdout
    assert hashlib.sha256(shown).hexdigest() == entry["baseline_sha256"]


def test_git_baseline_null_records_appeared(tmp_path: Path) -> None:
    """A null git baseline means absent at the ref: a present ``after`` is appeared.

    R2 verifies the null by confirming the object is genuinely absent at that
    commit (``git show <commit>:created.txt`` fails) — a forged null over an
    object that DOES exist would be refused.
    """

    workspace = tmp_path / "repo"
    _init_git_repo(workspace)
    # A committed file makes HEAD born; created.txt is absent at that commit.
    commit, _ = _commit_file(workspace, "seed.txt", "seed\n", "seed")
    sidecar = _write_sidecar(
        tmp_path / "sidecar.json",
        git_baseline=_git_baseline_block("created.txt", commit, None),
    )
    command = (
        f"{sys.executable} -c "
        "\"from pathlib import Path; Path('created.txt').write_text('new\\\\n')\""
    )

    result, provenance = _invoke_generic(
        workspace,
        tmp_path / "out",
        change_path="created.txt",
        command=command,
        sidecar=sidecar,
    )

    assert result.returncode == 0, result.stderr
    entry = provenance["change"]["paths"]["created.txt"]
    assert entry["baseline_sha256"] is None
    assert entry["after_sha256"] is not None
    assert entry["changed"] is True
    assert entry["changed_basis"] == "git_baseline"
    assert provenance["change"]["patch_applied"] is True


def test_git_baseline_matching_after_warns_commit_before_record(tmp_path: Path) -> None:
    """R1: baseline == after under ``git_baseline`` is AMBIGUOUS, never silent.

    When the pre-edit ref (default HEAD) already contains the final bytes —
    exactly what happens if the edit was COMMITTED before recording began — the
    recorder cannot tell a genuine no-op from a committed-then-recorded change.
    The old behavior emitted a silent ``changed=false`` under the strongest
    label. It must now emit a per-path note naming the commit AND a stderr
    warning pointing at ``--baseline-ref`` (replaces the silence-codifying test).
    """

    content = "committed state\n"
    workspace = tmp_path / "repo"
    _init_git_repo(workspace)
    # HEAD already holds the (possibly agent-committed) final bytes.
    commit, baseline_sha = _commit_file(workspace, "same.txt", content, "committed edit")
    sidecar = _write_sidecar(
        tmp_path / "sidecar.json",
        git_baseline=_git_baseline_block("same.txt", commit, baseline_sha),
    )

    result, provenance = _invoke_generic(
        workspace,
        tmp_path / "out",
        change_path="same.txt",
        command="true",
        sidecar=sidecar,
    )

    assert result.returncode == 0, result.stderr
    entry = provenance["change"]["paths"]["same.txt"]
    assert entry["changed"] is False
    assert entry["changed_basis"] == "git_baseline"
    assert provenance["change"]["patch_applied"] is False
    # The ambiguity is recorded, not swallowed: note names the commit + escape hatch.
    assert entry["note"].startswith("file matches HEAD")
    assert commit in entry["note"]
    assert "--baseline-ref" in entry["note"]
    # And it is LOUD on stderr, naming the path and the fix.
    assert "same.txt" in result.stderr
    assert "--baseline-ref" in result.stderr
    assert "committed before recording" in result.stderr


def test_forged_sidecar_baseline_is_refused_and_falls_back(tmp_path: Path) -> None:
    """R2 (reviewer's exact probe): a forged git_baseline is not trusted verbatim.

    The sidecar's ``baseline_sha256`` does NOT match the git object at the
    referenced commit. The old code accepted it and reported
    ``changed_basis=git_baseline`` — exactly-as-asserted evidence wearing a
    verified label. It must now be refused: fall back to recorder-window
    semantics with a per-path note + loud stderr warning, and never pin the
    forged commit as evidence. The run is recorded honestly, not hard-failed.
    """

    workspace = tmp_path / "repo"
    _init_git_repo(workspace)
    commit, real_sha = _commit_file(workspace, "edit.txt", "pre-edit\n", "baseline")
    forged_sha = "d" * 64
    assert forged_sha != real_sha
    # EDIT FIRST so the recorder's own window sees no change (before == after).
    (workspace / "edit.txt").write_text("final state\n", encoding="utf-8")
    sidecar = _write_sidecar(
        tmp_path / "sidecar.json",
        git_baseline=_git_baseline_block("edit.txt", commit, forged_sha),
    )

    result, provenance = _invoke_generic(
        workspace,
        tmp_path / "out",
        change_path="edit.txt",
        command="true",
        sidecar=sidecar,
    )

    assert result.returncode == 0, result.stderr
    change = provenance["change"]
    entry = change["paths"]["edit.txt"]
    # Refused: basis fell back to the recorder's own window.
    assert entry["changed_basis"] == "recorder_window"
    assert "did not match" in entry["note"]
    assert commit in entry["note"]
    # before == after in-window and the forged baseline is gone -> honest false.
    assert entry["changed"] is False
    assert change["patch_applied"] is False
    # The forged commit must NOT be pinned as verifiable evidence.
    assert f"git:{commit}:edit.txt" not in provenance["evidence_refs"]
    # Loud, path-named warning.
    assert "edit.txt" in result.stderr
    assert "IGNORED" in result.stderr


def test_unverifiable_sidecar_baseline_falls_back(tmp_path: Path) -> None:
    """R2: a sidecar baseline unverifiable in this workspace falls back honestly.

    Non-git workspace (the commit/object cannot be resolved here). The supplied
    baseline is refused with an explicit note + stderr warning; the change is
    derived from the recorder's own window instead of trusting the assertion.
    """

    workspace = tmp_path / "workspace"  # NOT a git repo
    workspace.mkdir()
    (workspace / "edit.txt").write_text("final state\n", encoding="utf-8")
    sidecar = _write_sidecar(
        tmp_path / "sidecar.json",
        git_baseline=_git_baseline_block("edit.txt", "a" * 40, "b" * 64),
    )

    result, provenance = _invoke_generic(
        workspace,
        tmp_path / "out",
        change_path="edit.txt",
        command="true",
        sidecar=sidecar,
    )

    assert result.returncode == 0, result.stderr
    entry = provenance["change"]["paths"]["edit.txt"]
    assert entry["changed_basis"] == "recorder_window"
    assert entry["note"] == "baseline unverifiable in this workspace"
    assert f"git:{'a' * 40}:edit.txt" not in provenance["evidence_refs"]
    assert "edit.txt" in result.stderr
    assert "IGNORED" in result.stderr


def test_patch_applied_true_on_edited_file(tmp_path: Path) -> None:
    command = (
        f"{sys.executable} -c "
        "\"from pathlib import Path; Path('edit.txt').write_text('after\\\\n')\""
    )
    result, provenance, _ = _run_generic_with_change(
        tmp_path,
        change_path="edit.txt",
        command=command,
        seed={"edit.txt": "before\n"},
    )

    assert result.returncode == 0, result.stderr
    change = provenance["change"]
    assert change["patch_applied"] is True
    assert change["paths"]["edit.txt"]["changed"] is True
    assert (
        change["paths"]["edit.txt"]["before_sha256"]
        != change["paths"]["edit.txt"]["after_sha256"]
    )


def test_patch_applied_true_on_appeared_file(tmp_path: Path) -> None:
    command = (
        f"{sys.executable} -c "
        "\"from pathlib import Path; Path('appeared.txt').write_text('new\\\\n')\""
    )
    result, provenance, _ = _run_generic_with_change(
        tmp_path,
        change_path="appeared.txt",
        command=command,
    )

    assert result.returncode == 0, result.stderr
    change = provenance["change"]
    assert change["paths"]["appeared.txt"]["before_sha256"] is None
    assert change["paths"]["appeared.txt"]["after_sha256"] is not None
    assert change["paths"]["appeared.txt"]["changed"] is True
    assert change["patch_applied"] is True


def test_patch_applied_true_on_deleted_file(tmp_path: Path) -> None:
    command = (
        f"{sys.executable} -c "
        "\"from pathlib import Path; Path('gone.txt').unlink()\""
    )
    result, provenance, _ = _run_generic_with_change(
        tmp_path,
        change_path="gone.txt",
        command=command,
        seed={"gone.txt": "doomed\n"},
    )

    assert result.returncode == 0, result.stderr
    change = provenance["change"]
    assert change["paths"]["gone.txt"]["before_sha256"] is not None
    assert change["paths"]["gone.txt"]["after_sha256"] is None
    assert change["paths"]["gone.txt"]["changed"] is True
    assert change["patch_applied"] is True


def test_change_path_never_observed_completes_with_note_and_warning(
    tmp_path: Path,
) -> None:
    result, provenance, output_dir = _run_generic_with_change(
        tmp_path,
        change_path="typo-does-not-exist.txt",
        command="true",
    )

    # The run must COMPLETE — recording an attempt honestly is valid — but the
    # evidence must say the path was never seen, and stderr must name it.
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "completed"
    assert "typo-does-not-exist.txt" in result.stderr
    assert "never observed on disk" in result.stderr

    change = provenance["change"]
    entry = change["paths"]["typo-does-not-exist.txt"]
    assert entry["before_sha256"] is None
    assert entry["after_sha256"] is None
    assert entry["changed"] is False
    assert entry["note"] == "path never observed on disk"
    assert change["patch_applied"] is False

    conn = initialize(connect(output_dir / "nlfr.sqlite"))
    run = conn.execute(
        "SELECT status FROM runs WHERE run_group = ?", ("patch-derive",)
    ).fetchone()
    assert run["status"] == "completed"


def test_generic_run_records_change_path(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "probe.txt"
    target.write_text("before\n", encoding="utf-8")
    output_dir = tmp_path / "out"

    run_nlfr(
        "run",
        "--mode",
        "generic",
        "--scenario",
        "change-probe",
        "--run-group",
        "generic-change",
        "--workspace",
        str(workspace),
        "--output-dir",
        str(output_dir),
        "--change-path",
        "probe.txt",
        "--command",
        f"{sys.executable} -c \"from pathlib import Path; Path('probe.txt').write_text('after\\\\n')\"",
    )

    conn = initialize(connect(output_dir / "nlfr.sqlite"))
    change = conn.execute(
        "SELECT before_hash, after_hash FROM changes WHERE path = ?",
        ("probe.txt",),
    ).fetchone()
    assert change is not None
    assert change["before_hash"] is not None
    assert change["after_hash"] is not None
    assert change["before_hash"] != change["after_hash"]
