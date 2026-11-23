// Per-profile cloud icon of the Profiles tab (synced / unsaved / local only / cloud only / error).  Always loaded (tiny); only rendered when accounts are on.
import type { ProfileSyncStatus } from "../lib/cloud/merge";

export const CLOUD_STATUS_TEXT: Record<ProfileSyncStatus, string> = {
  synced: "Saved to your account",
  unsaved: "Unsaved changes: not in your account yet (press Save to account)",
  "local-only": "On this device only (not uploaded)",
  "cloud-only": "In your account, not on this device",
  error: "Could not be saved to your account (see the message)",
};

const SVG = { width: 16, height: 16, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": true, focusable: false } as const;

export function CloudStatusIcon({ status }: { status: ProfileSyncStatus }) {
  const text = CLOUD_STATUS_TEXT[status];
  return (
    <span className={`cloud-status cloud-${status}`} role="img" aria-label={text} title={text} data-status={status}>
      <svg {...SVG}>
        <path d="M7 18a4.5 4.5 0 0 1-.6-8.96A6 6 0 0 1 18 8.5a4 4 0 0 1-.5 8z" />
        {status === "synced" && <path d="M9 12.5l2.2 2.2L15.5 10.5" />}
        {status === "unsaved" && <path d="M12 9v4M12 15.8v.1" />}
        {status === "error" && <path d="M10 10l4 4M14 10l-4 4" />}
        {status === "local-only" && <path d="M3 3l18 18" />}
        {status === "cloud-only" && <path d="M12 9v5M9.8 12.2L12 14.5l2.2-2.3" />}
      </svg>
    </span>
  );
}
