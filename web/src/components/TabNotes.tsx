import type { ReactNode } from "react";
import "./tabnotes.css";

/** The collapsed explanation block at the BOTTOM of a tab ("less is more": the working area stays minimal, the how-to-read text lives here and in Help). */
export function AboutTab({ children, title = "About this tab" }: { children: ReactNode; title?: string }) {
  return (
    <details className="about-tab">
      <summary>{title}</summary>
      <div className="about-body">{children}</div>
    </details>
  );
}

export const NOT_AVAILABLE_TEXT = "Not available for this class yet.";

/** ONE line for a tab the selected class does not have yet, plus a "See Help" link when the app passes `onOpenHelp`. */
export function Unavailable({ onOpenHelp, text = NOT_AVAILABLE_TEXT }: { onOpenHelp?: () => void; text?: string }) {
  return (
    <p className="empty unavailable" role="status">
      {text}
      {onOpenHelp && (
        <>
          {" "}
          <button type="button" className="link" onClick={onOpenHelp}>
            See Help
          </button>
        </>
      )}
    </p>
  );
}
