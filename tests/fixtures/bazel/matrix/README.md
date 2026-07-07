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
| (b) **these** proto-derived matrix fixtures | `matrix/7.4.1/`, `matrix/9.0.0/` | **doc-derived** — shapes derived from Bazel's own `build_event_stream.proto` **and its Java populators** at the named release tag (the same doc-derived provenance discipline the packet calls out via the repo's receipt-fixture precedent) | `matrix/<version>/build.bep.jsonl` |
| (c) live-generated coverage | recorded by real `bazelisk` on a future machine | **live** — would ingest as `collectable_v1` | env-gated hook `test_live_bep_matrix_generation_hook`, skipped here |

These are tier (b): **doc-derived, not machine-recorded.** No real Bazel ran to
produce them (real Bazel is not reliably available in this environment). They are
faithful to **what each tag's populators actually emit** (not merely to the proto
schema — a deprecated field can exist in the `.proto` yet be emitted, or not, only
according to the Java that sets it), but make no `collectable_v1` claim of their
own — a test that ingests one chooses the `source_kind` it passes.

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

### Source of what is *emitted* (the Java populators)

The `.proto` declares which fields *may* appear; it cannot tell you which are
actually written — a `[deprecated = true]` field can still be set on every build,
or dropped, purely according to the Java that builds the proto. Each fixture event
was re-derived from the populator that emits it, read at **both** tags so the
7.4.1↔9.0.0 diff is verified, not assumed:

| BEP event | Java populator | Path (same at both tags) |
| --- | --- | --- |
| `started` (`BuildStarted`) | `BuildStartingEvent.asStreamProto` | `src/main/java/com/google/devtools/build/lib/buildtool/buildevent/BuildStartingEvent.java` |
| `finished` (`BuildFinished`) | `BuildCompletingEvent.asStreamProto` | `src/main/java/com/google/devtools/build/lib/buildeventstream/BuildCompletingEvent.java` |
| `testResult` (`TestResult`) | `TestAttempt.asTestResult` | `src/main/java/com/google/devtools/build/lib/analysis/test/TestAttempt.java` |
| `testSummary` (`TestSummary`) | `TestSummary.asStreamProto` | `src/main/java/com/google/devtools/build/lib/runtime/TestSummary.java` |

Raw form (swap `<tag>` for `7.4.1` or `9.0.0`):
`https://raw.githubusercontent.com/bazelbuild/bazel/<tag>/<path>`

What the populators show at both tags:

* `BuildStartingEvent` sets `startTimeMillis` (proto 2, deprecated) **and**
  `startTime` (proto 9) in **both** versions; 9.x additionally calls
  `setHost(...)`/`setUser(...)` (proto 10/11). That `host`/`user` addition is the
  **only** cross-version change in the `started` event.
* `BuildCompletingEvent` sets `overallSuccess` (1, deprecated), `exitCode` (3),
  `finishTimeMillis` (2, deprecated) and `finishTime` (5) in **both** versions,
  and calls `setAnomalyReport` in **neither** — so `anomaly_report` (proto 4) is
  a deprecated field present in both `.proto`s but emitted by neither build, and
  is therefore absent from both fixtures.
* `TestAttempt` and `TestSummary` each set **both** the deprecated `*_millis` /
  `*_millis_epoch` fields **and** their Timestamp/Duration successors in **both**
  versions.

## What actually changes across 7.4.1 → 9.0.0 (diff, not assumption)

The `BuildFinished`, `TestSummary` and `TestResult` message blocks are
**byte-identical** in `build_event_stream.proto` across 7.4.1..9.0.0, and the
populators (above) set the same fields in both. There is exactly **one** genuine
cross-version drift in the events these fixtures cover.

### The one genuine drift

| Drift point | 7.4.1 | 9.0.0 | Parser behavior |
| --- | --- | --- | --- |
| `BuildStarted.host` / `.user` (fields 10, 11) | **absent** | **present** — `setHost`/`setUser` added to the 9.x populator | ignored — extra started fields do not change normalized ingest; `test_started_host_user_are_the_only_9x_drift` pins that these are the *only* differing keys |

### Byte-stable across the range (asserted as stability tripwires, not drift)

If a future Bazel really drops one of these deprecated fields, the named test
fails — and *that* is when the matrix earns a new drift row. Until then, the
honest statement is: no drift here.

| Field / block | 7.4.1 | 9.0.0 | Emitted because | Pinned by |
| --- | --- | --- | --- | --- |
| `BuildStarted.build_tool_version` (3) | `"7.4.1"` | `"9.0.0"` | value differs (that is the point); shape identical | `extract_bep_tool_version` → `build_tool_identity_v1` proof block + `summary.build_tool` |
| `BuildStarted.start_time_millis` (2, deprecated) + `start_time` (9) | **both** emitted | **both** emitted | `BuildStartingEvent` sets both in both versions | `test_started_host_user_are_the_only_9x_drift` |
| `BuildFinished` = `{overall_success (1, deprecated), exit_code (3), finish_time_millis (2, deprecated), finish_time (5)}` | all 4 emitted | all 4 emitted | `BuildCompletingEvent` sets the same 4 in both | `test_build_finished_shape_is_byte_stable_across_versions` |
| `BuildFinished.anomaly_report` (4, deprecated) | absent | absent | `setAnomalyReport` called in **neither** populator | (absent from both fixtures) |
| `TestResult` `test_attempt_start_millis_epoch` (6) + `test_attempt_start` (10); `test_attempt_duration_millis` (3) + `test_attempt_duration` (11) | **both** forms | **both** forms | `TestAttempt` sets millis **and** Timestamp/Duration in both | `test_test_timing_fields_are_byte_stable_across_versions` |
| `TestSummary` `first_start_time_millis` (7)/`last_stop_time_millis` (8)/`total_run_duration_millis` (9) + Timestamp/Duration (13/14/12) | **both** forms | **both** forms | `TestSummary` sets millis **and** Timestamp/Duration in both | `test_test_timing_fields_are_byte_stable_across_versions` |
| `File` `digest`/`length`/`pathPrefix` (5/6/4); `namedSetOfFiles` → `File` indirection | identical | identical | proto blocks unchanged | `test_matrix_versions_parse_to_identical_normalized_ingest` |

> **Correction (why the shapes changed):** earlier revisions of the 9.0.0 fixture
> *omitted* `startTimeMillis`, `overallSuccess`, `finishTimeMillis` and the
> `*_millis` test-timing fields and added a fictional `anomaly_report`, encoding a
> Bazel 9 that assumed these deprecated fields were dropped. They are not: the
> populators listed above set them in 9.0.0 exactly as in 7.4.1. The fixtures and
> tests now depict the diff that the primary sources actually show.

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

with `bazelisk` on `PATH`. The hook runs Bazel in the repo's real workspace
(`demo/bazel-monorepo`, which pins `.bazelversion` and defines `//tasks/...`) —
**not** at the repo root, which is not a Bazel workspace. Absent the env gate and
`bazelisk`, the live hook is **skipped** and these proto-derived fixtures are the
tested coverage — see the honest range statement in
`docs/wiki/reference/bep-version-matrix.md`.
