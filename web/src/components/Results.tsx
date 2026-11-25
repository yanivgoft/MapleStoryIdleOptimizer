import { useMemo } from "react";
import type { ComputeResult } from "../types";
import { BarChart, type Bar } from "./BarChart";
import { formatNumber, formatPercent } from "../lib/format";

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
  const ofTotal = (v: number) => (result.total_dps > 0 ? v / result.total_dps : null);
  const branchShare = (v: number, branchTotal: number) => (branchTotal > 0 ? formatPercent(v / branchTotal) : "–");
  const derivedRows = Object.entries(result.derived).filter(([k]) => !HIDDEN_DERIVED.has(k));

  return (
    <section className={`results${busy || stale ? " busy" : ""}`} aria-busy={busy}>
      <span className="sr-only" aria-live="polite" role="status">
        Total DPS updated
      </span>
      <div className="total card">
        <div className="label">
          Total DPS
          {busy && <span className="updating"> Updating...</span>}
        </div>
        <div className="big">{formatNumber(result.total_dps)}</div>
        <div className="sub">
          {result.engine_on && (
            <span className="pill on" title="Buffs, stuns and KO phases are placed second by second over the fight">
              Detailed simulation
            </span>
          )}
          <span>Player {formatPercent(ofTotal(result.player_dps), 0)}</span>
          {c && c.dps > 0 && <span>{hasCompanion ? "Companion" : "Stun effect"} {formatPercent(ofTotal(c.dps), 0)}</span>}
        </div>
      </div>
      <div className="split">
        <div className="card">
          <div className="label">Boss only (% of Total DPS)</div>
          <div className="mid">{formatPercent(ofTotal(result.boss_dps), 0)}</div>
        </div>
        <div className="card">
          <div className="label">Normal monsters only (% of Total DPS)</div>
          <div className="mid">{result.normal_dps > 0 ? formatPercent(ofTotal(result.normal_dps), 0) : result.derived.monster_type === "pvp" ? "n/a (PvP)" : "n/a (boss fight)"}</div>
        </div>
      </div>

      <div className="card">
        <h2>Share of Total DPS by skill</h2>
        <BarChart bars={bars} title="Share of Total DPS by skill, highest first" />
      </div>

      <div className="card">
        <h2>Breakdown</h2>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">Skill</th>
                <th scope="col" className="num">Share</th>
                <th scope="col" className="num">Boss share</th>
                <th scope="col" className="num">Normal share</th>
              </tr>
            </thead>
            <tbody>
              {sortedSkills.map((s) => (
                <tr key={s.key} className={s.unlocked ? "" : "locked"}>
                  <th scope="row">
                    {s.name}
                    {!s.unlocked && <span className="tag">locked</span>}
                  </th>
                  <td className="num">{formatPercent(s.share)}</td>
                  <td className="num">{branchShare(s.boss_dps, result.boss_dps)}</td>
                  <td className="num">{branchShare(s.normal_dps, result.normal_dps)}</td>
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
                  <td className="num">{formatPercent(c.share)}</td>
                  <td className="num">{branchShare(c.boss_dps, result.boss_dps)}</td>
                  <td className="num">{branchShare(c.normal_dps, result.normal_dps)}</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        {c && hasCompanion && (
          <p className="note">
            Companion summoned every {formatNumber(c.summon_time_s)}s for {formatNumber(c.window_s)}s.
          </p>
        )}
      </div>

      <details className="card">
        <summary>Advanced: calculation details</summary>
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
