// Class picker logic: grouping by job family, the stat identity label and the per-class "what is modelled" status line.
import type { ClassInfo } from "../types";

export const FAMILY_ORDER = ["Warrior", "Mage", "Archer", "Thief", "Pirate"];

export interface ClassGroup {
  family: string;
  classes: ClassInfo[];
}

/** "STR / DEX" (main / sub) or "" when the API did not send the identity. */
export function statLabel(c: ClassInfo): string {
  return c.stat_identity ? `${c.stat_identity.main} / ${c.stat_identity.sub}` : "";
}

/** Picker entry text: "Hero (STR / DEX)". */
export function optionLabel(c: ClassInfo): string {
  const s = statLabel(c);
  return s ? `${c.name} (${s})` : c.name;
}

/** Classes grouped by job family (known families first in game order, unknown ones after), each group sorted by name. */
export function groupClasses(classes: ClassInfo[]): ClassGroup[] {
  const byFamily = new Map<string, ClassInfo[]>();
  for (const c of classes) {
    const fam = c.family || "Other";
    byFamily.set(fam, [...(byFamily.get(fam) ?? []), c]);
  }
  const rank = (f: string) => (FAMILY_ORDER.includes(f) ? FAMILY_ORDER.indexOf(f) : FAMILY_ORDER.length);
  return [...byFamily.entries()]
    .sort((a, b) => rank(a[0]) - rank(b[0]) || a[0].localeCompare(b[0]))
    .map(([family, list]) => ({ family, classes: [...list].sort((a, b) => a.name.localeCompare(b.name)) }));
}

export interface StatusItem {
  label: string;
  state: "ready" | "soon";
}

/** What the engine models for this class; features it lacks read "coming soon". */
export function statusItems(c: ClassInfo): StatusItem[] {
  const st = c.status ?? {};
  const artifacts = st.artifacts ?? c.artifacts_modelled ?? false;
  return [
    { label: "Companions", state: st.companions === false ? "soon" : "ready" },
    { label: "Artifacts", state: artifacts ? "ready" : "soon" },
    { label: "Stat values", state: st.stat_values ? "ready" : "soon" },
  ];
}

/** "Status - companions: yes - artifacts: coming soon - stat values: coming soon" (plain text, used for tooltips / tests). */
export function statusLine(c: ClassInfo): string {
  return statusItems(c)
    .map((i) => `${i.label.toLowerCase()}: ${i.state === "ready" ? "yes" : "coming soon"}`)
    .join(" · ");
}

/** Class selected on load: FP-Mage (the reference class) when the API has it, else the first class of the first family. */
export function defaultClassId(classes: ClassInfo[]): string | null {
  if (classes.some((c) => c.id === "fp_mage")) return "fp_mage";
  return groupClasses(classes)[0]?.classes[0]?.id ?? null;
}
