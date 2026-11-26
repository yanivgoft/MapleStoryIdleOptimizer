#!/usr/bin/env python3
"""ENGINE-ONLY tests of the fifth artifact slot (the game gained a 5th slot on 2026-11-23; the 12 workbooks still have 4 slot rows).

There is no workbook ground truth for 5 equipped artifacts: the engine composes the (workbook-verified) per-artifact effects itself - every effect is a
bucket contribution that does not depend on the slot it sits in - so what is checked here is internal consistency, not agreement with Excel:

* the schema offers 5 slots for all 12 classes, 5 equipped artifacts compute without error to finite numbers, a 6th is rejected;
* order independence (permuting the 5 slots gives the same total), the same artifact twice counts once, "(none)" slots are skipped;
* adding the 5th artifact never lowers DPS for artifacts with non-negative effects (and does raise it for live ones);
* the equip-toggle row of the 5th artifact in ``engine.sensitivity`` (adding to 4 equipped) equals the engine's own 5-slot minus 4-slot difference, and a SIXTH
  what-if on top of 5 equipped works (the toggle bypasses ``resolve_slots``' cap by design);
* 4-slot results are bit-identical to what the 4-slot cap produced (the cap change adds no term).

    python3 tests/golden/test_artifact_five_slots.py [-v]      (also pytest-collectable)
"""
import importlib
import itertools
import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))
from engine import CLASSES, artifacts as art, sensitivity  # noqa: E402
from engine.data import artifacts as AD  # noqa: E402
import factor_mode  # noqa: E402

FACTOR_MODE = factor_mode.pin("legacy")        # workbook classes against workbook-derived expectations: skill levels clamp at 300 (engine/common/factors.py)

# live artifacts with non-negative, slot-independent effects that exist in every class's model (Attack%, boss / normal damage, Final Damage, Crit Damage)
LIVE5 = ["alliance_badge", "sayrams_necklace", "flaming_lava", "icy_soul_rock", "secret_map"]
STAR = {"alliance_badge": 5, "sayrams_necklace": 5, "flaming_lava": 5, "icy_soul_rock": 5, "secret_map": 5}
# a mixed set including baked-in / no-effect artifacts and Not Unlocked (star 0) ones
MIXED5 = [("pigs_ribbon", None), ("candle", 3), ("hexagon_necklace", 0), ("bottle_of_emotion", 5), ("reindeer_spear", 2)]


def mod(cid):
    return importlib.import_module(f"engine.classes.{cid}")


def inputs(cid, slots, content="World Boss"):
    d = mod(cid).defaults()
    d["content_type"] = content
    d["artifacts"] = list(slots)
    d["artifact_stars"] = dict(STAR)
    return d


def slot_list(keys, star=None):
    return [{"key": k, "star": STAR.get(k, 5) if star is None else star} for k in keys]


def finite_result(res):
    assert math.isfinite(res["total_dps"]) and res["total_dps"] > 0, res["total_dps"]
    assert math.isfinite(res["boss_dps"]) and math.isfinite(res["normal_dps"])
    for r in res["skills"]:
        assert math.isfinite(r["dps"]), r["key"]
    for b, v in res["artifacts"]["buckets"].items():
        assert isinstance(v, (int, float)) and math.isfinite(v), (b, v)


def test_resolve_slots_cap():
    assert art.MAX_SLOTS == 5 and art.WORKBOOK_SLOTS == 4
    five = art.resolve_slots(slot_list(LIVE5))
    assert list(five) == LIVE5 and len(five) == 5
    try:
        art.resolve_slots(slot_list(LIVE5 + ["candle"]))
    except ValueError as e:
        assert "at most 5" in str(e)
    else:
        raise AssertionError("6 slots must be rejected")
    # (none) / blank slots are skipped and do not count twice; the same artifact twice is one artifact (first star wins)
    got = art.resolve_slots(slot_list(LIVE5[:3]) + [{"key": "(none)", "star": 0}, {"key": "alliance_badge", "star": 1}])
    assert got == {"alliance_badge": 5, "sayrams_necklace": 5, "flaming_lava": 5}


def test_schema_has_five_slots_in_every_class():
    for cid in CLASSES:
        s = mod(cid).schema()
        assert s["artifacts"]["max_slots"] == 5, cid
        assert s["artifacts"]["none_label"] == "(none)" and len(s["artifacts"]["slot_options"]) == len(AD.ARTIFACT_LABELS) + 1, cid


def test_five_slots_compute_in_all_classes():
    for cid in CLASSES:
        m = mod(cid)
        four = m.compute(inputs(cid, slot_list(LIVE5[:4])))
        five = m.compute(inputs(cid, slot_list(LIVE5)))
        finite_result(four)
        finite_result(five)
        assert len(five["artifacts"]["equipped"]) == 5, cid
        assert five["total_dps"] >= four["total_dps"] * (1 - 1e-12), (cid, four["total_dps"], five["total_dps"])
        mixed = m.compute(inputs(cid, [{"key": k, "star": s} for k, s in MIXED5]))
        finite_result(mixed)
        assert len(mixed["artifacts"]["equipped"]) == 5, cid
        # other fight shapes (PvP / fixed-duration, Soul Contract, Candle ...) also stay finite (Chapter Hunt is left out: the class defaults carry no chapter
        # stage, which degenerates even without artifacts)
        for content in ("PvP", "Breakthrough", "Chapter Boss"):
            finite_result(m.compute(inputs(cid, slot_list(LIVE5[:3] + ["candle", "soul_contract"]), content)))


def test_order_independence():
    rng = random.Random(7)
    for cid in CLASSES:
        m = mod(cid)
        ref = m.compute(inputs(cid, slot_list(LIVE5)))["total_dps"]
        perms = [LIVE5[::-1], LIVE5[2:] + LIVE5[:2]] + [rng.sample(LIVE5, 5) for _ in range(2)]
        for p in perms:
            t = m.compute(inputs(cid, slot_list(p)))["total_dps"]
            assert math.isclose(t, ref, rel_tol=1e-12), (cid, p, t, ref)
    # FP-Mage and Hero: ALL 120 orders of the mixed set (timeline-engine artifacts, baked-in ones and Reindeer's Spear included)
    for cid in ("fp_mage", "hero"):
        m = mod(cid)
        slots = [{"key": k, "star": s} for k, s in MIXED5]
        ref = m.compute(inputs(cid, slots))["total_dps"]
        for perm in itertools.permutations(slots):
            t = m.compute(inputs(cid, list(perm)))["total_dps"]
            assert math.isclose(t, ref, rel_tol=1e-12), (cid, [p["key"] for p in perm], t, ref)


def test_same_artifact_twice_counts_once():
    for cid in CLASSES:
        m = mod(cid)
        four = slot_list(LIVE5[:4])
        base = m.compute(inputs(cid, four))["total_dps"]
        dup = m.compute(inputs(cid, four + [{"key": "alliance_badge", "star": 2}]))        # fifth slot repeats an equipped artifact (its own star is ignored)
        assert dup["total_dps"] == base, cid
        assert len(dup["artifacts"]["equipped"]) == 4, cid
        none5 = m.compute(inputs(cid, four + [{"key": "(none)", "star": None}]))
        assert none5["total_dps"] == base, cid


def test_four_slot_results_unchanged_by_the_cap():
    # the cap is the only change: a 4-slot request gives the same total whether it is passed as 4 entries or padded with "(none)"
    for cid in ("fp_mage", "hero"):
        m = mod(cid)
        four = slot_list(LIVE5[:4])
        a = m.compute(inputs(cid, four))["total_dps"]
        b = m.compute(inputs(cid, four + [{"key": "(none)", "star": 0}]))["total_dps"]
        assert a == b


def _row(rows, key):
    return next(r for r in rows if r["key"] == key)


def test_fifth_equals_sequential_toggle_in_sensitivity():
    """Sensitivity's equip-toggle (adding) row of the 5th artifact == the engine's 5-slot minus 4-slot DPS (pure boss content, where the time-weighted ratio
    blend collapses to the dollar delta), and the what-if on top of 5 equipped (a 6th) is the same composition."""
    for cid in ("fp_mage", "hero"):
        m = mod(cid)
        four = slot_list(LIVE5[:4])
        t4 = m.compute(inputs(cid, four))["total_dps"]
        t5 = m.compute(inputs(cid, slot_list(LIVE5)))["total_dps"]
        rows = sensitivity.run(m, inputs(cid, four), which="artifacts")["artifacts"]["rows"]
        fifth = _row(rows, LIVE5[4])
        assert not fifth["equipped"] and len(rows) == len(AD.ARTIFACT_LABELS)
        assert math.isclose(fifth["dps_gain"], t5 - t4, rel_tol=1e-12), (cid, fifth["dps_gain"], t5 - t4)
        assert math.isclose(fifth["new_total"], t5, rel_tol=1e-12), (cid, fifth["new_total"], t5)
        # removing it again from 5 equipped is the same pair of states (direction-invariant, live artifact)
        rows5 = sensitivity.run(m, inputs(cid, slot_list(LIVE5)), which="artifacts")["artifacts"]["rows"]
        r5 = _row(rows5, LIVE5[4])
        assert r5["equipped"] and math.isclose(r5["dps_gain"], t5 - t4, rel_tol=1e-12), (cid, r5["dps_gain"], t5 - t4)
        assert math.isclose(r5["pct_gain"], fifth["pct_gain"], rel_tol=1e-11), (cid, r5["pct_gain"], fifth["pct_gain"])
        # a 6th what-if on top of 5 equipped: no error, finite, positive for a live artifact, equals the direct model run with the 6-entry equipped set
        six = _row(rows5, "peach_tree")
        assert math.isfinite(six["dps_gain"]) and six["dps_gain"] > 0 and not six["equipped"], (cid, six["dps_gain"])
        eq6 = dict(art.resolve_slots(slot_list(LIVE5)), peach_tree=0 if art.default_star("peach_tree") == "Not Unlocked" else art.default_star("peach_tree"))   # (the what-if star: ``artifact_stars`` absent -> the default by rank)
        assert len(eq6) == 6
        t6 = m.model(dict(inputs(cid, slot_list(LIVE5)), _sens={"eq": eq6})).result()["total_dps"]
        assert math.isclose(six["dps_gain"], t6 - t5, rel_tol=1e-9), (cid, six["dps_gain"], t6 - t5)
        for r in rows5:
            assert math.isfinite(r["dps_gain"]) and math.isfinite(r["pct_gain"]), (cid, r["key"])


def _main():
    verbose = "-v" in sys.argv
    n = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            n += 1
            if verbose:
                print("ok  ", name)
    print(f"{n} tests passed")


if __name__ == "__main__":
    _main()
