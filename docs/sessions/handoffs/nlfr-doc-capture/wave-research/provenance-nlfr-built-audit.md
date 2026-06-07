# NLFR Built-State Provenance Audit

**Repo:** `/Users/alecbot/Documents/nativelink-agent-flight-recorder`  
**Branch observed:** `feat/m5-m9-umbrella`  
**Audit date:** 2026-06-06  
**Method:** Read-only inspection of code, scripts, committed projections, `data/*/summary.json`, handoffs, CI workflow, and docs vs `docs/ONE_PAGER.md`.

---

## Executive summary

NLFR has a real evidence spine (Python CLI → SHA-256 artifacts → SQLite → truth-labeled projection JSON → sparse canvas). **Real NativeLink/Bazel proof is Nix-gated.** Outside `nix develop`, scripts honestly emit `environment_blocker` JSON rather than fake success.

The repo is **honest in architecture** but **drifts in demo defaults**: docs claim M6 "canvas-dev `collectable_v1` default," while **committed** `apps/canvas/public/projections/` is **`simulated_v1` fixture** (agent-loop + fixture Bazel ingest from `verify-demo.sh`).

---

## Milestone map (M1–M9 + dogfood + doc capture)

### M1 — Reference kit (PER-1059)

| Aspect | Truth |
|--------|-------|
| **Built** | Public repo, docs hub, pytest suite (~61 tests), fixture demo path, tag `v0.2.0-mvp` cited in ONE_PAGER |
| **Proven** | `uv run pytest`; `./scripts/verify-demo.sh` exit 0 on Linux (fixture legs) |
| **Label** | Spine code is real; default canvas data is **`simulated_v1`** |

### M2 — Quantified cache "fast" (PER-1060)

| Aspect | Truth |
|--------|-------|
| **Built** | `scripts/cold-warm-cache-proof.sh`, cache economics in proof projector |
| **Nix proven** | **`collectable_v1`** — cold `hit_rate` 0.0, warm 1.0; real Bazel via Nix store |
| **Evidence** | `data/cold-warm-proof/summary.json` (8.51s / 6.56s on latest author run); `docs/proof-samples/cold-warm-summary.json` (8.17s / 5.48s — ONE_PAGER numbers) |
| **CI** | `.github/workflows/nlfr-proof.yml` job `linux-nix-toolchain` runs cold-warm |

### M3 — Two-worker live endpoints (PER-1061)

| Aspect | Truth |
|--------|-------|
| **Built** | `NLFR_EXPECTED_WORKERS=2 scripts/local-exec-proof.sh`, `scripts/worker-readiness.py` |
| **Nix proven** | **`collectable_v1`** — `worker_endpoints_ready`, `configured_workers=2`, `expected_workers=2` |
| **Evidence** | `data/local-exec-proof-2w/summary.json` |
| **Honest limit** | Endpoint readiness only — **not** work distributed across two workers |
| **CI gap** | **Not** in GitHub Actions workflow |

### M4 — Agent loop closure (PER-1062)

| Aspect | Truth |
|--------|-------|
| **Built** | `scripts/agent-loop-proof.sh`, `nlfr simulate --scenario llm-bounded-patch` + real Bazel ingest |
| **Nix proven** | Mixed: validation/cache leg **`collectable_v1`**; agent/change nodes **`simulated_v1`** (deterministic patch, zero LLM tokens) |
| **Evidence** | `data/agent-loop-proof/summary.json` — `chain_complete: true` |
| **CI** | Agent-loop in `linux-nix-toolchain` job |

### Dogfood A — Generic command recorder (PER-1063)

| Aspect | Truth |
|--------|-------|
| **Built** | `nlfr run --mode generic`, `scripts/record-proof.sh` |
| **Proven** | **`collectable_v1`** without Nix — arbitrary commands, invocations, artifacts; no Bazel cache/target layers |
| **CI** | `record-proof.sh` in unit job |

### Dogfood B — Canvas dogfood (PER-1064)

| Aspect | Truth |
|--------|-------|
| **Built** | `scripts/record-canvas-build.sh`, `scripts/redact-projection.py`, truth-guard, screenshot diff |
| **Proven locally** | **`collectable_v1`** in `data/canvas-dev/summary.json` and `data/canvas-dev/projections/proof.raw.json` |
| **Committed default** | **`simulated_v1`** in `apps/canvas/public/projections/` — **M6 drift** (see Gaps) |
| **CI** | Unit job runs `record-canvas-build.sh` + `test:truth`; separate `verify-demo-fixture` job overwrites projections with fixtures in CI artifacts only |

### M5 — Linux CI + adoption docs (PER-1065)

| Aspect | Truth |
|--------|-------|
| **Built** | `.github/workflows/nlfr-proof.yml`, `docs/ADOPTION_GUIDE.md`, `docs/CI_RECIPE.md` |
| **CI jobs** | (1) unit + generic + canvas dogfood; (2) Nix cold-warm + agent-loop; (3) verify-demo fixture |
| **Gap** | `docs/proof-samples/` from **author Nix**, not first green Linux CI artifact (vision auditor flagged) |

### M6 — Real default projection (PER-1066)

| Aspect | Truth |
|--------|-------|
| **Claimed** | Done — canvas-dev `collectable_v1` default + fixture fallback banner |
| **Actual committed state** | `apps/canvas/public/projections/action-graph.json` nodes/edges are **`simulated_v1`** (`scenario:llm-bounded-patch`, fixture ingest) |
| **Regenerate real default** | `./scripts/record-canvas-build.sh` (not what's committed after verify-demo workflow) |
| **UI** | Fixture fallback banner in `App.tsx` works; currently unnecessary because committed files load successfully as fixtures |

### M7 — Worker identity parser (PER-1067)

| Aspect | Truth |
|--------|-------|
| **Built** | `src/nlfr/ingest/worker_admin_stdout.py`, graph/proof promotion, `scripts/worker-evidence-proof.sh` |
| **Last local proof** | **`fixture-replay`** mode — redacted `tests/fixtures/worker-admin/nativelink.stdout.txt` stitched with Bazel fixtures |
| **Parser labels** | Parsed rows **`collectable_v1`** when log lines match; drops `worker_identity` from unsupported claims |
| **Live Nix path** | Script can chain `local-exec-proof.sh` when Nix PATH available — not CI-gated |
| **Still unproven** | action_placement, queue_time, scheduler_assignment, load_distribution |

### M8 — Real agent adapter (PER-1068)

| Aspect | Truth |
|--------|-------|
| **Built** | `scripts/record-agent-change.sh`, `--provenance-sidecar` in generic run, `adapters/cursor/README.md` |
| **Proven** | Adapter metadata **`collectable_v1`** (model + `prompt_sha256` only; raw prompt never stored) |
| **E2E** | `data/agent-change-proof/summary.json` — validation via `pytest tests/test_record_agent_change.py`, **not** Bazel/NativeLink |
| **Not built** | Live Cursor hook, automatic session capture, full agent→change→Bazel chain via adapter |

### M9 — Multi-run compare (PER-1069)

| Aspect | Truth |
|--------|-------|
| **Built** | `nlfr compare export|index`, `src/nlfr/projectors/compare.py`, `scripts/compare-proof.sh`, canvas Compare lens |
| **Labels** | Compare projection **`derived_v1`** (5 dimensions: run_counts, cache_metrics, worker_identity, agent_provenance, status_deltas) |
| **Evidence** | `data/compare-proof/summary.json`; `apps/canvas/public/projections/compare-projection.json` present |
| **Limit** | Index-only retention; no auto-purge; no cross-run worker/queue correlation |

### Doc capture (PER-1071–1074)

| Aspect | Truth |
|--------|-------|
| **Built** | `capture-demo-tour.mjs`, `capture-evidence-loop.mjs`, `docs/media/*.gif`, `docs/MEDIA_CAPTURE.md`, Harmony-style README |
| **Tour GIF** | Playwright over canvas preview — Action Graph, Proof Packet, Compare, operator command |
| **Evidence-loop GIF** | **Curated HTML terminal replay** (not live shell); public-safe `${NLFR_DATA}` placeholders |
| **Truth** | Tour renders whatever projections are loaded (currently **`simulated_v1`** committed fixtures) |

---

## Scripts inventory

| Script | Requires Nix | Primary `source_kind` | What it actually proves |
|--------|--------------|----------------------|---------------------------|
| `scripts/cold-warm-cache-proof.sh` | Yes | `collectable_v1` | Real NativeLink cache-only + Bazel cold/warm; cache economics in proof |
| `scripts/local-exec-proof.sh` | Yes | `collectable_v1` | One-process remote-executor smoke; `worker_endpoints_ready` (1 worker) |
| `NLFR_EXPECTED_WORKERS=2 … local-exec-proof.sh` | Yes | `collectable_v1` | Two workers configured + ports open — not distributed execution |
| `scripts/agent-loop-proof.sh` | Yes | Mixed | Full graph chain; Bazel leg collectable; agent/change simulated |
| `scripts/verify-demo.sh` | Partial | Mixed | pytest; Nix legs → blocker off-Nix; fixture simulate+ingest → **`simulated_v1`**; overwrites public projections |
| `scripts/record-proof.sh` | No | `collectable_v1` | Generic command record (pytest subset) |
| `scripts/record-canvas-build.sh` | No | `collectable_v1` | Dogfood canvas build + redacted publish to `public/projections/` |
| `scripts/record-agent-change.sh` | No | `collectable_v1` | M8 adapter sidecar + generic validation command |
| `scripts/worker-evidence-proof.sh` | Optional | `collectable_v1` | Fixture-replay default; live local-exec when tools on PATH |
| `scripts/compare-proof.sh` | No | `derived_v1` | Cross-DB compare record-proof vs canvas-dev |
| `scripts/worker-readiness.py` | Helper | — | Port/config readiness JSON for local-exec proofs |
| `scripts/redact-projection.py` | Helper | — | Path redaction before publishing projections |

**Canvas npm scripts:** `dev`, `build`, `capture`, `capture:tour`, `capture:evidence`, `capture:heroes`, `diff`, `test:truth`, `preview`.

---

## Canvas capabilities (projection-only)

From `apps/canvas/src/App.tsx`:

1. **Action Graph** — D3 layout, zoom/pan, node inspector (source_kind, confidence, redaction, evidence_refs)
2. **Validation Runway** — timeline overlay sorted by node kind
3. **Proof Packet** — drawer with blocks, metrics, unsupported-claims lists
4. **Remote Boundary** — lens from `remote_execution` + worker readiness proof blocks
5. **Compare Runs** — optional `compare-projection.json` (`derived_v1` dimensions)
6. **Operator command bar** — keyword routing (cache, fail, proof, remote, agent, compare, runway, reset)
7. **Truth legend** — collectable / derived / simulated / future
8. **Fixture fallback banner** — when projection fetch fails (loads `sampleProjection.ts`)

**Tests:** `test:truth` (truth-guard), Playwright capture scripts, pixel diff baselines.

---

## Gaps vs `docs/ONE_PAGER.md`

| ONE_PAGER claim | Actual state |
|-----------------|--------------|
| Cold/warm 8.17s / 5.48s | Proven class of claim; latest author run differs (8.51s / 6.56s) — timing is run-specific |
| Two-worker live endpoints | Proven on author Nix (`local-exec-proof-2w`); **not in CI**; ONE_PAGER honest about "not distributed" |
| Agent loop mixed labels | **Aligned** — ONE_PAGER correctly separates collectable validation vs simulated agent |
| "Deterministic simulated-agent provenance (zero LLM tokens)" | **Accurate** |
| Evaluator path "Fixture canvas ~5 min" | **Accurate** — committed projections are `simulated_v1` |
| Evaluator path "Real proof Nix ~30+ min" | **Accurate** when run inside `nix develop` |
| Tag `v0.2.0-mvp`, branch `main` | Docs say main; active work on `feat/m5-m9-umbrella` |
| Implicit: first canvas view is real proof | **Gap** — M6 docs vs committed `simulated_v1` fixtures |
| Worker identity "unproven" in ONE_PAGER | **Partially superseded by M7** — parser exists; last proof run was fixture-replay |
| Remote execution beyond endpoint readiness | Still **explicitly unproven** (aligned) |

**Additional gaps not in ONE_PAGER:**

- `tri-agent-loop` in README/AGENTS.md proof commands — scenario name in tests/docs, **not** a scripted proof gate
- M8 "real adapter" = **manual shell script**, not Cursor automation
- Linux CI does not run local-exec, two-worker, worker-evidence, or compare-proof
- `verify-demo.sh` last step replaces public projections with **`simulated_v1`** — conflicts with M6/ADOPTION_GUIDE

---

## Test / CI truth summary

| Layer | Status |
|-------|--------|
| pytest (~61 tests) | Fixture-backed parsers, projectors, generic run, compare, worker parser, agent adapter dry-run |
| GitHub Actions unit | record-proof + record-canvas-build + truth-guard |
| GitHub Actions Nix | cold-warm + agent-loop only |
| GitHub Actions verify-demo | Full script; Nix proofs → blockers; fixture path succeeds |

---

## JSON summary

```json
{
  "proven": [
    {
      "id": "m2-cold-warm-cache",
      "milestone": "M2",
      "source_kind": "collectable_v1",
      "environment": "nix develop (author Mac + CI linux-nix-toolchain job)",
      "script": "scripts/cold-warm-cache-proof.sh",
      "artifact": "data/cold-warm-proof/summary.json",
      "claim": "Cold hit_rate 0.0 → warm hit_rate 1.0 with real Bazel through NativeLink cache-only"
    },
    {
      "id": "m3-one-worker-local-exec",
      "milestone": "M3",
      "source_kind": "collectable_v1",
      "environment": "nix develop (author Mac only; not CI)",
      "script": "scripts/local-exec-proof.sh",
      "artifact": "data/local-exec-proof/summary.json",
      "claim": "One-process remote-executor smoke; worker_endpoints_ready expected_workers=1"
    },
    {
      "id": "m3-two-worker-endpoints",
      "milestone": "M3",
      "source_kind": "collectable_v1",
      "environment": "nix develop (author Mac only; not CI)",
      "script": "NLFR_EXPECTED_WORKERS=2 scripts/local-exec-proof.sh",
      "artifact": "data/local-exec-proof-2w/summary.json",
      "claim": "Two workers configured and ports open; not work distributed across workers"
    },
    {
      "id": "m4-agent-loop-validation-leg",
      "milestone": "M4",
      "source_kind": "collectable_v1",
      "environment": "nix develop (author Mac + CI linux-nix-toolchain job)",
      "script": "scripts/agent-loop-proof.sh",
      "artifact": "data/agent-loop-proof/summary.json",
      "claim": "chain_complete=true; Bazel validation/cache ingested from real run"
    },
    {
      "id": "dogfood-a-generic-record",
      "milestone": "Dogfood A",
      "source_kind": "collectable_v1",
      "environment": "any host with uv",
      "script": "scripts/record-proof.sh",
      "artifact": "data/record-proof/summary.json",
      "claim": "Generic command recorder spine without Bazel layers"
    },
    {
      "id": "dogfood-b-canvas-dev-record",
      "milestone": "Dogfood B",
      "source_kind": "collectable_v1",
      "environment": "uv + npm (CI unit job)",
      "script": "scripts/record-canvas-build.sh",
      "artifact": "data/canvas-dev/summary.json",
      "claim": "NLFR records building its own canvas; redacted raw projections exist under data/canvas-dev/"
    },
    {
      "id": "m8-agent-adapter-metadata",
      "milestone": "M8",
      "source_kind": "collectable_v1",
      "environment": "uv (manual operator run)",
      "script": "scripts/record-agent-change.sh",
      "artifact": "data/agent-change-proof/summary.json",
      "claim": "Adapter sidecar with model + prompt_sha256; validation via pytest not Bazel"
    },
    {
      "id": "m7-worker-identity-parser",
      "milestone": "M7",
      "source_kind": "collectable_v1",
      "environment": "fixture-replay default; optional nix local-exec",
      "script": "scripts/worker-evidence-proof.sh",
      "artifact": "data/worker-evidence-proof/summary.json",
      "claim": "worker_identity_observed from admin stdout regex; worker_nodes=2 in fixture-replay mode"
    },
    {
      "id": "m9-compare-projection",
      "milestone": "M9",
      "source_kind": "derived_v1",
      "environment": "uv after record-proof + canvas-dev DBs exist",
      "script": "scripts/compare-proof.sh",
      "artifact": "data/compare-proof/summary.json",
      "claim": "Five-dimension proof-packet diff across run groups; no cross-run worker correlation"
    },
    {
      "id": "environment-blockers",
      "milestone": "M1/M5",
      "source_kind": "collectable_v1",
      "environment": "host without bazel/nativelink on PATH",
      "script": "verify-demo.sh and proof scripts",
      "artifact": "data/demo-proof/*/environment-blocker.json",
      "claim": "Honest blocker recording instead of false NativeLink success"
    }
  ],
  "simulated": [
    {
      "id": "committed-canvas-projections",
      "source_kind": "simulated_v1",
      "artifact": "apps/canvas/public/projections/action-graph.json",
      "origin": "verify-demo.sh fixture simulate + ingest with --source-kind simulated_v1",
      "claim": "Agent-loop demo graph with fixture Bazel evidence; not canvas-dev dogfood"
    },
    {
      "id": "m4-agent-change-nodes",
      "source_kind": "simulated_v1",
      "artifact": "data/agent-loop-proof/projections/proof.json",
      "origin": "nlfr simulate llm-bounded-patch deterministic patch",
      "claim": "Agent and change provenance nodes; zero LLM tokens"
    },
    {
      "id": "verify-demo-fixture-chain",
      "source_kind": "simulated_v1",
      "script": "scripts/verify-demo.sh (simulate + ingest legs)",
      "claim": "Full agent→fixture-Bazel chain for 5-minute evaluator path"
    },
    {
      "id": "m7-worker-fixture-replay",
      "source_kind": "collectable_v1 ingest of simulated log fixture",
      "artifact": "tests/fixtures/worker-admin/nativelink.stdout.txt",
      "note": "Log content is fixture; parser behavior proven; not live worker fleet"
    },
    {
      "id": "doc-capture-evidence-gif",
      "source_kind": "simulated_v1 presentation",
      "artifact": "docs/media/nlfr-evidence-loop.gif",
      "claim": "Curated HTML terminal replay; illustrates pipeline, not live recording"
    },
    {
      "id": "canvas-sample-fallback",
      "source_kind": "simulated_v1",
      "artifact": "apps/canvas/src/sampleProjection.ts",
      "claim": "In-app fallback when projection fetch fails"
    }
  ],
  "gaps": [
    "M6 drift: ADOPTION_GUIDE/README claim canvas-dev collectable_v1 default; committed public/projections is simulated_v1 fixture",
    "verify-demo.sh overwrites apps/canvas/public/projections with fixture simulated_v1 after record-canvas-build would publish collectable_v1",
    "CI linux-nix-toolchain omits local-exec, two-worker, worker-evidence, and compare-proof scripts",
    "docs/proof-samples/ sourced from author Nix Mac, not promoted from first green Linux CI run",
    "ONE_PAGER cold/warm timing (8.17s/5.48s) is one run snapshot; not pinned to CI artifact",
    "M8 real adapter is manual record-agent-change.sh; no live Cursor integration or Bazel validation via adapter",
    "Worker identity parser last local proof was fixture-replay; live Nix stdout path not CI-gated",
    "Still unproven per ONE_PAGER: action placement, queue time, scheduler assignment, load distribution, multi-machine fleet",
    "tri-agent-loop referenced in README/AGENTS.md proof commands but not a proof script or CI gate",
    "M9 retention is index-only; no artifact retention policy or auto-purge"
  ],
  "demo_ready_scripts": [
    {
      "script": "uv run pytest tests -q",
      "needs_nix": false,
      "proves": "Parser/projector/CLI fixture tests (~61 tests)"
    },
    {
      "script": "npm --prefix apps/canvas run dev -- --host 127.0.0.1",
      "needs_nix": false,
      "proves": "Canvas renders committed simulated_v1 projections + compare lens if JSON present"
    },
    {
      "script": "./scripts/verify-demo.sh",
      "needs_nix": false,
      "proves": "End-to-end fixture demo path; records Nix blockers for real-tool legs; publishes simulated projections"
    },
    {
      "script": "./scripts/record-proof.sh",
      "needs_nix": false,
      "proves": "collectable_v1 generic recorder without Bazel"
    },
    {
      "script": "./scripts/record-canvas-build.sh",
      "needs_nix": false,
      "proves": "collectable_v1 dogfood + redacted publish (requires npm)"
    },
    {
      "script": "npm --prefix apps/canvas run capture:heroes",
      "needs_nix": false,
      "proves": "Regenerates hero GIFs from current projections (Playwright + ffmpeg)"
    },
    {
      "script": "nix develop -c ./scripts/cold-warm-cache-proof.sh",
      "needs_nix": true,
      "proves": "collectable_v1 cache economics (real proof)"
    },
    {
      "script": "nix develop -c ./scripts/agent-loop-proof.sh",
      "needs_nix": true,
      "proves": "Mixed chain_complete agent loop with real Bazel validation leg"
    },
    {
      "script": "nix develop -c ./scripts/local-exec-proof.sh",
      "needs_nix": true,
      "proves": "collectable_v1 one-worker endpoint readiness"
    },
    {
      "script": "nix develop -c env NLFR_EXPECTED_WORKERS=2 NLFR_LOCAL_EXEC_OUTPUT=$PWD/data/local-exec-proof-2w ./scripts/local-exec-proof.sh",
      "needs_nix": true,
      "proves": "collectable_v1 two-worker endpoint readiness"
    },
    {
      "script": "./scripts/compare-proof.sh",
      "needs_nix": false,
      "proves": "derived_v1 multi-run compare (requires prior record-proof + canvas-dev DBs)"
    },
    {
      "script": "./scripts/record-agent-change.sh --dry-run --change-path README.md --model demo --prompt-file README.md",
      "needs_nix": false,
      "proves": "M8 sidecar shape + prompt_sha256 without mutating workspace"
    }
  ]
}
```
