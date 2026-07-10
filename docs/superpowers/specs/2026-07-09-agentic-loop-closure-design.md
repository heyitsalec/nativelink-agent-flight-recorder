# Agentic loop closure — `nlfr evaluate`, `nlfr loop`, and imported agent receipts

Date: 2026-07-09 · Status: approved for implementation (autonomous session; design
reviewed by adversarial redteam before build) · Owner: this session

## Problem

NLFR records truth-labeled evidence, but the *reasoning* about that evidence
lives outside the product. In `scripts/two-act-spark-proof.sh`, every decision —
"did act 1 fail?", "is the red an honest scenario failure or a toolchain
blocker?", "what evidence do we hand the fixing agent?", "did the loop
succeed?" — is bash branching over inline `python3 -c` JSON greps. The
honest-failure classification verdict (`act1-failure-classification.json`) is
never ingested; it is invisible to the evidence DB, the proof packet, and the
canvas. NLFR watches the loop but does not close it.

Separately: agent receipts today exist only because we invoke the agent CLI
locally (`nlfr agent-invoke`). Cloud and pod builds (CI runners, Kubernetes
jobs, hosted agent sessions) have no documented, honest path to land their
agent telemetry in the flight record.

## Goal

Turn NLFR into the system that (1) **evaluates** recorded truth data, (2)
**reasons about next steps** as truth-labeled, machine-actionable output, (3)
**drives the fix loop** natively (dispatch fix agent with recorded evidence →
re-validate → re-evaluate → compare), and (4) accepts **agent telemetry from
builds NLFR did not itself invoke**, labeled honestly. Then ship it as a new
build.

## Non-goals (v1)

- No LLM-authored verdicts. The evaluator is deterministic rules over recorded
  evidence. An LLM advisory lane can come later as its own labeled block kind.
- No scheduler/fleet claims, no auto-merge/auto-deploy of the *target* repo's
  code. The loop fixes and re-validates inside its scenario workspace.
- No push telemetry transport (OTLP etc.). Receipt movement is files +
  hashes — NLFR's idiom. Transport is the CI system's job.
- No change to the existing two-act script's committed proof path; it keeps
  working as-is. A new thin proof script demonstrates the native loop.

## Approaches considered

1. **Deterministic evaluator + native loop driver (chosen).** Verdicts are
   reproducible functions of the evidence, so they can be truth-labeled
   `derived_v1` honestly and tested against fixtures. LLM stays where it
   already is: authoring the fix, with receipts.
2. LLM-evaluator ("ask the model what to do next" over the proof packet).
   Rejected for v1: non-deterministic, unfalsifiable verdicts poison the
   truth-label ethos that is NLFR's differentiation.
3. Incremental bash (share jq helpers across scripts). Rejected: doesn't move
   the capability into the product; nothing becomes queryable or attestable.

## Design

### 1. Evaluator core — `src/nlfr/evaluator.py`

A pure module: `evaluate_run_group(conn, run_group, *, artifact_root=None,
attribution_target=None) -> dict` producing a versioned payload
`schema: "nlfr.evaluation.v1"`.

Inputs (all already recorded):
- SQLite rows: `runs`, `targets`, `failures`, `cache_events`,
  `artifact_references`, `proof_blocks` (via `nlfr.projectors.common.rows`).
- Optional `artifact_root` for raw-log analysis (failure classification and
  evidence excerpts read recorded `bazel.stderr/stdout.txt` artifacts — same
  files `nlfr.spark.classify_validation_failure` / `failure_excerpt` read
  today; that logic generalizes into the evaluator with the signature list and
  attribution target as parameters instead of spark-scenario hardcodes; spark
  keeps thin wrappers so the existing script's behavior is unchanged).

Verdict payload:
- `status`: `ok | failed | empty` — reuses the exact
  `proof_markdown.validation_status()` semantics (max of summary failures and
  validation-block failures); never re-derived differently.
- `failures[]`: kind, message, span, plus `attributed_targets[]` (labels whose
  `targets.status == "FAILED"`, cross-referenced with failure messages).
- `classification`: `honest_scenario_failure | toolchain_blocker |
  first_pass_success | unclassified` + `matched_signatures[]` +
  `attribution_target_referenced` (bool, when an attribution target given).
  Only computed when `artifact_root` provided; otherwise `unclassified` with
  reason `raw_logs_unavailable` — never guessed from DB rows alone.
- `failure_evidence`: when red and raw logs available — redacted excerpt
  (same 80-line `failure_excerpt` rules), its sha256, and the artifact refs
  it came from. The excerpt itself is written next to the verdict output, not
  inlined raw into the DB.
- `cache`: hits/misses/hit_rate rolled up from `cache_events`.
- `artifact_verification`: reuse of the proof-packet rollup counts.
- `agent_provenance`: receipt classes present on the run-group
  (`receipt_verified_v1` / `receipt_imported_v1` / `stub_receipt_v1` /
  `operator_asserted_v1` counts).
- `next_steps[]`: **ordered, closed enum** — each entry
  `{action, reason, inputs, source_kind, confidence, evidence_refs,
  redaction_state}`. v1 action vocabulary:
  - `dispatch_fix_with_evidence` — red + honest classification; `inputs`
    carries the evidence-excerpt ref and the changed-file path from `changes`.
  - `rerun_validation` — a fix was applied after the last recorded run
    (changes row newer than latest run) or verdict requested it.
  - `record_environment_blocker` — toolchain/blocked classification; loop
    must stop, not retry.
  - `attach_missing_evidence` — evaluation degraded because raw logs or
    receipts absent; names exactly what is missing.
  - `none_complete` — green with nothing outstanding.
- Top-level truth quad: `source_kind: "derived_v1"` always (a verdict is a
  synthesized judgment, never `collectable_v1`); `confidence` = weakest-input
  rule mirroring `proof.py:_confidence()`; `evidence_refs` = union of every
  ref actually consulted; `redaction_state` via `redact_payload()` before any
  write — same gate as `pr_comment.py`.

### 2. `nlfr evaluate` command — `src/nlfr/commands/evaluate_cmd.py`

```
nlfr evaluate --db data/nlfr/nlfr.sqlite --run-group latest
              [--artifact-root PATH] [--attribution-target //label]
              [--output evaluate-<rg>.json] [--format json|markdown]
              [--record] [--fail-on-action-required]
```

- Standard idioms: `connect_readonly` + `UnreadableDatabaseError → stderr,
  exit 2`; `write_or_print`; markdown via sibling-JSON-sidecar pattern from
  `export_cmds.py`.
- Exit codes: 0 evaluated (regardless of verdict), 2 cannot evaluate,
  and with `--fail-on-action-required`: 1 when `next_steps[0].action` is not
  `none_complete` — mirrors `--fail-on-validation` composability.
- `--record`: re-opens the DB read-write and inserts the verdict as a
  `proof_blocks` row (`kind="evaluation"`, truth quad from the verdict) so
  proof packets, in-toto export, compare, and the canvas can carry it. The
  loop's reasoning becomes part of the flight record — that is the closure.
- Registered in `commands/__init__.py`; added to `test_cli.py`'s help
  assertion list.

### 3. `nlfr loop` command — `src/nlfr/commands/loop_cmd.py`

The native driver for the red → evaluate → fix → green story:

```
nlfr loop --scenario two-act-underspec --mode cache-only [--skip-nativelink]
          [--claude-bin PATH] [--max-iterations 2] [--run-group-prefix NAME]
          [--output-dir data/nlfr-loop] [--workspace PATH]
```

- Reuses `nlfr.spark` plumbing as Python calls (scenario load, workspace
  setup, prompt build, fenced-file extraction) and invokes the existing
  `agent-invoke` / `run` / `ingest` / `graph export` / `proof export` /
  `compare export` machinery per iteration.
- Environment boundary: the loop does **not** manage the NativeLink server —
  the operator/script provides the validation environment, exactly as
  `run --skip-nativelink` assumes today (or `run` manages it when asked).
- Iteration engine: run validation → ingest → `evaluate` (with `--record`
  semantics) → branch **only** on `next_steps[0].action`:
  - `dispatch_fix_with_evidence` → build fix prompt from the verdict's
    recorded evidence excerpt, `agent-invoke`, apply change, next iteration.
  - `record_environment_blocker` → write blocker JSON, exit 2 (honest stop).
  - `none_complete` → success path: export compare (first vs last), stop.
  - iteration cap reached with red → exit 1, verdict stands, no retry spiral.
- Output: `loop-summary.json` — schema `nlfr.loop.v1`: per-iteration
  {run_group, verdict ref, receipt ref, action taken}, final outcome, checks
  (first iteration red, honest classification, fix receipt present, final
  green, warm cache on unchanged targets, compare exported), truth-labeled.
  The bash `checks` heredoc from the two-act script becomes this, in-product.
- Stub vs live agent: unchanged mechanics — stub CLI ⇒ `stub_receipt_v1`
  legs; live claude ⇒ `receipt_verified_v1`. The loop never upgrades labels.
- New thin proof script `scripts/agentic-loop-proof.sh`: env setup (NativeLink
  bring-up, temp cache root) + one `nlfr loop` call + redaction scan — the
  decision spine now lives in the product.

### 4. Imported agent receipts (cloud/pod telemetry) — `nlfr receipt import`

Reality today: receipts exist because NLFR ran the CLI itself. In cloud/pod
builds the invocation happens where NLFR isn't. The honest contract:

- **Preferred: wrap in-pod.** `nlfr` is stdlib-only; `pip install` in the
  pod/CI step and use `nlfr agent-invoke` there. Receipts produced this way
  keep full `receipt_verified_v1` semantics. Documented for GHA and generic
  k8s in a new how-to.
- **Drop-box import.** When wrapping is impossible (hosted agent produced its
  own `nlfr.agent_receipt.v1` JSON, moved as a build artifact):

  ```
  nlfr receipt import --receipt act1-receipt.json --db ... --run-group ...
  ```

  Validates via the existing `validate_receipt()` (schema, privacy invariants,
  sha256 shapes, no raw-prompt keys), stores the file as an artifact, and
  attaches an `agent_provenance` proof block with **new provenance class
  `receipt_imported_v1`**: the receipt content is collected evidence
  (`collectable_v1`) but the invocation was not observed by NLFR, so
  `confidence: "medium"` and the class name states the boundary. It is never
  `receipt_verified_v1` (reserved for NLFR-observed invocations) and never
  silently downgraded to `operator_asserted_v1` (which stays the no-receipt
  class). Ladder becomes: `receipt_verified_v1 > receipt_imported_v1 >
  stub_receipt_v1 > operator_asserted_v1`, updated everywhere the ladder is
  documented (README, one-pager, graph projector docstring).
- Invalid/privacy-violating receipt files are rejected with exit 2 and a
  specific reason; no partial attach.
- New how-to: `docs/wiki/how-to/capture-agent-telemetry-in-ci.md` covering
  the three rungs (wrap in-pod / import / no receipt ⇒ `operator_asserted_v1`)
  with GHA and pod examples.

### 5. Ship

- Version bump 0.2.1 → 0.3.0 in the three documented places (`pyproject.toml`,
  `src/nlfr/__init__.py`, `cli.py --version`).
- Docs: README capability rows for evaluate/loop/receipt-import; CLI
  reference; one-pager and roadmap updated **only with what the local proof
  actually demonstrates** (stub vs live stated explicitly).
- PR → CI green → merge → tag `v0.3.0` (release workflow: wheel + GitHub
  release; PyPI stays gated by `PYPI_PUBLISH_ENABLED`).

## Error handling

- Missing/unreadable DB, unknown run-group: exit 2 with the established
  stderr idioms (`MissingRunGroupError` reused from compare).
- Raw logs absent: evaluation still succeeds, classification `unclassified`,
  `attach_missing_evidence` next step — degraded honestly, never guessed.
- Agent invocation failure inside `loop`: receipt still recorded (failed
  attempt is evidence), loop stops with exit 2 and blocker JSON, mirroring
  the script's `invoke_agent` gate.
- All written payloads pass `redact_payload()`; the loop proof script keeps
  the whole-tree redaction scan as a final gate.

## Testing

TDD throughout; patterns copied from named exemplars:
- Evaluator unit tests (style: `test_pr_comment_export.py`): in-proc SQLite,
  upsert fixtures (green run / red run / red+logs / missing logs / stale
  changes), assert verdict fields, next-step ordering, truth labels
  (`derived_v1` always, weakest-input confidence), redaction-cleanliness.
- Fixture-round-trip: verdict over the committed compare fixtures stays
  byte-stable (guards determinism claim).
- CLI tests (style: `test_cli.py`): registration/help, exit codes, `--record`
  writes exactly one evaluation proof block; second `--record` upserts, not
  duplicates.
- Loop tests (style: `test_record_cmd.py` fake-bazel shim + existing stub
  claude): two-iteration red→green run, asserts loop summary checks, receipt
  classes, compare exported; blocker path (toolchain signature ⇒ exit 2);
  iteration-cap path.
- Receipt import tests: valid live receipt fixture ⇒ `receipt_imported_v1`
  block; invalid schema / raw-prompt key ⇒ exit 2, nothing written.
- Suite: `uv run pytest -q` (764 tests today) stays green; never system
  python3.

## Proof before done

- `uv run pytest -q` green.
- Native loop proof: `scripts/agentic-loop-proof.sh` under nix (stub agent;
  live claude pass if host allows) → `loop-summary.json` with all checks true,
  evaluation blocks queryable via `nlfr proof export`.
- If NativeLink/Bazel can't run on this host, the exact blocker is documented
  and the fixture-backed tests stand as the gate (repo convention).
