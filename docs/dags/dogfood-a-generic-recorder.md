# DAG A — Generic Command Recorder

Linear parent: [PER-1058](https://linear.app/gradschool/issue/PER-1058)  
Linear issue: PER-1063 (generic command recorder — dogfood spine)

## Objective

Add a first-class `nlfr run --mode generic --command "..."` path that records arbitrary
local commands into the SQLite spine without inventing Bazel cache/target/action layers.

## Coordinator mode

Single coordinator dispatches parallel workers when write scopes do not collide:

| Worker | Scope | Deliverable |
|--------|-------|-------------|
| Backend | `src/nlfr/commands/` | Generic run mode via `ProcessRunner` |
| Tests | `tests/` | Pass/fail/idempotent + graph projection fixtures |
| Proof | `scripts/record-proof.sh` | `collectable_v1` `summary.json` gate |

## Handoff checklist

- [x] Collect gate: invocations + stdout/stderr artifacts + SHA-256
- [x] Normalize gate: idempotent SQLite ingest (runs, invocations, artifacts, failures)
- [x] Project gate: four truth labels on all nodes; empty Bazel layers
- [x] Ship gate: `scripts/record-proof.sh` + `python3 -m pytest`

## Proof commands

```bash
python3 -m pytest tests/test_generic_run.py -q
scripts/record-proof.sh
```

## Blocked by

Nothing — unblocks DAG B dogfood script.

## Related

- DAG B: [dogfood-b-canvas-dogfood.md](dogfood-b-canvas-dogfood.md)
- Spec: [../USEFULNESS_ROADMAP.md](../USEFULNESS_ROADMAP.md)
