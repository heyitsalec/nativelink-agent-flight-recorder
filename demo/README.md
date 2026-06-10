# Demo Workload

This directory contains the small demo workload and simulated patch scenarios.

The files here are fixtures for the NativeLink Agent Flight Recorder MVP. They
do not claim real AI-agent provenance, real NativeLink cache behavior, or exact
worker/action/queue timing. Scenario metadata is explicitly labeled
`simulated_v1`; future recorder runs must attach collectable Bazel and
NativeLink evidence before making runtime proof claims.

## Bazel Workload

`bazel-monorepo/` is intentionally tiny:

- `//tasks:policy` is a shared Python module with priority thresholds.
- `//tasks:priority` is a Python library that classifies task scores.
- `//tasks:priority_test` is a Python test target for the library.

Run from `demo/bazel-monorepo`:

```bash
bazel test //tasks:priority_test
```

If Bazel is not installed, the workload is still useful as a fixture for
scenario parsing, static validation, and later runner/parser workstreams.

### LRE overlay (opt-in, currently blocked)

The committed `bazel-monorepo/MODULE.bazel` template declares no external
dependencies, so the cache-only path analyzes on a fresh clone. Local Remote
Execution experiments use the `bazel-monorepo/MODULE.lre.bazel` overlay
(copied over `MODULE.bazel` in a scratch workspace copy, Nix shell active).
The overlay header documents a known toolchain version blocker — LRE runs
record a truth-labeled `environment_blocker` until the NativeLink pin and
`.bazelversion` advance together.

## Scenario Files

The files under `scenarios/` are simulated-agent patch metadata. Each scenario
includes:

- `simulated_agent.kind: "simulated_v1"`
- a note that the provenance is synthetic
- the Bazel target(s) involved
- a unified diff payload
- truth-labeled proof claims with `source_kind`, `confidence`,
  `evidence_refs`, and `redaction_state`

## Proof Claim Mapping

| Scenario | Patch Shape | Demo Claim It Supports | Evidence Boundary |
| --- | --- | --- | --- |
| `safe-leaf-change.json` | Adds a passing assertion to `tasks/priority_test.py`. | A leaf-only patch can be represented separately from the real Bazel result. | The scenario can label scope as simulated. Passing target status requires collectable Bazel test evidence. |
| `shared-module-change.json` | Changes `tasks/policy.py`, which is imported by the library. | Shared-code patches need broader affected-target reasoning than leaf-only changes. | The scenario can flag shared-module risk. Dependency and pass/fail claims require Bazel query/aquery/test evidence. |
| `nondeterministic-test-change.json` | Adds a test using randomness. | A single observed pass/fail should not be promoted into a stable correctness claim. | The scenario identifies a flaky pattern. Real nondeterminism claims require repeated collected outcomes. |

These scenarios are designed to feed the later recorder flow:

1. Apply or replay a simulated patch.
2. Run the Bazel target.
3. Capture immutable artifacts and hashes.
4. Ingest evidence into SQLite.
5. Export projection/proof JSON where simulated labels and collectable facts
   remain distinct.
