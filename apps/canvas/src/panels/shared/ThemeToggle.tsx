import { useState } from "react";
import { Moon, Sun } from "lucide-react";
import { currentTheme, setTheme, type ThemeName } from "../../lib/theme";

/**
 * Header theme toggle (boards 1c/1d): 32px bordered square, moon in light
 * mode / sun in dark mode. Sets data-theme on <html> and persists the choice.
 */
export function ThemeToggle() {
  const [theme, setThemeState] = useState<ThemeName>(() => currentTheme());
  const next: ThemeName = theme === "dark" ? "light" : "dark";

  return (
    <button
      type="button"
      className="theme-toggle"
      aria-label={`Switch to ${next} theme`}
      title={`Switch to ${next} theme`}
      onClick={() => {
        setTheme(next);
        setThemeState(next);
      }}
    >
      {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
    </button>
  );
}
