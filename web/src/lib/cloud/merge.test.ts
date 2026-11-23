import { describe, expect, it } from "vitest";
import {
  HISTORY_MAX,
  MAX_PROFILES,
  MAX_STATE_CHARS,
  TOMBSTONE_TTL_MS,
  addHistory,
  applyMigrationDecision,
  applySaved,
  contentHash,
  dirtyIds,
  emptyMeta,
  hashString,
  localStatuses,
  mergeProfiles,
  mergeSettings,
  planSave,
  settingsDirty,
  settingsHash,
  stableStringify,
  trackLocalChanges,
  type HistoryEntry,
  type ProfileRec,
  type SyncMeta,
} from "./merge";

const NOW = 1_800_000_000_000;
const rec = (id: string, v = 1, updatedAt = 1000, extra: Partial<ProfileRec> = {}): ProfileRec => ({ id, classId: "fp_mage", name: `P-${id}`, updatedAt, state: stableStringify({ classId: "fp_mage", v }), ...extra });
const tomb = (id: string, updatedAt: number): ProfileRec => ({ id, classId: "fp_mage", name: `P-${id}`, updatedAt, deleted: true, state: "" });
const synced = (...recs: ProfileRec[]): SyncMeta => {
  const m = emptyMeta();
  m.lastSyncAt = 1;
  for (const r of recs) m.baseline[r.id] = { hash: contentHash(r), updatedAt: r.updatedAt };
  return m;
};

describe("canonical JSON + hash", () => {
  it("stableStringify sorts keys recursively and drops undefined", () => {
    expect(stableStringify({ b: 1, a: { d: [1, { z: 1, y: undefined }], c: null } })).toBe('{"a":{"c":null,"d":[1,{"z":1}]},"b":1}');
    expect(stableStringify({ a: 1, b: 2 })).toBe(stableStringify({ b: 2, a: 1 }));
    expect(stableStringify([undefined, NaN])).toBe("[null,null]");
  });
  it("hashString is deterministic and sensitive", () => {
    expect(hashString("abc")).toBe(hashString("abc"));
    expect(hashString("abc")).not.toBe(hashString("abd"));
    expect(hashString("abc")).toHaveLength(14);
  });
  it("a profile's content hash ignores its id and timestamp", () => {
    expect(contentHash(rec("a", 1, 5))).toBe(contentHash(rec("b", 1, 99, { name: "P-a" })));
    expect(contentHash(rec("a", 1))).not.toBe(contentHash(rec("a", 2)));
    expect(contentHash({ ...rec("a"), name: "other" })).not.toBe(contentHash(rec("a")));
  });
});

describe("dirty tracking", () => {
  it("a profile is dirty when new or changed since its baseline, never when skipped", () => {
    const a = rec("a");
    const b = rec("b");
    const meta = synced(a);
    expect(dirtyIds([a, b], meta)).toEqual(["b"]);
    expect(dirtyIds([rec("a", 2), b], meta).sort()).toEqual(["a", "b"]);
    meta.skipped.b = true;
    expect(dirtyIds([a, b], meta)).toEqual([]);
    expect(localStatuses([a, b, rec("c")], meta)).toEqual({ a: "synced", b: "local-only", c: "unsaved" });
  });
  it("a profile that disappears locally becomes a pending deletion; coming back cancels it; unknown ids are ignored", () => {
    const a = rec("a");
    const b = rec("b");
    const meta = synced(a, b);
    const m1 = trackLocalChanges([a], meta, 77, [a, b]);
    expect(m1).not.toBe(meta);
    expect(m1.deletes.b).toEqual({ at: 77, classId: "fp_mage", name: "P-b" });
    expect(meta.deletes).toEqual({}); // the input is not mutated
    expect(trackLocalChanges([a], m1, 99, [a])).toBe(m1); // already recorded: unchanged, same object
    expect(trackLocalChanges([a, b], m1, 100, [a]).deletes).toEqual({});
    expect(trackLocalChanges([a, rec("never-synced")], synced(a), 5, [a])).toEqual(synced(a));
  });
});

describe("mergeProfiles", () => {
  it("cloud-only profiles are downloaded; local-only ones are offered for migration on the FIRST login", () => {
    const r = mergeProfiles({ local: [rec("l")], cloud: [rec("c")], meta: emptyMeta(), now: NOW });
    expect(r.firstLogin).toBe(true);
    expect(r.download.map((d) => d.id)).toEqual(["c"]);
    expect(r.migration).toEqual(["l"]);
    expect(r.meta.baseline.c).toBeTruthy();
    expect(r.meta.baseline.l).toBeUndefined();
  });
  it("later logins do not ask again: a new local profile is simply unsaved", () => {
    const meta = synced();
    const r = mergeProfiles({ local: [rec("l")], cloud: [], meta, now: NOW });
    expect(r.firstLogin).toBe(false);
    expect(r.migration).toEqual([]);
    expect(dirtyIds([rec("l")], r.meta)).toEqual(["l"]);
  });
  it("identical content on both sides is in sync (and no longer skipped)", () => {
    const meta = emptyMeta();
    meta.skipped.a = true;
    const r = mergeProfiles({ local: [rec("a", 1, 1000)], cloud: [rec("a", 1, 2000)], meta, now: NOW });
    expect(r.download).toEqual([]);
    expect(r.notices).toEqual([]);
    expect(r.meta.baseline.a).toEqual({ hash: contentHash(rec("a")), updatedAt: 2000 });
    expect(r.meta.skipped.a).toBeUndefined();
  });
  it("edited on the cloud side only: the cloud version is taken, with an 'updated from another device' notice and no history", () => {
    const base = rec("a", 1, 1000);
    const r = mergeProfiles({ local: [base], cloud: [rec("a", 2, 2000)], meta: synced(base), now: NOW });
    expect(r.download).toEqual([rec("a", 2, 2000)]);
    expect(r.history).toEqual([]);
    expect(r.notices.map((n) => n.kind)).toEqual(["updated"]);
    expect(dirtyIds([rec("a", 2, 2000)], r.meta)).toEqual([]);
  });
  it("edited on the local side only: kept, stays dirty, no notice", () => {
    const base = rec("a", 1, 1000);
    const r = mergeProfiles({ local: [rec("a", 3, 3000)], cloud: [base], meta: synced(base), now: NOW });
    expect(r.download).toEqual([]);
    expect(r.notices).toEqual([]);
    expect(dirtyIds([rec("a", 3, 3000)], r.meta)).toEqual(["a"]);
  });
  it("edited on both sides: the newer updatedAt wins and the loser goes to the history", () => {
    const base = rec("a", 1, 1000);
    const cloudWins = mergeProfiles({ local: [rec("a", 2, 2000)], cloud: [rec("a", 3, 3000)], meta: synced(base), now: NOW });
    expect(cloudWins.download).toEqual([rec("a", 3, 3000)]);
    expect(cloudWins.history).toHaveLength(1);
    expect(cloudWins.history[0]).toMatchObject({ profileId: "a", reason: "replaced-by-cloud", state: rec("a", 2).state, versionUpdatedAt: 2000 });
    expect(cloudWins.notices.map((n) => n.kind)).toEqual(["conflict"]);

    const localWins = mergeProfiles({ local: [rec("a", 2, 4000)], cloud: [rec("a", 3, 3000)], meta: synced(base), now: NOW });
    expect(localWins.download).toEqual([]);
    expect(localWins.history[0]).toMatchObject({ reason: "replaced-by-local", state: rec("a", 3).state });
    expect(dirtyIds([rec("a", 2, 4000)], localWins.meta)).toEqual(["a"]); // will overwrite the cloud copy on the next Save

    const tie = mergeProfiles({ local: [rec("a", 2, 3000)], cloud: [rec("a", 3, 3000)], meta: synced(base), now: NOW });
    expect(tie.download.map((d) => d.id)).toEqual(["a"]); // a tie goes to the cloud
  });
  it("same id with different content and no baseline (e.g. metadata lost) is treated as a conflict, never silently overwritten", () => {
    const r = mergeProfiles({ local: [rec("a", 2, 5000)], cloud: [rec("a", 3, 3000)], meta: emptyMeta(), now: NOW });
    expect(r.history).toHaveLength(1);
    expect(r.notices[0].kind).toBe("conflict");
  });
  it("deleted in the cloud vs unchanged locally: removed locally, a copy kept in the history", () => {
    const base = rec("a", 1, 1000);
    const r = mergeProfiles({ local: [base], cloud: [tomb("a", 2000)], meta: synced(base), now: NOW });
    expect(r.removeLocal).toEqual(["a"]);
    expect(r.history[0]).toMatchObject({ reason: "deleted-elsewhere", profileId: "a" });
    expect(r.notices.map((n) => n.kind)).toEqual(["deleted"]);
    expect(r.meta.baseline.a).toBeUndefined();
  });
  it("deleted in the cloud vs edited locally afterwards: the edit survives and is uploaded again", () => {
    const base = rec("a", 1, 1000);
    const r = mergeProfiles({ local: [rec("a", 2, 5000)], cloud: [tomb("a", 2000)], meta: synced(base), now: NOW });
    expect(r.removeLocal).toEqual([]);
    expect(dirtyIds([rec("a", 2, 5000)], r.meta)).toEqual(["a"]);
  });
  it("deleted locally vs edited in the cloud afterwards: the cloud edit wins ('restored'); vs untouched cloud: the deletion stays pending", () => {
    const base = rec("a", 1, 1000);
    const meta = synced(base);
    meta.deletes.a = { at: 3000, classId: "fp_mage", name: "P-a" };
    const edited = mergeProfiles({ local: [], cloud: [rec("a", 2, 4000)], meta, now: NOW });
    expect(edited.download.map((d) => d.id)).toEqual(["a"]);
    expect(edited.meta.deletes.a).toBeUndefined();
    expect(edited.notices.map((n) => n.kind)).toEqual(["restored"]);

    const editedBefore = mergeProfiles({ local: [], cloud: [rec("a", 2, 2500)], meta, now: NOW });
    expect(editedBefore.download).toEqual([]); // the edit is older than the deletion: deletion wins
    expect(editedBefore.meta.deletes.a).toBeTruthy();

    const untouched = mergeProfiles({ local: [], cloud: [base], meta, now: NOW });
    expect(untouched.download).toEqual([]);
    expect(untouched.meta.deletes.a).toBeTruthy();
  });
  it("a deletion that the cloud already knows (tombstone or nothing) is forgotten", () => {
    const meta = synced(rec("a"));
    meta.deletes.a = { at: 3000, classId: "fp_mage", name: "P-a" };
    expect(mergeProfiles({ local: [], cloud: [tomb("a", 3500)], meta, now: NOW }).meta.deletes).toEqual({});
    expect(mergeProfiles({ local: [], cloud: [], meta, now: NOW }).meta.deletes).toEqual({});
  });
  it("tombstones older than 30 days are swept; young ones are not; they never create local profiles", () => {
    const old = tomb("old", NOW - TOMBSTONE_TTL_MS - 1);
    const young = tomb("young", NOW - TOMBSTONE_TTL_MS + 60_000);
    const r = mergeProfiles({ local: [], cloud: [old, young], meta: synced(), now: NOW });
    expect(r.sweep).toEqual(["old"]);
    expect(r.download).toEqual([]);
  });
  it("a baseline entry whose cloud document vanished (purged) makes the local profile new again, never deletes it", () => {
    const a = rec("a");
    const r = mergeProfiles({ local: [a], cloud: [], meta: synced(a), now: NOW });
    expect(r.removeLocal).toEqual([]);
    expect(dirtyIds([a], r.meta)).toEqual(["a"]);
  });
  it("is pure: the input meta is not modified", () => {
    const meta = synced(rec("a"));
    const copy = JSON.stringify(meta);
    mergeProfiles({ local: [], cloud: [rec("x")], meta, now: NOW });
    expect(JSON.stringify(meta)).toBe(copy);
  });
});

describe("first-login migration decisions", () => {
  const cands = ["a", "b", "c"];
  it("all: nothing is skipped (they stay dirty and are uploaded by Save)", () => {
    const m = applyMigrationDecision(emptyMeta(), cands, { kind: "all" });
    expect(m.skipped).toEqual({});
    expect(dirtyIds(cands.map((i) => rec(i)), m)).toEqual(cands);
  });
  it("none: every candidate becomes local-only and is never counted as unsaved", () => {
    const m = applyMigrationDecision(emptyMeta(), cands, { kind: "none" });
    expect(Object.keys(m.skipped).sort()).toEqual(cands);
    expect(dirtyIds(cands.map((i) => rec(i)), m)).toEqual([]);
  });
  it("choose: only the chosen ones are uploaded; ids that were not offered are ignored; re-opening can un-skip", () => {
    const m = applyMigrationDecision(emptyMeta(), cands, { kind: "choose", ids: ["b", "zzz"] });
    expect(Object.keys(m.skipped).sort()).toEqual(["a", "c"]);
    const again = applyMigrationDecision(m, ["a", "c"], { kind: "choose", ids: ["a"] });
    expect(Object.keys(again.skipped)).toEqual(["c"]);
  });
});

describe("planSave: what 'Save to account' writes", () => {
  const cloudOf = (...recs: ProfileRec[]) => Object.fromEntries(recs.map((r) => [r.id, r]));
  it("writes ONLY the dirty profiles", () => {
    const a = rec("a", 1, 1000);
    const b = rec("b", 1, 1000);
    const meta = synced(a, b);
    const plan = planSave({ local: [a, rec("b", 2, 2000), rec("c", 1, 3000)], cloud: cloudOf(a, b), meta });
    expect(plan.writes.map((w) => w.id).sort()).toEqual(["b", "c"]);
    expect(plan.tombstones).toEqual([]);
    expect(planSave({ local: [a, b], cloud: cloudOf(a, b), meta }).writes).toEqual([]);
  });
  it("an edit always gets an updatedAt newer than the version it replaces", () => {
    const a = rec("a", 1, 5000);
    const plan = planSave({ local: [rec("a", 2, 100)], cloud: cloudOf(a), meta: synced(a) });
    expect(plan.writes[0].updatedAt).toBe(5001);
  });
  it("pending deletions become tombstones (state emptied); never-uploaded ones and already-deleted ones are skipped", () => {
    const a = rec("a", 1, 1000);
    const meta = synced(a);
    meta.deletes.a = { at: 4000, classId: "fp_mage", name: "P-a" };
    meta.deletes.ghost = { at: 4000, classId: "fp_mage", name: "ghost" };
    meta.deletes.gone = { at: 4000, classId: "fp_mage", name: "gone" };
    const plan = planSave({ local: [], cloud: cloudOf(a, tomb("gone", 3000)), meta });
    expect(plan.tombstones).toHaveLength(1);
    expect(plan.tombstones[0]).toMatchObject({ id: "a", deleted: true, state: "", updatedAt: 4000, name: "P-a", classId: "fp_mage" });
  });
  it(`caps an account at ${MAX_PROFILES} live profiles: new ones beyond it are rejected with a message (newest first), edits of existing ones are always allowed`, () => {
    const existing = Array.from({ length: MAX_PROFILES - 1 }, (_, i) => rec(`e${i}`, 1, 1000));
    const meta = synced(...existing);
    const local = [...existing.slice(0, 5).map((r) => rec(r.id, 2, 5000)), rec("n1", 1, 3000), rec("n2", 1, 4000), rec("n3", 1, 2000), ...existing.slice(5)];
    const plan = planSave({ local, cloud: cloudOf(...existing), meta });
    expect(plan.writes.filter((w) => w.id.startsWith("e"))).toHaveLength(5);
    expect(plan.writes.filter((w) => w.id.startsWith("n")).map((w) => w.id)).toEqual(["n2"]); // 49 + 1 = 50
    expect(plan.rejected.map((r) => [r.id, r.reason]).sort()).toEqual([["n1", "over-cap"], ["n3", "over-cap"]]);
    expect(plan.rejected[0].detail).toContain("at most 50");
    expect(plan.cloudLiveCount).toBe(MAX_PROFILES);
  });
  it("deleting profiles in the same save frees room for new ones", () => {
    const existing = Array.from({ length: MAX_PROFILES }, (_, i) => rec(`e${i}`, 1, 1000));
    const meta = synced(...existing);
    meta.deletes.e0 = { at: 4000, classId: "fp_mage", name: "P-e0" };
    const plan = planSave({ local: [...existing.slice(1), rec("new", 1, 3000)], cloud: cloudOf(...existing), meta });
    expect(plan.writes.map((w) => w.id)).toEqual(["new"]);
    expect(plan.rejected).toEqual([]);
  });
  it("size guard: a state over the limit is rejected with a friendly message and not written", () => {
    const big = rec("big", 1, 1000, { state: "x".repeat(MAX_STATE_CHARS + 1) });
    const ok = rec("ok", 1, 1000, { state: "x".repeat(MAX_STATE_CHARS) });
    const plan = planSave({ local: [big, ok], cloud: {}, meta: emptyMeta() });
    expect(plan.writes.map((w) => w.id)).toEqual(["ok"]);
    expect(plan.rejected).toHaveLength(1);
    expect(plan.rejected[0]).toMatchObject({ id: "big", reason: "too-large" });
    expect(plan.rejected[0].detail).toMatch(/too large .*limit is 180 KB/);
  });
  it("ids that Firestore / the rules would refuse are rejected", () => {
    const plan = planSave({ local: [rec("a/b"), rec("x".repeat(65)), rec("fine_id-1")], cloud: {}, meta: emptyMeta() });
    expect(plan.writes.map((w) => w.id)).toEqual(["fine_id-1"]);
    expect(plan.rejected.map((r) => r.reason)).toEqual(["bad-id", "bad-id"]);
  });
  it("skipped (local-only) profiles are never written; only expired tombstones are swept", () => {
    const meta = emptyMeta();
    meta.skipped.s = true;
    const plan = planSave({ local: [rec("s")], cloud: cloudOf(tomb("t", 1), rec("live")), meta, sweep: ["t", "live"] });
    expect(plan.writes).toEqual([]);
    expect(plan.sweep).toEqual(["t"]);
  });
  it("after a successful commit nothing is dirty any more", () => {
    const local = [rec("a", 1, 1000), rec("b", 1, 2000)];
    const meta0 = emptyMeta();
    meta0.deletes.z = { at: 1, classId: "c", name: "z" };
    meta0.baseline.z = { hash: "h", updatedAt: 1 };
    const plan = planSave({ local, cloud: { z: rec("z") }, meta: meta0 });
    const meta1 = applySaved(meta0, plan, NOW);
    expect(dirtyIds(local, meta1)).toEqual([]);
    expect(meta1.deletes).toEqual({});
    expect(meta1.baseline.z).toBeUndefined();
    expect(meta1.lastSyncAt).toBe(NOW);
    expect(meta1.userDocCreated).toBe(true);
  });
});

describe("settings", () => {
  const cloud = { theme: "dark" as const, lastClassId: "hero", updatedAt: 500 };
  it("a new device adopts the account's settings; an older copy is not applied again", () => {
    const m = mergeSettings(cloud, emptyMeta());
    expect(m.apply).toEqual(cloud);
    expect(m.meta.settingsUpdatedAt).toBe(500);
    expect(mergeSettings(cloud, m.meta).apply).toBeNull();
    expect(mergeSettings({ ...cloud, updatedAt: 900 }, m.meta).apply).not.toBeNull();
    expect(mergeSettings(null, emptyMeta()).apply).toBeNull();
  });
  it("dirty = the content differs from what was last written or applied", () => {
    const m = mergeSettings(cloud, emptyMeta()).meta;
    expect(settingsDirty({ theme: "dark", lastClassId: "hero" }, m)).toBe(false);
    expect(settingsDirty({ theme: "light", lastClassId: "hero" }, m)).toBe(true);
    expect(settingsDirty({ theme: "dark" }, emptyMeta())).toBe(true);
    expect(settingsHash({ theme: "dark" })).not.toBe(settingsHash({ theme: "dark", lastProfileId: "x" }));
  });
});

describe("history", () => {
  const h = (profileId: string, state: string, i = 0): HistoryEntry => ({ key: `${profileId}${i}`, profileId, name: profileId, classId: "c", state, versionUpdatedAt: i, at: i, reason: "replaced-by-cloud" });
  it("newest first, de-duplicated by profile + content, capped in count", () => {
    expect(addHistory([h("a", "s1")], [h("a", "s1", 1)])).toHaveLength(1);
    expect(addHistory([h("a", "s1")], [h("a", "s2", 1)]).map((e) => e.state)).toEqual(["s2", "s1"]);
    const many = addHistory([], Array.from({ length: HISTORY_MAX + 5 }, (_, i) => h("p", `state${i}`, i)));
    expect(many).toHaveLength(HISTORY_MAX);
    expect(many[0].state).toBe("state0");
  });
  it("is also capped in total size", () => {
    const big = "x".repeat(700_000);
    expect(addHistory([], [h("a", big + "1"), h("b", big + "2"), h("c", big + "3")])).toHaveLength(2);
  });
});
