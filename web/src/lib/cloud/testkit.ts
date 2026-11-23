// Test-only fakes for the account feature: an in-memory Firestore (as the SDK subset firestoreDb.ts uses, with read / write / listener counters and the
// value restrictions of the real thing), in-memory ports for the controller, and small record factories.  Not imported by app code.
import type { FirestoreSdk } from "./firestoreDb";
import { clipName, emptyMeta, stableStringify, type HistoryEntry, type ProfileRec, type SettingsContent, type SettingsRec, type SyncMeta } from "./merge";
import type { LocalPort, MetaPort, SettingsPort } from "./sync";

/** Firestore refuses `undefined` and arrays directly inside arrays: the fake does too, so a regression fails here instead of in production. */
export function assertFirestoreData(v: unknown, path = "data"): void {
  if (v === undefined) throw new Error(`Unsupported field value: undefined (found in ${path})`);
  if (Array.isArray(v)) {
    v.forEach((x, i) => {
      if (Array.isArray(x)) throw new Error(`Nested arrays are not supported (found in ${path}[${i}])`);
      assertFirestoreData(x, `${path}[${i}]`);
    });
  } else if (v && typeof v === "object") for (const [k, x] of Object.entries(v)) assertFirestoreData(x, `${path}.${k}`);
}

export interface FakeFirestore {
  sdk: FirestoreSdk & { onSnapshot?: never };
  db: object;
  docs: Map<string, Record<string, unknown>>;
  reads: number; // documents read (a getDoc of a missing document counts 1, like the billing)
  getDocCalls: number;
  getDocsCalls: number;
  commits: { path: string; type: "set" | "delete"; merge?: boolean; data?: Record<string, unknown> }[][];
  failNextCommit: (err: unknown, times?: number) => void;
  failNextRead: (err: unknown, times?: number) => void;
}

export function fakeFirestore(initial: Record<string, Record<string, unknown>> = {}): FakeFirestore {
  const docs = new Map<string, Record<string, unknown>>(Object.entries(initial).map(([k, v]) => [k, structuredClone(v)]));
  const f: FakeFirestore = {
    docs,
    db: { fake: true },
    reads: 0,
    getDocCalls: 0,
    getDocsCalls: 0,
    commits: [],
    failNextCommit: (err, times = 1) => void (commitFail = { err, left: times }),
    failNextRead: (err, times = 1) => void (readFail = { err, left: times }),
    sdk: undefined as unknown as FakeFirestore["sdk"],
  };
  let commitFail: { err: unknown; left: number } | null = null;
  let readFail: { err: unknown; left: number } | null = null;
  const tick = (slot: "c" | "r") => {
    const s = slot === "c" ? commitFail : readFail;
    if (s && s.left > 0) {
      s.left--;
      throw s.err;
    }
  };
  // NOTE: no onSnapshot / no listener API exists on this object: any code that tries to listen throws a TypeError.
  f.sdk = {
    doc: (_db, path) => ({ path }),
    collection: (_db, path) => ({ collectionPath: path }),
    async getDoc(ref) {
      tick("r");
      f.getDocCalls++;
      f.reads++;
      const path = (ref as { path: string }).path;
      const data = docs.get(path);
      return { exists: () => data !== undefined, id: path.split("/").pop()!, data: () => (data ? structuredClone(data) : undefined) };
    },
    async getDocs(ref) {
      tick("r");
      f.getDocsCalls++;
      const prefix = `${(ref as { collectionPath: string }).collectionPath}/`;
      const hits = [...docs.entries()].filter(([p]) => p.startsWith(prefix) && !p.slice(prefix.length).includes("/"));
      f.reads += Math.max(1, hits.length);
      return { docs: hits.map(([p, d]) => ({ id: p.slice(prefix.length), data: () => structuredClone(d) })) };
    },
    writeBatch() {
      const ops: FakeFirestore["commits"][number] = [];
      return {
        set(ref, data, options) {
          assertFirestoreData(data);
          ops.push({ path: (ref as { path: string }).path, type: "set", merge: options?.merge, data: structuredClone(data) });
        },
        delete(ref) {
          ops.push({ path: (ref as { path: string }).path, type: "delete" });
        },
        async commit() {
          tick("c");
          if (ops.length > 500) throw new Error("A batch holds at most 500 operations");
          f.commits.push(ops);
          for (const o of ops) {
            if (o.type === "delete") docs.delete(o.path);
            else docs.set(o.path, o.merge ? { ...(docs.get(o.path) ?? {}), ...o.data! } : o.data!);
          }
        },
      };
    },
  };
  return f;
}

export const rec = (id: string, v: unknown = 1, updatedAt = 1000, extra: Partial<ProfileRec> = {}): ProfileRec => ({
  id,
  classId: "fp_mage",
  name: `P-${id}`,
  updatedAt,
  state: stableStringify({ classId: "fp_mage", v }),
  ...extra,
});
export const tombstone = (id: string, updatedAt: number): ProfileRec => ({ id, classId: "fp_mage", name: `P-${id}`, updatedAt, deleted: true, state: "" });
export const cloudDoc = (r: ProfileRec): Record<string, unknown> => ({ classId: r.classId, name: r.name, updatedAt: r.updatedAt, state: r.state, ...(r.deleted ? { deleted: true } : {}) });

export interface FakeLocal extends LocalPort {
  recs: Map<string, ProfileRec>;
  fire(): void;
}
export function fakeLocal(initial: ProfileRec[] = []): FakeLocal {
  const recs = new Map(initial.map((r) => [r.id, r]));
  const subs = new Set<() => void>();
  const fire = () => subs.forEach((f) => f());
  return {
    recs,
    fire,
    listRecs: () => [...recs.values()].sort((a, b) => a.name.localeCompare(b.name)),
    put(list) {
      for (const r of list) recs.set(r.id, { ...r, name: clipName(r.name) });
      fire();
    },
    remove(ids) {
      ids.forEach((i) => recs.delete(i));
      fire();
    },
    clear() {
      recs.clear();
      fire();
    },
    subscribe(fn) {
      subs.add(fn);
      return () => void subs.delete(fn);
    },
    canonical: (r) => (r.state.includes("UNPARSEABLE") ? null : r),
  };
}

export interface FakeMeta extends MetaPort {
  metas: Map<string, SyncMeta>;
  history: HistoryEntry[];
  last: string | null;
}
export function fakeMeta(): FakeMeta {
  const m: FakeMeta = {
    metas: new Map(),
    history: [],
    last: null,
    load: (uid) => (m.metas.has(uid) ? structuredClone(m.metas.get(uid)!) : null),
    save: (uid, meta) => void m.metas.set(uid, structuredClone(meta)),
    clear: (uid) => void m.metas.delete(uid),
    lastUid: () => m.last,
    setLastUid: (uid) => void (m.last = uid),
    loadHistory: () => structuredClone(m.history),
    saveHistory: (h) => void (m.history = structuredClone(h)),
  };
  return m;
}

export interface FakeSettings extends SettingsPort {
  current: SettingsContent;
  applied: SettingsRec[];
}
export function fakeSettings(current: SettingsContent = { theme: "auto", lastClassId: "fp_mage" }): FakeSettings {
  const s: FakeSettings = {
    current,
    applied: [],
    read: () => ({ ...s.current }),
    apply(r) {
      s.applied.push(r);
      s.current = { theme: r.theme, lastClassId: r.lastClassId ?? s.current.lastClassId, lastProfileId: r.lastProfileId ?? s.current.lastProfileId };
    },
  };
  return s;
}

export { emptyMeta };
