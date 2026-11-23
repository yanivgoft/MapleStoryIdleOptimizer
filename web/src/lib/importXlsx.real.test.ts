// Sanity run against the real calculators of this repository (<Dir>/<Class>-DPS-Calculator.xlsx at the repo root; the suite finds them from the web/ folder).  Point it at
// another copy with
//
//   MSI_REAL_XLSX="/path/to/MapleStoryIdleOptimizer" npx vitest run src/lib/importXlsx.real.test.ts
//
// (that also prints what would be imported).  For every such file under the folder it opens the file with the browser-side reader, detects the class, imports it and prints what
// would be imported (counts, warnings, ignored cells).  Assertions: the class is detected, the import does not throw, and each content type's equipped artifacts equal the workbook's own Slot rows (read
// independently from the raw cells: name -> artifact, "(none)" blank, repeats counted once).
import { describe, expect, it } from "vitest";
import "../test/xlsxFiles";
import { fixtureFor } from "../test/fixtures";
import { XlsxBook } from "./xlsx_read";
import { XLSX_MAP, detectClass, importWorkbook } from "./importXlsx";
import { equippedKeys } from "./artifacts";

// @ts-ignore node:fs has no type declarations unless @types/node is installed (it arrives transitively with firebase)
const fs = (await import("node:fs")) as { readFileSync(p: string): Uint8Array; readdirSync(p: string): string[]; existsSync(p: string): boolean };
// @ts-ignore node:process has no type declarations unless @types/node is installed (it arrives transitively with firebase)
const env = ((await import("node:process")) as { env: Record<string, string | undefined> }).env;
const verbose = !!env.MSI_REAL_XLSX;
const root = env.MSI_REAL_XLSX ?? "..";            // vitest runs in web/: the repository root is one level up

const files: { dir: string; file: string }[] = [];
if (root && fs.existsSync(root)) {
  for (const dir of fs.readdirSync(root)) {
    const p = `${root}/${dir}`;
    let list: string[] = [];
    try {
      list = fs.readdirSync(p);
    } catch {
      continue;
    }
    for (const f of list) if (/-DPS-Calculator\.xlsx$/.test(f) && !f.startsWith("~$")) files.push({ dir, file: `${p}/${f}` });
  }
}

const perContentSets: Record<string, string[]> = {};   // file -> distinct artifact sets per content type (filled by the cases below)

describe.skipIf(!root)("real workbooks (sanity run)", () => {
  it.each(files.map((f) => [f.file.split("/").pop()!, f] as const))("%s", (_name, f) => {
    const book = XlsxBook.open(new Uint8Array(fs.readFileSync(f.file)), f.file);
    const { classId, title } = detectClass(book);
    expect(classId, `title ${title}`).not.toBeNull();
    expect(book.hasSheet("PotentialCubes"), "PotentialCubes sheet").toBe(true);
    const { schema } = fixtureFor(classId!);
    const r = importWorkbook(book, schema);
    const s = r.summary;
    expect(s.cubesRead).toBe(true);
    // the equipped artifacts of every content type = the Slot rows of that content type's column
    const cm = XLSX_MAP[classId!];
    const art = schema.artifacts!;
    const inputs = book.sheet("Inputs")!;
    const contentsWithSlots: string[] = [];
    schema.content_types.forEach((ct, i) => {
      const names = cm.inputs.slotRows.map((row) => String(inputs.at(row, cm.inputs.firstCol + i)?.value ?? "").trim()).filter((n) => n && n !== cm.inputs.noneLabel);
      const want = [...new Set(names.map((n) => art.artifacts.find((a) => a.name === n)?.key).filter((k): k is string => !!k))];
      expect(equippedKeys(art, r.state.equippedArtifacts![ct]).sort(), ct).toEqual(want.sort());
      expect(r.state.equippedArtifacts![ct]).toHaveLength(art.max_slots);
      if (want.length) contentsWithSlots.push(ct);
    });
    expect(Object.keys(s.loadouts).sort()).toEqual(contentsWithSlots.sort());
    perContentSets[f.file] = [...new Set(schema.content_types.map((ct) => equippedKeys(art, r.state.equippedArtifacts![ct]).join()).filter(Boolean))];
    if (verbose)
      console.log(
      `\n== ${f.file.split("/").pop()}  [${s.className}]  level ${s.level}  opens on ${s.contentType}\n` +
        `   values read per content type: ${Object.entries(s.valuesPerContent).map(([k, v]) => `${k} ${v}`).join(", ")}\n` +
        `   skipped content types: ${s.skippedContentTypes.join(", ") || "-"}\n` +
        `   equipped artifacts set for ${Object.keys(s.loadouts).length} of ${schema.content_types.length} content types: ${Object.entries(s.loadouts).map(([ct, l]) => `${ct}: ${l.join(", ")}`).join(" | ") || "-"}\n` +
        `   companions owned: ${s.companionLevels.map((c) => `${c.name} ${c.level}`).join(", ") || "-"}   chosen: ${[...new Set(Object.values(s.companionChoices))].join(", ")}\n` +
        `   cubes (PotentialCubes): ${s.cubesRead ? `${s.cubePieces} pieces with lines, ${s.cubeLines} lines, ${s.cubeRows} of 30 rows set` : "sheet not found"}\n` +
        `   cube warnings: ${r.warnings.filter((w) => /\/ (Potential|Bonus Potential)/.test(w.message)).map((w) => `${w.where}: ${w.message}`).join(" | ") || "-"}\n` +
        `   warnings (${r.warnings.length}): ${r.warnings.slice(0, 12).map((w) => `${w.where}: ${w.message}`).join(" | ")}\n` +
        `   ignored (${r.ignored.length}): ${r.ignored.slice(0, 6).map((w) => `${w.where}: ${w.message}`).join(" | ")}`,
    );
  });
  it("the repository's workbooks give per-content-type artifacts (not one global set)", () => {
    if (!files.length) return;
    expect(Object.values(perContentSets).some((sets) => sets.length > 1), "some workbook has different artifact sets in different content types").toBe(true);
  });
});
