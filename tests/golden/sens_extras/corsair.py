"""Class-specific sensitivity tests of Corsair (the tests every class repeats - hooks are no-ops, API shape, the equip-toggle direction-invariance loop, the golden - are in
``sens_test_common.py`` / ``test_sensitivity.py``; this module holds what only Corsair has: the spec == builder check, the baked-in artifact pairs and the DATA of the shared tests).
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
from engine.classes import corsair  # noqa: E402
from engine.data import artifacts as AD  # noqa: E402
import sens_compare_generic as C  # noqa: E402
import sens_test_common as SC  # noqa: E402
import patch_2026_11_26  # noqa: E402

TEST = SC.SensTest.from_registry("corsair")
GOLDEN = TEST.GOLDEN
SPEC = sens_specs.get("corsair")


_builder, _inputs = TEST.builder, TEST.inputs


# data of the shared test_api_shape
API = dict(content="Breakthrough", shamaness="positive", naive_rows=28, keys_prefix=['flat_dex', 'dex_pct', 'str', 'damage'], keys_absent=['defense'])
FD_SWEEP = "strip_under"          # shared sweep (sens_test_common.final_damage_sweep)

def test_static():
    """The spec reproduces the builder's tables (so a builder change that is not mirrored in the spec fails here)."""
    assert [t["key"] for t in sensitivity.ARTIFACT_TOGGLES] == list(AD.ARTIFACT_LABELS), "toggle list must come from the engine's artifact table"
    assert sensitivity.supports(corsair) and sensitivity.meta(corsair)["class_id"] == "corsair"
    assert len(sensitivity.stat_sweep(corsair)) == 28 and len(sensitivity.ARTIFACT_TOGGLES) == len(AD.ARTIFACT_LABELS)
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
    TEST.baked_values(full=True)


def toggle_pairs():
    """CLAUDE.md item 15 / checklist 8c, engine-only: the same real state reached from the two directions (artifact equipped with its baked-in stat typed into the
    Inputs, or unequipped with the stat removed) reports the IDENTICAL DPS gain and % gain - in World Boss (pure boss: the time-weighted ratio blend collapses to
    the dollar delta) - and the adding gain equals the true Total delta.  The baked-in artifacts of the chain (Shamaness Marble, Athena's Gloves, Reindeer's Spear, Cursed
    Doll, Bottle of Emotion) are the golden's own states (``corsair_sens_cases.CHAIN``); the rest are built here."""
    from engine import artifacts as art
    from sens_cases import STARS
    import corsair_sens_cases as K
    TEST.chain_invariance("I/WB140", "CHAIN", "CHAIN_PAIRS")
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
    return pairs


def test_baked_chain_golden():
    TEST.baked_chain_golden("I/WB140", "CHAIN_PAIRS")


EXTRA = [test_baked_values]            # engine-only tests of this class
GOLDEN_EXTRA = [test_baked_chain_golden]      # checks of the golden file's own states (run when the file exists)
