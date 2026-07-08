import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { ChevronRight, Copy, Download, GitCompare, Maximize2, Network, ReceiptText, X } from "lucide-react";
import {
  blockIndexMeta,
  blocksBelow,
  formatMetricValue,
  isRedactedValue,
  labelKind,
  payloadRecord,
  proofRollup,
  redactedValueForBlock,
  type RemoteLensModel,
  unsupportedClaimsFromPayload,
} from "../pageModel";
import {
  agentReceiptModel,
  provenanceSide,
  truncateHash,
  type AgentReceiptModel,
  type ProvenanceBadge as ProvenanceBadgeModel,
  type ProvenanceBlockSummary,
} from "../receiptModel";
import type {
  CompareProjection,
  Confidence,
  PositionedNode,
  ProofBlock,
  ProofMetricValue,
  ProofPacket,
  SourceKind,
} from "../types";
import type { ComponentInstance } from "../view/types";
import { useViewComponent, useViewContext } from "../view/ViewContext";
import { stringProp } from "./shared/props";
import {
  ConfidenceMeter,
  ProvenanceBadge,
  RedactionChip,
  SourceGlyph,
  StatusGlyph,
  UnsupportedClaimChip,
} from "./shared/truth";

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

function CopyHash({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="receipt-hash">
      <span className="receipt-hash-label">{label}</span>
      <code title={value}>{truncateHash(value)}</code>
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

function ReceiptDetailPane({ receipt }: { receipt: AgentReceiptModel }) {
  const fields: { label: string; value: string | null }[] = [
    { label: "Model", value: receipt.model },
    { label: "Session", value: receipt.sessionId },
    { label: "CLI version", value: receipt.cliVersion },
    { label: "Captured at", value: receipt.capturedAt },
  ];
  const present = fields.filter((field) => field.value !== null);

  return (
    <section className="receipt-pane" aria-label="agent receipt" data-testid="receipt-detail-pane">
      <div className="receipt-pane-heading">
        <ReceiptText size={15} />
        <span>Agent receipt</span>
        <ProvenanceChip badge={receipt.badge} />
      </div>
      <p className="receipt-pane-hint">{receipt.badge.hint}</p>
      {present.length > 0 && (
        <dl className="truth-grid receipt-grid">
          {present.map((field) => (
            <div key={field.label}>
              <dt>{field.label}</dt>
              <dd>{field.value}</dd>
            </div>
          ))}
        </dl>
      )}
      {receipt.usage.length > 0 && (
        <div className="receipt-usage lens-metric-strip" aria-label="receipt token usage">
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
    </section>
  );
}

function Inspector({ node, onClose }: { node: PositionedNode; onClose: () => void }) {
  const message = failureMessage(node);
  const receipt = node.kind === "agent" ? agentReceiptModel(node.payload) : null;

  return (
    <aside
      className={`inspector ${node.kind === "failure" ? "inspector--failure" : ""}`}
      aria-label="selected evidence"
    >
      <button className="close-button" onClick={onClose} aria-label="Close inspector">
        <Maximize2 size={16} />
      </button>
      <div className="inspector-heading">
        <SourceGlyph kind={node.source_kind} size={11} />
        <p>{labelKind(node.kind)}</p>
        <h2>{node.label}</h2>
      </div>
      {receipt && <ReceiptDetailPane receipt={receipt} />}
      {message && (
        <section className="failure-message-panel" aria-label="failure message">
          <span className="failure-message-label">Failure message</span>
          <p className="failure-message-body">{message}</p>
        </section>
      )}
      <dl className="truth-grid">
        <div>
          <dt>Source</dt>
          <dd className="truth-value">
            <SourceGlyph kind={node.source_kind} size={11} />
            <span>{node.source_kind}</span>
          </dd>
        </div>
        <div>
          <dt>Confidence</dt>
          <dd className="truth-value">
            <ConfidenceMeter confidence={node.confidence} />
            <span>{node.confidence}</span>
          </dd>
        </div>
        <div>
          <dt>Redaction</dt>
          <dd className="truth-value">
            <RedactionChip state={node.redaction_state} />
          </dd>
        </div>
        <div>
          <dt>Status</dt>
          <dd className="truth-value">
            <StatusGlyph status={node.status} />
          </dd>
        </div>
      </dl>
      <div className="evidence-list">
        <span>Evidence refs</span>
        {node.evidence_refs.map((ref) => (
          <code key={ref}>{ref}</code>
        ))}
      </div>
      {node.payload && Object.keys(node.payload).length > 0 && (
        <pre className="payload">{JSON.stringify(node.payload, null, 2)}</pre>
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

export function RemoteBoundaryLensPanel(_instance: ComponentInstance) {
  const { routeActions } = useViewContext();
  const lens = useViewComponent(_instance) as RemoteLensModel | null;
  if (!lens) return null;

  return (
    <aside className="remote-lens lens-panel lens-panel--remote" aria-label="remote execution boundary">
      <button
        className="close-button"
        onClick={() => routeActions.setMode("graph")}
        aria-label="Close remote boundary"
      >
        <X size={16} />
      </button>
      <div className="remote-lens-heading lens-heading">
        <Network size={18} />
        <p>Remote Boundary</p>
        <h2>{lens.statusLabel}</h2>
        <span className="lens-meta">
          {lens.boundaries.length} boundary{lens.boundaries.length === 1 ? "" : "ies"} · projection join
        </span>
      </div>
      <div className="remote-state-line lens-state-line">
        <SourceGlyph kind={lens.sourceKind as SourceKind} size={11} />
        <strong>{lens.modeLabel}</strong>
        <span className="truth-value">
          <ConfidenceMeter confidence={lens.confidence as Confidence} />
          {lens.confidence}
        </span>
      </div>
      <div className="remote-metrics lens-metric-strip">
        {lens.metrics.map((metric) => (
          <span key={metric.label}>
            <strong>{metric.value}</strong>
            {metric.label}
          </span>
        ))}
      </div>
      <div className="remote-boundaries lens-boundary-list">
        {lens.boundaries.map((boundary) => (
          <section key={boundary.title} className={`remote-boundary lens-boundary ${boundary.sourceKind}`}>
            <div>
              <p>{boundary.kind}</p>
              <h3>{boundary.title}</h3>
            </div>
            <span className="truth-value">
              <ConfidenceMeter confidence={boundary.confidence as Confidence} />
              {boundary.confidence}
            </span>
            <p>{boundary.summary}</p>
          </section>
        ))}
      </div>
      <div className="unsupported-list">
        <span>Unsupported claims — named, not hidden</span>
        <div>
          {lens.unsupportedClaims.map((claim) => (
            <UnsupportedClaimChip key={claim} claim={labelKind(claim)} />
          ))}
        </div>
      </div>
    </aside>
  );
}

export function CompareLensPanel(instance: ComponentInstance) {
  const { bindings, routeActions } = useViewContext();
  const projection = bindings.compareProjection;
  void stringProp(instance.props, "empty_state_path_hint");

  return (
    <aside className="compare-lens lens-panel lens-panel--compare" aria-label="multi-run compare">
      <button
        className="close-button"
        onClick={() => routeActions.setMode("graph")}
        aria-label="Close compare lens"
      >
        <X size={16} />
      </button>
      <div className="compare-lens-heading lens-heading">
        <GitCompare size={18} />
        <p>Multi-run Compare</p>
        {projection ? (
          <>
            <h2 className="compare-run-title">Run group deltas</h2>
            <div className="compare-run-pills" aria-label="compared run groups">
              <span className="compare-run-pill compare-run-pill--left">{projection.left_run_group}</span>
              <span className="compare-run-pill compare-run-pill--vs">vs</span>
              <span className="compare-run-pill compare-run-pill--right">{projection.right_run_group}</span>
            </div>
          </>
        ) : (
          <h2>No compare projection loaded</h2>
        )}
      </div>
      {!projection ? (
        <p className="compare-empty lens-empty">
          Place <code>compare-projection.json</code> under <code>public/projections/</code> to enable
          derived proof-packet diffs.
        </p>
      ) : (
        <>
          <div className="compare-state-line lens-state-line">
            <SourceGlyph kind={projection.source_kind} size={11} />
            <strong>{projection.source_kind}</strong>
            <span className="truth-value">
              <ConfidenceMeter confidence={projection.confidence} />
              {projection.confidence}
            </span>
            <span className="compare-dimension-count">
              {projection.dimensions.length} dimension{projection.dimensions.length === 1 ? "" : "s"}
            </span>
          </div>
          <div className="compare-dimension-list">
            {projection.dimensions.map((dimension) => (
              <CompareDimensionView
                key={dimension.id}
                dimension={dimension}
                leftRunGroup={projection.left_run_group}
                rightRunGroup={projection.right_run_group}
              />
            ))}
          </div>
        </>
      )}
    </aside>
  );
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
    <div className="provenance-side">
      <span className="provenance-side-title">{title}</span>
      {side.blocks.length === 0 ? (
        <p className="provenance-side-empty">
          {side.present
            ? "Provenance blocks recorded without receipt summaries."
            : "No agent provenance block recorded."}
        </p>
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

function CompareDimensionView({
  dimension,
  leftRunGroup,
  rightRunGroup,
}: {
  dimension: CompareProjection["dimensions"][number];
  leftRunGroup?: string;
  rightRunGroup?: string;
}) {
  const deltaEntries = Object.entries(dimension.delta ?? {}).filter(
    ([, value]) => value !== null && typeof value !== "object",
  );
  return (
    <section className={`compare-dimension ${dimension.source_kind}`}>
      <div className="compare-dimension-heading">
        <SourceGlyph kind={dimension.source_kind} size={11} />
        <div>
          <p>{dimension.id}</p>
          <h3>{dimension.title}</h3>
        </div>
      </div>
      <p className="compare-dimension-summary">{dimension.summary}</p>
      {dimension.id === "agent_provenance" && (
        <AgentProvenanceCompare
          dimension={dimension}
          leftRunGroup={leftRunGroup ?? "left run group"}
          rightRunGroup={rightRunGroup ?? "right run group"}
        />
      )}
      <dl className="truth-grid compare-dimension-truth">
        <div>
          <dt>Source</dt>
          <dd className="truth-value">
            <SourceGlyph kind={dimension.source_kind} size={11} />
            <span>{dimension.source_kind}</span>
          </dd>
        </div>
        <div>
          <dt>Confidence</dt>
          <dd className="truth-value">
            <ConfidenceMeter confidence={dimension.confidence} />
            <span>{dimension.confidence}</span>
          </dd>
        </div>
        <div>
          <dt>Redaction</dt>
          <dd className="truth-value">
            <RedactionChip state={dimension.redaction_state} />
          </dd>
        </div>
      </dl>
      {deltaEntries.length > 0 && (
        <div className="compare-delta-metrics" aria-label={`${dimension.title} delta`}>
          {deltaEntries.map(([key, value]) => (
            <span key={key}>
              <strong>{formatMetricValue(value as ProofMetricValue)}</strong>
              {labelKind(key)}
            </span>
          ))}
        </div>
      )}
      {(dimension.claims?.length ?? 0) > 0 && (
        <ul className="proof-claims">
          {dimension.claims.map((claim) => (
            <li key={claim}>{claim}</li>
          ))}
        </ul>
      )}
      {dimension.evidence_refs.length > 0 && (
        <div className="evidence-list proof-evidence">
          <span>Evidence refs</span>
          {dimension.evidence_refs.map((ref) => (
            <code key={ref}>{ref}</code>
          ))}
        </div>
      )}
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
