// WCAG contrast of the palette in styles.css, both themes: text >= 4.5:1, control borders >= 3:1.
import { describe, expect, it } from "vitest";

// @ts-ignore node:fs has no type declarations unless @types/node is installed (it arrives transitively with firebase)
const fs = (await import("node:fs")) as { readFileSync(u: URL, enc: string): string };
const css = fs.readFileSync(new URL("../styles.css", import.meta.url), "utf8");

const vars: Record<string, { light: string; dark: string }> = {};
for (const m of css.matchAll(/--([a-z0-9-]+):\s*light-dark\(\s*(#[0-9a-fA-F]{6})\s*,\s*(#[0-9a-fA-F]{6})\s*\)/g)) vars[m[1]] = { light: m[2], dark: m[3] };

function lum(hex: string): number {
  const ch = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2];
}
export function ratio(a: string, b: string): number {
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

describe("WCAG ratio helper", () => {
  it("known values", () => {
    expect(ratio("#000000", "#ffffff")).toBeCloseTo(21, 5);
    expect(ratio("#777777", "#ffffff")).toBeCloseTo(4.48, 1);
    expect(ratio("#ffffff", "#ffffff")).toBeCloseTo(1, 5);
  });
});

describe("palette contrast", () => {
  const themes = ["light", "dark"] as const;
  const textVars = ["ink", "ink2", "muted", "accent", "danger", "ok", "bar-alt"];
  it("the variables are all there", () => {
    for (const v of ["bg", "surface", ...textVars, "control-border", "line"]) expect(vars[v], v).toBeDefined();
  });
  it.each(themes)("%s: text colours reach 4.5:1 on the page and on cards", (theme) => {
    for (const v of textVars) for (const bg of ["bg", "surface"]) {
      expect(ratio(vars[v][theme], vars[bg][theme]), `${theme}: ${v} on ${bg}`).toBeGreaterThanOrEqual(4.5);
    }
  });
  it.each(themes)("%s: accent-ink on the accent fill (the primary button) reaches 4.5:1", (theme) => {
    expect(ratio(vars["accent-ink"][theme], vars["accent"][theme])).toBeGreaterThanOrEqual(4.5);
  });
  it.each(themes)("%s: control borders reach 3:1 against the page and the card", (theme) => {
    for (const bg of ["bg", "surface"]) expect(ratio(vars["control-border"][theme], vars[bg][theme]), `${theme}: control-border on ${bg}`).toBeGreaterThanOrEqual(3);
  });
  it.each(themes)("%s: bars (graphics) reach 3:1", (theme) => {
    for (const v of ["bar", "bar-alt"]) expect(ratio(vars[v][theme], vars["surface"][theme]), `${theme}: ${v}`).toBeGreaterThanOrEqual(3);
  });
  it("the no-light-dark() fallback block repeats the light values", () => {
    const fb = /@supports not[\s\S]*?\n\}\n/.exec(css)![0];
    for (const v of ["muted", "bar-alt", "control-border"]) expect(fb.toLowerCase(), v).toContain(`--${v}: ${vars[v].light.toLowerCase()}`);
  });
  it("controls draw their border from --control-border, not the decorative --line", () => {
    expect(css).toMatch(/input\[type="text"\], select \{[^}]*border: 1px solid var\(--control-border\)/);
    expect(css).toMatch(/\nbutton \{[^}]*border: 1px solid var\(--control-border\)/);
  });
});

describe("accessibility rules of styles.css", () => {
  it("the tab chip has its own class (a bare .soon rule leaked into the class picker's .status-item.soon)", () => {
    expect(css).not.toMatch(/(^|\n)\.soon\s*\{/);
    expect(css).toMatch(/\.tab-soon\s*\{/);
  });
  it("reduced motion switches animations / transitions / smooth scrolling off", () => {
    expect(css).toMatch(/@media \(prefers-reduced-motion: reduce\)[\s\S]*transition-duration/);
  });
  it("touch screens get 44px targets", () => {
    expect(css).toMatch(/@media \(pointer: coarse\)[\s\S]*min-height: 44px/);
  });
  it("the sticky results column cannot outgrow the screen", () => {
    expect(css).toMatch(/\.col-results \{[^}]*max-height: calc\(100vh[^}]*overflow-y: auto/);
  });
});
