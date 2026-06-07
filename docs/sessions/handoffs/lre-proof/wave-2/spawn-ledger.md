# Spawn ledger — lre-proof wave-2 (LRE substrate)

**Coordinator:** `coord-lre-proof`  
**DAG:** `docs/dags/lre-proof.md`  
**Branch:** `feat/lre-fleet-unlocks`  
**KOS:** `docs/sessions/handoffs/unlock-wave/KOS-startup-routing.md`

| worker_id | type | write_scope | status | provenance |
|-----------|------|-------------|--------|------------|
| lre-w2-config-readme | worker | `demo/nativelink/lre.json5`, `demo/nativelink/README.md` | DONE | `provenance-lre-w2-config-readme.md` |
| lre-w2-proof-script | worker | `scripts/lre-proof.sh`, `docs/proof-samples/*` | DONE | `provenance-lre-w2-proof-script.md` |
| lre-w2-tests | worker | `tests/test_lre_proof.py` | DONE | `provenance-lre-w2-tests.md` |
| lre-w2-ci-probe | worker | `.github/workflows/nlfr-proof.yml` | DONE | `provenance-lre-w2-ci-probe.md` |
| lre-w2-handoffs | worker | `docs/sessions/handoffs/lre-proof/wave-2/**`, `docs/dags/lre-proof.md` | DONE | `provenance-lre-w2-handoffs.md` |

**Ceiling:** `lre_substrate_ready` (`collectable_v1`, `medium`) — not hermetic Nix `--config=lre` or fleet dashboards.

**Proof gate:**

```bash
uv run pytest tests/test_lre_proof.py -q
nix develop --command ./scripts/lre-proof.sh   # when Nix toolchain available
```
