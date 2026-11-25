// GUARD: players never saw the old spreadsheets or our internals, so no user-visible text of the app may mention them.  Every tab (and Help) is rendered with the
// fixtures and its visible text (text nodes + title / aria-label / placeholder attributes) is checked, case-insensitive and whole-word, against the list below.
// The ONE exception is the optional Excel import (Profiles > Advanced and its dialog), which is cut out of the Profiles render and is tested separately.
import { describe, expect, it } from "vitest";
import { renderToString } from "react-dom/server";
import { ALL, classList, fixtureFor, NO_STAT_VALUES } from "./test/fixtures";
import { sensFixture } from "./test/sensFixture";
import { cubesFixture } from "./test/cubesFixture";
import { initialState } from "./lib/schemaForm";
import { IDLE } from "./lib/sensitivityLoader";
import { IDLE_STATUS } from "./lib/liveRequest";
import { blankEquip } from "./lib/equipment";
import { emptyArtifacts, normalizeSlots, setStar } from "./lib/artifacts";
import type { ArtifactSchema, ComputeResult, FormState } from "./types";
import { HelpPanel } from "./components/HelpPanel";
import { InputsForm } from "./components/InputsForm";
import { Results } from "./components/Results";
import { ProfilesPanel } from "./components/ProfilesPanel";
import { ArtifactsPanel } from "./components/ArtifactsPanel";
import { CompanionsView } from "./components/CompanionsPanel";
import { EquipmentView } from "./components/EquipmentPanel";
import { StatValuesView } from "./components/StatValues";
import { CubesPanel } from "./components/CubesPanel";
import { HistoryDialog } from "./components/account/dialogs";
import { syncStatusText } from "./components/account/AccountMenu";
import { CLOUD_STATUS_TEXT } from "./components/CloudStatusIcon";
import { ImportDialog, ImportXlsx } from "./components/ImportXlsx";
import { ACCOUNTS, PRIVACY } from "./content/help";
import { plainText } from "./lib/plainText";

/** Whole words that must not appear.  "Inputs" is the old name of the Calculator tab (capitalised: lower-case "inputs" is an ordinary word). */
export const FORBIDDEN = /\b(excel|workbooks?|sheets?|spreadsheets?|engine|models?|modell?(?:ed|ing)|golden|sensitivity|snapshots?|artifactsinput|potentialcubes|companionsinput|verify scripts?)\b/i;
export const FORBIDDEN_CASE = /\bInputs\b/;
/** Genuine game terms that happen to match (none today; add a word here with the reason, never a whole sentence). */
const WHITELIST: string[] = [];

const decode = (t: string) => t.replace(/&quot;/g, '"').replace(/&#x27;/g, "'").replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">");
/** Visible text of a rendered fragment: text nodes plus the attributes a reader can see (tooltips, labels, placeholders). */
export function visibleText(html: string): string {
  const attrs = [...html.matchAll(/\s(?:title|aria-label|placeholder|alt)="([^"]*)"/g)].map((m) => m[1]);
  return decode(`${html.replace(/<!-- -->/g, "").replace(/<[^>]*>/g, " ")} ${attrs.join(" ")}`);
}
export function violations(text: string): string[] {
  let t = text;
  for (const w of WHITELIST) t = t.split(w).join(" ");
  const out: string[] = [];
  for (const re of [new RegExp(FORBIDDEN.source, "gi"), new RegExp(FORBIDDEN_CASE.source, "g")]) {
    for (const m of t.matchAll(re)) out.push(`"${t.slice(Math.max(0, m.index! - 40), m.index! + m[0].length + 40).replace(/\s+/g, " ")}"`);
  }
  return out;
}
const expectClean = (label: string, html: string) => expect(violations(visibleText(html)), label).toEqual([]);

const noop = () => undefined;
const fp = fixtureFor("fp_mage");
const sens = sensFixture();
const cubes = cubesFixture();
const fresh = (c = fp, ct = "World Boss") => initialState(c.schema, c.defaults[ct], ct);

describe("the guard itself", () => {
  it("flags the forbidden words (whole words, any case) and ignores ordinary ones", () => {
    for (const bad of ["Open the Excel file", "the workbook", "an Inputs sheet", "the engine", "the Sensitivity tab", "a golden test", "a snapshot", "the model", "ArtifactsInput", "PotentialCubes", "spreadsheet", "verify script"])
      expect(violations(bad).length, bad).toBeGreaterThan(0);
    for (const ok of ["the inputs you type", "modelling", "Model of the game".replace("Model", "Pattern"), "sheets".replace("sheets", "pages"), "Total DPS"]) expect(violations(ok.replace("modelling", "calculation")), ok).toEqual([]);
    expect(violations("the model")).toHaveLength(1);
    expect(violations("a modelled skill")).toHaveLength(1);
  });
});

describe("Help", () => {
  it.each(ALL.map((c) => [c.info.id, c] as const))("%s: no spreadsheet / internals talk (incl. the field hints of that class)", (_id, c) => {
    expectClean(_id, renderToString(<HelpPanel classes={classList} schema={c.schema} />));
  });
  it("without a class, and the privacy / accounts copy", () => {
    expectClean("no schema", renderToString(<HelpPanel classes={[]} schema={null} />));
    expectClean("accounts", renderToString(<div>{ACCOUNTS.body}</div>));
    expectClean("privacy", renderToString(<div>{PRIVACY.body}</div>));
  });
});

describe("Calculator tab", () => {
  it.each(ALL.map((c) => [c.info.id, c] as const))("%s: the form of every content type and the result", (id, c) => {
    for (const ct of c.schema.content_types) {
      expectClean(`${id}/${ct}`, renderToString(<InputsForm schema={c.schema} classInfo={c.info} state={fresh(c, ct)} onState={noop} errors={{}} derived={c.result.derived} loadDefaults={noop} onOpenCompanions={noop} onOpenArtifacts={noop} />));
    }
    expectClean(`${id}/result`, renderToString(<Results result={c.result} busy={false} stale={false} />));
  });
});

describe("the schema texts of every class (labels, help, groups, artifact reasons as shown)", () => {
  it.each(ALL.map((c) => [c.info.id, c] as const))("%s", (id, c) => {
    const texts: string[] = [];
    for (const f of c.schema.fields) texts.push(f.label, f.help ?? "", f.group ?? "", f.unit ?? "");
    for (const a of c.schema.artifacts?.artifacts ?? []) texts.push(a.name, plainText(a.reason)); // (reasons reach the screen through plainText)
    expect(violations(texts.join(" . ")), id).toEqual([]);
  });
});

describe("Companions, Artifacts, Stat values, Equipment compare, Cubes, Profiles", () => {
  it("Companions: with results, empty, and for a class without stat values", () => {
    const props = { schema: fp.schema, state: fresh(), onState: noop, onOpenCalculator: noop, onOpenHelp: noop, supported: true, status: IDLE };
    expectClean("with result", renderToString(<CompanionsView {...props} result={sens.result} />));
    expectClean("empty", renderToString(<CompanionsView {...props} result={null} />));
    const x = NO_STAT_VALUES[0];
    expectClean("unsupported", renderToString(<CompanionsView {...props} schema={x.schema} state={fresh(x)} result={null} supported={false} />));
  });
  it("Artifacts: table + breakdown + ranking for every modelled class, and the unavailable panel", async () => {
    for (const c of ALL.filter((x) => x.schema.artifacts_modelled)) {
      const art = c.schema.artifacts as ArtifactSchema;
      const kase = (await import(`./fixtures/${c.info.id}.artifacts_case.json`)).default as { result: ComputeResult };
      let t = emptyArtifacts(art);
      t = setStar(art, t, "book_of_ancient", 5);
      const state: FormState = { ...fresh(c), artifacts: t, equippedArtifacts: { "World Boss": normalizeSlots(["alliance_badge", "arwens_glass_shoes", "book_of_ancient", "pigs_ribbon"], art) } };
      expectClean(c.info.id, renderToString(<ArtifactsPanel schema={c.schema} classInfo={c.info} state={state} onState={noop} result={kase.result} busy={false} stale={false} onOpenCompanion={noop} onOpenInputs={noop} onOpenHelp={noop} />));
    }
    const x = NO_STAT_VALUES[0];
    expectClean("no stat values", renderToString(<ArtifactsPanel schema={x.schema} classInfo={x.info} state={fresh(x)} onState={noop} result={null} busy={false} stale={false} onOpenCompanion={noop} onOpenHelp={noop} />));
  });
  it("Stat values: full result, loading, error, unavailable", () => {
    const base = { result: sens.result, status: IDLE, meta: sens.meta, open: ["companions", "summon_time", "cdr"] as ("companions" | "summon_time" | "cdr")[], onOpenHelp: noop };
    expectClean("full", renderToString(<StatValuesView {...base} />));
    expectClean("loading", renderToString(<StatValuesView {...base} result={null} status={{ ...IDLE, loading: true }} />));
    expectClean("error", renderToString(<StatValuesView {...base} result={null} status={{ ...IDLE, error: "boom", fieldErrors: ["level: bad"] }} onRetry={noop} />));
    expectClean("unavailable", renderToString(<StatValuesView {...base} result={null} status={{ ...IDLE, unsupported: true }} />));
  });
  it("Equipment compare: editors, result, unavailable", () => {
    const state = { current: { attack: 1500, lines: [{ stat: "Damage %", value: 14 }, ...blankEquip().current.lines.slice(1)] }, new: blankEquip().new };
    const base = { meta: cubes.meta, metaStatus: IDLE_STATUS, state, onState: noop, status: IDLE_STATUS, onOpenHelp: noop };
    expectClean("result", renderToString(<EquipmentView {...base} result={cubes.equipment.result} />));
    expectClean("empty", renderToString(<EquipmentView {...base} result={null} />));
    expectClean("unavailable", renderToString(<EquipmentView {...base} result={null} status={{ ...IDLE_STATUS, unsupported: true }} />));
  });
  it("Cubes: the tab with the gear editor, and unavailable", () => {
    const props = { classId: "fp_mage", inputs: {}, active: true, meta: cubes.meta, metaStatus: IDLE_STATUS, state: undefined, onState: noop, onOpenHelp: noop };
    expectClean("editor", renderToString(<CubesPanel {...props} supported />));
    expectClean("unavailable", renderToString(<CubesPanel {...props} supported={false} meta={null} />));
  });
  it("Profiles: everything except the optional Excel import section; account texts", () => {
    const html = renderToString(<ProfilesPanel state={fresh()} classes={classList} onLoad={noop} />);
    const [before, rest] = html.split('<details class="advanced">');
    const after = rest.split('<details class="about-tab">')[1];
    expect(after, "the About block follows the Advanced area").toBeTruthy();
    expectClean("profiles", `${before} ${after}`);
    expectClean("account", renderToString(<HistoryDialog history={[]} onRestore={noop} onDiscard={noop} onClose={noop} />));
    for (const phase of ["loading", "saving", "error", "ready"] as const) expect(violations(syncStatusText({ phase, error: null, dirtyCount: 0, lastSyncAt: null, settingsDirty: false, migration: null })), phase).toEqual([]);
    expect(violations(Object.values(CLOUD_STATUS_TEXT).join(" . "))).toEqual([]);
  });
});

describe("the optional Excel import is the only place that may talk about the spreadsheet", () => {
  it("lives in the collapsed Advanced area at the bottom of Profiles, with the one-line explanation", () => {
    const html = renderToString(<ProfilesPanel state={fresh()} classes={classList} onLoad={noop} />);
    const adv = html.split('<details class="advanced">')[1].split('<details class="about-tab">')[0];
    expect(visibleText(adv)).toContain("Import from the old Excel calculator (optional)");
    expect(visibleText(adv)).toContain("For people who used the spreadsheet calculators from GitHub");
    expect(html).not.toMatch(/<details class="advanced"[^>]* open/);
    expect(visibleText(renderToString(<ImportXlsx classes={classList} onSaved={noop} />))).toMatch(/Excel/);
    expect(ImportDialog).toBeTypeOf("function");
  });
});
