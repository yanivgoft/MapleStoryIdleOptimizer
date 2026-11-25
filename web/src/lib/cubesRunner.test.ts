import { describe, expect, it } from "vitest";
import { ApiError } from "../api";
import { CubesRunner, type CubesFetcher, type RunState } from "./cubesRunner";
import type { CubeRow, GearPayloadRow, RowRef } from "./cubes";
import { CUBES_CHUNK_ROWS } from "./cubes";

const SLOTS = ["head", "cape", "chest", "shoulders", "legs", "belt", "gloves", "boots", "ring", "neck", "eye-accessory", "ring2", "face", "earrings", "pocket"];
const ALL: RowRef[] = SLOTS.flatMap((slot) => ["Potential", "Bonus Potential"].map((potential_type) => ({ slot, potential_type })));
const row = (r: RowRef): CubeRow => ({ ...r, rarity: "normal", pity: 0, lines: [], current_value: 0, current_value_pct: 0, smallest_n: 1, n_for_50pct: 2, n_for_75pct: 3, milestone_ev: {}, milestone_ev_pct: {} });
const GEAR: GearPayloadRow[] = [];
const tick = () => new Promise((r) => setTimeout(r, 0));

function okFetcher(log: RowRef[][] = []): CubesFetcher {
  return async (_c, _i, _g, only) => {
    log.push(only);
    return { class_id: "fp_mage", baseline_total: 1000, milestones: [], csv_columns: [], backend: "python", rows: only.map(row), notes: only.length ? ["above"] : [] };
  };
}

describe("CubesRunner", () => {
  it("sends the rows in chunks and fills the result progressively", async () => {
    const log: RowRef[][] = [];
    const seen: RunState[] = [];
    const r = new CubesRunner(okFetcher(log), (s) => seen.push(s));
    await r.run("fp_mage", {}, GEAR, ALL, "k");
    expect(log.map((c) => c.length)).toEqual([6, 6, 6, 6, 6]);
    expect(CUBES_CHUNK_ROWS).toBe(6);
    expect(r.requests).toBe(5);
    expect(r.state).toMatchObject({ phase: "done", done: 30, total: 30, baseline: 1000, key: "k" });
    expect(r.state.rows).toHaveLength(30);
    expect(r.state.notes).toEqual(["above"]);
    const progress = seen.filter((s) => s.phase === "running").map((s) => s.done);
    expect(progress[0]).toBe(0);
    expect([...progress].sort((a, b) => a - b)).toEqual(progress); // never goes backwards
    expect(new Set(progress)).toEqual(new Set([0, 6, 12, 18, 24, 30]));
    expect(Math.max(...progress)).toBe(30);
  });
  it("rows keep their per-count curve through the chunk merge", async () => {
    const curve = Array.from({ length: 1001 }, (_v, n) => n / 100);
    const r = new CubesRunner(async (_c, _i, _g, only) => ({ class_id: "x", baseline_total: 1, milestones: [], csv_columns: [], backend: "python", rows: only.map((x) => ({ ...row(x), ev_pct_by_cubes: curve })), notes: [] }));
    await r.run("fp_mage", {}, GEAR, ALL, "k");
    expect(r.state.rows).toHaveLength(30);
    expect(r.state.rows.every((x) => x.ev_pct_by_cubes?.length === 1001 && x.ev_pct_by_cubes[86] === 0.86)).toBe(true);
  });
  it("a smaller selection is one request; zero rows is a finished empty run", async () => {
    const log: RowRef[][] = [];
    const r = new CubesRunner(okFetcher(log));
    await r.run("fp_mage", {}, GEAR, ALL.slice(0, 2), "k");
    expect(log).toHaveLength(1);
    await r.run("fp_mage", {}, GEAR, [], "k2");
    expect(r.state).toMatchObject({ phase: "done", done: 0, total: 0 });
  });
  it("cancel stops after the request in flight and keeps what arrived", async () => {
    let release!: () => void;
    let n = 0;
    const fetcher: CubesFetcher = (_c, _i, _g, only, signal) => {
      n++;
      if (n === 1) return Promise.resolve({ class_id: "x", baseline_total: 1, milestones: [], csv_columns: [], backend: "python", rows: only.map(row), notes: [] });
      return new Promise((_res, rej) => {
        release = () => rej(Object.assign(new Error("a"), { name: "AbortError" }));
        signal.addEventListener("abort", release);
      });
    };
    const r = new CubesRunner(fetcher);
    const p = r.run("fp_mage", {}, GEAR, ALL, "k");
    await tick();
    expect(r.state.phase).toBe("running");
    expect(r.state.done).toBe(6);
    r.cancel();
    await p;
    expect(r.state.phase).toBe("cancelled");
    expect(r.state.rows).toHaveLength(6);
    expect(n).toBe(2); // no third request
  });
  it("a failing chunk stops the run, keeps the earlier rows and reports the status (429 / 504 / 422 / 501)", async () => {
    for (const [status, check] of [
      [429, (s: RunState) => expect(s.status.error).toContain("Too many")],
      [504, (s: RunState) => expect(s.status.error).toContain("took longer")],
      [422, (s: RunState) => expect(s.status.fieldErrors).toEqual(["gear[0].rarity: bad"])],
      [501, (s: RunState) => expect(s.status.unsupported).toBe(true)],
    ] as const) {
      let n = 0;
      const r = new CubesRunner(async (_c, _i, _g, only) => {
        if (++n === 2) throw new ApiError(status, status === 504 ? "cube calculation took longer than 45 s; try again" : "x", status === 422 ? [{ field: "gear[0].rarity", message: "bad" }] : []);
        return { class_id: "x", baseline_total: 1, milestones: [], csv_columns: [], backend: "python", rows: only.map(row), notes: [] };
      });
      await r.run("fp_mage", {}, GEAR, ALL, "k");
      expect(r.state.phase).toBe("error");
      expect(r.state.rows).toHaveLength(6);
      expect(n).toBe(2);
      check(r.state);
    }
  });
  it("starting a new run supersedes the old one; reset clears everything", async () => {
    const log: RowRef[][] = [];
    const r = new CubesRunner(okFetcher(log));
    const first = r.run("fp_mage", {}, GEAR, ALL, "old");
    void r.run("fp_mage", {}, GEAR, ALL.slice(0, 2), "new");
    await first;
    await tick();
    expect(r.state.key).toBe("new");
    expect(r.state.rows).toHaveLength(2);
    r.reset();
    expect(r.state).toMatchObject({ phase: "idle", rows: [], done: 0 });
  });
});
