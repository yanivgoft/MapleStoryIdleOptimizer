#!/usr/bin/env python3
"""Golden test: ``engine.sensitivity`` for ICE/LIGHTNING MAGE against the Ice/Lightning Mage WORKBOOK's Sensitivity sheet (evaluated with ``formulas`` on Sensitivity-slimmed
copies by ``sens_reference_generic.py --class ice_lightning_mage``; numbers frozen in tests/golden/ice_lightning_mage_sensitivity_golden.json).  Plain ``python3``
runnable, also pytest-collectable.  The comparison logic is the class-agnostic ``sens_compare_generic.py`` (a new class's test is a wrapper like this file).

    python3 tests/golden/test_ice_lightning_mage_sensitivity.py              # rel 1e-9 on every compared value; exits 1 on any difference
    python3 tests/golden/test_ice_lightning_mage_sensitivity.py -v --rtol 1e-6
    python3 tests/golden/test_ice_lightning_mage_sensitivity.py --case "S/WB140/a"

Besides the golden: the spec == the builder's tables (STAT_SWEEP, STATUS_REBUILD_KEYS, COMPANION_FULL_SEARCH_KEYS, SUMMON_TIME_KEYS, the passive rows of the Skills sheet), the
three workbook wirings the Dark Knight port found missing (all present in this builder since 2026-11-22), the engine-only direction-invariance of the equip toggles
(CLAUDE.md item 15 / checklist 8c) and the API shape.
"""
import json
import math
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))
from engine import sensitivity  # noqa: E402
from engine import sens_specs  # noqa: E402
from engine.classes import ice_lightning_mage as ilm  # noqa: E402
from engine.data import artifacts as AD  # noqa: E402
import sens_compare_generic as C  # noqa: E402
import sens_test_common as SC  # noqa: E402

GOLDEN = HERE / "ice_lightning_mage_sensitivity_golden.json"
TEST = SC.SensTest("ice_lightning_mage", ilm, GOLDEN, "Ice/Lightning Mage")
SPEC = sens_specs.get("ice_lightning_mage")


_builder, _inputs = TEST.builder, TEST.inputs


def test_static():
    """The spec reproduces the builder's tables (so a builder change that is not mirrored in the spec fails here)."""
    assert [t["key"] for t in sensitivity.ARTIFACT_TOGGLES] == list(AD.ARTIFACT_LABELS), "toggle list must come from the engine's artifact table"
    assert sensitivity.supports(ilm) and sensitivity.meta(ilm)["class_id"] == "ice_lightning_mage"
    assert len(sensitivity.stat_sweep(ilm)) == 27 and len(sensitivity.ARTIFACT_TOGGLES) == 36
    bm = _builder()
    if bm is None:
        return
    assert [(k, l, t) for k, l, t in bm.STAT_SWEEP_STAT_ENTRIES] == [tuple(e) for e in SPEC.stat_list]
    assert list(bm.STATUS_REBUILD_KEYS) == list(SPEC.status_rebuild_keys)
    assert tuple(bm.COMPANION_FULL_SEARCH_KEYS) == tuple(SPEC.companion_full_search_keys)
    assert tuple(bm.SUMMON_TIME_KEYS) == tuple(SPEC.summon_time_keys)
    assert list(bm.CDR_SWEEP_VALUES) == list(sensitivity.CDR_SWEEP_VALUES)
    assert list(bm.ARTIFACT_LABELS) == list(AD.ARTIFACT_LABELS) and sorted(bm.ARTIFACT_NO_DPS_EFFECT) == sorted(AD.ARTIFACT_NO_DPS_EFFECT)
    # passive-level deltas: the block's crit_rate_delta / crit_dmg_delta / min_dmg_delta / attack_speed_delta rows, each with the Skills-sheet row's own (base, factor index, job step)
    col = {name: i for i, name in enumerate(bm.SKILL_COLUMNS)}
    rows = {r[col["Key"]]: r for r in bm.SKILL_ROWS}
    hook_of = {"MAGIC_CRITICAL_RATE": "crit_rate_delta", "HIGH_WISDOM": "crit_rate_delta", "MAGIC_CRITICAL_DAMAGE": "crit_damage_delta",
               "SPELL_MASTERY": "min_damage_delta", "MAGIC_ACCELERATION": "as_bonus_extra"}
    expect = sorted((hook, rows[k][col["BaseDamage(tenths%)"]], rows[k][col["FactorIndex"]], rows[k][col["JobStep"]]) for k, hook in hook_of.items())
    got = sorted((p.hook, p.base, p.fidx, p.step) for p in SPEC.passive_levels)
    assert expect == got, (expect, got)
    assert all(rows[k][col["ScalesWithLevel"]] is True for k in hook_of) and all(p.unlock is None for p in SPEC.passive_levels)
    src = Path(bm.__file__).read_text()
    for k, hook in (("MAGIC_CRITICAL_RATE", "crit_rate_delta"), ("HIGH_WISDOM", "crit_rate_delta"), ("MAGIC_CRITICAL_DAMAGE", "crit_dmg_delta"),
                    ("SPELL_MASTERY", "min_dmg_delta"), ("MAGIC_ACCELERATION", "attack_speed_delta")):
        assert f'(F{{row_of["{k}"]}}-Calc!F{{ROW["{k}"]}})' in src, k
    # the stat maps of cubes / equipment / artifact potentials are the engine's INT defaults (so the spec carries none)
    from engine import cubes, equipment, potentials
    assert not SPEC.stat_to_key
    assert bm.POTENTIAL_STAT_TO_SWEEP_KEY == cubes.POTENTIAL_STAT_TO_SWEEP_KEY and bm.EQUIP_COMPARE_STAT_TO_SWEEP_KEY == equipment.STAT_TO_SWEEP_KEY
    assert bm.ARTIFACT_POTENTIAL_STAT_TO_SWEEP_KEY == potentials.STAT_TO_KEY and bm.POTENTIAL_SUB_STAT_PCT_LINES == {}
    assert SPEC.mainstat.flat == "flat_int" and SPEC.mainstat.pct == "int_pct" and not SPEC.mainstat.subs
    # the three block wirings the Dark Knight port found missing, all present here (a builder change flips these, then flip the spec flag and regenerate the golden)
    assert 'f\'({ib("buff_duration_increase_pct")}+{shamaness_marble_delta_block})\'' in src          # Shamaness Marble's Buff Duration what-if enters bdi_block
    assert "{attack_speed_total_block}/150" in src and "{attack_speed_with_delta}" not in src          # Actions Per Second includes Athena's direct Attack Speed
    assert "(1-{def_pen_total_block}/100)))'\n                f'*(1+{ib(\"final_damage\")}/100)" in src   # the rows' K formula reads def_pen_total_block (the Reindeer dose)
    assert SPEC.bdi_toggle_wired and SPEC.reindeer_dose_in_rows and SPEC.athena_as_in_aps and not SPEC.pin_monster_defense and SPEC.baked_fd_form == "factor"


def test_toggle_direction_invariance():
    """CLAUDE.md item 15 / checklist 8c, engine-only: the same real state reached from the two directions (artifact equipped with its baked-in stat typed into the
    Inputs, or unequipped with the stat removed) reports the IDENTICAL DPS gain and % gain - in World Boss (pure boss: the time-weighted ratio blend collapses to
    the dollar delta) - and the adding gain equals the true Total delta."""
    from engine import artifacts as art
    from sens_cases import STARS
    pairs = []
    for key in ("hexagon_necklace", "horn_flute", "candle", "secret_map", "alliance_badge", "charm_of_the_undead", "old_music_box", "ring_of_cycles"):
        pairs.append((key, {}, {}))        # live artifacts: no Inputs adjustment
    # Book of Ancient: typed Crit Rate + dependent Crit Damage (pct x the TOTAL crit rate; Ice/Lightning Mage has no other live crit-rate source)
    star = STARS["book_of_ancient"]
    cr_d, pct = art.sv("book_of_ancient_crit_rate", star), art.sv("book_of_ancient_crit_damage_pct_of_crit_rate", star)
    assert ilm.model(_inputs("World Boss", [])).crit_rate_bonus == 0.0
    pairs.append(("book_of_ancient", dict(crit_rate=60.0, crit_damage=150.0), dict(crit_rate=60.0 + cr_d, crit_damage=150.0 + pct / 100 * (60.0 + cr_d))))
    for key in ("cursed_doll", "lit_lamp"):
        fd = art.sv(f"{key}_final_damage", STARS[key])
        pairs.append((key, dict(final_damage=12.0), dict(final_damage=((1 + 12.0 / 100) * (1 + fd / 100) - 1) * 100)))
    fd_cd = art.sv("cursed_doll_final_damage", STARS["cursed_doll"])          # with a LIVE Final Damage artifact (bucket a > 1) equipped as well
    pairs.append(("cursed_doll", dict(final_damage=12.0), dict(final_damage=((1 + 12.0 / 100) * (1 + fd_cd / 100) - 1) * 100), "flaming_lava"))
    # Athena's Gloves: the direct Attack Speed joins the typed Attack Speed, the dependent Max Damage follows the TOTAL (the block's Actions Per Second includes it)
    star = STARS["athena_gloves"]
    a_d, a_p = art.sv("athena_gloves_attack_speed", star), art.sv("athena_gloves_max_damage_pct_of_attack_speed", star)
    pairs.append(("athena_gloves", dict(attack_speed=20.0, max_damage=130.0), dict(attack_speed=20.0 + a_d, max_damage=130.0 + a_p / 100 * (20.0 + a_d))))
    # Shamaness Marble: the Buff Duration Increase typed into the Inputs (the block adds it to the Fight's buff duration: buff uptimes, the Weaken window, the strip)
    sm = art.sv("shamaness_marble_buff_duration_increase_pct", STARS["shamaness_marble"])
    pairs.append(("shamaness_marble", dict(buff_duration_increase_pct=15.0), dict(buff_duration_increase_pct=15.0 + sm)))
    # Reindeer's Spear: its base Def Pen folded into the typed Def Pen by diminishing returns (the rows' defense reduction AND the boss-branch correction use the total)
    dp = art.sv("reindeer_spear_def_pen", STARS["reindeer_spear"])
    pairs.append(("reindeer_spear", dict(def_pen=35.0), dict(def_pen=100 * (1 - (1 - 35.0 / 100) * (1 - dp / 100)))))
    pairs.append(("star_rock", dict(boss_damage=40.0), dict(boss_damage=40.0 + art.sv("star_rock_boss_damage", STARS["star_rock"]))))
    for key, off_over, on_over, *live in pairs:
        base_slots = [{"key": k, "star": STARS[k]} for k in live]
        slot = base_slots + [{"key": key, "star": STARS[key]}]
        off = sensitivity.run(ilm, _inputs("World Boss", base_slots, **off_over), which="artifacts")["artifacts"]["rows"]
        on = sensitivity.run(ilm, _inputs("World Boss", slot, **on_over), which="artifacts")["artifacts"]["rows"]
        r_off = next(r for r in off if r["key"] == key)
        r_on = next(r for r in on if r["key"] == key)
        t_off = ilm.compute(_inputs("World Boss", base_slots, **off_over))["total_dps"]
        t_on = ilm.compute(_inputs("World Boss", slot, **on_over))["total_dps"]
        assert math.isclose(r_off["dps_gain"], t_on - t_off, rel_tol=1e-9), (key, r_off["dps_gain"], t_on - t_off)      # adding = the true delta
        assert math.isclose(r_on["dps_gain"], r_off["dps_gain"], rel_tol=1e-9), (key, r_off["dps_gain"], r_on["dps_gain"])
        assert math.isclose(r_off["pct_gain"], r_on["pct_gain"], rel_tol=1e-11), (key, r_off["pct_gain"], r_on["pct_gain"])


def test_baked_fd_both_directions_golden():
    """Workbook ground truth (cases I/*): state k has artifacts 1..k equipped with their Final Damage typed into Inputs!final_damage; the toggle row of artifact k read
    in state k-1 (adding) and in state k (removing) gives the identical gain and % Gain, equal to Summary Total(k) - Total(k-1)."""
    if not GOLDEN.exists():
        return
    g = json.loads(GOLDEN.read_text())["cases"]
    for k, art in enumerate(["cursed_doll", "bottle_of_emotion"]):
        u, e = f"I/WB140/{k}", f"I/WB140/{k + 1}"
        if u not in g or e not in g:
            continue
        add, rem = g[u]["workbook"]["toggles"][art], g[e]["workbook"]["toggles"][art]
        true = g[e]["workbook"]["summary"]["total"] - g[u]["workbook"]["summary"]["total"]
        assert math.isclose(add["dps_gain"], rem["dps_gain"], rel_tol=1e-12), (art, add["dps_gain"], rem["dps_gain"])
        assert math.isclose(add["pct_gain"], rem["pct_gain"], rel_tol=1e-13), (art, add["pct_gain"], rem["pct_gain"])
        assert math.isclose(add["dps_gain"], true, rel_tol=1e-12), (art, add["dps_gain"], true)


def test_hooks_are_noops_without_sens():
    TEST.test_hooks_are_noops_without_sens()


def test_api_shape():
    """`which` selection, JSON-serialisable output, the no-effect flag, the potential-gain term, the live Shamaness row and the naive switch."""
    inp = _inputs("World Boss", [{"key": "hexagon_necklace", "star": 5}])
    out = sensitivity.run(ilm, inp, which=["artifacts", "cdr"])
    assert set(out) >= {"artifacts", "cdr", "baseline_total"} and "stats" not in out and "companions" not in out and out["class_id"] == "ice_lightning_mage"
    json.dumps(out)
    rows = {r["key"]: r for r in out["artifacts"]["rows"]}
    assert rows["pigs_ribbon"]["no_dps_effect"] and rows["pigs_ribbon"]["dps_gain"] == 0.0 and rows["pigs_ribbon"]["pct_gain"] == 100.0
    assert rows["hexagon_necklace"]["equipped"] and rows["hexagon_necklace"]["dps_gain"] > 0
    assert rows["shamaness_marble"]["dps_gain"] != 0.0 and not rows["shamaness_marble"]["no_dps_effect"]      # live since the 2026-11-22 builder fix (was inert)
    out2 = sensitivity.run(ilm, dict(inp, artifact_potential_gain={"pigs_ribbon": 1.0e9}), which="artifacts")
    assert {r["key"]: r for r in out2["artifacts"]["rows"]}["pigs_ribbon"]["dps_gain"] == 1.0e9
    naive = sensitivity.run(ilm, inp, which="stats", naive=True)
    assert naive["semantics"] == "naive" and len(naive["stats"]["rows"]) == 27
    keys = [r["key"] for r in naive["stats"]["rows"]]
    assert keys[:3] == ["flat_int", "int_pct", "damage"]
    try:
        sensitivity.run(types.SimpleNamespace(CLASS_ID="no_such_class"), inp)
        raise AssertionError("a class without a spec must raise")
    except NotImplementedError:
        pass


def test_golden():
    TEST.test_golden()


if __name__ == "__main__":
    TEST.main([test_static, test_hooks_are_noops_without_sens, test_api_shape, test_toggle_direction_invariance],
              [test_baked_fd_both_directions_golden],
              "ok: spec == builder, hooks are no-ops, API shape, toggle direction invariance (engine + workbook golden)")
