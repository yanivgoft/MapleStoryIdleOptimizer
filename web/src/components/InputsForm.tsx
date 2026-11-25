import { useMemo, type ReactNode } from "react";
import type { ClassInfo, ClassSchema, FormState, Scalar } from "../types";
import { FormField } from "./FormField";
import "./companions.css";
import { COMPANION_GROUP, computedFields, copyContentValues, getValue, groupFields, groupRank, setValue, switchContentType, visibleGroups } from "../lib/schemaForm";
import { companionOptions, companionsOf, effectiveCompanion, unlockedCompanions } from "../lib/companions";
import { formatNumber } from "../lib/format";
import { COMPANION_SECTION_ID } from "../lib/artifacts";
import { EquippedArtifacts } from "./EquippedArtifacts";

interface Props {
  schema: ClassSchema;
  state: FormState;
  onState: (s: FormState) => void;
  errors: Record<string, string>;
  derived?: Record<string, unknown>;
  loadDefaults: (contentType: string) => void; // switch: resolves defaults (server) for a content type visited first time
  onOpenCompanions?: () => void; // "Edit companions" / "Set up your companions": switch to the Companions tab
  classInfo?: ClassInfo | null;
  onOpenArtifacts?: () => void; // "Artifacts tab" link of the Equipped artifacts section
}

/** Sections that start collapsed (everything else is open); a section with a field error always opens. */
export const COLLAPSED_SECTIONS = ["Skill levels", "Additional bonuses", "Fight setup (calculated)"];
export const FORM_HINT = "Enter the values shown on your preset page in game.";
export const CONTENT_TYPE_HINT = "Each content type keeps its own stats.";

function Section({ name, id, hasError, children }: { name: string; id?: string; hasError?: boolean; children: ReactNode }) {
  return (
    <details className="sec" id={id} open={!COLLAPSED_SECTIONS.includes(name) || !!hasError}>
      <summary>{name}</summary>
      {children}
    </details>
  );
}

export function InputsForm({ schema, state, onState, errors, derived, loadDefaults, onOpenCompanions, classInfo, onOpenArtifacts }: Props) {
  const groups = useMemo(() => groupFields(schema), [schema]);
  const shown = visibleGroups(groups, state.contentType);
  const computed = computedFields(schema);
  const owned = companionsOf(schema, state);
  const options = companionOptions(schema, owned);
  const { choice: chosen, level: chosenLevel } = effectiveCompanion(schema, state);
  const hasCompanions = unlockedCompanions(schema, owned).length > 0;
  // the Equipped artifacts section sits after "Additional bonuses", just before the Main companion section
  const equippedAt = shown.findIndex((g) => groupRank(g.name) >= groupRank(COMPANION_GROUP));
  const equippedSection = <EquippedArtifacts key="equipped-artifacts" schema={schema} classInfo={classInfo} state={state} onState={onState} onOpenArtifacts={onOpenArtifacts} />;
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
      <p className="form-hint">{FORM_HINT}</p>
      {shown.flatMap((g, gi) => [
        ...(gi === equippedAt ? [equippedSection] : []),
        <Section key={g.name} name={g.name} id={g.name === COMPANION_GROUP ? COMPANION_SECTION_ID : undefined} hasError={g.fields.some((f) => !!errors[f.key])}>
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
                  {hasCompanions ? (
                    <>
                      <span className="label">Companion level</span>
                      <span className="companion-level-text">{chosen === "None" ? "no companion chosen" : `${chosen}: level ${chosenLevel} (set on the Companions tab)`}</span>
                      <button type="button" className="link" onClick={onOpenCompanions} disabled={!onOpenCompanions}>
                        Edit companions
                      </button>
                    </>
                  ) : (
                    <span className="companion-level-text">
                      No companions yet:{" "}
                      <button type="button" className="link" onClick={onOpenCompanions} disabled={!onOpenCompanions}>
                        set levels on the Companions tab
                      </button>
                      .
                    </span>
                  )}
                </div>
              ) : (
                <FormField
                  key={f.key}
                  field={f.key === "companion_choice" ? { ...f, options, help: null } : f.key === "content_type" ? { ...f, help: CONTENT_TYPE_HINT } : f}
                  value={f.key === "companion_choice" ? chosen : getValue(state, f)}
                  error={errors[f.key]}
                  onChange={(v) => onChange(f.key, v)}
                />
              ),
            )}
          </div>
        </Section>,
      ])}
      {equippedAt < 0 && equippedSection}
      <Section name="Fight setup (calculated)">
        <div className="grid">
          {computed.map((f) => {
            const v = derived?.[f.key];
            const text = typeof v === "number" ? formatNumber(v) : v === undefined || v === null ? "–" : String(v);
            return <FormField key={f.key} field={f} value={null} readOnlyDisplay={text} onChange={() => undefined} />;
          })}
        </div>
      </Section>
    </form>
  );
}
