# Subagent task packet template — Tier 1 Agent Vision

Copy per worker. Parent broker fills `{braces}`.

---

## KOS arming (mandatory)

Read before acting:

- [`KOS-startup-routing.md`](KOS-startup-routing.md)
- [`/Users/alecbot/Documents/knowledge-os/adapters/cursor/composer-dispatch-contract.md`](/Users/alecbot/Documents/knowledge-os/adapters/cursor/composer-dispatch-contract.md)

**Role:** `{coordinator | explore worker | generalPurpose worker | shell worker}`  
**Coordinators:** return `DispatchManifest` JSON; do **not** spawn subagents.

---

## Task

| Field | Value |
|-------|-------|
| worker_id | `{id}` |
| coordinator_id | `{coord-id}` |
| dag_ref | tier1-agent-vision / `{sub-dag}` |
| objective | `{one sentence}` |
| expected_output | `{files}` |
| repo_path | `/Users/alecbot/Documents/nativelink-agent-flight-recorder` |
| write_scope | `{paths}` |
| no_touch | `{paths}` |
| proof_commands | `{commands}` |
| privacy_tier | `private_internal` |
| source_refs | `{list}` |
| stop_conditions | `{list}` |
| return_status | DONE, DONE_WITH_CONCERNS, NEEDS_CONTEXT, BLOCKED |

---

## NLFR constraints

- Evidence-first; canvas renders projection JSON only
- Truth labels on every projected claim
- Agent adapter: `model` + `prompt_sha256` only — never raw prompt
- `data/` is gitignored; commit proof-samples JSON for evaluators

---

## Provenance (write on completion)

`docs/sessions/handoffs/tier1-agent-vision/wave-{n}/provenance-{worker-id}.md`

Return chat JSON envelope only (see KOS-startup-routing.md §3).
