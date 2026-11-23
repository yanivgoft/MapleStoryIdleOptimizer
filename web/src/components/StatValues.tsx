import { useEffect, useMemo, useState } from "react";
import "./sensitivity.css";
import { api } from "../api";
import type { SensitivityMeta, SensitivityResult, SensPart, StatSort } from "../lib/sensitivity";
import { STAT_SORTS } from "../lib/sensitivity";
import { useSensitivity, type SensStatus } from "../lib/useSensitivity";
import { formatFull, formatNumber } from "../lib/format";
import { StatTable } from "./StatTable";
import { EquipRanking } from "./EquipRanking";
import { CdrTable, CompanionTable, SummonTable } from "./SensitivitySections";

export const UNSUPPORTED_TEXT = "Stat values are not available for this class yet.";

interface SectionDef {
  part: SensPart;
  title: string;
  hint: string;
}
const SECTIONS: SectionDef[] = [
  { part: "companions", title: "Companion comparison", hint: "Every companion at your companion level: total DPS it adds against no companion (set your own levels on the Companions tab)." },
  { part: "summon_time", title: "Companion summoning time potential", hint: "What each total of boots potential lines (Summoning Time Increase %) is worth for the chosen companion." },
  { part: "cdr", title: "Cooldown decrease milestones", hint: "Total DPS at absolute Skill Cooldown Decrease values; a step function (fixed-duration content only), so read the jumps, not the slope." },
];

/** Presentational part of the tab: everything given, nothing fetched (used by the render tests). */
export function StatValuesView(props: {
  result: SensitivityResult | null;
  status: SensStatus;
  stale?: boolean;
  pending?: boolean;
  meta?: SensitivityMeta | null;
  open: SensPart[];
  onToggle?: (part: SensPart, open: boolean) => void;
  onRetry?: () => void;
}) {
  const { result, status, stale = false, pending = false, meta, open, onToggle, onRetry } = props;
  const [sort, setSort] = useState<StatSort>("value");

  if (status.unsupported) {
    return (
      <div className="sens-message" role="status">
        <strong>{UNSUPPORTED_TEXT}</strong>
        <p>The engine only models stat values for some classes so far; the Calculator tab works for every class.</p>
      </div>
    );
  }
  return (
    <div className={`stat-values${stale || pending ? " sens-stale" : ""}`} aria-busy={status.loading}>
      {status.error && (
        <div className="banner error" role="alert">
          {status.error}
          {status.fieldErrors.length > 0 && (
            <ul>
              {status.fieldErrors.map((m) => (
                <li key={m}>{m}</li>
              ))}
            </ul>
          )}
          {onRetry && (
            <p>
              <button type="button" onClick={onRetry}>
                Try again
              </button>
            </p>
          )}
        </div>
      )}
      {(status.loading || pending) && (
        <div className="sens-loading" role="status">
          <span className="spinner" aria-hidden="true" /> {pending && !status.loading ? "Waiting for the inputs to settle..." : "Computing stat values (about half a second)..."}
        </div>
      )}
      {result?.stats ? (
        <>
          <div className="sens-head">
            <div>
              <div className="label">Total DPS now</div>
              <div className="big" title={formatFull(result.baseline_total)}>
                {formatNumber(result.baseline_total)}
              </div>
            </div>
            <div className="note">
              {result.content_type}. Each stat is raised by one step on its own; boss and normal monsters are blended by the time weight of this content (
              {Math.round(result.normal_weight * 100)}% normal). "Units per +1% DPS": how many units of the stat give +1% total DPS - lower means each unit is worth more.
            </div>
          </div>
          <div className="sens-controls">
            <label htmlFor="stat-sort">Sort</label>
            <select id="stat-sort" value={sort} onChange={(e) => setSort(e.target.value as StatSort)}>
              {STAT_SORTS.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.label}
                </option>
              ))}
            </select>
          </div>
          <StatTable rows={result.stats.rows} sort={sort} meta={meta} />
        </>
      ) : (
        !status.error && (
          <div aria-hidden="true">
            {Array.from({ length: 8 }, (_, i) => (
              <span key={i} className="skeleton" style={{ margin: "10px 0", width: `${95 - (i % 3) * 12}%` }} />
            ))}
          </div>
        )
      )}

      <div className="card" style={{ marginTop: 16 }}>
        <h2>Artifacts: what equipping each one is worth</h2>
        {result?.artifacts ? (
          <EquipRanking rows={result.artifacts.rows} title="Artifact equip ranking" />
        ) : (
          <p className="empty">{result?.stats ? "Loading the artifact ranking..." : "Waiting for the stat values..."}</p>
        )}
      </div>

      {SECTIONS.map((s) => {
        const data = result?.[s.part];
        return (
          <details key={s.part} className="sens-section" open={open.includes(s.part)} onToggle={(e) => onToggle?.(s.part, (e.currentTarget as HTMLDetailsElement).open)}>
            <summary>{s.title}</summary>
            <p className="hint">{s.hint}</p>
            {!data && <p className="empty">{status.loading ? "Loading..." : "Not loaded yet."}</p>}
            {s.part === "companions" && result?.companions && <CompanionTable part={result.companions} />}
            {s.part === "summon_time" && result?.summon_time && <SummonTable part={result.summon_time} />}
            {s.part === "cdr" && result?.cdr && (
              <>
                <CdrTable part={result.cdr} />
                <p className="hint">{result.cdr.note}</p>
              </>
            )}
          </details>
        );
      })}
    </div>
  );
}

interface Props {
  classId: string | null;
  inputs: Record<string, unknown> | null;
  active: boolean;
  /** GET /api/classes `status.stat_values` of the class: `false` shows the "not available" message without asking the API at all */
  supported?: boolean;
}

/** The "Stat values" tab: loads stats first (the artifact ranking right after), the three sections only once expanded. */
export function StatValues({ classId, inputs, active, supported }: Props) {
  const on = active && supported !== false;
  const [open, setOpen] = useState<SensPart[]>([]);
  const [meta, setMeta] = useState<SensitivityMeta | null>(null);
  const [statsDone, setStatsDone] = useState(false);

  const wanted = useMemo<SensPart[]>(() => ["stats", ...(statsDone ? (["artifacts"] as SensPart[]) : []), ...open], [statsDone, open]);
  const { result, status, stale, pending, retry } = useSensitivity({ classId, inputs, active: on, wanted });

  // the artifact ranking follows once the stats are in (stats first keeps the first paint at one cheap request)
  useEffect(() => {
    if (result?.stats) setStatsDone(true);
  }, [result]);
  useEffect(() => {
    setOpen([]);
    setStatsDone(false);
    setMeta(null);
  }, [classId]);
  // static labels / notes (cheap, once per class, only when the tab is first shown); the table works without them
  useEffect(() => {
    if (!on || !classId || meta?.class_id === classId) return;
    const ctl = new AbortController();
    api.sensitivityMeta(classId, ctl.signal).then(setMeta, () => undefined);
    return () => ctl.abort();
  }, [on, classId, meta]);

  const onToggle = (part: SensPart, isOpen: boolean) => setOpen((o) => (isOpen ? (o.includes(part) ? o : [...o, part]) : o.filter((p) => p !== part)));
  const shown = supported === false ? { ...status, unsupported: true } : status;
  return <StatValuesView result={result} status={shown} stale={stale} pending={pending} meta={meta} open={open} onToggle={onToggle} onRetry={retry} />;
}
