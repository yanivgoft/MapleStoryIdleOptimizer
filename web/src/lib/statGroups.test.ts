import { describe, expect, it } from "vitest";
import { STAT_GROUPS, OTHER_GROUP, groupStats, groupedStatChoices } from "./statGroups";
import { NONE_STAT, NOT_ROLLABLE_ON_SLOT, statOptions, type CubesMeta } from "./cubes";
import { STATIC_POTENTIAL_TABLES } from "./artifactPotentials";

// every cube meta fixture (one per class; the tables are class independent but each is checked)
const files = import.meta.glob("../fixtures/*.cubes_meta.json", { eager: true, import: "default" }) as Record<string, CubesMeta>;
const metas = Object.values(files);

/** every stat name a dropdown can offer anywhere: cube lines (all and per slot), Equipment compare, artifact potential lines (meta and the shipped static copy) */
const realStats = (): string[] => {
  const out = new Set<string>(STATIC_POTENTIAL_TABLES.stats);
  for (const m of metas) {
    for (const s of [...m.stats, ...m.equipment.stats, ...m.artifact_potentials.stats, ...Object.values(m.stats_by_slot).flat()]) out.add(s);
  }
  return [...out];
};

describe("stat groups: one definition for the cube lines, the artifact potential lines and Equipment compare", () => {
  it("has fixtures to check", () => {
    expect(metas.length).toBeGreaterThanOrEqual(12);
  });
  it("no real stat falls into 'Other' (a new stat forces a decision in statGroups.ts)", () => {
    const stats = realStats();
    expect(stats.length).toBeGreaterThan(40);
    const other = groupStats(stats).find((g) => g.label === OTHER_GROUP);
    expect(other?.stats ?? []).toEqual([]);
  });
  it("a stat is listed in ONE group only, and group labels are unique", () => {
    const all = STAT_GROUPS.flatMap((g) => g.stats);
    expect(new Set(all).size).toBe(all.length);
    expect(new Set(STAT_GROUPS.map((g) => g.label)).size).toBe(STAT_GROUPS.length);
    expect(STAT_GROUPS.map((g) => g.label)).not.toContain(OTHER_GROUP);
  });
  it("every stat of every slot (and of each editor's list) appears exactly once, in the fixed group order", () => {
    const labels = STAT_GROUPS.map((g) => g.label);
    for (const m of metas) {
      const lists = [m.stats, m.equipment.stats, m.artifact_potentials.stats, ...m.slots.map((s) => statOptions(m, s.key))];
      for (const list of lists) {
        const groups = groupStats(list);
        const flat = groups.flatMap((g) => g.stats);
        expect([...flat].sort()).toEqual([...list].sort());
        expect(new Set(flat).size).toBe(flat.length);
        const idx = groups.map((g) => labels.indexOf(g.label));
        expect(idx).toEqual([...idx].sort((a, b) => a - b));            // groups come in the defined order
        expect(groups.every((g) => g.stats.length > 0)).toBe(true);     // empty groups are left out
      }
    }
  });
  it("order: main stat % first, then flat, scaling, critical, damage, attack, skills / utility, defense; STR% DEX% INT% LUK% together", () => {
    expect(STAT_GROUPS.map((g) => g.label)).toEqual([
      "Main stat %", "Main stat (flat)", "Main stat scaling", "Critical", "Damage", "Attack and accuracy", "Skills and utility", "Defense and health",
    ]);
    const g = groupStats(["Luk", "Max HP %", "Boss Monster Damage %", "Critical Damage %", "Dex %", "Str", "Luk %", "Int %", "Str %", "Damage %", "Critical Rate %", "Normal Monster Damage %"]);
    expect(g).toEqual([
      { label: "Main stat %", stats: ["Str %", "Dex %", "Int %", "Luk %"] },
      { label: "Main stat (flat)", stats: ["Str", "Luk"] },
      { label: "Critical", stats: ["Critical Rate %", "Critical Damage %"] },
      { label: "Damage", stats: ["Damage %", "Boss Monster Damage %", "Normal Monster Damage %"] },
      { label: "Defense and health", stats: ["Max HP %"] },
    ]);
  });
  it("an unknown stat goes to a trailing 'Other' group in the order it came in (and an input order does not change the groups)", () => {
    const g = groupStats(["Zeta", "Damage %", "Alpha", "Str %"]);
    expect(g.map((x) => x.label)).toEqual(["Main stat %", "Damage", OTHER_GROUP]);
    expect(g[g.length - 1].stats).toEqual(["Zeta", "Alpha"]);
    expect(groupStats(["Damage %", "Str %"])).toEqual(groupStats(["Str %", "Damage %"]));
    expect(groupStats([])).toEqual([]);
  });
  it("groupedStatChoices: '(none)' and a flagged stored stat sit above the groups; the rollable stats are only grouped, never added or dropped", () => {
    const own = ["Damage %", "Str %", "Critical Rate %"];
    const plain = groupedStatChoices(own, "Damage %", NOT_ROLLABLE_ON_SLOT);
    expect(plain.head.map((c) => c.value)).toEqual([NONE_STAT]);
    expect(plain.groups.map((g) => g.label)).toEqual(["Main stat %", "Critical", "Damage"]);
    expect(plain.groups.flatMap((g) => g.choices.map((c) => c.value)).sort()).toEqual([...own].sort());
    const odd = groupedStatChoices(own, "Companion Summoning Time Increase %", NOT_ROLLABLE_ON_SLOT);
    expect(odd.head).toEqual([
      { value: NONE_STAT, label: NONE_STAT },
      { value: "Companion Summoning Time Increase %", label: "⚠ Companion Summoning Time Increase % (not rollable on this slot)", warn: true },
    ]);
    expect(odd.groups.flatMap((g) => g.choices).some((c) => c.warn)).toBe(false);
    expect(groupedStatChoices(own, NONE_STAT).head).toEqual([{ value: NONE_STAT, label: NONE_STAT }]);
  });
});
