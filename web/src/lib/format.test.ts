import { describe, expect, it } from "vitest";
import { formatFull, formatNumber, formatPercent } from "./format";

describe("formatNumber", () => {
  it("abbreviates large values", () => {
    expect(formatNumber(1.23e12)).toBe("1.23T");
    expect(formatNumber(4.5678e9)).toBe("4.57B");
    expect(formatNumber(45678)).toBe("45.7K");
    expect(formatNumber(5.036411e16)).toBe("50.4Qa");
    expect(formatNumber(1.5e6)).toBe("1.5M");
  });
  it("keeps small values readable", () => {
    expect(formatNumber(0)).toBe("0");
    expect(formatNumber(999)).toBe("999");
    expect(formatNumber(3.14159)).toBe("3.14");
    expect(formatNumber(12.34)).toBe("12.3");
    expect(formatNumber(-2500)).toBe("-2.5K");
  });
  it("carries rounding into the next unit", () => {
    expect(formatNumber(999_960)).toBe("1M");
    expect(formatNumber(999_999_999)).toBe("1B");
  });
  it("handles missing / non-finite", () => {
    expect(formatNumber(null)).toBe("–");
    expect(formatNumber(undefined)).toBe("–");
    expect(formatNumber(NaN)).toBe("–");
    expect(formatNumber(Infinity)).toBe("–");
  });
});

describe("formatFull / formatPercent", () => {
  it("groups digits", () => expect(formatFull(1234567.4)).toBe("1,234,567"));
  it("formats shares", () => {
    expect(formatPercent(0.1780294)).toBe("17.8%");
    expect(formatPercent(0.5, 0)).toBe("50%");
    expect(formatPercent(NaN)).toBe("–");
  });
});
