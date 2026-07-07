# Reference: truth labels

**Quadrant:** Reference · **Audience:** contributors, canvas authors, proof reviewers

Every projected node, edge, metric, and proof claim in NLFR carries four truth
fields. Docs, diagrams, and proof samples must show at least `source_kind` and
`confidence` when citing claims.

Canonical rule: [AGENTS.md](../../../AGENTS.md) · Product summary: [One pager](../../ONE_PAGER.md)

## Required fields

| Field | Values | Meaning |
|-------|--------|---------|
| `source_kind` | `collectable_v1`, `derived_v1`, `simulated_v1`, `future` | How the value entered the system |
| `confidence` | `high`, `medium`, `low`, `unknown` | Parser / projector confidence in the label |
| `evidence_refs` | string array | Stable refs (`run:{id}`, `artifact:{key}`, `run_group:{name}`) |
| `redaction_state` | `safe`, `redacted`, `blocked`, `unknown` | Privacy posture of the exported span |

## source_kind

| Value | Definition | Example |
|-------|------------|---------|
| `collectable_v1` | Captured from real process output or attached artifacts with SHA-256 | Bazel BEP, NativeLink stdout, `record-agent-change.sh` sidecar |
| `derived_v1` | Computed from collectable rows by projectors | Compare deltas (M9), canvas layout bindings |
| `simulated_v1` | Deterministic fixture or scenario with no live LLM | `nlfr simulate` demo scenarios |
| `future` | Reserved claim type; not promoted without parser + proof script | Scheduler assignment, queue time |

## confidence

Use `high` only when direct evidence and parsers match without ambiguity.
Use `medium` for probe-success with environment variance (e.g. LRE parity on linux).
Use `low` or `unknown` when blockers or partial captures apply.

## evidence_refs

Pointers only — not raw log bodies. Typical patterns:

- `run:{stable_run_id}`
- `run_group:{label}`
- `artifact:bazel-test.log`
- `proof_block:cache_economics`

Compare projections (M9) must reference **both** left and right run groups.

## redaction_state

| Value | When |
|-------|------|
| `safe` | Public-safe export |
| `redacted` | Path or span redacted (hashes, short excerpts) |
| `blocked` | Withheld — privacy or policy |
| `unknown` | Ingest could not classify |

Never export raw prompts, credentials, or full private logs. M8 stores
`prompt_sha256` + `model` only: [Cursor adapter](../../../adapters/cursor/README.md).

## Artifact verification (issue #25)

NLFR does not trust the build tool's self-reports. Every file the ingested BEP
references is independently checked: local bytes have their SHA-256 recomputed
and compared against the BEP-declared digest, and remote-only URIs are labeled
rather than promoted. Each `artifact_references` row (and each entry in the proof
packet's `artifact_verification` block payload) carries two extra fields on top
of the four truth labels:

| Field | Values | Meaning |
|-------|--------|---------|
| `digest_verified` | `true`, `false`, `null` | `true` when the recomputed SHA-256 matched the BEP-declared digest; `false` on mismatch; `null` when no local comparison was possible (missing file, remote URI, no declared digest, or a declared digest NLFR cannot prove is SHA-256) |
| `presence` | `local_verified`, `local_present`, `local_mismatch`, `missing`, `unverified_remote_reference` | What NLFR could actually confirm about the bytes |

Truth-label consequences (this feature only **adds** verification state — it never
weakens an existing honest claim):

| `presence` | `source_kind` | `confidence` |
|------------|---------------|--------------|
| `local_verified` | unchanged (e.g. `collectable_v1`) | `high` (or `medium` when BEP declared no digest to cross-check) |
| `local_present` | unchanged (e.g. `collectable_v1`) | `medium` — bytes are on disk, but the declared digest was **not** cross-checked because it is not a recomputable SHA-256 |
| `local_mismatch` | downgraded (`collectable_v1` → `derived_v1`) | `low` |
| `missing` | downgraded (`collectable_v1` → `derived_v1`) | `low` |
| `unverified_remote_reference` | downgraded (`collectable_v1` → `derived_v1`) | `low` |

A `derived_v1` label on a downgraded reference means **NLFR derived a contradicting
or unverifiable state from its own recomputation** — it is not the build tool's
self-report echoed back. The `artifact_verification` block's per-reference
`verification_note` carries the specifics (mismatch, missing file, or remote URI).

### Digest function is not assumed to be SHA-256

Bazel's `File.digest` is the hex of the **configured** `--digest_function` (a
startup flag). Remote-execution shops — NLFR's exact audience — may run a
non-default function (BLAKE3, SHA-512, …). NLFR only recomputes **SHA-256** in v1,
so it must never treat a non-SHA-256 digest as a failed SHA-256 comparison:

- If the BEP's `optionsDescription` / command line names a `--digest_function`
  that is not SHA-256, or the declared digest is not 64 hex chars (SHA-1 is 40,
  SHA-512 is 128, base64 shapes differ), NLFR **skips** the comparison:
  `presence = local_present`, `digest_verified = null`, label unchanged. No
  mismatch is fabricated and no honest `collectable_v1` / `high` claim is
  downgraded on algorithm uncertainty alone.
- A 64-hex digest is compared as SHA-256. If the BEP exposed the command line
  (SHA-256 named, or no override → Bazel's default), a mismatch is a real
  integrity signal and downgrades to `local_mismatch`. If the BEP exposed **no**
  command line, the mismatch still downgrades (a mismatch on the default function
  is overwhelmingly a real failure) but the `verification_note` records that the
  digest function could not be confirmed. (A 64-hex digest is also the length of
  SHA3-256; that theoretical collision is an accepted v1 risk.)

`unverified_remote_reference` exists because a BEP can reference an artifact at a
`bytestream://` URI even when the cache upload FAILED
([bazelbuild/bazel#23250](https://github.com/bazelbuild/bazel/issues/23250)).
A remote reference is **never** promoted to a `collectable_v1` / `high` presence
claim; verifying remote CAS via REAPI is a documented follow-up, not v1.

The proof packet surfaces a rollup at `summary.artifact_verification` and in the
`artifact_verification` block metrics: `verified_count`, `present_unverified`,
`mismatched`, `missing`, `unverified_remote`, `total`. `present_unverified` counts
`local_present` references (bytes on disk, digest not a recomputable SHA-256).

## Conditional claims (M7)

`worker_identity` is `collectable_v1` **only when**:

1. `nativelink.stdout.txt` is attached pre-ingest, and
2. M7 `worker_admin_stdout` parser regex matches admin lines.

Runs without stdout do not carry worker identity claims. Scheduler, queue, and
placement remain `future` / unsupported:
[future fleet claims](../../dags/future-fleet-claims.md).

## Compare claims (M9)

Compare metrics are `derived_v1`. They summarize proof blocks per run group —
they do not reconstruct a unified worker graph across runs.

## Review checklist

- [ ] Every doc diagram caption names `source_kind`
- [ ] Fixture paths labeled `simulated_v1` where applicable
- [ ] No fleet dashboard language without proof block citation
- [ ] Proof samples in [proof-samples](../../proof-samples/README.md) include labels

## Related

- [CLI reference](cli.md)
- [Proof scripts matrix](proof-scripts-matrix.md)
- [Projection-only canvas](../explanation/projection-only-canvas.md)
- [Architecture track](../../ARCHITECTURE_TRACK.md)
