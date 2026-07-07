# Vendored REAPI proto subset (provenance)

These `.proto` files are **minimal, wire-compatible subsets** of the upstream
Remote Execution API and ByteStream API definitions. They exist so NLFR's
**optional** CAS probe (`pip install nativelink-agent-flight-recorder[reapi]`,
GitHub issue #81) can speak the two RPCs it needs —
`ContentAddressableStorage/FindMissingBlobs` and `ByteStream/Read` — with
protobuf message classes generated from reviewable sources, instead of either
hand-rolled wire encoding (rejected: unreviewable correctness risk) or ~10k
lines of generated code from the full API surface (rejected: unreviewable
volume).

Nothing in this directory is imported by the stdlib-only NLFR core. The
generated message modules live in `src/nlfr/reapi/_gen/` and are imported only
lazily, inside the probe module, when an operator explicitly requests remote
CAS verification.

## Subset claim (what a reviewer should check)

Each vendored file keeps the upstream `package`, message names, field names,
field numbers, and field types **verbatim**. Protobuf wire compatibility
depends only on field numbers and types, so servers built against the full
upstream API interoperate with these messages unchanged. Everything else —
service definitions, all other messages, and their transitive imports
(`google/api/annotations.proto`, `google/longrunning/operations.proto`,
`google/protobuf/*.proto`, `google/rpc/status.proto`, semver) — is removed.
The two RPC method paths are spelled explicitly in
`src/nlfr/reapi/probe.py` and invoked through gRPC's generic method API, so no
service stubs are vendored or generated.

To re-verify the subset: fetch the pinned upstream files below, and diff the
kept messages against the vendored files — they must match verbatim apart from
the `NLFR VENDORED SUBSET` header comment and removed content.

## Files

### `build/bazel/remote/execution/v2/remote_execution.proto`

- **Upstream repo:** <https://github.com/bazelbuild/remote-apis>
- **Upstream path:** `build/bazel/remote/execution/v2/remote_execution.proto`
- **Pinned commit:** `becdd8f9ff811df88a22d3eadd6341753d51d167` (branch `main`)
- **Retrieved:** 2026-07-07
- **Upstream file SHA-256 (full original, 2516 lines):**
  `f0b237af779fd1de3a9a3a851915a09de3288538856bc5f5199701e0030cb70d`
- **Vendored subset SHA-256:**
  `7c634aee1e183c94424ead66348e647b95698433f2e6f01687aed248aa2bc5c5`
- **Kept messages:** `Digest`, `DigestFunction`, `FindMissingBlobsRequest`,
  `FindMissingBlobsResponse`
- **License:** Apache-2.0 (The Bazel Authors) — header retained in the file,
  full text in [`LICENSE`](LICENSE).

### `google/bytestream/bytestream.proto`

- **Upstream repo:** <https://github.com/googleapis/googleapis>
- **Upstream path:** `google/bytestream/bytestream.proto`
- **Pinned commit:** `af2513fa2dc3b1fb9992faaf900807f856d35990` (branch `master`)
- **Retrieved:** 2026-07-07
- **Upstream file SHA-256 (full original, 178 lines):**
  `961b833f35f4bdc51df4bca017cffdba299893e89762bf8041465560106dd3d6`
- **Vendored subset SHA-256:**
  `cc955564c9d26b601bcba7f2363ad1520190fcf5063fe9a5bd75173c7a1e2ffc`
- **Kept messages:** `ReadRequest`, `ReadResponse`
- **License:** Apache-2.0 (Google LLC) — header retained in the file, full text
  in [`LICENSE`](LICENSE).

## Generated code

`scripts/regen-reapi-stubs.sh` generates the committed message modules under
`src/nlfr/reapi/_gen/` from these protos using pinned `grpcio-tools==1.62.3`
(protobuf 4.25.x gencode — deliberately pre-runtime-version-gate so the stubs
load on every protobuf runtime from 4.25 onward, verified against 7.x in CI;
see the script header before bumping). Generation happens **only** via that
script, never at build, install, or import time. The generated modules'
SHA-256s at the time of vendoring:

- `src/nlfr/reapi/_gen/build/bazel/remote/execution/v2/remote_execution_pb2.py`
  `c7c05b5125b43f74c38790c2ff260013d11800cdc1123bd3f462bbbbed9b6cad`
- `src/nlfr/reapi/_gen/google/bytestream/bytestream_pb2.py`
  `7493c59ade808471169b22c186e5dbe4b2a2358e09c4266435c543e351975e4a`

## Known caveat: descriptor-pool symbol collision

The vendored subsets register upstream-canonical symbol names (e.g.
`build.bazel.remote.execution.v2.Digest`) in the protobuf default descriptor
pool. If another library in the **same Python process** loads full REAPI
Python bindings, the pool will reject the duplicate registration and the NLFR
probe import fails with a protobuf `TypeError`. NLFR's probe treats any import
failure honestly (the CLI refuses `--cas-endpoint` with an explanatory error;
nothing is fabricated). This is an accepted trade-off for keeping the vendored
names truthful to upstream; NLFR is a CLI and does not expect to share a
process with other REAPI stacks.
