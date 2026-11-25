import { afterEach, describe, expect, it } from "vitest";
import { clearDraft, DRAFT_KEY, loadDraft, parseDraft, saveDraft, STORAGE_FAIL_MESSAGE, type DraftStorage } from "./draft";
import { listProfiles, saveProfile, SAVE_FAIL_MESSAGE } from "./profiles";
import { initialState, normalizeState, setValue, switchContentType } from "./schemaForm";
import { fixtureFor } from "../test/fixtures";

const c = fixtureFor("fp_mage");
const state = () => setValue(initialState(c.schema, c.defaults["World Boss"], "World Boss"), c.schema.fields.find((f) => f.key === "flat_attack")!, 123456789);

function memory(): DraftStorage & { data: Map<string, string> } {
  const data = new Map<string, string>();
  return { data, getItem: (k) => data.get(k) ?? null, setItem: (k, v) => void data.set(k, v), removeItem: (k) => void data.delete(k) };
}
const full = (): DraftStorage => ({ getItem: () => null, setItem: () => { throw new DOMException("quota", "QuotaExceededError"); }, removeItem: () => undefined });

describe("draft autosave", () => {
  it("saves under msi.draft.v1 and restores the same state", () => {
    const m = memory();
    const s = switchContentType(state(), c.schema, "Chapter Hunt", c.defaults["Chapter Hunt"]);
    expect(saveDraft(s, m)).toBe(true);
    expect(DRAFT_KEY).toBe("msi.draft.v1");
    expect(m.data.has("msi.draft.v1")).toBe(true);
    const back = loadDraft(m)!;
    expect(back.classId).toBe("fp_mage");
    expect(normalizeState(c.schema, back)).toEqual(normalizeState(c.schema, s));
    expect(back.perContent["Chapter Hunt"].flat_attack).toBe(123456789);                 // the seeded copy came along
    expect(back.editOrder).toEqual(s.editOrder);
  });
  it("nothing stored, junk, a wrong version or a profile-less shape all read as no draft", () => {
    const m = memory();
    expect(loadDraft(m)).toBeNull();
    for (const raw of ["", "not json", "null", "[]", '{"v":2,"state":{}}', '{"v":1}', '{"v":1,"state":{"classId":5}}']) expect(parseDraft(raw), raw).toBeNull();
  });
  it("a refusing browser (quota / blocked) reports false and never throws; reading and clearing are safe too", () => {
    expect(saveDraft(state(), full())).toBe(false);
    expect(saveDraft(state(), null)).toBe(false);
    const throwing: DraftStorage = { getItem: () => { throw new Error("blocked"); }, setItem: () => { throw new Error("blocked"); }, removeItem: () => { throw new Error("blocked"); } };
    expect(loadDraft(throwing)).toBeNull();
    expect(() => clearDraft(throwing)).not.toThrow();
    expect(STORAGE_FAIL_MESSAGE.length).toBeLessThan(120);                                // one short message
    expect(STORAGE_FAIL_MESSAGE).not.toMatch(/localStorage|quota/i);
  });
  it("clearDraft removes it", () => {
    const m = memory();
    saveDraft(state(), m);
    clearDraft(m);
    expect(loadDraft(m)).toBeNull();
  });
});

describe("profile storage errors", () => {
  afterEach(() => delete (globalThis as { localStorage?: unknown }).localStorage);
  it("saving into a full / blocked storage throws one readable message and keeps the old list", () => {
    const data = new Map<string, string>();
    let refuse = false;
    (globalThis as { localStorage?: unknown }).localStorage = {
      getItem: (k: string) => data.get(k) ?? null,
      setItem: (k: string, v: string) => { if (refuse) throw new DOMException("quota", "QuotaExceededError"); data.set(k, v); },
    };
    saveProfile("keep", state());
    refuse = true;
    expect(() => saveProfile("lost", state())).toThrow(SAVE_FAIL_MESSAGE);
    expect(listProfiles().map((p) => p.name)).toEqual(["keep"]);
    expect(SAVE_FAIL_MESSAGE).not.toMatch(/localStorage|quota/i);
  });
});
