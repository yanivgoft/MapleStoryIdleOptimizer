import "./sensitivity.css";
import type { CdrPart, CompanionsPart, SummonPart } from "../lib/sensitivity";
import { gainPct, signedPct, sig, sortCompanions } from "../lib/sensitivity";

/** Companion comparison: every companion at the chosen comparison level, best first. */
export function CompanionTable({ part }: { part: CompanionsPart }) {
  const rows = sortCompanions(part.rows);
  return (
    <div className="sens-wrap">
      <table className="sens-table companion-table">
        <caption className="sr-only">Companion comparison</caption>
        <thead>
          <tr>
            <th scope="col">#</th>
            <th scope="col">Companion</th>
            <th scope="col" className="num">Level</th>
            <th scope="col" className="num">% gain</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const chosen = r.name === part.chosen;
            return (
              <tr key={r.name} className={`${r.unlocked ? "" : "dim"}${chosen ? " current" : ""}`} data-companion={r.name}>
                <td className="rank">{r.unlocked ? r.rank_position : "–"}</td>
                <td>
                  <span className="label-main">{r.name}</span>
                  {chosen && <span className="chip ok">chosen</span>}
                  {!r.unlocked && <span className="sub">not owned</span>}
                </td>
                <td className="num">{r.level}</td>
                <td className={`num${r.pct_gain < 100 ? " neg" : ""}`}>{r.unlocked ? gainPct(r.pct_gain) : "–"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

const frac = (v: number | null) => (v === null ? "–" : signedPct(v * 100));

/** Value of each Summoning-Time total the boots potential lines can reach. */
export function SummonTable({ part }: { part: SummonPart }) {
  return (
    <div className="sens-wrap">
      <table className="sens-table summon-table">
        <caption className="sr-only">Companion summoning time potential</caption>
        <thead>
          <tr>
            <th scope="col">+ Lines %</th>
            <th scope="col" className="num">Total %</th>
            <th scope="col" className="num">Summon time (s)</th>
            <th scope="col" className="num">Window (s)</th>
            <th scope="col" className="num">Weighted DPS change</th>
            <th scope="col" className="num">Normal monsters</th>
            {part.boss_phase_content && <th scope="col" className="num">Avg boss DPS</th>}
          </tr>
        </thead>
        <tbody>
          {part.rows.map((r) => (
            <tr key={r.total_pct} className={r.total_pct === 0 ? "current" : ""}>
              <td>{r.total_pct === 0 ? "none" : `+${r.total_pct}%`}</td>
              <td className="num">{sig(r.summon_time_increase_pct)}</td>
              <td className="num">{sig(r.summon_time_s, 4)}</td>
              <td className="num">{sig(r.window_s, 4)}</td>
              <td className={`num${r.weighted_dps_change < 0 ? " neg" : ""}`}>{frac(r.weighted_dps_change)}</td>
              <td className="num">{frac(r.normal_dps_change)}</td>
              {part.boss_phase_content && <td className="num">{frac(r.avg_boss_dps_change)}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Skill Cooldown Decrease milestones (absolute seconds): a step function in fixed-duration content. */
export function CdrTable({ part }: { part: CdrPart }) {
  return (
    <div className="sens-wrap">
      <table className="sens-table cdr-table">
        <caption className="sr-only">Cooldown decrease milestones</caption>
        <thead>
          <tr>
            <th scope="col" className="num">CDR (s)</th>
            <th scope="col" className="num">% vs now</th>
            <th scope="col" className="num">Step gain</th>
          </tr>
        </thead>
        <tbody>
          {part.rows.map((r) => (
            <tr key={r.cdr} className={r.cdr === part.current_cdr ? "current" : ""}>
              <td className="num">{r.cdr}</td>
              <td className={`num${r.pct_gain < 0 ? " neg" : ""}`}>{signedPct(r.pct_gain)}</td>
              <td className={`num${r.step_gain < 0 ? " neg" : ""}`}>{r.step_gain === 0 || !(part.baseline_total > 0) ? "–" : signedPct((r.step_gain / part.baseline_total) * 100)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
