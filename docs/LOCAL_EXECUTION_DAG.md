# Local Remote Execution Worker Proof DAG

> **Historical snapshot.** This planning doc records local
> remote-execution worker proof completion.
> For current product truth and milestone status, use **[ONE_PAGER.md](ONE_PAGER.md)**
> and **[ARCHITECTURE_TRACK.md](ARCHITECTURE_TRACK.md)**.
> Deep dives: **[Wiki hub](wiki/README.md)**.

## Objective

Turn the NLFR `local-exec` scaffold into a credible NativeLink remote-execution
proof path while keeping the demo zero-LLM by default.

The first gate is a one-process remote-executor smoke: Bazel is configured for
remote execution, NativeLink endpoints are reachable, and NLFR records the
artifacts. Later gates can grow this into one-worker, two-worker, and
multi-machine evidence once direct worker proof is capturable.

## Product Thesis

Build NativeLink worker proof before spending LLM tokens.

The tryout-grade demo should feel impressive because the validation substrate is
real: deterministic agents create repeatable load, NativeLink is the substrate
we are proving toward acceleration/distribution, and NLFR proves inspectability
of captured evidence.

## Children

- Reproducible local-exec environment. Done.
- Remote execution evidence model. Done.
- One-worker then two-worker smoke. Done.
- Canvas remote execution lens. Done.
- Completion review and tryout packet. Done.

## Current State

This track is complete for this host's available proof boundary:

- repo docs, Linear, proof commands, and visual artifacts are reconciled;
- the tryout packet captures the zero-LLM worker-first strategy;
- the final parent claim is limited to recorded evidence and environment
  blockers on this host;
- worker identity is **conditional** on M7 admin stdout; queue time, scheduler
  assignment, action placement, and load distribution remain follow-ups until
  direct NativeLink worker evidence exists beyond M7.

Completed worker-readiness behavior:

- `scripts/local-exec-proof.sh` writes `worker-readiness.json`;
- one-worker smoke records config and endpoint readiness when tools are present;
- `NLFR_EXPECTED_WORKERS=2 scripts/local-exec-proof.sh` gates future two-worker
  proof and blocks against the current one-worker config;
- the canvas Remote Boundary lens renders remote execution and worker-readiness
  proof blocks without inventing worker/scheduler state.

Future full-LRE runs should use repeatable Bazel passthrough args such as
`--bazel-arg=--config=lre` and
`--bazel-arg=--remote_default_exec_properties=cpu_count=1`.

## Proof Gates

```bash
uv run pytest tests -q
npm --prefix apps/canvas run build
scripts/verify-demo.sh
scripts/local-exec-proof.sh
```

On hosts without Bazel or NativeLink, `scripts/local-exec-proof.sh` should write
truth-labeled `environment-blocker.json` and exit nonzero. That blocker is valid
evidence for host readiness; it is not a successful remote-execution proof.

Canvas proof requires:

```bash
npm --prefix apps/canvas run capture
```

## Privacy

Use only local demo workspaces, deterministic simulated-agent scenarios, and
generated build evidence. Do not ingest secrets, raw private logs, raw prompts,
customer data, or private legacy source material.

## Stop Conditions

- Local execution proof would need to claim worker identity without M7 admin
  stdout, or claim queue time or scheduling behavior without direct evidence.
- NativeLink/Bazel cannot run and the blocker path fails to record durable
  evidence.
- The work drifts into token-heavy real-agent demos before worker proof is
  stable.
- Linear/Git/repo state conflicts would mislead the next agent.
