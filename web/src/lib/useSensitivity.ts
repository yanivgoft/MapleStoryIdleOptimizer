import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { useDebounced } from "../hooks";
import type { SensPart } from "./sensitivity";
import { SENS_PARTS } from "./sensitivity";
import { SensitivityLoader, type Fetcher, type LoaderState } from "./sensitivityLoader";

export type { SensStatus } from "./sensitivityLoader";
export const SENS_DEBOUNCE_MS = 600; // one call costs ~0.5 s on the server

const apiFetcher: Fetcher = (classId, inputs, parts, signal) => api.sensitivity(classId, inputs, parts, signal);

/**
 * Stat values for the current inputs.  Requests only while `active` (the tab is visible), debounced by 600 ms, aborts the in-flight request when the inputs /
 * class / wanted parts change or the tab is left, and asks the server only for the `wanted` parts that are not loaded yet for these inputs (stats first, the
 * rest when asked; see `SensitivityLoader`).  The previous result stays available (`stale`) while a new one loads.
 */
export function useSensitivity(opts: { classId: string | null; inputs: Record<string, unknown> | null; active: boolean; wanted: SensPart[]; debounceMs?: number; fetcher?: Fetcher }) {
  const { classId, inputs, active, wanted, debounceMs = SENS_DEBOUNCE_MS, fetcher = apiFetcher } = opts;
  const inputsKey = inputs ? JSON.stringify(inputs) : "";
  const key = useDebounced(inputsKey, debounceMs);
  const [state, setState] = useState<LoaderState | null>(null);
  const loader = useRef<SensitivityLoader | null>(null);
  if (loader.current === null) loader.current = new SensitivityLoader(fetcher, setState);
  const [attempt, setAttempt] = useState(0);
  const wantedKey = SENS_PARTS.filter((p) => wanted.includes(p)).join(",");

  useEffect(() => {
    const l = loader.current!;
    if (!active || !classId || !key) {
      l.cancel();
      return;
    }
    l.load(classId, key, wantedKey ? (wantedKey.split(",") as SensPart[]) : []);
    return () => l.cancel();
  }, [active, classId, key, wantedKey, attempt]);

  const s = state ?? loader.current.state;
  const result = s.loaded && s.loaded.classId === classId ? s.loaded.result : null;
  const stale = !!s.loaded && s.loaded.key !== inputsKey;
  const pending = inputsKey !== key; // typing: the request waits for the inputs to settle
  const retry = useCallback(() => setAttempt((n) => n + 1), []);
  return { result, status: { ...s.status, unsupported: classId !== null && s.unsupportedFor === classId }, stale, pending, retry };
}
