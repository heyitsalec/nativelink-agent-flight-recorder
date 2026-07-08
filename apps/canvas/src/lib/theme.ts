/**
 * Theme plumbing for the canvas (redesign P1).
 *
 * The token system in styles.css keys off `document.documentElement.dataset.theme`
 * ("light" | "dark"). The operator's explicit choice persists in localStorage
 * under `nlfr.theme`; when unset we follow `prefers-color-scheme` (and keep
 * following it live until the operator picks a theme). A CSS-only
 * `@media (prefers-color-scheme: dark)` fallback in styles.css covers the
 * pre-hydration frame, so there is no light-theme flash for dark-mode users.
 *
 * Theme is operator UI state only — it is never serialized into any
 * projection, export, or evidence surface.
 */

export type ThemeName = "light" | "dark";

export const THEME_STORAGE_KEY = "nlfr.theme";

export function storedTheme(): ThemeName | null {
  try {
    const value = window.localStorage.getItem(THEME_STORAGE_KEY);
    return value === "light" || value === "dark" ? value : null;
  } catch {
    return null; // storage unavailable (privacy mode) — fall back to system
  }
}

export function systemTheme(): ThemeName {
  if (typeof window.matchMedia !== "function") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function currentTheme(): ThemeName {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

export function applyTheme(theme: ThemeName): void {
  document.documentElement.dataset.theme = theme;
}

/** Persist the operator's explicit choice and apply it. */
export function setTheme(theme: ThemeName): void {
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    // storage unavailable — the choice still applies for this session
  }
  applyTheme(theme);
}

/**
 * Stamp the resolved theme before first render, and track system preference
 * changes for as long as the operator has not made an explicit choice.
 */
export function initTheme(): void {
  applyTheme(storedTheme() ?? systemTheme());
  if (typeof window.matchMedia !== "function") return;
  const query = window.matchMedia("(prefers-color-scheme: dark)");
  const followSystem = () => {
    if (storedTheme() === null) applyTheme(systemTheme());
  };
  if (typeof query.addEventListener === "function") {
    query.addEventListener("change", followSystem);
  }
}
