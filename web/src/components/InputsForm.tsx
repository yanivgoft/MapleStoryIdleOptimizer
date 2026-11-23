import { useMemo } from "react";
import type { ClassSchema, FormState, Scalar } from "../types";
import { FormField } from "./FormField";
import "./companions.css";
import { COMPANION_GROUP, computedFields, copyContentValues, getValue, groupFields, setValue, switchContentType, visibleGroups } from "../lib/schemaForm";
import { companionOptions, companionsOf, effectiveCompanion, unlockedCompanions } from "../lib/companions";
import { formatNumber } from "../lib/format";
import { COMPANION_SECTION_ID } from "../lib/artifacts";

interface Props {
  schema: ClassSchema;
  state: FormState;
  onState: (s: FormState) => void;
  errors: Record<string, string>;
  derived?: Record<string, unknown>;
  loadDefaults: (contentType: string) => void; // switch: resolves defaults (server) for a content type visited first time
  onOpenCompanions?: () => void; // "Edit companions" / "Set up your companions": switch to the Companions tab
}

export function InputsForm({ schema, state, onState, errors, derived, loadDefaults, onOpenCompanions }: Props) {
  const groups = useMemo(() => groupFields(schema), [schema]);
  const shown = visibleGroups(groups, state.contentType);
  const computed = computedFields(schema);
  const owned = companionsOf(schema, state);
  const options = companionOptions(schema, owned);
  const { choice: chosen, level: chosenLevel } = effectiveCompanion(schema, state);
  const visited = Object.keys(state.perContent).filter((c) => c !== state.contentType);

  const onChange = (key: string, value: Scalar) => {
    const field = schema.fields.find((f) => f.key === key)!;
    if (key === "content_type") {
      const ct = String(value);
      if (state.perContent[ct]) onState(switchContentType(state, schema, ct));
      else loadDefaults(ct);
      return;
    }
    onState(setValue(state, field, value));
  };

  return (
    <form className="inputs" onSubmit={(e) => e.preventDefault()} aria-label={`${schema.name} inputs`}>
      {shown.map((g) => (
        <fieldset key={g.name} id={g.name === COMPANION_GROUP ? COMPANION_SECTION_ID : undefined}>
          <legend>{g.name}</legend>
          {g.name === "Character" && visited.length > 0 && (
            <div className="copy-from">
              <label htmlFor="copy-from">Copy stats from</label>
              <select
                id="copy-from"
                value=""
                onChange={(e) => e.target.value && onState(copyContentValues(state, schema, e.target.value, state.contentType))}
              >
                <option value="">choose content type...</option>
                {visited.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
          )}
          <div className="grid">
            {g.fields.map((f) =>
              f.key === "companion_level" ? (
                <div key={f.key} className="field companion-level-line" data-testid="companion-level-line">
                  <span className="label">Companion level</span>
                  <span className="companion-level-text">
                    {chosen === "None"
                      ? unlockedCompanions(schema, owned).length
                        ? "no companion chosen"
                        : "no companions set up yet"
                      : `${chosen}: level ${chosenLevel} (set on the Companions tab)`}
                  </span>
                  <button type="button" className="link" onClick={onOpenCompanions} disabled={!onOpenCompanions}>
                    {unlockedCompanions(schema, owned).length ? "Edit companions" : "Set up your companions"}
                  </button>
                </div>
              ) : (
                <FormField
                  key={f.key}
                  field={f.key === "companion_choice" ? { ...f, options, help: "Pick from the companions you own (levels are set on the Companions tab)." } : f}
                  value={f.key === "companion_choice" ? chosen : getValue(state, f)}
                  error={errors[f.key]}
                  onChange={(v) => onChange(f.key, v)}
                />
              ),
            )}
          </div>
        </fieldset>
      ))}
      <fieldset>
        <legend>Computed (read-only)</legend>
        <div className="grid">
          {computed.map((f) => {
            const v = derived?.[f.key];
            const text = typeof v === "number" ? formatNumber(v) : v === undefined || v === null ? "–" : String(v);
            return <FormField key={f.key} field={f} value={null} readOnlyDisplay={text} onChange={() => undefined} />;
          })}
        </div>
      </fieldset>
    </form>
  );
}
