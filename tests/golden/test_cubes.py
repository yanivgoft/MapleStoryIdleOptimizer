#!/usr/bin/env python3
"""Golden test: ``engine.cubes`` (the cube optimizer core) against the ORIGINAL ``src/potential_cubes_ev.py`` logic.

``tests/golden/cubes_golden.json`` freezes what the original's ``main()`` computed (``cubes_reference.py``: its functions executed unmodified on constructed
gear + pricing, the same data it would have read from a workbook) for ~490 (slot, potential type) rows over 10 cases: all 15 slots x both potential types x all
6 rarities x rotating pity values, pity edge values, rows holding Skill Cooldown Decrease / Companion Summoning Time lines (own baselines), a real FP-Mage
pricing built by the adapter (companion model tabulated) and synthetic pricing tables (CDR table / linear CDR / CDR baseline below the table with and without
the exact re-evaluation).  Plain ``python3`` runnable, also pytest-collectable.

    python3 tests/golden/test_cubes.py                  # numpy backend on every row, pure-Python backend on every 6th row; rel 1e-9
    python3 tests/golden/test_cubes.py --full           # both backends on every row
    python3 tests/golden/test_cubes.py --rtol 1e-12 -v

Also checked: the engine's roll table == the builder's CubeData rows; the separate Potential / Bonus Potential pity caps (CLAUDE.md item 17); the
stat -> DPS-per-unit table == the CubeData!J:K formulas of the real builder (tiny workbook golden, incl. the crit-rate cap rule, CLAUDE.md item 13, and the
Ring of Cycles / Book of Ancient exception); the adapter ``pricing_from_sensitivity`` (live engine run); trace / probability monotonicity.
"""
import argparse
import importlib.util
import json
import math
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))
import cubes_cases as cc  # noqa: E402
from engine import cubes  # noqa: E402

GOLDEN = HERE / "cubes_golden.json"
TINY = HERE / "tiny_golden.json"
_DATA = {}


def golden():
    if "g" not in _DATA:
        _DATA["g"] = json.loads(GOLDEN.read_text())
    return _DATA["g"]


def close(a, b, rtol, atol):
    if a == b:
        return True
    if a is None or b is None:
        return False
    return abs(a - b) <= rtol * max(abs(a), abs(b)) + atol


def compare_rows(engine_rows, golden_rows, base, rtol):
    """List of (what, golden, engine) differences.  Cube counts are exact integers; DPS values rel ``rtol`` (+ 1e-12 x baseline absolute)."""
    bad = []
    if len(engine_rows) != len(golden_rows):
        return [("row count", len(golden_rows), len(engine_rows))]
    atol = 1e-12 * base
    for i, (e, g) in enumerate(zip(engine_rows, golden_rows)):
        tag = f"{i}:{g['slot']}/{g['potential_type']}/{g['rarity']}/{g['pity']:g}"
        for k in ("slot", "potential_type", "rarity", "smallest_n", "n_for_50pct", "n_for_75pct"):
            if e[k] != g[k]:
                bad.append((f"{tag} {k}", g[k], e[k]))
        if e["pity"] != g["pity"]:
            bad.append((f"{tag} pity", g["pity"], e["pity"]))
        if not close(e["current_value"], g["current_value"], rtol, atol):
            bad.append((f"{tag} current_value", g["current_value"], e["current_value"]))
        if not close(e["current_value_pct"], g["current_value_pct"], rtol, 1e-12):
            bad.append((f"{tag} current_value_pct", g["current_value_pct"], e["current_value_pct"]))
        for n in cubes.CUBE_MILESTONES:
            if not close(e["milestone_ev"][n], g["milestone_ev"][str(n)], rtol, atol):
                bad.append((f"{tag} EV@{n}", g["milestone_ev"][str(n)], e["milestone_ev"][n]))
            if not close(e["milestone_ev_pct"][n], g["milestone_ev_pct"][str(n)], rtol, 1e-12):
                bad.append((f"{tag} EV%@{n}", g["milestone_ev_pct"][str(n)], e["milestone_ev_pct"][n]))
    return bad


def run_golden(backend, stride, rtol=1e-9, verbose=False):
    """Engine (``backend``) on every ``stride``-th row of every case; rows are compared one by one (each row's own state, so subsets stay valid because the
    only cross-row coupling - the companion baseline of the OTHER rows - is fixed by the full gear list passed in)."""
    g = golden()
    n_rows, bad_all = 0, {}
    for case in g["cases"]:
        spec = g["pricings"][case["pricing"]]
        pricing = cc.pricing_from_spec(spec)
        t = time.time()
        gear = case["gear"]
        sel = case["rows"]
        only = None
        if stride > 1:
            # every stride-th golden row (+ every row holding a CDR / summoning-time line); the other rows still define the cross-row baselines
            special = {cubes.CDR_STAT, cubes.COMPANION_STAT}
            ident = lambda r: (r["slot"], r["potential_type"], r["rarity"], float(r["pity"]))
            keep = {ident(r) for r in sel[::stride]} | {ident(r) for r in gear if any(l[0] in special for l in r["lines"])}
            only = {i for i, r in enumerate(gear) if ident(r) in keep}
            sel = [r for r in sel if ident(r) in keep]
        rows = cubes.recommend(gear, pricing, backend=backend, only=only)
        bad = compare_rows(rows, sel, spec["baseline_dps"], rtol)
        n_rows += len(rows)
        if bad:
            bad_all[case["name"]] = bad
        if verbose:
            print(f"  {case['name']:24s} {backend:6s} {len(rows):4d} rows  {time.time() - t:5.1f}s  {'OK' if not bad else f'{len(bad)} differences'}", flush=True)
    return n_rows, bad_all


def test_roll_table_matches_builder():
    """The engine's roll table == the CubeData rows the builder emits (slot specials, weights, order)."""
    sys.path.insert(0, str(HERE.parents[1] / "src"))
    spec = importlib.util.spec_from_file_location("build_fp_mage_workbook_cubes_test", HERE.parents[1] / "src" / "build_fp_mage_workbook.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    table = {}
    for slot, rarity, line, entry in mod._iter_potential_line_entries():
        table.setdefault((slot, rarity, line), []).append((entry["stat"], float(entry["value"]), float(entry["weight"])))
    assert table == cubes.roll_table()
    assert list(mod.CUBE_SLOTS) == cubes.CUBE_SLOTS and list(mod.RARITY_ORDER) == cubes.RARITY_ORDER
    assert list(mod.CUBE_MILESTONES) == cubes.CUBE_MILESTONES
    assert sorted(mod.ALL_POTENTIAL_STATS) == cubes.all_potential_stats()
    assert mod.RARITY_UPGRADE_RATES == cubes.rarity_rates()


def test_separate_pity_caps():
    """CLAUDE.md item 17: Potential and Bonus Potential have different pity caps at every tier except legendary; the engine uses the matching table."""
    r = cubes.rarity_rates()
    assert [r["Potential"][t]["max"] for t in cubes.RARITY_ORDER[:5]] == [30, 60, 120, 333, 714]
    assert [r["Bonus Potential"][t]["max"] for t in cubes.RARITY_ORDER[:5]] == [42, 75, 150, 417, 714]
    p = cubes.Pricing.from_dict(dict(baseline_dps=1e6, dps_per_unit=cubes.dps_per_unit_table(cc.SYNTH_RATES, level=150)))
    row = dict(slot="cape", rarity="normal", pity=0, lines=[])
    out = {pt: cubes.recommend([dict(row, potential_type=pt)], p, backend="python")[0] for pt in cubes.POTENTIAL_TYPES}
    # same pricing, same state: the longer Bonus Potential pity must change the result (it reaches higher tiers later)
    assert out["Potential"]["milestone_ev"][1000] != out["Bonus Potential"]["milestone_ev"][1000]
    # a pity above the Potential cap is invalid there but valid for Bonus Potential (clamped for the former, never an IndexError)
    hi = cubes.recommend([dict(row, potential_type="Potential", pity=40), dict(row, potential_type="Bonus Potential", pity=40)], p, backend="python", sort=False)
    assert hi[0]["milestone_ev"][100] == cubes.recommend([dict(row, potential_type="Potential", pity=29)], p, backend="python")[0]["milestone_ev"][100]


def test_dps_per_unit_table_matches_workbook():
    """cubes.dps_per_unit_table == CubeData!K (the builder's dps_per_unit_expr for every stat) evaluated with ``formulas`` on stub Sensitivity rates."""
    t = json.loads(TINY.read_text())
    checked = 0
    for cid, case in t["cases"].items():
        res = t["results"][cid]
        arts = res["artifacts"]
        ring = bool(arts["ring_of_cycles"]["equipped"])
        book = bool(arts["book_of_ancient"]["equipped"])
        table = cubes.dps_per_unit_table(case["H"], level=case["level"], crit_rate_total=case["crit_rate"] + case["agg_crit"],
                                         ring_of_cycles_equipped=ring, book_of_ancient_equipped=book)
        for stat, value in res["cube_k"].items():
            assert close(table[stat], float(value), 1e-12, 1e-9), (cid, stat, table[stat], value)
            checked += 1
        assert set(table) == set(res["cube_k"])
    # the crit-rate cap rule, spelled out (CLAUDE.md item 13): FULL live total (Inputs + artifact bucket), >= 100, unless Ring of Cycles / Book of Ancient
    H = {"crit_rate": 111.0, "crit_damage": 222.0}
    f = lambda **kw: cubes.dps_per_unit_table(H, **kw)["Critical Rate %"]
    assert f(crit_rate_total=99.9) == 111.0 and f(crit_rate_total=100) == 222.0 and f(crit_rate_total=250) == 222.0
    assert f(crit_rate_total=250, ring_of_cycles_equipped=True) == 111.0 and f(crit_rate_total=250, book_of_ancient_equipped=True) == 111.0
    assert checked > 200


def test_properties():
    """Optimal-stopping value never decreases with more cubes; the improvement probability never decreases and ends at 1 - tiny; both backends agree."""
    p = cubes.Pricing.from_dict(dict(baseline_dps=1e6, dps_per_unit=cubes.dps_per_unit_table(cc.SYNTH_RATES, level=150), cdr_current=0.0,
                                     cdr_table=cc.SYNTH_CDR_TABLE))
    gear = [dict(slot="head", potential_type="Potential", rarity="epic", pity=10, lines=[("Damage %", 9.0), ("Final Damage %", 3.0), (cubes.NONE_STAT, 0)]),
            dict(slot="boots", potential_type="Bonus Potential", rarity="rare", pity=3, lines=[])]
    a = cubes.recommend(gear, p, backend="python", include_trace=True, sort=False)
    b = cubes.recommend(gear, p, backend="numpy", include_trace=True, sort=False) if cubes._np is not None else a
    for ra, rb in zip(a, b):
        tr, pa = ra["trace"], ra["prob_any"]
        assert tr[0] == ra["current_value"] and all(tr[k + 1] >= tr[k] for k in range(len(tr) - 1))
        assert all(pa[k + 1] >= pa[k] - 1e-15 for k in range(len(pa) - 1)) and 0.999 < pa[-1] <= 1.0 + 1e-12
        assert tr == rb["trace"] and all(close(x, y, 1e-12, 1e-15) for x, y in zip(pa, rb["prob_any"]))
        assert ra["smallest_n"] is None or tr[ra["smallest_n"]] > ra["current_value"] and (ra["smallest_n"] == 1 or tr[ra["smallest_n"] - 1] <= ra["current_value"])
    # sort order: Potential before Bonus Potential, then smallest_n ascending, never-positive last
    s = cubes.recommend(gear + cubes.default_gear(), p, backend="python")
    keys = [(0 if r["potential_type"] == "Potential" else 1, r["smallest_n"] if r["smallest_n"] is not None else 10 ** 9) for r in s]
    assert keys == sorted(keys)
    row = cubes.csv_row(s[0])
    assert len(row) == len(cubes.CSV_COLUMNS) == 9 + 2 * len(cubes.CUBE_MILESTONES)


def test_adapter_from_sensitivity():
    """``pricing_from_sensitivity`` on a live FP-Mage sensitivity run: rates, CDR curve, companion b0 / model, crit-cap and ring / book rules."""
    from engine import sensitivity
    from engine.classes import fp_mage
    inp = fp_mage.defaults("World Boss")
    inp.update(level=140, flat_attack=1_209_199, flat_int=60000, int_pct=150, luk=3000, crit_rate=80, crit_damage=150, damage=200, skill_cooldown_decrease=1.5,
               companion_choice="Blaze Wizard", companion_level=10, companion_summon_time_increase_pct=20, companion_potential_lines_pct=12)
    sens = sensitivity.run(fp_mage, inp, which=["stats", "cdr", "summon_time"])
    p = cubes.pricing_from_sensitivity(sens, inp)
    rates = cubes.sweep_rates(sens)
    assert p.baseline_dps == sens["baseline_total"] and p.cdr_current == 1.5
    assert p.dps_per_unit["Damage %"] == rates["damage"] and p.dps_per_unit["Main Stat Per Level"] == rates["flat_int"] * 140
    assert p.dps_per_unit["Main Stat % per 4 Levels"] == rates["int_pct"] * 35 and p.dps_per_unit["Critical Rate %"] == rates["crit_rate"]
    assert p.dps_per_unit["Str %"] == 0.0 and p.dps_per_unit["Skill Cooldown Decrease (seconds)"] == rates["skill_cooldown_decrease"]
    xs = [x for x, _ in p.cdr_points]
    assert 1.5 in xs and dict(p.cdr_points)[1.5] == sens["baseline_total"] and all(r["cdr"] in xs for r in sens["cdr"]["rows"])
    c = p.companion
    assert c is not None and c.b0 == sens["summon_time"]["b0"] and c.factor(0, 0) == 1.0 and c.factor(20, 0) > 1.0
    assert abs(c.at(0)["comp_blend_dps"] - sens["summon_time"]["rows"][0]["companion_dps"]) <= 1e-9 * max(1.0, c.at(0)["comp_blend_dps"])
    assert p.dps_per_unit["Companion Summoning Time Increase %"] > 0
    # crit cap: raise the crit total above 100 -> priced as Critical Damage; Ring of Cycles equipped -> the literal rate again
    inp2 = dict(inp, crit_rate=100)
    sens2 = sensitivity.run(fp_mage, inp2, which=["stats", "cdr"])
    p2 = cubes.pricing_from_sensitivity(sens2, inp2, cdr_exact=None)
    assert p2.dps_per_unit["Critical Rate %"] == cubes.sweep_rates(sens2)["crit_damage"]
    inp3 = dict(inp2, artifacts=[{"key": "ring_of_cycles", "star": 5}])
    sens3 = sensitivity.run(fp_mage, inp3, which=["stats", "cdr"])
    p3 = cubes.pricing_from_sensitivity(sens3, inp3, cdr_exact=None)
    assert p3.dps_per_unit["Critical Rate %"] == cubes.sweep_rates(sens3)["crit_rate"]
    # end to end: a few rows priced with the real pricing
    gear = cubes.default_gear()
    gear[0].update(rarity="legendary", pity=0, lines=[(cubes.CDR_STAT, 1.5), ("Damage %", 15.0), (cubes.NONE_STAT, 0)])
    rows = cubes.recommend(gear[:2] + [g for g in gear if g["slot"] == "boots"], p, max_cubes=100, milestones=[5, 100])
    assert rows and all(r["milestone_ev"][100] >= 0 for r in rows)


def test_golden(stride=6):
    n, bad = run_golden("python", stride)
    assert not bad, {k: v[:5] for k, v in bad.items()}
    if cubes._np is not None:
        n, bad = run_golden("numpy", 1)
        assert not bad, {k: v[:5] for k, v in bad.items()}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rtol", type=float, default=1e-9)
    ap.add_argument("--full", action="store_true", help="pure-Python backend on every row too")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()
    t0 = time.time()
    for fn in (test_roll_table_matches_builder, test_separate_pity_caps, test_dps_per_unit_table_matches_workbook, test_properties, test_adapter_from_sensitivity):
        fn()
        print(f"ok: {fn.__name__}", flush=True)
    failed = False
    plan = [("python", 1 if a.full else 6)] + ([("numpy", 1)] if cubes._np is not None else [])
    for backend, stride in plan:
        n, bad = run_golden(backend, stride, a.rtol, a.verbose)
        for case, diffs in bad.items():
            for what, gv, ev in diffs[:10]:
                print(f"  {case}: {what}: original {gv!r} engine {ev!r}")
        print(f"{'FAIL' if bad else 'OK'}: backend {backend}: {n} rows over {len(golden()['cases'])} cases vs the original script (rtol {a.rtol:g}), "
              f"{sum(len(v) for v in bad.values())} differences")
        failed |= bool(bad)
    print(f"{time.time() - t0:.0f}s")
    sys.exit(1 if failed else 0)
