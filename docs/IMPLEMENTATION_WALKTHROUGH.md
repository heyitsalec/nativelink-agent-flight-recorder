# NLFR implementation walkthrough

This file is a code tour. It explains the important implementation files and how
they fit together. Read it alongside [`WALKTHROUGH.md`](WALKTHROUGH.md).

## Top-level structure

```text
src/nlfr/                  Python recorder CLI and evidence pipeline
apps/canvas/               React canvas reading projection JSON
demo/bazel-monorepo/       Tiny Bazel workspace used by proofs and fixtures
demo/nativelink/           NativeLink configs for cache-only/local-exec paths
demo/scenarios/            Deterministic agent patch scenarios
scripts/                   End-to-end proof and demo scripts
tests/                     Pytest coverage over artifacts, ingest, projectors, CLI
docs/                      Product, proof, demo, and walkthrough docs
```

The codebase is intentionally small and mostly stdlib Python. The recorder is
designed so a skeptic can inspect each transformation from raw tool output to
projection JSON.

## CLI entrypoint

### `src/nlfr/__main__.py`

Lets the package run as:

```bash
python -m nlfr ...
```

It delegates to `nlfr.cli.main`.

### `src/nlfr/cli.py`

Builds the top-level `argparse` parser:

- Program name: `nlfr`.
- Version: matches `pyproject.toml` (see `nlfr --version`).
- Requires a subcommand.
- Calls `register_commands(subparsers)`.
- Dispatches to the selected command handler.

Study this first to see how the CLI is shaped. The key pattern is:

1. Parse args.
2. Find `args.handler`.
3. Return the handler's integer exit code.

### `src/nlfr/commands/__init__.py`

Registers subcommands. Each command module exposes a `register(subparsers)`
function.

Commands of interest:

- `doctor`
- `run`
- `ingest`
- `graph export`
- `proof export`
- `runway export`
- `simulate`

## Running and recording evidence

### `src/nlfr/commands/run_cmd.py`

This is the recorder's first major path.

What it does:

1. Validates `--mode` (`cache-only`, `local-exec`, or `generic`).
2. For Bazel modes: resolves workspace, output directory, NativeLink config, run key, and run ID.
3. For `generic` mode: delegates to `generic_run.py` (see below).
4. Initializes SQLite at `<output-dir>/nlfr.sqlite`.
5. Upserts a `runs` row with `source_kind=collectable_v1`.
6. Creates a `NativeLinkRunner`.
7. Creates a `BazelRunner`.
8. Optionally starts NativeLink.
9. Runs Bazel tests.
10. Writes process artifacts and `run.json`.
11. Upserts invocation/artifact rows.
12. Returns `0` only if the terminal status is `completed`.

### `src/nlfr/commands/generic_run.py`

Generic (non-Bazel) recording path for dogfooding NLFR on its own GUI build.

What it does:

1. Runs one or more `--command` strings via `ProcessRunner` (parsed with `shlex`).
2. Optionally records `--change-path` before/after file hashes.
3. Optionally copies `--artifact PATH:LABEL` outputs into the manifest.
4. Writes failures for nonzero exit codes; leaves targets/actions/cache_events empty.
5. Exports the same projection chain as Bazel runs: run → change → invocation → artifact.

Proof scripts:

- `scripts/record-proof.sh` — generic run self-test gate.
- `scripts/record-canvas-build.sh` — records canvas build + publishes redacted default projections.

The important objects:

- `run_key`: stable logical identity such as `scenario:mode`.
- `run_id`: deterministic ID from `stable_id("run", run_key)`.
- `artifact_root`: where stdout/stderr/run summaries are written.
- `run_group`: projection grouping label, usually `latest`, `cold-warm`,
  `local-exec`, or `agent-loop`.

Important implementation choices:

- Runs are inserted before commands execute so even blocked/failed runs can be
  recorded.
- NativeLink and Bazel process results are both represented as invocations.
- Commands and endpoints are later sanitized by projection helpers before UI
  display.
- `nlfr run` captures process-level evidence; it does not parse Bazel BEP into
  targets/actions/cache events. That is `nlfr ingest`.

### `src/nlfr/runners/process.py`

Provides the process execution abstraction and `ProcessResult`.

Expected role:

- Run a command with cwd/timeout.
- Capture stdout/stderr to artifact files.
- Produce metadata used by `run_cmd.py`.

The runner layer keeps command execution details out of the CLI command.

### `src/nlfr/runners/nativelink.py`

Wraps NativeLink process execution. In cache-only mode the proof scripts may
start NativeLink themselves and pass `--skip-nativelink` to avoid duplicate
servers.

### `src/nlfr/runners/bazel.py`

Builds Bazel test commands with BEP/profile/execution-log output so later ingest
has structured artifacts to parse. It also attaches `--remote_cache` and, in
local-exec mode, `--remote_executor`.

## Immutable artifacts

### `src/nlfr/artifacts.py`

This is the lowest-level proof primitive.

Key pieces:

- `ArtifactManifestEntry`: stable manifest metadata.
- `write_artifact(...)`: writes a file once, hashes it, and appends to
  `artifact_manifest.json`.
- `read_manifest(...)`: reads the current manifest or returns an empty schema.
- `_safe_relative_path(...)`: blocks absolute paths and parent traversal in
  artifact keys.

Important behavior:

- If the same artifact key and exact same manifest entry already exist, the
  write is idempotently reused.
- If the key exists with different content or metadata, an
  `ArtifactExistsError` is raised.
- Manifest writes go through a temp file and `os.replace`.

This lets proof packets say "this artifact existed with this hash" rather than
"some command printed something."

## Stable IDs

### `src/nlfr/ids.py`

Generates stable IDs. The exact implementation is small, but conceptually it
turns a namespace and stable key into deterministic row IDs. This is why ingest
can be rerun without creating duplicate rows.

## SQLite data spine

### `src/nlfr/db/schema.py`

Defines the schema and migrations.

Core tables:

- `runs`: one logical validation run.
- `changes`: deterministic patch/change provenance.
- `invocations`: recorded process commands.
- `artifacts`: immutable files and hashes.
- `targets`: Bazel targets.
- `actions`: Bazel actions/test actions.
- `cache_events`: cache hits/misses/observations.
- `failures`: target/build failures.
- `graph_nodes`, `graph_edges`: optional explicit graph rows.
- `proof_blocks`: stored proof claims such as agent provenance or worker
  readiness.

Shared columns on core evidence:

- `source_kind`
- `confidence`
- `evidence_refs`
- `redaction_state`
- timestamps

Schema checks enforce allowed truth-label values. This matters because the
projectors and UI can trust the vocabulary.

### `src/nlfr/db/connection.py`

Creates SQLite connections. It configures row access so projectors can treat rows
as dictionaries.

### `src/nlfr/db/ingest.py`

Contains upsert helpers for each table.

The pattern is:

1. Accept stable key plus row fields.
2. Serialize lists/dicts as JSON where needed.
3. Insert or update by stable key.
4. Return the row ID.

This is what makes `nlfr ingest` idempotent.

## Bazel evidence parsing

### `src/nlfr/commands/ingest_cmd.py`

The `nlfr ingest` command connects raw evidence files to the SQLite spine.

It accepts:

- `--database`
- `--run-key`
- `--run-group`
- `--scenario`
- `--mode`
- `--bep`
- `--execution-log`
- `--profile`
- `--source-kind`

Flow:

1. Find evidence files from explicit args or an evidence directory.
2. Parse BEP, execution log, and profile into an `EvidenceBundle`.
3. Initialize SQLite.
4. Upsert a `runs` row.
5. Insert targets/actions/cache events/failures.
6. If `worker-readiness.json` exists, ingest it as a proof block.
7. Print counts.

The `--source-kind` can be `collectable_v1` for real artifacts or
`simulated_v1` for fixture-backed evidence.

### `src/nlfr/ingest/models.py`

Defines the parsed evidence dataclasses:

- `TargetEvidence`
- `ActionEvidence`
- `CacheEventEvidence`
- `FailureEvidence`
- `EvidenceBundle`

This layer separates parser output from SQLite insertion.

### `src/nlfr/ingest/bazel.py`

Parses compact Bazel artifacts.

Important functions:

- `parse_bazel_bep(...)`: reads Build Event Protocol JSON/JSONL and extracts
  targets, test actions, and failures.
- `parse_bazel_execution_log(...)`: extracts cache hit/miss events from
  execution-log-like JSON.
- `parse_bazel_profile(...)`: extracts derived cache observations from Bazel
  profile/Chrome trace JSON.

Evidence truth behavior:

- BEP and execution log data can be `collectable_v1` when sourced from real
  runs.
- Profile-derived cache observations are `derived_v1`, often medium/low
  confidence.
- If an execution-log event cannot prove hit/miss, it becomes derived/low.

### `src/nlfr/ingest/sqlite.py`

Takes an `EvidenceBundle` and inserts it into SQLite.

The relationship logic:

- Targets are inserted first.
- Actions link to targets when target labels match.
- Cache events link to actions if action keys are known, else targets, else
  just the run.
- Failures link to the run.

This is why the graph can later draw:

`run -> target -> action -> cache_event`

## Projection exports

### `src/nlfr/commands/export_cmds.py`

Registers export commands:

- `nlfr graph export`
- `nlfr proof export`
- `nlfr runway export`

Each command opens SQLite, calls the matching projector, and writes JSON.

### `src/nlfr/projectors/common.py`

Shared projector helpers:

- Fetch rows by run group.
- Decode JSON fields.
- Compute generated timestamps.
- Extract truth labels.
- Count statuses.

### `src/nlfr/projectors/graph.py`

Builds the Action Graph projection.

It reads:

- runs
- invocations
- artifacts
- targets
- actions
- cache events
- failures
- changes
- proof blocks
- explicit graph nodes/edges

Then it creates nodes and edges:

- `run` node for each run.
- `agent` nodes derived from `agent_provenance` proof blocks.
- `change` nodes from the `changes` table.
- `authored_change` edge from agent to change.
- `validated_by` edge from change to run.
- `recorded_invocation` edges.
- `recorded_artifact` edges.
- `evaluated_target` edges.
- `produced_action` edges.
- `observed_cache_event` edges.
- `observed_failure` edges.

Privacy-critical detail:

`_project_agents(...)` carries only redacted/hash-level agent data:

- agent kind
- agent name
- model label
- `prompt_sha256`
- input signal summary
- change class
- patch hash

It does not export raw prompts.

Remote-execution detail:

Remote execution configuration nodes are derived only from recorded invocation
arguments. They prove configuration intent, not worker assignment or queue time.

### `src/nlfr/projectors/proof.py`

Builds the Proof Packet projection.

Generated proof blocks include:

- Proof Scope
- Invocation Results
- Cache Evidence
- Cache Economics
- Remote Execution Boundary
- Validation Surface
- Artifact Chain
- Stored proof blocks from SQLite

The cache economics block computes per-run legs and cold/warm comparisons:

- cold hit rate
- warm hit rate
- cold duration
- warm duration
- hit-rate delta
- duration delta

It explicitly refuses to claim dollar savings or fleet-wide performance.

### `src/nlfr/projectors/remote_execution.py`

Owns the conservative remote-execution model.

It detects `--remote_executor` configuration, sanitizes endpoint values, and
centralizes unsupported remote claims:

- worker identity
- action placement
- queue time
- scheduler assignment
- load distribution

This keeps all remote-execution UI/proof claims bounded.

### `src/nlfr/projectors/runway.py`

Exports a simplified validation sequence. The canvas can render this as a
runway overlay. It is not a separate truth source; it is another projection of
SQLite rows.

## Simulated agent provenance

### `demo/scenarios/*.json`

Scenario files define deterministic patch workflows. The key scenario today is:

- `demo/scenarios/llm-bounded-patch.json`

It models a bounded-agent patch with:

- scenario ID
- agent kind/name/model
- redacted input signal
- prompt hash
- patch diff
- proof claims

The scenario is deterministic. It does not make a live LLM call.

### `src/nlfr/commands/simulate_cmd.py`

Implements `nlfr simulate`.

Flow:

1. Resolve one or more scenario JSON files.
2. Copy `demo/bazel-monorepo` to an output workspace.
3. Compute before hashes of affected files.
4. Apply the patch with `git apply`.
5. Compute after hashes.
6. Either skip build (`--skip-run`) or call `nlfr run`.
7. If `--ingest` is set after a real run, ingest Bazel artifacts.
8. Build a provenance payload.
9. Write `agent-provenance.json` as an artifact.
10. Upsert changes, artifacts, and an `agent_provenance` proof block.

Key guarantees:

- Raw prompts are never stored.
- If a raw prompt is supplied, the command hashes it to `prompt_sha256`.
- The copied workspace protects the source demo workspace from mutation.
- The graph projector links agent/change/run through proof blocks and changes.

## Proof scripts

### `scripts/verify-demo.sh`

One-command local demo verifier. It runs:

- backend tests
- doctor
- local real-tool smoke
- cold/warm proof
- local-exec proof
- agent-loop proof
- fixture-backed agent-loop projection
- canvas build

Outside the right environment, real-tool paths record blockers/logs rather than
claiming success.

### `scripts/cold-warm-cache-proof.sh`

Starts a NativeLink cache-only server and runs a cold leg and warm leg with
separate Bazel output bases. It exports projections and writes
`summary.json`.

What it proves:

- Real NativeLink cache proof can be captured.
- In the current sample, warm hit rate and duration improved.

What it does not prove:

- Fleet-wide savings.
- Multi-run economics across an organization.

### `scripts/local-exec-proof.sh`

Exercises local remote-execution configuration. With `NLFR_EXPECTED_WORKERS=2`,
it can prove two configured workers and live endpoints.

What it does not prove:

- Which worker ran which action.
- Queue time.
- Scheduler assignment.
- Load distribution.

### `scripts/agent-loop-proof.sh`

Runs the deterministic bounded-agent scenario through a live NativeLink cache
path and ingests validation/cache evidence. It then exports graph/proof/runway
projections and writes `summary.json` with `chain_complete=true` when the
agent/change/run graph chain exists.

Important distinction:

- validation/cache leg: `collectable_v1`
- agent/change provenance: `simulated_v1`

## Canvas implementation

### `apps/canvas/src/types.ts`

Defines TypeScript shapes for projection JSON:

- source kinds
- confidence values
- graph nodes/edges
- proof blocks
- canvas mode
- focus filters

This file keeps the React app honest about the projection schema.

### `apps/canvas/src/layout.ts`

Computes deterministic node positions and radii. It includes anchors for key
node kinds such as run, target, action, cache event, artifact, agent, and change.

The layout is intentionally sparse. It is not a force-directed exploratory
dashboard.

### `apps/canvas/src/App.tsx`

Main React application.

Important responsibilities:

- Fetch action graph projection.
- Fetch proof projection.
- Fall back to sample data if projections are missing.
- Maintain canvas mode: graph, runway, proof, remote.
- Maintain focus filter: all, cache, failures, remote, derived, agent.
- Render graph SVG nodes and edges.
- Render inspector drawer.
- Render proof drawer.
- Render remote lens.
- Render runway overlay.
- Render truth-label legend.
- Interpret operator commands.

Operator command behavior:

- `cache`: focus cache evidence.
- `fail`: focus failures and open the first failure.
- `proof`: open Proof Packet.
- `remote`, `worker`, or `execution`: open Remote Boundary.
- `agent`, `loop`, or `change`: focus agent/change nodes.
- `runway` or `timeline`: open runway.
- anything else: reset.

### `apps/canvas/src/styles.css`

Styles the visual language:

- Green: `collectable_v1`.
- Amber: `derived_v1`.
- Purple: `simulated_v1`.
- Gray: `future`.
- Red-ish failure nodes.
- Side drawers for inspector/proof/remote.
- Bottom operator input.
- Bottom-left truth legend.
- Mobile layout.

### `apps/canvas/scripts/capture-proof.mjs`

Uses Playwright to capture:

- `canvas-desktop.png`
- `canvas-proof.png`
- `canvas-remote-boundary.png`
- `canvas-failure-focus.png`
- `canvas-agent-loop.png`
- `canvas-mobile.png`
- `canvas-operator-flow.webm`

The committed walkthrough media in `docs/images/` comes from this capture path.

### `scripts/worker-readiness.py`

Builds conservative worker-readiness payloads for local-exec proofs. It records
endpoint readiness and explicitly lists unsupported claims rather than inferring
worker identity or action placement.

## Projection contracts

The exported JSON shapes are versioned under `contracts/`:

- `contracts/artifact_manifest.v1.json`
- `contracts/canvas_projection.v1.json`
- `contracts/proof_packet.v1.json`

These are the schema guardrails for artifact manifests, action graphs, and proof
packets. Projector tests validate exported JSON against them.

## Tests

### `tests/test_data_spine.py`

Verifies schema tables, truth labels, idempotent upserts, and artifact manifest
hashing/overwrite refusal.

### `tests/test_ingest_bazel.py`

Verifies Bazel evidence parsers, SQLite ingest behavior, `nlfr ingest`, and
worker-readiness proof-block ingest against fixture files.

### `tests/test_projectors.py`

Verifies projection output, including proof blocks, truth labels, remote
execution boundaries, cache economics, agent/change/validation graph chain, and
contract JSON validity.

### `tests/test_simulate_cmd.py`

Verifies simulated-agent provenance, including hashed prompt behavior and the
absence of raw prompt leakage.

### `tests/test_cli.py`

Verifies CLI command behavior such as `doctor`, with environment-aware return
code assertions.

### `tests/test_worker_readiness.py`

Verifies worker-readiness payloads, expected worker gates, and
endpoint-readiness-only claims.

### `tests/runners/test_*.py`

Runner tests for Bazel, NativeLink, and process execution command construction
and blocker behavior.

## Data flow in one concrete example

Follow `scripts/agent-loop-proof.sh`:

1. Start NativeLink cache-only server.
2. Run `nlfr simulate --scenario llm-bounded-patch --ingest`.
3. `simulate_cmd.py` copies the demo workspace and applies the patch.
4. It calls `nlfr run`.
5. `run_cmd.py` records NativeLink/Bazel process artifacts.
6. `simulate_cmd.py` calls ingest for the run artifacts.
7. `ingest_cmd.py` parses Bazel evidence and writes targets/actions/cache events.
8. `simulate_cmd.py` writes agent provenance and change rows.
9. `graph.py` exports the action graph.
10. `proof.py` exports the proof packet.
11. The script checks that the graph contains agent/change edges.
12. The canvas can render the exported JSON.

The key proof chain is:

`agent -> authored_change -> change -> validated_by -> run -> evaluated_target -> target -> produced_action -> action -> observed_cache_event -> cache_event`

## How to debug this system

When something looks wrong, walk backward:

1. Is the canvas reading the projection you think it is?
   Check `apps/canvas/public/projections/*.json`.
2. Does the projection include the node/edge/block?
   Run `nlfr graph export` or `nlfr proof export` against the target DB.
3. Does SQLite contain the row?
   Inspect `data/.../nlfr.sqlite`.
4. Did ingest parse the artifact?
   Check ingest JSON counts and parser tests.
5. Did the run capture the artifact?
   Check `artifact_manifest.json` and `run.json`.
6. Did the external tool run?
   Check invocation stdout/stderr artifacts and blocker files.

The project is designed so every layer leaves an inspectable artifact.
