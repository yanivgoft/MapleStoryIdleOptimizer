import { describe, expect, it } from "vitest";
import {
  formatStatValue,
  formatUnits,
  gainPct,
  hasValue,
  loadedParts,
  mergeResult,
  missingParts,
  rankEquip,
  relativeValues,
  sensitivityBody,
  signedPct,
  sig,
  sortCompanions,
  statFlags,
  statLabel,
  type ArtifactRow,
  type CompanionRow,
  type SensitivityResult,
  type StatRow,
} from "./sensitivity";
import { sensFixture } from "../test/sensFixture";

const stat = (key: string, units: number | null, over: Partial<StatRow> = {}): StatRow => ({
  key, label: key.toUpperCase(), type: "pct", current: 10, new: 11, baseline_total: 1000, new_total: 1010,
  dps_gain: 10, pct_gain: units === null ? 100 : 100 + 1 / units, units_per_1pct: units, boss_ratio: 1, normal_ratio: 1,
  semantics: null, strip_reused: true, summon_time_pinned: true, ...over,
});
const art = (key: string, over: Partial<ArtifactRow> = {}): ArtifactRow => ({
  key, label: key, rank: "Epic", effect: "live", no_dps_effect: false, reason: null, equipped: false, star: 5, unlocked: true, potential_gain: 0,
  baked_into_inputs: false, new_total: 0, ratio: 1, dps_gain: 0, pct_gain: 100, rank_position: null, ...over,
});

describe("formatting", () => {
  it("units per +1%: significant digits, n/a for null / non-positive", () => {
    expect(formatUnits(49.9975)).toBe("50");
    expect(formatUnits(0.999999)).toBe("1");
    expect(formatUnits(0.0123456)).toBe("0.0123");
    expect(formatUnits(1234.5)).toBe("1,235");
    expect(formatUnits(2.5e6)).toBe("2.5M");
    expect(formatUnits(null)).toBe("n/a");
    expect(formatUnits(-3)).toBe("n/a");
    expect(formatUnits(0)).toBe("n/a");
    expect(sig(0)).toBe("0");
  });
  it("signed percentages and gains from the '100 + gain' convention", () => {
    expect(gainPct(105.94)).toBe("+5.94%");
    expect(gainPct(100.02)).toBe("+0.020%");
    expect(gainPct(99.5)).toBe("−0.50%");
    expect(gainPct(100)).toBe("0%");
    expect(gainPct(236.15)).toBe("+136%");
    expect(signedPct(12.345)).toBe("+12.3%");
    expect(signedPct(0.0001)).toBe("≈0%");
    expect(signedPct(null)).toBe("–");
  });
  it("stat values", () => {
    expect(formatStatValue(55.5)).toBe("55.5");
    expect(formatStatValue(1.0000000000000064)).toBe("1");
    expect(formatStatValue(1209199)).toBe("1.209M");
    expect(formatStatValue(null)).toBe("–");
  });
});

describe("stat values", () => {
  const rows = [stat("a", 50), stat("b", null), stat("c", 1), stat("d", 5), stat("e", null), stat("f", 20)];
  it("a stat that lowers DPS (negative units) has no value", () => {
    const harmful = stat("h", -2, { pct_gain: 99.5 });
    expect(hasValue(harmful)).toBe(false);
    expect(hasValue(stat("x", 9))).toBe(true);
  });
  it("relative bar lengths: best = 1, proportional, none = 0", () => {
    const rel = relativeValues(rows);
    expect(rel.get("c")).toBe(1);
    expect(rel.get("d")).toBeCloseTo(0.2, 12);
    expect(rel.get("a")).toBeCloseTo(0.02, 12);
    expect(rel.get("b")).toBe(0);
    expect(relativeValues([stat("n", null)]).get("n")).toBe(0);
  });
  it("flags only mean something when other rows show the timeline / pin is in use", () => {
    const all = [stat("a", 1), stat("b", 2, { strip_reused: false, summon_time_pinned: false })];
    expect(statFlags(all[0], all)).toEqual([]);
    expect(statFlags(all[1], all)).toEqual(["timing re-run", "summon time re-searched"]);
    const none = [stat("a", 1, { strip_reused: false, summon_time_pinned: false })];
    expect(statFlags(none[0], none)).toEqual([]);
  });
});

describe("equip ranking", () => {
  const rows = [
    art("locked1", { unlocked: false, pct_gain: 150 }),
    art("noeff", { no_dps_effect: true, reason: "stat not used" }),
    art("second", { pct_gain: 105, rank_position: 2 }),
    art("first", { pct_gain: 120, rank_position: 1, equipped: true }),
    art("third", { pct_gain: 101, rank_position: 3 }),
    art("noeff2", { no_dps_effect: true }),
    art("locked2", { unlocked: false }),
  ];
  it("ranked first by rank_position, then no-effect, then locked", () => {
    expect(rankEquip(rows).map((e) => `${e.group}:${e.row.key}`)).toEqual([
      "ranked:first", "ranked:second", "ranked:third", "no_effect:noeff", "no_effect:noeff2", "locked:locked1", "locked:locked2",
    ]);
  });
  it("options drop groups", () => {
    expect(rankEquip(rows, { includeLocked: false }).map((e) => e.row.key)).toEqual(["first", "second", "third", "noeff", "noeff2"]);
    expect(rankEquip(rows, { includeLocked: false, includeNoEffect: false }).map((e) => e.row.key)).toEqual(["first", "second", "third"]);
  });
});

describe("companions", () => {
  it("best first, level-0 companions last", () => {
    const c = (name: string, unlocked: boolean, rank: number | null): CompanionRow => ({
      name, level: unlocked ? 10 : 0, unlocked, dps_gain: 0, pct_gain: 100, companion_dps: 0, companion_boss_dps: 0, companion_normal_dps: 0, rank_position: rank,
    });
    expect(sortCompanions([c("a", false, null), c("b", true, 2), c("c", true, 1)]).map((r) => r.name)).toEqual(["c", "b", "a"]);
  });
});

describe("lazy loading plan", () => {
  it("only the wanted parts that are not loaded yet, canonical order", () => {
    expect(missingParts([], ["stats"])).toEqual(["stats"]);
    expect(missingParts(["stats"], ["cdr", "stats", "artifacts"])).toEqual(["artifacts", "cdr"]);
    expect(missingParts(["stats", "cdr"], ["stats", "cdr"])).toEqual([]);
  });
  it("loaded parts and merge", () => {
    const base = { class_id: "x", content_type: "World Boss", baseline_total: 1, baseline_boss_total: 1, baseline_normal_total: 1, normal_weight: 0, semantics: "workbook" };
    const a = { ...base, stats: { rows: [] } } as unknown as SensitivityResult;
    const b = { ...base, cdr: { rows: [] } } as unknown as SensitivityResult;
    expect(loadedParts(a)).toEqual(["stats"]);
    expect(loadedParts(mergeResult(a, b))).toEqual(["stats", "cdr"]);
    expect(mergeResult(null, b)).toBe(b);
    expect(loadedParts(null)).toEqual([]);
  });
  it("request body = inputs + which", () => {
    expect(sensitivityBody({ level: 140 }, ["stats"])).toEqual({ level: 140, which: ["stats"] });
  });
});

describe("the real FP-Mage fixture (dumped from the engine through the API)", () => {
  const fx = sensFixture();
  it("27 stats, 36 artifacts, 16 companions; every row has the fields the table reads", () => {
    expect(fx.result.stats!.rows).toHaveLength(27);
    expect(fx.result.artifacts!.rows).toHaveLength(36);
    expect(fx.result.companions!.rows).toHaveLength(16);
    expect(fx.meta.stats.map((s) => s.key)).toEqual(fx.result.stats!.rows.map((r) => r.key));
    for (const r of fx.result.stats!.rows) {
      expect(Number.isFinite(r.pct_gain) && Number.isFinite(r.dps_gain)).toBe(true);
      expect(r.units_per_1pct === null || Number.isFinite(r.units_per_1pct)).toBe(true);
    }
  });
  it("equip ranking agrees with the engine's own ranking", () => {
    const ranked = rankEquip(fx.result.artifacts!.rows).filter((e) => e.group === "ranked").map((e) => e.row);
    const engine = fx.result.artifacts!.ranking.filter((k) => !fx.result.artifacts!.rows.find((r) => r.key === k)!.no_dps_effect);
    expect(ranked.map((r) => r.key)).toEqual(engine);
  });
});

describe("statLabel: the engine label without its explanatory tail", () => {
  it.each([
    ["ATTACK_SPEED % (diminishing returns, factor 150)", "Attack Speed %"],
    ["DEF_PEN % (diminishing returns, factor 100)", "Defense Penetration %"],
    ["FINAL_DAMAGE % (multiplicative source)", "Final Damage %"],
    ["BOSS_DAMAGE %", "Boss Damage %"],
    ["ATTACK %", "Attack %"],
    ["DEX %", "DEX %"],
    ["LUK", "LUK"],
    ["Flat ATTACK", "Flat ATTACK"],
    ["Skill Level Bonus — 1st Job", "Skill Level Bonus — 1st Job"],
    ["Defense (flat) — Iron Wall converts a level-scaling % (10%+) into STR", "Defense"],
    ["Incoming Hit Rate (hits/sec, Shadow Shifter only)", "Incoming Hit Rate"],
    ["Skill Cooldown Decrease (seconds)", "Skill Cooldown Decrease (s)"],
    ["Basic Attack Target Increase (flat)", "Basic Attack Target Increase"],
  ])("%s -> %s", (raw, shown) => expect(statLabel(raw)).toBe(shown));
});
