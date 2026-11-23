import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useDebounced } from "../hooks";
import { useSensitivity } from "../lib/useSensitivity";
import type { SensPart } from "../lib/sensitivity";
import { EquipRanking } from "./EquipRanking";
import { buildInputs } from "../lib/schemaForm";
import { formatNumber } from "../lib/format";
import { artifactStarsExtra, artifactsAvailable, breakdown, bucketTotals, dpsDelta, equippedCount, withoutArtifacts } from "../lib/artifacts";
import type { ClassInfo, ClassSchema, ComputeResult, FormState } from "../types";
import { ArtifactTable } from "./ArtifactTable";
import type { CubesMeta } from "../lib/cubes";
import type { RequestStatus } from "../lib/liveRequest";

// The equip ranking is the Stat values engine's artifact part (POST .../sensitivity, which=["artifacts"]) shown with the shared EquipRanking table.
const RANKING_UNSUPPORTED = "The equip ranking (which artifact is worth the most DPS) is not available for this class yet.";

/** Equip ranking of all 36 artifacts for the current inputs; only requested while the Artifacts tab is open and the class supports stat values. */
export function RankingSection({ classId, inputs, supported }: { classId: string; inputs: Record<string, unknown> | null; supported: boolean }) {
  const wanted = useMemo<SensPart[]>(() => ["artifacts"], []);
  const { result, status, stale, pending, retry } = useSensitivity({ classId, inputs, active: supported, wanted });
  return (
    <section className="card art-ranking" aria-label="Artifact equip ranking">
      <h2>Equip ranking</h2>
      {!supported || status.unsupported ? (
        <p className="empty" role="status">
          {RANKING_UNSUPPORTED}
        </p>
      ) : (
        <div className={stale || pending ? "sens-stale" : undefined} aria-busy={status.loading}>
          {status.error && (
            <div className="banner error" role="alert">
              {status.error}{" "}
              <button type="button" onClick={retry}>
                Try again
              </button>
            </div>
          )}
          {result?.artifacts ? (
            <EquipRanking rows={result.artifacts.rows} title="Artifact equip ranking" />
          ) : (
            !status.error && <p className="empty">{status.loading || pending ? "Computing the ranking..." : "Loading the ranking..."}</p>
          )}
          <p className="note">What each artifact is worth in total DPS if equipped (a what-if per artifact: the unequipped ones at the star set in the table above, added to what you have equipped even when all slots are used; artifacts that are not unlocked are listed unranked). Equipped ones show what you would lose.</p>
        </div>
      )}
    </section>
  );
}

interface Props {
  schema: ClassSchema;
  classInfo?: ClassInfo | null;
  state: FormState;
  onState: (s: FormState) => void;
  result: ComputeResult | null;
  busy: boolean;
  stale: boolean;
  onOpenCompanion: () => void;
  /** GET .../cubes/meta (the potential-line tables of the Artifacts table; the app's static copy is used while it is null / undefined / unavailable) */
  cubesMeta?: CubesMeta | null;
  cubesMetaStatus?: RequestStatus;
}

/** "Not available for this class yet" panel (schema says artifacts are not modelled). */
export function ArtifactsUnavailable({ name }: { name: string }) {
  return (
    <section className="card artifacts" aria-label="Artifacts">
      <h2>Artifacts</h2>
      <p className="empty" role="status">
        Artifacts are not available for {name} yet. They are modelled class by class; no artifact settings are sent with this class&apos;s calculation.
      </p>
    </section>
  );
}

const fmtVal = (v: number, unit: string) => `${v >= 0 ? "+" : ""}${formatNumber(v)}${unit}`;

/** Equip effects as the engine used them for the current inputs (result.artifacts) + the Total DPS effect against a no-artifact calculation. */
export function ArtifactBreakdown({ result, baselineDps, baselineState }: { result: ComputeResult; baselineDps: number | null; baselineState: "idle" | "busy" | "error" }) {
  const rows = breakdown(result);
  const totals = bucketTotals(result);
  const notes = Array.isArray(result.artifacts?.notes) ? (result.artifacts!.notes as unknown[]).filter((n): n is string => typeof n === "string") : [];
  if (!rows.length) return null;
  const delta = dpsDelta(result.total_dps, baselineDps);
  return (
    <section className="card art-breakdown" aria-label="Artifact effects in the calculation">
      <h2>What the equipped artifacts do in this calculation</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Artifact</th>
              <th className="num">Star</th>
              <th>Value used</th>
              <th>Feeds</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.key} className={r.badges.some((b) => b.kind === "no_dps") ? "dim" : undefined}>
                <td>{r.name}</td>
                <td className="num">{r.star}</td>
                <td>
                  {r.values.length === 0 ? (
                    <span className="note">{r.note ?? "-"}</span>
                  ) : (
                    <ul className="art-lines">
                      {r.values.map((v) => (
                        <li key={v.label}>
                          {v.label}: {fmtVal(v.value, v.unit)}
                          {!v.applied && <span className="note"> (reference only: type it into Inputs)</span>}
                        </li>
                      ))}
                    </ul>
                  )}
                </td>
                <td>{r.bucket}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {notes.map((n) => (
        <p key={n} className="note">
          {n}
        </p>
      ))}
      {totals.length > 0 && (
        <p className="note">
          Bucket totals fed into the model: {totals.map((t) => `${t.label} ${fmtVal(t.value, "")}`).join(" | ")}
        </p>
      )}
      <p className="art-delta" role="status">
        <strong>Total DPS with these artifacts vs. none</strong> (separate calculation without artifacts):{" "}
        {delta ? (
          <>
            {formatNumber(result.total_dps)} vs {formatNumber(baselineDps as number)}
            {" = "}
            <strong>
              {delta.abs >= 0 ? "+" : ""}
              {formatNumber(delta.abs)}
              {delta.pct !== null && ` (${delta.pct >= 0 ? "+" : ""}${delta.pct.toFixed(2)}%)`}
            </strong>
          </>
        ) : baselineState === "error" ? (
          "not available (the comparison calculation failed)"
        ) : (
          "calculating..."
        )}
      </p>
      <p className="note">Baked-into-Inputs artifacts add nothing here until you type their stat into the Inputs; their gain is shown on the equip ranking below.</p>
    </section>
  );
}

/** The no-artifact comparison calculation: only runs while this panel is mounted (the tab is open) and something is equipped. */
function useBaseline(classId: string, inputs: Record<string, unknown> | null, enabled: boolean) {
  const key = enabled && inputs ? JSON.stringify(withoutArtifacts(inputs)) : "";
  const debounced = useDebounced(key, 500);
  const [dps, setDps] = useState<number | null>(null);
  const [status, setStatus] = useState<"idle" | "busy" | "error">("idle");
  useEffect(() => {
    if (!debounced) {
      setDps(null);
      setStatus("idle");
      return;
    }
    const ctl = new AbortController();
    setStatus("busy");
    api
      .compute(classId, JSON.parse(debounced), ctl.signal)
      .then((r) => {
        setDps(r.total_dps);
        setStatus("idle");
      })
      .catch((e: unknown) => {
        if ((e as Error).name === "AbortError") return;
        setDps(null);
        setStatus("error");
      });
    return () => ctl.abort();
  }, [debounced, classId]);
  return { dps: debounced === key ? dps : null, status: debounced === key ? status : ("busy" as const) };
}

export function ArtifactsPanel({ schema, classInfo, state, onState, result, busy, stale, onOpenCompanion, cubesMeta, cubesMetaStatus }: Props) {
  const art = schema.artifacts;
  const available = artifactsAvailable(schema, classInfo);
  const equipped = art ? equippedCount(art, state.artifacts) : 0;
  const inputs = useMemo(() => (available ? buildInputs(schema, state) : null), [available, schema, state]);
  // the equip ranking also gets the star of EVERY artifact (the table's Star level column), not only of the equipped ones
  const rankingInputs = useMemo(() => (inputs && art ? { ...inputs, ...artifactStarsExtra(art, state.artifacts) } : inputs), [inputs, art, state.artifacts]);
  const baseline = useBaseline(state.classId, inputs, available && equipped > 0);

  if (!available || !art) return <ArtifactsUnavailable name={schema.name} />;
  const hasResult = !!result && breakdown(result).length > 0;

  return (
    <div className="artifacts-tab">
      <ArtifactTable
        classId={state.classId}
        inputs={inputs}
        supported={classInfo?.status?.stat_values}
        active
        meta={cubesMeta}
        metaStatus={cubesMetaStatus ?? { loading: false, unsupported: false, error: null, fieldErrors: [] }}
        art={art}
        state={state.artifacts}
        onState={(artifacts) => onState({ ...state, artifacts })}
        onOpenCompanion={onOpenCompanion}
      />

      {equipped > 0 && hasResult && <ArtifactBreakdown result={result!} baselineDps={!busy && !stale ? baseline.dps : null} baselineState={baseline.status} />}
      {equipped > 0 && !hasResult && <p className="empty">{busy ? "Calculating..." : "The artifact breakdown appears after the next calculation."}</p>}

      <RankingSection classId={state.classId} inputs={rankingInputs} supported={classInfo?.status?.stat_values !== false} />
    </div>
  );
}
