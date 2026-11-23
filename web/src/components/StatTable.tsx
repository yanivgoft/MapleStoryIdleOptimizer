import "./sensitivity.css";
import type { SensitivityMeta, StatRow, StatSort } from "../lib/sensitivity";
import { formatStatValue, formatUnits, gainPct, hasValue, relativeValues, signedNumber, sortStats, statFlags, statNotes, STEP_LONG, STEP_SHORT } from "../lib/sensitivity";

interface Props {
  rows: StatRow[];
  sort?: StatSort;
  meta?: SensitivityMeta | null;
}

/** The 27 stats ranked by value: units per +1% DPS (fewest first = most valuable per unit), DPS / % gain of one step, relative bar, notes. */
export function StatTable({ rows, sort = "value", meta }: Props) {
  const ordered = sortStats(rows, sort);
  const rel = relativeValues(rows);
  const metaStep = new Map((meta?.stats ?? []).map((s) => [s.key, s.step]));
  return (
    <div className="sens-wrap">
      <table className="sens-table stat-table">
        <caption className="sr-only">Stat values, one step of each stat</caption>
        <thead>
          <tr>
            <th>#</th>
            <th>Stat</th>
            <th className="num">Current</th>
            <th className="num" title="Value after one step (the step is shown under it)">New (+step)</th>
            <th className="num" title="Units of the stat needed for +1% total DPS (1 / (% gain of one step - 100)). LOWER = fewer units needed = each unit is worth more. n/a = one step gives no gain.">
              Units per +1% DPS
            </th>
            <th className="num" title="Total DPS gained by one step of the stat">DPS gain</th>
            <th className="num" title="Gain in total DPS from one step">% gain</th>
            <th title="Gain of one step relative to the best stat">Relative value</th>
            <th>Notes</th>
          </tr>
        </thead>
        <tbody>
          {ordered.map((r, i) => {
            const valued = hasValue(r);
            const step = metaStep.get(r.key) ?? STEP_LONG[r.type] ?? "";
            const flags = statFlags(r, rows);
            return (
              <tr key={r.key} className={valued ? "" : "dim"} data-stat={r.key} title={statNotes(r).join("\n")}>
                <td className="rank">{valued ? i + 1 : "–"}</td>
                <td>
                  <span className="label-main">{r.label}</span>
                  {r.semantics && <span className="sub">{r.semantics}</span>}
                </td>
                <td className="num">{formatStatValue(r.current)}</td>
                <td className="num" title={step}>
                  {formatStatValue(r.new)}
                  <span className="sub">{STEP_SHORT[r.type] ?? ""}</span>
                </td>
                <td className="num" title={r.units_per_1pct !== null ? `${r.units_per_1pct}` : "one step gives no DPS gain"}>
                  <strong>{formatUnits(r.units_per_1pct)}</strong>
                </td>
                <td className={`num${r.dps_gain < 0 ? " neg" : ""}`}>{signedNumber(r.dps_gain)}</td>
                <td className={`num${r.pct_gain < 100 ? " neg" : ""}`} title={`${r.pct_gain}% of the baseline`}>
                  {gainPct(r.pct_gain)}
                </td>
                <td>
                  <span className="sens-bar" aria-hidden="true">
                    <span style={{ width: `${Math.round((rel.get(r.key) ?? 0) * 100)}%` }} />
                  </span>
                </td>
                <td>
                  <span className="info" aria-hidden="true">ⓘ </span>
                  <span className="sub" style={{ display: "inline" }}>{step}</span>
                  {flags.map((f) => (
                    <span key={f} className="chip warn">
                      {f}
                    </span>
                  ))}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
