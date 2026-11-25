// The tab bar: order, ids and the keyboard rule of a WAI-ARIA tablist (pure, unit-tested).
export type Tab = "calc" | "companions" | "artifacts" | "stats" | "cubes" | "equip" | "profiles" | "help";

/** Workflow order: set up the character, then the extras, then the analyses, then saved profiles and help. */
export const TABS: { id: Tab; label: string }[] = [
  { id: "calc", label: "Calculator" },
  { id: "companions", label: "Companions" },
  { id: "artifacts", label: "Artifacts" },
  { id: "stats", label: "Stat values" },
  { id: "cubes", label: "Cubes" },
  { id: "equip", label: "Equipment compare" },
  { id: "profiles", label: "Profiles" },
  { id: "help", label: "Help" },
];

export const tabId = (t: Tab) => `tab-${t}`;
export const panelId = (t: Tab) => `panel-${t}`;

/** Tab to move to for a key pressed on `current` (arrows wrap around, Home / End jump to the ends); null = the key is not ours. */
export function tabForKey(current: Tab, key: string, order: readonly Tab[] = TABS.map((t) => t.id)): Tab | null {
  const i = order.indexOf(current);
  if (i < 0) return null;
  switch (key) {
    case "ArrowRight":
    case "ArrowDown":
      return order[(i + 1) % order.length];
    case "ArrowLeft":
    case "ArrowUp":
      return order[(i - 1 + order.length) % order.length];
    case "Home":
      return order[0];
    case "End":
      return order[order.length - 1];
    default:
      return null;
  }
}

/** Tabs that read "soon" for a class: Stat values, Cubes and Equipment compare need the class's stat values; Artifacts needs artifact support.
 *  Only an explicit `stat_values: false` counts (a class list without a status says nothing), and `artifactsOk` comes from the loaded schema. */
export function tabsNotAvailable(status: { stat_values?: boolean } | undefined | null, artifactsOk: boolean): Tab[] {
  const out: Tab[] = [];
  if (status?.stat_values === false) out.push("stats", "cubes", "equip");
  if (!artifactsOk) out.push("artifacts");
  return TABS.map((t) => t.id).filter((t) => out.includes(t));
}
