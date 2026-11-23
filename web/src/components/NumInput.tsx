import { useEffect, useState } from "react";
import { parseNumber } from "../lib/schemaForm";

interface Props {
  value: number | null;
  onChange: (value: number | null) => void;
  label: string; // aria-label (the control has no visible label of its own)
  whole?: boolean;
  min?: number | null;
  max?: number | null;
  disabled?: boolean;
  placeholder?: string;
  className?: string;
}

const show = (v: number | null) => (v === null || v === undefined ? "" : String(v));

/** Small numeric text input for the cube tabs: '' = null, "1,234" / "1e6" accepted, inline range message, follows external changes (profile load). */
export function NumInput({ value, onChange, label, whole = false, min = 0, max = null, disabled, placeholder, className }: Props) {
  const [draft, setDraft] = useState(show(value));
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const p = parseNumber(draft, whole ? "int" : "float");
    if (!(p.ok && p.value === value)) {
      setDraft(show(value));
      setError(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);
  return (
    <input
      type="text"
      inputMode={whole ? "numeric" : "decimal"}
      autoComplete="off"
      className={`numin${className ? ` ${className}` : ""}`}
      aria-label={label}
      aria-invalid={!!error}
      title={error ?? undefined}
      placeholder={placeholder}
      disabled={disabled}
      value={draft}
      onChange={(e) => {
        setDraft(e.target.value);
        const p = parseNumber(e.target.value, whole ? "int" : "float", min, max);
        if (p.ok) {
          setError(null);
          onChange(p.value);
        } else setError(p.message);
      }}
    />
  );
}
