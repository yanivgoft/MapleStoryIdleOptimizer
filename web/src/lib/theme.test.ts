import { describe, expect, it } from "vitest";
import { applyTheme, isThemeMode, nextTheme, parseTheme, readTheme, THEME_KEY, THEME_ORDER, themeButtonText, writeTheme, type ThemeRoot } from "./theme";

function memoryStorage(initial: Record<string, string> = {}) {
  const data = new Map(Object.entries(initial));
  return {
    data,
    getItem: (k: string) => data.get(k) ?? null,
    setItem: (k: string, v: string) => void data.set(k, v),
    removeItem: (k: string) => void data.delete(k),
  };
}
const blocked = {
  getItem: () => {
    throw new Error("SecurityError");
  },
  setItem: () => {
    throw new Error("QuotaExceededError");
  },
  removeItem: () => {
    throw new Error("SecurityError");
  },
};
function fakeRoot() {
  const attrs = new Map<string, string>();
  const root: ThemeRoot & { attrs: Map<string, string> } = {
    attrs,
    setAttribute: (n, v) => void attrs.set(n, v),
    removeAttribute: (n) => void attrs.delete(n),
    style: { colorScheme: "" },
  };
  return root;
}

describe("theme cycle", () => {
  it("goes Auto -> Light -> Dark -> Auto", () => {
    expect(THEME_ORDER).toEqual(["auto", "light", "dark"]);
    expect(nextTheme("auto")).toBe("light");
    expect(nextTheme("light")).toBe("dark");
    expect(nextTheme("dark")).toBe("auto");
  });
  it("button text names the current mode and what a click does", () => {
    expect(themeButtonText("auto").title).toBe("Theme: Auto (follows your system). Click to switch to Light.");
    expect(themeButtonText("light").title).toContain("Click to switch to Dark");
    expect(themeButtonText("dark").label).toContain("Theme: Dark.");
    expect(themeButtonText("dark").label).toContain("switch to Auto");
  });
});

describe("theme persistence", () => {
  it("parses only the three modes; everything else is Auto", () => {
    for (const m of THEME_ORDER) expect(parseTheme(m)).toBe(m);
    for (const bad of [null, undefined, "", "Dark", "sepia", 1, {}]) expect(parseTheme(bad), String(bad)).toBe("auto");
    expect(isThemeMode("light")).toBe(true);
    expect(isThemeMode("system")).toBe(false);
  });
  it("round-trips light / dark; Auto removes the key", () => {
    const st = memoryStorage();
    expect(readTheme(st)).toBe("auto");
    expect(writeTheme("dark", st)).toBe(true);
    expect(st.data.get(THEME_KEY)).toBe("dark");
    expect(readTheme(st)).toBe("dark");
    writeTheme("light", st);
    expect(readTheme(st)).toBe("light");
    writeTheme("auto", st);
    expect(st.data.has(THEME_KEY)).toBe(false);
    expect(readTheme(st)).toBe("auto");
  });
  it("an invalid stored value reads as Auto", () => {
    expect(readTheme(memoryStorage({ [THEME_KEY]: "purple" }))).toBe("auto");
    expect(readTheme(memoryStorage({ [THEME_KEY]: "" }))).toBe("auto");
  });
  it("blocked or missing storage never throws", () => {
    expect(readTheme(blocked)).toBe("auto");
    expect(writeTheme("dark", blocked)).toBe(false);
    expect(readTheme(null)).toBe("auto");
    expect(writeTheme("dark", null)).toBe(false);
  });
});

describe("applyTheme", () => {
  it("sets data-theme and color-scheme for forced modes and removes them for Auto", () => {
    const root = fakeRoot();
    applyTheme("dark", root);
    expect(root.attrs.get("data-theme")).toBe("dark");
    expect(root.style.colorScheme).toBe("dark");
    applyTheme("light", root);
    expect(root.attrs.get("data-theme")).toBe("light");
    expect(root.style.colorScheme).toBe("light");
    applyTheme("auto", root);
    expect(root.attrs.has("data-theme")).toBe(false);
    expect(root.style.colorScheme).toBe("");
  });
  it("does nothing without a document", () => {
    expect(() => applyTheme("dark", null)).not.toThrow();
  });
});
