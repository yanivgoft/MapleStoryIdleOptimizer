// The Firestore rules (deploy/firebase/firestore.rules) cannot be run here (they need the emulator, i.e. Java); this test pins everything that CAN be checked
// offline: the rules file lints, and the numbers / key lists in it agree with what the web client writes.  A mismatch would show up for the user as
// "permission denied" on the first Save, so it is worth a dedicated test.
import { describe, expect, it } from "vitest";
import { MAX_NAME_CHARS, MAX_STATE_CHARS, planSave, emptyMeta, validDocId } from "./merge";
import { USER_SCHEMA, buildOps, profileDoc, settingsDoc } from "./store";
import { rec, tombstone } from "./testkit";

// @ts-ignore node:fs has no type declarations unless @types/node is installed (it arrives transitively with firebase)
const fs = (await import("node:fs")) as { readFileSync(u: URL, enc: string): string };
const rules = fs.readFileSync(new URL("../../../../deploy/firebase/firestore.rules", import.meta.url), "utf8");
// @ts-ignore plain .mjs without declarations
const { lintRules } = (await import("../../../../deploy/firebase/rules-test/lint-rules.mjs")) as { lintRules(s: string): string[] };

const noComments = rules.replace(/\/\/.*$/gm, "");
const fn = (name: string): string => {
  const i = noComments.indexOf(`function ${name}(`);
  expect(i, name).toBeGreaterThan(-1);
  return noComments.slice(i, noComments.indexOf("\n    }", i));
};
const list = (body: string, kind: "hasOnly" | "hasAll"): string[] => {
  const m = new RegExp(`${kind}\\(\\[([^\\]]*)\\]\\)`).exec(body);
  expect(m, kind).toBeTruthy();
  return [...m![1].matchAll(/'([^']+)'/g)].map((x) => x[1]);
};

describe("firestore.rules", () => {
  it("lints clean, and the lint really does flag broken rules", () => {
    expect(lintRules(rules)).toEqual([]);
    expect(lintRules(rules.replace("request.auth != null &&", "request.resource.size() < 10 &&")).length).toBeGreaterThan(0);
    expect(lintRules(rules + "\n}")).not.toEqual([]);
  });
  it("is closed by default and owner-only", () => {
    expect(noComments).toMatch(/match \/\{document=\*\*\} \{\s*allow read, write: if false;/);
    expect(noComments).not.toMatch(/if true/);
    for (const m of noComments.matchAll(/allow [^:]+: if ([^;]+);/g)) if (m[1].trim() !== "false") expect(m[1]).toContain("signedInAs(uid)");
    expect(fn("signedInAs")).toContain("request.auth != null && request.auth.uid == uid");
  });
  it("the profile limits equal the client's", () => {
    const body = fn("validProfile");
    expect(body).toContain(`d.state.size() <= ${MAX_STATE_CHARS}`);
    expect(body).toContain(`d.name.size() <= ${MAX_NAME_CHARS}`);
    const re = noComments.match(/profileId\.matches\('([^']+)'\)/)![1];
    for (const id of ["a", "A_b-9", "x".repeat(64), "x".repeat(65), "", "a b", "a.b", "a/b"]) expect(new RegExp(re).test(id), id).toBe(validDocId(id));
  });
  it("the profile key list is exactly what the client can write", () => {
    const body = fn("validProfile");
    const allowed = list(body, "hasOnly").sort();
    const required = list(body, "hasAll").sort();
    const live = Object.keys(profileDoc(rec("a"))).sort();
    const dead = Object.keys(profileDoc(tombstone("a", 1))).sort();
    expect(allowed).toEqual([...new Set([...live, ...dead])].sort());
    for (const k of required) expect(live, k).toContain(k);
    for (const k of live) expect(allowed, k).toContain(k);
    expect(dead).toEqual([...required, "deleted"].sort());
  });
  it("the settings and user documents the client writes satisfy the key rules", () => {
    const s = fn("validSettings");
    const sAllowed = list(s, "hasOnly");
    for (const doc of [settingsDoc({ theme: "dark", lastClassId: "hero", lastProfileId: "p", updatedAt: 1 }), settingsDoc({ theme: "auto", updatedAt: 1 })]) {
      for (const k of Object.keys(doc)) expect(sAllowed, k).toContain(k);
      for (const k of list(s, "hasAll")) expect(Object.keys(doc), k).toContain(k);
    }
    expect(s).toContain("d.theme in ['auto', 'light', 'dark']");
    const u = fn("validUser");
    const ops = buildOps("u", { writes: [], tombstones: [], sweep: [], rejected: [], cloudLiveCount: 0 }, { now: 1, createUserDoc: true });
    const userOp = ops.find((o) => o.type === "set" && o.path === "users/u");
    expect(userOp).toBeTruthy();
    const userData = (userOp as { data: Record<string, unknown> }).data;
    for (const k of Object.keys(userData)) expect(list(u, "hasOnly"), k).toContain(k);
    for (const k of list(u, "hasAll")) expect(Object.keys(userData), k).toContain(k);
    expect(u).toMatch(/d\.schema >= 1 && d\.schema < 100/);
    expect(USER_SCHEMA).toBeGreaterThanOrEqual(1);
    expect(USER_SCHEMA).toBeLessThan(100);
  });
  it("the paths the client uses are the ones the rules match", () => {
    for (const frag of ["match /users/{uid}", "match /profiles/{profileId}", "match /settings/{docId}", "docId == 'app'"]) expect(noComments).toContain(frag);
    const plan = planSave({ local: [rec("a")], cloud: {}, meta: emptyMeta() });
    const ops = buildOps("u", plan, { now: 1, createUserDoc: false, settings: { theme: "auto", updatedAt: 1 } });
    for (const o of ops) expect(o.path).toMatch(/^users\/u(\/profiles\/[A-Za-z0-9_-]+|\/settings\/app)?$/);
  });
});
