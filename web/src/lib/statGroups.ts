// ONE definition of how stat dropdowns are grouped and ordered (cube lines, artifact potential lines, Equipment compare): by kind of stat, not alphabetically.
// The names are the exact strings of the game tables (cube roll tables, artifact potential tables, the Equipment compare list).  A stat that is in none of the
// groups lands in a trailing "Other" group; statGroups.test.ts fails when a real stat does, so a new stat forces a decision here.
import { statChoices, type StatChoice } from "./cubes";

export interface StatGroup {
  label: string;
  stats: string[];
}

export const OTHER_GROUP = "Other";

export const STAT_GROUPS: readonly StatGroup[] = [
  { label: "Main stat %", stats: ["Str %", "Dex %", "Int %", "Luk %", "Main Stat %"] },
  { label: "Main stat (flat)", stats: ["Str", "Dex", "Int", "Luk", "Main Stat (flat)"] },
  { label: "Main stat scaling", stats: ["Main Stat Per Level", "Main Stat % per 4 Levels"] },
  { label: "Critical", stats: ["Critical Rate %", "Critical Damage %"] },
  {
    label: "Damage",
    stats: [
      "Damage %",
      "Boss Monster Damage %",
      "Normal Monster Damage %",
      "Final Damage %",
      "Min Damage Multiplier %",
      "Max Damage Multiplier %",
      "Min Damage %",
      "Max Damage %",
      "Basic Attack Damage %",
      "Skill Damage %",
      "Status Effect Damage %",
    ],
  },
  { label: "Attack and accuracy", stats: ["Attack (flat)", "Defense Penetration", "Defense Penetration %", "Attack Speed %", "Accuracy"] },
  {
    label: "Skills and utility",
    stats: [
      "All Skill Level",
      "Skill Level Bonus — 1st Job",
      "Skill Level Bonus — 2nd Job",
      "Skill Level Bonus — 3rd Job",
      "Skill Level Bonus — 4th Job",
      "Skill Level Bonus — All Skills",
      "Skill Cooldown Decrease (seconds)",
      "Buff Duration Increase %",
      "Basic Attack Target Increase",
      "Companion Summoning Time Increase %",
    ],
  },
  { label: "Defense and health", stats: ["Defense %", "Defense (flat)", "Max HP %", "Max MP %", "Damage Taken Decrease %"] },
];

/** `stats` split into the groups above, groups in their fixed order and the stats inside a group in the group's order (empty groups left out); stats that
 *  belong to no group follow in an "Other" group in the order they came in. */
export function groupStats(stats: readonly string[]): StatGroup[] {
  const have = new Set(stats);
  const placed = new Set<string>();
  const out: StatGroup[] = [];
  for (const g of STAT_GROUPS) {
    const own = g.stats.filter((s) => have.has(s) && !placed.has(s));
    own.forEach((s) => placed.add(s));
    if (own.length) out.push({ label: g.label, stats: own });
  }
  const rest = [...new Set(stats)].filter((s) => !placed.has(s));
  if (rest.length) out.push({ label: OTHER_GROUP, stats: rest });
  return out;
}

export interface StatChoiceGroup {
  label: string;
  choices: StatChoice[];
}
export interface GroupedStatChoices {
  /** "(none)" and - only when the current value cannot roll here - that value as one flagged entry: both sit above the groups */
  head: StatChoice[];
  groups: StatChoiceGroup[];
}

/** The entries of one stat select: `statChoices` (same "(none)" / flagged-current rules), the rollable stats grouped by `groupStats`. */
export function groupedStatChoices(rollable: string[], current: string, notRollable?: string, none?: string): GroupedStatChoices {
  const flat = statChoices(rollable, current, notRollable, none);
  const byValue = new Map(flat.map((c) => [c.value, c]));
  const inList = new Set(rollable);
  const head = flat.filter((c) => !inList.has(c.value));
  return { head, groups: groupStats(rollable).map((g) => ({ label: g.label, choices: g.stats.map((s) => byValue.get(s)!) })) };
}
