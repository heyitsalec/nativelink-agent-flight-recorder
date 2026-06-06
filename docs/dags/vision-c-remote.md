# Sub-DAG C — Remote execution (Ring 3)

Linear: [PER-1056](https://linear.app/gradschool/issue/PER-1056) — **Done** (Wave 1)

| Child | Status |
|-------|--------|
| C-R1 | Done |
| C-D1 | Done |
| C-I1 | Done — two workers in local-execution.json5 |
| C-I2 | Done — unsupported claims aligned (5 items) |
| C-V1 | Done — two-worker live Nix proof (`worker_endpoints_ready`, 2 configured; `data/local-exec-proof-2w/summary.json`) |

Live two-worker proof upgrades the prior config gate: two workers configured AND
endpoints opened live — not work distributed across workers. Worker identity,
scheduler assignment, queue time, action placement, and load distribution stay
unsupported.

Wave 2 (LLM spark): agent-loop closure proven — `scripts/agent-loop-proof.sh`
(`data/agent-loop-proof/summary.json`, `chain_complete=true`). Multi-machine:
armed, not started.
