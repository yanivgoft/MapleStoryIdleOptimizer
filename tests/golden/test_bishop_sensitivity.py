#!/usr/bin/env python3
"""Golden test: ``engine.sensitivity`` for BISHOP against the Bishop WORKBOOK's Sensitivity sheet (evaluated with ``formulas`` on Sensitivity-slimmed
copies by ``sens_reference_generic.py --class bishop``; numbers frozen in tests/golden/bishop_sensitivity_golden.json).  Plain ``python3``
runnable, also pytest-collectable.  The comparison logic is the class-agnostic ``sens_compare_generic.py`` (a new class's test is a wrapper like this file).

    python3 tests/golden/test_bishop_sensitivity.py              # rel 1e-9 on every compared value; exits 1 on any difference
    python3 tests/golden/test_bishop_sensitivity.py -v --rtol 1e-6
    python3 tests/golden/test_bishop_sensitivity.py --case "S/WB140/a"

Besides the golden: the spec == the builder's tables (STAT_SWEEP, STATUS_REBUILD_KEYS, COMPANION_FULL_SEARCH_KEYS, SUMMON_TIME_KEYS, the passive rows of the Skills sheet, the
cube / equipment / artifact-potential stat maps), the three workbook wirings the Dark Knight port found missing (Shamaness Marble and the Reindeer dose were already wired in this
builder, Athena's Gloves' Attack Speed in the block's Actions Per Second was fixed 2026-11-22), the engine-only direction-invariance of the equip toggles (CLAUDE.md item 15 /
checklist 8c) and the API shape.
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
from engine.classes import bishop  # noqa: E402
from engine.data import artifacts as AD  # noqa: E402
import sens_compare_generic as C  # noqa: E402
import sens_test_common as SC  # noqa: E402

GOLDEN = HERE / "bishop_sensitivity_golden.json"
TEST = SC.SensTest("bishop", bishop, GOLDEN, "Bishop")
SPEC = sens_specs.get("bishop")


_builder, _inputs = TEST.builder, TEST.inputs


def test_static():
    """The spec reproduces the builder's tables (so a builder change that is not mirrored in the spec fails here)."""
    assert [t["key"] for t in sensitivity.ARTIFACT_TOGGLES] == list(AD.ARTIFACT_LABELS), "toggle list must come from the engine's artifact table"
    assert sensitivity.supports(bishop) and sensitivity.meta(bishop)["class_id"] == "bishop"
    assert len(sensitivity.stat_sweep(bishop)) == 29 and len(sensitivity.ARTIFACT_TOGGLES) == 36
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
    # the stat maps of cubes / equipment / artifact potentials (api/features.py reads them from the spec); Invincible makes Defense / Defense % lines real
    m = SPEC.stat_to_key
    assert m["cubes"] == bm.POTENTIAL_STAT_TO_SWEEP_KEY and m["cubes_sub_stat_pct"] == bm.POTENTIAL_SUB_STAT_PCT_LINES == {}
    assert m["equipment"] == bm.EQUIP_COMPARE_STAT_TO_SWEEP_KEY and m["potentials"] == bm.ARTIFACT_POTENTIAL_STAT_TO_SWEEP_KEY
    assert SPEC.mainstat.flat == "flat_int" and SPEC.mainstat.pct == "int_pct" and not SPEC.mainstat.subs
    assert 'f\'((({ib("flat_int")}*(1+{ib("int_pct")}/100))-({IB("flat_int")}*(1+{IB("int_pct")}/100)))\'' in src and 'f\'+0.25*({ib("luk")}-{IB("luk")}))\'' in src
    assert [k for k, _l, _t in bm.STAT_SWEEP_STAT_ENTRIES if k in ("luk", "dex")] == []        # LUK is typed but not a sweep stat: no sub-stat term
    # the three block wirings the Dark Knight port found missing, all present here (a builder change flips these, then flip the spec flag and regenerate the golden)
    assert 'f\'({ib("buff_duration_increase_pct")}+{shamaness_marble_delta_block})\'' in src          # Shamaness Marble's Buff Duration what-if enters bdi_block
    assert "{attack_speed_total_block}/150" in src and "{attack_speed_with_delta}" not in src          # Actions Per Second includes Athena's direct Attack Speed
    assert "*(5000/(6000+{ib(\"monster_defense\")}*(1-{def_pen_total_block}/100)))" in src                 # the rows' K formula reads def_pen_total_block (the Reindeer dose)
    assert "roc_threshold_cr_block = f'({ib(\"crit_rate\")}+{boa_direct_delta}+{rainbow_crit_rate_block})'" in src      # no passive crit delta in the Ring's threshold
    assert "f'=IF(C{me}=TRUE,F{me}+{attack_speed_delta},0)+IF" in src or "=IF(C{me}=TRUE,F{me}+{attack_speed_delta},0)" in src   # Magic Acceleration only while MP Eater is unlocked
    assert SPEC.bdi_toggle_wired and SPEC.reindeer_dose_in_rows and SPEC.athena_as_in_aps and SPEC.pin_monster_defense and SPEC.baked_fd_form == "factor"


def test_toggle_direction_invariance():
    """CLAUDE.md item 15 / checklist 8c, engine-only: the same real state reached from the two directions (artifact equipped with its baked-in stat typed into the
    Inputs, or unequipped with the stat removed) reports the IDENTICAL DPS gain and % gain - in World Boss (pure boss: the time-weighted ratio blend collapses to
    the dollar delta) - and the adding gain equals the true Total delta."""
    from engine import artifacts as art
    from sens_cases import STARS
    pairs = []
    for key in ("hexagon_necklace", "horn_flute", "candle", "secret_map", "alliance_badge", "charm_of_the_undead", "old_music_box", "ring_of_cycles"):
        pairs.append((key, {}, {}))        # live artifacts: no Inputs adjustment
    # Book of Ancient: typed Crit Rate + dependent Crit Damage (pct x the TOTAL crit rate; Bishop has no other live crit-rate source)
    star = STARS["book_of_ancient"]
    cr_d, pct = art.sv("book_of_ancient_crit_rate", star), art.sv("book_of_ancient_crit_damage_pct_of_crit_rate", star)
    assert bishop.model(_inputs("World Boss", [])).crit_rate_bonus == 0.0
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
        off = sensitivity.run(bishop, _inputs("World Boss", base_slots, **off_over), which="artifacts")["artifacts"]["rows"]
        on = sensitivity.run(bishop, _inputs("World Boss", slot, **on_over), which="artifacts")["artifacts"]["rows"]
        r_off = next(r for r in off if r["key"] == key)
        r_on = next(r for r in on if r["key"] == key)
        t_off = bishop.compute(_inputs("World Boss", base_slots, **off_over))["total_dps"]
        t_on = bishop.compute(_inputs("World Boss", slot, **on_over))["total_dps"]
        assert math.isclose(r_off["dps_gain"], t_on - t_off, rel_tol=1e-9), (key, r_off["dps_gain"], t_on - t_off)      # adding = the true delta
        assert math.isclose(r_on["dps_gain"], r_off["dps_gain"], rel_tol=1e-9), (key, r_off["dps_gain"], r_on["dps_gain"])
        assert math.isclose(r_off["pct_gain"], r_on["pct_gain"], rel_tol=1e-11), (key, r_off["pct_gain"], r_on["pct_gain"])


def test_baked_fd_both_directions_golden():
    """Workbook ground truth: ``T/WB140/a`` is the unequipped state, ``T/WB140/eq`` the same state with the Cursed Doll equipped and its Final Damage typed into
    Inputs!final_damage; the Cursed Doll toggle row read in state 0 (adding) and in state 1 (removing) gives the identical gain and % Gain, equal to Summary Total(1) - Total(0)."""
    if not GOLDEN.exists():
        return
    g = json.loads(GOLDEN.read_text())["cases"]
    u, e = "T/WB140/a", "T/WB140/eq"
    if u not in g or e not in g:
        return
    # the potential-line constants of the two cases differ (T/WB140/eq adds 1e9 for the Cursed Doll): compare the part without it
    add, rem = g[u]["workbook"]["toggles"]["cursed_doll"], g[e]["workbook"]["toggles"]["cursed_doll"]
    pot = g[e]["potential"].get("cursed_doll", 0.0)
    true = g[e]["workbook"]["summary"]["total"] - g[u]["workbook"]["summary"]["total"]
    assert math.isclose(add["dps_gain"], true, rel_tol=1e-12), (add["dps_gain"], true)
    assert math.isclose(rem["dps_gain"] - pot, add["dps_gain"], rel_tol=1e-9), (rem["dps_gain"] - pot, add["dps_gain"])


def test_defense_rows_are_plain_reruns():
    """Defense / Defense % / Damage % ... have NO block-only term in the workbook (Invincible's INT share is plain STAT_DAMAGE, no flat-Attack channel): the block equals a
    plain re-run of the model with the value changed (World Boss), while Flat INT / INT % carry the flat-Attack channel (bug 7)."""
    inp = _inputs("World Boss", [{"key": "bottle_of_emotion", "star": 5}])
    diff = {k: v for k, v in sensitivity.semantic_differences(bishop, inp).items() if not math.isclose(v[0], v[1], rel_tol=1e-9)}   # (strip reuse vs re-solve: ~1e-12 noise)
    for key in ("defense", "defense_pct", "damage", "boss_damage", "def_pen", "crit_damage", "final_damage"):
        assert key not in diff, (key, diff[key])
    assert "flat_int" in diff and "int_pct" in diff
    out = sensitivity.run(bishop, inp, which="stats")["stats"]["rows"]
    r = {x["key"]: x for x in out}
    assert r["defense"]["dps_gain"] > 0 and r["defense_pct"]["dps_gain"] > 0       # Invincible: Defense is worth DPS here


def test_pvp_opponent_defense_is_pinned():
    """PvP: the opponent has the main sheet's TOTAL Defense; a Defense / Defense % block must not move it (the workbook's block reads the baseline Inputs cell)."""
    inp = _inputs("PvP", [])
    base = bishop.model(dict(inp))
    for key, new in (("defense", inp["defense"] + 1), ("defense_pct", inp["defense_pct"] + 1)):
        plain = bishop.model(dict(inp, **{key: new}))
        assert plain.monster_defense != base.monster_defense                         # a plain re-run moves the opponent ...
        pinned = bishop.model(dict(inp, **{key: new}, _sens={"monster_defense": base.monster_defense}))
        assert pinned.monster_defense == base.monster_defense and pinned.total_defense == plain.total_defense      # ... the block keeps it, my own Defense still moves


def test_hooks_are_noops_without_sens():
    TEST.test_hooks_are_noops_without_sens()


def test_api_shape():
    """`which` selection, JSON-serialisable output, the no-effect flag, the potential-gain term, the live Shamaness row and the naive switch."""
    inp = _inputs("World Boss", [{"key": "hexagon_necklace", "star": 5}])
    out = sensitivity.run(bishop, inp, which=["artifacts", "cdr"])
    assert set(out) >= {"artifacts", "cdr", "baseline_total"} and "stats" not in out and "companions" not in out and out["class_id"] == "bishop"
    json.dumps(out)
    rows = {r["key"]: r for r in out["artifacts"]["rows"]}
    assert rows["pigs_ribbon"]["no_dps_effect"] and rows["pigs_ribbon"]["dps_gain"] == 0.0 and rows["pigs_ribbon"]["pct_gain"] == 100.0
    assert rows["hexagon_necklace"]["equipped"] and rows["hexagon_necklace"]["dps_gain"] > 0
    assert rows["shamaness_marble"]["dps_gain"] != 0.0 and not rows["shamaness_marble"]["no_dps_effect"]      # live since the 2026-11-22 builder fix (was inert)
    out2 = sensitivity.run(bishop, dict(inp, artifact_potential_gain={"pigs_ribbon": 1.0e9}), which="artifacts")
    assert {r["key"]: r for r in out2["artifacts"]["rows"]}["pigs_ribbon"]["dps_gain"] == 1.0e9
    naive = sensitivity.run(bishop, inp, which="stats", naive=True)
    assert naive["semantics"] == "naive" and len(naive["stats"]["rows"]) == 29
    keys = [r["key"] for r in naive["stats"]["rows"]]
    assert keys[:5] == ["flat_int", "int_pct", "defense", "defense_pct", "damage"]
    try:
        sensitivity.run(types.SimpleNamespace(CLASS_ID="no_such_class"), inp)
        raise AssertionError("a class without a spec must raise")
    except NotImplementedError:
        pass


def test_golden():
    TEST.test_golden()


if __name__ == "__main__":
    TEST.main([test_static, test_hooks_are_noops_without_sens, test_api_shape,
               test_toggle_direction_invariance, test_defense_rows_are_plain_reruns, test_pvp_opponent_defense_is_pinned],
              [test_baked_fd_both_directions_golden],
              "ok: spec == builder, hooks are no-ops, API shape, toggle direction invariance (engine + workbook golden)")
