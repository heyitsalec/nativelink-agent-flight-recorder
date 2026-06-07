# Frontier wave — broker ARM

**Date:** 2026-06-06  
**Status:** ARMED

## Operator intent

Broker three frontier DAGs in parallel where write scopes are disjoint:

1. **tier1-live-bazel** — live acts 1+2 with real Bazel, refresh proof samples
2. **fleet-evidence-v1** — capture + ingest `nativelink.stdout.txt` on all remote-exec proof scripts
3. **lre-cache-parity** — research → implement cold/warm LRE parity probe (Linux-CI-gated)

## Wave-1 dispatch

Spawn coordinators in parallel → workers → parent proof gates.
