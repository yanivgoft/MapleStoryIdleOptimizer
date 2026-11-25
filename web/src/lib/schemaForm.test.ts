import { describe, expect, it } from "vitest";
import { ALL, fixtureFor } from "../test/fixtures";
import { setSlot, slotsFor } from "./artifacts";
import type { ArtifactSchema, FormState } from "../types";
import {
  buildInputs, computedFields, contentGroup, CONTENT_GROUPS, copyContentValues, markEdited, NUMBER_HINT, seedSource, COMPANION_GROUP, COMPANION_GROUP_KEYS, defaultsFromSchema,
  getValue, groupFields, GROUP_ORDER, initialState, isApplicable, normalizeState, optionLabel, parseNumber, rangeText, setValue, sharedKeys,
  splitErrors, switchContentType, unitSuffix, visibleGroups,
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
    expect(getValue(s, field("flat_attack"))).toBe(123456); // a first-time content type with no sibling is seeded from the one it was switched from (seeding rules below)
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

describe("number shorthand", () => {
  it("K / M / B / T / Qa / Qi / Sx / Sp, any case, exact decimals", () => {
    const ok = (t: string) => parseNumber(t, "float");
    expect(ok("12.5M")).toEqual({ ok: true, value: 12500000 });
    expect(ok("12.5m")).toEqual({ ok: true, value: 12500000 });
    expect(ok("1.1T")).toEqual({ ok: true, value: 1.1e12 });                 // exactly the literal, no 1.1 * 1e12 rounding
    expect(ok("3k")).toEqual({ ok: true, value: 3000 });
    expect(ok("2B")).toEqual({ ok: true, value: 2e9 });
    expect(ok("1,500K")).toEqual({ ok: true, value: 1.5e6 });
    expect(ok(" 7 M ")).toEqual({ ok: true, value: 7e6 });
    expect(ok("4Qa")).toEqual({ ok: true, value: 4e15 });
    expect(ok("1.2qi")).toEqual({ ok: true, value: 1.2e18 });
    expect(ok("5Sx")).toEqual({ ok: true, value: 5e21 });
    expect(ok("2sp")).toEqual({ ok: true, value: 2e24 });
    expect(ok("-2M")).toEqual({ ok: true, value: -2e6 });
    expect(ok(".5K")).toEqual({ ok: true, value: 500 });
    expect(ok("1.2e6")).toEqual({ ok: true, value: 1.2e6 });
  });
  it("the suffix goes through the same whole-number and bounds checks", () => {
    expect(parseNumber("1.5K", "int")).toEqual({ ok: true, value: 1500 });
    expect(parseNumber("1.0005K", "int")).toEqual({ ok: false, message: "Whole number required" });
    expect(parseNumber("2K", "int", 1, 300)).toEqual({ ok: false, message: "Must be between 1 and 300" });
    expect(parseNumber("1e999", "float").ok).toBe(false);
    expect(parseNumber(`1${"0".repeat(300)}Sp`, "float").ok).toBe(false);          // overflows to Infinity
  });
  it("junk gets the one helpful message", () => {
    expect(NUMBER_HINT).toBe("Enter a number like 1234567, 12.5M or 1.2e6");
    for (const t of ["abc", "12X", "M", "1e", "12MM", "1e3K", "--5", "12 5"]) expect(parseNumber(t, "float"), t).toEqual({ ok: false, message: NUMBER_HINT });
  });
  it("one unit marker: no suffix when the label already ends in %", () => {
    const f = (label: string, unit: string) => ({ ...field("attack_pct"), label, unit });
    expect(unitSuffix(f("ATTACK %", "%"))).toBe("");
    expect(unitSuffix(f("Crit Rate", "%"))).toBe("%");
    expect(unitSuffix(f("Skill Cooldown Decrease", "s"))).toBe("s");
    expect(unitSuffix(f("Flat ATTACK", "flat"))).toBe("");
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
    s = { ...s, companions: { levels: { "Blaze Wizard": 7 } } };
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

// ---- seeding of a content type visited for the first time -------------------------------------------------------------------------------------------
describe("content type seeding", () => {
  const sch = fixtureFor("fp_mage").schema;
  const defs = fixtureFor("fp_mage").defaults;
  const art = sch.artifacts as ArtifactSchema;
  const f = (k: string) => sch.fields.find((x) => x.key === k)!;
  const atk = (s: FormState, ct = s.contentType) => s.perContent[ct]?.flat_attack;
  /** open `ct` the way the app does (defaults fetched, then seeded) and set Flat ATTACK there */
  const visit = (s: FormState, ct: string, flat?: number): FormState => {
    const n = switchContentType(s, sch, ct, defs[ct]);
    return flat === undefined ? n : setValue(n, f("flat_attack"), flat);
  };
  const start = (ct: string, flat: number) => setValue(initialState(sch, defs[ct], ct), f("flat_attack"), flat);

  it("groups: normal monsters, breakthrough, bosses; PvP in none; every group member is a real content type", () => {
    expect(CONTENT_GROUPS.map((g) => [...g])).toEqual([
      ["Chapter Hunt", "EXP Dungeon", "Equipment Dungeon"],
      ["Breakthrough", "Hero Dungeon"],
      ["Chapter Boss", "Weapon Dungeon", "Enhancement Dungeon", "World Boss"],
    ]);
    expect(contentGroup("PvP")).toBeNull();
    for (const g of CONTENT_GROUPS) for (const ct of g) expect(sch.content_types).toContain(ct);
    expect(new Set(CONTENT_GROUPS.flat()).size).toBe(CONTENT_GROUPS.flat().length);
  });

  it("rule 1: a visited content type of the SAME group wins over the one switched from", () => {
    let s = start("Chapter Hunt", 111);
    s = visit(s, "Chapter Boss", 222);                         // seeded from Chapter Hunt (rule 2), then edited
    expect(atk(s)).toBe(222);
    s = visit(s, "EXP Dungeon");                                // sibling Chapter Hunt (111), not the current Chapter Boss (222)
    expect(atk(s)).toBe(111);
    expect(seedSource(visit(start("Chapter Hunt", 1), "Chapter Boss"), "Weapon Dungeon")).toBe("Chapter Boss");
  });

  it("rule 1 with several siblings: the most recently edited one; without any edit record the first in group order", () => {
    let s = start("Chapter Hunt", 111);
    s = visit(s, "EXP Dungeon", 333);                          // edited after Chapter Hunt
    s = visit(s, "Chapter Boss", 999);                         // elsewhere
    s = visit(s, "Equipment Dungeon");
    expect(atk(s)).toBe(333);
    s = setValue(switchContentType(s, sch, "Chapter Hunt"), f("flat_attack"), 444);   // now Chapter Hunt is the most recent
    expect(seedSource(s, "Equipment Dungeon")).toBe("Chapter Hunt");                    // (as if it were new) the most recent edit is now Chapter Hunt's
    let t = start("Chapter Hunt", 111);
    t = visit(t, "EXP Dungeon", 333);
    t = { ...t, editOrder: undefined };                                                // an older state: no record
    expect(seedSource(t, "Equipment Dungeon")).toBe("Chapter Hunt");
    expect(atk(visit(t, "Equipment Dungeon"))).toBe(111);
  });

  it("rule 2: no sibling visited -> copy from the content type being switched from", () => {
    const s = visit(start("Chapter Boss", 555), "Chapter Hunt");            // Chapter Hunt has no visited sibling
    expect(atk(s)).toBe(555);
    expect(seedSource(start("Chapter Boss", 1), "Breakthrough")).toBe("Chapter Boss");
  });

  it("PvP: never a source for group lookups, but the first-time PvP copies the content type it came from", () => {
    let s = start("Chapter Hunt", 111);
    s = visit(s, "PvP", 777);                                  // first-time PvP: rule 2 (copied 111, then edited)
    expect(s.perContent["PvP"].pvp_fight_length).toBe(15);     // its own default stays (not an applicable field of Chapter Hunt)
    s = visit(s, "EXP Dungeon");                               // PvP is the most recently edited, but only the group counts: Chapter Hunt
    expect(atk(s)).toBe(111);
    const fromPvp = visit(start("PvP", 888), "Chapter Boss");   // no group member visited: rule 2 from where the user was
    expect(atk(fromPvp)).toBe(888);
    expect(seedSource(start("Chapter Boss", 1), "PvP")).toBe("Chapter Boss");
    expect(atk(visit(start("Chapter Boss", 5), "PvP"))).toBe(5);
  });

  it("copies what 'Copy stats from' copies, plus the companion pick and the equipped artifacts; not the per-content defaults", () => {
    let s = start("Breakthrough", 1234);
    s = setValue(s, f("companion_choice"), "Blaze Wizard");
    s = { ...s, companions: { levels: { "Blaze Wizard": 5 } }, equippedArtifacts: setSlot(art, s.equippedArtifacts, "Breakthrough", 1, "candle") };
    s = setValue(s, f("max_enemies_hit"), 7);
    s = setValue(s, f("chapter_stage"), "30-2");
    const h = visit(s, "Hero Dungeon");
    expect(atk(h)).toBe(1234);
    expect(h.perContent["Hero Dungeon"].companion_choice).toBe("Blaze Wizard");
    expect(h.perContent["Hero Dungeon"].max_enemies_hit).toBe(7);          // applicable to both
    expect(slotsFor(art, h.equippedArtifacts, "Hero Dungeon")[1]).toBe("candle");
    expect(h.perContent["Hero Dungeon"].chapter_stage).toBe("80");         // default_by_content: the content type's own default
    const w = visit(s, "World Boss");                                       // boss content: Breakthrough-only fields are not applicable there
    expect(w.perContent["World Boss"].max_enemies_hit).toBeNull();
    expect(w.perContent["World Boss"].chapter_stage).toBeNull();
    expect(slotsFor(art, w.equippedArtifacts, "World Boss")[1]).toBe("candle");
    expect(w.equippedArtifacts!["World Boss"]).not.toBe(s.equippedArtifacts!["Breakthrough"]);   // not shared by reference
  });

  it("never overwrites: stored content types are untouched, slots already stored for a new one are kept", () => {
    let s = start("Chapter Boss", 10);
    s = visit(s, "World Boss", 20);
    const before = JSON.stringify(s.perContent["Chapter Boss"]);
    s = visit(s, "Chapter Boss");                                            // switching back: nothing is copied over it
    expect(JSON.stringify(s.perContent["Chapter Boss"])).toBe(before);
    expect(atk(s)).toBe(10);
    // an equipped set that exists for a content type without values (a stored profile) is not replaced by the seed
    let t = start("Chapter Boss", 10);
    t = { ...t, equippedArtifacts: { ...setSlot(art, undefined, "Chapter Boss", 0, "candle"), ...setSlot(art, undefined, "Weapon Dungeon", 2, "chalice") } };
    const n = visit(t, "Weapon Dungeon");
    expect(slotsFor(art, n.equippedArtifacts, "Weapon Dungeon")[2]).toBe("chalice");
    expect(slotsFor(art, n.equippedArtifacts, "Weapon Dungeon")[0]).toBe("");
    expect(atk(n)).toBe(10);                                                  // the stats were seeded, the slots were not
  });

  it("only user edits count as 'edited' (seeding, shared fields and the switch itself do not)", () => {
    let s = start("Chapter Hunt", 1);
    expect(s.editOrder).toEqual(["Chapter Hunt"]);
    s = visit(s, "EXP Dungeon");
    expect(s.editOrder).toEqual(["Chapter Hunt"]);
    s = setValue(s, f("level"), 150);                                         // shared: not a content-type edit
    expect(s.editOrder).toEqual(["Chapter Hunt"]);
    s = setValue(s, f("crit_rate"), 5);
    expect(s.editOrder).toEqual(["EXP Dungeon", "Chapter Hunt"]);
    s = copyContentValues(visit(s, "Chapter Boss"), sch, "EXP Dungeon", "Chapter Boss");     // the user's own "Copy stats from"
    expect(s.editOrder).toEqual(["Chapter Boss", "EXP Dungeon", "Chapter Hunt"]);
    expect(markEdited(s, "Chapter Boss")).toBe(s);
  });

  it("older profiles load unchanged (no editOrder is invented, nothing is overwritten); the order round-trips through JSON and bad entries are dropped", () => {
    const old = initialState(sch, defs["Chapter Boss"], "Chapter Boss");
    delete (old as { editOrder?: string[] }).editOrder;
    const n = normalizeState(sch, JSON.parse(JSON.stringify(old)));
    expect("editOrder" in n).toBe(false);
    expect(n.perContent).toEqual(old.perContent);
    expect(Object.keys(n.perContent)).toEqual(["Chapter Boss"]);
    const s = visit(start("Chapter Hunt", 9), "EXP Dungeon", 8);
    const back = normalizeState(sch, JSON.parse(JSON.stringify(s)));
    expect(back.editOrder).toEqual(s.editOrder);
    expect(back.perContent).toEqual(s.perContent);
    const bad = normalizeState(sch, { ...s, editOrder: ["EXP Dungeon", "Nope", "EXP Dungeon", 5 as unknown as string, "Chapter Hunt"] });
    expect(bad.editOrder).toEqual(["EXP Dungeon", "Chapter Hunt"]);
    // a profile that stored several content types seeds a NEW one from the most recently edited sibling of its record
    const t = visit(normalizeState(sch, JSON.parse(JSON.stringify(s))), "Equipment Dungeon");
    expect(atk(t)).toBe(8);
  });

  it("every class: opening a first-time content type seeds it and keeps buildInputs valid", () => {
    for (const c of ALL) {
      let st = initialState(c.schema, c.defaults[c.schema.content_types[0]], c.schema.content_types[0]);
      st = setValue(st, c.schema.fields.find((x) => x.key === "flat_attack")!, 4242);
      for (const ct of c.schema.content_types) {
        st = switchContentType(st, c.schema, ct, c.defaults[ct]);
        const inp = buildInputs(c.schema, st);
        expect(inp.flat_attack, `${c.info.id}/${ct}`).toBe(4242);
        for (const fl of c.schema.fields) if (!fl.computed && !isApplicable(fl, ct)) expect(inp[fl.key], `${ct}/${fl.key}`).toBeNull();
      }
    }
  });
});
