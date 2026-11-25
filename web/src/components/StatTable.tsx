import "./sensitivity.css";
import type { SensitivityMeta, StatRow } from "../lib/sensitivity";
import { formatStatValue, formatUnits, gainPct, hasValue, relativeValues, statLabel, STEP_SHORT } from "../lib/sensitivity";

interface Props {
  rows: StatRow[];
  meta?: SensitivityMeta | null; // kept for callers; the table shows no prose from it
}

/** The stats in game stat order (no ranking: stats come in different quantities): units per +1% DPS, % gain of one step, relative bar; no prose (the how-to-read text is in the About block). */
export function StatTable({ rows }: Props) {
  const ordered = rows;
  const rel = relativeValues(rows);
  return (
    <div className="sens-wrap">
      <table className="sens-table stat-table">
        <caption className="sr-only">Stat values, one step of each stat</caption>
        <thead>
          <tr>
            <th scope="col">Stat</th>
            <th scope="col" className="num">Current</th>
            <th scope="col" className="num">After one step</th>
            <th scope="col">Step</th>
            <th scope="col" className="num">Units per +1% DPS</th>
            <th scope="col" className="num">% gained per step</th>
            <th scope="col">Relative value</th>
          </tr>
        </thead>
        <tbody>
          {ordered.map((r) => {
            const valued = hasValue(r);
            return (
              <tr key={r.key} className={valued ? "" : "dim"} data-stat={r.key}>
                <td>
                  <span className="label-main">{statLabel(r.label)}</span>
                </td>
                <td className="num">{formatStatValue(r.current)}</td>
                <td className="num">{formatStatValue(r.new)}</td>
                <td className="step">{STEP_SHORT[r.type] ?? ""}</td>
                <td className="num">
                  <strong>{formatUnits(r.units_per_1pct)}</strong>
                </td>
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
