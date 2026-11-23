import { describe, expect, it } from "vitest";
import { renderToString } from "react-dom/server";
import { ThemeToggle, ThemeToggleView } from "./ThemeToggle";

const strip = (h: string) => h.replace(/<!-- -->/g, "");

describe("ThemeToggle render", () => {
  it.each([
    ["auto", "Theme: Auto (follows your system). Click to switch to Light.", "auto"],
    ["light", "Theme: Light. Click to switch to Dark.", "sun"],
    ["dark", "Theme: Dark. Click to switch to Auto (follows your system).", "moon"],
  ] as const)("%s: label, title and icon", (mode, text, icon) => {
    const html = strip(renderToString(<ThemeToggleView mode={mode} onClick={() => undefined} />));
    expect(html).toContain(`aria-label="${text}"`);
    expect(html).toContain(`title="${text}"`);
    expect(html).toContain(`data-icon="${icon}"`);
    expect(html).toContain('type="button"');
    expect(html).toContain("<button");
  });
  it("the container starts in Auto when storage is unavailable (server render)", () => {
    expect(renderToString(<ThemeToggle />)).toContain('data-mode="auto"');
  });
});

// no @types/node in this project and vitest does not serve css as ?raw: read the files with node:fs through file URLs
// @ts-ignore node:fs has no type declarations unless @types/node is installed (it arrives transitively with firebase)
const fs = (await import("node:fs")) as { readFileSync(u: URL, enc: string): string; readdirSync(u: URL): string[] };
const read = (rel: string) => fs.readFileSync(new URL(rel, import.meta.url), "utf8");
const cssFiles: Record<string, string> = Object.fromEntries([
  ["../styles.css", read("../styles.css")],
  ...fs.readdirSync(new URL("./", import.meta.url)).filter((f) => f.endsWith(".css")).map((f) => [`./${f}`, read(`./${f}`)]),
]);
const stylesCss = cssFiles["../styles.css"];
const indexHtml = read("../../index.html");

describe("palette hygiene", () => {
  const colour = /#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(/;
  it("no hard-coded colour outside the palette block of styles.css", () => {
    expect(Object.keys(cssFiles).length).toBeGreaterThan(3); // styles.css + the component sheets
    for (const [f, text] of Object.entries(cssFiles)) {
      const css = f === "../styles.css" ? text.replace(/\/\* Palette[\s\S]*?(?=\* \{ box-sizing)/, "") : text; // palette block = variables + the no-light-dark fallback
      expect(css, f).not.toMatch(colour);
    }
  });
  it("the palette block really is stripped (guards the test itself)", () => {
    expect(stylesCss).toMatch(colour);
  });
  it("index.html applies the saved theme before first paint with the same storage key", () => {
    expect(indexHtml).toContain('localStorage.getItem("msi.theme")');
    expect(indexHtml.indexOf("msi.theme")).toBeLessThan(indexHtml.indexOf("<title>"));
  });
  it("styles.css defines the forced themes", () => {
    expect(stylesCss).toContain(':root[data-theme="dark"] { color-scheme: dark; }');
    expect(stylesCss).toContain(':root[data-theme="light"] { color-scheme: light; }');
  });
});
