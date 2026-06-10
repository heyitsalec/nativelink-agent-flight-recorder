import { withBase } from "../lib/basePath";
import { sampleProofPacket, sampleProjection } from "../sampleProjection";
import type { ActionGraphProjection, CompareProjection, ProofPacket } from "../types";
import type {
  BindingKey,
  BindingResolveStatus,
  ProjectionBindingDirect,
  ResolvedBindingEntry,
  ViewSpec,
} from "../view/types";

export type ResolvedBindings = {
  actionGraph: ActionGraphProjection;
  proofPacket: ProofPacket;
  compareProjection: CompareProjection | null;
  usingFixtureFallback: boolean;
  entries: ResolvedBindingEntry[];
  values: Record<BindingKey, unknown>;
  status: Record<BindingKey, BindingResolveStatus>;
};

const FIXTURES: Record<string, unknown> = {
  sampleProjection,
  sampleProofPacket,
};

function loadFixture(name: string): unknown {
  const fixture = FIXTURES[name];
  if (!fixture) {
    throw new Error(`Unknown fixture: ${name}`);
  }
  return fixture;
}

async function fetchBinding(binding: ProjectionBindingDirect): Promise<{
  value: unknown;
  status: BindingResolveStatus;
}> {
  try {
    const response = await fetch(withBase(binding.path));
    if (!response.ok) throw new Error(`fetch failed: ${binding.path}`);
    const value = await response.json();
    return { value, status: "ok" };
  } catch {
    if (binding.fallback?.startsWith("fixture:")) {
      const fixtureName = binding.fallback.slice("fixture:".length);
      return { value: loadFixture(fixtureName), status: "fixture" };
    }
    if (binding.required === false) {
      return { value: null, status: "missing" };
    }
    if (binding.fallback === "none") {
      return { value: null, status: "missing" };
    }
    return { value: null, status: "missing" };
  }
}

export async function resolveBindings(spec: ViewSpec): Promise<ResolvedBindings> {
  const entries: ResolvedBindingEntry[] = [];
  const values: Record<string, unknown> = {};
  const status: Record<string, BindingResolveStatus> = {};
  let usingFixtureFallback = false;

  const pairs = await Promise.all(
    Object.entries(spec.bindings).map(async ([key, binding]) => {
      const result = await fetchBinding(binding);
      return { key: key as BindingKey, binding, ...result };
    }),
  );

  for (const pair of pairs) {
    entries.push({
      key: pair.key,
      status: pair.status,
      value: pair.value,
      required: pair.binding.required !== false,
    });
    values[pair.key] = pair.value;
    status[pair.key] = pair.status;
    if (pair.status === "fixture") usingFixtureFallback = true;
  }

  const actionGraph =
    (values["binding.action_graph"] as ActionGraphProjection | undefined) ?? sampleProjection;
  const proofPacket =
    (values["binding.proof_packet"] as ProofPacket | undefined) ?? sampleProofPacket;
  const compareProjection = (values["binding.compare"] as CompareProjection | null) ?? null;

  if (!values["binding.action_graph"]) usingFixtureFallback = true;
  if (!values["binding.proof_packet"] && status["binding.proof_packet"] === "fixture") {
    usingFixtureFallback = true;
  }

  return {
    actionGraph,
    proofPacket,
    compareProjection,
    usingFixtureFallback,
    entries,
    values,
    status,
  };
}

export function bindingSources(values: Record<BindingKey, unknown>): Record<string, unknown> {
  return { ...values };
}
