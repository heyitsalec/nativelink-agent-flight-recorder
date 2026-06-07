# Provenance — fel-w0-scripts-capture

**Worker:** `fel-w0-scripts-capture`  
**Wave:** 0  
**Write scope:** `scripts/local-exec-proof.sh`, `scripts/worker-evidence-proof.sh`, `docs/sessions/handoffs/fleet-evidence-v1/wave-0/research-nativelink-stdout-formats.md`  
**Status:** `DONE`

---

## Executive summary

Extended local-exec proof to attach `nativelink.stdout.txt` and
`nativelink.stderr.txt` into `artifact_root` before ingest; removed the live-path
stdout copy workaround from worker-evidence proof. Documented capture surfaces,
M7 parser contract, and remaining script gaps in wave-0 research.

---

## Deliverables written

| File | Action |
|------|--------|
| `scripts/local-exec-proof.sh` | Extended `write_artifact` block for stdout/stderr |
| `scripts/worker-evidence-proof.sh` | Removed post-run `cp` of stdout on live path |
| `docs/sessions/handoffs/fleet-evidence-v1/wave-0/research-nativelink-stdout-formats.md` | Created — capture matrix + gap analysis |
| This file | Created |

---

## Proof

```bash
bash -n scripts/local-exec-proof.sh scripts/worker-evidence-proof.sh
uv run pytest tests/test_worker_admin_stdout.py tests/test_worker_readiness.py -q
# 10 passed
```

---

## Claims touched

- `worker_identity` — conditional when stdout attached and M7 regex matches
- `worker_endpoints_ready` — unchanged (readiness probe)

## Blockers

None for wave-0 scope. `agent-loop-proof.sh` and `cold-warm-cache-proof.sh` deferred to wave-1.
