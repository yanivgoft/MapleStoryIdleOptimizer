// Theme (Auto / Light / Dark) - pure logic.  The choice lives in localStorage (`msi.theme`) and on <html data-theme="light|dark"> (absent = Auto,
// i.e. follow the OS).  The same rules are inlined in index.html so the right theme is set before the first paint (keep THEME_KEY in sync there).

export type ThemeMode = "auto" | "light" | "dark";

export const THEME_KEY = "msi.theme";
/** One click on the header button moves to the next entry (wrapping). */
export const THEME_ORDER: readonly ThemeMode[] = ["auto", "light", "dark"];

export const THEME_NAMES: Record<ThemeMode, string> = { auto: "Auto (follows your system)", light: "Light", dark: "Dark" };

export function isThemeMode(v: unknown): v is ThemeMode {
  return v === "auto" || v === "light" || v === "dark";
}

/** Auto -> Light -> Dark -> Auto. */
export function nextTheme(mode: ThemeMode): ThemeMode {
  return THEME_ORDER[(THEME_ORDER.indexOf(mode) + 1) % THEME_ORDER.length];
}

/** Anything that is not one of the three modes (null, old / hand-edited values) reads as Auto. */
export function parseTheme(raw: unknown): ThemeMode {
  return isThemeMode(raw) ? raw : "auto";
}

type StorageLike = Pick<Storage, "getItem" | "setItem" | "removeItem">;

function defaultStorage(): StorageLike | null {
  try {
    return typeof localStorage === "undefined" ? null : localStorage; // reading the global itself can throw when storage is blocked
  } catch {
    return null;
  }
}

/** Stored choice; Auto when nothing / something invalid is stored or storage is blocked. */
export function readTheme(storage: StorageLike | null = defaultStorage()): ThemeMode {
  try {
    return parseTheme(storage?.getItem(THEME_KEY));
  } catch {
    return "auto";
  }
}

/** Persists the choice (Auto removes the key); returns false when storage is blocked (the choice then only lasts for this page view). */
export function writeTheme(mode: ThemeMode, storage: StorageLike | null = defaultStorage()): boolean {
  if (!storage) return false;
  try {
    if (mode === "auto") storage.removeItem(THEME_KEY);
    else storage.setItem(THEME_KEY, mode);
    return true;
  } catch {
    return false;
  }
}

/** The part of <html> the theme touches (an HTMLElement fits; tests pass a stub). */
export interface ThemeRoot {
  setAttribute(name: string, value: string): void;
  removeAttribute(name: string): void;
  style: { colorScheme: string };
}

/** `data-theme` is set for Light / Dark and removed for Auto; `color-scheme` follows (native controls, scrollbars), Auto goes back to "light dark". */
export function applyTheme(mode: ThemeMode, root: ThemeRoot | null = typeof document === "undefined" ? null : document.documentElement): void {
  if (!root) return;
  if (mode === "auto") {
    root.removeAttribute("data-theme");
    root.style.colorScheme = "";
  } else {
    root.setAttribute("data-theme", mode);
    root.style.colorScheme = mode;
  }
}

/** Label / tooltip of the header button: states the current mode and what a click does. */
export function themeButtonText(mode: ThemeMode): { label: string; title: string } {
  const next = nextTheme(mode);
  const title = `Theme: ${THEME_NAMES[mode]}. Click to switch to ${THEME_NAMES[next]}.`;
  return { label: title, title };
}
