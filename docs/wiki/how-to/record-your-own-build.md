# How-to: record your own Bazel build

**Quadrant:** How-to · **Audience:** engineers in their own Bazel repo
**Track:** `nlfr record` — one-command evidence capture

Capture immutable, truth-labeled evidence from **your own** `bazel` invocation
in **any** Bazel repo — no NLFR config, no NativeLink deployment required.

← [Wiki hub](../README.md) · [Adopt an existing monorepo](adopt-existing-bazel-monorepo.md)

## Scope boundary

| In scope | Out of scope |
|----------|--------------|
| Wrapping `bazel`/`bazelisk` test/build/run | Non-Bazel commands (use `nlfr run --mode generic`) |
| BEP + stdout/stderr capture, SHA-256 manifest | Remote worker/queue/scheduler claims |
| SQLite ingest + graph/proof projections | Cache-hit evidence without a configured remote cache |
| Honest recording of **failed** builds | Faking a red build green |

## 60-second path

From the root of your Bazel repo (the directory with `MODULE.bazel`,
`WORKSPACE.bazel`, or `WORKSPACE`):

```bash
# 1. Wrap your normal bazel command with `nlfr record -- ...`
nlfr record -- bazel test //your:target

# 2. Read the summary it prints: run group, status, exit code,
#    evidence dir, and the two projection paths.
```

That single command:

1. Injects `--build_event_json_file=<evidence>/bazel-bep.json` immediately after
   your Bazel verb (`test`/`build`/`run`), leaving your own flags untouched.
2. Runs your command in the workspace, capturing stdout, stderr, and the exit
   code.
3. Hashes every captured artifact into an immutable `artifact_manifest.json`.
4. Ingests the BEP into SQLite (`data/nlfr-record/<run-group>/nlfr.sqlite`).
5. Exports two projections you can attach to a PR or dashboard:
   - `projections/graph-<run-group>.json` — action graph
   - `projections/proof-<run-group>.json` — proof packet

Every projected row carries the NLFR truth labels: `source_kind`, `confidence`,
`evidence_refs`, and `redaction_state`.

## Common options

```bash
# Name the run group (default: record-<UTC date>, e.g. record-2026-07-06)
nlfr record --run-group nightly -- bazel test //...

# Record from a different workspace root
nlfr record --workspace /path/to/repo -- bazel build //app:server

# Choose where evidence lands (default: <workspace>/data/nlfr-record/<run-group>)
nlfr record --output-dir /tmp/evidence -- bazel test //pkg:unit

# Machine-readable summary for scripting/CI
nlfr record --json -- bazel test //your:target
```

If you already pass your own `--build_event_json_file`, `nlfr record` honors it
and ingests from that path instead of injecting a second one.

## Failing builds are the product

A non-zero Bazel exit is a **valid** recording — the failure evidence is exactly
what you want to keep. `nlfr record`:

- records the run with `status: failed` and the real exit code,
- still ingests the BEP (failed targets, `command_exit`, `build_finished`),
- **mirrors Bazel's exit code** as its own, so a red build stays red in CI.

Nothing is masked green. See [AGENTS.md](../../../AGENTS.md) doctrine.

## Exit codes & CI disambiguation

`nlfr record` keeps its **own** failures out of Bazel's exit-code space so a CI
pipeline can tell "you invoked nlfr wrong" apart from "your build failed":

| Exit code | Meaning | Who to blame |
|-----------|---------|--------------|
| `64` | **nlfr usage error** — no command, a non-`bazel`/`bazelisk` executable, no workspace marker, or **no recognized Bazel verb** in your command | Fix the `nlfr record` invocation |
| `127` | **bazel/bazelisk executable not found** on `PATH` | Install/point to Bazel |
| anything else | **Bazel's own exit code, mirrored faithfully** (e.g. `0` pass, `1` build failed, `2` bad Bazel command line, `3`/`4` test failures) | Your build/tests |

Why this matters: Bazel itself uses `1` (build failed) and `2` (command-line
problem). If nlfr reused those for its own preflight rejections, a pipeline
parsing the exit code could not distinguish a broken `nlfr record` call from a
genuine build failure. `64` (BSD `EX_USAGE`) and `127` (shell "command not
found") never collide with Bazel.

The verb `64` case is deliberately honest: nlfr locates the Bazel verb by
matching a **known-verb set** (`build`, `test`, `run`, `query`, `coverage`, …)
rather than guessing "the first non-`--` token" — because startup options can
take space-separated values (`--bazelrc /path`, `--output_base /path`) that
would otherwise be mistaken for the verb, corrupting the injected
`--build_event_json_file`. If nlfr can't find a known verb it **refuses to
guess** and tells you to use a supported verb or pass your own
`--build_event_json_file=PATH` (which bypasses verb detection entirely).

**JSON consumers:** with `--json`, *every* failure path — preflight rejections,
missing executable, and post-run results — emits a structured object on
**stdout** (never empty stdout). Read `status` and `record_error` rather than
inferring intent from the exit code; the `exit_code` field carries the same
code the process returns. `record_error` is `null` on a successful recording.

```bash
# Fail the job on an nlfr misuse, but keep bazel's own codes intact:
nlfr record --json -- bazel test //... > record.json
code=$?
if [ "$code" = 64 ] || [ "$code" = 127 ]; then
  echo "nlfr was invoked incorrectly:"; jq -r .record_error record.json; exit 1
fi
# otherwise $code is bazel's own exit code (0 = green, non-zero = red)
exit "$code"
```

## CI snippets

### GitHub Actions

```yaml
- name: Record Bazel evidence
  run: nlfr record --run-group ci-${{ github.run_id }} -- bazel test //...
  # Non-zero bazel exit propagates and fails the job honestly.

- name: Upload evidence
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: nlfr-evidence
    path: data/nlfr-record/
```

### Buildkite

```yaml
steps:
  - label: ":bazel: record tests"
    command: nlfr record --run-group "ci-$BUILDKITE_BUILD_NUMBER" -- bazel test //...
    artifact_paths: "data/nlfr-record/**/*"
```

## Honest limits

- **No NativeLink required.** `nlfr record` works against a plain Bazel repo.
- **Cache-hit evidence appears only when Bazel is configured against a remote
  cache** (e.g. `--remote_cache=...`). Without one, cache-event rows are simply
  absent — the recorder does not invent them.
- **v1 wraps Bazel only.** For other commands, use
  `nlfr run --mode generic --command '<your command>'`.
- Bazel output is captured to files, not streamed live; read
  `runs/<run-id>/artifacts/bazel.stdout.txt` for the full log.

## Truth labels

Ingested Bazel evidence is `collectable_v1` at `high` confidence. Absence of
NativeLink or remote-cache stats is recorded as absence, never as a claim.

Reference: [truth labels](../reference/truth-labels.md).

## Related

- [Adopt an existing Bazel monorepo](adopt-existing-bazel-monorepo.md) — deeper adoption path
- [Attach proof to a PR](attach-proof-to-pr.md) — turn projections into PR markdown
- [Export and compare run groups](export-and-compare-run-groups.md) — compare lens
- [One pager](../../ONE_PAGER.md) — proven vs unproven claims
