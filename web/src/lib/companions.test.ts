import { describe, expect, it } from "vitest";
import { sensFixture } from "../test/sensFixture";
import { ALL, fixtureFor } from "../test/fixtures";
import { buildInputs, initialState, normalizeState, setValue } from "./schemaForm";
import { exportJson, parseImport, withArtifacts } from "./profiles";
import type { FormState, Profile } from "../types";
import {
  bestSummary, cleanLevel, companionOptions, companionsOf, companionViews, cubesCompanionLinesPct, effectiveCompanion, legacyCompanions, normalizeCompanions,
  potentialLineTotals, relevel, sensitivityExtras, setCompanionLevel, setPotentialLinesPct, stepTotals, summonViews, unlockedCompanions,
} from "./companions";
import { sensitivityBody } from "./sensitivity";

const fp = fixtureFor("fp_mage");
const schema = fp.schema;
const field = (k: string) => schema.fields.find((f) => f.key === k)!;
const fresh = (ct = "World Boss"): FormState => initialState(schema, fp.defaults[ct], ct);
const choose = (s: FormState, name: string) => setValue(s, field("companion_choice"), name);
const sens = sensFixture().result;

describe("levels -> chosen companion", () => {
  it("a fresh state owns nothing, so the dropdown is just None and the request has no companion", () => {
    const s = fresh();
    expect(companionsOf(schema, s).levels).toEqual({});
    expect(companionOptions(schema, companionsOf(schema, s))).toEqual(["None"]);
    expect(buildInputs(schema, s)).toMatchObject({ companion_choice: "None", companion_level: 0 });
  });
  it("owning a companion adds it to the dropdown (schema order); the chosen one's level feeds companion_level", () => {
    let s = setCompanionLevel(fresh(), schema, "Hero", 4);
    s = setCompanionLevel(s, schema, "Wind Archer", 12);
    expect(companionOptions(schema, companionsOf(schema, s))).toEqual(["None", "Wind Archer", "Hero"]);
    expect(unlockedCompanions(schema, companionsOf(schema, s))).toEqual(["Wind Archer", "Hero"]);
    s = choose(s, "Hero");
    expect(effectiveCompanion(schema, s)).toEqual({ choice: "Hero", level: 4 });
    expect(buildInputs(schema, s)).toMatchObject({ companion_choice: "Hero", companion_level: 4 });
    s = setCompanionLevel(s, schema, "Hero", 18);
    expect(buildInputs(schema, s)).toMatchObject({ companion_level: 18 });
  });
  it("setting the chosen companion to Not unlocked resets the choice of every content type; other companions stay", () => {
    let s = setCompanionLevel(setCompanionLevel(fresh(), schema, "Hero", 4), schema, "Bishop", 2);
    s = choose(s, "Hero");
    s = { ...s, perContent: { ...s.perContent, Breakthrough: { ...s.perContent["World Boss"], companion_choice: "Hero" } } };
    s = setCompanionLevel(s, schema, "Hero", 0);
    expect(s.companions!.levels).toEqual({ Bishop: 2 });
    expect(s.perContent["World Boss"].companion_choice).toBe("None");
    expect(s.perContent["Breakthrough"].companion_choice).toBe("None");
  });
  it("junk levels / unknown companions are ignored or clamped", () => {
    const s = fresh();
    expect(setCompanionLevel(s, schema, "Nobody", 5)).toBe(s);
    expect(cleanLevel("Not unlocked")).toBe(0);
    expect(cleanLevel(99)).toBe(18);
    expect(cleanLevel("7")).toBe(7);
    expect(cleanLevel(-3)).toBe(0);
    expect(normalizeCompanions({ levels: { Hero: 5, Nobody: 3, "FP Mage": 0, Bishop: "x" }, potentialLinesPct: -4 }, schema.companions)).toEqual({ levels: { Hero: 5 }, potentialLinesPct: 0 });
    expect(normalizeCompanions(null)).toEqual({ levels: {}, potentialLinesPct: 0 });
  });
  it("the sample inputs (Blaze Wizard Lv10) come back out unchanged, with Blaze owned at 10", () => {
    for (const c of ALL) {
      const ct = String(c.sampleInputs.content_type);
      const s = initialState(c.schema, c.sampleInputs, ct);
      expect(s.companions!.levels, c.info.id).toEqual({ "Blaze Wizard": 10 });
      const out = buildInputs(c.schema, s);
      expect(out.companion_choice).toBe(c.sampleInputs.companion_choice);
      expect(out.companion_level).toBe(c.sampleInputs.companion_level);
    }
  });
});

describe("request building with companion_levels", () => {
  it("lists all 16 companions (0 = not unlocked) plus the potential lines, and sensitivityBody keeps them next to `which`", () => {
    let s = setCompanionLevel(fresh(), schema, "Wind Archer", 7);
    s = setPotentialLinesPct(s, schema, 12);
    const extras = sensitivityExtras(schema, s);
    expect(Object.keys(extras.companion_levels)).toEqual(schema.companions);
    expect(extras.companion_levels["Wind Archer"]).toBe(7);
    expect(Object.values(extras.companion_levels).filter((v) => v > 0)).toHaveLength(1);
    expect(extras.companion_potential_lines_pct).toBe(12);
    const body = sensitivityBody({ ...buildInputs(schema, s), ...extras }, ["companions", "summon_time"]);
    expect(body).toMatchObject({ companion_levels: extras.companion_levels, companion_potential_lines_pct: 12, which: ["companions", "summon_time"] });
    expect(setPotentialLinesPct(s, schema, null).companions!.potentialLinesPct).toBe(0);
    expect(setPotentialLinesPct(s, schema, -3).companions!.potentialLinesPct).toBe(0);
  });
});

describe("profile migration", () => {
  const legacyState = (): FormState => {
    const s = fresh();
    const { companions: _drop, ...rest } = s; // a state saved before the Companions tab: no block, one shared level, a pick per content type
    void _drop;
    let t = { ...rest, shared: { ...s.shared, companion_level: 9 } } as FormState;
    t = choose(t, "Shadower");
    return { ...t, perContent: { ...t.perContent, Breakthrough: { ...t.perContent["World Boss"], companion_choice: "Paladin" } } };
  };
  it("old profiles keep every chosen companion unlocked at the old shared level, nothing else", () => {
    const n = normalizeState(schema, legacyState());
    expect(n.companions).toEqual({ levels: { Shadower: 9, Paladin: 9 }, potentialLinesPct: 0 });
    expect(buildInputs(schema, n)).toMatchObject({ companion_choice: "Shadower", companion_level: 9 });
    expect(legacyCompanions({ companion_level: 9 }, n.perContent).levels).toEqual({ Shadower: 9, Paladin: 9 });
  });
  it("an old profile with a companion chosen at level 0 had no companion: nothing is owned, the choice becomes None", () => {
    const old = legacyState();
    const n = normalizeState(schema, { ...old, shared: { ...old.shared, companion_level: 0 } });
    expect(n.companions!.levels).toEqual({});
    expect(n.perContent["World Boss"].companion_choice).toBe("None");
  });
  it("loading an old profile through the profile reader leaves `companions` undefined until normalizeState", () => {
    const p: Profile = { id: "a", name: "old", savedAt: "2026-01-01T00:00:00Z", state: legacyState() };
    expect(withArtifacts(p).state.companions).toBeUndefined();
    expect(parseImport(exportJson([p]))[0].state.companions).toBeUndefined();
  });
  it("new profiles round-trip levels and the potential lines through export / import and normalizeState", () => {
    let s = setPotentialLinesPct(setCompanionLevel(fresh(), schema, "Blaze Wizard", 10), schema, 13);
    s = choose(s, "Blaze Wizard");
    const p: Profile = { id: "b", name: "new", savedAt: "2026-11-20T00:00:00Z", state: s };
    const back = parseImport(exportJson([p]))[0].state;
    expect(back.companions).toEqual({ levels: { "Blaze Wizard": 10 }, potentialLinesPct: 13 });
    expect(normalizeState(schema, back).companions).toEqual(back.companions);
    expect(buildInputs(schema, normalizeState(schema, back))).toMatchObject({ companion_choice: "Blaze Wizard", companion_level: 10 });
  });
  it("junk in an imported companions block is repaired", () => {
    const p = { id: "c", name: "junk", savedAt: "x", state: { ...fresh(), companions: { levels: { Hero: "abc", "FP Mage": 99 }, potentialLinesPct: "x" } } } as unknown as Profile;
    expect(withArtifacts(p).state.companions).toEqual({ levels: { "FP Mage": 18 }, potentialLinesPct: 0 });
  });
});

describe("comparison table view", () => {
  const part = sens.companions!;
  it("rows in schema order, gain only where the row was computed at the same level, best / chosen flagged", () => {
    const cs = { levels: Object.fromEntries(schema.companions.map((n) => [n, 10])), potentialLinesPct: 0 };
    const views = companionViews(schema, cs, "Blaze Wizard", part);
    expect(views.map((v) => v.name)).toEqual(schema.companions);
    const best = part.rows.find((r) => r.rank_position === 1)!;
    expect(views.filter((v) => v.best).map((v) => v.name)).toEqual([best.name]);
    expect(views.filter((v) => v.chosen).map((v) => v.name)).toEqual(["Blaze Wizard"]);
    const changed = companionViews(schema, { ...cs, levels: { ...cs.levels, Hero: 11 } }, "Blaze Wizard", part);
    expect(changed.find((v) => v.name === "Hero")!.gain).toBeNull(); // stale level: wait for the new numbers
    expect(bestSummary(views)).toMatchObject({ best: { name: best.name }, owned: 16 });
  });
  it("not unlocked companions have no gain and are not chosen; sort by rank puts owned ones first", () => {
    const cs = { levels: { Hero: 10, "Dawn Warrior": 10 }, potentialLinesPct: 0 };
    const views = companionViews(schema, cs, "Hero", part, "rank");
    expect(views.slice(0, 2).map((v) => v.name)).toEqual(["Dawn Warrior", "Hero"]); // Dawn Warrior out-ranks Hero in the fixture
    expect(views.slice(2).every((v) => v.level === 0 && v.gain === null && !v.chosen && !v.best)).toBe(true);
    expect(companionViews(schema, { levels: {}, potentialLinesPct: 0 }, "None", null).every((v) => !v.chosen && !v.best)).toBe(true);
  });
  it("relevel (mock mode) relabels a fixture with the requested levels and re-ranks the owned ones", () => {
    const r = relevel(part, { Hero: 3, "Dawn Warrior": 5, Paladin: 0 }, "Hero", 3);
    expect(r.rows.filter((x) => x.unlocked).map((x) => x.name).sort()).toEqual(["Dawn Warrior", "Hero"]);
    expect(r.ranking).toEqual(["Dawn Warrior", "Hero"]);
    expect(r.rows.find((x) => x.name === "Hero")).toMatchObject({ level: 3, rank_position: 2 });
    expect(r.rows.find((x) => x.name === "Paladin")).toMatchObject({ unlocked: false, rank_position: null, dps_gain: 0 });
    expect(r).toMatchObject({ chosen: "Hero", chosen_level: 3 });
  });
});

describe("summoning-time potential lines", () => {
  it("lists the workbook's 18 totals with their combinations (companion_model.potential_line_totals)", () => {
    const t = potentialLineTotals();
    expect(t.map((x) => x.total)).toEqual([5, 8, 10, 12, 13, 15, 16, 18, 20, 21, 24, 28, 32, 36, 40, 44, 52, 60]);
    const by = Object.fromEntries(t.map((x) => [x.total, x.combos]));
    expect(by[5]).toEqual(["Epic: 5", "Unique: 5"]);
    expect(by[13]).toEqual(["Unique: 8+5"]);
    expect(by[24]).toEqual(["Legendary: 12+12", "Legendary: 8+8+8", "Mystic: 12+12", "Unique: 8+8+8"]);
    expect(by[32]).toEqual(["Legendary: 12+12+8", "Mystic: 20+12"]);
    expect(by[60]).toEqual(["Mystic: 20+20+20"]);
  });
  it("matches the engine's rows of the fixture total for total", () => {
    expect(sens.summon_time!.rows.map((r) => r.total_pct)).toEqual([0, ...potentialLineTotals().map((x) => x.total)]);
  });
  it("flags the jumps to +15% (Blaze Wizard's 3rd stun cast at +13.667%) and +28% in the fixture", () => {
    expect([...stepTotals(sens.summon_time!.rows)]).toEqual([15, 28]);
  });
  it("views: gains against none of the lines, 'vs current' against the setup now, the entered lines marked", () => {
    const rows = sens.summon_time!.rows;
    const v = summonViews(rows, sens.baseline_total, sens.companions!.current_companion_dps, 0);
    expect(v[0].current).toBe(true);
    expect(v[0].gain).toBeCloseTo(0, 6);
    expect(v[0].vsCurrent).toBeCloseTo(0, -3); // lines 0 == the current setup in the fixture
    const r15 = v.find((x) => x.row.total_pct === 15)!;
    expect(r15.gain! / sens.baseline_total).toBeCloseTo(rows.find((r) => r.total_pct === 15)!.weighted_dps_change, 3);
    expect(r15.combos).toEqual(["Epic: 5+5+5", "Unique: 5+5+5"]);
    expect(summonViews(rows, null, null, 12).find((x) => x.row.total_pct === 12)).toMatchObject({ current: true, gain: null, vsCurrent: null });
  });
  it("lines typed on the Cubes tab can be offered", () => {
    expect(cubesCompanionLinesPct(undefined)).toBe(0);
    const line = (stat: string, value: number | null) => ({ stat, value });
    const lines = (...l: ReturnType<typeof line>[]) => ({ rarity: "epic", pity: null, lines: [...l, ...Array(3 - l.length).fill(line("(none)", null))] });
    expect(
      cubesCompanionLinesPct({
        "boots|Potential": lines(line("Companion Summoning Time Increase %", 12), line("Damage %", 5), line("Companion Summoning Time Increase %", 8)),
        "boots|Bonus Potential": lines(line("Companion Summoning Time Increase %", null)),
      }),
    ).toBe(20);
  });
});
