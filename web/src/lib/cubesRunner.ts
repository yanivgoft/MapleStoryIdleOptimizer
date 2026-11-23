// Calculate-button controller of the Cubes tab (React-free, unit-tested): sends the rows chunk by chunk (each request = a few slots), merges the answers as they
// arrive so the ranking fills in progressively, and supports cancel.  A failure keeps the rows received so far.
import { type RequestStatus, IDLE_STATUS, isAbort, statusOf } from "./liveRequest";
import type { CubeRow, CubesResult, GearPayloadRow, RowRef } from "./cubes";
import { CUBES_CHUNK_ROWS, chunk, rowKey } from "./cubes";

export type RunPhase = "idle" | "running" | "done" | "cancelled" | "error";

export interface RunState {
  phase: RunPhase;
  done: number; // rows received
  total: number; // rows asked for
  rows: CubeRow[]; // in arrival order (rank them with rankRows)
  baseline: number | null; // Total DPS the EVs are measured against
  notes: string[];
  status: RequestStatus; // error / 501 / 422 of a failed chunk
  key: string | null; // JSON of what this run was computed for (inputs + gear): compare with the current one to show "outdated"
}

export const IDLE_RUN: RunState = { phase: "idle", done: 0, total: 0, rows: [], baseline: null, notes: [], status: IDLE_STATUS, key: null };

export type CubesFetcher = (classId: string, inputs: Record<string, unknown>, gear: GearPayloadRow[], only: RowRef[], signal: AbortSignal) => Promise<CubesResult>;

export class CubesRunner {
  state: RunState = IDLE_RUN;
  requests = 0; // API calls made (tests)
  private ctl: AbortController | null = null;

  constructor(
    private fetcher: CubesFetcher,
    private onChange: (s: RunState) => void = () => undefined,
  ) {}

  private set(patch: Partial<RunState>) {
    this.state = { ...this.state, ...patch };
    this.onChange(this.state);
  }

  get running() {
    return this.state.phase === "running";
  }

  cancel() {
    if (!this.ctl) return;
    this.ctl.abort();
    this.ctl = null;
    if (this.state.phase === "running") this.set({ phase: "cancelled" });
  }

  reset() {
    this.cancel();
    this.set({ ...IDLE_RUN });
  }

  /** Start a run (an unfinished one is cancelled).  Resolves when it finishes, fails or is cancelled. */
  async run(classId: string, inputs: Record<string, unknown>, gear: GearPayloadRow[], rows: RowRef[], key: string, chunkRows = CUBES_CHUNK_ROWS): Promise<void> {
    this.ctl?.abort();
    const ctl = (this.ctl = new AbortController());
    this.set({ phase: "running", done: 0, total: rows.length, rows: [], baseline: null, notes: [], status: IDLE_STATUS, key });
    const byKey = new Map<string, CubeRow>();
    for (const part of chunk(rows, chunkRows)) {
      let res: CubesResult;
      try {
        this.requests++;
        res = await this.fetcher(classId, inputs, gear, part, ctl.signal);
      } catch (e) {
        if (ctl.signal.aborted || isAbort(e)) return;
        this.ctl = null;
        this.set({ phase: "error", status: statusOf(e, "cube") });
        return;
      }
      if (ctl.signal.aborted) return;
      for (const r of res.rows) byKey.set(rowKey(r), r);
      const notes = new Set([...this.state.notes, ...res.notes]);
      this.set({ rows: [...byKey.values()], done: byKey.size, baseline: res.baseline_total, notes: [...notes] });
    }
    this.ctl = null;
    this.set({ phase: "done" });
  }
}
