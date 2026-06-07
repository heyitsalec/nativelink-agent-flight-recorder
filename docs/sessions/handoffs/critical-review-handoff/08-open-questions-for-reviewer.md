# Open questions for critical reviewer

**Audience:** Fresh Claude session on adversarial review  
**Instruction:** Answer each question with **evidence** (file path, command output, or test name). Mark **UNANSWERED** if you cannot verify in-repo. Do not speculate beyond artifacts.

Cross-reference: [`05-review-rubric.md`](05-review-rubric.md) · [`06-demo-rehearsal-script.md`](06-demo-rehearsal-script.md)

---

## Architecture & truth labels

1. Does every exported projection node, edge, metric, and proof claim include all four truth fields (`source_kind`, `confidence`, `evidence_refs`, `redaction_state`)? Which test or schema enforces this?

2. Where does the codebase **reject** or downgrade a claim when direct evidence is missing (e.g. worker identity without M7 stdout)? Is that behavior covered by tests?

3. Is there any code path where the canvas fetches live NativeLink or Bazel state at render time? If yes, is it gated and documented?

4. Does `nlfr proof export` always include an `unsupported_claims` (or equivalent) section? What claims are listed today?

5. How does ingest distinguish `collectable_v1` from `simulated_v1` at write time — CLI flag only, or automatic detection? Can a fixture path accidentally land as `collectable_v1`?

---

## Claim honesty & documentation

6. List every place README or ONE_PAGER says "proven" or "collectable_v1". Does each map to a script under `scripts/` and an artifact under `data/` or `docs/proof-samples/`?

7. Is the two-worker proof described consistently everywhere as **endpoint readiness** (not work distribution)? Find any doc that overstates it.

8. Does `agent-loop-summary.json` documentation clearly state the agent/change leg is `simulated_v1` while validation is `collectable_v1`? Could a Tier 2 presenter confuse it with Tier1 live Bazel samples?

9. Are GHA-offline instructions consistent across CONTRIBUTING, CI_RECIPE, proof-samples README, and gap-honesty packet? Any doc still implying CI green is required?

10. Do historical banners on legacy docs (`IMPLEMENTATION_DAG`, `EXTENSION_DAG`, `ONE_PAGER`, `demo/nativelink/README.md`) match wave-1 integration brief status? What's still missing?

---

## Evidence spine & parsers

11. Is ingest idempotent under repeated runs with the same artifact hashes? Which pytest module proves it?

12. Do Bazel parsers (`bep`, execution log, profile) ever infer worker placement, queue time, or scheduler assignment? Trace the code.

13. What happens when `nlfr doctor` runs outside `nix develop`? Is the blocker JSON shape stable and tested?

14. Does `nlfr compare export` produce only `derived_v1` labels? Can compare output reference evidence from both run groups with valid `evidence_refs`?

---

## M7 · M8 · M9 milestones

15. Under what exact conditions does `worker_admin_stdout` promote `worker_identity` to `collectable_v1` / `high`? Quote the regex or parser rules and matching test fixtures.

16. What is stored by `record-agent-change.sh` and the `cursor_adapter_v1` sidecar? Confirm no raw prompt text can enter SQLite or exported JSON.

17. What is the difference between M8 `agent-live-proof.sh` (live Cursor) and `agent-loop-proof.sh` (bounded simulated agent)? Are both honestly labeled in proof-samples?

18. Does M9 compare (`compare-proof.sh`, `nlfr compare export`) ever introduce new collectable fleet claims, or strictly diffs existing projections?

19. Is `docs/proof-samples/compare-projection-sample.json` consistent with `tests/test_compare_proof_sample.py` and the wiki contract page?

---

## Tier 1 live Bazel

20. What is the exact difference between `tier1-live-bazel-proof.sh`, `tier1-agent-demo.sh`, and `tier1-bazel-ci-proof.sh`? Which is appropriate for external demo?

21. Can `NLFR_SKIP_BAZEL=1` or pytest-only paths produce summaries that look like live Bazel proof? Are those paths labeled in output JSON?

22. Do `agent-bugfix-summary.json` and `agent-feature-summary.json` match the schema emitted by a real `tier1-live-bazel-proof.sh` run? Any field drift?

23. Does Act 3 (`compare-agent-runs.sh` + `promote-tier1-compare.sh`) write projections that the `tier1-demo` view actually loads?

24. Is `apps/canvas/public/views/tier1-demo.json` aligned with `view-spec.v1.schema.json` and the view composer protocol doc?

---

## Canvas & UI

25. What projection files does the default dev server load vs `?view=tier1-demo`? Is canvas-dev dogfood clearly `collectable_v1` in the committed JSON?

26. Do `npm --prefix apps/canvas run test:truth` tests fail if someone removes the truth legend or mislabels a node in fixtures?

27. Does the view composer (`composer` command) export specs that could accidentally embed backend URLs or invented worker IDs?

28. Are hero GIFs (`docs/media/*.gif`) generated only from committed projections with visible truth labels per MEDIA_CAPTURE.md?

---

## Proof scripts & samples

29. For each script in `docs/wiki/reference/proof-scripts-matrix.md`, does a matching pytest or `bash -n` gate exist? Any script listed but untested?

30. Does `verify-demo.sh` overwrite `apps/canvas/public/projections/`? If not, is that documented accurately everywhere verify-demo is mentioned?

31. Are all files in `docs/proof-samples/` indexed in proof-samples README with claim boundaries? Any orphan JSON?

32. Does `fleet-claims-audit.sh` output align with `future-fleet-claims.md` and `fleet-claims-matrix-sample.json`?

33. Which proof samples are **local-only** vs CI-promotable per `CI_PROMOTION_MATRIX.md`? Any sample marketed as CI-proven without a green job?

---

## LRE · fleet · environment gaps

34. What does `lre-proof.sh` actually prove on darwin vs x86_64-linux? Are blocker samples honest on unsupported hosts?

35. Is fleet parser work still correctly marked `future` / blocked in ARCHITECTURE_TRACK and gap-honesty packet? Any code that prematurely parses scheduler logs?

36. Does `agent-live-blocker-sample.json` represent a valid `collectable_v1` negative outcome? Would a skeptic accept it as evidence of honesty?

---

## Security & privacy

37. Search committed JSON and docs for patterns that look like API keys, tokens, absolute home paths, or raw prompts. What redaction rules apply?

38. Does the repo export environment variables or full stdout anywhere in proof samples? Is `redaction_state` set appropriately?

---

## Documentation quality (wiki wave 2)

39. Do `docs/wiki/reference/contracts/**` pages match actual export JSON from `graph export`, `proof export`, and `compare export`? Pick one contract and diff against a fixture.

40. Does ADR `001-evidence-first-recorder.md` match current implementation, or has the canvas/view composer outpaced the ADR?

41. Is `docs/diagrams/broker-orchestration.md` captioned as maintainer-only / `derived_v1` with no fleet claims?

42. Are command blocks identical (or intentionally different with explanation) across README Path A/B, ADOPTION_GUIDE, and DEMO_SCRIPT?

---

## Test suite & CI posture

43. What is the current pytest count and skip reasons? Do any legacy docs cite stale counts (e.g. "103 passed")?

44. Which tests require Nix or live Bazel and which are fixture-only? Is the split obvious to a new contributor?

45. What would break first if GitHub Actions restored green — any known drift between local gates and `.github/workflows/nlfr-proof.yml`?

---

## Meta — review process

46. After answering the above, what are the top three **P0/P1** risks for an external NativeLink evaluator running Tier 2 demo?

47. What is the single most credible "honesty win" in this repo that competitors typically fake?

48. What one claim should the author **stop making** in interviews based on your evidence audit?

---

## Answer format

For each question:

```markdown
### Q{n}. <short title>
**Verdict:** CONFIRMED | REFUTED | PARTIAL | UNANSWERED  
**Evidence:** `path/to/file` or command output excerpt  
**Notes:** (1–3 sentences)
```

Deliver answers in the review output template from `05-review-rubric.md`.
