import { useEffect, useState } from "react";
import type { Field, Scalar } from "../types";
import { optionLabel, parseNumber, rangeText, unitSuffix } from "../lib/schemaForm";

interface Props {
  field: Field;
  value: Scalar;
  onChange: (value: Scalar) => void;
  error?: string;
  readOnlyDisplay?: string; // computed fields: shown instead of an editable value
  disabled?: boolean; // greyed out (e.g. companion level while no companion is chosen)
  note?: string; // extra hint under the field (e.g. "not unlocked at level 0")
}

function show(value: Scalar): string {
  return value === null || value === undefined ? "" : String(value);
}

export function FormField({ field, value, onChange, error, readOnlyDisplay, disabled, note }: Props) {
  const id = `f-${field.key}`;
  const range = rangeText(field);
  const tightRange = range && !range.startsWith("min") ? range : ""; // wide "min 0" ranges are not worth a line on every field
  const hasHint = !!(field.help || tightRange);
  const helpId = hasHint ? `${id}-help` : undefined;
  const errId = `${id}-err`;
  const numeric = field.type === "int" || field.type === "float";
  const [draft, setDraft] = useState(show(value));
  const [parseError, setParseError] = useState<string | null>(null);

  // follow external changes (profile load, content type switch) unless they equal what the draft already parses to
  useEffect(() => {
    if (!numeric) return;
    const parsed = parseNumber(draft, field.type as "int" | "float");
    if (!(parsed.ok && parsed.value === (value === undefined ? null : value))) {
      setDraft(show(value));
      setParseError(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  const message = parseError ?? error;
  const describedBy = [helpId, message ? errId : undefined].filter(Boolean).join(" ") || undefined;
  const suffix = unitSuffix(field);

  let control;
  if (field.computed) {
    control = <input id={id} type="text" value={readOnlyDisplay ?? "–"} readOnly aria-readonly="true" className="readonly" />;
  } else if (field.type === "enum") {
    control = (
      <select id={id} value={show(value)} onChange={(e) => onChange(e.target.value)} aria-invalid={!!message} aria-describedby={describedBy} disabled={disabled}>
        {(field.options ?? []).map((o) => (
          <option key={o} value={o}>
            {optionLabel(field, o)}
          </option>
        ))}
      </select>
    );
  } else if (numeric) {
    control = (
      <span className="input-wrap">
        <input
          id={id}
          type="text"
          inputMode={field.type === "int" ? "numeric" : "decimal"}
          autoComplete="off"
          value={draft}
          min={field.min ?? undefined}
          max={field.max ?? undefined}
          disabled={disabled}
          aria-invalid={!!message}
          aria-describedby={describedBy}
          onChange={(e) => {
            setDraft(e.target.value);
            const p = parseNumber(e.target.value, field.type as "int" | "float", field.min, field.max);
            if (p.ok) {
              setParseError(null);
              onChange(p.value);
            } else setParseError(p.message);
          }}
        />
        {suffix && <span className="suffix" aria-hidden="true">{suffix}</span>}
      </span>
    );
  } else {
    control = (
      <input id={id} type="text" value={show(value)} aria-invalid={!!message} aria-describedby={describedBy} onChange={(e) => onChange(e.target.value)} />
    );
  }

  return (
    <div className={`field${message ? " has-error" : ""}`}>
      <label htmlFor={id}>
        {field.label}
        {field.unit === "s" && <span className="unit"> (s)</span>}
      </label>
      {control}
      {hasHint && (
        <small id={helpId} className="help">
          {field.help}
          {tightRange && <span className="range"> {field.help ? "(" : "Range "}{tightRange}{field.help ? ")" : ""}</span>}
        </small>
      )}
      {note && <small className="help note-warn">{note}</small>}
      {message && (
        <small id={errId} className="error" role="alert">
          {message}
        </small>
      )}
    </div>
  );
}
