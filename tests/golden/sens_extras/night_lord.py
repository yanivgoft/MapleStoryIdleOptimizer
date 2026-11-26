"""Class-specific sensitivity tests of Night Lord (the tests every class repeats - hooks are no-ops, API shape, the equip-toggle direction-invariance loop, the golden - are in
``sens_test_common.py`` / ``test_sensitivity.py``; this module holds what only Night Lord has: the spec == builder check, the baked-in artifact pairs and the DATA of the shared tests).
Protocol: see ``sens_test_common.plan``."""
import importlib.util
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))
from engine import sensitivity  # noqa: E402
from engine import sens_specs  # noqa: E402
from engine.classes import night_lord  # noqa: E402
from engine.data import artifacts as AD  # noqa: E402
import sens_compare_generic as C  # noqa: E402
import sens_test_common as SC  # noqa: E402
import patch_2026_11_26  # noqa: E402

TEST = SC.SensTest.from_registry("night_lord")
GOLDEN = TEST.GOLDEN
SPEC = sens_specs.get("night_lord")


_builder, _inputs = TEST.builder, TEST.inputs


# data of the shared test_api_shape
API = dict(content="Breakthrough", shamaness="positive", naive_rows=29, keys_prefix=['flat_luk', 'luk_pct', 'dex', 'damage'], keys_absent=['defense'], keys_last="incoming_hit_rate")

def test_static():
    """The spec reproduces the builder's tables (so a builder change that is not mirrored in the spec fails here)."""
    assert [t["key"] for t in sensitivity.ARTIFACT_TOGGLES] == list(AD.ARTIFACT_LABELS), "toggle list must come from the engine's artifact table"
    assert sensitivity.supports(night_lord) and sensitivity.meta(night_lord)["class_id"] == "night_lord"
    assert len(sensitivity.stat_sweep(night_lord)) == 29 and len(sensitivity.ARTIFACT_TOGGLES) == len(AD.ARTIFACT_LABELS)
    bm = _builder()
    if bm is None:
        return
    assert [(k, l, t) for k, l, t in bm.STAT_SWEEP_STAT_ENTRIES] == [tuple(e) for e in SPEC.stat_list]
    assert list(bm.STATUS_REBUILD_KEYS) == list(patch_2026_11_26.workbook_keys(SPEC.status_rebuild_keys))
    assert tuple(bm.COMPANION_FULL_SEARCH_KEYS) == tuple(patch_2026_11_26.workbook_keys(SPEC.companion_full_search_keys, search=True))
    assert tuple(bm.SUMMON_TIME_KEYS) == tuple(SPEC.summon_time_keys)
    assert list(bm.CDR_SWEEP_VALUES) == list(sensitivity.CDR_SWEEP_VALUES)
    assert list(bm.ARTIFACT_LABELS) == list(AD.WORKBOOK_ARTIFACT_LABELS) and sorted(bm.ARTIFACT_NO_DPS_EFFECT) == sorted(AD.ARTIFACT_NO_DPS_EFFECT)
    # passive-level deltas: every PASSIVE_DELTA_SLOT row is a PassiveLevel with the Skills-sheet row's own (job step, base, factor index) and unlock level
    col = {name: i for i, name in enumerate(bm.SKILL_COLUMNS)}
    rows = {r[col["Key"]]: r for r in bm.SKILL_ROWS}
    hook_of = {"attack_speed": "attack_speed_extra", "basic_attack_damage": "basic_attack_damage_delta", "min_damage": "min_damage_delta", "crit_rate": "crit_rate_delta",
               "final_damage": "final_damage_delta", "attack_mult": "attack_mult_delta", "crit_damage": "crit_damage_delta", "boss_damage": "boss_damage_delta",
               "skill_damage": "skill_damage_delta"}
    expect = sorted((hook_of[slot], rows[key][col["BaseDamage(tenths%)"]], rows[key][col["FactorIndex"]], rows[key][col["JobStep"]], bm.UNLOCK_LEVEL[key])
                    for key, slot in bm.PASSIVE_DELTA_SLOT.items())
    got = patch_2026_11_26.to_workbook('night_lord', ((p.hook, p.base, p.fidx, p.step, p.unlock) for p in SPEC.passive_levels))   # engine-vs-workbook differences of the 2026-11-26 patch are listed there
    assert expect == got, (expect, got)
    assert all(rows[key][col["ScalesWithLevel"]] is True for key in bm.PASSIVE_DELTA_SLOT)
    # cube / equipment / artifact-potential stat maps (api/features.py reads them from the spec)
    m = SPEC.stat_to_key
    assert m["cubes"] == bm.POTENTIAL_STAT_TO_SWEEP_KEY and m["cubes_sub_stat_pct"] == bm.POTENTIAL_SUB_STAT_PCT_LINES
    assert m["equipment"] == bm.EQUIP_COMPARE_STAT_TO_SWEEP_KEY and m["potentials"] == bm.ARTIFACT_POTENTIAL_STAT_TO_SWEEP_KEY
    assert SPEC.mainstat.flat == "flat_luk" and SPEC.mainstat.pct == "luk_pct" and SPEC.mainstat.subs == (("dex", 0.25),)
    # the form this spec reproduces (a builder change flips these asserts, then flip the spec flag and regenerate the golden)
    src = Path(bm.__file__).read_text()
    assert "bdi_block = f'({ib(\"buff_duration_increase_pct\")}+{shamaness_bdi_cell})'" in src and "ws[shamaness_bdi_cell] = f'={shamaness_marble_delta_block}'" in src   # Shamaness Marble wired into EVERY reader of the block's BDI (fixed 2026-11-23)
    assert "{attack_speed_total_block}/150" in src and "{attack_speed_with_delta}" not in src                                     # Actions Per Second includes Athena's direct AS
    assert "athena_gloves_equipped" not in bm.STATUS_REBUILD_KEYS                                                                 # the strip does not read the Actions Per Second: the toggle needs no strip of its own
    assert "*(5000/(6000+{ib(\"monster_defense\")}*(1-{def_pen_total_block}/100)))" in src                                        # the rows' K formula reads def_pen_total_block
    assert "def fd_baked_factor(" in src and "f'=((1+{fd_live_cell}/100)*{csw_factor_block}" in src                               # baked FD = a FACTOR on the live artifact bucket
    assert "(1+({ib(\"final_damage\")}+{delta[\"final_damage\"]})/100)" in src and not hasattr(bm, "MULT_KIND_EXTRA_REF") and SPEC.mult_extra == ()
    assert "roc_threshold_cr_block = f'({ib(\"crit_rate\")}+{delta[\"crit_rate\"]}+{crit_rate_bonus_ref}+{boa_direct_delta}+{rainbow_crit_rate_block})'" in src   # passive crit delta IS in the threshold
    assert "return f'IF({ib(\"level\")}>=107,F{row_of[\"NIGHT_LORDS_MARK\"]},0)'" in src                                        # Assassin's Mark reads the block's OWN Night Lord's Mark row (bug 19)
    assert SPEC.bdi_toggle_wired and SPEC.reindeer_dose_in_rows and SPEC.athena_as_in_aps and not SPEC.pin_monster_defense and SPEC.baked_fd_form == "factor"


def test_baked_values():
    """The constants of the case matrix (plain data) are the artifact tables' values at the case stars."""
    TEST.baked_values(full=True)


def toggle_pairs():
    """CLAUDE.md item 15 / checklist 8c, engine-only: the same real state reached from the two directions (artifact equipped with its baked-in stat typed into the
    Inputs, or unequipped with the stat removed) reports the IDENTICAL DPS gain and % gain - in World Boss (pure boss: the time-weighted ratio blend collapses to
    the dollar delta) - and the adding gain equals the true Total delta.  The baked-in artifacts of the chain (Shamaness Marble, Athena's Gloves, Reindeer's Spear, Cursed
    Doll, Bottle of Emotion) are the golden's own states (``night_lord_sens_cases.CHAIN``); the rest are built here."""
    from engine import artifacts as art
    from sens_cases import STARS
    import night_lord_sens_cases as K
    TEST.chain_invariance("I/WB140", "CHAIN", "CHAIN_PAIRS")
    pairs = []
    for key in ("hexagon_necklace", "horn_flute", "candle", "secret_map", "alliance_badge", "charm_of_the_undead", "old_music_box", "ring_of_cycles"):
        pairs.append((key, {}, {}))        # live artifacts: no Inputs adjustment
    # Book of Ancient: typed Crit Rate + dependent Crit Damage (pct x the TOTAL crit rate, incl. Night Lord's live Critical Throw / Dark Sight (Crit Rate) bonus)
    star = STARS["book_of_ancient"]
    cr_d, pct = art.sv("book_of_ancient_crit_rate", star), art.sv("book_of_ancient_crit_damage_pct_of_crit_rate", star)
    live = night_lord.model(_inputs("World Boss", [], crit_rate=60.0, crit_damage=150.0)).crit_rate_bonus
    assert live > 0
    pairs.append(("book_of_ancient", dict(crit_rate=60.0, crit_damage=150.0), dict(crit_rate=60.0 + cr_d, crit_damage=150.0 + pct / 100 * (60.0 + cr_d + live))))
    # Star Rock: typed Boss Damage
    pairs.append(("star_rock", dict(boss_damage=40.0), dict(boss_damage=40.0 + art.sv("star_rock_boss_damage", STARS["star_rock"]))))
    fd = art.sv("lit_lamp_final_damage", STARS["lit_lamp"])
    pairs.append(("lit_lamp", dict(final_damage=12.0), dict(final_damage=((1 + 12.0 / 100) * (1 + fd / 100) - 1) * 100)))
    fd_cd = art.sv("cursed_doll_final_damage", STARS["cursed_doll"])          # with a LIVE Final Damage artifact (bucket a > 1) equipped as well
    pairs.append(("cursed_doll", dict(final_damage=12.0), dict(final_damage=((1 + 12.0 / 100) * (1 + fd_cd / 100) - 1) * 100), "flaming_lava"))
    return pairs


def test_final_damage_sweep_is_exactly_one_percent():
    """The +1% multiplicative Final Damage step multiplies the typed bracket (Frailty Curse / Alchemic Adrenaline are their own factors, no live additive source shares it):
    the ratio is exactly 1.01 wherever nothing else moves (Chapter Hunt: no timeline strip) and Current / New are the typed value and x1.01 of it.  With the strip on (World Boss)
    the Final Damage change still scales every damage row alike, so the ratio is 1.01 there too (no timing decision depends on it)."""
    inp = _inputs("Chapter Hunt", [{"key": "bottle_of_emotion", "star": 5}], status_effect_damage=0)
    inp.update(companion_choice="None", companion_level=0)
    out = sensitivity.run(night_lord, inp, which="stats")["stats"]["rows"]
    r = next(x for x in out if x["key"] == "final_damage")
    assert math.isclose(r["pct_gain"], 101.0, rel_tol=1e-12), r["pct_gain"]
    assert r["current"] == 12.0 and math.isclose(r["new"], (1.12 * 1.01 - 1) * 100, rel_tol=1e-12)
    wb = sensitivity.run(night_lord, _inputs("World Boss", [{"key": "bottle_of_emotion", "star": 5}]), which="stats")["stats"]["rows"]
    assert math.isclose(next(x for x in wb if x["key"] == "final_damage")["pct_gain"], 101.0, rel_tol=1e-9)


def test_baked_chain_golden():
    TEST.baked_chain_golden("I/WB140", "CHAIN_PAIRS")


FD_SWEEP = test_final_damage_sweep_is_exactly_one_percent          # this class's own sweep
EXTRA = [test_baked_values]            # engine-only tests of this class
GOLDEN_EXTRA = [test_baked_chain_golden]      # checks of the golden file's own states (run when the file exists)
