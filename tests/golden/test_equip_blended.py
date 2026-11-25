#!/usr/bin/env python3
"""ENGINE-ONLY: every equip toggle of the Sensitivity artifact table reports the SAME gain and % gain from both directions in BLENDED content (Breakthrough, Hero Dungeon).

The rows use the time-weighted blend of the per-branch growth ratios (CLAUDE.md bug 9).  An unequipped artifact is measured ADDING it (ratio = with / without per branch); an
equipped one was measured REMOVING it (without / with), and ``(1-w) r'_boss + w r'_normal`` is not the inverse of ``(1-w) r_boss + w r_normal`` - so the same real pair read
differently (Arwen's Glass Shoes at typed 0 in Breakthrough: 7.3% from one side, 10.2% from the other).  Since 2026-11-25 the equipped row inverts each branch ratio first
(``engine.sensitivity.artifact_row``), so both directions agree; pure boss / pure normal content is bit-identical to before (the goldens pin it).

Covered: 19 live artifacts unequipped vs equipped on the same inputs; the baked-in ones (Book of Ancient, Athena's Gloves, Shamaness
Marble, Reindeer's Spear, Star Rock, Clear Spring Water, Soul Pouch, Cursed Doll, Lit Lamp, Bottle of Emotion's Final Damage) with the stat typed in / out; with and without a
second artifact equipped; several classes of different families.

    python3 tests/golden/test_equip_blended.py        (also pytest-collectable)
"""
import importlib
import itertools
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))
import factor_mode  # noqa: E402

FACTOR_MODE = factor_mode.pin("extended")
import snapshot_common as SC  # noqa: E402
from engine import artifacts as art_mod, sensitivity  # noqa: E402
from engine.data import artifacts as AD  # noqa: E402

CONTENTS = ("Breakthrough", "Hero Dungeon")
LIVE_CLASSES = ("fp_mage", "hero", "night_lord", "bowmaster", "bishop")
BAKED_CLASSES = ("fp_mage", "hero", "night_lord")           # the classes whose blocks wire every baked-in toggle (SensSpec flags)
LIVE = [a for a in AD.ARTIFACT_LABELS if art_mod.effect_kind(a) == "live" and a != "reindeer_spear"]      # (Reindeer's Spear / Bottle of Emotion also carry a baked-in stat: baked_pairs)
STAR = 4


def mod(cid):
    return importlib.import_module(f"engine.classes.{cid}")


def inputs(cid, content, slots, **over):
    d = SC.make_inputs(mod(cid), content, "late", True, **over)
    d["artifacts"] = [dict(s) for s in slots]
    d["artifact_stars"] = {s["key"]: s["star"] for s in slots}
    return d


def row(cid, d, art):
    d = dict(d)
    d["artifact_stars"] = dict(d.get("artifact_stars") or {}, **{art: STAR})
    base = sensitivity._Base(d, class_module=mod(cid))
    return sensitivity.artifact_row(base, art), base


def same(r_off, r_on, label):
    assert not r_off["equipped"] and r_on["equipped"], label
    assert math.isclose(r_off["dps_gain"], r_on["dps_gain"], rel_tol=1e-9, abs_tol=1e-11 * r_off["new_total"]), (label, r_off["dps_gain"], r_on["dps_gain"])
    assert math.isclose(r_off["pct_gain"], r_on["pct_gain"], rel_tol=1e-11), (label, r_off["pct_gain"], r_on["pct_gain"])


def test_live_toggles_are_direction_invariant_in_blended_content():
    n = 0
    for cid, content, art in itertools.product(LIVE_CLASSES, CONTENTS, LIVE):
        for extra in ([], [{"key": "candle", "star": 3}, {"key": "hexagon_necklace", "star": 2}]):
            if art in [e["key"] for e in extra]:
                continue
            r_off, b_off = row(cid, inputs(cid, content, extra), art)
            r_on, b_on = row(cid, inputs(cid, content, extra + [{"key": art, "star": STAR}]), art)
            assert 0 < b_off.w < 1 and 0 < b_on.w < 1
            same(r_off, r_on, (cid, content, art, [e["key"] for e in extra]))
            n += 1
    assert n >= 350


def baked_pairs(cid, content):
    """[(artifact, off typed overrides, on typed overrides)]: the same real state with the baked-in artifact's stat typed out / in."""
    m = mod(cid)
    stats = SC.stat_values(m.schema(), "late")
    cr, cd, asp, md, fd, bd, bdi, dp = (stats[k] for k in ("crit_rate", "crit_damage", "attack_speed", "max_damage", "final_damage", "boss_damage", "buff_duration_increase_pct", "def_pen"))
    sv = art_mod.sv
    off_m = m.model(inputs(cid, content, []))
    bonus = getattr(off_m, "crit_rate_bonus", 0.0)
    ct, mt = off_m.content_type, off_m.monster_type
    pairs = []
    cr_d, pct = sv("book_of_ancient_crit_rate", STAR), sv("book_of_ancient_crit_damage_pct_of_crit_rate", STAR)
    pairs.append(("book_of_ancient", {}, dict(crit_rate=cr + cr_d, crit_damage=cd + pct / 100 * (cr + cr_d + bonus))))
    a_d, a_pct = sv("athena_gloves_attack_speed", STAR), sv("athena_gloves_max_damage_pct_of_attack_speed", STAR)
    pairs.append(("athena_gloves", {}, dict(attack_speed=asp + a_d, max_damage=md + a_pct / 100 * (asp + a_d))))
    pairs.append(("shamaness_marble", {}, dict(buff_duration_increase_pct=bdi + sv("shamaness_marble_buff_duration_increase_pct", STAR))))
    mag = sv("reindeer_spear_def_pen", STAR)
    pairs.append(("reindeer_spear", {}, dict(def_pen=100 * (1 - (1 - dp / 100) * (1 - mag / 100)))))
    pairs.append(("star_rock", {}, dict(boss_damage=bd + sv("star_rock_boss_damage", STAR))))
    for art in ("clear_spring_water", "soul_pouch", "cursed_doll", "lit_lamp"):
        x = sensitivity._baked_fd_value(art, STAR, ct, mt, asp)
        pairs.append((art, {}, dict(final_damage=((1 + fd / 100) * (1 + x / 100) - 1) * 100)))
    x = sensitivity._baked_fd_value("bottle_of_emotion", STAR, ct, mt, 80.0)           # Attack-Speed-dependent: typed Attack Speed 80 on both sides
    pairs.append(("bottle_of_emotion", dict(attack_speed=80.0), dict(attack_speed=80.0, final_damage=((1 + fd / 100) * (1 + x / 100) - 1) * 100)))
    return pairs


def test_baked_in_toggles_are_direction_invariant_in_blended_content():
    n = 0
    for cid, content in itertools.product(BAKED_CLASSES, CONTENTS):
        for art, off, on in baked_pairs(cid, content):
            slots_off, slots_on = [], [{"key": art, "star": STAR}]
            r_off, _b = row(cid, inputs(cid, content, slots_off, **off), art)
            r_on, _b = row(cid, inputs(cid, content, slots_on, **dict(off, **on)), art)
            same(r_off, r_on, (cid, content, art))
            n += 1
    assert n >= 50


def test_pure_content_rows_are_bit_identical_to_the_dollar_form():
    """w = 0 / 1 (World Boss, Chapter Hunt): the equipped row is still ``-total x (ratio - 1)`` with the removal ratio - the blended branch never runs."""
    for cid, content in itertools.product(("fp_mage", "hero"), ("World Boss", "Chapter Hunt")):
        r, base = row(cid, inputs(cid, content, [{"key": "alliance_badge", "star": STAR}]), "alliance_badge")
        assert base.w in (0.0, 1.0) and "ratio_adding" not in r
        assert r["dps_gain"] == -1 * base.total * (r["ratio"] - 1)


def test_blended_removal_is_the_inverse_blend():
    r, base = row("fp_mage", inputs("fp_mage", "Breakthrough", [{"key": "arwens_glass_shoes", "star": STAR}]), "arwens_glass_shoes")
    assert 0 < base.w < 1 and "ratio_adding" in r
    # without the artifact: boss / normal totals of the block; the adding blend of the same pair is (1-w) b1/b0 + w n1/n0
    d = inputs("fp_mage", "Breakthrough", [])
    off = mod("fp_mage").compute(d)
    on = mod("fp_mage").compute(inputs("fp_mage", "Breakthrough", [{"key": "arwens_glass_shoes", "star": STAR}]))
    g = (1 - base.w) * on["boss_dps"] / off["boss_dps"] + base.w * on["normal_dps"] / off["normal_dps"]
    assert math.isclose(r["ratio_adding"], g, rel_tol=1e-12) and math.isclose(r["pct_gain"], g * 100, rel_tol=1e-12)


def main():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"ok: {fn.__name__}", flush=True)
    print(f"OK: {len(fns)} checks")


if __name__ == "__main__":
    main()
