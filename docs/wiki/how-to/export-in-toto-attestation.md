# How-to: export an in-toto attestation from a proof packet

**Quadrant:** How-to · **Audience:** operators wiring NLFR evidence into a supply-chain stack
**Issue:** #26 — in-toto Statement export for proof packets

Export a proof packet as an **unsigned, DSSE-ready** [in-toto attestation
Statement](https://github.com/in-toto/attestation) (spec v1). The subjects are the
run group's SHA-256'd manifest artifacts; the predicate carries the truth-labeled
proof packet, the independent artifact-integrity verification summary, and
agent-receipt provenance (hashes only).

← [Wiki hub](../README.md) · [CLI reference](../reference/cli.md) · [proof packet contract](../reference/contracts/README.md)

## Positioning (read this first)

This attestation is **evidence that plugs into your existing safety case /
provenance stack** (SLSA / in-toto / Sigstore). It is the format A/V, robotics, and
other supply-chain stacks already accept — but NLFR emits the format, it does **not**
confer approval.

> NLFR does **not** sign this attestation and makes **no** claim of auditor
> acceptance or compliance certification. It is an honest record of exactly what was
> recorded, in a shape your existing tooling can verify and sign.

## What it is

An in-toto v1 Statement is a small JSON envelope:

```json
{
  "_type": "https://in-toto.io/Statement/v1",
  "subject": [
    { "name": "run.json", "digest": { "sha256": "…" } }
  ],
  "predicateType": "https://github.com/heyitsalec/nativelink-agent-flight-recorder/attestation/proof-packet/v1",
  "predicate": { "…the NLFR proof packet…" }
}
```

- **Subjects** are the run group's recorded manifest artifacts. Each `digest.sha256`
  is the value NLFR recorded **when it captured the artifact** — it is **not**
  recomputed at export time.
- **predicateType** is a URL under a namespace NLFR controls.
- **predicate** carries a stable subset of the proof packet: every proof block with
  its truth labels, the `artifact_verification` rollup + per-reference presence,
  agent-receipt provenance class (`receipt_verified_v1` / `stub_receipt_v1` /
  `operator_asserted_v1`), and run / run-group identity. The predicate schema is
  documented in [`contracts/in_toto_proof_predicate.v1.json`](../../../contracts/in_toto_proof_predicate.v1.json).

## Export it

This continues directly from **[record your own Bazel build](record-your-own-build.md)**.
That guide writes its SQLite spine to `data/nlfr-record/<run-group>/nlfr.sqlite` and
prints the run group it used (default `record-<UTC date>`, e.g. `record-2026-07-06`).
Point `--db` at that file and `--run-group` at that exact group — both values come
straight from the summary `nlfr record` prints:

```bash
# Unsigned, DSSE-ready in-toto Statement (default output is stdout).
uv run nlfr proof export \
  --db data/nlfr-record/record-2026-07-06/nlfr.sqlite \
  --run-group record-2026-07-06 \
  --format in-toto \
  --output out/proof.intoto.json
```

> **`--run-group` is a literal match, not "latest wins."** There is no `latest`
> resolver — the value must equal a run group actually recorded in that DB. If it
> matches nothing (or `--db` points at the wrong file), the export **fails hard**
> with a nonzero exit rather than emit a vacuous empty-subject attestation that
> cosign would happily sign and verify. The error lists the run groups that *are*
> present; you can also list them yourself any time:
>
> ```bash
> nlfr compare index --db data/nlfr-record/record-2026-07-06/nlfr.sqlite
> ```
>
> Automation that genuinely wants the empty envelope can pass
> `--allow-empty-subject` to downgrade the hard error to a warning.

`--format json` (default) and `--format markdown` are unchanged. The `in-toto`
output is **deterministic**: two exports of the same database are byte-identical
(stable key ordering, and no export-time wall-clock timestamps beyond what the
recorded evidence already carries).

## Sign it externally (Sigstore / cosign)

NLFR deliberately stops at the bare Statement so you can wrap and sign it with the
tooling you already trust. The commands below use **external tooling**
([Sigstore cosign](https://docs.sigstore.dev/)); NLFR neither ships nor wraps them.

The whole point is to sign **NLFR's own Statement, with NLFR's own recorded
subjects intact**. To do that you must give cosign the **complete** Statement,
not just its predicate. Modern cosign has a dedicated flag for exactly this:
`cosign attest-blob --statement <file>`, which wraps a pre-built in-toto Statement
in a DSSE envelope **without touching its subjects**.

> ⚠️ **Do not use `--predicate` for this.** `cosign attest-blob --predicate <file>`
> treats the file as a *bare predicate* and computes the subject from a **positional
> blob argument** you pass — a local file that has nothing to do with NLFR's
> recorded artifacts. The result is a DSSE whose single subject is that random
> local file and whose predicate is NLFR's **entire Statement double-nested inside
> it**. None of NLFR's recorded subjects survive, and it fails this export's own
> predicate contract. Use `--statement`, shown below.

This flag requires a cosign new enough to support it (verified here with **cosign
v3.1.1**). Confirm yours does: `cosign attest-blob --help | grep -- --statement`.

```bash
# External tooling — install cosign yourself. Offline key pair for this example:
#   cosign generate-key-pair        # writes cosign.key / cosign.pub
# (Sign with a KMS/keyless signer instead per your policy — the load-bearing flag
# is --statement, which is signer-independent.)

PREDICATE_TYPE=https://github.com/heyitsalec/nativelink-agent-flight-recorder/attestation/proof-packet/v1

# Wrap NLFR's COMPLETE Statement (subjects intact) in a signed DSSE bundle:
cosign attest-blob \
  --statement out/proof.intoto.json \
  --key cosign.key \
  --bundle out/proof.intoto.bundle.json

# Verify the signature over the bundle (offline public key). --check-claims=false
# verifies the envelope/signature without needing the subject bytes on disk:
cosign verify-blob-attestation \
  --key cosign.pub \
  --type "$PREDICATE_TYPE" \
  --bundle out/proof.intoto.bundle.json \
  --check-claims=false

# Full claims check: also prove a recorded subject's bytes match its digest by
# passing that artifact file positionally (its sha256 must equal a subject digest):
cosign verify-blob-attestation \
  --key cosign.pub \
  --type "$PREDICATE_TYPE" \
  --bundle out/proof.intoto.bundle.json \
  path/to/recorded/artifact
```

Both commands above print `Verified OK` on success. Decoding the resulting DSSE
payload (`.dsseEnvelope.payload`, base64) yields **NLFR's Statement byte-for-byte**
— identical `_type`, `predicateType`, and `subject[]` — which is exactly what a
downstream verifier expects.

> The exact signer configuration (local key vs. KMS vs. keyless OIDC) depends on
> your policy; swap `--key cosign.key` for your signer. The load-bearing,
> non-negotiable part is `--statement` (not `--predicate`): it is what keeps NLFR's
> recorded subjects in the signed envelope.

## Honest limits

- **Unsigned by NLFR.** The Statement carries no signature. Add one with your own
  signer (e.g. `cosign attest-blob`) if your stack requires it.
- **Digests come from recorded evidence.** Every subject `sha256` is the digest NLFR
  recorded at capture time; nothing is re-hashed at export. If the bytes were never
  recorded, they are not a subject.
- **Failing evidence is surfaced, not hidden.** If the run's artifact verification
  found `local_mismatch` or `missing` references, those counts appear in
  `predicate.artifact_verification.summary` and per-reference in `references[]`. An
  attestation over failing evidence is still an **honest attestation of what was
  recorded** — NLFR does not quietly drop contradicted or absent artifacts to make
  the packet look clean.
- **No approval is implied.** See the positioning note above.

## Related

- [Record your own Bazel build](record-your-own-build.md) — produces the `--db` and `--run-group` this guide consumes
- [Attach proof to a PR](attach-proof-to-pr.md)
- [Export and compare run groups](export-and-compare-run-groups.md)
- [Truth labels reference](../reference/truth-labels.md)
