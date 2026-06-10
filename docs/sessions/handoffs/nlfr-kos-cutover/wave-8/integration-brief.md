# Wave 8 Integration Brief — pr-proof-attachment

**Date:** 2026-06-06  
**Worker:** `waves-5-8-integrate-close`  
**Status:** SHIPPED  
**Branch:** `feat/docs-wiki-wave2`  
**Prerequisite:** Wave 7 `W7-INTEGRATE` done

---

## Wave-8 coordinators

| Coordinator | Worker | KOS node | Status | Summary |
|-------------|--------|----------|--------|---------|
| `coord-pr-markdown-exporter` | `pr-markdown-exporter` | `W8-PR-EXPORTER` | SHIPPED | `proof export --format markdown`, `scripts/export-pr-proof-comment.sh` |
| `coord-pr-sample-promote` | `pr-sample-promote` | `W8-PR-SAMPLE` | SHIPPED | `docs/proof-samples/pr-proof-comment-sample.md` — redacted sample |
| `coord-pr-attachment-wiki` | `pr-attachment-wiki` | `W8-PR-RECIPE` | SHIPPED | `docs/wiki/how-to/attach-proof-to-pr.md`, `docs/CI_RECIPE.md` PR section |
| `w8-integrate` | `waves-5-8-integrate-close` | `W8-INTEGRATE` | DONE | This brief, spawn ledger, worker-results, KOS close |

---

## Landed deliverables

| Layer | Artifacts |
|-------|-----------|
| Markdown exporter | `src/nlfr/projectors/proof_markdown.py`, `src/nlfr/commands/export_cmds.py` |
| Shell wrapper | `scripts/export-pr-proof-comment.sh` |
| Sample | `docs/proof-samples/pr-proof-comment-sample.md` |
| Wiki how-to | `docs/wiki/how-to/attach-proof-to-pr.md` |
| Hub | `docs/proof-samples/README.md` (PR attachment section) |
| Tests | `tests/test_pr_proof_markdown.py` |

---

## Claim boundary

**Supported:** redacted markdown summary with `source_kind` / `confidence` labels; exit-code policy separates validation failure from unsupported boundary labels.

**Out of scope:** GitHub PR comment bot (`future`).

---

## Proof (local)

```bash
./scripts/export-pr-proof-comment.sh --run-group latest
uv run pytest tests/test_pr_proof_markdown.py -q
bash -n scripts/export-pr-proof-comment.sh
```

---

## Handoff index

- Spawn ledger: [`spawn-ledger.md`](spawn-ledger.md)
- Worker results: [`worker-results.json`](worker-results.json)
- Four-wave plan: [`../wave-5/four-wave-plan-5-8.md`](../wave-5/four-wave-plan-5-8.md)
