import { describe, expect, it } from "vitest";
import { cubesFixture } from "../test/cubesFixture";
import { ALL, fixtureFor } from "../test/fixtures";
import { DEFAULT_LINE_RARITY, NO_STAT, lineCount } from "./artifacts";
import { NONE_STAT } from "./cubes";
import { computePotentials, lineKnown, lineUnlockStar, lineValue, normalizePotentials, potentialTables, potentialsRequest, resolveStar, STATIC_POTENTIAL_TABLES } from "./artifactPotentials";
import { emptyArtifacts, setLine } from "./artifacts";
import type { ArtifactSchema } from "../types";

const fx = cubesFixture();
const pm = fx.meta.artifact_potentials;
const close = (a: number, b: number) => expect(Math.abs(a - b)).toBeLessThanOrEqual(1e-9 * Math.max(1, Math.abs(b)));

describe("potential port == the real engine (fixture)", () => {
  const slots: { key: string; star: number }[] = []; // the fixture case equips nothing (its stars come from the request)
  const rows = computePotentials(pm, fx.potentials.request.potentials, fx.potentials.rate_by_stat, fx.potentials.result.baseline_total, slots);
  it("every artifact, every line", () => {
    expect(rows).toHaveLength(fx.potentials.result.rows.length);
    expect(rows.length).toBeGreaterThanOrEqual(36);
    fx.potentials.result.rows.forEach((e, i) => {
      const r = rows[i];
      expect(r.key).toBe(e.key);
      expect(r.star).toBe(e.star);
      expect(r.equipped).toBe(e.equipped);
      close(r.total, e.total);
      expect(r.lines).toHaveLength(e.lines.length);
      r.lines.forEach((l, j) => {
        expect(l.active).toBe(e.lines[j].active);
        close(l.gain, e.lines[j].gain);
      });
    });
    expect(rows.find((r) => r.key === "book_of_ancient")!.total).toBeGreaterThan(0);
  });
  it("star gating: locked lines are worth 0, an equipped artifact takes its slot's star", () => {
    const state = { book_of_ancient: { lines: [{ rarity: "Legendary", stat: "Damage %" }, { rarity: "Legendary", stat: "Damage %" }] } };
    const base = (star: number | string) => computePotentials(pm, state, fx.potentials.rate_by_stat, 1e6, [{ key: "book_of_ancient", star }]).find((r) => r.key === "book_of_ancient")!;
    expect(base("Not Unlocked").total).toBe(0);
    expect(base(0).lines.map((l) => l.active)).toEqual([false, false, false]);
    expect(base(1).lines.map((l) => l.active)).toEqual([true, false, false]);
    expect(base(2).lines.map((l) => l.active)).toEqual([true, true, false]);
    expect(base(5).lines.map((l) => l.active)).toEqual([true, true, true]);
    expect(base(2).total).toBeGreaterThan(base(1).total);
    expect(base(5).star).toBe(5);
  });
});

describe("potential state", () => {
  it("helpers", () => {
    expect(resolveStar("Not Unlocked")).toBe(0);
    expect(resolveStar(null)).toBe(0);
    expect(resolveStar(undefined)).toBe(0);
    expect(resolveStar(4)).toBe(4);
    expect(pm.line_min_star).toEqual([1, 2, 5]);
    expect(lineUnlockStar(pm, 2)).toBe(5);
    expect(lineValue(pm, "Damage %", "Legendary")).toBe(14);
    expect(lineValue(pm, "Nope", "Legendary")).toBe(0);
    expect(new Set(pm.artifacts.map((a) => a.lines))).toEqual(new Set([2, 3]));
  });
  it("the app's static tables equal the API's cube meta (all classes that have one): the dropdowns work before the meta arrives", () => {
    const { artifact_potentials: m } = fx.meta;
    expect(STATIC_POTENTIAL_TABLES).toEqual({ rarities: m.rarities, stats: m.stats, values: m.values, line_min_star: m.line_min_star, default_rarity: m.default_rarity, none_stat: m.none_stat });
    expect(potentialTables(null)).toBe(STATIC_POTENTIAL_TABLES);
    expect(potentialTables(fx.meta)).toBe(fx.meta.artifact_potentials);
    expect(NO_STAT).toBe(NONE_STAT);                                   // artifacts.ts keeps its own copy (no import cycle): they must agree
    expect(DEFAULT_LINE_RARITY).toBe(m.default_rarity);
  });
  it("the line count of every artifact (rank rule) equals the meta's", () => {
    const art = fixtureFor("fp_mage").schema.artifacts as ArtifactSchema;
    for (const a of pm.artifacts) {
      expect(lineCount(art.artifacts.find((x) => x.key === a.key)), a.key).toBe(a.lines);
      expect(art.artifacts.find((x) => x.key === a.key)!.rank).toBe(a.rank);
    }
    expect(pm.artifacts.map((a) => a.key)).toEqual(art.artifacts.map((a) => a.key));          // the table's order = the sheet's order
  });
  it("request body from the table: see ArtifactsPanel.test.tsx; unknown lines are sent as (none) and flagged", () => {
    const art = fixtureFor("fp_mage").schema.artifacts as ArtifactSchema;
    const t = setLine(art, emptyArtifacts(art), "candle", 0, { rarity: "Rare", stat: "Final Damage %" });
    expect(lineKnown(STATIC_POTENTIAL_TABLES, t.candle.lines[0])).toBe(false);
    expect(lineKnown(STATIC_POTENTIAL_TABLES, { rarity: "Rare", stat: "Damage %" })).toBe(true);
    expect(lineKnown(STATIC_POTENTIAL_TABLES, { rarity: "Rare", stat: NONE_STAT })).toBe(true);
    expect(potentialsRequest(art, t, STATIC_POTENTIAL_TABLES)).toEqual({});
  });
  it("every class that has a cube meta has the same potential tables (class independent)", () => {
    for (const c of ALL.filter((x) => x.info.status?.stat_values)) {
      const m = cubesFixture(c.info.id).meta.artifact_potentials;
      expect(m.values, c.info.id).toEqual(STATIC_POTENTIAL_TABLES.values);
      expect(m.stats, c.info.id).toEqual(STATIC_POTENTIAL_TABLES.stats);
    }
  });
  it("normalizePotentials (the OLD per-artifact state, kept for migration) repairs stored junk and keeps line positions", () => {
    expect(normalizePotentials(undefined)).toEqual({});
    const n = normalizePotentials({ book_of_ancient: { star: 2, lines: [{ rarity: "Epic", stat: "Damage %" }, { rarity: 1 }, null, {}, {}] }, "Bad Key": {}, x: 5 });
    expect(n).toEqual({ book_of_ancient: { star: 2, lines: [{ rarity: "Epic", stat: "Damage %" }, { rarity: "Rare", stat: "(none)" }, { rarity: "Rare", stat: "(none)" }] } });
  });
});
