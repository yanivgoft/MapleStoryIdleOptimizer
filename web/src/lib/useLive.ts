import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { useDebounced } from "../hooks";
import { IDLE_STATUS, LiveRequest, type LiveState } from "./liveRequest";
import type { CubesMeta } from "./cubes";
import { statusOf, type RequestStatus } from "./liveRequest";

export const LIVE_DEBOUNCE_MS = 500;

/**
 * One debounced request while `active` (the tab is visible) and `key` is non-empty: aborts the in-flight request when the key / class changes or the tab is left, keeps
 * the previous answer (dimmed) while the next one loads.  `key` is the JSON of everything the request depends on; `fetcher` receives it back.
 */
export function useLive<T>(opts: { key: string; group: string; active: boolean; what: string; fetcher: (key: string, signal: AbortSignal) => Promise<T>; debounceMs?: number }) {
  const { key, group, active, what, fetcher, debounceMs = LIVE_DEBOUNCE_MS } = opts;
  const debounced = useDebounced(key, debounceMs);
  const [state, setState] = useState<LiveState<T> | null>(null);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;
  const loader = useRef<LiveRequest<T> | null>(null);
  if (loader.current === null) loader.current = new LiveRequest<T>((k, s) => fetcherRef.current(k, s), what, setState);
  const [attempt, setAttempt] = useState(0);
  const lastGroup = useRef(group);

  useEffect(() => {
    const l = loader.current!;
    if (lastGroup.current !== group) {
      lastGroup.current = group;
      l.reset();
    }
    if (!active || !debounced) {
      l.cancel();
      return;
    }
    l.load(debounced, group);
    return () => l.cancel();
  }, [active, debounced, group, attempt]);

  const s = state ?? loader.current.state;
  const retry = useCallback(() => {
    loader.current!.state = { ...loader.current!.state, resultKey: null };
    setAttempt((n) => n + 1);
  }, []);
  return { result: s.result, status: s.status, stale: s.result !== null && s.resultKey !== key, pending: key !== debounced && !!key, retry };
}

/** Static cube-tab tables of a class (GET .../cubes/meta), fetched once per class while `enabled`; 501 = the class does not have them. */
export function useCubesMeta(classId: string | null, enabled: boolean): { meta: CubesMeta | null; status: RequestStatus } {
  const [meta, setMeta] = useState<CubesMeta | null>(null);
  const [status, setStatus] = useState<RequestStatus>(IDLE_STATUS);
  useEffect(() => {
    if (!enabled || !classId || meta?.class_id === classId) return;
    const ctl = new AbortController();
    setStatus({ ...IDLE_STATUS, loading: true });
    api.cubesMeta(classId, ctl.signal).then(
      (m) => {
        setMeta({ ...m, class_id: classId });
        setStatus(IDLE_STATUS);
      },
      (e: unknown) => {
        if ((e as Error).name !== "AbortError") setStatus(statusOf(e, "cube tables"));
      },
    );
    return () => ctl.abort();
  }, [enabled, classId, meta]);
  return { meta: meta?.class_id === classId ? meta : null, status };
}
