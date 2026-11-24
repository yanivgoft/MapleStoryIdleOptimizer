#!/usr/bin/env python3
"""Ground truth for the cube optimizer golden: runs the ORIGINAL ``src/potential_cubes_ev.py`` logic on constructed inputs (no workbook).

The script reads everything from a workbook at import time, so it cannot be imported.  Instead its source is parsed with ``ast`` and only the
module-level function definitions and the small constants are executed (unmodified) in a namespace that is then given the same data the script would have
loaded from the workbook: DPS-per-unit table, baseline DPS, CDR curve, companion model, rarity table and roll table (the roll table is built from the
BUILDER's own ``_iter_potential_line_entries()`` - i.e. the rows the CubeData sheet holds - not from ``engine.cubes``, so the engine's table is checked too).
The script's own ``main()`` then runs on a constructed gear list (its ``read_current_state`` replaced) and the CSV it writes is the golden.

    python3 tests/golden/cubes_reference.py --write      # regenerate tests/golden/cubes_golden.json (a few minutes, numpy required)
    python3 tests/golden/cubes_reference.py --check-source   # exit 1 when src/potential_cubes_ev.py changed since the golden was written

numpy and (for the real FP-Mage pricing) the engine's sensitivity are only needed to REGENERATE; the test needs neither numpy nor the original.
"""
import ast
import contextlib
import csv
import hashlib
import importlib.util
import io
import json
import re
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

import cubes_cases as cc  # noqa: E402
from engine import cubes  # noqa: E402
import factor_mode  # noqa: E402

factor_mode.pin("legacy")        # reference numbers of the workbook path: skill levels clamp at 300

ORIGINAL = REPO / "src" / "potential_cubes_ev.py"
BUILDER = REPO / "src" / "build_fp_mage_workbook.py"
GOLDEN = HERE / "cubes_golden.json"
CONSTANTS = {"MAX_CUBES", "CUBE_MILESTONES", "CDR_STAT", "CDR_INPUT_ROW", "_CDR_NOTES", "_CDR_EXACT_FAILED", "COMPANION_STAT", "_ROW_COMPANION_BASE",
             "_COMPANION_CACHE", "_roll_dist_cache"}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_original_namespace():
    """The script's functions + constants, exactly as written, in a fresh namespace (no workbook is opened)."""
    import numpy as np
    tree = ast.parse(ORIGINAL.read_text())
    keep = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            keep.append(node)
        elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in CONSTANTS for t in node.targets):
            keep.append(node)
    ns = {"np": np, "re": re, "csv": csv, "Path": Path, "sys": sys, "__name__": "potential_cubes_ev_original"}
    exec(compile(ast.Module(body=keep, type_ignores=[]), str(ORIGINAL), "exec"), ns)
    return ns


def builder_roll_table():
    """{(slot, rarity, line): [(stat, value, weight)]} as read back from CubeData A:G rows (the builder's emission order)."""
    spec = importlib.util.spec_from_file_location("build_fp_mage_workbook_ref", BUILDER)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["build_fp_mage_workbook_ref"] = mod
    spec.loader.exec_module(mod)
    table = {}
    for slot, rarity, line, entry in mod._iter_potential_line_entries():
        table.setdefault((slot, rarity, line), []).append((entry["stat"], float(entry["value"]), float(entry["weight"])))
    return table, mod


class _CompanionStub:
    """Stands in for companion_python_model: ``run(host, choice, lvl, inc)`` looks the answer up in the spec's table."""

    def __init__(self, spec):
        self.runs = {round(float(k), 6): v for k, v in spec["runs"].items()}
        self.b0 = float(spec["b0"])

    def run(self, host, choice, lvl, inc):
        boss, norm = self.runs[round(inc - self.b0, 6)]
        return {"comp_boss_dps": boss, "comp_norm_dps": norm}


def run_original(spec, gear, roll_table, tmpdir):
    """The script's ``main()`` on ``gear`` with the workbook data of ``spec``; returns the CSV rows it wrote (list of dicts, floats / ints parsed)."""
    ns = load_original_namespace()
    base = spec["baseline_dps"]
    rates = cubes.rarity_rates()
    ns.update(DPS_PER_UNIT=dict(spec["dps_per_unit"]), BASELINE_DPS=base, CDR_CURRENT=float(spec["cdr_current"]),
              RARITY_ORDER=list(cubes.RARITY_ORDER), RARITY_UPGRADE_RATES={pt: {r: dict(rate=float(v["rate"]), max=float(v["max"])) for r, v in d.items()}
                                                                              for pt, d in rates.items()},
              ROLL_TABLE=roll_table)
    if spec.get("cdr_table"):
        pts = {float(x): float(t) for x, t in spec["cdr_table"]}
        pts[float(spec["cdr_current"])] = base
        ns["CDR_POINTS"] = sorted(pts.items())
    else:
        ns["CDR_POINTS"] = None
    comp = spec.get("companion")
    if comp:
        ns["COMPANION_MODEL"] = dict(cpm=_CompanionStub(comp), host=dict(w=comp["w"], player_boss=comp["player_boss"], player_norm=comp["player_norm"]),
                                     choice="X", lvl=1, b0=float(comp["b0"]), total=comp.get("total"), current_blend=comp.get("current_blend"))
    else:
        ns["COMPANION_MODEL"] = None
    ns["COMPANION_POINTS"] = ns["COMPANION_MODEL"]
    exact = cc.make_cdr_exact(spec)
    failed = ns["_CDR_EXACT_FAILED"]

    def exact_total_at_cdr(cdr):                      # the script re-evaluates the workbook here; the constructed case supplies a function instead
        if exact is None or cdr in failed:
            return None
        failed.add(cdr)
        value = exact(cdr)
        failed.discard(cdr)
        return value
    ns["exact_total_at_cdr"] = exact_total_at_cdr
    state = [dict(slot=g["slot"], potential_type=g["potential_type"], rarity=g["rarity"], pity=float(g["pity"]),
                  lines=[(s, float(v)) for s, v in g["lines"]]) for g in gear]
    ns["read_current_state"] = lambda: state
    csv_path = Path(tmpdir) / "out.csv"
    ns["CSV_PATH"] = csv_path
    with contextlib.redirect_stdout(io.StringIO()):
        ns["main"]()
    out = []
    with open(csv_path, newline="") as f:
        for r in csv.DictReader(f):
            row = dict(slot=r["Slot"], potential_type=r["PotentialType"], rarity=r["Rarity"], pity=float(r["Pity"]), current_value=float(r["CurrentValue"]),
                       current_value_pct=float(r["CurrentValue%"]))
            for col, key in (("SmallestNPositive", "smallest_n"), ("NFor50PctChance", "n_for_50pct"), ("NFor75PctChance", "n_for_75pct")):
                row[key] = None if r[col] == "" else int(r[col])
            row["milestone_ev"] = {n: float(r[f"EV@{n}"]) for n in cubes.CUBE_MILESTONES}
            row["milestone_ev_pct"] = {n: float(r[f"EV%@{n}"]) for n in cubes.CUBE_MILESTONES}
            out.append(row)
    return out


def real_fpmage_spec():
    """Pricing built by the adapter from a real engine.sensitivity run of FP-Mage (World Boss, Blaze Wizard Lv10), the companion model tabulated."""
    from engine import sensitivity
    from engine.classes import fp_mage
    inp = fp_mage.defaults("World Boss")
    inp.update(level=140, flat_attack=1_209_199, flat_int=60000, int_pct=150, luk=3000, crit_rate=80, crit_damage=150, attack_speed=40, damage=200,
               boss_damage=120, def_pen=40, final_damage=30, min_damage=60, max_damage=130, skill_cooldown_decrease=1.0, buff_duration_increase_pct=30,
               companion_choice="Blaze Wizard", companion_level=10, companion_summon_time_increase_pct=20)
    gear = cc.gear_cdr_companion()
    inp["companion_potential_lines_pct"] = cubes.companion_lines_pct(gear)
    sens = sensitivity.run(fp_mage, inp, which=["stats", "cdr", "summon_time"])
    p = cubes.pricing_from_sensitivity(sens, inp)
    spec = dict(baseline_dps=p.baseline_dps, dps_per_unit=p.dps_per_unit, cdr_current=p.cdr_current,
                cdr_table=[[r["cdr"], r["total_dps"]] for r in sens["cdr"]["rows"]], cdr_exact_slope=None)
    c = p.companion
    spec["companion"] = dict(b0=c.b0, w=c.w, player_boss=c.player_boss, player_norm=c.player_norm, total=c.total, current_blend=c.current_blend,
                             runs={str(x): [c.at(x)["comp_boss_dps"], c.at(x)["comp_norm_dps"]] for x in range(0, 121)})
    return spec, inp


def build_cases():
    grid, pity_extra, cdc = cc.gear_grid(), cc.gear_pity_extra(), cc.gear_cdr_companion()
    real, _inp = real_fpmage_spec()
    pricings = {"real_fpmage_world_boss_blaze": real}
    for name in ("s1_cdr_table", "s2_cdr_current2_exact", "s2b_cdr_current2_no_exact", "s3_linear_cdr", "s4_cap_crit_damage_priced"):
        pricings[name] = cc.synth_pricing(name)
    cases = [
        ("real/grid", "real_fpmage_world_boss_blaze", grid),
        ("real/pity_extra", "real_fpmage_world_boss_blaze", pity_extra),
        ("real/cdr_companion", "real_fpmage_world_boss_blaze", cdc),
        ("s1/cdr_companion", "s1_cdr_table", cdc),
        ("s1/grid_every3", "s1_cdr_table", cc.every(grid, 3)),
        ("s2/cdr_companion", "s2_cdr_current2_exact", cdc),
        ("s2b/cdr_companion", "s2b_cdr_current2_no_exact", cdc),
        ("s3/cdr_companion", "s3_linear_cdr", cdc),
        ("s3/grid_every3", "s3_linear_cdr", cc.every(grid, 3, 1)),
        ("s4/pity_extra", "s4_cap_crit_damage_priced", pity_extra),
    ]
    return pricings, cases


def write_golden():
    t0 = time.time()
    roll_table, _mod = builder_roll_table()
    pricings, cases = build_cases()
    out_cases = []
    for name, pname, gear in cases:
        t = time.time()
        with tempfile.TemporaryDirectory() as td:
            rows = run_original(pricings[pname], gear, roll_table, td)
        print(f"{name}: {len(gear)} rows via the original in {time.time() - t:.1f}s", flush=True)
        out_cases.append(dict(name=name, pricing=pname, gear=[dict(g, lines=[list(x) for x in g["lines"]]) for g in gear], rows=rows))
    data = dict(meta=dict(original_sha256=sha256(ORIGINAL), generator="tests/golden/cubes_reference.py", milestones=cubes.CUBE_MILESTONES),
                pricings=pricings, cases=out_cases)
    GOLDEN.write_text(json.dumps(data))
    print(f"wrote {GOLDEN} ({GOLDEN.stat().st_size / 1e6:.2f} MB) in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    if "--write" in sys.argv:
        write_golden()
    elif "--check-source" in sys.argv:
        ok = json.loads(GOLDEN.read_text())["meta"]["original_sha256"] == sha256(ORIGINAL)
        print("original script unchanged since the golden was written" if ok else "src/potential_cubes_ev.py CHANGED since the golden was written")
        sys.exit(0 if ok else 1)
    else:
        print(__doc__)
