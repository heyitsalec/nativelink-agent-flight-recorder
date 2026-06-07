# LRE proof — broker DAG (blocker-gated)

**Parent:** PER-1058 architecture track Phase 3+  
**Handoffs:** `docs/sessions/handoffs/lre-proof/`

## Objective

Record NativeLink **Local Remote Execution** when `demo/nativelink/lre.json5` exists and toolchain is stable.

## Current ceiling (honest)

Without LRE config, `scripts/lre-proof.sh` writes `environment-blocker.json` with `collectable_v1` probe metadata. NLFR does **not** invent LRE claims.

**Supported today:** cache-only, local-exec smoke, two-worker endpoint readiness.

## Proof commands

```bash
nix develop --command ./scripts/lre-proof.sh
```

## Broker rule

Do not spawn implement workers for fleet/scheduler UI. LRE config addition requires NativeLink upstream toolchain artifacts — track in `environment-blocker.json` `next_step`.
