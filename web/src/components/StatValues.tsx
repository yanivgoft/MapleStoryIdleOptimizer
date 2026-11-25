import { useEffect, useMemo, useState } from "react";
import "./sensitivity.css";
import { api } from "../api";
import type { SensitivityMeta, SensitivityResult, SensPart } from "../lib/sensitivity";
import { useSensitivity, type SensStatus } from "../lib/useSensitivity";
import { StatTable } from "./StatTable";
import { ARTIFACT_RANKING_TITLE, EquipRanking } from "./EquipRanking";
import { CdrTable, CompanionTable, SummonTable } from "./SensitivitySections";
import { AboutTab, NOT_AVAILABLE_TEXT, Unavailable } from "./TabNotes";

export const UNSUPPORTED_TEXT = NOT_AVAILABLE_TEXT;

interface SectionDef {
  part: SensPart;
  title: string;
  /** only for the step-like stats: the threshold line that tells the player what to aim for */
  hint?: string;
}
const SECTIONS: SectionDef[] = [
  { part: "companions", title: "Companion comparison" },
  { part: "summon_time", title: "Companion summoning time potential", hint: "Gain at each total of Summoning Time Increase. It rises in steps: aim for the totals where it jumps (Step gain)." },
  { part: "cdr", title: "Cooldown decrease milestones", hint: "Gain at each Skill Cooldown Decrease total. It rises in steps (fixed-duration content only): aim for the totals where it jumps, not for a smooth slope." },
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
  /** opens the Help tab ("See Help" next to the not-available line) */
  onOpenHelp?: () => void;
}) {
  const { result, status, stale = false, pending = false, meta, open, onToggle, onRetry, onOpenHelp } = props;

  if (status.unsupported) {
    return <Unavailable onOpenHelp={onOpenHelp} text={UNSUPPORTED_TEXT} />;
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
            <div className="note">{result.content_type}</div>
          </div>
          <StatTable rows={result.stats.rows} meta={meta} />
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
        <h2>{ARTIFACT_RANKING_TITLE}</h2>
        {result?.artifacts ? (
          <EquipRanking rows={result.artifacts.rows} title={ARTIFACT_RANKING_TITLE} />
        ) : (
          <p className="empty">{result?.stats ? "Loading the artifact ranking..." : "Waiting for the stat values..."}</p>
        )}
      </div>

      {SECTIONS.map((s) => {
        const data = result?.[s.part];
        return (
          <details key={s.part} className="sens-section" open={open.includes(s.part)} onToggle={(e) => onToggle?.(s.part, (e.currentTarget as HTMLDetailsElement).open)}>
            <summary>{s.title}</summary>
            {s.hint && <p className="hint">{s.hint}</p>}
            {!data && <p className="empty">{status.loading ? "Loading..." : "Not loaded yet."}</p>}
            {s.part === "companions" && result?.companions && <CompanionTable part={result.companions} />}
            {s.part === "summon_time" && result?.summon_time && <SummonTable part={result.summon_time} />}
            {s.part === "cdr" && result?.cdr && (
              <>
                <CdrTable part={result.cdr} />
                {result.cdr.note && <p className="hint">{result.cdr.note}</p>}
              </>
            )}
          </details>
        );
      })}

      <AboutTab>
        <ul>
          <li>Each stat is raised by one step on its own (the Step column) and the table shows the % of Total DPS it adds.</li>
          <li>
            &quot;Units per +1% DPS&quot; is how many units of a stat give +1% Total DPS: lower means each unit is worth more, n/a means one step gives no gain. Units differ between stats, so compare the % gained per
            step, or the units against what a unit costs you in game.
          </li>
          <li>Some stats also move the artifacts or masteries that depend on them (for example Crit Rate with Book of Ancient), and that is included.</li>
          <li>
            Where a content type has both bosses and normal monsters, the two are blended by the time weight of that content{result ? ` (${Math.round(result.normal_weight * 100)}% normal monsters here)` : ""}.
          </li>
          <li>Cooldown decrease milestones are a step function and only apply to fixed-duration content: read the jumps, not the slope.</li>
          <li>The artifact ranking shows the gain of equipping each artifact; for an equipped one it is what you lose by removing it. &quot;Typed in Calculator&quot; means its bonus is already in the stats you typed, so the gain is a what-if.</li>
        </ul>
      </AboutTab>
    </div>
  );
}

interface Props {
  classId: string | null;
  inputs: Record<string, unknown> | null;
  active: boolean;
  /** GET /api/classes `status.stat_values` of the class: `false` shows the "not available" message without asking the API at all */
  supported?: boolean;
  /** opens the Help tab ("See Help" next to the not-available line) */
  onOpenHelp?: () => void;
}

/** The "Stat values" tab: loads stats first (the artifact ranking right after), the three sections only once expanded. */
export function StatValues({ classId, inputs, active, supported, onOpenHelp }: Props) {
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
  return <StatValuesView result={result} status={shown} stale={stale} pending={pending} meta={meta} open={open} onToggle={onToggle} onRetry={retry} onOpenHelp={onOpenHelp} />;
}
