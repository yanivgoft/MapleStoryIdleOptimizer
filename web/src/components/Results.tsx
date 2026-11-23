import { useMemo } from "react";
import type { ComputeResult } from "../types";
import { BarChart, type Bar } from "./BarChart";
import { formatFull, formatNumber, formatPercent } from "../lib/format";

const HIDDEN_DERIVED = new Set(["monster_type", "chapter", "stage", "breakthrough_normal_weight_pct", "breakthrough_stage_index", "monster_defense", "fight_duration"]);

function derivedText(v: unknown): string {
  if (typeof v === "number") return formatNumber(v, 4);
  if (typeof v === "boolean") return v ? "yes" : "no";
  if (v && typeof v === "object") {
    return Object.entries(v as Record<string, unknown>)
      .map(([k, x]) => `${k} ${typeof x === "number" ? formatNumber(x, 4) : String(x)}`)
      .join(" · ");
  }
  return v === null || v === undefined ? "–" : String(v);
}

function titleCase(key: string) {
  return key.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
}

export function Results({ result, busy, stale }: { result: ComputeResult; busy: boolean; stale: boolean }) {
  // No companion chosen: the block can still carry a stun effect (e.g. Hero's Rush lengthening the boss phase); it is not a companion.
  const c = result.companion;
  const hasCompanion = !!c && c.choice !== "None";
  const bars = useMemo<Bar[]>(() => {
    const rows: Bar[] = result.skills.filter((s) => s.unlocked && s.dps > 0).map((s) => ({ label: s.name, value: s.dps, share: s.share }));
    const comp = result.companion;
    if (comp && comp.dps > 0) {
      rows.push({ label: comp.choice === "None" ? "Stun effect" : `Companion: ${comp.choice}`, value: comp.dps, share: comp.share, highlight: true });
    }
    return rows.sort((a, b) => b.value - a.value);
  }, [result]);

  const sortedSkills = useMemo(() => [...result.skills].sort((a, b) => b.dps - a.dps), [result]);
  const derivedRows = Object.entries(result.derived).filter(([k]) => !HIDDEN_DERIVED.has(k));

  return (
    <section className={`results${busy || stale ? " busy" : ""}`} aria-live="polite" aria-busy={busy}>
      <div className="total card">
        <div className="label">Total DPS</div>
        <div className="big" title={formatFull(result.total_dps)}>
          {formatNumber(result.total_dps)}
        </div>
        <div className="sub">
          <span className={`pill ${result.engine_on ? "on" : "off"}`} title="Status Effect / KO timeline engine (time-resolved buff, stun and KO windows)">
            Timeline engine: {result.engine_on ? "on" : "off"}
          </span>
          <span>Player {formatNumber(result.player_dps)}</span>
          {c && c.dps > 0 && <span>{hasCompanion ? "Companion" : "Stun effect"} {formatNumber(c.dps)}</span>}
        </div>
      </div>
      <div className="split">
        <div className="card">
          <div className="label">Boss only</div>
          <div className="mid" title={formatFull(result.boss_dps)}>{formatNumber(result.boss_dps)}</div>
        </div>
        <div className="card">
          <div className="label">Normal monsters only</div>
          <div className="mid" title={formatFull(result.normal_dps)}>{result.normal_dps > 0 ? formatNumber(result.normal_dps) : "n/a"}</div>
        </div>
      </div>

      <div className="card">
        <h2>DPS by skill</h2>
        <BarChart bars={bars} title="DPS by skill, highest first" />
      </div>

      <div className="card">
        <h2>Breakdown</h2>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">Skill</th>
                <th scope="col" className="num">DPS</th>
                <th scope="col" className="num">Share</th>
                <th scope="col" className="num">Boss</th>
                <th scope="col" className="num">Normal</th>
              </tr>
            </thead>
            <tbody>
              {sortedSkills.map((s) => (
                <tr key={s.key} className={s.unlocked ? "" : "locked"}>
                  <th scope="row">
                    {s.name}
                    {!s.unlocked && <span className="tag">locked</span>}
                  </th>
                  <td className="num" title={formatFull(s.dps)}>{formatNumber(s.dps)}</td>
                  <td className="num">{formatPercent(s.share)}</td>
                  <td className="num">{formatNumber(s.boss_dps)}</td>
                  <td className="num">{formatNumber(s.normal_dps)}</td>
                </tr>
              ))}
              {c && (hasCompanion || c.dps > 0) && (
                <tr className="companion">
                  <th scope="row">
                    {hasCompanion ? (
                      <>
                        Companion: {c.choice} <span className="tag">Lv {c.level}</span>
                      </>
                    ) : (
                      "Stun effect (no companion)"
                    )}
                  </th>
                  <td className="num" title={formatFull(c.dps)}>{formatNumber(c.dps)}</td>
                  <td className="num">{formatPercent(c.share)}</td>
                  <td className="num">{formatNumber(c.boss_dps)}</td>
                  <td className="num">{formatNumber(c.normal_dps)}</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        {c && hasCompanion && (
          <p className="note">
            Companion summoned every {formatNumber(c.summon_time_s)}s for {formatNumber(c.window_s)}s; it adds {formatNumber(c.uplift)} damage uplift to the
            player's own skills over the fight.
          </p>
        )}
      </div>

      <details className="card">
        <summary>Derived values</summary>
        <dl className="derived">
          {derivedRows.map(([k, v]) => (
            <div key={k}>
              <dt>{titleCase(k)}</dt>
              <dd>{derivedText(v)}</dd>
            </div>
          ))}
        </dl>
      </details>
    </section>
  );
}
