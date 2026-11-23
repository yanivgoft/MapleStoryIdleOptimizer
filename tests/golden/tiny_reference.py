#!/usr/bin/env python3
"""Ground truth for ``engine.equipment`` / ``engine.potentials`` and the stat -> DPS-per-unit table of ``engine.cubes``: a TINY standalone workbook
evaluated with the ``formulas`` package.

The workbook holds the REAL sheets the builder generates for these features - ``Equipment Compare`` (``build_equipment_compare_sheet``) and
``ArtifactsInput`` (``build_artifacts_input_sheet``: potential-line gains, grouping, Total Potential DPS Gain, Equipped? / Star Level resolution) - plus the
CubeData ``J:K`` stat table (``dps_per_unit_expr`` for every stat), with the cells they read replaced by stubs: ``Summary!B3`` (Total DPS), ``Sensitivity!H``
(the DPS-per-unit column, one stub value per sweep key), a few ``Inputs`` cells (level, crit rate, the 4 equipped-artifact slot pickers) and
``Artifacts!B<AGG_CRIT_RATE>``.  No full workbook is opened (about 50 KB, one evaluation takes a fraction of a second); the ``Companion Summoning Time``
stat row is replaced by 0 (its formula reads the companion model, which is not part of this tiny workbook).

    python3 tests/golden/tiny_reference.py --write       # regenerate tests/golden/tiny_golden.json   (needs openpyxl + formulas)
    python3 tests/golden/tiny_reference.py --check-source  # exit 1 when the builder's tables changed since the golden was written

Each case sets EVERY stub / input cell (so a case is self-contained) and reads: all CubeData K cells, all ArtifactsInput gain / total / equipped / star
cells, and every Equipment Compare cell (per-line gain / first / group / factor, totals, % and the delta).
"""
import hashlib
import importlib.util
import json
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BUILDER = REPO / "src" / "build_fp_mage_workbook.py"
GOLDEN = HERE / "tiny_golden.json"
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))   # the builder imports companion_model etc. from src/


def load_builder():
    spec = importlib.util.spec_from_file_location("build_fp_mage_workbook_tiny", BUILDER)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["build_fp_mage_workbook_tiny"] = mod
    spec.loader.exec_module(mod)
    return mod


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ----------------------------------------------------------------------------------------------------------------------------------------------
# the tiny workbook
# ----------------------------------------------------------------------------------------------------------------------------------------------
def build_tiny(path, mod):
    import openpyxl
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    wb.create_sheet("Summary")
    wb.create_sheet("Sensitivity")
    wb.create_sheet("Inputs")
    wb.create_sheet("Artifacts")
    mod.build_equipment_compare_sheet(wb)
    mod.build_artifacts_input_sheet(wb)
    cube = wb.create_sheet("CubeData")
    stats = ["(none)"] + mod.ALL_POTENTIAL_STATS
    for i, stat in enumerate(stats):
        cube.cell(row=i + 2, column=10, value=stat)
        if stat == "(none)" or stat == "Companion Summoning Time Increase %":
            cube.cell(row=i + 2, column=11, value=0)
        else:
            cube.cell(row=i + 2, column=11, value=mod.dps_per_unit_expr(stat))
    wb.save(path)
    return stats


def input_cells(mod):
    """Names of the constant cells a case sets: {name: (sheet, cell)}."""
    cells = {"total": ("SUMMARY", "B3"), "level": ("INPUTS", f"B{mod.IN['level']}"), "crit_rate": ("INPUTS", f"B{mod.IN['crit_rate']}"),
             "agg_crit": ("ARTIFACTS", f"B{mod.ART_ROW['AGG_CRIT_RATE']}")}
    for i, r in enumerate(mod.INPUT_ARTIFACT_SLOT_ROWS):
        cells[f"slot{i}"] = ("INPUTS", f"B{r}")
    for key, row in mod.SENSITIVITY_ROW_FOR.items():
        cells[f"H:{key}"] = ("SENSITIVITY", f"H{row}")
    return cells


def artifact_rows(mod):
    return {k: r for k, r in mod.ARTIFACTS_INPUT_ROW.items()}


def evaluate_cases(cases, mod, verbose=False):
    import formulas
    out = {}
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "tiny.xlsx"
        stats = build_tiny(path, mod)
        model = formulas.ExcelModel().loads(str(path)).finish()
        prefix = f"'[{path.name}]"
        ic = input_cells(mod)
        arows = artifact_rows(mod)
        n_lines = {k: (3 if mod.ARTIFACT_RANK[k] == "Legendary" else 2) for k in arows}
        line_cols = [("C", "D"), ("F", "G"), ("I", "J")]
        for cid, case in cases.items():
            t = time.time()
            inputs = {}

            def put(sheet, cell, value):
                inputs[f"{prefix}{sheet}'!{cell}"] = value
            put("SUMMARY", "B3", case["total"])
            put("INPUTS", ic["level"][1], case["level"])
            put("INPUTS", ic["crit_rate"][1], case["crit_rate"])
            put("ARTIFACTS", ic["agg_crit"][1], case["agg_crit"])
            for i in range(4):
                put("INPUTS", ic[f"slot{i}"][1], case["slots"][i])
            for key, row in mod.SENSITIVITY_ROW_FOR.items():
                put("SENSITIVITY", f"H{row}", case["H"][key])
            for art, row in arows.items():
                put("ARTIFACTSINPUT", f"B{row}", case["stars"][art])
                for li in range(n_lines[art]):
                    rc, sc = line_cols[li]
                    line = case["lines"][art][li]
                    put("ARTIFACTSINPUT", f"{rc}{row}", line[0])
                    put("ARTIFACTSINPUT", f"{sc}{row}", line[1])
            for side, (stat_c, val_c) in (("current", ("B", "C")), ("new", ("I", "J"))):
                eq = case["equip"][side]
                put("EQUIPMENT COMPARE", f"{val_c}5", eq["attack"])
                for r, (stat, val) in zip(range(6, 11), eq["lines"]):
                    put("EQUIPMENT COMPARE", f"{stat_c}{r}", stat)
                    put("EQUIPMENT COMPARE", f"{val_c}{r}", val)
            sol = model.calculate(inputs=inputs)
            index = {k.upper(): v for k, v in sol.items()}

            def get(sheet, cell):
                v = index[f"{prefix.upper()}{sheet}'!{cell}"].value
                v = v[0, 0] if hasattr(v, "shape") else v
                return v.item() if hasattr(v, "item") else v
            res = {"cube_k": {stat: get("CUBEDATA", f"K{i + 2}") for i, stat in enumerate(stats)}, "artifacts": {}, "equip": {}}
            for art, row in arows.items():
                res["artifacts"][art] = dict(
                    gains=[get("ARTIFACTSINPUT", f"{c}{row}") for c in ("E", "H", "K")[:n_lines[art]]], total=get("ARTIFACTSINPUT", f"L{row}"),
                    equipped=get("ARTIFACTSINPUT", f"M{row}"), star=get("ARTIFACTSINPUT", f"N{row}"))
            for side, cols in (("current", "BCDEFG"), ("new", "IJKLMN")):
                s = dict(rows=[], total_gain=get("EQUIPMENT COMPARE", f"{cols[2]}12"), pct=get("EQUIPMENT COMPARE", f"{cols[2]}13"))
                for r in range(5, 11):
                    s["rows"].append(dict(gain=get("EQUIPMENT COMPARE", f"{cols[2]}{r}"), group=get("EQUIPMENT COMPARE", f"{cols[3]}{r}"),
                                          first=get("EQUIPMENT COMPARE", f"{cols[4]}{r}"), factor=get("EQUIPMENT COMPARE", f"{cols[5]}{r}")))
                res["equip"][side] = s
            res["equip"]["delta"] = get("EQUIPMENT COMPARE", "D15")
            out[cid] = res
            if verbose:
                print(f"  {cid}: {time.time() - t:.2f}s", flush=True)
    return out


# ----------------------------------------------------------------------------------------------------------------------------------------------
# cases
# ----------------------------------------------------------------------------------------------------------------------------------------------
def make_cases(mod):
    arts = list(mod.ARTIFACT_LABELS)
    labels = mod.ARTIFACT_LABELS
    pot_stats = list(mod.ARTIFACT_POTENTIAL_VALUES)
    pot_rar = list(mod.ARTIFACT_POTENTIAL_RARITIES)
    eq_stats = list(mod.EQUIP_COMPARE_DROPDOWN_STATS)
    keys = list(mod.SENSITIVITY_ROW_FOR)

    def H(seed):
        # deterministic, distinct, positive rates (a different magnitude per key; some zero like an unpriced stat)
        return {k: (0.0 if (i + seed) % 11 == 0 else round((i + 3) * 1357.0 * (1 + 0.37 * ((i * seed) % 5)) + seed * 11.5, 4)) for i, k in enumerate(keys)}

    def stars(seed):
        opts = ["Not Unlocked", 0, 1, 2, 3, 4, 5]
        return {a: opts[(i * 3 + seed) % 7] for i, a in enumerate(arts)}

    def lines(seed):
        out = {}
        for i, a in enumerate(arts):
            ls = []
            for li in range(3):
                n = i * 5 + li * 3 + seed
                stat = "(none)" if n % 6 == 0 else pot_stats[n % len(pot_stats)]
                ls.append([pot_rar[(n * 2 + li) % len(pot_rar)], stat])
            # duplicate stats inside one artifact on a few rows (grouping rule)
            if i % 4 == 0:
                ls[1][1] = ls[0][1]
            if i % 5 == 0:
                ls[2][1] = ls[0][1]
            if i % 9 == 0:
                ls[2][1] = ls[1][1]
            out[a] = ls
        return out

    def equip(seed, dup):
        def side(s):
            ls = []
            for j in range(5):
                n = j * 4 + s + seed
                ls.append([("(none)" if n % 7 == 0 else eq_stats[n % len(eq_stats)]), round(1 + (n * 7) % 23 + 0.5 * (n % 3), 2)])
            return ls
        cur, new = side(1), side(5)
        if dup:       # duplicates: the same stat twice, a dropdown line on 'Attack (flat)' (merges into the fixed Attack line) and a crit-rate pair
            cur[1][0] = cur[0][0] = "Damage %"
            cur[3][0] = "Attack (flat)"
            new[2][0] = new[4][0] = "Critical Rate %"
            new[0][0] = "Damage %"
        return {"current": dict(attack=round(1500 + seed * 311.5, 2), lines=cur), "new": dict(attack=round(2200 + seed * 97.25, 2), lines=new)}

    book, roc, spear, bottle = labels["book_of_ancient"], labels["ring_of_cycles"], labels["reindeer_spear"], labels["bottle_of_emotion"]
    none4 = ["(none)"] * 4
    # (crit rate, artifact crit bucket, equipped slots, total, level): the Critical Rate cap rule - total >= 100 and neither Ring of Cycles nor Book of Ancient
    spec = [(60, 0, none4, 1.0e6, 120), (100, 0, none4, 2.5e6, 140), (120, 0, none4, 7.3e5, 200), (95, 5, none4, 1.23456789e7, 33),
            (99.5, 0.4, none4, 4.0e5, 1), (130, 0, [book, "(none)", "(none)", "(none)"], 9.0e6, 117), (130, 0, [roc, spear, "(none)", "(none)"], 3.3e6, 176),
            (100, 0, [bottle, "(none)", "(none)", "(none)"], 5.5e5, 64), (80, 25, none4, 2.2e6, 150), (150, 0, [bottle, book, roc, spear], 6.1e6, 99)]
    cases = {}
    for n, (crit, agg, slots, total, level) in enumerate(spec):
        cases[f"c{n}"] = dict(total=total, level=level, crit_rate=crit, agg_crit=agg, slots=slots, H=H(n + 1), stars=stars(n), lines=lines(n),
                              equip=equip(n, dup=(n % 2 == 1)))
    # a case where every equipped artifact slot is empty and the crit total is exactly 100 (>= boundary), plus ring of cycles only / book only
    return cases


def artifact_key_for(mod):
    return {v: k for k, v in mod.ARTIFACT_LABELS.items()}


def write():
    mod = load_builder()
    cases = make_cases(mod)
    t0 = time.time()
    results = evaluate_cases(cases, mod, verbose=True)
    data = dict(meta=dict(builder_sha256=sha256(BUILDER), generator="tests/golden/tiny_reference.py"),
                layout=dict(sensitivity_rows=mod.SENSITIVITY_ROW_FOR, artifact_rows=mod.ARTIFACTS_INPUT_ROW), cases=cases, results=results)
    GOLDEN.write_text(json.dumps(data))
    print(f"wrote {GOLDEN} ({GOLDEN.stat().st_size / 1e6:.2f} MB), {len(cases)} cases in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    if "--write" in sys.argv:
        write()
    elif "--check-source" in sys.argv:
        ok = json.loads(GOLDEN.read_text())["meta"]["builder_sha256"] == sha256(BUILDER)
        print("builder unchanged since the golden was written" if ok else "src/build_fp_mage_workbook.py CHANGED since the golden was written (tables may still be equal)")
        sys.exit(0 if ok else 1)
    else:
        print(__doc__)
