// Types mirroring the engine's JSON (see src/fixtures/*.json, dumped from engine/classes/fp_mage.py).
import type { CubesState } from "./lib/cubes";
import type { EquipState } from "./lib/equipment";
import type { PotentialsState } from "./lib/artifactPotentials";
import type { CompanionsState } from "./lib/companions";

export type Scalar = string | number | null;
export type Values = Record<string, Scalar>;

export type FieldType = "int" | "float" | "text" | "enum";

export interface Field {
  key: string;
  label: string;
  group: string;
  type: FieldType;
  unit: string; // '%', 's', 'flat', ''
  default: Scalar;
  per_content: boolean; // the workbook keeps one value per content type
  applicable: string[] | null; // content types it applies to; null = all
  options: string[] | null; // dropdown values (enum)
  computed: boolean; // derived by the engine: read-only
  help: string | null;
  default_by_content: Record<string, Scalar> | null;
  min?: number | null; // inclusive numeric bounds from the schema (null / absent for enum, text, computed)
  max?: number | null;
}

export interface ArtifactInfo {
  key: string;
  name: string;
  rank: string;
  default_star: number | string | null;
  effect: "live" | "reference_only" | "no_dps_effect" | "zero"; // "zero" = legacy value of older schema snapshots (= no_dps_effect)
  no_dps_effect?: boolean; // genuinely no DPS effect in the model (stat not used / content not modelled)
  reason?: string | null; // why, when no_dps_effect
}

export interface ArtifactSchema {
  modelled: boolean;
  max_slots: number;
  none_label: string;
  star_options: (string | number)[];
  slot_options: string[];
  artifacts: ArtifactInfo[];
}

export interface ClassSchema {
  class_id: string;
  name: string;
  stat_identity: { main: string; sub: string };
  content_types: string[];
  companions: string[];
  fields: Field[];
  dps_rows: [string, string][];
  artifacts_modelled?: boolean;
  artifacts?: ArtifactSchema;
}

/** What the engine models for a class (GET /api/classes `status`). */
export interface ClassStatus {
  companions?: boolean;
  artifacts?: boolean;
  stat_values?: boolean; // marginal-DPS "Stat values" tab
}

export interface ClassInfo {
  id: string;
  name: string;
  family?: string; // job family: Warrior / Mage / Archer / Thief / Pirate
  stat_identity?: { main: string; sub: string };
  artifacts_modelled?: boolean;
  status?: ClassStatus;
}

export interface SkillResult {
  key: string;
  name: string;
  dps: number;
  share: number; // of total DPS, 0..1
  boss_dps: number;
  normal_dps: number;
  unlocked: boolean;
}

export interface CompanionResult {
  choice: string;
  level: number;
  dps: number;
  boss_dps: number;
  normal_dps: number;
  share: number;
  damage: number;
  uplift: number;
  best_candidate: number;
  summon_time_s: number;
  window_s: number;
  details?: Record<string, number>;
}

export interface ComputeResult {
  total_dps: number;
  player_dps: number;
  boss_dps: number;
  normal_dps: number;
  player_boss_dps: number;
  player_normal_dps: number;
  skills: SkillResult[];
  companion: CompanionResult | null;
  engine_on: boolean;
  engine?: Record<string, unknown>;
  artifacts?: Record<string, unknown>;
  derived: Record<string, unknown>;
}

export interface FieldError {
  field: string;
  message: string;
}

/** Form state: shared fields (not per content type) + one resolved value set per visited content type. */
export interface FormState {
  classId: string;
  contentType: string;
  shared: Values;
  perContent: Record<string, Values>;
  // Artifacts tab: ONE record per artifact (all 36, keyed by artifact id): star level, equipped, 3 potential lines.  Profiles saved before the table (a slots LIST +
  // `potentials`) are migrated by normalizeState (lib/artifacts.ts `normalizeArtifacts`).
  artifacts: ArtifactsState;
  // Companions tab: level of every companion owned + boots lines already in the summoning-time input (absent in profiles saved before the tab existed:
  // normalizeState migrates the old shared companion level)
  companions?: CompanionsState;
  // cube tabs (saved with the profile; absent in profiles saved before they existed)
  cubes?: CubesState; // PotentialCubes sheet: rarity / pity / 3 lines per (slot, potential type)
  equipment?: EquipState; // Equipment Compare: current vs new equip
  /** LEGACY (profiles saved before the Artifacts table): per-artifact potential lines; migrated into `artifacts` by normalizeState and dropped */
  potentials?: PotentialsState;
}

/** The engine's request entry of one equipped artifact (`inputs.artifacts = [{key, star}]`). */
export interface ArtifactSlot {
  key: string; // artifact id or none label
  star: number | string | null;
}

/** One potential line of an artifact: rarity + stat ("(none)" = empty). */
export interface ArtifactLine {
  rarity: string;
  stat: string;
}

/** One row of the Artifacts table (the workbook's ArtifactsInput row + its equipped state). */
export interface ArtifactEntry {
  star: number | null; // 0..5; null = "Not Unlocked" (acts as star 0 when equipped)
  equipped: boolean;
  lines: ArtifactLine[]; // always 3 (line 3 only counts for Legendary artifacts; the others keep a blank one)
}
export type ArtifactsState = Record<string, ArtifactEntry>;

export interface Profile {
  id: string;
  name: string;
  savedAt: string; // ISO
  state: FormState;
}
