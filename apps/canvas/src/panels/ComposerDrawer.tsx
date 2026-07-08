import { useMemo, useState } from "react";
import {
  AlertTriangle,
  Check,
  Download,
  GripVertical,
  Pencil,
  Plus,
  Save,
  X,
} from "lucide-react";
import {
  COMPONENT_CATALOG,
  getTemplateSpec,
  preview_spec,
  validate_spec,
} from "../composer";
import {
  addableCatalog,
  effectiveComponents,
  newPanelInstance,
  togglePanelSet,
} from "../composer/effectiveSpec";
import { TEMPLATE_REFS } from "../composer/templates";
import type { ComponentInstance, ComponentKind, ViewSpec } from "../view/types";
import { persistViewSpec } from "../view/persistViewSpec";
import { useRunGroups } from "./RunGroupSelector";

type ComposerDrawerProps = {
  open: boolean;
  onClose: () => void;
  initialSpec: ViewSpec;
};

/** Dedup the registry defensively — templates.ts is the single source. */
const TEMPLATE_OPTIONS = TEMPLATE_REFS.filter(
  (ref, index) => TEMPLATE_REFS.findIndex((other) => other.view_id === ref.view_id) === index,
);

/** Short mono descriptor for a component row (kind · region · testid). */
function panelDescriptor(component: ComponentInstance): string {
  const testid = component.data_testid ?? component.component_kind;
  return `${component.region} · ${testid}`;
}

function humanKind(kind: ComponentKind): string {
  return kind.replace(/_/g, " ");
}

export function ComposerDrawer({ open, onClose, initialSpec }: ComposerDrawerProps) {
  const [draft, setDraft] = useState<ViewSpec>(initialSpec);
  const [templateId, setTemplateId] = useState(initialSpec.view_id);
  // Instance ids toggled OFF. Kept as a denylist (not by mutating components)
  // so panel ORDER is preserved when a panel is toggled back on.
  const [disabled, setDisabled] = useState<Set<string>>(() => new Set());
  const [addKind, setAddKind] = useState("");
  const runGroups = useRunGroups();

  // The spec as composed = the draft minus toggled-off panels. Everything
  // downstream (validation, live preview, persist, export) reads THIS, so the
  // preview and validation reflect the REAL composed spec — never a mock.
  const effectiveSpec = useMemo<ViewSpec>(
    () => ({ ...draft, components: effectiveComponents(draft.components, disabled) }),
    [draft, disabled],
  );

  const validation = useMemo(
    () => validate_spec({ spec: effectiveSpec, strict: false }),
    [effectiveSpec],
  );

  const preview = useMemo(
    () => preview_spec({ spec: effectiveSpec, mode: "graph", selected_node: true }),
    [effectiveSpec],
  );

  const previewKinds = useMemo(() => {
    const byId = new Map(effectiveSpec.components.map((c) => [c.instance_id, c.component_kind]));
    const kinds = new Set<ComponentKind>();
    for (const id of preview.render_plan.visible_components) {
      const kind = byId.get(id);
      if (kind) kinds.add(kind);
    }
    return kinds;
  }, [preview, effectiveSpec]);

  const regions = preview.render_plan.regions;
  const previewBlocks = {
    notice: (regions.notice?.length ?? 0) > 0,
    header: (regions.header?.length ?? 0) > 0,
    graph: previewKinds.has("action_graph_canvas"),
    legend: previewKinds.has("truth_legend"),
    rail: (regions.rail?.length ?? 0) > 0,
    operator: (regions.operator?.length ?? 0) > 0,
  };

  const activeCount = effectiveSpec.components.length;

  const addableKinds = useMemo(
    () => addableCatalog(draft.components, COMPONENT_CATALOG),
    [draft.components],
  );

  if (!open) return null;

  function loadTemplate(viewId: string) {
    const spec = getTemplateSpec(viewId);
    if (spec) {
      setDraft(structuredClone(spec));
      setTemplateId(viewId);
      setDisabled(new Set());
      setAddKind("");
    }
  }

  function togglePanel(instanceId: string) {
    setDisabled((prev) => togglePanelSet(prev, instanceId));
  }

  function addPanel(kind: string) {
    const entry = COMPONENT_CATALOG.find((c) => c.kind === kind);
    if (!entry) return;
    const component = newPanelInstance(entry, Date.now().toString(36));
    setDraft((prev) => ({ ...prev, components: [...prev.components, component] }));
    setAddKind("");
  }

  function downloadJson() {
    const blob = new Blob([JSON.stringify(effectiveSpec, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${effectiveSpec.view_id}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <aside className="composer-drawer" aria-label="view composer" data-testid="composer-drawer">
      <header className="composer-head">
        <span className="composer-head-title">
          <Pencil size={15} aria-hidden="true" />
          Composer
        </span>
        <button
          type="button"
          className="composer-close"
          onClick={onClose}
          aria-label="Close composer"
        >
          <X size={16} />
        </button>
      </header>

      <div className="composer-scroll">
        {/* 1 — View template (real registry) */}
        <section className="composer-section" aria-label="view template">
          <p className="composer-overline">View template</p>
          <div className="composer-listbox" role="listbox" data-testid="composer-template-select">
            {TEMPLATE_OPTIONS.map((template) => {
              const selected = template.view_id === templateId;
              return (
                <button
                  type="button"
                  key={template.view_id}
                  role="option"
                  aria-selected={selected}
                  className={`composer-template-row${selected ? " composer-template-row--selected" : ""}`}
                  data-testid="composer-template-option"
                  data-selected={selected}
                  onClick={() => loadTemplate(template.view_id)}
                >
                  <span className={`composer-radio${selected ? " composer-radio--on" : ""}`} aria-hidden="true" />
                  <span className="composer-template-copy">
                    <span className="composer-template-name">{template.title}</span>
                    <span className="composer-template-desc">{template.description}</span>
                  </span>
                </button>
              );
            })}
          </div>
        </section>

        {/* 2 — Run group (real index/history/compare fallback) */}
        <section className="composer-section" aria-label="run group">
          <p className="composer-overline">Run group</p>
          <div className="composer-pills" data-testid="composer-run-groups">
            {runGroups.loading && <span className="composer-pill-note">Loading run group index…</span>}
            {!runGroups.loading && runGroups.groups.length === 0 && (
              <span className="composer-pill-note">
                {runGroups.error ?? "No indexed run groups — projection JSON only."}
              </span>
            )}
            {runGroups.groups.map((group) => {
              const active = group.run_group === draft.run_group;
              return (
                <button
                  type="button"
                  key={group.run_group}
                  className={`composer-pill${active ? " composer-pill--active" : ""}`}
                  data-testid="composer-run-group-pill"
                  data-active={active}
                  aria-pressed={active}
                  onClick={() => setDraft((prev) => ({ ...prev, run_group: group.run_group }))}
                >
                  <span className="composer-pill-dot" aria-hidden="true" />
                  <span className="composer-pill-name">{group.run_group}</span>
                  {group.run_count != null && (
                    <span className="composer-pill-count">
                      {group.run_count} run{group.run_count === 1 ? "" : "s"}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
          {runGroups.helper && <p className="composer-pill-source">{runGroups.helper}</p>}
        </section>

        {/* 3 — Panels + toggles (real view-spec components) */}
        <section className="composer-section" aria-label="panels">
          <div className="composer-section-head">
            <p className="composer-overline">Panels · {activeCount}</p>
            {addableKinds.length > 0 && (
              <label className="composer-add">
                <Plus size={13} aria-hidden="true" />
                <span>add panel</span>
                <select
                  value={addKind}
                  data-testid="composer-add-panel"
                  onChange={(event) => {
                    const kind = event.target.value;
                    setAddKind(kind);
                    if (kind) addPanel(kind);
                  }}
                >
                  <option value="">add panel…</option>
                  {addableKinds.map((entry) => (
                    <option key={entry.kind} value={entry.kind}>
                      {humanKind(entry.kind)}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </div>
          <ul className="composer-panels">
            {draft.components.map((component) => {
              const on = !disabled.has(component.instance_id);
              return (
                <li
                  key={component.instance_id}
                  className={`composer-panel-row${on ? "" : " composer-panel-row--off"}`}
                >
                  <GripVertical size={13} className="composer-grip" aria-hidden="true" />
                  <span className="composer-panel-copy">
                    <span className="composer-panel-name">{humanKind(component.component_kind)}</span>
                    <span className="composer-panel-desc">{panelDescriptor(component)}</span>
                  </span>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={on}
                    aria-label={`${humanKind(component.component_kind)} panel`}
                    className={`composer-toggle${on ? " composer-toggle--on" : ""}`}
                    data-testid="composer-panel-toggle"
                    data-on={on}
                    onClick={() => togglePanel(component.instance_id)}
                  >
                    <span className="composer-toggle-knob" aria-hidden="true" />
                  </button>
                </li>
              );
            })}
          </ul>
        </section>

        {/* 4 — Validation (live, real validate_spec) */}
        <section className="composer-section" aria-label="validation" data-testid="composer-validation">
          <p className="composer-overline">Validation</p>
          {validation.warnings.length > 0 && (
            <div className="composer-validation-warn" role="status">
              <AlertTriangle size={14} aria-hidden="true" />
              <ul>
                {validation.warnings.map((issue) => (
                  <li key={`${issue.code}-${issue.path}`}>{issue.message}</li>
                ))}
              </ul>
            </div>
          )}
          {validation.errors.length > 0 ? (
            <div className="composer-validation-error" role="alert">
              <AlertTriangle size={14} aria-hidden="true" />
              <ul>
                {validation.errors.map((issue) => (
                  <li key={`${issue.code}-${issue.path}`}>
                    <code>{issue.path}</code> {issue.message}
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="composer-validation-ok" data-testid="composer-validation-ok">
              <Check size={14} aria-hidden="true" />
              spec valid · {activeCount} panel{activeCount === 1 ? "" : "s"} · 0 errors
            </p>
          )}
        </section>

        {/* 5 — Live preview (wired via preview.ts / the real view-spec engine) */}
        <section className="composer-section" aria-label="live preview">
          <p className="composer-overline">Live preview</p>
          <div className="composer-preview" data-testid="composer-live-preview">
            <div className="composer-wire" aria-hidden="true">
              {previewBlocks.notice && <span className="wire-notice" />}
              {previewBlocks.header && <span className="wire-header" />}
              <div className="wire-body">
                <div className="wire-main">
                  {previewBlocks.graph ? (
                    <div className="wire-nodes">
                      {Array.from({ length: 6 }).map((_, i) => (
                        <span key={i} className="wire-node" />
                      ))}
                    </div>
                  ) : (
                    <span className="wire-empty" />
                  )}
                  {previewBlocks.legend && <span className="wire-legend" />}
                </div>
                {previewBlocks.rail && <div className="wire-rail" />}
              </div>
              {previewBlocks.operator && <span className="wire-operator" />}
            </div>
            <p className="composer-preview-caption">
              updates as you edit · {preview.render_plan.visible_components.length} components visible
            </p>
          </div>
        </section>
      </div>

      {/* 6 — Footer: persist / export + non-evidentiary caption */}
      <footer className="composer-footer">
        <div className="composer-footer-actions">
          <button
            type="button"
            className="composer-btn composer-btn--primary"
            disabled={!validation.ok}
            onClick={() => {
              persistViewSpec(effectiveSpec);
              onClose();
              window.location.reload();
            }}
            data-testid="composer-persist-local"
          >
            <Save size={13} aria-hidden="true" />
            Persist locally
          </button>
          <button
            type="button"
            className="composer-btn composer-btn--bordered"
            disabled={!validation.ok}
            onClick={downloadJson}
            data-testid="composer-export"
          >
            <Download size={13} aria-hidden="true" />
            Export JSON
          </button>
        </div>
        <p className="composer-footer-caption">view spec is URL-encoded · never evidence</p>
      </footer>
    </aside>
  );
}
