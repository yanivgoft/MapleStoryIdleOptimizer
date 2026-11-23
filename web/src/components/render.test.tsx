import { describe, expect, it } from "vitest";
import { renderToString } from "react-dom/server";
import { initialState, setValue } from "../lib/schemaForm";
import { formatNumber } from "../lib/format";
import { ALL, classList, fixtureFor } from "../test/fixtures";
import { InputsForm } from "./InputsForm";
import { Results } from "./Results";
import { ClassPicker } from "./ClassPicker";

const esc = (t: string) => t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#x27;");
const strip = (h: string) => h.replace(/<!-- -->/g, "");

const form = (id: string, ct: string, errors: Record<string, string> = {}) => {
  const c = fixtureFor(id);
  return strip(
    renderToString(
      <InputsForm schema={c.schema} state={initialState(c.schema, c.defaults[ct], ct)} onState={() => undefined} errors={errors} derived={c.result.derived} loadDefaults={() => undefined} />,
    ),
  );
};

describe("render smoke (server-side), FP-Mage", () => {
  const fp = fixtureFor("fp_mage");
  it("renders the form from the schema, hiding non-applicable fields", () => {
    const wb = form("fp_mage", "World Boss", { level: "bad level" });
    expect(wb).toContain("Flat INT");
    expect(wb).toContain("bad level");
    expect(wb).not.toContain("PvP Fight Length");
    expect(wb).not.toContain("Chapter-Stage");
    expect(form("fp_mage", "PvP")).toContain("PvP Fight Length");
    expect(form("fp_mage", "Breakthrough")).toContain("Boss/Normal Emphasis");
    expect(wb).toContain('for="f-level"');
  });
  it("renders results: total, breakdown, companion, engine flag", () => {
    const html = strip(renderToString(<Results result={fp.result} busy={false} stale={false} />));
    expect(html).toContain("Total DPS");
    expect(html).toContain(formatNumber(fp.result.total_dps));
    expect(html).toContain("Companion: Blaze Wizard");
    expect(html).toContain("Basic Attack");
    expect(html).toContain(`Timeline engine: ${fp.result.engine_on ? "on" : "off"}`);
    expect(html).toContain("<svg");
  });
  it("hints: schema help text, range and min / max attributes", () => {
    const html = form("fp_mage", "Chapter Boss");
    expect(html).toContain("Defense Penetration in %, 0-100");
    expect(html).toContain("(0 - 100)");
    expect(html).toMatch(/id="f-level"[^>]*min="1"[^>]*max="300"/);
  });
});

describe("render smoke, every class", () => {
  it.each(ALL.map((c) => [c.info.id, c] as const))("%s: form for all ten content types", (id, c) => {
    for (const ct of c.schema.content_types) {
      const html = form(id, ct);
      for (const f of c.schema.fields) {
        if (f.computed) continue;
        const applicable = f.applicable === null || f.applicable.includes(ct);
        if (applicable && f.key !== "content_type" && f.key !== "companion_level") expect(html, `${id}/${ct}/${f.key}`).toContain(`for="f-${f.key}"`);
        if (f.key === "companion_level") expect(html, `${id}/${ct}/${f.key}`).not.toContain('for="f-companion_level"'); // read-only line: the level lives on the Companions tab
        else if (!applicable) expect(html, `${id}/${ct}/${f.key}`).not.toContain(`for="f-${f.key}"`);
      }
      expect(html).toContain("Companion");
      expect(html).toContain("Status Effect Damage");
      expect(html).toContain("Companion Summoning Time Increase");
      expect(html).toContain("None (no companion)");
    }
  });
  it.each(ALL.map((c) => [c.info.id, c] as const))("%s: class-specific labels and the main stat", (id, c) => {
    const html = form(id, "Chapter Boss");
    const main = c.schema.stat_identity.main;
    expect(html).toContain(`Flat ${main}`);
    expect(html).toContain(`${main} %`);
    if (id === "night_lord" || id === "shadower") expect(html).toContain("Incoming Hit Rate");
    if (id === "bishop" || id === "dark_knight") expect(html).toContain("Defense %");
    expect(html).toContain("Defense");
  });
  it.each(ALL.map((c) => [c.info.id, c] as const))("%s: results", (_id, c) => {
    const html = strip(renderToString(<Results result={c.result} busy={false} stale={false} />));
    expect(html).toContain(formatNumber(c.result.total_dps));
    expect(html).toContain("<svg");
    for (const s of c.result.skills.filter((x) => x.unlocked)) expect(html, s.key).toContain(esc(s.name));
    expect(html).toContain("Companion: Blaze Wizard");
    expect(html).toContain("Derived values");
  });
  it("no companion chosen: no 'Companion: None' row; a stun-only block is labelled as such", () => {
    const hero = fixtureFor("hero").result;
    const none = { ...hero, companion: { ...hero.companion!, choice: "None", level: 0, dps: 123, boss_dps: 123, normal_dps: 0, share: 0.001 } };
    let html = strip(renderToString(<Results result={none} busy={false} stale={false} />));
    expect(html).not.toContain("Companion: None");
    expect(html).toContain("Stun effect (no companion)");
    html = strip(renderToString(<Results result={{ ...none, companion: { ...none.companion, dps: 0 } }} busy={false} stale={false} />));
    expect(html).not.toContain("Stun effect");
    html = strip(renderToString(<Results result={{ ...hero, companion: null }} busy={false} stale={false} />));
    expect(html).not.toContain("Companion:");
  });
  it("companion section: dropdown lists only owned companions, the level is a read-only line with an Edit link", () => {
    const c = fixtureFor("corsair");
    const base = initialState(c.schema, c.defaults["Chapter Boss"], "Chapter Boss");
    const render = (st: typeof base, open?: () => void) =>
      strip(renderToString(<InputsForm schema={c.schema} state={st} onState={() => undefined} errors={{}} loadDefaults={() => undefined} onOpenCompanions={open} />));
    const none = render(base, () => undefined);
    expect(none).not.toContain('id="f-companion_level"');
    for (const n of ["Shadower", "Hero", "Wind Archer"]) expect(none).not.toContain(`<option value="${n}"`);
    expect(none).toContain('<option value="None"');
    expect(none).toContain("no companions set up yet");
    expect(none).toContain("Set up your companions");
    const owned = { ...setValue(base, c.schema.fields.find((f) => f.key === "companion_choice")!, "Shadower"), companions: { levels: { Shadower: 7, Hero: 3 }, potentialLinesPct: 0 } };
    const html = render(owned, () => undefined);
    expect(html).toContain("Shadower: level 7");
    expect(html).toContain("Edit companions");
    expect(html).toMatch(/<option value="Shadower" selected/);
    expect(html).toContain('<option value="Hero">');
    expect(html).not.toContain('<option value="Wind Archer">');
    expect(html).toContain("Status Effect Damage");
    expect(html).toContain("Companion Summoning Time Increase");
  });
});

describe("class picker", () => {
  it("renders every class of the fixtures in family groups with the stat identity and a status line", () => {
    const html = strip(renderToString(<ClassPicker classes={classList} value="night_lord" onChange={() => undefined} />));
    expect((html.match(/<optgroup/g) ?? []).length).toBe(5);
    expect((html.match(/<option/g) ?? []).length).toBe(classList.length);
    expect(html).toContain("Night Lord (LUK / DEX)");
    expect(html).toContain("Corsair (DEX / STR)");
    expect(html).toContain("Status");
    const night = classList.find((c) => c.id === "night_lord")!;      // the status line follows the selected class's status block
    const item = (label: string, on?: boolean) => `${label}: ${on ? "yes" : "coming soon"}`;
    expect(html).toContain(item("Companions", night.status?.companions));
    expect(html).toContain(item("Artifacts", night.status?.artifacts));
    expect(html).toContain(item("Stat values", night.status?.stat_values));
    const fp = strip(renderToString(<ClassPicker classes={classList} value="fp_mage" onChange={() => undefined} />));
    expect(fp).toContain("Artifacts: yes");
    const soon = strip(renderToString(<ClassPicker classes={[{ id: "x", name: "X", family: "Mage", status: { companions: true, artifacts: false, stat_values: false } }]} value="x" onChange={() => undefined} />));
    expect(soon).toContain("Artifacts: coming soon");
    expect(soon).toContain("Companions: yes");
  });
});
