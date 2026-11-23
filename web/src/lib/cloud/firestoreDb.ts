// The CloudDb implementation on top of the Firebase Firestore modular SDK.  It only needs the handful of functions below (the real `firebase/firestore`
// module satisfies this shape), which is also what the tests fake.  Deliberately absent: onSnapshot / any listener.
import type { CloudDb, DbOp, RawDoc } from "./store";
import { profilesPath, settingsPath, userPath } from "./store";

export interface FirestoreSdk {
  doc(db: unknown, path: string): unknown;
  collection(db: unknown, path: string): unknown;
  getDoc(ref: unknown): Promise<{ exists(): boolean; id: string; data(): Record<string, unknown> | undefined }>;
  getDocs(ref: unknown): Promise<{ docs: { id: string; data(): Record<string, unknown> }[] }>;
  writeBatch(db: unknown): {
    set(ref: unknown, data: Record<string, unknown>, options?: { merge?: boolean }): unknown;
    delete(ref: unknown): unknown;
    commit(): Promise<void>;
  };
}

export function createFirestoreDb(sdk: FirestoreSdk, db: unknown): CloudDb {
  const one = async (path: string): Promise<RawDoc | null> => {
    const snap = await sdk.getDoc(sdk.doc(db, path));
    return snap.exists() ? { id: snap.id, data: snap.data() ?? {} } : null;
  };
  return {
    async readProfiles(uid) {
      const snap = await sdk.getDocs(sdk.collection(db, profilesPath(uid))); // ONE query: one read per document returned
      return snap.docs.map((d) => ({ id: d.id, data: d.data() }));
    },
    readSettings: (uid) => one(settingsPath(uid)),
    readUser: (uid) => one(userPath(uid)),
    async commit(ops: DbOp[]) {
      const batch = sdk.writeBatch(db);
      for (const op of ops) {
        const ref = sdk.doc(db, op.path);
        if (op.type === "delete") batch.delete(ref);
        else if (op.merge) batch.set(ref, op.data, { merge: true });
        else batch.set(ref, op.data);
      }
      await batch.commit();
    },
  };
}
