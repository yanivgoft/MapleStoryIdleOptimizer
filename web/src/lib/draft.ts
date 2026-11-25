// Silent autosave of the form: the current inputs are kept in the browser (`msi.draft.v1`) and restored on the next visit.  No UI of its own; the only text is the
// short message shown when the browser refuses to store anything.  Storage is injectable for tests.
import type { FormState } from "../types";
import { isProfile, withArtifacts } from "./profiles";

export const DRAFT_KEY = "msi.draft.v1";
export const STORAGE_FAIL_MESSAGE = "Your browser is blocking storage, so your inputs will not be remembered between visits.";

export interface DraftStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

function browserStorage(): DraftStorage | null {
  try {
    return typeof localStorage === "undefined" ? null : localStorage;
  } catch {
    return null; // some browsers throw on the property access itself when storage is blocked
  }
}

/** Parse a stored draft; anything malformed (or from a future shape) reads as no draft. */
export function parseDraft(raw: string | null): FormState | null {
  if (!raw) return null;
  try {
    const data = JSON.parse(raw) as { v?: unknown; state?: unknown };
    if (!data || data.v !== 1 || !data.state) return null;
    const profile = { id: "draft", name: "draft", savedAt: "", state: data.state as FormState };
    return isProfile(profile) ? withArtifacts(profile).state : null;
  } catch {
    return null;
  }
}

export function loadDraft(storage: DraftStorage | null = browserStorage()): FormState | null {
  try {
    return storage ? parseDraft(storage.getItem(DRAFT_KEY)) : null;
  } catch {
    return null;
  }
}

/** Store the draft; `false` when the browser refused (quota / blocked storage). */
export function saveDraft(state: FormState, storage: DraftStorage | null = browserStorage()): boolean {
  if (!storage) return false;
  try {
    storage.setItem(DRAFT_KEY, JSON.stringify({ v: 1, state }));
    return true;
  } catch {
    return false;
  }
}

export function clearDraft(storage: DraftStorage | null = browserStorage()): void {
  try {
    storage?.removeItem(DRAFT_KEY);
  } catch {
    /* nothing to do */
  }
}
