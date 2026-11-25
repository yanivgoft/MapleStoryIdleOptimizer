// Header controls of the account feature (presentational): the "Sign in with Google" button and the avatar menu.
import { useEffect, useId, useRef, type KeyboardEvent, type ReactNode } from "react";
import type { AccountState } from "../../lib/cloud/sync";

/** The one-line sync status shown in the menu (and read out by screen readers). */
export function syncStatusText(s: Pick<AccountState, "phase" | "error" | "dirtyCount" | "lastSyncAt" | "settingsDirty" | "migration">): string {
  if (s.phase === "loading") return "Loading your account...";
  if (s.phase === "saving") return "Saving...";
  if (s.phase === "error") return s.error ?? "Something went wrong.";
  if (s.migration?.first) return "Choose which local profiles to upload.";
  if (s.dirtyCount > 0) return `${s.dirtyCount} unsaved profile${s.dirtyCount === 1 ? "" : "s"}`;
  if (s.settingsDirty) return "Settings changed (saved with your next Save)";
  if (s.lastSyncAt) return `All changes saved (${new Date(s.lastSyncAt).toLocaleTimeString()})`;
  return "Signed in - profiles are saved only when you press Save to account";
}

export function SignInButtonView({ busy, onClick, onPrefetch }: { busy?: boolean; onClick: () => void; onPrefetch?: () => void }) {
  return (
    <button type="button" className="acct-signin" disabled={busy} onClick={onClick} onPointerEnter={onPrefetch} onFocus={onPrefetch} onTouchStart={onPrefetch}>
      <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M20 12H11M16 8l4 4-4 4" />
        <path d="M11 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h5" />
      </svg>
      <span>{busy ? "Signing in..." : "Sign in with Google"}</span>
    </button>
  );
}

function Avatar({ name, photoURL }: { name: string; photoURL: string | null }) {
  if (photoURL) return <img className="acct-avatar" src={photoURL} alt="" width={24} height={24} referrerPolicy="no-referrer" />;
  return (
    <span className="acct-avatar initial" aria-hidden="true">
      {(name.trim()[0] ?? "?").toUpperCase()}
    </span>
  );
}

export interface AccountMenuProps {
  state: AccountState;
  open: boolean;
  onToggle: () => void;
  onClose: () => void;
  onSave: () => void;
  onRefresh: () => void;
  onUploadLocal: () => void;
  onHistory: () => void;
  onExport: () => void;
  onDelete: () => void;
  onSignOut: () => void;
}

export function AccountMenuView(p: AccountMenuProps) {
  const { state, open } = p;
  const user = state.user;
  const menuId = useId();
  const wrap = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const busy = state.phase === "loading" || state.phase === "saving";
  const canSave = !busy && !state.migration?.first && (state.dirtyCount > 0 || state.settingsDirty);

  // close on a click outside; focus the first item when opened
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (wrap.current && !wrap.current.contains(e.target as Node)) p.onClose();
    };
    document.addEventListener("mousedown", onDown);
    wrap.current?.querySelector<HTMLElement>('[role="menuitem"]:not([disabled])')?.focus();
    return () => document.removeEventListener("mousedown", onDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const onKey = (e: KeyboardEvent) => {
    if (!open) return;
    const items = Array.from(wrap.current?.querySelectorAll<HTMLElement>('[role="menuitem"]:not([disabled])') ?? []);
    const i = items.indexOf(document.activeElement as HTMLElement);
    const go = (n: number) => {
      e.preventDefault();
      items[(n + items.length) % items.length]?.focus();
    };
    if (e.key === "ArrowDown") go(i + 1);
    else if (e.key === "ArrowUp") go(i < 0 ? items.length - 1 : i - 1);
    else if (e.key === "Home") go(0);
    else if (e.key === "End") go(items.length - 1);
    else if (e.key === "Escape") {
      e.preventDefault();
      p.onClose();
      trigger.current?.focus();
    } else if (e.key === "Tab") p.onClose();
  };

  if (!user) return null;
  const label = user.displayName || user.email || "Account";
  const item = (text: ReactNode, onClick: () => void, opts: { disabled?: boolean; primary?: boolean; danger?: boolean; hint?: string } = {}) => (
    <button
      type="button"
      role="menuitem"
      className={`acct-item${opts.primary ? " primary" : ""}${opts.danger ? " danger" : ""}`}
      disabled={opts.disabled}
      title={opts.hint}
      onClick={() => {
        p.onClose();
        onClick();
      }}
    >
      {text}
    </button>
  );

  return (
    <div className="acct-menu-wrap" ref={wrap} onKeyDown={onKey}>
      <button
        ref={trigger}
        type="button"
        className="acct-trigger"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        aria-label={`Account menu for ${label}${state.dirtyCount > 0 ? `, ${state.dirtyCount} unsaved` : ""}`}
        title={syncStatusText(state)}
        onClick={p.onToggle}
      >
        <Avatar name={label} photoURL={user.photoURL} />
        {state.dirtyCount > 0 && <span className="acct-dot" data-testid="unsaved-dot" aria-hidden="true" />}
        {state.phase === "error" && <span className="acct-dot error" aria-hidden="true" />}
      </button>
      {open && (
        <div id={menuId} className="acct-menu" role="menu" aria-label="Account">
          <div className="acct-menu-head" role="none">
            <strong>{user.email ?? label}</strong>
            <span className={`acct-status ${state.phase === "error" ? "error" : state.dirtyCount > 0 ? "dirty" : ""}`} role="status">
              {syncStatusText(state)}
            </span>
          </div>
          {item(`Save to account${state.dirtyCount > 0 ? ` (${state.dirtyCount} unsaved)` : ""}`, p.onSave, { primary: true, disabled: !canSave, hint: canSave ? "Writes the profiles that changed since the last save" : "Nothing to save" })}
          {item("Refresh from account", p.onRefresh, { disabled: busy, hint: "Reads your account again and merges it with this device" })}
          {state.skippedCount > 0 && item(`Upload local-only profiles (${state.skippedCount})...`, p.onUploadLocal)}
          {(state.history.length > 0 || state.notices.some((n) => n.kind === "conflict")) && item(`Version history (${state.history.length})...`, p.onHistory, { hint: "Versions of a profile that lost when two devices edited it: restore one as a new profile" })}
          {item("Download all my data (JSON)", p.onExport, { disabled: busy })}
          {item("Delete my account and data...", p.onDelete, { danger: true })}
          {item("Sign out...", p.onSignOut)}
        </div>
      )}
    </div>
  );
}
