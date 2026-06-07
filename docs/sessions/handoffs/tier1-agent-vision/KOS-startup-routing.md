# Knowledge OS startup routing — Tier 1 Agent Vision DAG

**Mandatory read** for every coordinator and worker spawned in this DAG.  
**Adapter home:** `/Users/alecbot/Documents/knowledge-os/adapters/cursor/`

---

## 1. Universal first reads (startup router)

Per [`agent-os/session-start/startup-router.md`](/Users/alecbot/Documents/knowledge-os/agent-os/session-start/startup-router.md):

| Order | Doc | Why |
|-------|-----|-----|
| 1 | NLFR [`AGENTS.md`](../../../../AGENTS.md) | Evidence-first product rules |
| 2 | KOS [`projects/nlfr/pack.md`](/Users/alecbot/Documents/knowledge-os/projects/nlfr/pack.md) | NLFR proof commands, stop conditions, broker mode |
| 3 | This DAG [`docs/dags/tier1-agent-vision.md`](../../../dags/tier1-agent-vision.md) | North star + wave schedule |
| 4 | [`broker-dispatch-manifest.md`](/Users/alecbot/Documents/knowledge-os/agent-os/harness/broker-dispatch-manifest.md) | Broker loop + DispatchManifest schema |

**Privacy:** `private_internal` — no raw prompts, credentials, or customer data in handoffs.

---

## 2. Cursor adapter — role mapping

Per [`adapters/cursor/README.md`](/Users/alecbot/Documents/knowledge-os/adapters/cursor/README.md) and [`composer-dispatch-contract.md`](/Users/alecbot/Documents/knowledge-os/adapters/cursor/composer-dispatch-contract.md):

| Role | Who | May spawn? | Writes? |
|------|-----|------------|---------|
| **Broker** | Parent Composer session | Yes — sole spawn authority | Integrate/rescue only |
| **DAG coordinator** | `generalPurpose` subagent | **No** — returns `DispatchManifest` | Integrate scope only |
| **Worker** | `explore` / `generalPurpose` / `shell` | No | Packet `write_scope` only |
| **Reviewer** | `explore` readonly | No | No |

### Coordinator modes

| Mode | Coordinator returns | Parent action |
|------|---------------------|---------------|
| `dispatch-workers` | `DispatchManifest` with `workers[]` | Spawn workers; collect provenance |
| `coordinator-only` | Plan / blocker | Resume with operator answer |
| `review-gate` | Review request | Spawn readonly reviewer |
| `completion-ritual` | Done pending ship | Parent runs proof gates |
| `blocked` | Blocker | Stop wave; ask operator |

**Coordinators must not call Task tool to spawn subagents.**

---

## 3. Broker loop (this DAG)

```text
ARM → coordinators return DispatchManifest
SPAWN → parent spawns workers (disjoint write_scope)
COLLECT → worker JSON + provenance on disk
RESUME → parent passes worker-results.json to coordinator
REPEAT → R → D → I → V → R → I per sub-DAG
SHIP → parent proof gates; no inline DAG work while broker active
```

### Handoff tree (NLFR)

```text
docs/sessions/handoffs/tier1-agent-vision/wave-{n}/
  task-packet-{worker-id}.md
  provenance-{worker-id}.md
  worker-results.json
  integration-brief.md
  spawn-ledger.md
```

Chat carries **paths + short JSON only**. Large diffs/logs stay on disk.

### Worker return envelope (chat)

```json
{
  "worker_id": "t1-bugfix-setup",
  "status": "DONE",
  "handoff_dir": "docs/sessions/handoffs/tier1-agent-vision/wave-2/",
  "artifacts": { "provenance": "provenance-t1-bugfix-setup.md" },
  "claims_touched": [],
  "blockers": []
}
```

---

## 4. NLFR north star (do not drift)

**Story:** "AI wrote it; here's proof it was validated."

| Act | Run group | Demo |
|-----|-----------|------|
| 1 Bugfix | `agent-bugfix-1` | yes |
| 2 Feature | `agent-feature-compare` | yes |
| 3 Meta dogfood | `agent-change` + compare triple | story hook |

**Truth labels:** every claim needs `source_kind`, `confidence`, `evidence_refs`, `redaction_state`.

**Kind split (critical):**

| Path | Agent kind | source_kind |
|------|------------|-------------|
| `nlfr simulate` / llm-bounded-patch | `bounded_llm_v1` | `simulated_v1` |
| `record-agent-change.sh` | `cursor_adapter_v1` | `collectable_v1` |

---

## 5. Startup output contract (every agent states before acting)

1. **Objective** and sub-DAG id (e.g. T1-BUGFIX)
2. **Lane:** Agent OS / build-acceleration
3. **Project pack:** `projects/nlfr/pack.md`
4. **Privacy tier:** `private_internal`
5. **Write scope** + **no_touch**
6. **Proof commands**
7. **Source refs** (paths, not bodies)
8. **Stop conditions**

---

## 6. NLFR proof gates (parent runs at ship)

```bash
cd /Users/alecbot/Documents/nativelink-agent-flight-recorder
uv run pytest -q
./scripts/tier1-agent-demo.sh --dry-run
npm --prefix apps/canvas run test:truth
./scripts/compare-agent-runs.sh --dry-run
```

Canvas changes: also `npm --prefix apps/canvas run build`.

---

## 7. Coordinator roster + current wave

| Coordinator | Sub-DAG | Wave status |
|-------------|---------|-------------|
| coord-t1-spine | T1-SPINE | Wave 2 implement dispatched |
| coord-t1-bugfix | T1-BUGFIX | Manifest ready — workers pending |
| coord-t1-feature | T1-FEATURE | Manifest ready — workers pending |
| coord-t1-integrate | T1-INTEGRATE | Blocked on bugfix + feature |
| coord-t3-research | T3-R | Wave 1 DONE |
| coord-t3-design | T3-D | Wave 2 DONE |
| coord-t3-implement | T3-I1–I4 | Wave 3 manifest ready |
| coord-t3-dogfood | T3-INTEGRATE | Blocked on implement + integrate |

**Resume frontier:** spawn T1-BUGFIX + T1-FEATURE workers (parallel), then T3-I views + shell.

---

## 8. Context budget rule

Load this file + task packet + integration brief. Read source **files on disk** for implementation; do not paste full `App.tsx` into coordinator chat.
