# feat: LRE substrate proof + fleet claims research (unlock wave)

## Summary

- **LRE substrate (`lre_substrate_ready`):** Adds `demo/nativelink/lre.json5`, `scripts/lre-proof.sh`, fixture-backed `tests/test_lre_proof.py`, proof samples, and CI `lre-proof-probe` in `.github/workflows/nlfr-proof.yml` — probes LRE ports and writes `data/lre-proof/summary.json` or an honest `environment-blocker.json`.
- **Fleet claims research (`derived_v1`):** Adds `scripts/fleet_claims_audit.py`, `scripts/fleet-claims-audit.sh`, `tests/test_fleet_claims_audit.py`, `docs/proof-samples/fleet-claims-matrix-sample.json`, and ONE_PAGER explicitly-unproven footnote synced to `data/fleet-claims-audit/claim-matrix.json`.
- **Broker handoffs:** Closes `lre-proof` wave-2 and `future-fleet-claims` wave-1 with spawn ledgers, task packets, worker-results, integration briefs, and DAG mirrors (`docs/dags/lre-proof.md`, `docs/dags/future-fleet-claims.md`).
- **LRE Nix toolchain (wave-3, `lre_bazelrc_generated`):** Migrates `flake.nix` to TraceMachina LRE flake module; wires `demo/bazel-monorepo/MODULE.bazel` + `.bazelrc`; adds `scripts/lre-nix-toolchain-proof.sh` and CI job `lre-nix-ci` on `ubuntu-latest`.
- **Ladder truth sync:** `docs/dags/future-execution-ladder.md` reflects shipped substrate, ci-bazel-tier1, and fleet wave-1.

## Honesty boundaries (not in this PR)

- **LRE:** Substrate + generated `lre.bazelrc` on Linux — **not** hermetic local↔remote cache hit parity, aarch64-darwin `--config=lre`, or fleet dashboards.
- **Fleet:** Research claim matrix + ONE_PAGER footnote — **no** scheduler/fleet canvas UI, queue-time correlation, or action-placement claims without new collectable parsers.

## Test plan

- [ ] `uv run pytest -q` — full suite green (95 passed, 1 skipped at ship gate)
- [ ] `uv run pytest tests/test_lre_proof.py -q` — 7 LRE proof contract tests
- [ ] `bash -n scripts/lre-nix-toolchain-proof.sh`
- [ ] CI `lre-nix-ci` job uploads `data/lre-nix-toolchain-proof/summary.json` or blocker
- [ ] `uv run pytest tests/test_fleet_claims_audit.py -q` — 4 fleet claims audit tests
- [ ] `bash -n scripts/lre-proof.sh` — shell syntax check
- [ ] `./scripts/fleet-claims-audit.sh` — writes `data/fleet-claims-audit/claim-matrix.json` with `source_kind: derived_v1`
- [ ] `grep lre_substrate_ready docs/dags/lre-proof.md` — DAG ceiling matches substrate-ready claim
- [ ] `grep research_only docs/dags/future-fleet-claims.md` — fleet DAG stays research-only
- [ ] CI `lre-proof-probe` job uploads `summary.json` or `environment-blocker.json` (Nix toolchain on runner; local Nix green path optional)
- [ ] Confirm PR description does **not** claim hermetic Nix LRE or fleet dashboard UI
