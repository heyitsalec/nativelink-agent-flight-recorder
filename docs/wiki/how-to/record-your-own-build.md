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

## Before you share a projection

The recorder records **raw** evidence locally — an invocation's real `cwd` and
the injected `--build_event_json_file=<absolute path>` land in the SQLite spine
verbatim, which is correct: local evidence should be faithful. The **projection**
is the sharing boundary. `nlfr graph export` and `nlfr runway export` scrub local
absolute paths (home dirs *and* `/private/tmp`-style paths) to a
basename-preserving placeholder — `/Users/you/repo/workspace` becomes
`[REDACTED:abs_path]/workspace` — and any node that had to be scrubbed is
relabelled `redaction_state: redacted` rather than claiming `safe`. The recorded
SQLite row keeps its raw, record-time value; scrubbing happens only when the
shared projection is built.

Belt-and-suspenders: before you attach **any** projection to a PR or dashboard,
gate it with `nlfr redact` (defense-in-depth pattern matching for credentials +
PII on top of the path scrub — **not** a guarantee; review sensitive evidence at
the source too):

```bash
# Fail the share if a secret/PII shape is present (writes nothing; exit 1 on find)
nlfr redact --check projections/graph-<run-group>.json

# Or write a scrubbed copy to attach instead of the raw projection
nlfr redact projections/graph-<run-group>.json graph-shareable.json
```

`--check` exits non-zero and prints each finding (detector, JSON path, masked
excerpt — never the raw secret) so it drops straight into a pre-publish CI step.
See the [redact CLI reference](../reference/cli.md#redact) and the module
docstring in `src/nlfr/redaction.py` for the honest scope and limits.

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

The verb `64` case is deliberately honest: nlfr locates the Bazel verb with an
**arity-aware scan** of the startup segment — `=`-form and boolean startup
options consume one token, known unary options (`--bazelrc /path`,
`--output_base /path`, …) consume two — so even a startup-option *value* that
spells a verb (`--output_base test build //x`) cannot steal the verb slot.
When an unknown startup option makes the scan ambiguous, or no known verb is
present, nlfr **refuses to guess** (injecting into Bazel's startup segment
would corrupt your command) and tells you to use a supported verb or pass your
own `--build_event_json_file=PATH` (which bypasses verb detection entirely).

**JSON consumers:** with `--json`, *every* failure path — preflight rejections,
missing executable, and post-run results — emits a structured object on
**stdout** (never empty stdout). Read `status` and `record_error` rather than
inferring intent from the exit code; the `exit_code` field carries the same
code the process returns. `record_error` is `null` on a successful recording.

```bash
# Fail the job on an nlfr misuse, but keep bazel's own codes intact.
# Disambiguate via the JSON contract, not the raw exit code: `bazel run`
# passes the wrapped tool's own exit code through, so a tool that itself
# exits 64/127 would be indistinguishable from nlfr's sentinels by code
# alone. `record_error` is non-null exactly when nlfr (not your build)
# failed.
nlfr record --json -- bazel test //... > record.json
code=$?
err=$(jq -r '.record_error // empty' record.json 2>/dev/null)
if [ -n "$err" ]; then
  echo "nlfr could not record: $err"; exit 1
fi
# $code is bazel's own exit code (0 = green, non-zero = red), evidence recorded
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
