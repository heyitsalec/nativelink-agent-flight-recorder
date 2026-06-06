# Working in nativelink-agent-flight-recorder

This repo is the implementation home for the NativeLink Agent Flight Recorder MVP.

## Product Rule

Build an evidence-first recorder, not a UI-first dashboard.

The canonical flow is:

1. Run a Bazel workload through a NativeLink-backed mode.
2. Capture immutable artifacts with SHA-256 hashes.
3. Ingest evidence into SQLite.
4. Export versioned projection JSON.
5. Render the canvas from projection JSON only.

The canvas is a projection of recorded facts. It must not invent backend state.

## V1 Order

1. Cache-only proof path.
2. Artifact manifest and idempotent SQLite ingest.
3. Bazel evidence parsers.
4. Proof packet and projection JSON.
5. Sparse TypeScript canvas.
6. LRE path when stable on the host.

Remote execution, worker/scheduler dashboards, OTLP/Jaeger clones, real agent
integrations, auth, billing, and multi-tenancy are out of scope for v1.

## Truth Labels

Every projected node, edge, metric, and proof claim must include:

- `source_kind`: `collectable_v1`, `derived_v1`, `simulated_v1`, or `future`
- `confidence`: `high`, `medium`, `low`, or `unknown`
- `evidence_refs`
- `redaction_state`: `safe`, `redacted`, `blocked`, or `unknown`

Do not claim exact worker/action/queue-time correlation unless the implementation
captures direct evidence for it.

## Privacy

Do not export secrets, credentials, raw private logs, environment variables,
raw prompts, customer data, or private legacy GUI/source material. Use hashes,
redacted paths, and short evidence spans where possible.

## Engineering Rules

- Prefer Python stdlib for the recorder: `argparse`, `sqlite3`, `subprocess`,
  `json`, `gzip`, `hashlib`, `pathlib`.
- Use `pytest` as a dev/test dependency.
- Keep runtime dependencies small and justified.
- Tests should exercise real local files, SQLite schemas, and serializers.
- UI tests should use stable selectors and real browser rendering.

## Proof Before Done

Backend work should run:

```bash
python3 -m pytest
```

End-to-end work should eventually prove:

```bash
python3 -m nlfr doctor --mode cache-only
python3 -m nlfr run --scenario tri-agent-loop --mode cache-only --target //...
python3 -m nlfr graph export --run-group latest
python3 -m nlfr proof export --run-group latest
```

If NativeLink or Bazel is unavailable on the host, document the exact blocker
and keep parser/projection tests fixture-backed until the local smoke path is
available.
