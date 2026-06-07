# Wave 0 — Knowledge OS arming complete

**Date:** 2026-06-06  
**Status:** DONE

## Armed surfaces

All coordinators and workers for `tier1-agent-vision` must read:

1. [`../KOS-startup-routing.md`](../KOS-startup-routing.md) (this DAG packet)
2. [`/Users/alecbot/Documents/knowledge-os/adapters/cursor/README.md`](/Users/alecbot/Documents/knowledge-os/adapters/cursor/README.md)
3. [`/Users/alecbot/Documents/knowledge-os/agent-os/session-start/startup-router.md`](/Users/alecbot/Documents/knowledge-os/agent-os/session-start/startup-router.md)
4. [`/Users/alecbot/Documents/knowledge-os/projects/nlfr/pack.md`](/Users/alecbot/Documents/knowledge-os/projects/nlfr/pack.md)

## Broker contract

- Parent = sole spawn authority
- Coordinators return `DispatchManifest` only
- Workers write provenance under `docs/sessions/handoffs/tier1-agent-vision/wave-{n}/`
- Return vocabulary: `DONE` | `DONE_WITH_CONCERNS` | `NEEDS_CONTEXT` | `BLOCKED`

## Inject into every Task prompt

```markdown
## KOS arming (mandatory)
Read before acting:
- docs/sessions/handoffs/tier1-agent-vision/KOS-startup-routing.md
- Your task packet in docs/sessions/handoffs/tier1-agent-vision/wave-{n}/

You are a {coordinator|worker}. Coordinators must NOT spawn subagents.
Repo: /Users/alecbot/Documents/nativelink-agent-flight-recorder
Privacy: private_internal — no raw prompts in exports.
```

## Next broker action

Spawn Wave 2 implement workers with KOS block above prepended to each packet.
