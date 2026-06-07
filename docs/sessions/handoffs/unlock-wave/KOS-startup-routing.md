# Knowledge OS startup routing — Unlock wave (LRE + fleet claims)

**Mandatory read** for every coordinator and worker in this broker wave.

---

## 1. Universal first reads

| Order | Doc | Why |
|-------|-----|-----|
| 1 | NLFR [`AGENTS.md`](../../../../AGENTS.md) | Evidence-first product rules |
| 2 | KOS [`projects/nlfr/pack.md`](/Users/alecbot/Documents/knowledge-os/projects/nlfr/pack.md) | Proof commands, broker mode |
| 3 | [`future-execution-ladder.md`](../../../dags/future-execution-ladder.md) | Unlock priority + honesty policy |
| 4 | KOS [`broker-dispatch-manifest.md`](/Users/alecbot/Documents/knowledge-os/agent-os/harness/broker-dispatch-manifest.md) | DispatchManifest schema |

**Privacy:** `private_internal`

---

## 2. Role mapping (broker mode)

| Role | Who | May spawn? | Writes? |
|------|-----|------------|---------|
| **Broker** | Parent Composer | Yes — sole spawn authority | ARM + integrate/rescue only |
| **DAG coordinator** | `generalPurpose` subagent | **No** | Integration brief only |
| **Worker** | `generalPurpose` / `shell` | No | Packet `write_scope` only |

**Coordinators must not call Task tool.**

---

## 3. Active sub-DAGs (wave-1 continuation)

| Coordinator | DAG mirror | Wave | Objective |
|-------------|------------|------|-----------|
| `coord-unlock-ship` | unlock-wave | wave-1 | Ship PR: integration close, stale doc sync, ship packet |
| `coord-lre-nix-phase3` | `docs/dags/lre-proof.md` | wave-3 | Nix LRE toolchain research → implement or blocker |
| `coord-ladder-docs-sync` | `future-execution-ladder.md` | wave-1 | Ladder + DAG README truth sync |

**Branch:** `feat/lre-fleet-unlocks`

## 4. Completed sub-DAGs (wave-0)

| DAG | Wave | Ceiling |
|-----|------|---------|
| `lre-proof` | wave-2 | `lre_substrate_ready` |
| `future-fleet-claims` | wave-1 | research-only `derived_v1` |

---

## 4. Truth labels (unchanged)

Every claim: `source_kind`, `confidence`, `evidence_refs`, `redaction_state`.

LRE phase 1 = `lre_substrate_ready` (`collectable_v1`, `medium`) — **not** full Nix LRE toolchain.

Fleet audit = `derived_v1` research matrix — **no** fleet UI workers.

---

## 5. Parent proof gates (ship)

```bash
cd /Users/alecbot/Documents/nativelink-agent-flight-recorder
uv run pytest -q
./scripts/fleet-claims-audit.sh
```

Nix (when available):

```bash
nix develop --command ./scripts/lre-proof.sh
```
