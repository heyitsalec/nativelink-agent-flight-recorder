# NLFR DAG Mirrors

## Active — Docs wiki wave 2 (wave-0 ARMED)

[docs-wiki-wave2.md](docs-wiki-wave2.md) · Handoffs: `docs/sessions/handoffs/docs-wiki-wave2/wave-0/`  
Wave-0 ceiling: close docs-excellence wave-1 gaps (historical banners, broker diagram, ADR-lite, compare sample, link audit). Control plane: `kos serve http://127.0.0.1:7423`, `dag_ref` `dag:nlfr-flagship`, `linear_authority: false`. Parallel coordinators: `coord-historical-banners`, `coord-broker-diagram`, `coord-wiki-adrs`, `coord-compare-sample`, `coord-link-audit`. Branch: `feat/docs-wiki-wave2`.

## Active — Docs excellence (wave-0 ARMED)

[docs-excellence.md](docs-excellence.md) · Handoffs: `docs/sessions/handoffs/docs-excellence/wave-0/`  
Wave-0 ceiling: flagship OSS documentation — Diátaxis wiki hub, Harmony README, adoption paths, mermaid diagrams under `docs/diagrams/`, proof-samples hub, contributor cross-links. Parallel coordinators: `coord-readme-flagship`, `coord-wiki-hub`, `coord-adoption-paths`, `coord-diagrams`, `coord-proof-samples-hub`, `coord-code-polish`, `coord-contributing`. Branch: `feat/docs-excellence`. GHA offline tolerated; local proof gates at ship.

## Active — Fleet evidence v1 (frontier wave)

[fleet-evidence-v1.md](fleet-evidence-v1.md) · Handoffs: `docs/sessions/handoffs/fleet-evidence-v1/wave-1/` (wave-0: `wave-0/`)  
Wave-1 ceiling: `stdout_ingest_breadth` — attach `nativelink.stdout.txt` pre-ingest on local-exec, worker-evidence, agent-loop, and cold-warm proof paths; M7 `worker_identity` conditional on regex match. **Committed today:** local-exec + worker-evidence only; agent-loop + cold-warm attach pending `fel-w1-agent-coldwarm-attach`. Local proof gates substitute for CI while GHA offline.

## Active — LRE proof (cache parity wired; CI deferred)

[lre-proof.md](lre-proof.md) · Handoffs: `docs/sessions/handoffs/lre-proof/wave-4/`  
Phase 4 ceiling: `lre_cache_parity_observed` (`collectable_v1`, `medium`) — `lre-cold-warm-proof.sh` cold/warm cache economics on x86_64-linux. Phases 1–2 preserved via `lre-proof.sh` and `lre-nix-toolchain-proof.sh`. CI green deferred while GHA offline; fleet UI remains blocked.

## Future — execution ladder (blocker-gated)

Fleet dashboards: [future-execution-ladder.md](future-execution-ladder.md) — research only, no UI DAG.

## Active — Architecture track

Linear: [PER-1058](https://linear.app/gradschool/issue/PER-1058/nlfr-arch-architecturally-sound-track-l0-l2-hardening)

| Milestone | Linear | Phase |
|-----------|--------|-------|
| M1 Reference kit | PER-1059 | 1 — merge PR #2 + tag |
| M2 Quantified fast | PER-1060 | 2 — cache economics in proof |
| M3 Two-worker Nix | PER-1061 | 3 — execution ladder |
| M4 Agent loop | PER-1062 | 4 — LLM patch provenance |

### Phase 5+ — Credibility + substrate (M5–M9)

| Milestone | Proves | Status |
|-----------|--------|--------|
| M5 | CI Linux proof + adoption docs | landed (PER-1065) |
| M6 | Real default projection polish | done (PER-1066) |
| M7 | One worker-evidence parser | landed (PER-1067) |
| M8 | Real agent adapter | landed (PER-1068) |
| M9 | Multi-run compare | landed (PER-1069) |

Review gates: Wave 1.5 and 2.5 per [`review-gates.md`](review-gates.md). Umbrella: [`m5-m9-umbrella.md`](m5-m9-umbrella.md).

Phase 5 (product shape fork) remains buyer-signal gated after M5–M9.

Mirror: [architecture-track.md](architecture-track.md) · Spec: [../ARCHITECTURE_TRACK.md](../ARCHITECTURE_TRACK.md)

## Active — Dogfood (GUI builder loop)

Linear parent: [PER-1058](https://linear.app/gradschool/issue/PER-1058)

| DAG | Linear | Scope |
|-----|--------|-------|
| A — Generic command recorder | PER-1063 | `nlfr run --mode generic` spine |
| B — Canvas dogfood + diff | PER-1064 | screenshot diff, truth guard, real default projection |

Mirrors: [dogfood-a-generic-recorder.md](dogfood-a-generic-recorder.md) · [dogfood-b-canvas-dogfood.md](dogfood-b-canvas-dogfood.md)

Coordinator mode: **parallel** A + B; B dogfood leg blocked on A.

## Active — M5–M9 umbrella (broker)

Linear parent: [PER-1058](https://linear.app/gradschool/issue/PER-1058)

| Milestone | Linear | Scope |
|-----------|--------|-------|
| M5 CI proof | PER-1065 | Linux CI + adoption docs |
| M6 real default | PER-1066 | docs/banner polish (non-blocking) |
| M7 worker parser | PER-1067 | one direct-evidence claim |
| M8 agent adapter | PER-1068 | real Cursor/CLI provenance |
| M9 multi-run compare | PER-1069 | compare + canvas lens |

Umbrella: [m5-m9-umbrella.md](m5-m9-umbrella.md) · Review gates at Wave 1.5 and 2.5.

## Completed — Frontier wave (2026-06-06)

| DAG | Ceiling | Handoffs |
|-----|---------|----------|
| Tier1 live Bazel | live Acts 1+2 + Bazel validation | [tier1-live-bazel.md](tier1-live-bazel.md) · `tier1-live-bazel/wave-1/` |
| CI Bazel tier1 | workflow job + local proof script | [ci-bazel-tier1.md](ci-bazel-tier1.md) · `ci-bazel-tier1/` |
| Tier 1 Agent Vision | broker waves 0–6 shipped | [tier1-agent-vision.md](tier1-agent-vision.md) · `tier1-agent-vision/` |
| Doc capture wave 2 | tier1-aligned hero GIF refresh | [nlfr-doc-capture-wave2.md](nlfr-doc-capture-wave2.md) · `nlfr-doc-capture/wave-2/` |

Broker handoffs: `docs/sessions/handoffs/frontier-wave/wave-0/` · Wave-1 closeout: `frontier-wave/wave-1/`

## Completed — Doc capture (PER-1071)

Linear: [PER-1071](https://linear.app/gradschool/issue/PER-1071/nlfr-doc-documentation-and-hero-media-capture-pass)

| Workstream | Linear | Deliverable |
|------------|--------|-------------|
| DOC-A capture | PER-1072 | Capture scripts + `docs/media/*.gif` + `MEDIA_CAPTURE.md` |
| DOC-B wiki | PER-1073 | `docs/INDEX.md` hub + cross-links + `CONTRIBUTING.md` |
| DOC-C readme | PER-1074 | Harmony-style root `README.md` with embedded heroes |

Mirror: [doc-capture-pass.md](doc-capture-pass.md) · Handoffs: `docs/sessions/handoffs/nlfr-doc-capture/wave-1/`

## Completed — Vision DAG

Linear umbrella: [PER-1053](https://linear.app/gradschool/issue/PER-1053/nlfr-vision-product-vision-implementation-dag)

| Sub-DAG | Linear | Ring | Repo mirror |
|---------|--------|------|-------------|
| A — Tryout kit | PER-1055 | 1 | [vision-a-tryout.md](vision-a-tryout.md) |
| B — Truth and canvas | PER-1054 | 2 | [vision-b-truth.md](vision-b-truth.md) |
| C — Remote execution | PER-1056 | 3 | [vision-c-remote.md](vision-c-remote.md) |
| D — Integration | PER-1057 | all | [vision-d-integration.md](vision-d-integration.md) |

Coordinator mode: single serial session **A → B → C → D**.

Handoffs: `docs/sessions/handoffs/`

## Orchestration (Knowledge OS broker)

Multi-DAG milestones ("Implement the plan") use **parent broker mode**:

- Canonical contract: [knowledge-os/agent-os/harness/broker-dispatch-manifest.md](/Users/alecbot/Documents/knowledge-os/agent-os/harness/broker-dispatch-manifest.md)
- NLFR pack: [knowledge-os/projects/nlfr/pack.md](/Users/alecbot/Documents/knowledge-os/projects/nlfr/pack.md) § Orchestration

Parent spawns coordinator subagents per DAG; coordinators return `DispatchManifest` JSON; parent spawns workers and resumes coordinators until `completion-ritual`.

### Parent proof gates (GHA offline — 2026-06-06)

GitHub Actions workflows have been non-green ~1 month. Broker **must not block** on CI at ship. Local gates: `uv run pytest -q`, `bash -n scripts/*.sh`, optional Nix develop proofs on host. PR merge: local gates + review packet, not CI green. See [`frontier-wave/wave-1/gha-offline-proof-shift.md`](../sessions/handoffs/frontier-wave/wave-1/gha-offline-proof-shift.md).
