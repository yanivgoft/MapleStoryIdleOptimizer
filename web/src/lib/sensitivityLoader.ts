// Request controller of the Stat values tab, kept free of React so it can be unit-tested: asks the API only for the wanted parts that are not loaded yet for
// these inputs, aborts the in-flight request when a newer one supersedes it, merges partial answers, and turns 501 / 422 / other failures into a status.
import { ApiError } from "../api";
import type { SensPart, SensitivityResult } from "./sensitivity";
import { loadedParts, mergeResult, missingParts } from "./sensitivity";

export interface SensStatus {
  loading: boolean;
  unsupported: boolean; // 501: not modelled for this class
  error: string | null;
  fieldErrors: string[]; // 422 messages ("field: message")
}

export interface Loaded {
  classId: string;
  key: string; // JSON of the inputs the result belongs to
  result: SensitivityResult;
}

export interface LoaderState {
  loaded: Loaded | null;
  status: SensStatus;
  unsupportedFor: string | null; // class the API answered 501 for (no point asking again)
}

export type Fetcher = (classId: string, inputs: Record<string, unknown>, parts: SensPart[], signal: AbortSignal) => Promise<SensitivityResult>;

export const IDLE: SensStatus = { loading: false, unsupported: false, error: null, fieldErrors: [] };

export class SensitivityLoader {
  state: LoaderState = { loaded: null, status: IDLE, unsupportedFor: null };
  private ctl: AbortController | null = null;
  requests = 0; // number of API calls made (tests)

  constructor(
    private fetcher: Fetcher,
    private onChange: (s: LoaderState) => void = () => undefined,
  ) {}

  private set(patch: Partial<LoaderState>) {
    this.state = { ...this.state, ...patch };
    this.onChange(this.state);
  }

  /** Abort whatever is in flight (tab left, unmount). */
  cancel() {
    this.ctl?.abort();
    this.ctl = null;
    if (this.state.status.loading) this.set({ status: { ...this.state.status, loading: false } });
  }

  /** Make sure the `wanted` parts of `classId` / `key` (JSON inputs) are loaded; a no-op when they already are. */
  load(classId: string, key: string, wanted: SensPart[]) {
    if (this.state.unsupportedFor === classId) return;
    const cur = this.state.loaded;
    const same = cur !== null && cur.classId === classId && cur.key === key;
    const todo = missingParts(same ? loadedParts(cur.result) : [], wanted);
    if (!todo.length) {
      this.cancel();
      return;
    }
    this.ctl?.abort();
    const ctl = (this.ctl = new AbortController());
    this.requests++;
    this.set({ status: { ...IDLE, loading: true } });
    this.fetcher(classId, JSON.parse(key), todo, ctl.signal).then(
      (r) => {
        if (ctl.signal.aborted) return;
        const prev = this.state.loaded;
        const merge = prev !== null && prev.classId === classId && prev.key === key;
        this.set({ loaded: { classId, key, result: merge ? mergeResult(prev.result, r) : r }, status: IDLE });
      },
      (e: unknown) => {
        if ((e as Error).name === "AbortError" || ctl.signal.aborted) return;
        if (e instanceof ApiError && e.status === 501) this.set({ unsupportedFor: classId, status: IDLE });
        else if (e instanceof ApiError && e.status === 422) {
          this.set({
            status: { ...IDLE, error: "Some inputs are invalid - fix them on the Calculator tab.", fieldErrors: e.fieldErrors.map((f) => (f.field ? `${f.field}: ${f.message}` : f.message)) },
          });
        } else this.set({ status: { ...IDLE, error: friendlyError(e) } });
      },
    );
  }
}

/** Message of a failed request (429 / 504 get a hint; everything else shows the API's own text). */
export function friendlyError(e: unknown): string {
  if (e instanceof ApiError && e.status === 429) return `Too many stat-value requests in a short time (${e.message}). Wait a few seconds and try again.`;
  if (e instanceof ApiError && e.status === 504) return `${e.message}.`;
  return (e as Error).message || "Request failed.";
}
