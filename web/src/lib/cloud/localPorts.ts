// Accounts: the real (browser) implementations of the controller's ports: the profile list (through lib/profiles.ts' public functions), the sync metadata and
// the conflict history (localStorage), the theme.  A profile's `state` is OPAQUE here: it is only ever stringified (canonical JSON), hashed and passed back
// through lib/profiles.ts' own import normalisation (`parseImport`), so changes to the form-state shape need no change in the cloud code.
import type { Profile } from "../../types";
import { EXPORT_VERSION, listProfiles, parseImport, clearAllProfiles, removeProfilesById, subscribeProfiles, upsertProfilesById } from "../profiles";
import { applyTheme, readTheme, writeTheme } from "../theme";
import type { ControllerDeps, LocalPort, MetaPort, SettingsPort } from "./sync";
import { clipName, emptyMeta, stableStringify, type HistoryEntry, type ProfileRec, type SettingsContent, type SettingsRec, type SyncMeta } from "./merge";

// ---- Profile <-> cloud record ----------------------------------------------------------------------------------------------------------------------

export function profileToRec(p: Profile): ProfileRec {
  const t = Date.parse(p.savedAt);
  return { id: p.id, classId: p.state.classId, name: clipName(p.name), updatedAt: Number.isFinite(t) ? t : 0, state: stableStringify(p.state) };
}

/** A cloud record as a local Profile, repaired by the app's own import normalisation; null when it is not a usable profile. */
export function recToProfile(r: ProfileRec): Profile | null {
  if (r.deleted) return null;
  try {
    const state = JSON.parse(r.state) as unknown;
    const text = JSON.stringify({ app: "msi-dps", version: EXPORT_VERSION, profiles: [{ id: r.id, name: r.name, savedAt: new Date(r.updatedAt).toISOString(), state }] });
    const p = parseImport(text)[0];
    return p && p.id === r.id ? p : null;
  } catch {
    return null;
  }
}

/** The record the way this app version would store it locally (so cloud and local content compare like for like). */
export function canonicalRec(r: ProfileRec): ProfileRec | null {
  const p = recToProfile(r);
  return p ? { ...profileToRec(p), updatedAt: r.updatedAt } : null;
}

// ---- storage helpers ---------------------------------------------------------------------------------------------------------------------------------

type Store = Pick<Storage, "getItem" | "setItem" | "removeItem">;
const store = (): Store | null => {
  try {
    return typeof localStorage === "undefined" ? null : localStorage;
  } catch {
    return null;
  }
};
function getJson<T>(key: string): T | null {
  try {
    const raw = store()?.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}
function setJson(key: string, value: unknown): void {
  try {
    store()?.setItem(key, JSON.stringify(value));
  } catch {
    /* storage full / blocked: the sync data is rebuilt at the next sign-in */
  }
}
function remove(key: string): void {
  try {
    store()?.removeItem(key);
  } catch {
    /* ignore */
  }
}

export const META_KEY = "msi.cloud.meta.v1."; // + uid
export const LAST_UID_KEY = "msi.cloud.last.v1";
export const HISTORY_KEY = "msi.cloud.history.v1";
export const PRIVACY_KEY = "msi.cloud.privacy.v1";
export const SESSION_KEY = "msi.cloud.session.v1"; // present = a Google session was open: restore it (load the SDK) at startup
export const PROFILES_KEY = "msi.profiles.v1";

export const hasSessionFlag = (): boolean => {
  try {
    return !!store()?.getItem(SESSION_KEY);
  } catch {
    return false;
  }
};
export const setSessionFlag = (on: boolean): void => (on ? setJson(SESSION_KEY, 1) : remove(SESSION_KEY));
export const privacySeen = (): boolean => getJson<number>(PRIVACY_KEY) !== null;
export const markPrivacySeen = (): void => setJson(PRIVACY_KEY, Date.now());

export function browserMetaPort(): MetaPort {
  return {
    load(uid) {
      const m = getJson<SyncMeta>(META_KEY + uid);
      return m && m.v === 1 && m.baseline && m.deletes && m.skipped ? { ...emptyMeta(), ...m } : null;
    },
    save: (uid, meta) => setJson(META_KEY + uid, meta),
    clear: (uid) => remove(META_KEY + uid),
    lastUid: () => getJson<string>(LAST_UID_KEY),
    setLastUid: (uid) => (uid ? setJson(LAST_UID_KEY, uid) : remove(LAST_UID_KEY)),
    loadHistory: () => {
      const h = getJson<HistoryEntry[]>(HISTORY_KEY);
      return Array.isArray(h) ? h.filter((e) => e && typeof e.key === "string" && typeof e.state === "string") : [];
    },
    saveHistory: (h) => (h.length ? setJson(HISTORY_KEY, h) : remove(HISTORY_KEY)),
  };
}

export function browserLocalPort(): LocalPort {
  return {
    listRecs: () => listProfiles().map(profileToRec),
    put(recs) {
      const profiles = recs.flatMap((r) => {
        const p = recToProfile(r);
        return p ? [p] : [];
      });
      upsertProfilesById(profiles);
    },
    remove: removeProfilesById,
    clear: clearAllProfiles,
    subscribe(fn) {
      const off = subscribeProfiles(fn);
      const onStorage = (e: StorageEvent) => {
        if (e.key === PROFILES_KEY || e.key === null) fn(); // another tab changed the list
      };
      if (typeof window !== "undefined") window.addEventListener("storage", onStorage);
      return () => {
        off();
        if (typeof window !== "undefined") window.removeEventListener("storage", onStorage);
      };
    },
    canonical: canonicalRec,
  };
}

/** Fired on `window` after the theme was changed by the account (the header ThemeToggle listens and re-reads the stored choice). */
export const THEME_EVENT = "msi-theme-change";

/** `read` supplies the current class / last profile (kept up to date by the React layer); `onApply` is told about the account's settings (to switch class). */
export function browserSettingsPort(read: () => { lastClassId?: string; lastProfileId?: string }, onApply?: (s: SettingsRec) => void): SettingsPort {
  return {
    read: (): SettingsContent => ({ theme: readTheme(), ...read() }),
    apply(s) {
      writeTheme(s.theme);
      applyTheme(s.theme);
      if (typeof window !== "undefined") window.dispatchEvent(new Event(THEME_EVENT));
      onApply?.(s);
    },
  };
}

export function browserDeps(read: Parameters<typeof browserSettingsPort>[0], onApply?: Parameters<typeof browserSettingsPort>[1]): ControllerDeps {
  return { local: browserLocalPort(), meta: browserMetaPort(), settings: browserSettingsPort(read, onApply) };
}
