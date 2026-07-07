# How-to: air-gapped / offline-wheel install

**Quadrant:** How-to · **Audience:** operators on air-gapped or egress-restricted hosts
**Track:** offline install — build the wheel once, transfer, run with no network

Install and run NLFR on a host with **no internet access**. Because NLFR is
stdlib-only with [zero runtime dependencies](../../SECURITY_MODEL.md#attack-surface-the-stdlib-only-zero-runtime-dependency-posture),
the whole install is a single `.whl` file — there is no dependency tree to
resolve or vendor. The fixture/demo loop, record, export, and redact paths then
run with **no network egress at all**, *provided the host already has a Python
`>=3.11` interpreter and your install tool present* — see
[Prerequisites](#prerequisites-on-the-air-gapped-host) below, because that
precondition is the one thing that can silently pull a toolchain over the wire if
it is not met.

← [Wiki hub](../README.md) · [Threat model](../../SECURITY_MODEL.md) · [Security policy](../../SECURITY.md)

## What needs a network, and what does not

| Path | Network? |
|------|----------|
| `nlfr` install from a transferred wheel | No — **but read the prerequisites**: `uv tool install`/`uvx` will fetch a CPython toolchain over the network if uv cannot see a `>=3.11` interpreter already on the host |
| `nlfr simulate` fixture / demo evidence loop | **No** — the demo scenarios and demo Bazel workspace ship *inside* the wheel |
| `nlfr record -- bazel …` capture, ingest, SQLite | **No** (Bazel/NativeLink are operator-supplied) |
| `nlfr graph/proof export`, projection JSON | **No** |
| `nlfr redact` (scrub before sharing) | **No** |
| Optional **real-NativeLink proof** (Nix toolchain) | Yes — reaches out |
| Optional **cosign / Sigstore** signing of an attestation | Yes — reaches out |

State it plainly: once the [prerequisites](#prerequisites-on-the-air-gapped-host)
are met, only the two optional, opt-in paths at the bottom touch the network.
Nothing on the record/export/redact path phones home — there is no telemetry and
no update check. The `nlfr simulate` row used to be the exception in practice
(the demo fixtures were not packaged and the command failed from a wheel); as of
the fix for [#94](https://github.com/heyitsalec/nativelink-agent-flight-recorder/issues/94)
the scenarios and a minimal demo workspace are bundled in the wheel, so the
fixture loop genuinely runs offline.

## Prerequisites on the air-gapped host

Verify **both** of these on the target *before* transferring or installing
anything. They are the difference between the "no network" claim being true and
the install silently reaching for the internet.

**1. A Python `>=3.11` interpreter is already present and visible to your install
tool.** Check it first:

```bash
python3 --version            # must report 3.11 or newer
command -v python3.11 || command -v python3   # note the exact path you will pin
```

Why this matters: NLFR requires Python `>=3.11`. If you run `uv tool install` /
`uvx` and uv **cannot** find a satisfying interpreter on the host, uv does **not**
fail — it tries to *download* a matching CPython build from
`releases.astral.sh` / `github.com`. On a truly air-gapped host those requests do
not refuse instantly; they hit uv's connect timeout and retry with backoff, so
the command can appear to hang for a couple of minutes before finally failing with
a "current Python version does not satisfy" message that never mentions the failed
network fetch. Older enterprise golden images (RHEL / Ubuntu-LTS) that predate
3.11 hit this. Pinning the interpreter and passing `--offline` (below) turns that
silent retry-hang into an immediate, honest error.

**2. Your install tool is already on the host.** Options A/B below assume `uv` is
already installed on the *target* (Step 1's "with uv installed" is about the
*connected build host*). If you cannot guarantee `uv` on the target, use the
`pip --no-index` path (Option C) — plain `pip` never auto-fetches interpreters, so
it fails fast and honestly on a too-old Python instead of reaching for the network.

## Step 1 — build the wheel on a connected host

On a machine **with** internet access and [uv](https://docs.astral.sh/uv/)
installed, clone the repo and build:

```bash
git clone https://github.com/heyitsalec/nativelink-agent-flight-recorder.git
cd nativelink-agent-flight-recorder
uv build
# -> dist/nativelink_agent_flight_recorder-<version>-py3-none-any.whl
# -> dist/nativelink_agent_flight_recorder-<version>.tar.gz  (sdist)
```

`uv build` needs no third-party runtime wheels for NLFR itself (there are none);
it only needs the build backend (`hatchling`), which uv fetches on the connected
host. The resulting `.whl` is self-contained and bundles the demo scenarios and a
minimal demo Bazel workspace under `nlfr/data/` (that is what makes the offline
`nlfr simulate` self-check in Step 4 work).

**Pin the version you built** so you can reproduce the same artifact later: record
the exact `nativelink-agent-flight-recorder` version (it is in the wheel filename)
and, if you care about byte-for-byte reproducibility, the `uv --version` you built
with.

## Step 2 — transfer the single wheel

Copy just the `.whl` to the air-gapped host by whatever approved channel you use
(removable media, internal artifact mirror, etc.):

```bash
# example — adapt to your transfer mechanism
scp dist/nativelink_agent_flight_recorder-*-py3-none-any.whl airgapped-host:/opt/nlfr/
```

There is nothing else to carry for the *runtime*: no `requirements.txt`, no
vendored dependencies, no lockfile resolution on the target. The wheel is the
whole runtime. (The interpreter and install tool from the
[prerequisites](#prerequisites-on-the-air-gapped-host) must already be on the
host — they are not part of the wheel.)

## Step 3 — install on the air-gapped host

Pick the option that matches what the target already has. In every case, pin the
present interpreter so nothing tries to fetch one.

**Option A — run ephemerally with `uvx`** (no install):

```bash
uvx --offline --python "$(command -v python3.11)" \
  --from /opt/nlfr/nativelink_agent_flight_recorder-*.whl nlfr --help
```

**Option B — install the tool** (persistent `nlfr` on PATH):

```bash
uv tool install --offline --python "$(command -v python3.11)" \
  /opt/nlfr/nativelink_agent_flight_recorder-*.whl
nlfr --help
```

The `--offline` flag makes the "no network" claim unconditional: uv is forbidden
from any egress, so a missing/too-old interpreter fails **immediately** (e.g.
`No interpreter found for Python … in search path`) instead of hanging on a
toolchain download. `--python "$(command -v python3.11)"` pins uv to the
interpreter you verified in the prerequisites (substitute the exact path you
noted — `python3.12`, `python3.13`, a full path, etc.). If you omit both, uv will
try to download CPython when it cannot find a match — the exact failure the
prerequisites section warns about.

**Option C — plain `pip`, no `uv` required** (recommended when you cannot
guarantee `uv` + a matching interpreter on the target):

```bash
python3.11 -m pip install --no-index \
  --find-links /opt/nlfr \
  nativelink-agent-flight-recorder
nlfr --help
```

`--no-index` proves the point: with zero runtime dependencies, pip never needs an
index to satisfy the install, and `--find-links /opt/nlfr` points it at the
directory holding the transferred wheel. Run it with the `>=3.11` interpreter
directly (`python3.11 -m pip …`); pip never auto-fetches an interpreter, so on a
too-old Python it fails fast and honestly
(`requires a different Python: 3.9.x not in '>=3.11'`) with **no** network attempt.

## Step 4 — verify the offline evidence loop

Two independent offline self-checks. Neither opens a socket.

**4a — packaged fixture/demo loop (no Bazel, no workspace of your own needed).**
This is the fastest "did my install actually work" check and it runs entirely
from the wheel's bundled fixtures:

```bash
# list the demo scenarios the wheel resolved (proves the fixtures shipped):
nlfr simulate --list
# -> scenarios resolved from <site-packages>/nlfr/data/scenarios (packaged)

# run one end-to-end without invoking Bazel/NativeLink:
nlfr simulate --scenario safe-leaf-change --skip-run --output-dir data/agent-sim
```

`--list` resolving from a `…/nlfr/data/scenarios (packaged)` path is proof the
scenarios came from the wheel, not a source checkout. The `--scenario … --skip-run`
run copies the bundled demo workspace, applies the scenario's deterministic patch,
and records agent→change provenance to local SQLite + JSON under `--output-dir` —
all offline, with no Bazel or NativeLink present. It proves the recorder, change
evidence, and provenance-writing paths work on this host before you point them at
a real build.

**4b — your own build (the real capture path).** Confirm the record → ingest →
export → redact loop works against *your* Bazel workspace with the network down.
Recorded evidence stays local under `data/` (gitignored) and the export is the
only artifact meant to leave the host — scrub it with `nlfr redact` before it does:

```bash
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
