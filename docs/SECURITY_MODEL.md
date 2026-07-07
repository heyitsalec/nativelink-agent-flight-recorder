# NLFR threat model

**Quadrant:** Explanation · **Audience:** enterprise security reviewers, platform engineers, procurement
**Companion:** [SECURITY.md](../SECURITY.md) (reporting a vulnerability) · [docs hub](INDEX.md)

This page states NLFR's trust boundaries plainly and, in keeping with repo
doctrine, is careful about what it does **not** claim. NLFR produces *evidence
that plugs into your safety case* — it is not an auditor, a sandbox, or a
signing authority. Where a boundary is a known limitation rather than a
protection, this document says so and links the tracking issue.

## What NLFR is

A local-first, stdlib-only Python CLI that records Bazel / NativeLink build
evidence for AI-agent code changes into truth-labeled proof packets. It runs on
the operator's own host, writes to a local SQLite database plus local artifact
files, and exports a scrubbed **projection** that is the only thing meant to
leave the machine.

## Trust boundaries

```
        ┌─────────────────────────── operator's host (trusted) ───────────────────────────┐
        │                                                                                  │
  bazel/NativeLink ──► BEP (local file) ──► ingest ──► SQLite (data/, gitignored)          │
   (operator-owned)     │                    │            │                                │
                        │       independent digest        │                                │
                        │       verification here         │                                │
                        │       (bazel#23250)             ▼                                │
                        │                            projection (scrubbed)  ◄── sharing     │
                        │                                 │                     boundary    │
        └───────────────┼─────────────────────────────────┼──────────────────────────────┘
                        │                                 │
                 raw prompts NEVER                 optional in-toto attestation
                 enter storage —                   (operator-signed, external)
                 SHA-256 hashes only                       │
                                                    cosign / Sigstore (external)
```

Three boundaries matter:

1. **Recorded evidence is LOCAL.** The SQLite database and captured artifacts
   live under `data/` (per-run-group, e.g. `data/nlfr-record/<group>/nlfr.sqlite`).
   `data/` is **gitignored** and never committed. Nothing about recording
   reaches the network — see [No network egress](#no-network-egress-on-the-recordfixture-path).

2. **The PROJECTION layer is the sharing boundary.** The only artifact intended
   to leave the host is the exported projection JSON, and it passes through
   redaction (`src/nlfr/redaction.py`, `nlfr redact`) before sharing. Home paths
   collapse to `${HOME}`; absolute local paths collapse to
   `[REDACTED:abs_path]/<basename>`; recognizable-shape secrets (AWS keys,
   `ghp_`/`github_pat_` tokens, GitLab/Slack tokens, PEM keys, bearer creds,
   JWTs, URL userinfo) become `[REDACTED:<detector>]`. Every projected row also
   carries a `redaction_state` truth label (`safe` / `redacted` / `blocked` /
   `unknown`).

3. **Prompts never enter storage.** Raw prompt text is never written to SQLite
   or a projection — only its SHA-256 hash is. This is enforced structurally by
   `FORBIDDEN_PROMPT_KEYS` in `src/nlfr/agent_receipt.py` and guarded repo-wide
   by `tests/test_prompt_redaction_gate.py`.

### The recorder does not trust the build tool's self-reports

Bazel's Build Event Protocol can reference an artifact at a `bytestream://` URI
even when the cache upload actually *failed*
([bazelbuild/bazel#23250](https://github.com/bazelbuild/bazel/issues/23250)).
NLFR therefore performs **independent digest verification**
(`src/nlfr/ingest/verification.py`): for every artifact whose bytes are on disk
it recomputes the SHA-256 and compares it against the BEP-declared digest; a
mismatch or a missing file downgrades the truth label and records an explicit
note. It does not repeat BEP's file references on faith.

## Data flow

```
bazel → BEP (local file) → ingest → SQLite → projection (scrubbed)
                                                   → optional in-toto attestation (operator-signed)
```

1. A Bazel workload runs through a NativeLink-backed mode (operator-owned).
2. BEP is written to a **local file**; artifacts are captured immutably with
   SHA-256 hashes.
3. Ingest normalizes evidence into local **SQLite**, verifying digests it can.
4. A versioned **projection JSON** is exported and scrubbed at the sharing
   boundary.
5. Optionally, the operator exports an in-toto v1 Statement over the recorded
   artifacts and signs it **themselves** with cosign / Sigstore. NLFR emits an
   unsigned, DSSE-ready Statement; it never signs on the operator's behalf.

## No network egress on the record/fixture path

The fixture, record, export, and redact paths perform **no network I/O**. There
is no telemetry, no update check, and no phone-home. The only paths that reach
out are explicitly opt-in and operator-driven:

- the **optional real-NativeLink proof** (Nix toolchain), and
- **optional cosign / Sigstore signing** of an exported attestation.

See the [air-gapped install runbook](wiki/how-to/air-gapped-install.md) for how
to run the full evidence loop offline.

## What NLFR protects

- **Evidence integrity** — artifacts are captured with SHA-256 hashes and
  independently digest-verified against BEP's own claims (bazel#23250); truth
  labels (`source_kind` / `confidence` / `evidence_refs` / `redaction_state`)
  make the strength of every claim explicit rather than assumed.
- **Prompt privacy** — raw prompts never reach storage or a projection; only
  SHA-256 hashes are recorded, enforced structurally and by a repo-wide gate.
- **Path / secret redaction before sharing** — the projection layer scrubs home
  and absolute local paths and recognizable-shape credentials before anything is
  shared.

## What NLFR explicitly does NOT protect

Stating these plainly is part of the doctrine — NLFR provides *evidence that
plugs into your safety case*, never *auditor acceptance*.

- **It is not a sandbox.** NLFR does not isolate, contain, or constrain the
  agent or the build it records. If the recorded build can do something
  dangerous, NLFR records that it happened; it does not prevent it.
- **It does not vet the agent's code.** NLFR records *what ran* and *what
  changed*; it makes no judgment about whether the change is correct, safe, or
  free of vulnerabilities.
- **It does not sign.** NLFR emits an unsigned, DSSE-ready in-toto Statement.
  Signing is an **external, operator-owned** step (cosign / Sigstore). NLFR
  holds no keys and asserts no signature.
- **Remote-CAS references are downgraded, not verified.** References whose bytes
  live only in a remote CAS (`bytestream://` and other REAPI URIs) cannot be
  verified locally without a REAPI/CAS probe. In v1 they are labeled
  `unverified_remote_reference` and never promoted to a high-confidence presence
  claim. Verifying them instead of downgrading them is tracked in
  [#81](https://github.com/heyitsalec/nativelink-agent-flight-recorder/issues/81).
- **Redaction is best-effort pattern matching, not a guarantee.** It reliably
  catches credentials with a recognizable *shape* (a known prefix, a structural
  marker, or a credential-named key). It **cannot** catch a free-standing
  high-entropy secret with no prefix and no contextual marker — a context-free
  "high-entropy string" rule would false-positive over the SHA-1/SHA-256 digests
  and base64 payloads that fill NLFR's corpus. Treat published projections as
  *scrubbed on a best-effort basis*, not *proven secret-free*, and review
  evidence at the source when handling sensitive workspaces (see the scope note
  in `src/nlfr/redaction.py`).

## Attack surface: the stdlib-only, zero-runtime-dependency posture

NLFR declares **zero runtime dependencies** (`dependencies = []` in
`pyproject.toml`). This is a deliberate security posture, not an accident of
scope:

- **Nothing to compromise transitively.** There is no third-party runtime
  package tree — no transitive dependency can be typosquatted, hijacked, or
  shipped with a malicious post-install step, because there are none. The
  runtime trust root is **CPython's standard library plus the operator's own
  Bazel / NativeLink** — nothing else.
- **Auditable, not asserted.** The empty runtime set is machine-checked by
  `tests/test_stdlib_only_posture.py`, which fails the moment a runtime
  dependency is added, and is made explicit for reviewers by the non-blocking
  SBOM / dependency-audit CI job (`.github/workflows/sbom.yml`), which emits an
  SBOM and asserts the runtime dependency set is empty on every push.
- **Dev tooling is scoped and disclosed.** The only third-party packages are
  dev-time (`pytest`, `jsonschema` for contract enforcement), pinned in
  `[dependency-groups].dev` and covered by the SBOM audit. They are never
  imported by the shipped `nlfr` runtime.

To verify independently: read `project.dependencies` in `pyproject.toml`, run
`uv run pytest -q tests/test_stdlib_only_posture.py`, and inspect the SBOM
artifact produced by the `SBOM / dependency audit` workflow.
