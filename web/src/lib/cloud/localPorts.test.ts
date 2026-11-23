import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { browserLocalPort, browserMetaPort, browserSettingsPort, canonicalRec, hasSessionFlag, markPrivacySeen, privacySeen, profileToRec, recToProfile, setSessionFlag, LAST_UID_KEY, META_KEY } from "./localPorts";
import { deleteProfile, listProfiles, saveProfile } from "../profiles";
import { initialState } from "../schemaForm";
import { fixtureFor } from "../../test/fixtures";
import { emptyMeta, stableStringify } from "./merge";
import { THEME_KEY as READ_THEME_KEY } from "../theme";

function memoryStorage() {
  const m = new Map<string, string>();
  return {
    m,
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null),
    setItem: (k: string, v: string) => void m.set(k, String(v)),
    removeItem: (k: string) => void m.delete(k),
  };
}
const fp = fixtureFor("fp_mage");
const state = (v = 0) => ({ ...initialState(fp.schema, fp.defaults["World Boss"], "World Boss"), shared: { level: 100 + v } });

let mem: ReturnType<typeof memoryStorage>;
beforeEach(() => {
  mem = memoryStorage();
  vi.stubGlobal("localStorage", mem);
});
afterEach(() => vi.unstubAllGlobals());

describe("profile <-> cloud record", () => {
  it("a saved profile maps to a record with a canonical JSON state and back to the same profile", () => {
    const p = saveProfile("Main", state());
    const rec = profileToRec(p);
    expect(rec).toMatchObject({ id: p.id, classId: "fp_mage", name: "Main", updatedAt: Date.parse(p.savedAt) });
    expect(rec.state).toBe(stableStringify(p.state));
    const back = recToProfile(rec)!;
    expect(back.id).toBe(p.id);
    expect(back.name).toBe("Main");
    expect(profileToRec(back).state).toBe(rec.state); // lossless through the app's own import normalisation
    expect(canonicalRec(rec)).toEqual(rec);
  });
  it("junk is rejected, tombstones are not profiles", () => {
    const rec = profileToRec(saveProfile("Main", state()));
    expect(recToProfile({ ...rec, state: "{not json" })).toBeNull();
    expect(recToProfile({ ...rec, state: "{}" })).toBeNull();
    expect(recToProfile({ ...rec, deleted: true, state: "" })).toBeNull();
    expect(canonicalRec({ ...rec, state: '"x"' })).toBeNull();
  });
});

describe("browser local port", () => {
  it("put keeps ids exactly (even when another profile has the same name + class), remove / clear work, changes are announced", () => {
    const port = browserLocalPort();
    const calls: number[] = [];
    const off = port.subscribe(() => calls.push(1));
    const mine = saveProfile("Same name", state(1));
    const fromCloud = { ...profileToRec(mine), id: "cloudid", updatedAt: Date.now() + 1000, state: stableStringify(state(2)) };
    port.put([fromCloud]);
    const ids = listProfiles().map((p) => p.id).sort();
    expect(ids).toEqual([mine.id, "cloudid"].sort()); // the app's importProfiles would have merged them; the id-exact upsert does not
    port.remove(["cloudid"]);
    expect(listProfiles().map((p) => p.id)).toEqual([mine.id]);
    deleteProfile(mine.id);
    expect(calls.length).toBeGreaterThanOrEqual(4); // save, put, remove, delete
    port.put([]);
    port.clear();
    expect(listProfiles()).toEqual([]);
    off();
    const n = calls.length;
    saveProfile("after unsubscribe", state());
    expect(calls.length).toBe(n);
  });
  it("listRecs reflects the stored profiles", () => {
    saveProfile("A", state(1));
    saveProfile("B", state(2));
    expect(browserLocalPort().listRecs().map((r) => r.name)).toEqual(["A", "B"]);
  });
});

describe("metadata, history, flags", () => {
  it("meta round-trips per uid; garbage reads as 'never synced'", () => {
    const port = browserMetaPort();
    expect(port.load("u1")).toBeNull();
    const m = emptyMeta();
    m.baseline.a = { hash: "h", updatedAt: 3 };
    m.lastSyncAt = 9;
    port.save("u1", m);
    expect(port.load("u1")).toEqual(m);
    expect(port.load("u2")).toBeNull();
    mem.m.set(META_KEY + "u1", "{broken");
    expect(port.load("u1")).toBeNull();
    port.save("u1", m);
    port.clear("u1");
    expect(port.load("u1")).toBeNull();
  });
  it("last uid and history", () => {
    const port = browserMetaPort();
    expect(port.lastUid()).toBeNull();
    port.setLastUid("u1");
    expect(port.lastUid()).toBe("u1");
    port.setLastUid(null);
    expect(mem.m.has(LAST_UID_KEY)).toBe(false);
    expect(port.loadHistory()).toEqual([]);
    const h = { key: "k", profileId: "a", name: "n", classId: "c", state: "{}", versionUpdatedAt: 1, at: 2, reason: "replaced-by-cloud" as const };
    port.saveHistory([h]);
    expect(port.loadHistory()).toEqual([h]);
    port.saveHistory([]);
    expect(port.loadHistory()).toEqual([]);
    mem.m.set("msi.cloud.history.v1", '[{"nope":1}]');
    expect(port.loadHistory()).toEqual([]);
  });
  it("session and privacy flags", () => {
    expect(hasSessionFlag()).toBe(false);
    setSessionFlag(true);
    expect(hasSessionFlag()).toBe(true);
    setSessionFlag(false);
    expect(hasSessionFlag()).toBe(false);
    expect(privacySeen()).toBe(false);
    markPrivacySeen();
    expect(privacySeen()).toBe(true);
  });
  it("blocked storage never throws", () => {
    vi.stubGlobal("localStorage", { getItem: () => { throw new Error("blocked"); }, setItem: () => { throw new Error("blocked"); }, removeItem: () => { throw new Error("blocked"); } });
    expect(hasSessionFlag()).toBe(false);
    expect(() => setSessionFlag(true)).not.toThrow();
    expect(browserMetaPort().load("u")).toBeNull();
    expect(() => browserMetaPort().save("u", emptyMeta())).not.toThrow();
  });
});

describe("settings port", () => {
  it("reads the stored theme + the class / profile it is given; applying writes the theme and tells the app", () => {
    const applied: unknown[] = [];
    const port = browserSettingsPort(() => ({ lastClassId: "hero" }), (s) => applied.push(s));
    expect(port.read()).toEqual({ theme: "auto", lastClassId: "hero" });
    port.apply({ theme: "dark", lastClassId: "bishop", updatedAt: 1 });
    expect(mem.m.get(READ_THEME_KEY)).toBe("dark");
    expect(port.read().theme).toBe("dark");
    expect(applied).toEqual([{ theme: "dark", lastClassId: "bishop", updatedAt: 1 }]);
    port.apply({ theme: "auto", updatedAt: 2 });
    expect(mem.m.has(READ_THEME_KEY)).toBe(false);
  });
});
