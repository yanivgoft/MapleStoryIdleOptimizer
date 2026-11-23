// Pure logic that turns an engine schema into a form: grouping, applicability, per-content-type values, parsing, request building.
import type { ClassSchema, Field, FormState, Scalar, Values } from "../types";
import { emptyArtifacts, normalizeArtifacts, requestSlots } from "./artifacts";
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
export const COMPANION_GROUP = "Companion";
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
  const rank = (n: string) => (GROUP_ORDER.includes(n) ? GROUP_ORDER.indexOf(n) : GROUP_ORDER.indexOf("PvP") - 0.5);
  return groups.map((g, i) => ({ g, i })).sort((a, b) => rank(a.g.name) - rank(b.g.name) || a.i - b.i).map((x) => x.g);
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
  return { classId: schema.class_id, contentType: ct, shared, perContent: { [ct]: per }, artifacts: schema.artifacts ? emptyArtifacts(schema.artifacts) : {}, companions: legacyCompanions(shared, { [ct]: per }, schema.companions) };
}

/** Switch content type; a content type visited for the first time gets its own defaults (fetched or computed by the caller). */
export function switchContentType(state: FormState, schema: ClassSchema, contentType: string, defaults?: Values): FormState {
  if (state.perContent[contentType]) return { ...state, contentType };
  const d = defaults ?? defaultsFromSchema(schema, contentType);
  const sk = new Set(sharedKeys(schema));
  const per: Values = {};
  for (const [k, v] of Object.entries(d)) if (k !== "content_type" && !sk.has(k)) per[k] = v;
  return { ...state, contentType, perContent: { ...state.perContent, [contentType]: per } };
}

/** Copy the per-content values (not Chapter-Stage-like per-content defaults) from one visited content type to another. */
export function copyContentValues(state: FormState, schema: ClassSchema, from: string, to: string): FormState {
  const src = state.perContent[from];
  if (!src) return state;
  const base = state.perContent[to] ?? {};
  const next: Values = { ...base };
  for (const f of schema.fields) {
    if (f.computed || !f.per_content || f.default_by_content) continue;
    if (!isApplicable(f, to) || !isApplicable(f, from)) continue;
    next[f.key] = src[f.key] ?? null;
  }
  return { ...state, perContent: { ...state.perContent, [to]: next } };
}

export function getValue(state: FormState, field: Field): Scalar {
  if (field.key === "content_type") return state.contentType;
  if (!field.per_content) return state.shared[field.key] ?? null;
  return state.perContent[state.contentType]?.[field.key] ?? null;
}

export function setValue(state: FormState, field: Field, value: Scalar): FormState {
  if (!field.per_content) return { ...state, shared: { ...state.shared, [field.key]: value } };
  const cur = state.perContent[state.contentType] ?? {};
  return { ...state, perContent: { ...state.perContent, [state.contentType]: { ...cur, [field.key]: value } } };
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
    out.artifacts = requestSlots(schema.artifacts, state.artifacts);       // the equipped artifacts only, schema order, <= max_slots (lib/artifacts.ts)
  }
  return out;
}

export type ParseResult = { ok: true; value: number | null } | { ok: false; message: string };

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

/** Parse what the user typed into a numeric field: '' -> null (blank cell, reads as 0); '1,234.5' / '1e6' accepted; ints must be whole;
 *  optional inclusive bounds (the schema's min / max) are checked here too, with the same wording as the API. */
export function parseNumber(text: string, type: "int" | "float", min?: number | null, max?: number | null): ParseResult {
  const t = text.trim().replace(/,/g, "");
  if (t === "") return { ok: true, value: null };
  if (!/^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$/.test(t)) return { ok: false, message: "Enter a number" };
  const n = Number(t);
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

export function unitSuffix(field: Field): string {
  if (field.unit === "%") return "%";
  if (field.unit === "s") return "s";
  return "";
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
  const out: FormState = { ...rest, contentType: contentTypes, shared, perContent: dropLockedChoices(perContent, companions.levels), artifacts, companions };
  return out.perContent[contentTypes] ? out : switchContentType(out, schema, contentTypes);
}
