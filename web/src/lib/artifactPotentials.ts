// Artifact potential lines logic (pure): the static tables, the request body built from the Artifacts table, result types and a port of the engine's formula that
// mock mode uses (tested against a real engine case).  The EDITABLE state lives in FormState.artifacts (lib/artifacts.ts); `PotentialsState` below is the
// request body of POST .../artifact-potentials and the shape profiles saved before the Artifacts table stored (migrated by `normalizeArtifacts`).
import type { ArtifactPotentialMeta } from "./cubes";
import { NONE_STAT } from "./cubes";
import { lineCount, normalizeArtifacts } from "./artifacts";
import staticTables from "./artifact_potential_tables.json";
import type { ArtifactLine, ArtifactSchema, ArtifactsState } from "../types";

export interface PotentialLine {
  rarity: string;
  stat: string;
}
export interface PotentialEntry {
  star?: number | string | null; // absent = the engine's default by rank (equipped artifacts: their slot's star)
  lines: PotentialLine[];
}
/** Request body of POST .../artifact-potentials (an entry per artifact with lines); also the OLD per-artifact state of the pre-table Artifacts tab. */
export type PotentialsState = Record<string, PotentialEntry>;

export interface PotentialLineResult {
  rarity: string;
  stat: string;
  active: boolean; // the Star Level reaches this line's unlock star
  gain: number; // DPS
}
export interface PotentialRow {
  key: string;
  label: string;
  rank: string;
  equipped: boolean;
  star: number; // resolved Star Level (0 for "Not Unlocked")
  lines: PotentialLineResult[];
  total: number; // Total Potential DPS gain of the artifact (same-stat lines add, different stats multiply)
}
export interface PotentialsResult {
  class_id: string;
  baseline_total: number;
  rows: PotentialRow[];
}

export function normalizePotentials(raw: unknown): PotentialsState {
  const out: PotentialsState = {};
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return out;
  for (const [k, v] of Object.entries(raw as Record<string, unknown>)) {
    if (!/^[a-z0-9_]+$/.test(k) || !v || typeof v !== "object") continue;
    const e = v as Partial<PotentialEntry>;
    // positions matter (line 1 / 2 / 3): a malformed line becomes an empty one instead of shifting the next lines up
    const lines = (Array.isArray(e.lines) ? e.lines : [])
      .slice(0, 3)
      .map((l): PotentialLine => (l && typeof l.rarity === "string" && typeof l.stat === "string" ? { rarity: l.rarity, stat: l.stat } : { rarity: "Rare", stat: NONE_STAT }));
    const entry: PotentialEntry = { lines };
    if ("star" in e && (e.star === null || typeof e.star === "number" || typeof e.star === "string")) entry.star = e.star;
    out[k] = entry;
  }
  return out;
}

/** The class-independent tables of the potential lines (rarities, rollable stats, value per stat and rarity, unlock stars): `GET .../cubes/meta`'s
 *  `artifact_potentials` when it has loaded, else the static copy shipped with the app (`artifact_potential_tables.json`, written by scripts/gen_fixtures.py from
 *  the engine; a test keeps the two equal), so the Artifacts table can be edited before the meta arrived and for classes without stat values. */
export type PotentialTables = Pick<ArtifactPotentialMeta, "rarities" | "stats" | "values" | "line_min_star" | "default_rarity" | "none_stat">;
export const STATIC_POTENTIAL_TABLES = staticTables as PotentialTables;
export const potentialTables = (meta: { artifact_potentials?: ArtifactPotentialMeta } | null | undefined): PotentialTables => meta?.artifact_potentials ?? STATIC_POTENTIAL_TABLES;

const isRolled = (t: PotentialTables, l: ArtifactLine) => l.stat !== NONE_STAT && t.stats.includes(l.stat) && t.rarities.includes(l.rarity);

/** Body of POST .../artifact-potentials: an entry (star + the artifact's lines) per artifact that has at least one line.  A line the tables do not know (a stat or
 *  rarity from an old profile / import) is sent as "(none)" - the API would refuse the whole request - and is flagged in the table. */
export function potentialsRequest(art: ArtifactSchema, state: ArtifactsState | undefined, tables: PotentialTables): PotentialsState {
  const cur = normalizeArtifacts(state, art);
  const out: PotentialsState = {};
  for (const info of art.artifacts) {
    const e = cur[info.key];
    const n = lineCount(info);
    const lines = e.lines.slice(0, n).map((l) => (isRolled(tables, l) ? { rarity: l.rarity, stat: l.stat } : { rarity: tables.default_rarity, stat: NONE_STAT }));
    if (!lines.some((l) => l.stat !== NONE_STAT)) continue;
    out[info.key] = { star: e.star ?? "Not Unlocked", lines };
  }
  return out;
}

/** Is this stored line something the potential tables can value?  (false = a stat / rarity that is not in the tables: flagged, worth 0, sent as "(none)") */
export const lineKnown = (t: PotentialTables, l: ArtifactLine): boolean => l.stat === NONE_STAT || (t.stats.includes(l.stat) && t.rarities.includes(l.rarity));

/** Star Level at which line `i` (0-based) starts to count. */
export const lineUnlockStar = (meta: Pick<ArtifactPotentialMeta, "line_min_star">, i: number) => meta.line_min_star[i] ?? 0;

export const resolveStar = (star: number | string | null | undefined) => (star === null || star === undefined || star === "Not Unlocked" ? 0 : Number(star));

/** Value of one line (stat at rarity), 0 when the stat has no table entry. */
export function lineValue(meta: Pick<ArtifactPotentialMeta, "values">, stat: string, rarity: string): number {
  return meta.values[stat]?.[rarity] ?? 0;
}

const same = (a: string, b: string) => a.toLowerCase() === b.toLowerCase();

/** Port of engine/potentials.py ``artifact_potential`` / ``potential_table`` (mock mode; `rate` = DPS per unit of every potential stat). */
export function computePotentials(meta: ArtifactPotentialMeta, state: PotentialsState, rate: Record<string, number>, total: number, equippedSlots: { key: string; star: number | string | null }[]): PotentialRow[] {
  return meta.artifacts.map((a) => {
    const slot = equippedSlots.find((s) => s.key === a.key);
    const e = state[a.key];
    const star = resolveStar(e && "star" in e ? e.star : slot ? slot.star : a.default_star);
    const lines: PotentialLine[] = Array.from({ length: a.lines }, (_v, i) => e?.lines[i] ?? { rarity: meta.default_rarity, stat: NONE_STAT });
    const gains = lines.map((l, i) => (star < lineUnlockStar(meta, i) || l.stat === NONE_STAT ? 0 : lineValue(meta, l.stat, l.rarity) * (rate[l.stat] ?? 0)));
    let factor = 1;
    lines.forEach((l, i) => {
      if (l.stat === NONE_STAT || lines.slice(0, i).some((o) => same(o.stat, l.stat))) return;
      const grouped = gains[i] + gains.slice(i + 1).reduce((acc, g, j) => acc + (same(lines[i + 1 + j].stat, l.stat) ? g : 0), 0);
      factor *= 1 + grouped / total;
    });
    return {
      key: a.key,
      label: a.label,
      rank: a.rank,
      equipped: !!slot,
      star,
      lines: lines.map((l, i) => ({ rarity: l.rarity, stat: l.stat, active: star >= lineUnlockStar(meta, i), gain: gains[i] })),
      total: total * (factor - 1),
    };
  });
}
