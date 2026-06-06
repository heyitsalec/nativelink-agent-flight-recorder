# NativeLink Agent Flight Recorder Product Framing

## Core Thesis

AI will make code generation abundant. The scarce thing becomes trustworthy
validation: can this patch build, test, cache, reproduce, explain itself, and
prove what happened without a human spelunking CI logs?

NativeLink fits there because it is not betting on one app category. It is
infrastructure for the validation loop itself.

## What We Are Building

NativeLink Agent Flight Recorder is an evidence layer for AI-generated code
validation, with NativeLink as the acceleration and reproducibility substrate
underneath it.

Conceptually, it is a local-first proof recorder for agentic engineering loops.

A coding agent changes a repo. The system runs build/test through Bazel with
NativeLink-backed cache or execution. NLFR records the artifacts, normalizes
them, and gives the operator a visual, evidence-backed story:

- which agent or scenario produced the change;
- what files changed;
- what build and test actions ran;
- what hit or missed cache;
- what failed or flaked;
- what evidence backs each claim;
- what the system explicitly cannot claim yet.

This is not a dashboard in the usual metrics-everywhere sense. It is closer to a
black box recorder for AI engineering runs.

## How It Uses NativeLink

NativeLink is the thing that makes the validation loop fast and scalable.

Today, NLFR mostly uses the remote cache path:

1. Run a Bazel workload.
2. Point Bazel at NativeLink as the cache backend.
3. Capture Bazel BEP/profile/execution-log artifacts.
4. Compare cold and warm runs.
5. Show cache evidence and time/cost implications.
6. Preserve all of that as proof JSON and SQLite evidence.

Future expansion is remote execution:

1. Agents generate many code changes.
2. Build/test jobs fan out across NativeLink workers.
3. NLFR records which validations happened, what reused prior work, what failed,
   and what remains unproven.
4. Operators get an action graph instead of CI soup.

NativeLink is not just a faster CI component in this framing. It becomes the
validation fabric for AI-native engineering orgs.

## What It Showcases

The showcase is not simply, "look, we made a pretty UI for NativeLink."

The showcase is:

> In an AI-heavy engineering world, NativeLink makes repeated code validation
> cheap, fast, reproducible, and inspectable.

That is the strategic point.

The demo should make a NativeLink buyer or investor feel:

- agentic coding will multiply build/test volume;
- cache/reuse/execution infrastructure becomes more valuable, not less;
- NativeLink can sit under all of those agents;
- this proof layer makes the value legible to platform teams, executives, and
  skeptical engineers;
- this is a category NativeLink can own before generic CI vendors catch up.

The strongest visual is the Action Graph: agents, patches, build actions, cache
hits/misses, failures, and proof artifacts connected as one evidence canvas.

The second strongest visual is the Proof Drawer: every claim has source kind,
confidence, evidence refs, and explicit unsupported claims. That discipline
matters because AI tooling gets hand-wavy quickly. NativeLink can look more
serious by being the opposite.

## End Goal

The immediate end goal is a tryout-grade reference kit:

> Here is how an AI-native engineering org should validate agent-written code
> with NativeLink.

It should be runnable, explainable, and useful in fundraising, sales, DevRel,
and product conversations.

Longer term, there are three possible product shapes:

1. Reference Architecture

   A polished demo repo and guide showing how to pair NativeLink with Claude
   Code, Cursor, Devin-style agents, CI, Bazel, and monorepos.

2. Operator Console

   A visual canvas for platform teams watching many agents generate code and
   consume validation compute.

3. Proof and Provenance Layer

   A deeper product that records agent-to-build provenance, reproducibility
   metadata, cache economics, and validation history across an org.

The end-state sentence:

> NativeLink Agent Flight Recorder helps AI-heavy engineering teams turn code
> generation chaos into cheap, reproducible, inspectable validation loops.

Sharper:

> When AI writes the code, NativeLink makes validating it fast, and NLFR makes
> validating it trustworthy.

That is the wedge. Not another CI dashboard. Not generic agent management
software. It is the proof layer for accelerated agentic engineering.

## Next Deep-Dive: Remote Execution Expansion

Future expansion is remote execution:

1. Agents generate many code changes.
2. Build/test jobs fan out across NativeLink workers.
3. NLFR records which validations happened, what reused prior work, what failed,
   and what remains unproven.
4. Operators get an action graph instead of CI soup.

The planning question is how to build, test, and utilize this without
overclaiming. The likely path is:

- start with cache-only proof as the stable baseline;
- add Local Remote Execution or a small worker fleet once the host environment is
  reproducible;
- record execution artifacts as evidence first, product claims second;
- model agents, changes, actions, workers, cache hits, failures, and proof blocks
  as one action graph;
- use the demo to show why NativeLink becomes more valuable as agent-generated
  validation volume grows.

See `docs/REMOTE_EXECUTION_PLAN.md` for the current local-execution worker path.
