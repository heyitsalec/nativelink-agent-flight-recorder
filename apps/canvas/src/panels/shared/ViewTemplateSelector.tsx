import { TEMPLATE_REFS } from "../../composer/templates";

const VIEW_OPTIONS = [
  ...TEMPLATE_REFS,
  {
    view_id: "tier1-demo",
    title: "Tier 1 Demo",
    description: "Compare lens + tier1 run groups",
  },
];

export function ViewTemplateSelector() {
  const current =
    typeof window !== "undefined"
      ? new URLSearchParams(window.location.search).get("view") ?? "nlfr-default-v0"
      : "nlfr-default-v0";

  return (
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
  );
}
