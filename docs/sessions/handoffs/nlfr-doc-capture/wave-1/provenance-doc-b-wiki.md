# DOC-B wiki provenance (wave-1)

- **Date:** 2026-06-06
- **Branch:** `feat/m5-m9-umbrella`
- **Linear:** PER-1073 (NLFR-DOC-B)
- **Parent DAG:** PER-1071 (doc-capture-pass)
- **Reference:** Harmony docs index at `/Users/alecbot/Documents/harmony/docs/INDEX.md`

## Scope

Professional open-source documentation wiki pass:

1. Rewrite `docs/INDEX.md` as NLFR docs hub (Harmony-style routing).
2. Add `docs/CONTRIBUTING.md` (pytest, proof scripts, media regen, truth labels).
3. Cross-link `WALKTHROUGH.md`, `ADOPTION_GUIDE.md`, `ONE_PAGER.md`,
   `USEFULNESS_ROADMAP.md` back to INDEX (top + bottom).
4. Update `docs/dags/README.md` with doc-capture-pass mirror.
5. Write this provenance file.

Explicitly **not** in scope: root `README.md` rewrite (PER-1074 / DOC-C).

## Files touched

| File | Action |
|------|--------|
| `docs/INDEX.md` | Rewritten — replaced Symphony auto-generated stub |
| `docs/CONTRIBUTING.md` | Created |
| `docs/WALKTHROUGH.md` | Added INDEX cross-links |
| `docs/ADOPTION_GUIDE.md` | Added INDEX cross-links |
| `docs/ONE_PAGER.md` | Added INDEX cross-links |
| `docs/USEFULNESS_ROADMAP.md` | Added INDEX cross-links |
| `docs/dags/README.md` | Added doc-capture-pass section |
| `docs/sessions/handoffs/nlfr-doc-capture/wave-1/provenance-doc-b-wiki.md` | Created |

## INDEX sections

1. Fast Review Path (5 steps)
2. Core Docs (7 linked guides + README)
3. DAG Mirrors (table + dags/README pointer)
4. Proof & Media (samples, CI, scripts, pytest)
5. Handoffs (active DAG dirs + template)

## Verification

- No code or test changes; documentation-only pass.
- `MEDIA_CAPTURE.md` linked from INDEX as DOC-A deliverable (PER-1072); not
  authored in this workstream.
- Cross-links use relative `INDEX.md` paths within `docs/`.

## Notes

- Prior `docs/INDEX.md` was a Symphony standards corpus stub marked
  auto-generated; safe to replace for OSS wiki routing.
- Harmony INDEX pattern: fast review path → core → components/tracks → proof →
  handoff/launch copy. NLFR adaptation maps components to DAG mirrors and proof
  samples instead of Fleet/Cockpit splits.
