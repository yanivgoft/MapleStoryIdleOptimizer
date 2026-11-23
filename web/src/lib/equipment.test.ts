import { describe, expect, it } from "vitest";
import { cubesFixture } from "../test/cubesFixture";
import { blankEquip, compareEquip, equipPayload, equipVerdict, evaluateSide, normalizeEquip, sideHasContent } from "./equipment";

const fx = cubesFixture().equipment;
const close = (a: number, b: number) => expect(Math.abs(a - b)).toBeLessThanOrEqual(1e-9 * Math.max(1, Math.abs(b)));

describe("equipment compare port == the real engine (fixture)", () => {
  const { rate_by_stat: rate, baseline_total: total } = fx.result;
  const out = compareEquip(fx.request, rate, total);
  it("both sides, every line", () => {
    for (const side of ["current", "new"] as const) {
      close(out[side].total_gain, fx.result[side].total_gain);
      close(out[side].pct, fx.result[side].pct);
      expect(out[side].rows).toHaveLength(6);
      out[side].rows.forEach((r, i) => {
        const e = fx.result[side].rows[i];
        expect(r.stat).toBe(e.stat);
        expect(r.first).toBe(e.first);
        close(r.gain, e.gain);
        close(r.group, e.group);
        close(r.factor, e.factor);
      });
    }
    close(out.delta_pct, fx.result.delta_pct);
    close(out.delta_dps, fx.result.delta_dps);
    expect(out.better).toBe(fx.result.better);
  });
  it("same-stat lines merge (including a dropdown Attack line into the fixed one), different stats compound", () => {
    const rates = { "Attack (flat)": 2, "Damage %": 3, "Final Damage %": 5 };
    const a = evaluateSide({ attack: 10, lines: [{ stat: "Attack (flat)", value: 5 }, { stat: "Damage %", value: 1 }, { stat: "Damage %", value: 2 }] }, rates, 1000);
    expect(a.rows[1].first).toBe(false); // merged into the fixed Attack line
    expect(a.rows[2].first).toBe(true);
    expect(a.rows[3].first).toBe(false); // merged into line 2
    close(a.rows[0].group, 30); // (10 + 5) x 2
    close(a.rows[2].group, 9); // (1 + 2) x 3
    close(a.total_gain, 1000 * ((1 + 30 / 1000) * (1 + 9 / 1000) - 1));
    const same = compareEquip({ current: { attack: 0, lines: [{ stat: "Damage %", value: 10 }] }, new: { attack: 0, lines: [{ stat: "Damage %", value: 4 }, { stat: "Damage %", value: 6 }] } }, rates, 1000);
    expect(same.better).toBe("equal");
    expect(same.delta_pct).toBe(0);
  });
});

describe("equipment state", () => {
  it("payload drops (none) lines and blanks read as 0", () => {
    const s = blankEquip();
    s.current.attack = 1500;
    s.current.lines[0] = { stat: "Damage %", value: 14 };
    s.current.lines[1] = { stat: "(none)", value: 9 };
    s.new.lines[2] = { stat: "Final Damage %", value: null };
    expect(equipPayload(s)).toEqual({
      current: { attack: 1500, lines: [{ stat: "Damage %", value: 14 }] },
      new: { attack: 0, lines: [{ stat: "Final Damage %", value: 0 }] },
    });
    expect(sideHasContent(s.current)).toBe(true);
    expect(sideHasContent(blankEquip().new)).toBe(false);
  });
  it("normalizeEquip repairs stored junk and pads to 5 lines", () => {
    expect(normalizeEquip(undefined)).toEqual(blankEquip());
    const n = normalizeEquip({ current: { attack: -3, lines: [{ stat: "Damage %", value: 5 }, 7] }, new: "x" });
    expect(n.current.attack).toBeNull();
    expect(n.current.lines).toHaveLength(5);
    expect(n.current.lines[0]).toEqual({ stat: "Damage %", value: 5 });
    expect(n.current.lines[1].stat).toBe("(none)");
    expect(n.new).toEqual(blankEquip().new);
  });
  it("verdict wording", () => {
    expect(equipVerdict({ better: "equal", delta_pct: 0 })).toContain("same");
    expect(equipVerdict({ better: "new", delta_pct: 1.234 })).toBe("The new equip is better: +1.23% of Total DPS.");
    expect(equipVerdict({ better: "current", delta_pct: -2 })).toContain("loses 2.00%");
  });
});
