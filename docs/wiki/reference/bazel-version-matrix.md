# Bazel parser version support (7.x / 9.x)

**Quadrant:** Reference · **Audience:** contributors, adopters running Bazel version ranges

> Renamed from `bep-version-matrix.md` (2026-07): the matrix now pins **three**
> evidence parsers — BEP, execution log, and profile — not BEP alone, so the
> file name reflects the broader Bazel-compat scope (GitHub issue #85).

## What is tested, honestly

NLFR's Bazel evidence parsers — `parse_bazel_bep` (`nlfr ingest --bep`),
`parse_bazel_execution_log` (`--execution-log`), and `parse_bazel_profile`
(`--profile`) — are **fixture-tested against Bazel 7.4.1 (7.x LTS) and 9.0.0
(current 9.x)**. The matrix fixtures are **proto-derived, populator-verified**:
their JSON shapes come from Bazel's own protobuf definitions **and the Java that
populates them** at each release tag, not from a live build. The populators
matter because a deprecated proto field can still be emitted on every build —
only the Java that sets it says whether it is. See
[`tests/fixtures/bazel/matrix/README.md`](../../../tests/fixtures/bazel/matrix/README.md)
for the per-fixture provenance table and exact source URLs.

This is **not** a claim that NLFR "supports all Bazel versions." It is the
honest, verifiable statement:

> The BEP, exec-log, and profile parsers are pinned by parametrized tests across
> proto-derived fixtures for Bazel 7.4.1 and 9.0.0. Coverage against evidence
> recorded by a *live* Bazel is env-gated and not exercised in CI on machines
> without Bazel.

The tested anchors are a single source of truth: `TESTED_BAZEL_VERSIONS` /
`TESTED_BAZEL_MAJORS` in
[`src/nlfr/ingest/bazel.py`](../../../src/nlfr/ingest/bazel.py), asserted to match
the fixture directories by
`tests/test_ingest_bazel_matrix.py::test_matrix_anchor_constant_matches_fixtures`.

## The three parsers across the range

### BEP (`build_event_stream.proto` + populators)

Equivalent semantics parse to **identical normalized ingest** across 7.4.1 and
9.0.0. The **one** genuine drift in the covered events: `BuildStarted` gains
`host` (field 10) and `user` (field 11) in 9.x (`BuildStartingEvent.java` calls
`setHost`/`setUser` at 9.0.0, neither at 7.4.1). NLFR ignores both, so ingest is
unchanged. `BuildFinished`, `TestSummary` and `TestResult` are byte-identical
across the range — the deprecated `overall_success` / `*_millis` /
`*_millis_epoch` fields are **still emitted in 9.x** alongside their
Timestamp/Duration successors, pinned as stability tripwires.

### Execution log (`spawn.proto` `SpawnExec`, JSON)

`nlfr ingest --execution-log` reads `--execution_log_json_file` output — a stream
of `SpawnExec` JSON objects. The `SpawnExec` message is **byte-identical across
7.4.1..9.0.0**: the only `spawn.proto` diffs at these tags are in `ExecLogEntry`,
the **compact**-log format (`--execution_log_compact_file`) NLFR does **not**
parse. The two exec-log fixtures are therefore byte-identical, asserted as a
stability tripwire (`test_exec_log_fixtures_are_byte_identical_across_versions`).
NLFR reads `targetLabel`, `mnemonic`, `runner`, `cacheHit`, and the `digest`
(`Digest{hash, sizeBytes, hashFunctionName}` object): a `remote cache hit` /
`cacheHit:true` spawn ingests as `remote_cache_hit` (`collectable_v1`/`high`); a
locally-run spawn ingests as `cache_miss`.

### Profile (JSON trace)

`nlfr ingest --profile` reads the `--profile` JSON trace. Real action events
carry `args: {target, mnemonic}` (the label is `args.target`, **not** `label`);
the parser also tolerantly accepts `label`/`targetLabel`. The **one** genuine
profile drift across the range: 9.0.0 adds an optional `args.configuration`
(`Profiler.java` `TaskData.writeTraceData` sets it at 9.0.0, not at 7.4.1). NLFR
ignores it, so normalized ingest is identical
(`test_profile_configuration_is_the_only_9x_drift`).

> **Honest boundary — the profile yields low-confidence evidence, and NLFR does
> not fabricate cache hits from it.** Real Bazel profile action events are named
> by their *action description* (e.g. "Testing //app:widget_test"), never
> "cache hit", and carry **no digest**. So `parse_bazel_profile` extracts the
> target + mnemonic and records `action_cache_observed` (`derived_v1`/`low`) — it
> never promotes a profile event to a `remote_cache_hit`. Use the exec log (or
> BEP) for cache-hit evidence; the profile contributes action observation, not
> cache-integrity claims.

## Out-of-range version warning (non-blocking)

Because production A/V fleets run version **ranges** (adoption blocker #6), NLFR
emits a **non-blocking "untested version" signal** when the local Bazel major is
outside the tested anchors:

- **`nlfr doctor`** shells out to `bazel version`, and reports a `bazel_version`
  block in `--json` (`detected`, `major`, `tested_versions`, `in_tested_range`,
  `warning`) plus a `[warn]` line on stderr. The warning **never** changes
  doctor's exit code or its `ok` field — those reflect the required tool checks
  only.
- **`nlfr record`** reads the version from the **ingested BEP's own**
  `started.buildToolVersion` (evidence-backed, not a separate probe) and surfaces
  `bazel_version` / `bazel_version_warning` in its JSON summary plus a stderr
  line. It never changes record's exit code (which mirrors Bazel's).

An **unknown** version (Bazel absent, a source/dev build with no `Build label`,
or a BEP with no `buildToolVersion`) stays **silent** — NLFR never fabricates an
"untested" claim from a version it could not read. Only a parseable major outside
`TESTED_BAZEL_MAJORS` warns.

## Which Bazel produced the evidence

`nlfr ingest` reads the `started` event's `buildToolVersion` and records it as a
`build_tool_identity_v1` proof block, surfaced in `summary.build_tool`:

```json
"build_tool": { "tool": "bazel", "versions": ["7.4.1"], "recorded": true }
```

When a BEP declares **no** build tool version, `recorded` is `false` and
`versions` is empty — reported as **unknown, never fabricated**. A run group
mixing versions lists every version observed
(`test_run_group_mixing_two_bazel_versions_lists_both`).

## Known parser boundary

`parse_bazel_bep` keys build outcome on `buildFinished.exitCode` (emitted by both
7.4.x and 9.x) and does **not** fall back to the deprecated `overall_success`
bool. A BEP carrying only `overallSuccess` (pre-`exit_code` Bazel, far older than
7.4) is recorded as exit **UNKNOWN**, not SUCCESS
(`test_build_finished_overall_success_only_is_exit_unknown`).

## Build Event Service (BES) streaming — scope decision: OUT (v1)

**Decision: BES streaming is explicitly OUT of scope for v1; NLFR ingests the
on-disk BEP file, not a BES gRPC stream.**

Bazel can *stream* build events to a Build Event Service
(`--bes_backend=grpc://…`, the `PublishBuildToolEventStream` RPC over
`build_event_stream.proto`) **in addition to** writing the local
`--build_event_json_file`. NLFR deliberately consumes the **local file**:

- **Evidence-integrity doctrine.** NLFR's trust root is a local, hashed,
  immutable artifact on the operator's own host (see
  [threat model](../../SECURITY_MODEL.md)). A BES *listener* would make NLFR a
  network service receiving a live event stream — a different, larger trust
  boundary (auth, backpressure, partial/duplicated streams, an open port) that
  contradicts the local-first, no-network-egress posture.
- **Same proto, same parsers.** BES carries the *same* `BuildEvent` messages the
  local file does, so the version-matrix work here (BEP shape stability across
  7.4.1..9.0.0) is exactly what a future BES path would reuse. Choosing "out"
  costs no evidence coverage today.
- **The honest capture path already exists.** `nlfr record` wraps a Bazel
  invocation and injects `--build_event_json_file`, capturing the complete BEP
  locally without a service. That is the supported, in-scope capture surface.

If a future adopter needs live BES capture (e.g. events that never touch disk),
that is a **new** networked-ingest workstream with its own threat-model review —
tracked separately, not folded into the parser matrix.

## Regenerating from a live Bazel (tier c)

On a machine with `bazelisk`, record real evidence (tier-c, `collectable`) with:

```
NLFR_RUN_BEP_MATRIX_LIVE=1 uv run pytest tests/test_ingest_bazel_matrix.py -k live
```

Without that env gate and `bazelisk` on `PATH`, the live hook is skipped and the
proto-derived fixtures are the tested coverage.

> **Deferred (this PR):** a live Bazel **9.x** CI leg (issue #85 item 2) is not
> added here — it would touch the blocking `nlfr-proof.yml`, owned by a
> concurrent CI change. The in-repo live hook above is the honest live path until
> that leg lands; hosted CI runs the proto-derived fixtures.

## Related

- [Truth labels reference](truth-labels.md)
- [Threat model](../../SECURITY_MODEL.md)
- [Matrix fixture provenance](../../../tests/fixtures/bazel/matrix/README.md)
