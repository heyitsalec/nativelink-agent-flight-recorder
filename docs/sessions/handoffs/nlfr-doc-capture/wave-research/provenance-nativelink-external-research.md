# NativeLink External Research — Demo Strategy Brief

**Worker:** wave-research  
**When:** 2026-06-06  
**Purpose:** Inform NLFR demo strategy for engineers who build and buy NativeLink  
**Sources:** Public README, product site, Mintlify docs, Bazel community listing, v1.0.0 release notes, Reid Kleckner LLVM blog, NativeLink MCP server README, NLFR one-pager (internal context)

---

## 1. What NativeLink Is (Product Positioning)

NativeLink is a **high-performance remote build cache and remote execution (RBE) platform** from Trace Machina. It implements the standard **Remote Execution API v2** (gRPC + protobuf) and acts as a drop-in backend for build clients — not a replacement for Bazel, Buck2, or CMake.

**One-line pitch (their words):** unify remote caching, remote execution, and observability into a single Rust-native platform built for codebases that outgrow provisioning speed.

**Four product pillars** (nativelink.com/product):

| Pillar | Claim | Mechanism |
|--------|-------|-----------|
| Remote cache | "Cache once. Reuse forever." | Content-addressable storage (CAS) + Action Cache (AC); dedup by hash |
| Remote execution | "Distribute across every core." | Scheduler assigns actions to worker fleet; hermetic, platform-matched |
| Cloud & self-host | "<10m time to first hit" | NativeLink Cloud free tier, Docker one-liner, or K8s/multi-region self-host |
| Rust performance | "0 GC pauses" | Memory safety without runtime GC; positioned as infra that stays fast at scale |

**Not the product:** NativeLink is not a build system, CI orchestrator, or results dashboard. Clients (Bazel, Buck2, Reclient, Goma, Pants, Soong, CMake via **recc**) speak RE protocol; NativeLink serves cache + execution.

**License note:** Most of the monorepo is **FSL-1.1-Apache-2.0** (converts to Apache 2.0 after two years). Some modules (metrics, remote persistent workers) are BSL. Individual cache use does not require commercial license; shared production metrics/RPE may.

**Emerging positioning (2026):** Agent-era builds — product page lists Cursor, Claude Code, Copilot Workspace, Devin, Windsurf as AI coding platform integrations; MCP server generates `.bazelrc` and triggers cloud cache/RBE from agents.

---

## 2. Who Uses It and For What

### Stated production users / contributors

- **Samsung** — named repeatedly as production customer; 1B+ requests/month
- **Meta, Menlo Security, AWS, Alibaba Cloud** — named as v1.0.0 development contributors (Mar 2026 release)
- **Thirdwave Automation** — case study: autonomous systems / safety-critical robotics; Bazel + massive parallel testing
- **LLVM community** — Reid Kleckner distributed CMake/recc builds (17m → 4m full compile on product page; blog reports ~4× on personal cluster)

### Primary use cases

| Use case | Who | What they get |
|----------|-----|---------------|
| **Remote cache only** | Dev laptops, CI | Incremental builds skip unchanged actions; cross-dev/CI artifact reuse |
| **Full RBE** | Large monorepos (C++, Rust, Java, Go, Python) | Parallel compile/test across worker pool; offload from laptops |
| **CI acceleration** | GitHub Actions, GitLab, Buildkite, Jenkins | Same cache across PR builds; reduced wall time and cloud spend |
| **Hermetic / reproducible builds** | Platform teams, safety-critical | LRE (Local Remote Execution) mirrors Nix toolchains locally and remotely |
| **Specialized hardware** | ML, mobile, embedded | Workers tagged by platform properties (GPU, ARM, Apple Silicon) |
| **Non-Bazel paths** | LLVM, CMake shops | **recc** wraps compiler invocations for RE without Bazel migration |
| **Agent loops** | AI coding workflows | Fast validate-after-edit via cloud cache; MCP-assisted Bazel config |

### Deployment patterns (from architecture docs)

- Single-node (dev/CI runner)
- Distributed cluster (dedicated schedulers + 10s–1000s workers + S3/GCS)
- Hybrid cloud (local CAS/AC + GRPC scheduler forwarding to cloud)
- Multi-region (regional workers, global CAS)

---

## 3. Problems They Claim vs Competitors

NativeLink sits in the **Bazel Remote Execution ecosystem** alongside self-hosted OSS (Buildbarn, Buildfarm, BuildGrid) and commercial platforms (BuildBuddy, EngFlow, Aspect, Hermetiq, Bitrise). Bazel's official community page lists NativeLink under **Commercial**: "Remote build execution, caching, analytics, and simulation."

### Problems NativeLink claims to solve

1. **Build wall time at monorepo scale** — cache hits in milliseconds; RBE parallelizes thousands of actions
2. **Infrastructure cost** — dedup CAS, tiered stores (FastSlow), reuse across dev/CI/agent; Thirdwave cites 50% cloud cost reduction
3. **Cache miss pain between local and remote** — **LRE** is the flagship differentiator: Nix-generated toolchains give "virtually perfect" hit rates across repos, devs, and CI
4. **Operational fragility of first-gen RBE** — founder origin story: built because "similar projects not working or being extremely inefficient" (Reid Kleckner blog, history docs)
5. **Runtime overhead at high QPS** — Rust/no-GC vs Java (Buildfarm) or Go (Buildbarn) under load; "1B requests/month on infrastructure that would buckle other systems"
6. **Build-system lock-in** — RE API compatibility + recc for CMake; no proprietary client required for LLVM path
7. **Provenance / trust** — content-addressed artifacts, signed inputs/outputs, hermetic builds, audit trails (SOC 2 in progress)

### Competitive framing (inferred from public material — no head-to-head benchmarks published)

| Dimension | NativeLink emphasis | Typical competitor angle |
|-----------|--------------------|-----------------------|
| **Performance / efficiency** | Rust, no GC pauses, store composition, gRPC efficiency | BuildBuddy: warm VM snapshots, rich UI; EngFlow: managed enterprise RBE |
| **Hermeticity / cache correctness** | LRE + Nix toolchain pipeline | Buildfarm: reference RE API; manual toolchain configs |
| **Developer experience** | 10-minute Docker/cloud start, MCP for agents | BuildBuddy/Hermetiq: build analytics, cache miss debugging, cost tracking UI |
| **Deployment flexibility** | Self-host, cloud, hybrid, multi-region same code path | Aspect/EngFlow: hosted + self-hosted enterprise |
| **Observability** | Prometheus, OpenTelemetry, origin events | BuildBuddy BES/results UI as primary surface |

**Honest gap:** NativeLink does not publish systematic benchmarks vs BuildBuddy/Buildfarm. Proof is anecdotal (LLVM 4×, Thirdwave 80% reduction, 1B req/month scale claim) plus architecture arguments.

---

## 4. What Would Impress Engineers Who BUILD NativeLink

These are proof points the **implementers and maintainers** care about — not buyer marketing fluff.

### Scale and production hardening

- **1B+ requests/month** in production (Samsung named)
- **v1.0.0 (Mar 2026)** positioned as "most exhaustively tested, configurable, and scalable release"; Meta/AWS/Samsung/Alibaba involved
- **50K simultaneous jobs** (Thirdwave case study)
- OpenSSF Scorecard + Best Practices badges on GitHub

### Protocol correctness and composability

- Full **RE API v2** surface: Execution, CAS, ByteStream, Action Cache, Capabilities
- **Modular scheduler stack**: Simple, Cache Lookup, Property Modifier, GRPC federation schedulers — composable in config
- **Platform property matching** (minimum/exact/priority/ignore) for worker routing
- **Store composition**: compression, dedup, FastSlow tiers, S3/GCS/Redis/filesystem backends

### The LRE story (their technical moat)

- Nix-powered toolchain generation → Bazel `@local-remote-execution` module
- Same `/nix/store/...` paths in `lre.bazelrc` and generated-cc BUILD files
- Demonstrable **local build → remote cache hit** without re-execution (documented LRE flow)
- `rbe_configs_gen` pipeline for worker image + client config generation

### Performance engineering evidence

- **LLVM distributed build**: 17m → 4m (product); ~1026s → 253s on Kleckner cluster (~4×)
- **Cold/warm cache behavior** measurable via Bazel `--remote_*` flags and cache events
- **MRU worker allocation** to keep inputs warm on workers (documented scheduler strategy)
- Blake3 digest recommended; remote cache compression flags

### Operability

- JSON5 config for stores/schedulers/workers/servers
- Prometheus metrics, OpenTelemetry tracing, health endpoints
- K8s deployment examples; toolchain-examples module for validating worker images (cpp, rust, go, java, python)
- Docker prebuilt images + Nix flake for source builds

### Agent-era narrative (strategic, not Rust-internal)

- **NLFR thesis alignment:** "When AI writes the code, NativeLink makes validating it fast" — flight recorder adds **trust/provenance** layer they are also messaging (signed inputs, audit trails)
- MCP server: agent-triggered cache setup, watch-and-build — shows product thinking beyond raw RBE

### What NLFR can add that NativeLink docs don't fully productize

- **Evidence-first proof** of cache hit/miss, action graph, run comparison — with truth labels (`collectable_v1` vs `simulated_v1`)
- Honest boundary: worker identity / scheduler assignment / queue time require direct evidence (NLFR explicitly does not over-claim)

---

## 5. What a TypeScript-Skilled Outsider Should NOT Demo

Avoid areas where shallow demos backfire with NativeLink engineers or misrepresent system behavior.

### Do not demo / claim

| Avoid | Why |
|-------|-----|
| **Rust scheduler internals** | Simple scheduler, LRU/MRU allocation, queue logic — requires reading `schedulers.rs`, load testing |
| **Custom scheduler hacks** | Property Modifier / federation wrappers are config-composition problems, not UI demos |
| **Worker executor implementation** | Precondition scripts, inflight task limits, spawn/isolation — ops + Rust domain |
| **Store backend implementation** | FastSlow, compression pipelines, CAS dedup internals — infra engineering |
| **LRE / Nix toolchain pipeline** | `rbe_configs_gen`, image generators, flake.nix commit pinning — deep NativeLink contributor territory |
| **"We know which worker ran action X"** | Unless direct log evidence ingested; scheduler assignment is unsupported without proof |
| **Queue time / load distribution claims** | Same — NLFR UNSUPPORTED_CLAIMS unless collectable evidence exists |
| **Head-to-head "NativeLink beats BuildBuddy"** | No published benchmarks; engineers will challenge |
| **BuildBuddy-style results UI** | Not NativeLink's surface; BES/app.nativelink.com is separate product layer |
| **Multi-region / fleet ops** | K8s, Garage/S3 tuning, Talos clusters — Kleckner blog shows this is hard |
| **RBE without toolchain config** | Remote execution fails silently or slow-compiles without correct `--config` / platform |
| **Rust performance advocacy** | "Rust is fast" is marketing; show **measured** cache hit rate, wall time, evidence exports instead |

### Safe demo lanes for TS/NLFR outsider

1. **Cache-only proof path** — cold vs warm Bazel build through NativeLink; export hit rate and timings (`collectable_v1`)
2. **Projection canvas** — Action Graph, Proof Packet, Compare Runs from exported JSON only (no invented backend state)
3. **Agent loop closure** — deterministic patch → validate → SQLite → proof export (simulated agent + real Bazel leg)
4. **Truth labels** — explicitly mark what is proven vs simulated vs future
5. **Integration story** — Bazel `.bazelrc` flags, MCP "use nativelink" workflow, CI recipe — config not internals
6. **Redacted evidence** — hashes, spans, paths; never secrets or raw private logs

---

## Demo Strategy Implications for NLFR

**Audience split:**

- **NativeLink builders** — respect protocol, hermeticity, and evidence boundaries; impress with honest cache proof + export pipeline, not scheduler cosplay
- **Buyers / platform teams** — lead with wall-time and cost stories (Thirdwave, LLVM, 10× claims) backed by reproducible local proof scripts
- **Agent-era narrative** — pair "fast validation" (NativeLink cache) with "trustworthy validation" (NLFR proof packet)

**Recommended demo arc:**

1. `nlfr doctor --mode cache-only` — environment gate
2. Cold/warm run — measurable hit rate delta
3. Export graph + proof JSON — show truth labels
4. Canvas tour — projection-only lenses
5. Explicit "unproven" slide — worker placement, queue time (builds credibility with engineers)

**Do not lead with:** Rust architecture slides, scheduler diagrams as if implemented, or competitor trash-talk.

---

## Source Index

| Source | URL |
|--------|-----|
| GitHub README | https://github.com/TraceMachina/nativelink |
| Product page | https://nativelink.com/product |
| Architecture docs | https://tracemachina-nativelink.mintlify.app/concepts/architecture |
| Remote execution docs | https://tracemachina-nativelink.mintlify.app/concepts/remote-execution |
| Bazel integration | https://tracemachina-nativelink.mintlify.app/integration/bazel |
| LRE explanation | https://nativelink.com/docs/explanations/lre/ |
| Bazel RE services list | https://bazel.build/community/remote-execution-services |
| v1.0.0 release | https://github.com/TraceMachina/nativelink/releases/tag/v1.0.0 |
| LLVM + recc blog | https://reidkleckner.dev/posts/llvm-recc-nativelink/ |
| MCP server | https://github.com/TraceMachina/nativelink-mcp-server |
| NLFR one-pager (internal) | `docs/ONE_PAGER.md` |
