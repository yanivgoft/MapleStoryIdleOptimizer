import { describe, expect, it } from "vitest";
import { renderToString } from "react-dom/server";
import { sensFixture } from "../test/sensFixture";
import { ALL, fixtureFor } from "../test/fixtures";
import { initialState, setValue } from "../lib/schemaForm";
import { setCompanionLevel } from "../lib/companions";
import { IDLE } from "../lib/sensitivityLoader";
import type { SensitivityResult } from "../lib/sensitivity";
import type { FormState } from "../types";
import { CompanionsView, companionRequestInputs, GAIN_UNAVAILABLE } from "./CompanionsPanel";

const strip = (h: string) => h.replace(/<!-- -->/g, "");
const fp = fixtureFor("fp_mage");
const sens = sensFixture().result;
const owned = (s: FormState, levels: Record<string, number>) => Object.entries(levels).reduce((t, [n, l]) => setCompanionLevel(t, fp.schema, n, l), s);

function view(state: FormState, over: Partial<{ result: SensitivityResult | null; supported: boolean; schema: typeof fp.schema; status: typeof IDLE }> = {}) {
  return strip(
    renderToString(
      <CompanionsView
        schema={over.schema ?? fp.schema}
        state={state}
        onState={() => undefined}
        result={over.result === undefined ? sens : over.result}
        status={over.status ?? IDLE}
        supported={over.supported ?? true}
        onOpenCalculator={() => undefined}
      />,
    ),
  );
}
const fresh = () => initialState(fp.schema, fp.defaults["World Boss"], "World Boss");
const allTen = () => owned(fresh(), Object.fromEntries(fp.schema.companions.map((n) => [n, 10])));

describe("Companions tab render", () => {
  it("the table is titled 'Your legendary companions' (heading, region and table caption)", () => {
    const html = view(fresh(), { result: null });
    expect(html).toContain("<h2>Your legendary companions</h2>");
    expect(html).toContain('aria-label="Your legendary companions"');
    expect(html).toMatch(/<caption class="sr-only">Your legendary companions<\/caption>/);
    expect(html).not.toMatch(/Your companions|companions you own/);
  });
  it("lists the 16 companions with a level selector 'Not unlocked' / 1..18 each", () => {
    const html = view(fresh(), { result: null });
    expect((html.match(/data-companion=/g) ?? []).length).toBe(16);
    expect((html.match(/aria-label="[A-Za-z ]+ level"/g) ?? []).length).toBe(16);
    const sel = html.match(/<select class="companion-select" aria-label="Hero level"[\s\S]*?<\/select>/)![0];
    expect(sel).toContain('<option value="0" selected="">Not unlocked</option>');
    expect((sel.match(/<option /g) ?? []).length).toBe(19);
    expect(sel).toContain('<option value="18">18</option>');
    expect(html).not.toMatch(/Unlock at least one companion|Set the level of every companion|What each total of boots/);   // no restating lines in the working area
    expect(html).not.toMatch(/<th[^>]* title=/);
    expect(html).not.toMatch(/potential lines|Lines already counted/i);
  });
  it("owned companions show DPS gain, % of total and rank; the best one and the chosen one are marked", () => {
    const base = choose(allTen(), "Blaze Wizard");
    const html = view(base);
    const best = sens.companions!.rows.find((r) => r.rank_position === 1)!;
    const row = (name: string) => html.match(new RegExp(`<tr class="[^"]*" data-companion="${name}"[\\s\\S]*?</tr>`))![0];
    expect(row(best.name)).toContain("best for World Boss");
    expect(row(best.name)).toMatch(/class="rank">1</);
    expect(row("Blaze Wizard")).toContain(">chosen<");
    expect(row("Blaze Wizard")).toMatch(/class="rank">8</);
    expect(row("Blaze Wizard")).toContain("+26.1%");
    expect(html).toContain(`Best companion for World Boss: <strong>${best.name}</strong>`);
    expect(html).toContain("rank 8 of 16");
    expect((html.match(/chip warn">best for/g) ?? []).length).toBe(1);
  });
  it("a companion that is not owned shows no gain; only owned ones are offered 'use in'", () => {
    const html = view(owned(fresh(), { Hero: 10 }));
    const row = html.match(/<tr class="dim" data-companion="Paladin"[\s\S]*?<\/tr>/)![0];
    expect(row).toContain("–");
    expect(row).not.toContain("use in");
    expect(html).toContain("use in World Boss");
  });
  it("classes without stat values still show the levels, with 'gain: not available for this class yet'", () => {
    const c = fixtureFor("hero");
    const state = initialState(c.schema, c.defaults["World Boss"], "World Boss");
    const html = strip(renderToString(<CompanionsView schema={c.schema} state={state} onState={() => undefined} result={null} status={IDLE} supported={false} />));
    expect((html.match(/data-companion=/g) ?? []).length).toBe(16);
    expect(html).toContain(GAIN_UNAVAILABLE);
    const stat = strip(renderToString(<CompanionsView schema={c.schema} state={state} onState={() => undefined} result={null} status={{ ...IDLE, unsupported: true }} supported={true} />));
    expect(stat).toContain(GAIN_UNAVAILABLE);
  });
  it.each(ALL.map((c) => [c.info.id, c] as const))("%s: renders for every class", (_id, c) => {
    const state = initialState(c.schema, c.sampleInputs, String(c.sampleInputs.content_type));
    const html = strip(renderToString(<CompanionsView schema={c.schema} state={state} onState={() => undefined} result={null} status={IDLE} supported={!!c.info.status?.stat_values} />));
    expect((html.match(/data-companion=/g) ?? []).length).toBe(16);
    expect(html).toContain('data-level="10"'); // Blaze Wizard Lv10 of the sample inputs
    expect(html).toContain(">chosen<");
  });
});

describe("request inputs of the page", () => {
  it("compute inputs + every companion's level (and nothing about potential lines); null while no inputs", () => {
    const state = owned(fresh(), { Hero: 4 });
    const req = companionRequestInputs(fp.schema, state, { level: 200 }) as Record<string, unknown>;
    expect(req.level).toBe(200);
    expect((req.companion_levels as Record<string, number>).Hero).toBe(4);
    expect(Object.keys(req.companion_levels as object)).toHaveLength(16);
    expect(req).not.toHaveProperty("companion_potential_lines_pct");
    expect(companionRequestInputs(fp.schema, state, null)).toBeNull();
  });
});

function choose(s: FormState, name: string): FormState {
  return setValue(s, fp.schema.fields.find((f) => f.key === "companion_choice")!, name);
}
