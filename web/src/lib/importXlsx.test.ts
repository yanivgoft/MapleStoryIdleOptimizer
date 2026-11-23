import { describe, expect, it } from "vitest";
import { xlsxBytes, xlsxJson } from "../test/xlsxFiles";
import { ALL, fixtureFor } from "../test/fixtures";
import { XlsxBook, XlsxError } from "./xlsx_read";
import { CUBE_TABLES, XLSX_MAP, cubeSlotKey, detectClass, importWorkbook, uniqueProfileName } from "./importXlsx";
import { cubesFixture } from "../test/cubesFixture";
import { gearPayload, getRow, normalizeCubesState, rowsToCalculate, statChoices, statOptions, NOT_ROLLABLE_ON_SLOT } from "./cubes";
import type { CubesState } from "./cubes";
import { buildInputs, isApplicable } from "./schemaForm";
import { isProfile, withArtifacts } from "./profiles";
import type { ArtifactsState, Values } from "../types";
import { equippedKeys, emptyArtifacts, requestSlots } from "./artifacts";

interface Expected {
  level: number;
  contentType: string;
  perContent: Record<string, Values>;
  loadouts: Record<string, string[]>;           // content type -> equipped artifact keys
  artifactsFrom: string;
  stars: Record<string, number | string>;
  tables: Record<string, ArtifactsState>;       // content type -> the whole table the import must give
  linesRead: number;
  companionLevels: Record<string, number>;
  warnings: number;
  ignoredHints: string[];
  cubes: {
    state: CubesState;
    pieces: number;
    lines: number;
    rows: number;
    warnings: number;                           // the planted PotentialCubes problems (already part of `warnings`)
    ignored: number;
    hints: string[];                            // a message fragment of each planted warning
  };
}

const open = (name: string) => XlsxBook.open(xlsxBytes(name), name);

describe("xlsx_map.json matches the engine schemas", () => {
  it.each(ALL.map((c) => [c.schema.class_id, c] as const))("%s: every engine input has a workbook row and the layout fits the schema", (_id, c) => {
    const m = XLSX_MAP[c.schema.class_id];
    expect(m, "class in map").toBeTruthy();
    expect(m.inputs.contentTypes).toEqual(c.schema.content_types);
    const keys = c.schema.fields.filter((f) => !f.computed && f.key !== "content_type" && f.per_content).map((f) => f.key);
    expect(Object.keys(m.inputs.perContent).sort()).toEqual(keys.sort());
    expect(m.inputs.slotRows).toHaveLength(4);                                    // the WORKBOOK has 4 slot rows; the app allows max_slots (5)
    expect(c.schema.artifacts!.max_slots).toBeGreaterThan(m.inputs.slotRows.length);
    expect(m.artifacts.lineCols).toEqual([[3, 4], [6, 7], [9, 10]]);
    expect(Object.keys(m.artifacts.rows).sort()).toEqual(c.schema.artifacts!.artifacts.map((a) => a.key).sort());
    for (const a of c.schema.artifacts!.artifacts) expect(m.artifacts.rows[a.key].name).toBe(a.name);
    expect(Object.keys(m.companions.rows)).toEqual(c.schema.companions);
    // rows never collide
    expect(new Set(Object.values(m.inputs.perContent)).size).toBe(Object.keys(m.inputs.perContent).length);
    expect(Object.values(m.inputs.perContent).some((r) => m.inputs.slotRows.includes(r))).toBe(false);
  });
  it("every class has the PotentialCubes layout of its builder (15 slots x 2 tracks = 30 rows, 3 lines)", () => {
    for (const c of ALL) {
      const cc = XLSX_MAP[c.schema.class_id].cubes;
      expect(cc.sheet).toBe("PotentialCubes");
      expect([cc.headerRow, cc.firstRow, cc.lastRow]).toEqual([5, 6, 35]);
      expect(cc.lastRow - cc.firstRow + 1).toBe(CUBE_TABLES.slots.length * CUBE_TABLES.potentialTypes.length);
      expect([cc.slotCol, cc.typeCol, cc.rarityCol, cc.pityCol]).toEqual([1, 2, 3, 4]);
      expect(cc.lineCols).toEqual([[5, 6], [7, 8], [9, 10]]);
    }
  });
  it("the static cube tables equal the engine's cube meta of every class that has one", () => {
    for (const c of ALL.filter((x) => x.info.status?.stat_values)) {
      const m = cubesFixture(c.schema.class_id).meta;
      expect(CUBE_TABLES.slots, c.schema.class_id).toEqual(m.slots);
      expect(CUBE_TABLES.potentialTypes).toEqual(m.potential_types);
      expect(CUBE_TABLES.rarities).toEqual(m.rarities);
      expect(CUBE_TABLES.noneStat).toBe(m.none_stat);
      expect(CUBE_TABLES.stats).toEqual(m.stats);
      expect(CUBE_TABLES.statsBySlot).toEqual(m.stats_by_slot);
      expect(CUBE_TABLES.pityCaps).toEqual(m.pity_caps);
      expect(CUBE_TABLES.maxPity).toBe(m.limits.max_pity);
      expect(CUBE_TABLES.maxLineValue).toBe(m.limits.max_line_value);
    }
  });
  it("every class has its own title", () => {
    const titles = Object.values(XLSX_MAP).map((m) => m.title);
    expect(new Set(titles).size).toBe(titles.length);
    expect(Object.keys(XLSX_MAP).sort()).toEqual(ALL.map((c) => c.schema.class_id).sort());
  });
});

describe.each(ALL.map((c) => c.schema.class_id))("import of the generated %s workbook", (id) => {
  const { schema } = fixtureFor(id);
  const exp = xlsxJson<Expected>(`class_${id}.expected.json`);
  const book = open(`class_${id}.xlsx`);
  const res = importWorkbook(book, schema);

  it("detects the class from the Inputs title", () => {
    expect(detectClass(book).classId).toBe(id);
    expect(res.summary.detected).toBe("title");
    expect(res.state.classId).toBe(id);
  });
  it("reads level, selected content type and every per-content-type value", () => {
    expect(res.state.shared.level).toBe(exp.level);
    expect(res.state.contentType).toBe(exp.contentType);
    expect(Object.keys(res.state.perContent).sort()).toEqual(schema.content_types.slice().sort());
    for (const ct of schema.content_types) {
      for (const [key, want] of Object.entries(exp.perContent[ct])) {
        expect(res.state.perContent[ct][key], `${ct} / ${key}`).toEqual(want);
      }
    }
  });
  it("non-applicable cells are null, applicable ones are not undefined", () => {
    for (const ct of schema.content_types) {
      for (const f of schema.fields) {
        if (f.computed || !f.per_content || f.key === "content_type") continue;
        const v = res.state.perContent[ct][f.key];
        if (!isApplicable(f, ct)) expect(v ?? null).toBeNull();
        else expect(v).not.toBeUndefined();
      }
    }
  });
  it("imports the star level of EVERY artifact, the equipped set of the selected content type and the potential lines", () => {
    expect(res.summary.artifactsFrom).toBe(exp.artifactsFrom);
    expect(res.state.artifacts).toEqual(exp.tables[exp.artifactsFrom]);
    expect(Object.keys(res.state.artifacts)).toHaveLength(36);
    for (const [k, star] of Object.entries(exp.stars)) expect(res.state.artifacts[k].star, k).toBe(star === "Not Unlocked" ? null : star);
    expect(equippedKeys(schema.artifacts!, res.state.artifacts).sort()).toEqual([...exp.loadouts[exp.artifactsFrom]].sort());
    expect(res.summary.starsRead).toBe(36);
    expect(res.summary.linesRead).toBe(exp.linesRead);
    expect(res.summary.slots.map((s) => s.key).sort()).toEqual([...exp.loadouts[exp.artifactsFrom]].sort());
  });
  it("can import another content type's loadout (the stars and lines stay the same: they are per artifact)", () => {
    const other = schema.content_types[0];
    const r2 = importWorkbook(book, schema, { artifactsFrom: other });
    expect(r2.summary.artifactsFrom).toBe(other);
    expect(r2.state.artifacts).toEqual(exp.tables[other]);
  });
  it("imports companion levels and drops choices of companions that are not unlocked", () => {
    expect(res.state.companions!.levels).toEqual(exp.companionLevels);
    for (const ct of schema.content_types) {
      const choice = res.state.perContent[ct].companion_choice;
      expect(choice === "None" || (exp.companionLevels[String(choice)] ?? 0) >= 1).toBe(true);
    }
  });
  it("reports exactly the planted problems", () => {
    expect(res.warnings).toHaveLength(exp.warnings);
    expect(res.warnings.some((w) => /outside the allowed range/.test(w.message))).toBe(true);
    expect(res.warnings.some((w) => /not unlocked/.test(w.message))).toBe(true);
    for (const hint of exp.ignoredHints) expect(res.ignored.map((i) => i.message).join("\n")).toContain(hint);
    const ign = res.ignored.map((i) => i.message).join("\n");
    expect(ign).toMatch(/unknown artifact "bogus artifact"/);
    const w = res.warnings.map((x) => x.message).join("\n");
    expect(w).toMatch(/line 1: unknown potential stat "Bogus Stat %"; the line was left empty/);
    expect(w).toMatch(/line 1: unknown rarity "Godlike"; Rare used/);
    expect(ign).toMatch(/already in another slot/);
    expect(ign).toMatch(/different loadout/);
  });
  it("imports the cube gear (PotentialCubes) into the same state the Cubes tab edits", () => {
    expect(res.state.cubes).toEqual(exp.cubes.state);
    expect(res.summary.cubesRead).toBe(true);
    expect(res.summary.cubePieces).toBe(exp.cubes.pieces);
    expect(res.summary.cubeLines).toBe(exp.cubes.lines);
    expect(res.summary.cubeRows).toBe(exp.cubes.rows);
    expect(Object.keys(res.state.cubes!)).toHaveLength(exp.cubes.rows);                 // blank rows are not stored
    expect(normalizeCubesState(res.state.cubes)).toEqual(res.state.cubes);              // survives the profile's own repair
    expect(gearPayload(cubesFixture().meta, res.state.cubes)).toHaveLength(exp.cubes.rows);
  });
  it("reports exactly the planted cube problems", () => {
    expect(exp.cubes.hints).toHaveLength(exp.cubes.warnings);
    for (const h of exp.cubes.hints) expect(res.warnings.filter((x) => x.message.includes(h)), h).toHaveLength(1);   // each planted problem gives exactly one warning
    expect(res.ignored.filter((i) => /has no stat; ignored/.test(i.message))).toHaveLength(exp.cubes.ignored);
  });
  it("a stat the slot cannot roll is kept and flagged like the Cubes tab flags it", () => {
    const meta = cubesFixture().meta;
    let flagged = 0;
    for (const [key, row] of Object.entries(res.state.cubes!)) {
      const [slot] = key.split("|");
      for (const l of row.lines) {
        if (l.stat === "(none)") continue;
        const choices = statChoices(statOptions(meta, slot), l.stat, NOT_ROLLABLE_ON_SLOT);
        if (choices.find((c) => c.value === l.stat)?.warn) flagged++;
      }
    }
    expect(flagged).toBe(1);
  });
  it("the state is a well-formed profile the compute request can be built from", () => {
    const p = withArtifacts({ id: "x", name: "n", savedAt: "2026-01-01", state: res.state });
    expect(isProfile(p)).toBe(true);
    expect(p.state.artifacts).toEqual(res.state.artifacts);
    const inputs = buildInputs(schema, res.state);
    expect(inputs.level).toBe(exp.level);
    expect(inputs.content_type).toBe(exp.contentType);
    expect((inputs.artifacts as unknown[]).length).toBe(exp.loadouts[exp.artifactsFrom].length);
    expect(requestSlots(schema.artifacts!, res.state.artifacts)).toEqual(inputs.artifacts);
  });
});

describe("detection and robustness", () => {
  it("no title: no class", () => {
    expect(detectClass(open("literal.xlsx"))).toEqual({ classId: null, title: null });
    expect(detectClass(open("missing_sheets.xlsx")).classId).toBeNull();
  });
  it("a workbook without an Inputs sheet is refused with a clear message", () => {
    const { schema } = fixtureFor("shadower");
    expect(() => importWorkbook(open("missing_sheets.xlsx"), schema)).toThrow(XlsxError);
    expect(() => importWorkbook(open("missing_sheets.xlsx"), schema)).toThrow(/no "Inputs" sheet/);
  });
  it("a workbook of another class can be imported as the chosen class (same layout), flagged as chosen", () => {
    const { schema } = fixtureFor("hero");
    const r = importWorkbook(open("class_shadower.xlsx"), schema, { classChosen: true });
    expect(r.summary.detected).toBe("chosen");
    expect(r.state.classId).toBe("hero");
  });
  it("a workbook that has only the Inputs sheet still imports, with warnings about the missing sheets", () => {
    const { schema } = fixtureFor("shadower");
    const r = importWorkbook(open("inputs_only_shadower.xlsx"), schema);
    expect(r.state.perContent["Chapter Boss"].flat_attack).toBe(5000);
    expect(Object.keys(r.state.perContent)).toEqual(["Chapter Boss"]); // the other columns have no values
    expect(r.summary.skippedContentTypes).toHaveLength(schema.content_types.length - 1);
    expect(r.warnings.map((w) => w.where).sort()).toEqual(["ArtifactsInput", "CompanionsInput", "PotentialCubes"]);
    expect(r.state.artifacts).toEqual(emptyArtifacts(schema.artifacts!));            // nothing read: the defaults, nothing equipped
    expect(r.state.companions!.levels).toEqual({});
  });
  it("is deterministic and does not mutate the schema", () => {
    const { schema } = fixtureFor("bishop");
    const before = JSON.stringify(schema);
    const a = importWorkbook(open("class_bishop.xlsx"), schema);
    const b = importWorkbook(open("class_bishop.xlsx"), schema);
    expect(JSON.stringify(a.state)).toBe(JSON.stringify(b.state));
    expect(JSON.stringify(schema)).toBe(before);
  });
});

describe("odd values (Hero layout)", () => {
  const { schema } = fixtureFor("hero");
  const book = open("edge_hero.xlsx");
  const r = importWorkbook(book, schema);
  const msgs = (list: { message: string }[]) => list.map((m) => m.message).join("\n");
  it("recognises the title with a plain hyphen", () => expect(detectClass(book).classId).toBe("hero"));
  it("converts numeric text, '%' suffixes and numeric Chapter-Stage cells", () => {
    expect(r.state.shared.level).toBe(150);
    const cb = r.state.perContent["Chapter Boss"];
    expect(cb.flat_attack).toBe(1234.5);
    expect(cb.attack_pct).toBe(12.5);
    expect(r.state.perContent["Breakthrough"].chapter_stage).toBe("29");
    expect(r.state.perContent["Breakthrough"].boss_normal_weight_choice).toBe("Equal");
    expect(r.state.perContent["Breakthrough"].flat_attack).toBe(999); // formula with a cached result
  });
  it("garbage, a date-looking Chapter-Stage and wrong booleans fall back to the default and are warned about", () => {
    const cb = r.state.perContent["Chapter Boss"];
    const f = (k: string) => schema.fields.find((x) => x.key === k)!;
    expect(cb.crit_rate).toBe(f("crit_rate").default);
    expect(cb.crit_damage).toBe(f("crit_damage").default);
    expect(cb.chapter_stage).toBe(f("chapter_stage").default_by_content?.["Chapter Boss"] ?? f("chapter_stage").default);
    const w = msgs(r.warnings);
    expect(w).toMatch(/Crit Rate: "abc" is not a number/);
    expect(w).toMatch(/looks like a date/);
  });
  it("out-of-range / non-whole numbers are kept as typed and flagged", () => {
    const cb = r.state.perContent["Chapter Boss"];
    expect(cb.skill_lvl_1st).toBe(2.5);
    expect(cb.skill_lvl_2nd).toBe(-4);
    const w = msgs(r.warnings);
    expect(w).toMatch(/2\.5 is not a whole number/);
    expect(w).toMatch(/-4 is outside the allowed range/);
  });
  it("formula cells without a saved result and Excel errors read as blank (default) and are reported as ignored", () => {
    const f = (k: string) => schema.fields.find((x) => x.key === k)!;
    expect(r.state.perContent["Chapter Boss"].defense).toBe(f("defense").default);
    expect(r.state.perContent["Chapter Boss"].damage).toBe(f("damage").default);
    expect(r.summary.formulaCellsSkipped).toBe(1);
    expect(msgs(r.ignored)).toMatch(/Excel error #DIV\/0!/);
    expect(msgs(r.ignored)).toMatch(/1 formula cell has no saved result/);
  });
  it("values in cells that do not apply are ignored, unknown / repeated headers are reported", () => {
    const i = msgs(r.ignored);
    expect(i).toMatch(/does not apply to Chapter Boss \(cell has "More Normal"\)/);
    expect(i).toMatch(/does not apply to PvP \(cell has "Whatever"\)/);
    expect(i).toMatch(/Column "Mystery Dungeon" is not a content type/);
    expect(i).toMatch(/Column "Chapter Boss" repeats a content type/);
    expect(r.state.perContent["PvP"].boss_normal_weight_choice ?? null).toBeNull();
  });
  it("only the content types present in the file are imported; the selected one falls back with a warning", () => {
    expect(Object.keys(r.state.perContent).sort()).toEqual(["Breakthrough", "Chapter Boss", "PvP"]);
    expect(r.state.contentType).toBe("Chapter Boss");
    expect(msgs(r.warnings)).toMatch(/selected content type "World Boss" has no values/);
    expect(r.state.perContent["PvP"].attack_pct).toBe(77);
    expect(r.state.perContent["PvP"].pvp_fight_length).toBe(30);
    expect(r.summary.valuesPerContent["PvP"]).toBe(2);
  });
});

describe("cube gear import details", () => {
  const { schema } = fixtureFor("fp_mage");
  const r = importWorkbook(open("class_fp_mage.xlsx"), schema);
  it("slot names resolve by id or label, in any case and separator", () => {
    expect(cubeSlotKey("eye-accessory")).toBe("eye-accessory");
    expect(cubeSlotKey("Eye accessory")).toBe("eye-accessory");
    expect(cubeSlotKey(" EYE_ACCESSORY ")).toBe("eye-accessory");
    expect(cubeSlotKey("Necklace")).toBe("neck");
    expect(cubeSlotKey("Ring 2")).toBe("ring2");
    expect(cubeSlotKey("Face accessory")).toBe("face");
    expect(cubeSlotKey("tail")).toBeNull();
  });
  it("only rows with something are stored; the others stay blank for the Cubes tab", () => {
    const keys = Object.keys(r.state.cubes!);
    expect(keys.length).toBeLessThan(30);
    const meta = cubesFixture().meta;
    expect(rowsToCalculate(meta, r.state.cubes, true)).toHaveLength(30);
    expect(rowsToCalculate(meta, r.state.cubes, false)).toHaveLength(keys.length);
    const blank = meta.slots.flatMap((s) => meta.potential_types.map((t) => [s.key, t] as const)).find(([s, t]) => !keys.includes(`${s}|${t}`))!;
    expect(getRow(r.state.cubes, blank[0], blank[1]).lines.every((l) => l.stat === "(none)")).toBe(true);
  });
  it("a workbook without the PotentialCubes sheet still imports, with one warning", () => {
    const r2 = importWorkbook(open("inputs_only_shadower.xlsx"), fixtureFor("shadower").schema);
    expect(r2.state.cubes).toBeUndefined();
    expect(r2.summary.cubesRead).toBe(false);
    expect(r2.warnings.map((w) => w.where)).toContain("PotentialCubes");
  });
  it("the planted pity above the cap is KEPT as typed (the engine clamps it) and the unknown stat leaves the line empty", () => {
    const rare = Object.values(r.state.cubes!).find((x) => x.rarity === "rare")!;
    expect(rare.pity).toBe(75);
    expect(rare.lines.filter((l) => l.stat === "(none)")).toHaveLength(1);
  });
});

describe("profile names", () => {
  const existing = [
    { name: "Excel import", state: { classId: "hero" } },
    { name: "Excel import (2)", state: { classId: "hero" } },
    { name: "Excel import", state: { classId: "bishop" } },
  ];
  it("never collides with a stored profile of the same class", () => {
    expect(uniqueProfileName("Excel import", existing, "hero")).toBe("Excel import (3)");
    expect(uniqueProfileName("Excel import", existing, "shadower")).toBe("Excel import");
    expect(uniqueProfileName("   ", [], "hero")).toBe("Excel import");
    expect(uniqueProfileName("x".repeat(80), [], "hero")).toHaveLength(60);
  });
});
