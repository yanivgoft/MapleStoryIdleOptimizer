// Accounts: the ONLY place the Firebase SDK is loaded, and only through dynamic import(): the SDK is a separate chunk that is downloaded when the user clicks
// "Sign in" or when a previous session is restored (see localPorts.ts: the session flag).  A signed-out visitor never downloads it.  Never import "firebase/..." statically anywhere.
import type { FirebaseConfig } from "./config";
import type { AuthSdk } from "./auth";
import type { FirestoreSdk } from "./firestoreDb";

export interface FirebaseHandle {
  auth: unknown; // firebase Auth instance
  db: unknown; // firebase Firestore instance
  authSdk: AuthSdk;
  fsSdk: FirestoreSdk;
}

let pending: Promise<FirebaseHandle> | null = null;

export function loadFirebase(config: FirebaseConfig): Promise<FirebaseHandle> {
  pending ??= (async () => {
    const [appMod, authMod, fsMod] = await Promise.all([import("firebase/app"), import("firebase/auth"), import("firebase/firestore/lite")]);
    const app = appMod.getApps().length ? appMod.getApp() : appMod.initializeApp(config);
    return {
      auth: authMod.getAuth(app),
      // Firestore LITE: only get / query / batch writes (REST), no realtime listeners and no offline cache (so no IndexedDB copy of the user's data is left behind)
      // and ~5x smaller than the full SDK.  It is exactly the feature set the sync design uses.
      db: fsMod.getFirestore(app),
      authSdk: authMod as unknown as AuthSdk,
      fsSdk: fsMod as unknown as FirestoreSdk,
    };
  })().catch((e) => {
    pending = null; // allow a retry after a failed chunk download
    throw e;
  });
  return pending;
}
