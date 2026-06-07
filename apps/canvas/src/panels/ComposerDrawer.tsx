import { useMemo, useState } from "react";
import {
  getTemplateSpec,
  list_catalog,
  list_templates,
  validate_spec,
} from "../composer";
import type { ViewSpec } from "../view/types";
import { persistViewSpec } from "../view/persistViewSpec";

type ComposerDrawerProps = {
  open: boolean;
  onClose: () => void;
  initialSpec: ViewSpec;
};

export function ComposerDrawer({ open, onClose, initialSpec }: ComposerDrawerProps) {
  const [draft, setDraft] = useState<ViewSpec>(initialSpec);
  const [templateId, setTemplateId] = useState(initialSpec.view_id);
  const catalog = useMemo(() => list_catalog(), []);
  const templates = useMemo(() => list_templates(), []);
  const validation = useMemo(() => validate_spec({ spec: draft, strict: true }), [draft]);

  if (!open) return null;

  function loadTemplate(viewId: string) {
    const spec = getTemplateSpec(viewId);
    if (spec) {
      setDraft(structuredClone(spec));
      setTemplateId(viewId);
    }
  }

  function downloadJson() {
    const blob = new Blob([JSON.stringify(draft, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${draft.view_id}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <aside className="composer-drawer" aria-label="view composer" data-testid="composer-drawer">
      <header>
        <h2>View Composer</h2>
        <button type="button" onClick={onClose} aria-label="Close composer">
          ×
        </button>
      </header>
      <p className="composer-meta">
        Layout metadata only — <code>{draft.source_kind}</code> · {catalog.count} component kinds
      </p>
      <label>
        Template
        <select
          value={templateId}
          onChange={(event) => loadTemplate(event.target.value)}
          data-testid="composer-template-select"
        >
          {templates.templates.map((t) => (
            <option key={t.view_id} value={t.view_id}>
              {t.title}
            </option>
          ))}
        </select>
      </label>
      <label>
        Run group (metadata)
        <input
          value={draft.run_group}
          onChange={(event) => setDraft({ ...draft, run_group: event.target.value })}
        />
      </label>
      {(validation.errors.length > 0 || validation.warnings.length > 0) && (
        <ul className="composer-issues" role="alert">
          {[...validation.errors, ...validation.warnings].map((issue) => (
            <li key={`${issue.code}-${issue.path}`}>{issue.message}</li>
          ))}
        </ul>
      )}
      <div className="composer-actions">
        <button
          type="button"
          disabled={!validation.ok}
          onClick={() => {
            persistViewSpec(draft);
            onClose();
            window.location.reload();
          }}
          data-testid="composer-persist-local"
        >
          Persist locally
        </button>
        <button type="button" disabled={!validation.ok} onClick={downloadJson}>
          Export JSON
        </button>
      </div>
    </aside>
  );
}
