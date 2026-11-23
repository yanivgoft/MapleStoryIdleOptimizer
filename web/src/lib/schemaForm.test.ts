import { describe, expect, it } from "vitest";
import { ALL, fixtureFor } from "../test/fixtures";
import {
  buildInputs, computedFields, copyContentValues, COMPANION_GROUP, COMPANION_GROUP_KEYS, defaultsFromSchema,
  getValue, groupFields, GROUP_ORDER, initialState, isApplicable, normalizeState, optionLabel, parseNumber, rangeText, setValue, sharedKeys,
  splitErrors, switchContentType, visibleGroups,
} from "./schemaForm";

const fp = fixtureFor("fp_mage");
const schema = fp.schema;
const defaults = fp.defaults;
const field = (k: string) => schema.fields.find((f) => f.key === k)!;

describe("grouping and applicability", () => {
  it("groups editable fields in schema order and keeps computed ones apart", () => {
    const groups = groupFields(schema);
    expect(groups.map((g) => g.name)).toEqual(["Character", "Offense", "Main stats", "Damage modifiers", "Skill levels", "Additional bonuses", COMPANION_GROUP, "PvP"]);
    expect(groups.flatMap((g) => g.fields).some((f) => f.computed)).toBe(false);
    expect(computedFields(schema).map((f) => f.key)).toContain("monster_defense");
  });
  it("hides fields that do not apply to the content type", () => {
    expect(isApplicable(field("pvp_fight_length"), "PvP")).toBe(true);
    expect(isApplicable(field("pvp_fight_length"), "World Boss")).toBe(false);
    const names = (ct: string) => visibleGroups(groupFields(schema), ct).map((g) => g.name);
    expect(names("World Boss")).not.toContain("PvP");
    expect(names("PvP")).toContain("PvP");
    const wb = visibleGroups(groupFields(schema), "World Boss").flatMap((g) => g.fields.map((f) => f.key));
    expect(wb).not.toContain("chapter_stage");
    expect(wb).not.toContain("boss_normal_weight_choice");
    const bt = visibleGroups(groupFields(schema), "Breakthrough").flatMap((g) => g.fields.map((f) => f.key));
    expect(bt).toContain("boss_normal_weight_choice");
    expect(bt).toContain("max_enemies_hit");
  });
});

describe("defaults per content type", () => {
  it("schema-derived defaults equal the engine's /defaults output", () => {
    for (const ct of schema.content_types) expect(defaultsFromSchema(schema, ct)).toEqual(defaults[ct]);
  });
  it("Chapter-Stage default differs per content type", () => {
    expect(defaults["Breakthrough"].chapter_stage).toBe("28-9");
    expect(defaults["Weapon Dungeon"].chapter_stage).toBe("80");
    expect(defaults["World Boss"].chapter_stage).toBeNull();
  });
  it("switching content type creates a default set once and keeps edits", () => {
    let s = initialState(schema, defaults["Chapter Boss"], "Chapter Boss");
    s = setValue(s, field("flat_attack"), 123456);
    s = switchContentType(s, schema, "Breakthrough", defaults["Breakthrough"]);
    expect(getValue(s, field("chapter_stage"))).toBe("28-9");
    expect(getValue(s, field("flat_attack"))).toBe(10000); // fresh defaults for the new content type
    s = switchContentType(s, schema, "Chapter Boss");
    expect(getValue(s, field("flat_attack"))).toBe(123456); // edits are remembered per content type
    s = copyContentValues(s, schema, "Chapter Boss", "Breakthrough");
    s = switchContentType(s, schema, "Breakthrough");
    expect(getValue(s, field("flat_attack"))).toBe(123456);
    expect(getValue(s, field("chapter_stage"))).toBe("28-9"); // per-content defaults are not copied
  });
  it("shared fields (level, companion level) follow across content types", () => {
    expect(sharedKeys(schema).sort()).toEqual(["companion_level", "level"]);
    let s = initialState(schema, defaults["Chapter Boss"]);
    s = setValue(s, field("level"), 140);
    s = switchContentType(s, schema, "PvP", defaults["PvP"]);
    expect(getValue(s, field("level"))).toBe(140);
  });
});

describe("buildInputs", () => {
  it("produces the flat dict the API wants: non-applicable null, computed omitted", () => {
    let s = initialState(schema, defaults["World Boss"], "World Boss");
    s = setValue(s, field("flat_attack"), 5e6);
    const inp = buildInputs(schema, s);
    expect(inp.content_type).toBe("World Boss");
    expect(inp.flat_attack).toBe(5e6);
    expect(inp.pvp_fight_length).toBeNull();
    expect(inp.chapter_stage).toBeNull();
    expect("monster_defense" in inp).toBe(false);
    expect(inp.level).toBe(200);
  });
  it("keeps the same keys as the engine defaults (plus artifacts)", () => {
    const s = initialState(schema, defaults["Chapter Boss"], "Chapter Boss");
    const keys = Object.keys(buildInputs(schema, s)).filter((k) => k !== "artifacts").sort();
    expect(keys).toEqual(Object.keys(defaults["Chapter Boss"]).sort());
  });
});

describe("normalizeState", () => {
  it("fills keys missing from an old profile", () => {
    const s = initialState(schema, defaults["Chapter Boss"], "Chapter Boss");
    delete s.perContent["Chapter Boss"].crit_damage;
    delete s.shared.level;
    const n = normalizeState(schema, s);
    expect(n.perContent["Chapter Boss"].crit_damage).toBe(0);
    expect(n.shared.level).toBe(200);
  });
  it("falls back to a valid content type", () => {
    const s = { ...initialState(schema, defaults["Chapter Boss"]), contentType: "Nope" };
    expect(schema.content_types).toContain(normalizeState(schema, s).contentType);
  });
});

describe("parseNumber", () => {
  it("accepts numbers, separators, exponents and blanks", () => {
    expect(parseNumber("1,209,199", "float")).toEqual({ ok: true, value: 1209199 });
    expect(parseNumber("1.5e6", "float")).toEqual({ ok: true, value: 1500000 });
    expect(parseNumber("  ", "float")).toEqual({ ok: true, value: null });
    expect(parseNumber(".5", "float")).toEqual({ ok: true, value: 0.5 });
  });
  it("rejects junk and fractional ints", () => {
    expect(parseNumber("abc", "float").ok).toBe(false);
    expect(parseNumber("1.5", "int").ok).toBe(false);
    expect(parseNumber("1e999", "float").ok).toBe(false);
  });
});

describe("splitErrors", () => {
  it("maps API errors to fields, leaves the rest general", () => {
    const r = splitErrors([{ field: "level", message: "bad" }, { field: "bogus", message: "unknown field" }, { field: "", message: "oops" }], schema);
    expect(r.byField).toEqual({ level: "bad" });
    expect(r.general).toEqual(["bogus: unknown field", "oops"]);
  });
});

describe("bounds", () => {
  it("parseNumber checks the schema's min / max with the API's wording", () => {
    expect(parseNumber("301", "int", 1, 300)).toEqual({ ok: false, message: "Must be between 1 and 300" });
    expect(parseNumber("0", "int", 1, 300).ok).toBe(false);
    expect(parseNumber("300", "int", 1, 300)).toEqual({ ok: true, value: 300 });
    expect(parseNumber("-1", "float", 0, 1e13)).toEqual({ ok: false, message: "Must be between 0 and 1e13" });
    expect(parseNumber("-1", "float", 0, null)).toEqual({ ok: false, message: "Must be at least 0" });
    expect(parseNumber("", "int", 1, 300)).toEqual({ ok: true, value: null });
    expect(parseNumber("5", "float")).toEqual({ ok: true, value: 5 });
  });
  it("rangeText: tight ranges as 'lo - hi', wide ones as 'min lo'", () => {
    expect(rangeText({ type: "int", min: 1, max: 300 })).toBe("1 - 300");
    expect(rangeText({ type: "float", min: 0, max: 100 })).toBe("0 - 100");
    expect(rangeText({ type: "float", min: 0, max: 1e8 })).toBe("min 0");
    expect(rangeText({ type: "enum", min: null, max: null })).toBe("");
  });
});

describe("companion section", () => {
  it("collects the companion pick, its level and summoning time in one section, in that order", () => {
    const g = groupFields(schema).find((x) => x.name === COMPANION_GROUP)!;
    expect(g.fields.map((f) => f.key)).toEqual(COMPANION_GROUP_KEYS);
    expect(groupFields(schema).find((x) => x.name === "Damage modifiers")!.fields.map((f) => f.key)).toContain("status_effect_damage");
    expect(groupFields(schema).find((x) => x.name === "Additional bonuses")!.fields.map((f) => f.key)).not.toContain("companion_summon_time_increase_pct");
  });
  it("the chosen companion's level comes from the Companions tab's table, not from the shared field", () => {
    let s = initialState(schema, defaults["Chapter Boss"], "Chapter Boss");
    expect(buildInputs(schema, s)).toMatchObject({ companion_choice: "None", companion_level: 0 });
    s = setValue(s, field("companion_choice"), "Blaze Wizard");
    expect(buildInputs(schema, s)).toMatchObject({ companion_choice: "None", companion_level: 0 }); // not owned: no companion
    s = { ...s, companions: { levels: { "Blaze Wizard": 7 }, potentialLinesPct: 0 } };
    expect(buildInputs(schema, s)).toMatchObject({ companion_choice: "Blaze Wizard", companion_level: 7 });
    s = setValue(s, field("companion_level"), 3); // the stale shared value is ignored
    expect(buildInputs(schema, s)).toMatchObject({ companion_level: 7 });
  });
  it("labels the None option without changing its value", () => {
    const f = schema.fields.find((x) => x.key === "companion_choice")!;
    expect(optionLabel(f, "None")).toBe("None (no companion)");
    expect(optionLabel(f, "Hero")).toBe("Hero");
  });
});

describe.each(ALL.map((c) => [c.info.id, c] as const))("every class: %s", (_id, c) => {
  const sch = c.schema;
  const cts = sch.content_types;
  it("form groups cover every editable field exactly once, sections in the fixed order", () => {
    const groups = groupFields(sch);
    const keys = groups.flatMap((g) => g.fields.map((f) => f.key));
    expect(keys.sort()).toEqual(sch.fields.filter((f) => !f.computed).map((f) => f.key).sort());
    const rank = (n: string) => GROUP_ORDER.indexOf(n);
    const known = groups.map((g) => rank(g.name)).filter((r) => r >= 0);
    expect(known).toEqual([...known].sort((a, b) => a - b));
    expect(groups.some((g) => g.name === COMPANION_GROUP)).toBe(true);
  });
  it("main stat fields follow the stat identity", () => {
    const main = sch.stat_identity.main.toLowerCase();
    const mainGroup = groupFields(sch).find((g) => g.name === "Main stats")!;
    const keys = mainGroup.fields.map((f) => f.key);
    expect(keys).toContain(`flat_${main}`);
    expect(keys).toContain(`${main}_pct`);
    expect(keys).toContain(sch.stat_identity.sub.toLowerCase());
  });
  it("schema defaults == the API's /defaults for every content type; buildInputs keeps exactly those keys", () => {
    for (const ct of cts) {
      expect(defaultsFromSchema(sch, ct)).toEqual(c.defaults[ct]);
      const keys = Object.keys(buildInputs(sch, initialState(sch, c.defaults[ct], ct))).filter((k) => k !== "artifacts").sort();
      expect(keys).toEqual(Object.keys(c.defaults[ct]).sort());
    }
  });
  it("sample inputs load into the form state and come back out unchanged", () => {
    const ct = String(c.sampleInputs.content_type);
    const s = initialState(sch, c.sampleInputs, ct);
    const out = buildInputs(sch, s);
    for (const [k, v] of Object.entries(c.sampleInputs)) {
      const f = sch.fields.find((x) => x.key === k)!;
      expect(out[k], k).toEqual(isApplicable(f, ct) ? v : null);
    }
  });
  it("only level and companion level are shared across content types", () => {
    expect(sharedKeys(sch).sort()).toEqual(["companion_level", "level"]);
  });
  it("numeric fields carry sane bounds, defaults inside them; enum / text fields none", () => {
    for (const f of sch.fields) {
      if ((f.type === "int" || f.type === "float") && !f.computed) {
        expect(typeof f.min, f.key).toBe("number");
        expect(typeof f.max, f.key).toBe("number");
        expect(f.min! <= f.max!, f.key).toBe(true);
        for (const ct of cts) {
          const d = defaultsFromSchema(sch, ct)[f.key];
          if (typeof d === "number") expect(d >= f.min! && d <= f.max!, `${f.key} default ${d}`).toBe(true);
        }
      } else {
        expect(f.min ?? null, f.key).toBeNull();
      }
    }
  });
  it("companion dropdown: None first, 16 companions", () => {
    const f = sch.fields.find((x) => x.key === "companion_choice")!;
    expect(f.options![0]).toBe("None");
    expect(f.options!.length).toBe(17);
    expect(sch.companions.length).toBe(16);
  });
  it("every content type switches and builds inputs without the non-applicable fields", () => {
    let s = initialState(sch, c.defaults[cts[0]], cts[0]);
    for (const ct of cts) {
      s = switchContentType(s, sch, ct, c.defaults[ct]);
      const out = buildInputs(sch, s);
      for (const f of sch.fields) if (!f.computed && !isApplicable(f, ct)) expect(out[f.key], `${ct}/${f.key}`).toBeNull();
      expect(visibleGroups(groupFields(sch), ct).length).toBeGreaterThan(0);
    }
  });
});
