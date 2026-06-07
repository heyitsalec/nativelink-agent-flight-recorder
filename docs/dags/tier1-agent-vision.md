# Tier 1 Agent Vision — broker-coordinated DAG

Linear parent: PER-TIER1-AGENT (proposed)

Broker: [knowledge-os/agent-os/harness/broker-dispatch-manifest.md](/Users/alecbot/Documents/knowledge-os/agent-os/harness/broker-dispatch-manifest.md)

Handoffs: `docs/sessions/handoffs/tier1-agent-vision/`

**KOS arming (all coordinators/workers):** [`sessions/handoffs/tier1-agent-vision/KOS-startup-routing.md`](../sessions/handoffs/tier1-agent-vision/KOS-startup-routing.md) · Cursor adapter: `/Users/alecbot/Documents/knowledge-os/adapters/cursor/`

## North star

**Demo narrative:** "AI wrote it; here's proof it was validated."

| Act | Run group | Show in demo |
|-----|-----------|--------------|
| 1 Bounded bugfix | `agent-bugfix-1` | yes |
| 2 Feature slice | `agent-feature-compare` | yes |
| 3 Meta dogfood | `agent-change` + compare triple | story hook |

**Parallel tracks:** Track A (Scenarios 1+2 demo pack) + Track B (GUI substrate).

## Sub-DAG coordinators (parent spawns; coordinators do not spawn)

| Coordinator | Sub-DAG | Track |
|-------------|---------|-------|
| coord-t1-spine | T1-SPINE | A |
| coord-t1-bugfix | T1-BUGFIX | A |
| coord-t1-feature | T1-FEATURE | A |
| coord-t1-integrate | T1-INTEGRATE | A |
| coord-t3-research | T3-R | B |
| coord-t3-design | T3-D | B |
| coord-t3-implement | T3-I1–I4 | B |
| coord-t3-dogfood | T3-INTEGRATE | B |

## Wave schedule

| Wave | Work | Gate |
|------|------|------|
| 0 | ARM | spawn ledger |
| 1 | T1-SPINE R + T3-R | research provenance on disk |
| 1.5 | Reflect | integration briefs |
| 2 | T1-BUGFIX + T1-FEATURE + T3-D | real recordings + design artifacts |
| 2.5 | Review | proof matrix |
| 3 | T1-INTEGRATE + T3-I1/I2 | demo script + grid/panels |
| 4 | T3-I3/I4 | persisted views + composer |
| 5 | T3 dogfood | 3-way compare |
| 6 | Integrative review | parent proof gates |

## Proof matrix (umbrella)

```bash
uv run pytest -q
./scripts/tier1-agent-demo.sh --dry-run
npm --prefix apps/canvas run test:truth
./scripts/compare-agent-runs.sh
```
