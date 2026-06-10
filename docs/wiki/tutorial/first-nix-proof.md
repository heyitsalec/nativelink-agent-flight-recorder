# Tutorial: first Nix proof

**Quadrant:** Tutorial · **Audience:** evaluators on an independent host  
**Time:** ~30+ minutes · **Requires:** Nix, x86_64-linux or supported flake host

Run real NativeLink cache economics proof and inspect `collectable_v1` artifacts.
This is the **real proof** path from [One pager § Evaluator paths](../../ONE_PAGER.md).

← [Wiki hub](../README.md) · [Adoption guide](../../ADOPTION_GUIDE.md)

## What you will prove

Cold/warm cache reuse with measurable deltas in proof JSON:

- Cold run: `hit_rate` 0.0 (~8.17s in reference proof)
- Warm run: `hit_rate` 1.0 (~5.48s in reference proof)
- Labels: `collectable_v1`, `high`

Evidence path: `data/cold-warm-proof/summary.json` (gitignored on your machine).

## Prerequisites

1. Enter the Nix dev shell:

```bash
nix develop
```

2. Confirm tools:

```bash
python3 -m nlfr doctor --mode cache-only
```

3. Read honest ceilings in [Architecture track § Phase 2](../../ARCHITECTURE_TRACK.md).
This tutorial does **not** prove scheduler assignment, queue time, or fleet behavior.

## Step 1 — Run cold/warm cache proof

```bash
./scripts/cold-warm-cache-proof.sh
```

The script starts NativeLink cache mode, runs Bazel cold then warm, ingests evidence,
and writes `data/cold-warm-proof/summary.json`.

On blocker hosts it writes `environment-blocker.json` instead — that is an honest
outcome, not a failure of the doc.

## Step 2 — Inspect summary.json

```bash
jq '.claim_boundary, .cache_economics' data/cold-warm-proof/summary.json
```

Confirm:

- `warm_hit_rate_higher` and `warm_duration_lower` (or equivalent metrics) are present
- Truth labels on metrics match [truth labels reference](../reference/truth-labels.md)
- No invented dollar savings or fleet claims

Redacted reference: [proof-samples](../../proof-samples/README.md).

## Step 3 — Export and view (optional)

```bash
PYTHONPATH=src uv run python -m nlfr proof export \
  --db data/cold-warm-proof/nlfr.sqlite \
  --run-group latest \
  --output /tmp/cold-warm-proof-packet.json
```

## Optional ladder steps

Run these only when you need the next claim boundary. Each has its own script and
`summary.json` — see [proof scripts matrix](../reference/proof-scripts-matrix.md).

| Step | Script | Claim |
|------|--------|-------|
| Local-exec readiness | `scripts/local-exec-proof.sh` | `worker_endpoints_ready` |
| Two-worker endpoints | `NLFR_EXPECTED_WORKERS=2 … local-exec-proof.sh` | Two workers configured + live |
| M7 worker identity | `scripts/worker-evidence-proof.sh` | Conditional `worker_identity` |
| Agent loop | `scripts/agent-loop-proof.sh` | `chain_complete=true` |
| LRE cold/warm | `scripts/lre-cold-warm-proof.sh` | `lre_cache_parity_observed` (linux) |

## GHA offline

Do not require CI green to trust your local Nix run. Parent proof gates are local:

```bash
uv run pytest -q
bash -n scripts/cold-warm-cache-proof.sh
```

## Next steps

| Goal | Page |
|------|------|
| Fixture path without Nix | [First evidence loop](first-evidence-loop.md) |
| M8 Cursor recording | [Cursor adapter](../../../adapters/cursor/README.md) |
| M9 compare two proof runs | [Export and compare](../how-to/export-and-compare-run-groups.md) |
| Full phase map | [Architecture track](../../ARCHITECTURE_TRACK.md) |
