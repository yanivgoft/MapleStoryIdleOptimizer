import { afterEach, describe, expect, it, vi } from "vitest";
import { CLASS_IDS, fixtureFor } from "./test/fixtures";

// VITE_MOCK=1 mode (npm run dev:mock): every class is served from its fixture set.
async function mockApi() {
  vi.stubEnv("VITE_MOCK", "1");
  vi.resetModules();
  return await import("./api");
}

afterEach(() => vi.unstubAllEnvs());

describe("mock mode serves all 12 classes", () => {
  it("lists the classes, loads schema + defaults for every content type, computes", async () => {
    const { api, MOCK } = await mockApi();
    expect(MOCK).toBe(true);
    const classes = await api.classes();
    expect(classes.map((c) => c.id).sort()).toEqual([...CLASS_IDS].sort());
    expect(classes).toHaveLength(12);
    for (const id of CLASS_IDS) {
      const schema = await api.schema(id);
      expect(schema.class_id).toBe(id);
      for (const ct of schema.content_types) {
        const d = await api.defaults(id, ct);
        expect(d.content_type).toBe(ct);
      }
    }
  });
  it("compute scales with Flat ATTACK, follows the companion choice, and rejects unknown classes", async () => {
    const { api, ApiError } = await mockApi();
    for (const id of ["hero", "night_lord", "fp_mage"]) {
      const f = fixtureFor(id);
      const inp = { ...f.sampleInputs };
      const base = await api.compute(id, inp);
      expect(base.total_dps).toBe(f.result.total_dps);
      const doubled = await api.compute(id, { ...inp, flat_attack: Number(inp.flat_attack) * 2 });
      expect(doubled.total_dps).toBeCloseTo(base.total_dps * 2, 3);
      const none = await api.compute(id, { ...inp, companion_choice: "None" });
      expect(none.companion).toBeNull();
      expect(none.total_dps).toBeLessThan(base.total_dps);
      const other = await api.compute(id, { ...inp, companion_choice: "Shadower", companion_level: 7 });
      expect(other.companion).toMatchObject({ choice: "Shadower", level: 7 });
    }
    await expect(api.schema("nope")).rejects.toBeInstanceOf(ApiError);
  });
});
