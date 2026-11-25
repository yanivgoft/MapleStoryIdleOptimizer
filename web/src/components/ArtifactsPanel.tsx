import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useDebounced } from "../hooks";
import { useSensitivity } from "../lib/useSensitivity";
import type { SensPart } from "../lib/sensitivity";
import { buildInputs } from "../lib/schemaForm";
import { formatNumber } from "../lib/format";
import { artifactStarsExtra, artifactsAvailable, breakdown, bucketTotals, currentSlots, dpsDelta, equippedKeys, withoutArtifacts } from "../lib/artifacts";
import type { ArtifactSchema, ClassInfo, ClassSchema, ComputeResult, FormState } from "../types";
import { ArtifactTable } from "./ArtifactTable";
import { AboutTab, Unavailable } from "./TabNotes";
import { ARTIFACT_RANKING_TITLE, EquipRanking } from "./EquipRanking";
import { potentialTables } from "../lib/artifactPotentials";
import type { CubesMeta } from "../lib/cubes";
import type { RequestStatus } from "../lib/liveRequest";

// The artifact ranking is the stat values' artifact part (POST .../sensitivity, which=["artifacts"]) shown with the shared EquipRanking table.

/** Artifact ranking of all 36 artifacts for the current inputs; only requested while the Artifacts tab is open and the class supports stat values. */
export function RankingSection({ classId, inputs, supported, onOpenHelp }: { classId: string; inputs: Record<string, unknown> | null; supported: boolean; onOpenHelp?: () => void }) {
  const wanted = useMemo<SensPart[]>(() => ["artifacts"], []);
  const { result, status, stale, pending, retry } = useSensitivity({ classId, inputs, active: supported, wanted });
  return (
    <section className="card art-ranking" aria-label={ARTIFACT_RANKING_TITLE}>
      <h2>{ARTIFACT_RANKING_TITLE}</h2>
      {!supported || status.unsupported ? (
        <Unavailable onOpenHelp={onOpenHelp} />
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
            <EquipRanking rows={result.artifacts.rows} title={ARTIFACT_RANKING_TITLE} />
          ) : (
            !status.error && <p className="empty">{status.loading || pending ? "Computing the ranking..." : "Loading the ranking..."}</p>
          )}
        </div>
      )}
    </section>
  );
}

/** The collapsed explanation at the bottom of the Artifacts tab (what the table, the equipped marker, the potential lines and the ranking mean). */
export function ArtifactsAbout({ art, meta, contentType }: { art: ArtifactSchema; meta?: CubesMeta | null; contentType?: string }) {
  const tables = potentialTables(meta);
  return (
    <AboutTab>
      <ul>
        <li>
          One row per artifact: its star level and its potential lines are kept for every artifact and saved with your profile (the same for every content type). Which artifacts are equipped (up to {art.max_slots}{" "}
          slots, an artifact once) is chosen per content type in the Equipped artifacts section of the Calculator; the rows marked &quot;equipped&quot; are the ones equipped in{" "}
          {contentType ? <strong>{contentType}</strong> : "the current content type"}. &quot;Not unlocked&quot; counts as star 0 once the artifact is equipped.
        </li>
        <li>
          Potential lines are a reference calculator: they do not change your Total DPS (type a roll you keep into the Calculator yourself), but the artifact ranking counts them. Epic / Unique artifacts have 2 lines, Legendary 3; lines unlock at star{" "}
          {tables.line_min_star.join(" / ")}, locked lines count 0. Same-stat lines add, different stats multiply. A stat marked with a warning is not rollable on artifacts: it is kept from an old profile or an import,
          valued at 0 and sent as empty.
        </li>
        <li>Artifacts marked baked in already have their bonus inside the stats you typed, so they add nothing to Total DPS here; their gain in the ranking is a what-if. The &quot;No DPS effect&quot; tag marks artifacts whose effect does not change damage in this calculator (for example raid-only or accuracy bonuses).</li>
        <li>The equipped-artifacts table lists the value each equipped artifact feeds into the calculation and the Total DPS with them against none.</li>
        <li>
          The artifact ranking shows what each artifact is worth in Total DPS if equipped: the unequipped ones at the star set in the table, added to what you have equipped in this content type even when all slots are used.
          Artifacts that are not unlocked are listed unranked. Equipped ones show what you would lose by removing them.
        </li>
      </ul>
    </AboutTab>
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
  /** "go to Equipped artifacts": the Calculator's section (the equipped artifacts are chosen there, per content type) */
  onOpenInputs?: () => void;
  /** opens the Help tab (the "See Help" link of an unavailable section) */
  onOpenHelp?: () => void;
  /** GET .../cubes/meta (the potential-line tables of the Artifacts table; the app's static copy is used while it is null / undefined / unavailable) */
  cubesMeta?: CubesMeta | null;
  cubesMetaStatus?: RequestStatus;
}

/** "Not available for this class yet" panel (schema says artifacts are not modelled). */
export function ArtifactsUnavailable({ name, onOpenHelp }: { name: string; onOpenHelp?: () => void }) {
  return (
    <section className="card artifacts" aria-label="Artifacts">
      <h2>Artifacts</h2>
      <Unavailable onOpenHelp={onOpenHelp} text={`Artifacts are not available for ${name} yet.`} />
    </section>
  );
}

const fmtVal = (v: number, unit: string) => `${v >= 0 ? "+" : ""}${formatNumber(v)}${unit}`;

/** Equip effects as the engine used them for the current inputs (result.artifacts) + the Total DPS effect against a no-artifact calculation. */
export function ArtifactBreakdown({ result, baselineDps, baselineState }: { result: ComputeResult; baselineDps: number | null; baselineState: "idle" | "busy" | "error" }) {
  const rows = breakdown(result);
  const totals = bucketTotals(result);
  if (!rows.length) return null;
  const delta = dpsDelta(result.total_dps, baselineDps);
  return (
    <section className="card art-breakdown" aria-label="Artifact effects in the calculation">
      <h2>What the equipped artifacts do in this calculation</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">Artifact</th>
              <th scope="col" className="num">Star</th>
              <th scope="col">Value used</th>
              <th scope="col">Feeds</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.key} className={r.badges.some((b) => b.kind === "no_dps") ? "dim" : undefined}>
                <td>{r.name}</td>
                <td className="num">{r.star}</td>
                <td>
                  {r.values.length === 0 ? (
                    <span className="note">-</span>
                  ) : (
                    <ul className="art-lines">
                      {r.values.map((v) => (
                        <li key={v.label}>
                          {v.label}: {fmtVal(v.value, v.unit)}
                          {!v.applied && <span className="note"> (baked in)</span>}
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
      {totals.length > 0 && (
        <p className="note">
          Totals these artifacts add: {totals.map((t) => `${t.label} ${fmtVal(t.value, "")}`).join(" | ")}
        </p>
      )}
      <p className="art-delta" role="status">
        <strong>Total DPS with these artifacts vs. none</strong>:{" "}
        {delta ? (
          <strong>{delta.pct !== null ? `${delta.pct >= 0 ? "+" : ""}${delta.pct.toFixed(2)}%` : "–"}</strong>
        ) : baselineState === "error" ? (
          "not available (the comparison failed)"
        ) : (
          "calculating..."
        )}
      </p>
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

export function ArtifactsPanel({ schema, classInfo, state, onState, result, busy, stale, onOpenCompanion, onOpenInputs, onOpenHelp, cubesMeta, cubesMetaStatus }: Props) {
  const art = schema.artifacts;
  const available = artifactsAvailable(schema, classInfo);
  const equippedIds = useMemo(() => (art ? equippedKeys(art, currentSlots(art, state)) : []), [art, state]);
  const equipped = equippedIds.length;
  const inputs = useMemo(() => (available ? buildInputs(schema, state) : null), [available, schema, state]);
  // the equip ranking also gets the star of EVERY artifact (the table's Star level column), not only of the equipped ones
  const rankingInputs = useMemo(() => (inputs && art ? { ...inputs, ...artifactStarsExtra(art, state.artifacts) } : inputs), [inputs, art, state.artifacts]);
  const baseline = useBaseline(state.classId, inputs, available && equipped > 0);

  if (!available || !art) return <ArtifactsUnavailable name={schema.name} onOpenHelp={onOpenHelp} />;
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
        equipped={equippedIds}
        contentType={state.contentType}
        onOpenInputs={onOpenInputs}
      />

      {equipped > 0 && hasResult && <ArtifactBreakdown result={result!} baselineDps={!busy && !stale ? baseline.dps : null} baselineState={baseline.status} />}
      {equipped > 0 && !hasResult && <p className="empty">{busy ? "Calculating..." : "The artifact breakdown appears after the next calculation."}</p>}

      <RankingSection classId={state.classId} inputs={rankingInputs} supported={classInfo?.status?.stat_values !== false} onOpenHelp={onOpenHelp} />

      <ArtifactsAbout art={art} meta={cubesMeta} contentType={state.contentType} />
    </div>
  );
}
