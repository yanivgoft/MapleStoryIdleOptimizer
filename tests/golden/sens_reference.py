#!/usr/bin/env python3
"""Ground truth of the Sensitivity golden file: evaluates SENSITIVITY-SLIMMED copies of the FP-Mage WORKBOOK with the ``formulas`` package.

The full Sensitivity sheet (63 stat / toggle blocks + 10 CDR blocks + 14 timeline strips, ~200k cells of very long formulas) is never evaluated whole:
per case a scratch copy keeps only the blocks / table rows the case compares (``sens_cases.py``), plus everything the main sheets need.  ONE ``formulas``
evaluation per case (run strictly one at a time - several GB each), the scratch .xlsx is deleted right after.

    python3 tests/golden/sens_reference.py --list
    python3 tests/golden/sens_reference.py --case "S/WB200/a"                  # one evaluation -> /tmp/engine_p3/results/<slug>.json
    python3 tests/golden/sens_reference.py --run-all                            # every missing case, sequential subprocesses
    python3 tests/golden/sens_reference.py --assemble                           # results -> tests/golden/fp_mage_sensitivity_golden.json
    options: --workbook PATH --builder PATH (default: the repo's workbook / builder)

Read per case: Summary Total / boss-only / normal-only, the Companion chain's main cells, and
  * stats:   the Sensitivity table row (units per +1%, current, new, baseline, new total, DPS gain, % gain) and the block's Total / boss-only / normal-only,
  * toggles: the hidden staging row (DPS gain, % gain, unlocked) and the block's three totals,
  * cdr:     the milestone table (Total, step gain, % gain),
  * tables:  the Companion Comparison staging block (level, gain, %, unlocked) and the Summoning-Time breakdown table.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import re
import resource
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
SCRATCH = Path("/tmp/engine_p3")
RESULTS = SCRATCH / "results"
WORKBOOK = REPO / "FP-Mage" / "FP-Mage-DPS-Calculator.xlsx"
BUILDER = REPO / "src" / "build_fp_mage_workbook.py"
GOLDEN = HERE / "fp_mage_sensitivity_golden.json"


def slug(case_id):
    return re.sub(r"[^A-Za-z0-9_.+-]+", "_", case_id)


def load_builder(path):
    """The builder module (module-level tables only; main() is NOT run).  A frozen copy of the builder outside the repo (--builder) is executed
    with ``__file__`` pointing at the repo's src/ so its REPO-relative data paths resolve."""
    sys.path.insert(0, str(REPO / "src"))
    g = {"__file__": str(BUILDER), "__name__": "bm_sens"}
    exec(compile(Path(path).read_text(), str(path), "exec"), g)

    class NS:
        pass
    bm = NS()
    bm.__dict__.update(g)
    return bm


def block_rows(bm, key):
    """(first row of the block, first row of its re-run strip or None, index in STAT_SWEEP) of a STAT_SWEEP key."""
    sweep = [k for k, _l, _t in bm.STAT_SWEEP]
    counter, strip_of = 0, {}
    for k in sweep:
        if k in bm.STATUS_REBUILD_KEYS:
            strip_of[k] = bm.STATUS_STRIPS_START + counter * (bm.STATUS_STRIP_HEIGHT + 3)
            counter += 1
    idx = sweep.index(key)
    base = bm.BLOCK_START + idx * bm.BLOCK_HEIGHT
    return base, strip_of.get(key), idx


def kept_rows(bm, case):
    keep = set()
    plan = []   # (kind, key, base, strip)
    for key in case["stats"]:
        base, strip, _ = block_rows(bm, key)
        keep |= set(range(base, base + bm.BLOCK_HEIGHT))
        if strip is not None:
            keep |= set(range(strip, strip + bm.STATUS_STRIP_HEIGHT + 2))
        keep.add(bm.SENSITIVITY_ROW_FOR[key])
        plan.append(("stat", key, base))
    bool_keys = [e[0] for e in bm.STAT_SWEEP_ARTIFACT_ENTRIES]
    for art in case["toggles"]:
        key = f"{art}_equipped"
        base, strip, _ = block_rows(bm, key)
        keep |= set(range(base, base + bm.BLOCK_HEIGHT))
        if strip is not None:
            keep |= set(range(strip, strip + bm.STATUS_STRIP_HEIGHT + 2))
        keep.add(bm.ARTIFACT_TABLE_FIRST_DATA_ROW + bool_keys.index(key))
        plan.append(("toggle", art, base))
    if case["cdr"]:
        sweep_end = bm.BLOCK_START + len(bm.STAT_SWEEP) * bm.BLOCK_HEIGHT
        header = sweep_end + 1
        for i, _v in enumerate(bm.CDR_SWEEP_VALUES):
            base = header + len(bm.CDR_SWEEP_VALUES) + 3 + i * bm.BLOCK_HEIGHT
            strip = bm.STATUS_STRIPS_START + (sum(1 for k, _l, _t in bm.STAT_SWEEP if k in bm.STATUS_REBUILD_KEYS) + i) * (bm.STATUS_STRIP_HEIGHT + 3)
            keep |= set(range(base, base + bm.BLOCK_HEIGHT)) | set(range(strip, strip + bm.STATUS_STRIP_HEIGHT + 2))
            keep.add(header + 1 + i)
            plan.append(("cdr", bm.CDR_SWEEP_VALUES[i], base))
    if case["tables"]:
        keep |= set(range(bm.COMPANION_TABLE_FIRST_DATA_ROW, bm.COMPANION_TABLE_LAST_ROW + 1))
        keep |= set(range(bm.COMPANION_BREAKDOWN_FIRST_ROW, bm.COMPANION_BREAKDOWN_LAST_ROW + 1))
    return keep, plan


def build_scratch(bm, wb_path, case, out_path):
    import openpyxl
    from openpyxl.utils import get_column_letter  # noqa: F401
    inputs = case["inputs"]
    wb = openpyxl.load_workbook(wb_path)
    wi = wb["Inputs"]
    ct = inputs["content_type"]
    col = next(c for c in range(3, 3 + len(bm.CONTENT_TYPES)) if wi.cell(2, c).value == ct)
    wi.cell(bm.IN["level"], 2).value = inputs["level"]
    wi.cell(bm.IN["content_type"], 2).value = ct
    for key, v in inputs.items():
        if key in ("level", "content_type", "artifacts", "companion_level", "artifact_stars", "companion_levels"):
            continue
        if key not in bm.IN:
            raise KeyError(f"input {key!r} is not a workbook Inputs key")
        wi.cell(bm.IN[key], col).value = v
    # equipped slots (every content type's column) + star level of EVERY artifact (ArtifactsInput)
    labels = [bm.ARTIFACT_LABELS[a["key"]] for a in inputs.get("artifacts", [])]
    labels += ["(none)"] * (len(bm.INPUT_ARTIFACT_SLOT_ROWS) - len(labels))
    for row, label in zip(bm.INPUT_ARTIFACT_SLOT_ROWS, labels):
        for c in range(3, 3 + len(bm.CONTENT_TYPES)):
            wi.cell(row, c).value = label
    wa = wb["ArtifactsInput"]
    for art, star in inputs["artifact_stars"].items():
        wa.cell(bm.ARTIFACTS_INPUT_ROW[art], 2).value = "Not Unlocked" if star is None else int(star)
    # no potential lines (they are an input of the equip rows, set separately by `potential`): stat cells D / G / J = "(none)", gain cells L = constant
    for art, row in bm.ARTIFACTS_INPUT_ROW.items():
        for c in (4, 7, 10):
            if wa.cell(row, c).value is not None:
                wa.cell(row, c).value = "(none)"
        wa.cell(row, 12).value = float(case["potential"].get(art, 0.0))
    # companions: the chosen one's level on CompanionsInput (+ every other companion for the comparison table)
    choice = inputs["companion_choice"]
    levels = dict(inputs.get("companion_levels") or {})
    if choice != "None":
        levels.setdefault(choice, inputs["companion_level"])
    wc = wb["CompanionsInput"]
    for name, row in bm.COMPANION_INPUT_ROW.items():
        lv = levels.get(name, 0)
        wc.cell(row, 2).value = int(lv) if lv else "Not unlocked"
    # slim: formulas outside Sensitivity that read it -> 0; Sensitivity keeps only the compared rows; Companion grid columns only when a table is compared
    for ws_ in wb.worksheets:
        if ws_.title == "Sensitivity":
            continue
        for row_ in ws_.iter_rows():
            for c_ in row_:
                if isinstance(c_.value, str) and c_.value.startswith("=") and "Sensitivity!" in c_.value:
                    c_.value = 0
    keep, _plan = kept_rows(bm, case)
    ws = wb["Sensitivity"]
    for (r, c) in list(ws._cells.keys()):
        if r not in keep:
            del ws._cells[(r, c)]
    if not case["tables"]:
        for row_ in wb["Companion"].iter_rows(min_col=3):
            for c_ in row_:
                c_.value = None
    wb.save(out_path)


def scalar(v):
    import numpy as np
    try:
        a = np.asarray(v.value).reshape(-1)[0]
    except Exception:
        return str(v)
    if isinstance(a, (bool, np.bool_)):
        return bool(a)
    try:
        return float(a)
    except (TypeError, ValueError):
        return str(a)


def evaluate(bm, case, path):
    import formulas
    from openpyxl.utils import get_column_letter
    t0 = time.time()
    model = formulas.ExcelModel().loads(str(path)).finish()
    t1 = time.time()
    sol = model.calculate()
    t2 = time.time()
    cells = {}
    pat = re.compile(r"\]([^']+)'!([A-Z]+[0-9]+)$")
    for k, v in sol.items():
        m = pat.search(k)
        if m:
            cells[(m.group(1).upper(), m.group(2))] = v

    def get(sheet, addr):
        v = cells.get((sheet.upper(), addr))
        return None if v is None else scalar(v)
    out = dict(stats={}, toggles={}, cdr=[], companions=[], summon_time=[], summary={}, companion_main={})
    out["summary"] = dict(total=get("Summary", f"B{bm.R_TOTAL}"), boss_only=get("Summary", f"B{bm.R_BOSS_ONLY_TOTAL}"),
                          normal_only=get("Summary", f"B{bm.R_NORMAL_ONLY_TOTAL}"), aps=get("Summary", f"B{bm.R_APS}"))
    for name in ("best", "best_s", "best_E", "best_Tend", "comp_blend_dps", "comp_boss_dps", "comp_norm_dps", "s_0", "W_0", "stunfracB", "stunfracN",
                 "horn_uptime", "pb", "pn", "tb0", "Tbp"):
        out["companion_main"][name] = get("Companion", f"B{bm.COMPANION_ROW_OF[name]}")
    L = bm.LAST_ROW
    bool_keys = [e[0] for e in bm.STAT_SWEEP_ARTIFACT_ENTRIES]
    _keep, plan = kept_rows(bm, case)
    for kind, key, base in plan:
        blk = dict(total=get("Sensitivity", f"B{base + L + 13}"), boss=get("Sensitivity", f"B{base + L + 11}"), normal=get("Sensitivity", f"B{base + L + 12}"))
        if kind == "stat":
            r = bm.SENSITIVITY_ROW_FOR[key]
            blk.update({n: get("Sensitivity", f"{c}{r}") for n, c in (("units_per_1pct", "B"), ("current", "D"), ("new", "E"), ("baseline", "F"),
                                                                       ("new_total", "G"), ("dps_gain", "H"), ("pct_gain", "I"))})
            out["stats"][key] = blk
        elif kind == "toggle":
            r = bm.ARTIFACT_TABLE_FIRST_DATA_ROW + bool_keys.index(f"{key}_equipped")
            blk.update(dps_gain=get("Sensitivity", f"{get_column_letter(28)}{r}"), pct_gain=get("Sensitivity", f"{get_column_letter(29)}{r}"),
                       unlocked=get("Sensitivity", f"{get_column_letter(30)}{r}"))
            out["toggles"][key] = blk
        else:
            sweep_end = bm.BLOCK_START + len(bm.STAT_SWEEP) * bm.BLOCK_HEIGHT
            i = bm.CDR_SWEEP_VALUES.index(key)
            r = sweep_end + 2 + i
            blk.update(cdr=key, table_total=get("Sensitivity", f"B{r}"), table_step=get("Sensitivity", f"C{r}"), table_pct=get("Sensitivity", f"D{r}"))
            out["cdr"].append(blk)
    if case["tables"]:
        for i, name in enumerate(bm.cm.COMPANIONS):
            r = bm.COMPANION_TABLE_FIRST_DATA_ROW + i
            out["companions"].append(dict(name=name, level=get("Sensitivity", f"{get_column_letter(34)}{r}"), gain=get("Sensitivity", f"{get_column_letter(35)}{r}"),
                                          pct=get("Sensitivity", f"{get_column_letter(36)}{r}"), unlocked=get("Sensitivity", f"{get_column_letter(37)}{r}"),
                                          rank=get("Sensitivity", f"{get_column_letter(38)}{r}")))
        for i, x in enumerate(bm.COMPANION_POT_TOTALS):
            r = bm.COMPANION_BREAKDOWN_FIRST_ROW + i
            out["summon_time"].append(dict(total_pct=get("Sensitivity", f"A{r}"), avg_boss_dps_change=get("Sensitivity", f"B{r}"),
                                           boss_phase_time_factor=get("Sensitivity", f"C{r}"), boss_damage_change=get("Sensitivity", f"D{r}"),
                                           normal_dps_change=get("Sensitivity", f"E{r}"), weighted_dps_change=get("Sensitivity", f"F{r}")))
    out["load_s"], out["calc_s"] = round(t1 - t0, 1), round(t2 - t1, 1)
    return out


def run_case(case_id, out_json, wb_path, builder_path):
    from sens_cases import sens_cases
    case = next(c for c in sens_cases() if c["id"] == case_id)
    bm = load_builder(builder_path)
    SCRATCH.mkdir(exist_ok=True)
    scratch = SCRATCH / f"sens_run_{os.getpid()}.xlsx"
    t0 = time.time()
    try:
        build_scratch(bm, wb_path, case, scratch)
        t_build = time.time() - t0
        res = evaluate(bm, case, scratch)
    finally:
        if scratch.exists():
            scratch.unlink()
    res.update(case=case_id, build_s=round(t_build, 1), eval_total_s=round(time.time() - t0, 1),
               max_rss_gb=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e9, 2))
    RESULTS.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(res))
    print(f"{case_id}: total={res['summary']['total']!r} blocks={len(res['stats']) + len(res['toggles']) + len(res['cdr'])} build {res['build_s']}s "
          f"load {res['load_s']}s calc {res['calc_s']}s total {res['eval_total_s']}s rss {res['max_rss_gb']} GB", flush=True)


def run_all(wb_path, builder_path, only=None):
    from sens_cases import sens_cases
    RESULTS.mkdir(parents=True, exist_ok=True)
    for case in sens_cases():
        cid = case["id"]
        if only and not re.search(only, cid):
            continue
        out = RESULTS / f"{slug(cid)}.json"
        if out.exists():
            continue
        r = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--case", cid, "--out", str(out), "--workbook", str(wb_path),
                            "--builder", str(builder_path)], timeout=7200)
        if r.returncode != 0:
            print(f"FAILED {cid} (rc={r.returncode})", flush=True)
            break
        for f in SCRATCH.glob("sens_run_*.xlsx"):          # never leave a scratch workbook behind
            f.unlink()


def assemble(wb_path, builder_path):
    from sens_cases import sens_cases
    cases = {}
    for case in sens_cases():
        f = RESULTS / f"{slug(case['id'])}.json"
        if not f.exists():
            print("missing", case["id"])
            continue
        cases[case["id"]] = dict(inputs=case["inputs"], stats=case["stats"], toggles=case["toggles"], cdr=case["cdr"], tables=case["tables"],
                                 potential=case["potential"], workbook=json.loads(f.read_text()))
    meta = dict(workbook=str(Path(wb_path).name), workbook_sha256=hashlib.sha256(Path(wb_path).read_bytes()).hexdigest(),
                builder_sha256=hashlib.sha256(Path(builder_path).read_bytes()).hexdigest(),
                strip="Sensitivity sheet reduced to the compared blocks / rows; formulas outside it reading it = 0; Companion grid columns blanked unless a table is compared",
                evaluator="formulas " + __import__("formulas").__version__)
    GOLDEN.write_text(json.dumps(dict(meta=meta, cases=cases), indent=0))
    secs = [c["workbook"]["eval_total_s"] for c in cases.values()]
    print(f"wrote {GOLDEN}: {len(cases)} cases; evaluation seconds min/mean/max = {min(secs):.0f}/{sum(secs) / len(secs):.0f}/{max(secs):.0f}; total {sum(secs) / 60:.1f} min")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--case")
    ap.add_argument("--out")
    ap.add_argument("--run-all", action="store_true")
    ap.add_argument("--only")
    ap.add_argument("--assemble", action="store_true")
    ap.add_argument("--workbook", default=str(WORKBOOK))
    ap.add_argument("--builder", default=str(BUILDER))
    a = ap.parse_args()
    if a.list:
        from sens_cases import sens_cases
        for c in sens_cases():
            print(c["id"], "done" if (RESULTS / f"{slug(c['id'])}.json").exists() else "")
    elif a.case:
        run_case(a.case, Path(a.out) if a.out else RESULTS / f"{slug(a.case)}.json", a.workbook, a.builder)
    elif a.run_all:
        run_all(a.workbook, a.builder, a.only)
    elif a.assemble:
        assemble(a.workbook, a.builder)
    else:
        ap.print_help()
