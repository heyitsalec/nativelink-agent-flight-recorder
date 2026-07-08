import { withBase } from "../lib/basePath";
import { classifyBindingFetch, projectionParseDetail } from "../pageModel";
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

/**
 * A bound projection that was fetched OK but is not valid JSON — the real
 * projection is CORRUPT. This is deliberately NOT swallowed into the fixture
 * fallback (which is reserved for MISSING data): it rethrows so the honest
 * projection error state fires ("… — invalid JSON. Nothing partial is
 * rendered."), carrying already-curated human copy in `.message` (redesign
 * P7 V4, board 1l).
 */
export class ProjectionParseError extends Error {
  constructor(detail: string) {
    super(detail);
    this.name = "ProjectionParseError";
  }
}

/** MISSING binding → labeled fixture fallback (honest) or a null/missing value. */
function fallbackForMissing(binding: ProjectionBindingDirect): {
  value: unknown;
  status: BindingResolveStatus;
} {
  if (binding.fallback?.startsWith("fixture:")) {
    const fixtureName = binding.fallback.slice("fixture:".length);
    return { value: loadFixture(fixtureName), status: "fixture" };
  }
  return { value: null, status: "missing" };
}

async function fetchBinding(binding: ProjectionBindingDirect): Promise<{
  value: unknown;
  status: BindingResolveStatus;
}> {
  // Stage 1 — reach the projection. A network throw or a non-2xx status means
  // the projection is MISSING/unreachable → degrade to the labeled fallback.
  let response: Response | null = null;
  let networkError = false;
  try {
    response = await fetch(withBase(binding.path));
  } catch {
    networkError = true;
  }
  if (networkError || !response || !response.ok) {
    // classifyBindingFetch: networkError | !responseOk → "missing"
    return fallbackForMissing(binding);
  }

  // Stage 2 — parse. The projection EXISTS (HTTP OK); if its body is not valid
  // JSON it is CORRUPT (classifyBindingFetch → "malformed"), which is a
  // different failure from "missing". Do NOT dress it as a fixture fallback —
  // surface the honest error state via a curated ProjectionParseError.
  try {
    const value = await response.json();
    return { value, status: "ok" };
  } catch (parseError) {
    if (
      classifyBindingFetch({ networkError: false, responseOk: true, parsedOk: false }) ===
      "malformed"
    ) {
      throw new ProjectionParseError(projectionParseDetail(binding.path, parseError));
    }
    return fallbackForMissing(binding);
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
