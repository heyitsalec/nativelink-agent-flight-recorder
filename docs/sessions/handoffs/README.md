# Session handoffs

Broker-coordinated subagents write **rich artifacts here**; parent chat carries
only JSON summaries and paths. See
[knowledge-os broker dispatch manifest](/Users/alecbot/Documents/knowledge-os/agent-os/harness/broker-dispatch-manifest.md)
for the full contract.

## Directory layout

```text
docs/sessions/handoffs/{dag-id}/wave-{n}/
  task-packet-{worker-id}.md
  provenance-{worker-id}.md
  worker-results.json
  integration-brief.md
  spawn-ledger.md
```

## Active DAGs

| DAG | Linear parent | Waves |
|-----|---------------|-------|
| `m5-m9-umbrella` | PER-1058 | [m5-m9-umbrella/](m5-m9-umbrella/) |
| `nlfr-doc-capture` | PER-1071 | [nlfr-doc-capture/](nlfr-doc-capture/) |
| `future-fleet-claims` | PER-1058 | [future-fleet-claims/wave-1/](future-fleet-claims/wave-1/) · DAG: [future-fleet-claims.md](../../dags/future-fleet-claims.md) |
| `fleet-evidence-v1` | PER-1058 · frontier | [wave-0/](fleet-evidence-v1/wave-0/) · [wave-1/](fleet-evidence-v1/wave-1/) · DAG: [fleet-evidence-v1.md](../../dags/fleet-evidence-v1.md) |
| `tier1-agent-vision` | PER-TIER1-AGENT | [tier1-agent-vision/](tier1-agent-vision/) · KOS: [KOS-startup-routing.md](tier1-agent-vision/KOS-startup-routing.md) |
| `tier1-live-bazel` | frontier | [tier1-live-bazel/](tier1-live-bazel/) |
| `frontier-wave` | broker | [frontier-wave/](frontier-wave/) |

## Templates

- [HANDOFF_TEMPLATE.md](HANDOFF_TEMPLATE.md) — coordinator checklist
- Flat legacy handoffs (`vision-r-wave-*.md`, `git-reconcile-*.md`) predate the tree layout
