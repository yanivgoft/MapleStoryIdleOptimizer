import { useMemo, useState } from "react";
import "./sensitivity.css";
import "./cubes.css";
import "./artifacttable.css";
import { api } from "../api";
import {
  NOT_UNLOCKED, badgesFor, equippedKeys, isBlankLine, isNoDps, lineCount, normalizeArtifacts, setLine,
  setStar, starIndex, starOptions, visibleArtifacts, type Badge,
} from "../lib/artifacts";
import {
  lineKnown, lineValue, potentialTables, potentialsRequest, type PotentialRow, type PotentialsResult, type PotentialTables,
} from "../lib/artifactPotentials";
import { NONE_STAT, NOT_ROLLABLE_ON_ARTIFACTS, type CubesMeta } from "../lib/cubes";
import type { RequestStatus } from "../lib/liveRequest";
import { signedPct } from "../lib/sensitivity";
import { useLive } from "../lib/useLive";
import type { ArtifactInfo, ArtifactSchema, ArtifactsState } from "../types";
import { StatSelect } from "./CubesPanel";

export const POTENTIALS_UNSUPPORTED_TEXT = "Artifact potentials are not available for this class yet.";
const GAINS_UNSUPPORTED_NOTE = `${POTENTIALS_UNSUPPORTED_TEXT} Your lines are still saved with the profile.`;

export function BadgeChip({ badge, onOpenCompanion, compact }: { badge: Badge; onOpenCompanion: () => void; compact?: boolean }) {
  if (badge.kind === "companion" || badge.kind === "status") {
    return (
      <button type="button" className={`badge ${badge.kind}`} onClick={onOpenCompanion}>
        {badge.label} <span className="badge-link">(go to Companion)</span>
      </button>
    );
  }
  return (
    <span className={`badge ${badge.kind}`}>
      {badge.label}
      {!compact && <span className="badge-detail">: {badge.detail}</span>}
    </span>
  );
}

interface ViewProps {
  art: ArtifactSchema;
  state: ArtifactsState | undefined;
  onState: (s: ArtifactsState) => void;
  tables: PotentialTables;
  /** the answer of POST .../artifact-potentials (null: none yet / not available) */
  result: PotentialsResult | null;
  status: RequestStatus;
  /** the class has no stat values / potentials engine: the table shows no gains and says so */
  gainsUnsupported?: boolean;
  /** the class's `status.stat_values` is still unknown or the potentials tables are still loading: nothing to say */
  stale?: boolean;
  pending?: boolean;
  onRetry?: () => void;
  onOpenCompanion: () => void;
  /** artifact ids equipped in the CURRENT content type (read-only here: they are chosen in the Calculator's "Equipped artifacts" section) */
  equipped: readonly string[];
  contentType?: string;
  /** link to that section (absent: no link) */
  onOpenInputs?: () => void;
  /** initial filter state (tests; the controls own it afterwards) */
  initialText?: string;
  initialOnlyActive?: boolean;
}

const NOT_UNLOCKED_VALUE = NOT_UNLOCKED;

/**
 * The Artifacts tab's one table: a row per artifact with its Star Level, a read-only "equipped" marker (for the current content
 * type; the slots are chosen on the Calculator, at most `art.max_slots`) and the 3 potential lines (rarity + stat; line 3 only for Legendary artifacts) with their DPS gain and the artifact's total.  Presentational: the container
 * (`ArtifactTable`) feeds it the potentials answer.
 */
export function ArtifactTableView(p: ViewProps) {
  const { art, tables } = p;
  const state = useMemo(() => normalizeArtifacts(p.state, art), [p.state, art]);
  const [text, setText] = useState(p.initialText ?? "");
  const [onlyActive, setOnlyActive] = useState(!!p.initialOnlyActive);
  const opts = starOptions(art);
  const equippedIds = useMemo(() => equippedKeys(art, p.equipped), [art, p.equipped]);
  const equipped = equippedIds.length;
  const rows = new Map<string, PotentialRow>((p.result?.rows ?? []).map((r) => [r.key, r]));
  const shown = visibleArtifacts(art, state, { text, onlyActive }, equippedIds);
  const groups: { rank: string; items: ArtifactInfo[] }[] = [];
  for (const a of shown) {
    const g = groups[groups.length - 1];
    if (g && g.rank === a.rank) g.items.push(a);
    else groups.push({ rank: a.rank, items: [a] });
  }
  const showGains = !p.gainsUnsupported && !p.status.unsupported;
  const err = p.status.error ? p.status : null;
  const total = p.result?.baseline_total ?? 0;
  const COLS = 7;

  return (
    <section className="card artifacts art-table-card" aria-label="Artifacts table">
      <h2>Artifacts</h2>
      <div className="art-controls-row">
        <label htmlFor="art-filter">Filter</label>
        <input id="art-filter" type="search" value={text} placeholder="filter by name" onChange={(e) => setText(e.target.value)} />
        <label className="check" htmlFor="art-only-active">
          <input id="art-only-active" type="checkbox" checked={onlyActive} onChange={(e) => setOnlyActive(e.target.checked)} /> Show only unlocked / equipped
        </label>
        <span className={`equip-count${equipped >= art.max_slots ? " full" : ""}`} role="status" data-testid="equip-count">
          {equipped} / {art.max_slots} equipped{p.contentType ? ` in ${p.contentType}` : ""}
        </span>
      </div>
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
      {!showGains && (
        <p className="note" role="status" data-testid="gains-unsupported">
          {GAINS_UNSUPPORTED_NOTE}
        </p>
      )}
      <div className={`art-table-wrap${p.stale || p.pending ? " sens-stale" : ""}`} aria-busy={p.status.loading}>
        <table className="art-table" aria-label="Artifacts">
          <thead>
            <tr>
              <th scope="col">Artifact</th>
              <th scope="col">Star level</th>
              <th scope="col">Equipped</th>
              {[0, 1, 2].map((i) => (
                <th key={i} scope="col">
                  Line {i + 1}
                  {i === 2 ? " (Legendary)" : ""}
                </th>
              ))}
              <th scope="col">Potential total</th>
            </tr>
          </thead>
          <tbody>
            {groups.map((g) => (
              <RankGroup key={g.rank} rank={g.rank} cols={COLS}>
                {g.items.map((info) => {
                  const e = state[info.key];
                                  const noDps = isNoDps(info);
                  const row = rows.get(info.key);
                  const n = lineCount(info);
                  const isEq = equippedIds.includes(info.key);
                  const starNum = starIndex(e.star);
                  const rowTotal = row && e.lines.slice(0, n).some((l) => !isBlankLine(l)) ? row.total : null;
                  return (
                    <tr key={info.key} data-artifact={info.key} className={`${isEq ? "equipped" : ""}${noDps ? " dim" : ""}`}>
                      <td className="art-name-cell">
                        <div className="art-name">
                          <strong>{info.name}</strong> <span className="pill">{info.rank}</span>
                        </div>
                        <div className="badges">
                          {badgesFor(info).map((b) => (
                            <BadgeChip key={b.kind} badge={b} onOpenCompanion={p.onOpenCompanion} compact />
                          ))}
                        </div>
                      </td>
                      <td>
                        <select
                          aria-label={`${info.name} star level`}
                          value={String(e.star ?? NOT_UNLOCKED_VALUE)}
                          onChange={(ev) => {
                            const o = opts.find((x) => String(x.value) === ev.target.value);
                            if (o) p.onState(setStar(art, state, info.key, o.value));
                          }}
                        >
                          {opts.map((o) => (
                            <option key={String(o.value)} value={String(o.value)}>
                              {o.label}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="equip-cell">
                        {isEq && (
                          <span className="chip ok">equipped</span>
                        )}
                      </td>
                      {[0, 1, 2].map((i) => {
                        if (i >= n) {
                          return (
                            <td key={i} className="line-na">
                              -
                            </td>
                          );
                        }
                        const l = e.lines[i];
                        const res = row?.lines[i];
                        const unlock = tables.line_min_star[i] ?? 0;
                        const active = res ? res.active : starNum >= unlock;
                        const known = lineKnown(tables, l);
                        const v = lineValue(tables, l.stat, l.rarity);
                        return (
                          <td key={i} className={`line-cell${active ? "" : " inactive"}`}>
                            <select
                              aria-label={`${info.name} line ${i + 1} rarity`}
                              value={l.rarity}
                              onChange={(ev) => p.onState(setLine(art, state, info.key, i, { rarity: ev.target.value }))}
                            >
                              {!tables.rarities.includes(l.rarity) && <option value={l.rarity}>{`⚠ ${l.rarity} (unknown rarity)`}</option>}
                              {tables.rarities.map((r) => (
                                <option key={r} value={r}>
                                  {r}
                                </option>
                              ))}
                            </select>
                            <StatSelect
                              value={l.stat}
                              label={`${info.name} line ${i + 1} stat`}
                              primary={tables.stats}
                              notRollable={NOT_ROLLABLE_ON_ARTIFACTS}
                              onChange={(stat) => p.onState(setLine(art, state, info.key, i, { stat }))}
                            />
                            <span className="note line-gain">
                              {l.stat === NONE_STAT ? "" : known ? `+${v}` : "not valued"}
                              {l.stat !== NONE_STAT && showGains && res && active && known && total ? ` = ${signedPct((res.gain / total) * 100)}` : ""}
                              {l.stat !== NONE_STAT && !active ? ` (locked: star ${unlock})` : ""}
                            </span>
                          </td>
                        );
                      })}
                      <td className="num total-cell">
                        {showGains && rowTotal !== null && row ? (
                          <span>+{total ? ((row.total / total) * 100).toFixed(2) : "0.00"}%</span>
                        ) : (
                          <span className="note">-</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </RankGroup>
            ))}
            {groups.length === 0 && (
              <tr>
                <td colSpan={COLS} className="empty">
                  No artifact matches{text ? ` "${text}"` : ""}{onlyActive ? " among the unlocked / equipped ones" : ""}.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {(p.status.loading || p.pending) && showGains && (
        <div className="sens-loading" role="status">
          <span className="spinner" aria-hidden="true" /> Calculating the potential gains...
        </div>
      )}
    </section>
  );
}

function RankGroup({ rank, cols, children }: { rank: string; cols: number; children: React.ReactNode }) {
  return (
    <>
      <tr className="rank-row">
        <th scope="rowgroup" colSpan={cols}>
          {rank}
        </th>
      </tr>
      {children}
    </>
  );
}

interface Props {
  classId: string | null;
  inputs: Record<string, unknown> | null;
  /** GET /api/classes `status.stat_values` (the prices of the stats come from the stat-values engine): `false` = no gains, without asking the API */
  supported?: boolean;
  active: boolean;
  meta: CubesMeta | null | undefined;
  metaStatus: RequestStatus;
  art: ArtifactSchema;
  state: ArtifactsState | undefined;
  onState: (s: ArtifactsState) => void;
  onOpenCompanion: () => void;
  equipped: readonly string[];
  contentType?: string;
  onOpenInputs?: () => void;
}

/** The table with live potential gains: lazy (only while the Artifacts tab is open, only when some line is set), debounced, one request at a time. */
export function ArtifactTable({ classId, inputs, supported, active, meta, metaStatus, art, state, onState, onOpenCompanion, equipped, contentType, onOpenInputs }: Props) {
  const tables = potentialTables(meta);
  const payload = useMemo(() => potentialsRequest(art, state, tables), [art, state, tables]);
  const hasLines = Object.keys(payload).length > 0;
  const on = active && supported !== false && !metaStatus.unsupported && hasLines;
  const key = useMemo(() => (inputs && classId && hasLines ? JSON.stringify({ inputs, potentials: payload }) : ""), [inputs, classId, payload, hasLines]);
  const live = useLive<PotentialsResult>({
    key: on ? key : "",
    group: classId ?? "",
    active: on,
    what: "artifact potentials",
    fetcher: (k, signal) => {
      const { inputs: inp, potentials } = JSON.parse(k);
      return api.artifactPotentials(classId!, inp, potentials, signal);
    },
  });
  return (
    <ArtifactTableView
      art={art}
      state={state}
      onState={onState}
      tables={tables}
      result={hasLines ? live.result : null}
      status={live.status}
      gainsUnsupported={supported === false || metaStatus.unsupported}
      stale={live.stale}
      pending={live.pending}
      onRetry={live.retry}
      onOpenCompanion={onOpenCompanion}
      equipped={equipped}
      contentType={contentType}
      onOpenInputs={onOpenInputs}
    />
  );
}
