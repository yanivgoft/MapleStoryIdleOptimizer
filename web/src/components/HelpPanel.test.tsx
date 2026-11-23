import { describe, expect, it } from "vitest";
import { renderToString } from "react-dom/server";
import { HELP_SECTIONS, HelpPanel, hintGroups } from "./HelpPanel";
import { classCapabilities, KNOWN_GAPS_URL, LIMITATIONS } from "../content/help";
import { ALL, classList, fixtureFor } from "../test/fixtures";

const strip = (h: string) => h.replace(/<!-- -->/g, "").replace(/&#x27;/g, "'");
const fp = fixtureFor("fp_mage");
const html = strip(renderToString(<HelpPanel classes={classList} schema={fp.schema} />));

describe("Help tab render", () => {
  it("has the headings, in order, with anchors from the table of contents", () => {
    const heads = ["Help", "How to use it", "Which stats to type", "Modelling conventions", "What is modelled per class", "Known limitations"];
    let at = -1;
    for (const h of heads) {
      const i = html.indexOf(`>${h}</h`);
      expect(i, h).toBeGreaterThan(at);
      at = i;
    }
    expect(html).toContain("<h2");
    for (const s of HELP_SECTIONS) {
      expect(html, s.id).toContain(`href="#${s.id}"`);
      expect(html, s.id).toContain(`id="${s.id}"`);
    }
  });
  it("the Import from Excel help names the cube gear as imported and Equipment Compare as not imported", () => {
    expect(html).toContain("Import from Excel");
    expect(html).toContain("your cube gear (the PotentialCubes sheet");
    expect(html).toContain("and the Equipment Compare sheet");
  });
  it("covers every tab and the key conventions", () => {
    for (const t of ["Calculator", "Companions", "Profiles", "Stat values", "Artifacts", "Cubes", "Equipment compare"]) expect(html, t).toContain(`<strong>${t}</strong>`);
    for (const t of ["Book of Ancient", "Bottle of Emotion", "Reindeer", "time-weighted", "second-by-second", "90 s cooldown", "7 s", "0.3 s", "13.667%", "Arwen", "+20%", "Lower is better".toLowerCase(), "Seven artifacts"])
      expect(html.toLowerCase(), t).toContain(t.toLowerCase());
  });
  it("shows the selected class's schema help text per field, grouped", () => {
    const groups = hintGroups(fp.schema);
    expect(groups.map((g) => g.group)).toContain("Offense");
    expect(html).toContain(`Field hints for ${fp.schema.name}`);
    for (const g of groups) for (const f of g.fields) expect(html, f.key).toContain(f.help!.replace(/&/g, "&amp;").replace(/'/g, "'").replace(/"/g, "&quot;"));
    expect(html).not.toContain("Monster Defense"); // computed rows are left out
  });
  it("without a loaded class the hints say so", () => {
    expect(strip(renderToString(<HelpPanel classes={[]} schema={null} />))).toContain("Load a class");
  });
  it("per-class table has one row per fixture class, driven by status", () => {
    const rows = html.match(/<tr data-class="[a-z_]+"/g) ?? [];
    expect(rows.length).toBe(12);
    expect(rows.length).toBe(classList.length);
    for (const c of ALL) {
      const cap = classCapabilities(c.info);
      expect(cap["Stat values"], c.info.id).toBe(!!c.info.status?.stat_values);
      expect(cap.Cubes).toBe(cap["Equipment compare"]);
      expect(html).toContain(`data-class="${c.info.id}"`);
    }
    const row = (id: string) => html.split(`data-class="${id}"`)[1].split("</tr>")[0];
    expect(row("bowmaster")).toContain("coming soon"); // no stat values yet
    expect(row("hero")).not.toContain("coming soon");
  });
  it("limitations: at most 12 bullets and a link to KNOWN_GAPS.md", () => {
    expect(LIMITATIONS.length).toBeGreaterThan(0);
    expect(LIMITATIONS.length).toBeLessThanOrEqual(12);
    expect(html).toContain(`href="${KNOWN_GAPS_URL}"`);
    expect(html).toContain("No MP consumption");
    expect(html).toContain("Divine Protection");
  });
});
