// A small, dependency-light .xlsx reader (pure TypeScript; runs entirely in the browser - the file is never uploaded).
//
// An .xlsx is a zip of XML parts.  We unzip with `fflate`, then parse `xl/workbook.xml` (sheet names), `xl/_rels/workbook.xml.rels` (sheet -> part),
// `xl/sharedStrings.xml` and the worksheets that are asked for, with the browser's `DOMParser`.  Only LITERAL values are read: strings (shared / inline /
// formula-result), numbers and booleans.  A formula cell yields its cached `<v>` value when the file has one (a workbook that was never opened in Excel has
// none: the cell then reads as empty with `formula: true`).  Styles, dates, merged cells, charts and macros are ignored on purpose.
//
// Deliberately NOT SheetJS (`xlsx` on npm: unmaintained, known vulnerabilities).
import { unzipSync } from "fflate";

export type CellValue = string | number | boolean | null;

export interface Cell {
  value: CellValue; // null = no usable value (blank, error, formula without a cached result)
  formula: boolean; // the cell holds a formula (value is its cached result, when the file had one)
  error?: string; // an Excel error value such as "#N/A" (value is null then)
}

export type XlsxErrorCode = "not_zip" | "legacy_xls" | "not_xlsx" | "macro" | "encrypted" | "corrupt" | "too_big" | "missing_part" | "no_layout";

export class XlsxError extends Error {
  code: XlsxErrorCode;
  constructor(code: XlsxErrorCode, message: string) {
    super(message);
    this.name = "XlsxError";
    this.code = code;
  }
}

/** Hard limits: a calculator workbook is well under 2 MB; anything wildly bigger is not what we expect (and a zip bomb must not eat the tab's memory). */
export const MAX_FILE_BYTES = 40 * 1024 * 1024;
export const MAX_PART_BYTES = 64 * 1024 * 1024; // declared uncompressed size of one XML part
const MAX_ROW = 5000;
const MAX_COL = 200;

export const colNumber = (letters: string): number => [...letters.toUpperCase()].reduce((n, ch) => n * 26 + (ch.charCodeAt(0) - 64), 0);

export function colLetters(n: number): string {
  let s = "";
  while (n > 0) {
    const r = (n - 1) % 26;
    s = String.fromCharCode(65 + r) + s;
    n = Math.floor((n - 1) / 26);
  }
  return s;
}

/** "B3" -> {row: 3, col: 2}; null when it is not an A1 reference. */
export function parseRef(ref: string): { row: number; col: number } | null {
  const m = /^\$?([A-Za-z]{1,3})\$?(\d{1,7})$/.exec(ref.trim());
  return m ? { row: Number(m[2]), col: colNumber(m[1]) } : null;
}

// ---- XML helpers (work with the browser's DOM and with xmldom, which the tests use) ---------------------------------------------------------------
type El = Element;

function parseXml(bytes: Uint8Array, part: string): Document {
  if (typeof DOMParser === "undefined") throw new XlsxError("corrupt", "This browser cannot read XML (no DOMParser).");
  const text = new TextDecoder("utf-8").decode(bytes).replace(/^﻿/, "");
  let doc: Document;
  try {
    doc = new DOMParser().parseFromString(text, "application/xml");
  } catch {
    throw new XlsxError("corrupt", `The workbook part ${part} is not valid XML.`);
  }
  if (!doc || !doc.documentElement || doc.getElementsByTagName("parsererror").length > 0) {
    throw new XlsxError("corrupt", `The workbook part ${part} is not valid XML.`);
  }
  return doc;
}

const local = (n: Node): string => ((n as Element).localName ?? n.nodeName.replace(/^.*:/, "")) as string;

function kids(el: El, name: string): El[] {
  const out: El[] = [];
  for (let n = el.firstChild; n; n = n.nextSibling) if (n.nodeType === 1 && local(n) === name) out.push(n as El);
  return out;
}

function descendants(el: El, name: string): El[] {
  const out: El[] = [];
  const walk = (e: El) => {
    for (let n = e.firstChild; n; n = n.nextSibling) {
      if (n.nodeType !== 1) continue;
      if (local(n) === name) out.push(n as El);
      walk(n as El);
    }
  };
  walk(el);
  return out;
}

function attr(el: El, name: string): string | null {
  const direct = el.getAttribute(name);
  if (direct !== null && direct !== "") return direct;
  const attrs = el.attributes;
  for (let i = 0; i < attrs.length; i++) {
    const a = attrs[i];
    if ((a.localName ?? a.name.replace(/^.*:/, "")) === name) return a.value;
  }
  return direct;
}

/** Concatenated text of an <si>/<is> element: plain <t> and rich-text <r><t> runs, never phonetic <rPh> runs. */
function richText(el: El): string {
  let s = "";
  for (let n = el.firstChild; n; n = n.nextSibling) {
    if (n.nodeType !== 1) continue;
    const name = local(n);
    if (name === "t") s += n.textContent ?? "";
    else if (name === "r") for (const t of kids(n as El, "t")) s += t.textContent ?? "";
  }
  return s;
}

// ---- the book ------------------------------------------------------------------------------------------------------------------------------------
export class XlsxSheet {
  readonly name: string;
  private cells = new Map<number, Cell>(); // row * 1000 + col
  private _maxRow = 0;
  constructor(name: string) {
    this.name = name;
  }
  /** @internal */
  put(row: number, col: number, cell: Cell) {
    this.cells.set(row * 1000 + col, cell);
    if (row > this._maxRow) this._maxRow = row;
  }
  /** The last row that holds a cell (0 for an empty sheet). */
  get maxRow(): number {
    return this._maxRow;
  }
  at(row: number, col: number): Cell | null {
    return this.cells.get(row * 1000 + col) ?? null;
  }
  /** Cell by A1 reference ("B3"). */
  get(ref: string): Cell | null {
    const p = parseRef(ref);
    return p ? this.at(p.row, p.col) : null;
  }
  /** Cell value by (row, col), or null. */
  value(row: number, col: number): CellValue {
    return this.at(row, col)?.value ?? null;
  }
  get size(): number {
    return this.cells.size;
  }
}

export class XlsxBook {
  readonly sheetNames: string[];
  private parts: Record<string, Uint8Array>;
  private bytes: Uint8Array;
  private sheetPart = new Map<string, string>();
  private strings: string[] | null = null;
  private cache = new Map<string, XlsxSheet>();

  private constructor(bytes: Uint8Array, parts: Record<string, Uint8Array>, names: string[], map: Map<string, string>) {
    this.bytes = bytes;
    this.parts = parts;
    this.sheetNames = names;
    this.sheetPart = map;
  }

  /** Open an .xlsx from its bytes.  Throws XlsxError with a friendly message for anything that is not a usable workbook. */
  static open(input: ArrayBuffer | Uint8Array, fileName = ""): XlsxBook {
    const bytes = input instanceof Uint8Array ? input : new Uint8Array(input);
    if (bytes.length > MAX_FILE_BYTES) throw new XlsxError("too_big", "This file is much larger than a calculator workbook (over 40 MB).");
    // OLE2 container: the old binary .xls format, or an Excel file protected with a password (encrypted .xlsx is wrapped in OLE2 too)
    if (bytes.length >= 8 && bytes[0] === 0xd0 && bytes[1] === 0xcf && bytes[2] === 0x11 && bytes[3] === 0xe0) {
      throw new XlsxError("legacy_xls", "This is an old-style .xls file or a password-protected workbook. Remove the password / use File > Save As > Excel Workbook (.xlsx) and try again.");
    }
    if (bytes.length < 4 || bytes[0] !== 0x50 || bytes[1] !== 0x4b) {
      throw new XlsxError("not_zip", "This is not an Excel .xlsx workbook (it is not a zip archive). Pick the <Class>-DPS-Calculator.xlsx file.");
    }
    const lowerName = fileName.toLowerCase();
    if (lowerName.endsWith(".xlsm") || lowerName.endsWith(".xlsb")) {
      throw new XlsxError("macro", "Macro-enabled / binary workbooks (.xlsm, .xlsb) are not supported. Open it in Excel and use Save As > Excel Workbook (.xlsx).");
    }
    const unzip = (want: (name: string) => boolean): Record<string, Uint8Array> => {
      try {
        return unzipSync(bytes, { filter: (f) => want(f.name) && f.originalSize <= MAX_PART_BYTES });
      } catch {
        throw new XlsxError("corrupt", "The file looks corrupted: the zip archive cannot be read. Re-download it or re-save it from Excel.");
      }
    };
    const meta = unzip((n) => n === "[Content_Types].xml" || n === "xl/workbook.xml" || n === "xl/_rels/workbook.xml.rels" || n === "xl/sharedStrings.xml" || n === "xl/vbaProject.bin" || n === "xl/workbook.bin" || n === "EncryptionInfo");
    if (meta["xl/vbaProject.bin"]) {
      throw new XlsxError("macro", "Macro-enabled workbooks (.xlsm) are not supported. Open it in Excel and use Save As > Excel Workbook (.xlsx).");
    }
    if (meta["xl/workbook.bin"]) throw new XlsxError("macro", "Binary workbooks (.xlsb) are not supported. Open it in Excel and use Save As > Excel Workbook (.xlsx).");
    if (meta["EncryptionInfo"]) throw new XlsxError("encrypted", "This workbook is password-protected. Remove the password in Excel and try again.");
    if (meta["[Content_Types].xml"]) {
      const ct = new TextDecoder().decode(meta["[Content_Types].xml"]);
      if (/macroEnabled/i.test(ct)) throw new XlsxError("macro", "Macro-enabled workbooks (.xlsm) are not supported. Open it in Excel and use Save As > Excel Workbook (.xlsx).");
    }
    const wbXml = meta["xl/workbook.xml"];
    const relXml = meta["xl/_rels/workbook.xml.rels"];
    if (!wbXml || !relXml) throw new XlsxError("not_xlsx", "This zip archive is not an Excel workbook (no xl/workbook.xml). Pick the <Class>-DPS-Calculator.xlsx file.");

    const rels = new Map<string, string>();
    for (const r of descendants(parseXml(relXml, "xl/_rels/workbook.xml.rels").documentElement, "Relationship")) {
      const id = r.getAttribute("Id");
      const target = r.getAttribute("Target");
      if (id && target) rels.set(id, target);
    }
    const names: string[] = [];
    const map = new Map<string, string>();
    for (const s of descendants(parseXml(wbXml, "xl/workbook.xml").documentElement, "sheet")) {
      const name = s.getAttribute("name");
      const rid = attr(s, "id");
      const target = rid ? rels.get(rid) : undefined;
      if (!name || !target) continue;
      const path = target.startsWith("/") ? target.slice(1) : `xl/${target.replace(/^\.\//, "")}`;
      names.push(name);
      map.set(name, path);
    }
    if (!names.length) throw new XlsxError("not_xlsx", "This workbook has no worksheets.");
    return new XlsxBook(bytes, meta, names, map);
  }

  hasSheet(name: string): boolean {
    return this.sheetPart.has(name);
  }

  private sharedStrings(): string[] {
    if (this.strings) return this.strings;
    const raw = this.parts["xl/sharedStrings.xml"];
    const out: string[] = [];
    if (raw) {
      const root = parseXml(raw, "xl/sharedStrings.xml").documentElement;
      for (const si of kids(root, "si")) out.push(richText(si));
    }
    return (this.strings = out);
  }

  /** The worksheet called ``name`` (parsed on first use), or null when the workbook has no such sheet. */
  sheet(name: string): XlsxSheet | null {
    const cached = this.cache.get(name);
    if (cached) return cached;
    const path = this.sheetPart.get(name);
    if (!path) return null;
    let raw = this.parts[path];
    if (!raw) {
      let got: Record<string, Uint8Array>;
      try {
        got = unzipSync(this.bytes, { filter: (f) => f.name === path && f.originalSize <= MAX_PART_BYTES });
      } catch {
        throw new XlsxError("corrupt", "The file looks corrupted: the zip archive cannot be read. Re-download it or re-save it from Excel.");
      }
      raw = got[path];
      if (!raw) throw new XlsxError("missing_part", `The sheet "${name}" is listed in the workbook but its data is missing.`);
      this.parts[path] = raw;
    }
    const sheet = new XlsxSheet(name);
    const root = parseXml(raw, path).documentElement;
    const shared = this.sharedStrings();
    for (const data of kids(root, "sheetData")) {
      let rowNo = 0;
      for (const row of kids(data, "row")) {
        const rAttr = Number(row.getAttribute("r"));
        rowNo = Number.isFinite(rAttr) && rAttr > 0 ? rAttr : rowNo + 1;
        let colNo = 0;
        for (const c of kids(row, "c")) {
          const ref = c.getAttribute("r");
          const p = ref ? parseRef(ref) : null;
          colNo = p ? p.col : colNo + 1;
          const r = p ? p.row : rowNo;
          if (r > MAX_ROW || colNo > MAX_COL) continue;
          const cell = readCell(c, shared);
          if (cell) sheet.put(r, colNo, cell);
        }
      }
    }
    this.cache.set(name, sheet);
    return sheet;
  }
}

function readCell(c: El, shared: string[]): Cell | null {
  const t = c.getAttribute("t") ?? "n";
  const f = kids(c, "f").length > 0;
  const v = kids(c, "v")[0]?.textContent ?? null;
  let value: CellValue = null;
  let error: string | undefined;
  switch (t) {
    case "s": {
      const i = v === null ? NaN : Number(v);
      value = Number.isInteger(i) && i >= 0 && i < shared.length ? shared[i] : null;
      break;
    }
    case "str":
    case "d":
      value = v;
      break;
    case "inlineStr": {
      const is = kids(c, "is")[0];
      value = is ? richText(is) : null;
      break;
    }
    case "b":
      value = v === null ? null : v.trim() === "1" || v.trim().toLowerCase() === "true";
      break;
    case "e":
      error = v ?? "#ERROR";
      break;
    default: {
      if (v !== null && v.trim() !== "") {
        const n = Number(v);
        value = Number.isFinite(n) ? n : null;
      }
    }
  }
  if (value === null && !f && error === undefined) return null;
  const cell: Cell = { value, formula: f };
  if (error !== undefined) cell.error = error;
  return cell;
}
