import { afterEach, describe, expect, it, vi } from "vitest";
import { fixtureFor, NO_STAT_VALUES } from "./test/fixtures";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

async function load(mock: boolean) {
  vi.stubEnv("VITE_MOCK", mock ? "1" : "");
  vi.resetModules();
  return await import("./api");
}

describe("companion levels in the sensitivity request", () => {
  it("real mode: the body carries companion_levels, companion_potential_lines_pct and which next to the compute inputs", async () => {
    let sent: Record<string, unknown> = {};
    vi.stubGlobal("fetch", async (_url: string, init: RequestInit) => {
      sent = JSON.parse(String(init.body));
      return new Response(JSON.stringify({ class_id: "fp_mage" }), { status: 200, headers: { "Content-Type": "application/json" } });
    });
    const { api } = await load(false);
    const inputs = { ...fixtureFor("fp_mage").sampleInputs, companion_levels: { "Blaze Wizard": 10, Hero: 0 }, companion_potential_lines_pct: 12 };
    await api.sensitivity("fp_mage", inputs, ["companions", "summon_time"]);
    expect(sent).toMatchObject({ companion_levels: { "Blaze Wizard": 10, Hero: 0 }, companion_potential_lines_pct: 12, which: ["companions", "summon_time"], companion_choice: "Blaze Wizard" });
  });
  it("mock mode: the comparison is re-labelled with the requested levels (owned ones ranked), summon_time untouched, classes without stat values answer 501", async () => {
    const { api, ApiError } = await load(true);
    const inputs = { ...fixtureFor("fp_mage").sampleInputs, companion_levels: { "Blaze Wizard": 10, "Dawn Warrior": 4 } };
    const r = await api.sensitivity("fp_mage", inputs, ["companions", "summon_time"]);
    expect(r.companions!.rows.filter((x) => x.unlocked).map((x) => x.name).sort()).toEqual(["Blaze Wizard", "Dawn Warrior"]);
    expect(r.companions!.rows.find((x) => x.name === "Dawn Warrior")).toMatchObject({ level: 4, rank_position: 1 });
    expect(r.summon_time!.rows.length).toBe(19);
    const plain = await api.sensitivity("fp_mage", fixtureFor("fp_mage").sampleInputs, ["companions"]);
    expect(plain.companions!.rows.every((x) => x.unlocked)).toBe(true); // no levels sent: the fixture as it is
    expect(NO_STAT_VALUES.length).toBeGreaterThan(0);
    for (const c of NO_STAT_VALUES) await expect(api.sensitivity(c.info.id, inputs, ["companions"])).rejects.toBeInstanceOf(ApiError);
  });
});
