import { describe, expect, it } from "vitest";
import { cubesFixture } from "../test/cubesFixture";
import {
  NONE_STAT, DEFAULT_CUBE_COUNT, WORTH_MAYBE_PCT, WORTH_YES_PCT, blankRow, chunk, cubesCsv, evAt, evPctAt, formatCubes, formatEvPct, formatUntilPositive, parseCubeCount, typeCubeCount, effectiveCubeCount, initialCubeCount, gearKey, gearPayload, getRow, isConfigured,
  linesText, autoValue, lineWithStat, rollValueOptions, sanitizeLine, withRarity, STATIC_ROLL_VALUES, normalizeCubesState, pityCap, pityCapsText, pityHint, potentialExplainer, groupByPotentialType, rankRows, rowsToCalculate, setLine, setRow, statChoices, statOptions, worthRolling, NOT_ROLLABLE_ON_ARTIFACTS, NOT_ROLLABLE_ON_SLOT,
  type CubeRow, type CubesState,
} from "./cubes";

const fx = cubesFixture();
const meta = fx.meta;

const mkRow = (over: Partial<CubeRow> = {}, ev: Record<number, number> = {}): CubeRow => ({
  slot: "head", potential_type: "Potential", rarity: "epic", pity: 0, lines: [], current_value: 0, current_value_pct: 0, smallest_n: 3, n_for_50pct: 4, n_for_75pct: 9,
  milestone_ev: {}, milestone_ev_pct: Object.fromEntries(Object.entries(ev).map(([k, v]) => [k, v])), ...over,
});

describe("meta (real engine tables)", () => {
  it("15 slots x 2 tracks, 6 rarities, separate pity caps", () => {
    expect(meta.slots).toHaveLength(15);
    expect(meta.potential_types).toEqual(["Potential", "Bonus Potential"]);
    expect(meta.rarities.map((r) => r.key)).toEqual(["normal", "rare", "epic", "unique", "legendary", "mystic"]);
    expect(pityCap(meta, "Potential", "normal")).toBe(30);
    expect(pityCap(meta, "Bonus Potential", "normal")).toBe(42);
    expect(pityCap(meta, "Potential", "mystic")).toBe(0);
    expect(pityHint(meta, "Bonus Potential", "unique")).toBe("cap 417");
    expect(pityHint(meta, "Potential", "mystic")).toBe("top tier");
    expect(pityCap(null, "Potential", "normal")).toBe(0);
  });
  it("the pity text and the explainer come from the meta, with the crit-rate note", () => {
    expect(pityCapsText(meta)).toBe("Normal 30 / 42, Rare 60 / 75, Epic 120 / 150, Unique 333 / 417, Legendary 714");
    const text = potentialExplainer(meta).join(" ");
    expect(text).toContain("Normal 30 / 42");
    expect(text).toContain("Ring of Cycles");
    expect(text).toContain("Book of");
    expect(text).toContain("100%");
    expect(pityCapsText(null)).toBe("");
  });
  it("stat options: ONLY the stats the slot can roll (no 'other stats' tail)", () => {
    const boots = statOptions(meta, "boots");
    expect(boots).toContain("Companion Summoning Time Increase %");
    expect(statOptions(meta, "head")).not.toContain("Companion Summoning Time Increase %");
    expect(statOptions(meta, "head")).toEqual(meta.stats_by_slot.head);
    expect(statOptions(meta, "head").length).toBeLessThan(meta.stats.length);
    expect(new Set(statOptions(meta, "head")).size).toBe(statOptions(meta, "head").length);
    expect(statOptions(meta, "no-such-slot")).toEqual(meta.stats);                       // an unknown slot falls back to every stat
  });
  it("statChoices: (none) + the rollable stats; a current value outside them is kept as ONE flagged entry (only when asked for)", () => {
    const own = statOptions(meta, "head");
    const plain = statChoices(own, "Damage %", NOT_ROLLABLE_ON_SLOT);
    expect(plain.map((c) => c.value)).toEqual(["(none)", ...own]);
    expect(plain.some((c) => c.warn)).toBe(false);
    expect(statChoices(own, "(none)", NOT_ROLLABLE_ON_SLOT).map((c) => c.value)).toEqual(["(none)", ...own]);
    const odd = statChoices(own, "Companion Summoning Time Increase %", NOT_ROLLABLE_ON_SLOT);
    expect(odd).toHaveLength(own.length + 2);
    expect(odd[1]).toEqual({ value: "Companion Summoning Time Increase %", label: "\u26A0 Companion Summoning Time Increase % (not rollable on this slot)", warn: true });
    expect(odd.filter((c) => c.value === "Companion Summoning Time Increase %")).toHaveLength(1);
    // Equipment compare keeps its own plain behaviour: no flag, no suffix
    expect(statChoices(own, "Other", undefined)[1]).toEqual({ value: "Other", label: "Other" });
    expect(NOT_ROLLABLE_ON_ARTIFACTS).toContain("artifacts");
  });
});

describe("slot-exclusive stats", () => {
  it("Skill Cooldown Decrease is offered on the hat only, Buff Duration Increase on the belt only, Basic Attack Target Increase on the chest only", () => {
    const only = (stat: string) => meta.slots.map((s) => s.key).filter((k) => statOptions(meta, k).includes(stat));
    expect(only("Skill Cooldown Decrease (seconds)")).toEqual(["head"]);
    expect(only("Buff Duration Increase %")).toEqual(["belt"]);
    expect(only("Basic Attack Target Increase")).toEqual(["chest"]);
    expect(only("Companion Summoning Time Increase %")).toEqual(["boots"]);
    expect(meta.stats).toContain("Skill Cooldown Decrease (seconds)");                    // still a known stat (a stored line is recognised)
  });
  it("a stored line of one on another slot is kept as ONE flagged entry, not offered as a rollable one", () => {
    const own = statOptions(meta, "boots");
    const c = statChoices(own, "Skill Cooldown Decrease (seconds)", NOT_ROLLABLE_ON_SLOT);
    expect(c.filter((x) => x.value === "Skill Cooldown Decrease (seconds)")).toEqual([{ value: "Skill Cooldown Decrease (seconds)", label: "\u26A0 Skill Cooldown Decrease (seconds) (not rollable on this slot)", warn: true }]);
    expect(statChoices(statOptions(meta, "head"), "Skill Cooldown Decrease (seconds)", NOT_ROLLABLE_ON_SLOT).some((x) => x.warn)).toBe(false);
    expect(statChoices(statOptions(meta, "belt"), "Buff Duration Increase %", NOT_ROLLABLE_ON_SLOT).some((x) => x.warn)).toBe(false);
    expect(statChoices(statOptions(meta, "head"), "Buff Duration Increase %", NOT_ROLLABLE_ON_SLOT).some((x) => x.warn)).toBe(true);
  });
});

describe("line values: the dropdown lists exactly what the game rolls", () => {
  const vals = (slot: string, rarity: string, line: number, stat: string) => rollValueOptions(meta, slot, rarity, line, stat).map((o) => o.label);
  it("prime first, then descending, labelled with the plain number; line 1 of a rarity has one value", () => {
    expect(vals("head", "legendary", 1, "Critical Rate %")).toEqual(["12", "9"]);
    expect(vals("head", "legendary", 2, "Critical Rate %")).toEqual(["12", "9"]);
    expect(vals("head", "epic", 0, "Critical Rate %")).toEqual(["6"]);
    expect(vals("head", "legendary", 0, "Critical Rate %")).toEqual(["12"]);
    expect(rollValueOptions(meta, "head", "legendary", 1, "Critical Rate %").map((o) => o.prime)).toEqual([true, false]);   // the data's own prime flag decides the order
    for (const slot of meta.slots.map((s) => s.key)) {
      for (const o of meta.rarities.flatMap((r) => [0, 1, 2].flatMap((i) => meta.stats.map((st) => rollValueOptions(meta, slot, r.key, i, st))))) {
        for (const x of o) expect(x.label, "no '(prime)' / '(normal)' / '(custom)' text").toMatch(/^[0-9.]+$/);
      }
    }
    const o = rollValueOptions(meta, "head", "unique", 1, "Damage %");
    expect(o.map((x) => x.prime)).toEqual([...o.map((x) => x.prime)].sort((a, b) => Number(b) - Number(a)));
    for (const flag of [true, false]) {
      const part = o.filter((x) => x.prime === flag).map((x) => x.value);
      expect(part).toEqual([...part].sort((x, y) => y - x));                                       // descending inside prime / normal
    }
  });
  it("depends on slot, rarity, line position and stat; slot-only stats come from the slot's own table", () => {
    expect(vals("head", "epic", 0, "Skill Cooldown Decrease (seconds)")).toEqual(["0.5"]);
    expect(vals("head", "mystic", 1, "Skill Cooldown Decrease (seconds)")).toEqual(["2", "1.5"]);
    expect(vals("belt", "unique", 2, "Buff Duration Increase %")).toEqual(["8", "5"]);
    expect(vals("chest", "unique", 0, "Basic Attack Target Increase")).toEqual(["1"]);
    expect(vals("boots", "legendary", 0, "Companion Summoning Time Increase %")).toEqual(["12"]);
    // not rollable there: no table entry (the editor shows the stat without a value input)
    expect(vals("boots", "epic", 0, "Skill Cooldown Decrease (seconds)")).toEqual([]);
    expect(vals("chest", "epic", 0, "Basic Attack Target Increase")).toEqual([]);                  // the chest has no epic option
    expect(vals("head", "epic", 0, NONE_STAT)).toEqual([]);
    expect(vals("head", "epic", 0, "Damage %")).not.toEqual(vals("head", "mystic", 0, "Damage %"));
    expect(rollValueOptions(null, "head", "epic", 0, "Damage %")).toEqual(rollValueOptions(meta, "head", "epic", 0, "Damage %"));   // no meta: the shared tables
    expect(rollValueOptions({ ...meta, roll_values: undefined }, "head", "epic", 0, "Damage %")).toEqual(rollValueOptions(meta, "head", "epic", 0, "Damage %"));   // a meta without the tables uses the shared copy
    expect(meta.roll_values).toEqual(STATIC_ROLL_VALUES);                                              // the copy used by profile repair / the Excel import equals the API's tables
  });
  it("every stat a slot can roll has at least one value on a rarity and line where it rolls; values are unique per line", () => {
    for (const slot of meta.slots.map((s) => s.key)) {
      for (const stat of statOptions(meta, slot)) {
        const all = meta.rarities.flatMap((r) => [0, 1, 2].map((i) => rollValueOptions(meta, slot, r.key, i, stat)));
        expect(all.some((o) => o.length > 0), `${slot} / ${stat}`).toBe(true);
        for (const o of all) expect(new Set(o.map((x) => x.value)).size).toBe(o.length);
      }
    }
  });
  it("autoValue: the one prime option, else the only option, else blank", () => {
    expect(autoValue(rollValueOptions(meta, "head", "legendary", 1, "Critical Rate %"))).toBe(12);
    expect(autoValue(rollValueOptions(meta, "head", "legendary", 0, "Critical Rate %"))).toBe(12);       // single (non-prime) option
    expect(autoValue([])).toBeNull();
    const two = [{ value: 5, prime: false, label: "" }, { value: 4, prime: false, label: "" }];
    expect(autoValue(two)).toBeNull();
    expect(autoValue([{ value: 5, prime: true, label: "" }, { value: 6, prime: true, label: "" }])).toBeNull();
  });
  it("lineWithStat: choosing a stat auto-selects the prime value; '(none)' clears; a stat without a table entry gets no value", () => {
    const l = { stat: "Damage %", value: 7 };
    expect(lineWithStat(meta, "head", "legendary", 1, l, "Critical Rate %")).toEqual({ stat: "Critical Rate %", value: 12 });
    expect(lineWithStat(meta, "head", "legendary", 1, l, NONE_STAT)).toEqual({ stat: NONE_STAT, value: null });
    expect(lineWithStat(meta, "boots", "epic", 0, l, "Skill Cooldown Decrease (seconds)")).toEqual({ stat: "Skill Cooldown Decrease (seconds)", value: null });
    expect(lineWithStat(meta, "head", "legendary", 1, l, "Damage %").value).toBe(25);                // two values: the one prime value is picked
    expect(lineWithStat(meta, "head", "legendary", 0, l, "Damage %").value).toBe(25);                 // exactly one value: set at once
  });
  it("there is no custom value option any more", async () => {
    const mod = await import("./cubes");
    expect(Object.keys(mod)).not.toContain("customValueOption");
    expect(Object.keys(mod)).not.toContain("valueLabel");
  });
  it("sanitizeLine: a value outside the allowed values is cleared, a single allowed value is filled in, a stat with no table entry is left alone", () => {
    const rv = STATIC_ROLL_VALUES;
    expect(sanitizeLine(rv, "head", "legendary", 1, { stat: "Critical Rate %", value: 12.5 })).toEqual({ line: { stat: "Critical Rate %", value: null }, cleared: true });
    expect(sanitizeLine(rv, "head", "legendary", 1, { stat: "Critical Rate %", value: 9 })).toEqual({ line: { stat: "Critical Rate %", value: 9 }, cleared: false });
    expect(sanitizeLine(rv, "head", "legendary", 1, { stat: "Critical Rate %", value: null })).toEqual({ line: { stat: "Critical Rate %", value: null }, cleared: false });
    expect(sanitizeLine(rv, "head", "legendary", 0, { stat: "Critical Rate %", value: null })).toEqual({ line: { stat: "Critical Rate %", value: 12 }, cleared: false });
    expect(sanitizeLine(rv, "head", "legendary", 0, { stat: "Critical Rate %", value: 3 })).toEqual({ line: { stat: "Critical Rate %", value: 12 }, cleared: true });
    expect(sanitizeLine(rv, "boots", "epic", 0, { stat: "Skill Cooldown Decrease (seconds)", value: 0.5 })).toEqual({ line: { stat: "Skill Cooldown Decrease (seconds)", value: 0.5 }, cleared: false });
    expect(sanitizeLine(rv, "head", "epic", 0, { stat: NONE_STAT, value: 4 }).line).toEqual({ stat: NONE_STAT, value: null });
  });
  it("withRarity: another rarity empties all three lines (stat (none), value blank) and keeps the pity", () => {
    const row = { rarity: "epic", pity: 7, lines: [{ stat: "Damage %", value: 12 }, { stat: "Critical Rate %", value: 9 }, { stat: "Str %", value: 5 }] };
    const out = withRarity(row, "legendary");
    expect(out).toEqual({ rarity: "legendary", pity: 7, lines: [0, 1, 2].map(() => ({ stat: NONE_STAT, value: null })) });
    expect(row.lines[0].stat).toBe("Damage %");                                                      // immutable
  });
});

describe("gear state", () => {
  it("blank rows are not configured, any rarity / pity / line is", () => {
    expect(isConfigured(blankRow())).toBe(false);
    expect(isConfigured({ ...blankRow(), rarity: "epic" })).toBe(true);
    expect(isConfigured({ ...blankRow(), pity: 5 })).toBe(true);
    expect(isConfigured(setLine(blankRow(), 1, { stat: "Damage %", value: 4 }))).toBe(true);
  });
  it("setRow / getRow / setLine are immutable", () => {
    const s0: CubesState = {};
    const r = setLine(blankRow(), 0, { stat: "Damage %", value: 12 });
    const s1 = setRow(s0, "head", "Potential", r);
    expect(Object.keys(s0)).toEqual([]);
    expect(getRow(s1, "head", "Potential").lines[0]).toEqual({ stat: "Damage %", value: 12 });
    expect(getRow(s1, "head", "Bonus Potential")).toEqual(blankRow());
    expect(blankRow().lines[0]).toEqual({ stat: NONE_STAT, value: null });
  });
  it("normalizeCubesState repairs junk from stored / imported profiles", () => {
    expect(normalizeCubesState(null)).toEqual({});
    expect(normalizeCubesState([1])).toEqual({});
    const n = normalizeCubesState({
      "head|Potential": { rarity: "epic", pity: 3.7, lines: [{ stat: "Damage %", value: 12 }, { stat: 5, value: -1 }] },
      "bad key": { rarity: "epic" },
      "ring|Potential": "nope",
      "cape|Bonus Potential": { rarity: 7, pity: -2 },
    });
    expect(Object.keys(n).sort()).toEqual(["cape|Bonus Potential", "head|Potential"]);
    expect(n["head|Potential"]).toEqual({ rarity: "epic", pity: 3, lines: [{ stat: "Damage %", value: 12 }, { stat: NONE_STAT, value: null }, { stat: NONE_STAT, value: null }] });
    expect(n["cape|Bonus Potential"]).toEqual({ rarity: "normal", pity: null, lines: blankRow().lines });
  });
  it("normalizeCubesState clears a line value that is not allowed for (slot, rarity, line, stat) and keeps the stat; a single-value line is filled in", () => {
    const n = normalizeCubesState({
      "head|Potential": { rarity: "legendary", pity: 0, lines: [{ stat: "Critical Rate %", value: null }, { stat: "Critical Rate %", value: 12.5 }, { stat: "Critical Rate %", value: 9 }] },
      "boots|Potential": { rarity: "epic", pity: 0, lines: [{ stat: "Skill Cooldown Decrease (seconds)", value: 0.5 }, { stat: NONE_STAT, value: null }, { stat: NONE_STAT, value: null }] },
    });
    expect(n["head|Potential"].lines).toEqual([{ stat: "Critical Rate %", value: 12 }, { stat: "Critical Rate %", value: null }, { stat: "Critical Rate %", value: 9 }]);
    expect(n["boots|Potential"].lines[0]).toEqual({ stat: "Skill Cooldown Decrease (seconds)", value: 0.5 });   // no roll entry: kept as before
    expect(normalizeCubesState(n)).toEqual(n);                                                          // idempotent
  });
  const state: CubesState = {
    [gearKey("head", "Potential")]: { rarity: "epic", pity: 12, lines: [{ stat: "Damage %", value: 12 }, { stat: NONE_STAT, value: 7 }, { stat: "Critical Rate %", value: null }] },
    [gearKey("boots", "Bonus Potential")]: { rarity: "unique", pity: null, lines: [{ stat: "Companion Summoning Time Increase %", value: 8 }, emptyL(), emptyL()] },
  };
  function emptyL() {
    return { stat: NONE_STAT, value: null };
  }
  it("rowsToCalculate: configured rows in sheet order, or all 30", () => {
    expect(rowsToCalculate(meta, state, false)).toEqual([
      { slot: "head", potential_type: "Potential" },
      { slot: "boots", potential_type: "Bonus Potential" },
    ]);
    expect(rowsToCalculate(meta, state, true)).toHaveLength(30);
    expect(rowsToCalculate(meta, undefined, false)).toEqual([]);
  });
  it("gearPayload: only configured rows, '(none)' lines dropped, blanks as 0, whole pity", () => {
    const g = gearPayload(meta, state);
    expect(g).toEqual([
      { slot: "head", potential_type: "Potential", rarity: "epic", pity: 12, lines: [{ stat: "Damage %", value: 12 }, { stat: "Critical Rate %", value: 0 }] },
      { slot: "boots", potential_type: "Bonus Potential", rarity: "unique", pity: 0, lines: [{ stat: "Companion Summoning Time Increase %", value: 8 }] },
    ]);
  });
  it("chunk", () => {
    expect(chunk([1, 2, 3, 4, 5], 2)).toEqual([[1, 2], [3, 4], [5]]);
    expect(chunk([], 3)).toEqual([]);
    expect(chunk([1, 2], 0)).toEqual([[1], [2]]);
  });
});

describe("worth rolling? rule", () => {
  it("never positive -> No whatever the EV", () => {
    expect(worthRolling(mkRow({ smallest_n: null }, { 100: 50 }), 100).verdict).toBe("no");
  });
  it("thresholds on EV% at the chosen cube count", () => {
    const row = mkRow({}, { 20: 0.05, 100: WORTH_MAYBE_PCT, 500: WORTH_YES_PCT, 1000: 12 });
    expect(worthRolling(row, 20).verdict).toBe("marginal");
    expect(worthRolling(row, 100).verdict).toBe("maybe");
    expect(worthRolling(row, 500).verdict).toBe("yes");
    expect(worthRolling(row, 1000).verdict).toBe("yes");
    expect(worthRolling(row, 5).verdict).toBe("marginal"); // below the first milestone reads as 0
    expect(worthRolling(row, 86).verdict).toBe("marginal"); // no per-count curve: the largest milestone not above 86 (20) is used
    expect(worthRolling(row, 499).verdict).toBe("maybe"); // ... 100, never an optimistic later one
    expect(worthRolling(row, 500).why).toContain("500 cubes");
    expect(worthRolling(row, 20).why).toContain("first positive gain comes after 3 cubes");
  });
  it("real engine rows: every row gets a verdict consistent with its fields at preset and in-between cube counts", () => {
    for (const r of fx.cubes.result.rows) {
      for (const n of [1, 5, 20, 50, 86, 100, 200, 500, 1000]) {
        const w = worthRolling(r, n);
        if (r.smallest_n === null) expect(w.verdict).toBe("no");
        else expect(w.verdict).toBe(evPctAt(r, n) >= WORTH_YES_PCT ? "yes" : evPctAt(r, n) >= WORTH_MAYBE_PCT ? "maybe" : "marginal");
      }
    }
  });
});

describe("ranking and formatting", () => {
  const rows = [
    mkRow({ slot: "ring", smallest_n: 7 }, { 100: 1 }),
    mkRow({ slot: "head", smallest_n: 2 }, { 100: 3 }),
    mkRow({ slot: "boots", potential_type: "Bonus Potential", smallest_n: null }, { 100: 0 }),
    mkRow({ slot: "cape", smallest_n: 2 }, { 100: 3 }),
  ];
  it("by expected gain (ties: fewer cubes first), by cubes to positive EV (never last), by slot order", () => {
    expect(rankRows(rows, "ev", 100, meta).map((r) => r.slot)).toEqual(["head", "cape", "ring", "boots"]);
    expect(rankRows(rows, "smallest_n", 100, meta).map((r) => r.slot)).toEqual(["head", "cape", "ring", "boots"]);
    expect(rankRows(rows, "slot", 100, meta).map((r) => r.slot)).toEqual(["head", "cape", "boots", "ring"]);
    const copy = [...rows];
    rankRows(rows, "ev", 100, meta);
    expect(rows).toEqual(copy); // input untouched
  });
  it("groups the ranking by roll track (Potential first, then Bonus Potential), keeping the order inside each", () => {
    const g = groupByPotentialType(rankRows(rows, "ev", 100, meta));
    expect(g.map((x) => x.type)).toEqual(["Potential", "Bonus Potential"]);
    expect(g[0].rows.map((r) => r.slot)).toEqual(["head", "cape", "ring"]);
    expect(g[1].rows.map((r) => r.slot)).toEqual(["boots"]);
    expect(groupByPotentialType(rows.filter((r) => r.potential_type === "Potential")).map((x) => x.type)).toEqual(["Potential"]);
    expect(groupByPotentialType([])).toEqual([]);
  });
  it("formatters", () => {
    expect(formatCubes(null)).toBe("> 1000");
    expect(formatUntilPositive(null)).toBe("never (already near the best)");
    expect(formatUntilPositive(7)).toBe("7");
    expect(formatCubes(12)).toBe("12");
    expect(formatEvPct(2.345)).toBe("+2.35%");
    expect(formatEvPct(25.55)).toBe("+25.6%");
    expect(formatEvPct(0.0123)).toBe("+0.012%");
    expect(formatEvPct(0)).toBe("0%");
    expect(formatEvPct(-1.5)).toBe("-1.50%");
    expect(formatEvPct(NaN)).toBe("–");
    expect(linesText(mkRow({ lines: [["Damage %", 12], [NONE_STAT, 0]] }))).toBe("Damage % 12");
    expect(linesText(mkRow({ lines: [] }))).toBe("no lines");
  });
  it("CSV keeps the preset-milestone % columns (no absolute DPS columns) and the right number of cells, also for rows with the full per-count curve", () => {
    const text = cubesCsv(fx.cubes.result.rows.slice(0, 2), meta.milestones, meta.csv_columns);
    const lines = text.trim().split("\n");
    expect(lines).toHaveLength(3);
    const header = lines[0].split(",");
    const nCols = meta.csv_columns.length - 1 - meta.milestones.length; // without CurrentValue and the EV@n columns
    expect(header.slice(0, 8)).toEqual(["Slot", "PotentialType", "Rarity", "Pity", "CurrentValue%", "SmallestNPositive", "NFor50PctChance", "NFor75PctChance"]);
    expect(header).toHaveLength(nCols);
    expect(header.some((h) => h === "CurrentValue" || h.startsWith("EV@"))).toBe(false);
    expect(lines[1].split(",")).toHaveLength(nCols);
    expect(lines[1].split(",")[0]).toBe(fx.cubes.result.rows[0].slot);
    expect(Number(lines[1].split(",")[8])).toBeCloseTo(fx.cubes.result.rows[0].milestone_ev_pct["5"], 6);
    expect(cubesCsv([mkRow({ smallest_n: null, slot: 'we"ird' })], [100], ["a"])).toContain('"we""ird"');
  });
});

describe("the exact cube count", () => {
  it("parseCubeCount: whole numbers 1..max (typing like 86 or 1,000 works); blank, decimals, text and out-of-range give a message", () => {
    expect(DEFAULT_CUBE_COUNT).toBe(100);
    for (const [text, value] of [["86", 86], [" 86 ", 86], ["1", 1], ["1000", 1000], ["1,000", 1000], ["007", 7]] as const) expect(parseCubeCount(text)).toEqual({ value, error: null });
    expect(parseCubeCount("86", 50).value).toBeNull();
    expect(parseCubeCount("50", 50).value).toBe(50);
    for (const bad of ["", "   ", "0", "1001", "-5", "abc", "1e2", "8 6", "+5"]) {
      const r = parseCubeCount(bad);
      expect(r.value, bad).toBeNull();
      expect(r.error, bad).toBe("Enter a whole number of cubes from 1 to 1000");
    }
    expect(parseCubeCount("86.5").value).toBeNull();
    expect(parseCubeCount("86.5").error).toContain("Whole cubes only");
    expect(parseCubeCount("2000", 1500).error).toBe("Enter a whole number of cubes from 1 to 1500");
  });
  it("the box keeps the last valid count while the text is invalid (typing 86 -> 8 -> '' -> 86.5 -> 90)", () => {
    let c = initialCubeCount();
    expect(c).toEqual({ text: "100", good: 100 });
    expect(effectiveCubeCount(c)).toBe(100);
    c = typeCubeCount(c, "8");
    c = typeCubeCount(c, "86");
    expect(effectiveCubeCount(c)).toBe(86);
    for (const bad of ["", "86.5", "abc", "0", "1001"]) {
      c = typeCubeCount(c, bad);
      expect(c.text).toBe(bad);
      expect(effectiveCubeCount(c), bad).toBe(86); // still priced for the last good count
    }
    c = typeCubeCount(c, "90");
    expect(effectiveCubeCount(c)).toBe(90);
    expect(effectiveCubeCount({ text: "", good: 800 }, 500)).toBe(500); // never above the maximum
    expect(typeCubeCount(initialCubeCount(), "600", 500)).toEqual({ text: "600", good: 100 });
  });
  // two rows whose order flips between 85 and 100 cubes: A grows steadily, B grows faster but stops at 85 cubes
  const curve = (f: (n: number) => number) => Array.from({ length: 1001 }, (_v, n) => f(n));
  const withCurve = (slot: string, f: (n: number) => number): CubeRow => {
    const c = curve(f);
    const ms = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 60, 70, 80, 90, 100, 125, 150, 175, 200, 250, 300, 400, 500, 1000];
    return mkRow({ slot, ev_pct_by_cubes: c, milestone_ev_pct: Object.fromEntries(ms.map((n) => [String(n), c[n]])), milestone_ev: Object.fromEntries(ms.map((n) => [String(n), c[n] * 100])) });
  };
  const A = withCurve("head", (n) => n * 0.01);
  const B = withCurve("cape", (n) => Math.min(n, 85) * 0.0115);
  it("evPctAt reads the per-count curve (any n), clamps beyond its end, falls back to the preset milestones without it", () => {
    expect(evPctAt(A, 86)).toBeCloseTo(0.86, 12);
    expect(evPctAt(A, 0)).toBe(0);
    expect(evPctAt(A, 5000)).toBeCloseTo(10, 12);
    expect(evPctAt(B, 86)).toBeCloseTo(85 * 0.0115, 12);
    const { ev_pct_by_cubes: _drop, ...plain } = A;
    expect(evPctAt(plain as CubeRow, 86)).toBeCloseTo(0.8, 12);       // largest preset milestone not above 86 = 80
    expect(evPctAt(plain as CubeRow, 100)).toBeCloseTo(1, 12);
    expect(evPctAt(plain as CubeRow, 3)).toBe(0);
  });
  it("evAt: DPS from the % and the baseline Total DPS (curve), else the milestone value", () => {
    expect(evAt(A, 86, 2_000_000)).toBeCloseTo(0.86 / 100 * 2_000_000, 6);
    const { ev_pct_by_cubes: _drop, ...plain } = A;
    expect(evAt(plain as CubeRow, 86)).toBeCloseTo(80, 9);            // milestone_ev of 80 cubes (this fixture stores pct x 100)
    expect(evAt(A, 86)).toBeCloseTo(80, 9);                           // no baseline: also the milestone value
  });
  it("re-ranks at the typed count: at 86 cubes B leads, at 100 A leads; the verdict follows the same count", () => {
    const at = (n: number) => rankRows([A, B], "ev", n, meta).map((r) => r.slot);
    expect(at(86)).toEqual(["cape", "head"]);
    expect(at(85)).toEqual(["cape", "head"]);
    expect(at(100)).toEqual(["head", "cape"]);
    expect(worthRolling(A, 86).verdict).toBe("maybe");                 // 0.86% is between 0.1 and 1
    expect(worthRolling(A, 100).verdict).toBe("yes");                  // 1.00% reaches the rule's 1%
    expect(worthRolling(B, 86).why).toContain("after 86 cubes");
    // the same ranking from rows WITHOUT the curve uses the milestone floor (80 cubes): still a valid, conservative answer
    const [a, b] = [A, B].map(({ ev_pct_by_cubes: _d, ...r }) => r as CubeRow);
    expect(rankRows([a, b], "ev", 86, meta).map((r) => r.slot)).toEqual(["cape", "head"]);
  });
  it("CSV columns stay the preset milestones even when the row has the curve", () => {
    const text = cubesCsv([A], meta.milestones, meta.csv_columns).trim().split("\n");
    const cells = text[1].split(",");
    const header = text[0].split(",");
    const i = header.indexOf("EV%@100");
    expect(Number(cells[i])).toBeCloseTo(1, 12);
    expect(cells).toHaveLength(meta.csv_columns.length - 1 - meta.milestones.length);
  });
  it("the real FP-Mage fixture rows carry ev_pct_by_cubes: length 1001, equal to the milestone % at every preset milestone", () => {
    for (const r of fx.cubes.result.rows) {
      const c = r.ev_pct_by_cubes!;
      expect(c).toHaveLength(1001);
      expect(c[0]).toBe(0);
      for (const n of meta.milestones) expect(c[n]).toBeCloseTo(r.milestone_ev_pct[String(n)], 4);
      expect(evPctAt(r, 86)).toBeGreaterThanOrEqual(evPctAt(r, 80));
      expect(evPctAt(r, 86)).toBeLessThanOrEqual(evPctAt(r, 90));
    }
  });
});
