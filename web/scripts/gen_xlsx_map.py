#!/usr/bin/env python3
"""Regenerate web/src/lib/xlsx_map.json: where every engine input lives in each class's Excel calculator (the "Import from Excel" feature).

Run from the repository root with the system python3 (read-only: it imports src/build_<class>_workbook.py for its layout constants and reads the
web fixtures; it never builds, opens or evaluates a workbook):

    python3 web/scripts/gen_xlsx_map.py            # writes web/src/lib/xlsx_map.json and prints the report
    python3 web/scripts/gen_xlsx_map.py --check    # report only, exit 1 when the map would change or a layout disagrees with the engine

Per class id the map holds (sheet / row / column coordinates, 1-based; columns as numbers, A=1):

  title            the Inputs!A1 title the builder writes (how the browser recognises the class)
  inputs           Inputs sheet: header row (content-type names, columns C..L), level / content-type cells (column B, literal), `perContent`
                   (engine key -> row; one value per content type in C..L), the 4 artifact slot rows of the WORKBOOK (the app / engine allow 5: the
                   workbooks keep 4 Inputs rows, so the 5th slot is never imported), the companion choice row
  artifacts        ArtifactsInput: Star Level column + artifact key -> {name, row} + the (rarity, stat) column pairs of potential lines 1-3 (`lineCols`)
  companions       CompanionsInput: level column + companion name -> row
  cubes            PotentialCubes (the 15 slots x {Potential, Bonus Potential} gear table): header / first / last data row, the Slot / Potential Type / Rarity / Pity
                   columns and the (stat, value) column pairs of lines 1-3.  Read from the builder's own constants and source (headers list, column writes) and
                   cross-checked against the engine's cube meta fixtures; `--check` also compares the header row of every committed workbook that exists.
                   Equipment Compare is NOT imported (the user's decision), so it has no entry.

and one top-level `cubeTables` entry: the class-independent cube tables the importer needs without an API call (slots, potential types, rarities, stat names,
the stats each slot can roll, pity caps, limits).  It is a copy of the engine's `GET .../cubes/meta` (the fixtures of the 7 classes with cubes are identical in
these keys; `--check` fails when one differs from the copy or from the builder's constants).

The report lists keys that exist in the workbook but not in the engine schema and vice versa (expected: engine `companion_level` is derived from the
CompanionsInput sheet; computed rows are never read).
"""
import ast
import importlib
import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
FIX = ROOT / "web" / "src" / "fixtures"
OUT = ROOT / "web" / "src" / "lib" / "xlsx_map.json"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT))

# workbook IN key -> engine schema key, only where the names differ (today none do)
KEY_ALIASES: dict[str, str] = {}
# engine fields that legitimately have no Inputs row of their own
ENGINE_ONLY_OK = {"companion_level"}  # the chosen companion's level comes from CompanionsInput
# workbook Inputs rows that are shared across content types (column B literal) rather than one value per content type
SHARED_KEYS = ("level", "content_type")


# cube meta keys copied into the map's `cubeTables` (fixture key -> map key)
CUBE_TABLE_KEYS = {"slots": "slots", "potential_types": "potentialTypes", "rarities": "rarities", "none_stat": "noneStat", "stats": "stats",
                   "stats_by_slot": "statsBySlot", "pity_caps": "pityCaps"}


def cube_tables(problems: list[str]) -> dict:
    """The static cube tables from the fixtures of the classes that have a cube meta; every such fixture must agree on them."""
    metas = {p.name.split(".")[0]: json.loads(p.read_text()) for p in sorted(FIX.glob("*.cubes_meta.json"))}
    if not metas:
        raise SystemExit("no *.cubes_meta.json fixture found")
    first_id, first = next(iter(metas.items()))
    tables = {out_key: first[k] for k, out_key in CUBE_TABLE_KEYS.items()}
    tables["maxPity"] = first["limits"]["max_pity"]
    tables["maxLineValue"] = first["limits"]["max_line_value"]
    for cid, m in metas.items():
        for k in list(CUBE_TABLE_KEYS) + ["limits"]:
            if m[k] != first[k]:
                problems.append(f"cubes meta fixture of {cid} differs from {first_id} in '{k}' (the importer's static cube tables assume they are identical)")
    return tables


def cubes_layout(cid: str, m, tables: dict, problems: list[str]) -> dict:
    """PotentialCubes coordinates, from the builder's constants + the source of build_potential_cubes_sheet (so a layout change makes --check fail)."""
    text = (SRC / f"build_{cid}_workbook.py").read_text(encoding="utf-8")
    body = re.search(r"def build_potential_cubes_sheet\(.*?(?=\ndef )", text, re.S)
    if not body:
        raise SystemExit(f"{cid}: build_potential_cubes_sheet not found")
    body = body.group(0)
    hm = re.search(r"headers\s*=\s*(\[.*?\])", body, re.S)
    headers = ast.literal_eval(hm.group(1)) if hm else []
    want = ["Slot", "Potential Type", "Current Rarity", "Current Pity Count", "Line 1 Stat", "Line 1 Value", "Line 2 Stat", "Line 2 Value", "Line 3 Stat", "Line 3 Value"]
    if headers != want:
        problems.append(f"PotentialCubes headers changed: {headers}")
    col = {h: i + 1 for i, h in enumerate(headers)}
    checks = [
        (r"column=1, value=slot\)", "slot is written to column A"),
        (r"column=2, value=potential_type\)", "potential type is written to column B"),
        (r'column=3, value=saved\.get\("rarity"', "rarity is written to column C"),
        (r'column=4, value=saved\.get\("pity"', "pity is written to column D"),
        (r"enumerate\(\(5, 7, 9\)\)", "line stat columns are E / G / I"),
        (r"column=line_col \+ 1, value=val\)", "line value columns are the stat column + 1"),
    ]
    for pat, what in checks:
        if not re.search(pat, body):
            problems.append(f"PotentialCubes layout changed: expected {what}")
    if 'create_sheet("PotentialCubes")' not in body:
        problems.append("PotentialCubes sheet name changed")
    if list(m.CUBE_SLOTS) != [s["key"] for s in tables["slots"]]:
        problems.append("builder CUBE_SLOTS differ from the engine's cube slots")
    if list(m.POTENTIAL_TYPES) != tables["potentialTypes"]:
        problems.append("builder POTENTIAL_TYPES differ from the engine's potential types")
    if list(m.RARITY_ORDER) != [r["key"] for r in tables["rarities"]]:
        problems.append("builder RARITY_ORDER differs from the engine's rarities")
    if sorted(m.ALL_POTENTIAL_STATS) != sorted(tables["stats"]):
        problems.append("builder potential stat names differ from the engine's cube stats")
    n_rows = len(m.CUBE_SLOTS) * len(m.POTENTIAL_TYPES)
    if m.POTENTIAL_CUBES_LAST_DATA_ROW - m.POTENTIAL_CUBES_FIRST_DATA_ROW + 1 != n_rows:
        problems.append("PotentialCubes row range does not hold slots x potential types")
    return {
        "sheet": "PotentialCubes",
        "headerRow": m.POTENTIAL_CUBES_HEADER_ROW,
        "firstRow": m.POTENTIAL_CUBES_FIRST_DATA_ROW,
        "lastRow": m.POTENTIAL_CUBES_LAST_DATA_ROW,
        "slotCol": col["Slot"],
        "typeCol": col["Potential Type"],
        "rarityCol": col["Current Rarity"],
        "pityCol": col["Current Pity Count"],
        "lineCols": [[col[f"Line {i} Stat"], col[f"Line {i} Value"]] for i in (1, 2, 3)],   # (stat, value) of lines 1 / 2 / 3
        "headers": headers,
    }


def check_committed_workbook(cid: str, cubes: dict, problems: list[str], report: list[str]):
    """Drift check against the committed workbook (when present): its PotentialCubes header row and slot / type columns must match the map."""
    path = ROOT / m_dir(cid) / f"{m_dir(cid)}-DPS-Calculator.xlsx"
    if not path.exists():
        return
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        if cubes["sheet"] not in wb.sheetnames:
            problems.append(f"committed workbook has no {cubes['sheet']} sheet")
            return
        ws = wb[cubes["sheet"]]
        rows = list(ws.iter_rows(min_row=cubes["headerRow"], max_row=cubes["lastRow"], max_col=len(cubes["headers"]), values_only=True))
    finally:
        wb.close()
    if not rows or [str(v) for v in rows[0]] != cubes["headers"]:
        problems.append(f"committed workbook {path.name}: PotentialCubes header row differs from the map {rows[0] if rows else None}")
        return
    body = rows[1:]
    if len(body) != cubes["lastRow"] - cubes["firstRow"] + 1 or any(r[cubes["slotCol"] - 1] is None or r[cubes["typeCol"] - 1] is None for r in body):
        problems.append(f"committed workbook {path.name}: PotentialCubes rows {cubes['firstRow']}-{cubes['lastRow']} are not all (slot, type) rows")


def m_dir(cid: str) -> str:
    """Workbook folder / file prefix of a class id (fp_mage -> FP-Mage, ice_lightning_mage -> Ice-Lightning-Mage ...)."""
    special = {"fp_mage": "FP-Mage"}
    return special.get(cid, "-".join(w.capitalize() for w in cid.split("_")))


def col_letter(n: int) -> str:
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def title_of(cid: str) -> str:
    """The literal Inputs!A1 title (read from the builder's source: it is assigned inside build_inputs_sheet, not a module constant)."""
    text = (SRC / f"build_{cid}_workbook.py").read_text(encoding="utf-8")
    m = re.search(r'ws\["A1"\]\s*=\s*"([^"]*DPS Calculator Inputs)"', text)
    if not m:
        raise SystemExit(f"{cid}: no Inputs title found in the builder")
    return m.group(1)


def build_class(cid: str, report: list[str], tables: dict) -> dict:
    m = importlib.import_module(f"build_{cid}_workbook")
    schema = json.loads((FIX / f"{cid}.schema.json").read_text())
    fields = {f["key"]: f for f in schema["fields"]}
    editable = {k for k, f in fields.items() if not f["computed"]}
    problems = []

    if list(m.CONTENT_TYPES) != schema["content_types"]:
        problems.append(f"content types differ: workbook {list(m.CONTENT_TYPES)} vs engine {schema['content_types']}")
    if list(m.cm.COMPANIONS) != schema["companions"]:
        problems.append("companion list differs between workbook and engine")
    wb_arts = dict(m.ARTIFACT_LABELS)
    eng_arts = {a["key"]: a["name"] for a in schema["artifacts"]["artifacts"]}
    if wb_arts != eng_arts:
        problems.append("artifact keys/names differ between workbook and engine")
    from engine import artifacts as engine_artifacts

    if len(m.INPUT_ARTIFACT_SLOT_ROWS) != engine_artifacts.WORKBOOK_SLOTS:
        problems.append("artifact slot rows of the workbook differ from engine.artifacts.WORKBOOK_SLOTS")
    if schema["artifacts"]["max_slots"] < len(m.INPUT_ARTIFACT_SLOT_ROWS):
        problems.append("the engine allows fewer artifact slots than the workbook has")
    builder_text = (SRC / f"build_{cid}_workbook.py").read_text(encoding="utf-8")
    if "line_cols = [(3, 4, 5), (6, 7, 8), (9, 10, 11)]" not in builder_text:
        problems.append("ArtifactsInput potential-line columns differ from the layout the importer assumes (C/D, F/G, I/J)")

    per_content, shared = {}, {}
    wb_only, computed_skipped = [], []
    for key, row in m.IN.items():
        ekey = KEY_ALIASES.get(key, key)
        if ekey not in fields:
            wb_only.append(key)
            continue
        if fields[ekey]["computed"] or row in m.COMPUTED_INPUT_ROWS:
            computed_skipped.append(key)
            continue
        if key in SHARED_KEYS:
            shared[ekey] = row
        else:
            if key not in m.PER_CONTENT_TYPE_INPUT_KEYS:
                problems.append(f"{key}: not a per-content-type row in the workbook")
            if not fields[ekey]["per_content"]:
                problems.append(f"{key}: per content type in the workbook, shared in the engine")
            per_content[ekey] = row
    engine_only = sorted(editable - set(shared) - set(per_content) - {"content_type"} - ENGINE_ONLY_OK)
    for k in sorted(set(f for f in editable if fields[f]["per_content"]) - set(per_content) - ENGINE_ONLY_OK):
        problems.append(f"engine per-content field {k} has no Inputs row")

    cubes = cubes_layout(cid, m, tables, problems)
    check_committed_workbook(cid, cubes, problems, report)

    report.append(f"[{cid}] title={title_of(cid)!r}  per-content rows={len(per_content)}  shared={shared}  computed rows skipped={len(computed_skipped)}")
    report.append(f"    workbook-only keys: {wb_only or '-'}   engine-only keys (excluding companion_level): {engine_only or '-'}")
    for p in problems:
        report.append(f"    PROBLEM: {p}")

    return {
        "name": schema["name"],
        "title": title_of(cid),
        "problems": problems,
        "inputs": {
            "sheet": "Inputs",
            "headerRow": 2,
            "firstCol": 3,
            "contentTypes": list(m.CONTENT_TYPES),
            "level": f"B{shared['level']}",
            "contentType": f"B{shared['content_type']}",
            "perContent": per_content,
            "slotRows": list(m.INPUT_ARTIFACT_SLOT_ROWS),
            "noneLabel": "(none)",
        },
        "artifacts": {
            "sheet": "ArtifactsInput",
            "starCol": 2,
            "lineCols": [[3, 4], [6, 7], [9, 10]],      # (rarity, stat) of lines 1 / 2 / 3 (line 3: Legendary artifacts only); checked against the builder above
            "rows": {k: {"name": v, "row": m.ARTIFACTS_INPUT_ROW[k]} for k, v in wb_arts.items()},
        },
        "companions": {
            "sheet": "CompanionsInput",
            "levelCol": 2,
            "rows": dict(m.COMPANION_INPUT_ROW),
            "firstRow": m.COMPANIONS_INPUT_FIRST_ROW,
        },
        "cubes": cubes,
    }


def main() -> int:
    check = "--check" in sys.argv
    classes = [c["id"] for c in json.loads((FIX / "classes.json").read_text())["classes"]]
    report: list[str] = []
    out = {"_comment": "Generated by web/scripts/gen_xlsx_map.py - do not edit by hand.", "version": 1, "cubeTables": None, "classes": {}}
    table_problems: list[str] = []
    out["cubeTables"] = cube_tables(table_problems)
    for p in table_problems:
        report.append(f"PROBLEM: {p}")
    for cid in classes:
        out["classes"][cid] = build_class(cid, report, out["cubeTables"])
    print("\n".join(report))
    bad = [cid for cid, c in out["classes"].items() if c["problems"]] + (["cubeTables"] if table_problems else [])
    text = json.dumps(out, indent=1, ensure_ascii=False) + "\n"
    if check:
        same = OUT.exists() and OUT.read_text(encoding="utf-8") == text
        print("map up to date" if same else "map WOULD CHANGE")
        return 0 if same and not bad else 1
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(classes)} classes, {len(text)} bytes)" + (f"; classes with problems: {bad}" if bad else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
