import { useEffect, useMemo, useState } from "react";
import type { CompareProjection, Confidence, RedactionState, SourceKind } from "../types";

const INDEX_PATH = "/projections/compare-index.json";
const COMPARE_PATH = "/projections/compare-projection.json";

export type RunGroupIndexEntry = {
  run_group: string;
  run_count?: number;
  first_started_at?: string | null;
  last_started_at?: string | null;
  source_kind: SourceKind;
  confidence: Confidence;
  evidence_refs: string[];
  redaction_state: RedactionState;
};

export type RunGroupIndex = {
  schema_version: 1;
  kind: "run_group_index";
  source_kind: SourceKind;
  confidence: Confidence;
  evidence_refs: string[];
  redaction_state: RedactionState;
  run_groups: RunGroupIndexEntry[];
  count: number;
};

type RunGroupSelectorProps = {
  value: string;
  onChange: (runGroup: string) => void;
};

function derivedEntry(runGroup: string, runCount?: number): RunGroupIndexEntry {
  return {
    run_group: runGroup,
    run_count: runCount,
    source_kind: "derived_v1",
    confidence: "medium",
    evidence_refs: [`run_group:${runGroup}`],
    redaction_state: "safe",
  };
}

function parseCompareProjection(payload: CompareProjection): RunGroupIndexEntry[] {
  const groups = new Map<string, RunGroupIndexEntry>();
  const add = (name: string | undefined, runCount?: number) => {
    if (!name || groups.has(name)) return;
    groups.set(name, derivedEntry(name, runCount));
  };

  add(payload.left_run_group, payload.summary?.left_runs as number | undefined);
  add(payload.right_run_group, payload.summary?.right_runs as number | undefined);

  for (const ref of payload.evidence_refs ?? []) {
    if (ref.startsWith("run_group:")) {
      add(ref.slice("run_group:".length));
    }
  }

  for (const dimension of payload.dimensions ?? []) {
    const left = dimension.left?.run_group;
    const right = dimension.right?.run_group;
    if (typeof left === "string") add(left, dimension.left?.runs as number | undefined);
    if (typeof right === "string") add(right, dimension.right?.runs as number | undefined);
  }

  return [...groups.values()].sort((a, b) => a.run_group.localeCompare(b.run_group));
}

function isRunGroupIndex(value: unknown): value is RunGroupIndex {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const candidate = value as RunGroupIndex;
  return (
    candidate.kind === "run_group_index" &&
    Array.isArray(candidate.run_groups) &&
    candidate.run_groups.every((item) => typeof item.run_group === "string")
  );
}

async function loadRunGroupIndex(): Promise<RunGroupIndexEntry[]> {
  try {
    const response = await fetch(INDEX_PATH);
    if (response.ok) {
      const payload: unknown = await response.json();
      if (isRunGroupIndex(payload)) {
        return payload.run_groups;
      }
    }
  } catch {
    // Fall through to compare projection parse.
  }

  const response = await fetch(COMPARE_PATH);
  if (!response.ok) {
    throw new Error("Run group index unavailable — compare-index.json and compare-projection.json missing.");
  }
  const payload = (await response.json()) as CompareProjection;
  return parseCompareProjection(payload);
}

export function RunGroupSelector({ value, onChange }: RunGroupSelectorProps) {
  const [groups, setGroups] = useState<RunGroupIndexEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [source, setSource] = useState<"index" | "compare" | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    void (async () => {
      try {
        const indexResponse = await fetch(INDEX_PATH);
        if (!cancelled && indexResponse.ok) {
          const payload: unknown = await indexResponse.json();
          if (isRunGroupIndex(payload)) {
            setGroups(payload.run_groups);
            setSource("index");
            setLoading(false);
            return;
          }
        }

        const compareResponse = await fetch(COMPARE_PATH);
        if (!compareResponse.ok) {
          throw new Error("Run group index unavailable — projection JSON not loaded.");
        }
        const comparePayload = (await compareResponse.json()) as CompareProjection;
        if (!cancelled) {
          setGroups(parseCompareProjection(comparePayload));
          setSource("compare");
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load run groups");
          setGroups([]);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  const options = useMemo(() => {
    const names = new Set(groups.map((item) => item.run_group));
    if (value && !names.has(value)) {
      return [derivedEntry(value), ...groups];
    }
    return groups;
  }, [groups, value]);

  const helper =
    source === "index"
      ? "Loaded from compare-index.json (derived_v1)."
      : source === "compare"
        ? "Derived from compare-projection.json run_group fields (derived_v1)."
        : null;

  return (
    <label>
      Run group
      <select
        value={value}
        disabled={loading || options.length === 0}
        onChange={(event) => onChange(event.target.value)}
        data-testid="run-group-selector"
        aria-busy={loading}
      >
        {options.length === 0 ? (
          <option value={value}>{value || "No indexed run groups"}</option>
        ) : (
          options.map((item) => (
            <option key={item.run_group} value={item.run_group}>
              {item.run_count != null
                ? `${item.run_group} (${item.run_count} run${item.run_count === 1 ? "" : "s"})`
                : item.run_group}
            </option>
          ))
        )}
      </select>
      <span className="run-group-selector-meta" data-source-kind="derived_v1">
        {loading ? "Loading run group index…" : error ?? helper ?? "Projection JSON only."}
      </span>
    </label>
  );
}

export { loadRunGroupIndex, parseCompareProjection };
