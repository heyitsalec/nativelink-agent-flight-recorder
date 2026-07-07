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
only, never resurrectable content.

## compare (M9)

### compare index

```bash
python3 -m nlfr compare index --db data/nlfr-record/baseline/nlfr.sqlite
python3 -m nlfr compare index --db data/nlfr-record/baseline/nlfr.sqlite --json
```

Lists run groups with run counts (retention index only). An existing DB with zero
groups prints `no run groups recorded` (exit 0); a missing/empty `--db` exits 2.

### compare history

```bash
python3 -m nlfr compare history --db data/nlfr-record/baseline/nlfr.sqlite
python3 -m nlfr compare history --db data/nlfr-record/baseline/nlfr.sqlite --limit 10 \
  --output run-history.json
```

Exports multi-run `run_history` projection (`derived_v1`) with per-group proof
summaries. Guide: [browse run history](../how-to/browse-run-history.md).

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
