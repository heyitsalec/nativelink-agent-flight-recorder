# Adoption guide (M5)

For evaluators who are not on the author's Mac.

## 5-minute path (no Nix, no NativeLink)

```bash
git clone https://github.com/heyitsalec/nativelink-agent-flight-recorder.git
cd nativelink-agent-flight-recorder
pip install uv
uv sync
uv run pytest -q
./scripts/verify-demo.sh
npm --prefix apps/canvas ci && npm --prefix apps/canvas run build
npm --prefix apps/canvas run preview   # http://127.0.0.1:5174/
```

What you get:

- Fixture-backed `simulated_v1` canvas projections via `verify-demo.sh`
- Truth labels on every node; fixture fallback banner if projection fetch fails

What you do **not** get:

- Live NativeLink cache proof
- `collectable_v1` Bazel validation chain

## 30-minute path (Nix, real toolchain)

Requires Nix with flakes enabled (~82GB disk for first Bazel fetch).

```bash
nix develop
uv sync
./scripts/cold-warm-cache-proof.sh
./scripts/agent-loop-proof.sh
npm --prefix apps/canvas run capture
```

Evidence locations:

- `data/cold-warm-proof/summary.json`
- `data/agent-loop-proof/summary.json`

See [`DEV_ENVIRONMENT.md`](DEV_ENVIRONMENT.md) and [`TRYOUT_PACKET.md`](TRYOUT_PACKET.md).

## Skeptic path (CI artifacts)

1. Open latest GitHub Actions run for workflow `NLFR proof`.
2. Download artifact `linux-nix-toolchain-proof`.
3. Verify `summary.json` files have `source_kind: collectable_v1`.
4. Compare redacted samples in [`proof-samples/`](proof-samples/) with your download (paths redacted).

If toolchain job failed with `environment_blocker.json`, the honest claim is "CI recorded a blocker" — not "proof passed on Linux."

## Default canvas projection

Committed under `apps/canvas/public/projections/` is a redacted **`canvas-dev`** generic-run projection (`collectable_v1`). It records NLFR building its own GUI — not the Bazel demo fixtures.

Regenerate locally:

```bash
./scripts/record-canvas-build.sh
```

## What remains unsupported

Until M7–M9 land:

- Worker identity, queue time, action placement, scheduler assignment
- Multi-run compare (`nlfr compare` is a shell)
- Real external agent adapter (M8)

See [`USEFULNESS_ROADMAP.md`](USEFULNESS_ROADMAP.md).

## Questions the MVP answers today

| Question | Answer source |
|----------|---------------|
| What ran? | `nlfr run` + SQLite + projections |
| Did it pass? | `summary.json` status |
| Cache behavior? | cold/warm proof (Nix) |
| What changed? | `changes` table / generic `--change-path` |
| Agent provenance? | agent-loop proof (deterministic patch; M8 adds real adapter) |
| Real vs simulated? | truth labels on every node |

## Next milestones (umbrella)

M5 CI → M6 polish → **Wave 1.5 review** → M7 parser → M8 adapter → **Wave 2.5 review** → M9 compare → Wave 4 handoff.

Mirror: [`dags/m5-m9-umbrella.md`](dags/m5-m9-umbrella.md)
