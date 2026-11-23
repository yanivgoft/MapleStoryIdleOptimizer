// Stat values (sensitivity) logic: types of POST /api/classes/{id}/sensitivity, ranking / sorting, formatting and the lazy-loading plan.
// Pure functions only (the hook lives in lib/useSensitivity.ts); everything here is covered by sensitivity.test.ts.
import { formatNumber } from "./format";

// ---- types (mirror engine/sensitivity.py's JSON; see src/fixtures/fp_mage.sensitivity.json) ---------------------------------------------------
export type SensPart = "stats" | "artifacts" | "companions" | "summon_time" | "cdr";
export const SENS_PARTS: SensPart[] = ["stats", "artifacts", "companions", "summon_time", "cdr"];

export type StatKind = "flat" | "pct" | "mult" | "dr150" | "dr100" | "level";

export interface StatRow {
  key: string;
  label: string;
  type: StatKind;
  current: number;
  new: number;
  baseline_total: number;
  new_total: number;
  dps_gain: number; // "DPS per +1": total DPS gained by ONE step of the stat
  pct_gain: number; // "100 + gain" convention (100 = no change)
  units_per_1pct: number | null; // units of the stat for +1% DPS; LOWER = more valuable per unit; null = n/a
  boss_ratio: number;
  normal_ratio: number;
  semantics: string | null;
  strip_reused: boolean; // the block reused the baseline Status Effect / KO timeline (workbook semantics)
  summon_time_pinned: boolean; // the block kept the baseline's companion summon-time choice
}

export interface StatsPart {
  baseline_total: number;
  baseline_boss_total: number;
  baseline_normal_total: number;
  normal_weight: number;
  rows: StatRow[];
}

export interface ArtifactRow {
  key: string;
  label: string;
  rank: string; // Epic / Unique / Legendary / Mystic
  effect: string; // live | reference_only | no_dps_effect
  no_dps_effect: boolean;
  reason: string | null;
  equipped: boolean;
  star: number;
  unlocked: boolean;
  potential_gain: number;
  baked_into_inputs: boolean;
  new_total: number;
  ratio: number;
  dps_gain: number;
  pct_gain: number; // 100 + gain
  rank_position: number | null;
}

export interface ArtifactsPart {
  baseline_total: number;
  rows: ArtifactRow[];
  ranking: string[];
}

export interface CompanionRow {
  name: string;
  level: number;
  unlocked: boolean;
  dps_gain: number;
  pct_gain: number; // 100 + gain
  companion_dps: number;
  companion_boss_dps: number;
  companion_normal_dps: number;
  rank_position: number | null;
}

export interface CompanionsPart {
  baseline_total: number;
  chosen: string;
  chosen_level: number;
  current_companion_dps: number;
  rows: CompanionRow[];
  ranking: string[];
}

export interface SummonRow {
  total_pct: number;
  summon_time_increase_pct: number;
  companion_dps: number;
  best_candidate: number;
  summon_time_s: number;
  window_s: number;
  avg_boss_dps_change: number | null; // fractions (0.05 = +5%); null outside boss-phase contents
  boss_phase_time_factor: number | null;
  boss_damage_change: number | null;
  normal_dps_change: number;
  weighted_dps_change: number;
}

export interface SummonPart {
  b0: number;
  companion: string;
  companion_level: number;
  boss_phase_content: boolean;
  rows: SummonRow[];
}

export interface CdrRow {
  cdr: number;
  total_dps: number;
  step_gain: number;
  pct_gain: number; // already a percentage (7.2 = +7.2%)
}

export interface CdrPart {
  baseline_total: number;
  current_cdr: number;
  rows: CdrRow[];
  note: string;
}

export interface SensitivityResult {
  class_id: string;
  content_type: string;
  baseline_total: number;
  baseline_boss_total: number;
  baseline_normal_total: number;
  normal_weight: number;
  semantics: string;
  stats?: StatsPart;
  artifacts?: ArtifactsPart;
  companions?: CompanionsPart;
  summon_time?: SummonPart;
  cdr?: CdrPart;
}

export interface SensitivityMeta {
  class_id: string;
  parts: SensPart[];
  stats: { key: string; label: string; type: StatKind; step: string; semantics: string | null }[];
  artifacts: { key: string; label: string; rank: string; effect: string; no_dps_effect: boolean; reason: string | null }[];
  cdr_values: number[];
  metric: Record<string, string>;
}

// ---- formatting ------------------------------------------------------------------------------------------------------------------------------
const MINUS = "−";

/** Short step text of a stat type ("+1", "+1 pp", "x1.01" ...); `step` of the meta endpoint is the long form (tooltips). */
export const STEP_SHORT: Record<StatKind, string> = { flat: "+1", pct: "+1 pp", level: "+1 lvl", mult: "×1.01", dr150: "+1 (DR 150)", dr100: "+1 (DR 100)" };
export const STEP_LONG: Record<StatKind, string> = {
  flat: "+1",
  pct: "+1 percentage point",
  level: "+1 skill level",
  mult: "x1.01 (multiplicative source)",
  dr150: "+1 combined by diminishing returns (factor 150)",
  dr100: "+1 combined by diminishing returns (factor 100)",
};

/** Significant-digit number without exponent and without trailing zeros ("0.0123", "1.5", "1000"). */
export function sig(value: number, digits = 3): string {
  if (!Number.isFinite(value)) return "–";
  if (value === 0) return "0";
  const abs = Math.abs(value);
  if (abs >= 10 ** digits) return Math.round(value).toLocaleString("en-US");
  return String(Number(value.toPrecision(digits)));
}

/** "Units per +1% DPS": "n/a" when the stat gives no gain (null, or <= 0: the engine reports a negative value for a stat that lowers DPS). */
export function formatUnits(units: number | null | undefined): string {
  if (units === null || units === undefined || !Number.isFinite(units) || units <= 0) return "n/a";
  if (units >= 1e6) return formatNumber(units, 3);
  return sig(units, 3);
}

/** Signed percentage points: "+0.020%", "−2.50%", "+135%" (input is a percent value, not a fraction). */
export function signedPct(pp: number | null | undefined): string {
  if (pp === null || pp === undefined || !Number.isFinite(pp)) return "–";
  const abs = Math.abs(pp);
  if (abs === 0) return "0%";
  if (abs < 0.001) return "≈0%";
  const body = abs >= 100 ? abs.toFixed(0) : abs >= 10 ? abs.toFixed(1) : abs >= 1 ? abs.toFixed(2) : abs.toPrecision(2);
  return `${pp < 0 ? MINUS : "+"}${body}%`;
}

/** A "100 + gain" value (the workbook's % Gain column) as a signed gain: 105.94 -> "+5.94%". */
export function gainPct(pct100: number | null | undefined): string {
  return pct100 === null || pct100 === undefined ? "–" : signedPct(pct100 - 100);
}

/** Signed compact DPS amount: "+190", "-2.18K". */
export function signedNumber(v: number | null | undefined): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "–";
  if (v === 0) return "0";
  return `${v < 0 ? MINUS : "+"}${formatNumber(Math.abs(v))}`;
}

/** A stat's current / new value for the table (flat values compact, percentages with up to 2 decimals). */
export function formatStatValue(v: number | null | undefined): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "–";
  if (Math.abs(v) >= 1000) return formatNumber(v, 4);
  return String(Number(v.toFixed(2)));
}

// ---- stats table -----------------------------------------------------------------------------------------------------------------------------
export type StatSort = "value" | "order" | "name";
export const STAT_SORTS: { id: StatSort; label: string }[] = [
  { id: "value", label: "Best value first" },
  { id: "order", label: "Workbook order" },
  { id: "name", label: "Name" },
];

/** Percentage points one step adds (pct_gain - 100); this is what "units per +1%" inverts. */
export function stepGainPp(r: Pick<StatRow, "pct_gain">): number {
  return r.pct_gain - 100;
}

/** A row's value per unit is meaningful only when one step helps. */
export function hasValue(r: Pick<StatRow, "pct_gain" | "units_per_1pct">): boolean {
  return r.units_per_1pct !== null && r.units_per_1pct > 0 && stepGainPp(r) > 0;
}

/**
 * Rows in display order.  "value": fewest units for +1% DPS first (units_per_1pct ascending == % gain per step descending); stats without any gain
 * (n/a) sink to the bottom in workbook order.  The input is not mutated.
 */
export function sortStats(rows: StatRow[], sort: StatSort = "value"): StatRow[] {
  const idx = new Map(rows.map((r, i) => [r.key, i]));
  const byOrder = (a: StatRow, b: StatRow) => idx.get(a.key)! - idx.get(b.key)!;
  const out = [...rows];
  if (sort === "order") return out.sort(byOrder);
  if (sort === "name") return out.sort((a, b) => a.label.localeCompare(b.label) || byOrder(a, b));
  return out.sort((a, b) => {
    const ha = hasValue(a);
    const hb = hasValue(b);
    if (ha !== hb) return ha ? -1 : 1;
    if (!ha) return byOrder(a, b);
    return (a.units_per_1pct as number) - (b.units_per_1pct as number) || byOrder(a, b);
  });
}

/** Bar length 0..1 per stat key: the step gain relative to the best stat's (0 for stats without gain). */
export function relativeValues(rows: StatRow[]): Map<string, number> {
  const best = Math.max(0, ...rows.map((r) => (hasValue(r) ? stepGainPp(r) : 0)));
  return new Map(rows.map((r) => [r.key, best > 0 && hasValue(r) ? stepGainPp(r) / best : 0]));
}

/** Chips / tooltip lines explaining how the workbook's block differs from a plain re-run of the stat. */
export function statNotes(r: StatRow): string[] {
  const out: string[] = [];
  if (r.semantics) out.push(r.semantics);
  if (r.strip_reused) out.push("reuses the baseline Status Effect / KO timeline (exact: this stat does not move timing)");
  else out.push("re-runs the timeline (this stat moves cooldowns, buff values or damage weights)");
  if (r.summon_time_pinned) out.push("keeps the baseline's companion summon-time choice");
  else out.push("searches the companion summon-time candidates again");
  return out;
}

/**
 * Visible chips of a row.  A block either reuses the baseline's Status / KO timeline or re-solves it (`strip_reused`; when NO row reuses it the content has
 * no timeline, so nothing is flagged), and either keeps the baseline's companion summon-time choice or searches again (`summon_time_pinned`, same rule).
 */
export function statFlags(r: StatRow, all: StatRow[]): string[] {
  const out: string[] = [];
  if (!r.strip_reused && all.some((x) => x.strip_reused)) out.push("timing re-run");
  if (!r.summon_time_pinned && all.some((x) => x.summon_time_pinned)) out.push("summon time re-searched");
  return out;
}

// ---- artifact equip ranking ------------------------------------------------------------------------------------------------------------------
export type EquipGroup = "ranked" | "no_effect" | "locked";

export interface EquipEntry {
  group: EquipGroup;
  row: ArtifactRow;
}

/**
 * Display order of the equip toggles: unlocked artifacts with an effect first (by the engine's rank_position, best % gain first), then unlocked artifacts
 * with no DPS effect (greyed, with their reason), then not-unlocked ones (greyed; their values are what-ifs at star 0 and unranked).
 */
export function rankEquip(rows: ArtifactRow[], opts: { includeLocked?: boolean; includeNoEffect?: boolean } = {}): EquipEntry[] {
  const { includeLocked = true, includeNoEffect = true } = opts;
  const idx = new Map(rows.map((r, i) => [r.key, i]));
  const byOrder = (a: ArtifactRow, b: ArtifactRow) => idx.get(a.key)! - idx.get(b.key)!;
  const ranked = rows
    .filter((r) => r.unlocked && !r.no_dps_effect)
    .sort((a, b) => (a.rank_position ?? 1e9) - (b.rank_position ?? 1e9) || b.pct_gain - a.pct_gain || byOrder(a, b));
  const noEffect = rows.filter((r) => r.unlocked && r.no_dps_effect).sort(byOrder);
  const locked = rows.filter((r) => !r.unlocked).sort(byOrder);
  return [
    ...ranked.map((row) => ({ group: "ranked" as const, row })),
    ...(includeNoEffect ? noEffect.map((row) => ({ group: "no_effect" as const, row })) : []),
    ...(includeLocked ? locked.map((row) => ({ group: "locked" as const, row })) : []),
  ];
}

/** Why a row reads the way it does ("equipped: value of keeping it" / what-if notes), for the row tooltip. */
export function equipNote(r: ArtifactRow): string {
  const parts: string[] = [];
  if (r.no_dps_effect) parts.push(r.reason || "no DPS effect in the model");
  if (!r.unlocked) parts.push("not unlocked: what-if at star 0, not ranked");
  if (r.equipped) parts.push("equipped: the gain is what you lose if you remove it (same % either direction)");
  if (r.baked_into_inputs) parts.push("its stat is typed into Inputs: the gain is a what-if on top of your typed values");
  if (r.potential_gain) parts.push(`includes ${formatNumber(r.potential_gain)} DPS from its potential lines`);
  return parts.join(". ");
}

// ---- companions / summon time / cdr ----------------------------------------------------------------------------------------------------------
/** Companion rows best first (engine rank_position); companions at level 0 (not unlocked) last in table order. */
export function sortCompanions(rows: CompanionRow[]): CompanionRow[] {
  const idx = new Map(rows.map((r, i) => [r.name, i]));
  return [...rows].sort((a, b) => {
    if (a.unlocked !== b.unlocked) return a.unlocked ? -1 : 1;
    return (a.rank_position ?? 1e9) - (b.rank_position ?? 1e9) || idx.get(a.name)! - idx.get(b.name)!;
  });
}

// ---- lazy loading plan -----------------------------------------------------------------------------------------------------------------------
/** Parts still to request: wanted but not loaded yet (canonical order). */
export function missingParts(loaded: Iterable<SensPart>, wanted: Iterable<SensPart>): SensPart[] {
  const have = new Set(loaded);
  const want = new Set(wanted);
  return SENS_PARTS.filter((p) => want.has(p) && !have.has(p));
}

/** Parts of a result actually present. */
export function loadedParts(result: Partial<SensitivityResult> | null | undefined): SensPart[] {
  return result ? SENS_PARTS.filter((p) => result[p] !== undefined) : [];
}

/** Merge a (partial) answer into what is already loaded for the same inputs. */
export function mergeResult(prev: SensitivityResult | null, next: SensitivityResult): SensitivityResult {
  return prev ? { ...prev, ...next } : next;
}

/** Request body of POST /sensitivity: the compute inputs + `which`. */
export function sensitivityBody(inputs: Record<string, unknown>, which: SensPart[]): Record<string, unknown> {
  return { ...inputs, which };
}
