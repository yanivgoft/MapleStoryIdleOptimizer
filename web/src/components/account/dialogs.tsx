// The account dialogs (presentational: state and actions come in through props, so the render tests need no browser).
import { useId, useState, type FormEvent } from "react";
import { Modal } from "./Modal";
import { MAX_PROFILES, type HistoryEntry, type MigrationDecision, type SyncNotice } from "../../lib/cloud/merge";
import type { MigrationPrompt } from "../../lib/cloud/sync";

export const HELP_ACCOUNTS_ID = "help-accounts";
export const DELETE_PHRASE = "DELETE";

const fmtTime = (ms: number) => new Date(ms).toLocaleString();

// ---- privacy note (before the first sign-in) -------------------------------------------------------------------------------------------------------

export function PrivacyDialog({ onContinue, onCancel, onOpenHelp }: { onContinue: () => void; onCancel: () => void; onOpenHelp?: () => void }) {
  return (
    <Modal title="Before you sign in: what is stored" onClose={onCancel} initialFocusId="acct-privacy-continue">
      <ul className="acct-list">
        <li>
          <strong>What:</strong> the profiles you save (the stats, artifacts, companion levels and cube / equipment lines you typed), your theme and last-used class, and your Google account id and
          e-mail address (kept by Google sign-in). Your name and photo are shown here but are not stored by this app.
        </li>
        <li>
          <strong>Where:</strong> Google Firebase (Authentication and the Firestore database). Rules allow only your own signed-in account to read or write your documents. No analytics or advertising cookies
          are added.
        </li>
        <li>
          <strong>Your control:</strong> nothing is uploaded until you press <em>Save to account</em>. <em>Download all my data</em> and <em>Delete my account and data</em> are in the account menu.
        </li>
      </ul>
      <p className="note">
        Signed-out use is unchanged: without an account everything stays in this browser.{" "}
        {onOpenHelp && (
          <button type="button" className="linklike" onClick={onOpenHelp}>
            Full privacy policy: Help tab (Accounts and Privacy sections)
          </button>
        )}
      </p>
      <div className="acct-buttons">
        <button type="button" onClick={onCancel}>
          Cancel
        </button>
        <button type="button" id="acct-privacy-continue" className="primary" onClick={onContinue}>
          Continue with Google
        </button>
      </div>
    </Modal>
  );
}

// ---- first-login migration ---------------------------------------------------------------------------------------------------------------------

export function MigrationDialog({ prompt, cloudCount, onResolve, onClose }: { prompt: MigrationPrompt; cloudCount: number; onResolve: (d: MigrationDecision) => void; onClose: () => void }) {
  const id = useId();
  const [picked, setPicked] = useState<Record<string, boolean>>(() => Object.fromEntries(prompt.candidates.map((c) => [c.id, true])));
  const chosen = prompt.candidates.filter((c) => picked[c.id]).map((c) => c.id);
  const room = Math.max(0, MAX_PROFILES - cloudCount);
  const n = prompt.candidates.length;
  return (
    <Modal title={prompt.first ? `Upload your ${n} local profile${n === 1 ? "" : "s"}?` : `Upload ${n} local-only profile${n === 1 ? "" : "s"}?`} onClose={onClose} initialFocusId={`${id}-upload`}>
      <p>
        {prompt.first ? "This browser already holds profiles that are not in your account. " : "These profiles were kept on this device only. "}
        Uploading copies them to your account the next time you press <em>Save to account</em> (it happens right away from this dialog); nothing on this device is changed.
      </p>
      <fieldset className="acct-picks">
        <legend>Profiles to upload</legend>
        {prompt.candidates.map((c) => (
          <div key={c.id} className="acct-pick">
            <input id={`${id}-${c.id}`} type="checkbox" checked={!!picked[c.id]} onChange={(e) => setPicked({ ...picked, [c.id]: e.target.checked })} />
            <label htmlFor={`${id}-${c.id}`}>
              {c.name} <span className="meta">({c.classId}, {fmtTime(c.updatedAt)})</span>
            </label>
          </div>
        ))}
      </fieldset>
      {chosen.length > room && (
        <p className="error" role="alert">
          An account holds at most {MAX_PROFILES} profiles ({cloudCount} already in it): only {room} more can be saved. Choose fewer, or delete some later.
        </p>
      )}
      <div className="acct-buttons">
        <button type="button" onClick={() => onResolve({ kind: "none" })}>
          Not now (keep local only)
        </button>
        <button type="button" id={`${id}-upload`} className="primary" disabled={chosen.length === 0} onClick={() => onResolve(chosen.length === n ? { kind: "all" } : { kind: "choose", ids: chosen })}>
          {chosen.length === n ? `Upload all ${n}` : `Upload ${chosen.length} selected`}
        </button>
      </div>
    </Modal>
  );
}

// ---- sign out ----------------------------------------------------------------------------------------------------------------------------------------

export function SignOutDialog({
  dirtyCount,
  busy,
  onSignOut,
  onSaveThenSignOut,
  onCancel,
}: {
  dirtyCount: number;
  busy?: boolean;
  onSignOut: (clearLocal: boolean) => void;
  onSaveThenSignOut: () => void;
  onCancel: () => void;
}) {
  return (
    <Modal title="Sign out" onClose={onCancel} initialFocusId={dirtyCount ? "acct-signout-save" : "acct-signout-keep"}>
      {dirtyCount > 0 && (
        <p className="error" role="alert">
          {dirtyCount} profile{dirtyCount === 1 ? " has" : "s have"} unsaved changes that are not in your account.
        </p>
      )}
      <p>What should happen to the profiles stored in this browser?</p>
      <div className="acct-buttons stack">
        {dirtyCount > 0 && (
          <button type="button" id="acct-signout-save" className="primary" disabled={busy} onClick={onSaveThenSignOut}>
            Save to account, then sign out
          </button>
        )}
        <button type="button" id="acct-signout-keep" className={dirtyCount ? undefined : "primary"} disabled={busy} onClick={() => onSignOut(false)}>
          Sign out and keep the profiles on this device
        </button>
        <button type="button" className="danger" disabled={busy} onClick={() => onSignOut(true)}>
          Sign out and clear this browser's profiles
        </button>
        <button type="button" onClick={onCancel}>
          Cancel
        </button>
      </div>
      <p className="note">Clearing only removes this browser's copies; whatever you saved to your account stays there.</p>
    </Modal>
  );
}

// ---- delete account ----------------------------------------------------------------------------------------------------------------------------

export function DeleteDialog({ email, busy, error, onDelete, onCancel }: { email: string | null; busy?: boolean; error?: string | null; onDelete: () => void; onCancel: () => void }) {
  const id = useId();
  const [typed, setTyped] = useState("");
  const ok = typed.trim() === DELETE_PHRASE;
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (ok && !busy) onDelete();
  };
  return (
    <Modal title="Delete my account and data" role="alertdialog" onClose={onCancel} initialFocusId={`${id}-phrase`}>
      <form onSubmit={submit}>
        <p>
          This permanently deletes everything stored for {email ? <strong>{email}</strong> : "this account"} in the cloud: all saved profiles, your settings and the sign-in account itself. It cannot be
          undone. Profiles that are on this device stay here as normal local profiles.
        </p>
        <p className="note">You will be asked to sign in with Google once more to confirm. Download your data first if you want a copy.</p>
        <div className="acct-field">
          <label htmlFor={`${id}-phrase`}>
            Type <code>{DELETE_PHRASE}</code> to confirm
          </label>
          <input id={`${id}-phrase`} type="text" value={typed} autoComplete="off" spellCheck={false} onChange={(e) => setTyped(e.target.value)} aria-invalid={typed !== "" && !ok} />
        </div>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <div className="acct-buttons">
          <button type="button" onClick={onCancel} disabled={busy}>
            Cancel
          </button>
          <button type="submit" className="danger" disabled={!ok || busy}>
            {busy ? "Deleting..." : "Delete my account and data"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

// ---- history (losing versions) -----------------------------------------------------------------------------------------------------------------

const REASON_TEXT: Record<HistoryEntry["reason"], string> = {
  "replaced-by-cloud": "replaced by the newer version from your account",
  "replaced-by-local": "the account's version, replaced by your newer one here",
  "deleted-elsewhere": "deleted on another device",
};

export function HistoryDialog({ history, onRestore, onDiscard, onClose }: { history: HistoryEntry[]; onRestore: (key: string) => void; onDiscard: (key: string) => void; onClose: () => void }) {
  return (
    <Modal title="Version history" onClose={onClose}>
      <p className="note">When a profile was edited on two devices, the version that lost is kept here (on this device only). Restore puts it back as a new profile.</p>
      {history.length === 0 ? (
        <p className="empty">Nothing here.</p>
      ) : (
        <ul className="acct-history">
          {history.map((h) => (
            <li key={h.key}>
              <div>
                <strong>{h.name}</strong> <span className="meta">version of {fmtTime(h.versionUpdatedAt)} - {REASON_TEXT[h.reason]}</span>
              </div>
              <div className="actions">
                <button type="button" onClick={() => onRestore(h.key)}>
                  Restore as new profile
                </button>
                <button type="button" onClick={() => onDiscard(h.key)}>
                  Discard
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
      <div className="acct-buttons">
        <button type="button" className="primary" onClick={onClose}>
          Close
        </button>
      </div>
    </Modal>
  );
}

// ---- notices (conflicts / updated from another device) -------------------------------------------------------------------------------------------------

export function Notices({ notices, onDismiss, onOpenHistory }: { notices: SyncNotice[]; onDismiss: (id: string) => void; onOpenHistory: () => void }) {
  return (
    <div className="acct-notices" role="status" aria-live="polite">
      {notices.map((n) => (
        <div key={n.id} className={`acct-notice ${n.kind}`}>
          <span>{n.message}</span>
          <span className="actions">
            {(n.kind === "conflict" || n.kind === "deleted") && (
              <button type="button" onClick={onOpenHistory}>
                View history
              </button>
            )}
            <button type="button" aria-label={`Dismiss: ${n.message}`} onClick={() => onDismiss(n.id)}>
              Dismiss
            </button>
          </span>
        </div>
      ))}
    </div>
  );
}
