// Equipment compare logic (pure): the editable state (current vs new equip), the request body, result types and a port of the engine's formula that mock mode uses.
import type { GearLine } from "./cubes";
import { NONE_STAT, emptyLine } from "./cubes";

export interface EquipSide {
  attack: number | null; // the fixed "Attack (flat)" line
  lines: GearLine[]; // 5 dropdown lines
}
export interface EquipState {
  current: EquipSide;
  new: EquipSide;
}

export const EQUIP_LINES = 5;
export const blankSide = (): EquipSide => ({ attack: null, lines: Array.from({ length: EQUIP_LINES }, emptyLine) });
export const blankEquip = (): EquipState => ({ current: blankSide(), new: blankSide() });

export function normalizeSide(raw: unknown): EquipSide {
  const r = (raw && typeof raw === "object" ? raw : {}) as Partial<EquipSide>;
  const attack = typeof r.attack === "number" && Number.isFinite(r.attack) && r.attack >= 0 ? r.attack : null;
  const lines: GearLine[] = Array.from({ length: EQUIP_LINES }, (_v, i) => {
    const l = Array.isArray(r.lines) ? (r.lines[i] as Partial<GearLine> | undefined) : undefined;
    return {
      stat: typeof l?.stat === "string" && l.stat ? l.stat : NONE_STAT,
      value: typeof l?.value === "number" && Number.isFinite(l.value) && l.value >= 0 ? l.value : null,
    };
  });
  return { attack, lines };
}

/** Stored / imported equip state -> well-formed (profiles saved before this tab simply have none). */
export function normalizeEquip(raw: unknown): EquipState {
  const r = (raw && typeof raw === "object" ? raw : {}) as Partial<EquipState>;
  return { current: normalizeSide(r.current), new: normalizeSide(r.new) };
}

export function sideHasContent(s: EquipSide): boolean {
  return (s.attack ?? 0) > 0 || s.lines.some((l) => l.stat !== NONE_STAT && (l.value ?? 0) > 0);
}

const sidePayload = (s: EquipSide) => ({
  attack: s.attack ?? 0,
  lines: s.lines.filter((l) => l.stat !== NONE_STAT).map((l) => ({ stat: l.stat, value: l.value ?? 0 })),
});

export function equipPayload(state: EquipState) {
  return { current: sidePayload(state.current), new: sidePayload(state.new) };
}

// ---- result (mirror api/features.run_equipment) --------------------------------------------------------------------------------------------------------
export interface EquipRow {
  stat: string;
  value: number;
  gain: number; // this line's own DPS gain (value x DPS per unit)
  first: boolean; // first line of its stat (same-stat lines add into one group)
  group: number;
  factor: number;
}
export interface EquipSideResult {
  rows: EquipRow[]; // the fixed Attack line + 5 dropdown lines
  total_gain: number; // DPS
  pct: number; // % of Total DPS
}
export interface EquipResult {
  class_id: string;
  baseline_total: number;
  crit_rate_total: number;
  crit_priced_as_crit_damage: boolean;
  rate_by_stat: Record<string, number>;
  current: EquipSideResult;
  new: EquipSideResult;
  delta_pct: number; // new % - current %
  delta_dps: number;
  better: "new" | "current" | "equal";
}

const same = (a: string, b: string) => a.toLowerCase() === b.toLowerCase();
export const ATTACK_STAT = "Attack (flat)";

/** Port of engine/equipment.py ``evaluate_equip`` (same-stat lines add, different stats multiply).  Real answers come from the API; this serves mock mode and is
 *  tested against a real engine case. */
export function evaluateSide(side: { attack: number; lines: { stat: string; value: number }[] }, rate: Record<string, number>, total: number): EquipSideResult {
  const items: [string, number][] = [[ATTACK_STAT, side.attack || 0]];
  for (const l of side.lines.slice(0, EQUIP_LINES)) items.push([l.stat || NONE_STAT, l.value || 0]);
  while (items.length < 1 + EQUIP_LINES) items.push([NONE_STAT, 0]);
  const rows: EquipRow[] = items.map(([stat, value], i) => ({
    stat,
    value,
    gain: i === 0 ? value * (rate[stat] ?? 0) : stat === NONE_STAT ? 0 : value * (rate[stat] ?? 0),
    first: false,
    group: 0,
    factor: 1,
  }));
  rows.forEach((r, i) => {
    r.first = i === 0 ? true : r.stat !== NONE_STAT && !rows.slice(0, i).some((o) => same(o.stat, r.stat));
    r.group = rows.filter((o) => same(o.stat, r.stat)).reduce((a, o) => a + o.gain, 0);
    r.factor = r.first ? 1 + r.group / total : 1;
  });
  const prod = rows.reduce((a, r) => a * r.factor, 1);
  const gain = total * (prod - 1);
  return { rows, total_gain: gain, pct: (gain / total) * 100 };
}

export function compareEquip(body: ReturnType<typeof equipPayload>, rate: Record<string, number>, total: number) {
  const current = evaluateSide(body.current, rate, total);
  const nw = evaluateSide(body.new, rate, total);
  const delta = nw.pct - current.pct;
  return { current, new: nw, delta_pct: delta, delta_dps: nw.total_gain - current.total_gain, better: (delta > 0 ? "new" : delta < 0 ? "current" : "equal") as EquipResult["better"] };
}

/** One-line verdict of a result. */
export function equipVerdict(r: Pick<EquipResult, "better" | "delta_pct">): string {
  if (r.better === "equal") return "Both equips are worth the same.";
  const pct = Math.abs(r.delta_pct);
  const txt = pct >= 0.01 ? pct.toFixed(2) : pct.toExponential(1);
  return r.better === "new" ? `The new equip is better: +${txt}% of Total DPS.` : `Your current equip is better: the new one loses ${txt}% of Total DPS.`;
}
