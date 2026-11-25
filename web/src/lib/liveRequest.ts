// Shared request plumbing of the cube tabs (React-free, unit-tested): maps API failures to a status and runs ONE debounced "live" request at a time.
import { ApiError } from "../api";

export interface RequestStatus {
  loading: boolean;
  unsupported: boolean; // 501: not modelled for this class
  error: string | null;
  fieldErrors: string[]; // 422 messages ("field: message")
}

export const IDLE_STATUS: RequestStatus = { loading: false, unsupported: false, error: null, fieldErrors: [] };

/** Message of a failed request: 429 / 504 get a hint, 422 is summarised (the field messages are listed separately), anything else shows the API's own text. */
export function friendlyError(e: unknown, what: string): string {
  if (e instanceof ApiError) {
    if (e.status === 0) return "Can't reach the calculator server. Check your connection and try again.";
    if (e.status === 429) return `Too many ${what} requests in a short time (${e.message}). Wait a little and try again.`;
    if (e.status === 504) return `${e.message}.`;
    if (e.status === 422) return "Some inputs are invalid - fix them below or on the Calculator tab.";
    if (e.status === 413) return "The request was too large.";
  }
  return (e as Error).message || "Request failed.";
}

/** An aborted request is not a failure. */
export function isAbort(e: unknown): boolean {
  return (e as Error)?.name === "AbortError";
}

/** Status of a failed request (501 / 422 / other); abort errors must be filtered by the caller. */
export function statusOf(e: unknown, what: string): RequestStatus {
  if (e instanceof ApiError && e.status === 501) return { ...IDLE_STATUS, unsupported: true };
  const fieldErrors = e instanceof ApiError && e.status === 422 ? e.fieldErrors.map((f) => (f.field ? `${f.field}: ${f.message}` : f.message)) : [];
  return { ...IDLE_STATUS, error: friendlyError(e, what), fieldErrors };
}

export interface LiveState<T> {
  result: T | null; // the last answer (kept, dimmed, while the next one loads)
  resultKey: string | null; // the request key it belongs to
  status: RequestStatus;
}

/** One debounced request at a time: `load(key)` aborts the previous one; a no-op when `key` is the key of the last answer.  `fetcher(key, signal)` gets the same
 *  key string back (the JSON of the request), so callers can put everything the request depends on into it. */
export class LiveRequest<T> {
  state: LiveState<T> = { result: null, resultKey: null, status: IDLE_STATUS };
  requests = 0; // API calls made (tests)
  private ctl: AbortController | null = null;
  private unsupportedKey: string | null = null;

  constructor(
    private fetcher: (key: string, signal: AbortSignal) => Promise<T>,
    private what: string,
    private onChange: (s: LiveState<T>) => void = () => undefined,
  ) {}

  private set(patch: Partial<LiveState<T>>) {
    this.state = { ...this.state, ...patch };
    this.onChange(this.state);
  }

  cancel() {
    this.ctl?.abort();
    this.ctl = null;
    if (this.state.status.loading) this.set({ status: { ...this.state.status, loading: false } });
  }

  /** `group` identifies what 501 applies to (the class): once a group answered 501 it is not asked again until `reset`. */
  load(key: string, group = "") {
    if (this.unsupportedKey === group && group !== "") return;
    if (this.state.resultKey === key && !this.state.status.error) return;
    this.ctl?.abort();
    const ctl = (this.ctl = new AbortController());
    this.requests++;
    this.set({ status: { ...IDLE_STATUS, loading: true } });
    this.fetcher(key, ctl.signal).then(
      (r) => {
        if (ctl.signal.aborted) return;
        this.set({ result: r, resultKey: key, status: IDLE_STATUS });
      },
      (e: unknown) => {
        if (isAbort(e) || ctl.signal.aborted) return;
        const st = statusOf(e, this.what);
        if (st.unsupported) this.unsupportedKey = group;
        this.set({ status: st });
      },
    );
  }

  /** Forget the answer and any 501 (class switch). */
  reset() {
    this.cancel();
    this.unsupportedKey = null;
    this.set({ result: null, resultKey: null, status: IDLE_STATUS });
  }
}
