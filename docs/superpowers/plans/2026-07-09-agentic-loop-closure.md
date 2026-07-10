# Agentic Loop Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> **This session:** executed inline (user directive), TDD per task, commit per task.

**Goal:** `nlfr evaluate` (deterministic truth-labeled verdict + next_steps over recorded evidence), `nlfr loop` (native red→evaluate→fix→green driver), `nlfr receipt import` (cloud/pod receipts, honest `receipt_imported_v1`), then ship v0.3.0.

**Architecture:** Pure evaluator module over SQLite evidence + proof-packet rollups; thin argparse commands following repo idioms; loop orchestrates existing subcommands via subprocess (as `simulate_cmd._execute_recorder_run` already does) with spark/evaluator as module calls. Spec: `docs/superpowers/specs/2026-07-09-agentic-loop-closure-design.md` (includes redteam amendments — read it first).

**Tech Stack:** Python stdlib only (argparse/sqlite3/json/hashlib/pathlib), pytest via `uv run pytest -q` (NEVER system python3 — needs ≥3.10).

## Global Constraints

- Every emitted payload: truth quad; verdict/loop outputs hardcode `source_kind: "derived_v1"`, confidence = weakest input (`high` only if all inputs high, `low` if any low, else `medium`), evidence_refs = union of consulted refs, `redact_payload()` before write.
- next_steps precedence (tested contract): `record_environment_blocker` > `rerun_validation` > `dispatch_fix_with_evidence` > `attach_missing_evidence` > `none_complete`.
- Imported receipts: NEVER `is_live_receipt`/`live: true`/`receipt_verified_v1`; dedicated builder sets `provenance_class="receipt_imported_v1"`, summary `live: false`, `observed_by_nlfr: false`.
- Loop: one run group per iteration (`<prefix>-iter<N>`), evaluate called with explicit group id; no schema migration needed (`proof_blocks.block_kind` unconstrained TEXT).
- CLI idioms: `connect_readonly` → catch `UnreadableDatabaseError` → stderr + exit 2; `write_or_print`; new subcommand names added to `tests/test_cli.py` help assertion list.
- Exit codes: 0 evaluated/success; 1 only behind `--fail-on-action-required` (evaluate) or red-at-cap (loop); 2 cannot-evaluate/blocker.

---

### Task 1: Evaluator core — `src/nlfr/evaluator.py`

**Files:** Create `src/nlfr/evaluator.py`; Modify `src/nlfr/spark.py` (delegate wrappers); Test `tests/test_evaluator.py`.

**Produces (later tasks consume):**
- `EVALUATION_SCHEMA_VERSION = "nlfr.evaluation.v1"`
- `classify_validation_failure(artifact_root, *, attribution_target=None, signatures=TOOLCHAIN_FAILURE_SIGNATURES) -> dict` (moved from spark; values `scenario_validation_failure|toolchain_failure|unattributed_failure`; with `attribution_target=None`, attribution key `attribution_target_referenced` is `None` and non-toolchain reds classify `unattributed_failure` only when a target was given — else `scenario_validation_failure` requires a target, so no-target non-toolchain reds are `unclassified_red`… **decision:** keep it simple: no target + no toolchain match → `unattributed_failure` with `attribution_target_referenced: null`).
- `failure_excerpt(artifact_root, *, max_lines=80)` (moved from spark, same behavior).
- `TOOLCHAIN_FAILURE_SIGNATURES` (moved; spark re-exports).
- `evaluate_run_group(conn, run_group, *, artifact_root=None, attribution_target=None) -> dict` — payload keys: `schema_version, generated_at, run_group, status{status,failure_count}, failures[], classification{...}, failure_evidence{excerpt, excerpt_sha256, refs}|None, cache{hits,misses,hit_rate}, artifact_verification, agent_provenance{classes:{...counts}}, next_steps[], source_kind, confidence, evidence_refs, redaction_state`. Raises `MissingRunGroupError` (reuse compare's, `side="evaluate"`).
- `next_steps_for(verdict_parts) -> list[dict]` — pure precedence function.
- spark.py keeps `classify_validation_failure(artifact_root, *, hidden_target)` + `failure_excerpt` + `TOOLCHAIN_FAILURE_SIGNATURES` as thin delegates (existing tests/scripts unchanged; evaluator must not import spark).

Status via `proof_markdown.validation_status(export_proof_packet(conn, run_group))`. Rows via `projectors.common.rows/run_rows`. `rerun_validation` trigger: any `changes` row with `created_at` strictly newer than the newest run's `finished_at/created_at` in the group. Excerpt is returned in-payload only under `failure_evidence.excerpt` (already path-redacted by `_HOME_PATH` rule) and whole payload passes `redact_payload`.

Tests (in-proc SQLite per `test_pr_comment_export.py` style): green→`none_complete`; red honest (fixture logs with target ref)→`dispatch_fix_with_evidence` with excerpt sha; red toolchain→`record_environment_blocker` first even when honest-looking change pending (precedence); red no logs→`unclassified` + `attach_missing_evidence` naming `raw_logs`; stale change→`rerun_validation` outranks dispatch; labels always `derived_v1` + weakest-input confidence; payload redact-clean; unknown group raises `MissingRunGroupError`; spark wrappers still importable with old signatures.

- [x] failing tests → [x] implement → [x] suite green → [x] commit

### Task 2: `nlfr evaluate` command

**Files:** Create `src/nlfr/commands/evaluate_cmd.py`; Modify `src/nlfr/commands/__init__.py`, `tests/test_cli.py` (add "evaluate" to help list); Test `tests/test_evaluate_cmd.py`.

Flags per spec (§2): `--db`, `--run-group` (default latest — literal, documented), `--artifact-root`, `--attribution-target`, `--output`, `--format json|markdown` (markdown = short human rendering + JSON sidecar via `_write_or_print_text` sibling pattern), `--record`, `--fail-on-action-required`.
`--record`: after readonly evaluation, reopen with `connect(args.db)`, `upsert_proof_block(conn, stable_key=f"{run_id}:evaluation", run_id=<newest run row id in group>, block_key="evaluation", block_kind="evaluation", title="Evaluation verdict", summary=<one-line>, payload=json.dumps(verdict), source_kind/confidence/evidence_refs/redaction_state from verdict)`; idempotent on re-run (UNIQUE(run_id, block_key)).
Tests: exit 0 on green and red; 1 only with flag+action-required; 2 on missing db/group; `--record` writes exactly one block, twice → still one; recorded block visible in `export_proof_packet` blocks; registration/help.

- [x] failing tests → [x] implement → [x] suite green → [x] commit

### Task 3: `nlfr receipt import`

**Files:** Create `src/nlfr/commands/receipt_cmd.py`; Modify `src/nlfr/commands/__init__.py`, `tests/test_cli.py`; Create fixture `tests/fixtures/receipts/imported-claude-receipt.json`; Test `tests/test_receipt_import.py`.

`nlfr receipt import --receipt PATH --db PATH --run-group NAME [--run-key KEY]`:
1. `load_receipt` + `validate_receipt` (reject → stderr reason, exit 2, nothing written).
2. Resolve run: newest run in group (or `--run-key`); missing → exit 2.
3. `upsert_artifact` row for the receipt file (sha256 of bytes, `redaction_state="redacted"`).
4. Dedicated builder `imported_receipt_provenance(receipt, *, run_id, run_group) -> dict` in `receipt_cmd.py`: summary = `receipt_provenance_summary(receipt)` then **overrides** `summary["live"] = False`, adds `summary["observed_by_nlfr"] = False`; payload mirrors `_agent_provenance_payload` agent-block shape with `provenance_class="receipt_imported_v1"`, `source_kind="collectable_v1"`, `confidence="medium"`, evidence_refs incl. `receipt:sha256:...`; never calls `is_live_receipt`.
5. `upsert_proof_block(kind="agent_provenance", block_key="agent-receipt-imported:<sha12>")`.

Tests: valid claude/success receipt fixture → block has class `receipt_imported_v1`; **graph projection renders the agent node `receipt_verified: false`** and **compare projection `receipt_verified: false`** (the BLOCKER guard); schema-invalid receipt → exit 2 + no rows; receipt with raw-prompt key → exit 2; help/registration.

- [x] failing tests → [x] implement → [x] suite green → [x] commit

### Task 4: `nlfr loop` command

**Files:** Create `src/nlfr/commands/loop_cmd.py`; Modify `src/nlfr/commands/__init__.py`, `tests/test_cli.py`; Test `tests/test_loop_cmd.py` (fake `bazel` shim from `test_record_cmd.py` pattern + `scripts/spark-stub-claude.sh`).

Flags: `--scenario NAME|PATH` (resolve like spark scenario via `simulate_resources` precedence: explicit path > packaged > repo `demo/scenarios/`), `--mode cache-only`, `--skip-nativelink`, `--claude-bin`, `--max-iterations` (default 2), `--run-group-prefix` (default `loop`), `--output-dir` (default `data/nlfr-loop`), `--workspace` (template override), `--bazel-bin` (test seam, mirrors record_cmd's shim approach if present — else PATH).
Engine (spec §3): setup workspace (`apply_workspace_setup`), per iteration N: build prompt (`build_act1_prompt` for N=1 / `build_act2_prompt` with prior file + verdict excerpt for N>1) → `agent-invoke` (subprocess `[sys.executable,"-m","nlfr","agent-invoke",...]`) → `extract_python_file` → write target file + hashes + sidecar → `run` (subprocess, `--run-group {prefix}-iter{N}`) → `ingest` → `graph export`/`proof export` → in-process `evaluate_run_group(..., artifact_root=..., attribution_target=hidden target label from scenario)` + record block → branch on `next_steps[0].action` (dispatch → next iteration; blocker → blocker JSON exit 2; none_complete → `compare export --left iter1 --right iterN`, write `loop-summary.json` (`nlfr.loop.v1`, checks per spec), exit 0; cap+red → summary, exit 1). Agent-invoke rc≠0 → receipt kept, blocker JSON, exit 2.
Tests: two-iteration stub red→green e2e (fake bazel shim emitting BEP fixtures: iter1 red w/ hidden-target line in stderr, iter2 green) asserting summary checks all true, per-iteration evaluation blocks in both DBs/groups, compare file exists, exit 0; toolchain-signature path → exit 2 blocker; `--max-iterations 1` red → exit 1; help/registration.

- [x] failing tests → [x] implement → [x] suite green → [x] commit

### Task 5: proof script + docs

**Files:** Create `scripts/agentic-loop-proof.sh` (env bring-up copied from two-act script L193-220 + one `nlfr loop` call + redaction scan), `docs/wiki/how-to/capture-agent-telemetry-in-ci.md` (three rungs: in-pod wrap / drop-box import / none ⇒ operator_asserted_v1; GHA + k8s examples); Modify `README.md` (capability rows), `docs/wiki/reference/cli.md` (evaluate/loop/receipt import), `docs/ONE_PAGER.md` + `docs/USEFULNESS_ROADMAP.md` (only proven claims, stub vs live explicit), ladder text where documented (README/one-pager/`projectors/graph.py` docstring).

- [x] write → [x] `uv run pytest -q` (doc-sample tests may assert samples) → [x] commit

### Task 6: version bump + full proof

**Files:** Modify `pyproject.toml:7`, `src/nlfr/__init__.py:5`, `src/nlfr/cli.py:25` → `0.3.0`.
- [x] bump → [x] `uv run pytest -q` full green (764+new) → [x] run `scripts/agentic-loop-proof.sh` under nix if env allows (else document blocker; fixture tests stand per repo convention) → [x] commit

### Task 7: review gate + ship

- [x] Dispatch fresh-context reviews: kos-review-opus (honesty/correctness) + kos-review-sonnet (conventions/tests) on the full diff; fix confirmed findings.
- [x] Push branch, open PR, CI green, merge to main (ship authority per campaign memory).
- [x] Tag `v0.3.0` → release workflow (wheel + GitHub release; PyPI stays env-gated).

## Self-Review

Spec coverage: §1→T1, §2→T2, §3→T4(+T5 script), §4→T3(+T5 how-to), §5→T6/T7, error handling/testing sections embedded per task. Placeholder scan: task 1 carries one explicit inline decision (no-target classification → `unattributed_failure` with null attribution) — resolved, not deferred. Type consistency: `evaluate_run_group` signature and precedence enum verified consistent across T1/T2/T4.
