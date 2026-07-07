"""Simulated agent workflow command."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nlfr.artifacts import write_artifact
from nlfr.change_evidence import derive_change_details, patch_applied_from
from nlfr.config import WorkspaceResolutionError, resolve_workspace
from nlfr.db import connect, initialize
from nlfr.db.ingest import (
    upsert_artifact,
    upsert_change,
    upsert_proof_block,
    upsert_run,
)


def run(args: argparse.Namespace) -> int:
    """Apply demo agent patches and record simulated provenance."""

    try:
        template, template_notice = resolve_workspace(Path.cwd(), args.workspace_template)
    except WorkspaceResolutionError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if template_notice:
        print(template_notice, file=sys.stderr)
    args.workspace_template = str(template)

    try:
        scenario_paths = _scenario_paths(args)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    for scenario_path in scenario_paths:
        try:
            results.append(_run_scenario(args, scenario_path, output_dir))
        except (ValueError, RuntimeError) as exc:
            print(str(exc), file=sys.stderr)
            return 2

    payload = {
        "schema_version": "nlfr.agent_simulation_batch.v1",
        "generated_at": _timestamp(),
        "output_dir": str(output_dir),
        "run_group": args.run_group,
        "scenarios": results,
        "source_kind": "simulated_v1",
        "confidence": "medium",
        "redaction_state": "safe",
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"simulated {len(results)} agent scenario(s) into {output_dir}")
        for item in results:
            print(f"- {item['scenario_id']}: {item['build']['status']}")
    return 0


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``simulate`` command on ``subparsers``."""

    parser = subparsers.add_parser(
        "simulate",
        help="simulate agent patches and record agent-to-build provenance",
        description="Apply deterministic demo agent patches and record provenance.",
    )
    parser.add_argument(
        "--scenario",
        action="append",
        help="scenario id or JSON path; repeat to run a subset",
    )
    parser.add_argument(
        "--scenario-dir",
        default=str(_repo_root() / "demo" / "scenarios"),
        help="directory containing demo scenario JSON files",
    )
    parser.add_argument(
        "--workspace-template",
        default=None,
        help=(
            "Bazel workspace copied before each simulated agent patch. Default: "
            "the bundled demo workspace inside the NLFR source checkout, else the "
            "current directory when it holds a Bazel marker"
        ),
    )
    parser.add_argument(
        "--output-dir",
        default="data/agent-sim",
        help="directory for copied workspaces, provenance, runs, and SQLite",
    )
    parser.add_argument(
        "--run-group",
        default="agent-sim",
        help="run group used by recorder and projection exports",
    )
    parser.add_argument(
        "--mode",
        choices=("cache-only",),
        default="cache-only",
        help="recorder execution mode",
    )
    parser.add_argument(
        "--skip-run",
        action="store_true",
        help="apply patches and record simulated provenance without invoking nlfr run",
    )
    parser.add_argument(
        "--ingest",
        action="store_true",
        help="after a real run, ingest its Bazel artifacts so validation/cache evidence joins the chain",
    )
    parser.add_argument(
        "--skip-nativelink",
        action="store_true",
        help="pass through to nlfr run when using an already-running NativeLink cache",
    )
    parser.add_argument(
        "--nativelink-config",
        default=str(_repo_root() / "demo" / "nativelink" / "cache-only.json"),
        help="NativeLink config passed to nlfr run",
    )
    parser.add_argument(
        "--nativelink-executable",
        default="nativelink",
        help="NativeLink executable passed to nlfr run",
    )
    parser.add_argument(
        "--bazel-executable",
        default="bazel",
        help="Bazel executable passed to nlfr run",
    )
    parser.add_argument(
        "--remote-cache",
        default="grpc://127.0.0.1:50051",
        help="remote cache endpoint passed to nlfr run",
    )
    parser.add_argument(
        "--bazel-startup-arg",
        action="append",
        default=[],
        help="Bazel startup argument passed to nlfr run; repeatable",
    )
    parser.add_argument("--json", action="store_true", help="emit machine-readable summary")
    parser.set_defaults(handler=run)


def _run_scenario(
    args: argparse.Namespace,
    scenario_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    scenario = _load_scenario(scenario_path)
    scenario_id = _required_string(scenario, "scenario_id", scenario_path)
    workspace = output_dir / "workspaces" / scenario_id
    _copy_workspace(Path(args.workspace_template).resolve(), workspace)

    affected_paths = _affected_paths(scenario)
    before_hashes = {path: _file_sha256(workspace / path) for path in affected_paths}
    patch_diff = _patch_diff(scenario, scenario_path)
    _apply_patch(workspace, patch_diff, scenario_id)
    after_hashes = {path: _file_sha256(workspace / path) for path in affected_paths}

    build = (
        _simulate_only_run(args, scenario, output_dir)
        if args.skip_run
        else _execute_recorder_run(args, scenario, workspace, output_dir)
    )
    if getattr(args, "ingest", False) and not args.skip_run:
        build["ingest"] = _ingest_run_artifacts(args, build, output_dir)
    provenance = _provenance_payload(
        scenario=scenario,
        scenario_path=scenario_path,
        workspace=workspace,
        affected_paths=affected_paths,
        before_hashes=before_hashes,
        after_hashes=after_hashes,
        patch_diff=patch_diff,
        build=build,
        run_group=args.run_group,
        mode=args.mode,
    )
    artifact_entry = _write_provenance_artifact(provenance, build, output_dir)
    _record_provenance_in_db(
        output_dir=output_dir,
        build=build,
        provenance=provenance,
        artifact_key=artifact_entry["artifact_key"],
        artifact_path=artifact_entry["path"],
        artifact_sha256=artifact_entry["sha256"],
        artifact_size=artifact_entry["size_bytes"],
    )

    stable_path = output_dir / "provenance" / f"{scenario_id}.json"
    stable_path.parent.mkdir(parents=True, exist_ok=True)
    stable_path.write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n")

    return {
        "scenario_id": scenario_id,
        "agent": provenance["agent"],
        "workspace": str(workspace),
        "provenance_path": str(stable_path),
        "artifact_key": artifact_entry["artifact_key"],
        "build": build,
        "source_kind": "simulated_v1",
        "confidence": "medium",
        "evidence_refs": provenance["evidence_refs"],
        "redaction_state": "safe",
    }


def _scenario_paths(args: argparse.Namespace) -> list[Path]:
    scenario_dir = Path(args.scenario_dir).resolve()
    requested = args.scenario or []
    if not requested:
        paths = sorted(scenario_dir.glob("*.json"))
        if not paths:
            raise ValueError(f"no scenarios found in {scenario_dir}")
        return paths

    paths: list[Path] = []
    for item in requested:
        candidate = Path(item)
        if candidate.suffix == ".json" or candidate.parent != Path("."):
            path = candidate if candidate.is_absolute() else Path.cwd() / candidate
        else:
            path = scenario_dir / f"{item}.json"
        if not path.exists():
            raise ValueError(f"scenario not found: {item}")
        paths.append(path.resolve())
    return paths


def _load_scenario(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid scenario JSON at {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"invalid scenario JSON at {path}: expected object")
    return payload


def _copy_workspace(template: Path, destination: Path) -> None:
    if not template.exists():
        raise ValueError(f"workspace template not found: {template}")
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(
        template,
        destination,
        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "bazel-*"),
    )


def _apply_patch(workspace: Path, patch_diff: str, scenario_id: str) -> None:
    try:
        result = subprocess.run(
            ["git", "apply", "--whitespace=nowarn", "-"],
            cwd=workspace,
            input=patch_diff,
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("missing git executable required to apply scenario patches") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"failed to apply scenario patch {scenario_id}: {detail}")


def _execute_recorder_run(
    args: argparse.Namespace,
    scenario: dict[str, Any],
    workspace: Path,
    output_dir: Path,
) -> dict[str, Any]:
    scenario_id = _required_string(scenario, "scenario_id", Path("<scenario>"))
    command = [
        sys.executable,
        "-m",
        "nlfr",
        "run",
        "--scenario",
        scenario_id,
        "--run-group",
        args.run_group,
        "--workspace",
        str(workspace),
        "--output-dir",
        str(output_dir),
        "--mode",
        args.mode,
        "--nativelink-config",
        args.nativelink_config,
        "--nativelink-executable",
        args.nativelink_executable,
        "--bazel-executable",
        args.bazel_executable,
        "--remote-cache",
        args.remote_cache,
        "--json",
    ]
    for startup_arg in args.bazel_startup_arg:
        command.append(f"--bazel-startup-arg={startup_arg}")
    if args.skip_nativelink:
        command.append("--skip-nativelink")
    command.append(_target_for_scenario(scenario))

    env = os.environ.copy()
    env["PYTHONPATH"] = str(_repo_root() / "src")
    result = subprocess.run(
        command,
        cwd=_repo_root(),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"nlfr run did not emit JSON for {scenario_id}: {result.stderr.strip()}"
        ) from exc
    return {
        "status": payload.get("status", "unknown"),
        "returncode": result.returncode,
        "run_id": payload.get("run_id"),
        "run_key": payload.get("run_key"),
        "run_group": args.run_group,
        "mode": args.mode,
        "target": _target_for_scenario(scenario),
        "artifact_root": payload.get("artifact_root"),
        "results": payload.get("results", []),
        "source_kind": "collectable_v1",
        "confidence": "high" if payload.get("run_id") else "unknown",
        "redaction_state": "safe",
    }


def _ingest_run_artifacts(
    args: argparse.Namespace,
    build: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    """Ingest a real run's Bazel artifacts into the same DB and run group.

    This joins targets/actions/cache_events/failures to the run that the agent
    patch validated, so the action graph can show the full
    agent -> change -> run -> validation -> cache chain.
    """

    artifact_root = build.get("artifact_root")
    run_key = build.get("run_key")
    if not artifact_root or not run_key:
        return {"status": "skipped", "reason": "missing artifact_root or run_key"}

    command = [
        sys.executable,
        "-m",
        "nlfr",
        "ingest",
        str(artifact_root),
        "--database",
        str(output_dir / "nlfr.sqlite"),
        "--run-key",
        str(run_key),
        "--run-group",
        args.run_group,
        "--source-kind",
        "collectable_v1",
        "--json",
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(_repo_root() / "src")
    result = subprocess.run(
        command,
        cwd=_repo_root(),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return {
            "status": "ingest_failed",
            "returncode": result.returncode,
            "detail": result.stderr.strip() or result.stdout.strip(),
        }
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"status": "ingest_unparsed", "returncode": result.returncode}
    return {
        "status": "ingested",
        "returncode": result.returncode,
        "counts": payload.get("counts", {}),
    }


def _simulate_only_run(
    args: argparse.Namespace,
    scenario: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    scenario_id = _required_string(scenario, "scenario_id", Path("<scenario>"))
    run_key = f"simulation:{scenario_id}:{args.mode}"
    conn = initialize(connect(output_dir / "nlfr.sqlite"))
    run_id = upsert_run(
        conn,
        stable_key=run_key,
        run_group=args.run_group,
        scenario=scenario_id,
        mode=args.mode,
        status="simulated_only",
        source_kind="simulated_v1",
        confidence="medium",
        evidence_refs=[f"scenario:{scenario_id}"],
        redaction_state="safe",
    )
    artifact_root = output_dir / "simulations" / scenario_id / "artifacts"
    artifact_root.mkdir(parents=True, exist_ok=True)
    return {
        "status": "simulated_only",
        "returncode": 0,
        "run_id": run_id,
        "run_key": run_key,
        "run_group": args.run_group,
        "mode": args.mode,
        "target": _target_for_scenario(scenario),
        "artifact_root": str(artifact_root),
        "results": [],
        "source_kind": "simulated_v1",
        "confidence": "medium",
        "redaction_state": "safe",
    }


def _provenance_payload(
    *,
    scenario: dict[str, Any],
    scenario_path: Path,
    workspace: Path,
    affected_paths: list[str],
    before_hashes: dict[str, str | None],
    after_hashes: dict[str, str | None],
    patch_diff: str,
    build: dict[str, Any],
    run_group: str,
    mode: str,
) -> dict[str, Any]:
    scenario_id = _required_string(scenario, "scenario_id", scenario_path)
    patch_sha = hashlib.sha256(patch_diff.encode("utf-8")).hexdigest()
    agent = scenario.get("simulated_agent") if isinstance(scenario.get("simulated_agent"), dict) else {}
    agent_name = str(agent.get("name") or f"simulated-agent-{scenario_id}")
    evidence_refs = [
        f"scenario:{scenario_id}",
        f"agent:{agent_name}",
        f"patch:sha256:{patch_sha}",
    ]
    prompt_sha = _prompt_sha256(agent)
    if prompt_sha:
        evidence_refs.append(f"prompt:sha256:{prompt_sha}")
    if build.get("run_id"):
        evidence_refs.append(f"run:{build['run_id']}")

    # Per-path change evidence, identical in shape to `nlfr run --mode generic`
    # (GitHub issue #62). Simulate never supplies git baselines: its before/after
    # come from a copied pristine template hashed, a deterministic scenario diff
    # applied, then re-hashed — a fully observed fixture window, so every path
    # carries changed_basis == "simulate_fixture" and no unobservable caveat.
    change_details = derive_change_details(
        affected_paths,
        before_hashes,
        after_hashes,
        window_basis="simulate_fixture",
        unobservable_note=None,
    )

    return {
        "schema_version": "nlfr.agent_provenance.v1",
        "generated_at": _timestamp(),
        "scenario_id": scenario_id,
        "scenario_path": str(scenario_path),
        "title": scenario.get("title"),
        "agent": {
            "kind": agent.get("kind", "simulated_v1"),
            "name": agent_name,
            "input_signal": agent.get("input_signal"),
            "model": agent.get("model"),
            "prompt_sha256": _prompt_sha256(agent),
        },
        "change": {
            "change_class": scenario.get("change_class"),
            "affected_paths": affected_paths,
            "before_hashes": before_hashes,
            "after_hashes": after_hashes,
            "patch_sha256": patch_sha,
            "paths": change_details,
            "patch_applied": patch_applied_from(change_details),
        },
        "workspace": str(workspace),
        "build": build,
        "run_group": run_group,
        "mode": mode,
        "expected_result": scenario.get("expected_result"),
        "proof_claims": scenario.get("proof_claims", []),
        "source_kind": "simulated_v1",
        "confidence": "medium",
        "evidence_refs": evidence_refs,
        "redaction_state": "safe",
    }


def _write_provenance_artifact(
    provenance: dict[str, Any],
    build: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    scenario_id = str(provenance["scenario_id"])
    artifact_root_value = build.get("artifact_root")
    artifact_root = Path(str(artifact_root_value)) if artifact_root_value else output_dir / "artifacts"
    entry = write_artifact(
        artifact_root,
        artifact_key="agent-provenance.json",
        data=json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        producer_command=["nlfr", "simulate", "--scenario", scenario_id],
        config_hash=None,
        redaction_state="safe",
        source_kind="simulated_v1",
        confidence="medium",
        evidence_refs=provenance["evidence_refs"],
    )
    return entry.to_manifest()


def _record_provenance_in_db(
    *,
    output_dir: Path,
    build: dict[str, Any],
    provenance: dict[str, Any],
    artifact_key: str,
    artifact_path: str,
    artifact_sha256: str,
    artifact_size: int,
) -> None:
    run_id = build.get("run_id")
    run_key = build.get("run_key")
    if not run_id or not run_key:
        return

    conn = initialize(connect(output_dir / "nlfr.sqlite"))
    scenario_id = str(provenance["scenario_id"])
    run_row = conn.execute(
        "SELECT id FROM runs WHERE stable_key = ?",
        (run_key,),
    ).fetchone()
    if run_row is None:
        raise RuntimeError(f"missing recorded run row for provenance: {run_key}")
    db_run_id = run_row["id"]

    for path in provenance["change"]["affected_paths"]:
        before_hash = provenance["change"]["before_hashes"].get(path)
        after_hash = provenance["change"]["after_hashes"].get(path)
        upsert_change(
            conn,
            stable_key=f"{run_key}:change:{scenario_id}:{path}",
            run_id=db_run_id,
            change_kind=provenance["change"].get("change_class"),
            path=path,
            before_hash=before_hash,
            after_hash=after_hash,
            summary=f"{scenario_id} touched {path}",
            source_kind="simulated_v1",
            confidence="medium",
            evidence_refs=provenance["evidence_refs"],
            redaction_state="safe",
        )

    upsert_artifact(
        conn,
        stable_key=f"{run_key}:artifact:agent-provenance",
        run_id=db_run_id,
        artifact_key=artifact_key,
        artifact_path=artifact_path,
        manifest_path="artifact_manifest.json",
        sha256=artifact_sha256,
        size_bytes=artifact_size,
        content_type="application/json",
        producer_command=["nlfr", "simulate", "--scenario", scenario_id],
        config_hash=None,
        source_kind="simulated_v1",
        confidence="medium",
        evidence_refs=provenance["evidence_refs"],
        redaction_state="safe",
    )
    upsert_proof_block(
        conn,
        stable_key=f"{run_key}:proof:agent-provenance:{scenario_id}",
        run_id=db_run_id,
        block_key=f"agent-provenance:{scenario_id}",
        block_kind="agent_provenance",
        title=f"Agent Provenance: {provenance['agent']['name']}",
        summary=f"{scenario_id} patch recorded with build status {build['status']}.",
        payload=provenance,
        source_kind="simulated_v1",
        confidence="medium",
        evidence_refs=provenance["evidence_refs"],
        redaction_state="safe",
    )


def _derive_patch_applied(
    affected_paths: list[str],
    before_hashes: dict[str, str | None],
    after_hashes: dict[str, str | None],
) -> bool:
    """Derive whether the patch changed the workspace, from real evidence.

    ``patch_applied`` was previously a hardcoded ``True`` literal — the same
    literal-vs-evidence class fixed for ``nlfr run`` in #52 (this is the #56
    follow-up). Simulate copies a workspace, hashes the affected files, applies
    the scenario diff, then hashes again; those before/after hashes are the
    ground truth. The flag is True iff at least one affected file's content hash
    actually changed. (A failed ``git apply`` never reaches here: it raises in
    :func:`_apply_patch`.)

    As of #62 this delegates to the shared :func:`nlfr.change_evidence` derivation
    so the boolean and the per-path ``change.paths`` map are computed identically.
    """

    return patch_applied_from(
        derive_change_details(
            affected_paths,
            before_hashes,
            after_hashes,
            window_basis="simulate_fixture",
            unobservable_note=None,
        )
    )


def _affected_paths(scenario: dict[str, Any]) -> list[str]:
    workload = scenario.get("workload")
    if not isinstance(workload, dict):
        return []
    paths = workload.get("affected_paths")
    if not isinstance(paths, list):
        return []
    return [str(path) for path in paths]


def _patch_diff(scenario: dict[str, Any], scenario_path: Path) -> str:
    patch = scenario.get("patch")
    if not isinstance(patch, dict):
        raise ValueError(f"scenario has no patch object: {scenario_path}")
    diff = patch.get("diff")
    if not isinstance(diff, str) or not diff.strip():
        raise ValueError(f"scenario patch has no diff: {scenario_path}")
    if patch.get("format") != "unified_diff":
        raise ValueError(f"unsupported patch format in {scenario_path}: {patch.get('format')}")
    return diff


def _target_for_scenario(scenario: dict[str, Any]) -> str:
    workload = scenario.get("workload")
    if isinstance(workload, dict):
        targets = workload.get("bazel_targets")
        if isinstance(targets, list) and targets:
            return str(targets[0])
    return "//..."


def _required_string(payload: dict[str, Any], key: str, path: Path) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"scenario missing string field {key}: {path}")
    return value


def _file_sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _prompt_sha256(agent: dict[str, Any]) -> str | None:
    """Return a prompt hash for bounded-LLM provenance, never the raw prompt.

    A scenario may supply either a precomputed ``prompt_sha256`` or a raw
    ``prompt`` string. If a raw prompt is supplied it is hashed immediately and
    discarded; the raw prompt is never stored or exported (AGENTS.md privacy).
    """

    precomputed = agent.get("prompt_sha256")
    if isinstance(precomputed, str) and precomputed:
        return precomputed
    prompt = agent.get("prompt")
    if isinstance(prompt, str) and prompt:
        return hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    return None


def _timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]
