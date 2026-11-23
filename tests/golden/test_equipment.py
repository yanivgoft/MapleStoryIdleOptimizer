#!/usr/bin/env python3
"""Golden test: ``engine.equipment`` against the REAL ``Equipment Compare`` sheet of the builder.

``tests/golden/tiny_golden.json`` (``tiny_reference.py``) freezes what the ``formulas`` package computed for that sheet (built by
``build_equipment_compare_sheet``) in a tiny standalone workbook with stub Total DPS / Sensitivity!H / crit-rate inputs: 10 cases of 6 + 6 lines (duplicate
stats, a dropdown line on "Attack (flat)", "(none)" lines, Critical Rate with the cap rule in all its states).  Every per-line gain / first / group / factor,
both totals / percentages and the delta are compared (rel 1e-9).  Plain ``python3`` runnable, also pytest-collectable.

    python3 tests/golden/test_equipment.py [-v] [--rtol 1e-12]
"""
import argparse
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from engine import equipment  # noqa: E402

TINY = HERE / "tiny_golden.json"


def close(a, b, rtol, atol=1e-9):
    if a == b:
        return True
    return abs(a - b) <= rtol * max(abs(a), abs(b)) + atol


def engine_case(case, res):
    arts = res["artifacts"]
    ring, book = bool(arts["ring_of_cycles"]["equipped"]), bool(arts["book_of_ancient"]["equipped"])
    return equipment.compare(case["equip"]["current"], case["equip"]["new"], case["H"], case["total"], crit_rate_total=case["crit_rate"] + case["agg_crit"],
                             ring_of_cycles_equipped=ring, book_of_ancient_equipped=book)


def run(rtol=1e-9, verbose=False):
    t = json.loads(TINY.read_text())
    n, bad = 0, []
    for cid, case in t["cases"].items():
        res = t["results"][cid]["equip"]
        out = engine_case(case, t["results"][cid])
        for side in ("current", "new"):
            g, e = res[side], out[side]
            for i, (gr, er) in enumerate(zip(g["rows"], e["rows"])):
                for k in ("gain", "group", "factor"):
                    n += 1
                    if not close(float(gr[k]), er[k], rtol, 1e-9):
                        bad.append((cid, side, i, k, gr[k], er[k]))
                n += 1
                if bool(gr["first"]) != er["first"]:
                    bad.append((cid, side, i, "first", gr["first"], er["first"]))
            for k in ("total_gain", "pct"):
                n += 1
                if not close(float(g[k]), e[k], rtol, 1e-9):
                    bad.append((cid, side, k, g[k], e[k]))
        n += 1
        if not close(res["delta"], out["delta_pct"], rtol, 1e-9):
            bad.append((cid, "delta", res["delta"], out["delta_pct"]))
        if verbose:
            print(f"  {cid}: delta {out['delta_pct']:+.6f}%  ({out['better']})")
    return len(t["cases"]), n, bad


def test_tables_match_builder():
    """The dropdown list / stat -> sweep-key map is the builder's own."""
    sys.path.insert(0, str(HERE.parents[1] / "src"))
    spec = importlib.util.spec_from_file_location("build_fp_mage_workbook_equip_test", HERE.parents[1] / "src" / "build_fp_mage_workbook.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert equipment.STAT_TO_SWEEP_KEY == mod.EQUIP_COMPARE_STAT_TO_SWEEP_KEY
    assert equipment.DROPDOWN_STATS == mod.EQUIP_COMPARE_DROPDOWN_STATS and len(equipment.DROPDOWN_STATS) == 21
    assert equipment.N_LINES == len(mod.EQUIP_COMPARE_LINE_ROWS)


def test_semantics():
    """Hand-derived cases: same stat adds, different stats multiply (1.01 x 1.01 - 1 = 2.0201%), Attack merges, (none) / unknown stats are 0."""
    total = 1_000_000.0
    rates = {"damage": 10_000.0, "final_damage": 10_000.0, "flat_attack": 1.0, "crit_rate": 5_000.0, "crit_damage": 7_000.0, "min_damage": 2_000.0}
    # two different stats worth 1% each compound: 1.01 * 1.01 - 1
    out = equipment.compare({"attack": 0, "lines": []}, {"attack": 0, "lines": [("Damage %", 1), ("Final Damage %", 1)]}, rates, total)
    assert close(out["new"]["pct"], (1.01 * 1.01 - 1) * 100, 1e-12) and out["current"]["pct"] == 0 and out["better"] == "new"
    # two lines of the same stat add: 5 + 5 = 10% of Damage
    out = equipment.compare({"attack": 0, "lines": []}, {"attack": 0, "lines": [("Damage %", 5), ("Damage %", 5)]}, rates, total)
    assert close(out["new"]["pct"], 10.0, 1e-12) and [r["first"] for r in out["new"]["rows"]] == [True, True, False, False, False, False]
    # a dropdown line on Attack (flat) merges into the fixed Attack line: 3000 + 2000 attack = 5000 x 1.0 DPS = 0.5%
    out = equipment.compare({"attack": 0, "lines": []}, {"attack": 3000, "lines": [("Attack (flat)", 2000)]}, rates, total)
    assert close(out["new"]["pct"], 0.5, 1e-12) and out["new"]["rows"][1]["first"] is False
    # (none) and stats without a sweep (Defense (flat)) are worth 0
    out = equipment.compare({"attack": 0, "lines": [("(none)", 99), ("Defense (flat)", 99)]}, {"attack": 0, "lines": []}, rates, total)
    assert out["current"]["pct"] == 0 and out["better"] == "equal"
    # the crit-rate cap rule: capped (>= 100, no ring / book) prices Critical Rate like Critical Damage
    base = dict(current={"attack": 0, "lines": []}, new={"attack": 0, "lines": [("Critical Rate %", 4)]}, rates=rates, total_dps=total)
    assert close(equipment.compare(**base, crit_rate_total=99.99)["new"]["pct"], 2.0, 1e-12)
    assert close(equipment.compare(**base, crit_rate_total=100)["new"]["pct"], 2.8, 1e-12)
    assert close(equipment.compare(**base, crit_rate_total=100, ring_of_cycles_equipped=True)["new"]["pct"], 2.0, 1e-12)
    assert close(equipment.compare(**base, crit_rate_total=100, book_of_ancient_equipped=True)["new"]["pct"], 2.0, 1e-12)
    # more than 5 lines are ignored, a zero Total DPS is an error
    assert len(equipment.compare({"attack": 1, "lines": [("Damage %", 1)] * 8}, {"attack": 1, "lines": []}, rates, total)["current"]["rows"]) == 6
    try:
        equipment.compare({"attack": 1}, {"attack": 1}, rates, 0)
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_golden():
    n_cases, n, bad = run()
    assert not bad, bad[:5]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rtol", type=float, default=1e-9)
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()
    test_tables_match_builder()
    test_semantics()
    print("ok: tables == builder, hand-derived semantics")
    n_cases, n, bad = run(a.rtol, a.verbose)
    for b in bad[:25]:
        print("  ", b)
    print(f"{'OK' if not bad else 'FAIL'}: {n_cases} cases, {n} values vs the Equipment Compare formulas (rtol {a.rtol:g}), {len(bad)} differences")
    sys.exit(1 if bad else 0)
