import { describe, expect, it } from "vitest";
import { panelId, tabForKey, tabId, tabsNotAvailable, TABS } from "./tabs";

const ids = TABS.map((t) => t.id);

describe("tab bar", () => {
  it("is in workflow order", () => {
    expect(TABS.map((t) => t.label)).toEqual(["Calculator", "Companions", "Artifacts", "Stat values", "Cubes", "Equipment compare", "Profiles", "Help"]);
    expect(new Set(ids).size).toBe(ids.length);
  });
  it("ids pair a tab with its panel", () => {
    for (const t of ids) {
      expect(tabId(t)).toBe(`tab-${t}`);
      expect(panelId(t)).toBe(`panel-${t}`);
    }
  });
  it("arrow keys move to the neighbour and wrap, Home / End jump to the ends, other keys are not ours", () => {
    expect(tabForKey("calc", "ArrowRight")).toBe("companions");
    expect(tabForKey("calc", "ArrowLeft")).toBe("help");                      // wraps backwards
    expect(tabForKey("help", "ArrowRight")).toBe("calc");                     // wraps forwards
    expect(tabForKey("artifacts", "ArrowDown")).toBe("stats");
    expect(tabForKey("artifacts", "ArrowUp")).toBe("companions");
    expect(tabForKey("stats", "Home")).toBe("calc");
    expect(tabForKey("stats", "End")).toBe("help");
    for (const k of ["Enter", " ", "Tab", "a", "PageDown"]) expect(tabForKey("stats", k), k).toBeNull();
  });
  it("walking right through every tab visits each exactly once", () => {
    let cur = ids[0];
    const seen = [cur];
    for (let i = 1; i < ids.length; i++) seen.push((cur = tabForKey(cur, "ArrowRight")!));
    expect(seen).toEqual(ids);
    expect(tabForKey(cur, "ArrowRight")).toBe(ids[0]);
  });
  it("an unknown current tab gives nothing", () => {
    expect(tabForKey("nope" as never, "ArrowRight")).toBeNull();
  });  it("tabs that read 'soon': stat values / cubes / equipment only on an explicit stat_values false, artifacts when the schema has none", () => {
    expect(tabsNotAvailable({ stat_values: false }, true)).toEqual(["stats", "cubes", "equip"]);
    expect(tabsNotAvailable({ stat_values: true }, true)).toEqual([]);
    expect(tabsNotAvailable({}, true)).toEqual([]);                           // no information: nothing is claimed
    expect(tabsNotAvailable(undefined, true)).toEqual([]);
    expect(tabsNotAvailable({ stat_values: true }, false)).toEqual(["artifacts"]);
    expect(tabsNotAvailable({ stat_values: false }, false)).toEqual(["artifacts", "stats", "cubes", "equip"]);   // in tab order
  });
});
