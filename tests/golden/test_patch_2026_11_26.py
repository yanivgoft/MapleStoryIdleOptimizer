#!/usr/bin/env python3
"""The numbers of the 2026-11-26 patch (Nexon patch notes, Job Balance) as they live in the engine data - one place that names every changed value, so a later edit cannot
silently undo one - plus the behaviour of the three new live terms (Final Pact / Phoenix Run ramp, Majestic Presence's Final Damage buff, Frailty Curse - Weaken).

Not modelled on purpose (see KNOWN_GAPS "Patch 2026-11-26"): Poison Breath's 1.5 s stun (FP-Mage), Elemental Adaptation / Divine Protection's debuff immunity, Flame Barrier's
absorb, companion barriers, party-play stacking.

    python3 tests/golden/test_patch_2026_11_26.py        # also pytest-collectable
"""
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))
import factor_mode  # noqa: E402

FACTOR_MODE = factor_mode.pin("extended")

from engine.classes import blaze_wizard as BW, corsair as CO, dark_knight as DK, night_lord as NL  # noqa: E402
from engine.common.fight import Fight  # noqa: E402
from engine.data import (blaze_wizard as BWD, bowmaster as BO, corsair as COD, dark_knight as DKD, hero as HE, marksman as MA,  # noqa: E402
                         night_lord as NLD, paladin as PA, shadower as SH)
from engine.sens_specs import (blaze_wizard as BWS, bowmaster as BOS, dark_knight as DKS, dawn_warrior as DWS, hero as HES, marksman as MAS,  # noqa: E402
                               night_lord as NLS, night_walker as NWS, paladin as PAS, shadower as SHS)


def test_plain_values():
    for mod in (HE, PA, DKD):
        assert mod.DAMAGE_SKILLS["MAGIC_CRASH"]["base"] == 65000
    assert PA.DAMAGE_SKILLS["DIVINE_JUDGMENT"]["base"] == 10000
    assert PA.DIVINE_MARK_WEAKEN["pct"] == 12 and PA.DIVINE_MARK_WEAKEN["level"] == 138
    for mod in (HE, DKD, BO, MA):
        assert mod.ADVANCED_FINAL_ATTACK["gated"] == {113: 100}
    assert BO.ILLUSION_STEP["base"] == 150 and MA.ILLUSION_STEP["base"] == 150
    assert MA.DAMAGE_SKILLS["ARROW_ILLUSION"]["base"] == 14000 and MA.BOLT_SURPLUS["base"] == 7500
    assert NLD.TOXIC_VENOM["base"] == 8000 and SH.TOXIC_VENOM["base"] == 8000
    assert NLD.DAMAGE_SKILLS["SUDDEN_RAID_BURST"]["mastery"] == {126: 80} and SH.DAMAGE_SKILLS["SUDDEN_RAID_BURST"]["mastery"] == {126: 80}
    assert SH.SMOKESCREEN_CRIT_DAMAGE == (113, 40)
    assert NLD.FRAILTY_WEAKEN == (113, 1.08) and not hasattr(NLD, "FRAILTY_CRIT_DAMAGE_TAKEN")


def test_passive_deltas():
    def base(spec, hook, unlock=120):
        return [p.base for p in spec.PASSIVE_LEVELS if p.hook == hook and p.unlock == unlock]
    for spec in (HES, DKS, PAS, BOS, MAS, SHS, NLS, NWS, DWS, BWS):
        assert base(spec, "max_damage_delta") == [300], spec.__name__          # Max Damage Multiplier 20 -> 30 (Brilliant Enlightenment's +20 at Lv66 is a different row)
    for spec in (HES, DKS):
        assert base(spec, "final_damage_delta", 125) == [180], spec.__name__    # Power Stance 15 -> 18
    assert BWD.CURVES["PURE_MAGIC_MAX"].base == 300


def test_ramp_average():
    class C:
        monster_type, fight_duration, fixed_duration_active, normal_weight = "boss", 60, True, 0.0
    f = Fight(C, 30, 0, 0, 999)
    assert math.isclose(f.ramp_avg_stacks(12), 12 - 78 / 60, rel_tol=1e-12)           # whole stacks gained at t = 1, 2, ...: 12 d - 78 over d seconds
    C.fight_duration = 5
    assert math.isclose(Fight(C, 30, 0, 0, 999).ramp_avg_stacks(12), (0 + 1 + 2 + 3 + 4) / 5, rel_tol=1e-12)
    C.fixed_duration_active, C.monster_type = False, "normal"
    assert Fight(C, 30, 0, 0, 999).ramp_avg_stacks(12) == 12.0                           # continuous hunting: always at the maximum
    C.monster_type = "pvp"
    assert math.isclose(Fight(C, 30, 0, 0, 999).ramp_avg_stacks(12), 12 - 78 / 30, rel_tol=1e-12)


def test_final_pact_and_phoenix_run_are_live_ramps():
    for content in ("World Boss", "Chapter Hunt"):
        m = DK.model(dict(DK.defaults(content), level=105))
        assert m.final_pact_avg == 0.0                                             # locked below 107
        lo = DK.model(dict(DK.defaults(content), level=110))
        hi = DK.model(dict(DK.defaults(content), level=120))
        assert lo.final_pact_avg > 0 and hi.final_pact_avg > lo.final_pact_avg      # the Lv118 mastery doubles the per-stack value (and the factor grows)
        assert lo.final_damage_extra == lo.final_pact_avg
    wb = BW.model(dict(BW.defaults("Chapter Hunt"), level=110))
    assert wb.phoenix_run_avg > 0 and BW.model(dict(BW.defaults("Chapter Hunt"), level=100)).phoenix_run_avg == 0.0
    assert BWD.UNLOCK_LEVEL["PHOENIX_RUN"] == 107 and BWD.UNLOCK_LEVEL["PHOENIX_RUN_BOOST"] == 118


def test_frailty_curse_weaken_multiplies_the_debuff():
    below = NL.model(dict(NL.defaults("World Boss"), level=112))
    at = NL.model(dict(NL.defaults("World Boss"), level=113))
    assert below.crit_damage_bonus == 0.0 and at.crit_damage_bonus == 0.0           # the Critical-Damage-Taken term is gone
    venom = NLD.VENOM_WEAKEN[1]
    assert 1.08 <= (at.monster_dmg_bonus - venom) / (below.monster_dmg_bonus - venom) < 1.10      # x1.08 (the one-level step of the growth curve adds about 1 %)


def test_majestic_presence_buff():
    assert COD.MAJESTIC_FD == dict(pct=8.0, duration=5.0)
    locked = CO.model(dict(CO.defaults("World Boss"), level=119))
    on = CO.model(dict(CO.defaults("World Boss"), level=120))
    assert locked.majestic_fd_pct == 0.0 and 0.0 < on.majestic_fd_pct < COD.MAJESTIC_FD["pct"]       # a Poisson uptime of an 8 % buff
    assert on.final_damage_all >= on.majestic_fd_pct and on.final_damage_rest >= on.majestic_fd_pct


def test_artifact_stars_6_and_7():
    from engine import artifacts as art
    from engine.data import artifacts as AD
    assert art.sv("silver_pendant_enemy_dmg_taken", 0) == 10 and art.sv("silver_pendant_enemy_dmg_taken", 5) == 20
    assert art.sv("silver_pendant_enemy_dmg_taken", 6) == 22 and art.sv("silver_pendant_enemy_dmg_taken", 7) == 24       # every star adds 20 % of the base value
    for key, values in AD.ARTIFACT_STAR_VALUES.items():                                # the whole table family is exactly v0 x (1 + 0.2 x star)
        for star in range(8):
            assert math.isclose(art.sv(key, star), values[0] * (1 + 0.2 * star), rel_tol=1e-12, abs_tol=1e-12), (key, star)
    for key, rank in AD.ARTIFACT_RANK.items():
        assert art.max_star(key) == (7 if rank == "Legendary" else 5)
    legendary = next(k for k, r in AD.ARTIFACT_RANK.items() if r == "Legendary")
    epic = next(k for k, r in AD.ARTIFACT_RANK.items() if r == "Epic")
    assert art.resolve_slots([{"key": legendary, "star": 7}]) == {legendary: 7}
    try:
        art.resolve_slots([{"key": epic, "star": 6}])
        raise AssertionError("an Epic artifact has no star 6")
    except ValueError:
        pass


def test_new_artifacts():
    from engine import artifacts as art
    from engine.classes import hero as H
    from engine.data import artifacts_extra as AX

    def report(content, slots, **over):
        return H.compute(dict(H.defaults(content), **over, artifacts=slots))

    def bucket(content, slots, name):
        return report(content, slots)["artifacts"]["buckets"][name]
    bottle = lambda star: [{"key": "sealed_bottle", "star": star}]                      # noqa: E731
    # Sealed Bottle: +6 % Final Damage always (x1.2 at star 5, x1.4 at star 7 by the "20 % of the base per star" rule)
    assert math.isclose(bucket("World Boss", bottle(0), "final_damage"), 6.0, rel_tol=1e-12)
    assert math.isclose(bucket("World Boss", bottle(7), "final_damage"), 6.0 * 2.4, rel_tol=1e-12)
    # ... kill stacks: full 10 in continuous hunting (+1 % Normal), none in boss-only content / PvP; Breakthrough ramps to 30 stacks (boss branch +2 % each) by the boss
    assert math.isclose(bucket("Chapter Hunt", bottle(0), "normal_damage"), AX.SEALED_BOTTLE_STACKS * 1.0, rel_tol=1e-12)
    assert bucket("World Boss", bottle(0), "normal_damage") == 0 and bucket("World Boss", bottle(0), "boss_damage") == 0 and bucket("PvP", bottle(0), "boss_damage") == 0
    bt_normal, bt_boss = bucket("Breakthrough", bottle(0), "normal_damage"), bucket("Breakthrough", bottle(0), "boss_damage")
    assert 0 < bt_normal < AX.SEALED_BOTTLE_STACKS_BREAKTHROUGH and math.isclose(bt_boss, 2.0 * AX.SEALED_BOTTLE_STACKS_BREAKTHROUGH, rel_tol=1e-12)
    assert math.isclose(bucket("Hero Dungeon", bottle(0), "boss_damage"), 2.0 * AX.SEALED_BOTTLE_STACKS, rel_tol=1e-12)         # 10 stacks outside Chapter Breakthrough
    # Mummydog's Bandages / Shiny Watch: Attack % (12 / 10 at star 0, +20 % of the base per star)
    assert math.isclose(bucket("World Boss", [{"key": "mummydogs_bandages", "star": 7}], "attack_pct"), 12 * 2.4, rel_tol=1e-12)
    assert math.isclose(bucket("World Boss", [{"key": "shiny_watch", "star": 3}], "attack_pct"), 10 * 1.6, rel_tol=1e-12)
    # Shiny Watch's companion ramp: 4 % Final Damage per 3 s up to 10 stacks, averaged over the companion's window (4.5 stacks = 18 % over the base 30 s)
    inputs = dict(H.defaults("World Boss"), companion_choice="Blaze Wizard", companion_level=10)
    m_off = H.model(dict(inputs, artifacts=[{"key": "alliance_badge", "star": 0}]))
    m_on = H.model(dict(inputs, artifacts=[{"key": "shiny_watch", "star": 0}]))
    assert m_on.comp_host["watch_per"] == 4.0 and m_off.comp_host["watch_per"] == 0.0
    cpm = __import__("companion_python_model")
    assert math.isclose(cpm._ramp_avg_stacks(30, 10, 3.0), 4.5, rel_tol=1e-12) and cpm._ramp_avg_stacks(300, 10, 3.0) < 10
    host = dict(m_on.comp_host)
    with_watch = cpm.run(host, "Blaze Wizard", 10, 0.0)["comp_blend_dps"]
    without = cpm.run(dict(host, watch_per=0.0), "Blaze Wizard", 10, 0.0)["comp_blend_dps"]
    assert with_watch > without * 1.05                                                  # the ramp adds at least ~5 % to a 30 s companion window (18 % of Final Damage on average)


def test_bishop_divine_protection_and_fp_mage_stun():
    from engine.classes import bishop as B, fp_mage as F
    from engine.data import fp_mage as FD
    b = B.model(dict(B.defaults("World Boss")))
    assert b.divine_protection_bonus == 0.0                                               # permanent now: part of the typed Defense %
    only_typed = B.model(dict(B.defaults("World Boss"), defense=1000.0, defense_pct=50.0, level=140)).total_defense
    assert math.isclose(only_typed, 1000.0 * 1.5, rel_tol=1e-12)                       # nothing but the typed Defense and Defense % (the old live +25 % x uptime is gone)
    assert FD.PLAYER_STUN == [dict(id="BREATH", key="POISON_BREATH", typ="cast", dur=1.5, p=1.0)]
    r = F.compute(dict(F.defaults("World Boss"), companion_choice="None", companion_level=0))
    assert r["companion"] is not None and r["companion"]["choice"] == "None"           # a stun-only uplift is reported like in every class with a player stun


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("OK: 2026-11-26 patch values, passive deltas, ramp average, Final Pact / Phoenix Run ramps, Frailty Curse - Weaken, Majestic Presence buff, artifact stars 6-7, the three new artifacts, Bishop Divine Protection, FP-Mage Poison Breath")
    return 0


if __name__ == "__main__":
    sys.exit(main())
