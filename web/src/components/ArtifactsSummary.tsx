import "./companions.css";
import { artifactsAvailable, artifactsInUse } from "../lib/artifacts";
import type { ClassInfo, ClassSchema, FormState } from "../types";

/** Compact read-only line on the Calculator: which artifacts are equipped (set on the Artifacts tab).  Nothing for classes without artifact support. */
export function ArtifactsSummary({ schema, classInfo, state, onEdit }: { schema: ClassSchema; classInfo?: ClassInfo | null; state: FormState; onEdit: () => void }) {
  if (!artifactsAvailable(schema, classInfo) || !schema.artifacts) return null;
  const used = artifactsInUse(schema.artifacts, state.artifacts);
  return (
    <div className="artifacts-summary" data-testid="artifacts-summary">
      <strong>Artifacts in use:</strong>
      {used.length ? (
        <span>
          {used.map((a, i) => (
            <span key={a.key}>
              {i > 0 && ", "}
              {a.name} {a.star}
            </span>
          ))}
        </span>
      ) : (
        <span className="none">none</span>
      )}
      <button type="button" className="link" onClick={onEdit}>
        Edit artifacts
      </button>
    </div>
  );
}
