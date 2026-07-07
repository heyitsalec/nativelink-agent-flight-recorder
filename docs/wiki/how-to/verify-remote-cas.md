# How-to: verify remote CAS references (REAPI probe)

**Quadrant:** How-to · **Audience:** operators of remote-cache / remote-execution builds

By default NLFR downgrades every remote `bytestream://` reference to
`unverified_remote_reference`, because a BEP can reference a blob whose cache
upload actually **failed**
([bazelbuild/bazel#23250](https://github.com/bazelbuild/bazel/issues/23250)).
This guide turns on the optional REAPI probe (GitHub issue #81) so `nlfr
ingest` independently **confirms** each remote reference against a running CAS
— or honestly records that it could not.

## 1. Install the optional extra

```bash
pip install "nativelink-agent-flight-recorder[reapi]"
```

The core stays stdlib-only (`dependencies = []` — the security posture is
unchanged); the extra adds `grpcio` + `protobuf`, imported lazily and only when
you pass `--cas-endpoint`. Without the extra, `nlfr ingest` behaves exactly as
before — and if you pass `--cas-endpoint` anyway it **refuses with the install
command** rather than silently downgrading, because you asked for verification.

## 2. Probe during ingest

```bash
nlfr ingest ./evidence \
  --database data/nlfr/nlfr.sqlite \
  --cas-endpoint grpc://127.0.0.1:50051 \
  --cas-instance main
```

Flags:

| Flag | Meaning |
|------|---------|
| `--cas-endpoint` | The CAS to ask: `grpc://host:port` (plaintext) or `grpcs://host:port` (TLS). This — not the URI's authority — decides where NLFR probes. |
| `--cas-instance` | REAPI instance name (the NativeLink demo configs serve `main`). An instance segment embedded in a `bytestream://` URI takes precedence over this flag. |
| `--cas-read-limit` | Max blob size in bytes to stream for digest recomputation (default 64 MiB). Larger blobs are recorded present-but-not-hash-checked, never "verified". |

For the local NativeLink demo (`demo/nativelink/cache-only.json`), the endpoint
is `grpc://127.0.0.1:50051` and the instance is `main`.

## 3. What each label means

Per remote reference, the probe runs `FindMissingBlobs` (presence) and — when
the blob is present, the BEP declared a recomputable SHA-256, and the blob is
within the read limit — streams the bytes with `ByteStream/Read` and recomputes
the SHA-256 **locally**:

| `presence` | What NLFR proved | Labels |
|------------|------------------|--------|
| `remote_verified` | Blob read from the CAS; locally recomputed SHA-256 **matches** the BEP-declared digest | `collectable_v1` / `high` |
| `remote_present` | CAS reports the blob present; bytes not hash-checked (reason appended to the note: no declared digest, non-SHA-256 digest, over read limit, or `compressed-blobs`) | unchanged / `medium` |
| `remote_mismatch` | Blob read; recomputed SHA-256 **contradicts** the declared digest | `derived_v1` / `low` |
| `remote_missing` | CAS confirms the blob is **absent** — the bazel#23250 upload-failure mode | `derived_v1` / `low` |
| `unverified_remote_reference` | Probe reached no verdict (unreachable, timeout, unsupported URI) | `derived_v1` / `low` |

Every probed ingest also records a `cas_probe_v1` proof block — endpoint,
instance, read limit, and per-outcome counts — so an exported packet states
what was probed, not just the resulting labels. When the CAS is unreachable the
ingest still succeeds (evidence recorded honestly) and stderr carries a
prominent `CAS probe unreachable: N remote refs left unverified` summary.

## Honest boundaries (read before citing this in a safety case)

- **This verifies CAS content, not Bazel's behavior.** A `remote_verified`
  label proves the CAS *you named* holds bytes matching the BEP-declared
  digest at probe time. It does **not** prove Bazel uploaded them, fetched
  them, or used that store during the build.
- **Point-in-time, not durable.** The CAS may evict a blob after the probe;
  the label records what was true when `nlfr ingest` ran.
- **Read-limit ceiling.** Blobs over `--cas-read-limit` are presence-checked
  only (`remote_present`), with the reason in the verification note — raise the
  limit to hash-verify them.
- **No decompression.** `compressed-blobs` resources are presence-checked only
  in v1.
- **Unreachable never fabricates.** Timeouts, transport errors, and unsupported
  URI shapes yield `unverified_remote_reference` with a probe-attempted note —
  the same honest downgrade as running without a probe.

## Verifying the vendored gRPC surface

The probe's protobuf messages are generated from a minimal vendored proto
subset with pinned upstream provenance and checksums —
[third_party/reapi/README.md](../../../third_party/reapi/README.md) — and the
two RPC method paths are spelled explicitly in
[`src/nlfr/reapi/probe.py`](../../../src/nlfr/reapi/probe.py). CI proves the
extra end-to-end against a real in-process gRPC server
(`.github/workflows/reapi-probe.yml`); it does not spin a live NativeLink on
hosted runners, so probing a real deployment (step 2 above) is the operator's
end-to-end proof.

## Related

- [Truth labels reference](../reference/truth-labels.md) — the full label
  vocabulary and downgrade rules
- [Threat model](../../SECURITY_MODEL.md) — trust boundaries and the
  stdlib-only posture
