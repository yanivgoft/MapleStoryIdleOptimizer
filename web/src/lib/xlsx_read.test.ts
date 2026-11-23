import { describe, expect, it } from "vitest";
import { makeZip, xlsxBytes } from "../test/xlsxFiles";
import { XlsxBook, XlsxError, colLetters, colNumber, parseRef } from "./xlsx_read";

const open = (name: string) => XlsxBook.open(xlsxBytes(name), name);
const code = (fn: () => unknown): string | undefined => {
  try {
    fn();
  } catch (e) {
    return e instanceof XlsxError ? e.code : `other:${(e as Error).message}`;
  }
  return undefined;
};

describe("A1 references", () => {
  it("round-trips column letters", () => {
    expect(colNumber("A")).toBe(1);
    expect(colNumber("L")).toBe(12);
    expect(colNumber("AA")).toBe(27);
    for (const n of [1, 12, 26, 27, 52, 703]) expect(colNumber(colLetters(n))).toBe(n);
  });
  it("parses references", () => {
    expect(parseRef("B3")).toEqual({ row: 3, col: 2 });
    expect(parseRef("$C$12")).toEqual({ row: 12, col: 3 });
    expect(parseRef("Inputs!B3")).toBeNull();
    expect(parseRef("")).toBeNull();
  });
});

describe("literal values", () => {
  const book = open("literal.xlsx");
  it("lists the sheets in workbook order", () => {
    expect(book.sheetNames).toEqual(["Data", "Second"]);
    expect(book.hasSheet("Second")).toBe(true);
    expect(book.sheet("Nope")).toBeNull();
  });
  it("reads strings, numbers and booleans", () => {
    const s = book.sheet("Data")!;
    expect(s.get("A1")?.value).toBe("label");
    expect(s.get("B1")?.value).toBe(42);
    expect(s.get("C1")?.value).toBe(3.5);
    expect(s.get("A2")?.value).toBe("28-9");
    expect(s.get("B2")?.value).toBe(true);
    expect(s.get("C2")?.value).toBe(false);
    expect(s.get("E5")?.value).toBe(-0.25);
    expect(s.get("B4")?.value).toBe(1e21);
    expect(s.get("AA10")?.value).toBe("far cell");
    expect(s.at(10, 27)?.value).toBe("far cell");
  });
  it("reads a shared string used twice, keeps spaces, leaves unset cells null", () => {
    const s = book.sheet("Data")!;
    expect(s.get("A3")?.value).toBe("dup");
    expect(s.get("B3")?.value).toBe("dup");
    expect(s.get("A4")?.value).toBe("  spaced  ");
    expect(s.get("Z99")).toBeNull();
    expect(s.value(99, 26)).toBeNull();
    expect(s.get("A1")?.formula).toBe(false);
  });
  it("reads the second sheet independently", () => {
    expect(book.sheet("Second")!.get("A1")?.value).toBe("second sheet");
  });
});

describe("rich text and escaping", () => {
  const s = open("rich_text.xlsx").sheet("Rich")!;
  it("concatenates rich-text runs", () => expect(s.get("A1")?.value).toBe("Hello bold world"));
  it("decodes XML entities and newlines", () => {
    expect(s.get("A2")?.value).toBe('plain & <escaped> "q"');
    expect(s.get("A3")?.value).toBe("line1\nline2");
  });
});

describe("formulas", () => {
  it("a workbook that was never opened in Excel has no cached values: formula cells read as empty, literals still read", () => {
    const s = open("formulas_no_cache.xlsx").sheet("F")!;
    expect(s.get("A1")?.value).toBe(21);
    expect(s.get("A2")?.value).toBe("literal next to formulas");
    for (const r of ["B1", "C1", "D1", "E1"]) {
      expect(s.get(r)?.formula).toBe(true);
      expect(s.get(r)?.value).toBeNull();
    }
  });
  it("cached results are used when the file has them (number, string, boolean) and errors are reported, not read as values", () => {
    const s = open("formulas_cached.xlsx").sheet("F")!;
    expect(s.get("B1")).toEqual({ value: 42, formula: true });
    expect(s.get("C1")).toEqual({ value: "big", formula: true });
    expect(s.get("D1")).toEqual({ value: true, formula: true });
    expect(s.get("E1")?.value).toBeNull();
    expect(s.get("E1")?.error).toBe("#DIV/0!");
    expect(s.get("A1")?.formula).toBe(false);
  });
});

describe("hand-written parts", () => {
  const s = open("inline.xlsx").sheet("Inline")!;
  it("reads inline strings, booleans and errors; absolute relationship targets", () => {
    expect(s.get("A1")?.value).toBe("inline text");
    expect(s.get("B1")?.value).toBe("rich inline");
    expect(s.get("C1")?.value).toBe(true);
    expect(s.get("D1")?.value).toBeNull();
    expect(s.get("D1")?.error).toBe("#N/A");
  });
  it("copes with rows and cells that have no r= attribute", () => {
    expect(s.get("A2")?.value).toBe("no refs");
    expect(s.get("B2")?.value).toBe(7);
    expect(s.get("C5")?.value).toBe(2.5);
    expect(s.get("E5")).toBeNull();
  });
});

describe("missing things", () => {
  it("a workbook without the expected sheets simply has no such sheet", () => {
    const b = open("missing_sheets.xlsx");
    expect(b.sheetNames).toEqual(["Something else"]);
    expect(b.sheet("Inputs")).toBeNull();
  });
});

describe("friendly errors", () => {
  it("rejects something that is not a zip", () => {
    expect(code(() => XlsxBook.open(new TextEncoder().encode("a,b,c\n1,2,3\n"), "data.csv"))).toBe("not_zip");
    expect(code(() => XlsxBook.open(new Uint8Array(0)))).toBe("not_zip");
  });
  it("recognises the old .xls / password-protected OLE container", () => {
    expect(code(() => XlsxBook.open(new Uint8Array([0xd0, 0xcf, 0x11, 0xe0, 0xa1, 0xb1, 0x1a, 0xe1, 0, 0])))).toBe("legacy_xls");
  });
  it("rejects a truncated xlsx as corrupt", () => {
    const good = xlsxBytes("literal.xlsx");
    expect(code(() => XlsxBook.open(good.slice(0, Math.floor(good.length / 2))))).toBe("corrupt");
    expect(code(() => XlsxBook.open(good.slice(0, good.length - 10)))).toBe("corrupt"); // end-of-central-directory record cut off
  });
  it("rejects a zip that is not a workbook", () => {
    expect(code(() => XlsxBook.open(makeZip({ "hello.txt": "hi" })))).toBe("not_xlsx");
  });
  it("rejects macro-enabled workbooks by name, by part and by content type", () => {
    const good = xlsxBytes("literal.xlsx");
    expect(code(() => XlsxBook.open(good, "Calc.xlsm"))).toBe("macro");
    expect(code(() => XlsxBook.open(makeZip({ "xl/vbaProject.bin": "x", "xl/workbook.xml": "<workbook/>", "xl/_rels/workbook.xml.rels": "<Relationships/>" })))).toBe("macro");
    expect(code(() => XlsxBook.open(makeZip({ "[Content_Types].xml": '<Types><Override ContentType="application/vnd.ms-excel.sheet.macroEnabled.main+xml"/></Types>' })))).toBe("macro");
  });
  it("rejects broken XML inside an otherwise valid zip", () => {
    const zip = makeZip({ "xl/workbook.xml": "<workbook><sheets>", "xl/_rels/workbook.xml.rels": "<Relationships></Relationships>" });
    expect(["corrupt", "not_xlsx"]).toContain(code(() => XlsxBook.open(zip)));
  });
  it("messages are human sentences", () => {
    try {
      XlsxBook.open(new TextEncoder().encode("hello world, not a workbook"));
    } catch (e) {
      expect((e as Error).message).toMatch(/not an Excel/);
    }
  });
});
