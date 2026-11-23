import { describe, expect, it } from "vitest";
import { cubesFixture } from "../test/cubesFixture";
import {
  NONE_STAT, SELECTABLE_MILESTONES, WORTH_MAYBE_PCT, WORTH_YES_PCT, blankRow, chunk, cubesCsv, evPctAt, formatCubes, formatEvPct, gearKey, gearPayload, getRow, isConfigured,
  linesText, normalizeCubesState, pityCap, pityCapsText, pityHint, potentialExplainer, groupByPotentialType, rankRows, rowsToCalculate, setLine, setRow, statChoices, statOptions, worthRolling, NOT_ROLLABLE_ON_ARTIFACTS, NOT_ROLLABLE_ON_SLOT,
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
    expect(worthRolling(row, 5).verdict).toBe("marginal"); // missing milestone reads as 0
    expect(worthRolling(row, 500).why).toContain("500 cubes");
    expect(worthRolling(row, 20).why).toContain("first positive EV after 3 cubes");
  });
  it("real engine rows: every row gets a verdict consistent with its fields at every selectable milestone", () => {
    for (const r of fx.cubes.result.rows) {
      for (const n of SELECTABLE_MILESTONES) {
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
  it("by expected gain (ties: fewer cubes first), by cubes to positive EV (never last), by sheet order", () => {
    expect(rankRows(rows, "ev", 100, meta).map((r) => r.slot)).toEqual(["head", "cape", "ring", "boots"]);
    expect(rankRows(rows, "smallest_n", 100, meta).map((r) => r.slot)).toEqual(["head", "cape", "ring", "boots"]);
    expect(rankRows(rows, "sheet", 100, meta).map((r) => r.slot)).toEqual(["head", "cape", "boots", "ring"]);
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
  it("CSV keeps the script's column order and the right number of cells", () => {
    const text = cubesCsv(fx.cubes.result.rows.slice(0, 2), meta.milestones, meta.csv_columns);
    const lines = text.trim().split("\n");
    expect(lines).toHaveLength(3);
    const header = lines[0].split(",");
    expect(header.slice(0, 9)).toEqual(["Slot", "PotentialType", "Rarity", "Pity", "CurrentValue", "CurrentValue%", "SmallestNPositive", "NFor50PctChance", "NFor75PctChance"]);
    expect(header).toHaveLength(57);
    expect(lines[1].split(",")).toHaveLength(57);
    expect(lines[1].split(",")[0]).toBe(fx.cubes.result.rows[0].slot);
    expect(Number(lines[1].split(",")[9])).toBeCloseTo(fx.cubes.result.rows[0].milestone_ev["5"], 6);
    expect(cubesCsv([mkRow({ smallest_n: null, slot: 'we"ird' })], [100], ["a"])).toContain('"we""ird"');
  });
});
