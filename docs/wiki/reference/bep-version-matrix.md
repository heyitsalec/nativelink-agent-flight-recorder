# BEP parser version support (Bazel 7.x / 9.x)

## What is tested, honestly

NLFR's Build Event Protocol parsers (`nlfr ingest --bep`, and the
`parse_bazel_bep` / `parse_bazel_execution_log` / `parse_bazel_profile` parsers)
are **fixture-tested against BEP shapes from Bazel 7.4.x and 9.x**. The matrix
fixtures are **proto-derived**: their JSON shapes come from Bazel's own
`build_event_stream.proto` **and its Java populators** (`BuildStartingEvent`,
`BuildCompletingEvent`, `TestAttempt`, `TestSummary`) at the `7.4.1` and `9.0.0`
release tags, not from a live build. The populators matter because a deprecated
proto field can still be emitted on every build — only the Java that sets it says
whether it is. See `tests/fixtures/bazel/matrix/README.md` for the per-fixture
provenance table, the exact proto/Java source URLs, and the field-by-field diff.

This is **not** a claim that NLFR "supports all Bazel versions." It is the honest,
verifiable statement:

> The BEP parsers are pinned by parametrized tests across proto-derived fixtures
> for the Bazel 7.x LTS line (7.4.1) and the current 9.x line (9.0.0). Coverage
> against BEPs recorded by a *live* Bazel is env-gated and not exercised in CI on
> machines without Bazel.

Versions **between and around** 7.4.x and 9.0.0 are expected to parse because the
BEP shapes NLFR reads (`started`, `namedSetOfFiles`, `testResult`,
`targetCompleted`, `buildFinished.exitCode`) are stable across that window — but
that expectation is bounded by the two tested anchors, not proven for every
release.

## Why a range, not a point

Production A/V fleets run version **ranges** (adoption blocker #6). The demo
workspace pins `.bazelversion` 7.4.1; the Nix environment historically used the
9.x line. Testing a single pinned Bazel left cross-major BEP schema drift
untested. The matrix closes that: equivalent semantics are asserted **identical**
across 7.4.1 and 9.0.0, and the genuine differences are documented.

Verified against the primary sources, the diff across 7.4.1 → 9.0.0 is small: the
**one** genuine change in the covered events is that `BuildStarted` gains `host`
(field 10) and `user` (field 11) in 9.x. The `BuildFinished`, `TestSummary` and
`TestResult` blocks are byte-identical across the range — the deprecated
`overall_success`, `finish_time_millis`, `start_time_millis` and `*_millis` test
timing fields are **still emitted in 9.x** alongside their Timestamp/Duration
successors, so NLFR does not have to guess a shape per version. Those
non-differences are pinned as stability tripwires: if a future Bazel really drops
one, the test fails and a real drift row is added rather than assumed in advance.

## Which Bazel produced the evidence

`nlfr ingest` reads the `started` event's `buildToolVersion` (proto
`build_tool_version`) and records it as a `build_tool_identity_v1` proof block.
An exported proof packet surfaces it in `summary.build_tool`:

```json
"build_tool": { "tool": "bazel", "versions": ["7.4.1"], "recorded": true }
```

When a BEP declares **no** build tool version (older evidence, a non-Bazel BEP),
`recorded` is `false` and `versions` is empty — the version is reported as
**unknown, never fabricated**. A run group that mixes evidence from more than one
Bazel version lists every version observed — e.g. ingesting the 7.4.1 and 9.0.0
fixtures into one run group yields `versions: ["7.4.1", "9.0.0"]`, pinned by
`tests/test_ingest_bazel_matrix.py::test_run_group_mixing_two_bazel_versions_lists_both`.

## Known parser boundary

`parse_bazel_bep` keys build outcome on `buildFinished.exitCode`
(`ExitCode{name, code}`) — emitted by both 7.4.x and 9.x. It intentionally does
**not** fall back to the deprecated `overall_success` bool. A BEP that carries
only `overallSuccess` (pre-`exit_code` Bazel, far older than 7.4) is recorded as
exit **UNKNOWN**, not SUCCESS. This boundary is pinned by
`tests/test_ingest_bazel_matrix.py`.

## Regenerating from a live Bazel

On a machine with `bazelisk`, record real BEPs (tier-c, `collectable`) with:

```
NLFR_RUN_BEP_MATRIX_LIVE=1 uv run pytest tests/test_ingest_bazel_matrix.py -k live
```

Without that env gate and `bazelisk` on `PATH`, the live hook is skipped and the
proto-derived fixtures are the tested coverage.
