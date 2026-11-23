import "./sensitivity.css";
import type { CdrPart, CompanionsPart, SummonPart } from "../lib/sensitivity";
import { gainPct, signedNumber, signedPct, sig, sortCompanions } from "../lib/sensitivity";
import { formatNumber } from "../lib/format";

/** Companion comparison: every companion at the chosen comparison level, best first. */
export function CompanionTable({ part }: { part: CompanionsPart }) {
  const rows = sortCompanions(part.rows);
  return (
    <div className="sens-wrap">
      <table className="sens-table companion-table">
        <caption className="sr-only">Companion comparison</caption>
        <thead>
          <tr>
            <th>#</th>
            <th>Companion</th>
            <th className="num">Level</th>
            <th className="num" title="Total DPS this companion adds against no companion">DPS gain</th>
            <th className="num">% gain</th>
            <th className="num" title="The companion's own DPS (boss / normal blended)">Companion DPS</th>
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
                  {!r.unlocked && <span className="sub">level 0: not owned</span>}
                </td>
                <td className="num">{r.level}</td>
                <td className={`num${r.dps_gain < 0 ? " neg" : ""}`}>{r.unlocked ? signedNumber(r.dps_gain) : "–"}</td>
                <td className={`num${r.pct_gain < 100 ? " neg" : ""}`}>{r.unlocked ? gainPct(r.pct_gain) : "–"}</td>
                <td className="num">{r.unlocked ? formatNumber(r.companion_dps) : "–"}</td>
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
            <th title="Summoning Time Increase % added by boots potential lines on top of the current value">+ Lines %</th>
            <th className="num">Total %</th>
            <th className="num">Summon time (s)</th>
            <th className="num">Window (s)</th>
            <th className="num">Companion DPS</th>
            <th className="num" title="Change of the blended total DPS against no boots lines">Weighted DPS change</th>
            <th className="num">Normal monsters</th>
            {part.boss_phase_content && <th className="num" title="Boss-phase content: average boss DPS change">Avg boss DPS</th>}
          </tr>
        </thead>
        <tbody>
          {part.rows.map((r) => (
            <tr key={r.total_pct} className={r.total_pct === 0 ? "current" : ""}>
              <td>{r.total_pct === 0 ? "none" : `+${r.total_pct}%`}</td>
              <td className="num">{sig(r.summon_time_increase_pct)}</td>
              <td className="num">{sig(r.summon_time_s, 4)}</td>
              <td className="num">{sig(r.window_s, 4)}</td>
              <td className="num">{formatNumber(r.companion_dps)}</td>
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
            <th className="num">CDR (s)</th>
            <th className="num">Total DPS</th>
            <th className="num" title="Gain over the previous milestone">Step gain</th>
            <th className="num" title="Against the current baseline">% vs now</th>
          </tr>
        </thead>
        <tbody>
          {part.rows.map((r) => (
            <tr key={r.cdr} className={r.cdr === part.current_cdr ? "current" : ""}>
              <td className="num">{r.cdr}</td>
              <td className="num">{formatNumber(r.total_dps)}</td>
              <td className={`num${r.step_gain < 0 ? " neg" : ""}`}>{r.step_gain === 0 ? "–" : signedNumber(r.step_gain)}</td>
              <td className={`num${r.pct_gain < 0 ? " neg" : ""}`}>{signedPct(r.pct_gain)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
