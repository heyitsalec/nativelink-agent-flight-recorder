import type { SourceKind } from "../types";
import { DEFAULT_VIEW_SPEC } from "../view/defaultViewSpec";
import type { ViewSpec } from "../view/types";
import graphOnlyJson from "../../public/views/graph-only.json";
import proofReviewJson from "../../public/views/proof-review.json";
import tier1DemoJson from "../../public/views/tier1-demo.json";

export type TemplateRef = {
  view_id: string;
  title: string;
  description: string;
  source_kind: Extract<SourceKind, "derived_v1" | "simulated_v1">;
};

export const TEMPLATE_REFS: TemplateRef[] = [
  {
    view_id: "nlfr-default-v0",
    title: "NLFR Default Canvas",
    description: "Equivalent to current App.tsx behavior",
    source_kind: "simulated_v1",
  },
  {
    view_id: "graph-only",
    title: "Action Graph Only",
    description: "Graph + inspector; no proof/compare lenses",
    source_kind: "derived_v1",
  },
  {
    view_id: "proof-review",
    title: "Proof Review",
    description: "Proof drawer primary; graph dimmed",
    source_kind: "derived_v1",
  },
  {
    view_id: "tier1-demo",
    title: "Tier 1 Agent Vision Demo",
    description: "Compare-forward tier1 demo with canvas-dev bindings",
    source_kind: "derived_v1",
  },
];

const BUNDLED_TEMPLATES: Record<string, ViewSpec> = {
  "nlfr-default-v0": DEFAULT_VIEW_SPEC,
  "graph-only": graphOnlyJson as unknown as ViewSpec,
  "proof-review": proofReviewJson as unknown as ViewSpec,
  "tier1-demo": tier1DemoJson as unknown as ViewSpec,
};

export function getTemplateRef(viewId: string): TemplateRef | undefined {
  return TEMPLATE_REFS.find((ref) => ref.view_id === viewId);
}

export function getTemplateSpec(viewId: string): ViewSpec | null {
  const spec = BUNDLED_TEMPLATES[viewId];
  if (!spec) return null;
  return structuredClone(spec);
}

export function assertComposerSourceKind(
  sourceKind: SourceKind,
): sourceKind is Extract<SourceKind, "derived_v1" | "simulated_v1"> {
  return sourceKind === "derived_v1" || sourceKind === "simulated_v1";
}
