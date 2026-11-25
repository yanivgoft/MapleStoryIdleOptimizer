import { describe, expect, it } from "vitest";
import { plainText } from "./plainText";
import { pctLabel, equipVerdict } from "./equipment";

describe("plainText", () => {
  it("rewrites the server's jargon and passes everything else through", () => {
    expect(plainText("raid content (not modelled)")).toBe("raid content (not covered)");
    expect(plainText("stat not used by the DPS model (Accuracy vs Evasion not modelled)")).toBe("stat not used for damage (accuracy and evasion do not change damage here)");
    expect(plainText("reference_only artifacts: their stat is entered by hand in Inputs (workbook convention); equipping changes nothing live")).toMatch(/already inside the stats you typed/);
    expect(plainText("Combat Orders' uptime moves with the cooldown (block F minus the main sheet's F)")).toBe("Combat Orders' uptime moves with the cooldown");
    expect(plainText("no attacking effect")).toBe("no attacking effect");
    expect(plainText(null)).toBe("");
  });
});

describe("tiny percentages never use exponent notation", () => {
  it("<0.01% instead of 1.2e-5", () => {
    expect(pctLabel(0.00001)).toBe("<0.01%");
    expect(pctLabel(-0.0000003)).toBe("<0.01%");
    expect(pctLabel(0)).toBe("0.00%");
    expect(pctLabel(1.234, true)).toBe("+1.23%");
    expect(pctLabel(-2)).toBe("-2.00%");
    expect(equipVerdict({ better: "new", delta_pct: 0.000012 })).toBe("The new equip is better: <0.01% of Total DPS.");
    expect(equipVerdict({ better: "current", delta_pct: -0.000012 })).toContain("loses <0.01% of Total DPS");
    expect(equipVerdict({ better: "new", delta_pct: 0.000012 })).not.toMatch(/e-/);
  });
});
