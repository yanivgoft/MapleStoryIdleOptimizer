import { useEffect, useMemo, useRef, useState } from "react";
import "./sensitivity.css";
import "./cubes.css";
import { api } from "../api";
import {
  CUBE_SORTS,
  DEFAULT_MILESTONE,
  NONE_STAT,
  SELECTABLE_MILESTONES,
  cubesCsv,
  evAt,
  evPctAt,
  formatCubes,
  formatEvPct,
  gearKey,
  gearPayload,
  getRow,
  isConfigured,
  linesText,
  pityCap,
  NOT_ROLLABLE_ON_SLOT,
  groupByPotentialType,
  pityHint,
  potentialExplainer,
  rankRows,
  rarityLabel,
  rowsToCalculate,
  setLine,
  setRow,
  slotLabel,
  statChoices,
  statOptions,
  worthRolling,
  type CubeRow,
  type CubeSort,
  type CubesMeta,
  type CubesState,
  type GearRowState,
} from "../lib/cubes";
import { CubesRunner, IDLE_RUN, type RunState } from "../lib/cubesRunner";
import { formatFull, formatNumber } from "../lib/format";
import type { RequestStatus } from "../lib/liveRequest";
import { NumInput } from "./NumInput";

export const CUBES_UNSUPPORTED_TEXT = "The cube optimizer is not available for this class yet.";

function StatusBanner({ status, onRetry }: { status: RequestStatus; onRetry?: () => void }) {
  if (!status.error) return null;
  return (
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
  );
}

/** One stat dropdown shared by the three editors: "(none)" and the stats in `primary` (what that piece of equipment can roll).  A current value outside `primary` stays
 *  selectable as ONE entry, flagged with a warning when `notRollable` says why (cubes, artifact lines); without `notRollable` it is shown plain (Equipment compare). */
export function StatSelect({
  value,
  onChange,
  label,
  primary,
  notRollable,
  none = NONE_STAT,
}: {
  value: string;
  onChange: (s: string) => void;
  label: string;
  primary: string[];
  notRollable?: string;
  none?: string;
}) {
  const choices = statChoices(primary, value, notRollable, none);
  const flagged = choices.some((c) => c.warn);
  return (
    <select
      aria-label={label}
      value={value}
      className={flagged ? "warn" : undefined}
      title={
        flagged
          ? `${value} is ${notRollable}. It came from an old profile or an import; it is kept so nothing is lost. Pick another stat to replace it.`
          : undefined
      }
      onChange={(e) => onChange(e.target.value)}
    >
      {choices.map((c) => (
        <option key={c.value} value={c.value} data-warn={c.warn ? "true" : undefined}>
          {c.label}
        </option>
      ))}
    </select>
  );
}

interface EditorProps {
  meta: CubesMeta;
  state: CubesState | undefined;
  onState: (s: CubesState) => void;
}

/** The PotentialCubes sheet: 15 slots x {Potential, Bonus Potential}, rarity + pity + 3 lines each. */
export function GearEditor({ meta, state, onState }: EditorProps) {
  const update = (slot: string, type: string, row: GearRowState) => onState(setRow(state, slot, type, row));
  return (
    <div className="table-wrap">
      <table className="cube-table" aria-label="Current potential lines">
        <thead>
          <tr>
            <th>Slot</th>
            <th>Track</th>
            <th>Rarity</th>
            <th>Pity</th>
            <th>Line 1</th>
            <th>Line 2</th>
            <th>Line 3</th>
          </tr>
        </thead>
        <tbody>
          {meta.slots.flatMap((s) => {
            const own = statOptions(meta, s.key);
            return meta.potential_types.map((t, ti) => {
              const row = getRow(state, s.key, t);
              const cap = pityCap(meta, t, row.rarity);
              const id = `${s.label} ${t}`;
              return (
                <tr key={gearKey(s.key, t)} data-row={gearKey(s.key, t)} className={isConfigured(row) ? "cfg" : undefined}>
                  <td className="slot">{ti === 0 ? s.label : ""}</td>
                  <td>{t}</td>
                  <td>
                    <select aria-label={`${id} rarity`} value={row.rarity} onChange={(e) => update(s.key, t, { ...row, rarity: e.target.value })}>
                      {meta.rarities.map((r) => (
                        <option key={r.key} value={r.key}>
                          {r.label}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <span className="pity">
                      <NumInput
                        value={row.pity}
                        whole
                        max={cap > 0 ? cap - 1 : 0}
                        disabled={cap === 0}
                        label={`${id} pity count`}
                        placeholder="0"
                        onChange={(v) => update(s.key, t, { ...row, pity: v })}
                      />
                      <span className="cap">{pityHint(meta, t, row.rarity)}</span>
                    </span>
                  </td>
                  {row.lines.map((l, i) => (
                    <td key={i}>
                      <span className="line">
                        <StatSelect
                          value={l.stat}
                          label={`${id} line ${i + 1} stat`}
                          primary={own}
                          notRollable={NOT_ROLLABLE_ON_SLOT}
                          onChange={(stat) =>
                            update(
                              s.key,
                              t,
                              setLine(row, i, {
                                stat,
                                value: stat === NONE_STAT ? null : l.value,
                              }),
                            )
                          }
                        />
                        <NumInput
                          value={l.value}
                          label={`${id} line ${i + 1} value`}
                          disabled={l.stat === NONE_STAT}
                          onChange={(v) => update(s.key, t, setLine(row, i, { value: v }))}
                        />
                      </span>
                    </td>
                  ))}
                </tr>
              );
            });
          })}
        </tbody>
      </table>
    </div>
  );
}

/** Ranked recommendations (pure presentation of rows already received). */
export function CubeResults({
  rows,
  meta,
  milestone,
  sort,
  baseline,
}: {
  rows: CubeRow[];
  meta: CubesMeta | null;
  milestone: number;
  sort: CubeSort;
  baseline: number | null;
}) {
  const groups = useMemo(() => groupByPotentialType(rankRows(rows, sort, milestone, meta)), [rows, sort, milestone, meta]);
  if (!rows.length) return null;
  return (
    <div className="table-wrap">
      <table className="sens-table" aria-label="Cube recommendations">
        <thead>
          <tr>
            <th>#</th>
            <th>Slot</th>
            <th>Current</th>
            <th className="num" title="What the lines you entered are worth now, in % of Total DPS">
              Now
            </th>
            <th className="num" title="Smallest number of cubes after which the expected value (keeping the best result so far) is positive">
              Cubes to positive EV
            </th>
            <th className="num" title="Cubes needed for a 50% chance that at least one reroll beats your current lines">
              N for 50%
            </th>
            <th className="num" title="... and for a 75% chance">
              N for 75%
            </th>
            <th className="num" title={`Expected DPS gained by spending up to ${milestone} cubes, optimally stopping`}>
              EV @ {milestone} cubes
            </th>
            <th title="A plain rule on the expected gain at the chosen cube count; see the note below the table">Worth rolling?</th>
          </tr>
        </thead>
        {groups.map((g) => (
          <tbody key={g.type} data-potential-type={g.type}>
            <tr className="group-row">
              <th colSpan={9} scope="colgroup">
                {g.type}{" "}
                <span className="sub">
                  {g.rows.length} {g.rows.length === 1 ? "slot" : "slots"}, ranked among themselves
                </span>
              </th>
            </tr>
            {g.rows.map((r, i) => {
              const w = worthRolling(r, milestone);
              return (
                <tr key={`${r.slot}|${r.potential_type}`} data-row={`${r.slot}|${r.potential_type}`} data-verdict={w.verdict}>
                  <td className="rank">{i + 1}</td>
                  <td>
                    <span className="label-main">{slotLabel(meta, r.slot)}</span>
                    <span className="sub">{r.potential_type}</span>
                  </td>
                  <td>
                    {rarityLabel(meta, r.rarity)}{" "}
                    <span className="sub">
                      pity {Math.round(r.pity)} | {linesText(r)}
                    </span>
                  </td>
                  <td className="num" title={baseline ? `${formatFull(r.current_value)} DPS` : undefined}>
                    {formatEvPct(r.current_value_pct)}
                  </td>
                  <td className="num">{r.smallest_n === null ? "never" : r.smallest_n}</td>
                  <td className="num">{formatCubes(r.n_for_50pct, meta?.max_cubes)}</td>
                  <td className="num">{formatCubes(r.n_for_75pct, meta?.max_cubes)}</td>
                  <td className="num" title={`${formatFull(evAt(r, milestone))} DPS`}>
                    {formatEvPct(evPctAt(r, milestone))}
                    <span className="sub">{formatNumber(evAt(r, milestone))}</span>
                  </td>
                  <td>
                    <span className={`verdict ${w.verdict}`} title={w.why}>
                      {w.label}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        ))}
      </table>
    </div>
  );
}

interface ViewProps {
  meta: CubesMeta | null;
  metaStatus: RequestStatus;
  state: CubesState | undefined;
  onState: (s: CubesState) => void;
  run: RunState;
  milestone: number;
  onMilestone: (n: number) => void;
  sort: CubeSort;
  onSort: (s: CubeSort) => void;
  includeBlank: boolean;
  onIncludeBlank: (b: boolean) => void;
  outdated: boolean;
  onCalculate: () => void;
  onCancel: () => void;
  onCsv?: () => void;
}

/** Presentational part of the tab: everything given, nothing fetched (render tests). */
export function CubesView(p: ViewProps) {
  const { meta, run, milestone, sort } = p;
  const running = run.phase === "running";
  const pct = run.total ? Math.round((run.done / run.total) * 100) : 0;
  const nRows = meta ? rowsToCalculate(meta, p.state, p.includeBlank).length : 0;
  return (
    <div className="cubes-tab">
      <section className="card" aria-label="Cube optimizer">
        <h2>Cube optimizer</h2>
        <div className="explain">
          {potentialExplainer(meta).map((t) => (
            <p key={t}>{t}</p>
          ))}
          <p>
            Enter what you have now (rarity, pity count, up to 3 lines; leave a row alone if you are not rolling it), then press Calculate. Nothing is
            calculated while you type - a full calculation takes a few seconds. Your entries are saved with the profile.
          </p>
        </div>
      </section>

      {p.metaStatus.error && <StatusBanner status={p.metaStatus} />}
      {!meta && !p.metaStatus.error && (
        <p className="empty" role="status">
          <span className="spinner" aria-hidden="true" /> Loading the cube tables...
        </p>
      )}

      {meta && (
        <>
          <section className="card" aria-label="Current gear">
            <h2>Current potential lines</h2>
            <GearEditor meta={meta} state={p.state} onState={p.onState} />
            <div className="cube-controls">
              <label className="chk">
                <input type="checkbox" checked={p.includeBlank} onChange={(e) => p.onIncludeBlank(e.target.checked)} />
                Also calculate rows I left blank (treated as Normal with no lines)
              </label>
              <label htmlFor="cube-milestone">Cubes to compare</label>
              <select id="cube-milestone" value={milestone} onChange={(e) => p.onMilestone(Number(e.target.value))}>
                {SELECTABLE_MILESTONES.map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
              <label htmlFor="cube-sort">Rank by</label>
              <select id="cube-sort" value={sort} onChange={(e) => p.onSort(e.target.value as CubeSort)}>
                {CUBE_SORTS.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="cube-controls">
              {running ? (
                <button type="button" onClick={p.onCancel}>
                  Cancel
                </button>
              ) : (
                <button type="button" className="primary" onClick={p.onCalculate} disabled={nRows === 0}>
                  Calculate ({nRows} {nRows === 1 ? "row" : "rows"})
                </button>
              )}
              {(running || run.phase !== "idle") && (
                <>
                  <div
                    className="progress"
                    role="progressbar"
                    aria-valuemin={0}
                    aria-valuemax={run.total}
                    aria-valuenow={run.done}
                    aria-label="Cube calculation progress"
                  >
                    <span style={{ width: `${pct}%` }} />
                  </div>
                  <span className="note">
                    {run.done} / {run.total} rows
                    {running ? "" : run.phase === "cancelled" ? " (cancelled)" : run.phase === "error" ? " (stopped)" : " (done)"}
                  </span>
                </>
              )}
              {nRows === 0 && <span className="note">Fill in at least one row, or tick the box above.</span>}
            </div>
          </section>

          {run.status.unsupported && (
            <div className="sens-message" role="status">
              <strong>{CUBES_UNSUPPORTED_TEXT}</strong>
            </div>
          )}
          <StatusBanner status={run.status} onRetry={run.phase === "error" ? p.onCalculate : undefined} />

          {run.rows.length > 0 && (
            <section className="card" aria-label="Recommendations">
              <h2>Recommendations</h2>
              {p.outdated && (
                <p className="cube-outdated" role="status">
                  Your inputs changed since this was calculated - press Calculate again to refresh.
                </p>
              )}
              <p className="note">
                Total DPS now: <strong title={run.baseline ? formatFull(run.baseline) : undefined}>{formatNumber(run.baseline)}</strong>. Gains are expected DPS
                as a % of that, keeping the best result so far and stopping optimally.
                {p.onCsv && (
                  <>
                    {" "}
                    <button type="button" onClick={p.onCsv}>
                      Download CSV
                    </button>
                  </>
                )}
              </p>
              <CubeResults rows={run.rows} meta={meta} milestone={milestone} sort={sort} baseline={run.baseline} />
              <p className="note">
                Worth rolling? (a rule on the expected gain at the chosen cube count, it does not know what a cube costs you): <strong>Yes</strong> = at least
                +1% Total DPS, <strong>Maybe</strong> = +0.1% to +1%, <strong>Marginal</strong> = positive but under +0.1%, <strong>No</strong> = no cube count
                up to {meta.max_cubes} has a positive expected gain (you are at or near the best this slot can roll). &quot;N for 50% / 75%&quot; is the number
                of cubes after which at least one reroll has beaten your current lines with that probability.
              </p>
              {run.notes.length > 0 && (
                <ul className="note">
                  {run.notes.map((n) => (
                    <li key={n}>{noteText(n)}</li>
                  ))}
                </ul>
              )}
            </section>
          )}
        </>
      )}
    </div>
  );
}

/** Engine notes (api cubes `notes`) in plain words. */
export function noteText(n: string): string {
  if (n === "above") return "Some Skill Cooldown Decrease values are above the table's last step; the last slope is extended.";
  if (n === "below") return "Some Skill Cooldown Decrease values are below the table's first step; priced from the exact model or the linear rate.";
  if (n.startsWith("cdr_lines_exceed_inputs:"))
    return `${n.split(":")[1]}: the Cooldown Decrease lines you entered exceed the Cooldown Decrease in your Inputs; the rest of the character counts as 0.`;
  if (n.startsWith("mock mode")) return n;
  return n;
}

interface Props {
  classId: string | null;
  inputs: Record<string, unknown> | null;
  /** GET /api/classes `status.stat_values`: `false` shows the "not available" message without asking the API at all */
  supported?: boolean;
  active: boolean;
  meta: CubesMeta | null;
  metaStatus: RequestStatus;
  state: CubesState | undefined;
  onState: (s: CubesState) => void;
}

/** The "Cubes" tab: gear editor, Calculate (chunked, cancellable), ranked recommendations. */
export function CubesPanel({ classId, inputs, supported, meta, metaStatus, state, onState }: Props) {
  const [run, setRun] = useState<RunState>(IDLE_RUN);
  const [milestone, setMilestone] = useState(DEFAULT_MILESTONE);
  const [sort, setSort] = useState<CubeSort>("ev");
  const [includeBlank, setIncludeBlank] = useState(false);
  const runner = useRef<CubesRunner | null>(null);
  if (runner.current === null) runner.current = new CubesRunner((id, inp, gear, only, signal) => api.cubes(id, inp, gear, only, signal), setRun);

  // a class switch (or leaving the page) drops the old run
  useEffect(() => {
    const r = runner.current!;
    return () => r.reset();
  }, [classId]);

  const currentKey = useMemo(() => (meta && inputs ? JSON.stringify({ classId, inputs, gear: gearPayload(meta, state) }) : ""), [classId, inputs, meta, state]);
  if (supported === false) {
    return (
      <div className="sens-message" role="status">
        <strong>{CUBES_UNSUPPORTED_TEXT}</strong>
        <p>
          The cube optimizer needs the class&apos;s stat values (they price every line), which are not modelled for this class yet. The Calculator tab works for
          every class.
        </p>
      </div>
    );
  }
  const calculate = () => {
    if (!meta || !inputs || !classId) return;
    const rows = rowsToCalculate(meta, state, includeBlank);
    if (!rows.length) return;
    void runner.current!.run(classId, inputs, gearPayload(meta, state), rows, currentKey);
  };
  const csv = () => {
    if (!meta) return;
    const text = cubesCsv(rankRows(run.rows, "sheet", milestone, meta), meta.milestones, meta.csv_columns);
    const url = URL.createObjectURL(new Blob([text], { type: "text/csv" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `cubes-${classId}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };
  return (
    <CubesView
      meta={meta}
      metaStatus={metaStatus}
      state={state}
      onState={onState}
      run={run}
      milestone={milestone}
      onMilestone={setMilestone}
      sort={sort}
      onSort={setSort}
      includeBlank={includeBlank}
      onIncludeBlank={setIncludeBlank}
      outdated={run.phase !== "idle" && run.phase !== "running" && run.key !== currentKey}
      onCalculate={calculate}
      onCancel={() => runner.current!.cancel()}
      onCsv={csv}
    />
  );
}
