import { afterEach, describe, expect, it } from "vitest";
import { renderToString } from "react-dom/server";
import { AccountMenuView, SignInButtonView, syncStatusText, type AccountMenuProps } from "./AccountMenu";
import { DELETE_PHRASE, DeleteDialog, HistoryDialog, MigrationDialog, Notices, PrivacyDialog, SignOutDialog } from "./dialogs";
import { CLOUD_STATUS_TEXT, CloudStatusIcon } from "../CloudStatusIcon";
import { ProfilesPanel } from "../ProfilesPanel";
import { publishCloud } from "../../lib/cloud/bridge";
import { ACCOUNTS } from "../../content/help";
import type { AccountState } from "../../lib/cloud/sync";
import type { HistoryEntry, ProfileSyncStatus, SyncNotice } from "../../lib/cloud/merge";
import { classList } from "../../test/fixtures";
import { initialState } from "../../lib/schemaForm";
import { fixtureFor } from "../../test/fixtures";

const strip = (h: string) => h.replace(/<!-- -->/g, "").replace(/&#x27;/g, "'").replace(/&quot;/g, '"');
const user = { uid: "u1", email: "me@example.com", displayName: "Me Myself", photoURL: null };
const base: AccountState = {
  phase: "ready",
  user,
  error: null,
  profileErrors: {},
  statuses: {},
  dirtyCount: 0,
  settingsDirty: false,
  skippedCount: 0,
  cloudCount: 2,
  cloudOnly: [],
  lastSyncAt: 1_800_000_000_000,
  notices: [],
  history: [],
  migration: null,
};
const noop = () => undefined;
const menuProps = (state: AccountState, open = true): AccountMenuProps => ({ state, open, onToggle: noop, onClose: noop, onSave: noop, onRefresh: noop, onUploadLocal: noop, onHistory: noop, onExport: noop, onDelete: noop, onSignOut: noop });
const menu = (state: AccountState, open = true) => strip(renderToString(<AccountMenuView {...menuProps(state, open)} />));

describe("sign-in button (signed out)", () => {
  it("is a labelled button", () => {
    const html = strip(renderToString(<SignInButtonView onClick={noop} />));
    expect(html).toContain("Sign in with Google");
    expect(html).toContain('type="button"');
    expect(html).not.toContain("disabled");
  });
  it("is disabled while signing in", () => {
    const html = strip(renderToString(<SignInButtonView busy onClick={noop} />));
    expect(html).toContain("Signing in...");
    expect(html).toContain("disabled");
  });
});

describe("account menu (signed in)", () => {
  it("closed: an avatar button with the menu semantics and no dot when everything is saved", () => {
    const html = menu(base, false);
    expect(html).toContain('aria-haspopup="menu"');
    expect(html).toContain('aria-expanded="false"');
    expect(html).toContain("Account menu for Me Myself");
    expect(html).not.toContain("unsaved-dot");
    expect(html).not.toContain('role="menu"');
    expect(html).toContain(">M<"); // initial when there is no photo
  });
  it("open: a role=menu with the e-mail, the status and every action", () => {
    const html = menu({ ...base, dirtyCount: 3, statuses: { a: "unsaved" } });
    expect(html).toContain('role="menu"');
    expect(html).toContain('aria-expanded="true"');
    expect(html).toContain("me@example.com");
    expect(html).toContain("3 unsaved profiles");
    for (const t of ["Save to account (3 unsaved)", "Refresh from account", "Download all my data (JSON)", "Delete my account and data...", "Sign out..."]) expect(html, t).toContain(t);
    expect((html.match(/role="menuitem"/g) ?? []).length).toBe(5);
  });
  it("dirty: the unsaved dot and the count are announced on the trigger; Save is enabled", () => {
    const html = menu({ ...base, dirtyCount: 1 }, false);
    expect(html).toContain("unsaved-dot");
    expect(html).toContain(", 1 unsaved");
    const open = menu({ ...base, dirtyCount: 1 });
    expect(open).not.toMatch(/<button[^>]*role="menuitem"[^>]*disabled=""[^>]*>Save to account/);
  });
  it("nothing to save: Save is disabled with a hint", () => {
    const html = menu(base);
    expect(html).toMatch(/disabled=""[^>]*>Save to account|Save to account<\/button>/);
    expect(html).toContain("All changes saved");
    expect(html).toContain("Nothing to save");
  });
  it("only a settings change: Save is enabled but there is no unsaved dot", () => {
    const html = menu({ ...base, settingsDirty: true });
    expect(html).toContain("Settings changed");
    expect(html).not.toContain("unsaved-dot");
    expect(html).not.toContain("Nothing to save");
  });
  it("error: the message is in the status line and an error dot shows", () => {
    const html = menu({ ...base, phase: "error", error: "Could not reach your account (offline).", dirtyCount: 2 });
    expect(html).toContain("Could not reach your account (offline).");
    expect(html).toContain("acct-dot error");
    expect(html).toContain("acct-status error");
  });
  it("loading / saving states disable Save and Refresh", () => {
    expect(menu({ ...base, phase: "saving", dirtyCount: 1 })).toContain("Saving...");
    const loading = menu({ ...base, phase: "loading" });
    expect(loading).toContain("Loading your account...");
    expect((loading.match(/disabled=""/g) ?? []).length).toBeGreaterThanOrEqual(3);
  });
  it("shows the optional entries only when relevant", () => {
    const plain = menu(base);
    expect(plain).not.toContain("Upload local-only");
    expect(plain).not.toContain("Version history");
    const html = menu({ ...base, skippedCount: 2, history: [{ key: "k" } as HistoryEntry] });
    expect(html).toContain("Upload local-only profiles (2)...");
    expect(html).toContain("Version history (1)...");
  });
  it("renders nothing without a user", () => {
    expect(menu({ ...base, user: null })).toBe("");
  });
  it("status text for each situation", () => {
    expect(syncStatusText({ ...base, migration: { first: true, candidates: [] } })).toMatch(/Choose which local profiles/);
    expect(syncStatusText({ ...base, lastSyncAt: null })).toBe("Signed in");
    expect(syncStatusText({ ...base, dirtyCount: 1 })).toBe("1 unsaved profile");
  });
});

describe("dialogs", () => {
  it("privacy note: what, where, control, deletion, a link to the Help section; focus lands on Continue", () => {
    const html = strip(renderToString(<PrivacyDialog onContinue={noop} onCancel={noop} onOpenHelp={noop} />));
    expect(html).toContain('role="dialog"');
    expect(html).toContain('aria-modal="true"');
    expect(html).toMatch(/aria-labelledby="[^"]+"/);
    for (const t of ["What:", "Where:", "Firestore", "Google account id and e-mail", "Save to account", "Download all my data", "Delete my account and data", "Help tab (Accounts)", "Continue with Google"]) expect(html, t).toContain(t);
    expect(html).toContain('id="acct-privacy-continue"');
  });
  const cands = [
    { id: "a", name: "Main", classId: "fp_mage", updatedAt: 1_700_000_000_000 },
    { id: "b", name: "Alt", classId: "hero", updatedAt: 1_700_000_000_000 },
  ];
  it("first-login migration: asks about N profiles with a checkbox each and the three answers", () => {
    const html = strip(renderToString(<MigrationDialog prompt={{ first: true, candidates: cands }} cloudCount={0} onResolve={noop} onClose={noop} />));
    expect(html).toContain("Upload your 2 local profiles?");
    expect((html.match(/type="checkbox"/g) ?? []).length).toBe(2);
    expect(html).toContain("Main");
    expect(html).toContain("Alt");
    expect(html).toContain("Upload all 2");
    expect(html).toContain("Not now (keep local only)");
    expect(html).not.toContain('role="alert"');
  });
  it("migration warns when the 50-profile cap would be exceeded", () => {
    const html = strip(renderToString(<MigrationDialog prompt={{ first: true, candidates: cands }} cloudCount={49} onResolve={noop} onClose={noop} />));
    expect(html).toContain('role="alert"');
    expect(html).toContain("at most 50 profiles");
    expect(html).toContain("only 1 more");
  });
  it("sign-out: keep / clear choice; unsaved changes are called out with a save-first button", () => {
    const clean = strip(renderToString(<SignOutDialog dirtyCount={0} onSignOut={noop} onSaveThenSignOut={noop} onCancel={noop} />));
    expect(clean).toContain("Sign out and keep the profiles on this device");
    expect(clean).toContain("Sign out and clear this browser&#x27;s profiles".replace("&#x27;", "'"));
    expect(clean).not.toContain("Save to account, then sign out");
    const dirty = strip(renderToString(<SignOutDialog dirtyCount={2} onSignOut={noop} onSaveThenSignOut={noop} onCancel={noop} />));
    expect(dirty).toContain("2 profiles have unsaved changes");
    expect(dirty).toContain("Save to account, then sign out");
  });
  it("delete account: alertdialog, typed confirmation required (submit disabled), explains what happens, shows errors", () => {
    const html = strip(renderToString(<DeleteDialog email="me@example.com" onDelete={noop} onCancel={noop} error="Sign in again." />));
    expect(html).toContain('role="alertdialog"');
    expect(html).toContain(`<code>${DELETE_PHRASE}</code>`);
    expect(html).toContain("me@example.com");
    expect(html).toContain("sign in with Google once more");
    expect(html).toMatch(/<button type="submit"[^>]*disabled=""/);
    expect(html).toContain("Sign in again.");
    expect(strip(renderToString(<DeleteDialog email={null} busy onDelete={noop} onCancel={noop} />))).toContain("Deleting...");
  });
  it("history: lists the losing versions with restore / discard", () => {
    const h: HistoryEntry = { key: "k1", profileId: "a", name: "Main", classId: "fp_mage", state: "{}", versionUpdatedAt: 1_700_000_000_000, at: 2, reason: "replaced-by-cloud" };
    const html = strip(renderToString(<HistoryDialog history={[h]} onRestore={noop} onDiscard={noop} onClose={noop} />));
    expect(html).toContain("Version history");
    expect(html).toContain("Main");
    expect(html).toContain("replaced by the newer version from your account");
    expect(html).toContain("Restore as new profile");
    expect(html).toContain("Discard");
    expect(strip(renderToString(<HistoryDialog history={[]} onRestore={noop} onDiscard={noop} onClose={noop} />))).toContain("Nothing here.");
  });
  it("notices: a polite live region; conflicts offer the history", () => {
    const n: SyncNotice[] = [
      { id: "1", kind: "conflict", profileId: "a", name: "Main", message: '"Main" was edited on two devices.' },
      { id: "2", kind: "updated", profileId: "b", name: "Alt", message: '"Alt" was updated from another device.' },
    ];
    const html = strip(renderToString(<Notices notices={n} onDismiss={noop} onOpenHistory={noop} />));
    expect(html).toContain('aria-live="polite"');
    expect(html).toContain("updated from another device");
    expect((html.match(/View history/g) ?? []).length).toBe(1);
    expect((html.match(/>Dismiss</g) ?? []).length).toBe(2);
  });
});

describe("per-profile cloud icon", () => {
  it.each(Object.keys(CLOUD_STATUS_TEXT) as ProfileSyncStatus[])("%s has a role=img, a label and a title", (s) => {
    const html = strip(renderToString(<CloudStatusIcon status={s} />));
    expect(html).toContain('role="img"');
    expect(html).toContain(`aria-label="${CLOUD_STATUS_TEXT[s]}"`);
    expect(html).toContain(`title="${CLOUD_STATUS_TEXT[s]}"`);
    expect(html).toContain(`data-status="${s}"`);
  });
});

describe("Profiles tab with accounts", () => {
  const fp = fixtureFor("fp_mage");
  const state = initialState(fp.schema, fp.defaults["World Boss"], "World Boss");
  const html = () => strip(renderToString(<ProfilesPanel state={state} classes={classList} onLoad={noop} />));
  afterEach(() => publishCloud(null));
  it("accounts off: exactly the old wording and no cloud controls", () => {
    const h = html();
    expect(h).toContain("Profiles live only in this browser (localStorage). Export a file to back them up or move them to another device.");
    expect(h).not.toContain("cloud-bar");
    expect(h).not.toContain("cloud-status");
  });
  it("signed out with accounts on: points to the sign-in", () => {
    publishCloud({ signedIn: false, busy: false, dirtyCount: 0, statuses: {}, errors: {}, save: noop, refresh: noop });
    const h = html();
    expect(h).toContain("sign in (header) to keep them in your account");
    expect(h).not.toContain("cloud-bar");
  });
  it("signed in: Save / Refresh buttons with the unsaved count", () => {
    publishCloud({ signedIn: true, busy: false, dirtyCount: 2, statuses: {}, errors: {}, save: noop, refresh: noop });
    const h = html();
    expect(h).toContain("Save to account (2 unsaved)");
    expect(h).toContain("Refresh from account");
    expect(h).not.toMatch(/<button[^>]*disabled=""[^>]*>Save to account/);
    publishCloud({ signedIn: true, busy: false, dirtyCount: 0, statuses: {}, errors: {}, save: noop, refresh: noop });
    expect(html()).toMatch(/<button[^>]*disabled=""[^>]*>Save to account<\/button>/);
  });
});

describe("Help: Accounts section", () => {
  const text = strip(renderToString(<div>{ACCOUNTS.body}</div>));
  it("covers what is saved, the Save button, conflicts, limits, privacy, export and deletion", () => {
    expect(ACCOUNTS.id).toBe("help-accounts");
    for (const t of ["Save to account", "Refresh from account", "newest edit wins", "Version history", "up to 50 profiles", "180 KB", "Download all my data", "Delete my account and data", "type DELETE", "Sign out", "Firestore", "30 days"]) expect(text, t).toContain(t);
  });
});

describe("AccountRoot (container)", () => {
  it("signed out: renders the sign-in button and nothing else (no SDK is touched while rendering)", async () => {
    const { default: AccountRoot } = await import("./AccountRoot");
    const html = strip(renderToString(<AccountRoot classId="fp_mage" classes={classList} onApplyClass={noop} onOpenHelp={noop} />));
    expect(html).toContain("Sign in with Google");
    expect(html).not.toContain("role=\"dialog\"");
    expect(html).not.toContain("acct-menu");
  });
});
