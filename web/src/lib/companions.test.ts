import { describe, expect, it } from "vitest";
import { sensFixture } from "../test/sensFixture";
import { ALL, fixtureFor } from "../test/fixtures";
import { buildInputs, initialState, normalizeState, setValue } from "./schemaForm";
import { exportJson, parseImport, withArtifacts } from "./profiles";
import type { FormState, Profile } from "../types";
import {
  bestSummary, cleanLevel, companionOptions, companionsOf, companionViews, effectiveCompanion, legacyCompanions, normalizeCompanions,
  relevel, sensitivityExtras, setCompanionLevel, unlockedCompanions,
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
    expect(normalizeCompanions({ levels: { Hero: 5, Nobody: 3, "FP Mage": 0, Bishop: "x" }, potentialLinesPct: -4 }, schema.companions)).toEqual({ levels: { Hero: 5 } });
    expect(normalizeCompanions(null)).toEqual({ levels: {} });
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
  it("lists all 16 companions (0 = not unlocked) and nothing else, and sensitivityBody keeps them next to `which`", () => {
    let s = setCompanionLevel(fresh(), schema, "Wind Archer", 7);
    const extras = sensitivityExtras(schema, s);
    expect(Object.keys(extras.companion_levels)).toEqual(schema.companions);
    expect(extras.companion_levels["Wind Archer"]).toBe(7);
    expect(Object.values(extras.companion_levels).filter((v) => v > 0)).toHaveLength(1);
    expect(Object.keys(extras)).toEqual(["companion_levels"]);
    const body = sensitivityBody({ ...buildInputs(schema, s), ...extras }, ["companions"]);
    expect(body).toMatchObject({ companion_levels: extras.companion_levels, which: ["companions"] });
    expect(body).not.toHaveProperty("companion_potential_lines_pct");
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
    expect(n.companions).toEqual({ levels: { Shadower: 9, Paladin: 9 } });
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
  it("new profiles round-trip levels through export / import and normalizeState", () => {
    let s = setCompanionLevel(fresh(), schema, "Blaze Wizard", 10);
    s = choose(s, "Blaze Wizard");
    const p: Profile = { id: "b", name: "new", savedAt: "2026-11-20T00:00:00Z", state: s };
    const back = parseImport(exportJson([p]))[0].state;
    expect(back.companions).toEqual({ levels: { "Blaze Wizard": 10 } });
    expect(normalizeState(schema, back).companions).toEqual(back.companions);
    expect(buildInputs(schema, normalizeState(schema, back))).toMatchObject({ companion_choice: "Blaze Wizard", companion_level: 10 });
  });
  it("an old profile that still carries `potentialLinesPct` loads without error and the field is not written back", () => {
    const old = { ...fresh(), companions: { levels: { "Blaze Wizard": 10 }, potentialLinesPct: 13 } } as unknown as FormState;
    const p: Profile = { id: "d", name: "old lines", savedAt: "2026-11-01T00:00:00Z", state: old };
    const loaded = withArtifacts(p).state;
    expect(loaded.companions).toEqual({ levels: { "Blaze Wizard": 10 } });
    expect(normalizeState(schema, old).companions).toEqual({ levels: { "Blaze Wizard": 10 } });
    expect(JSON.stringify(parseImport(exportJson([p]))[0].state.companions)).not.toContain("potentialLinesPct");
    expect(normalizeCompanions({ levels: { Hero: 4 }, potentialLinesPct: 9 })).toEqual({ levels: { Hero: 4 } });
  });
  it("junk in an imported companions block is repaired", () => {
    const p = { id: "c", name: "junk", savedAt: "x", state: { ...fresh(), companions: { levels: { Hero: "abc", "FP Mage": 99 } } } } as unknown as Profile;
    expect(withArtifacts(p).state.companions).toEqual({ levels: { "FP Mage": 18 } });
  });
});

describe("comparison table view", () => {
  const part = sens.companions!;
  it("rows in schema order, gain only where the row was computed at the same level, best / chosen flagged", () => {
    const cs = { levels: Object.fromEntries(schema.companions.map((n) => [n, 10])) };
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
    const cs = { levels: { Hero: 10, "Dawn Warrior": 10 } };
    const views = companionViews(schema, cs, "Hero", part, "rank");
    expect(views.slice(0, 2).map((v) => v.name)).toEqual(["Dawn Warrior", "Hero"]); // Dawn Warrior out-ranks Hero in the fixture
    expect(views.slice(2).every((v) => v.level === 0 && v.gain === null && !v.chosen && !v.best)).toBe(true);
    expect(companionViews(schema, { levels: {} }, "None", null).every((v) => !v.chosen && !v.best)).toBe(true);
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
