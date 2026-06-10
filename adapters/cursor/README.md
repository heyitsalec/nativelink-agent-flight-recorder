# Cursor adapter — bounded agent change recording

Thin adapter for recording Cursor agent edits through NLFR without exporting raw
prompts. Provenance matches the bounded-LLM contract in
`demo/scenarios/llm-bounded-patch.json`: **`model` + `prompt_sha256` only**.

Proof matrix: [M8 agent adapter](../../docs/wiki/reference/proof-scripts-matrix.md#m8-agent-adapter).

## Scope boundary

| In scope | Out of scope |
|----------|--------------|
| Bounded single-file (or small leaf) edits | Multi-agent fleet orchestration |
| `model` + `prompt_sha256` provenance (`collectable_v1`) | Raw prompt storage or export |
| Validation via `--command` stdout capture | Live LLM reasoning as proof |
| `agent → change → run` graph chain | Worker placement, queue time, scheduler claims |

## When to use

After a Cursor session applies a bounded edit to the repo, run the recorder to
capture:

- before/after hashes for the touched file (`--change-path`)
- adapter metadata (`collectable_v1`) with model label and prompt hash
- optional validation command output (pytest, Bazel, etc.)

The canvas and proof exports derive the `agent` node from the
`agent-provenance.json` artifact — never from a stored prompt.

## Live E2E runbook

Use this path when you need a **non-dry-run** `collectable_v1` chain that matches
the deterministic `llm-bounded-patch` shape but comes from a real adapter
invocation.

### Prerequisites

```bash
# From repo root — uv + PYTHONPATH wired by record-agent-change.sh
uv run pytest tests/test_record_agent_change.py -q
```

No NativeLink or Bazel required for the M8 adapter path. Validation is whatever
you pass to `--command` (pytest is the usual dogfood leg).

### Operator flow (manual live proof)

1. **Bounded edit in Cursor** — change one leaf file; save the workspace file.
2. **Capture prompt locally** — export or copy the session prompt to a file on
   disk (e.g. `/tmp/cursor-prompt.txt`). This file is hashed at record time and
   never ingested.
3. **Record the change** (non-dry-run):

```bash
./scripts/record-agent-change.sh \
  --change-path docs/M8_E2E_MARKER.md \
  --model composer-2.5 \
  --prompt-file /tmp/cursor-prompt.txt \
  --command "uv run pytest tests/test_record_agent_change.py -q --tb=no"
```

4. **Inspect outputs** under `data/agent-change-proof/` (gitignored):

| Artifact | Purpose |
|----------|---------|
| `summary.json` | Run status, model, `prompt_sha256`, truth labels |
| `run.json` | Full `nlfr run` payload |
| `agent-provenance.json` | Collectable provenance block (under artifact root) |
| `projections/action-graph.json` | `agent` node + `authored_change` edge |
| `projections/proof.json` | Proof packet export |

5. **Verify privacy** — grep artifacts for prompt text; only `prompt_sha256`
   should appear. See [Privacy](#privacy) below.

6. **Optional graph spot-check**:

```bash
PYTHONPATH=src uv run python -m nlfr graph export \
  --db data/agent-change-proof/nlfr.sqlite \
  --run-group agent-change \
  --output /tmp/action-graph.json
```

Expect an `agent` node with `source_kind=collectable_v1` linked to the change
row for `--change-path`.

Reference run: see the M8 row in
[`docs/wiki/reference/proof-scripts-matrix.md`](../../docs/wiki/reference/proof-scripts-matrix.md)
(per-wave working notes live in git history; see [`docs/METHOD.md`](../../docs/METHOD.md)).

## `agent-live-proof.sh`

Automated proof gate for Wave 2 — runs a **non-dry-run** adapter record or writes
an honest environment blocker. Use after adapter contract tests pass.

```bash
./scripts/record-agent-change.sh --dry-run   # regression smoke
./scripts/agent-live-proof.sh --dry-run      # CI contract; no Cursor CLI required
./scripts/agent-live-proof.sh                # live leg or honest blocker
NLFR_RUN_AGENT_LIVE=1 uv run pytest tests/test_agent_live_proof.py -q  # live gate
uv run pytest tests/test_record_agent_change.py tests/test_agent_live_proof.py tests/test_agent_live_proof_samples.py -q
```

### What it does

1. **`--dry-run`** — plans adapter invocation via `record-agent-change.sh --dry-run`;
   emits JSON on stdout; exit `0` (CI-safe, no Cursor CLI).
2. **Live path** — probes `cursor` on PATH (override: `NLFR_CURSOR_BIN`). When
   missing, writes honest `environment-blocker.json` (exit `2`) — see
   [`agent-live-blocker-sample.json`](../../docs/proof-samples/agent-live-blocker-sample.json).
3. When Cursor CLI is present, invokes `record-agent-change.sh` **without**
   `--dry-run` into `data/agent-live-proof/` (override: `NLFR_AGENT_LIVE_OUTPUT`).
4. Exports graph + proof projections, writes `summary.json`, and asserts
   `chain_complete=true` with no raw prompt text in artifacts.

### Outputs

| Outcome | Path | Exit |
|---------|------|------|
| Green | `data/agent-live-proof/summary.json` | 0 |
| Blocker | `data/agent-live-proof/environment-blocker.json` | 2 |

Promoted redacted samples live under `docs/proof-samples/`:

| Sample | When to cite |
|--------|--------------|
| [`agent-live-blocker-sample.json`](../../docs/proof-samples/agent-live-blocker-sample.json) | No Cursor CLI on host (expected on many CI/dev machines) |
| [`agent-live-summary-sample.json`](../../docs/proof-samples/agent-live-summary-sample.json) | Fixture-backed `chain_complete` shape (pytest validation leg) |

See [proof-samples hub](../../docs/proof-samples/README.md).

Environment overrides: `NLFR_AGENT_LIVE_OUTPUT`, `NLFR_AGENT_LIVE_CHANGE_PATH`,
`NLFR_AGENT_LIVE_MODEL`, `NLFR_AGENT_LIVE_PROMPT_FILE`,
`NLFR_AGENT_LIVE_COMMAND`, `NLFR_CURSOR_BIN`, `NLFR_AGENT_LIVE_FORCE_BLOCKER`
(test probe only).

## Honest blocker policy

NLFR does **not** upgrade a missing live agent session into a fake collectable run.

| Condition | Behavior | `source_kind` |
|-----------|----------|---------------|
| Cursor / operator cannot supply a real bounded edit + prompt file | `environment-blocker.json`, exit 2 | `collectable_v1` |
| `uv` or repo layout missing | `environment-blocker.json`, exit 2 | `collectable_v1` |
| Validation command fails | `summary.json` with failed run status; not `chain_complete` | `collectable_v1` |
| Dry-run only | Planned JSON on stdout; no SQLite mutation | `collectable_v1` |

**Stop rules:**

- Never write raw prompt text to `data/`, SQLite, or projection JSON.
- Never label a run `chain_complete=true` without a real non-dry-run record and
  graph linkage.
- A blocker artifact is a **valid** proof outcome — cite it honestly instead of
  implying live Cursor E2E ran on hosts that could not produce it.

Blocker shape matches other proof scripts (`status`, `reason`, truth labels,
`evidence_refs`).

## Quick start

```bash
# Smoke test (no SQLite or artifact writes)
./scripts/record-agent-change.sh \
  --change-path README.md \
  --model composer-2.5 \
  --prompt-file /tmp/cursor-prompt.txt \
  --dry-run

# Record a real session (agent already edited the file)
./scripts/record-agent-change.sh \
  --change-path src/nlfr/commands/generic_run.py \
  --model composer-2.5 \
  --prompt-file ~/.cursor/sessions/latest-prompt.txt \
  --command "uv run pytest tests/test_generic_run.py -q --tb=no"
```

## Arguments

| Flag | Required | Description |
|------|----------|-------------|
| `--change-path` | yes | Path relative to workspace that the agent changed |
| `--model` | yes | Model label (e.g. `composer-2.5`, `claude-4.6-sonnet`) |
| `--prompt-file` | yes | Local prompt text; hashed at record time, never exported |
| `--command` | no | Shell command for validation leg (default: `true`) |
| `--dry-run` | no | Emit sidecar JSON + planned `nlfr` command only |
| `--output-dir` | no | Default: `data/agent-change-proof` |
| `--workspace` | no | Default: repo root |

Environment overrides: `NLFR_AGENT_CHANGE_OUTPUT`, `NLFR_AGENT_CHANGE_WORKSPACE`,
`NLFR_AGENT_CHANGE_SCENARIO`, `NLFR_AGENT_CHANGE_RUN_GROUP`.

## Privacy

**Policy: prompt hash only.**

- `--prompt-file` is read once to compute SHA-256; contents are not copied into
  NLFR artifacts, SQLite, or projection JSON.
- Exports carry `prompt_sha256` and `model` — same fields as
  `demo/scenarios/llm-bounded-patch.json` (`simulated_agent` shape).
- Sidecar and `agent-provenance.json` use
  `input_signal: "redacted: prompt withheld, hash retained"`.
- Do not commit prompt files, session exports, credentials, env vars, or customer
  data. `data/` is gitignored; promote only redacted `summary.json` samples.

**Verification** (after a live record):

```bash
# Replace HASH with your prompt_sha256 from summary.json
grep -r "Add a leaf test" data/agent-change-proof/ && echo "FAIL: raw prompt leaked" || echo "OK"
```

If raw prompt text appears in any artifact, **stop** — that is a wave-blocking
privacy violation, not a successful proof.

## Cursor workflow

1. Complete the bounded edit in Cursor (single file or small leaf change).
2. Save the session prompt to a local file (or reuse Cursor's prompt export).
3. Run `record-agent-change.sh` with `--change-path` pointing at the edited file.
4. Optionally pass `--command` with a targeted test command for the validation leg.
5. Inspect `data/agent-change-proof/summary.json` and exported projections.
6. For release gates, run `./scripts/agent-live-proof.sh` and attach
   `summary.json` or `environment-blocker.json`.

## Truth labels

| Leg | `source_kind` | Notes |
|-----|---------------|-------|
| Agent adapter metadata | `collectable_v1` | From `record-agent-change.sh` sidecar |
| Validation command | `collectable_v1` | From `nlfr run --mode generic` process capture |
| Graph `agent` node | `derived_v1` | Projected from `agent_provenance` proof block |
| Simulated demo scenarios | `simulated_v1` | `nlfr simulate` only — not this adapter |
| Environment blocker | `collectable_v1` | Honest probe when live E2E cannot run |

Mixed labels in `summary.json` are intentional and honest when validation runs
through real command capture.

| Claim | Label | Gate |
|-------|-------|------|
| Agent change recorded non-dry-run | `collectable_v1` / `high` | `chain_complete=true` in summary |
| Prompt content stored | **blocked** | Stop if raw prompt in artifacts |
| Live LLM reasoning as proof | **blocked** | Provenance is claim source, not validation proof |

## Under the hood

`record-agent-change.sh` builds a provenance sidecar JSON and invokes:

```bash
nlfr run --mode generic \
  --change-path <file> \
  --provenance-sidecar <sidecar.json> \
  --command "<validation>"
```

Generic run writes `agent-provenance.json`, upserts an `agent_provenance` proof
block, and links change rows for graph projection (`agent → change → run`).

## Related

- [Agent loop provenance diagram](../../docs/diagrams/agent-loop-provenance.md)
- [M8 agent adapter DAG](../../docs/dags/m8-agent-adapter.md)
- [Truth labels reference](../../docs/wiki/reference/truth-labels.md)
