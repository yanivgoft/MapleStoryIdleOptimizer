#!/usr/bin/env python3
"""Golden test: ``engine.sensitivity`` for CORSAIR against the Corsair WORKBOOK's Sensitivity sheet (evaluated with ``formulas`` on Sensitivity-slimmed copies by
``sens_reference_generic.py --class corsair``; numbers frozen in tests/golden/corsair_sensitivity_golden.json).  Plain ``python3`` runnable, also pytest-collectable.  The
comparison logic is the class-agnostic ``sens_compare_generic.py`` (a new class's test is a wrapper like this file).

    python3 tests/golden/test_corsair_sensitivity.py              # rel 1e-9 on every compared value; exits 1 on any difference
    python3 tests/golden/test_corsair_sensitivity.py -v --rtol 1e-6
    python3 tests/golden/test_corsair_sensitivity.py --case "S/CH74"

Besides the golden: the spec == the builder's tables (STAT_SWEEP, STATUS_REBUILD_KEYS, COMPANION_FULL_SEARCH_KEYS, SUMMON_TIME_KEYS, PASSIVE_DELTA_SLOT and the passive rows'
Skills-sheet data), the engine-only direction-invariance of the equip toggles (CLAUDE.md item 15 / checklist 8c; Reindeer's Spear is wired correctly in the Corsair builder, Athena's Gloves and
Shamaness Marble since 2026-11-22, so they are all in the list), the workbook-side chain I/WB140/* (both directions of five baked-in artifacts: Shamaness Marble,
Athena's Gloves, Reindeer's Spear, Cursed Doll, Bottle of Emotion) and the API shape.
"""
import importlib.util
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))
from engine import sensitivity  # noqa: E402
from engine import sens_specs  # noqa: E402
from engine.classes import corsair  # noqa: E402
from engine.data import artifacts as AD  # noqa: E402
import sens_compare_generic as C  # noqa: E402
import sens_test_common as SC  # noqa: E402

GOLDEN = HERE / "corsair_sensitivity_golden.json"
TEST = SC.SensTest("corsair", corsair, GOLDEN, "Corsair")
SPEC = sens_specs.get("corsair")


_builder, _inputs = TEST.builder, TEST.inputs


def test_static():
    """The spec reproduces the builder's tables (so a builder change that is not mirrored in the spec fails here)."""
    assert [t["key"] for t in sensitivity.ARTIFACT_TOGGLES] == list(AD.ARTIFACT_LABELS), "toggle list must come from the engine's artifact table"
    assert sensitivity.supports(corsair) and sensitivity.meta(corsair)["class_id"] == "corsair"
    assert len(sensitivity.stat_sweep(corsair)) == 28 and len(sensitivity.ARTIFACT_TOGGLES) == 36
    bm = _builder()
    if bm is None:
        return
    assert [(k, l, t) for k, l, t in bm.STAT_SWEEP_STAT_ENTRIES] == [tuple(e) for e in SPEC.stat_list]
    assert list(bm.STATUS_REBUILD_KEYS) == list(SPEC.status_rebuild_keys)
    assert tuple(bm.COMPANION_FULL_SEARCH_KEYS) == tuple(SPEC.companion_full_search_keys)
    assert tuple(bm.SUMMON_TIME_KEYS) == tuple(SPEC.summon_time_keys)
    assert list(bm.CDR_SWEEP_VALUES) == list(sensitivity.CDR_SWEEP_VALUES)
    assert list(bm.ARTIFACT_LABELS) == list(AD.ARTIFACT_LABELS) and sorted(bm.ARTIFACT_NO_DPS_EFFECT) == sorted(AD.ARTIFACT_NO_DPS_EFFECT)
    # passive-level deltas: every PASSIVE_DELTA_SLOT row is a PassiveLevel with the Skills-sheet row's own (job step, base, factor index) and unlock level
    col = {name: i for i, name in enumerate(bm.SKILL_COLUMNS)}
    rows = {r[col["Key"]]: r for r in bm.SKILL_ROWS}
    hook_of = {"attack_speed": "attack_speed_extra", "basic_attack_damage": "basic_attack_damage_delta", "min_damage": "min_damage_delta", "crit_rate": "crit_rate_delta",
               "final_damage": "final_damage_delta", "attack_mult": "attack_mult_delta", "crit_damage": "crit_damage_delta"}
    expect = sorted((hook_of[slot], rows[key][col["BaseDamage(tenths%)"]], rows[key][col["FactorIndex"]], rows[key][col["JobStep"]], bm.UNLOCK_LEVEL[key])
                    for key, slot in bm.PASSIVE_DELTA_SLOT.items())
    got = sorted((p.hook, p.base, p.fidx, p.step, p.unlock) for p in SPEC.passive_levels)
    assert expect == got, (expect, got)
    assert all(rows[key][col["ScalesWithLevel"]] is True for key in bm.PASSIVE_DELTA_SLOT)
    # cube / equipment / artifact-potential stat maps (api/features.py reads them from the spec)
    m = SPEC.stat_to_key
    assert m["cubes"] == bm.POTENTIAL_STAT_TO_SWEEP_KEY and m["cubes_sub_stat_pct"] == bm.POTENTIAL_SUB_STAT_PCT_LINES
    assert m["equipment"] == bm.EQUIP_COMPARE_STAT_TO_SWEEP_KEY and m["potentials"] == bm.ARTIFACT_POTENTIAL_STAT_TO_SWEEP_KEY
    assert SPEC.mainstat.flat == "flat_dex" and SPEC.mainstat.pct == "dex_pct" and SPEC.mainstat.subs == (("str", 0.25),)
    # the form this spec reproduces (a builder change flips these asserts, then flip the spec flag and regenerate the golden)
    src = Path(bm.__file__).read_text()
    assert 'if key == "buff_duration_increase_pct":\n            return bdi_ref' in src and "ws[bdi_ref.replace(\"$\", \"\")] = f'={_ib_in(\"buff_duration_increase_pct\")}+{shamaness_marble_delta_block}'" in src   # Shamaness Marble wired into EVERY reader of the block's BDI (fixed 2026-11-22)
    assert "{attack_speed_total_block}/150" in src and "{attack_speed_with_delta}" not in src                                     # Actions Per Second includes Athena's direct AS (fixed 2026-11-22)
    assert "athena_gloves_equipped" in bm.STATUS_REBUILD_KEYS                                                                     # ... and the toggle re-solves its own strip
    assert "*(5000/(6000+{ib(\"monster_defense\")}*(1-{def_pen_total_block}/100)))" in src                                        # the rows' K formula reads def_pen_total_block
    assert "ws[fd_shift_ref.replace(\"$\", \"\")] = (" in src and "(1+({ib(\"final_damage\")}+{delta[\"final_damage\"]}+{fd_bonus_ref})/100)" in src   # baked FD = a SHIFT of the typed value inside the additive bracket
    assert bm.MULT_KIND_EXTRA_REF == {"final_damage": f"Summary!$B${bm.R_FD_ALL}"} and SPEC.mult_extra == (("final_damage", "final_damage_all"),)
    assert "roc_threshold_cr_block = f'({ib(\"crit_rate\")}+{delta[\"crit_rate\"]}+{crit_rate_bonus_ref}+{boa_direct_delta}+{rainbow_crit_rate_block})'" in src   # passive crit delta IS in the threshold
    assert SPEC.bdi_toggle_wired and SPEC.reindeer_dose_in_rows and SPEC.athena_as_in_aps and not SPEC.pin_monster_defense and SPEC.baked_fd_form == "typed"


def test_baked_values():
    """The constants of the case matrix (plain data) are the artifact tables' values at the case stars."""
    from engine import artifacts as art
    from sens_cases import STARS
    import corsair_sens_cases as K
    assert art.sv("shamaness_marble_buff_duration_increase_pct", STARS["shamaness_marble"]) == K.SHAMANESS_BDI
    assert art.sv("athena_gloves_attack_speed", STARS["athena_gloves"]) == K.ATHENA_AS
    assert art.sv("athena_gloves_max_damage_pct_of_attack_speed", STARS["athena_gloves"]) == K.ATHENA_MAX_PCT
    assert art.sv("reindeer_spear_def_pen", STARS["reindeer_spear"]) == K.REINDEER_DEF_PEN
    assert art.sv("cursed_doll_final_damage", STARS["cursed_doll"]) == K.CURSED_DOLL_FD
    assert art.sv("bottle_of_emotion_final_damage_per_3pct_as", STARS["bottle_of_emotion"]) == K.BOTTLE_PER_3PCT
    assert art.sv("bottle_of_emotion_final_damage_cap", STARS["bottle_of_emotion"]) == K.BOTTLE_CAP


def test_toggle_direction_invariance():
    """CLAUDE.md item 15 / checklist 8c, engine-only: the same real state reached from the two directions (artifact equipped with its baked-in stat typed into the
    Inputs, or unequipped with the stat removed) reports the IDENTICAL DPS gain and % gain - in World Boss (pure boss: the time-weighted ratio blend collapses to
    the dollar delta) - and the adding gain equals the true Total delta.  The baked-in artifacts of the chain (Shamaness Marble, Athena's Gloves, Reindeer's Spear, Cursed
    Doll, Bottle of Emotion) are the golden's own states (``corsair_sens_cases.CHAIN``); the rest are built here."""
    from engine import artifacts as art
    from sens_cases import STARS
    import corsair_sens_cases as K
    cases = {c["id"]: c for c in K.sens_cases()}
    tot, rows = {}, {}
    for suffix, _eq, _flags in K.CHAIN:
        out = sensitivity.run(corsair, cases[f"I/WB140/{suffix}"]["inputs"], which="artifacts")
        tot[suffix] = out["baseline_total"]
        rows[suffix] = {r["key"]: r for r in out["artifacts"]["rows"]}
    for key, add, rem in K.CHAIN_PAIRS:
        true = tot[rem] - tot[add]
        a, r = rows[add][key], rows[rem][key]
        assert math.isclose(a["dps_gain"], true, rel_tol=1e-9), (key, a["dps_gain"], true)             # adding = the true delta
        assert math.isclose(r["dps_gain"], true, rel_tol=1e-9), (key, r["dps_gain"], true)             # removing = the same value
        assert math.isclose(a["pct_gain"], r["pct_gain"], rel_tol=1e-11), (key, a["pct_gain"], r["pct_gain"])
    pairs = []
    for key in ("hexagon_necklace", "horn_flute", "candle", "secret_map", "alliance_badge", "charm_of_the_undead", "old_music_box", "ring_of_cycles"):
        pairs.append((key, {}, {}))        # live artifacts: no Inputs adjustment
    # Book of Ancient: typed Crit Rate + dependent Crit Damage (pct x the TOTAL crit rate)
    star = STARS["book_of_ancient"]
    cr_d, pct = art.sv("book_of_ancient_crit_rate", star), art.sv("book_of_ancient_crit_damage_pct_of_crit_rate", star)
    pairs.append(("book_of_ancient", dict(crit_rate=60.0, crit_damage=150.0), dict(crit_rate=60.0 + cr_d, crit_damage=150.0 + pct / 100 * (60.0 + cr_d))))
    # Star Rock: typed Boss Damage
    pairs.append(("star_rock", dict(boss_damage=40.0), dict(boss_damage=40.0 + art.sv("star_rock_boss_damage", STARS["star_rock"]))))
    fd = art.sv("lit_lamp_final_damage", STARS["lit_lamp"])
    pairs.append(("lit_lamp", dict(final_damage=12.0), dict(final_damage=((1 + 12.0 / 100) * (1 + fd / 100) - 1) * 100)))
    fd_cd = art.sv("cursed_doll_final_damage", STARS["cursed_doll"])          # with a LIVE Final Damage artifact (bucket a > 1) equipped as well
    pairs.append(("cursed_doll", dict(final_damage=12.0), dict(final_damage=((1 + 12.0 / 100) * (1 + fd_cd / 100) - 1) * 100), "flaming_lava"))
    for key, off_over, on_over, *live in pairs:
        base_slots = [{"key": k, "star": STARS[k]} for k in live]
        slot = base_slots + [{"key": key, "star": STARS[key]}]
        off = sensitivity.run(corsair, _inputs("World Boss", base_slots, **off_over), which="artifacts")["artifacts"]["rows"]
        on = sensitivity.run(corsair, _inputs("World Boss", slot, **on_over), which="artifacts")["artifacts"]["rows"]
        r_off = next(r for r in off if r["key"] == key)
        r_on = next(r for r in on if r["key"] == key)
        t_off = corsair.compute(_inputs("World Boss", base_slots, **off_over))["total_dps"]
        t_on = corsair.compute(_inputs("World Boss", slot, **on_over))["total_dps"]
        assert math.isclose(r_off["dps_gain"], t_on - t_off, rel_tol=1e-9), (key, r_off["dps_gain"], t_on - t_off)      # adding = the true delta
        assert math.isclose(r_on["dps_gain"], r_off["dps_gain"], rel_tol=1e-9), (key, r_off["dps_gain"], r_on["dps_gain"])
        assert math.isclose(r_off["pct_gain"], r_on["pct_gain"], rel_tol=1e-11), (key, r_off["pct_gain"], r_on["pct_gain"])


def test_final_damage_sweep_is_exactly_one_percent():
    """The +1% multiplicative Final Damage step bumps the FULL bucket (typed + Jolly Roger + Ahoy Mateys): the ratio is exactly 1.01 wherever
    nothing else moves (Chapter Hunt, no companion: no timeline strip).  With the strip on (World Boss) Jolly Roger is a TIME-VARYING term of the engine's own bucket,
    so the ratio is a little under 1.01 (the workbook does the same)."""
    inp = _inputs("Chapter Hunt", [{"key": "bottle_of_emotion", "star": 5}], status_effect_damage=0)
    inp.update(companion_choice="None", companion_level=0)
    out = sensitivity.run(corsair, inp, which="stats")["stats"]["rows"]
    r = next(x for x in out if x["key"] == "final_damage")
    assert math.isclose(r["pct_gain"], 101.0, rel_tol=1e-12), r["pct_gain"]
    assert r["current"] > 12.0 and r["new"] > r["current"]          # Current / New include the live Final Damage share (like the workbook's table)
    wb = sensitivity.run(corsair, _inputs("World Boss", [{"key": "bottle_of_emotion", "star": 5}]), which="stats")["stats"]["rows"]
    assert 100.9 < next(x for x in wb if x["key"] == "final_damage")["pct_gain"] < 101.0


def test_baked_chain_golden():
    """Workbook ground truth (cases I/WB140/*): state k has the first k chain artifacts equipped with their baked-in stats typed into the Inputs; the toggle row of artifact k
    read in the state without it (adding) and in the state with it (removing) gives the identical gain and % Gain, equal to Summary Total(with) - Total(without) - for Shamaness
    Marble (Buff Duration), Athena's Gloves (Attack Speed + Max Damage), Reindeer's Spear (Def Pen), Bottle of Emotion and Cursed Doll (Final Damage)."""
    if not GOLDEN.exists():
        return
    import corsair_sens_cases as K
    g = json.loads(GOLDEN.read_text())["cases"]
    for art, add_s, rem_s in K.CHAIN_PAIRS:
        u, e = f"I/WB140/{add_s}", f"I/WB140/{rem_s}"
        if u not in g or e not in g:
            continue
        add, rem = g[u]["workbook"]["toggles"][art], g[e]["workbook"]["toggles"][art]
        true = g[e]["workbook"]["summary"]["total"] - g[u]["workbook"]["summary"]["total"]
        assert math.isclose(add["dps_gain"], rem["dps_gain"], rel_tol=1e-9), (art, add["dps_gain"], rem["dps_gain"])
        assert math.isclose(add["pct_gain"], rem["pct_gain"], rel_tol=1e-11), (art, add["pct_gain"], rem["pct_gain"])
        assert math.isclose(add["dps_gain"], true, rel_tol=1e-9), (art, add["dps_gain"], true)


def test_hooks_are_noops_without_sens():
    TEST.test_hooks_are_noops_without_sens()


def _class_without_spec():
    import importlib
    for cid in ("night_lord", "shadower"):
        if sens_specs.get(cid) is None:
            return importlib.import_module(f"engine.classes.{cid}")
    return None


def test_api_shape():
    """`which` selection, JSON-serialisable output, the no-effect flag, the potential-gain term, the live Shamaness row and the naive switch."""
    inp = _inputs("Breakthrough", [{"key": "hexagon_necklace", "star": 5}])
    out = sensitivity.run(corsair, inp, which=["artifacts", "cdr"])
    assert set(out) >= {"artifacts", "cdr", "baseline_total"} and "stats" not in out and "companions" not in out and out["class_id"] == "corsair"
    json.dumps(out)
    rows = {r["key"]: r for r in out["artifacts"]["rows"]}
    assert rows["pigs_ribbon"]["no_dps_effect"] and rows["pigs_ribbon"]["dps_gain"] == 0.0 and rows["pigs_ribbon"]["pct_gain"] == 100.0
    assert rows["hexagon_necklace"]["equipped"] and rows["hexagon_necklace"]["dps_gain"] > 0
    assert rows["shamaness_marble"]["dps_gain"] > 0 and not rows["shamaness_marble"]["no_dps_effect"]      # wired since 2026-11-22 (it was inert before the fix)
    out2 = sensitivity.run(corsair, dict(inp, artifact_potential_gain={"pigs_ribbon": 1.0e9}), which="artifacts")
    assert {r["key"]: r for r in out2["artifacts"]["rows"]}["pigs_ribbon"]["dps_gain"] == 1.0e9
    naive = sensitivity.run(corsair, inp, which="stats", naive=True)
    assert naive["semantics"] == "naive" and len(naive["stats"]["rows"]) == 28
    keys = [r["key"] for r in naive["stats"]["rows"]]
    assert keys[:4] == ["flat_dex", "dex_pct", "str", "damage"] and "defense" not in keys
    other = _class_without_spec()
    if other is not None:
        try:
            sensitivity.run(other, inp)
            raise AssertionError("a class without a spec must raise")
        except NotImplementedError:
            pass


def test_golden():
    TEST.test_golden()


if __name__ == "__main__":
    TEST.main([test_static, test_baked_values, test_hooks_are_noops_without_sens,
               test_api_shape, test_final_damage_sweep_is_exactly_one_percent, test_toggle_direction_invariance],
              [test_baked_chain_golden],
              "ok: spec == builder, hooks are no-ops, API shape, Final Damage +1% exact, toggle direction invariance (engine + workbook golden)")
