import { describe, expect, it } from "vitest";
import { ApiError } from "../api";
import type { SensPart, SensitivityResult } from "./sensitivity";
import { friendlyError, SensitivityLoader, type Fetcher, type LoaderState } from "./sensitivityLoader";

const BASE = { class_id: "fp_mage", content_type: "World Boss", baseline_total: 1, baseline_boss_total: 1, baseline_normal_total: 1, normal_weight: 0, semantics: "workbook" };
const result = (...parts: SensPart[]) => ({ ...BASE, ...Object.fromEntries(parts.map((p) => [p, { rows: [] }])) }) as unknown as SensitivityResult;

/** Fetcher whose calls are resolved / rejected by hand; records parts and abort flags. */
function manual() {
  const calls: { classId: string; inputs: Record<string, unknown>; parts: SensPart[]; signal: AbortSignal; ok: (r: SensitivityResult) => void; fail: (e: unknown) => void }[] = [];
  const fetcher: Fetcher = (classId, inputs, parts, signal) =>
    new Promise((ok, fail) => {
      calls.push({ classId, inputs, parts, signal, ok, fail });
      signal.addEventListener("abort", () => fail(new DOMException("aborted", "AbortError")));
    });
  return { calls, fetcher };
}
const tick = () => new Promise((r) => setTimeout(r, 0));
const K1 = JSON.stringify({ level: 140 });
const K2 = JSON.stringify({ level: 141 });

describe("SensitivityLoader", () => {
  it("requests only the missing parts and never repeats loaded ones", async () => {
    const m = manual();
    const l = new SensitivityLoader(m.fetcher);
    l.load("fp_mage", K1, ["stats"]);
    expect(m.calls.map((c) => c.parts)).toEqual([["stats"]]);
    expect(l.state.status.loading).toBe(true);
    m.calls[0].ok(result("stats"));
    await tick();
    expect(l.state.status.loading).toBe(false);
    l.load("fp_mage", K1, ["stats"]); // already loaded
    expect(l.requests).toBe(1);
    l.load("fp_mage", K1, ["stats", "artifacts", "cdr"]);
    expect(m.calls[1].parts).toEqual(["artifacts", "cdr"]); // lazily: only what is new
    m.calls[1].ok(result("artifacts", "cdr"));
    await tick();
    expect(Object.keys(l.state.loaded!.result).filter((k) => ["stats", "artifacts", "cdr"].includes(k))).toEqual(["stats", "artifacts", "cdr"]);
    expect(JSON.stringify(m.calls[1].inputs)).toBe(K1);
  });

  it("changed inputs abort the in-flight request, ask for everything wanted again and drop the old result's parts", async () => {
    const m = manual();
    const l = new SensitivityLoader(m.fetcher);
    l.load("fp_mage", K1, ["stats"]);
    l.load("fp_mage", K2, ["stats"]);
    expect(m.calls[0].signal.aborted).toBe(true);
    expect(m.calls[1].signal.aborted).toBe(false);
    m.calls[0].ok(result("stats")); // a late answer of the aborted request must not show up
    await tick();
    expect(l.state.loaded).toBeNull();
    m.calls[1].ok(result("stats"));
    await tick();
    expect(l.state.loaded!.key).toBe(K2);
    l.load("fp_mage", K1, ["stats", "cdr"]); // other inputs: stats again, not just cdr
    expect(m.calls[2].parts).toEqual(["stats", "cdr"]);
  });

  it("cancel (tab left) aborts and clears the loading flag", () => {
    const m = manual();
    const l = new SensitivityLoader(m.fetcher);
    l.load("fp_mage", K1, ["stats"]);
    l.cancel();
    expect(m.calls[0].signal.aborted).toBe(true);
    expect(l.state.status.loading).toBe(false);
    expect(l.state.status.error).toBeNull();
  });

  it("501 marks the class unsupported and is not asked again", async () => {
    const m = manual();
    const seen: LoaderState[] = [];
    const l = new SensitivityLoader(m.fetcher, (s) => seen.push(s));
    l.load("hero", K1, ["stats"]);
    m.calls[0].fail(new ApiError(501, "stat values are not modelled for this class yet"));
    await tick();
    expect(l.state.unsupportedFor).toBe("hero");
    expect(l.state.status.error).toBeNull();
    l.load("hero", K2, ["stats"]);
    expect(l.requests).toBe(1);
    l.load("fp_mage", K1, ["stats"]); // another class is still asked
    expect(l.requests).toBe(2);
  });

  it("422 lists the field messages; other failures keep the message and a retry works", async () => {
    const m = manual();
    const l = new SensitivityLoader(m.fetcher);
    l.load("fp_mage", K1, ["stats"]);
    m.calls[0].fail(new ApiError(422, "Invalid inputs", [{ field: "level", message: "must be between 1 and 300" }]));
    await tick();
    expect(l.state.status.fieldErrors).toEqual(["level: must be between 1 and 300"]);
    expect(l.state.status.error).toMatch(/invalid/i);
    l.load("fp_mage", K1, ["stats"]);
    m.calls[1].fail(new ApiError(0, "Cannot reach the API"));
    await tick();
    expect(l.state.status).toMatchObject({ error: "Cannot reach the API", fieldErrors: [], loading: false });
    l.load("fp_mage", K1, ["stats"]); // nothing loaded: asks again
    m.calls[2].ok(result("stats"));
    await tick();
    expect(l.state.status.error).toBeNull();
    expect(l.requests).toBe(3);
  });

  it("friendly messages for rate limit and timeout", () => {
    expect(friendlyError(new ApiError(429, "rate limit exceeded, slow down"))).toContain("Wait a few seconds");
    expect(friendlyError(new ApiError(504, "stat values took longer than 30 s; try again"))).toBe("stat values took longer than 30 s; try again.");
    expect(friendlyError(new ApiError(500, "computation failed for these inputs"))).toBe("computation failed for these inputs");
  });
});
