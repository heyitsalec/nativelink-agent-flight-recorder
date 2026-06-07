# Wave 2 Integration Brief — M7 + M8

**From:** Wave 1.5 review (2026-06-06)  
**For:** Coordinators M7 (worker parser) and M8 (agent adapter) — parallel after this brief

## Wave 1 carryover (close in parallel, non-blocking)

- Reconcile M5 status mirrors (dags/README, USEFULNESS_ROADMAP, spawn-ledger)
- Extend `.github/workflows/nlfr-proof.yml` unit job: `record-canvas-build.sh`, `test:truth`
- Promote redacted CI summaries to `docs/proof-samples/` after first green GHA run

## M7 — Worker evidence parser

**Claim to promote:** `worker_identity` (first of `UNSUPPORTED_CLAIMS` with direct log evidence)

**Evidence surface:** NativeLink worker/admin **stdout** during local-exec proof — parse worker registration lines into a new ingest kind `worker_admin_stdout_v1` → SQLite `worker_identity_events` (or extend existing boundary table with direct rows).

**Rules:**

- Graph/proof projectors add nodes **only** when SQLite has direct parsed rows
- Truth label: `collectable_v1`, confidence `high` when log line matches fixture pattern
- Keep other four UNSUPPORTED claims explicit in proof packet
- Proof script: `scripts/worker-evidence-proof.sh` wrapping local-exec or dedicated fixture replay
- Tests: redacted log fixtures under `tests/fixtures/worker-admin/`

**Out of scope:** queue time, scheduler assignment, action placement correlation without direct evidence

## M8 — Real agent adapter

**Contract:** Mirror `demo/scenarios/llm-bounded-patch.json` — export `model` + `prompt_sha256` only; never raw prompt.

**Deliverable path:** `scripts/record-agent-change.sh` (thin) + `adapters/cursor/README.md`

**Flow:**

1. Accept bounded change descriptor (file path + optional model label)
2. Record via `nlfr run --mode generic` with `--change-path` and provenance sidecar JSON
3. One real NLFR-repo edit session recorded end-to-end
4. `summary.json` with mixed labels honest (agent provenance may be `collectable_v1` from adapter metadata; validation leg from Bazel if run)

**Parallel with M7:** no shared file conflicts if M7 touches `src/nlfr/ingest/` and M8 touches `scripts/` + `adapters/`.

## M9 preview (Wave 3 — do not start until 2.5)

- Implement `compare_cmd.py` against exported proof JSON
- Run-group retention policy in SQLite layer
- Canvas compare lens reading compare projection only

## Proof matrix for Wave 2 completion

```bash
uv run pytest -q
./scripts/worker-evidence-proof.sh   # M7
./scripts/record-agent-change.sh --dry-run  # M8 smoke; real run without --dry-run
```
