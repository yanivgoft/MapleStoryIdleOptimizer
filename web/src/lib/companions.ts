// Companions page logic (pure, no React): which companions the user owns and at what level (the workbook's CompanionsInput sheet), the chosen companion of the
// current content type, the request extras of POST .../sensitivity (`companion_levels`), the migration of profiles saved before the
// page existed, and the view model of the comparison table.
import type { ClassSchema, FormState, Scalar, Values } from "../types";
import type { CompanionRow, CompanionsPart } from "./sensitivity";

export const COMPANION_NONE = "None";
export const COMPANION_MAX_LEVEL = 18;
export const NOT_UNLOCKED_LABEL = "Not unlocked";

/** Level dropdown of one companion: 0 = "Not unlocked", 1..18. */
export const LEVEL_OPTIONS: { value: number; label: string }[] = [
  { value: 0, label: NOT_UNLOCKED_LABEL },
  ...Array.from({ length: COMPANION_MAX_LEVEL }, (_, i) => ({ value: i + 1, label: String(i + 1) })),
];

/** What the Companions page keeps (saved with the profile): level per owned companion (absent = not unlocked). */
export interface CompanionsState {
  levels: Record<string, number>;
}

export const emptyCompanions = (): CompanionsState => ({ levels: {} });

/** A level read from anything (number, "7", "Not unlocked", null): a whole number 0..18, 0 = not unlocked. */
export function cleanLevel(v: unknown): number {
  const n = Math.round(Number(v));
  return Number.isFinite(n) ? Math.min(COMPANION_MAX_LEVEL, Math.max(0, n)) : 0;
}

/** Tolerant reader of a stored `companions` block (hand-edited files, older exports): only owned companions (level >= 1; known names when `names` is given) survive.
 *  A stored `potentialLinesPct` (profiles saved before that input was removed) is ignored. */
export function normalizeCompanions(raw: unknown, names?: readonly string[]): CompanionsState {
  const r = (raw && typeof raw === "object" ? raw : {}) as { levels?: unknown };
  const levels: Record<string, number> = {};
  if (r.levels && typeof r.levels === "object" && !Array.isArray(r.levels)) {
    for (const [name, lv] of Object.entries(r.levels as Record<string, unknown>)) {
      const level = cleanLevel(lv);
      if (level >= 1 && (!names || names.includes(name))) levels[name] = level;
    }
  }
  return { levels };
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
  return { levels };
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

/** Request extras of POST .../sensitivity: every companion's level (0 = not unlocked). */
export function sensitivityExtras(schema: Pick<ClassSchema, "companions">, state: FormState): { companion_levels: Record<string, number> } {
  const cs = companionsOf(schema, state);
  return { companion_levels: Object.fromEntries(schema.companions.map((n) => [n, levelOf(cs, n)])) };
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
