import { artifactInfo, artifactsAvailable, currentSlots, setSlot, EMPTY_SLOT, EQUIPPED_SECTION_ID, starIndex } from "../lib/artifacts";
import type { ClassInfo, ClassSchema, FormState } from "../types";

/** "★3" / "not unlocked (acts as star 0)": the star the engine will use for an artifact in a slot (set on the Artifacts tab). */
const starText = (star: number | null | undefined): string => (star === null || star === undefined ? "not unlocked (acts as star 0)" : `★${starIndex(star)}`);

/**
 * The Inputs page's "Equipped artifacts" section (the workbook's "Equipped Artifacts (up to N)" slot rows): `max_slots` dropdowns for the CURRENT content type.  The choice
 * is stored per content type (`FormState.equippedArtifacts`) and saved with the profile; an artifact can sit in one slot only (it is disabled in the other slots).
 * Star levels and potential lines stay per artifact on the Artifacts tab.  Nothing for a class without artifact support.
 */
export function EquippedArtifacts({ schema, classInfo, state, onState, onOpenArtifacts }: { schema: ClassSchema; classInfo?: ClassInfo | null; state: FormState; onState: (s: FormState) => void; onOpenArtifacts?: () => void }) {
  const art = schema.artifacts;
  if (!art || !artifactsAvailable(schema, classInfo)) return null;
  const slots = currentSlots(art, state);
  const none = art.none_label || "(none)";
  return (
    <fieldset id={EQUIPPED_SECTION_ID} data-testid="equipped-artifacts">
      <legend>Equipped artifacts</legend>
      <p className="note" style={{ margin: "0 0 6px" }}>
        Up to {art.max_slots} artifacts equipped in <strong>{state.contentType}</strong> (each content type keeps its own set; an artifact fits one slot).
        {onOpenArtifacts ? (
          <>
            {" "}
            Star levels and potential lines are set on the{" "}
            <button type="button" className="link" onClick={onOpenArtifacts}>
              Artifacts tab
            </button>
            .
          </>
        ) : (
          " Star levels and potential lines are set on the Artifacts tab."
        )}
      </p>
      <div className="grid">
        {slots.map((key, i) => {
          const id = `f-artifact-slot-${i + 1}`;
          return (
            <div className="field" key={i}>
              <label htmlFor={id}>Slot {i + 1}</label>
              <select
                id={id}
                value={key}
                onChange={(e) => onState({ ...state, equippedArtifacts: setSlot(art, state.equippedArtifacts, state.contentType, i, e.target.value) })}
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
    </fieldset>
  );
}
