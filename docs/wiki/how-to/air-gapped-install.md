# How-to: air-gapped / offline-wheel install

**Quadrant:** How-to · **Audience:** operators on air-gapped or egress-restricted hosts
**Track:** offline install — build the wheel once, transfer, run with no network

Install and run NLFR on a host with **no internet access**. Because NLFR is
stdlib-only with [zero runtime dependencies](../../SECURITY_MODEL.md#attack-surface-the-stdlib-only-zero-runtime-dependency-posture),
the whole install is a single `.whl` file — there is no dependency tree to
resolve or vendor. The fixture, record, export, and redact paths then run with
**no network egress at all**.

← [Wiki hub](../README.md) · [Threat model](../../SECURITY_MODEL.md) · [Security policy](../../SECURITY.md)

## What needs a network, and what does not

| Path | Network? |
|------|----------|
| `nlfr` install from a transferred wheel | No (wheel already built) |
| `nlfr` fixture / demo evidence loop | **No** |
| `nlfr record -- bazel …` capture, ingest, SQLite | **No** (Bazel/NativeLink are operator-supplied) |
| `nlfr graph/proof export`, projection JSON | **No** |
| `nlfr redact` (scrub before sharing) | **No** |
| Optional **real-NativeLink proof** (Nix toolchain) | Yes — reaches out |
| Optional **cosign / Sigstore** signing of an attestation | Yes — reaches out |

State it plainly: only the two optional, opt-in paths above touch the network.
Nothing on the record/export/redact path phones home — there is no telemetry and
no update check.

## Step 1 — build the wheel on a connected host

On a machine **with** internet access and [uv](https://docs.astral.sh/uv/)
installed, from a clone of the repo:

```bash
uv build
# -> dist/nativelink_agent_flight_recorder-<version>-py3-none-any.whl
# -> dist/nativelink_agent_flight_recorder-<version>.tar.gz  (sdist)
```

`uv build` needs no third-party runtime wheels for NLFR itself (there are none);
it only needs the build backend (`hatchling`), which uv fetches on the connected
host. The resulting `.whl` is self-contained.

## Step 2 — transfer the single wheel

Copy just the `.whl` to the air-gapped host by whatever approved channel you use
(removable media, internal artifact mirror, etc.):

```bash
# example — adapt to your transfer mechanism
scp dist/nativelink_agent_flight_recorder-*-py3-none-any.whl airgapped-host:/opt/nlfr/
```

There is nothing else to carry: no `requirements.txt`, no vendored
dependencies, no lockfile resolution on the target. The wheel is the whole
runtime.

## Step 3 — run on the air-gapped host

You need a Python `>=3.11` interpreter on the target (CPython stdlib is the only
runtime trust root). Then either run the wheel ephemerally or install the tool.

**Option A — run ephemerally with `uvx`** (no install, no network):

```bash
uvx --from /opt/nlfr/nativelink_agent_flight_recorder-*.whl nlfr --help
uvx --from /opt/nlfr/nativelink_agent_flight_recorder-*.whl nlfr record -- bazel test //your:target
```

**Option B — install the tool** (persistent `nlfr` on PATH, no network):

```bash
uv tool install /opt/nlfr/nativelink_agent_flight_recorder-*.whl
nlfr --help
```

If you do not have `uv` on the target, plain `pip` works too, since there are no
dependencies to resolve:

```bash
python3 -m pip install --no-index /opt/nlfr/nativelink_agent_flight_recorder-*.whl
```

`--no-index` proves the point: with zero runtime dependencies, pip never needs
an index to satisfy the install.

## Step 4 — verify the offline evidence loop

Confirm the record → ingest → export → redact loop works with the network down.
Recorded evidence stays local under `data/` (gitignored) and the export is the
only artifact meant to leave the host — scrub it with `nlfr redact` before it
does:

```bash
# fixture/demo loop needs nothing external:
nlfr record --run-group airgap-smoke -- bazel test //your:target
nlfr graph export --run-group airgap-smoke
nlfr proof export --run-group airgap-smoke
nlfr redact --check data/nlfr-record/airgap-smoke/projections
```

None of these commands open a socket. The only reason to re-connect is the
**optional** real-NativeLink (Nix) proof or **optional** cosign signing of an
exported in-toto attestation — both explicitly opt-in.

## Related

- [Threat model](../../SECURITY_MODEL.md) — trust boundaries, no-egress recording path
- [Security policy](../../SECURITY.md) — supported versions, reporting a vulnerability
- [Export an in-toto attestation](export-in-toto-attestation.md) — the unsigned Statement you may later sign externally
- [Record your own Bazel build](record-your-own-build.md) — the capture path this runs offline
