"""`nlfr loop` — native evaluate → fix → revalidate loop driver.

This closes the agentic loop inside the product. Each iteration validates
into ITS OWN run group (`<prefix>-iter<N>`), ingests the evidence, evaluates
it with :mod:`nlfr.evaluator` (recording the verdict into the DB as an
`evaluation` proof block), and then branches ONLY on
``verdict.next_steps[0].action``:

* ``dispatch_fix_with_evidence`` — hand the verdict's recorded failure
  excerpt (never a re-run) to the agent, apply the fix, iterate;
* ``record_environment_blocker`` — stop with exit 2: retrying into a broken
  toolchain would fabricate an agent-failure narrative from environment
  noise;
* ``none_complete`` — success: export a first-vs-last compare projection and
  the ``nlfr.loop.v1`` summary.

The decision spine that previously lived in
``scripts/two-act-spark-proof.sh`` bash is exactly this branching. The loop
does NOT manage the NativeLink server: the operator/script provides the
validation environment (``--skip-nativelink`` / ``--remote-cache`` pass
through to ``nlfr run``, which can also manage it).

Raw prompts exist only inside a temporary directory that is deleted before
the command returns; receipts carry hashes, and the loop summary is routed
through redaction before it is written.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nlfr.artifacts import write_artifact
from nlfr.commands.simulate_resources import (
    SCENARIOS_RESOURCE,
    packaged_data_dir,
    packaged_demo_workspace,
)
from nlfr.redaction import RedactionConfig, redact_payload
from nlfr.spark import (
    apply_workspace_setup,
    build_act1_prompt,
    build_act2_prompt,
    extract_python_file,
    load_spark_scenario,
)

LOOP_SCHEMA_VERSION = "nlfr.loop.v1"
BLOCKER_SCHEMA_VERSION = "nlfr.loop.blocker.v1"

_COPY_IGNORE = shutil.ignore_patterns("__pycache__", ".pytest_cache", "bazel-*")


class LoopBlocked(RuntimeError):
    """Raised when the loop must stop honestly instead of iterating."""

    def __init__(self, reason: str, detail: str | None = None, refs: list[str] | None = None):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail
        self.refs = refs or []


def run(args: argparse.Namespace) -> int:
    try:
        scenario_path = _resolve_scenario(args.scenario)
        scenario = load_spark_scenario(scenario_path)
    except (OSError, ValueError) as exc:
        print(f"cannot load loop scenario: {exc}", file=sys.stderr)
        return 2

    output_dir = Path(args.output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        print(
            f"output dir {output_dir} is not empty; a loop run must start from a "
            "fresh evidence tree (reusing a prior workspace/DB would blend runs "
            "and could fake a first-pass success). Remove it or pass a new "
            "--output-dir.",
            file=sys.stderr,
        )
        return 2
    for sub in ("receipts", "responses", "projections", "verdicts"):
        (output_dir / sub).mkdir(parents=True, exist_ok=True)
    db_path = output_dir / "nlfr.sqlite"

    # Resolve tool paths BEFORE any subprocess: agent-invoke execs the CLI from
    # a scratch cwd, where a relative --claude-bin/--bazel-bin would no longer
    # resolve (found in the first live proof run — the --version probe passed
    # from the repo cwd, the real invocation then failed FileNotFoundError).
    args.claude_bin = _resolve_bin(args.claude_bin)
    args.bazel_bin = _resolve_bin(args.bazel_bin)

    workspace = output_dir / "workspace"
    try:
        template = _resolve_workspace_template(args.workspace, scenario)
        if not workspace.exists():
            shutil.copytree(template, workspace, ignore=_COPY_IGNORE)
        apply_workspace_setup(scenario, workspace)
    except (OSError, ValueError) as exc:
        print(f"cannot prepare loop workspace: {exc}", file=sys.stderr)
        return 2

    hidden_target = str(scenario["hidden_validation"]["bazel_target"])
    target_file = str(scenario["workload"]["target_file"])
    bazel_targets = [str(t) for t in scenario["workload"].get("bazel_targets", ["//..."])]

    iterations: list[dict[str, Any]] = []
    outcome = "iteration_cap_red"
    exit_code = 1
    prior_file_content: str | None = None
    evidence_excerpt: str | None = None
    final_verdict: dict[str, Any] | None = None

    scratch_root = Path(tempfile.mkdtemp(prefix="nlfr-loop-"))
    try:
        for iteration in range(1, args.max_iterations + 1):
            run_group = f"{args.run_group_prefix}-iter{iteration}"
            try:
                record = _iterate(
                    args,
                    scenario=scenario,
                    iteration=iteration,
                    run_group=run_group,
                    workspace=workspace,
                    scratch_root=scratch_root,
                    output_dir=output_dir,
                    db_path=db_path,
                    hidden_target=hidden_target,
                    target_file=target_file,
                    bazel_targets=bazel_targets,
                    prior_file_content=prior_file_content,
                    evidence_excerpt=evidence_excerpt,
                )
            except LoopBlocked as blocked:
                _write_blocker(output_dir, blocked)
                outcome = "blocked"
                exit_code = 2
                break

            iterations.append(record["summary"])
            final_verdict = record["verdict"]
            action = record["summary"]["action_taken"]

            if action == "none_complete":
                outcome = "fixed_and_green" if iteration > 1 else "green_first_pass"
                exit_code = 0
                break
            if action == "dispatch_fix_with_evidence":
                prior_file_content = (workspace / target_file).read_text(encoding="utf-8")
                evidence_excerpt = record["verdict"]["failure_evidence"]["excerpt"]
                continue
            if action == "record_environment_blocker":
                _write_blocker(
                    output_dir,
                    LoopBlocked(
                        "recorded validation red matches toolchain failure signatures",
                        detail=json.dumps(
                            record["verdict"]["classification"], sort_keys=True
                        ),
                        refs=[f"verdict:{record['summary']['verdict_ref']}"],
                    ),
                )
                outcome = "blocked"
                exit_code = 2
                break
            # attach_missing_evidence / rerun_validation: the loop just
            # validated and evaluated with full inputs, so a degraded verdict
            # means the evidence chain is broken — stop honestly.
            _write_blocker(
                output_dir,
                LoopBlocked(
                    f"evaluation demanded {action}; the loop cannot proceed on "
                    "degraded evidence",
                    refs=[f"verdict:{record['summary']['verdict_ref']}"],
                ),
            )
            outcome = "blocked"
            exit_code = 2
            break
    finally:
        shutil.rmtree(scratch_root, ignore_errors=True)

    compare_ref = None
    if exit_code == 0 and len(iterations) > 1:
        compare_ref = _export_compare(
            db_path,
            output_dir,
            left=iterations[0]["run_group"],
            right=iterations[-1]["run_group"],
        )
        if compare_ref is None:
            outcome = "blocked"
            exit_code = 2

    _write_summary(
        output_dir,
        outcome=outcome,
        iterations=iterations,
        final_verdict=final_verdict,
        compare_ref=compare_ref,
    )
    print(
        f"nlfr loop: {outcome} after {len(iterations)} iteration(s); "
        f"summary: {output_dir / 'loop-summary.json'}"
    )
    return exit_code


def _iterate(
    args: argparse.Namespace,
    *,
    scenario: dict[str, Any],
    iteration: int,
    run_group: str,
    workspace: Path,
    scratch_root: Path,
    output_dir: Path,
    db_path: Path,
    hidden_target: str,
    target_file: str,
    bazel_targets: list[str],
    prior_file_content: str | None,
    evidence_excerpt: str | None,
) -> dict[str, Any]:
    """One loop iteration: prompt → agent → apply → validate → ingest → evaluate."""

    if iteration == 1:
        prompt = build_act1_prompt(scenario, workspace)
    else:
        assert prior_file_content is not None and evidence_excerpt is not None
        prompt = build_act2_prompt(
            scenario,
            act1_file_content=prior_file_content,
            failure_evidence=evidence_excerpt,
        )
    prompt_path = scratch_root / f"iter{iteration}-prompt.txt"
    prompt_path.write_text(prompt, encoding="utf-8")

    receipt_path = output_dir / "receipts" / f"iter{iteration}-receipt.json"
    response_path = output_dir / "responses" / f"iter{iteration}-response.md"
    agent_cwd = scratch_root / f"scratch-iter{iteration}"
    agent_cwd.mkdir(parents=True, exist_ok=True)
    invoke_cmd = [
        sys.executable, "-m", "nlfr", "agent-invoke",
        "--prompt-file", str(prompt_path),
        "--receipt-output", str(receipt_path),
        "--response-output", str(response_path),
        "--claude-bin", args.claude_bin,
        "--cwd", str(agent_cwd),
        "--timeout", str(args.agent_timeout),
        "--json",
    ]
    if args.model:
        invoke_cmd += ["--model", args.model]
    invoke = _run_subprocess(invoke_cmd, output_dir / f"iter{iteration}-invoke.json")
    if invoke.returncode != 0:
        raise LoopBlocked(
            f"headless agent CLI invocation failed in iteration {iteration} "
            "(receipt kept as evidence)",
            detail=_json_field(output_dir / f"iter{iteration}-invoke.json", "detail"),
            refs=[f"receipt:{receipt_path}"],
        )

    try:
        content = extract_python_file(response_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise LoopBlocked(
            f"agent response in iteration {iteration} carried no usable file",
            detail=str(exc),
            refs=[f"receipt:{receipt_path}"],
        )
    target = workspace / target_file
    before = hashlib.sha256(target.read_bytes()).hexdigest() if target.exists() else None
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")

    sidecar_path = scratch_root / f"iter{iteration}-sidecar.json"
    _write_sidecar(
        sidecar_path,
        receipt_path=receipt_path,
        iteration=iteration,
        target_file=target_file,
        before_hash=before,
    )

    run_json_path = output_dir / f"iter{iteration}-run.json"
    run_cmd = [
        sys.executable, "-m", "nlfr", "run",
        "--mode", args.mode,
        "--scenario", f"{scenario['scenario_id']}-iter{iteration}",
        "--run-group", run_group,
        "--workspace", str(workspace),
        "--output-dir", str(output_dir),
        "--bazel-executable", args.bazel_bin,
        f"--bazel-startup-arg=--output_base={output_dir / f'bazel-output-iter{iteration}'}",
        "--bazel-arg=--test_output=errors",
        "--change-path", target_file,
        "--provenance-sidecar", str(sidecar_path),
        "--agent-receipt", str(receipt_path),
        "--json",
    ]
    if args.skip_nativelink:
        run_cmd.append("--skip-nativelink")
    if args.no_remote_cache:
        run_cmd.append("--no-remote-cache")
    elif args.remote_cache:
        run_cmd += ["--remote-cache", args.remote_cache]
    run_cmd += bazel_targets
    run_result = _run_subprocess(run_cmd, run_json_path)
    try:
        run_payload = _load_json(run_json_path)
    except (OSError, ValueError):
        # nlfr run's early-error paths (rc 2) print to stderr and emit no JSON;
        # an honest blocker beats a traceback.
        raise LoopBlocked(
            f"validation run in iteration {iteration} produced no run metadata "
            f"(rc={run_result.returncode})",
            detail=run_result.stderr[-2000:],
            refs=[f"run:{run_json_path}"],
        )
    status = run_payload.get("status")
    if status not in ("completed", "failed"):
        raise LoopBlocked(
            f"validation run in iteration {iteration} ended in unexpected "
            f"status {status!r} (rc={run_result.returncode})",
            detail=run_payload.get("detail"),
            refs=[f"run:{run_json_path}"],
        )
    artifact_root = Path(str(run_payload["artifact_root"]))
    run_key = str(run_payload["run_key"])

    write_artifact(
        artifact_root,
        artifact_key="agent-response.md",
        data=response_path.read_bytes(),
        producer_command=["nlfr", "loop"],
        config_hash=None,
        redaction_state="safe",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["command:nlfr-loop", "agent-response.md"],
    )

    ingest = _run_subprocess(
        [
            sys.executable, "-m", "nlfr", "ingest", str(artifact_root),
            "--database", str(db_path),
            "--run-key", run_key,
            "--run-group", run_group,
            "--source-kind", "collectable_v1",
            "--json",
        ],
        output_dir / f"iter{iteration}-ingest.json",
    )
    if ingest.returncode != 0:
        raise LoopBlocked(
            f"evidence ingest failed in iteration {iteration}",
            detail=ingest.stderr[-2000:],
            refs=[f"artifact_root:{artifact_root}"],
        )

    for kind, cmd_name in (("action-graph", "graph"), ("proof", "proof")):
        _run_subprocess(
            [
                sys.executable, "-m", "nlfr", cmd_name, "export",
                "--db", str(db_path),
                "--run-group", run_group,
                "--output", str(output_dir / "projections" / f"iter{iteration}-{kind}.json"),
            ],
            None,
        )

    verdict_path = output_dir / "verdicts" / f"iter{iteration}-verdict.json"
    evaluate = _run_subprocess(
        [
            sys.executable, "-m", "nlfr", "evaluate",
            "--db", str(db_path),
            "--run-group", run_group,
            "--artifact-root", str(artifact_root),
            "--attribution-target", hidden_target,
            "--workspace", str(workspace),
            "--record",
            "--output", str(verdict_path),
        ],
        None,
    )
    if evaluate.returncode != 0:
        raise LoopBlocked(
            f"evaluation failed in iteration {iteration}",
            detail=evaluate.stderr[-2000:],
            refs=[f"run-group:{run_group}"],
        )
    verdict = _load_json(verdict_path)
    action = verdict["next_steps"][0]["action"] if verdict.get("next_steps") else "none"

    receipt = _load_json(receipt_path)
    provenance_class = _provenance_class_for(receipt)

    return {
        "verdict": verdict,
        "summary": {
            "iteration": iteration,
            "run_group": run_group,
            "status": status,
            "action_taken": action,
            "classification": (verdict.get("classification") or {}).get("classification"),
            "provenance_class": provenance_class,
            "verdict_ref": str(verdict_path),
            "receipt_ref": str(receipt_path),
        },
    }


def _provenance_class_for(receipt: dict[str, Any]) -> str:
    """Mirror the recorder's ladder for the loop summary (labels, not trust)."""

    from nlfr.agent_receipt import is_live_receipt

    if is_live_receipt(receipt):
        return "receipt_verified_v1"
    return "stub_receipt_v1"


def _write_sidecar(
    sidecar_path: Path,
    *,
    receipt_path: Path,
    iteration: int,
    target_file: str,
    before_hash: str | None,
) -> None:
    receipt = _load_json(receipt_path)
    model = (
        (receipt.get("model") or {}).get("resolved")
        or (receipt.get("model") or {}).get("requested")
        or "unresolved"
    )
    payload = {
        "schema_version": "nlfr.agent_provenance.sidecar.v1",
        "adapter": "nlfr-loop",
        "change_class": "bounded_agent_v1",
        "agent": {
            "kind": "claude_code_adapter_v1",
            "name": f"loop-iter{iteration}",
            "model": model,
            "prompt_sha256": receipt["prompt_sha256"],
            "input_signal": "redacted: prompt withheld, hash retained",
        },
        "change_before_hashes": {target_file: before_hash},
    }
    sidecar_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _export_compare(db_path: Path, output_dir: Path, *, left: str, right: str) -> str | None:
    compare_path = output_dir / "projections" / f"compare-{left}-vs-{right}.json"
    result = _run_subprocess(
        [
            sys.executable, "-m", "nlfr", "compare", "export",
            "--db", str(db_path),
            "--left", left,
            "--right", right,
            "--output", str(compare_path),
        ],
        None,
    )
    return str(compare_path) if result.returncode == 0 else None


def _write_blocker(output_dir: Path, blocked: LoopBlocked) -> None:
    payload = {
        "schema_version": BLOCKER_SCHEMA_VERSION,
        "generated_at": _timestamp(),
        "reason": blocked.reason,
        "detail": blocked.detail,
        "source_kind": "derived_v1",
        "confidence": "high",
        "evidence_refs": blocked.refs,
        "redaction_state": "safe",
    }
    result = redact_payload(payload, RedactionConfig())
    (output_dir / "loop-blocker.json").write_text(
        json.dumps(result.payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"nlfr loop blocked: {blocked.reason}", file=sys.stderr)


def _write_summary(
    output_dir: Path,
    *,
    outcome: str,
    iterations: list[dict[str, Any]],
    final_verdict: dict[str, Any] | None,
    compare_ref: str | None,
) -> None:
    final_status = (final_verdict or {}).get("status") or {}
    final_cache = (final_verdict or {}).get("cache") or {}
    checks = {
        "first_iteration_red": bool(iterations) and iterations[0]["status"] == "failed",
        # True only when a RED first iteration was honestly attributed; a green
        # first pass reads false here and true under first-pass outcome — the
        # check never claims "the recorder caught the agent" without a red.
        "honest_classification": bool(iterations)
        and iterations[0]["status"] == "failed"
        and iterations[0]["classification"] == "scenario_validation_failure",
        "fix_receipt_present": len(iterations) > 1
        and Path(iterations[-1]["receipt_ref"]).exists(),
        "final_green": final_status.get("status") == "ok",
        "warm_cache_final": bool(final_cache.get("hits")),
        "compare_exported": compare_ref is not None,
    }
    evidence_refs = [f"verdict:{item['verdict_ref']}" for item in iterations]
    if compare_ref:
        evidence_refs.append(f"compare:{compare_ref}")
    payload = {
        "schema_version": LOOP_SCHEMA_VERSION,
        "generated_at": _timestamp(),
        "outcome": outcome,
        "iterations": iterations,
        "checks": checks,
        "compare_ref": compare_ref,
        "source_kind": "derived_v1",
        "confidence": "medium",
        "evidence_refs": evidence_refs,
        "redaction_state": "safe",
    }
    result = redact_payload(payload, RedactionConfig())
    (output_dir / "loop-summary.json").write_text(
        json.dumps(result.payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _resolve_scenario(name_or_path: str) -> Path:
    candidate = Path(name_or_path)
    if candidate.suffix == ".json" and candidate.is_file():
        return candidate
    packaged = packaged_data_dir(SCENARIOS_RESOURCE)
    repo = Path(__file__).resolve().parents[3] / "demo" / "scenarios"
    for base in (packaged, repo):
        if base is None:
            continue
        scenario_path = base / f"{name_or_path}.json"
        if scenario_path.is_file():
            return scenario_path
    raise ValueError(
        f"scenario {name_or_path!r} not found (tried packaged wheel data and demo/scenarios)"
    )


def _resolve_workspace_template(explicit: str | None, scenario: dict[str, Any]) -> Path:
    if explicit:
        template = Path(explicit)
        if not template.is_dir():
            raise ValueError(f"--workspace template does not exist: {template}")
        return template
    repo_root = Path(__file__).resolve().parents[3]
    repo_template = repo_root / str(scenario["workload"].get("repo_root", ""))
    if repo_template.is_dir():
        return repo_template
    packaged = packaged_demo_workspace()
    if packaged is not None:
        return packaged
    raise ValueError(
        "no workspace template found: pass --workspace PATH (tried the scenario's "
        "repo_root in a source checkout and the packaged demo workspace)"
    )


def _resolve_bin(value: str) -> str:
    """Absolutize a path-like tool argument; leave bare command names to PATH."""

    if "/" in value:
        candidate = Path(value)
        if candidate.exists():
            return str(candidate.resolve())
    return value


def _run_subprocess(cmd: list[str], stdout_path: Path | None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(cmd, text=True, capture_output=True, check=False)
    if stdout_path is not None:
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stdout_path.write_text(result.stdout, encoding="utf-8")
    return result


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _json_field(path: Path, field: str) -> str | None:
    try:
        value = _load_json(path).get(field)
        return str(value) if value is not None else None
    except (OSError, ValueError):
        return None


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``loop`` subcommand."""

    parser = subparsers.add_parser(
        "loop",
        help="drive the evaluate → fix → revalidate agent loop natively",
        description=(
            "Drive the closed agent loop from recorded evidence: validate, "
            "ingest, evaluate (verdict recorded as an evaluation proof block), "
            "then branch only on the verdict's first next step — dispatching "
            "the fix agent with the recorded failure excerpt, stopping on an "
            "environment blocker, or finishing green with a compare projection."
        ),
    )
    parser.add_argument(
        "--scenario",
        required=True,
        help="spark scenario name (packaged/demo) or path to a scenario JSON",
    )
    parser.add_argument("--mode", default="cache-only", help="nlfr run mode")
    parser.add_argument(
        "--skip-nativelink",
        action="store_true",
        help="pass through to nlfr run (operator manages the cache server)",
    )
    parser.add_argument("--remote-cache", help="Bazel remote cache endpoint pass-through")
    parser.add_argument(
        "--no-remote-cache",
        action="store_true",
        help="run plain Bazel with no remote cache (pass-through)",
    )
    parser.add_argument("--claude-bin", default="claude", help="agent CLI executable")
    parser.add_argument("--bazel-bin", default="bazel", help="Bazel executable")
    parser.add_argument("--model", help="agent model to request (optional)")
    parser.add_argument(
        "--agent-timeout", type=float, default=240.0, help="agent CLI timeout seconds"
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=2,
        help="hard iteration cap (red at the cap exits 1; no retry spiral)",
    )
    parser.add_argument(
        "--run-group-prefix",
        default="loop",
        help="each iteration validates into run group <prefix>-iter<N>",
    )
    parser.add_argument(
        "--output-dir",
        default="data/nlfr-loop",
        help="directory for evidence DB, receipts, verdicts, projections, summary",
    )
    parser.add_argument(
        "--workspace",
        help="workspace template override (default: scenario repo_root > packaged demo)",
    )
    parser.set_defaults(handler=run)
