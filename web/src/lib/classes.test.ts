import { describe, expect, it } from "vitest";
import { defaultClassId, FAMILY_ORDER, groupClasses, optionLabel, statLabel, statusItems, statusLine } from "./classes";
import { classList } from "../test/fixtures";

describe("class picker logic (all 12 classes from the API fixture)", () => {
  it("lists 12 classes with a family, a stat identity and a status", () => {
    expect(classList).toHaveLength(12);
    for (const c of classList) {
      expect(c.family, c.id).toBeTruthy();
      expect(c.stat_identity, c.id).toBeTruthy();
      expect(c.status, c.id).toBeTruthy();
    }
  });
  it("groups by job family in game order, each group sorted by name", () => {
    const g = groupClasses(classList);
    expect(g.map((x) => x.family)).toEqual(FAMILY_ORDER);
    expect(g.flatMap((x) => x.classes)).toHaveLength(12);
    for (const grp of g) {
      const names = grp.classes.map((c) => c.name);
      expect(names).toEqual([...names].sort((a, b) => a.localeCompare(b)));
    }
    expect(g.find((x) => x.family === "Thief")!.classes.map((c) => c.id).sort()).toEqual(["night_lord", "shadower"]);
    expect(g.find((x) => x.family === "Mage")!.classes).toHaveLength(3);
  });
  it("puts unknown families after the known ones", () => {
    const g = groupClasses([...classList, { id: "x", name: "X", family: "Explorer" }, { id: "y", name: "Y" }]);
    expect(g.slice(-2).map((x) => x.family)).toEqual(["Explorer", "Other"]);
  });
  it("shows the stat identity in the option text", () => {
    const night = classList.find((c) => c.id === "night_lord")!;
    expect(statLabel(night)).toBe("LUK / DEX");
    expect(optionLabel(night)).toBe("Night Lord (LUK / DEX)");
    expect(optionLabel({ id: "z", name: "Z" })).toBe("Z");
  });
  it("status line says what is modelled; missing features read coming soon", () => {
    const fp = classList.find((c) => c.id === "fp_mage")!;
    const yes = (b?: boolean) => (b ? "yes" : "coming soon");
    for (const c of classList) {         // every fixture class: the line follows the API's status block
      expect(statusLine(c), c.id).toBe(`companions: ${yes(c.status?.companions)} · artifacts: ${yes(c.status?.artifacts)} · stat values: ${yes(c.status?.stat_values)}`);
      expect(statusItems(c).map((i) => i.state), c.id).toEqual([c.status?.companions, c.status?.artifacts, c.status?.stat_values].map((b) => (b ? "ready" : "soon")));
    }
    expect(statusLine(fp)).toContain("artifacts: yes");
    const partial = { id: "p", name: "P", status: { companions: true, artifacts: false, stat_values: false } };      // synthetic: a class with features still missing
    expect(statusLine(partial)).toBe("companions: yes · artifacts: coming soon · stat values: coming soon");
    expect(statusItems(partial).map((i) => i.state)).toEqual(["ready", "soon", "soon"]);
    expect(statusItems({ id: "a", name: "A", artifacts_modelled: true })[1].state).toBe("ready");     // an older API without `status`
  });
  it("loads FP-Mage first when available", () => {
    expect(defaultClassId(classList)).toBe("fp_mage");
    expect(defaultClassId(classList.filter((c) => c.id !== "fp_mage"))).toBe("dark_knight"); // first Warrior by name
    expect(defaultClassId([])).toBeNull();
  });
});
