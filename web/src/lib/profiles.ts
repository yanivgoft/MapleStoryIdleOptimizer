import type { FormState, Profile } from "../types";
import { normalizeCubesState } from "./cubes";
import { normalizeEquip } from "./equipment";
import { normalizePotentials } from "./artifactPotentials";
import { normalizeCompanions } from "./companions";

const KEY = "msi.profiles.v1";
export const EXPORT_VERSION = 1;

function read(): Profile[] {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter(isProfile).map(withArtifacts) : [];
  } catch {
    return [];
  }
}

function write(list: Profile[]) {
  localStorage.setItem(KEY, JSON.stringify(list));
  changeListeners.forEach((fn) => fn());
}

// Change hook (used by the optional accounts feature, lib/cloud/): called after EVERY write of the profile list, in this tab.
const changeListeners = new Set<() => void>();
export function subscribeProfiles(fn: () => void): () => void {
  changeListeners.add(fn);
  return () => void changeListeners.delete(fn);
}

export function isProfile(x: unknown): x is Profile {
  const p = x as Profile;
  return (
    !!p &&
    typeof p.id === "string" &&
    typeof p.name === "string" &&
    !!p.state &&
    typeof p.state.classId === "string" &&
    typeof p.state.contentType === "string" &&
    typeof p.state.shared === "object" &&
    typeof p.state.perContent === "object"
  );
}

/** The Artifacts table is optional in stored / imported profiles and comes in two shapes: the current one (a record per artifact id) and the OLD one (a list of
 *  equipped slots `[{key, star}]` + a separate `potentials` state, saved before the table).  Here the state is only made well-formed; the OLD shape is kept
 *  as it is (a cleaned list) and migrated, with the engine's schema at hand, by `normalizeState` (lib/schemaForm.ts -> `normalizeArtifacts`). */
export function withArtifacts(p: Profile): Profile {
  const st = p.state as { artifacts?: unknown; cubes?: unknown; equipment?: unknown; potentials?: unknown; companions?: unknown };
  const raw = st.artifacts;
  let artifacts: unknown;
  if (Array.isArray(raw)) {
    artifacts = raw
      .filter((s): s is { key: string; star?: unknown } => !!s && typeof (s as { key?: unknown }).key === "string")
      .map((s) => ({ key: s.key, star: typeof s.star === "number" || typeof s.star === "string" ? s.star : null }));
  } else if (raw && typeof raw === "object") {
    artifacts = Object.fromEntries(Object.entries(raw as Record<string, unknown>).filter(([k, v]) => /^[a-z0-9_]+$/.test(k) && !!v && typeof v === "object" && !Array.isArray(v)));
  } else artifacts = {};
  // cube tabs' data is optional too (profiles saved before they existed); present ones are made well-formed
  const extra: Pick<FormState, "cubes" | "equipment" | "potentials" | "companions"> = {};
  // Companions tab data; profiles saved before it have none (normalizeState then migrates the old shared companion level)
  if (st.companions !== undefined) extra.companions = normalizeCompanions(st.companions);
  if (st.cubes !== undefined) extra.cubes = normalizeCubesState(st.cubes);
  if (st.equipment !== undefined) extra.equipment = normalizeEquip(st.equipment);
  // legacy: the old Artifact-potentials state only matters as long as the artifacts are still the old slots list (normalizeState migrates and drops it)
  if (st.potentials !== undefined && Array.isArray(raw)) extra.potentials = normalizePotentials(st.potentials);
  const { potentials: _dropped, ...state } = p.state;
  void _dropped;
  return { ...p, state: { ...state, artifacts: artifacts as FormState["artifacts"], ...extra } };
}

export function listProfiles(): Profile[] {
  return read().sort((a, b) => a.name.localeCompare(b.name));
}

/** Save under ``name`` (same name + class overwrites). */
export function saveProfile(name: string, state: FormState): Profile {
  const list = read();
  const clean = name.trim() || "Unnamed";
  const existing = list.find((p) => p.name === clean && p.state.classId === state.classId);
  const profile: Profile = {
    id: existing?.id ?? `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`,
    name: clean,
    savedAt: new Date().toISOString(),
    state: JSON.parse(JSON.stringify({ ...state, artifacts: state.artifacts ?? {} })),
  };
  write([...list.filter((p) => p.id !== profile.id), profile]);
  return profile;
}

export function deleteProfile(id: string) {
  write(read().filter((p) => p.id !== id));
}

export function exportJson(profiles: Profile[]): string {
  return JSON.stringify({ app: "msi-dps", version: EXPORT_VERSION, profiles }, null, 2);
}

/** Parse an exported file (or a single bare profile); throws a readable Error on junk. */
export function parseImport(text: string): Profile[] {
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch {
    throw new Error("Not valid JSON");
  }
  const list = Array.isArray((data as { profiles?: unknown })?.profiles) ? (data as { profiles: unknown[] }).profiles : [data];
  const ok = list.filter(isProfile).map(withArtifacts);
  if (!ok.length) throw new Error("No profiles found in file");
  return ok;
}

export function importProfiles(profiles: Profile[]): number {
  const list = read();
  for (const p of profiles) {
    const existing = list.find((x) => x.name === p.name && x.state.classId === p.state.classId);
    const id = existing?.id ?? p.id;
    const next = { ...p, id, savedAt: p.savedAt || new Date().toISOString() };
    const i = list.findIndex((x) => x.id === id);
    if (i >= 0) list[i] = next;
    else list.push(next);
  }
  write(list);
  return profiles.length;
}

// ---- id-exact helpers for the accounts feature (cloud sync) -----------------------------------------------------------------------------------------

/** Insert or replace profiles by their id (unlike importProfiles this never re-maps an id to a profile with the same name). */
export function upsertProfilesById(profiles: Profile[]): void {
  if (!profiles.length) return;
  const list = read();
  for (const p of profiles) {
    const i = list.findIndex((x) => x.id === p.id);
    if (i >= 0) list[i] = p;
    else list.push(p);
  }
  write(list);
}

export function removeProfilesById(ids: string[]): void {
  if (!ids.length) return;
  const gone = new Set(ids);
  write(read().filter((p) => !gone.has(p.id)));
}

export function clearAllProfiles(): void {
  write([]);
}
