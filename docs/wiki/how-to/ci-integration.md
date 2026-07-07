# How-to: drop NLFR into CI with the redact-gate baked in

**Quadrant:** How-to · **Audience:** engineers wiring NLFR into GitHub Actions,
Buildkite, or Jenkins
**Track:** packaged CI primitive — `nlfr record` + `nlfr redact` as one drop-in

← [Wiki hub](../README.md) · [Record your own build](record-your-own-build.md) ·
[Attach proof to a PR](attach-proof-to-pr.md) · [CI recipe](../../CI_RECIPE.md)

Record a Bazel build's evidence in CI and publish it as a build artifact —
**without ever hand-copying a redact step that a future edit can drop.** Each
primitive below wraps `nlfr record` and runs the `nlfr redact` gate *before* any
upload, as one versioned unit.

## The guarantee

> **The packaged steps never upload evidence that has not passed the redact
> gate.**

Concretely, every primitive here runs the same sequence — the [shared core
script](#one-shared-core-no-drift) all three reuse:

1. `nlfr record -- <your bazel command>` — capture BEP + stdout/stderr evidence,
   mirroring Bazel's own exit code (a red build stays red; an environment
   blocker surfaces its honest non-Bazel exit).
2. **Redact gate on the evidence directory, before any upload:**
   - **strict** (default): `nlfr redact --check <dir>` — any finding **fails the
     step and nothing is uploaded**.
   - **non-strict**: `nlfr redact <dir> <mirror>` — scrub to a redacted mirror
     and upload **only the mirror**, never the raw tree.
3. Upload the gate-blessed path only (the raw tree solely when `--check` passed;
   otherwise the scrubbed mirror).
4. Re-apply the recorded build's exit code, so the gate never turns a red build
   green.

This closes the exact leak class NLFR exists to prevent: a copy-pasted CI job
that drops the redact step and uploads a raw evidence tree carrying a secret or
absolute path.

Runtime stays **stdlib-only**: every primitive shells out to `uvx` and adds no
Python dependency to your repo.

## GitHub Actions

Reference the composite Action by tag — no YAML to hand-copy:

```yaml
# .github/workflows/nlfr-proof.yml
name: NLFR proof
on: [push]
jobs:
  proof:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: heyitsalec/nativelink-agent-flight-recorder@v0
        with:
          command: bazel test //...
          # strict-redact: true is the default — the step fails on any finding.
          # upload-artifact: true is the default — uploads the gated evidence.
```

Non-strict (scrub and upload a redacted mirror instead of failing):

```yaml
      - uses: heyitsalec/nativelink-agent-flight-recorder@v0
        with:
          command: bazel test //...
          strict-redact: false
```

### Inputs

| Input | Default | Meaning |
|-------|---------|---------|
| `command` | *(required)* | The bazel command to wrap, e.g. `bazel test //...`. |
| `run-group` | `${{ github.run_id }}` | Run-group label for the evidence. |
| `output-dir` | `data/nlfr-record` | Where SQLite / artifacts / projections land. |
| `upload-artifact` | `true` | Upload the gated evidence as a build artifact. |
| `artifact-name` | `nlfr-proof` | Name of the uploaded artifact. |
| `nlfr-version` | `""` (latest) | Pin the PyPI version of `nlfr`. |
| `strict-redact` | `true` | `true`: fail on findings before upload. `false`: scrub to a mirror and upload only the mirror. |

### Outputs

| Output | Meaning |
|--------|---------|
| `evidence-dir` | Directory of recorded evidence. |
| `proof-path` | Proof-packet projection, if produced. |
| `redact-status` | `clean` \| `scrubbed` \| `blocked` \| `empty`. |

## Buildkite

Reference the plugin (vendored under `.buildkite/plugin`, or from your own
plugin registry):

```yaml
# pipeline.yml
steps:
  - label: ":shield: nlfr proof"
    plugins:
      - nlfr-redact-gate#v0:
          command: "bazel test //..."
          # strict-redact: true      # default — fail on findings before upload
          # upload-artifact: true     # default — buildkite-agent artifact upload
```

The command hook runs the identical record → redact-gate → upload sequence and
uploads only the gate-blessed path with `buildkite-agent artifact upload`.

## Jenkins

No plugin binary — a declarative-pipeline stage runs the same `uvx` + redact-gate
sequence. Strict mode: the scan fails the stage before any `archiveArtifacts`.

```groovy
pipeline {
  agent any
  stages {
    stage('nlfr proof') {
      steps {
        sh '''
          set -euo pipefail
          # 1. Record (mirrors Bazel's exit; a red build stays red).
          uvx --from nativelink-agent-flight-recorder nlfr record \
            --run-group "${BUILD_TAG}" --output-dir data/nlfr-record \
            -- bazel test //... || RECORD_EXIT=$?

          # 2. Redact gate BEFORE any archive — strict: fail on any finding.
          uvx --from nativelink-agent-flight-recorder nlfr redact \
            --check data/nlfr-record

          # (non-strict alternative: scrub to a mirror and archive only it)
          #   uvx --from nativelink-agent-flight-recorder nlfr redact \
          #     data/nlfr-record data/nlfr-record-redacted
          #   -> then archiveArtifacts 'data/nlfr-record-redacted/**'

          exit ${RECORD_EXIT:-0}   # surface the recorded build result
        '''
        // 3. Archive only after the gate passed.
        archiveArtifacts artifacts: 'data/nlfr-record/**', fingerprint: true
      }
    }
  }
}
```

In strict mode the `nlfr redact --check` line exits non-zero on a finding, which
fails the `sh` step, so `archiveArtifacts` never runs on unredacted evidence. For
non-strict, scrub to a mirror and archive only `data/nlfr-record-redacted/**`.

## One shared core, no drift

All three primitives delegate the safety-critical sequence to a single script,
[`.buildkite/plugin/lib/nlfr-ci-gate.sh`](../../../.buildkite/plugin/lib/nlfr-ci-gate.sh),
so the redact-before-upload guarantee cannot drift between CI systems. Its
behavior is covered by [`tests/test_ci_gate_script.py`](../../../tests/test_ci_gate_script.py)
(strict blocks on a planted finding; non-strict scrubs and blesses only the
mirror; a clean tree passes; a red build stays red) and the raw-tree-upload
invariant by [`tests/test_ci_primitive_yaml.py`](../../../tests/test_ci_primitive_yaml.py).

## Honest boundary

The redact gate is **defense-in-depth pattern matching, not a guarantee.** It
detects the [redaction registry's pattern classes](../reference/cli.md#redact) —
secret/credential shapes, absolute paths, and (by default) email + IPv4 PII — not
every conceivable secret. Two honest limits worth stating in a procurement
review:

- **`--check` skips binaries and SQLite databases**, reporting them honestly
  (`skipped:binary`, `skipped:database`) rather than scanning them. A secret
  embedded in a binary blob is out of scope. In **strict-clean** mode the raw
  tree — including the SQLite spine and any binary artifacts — is uploaded once
  the *scannable* text/JSON passes; if you do not want those uploaded, use
  **non-strict**, whose redacted mirror contains only the scrubbed text/JSON.
- **Review sensitive evidence at the source too.** The gate is the last line of
  defense before upload, not a substitute for not recording secrets in the first
  place.

See the [redact CLI reference](../reference/cli.md#redact) for the full detector
list, scope, and limits, and the [security policy](../../../SECURITY.md) for the
overall posture.

## Related

- [Record your own Bazel build](record-your-own-build.md) — the underlying `nlfr record`
- [Attach proof to a PR](attach-proof-to-pr.md) — turn projections into PR markdown
- [CI recipe](../../CI_RECIPE.md) — NLFR's own proof jobs and local substitutes
- [redact CLI reference](../reference/cli.md#redact) — detectors, scope, limits
