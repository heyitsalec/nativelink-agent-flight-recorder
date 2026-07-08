import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  ArrowLeftRight,
  Bot,
  Box,
  ChevronRight,
  Copy,
  Database,
  Download,
  FileText,
  GitCommitVertical,
  Globe,
  Lock,
  Play,
  ReceiptText,
  Server,
  Target,
  Terminal,
  TriangleAlert,
  X,
  Zap,
} from "lucide-react";
import {
  blockIndexMeta,
  blocksBelow,
  compareHeadline,
  formatMetricValue,
  isRedactedValue,
  labelKind,
  payloadRecord,
  proofRollup,
  redactedPayloadFields,
  redactedValueForBlock,
  remoteBoundaryView,
  unsupportedClaimsFromPayload,
} from "../pageModel";
import {
  agentReceiptModel,
  provenanceSide,
  type AgentReceiptModel,
  type ProvenanceBadge as ProvenanceBadgeModel,
  type ProvenanceBlockSummary,
} from "../receiptModel";
import type {
  CompareDimension,
  CompareProjection,
  Confidence,
  PositionedNode,
  ProofBlock,
  ProofMetricValue,
  ProofPacket,
  SourceKind,
} from "../types";
import type { ComponentInstance } from "../view/types";
import { useViewContext } from "../view/ViewContext";
import { stringProp } from "./shared/props";
import {
  ConfidenceMeter,
  ProvenanceBadge,
  RedactionChip,
  SourceGlyph,
  StatusGlyph,
  UnsupportedClaimChip,
} from "./shared/truth";
import { SOURCE_KIND_META } from "./shared/truth/copy";

export function EvidenceInspectorPanel(_instance: ComponentInstance) {
  const { graph, route, routeActions } = useViewContext();
  const selectedNode = graph.nodes.find((node) => node.id === route.selectedId) ?? null;
  if (!selectedNode) return null;

  return (
    <Inspector node={selectedNode} onClose={() => routeActions.setSelectedId(null)} />
  );
}

function failureMessage(node: PositionedNode): string | null {
  if (node.kind !== "failure") return null;
  const payloadMessage = node.payload?.message;
  if (typeof payloadMessage === "string" && payloadMessage.trim()) {
    return payloadMessage.trim();
  }
  if (typeof node.status === "string" && node.status.trim()) {
    return node.status.trim();
  }
  return node.label.trim() || null;
}

export function ProvenanceChip({ badge }: { badge: ProvenanceBadgeModel }) {
  // Delegates to the P2 truth primitive so provenance reuses the source-kind
  // shape families (verified→circle, asserted→diamond, stub→triangle).
  return <ProvenanceBadge badge={badge} />;
}

/** Kind → lucide icon for the inspector header plate (mirrors the graph card
 *  plate icons, DESIGN-SYSTEM.md §1). */
const INSPECTOR_KIND_ICONS: Record<
  string,
  React.ComponentType<{ size?: number | string; "aria-hidden"?: React.AriaAttributes["aria-hidden"] }>
> = {
  run: Play,
  invocation: Terminal,
  artifact: FileText,
  agent: Bot,
  change: GitCommitVertical,
  target: Target,
  action: Zap,
  cache_event: Database,
  failure: TriangleAlert,
  worker: Server,
  worker_readiness: Server,
  remote_execution_config: Server,
};

/** Middle-truncate a hash for display; full value stays copyable. */
function truncateHashMiddle(value: string, head = 10, tail = 8): string {
  if (value.length <= head + tail + 1) return value;
  return `${value.slice(0, head)}…${value.slice(-tail)}`;
}

function CopyHash({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="receipt-hash">
      <span className="receipt-hash-label">{label}</span>
      <code title={value}>{truncateHashMiddle(value)}</code>
      <button
        className="receipt-hash-copy"
        aria-label={`Copy ${label}`}
        onClick={() => {
          void navigator.clipboard?.writeText(value).then(() => {
            setCopied(true);
            window.setTimeout(() => setCopied(false), 1400);
          });
        }}
      >
        {copied ? "copied" : <Copy size={12} />}
      </button>
    </div>
  );
}

/**
 * Agent receipt pane (board 1g §3). Provenance badge + server-resolved model +
 * prompt/response sha256 (mono, middle-truncated, copyable) + the honest
 * raw-prompt lock: the prompt is NEVER exported — only its hash is retained.
 */
function ReceiptDetailPane({ receipt }: { receipt: AgentReceiptModel }) {
  return (
    <section className="receipt-pane inspector-section" aria-label="agent receipt" data-testid="receipt-detail-pane">
      <span className="inspector-overline">AGENT RECEIPT</span>
      <div className="receipt-pane-heading">
        <ReceiptText size={15} aria-hidden="true" />
        <span>Agent receipt</span>
        <ProvenanceChip badge={receipt.badge} />
      </div>
      <p className="receipt-pane-hint">{receipt.badge.hint}</p>
      {receipt.model && (
        <div className="receipt-model">
          <span className="receipt-model-value">{receipt.model}</span>
          <span className="receipt-model-note">server-resolved</span>
        </div>
      )}
      {receipt.usage.length > 0 && (
        <div className="receipt-usage" aria-label="receipt token usage">
          {receipt.usage.map((entry) => (
            <span key={entry.label}>
              <strong>{entry.value}</strong>
              {entry.label}
            </span>
          ))}
        </div>
      )}
      {receipt.hashes.length > 0 && (
        <div className="receipt-hashes" aria-label="receipt hashes">
          {receipt.hashes.map((hash) => (
            <CopyHash key={hash.label} label={hash.label} value={hash.value} />
          ))}
        </div>
      )}
      <div className="receipt-rawlock" title="The raw prompt is never written to any projection or export — only its sha256 is retained.">
        <Lock size={12} aria-hidden="true" />
        <span>raw prompt — never exported · hash only</span>
      </div>
    </section>
  );
}

/** Curated recorded-run detail fields, in board order (§5). Redacted values
 *  render as lock chips (carry-forward), never a bare "[REDACTED]". */
const RECORDED_DETAIL_KEYS: { key: string; label: string }[] = [
  { key: "run_group", label: "run group" },
  { key: "scenario", label: "scenario" },
  { key: "mode", label: "mode" },
  { key: "invocation_kind", label: "invocation" },
  { key: "exit_code", label: "exit code" },
  { key: "cwd", label: "cwd" },
  { key: "started_at", label: "started" },
  { key: "ended_at", label: "ended" },
];

function durationSeconds(start: unknown, end: unknown): string | null {
  if (typeof start !== "string" || typeof end !== "string") return null;
  const a = Date.parse(start);
  const b = Date.parse(end);
  if (!Number.isFinite(a) || !Number.isFinite(b) || b < a) return null;
  return `${((b - a) / 1000).toFixed(2)}s`;
}

/** Recorded-run details section (§5): the real payload facts, with a computed
 *  duration and redacted values kept honest as lock chips. */
function RecordedDetails({ node }: { node: PositionedNode }) {
  const record = payloadRecord(node.payload);
  if (!record) return null;
  const rows = RECORDED_DETAIL_KEYS.filter(({ key }) => {
    const value = record[key];
    return value !== undefined && value !== null && value !== "";
  }).map(({ key, label }) => ({ key, label, raw: record[key] }));
  const duration = durationSeconds(record.started_at, record.ended_at);
  if (rows.length === 0 && !duration) return null;

  return (
    <section className="inspector-section" aria-label="recorded details">
      <span className="inspector-overline">RECORDED {node.kind === "run" ? "RUN" : "EVIDENCE"}</span>
      <dl className="insp-kv">
        {rows.map((row) => (
          <div key={row.key}>
            <dt>{row.label}</dt>
            <dd>
              {typeof row.raw === "string" && isRedactedValue(row.raw) ? (
                <RedactionChip state="redacted" value={row.raw} />
              ) : (
                <span>{String(row.raw)}</span>
              )}
            </dd>
          </div>
        ))}
        {duration && (
          <div>
            <dt>duration</dt>
            <dd>
              <span className="insp-mono">{duration}</span>
            </dd>
          </div>
        )}
      </dl>
    </section>
  );
}

/** Raw payload — collapsed by default, explicitly secondary (§7). */
function RawPayload({ payload }: { payload: Record<string, unknown> }) {
  const [open, setOpen] = useState(false);
  const json = useMemo(() => JSON.stringify(payload, null, 2), [payload]);
  const [copied, setCopied] = useState(false);
  const lines = json.split("\n").length;
  return (
    <div className="insp-raw">
      <button type="button" className="insp-raw-toggle" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
        <ChevronRight size={12} className={`insp-raw-caret${open ? " open" : ""}`} aria-hidden="true" />
        <span className="insp-raw-word">raw payload</span>
        <span className="insp-raw-meta">developer · {lines} lines JSON</span>
        <button
          type="button"
          className="insp-raw-copy"
          aria-label="Copy raw payload"
          onClick={(event) => {
            event.stopPropagation();
            void navigator.clipboard?.writeText(json).then(() => {
              setCopied(true);
              window.setTimeout(() => setCopied(false), 1400);
            });
          }}
        >
          {copied ? "copied" : <Copy size={12} aria-hidden="true" />}
        </button>
      </button>
      {open && <pre className="insp-raw-pre">{json}</pre>}
    </div>
  );
}

/**
 * Evidence Inspector (redesign P6 — DESIGN-SYSTEM.md §2, board 1g). Right E3
 * drawer. Hairline-divided sections, each overlined: header, the 2×2 truth
 * grid, the agent receipt (if any), a failure callout that keeps the honest
 * "red marks the outcome, teal marks the origin" truth row, recorded-run
 * details, collapsible evidence refs, and a collapsed-by-default raw payload.
 * Redacted payload values are kept as lock chips carrying the real partial path.
 */
function Inspector({ node, onClose }: { node: PositionedNode; onClose: () => void }) {
  const message = failureMessage(node);
  const receipt = node.kind === "agent" ? agentReceiptModel(node.payload) : null;
  const Icon = INSPECTOR_KIND_ICONS[node.kind] ?? Box;
  const sourceMeta = SOURCE_KIND_META[node.source_kind] ?? SOURCE_KIND_META.unknown;
  // Carry-forward: surface a real `[REDACTED:...]` value from the payload so the
  // redaction cell shows the partial path, never a bare "[REDACTED]".
  const redactedFields = useMemo(() => redactedPayloadFields(node.payload), [node.payload]);
  const redactionValue = node.redaction_state === "redacted" ? redactedFields[0]?.value : undefined;
  const exitCode = payloadRecord(node.payload)?.exit_code;

  return (
    <aside
      className={`inspector ${node.kind === "failure" ? "inspector--failure" : ""}`}
      aria-label="selected evidence"
    >
      <section className="inspector-section inspector-head-section">
        <div className="inspector-head-row">
          <span className="inspector-overline">EVIDENCE INSPECTOR</span>
          <button className="close-button inspector-close" onClick={onClose} aria-label="Close inspector">
            <X size={16} />
          </button>
        </div>
        <div className="inspector-head">
          <span className={`inspector-plate truth--${sourceMeta.tone}`} aria-hidden="true">
            <Icon size={18} />
          </span>
          <div className="inspector-head-text">
            <h2 className="inspector-title">{node.label}</h2>
            <span className="inspector-id">{node.id}</span>
          </div>
        </div>
      </section>

      <section className="inspector-section">
        <span className="inspector-overline">TRUTH LABELS</span>
        <div className="inspector-truth-grid">
          <div className="inspector-truth-cell">
            <span className="inspector-truth-caption">source</span>
            <span className="truth-value">
              <SourceGlyph kind={node.source_kind} size={11} />
              <span>{sourceMeta.label}</span>
            </span>
          </div>
          <div className="inspector-truth-cell">
            <span className="inspector-truth-caption">confidence</span>
            <span className="truth-value">
              <ConfidenceMeter confidence={node.confidence} />
              <span>{node.confidence}</span>
            </span>
          </div>
          <div className="inspector-truth-cell">
            <span className="inspector-truth-caption">redaction</span>
            <span className="truth-value">
              <RedactionChip state={node.redaction_state} value={redactionValue} />
            </span>
          </div>
          <div className="inspector-truth-cell">
            <span className="inspector-truth-caption">status</span>
            <span className="truth-value">
              <StatusGlyph status={node.status} />
            </span>
          </div>
        </div>
      </section>

      {receipt && <ReceiptDetailPane receipt={receipt} />}

      {message && (
        <section className="inspector-section failure-callout" aria-label="failure callout">
          <div className="failure-callout-box">
            <div className="failure-callout-head">
              <TriangleAlert size={14} aria-hidden="true" />
              <strong>
                Recorded failure{typeof exitCode === "number" ? ` — exit ${exitCode}` : ""}
              </strong>
            </div>
            <p className="failure-callout-body">{message}</p>
          </div>
          <p className="failure-callout-truth">
            a failure is still high-confidence recorded evidence — red marks the outcome, teal marks the
            origin.
          </p>
        </section>
      )}

      <RecordedDetails node={node} />

      {node.evidence_refs.length > 0 && (
        <section className="inspector-section">
          <span className="inspector-overline">EVIDENCE REFS</span>
          <EvidenceRefs refs={node.evidence_refs} defaultOpen={false} />
        </section>
      )}

      {node.payload && Object.keys(node.payload).length > 0 && (
        <section className="inspector-section">
          <RawPayload payload={node.payload} />
        </section>
      )}
    </aside>
  );
}

/* ------------------------------------------------------------------------ *
 * Proof Packet drawer (redesign P5 — DESIGN-SYSTEM.md §4, boards 1e/1f/1o).
 * Three zones: A header (rollup + real summary grid), B block index (the
 * scannable TOC), C cards (asserting vs future, collapsible evidence refs).
 * Every number is a REAL packet number; future blocks are dashed and assert
 * nothing; redacted values keep their slot as a lock chip.
 * ------------------------------------------------------------------------ */

/** The 6 summary stat cells, in board order. Values are REAL packet numbers. */
const PROOF_SUMMARY_CELLS: { key: string; label: string }[] = [
  { key: "runs", label: "runs" },
  { key: "artifacts", label: "artifacts" },
  { key: "actions", label: "actions" },
  { key: "targets", label: "targets" },
  { key: "cache_events", label: "cache events" },
  { key: "failures", label: "failures" },
];

/** How many refs a card shows before the "show N more…" affordance. */
const REFS_PREVIEW_LIMIT = 6;

/** ISO ts → "YYYY-MM-DD HH:MM" (kept in UTC; the drawer appends " UTC"). */
function formatGeneratedAt(iso: string): string {
  if (typeof iso !== "string" || iso.length < 16) return iso ?? "";
  return iso.slice(0, 16).replace("T", " ");
}

/** Middle-truncate a long ref/hash for display; the full value stays copyable. */
function middleTruncate(value: string, head = 20, tail = 12): string {
  if (value.length <= head + tail + 1) return value;
  return `${value.slice(0, head)}…${value.slice(-tail)}`;
}

/** Metric key → display label. The packet uses a generic "unknown" key for an
 *  untyped count; name it honestly rather than printing "unknown 14". */
function metricLabel(key: string, blockId: string): string {
  if (key === "unknown") return blockId === "invocations" ? "commands" : "count";
  return labelKind(key);
}

/** Split a claim so a standalone "not" renders bold (negative claims). */
function claimNodes(claim: string): ReactNode[] {
  return claim
    .split(/(\bnot\b)/gi)
    .map((part, index) => (/^not$/i.test(part) ? <strong key={index}>{part}</strong> : <span key={index}>{part}</span>));
}

type CacheLeg = { runId: string; scenario: string; duration: string; hits: number; misses: number };

/** Per-leg cache economics rows from real payload legs (board 1o). */
function cacheLegs(payload: unknown): CacheLeg[] | null {
  const record = payloadRecord(payload);
  const legs = record?.legs;
  if (!Array.isArray(legs)) return null;
  return legs.map((leg) => {
    const rec = (leg && typeof leg === "object" ? leg : {}) as Record<string, unknown>;
    const seconds = typeof rec.duration_seconds === "number" ? rec.duration_seconds : null;
    return {
      runId: typeof rec.run_id === "string" ? rec.run_id : "",
      scenario: typeof rec.scenario === "string" ? rec.scenario : "leg",
      duration: seconds === null ? "n/a" : `${seconds.toFixed(2)}s`,
      hits: typeof rec.hits === "number" ? rec.hits : 0,
      misses: typeof rec.misses === "number" ? rec.misses : 0,
    };
  });
}

function exportPacketJson(packet: ProofPacket) {
  const blob = new Blob([JSON.stringify(packet, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${packet.run_group || "proof"}-proof-packet.json`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function ProofDrawerPanel(_instance: ComponentInstance) {
  const { bindings, routeActions } = useViewContext();
  const packet = bindings.proofPacket;
  const blocks = packet.blocks;
  const rollup = useMemo(() => proofRollup(blocks), [blocks]);
  const [activeId, setActiveId] = useState<string | null>(blocks[0]?.id ?? null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const cardRefs = useRef<Map<string, HTMLElement>>(new Map());
  // While a TOC click is scrolling the cards, the spy is suppressed so the
  // clicked block stays authoritative; released once scrolling goes idle.
  const jumpLockRef = useRef(false);
  const idleTimerRef = useRef<number | null>(null);

  const registerCard = (id: string) => (el: HTMLElement | null) => {
    if (el) cardRefs.current.set(id, el);
    else cardRefs.current.delete(id);
  };

  const jumpTo = (id: string) => {
    setActiveId(id);
    // Suppress the scrollspy for the duration of this programmatic scroll
    // (redesign P5 fix M2). Without the lock, the spy flips the active block to
    // whatever card is momentarily under the top line mid-animation; the newly
    // active card's evidence refs auto-expand, the layout churns, and that
    // churn stalls the smooth scroll BEFORE it reaches the target — so clicking
    // the last row left an earlier card active (and its "N more blocks" pill
    // showing) permanently. Keeping the clicked block active lets the scroll
    // land cleanly.
    jumpLockRef.current = true;
    cardRefs.current.get(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  // Block-index scrollspy driven by scroll POSITION rather than an
  // IntersectionObserver (redesign P5 fix M2): the last card can never reach
  // the top of a scroll container that runs out of content beneath it, so an
  // "is it near the top?" observer would leave an earlier row wrongly pinned
  // and the footer pill claiming "1 more block" while you are already on the
  // last one. Instead we resolve the active block from where the container is
  // actually scrolled — and, crucially, snap to the LAST block whenever the
  // container is scrolled to its bottom.
  useEffect(() => {
    const root = scrollRef.current;
    if (!root) return;
    const resolveActive = () => {
      const cards = blocks
        .map((block) => ({ id: block.id, el: cardRefs.current.get(block.id) }))
        .filter((entry): entry is { id: string; el: HTMLElement } => Boolean(entry.el));
      if (cards.length === 0) return;
      // Non-overflowing container: everything is visible at once, so there is
      // nothing to spy — leave whatever a click set as active.
      const overflowing = root.scrollHeight > root.clientHeight + 4;
      if (!overflowing) return;
      // Scrolled to the bottom → the last card is the one being read, even
      // though it may sit below the top line.
      if (root.scrollTop + root.clientHeight >= root.scrollHeight - 4) {
        setActiveId(cards[cards.length - 1].id);
        return;
      }
      // Otherwise: the last card whose top has crossed a line a little below
      // the container top (matching scrollIntoView block:"start" landings).
      const line = root.getBoundingClientRect().top + root.clientHeight * 0.28;
      let current = cards[0].id;
      for (const card of cards) {
        if (card.el.getBoundingClientRect().top <= line) current = card.id;
        else break;
      }
      setActiveId(current);
    };
    const onScroll = () => {
      // Any scroll (programmatic or user) that then goes quiet for 150ms is
      // "settled" — release the jump lock so genuine user scrolling drives the
      // spy again.
      if (idleTimerRef.current !== null) window.clearTimeout(idleTimerRef.current);
      idleTimerRef.current = window.setTimeout(() => {
        jumpLockRef.current = false;
        idleTimerRef.current = null;
      }, 150);
      if (jumpLockRef.current) return;
      resolveActive();
    };
    root.addEventListener("scroll", onScroll, { passive: true });
    resolveActive();
    return () => {
      root.removeEventListener("scroll", onScroll);
      if (idleTimerRef.current !== null) window.clearTimeout(idleTimerRef.current);
    };
  }, [blocks]);

  const summaryValue = (key: string): string => {
    const value = packet.summary[key];
    return typeof value === "number" || typeof value === "string"
      ? formatMetricValue(value as ProofMetricValue)
      : "0";
  };

  // Real recorded run count from the packet summary — surfaced as the second
  // stat cell on the Invocation Results card (redesign P5 fix M4).
  const runsCount = typeof packet.summary.runs === "number" ? packet.summary.runs : undefined;

  const remaining = blocksBelow(blocks, activeId);

  return (
    <aside className="proof-drawer proof-drawer--flagship" aria-label="proof packet">
      {/* Zone A — header */}
      <header className="proof-head">
        <div className="proof-head-row">
          <span className="proof-overline">PROOF PACKET</span>
          <div className="proof-head-actions">
            <button type="button" className="proof-export" onClick={() => exportPacketJson(packet)}>
              <Download size={13} aria-hidden="true" />
              Export JSON
            </button>
            <button
              className="close-button proof-close"
              onClick={() => routeActions.setMode("graph")}
              aria-label="Close proof drawer"
            >
              <X size={16} />
            </button>
          </div>
        </div>
        <h2 className="proof-name">{packet.run_group}</h2>
        <span className="proof-generated">
          {blocks.length} block{blocks.length === 1 ? "" : "s"} · generated {formatGeneratedAt(packet.generated_at)} UTC
        </span>
        <div className="proof-rollup" aria-label="evidence rollup">
          <span className="proof-rollup-pill proof-rollup-pill--recorded">
            <SourceGlyph kind="collectable_v1" size={9} title={null} />
            {rollup.recorded} recorded
          </span>
          <span className="proof-rollup-pill proof-rollup-pill--future">
            <SourceGlyph kind="future" size={9} title={null} />
            {rollup.notCollected} not yet collected
          </span>
          {rollup.unknown > 0 && (
            <span className="proof-rollup-pill proof-rollup-pill--unknown">
              <SourceGlyph kind="unknown" size={9} title={null} />
              {rollup.unknown} unknown
            </span>
          )}
          <span className="proof-rollup-plain">
            {rollup.computed} computed · {rollup.simulated} simulated
          </span>
        </div>
        <div className="proof-summary-grid" aria-label="proof summary">
          {PROOF_SUMMARY_CELLS.map((cell) => (
            <div key={cell.key} className="proof-stat">
              <strong>{summaryValue(cell.key)}</strong>
              <span>{cell.label}</span>
            </div>
          ))}
        </div>
      </header>

      {/* Zone B — block index (scannable TOC) */}
      <nav className="proof-index" aria-label="proof blocks">
        <span className="proof-overline proof-index-overline">BLOCKS</span>
        {blocks.map((block) => {
          const meta = blockIndexMeta(block);
          const future = block.source_kind === "future";
          return (
            <button
              key={block.id}
              type="button"
              className={`proof-index-row${block.id === activeId ? " active" : ""}${future ? " future" : ""}`}
              onClick={() => jumpTo(block.id)}
              aria-current={block.id === activeId}
            >
              <SourceGlyph kind={block.source_kind} size={16} />
              <span className="proof-index-title">{block.title}</span>
              <span className={`proof-index-meta proof-index-meta--${meta.tone}`}>{meta.text}</span>
              {future ? (
                <span className="proof-index-q" aria-hidden="true">?</span>
              ) : (
                <ConfidenceMeter confidence={block.confidence} size="sm" />
              )}
              <ChevronRight size={12} className="proof-index-chevron" aria-hidden="true" />
            </button>
          );
        })}
      </nav>

      {/* Zone C — cards */}
      <div className="proof-cards" ref={scrollRef}>
        {blocks.map((block) => (
          <ProofBlockCard
            key={block.id}
            block={block}
            active={block.id === activeId}
            registerRef={registerCard(block.id)}
            runs={runsCount}
          />
        ))}
        {remaining.length > 0 && (
          <div className="proof-cards-footer" aria-hidden="true">
            <span className="proof-more-pill">
              ▾ {remaining.length} more block{remaining.length === 1 ? "" : "s"} —{" "}
              {remaining.slice(0, 3).map((block) => block.title).join(" · ")}
            </span>
          </div>
        )}
      </div>
    </aside>
  );
}

export function ProofBlockCardPanel(instance: ComponentInstance) {
  const { bindings } = useViewContext();
  const blockId = stringProp(instance.props, "block_id");
  const packet = bindings.proofPacket;
  const block = packet.blocks.find((entry) => entry.id === blockId);
  if (!block) return null;
  const runs = typeof packet.summary.runs === "number" ? packet.summary.runs : undefined;
  return <ProofBlockCard block={block} active registerRef={() => {}} runs={runs} />;
}

/** Board order for the Validation Surface stat cells (redesign P5 fix m9). */
const VALIDATION_CELL_ORDER = ["targets", "actions", "failures"];

function validationRank(key: string): number {
  const index = VALIDATION_CELL_ORDER.indexOf(key);
  return index === -1 ? VALIDATION_CELL_ORDER.length : index;
}

/**
 * Board-accurate stat cells for a proof block (redesign P5 fixes M4/m6/m7/m9).
 * Drops the redundant generic legs count the per-leg list already renders (m6)
 * and the generic "unknown"→count cell that only makes sense for invocations
 * (m7); orders the validation surface targets/actions/failures (m9); and
 * appends the REAL recorded `runs` count to the invocation card (M4).
 */
function proofMetricCells(block: ProofBlock, runs?: number): [string, ProofMetricValue][] {
  let cells = Object.entries(block.metrics ?? {}).filter(([key]) => {
    if (block.id === "cache_economics" && key === "legs") return false; // m6
    if (key === "unknown" && block.id !== "invocations") return false; // m7
    return true;
  });
  if (block.id === "validation") {
    cells = [...cells].sort(([a], [b]) => validationRank(a) - validationRank(b)); // m9
  }
  if (block.id === "invocations" && typeof runs === "number") {
    cells = [...cells, ["runs", runs]]; // M4
  }
  return cells;
}

function ProofBlockCard({
  block,
  active,
  registerRef,
  runs,
}: {
  block: ProofBlock;
  active: boolean;
  registerRef: (el: HTMLElement | null) => void;
  runs?: number;
}) {
  const future = block.source_kind === "future";
  const metricCells = proofMetricCells(block, runs);
  const unsupported = unsupportedClaimsFromPayload(block.payload);
  const legs = block.id === "cache_economics" ? cacheLegs(block.payload) : null;
  const claims = block.claims ?? [];
  const redactedValue = block.redaction_state === "redacted" ? redactedValueForBlock(block) : undefined;

  // Dedupe the source-kind class against the asserting/future class — for a
  // future block both resolve to "proof-card--future" (redesign P5 fix m11).
  const kindClass = `proof-card--${block.source_kind}`;
  const assertClass = future ? "proof-card--future" : "proof-card--asserting";
  const cardClass = [
    "proof-card",
    assertClass,
    ...(kindClass === assertClass ? [] : [kindClass]),
    ...(active ? ["active"] : []),
  ].join(" ");

  return (
    <section
      ref={registerRef}
      className={cardClass}
      data-block-id={block.id}
      data-testid={`proof-card-${block.id}`}
    >
      <header className="proof-card-head">
        <SourceGlyph kind={block.source_kind} size={16} />
        <h3 className="proof-card-title">{block.title}</h3>
        <span className="proof-card-truth">
          <ConfidenceMeter confidence={block.confidence} size="sm" />
          <RedactionChip state={block.redaction_state} value={redactedValue} />
        </span>
      </header>
      <p className={`proof-card-summary${block.id === "remote_execution" ? " proof-card-summary--strong" : ""}`}>
        {block.summary}
      </p>
      {future && claims.length === 0 && <span className="proof-noclaim">no claim recorded</span>}
      {metricCells.length > 0 && (
        <div className="proof-metrics" aria-label={`${block.title} metrics`}>
          {metricCells.map(([key, value]) => (
            <div key={key} className="proof-metric-cell">
              <strong>{formatMetricValue(value)}</strong>
              <span>{metricLabel(key, block.id)}</span>
            </div>
          ))}
        </div>
      )}
      {legs && legs.length > 0 && (
        <div className="proof-legs" aria-label="cache economics per leg">
          {legs.map((leg, index) => (
            <div key={leg.runId || index} className="proof-leg-row">
              <span className="proof-leg-index">#{index + 1}</span>
              <span className="proof-leg-name">{leg.scenario}</span>
              <span className="proof-leg-dur">{leg.duration}</span>
              <span className="proof-leg-hm">
                {leg.hits}/{leg.misses}
              </span>
            </div>
          ))}
          <span className="proof-legs-caption">hits / misses per leg — none recorded</span>
        </div>
      )}
      {claims.length > 0 && (
        <ul className="proof-claim-list">
          {claims.map((claim) => (
            <li key={claim}>{claimNodes(claim)}</li>
          ))}
        </ul>
      )}
      {unsupported.length > 0 && (
        <div className="proof-unsupported">
          <span className="proof-unsupported-label">Unsupported claims — named, not hidden</span>
          <div className="proof-unsupported-chips">
            {unsupported.map((claim) => (
              <UnsupportedClaimChip key={claim} claim={labelKind(claim)} />
            ))}
          </div>
        </div>
      )}
      <EvidenceRefs refs={block.evidence_refs} defaultOpen={active} />
    </section>
  );
}

/** Collapsible evidence-ref footer (redesign P5): count pill + expand on
 *  demand, middle-truncated mono refs with copy, "show N more…" past the
 *  preview limit. Collapsed by default except on the active block. Redacted
 *  refs keep their slot as a lock chip carrying the partial path. */
function EvidenceRefs({ refs, defaultOpen }: { refs: string[]; defaultOpen: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const [showAll, setShowAll] = useState(false);
  useEffect(() => {
    if (defaultOpen) setOpen(true);
  }, [defaultOpen]);
  if (refs.length === 0) return null;
  const shown = showAll ? refs : refs.slice(0, REFS_PREVIEW_LIMIT);
  const hidden = refs.length - shown.length;
  return (
    <div className="proof-refs">
      <button
        type="button"
        className="proof-refs-toggle"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <ChevronRight size={12} className={`proof-refs-caret${open ? " open" : ""}`} aria-hidden="true" />
        <span className="proof-refs-word">evidence refs</span>
        <span className="proof-refs-count">{refs.length}</span>
      </button>
      {open && (
        <div className="proof-refs-list">
          {shown.map((ref) => (
            <EvidenceRefRow key={ref} value={ref} />
          ))}
          {hidden > 0 && (
            <button type="button" className="proof-refs-more" onClick={() => setShowAll(true)}>
              show {hidden} more…
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function EvidenceRefRow({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  if (isRedactedValue(value)) {
    return (
      <div className="proof-ref-row proof-ref-row--redacted">
        <RedactionChip state="redacted" value={value} />
      </div>
    );
  }
  return (
    <div className="proof-ref-row">
      <code title={value}>{middleTruncate(value)}</code>
      <button
        type="button"
        className="proof-ref-copy"
        aria-label={`Copy ${value}`}
        onClick={() => {
          void navigator.clipboard?.writeText(value).then(() => {
            setCopied(true);
            window.setTimeout(() => setCopied(false), 1400);
          });
        }}
      >
        {copied ? "copied" : <Copy size={12} aria-hidden="true" />}
      </button>
    </div>
  );
}

/**
 * Remote Boundary (redesign P6 — DESIGN-SYSTEM.md §5, board 1h). Centered E3
 * panel. A dashed globe emblem, the honest boundary statement, a 3×2 grid of
 * DASHED metric cells (slate, NEVER red — "not observed" is a calm stated
 * boundary), what would earn the claims, the unsupported-claims set, and a
 * truth footer asserting the block claims nothing it cannot prove. Every value
 * is a real proof-packet number. Per-boundary rows shape-encode source_kind.
 */
export function RemoteBoundaryLensPanel(_instance: ComponentInstance) {
  const { bindings, routeActions } = useViewContext();
  const view = useMemo(
    () => remoteBoundaryView(bindings.actionGraph, bindings.proofPacket),
    [bindings.actionGraph, bindings.proofPacket],
  );

  return (
    <aside className="remote-lens" aria-label="remote execution boundary">
      <button
        className="close-button remote-close"
        onClick={() => routeActions.setMode("graph")}
        aria-label="Close remote boundary"
      >
        <X size={16} />
      </button>
      <div className="remote-lead">
        <span className="remote-emblem" aria-hidden="true">
          <Globe size={26} />
        </span>
        <span className="remote-overline">REMOTE EXECUTION BOUNDARY · DERIVED JOIN</span>
        <h2 className="remote-statement">{view.statement}</h2>
        <p className="remote-explainer">{view.explainer}</p>
        <span className="remote-observed-line">{view.observedLine}</span>
      </div>

      <div className="remote-grid" aria-label="remote boundary metrics">
        {view.countCells.map((cell) => (
          <div key={cell.key} className="remote-cell remote-cell--count">
            <strong className="remote-cell-value">{cell.value}</strong>
            <span className="remote-cell-label">{cell.label}</span>
          </div>
        ))}
        {view.flagCells.map((cell) => (
          <div key={cell.key} className="remote-cell remote-cell--flag">
            <span className="remote-cell-flag">
              <SourceGlyph kind="future" size={11} title={null} />
              {cell.value}
            </span>
            <span className="remote-cell-label">{cell.label}</span>
          </div>
        ))}
      </div>

      {view.earnClaims.length > 0 && (
        <div className="remote-earn">
          <span className="remote-earn-overline">WHAT WOULD EARN THESE CLAIMS</span>
          <ul className="remote-earn-list">
            {view.earnClaims.map((claim) => (
              <li key={claim}>{claim}</li>
            ))}
          </ul>
        </div>
      )}

      {view.boundaries.length > 0 && (
        <div className="remote-boundaries">
          {view.boundaries.map((boundary) => (
            <div key={boundary.title} className="remote-boundary-row">
              <SourceGlyph kind={boundary.sourceKind} size={11} />
              <div className="remote-boundary-text">
                <span className="remote-boundary-kind">{labelKind(boundary.kind)}</span>
                <h3 className="remote-boundary-title">{boundary.title}</h3>
                <p className="remote-boundary-summary">{boundary.summary}</p>
              </div>
              <span className="truth-value remote-boundary-conf">
                <ConfidenceMeter confidence={boundary.confidence as Confidence} />
                {boundary.confidence}
              </span>
            </div>
          ))}
        </div>
      )}

      {view.unsupportedClaims.length > 0 && (
        <div className="remote-unsupported">
          <span className="remote-unsupported-label">Unsupported claims — named, not hidden</span>
          <div className="remote-unsupported-chips">
            {view.unsupportedClaims.map((claim) => (
              <UnsupportedClaimChip key={claim} claim={labelKind(claim)} />
            ))}
          </div>
        </div>
      )}

      <div className="remote-footer">
        <SourceGlyph kind="future" size={11} title={null} />
        <ConfidenceMeter confidence="unknown" />
        <span>this block asserts nothing it cannot prove</span>
      </div>
    </aside>
  );
}

/** Honest empty state (board 1i) — no compare projection is bound. NLFR never
 *  fabricates a comparison; it names the file to place and offers the Composer.
 *  The "Open Composer" hook is wired by P7 (the composer drawer). */
function CompareEmptyState({ pathHint, onClose }: { pathHint: string; onClose: () => void }) {
  return (
    <aside className="compare-lens compare-lens--empty" aria-label="multi-run compare">
      <button className="close-button compare-close" onClick={onClose} aria-label="Close compare lens">
        <X size={16} />
      </button>
      <div className="compare-empty-card" data-testid="compare-empty-state">
        <SourceGlyph kind="future" size={22} title={null} />
        <h2 className="compare-empty-title">No comparison is bound</h2>
        <p className="compare-empty-body">
          Place <code>{pathHint}</code> in <code>public/projections/</code> to render a derived proof-packet
          diff. NLFR never fabricates a comparison.
        </p>
        <button
          type="button"
          className="compare-empty-composer"
          data-testid="compare-open-composer"
          title="The Composer drawer (bind run groups) arrives in a later phase (P7)."
        >
          Open Composer to bind run groups →
        </button>
      </div>
    </aside>
  );
}

/**
 * Compare Runs (redesign P6 — DESIGN-SYSTEM.md §6, board 1i). The context
 * banner re-tones derived amber (P3). Header = two run-group pills + arrow-swap;
 * a row of dimension cards (left value / delta pill / right value); the Agent
 * Provenance dimension renders as a full-width two-column card. When no compare
 * projection is bound, the honest empty state states so — never a fabricated
 * comparison.
 */
export function CompareLensPanel(instance: ComponentInstance) {
  const { bindings, routeActions } = useViewContext();
  const projection = bindings.compareProjection;
  const pathHint = stringProp(instance.props, "empty_state_path_hint") || "compare-projection.json";

  if (!projection) {
    return <CompareEmptyState pathHint={pathHint} onClose={() => routeActions.setMode("graph")} />;
  }

  const leftRuns = finiteSummary(projection.summary, "left_runs");
  const rightRuns = finiteSummary(projection.summary, "right_runs");

  return (
    <aside className="compare-lens" aria-label="multi-run compare">
      <button
        className="close-button compare-close"
        onClick={() => routeActions.setMode("graph")}
        aria-label="Close compare lens"
      >
        <X size={16} />
      </button>
      <header className="compare-head">
        <span className="compare-overline">COMPARE RUNS · DERIVED JOIN</span>
        <div className="compare-run-groups">
          <span className="compare-run-pill compare-run-pill--left">
            {projection.left_run_group}
            {leftRuns !== null && <span className="compare-run-count"> · {leftRuns} runs</span>}
          </span>
          <span className="compare-swap" aria-hidden="true">
            <ArrowLeftRight size={13} />
          </span>
          <span className="compare-run-pill compare-run-pill--right">
            {projection.right_run_group}
            {rightRuns !== null && <span className="compare-run-count"> · {rightRuns} runs</span>}
          </span>
        </div>
        <div className="compare-head-truth">
          <SourceGlyph kind={projection.source_kind} size={11} />
          <ConfidenceMeter confidence={projection.confidence} />
          <span className="compare-dimension-count">
            {projection.dimensions.length} dimension{projection.dimensions.length === 1 ? "" : "s"}
          </span>
        </div>
      </header>
      <div className="compare-cards">
        {projection.dimensions.map((dimension) => (
          <CompareDimensionView
            key={dimension.id}
            dimension={dimension}
            leftRunGroup={projection.left_run_group}
            rightRunGroup={projection.right_run_group}
          />
        ))}
      </div>
    </aside>
  );
}

function finiteSummary(summary: Record<string, unknown>, key: string): number | null {
  const value = summary[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function CompareDimensionCardPanel(instance: ComponentInstance) {
  const { bindings } = useViewContext();
  const dimensionId = stringProp(instance.props, "dimension_id");
  const projection = bindings.compareProjection;
  const dimension = projection?.dimensions.find((entry) => entry.id === dimensionId);
  if (!dimension || !projection) return null;
  return (
    <CompareDimensionView
      dimension={dimension}
      leftRunGroup={projection.left_run_group}
      rightRunGroup={projection.right_run_group}
    />
  );
}

function ProvenanceBlockCard({ block }: { block: ProvenanceBlockSummary }) {
  return (
    <article className={`provenance-block ${block.sourceKind}`}>
      <div className="provenance-block-heading">
        <SourceGlyph kind={block.sourceKind as SourceKind} size={11} />
        {block.badge ? (
          <ProvenanceChip badge={block.badge} />
        ) : (
          <span className="provenance-chip provenance--asserted">no provenance class</span>
        )}
      </div>
      {block.title && <h4>{block.title}</h4>}
      <dl className="provenance-block-facts">
        {block.model && (
          <div>
            <dt>model</dt>
            <dd>{block.model}</dd>
          </div>
        )}
        {block.sessionId && (
          <div>
            <dt>session</dt>
            <dd>
              <code>{block.sessionId}</code>
            </dd>
          </div>
        )}
        {block.promptSha256Prefix && (
          <div>
            <dt>prompt sha256</dt>
            <dd>
              <code>{block.promptSha256Prefix}…</code>
            </dd>
          </div>
        )}
      </dl>
    </article>
  );
}

function ProvenanceSideColumn({
  title,
  side,
}: {
  title: string;
  side: ReturnType<typeof provenanceSide>;
}) {
  return (
    <div className={`provenance-side${side.blocks.length === 0 ? " provenance-side--empty" : ""}`}>
      <span className="provenance-side-title">{title}</span>
      {side.blocks.length === 0 ? (
        <div className="provenance-side-empty">
          <SourceGlyph kind="future" size={13} title={null} />
          <strong>No agent receipts recorded</strong>
          <span>
            {side.present
              ? "provenance blocks recorded without receipt summaries — stated, not padded"
              : `${side.blockCount} agent_provenance blocks in this packet — stated, not padded`}
          </span>
        </div>
      ) : (
        side.blocks.map((block) => <ProvenanceBlockCard key={block.id} block={block} />)
      )}
    </div>
  );
}

function AgentProvenanceCompare({
  dimension,
  leftRunGroup,
  rightRunGroup,
}: {
  dimension: CompareProjection["dimensions"][number];
  leftRunGroup: string;
  rightRunGroup: string;
}) {
  const left = provenanceSide(dimension.left);
  const right = provenanceSide(dimension.right);
  return (
    <div className="compare-provenance" data-testid="compare-agent-provenance">
      <div className="compare-provenance-grid">
        <ProvenanceSideColumn title={leftRunGroup} side={left} />
        <ProvenanceSideColumn title={rightRunGroup} side={right} />
      </div>
    </div>
  );
}

/** Agent-provenance block-count pill: "differs · +N blocks" (derived amber) or
 *  "match · N blocks" — from the real recorded delta, never padded. */
function provenanceDeltaPill(dimension: CompareDimension): { text: string; changed: boolean } {
  const delta = payloadRecord(dimension.delta) ?? {};
  const changed = delta.present_changed === true;
  const count = typeof delta.block_count_delta === "number" ? delta.block_count_delta : 0;
  const signed = count > 0 ? `+${count}` : String(count);
  return {
    text: changed ? `differs · ${signed} blocks` : `match · ${count} blocks`,
    changed,
  };
}

/** Full-width Agent Provenance card (§6): header + differs/match pill + the
 *  two-column receipts-vs-empty comparison. */
function AgentProvenanceCard({
  dimension,
  leftRunGroup,
  rightRunGroup,
}: {
  dimension: CompareDimension;
  leftRunGroup: string;
  rightRunGroup: string;
}) {
  const pill = provenanceDeltaPill(dimension);
  return (
    <section className="compare-card compare-card--full compare-card--provenance">
      <header className="compare-card-head">
        <SourceGlyph kind={dimension.source_kind} size={11} />
        <h3 className="compare-card-title">{dimension.title}</h3>
        <span className={`compare-delta-pill compare-delta-pill--${pill.changed ? "differs" : "match"}`}>
          {pill.text}
        </span>
        <ConfidenceMeter confidence={dimension.confidence} size="md" />
      </header>
      <AgentProvenanceCompare dimension={dimension} leftRunGroup={leftRunGroup} rightRunGroup={rightRunGroup} />
      <p className="compare-card-caption">{dimension.summary}</p>
      <EvidenceRefs refs={dimension.evidence_refs} defaultOpen={false} />
    </section>
  );
}

function CompareDimensionView({
  dimension,
  leftRunGroup,
  rightRunGroup,
}: {
  dimension: CompareProjection["dimensions"][number];
  leftRunGroup?: string;
  rightRunGroup?: string;
}) {
  const left = leftRunGroup ?? "left run group";
  const right = rightRunGroup ?? "right run group";

  if (dimension.id === "agent_provenance") {
    return <AgentProvenanceCard dimension={dimension} leftRunGroup={left} rightRunGroup={right} />;
  }

  const headline = compareHeadline(dimension);
  const sourceMeta = SOURCE_KIND_META[dimension.source_kind] ?? SOURCE_KIND_META.unknown;

  return (
    <section className="compare-card compare-card--dimension">
      <header className="compare-card-head">
        <SourceGlyph kind={dimension.source_kind} size={11} />
        <h3 className="compare-card-title">{dimension.title}</h3>
        <ConfidenceMeter confidence={dimension.confidence} size="md" />
      </header>
      <div className="compare-card-values">
        <div className="compare-val compare-val--left">
          <span className="compare-val-tag">{left}</span>
          <strong className="compare-val-num">{headline.left}</strong>
        </div>
        {headline.delta !== null && (
          <span className={`compare-delta-pill compare-delta-pill--${headline.deltaTone}`}>{headline.delta}</span>
        )}
        <div className="compare-val compare-val--right">
          <span className="compare-val-tag">{right}</span>
          <strong className="compare-val-num">{headline.right}</strong>
        </div>
      </div>
      <p className="compare-card-caption">{headline.caption}</p>
      <div className="compare-card-truth">
        <span className="truth-value">
          <SourceGlyph kind={dimension.source_kind} size={11} />
          <span>{sourceMeta.label}</span>
        </span>
        <span className="truth-value">
          <ConfidenceMeter confidence={dimension.confidence} />
          <span>{dimension.confidence}</span>
        </span>
        <RedactionChip state={dimension.redaction_state} />
      </div>
      <EvidenceRefs refs={dimension.evidence_refs} defaultOpen={false} />
    </section>
  );
}

export type TablePanelKind =
  | "evidence_inspector"
  | "proof_drawer"
  | "proof_block_card"
  | "remote_boundary_lens"
  | "compare_lens"
  | "compare_dimension_card";

export const TABLE_PANELS: Record<TablePanelKind, (instance: ComponentInstance) => React.ReactNode> = {
  evidence_inspector: EvidenceInspectorPanel,
  proof_drawer: ProofDrawerPanel,
  proof_block_card: ProofBlockCardPanel,
  remote_boundary_lens: RemoteBoundaryLensPanel,
  compare_lens: CompareLensPanel,
  compare_dimension_card: CompareDimensionCardPanel,
};
