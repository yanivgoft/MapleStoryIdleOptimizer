import "./sensitivity.css";
import type { ArtifactRow } from "../lib/sensitivity";
import { equipNote, gainPct, rankEquip, signedNumber } from "../lib/sensitivity";

interface Props {
  rows: ArtifactRow[];
  /** show only the first N entries (default: all) */
  limit?: number;
  /** list artifacts that are not unlocked (greyed, unranked; their numbers are what-ifs at star 0) - default true */
  showLocked?: boolean;
  /** list unlocked artifacts without any DPS effect in the model (greyed, with their reason) - default true */
  showNoEffect?: boolean;
  /** caption above the table */
  title?: string;
}

/**
 * Equip-toggle ranking of the Sensitivity result (`SensitivityResult.artifacts.rows`): what each artifact is worth in total DPS, best first.  Equipped ones are
 * marked (their gain is the value of keeping them: same % in both directions), no-DPS-effect artifacts and locked ones are greyed.  Self-contained (imports its own
 * stylesheet), so the Artifacts tab can reuse it as `<EquipRanking rows={sensitivity.artifacts.rows} />`.
 */
export function EquipRanking({ rows, limit, showLocked = true, showNoEffect = true, title }: Props) {
  let entries = rankEquip(rows, { includeLocked: showLocked, includeNoEffect: showNoEffect });
  if (limit !== undefined) entries = entries.slice(0, limit);
  const bestPp = Math.max(0, ...rows.filter((r) => r.unlocked && !r.no_dps_effect).map((r) => r.pct_gain - 100));
  return (
    <div className="sens-wrap equip-ranking">
      <table className="sens-table">
        {title && <caption className="sr-only">{title}</caption>}
        <thead>
          <tr>
            <th>#</th>
            <th>Artifact</th>
            <th className="num" title="Total DPS gained by equipping it (what you would lose by removing it when equipped)">DPS gain</th>
            <th className="num" title="Gain in total DPS; the same percentage whichever direction you test from">% gain</th>
            <th>Relative</th>
          </tr>
        </thead>
        <tbody>
          {entries.map(({ group, row }) => {
            const dim = group !== "ranked";
            const pp = row.pct_gain - 100;
            const frac = !dim && bestPp > 0 && pp > 0 ? pp / bestPp : 0;
            return (
              <tr key={row.key} className={`${dim ? "dim" : ""}${row.equipped ? " current" : ""}`} data-group={group} title={equipNote(row) || undefined}>
                <td className="rank">{group === "ranked" ? row.rank_position : "–"}</td>
                <td>
                  <span className="label-main">{row.label}</span> <span className="chip">{row.rank}</span>
                  {row.equipped && <span className="chip ok">equipped</span>}
                  {row.baked_into_inputs && <span className="chip" title="its stat is typed into Inputs; the gain is a what-if">in Inputs</span>}
                  {group === "no_effect" && <span className="sub">no DPS effect: {row.reason || "not used by the model"}</span>}
                  {group === "locked" && <span className="sub">not unlocked</span>}
                </td>
                <td className={`num${row.dps_gain < 0 ? " neg" : ""}`}>{group === "no_effect" ? "–" : signedNumber(row.dps_gain)}</td>
                <td className={`num${pp < 0 ? " neg" : ""}`}>{group === "no_effect" ? "–" : gainPct(row.pct_gain)}</td>
                <td>
                  {!dim && (
                    <span className="sens-bar" aria-hidden="true">
                      <span style={{ width: `${Math.round(frac * 100)}%` }} />
                    </span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
