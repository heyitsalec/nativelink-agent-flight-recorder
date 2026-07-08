import { payloadRecord, stringValue } from "./pageModel";
import { PROVENANCE_META } from "./panels/shared/truth/copy";

/**
 * Verifiable agent receipt rendering model.
 *
 * Everything here is derived 1:1 from recorded projection payload fields
 * emitted by src/nlfr/projectors/graph.py (_project_agents) and
 * compare.py (_agent_provenance_summary). Nothing is invented: a field that
 * is absent in the payload renders as absent, and only `receipt_verified_v1`
 * with `receipt_verified: true` earns the live affordance.
 */

export type ProvenanceClass =
  | "receipt_verified_v1"
  | "stub_receipt_v1"
  | "operator_asserted_v1";

export const PROVENANCE_CLASSES: ProvenanceClass[] = [
  "receipt_verified_v1",
  "stub_receipt_v1",
  "operator_asserted_v1",
];

export type ProvenanceBadge = {
  provenanceClass: ProvenanceClass;
  /** Short label rendered on the badge. */
  label: string;
  /** CSS modifier: provenance--verified | provenance--stub | provenance--asserted. */
  tone: "verified" | "stub" | "asserted";
  /** True only for receipt_verified_v1 with receipt_verified === true. */
  live: boolean;
  /** Honest one-line description of what the class means. */
  hint: string;
};

export type ReceiptHash = {
  label: string;
  value: string;
};

export type AgentReceiptModel = {
  badge: ProvenanceBadge;
  model: string | null;
  sessionId: string | null;
  cliVersion: string | null;
  capturedAt: string | null;
  usage: { label: string; value: number }[];
  hashes: ReceiptHash[];
};

function isProvenanceClass(value: unknown): value is ProvenanceClass {
  return (
    typeof value === "string" && (PROVENANCE_CLASSES as string[]).includes(value)
  );
}

export function provenanceBadge(
  payload: Record<string, unknown> | null | undefined,
): ProvenanceBadge | null {
  const record = payloadRecord(payload);
  if (!record) return null;
  const provenanceClass = record.provenance_class;
  if (!isProvenanceClass(provenanceClass)) return null;
  const receiptVerified = record.receipt_verified === true;

  // Badge label is the P2 ProvenanceBadge copy (PROVENANCE_META) — ONE source
  // for "verified"/"stub"/"asserted" across the graph-node badge, compare cards
  // and this receipt pane; the receipt pane read a divergent "verified receipt"
  // constant vs board 1g's P2 copy before (redesign P6 fix M4-residual).
  if (provenanceClass === "receipt_verified_v1") {
    return {
      provenanceClass,
      label: PROVENANCE_META[provenanceClass].label,
      tone: "verified",
      live: receiptVerified,
      hint: "live CLI receipt — hashes recomputable from recorded evidence",
    };
  }
  if (provenanceClass === "stub_receipt_v1") {
    return {
      provenanceClass,
      label: PROVENANCE_META[provenanceClass].label,
      tone: "stub",
      live: false,
      hint: "deterministic stub CLI — mechanics proof, not a live model",
    };
  }
  return {
    provenanceClass,
    label: PROVENANCE_META[provenanceClass].label,
    tone: "asserted",
    live: false,
    hint: "no CLI receipt recorded — provenance asserted by the operator",
  };
}

function numberValue(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function agentReceiptModel(
  payload: Record<string, unknown> | null | undefined,
): AgentReceiptModel | null {
  const record = payloadRecord(payload);
  if (!record) return null;
  const badge = provenanceBadge(record);
  if (!badge) return null;

  const usageRecord = payloadRecord(record.receipt_usage);
  const usage: { label: string; value: number }[] = [];
  if (usageRecord) {
    for (const [key, raw] of Object.entries(usageRecord)) {
      const value = numberValue(raw);
      if (value !== null) {
        usage.push({ label: key.replace(/_/g, " "), value });
      }
    }
  }

  const hashes: ReceiptHash[] = [];
  const hashFields: [string, string][] = [
    ["receipt sha256", "receipt_sha256"],
    ["response sha256", "receipt_response_sha256"],
    ["prompt sha256", "prompt_sha256"],
  ];
  for (const [label, key] of hashFields) {
    const value = stringValue(record[key]);
    if (value) hashes.push({ label, value });
  }

  return {
    badge,
    model:
      stringValue(record.receipt_model_resolved) ?? stringValue(record.model),
    sessionId: stringValue(record.receipt_session_id),
    cliVersion: stringValue(record.receipt_cli_version),
    capturedAt: stringValue(record.receipt_captured_at),
    usage,
    hashes,
  };
}

export function truncateHash(value: string, visible = 12): string {
  if (value.length <= visible + 1) return value;
  return `${value.slice(0, visible)}…`;
}

/** Compare-lens agent_provenance dimension: one summarized receipt block. */
export type ProvenanceBlockSummary = {
  id: string;
  title: string | null;
  model: string | null;
  promptSha256Prefix: string | null;
  sessionId: string | null;
  sourceKind: string;
  badge: ProvenanceBadge | null;
};

function blockSummary(value: unknown): ProvenanceBlockSummary | null {
  const record = payloadRecord(value);
  if (!record) return null;
  const id = stringValue(record.id);
  if (!id) return null;
  return {
    id,
    title: stringValue(record.title),
    model: stringValue(record.model),
    promptSha256Prefix: stringValue(record.prompt_sha256_prefix),
    sessionId: stringValue(record.receipt_session_id),
    sourceKind: stringValue(record.source_kind) ?? "unknown",
    badge: provenanceBadge(record),
  };
}

export type ProvenanceSide = {
  present: boolean;
  blockCount: number;
  blocks: ProvenanceBlockSummary[];
};

export function provenanceSide(value: unknown): ProvenanceSide {
  const record = payloadRecord(value);
  const rawBlocks = Array.isArray(record?.blocks) ? record.blocks : [];
  const blocks = rawBlocks
    .map(blockSummary)
    .filter((block): block is ProvenanceBlockSummary => block !== null);
  return {
    present: record?.present === true,
    blockCount: numberValue(record?.block_count) ?? blocks.length,
    blocks,
  };
}
