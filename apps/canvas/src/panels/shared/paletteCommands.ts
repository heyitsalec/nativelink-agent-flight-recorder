/**
 * Operator command palette catalog + fuzzy matcher (redesign P7 §8, board 1l).
 *
 * This module is deliberately JSX-free so `node --test` can import it directly
 * (Node strips the TS types on import) — the pure command metadata and the
 * fuzzy/highlight helpers are unit-tested in scripts/palette-fuzzy.test.mjs.
 * The lucide icon for each command is mapped by its `icon` key inside
 * OperatorPanel.tsx.
 *
 * HONESTY: every command routes through the SAME operator command string the
 * bar has always used (`command`), so the palette augments — never forks — the
 * operator router. The palette is non-evidentiary: it filters and navigates the
 * loaded projection only, and is never persisted or exported as evidence.
 */

export type PaletteGroup = "FOCUS" | "LENSES" | "CANVAS";

export type PaletteCommand = {
  id: string;
  group: PaletteGroup;
  /** Display name; the typed substring is highlighted in the row. */
  name: string;
  description: string;
  /** Fed verbatim to the operator command router — identical behavior. */
  command: string;
  /** lucide icon key, mapped to a component in OperatorPanel. */
  icon: string;
  /** Fuzzy-match haystack in addition to the name. */
  keywords: string[];
};

/** The overline order the palette renders groups in. */
export const PALETTE_GROUP_ORDER: PaletteGroup[] = ["FOCUS", "LENSES", "CANVAS"];

export const PALETTE_GROUP_LABELS: Record<PaletteGroup, string> = {
  FOCUS: "Focus — filters the loaded projection",
  LENSES: "Lenses",
  CANVAS: "Canvas",
};

export const PALETTE_COMMANDS: PaletteCommand[] = [
  {
    id: "focus-failures",
    group: "FOCUS",
    name: "focus failures",
    description: "isolate failing actions on the graph",
    command: "focus failures",
    icon: "alert",
    keywords: ["focus", "failures", "fail", "errors", "red"],
  },
  {
    id: "focus-cache-misses",
    group: "FOCUS",
    name: "focus cache misses",
    description: "highlight cache evidence on the graph",
    command: "focus cache misses",
    icon: "database",
    keywords: ["focus", "cache", "misses", "hits", "economics"],
  },
  {
    id: "agent-loop",
    group: "FOCUS",
    name: "agent loop",
    description: "isolate the agent → change → run arc",
    command: "agent loop",
    icon: "bot",
    keywords: ["agent", "loop", "change", "receipt"],
  },
  {
    id: "lens-proof",
    group: "LENSES",
    name: "proof",
    description: "open the proof-packet drawer",
    command: "proof",
    icon: "file-check",
    keywords: ["proof", "packet", "blocks", "claims"],
  },
  {
    id: "lens-runway",
    group: "LENSES",
    name: "runway",
    description: "open the validation runway timeline",
    command: "runway",
    icon: "rows",
    keywords: ["runway", "timeline", "lanes", "validation"],
  },
  {
    id: "lens-remote",
    group: "LENSES",
    name: "remote",
    description: "isolate the remote execution boundary",
    command: "remote",
    icon: "globe",
    keywords: ["remote", "worker", "execution", "boundary"],
  },
  {
    id: "lens-compare",
    group: "LENSES",
    name: "compare",
    description: "open the compare-runs lens",
    command: "compare",
    icon: "columns",
    keywords: ["compare", "diff", "runs", "delta"],
  },
  {
    id: "canvas-reset",
    group: "CANVAS",
    name: "reset",
    description: "clear focus, fit graph, keep selection",
    command: "reset",
    icon: "reset",
    keywords: ["reset", "clear", "fit", "default"],
  },
];

/** Longest contiguous case-insensitive substring index, or -1. */
function substringIndex(haystack: string, needle: string): number {
  return haystack.toLowerCase().indexOf(needle.toLowerCase());
}

/** True when the needle's chars appear in order within the haystack. */
function isSubsequence(haystack: string, needle: string): boolean {
  const h = haystack.toLowerCase();
  const n = needle.toLowerCase();
  let i = 0;
  for (let j = 0; j < h.length && i < n.length; j++) {
    if (h[j] === n[i]) i++;
  }
  return i === n.length;
}

/**
 * Rank a command against a query. Higher is better; null = no match.
 * Contiguous substring beats subsequence; an earlier match beats a later one;
 * a name match beats a keyword-only match.
 */
function scoreCommand(command: PaletteCommand, query: string): number | null {
  const nameSub = substringIndex(command.name, query);
  if (nameSub >= 0) return 1000 - nameSub;
  for (const keyword of command.keywords) {
    const kwSub = substringIndex(keyword, query);
    if (kwSub >= 0) return 500 - kwSub;
  }
  if (isSubsequence(command.name, query)) return 200;
  for (const keyword of command.keywords) {
    if (isSubsequence(keyword, query)) return 100;
  }
  return null;
}

/**
 * Fuzzy-filter the palette. An empty query returns everything in canonical
 * order (that IS the discoverability — the whole catalog is browsable). A
 * non-empty query keeps only matches, best score first.
 */
export function filterPaletteCommands(
  query: string,
  commands: PaletteCommand[] = PALETTE_COMMANDS,
): PaletteCommand[] {
  const normalized = query.trim();
  if (!normalized) return [...commands];
  const scored: { command: PaletteCommand; score: number; index: number }[] = [];
  commands.forEach((command, index) => {
    const score = scoreCommand(command, normalized);
    if (score !== null) scored.push({ command, score, index });
  });
  scored.sort((a, b) => (b.score === a.score ? a.index - b.index : b.score - a.score));
  return scored.map((entry) => entry.command);
}

export type HighlightSegment = { text: string; match: boolean };

/**
 * Split `text` into segments, marking the part matching `query` for the
 * teal-tint <mark>. Prefers a contiguous substring; falls back to the
 * subsequence characters so fuzzy matches are still visibly explained.
 */
export function highlightSegments(text: string, query: string): HighlightSegment[] {
  const normalized = query.trim();
  if (!normalized) return [{ text, match: false }];

  const sub = substringIndex(text, normalized);
  if (sub >= 0) {
    const segments: HighlightSegment[] = [];
    if (sub > 0) segments.push({ text: text.slice(0, sub), match: false });
    segments.push({ text: text.slice(sub, sub + normalized.length), match: true });
    if (sub + normalized.length < text.length) {
      segments.push({ text: text.slice(sub + normalized.length), match: false });
    }
    return segments;
  }

  // Subsequence fallback: mark the matched characters individually, coalescing
  // runs of same-match chars so the DOM stays compact.
  const lowerText = text.toLowerCase();
  const lowerQuery = normalized.toLowerCase();
  const matched: boolean[] = new Array(text.length).fill(false);
  let qi = 0;
  for (let ti = 0; ti < text.length && qi < lowerQuery.length; ti++) {
    if (lowerText[ti] === lowerQuery[qi]) {
      matched[ti] = true;
      qi++;
    }
  }
  if (qi < lowerQuery.length) return [{ text, match: false }];

  const segments: HighlightSegment[] = [];
  let buffer = "";
  let bufferMatch = matched[0];
  for (let i = 0; i < text.length; i++) {
    if (matched[i] === bufferMatch) {
      buffer += text[i];
    } else {
      segments.push({ text: buffer, match: bufferMatch });
      buffer = text[i];
      bufferMatch = matched[i];
    }
  }
  if (buffer) segments.push({ text: buffer, match: bufferMatch });
  return segments;
}
