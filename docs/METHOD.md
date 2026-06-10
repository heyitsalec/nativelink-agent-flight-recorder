# How this repo was built

**Quadrant:** Explanation · **Audience:** anyone curious why an evidence
recorder has this much process behind it.

NLFR's product thesis is that agent-driven engineering work should ship with
labeled, inspectable evidence instead of vibes. The repo was built the same
way: most of the code and documentation here was produced by AI coding agents,
coordinated by a human, under the same truth-label discipline the product
enforces.

## Contracts before code

Every milestone started from an explicit claim boundary: what the change would
prove, what evidence would back it, and what it would *not* claim. JSON
contracts (artifact manifest, proof packet, projections) and their fixtures
were designed before the parsers and projectors that fill them. Tests assert
the contracts, and the canvas renders only what the contracts carry — so an
agent could not "improve" the demo by inventing state.

## Multi-wave agent coordination

Work was organized as a dependency graph of small, scoped tasks and executed
in waves:

- A coordinating session (Claude) decomposed each milestone into worker tasks
  with explicit objectives, file-write boundaries, and proof commands.
- Worker agents executed tasks in parallel where the graph allowed, each
  inside its own scope — a worker improving parsers could not touch canvas
  code, and vice versa.
- Each wave landed as a reviewable pull request with proof gates attached:
  `uv run pytest -q`, `./scripts/verify-demo.sh`, shell-syntax checks, and —
  for real-toolchain claims — Nix proof scripts that write `summary.json`
  evidence.
- Results were reviewed against the claim boundary before merge. Outcomes
  that fell short were recorded as such (for example, blocked environments
  produce `environment_blocker` evidence rather than a green checkmark).

The planning records for the shipped milestones are kept under
[`docs/dags/`](dags/README.md). The full wave-by-wave working notes were
internal scaffolding and were removed before open-sourcing; they remain in
git history.

## Why the same discipline twice

A recorder that polices claims has to survive the question: "was *it* built
honestly?" Applying the product's own rules to its development — evidence
before claims, labeled confidence, explicit unproven boundaries — was the
cheapest way to keep the answer "yes". Where the repo falls short of a claim
(see [ONE_PAGER.md](ONE_PAGER.md) for the explicit unproven list), the docs
say so instead of rounding up.

## What this means for evaluating the repo

- Trust the artifacts, not the narration: every proven claim points at a
  test, script, or committed `summary.json`.
- AI authorship is disclosed, bounded, and recorded — the M8 adapter exists
  precisely because we wanted agent changes captured as `model` +
  `prompt_sha256` provenance, never raw prompts.
- If you want to audit the process itself, the git history preserves the
  per-wave pull requests and their proof gates.
