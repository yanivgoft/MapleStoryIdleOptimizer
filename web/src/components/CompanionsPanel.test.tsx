import { describe, expect, it } from "vitest";
import { renderToString } from "react-dom/server";
import { sensFixture } from "../test/sensFixture";
import { ALL, fixtureFor } from "../test/fixtures";
import { initialState, setValue } from "../lib/schemaForm";
import { setCompanionLevel, setPotentialLinesPct } from "../lib/companions";
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
  it("lists the 16 companions with a level selector 'Not unlocked' / 1..18 each", () => {
    const html = view(fresh(), { result: null });
    expect((html.match(/data-companion=/g) ?? []).length).toBe(16);
    expect((html.match(/aria-label="[A-Za-z ]+ level"/g) ?? []).length).toBe(16);
    const sel = html.match(/<select class="companion-select" aria-label="Hero level"[\s\S]*?<\/select>/)![0];
    expect(sel).toContain('<option value="0" selected="">Not unlocked</option>');
    expect((sel.match(/<option /g) ?? []).length).toBe(19);
    expect(sel).toContain('<option value="18">18</option>');
    expect(html).toContain("Unlock at least one companion");
    expect(html).toContain("Summoning Time Increase potential lines");
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
    expect(row("Blaze Wizard")).toContain("+26.2%");
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

describe("summoning time potential lines section", () => {
  it("the table has the 18 totals + 'none' with combinations, DPS gain and the threshold explanation", () => {
    const html = view(choose(owned(fresh(), { "Blaze Wizard": 10 }), "Blaze Wizard"));
    expect((html.match(/data-total=/g) ?? []).length).toBe(19);
    for (const h of ["Total % from lines", "Possible line combinations", "DPS gain", "DPS vs current"]) expect(html).toContain(h);
    expect(html).toContain("Unique: 8+5");
    expect(html).toContain("Blaze Wizard&#x27;s 3rd stun cast needs a total of +13.667%");
    expect(html).not.toContain("Boss: avg DPS"); // World Boss has no boss phase
    expect(html).toMatch(/data-total="15"[\s\S]*?>step</);
  });
  it("boss-phase columns appear in boss-phase content", () => {
    const part = { ...sens.summon_time!, boss_phase_content: true, rows: sens.summon_time!.rows.map((r) => ({ ...r, avg_boss_dps_change: 0.01, boss_phase_time_factor: 1.02, boss_damage_change: 0.03 })) };
    const html = view(choose(owned(fresh(), { "Blaze Wizard": 10 }), "Blaze Wizard"), { result: { ...sens, summon_time: part } });
    for (const h of ["Boss: avg DPS", "Boss: time x", "Boss: total damage"]) expect(html).toContain(h);
    expect(html).toContain("+3.00%");
  });
  it("the entered lines are an input and mark their row; without a companion the table asks for one", () => {
    const state = choose(setPotentialLinesPct(owned(fresh(), { "Blaze Wizard": 10 }), fp.schema, 13), "Blaze Wizard");
    const html = view(state);
    expect(html).toMatch(/aria-label="Boots lines already counted in the Summoning Time Increase %"[^>]*value="13"/);
    expect(html).toMatch(/<tr class="current" data-total="13">[\s\S]*?>yours</);
    const none = view(owned(fresh(), { "Blaze Wizard": 10 }));
    expect(none).toContain("Choose a companion for World Boss");
    expect(none).not.toContain("data-total=");
  });
  it("offers the lines typed on the Cubes tab", () => {
    const cubes = { "boots|Potential": { rarity: "epic", pity: null, lines: [{ stat: "Companion Summoning Time Increase %", value: 12 }, { stat: "(none)", value: null }, { stat: "(none)", value: null }] } };
    const html = view({ ...choose(owned(fresh(), { "Blaze Wizard": 10 }), "Blaze Wizard"), cubes });
    expect(html).toContain("use 12% from the lines on the Cubes tab");
  });
});

describe("request inputs of the page", () => {
  it("compute inputs + every companion's level + the lines already counted; null while no inputs", () => {
    const state = setPotentialLinesPct(owned(fresh(), { Hero: 4 }), fp.schema, 8);
    const req = companionRequestInputs(fp.schema, state, { level: 200 }) as Record<string, unknown>;
    expect(req.level).toBe(200);
    expect((req.companion_levels as Record<string, number>).Hero).toBe(4);
    expect(Object.keys(req.companion_levels as object)).toHaveLength(16);
    expect(req.companion_potential_lines_pct).toBe(8);
    expect(companionRequestInputs(fp.schema, state, null)).toBeNull();
  });
});

function choose(s: FormState, name: string): FormState {
  return setValue(s, fp.schema.fields.find((f) => f.key === "companion_choice")!, name);
}
