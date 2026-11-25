import "./sensitivity.css";
import type { SensitivityMeta, StatRow, StatSort } from "../lib/sensitivity";
import { formatStatValue, formatUnits, gainPct, hasValue, relativeValues, signedNumber, sortStats, statLabel, STEP_SHORT } from "../lib/sensitivity";

interface Props {
  rows: StatRow[];
  sort?: StatSort;
  meta?: SensitivityMeta | null; // kept for callers; the table shows no prose from it
}

/** The stats ranked by value: units per +1% DPS (fewest first = most valuable per unit), DPS / % gain of one step, relative bar; no prose (the how-to-read text is in the About block). */
export function StatTable({ rows, sort = "value" }: Props) {
  const ordered = sortStats(rows, sort);
  const rel = relativeValues(rows);
  return (
    <div className="sens-wrap">
      <table className="sens-table stat-table">
        <caption className="sr-only">Stat values, one step of each stat</caption>
        <thead>
          <tr>
            <th scope="col">#</th>
            <th scope="col">Stat</th>
            <th scope="col" className="num">Current</th>
            <th scope="col" className="num">After one step</th>
            <th scope="col">Step</th>
            <th scope="col" className="num">Units per +1% DPS</th>
            <th scope="col" className="num">DPS gained per step</th>
            <th scope="col" className="num">% gained per step</th>
            <th scope="col">Relative value</th>
          </tr>
        </thead>
        <tbody>
          {ordered.map((r, i) => {
            const valued = hasValue(r);
            return (
              <tr key={r.key} className={valued ? "" : "dim"} data-stat={r.key}>
                <td className="rank">{valued ? i + 1 : "–"}</td>
                <td>
                  <span className="label-main">{statLabel(r.label)}</span>
                </td>
                <td className="num">{formatStatValue(r.current)}</td>
                <td className="num">{formatStatValue(r.new)}</td>
                <td className="step">{STEP_SHORT[r.type] ?? ""}</td>
                <td className="num">
                  <strong>{formatUnits(r.units_per_1pct)}</strong>
                </td>
                <td className={`num${r.dps_gain < 0 ? " neg" : ""}`}>{signedNumber(r.dps_gain)}</td>
                <td className={`num${r.pct_gain < 100 ? " neg" : ""}`}>{gainPct(r.pct_gain)}</td>
                <td>
                  <span className="sens-bar" aria-hidden="true">
                    <span style={{ width: `${Math.round((rel.get(r.key) ?? 0) * 100)}%` }} />
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
