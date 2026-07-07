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

## Observation modes — what `changed` is derived against

`changed` (and the `patch_applied` rollup) is always **derived**, never asserted.
But the recorder can only honestly derive a change from what it can **observe**.
There are three modes, and each per-path entry records which one applied via
`changed_basis`:

| Mode | When | `changed_basis` | What it attests |
|------|------|-----------------|-----------------|
| **(a) git baseline** | The change path is **tracked in a git workspace**. The adapter captures the pre-edit bytes from `git show <ref>:<path>` into the sidecar. **Takes priority for every tracked path** — even when the edit happens inside `--command`. | `git_baseline` | `changed = baseline_sha256 != after_sha256`. Honest claim: *"differs from the baseline ref."* **Works edit-first** — this is the recommended documented flow. |
| **(b) recorder window** | The change path is **untracked, or the workspace is not a git repo**, and the edit happens **inside** `--command`. | `recorder_window` | `changed = before_sha256 != after_sha256`. The recorder samples the file at process start and end, so it observes the edit directly. |
| **(c) unobservable** | **Untracked or non-git** path **and** the file is already at its final state when recording begins (edit happened before the invocation). | `recorder_window` | `changed=false` with an explicit note **and a stderr warning** — the recorder cannot attest whether the agent changed the file. Recorded honestly, never silently. |

Why this matters: the documented flow below **edits first, then records** (the
`--command` is validation only). Without a baseline, `before == after` on every
such invocation and `changed` would be a silent, always-false — the recorder
would fail to attest a real change. Mode (a) fixes this with **verifiable git
evidence**: the git object store still holds the committed pre-edit bytes, so a
skeptic can recompute `git show <commit>:<path> | sha256sum` and match it against
the recorded `baseline_sha256`. The baseline is labeled explicitly
(`baseline_source: {kind: git_head, commit, ref}`) and never conflated with the
recorder's own before/after window. Note that **`recorder_window` is the fallback
for untracked or non-git paths only** — a tracked path always uses mode (a), even
for edits made inside `--command`.

Baselines are **re-verified, not trusted**: the sidecar is a public interface, so
`nlfr run` recomputes `git show <commit>:<path>` in the workspace and hashes it
before honoring any supplied `git_baseline`. A forged/stale `baseline_sha256`, or
a commit/object that cannot be resolved in this workspace, is **refused** — that
path falls back to `recorder_window` with an explicit note and a stderr warning,
recorded honestly rather than hard-failed.

Commit-before-record: if the edit was **committed before recording began**, the
default `HEAD` baseline already equals the final state (`baseline == after`), so
the change is not attestable against `HEAD`. Rather than emit a silent
`changed=false`, the recorder flags it — a per-path note naming the commit and a
stderr warning pointing at **`--baseline-ref`**. Pass the true pre-edit ref
(`--baseline-ref HEAD~1` or a commit sha) to capture the pre-edit blob and attest
the committed change.

Honesty ceiling: mode (a) attests **"differs from the baseline ref"** — the honest
claim when the operator edited before invoking. It does **not** prove the named
model authored the edit (that requires a receipt; see [Provenance ladder](#provenance-ladder)).

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

Run this in a **git-tracked workspace** with the edited file tracked (mode (a)
above). Editing first and recording second is fully supported: the adapter reads
the pre-edit bytes from `git show HEAD:<path>`, so `changed` is evidence-backed
even though your edit already landed in the working tree.

1. **Bounded edit in Cursor** — change one tracked leaf file; save the workspace
   file. (No need to record before editing — the git baseline captures the
   pre-edit state from HEAD.)
2. **Capture prompt locally** — export or copy the session prompt to a file on
   disk (e.g. `/tmp/cursor-prompt.txt`). This file is hashed at record time and
   never ingested.
3. **Record the change** (non-dry-run):

```bash
./scripts/record-agent-change.sh \
  --change-path README.md \
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
(per-wave working notes live in git history; see [`docs/internal/METHOD.md`](../../docs/internal/METHOD.md)).

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

# Record a real session (agent already edited the file).
# In a git-tracked workspace the pre-edit state is read from HEAD, so recording
# AFTER the edit still yields an evidence-backed changed=true (mode (a) above).
./scripts/record-agent-change.sh \
  --change-path src/nlfr/commands/generic_run.py \
  --model composer-2.5 \
  --prompt-file ~/.cursor/sessions/latest-prompt.txt \
  --command "uv run pytest tests/test_generic_run.py -q --tb=no"
```

> If the workspace is **not** a git repo (or the path is untracked) and the edit
> already landed before recording, the change is **not observable** — the record
> completes with `changed=false`, an explicit note, and a stderr warning naming
> the path (mode (c) above). Either record inside a git-tracked workspace or make
> the edit happen inside `--command` (mode (b)).

## Arguments

| Flag | Required | Description |
|------|----------|-------------|
| `--change-path` | yes | Path relative to workspace that the agent changed |
| `--model` | yes | Model label (e.g. `composer-2.5`, `claude-4.6-sonnet`) |
| `--prompt-file` | yes | Local prompt text; hashed at record time, never exported |
| `--command` | no | Shell command for validation leg (default: `true`) |
| `--baseline-ref` | no | Git ref holding the **pre-edit** state (default: `HEAD`). Use `HEAD~1` or a commit sha when the edit was **committed** before recording — otherwise `HEAD` equals the final state and the change is not attestable (see [Observation modes](#observation-modes--what-changed-is-derived-against)) |
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
| Graph `agent` node | **inherits the proof block** — `collectable_v1` (recorded adapter run) / `simulated_v1` (simulate) | `_project_agents` copies the `agent_provenance` block's own `source_kind`/`confidence` verbatim; it does **not** re-label the node to `derived_v1` |
| Simulated demo scenarios | `simulated_v1` | `nlfr simulate` only — not this adapter |
| Environment blocker | `collectable_v1` | Honest probe when live E2E cannot run |

Mixed labels in `summary.json` are intentional and honest when validation runs
through real command capture.

| Claim | Label | Gate |
|-------|-------|------|
| Agent change recorded non-dry-run | `collectable_v1` / `high` | `chain_complete=true` in summary |
| Prompt content stored | **blocked** | Stop if raw prompt in artifacts |
| Live LLM reasoning as proof | **blocked** | Provenance is claim source, not validation proof |

## Provenance ladder

Separately from the four truth labels, the agent leg carries a **`provenance_class`**
that records *how the model attribution was established*:

| `provenance_class` | Established by | Model label is | This adapter |
|--------------------|----------------|----------------|--------------|
| `operator_asserted_v1` | Operator `--model` + hashed prompt; no server verification | An operator claim | **Ceiling for this path** |
| `stub_receipt_v1` | A deterministic (non-live) `nlfr.agent_receipt.v1` receipt | Simulated (`simulated_v1` agent leg) | Not reachable here |
| `receipt_verified_v1` | A live `nlfr agent-invoke` receipt pinning the server-resolved model id, session id, and `response_sha256` | Server-verified | Not reachable here |

`record-agent-change.sh` invokes `nlfr run --mode generic` with `--provenance-sidecar`
**only** — it cannot pass `--agent-receipt`. So this integration's maximum is
**`operator_asserted_v1`**: the `model` you supply is an operator assertion, not a
verified fact.

**What operator assertion does NOT prove:** that the named model actually authored
the edit. It proves only that *these bytes changed* (derived by
[observation mode](#observation-modes--what-changed-is-derived-against) — against
the git baseline when available, else the recorder's own before/after window) and
that *this operator asserted this model over this prompt hash*. To upgrade to
`receipt_verified_v1`, capture the session with
[`nlfr agent-invoke`](../../docs/proof-samples/README.md) and record its
`nlfr.agent_receipt.v1` receipt. The full class ladder is defined in the
[truth labels reference](../../docs/wiki/reference/truth-labels.md#agent-provenance-class-provenance_class)
and the [in-toto attestation how-to](../../docs/wiki/how-to/export-in-toto-attestation.md).

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
