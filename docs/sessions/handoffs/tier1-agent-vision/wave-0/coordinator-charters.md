# Coordinator charters — Tier 1 Agent Vision

Each coordinator owns one sub-DAG. Phases: **R → D → I → V → R → I**.

**KOS arming (mandatory):** [`../KOS-startup-routing.md`](../KOS-startup-routing.md) · [`kos-arming.md`](kos-arming.md)

Return `DispatchManifest` JSON per broker contract. Write `integration-brief.md` at reflect gates. **Coordinators must not spawn subagents.**

---

## coord-t1-spine

**DAG:** T1-SPINE · **Track A**  
**Deliverables:** `tier1-agent-demo.sh`, `compare-agent-runs.sh`, `demo/scenarios/tier1/`, `tests/test_tier1_agent_demo.py`  
**Proof:** `uv run pytest tests/test_tier1_agent_demo.py -q && ./scripts/tier1-agent-demo.sh --dry-run`

---

## coord-t1-bugfix

**DAG:** T1-BUGFIX · **Blocked by:** T1-SPINE wave 2  
**Deliverables:** bugfix fixture, `agent-bugfix-1` record, `docs/proof-samples/agent-bugfix-summary.json`

---

## coord-t1-feature

**DAG:** T1-FEATURE · **Blocked by:** T1-SPINE wave 2  
**Deliverables:** `compare_cmd --format`, `agent-feature-compare` record, tests

---

## coord-t1-integrate

**DAG:** T1-INTEGRATE · **Blocked by:** T1-BUGFIX + T1-FEATURE  
**Deliverables:** DEMO_SCRIPT Tier 1, capture script, compare narrative

---

## coord-t3-research

**DAG:** T3-R · **Track B** · **Parallel with T1-SPINE wave 1**  
**Deliverables:** `provenance-t3-*.md`, `integration-brief-t3-design-inputs.md` (readonly explore workers)

---

## coord-t3-design

**DAG:** T3-D · **Blocked by:** T3-R  
**Deliverables:** `docs/design/view-spec.v1.schema.json`, component-catalog, routing, composer protocol

---

## coord-t3-implement

**DAG:** T3-I1–I4 · **Blocked by:** T3-D  
**Deliverables:** GridShell, panels, persist, view composer MVP

---

## coord-t3-dogfood

**DAG:** T3-INTEGRATE · **Blocked by:** T3-implement + T1-integrate  
**Deliverables:** record-agent-change + record-canvas-build + 3-way compare doc
