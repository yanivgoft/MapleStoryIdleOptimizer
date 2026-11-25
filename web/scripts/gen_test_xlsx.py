#!/usr/bin/env python3
"""Generate the small .xlsx files the vitest suites read (web/src/test/xlsx/).  Run from the repository root with the system python3 (openpyxl only):

    python3 web/scripts/gen_test_xlsx.py

Reader cases (lib/xlsx_read.test.ts):  literal.xlsx, rich_text.xlsx, formulas_no_cache.xlsx, formulas_cached.xlsx (cached <v> patched in), inline.xlsx (hand-written
inline strings / booleans / errors), missing_sheets.xlsx.
Mapping cases (lib/importXlsx.test.ts): class_<id>.xlsx for every class = sample values written at the coordinates of web/src/lib/xlsx_map.json (Inputs,
ArtifactsInput, CompanionsInput and the PotentialCubes gear table with planted problems; Equipment Compare is not imported), plus
class_<id>.expected.json, the FormState values computed here independently (defaults for blank cells, null for non-applicable ones, ...).
No real workbook data is used.  The files are deterministic.
"""
import json
import re
import sys
import zipfile
from pathlib import Path

import openpyxl
from openpyxl.cell.rich_text import CellRichText, TextBlock
from openpyxl.cell.text import InlineFont

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / "web" / "src" / "fixtures"
OUT = ROOT / "web" / "src" / "test" / "xlsx"
_MAPFILE = json.loads((ROOT / "web" / "src" / "lib" / "xlsx_map.json").read_text(encoding="utf-8"))
MAP = _MAPFILE["classes"]
CUBE_TABLES = _MAPFILE["cubeTables"]
OUT.mkdir(parents=True, exist_ok=True)
FIXED_PROPS = None


def save(wb, name):
    wb.properties.creator = "msi-tests"
    from datetime import datetime
    wb.properties.created = wb.properties.modified = datetime(2026, 1, 1)
    wb.save(OUT / name)


# ---------------------------------------------------------------- reader cases
def reader_cases():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Data"
    ws["A1"], ws["B1"], ws["C1"] = "label", 42, 3.5
    ws["A2"], ws["B2"], ws["C2"] = "28-9", True, False
    ws["A3"], ws["B3"] = "dup", "dup"          # the same string twice: one shared-string entry
    ws["E5"] = -0.25
    ws["AA10"] = "far cell"
    ws["A4"] = "  spaced  "
    ws["B4"] = 1e21
    wb.create_sheet("Second")["A1"] = "second sheet"
    save(wb, "literal.xlsx")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Rich"
    ws["A1"] = CellRichText("Hello ", TextBlock(InlineFont(b=True), "bold"), " world")
    ws["A2"] = "plain & <escaped> \"q\""
    ws["A3"] = "line1\nline2"
    save(wb, "rich_text.xlsx")

    for name, cached in (("formulas_no_cache.xlsx", False), ("formulas_cached.xlsx", True)):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "F"
        ws["A1"] = 21
        ws["B1"] = "=A1*2"
        ws["C1"] = '=IF(A1>5,"big","small")'
        ws["D1"] = "=A1>5"
        ws["E1"] = "=1/0"
        ws["A2"] = "literal next to formulas"
        save(wb, name)
        if cached:
            patch_cached(OUT / name, {"B1": ("n", "42"), "C1": ("str", "big"), "D1": ("b", "1"), "E1": ("e", "#DIV/0!")})

    # hand-written part: inline strings, booleans, an error value, a cell without r=, a row without r=
    write_inline(OUT / "inline.xlsx")

    wb = openpyxl.Workbook()
    wb.active.title = "Something else"
    wb.active["A1"] = "nothing useful"
    save(wb, "missing_sheets.xlsx")


def patch_cached(path, cells):
    """openpyxl writes `<c r="B1"><f>..</f><v></v></c>`: rewrite those cells with cached results the way Excel stores them."""
    zin = zipfile.ZipFile(path)
    items = {n: zin.read(n) for n in zin.namelist()}
    zin.close()
    sheet = "xl/worksheets/sheet1.xml"
    xml = items[sheet].decode("utf-8")
    for ref, (t, v) in cells.items():
        pat = re.compile(r'<c r="%s"([^>]*)>(<f>.*?</f>)<v\s*/?>(?:</v>)?</c>' % ref, re.S)
        attrs_re = lambda m: '<c r="%s"%s t="%s">%s<v>%s</v></c>' % (ref, re.sub(r'\st="[^"]*"', "", m.group(1)), t, m.group(2), v)
        xml, n = pat.subn(attrs_re, xml)
        assert n == 1, (ref, xml[:500])
    items[sheet] = xml.encode("utf-8")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zout:
        for n, b in items.items():
            zout.writestr(zipfile.ZipInfo(n, (2026, 1, 1, 0, 0, 0)), b)


def write_inline(path):
    ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
          '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
          '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
    wbx = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
           'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Inline" sheetId="1" r:id="rId1"/></sheets></workbook>')
    wbrels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
              '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="/xl/worksheets/sheet1.xml"/></Relationships>')
    sheet = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
             '<row r="1"><c r="A1" t="inlineStr"><is><t>inline text</t></is></c><c r="B1" t="inlineStr"><is><r><t>rich </t></r><r><t>inline</t></r></is></c>'
             '<c r="C1" t="b"><v>1</v></c><c r="D1" t="e"><v>#N/A</v></c></row>'
             '<row><c t="inlineStr"><is><t>no refs</t></is></c><c><v>7</v></c></row>'
             '<row r="5"><c r="C5"><v>2.5</v></c><c r="E5" t="n"/></row>'
             '</sheetData></worksheet>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for n, b in (("[Content_Types].xml", ct), ("_rels/.rels", rels), ("xl/workbook.xml", wbx), ("xl/_rels/workbook.xml.rels", wbrels), ("xl/worksheets/sheet1.xml", sheet)):
            z.writestr(zipfile.ZipInfo(n, (2026, 1, 1, 0, 0, 0)), b)


# ---------------------------------------------------------------- per-class mapping cases
def sample_value(f, i, j):
    """Deterministic in-range sample for field f in content-type column i (field index j)."""
    lo, hi = f.get("min"), f.get("max")
    if f["type"] == "int":
        v = (j + i) % 9 + 1
        if lo is not None:
            v = max(v, int(lo))
        if hi is not None:
            v = min(v, int(hi))
        return v
    if f["type"] == "float":
        v = round(5 + j * 2 + i * 0.5, 1)
        if lo is not None:
            v = max(v, lo)
        if hi is not None:
            v = min(v, hi)
        return v
    if f["type"] == "enum":
        return f["options"][(i + j) % len(f["options"])]
    # text: chapter-stage
    return ["29-3", "85", "31", "90", "12", "7", "99", "41", "28", "55"][i % 10] if i % 2 else ["28-9", "30", "70", "33", "100", "2", "5", "6", "8", "9"][i % 10]


def class_case(cid):
    cm = MAP[cid]
    schema = json.loads((FIX / f"{cid}.schema.json").read_text())
    fields = {f["key"]: f for f in schema["fields"]}
    cts = schema["content_types"]
    inp = cm["inputs"]
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Inputs"
    ws["A1"] = cm["title"]
    for i, ct in enumerate(cts):
        ws.cell(row=inp["headerRow"], column=inp["firstCol"] + i, value=ct)
    ws[inp["level"]] = 123
    selected = cts[2]
    ws[inp["contentType"]] = selected
    owned = {"Hero": 7, "Dark Knight": 18, "Wind Archer": "3"}       # numeric, numeric at the max, numeric string
    expected = {"level": 123, "contentType": selected, "perContent": {}, "warnings": 0, "ignoredHints": []}
    blank_cell = ("attack_pct", 1)                                    # a blank applicable cell -> the default
    bad_cell = ("crit_rate", 3)                                       # a number out of range -> kept + warning
    stray = ("pvp_fight_length", 0)                                   # a value in a non-applicable cell -> null + ignored
    expected_warnings = 0
    for i, ct in enumerate(cts):
        vals = {}
        for j, (key, row) in enumerate(sorted(inp["perContent"].items(), key=lambda kv: kv[1])):
            f = fields[key]
            app = f["applicable"] is None or ct in f["applicable"]
            col = inp["firstCol"] + i
            if not app:
                vals[key] = None
                if (key, i) == stray:
                    ws.cell(row=row, column=col, value=15)
                    expected["ignoredHints"].append(f"does not apply to {ct}")
                continue
            default = (f["default_by_content"] or {}).get(ct) if f["default_by_content"] else f["default"]
            if key == "companion_choice":
                choice = "Hero" if i % 2 == 0 else "Bishop"          # Bishop is not owned -> None (+ a warning)
                ws.cell(row=row, column=col, value=choice)
                vals[key] = "Hero" if choice == "Hero" else "None"
                if choice != "Hero":
                    expected_warnings += 1
                continue
            if (key, i) == blank_cell:
                vals[key] = default
                continue
            if (key, i) == bad_cell:
                v = (f["max"] or 0) + 1
                ws.cell(row=row, column=col, value=v)
                vals[key] = v
                expected_warnings += 1
                continue
            v = sample_value(f, i, j)
            ws.cell(row=row, column=col, value=v)
            vals[key] = v
        expected["perContent"][ct] = vals
    # ArtifactsInput: the Star Level of EVERY artifact + planted potential lines (rarity / stat in C-D, F-G, I-J) + the slot rows (a different loadout per content type;
    # one unknown name + one repeat -> ignored).  `expected["artifacts"]` is what the app's table must hold after the import of the selected content type.
    art_keys = list(cm["artifacts"]["rows"])
    stars_cycle = ["Not Unlocked", 0, 1, 2, 3, 4, 5]
    rarities = ["Rare", "Epic", "Unique", "Legendary", "Mystic", "Mystic (Prime)"]
    stats = ["Main Stat %", "Damage Taken Decrease %", "Defense %", "Accuracy", "Critical Rate %", "Min Damage Multiplier %", "Max Damage Multiplier %",
             "Boss Monster Damage %", "Normal Monster Damage %", "Status Effect Damage %", "Damage %", "Defense Penetration %"]
    legendary = {a["key"] for a in schema["artifacts"]["artifacts"] if a["rank"] == "Legendary"}
    lc = cm["artifacts"]["lineCols"]
    wa = wb.create_sheet("ArtifactsInput")
    wa["A4"], wa["B4"] = "Artifact", "Star Level"
    stars, lines = {}, {}
    for n, k in enumerate(art_keys):
        r = cm["artifacts"]["rows"][k]
        stars[k] = stars_cycle[n % len(stars_cycle)]
        wa.cell(row=r["row"], column=1, value=r["name"])
        wa.cell(row=r["row"], column=cm["artifacts"]["starCol"], value=stars[k])
        nl = 3 if k in legendary else 2
        got = [["Rare", "(none)"] for _ in range(3)]
        for i in range(nl):
            if (n + i) % 3 != 0:                      # every 3rd (artifact, line) is left as the builder writes it: Rare / (none)
                rar, st = rarities[(n + i) % 6], stats[(n * 2 + i) % len(stats)]
                if n == 1 and i == 0:                 # planted: an unknown stat -> warning, the line stays empty
                    wa.cell(row=r["row"], column=lc[i][0], value=rar)
                    wa.cell(row=r["row"], column=lc[i][1], value="Bogus Stat %")
                    expected_warnings += 1
                    continue
                if n == 2 and i == 0:                 # planted: an unknown rarity next to a valid stat -> warning, Rare
                    wa.cell(row=r["row"], column=lc[i][0], value="Godlike")
                    wa.cell(row=r["row"], column=lc[i][1], value=st)
                    got[i] = ["Rare", st]
                    expected_warnings += 1
                    continue
                shown_rar, shown_st = (rar.lower(), st.upper()) if n % 5 == 0 else (rar, st)   # case differences are tolerated
                wa.cell(row=r["row"], column=lc[i][0], value=shown_rar)
                wa.cell(row=r["row"], column=lc[i][1], value=shown_st)
                got[i] = [rar, st]
            else:
                wa.cell(row=r["row"], column=lc[i][0], value="Rare")
                wa.cell(row=r["row"], column=lc[i][1], value="(none)")
        lines[k] = got
    loadouts, slots = {}, {}
    max_slots = schema["artifacts"]["max_slots"]
    for i, ct in enumerate(cts):
        picks = [art_keys[(i * 5 + s * 7) % len(art_keys)] for s in range(4)]
        if i == 4:
            picks = [picks[0], "(none)", picks[0], "bogus artifact"]    # empty slot, a repeat and an unknown name
        names = [cm["artifacts"]["rows"][k]["name"] if k in cm["artifacts"]["rows"] else k for k in picks]
        for s, row in enumerate(inp["slotRows"]):
            ws.cell(row=row, column=inp["firstCol"] + i, value=names[s])
        eq, seen, pos = [], set(), []
        for k in picks:
            if k in cm["artifacts"]["rows"] and k not in seen:
                seen.add(k)
                eq.append(k)
                pos.append(k)
            else:
                pos.append("")                                          # (none) / a repeat / an unknown name: that slot stays empty
        loadouts[ct] = eq
        slots[ct] = pos + [""] * (max_slots - len(pos))                 # the app's slots of that content type: slot i = the workbook's Slot i, the 5th is free
    order = [a["key"] for a in schema["artifacts"]["artifacts"]]
    table = {k: {"star": None if stars[k] == "Not Unlocked" else stars[k], "lines": [{"rarity": r, "stat": st} for r, st in lines[k]]} for k in order}
    expected["loadouts"] = loadouts                      # content type -> equipped artifact keys (schema order is applied by the app)
    expected["slots"] = slots                            # content type -> the app's slots (artifact key or "" per slot, max_slots entries)
    expected["stars"] = stars
    expected["table"] = table                            # the whole table (stars + lines) the app must hold after the import: shared by every content type
    expected["linesRead"] = sum(1 for k in order for r, st in lines[k] if st != "(none)")
    # companions: Hero 7, Dark Knight 18, Wind Archer "3", one "Not unlocked", the rest blank
    wc = wb.create_sheet("CompanionsInput")
    wc["A4"], wc["B4"] = "Companion", "Level (Not unlocked / 1-18)"
    levels = {}
    for name, row in cm["companions"]["rows"].items():
        wc.cell(row=row, column=1, value=name)
        if name in owned:
            wc.cell(row=row, column=cm["companions"]["levelCol"], value=owned[name])
            levels[name] = int(owned[name])
        elif name == "Bishop":
            wc.cell(row=row, column=cm["companions"]["levelCol"], value="Not unlocked")
    expected["companionLevels"] = levels
    # PotentialCubes (gear table) with planted problems
    expected["cubes"] = cubes_case(cid, list(MAP).index(cid), wb)
    expected_warnings += expected["cubes"]["warnings"]
    expected["warnings"] = expected_warnings
    expected["class"] = cid
    save(wb, f"class_{cid}.xlsx")
    (OUT / f"class_{cid}.expected.json").write_text(json.dumps(expected, indent=1) + "\n")


def cubes_case(cid, idx, wb):
    """PotentialCubes: the 30-row gear table with planted rows (see the comments), written at the map's coordinates.  Returns the expected import: `state` (the
    app's `FormState.cubes`), counts, how many warnings the planted problems must give and message hints.  The planted slots rotate with the class index."""
    cc = MAP[cid]["cubes"]
    T = CUBE_TABLES
    slots = [s_["key"] for s_ in T["slots"]]
    labels = {s_["key"]: s_["label"] for s_ in T["slots"]}
    ws = wb.create_sheet(cc["sheet"])
    ws["A1"] = "Potential Cubes — Current Gear State"
    for i, h in enumerate(cc["headers"]):
        ws.cell(row=cc["headerRow"], column=i + 1, value=h)
    S = lambda k: slots[(k + idx) % len(slots)]
    roll = lambda slot, n: sorted(T["statsBySlot"][slot])[(n * 3 + idx) % len(T["statsBySlot"][slot])]
    unrollable = lambda slot, n: [x for x in T["stats"] if x not in T["statsBySlot"][slot]][n % 3]

    def put(row, slot_text, type_text, rarity, pity, lines):
        ws.cell(row=row, column=cc["slotCol"], value=slot_text)
        ws.cell(row=row, column=cc["typeCol"], value=type_text)
        ws.cell(row=row, column=cc["rarityCol"], value=rarity)
        ws.cell(row=row, column=cc["pityCol"], value=pity)
        for (sc, vc), (st, v) in zip(cc["lineCols"], lines):
            ws.cell(row=row, column=sc, value=st)
            ws.cell(row=row, column=vc, value=v)

    def opts(slot, rarity, i, stat):
        """the values the app's tables allow for this line (prime first, then descending), merged like lib/cubes.ts rollOptionsIn"""
        by = {}
        for key in ("ALL", slot):
            for v, prime in T["rollValues"].get(key, {}).get(rarity, {}).get(str(i + 1), {}).get(stat, []):
                by[v] = by.get(v, False) or prime
        return [v for v, _ in sorted(by.items(), key=lambda kv: (not kv[1], -kv[0]))]

    def val(slot, rarity, i, stat, k=0, fallback=5):
        o = opts(slot, rarity, i, stat)
        return o[min(k, len(o) - 1)] if o else fallback

    def fix(slot, rarity, i, stat, v):
        """(expected value, was cleared): a value outside the allowed ones is cleared, a single allowed value fills a blank, no table entry = kept"""
        o = opts(slot, rarity, i, stat)
        if not o:
            return v, False
        if v is not None and any(abs(x - v) < 1e-9 for x in o):
            return v, False
        return (o[0] if len(o) == 1 else None), v is not None

    cleared = 0
    blank = [("(none)", 0)] * 3
    planted = {}   # (slot, type) -> (slot text, type text, rarity, pity, lines)
    expected_rows = {}     # key -> {"rarity", "pity", "lines": [[stat, value|None] x 3]}
    warnings = 0
    ignored = 0
    hints = []
    NONE = ["(none)", None]

    # A: three rollable lines, a capitalised rarity, a pity below the cap
    a = S(0)
    la = [(roll(a, i), val(a, "legendary", i, roll(a, i), k=i % 2)) for i in range(3)]
    planted[(a, "Potential")] = (a, "Potential", "Legendary", 120, la)
    expected_rows[f"{a}|Potential"] = {"rarity": "legendary", "pity": 120, "lines": [[x, y] for x, y in la]}
    # B: Bonus Potential of the same slot, two lines, the third empty
    lb = [(roll(a, 3), val(a, "epic", 0, roll(a, 3))), (roll(a, 4), val(a, "epic", 1, roll(a, 4))), ("(none)", 0)]
    planted[(a, "Bonus Potential")] = (a, "Bonus Potential", "epic", 49, lb)
    expected_rows[f"{a}|Bonus Potential"] = {"rarity": "epic", "pity": 49, "lines": [[lb[0][0], lb[0][1]], [lb[1][0], lb[1][1]], NONE]}
    # C: pity above the Rare cap (60), an UNKNOWN stat (line left empty), a stat this slot cannot roll (kept + flagged)
    c = S(1)
    nr = unrollable(c, idx)
    lc = [(roll(c, 0), val(c, "rare", 0, roll(c, 0))), ("Bogus Stat", 5), (nr, 7)]
    assert not opts(c, "rare", 2, nr), "the planted not-rollable stat must have no roll entry on that slot"
    planted[(c, "Potential")] = (c, "Potential", "rare", 75, lc)
    expected_rows[f"{c}|Potential"] = {"rarity": "rare", "pity": 75, "lines": [[lc[0][0], lc[0][1]], NONE, [nr, 7]]}
    warnings += 3
    hints += [f'unknown stat "Bogus Stat"; the line was left empty', f"{nr} cannot roll on this slot", "is not below the rare cap of 60 for Potential"]
    # D: slot written as its label, type in lower case, rarity upper case, pity exactly at the Unique Bonus cap (417), a stat without a value, a value without a stat,
    #    a numeric string
    d = S(2)
    v2 = val(d, "unique", 2, roll(d, 2), fallback=7.5)
    ld = [(roll(d, 0), None), ("(none)", 3), (roll(d, 2).upper(), str(v2))]
    d0, _ = fix(d, "unique", 0, roll(d, 0), None)
    planted[(d, "Bonus Potential")] = (labels[d], "bonus potential", "UNIQUE", 417, ld)
    expected_rows[f"{d}|Bonus Potential"] = {"rarity": "unique", "pity": 417, "lines": [[ld[0][0], d0], NONE, [roll(d, 2), v2]]}
    warnings += 1
    ignored += 1
    hints += ["is not below the unique cap of 417 for Bonus Potential"]
    if d0 is None:                      # a stat with several allowed values stays blank (a single allowed value is filled in silently)
        warnings += 1
        hints += ["has no value; left empty"]
    # E: top tier with a pity count (meaningless), an upper-case stat name
    e = S(3)
    #    and a value the line cannot roll (cleared, listed as not imported)
    e1 = next(x for x in sorted(T["statsBySlot"][e]) if len(opts(e, "mystic", 1, x)) >= 2)
    le = [(roll(e, 0).upper(), val(e, "mystic", 0, roll(e, 0))), (e1, 0.123), ("(none)", 0)]
    planted[(e, "Potential")] = (e, "Potential", "mystic", 5, le)
    expected_rows[f"{e}|Potential"] = {"rarity": "mystic", "pity": 5, "lines": [[roll(e, 0), le[0][1]], [e1, None], NONE]}
    warnings += 1
    cleared += 1
    hints += ["is the top tier, so pity 5 has no meaning"]
    # F: an unknown rarity and a pity that is not a number, no lines -> an unconfigured row (not stored)
    f = S(4)
    planted[(f, "Potential")] = (f, "Potential", "Godlike", "abc", blank)
    warnings += 2
    hints += ['unknown rarity "Godlike"; normal used', 'pity "abc" is not a number']
    # G: a pity count only (no lines): stored, but not a piece with lines
    g = S(5)
    planted[(g, "Bonus Potential")] = (g, "Bonus Potential", "normal", 20, blank)
    expected_rows[f"{g}|Bonus Potential"] = {"rarity": "normal", "pity": 20, "lines": [NONE, NONE, NONE]}

    row = cc["firstRow"]
    for slot in slots:
        for t in T["potentialTypes"]:
            put(row, *planted.get((slot, t), (slot, t, "normal", 0, blank)))
            row += 1
    assert row - 1 == cc["lastRow"]
    # below the table: a repeated (slot, type) -> the first row wins (warning); a note -> not ours, silently skipped
    put(row, a, "Potential", "epic", 3, [(roll(a, 5), 1), ("(none)", 0), ("(none)", 0)])
    ws.cell(row=row + 2, column=1, value="Notes: values typed by hand")
    warnings += 1
    hints += ["appears twice"]
    pieces = sum(1 for r_ in expected_rows.values() if any(l[0] != "(none)" for l in r_["lines"]))
    nlines = sum(1 for r_ in expected_rows.values() for l in r_["lines"] if l[0] != "(none)")
    return {
        "state": {k: {"rarity": v["rarity"], "pity": v["pity"], "lines": [{"stat": l[0], "value": l[1]} for l in v["lines"]]} for k, v in expected_rows.items()},
        "pieces": pieces, "lines": nlines, "rows": len(expected_rows), "warnings": warnings, "ignored": ignored, "cleared": cleared, "hints": hints,
    }


def edge_cases():
    """Hero layout with odd values: text numbers, '%' suffixes, garbage, bad enum, a date-looking Chapter-Stage, an error cell, a formula cell (cached /
    uncached), a non-integer in an int field, only three content-type columns, a repeated header, an unknown header, no companions / artifacts sheets."""
    cm = MAP["hero"]
    inp = cm["inputs"]
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Inputs"
    ws["A1"] = cm["title"].replace("—", "-")      # a plain hyphen must still be recognised
    heads = ["Chapter Boss", "Breakthrough", "PvP", "Chapter Boss", "Mystery Dungeon"]
    for i, h in enumerate(heads):
        ws.cell(row=2, column=3 + i, value=h)
    ws[inp["level"]] = "150"
    ws[inp["contentType"]] = "World Boss"             # not a column of this file -> falls back with a warning
    r = inp["perContent"]
    ws.cell(row=r["flat_attack"], column=3, value="1,234.5")
    ws.cell(row=r["attack_pct"], column=3, value="12.5 %")
    ws.cell(row=r["crit_rate"], column=3, value="abc")
    ws.cell(row=r["crit_damage"], column=3, value=True)
    ws.cell(row=r["boss_normal_weight_choice"], column=4, value="  equal ")
    ws.cell(row=r["boss_normal_weight_choice"], column=3, value="More Normal")   # not applicable to Chapter Boss -> ignored
    ws.cell(row=r["chapter_stage"], column=3, value=45928)
    ws.cell(row=r["chapter_stage"], column=4, value=29.0)
    ws.cell(row=r["skill_lvl_1st"], column=3, value=2.5)                       # int field, not whole
    ws.cell(row=r["skill_lvl_2nd"], column=3, value=-4)                         # below min
    ws.cell(row=r["defense"], column=3, value="=B1*2")                          # formula without cached value
    ws.cell(row=r["damage"], column=3, value="=1/0")                            # becomes an error cell below
    ws.cell(row=r["flat_attack"], column=4, value="=A1*2")                      # formula with a cached value (patched)
    ws.cell(row=r["attack_pct"], column=5, value=77)                            # PvP column of this file is column E (index 2)
    ws.cell(row=r["boss_normal_weight_choice"], column=5, value="Whatever")
    ws.cell(row=r["pvp_fight_length"], column=5, value=30)
    save(wb, "edge_hero.xlsx")
    patch_cached(OUT / "edge_hero.xlsx", {
        "%s%d" % ("D", r["flat_attack"]): ("n", "999"),
        "%s%d" % ("C", r["damage"]): ("e", "#DIV/0!"),
    })

    wb = openpyxl.Workbook()
    wb.active.title = "Inputs"
    wb.active["A1"] = MAP["shadower"]["title"]
    for i, ct in enumerate(MAP["shadower"]["inputs"]["contentTypes"]):
        wb.active.cell(row=2, column=3 + i, value=ct)
    wb.active.cell(row=MAP["shadower"]["inputs"]["perContent"]["flat_attack"], column=3, value=5000)
    save(wb, "inputs_only_shadower.xlsx")


def main():
    reader_cases()
    edge_cases()
    for cid in MAP:
        class_case(cid)
    print(f"wrote {len(list(OUT.iterdir()))} files to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
