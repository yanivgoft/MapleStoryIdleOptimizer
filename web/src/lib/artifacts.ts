// Artifacts tab logic (pure, no React): slots, star options, effect text, badges, request building, breakdown rows.
//
// Source of truth is the engine: slot options / star options / ranks / default stars / `no_dps_effect` + reason come from `schema.artifacts`
// (engine/classes/<id>.py `artifact_schema()`), the star values behind the effect text from `artifact_values.json` (a dump of
// `engine/data/artifacts.py` ARTIFACT_STAR_VALUES written by web/scripts/gen_fixtures.py), the equipped effects from `result.artifacts`.  What stays
// here is the human wording per artifact (EFFECTS below, mirroring the Equip effect code of engine/artifacts.py): which star-value keys belong to which
// artifact, under which condition they apply, whether the stat is "baked into Inputs" (typed by the user) and whether the companion model reads it.
import values from "./artifact_values.json";
import type { ArtifactEntry, ArtifactInfo, ArtifactLine, ArtifactSchema, ArtifactsState, ClassInfo, ClassSchema, ComputeResult } from "../types";

export const STAR_VALUES = values as Record<string, number[]>;
export const NOT_UNLOCKED = "Not Unlocked";
export const COMPANION_SECTION_ID = "companion-section";

// ---------------------------------------------------------------------------------------------------------------------------------------
// capability
// ---------------------------------------------------------------------------------------------------------------------------------------
/** Artifacts are available for a class only when its schema says so (engine `artifacts_modelled` + a usable `artifacts` block); the class list's
 *  status is only a fallback while the schema is not loaded.  Never a hard-coded class list. */
export function artifactsAvailable(schema: ClassSchema | null | undefined, info?: ClassInfo | null): boolean {
  if (schema) return !!schema.artifacts_modelled && !!schema.artifacts && schema.artifacts.modelled !== false;
  if (info) return !!(info.status?.artifacts ?? info.artifacts_modelled);
  return false;
}

// ---------------------------------------------------------------------------------------------------------------------------------------
// the table state: one record per artifact {star, equipped, lines}
// ---------------------------------------------------------------------------------------------------------------------------------------
export const NO_STAT = "(none)"; // an empty potential line (= cubes.ts NONE_STAT and the engine's potentials.NONE_STAT; tested)
export const DEFAULT_LINE_RARITY = "Rare"; // = the engine's potentials.DEFAULT_RARITY (and `meta.artifact_potentials.default_rarity`; tested)
export const LINE_SLOTS = 3;

/** Number of potential lines an artifact has: 3 for Legendary artifacts, 2 for Epic / Unique (engine `potentials.num_lines`, regardless of star level). */
export const lineCount = (info: Pick<ArtifactInfo, "rank"> | undefined): number => (info?.rank === "Legendary" ? 3 : 2);

export const blankLine = (): ArtifactLine => ({ rarity: DEFAULT_LINE_RARITY, stat: NO_STAT });
export const isBlankLine = (l: ArtifactLine | undefined): boolean => !l || l.stat === NO_STAT;

export function artifactInfo(art: ArtifactSchema, key: string): ArtifactInfo | undefined {
  return art.artifacts.find((a) => a.key === key);
}

/** The star level the engine will use: "Not Unlocked" / null act as star 0, anything else is clamped to 0..5. */
export function starIndex(star: number | string | null | undefined): number {
  if (star === null || star === undefined || star === NOT_UNLOCKED) return 0;
  const n = Math.round(Number(star));
  return Number.isFinite(n) ? Math.min(5, Math.max(0, n)) : 0;
}

/** Table star (null = Not Unlocked) from anything stored / imported: `{ok:false}` for junk (the caller falls back to the default). */
export function parseStar(x: unknown): { ok: true; value: number | null } | { ok: false } {
  if (x === null || x === NOT_UNLOCKED) return { ok: true, value: null };
  if (typeof x === "string") {
    if (x.trim().toLowerCase() === NOT_UNLOCKED.toLowerCase()) return { ok: true, value: null };
    if (/^\d$/.test(x.trim())) return parseStar(Number(x.trim()));
    return { ok: false };
  }
  if (typeof x === "number" && Number.isInteger(x) && x >= 0 && x <= 5) return { ok: true, value: x };
  return { ok: false };
}

/** Star dropdown: "Not unlocked" (value "Not Unlocked") + Star 0..5; how "Not unlocked" acts is the select's tooltip (STAR_TOOLTIP). */
export const STAR_TOOLTIP =
  "Not unlocked acts as star 0 when the artifact is equipped: its equip effect still applies at the star-0 value. An artifact that is not equipped does nothing; its star only feeds the equip ranking (locked artifacts are unranked) and its potential lines.";
export function starOptions(art: ArtifactSchema): { value: number | string; label: string }[] {
  const max = Math.max(...art.star_options.filter((s): s is number => typeof s === "number"));
  return art.star_options.map((s) => ({ value: s, label: s === NOT_UNLOCKED ? "Not unlocked" : `Star ${s}${s === max ? " (max)" : ""}` }));
}

export function defaultStarFor(art: ArtifactSchema, key: string): number | string {
  const d = artifactInfo(art, key)?.default_star;
  return d === null || d === undefined ? NOT_UNLOCKED : d;
}
/** The workbook's default star by rank as a table star (Epic 5, Unique 3, Legendary null = Not Unlocked). */
export function defaultTableStar(art: ArtifactSchema, key: string): number | null {
  const p = parseStar(defaultStarFor(art, key));
  return p.ok ? p.value : null;
}

export function defaultEntry(art: ArtifactSchema, key: string): ArtifactEntry {
  return { star: defaultTableStar(art, key), equipped: false, lines: Array.from({ length: LINE_SLOTS }, blankLine) };
}

/** A fresh table: every artifact at its default star, nothing equipped, no lines. */
export function emptyArtifacts(art: ArtifactSchema): ArtifactsState {
  return Object.fromEntries(art.artifacts.map((a) => [a.key, defaultEntry(art, a.key)]));
}

const isObj = (x: unknown): x is Record<string, unknown> => !!x && typeof x === "object" && !Array.isArray(x);

/** Exactly 3 well-formed lines; the lines beyond ``count`` (Epic / Unique artifacts have 2) stay blank. */
function normalizeLines(raw: unknown, count: number): ArtifactLine[] {
  const list = Array.isArray(raw) ? raw : [];
  return Array.from({ length: LINE_SLOTS }, (_v, i) => {
    const l = list[i] as Partial<ArtifactLine> | null | undefined;
    if (i >= count || !l || typeof l.stat !== "string" || !l.stat) return blankLine();
    return { rarity: typeof l.rarity === "string" && l.rarity ? l.rarity : DEFAULT_LINE_RARITY, stat: l.stat };
  });
}

/**
 * The table state for ``art`` from anything stored (current record shape, or the OLD shape: a list of equipped slots ``[{key, star}]`` plus - optionally - the
 * old Artifact-potentials state ``{key: {star?, lines}}``).  Junk is repaired, never thrown: unknown artifacts are dropped, a missing entry becomes the default
 * (star by rank, not equipped, no lines), stars outside Not Unlocked / 0-5 fall back to the default, at most ``max_slots`` artifacts stay equipped (schema order),
 * and an old equipped artifact keeps the star of its slot (the old UI used the slot's star for its potentials too).
 */
export function normalizeArtifacts(raw: unknown, art: ArtifactSchema | undefined, legacyPotentials?: unknown): ArtifactsState {
  if (!art) return isObj(raw) ? (raw as unknown as ArtifactsState) : {};
  const out: ArtifactsState = {};
  const legacy = Array.isArray(raw);
  const rec = !legacy && isObj(raw) ? raw : {};
  const pot = legacy && isObj(legacyPotentials) ? legacyPotentials : {};
  const slotStar = new Map<string, unknown>();
  if (legacy) {
    for (const s of raw as unknown[]) {
      if (slotStar.size >= art.max_slots) break;
      const k = isObj(s) && typeof s.key === "string" ? s.key : null;
      const key = k === null ? null : art.artifacts.find((a) => a.key === k || a.name === k)?.key ?? null;
      if (key && !slotStar.has(key)) slotStar.set(key, (s as Record<string, unknown>).star);
    }
  }
  let equipped = 0;
  for (const info of art.artifacts) {
    const key = info.key;
    const d = defaultEntry(art, key);
    let star = d.star;
    let isEq = false;
    let linesRaw: unknown;
    if (legacy) {
      const p = isObj(pot[key]) ? (pot[key] as Record<string, unknown>) : null;
      linesRaw = p?.lines;
      const own = slotStar.has(key) ? slotStar.get(key) : p && "star" in p ? p.star : undefined;
      const ps = own === undefined ? ({ ok: false } as const) : parseStar(own);
      if (ps.ok) star = ps.value;
      isEq = slotStar.has(key);
    } else {
      const e = rec[key];
      if (isObj(e)) {
        const ps = "star" in e ? parseStar(e.star) : ({ ok: false } as const);
        if (ps.ok) star = ps.value;
        isEq = e.equipped === true;
        linesRaw = e.lines;
      }
    }
    if (isEq && equipped >= art.max_slots) isEq = false;
    if (isEq) equipped++;
    out[key] = { star, equipped: isEq, lines: normalizeLines(linesRaw, lineCount(info)) };
  }
  return out;
}

/** Equipped artifact ids in the schema's (workbook) order: the stable order of the engine request. */
export function equippedKeys(art: ArtifactSchema, state: ArtifactsState | undefined): string[] {
  return art.artifacts.filter((a) => state?.[a.key]?.equipped).map((a) => a.key);
}
export const equippedCount = (art: ArtifactSchema, state: ArtifactsState | undefined): number => equippedKeys(art, state).length;

/** May ``key`` be (un)equipped?  Unequipping is always possible; equipping needs a free slot (``max_slots``). */
export function canEquip(art: ArtifactSchema, state: ArtifactsState | undefined, key: string): boolean {
  return !!artifactInfo(art, key) && (!!state?.[key]?.equipped || equippedCount(art, state) < art.max_slots);
}

export const equipCapTitle = (art: ArtifactSchema): string => `All ${art.max_slots} artifact slots are used: unequip another artifact first.`;

/** Equip / unequip ``key`` (no-op for an unknown artifact or when equipping with every slot used). */
export function setEquipped(art: ArtifactSchema, state: ArtifactsState | undefined, key: string, on: boolean): ArtifactsState {
  const cur = normalizeArtifacts(state, art);
  if (!cur[key] || cur[key].equipped === on) return cur;
  if (on && equippedCount(art, cur) >= art.max_slots) return cur;
  return { ...cur, [key]: { ...cur[key], equipped: on } };
}

/** Star of ``key``: a table star (null = Not Unlocked), or the dropdown values "Not Unlocked" / 0..5. */
export function setStar(art: ArtifactSchema, state: ArtifactsState | undefined, key: string, star: number | string | null): ArtifactsState {
  const cur = normalizeArtifacts(state, art);
  const p = parseStar(star);
  if (!cur[key] || !p.ok) return cur;
  return { ...cur, [key]: { ...cur[key], star: p.value } };
}

/** Patch line ``i`` (0-based) of ``key``; lines beyond the artifact's own count (Epic / Unique: 2) cannot be set. */
export function setLine(art: ArtifactSchema, state: ArtifactsState | undefined, key: string, i: number, patch: Partial<ArtifactLine>): ArtifactsState {
  const cur = normalizeArtifacts(state, art);
  const info = artifactInfo(art, key);
  if (!cur[key] || !info || i < 0 || i >= lineCount(info)) return cur;
  const lines = cur[key].lines.map((l, j) => (j === i ? { ...l, ...patch } : l));
  return { ...cur, [key]: { ...cur[key], lines } };
}

/** The ``artifacts`` list of the compute request: the equipped artifacts only, in the schema's order, at most ``max_slots`` (``null`` star = "Not Unlocked"). */
export function requestSlots(art: ArtifactSchema, state: ArtifactsState | undefined): { key: string; star: number | string }[] {
  return equippedKeys(art, normalizeArtifacts(state, art)).map((key) => ({ key, star: state?.[key]?.star ?? NOT_UNLOCKED }));
}

/** ``artifact_stars`` of POST .../sensitivity: the star of EVERY artifact (what the equip ranking uses for the ones that are not equipped). */
export function artifactStarsExtra(art: ArtifactSchema | undefined, state: ArtifactsState | undefined): { artifact_stars: Record<string, number | string> } | Record<string, never> {
  if (!art) return {};
  const cur = normalizeArtifacts(state, art);
  return { artifact_stars: Object.fromEntries(art.artifacts.map((a) => [a.key, cur[a.key].star ?? NOT_UNLOCKED])) };
}

export interface TableFilter {
  text: string; // case-insensitive substring of the artifact name
  onlyActive: boolean; // only unlocked or equipped artifacts
}
/** Artifacts the table shows, in schema order (equipped / unlocked: a star is set, or it is equipped). */
export function visibleArtifacts(art: ArtifactSchema, state: ArtifactsState | undefined, f: TableFilter): ArtifactInfo[] {
  const q = f.text.trim().toLowerCase();
  return art.artifacts.filter((a) => {
    if (q && !a.name.toLowerCase().includes(q)) return false;
    const e = state?.[a.key];
    return !f.onlyActive || !!e?.equipped || (e ? e.star !== null : defaultTableStar(art, a.key) !== null);
  });
}

// ---------------------------------------------------------------------------------------------------------------------------------------
// effect text
// ---------------------------------------------------------------------------------------------------------------------------------------
/** Wording of one artifact's Equip effect.  ``{value_key}`` placeholders are star values (STAR_VALUES) at the chosen star. */
export interface EffectSpec {
  live: string[]; // what the model applies (uptime / content conditions in ``note``)
  baked?: string[]; // stats the user types into Inputs by hand (the model only reports them)
  note?: string; // when it applies / how it is averaged
  rows?: string[]; // result.artifacts.rows keys carrying the live value(s)
  refs?: string[]; // result.artifacts.reference_only keys carrying the baked value(s)
  bucket?: string; // which pipeline bucket the live value feeds
  companion?: "companion" | "status"; // read by the companion model / the Status-effect timeline
}

export const EFFECTS: Record<string, EffectSpec> = {
  charm_of_the_undead: {
    live: ["+{charm_of_the_undead_attack_pct}% Attack while the charm is up"],
    note: "Up 5 s of every 10 s from second 10 (50% duty in steady-state content); timed in the status-effect timeline.",
    rows: ["charm_of_the_undead"], bucket: "Attack %", companion: "status",
  },
  pigs_ribbon: { live: [] },
  shamaness_marble: {
    live: [], baked: ["+{shamaness_marble_buff_duration_increase_pct}% Buff Duration"], refs: ["shamaness_marble_buff_duration_increase_pct"],
  },
  contract_of_darkness: {
    live: ["+{contract_of_darkness_crit_rate}% Critical Rate against bosses"], note: "Not in PvP.",
    rows: ["contract_of_darkness_crit_rate_bonus"], bucket: "Boss Crit Rate (boss branch only)",
  },
  rainbow_snail_shell: {
    live: ["+{rainbow_snail_shell_crit_rate}% Critical Rate", "+{rainbow_snail_shell_crit_damage}% Critical Damage"],
    note: "First 15 s of a fight (fixed-duration / PvP content only; uptime-weighted, 0 in steady-state content).",
    rows: ["rainbow_crit_rate", "rainbow_crit_damage"], bucket: "Crit Rate / Crit Damage",
  },
  hexagon_necklace: {
    live: ["+{hexagon_necklace_damage}% Damage per stack"],
    note: "A stack every 20 s from second 20, up to 3 (steady state = 3); counted in the status-effect timeline.",
    rows: ["hexagon_damage"], bucket: "Damage %", companion: "status",
  },
  arwens_glass_shoes: {
    live: ["+{arwens_glass_shoes_summon_time_increase_pct}% Companion Summoning Time Increase"],
    note: "Added to the Inputs value wherever the companion model reads it.",
    rows: ["arwens_glass_shoes_summon_time_increase_pct"], bucket: "Companion Summoning Time Increase %", companion: "companion",
  },
  mushmoms_cap: { live: [] },
  clear_spring_water: {
    live: [], baked: ["+{clear_spring_water_final_damage}% Final Damage in the Growth Dungeons"], refs: ["clear_spring_water_final_damage"],
  },
  athena_gloves: {
    live: [],
    baked: ["+{athena_gloves_attack_speed}% Attack Speed", "Max Damage +{athena_gloves_max_damage_pct_of_attack_speed}% of Attack Speed"],
    refs: ["athena_attack_speed", "athena_max_damage"],
  },
  zakums_stone_piece: { live: [] },
  horntails_scale: { live: [] },
  pink_beans_giant_rib: { live: [] },
  chalice: {
    live: ["+{chalice_final_damage}% Final Damage"],
    note: "A 30 s window at the end of a fixed fight (a kill-rate proc in steady-state normal content); normal / breakthrough content only.",
    rows: ["chalice_normal", "chalice_boss"], bucket: "Final Damage (normal-only / boss-only branch)",
  },
  old_music_box: {
    live: ["+{old_music_box_attack_pct}% Attack"],
    note: "Content-type uptime assumption: never in Chapter Hunt / Breakthrough / Growth Dungeons, always in World Boss / PvP, 6/7 in Chapter Boss.",
    rows: ["old_music_box_attack_pct"], bucket: "Attack %",
  },
  silver_pendant: {
    live: ["+{silver_pendant_enemy_dmg_taken}% enemy damage taken per stack (up to 5)"],
    note: "Average stacks from the attack rate; not in Chapter Hunt.", rows: ["silver_enemy_dmg_taken"], bucket: "Enemy Damage Taken %",
  },
  star_rock: { live: [], baked: ["+{star_rock_boss_damage}% Boss Monster Damage"], refs: ["star_rock_boss_damage"] },
  book_of_ancient: {
    live: [],
    baked: ["+{book_of_ancient_crit_rate}% Critical Rate", "Critical Damage +{book_of_ancient_crit_damage_pct_of_crit_rate}% of your Critical Rate"],
    refs: ["book_of_ancient_crit_rate", "book_of_ancient_crit_damage"],
  },
  lunar_dew: { live: [] },
  fire_flower: {
    live: ["+{fire_flower_final_damage_per_target}% Final Damage per target hit"],
    note: "1 target against a boss, 10 against normal monsters.", rows: ["fire_flower_boss", "fire_flower_normal"],
    bucket: "Final Damage (boss-only / normal-only branch)",
  },
  soul_contract: {
    live: ["-{soul_contract_cooldown_decrease_pct}% Skill Cooldown"], note: "Chapter Hunt only; applied to every skill's cooldown.",
    rows: ["soul_contract_pct"], bucket: "Skill Cooldown Decrease %",
  },
  lit_lamp: { live: [], baked: ["+{lit_lamp_final_damage}% Final Damage in World Boss"], refs: ["lit_lamp_final_damage"] },
  soul_pouch: { live: [], baked: ["+{soul_pouch_final_damage}% Final Damage in PvP"], refs: ["soul_pouch_final_damage"] },
  ancient_text_piece: { live: [] },
  icy_soul_rock: {
    live: ["+{icy_soul_rock_crit_damage}% Critical Damage"], note: "Averaged at 1.5x its base value (MP is not modelled).",
    rows: ["icy_soul_rock"], bucket: "Crit Damage",
  },
  flaming_lava: {
    live: ["+{flaming_lava_final_damage_debuffed}% Final Damage against debuffed targets"], note: "Targets are assumed debuffed; not in Chapter Hunt.",
    rows: ["flaming_lava"], bucket: "Final Damage",
  },
  sayrams_necklace: {
    live: ["+{sayrams_necklace_normal_damage}% Normal Monster Damage", "+{sayrams_necklace_boss_damage}% Boss Monster Damage"],
    rows: ["sayrams_necklace_normal", "sayrams_necklace_boss"], bucket: "Normal / Boss Monster Damage %",
  },
  bottle_of_emotion: {
    live: ["+{bottle_of_emotion_attack_pct}% Attack"],
    baked: ["+{bottle_of_emotion_final_damage_per_3pct_as}% Final Damage per 3% Attack Speed above 60% (cap {bottle_of_emotion_final_damage_cap}%)"],
    rows: ["bottle_of_emotion_attack_pct"], refs: ["bottle_of_emotion_final_damage"], bucket: "Attack %",
  },
  peach_tree: {
    live: ["+{peach_tree_enemy_dmg_taken}% enemy damage taken"], note: "Refreshing 5 s window proc (uptime from the attack rate); not in Chapter Hunt.",
    rows: ["peach_enemy_dmg_taken"], bucket: "Enemy Damage Taken %",
  },
  candle: {
    live: ["+{candle_final_damage}% Final Damage", "+{candle_boss_damage}% Boss Monster Damage (seconds 20-40)"],
    note: "Fixed-duration and PvP fights only (0 in steady-state content).", rows: ["candle_final_damage", "candle_boss_damage"],
    bucket: "Final Damage / Boss Monster Damage %",
  },
  alliance_badge: { live: ["+{alliance_badge_attack_pct}% Attack"], rows: ["alliance_badge"], bucket: "Attack %" },
  horn_flute: {
    live: ["+{horn_flute_final_damage}% Final Damage (doubled in Chapter Boss)"],
    note: "Weighted by the uptime of the companion's Horn window.", rows: ["horn_flute"], bucket: "Final Damage", companion: "companion",
  },
  cursed_doll: { live: [], baked: ["+{cursed_doll_final_damage}% Final Damage"], refs: ["cursed_doll_final_damage"] },
  reindeer_spear: {
    live: ["+{reindeer_spear_attack_pct}% Attack", "Extra applications of its Defense Penetration against bosses / PvP (2x extra vs bosses, 1x in PvP)"],
    baked: ["+{reindeer_spear_def_pen}% Defense Penetration (the base 1x)"],
    note: "The base Defense Penetration is typed into Inputs; the model adds the extra boss / PvP applications on top.",
    rows: ["reindeer_spear_attack_pct"], refs: ["reindeer_spear_base_def_pen"], bucket: "Attack % and a boss / PvP defense correction",
  },
  secret_map: {
    live: ["+{secret_map_attack_pct}% Attack", "+{secret_map_final_damage}% Final Damage against normal monsters (x3 in Growth Dungeons)"],
    rows: ["secret_map_attack_pct", "secret_map_final_dmg_normal"], bucket: "Attack % / Final Damage (normal-only branch)",
  },
  ring_of_cycles: {
    live: [
      "Crit Rate below 100%: +{ring_of_cycles_crit_rate}% Critical Rate",
      "Crit Rate at 100% or more: +{ring_of_cycles_skill_damage}% Skill Damage and +{ring_of_cycles_basic_attack_damage_per_point}% Basic Attack Damage per 1% over 100",
    ],
    note: "Starts 5 s into the fight; the branch follows your total Critical Rate.",
    rows: ["roc_crit_rate", "roc_skill_damage", "roc_basic_attack_damage"], bucket: "Crit Rate / Skill Damage / Basic Attack Damage",
  },
};

export function formatValue(v: number): string {
  return String(Number(v.toFixed(2)));
}

/** Fill the ``{value_key}`` placeholders with the star value at ``star``; unknown keys are left visible so a gap shows up in tests. */
export function fillTemplate(text: string, star: number | string | null | undefined): string {
  const s = starIndex(star);
  return text.replace(/\{([a-z0-9_]+)\}/g, (m, k: string) => (STAR_VALUES[k] ? formatValue(STAR_VALUES[k][s]) : m));
}

export interface EffectText {
  live: string[];
  baked: string[];
  note?: string;
  summary: string; // one line (live part, else baked part, else "no effect")
}

export function effectText(key: string, star: number | string | null | undefined): EffectText {
  const spec = EFFECTS[key];
  if (!spec) return { live: [], baked: [], summary: "" };
  const live = spec.live.map((t) => fillTemplate(t, star));
  const baked = (spec.baked ?? []).map((t) => fillTemplate(t, star));
  return { live, baked, note: spec.note, summary: (live.length ? live : baked).join("; ") };
}

/** Every ``{placeholder}`` of an artifact's templates (tests: each must exist in the engine's value table). */
export function placeholders(key: string): string[] {
  const spec = EFFECTS[key];
  if (!spec) return [];
  return [...spec.live, ...(spec.baked ?? [])].flatMap((t) => [...t.matchAll(/\{([a-z0-9_]+)\}/g)].map((m) => m[1]));
}

// ---------------------------------------------------------------------------------------------------------------------------------------
// badges
// ---------------------------------------------------------------------------------------------------------------------------------------
export type BadgeKind = "baked" | "companion" | "status" | "no_dps";
export interface Badge {
  kind: BadgeKind;
  label: string;
  detail: string;
  partial?: boolean; // baked: only part of the artifact is baked, the rest is live
}

export const BAKED_LABEL = "Baked into your stats";
export const BAKED_DETAIL = "type the stat into Inputs";

export const isNoDps = (info: ArtifactInfo): boolean => !!info.no_dps_effect || info.effect === "no_dps_effect" || info.effect === "zero";

export function badgesFor(info: ArtifactInfo): Badge[] {
  const spec = EFFECTS[info.key];
  const out: Badge[] = [];
  if (isNoDps(info)) {
    out.push({ kind: "no_dps", label: "No DPS effect", detail: info.reason || "no effect in the DPS model" });
    return out;
  }
  const bakedLines = spec?.baked?.length ?? 0;
  if (info.effect === "reference_only" || bakedLines > 0) {
    const partial = (spec?.live.length ?? 0) > 0;
    out.push({
      kind: "baked", partial,
      label: partial ? "Partly baked into your stats" : BAKED_LABEL,
      detail: partial ? `${BAKED_DETAIL} (only the part listed as "baked"; the rest is applied live)` : BAKED_DETAIL,
    });
  }
  if (spec?.companion === "companion") out.push({ kind: "companion", label: "Companion effect", detail: "read by the companion model" });
  if (spec?.companion === "status") out.push({ kind: "status", label: "Companion effect", detail: "timed together with the companion / status effects" });
  return out;
}

// ---------------------------------------------------------------------------------------------------------------------------------------
// result breakdown
// ---------------------------------------------------------------------------------------------------------------------------------------
type Unit = "%" | "s" | "";
const ROW_LABELS: Record<string, [string, Unit]> = {
  charm_of_the_undead: ["Attack % (time-averaged)", "%"],
  contract_of_darkness_crit_rate_bonus: ["Boss Critical Rate", "%"],
  rainbow_crit_rate: ["Critical Rate (time-averaged)", "%"],
  rainbow_crit_damage: ["Critical Damage (time-averaged)", "%"],
  hexagon_damage: ["Damage % (time-averaged)", "%"],
  arwens_glass_shoes_summon_time_increase_pct: ["Companion Summoning Time Increase", "%"],
  chalice_normal: ["Final Damage, normal branch (time-averaged)", "%"],
  chalice_boss: ["Final Damage, boss branch (time-averaged)", "%"],
  old_music_box_attack_pct: ["Attack % (uptime-weighted)", "%"],
  silver_enemy_dmg_taken: ["Enemy Damage Taken (average stacks)", "%"],
  fire_flower_boss: ["Final Damage, boss branch", "%"],
  fire_flower_normal: ["Final Damage, normal branch", "%"],
  soul_contract_pct: ["Skill Cooldown Decrease", "%"],
  icy_soul_rock: ["Critical Damage (x1.5 average)", "%"],
  flaming_lava: ["Final Damage", "%"],
  sayrams_necklace_normal: ["Normal Monster Damage", "%"],
  sayrams_necklace_boss: ["Boss Monster Damage", "%"],
  bottle_of_emotion_attack_pct: ["Attack %", "%"],
  peach_enemy_dmg_taken: ["Enemy Damage Taken (uptime-weighted)", "%"],
  candle_final_damage: ["Final Damage", "%"],
  candle_boss_damage: ["Boss Monster Damage (window-weighted)", "%"],
  alliance_badge: ["Attack %", "%"],
  horn_flute: ["Final Damage (uptime-weighted)", "%"],
  reindeer_spear_attack_pct: ["Attack %", "%"],
  secret_map_attack_pct: ["Attack %", "%"],
  secret_map_final_dmg_normal: ["Final Damage, normal branch", "%"],
  roc_crit_rate: ["Critical Rate", "%"],
  roc_skill_damage: ["Skill Damage", "%"],
  roc_basic_attack_damage: ["Basic Attack Damage", "%"],
};
const REF_LABELS: Record<string, [string, Unit]> = {
  shamaness_marble_buff_duration_increase_pct: ["Buff Duration", "%"],
  clear_spring_water_final_damage: ["Final Damage (Growth Dungeons only, else 0)", "%"],
  athena_attack_speed: ["Attack Speed", "%"],
  athena_max_damage: ["Max Damage (from your Attack Speed)", "%"],
  star_rock_boss_damage: ["Boss Monster Damage", "%"],
  book_of_ancient_crit_rate: ["Critical Rate", "%"],
  book_of_ancient_crit_damage: ["Critical Damage (from your Critical Rate)", "%"],
  lit_lamp_final_damage: ["Final Damage (World Boss only, else 0)", "%"],
  soul_pouch_final_damage: ["Final Damage (PvP only, else 0)", "%"],
  bottle_of_emotion_final_damage: ["Final Damage (from your Attack Speed)", "%"],
  cursed_doll_final_damage: ["Final Damage", "%"],
  reindeer_spear_base_def_pen: ["Defense Penetration", "%"],
};
export const BUCKET_LABELS: Record<string, string> = {
  attack_pct: "Attack %",
  final_damage: "Final Damage %",
  damage: "Damage %",
  skill_damage: "Skill Damage %",
  basic_attack_damage: "Basic Attack Damage %",
  crit_rate: "Critical Rate %",
  crit_damage: "Critical Damage %",
  boss_damage: "Boss Monster Damage %",
  normal_damage: "Normal Monster Damage %",
  enemy_damage_taken: "Enemy Damage Taken %",
  final_damage_normal_only: "Final Damage % (normal branch only)",
  final_damage_boss_only: "Final Damage % (boss branch only)",
  soul_contract_cooldown_decrease_pct: "Skill Cooldown Decrease %",
  contract_of_darkness_boss_crit_rate: "Boss Critical Rate %",
  reindeer_spear_extra_def_pen_unit: "Reindeer's Spear extra Defense Penetration unit %",
  companion_summon_time_increase_pct: "Companion Summoning Time Increase %",
};

export interface BreakdownValue {
  label: string;
  value: number;
  unit: Unit;
  applied: boolean; // false: reference only (type it into Inputs; not applied live)
}
export interface BreakdownRow {
  key: string;
  name: string;
  star: number;
  badges: Badge[];
  bucket: string;
  values: BreakdownValue[];
  note?: string;
}

const num = (x: unknown): number | null => (typeof x === "number" && Number.isFinite(x) ? x : null);
const asRec = (x: unknown): Record<string, unknown> => (x && typeof x === "object" ? (x as Record<string, unknown>) : {});

/** Per equipped artifact (from ``result.artifacts``): the values the engine used and the bucket they feed.  Empty without an artifacts block. */
export function breakdown(result: ComputeResult | null | undefined): BreakdownRow[] {
  const block = asRec(result?.artifacts);
  const equipped = Array.isArray(block.equipped) ? (block.equipped as Record<string, unknown>[]) : [];
  const rows = asRec(block.rows);
  const refs = asRec(block.reference_only);
  return equipped.map((e) => {
    const key = String(e.key);
    const spec = EFFECTS[key];
    const info = { key, name: String(e.name ?? key), rank: String(e.rank ?? ""), default_star: null, effect: e.effect as ArtifactInfo["effect"],
      no_dps_effect: !!e.no_dps_effect, reason: (e.reason as string | null) ?? null } satisfies ArtifactInfo;
    const values: BreakdownValue[] = [];
    for (const k of spec?.rows ?? []) {
      const v = num(rows[k]);
      const [label, unit] = ROW_LABELS[k] ?? [k, ""];
      if (v !== null) values.push({ label, value: v, unit, applied: true });
    }
    for (const k of spec?.refs ?? []) {
      const v = num(refs[k]);
      const [label, unit] = REF_LABELS[k] ?? [k, ""];
      if (v !== null) values.push({ label, value: v, unit, applied: false });
    }
    return {
      key, name: info.name, star: starIndex(num(e.star)), badges: badgesFor(info),
      bucket: isNoDps(info) ? "none" : spec?.bucket ?? (spec?.baked?.length ? "none (reference only)" : ""), values,
      note: isNoDps(info) ? info.reason ?? undefined : spec?.note,
    };
  });
}

/** Non-zero bucket totals of ``result.artifacts.buckets`` with readable labels (a summary of what the equipped artifacts feed into the model). */
export function bucketTotals(result: ComputeResult | null | undefined): { key: string; label: string; value: number }[] {
  const b = asRec(asRec(result?.artifacts).buckets);
  return Object.entries(b)
    .map(([key, v]) => ({ key, label: BUCKET_LABELS[key] ?? key, value: num(v) ?? 0 }))
    .filter((x) => Math.abs(x.value) > 1e-12);
}

/** Total DPS with the artifacts vs without them: absolute and relative (null when the baseline is missing / zero). */
export function dpsDelta(withArtifacts: number, without: number | null | undefined): { abs: number; pct: number | null } | null {
  if (without === null || without === undefined || !Number.isFinite(without)) return null;
  return { abs: withArtifacts - without, pct: without > 0 ? (withArtifacts / without - 1) * 100 : null };
}

/** The compute request without artifacts (for the "vs no artifacts" comparison). */
export function withoutArtifacts(inputs: Record<string, unknown>): Record<string, unknown> {
  const { artifacts: _drop, ...rest } = inputs;
  void _drop;
  return rest;
}

/** The equipped artifacts for the Calculator's compact summary: in the schema's order, with the star as shown ("\u26053", "not unlocked" for a locked one). */
export function artifactsInUse(art: ArtifactSchema, state: ArtifactsState | undefined): { key: string; name: string; star: string }[] {
  return equippedKeys(art, state).map((key) => {
    const star = state?.[key]?.star ?? null;
    return { key, name: artifactInfo(art, key)?.name ?? key, star: star === null ? "not unlocked" : `\u2605${star}` };
  });
}
