# NLFR walkthrough

This is the guided tour for understanding the NativeLink Agent Flight Recorder
(NLFR) as it exists today. Read it with the repo open. The goal is to move from
the product idea to the concrete files, commands, screenshots, and proof
artifacts that make the MVP work.

If you only read one path, follow this order:

1. This file for the system shape and demo flow.
2. [`IMPLEMENTATION_WALKTHROUGH.md`](IMPLEMENTATION_WALKTHROUGH.md) for the
   file-by-file code tour.
3. [`USEFULNESS_ROADMAP.md`](USEFULNESS_ROADMAP.md) for what is needed to make
   NLFR useful beyond the demo.

## What NLFR is

NLFR is a local-first black-box recorder for agent validation loops. It does
not try to become a CI system, dashboard, tracing stack, or SaaS product in the
MVP. It records evidence from a Bazel/NativeLink validation path, normalizes it
into SQLite, exports truth-labeled projection JSON, and renders a sparse canvas
from that projection only.

The short thesis from [`ONE_PAGER.md`](ONE_PAGER.md):

> When AI writes the code, NativeLink makes validating it fast, and NLFR makes
> validating it trustworthy.

The repo rule that matters most:

> Build an evidence-first recorder, not a UI-first dashboard.

That means every node, edge, metric, and proof claim needs truth labels:

- `source_kind`: `collectable_v1`, `derived_v1`, `simulated_v1`, or `future`.
- `confidence`: `high`, `medium`, `low`, or `unknown`.
- `evidence_refs`: artifact or fixture references backing the claim.
- `redaction_state`: `safe`, `redacted`, `blocked`, or `unknown`.

## The current app in pictures

These screenshots are fixture-backed `simulated_v1` canvas renders. They are
useful for understanding the current app surface, not for claiming live
NativeLink execution. The real proof summaries live in
[`proof-samples/`](proof-samples/), and the real scripts write under ignored
`data/`.

### Action Graph

![Action Graph canvas rendered from fixture-backed projection JSON](images/canvas-desktop.png)

This is the main canvas. It renders `apps/canvas/public/projections/action-graph.json`.
The graph shows the evidence chain:

`agent -> change -> run -> target -> action -> cache_event`

The bottom-left legend explains the truth labels. Purple nodes are simulated
fixture evidence in the no-Nix demo. Green is reserved for collectable evidence
from real tool output.

### Agent-loop focus

![Agent-loop focus rendered from fixture projection JSON](images/canvas-agent-loop.png)

Typing `agent loop` in the operator input isolates the deterministic
bounded-agent patch provenance: the agent node, the change node, and their
relationship to the validation run.

Important honesty point: this is not a live LLM call. The scenario carries a
`model` label and `prompt_sha256`, but the raw prompt is never stored and no
tokens are spent.

### Proof Packet

![Proof Packet view rendered from fixture projection JSON](images/canvas-proof.png)

The Proof Packet is the "what can we actually claim?" view. It summarizes scope,
invocations, cache evidence, validation surface, artifacts, stored proof blocks,
and unsupported claims.

### Remote Boundary

![Remote Boundary view showing gated worker claims](images/canvas-remote-boundary.png)

The Remote Boundary lens is intentionally conservative. It can show when a
recorded Bazel invocation was configured with remote execution or when a proof
script observed worker endpoints. It does not claim worker identity, action
placement, queue time, scheduler assignment, or load distribution unless direct
evidence exists.

### Failure focus

![Failure focus view rendered from fixture projection JSON](images/canvas-failure-focus.png)

Typing `failures` isolates failure nodes and opens the evidence inspector. The
point is not to hide failed validation; the point is to make failed proof
inspectable and labeled.

### Mobile shape

![Mobile canvas screenshot](images/canvas-mobile.png)

The canvas is sparse and responsive enough for inspection, but mobile is not the
primary MVP surface.

### Operator flow video

<video controls src="images/canvas-operator-flow.webm" width="900"></video>

If your Markdown renderer does not play WebM inline, open
[`images/canvas-operator-flow.webm`](images/canvas-operator-flow.webm).

To regenerate these assets from a running canvas dev/preview server:

```bash
npm --prefix apps/canvas run dev -- --host 127.0.0.1
CANVAS_URL=http://127.0.0.1:5174/ npm --prefix apps/canvas run capture
cp output/playwright/canvas-*.png docs/images/
cp output/playwright/canvas-operator-flow.webm docs/images/
```

The committed files in `docs/images/` are the walkthrough copies. Fresh captures
land in ignored `output/playwright/` first.

## How someone uses the demo today

There are two evaluator paths.

### Path A: fixture-backed canvas, no Nix

Use this when the evaluator wants to understand the interface quickly.

```bash
uv sync
npm --prefix apps/canvas install
uv run pytest tests -q
scripts/verify-demo.sh
npm --prefix apps/canvas run dev -- --host 127.0.0.1
```

Then open the Vite URL and drive the operator bar:

- `agent loop` highlights agent/change provenance.
- `proof` opens the proof packet.
- `remote` opens the remote boundary lens.
- `failures` isolates failure evidence.
- `cache` highlights cache events.
- `reset` returns to the full graph.

What this path proves:

- The backend tests pass.
- Fixture evidence can be ingested and projected.
- The canvas can render the projected graph/proof JSON.
- The demo UI can explain evidence labels.

What this path does not prove:

- Live NativeLink cache behavior.
- Live remote execution worker behavior.
- Live LLM agent behavior.

### Path B: real Nix proof path

Use this when the evaluator is a skeptic and wants to re-run evidence.

```bash
nix develop
scripts/cold-warm-cache-proof.sh
NLFR_EXPECTED_WORKERS=2 NLFR_LOCAL_EXEC_OUTPUT=$PWD/data/local-exec-proof-2w \
  scripts/local-exec-proof.sh
scripts/agent-loop-proof.sh
```

The scripts write summaries and projections under ignored `data/`. Redacted
copies of representative summaries are committed in
[`proof-samples/`](proof-samples/).

What this path proves today:

- Cold/warm NativeLink cache behavior can be recorded from real tool output.
- A warm cache leg recorded higher hit rate and lower duration in the current
  proof sample.
- Two local worker endpoints can be configured and observed live.
- A deterministic bounded-agent patch can be linked to validation/cache evidence
  through the action graph.

What remains explicitly unproven:

- Worker identity.
- Scheduler assignment.
- Queue time.
- Action placement.
- Load distribution.
- Multi-machine fleet behavior.
- Production AI-agent identity/auth.

## The system architecture

The core architecture is a one-way evidence pipeline:

```text
Bazel / NativeLink / scenario
  -> immutable artifacts with SHA-256 hashes
  -> SQLite evidence spine
  -> projection JSON
  -> canvas and proof docs
```

The UI is last on purpose. The canvas does not query Bazel, NativeLink, logs, or
an API at runtime. It reads projection JSON from `apps/canvas/public/projections/`.

### Layer 0: commands

The CLI starts at `src/nlfr/cli.py` and registers subcommands through
`src/nlfr/commands/__init__.py`.

The commands you will use most:

- `nlfr doctor`: environment readiness.
- `nlfr run`: run Bazel/NativeLink and record process artifacts.
- `nlfr ingest`: parse Bazel evidence into SQLite.
- `nlfr graph export`: export Action Graph JSON.
- `nlfr proof export`: export Proof Packet JSON.
- `nlfr runway export`: export Validation Runway JSON.
- `nlfr simulate`: apply deterministic agent patch scenarios and record
  provenance.

### Layer 1: artifact capture

`src/nlfr/artifacts.py` owns immutable artifact writes. It hashes bytes with
SHA-256, writes each artifact once, and appends `artifact_manifest.json`.

This is the "do not trust memory" layer. If a proof refers to a file, that file
has a manifest entry, hash, size, producer command, redaction state, source kind,
confidence, and evidence refs.

### Layer 2: SQLite evidence spine

`src/nlfr/db/schema.py` defines the core tables:

- `runs`
- `changes`
- `invocations`
- `artifacts`
- `targets`
- `actions`
- `cache_events`
- `failures`
- `graph_nodes`
- `graph_edges`
- `proof_blocks`

All core rows carry the truth-label columns. This is what prevents the UI from
accidentally implying a stronger claim than the recorder captured.

### Layer 3: ingest

`src/nlfr/ingest/bazel.py` parses compact Bazel evidence:

- BEP JSON/JSONL into targets, actions, and failures.
- Execution log JSON into cache events.
- Bazel profile JSON into derived cache observations.

`src/nlfr/ingest/sqlite.py` inserts parsed evidence into the schema with stable
keys so ingest is idempotent.

### Layer 4: projectors

Projectors read SQLite and export versioned JSON:

- `src/nlfr/projectors/graph.py` creates nodes and edges for the Action Graph.
- `src/nlfr/projectors/proof.py` creates proof blocks and cache economics.
- `src/nlfr/projectors/runway.py` creates a simplified validation sequence.
- `src/nlfr/projectors/remote_execution.py` sanitizes and gates remote-execution
  claims.

This layer is where truth labels become visible product behavior.

### Layer 5: canvas

The canvas is in `apps/canvas/src/`. The central file is `App.tsx`.

It fetches:

- `/projections/action-graph.json`
- `/projections/proof.json`

Then it renders:

- Action Graph nodes and edges.
- Proof Packet drawer.
- Remote Boundary lens.
- Validation Runway overlay.
- Operator command input.
- Truth-label legend.

The layout is deterministic (`layout.ts`) and the types are explicit
(`types.ts`).

## Walk the repo in this order

Start here:

1. `AGENTS.md` for product and engineering rules.
2. `README.md` for the quick-start and current proof paths.
3. `docs/ONE_PAGER.md` for the shortest product framing.
4. `docs/DEMO_SCRIPT.md` for the rehearsal path.
5. `docs/proof-samples/README.md` and the three JSON samples.

Then trace the backend:

1. `src/nlfr/cli.py`
2. `src/nlfr/commands/run_cmd.py`
3. `src/nlfr/artifacts.py`
4. `src/nlfr/db/schema.py`
5. `src/nlfr/commands/ingest_cmd.py`
6. `src/nlfr/ingest/bazel.py`
7. `src/nlfr/ingest/sqlite.py`
8. `src/nlfr/projectors/graph.py`
9. `src/nlfr/projectors/proof.py`
10. `src/nlfr/commands/simulate_cmd.py`

Then trace the UI:

1. `apps/canvas/public/projections/action-graph.json`
2. `apps/canvas/public/projections/proof.json`
3. `apps/canvas/src/types.ts`
4. `apps/canvas/src/layout.ts`
5. `apps/canvas/src/App.tsx`
6. `apps/canvas/src/styles.css`
7. `apps/canvas/scripts/capture-proof.mjs`

Then trace the proofs:

1. `scripts/verify-demo.sh`
2. `scripts/cold-warm-cache-proof.sh`
3. `scripts/local-exec-proof.sh`
4. `scripts/agent-loop-proof.sh`

Finally read the tests:

1. `tests/test_cli.py`
2. `tests/test_ingest_bazel.py`
3. `tests/test_projectors.py`
4. `tests/test_simulate_cmd.py`
5. `tests/test_artifacts.py`

## The key mental model

NLFR is not trying to say "the build is good" or "the agent was smart."

It is trying to say:

1. Here is exactly what ran.
2. Here are the artifacts we captured.
3. Here are their hashes.
4. Here is what we parsed into SQLite.
5. Here is the projection JSON.
6. Here is what the canvas can show.
7. Here are the claims we still cannot make.

That last item is not a weakness of the demo. It is the product's differentiator.

## Where the MVP stops

The MVP is now credible as a local proof kit. It is not yet "actually useful" as
a day-to-day platform tool for a team. The largest missing pieces are covered in
[`USEFULNESS_ROADMAP.md`](USEFULNESS_ROADMAP.md), but the short version is:

- Package the reference architecture so another repo can adopt it quickly.
- Add repeatable multi-run history and comparison.
- Make proof exports easy to attach to PRs or CI artifacts.
- Preserve the evidence spine while improving operator ergonomics.
- Do not build SaaS/auth/billing or a worker dashboard before direct evidence
  exists for the claims those surfaces would imply.
