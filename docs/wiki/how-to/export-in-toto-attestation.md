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

```bash
# Unsigned, DSSE-ready in-toto Statement (default output is stdout)
uv run nlfr proof export \
  --db data/record-proof/nlfr.sqlite \
  --run-group latest \
  --format in-toto \
  --output out/proof.intoto.json
```

`--format json` (default) and `--format markdown` are unchanged. The `in-toto`
output is **deterministic**: two exports of the same database are byte-identical
(stable key ordering, and no export-time wall-clock timestamps beyond what the
recorded evidence already carries).

## Sign it externally (Sigstore / cosign)

NLFR deliberately stops at the bare Statement so you can wrap and sign it with the
tooling you already trust. The commands below use **external tooling**
([Sigstore cosign](https://docs.sigstore.dev/)); NLFR neither ships nor wraps them.

```bash
# External tooling — install cosign yourself.
# Keyless (Sigstore OIDC) signing of the NLFR Statement as a DSSE attestation over a subject file:
cosign attest-blob \
  --predicate out/proof.intoto.json \
  --type https://github.com/heyitsalec/nativelink-agent-flight-recorder/attestation/proof-packet/v1 \
  --bundle out/proof.intoto.bundle.json \
  path/to/one/subject-artifact

# Verify the resulting bundle (again, external tooling):
cosign verify-blob-attestation \
  --bundle out/proof.intoto.bundle.json \
  --type https://github.com/heyitsalec/nativelink-agent-flight-recorder/attestation/proof-packet/v1 \
  --certificate-identity-regexp '.*' \
  --certificate-oidc-issuer-regexp '.*' \
  path/to/one/subject-artifact
```

> The exact `cosign` flags depend on your cosign version and signing policy. Treat
> the above as a shape, not a copy-paste contract — the load-bearing part is that the
> NLFR Statement is a standard DSSE-ready predicate your signer already understands.

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

- [Attach proof to a PR](attach-proof-to-pr.md)
- [Export and compare run groups](export-and-compare-run-groups.md)
- [Truth labels reference](../reference/truth-labels.md)
