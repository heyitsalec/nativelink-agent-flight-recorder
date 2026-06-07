# NLFR-DOC — Documentation and hero media capture

Linear: [PER-1071](https://linear.app/gradschool/issue/PER-1071/nlfr-doc-documentation-and-hero-media-capture-pass)

## Objective

Harmony-quality README and docs wiki with two 8-second hero GIFs demonstrating
the ideal NLFR workflow (canvas operator tour + evidence recorder under the hood).

## Child DAG

| ID | Workstream | Deliverable |
|----|------------|-------------|
| PER-1072 | DOC-A | Capture scripts + `docs/media/*.gif` + `MEDIA_CAPTURE.md` |
| PER-1073 | DOC-B | `docs/INDEX.md` wiki hub + cross-links |
| PER-1074 | DOC-C | Harmony-style `README.md` with embedded heroes |

## Reference standards

- Harmony root README: `/Users/alecbot/Documents/harmony/README.md`
- GIF tour script: `harmony/cockpit/scripts/capture-demo-tour.mjs`
- Docs index: `harmony/docs/INDEX.md`

## Ideal scenes (8s each)

**GIF 1 — Canvas operator tour:** Action Graph → Proof Packet → Compare lens →
agent-loop operator command. Truth labels visible.

**GIF 2 — Evidence loop:** Terminal/scripted flow: `record-proof` → SQLite →
`graph export` → `collectable_v1` summary. No secrets; redacted paths.

## Proof commands

```bash
npm --prefix apps/canvas run capture:tour
npm --prefix apps/canvas run capture:evidence
npm --prefix apps/canvas run test:truth
```

## Handoff dir

`docs/sessions/handoffs/nlfr-doc-capture/wave-1/`
