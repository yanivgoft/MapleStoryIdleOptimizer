// Accessible modal dialog shared by the account dialogs: role="dialog" + aria-modal + a labelled title, focus moves into the dialog on open, Tab / Shift+Tab
// stay inside, Escape closes, and focus goes back to whatever had it before.  Rendered in place (position: fixed), not through a portal.
import { useEffect, useId, useRef, type ReactNode } from "react";

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

interface ModalProps {
  title: string;
  onClose: () => void;
  children: ReactNode;
  /** `alertdialog` for destructive confirmations. */
  role?: "dialog" | "alertdialog";
  className?: string;
  /** Element id inside the dialog to focus first (default: the first focusable control). */
  initialFocusId?: string;
}

export function Modal({ title, onClose, children, role = "dialog", className, initialFocusId }: ModalProps) {
  const ref = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null;
    const root = ref.current;
    const first = (initialFocusId ? root?.querySelector<HTMLElement>(`#${CSS.escape(initialFocusId)}`) : null) ?? root?.querySelector<HTMLElement>(FOCUSABLE) ?? root;
    first?.focus();
    return () => prev?.focus?.();
  }, [initialFocusId]);

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      e.stopPropagation();
      closeRef.current();
      return;
    }
    if (e.key !== "Tab" || !ref.current) return;
    const items = Array.from(ref.current.querySelectorAll<HTMLElement>(FOCUSABLE));
    if (!items.length) {
      e.preventDefault();
      return;
    }
    const firstEl = items[0];
    const lastEl = items[items.length - 1];
    if (e.shiftKey && document.activeElement === firstEl) {
      e.preventDefault();
      lastEl.focus();
    } else if (!e.shiftKey && document.activeElement === lastEl) {
      e.preventDefault();
      firstEl.focus();
    }
  };

  return (
    <div className="acct-backdrop" onMouseDown={(e) => e.target === e.currentTarget && closeRef.current()}>
      <div ref={ref} className={`acct-dialog${className ? ` ${className}` : ""}`} role={role} aria-modal="true" aria-labelledby={titleId} tabIndex={-1} onKeyDown={onKeyDown}>
        <h2 id={titleId}>{title}</h2>
        {children}
      </div>
    </div>
  );
}
