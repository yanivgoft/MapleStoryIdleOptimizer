import { describe, expect, it } from "vitest";
import { AccountController } from "./sync";
import { createFirestoreDb } from "./firestoreDb";
import { MAX_PROFILES, MAX_STATE_CHARS, TOMBSTONE_TTL_MS } from "./merge";
import { cloudDoc, fakeFirestore, fakeLocal, fakeMeta, fakeSettings, rec, tombstone } from "./testkit";

const user = { uid: "u1", email: "me@example.com", displayName: "Me", photoURL: null };
const P = (id: string, uid = "u1") => `users/${uid}/profiles/${id}`;
const S = (uid = "u1") => `users/${uid}/settings/app`;
const NOW = 1_800_000_000_000;
const noSleep = { sleep: async () => undefined, delaysMs: [0] };

function setup(opts: { local?: ReturnType<typeof rec>[]; cloud?: Record<string, Record<string, unknown>> } = {}) {
  const fs = fakeFirestore(opts.cloud);
  const local = fakeLocal(opts.local);
  const meta = fakeMeta();
  const settings = fakeSettings();
  let now = NOW;
  const ctl = new AccountController({ local, meta, settings, now: () => now, retry: noSleep, newId: () => "restored1" });
  const db = createFirestoreDb(fs.sdk, fs.db);
  return { fs, local, meta, settings, ctl, db, tick: (ms = 1000) => (now += ms), setNow: (n: number) => (now = n) };
}

describe("first sign-in", () => {
  it("reads once, asks about the local profiles, and uploads exactly the chosen ones in ONE batch with the settings", async () => {
    const t = setup({ local: [rec("a"), rec("b"), rec("c")] });
    await t.ctl.signedIn(user, t.db);
    const s = t.ctl.getState();
    expect(s.phase).toBe("ready");
    expect(s.migration?.first).toBe(true);
    expect(s.migration?.candidates.map((c) => c.id)).toEqual(["a", "b", "c"]);
    expect(s.dirtyCount).toBe(0); // waiting for the decision, not "unsaved"
    expect(t.fs.reads).toBe(2); // empty query (min 1) + settings
    expect(t.fs.commits).toEqual([]);
    expect((await t.ctl.save()).skipped).toBe("migration"); // cannot save before deciding

    t.ctl.resolveMigration({ kind: "choose", ids: ["a", "c"] });
    expect(t.ctl.getState().migration).toBeNull();
    expect(t.ctl.getState().statuses).toEqual({ a: "unsaved", b: "local-only", c: "unsaved" });
    expect(t.ctl.getState().dirtyCount).toBe(2);
    const r = await t.ctl.save();
    expect(r).toMatchObject({ ok: true, written: 2 });
    expect(t.fs.commits).toHaveLength(1);
    expect(t.fs.commits[0].map((o) => o.path).sort()).toEqual([P("a"), P("c"), S(), "users/u1"].sort());
    expect(t.fs.docs.has(P("b"))).toBe(false);
    expect(t.fs.docs.get("users/u1")).toMatchObject({ schema: 1, createdAt: NOW });
    expect(t.ctl.getState().statuses).toEqual({ a: "synced", b: "local-only", c: "synced" });
    expect(t.ctl.getState().skippedCount).toBe(1);
  });
  it("closing the dialog means 'not now': everything stays local-only and can be uploaded later from the menu", async () => {
    const t = setup({ local: [rec("a")] });
    await t.ctl.signedIn(user, t.db);
    t.ctl.dismissMigration();
    expect(t.ctl.getState().statuses.a).toBe("local-only");
    expect(t.ctl.getState().dirtyCount).toBe(0);
    t.ctl.openMigration();
    expect(t.ctl.getState().migration).toMatchObject({ first: false });
    t.ctl.resolveMigration({ kind: "all" });
    expect(t.ctl.getState().statuses.a).toBe("unsaved");
    await t.ctl.save();
    expect(t.fs.docs.has(P("a"))).toBe(true);
  });
  it("downloads cloud-only profiles and applies the account's settings; no question when nothing local is new", async () => {
    const t = setup({ cloud: { [P("c1")]: cloudDoc(rec("c1")), [P("c2")]: cloudDoc(rec("c2")), [S()]: { theme: "dark", lastClassId: "hero", updatedAt: 5 } } });
    await t.ctl.signedIn(user, t.db);
    expect([...t.local.recs.keys()].sort()).toEqual(["c1", "c2"]);
    expect(t.ctl.getState().migration).toBeNull();
    expect(t.ctl.getState().statuses).toEqual({ c1: "synced", c2: "synced" });
    expect(t.ctl.getState().dirtyCount).toBe(0);
    expect(t.settings.applied).toHaveLength(1);
    expect(t.settings.current.theme).toBe("dark");
    expect(t.ctl.getState().settingsDirty).toBe(false);
    expect(t.fs.reads).toBe(3);
    expect(t.fs.commits).toEqual([]); // sign-in never writes
  });
  it("a read failure surfaces as an error state and refresh can recover", async () => {
    const t = setup({ cloud: { [P("c1")]: cloudDoc(rec("c1")) } });
    t.fs.failNextRead({ code: "permission-denied" }, 1);
    await t.ctl.signedIn(user, t.db);
    expect(t.ctl.getState().phase).toBe("error");
    expect(t.ctl.getState().error).toMatch(/permission denied/);
    await t.ctl.refresh();
    expect(t.ctl.getState().phase).toBe("ready");
    expect(t.local.recs.has("c1")).toBe(true);
  });
});

describe("saving", () => {
  async function synced() {
    const t = setup({ cloud: { [P("a")]: cloudDoc(rec("a", 1, 100)), [P("b")]: cloudDoc(rec("b", 1, 100)), [S()]: { theme: "auto", lastClassId: "fp_mage", updatedAt: 5 } } });
    await t.ctl.signedIn(user, t.db);
    t.fs.commits.length = 0;
    t.fs.reads = 0;
    return t;
  }
  it("writes only the profiles edited since the last save, then nothing at all", async () => {
    const t = await synced();
    expect(t.ctl.getState().dirtyCount).toBe(0);
    t.tick();
    t.local.put([rec("b", 2, NOW + 1000)]); // an edit
    expect(t.ctl.getState().statuses).toEqual({ a: "synced", b: "unsaved" });
    expect(t.ctl.getState().dirtyCount).toBe(1);
    const r = await t.ctl.save();
    expect(r).toMatchObject({ ok: true, written: 1 });
    expect(t.fs.commits).toHaveLength(1);
    expect(t.fs.commits[0].map((o) => o.path).sort()).toEqual([P("b"), "users/u1"].sort());
    expect(t.fs.reads).toBe(0);
    expect(t.ctl.getState().dirtyCount).toBe(0);
    expect((await t.ctl.save()).skipped).toBe("nothing");
    expect(t.fs.commits).toHaveLength(1); // no second commit
  });
  it("a local delete is saved as a tombstone (soft delete) and the profile's content is gone from the cloud", async () => {
    const t = await synced();
    t.tick();
    t.local.remove(["a"]);
    expect(t.ctl.getState().dirtyCount).toBe(1);
    await t.ctl.save();
    expect(t.fs.docs.get(P("a"))).toMatchObject({ deleted: true, state: "", name: "P-a", classId: "fp_mage" });
    expect(t.fs.docs.get(P("a"))!.updatedAt).toBeGreaterThan(100);
    expect(t.ctl.getState().dirtyCount).toBe(0);
  });
  it("a deletion made while signed out is remembered and saved after the next sign-in", async () => {
    const t = await synced();
    t.ctl.leave(false);
    expect(t.ctl.getState().phase).toBe("signed-out");
    t.local.remove(["a"]); // deleted while signed out: tracked through the last account
    const again = new AccountController({ local: t.local, meta: t.meta, settings: t.settings, now: () => NOW + 5000, retry: noSleep });
    await again.signedIn(user, t.db);
    expect(again.getState().dirtyCount).toBe(1);
    await again.save();
    expect(t.fs.docs.get(P("a"))).toMatchObject({ deleted: true });
  });
  it("only theme / class changes: Save writes the settings but they never count as unsaved profiles", async () => {
    const t = await synced();
    t.settings.current = { theme: "dark", lastClassId: "fp_mage" };
    t.ctl.touch();
    expect(t.ctl.getState().settingsDirty).toBe(true);
    expect(t.ctl.getState().dirtyCount).toBe(0);
    await t.ctl.save();
    expect(t.fs.docs.get(S())).toMatchObject({ theme: "dark", lastClassId: "fp_mage" });
    expect(t.ctl.getState().settingsDirty).toBe(false);
  });
  it("a failed save keeps everything dirty and reports; the next save works", async () => {
    const t = await synced();
    t.local.put([rec("a", 9, NOW + 10)]);
    t.fs.failNextCommit({ code: "permission-denied" }, 1);
    const r = await t.ctl.save();
    expect(r.ok).toBe(false);
    expect(r.error).toMatch(/permission denied/);
    expect(t.ctl.getState().phase).toBe("error");
    expect(t.ctl.getState().dirtyCount).toBe(1);
    expect((await t.ctl.save()).ok).toBe(true);
    expect(t.ctl.getState().phase).toBe("ready");
    expect(t.ctl.getState().dirtyCount).toBe(0);
  });
  it("a transient failure is retried inside the save", async () => {
    const t = await synced();
    t.local.put([rec("a", 9, NOW + 10)]);
    t.fs.failNextCommit({ code: "unavailable" }, 2);
    expect((await t.ctl.save()).ok).toBe(true);
    expect(t.fs.commits).toHaveLength(1);
  });
  it("profiles over the size guard or the 50-profile cap are reported per profile and never dropped silently", async () => {
    const cloud: Record<string, Record<string, unknown>> = {};
    for (let i = 0; i < MAX_PROFILES - 1; i++) cloud[P(`e${i}`)] = cloudDoc(rec(`e${i}`, 1, 100));
    const t = setup({ cloud });
    await t.ctl.signedIn(user, t.db);
    t.fs.commits.length = 0;
    t.local.put([rec("n1", 1, NOW + 1), rec("n2", 1, NOW + 2), rec("big", 1, NOW + 3, { state: "y".repeat(MAX_STATE_CHARS + 1) })]);
    const r = await t.ctl.save();
    expect(r.written).toBe(1); // 49 + 1 = 50
    expect(r.rejected.map((x) => x.reason).sort()).toEqual(["over-cap", "too-large"]);
    const s = t.ctl.getState();
    expect(s.statuses.big).toBe("error");
    expect(s.profileErrors.big).toMatch(/too large/);
    expect(Object.values(s.statuses).filter((x) => x === "error")).toHaveLength(2);
    expect(s.dirtyCount).toBe(2); // the two that did not fit are still unsaved
    expect(t.local.recs.has("big")).toBe(true); // nothing is removed locally
  });
  it("concurrent saves are serialized: the second one finds nothing to do", async () => {
    const t = await synced();
    t.local.put([rec("a", 9, NOW + 10)]);
    const [r1, r2] = await Promise.all([t.ctl.save(), t.ctl.save()]);
    expect(r1.written).toBe(1);
    expect(r2.skipped).toBe("nothing");
    expect(t.fs.commits).toHaveLength(1);
  });
  it("expired tombstones are swept with the next save; young ones stay", async () => {
    const t = setup({ cloud: { [P("old")]: cloudDoc(tombstone("old", NOW - TOMBSTONE_TTL_MS - 5)), [P("young")]: cloudDoc(tombstone("young", NOW - 1000)), [P("a")]: cloudDoc(rec("a", 1, 100)) } });
    await t.ctl.signedIn(user, t.db);
    t.local.put([rec("a", 2, NOW + 1)]);
    await t.ctl.save();
    expect(t.fs.docs.has(P("old"))).toBe(false);
    expect(t.fs.docs.has(P("young"))).toBe(true);
  });
});

describe("refresh and conflicts", () => {
  it("another device edited a profile: refresh brings it in with a notice; our unsaved edit of another profile is untouched", async () => {
    const t = setup({ cloud: { [P("a")]: cloudDoc(rec("a", 1, 100)), [P("b")]: cloudDoc(rec("b", 1, 100)) } });
    await t.ctl.signedIn(user, t.db);
    t.local.put([rec("b", 5, NOW + 1)]);
    t.fs.docs.set(P("a"), cloudDoc(rec("a", 2, NOW + 500)));
    t.fs.reads = 0;
    await t.ctl.refresh();
    expect(t.fs.reads).toBe(3); // 2 profiles + settings
    expect(t.local.recs.get("a")!.state).toBe(rec("a", 2).state);
    expect(t.ctl.getState().notices.map((n) => n.kind)).toEqual(["updated"]);
    expect(t.ctl.getState().statuses).toEqual({ a: "synced", b: "unsaved" });
  });
  it("edited on both devices: last write wins, the loser is kept in the persisted history and can be restored as a new profile", async () => {
    const t = setup({ cloud: { [P("a")]: cloudDoc(rec("a", 1, 100)) } });
    await t.ctl.signedIn(user, t.db);
    t.local.put([rec("a", "local-edit", NOW + 100)]);
    t.fs.docs.set(P("a"), cloudDoc(rec("a", "cloud-edit", NOW + 900)));
    await t.ctl.refresh();
    expect(t.local.recs.get("a")!.state).toBe(rec("a", "cloud-edit").state);
    const s = t.ctl.getState();
    expect(s.notices.map((n) => n.kind)).toEqual(["conflict"]);
    expect(s.history).toHaveLength(1);
    expect(s.history[0].state).toBe(rec("a", "local-edit").state);
    expect(t.meta.history).toHaveLength(1); // persisted
    const newId = t.ctl.restoreHistory(s.history[0].key);
    expect(newId).toBe("restored1");
    expect(t.local.recs.get("restored1")).toMatchObject({ name: "P-a (restored)", state: rec("a", "local-edit").state });
    expect(t.ctl.getState().history).toEqual([]);
    expect(t.ctl.getState().statuses.restored1).toBe("unsaved");
  });
  it("our newer edit wins over an older cloud version: the cloud version goes to the history and the next Save overwrites it", async () => {
    const t = setup({ cloud: { [P("a")]: cloudDoc(rec("a", 1, 100)) } });
    await t.ctl.signedIn(user, t.db);
    t.local.put([rec("a", "mine", NOW + 800)]);
    t.fs.docs.set(P("a"), cloudDoc(rec("a", "theirs", NOW + 200)));
    await t.ctl.refresh();
    expect(t.local.recs.get("a")!.state).toBe(rec("a", "mine").state);
    expect(t.ctl.getState().history[0].reason).toBe("replaced-by-local");
    await t.ctl.save();
    expect((t.fs.docs.get(P("a")) as { state: string }).state).toBe(rec("a", "mine").state);
  });
  it("a profile deleted on another device is removed here (copy in the history); an unreadable cloud profile is left alone", async () => {
    const t = setup({ cloud: { [P("a")]: cloudDoc(rec("a", 1, 100)), [P("junk")]: { classId: 7 } } });
    await t.ctl.signedIn(user, t.db);
    t.fs.docs.set(P("a"), cloudDoc(tombstone("a", NOW + 50)));
    await t.ctl.refresh();
    expect(t.local.recs.has("a")).toBe(false);
    expect(t.ctl.getState().history.map((h) => h.reason)).toEqual(["deleted-elsewhere"]);
    expect(t.ctl.getState().notices.map((n) => n.kind).sort()).toEqual(["deleted", "invalid"]);
    expect(t.ctl.getState().dirtyCount).toBe(0); // removing it locally is not a new deletion to upload
    await t.ctl.save();
    expect(t.fs.docs.get(P("junk"))).toEqual({ classId: 7 });
  });
  it("cloud profiles that this app version cannot normalise are reported, never overwritten", async () => {
    const t = setup({ cloud: { [P("x")]: cloudDoc(rec("x", "UNPARSEABLE")) } });
    await t.ctl.signedIn(user, t.db);
    expect(t.local.recs.has("x")).toBe(false);
    expect(t.ctl.getState().notices[0].kind).toBe("invalid");
  });
  it("notices can be dismissed", async () => {
    const t = setup({ cloud: { [P("a")]: cloudDoc(rec("a", 1, 100)) } });
    await t.ctl.signedIn(user, t.db);
    t.fs.docs.set(P("a"), cloudDoc(rec("a", 2, NOW + 100)));
    await t.ctl.refresh();
    const id = t.ctl.getState().notices[0].id;
    t.ctl.dismissNotice(id);
    expect(t.ctl.getState().notices).toEqual([]);
  });
});

describe("sign-out, export, deletion", () => {
  it("sign out and keep: the profiles stay; sign out and clear: this browser's profiles, sync data and history are removed (the cloud is untouched)", async () => {
    const t = setup({ cloud: { [P("a")]: cloudDoc(rec("a", 1, 100)) } });
    await t.ctl.signedIn(user, t.db);
    t.ctl.leave(false);
    expect(t.local.recs.has("a")).toBe(true);
    expect(t.ctl.getState()).toMatchObject({ phase: "signed-out", user: null, dirtyCount: 0 });
    await t.ctl.signedIn(user, t.db);
    t.ctl.leave(true);
    expect(t.local.recs.size).toBe(0);
    expect(t.meta.metas.size).toBe(0);
    expect(t.meta.last).toBeNull();
    expect(t.fs.docs.has(P("a"))).toBe(true);
  });
  it("deleteCloudData removes every document of the account and the sync data, keeps the local profiles", async () => {
    const t = setup({ cloud: { [P("a")]: cloudDoc(rec("a", 1, 100)), [S()]: { theme: "auto", updatedAt: 1 }, "users/u1": { lastSeenAt: 1, schema: 1 }, [P("x", "other")]: cloudDoc(rec("x")) } });
    await t.ctl.signedIn(user, t.db);
    const n = await t.ctl.deleteCloudData();
    expect(n).toBe(3);
    expect([...t.fs.docs.keys()]).toEqual([P("x", "other")]);
    expect(t.local.recs.has("a")).toBe(true);
    expect(t.meta.metas.has("u1")).toBe(false);
  });
  it("exportAll needs a signed-in account", async () => {
    const t = setup();
    await expect(t.ctl.exportAll()).rejects.toThrow(/Not signed in/);
    await t.ctl.signedIn(user, t.db);
    expect(await t.ctl.exportAll()).toMatchObject({ kind: "account-export", account: { uid: "u1", email: "me@example.com" } });
  });
});
