"""Class-specific sensitivity tests of Bowmaster (the tests every class repeats - hooks are no-ops, API shape, the equip-toggle direction-invariance loop, the golden - are in
``sens_test_common.py`` / ``test_sensitivity.py``; this module holds what only Bowmaster has: the spec == builder check, the baked-in artifact pairs and the DATA of the shared tests).
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
from engine.classes import bowmaster  # noqa: E402
from engine.data import artifacts as AD  # noqa: E402
import sens_compare_generic as C  # noqa: E402
import sens_test_common as SC  # noqa: E402
import patch_2026_11_26  # noqa: E402

TEST = SC.SensTest.from_registry("bowmaster")
GOLDEN = TEST.GOLDEN
SPEC = sens_specs.get("bowmaster")


_builder, _inputs = TEST.builder, TEST.inputs


# data of the shared test_api_shape
API = dict(content="Breakthrough", shamaness="positive", naive_rows=28, keys_prefix=['flat_dex', 'dex_pct', 'str', 'damage'], keys_absent=['defense'])
FD_SWEEP = "plain"          # shared sweep (sens_test_common.final_damage_sweep)

def test_static():
    """The spec reproduces the builder's tables (so a builder change that is not mirrored in the spec fails here)."""
    assert [t["key"] for t in sensitivity.ARTIFACT_TOGGLES] == list(AD.ARTIFACT_LABELS), "toggle list must come from the engine's artifact table"
    assert sensitivity.supports(bowmaster) and sensitivity.meta(bowmaster)["class_id"] == "bowmaster"
    assert len(sensitivity.stat_sweep(bowmaster)) == 28 and len(sensitivity.ARTIFACT_TOGGLES) == len(AD.ARTIFACT_LABELS)
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
    hook_of = {"attack_speed": "attack_speed_extra", "basic_attack_damage": "basic_attack_damage_delta", "min_damage": "min_damage_delta",
               "skill_damage": "skill_damage_delta", "max_damage": "max_damage_delta", "final_damage": "final_damage_delta", "crit_rate": "crit_rate_delta",
               "attack_mult": "attack_mult_delta", "def_pen": "def_pen_delta"}
    expect = sorted((hook_of[slot], rows[key][col["BaseDamage(tenths%)"]], rows[key][col["FactorIndex"]], rows[key][col["JobStep"]], bm.UNLOCK_LEVEL[key])
                    for key, slot in bm.PASSIVE_DELTA_SLOT.items())
    got = patch_2026_11_26.to_workbook('bowmaster', ((p.hook, p.base, p.fidx, p.step, p.unlock) for p in SPEC.passive_levels))   # engine-vs-workbook differences of the 2026-11-26 patch are listed there
    assert expect == got, (expect, got)
    assert all(rows[key][col["ScalesWithLevel"]] is True for key in bm.PASSIVE_DELTA_SLOT)
    # cube / equipment / artifact-potential stat maps (api/features.py reads them from the spec)
    m = SPEC.stat_to_key
    assert m["cubes"] == bm.POTENTIAL_STAT_TO_SWEEP_KEY and m["cubes_sub_stat_pct"] == bm.POTENTIAL_SUB_STAT_PCT_LINES
    assert m["equipment"] == bm.EQUIP_COMPARE_STAT_TO_SWEEP_KEY and m["potentials"] == bm.ARTIFACT_POTENTIAL_STAT_TO_SWEEP_KEY
    assert SPEC.mainstat.flat == "flat_dex" and SPEC.mainstat.pct == "dex_pct" and SPEC.mainstat.subs == (("str", 0.25),)
    # the form this spec reproduces (a builder change flips these asserts, then flip the spec flag and regenerate the golden)
    src = Path(bm.__file__).read_text()
    assert "bdi_block = f'({ib(\"buff_duration_increase_pct\")}+{shamaness_marble_delta_block})'" in src                       # Shamaness Marble wired into the block
    assert "{attack_speed_total_block}/150" in src and "{attack_speed_with_delta}" not in src                                     # Actions Per Second includes Athena's direct AS (fixed 2026-11-22)
    assert "*(5000/(6000+{ib(\"monster_defense\")}*(1-{def_pen_total_block}/100)))" in src                                        # the rows' K formula reads def_pen_total_block
    assert "(1+({ib(\"final_damage\")}+{delta[\"final_damage\"]}+{mortal_blow_bonus_ref})/100)*(1+{agg_final_damage_block}/100)" in src      # baked FD = a factor on the artifact bucket (the whole product)
    assert "def fd_baked_factor(" in src and "final_damage_typed_block" not in src
    assert bm.MULT_KIND_EXTRA_REF == {"final_damage": f"Summary!$B${bm.R_MORTAL_BLOW_BONUS}"} and SPEC.mult_extra == (("final_damage", "mortal_blow_bonus"),)
    assert ("roc_threshold_cr_block = f'({ib(\"crit_rate\")}+{delta[\"crit_rate\"]}+{crit_rate_bonus_ref}+{boa_direct_delta}+{rainbow_crit_rate_block})'" in src)   # the passive crit delta IS in the Ring's threshold
    assert SPEC.bdi_toggle_wired and SPEC.reindeer_dose_in_rows and SPEC.athena_as_in_aps and not SPEC.pin_monster_defense and SPEC.baked_fd_form == "factor"


def test_constants():
    """The baked-in magnitudes hard-coded in bowmaster_sens_cases.py (plain data) equal the artifact tables at the cases' star levels."""
    from engine import artifacts as art
    from sens_cases import STARS
    import bowmaster_sens_cases as M
    assert art.sv("cursed_doll_final_damage", STARS["cursed_doll"]) == M.CURSED_DOLL_FD
    assert art.sv("athena_gloves_attack_speed", STARS["athena_gloves"]) == M.ATHENA_AS
    assert art.sv("athena_gloves_max_damage_pct_of_attack_speed", STARS["athena_gloves"]) == M.ATHENA_MAX_PCT
    assert art.sv("shamaness_marble_buff_duration_increase_pct", STARS["shamaness_marble"]) == M.SHAMANESS_BDI
    assert art.sv("reindeer_spear_def_pen", STARS["reindeer_spear"]) == M.REINDEER_DEF_PEN
    from engine.classes import bowmaster as bm_engine
    from bowmaster_cases import make_inputs
    for ct, lvl in (("World Boss", 140), ("Chapter Hunt", 118)):
        assert bm_engine.model(make_inputs(ct, lvl, M.STATS_S, "blaze")).mortal_blow_bonus == M.MORTAL_BLOW, (ct, lvl)


def toggle_pairs():
    """CLAUDE.md item 15 / checklist 8c, engine-only: the same real state reached from the two directions (artifact equipped with its baked-in stat typed into the
    Inputs, or unequipped with the stat removed) reports the IDENTICAL DPS gain and % gain - in World Boss (pure boss: the time-weighted ratio blend collapses to
    the dollar delta) - and the adding gain equals the true Total delta.  Bowmaster's block wires Reindeer's Spear (Def Pen dose in the rows), Athena's Gloves (direct Attack
    Speed in the Actions Per Second) and Shamaness Marble (Buff Duration), so all three are in the list (the Dark Knight workbook has all three gaps)."""
    from engine import artifacts as art
    from sens_cases import STARS
    pairs = []
    for key in ("hexagon_necklace", "horn_flute", "candle", "secret_map", "alliance_badge", "charm_of_the_undead", "old_music_box", "ring_of_cycles"):
        pairs.append((key, {}, {}))        # live artifacts: no Inputs adjustment
    # Book of Ancient: typed Crit Rate + dependent Crit Damage (pct x the TOTAL crit rate)
    star = STARS["book_of_ancient"]
    cr_d, pct = art.sv("book_of_ancient_crit_rate", star), art.sv("book_of_ancient_crit_damage_pct_of_crit_rate", star)
    pairs.append(("book_of_ancient", dict(crit_rate=60.0, crit_damage=150.0), dict(crit_rate=60.0 + cr_d, crit_damage=150.0 + pct / 100 * (60.0 + cr_d))))
    # Athena's Gloves: typed Attack Speed (direct, ADDED to the typed value in the block's APS) + dependent Max Damage (pct x the total Attack Speed)
    star = STARS["athena_gloves"]
    a_d, a_pct = art.sv("athena_gloves_attack_speed", star), art.sv("athena_gloves_max_damage_pct_of_attack_speed", star)
    pairs.append(("athena_gloves", dict(attack_speed=70.0, max_damage=130.0), dict(attack_speed=70.0 + a_d, max_damage=130.0 + a_pct / 100 * (70.0 + a_d))))
    # Shamaness Marble: typed Buff Duration Increase
    pairs.append(("shamaness_marble", dict(buff_duration_increase_pct=15.0),
                  dict(buff_duration_increase_pct=15.0 + art.sv("shamaness_marble_buff_duration_increase_pct", STARS["shamaness_marble"]))))
    # Reindeer's Spear: its base Def Pen (diminishing returns) typed into Inputs!def_pen next to the live Attack%
    mag = art.sv("reindeer_spear_def_pen", STARS["reindeer_spear"])
    pairs.append(("reindeer_spear", dict(def_pen=35.0), dict(def_pen=100 * (1 - (1 - 35.0 / 100) * (1 - mag / 100)))))
    # Star Rock: typed Boss Damage
    pairs.append(("star_rock", dict(boss_damage=40.0), dict(boss_damage=40.0 + art.sv("star_rock_boss_damage", STARS["star_rock"]))))
    mb = bowmaster.model(_inputs("World Boss", [])).mortal_blow_bonus       # Mortal Blow shares the Final Damage bracket (1 + (typed + Mortal Blow)/100) with the typed value

    def fd_typed(x):                                                           # the typed value that bumps that bracket by the artifact's factor 1 + x/100
        return ((1 + (12.0 + mb) / 100) * (1 + x / 100) - 1) * 100 - mb
    for key in ("cursed_doll", "lit_lamp"):
        fd = art.sv(f"{key}_final_damage", STARS[key])
        pairs.append((key, dict(final_damage=12.0), dict(final_damage=fd_typed(fd))))
    fd_cd = art.sv("cursed_doll_final_damage", STARS["cursed_doll"])          # with a LIVE Final Damage artifact (bucket a > 1) equipped as well
    pairs.append(("cursed_doll", dict(final_damage=12.0), dict(final_damage=fd_typed(fd_cd)), "flaming_lava"))
    return pairs


def test_baked_pairs_golden():
    """Workbook ground truth (the chain T/WB140/a -> doll -> ath -> sham -> rei): every state adds ONE more baked-in artifact - equipped AND its stat typed into the Inputs - to the
    previous one (Cursed Doll's Final Damage as a factor on the Final Damage bracket incl. Mortal Blow, Athena's Gloves' Attack Speed + Max Damage, Shamaness Marble's Buff Duration,
    Reindeer's Spear's Def Pen).  The toggle row read in the state WITHOUT the artifact (adding) and in the state WITH it (removing) give the identical gain, and both equal the
    Summary Total difference of the two states - the toggled-copy test of the two Bowmaster builder fixes (Athena's APS, Shamaness' Buff Duration), of Reindeer's Def Pen in the
    rows and of the typed Final Damage form, in BOTH directions, ratio 1.00000000."""
    if not GOLDEN.exists():
        return
    g = json.loads(GOLDEN.read_text())["cases"]
    chain = ["T/WB140/a", "T/WB140/doll", "T/WB140/ath", "T/WB140/sham", "T/WB140/rei"]
    for art, u, e in zip(("cursed_doll", "athena_gloves", "shamaness_marble", "reindeer_spear"), chain, chain[1:]):
        if u not in g or e not in g:
            continue
        add, rem = g[u]["workbook"]["toggles"][art], g[e]["workbook"]["toggles"][art]
        # (a potential-line constant is added unsigned in both directions; only the doll case carries one)
        pot_add, pot_rem = g[u]["potential"].get(art, 0.0), g[e]["potential"].get(art, 0.0)
        true = g[e]["workbook"]["summary"]["total"] - g[u]["workbook"]["summary"]["total"]
        assert math.isclose(add["dps_gain"] - pot_add, true, rel_tol=1e-12), (art, add["dps_gain"], true)
        assert math.isclose(rem["dps_gain"] - pot_rem, true, rel_tol=1e-12), (art, rem["dps_gain"], pot_rem, true)


EXTRA = [test_constants]            # engine-only tests of this class
GOLDEN_EXTRA = [test_baked_pairs_golden]      # checks of the golden file's own states (run when the file exists)
