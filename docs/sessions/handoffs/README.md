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

## Templates

- [HANDOFF_TEMPLATE.md](HANDOFF_TEMPLATE.md) — coordinator checklist
- Flat legacy handoffs (`vision-r-wave-*.md`, `git-reconcile-*.md`) predate the tree layout
