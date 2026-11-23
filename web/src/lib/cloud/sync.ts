// Accounts: the sync CONTROLLER.  Framework-free (the React layer only subscribes to it): it owns the sync metadata of the signed-in account, merges the cloud
// into the local profile list, plans and commits "Save to account", keeps the conflict history, and runs the first-login migration.  All I/O goes through
// ports (local profiles, metadata storage, settings, the CloudDb), so the whole flow runs in tests against in-memory fakes.
//
// Rules (APP_ACCOUNTS_DESIGN.md): local-first (localStorage stays the working copy); the cloud is written ONLY by save() (the "Save to account" button);
// reads happen only in signedIn() / refresh(); there are no listeners.
import type { AccountUser } from "./auth";
import {
  addHistory,
  applyMigrationDecision,
  applySaved,
  cloneMeta,
  dirtyIds,
  emptyMeta,
  localStatuses,
  mergeProfiles,
  mergeSettings,
  planSave,
  settingsDirty,
  settingsHash,
  trackLocalChanges,
  validDocId,
  clipName,
  type HistoryEntry,
  type MigrationDecision,
  type ProfileRec,
  type ProfileSyncStatus,
  type RejectedProfile,
  type SettingsContent,
  type SettingsRec,
  type SyncMeta,
  type SyncNotice,
} from "./merge";
import { buildOps, commitOps, deleteAllData, describeCloudError, exportAllData, loadCloud, type CloudDb, type RetryOptions } from "./store";

export interface LocalPort {
  /** Live local profiles in canonical form. */
  listRecs(): ProfileRec[];
  /** Insert / replace by id (the records are the cloud's, already canonical). */
  put(recs: ProfileRec[]): void;
  remove(ids: string[]): void;
  clear(): void;
  /** Called after every change of the local list (this tab and other tabs); returns the unsubscribe function. */
  subscribe(fn: () => void): () => void;
  /** Canonical form of a cloud record as THIS version of the app understands it (null = not a usable profile). */
  canonical(rec: ProfileRec): ProfileRec | null;
}
export interface MetaPort {
  load(uid: string): SyncMeta | null;
  save(uid: string, meta: SyncMeta): void;
  clear(uid: string): void;
  lastUid(): string | null;
  setLastUid(uid: string | null): void;
  loadHistory(): HistoryEntry[];
  saveHistory(h: HistoryEntry[]): void;
}
export interface SettingsPort {
  read(): SettingsContent;
  /** Apply the account's settings to this device (theme, last class). */
  apply(s: SettingsRec): void;
}
export interface ControllerDeps {
  local: LocalPort;
  meta: MetaPort;
  settings: SettingsPort;
  now?: () => number;
  retry?: RetryOptions;
  newId?: () => string;
}

export type Phase = "signed-out" | "loading" | "ready" | "saving" | "error";

export interface MigrationPrompt {
  first: boolean; // true: the one-time first-login question; false: re-opened from the menu for the "local only" profiles
  candidates: { id: string; name: string; classId: string; updatedAt: number }[];
}

export interface AccountState {
  phase: Phase;
  user: AccountUser | null;
  error: string | null;
  profileErrors: Record<string, string>;
  statuses: Record<string, ProfileSyncStatus>;
  dirtyCount: number; // unsaved profiles (new / edited / deleted)
  settingsDirty: boolean;
  skippedCount: number; // "local only" profiles (not uploaded by choice)
  cloudCount: number; // live profiles in the account, as last seen
  cloudOnly: { id: string; name: string; classId: string }[];
  lastSyncAt: number | null;
  notices: SyncNotice[];
  history: HistoryEntry[];
  migration: MigrationPrompt | null;
}

export interface SaveReport {
  ok: boolean;
  written: number;
  deleted: number;
  rejected: RejectedProfile[];
  error?: string;
  skipped?: "not-ready" | "migration" | "nothing";
}

export class AccountController {
  private deps: Required<Pick<ControllerDeps, "local" | "meta" | "settings">> & { now: () => number; retry?: RetryOptions; newId: () => string };
  private listeners = new Set<() => void>();
  private user: AccountUser | null = null;
  private db: CloudDb | null = null;
  private tracked: string | null; // uid whose deletions we follow (the signed-in one, or the last one while signed out)
  private meta: SyncMeta = emptyMeta();
  private cloud: Record<string, ProfileRec> = {};
  private sweepIds: string[] = [];
  private prevLocal: ProfileRec[] = [];
  private applying = false;
  private chain: Promise<unknown> = Promise.resolve();
  private migrationIds: string[] = [];
  private migrationFirst = false;
  private unsubLocal: (() => void) | null = null;
  private state: AccountState;

  constructor(deps: ControllerDeps) {
    this.deps = { local: deps.local, meta: deps.meta, settings: deps.settings, now: deps.now ?? Date.now, retry: deps.retry, newId: deps.newId ?? (() => `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`) };
    this.tracked = this.deps.meta.lastUid();
    if (this.tracked) this.meta = this.deps.meta.load(this.tracked) ?? emptyMeta();
    this.prevLocal = this.deps.local.listRecs();
    this.state = this.derive("signed-out", null, null, {});
    this.state.history = this.deps.meta.loadHistory();
    this.unsubLocal = this.deps.local.subscribe(() => this.onLocalChange());
  }

  // ---- observable state ---------------------------------------------------------------------------------------------------------------------------

  getState = (): AccountState => this.state;
  subscribe = (fn: () => void): (() => void) => {
    this.listeners.add(fn);
    return () => void this.listeners.delete(fn);
  };
  dispose(): void {
    this.unsubLocal?.();
    this.listeners.clear();
  }

  private emit(patch: Partial<AccountState> = {}): void {
    const s = this.state;
    const phase = patch.phase ?? s.phase;
    const user = patch.user === undefined ? s.user : patch.user;
    const error = patch.error === undefined ? s.error : patch.error;
    const profileErrors = patch.profileErrors ?? s.profileErrors;
    this.state = { ...this.derive(phase, user, error, profileErrors), notices: patch.notices ?? s.notices, history: patch.history ?? s.history, migration: patch.migration === undefined ? s.migration : patch.migration };
    this.listeners.forEach((fn) => fn());
  }

  private derive(phase: Phase, user: AccountUser | null, error: string | null, profileErrors: Record<string, string>): AccountState {
    const recs = this.deps.local.listRecs();
    const pending = new Set(this.migrationIds);
    // profiles waiting for the first-login decision are not "unsaved" yet
    const meta: SyncMeta = pending.size ? { ...this.meta, skipped: { ...this.meta.skipped, ...Object.fromEntries([...pending].map((i) => [i, true as const])) } } : this.meta;
    const statuses = localStatuses(recs, meta);
    for (const id of Object.keys(profileErrors)) if (statuses[id]) statuses[id] = "error";
    const dirty = dirtyIds(recs, meta);
    const liveIds = new Set(recs.map((r) => r.id));
    const pendingDeletes = Object.keys(this.meta.deletes).filter((id) => !liveIds.has(id) && (this.cloud[id] ? !this.cloud[id].deleted : !!this.meta.baseline[id])).length;
    const cloudOnly = Object.values(this.cloud)
      .filter((r) => !r.deleted && !liveIds.has(r.id) && !this.meta.deletes[r.id])
      .map((r) => ({ id: r.id, name: r.name, classId: r.classId }));
    return {
      phase,
      user,
      error,
      profileErrors,
      statuses,
      dirtyCount: user ? dirty.length + pendingDeletes : 0,
      settingsDirty: !!user && settingsDirty(this.deps.settings.read(), this.meta),
      skippedCount: recs.filter((r) => this.meta.skipped[r.id]).length,
      cloudCount: Object.values(this.cloud).filter((r) => !r.deleted).length,
      cloudOnly,
      lastSyncAt: this.meta.lastSyncAt,
      notices: this.state?.notices ?? [],
      history: this.state?.history ?? [],
      migration: this.state?.migration ?? null,
    };
  }

  /** The Settings (theme, last class / profile) may have changed: re-evaluate whether the settings are unsaved. */
  touch(): void {
    if (this.user) this.emit();
  }

  // ---- local changes (deletions are remembered) ----------------------------------------------------------------------------------------------------

  private onLocalChange(): void {
    if (this.applying) return;
    const recs = this.deps.local.listRecs();
    if (this.tracked) {
      const next = trackLocalChanges(recs, this.meta, this.deps.now(), this.prevLocal);
      if (next !== this.meta) {
        this.meta = next;
        this.deps.meta.save(this.tracked, next);
      }
    }
    this.prevLocal = recs;
    this.emit();
  }

  private serial<T>(fn: () => Promise<T>): Promise<T> {
    const run = this.chain.then(fn, fn);
    this.chain = run.catch(() => undefined);
    return run;
  }

  private persist(): void {
    if (this.tracked) this.deps.meta.save(this.tracked, this.meta);
  }

  // ---- sign-in / refresh ---------------------------------------------------------------------------------------------------------------------------

  /** An account is signed in (fresh sign-in or restored session): read the cloud once and merge. */
  signedIn(user: AccountUser, db: CloudDb): Promise<void> {
    return this.serial(async () => {
      this.user = user;
      this.db = db;
      this.tracked = user.uid;
      this.deps.meta.setLastUid(user.uid);
      this.meta = this.deps.meta.load(user.uid) ?? emptyMeta();
      this.prevLocal = this.deps.local.listRecs();
      this.meta = trackLocalChanges(this.prevLocal, this.meta, this.deps.now(), this.prevLocal); // deletions made while signed out were tracked live; this only cleans up
      this.emit({ phase: "loading", user, error: null, profileErrors: {} });
      await this.pull(true);
    });
  }

  /** "Refresh from account": one read per cloud profile + settings, then merge (unsaved local changes are kept unless the cloud is newer). */
  refresh(): Promise<void> {
    return this.serial(async () => {
      if (!this.user || !this.db) return;
      this.emit({ phase: "loading", error: null });
      await this.pull(false);
    });
  }

  private async pull(initial: boolean): Promise<void> {
    const db = this.db!;
    const uid = this.user!.uid;
    let snap;
    try {
      snap = await loadCloud(db, uid, this.deps.retry);
    } catch (e) {
      this.emit({ phase: "error", error: describeCloudError(e).message });
      return;
    }
    const now = this.deps.now();
    const invalid = [...snap.invalid];
    const cloudRecs: ProfileRec[] = [];
    for (const r of Object.values(snap.profiles)) {
      if (r.deleted) {
        cloudRecs.push(r);
        continue;
      }
      const canon = this.deps.local.canonical(r);
      if (canon) cloudRecs.push(canon);
      else invalid.push(r.id);
    }
    const invalidSet = new Set(invalid);
    const local = this.deps.local.listRecs();
    const res = mergeProfiles({ local: local.filter((r) => !invalidSet.has(r.id)), cloud: cloudRecs, meta: this.meta, now });

    this.applying = true;
    try {
      this.deps.local.put(res.download);
      this.deps.local.remove(res.removeLocal);
    } finally {
      this.applying = false;
    }
    let meta = res.meta;
    const sm = mergeSettings(snap.settings, meta);
    meta = sm.meta;
    if (sm.apply) this.deps.settings.apply(sm.apply);

    const history = addHistory(this.state.history, res.history);
    if (res.history.length) this.deps.meta.saveHistory(history);
    const notices: SyncNotice[] = [...this.state.notices, ...res.notices];
    for (const id of invalid) if (!notices.some((n) => n.id === `invalid:${id}`)) notices.push({ id: `invalid:${id}`, kind: "invalid", profileId: id, name: id, message: `A profile in your account could not be read (it may come from a newer version of the app) and was left untouched.` });

    this.cloud = Object.fromEntries(cloudRecs.map((r) => [r.id, r]));
    for (const id of invalid) delete this.cloud[id];
    this.sweepIds = res.sweep;
    this.migrationIds = res.migration;
    this.migrationFirst = res.firstLogin && res.migration.length > 0;
    if (!this.migrationFirst) meta.lastSyncAt = now;
    this.meta = meta;
    this.persist();
    this.prevLocal = this.deps.local.listRecs();
    const migration = this.migrationFirst ? this.migrationPrompt(res.migration, true) : initial ? null : this.state.migration;
    this.emit({ phase: "ready", error: null, notices, history, migration });
  }

  private migrationPrompt(ids: string[], first: boolean): MigrationPrompt {
    const byId = new Map(this.deps.local.listRecs().map((r) => [r.id, r]));
    return { first, candidates: ids.flatMap((id) => (byId.get(id) ? [{ id, name: byId.get(id)!.name, classId: byId.get(id)!.classId, updatedAt: byId.get(id)!.updatedAt }] : [])) };
  }

  // ---- first-login migration -------------------------------------------------------------------------------------------------------------------

  /** Re-open the "upload your local profiles?" question for the profiles that were kept local-only. */
  openMigration(): void {
    const ids = this.deps.local.listRecs().filter((r) => this.meta.skipped[r.id]).map((r) => r.id);
    if (!ids.length) return;
    this.migrationIds = ids;
    this.migrationFirst = false;
    this.emit({ migration: this.migrationPrompt(ids, false) });
  }

  resolveMigration(decision: MigrationDecision): void {
    const wasFirst = this.migrationFirst;
    this.meta = applyMigrationDecision(this.meta, this.migrationIds, decision);
    if (wasFirst) this.meta.lastSyncAt = this.deps.now();
    this.migrationIds = [];
    this.migrationFirst = false;
    this.persist();
    this.emit({ migration: null });
  }

  /** Closing the dialog: the first-login question counts as "not now" (the profiles stay local-only and can be uploaded from the menu later). */
  dismissMigration(): void {
    if (this.state.migration) this.resolveMigration({ kind: "none" });
  }

  // ---- save ----------------------------------------------------------------------------------------------------------------------------------------

  /** "Save to account": ONE batched commit with only the profiles that changed (+ settings if changed).  No reads. */
  save(): Promise<SaveReport> {
    return this.serial(async () => {
      const none = (skipped: SaveReport["skipped"]): SaveReport => ({ ok: false, written: 0, deleted: 0, rejected: [], skipped });
      if (!this.user || !this.db || this.state.phase === "loading") return none("not-ready");
      if (this.migrationFirst) return none("migration");
      const uid = this.user.uid;
      const now = this.deps.now();
      const local = this.deps.local.listRecs().filter((r) => !this.meta.skipped[r.id]);
      const plan = planSave({ local, cloud: this.cloud, meta: this.meta, sweep: this.sweepIds });
      const content = this.deps.settings.read();
      const sDirty = settingsDirty(content, this.meta);
      const settings: SettingsRec | null = sDirty ? { ...content, updatedAt: now } : null;
      const profileErrors = Object.fromEntries(plan.rejected.map((r) => [r.id, r.detail]));
      const nothing = !plan.writes.length && !plan.tombstones.length && !plan.sweep.length && !settings;
      if (nothing) {
        this.emit({ profileErrors, phase: this.state.phase === "error" ? "ready" : this.state.phase, error: null });
        return { ok: true, written: 0, deleted: 0, rejected: plan.rejected, skipped: "nothing" };
      }
      this.emit({ phase: "saving", error: null });
      try {
        await commitOps(this.db, buildOps(uid, plan, { settings, now, createUserDoc: !this.meta.userDocCreated }), this.deps.retry);
      } catch (e) {
        const info = describeCloudError(e);
        this.emit({ phase: "error", error: info.message, profileErrors });
        return { ok: false, written: 0, deleted: 0, rejected: plan.rejected, error: info.message };
      }
      this.meta = applySaved(this.meta, plan, now);
      if (settings) {
        this.meta.settingsHash = settingsHash(settings);
        this.meta.settingsUpdatedAt = settings.updatedAt;
      }
      for (const w of plan.writes) this.cloud[w.id] = w;
      for (const t of plan.tombstones) this.cloud[t.id] = t;
      for (const id of plan.sweep) delete this.cloud[id];
      this.sweepIds = this.sweepIds.filter((id) => !plan.sweep.includes(id));
      this.persist();
      this.emit({ phase: "ready", error: null, profileErrors });
      return { ok: true, written: plan.writes.length, deleted: plan.tombstones.length, rejected: plan.rejected };
    });
  }

  // ---- notices, history ----------------------------------------------------------------------------------------------------------------------------

  dismissNotice(id: string): void {
    this.emit({ notices: this.state.notices.filter((n) => n.id !== id) });
  }
  dismissAllNotices(): void {
    this.emit({ notices: [] });
  }

  /** Put a history version back as a NEW local profile (it becomes an unsaved profile); the entry is removed from the history. */
  restoreHistory(key: string): string | null {
    const e = this.state.history.find((h) => h.key === key);
    if (!e) return null;
    const id = this.deps.newId();
    if (!validDocId(id)) return null;
    this.deps.local.put([{ id, classId: e.classId, name: clipName(`${e.name} (restored)`), updatedAt: this.deps.now(), state: e.state }]);
    this.discardHistory(key);
    return id;
  }

  discardHistory(key: string): void {
    const history = this.state.history.filter((h) => h.key !== key);
    this.deps.meta.saveHistory(history);
    this.emit({ history });
  }

  // ---- sign-out, export, delete --------------------------------------------------------------------------------------------------------------------

  /** Leave the account in this browser.  `clearLocal` also removes this browser's profiles, sync data and history; otherwise the profiles stay as signed-out ones. */
  leave(clearLocal: boolean): void {
    const uid = this.user?.uid ?? this.tracked;
    this.user = null;
    this.db = null;
    this.cloud = {};
    this.sweepIds = [];
    this.migrationIds = [];
    this.migrationFirst = false;
    if (clearLocal) {
      this.applying = true;
      try {
        this.deps.local.clear();
      } finally {
        this.applying = false;
      }
      if (uid) this.deps.meta.clear(uid);
      this.deps.meta.setLastUid(null);
      this.deps.meta.saveHistory([]);
      this.tracked = null;
      this.meta = emptyMeta();
      this.prevLocal = [];
      this.emit({ phase: "signed-out", user: null, error: null, profileErrors: {}, notices: [], history: [], migration: null });
    } else {
      this.prevLocal = this.deps.local.listRecs();
      this.emit({ phase: "signed-out", user: null, error: null, profileErrors: {}, notices: [], migration: null });
    }
  }

  /** The data of the account as a JSON-able object (one read per document). */
  exportAll(): Promise<unknown> {
    if (!this.user || !this.db) return Promise.reject(new Error("Not signed in"));
    return exportAllData(this.db, this.user.uid, { email: this.user.email }, this.deps.now());
  }

  /** Delete every cloud document of the account (the caller deletes the Auth user afterwards).  Local copies stay as ordinary signed-out profiles. */
  deleteCloudData(): Promise<number> {
    return this.serial(async () => {
      if (!this.user || !this.db) throw new Error("Not signed in");
      const uid = this.user.uid;
      const n = await deleteAllData(this.db, uid, this.deps.retry);
      this.deps.meta.clear(uid);
      this.deps.meta.setLastUid(null);
      this.tracked = null;
      this.meta = emptyMeta();
      this.cloud = {};
      return n;
    });
  }

  /** Unlike leave(): called after the account is gone. */
  accountDeleted(): void {
    this.leave(false);
  }

  /** Meta of the current account (read-only copy; for tests and diagnostics). */
  debugMeta(): SyncMeta {
    return cloneMeta(this.meta);
  }
}
