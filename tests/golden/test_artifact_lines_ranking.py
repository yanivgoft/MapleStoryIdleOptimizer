#!/usr/bin/env python3
"""Engine test (no workbook): the equip ranking carries the value of an artifact's POTENTIAL LINES (``inputs["artifact_lines"]``) and Arwen's Glass Shoes
(Companion Summoning Time Increase) is priced on the real companion model.

Reported bug (2026-11-25): Arwen's Glass Shoes equipped at star 5 (+40% summoning time) with potential lines entered on the Artifacts tab showed "0%" in the
artifact ranking.  Two causes: (1) once the typed total is past the companion's last useful step (Blaze Wizard in Breakthrough: +40%) the effect is genuinely
worth 0 in the model, and (2) the web never sent the lines, so the ranking row (which the engine already extends by ``artifact_potential_gain``) never saw them.

    python3 tests/golden/test_artifact_lines_ranking.py            (also pytest-collectable)
"""
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))
import factor_mode  # noqa: E402

FACTOR_MODE = factor_mode.pin("extended")          # engine-only test: production growth curves
from engine import potentials, sensitivity  # noqa: E402
from engine.classes import fp_mage  # noqa: E402

ARWEN = "arwens_glass_shoes"
LINES = {ARWEN: {"lines": [("Legendary", "Damage %"), ("Epic", "Boss Monster Damage %")]}}


def inputs(typed, equipped, content="Breakthrough", **extra):
    d = dict(fp_mage.defaults(content), companion_choice="Blaze Wizard", companion_level=10, companion_summon_time_increase_pct=typed)
    d["artifacts"] = [{"key": ARWEN, "star": 5}] if equipped else []
    d["artifact_stars"] = {ARWEN: 5}
    d.update(extra)
    return d


def arwen_row(d):
    return next(r for r in sensitivity.run(fp_mage, d, which=["artifacts"])["artifacts"]["rows"] if r["key"] == ARWEN)


def total(d):
    return fp_mage.compute(d)["total_dps"]


def test_saturated_effect_is_zero_without_lines():
    """Typed 60 + the shoes' 40 = 100, and 60 alone is already past Blaze Wizard's last useful step in Breakthrough (40 before FP-Mage's Poison Breath stun of the 2026-11-26 patch): the EFFECT is exactly 0 (the old 0% row)."""
    assert total(inputs(60, True)) == total(inputs(60, False))
    for equipped in (True, False):
        r = arwen_row(inputs(60, equipped))
        assert r["dps_gain"] == 0.0 and r["pct_gain"] == 100.0 and r["potential_gain"] == 0.0


def test_equipped_row_includes_the_lines():
    """The reported case: equipped, effect saturated, lines entered -> the row is the lines' value (> 0), not 0%."""
    d = inputs(60, True, artifact_lines=LINES)
    gains, _rates, base_total = potentials.hook_for(fp_mage, inputs(60, True), LINES)
    assert gains[ARWEN] > 0
    r = arwen_row(d)
    assert r["potential_gain"] == gains[ARWEN] and math.isclose(r["dps_gain"], gains[ARWEN], rel_tol=1e-12)
    # % gain divides by the hypothetical-UNEQUIPPED total (item 15): total / (total - gain)
    assert math.isclose(r["pct_gain"], base_total / (base_total - gains[ARWEN]) * 100, rel_tol=1e-12) and r["pct_gain"] > 100
    assert r["equipped"] is True


def test_unequipped_row_is_effect_plus_lines():
    d = inputs(60, False, artifact_lines=LINES)
    gains, _rates, base_total = potentials.hook_for(fp_mage, inputs(60, False), LINES)
    r = arwen_row(d)
    assert r["equipped"] is False and r["potential_gain"] == gains[ARWEN] > 0
    assert math.isclose(r["pct_gain"], (base_total + gains[ARWEN]) / base_total * 100, rel_tol=1e-12)


def exact_effect(typed, equipped):
    """The Sensitivity convention for the shoes' EFFECT only (time-weighted blend of the boss / normal ratios, bug 9), rebuilt from two plain compute() runs:
    total_off x (ratio_on/off - 1) - the SAME number from both directions (2026-11-25: the equipped row inverts the per-branch removal ratios before blending, so a
    blended content such as Breakthrough no longer reads differently from the unequipped side of the identical real pair)."""
    on, off = fp_mage.compute(inputs(typed, True)), fp_mage.compute(inputs(typed, False))
    w = on["derived"]["normal_weight"]

    def ratio(new, old):
        return (1 - w) * new["boss_dps"] / old["boss_dps"] + w * new["normal_dps"] / old["normal_dps"]
    return off["total_dps"] * (ratio(on, off) - 1)


def test_threshold_crossing_is_priced_on_the_real_companion_model():
    """Typed 10 (Blaze Wizard's 3rd stun cast needs +13.667%): the shoes (10 -> 50) cross the 14 / 28 / 30 steps (the summon candidate flips at 40).  The effect part
    of the row is the time-weighted relative change of two plain compute() runs (the typed value + the star value goes through the real companion model), and the
    lines come on top, from both directions."""
    for equipped in (False, True):
        without_lines = arwen_row(inputs(10, equipped))
        with_lines = arwen_row(inputs(10, equipped, artifact_lines=LINES))
        assert without_lines["potential_gain"] == 0 and with_lines["potential_gain"] > 0
        assert math.isclose(without_lines["dps_gain"], exact_effect(10, equipped), rel_tol=1e-9), (equipped, without_lines["dps_gain"], exact_effect(10, equipped))
        assert without_lines["dps_gain"] != 0
        assert math.isclose(with_lines["dps_gain"], without_lines["dps_gain"] + with_lines["potential_gain"], rel_tol=1e-12)
        assert with_lines["pct_gain"] > 100
    # the typed value + the shoes IS the real model's input: 10 + 40 gives the same totals as typing 50 without the shoes, and 0 + 40 the same as typing 40
    assert total(inputs(10, True)) == total(inputs(50, False)) and total(inputs(0, True)) == total(inputs(40, False))
    assert total(inputs(10, True)) != total(inputs(10, False))


def test_removal_never_goes_below_zero_total():
    """Removing the shoes subtracts nothing below the typed value: the equipped row's model is the typed total itself (>= 0 by construction)."""
    r = arwen_row(inputs(0, True))
    assert r["dps_gain"] != 0 and math.isclose(r["dps_gain"], exact_effect(0, True), rel_tol=1e-9)


def test_lines_follow_the_resolved_star():
    """Lines unlock with the artifact's star (line 1 from star 1, line 2 from star 2): an equipped star-0 Arwen's has no active line -> 0 from the lines."""
    d = inputs(60, True, artifact_lines=LINES)
    d["artifacts"] = [{"key": ARWEN, "star": 0}]
    d["artifact_stars"] = {ARWEN: 0}
    assert arwen_row(d)["potential_gain"] == 0.0
    d["artifacts"] = [{"key": ARWEN, "star": 1}]
    one = arwen_row(d)["potential_gain"]
    d["artifacts"] = [{"key": ARWEN, "star": 2}]
    two = arwen_row(d)["potential_gain"]
    assert 0 < one < two


def test_explicit_gain_and_lines_do_not_clash():
    """``artifact_potential_gain`` (the workbook hook) keeps working; a computed value overrides only the artifacts that have lines."""
    d = inputs(60, True, artifact_lines=LINES, artifact_potential_gain={"pigs_ribbon": 123.0, ARWEN: 1.0})
    rows = {r["key"]: r for r in sensitivity.run(fp_mage, d, which=["artifacts"])["artifacts"]["rows"]}
    assert rows["pigs_ribbon"]["potential_gain"] == 123.0 and rows[ARWEN]["potential_gain"] > 1.0


def test_dict_lines_are_accepted():
    """The web sends ``{rarity, stat}`` objects; the engine takes them as well as ``(rarity, stat)`` pairs."""
    as_dicts = {ARWEN: {"lines": [{"rarity": "Legendary", "stat": "Damage %"}, {"rarity": "Epic", "stat": "Boss Monster Damage %"}]}}
    a = arwen_row(inputs(60, True, artifact_lines=LINES))
    b = arwen_row(inputs(60, True, artifact_lines=as_dicts))
    assert a["potential_gain"] == b["potential_gain"] > 0


def main():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"ok: {fn.__name__}", flush=True)
    print(f"OK: {len(fns)} checks")


if __name__ == "__main__":
    main()
