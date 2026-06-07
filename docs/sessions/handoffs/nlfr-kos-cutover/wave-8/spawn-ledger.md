# Spawn ledger — nlfr-kos-cutover wave 8 (`pr-proof-attachment`)

**DAG:** `docs/dags/nlfr-kos-roadmap-waves-5-8.md` § Wave 8  
**Branch:** `feat/docs-wiki-wave2`  
**Control plane:** `kos serve http://127.0.0.1:7423` · `dag_ref` `dag:nlfr-flagship`

## Wave-8 workers

| worker_id | coordinator | type | write_scope | KOS node | status |
|-----------|-------------|------|-------------|----------|--------|
| pr-markdown-exporter | coord-pr-markdown-exporter | worker | `src/nlfr/projectors/proof_markdown.py`, `src/nlfr/commands/export_cmds.py`, `scripts/export-pr-proof-comment.sh`, `tests/test_pr_proof_markdown.py` | `W8-PR-EXPORTER` | DONE |
| pr-sample-promote | coord-pr-sample-promote | worker | `docs/proof-samples/pr-proof-comment-sample.md`, `docs/proof-samples/README.md` | `W8-PR-SAMPLE` | DONE |
| pr-attachment-wiki | coord-pr-attachment-wiki | worker | `docs/wiki/how-to/attach-proof-to-pr.md`, `docs/CI_RECIPE.md` | `W8-PR-RECIPE` | DONE |
| w8-integrate | waves-5-8-integrate-close | worker | `docs/sessions/handoffs/nlfr-kos-cutover/wave-8/**` | `W8-INTEGRATE` | DONE |

**Dispatch order:** `pr-markdown-exporter` first; `pr-sample-promote` after exporter; `pr-attachment-wiki` parallel after W7 close; integrate last.

**Proof gate:**

```bash
./scripts/export-pr-proof-comment.sh --run-group latest
uv run pytest tests/test_pr_proof_markdown.py -q
bash -n scripts/export-pr-proof-comment.sh
```

**Stop condition:** Redaction scan — no prompt bodies, no raw `/Users` paths in committed sample.
