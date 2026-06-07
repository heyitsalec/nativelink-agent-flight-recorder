# Cursor adapter — bounded agent change recording

Thin adapter for recording Cursor agent edits through NLFR without exporting raw
prompts. Provenance matches the bounded-LLM contract in
`demo/scenarios/llm-bounded-patch.json`: **`model` + `prompt_sha256` only**.

## When to use

After a Cursor session applies a bounded edit to the repo, run the recorder to
capture:

- before/after hashes for the touched file (`--change-path`)
- adapter metadata (`collectable_v1`) with model label and prompt hash
- optional validation command output (pytest, Bazel, etc.)

The canvas and proof exports derive the `agent` node from the
`agent-provenance.json` artifact — never from a stored prompt.

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

- The script reads `--prompt-file` only to compute SHA-256.
- Exports contain `prompt_sha256` and `model` — same shape as the demo scenario.
- Raw prompt text is never written to NLFR artifacts, SQLite, or projection JSON.

## Cursor workflow

1. Complete the bounded edit in Cursor (single file or small leaf change).
2. Save the session prompt to a local file (or reuse Cursor's prompt export).
3. Run `record-agent-change.sh` with `--change-path` pointing at the edited file.
4. Optionally pass `--command` with a targeted test command for the validation leg.
5. Inspect `data/agent-change-proof/summary.json` and exported projections.

## Truth labels

| Leg | `source_kind` | Notes |
|-----|---------------|-------|
| Agent adapter metadata | `collectable_v1` | From `record-agent-change.sh` sidecar |
| Validation command | `collectable_v1` | From `nlfr run --mode generic` process capture |
| Simulated demo scenarios | `simulated_v1` | `nlfr simulate` only — not this adapter |

Mixed labels in `summary.json` are intentional and honest when validation runs
through real command capture.

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
