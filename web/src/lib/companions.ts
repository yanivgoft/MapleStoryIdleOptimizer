// Companions page logic (pure, no React): which companions the user owns and at what level (the workbook's CompanionsInput sheet), the chosen companion of the
// current content type, the request extras of POST .../sensitivity (`companion_levels`, `companion_potential_lines_pct`), the migration of profiles saved before the
// page existed, and the view models of the comparison table and the "Summoning Time Increase potential lines" table.
import type { ClassSchema, FormState, Scalar, Values } from "../types";
import type { CubesState } from "./cubes";
import type { CompanionRow, CompanionsPart, SummonRow } from "./sensitivity";

export const COMPANION_NONE = "None";
export const COMPANION_MAX_LEVEL = 18;
export const NOT_UNLOCKED_LABEL = "Not unlocked";
/** The Cubes tab's stat name of the boots lines this page prices. */
export const COMPANION_LINES_STAT = "Companion Summoning Time Increase %";

/** Level dropdown of one companion: 0 = "Not unlocked", 1..18. */
export const LEVEL_OPTIONS: { value: number; label: string }[] = [
  { value: 0, label: NOT_UNLOCKED_LABEL },
  ...Array.from({ length: COMPANION_MAX_LEVEL }, (_, i) => ({ value: i + 1, label: String(i + 1) })),
];

/** What the Companions page keeps (saved with the profile): level per owned companion (absent = not unlocked) and the summoning-time % of boots lines that are
 *  already part of the Calculator's "Companion Summoning Time Increase %" (the engine's `companion_potential_lines_pct`). */
export interface CompanionsState {
  levels: Record<string, number>;
  potentialLinesPct: number;
}

export const emptyCompanions = (): CompanionsState => ({ levels: {}, potentialLinesPct: 0 });

/** A level read from anything (number, "7", "Not unlocked", null): a whole number 0..18, 0 = not unlocked. */
export function cleanLevel(v: unknown): number {
  const n = Math.round(Number(v));
  return Number.isFinite(n) ? Math.min(COMPANION_MAX_LEVEL, Math.max(0, n)) : 0;
}

/** Tolerant reader of a stored `companions` block (hand-edited files, older exports): only owned companions (level >= 1; known names when `names` is given) survive. */
export function normalizeCompanions(raw: unknown, names?: readonly string[]): CompanionsState {
  const r = (raw && typeof raw === "object" ? raw : {}) as { levels?: unknown; potentialLinesPct?: unknown };
  const levels: Record<string, number> = {};
  if (r.levels && typeof r.levels === "object" && !Array.isArray(r.levels)) {
    for (const [name, lv] of Object.entries(r.levels as Record<string, unknown>)) {
      const level = cleanLevel(lv);
      if (level >= 1 && (!names || names.includes(name))) levels[name] = level;
    }
  }
  const pct = Number(r.potentialLinesPct);
  return { levels, potentialLinesPct: Number.isFinite(pct) && pct > 0 ? pct : 0 };
}

export function getCompanionChoice(state: Pick<FormState, "contentType" | "perContent">): string {
  return String(state.perContent[state.contentType]?.companion_choice ?? COMPANION_NONE);
}

/** Profiles saved before the Companions page had ONE shared level (`companion_level`) and a companion per content type: every companion chosen anywhere keeps
 *  being owned, at that level (level 0 = nothing was owned). */
export function legacyCompanions(shared: Values, perContent: Record<string, Values>, names?: readonly string[]): CompanionsState {
  const level = cleanLevel(shared.companion_level);
  const levels: Record<string, number> = {};
  if (level >= 1) {
    for (const vals of Object.values(perContent)) {
      const choice = vals?.companion_choice;
      if (typeof choice === "string" && choice !== COMPANION_NONE && (!names || names.includes(choice))) levels[choice] = level;
    }
  }
  return { levels, potentialLinesPct: 0 };
}

/** The state's companions block, or the migrated legacy one when it has none. */
export function companionsOf(schema: Pick<ClassSchema, "companions"> | null | undefined, state: Pick<FormState, "shared" | "perContent" | "companions">): CompanionsState {
  return state.companions ?? legacyCompanions(state.shared, state.perContent, schema?.companions);
}

export const levelOf = (cs: CompanionsState, name: string): number => cs.levels[name] ?? 0;

/** Companions the user owns, in the schema's order. */
export function unlockedCompanions(schema: Pick<ClassSchema, "companions">, cs: CompanionsState): string[] {
  return schema.companions.filter((n) => levelOf(cs, n) >= 1);
}

/** Dropdown of the main form: "None" + the owned companions. */
export function companionOptions(schema: Pick<ClassSchema, "companions">, cs: CompanionsState): string[] {
  return [COMPANION_NONE, ...unlockedCompanions(schema, cs)];
}

/** The companion the compute request uses: the content type's choice when it is owned, else "None" with level 0. */
export function effectiveCompanion(schema: Pick<ClassSchema, "companions">, state: FormState): { choice: string; level: number } {
  const choice = getCompanionChoice(state);
  const level = choice === COMPANION_NONE ? 0 : levelOf(companionsOf(schema, state), choice);
  return level >= 1 ? { choice, level } : { choice: COMPANION_NONE, level: 0 };
}

/** Set the level of one companion (0 = not unlocked).  A companion that is no longer owned is dropped from every content type's choice. */
export function setCompanionLevel(state: FormState, schema: Pick<ClassSchema, "companions">, name: string, level: unknown): FormState {
  if (!schema.companions.includes(name)) return state;
  const cs = companionsOf(schema, state);
  const lv = cleanLevel(level);
  const levels = { ...cs.levels };
  if (lv >= 1) levels[name] = lv;
  else delete levels[name];
  return { ...state, companions: { ...cs, levels }, perContent: dropLockedChoices(state.perContent, levels) };
}

export function setPotentialLinesPct(state: FormState, schema: Pick<ClassSchema, "companions">, pct: number | null): FormState {
  const v = pct === null || !Number.isFinite(pct) || pct < 0 ? 0 : pct;
  return { ...state, companions: { ...companionsOf(schema, state), potentialLinesPct: v } };
}

/** Choices naming a companion that is not owned (any content type) become "None". */
export function dropLockedChoices(perContent: Record<string, Values>, levels: Record<string, number>): Record<string, Values> {
  let changed = false;
  const out: Record<string, Values> = {};
  for (const [ct, vals] of Object.entries(perContent)) {
    const choice = vals?.companion_choice;
    if (typeof choice === "string" && choice !== COMPANION_NONE && !(levels[choice] >= 1)) {
      out[ct] = { ...vals, companion_choice: COMPANION_NONE as Scalar };
      changed = true;
    } else out[ct] = vals;
  }
  return changed ? out : perContent;
}

/** Request extras of POST .../sensitivity: every companion's level (0 = not unlocked) and the boots lines already inside the Summoning Time input. */
export function sensitivityExtras(schema: Pick<ClassSchema, "companions">, state: FormState): { companion_levels: Record<string, number>; companion_potential_lines_pct: number } {
  const cs = companionsOf(schema, state);
  return { companion_levels: Object.fromEntries(schema.companions.map((n) => [n, levelOf(cs, n)])), companion_potential_lines_pct: cs.potentialLinesPct };
}

/** Summoning-time % of the lines currently entered on the Cubes tab (the stat `COMPANION_LINES_STAT`, any slot / track). */
export function cubesCompanionLinesPct(cubes: CubesState | undefined): number {
  let sum = 0;
  for (const row of Object.values(cubes ?? {})) for (const l of row.lines ?? []) if (l.stat === COMPANION_LINES_STAT) sum += Number(l.value) || 0;
  return sum;
}

// ---- comparison table ----------------------------------------------------------------------------------------------------------------------------
export interface CompanionView {
  name: string;
  level: number; // 0 = not unlocked
  chosen: boolean; // the companion of the current content type
  best: boolean; // rank 1 of the comparison (current content type)
  gain: CompanionRow | null; // the engine's row, only when it was computed at this very level
}

/** One view per companion in the schema's order (the workbook's CompanionsInput order); `sort: "rank"` puts owned companions best first, the rest after. */
export function companionViews(schema: Pick<ClassSchema, "companions">, cs: CompanionsState, choice: string, part: CompanionsPart | null | undefined, sort: "table" | "rank" = "table"): CompanionView[] {
  const rows = new Map((part?.rows ?? []).map((r) => [r.name, r]));
  const views = schema.companions.map((name): CompanionView => {
    const level = levelOf(cs, name);
    const row = rows.get(name);
    const gain = row && level >= 1 && row.level === level && row.unlocked ? row : null;
    return { name, level, chosen: name === choice && level >= 1, best: !!gain && gain.rank_position === 1, gain };
  });
  if (sort === "table") return views;
  const idx = new Map(views.map((v, i) => [v.name, i]));
  return [...views].sort((a, b) => {
    if ((a.level >= 1) !== (b.level >= 1)) return a.level >= 1 ? -1 : 1;
    return (a.gain?.rank_position ?? 1e9) - (b.gain?.rank_position ?? 1e9) || idx.get(a.name)! - idx.get(b.name)!;
  });
}

/** One sentence about the best owned companion vs the chosen one (null until the comparison is loaded for the current levels). */
export function bestSummary(views: CompanionView[]): { best: CompanionView; chosen: CompanionView | null; owned: number } | null {
  const best = views.find((v) => v.best);
  if (!best) return null;
  return { best, chosen: views.find((v) => v.chosen) ?? null, owned: views.filter((v) => v.level >= 1).length };
}

/** Mock mode only: re-label a comparison fixture with the requested levels (the numbers stay the fixture's; ranks follow the fixture's gains of the owned ones). */
export function relevel(part: CompanionsPart, levels: Record<string, number>, chosen: string, chosenLevel: number): CompanionsPart {
  const rows: CompanionRow[] = part.rows.map((r) => {
    const level = cleanLevel(levels[r.name] ?? 0);
    return level >= 1 ? { ...r, level, unlocked: true, rank_position: null } : { ...r, level, unlocked: false, dps_gain: 0, pct_gain: 100, companion_dps: 0, companion_boss_dps: 0, companion_normal_dps: 0, rank_position: null };
  });
  const order = rows.map((_r, i) => i).filter((i) => rows[i].unlocked).sort((a, b) => rows[b].dps_gain - rows[a].dps_gain || a - b);
  order.forEach((i, pos) => (rows[i].rank_position = pos + 1));
  return { ...part, chosen, chosen_level: chosenLevel, rows, ranking: order.map((i) => rows[i].name) };
}

// ---- summoning-time potential lines ------------------------------------------------------------------------------------------------------------------
/** Port of src/companion_model.py POTENTIAL_LINE_TIERS: a line's value per rarity tier of the item. */
export const POTENTIAL_LINE_TIERS: [string, number][] = [["Epic", 5], ["Unique", 8], ["Legendary", 12], ["Mystic", 20]];
export const POTENTIAL_MAX_LINES = 3;

export interface LineTotal {
  total: number;
  combos: string[]; // "Unique: 8+5"
}

/** Every total that 1-3 summoning-time lines of ONE potential can add up to (lines roll at the item's tier or the tier directly below, so 12% and 5% never
 *  share a potential), with the combinations: the same list as the workbook's CompanionsInput table (`companion_model.potential_line_totals`). */
export function potentialLineTotals(): LineTotal[] {
  const out = new Map<number, Set<string>>();
  POTENTIAL_LINE_TIERS.forEach(([tier, v], i) => {
    const vals = [...new Set([v, ...(i > 0 ? [POTENTIAL_LINE_TIERS[i - 1][1]] : [])])].sort((a, b) => b - a);
    const rec = (prefix: number[], start: number, remaining: number) => {
      if (prefix.length) {
        const total = prefix.reduce((a, b) => a + b, 0);
        if (!out.has(total)) out.set(total, new Set());
        out.get(total)!.add(`${tier}: ${prefix.join("+")}`);
      }
      if (remaining) for (let j = start; j < vals.length; j++) rec([...prefix, vals[j]], j, remaining - 1);
    };
    rec([], 0, POTENTIAL_MAX_LINES);
  });
  return [...out.entries()].sort((a, b) => a[0] - b[0]).map(([total, set]) => ({ total, combos: [...set].sort() }));
}

export interface SummonView {
  row: SummonRow;
  combos: string[]; // [] for the "no lines" row
  gain: number | null; // DPS gain vs no such lines (null until the baseline is known)
  vsCurrent: number | null; // DPS vs the current setup
  current: boolean; // the entered lines (companion_potential_lines_pct) equal this total
  step: boolean; // DPS rises markedly faster up to this total than elsewhere (another cast / stun fits into the window)
}

const median = (xs: number[]): number => {
  const s = [...xs].sort((a, b) => a - b);
  return s.length ? (s.length % 2 ? s[(s.length - 1) / 2] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2) : 0;
};

/** Rows whose weighted-DPS slope (per +1% of summoning time) is more than twice the table's median slope: the thresholds the explanation talks about. */
export function stepTotals(rows: SummonRow[]): Set<number> {
  const slopes: [number, number][] = [];
  for (let i = 1; i < rows.length; i++) {
    const dx = rows[i].total_pct - rows[i - 1].total_pct;
    if (dx > 0) slopes.push([rows[i].total_pct, (rows[i].weighted_dps_change - rows[i - 1].weighted_dps_change) / dx]);
  }
  const m = median(slopes.map((s) => s[1]));
  return new Set(slopes.filter(([, s]) => s > 0 && s > 2 * m).map(([t]) => t));
}

/** Summon-time table rows with their combinations and DPS columns.  `baselineTotal` = the Total DPS now, `currentCompanionDps` = the companion's own DPS now
 *  (the companions part); both are needed for the absolute columns, which are the workbook's "Total DPS gain vs no such lines" / "DPS vs your current setup". */
export function summonViews(rows: SummonRow[], baselineTotal: number | null, currentCompanionDps: number | null, linesPct: number): SummonView[] {
  const combos = new Map(potentialLineTotals().map((t) => [t.total, t.combos]));
  const steps = stepTotals(rows);
  // Total DPS with the chosen companion but none of the entered lines: what every row's change is measured against
  const base0 = baselineTotal !== null && currentCompanionDps !== null && rows.length ? baselineTotal - currentCompanionDps + rows[0].companion_dps : null;
  return rows.map((row) => ({
    row,
    combos: combos.get(row.total_pct) ?? [],
    gain: base0 === null ? null : base0 * row.weighted_dps_change,
    vsCurrent: base0 === null || baselineTotal === null ? null : base0 * (1 + row.weighted_dps_change) - baselineTotal,
    current: row.total_pct === linesPct,
    step: steps.has(row.total_pct),
  }));
}
