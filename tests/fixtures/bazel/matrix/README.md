# Bazel BEP version-matrix fixtures

These fixtures pin NLFR's Build Event Protocol parsers across the **Bazel 7.x LTS
line** and the **current 9.x line**. Production A/V fleets run version *ranges*
(adoption blocker #6), and BEP schema drift across majors was previously
untested: the parsers were exercised against a single pinned-Bazel fixture set.

Each subdirectory holds the **same logical build** — a passing `//app:widget_test`
`py_test` — emitted in that Bazel version's BEP shape. Parametrized tests
(`tests/test_ingest_bazel_matrix.py`) assert **identical normalized ingest**
where semantics are equivalent, and **explicit, documented differences** where
they are not.

## Provenance tiers (never blurred)

NLFR labels where every fixture came from, exactly as it labels every other
evidence source. The "Provenance" column below describes **how each fixture was
authored** — it is a provenance descriptor, not the ingest `source_kind` truth
label (that enum is `collectable_v1` / `derived_v1` / `simulated_v1` / `future` /
`unknown`; a test chooses one when it ingests a fixture). Three tiers exist for
BEP fixtures:

| Tier | What | Provenance (how authored) | Where |
| --- | --- | --- | --- |
| (a) existing committed fixtures | `tests/fixtures/bazel/bep.jsonl`, `bep-output-group.jsonl`, `execution-log.json`, `profile.json` | hand-authored (pre-matrix); generator Bazel version **not recorded** in repo history — treated as version-agnostic minimal shapes, **not** attributed to any release | `tests/fixtures/bazel/` |
| (b) **these** proto-derived matrix fixtures | `matrix/7.4.1/`, `matrix/9.0.0/` | **doc-derived** — shapes derived from Bazel's own `build_event_stream.proto` at the named release tag (the same doc-derived provenance discipline the packet calls out via the repo's receipt-fixture precedent) | `matrix/<version>/build.bep.jsonl` |
| (c) live-generated coverage | recorded by real `bazelisk` on a future machine | **live** — would ingest as `collectable_v1` | env-gated hook `test_live_bep_matrix_generation_hook`, skipped here |

These are tier (b): **doc-derived, not machine-recorded.** No real Bazel ran to
produce them (real Bazel is not reliably available in this environment). They are
faithful to the proto schema at each tag but make no `collectable_v1` claim of
their own — a test that ingests one chooses the `source_kind` it passes.

### Source of the schema (verbatim tags)

Derived from `src/main/java/com/google/devtools/build/lib/buildeventstream/proto/build_event_stream.proto`
at these tags in `github.com/bazelbuild/bazel`:

| Fixture dir | Bazel tag | Raw proto URL |
| --- | --- | --- |
| `matrix/7.4.1/` | `7.4.1` (7.x LTS) | `https://raw.githubusercontent.com/bazelbuild/bazel/7.4.1/src/main/java/com/google/devtools/build/lib/buildeventstream/proto/build_event_stream.proto` |
| `matrix/9.0.0/` | `9.0.0` (9.x) | `https://raw.githubusercontent.com/bazelbuild/bazel/9.0.0/src/main/java/com/google/devtools/build/lib/buildeventstream/proto/build_event_stream.proto` |

The demo workspace pins `.bazelversion` 7.4.1; the Nix environment historically
used the 9.x line. `9.0.0` is the fixed 9.x anchor here so the tag (and its proto)
is a stable, re-fetchable reference.

## Drift points covered (verified against the two protos, not assumed)

| Drift point | 7.4.1 | 9.0.0 | Parser behavior |
| --- | --- | --- | --- |
| `BuildStarted.build_tool_version` (field 3) | `"7.4.1"` | `"9.0.0"` | **surfaced** — `extract_bep_tool_version` reads it verbatim; recorded as a `build_tool_identity_v1` proof block and in `summary.build_tool` |
| `BuildStarted.host` / `.user` (fields 10, 11) | absent | present (**new in 9.x**) | ignored — extra started fields do not change normalized ingest |
| `BuildStarted.start_time_millis` (2, deprecated) vs `start_time` Timestamp (9) | emits `startTimeMillis` **and** `startTime` | emits `startTime` only | equivalent — NLFR does not fabricate a start; the deprecated↔Timestamp pair coexists in both protos |
| `File` `digest` / `length` / `pathPrefix` / `symlinkTargetPath` (5/6/4/7) | identical shape | identical shape | equivalent — same normalized `artifact_references` across versions |
| `namedSetOfFiles` → `File` indirection | same | same | equivalent — files harvested from `namedSetOfFiles.files` and `testResult.testActionOutput` |
| `TestResult.test_attempt_duration_millis` (3, deprecated) vs `test_attempt_duration` Duration (11) | `testAttemptDurationMillis` | `testAttemptDuration` | equivalent — status normalized identically; duration field shape ignored by v1 |
| `TestSummary` `first_start_time_millis` / `total_run_duration_millis` (deprecated) vs Timestamp/Duration | millis form | Timestamp/Duration form | tolerated — `testSummary` is not a parse source; extra shape ignored |
| `BuildFinished.exit_code` ExitCode{name,code} (3) vs deprecated `overall_success` (1) | emits `exitCode` **and** `overallSuccess` | emits `exitCode` only | keys on `exitCode` — SUCCESS → no failure in both; the deprecated `overall_success` bool is **not** used as a fallback (see documented limitation) |
| `BuildFinished.anomaly_report` (4) | absent | present (**new in 9.x**, itself deprecated) | ignored |

### Documented limitation (not a bug — an honest boundary)

NLFR's `parse_bazel_bep` reads `buildFinished.exitCode` (both 7.4.x and 9.x emit
it). It intentionally does **not** fall back to the long-deprecated
`overall_success` bool. A BEP that carries **only** `overallSuccess` (pre-`exit_code`
Bazel, far older than 7.4) would be recorded as exit **UNKNOWN**, not SUCCESS —
`tests/test_ingest_bazel_matrix.py::test_build_finished_overall_success_only_is_exit_unknown`
pins this behavior so the boundary is explicit rather than silent.

## Live regeneration (tier c)

To record *real* BEPs on a machine that has Bazel, run the tests with:

```
NLFR_RUN_BEP_MATRIX_LIVE=1 uv run pytest tests/test_ingest_bazel_matrix.py -k live
```

with `bazelisk` on `PATH`. Absent that, the live hook is **skipped** and these
proto-derived fixtures are the tested coverage — see the honest range statement
in `docs/wiki/reference/bep-version-matrix.md`.
