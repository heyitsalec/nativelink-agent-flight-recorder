# NLFR Docs Index

Start here when reviewing the NativeLink Agent Flight Recorder. The root
[README](../README.md) explains the product; this index routes reviewers to
architecture, adoption paths, proof artifacts, and orchestration mirrors.

## Fast Review Path

1. Read the root [README](../README.md) for the product story and local run
   commands.
2. Read [One pager](ONE_PAGER.md) for thesis, proven claims, and explicit
   unproven boundaries.
3. Read [Walkthrough](WALKTHROUGH.md) for the guided tour from commands to
   canvas and proof artifacts.
4. Read [Adoption guide](ADOPTION_GUIDE.md) for the 5-minute fixture path and
   30-minute Nix proof path on an independent host.
5. Drop into [Architecture track](ARCHITECTURE_TRACK.md) or
   [DAG mirrors](dags/README.md) when you need milestone scope, review gates,
   or broker handoffs.

## Core Docs

- [One pager](ONE_PAGER.md) — thesis, proven vs unproven claims, evaluator paths.
- [Architecture track](ARCHITECTURE_TRACK.md) — L0–L2 evidence spine, milestone
  gates, and product-shape fork rules.
- [Walkthrough](WALKTHROUGH.md) — guided tour from Bazel/NativeLink run to
  SQLite ingest, projection JSON, and canvas.
- [Adoption guide](ADOPTION_GUIDE.md) — no-Nix fixture path and Nix toolchain
  path for evaluators off the author's machine.
- [CI recipe](CI_RECIPE.md) — GitHub Actions proof jobs and local Linux
  reproduction.
- [Media capture](MEDIA_CAPTURE.md) — hero GIF capture scripts, truth-label
  visibility checks, and regeneration commands.
- [Demo script](DEMO_SCRIPT.md) — Tier 1/2/3 rehearsal paths (Tier 2 for NativeLink team)
- [Usefulness roadmap](USEFULNESS_ROADMAP.md) — what the MVP does today, what
  makes it useful, and what to build next.
- Root [README](../README.md) — product framing, quick start, and release
  boundary.

## DAG Mirrors

Orchestration mirrors live under [`docs/dags/`](dags/README.md). Use them for
Linear ticket scope, wave boundaries, and broker handoff contracts.

| Track | Mirror | Spec |
|-------|--------|------|
| Architecture (M1–M9) | [dags/architecture-track.md](dags/architecture-track.md) | [ARCHITECTURE_TRACK.md](ARCHITECTURE_TRACK.md) |
| M5–M9 umbrella | [dags/m5-m9-umbrella.md](dags/m5-m9-umbrella.md) | [CI_RECIPE.md](CI_RECIPE.md) |
| Doc capture (PER-1071) | [dags/doc-capture-pass.md](dags/doc-capture-pass.md) | this index + [MEDIA_CAPTURE.md](MEDIA_CAPTURE.md) |
| Dogfood A — generic recorder | [dags/dogfood-a-generic-recorder.md](dags/dogfood-a-generic-recorder.md) | — |
| Dogfood B — canvas dogfood | [dags/dogfood-b-canvas-dogfood.md](dags/dogfood-b-canvas-dogfood.md) | — |
| Review gates | [dags/review-gates.md](dags/review-gates.md) | — |
| Vision (completed) | [dags/vision-a-tryout.md](dags/vision-a-tryout.md) … [vision-d-integration.md](dags/vision-d-integration.md) | — |

Full index: [dags/README.md](dags/README.md).

## Proof & Media

Use these when validating claims or refreshing public-safe artifacts.

| Resource | Purpose |
|----------|---------|
| [proof-samples/](proof-samples/README.md) | Redacted `summary.json` excerpts (`collectable_v1` / `simulated_v1`) without running Nix |
| [CI recipe](CI_RECIPE.md) | Linux/x86_64 GitHub Actions proof lane |
| [Media capture](MEDIA_CAPTURE.md) | Hero GIF regeneration (`capture:tour`, `capture:evidence`, `test:truth`) |
| `scripts/cold-warm-cache-proof.sh` | Cold/warm cache economics proof |
| `scripts/agent-loop-proof.sh` | Agent → change → validation chain proof |
| `scripts/verify-demo.sh` | Fixture-backed canvas path (no NativeLink) |

Proof commands (full local spine):

```bash
python3 -m pytest
python3 -m nlfr doctor --mode cache-only
./scripts/verify-demo.sh
```

See [Contributing](CONTRIBUTING.md) for contributor proof expectations.

## Handoffs

Broker-coordinated sessions write rich artifacts under
[`docs/sessions/handoffs/`](sessions/handoffs/README.md). Parent chats carry
JSON summaries and paths only.

| DAG | Handoff dir |
|-----|-------------|
| M5–M9 umbrella | [sessions/handoffs/m5-m9-umbrella/](sessions/handoffs/m5-m9-umbrella/) |
| Doc capture (PER-1071) | [sessions/handoffs/nlfr-doc-capture/wave-1/](sessions/handoffs/nlfr-doc-capture/wave-1/) |

Templates: [HANDOFF_TEMPLATE.md](sessions/handoffs/HANDOFF_TEMPLATE.md).
