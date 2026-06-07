# Tier 1 Agent Vision — broker spawn ledger

**Parent broker session:** complete  
**DAG:** tier1-agent-vision  
**Mode:** broker-coordinated (coordinators return DispatchManifest only)  
**KOS arming:** [`../KOS-startup-routing.md`](../KOS-startup-routing.md) · [`kos-arming.md`](kos-arming.md)  
**Ship:** [`../wave-6/ship-packet.md`](../wave-6/ship-packet.md)

## Wave 0 — ARM

| Agent | Role | Status |
|-------|------|--------|
| parent | broker | DONE |
| coord-t1-spine | coordinator | DONE |
| coord-t3-research | coordinator | DONE |

## Wave 1 — Research

| Agent | Status |
|-------|--------|
| t1-spine-r-adapter-scenario | DONE |
| t1-spine-r-compare-retention | DONE |
| t3-r-harmony | DONE |
| t3-r-canvas-audit | DONE |
| t3-r-view-systems | DONE |

## Wave 2 — Implement (Track A + T3-D)

| Agent | Coordinator | Status |
|-------|-------------|--------|
| t1-spine-orchestrator | coord-t1-spine | DONE |
| t1-spine-tests | coord-t1-spine | DONE |
| t1-bugfix-setup | coord-t1-bugfix | DONE |
| t1-bugfix-fixtures-tests | coord-t1-bugfix | DONE |
| t1-bugfix-record | coord-t1-bugfix | DONE |
| t1-feature-compare-format | coord-t1-feature | DONE |
| t1-feature-record-proof | coord-t1-feature | DONE |
| t3-d-schema-routing | coord-t3-design | DONE |
| t3-d-catalog-composer | coord-t3-design | DONE |

## Wave 3 — T3-I1/I2

| Agent | Status |
|-------|--------|
| t3-i-views | DONE |
| t3-i-shell | DONE |
| t3-i-panels | DONE |

## Wave 4 — Composer

| Agent | Status |
|-------|--------|
| t3-i-composer | DONE |

## Wave 6 — Ship

Parent proof gates: **all green** (81 pytest, tier1 dry-run, compare live, test:truth)

## Rules

- Coordinators **must not** spawn subagents.
- Parent is sole spawn authority and message bus.
- Large artifacts → `docs/sessions/handoffs/tier1-agent-vision/wave-{n}/`
- Chat carries JSON summaries + paths only.
