import { useMemo, useState } from "react";
import "./sensitivity.css";
import "./companions.css";
import { useSensitivity, type SensStatus } from "../lib/useSensitivity";
import type { SensPart, SensitivityResult } from "../lib/sensitivity";
import { gainPct, sig, signedNumber, signedPct } from "../lib/sensitivity";
import { formatNumber } from "../lib/format";
import {
  bestSummary, COMPANION_LINES_STAT, companionsOf, companionViews, cubesCompanionLinesPct, LEVEL_OPTIONS, sensitivityExtras, setCompanionLevel,
  setPotentialLinesPct, summonViews, effectiveCompanion,
} from "../lib/companions";
import { setValue } from "../lib/schemaForm";
import type { ClassSchema, FormState } from "../types";
import { NumInput } from "./NumInput";

export const GAIN_UNAVAILABLE = "gain: not available for this class yet";

const frac = (v: number | null) => (v === null ? "–" : signedPct(v * 100));

/** The inputs of the page's requests: the compute inputs + every companion's level + the boots lines already inside the summoning-time input. */
export function companionRequestInputs(schema: ClassSchema, state: FormState, inputs: Record<string, unknown> | null): Record<string, unknown> | null {
  return inputs ? { ...inputs, ...sensitivityExtras(schema, state) } : null;
}

interface ViewProps {
  schema: ClassSchema;
  state: FormState;
  onState: (s: FormState) => void;
  result: SensitivityResult | null;
  status: SensStatus;
  supported: boolean; // class has stat values (the gain columns)
  stale?: boolean;
  pending?: boolean;
  onRetry?: () => void;
  onOpenCalculator?: () => void;
}

/** Presentational part of the tab: everything given, nothing fetched (used by the render tests). */
export function CompanionsView({ schema, state, onState, result, status, supported, stale = false, pending = false, onRetry, onOpenCalculator }: ViewProps) {
  const [sortRank, setSortRank] = useState(false);
  const cs = companionsOf(schema, state);
  const { choice: effChoice } = effectiveCompanion(schema, state);
  const choiceField = schema.fields.find((f) => f.key === "companion_choice");
  const unsupported = !supported || status.unsupported;
  const part = unsupported ? null : (result?.companions ?? null);
  const views = useMemo(() => companionViews(schema, cs, effChoice, part, sortRank ? "rank" : "table"), [schema, cs, effChoice, part, sortRank]);
  const summary = bestSummary(views);
  const owned = views.filter((v) => v.level >= 1).length;
  const loading = status.loading || pending;
  const lines = cs.potentialLinesPct;
  const cubesLines = cubesCompanionLinesPct(state.cubes);
  const summon = result?.summon_time;
  const sviews = useMemo(
    () => (summon ? summonViews(summon.rows, result?.baseline_total ?? null, result?.companions?.current_companion_dps ?? null, lines) : []),
    [summon, result, lines],
  );

  return (
    <div className={`companions-tab${stale || pending ? " sens-stale" : ""}`} aria-busy={status.loading}>
      <section className="card" aria-label="Your companions">
        <h2>Your companions</h2>
        <p className="note">
          Set the level of every companion you own (Not unlocked, or 1-18). The main form lets you pick only from these; its summoned companion is chosen per content type
          ({state.contentType}: <strong>{effChoice === "None" ? "none" : effChoice}</strong>). Damage multiplier by level: 60/64/68/72/75/78/81/84/87/90% (90% from Lv10 on), +25% Final
          Damage at Lv5, Lv8 and Lv10.
        </p>
        {status.error && !unsupported && (
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
        {unsupported ? (
          <p className="empty" role="status">
            {GAIN_UNAVAILABLE}. The levels are still saved with your profile and used by the Calculator.
          </p>
        ) : (
          <>
            {loading && (
              <div className="sens-loading" role="status">
                <span className="spinner" aria-hidden="true" /> {pending && !status.loading ? "Waiting for the inputs to settle..." : "Comparing companions (about half a second)..."}
              </div>
            )}
            {summary ? (
              <p className="note" data-testid="best-summary">
                Best companion for {state.contentType}: <strong>{summary.best.name}</strong> at level {summary.best.level} ({gainPct(summary.best.gain!.pct_gain)} of Total DPS without a companion)
                {summary.chosen && summary.chosen.name !== summary.best.name && summary.chosen.gain
                  ? `; you use ${summary.chosen.name} (rank ${summary.chosen.gain.rank_position} of ${summary.owned}, ${gainPct(summary.chosen.gain.pct_gain)}).`
                  : summary.chosen
                    ? "; that is the one you use."
                    : effChoice === "None"
                      ? "; you have none chosen."
                      : "."}
              </p>
            ) : (
              owned === 0 && <p className="note">Unlock at least one companion below to see what each is worth.</p>
            )}
          </>
        )}
        <div className="sens-controls">
          <label>
            <input type="checkbox" checked={sortRank} onChange={(e) => setSortRank(e.target.checked)} /> Sort by rank
          </label>
        </div>
        <div className="sens-wrap">
          <table className="sens-table companion-input-table">
            <caption className="sr-only">Companion levels and what each is worth</caption>
            <thead>
              <tr>
                <th title="Rank among the companions you own, best DPS gain first, in this content type">#</th>
                <th>Companion</th>
                <th>Level</th>
                <th className="num" title="Level the engine uses (0 = not unlocked)">Resolved</th>
                <th className="num" title="Total DPS this companion adds in the current content type, against no companion">DPS gain vs no companion</th>
                <th className="num" title="% of Total DPS without a companion gained">% of Total DPS (without a companion)</th>
                <th aria-label="Use"></th>
              </tr>
            </thead>
            <tbody>
              {views.map((v) => {
                const unlocked = v.level >= 1;
                return (
                  <tr key={v.name} className={`${unlocked ? "" : "dim"}${v.best ? " best" : ""}${v.chosen ? " chosen" : ""}`} data-companion={v.name} data-level={v.level}>
                    <td className="rank">{v.gain ? v.gain.rank_position : "–"}</td>
                    <td>
                      <span className="label-main">{v.name}</span>
                      {v.chosen && <span className="chip ok">chosen</span>}
                      {v.best && <span className="chip warn">best for {state.contentType}</span>}
                    </td>
                    <td>
                      <select
                        className="companion-select"
                        aria-label={`${v.name} level`}
                        value={v.level}
                        onChange={(e) => onState(setCompanionLevel(state, schema, v.name, Number(e.target.value)))}
                      >
                        {LEVEL_OPTIONS.map((o) => (
                          <option key={o.value} value={o.value}>
                            {o.label}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="num">{v.level}</td>
                    <td className={`num${v.gain && v.gain.dps_gain < 0 ? " neg" : ""}`}>{unsupported ? <span className="sub">n/a</span> : v.gain ? signedNumber(v.gain.dps_gain) : unlocked ? "…" : "–"}</td>
                    <td className="num">{unsupported ? <span className="sub">n/a</span> : v.gain ? gainPct(v.gain.pct_gain) : unlocked ? "…" : "–"}</td>
                    <td>
                      {unlocked && !v.chosen && choiceField && (
                        <button type="button" className="link" onClick={() => onState(setValue(state, choiceField, v.name))} title={`Summon ${v.name} in ${state.contentType}`}>
                          use in {state.contentType}
                        </button>
                      )}
                      {v.chosen && choiceField && (
                        <button type="button" className="link" onClick={() => onState(setValue(state, choiceField, "None"))} title="Summon no companion in this content type">
                          use none
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {onOpenCalculator && (
          <p className="note">
            <button type="button" className="link" onClick={onOpenCalculator}>
              Back to the Calculator
            </button>{" "}
            (Status Effect Damage and Companion Summoning Time Increase % stay there: they are stats).
          </p>
        )}
      </section>

      <section className="card" aria-label="Summoning Time Increase potential lines">
        <h2>Summoning Time Increase potential lines</h2>
        <p className="note">
          What each total of boots potential lines (Companion Summoning Time Increase %) would be worth for the companion you summon in {state.contentType}
          {effChoice !== "None" && (
            <>
              {" "}
              (<strong>{effChoice}</strong> Lv {effectiveCompanion(schema, state).level})
            </>
          )}
          . A potential&apos;s lines roll at the item&apos;s rarity or the one below, so 12% and 5% never share a potential; the table lists every total that can happen.
        </p>
        <div className="lines-input">
          <label htmlFor="companion-lines-pct">Lines already counted in your Summoning Time Increase %</label>
          <NumInput
            value={lines || null}
            onChange={(v) => onState(setPotentialLinesPct(state, schema, v))}
            label="Boots lines already counted in the Summoning Time Increase %"
            min={0}
            max={10000}
            placeholder="0"
          />
          <span>%</span>
          {cubesLines > 0 && cubesLines !== lines && (
            <button type="button" className="link" onClick={() => onState(setPotentialLinesPct(state, schema, cubesLines))}>
              use {sig(cubesLines)}% from the lines on the Cubes tab ({COMPANION_LINES_STAT})
            </button>
          )}
        </div>
        <p className="note">
          The table measures every option against having <em>none</em> of these lines: enter the part of the Calculator&apos;s Summoning Time Increase % that comes from boots
          potential lines you could re-roll (0 = all of it is permanent). The row matching your entry is marked.
        </p>
        <ul className="explain">
          <li>
            The companion stays for 30 s x (1 + total/100) and comes back 90 s after it was summoned. Its skills fire on a fixed cast schedule, so DPS grows in small steps with
            summoning time and <strong>jumps at thresholds</strong> where one more stun / skill cast fits into the window.
          </li>
          <li>
            Example: Blaze Wizard&apos;s 3rd stun cast needs a total of +13.667%, so +13% (a single 8+5 potential) gains almost nothing over +12% while +15% gains a lot more. Rows
            marked <span className="chip warn">step</span> are where the table itself shows such a jump.
          </li>
          {summon?.boss_phase_content && (
            <li>
              In this content (Breakthrough / Hero Dungeon) a longer stun also lengthens the boss phase: the boss-phase columns split the effect into the average DPS over the
              longer phase, the time factor and the total damage (DPS x time).
            </li>
          )}
        </ul>
        {unsupported ? (
          <p className="empty" role="status">
            {GAIN_UNAVAILABLE}.
          </p>
        ) : effChoice === "None" ? (
          <p className="empty">Choose a companion for {state.contentType} on the Calculator (or &quot;use in {state.contentType}&quot; above) to price the lines.</p>
        ) : !summon ? (
          <p className="empty">{status.error ? "Not loaded." : loading ? "Loading..." : "Not loaded yet."}</p>
        ) : (
          <div className="sens-wrap">
            <table className="sens-table summon-lines-table">
              <caption className="sr-only">Summoning Time Increase potential lines</caption>
              <thead>
                <tr>
                  <th className="num" title="Total % from the lines">Total % from lines</th>
                  <th>Possible line combinations</th>
                  <th className="num">Window (s)</th>
                  <th className="num" title="Total DPS gain vs none of these lines">DPS gain</th>
                  <th className="num" title="% DPS gain vs none of these lines">% gain</th>
                  <th className="num" title="Total DPS compared with your current setup">DPS vs current</th>
                  {summon.boss_phase_content && (
                    <>
                      <th className="num" title="Boss phase: average DPS change over the longer phase">Boss: avg DPS</th>
                      <th className="num" title="Boss phase: time factor">Boss: time x</th>
                      <th className="num" title="Boss phase: total damage change (DPS x time)">Boss: total damage</th>
                    </>
                  )}
                </tr>
              </thead>
              <tbody>
                {sviews.map((v) => (
                  <tr key={v.row.total_pct} className={v.current ? "current" : ""} data-total={v.row.total_pct}>
                    <td className="num">
                      {v.row.total_pct === 0 ? "none" : `+${v.row.total_pct}%`}
                      {v.current && <span className="chip ok">yours</span>}
                      {v.step && <span className="chip warn" title="DPS rises much faster up to this total than elsewhere: another cast / stun fits into the companion's window">step</span>}
                    </td>
                    <td className="combos">{v.combos.length ? v.combos.join("  |  ") : "no lines"}</td>
                    <td className="num">{sig(v.row.window_s, 4)}</td>
                    <td className={`num${v.gain !== null && v.gain < 0 ? " neg" : ""}`}>{v.gain === null ? "–" : v.row.total_pct === 0 ? "0" : signedNumber(v.gain)}</td>
                    <td className="num">{frac(v.row.weighted_dps_change)}</td>
                    <td className={`num${v.vsCurrent !== null && v.vsCurrent < 0 ? " neg" : ""}`}>{v.vsCurrent === null ? "–" : signedNumber(v.vsCurrent)}</td>
                    {summon.boss_phase_content && (
                      <>
                        <td className="num">{frac(v.row.avg_boss_dps_change)}</td>
                        <td className="num">{v.row.boss_phase_time_factor === null ? "–" : sig(v.row.boss_phase_time_factor, 4)}</td>
                        <td className="num">{frac(v.row.boss_damage_change)}</td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {summon && result?.companions && (
          <p className="hint">Companion DPS now: {formatNumber(result.companions.current_companion_dps)}. "DPS gain" is measured against none of these lines, "DPS vs current" against your setup now.</p>
        )}
      </section>
    </div>
  );
}

interface Props {
  classId: string | null;
  schema: ClassSchema;
  state: FormState;
  onState: (s: FormState) => void;
  /** the compute inputs (`buildInputs`), without the companion extras */
  inputs: Record<string, unknown> | null;
  active: boolean;
  /** GET /api/classes `status.stat_values`: `false` shows levels only ("gain: not available for this class yet") without asking the API */
  supported?: boolean;
  onOpenCalculator?: () => void;
}

/** The "Companions" tab (the workbook's CompanionsInput sheet): levels of the 16 companions, what each is worth and the summoning-time potential-lines table.
 *  Requests (`companions`, and `summon_time` once a companion is chosen) only while visible, debounced like the Stat values tab. */
export function CompanionsPanel({ classId, schema, state, onState, inputs, active, supported, onOpenCalculator }: Props) {
  const on = active && supported !== false;
  const reqInputs = useMemo(() => companionRequestInputs(schema, state, inputs), [schema, state, inputs]);
  const choice = effectiveCompanion(schema, state).choice;
  const wanted = useMemo<SensPart[]>(() => (choice === "None" ? ["companions"] : ["companions", "summon_time"]), [choice]);
  const { result, status, stale, pending, retry } = useSensitivity({ classId, inputs: reqInputs, active: on, wanted });
  return (
    <CompanionsView
      schema={schema}
      state={state}
      onState={onState}
      result={result}
      status={status}
      supported={supported !== false}
      stale={stale}
      pending={pending}
      onRetry={retry}
      onOpenCalculator={onOpenCalculator}
    />
  );
}
