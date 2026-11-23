import { useEffect, useState } from "react";
import { applyTheme, nextTheme, readTheme, themeButtonText, writeTheme, type ThemeMode } from "../lib/theme";

const SVG = { width: 18, height: 18, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": true, focusable: false } as const;

/** Icon of the CURRENT mode: monitor (Auto), sun (Light), moon (Dark). */
export function ThemeIcon({ mode }: { mode: ThemeMode }) {
  if (mode === "light")
    return (
      <svg {...SVG} data-icon="sun">
        <circle cx="12" cy="12" r="4" />
        <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
      </svg>
    );
  if (mode === "dark")
    return (
      <svg {...SVG} data-icon="moon">
        <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
      </svg>
    );
  return (
    <svg {...SVG} data-icon="auto">
      <rect x="3" y="4" width="18" height="12" rx="2" />
      <path d="M8 20h8M12 16v4" />
      <path d="M12 7a3 3 0 0 0 0 6z" fill="currentColor" />
    </svg>
  );
}

/** Presentational button: label / tooltip say the current mode and what a click does. */
export function ThemeToggleView({ mode, onClick }: { mode: ThemeMode; onClick: () => void }) {
  const { label, title } = themeButtonText(mode);
  return (
    <button type="button" className="theme-toggle" data-mode={mode} aria-label={label} title={title} onClick={onClick}>
      <ThemeIcon mode={mode} />
      <span className="theme-toggle-text" aria-hidden="true">
        {mode === "auto" ? "Auto" : mode === "light" ? "Light" : "Dark"}
      </span>
    </button>
  );
}

/** Header button cycling Auto -> Light -> Dark; the choice is stored in localStorage and applied to <html> (index.html applies it before first paint). */
export function ThemeToggle() {
  const [mode, setMode] = useState<ThemeMode>(() => readTheme());
  useEffect(() => applyTheme(mode), [mode]);
  // the optional account feature can change the stored theme (settings synced from the account): follow it
  useEffect(() => {
    const onChange = () => setMode(readTheme());
    window.addEventListener("msi-theme-change", onChange);
    return () => window.removeEventListener("msi-theme-change", onChange);
  }, []);
  return (
    <ThemeToggleView
      mode={mode}
      onClick={() => {
        const next = nextTheme(mode);
        writeTheme(next);
        setMode(next);
      }}
    />
  );
}
