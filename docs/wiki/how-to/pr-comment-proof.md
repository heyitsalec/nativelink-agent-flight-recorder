# How-to: post a compact proof summary as a PR comment

**Quadrant:** How-to · **Audience:** operators and reviewers who want NLFR's
honest evidence in the review surface where BuildBuddy / EngFlow dashboards sit
**Milestone:** W4 — PR-comment / CI-attachment exporter (issue #87)

Render a **compact, redacted** proof-packet summary and land it exactly where a
reviewer already looks: a PR comment (markdown) plus a machine-readable JSON
sidecar (a CI artifact). Unlike the verbose per-block export
([attach proof to a PR](attach-proof-to-pr.md)), this is the *scannable* summary
— status, cache economics, the artifact-integrity rollup (local **and** remote
CAS tiers), agent-receipt provenance presence, and an optional in-toto ref.

← [Wiki hub](../README.md) · [CI integration](ci-integration.md) ·
[Attach proof to a PR](attach-proof-to-pr.md) ·
[Compact sample](../../proof-samples/pr-comment-compact-sample.md)

## What it renders

Recorded evidence only — nothing about backend state, cost, or cross-machine
("fleet") performance is invented. The remote-only references stay **unverified**
unless an independent CAS probe recorded a verdict.

Committed compact samples:
[`pr-comment-compact-sample.md`](../../proof-samples/pr-comment-compact-sample.md)
and its JSON sidecar
[`pr-comment-compact-sample.json`](../../proof-samples/pr-comment-compact-sample.json).

## Render the comment + JSON sidecar

```bash
# CLI: writes markdown AND a sibling <stem>.json sidecar by default.
PYTHONPATH=src uv run python -m nlfr proof comment \
  --run-group record-proof \
  --db data/record-proof/nlfr.sqlite \
  --output pr-comment.md
# -> pr-comment.md  +  pr-comment.json
```

Cite an exported in-toto attestation (by content digest, so no path leaks):

```bash
PYTHONPATH=src uv run python -m nlfr proof comment \
  --run-group record-proof \
  --db data/record-proof/nlfr.sqlite \
  --output pr-comment.md \
  --in-toto data/record-proof/attestations/in-toto.jsonl
```

Or use the wrapper script's compact mode, which also runs the redact gate for you:

```bash
./scripts/export-pr-proof-comment.sh --compact \
  --run-group record-proof \
  --db data/record-proof/nlfr.sqlite \
  --output pr-comment.md
```

| Flag | Meaning |
|------|---------|
| `--output` | markdown path (default: stdout). A sibling `<stem>.json` sidecar is written beside it. |
| `--json-output` | explicit JSON sidecar path |
| `--in-toto` | path to an exported in-toto attestation, cited by content digest |
| `--in-toto-ref` | literal attestation reference string (redacted before it is emitted) |
| `--fail-on-validation` | exit `1` when validation failures (failed Bazel targets) are present |

## Gate it BEFORE you post — the sharing boundary

The exporter self-redacts, but the projection/redaction layer is the **sharing
boundary**: never post an artifact that has not cleared `nlfr redact --check`. A
leak here is the [#71 class](../reference/cli.md#redact) — a raw secret or
absolute path landing in a public PR comment.

```bash
# Gate BOTH artifacts; exit 1 on any finding — post nothing on failure.
nlfr redact --check pr-comment.md
nlfr redact --check pr-comment.json
```

The `--compact` wrapper script does this automatically and exits `3` if the gate
finds a leak.

## Post it to the PR

```bash
# After the redact gate passes:
gh pr comment "$PR_NUMBER" --body-file pr-comment.md
```

Or via the REST API directly:

```bash
gh api "repos/$GITHUB_REPOSITORY/issues/$PR_NUMBER/comments" \
  -f body="$(cat pr-comment.md)"
```

## Attach the JSON sidecar as a CI artifact

```yaml
# GitHub Actions — after the redact gate passes.
- name: Upload proof-comment JSON
  uses: actions/upload-artifact@v4
  with:
    name: nlfr-proof-comment
    path: pr-comment.json
```

## End-to-end in one CI job

```bash
set -euo pipefail
RUN_GROUP="pr-${PR_NUMBER}"

# 1. Render compact comment + JSON sidecar (self-redacted).
nlfr proof comment --run-group "$RUN_GROUP" --db "$DB" --output pr-comment.md

# 2. Redact gate — the sharing boundary. Post nothing if it fails.
nlfr redact --check pr-comment.md
nlfr redact --check pr-comment.json

# 3. Post the comment + keep the JSON as an artifact.
gh pr comment "$PR_NUMBER" --body-file pr-comment.md
```

Prefer the **packaged Action** to keep the redact gate un-droppable: set
`post-pr-comment: true` (see
[CI integration § optional PR comment](ci-integration.md#optional-post-the-compact-proof-comment-to-the-pr)).

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | rendered; with `--fail-on-validation`, no validation failures |
| `1` | with `--fail-on-validation`: rendered, but validation failures were present |
| `2` | missing database or CLI error |

## Related

- [CI integration with the redact-gate](ci-integration.md)
- [Attach proof to a PR (verbose per-block export)](attach-proof-to-pr.md)
- [Export an in-toto attestation](export-in-toto-attestation.md)
- [Proof samples hub](../../proof-samples/README.md)
