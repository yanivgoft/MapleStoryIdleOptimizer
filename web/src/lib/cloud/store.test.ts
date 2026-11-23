import { describe, expect, it } from "vitest";
import { COMMIT_CHUNK, buildOps, commitOps, deleteAllData, describeCloudError, exportAllData, loadCloud, parseProfileDoc, parseSettingsDoc, profileDoc, settingsDoc, withRetry } from "./store";
import { createFirestoreDb } from "./firestoreDb";
import { MAX_NAME_CHARS, emptyMeta, planSave, type SavePlan } from "./merge";
import { assertFirestoreData, cloudDoc, fakeFirestore, rec, tombstone } from "./testkit";

const UID = "u1";
const P = (id: string) => `users/${UID}/profiles/${id}`;
const noSleep = { sleep: async () => undefined, delaysMs: [0] };

describe("documents <-> records", () => {
  it("a profile document has exactly the designed fields; the state is a JSON string", () => {
    const d = profileDoc(rec("a", { nested: [[1, 2]] }, 55));
    expect(Object.keys(d).sort()).toEqual(["classId", "name", "state", "updatedAt"]);
    expect(typeof d.state).toBe("string");
    assertFirestoreData(d); // nested arrays inside the state string are fine: it is a string
  });
  it("tombstones carry deleted: true and no state", () => {
    expect(profileDoc(tombstone("a", 9))).toEqual({ classId: "fp_mage", name: "P-a", updatedAt: 9, deleted: true, state: "" });
  });
  it("names are clipped to the rules' limit", () => {
    expect((profileDoc(rec("a", 1, 1, { name: "n".repeat(300) })).name as string).length).toBe(MAX_NAME_CHARS);
  });
  it("parses documents defensively", () => {
    expect(parseProfileDoc("a", cloudDoc(rec("a")))).toEqual(rec("a"));
    expect(parseProfileDoc("a", cloudDoc(tombstone("a", 5)))).toEqual(tombstone("a", 5));
    expect(parseProfileDoc("a", { ...cloudDoc(rec("a")), updatedAt: "x" })).toBeNull();
    expect(parseProfileDoc("a", { ...cloudDoc(rec("a")), state: 5 })).toBeNull();
    expect(parseProfileDoc("a", { ...cloudDoc(rec("a")), state: "" })).toBeNull(); // a live profile needs a state
    expect(parseProfileDoc("a", { classId: "x" })).toBeNull();
  });
  it("settings documents", () => {
    const s = { theme: "dark" as const, lastClassId: "hero", updatedAt: 4 };
    expect(settingsDoc(s)).toEqual(s);
    expect(settingsDoc({ theme: "auto", updatedAt: 4 })).toEqual({ theme: "auto", updatedAt: 4 }); // no undefined fields
    expect(parseSettingsDoc(s)).toEqual(s);
    expect(parseSettingsDoc({ theme: "neon", updatedAt: 1 })).toBeNull();
  });
});

describe("reading the account (sign-in / refresh)", () => {
  it("costs one read per cloud profile plus one for the settings, in one query + one get, and uses no listener", async () => {
    const fs = fakeFirestore({
      [P("a")]: cloudDoc(rec("a")),
      [P("b")]: cloudDoc(rec("b")),
      [P("t")]: cloudDoc(tombstone("t", 5)),
      [`users/${UID}/settings/app`]: { theme: "dark", updatedAt: 7 },
      [`users/${UID}`]: { lastSeenAt: 1, schema: 1 },
      "users/other/profiles/x": cloudDoc(rec("x")),
    });
    const db = createFirestoreDb(fs.sdk, fs.db);
    const snap = await loadCloud(db, UID);
    expect(Object.keys(snap.profiles).sort()).toEqual(["a", "b", "t"]);
    expect(snap.settings).toEqual({ theme: "dark", updatedAt: 7 });
    expect(snap.reads).toBe(3 + 1);
    expect(fs.reads).toBe(3 + 1); // = profiles (tombstones count) + settings; the user document is NOT read
    expect(fs.getDocsCalls).toBe(1);
    expect(fs.getDocCalls).toBe(1);
    expect("onSnapshot" in fs.sdk).toBe(false);
    expect(fs.commits).toEqual([]);
  });
  it("an empty account still costs the settings read plus the (minimum 1) query read, and unreadable documents are reported not dropped", async () => {
    const fs = fakeFirestore({ [P("bad")]: { classId: 5 } });
    const snap = await loadCloud(createFirestoreDb(fs.sdk, fs.db), UID);
    expect(snap.invalid).toEqual(["bad"]);
    expect(snap.settings).toBeNull();
  });
  it("retries transient failures and gives up on permanent ones", async () => {
    const fs = fakeFirestore({ [P("a")]: cloudDoc(rec("a")) });
    fs.failNextRead({ code: "unavailable" }, 2);
    const snap = await loadCloud(createFirestoreDb(fs.sdk, fs.db), UID, noSleep);
    expect(Object.keys(snap.profiles)).toEqual(["a"]);
    const fs2 = fakeFirestore();
    fs2.failNextRead({ code: "permission-denied" }, 5);
    await expect(loadCloud(createFirestoreDb(fs2.sdk, fs2.db), UID, noSleep)).rejects.toMatchObject({ code: "permission-denied" });
  });
});

describe("saving: one batched commit with only what changed", () => {
  const plan = (over: Partial<SavePlan> = {}): SavePlan => ({ writes: [], tombstones: [], sweep: [], rejected: [], cloudLiveCount: 0, ...over });
  it("buildOps: changed profiles, tombstones, swept tombstones, settings (only if changed) and the user document", () => {
    const ops = buildOps(UID, plan({ writes: [rec("a")], tombstones: [tombstone("b", 3)], sweep: ["old"] }), { now: 100, createUserDoc: true, settings: { theme: "dark", updatedAt: 100 } });
    expect(ops.map((o) => `${o.type}:${o.path}`)).toEqual([`set:${P("a")}`, `set:${P("b")}`, `delete:${P("old")}`, `set:users/${UID}/settings/app`, `set:users/${UID}`]);
    expect(ops[4]).toMatchObject({ merge: true, data: { lastSeenAt: 100, schema: 1, createdAt: 100 } });
    const again = buildOps(UID, plan({ writes: [rec("a")] }), { now: 200, createUserDoc: false, settings: null });
    expect(again.map((o) => o.path)).toEqual([P("a"), `users/${UID}`]);
    expect(again[1]).toMatchObject({ data: { lastSeenAt: 200, schema: 1 } });
    expect((again[1] as { data: Record<string, unknown> }).data.createdAt).toBeUndefined();
  });
  it("commitOps sends ONE batch for a normal save and writes exactly the planned documents", async () => {
    const fs = fakeFirestore({ [P("keep")]: cloudDoc(rec("keep", 1, 10)) });
    const p = planSave({ local: [rec("a", 2, 50), rec("keep", 1, 10)], cloud: { keep: rec("keep", 1, 10) }, meta: { ...emptyMeta(), baseline: { keep: { hash: "x", updatedAt: 10 } } } });
    const n = await commitOps(createFirestoreDb(fs.sdk, fs.db), buildOps(UID, p, { now: 9, createUserDoc: true }));
    expect(n).toBe(1);
    expect(fs.commits).toHaveLength(1);
    expect(fs.commits[0].map((o) => o.path).sort()).toEqual([P("a"), P("keep"), `users/${UID}`].sort()); // keep's hash differs from the fake baseline: it is dirty here
    expect(fs.reads).toBe(0); // saving reads nothing
    expect((fs.docs.get(P("a")) as { state: string }).state).toBe(rec("a", 2).state);
  });
  it("splits very large batches (Firestore allows 500 operations)", async () => {
    const fs = fakeFirestore();
    const writes = Array.from({ length: COMMIT_CHUNK + 50 }, (_, i) => rec(`p${i}`));
    const n = await commitOps(createFirestoreDb(fs.sdk, fs.db), buildOps(UID, plan({ writes }), { now: 1, createUserDoc: false }));
    expect(n).toBe(2);
    expect(fs.commits.map((c) => c.length)).toEqual([COMMIT_CHUNK, 51]);
  });
  it("retries a transient commit failure, then succeeds; a permanent one is thrown", async () => {
    const fs = fakeFirestore();
    const db = createFirestoreDb(fs.sdk, fs.db);
    fs.failNextCommit({ code: "unavailable" }, 2);
    await commitOps(db, buildOps(UID, plan({ writes: [rec("a")] }), { now: 1, createUserDoc: true }), noSleep);
    expect(fs.commits).toHaveLength(1);
    fs.failNextCommit({ code: "permission-denied" }, 1);
    await expect(commitOps(db, buildOps(UID, plan({ writes: [rec("b")] }), { now: 1, createUserDoc: true }), noSleep)).rejects.toMatchObject({ code: "permission-denied" });
    expect(fs.docs.has(P("b"))).toBe(false);
  });
});

describe("export and delete", () => {
  const seeded = () =>
    fakeFirestore({
      [P("a")]: cloudDoc(rec("a", { x: 1 })),
      [P("t")]: cloudDoc(tombstone("t", 5)),
      [`users/${UID}/settings/app`]: { theme: "light", updatedAt: 3 },
      [`users/${UID}`]: { lastSeenAt: 1, schema: 1, createdAt: 1 },
      "users/other": { lastSeenAt: 1 },
    });
  it("export returns everything stored for the account, states parsed", async () => {
    const fs = seeded();
    const out = (await exportAllData(createFirestoreDb(fs.sdk, fs.db), UID, { email: "a@b.c" }, 1_700_000_000_000)) as { account: { uid: string; email: string }; profiles: { id: string; state: unknown; deleted: boolean }[]; settings: unknown; user: unknown };
    expect(out.account).toEqual({ uid: UID, email: "a@b.c" });
    expect(out.profiles.map((p) => p.id).sort()).toEqual(["a", "t"]);
    expect(out.profiles.find((p) => p.id === "a")!.state).toEqual({ classId: "fp_mage", v: { x: 1 } });
    expect(out.profiles.find((p) => p.id === "t")!.deleted).toBe(true);
    expect(out.settings).toMatchObject({ theme: "light" });
    expect(out.user).toMatchObject({ schema: 1 });
  });
  it("delete removes every document of the account (profiles, tombstones, settings, user) and nothing else", async () => {
    const fs = seeded();
    const n = await deleteAllData(createFirestoreDb(fs.sdk, fs.db), UID);
    expect(n).toBe(4);
    expect([...fs.docs.keys()]).toEqual(["users/other"]);
    expect(fs.commits).toHaveLength(1);
  });
});

describe("error descriptions and retry", () => {
  it("classifies errors in words a player can act on", () => {
    expect(describeCloudError({ code: "unavailable" })).toMatchObject({ kind: "offline", transient: true });
    expect(describeCloudError({ code: "firestore/unavailable" }).transient).toBe(true);
    expect(describeCloudError(new TypeError("Failed to fetch"))).toMatchObject({ kind: "offline", transient: true });
    expect(describeCloudError({ code: "permission-denied" })).toMatchObject({ kind: "permission", transient: false });
    expect(describeCloudError({ code: "resource-exhausted" }).kind).toBe("quota");
    expect(describeCloudError({ code: "unauthenticated" }).kind).toBe("auth");
    expect(describeCloudError(new Error("boom")).message).toContain("boom");
  });
  it("withRetry: tries up to 3 times for transient errors, once for others, and times out a hanging promise", async () => {
    let n = 0;
    await expect(withRetry(async () => { n++; throw { code: "unavailable" }; }, noSleep)).rejects.toBeTruthy();
    expect(n).toBe(3);
    n = 0;
    await expect(withRetry(async () => { n++; throw { code: "permission-denied" }; }, noSleep)).rejects.toBeTruthy();
    expect(n).toBe(1);
    let calls = 0;
    const hang = withRetry(() => { calls++; return new Promise<never>(() => undefined); }, { ...noSleep, timeoutMs: 5, attempts: 2 });
    await expect(hang).rejects.toMatchObject({ code: "timeout" });
    expect(calls).toBe(2);
  });
});
