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
import factor_mode  # noqa: E402

FACTOR_MODE = factor_mode.pin("legacy")        # workbook-derived golden: skill levels clamp at 300 (engine/common/factors.py)

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


def test_ev_curve_for_every_cube_count():
    """``include_curve`` adds ``ev_pct_by_cubes`` (EV % after n cubes for EVERY n = 0..max_cubes, 6 significant digits): equals ``milestone_ev_pct`` at every preset
    milestone (within the rounding), starts at 0, never decreases, is the same on both backends, and is absent by default (the existing row shape is untouched)."""
    p = cubes.Pricing.from_dict(dict(baseline_dps=1e6, dps_per_unit=cubes.dps_per_unit_table(cc.SYNTH_RATES, level=150), cdr_current=0.0,
                                     cdr_table=cc.SYNTH_CDR_TABLE))
    gear = [dict(slot="head", potential_type="Potential", rarity="epic", pity=10, lines=[("Damage %", 9.0), ("Final Damage %", 3.0), (cubes.NONE_STAT, 0)]),
            dict(slot="boots", potential_type="Bonus Potential", rarity="rare", pity=3, lines=[]),
            dict(slot="ring", potential_type="Potential", rarity="mystic", pity=0, lines=[("Damage %", 40.0), ("Final Damage %", 20.0), ("Critical Damage %", 30.0)])]
    plain = cubes.recommend(gear, p, backend="python", sort=False)
    assert all("ev_pct_by_cubes" not in r for r in plain)
    runs = [cubes.recommend(gear, p, backend="python", sort=False, include_curve=True)]
    if cubes._np is not None:
        runs.append(cubes.recommend(gear, p, backend="numpy", sort=False, include_curve=True))
    for rows in runs:
        for r, q in zip(rows, plain):
            curve = r["ev_pct_by_cubes"]
            assert len(curve) == cubes.MAX_CUBES + 1 and curve[0] == 0.0
            assert all(curve[k + 1] >= curve[k] for k in range(len(curve) - 1))
            for n in cubes.CUBE_MILESTONES:
                assert close(curve[n], r["milestone_ev_pct"][n], 5.1e-6, 1e-12), (r["slot"], n, curve[n], r["milestone_ev_pct"][n])
            assert {k: v for k, v in r.items() if k != "ev_pct_by_cubes"} == q          # nothing else changes
    assert any(r["milestone_ev_pct"][100] > 0 for r in runs[0])
    short = cubes.recommend(gear[:1], p, backend="python", max_cubes=50, milestones=[5, 50], include_curve=True)[0]["ev_pct_by_cubes"]
    assert len(short) == 51
    assert cubes.ev_pct_curve([5.0, 7.0], 5.0, 0) == [0.0, 0.0]                           # zero baseline: no division


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


# ---- exact pricing of step / capped stats (Skill Cooldown Decrease, Buff Duration Increase %, Companion Summoning Time Increase %) --------------------------------------
def _live(content, typed_cdr=1.5, typed_buff=20.0, typed_sum=0.0, gear=None, companion="Blaze Wizard", **over):
    """(inputs, sensitivity result, pricing, the evaluated sensitivity base) of a live FP-Mage state; ``companion_potential_lines_pct`` = the gear's boots lines (the API's rule)."""
    from engine import sensitivity
    from engine.classes import fp_mage
    inp = fp_mage.defaults(content)
    inp.update(level=140, flat_attack=1_209_199, flat_int=60000, int_pct=150, luk=3000, crit_rate=80, crit_damage=150, damage=200, skill_cooldown_decrease=typed_cdr,
               buff_duration_increase_pct=typed_buff, companion_choice=companion, companion_level=10, companion_summon_time_increase_pct=typed_sum,
               companion_potential_lines_pct=cubes.companion_lines_pct(gear or []))
    inp.update(over)
    sens = sensitivity.run(fp_mage, dict(inp), which=["stats", "cdr", "summon_time"])
    return inp, sens, cubes.pricing_from_sensitivity(sens, dict(inp), fp_mage), sensitivity._Base(dict(inp), class_module=fp_mage)


def _g(base, key, total_with, total_without):
    """Exact factor of an Inputs stat going from ``total_without`` to ``total_with``: the full class model at both totals; boss / normal growth blended by the time
    weight (Summoning Time, Buff Duration, Cooldown Decrease)."""
    run = lambda x: base.block({key: x}, {}, rebuild=True, full_search=True)
    (t0, b0, n0), (t1, b1, n1) = run(total_without), run(total_with)
    return (1 - base.w) * b1 / b0 + base.w * n1 / n0


def _gear(**rows):
    """default gear with ``{slot}_{p|b}`` = (rarity, [lines]) rows replaced."""
    g = cubes.default_gear()
    for name, (rarity, lines) in rows.items():
        slot, kind = name.rsplit("_", 1)
        row = next(r for r in g if r["slot"] == slot and r["potential_type"] == ("Potential" if kind == "p" else "Bonus Potential"))
        row.update(rarity=rarity, lines=list(lines) + [(cubes.NONE_STAT, 0.0)] * (3 - len(lines)))
    return g


def _row(rows, slot, ptype="Potential"):
    return next(r for r in rows if r["slot"] == slot and r["potential_type"] == ptype)


def test_exact_companion_held_line_and_threshold():
    """The user's scenario (Breakthrough, Blaze Wizard, typed Summoning Time 10 INCLUDING a held boots line of 10): b0 = 0, the held line is worth the exact full-model
    f(10)/f(0) (not a step from the typed total), a candidate crossing 13.667 % is priced from b0 + the OTHER held lines, and the same candidate with no lines on the gear
    is priced from the typed 10 (the old, positive-only behaviour)."""
    S = cubes.COMPANION_STAT
    gear = _gear(boots_p=("unique", [(S, 10.0)]))
    inp, sens, p, base = _live("Breakthrough", typed_sum=10.0, gear=gear)
    assert p.companion.b0 == 0.0
    rows = cubes.recommend(gear, p, max_cubes=60, milestones=[5, 60])
    held = _row(rows, "boots")
    g_exact = _g(base, "companion_summon_time_increase_pct", 10.0, 0.0)
    assert close(1 + held["current_value"] / p.baseline_dps, g_exact, 1e-12, 0)
    assert close(held["row_loss"], p.baseline_dps * (1 - 1 / g_exact), 1e-12, 0) and held["line_loss"][0] == held["row_loss"] and held["line_loss"][1:] == [None, None]
    assert g_exact > 1.0 and held["row_loss"] > 0                                      # the lost DPS on removing the line is a real, positive amount
    # a candidate +5 on the Bonus row: 15 from the other row's 10 (crosses 13.667) vs 5 from nothing vs 25 from 20
    m = cubes.CubeModel(p)
    gain = lambda extra, other: m.combined_dps_gain([(S, extra)], None, other) / p.baseline_dps + 1
    assert close(gain(5.0, 10.0), _g(base, "companion_summon_time_increase_pct", 15.0, 10.0), 1e-12, 0)
    assert close(gain(5.0, 0.0), _g(base, "companion_summon_time_increase_pct", 5.0, 0.0), 1e-12, 0)
    assert close(gain(5.0, 20.0), _g(base, "companion_summon_time_increase_pct", 25.0, 20.0), 1e-12, 0)
    assert gain(5.0, 10.0) > gain(5.0, 0.0) > 1.0 and gain(5.0, 10.0) > gain(5.0, 20.0)       # the crossing step shows only from b0 + the held lines
    # nothing on the gear: the typed 10 is all "other sources" (b0 = 10) and the same candidates are priced on top of it
    inp0, sens0, p0, base0 = _live("Breakthrough", typed_sum=10.0, gear=_gear())
    assert p0.companion.b0 == 10.0
    r0 = _row(cubes.recommend(_gear(), p0, max_cubes=60, milestones=[5, 60]), "boots")
    assert r0["current_value"] == 0.0 and r0["row_loss"] == 0.0 and r0["line_loss"] == [None] * 3
    m0 = cubes.CubeModel(p0)
    assert close(m0.combined_dps_gain([(S, 5.0)], None, 0.0) / p0.baseline_dps + 1, _g(base0, "companion_summon_time_increase_pct", 15.0, 10.0), 1e-12, 0)
    # both tracks: the Bonus Potential row sees the Potential row's held line as its base and vice versa
    two = _gear(boots_p=("unique", [(S, 8.0)]), boots_b=("epic", [(S, 5.0)]))
    inp2, sens2, p2, base2 = _live("Breakthrough", typed_sum=13.0, gear=two)
    rows2 = cubes.recommend(two, p2, max_cubes=60, milestones=[5, 60])
    assert p2.companion.b0 == 0.0
    assert close(1 + _row(rows2, "boots", "Potential")["current_value"] / p2.baseline_dps, _g(base2, "companion_summon_time_increase_pct", 13.0, 5.0), 1e-12, 0)
    assert close(1 + _row(rows2, "boots", "Bonus Potential")["current_value"] / p2.baseline_dps, _g(base2, "companion_summon_time_increase_pct", 13.0, 8.0), 1e-12, 0)
    # held lines above the typed total: noted, b0 clamps at 0
    inp3, sens3, p3, _b3 = _live("Breakthrough", typed_sum=6.0, gear=two)
    m3 = cubes.CubeModel(p3)
    cubes.recommend(two, p3, max_cubes=20, milestones=[5], model=m3)
    assert p3.companion.b0 == 0.0 and {"companion_lines_exceed_inputs:boots/Potential", "companion_lines_exceed_inputs:boots/Bonus Potential"} <= m3.notes
    # pure boss content: the factor is the plain Total ratio, so the removal loss is exactly Total(10) - Total(0) of the real model
    from engine.classes import fp_mage
    wb_gear = _gear(boots_p=("unique", [(S, 10.0)]))
    wb_inp, _s, wb_p, _bb = _live("World Boss", typed_sum=10.0, gear=wb_gear)
    wb_row = _row(cubes.recommend(wb_gear, wb_p, max_cubes=20, milestones=[5]), "boots")
    t10, t0 = (fp_mage.compute(dict(wb_inp, companion_summon_time_increase_pct=x))["total_dps"] for x in (10.0, 0.0))
    assert close(wb_row["row_loss"], t10 - t0, 1e-9, 0), (wb_row["row_loss"], t10 - t0)


def test_exact_cdr_and_buff_duration_lines():
    """Skill Cooldown Decrease (hat) and Buff Duration Increase % (belt) on both tracks: each row is priced on the real model at b0 + the other rows' lines, the typed
    total (off the 0.5 s table grid, past its 5.0 s end) included, instead of interpolating the milestone table / the linear rate."""
    C, B = cubes.CDR_STAT, cubes.BUFF_STAT
    gear = _gear(head_p=("legendary", [(C, 1.5), ("Damage %", 15.0), (C, 1.0)]), head_b=("unique", [(C, 1.0), (C, 0.5)]),
                 belt_p=("epic", [(B, 5.0), ("Damage %", 9.0), (B, 5.0)]), belt_b=("unique", [(B, 8.0)]))
    inp, sens, p, base = _live("Breakthrough", typed_cdr=4.2, typed_buff=35.0, gear=gear)
    assert set(p.exact) == {C, B} and p.exact[C].typed == 4.2 and p.exact[B].typed == 35.0
    rows = cubes.recommend(gear, p, max_cubes=60, milestones=[5, 60])
    key = {C: "skill_cooldown_decrease", B: "buff_duration_increase_pct"}
    for slot, ptype, stat, own in (("head", "Potential", C, 2.5), ("head", "Bonus Potential", C, 1.5), ("belt", "Potential", B, 10.0), ("belt", "Bonus Potential", B, 8.0)):
        typed = p.exact[stat].typed
        row = _row(rows, slot, ptype)
        # the Damage % line (linear) multiplies on top: strip it out by pricing the stat's own lines alone
        only = [(s, v) for s, v in row["lines"] if s == stat]
        m = cubes.CubeModel(p)
        ebases = m.row_exact_bases(dict(row, lines=[tuple(x) for x in row["lines"]]), [dict(r, lines=[tuple(x) for x in r["lines"]]) for r in rows])
        assert close(ebases[stat], typed - own, 1e-12, 1e-12)
        g_own = 1 + m.combined_dps_gain(only, None, 0.0, ebases) / p.baseline_dps
        assert close(g_own, _g(base, key[stat], typed, typed - own), 1e-12, 0), (slot, ptype)
    # the table / rate it replaces is NOT exact here (off-grid typed total, 4.2 - 1.5 = 2.7 s between steps, 35 % buff past the linear regime)
    p_old = cubes.pricing_from_sensitivity(sens, dict(inp), exact_stats=None)
    old = cubes.recommend(gear, p_old, max_cubes=60, milestones=[5, 60])
    assert abs(_row(old, "belt")["current_value"] - _row(rows, "belt")["current_value"]) > 1e-3 * p.baseline_dps
    # past the table's end: 7 s of Cooldown Decrease all on the hat (typed 7, three 2 s / 1.5 s lines + ...) is the real model, not the last slope continued
    big = _gear(head_p=("mystic", [(C, 2.0), (C, 2.0), (C, 2.0)]), head_b=("mystic", [(C, 1.0)]))
    inp_b, sens_b, p_b, base_b = _live("Breakthrough", typed_cdr=7.0, gear=big)
    rows_b = cubes.recommend(big, p_b, max_cubes=20, milestones=[5], only=lambda r: r["slot"] == "head")
    assert close(1 + _row(rows_b, "head")["current_value"] / p_b.baseline_dps, _g(base_b, "skill_cooldown_decrease", 7.0, 1.0), 1e-12, 0)
    # held lines above the typed total: the old note key stays, b0 clamps at 0 (the row's base = the other rows' lines)
    inp_c, sens_c, p_c, base_c = _live("Breakthrough", typed_cdr=1.0, gear=gear)
    m_c = cubes.CubeModel(p_c)
    cubes.recommend(gear, p_c, max_cubes=20, milestones=[5], model=m_c, only=lambda r: r["slot"] == "head")
    assert {"cdr_lines_exceed_inputs:head/Potential", "cdr_lines_exceed_inputs:head/Bonus Potential"} <= m_c.notes


def test_exact_stats_leave_everything_else_alone():
    """Rows without a step-stat line / a roll of one are priced exactly as before; with nothing held and a typed total on the table grid, an exact curve reproduces the
    milestone table in pure-boss content (where the Total ratio is the weighted ratio); linear stats and golden-pinned numbers do not move."""
    C = cubes.CDR_STAT
    gear = _gear(ring_p=("legendary", [("Damage %", 12.0), ("Final Damage %", 6.0)]), cape_p=("epic", [("Critical Damage %", 15.0)]),
                 head_p=("epic", [("Damage %", 12.0)]))
    inp, sens, p, base = _live("World Boss", typed_cdr=1.5, gear=gear)
    p_old = cubes.pricing_from_sensitivity(sens, dict(inp), exact_stats=None)
    new = cubes.recommend(gear, p, max_cubes=40, milestones=[5, 40], only=lambda r: r["slot"] in ("ring", "cape"), sort=False)
    old = cubes.recommend(gear, p_old, max_cubes=40, milestones=[5, 40], only=lambda r: r["slot"] in ("ring", "cape"), sort=False)
    strip = lambda rows: [{k: v for k, v in r.items() if not k.startswith(("line_loss", "row_loss"))} for r in rows]
    assert strip(new) == strip(old) and len(new) == 4
    # nothing held, typed total on the 0.5 s grid: the exact curve == a milestone table that covers every reachable total (World Boss: weighted ratio == Total ratio);
    # the table is interpolated exactly on its grid, so the two pricings must agree to rounding (the stock 5 s table would extrapolate past its end instead)
    wide = [(x / 2, base.block({"skill_cooldown_decrease": x / 2}, {}, rebuild=True, full_search=True)[0]) for x in range(1, 25)]
    p_grid = cubes.Pricing(p.baseline_dps, p.dps_per_unit, p.cdr_current, wide, None, p.companion, {k: v for k, v in p.exact.items() if k != C})
    hat_new = cubes.recommend(gear, p, max_cubes=40, milestones=[5, 40], only=lambda r: r["slot"] == "head", sort=False)
    hat_old = cubes.recommend(gear, p_grid, max_cubes=40, milestones=[5, 40], only=lambda r: r["slot"] == "head", sort=False)
    for a, b in zip(hat_new, hat_old):
        assert close(a["current_value"], b["current_value"], 1e-11, 1e-3) and a["smallest_n"] == b["smallest_n"]
        for n in (5, 40):
            assert close(a["milestone_ev"][n], b["milestone_ev"][n], 1e-9, 1e-3), (a["slot"], a["potential_type"], n)
    # model evaluations stay small (memoised per total) for a full 30-row sheet
    full = cubes.default_gear()
    for r in full:
        r.update(rarity="legendary")
    _i, _s, pf, _b = _live("Breakthrough", typed_cdr=1.5, typed_buff=20.0, typed_sum=0.0, gear=[])
    cubes.recommend(full, pf, max_cubes=30, milestones=[5, 30])
    assert 0 < pf.model_evaluations() < 400, pf.model_evaluations()


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
    for fn in (test_roll_table_matches_builder, test_separate_pity_caps, test_dps_per_unit_table_matches_workbook, test_properties, test_ev_curve_for_every_cube_count,
               test_adapter_from_sensitivity, test_exact_companion_held_line_and_threshold, test_exact_cdr_and_buff_duration_lines, test_exact_stats_leave_everything_else_alone):
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
