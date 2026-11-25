import { useMemo, useState } from "react";
import "./sensitivity.css";
import "./companions.css";
import { useSensitivity, type SensStatus } from "../lib/useSensitivity";
import type { SensPart, SensitivityResult } from "../lib/sensitivity";
import { gainPct, signedNumber } from "../lib/sensitivity";
import { bestSummary, companionsOf, companionViews, LEVEL_OPTIONS, sensitivityExtras, setCompanionLevel, effectiveCompanion } from "../lib/companions";
import { setValue } from "../lib/schemaForm";
import type { ClassSchema, FormState } from "../types";
import { AboutTab, Unavailable } from "./TabNotes";

export const GAIN_UNAVAILABLE = "DPS numbers are not available for this class yet";

/** The inputs of the page's requests: the compute inputs + every companion's level. */
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
  /** opens the Help tab ("See Help" next to the not-available line) */
  onOpenHelp?: () => void;
}

/** Presentational part of the tab: everything given, nothing fetched (used by the render tests). */
export function CompanionsView({ schema, state, onState, result, status, supported, stale = false, pending = false, onRetry, onOpenCalculator, onOpenHelp }: ViewProps) {
  const [sortRank, setSortRank] = useState(false);
  const cs = companionsOf(schema, state);
  const { choice: effChoice } = effectiveCompanion(schema, state);
  const choiceField = schema.fields.find((f) => f.key === "companion_choice");
  const unsupported = !supported || status.unsupported;
  const part = unsupported ? null : (result?.companions ?? null);
  const views = useMemo(() => companionViews(schema, cs, effChoice, part, sortRank ? "rank" : "table"), [schema, cs, effChoice, part, sortRank]);
  const summary = bestSummary(views);
  const loading = status.loading || pending;

  return (
    <div className={`companions-tab${stale || pending ? " sens-stale" : ""}`} aria-busy={status.loading}>
      <section className="card" aria-label="Your legendary companions">
        <h2>Your legendary companions</h2>
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
          <Unavailable onOpenHelp={onOpenHelp} text={`${GAIN_UNAVAILABLE}; your levels are still saved.`} />
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
            ) : null}
          </>
        )}
        <div className="sens-controls">
          <label>
            <input type="checkbox" checked={sortRank} onChange={(e) => setSortRank(e.target.checked)} /> Sort by rank
          </label>
        </div>
        <div className="sens-wrap">
          <table className="sens-table companion-input-table">
            <caption className="sr-only">Your legendary companions</caption>
            <thead>
              <tr>
                <th scope="col">#</th>
                <th scope="col">Companion</th>
                <th scope="col">Level</th>
                <th scope="col" className="num">DPS it adds</th>
                <th scope="col" className="num">% DPS it adds</th>
                <th scope="col" aria-label="Use"></th>
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
                    <td className={`num${v.gain && v.gain.dps_gain < 0 ? " neg" : ""}`}>{unsupported ? <span className="sub">n/a</span> : v.gain ? signedNumber(v.gain.dps_gain) : unlocked ? "…" : "–"}</td>
                    <td className="num">{unsupported ? <span className="sub">n/a</span> : v.gain ? gainPct(v.gain.pct_gain) : unlocked ? "…" : "–"}</td>
                    <td>
                      {unlocked && !v.chosen && choiceField && (
                        <button type="button" className="link" onClick={() => onState(setValue(state, choiceField, v.name))}>
                          use in {state.contentType}
                        </button>
                      )}
                      {v.chosen && choiceField && (
                        <button type="button" className="link" onClick={() => onState(setValue(state, choiceField, "None"))}>
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
      </section>

      <AboutTab>
        <ul>
          <li>
            The main form lets you pick only from the legendary companions you set here; the companion it summons is chosen per content type ({state.contentType}: <strong>{effChoice === "None" ? "none" : effChoice}</strong>).
            Damage multiplier by level: 60/64/68/72/75/78/81/84/87/90% (90% from Lv10 on), +25% Final Damage at Lv5, Lv8 and Lv10.
          </li>
          <li>
            &quot;DPS it adds&quot; compares the companion with having none, in the current content type. Status Effect Damage and Companion Summoning Time Increase % are stats, so they stay on the Calculator
            {onOpenCalculator && (
              <>
                {" "}
                <button type="button" className="link" onClick={onOpenCalculator}>
                  (back to the Calculator)
                </button>
              </>
            )}
            .
          </li>
          <li>
            The companion stays for 30 s x (1 + total/100) and comes back 90 s after it was summoned. Its skills fire on a fixed cast schedule, so DPS grows in small steps with summoning time and{" "}
            <strong>jumps at thresholds</strong> where one more stun / skill cast fits into the window.
          </li>
        </ul>
      </AboutTab>
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
  /** opens the Help tab ("See Help" next to the not-available line) */
  onOpenHelp?: () => void;
}

/** The "Companions" tab: levels of the 16 companions and what each is worth.
 *  The request (`companions`) is sent only while the tab is visible, debounced like the Stat values tab. */
export function CompanionsPanel({ classId, schema, state, onState, inputs, active, supported, onOpenCalculator, onOpenHelp }: Props) {
  const on = active && supported !== false;
  const reqInputs = useMemo(() => companionRequestInputs(schema, state, inputs), [schema, state, inputs]);
  const wanted = useMemo<SensPart[]>(() => ["companions"], []);
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
      onOpenHelp={onOpenHelp}
    />
  );
}
