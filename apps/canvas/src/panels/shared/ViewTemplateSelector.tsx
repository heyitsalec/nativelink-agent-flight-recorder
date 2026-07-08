import { useEffect, useState } from "react";
import { Pencil } from "lucide-react";
import { TEMPLATE_REFS } from "../../composer/templates";
import { useViewContext } from "../../view/ViewContext";

const VIEW_OPTIONS = TEMPLATE_REFS.filter(
  (ref, index) => TEMPLATE_REFS.findIndex((other) => other.view_id === ref.view_id) === index,
);

/** Short picker labels for the ~52px mobile header (board 1m) so the option text
 *  fits the width-bounded picker without truncating into the native chevron
 *  (V1b fix). Desktop keeps the full `title`. Falls back to the full title for
 *  any unmapped view id. */
const SHORT_TITLES: Record<string, string> = {
  "nlfr-default-v0": "Default",
  "graph-only": "Graph",
  "proof-review": "Proof",
  "tier1-demo": "Tier 1",
  "two-act-spark": "Two-Act",
};

/** True at the mobile IA breakpoint (720 — the single mobile breakpoint used by
 *  the shell collapse, chip row, and bottom sheet). Initialised from matchMedia
 *  so desktop renders full titles on the very first paint (no flash) and the
 *  1440px truth-guard / capture runs are byte-identical to before. */
function useCompactPicker(): boolean {
  const [compact, setCompact] = useState(
    () => typeof window !== "undefined" && window.matchMedia("(max-width: 720px)").matches,
  );
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 720px)");
    const onChange = () => setCompact(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  return compact;
}

export function ViewTemplateSelector() {
  const { overlay, overlayActions } = useViewContext();
  const compact = useCompactPicker();
  const current =
    typeof window !== "undefined"
      ? new URLSearchParams(window.location.search).get("view") ?? "nlfr-default-v0"
      : "nlfr-default-v0";

  return (
    <div className="view-template-group">
      <label className="view-template-select" aria-label="View template">
        <span className="view-template-label">View</span>
        <select
          data-testid="view-template-selector"
          value={current}
          onChange={(event) => {
            const viewId = event.target.value;
            const url = new URL(window.location.href);
            if (viewId === "nlfr-default-v0") {
              url.searchParams.delete("view");
            } else {
              url.searchParams.set("view", viewId);
            }
            window.location.assign(url.toString());
          }}
        >
          {VIEW_OPTIONS.map((option) => (
            <option key={option.view_id} value={option.view_id}>
              {compact ? SHORT_TITLES[option.view_id] ?? option.title : option.title}
            </option>
          ))}
        </select>
      </label>
      <button
        type="button"
        className={`composer-open-button${overlay.composerOpen ? " composer-open-button--active" : ""}`}
        data-testid="composer-open-header"
        aria-pressed={overlay.composerOpen}
        onClick={() => overlayActions.openComposer()}
      >
        <Pencil size={13} aria-hidden="true" />
        <span>Composer</span>
      </button>
    </div>
  );
}
