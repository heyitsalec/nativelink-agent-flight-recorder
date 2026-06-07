# lre-proof — spawn ledger

| worker | wave | status | artifact |
|--------|------|--------|----------|
| lre-proof-script | wave-1 | DONE | `scripts/lre-proof.sh` |
| lre-proof-dag | wave-1 | DONE | `docs/dags/lre-proof.md` |
| lre-ci-probe | wave-1 | DONE | workflow job `lre-proof-probe` |
| lre-proof-tests | wave-1 | DONE | `tests/test_lre_proof.py` |
| lre-w2-config-readme | wave-2 | DONE | `demo/nativelink/lre.json5`, README |
| lre-w2-proof-script | wave-2 | DONE | proof samples + script verify |
| lre-w2-tests | wave-2 | DONE | 4 fixture tests |
| lre-w2-ci-probe | wave-2 | DONE | CI substrate proof job |
| lre-w2-handoffs | wave-2 | DONE | `wave-2/` handoff closure |
| lre-nix-research | wave-3 | DONE | TraceMachina LRE flake pattern |
| lre-nix-flake-wire | wave-3 | DONE | `flake.nix` + `flake.lock` LRE module |
| lre-nix-bazel-wire | wave-3 | DONE | `MODULE.bazel` + `.bazelrc` consumer |
| lre-nix-proof | wave-3 | DONE | `lre-nix-toolchain-proof.sh` + tests |
| lre-nix-ci | wave-3 | DONE | CI `lre-nix-ci` job |
| lre-wave3-handoffs | wave-3 | DONE | `wave-3/` handoff closure |

**Status:** `lre_bazelrc_generated` — phase-2 Nix toolchain wired; cache parity and fleet UI remain blocked.

**Handoffs:** `docs/sessions/handoffs/lre-proof/wave-3/` · **DAG:** `docs/dags/lre-proof.md`
