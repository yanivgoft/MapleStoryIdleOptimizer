// Accounts: the PURE sync logic (no React, no Firebase, no storage).  Everything the account feature decides is decided here, so it can be tested
// exhaustively: merging the local and the cloud profile sets, soft deletes, conflicts + the local history slot, dirty tracking, the first-login
// migration, the 50-profile cap and the document-size guard.  See APP_ACCOUNTS_DESIGN.md ("Sync behaviour") for the rules this implements.
//
// Vocabulary
//   rec        a profile as it is stored in the cloud: {id, classId, name, updatedAt, deleted?, state}; `state` is the profile's FormState as a CANONICAL
//              JSON string (sorted keys), so "same content" is a string comparison and the document is one indexed field.
//   baseline   per profile id, the hash + updatedAt of the version we last saw in the cloud (written by us or read from it).  A local profile whose hash
//              differs from its baseline is DIRTY (unsaved); a local profile without a baseline is new.
//   deletes    local deletions not yet saved (they become tombstones, `deleted: true`, on the next Save).
//   skipped    ids the user chose NOT to upload at the first-login migration ("local only").

export const MAX_PROFILES = 50; // live profiles per account (client-side cap; Firestore rules cannot count a collection)
export const TOMBSTONE_TTL_MS = 30 * 24 * 3600 * 1000; // soft-deleted profiles are purged by the client sweep after 30 days
export const MAX_NAME_CHARS = 80; // = the rules' name.size() <= 80
export const MAX_STATE_CHARS = 180_000; // = the rules' state.size() <= 180000 (< 200 KB document limit of the design, far below Firestore's 1 MiB)
export const HISTORY_MAX = 20; // losing versions kept locally
export const HISTORY_MAX_CHARS = 1_500_000; // ... and at most this many characters of state in total (localStorage is ~5 MB)

export interface ProfileRec {
  id: string;
  classId: string;
  name: string;
  updatedAt: number; // epoch ms
  deleted?: boolean;
  state: string; // canonical JSON of FormState ("" for a tombstone)
}

export interface BaselineEntry {
  hash: string;
  updatedAt: number;
}
export interface PendingDelete {
  at: number;
  classId: string;
  name: string;
}
export interface SyncMeta {
  v: 1;
  baseline: Record<string, BaselineEntry>;
  deletes: Record<string, PendingDelete>;
  skipped: Record<string, true>;
  settingsHash: string | null; // hash of the settings content last written to / applied from the cloud
  settingsUpdatedAt: number | null; // updatedAt of the cloud settings document we last saw
  userDocCreated: boolean;
  lastSyncAt: number | null; // null = this account was never synced on this browser = "first login"
}

export const emptyMeta = (): SyncMeta => ({ v: 1, baseline: {}, deletes: {}, skipped: {}, settingsHash: null, settingsUpdatedAt: null, userDocCreated: false, lastSyncAt: null });

export function cloneMeta(m: SyncMeta): SyncMeta {
  return JSON.parse(JSON.stringify(m)) as SyncMeta;
}

export type HistoryReason = "replaced-by-cloud" | "replaced-by-local" | "deleted-elsewhere";
export interface HistoryEntry {
  key: string; // unique
  profileId: string;
  name: string;
  classId: string;
  state: string; // canonical JSON
  versionUpdatedAt: number; // updatedAt of the version that LOST
  at: number; // when it was replaced
  reason: HistoryReason;
}

export type NoticeKind = "conflict" | "updated" | "deleted" | "restored" | "invalid";
export interface SyncNotice {
  id: string;
  kind: NoticeKind;
  profileId: string;
  name: string;
  message: string;
}

// ---- canonical JSON + hash -------------------------------------------------------------------------------------------------------------------------

/** JSON.stringify with sorted keys (recursively); undefined / functions are dropped, non-finite numbers become null, exactly like JSON.stringify. */
export function stableStringify(value: unknown): string {
  if (value === null || typeof value === "number" || typeof value === "boolean" || typeof value === "string") return JSON.stringify(value) ?? "null";
  if (Array.isArray(value)) return `[${value.map((v) => (v === undefined || typeof v === "function" ? "null" : stableStringify(v))).join(",")}]`;
  if (typeof value === "object" && value) {
    const o = value as Record<string, unknown>;
    const parts: string[] = [];
    for (const k of Object.keys(o).sort()) {
      const v = o[k];
      if (v === undefined || typeof v === "function") continue;
      parts.push(`${JSON.stringify(k)}:${stableStringify(v)}`);
    }
    return `{${parts.join(",")}}`;
  }
  return "null";
}

/** cyrb53 (53-bit string hash) as 14 hex digits: not cryptographic, only used to tell "changed" from "unchanged". */
export function hashString(s: string, seed = 0): string {
  let h1 = 0xdeadbeef ^ seed;
  let h2 = 0x41c6ce57 ^ seed;
  for (let i = 0; i < s.length; i++) {
    const ch = s.charCodeAt(i);
    h1 = Math.imul(h1 ^ ch, 2654435761);
    h2 = Math.imul(h2 ^ ch, 1597334677);
  }
  h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909);
  h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909);
  const n = 4294967296 * (2097151 & h2) + (h1 >>> 0);
  return n.toString(16).padStart(14, "0");
}

export const clipName = (name: string): string => {
  const t = (name ?? "").trim() || "Unnamed";
  return t.length > MAX_NAME_CHARS ? t.slice(0, MAX_NAME_CHARS) : t;
};

/** Hash of the CONTENT of a live profile (name + class + state); the id and the timestamp are not content. */
export function contentHash(r: Pick<ProfileRec, "name" | "classId" | "state">): string {
  return hashString(`${r.name}\u0000${r.classId}\u0000${r.state}`);
}

/** Size guard of the design: the state string must stay below MAX_STATE_CHARS (the rules enforce the same number). */
export function stateTooLarge(r: Pick<ProfileRec, "state">): boolean {
  return r.state.length > MAX_STATE_CHARS;
}

// ---- dirty tracking --------------------------------------------------------------------------------------------------------------------------------

export type ProfileSyncStatus = "synced" | "unsaved" | "local-only" | "cloud-only" | "error";

/** Ids of local profiles that differ from what the cloud holds (never uploaded, or edited since the last save); skipped ("local only") ones never count. */
export function dirtyIds(local: ProfileRec[], meta: SyncMeta): string[] {
  const out: string[] = [];
  for (const r of local) {
    if (meta.skipped[r.id]) continue;
    const b = meta.baseline[r.id];
    if (!b || b.hash !== contentHash(r)) out.push(r.id);
  }
  return out;
}

/** Per local profile: synced / unsaved / local-only. (`error` is overlaid by the controller from the last failed save.) */
export function localStatuses(local: ProfileRec[], meta: SyncMeta): Record<string, ProfileSyncStatus> {
  const dirty = new Set(dirtyIds(local, meta));
  const out: Record<string, ProfileSyncStatus> = {};
  for (const r of local) out[r.id] = meta.skipped[r.id] ? "local-only" : dirty.has(r.id) ? "unsaved" : "synced";
  return out;
}

/** Notices that a profile known to the baseline has disappeared locally: remember it as a pending deletion (called whenever the local list changes while an
 *  account is tracked).  A deleted id that comes back (re-created by the same id, e.g. an import) cancels its pending deletion.  Returns a NEW meta when something changed. */
export function trackLocalChanges(local: ProfileRec[], meta: SyncMeta, now: number, previous: ProfileRec[] = []): SyncMeta {
  const ids = new Set(local.map((r) => r.id));
  let next: SyncMeta | null = null;
  const edit = () => (next ??= cloneMeta(meta));
  for (const id of Object.keys(meta.baseline)) {
    if (!ids.has(id) && !meta.deletes[id]) {
      const known = previous.find((r) => r.id === id);
      edit().deletes[id] = { at: now, classId: known?.classId ?? "", name: known?.name ?? "Unnamed" };
    }
  }
  for (const id of Object.keys(meta.deletes)) if (ids.has(id)) delete edit().deletes[id];
  for (const id of Object.keys(meta.skipped)) if (!ids.has(id)) delete edit().skipped[id];
  return next ?? meta;
}

// ---- merge ----------------------------------------------------------------------------------------------------------------------------------------

export interface MergeInput {
  local: ProfileRec[]; // live local profiles (canonical)
  cloud: ProfileRec[]; // every cloud profile document, live and tombstones (canonical states)
  meta: SyncMeta;
  now: number;
}

export interface MergeResult {
  download: ProfileRec[]; // cloud versions to write into the local list (replace by id)
  removeLocal: string[]; // local ids to delete (deleted on another device)
  history: HistoryEntry[]; // versions that lost and must be kept locally
  notices: SyncNotice[];
  meta: SyncMeta;
  migration: string[]; // FIRST LOGIN ONLY: local profiles that exist nowhere in the cloud; the user decides whether they are uploaded
  sweep: string[]; // cloud tombstones older than 30 days (deleted by the next Save)
  firstLogin: boolean;
}

let noticeSeq = 0;
const nid = (kind: string, id: string, now: number) => `${kind}:${id}:${now}:${noticeSeq++}`;
const hist = (r: ProfileRec, reason: HistoryReason, now: number): HistoryEntry => ({
  key: `${r.id}:${r.updatedAt}:${reason}:${now}`,
  profileId: r.id,
  name: r.name,
  classId: r.classId,
  state: r.state,
  versionUpdatedAt: r.updatedAt,
  at: now,
  reason,
});

/** Merge the local profile set with the cloud's by profileId (updatedAt, last write wins).  Pure: the caller applies `download` / `removeLocal`, stores `meta`
 *  and `history`, and the profiles that are left dirty are uploaded by the next Save.
 *
 *  per id (L local live, C cloud doc, D pending local deletion, B baseline = the cloud version we last saw):
 *   - L only                   first login: offered for migration; later: simply new (dirty, uploaded by Save)
 *   - C only (live)            downloaded; (tombstone) ignored (and swept once older than 30 days)
 *   - L and C, same content    in sync
 *   - L and C differ           only the cloud changed since B -> take the cloud ("updated from another device"); only local changed -> keep local (dirty);
 *                              BOTH changed (or no B) -> newer updatedAt wins (a tie goes to the cloud), the loser is kept in the local history, a notice says so
 *   - L and C tombstone        local unchanged since B, or the tombstone is not older -> delete locally (copy to history); a newer local edit survives and is re-uploaded
 *   - D and C live             edited in the cloud after the deletion -> the edit survives ("restored"); otherwise the deletion is uploaded as a tombstone */
export function mergeProfiles({ local, cloud, meta: meta0, now }: MergeInput): MergeResult {
  const meta = cloneMeta(meta0);
  const firstLogin = meta.lastSyncAt === null;
  const L = new Map(local.map((r) => [r.id, r]));
  const C = new Map(cloud.map((r) => [r.id, r]));
  const ids = new Set<string>([...L.keys(), ...C.keys(), ...Object.keys(meta.deletes)]);
  const res: MergeResult = { download: [], removeLocal: [], history: [], notices: [], meta, migration: [], sweep: [], firstLogin };
  const take = (c: ProfileRec) => {
    res.download.push(c);
    meta.baseline[c.id] = { hash: contentHash(c), updatedAt: c.updatedAt };
  };

  for (const id of [...ids].sort()) {
    const l = L.get(id);
    const c = C.get(id);
    const d = meta.deletes[id];
    const b = meta.baseline[id];

    if (d && !l) {
      // a local deletion that has not been saved yet
      if (!c || c.deleted) {
        delete meta.deletes[id];
        delete meta.baseline[id];
      } else if (!b || contentHash(c) !== b.hash) {
        if (c.updatedAt > d.at) {
          delete meta.deletes[id];
          take(c);
          res.notices.push({ id: nid("restored", id, now), kind: "restored", profileId: id, name: c.name, message: `"${c.name}" was deleted here but edited on another device afterwards, so it was kept.` });
        }
      }
      continue;
    }
    if (d && l) delete meta.deletes[id]; // re-created: the profile exists again

    if (l && !c) {
      delete meta.baseline[id]; // the cloud no longer has it (never uploaded, or purged): it is new again
      if (firstLogin && !meta.skipped[id]) res.migration.push(id);
      continue;
    }
    if (!l && c) {
      if (c.deleted) {
        if (now - c.updatedAt > TOMBSTONE_TTL_MS) res.sweep.push(id);
        delete meta.baseline[id];
      } else take(c);
      continue;
    }
    if (!l || !c) continue;

    const hl = contentHash(l);
    if (c.deleted) {
      if (now - c.updatedAt > TOMBSTONE_TTL_MS) res.sweep.push(id);
      const localUnchanged = !!b && b.hash === hl;
      if (localUnchanged || c.updatedAt >= l.updatedAt) {
        res.removeLocal.push(id);
        res.history.push(hist(l, "deleted-elsewhere", now));
        res.notices.push({ id: nid("deleted", id, now), kind: "deleted", profileId: id, name: l.name, message: `"${l.name}" was deleted on another device and was removed here (a copy is in the history).` });
        delete meta.baseline[id];
      } else {
        delete meta.baseline[id]; // edited here after it was deleted elsewhere: keep it and upload it again
      }
      continue;
    }

    const hc = contentHash(c);
    if (hl === hc) {
      meta.baseline[id] = { hash: hc, updatedAt: c.updatedAt };
      delete meta.skipped[id];
      continue;
    }
    const localChanged = !b || b.hash !== hl;
    const cloudChanged = !b || b.hash !== hc;
    if (localChanged && !cloudChanged) {
      meta.baseline[id] = { hash: hc, updatedAt: c.updatedAt }; // the cloud is unchanged: local stays dirty
    } else if (!localChanged && cloudChanged) {
      take(c);
      res.notices.push({ id: nid("updated", id, now), kind: "updated", profileId: id, name: c.name, message: `"${c.name}" was updated from another device.` });
    } else {
      const cloudWins = c.updatedAt >= l.updatedAt;
      if (cloudWins) {
        take(c);
        res.history.push(hist(l, "replaced-by-cloud", now));
        res.notices.push({ id: nid("conflict", id, now), kind: "conflict", profileId: id, name: c.name, message: `"${c.name}" was edited on two devices: the newer version from your account was kept; your version here is in the history.` });
      } else {
        meta.baseline[id] = { hash: hc, updatedAt: c.updatedAt }; // local stays dirty and overwrites the cloud version on the next Save
        res.history.push(hist(c, "replaced-by-local", now));
        res.notices.push({ id: nid("conflict", id, now), kind: "conflict", profileId: id, name: l.name, message: `"${l.name}" was edited on two devices: your newer version here will replace the one in your account on the next Save (the account version is in the history).` });
      }
    }
  }
  return res;
}

// ---- first-login migration -------------------------------------------------------------------------------------------------------------------------

export type MigrationDecision = { kind: "all" } | { kind: "none" } | { kind: "choose"; ids: string[] };

/** Applies the user's answer to "upload your N local profiles?": the profiles that are not uploaded become "local only" (skipped); the others simply stay
 *  dirty (no baseline) and are written by the next Save.  `candidates` is the list that was offered. */
export function applyMigrationDecision(meta: SyncMeta, candidates: string[], decision: MigrationDecision): SyncMeta {
  const m = cloneMeta(meta);
  const chosen = new Set(decision.kind === "all" ? candidates : decision.kind === "choose" ? decision.ids.filter((i) => candidates.includes(i)) : []);
  for (const id of candidates) {
    if (chosen.has(id)) delete m.skipped[id];
    else m.skipped[id] = true;
  }
  return m;
}

// ---- save plan ------------------------------------------------------------------------------------------------------------------------------------

export interface RejectedProfile {
  id: string;
  name: string;
  reason: "too-large" | "over-cap" | "bad-id";
  detail: string; // friendly sentence
}

/** Firestore document ids the rules accept (rules: pid.matches('^[A-Za-z0-9_-]{1,64}$')). */
export const validDocId = (id: string): boolean => /^[A-Za-z0-9_-]{1,64}$/.test(id);

export interface SavePlan {
  writes: ProfileRec[]; // live documents to write (only the dirty ones)
  tombstones: ProfileRec[]; // soft deletes to write
  sweep: string[]; // expired tombstones to delete for good
  rejected: RejectedProfile[]; // dirty profiles that cannot be saved (and why); they stay unsaved, with an error shown
  cloudLiveCount: number; // live documents in the account after this save
}

export interface PlanInput {
  local: ProfileRec[];
  cloud: Record<string, ProfileRec>; // the cloud documents as last read / written (live + tombstones)
  meta: SyncMeta;
  sweep?: string[];
  cap?: number;
}

/** What the "Save to account" button writes: ONLY the profiles that changed since the last save, the pending deletions as tombstones, the expired tombstones
 *  as deletions.  Profiles over the size guard or over the 50-profile cap are left out (and reported), never silently dropped. */
export function planSave({ local, cloud, meta, sweep = [], cap = MAX_PROFILES }: PlanInput): SavePlan {
  const dirty = new Set(dirtyIds(local, meta));
  const byId = new Map(local.map((r) => [r.id, r]));
  const tombstones: ProfileRec[] = [];
  for (const [id, d] of Object.entries(meta.deletes)) {
    if (byId.has(id)) continue;
    const prev = cloud[id];
    if (prev?.deleted) continue; // already a tombstone
    if (!prev && !meta.baseline[id]) continue; // never reached the cloud
    tombstones.push({ id, classId: prev?.classId || d.classId || "unknown", name: clipName(prev?.name ?? d.name), updatedAt: Math.max(d.at, (meta.baseline[id]?.updatedAt ?? 0) + 1), deleted: true, state: "" });
  }
  const tombIds = new Set(tombstones.map((t) => t.id));
  let live = Object.values(cloud).filter((r) => !r.deleted && !tombIds.has(r.id)).length;

  const writes: ProfileRec[] = [];
  const rejected: RejectedProfile[] = [];
  // newest first, so that when the cap bites it is the oldest new profiles that wait
  const candidates = local.filter((r) => dirty.has(r.id)).sort((a, b) => b.updatedAt - a.updatedAt || a.id.localeCompare(b.id));
  for (const r of candidates) {
    if (!validDocId(r.id)) {
      rejected.push({ id: r.id, name: r.name, reason: "bad-id", detail: `"${r.name}" has an id that cannot be stored in an account (re-save it under the same name or import it again).` });
      continue;
    }
    if (stateTooLarge(r)) {
      rejected.push({ id: r.id, name: r.name, reason: "too-large", detail: `"${r.name}" is too large to save to your account (${Math.round(r.state.length / 1000)} KB; the limit is ${Math.round(MAX_STATE_CHARS / 1000)} KB). It stays on this device.` });
      continue;
    }
    const known = cloud[r.id] && !cloud[r.id].deleted;
    if (!known) {
      if (live >= cap) {
        rejected.push({ id: r.id, name: r.name, reason: "over-cap", detail: `"${r.name}" was not saved: an account holds at most ${cap} profiles. Delete a profile you no longer need, then save again.` });
        continue;
      }
      live++;
    }
    const base = meta.baseline[r.id]?.updatedAt ?? cloud[r.id]?.updatedAt ?? 0;
    writes.push({ id: r.id, classId: r.classId, name: clipName(r.name), updatedAt: Math.max(r.updatedAt, base + 1), state: r.state });
  }
  return { writes, tombstones, sweep: sweep.filter((id) => cloud[id]?.deleted), rejected, cloudLiveCount: live };
}

/** Meta after a successful commit of `plan`. */
export function applySaved(meta: SyncMeta, plan: SavePlan, now: number): SyncMeta {
  const m = cloneMeta(meta);
  for (const w of plan.writes) m.baseline[w.id] = { hash: contentHash(w), updatedAt: w.updatedAt };
  for (const t of plan.tombstones) {
    delete m.baseline[t.id];
    delete m.deletes[t.id];
  }
  m.userDocCreated = true;
  m.lastSyncAt = now;
  return m;
}

// ---- settings --------------------------------------------------------------------------------------------------------------------------------------

export type ThemeSetting = "auto" | "light" | "dark";
export interface SettingsContent {
  theme: ThemeSetting;
  lastClassId?: string;
  lastProfileId?: string;
}
export interface SettingsRec extends SettingsContent {
  updatedAt: number;
}

export const settingsHash = (s: SettingsContent): string => hashString(stableStringify({ theme: s.theme, lastClassId: s.lastClassId ?? null, lastProfileId: s.lastProfileId ?? null }));

export interface SettingsMerge {
  apply: SettingsRec | null; // cloud settings to apply to this device (theme, last class)
  meta: SyncMeta;
}

/** On sign-in / refresh: the cloud settings are applied when they are newer than what this device last synced (a new device adopts them); otherwise nothing. */
export function mergeSettings(cloud: SettingsRec | null, meta0: SyncMeta): SettingsMerge {
  const meta = cloneMeta(meta0);
  if (cloud && (meta.settingsUpdatedAt === null || cloud.updatedAt > meta.settingsUpdatedAt)) {
    meta.settingsUpdatedAt = cloud.updatedAt;
    meta.settingsHash = settingsHash(cloud);
    return { apply: cloud, meta };
  }
  return { apply: null, meta };
}

/** Settings are "dirty" when the current content differs from what was last written / applied (does not count as an unsaved-changes warning). */
export function settingsDirty(current: SettingsContent, meta: SyncMeta): boolean {
  return meta.settingsHash !== settingsHash(current);
}

// ---- history ---------------------------------------------------------------------------------------------------------------------------------------

/** Newest first, at most HISTORY_MAX entries and HISTORY_MAX_CHARS of state in total; an entry equal to an older one (same profile + same content) is not repeated. */
export function addHistory(existing: HistoryEntry[], added: HistoryEntry[]): HistoryEntry[] {
  const out: HistoryEntry[] = [];
  const seen = new Set<string>();
  for (const e of [...added, ...existing]) {
    const sig = `${e.profileId}\u0000${hashString(e.state)}`;
    if (seen.has(sig)) continue;
    seen.add(sig);
    out.push(e);
  }
  let chars = 0;
  const kept: HistoryEntry[] = [];
  for (const e of out) {
    if (kept.length >= HISTORY_MAX || chars + e.state.length > HISTORY_MAX_CHARS) break;
    chars += e.state.length;
    kept.push(e);
  }
  return kept;
}
