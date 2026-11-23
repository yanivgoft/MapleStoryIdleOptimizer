import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { renderToString } from "react-dom/server";
import { xlsxBytes } from "../test/xlsxFiles";
import { classList, fixtureFor } from "../test/fixtures";
import { XlsxBook, XlsxError } from "../lib/xlsx_read";
import { groupNotes, importWorkbook, uniqueProfileName } from "../lib/importXlsx";
import { listProfiles, saveProfile } from "../lib/profiles";
import { ImportDialog, ImportXlsx, describeLoadError, filesOfDrop } from "./ImportXlsx";
import { ProfilesPanel } from "./ProfilesPanel";
import { initialState } from "../lib/schemaForm";

const strip = (h: string) => h.replace(/<!-- -->/g, "");
const lib = { groupNotes, uniqueProfileName };

// a tiny in-memory localStorage (the vitest environment is node)
function stubStorage() {
  const m = new Map<string, string>();
  (globalThis as unknown as { localStorage: unknown }).localStorage = {
    getItem: (k: string) => m.get(k) ?? null,
    setItem: (k: string, v: string) => void m.set(k, String(v)),
    removeItem: (k: string) => void m.delete(k),
  };
  return m;
}
const unstub = () => delete (globalThis as unknown as { localStorage?: unknown }).localStorage;

const schemaContents = (id: string) => fixtureFor(id).schema.content_types.length;
const importOf = (id: string) => importWorkbook(XlsxBook.open(xlsxBytes(`class_${id}.xlsx`)), fixtureFor(id).schema);
const dialog = (over: Partial<Parameters<typeof ImportDialog>[0]> = {}) => {
  const result = importOf("shadower");
  return strip(
    renderToString(
      <ImportDialog lib={lib} fileName="Shadower-DPS-Calculator.xlsx" fileTitle="Shadower — DPS Calculator Inputs" classes={classList} classId="shadower" detected result={result} problem={null} onClass={() => undefined} onCancel={() => undefined} onApply={() => undefined} {...over} />,
    ),
  );
};

describe("Profiles panel: import from Excel", () => {
  const html = strip(renderToString(<ProfilesPanel state={initialState(fixtureFor("shadower").schema, fixtureFor("shadower").defaults["Chapter Boss"])} classes={classList} onLoad={() => undefined} />));
  it("offers the .xlsx import next to the JSON import, with the privacy promise", () => {
    expect(html).toContain("Import from Excel (.xlsx)");
    expect(html).toContain("Import file"); // the existing JSON import is untouched
    expect(html).toMatch(/accept="\.xlsx,application\/vnd\.openxmlformats-officedocument\.spreadsheetml\.sheet"/);
    expect(html).toMatch(/never uploaded/);
    expect(html).toContain("or drop the .xlsx file here");
  });
  it("the file input is labelled and described for assistive technology", () => {
    expect(html).toMatch(/<label[^>]*for="import-xlsx-file"/);
    expect(html).toMatch(/id="import-xlsx-file"[^>]*aria-describedby=/);
    expect(strip(renderToString(<ImportXlsx classes={classList} onSaved={() => undefined} />))).toContain('aria-labelledby=');
  });
});

describe("preview dialog", () => {
  beforeEach(() => void stubStorage());
  afterEach(unstub);
  it("is a labelled modal dialog with Apply and Cancel", () => {
    const h = dialog();
    expect(h).toContain('role="dialog"');
    expect(h).toContain('aria-modal="true"');
    expect(h).toMatch(/aria-labelledby="[^"]+-t"/);
    expect(h).toContain("Import as new profile");
    expect(h).toContain("Cancel");
    expect(h).toContain("Shadower-DPS-Calculator.xlsx");
    expect(h).toContain("the file stays on your device");
  });
  it("lists what will be imported", () => {
    const r = importOf("shadower");
    const h = dialog();
    expect(h).toContain("Recognised from the workbook title");
    expect(h).toContain("Character level");
    expect(h).toContain(String(r.state.shared.level));
    expect(h).toContain(`Opens on</dt><dd>${r.state.contentType}`);
    expect(h).toContain("Values read per content type");
    expect(h).toContain(`Warnings (${r.warnings.length})`);
    expect(h).toContain(`Ignored (${r.ignored.length})`);
    expect(h).toContain("Wind Archer Lv 3");
    expect(h).toContain(`equipped artifacts set for ${Object.keys(r.summary.loadouts).length} of ${schemaContents("shadower")} content types`); // one set per content type, like the workbook
    expect(h).not.toContain("Artifact loadout of");               // (the old "choose one loadout" selector is gone)
    expect(h).toContain("New profile name");
    expect(h).toContain("Shadower (Excel import)");
  });
  it("shows the cube gear counts: pieces with lines, lines and gear rows set", () => {
    const r = importOf("shadower");
    const h = dialog();
    expect(r.summary.cubePieces).toBeGreaterThan(0);
    expect(h).toContain("<dt>Cubes</dt>");
    expect(h).toContain(`${r.summary.cubePieces} pieces with lines`);
    expect(h).toContain(`${r.summary.cubeLines} lines; ${r.summary.cubeRows} of 30 gear rows set`);
    expect(h).toContain("read from PotentialCubes");
    expect(h).not.toContain("Equipment compare");                   // Equipment Compare is not imported
    expect(h).toContain("cannot roll on this slot");                // the planted cube warnings are grouped with the others
    expect(h).toContain("appears twice");
    const fp = dialog({ classId: "fp_mage", result: importOf("fp_mage") });   // FP-Mage has the Cubes tab: no such note
    expect(fp).toContain("<dt>Cubes</dt>");
    expect(fp).not.toContain("Cubes tab is not available");
  });
  it("says so when the class has no Cubes tab yet (the gear is still kept in the profile)", () => {
    const id = classList.find((c) => c.status?.stat_values === false)!.id;
    const r = importOf(id);
    const h = dialog({ classId: id, result: r });
    expect(r.state.cubes && Object.keys(r.state.cubes).length).toBeGreaterThan(0);
    expect(h).toContain("the Cubes tab is not available for this class yet");
  });
  it("a workbook without the PotentialCubes sheet says so", () => {
    const r = importWorkbook(XlsxBook.open(xlsxBytes("inputs_only_shadower.xlsx")), fixtureFor("shadower").schema);
    const h = dialog({ result: r });
    expect(h).toContain("no PotentialCubes sheet in the file");
  });
  it("planted warnings are shown, grouped, with their cells", () => {
    const h = dialog();
    expect(h).toContain("outside the allowed range");
    expect(h).toContain("not unlocked");
    expect(h).toMatch(/\(C\d+/); // cell references of the finding
  });
  it("warns when the suggested name is taken and says nothing is overwritten", () => {
    const { schema, defaults } = fixtureFor("shadower");
    saveProfile("Shadower (Excel import)", initialState(schema, defaults["Chapter Boss"]));
    const h = dialog();
    expect(h).toContain('already exists; it will be saved as &quot;Shadower (Excel import) (2)&quot;');
  });
  it("an unrecognised workbook asks for the class and cannot be applied yet", () => {
    const h = dialog({ classId: null, detected: false, result: null, fileTitle: "Something — else" });
    expect(h).toContain("Choose the class...");
    expect(h).toMatch(/is not one of the calculators/);
    expect(h).toMatch(/<button type="submit" disabled=""/);
  });
  it("shows a problem (schema could not be loaded) as an alert", () => {
    const h = dialog({ result: null, problem: "Could not load the class definition" });
    expect(h).toContain('role="alert"');
    expect(h).toContain("Could not load the class definition");
  });
});

describe("applying creates a new profile and never overwrites", () => {
  beforeEach(() => void stubStorage());
  afterEach(unstub);
  it("saves the imported state under a unique name, readable as a normal profile", () => {
    const r = importOf("fp_mage");
    const first = saveProfile(uniqueProfileName("FP (Excel import)", listProfiles(), "fp_mage"), r.state);
    const second = saveProfile(uniqueProfileName("FP (Excel import)", listProfiles(), "fp_mage"), r.state);
    expect(first.name).toBe("FP (Excel import)");
    expect(second.name).toBe("FP (Excel import) (2)");
    expect(listProfiles().map((p) => p.name)).toEqual(["FP (Excel import)", "FP (Excel import) (2)"]);
    const back = listProfiles()[0];
    expect(back.state.classId).toBe("fp_mage");
    expect(back.state.artifacts).toEqual(r.state.artifacts);
    expect(back.state.companions!.levels).toEqual(r.state.companions!.levels);
    expect(back.state.perContent).toEqual(r.state.perContent);
    expect(back.state.cubes).toEqual(r.state.cubes);                  // the same `cubes` key the Cubes tab saves
    expect(Object.keys(back.state.cubes!).length).toBeGreaterThan(0);
  });
});

describe("friendly errors", () => {
  const xe = (code: ConstructorParameters<typeof XlsxError>[0], message: string) => new XlsxError(code, message);
  it("explains what to do for each kind of unusable file", () => {
    expect(describeLoadError(xe("not_zip", "This is not an Excel .xlsx workbook"))).toMatch(/Import file/);
    expect(describeLoadError(xe("macro", "Macro-enabled workbooks (.xlsm) are not supported. Save As .xlsx"))).toMatch(/\.xlsx/);
    expect(describeLoadError(xe("corrupt", "The file looks corrupted"))).toMatch(/corrupted/);
    expect(describeLoadError(Object.assign(new Error("HTTP 503"), { name: "ApiError", status: 503 }))).toMatch(/not uploaded/);
    expect(describeLoadError(new Error("boom"))).toMatch(/could not be read: boom/);
  });
  it("end to end: real error cases from the reader give readable messages", () => {
    const msgs = [new Uint8Array(0), new TextEncoder().encode("PK"), new Uint8Array([0xd0, 0xcf, 0x11, 0xe0, 0, 0, 0, 0])].map((b) => {
      try {
        XlsxBook.open(b, "x.xlsx");
      } catch (e) {
        return describeLoadError(e);
      }
      return "";
    });
    for (const m of msgs) expect(m.length).toBeGreaterThan(20);
    expect(msgs[2]).toMatch(/password|\.xls/);
  });
  it("drop events: first file wins, empty drops are harmless", () => {
    const f = (n: string) => new File(["x"], n);
    expect(filesOfDrop({ files: [f("a.xlsx"), f("b.xlsx")] }).map((x) => x.name)).toEqual(["a.xlsx", "b.xlsx"]);
    expect(filesOfDrop(null)).toEqual([]);
    expect(filesOfDrop({})).toEqual([]);
  });
});
