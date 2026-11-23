import { afterEach, describe, expect, it, vi } from "vitest";
import { cubesFixture } from "./test/cubesFixture";
import { fixtureFor, NO_STAT_VALUES } from "./test/fixtures";

// VITE_MOCK=1: the cube tabs are served from the real-engine fixtures; classes without them answer 501 like the API.
async function mockApi() {
  vi.stubEnv("VITE_MOCK", "1");
  vi.resetModules();
  return await import("./api");
}
afterEach(() => vi.unstubAllEnvs());

const fx = cubesFixture();
const inputs = fixtureFor("fp_mage").sampleInputs;

describe("mock mode, cube tabs", () => {
  it("meta is the fixture; classes without stat values answer 501", async () => {
    const { api, ApiError } = await mockApi();
    expect(await api.cubesMeta("fp_mage")).toEqual(fx.meta);
    expect(NO_STAT_VALUES.length).toBeGreaterThan(0);
    for (const id of NO_STAT_VALUES.map((c) => c.info.id)) {
      await expect(api.cubesMeta(id)).rejects.toMatchObject({ status: 501 });
      await expect(api.cubes(id, inputs, [], [{ slot: "head", potential_type: "Potential" }])).rejects.toBeInstanceOf(ApiError);
      await expect(api.equipmentCompare(id, inputs, { current: { attack: 0, lines: [] }, new: { attack: 0, lines: [] } })).rejects.toMatchObject({ status: 501 });
      await expect(api.artifactPotentials(id, inputs, {})).rejects.toMatchObject({ status: 501 });
    }
  });
  it("cubes returns only the requested rows, labelled with the requested gear", async () => {
    const { api } = await mockApi();
    const only = [{ slot: "ring", potential_type: "Potential" }, { slot: "head", potential_type: "Bonus Potential" }];
    const gear = [{ slot: "ring", potential_type: "Potential", rarity: "mystic", pity: 0, lines: [{ stat: "Damage %", value: 7 }] }];
    const r = await api.cubes("fp_mage", inputs, gear, only);
    expect(r.rows.map((x) => `${x.slot}|${x.potential_type}`).sort()).toEqual(["head|Bonus Potential", "ring|Potential"]);
    const ring = r.rows.find((x) => x.slot === "ring")!;
    expect(ring.rarity).toBe("mystic");
    expect(ring.lines[0]).toEqual(["Damage %", 7]);
    expect(r.baseline_total).toBe(fx.cubes.result.baseline_total);
    expect(r.notes[0]).toContain("mock mode");
    const all = await api.cubes("fp_mage", inputs, [], fx.cubes.result.rows.map((x) => ({ slot: x.slot, potential_type: x.potential_type })));
    expect(all.rows).toHaveLength(30);
  });
  it("cubes honours an abort", async () => {
    const { api } = await mockApi();
    const ctl = new AbortController();
    const p = api.cubes("fp_mage", inputs, [], [{ slot: "ring", potential_type: "Potential" }], ctl.signal);
    ctl.abort();
    await expect(p).rejects.toMatchObject({ name: "AbortError" });
  });
  it("equipment compare recomputes edits with the engine's formula", async () => {
    const { api } = await mockApi();
    const same = await api.equipmentCompare("fp_mage", inputs, fx.equipment.request);
    expect(same.delta_pct).toBeCloseTo(fx.equipment.result.delta_pct, 9);
    expect(same.baseline_total).toBe(fx.equipment.result.baseline_total);
    const better = await api.equipmentCompare("fp_mage", inputs, { current: fx.equipment.request.current, new: { attack: 1e9, lines: fx.equipment.request.new.lines } });
    expect(better.new.pct).toBeGreaterThan(same.new.pct);
  });
  it("artifact potentials recompute with the slot's star", async () => {
    const { api } = await mockApi();
    const state = { book_of_ancient: { lines: [{ rarity: "Legendary", stat: "Damage %" }] } };
    const locked = await api.artifactPotentials("fp_mage", { ...inputs, artifacts: [{ key: "book_of_ancient", star: "Not Unlocked" }] }, state);
    const unlocked = await api.artifactPotentials("fp_mage", { ...inputs, artifacts: [{ key: "book_of_ancient", star: 3 }] }, state);
    const get = (r: typeof locked) => r.rows.find((x) => x.key === "book_of_ancient")!;
    expect(get(locked)).toMatchObject({ star: 0, total: 0, equipped: true });
    expect(get(unlocked).star).toBe(3);
    expect(get(unlocked).total).toBeGreaterThan(0);
    expect(unlocked.rows).toHaveLength(36);
  });
});
