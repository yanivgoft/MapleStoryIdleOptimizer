// Accounts: the Firestore side, behind a tiny interface (CloudDb) so that everything above it is testable with an in-memory fake.
//
// Read/write budget (see APP_ACCOUNTS_DESIGN.md "Cost and limits"):
//   - sign-in / "Refresh from account": ONE getDocs of users/{uid}/profiles (one read per document, tombstones included) + ONE getDoc of settings/app
//   - "Save to account": ONE batched commit (profiles that changed, pending deletions as tombstones, expired tombstones deleted, settings if changed, the user doc)
//   - NO live listeners (no onSnapshot anywhere), no per-edit writes
// Offline persistence of the Firestore SDK is deliberately NOT enabled: the dirty state is persisted by us (localStorage) and a failed Save is simply
// recomputed and retried, so IndexedDB would only leave a copy of the user's data behind on a shared computer.
import { MAX_NAME_CHARS, clipName, type ProfileRec, type SavePlan, type SettingsRec, type ThemeSetting } from "./merge";

export const USER_SCHEMA = 1; // users/{uid}.schema; bump together with lib/profiles.ts EXPORT_VERSION when the stored profile format changes
export const COMMIT_CHUNK = 400; // Firestore allows 500 operations per batch

export interface RawDoc {
  id: string;
  data: Record<string, unknown>;
}
export type DbOp = { type: "set"; path: string; data: Record<string, unknown>; merge?: boolean } | { type: "delete"; path: string };

export interface CloudDb {
  readProfiles(uid: string): Promise<RawDoc[]>;
  readSettings(uid: string): Promise<RawDoc | null>;
  readUser(uid: string): Promise<RawDoc | null>;
  commit(ops: DbOp[]): Promise<void>;
}

export const userPath = (uid: string) => `users/${uid}`;
export const profilesPath = (uid: string) => `users/${uid}/profiles`;
export const profilePath = (uid: string, id: string) => `users/${uid}/profiles/${id}`;
export const settingsPath = (uid: string) => `users/${uid}/settings/app`;

// ---- documents <-> records -----------------------------------------------------------------------------------------------------------------------

/** users/{uid}/profiles/{profileId}: {classId, name, updatedAt, deleted?, state}.  `state` is the canonical JSON string of the exported FormState (a string, not a
 *  map: Firestore rejects nested arrays and undefined, indexes every map field, and a future shape change of the profile can never make a save fail). */
export function profileDoc(r: ProfileRec): Record<string, unknown> {
  const doc: Record<string, unknown> = { classId: r.classId, name: clipName(r.name), updatedAt: r.updatedAt, state: r.deleted ? "" : r.state };
  if (r.deleted) doc.deleted = true;
  return doc;
}

export function parseProfileDoc(id: string, d: Record<string, unknown>): ProfileRec | null {
  if (typeof d.classId !== "string" || typeof d.name !== "string" || typeof d.updatedAt !== "number" || typeof d.state !== "string") return null;
  if (d.deleted !== undefined && typeof d.deleted !== "boolean") return null;
  const rec: ProfileRec = { id, classId: d.classId, name: d.name.slice(0, MAX_NAME_CHARS), updatedAt: d.updatedAt, state: d.state };
  if (d.deleted === true) rec.deleted = true;
  else if (!d.state) return null;
  return rec;
}

const THEMES: ThemeSetting[] = ["auto", "light", "dark"];

export function settingsDoc(s: SettingsRec): Record<string, unknown> {
  const doc: Record<string, unknown> = { theme: s.theme, updatedAt: s.updatedAt };
  if (s.lastClassId) doc.lastClassId = s.lastClassId.slice(0, 64);
  if (s.lastProfileId) doc.lastProfileId = s.lastProfileId.slice(0, 64);
  return doc;
}

export function parseSettingsDoc(d: Record<string, unknown>): SettingsRec | null {
  if (typeof d.updatedAt !== "number" || !THEMES.includes(d.theme as ThemeSetting)) return null;
  const s: SettingsRec = { theme: d.theme as ThemeSetting, updatedAt: d.updatedAt };
  if (typeof d.lastClassId === "string") s.lastClassId = d.lastClassId;
  if (typeof d.lastProfileId === "string") s.lastProfileId = d.lastProfileId;
  return s;
}

// ---- reads -----------------------------------------------------------------------------------------------------------------------------------------

export interface CloudSnapshot {
  profiles: Record<string, ProfileRec>; // live and tombstones
  invalid: string[]; // documents that did not parse (never overwritten by a merge)
  settings: SettingsRec | null;
  reads: number; // documents read
}

/** The whole account: one query for the profiles + one document read for the settings (no listeners). */
export async function loadCloud(db: CloudDb, uid: string, retry?: RetryOptions): Promise<CloudSnapshot> {
  const [docs, sdoc] = await withRetry(() => Promise.all([db.readProfiles(uid), db.readSettings(uid)]), retry);
  const profiles: Record<string, ProfileRec> = {};
  const invalid: string[] = [];
  for (const d of docs) {
    const r = parseProfileDoc(d.id, d.data);
    if (r) profiles[d.id] = r;
    else invalid.push(d.id);
  }
  return { profiles, invalid, settings: sdoc ? parseSettingsDoc(sdoc.data) : null, reads: docs.length + 1 };
}

// ---- writes ----------------------------------------------------------------------------------------------------------------------------------------

export interface SaveExtras {
  settings?: SettingsRec | null; // written only when it changed
  now: number;
  createUserDoc: boolean; // first save of this account: also write createdAt
}

/** The operations of one "Save to account": changed profiles (full replace), tombstones, expired tombstones removed, settings if changed, the user document. */
export function buildOps(uid: string, plan: SavePlan, extras: SaveExtras): DbOp[] {
  const ops: DbOp[] = [];
  for (const r of plan.writes) ops.push({ type: "set", path: profilePath(uid, r.id), data: profileDoc(r) });
  for (const t of plan.tombstones) ops.push({ type: "set", path: profilePath(uid, t.id), data: profileDoc(t) });
  for (const id of plan.sweep) ops.push({ type: "delete", path: profilePath(uid, id) });
  if (extras.settings) ops.push({ type: "set", path: settingsPath(uid), data: settingsDoc(extras.settings) });
  const user: Record<string, unknown> = { lastSeenAt: extras.now, schema: USER_SCHEMA };
  if (extras.createUserDoc) user.createdAt = extras.now;
  ops.push({ type: "set", path: userPath(uid), data: user, merge: true });
  return ops;
}

/** Commits in batches of at most COMMIT_CHUNK operations (one batch for any normal save), each retried on transient errors. */
export async function commitOps(db: CloudDb, ops: DbOp[], retry?: RetryOptions): Promise<number> {
  let batches = 0;
  for (let i = 0; i < ops.length; i += COMMIT_CHUNK) {
    const part = ops.slice(i, i + COMMIT_CHUNK);
    await withRetry(() => db.commit(part), retry);
    batches++;
  }
  return batches;
}

/** Everything that is stored for the account, as one JSON-able object (the "Download all my data" file).  Costs one read per document. */
export async function exportAllData(db: CloudDb, uid: string, account: { email: string | null }, now: number): Promise<unknown> {
  const [docs, settings, user] = await Promise.all([db.readProfiles(uid), db.readSettings(uid), db.readUser(uid)]);
  const profiles = docs.map((d) => {
    const r = parseProfileDoc(d.id, d.data);
    let state: unknown = r?.state ?? d.data.state ?? null;
    try {
      if (typeof state === "string" && state) state = JSON.parse(state);
    } catch {
      /* keep the raw text */
    }
    return { id: d.id, classId: d.data.classId, name: d.data.name, updatedAt: d.data.updatedAt, deleted: d.data.deleted === true, state };
  });
  return { app: "msi-dps", kind: "account-export", exportedAt: new Date(now).toISOString(), account: { uid, email: account.email }, user: user?.data ?? null, settings: settings?.data ?? null, profiles };
}

/** Deletes every document of the account (profiles incl. tombstones, settings, the user document).  Returns how many documents were deleted. */
export async function deleteAllData(db: CloudDb, uid: string, retry?: RetryOptions): Promise<number> {
  const docs = await withRetry(() => db.readProfiles(uid), retry);
  const ops: DbOp[] = docs.map((d) => ({ type: "delete", path: profilePath(uid, d.id) }));
  ops.push({ type: "delete", path: settingsPath(uid) }, { type: "delete", path: userPath(uid) });
  await commitOps(db, ops, retry);
  return ops.length;
}

// ---- errors and retries -------------------------------------------------------------------------------------------------------------------------------

export interface CloudErrorInfo {
  message: string;
  transient: boolean; // worth retrying (offline, server busy)
  kind: "offline" | "permission" | "quota" | "auth" | "timeout" | "other";
}

export function describeCloudError(e: unknown): CloudErrorInfo {
  const code = String((e as { code?: unknown })?.code ?? "").replace(/^firestore\//, "");
  const text = String((e as { message?: unknown })?.message ?? e ?? "");
  if (code === "timeout" || /timed out/i.test(text)) return { kind: "timeout", transient: true, message: "The server did not answer in time. Your changes are still unsaved here; try again in a moment." };
  if (code === "unavailable" || code === "deadline-exceeded" || code === "aborted" || code === "network-request-failed" || /network|offline|failed to fetch/i.test(text))
    return { kind: "offline", transient: true, message: "Could not reach your account (offline or the service is busy). Your changes are still unsaved here and will be retried." };
  if (code === "permission-denied") return { kind: "permission", transient: false, message: "The server refused the request (permission denied). Sign out and in again; if it keeps happening the account rules may not be deployed yet." };
  if (code === "unauthenticated" || code === "requires-recent-login" || code === "user-token-expired") return { kind: "auth", transient: false, message: "Your sign-in has expired. Sign in again." };
  if (code === "resource-exhausted") return { kind: "quota", transient: false, message: "The daily free quota of the service is used up. Try again later (your changes stay on this device)." };
  return { kind: "other", transient: false, message: `Something went wrong (${text || code || "unknown error"}).` };
}

export interface RetryOptions {
  attempts?: number; // total tries (default 3)
  delaysMs?: number[]; // wait before 2nd, 3rd ... try (default 600, 2000)
  sleep?: (ms: number) => Promise<void>;
  timeoutMs?: number; // per try (default 20 000); offline the SDK's promises can stay pending forever
}

export async function withRetry<T>(fn: () => Promise<T>, opts: RetryOptions = {}): Promise<T> {
  const attempts = opts.attempts ?? 3;
  const delays = opts.delaysMs ?? [600, 2000];
  const sleep = opts.sleep ?? ((ms: number) => new Promise<void>((r) => setTimeout(r, ms)));
  let last: unknown;
  for (let i = 0; i < attempts; i++) {
    try {
      return await withTimeout(fn(), opts.timeoutMs ?? 20_000);
    } catch (e) {
      last = e;
      if (!describeCloudError(e).transient || i === attempts - 1) break;
      await sleep(delays[Math.min(i, delays.length - 1)] ?? 1000);
    }
  }
  throw last;
}

function withTimeout<T>(p: Promise<T>, ms: number): Promise<T> {
  if (!Number.isFinite(ms) || ms <= 0) return p;
  return new Promise<T>((resolve, reject) => {
    const t = setTimeout(() => reject(Object.assign(new Error("timed out"), { code: "timeout" })), ms);
    p.then(
      (v) => {
        clearTimeout(t);
        resolve(v);
      },
      (e) => {
        clearTimeout(t);
        reject(e);
      },
    );
  });
}
