// Cubes tab logic (pure): types of GET .../cubes/meta and POST .../cubes, the editable gear state, request building, the exact cube count, ranking and the "worth rolling?" rule.
import { parseNumber } from "./schemaForm";
import xlsxMap from "./xlsx_map.json";

export const NONE_STAT = "(none)";
export const POTENTIAL_TYPES = ["Potential", "Bonus Potential"] as const;

// ---- types (mirror api/features.py + engine/cubes.py; see src/fixtures/fp_mage.cubes_meta.json / .cubes_case.json) ----------------------------------------------
export interface SlotMeta {
  key: string;
  label: string;
}
export interface RarityMeta {
  key: string;
  label: string;
}
export interface EquipmentMeta {
  stats: string[]; // the 21 dropdown stats
  lines: number; // 5 dropdown lines per equip (+ the fixed Attack line)
  attack_stat: string;
  none_stat: string;
}
export interface PotentialArtifactMeta {
  key: string;
  label: string;
  rank: string; // Epic / Unique / Legendary
  lines: number; // 2 (Epic / Unique) or 3 (Legendary)
  default_star: number | string;
}
export interface ArtifactPotentialMeta {
  rarities: string[];
  stats: string[];
  values: Record<string, Record<string, number>>; // stat -> rarity -> value of one line
  line_min_star: number[]; // star at which line 1 / 2 / 3 become active
  default_rarity: string;
  none_stat: string;
  star_options: (number | string)[];
  artifacts: PotentialArtifactMeta[];
}
/** "ALL" (the pool shared by every slot) or a slot key -> rarity -> line "1".."3" -> stat -> [value, prime] pairs */
export type RollValues = Record<string, Record<string, Record<string, Record<string, [number, boolean][]>>>>;
export interface CubesMeta {
  class_id: string;
  slots: SlotMeta[];
  potential_types: string[];
  rarities: RarityMeta[];
  none_stat: string;
  stats: string[]; // every stat selectable on a line
  stats_by_slot: Record<string, string[]>; // stats that can actually roll in the slot
  /** the values a line can show: "ALL" (the pool shared by every slot) or a slot key (that slot's own additions) -> rarity -> line "1".."3" -> stat -> [value, prime] pairs;
   *  merged for one (slot, rarity, line, stat) by `rollValueOptions`.  Absent in an old cached meta (the value stays a typed number then). */
  roll_values?: RollValues;
  pity_caps: Record<string, Record<string, number>>; // potential type -> rarity -> cubes that force the upgrade (0 = top tier)
  upgrade_rates: Record<string, Record<string, number>>;
  milestones: number[];
  max_cubes: number;
  csv_columns: string[];
  max_rows: number;
  limits: { max_pity: number; max_line_value: number };
  equipment: EquipmentMeta;
  artifact_potentials: ArtifactPotentialMeta;
}

export interface GearLine {
  stat: string;
  value: number | null;
}
export interface GearRowState {
  rarity: string;
  pity: number | null;
  lines: GearLine[]; // always 3
}
/** The PotentialCubes sheet: one entry per (slot, potential type) the user touched (`gearKey`); a missing one is blank (normal, pity 0, no lines). */
export type CubesState = Record<string, GearRowState>;

export interface CubeRow {
  slot: string;
  potential_type: string;
  rarity: string;
  pity: number;
  lines: [string, number][];
  current_value: number; // DPS
  current_value_pct: number;
  smallest_n: number | null; // first cube count with positive EV, null = never within max_cubes
  n_for_50pct: number | null; // cubes for a 50% / 75% chance that at least one reroll beats the current value
  n_for_75pct: number | null;
  milestone_ev: Record<string, number>; // EV (DPS) per cube count, keys are the milestones
  milestone_ev_pct: Record<string, number>; // EV as % of the current Total DPS
  /** EV as % of the current Total DPS after n cubes for EVERY n = 0..max_cubes (index n = n cubes, ~6 significant digits); absent in old cached rows / mock fixtures */
  ev_pct_by_cubes?: number[];
}
export interface CubesResult {
  class_id: string;
  baseline_total: number;
  milestones: number[];
  csv_columns: string[];
  backend: string;
  rows: CubeRow[];
  notes: string[];
}

export interface GearPayloadRow {
  slot: string;
  potential_type: string;
  rarity: string;
  pity: number;
  lines: { stat: string; value: number }[];
}
export interface RowRef {
  slot: string;
  potential_type: string;
}

// ---- state ----------------------------------------------------------------------------------------------------------------------------------------
export const gearKey = (slot: string, type: string) => `${slot}|${type}`;
export const emptyLine = (): GearLine => ({ stat: NONE_STAT, value: null });
export const blankRow = (): GearRowState => ({ rarity: "normal", pity: null, lines: [emptyLine(), emptyLine(), emptyLine()] });

export function getRow(state: CubesState | undefined, slot: string, type: string): GearRowState {
  return state?.[gearKey(slot, type)] ?? blankRow();
}

export function setRow(state: CubesState | undefined, slot: string, type: string, row: GearRowState): CubesState {
  return { ...(state ?? {}), [gearKey(slot, type)]: row };
}

export function setLine(row: GearRowState, i: number, patch: Partial<GearLine>): GearRowState {
  return { ...row, lines: row.lines.map((l, j) => (j === i ? { ...l, ...patch } : l)) };
}

/** Did the user enter anything for this row (a rarity above normal, a pity count or a line)? */
export function isConfigured(row: GearRowState): boolean {
  return row.rarity !== "normal" || (row.pity ?? 0) > 0 || row.lines.some((l) => l.stat !== NONE_STAT);
}

/** Make a stored / imported value well-formed (profiles may hold anything): unknown shapes are dropped, numbers clamped, three lines each, and a line value that is
 *  not one of the values the game rolls for (slot, rarity, line, stat) is cleared (a line with exactly one possible value gets it). */
export function normalizeCubesState(raw: unknown, rollValues: RollValues = STATIC_ROLL_VALUES): CubesState {
  const out: CubesState = {};
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return out;
  for (const [k, v] of Object.entries(raw as Record<string, unknown>)) {
    if (!/^[a-z0-9-]+\|[A-Za-z ]+$/.test(k) || !v || typeof v !== "object") continue;
    const r = v as Partial<GearRowState>;
    const pity = typeof r.pity === "number" && Number.isFinite(r.pity) && r.pity >= 0 ? Math.floor(r.pity) : null;
    const lines: GearLine[] = [0, 1, 2].map((i) => {
      const l = Array.isArray(r.lines) ? (r.lines[i] as Partial<GearLine> | undefined) : undefined;
      const stat = typeof l?.stat === "string" && l.stat ? l.stat : NONE_STAT;
      const value = typeof l?.value === "number" && Number.isFinite(l.value) && l.value >= 0 ? l.value : null;
      return { stat, value };
    });
    const rarity = typeof r.rarity === "string" && r.rarity ? r.rarity : "normal";
    const slot = k.split("|")[0];
    out[k] = { rarity, pity, lines: lines.map((l, i) => sanitizeLine(rollValues, slot, rarity, i, l).line) };
  }
  return out;
}

// ---- pity / meta helpers ------------------------------------------------------------------------------------------------------------------------
/** The pity cap (cubes that force the next rarity) of a rarity in a potential type; 0 = the top tier, nothing left to upgrade to. */
export function pityCap(meta: CubesMeta | null, type: string, rarity: string): number {
  return meta?.pity_caps?.[type]?.[rarity] ?? 0;
}

export function pityHint(meta: CubesMeta | null, type: string, rarity: string): string {
  const cap = pityCap(meta, type, rarity);
  return cap > 0 ? `cap ${cap}` : "top tier";
}

/** Stats offered on a line of `slot`: ONLY the stats that piece of equipment can roll (`stats_by_slot`).  The engine's roll tables are keyed by slot and rarity,
 *  not by track, so Potential and Bonus Potential share the list.  Slot-exclusive stats (Skill Cooldown Decrease on the hat, Buff Duration Increase on the belt,
 *  Basic Attack Target Increase on the chest, ...) appear only on their slot; a stored line outside the list is handled by `statChoices`. */
export function statOptions(meta: CubesMeta, slot: string): string[] {
  return meta.stats_by_slot[slot] ?? meta.stats;
}

export interface StatChoice {
  value: string;
  label: string;
  /** the current value cannot roll here: kept so no data is lost, shown with a warning */
  warn?: boolean;
}
export const NOT_ROLLABLE_ON_SLOT = "not rollable on this slot";
export const NOT_ROLLABLE_ON_ARTIFACTS = "not rollable on artifacts";
/** Dropdown entries of one stat select: "(none)", the stats that can roll, and - only when the current value is neither - that value as a single flagged entry
 *  "<stat> (not rollable ...)" (an old profile / an Excel import may hold one; it is never offered otherwise). */
export function statChoices(rollable: string[], current: string, notRollable?: string, none = NONE_STAT): StatChoice[] {
  const out: StatChoice[] = [{ value: none, label: none }];
  if (current !== none && !rollable.includes(current)) out.push(notRollable ? { value: current, label: `\u26A0 ${current} (${notRollable})`, warn: true } : { value: current, label: current });
  for (const s of rollable) out.push({ value: s, label: s });
  return out;
}

// ---- the values a line can roll ---------------------------------------------------------------------------------------------------------------------
/** The class-independent roll tables (the same in every class's cube meta; `gen_xlsx_map.py --check` keeps this copy equal to the fixtures).  Used when a meta has none
 *  and where no meta is at hand (profile repair, the Excel import). */
export const STATIC_ROLL_VALUES = (xlsxMap as unknown as { cubeTables: { rollValues: RollValues } }).cubeTables.rollValues;

export interface ValueOption {
  value: number;
  prime: boolean;
  label: string;
}
const fmtValue = (v: number) => String(Number(v.toFixed(6)));

/** The values a line can show for (slot, rarity, line position, stat), prime first then descending: the shared pool of `roll_values` plus the slot's own
 *  additions, equal values merged (prime if any of them is).  `line` is 0-based (Line 1 = 0).  Empty = no table entry (no stat, or a stat that does not roll on that
 *  slot / rarity / line). */
export function rollOptionsIn(rv: RollValues, slot: string, rarity: string, line: number, stat: string): ValueOption[] {
  if (stat === NONE_STAT) return [];
  const byValue = new Map<number, boolean>();
  for (const key of ["ALL", slot]) {
    for (const [v, prime] of rv[key]?.[rarity]?.[String(line + 1)]?.[stat] ?? []) byValue.set(v, (byValue.get(v) ?? false) || prime);
  }
  return [...byValue]
    .map(([value, prime]) => ({ value, prime, label: fmtValue(value) }))
    .sort((a, b) => Number(b.prime) - Number(a.prime) || b.value - a.value);
}
export function rollValueOptions(meta: CubesMeta | null, slot: string, rarity: string, line: number, stat: string): ValueOption[] {
  return rollOptionsIn(meta?.roll_values ?? STATIC_ROLL_VALUES, slot, rarity, line, stat);
}

/** The value picked for you when a stat is chosen: the one prime option, else the only option; null = the user must choose. */
export function autoValue(options: ValueOption[]): number | null {
  const primes = options.filter((o) => o.prime);
  if (primes.length === 1) return primes[0].value;
  return options.length === 1 ? options[0].value : null;
}

/** A line made consistent with the roll tables: a value that is not one of the allowed values for (slot, rarity, line, stat) is cleared (`cleared` = it was a real
 *  number that got dropped); a blank value on a line with exactly ONE allowed value gets that value; a stat without any table entry keeps its value untouched (it is
 *  shown flagged, without a value input). */
export function sanitizeLine(rv: RollValues, slot: string, rarity: string, line: number, l: GearLine): { line: GearLine; cleared: boolean } {
  if (l.stat === NONE_STAT) return { line: l.value === null ? l : { stat: l.stat, value: null }, cleared: false };
  const options = rollOptionsIn(rv, slot, rarity, line, l.stat);
  if (options.length === 0) return { line: l, cleared: false };
  if (l.value !== null && options.some((o) => Math.abs(o.value - l.value!) < 1e-9)) return { line: l, cleared: false };
  const cleared = l.value !== null;
  return { line: { stat: l.stat, value: options.length === 1 ? options[0].value : null }, cleared };
}

/** The line after the user picked `stat` for line `line` (0-based): "(none)" clears the value; a stat with a value table gets its auto value (or blank); a stat
 *  without a table entry gets no value. */
export function lineWithStat(meta: CubesMeta | null, slot: string, rarity: string, line: number, _current: GearLine, stat: string): GearLine {
  if (stat === NONE_STAT) return { stat, value: null };
  return { stat, value: autoValue(rollValueOptions(meta, slot, rarity, line, stat)) };
}

/** The row after the user picked another rarity: the allowed stats and values differ per rarity, so all three lines are emptied. */
export function withRarity(row: GearRowState, rarity: string): GearRowState {
  return { ...row, rarity, lines: [emptyLine(), emptyLine(), emptyLine()] };
}

export function slotLabel(meta: CubesMeta | null, slot: string): string {
  return meta?.slots.find((s) => s.key === slot)?.label ?? slot;
}
export function rarityLabel(meta: CubesMeta | null, rarity: string): string {
  return meta?.rarities.find((r) => r.key === rarity)?.label ?? rarity;
}

// ---- request building ---------------------------------------------------------------------------------------------------------------------------
/** Rows to calculate: the configured ones (or, with `includeBlank`, all 15 slots x 2 types), in sheet order. */
export function rowsToCalculate(meta: CubesMeta, state: CubesState | undefined, includeBlank: boolean): RowRef[] {
  const out: RowRef[] = [];
  for (const s of meta.slots) {
    for (const t of meta.potential_types) {
      if (includeBlank || isConfigured(getRow(state, s.key, t))) out.push({ slot: s.key, potential_type: t });
    }
  }
  return out;
}

/** The `gear` body of POST .../cubes: every configured row (the other rows' lines matter for summoning-time baselines even when they are not recalculated). */
export function gearPayload(meta: CubesMeta, state: CubesState | undefined): GearPayloadRow[] {
  const out: GearPayloadRow[] = [];
  for (const s of meta.slots) {
    for (const t of meta.potential_types) {
      const r = getRow(state, s.key, t);
      if (!isConfigured(r)) continue;
      out.push({
        slot: s.key,
        potential_type: t,
        rarity: r.rarity,
        pity: Math.max(0, Math.floor(r.pity ?? 0)),
        lines: r.lines.filter((l) => l.stat !== NONE_STAT).map((l) => ({ stat: l.stat, value: l.value ?? 0 })),
      });
    }
  }
  return out;
}

export function chunk<T>(items: T[], size: number): T[][] {
  const out: T[][] = [];
  for (let i = 0; i < items.length; i += Math.max(1, size)) out.push(items.slice(i, i + Math.max(1, size)));
  return out;
}

/** Rows per request of a Calculate run: 6 rows (3 slots) = 5 requests for the whole sheet, comfortably under the API's 20 per minute for cube calls. */
export const CUBES_CHUNK_ROWS = 6;

/** Parse a line / pity / attack input: blank = null, otherwise a non-negative number (the API's own bounds are re-checked server side). */
export function parseNonNegative(text: string, whole = false, max: number | null = null) {
  return parseNumber(text, whole ? "int" : "float", 0, max);
}

// ---- the cube count the user typed -----------------------------------------------------------------------------------------------------------------
export const DEFAULT_CUBE_COUNT = 100;
export const MIN_CUBE_COUNT = 1;

export interface CubeCountParse {
  value: number | null; // the count when the text is valid
  error: string | null;
}

/** "Cubes you have": a whole number from 1 to `max` (the most cubes the calculation covers).  Typing like "86" or "1,000" works; blank, decimals, text and
 *  out-of-range numbers give a message and no value. */
export function parseCubeCount(text: string, max = 1000): CubeCountParse {
  const msg = `Enter a whole number of cubes from ${MIN_CUBE_COUNT} to ${max}`;
  const t = text.trim().replace(/,/g, "");
  if (t === "") return { value: null, error: msg };
  if (!/^\d+$/.test(t)) return { value: null, error: /^\d*\.\d+$/.test(t) ? "Whole cubes only: enter a number like 86" : msg };
  const n = Number(t);
  if (n < MIN_CUBE_COUNT || n > max) return { value: null, error: msg };
  return { value: n, error: null };
}

/** What the "Cubes you have" box remembers: the text as typed and the last valid count (the table keeps using it while the text is invalid). */
export interface CubeCountState {
  text: string;
  good: number;
}
export const initialCubeCount = (): CubeCountState => ({ text: String(DEFAULT_CUBE_COUNT), good: DEFAULT_CUBE_COUNT });

/** The box after the user typed `text`: the text always follows the typing; the count changes only when the text is valid. */
export function typeCubeCount(prev: CubeCountState, text: string, max = 1000): CubeCountState {
  const { value } = parseCubeCount(text, max);
  return { text, good: value ?? prev.good };
}

/** The count to price the table for: the typed one when valid, else the last valid one (never above `max`). */
export function effectiveCubeCount(c: CubeCountState, max = 1000): number {
  return parseCubeCount(c.text, max).value ?? Math.min(c.good, max);
}

// ---- results ---------------------------------------------------------------------------------------------------------------------------------------
/** Largest preset milestone <= n among a row's milestone keys (EV never decreases with more cubes, so it is a safe lower bound); null = none that small. */
function milestoneFloor(record: Record<string, number>, n: number): number | null {
  let best: number | null = null;
  for (const k of Object.keys(record)) {
    const m = Number(k);
    if (m <= n && (best === null || m > best)) best = m;
  }
  return best;
}

/** EV as % of Total DPS after exactly `n` cubes: from the full per-count curve when the row has one, else from the preset milestones (the largest one not above n). */
export function evPctAt(row: CubeRow, n: number): number {
  const curve = row.ev_pct_by_cubes;
  if (curve && curve.length > 0) return curve[Math.max(0, Math.min(Math.floor(n), curve.length - 1))] ?? 0;
  const key = milestoneFloor(row.milestone_ev_pct, n);
  return key === null ? 0 : row.milestone_ev_pct[String(key)] ?? 0;
}

/** EV in DPS after `n` cubes: derived from the % and the baseline Total DPS when the row has the full curve, else from the milestone values. */
export function evAt(row: CubeRow, n: number, baseline?: number | null): number {
  if (row.ev_pct_by_cubes && row.ev_pct_by_cubes.length > 0 && baseline) return (evPctAt(row, n) / 100) * baseline;
  const key = milestoneFloor(row.milestone_ev, n);
  return key === null ? 0 : row.milestone_ev[String(key)] ?? 0;
}

/** The preset-milestone values exactly as the API sends them (the CSV keeps these columns). */
/** Columns of the API's CSV that are absolute DPS amounts: not exported. */
const ABSOLUTE_CSV_COLUMN = /^(CurrentValue|EV@\d+)$/;
const msEv = (row: CubeRow, n: number): number => row.milestone_ev[String(n)] ?? 0;
const msEvPct = (row: CubeRow, n: number): number => row.milestone_ev_pct[String(n)] ?? 0;

export type Verdict = "yes" | "maybe" | "marginal" | "no";
export interface Worth {
  verdict: Verdict;
  label: string;
  why: string;
}

/** EV at the chosen cube count, in % of Total DPS, at which rolling is a clear yes / a maybe. */
export const WORTH_YES_PCT = 1;
export const WORTH_MAYBE_PCT = 0.1;

/**
 * "Worth rolling?" - a plain rule on the API's fields, for exactly `n` cubes:
 *  - `smallest_n` null: no cube count up to the maximum has a positive expected gain -> No (this line set is at or near the best the slot can roll);
 *  - expected gain at `n` cubes (EV, kept only when better: you never accept a worse roll) of at least 1% Total DPS -> Yes;
 *  - at least 0.1% -> Maybe (worth it only when cubes are cheap or the slot is your weakest one);
 *  - otherwise Marginal (a positive but tiny expected gain).
 * The rule knows nothing about what a cube costs you; it ranks, you decide.
 */
export function worthRolling(row: CubeRow, n: number): Worth {
  if (row.smallest_n === null) {
    return { verdict: "no", label: "No", why: "No number of cubes gives a positive average gain: the current lines are at or near the best this slot can roll." };
  }
  const pct = evPctAt(row, n);
  if (pct >= WORTH_YES_PCT) return { verdict: "yes", label: "Yes", why: `On average +${pct.toFixed(2)}% Total DPS after ${n} cubes (rule: at least ${WORTH_YES_PCT}%).` };
  if (pct >= WORTH_MAYBE_PCT) {
    return { verdict: "maybe", label: "Maybe", why: `On average +${pct.toFixed(2)}% Total DPS after ${n} cubes (between ${WORTH_MAYBE_PCT}% and ${WORTH_YES_PCT}%).` };
  }
  return { verdict: "marginal", label: "Marginal", why: `On average only +${pct.toFixed(3)}% Total DPS after ${n} cubes (under ${WORTH_MAYBE_PCT}%); the first positive gain comes after ${row.smallest_n} cubes.` };
}

export type CubeSort = "ev" | "smallest_n" | "slot";
export const CUBE_SORTS: { id: CubeSort; label: string }[] = [
  { id: "ev", label: "Best average gain with your cubes" },
  { id: "smallest_n", label: "Fewest cubes until rolling pays off" },
  { id: "slot", label: "Slot order" },
];

export function rankRows(rows: CubeRow[], sort: CubeSort, n: number, meta?: CubesMeta | null): CubeRow[] {
  const slotIdx = (s: string) => {
    const i = meta?.slots.findIndex((x) => x.key === s) ?? -1;
    return i < 0 ? 999 : i;
  };
  const typeIdx = (t: string) => (t === "Potential" ? 0 : 1);
  const never = Number.POSITIVE_INFINITY;
  const copy = [...rows];
  if (sort === "slot") return copy.sort((a, b) => slotIdx(a.slot) - slotIdx(b.slot) || typeIdx(a.potential_type) - typeIdx(b.potential_type));
  if (sort === "smallest_n") return copy.sort((a, b) => (a.smallest_n ?? never) - (b.smallest_n ?? never) || evPctAt(b, n) - evPctAt(a, n));
  return copy.sort((a, b) => evPctAt(b, n) - evPctAt(a, n) || (a.smallest_n ?? never) - (b.smallest_n ?? never));
}

/** Ranked rows split into the two roll tracks, as the cubing script prints them (regular Potential first, then Bonus Potential); the order inside each
 *  group is kept, a group with no rows is left out. */
export function groupByPotentialType(ranked: CubeRow[]): { type: (typeof POTENTIAL_TYPES)[number]; rows: CubeRow[] }[] {
  return POTENTIAL_TYPES.map((type) => ({ type, rows: ranked.filter((r) => r.potential_type === type) })).filter((g) => g.rows.length > 0);
}

/** "never (already near the best)" for a row whose gain never turns positive, else the cube count. */
export function formatUntilPositive(n: number | null): string {
  return n === null ? "never (already near the best)" : String(n);
}

/** Cube count text: null = not reached within the maximum. */
export function formatCubes(n: number | null, max = 1000): string {
  return n === null ? `> ${max}` : String(n);
}

/** EV percentage text with a sign; tiny values keep a decimal so they do not read as 0. */
export function formatEvPct(p: number): string {
  if (!Number.isFinite(p)) return "–";
  if (p === 0) return "0%";
  const abs = Math.abs(p);
  const txt = abs >= 10 ? p.toFixed(1) : abs >= 1 ? p.toFixed(2) : abs >= 0.01 ? p.toFixed(3) : p.toExponential(1);
  return `${p > 0 ? "+" : ""}${txt}%`;
}

/** Lines of a result row as "Damage % 12 | Critical Rate % 3" ("(none)" lines dropped). */
export function linesText(row: CubeRow): string {
  const parts = row.lines.filter(([s]) => s !== NONE_STAT).map(([s, v]) => `${s} ${v}`);
  return parts.length ? parts.join(" | ") : "no lines";
}

/** The key of a result row (slot and track; to tell the rows apart across Calculate runs). */
export const rowKey = (r: { slot: string; potential_type: string }) => gearKey(r.slot, r.potential_type);

/** "Normal 30 / 42, Rare 60 / 75, ..." from the meta's pity caps (Potential / Bonus Potential); the top tier (cap 0) is left out. */
export function pityCapsText(meta: CubesMeta | null): string {
  if (!meta) return "";
  const [a, b] = meta.potential_types;
  return meta.rarities
    .filter((r) => (meta.pity_caps[a]?.[r.key] ?? 0) > 0)
    .map((r) => {
      const pa = meta.pity_caps[a][r.key];
      const pb = meta.pity_caps[b]?.[r.key] ?? pa;
      return pa === pb ? `${r.label} ${pa}` : `${r.label} ${pa} / ${pb}`;
    })
    .join(", ");
}

export function potentialExplainer(meta: CubesMeta | null): string[] {
  return [
    "Potential and Bonus Potential are separate roll tracks: they roll the same lines at the same weights, but their pity caps (the number of cubes after which the next " +
      `rarity is forced) differ - ${pityCapsText(meta) || "see the table"} (Potential / Bonus Potential; where only one number is shown both tracks share it).`,
    "The pity count is how many cubes you have already spent on the current rarity without an upgrade. Every cube re-rolls all 3 lines; the average gain assumes you keep " +
      "the best result so far and stop at the best moment.",
    "Critical Rate lines are priced as Critical Damage once your live crit rate is at or above 100% (the extra crit rate does nothing), unless Ring of Cycles or Book of " +
      "Ancient is equipped - their effects keep growing with crit rate, so it is priced as itself.",
  ];
}

/**
 * The result as CSV, in % of Total DPS only: the API's csv_columns without the absolute-DPS ones ("CurrentValue", "EV@n"); what is left is Slot, PotentialType,
 * Rarity, Pity, CurrentValue%, SmallestNPositive, NFor50PctChance, NFor75PctChance and EV%@n for each preset milestone.
 */
export function cubesCsv(rows: CubeRow[], milestones: number[], columns: string[]): string {
  const cell = (v: unknown) => (v === null || v === undefined ? "" : typeof v === "number" ? String(v) : /[",\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : String(v));
  const keep = columns.map((c) => !ABSOLUTE_CSV_COLUMN.test(c));
  const line = (r: CubeRow) =>
    [r.slot, r.potential_type, r.rarity, r.pity, r.current_value, r.current_value_pct, r.smallest_n, r.n_for_50pct, r.n_for_75pct, ...milestones.map((n) => msEv(r, n)), ...milestones.map((n) => msEvPct(r, n))]
      .filter((_v, i) => keep[i] !== false)
      .map(cell)
      .join(",");
  return [columns.filter((_c, i) => keep[i]).join(","), ...rows.map(line)].join("\n") + "\n";
}
