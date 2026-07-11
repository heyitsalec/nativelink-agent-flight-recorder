import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  AlertTriangle,
  Bot,
  Columns2,
  CornerDownLeft,
  Database,
  FileCheck2,
  Globe,
  History,
  Info,
  Rows3,
  RotateCcw,
  Search,
} from "lucide-react";
import { ComposerDrawer } from "./ComposerDrawer";
import { MobileBottomSheet } from "./shared/MobileBottomSheet";
import { SystemStates } from "./shared/SystemStates";
import {
  filterPaletteCommands,
  highlightSegments,
  PALETTE_GROUP_LABELS,
  PALETTE_GROUP_ORDER,
  type PaletteCommand,
} from "./shared/paletteCommands";
import type { ComponentInstance } from "../view/types";
import { useViewContext, type ViewContextValue } from "../view/ViewContext";
import { useOptionalZoomControllerRef } from "./shared/ZoomContext";
import { stringProp } from "./shared/props";
import { SOURCE_KIND_META } from "./shared/truth/copy";

const NON_EVIDENTIARY_TOOLTIP =
  "Operator commands filter and navigate the loaded projection only. They are never persisted or exported as evidence.";

const PALETTE_FOOTER =
  "Commands filter and navigate the loaded projection only — never persisted, never exported as evidence.";

type ZoomRef = ReturnType<typeof useOptionalZoomControllerRef>;

/**
 * Honest, data-driven note for the "agent loop" focus. The agent focus
 * highlights agent + change nodes (see highlightedIds); this note reflects the
 * REAL `source_kind` of the nodes actually loaded, so it can never mislabel —
 * e.g. it must not call recorded (`collectable_v1`) change evidence "simulated".
 * When no agent node is present it says so instead of implying one exists.
 */
function agentLoopNote(nodes: ViewContextValue["graph"]["nodes"]): string {
  const agents = nodes.filter((node) => node.kind === "agent");
  const changes = nodes.filter((node) => node.kind === "change");
  const focused = [...agents, ...changes];
  if (focused.length === 0) {
    return "Agent loop isolates agent and change provenance — none recorded in this projection.";
  }
  const kinds = new Set(focused.map((node) => node.source_kind));
  const kindWord =
    kinds.size === 1
      ? SOURCE_KIND_META[[...kinds][0]]?.label.toLowerCase() ?? "labeled"
      : "mixed-source";
  const counts = [
    agents.length ? `${agents.length} agent` : null,
    changes.length ? `${changes.length} change` : null,
  ]
    .filter(Boolean)
    .join(" + ");
  const noAgent = agents.length === 0 ? "; no agent node in this projection" : "";
  return `Agent loop isolates ${counts} — ${kindWord} evidence${noAgent}.`;
}

type CommandDeps = {
  graph: ViewContextValue["graph"];
  bindings: ViewContextValue["bindings"];
  routeActions: ViewContextValue["routeActions"];
  zoomRef: ZoomRef;
  openComposer: () => void;
};

/**
 * The operator command router (redesign P3, augmented in P7). Both the operator
 * bar's text input (Enter) AND the ⌘K palette rows call this exact function, so
 * the palette augments the router without forking its behavior. Non-evidentiary:
 * it only sets ephemeral focus/lens/selection route state.
 */
export function executeOperatorCommand(raw: string, deps: CommandDeps): void {
  const value = raw.trim().toLowerCase();
  if (!value) return;
  const { graph, bindings, routeActions, zoomRef, openComposer } = deps;

  if (value.includes("composer") || value.includes("layout")) {
    openComposer();
    routeActions.setOperatorNote("View composer open — export layout JSON only; no collectable claims.");
    routeActions.setCommand("");
    return;
  }

  // NOTE ordering: setMode() resets focus to the mode's default (applyModeChange),
  // so the mode MUST be set BEFORE the focus, or the focus is silently clobbered
  // and the "focus applied" pill never appears. Every branch below sets mode
  // first, then the intended focus.
  if (value.includes("cache")) {
    routeActions.setMode("graph");
    routeActions.setFocus("cache");
    routeActions.setOperatorNote("Cache evidence is highlighted; derived events stay amber.");
  } else if (value.includes("fail")) {
    routeActions.setMode("graph");
    routeActions.setFocus("failures");
    const firstFailure = graph.nodes.find((node) => node.kind === "failure");
    routeActions.setSelectedId(firstFailure?.id ?? null);
    routeActions.setOperatorNote("Failure path is isolated with its evidence refs open.");
  } else if (value.includes("proof")) {
    routeActions.setMode("proof");
    routeActions.setFocus("derived");
    routeActions.setOperatorNote("Proof lens is open; unsupported claims remain explicit.");
  } else if (value.includes("remote") || value.includes("worker") || value.includes("execution")) {
    routeActions.setMode("remote");
    routeActions.setFocus("remote");
    routeActions.setOperatorNote("Remote boundary is isolated; worker claims stay gated.");
  } else if (value.includes("agent") || value.includes("loop") || value.includes("change")) {
    routeActions.setMode("graph");
    routeActions.setFocus("agent");
    const firstAgent = graph.nodes.find((node) => node.kind === "agent");
    routeActions.setSelectedId(firstAgent?.id ?? null);
    routeActions.setOperatorNote(agentLoopNote(graph.nodes));
  } else if (value.includes("compare") || value.includes("diff")) {
    routeActions.setMode("compare");
    routeActions.setFocus("derived");
    routeActions.setOperatorNote(
      bindings.compareProjection
        ? "Compare lens shows derived proof-packet deltas only."
        : "Compare lens unavailable — compare-projection.json not loaded.",
    );
  } else if (value.includes("replay") || value.includes("playback") || value.includes("timeline")) {
    // "timeline" ownership (review arbitration): the projection this lens
    // replays is literally named timeline (timeline.json), so explicit
    // free-text "timeline" opens Replay. Runway keeps the keyword only for
    // fuzzy palette RANKING (paletteCommands) — this branch sits before the
    // runway branch, so it wins the router.
    routeActions.setMode("replay");
    routeActions.setFocus("all");
    routeActions.setOperatorNote(
      bindings.timelineProjection
        ? "Replay walks the recorded flight record — playback auto-pauses at repair loops."
        : "Replay lens unavailable — timeline.json not loaded.",
    );
  } else if (value.includes("runway")) {
    routeActions.setMode("runway");
    routeActions.setFocus("all");
    routeActions.setOperatorNote("Validation runway is projected over the same graph evidence.");
  } else if (value.includes("reset")) {
    // Explicit "reset" (board 1l): clear focus, fit graph, KEEP the selection —
    // distinct from the catch-all below, which fully resets on unrecognized text.
    routeActions.setMode("graph");
    routeActions.setFocus("all");
    zoomRef?.current?.reset();
    routeActions.setOperatorNote("Canvas reset — focus cleared, graph fit, selection kept.");
  } else {
    routeActions.setMode("graph");
    routeActions.setFocus("all");
    routeActions.setSelectedId(null);
    zoomRef?.current?.reset();
    routeActions.setOperatorNote("Canvas reset to the full Action Graph.");
  }
  routeActions.setCommand("");
}

const PALETTE_ICONS: Record<string, typeof Search> = {
  alert: AlertTriangle,
  database: Database,
  bot: Bot,
  "file-check": FileCheck2,
  rows: Rows3,
  globe: Globe,
  columns: Columns2,
  history: History,
  reset: RotateCcw,
};

function HighlightedName({ name, query }: { name: string; query: string }) {
  const segments = highlightSegments(name, query);
  return (
    <span className="palette-row-name">
      {segments.map((seg, i) =>
        seg.match ? (
          <mark key={i} className="palette-mark">
            {seg.text}
          </mark>
        ) : (
          <span key={i}>{seg.text}</span>
        ),
      )}
    </span>
  );
}

/**
 * ⌘K command palette (redesign P7 §8, board 1l). Centered modal over a scrim;
 * grouped, fuzzy-filtered results; each row routes through the SAME operator
 * command as the bar. Non-evidentiary by construction — nothing here is
 * persisted or exported.
 */
function CommandPalette({
  open,
  onClose,
  onRun,
}: {
  open: boolean;
  onClose: () => void;
  onRun: (command: PaletteCommand) => void;
}) {
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const results = useMemo(() => filterPaletteCommands(query), [query]);

  useEffect(() => {
    setActiveIndex(0);
  }, [query]);

  useEffect(() => {
    if (open) {
      setQuery("");
      setActiveIndex(0);
      const id = window.setTimeout(() => inputRef.current?.focus(), 0);
      return () => window.clearTimeout(id);
    }
  }, [open]);

  if (!open) return null;

  const grouped = PALETTE_GROUP_ORDER.map((group) => ({
    group,
    commands: results.filter((command) => command.group === group),
  })).filter((entry) => entry.commands.length > 0);

  function handleKeyDown(event: React.KeyboardEvent) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((i) => (results.length ? (i + 1) % results.length : 0));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((i) => (results.length ? (i - 1 + results.length) % results.length : 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      const command = results[activeIndex];
      if (command) onRun(command);
    } else if (event.key === "Escape") {
      event.preventDefault();
      onClose();
    }
  }

  return (
    <div
      className="palette-scrim"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        className="palette-modal"
        role="dialog"
        aria-modal="true"
        aria-label="operator command palette"
        data-testid="command-palette"
      >
        <div className="palette-input-row">
          <Search size={15} aria-hidden="true" className="palette-search-icon" />
          <input
            ref={inputRef}
            className="palette-input"
            aria-label="operator command palette input"
            placeholder="Filter or jump — failures, cache, agents, proof, runway, reset"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={handleKeyDown}
          />
          <kbd className="palette-esc" onClick={onClose}>
            esc
          </kbd>
        </div>

        <div className="palette-results" role="listbox" aria-label="commands">
          {grouped.length === 0 ? (
            <p className="palette-empty">No commands match — try failures, proof, or reset.</p>
          ) : (
            grouped.map(({ group, commands }) => (
              <div className="palette-group" key={group}>
                <p className="palette-overline">{PALETTE_GROUP_LABELS[group]}</p>
                {commands.map((command) => {
                  const flatIndex = results.indexOf(command);
                  const active = flatIndex === activeIndex;
                  const Icon = PALETTE_ICONS[command.icon] ?? Search;
                  return (
                    <button
                      type="button"
                      key={command.id}
                      role="option"
                      aria-selected={active}
                      className={`palette-row${active ? " palette-row--active" : ""}`}
                      data-testid="palette-row"
                      data-command={command.id}
                      onMouseEnter={() => setActiveIndex(flatIndex)}
                      onClick={() => onRun(command)}
                    >
                      <span className="palette-row-icon" aria-hidden="true">
                        <Icon size={14} />
                      </span>
                      <span className="palette-row-copy">
                        <HighlightedName name={command.name} query={query} />
                        <span className="palette-row-desc">{command.description}</span>
                      </span>
                      {active && (
                        <span className="palette-row-enter" aria-hidden="true">
                          <CornerDownLeft size={13} />
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            ))
          )}
        </div>

        <div className="palette-footer" data-testid="palette-nonevidentiary">
          <Info size={13} aria-hidden="true" />
          <span>{PALETTE_FOOTER}</span>
        </div>
      </div>
    </div>
  );
}

export function OperatorCommandBarPanel(instance: ComponentInstance) {
  const { graph, bindings, route, routeActions, spec, overlay, overlayActions } = useViewContext();
  const zoomRef = useOptionalZoomControllerRef();
  const placeholder = stringProp(
    instance.props,
    "placeholder",
    "Filter or jump — failures, cache, agents, proof, runway, reset",
  );

  const deps = useMemo<CommandDeps>(
    () => ({ graph, bindings, routeActions, zoomRef, openComposer: overlayActions.openComposer }),
    [graph, bindings, routeActions, zoomRef, overlayActions.openComposer],
  );

  const runCommand = useCallback(
    (raw: string) => executeOperatorCommand(raw, deps),
    [deps],
  );

  // ⌘K / Ctrl-K toggles the palette from anywhere; Escape closes overlays.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        overlayActions.togglePalette();
      } else if (event.key === "Escape" && overlay.paletteOpen) {
        overlayActions.closePalette();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [overlay.paletteOpen, overlayActions]);

  const lensClass =
    route.mode === "proof"
      ? "operator--lens-proof"
      : route.mode === "remote"
        ? "operator--lens-remote"
        : route.mode === "compare"
          ? "operator--lens-compare"
          : route.mode === "replay"
            ? "operator--lens-replay"
            : route.mode === "runway"
              ? "operator--lens-runway"
              : "";

  const overlays =
    typeof document !== "undefined"
      ? createPortal(
          <>
            <SystemStates />
            <MobileBottomSheet />
            <ComposerDrawer
              open={overlay.composerOpen}
              onClose={overlayActions.closeComposer}
              initialSpec={spec}
              bindingStatus={bindings.status}
            />
            <CommandPalette
              open={overlay.paletteOpen}
              onClose={overlayActions.closePalette}
              onRun={(command) => {
                runCommand(command.command);
                overlayActions.closePalette();
              }}
            />
          </>,
          document.body,
        )
      : null;

  // Clicking the operator BAR itself opens the palette (DESIGN-SYSTEM §8) — but
  // NEVER when the operator is interacting with the text input or an existing
  // control (input keeps its own focus + Enter→runCommand), and never for the
  // portaled overlays (which bubble through the React tree but live outside this
  // DOM node, so a contains() check on the real DOM target skips them).
  const onBarClick = useCallback(
    (event: React.MouseEvent<HTMLDivElement>) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      if (!event.currentTarget.contains(target)) return;
      if (target.closest("input, button, kbd, a, select, textarea")) return;
      overlayActions.openPalette();
    },
    [overlayActions],
  );

  return (
    <div
      className={`operator ${lensClass}`.trim()}
      onClick={onBarClick}
      data-testid="operator-bar"
    >
      {overlays}
      <button
        type="button"
        className="operator-key"
        aria-label="Open command palette"
        onClick={() => overlayActions.openPalette()}
      >
        ⌘K
      </button>
      <div className="operator-copy">
        {route.operatorNote && <span className="operator-note">{route.operatorNote}</span>}
        <input
          aria-label="operator command"
          value={route.command}
          placeholder={placeholder}
          onChange={(event) => routeActions.setCommand(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") runCommand(route.command);
          }}
        />
      </div>
      <span className="operator-divider" aria-hidden="true" />
      <span className="operator-nonevidentiary" title={NON_EVIDENTIARY_TOOLTIP}>
        <Info size={13} aria-hidden="true" />
        <span>local filter · not evidence</span>
      </span>
    </div>
  );
}

export type OperatorPanelKind = "operator_command_bar";

export const OPERATOR_PANELS: Record<
  OperatorPanelKind,
  (instance: ComponentInstance) => React.ReactNode
> = {
  operator_command_bar: OperatorCommandBarPanel,
};
