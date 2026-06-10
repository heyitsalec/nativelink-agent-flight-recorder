# NLFR Public Media

Public-safe hero GIFs and related still frames for README, walkthrough, and
release review. All artifacts are generated from committed projection JSON or
curated, redacted terminal replay — never from live secrets or private logs.

← [Docs index](../INDEX.md) · Regeneration: [MEDIA_CAPTURE.md](../MEDIA_CAPTURE.md)

## Hero GIFs

| File | Purpose | Source | Truth label |
| --- | --- | --- | --- |
| [nlfr-canvas-tour.gif](nlfr-canvas-tour.gif) | Action Graph → Proof Packet → Compare Runs → operator command | `npm run capture:tour` over canvas preview | Projection-driven; dogfood `collectable_v1` or fixture `simulated_v1` depending on published projections |
| [nlfr-evidence-loop.gif](nlfr-evidence-loop.gif) | Record → ingest → export → project terminal replay | `npm run capture:evidence` (curated HTML terminal) | Public-safe redacted paths; illustrates `collectable_v1` spine |

Regenerate both:

```bash
npm --prefix apps/canvas run capture:heroes
```

## Still frames

Still PNGs and WebM live under [`docs/images/`](../images/) (not in this
directory). They are copied from Playwright capture output for walkthrough and
README reference frames.

| File | Lens |
| --- | --- |
| [canvas-desktop.png](../images/canvas-desktop.png) | Desktop Action Graph |
| [canvas-agent-loop.png](../images/canvas-agent-loop.png) | Agent-loop focus |
| [canvas-proof.png](../images/canvas-proof.png) | Proof Packet drawer |
| [canvas-failure-focus.png](../images/canvas-failure-focus.png) | Failure focus |
| [canvas-remote-boundary.png](../images/canvas-remote-boundary.png) | Remote boundary |
| [canvas-mobile.png](../images/canvas-mobile.png) | Mobile layout |
| [canvas-operator-flow.webm](../images/canvas-operator-flow.webm) | Operator flow (WebM) |

Two-act spark stills (receipt badges, receipt pane, compare provenance card)
are Playwright baselines committed under
[`apps/canvas/baselines/screenshots/`](../../apps/canvas/baselines/screenshots/)
— rendered from committed projection JSON; agent legs in those frames are
stub-labeled (`stub_receipt_v1`), not live receipts.

Fresh capture (canvas server required):

```bash
CANVAS_URL=http://127.0.0.1:5174/ npm --prefix apps/canvas run capture
cp output/playwright/canvas-*.png docs/images/
cp output/playwright/canvas-operator-flow.webm docs/images/
```

## Truth-label visibility

Hero media must show or imply truth labels where the canvas exposes them.
Tour captions describe recorded projection state, not aspirational backend
behavior. See [MEDIA_CAPTURE.md](../MEDIA_CAPTURE.md) for scene design rules.
