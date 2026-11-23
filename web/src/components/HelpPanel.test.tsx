import { describe, expect, it } from "vitest";
import { renderToString } from "react-dom/server";
import { HELP_SECTIONS, HelpPanel, hintGroups } from "./HelpPanel";
import { CONTACT_URL, classCapabilities, KNOWN_GAPS_URL, LIMITATIONS } from "../content/help";
import { ALL, classList, fixtureFor, withoutStatValues } from "../test/fixtures";

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
    expect(rows.length).toBe(classList.length);
    for (const c of ALL) {
      const cap = classCapabilities(c.info);
      expect(cap["Stat values"], c.info.id).toBe(!!c.info.status?.stat_values);
      expect(cap.Cubes).toBe(cap["Equipment compare"]);
      expect(html).toContain(`data-class="${c.info.id}"`);
    }
    const rowIn = (h: string, id: string) => h.split(`data-class="${id}"`)[1].split("</tr>")[0];
    // every real class: "coming soon" exactly when its status has no stat values (whichever classes that is today)
    for (const c of ALL) {
      const r = rowIn(html, c.info.id);
      expect(r.includes("coming soon"), c.info.id).toBe(!c.info.status?.stat_values);
      expect(r.includes("yes"), c.info.id).toBe(true); // (the Calculator column)
    }
    // a synthetic class without stat values: its Stat values / Cubes / Equipment compare cells say "coming soon", the others still say "yes"
    const synth = withoutStatValues();
    const withSynth = strip(renderToString(<HelpPanel classes={[...classList, synth.info]} schema={fp.schema} />));
    expect((withSynth.match(/<tr data-class="[a-z_]+"/g) ?? []).length).toBe(classList.length + 1);
    const sr = rowIn(withSynth, synth.info.id);
    expect(sr.match(/coming soon/g)).toHaveLength(3);
    expect(sr).toContain("yes");
    expect(rowIn(withSynth, "fp_mage")).not.toContain("coming soon"); // a class with stat values is unaffected
  });
  it("limitations: at most 12 bullets and a link to KNOWN_GAPS.md", () => {
    expect(LIMITATIONS.length).toBeGreaterThan(0);
    expect(LIMITATIONS.length).toBeLessThanOrEqual(12);
    expect(html).toContain(`href="${KNOWN_GAPS_URL}"`);
    expect(html).toContain("No MP consumption");
    expect(html).toContain("Divine Protection");
  });
});

describe("privacy policy", () => {
  it("is always part of the Help tab (also without accounts), listed in the contents and carries the contact link", () => {
    const html = strip(renderToString(<HelpPanel classes={classList} schema={null} />));
    expect(html).toContain('id="help-privacy"');
    expect(html).toContain("Privacy policy");
    expect(html).toContain("Without an account");
    expect(html).toContain("Delete my account and data");
    expect(html).toContain(CONTACT_URL);
    expect(HELP_SECTIONS.map((s) => s.id)).toContain("help-privacy");
  });
});
