"""Tests for ``nlfr record`` — one-command evidence capture on any Bazel repo.

These tests use a fake ``bazel`` shim (a tmp Python script named ``bazel`` on
PATH). The shim validates that ``--build_event_json_file`` was injected in the
right place, writes a canned BEP derived from the existing Bazel fixture, and
exits with a configurable code. No real Bazel is required.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANNED_BEP = ROOT / "tests" / "fixtures" / "bazel" / "bep.jsonl"


def _write_bazel_shim(
    bin_dir: Path,
    *,
    exit_code: int,
    assert_after_verb: bool = True,
) -> Path:
    """Create an executable fake ``bazel`` and return its containing directory."""

    bin_dir.mkdir(parents=True, exist_ok=True)
    shim = bin_dir / "bazel"
    shim.write_text(
        "#!/usr/bin/env python3\n"
        "import os, shutil, sys\n"
        "args = sys.argv[1:]\n"
        "verb_i = next((i for i, a in enumerate(args) if not a.startswith('--')), None)\n"
        "assert verb_i is not None, f'no verb in {args}'\n"
        "flag = '--build_event_json_file'\n"
        "bep = None\n"
        "for i, a in enumerate(args):\n"
        "    if a.startswith(flag + '='):\n"
        "        bep = a.split('=', 1)[1]\n"
        "    elif a == flag and i + 1 < len(args):\n"
        "        bep = args[i + 1]\n"
        "assert bep is not None, f'no BEP flag in {args}'\n"
        "if os.environ.get('ASSERT_AFTER_VERB') == '1':\n"
        "    nxt = args[verb_i + 1] if verb_i + 1 < len(args) else ''\n"
        "    assert nxt.startswith(flag + '='), f'BEP not right after verb: {args}'\n"
        "shutil.copyfile(os.environ['NLFR_CANNED_BEP'], bep)\n"
        "sys.stdout.write('fake bazel ran targets\\n')\n"
        "sys.stderr.write('fake bazel diagnostics\\n')\n"
        f"sys.exit({exit_code})\n",
        encoding="utf-8",
    )
    shim.chmod(0o755)
    return bin_dir


# Bazel command verbs, mirrored into the strict shim so it can locate the verb
# exactly the way real Bazel does (and reject anything unknown before it).
_SHIM_VERBS = (
    "build test run query cquery aquery coverage fetch sync vendor mod info "
    "clean shutdown version dump canonicalize-flags config license print_action "
    "mobile-install analyze-profile help"
).split()


def _write_strict_bazel_shim(bin_dir: Path, *, exit_code: int = 0) -> Path:
    """Create a fake ``bazel`` that models real Bazel's startup-option parsing.

    Real Bazel accepts startup options (some with *space-separated* values like
    ``--bazelrc /path``) *before* the verb, and rejects any unknown startup
    option with exit 2 — never running the user's command. This shim reproduces
    that: it locates the verb by matching the known-verb set, requires every
    ``--flag`` before the verb to be a recognized startup option, and asserts the
    injected ``--build_event_json_file`` lands *after* the verb. If nlfr ever
    regresses and injects the BEP flag into the startup segment, this shim exits
    2 and writes no BEP, failing the regression test.
    """

    bin_dir.mkdir(parents=True, exist_ok=True)
    shim = bin_dir / "bazel"
    verbs_literal = repr(_SHIM_VERBS)
    shim.write_text(
        "#!/usr/bin/env python3\n"
        "import os, shutil, sys\n"
        "args = sys.argv[1:]\n"
        f"VERBS = set({verbs_literal})\n"
        "VALUE_STARTUP = {'--bazelrc', '--output_base', '--output_user_root', '--server_javabase'}\n"
        "BOOL_STARTUP = {'--nohome_rc', '--noworkspace_rc', '--batch'}\n"
        "verb_i = next((i for i, a in enumerate(args) if a in VERBS), None)\n"
        "if verb_i is None:\n"
        "    sys.stderr.write(f'ERROR: no command verb in {args}\\n')\n"
        "    sys.exit(2)\n"
        "# Validate the startup segment [0, verb_i): only recognized startup\n"
        "# options may appear. An injected --build_event_json_file here is an\n"
        "# unknown startup option -> real bazel exits 2 before running anything.\n"
        "i = 0\n"
        "while i < verb_i:\n"
        "    a = args[i]\n"
        "    if a in VALUE_STARTUP:\n"
        "        if i + 1 >= verb_i:\n"
        "            sys.stderr.write(f'ERROR: startup option {a} missing value\\n')\n"
        "            sys.exit(2)\n"
        "        i += 2\n"
        "        continue\n"
        "    if a in BOOL_STARTUP:\n"
        "        i += 1\n"
        "        continue\n"
        "    sys.stderr.write(f'ERROR: unknown startup option before verb: {a}\\n')\n"
        "    sys.exit(2)\n"
        "flag = '--build_event_json_file'\n"
        "bep = None\n"
        "bep_i = None\n"
        "for j, a in enumerate(args):\n"
        "    if a.startswith(flag + '='):\n"
        "        bep = a.split('=', 1)[1]; bep_i = j\n"
        "    elif a == flag and j + 1 < len(args):\n"
        "        bep = args[j + 1]; bep_i = j\n"
        "assert bep is not None, f'no BEP flag in {args}'\n"
        "assert bep_i > verb_i, f'BEP flag not after verb: {args}'\n"
        "shutil.copyfile(os.environ['NLFR_CANNED_BEP'], bep)\n"
        "sys.stdout.write('fake bazel ran targets\\n')\n"
        "sys.stderr.write('fake bazel diagnostics\\n')\n"
        f"sys.exit({exit_code})\n",
        encoding="utf-8",
    )
    shim.chmod(0o755)
    return bin_dir


def _bazel_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    (workspace / "demo").mkdir(parents=True)
    (workspace / "MODULE.bazel").write_text('module(name = "demo")\n', encoding="utf-8")
    return workspace


def _run_record(
    *args: str,
    cwd: Path,
    bin_dir: Path | None = None,
    assert_after_verb: bool = False,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    env["NLFR_CANNED_BEP"] = str(CANNED_BEP)
    if assert_after_verb:
        env["ASSERT_AFTER_VERB"] = "1"
    if bin_dir is not None:
        env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
    return subprocess.run(
        [sys.executable, "-m", "nlfr", "record", *args],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_record_passing_run_ingests_and_exports_with_truth_labels(tmp_path: Path) -> None:
    workspace = _bazel_workspace(tmp_path)
    bin_dir = _write_bazel_shim(tmp_path / "bin", exit_code=0)

    result = _run_record(
        "--run-group",
        "rec-pass",
        "--json",
        "--",
        "bazel",
        "test",
        "//demo:x",
        cwd=workspace,
        bin_dir=bin_dir,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "completed"
    assert payload["bazel_exit_code"] == 0
    assert payload["bep_captured"] is True
    # BEP flag was injected exactly once, right after the verb.
    command = payload["command"]
    assert command == [
        "bazel",
        "test",
        f"--build_event_json_file={Path(payload['bep_path'])}",
        "//demo:x",
    ]

    output_dir = workspace / "data" / "nlfr-record" / "rec-pass"
    conn = sqlite3.connect(output_dir / "nlfr.sqlite")
    conn.row_factory = sqlite3.Row

    run = conn.execute("SELECT status, mode, run_group FROM runs").fetchone()
    assert run["status"] == "completed"
    assert run["mode"] == "record"
    assert run["run_group"] == "rec-pass"

    # Ingest happened: BEP targets/actions landed in the spine.
    assert conn.execute("SELECT COUNT(*) c FROM targets").fetchone()["c"] == 2
    assert conn.execute("SELECT COUNT(*) c FROM actions").fetchone()["c"] == 3
    # No NativeLink / no remote cache configured -> no cache events, tolerated.
    assert conn.execute("SELECT COUNT(*) c FROM cache_events").fetchone()["c"] == 0

    target = conn.execute(
        "SELECT source_kind, confidence, redaction_state FROM targets LIMIT 1"
    ).fetchone()
    assert target["source_kind"] == "collectable_v1"
    assert target["confidence"] == "high"
    assert target["redaction_state"] == "safe"

    invocation = conn.execute(
        "SELECT invocation_kind, exit_code FROM invocations"
    ).fetchone()
    assert invocation["invocation_kind"] == "bazel"
    assert invocation["exit_code"] == 0

    # Projections exported, and every proof block carries truth labels.
    graph = json.loads((output_dir / "projections" / "graph-rec-pass.json").read_text())
    proof = json.loads((output_dir / "projections" / "proof-rec-pass.json").read_text())
    assert graph["nodes"], "expected graph nodes"
    assert proof["blocks"], "expected proof blocks"
    for block in proof["blocks"]:
        assert block["source_kind"]
        assert block["confidence"]
        assert "redaction_state" in block


def test_record_failing_run_is_recorded_honestly(tmp_path: Path) -> None:
    workspace = _bazel_workspace(tmp_path)
    bin_dir = _write_bazel_shim(tmp_path / "bin", exit_code=1)

    result = _run_record(
        "--run-group",
        "rec-fail",
        "--",
        "bazel",
        "test",
        "//demo:x",
        cwd=workspace,
        bin_dir=bin_dir,
    )

    # Non-zero Bazel exit is a valid recording; the process code mirrors Bazel's.
    assert result.returncode == 1
    assert "failed" in result.stdout
    assert "bazel exit code 1" in result.stdout

    output_dir = workspace / "data" / "nlfr-record" / "rec-fail"
    conn = sqlite3.connect(output_dir / "nlfr.sqlite")
    conn.row_factory = sqlite3.Row

    run = conn.execute("SELECT status FROM runs").fetchone()
    assert run["status"] == "failed"

    # The failing build is still fully ingested — evidence is the product.
    assert conn.execute("SELECT COUNT(*) c FROM targets").fetchone()["c"] == 2

    failures = conn.execute(
        "SELECT failure_kind FROM failures ORDER BY failure_kind"
    ).fetchall()
    kinds = [row["failure_kind"] for row in failures]
    # BEP-derived failures (build_finished + target_completed) plus the wrapper's
    # own command_exit failure row.
    assert "command_exit" in kinds
    assert "build_finished" in kinds


def test_record_injects_bep_after_verb_with_startup_option(tmp_path: Path) -> None:
    workspace = _bazel_workspace(tmp_path)
    bin_dir = _write_bazel_shim(tmp_path / "bin", exit_code=0)

    # The shim asserts the BEP flag lands immediately after the verb even when a
    # startup option precedes it: bazel --nohome_rc test //demo:x
    result = _run_record(
        "--run-group",
        "rec-startup",
        "--json",
        "--",
        "bazel",
        "--nohome_rc",
        "test",
        "//demo:x",
        cwd=workspace,
        bin_dir=bin_dir,
        assert_after_verb=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["bep_captured"] is True
    command = payload["command"]
    assert command[:3] == [
        "bazel",
        "--nohome_rc",
        "test",
    ]
    assert command[3].startswith("--build_event_json_file=")
    assert command[4] == "//demo:x"

    output_dir = workspace / "data" / "nlfr-record" / "rec-startup"
    conn = sqlite3.connect(output_dir / "nlfr.sqlite")
    conn.row_factory = sqlite3.Row
    assert conn.execute("SELECT COUNT(*) c FROM targets").fetchone()["c"] == 2


def test_record_respects_user_supplied_bep_flag(tmp_path: Path) -> None:
    workspace = _bazel_workspace(tmp_path)
    bin_dir = _write_bazel_shim(tmp_path / "bin", exit_code=0)

    result = _run_record(
        "--run-group",
        "rec-userbep",
        "--json",
        "--",
        "bazel",
        "test",
        "//demo:x",
        "--build_event_json_file=custom-bep.json",
        cwd=workspace,
        bin_dir=bin_dir,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    command = payload["command"]
    # The wrapper must not add a second BEP flag; the user's flag is honored.
    bep_flags = [tok for tok in command if tok.startswith("--build_event_json_file")]
    assert bep_flags == ["--build_event_json_file=custom-bep.json"]
    # Bazel wrote the BEP at the user's path (relative to the workspace).
    assert payload["bep_path"] == str(workspace / "custom-bep.json")
    assert payload["bep_captured"] is True
    assert (workspace / "custom-bep.json").is_file()

    output_dir = workspace / "data" / "nlfr-record" / "rec-userbep"
    conn = sqlite3.connect(output_dir / "nlfr.sqlite")
    conn.row_factory = sqlite3.Row
    # Ingest came from the user-supplied BEP path.
    assert conn.execute("SELECT COUNT(*) c FROM targets").fetchone()["c"] == 2


def test_record_rejects_non_bazel_command(tmp_path: Path) -> None:
    workspace = _bazel_workspace(tmp_path)

    result = _run_record("--", "make", "build", cwd=workspace)

    # nlfr-own usage error -> EX_USAGE (64), which never collides with Bazel's 2.
    assert result.returncode == 64
    assert "bazel/bazelisk commands only" in result.stderr
    assert "nlfr run --mode generic" in result.stderr


def test_record_requires_bazel_workspace_marker(tmp_path: Path) -> None:
    bare = tmp_path / "not-a-bazel-repo"
    bare.mkdir()

    result = _run_record("--", "bazel", "test", "//x", cwd=bare)

    assert result.returncode == 64
    assert "no Bazel workspace marker found" in result.stderr


def test_record_requires_a_command(tmp_path: Path) -> None:
    workspace = _bazel_workspace(tmp_path)

    result = _run_record(cwd=workspace)

    assert result.returncode == 64
    assert "requires a command" in result.stderr


def test_record_injects_bep_after_verb_with_space_valued_startup_option(
    tmp_path: Path,
) -> None:
    """Regression: a space-valued startup option (``--bazelrc <file>``) must not
    steal the verb slot. The strict shim rejects any BEP flag injected into the
    startup segment, so this only passes if injection lands *after* ``test``.
    """

    workspace = _bazel_workspace(tmp_path)
    bin_dir = _write_strict_bazel_shim(tmp_path / "bin", exit_code=0)
    bazelrc = tmp_path / "my.bazelrc"
    bazelrc.write_text("# empty user bazelrc\n", encoding="utf-8")

    result = _run_record(
        "--run-group",
        "rec-bazelrc",
        "--json",
        "--",
        "bazel",
        "--bazelrc",
        str(bazelrc),
        "test",
        "//demo:x",
        cwd=workspace,
        bin_dir=bin_dir,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["bep_captured"] is True
    command = payload["command"]
    # The BEP flag is injected immediately AFTER the verb `test`, never into the
    # `--bazelrc <file>` startup segment (which the old first-non-`--` heuristic
    # would have corrupted by treating the bazelrc path as the verb).
    verb_i = command.index("test")
    assert command[:verb_i] == ["bazel", "--bazelrc", str(bazelrc)]
    assert command[verb_i + 1].startswith("--build_event_json_file=")
    assert command[verb_i + 2] == "//demo:x"

    output_dir = workspace / "data" / "nlfr-record" / "rec-bazelrc"
    conn = sqlite3.connect(output_dir / "nlfr.sqlite")
    conn.row_factory = sqlite3.Row
    assert conn.execute("SELECT COUNT(*) c FROM targets").fetchone()["c"] == 2


def test_record_no_known_verb_is_honest_usage_error(tmp_path: Path) -> None:
    """No recognized bazel verb and no user BEP -> refuse to guess, exit 64."""

    workspace = _bazel_workspace(tmp_path)
    bin_dir = _write_bazel_shim(tmp_path / "bin", exit_code=0)

    # Plain text (no --json): actionable stderr, exit 64, command never runs.
    result = _run_record(
        "--",
        "bazel",
        "frobnicate",
        "//demo:x",
        cwd=workspace,
        bin_dir=bin_dir,
    )
    assert result.returncode == 64
    assert "known Bazel command verb" in result.stderr
    assert "--build_event_json_file" in result.stderr
    assert result.stdout == ""
    # Nothing was recorded — no run directory was created.
    assert not (workspace / "data").exists()

    # With --json: a structured object on stdout, nothing on stderr.
    json_result = _run_record(
        "--json",
        "--",
        "bazel",
        "frobnicate",
        "//demo:x",
        cwd=workspace,
        bin_dir=bin_dir,
    )
    assert json_result.returncode == 64
    payload = json.loads(json_result.stdout)
    assert payload["status"] == "no_bazel_verb"
    assert payload["exit_code"] == 64
    assert "known Bazel command verb" in payload["record_error"]
    assert payload["bep_captured"] is False


def test_record_no_known_verb_but_user_bep_still_records(tmp_path: Path) -> None:
    """The user-supplied --build_event_json_file escape hatch bypasses verb
    detection: even with an unrecognized verb, the command runs and is ingested.
    """

    workspace = _bazel_workspace(tmp_path)
    bin_dir = _write_bazel_shim(tmp_path / "bin", exit_code=0)

    result = _run_record(
        "--run-group",
        "rec-userbep-noverb",
        "--json",
        "--",
        "bazel",
        "--build_event_json_file=custom-bep.json",
        "frobnicate",
        "//demo:x",
        cwd=workspace,
        bin_dir=bin_dir,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    # nlfr did not inject a second BEP flag; the user's flag is honored as-is.
    bep_flags = [tok for tok in payload["command"] if tok.startswith("--build_event_json_file")]
    assert bep_flags == ["--build_event_json_file=custom-bep.json"]
    assert payload["bep_captured"] is True
    assert payload["bep_path"] == str(workspace / "custom-bep.json")

    output_dir = workspace / "data" / "nlfr-record" / "rec-userbep-noverb"
    conn = sqlite3.connect(output_dir / "nlfr.sqlite")
    conn.row_factory = sqlite3.Row
    assert conn.execute("SELECT COUNT(*) c FROM targets").fetchone()["c"] == 2


def test_record_missing_bazel_executable_exits_127(tmp_path: Path) -> None:
    """A bazel/bazelisk executable that is not on PATH -> 127, never Bazel's 1."""

    workspace = _bazel_workspace(tmp_path)

    # An executable whose basename contains "bazel" (so it passes the
    # is-bazel-command check) but is guaranteed absent from PATH.
    result = _run_record(
        "--",
        "bazel-does-not-exist-xyz",
        "test",
        "//demo:x",
        cwd=workspace,
    )

    assert result.returncode == 127
    assert "not found on PATH" in result.stderr
    # No half-baked run was recorded for a command that never ran.
    assert not (workspace / "data").exists()

    # And under --json the failure is a structured object on stdout.
    json_result = _run_record(
        "--json",
        "--",
        "bazel-does-not-exist-xyz",
        "test",
        "//demo:x",
        cwd=workspace,
    )
    assert json_result.returncode == 127
    payload = json.loads(json_result.stdout)
    assert payload["status"] == "bazel_not_found"
    assert payload["exit_code"] == 127


def test_record_json_preflight_reject_emits_json_on_stdout(tmp_path: Path) -> None:
    """--json on any preflight reject yields valid JSON on stdout (not empty)."""

    workspace = _bazel_workspace(tmp_path)

    result = _run_record("--json", "--", "make", "build", cwd=workspace)

    assert result.returncode == 64
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["status"] == "non_bazel_command"
    assert payload["exit_code"] == 64
    assert "bazel/bazelisk commands only" in payload["record_error"]
    assert payload["source_kind"] == "collectable_v1"
