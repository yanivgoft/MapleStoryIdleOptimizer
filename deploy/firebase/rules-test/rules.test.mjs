// Tests of ../firestore.rules against the Firestore EMULATOR.  Run from this directory (needs Java 21+ for the emulator):
//
//   npm install
//   npm run test:emulator        # = firebase emulators:exec --only firestore "npm test"
//
// (or start the emulator yourself with `npx firebase-tools emulators:start --only firestore --project demo-msi-rules`, then `FIRESTORE_EMULATOR_HOST=127.0.0.1:8080 npm test`).
// The documents below have exactly the shapes the web app writes (web/src/lib/cloud/store.ts: profileDoc / settingsDoc / buildOps).
import { readFileSync } from "node:fs";
import { after, before, beforeEach, describe, test } from "node:test";
import { assertFails, assertSucceeds, initializeTestEnvironment } from "@firebase/rules-unit-testing";
import { collection, deleteDoc, doc, getDoc, getDocs, setDoc, updateDoc, writeBatch } from "firebase/firestore";

const RULES = readFileSync(new URL("../firestore.rules", import.meta.url), "utf8");
let env;

const profile = (over = {}) => ({ classId: "fp_mage", name: "Main", updatedAt: 1_800_000_000_000, state: JSON.stringify({ classId: "fp_mage", shared: { level: 140 } }), ...over });
const tombstone = (over = {}) => ({ classId: "fp_mage", name: "Main", updatedAt: 1_800_000_000_001, deleted: true, state: "", ...over });
const settings = (over = {}) => ({ theme: "dark", lastClassId: "fp_mage", lastProfileId: "abc123", updatedAt: 1_800_000_000_000, ...over });
const userDoc = (over = {}) => ({ lastSeenAt: 1_800_000_000_000, schema: 1, createdAt: 1_800_000_000_000, ...over });

before(async () => {
  env = await initializeTestEnvironment({ projectId: "demo-msi-rules", firestore: { rules: RULES } });
});
after(async () => {
  await env?.cleanup();
});
beforeEach(async () => {
  await env.clearFirestore();
});

const alice = () => env.authenticatedContext("alice").firestore();
const bob = () => env.authenticatedContext("bob").firestore();
const anon = () => env.unauthenticatedContext().firestore();
const seed = (fn) => env.withSecurityRulesDisabled(async (ctx) => fn(ctx.firestore()));

describe("owner", () => {
  test("can create, read, update, list and delete their profiles", async () => {
    const db = alice();
    await assertSucceeds(setDoc(doc(db, "users/alice/profiles/p1"), profile()));
    await assertSucceeds(getDoc(doc(db, "users/alice/profiles/p1")));
    await assertSucceeds(setDoc(doc(db, "users/alice/profiles/p1"), profile({ name: "Renamed", updatedAt: 1_800_000_000_500 })));
    await assertSucceeds(updateDoc(doc(db, "users/alice/profiles/p1"), { updatedAt: 1_800_000_000_900 }));
    await assertSucceeds(getDocs(collection(db, "users/alice/profiles")));
    await assertSucceeds(deleteDoc(doc(db, "users/alice/profiles/p1")));
  });
  test("can write the user document and the settings, exactly as the web app does", async () => {
    const db = alice();
    await assertSucceeds(setDoc(doc(db, "users/alice"), { lastSeenAt: 1, schema: 1, createdAt: 1 }, { merge: true }));
    await assertSucceeds(setDoc(doc(db, "users/alice"), { lastSeenAt: 2, schema: 1 }, { merge: true })); // later saves omit createdAt
    await assertSucceeds(getDoc(doc(db, "users/alice")));
    await assertSucceeds(setDoc(doc(db, "users/alice/settings/app"), settings()));
    await assertSucceeds(setDoc(doc(db, "users/alice/settings/app"), { theme: "auto", updatedAt: 5 })); // optional fields omitted
    await assertSucceeds(getDoc(doc(db, "users/alice/settings/app")));
  });
  test("one 'Save to account' batch (profiles + tombstone + sweep + settings + user doc) is accepted", async () => {
    await seed((db) => setDoc(doc(db, "users/alice/profiles/old"), tombstone()));
    const db = alice();
    const b = writeBatch(db);
    b.set(doc(db, "users/alice/profiles/p1"), profile());
    b.set(doc(db, "users/alice/profiles/p2"), profile({ name: "Alt" }));
    b.set(doc(db, "users/alice/profiles/gone"), tombstone());
    b.delete(doc(db, "users/alice/profiles/old"));
    b.set(doc(db, "users/alice/settings/app"), settings());
    b.set(doc(db, "users/alice"), { lastSeenAt: 3, schema: 1, createdAt: 3 }, { merge: true });
    await assertSucceeds(b.commit());
  });
  test("account deletion: every document can be deleted", async () => {
    await seed(async (db) => {
      await setDoc(doc(db, "users/alice"), userDoc());
      await setDoc(doc(db, "users/alice/profiles/p1"), profile());
      await setDoc(doc(db, "users/alice/profiles/t"), tombstone());
      await setDoc(doc(db, "users/alice/settings/app"), settings());
    });
    const db = alice();
    const b = writeBatch(db);
    for (const p of ["users/alice/profiles/p1", "users/alice/profiles/t", "users/alice/settings/app", "users/alice"]) b.delete(doc(db, p));
    await assertSucceeds(b.commit());
  });
});

describe("everybody else", () => {
  beforeEach(async () => {
    await seed(async (db) => {
      await setDoc(doc(db, "users/alice"), userDoc());
      await setDoc(doc(db, "users/alice/profiles/p1"), profile());
      await setDoc(doc(db, "users/alice/settings/app"), settings());
    });
  });
  test("another signed-in user cannot read, list, write or delete", async () => {
    const db = bob();
    await assertFails(getDoc(doc(db, "users/alice/profiles/p1")));
    await assertFails(getDocs(collection(db, "users/alice/profiles")));
    await assertFails(getDoc(doc(db, "users/alice/settings/app")));
    await assertFails(getDoc(doc(db, "users/alice")));
    await assertFails(setDoc(doc(db, "users/alice/profiles/p2"), profile()));
    await assertFails(setDoc(doc(db, "users/alice/profiles/p1"), profile({ name: "hijacked" })));
    await assertFails(deleteDoc(doc(db, "users/alice/profiles/p1")));
    await assertFails(setDoc(doc(db, "users/alice/settings/app"), settings()));
    await assertFails(setDoc(doc(db, "users/alice"), userDoc()));
  });
  test("an unauthenticated visitor cannot do anything", async () => {
    const db = anon();
    await assertFails(getDoc(doc(db, "users/alice/profiles/p1")));
    await assertFails(getDocs(collection(db, "users/alice/profiles")));
    await assertFails(setDoc(doc(db, "users/alice/profiles/p2"), profile()));
    await assertFails(deleteDoc(doc(db, "users/alice/profiles/p1")));
    await assertFails(getDoc(doc(db, "users/alice/settings/app")));
    await assertFails(setDoc(doc(db, "users/anon/profiles/p"), profile()));
  });
  test("a user cannot list the users collection or write elsewhere", async () => {
    await assertFails(getDocs(collection(alice(), "users")));
    await assertFails(setDoc(doc(alice(), "other/doc"), { a: 1 }));
    await assertFails(getDoc(doc(alice(), "other/doc")));
    await assertFails(setDoc(doc(alice(), "users/alice/extra/doc"), { a: 1 }));
  });
});

describe("profile documents: shape and size", () => {
  const put = (data, id = "p1") => setDoc(doc(alice(), `users/alice/profiles/${id}`), data);
  test("unknown keys are rejected", async () => {
    await assertFails(put(profile({ extra: 1 })));
    await assertFails(put(profile({ owner: "bob" })));
  });
  test("missing required keys are rejected", async () => {
    for (const k of ["classId", "name", "updatedAt", "state"]) {
      const p = profile();
      delete p[k];
      await assertFails(put(p));
    }
  });
  test("wrong types are rejected", async () => {
    await assertFails(put(profile({ classId: 5 })));
    await assertFails(put(profile({ name: 5 })));
    await assertFails(put(profile({ updatedAt: "2026-11-23" })));
    await assertFails(put(profile({ state: { classId: "fp_mage" } }))); // a map, not the JSON string
    await assertFails(put(profile({ state: ["x"] })));
    await assertFails(put(profile({ deleted: "yes" })));
    await assertFails(put(profile({ deleted: 1 })));
    await assertFails(put(profile({ updatedAt: null })));
  });
  test("name: 1..80 characters", async () => {
    await assertSucceeds(put(profile({ name: "n".repeat(80) })));
    await assertFails(put(profile({ name: "n".repeat(81) })));
    await assertFails(put(profile({ name: "" })));
  });
  test("state is capped at 180000 characters", async () => {
    await assertSucceeds(put(profile({ state: "x".repeat(180_000) })));
    await assertFails(put(profile({ state: "x".repeat(180_001) })));
    await assertFails(put(profile({ state: "x".repeat(400_000) })));
  });
  test("a live profile needs content; a tombstone must carry none", async () => {
    await assertFails(put(profile({ state: "" })));
    await assertSucceeds(put(tombstone()));
    await assertFails(put(tombstone({ state: "{}" })));
    await assertSucceeds(put(profile({ deleted: false })));
    await assertFails(put(profile({ deleted: false, state: "" })));
  });
  test("profile ids: letters, digits, _ and - up to 64 characters", async () => {
    await assertSucceeds(put(profile(), "Abc_123-x"));
    await assertSucceeds(put(profile(), "a".repeat(64)));
    await assertFails(put(profile(), "a".repeat(65)));
    await assertFails(put(profile(), "has space"));
    await assertFails(put(profile(), "dots.not.allowed"));
  });
  test("classId is capped at 64 characters", async () => {
    await assertFails(put(profile({ classId: "c".repeat(65) })));
    await assertFails(put(profile({ classId: "" })));
  });
});

describe("settings and user documents: shape", () => {
  const putS = (data, id = "app") => setDoc(doc(alice(), `users/alice/settings/${id}`), data);
  test("settings: only the known keys, a known theme, short ids, document id 'app'", async () => {
    await assertFails(putS(settings({ extra: 1 })));
    await assertFails(putS(settings({ theme: "neon" })));
    await assertFails(putS(settings({ theme: 1 })));
    await assertFails(putS(settings({ updatedAt: "now" })));
    await assertFails(putS(settings({ lastClassId: "c".repeat(65) })));
    await assertFails(putS(settings({ lastProfileId: 5 })));
    await assertFails(putS({ updatedAt: 1 })); // theme missing
    await assertFails(putS(settings(), "other"));
    await assertSucceeds(putS(settings({ lastClassId: "c".repeat(64) })));
  });
  test("settings stay under 4 KB whatever is written", async () => {
    await assertFails(putS(settings({ lastClassId: "x".repeat(5000) })));
    await assertFails(putS({ ...settings(), blob: "x".repeat(5000) }));
  });
  test("user document: only createdAt / lastSeenAt / schema", async () => {
    const putU = (data) => setDoc(doc(alice(), "users/alice"), data);
    await assertSucceeds(putU(userDoc()));
    await assertFails(putU(userDoc({ email: "a@b.c" })));
    await assertFails(putU(userDoc({ schema: "1" })));
    await assertFails(putU(userDoc({ schema: 0 })));
    await assertFails(putU(userDoc({ lastSeenAt: "x" })));
    await assertFails(putU({ schema: 1 })); // lastSeenAt missing
  });
});
