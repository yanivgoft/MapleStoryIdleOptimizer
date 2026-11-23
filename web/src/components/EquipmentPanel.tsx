import { useMemo } from "react";
import "./sensitivity.css";
import "./cubes.css";
import { api } from "../api";
import { NONE_STAT, type CubesMeta } from "../lib/cubes";
import { ATTACK_STAT, blankEquip, equipPayload, equipVerdict, sideHasContent, type EquipResult, type EquipSide, type EquipSideResult, type EquipState } from "../lib/equipment";
import { formatFull, formatNumber } from "../lib/format";
import type { RequestStatus } from "../lib/liveRequest";
import { useLive } from "../lib/useLive";
import { NumInput } from "./NumInput";
import { StatSelect } from "./CubesPanel";

export const EQUIP_UNSUPPORTED_TEXT = "Equipment compare is not available for this class yet.";

/** Unsigned percentage text; tiny values keep an exponent so they do not read as 0. */
const pct = (v: number) => `${Math.abs(v) >= 0.01 || v === 0 ? Math.abs(v).toFixed(2) : Math.abs(v).toExponential(1)}%`;

function SideEditor({ title, side, meta, onChange, idPrefix }: { title: string; side: EquipSide; meta: CubesMeta; onChange: (s: EquipSide) => void; idPrefix: string }) {
  const stats = meta.equipment.stats;
  return (
    <div className="card" aria-label={title}>
      <h2>{title}</h2>
      <div className="equip-line">
        <span className="label-fixed">{ATTACK_STAT} (fixed line)</span>
        <NumInput value={side.attack} label={`${title} attack`} onChange={(v) => onChange({ ...side, attack: v })} />
      </div>
      {side.lines.map((l, i) => (
        <div key={i} className="equip-line">
          <StatSelect value={l.stat} label={`${title} line ${i + 1} stat`} primary={stats} onChange={(stat) => onChange({ ...side, lines: side.lines.map((x, j) => (j === i ? { stat, value: stat === NONE_STAT ? null : x.value } : x)) })} />
          <NumInput value={l.value} label={`${title} line ${i + 1} value`} disabled={l.stat === NONE_STAT} onChange={(v) => onChange({ ...side, lines: side.lines.map((x, j) => (j === i ? { ...x, value: v } : x)) })} />
        </div>
      ))}
      <span id={`${idPrefix}-hint`} className="note">
        Same-stat lines add up; different stats multiply.
      </span>
    </div>
  );
}

function SideResult({ title, r, total }: { title: string; r: EquipSideResult; total: number }) {
  return (
    <div className="card" aria-label={`${title} result`}>
      <h2>{title}</h2>
      <div className="equip-total" title={`${formatFull(r.total_gain)} DPS`}>
        +{pct(r.pct)} of Total DPS
      </div>
      <div className="note">= {formatNumber(r.total_gain)} DPS on top of {formatNumber(total)} without it</div>
      <table className="sens-table" aria-label={`${title} lines`}>
        <thead>
          <tr>
            <th>Line</th>
            <th className="num">Value</th>
            <th className="num">DPS</th>
          </tr>
        </thead>
        <tbody>
          {r.rows
            .filter((x) => x.stat !== NONE_STAT)
            .map((x, i) => (
              <tr key={i} className={x.first ? undefined : "dim"}>
                <td>
                  {x.stat}
                  {!x.first && <span className="sub">added to the first {x.stat} line</span>}
                </td>
                <td className="num">{formatNumber(x.value)}</td>
                <td className="num" title={`${formatFull(x.gain)} DPS`}>
                  {formatNumber(x.gain)}
                </td>
              </tr>
            ))}
        </tbody>
      </table>
    </div>
  );
}

/** Presentational part (render tests): editors + result of the compare. */
export function EquipmentView(p: {
  meta: CubesMeta | null;
  metaStatus: RequestStatus;
  state: EquipState;
  onState: (s: EquipState) => void;
  result: EquipResult | null;
  status: RequestStatus;
  stale?: boolean;
  pending?: boolean;
  onRetry?: () => void;
}) {
  const { meta, result, status } = p;
  if (status.unsupported || p.metaStatus.unsupported) {
    return (
      <div className="sens-message" role="status">
        <strong>{EQUIP_UNSUPPORTED_TEXT}</strong>
      </div>
    );
  }
  const err = status.error ? status : p.metaStatus.error ? p.metaStatus : null;
  return (
    <div className="equipment-tab">
      <section className="card" aria-label="Equipment compare">
        <h2>Equipment compare</h2>
        <p className="explain">
          Compare your current equip with a new one: a fixed Attack line plus up to 5 lines each (pick the stat, type the value). Each equip is priced against your Total DPS from the Calculator
          tab (its lines on top of what you have now, same-stat lines adding, different stats multiplying), and the result is the difference in % of Total DPS. Updates as you type. Saved with
          the profile.
        </p>
      </section>
      {err && (
        <div className="banner error" role="alert">
          {err.error}
          {err.fieldErrors.length > 0 && (
            <ul>
              {err.fieldErrors.map((m) => (
                <li key={m}>{m}</li>
              ))}
            </ul>
          )}
          {p.onRetry && (
            <p>
              <button type="button" onClick={p.onRetry}>
                Try again
              </button>
            </p>
          )}
        </div>
      )}
      {!meta && !err && (
        <p className="empty" role="status">
          <span className="spinner" aria-hidden="true" /> Loading the equipment tables...
        </p>
      )}
      {meta && (
        <>
          <div className="equip-grid">
            <SideEditor title="Current equip" side={p.state.current} meta={meta} idPrefix="eq-cur" onChange={(s) => p.onState({ ...p.state, current: s })} />
            <SideEditor title="New equip" side={p.state.new} meta={meta} idPrefix="eq-new" onChange={(s) => p.onState({ ...p.state, new: s })} />
          </div>
          <div className={p.stale || p.pending ? "sens-stale" : undefined} aria-busy={status.loading}>
            {(status.loading || p.pending) && (
              <div className="sens-loading" role="status">
                <span className="spinner" aria-hidden="true" /> Comparing...
              </div>
            )}
            {result ? (
              <section aria-label="Comparison result">
                <div className="card" role="status">
                  <h2>New vs current</h2>
                  <div className="equip-total" data-better={result.better}>
                    {result.better === "equal" ? "No difference" : `${result.delta_pct > 0 ? "+" : "-"}${pct(Math.abs(result.delta_pct))}`} of Total DPS
                  </div>
                  <div className="note">
                    {equipVerdict(result)} ({result.delta_dps >= 0 ? "+" : "-"}
                    {formatNumber(Math.abs(result.delta_dps))} DPS on {formatNumber(result.baseline_total)}.)
                  </div>
                  {result.crit_priced_as_crit_damage && <p className="note">Your live crit rate is at or above 100%, so Critical Rate lines are priced as Critical Damage (nothing gained from more crit rate).</p>}
                  {!sideHasContent(p.state.current) && !sideHasContent(p.state.new) && <p className="note">Both equips are empty - fill in some lines.</p>}
                </div>
                <div className="equip-grid">
                  <SideResult title="Current equip" r={result.current} total={result.baseline_total} />
                  <SideResult title="New equip" r={result.new} total={result.baseline_total} />
                </div>
              </section>
            ) : (
              !err && <p className="empty">{status.loading || p.pending ? "Comparing..." : "Waiting for the first comparison..."}</p>
            )}
          </div>
        </>
      )}
    </div>
  );
}

interface Props {
  classId: string | null;
  inputs: Record<string, unknown> | null;
  supported?: boolean;
  active: boolean;
  meta: CubesMeta | null;
  metaStatus: RequestStatus;
  state: EquipState | undefined;
  onState: (s: EquipState) => void;
}

/** The "Equipment compare" tab: live (debounced) because the call is cheap once the character's stat prices are cached on the server. */
export function EquipmentPanel({ classId, inputs, supported, active, meta, metaStatus, state, onState }: Props) {
  const eq = state ?? blankEquip();
  const on = active && supported !== false && !!meta;
  const key = useMemo(() => (inputs && classId ? JSON.stringify({ inputs, body: equipPayload(eq) }) : ""), [inputs, classId, eq]);
  const live = useLive<EquipResult>({
    key: on ? key : "",
    group: classId ?? "",
    active: on,
    what: "equipment compare",
    fetcher: (k, signal) => {
      const { inputs: inp, body } = JSON.parse(k);
      return api.equipmentCompare(classId!, inp, body, signal);
    },
  });
  if (supported === false) return <EquipmentView meta={null} metaStatus={{ ...metaStatus, unsupported: true }} state={eq} onState={onState} result={null} status={live.status} />;
  return <EquipmentView meta={meta} metaStatus={metaStatus} state={eq} onState={onState} result={live.result} status={live.status} stale={live.stale} pending={live.pending} onRetry={live.retry} />;
}
