# How-to: attach proof to a PR

**Quadrant:** How-to · **Audience:** operators and reviewers pasting evidence into pull requests  
**Milestone:** W8 — PR proof attachment

Export a **redacted markdown proof summary** from ingested SQLite evidence and paste it
into a PR comment or CI artifact. The summary carries truth labels on every claim block;
it never includes raw prompts, private logs, or absolute home paths.

← [Wiki hub](../README.md) · [CLI reference](../reference/cli.md) · [Proof samples](../../proof-samples/pr-proof-comment-sample.md)

## Prerequisites

- A proof output directory with `nlfr.sqlite` (e.g. `data/record-proof/`)
- Optional projection JSON under `projections/` (graph, proof packet, runway)
- Optional `artifact_manifest.json` beside the DB

## Quick export

```bash
./scripts/export-pr-proof-comment.sh --run-group record-proof
```

Default output: `data/pr-proof-comment/proof-comment.md`

Override paths:

```bash
./scripts/export-pr-proof-comment.sh \
  --run-group record-proof \
  --db data/record-proof/nlfr.sqlite \
  --output /tmp/pr-proof.md
```

Environment overrides: `NLFR_PR_PROOF_RUN_GROUP`, `NLFR_PR_PROOF_DB`, `NLFR_PR_PROOF_OUTPUT`.

## CLI export (markdown format)

```bash
PYTHONPATH=src uv run python -m nlfr proof export \
  --format markdown \
  --run-group record-proof \
  --db data/record-proof/nlfr.sqlite \
  --repo-root "$PWD" \
  --manifest data/record-proof/artifact_manifest.json \
  --proof-projection data/record-proof/projections/proof-packet.json \
  --output proof-comment.md \
  --fail-on-validation
```

`--format json` remains the default for programmatic consumers.

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Export succeeded; no validation failures recorded |
| `1` | Export succeeded but validation failures were present (targets/actions failed) |
| `2` | Missing database or CLI error |

**Unsupported boundary labels** (e.g. `worker_identity`, `queue_time` in the remote-execution
block) do **not** fail export. They appear as honest ceiling labels in the markdown.

## Paste into a PR

1. Run the export script after your proof run completes.
2. Open the generated `proof-comment.md`.
3. Paste the markdown into a PR comment (or attach as a CI artifact).
4. Link reviewers to the cited projection JSON paths and manifest for drill-down.

Committed redacted sample:
[`pr-proof-comment-sample.md`](../../proof-samples/pr-proof-comment-sample.md).

## Redaction rules

The markdown exporter builds from **already-scrubbed proof JSON**, so it never
inlines raw stdout/stderr bytes. It:

- Replaces repo-root paths with `<repo>` when `--repo-root` is set
- Collapses `/Users/...` and `/home/...` prefixes to `${HOME}`, and scrubs
  **non-home absolute paths** (`/private/tmp/…`, `/data/…`) to
  `[REDACTED:abs_path]/<basename>` — the `abs_path` scrub the projectors apply at
  the sharing boundary
- Surfaces agent provenance as **model + `prompt_sha256` prefix only** — never raw prompt text
- Labels every block with `source_kind`, `confidence`, and `redaction_state`

### Gate it with `nlfr redact` before you paste

The exporter's scrub is the *first* line of defense; `nlfr redact` is the
belt-and-suspenders gate. It carries a registry of secret/PII detectors (AWS /
GitHub / GitLab / Slack tokens, PEM keys, JWTs, `Authorization` credentials,
emails, IPv4) **plus** the `abs_path` detector, and runs in two modes over either
the proof JSON *or* the exported markdown (which is scanned as plain text — not
refused as "not JSON"):

```bash
# CHECK (gate): exit 1 if any secret/PII/abs-path shape is present; writes nothing.
nlfr redact --check data/pr-proof-comment/proof-comment.md
nlfr redact --check projections/proof-<run-group>.json

# WRITE: emit a scrubbed copy to paste instead of the original.
nlfr redact projections/proof-<run-group>.json proof-shareable.json
```

`--check` prints each finding (detector, location, **masked** excerpt — never the
raw secret) and exits non-zero, so it drops straight into a pre-paste CI step.
This is defense-in-depth pattern matching, **not** a guarantee — review sensitive
evidence at the source too. Full detector list, scope, and limits:
[redact CLI reference](../reference/cli.md#redact) and the
[before-you-share section](record-your-own-build.md#before-you-share-a-projection).

## CI recipe (optional)

Add a job step after proof ingest:

```bash
./scripts/export-pr-proof-comment.sh --run-group "$RUN_GROUP"
```

Upload `data/pr-proof-comment/proof-comment.md` as an artifact. Treat exit code `1` as a
**validation failure** (failed Bazel targets), not as an export or redaction failure.

## Related

- [Export and compare run groups](export-and-compare-run-groups.md)
- [Proof packet v1 contract](../reference/contracts/proof-packet-v1.md)
- [Proof samples hub](../../proof-samples/README.md)
