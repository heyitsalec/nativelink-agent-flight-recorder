# CI recipe (M5)

How NLFR proofs run on an independent Linux/x86_64 host (GitHub Actions).

## Workflow file

[`.github/workflows/nlfr-proof.yml`](../.github/workflows/nlfr-proof.yml) — three jobs:

| Job | Host | What it proves |
|-----|------|----------------|
| `unit` | `ubuntu-latest` | `pytest`, `scripts/record-proof.sh`, canvas build |
| `linux-nix-toolchain` | `ubuntu-latest` + Nix flake | `cold-warm-cache-proof.sh`, `agent-loop-proof.sh` |
| `verify-demo-fixture` | `ubuntu-latest` | `verify-demo.sh` (fixture path, no live NativeLink) |

See [M5 implementation spec](dags/m5-ci-proof.md).

## Local reproduction (Linux)

```bash
# Fast path (no Nix)
pip install uv
uv sync
uv run pytest -q
./scripts/record-proof.sh

# Full toolchain (inside repo)
nix develop --command bash -lc '
  uv sync
  ./scripts/cold-warm-cache-proof.sh
  ./scripts/agent-loop-proof.sh
'
```

## Artifacts

CI uploads:

- `data/record-proof/summary.json` — generic record gate (`collectable_v1`)
- `data/cold-warm-proof/summary.json` — cache economics
- `data/agent-loop-proof/summary.json` — agent loop chain

If NativeLink/Bazel unavailable, scripts write `environment-blocker.json` with `collectable_v1` status — never fake success.

## Redaction for committed samples

After a green CI run, redact absolute paths and copy summaries to [`proof-samples/`](proof-samples/) per [`proof-samples/README.md`](proof-samples/README.md).

## Honesty gates

- Do not claim CI passed if only `unit` job ran and toolchain job recorded `environment_blocker`.
- Document which job produced which claim in ADOPTION_GUIDE.
