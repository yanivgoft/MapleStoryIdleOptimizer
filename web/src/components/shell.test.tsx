// The app shell: tablist semantics, one <main>, the one collapsed explanation block of the Calculator tab, the page's meta tags, friendly server messages.
import { describe, expect, it } from "vitest";
import { renderToString } from "react-dom/server";
import App, { AboutNumbers } from "../App";
import { ApiError, UNREACHABLE_MESSAGE } from "../api";
import { friendlyError } from "../lib/liveRequest";
import { TABS } from "../lib/tabs";

const strip = (h: string) => h.replace(/<!-- -->/g, "");
// @ts-ignore node:fs has no type declarations unless @types/node is installed (it arrives transitively with firebase)
const fs = (await import("node:fs")) as { readFileSync(u: URL, enc: string): string; existsSync(u: URL): boolean };
const indexHtml = fs.readFileSync(new URL("../../index.html", import.meta.url), "utf8");

describe("tab bar markup", () => {
  const html = strip(renderToString(<App />));
  const tabs = [...html.matchAll(/<button[^>]*role="tab"[^>]*>/g)].map((m) => m[0]);
  it("a real tablist: 8 tabs in workflow order, exactly one in the tab order and selected", () => {
    expect(html).toContain('role="tablist"');
    expect(tabs).toHaveLength(8);
    const labels = [...html.matchAll(/<button[^>]*role="tab"[^>]*>(.*?)<\/button>/g)].map((m) => m[1].replace(/<[^>]+>/g, ""));
    expect(labels).toEqual(TABS.map((t) => t.label));
    expect(tabs.filter((t) => t.includes('tabindex="0"'))).toHaveLength(1);
    expect(tabs.filter((t) => t.includes('tabindex="-1"'))).toHaveLength(7);
    expect(tabs.filter((t) => t.includes('aria-selected="true"'))).toHaveLength(1);
    expect(tabs[0]).toContain('aria-selected="true"');
  });
  it("every tab controls a tabpanel that points back at it; only the selected panel is shown", () => {
    for (const t of tabs) {
      const id = /id="([^"]+)"/.exec(t)![1];
      const controls = /aria-controls="([^"]+)"/.exec(t)![1];
      const panel = new RegExp(`<div[^>]*role="tabpanel"[^>]*id="${controls}"[^>]*>`).exec(html)?.[0];
      expect(panel, controls).toBeDefined();
      expect(panel).toContain(`aria-labelledby="${id}"`);
      expect(panel!.includes("hidden")).toBe(!t.includes('aria-selected="true"'));
    }
  });
  it("one <main> around every panel", () => {
    expect((html.match(/<main/g) ?? []).length).toBe(1);
    expect(html.indexOf("<main")).toBeLessThan(html.indexOf('role="tabpanel"'));
    expect(html.lastIndexOf('role="tabpanel"')).toBeLessThan(html.indexOf("</main>"));
  });
});

describe("About these numbers", () => {
  const html = strip(renderToString(<AboutNumbers onOpenLimitations={() => undefined} />));
  it("is one collapsed block", () => {
    expect(html).toMatch(/^<details class="card about"><summary>About these numbers<\/summary>/);
    expect(html).not.toMatch(/<details[^>]* open/);
  });
  it("says what to type, that it is an estimate, the units, and links to the known limitations", () => {
    expect(html).toContain("preset page");
    expect(html).toMatch(/1-2%/);
    for (const u of ["K =", "M =", "B =", "T =", "Qa ="]) expect(html).toContain(u);
    expect(html).toContain("12.5M");
    expect(html).toContain("Known limitations");
  });
  it("is the only explanation block: nothing explanatory sits above the form or the results", () => {
    expect((strip(renderToString(<App />)).match(/class="card about"/g) ?? []).length).toBe(0);   // rendered only with a loaded class, at the bottom of the Calculator tab
  });
});

describe("server messages", () => {
  it("unreachable: friendly text without the dev address", () => {
    expect(UNREACHABLE_MESSAGE).toBe("Can't reach the calculator server.");
    const text = friendlyError(new ApiError(0, UNREACHABLE_MESSAGE), "calculation");
    expect(text).toMatch(/^Can't reach the calculator server\./);
    expect(text).not.toMatch(/localhost|https?:|VITE_|8000/i);
  });
  it("rate limit goes through the same helper as the cube tabs", () => {
    expect(friendlyError(new ApiError(429, "30 per minute"), "calculation")).toMatch(/Too many calculation requests/);
  });
});

describe("page head", () => {
  it("title, description, Open Graph, theme colours (light + dark) and a favicon that exists", () => {
    expect(indexHtml).toMatch(/<title>[^<]+<\/title>/);
    expect(indexHtml).toMatch(/<meta name="description" content="[^"]{60,}"/);
    for (const p of ["og:title", "og:description", "og:type"]) expect(indexHtml, p).toContain(`property="${p}"`);
    expect(indexHtml).toMatch(/<meta name="theme-color" content="#[0-9a-f]{6}" media="\(prefers-color-scheme: light\)"/i);
    expect(indexHtml).toMatch(/<meta name="theme-color" content="#[0-9a-f]{6}" media="\(prefers-color-scheme: dark\)"/i);
    const icon = /<link rel="icon"[^>]*href="\/([^"]+)"/.exec(indexHtml)![1];
    expect(fs.existsSync(new URL(`../../public/${icon}`, import.meta.url))).toBe(true);
  });
});
