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

### Redaction pipeline (issue #29)

> **Defense-in-depth, not a guarantee.** This pipeline is *best-effort pattern
> matching.* It reliably catches credentials that carry a recognizable shape — a
> known prefix (`AKIA`, `ghp_`, `github_pat_`, `glpat-`, `xox…`), a structural
> marker (a PEM header, a `Bearer …` scheme, a `secret_access_key=…` /
> `"SecretAccessKey": …` assignment), or a credential-named JSON key. It
> **cannot** catch a *free-standing high-entropy secret* with no prefix and no
> contextual marker — e.g. a bare 40-char AWS secret access key pasted into
> narrative log text — because a context-free "high-entropy string" rule would
> false-positive over the SHA-1/SHA-256 digests and base64 payloads that fill
> NLFR evidence. Operators handling sensitive workspaces must treat published
> projections as *scrubbed on a best-effort basis*, not as *proven secret-free*,
> and should review evidence at the source rather than relying on regex
> redaction alone.

Every projection is scrubbed before it is committed to
`apps/canvas/public/projections/`. `scripts/redact-projection.py` (a thin CLI
over the stdlib-only [`nlfr.redaction`](../../../src/nlfr/redaction.py) module)
walks the JSON structure — string values **and** keys — and applies:

- **Home-path scrubbing** (legacy): `/Users/<name>` and `/home/<name>` collapse
  to `${HOME}`.
- **Secret detectors** (always on): `home_path`, `private_key_pem`,
  `aws_access_key_id`, `aws_secret_access_key`, `github_token` (classic
  `gh[pousr]_`), `github_pat` (fine-grained `github_pat_`), `gitlab_pat`,
  `slack_token`, `jwt`, `url_credentials`, `authorization_credential`. Matched
  spans become `[REDACTED:<detector>]`.
- **Path detector** `abs_path` (on by default): non-home absolute local paths
  and local `file:///` URIs (the class the graph/runway projectors scrub) become
  `[REDACTED:abs_path]/<basename>`; `/Users`/`/home` stay with `home_path`
  (`${HOME}`), and Bazel labels, relative paths, and remote URI authorities are
  never flagged.
- **PII tier**: `email` and `ipv4` are redacted by default (loopback and
  link-local addresses are **not** sensitive and are excluded — `grpc://127.0.0.1`
  is left intact). `hostname` is **opt-in** (`--hostname`): in NLFR evidence,
  FQDN shapes are indistinguishable from tool/file names
  (`record-agent-change.sh`, `receipt.v1`, `nlfr.ingest.worker`), so redacting
  them by default would block honest publishes rather than protect anything.

Two properties keep the detectors honest on NLFR's own corpus, which is full of
64-hex SHA-256 digests and 40-hex shapes:

- **No detector flags a bare hex digest.** `aws_secret_access_key` fires on a
  40-char base64-ish value only when it is under a credential-ish key *or*
  introduced by an in-text `secret_access_key=…` marker, and in both paths it
  rejects a value that is pure hex (upper- **or** lowercase) or all-digits — so
  it can never collide with a SHA-1/SHA-256 digest.
- **Bazel labels** (`//foo:bar`), external repos (`@repo//pkg:tgt`), and
  loopback endpoints are never flagged.

When any value is redacted inside an object carrying `redaction_state`, that
state is upgraded honestly: `safe` / `unknown` → `redacted`. `blocked` and an
existing `redacted` are never downgraded. A secret-shaped **key** is *reported*
but never rewritten (rewriting a key would break consumers) — it is a `--check`
failure, not a silent mutation.

**The `--check` gate.** `redact-projection.py --check INPUT.json` scans without
writing and exits non-zero on any finding, printing a masked report (detector,
JSON path, `[REDACTED:…]` excerpt — never the raw secret). `test_redaction.py`
runs this scan over every committed projection and proof sample as a permanent
CI property, so a leaked credential shape fails the build.

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
| `digest_verified` | `true`, `false`, `null` | `true` when the recomputed SHA-256 matched the BEP-declared digest; `false` on mismatch; `null` when no comparison was possible (missing file, unprobed remote URI, no declared digest, or a declared digest NLFR cannot prove is SHA-256) |
| `presence` | `local_verified`, `local_present`, `local_mismatch`, `missing`, `unverified_remote_reference`, `remote_verified`, `remote_present`, `remote_mismatch`, `remote_missing` | What NLFR could actually confirm about the bytes. The `remote_*` values require an injected CAS probe (issue #81 part A); with no probe a remote reference stays `unverified_remote_reference` |

Truth-label consequences (this feature only **adds** verification state — it never
weakens an existing honest claim):

| `presence` | `source_kind` | `confidence` |
|------------|---------------|--------------|
| `local_verified` | unchanged (e.g. `collectable_v1`) | `high` (or `medium` when BEP declared no digest to cross-check) |
| `local_present` | unchanged (e.g. `collectable_v1`) | `medium` — the artifact is present but its digest was **not** cross-checked: a file with a non-recomputable-SHA-256 declared digest, a symlink output whose target exists (symlinks declare no digest), or inline bytes with a non-SHA-256 declared digest |
| `local_mismatch` | downgraded (`collectable_v1` → `derived_v1`) | `low` |
| `missing` | downgraded (`collectable_v1` → `derived_v1`) | `low` |
| `unverified_remote_reference` | downgraded (`collectable_v1` → `derived_v1`) | `low` |
| `remote_verified` | unchanged (e.g. `collectable_v1`) | `high` — the CAS probe read the blob and its recomputed SHA-256 matched the BEP-declared digest (the only remote tier that keeps a collectable claim) |
| `remote_present` | unchanged (e.g. `collectable_v1`) | `medium` — the CAS reports the blob present but its bytes were **not** hash-checked (the probe read no digest, or the declared digest is not a recomputable SHA-256) |
| `remote_mismatch` | downgraded (`collectable_v1` → `derived_v1`) | `low` — the CAS bytes were read and their recomputed SHA-256 contradicts the declared digest |
| `remote_missing` | downgraded (`collectable_v1` → `derived_v1`) | `low` — the CAS confirms the blob is **absent** (the actual bazelbuild/bazel#23250 upload-failure mode; the strongest downgrade) |

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
It is the **no-probe default**: with no CAS probe supplied, a remote reference is
recorded exactly this way and is **never** promoted to a `collectable_v1` / `high`
presence claim.

### Remote verification via an injectable CAS probe (issue #81)

NLFR exposes an **optional, injectable** CAS probe on `parse_bazel_bep` /
`build_reference` (`cas_probe`). When a probe is supplied, a remote reference is
checked against the content-addressable store and earns an honest label that
mirrors the local `*` symmetry:

| `presence` | Probe verdict | Truth-label consequence |
|------------|---------------|-------------------------|
| `remote_verified` | present, and the recomputed SHA-256 matched the declared digest | kept `collectable_v1` / `high` — the only remote tier that stays collectable |
| `remote_present` | present, but bytes not hash-checked (no declared digest, a non-recomputable-SHA-256 declared digest, a blob over the probe's read limit, or a `compressed-blobs` resource) — the honest reason is appended to `verification_note` | unchanged / `medium` |
| `remote_mismatch` | read, but recomputed SHA-256 contradicts the declared digest | downgraded (`collectable_v1` → `derived_v1`) / `low` |
| `remote_missing` | the CAS confirms the blob is **absent** (the bazel#23250 failure mode) | downgraded / `low` — the strongest downgrade |

A probe that raises or returns no verdict falls back to
`unverified_remote_reference` — NLFR **never** fabricates a presence claim from a
failed probe.

**Part B is live**: NLFR ships the actual REAPI probe backend behind the optional
`[reapi]` extra (`pip install "nativelink-agent-flight-recorder[reapi]"`), wired
to `nlfr ingest --cas-endpoint grpc://host:port [--cas-instance NAME]
[--cas-read-limit BYTES]`. The probe checks presence with
`ContentAddressableStorage/FindMissingBlobs` and, for present blobs with a
recomputable-SHA-256 declared digest within the read limit, streams the bytes
via `ByteStream/Read` and recomputes the SHA-256 locally — NLFR compares what
**it** hashed, never the store's self-report. Each probed ingest also records a
`cas_probe_v1` proof block (endpoint, instance, read limit, per-outcome counts)
so packets state what was probed. Without the flag — or without the extra, or
when the CAS is unreachable — every remote reference keeps the honest
`unverified_remote_reference` downgrade, and no exported packet claims remote
CAS was checked. Operator guide, including what the probe deliberately does
**not** prove: [Verify remote CAS references](../how-to/verify-remote-cas.md).

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
`mismatched`, `missing`, `unverified_remote`, `total`, plus the additive
remote-verification counts `remote_verified`, `remote_present`, `remote_mismatch`,
and `remote_missing` (issue #81 part A — all `0` unless a CAS probe was injected).
`present_unverified` counts `local_present` references (present but digest not
cross-checked — see the `local_present` row above).

## Agent receipt provenance ladder (multi-CLI)

Agent legs carry a `provenance_class` that ranks how the model claim is backed:

| Class | Meaning |
|-------|---------|
| `receipt_verified_v1` | Parsed live agent-CLI receipt: `status == success` **and** a response SHA-256, a `session_id`, and exactly one server-resolved model. Model label comes from the CLI, not the operator. |
| `stub_receipt_v1` | Deterministic stub CLI (CI mechanics gate); `simulated_v1`, never live. |
| `operator_asserted_v1` | Operator-typed model claim with no receipt. |

Receipts are captured through a per-CLI parser registry in
[`agent_receipt.py`](../../../src/nlfr/agent_receipt.py) (`CLI_PARSERS`): each
CLI normalizes its own `--output-format json` shape onto one internal receipt
shape, so the verified-tier bar and privacy posture (`prompt_sha256` only, raw
prompt structurally rejected) are identical across CLIs. A receipt only earns
`success` when the bar is met; otherwise it is recorded honestly as an
`invalid_output` / `api_error` / blocker receipt — collected evidence of the
attempt that stays **below** the verified tier (`is_live_receipt` is false).

Supported CLIs and their evidence status:

| `--agent-cli` | Verified-tier status |
|---------------|----------------------|
| `claude` | Live-proven — the committed two-act run carries `receipt_verified_v1` Claude receipts. |
| `gemini` | Doc-derived from the official Gemini CLI `--output-format json` contract (`response` + `stats.models` + `session_id`, optional `error`) and **fixture-tested**. Live validation is env-gated (`NLFR_RUN_AGENT_LIVE_GEMINI=1` with the Gemini CLI on PATH) and pending a machine with that CLI — **not** yet live-proven. |
| `codex` | Empirically derived from real `codex exec --json` JSONL runs (codex-cli 0.144.1) and fixture-tested. That stream attests **no model id**, so real codex successes honestly degrade to `invalid_output` — below the verified tier — until codex surfaces the model on its stream (the parser auto-upgrades when it does). Sanitized-from-real fixtures; model-bearing fixtures are forward-compat only. |

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
