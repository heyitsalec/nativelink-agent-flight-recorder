# NLFR demo script

A 5-step rehearsal path for showing the Agent Flight Recorder. Every step is
backed by recorded evidence — nothing here narrates ahead of proof. The first
three steps need no Nix; steps 4–5 prove the real NativeLink validation/cache legs.

Total time: ~5 min (steps 1–3) or ~30 min including the Nix proofs.

## Before you start

```bash
uv sync
npm --prefix apps/canvas install
```

Talking point: "This is a local-first black-box recorder. The canvas only ever
renders recorded facts — it never invents backend state. Watch the truth labels."

---

## Step 1 — Doctor: the environment is honest (~30s)

```bash
PYTHONPATH=src uv run python -m nlfr doctor --mode cache-only --json
```

Show: the JSON reports tool availability and an explicit `ok` flag. Outside Nix
it records a blocker instead of pretending. **Point:** the recorder tells the
truth about its own environment before it records anything.

## Step 2 — Backend tests are green (~30s)

```bash
uv run pytest tests -q
```

Show: the full suite passes. **Point:** projections, ingest idempotency, and
truth-labeling are all under test against real SQLite and fixture files.

## Step 3 — Fixture canvas: the Action Graph + truth legend (~2 min)

```bash
npm --prefix apps/canvas run dev -- --host 127.0.0.1
```

Open the dev server. Then drive the operator bar (bottom center):

1. Default view → the `agent → change → run → validation → cache` chain.
2. Type `agent loop` → isolates the deterministic bounded-agent patch provenance.
3. Type `proof` → opens the Proof Packet with unsupported claims listed.
4. Type `remote` → the Remote Boundary lens, with worker claims explicitly gated.
5. Type `reset` → back to the full graph.

Show: the **truth-label legend** (bottom left). **Point:** every node is colored
by `source_kind`. This no-Nix canvas is a `simulated_v1` fixture chain — not a
live run. The matching Nix proof in step 5 is where the validation/cache leg
becomes `collectable_v1`.

> No Nix? Stop here. `docs/proof-samples/` holds redacted real summaries to read.

---

## Step 4 — Real cold/warm cache economics (~10 min, Nix)

```bash
nix develop
scripts/cold-warm-cache-proof.sh
```

Show: `data/cold-warm-proof/summary.json` — cold `hit_rate` 0.0 / ~8.2s vs warm
`hit_rate` 1.0 / ~5.5s. **Point:** this is `collectable_v1` — measured from real
Bazel runs through a real NativeLink cache, not a claim.

## Step 5 — Agent-loop closure: validation/cache spine (~15 min, Nix)

```bash
scripts/agent-loop-proof.sh
```

Show: `data/agent-loop-proof/summary.json` with `chain_complete=true`. A
deterministic bounded-agent patch validated through `agent → change → run →
target → action → cache_event`. **Point:** the patch carries a `model` label and
a `prompt_sha256` only — the raw prompt is never stored and no live LLM call is
made. The validation/cache leg is `collectable_v1`; the agent/change provenance
stays `simulated_v1`. That distinction is the product: trustworthy validation,
honestly labeled.

---

## One-command version

```bash
scripts/verify-demo.sh
```

Runs tests, doctor, real-tool smoke, cold/warm, local-exec, the agent-loop
closure proof, the simulated fixture chain, projection exports, and the canvas
build — recording blockers instead of faking success when tools are absent.

## Closing line

"When AI writes the code, NativeLink makes validating it fast, and NLFR makes
validating it trustworthy — with every claim labeled by how it was proven."
