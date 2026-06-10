# CI proof lane

**Caption:** `.github/workflows/nlfr-proof.yml` lanes exercise the evidence spine on `ubuntu-latest`. **As of 2026-06-06, GHA is treated as offline/non-green** — local gates substitute for CI; do not block ship on workflow green.

```mermaid
flowchart TB
    subgraph trigger["Triggers"]
        PUSH["push: main, codex/**, fix/**"]
        PR["pull_request"]
        WD["workflow_dispatch"]
    end

    subgraph unit["Job: unit\n~20 min"]
        U1["uv run pytest -q"]
        U2["nlfr doctor --mode cache-only"]
        U3["tier1 dry-run scripts"]
        U4["record-proof.sh"]
        U5["canvas build + test:truth"]
        U1 --> U2 --> U3 --> U4 --> U5
    end

    subgraph nix["Job: linux-nix-toolchain\n~90 min"]
        N1["cold-warm-cache-proof.sh"]
        N2["agent-loop-proof.sh"]
        N1 --> N2
    end

    subgraph tier1["Job: tier1-bazel\n~45 min"]
        T1["tier1-bazel-ci-proof.sh"]
    end

    subgraph lre["Jobs: LRE lane"]
        L1["lre-proof-probe\nlre-proof.sh"]
        L2["lre-nix-ci\nlre-nix-toolchain-proof.sh"]
        L3["lre-cold-warm-ci\nlre-cold-warm-proof.sh"]
    end

    subgraph fixture["Job: verify-demo-fixture\n~20 min"]
        F1["verify-demo.sh"]
    end

    trigger --> unit & nix & tier1 & lre & fixture

    subgraph artifacts["Uploaded artifacts"]
        A1["record-proof/"]
        A2["nix-toolchain-proof/"]
        A3["lre-cold-warm-proof/\nsummary or environment-blocker"]
    end

    unit --> A1
    nix --> A2
    lre --> A3
```

## GHA offline — operator notes

| Topic | Policy while GHA offline |
|-------|--------------------------|
| Ship / merge gate | **Local only:** `uv run pytest -q`, `bash -n scripts/*.sh`, DAG-specific proof scripts |
| CI green badge | **Not required** — do not document workflows as passing until they actually pass |
| `lre-cold-warm-ci` green | **Deferred** — cite blocker sample or manual Linux+Nix run; not a broker-blocking gate |
| LRE parity claim | Script + tests + blocker samples supported locally; `lre_cache_parity_observed` from CI **not claimed** |
| Revisit trigger | First sustained green on `nlfr-proof.yml` or operator declares GHA restored |

**Local substitute matrix:**

```bash
# Parent proof gates (always)
uv run pytest -q
bash -n scripts/*.sh

# Canvas / record path
./scripts/record-proof.sh
npm --prefix apps/canvas run test:truth

# Optional when Nix available
nix develop --command ./scripts/cold-warm-cache-proof.sh
nix develop --command ./scripts/agent-loop-proof.sh
nix develop --command ./scripts/lre-cold-warm-proof.sh
```

## Honesty notes

| Lane | `source_kind` when job succeeds | `confidence` | When job fails / GHA offline |
|------|--------------------------------|--------------|------------------------------|
| `unit` + `record-proof` | `collectable_v1` | `high` | Local `record-proof.sh` + pytest prove same boundary |
| `linux-nix-toolchain` | `collectable_v1` | `high` | Run scripts in `nix develop` on host; defer CI artifact |
| `tier1-bazel` | `collectable_v1` | `high` | `environment-blocker.json` is honest outcome |
| `lre-*` jobs | `collectable_v1` or blocker artifact | `medium` | Do not claim CI green; use `docs/proof-samples/lre-cold-warm-proof-blocker-sample.json` |
| `verify-demo-fixture` | `simulated_v1` | `medium` | Fixture path — not live Bazel proof |

**Evidence refs:** `.github/workflows/nlfr-proof.yml`, `data/*/summary.json`, `data/*/environment-blocker.json`.
