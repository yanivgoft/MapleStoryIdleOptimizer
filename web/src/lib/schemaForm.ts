// Pure logic that turns an engine schema into a form: grouping, applicability, per-content-type values, parsing, request building.
import type { ClassSchema, Field, FormState, Scalar, Values } from "../types";
import { currentSlots, emptyArtifacts, normalizeArtifacts, normalizeEquipped, requestSlots } from "./artifacts";
import { dropLockedChoices, effectiveCompanion, legacyCompanions, normalizeCompanions } from "./companions";

export { getCompanionChoice } from "./companions";

export interface FieldGroup {
  name: string;
  fields: Field[];
}

/** Content types a field applies to; null = every content type. */
export function isApplicable(field: Field, contentType: string): boolean {
  return field.applicable === null || field.applicable.includes(contentType);
}

/** Section the form shows the companion machinery in: the pick + its level and Companion Summoning Time Increase %. (Status Effect Damage is a damage modifier and stays in "Damage modifiers".) */
export const COMPANION_GROUP = "Main companion";
/** Fields moved into COMPANION_GROUP (presentation only: the engine schema keeps its own groups) in display order. */
export const COMPANION_GROUP_KEYS = ["companion_choice", "companion_level", "companion_summon_time_increase_pct"];
/** Display order of sections; sections not listed go just before "PvP". */
export const GROUP_ORDER = ["Character", "Offense", "Main stats", "Damage modifiers", "Skill levels", "Additional bonuses", COMPANION_GROUP, "PvP"];

export function groupOf(field: Field): string {
  return COMPANION_GROUP_KEYS.includes(field.key) ? COMPANION_GROUP : field.group;
}

/** Editable (non-computed) fields grouped (sections in GROUP_ORDER, fields in schema order); computed fields are ``computedFields``. */
export function groupFields(schema: ClassSchema): FieldGroup[] {
  const groups: FieldGroup[] = [];
  for (const f of schema.fields) {
    if (f.computed) continue;
    const name = groupOf(f);
    let g = groups.find((x) => x.name === name);
    if (!g) groups.push((g = { name, fields: [] }));
    g.fields.push(f);
  }
  const companion = groups.find((g) => g.name === COMPANION_GROUP);
  if (companion) {
    companion.fields.sort((a, b) => COMPANION_GROUP_KEYS.indexOf(a.key) - COMPANION_GROUP_KEYS.indexOf(b.key));
  }
  return groups.map((g, i) => ({ g, i })).sort((a, b) => groupRank(a.g.name) - groupRank(b.g.name) || a.i - b.i).map((x) => x.g);
}

/** Position of a section in the form (sections not in GROUP_ORDER sit just before "PvP"). */
export function groupRank(name: string): number {
  return GROUP_ORDER.includes(name) ? GROUP_ORDER.indexOf(name) : GROUP_ORDER.indexOf("PvP") - 0.5;
}

export function computedFields(schema: ClassSchema): Field[] {
  return schema.fields.filter((f) => f.computed);
}

/** Fields of a group the user should see for this content type (the content-type selector itself is rendered by the form header). */
export function visibleFields(group: FieldGroup, contentType: string): Field[] {
  return group.fields.filter((f) => isApplicable(f, contentType));
}

/** Groups that still have something to show for this content type. */
export function visibleGroups(groups: FieldGroup[], contentType: string): FieldGroup[] {
  return groups.map((g) => ({ ...g, fields: visibleFields(g, contentType) })).filter((g) => g.fields.length > 0);
}

/** Workbook default of one field for a content type (null when it does not apply). */
export function defaultFor(field: Field, contentType: string): Scalar {
  if (!isApplicable(field, contentType)) return null;
  if (field.default_by_content) return field.default_by_content[contentType] ?? null;
  return field.default;
}

/** Whole default value set for a content type, from the schema alone (what ``GET /defaults`` returns). */
export function defaultsFromSchema(schema: ClassSchema, contentType: string): Values {
  const out: Values = {};
  for (const f of schema.fields) {
    if (f.computed) continue;
    out[f.key] = f.key === "content_type" ? contentType : defaultFor(f, contentType);
  }
  return out;
}

/** Fields stored once per profile, not per content type. */
export function sharedKeys(schema: ClassSchema): string[] {
  return schema.fields.filter((f) => !f.computed && !f.per_content && f.key !== "content_type").map((f) => f.key);
}

export function initialState(schema: ClassSchema, defaults: Values, contentType?: string): FormState {
  const ct = contentType ?? String(defaults.content_type ?? schema.content_types[0]);
  const shared: Values = {};
  const per: Values = {};
  const sk = new Set(sharedKeys(schema));
  for (const [k, v] of Object.entries(defaults)) {
    if (k === "content_type") continue;
    (sk.has(k) ? shared : per)[k] = v;
  }
  // the defaults of a class carry the companion pick + level (the sample inputs do): the Companions tab starts with exactly that companion owned
  return { classId: schema.class_id, contentType: ct, shared, perContent: { [ct]: per }, artifacts: schema.artifacts ? emptyArtifacts(schema.artifacts) : {}, equippedArtifacts: {}, companions: legacyCompanions(shared, { [ct]: per }, schema.companions) };
}

/** Content types that share a situation: a first-time content type is seeded from a visited one of its group (see `seedSource`).  PvP is in no group. */
export const CONTENT_GROUPS: readonly (readonly string[])[] = [
  ["Chapter Hunt", "EXP Dungeon", "Equipment Dungeon"], // normal monsters
  ["Breakthrough", "Hero Dungeon"], // normal monsters + boss
  ["Chapter Boss", "Weapon Dungeon", "Enhancement Dungeon", "World Boss"], // bosses
];

export function contentGroup(contentType: string): readonly string[] | null {
  return CONTENT_GROUPS.find((g) => g.includes(contentType)) ?? null;
}

/** Remember that the user edited this content type (most recent first; `editOrder` is persisted with the profile / draft). */
export function markEdited(state: FormState, contentType: string = state.contentType): FormState {
  const cur = state.editOrder ?? [];
  if (cur[0] === contentType) return state;
  return { ...state, editOrder: [contentType, ...cur.filter((c) => c !== contentType)] };
}

/** Where a content type that has no stored values yet gets its starting values from, or null (plain defaults):
 *  1. a visited content type of the SAME group (several: the most recently edited, else the first in group order);
 *  2. else the content type being switched from (PvP only ever counts here, never as a group member);
 *  3. else nothing. */
export function seedSource(state: FormState, contentType: string): string | null {
  const visited = (c: string) => c !== contentType && !!state.perContent[c];
  const group = contentGroup(contentType);
  if (group) {
    const siblings = group.filter(visited);
    if (siblings.length) return (state.editOrder ?? []).find((c) => siblings.includes(c)) ?? siblings[0];
  }
  return visited(state.contentType) ? state.contentType : null;
}

/** Switch content type.  A content type that already has stored values is never touched.  One visited for the first time starts from its defaults
 *  (fetched or computed by the caller) and then takes the values "Copy stats from" copies from `seedSource` (stats, the companion pick and the equipped
 *  artifacts; not the per-content defaults such as Chapter-Stage). */
export function switchContentType(state: FormState, schema: ClassSchema, contentType: string, defaults?: Values): FormState {
  if (state.perContent[contentType]) return { ...state, contentType };
  const d = defaults ?? defaultsFromSchema(schema, contentType);
  const sk = new Set(sharedKeys(schema));
  const per: Values = {};
  for (const [k, v] of Object.entries(d)) if (k !== "content_type" && !sk.has(k)) per[k] = v;
  const source = seedSource(state, contentType);
  const fresh: FormState = { ...state, contentType, perContent: { ...state.perContent, [contentType]: per } };
  return source ? copyInto(fresh, schema, source, contentType, false) : fresh;
}

function copyInto(state: FormState, schema: ClassSchema, from: string, to: string, overwriteEquipped: boolean): FormState {
  const src = state.perContent[from];
  if (!src) return state;
  const base = state.perContent[to] ?? {};
  const next: Values = { ...base };
  for (const f of schema.fields) {
    if (f.computed || !f.per_content || f.default_by_content) continue;
    if (!isApplicable(f, to) || !isApplicable(f, from)) continue;
    next[f.key] = src[f.key] ?? null;
  }
  // the equipped artifacts are a per-content value too (the Calculator's "Equipped artifacts" section); a seeded content type keeps slots that were already stored for it
  let equippedArtifacts = state.equippedArtifacts;
  if (schema.artifacts && (overwriteEquipped || !(state.equippedArtifacts?.[to] ?? []).some((k) => k !== ""))) {
    equippedArtifacts = { ...(state.equippedArtifacts ?? {}), [to]: currentSlots(schema.artifacts, { equippedArtifacts: state.equippedArtifacts, contentType: from }) };
  }
  return { ...state, perContent: { ...state.perContent, [to]: next }, ...(equippedArtifacts ? { equippedArtifacts } : {}) };
}

/** "Copy stats from": copy the per-content values (not Chapter-Stage-like per-content defaults) from one visited content type to another (the user's own action: counts as an edit). */
export function copyContentValues(state: FormState, schema: ClassSchema, from: string, to: string): FormState {
  const out = copyInto(state, schema, from, to, true);
  return out === state ? state : markEdited(out, to);
}

export function getValue(state: FormState, field: Field): Scalar {
  if (field.key === "content_type") return state.contentType;
  if (!field.per_content) return state.shared[field.key] ?? null;
  return state.perContent[state.contentType]?.[field.key] ?? null;
}

export function setValue(state: FormState, field: Field, value: Scalar): FormState {
  if (!field.per_content) return { ...state, shared: { ...state.shared, [field.key]: value } };
  const cur = state.perContent[state.contentType] ?? {};
  return markEdited({ ...state, perContent: { ...state.perContent, [state.contentType]: { ...cur, [field.key]: value } } });
}

/** Flat inputs dict for ``POST /compute``: shared + current content type's values, non-applicable fields null. */
export function buildInputs(schema: ClassSchema, state: FormState): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const f of schema.fields) {
    if (f.computed) continue;
    out[f.key] = isApplicable(f, state.contentType) ? getValue(state, f) : null;
  }
  out.content_type = state.contentType;
  // the chosen companion's level comes from the Companions tab's table (the schema's `companion_level` is filled from it; a companion that is not owned is "None")
  if ("companion_choice" in out && "companion_level" in out) {
    const { choice, level } = effectiveCompanion(schema, state);
    out.companion_choice = choice;
    out.companion_level = level;
  }
  if (schema.artifacts_modelled && schema.artifacts) {
    out.artifacts = requestSlots(schema.artifacts, state.artifacts, currentSlots(schema.artifacts, state));       // the CURRENT content type's equipped artifacts, schema order, <= max_slots (lib/artifacts.ts)
  }
  return out;
}

export type ParseResult = { ok: true; value: number | null } | { ok: false; message: string };

/** Number-input shorthand: the suffixes `formatNumber` prints (K = 1e3 ... Sp = 1e24). */
const SUFFIX_EXPONENT: Record<string, number> = { k: 3, m: 6, b: 9, t: 12, qa: 15, qi: 18, sx: 21, sp: 24 };
export const NUMBER_HINT = "Enter a number like 1234567, 12.5M or 1.2e6";

function fmtBound(n: number): string {
  return Math.abs(n) >= 1e6 ? n.toExponential().replace("+", "") : String(n);
}

/** "0 - 100" / "min 0": the schema's numeric bounds as a short hint ("" for fields without bounds). */
export function rangeText(field: Pick<Field, "min" | "max" | "type">): string {
  if (field.type !== "int" && field.type !== "float") return "";
  const lo = field.min ?? null;
  const hi = field.max ?? null;
  if (lo === null && hi === null) return "";
  if (hi === null || hi >= 1e6) return lo === null ? "" : `min ${fmtBound(lo)}`;
  return `${lo === null ? "" : fmtBound(lo)} - ${fmtBound(hi)}`;
}

/** Parse what the user typed into a numeric field: '' -> null (blank cell, reads as 0); '1,234.5', '1e6' and K / M / B / T / Qa / Qi / Sx / Sp shorthand ('12.5M') accepted;
 *  ints must be whole; optional inclusive bounds (the schema's min / max) are checked here too, with the same wording as the API. */
export function parseNumber(text: string, type: "int" | "float", min?: number | null, max?: number | null): ParseResult {
  const t = text.trim().replace(/,/g, "");
  if (t === "") return { ok: true, value: null };
  const plain = /^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$/.test(t);
  const short = /^([+-]?(?:\d+\.?\d*|\.\d+))\s*(k|m|b|t|qa|qi|sx|sp)$/i.exec(t);
  if (!plain && !short) return { ok: false, message: NUMBER_HINT };
  // "12.5M" -> Number("12.5e6"): going through the exponent form keeps 1.1T exactly 1.1e12 (1.1 * 1e12 is not)
  const n = plain ? Number(t) : Number(`${short![1]}e${SUFFIX_EXPONENT[short![2].toLowerCase()]}`);
  if (!Number.isFinite(n)) return { ok: false, message: "Enter a finite number" };
  if (type === "int" && !Number.isInteger(n)) return { ok: false, message: "Whole number required" };
  if ((min !== undefined && min !== null && n < min) || (max !== undefined && max !== null && n > max)) {
    const lo = min ?? null;
    const hi = max ?? null;
    return { ok: false, message: lo !== null && hi !== null ? `Must be between ${fmtBound(lo)} and ${fmtBound(hi)}` : lo !== null ? `Must be at least ${fmtBound(lo)}` : `Must be at most ${fmtBound(hi as number)}` };
  }
  return { ok: true, value: n };
}

/** Dropdown text of an option (the stored value stays unchanged). */
export function optionLabel(field: Field, option: string): string {
  return field.key === "companion_choice" && option === "None" ? "None (no companion)" : option;
}

/** The one unit marker shown inside the input: "%" / "s"; none when the label already ends in "%" (ATTACK %, INT %). */
export function unitSuffix(field: Field): string {
  if (field.unit === "%") return /%\s*$/.test(field.label) ? "" : "%";
  if (field.unit === "s") return "s";
  return "";
}

/**
 * The few fields that keep a line under the input because their FORMAT or special value cannot be guessed (user rule: no help under plain stats,
 * skill levels or anything a player already knows). Everything else shows no text at all; the full schema help lives in Help only.
 * - Chapter-Stage: the "28-9" format.  - Max Enemies In Range: 999 = no limit.  - Fixed Fight Duration: 0 = no time limit.
 * - Content Type: its single line (kept).  - Defense % when its help warns that the STR/INT it converts is added for you (a double-count trap with Flat STR).
 */
const INLINE_HELP: Record<string, string> = {
  chapter_stage: "Like 28-9; a plain number for bosses and dungeons.",
  max_enemies_hit: "999 = no limit.",
  fight_duration: "0 = no time limit.",
};
export function inlineHelpText(field: Pick<Field, "key" | "help">): string | null {
  if (!field.help) return null;
  if (field.key in INLINE_HELP) return INLINE_HELP[field.key];
  if (field.key === "content_type") return field.help; // the one "Each content type keeps its own stats." line (set by InputsForm)
  if (field.key === "defense_pct" && /leave it out/i.test(field.help)) return field.help;
  return null;
}

/** Map API field errors ('level', 'artifacts[0].key') onto form fields; the rest are general messages. */
export function splitErrors(errors: { field: string; message: string }[], schema: ClassSchema) {
  const keys = new Set(schema.fields.map((f) => f.key));
  const byField: Record<string, string> = {};
  const general: string[] = [];
  for (const e of errors) {
    if (keys.has(e.field)) byField[e.field] = e.message;
    else general.push(e.field ? `${e.field}: ${e.message}` : e.message);
  }
  return { byField, general };
}

/** Fill keys a stored state lacks (a profile saved before a schema change) with the schema defaults; drop nothing. */
export function normalizeState(schema: ClassSchema, state: FormState): FormState {
  const sk = new Set(sharedKeys(schema));
  const shared: Values = { ...state.shared };
  const perContent: Record<string, Values> = {};
  const contentTypes = schema.content_types.includes(state.contentType) ? state.contentType : schema.content_types[0];
  for (const f of schema.fields) {
    if (f.computed || f.key === "content_type" || !sk.has(f.key)) continue;
    if (!(f.key in shared)) shared[f.key] = f.default;
  }
  for (const [ct, vals] of Object.entries(state.perContent)) {
    if (!schema.content_types.includes(ct)) continue;
    const v: Values = { ...vals };
    for (const f of schema.fields) {
      if (f.computed || f.key === "content_type" || sk.has(f.key)) continue;
      if (!(f.key in v)) v[f.key] = defaultFor(f, ct);
    }
    perContent[ct] = v;
  }
  // owned companions + levels: profiles saved before the Companions tab keep their chosen companion(s) at the old shared level
  const companions = state.companions ? normalizeCompanions(state.companions, schema.companions) : legacyCompanions(state.shared, state.perContent, schema.companions);
  // artifacts: the per-artifact table; the OLD shape (a slots list + `potentials`) is migrated here and `potentials` is dropped
  const { potentials: legacyPotentials, ...rest } = state;
  const artifacts = schema.artifacts ? normalizeArtifacts(state.artifacts, schema.artifacts, legacyPotentials) : state.artifacts ?? {}; // (a class without artifact support keeps what it had; never sent)
  // equipped artifacts: per content type; a profile saved before (one global `equipped` flag per artifact, or the old slots list) seeds EVERY content type from that set, once
  const equippedArtifacts = schema.artifacts ? normalizeEquipped(state.equippedArtifacts, schema.artifacts, schema.content_types, state.artifacts) : state.equippedArtifacts ?? {};
  const editOrder = Array.isArray(state.editOrder) ? state.editOrder.filter((c, i, a) => typeof c === "string" && schema.content_types.includes(c) && a.indexOf(c) === i) : undefined;
  const out: FormState = { ...rest, contentType: contentTypes, shared, perContent: dropLockedChoices(perContent, companions.levels), artifacts, equippedArtifacts, companions, ...(editOrder ? { editOrder } : {}) };
  return out.perContent[contentTypes] ? out : switchContentType(out, schema, contentTypes);
}
