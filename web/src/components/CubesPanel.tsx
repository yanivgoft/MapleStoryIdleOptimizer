import { useEffect, useMemo, useRef, useState } from "react";
import "./sensitivity.css";
import "./cubes.css";
import { api } from "../api";
import {
  CUBE_SORTS,
  NONE_STAT,
  cubesCsv,
  evAt,
  effectiveCubeCount,
  evPctAt,
  formatCubes,
  formatEvPct,
  formatUntilPositive,
  gearKey,
  gearPayload,
  getRow,
  initialCubeCount,
  isConfigured,
  linesText,
  lineWithStat,
  parseCubeCount,
  pityCap,
  NOT_ROLLABLE_ON_SLOT,
  groupByPotentialType,
  pityHint,
  potentialExplainer,
  rankRows,
  rarityLabel,
  rollValueOptions,
  rowsToCalculate,
  setLine,
  setRow,
  slotLabel,
  typeCubeCount,
  withRarity,
  statOptions,
  worthRolling,
  type CubeRow,
  type CubeSort,
  type CubesMeta,
  type CubesState,
  type GearLine,
  type GearRowState,
} from "../lib/cubes";
import { CubesRunner, IDLE_RUN, type RunState } from "../lib/cubesRunner";
import { formatFull, formatNumber } from "../lib/format";
import { groupedStatChoices } from "../lib/statGroups";
import type { RequestStatus } from "../lib/liveRequest";
import { NumInput } from "./NumInput";
import { AboutTab, NOT_AVAILABLE_TEXT, Unavailable } from "./TabNotes";

export const CUBES_UNSUPPORTED_TEXT = NOT_AVAILABLE_TEXT;

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

/** One stat dropdown shared by the three editors: "(none)" first, then the stats in `primary` (what that piece of equipment can roll) in `<optgroup>`s by kind of stat
 *  (lib/statGroups.ts).  A current value outside `primary` stays selectable as ONE entry above the groups, flagged with a warning when `notRollable` says why (cubes,
 *  artifact lines); without `notRollable` it is shown plain (Equipment compare). */
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
  const { head, groups } = groupedStatChoices(primary, value, notRollable, none);
  const flagged = head.some((c) => c.warn);
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
      {head.map((c) => (
        <option key={c.value} value={c.value} data-warn={c.warn ? "true" : undefined}>
          {c.label}
        </option>
      ))}
      {groups.map((g) => (
        <optgroup key={g.label} label={g.label}>
          {g.choices.map((c) => (
            <option key={c.value} value={c.value}>
              {c.label}
            </option>
          ))}
        </optgroup>
      ))}
    </select>
  );
}

/** The value of one potential line: exactly the values the game rolls for (slot, rarity, line, stat), prime first, blank until chosen.  One possible value = plain text,
 *  no dropdown.  A stat without a roll entry here (flagged, or not rollable at this rarity) has no value input: a stored value is only shown as text. */
export function LineValue({ meta, slot, rarity, index, line, label, onChange }: {
  meta: CubesMeta;
  slot: string;
  rarity: string;
  index: number;
  line: GearLine;
  label: string;
  onChange: (v: number | null) => void;
}) {
  if (line.stat === NONE_STAT) return <NumInput value={null} label={label} disabled onChange={onChange} />;
  const options = rollValueOptions(meta, slot, rarity, index, line.stat);
  if (options.length === 0) {
    return (
      <span className="valfix valnone" data-value-for={label}>
        {line.value === null ? "" : String(line.value)}
      </span>
    );
  }
  if (options.length === 1) {
    return (
      <span className="valfix" data-value-for={label}>
        {options[0].label}
      </span>
    );
  }
  return (
    <select aria-label={label} className="valsel" value={line.value === null ? "" : String(line.value)} onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}>
      <option value=""></option>
      {options.map((o) => (
        <option key={o.value} value={String(o.value)}>
          {o.label}
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

/** The gear editor: 15 slots x {Potential, Bonus Potential}, rarity + pity + 3 lines each. */
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
        {meta.slots.map((s) => {
          const own = statOptions(meta, s.key);
          return (
            <tbody key={s.key} className="slot-block" data-slot={s.key}>
              {meta.potential_types.map((t, ti) => {
                const row = getRow(state, s.key, t);
                const cap = pityCap(meta, t, row.rarity);
                const id = `${s.label} ${t}`;
                return (
                  <tr key={gearKey(s.key, t)} data-row={gearKey(s.key, t)} className={isConfigured(row) ? "cfg" : undefined}>
                    <td className="slot">{ti === 0 ? s.label : ""}</td>
                    <td>{t}</td>
                    <td>
                      <select aria-label={`${id} rarity`} value={row.rarity} onChange={(e) => update(s.key, t, withRarity(row, e.target.value))}>
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
                            onChange={(stat) => update(s.key, t, setLine(row, i, lineWithStat(meta, s.key, row.rarity, i, l, stat)))}
                          />
                          <LineValue
                            meta={meta}
                            slot={s.key}
                            rarity={row.rarity}
                            index={i}
                            line={l}
                            label={`${id} line ${i + 1} value`}
                            onChange={(v) => update(s.key, t, setLine(row, i, { value: v }))}
                          />
                        </span>
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          );
        })}
      </table>
    </div>
  );
}

/** Ranked recommendations (pure presentation of rows already received); `cubes` = the exact number of cubes the user has. */
export function CubeResults({
  rows,
  meta,
  cubes,
  sort,
  baseline,
}: {
  rows: CubeRow[];
  meta: CubesMeta | null;
  cubes: number;
  sort: CubeSort;
  baseline: number | null;
}) {
  const groups = useMemo(() => groupByPotentialType(rankRows(rows, sort, cubes, meta)), [rows, sort, cubes, meta]);
  const [openWhy, setOpenWhy] = useState<string | null>(null);
  if (!rows.length) return null;
  return (
    <div className="table-wrap">
      <table className="sens-table" aria-label="Cube recommendations">
        <thead>
          <tr>
            <th scope="col">#</th>
            <th scope="col">Slot</th>
            <th scope="col">Current</th>
            <th scope="col" className="num" title="Now: what the lines you entered are worth now, in % of Total DPS">
              Worth now (% of Total DPS)
            </th>
            <th scope="col" className="num" title="Cubes to positive EV: the smallest number of cubes after which the average gain (keeping the best result so far) is positive">
              Cubes until rolling pays off
            </th>
            <th scope="col" className="num" title="N for 50%: cubes needed for a 50% chance that at least one reroll beats your current lines">
              Cubes for 50% chance of an upgrade
            </th>
            <th scope="col" className="num" title="N for 75%: cubes needed for a 75% chance that at least one reroll beats your current lines">
              Cubes for 75% chance of an upgrade
            </th>
            <th scope="col" className="num" title={`EV @ ${cubes} cubes: the expected DPS gained by spending up to ${cubes} cubes, stopping at the best moment`}>
              Average gain after {cubes} {cubes === 1 ? "cube" : "cubes"}
            </th>
            <th scope="col" title="A plain rule on the average gain at your cube count; see About this tab below">
              Worth rolling?
            </th>
          </tr>
        </thead>
        {groups.map((g) => (
          <tbody key={g.type} data-potential-type={g.type}>
            <tr className="group-row">
              <th colSpan={9} scope="colgroup">
                {g.type}{" "}
                <span className="sub">
                  {g.rows.length} {g.rows.length === 1 ? "slot" : "slots"}
                </span>
              </th>
            </tr>
            {g.rows.map((r, i) => {
              const w = worthRolling(r, cubes);
              const rk = `${r.slot}|${r.potential_type}`;
              const open = openWhy === rk;
              const whyId = `cube-why-${g.type === "Potential" ? "p" : "b"}-${r.slot}`;
              return (
                <tr key={rk} data-row={rk} data-verdict={w.verdict}>
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
                  <td className="num">{formatUntilPositive(r.smallest_n)}</td>
                  <td className="num">{formatCubes(r.n_for_50pct, meta?.max_cubes)}</td>
                  <td className="num">{formatCubes(r.n_for_75pct, meta?.max_cubes)}</td>
                  <td className="num" title={`${formatFull(evAt(r, cubes, baseline))} DPS`}>
                    {formatEvPct(evPctAt(r, cubes))}
                    <span className="sub">{formatNumber(evAt(r, cubes, baseline))}</span>
                  </td>
                  <td>
                    <button
                      type="button"
                      className={`verdict ${w.verdict}`}
                      title={w.why}
                      aria-expanded={open}
                      aria-controls={open ? whyId : undefined}
                      onClick={() => setOpenWhy(open ? null : rk)}
                    >
                      {w.label}
                    </button>
                    {open && (
                      <span className="verdict-why" id={whyId}>
                        {w.why}
                      </span>
                    )}
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
  /** the text in the "Cubes you have" box, and the count every result is priced for (the last valid entry) */
  countText: string;
  onCountText: (t: string) => void;
  cubes: number;
  sort: CubeSort;
  onSort: (s: CubeSort) => void;
  includeBlank: boolean;
  onIncludeBlank: (b: boolean) => void;
  outdated: boolean;
  onCalculate: () => void;
  onCancel: () => void;
  onCsv?: () => void;
  onOpenHelp?: () => void;
}

/** The "Cubes you have" box: a typed whole number (1..max); a bad entry shows a message and the results keep using the last good count. */
export function CubeCountInput({ text, onText, max }: { text: string; onText: (t: string) => void; max: number }) {
  const { error } = parseCubeCount(text, max);
  return (
    <span className="cube-count">
      <label htmlFor="cube-count">Cubes you have</label>
      <input
        id="cube-count"
        type="text"
        inputMode="numeric"
        autoComplete="off"
        className="numin"
        value={text}
        aria-invalid={!!error}
        aria-describedby={error ? "cube-count-err" : undefined}
        onChange={(e) => onText(e.target.value)}
      />
      {error && (
        <span className="note cube-count-err" id="cube-count-err" role="alert">
          {error}
        </span>
      )}
    </span>
  );
}

/** Presentational part of the tab: everything given, nothing fetched (render tests). */
export function CubesView(p: ViewProps) {
  const { meta, run, cubes, sort } = p;
  const running = run.phase === "running";
  const pct = run.total ? Math.round((run.done / run.total) * 100) : 0;
  const nRows = meta ? rowsToCalculate(meta, p.state, p.includeBlank).length : 0;
  return (
    <div className="cubes-tab">
      <section className="card" aria-label="Cubes">
        <h2>Cubes</h2>
        <p className="note">Enter the potential lines you have now to see which slots are worth cubing.</p>
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
              <CubeCountInput text={p.countText} onText={p.onCountText} max={meta.max_cubes} />
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

          {run.status.unsupported && <Unavailable onOpenHelp={p.onOpenHelp} text={CUBES_UNSUPPORTED_TEXT} />}
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
                Total DPS now: <strong title={run.baseline ? formatFull(run.baseline) : undefined}>{formatNumber(run.baseline)}</strong>.
                {p.onCsv && (
                  <>
                    {" "}
                    <button type="button" onClick={p.onCsv}>
                      Download CSV
                    </button>
                  </>
                )}
              </p>
              <CubeResults rows={run.rows} meta={meta} cubes={cubes} sort={sort} baseline={run.baseline} />
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

      {meta && <CubesAbout meta={meta} />}
    </div>
  );
}

/** The collapsed explanation at the bottom of the tab: how to use it, how to read the table, what the Worth rolling? chips mean. */
export function CubesAbout({ meta }: { meta: CubesMeta }) {
  return (
    <AboutTab>
      <p>
        Enter what you have now (rarity, pity count, up to 3 lines; leave a row alone if you are not rolling it), type how many cubes you have, then press Calculate. Changing a row's rarity clears its lines, because each rarity has its own stats and values.
        Nothing is calculated while you type - a full calculation takes a few seconds. Your entries are saved with the profile. Changing the number of cubes
        re-ranks the table at once, without calculating again.
      </p>
      {potentialExplainer(meta).map((t) => (
        <p key={t}>{t}</p>
      ))}
      <p>
        <strong>How to read the table.</strong> &quot;Worth now&quot; is what the lines you entered add to your Total DPS today. &quot;Average gain&quot; is the
        average DPS gained by spending your cubes, as a % of Total DPS: you keep the best result so far and stop at the best moment, and a cube always re-rolls all
        3 lines. &quot;Cubes until rolling pays off&quot; is the first cube count with a positive average gain. &quot;Cubes for 50% / 75% chance of an upgrade&quot;
        is how many cubes it takes for at least one reroll to have beaten your current lines with that probability.
      </p>
      <p>
        <strong>Worth rolling?</strong> A plain rule on the average gain at your cube count; it does not know what a cube costs you. <strong>Yes</strong> = at least
        +1% Total DPS, <strong>Maybe</strong> = +0.1% to +1%, <strong>Marginal</strong> = positive but under +0.1%, <strong>No</strong> = no cube count up to{" "}
        {meta.max_cubes} has a positive average gain (you are at or near the best this slot can roll). Press a chip to see its reason.
      </p>
    </AboutTab>
  );
}

/** Notes of the cubes answer (api cubes `notes`) in plain words. */
export function noteText(n: string): string {
  if (n === "above") return "Some Skill Cooldown Decrease values are above the table's last step; the last slope is extended.";
  if (n === "below") return "Some Skill Cooldown Decrease values are below the table's first step; they are priced from an exact recalculation or the linear rate.";
  if (n.startsWith("cdr_lines_exceed_inputs:"))
    return `${n.split(":")[1]}: the Cooldown Decrease lines you entered exceed the Cooldown Decrease on the Calculator tab; the rest of the character counts as 0.`;
  if (n.startsWith("buff_lines_exceed_inputs:"))
    return `${n.split(":")[1]}: the Buff Duration lines you entered exceed the Buff Duration on the Calculator tab; the rest of the character counts as 0.`;
  if (n.startsWith("companion_lines_exceed_inputs:"))
    return `${n.split(":")[1]}: the Companion Summoning Time lines you entered exceed the value on the Calculator tab; the rest of the character counts as 0.`;
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
  /** opens the Help tab (the "See Help" link of the "not available" line); App.tsx passes it, absent = no link */
  onOpenHelp?: () => void;
}

/** The "Cubes" tab: gear editor, the cube count, Calculate (chunked, cancellable), ranked recommendations. */
export function CubesPanel({ classId, inputs, supported, meta, metaStatus, state, onState, onOpenHelp }: Props) {
  const [run, setRun] = useState<RunState>(IDLE_RUN);
  const [count, setCount] = useState(initialCubeCount);
  const [sort, setSort] = useState<CubeSort>("ev");
  const [includeBlank, setIncludeBlank] = useState(false);
  const runner = useRef<CubesRunner | null>(null);
  if (runner.current === null) runner.current = new CubesRunner((id, inp, gear, only, signal) => api.cubes(id, inp, gear, only, signal), setRun);

  // a class switch (or leaving the page) drops the old run
  useEffect(() => {
    const r = runner.current!;
    return () => r.reset();
  }, [classId]);

  const maxCubes = meta?.max_cubes ?? 1000;
  const cubes = effectiveCubeCount(count, maxCubes);

  const currentKey = useMemo(() => (meta && inputs ? JSON.stringify({ classId, inputs, gear: gearPayload(meta, state) }) : ""), [classId, inputs, meta, state]);
  if (supported === false) return <Unavailable onOpenHelp={onOpenHelp} text={CUBES_UNSUPPORTED_TEXT} />;
  const calculate = () => {
    if (!meta || !inputs || !classId) return;
    const rows = rowsToCalculate(meta, state, includeBlank);
    if (!rows.length) return;
    void runner.current!.run(classId, inputs, gearPayload(meta, state), rows, currentKey);
  };
  const csv = () => {
    if (!meta) return;
    const text = cubesCsv(rankRows(run.rows, "slot", cubes, meta), meta.milestones, meta.csv_columns);
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
      countText={count.text}
      onCountText={(t) => setCount((c) => typeCubeCount(c, t, maxCubes))}
      cubes={cubes}
      sort={sort}
      onSort={setSort}
      includeBlank={includeBlank}
      onIncludeBlank={setIncludeBlank}
      outdated={run.phase !== "idle" && run.phase !== "running" && run.key !== currentKey}
      onCalculate={calculate}
      onCancel={() => runner.current!.cancel()}
      onCsv={csv}
      onOpenHelp={onOpenHelp}
    />
  );
}
