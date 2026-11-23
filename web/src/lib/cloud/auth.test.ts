import { describe, expect, it } from "vitest";
import { CANCEL_CODES, POPUP_FALLBACK_CODES, deleteAccount, describeAuthError, finishRedirect, signInWithGoogle, signOutUser, subscribeAuth, type AuthHandle, type AuthSdk } from "./auth";

function fakeAuth(over: Partial<Record<keyof AuthSdk, unknown>> = {}) {
  const calls: string[] = [];
  const params: Record<string, string>[] = [];
  class Provider {
    setCustomParameters(p: Record<string, string>) {
      params.push(p);
    }
  }
  const sdk = {
    GoogleAuthProvider: Provider,
    onAuthStateChanged: (_a: unknown, next: (u: unknown) => void) => {
      calls.push("onAuthStateChanged");
      next({ uid: "u1", email: "a@b.c", displayName: "A", photoURL: null, extra: "dropped" });
      return () => calls.push("unsubscribe");
    },
    signInWithPopup: async () => void calls.push("popup"),
    signInWithRedirect: async () => void calls.push("redirect"),
    getRedirectResult: async () => void calls.push("redirectResult"),
    signOut: async () => void calls.push("signOut"),
    reauthenticateWithPopup: async () => (calls.push("reauth"), { user: { uid: "u1" } }),
    deleteUser: async () => void calls.push("deleteUser"),
    ...over,
  } as unknown as AuthSdk;
  const handle: AuthHandle = { auth: { auth: true }, authSdk: sdk };
  return { handle, calls, params };
}
const err = (code: string) => Object.assign(new Error(code), { code });

describe("Google sign-in", () => {
  it("uses the popup and always lets the user pick an account", async () => {
    const { handle, calls, params } = fakeAuth();
    expect(await signInWithGoogle(handle)).toBe("popup");
    expect(calls).toEqual(["popup"]);
    expect(params).toEqual([{ prompt: "select_account" }]);
  });
  it.each(POPUP_FALLBACK_CODES)("falls back to the redirect flow when the popup fails with %s", async (code) => {
    const { handle, calls } = fakeAuth({ signInWithPopup: async () => { throw err(code); } });
    expect(await signInWithGoogle(handle)).toBe("redirect");
    expect(calls).toEqual(["redirect"]);
  });
  it.each(CANCEL_CODES)("a closed popup (%s) is a quiet cancel, not an error and not a redirect", async (code) => {
    const { handle, calls } = fakeAuth({ signInWithPopup: async () => { throw err(code); } });
    expect(await signInWithGoogle(handle)).toBe("cancelled");
    expect(calls).toEqual([]);
  });
  it("other errors are thrown with a friendly description available", async () => {
    const { handle } = fakeAuth({ signInWithPopup: async () => { throw err("auth/unauthorized-domain"); } });
    const e = await signInWithGoogle(handle).catch((x) => x);
    expect(describeAuthError(e)).toMatch(/Authorized domains/);
    expect(describeAuthError(err("auth/network-request-failed"))).toMatch(/connection/i);
    expect(describeAuthError(err("auth/operation-not-allowed"))).toMatch(/not enabled/);
    expect(describeAuthError(new Error("weird"))).toContain("weird");
  });
  it("auth state is exposed as a plain AccountUser (nothing else of the SDK object leaks)", () => {
    const { handle } = fakeAuth();
    const seen: unknown[] = [];
    const off = subscribeAuth(handle, (u) => seen.push(u));
    expect(seen).toEqual([{ uid: "u1", email: "a@b.c", displayName: "A", photoURL: null }]);
    off();
  });
  it("finishRedirect returns the error instead of throwing; sign-out calls the SDK", async () => {
    expect(await finishRedirect(fakeAuth().handle)).toBeNull();
    const bad = fakeAuth({ getRedirectResult: async () => { throw err("auth/x"); } });
    expect((await finishRedirect(bad.handle))?.message).toBe("auth/x");
    const f = fakeAuth();
    await signOutUser(f.handle);
    expect(f.calls).toEqual(["signOut"]);
  });
});

describe("delete account", () => {
  it("re-authenticates FIRST, then deletes the data, then the Auth user", async () => {
    const f = fakeAuth();
    await deleteAccount(f.handle, { user: true }, "u1", async () => void f.calls.push("deleteData"));
    expect(f.calls).toEqual(["reauth", "deleteData", "deleteUser"]);
  });
  it("when re-authentication fails nothing is deleted", async () => {
    const f = fakeAuth({ reauthenticateWithPopup: async () => { throw err("auth/popup-closed-by-user"); } });
    await expect(deleteAccount(f.handle, {}, "u1", async () => void f.calls.push("deleteData"))).rejects.toMatchObject({ code: "auth/popup-closed-by-user" });
    expect(f.calls).toEqual([]);
  });
  it("signing in with a different Google account during re-authentication deletes nothing", async () => {
    const f = fakeAuth({ reauthenticateWithPopup: async () => ({ user: { uid: "someone-else" } }) });
    const e = await deleteAccount(f.handle, {}, "u1", async () => void f.calls.push("deleteData")).catch((x) => x);
    expect(e.code).toBe("auth/user-mismatch");
    expect(describeAuthError(e)).toMatch(/different Google account/);
    expect(f.calls).toEqual([]);
  });
  it("if deleting the data fails the Auth user is kept (so the user can retry)", async () => {
    const f = fakeAuth();
    await expect(deleteAccount(f.handle, {}, "u1", async () => { throw new Error("offline"); })).rejects.toThrow("offline");
    expect(f.calls).toEqual(["reauth"]);
  });
});
