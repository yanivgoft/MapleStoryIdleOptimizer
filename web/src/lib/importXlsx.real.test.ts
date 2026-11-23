// Optional sanity run against YOUR OWN calculators (never part of the normal suite, nothing from them is committed):
//
//   MSI_REAL_XLSX="/path/to/MapleStoryIdleOptimizer" npx vitest run src/lib/importXlsx.real.test.ts
//
// For every <Dir>/<Class>-DPS-Calculator.xlsx under that folder it opens the file with the browser-side reader, detects the class, imports it and prints what
// would be imported (counts, warnings, ignored cells).  The only assertions: the class is detected and the import does not throw.
import { describe, expect, it } from "vitest";
import "../test/xlsxFiles";
import { fixtureFor } from "../test/fixtures";
import { XlsxBook } from "./xlsx_read";
import { detectClass, importWorkbook } from "./importXlsx";

// @ts-ignore node:fs has no type declarations unless @types/node is installed (it arrives transitively with firebase)
const fs = (await import("node:fs")) as { readFileSync(p: string): Uint8Array; readdirSync(p: string): string[]; existsSync(p: string): boolean };
// @ts-ignore node:process has no type declarations unless @types/node is installed (it arrives transitively with firebase)
const root = ((await import("node:process")) as { env: Record<string, string | undefined> }).env.MSI_REAL_XLSX;

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

describe.skipIf(!root)("real workbooks (opt-in sanity run)", () => {
  it.each(files.map((f) => [f.file.split("/").pop()!, f] as const))("%s", (_name, f) => {
    const book = XlsxBook.open(new Uint8Array(fs.readFileSync(f.file)), f.file);
    const { classId, title } = detectClass(book);
    expect(classId, `title ${title}`).not.toBeNull();
    expect(book.hasSheet("PotentialCubes"), "PotentialCubes sheet").toBe(true);
    const { schema } = fixtureFor(classId!);
    const r = importWorkbook(book, schema);
    const s = r.summary;
    expect(s.cubesRead).toBe(true);
    console.log(
      `\n== ${f.file.split("/").pop()}  [${s.className}]  level ${s.level}  opens on ${s.contentType}\n` +
        `   values read per content type: ${Object.entries(s.valuesPerContent).map(([k, v]) => `${k} ${v}`).join(", ")}\n` +
        `   skipped content types: ${s.skippedContentTypes.join(", ") || "-"}\n` +
        `   artifact loadout (${s.artifactsFrom ?? "none"}): ${s.slots.filter((x) => x.key !== "(none)").map((x) => `${x.key}@${x.star}`).join(", ") || "-"}\n` +
        `   companions owned: ${s.companionLevels.map((c) => `${c.name} ${c.level}`).join(", ") || "-"}   chosen: ${[...new Set(Object.values(s.companionChoices))].join(", ")}\n` +
        `   cubes (PotentialCubes): ${s.cubesRead ? `${s.cubePieces} pieces with lines, ${s.cubeLines} lines, ${s.cubeRows} of 30 rows set` : "sheet not found"}\n` +
        `   cube warnings: ${r.warnings.filter((w) => /\/ (Potential|Bonus Potential)/.test(w.message)).map((w) => `${w.where}: ${w.message}`).join(" | ") || "-"}\n` +
        `   warnings (${r.warnings.length}): ${r.warnings.slice(0, 12).map((w) => `${w.where}: ${w.message}`).join(" | ")}\n` +
        `   ignored (${r.ignored.length}): ${r.ignored.slice(0, 6).map((w) => `${w.where}: ${w.message}`).join(" | ")}`,
    );
  });
});
