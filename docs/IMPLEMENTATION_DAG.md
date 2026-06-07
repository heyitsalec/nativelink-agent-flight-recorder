# Implementation DAG

> **Historical planning artifact.** This DAG records the original MVP workstream
> sequencing (PER-998). For current milestones, execution-ladder boundaries, and
> M5–M9 status, use **[ARCHITECTURE_TRACK.md](ARCHITECTURE_TRACK.md)** and
> **[USEFULNESS_ROADMAP.md](USEFULNESS_ROADMAP.md)**.

Source planning issue: [PER-998](https://linear.app/gradschool/issue/PER-998/nlfr-0-implement-nativelink-agent-flight-recorder-mvp)

## Parent Objective

Implement the NativeLink Agent Flight Recorder MVP as a separate local repo.

## Child Workstreams

1. **Data Spine**: Done. Package scaffold, artifact manifest, SQLite schema, IDs,
   DB tests.
2. **CLI Shell**: Done. Command registry, `init`, `doctor`, help text, CLI tests.
3. **Demo Workload**: Done. Small Bazel repo and patch scenarios.
4. **NativeLink/Bazel Runners**: Done. Subprocess runner, cache-only NativeLink
   config, cold/warm run wrapper.
5. **Evidence Parsers**: Done. BEP/profile/execution-log fixture ingestion.
6. **Projection And Proof**: Done. Graph/runway/proof contracts and exporters.
7. **Canvas Consumer**: Done. Sparse TypeScript canvas from projection JSON.
8. **End-To-End Proof**: Done. Demo script, Playwright screenshot/WebM, README proof path.

## Final Proof

```bash
uv run pytest tests -q
npm --prefix apps/canvas run build
scripts/verify-demo.sh
```

Latest verification:

- `uv run pytest tests -q` -> `41 passed`.
- `npm --prefix apps/canvas run build` -> passed.
- `scripts/verify-demo.sh` -> passed with explicit Bazel/NativeLink environment
  blockers on this host.

## Follow-On Environment Slice

Added after MVP completion:

- `flake.nix`
- `.envrc`
- `.devcontainer/devcontainer.json`
- `scripts/cold-warm-cache-proof.sh`
- `docs/DEV_ENVIRONMENT.md`

This slice wires the real cold/warm NativeLink proof path. It is expected to run
inside `nix develop` or the devcontainer because this host does not currently
have Nix/Bazel/NativeLink installed.

## Sequencing

Start in parallel:

- Data Spine
- CLI Shell
- Demo Workload

Then:

- Runners depend on CLI Shell and Demo Workload.
- Parsers depend on Data Spine and fixtures from Demo Workload/Runners.
- Projection/Proof depends on Data Spine and Parsers.
- Canvas depends on Projection JSON contract.
- E2E Proof depends on the whole flow.

## Stop Conditions

- Cache-only NativeLink proof cannot run and no fixture-backed fallback is
  documented.
- Artifact manifest cannot enforce no-overwrite/idempotent ingest.
- Projection JSON lacks source/confidence/evidence labels.
- Implementation drifts into SaaS/dashboard scope.

## Related docs

- [ARCHITECTURE_TRACK.md](ARCHITECTURE_TRACK.md) — current phase map and M1–M9 ladder
- [USEFULNESS_ROADMAP.md](USEFULNESS_ROADMAP.md) — product usefulness gaps and next work
- [CONTRIBUTING.md](CONTRIBUTING.md) — proof scripts and contributor gates
