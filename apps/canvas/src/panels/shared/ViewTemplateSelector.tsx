import { Pencil } from "lucide-react";
import { TEMPLATE_REFS } from "../../composer/templates";
import { useViewContext } from "../../view/ViewContext";

const VIEW_OPTIONS = TEMPLATE_REFS.filter(
  (ref, index) => TEMPLATE_REFS.findIndex((other) => other.view_id === ref.view_id) === index,
);

export function ViewTemplateSelector() {
  const { overlay, overlayActions } = useViewContext();
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
              {option.title}
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
