# Compare runs (M9)

**Quadrant:** How-to · **Audience:** operators comparing validation run groups

This page is a stable entry point from the root README. Full recipe:

→ [Export and compare run groups](how-to/export-and-compare-run-groups.md)

Compare (like every read command) opens its `--db` / `--left-db` / `--right-db`
read-only against a database that must already exist — `nlfr record` writes one at
`data/nlfr-record/<run-group>/nlfr.sqlite`. A missing/empty path, or a run group
with no runs, is a hard error (exit 2) naming the side, never a silent zero-value
compare.

← [Wiki hub](README.md) · [Docs index](../INDEX.md)
