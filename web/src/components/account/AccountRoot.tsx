// The account feature as the App sees it: ONE lazy-loaded component (the App only imports it when the Firebase config is set, see lib/cloud/config.ts), rendered
// inside the header.  It owns the controller, connects it to Firebase Auth (the SDK itself is loaded lazily by lib/cloud/firebase.ts), shows the sign-in button /
// avatar menu / dialogs / notices, warns before the tab is closed with unsaved changes, and publishes the per-profile status to the Profiles tab (bridge).
import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import "./account.css";
import type { ClassInfo } from "../../types";
import { cloudConfig } from "../../lib/cloud/config";
import { AccountController } from "../../lib/cloud/sync";
import { browserDeps, hasSessionFlag, markPrivacySeen, privacySeen, setSessionFlag } from "../../lib/cloud/localPorts";
import { loadFirebase, type FirebaseHandle } from "../../lib/cloud/firebase";
import { deleteAccount, describeAuthError, finishRedirect, signInWithGoogle, signOutUser, subscribeAuth } from "../../lib/cloud/auth";
import { createFirestoreDb } from "../../lib/cloud/firestoreDb";
import { describeCloudError } from "../../lib/cloud/store";
import { getLastProfile, publishCloud } from "../../lib/cloud/bridge";
import { AccountMenuView, SignInButtonView } from "./AccountMenu";
import { DeleteDialog, HELP_ACCOUNTS_ID, HistoryDialog, MigrationDialog, Notices, PrivacyDialog, SignOutDialog } from "./dialogs";

export interface AccountRootProps {
  classId: string | null;
  classes: ClassInfo[];
  /** The account's settings name a last-used class: switch to it. */
  onApplyClass: (classId: string) => void;
  /** Open the Help tab at a section. */
  onOpenHelp: (sectionId: string) => void;
}

// one controller per page; the callbacks it needs are read through `live` so that they always see the latest props
const live: { classId: string | null; classes: ClassInfo[]; onApplyClass: (id: string) => void } = { classId: null, classes: [], onApplyClass: () => undefined };
let controller: AccountController | null = null;
function getController(): AccountController {
  controller ??= new AccountController(
    browserDeps(
      () => ({ lastClassId: live.classId ?? undefined, lastProfileId: getLastProfile() }),
      (s) => {
        if (s.lastClassId && s.lastClassId !== live.classId && live.classes.some((c) => c.id === s.lastClassId)) live.onApplyClass(s.lastClassId);
      },
    ),
  );
  return controller;
}

type Dialog = null | "privacy" | "signout" | "delete" | "history";

function download(data: unknown, file: string) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = file;
  a.click();
  URL.revokeObjectURL(url);
}

export default function AccountRoot({ classId, classes, onApplyClass, onOpenHelp }: AccountRootProps) {
  const c = getController();
  live.classId = classId;
  live.classes = classes;
  live.onApplyClass = onApplyClass;
  const state = useSyncExternalStore(c.subscribe, c.getState, c.getState);

  const [menuOpen, setMenuOpen] = useState(false);
  const [dialog, setDialog] = useState<Dialog>(null);
  const [signingIn, setSigningIn] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [working, setWorking] = useState(false); // sign-out / delete in progress
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const handle = useRef<FirebaseHandle | null>(null);
  const connecting = useRef<Promise<FirebaseHandle> | null>(null);
  const signingRef = useRef(false);
  const retrySave = useRef(false);

  // the Settings the account stores follow the selected class
  useEffect(() => c.touch(), [c, classId]);

  const connect = useCallback((): Promise<FirebaseHandle> => {
    connecting.current ??= (async () => {
      const cfg = cloudConfig();
      if (!cfg) throw new Error("Accounts are not configured for this build.");
      const h = await loadFirebase(cfg);
      handle.current = h;
      void finishRedirect(h).then((err) => err && setAuthError(describeAuthError(err)));
      subscribeAuth(
        h,
        (user) => {
          if (user) {
            setSessionFlag(true);
            if (c.getState().user?.uid === user.uid) return; // already signed in here (the listener can fire twice around a redirect)
            void c.signedIn(user, createFirestoreDb(h.fsSdk, h.db));
          } else {
            if (!signingRef.current) setSessionFlag(false);
            if (c.getState().user) c.leave(false);
          }
        },
        (e) => setAuthError(describeAuthError(e)),
      );
      return h;
    })().catch((e) => {
      connecting.current = null;
      throw e;
    });
    return connecting.current;
  }, [c]);

  // a Google session from an earlier visit: restore it (this is the only case where the SDK is loaded without a click)
  useEffect(() => {
    if (hasSessionFlag()) void connect().catch((e) => setAuthError(describeAuthError(e)));
  }, [connect]);

  const prefetch = useCallback(() => void connect().catch(() => undefined), [connect]);

  const doSignIn = useCallback(async () => {
    setAuthError(null);
    setSigningIn(true);
    signingRef.current = true;
    try {
      const h = await connect();
      setSessionFlag(true);
      const outcome = await signInWithGoogle(h);
      if (outcome === "cancelled") setSessionFlag(false);
    } catch (e) {
      setSessionFlag(false);
      setAuthError(describeAuthError(e));
    } finally {
      signingRef.current = false;
      setSigningIn(false);
    }
  }, [connect]);

  const onSignInClick = () => {
    if (privacySeen()) void doSignIn();
    else setDialog("privacy");
  };

  const say = (text: string) => {
    setMessage(text);
    window.setTimeout(() => setMessage((m) => (m === text ? null : m)), 6000);
  };

  const save = useCallback(async () => {
    const r = await c.save();
    if (r.skipped === "migration") say("Choose which local profiles to upload first.");
    else if (r.skipped === "nothing") say("Nothing to save: everything is already in your account.");
    else if (!r.ok) {
      retrySave.current = true;
      say(r.error ?? "Saving failed.");
    } else {
      retrySave.current = false;
      const bits = [`Saved ${r.written} profile${r.written === 1 ? "" : "s"}`];
      if (r.deleted) bits.push(`deleted ${r.deleted}`);
      if (r.rejected.length) bits.push(`${r.rejected.length} could not be saved (see the Profiles tab)`);
      say(bits.join(", ") + ".");
    }
    return r;
  }, [c]);

  // unsaved changes: warn before the tab is closed; a failed save is retried once when the connection is back
  useEffect(() => {
    if (!state.user || state.dirtyCount === 0) return;
    const onBefore = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", onBefore);
    return () => window.removeEventListener("beforeunload", onBefore);
  }, [state.user, state.dirtyCount]);
  useEffect(() => {
    const onOnline = () => {
      if (retrySave.current && c.getState().user) {
        retrySave.current = false;
        void save();
      }
    };
    window.addEventListener("online", onOnline);
    return () => window.removeEventListener("online", onOnline);
  }, [c, save]);

  // per-profile status for the Profiles tab
  const refresh = useCallback(() => void c.refresh(), [c]);
  useEffect(() => {
    publishCloud({ signedIn: !!state.user, busy: state.phase === "loading" || state.phase === "saving", dirtyCount: state.dirtyCount, statuses: state.user ? state.statuses : {}, errors: state.user ? state.profileErrors : {}, save: () => void save(), refresh });
  }, [state.user, state.phase, state.dirtyCount, state.statuses, state.profileErrors, save, refresh]);
  useEffect(() => () => publishCloud(null), []);

  const signOut = async (clearLocal: boolean) => {
    setWorking(true);
    try {
      c.leave(clearLocal);
      setSessionFlag(false);
      if (handle.current) await signOutUser(handle.current);
    } catch (e) {
      setAuthError(describeAuthError(e));
    } finally {
      setWorking(false);
      setDialog(null);
    }
  };
  const saveThenSignOut = async () => {
    setWorking(true);
    const r = await save();
    setWorking(false);
    if (r.ok || r.skipped === "nothing") await signOut(false);
  };

  const exportData = async () => {
    try {
      download(await c.exportAll(), "msi-account-data.json");
      say("Your data was downloaded.");
    } catch (e) {
      say(describeCloudError(e).message);
    }
  };

  const doDelete = async () => {
    const h = handle.current;
    const user = state.user;
    if (!h || !user) return;
    setWorking(true);
    setDeleteError(null);
    try {
      await deleteAccount(h, (h.auth as { currentUser?: unknown }).currentUser, user.uid, async () => void (await c.deleteCloudData()));
      c.accountDeleted();
      setSessionFlag(false);
      setDialog(null);
      say("Your account and its data were deleted. Profiles on this device are still here.");
    } catch (e) {
      const code = String((e as { code?: unknown })?.code ?? "");
      setDeleteError(code.startsWith("auth/") ? describeAuthError(e) : describeCloudError(e).message);
    } finally {
      setWorking(false);
    }
  };

  const toggleMenu = () => setMenuOpen((o) => !o);
  const openHelp = () => {
    setDialog(null);
    onOpenHelp(HELP_ACCOUNTS_ID);
  };

  return (
    <div className="acct-root">
      {!state.user && <SignInButtonView busy={signingIn} onClick={onSignInClick} onPrefetch={prefetch} />}
      {state.user && (
        <AccountMenuView
          state={state}
          open={menuOpen}
          onToggle={toggleMenu}
          onClose={() => setMenuOpen(false)}
          onSave={() => void save()}
          onRefresh={refresh}
          onUploadLocal={() => c.openMigration()}
          onHistory={() => setDialog("history")}
          onExport={() => void exportData()}
          onDelete={() => {
            setDeleteError(null);
            setDialog("delete");
          }}
          onSignOut={() => setDialog("signout")}
        />
      )}
      {authError && (
        <span className="error acct-err" role="alert">
          {authError}
        </span>
      )}
      {message && (
        <span className="acct-toast" role="status">
          {message}
        </span>
      )}
      {state.notices.length > 0 && <Notices notices={state.notices} onDismiss={(id) => c.dismissNotice(id)} onOpenHistory={() => setDialog("history")} />}

      {dialog === "privacy" && (
        <PrivacyDialog
          onCancel={() => setDialog(null)}
          onContinue={() => {
            markPrivacySeen();
            setDialog(null);
            void doSignIn();
          }}
          onOpenHelp={openHelp}
        />
      )}
      {state.migration && (
        <MigrationDialog
          prompt={state.migration}
          cloudCount={state.cloudCount}
          onClose={() => c.dismissMigration()}
          onResolve={(d) => {
            c.resolveMigration(d);
            if (d.kind !== "none") void save();
          }}
        />
      )}
      {dialog === "signout" && state.user && <SignOutDialog dirtyCount={state.dirtyCount} busy={working} onSignOut={(clear) => void signOut(clear)} onSaveThenSignOut={() => void saveThenSignOut()} onCancel={() => setDialog(null)} />}
      {dialog === "delete" && state.user && <DeleteDialog email={state.user.email} busy={working} error={deleteError} onDelete={() => void doDelete()} onCancel={() => setDialog(null)} />}
      {dialog === "history" && <HistoryDialog history={state.history} onRestore={(k) => c.restoreHistory(k)} onDiscard={(k) => c.discardHistory(k)} onClose={() => setDialog(null)} />}
    </div>
  );
}
