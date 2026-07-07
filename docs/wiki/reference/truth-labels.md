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

## Agent provenance class (`provenance_class`)

The agent leg of a bounded-change record carries a `provenance_class` **in addition
to** its four truth labels. It records *how the model attribution was established*,
which is orthogonal to `source_kind` (how the value entered the system):

| `provenance_class` | Established by | Model label is |
|--------------------|----------------|----------------|
| `operator_asserted_v1` | Operator `--model` + hashed prompt; no server verification | An operator claim |
| `stub_receipt_v1` | A deterministic (non-live) `nlfr.agent_receipt.v1` receipt | Simulated (`simulated_v1` agent leg) |
| `receipt_verified_v1` | A live `nlfr agent-invoke` receipt pinning the server-resolved model id, session id, and `response_sha256` | Server-verified |

`operator_asserted_v1` proves only that the recorded bytes changed (the
`patch_applied` flag is **derived**, never asserted — see observation modes below)
and that the operator asserted this model over this prompt hash — **not** that the
named model authored the edit. The [Cursor adapter](../../../adapters/cursor/README.md)
path tops out at `operator_asserted_v1` because `record-agent-change.sh` cannot
attach a receipt; `receipt_verified_v1` requires `nlfr agent-invoke`.

### Change observation modes (what `changed` / `patch_applied` is derived against)

A bounded change is only as honest as what the recorder could **observe**. Each
per-path entry in the change block records `changed_basis`:

| `changed_basis` | When | `changed` derived from | Note |
|-----------------|------|------------------------|------|
| `git_baseline` | Tracked path in a git workspace; the adapter captured the pre-edit bytes from `git show <ref>:<path>`. **Takes priority for every tracked path** — including edits made inside `--command`. | `baseline_sha256 != after_sha256` | Verifiable evidence (git object store); `baseline_source` carries `{kind: git_head, commit, ref}` and the commit-pinned ref is added to `evidence_refs`. Attests **"differs from the baseline ref"** — works even when the edit landed *before* recording. |
| `recorder_window` | **Untracked or non-git path** (no baseline available), or a supplied baseline that was refused (see below). | `before_sha256 != after_sha256` | The recorder's own before/after sample — only observes an edit made **inside** `--command`. |

**Sidecar baselines are re-verified, not trusted.** `--provenance-sidecar` is a
public interface, so every supplied `git_baseline` is re-checked against the
workspace git object store at record time (`git show <commit>:<path>` recomputed
and hashed here). A forged or stale `baseline_sha256`, or a baseline whose
commit/object cannot be resolved in this workspace, is **refused**: that path
falls back to `recorder_window` with an explicit note (`sidecar git_baseline did
not match …` or `baseline unverifiable in this workspace`) **and a stderr
warning**. The conflict is recorded honestly; the run is never hard-failed.

**Commit-before-record is flagged, not silently passed.** Under `git_baseline`,
when the baseline **equals** `after` the recorder cannot distinguish a genuine
no-op from a change already **committed before recording began** (HEAD moved past
the edit). It records `changed=false` with an explicit note naming the commit
**and a stderr warning** pointing at `--baseline-ref` — pass the true pre-edit ref
(e.g. `HEAD~1` or a commit sha) to attest a committed change.

When there is **no** git baseline and `before == after` (both non-null), the file
was already at its final state when recording began: the change is **not
observable**. This is recorded as `changed=false` with an explicit note **and a
stderr warning** — never a silent false (GitHub issue #52). The git baseline is
collectable git-object evidence and is labeled as such; it is never conflated with
the recorder's own observation window.

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
| `local_present` | unchanged (e.g. `collectable_v1`) | `medium` — the artifact is present but its digest was **not** cross-checked: a file with a non-recomputable-SHA-256 declared digest, a symlink output whose target exists (symlinks declare no digest), or inline bytes with a non-SHA-256 declared digest |
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

### Symlink and inline-content File entries

A Bazel BEP `File` populates exactly one of `uri`, `symlinkTargetPath`, or inline
`contents` (its `file` oneof). NLFR records all three rather than dropping the
non-`uri` shapes:

- A **symlink** output carries no digest to recompute. Presence comes from an
  existence probe of the resolved target — `local_present` when the target is on
  disk, `missing` when a resolvable target is absent — with `digest_verified = null`
  and a note. NLFR never fabricates a verified digest for a symlink.
- **Inline** `contents` (base64 in proto3 JSON) are hashed directly from the BEP
  with no filesystem access: a matching declared SHA-256 verifies (`local_verified`,
  `high`), a wrong one downgrades (`local_mismatch`), and a non-SHA-256 declared
  digest records `local_present` without cross-checking.

The proof packet surfaces a rollup at `summary.artifact_verification` and in the
`artifact_verification` block metrics: `verified_count`, `present_unverified`,
`mismatched`, `missing`, `unverified_remote`, `total`. `present_unverified` counts
`local_present` references (present but digest not cross-checked — see the
`local_present` row above).

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
