import { afterEach, describe, expect, it, vi } from "vitest";
import { fixtureFor } from "./test/fixtures";
import type { ComputeResult } from "./types";

async function mockApi() {
  vi.stubEnv("VITE_MOCK", "1");
  vi.resetModules();
  return await import("./api");
}
afterEach(() => vi.unstubAllEnvs());

describe("mock mode, artifacts", () => {
  const CASE = [{ key: "alliance_badge", star: 4 }, { key: "arwens_glass_shoes", star: 2 }, { key: "book_of_ancient", star: 5 }, { key: "pigs_ribbon", star: "Not Unlocked" }];
  it("the fixture's own 4 slots return the real engine output (artifacts block, higher DPS than without)", async () => {
    const { api } = await mockApi();
    const inputs = fixtureFor("fp_mage").sampleInputs;
    const plain = await api.compute("fp_mage", { ...inputs });
    const withArt = await api.compute("fp_mage", { ...inputs, artifacts: CASE });
    expect((plain.artifacts as { equipped: unknown[] }).equipped).toEqual([]);      // the engine always reports the block, empty when nothing is equipped
    expect((withArt.artifacts as { equipped: unknown[] }).equipped).toHaveLength(4);
    expect(withArt.total_dps).toBeGreaterThan(plain.total_dps);
  });
  it("other slot sets: plain numbers plus a stub block listing the equipped artifacts", async () => {
    const { api } = await mockApi();
    const inputs = fixtureFor("hero").sampleInputs;
    const r: ComputeResult = await api.compute("hero", { ...inputs, artifacts: [{ key: "candle", star: 3 }] });
    const block = r.artifacts as { equipped: { key: string; name: string; star: number }[]; notes: string[] };
    expect(block.equipped).toEqual([expect.objectContaining({ key: "candle", name: "Candle", star: 3 })]);
    expect(block.notes[0]).toContain("mock mode");
    expect(r.total_dps).toBeCloseTo(fixtureFor("hero").result.total_dps, 0);
  });
});
