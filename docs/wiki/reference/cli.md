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

**Read commands never create a database.** `graph`/`runway`/`proof` export and
`compare index`/`history`/`export` open the `--db` (and `--left-db`/`--right-db`)
read-only. A nonexistent, zero-byte, or non-SQLite path is a hard error (exit 2)
that names the path and leaves no file behind — a typo cannot fabricate an empty,
zero-value projection. An *existing* database with zero run groups is still an
honest empty report for `compare index`/`history`.

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
