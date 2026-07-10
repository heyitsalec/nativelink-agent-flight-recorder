# Reference: NLFR CLI

**Quadrant:** Reference · **Audience:** operators automating proof and export

Invoke via `python3 -m nlfr` or `uv run python -m nlfr` with `PYTHONPATH=src` in
dev trees. All exporters read SQLite — they do not invent backend state.

← [Wiki hub](../README.md) · [Truth labels](truth-labels.md)

## Global pattern

```bash
PYTHONPATH=src uv run python -m nlfr <command> [options]
```

Default DB path for exporters: `data/nlfr/nlfr.sqlite`. Default run group: `latest`
(a literal match, not a resolver). `nlfr record` writes recorded databases at
`data/nlfr-record/<run-group>/nlfr.sqlite`.

**Read commands never create or migrate a database.** `graph`/`runway`/`proof`
export and `compare index`/`history`/`export` open the `--db` (and
`--left-db`/`--right-db`) read-only. A nonexistent, zero-byte, or non-SQLite path
is a hard error (exit 2) that names the path and leaves no file behind — a typo
cannot fabricate an empty, zero-value projection. An *existing* database with zero
run groups is still an honest empty report for `compare index`/`history`.

Readers also never migrate an old database on open (that would silently rewrite
recorded evidence). A `--db` whose schema version is **older** than this build is
a hard error (exit 2) that tells you to run [`nlfr db upgrade`](#db-upgrade)
first; a `--db` **newer** than this build is refused too (upgrade nlfr). Migrating
evidence is always an explicit, operator-consented act.

## doctor

Check local tool availability for proof modes.

```bash
python3 -m nlfr doctor --mode cache-only
python3 -m nlfr doctor --mode local-exec
python3 -m nlfr doctor --mode cache-only --json
```

| Flag | Default | Description |
|------|---------|-------------|
| `--mode` | `cache-only` | `cache-only` or `local-exec` |
| `--json` | off | Machine-readable check list |

`local-exec` additionally validates `demo/nativelink/local-execution.json5`.

Exit code `0` when all checks pass; `1` when tools or config are missing.

## run

Run a Bazel workload and record evidence.

```bash
python3 -m nlfr run --mode cache-only --scenario tri-agent-loop //...
python3 -m nlfr run --mode local-exec --target //tasks:priority_test
python3 -m nlfr run --mode generic --change-path README.md --provenance-sidecar sidecar.json --command "pytest -q"
```

| Flag | Default | Description |
|------|---------|-------------|
| `--mode` | `cache-only` | `cache-only`, `local-exec`, or `generic` |
| `--scenario` | — | Scenario label for run key |
| `--target` | `//...` | Alias for the positional target pattern (both forms accepted) |
| `--run-group` | `latest` | Projection export grouping |
| `--workspace` | `demo/bazel-monorepo` | Bazel workspace root |
| `--output-dir` | `data/nlfr` | SQLite + artifact root |
| `--nativelink-config` | by mode | Override NativeLink config path |
| `--nativelink-executable` | `nativelink` | NativeLink binary |
| `--nativelink-timeout` | `2.0` | Seconds before timeout record |
| `--bazel-executable` | `bazel` | Bazel binary |
| `--bazel-startup-arg` | repeatable | Bazel startup flags |
| `--bazel-arg` | repeatable | Bazel test flags (e.g. `--bazel-arg=--config=lre`) |
| `--remote-cache` | `grpc://127.0.0.1:50051` | Cache endpoint |
| `--remote-executor` | `grpc://127.0.0.1:50051` | Executor endpoint (`local-exec`) |
| `--skip-nativelink` | off | Bazel-only capture |
| `--json` | off | Machine-readable run metadata |
| `target` | `//...` | Bazel target pattern |

### generic mode (M8)

Additional flags via `register_generic_args`:

| Flag | Description |
|------|-------------|
| `--change-path` | File the agent edited |
| `--provenance-sidecar` | JSON sidecar from `record-agent-change.sh` |
| `--command` | Validation shell command |

See [Cursor adapter](../../../adapters/cursor/README.md).

## simulate

Deterministic scenario replay (`simulated_v1` where fixtures apply).

```bash
python3 -m nlfr simulate --scenario tri-agent-loop --ingest
```

Use `--ingest` to load fixture evidence into SQLite. Full flags: `nlfr simulate --help`.

## ingest

Ingest Bazel evidence files or an artifact directory into SQLite (idempotent keys).

```bash
python3 -m nlfr ingest path/to/artifacts --run-group my-group --database data/nlfr/nlfr.sqlite
python3 -m nlfr ingest --bep path/to/bazel.bep.json --run-key my-run:cache-only
```

| Flag | Default | Description |
|------|---------|-------------|
| `path` | — | Artifact directory or evidence file |
| `--database` | `data/nlfr/nlfr.sqlite` | SQLite path |
| `--run-key` | derived | Stable idempotent run key |
| `--run-group` | — | Run group label |
| `--bep` / `--execution-log` / `--profile` | — | Explicit evidence files |
| `--source-kind` | `collectable_v1` | `collectable_v1` or `simulated_v1` |

Run keys are stable and idempotent: re-ingesting the same `--run-key` under the
**same** run group updates nothing (safe to repeat). Reusing a run key that already
belongs to a **different** run group is a hard error (exit 2) — that would silently
merge the new evidence into the first group — so pick a distinct `--run-key`, or
ingest under the group the key already belongs to.

When the BEP records a `started` event, ingest carries its real build start time as
the run's `started_at` (evidence-derived, never the wall-clock ingest time). Evidence
with no observable start stays age-unknown, which `db gc` never auto-deletes (below).

Proof scripts call ingest internally; operators rarely need this directly.

## graph export

```bash
python3 -m nlfr graph export --run-group baseline \
  --db data/nlfr-record/baseline/nlfr.sqlite --output graph.json
```

Exports action graph projection JSON. The `--db` must already exist (read-only).

## proof export

```bash
python3 -m nlfr proof export --run-group baseline \
  --db data/nlfr-record/baseline/nlfr.sqlite --output proof-packet.json
```

Exports proof packet JSON (cache economics, remote boundary, agent provenance
blocks). `json`/`markdown` over an *existing* DB whose run group has no runs
still emit an empty-payload projection; only a missing/empty `--db` is a hard
error. `--format in-toto` additionally hard-errors on an empty subject (see #26).

## runway export

```bash
python3 -m nlfr runway export --run-group baseline \
  --db data/nlfr-record/baseline/nlfr.sqlite --output runway.json
```

Exports validation runway projection. The `--db` must already exist (read-only).

Both `graph export` and `runway export` scrub local absolute paths (an
invocation's `cwd`, the injected `--build_event_json_file=<abs path>`) to a
basename-preserving `[REDACTED:abs_path]/<basename>` placeholder at projection
time, and relabel any scrubbed node `redaction_state: redacted` — never `safe`
for content that had to be scrubbed. The recorded SQLite row is never mutated.

## redact

Scrub secrets/PII before you share evidence — a **JSON projection**, a
**plain-text log** (stdout/stderr), or a whole **evidence directory**. Ships in
the wheel — the packaged, adopter-facing equivalent of the repo-side
`scripts/redact-projection.py`.

```bash
# Scan only — exit 1 if any secret/PII shape is found; writes nothing
python3 -m nlfr redact --check projections/graph-baseline.json

# A raw non-JSON log is scanned as PLAIN TEXT (not refused as "not JSON")
python3 -m nlfr redact --check data/nlfr-record/ci/runs/<id>/artifacts/bazel.stdout.txt

# A DIRECTORY enables tree mode: recursively scan every regular file (the CI gate)
python3 -m nlfr redact --check data/nlfr-record/ci

# Redact + write: a shareable copy of one file, or a redacted mirror of a tree
python3 -m nlfr redact projections/graph-baseline.json graph-shareable.json
python3 -m nlfr redact data/nlfr-record/ci redacted-evidence/
```

| Flag | Default | Description |
|------|---------|-------------|
| `input` | — | projection JSON, plain-text file, or evidence **directory** to scan/redact |
| `output` | — | destination file (or directory, for a tree) — required unless `--check` |
| `--check` | off | scan only; write nothing; exit 1 on any finding |
| `--format {json,text}` | auto | force the input interpretation (default: JSON if it parses, else text) |
| `--no-pii` | off | disable the default PII detectors (email + ipv4) |
| `--no-email` | off | disable the email detector |
| `--no-ip` | off | disable the IPv4 detector |
| `--hostname` | off | opt in to hostname redaction (off by default: FQDN shapes collide with tool/file names) |

**Text mode.** A non-JSON file is scanned/redacted as plain text with the *same*
detector registry (string-level spans; no JSON walk; no `redaction_state`
semantics — a text file carries no truth labels). Findings report a 1-based line
number and a masked excerpt. This is what lets `--check` gate a raw
`bazel.stdout.txt` — the file type where build-output secrets actually land —
instead of refusing every non-JSON file. Auto-detected by a JSON-parse attempt;
`--format` overrides.

**Tree mode.** A directory argument recursively scans (check) or
copies-and-redacts (write → an output dir mirroring the tree) every regular file,
honoring both formats. It **skips honestly, never silently**: binaries
(null-byte sniff → `skipped:binary`, a secret in a binary is out of scope) and
SQLite databases (`skipped:database` — local evidence, not meant for upload) are
reported in the check output and left out of a redacted mirror. The binary/DB
safety sniff **always runs first and outranks `--format`** — `--format text` over
an `nlfr.sqlite` skips the database, never decodes it into a corrupted copy;
`--format` only disambiguates text-vs-json for files that pass the sniff. **Symlinks
are never followed**: a directory or file link, at any depth, is reported as
`skipped:symlink` and left out of both the scan and the written mirror (which
therefore contains zero symlinks) — an alias would double-count evidence and a
link can smuggle out-of-scope filesystem content into a tree told to be safe to
share. Pass the real path explicitly if you mean to include it. `--check` exits 1
if *any* file has a finding; skips alone never fail the gate (but the report
always makes the non-scan visible). This is the gate
the [record how-to CI snippets](../how-to/record-your-own-build.md#ci-snippets)
run before uploading a raw evidence tree.

Secret-tier detectors (home paths, PEM keys, AWS/GitHub/GitLab/Slack tokens,
JWTs, URL/`Authorization` credentials) are always on. The `abs_path` detector is
also on by default: it flags (and, in write mode, scrubs to
`[REDACTED:abs_path]/<basename>`) **non-home absolute local paths** — the
`/private/tmp/…`, `/data/…`, `/var/folders/…` class the graph/runway projectors
scrub at export time — plus local `file:///abs/path` URIs (scheme preserved,
`file://[REDACTED:abs_path]/<basename>`). This closes the gap where a stale or
externally-produced projection carrying a raw `cwd`/`command` path under a
`redaction_state: safe` node would pass `--check` silently. `/Users`/`/home`
keep their `${HOME}` collapse; Bazel labels (`//foo:bar`), relative paths, and
remote URI authorities (`grpc://`, `bytestream://`, `https://`, `ssh://`,
`file://host/share`) are never flagged. This is defense-in-depth pattern
matching, **not** a guarantee — a free-standing high-entropy secret with no
prefix/marker is not regex-detectable without false-positiving over this
corpus's SHA digests; review sensitive evidence at the source too. When a value
is redacted inside an object carrying `redaction_state`, that state is honestly
upgraded `safe`/`unknown` → `redacted`. Guide:
[record your own build → before you share](../how-to/record-your-own-build.md#before-you-share-a-projection).

## db upgrade

```bash
python3 -m nlfr db upgrade --db data/nlfr-record/baseline/nlfr.sqlite
```

Migrates an **existing** database to the current schema version, in place. This
is the explicit, operator-consented way to bring an old database up to date —
read commands never migrate on open, so a reader that reports `is schema vN …
refusing to read` is telling you to run this first. The upgrade is idempotent
(an already-current DB reports "nothing to upgrade", exit 0) and preserves every
recorded row. It refuses to *create* a database (a nonexistent/empty/non-SQLite
`--db` is a hard error, exit 2) and refuses to *downgrade* one written by a newer
nlfr (exit 2 — upgrade nlfr instead).

## db gc

```bash
# DRY RUN (default): print the retention plan, delete nothing.
python3 -m nlfr db gc --db data/nlfr-record/shared/nlfr.sqlite --keep-last 5

# APPLY: actually delete the older run groups and reclaim space.
python3 -m nlfr db gc --db data/nlfr-record/shared/nlfr.sqlite --keep-last 5 --apply
```

Operator-consented retention. `retention_policy.py` documents "no auto-purge,
operator-managed" — `db gc` is that *managed* mechanism, and nothing about it is
automatic. The unit of deletion is always a whole **run group** (never individual
rows), so the `ON DELETE CASCADE` from `runs` can never orphan referenced child
evidence, and on-disk `runs/<id>/` artifact trees are removed only when they live
inside the database's own evidence root. Nothing outside that root is ever touched.

**Deleting evidence is the marked action.** A bare invocation is a **dry run**
that prints the plan (which groups, run/row/file/byte counts) and deletes nothing;
real deletion requires an explicit `--apply`. This deliberately inverts the usual
`--dry-run` convention — you cannot delete recorded evidence by forgetting a flag.

Choose exactly one selection mode (combining them is an exit-2 usage error):

| Mode | Meaning |
|------|---------|
| `--keep-last N` | Keep the N most-recent run groups (by latest run), delete older ones |
| `--keep-days D` | Delete run groups whose newest run is older than D days |
| `--run-group G` | Delete this run group (repeatable) |

Safety rails:

- **Unknown age is never auto-deleted.** The recency modes (`--keep-last` /
  `--keep-days`) rank only run groups with a known start time. A group whose runs
  have no recorded `started_at` (age unknown) is excluded from both the keep and
  the delete set and reported separately — *"N group(s) with unknown age — not
  auto-selected; delete explicitly with `--run-group`"* — in the plan, `--json`,
  and `gc-report.json`. This prevents a freshly-ingested, un-timestamped group
  from being ranked "oldest" and deleted ahead of a genuinely ancient one. To
  delete an age-unknown group, name it explicitly with `--run-group`.
- **Empty-store guard.** Deleting the last remaining run group (leaving an empty
  evidence database) is refused unless you add `--allow-empty`. Age-unknown groups
  still populate the store, so a delete that leaves only unknown-age groups is not
  "emptying" it and is allowed.
- **Out-of-tree guard.** If a group references evidence via an absolute path
  outside the evidence root, the whole group is refused (partial deletion is
  worse) and nothing is deleted.
- **Schema gate.** Like every writer, `db gc` refuses a database whose schema is
  not this build's — an older DB is pointed at [`nlfr db upgrade`](#db-upgrade)
  first (exit 2), and it never *creates* a database (a missing/empty/non-SQLite
  `--db` is a hard error, exit 2).

On `--apply`, gc runs `VACUUM` to reclaim freed space and writes a durable,
append-only `gc-report.json` next to the database — deleting evidence always
leaves a record of the deletion. The report (also available on stdout, or as JSON
with `--json`) is `derived_v1` and records each deleted group's name, run ids,
time range, per-table row counts, and file/byte totals — identifying metadata
only, never resurrectable content. The `vacuum.reclaimed_bytes` figure is the
**true on-disk delta** (a WAL checkpoint runs after `VACUUM` before the size is
measured), so it matches what you would `stat` the instant the command returns —
never a fabricated `0`.

**`--json` on failure.** Like `nlfr record --json`, every guard-rail/usage-error
path — bad `--db`, combined selection modes, the last-group refusal, the
out-of-tree guard, an unknown `--run-group`, and the schema gate — emits a
structured object on **stdout** under `--json` (`status`, `gc_error`,
`exit_code`, plus the `derived_v1` truth-label envelope), so a CI-scripted
retention job reading stdout JSON never gets empty output on a refusal. Without
`--json` these print human-readable text to stderr. Exit codes are unchanged
(guard-rail refusals stay exit 2); only the output *shape* gains the `--json`
branch.

## evaluate

```bash
python3 -m nlfr evaluate --run-group loop-iter1 \
  --db data/nlfr-loop/nlfr.sqlite \
  --artifact-root data/nlfr-loop/runs/<run>/artifacts \
  --attribution-target //tasks:escalation_policy_test \
  --record --output verdict.json
```

Evaluates one run group's recorded evidence into a deterministic, truth-labeled
verdict (`nlfr.evaluation.v1`): validation status, honest-failure
classification (`scenario_validation_failure` / `toolchain_failure` /
`unattributed_failure` / `first_pass_success` / `unclassified`), a redacted
failure-evidence excerpt (from the recorded `bazel.stderr/stdout.txt`
artifacts when `--artifact-root` is given), cache and artifact-verification
rollups, and a `next_steps` list with a **tested precedence contract**:
`record_environment_blocker` > `rerun_validation` >
`dispatch_fix_with_evidence` > `attach_missing_evidence` > `none_complete`.

The verdict is always `derived_v1` with weakest-input confidence — a computed
judgment over already-labeled evidence, never a new observation. Degraded
inputs degrade the verdict honestly: no raw logs means `unclassified` plus an
`attach_missing_evidence` step, never a guess. `--workspace PATH` lets the
evaluator observe pending (unvalidated) edits by hashing changed files against
the newest recorded after-hash; without it, `rerun_validation` never fires.

`--record` re-opens the DB read-write and upserts the verdict as an
`evaluation` proof block (idempotent per run). `--format markdown` renders a
short human summary with a sibling `.json` sidecar. Exit codes: `0` evaluated,
`2` cannot evaluate (missing DB / unknown run group), and `1` only with
`--fail-on-action-required` when the first next step is not `none_complete`.

## loop

```bash
python3 -m nlfr loop --scenario two-act-underspec \
  --mode cache-only --skip-nativelink --remote-cache grpc://127.0.0.1:50051 \
  --claude-bin claude --max-iterations 2 --output-dir data/nlfr-loop
```

Drives the closed agent loop natively: per iteration it invokes the agent
(`agent-invoke`, receipts captured), applies the change to the loop's own
workspace copy, validates through `nlfr run` into an **iteration-scoped run
group** (`<prefix>-iter<N>`), ingests, exports projections, then evaluates
with `--record` and branches ONLY on `next_steps[0].action`:

- `dispatch_fix_with_evidence` — the next prompt embeds the verdict's recorded
  failure excerpt (recorded artifacts, never a re-run) and the loop iterates;
- `record_environment_blocker` — exit 2 with `loop-blocker.json`: retrying into
  a broken toolchain would fabricate an agent-failure narrative;
- `none_complete` — success: first-vs-last compare projection exported, exit 0.

Hitting `--max-iterations` while red exits 1. `loop-summary.json`
(`nlfr.loop.v1`) records per-iteration verdict/receipt refs, the outcome, and
honest checks (first iteration red, honest classification, fix receipt
present, final green, warm cache, compare exported). Raw prompts live only in
a scratch directory deleted before the command returns. The loop does not
manage the NativeLink server — see
[`scripts/agentic-loop-proof.sh`](../../../scripts/agentic-loop-proof.sh) for
the environment bring-up wrapper.

## receipt import

```bash
python3 -m nlfr receipt import --receipt agent-receipt.json \
  --db data/nlfr-record/pr-validation/nlfr.sqlite --run-group pr-validation
```

Attaches an `nlfr.agent_receipt.v1` file produced by an invocation NLFR did
not observe (CI runner, pod, hosted agent) to a recorded run group. The file
is schema- and privacy-validated first (raw-prompt keys reject the import with
exit 2; nothing is written), recorded as a content-hashed artifact, and
attached as an `agent_provenance` proof block with `provenance_class:
receipt_imported_v1`, `source_kind: collectable_v1`, `confidence: medium`.
Imported receipts are stamped `live: false` / `observed_by_nlfr: false` and
always render `receipt_verified: false` — the class states evidence shape,
not trust ([how-to](../how-to/capture-agent-telemetry-in-ci.md)).
`--run-key` targets a specific run; the default is the newest run in the
group.

## compare (M9)

### compare index

```bash
python3 -m nlfr compare index --db data/nlfr-record/baseline/nlfr.sqlite
python3 -m nlfr compare index --db data/nlfr-record/baseline/nlfr.sqlite --json
```

Lists run groups with run counts (retention index only). An existing DB with zero
groups prints `no run groups recorded` (exit 0); a missing/empty `--db` exits 2.

Pass **exactly one** of `--db` (a single shared database) or `--db-root DIR`
(browse the whole `nlfr record` layout). Neither, or both, is a hard error
(exit 2).

```bash
# Browse every per-run-group database `nlfr record` wrote under data/nlfr-record:
python3 -m nlfr compare index --db-root data/nlfr-record --json
```

`--db-root` discovers databases at `<DIR>/<run-group>/nlfr.sqlite` — **exactly one
directory level down**, matching the `nlfr record` layout; it never recurses into
arbitrary trees, ignores subdirectories without an `nlfr.sqlite`, and **never
follows symlinks** (a group-shaped symlink is reported as `symlinked_entry`, not
read — aliases would double-count evidence and links can escape the root).
Hardlinks are **not detectable** (same inode, ordinary paths): duplicate
directory entries for one physical database list — and count — twice; they
cannot cross filesystems or escape the root (accepted residual). The result is
a LISTING keyed by `(database, run_group)`, **never a merge** (stable run ids can
collide across independent databases). Each entry gains a `database` field
(absolute paths are scrubbed at the sharing boundary; the run group survives in
`discovered_group`). A zero-byte or old-schema database is reported honestly with
its `reason` (old-schema entries carry `nlfr db upgrade` guidance in `detail`) —
never silently skipped. A listing with such problems still exits 0; **zero
readable databases** exits 2.

### compare history

```bash
python3 -m nlfr compare history --db data/nlfr-record/baseline/nlfr.sqlite
python3 -m nlfr compare history --db data/nlfr-record/baseline/nlfr.sqlite --limit 10 \
  --output run-history.json
```

Exports multi-run `run_history` projection (`derived_v1`) with per-group proof
summaries. Guide: [browse run history](../how-to/browse-run-history.md).

`--db-root DIR` is the same one-of / mutually-exclusive choice as `compare index`
(neither or both exits 2). It lists per-database summaries across the `nlfr record`
layout, keyed by `(database, run_group)` — a listing, not a merge:

```bash
python3 -m nlfr compare history --db-root data/nlfr-record \
  --output run-history.json
```

Any cross-database *comparison* goes through
`compare export --left-db X --right-db Y` (below); `--db-root` history never
builds cross-database deltas.

### compare export

Cross-DB is the realistic form for two recorded groups (one database per group):

```bash
python3 -m nlfr compare export \
  --left-db data/nlfr-record/baseline/nlfr.sqlite \
  --right-db data/nlfr-record/candidate/nlfr.sqlite \
  --left baseline --right candidate \
  --output compare-projection.json
```

Single-DB form when one database holds both groups (shared `--output-dir` or
combined ingest):

```bash
python3 -m nlfr compare export --left baseline --right candidate \
  --db data/nlfr-record/shared/nlfr.sqlite \
  --output compare-projection.json
```

Each side is opened read-only and validated independently: a missing/empty `--db`,
`--left-db`, or `--right-db`, or a run group with zero runs, is a hard error (exit
2) that names the side and lists the groups present. Compare output is
`derived_v1`. Guide: [export and compare run groups](../how-to/export-and-compare-run-groups.md).

## init / serve

| Command | Purpose |
|---------|---------|
| `nlfr init` | Write `nlfr.toml` + `data/.nlfr/` scaffold (workspace, database, run-group defaults) |
| `nlfr serve` | Dev projection server for canvas |

Init is idempotent and does not require NativeLink:

```bash
python3 -m nlfr init
python3 -m nlfr init --workspace demo/bazel-monorepo --run-group adopted --json
```

One-command record in the reference repo: `./scripts/record-this-target.sh`. Guide:
[adopt existing Bazel monorepo](../how-to/adopt-existing-bazel-monorepo.md).

## Proof-before-done bundle

From [AGENTS.md](../../../AGENTS.md):

```bash
python3 -m pytest
python3 -m nlfr doctor --mode cache-only
python3 -m nlfr run --scenario tri-agent-loop --mode cache-only --target //...
python3 -m nlfr graph export --run-group latest
python3 -m nlfr proof export --run-group latest
```

## Related

- [Proof scripts matrix](proof-scripts-matrix.md)
- [Design routing](../../design/routing.md) — canvas bindings for exports
