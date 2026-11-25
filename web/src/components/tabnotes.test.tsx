// "Less is more": the working area of each tab stays small; the explanations live in a collapsed "About this tab" block at the BOTTOM of the tab.
import { describe, expect, it } from "vitest";
import { renderToString } from "react-dom/server";
import { sensFixture } from "../test/sensFixture";
import { cubesFixture } from "../test/cubesFixture";
import { fixtureFor, classList, NO_STAT_VALUES } from "../test/fixtures";
import { initialState } from "../lib/schemaForm";
import { IDLE } from "../lib/sensitivityLoader";
import { IDLE_STATUS } from "../lib/liveRequest";
import { blankEquip } from "../lib/equipment";
import { CompanionsView } from "./CompanionsPanel";
import { EquipmentView } from "./EquipmentPanel";
import { StatValuesView } from "./StatValues";
import { ArtifactsPanel } from "./ArtifactsPanel";
import { ProfilesPanel } from "./ProfilesPanel";
import { Unavailable } from "./TabNotes";

const strip = (h: string) => h.replace(/<!-- -->/g, "");
const noop = () => undefined;
const fp = fixtureFor("fp_mage");
const sens = sensFixture();
const cubes = cubesFixture();
const state = initialState(fp.schema, fp.defaults["World Boss"], "World Boss");
const about = '<details class="about-tab"><summary>About this tab</summary>';

describe("About this tab: collapsed, at the bottom", () => {
  const tabs: Record<string, string> = {
    companions: strip(renderToString(<CompanionsView schema={fp.schema} state={state} onState={noop} result={sens.result} status={IDLE} supported />)),
    equipment: strip(renderToString(<EquipmentView meta={cubes.meta} metaStatus={IDLE_STATUS} state={blankEquip()} onState={noop} result={cubes.equipment.result} status={IDLE_STATUS} />)),
    stats: strip(renderToString(<StatValuesView result={sens.result} status={IDLE} meta={sens.meta} open={[]} />)),
    artifacts: strip(renderToString(<ArtifactsPanel schema={fp.schema} classInfo={fp.info} state={state} onState={noop} result={null} busy={false} stale={false} onOpenCompanion={noop} />)),
    profiles: strip(renderToString(<ProfilesPanel state={state} classes={classList} onLoad={noop} />)),
  };
  it.each(Object.keys(tabs))("%s: one collapsed block after the working area", (name) => {
    const html = tabs[name];
    expect((html.match(/class="about-tab"/g) ?? []).length).toBe(1);
    expect(html).toContain(about);
    expect(html).not.toMatch(/<details class="about-tab" open/);
    // nothing but the block itself comes after it (profiles: it is the last thing in the card)
    expect(html.indexOf(about)).toBeGreaterThan(html.length * 0.4);
  });
  it("the long intro paragraphs are gone from the top of the tabs", () => {
    expect(tabs.companions.indexOf("Damage multiplier by level")).toBeGreaterThan(tabs.companions.indexOf(about));
    expect(tabs.artifacts.indexOf("Potential lines are a reference calculator")).toBeGreaterThan(tabs.artifacts.indexOf(about));
    expect(tabs.equipment.indexOf("priced against your Total DPS")).toBeGreaterThan(tabs.equipment.indexOf(about));
  });
});

describe("Not available for this class yet: one line and a See Help link", () => {
  it("the link only exists when the app passes onOpenHelp", () => {
    expect(renderToString(<Unavailable />)).not.toContain("See Help");
    const h = strip(renderToString(<Unavailable onOpenHelp={noop} />));
    expect(h).toContain("Not available for this class yet.");
    expect(h).toContain(">See Help</button>");
  });
  it("Stat values and Equipment compare show just that line", () => {
    const sv = strip(renderToString(<StatValuesView result={null} status={{ ...IDLE, unsupported: true }} open={[]} onOpenHelp={noop} />));
    expect(sv).toContain("Not available for this class yet.");
    expect(sv).toContain("See Help");
    expect(sv).not.toContain("About this tab");
    const eq = strip(renderToString(<EquipmentView meta={null} metaStatus={IDLE_STATUS} state={blankEquip()} onState={noop} result={null} status={{ ...IDLE_STATUS, unsupported: true }} onOpenHelp={noop} />));
    expect(eq).toContain("Not available for this class yet.");
    expect(eq).toContain("See Help");
  });
  it("Companions keeps the levels and says the numbers are missing", () => {
    const x = NO_STAT_VALUES[0];
    const h = strip(renderToString(<CompanionsView schema={x.schema} state={initialState(x.schema, x.defaults["World Boss"], "World Boss")} onState={noop} result={null} status={IDLE} supported={false} onOpenHelp={noop} />));
    expect(h).toContain("not available for this class yet");
    expect(h).toContain("See Help");
    expect((h.match(/data-companion=/g) ?? []).length).toBe(16);
  });
});

describe("Companions table", () => {
  const h = strip(renderToString(<CompanionsView schema={fp.schema} state={state} onState={noop} result={sens.result} status={IDLE} supported />));
  it("no duplicate 'Resolved' level column; one column 'DPS it adds' showing % only", () => {
    expect(h).not.toContain("Resolved");
    expect(h).toContain(">DPS it adds<");
    expect(h).not.toContain(">% DPS it adds<");
    const row = h.match(/<tr class="[^"]*" data-companion="Hero"[\s\S]*?<\/tr>/)![0];
    expect((row.match(/<td/g) ?? []).length).toBe(5);                                           // rank, name, level select, DPS it adds (%), use
    expect(h).toMatch(/<th scope="col"[^>]*>Level<\/th>/);
  });
});

describe("Profiles", () => {
  const h = strip(renderToString(<ProfilesPanel state={state} classes={classList} onLoad={noop} />));
  it("empty state with a next step, stored-in-this-browser wording, JSON import label, Excel import tucked into Advanced", () => {
    expect(h).toContain("No saved profiles yet. Type a name above and press Save current inputs.");
    expect(h).toContain("Stored in this browser only.");
    expect(h).not.toContain("localStorage");
    expect(h).toContain("Import saved profiles (.json)");
    expect(h).not.toContain(">Import file<");
    expect(h.indexOf("<summary>Advanced</summary>")).toBeGreaterThan(h.indexOf("Export all"));
    expect(h.indexOf("Import from the old Excel calculator (optional)")).toBeGreaterThan(h.indexOf("<summary>Advanced</summary>"));
  });
});
