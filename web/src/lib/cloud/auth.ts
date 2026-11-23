// Accounts: Google sign-in on top of Firebase Auth, behind a narrow interface (AuthSdk) so that the flow logic is testable without the SDK.
// Sign-in: a popup; when the browser blocks it (or cannot show one) the full-page redirect flow is used instead.  Deleting the account re-authenticates
// FIRST (before any data is deleted), then the data is deleted, then the Auth user.
export interface AccountUser {
  uid: string;
  email: string | null;
  displayName: string | null;
  photoURL: string | null;
}

/** The part of the Firebase Auth user / SDK this module touches (the real `firebase/auth` module satisfies it). */
export interface FbUserLike {
  uid: string;
  email: string | null;
  displayName: string | null;
  photoURL: string | null;
}
export interface AuthSdk {
  GoogleAuthProvider: new () => { setCustomParameters(p: Record<string, string>): unknown };
  onAuthStateChanged(auth: unknown, next: (u: FbUserLike | null) => void, error?: (e: Error) => void): () => void;
  signInWithPopup(auth: unknown, provider: unknown): Promise<unknown>;
  signInWithRedirect(auth: unknown, provider: unknown): Promise<void>;
  getRedirectResult(auth: unknown): Promise<unknown>;
  signOut(auth: unknown): Promise<void>;
  reauthenticateWithPopup(user: unknown, provider: unknown): Promise<unknown>;
  deleteUser(user: unknown): Promise<void>;
}
export interface AuthHandle {
  auth: unknown;
  authSdk: AuthSdk;
}

export const toAccountUser = (u: FbUserLike): AccountUser => ({ uid: u.uid, email: u.email, displayName: u.displayName, photoURL: u.photoURL });

const code = (e: unknown): string => String((e as { code?: unknown })?.code ?? "");

/** Popup problems that call for the redirect flow instead. */
export const POPUP_FALLBACK_CODES = ["auth/popup-blocked", "auth/operation-not-supported-in-this-environment", "auth/web-storage-unsupported"];
/** The user closed / abandoned the popup: not an error. */
export const CANCEL_CODES = ["auth/popup-closed-by-user", "auth/cancelled-popup-request", "auth/user-cancelled"];

export function subscribeAuth(h: AuthHandle, onUser: (u: AccountUser | null) => void, onError?: (e: Error) => void): () => void {
  return h.authSdk.onAuthStateChanged(h.auth, (u) => onUser(u ? toAccountUser(u) : null), onError);
}

function provider(h: AuthHandle) {
  const p = new h.authSdk.GoogleAuthProvider();
  p.setCustomParameters({ prompt: "select_account" });
  return p;
}

export type SignInOutcome = "popup" | "redirect" | "cancelled";

/** Google popup; falls back to the redirect flow when the popup is blocked (the page then reloads and `finishRedirect` picks the result up). */
export async function signInWithGoogle(h: AuthHandle): Promise<SignInOutcome> {
  try {
    await h.authSdk.signInWithPopup(h.auth, provider(h));
    return "popup";
  } catch (e) {
    if (CANCEL_CODES.includes(code(e))) return "cancelled";
    if (POPUP_FALLBACK_CODES.includes(code(e))) {
      await h.authSdk.signInWithRedirect(h.auth, provider(h));
      return "redirect";
    }
    throw e;
  }
}

/** Call once at startup after a redirect sign-in; errors are returned, not thrown (the auth-state subscription delivers the user). */
export async function finishRedirect(h: AuthHandle): Promise<Error | null> {
  try {
    await h.authSdk.getRedirectResult(h.auth);
    return null;
  } catch (e) {
    return e instanceof Error ? e : new Error(String(e));
  }
}

export const signOutUser = (h: AuthHandle): Promise<void> => h.authSdk.signOut(h.auth);

export function describeAuthError(e: unknown): string {
  switch (code(e)) {
    case "auth/network-request-failed":
      return "No connection to Google. Check your network and try again.";
    case "auth/popup-blocked":
      return "The sign-in window was blocked by your browser. Allow pop-ups for this site and try again.";
    case "auth/unauthorized-domain":
      return "This site's address is not authorized for sign-in yet (Firebase console > Authentication > Settings > Authorized domains).";
    case "auth/operation-not-allowed":
      return "Google sign-in is not enabled for this project yet (Firebase console > Authentication > Sign-in method).";
    case "auth/user-disabled":
      return "This Google account has been disabled for this app.";
    case "auth/too-many-requests":
      return "Too many attempts. Wait a few minutes and try again.";
    case "auth/requires-recent-login":
      return "For your safety the account can only be deleted right after signing in. Sign in again and retry.";
    case "auth/user-mismatch":
      return "You signed in with a different Google account than the one being deleted. Use the same account.";
    default:
      return `Sign-in failed (${(e as Error)?.message || code(e) || "unknown error"}).`;
  }
}

/** Delete-account order: (1) re-authenticate with a fresh Google sign-in, so nothing is half-deleted when it fails; (2) `deleteData`; (3) the Auth user. */
export async function deleteAccount(h: AuthHandle, user: unknown, uid: string, deleteData: () => Promise<void>): Promise<void> {
  const res = (await h.authSdk.reauthenticateWithPopup(user, provider(h))) as { user?: { uid?: string } } | undefined;
  const again = res?.user?.uid;
  if (again && again !== uid) throw Object.assign(new Error("different account"), { code: "auth/user-mismatch" });
  await deleteData();
  await h.authSdk.deleteUser(user);
}
