# Executive summary — critical review handoff

**Audience:** Fresh Claude session or skeptical engineer with no prior chat context.  
**Ask:** Critique the repo as a **credible evidence-first recorder** and **NativeLink showcase**,
not as a finished SaaS product.

---

## One-sentence thesis

When AI writes the code, NativeLink makes validating it fast; NLFR makes validating it
**trustworthy** — by recording Bazel/NativeLink artifacts, labeling every claim, and rendering a
canvas **only** from exported projection JSON.

---

## Current verdict (2026-06-07)

| Dimension | Status | Notes |
|-----------|--------|-------|
| Evidence spine (record → ingest → project → canvas) | **Proven locally** | 140 pytest; fixture + Nix paths |
| NativeLink cache demo | **Proven** (Nix) | Cold/warm `collectable_v1` summaries |
| Agent-validation chain | **Partially proven** | Validation leg collectable; agent leg simulated or host-gated live |
| Multi-run compare (M9) | **Shipped** | `derived_v1` pairwise deltas only |
| Adoption (`nlfr init`, record-one-target) | **Shipped** | Wave 11 |
| CI / Linux skeptic path | **Blocked** | GHA offline ~1 month; local gates substitute |
| Fleet / scheduler / queue-time | **Explicitly unproven** | Policy + gap honesty packet |
| Broker umbrella (waves 1–13) | **DONE_WITH_CONCERNS** | See [03-broker-history-and-waves.md](03-broker-history-and-waves.md) |
| Open integration | **PR #10** on `feat/docs-wiki-wave2` | Docs wiki + KOS cutover completion |

**Bottom line:** NLFR is a **strong reference architecture and local proof kit**. It is **not** a
day-to-day team platform, hosted control plane, or remote-execution operations console.

---

## What was built (why, not what files)

1. **Immutable evidence path** — Because agent loops scatter truth across chat, CI logs, and cache
   hits, NLFR centralizes SHA-256-hashed artifacts in SQLite with idempotent ingest. The hard part
   is refusing to invent state later.

2. **Truth-labeled projections** — Because dashboards lie by omission, every node/metric carries
   `source_kind`, `confidence`, `evidence_refs`, and `redaction_state`. The canvas is a read-only
   projection consumer.

3. **Cache economics from real runs** — Because NativeLink's value story is speed via cache/RBE,
   cold/warm proof exports measurable hit rates and durations — without claiming dollar savings or
   org-wide fleet behavior.

4. **Bounded agent loop** — Because "AI wrote it" needs an audit trail, the graph links
   `agent → change → run → target → action → cache_event`. Agent provenance stores model label +
   prompt hash only; raw prompts never leave the operator boundary.

5. **Honest remote boundary** — Because RBE marketing outruns evidence, Remote Boundary and proof
   packets list **unsupported** claims. Worker identity is **conditional** (M7 stdout parser), not
   blanket fleet proof.

6. **Adoption + history layer (waves 10–13)** — Because a proof kit nobody can rerun isn't useful,
   `nlfr init`, compare history, PR markdown exporter, and canvas ergonomics (8-node cap, lenses)
   reduce friction — still without fleet UI.

7. **Broker + KOS orchestration** — Because multi-wave agent work needs receipts, `dag:nlfr-flagship`
   on `kos serve` tracks wave closure; handoffs live under `docs/sessions/handoffs/nlfr-kos-cutover/`.

---

## Explicit unproven boundaries (do not let review slide these)

| Claim | Status |
|-------|--------|
| Scheduler assignment | **Unproven** |
| Queue time | **Unproven** |
| Action placement / work distribution across workers | **Unproven** |
| Multi-machine fleet behavior | **Unproven** |
| Org-scale run history / trends | **Unproven** (pairwise compare only) |
| Sustained green Linux CI | **Blocked** (GHA offline) |
| Live Cursor agent on every host | **Host-gated** (M8) |
| LRE Linux parity on author's Mac | **Host-gated** (Darwin) |
| Worker identity | **Conditional** — only with M7 admin stdout attached pre-ingest |

Research matrix: [docs/dags/future-fleet-claims.md](../../../dags/future-fleet-claims.md).

---

## Career / portfolio framing (honest)

NLFR is best understood as:

- **Portfolio evidence** for roles touching agentic dev infra, build systems, or platform
  observability — showing you can design **evidence contracts** instead of flashy dashboards.
- **NativeLink narrative asset** — a companion demo that says "here's how you make cache/RBE outcomes
  auditable when agents change code," not "here's a replacement for NativeLink ops."
- **Agentic workflow story** — broker waves + KOS control plane demonstrate structured multi-session
  delivery; the product itself stays conservative about live LLM integration.

It is **not** (yet): a funded startup MVP, a hiring guarantee, or proof of production fleet
operations. Reviewers should separate **architecture credibility** from **commercial traction**.

---

## Recommended first 30 minutes for reviewer

### Minutes 0–5: Thesis + limits

1. Read [docs/ONE_PAGER.md](../../../ONE_PAGER.md) — especially "explicitly unproven."
2. Skim this doc's unproven table above.

### Minutes 5–15: Spine without Nix

```bash
cd /path/to/nativelink-agent-flight-recorder
uv sync && npm --prefix apps/canvas install
uv run pytest -q
PYTHONPATH=src uv run python -m nlfr doctor --mode cache-only --json
npm --prefix apps/canvas run preview
# Open http://127.0.0.1:5174/ — confirm green canvas-dev collectable_v1 banner
```

**Probe:** Open Proof Packet and Remote Boundary lenses. Do unsupported claims appear? Does the
truth legend match node `source_kind` in exported JSON?

### Minutes 15–25: Evidence samples (no live Nix required)

1. Open `docs/proof-samples/cold-warm-summary.json` — say aloud: **collectable_v1**.
2. Open `docs/proof-samples/two-worker-summary.json` — **endpoint readiness only**, not distributed work.
3. Open `docs/proof-samples/agent-loop-summary.json` — **mixed** labels (validation collectable, agent simulated).
4. Follow [docs/DEMO_SCRIPT.md](../../../DEMO_SCRIPT.md) Tier 2 cue cards — verify presenter obligations
   match file contents.

### Minutes 25–30: Integration surface + residuals

1. Read [PR #10](https://github.com/heyitsalec/nativelink-agent-flight-recorder/pull/10) summary and
   residual concerns section.
2. Read [umbrella-close-packet.md](../nlfr-kos-cutover/wave-14/umbrella-close-packet.md) honest residuals (C-UMB-1 through C-UMB-6).
3. Decide: merge PR with documented concerns, or block on GHA / live proof gaps?

---

## Red flags worth challenging

1. **Canvas default is real dogfood** (`canvas-dev` `collectable_v1`) — good — but easy to confuse
   with agent-loop fixture shape. Check banner and proof-samples narration.
2. **"Two-worker proof"** — proves endpoints opened, not load distribution. Any copy implying fleet
   scale is wrong.
3. **Compare lens** — `derived_v1` diffs across SQLite run groups; must not imply worker correlation.
4. **GHA offline** — local scripts are intentional substitute; absence of CI green is a real skeptic
   objection, not a footnote.
5. **Broker DONE_WITH_CONCERNS** — many waves shipped UX/docs while live proof paths remain
   host-gated. Distinguish **landed code** from **landed proof**.

---

## Suggested review outputs

1. **Claim audit** — table of user-visible claims vs `source_kind` in code/tests.
2. **Merge recommendation** for PR #10 with explicit conditions.
3. **Next milestone** — pick one: GHA restore, fleet evidence parser, or reference-kit polish (see
   [USEFULNESS_ROADMAP.md](../../../USEFULNESS_ROADMAP.md) product-shape fork).

---

← [README — handoff index](README.md) · Next: [01-product-vision-and-thesis.md](01-product-vision-and-thesis.md)
