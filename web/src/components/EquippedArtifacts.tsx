import { artifactInfo, artifactsAvailable, currentSlots, setSlot, EMPTY_SLOT, EQUIPPED_SECTION_ID, starIndex } from "../lib/artifacts";
import { markEdited } from "../lib/schemaForm";
import type { ClassInfo, ClassSchema, FormState } from "../types";

/** "★3" / "★ not set": the star the calculator uses for an artifact in a slot (set on the Artifacts tab). */
export const starText = (star: number | null | undefined): string => (star === null || star === undefined ? "★ not set" : `★${starIndex(star)}`);

/**
 * The Inputs page's "Equipped artifacts" section (the workbook's "Equipped Artifacts (up to N)" slot rows): `max_slots` dropdowns for the CURRENT content type.  The choice
 * is stored per content type (`FormState.equippedArtifacts`) and saved with the profile; an artifact can sit in one slot only (it is disabled in the other slots).
 * Star levels and potential lines stay per artifact on the Artifacts tab.  Nothing for a class without artifact support.
 */
export function EquippedArtifacts({ schema, classInfo, state, onState }: { schema: ClassSchema; classInfo?: ClassInfo | null; state: FormState; onState: (s: FormState) => void; onOpenArtifacts?: () => void /* kept for callers; the section no longer has a hint line or link */ }) {
  const art = schema.artifacts;
  if (!art || !artifactsAvailable(schema, classInfo)) return null;
  const slots = currentSlots(art, state);
  const none = art.none_label || "(none)";
  return (
    <details className="sec" id={EQUIPPED_SECTION_ID} data-testid="equipped-artifacts" open>
      <summary>Equipped artifacts</summary>
      <div className="grid">
        {slots.map((key, i) => {
          const id = `f-artifact-slot-${i + 1}`;
          return (
            <div className="field" key={i}>
              <label htmlFor={id}>Slot {i + 1}</label>
              <select
                id={id}
                value={key}
                onChange={(e) => onState(markEdited({ ...state, equippedArtifacts: setSlot(art, state.equippedArtifacts, state.contentType, i, e.target.value) }))}
              >
                <option value={EMPTY_SLOT}>{none}</option>
                {art.artifacts.map((a) => (
                  <option key={a.key} value={a.key} disabled={a.key !== key && slots.includes(a.key)}>
                    {a.name}
                  </option>
                ))}
              </select>
              {key !== EMPTY_SLOT && artifactInfo(art, key) && <small className="help">{starText(state.artifacts?.[key]?.star)}</small>}
            </div>
          );
        })}
      </div>
    </details>
  );
}
