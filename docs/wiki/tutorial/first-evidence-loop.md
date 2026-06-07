# Tutorial: first evidence loop

**Quadrant:** Tutorial · **Audience:** skeptical evaluators, new contributors  
**Time:** ~5 minutes · **Requires:** Python 3.11+, `uv`, no Nix

Learn the canonical NLFR flow with fixture-backed proofs. You will run tests,
export projection JSON, and open the canvas — without claiming live NativeLink
economics.

← [Wiki hub](../README.md) · [One pager](../../ONE_PAGER.md)

## What you will prove

| Claim | `source_kind` | Notes |
|-------|---------------|-------|
| SQLite ingest + idempotent keys | `collectable_v1` | From `verify-demo.sh` |
| Action graph + proof packet export | `collectable_v1` | Projection JSON on disk |
| Canvas render | `derived_v1` | UI reads projections only |
| Demo scenario nodes | `simulated_v1` | Where fixtures stand in for live agent |

This path matches the **fixture canvas** row in [One pager § Evaluator paths](../../ONE_PAGER.md).

## Prerequisites

```bash
cd /path/to/nativelink-agent-flight-recorder
uv sync   # or pip install -e . per CONTRIBUTING
```

## Step 1 — Run the fixture proof script

```bash
./scripts/verify-demo.sh
```

The script runs `uv run pytest`, `nlfr doctor --mode cache-only`, optional real-tool
smoke, `nlfr simulate` for demo scenarios, ingest, and exports under
`data/demo-proof/projections/`.

If Bazel or NativeLink are missing, the script records honest blockers — it does
not fake success.

## Step 2 — Export projections manually (optional)

```bash
PYTHONPATH=src uv run python -m nlfr graph export \
  --db data/demo-proof/nlfr.sqlite \
  --run-group latest \
  --output /tmp/graph-projection.json

PYTHONPATH=src uv run python -m nlfr proof export \
  --db data/demo-proof/nlfr.sqlite \
  --run-group latest \
  --output /tmp/proof-packet.json
```

Every node and claim in those files carries four [truth labels](../reference/truth-labels.md).

## Step 3 — Open the canvas

```bash
npm --prefix apps/canvas install
npm --prefix apps/canvas run dev
```

Load projections from `data/demo-proof/projections/` per canvas README. Switch modes
per [design routing](../../design/routing.md): Action Graph, Proof Packet, Remote
Boundary. The canvas does not call a live scheduler — see
[Projection-only canvas](../explanation/projection-only-canvas.md).

## Step 4 — Read the proof packet

Open `proof-packet.json` (or the Proof Packet mode). Confirm:

- `cache_economics` or cache blocks show `source_kind` and `confidence`
- No raw prompts, env vars, or private logs
- Worker placement / queue time are **not** claimed unless M7 stdout evidence exists

Boundaries: [One pager § What is explicitly unproven](../../ONE_PAGER.md).

## Local gates (GHA offline)

CI may be non-green. This tutorial succeeds on `verify-demo.sh` + local pytest only.
Do not wait for GitHub Actions.

```bash
uv run pytest -q
```

Policy: [GHA offline proof shift](../../sessions/handoffs/frontier-wave/wave-1/gha-offline-proof-shift.md).

## Next steps

| Goal | Page |
|------|------|
| Real cold/warm proof in Nix | [First Nix proof](first-nix-proof.md) |
| Compare two run groups (M9) | [Export and compare run groups](../how-to/export-and-compare-run-groups.md) |
| Record a Cursor agent edit (M8) | [Cursor adapter](../../../adapters/cursor/README.md) |
| Full milestone map | [Architecture track](../../ARCHITECTURE_TRACK.md) |
