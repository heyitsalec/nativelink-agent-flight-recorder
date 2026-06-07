# Spawn ledger — nlfr-doc-capture wave-2 (tier1 refresh)

| id | type | scope | status |
|----|------|-------|--------|
| parent-broker | parent | tier1-aligned media | DONE |
| doc-a-tier1-capture | verify | Re-run capture with view-spec + compare lens | pending host |

Wave 1 landed heroes (`docs/media/*.gif`). Wave 2: re-capture after tier1 canvas (`?view=tier1-demo`, Compare lens populated).

```bash
npm --prefix apps/canvas run capture:tour
npm --prefix apps/canvas run capture:evidence
```

Commit GIFs only when pixel diff acceptable per `docs/MEDIA_CAPTURE.md`.
