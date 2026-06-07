# Wave 1 NLFR Doc Capture Provenance — PER-1074 (NLFR-DOC-C)

**Worker:** NLFR-DOC-C  
**Linear:** PER-1074  
**Host:** `/Users/alecbot/Documents/nativelink-agent-flight-recorder`  
**Branch:** `feat/m5-m9-umbrella`  
**When:** 2026-06-06  

## Scope

Harmony-style root README rewrite and media index:

| Deliverable | Path |
|-------------|------|
| Root README (Harmony structure) | `README.md` |
| Media inventory | `docs/media/README.md` |
| This provenance | `docs/sessions/handoffs/nlfr-doc-capture/wave-1/provenance-doc-c-readme.md` |

## Reference

- Harmony README: `/Users/alecbot/Documents/harmony/README.md`
- DOC-A capture provenance: `provenance-doc-a-capture.md` (hero GIFs)
- DOC-B wiki provenance: `provenance-doc-b-wiki.md` (docs index, CONTRIBUTING)

## Inputs

| Prerequisite | Status |
|--------------|--------|
| `docs/media/nlfr-canvas-tour.gif` | Present (707,778 bytes, DOC-A) |
| `docs/media/nlfr-evidence-loop.gif` | Present (651,868 bytes, DOC-A) |
| `docs/images/*.png` still frames | Present (walkthrough copies) |
| Prior README proof commands | Preserved in Run Locally + verifier sections |

## README structure

1. Title + one-line tagline
2. Centered hero block with both GIFs and captions
3. The Loop — record → ingest → project → inspect → compare
4. What You Get table (+ still-frame links)
5. Run Locally — Path A fixture, Path B Nix, canvas dev, full verifier
6. Architecture brief → `docs/INDEX.md`, `docs/ONE_PAGER.md`
7. Truth labels / public-safe guarantees
8. Review Path → `docs/INDEX.md`
9. Status and limits (v1 scope)
10. Contributing → `docs/CONTRIBUTING.md`

Replaced static PNG heroes (`docs/images/canvas-*.png`) in README hero block with
GIFs. Still frames retained in What You Get and linked from `docs/media/README.md`.

## Files touched

| File | Action |
|------|--------|
| `README.md` | Rewritten — Harmony-style structure, GIF heroes, preserved proof commands |
| `docs/media/README.md` | Created — GIF + still-frame inventory |
| `docs/sessions/handoffs/nlfr-doc-capture/wave-1/provenance-doc-c-readme.md` | Created |

## Verification

| Check | Result |
|-------|--------|
| Hero GIF paths exist | PASS — `docs/media/nlfr-canvas-tour.gif`, `docs/media/nlfr-evidence-loop.gif` |
| Proof commands preserved | PASS — pytest, doctor, run, graph/proof export, verify-demo, Nix scripts |
| Truth-label honesty | PASS — fixture `simulated_v1` vs Nix `collectable_v1` called out |
| Review path links INDEX | PASS |

## Summary

Root README now mirrors Harmony's hero GIF layout, loop narrative, and review
spine while preserving NLFR's evidence-first proof commands and truth-label
boundaries. Media index documents hero GIFs and `docs/images/` still frames.
