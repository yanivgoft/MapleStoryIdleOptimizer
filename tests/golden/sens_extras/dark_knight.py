"""Class-specific sensitivity tests of Dark Knight (the tests every class repeats - hooks are no-ops, API shape, the equip-toggle direction-invariance loop, the golden - are in
``sens_test_common.py`` / ``test_sensitivity.py``; this module holds what only Dark Knight has: the spec == builder check, the baked-in artifact pairs and the DATA of the shared tests).
Protocol: see ``sens_test_common.plan``."""
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
from engine.classes import dark_knight  # noqa: E402
from engine.data import artifacts as AD  # noqa: E402
import sens_compare_generic as C  # noqa: E402
import sens_test_common as SC  # noqa: E402
import patch_2026_11_26  # noqa: E402

TEST = SC.SensTest.from_registry("dark_knight")
GOLDEN = TEST.GOLDEN
SPEC = sens_specs.get("dark_knight")


_builder, _inputs = TEST.builder, TEST.inputs


# data of the shared test_api_shape
API = dict(content="Breakthrough", shamaness="positive", naive_rows=30, keys_prefix=['flat_str', 'str_pct', 'dex', 'defense', 'defense_pct'], keys_absent=[])

def test_static():
    """The spec reproduces the builder's tables (so a builder change that is not mirrored in the spec fails here)."""
    assert [t["key"] for t in sensitivity.ARTIFACT_TOGGLES] == list(AD.ARTIFACT_LABELS), "toggle list must come from the engine's artifact table"
    assert sensitivity.supports(dark_knight) and sensitivity.meta(dark_knight)["class_id"] == "dark_knight"
    assert len(sensitivity.stat_sweep(dark_knight)) == 30 and len(sensitivity.ARTIFACT_TOGGLES) == len(AD.ARTIFACT_LABELS)
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
    hook_of = {"attack_speed": "attack_speed_extra", "min_damage": "min_damage_delta", "skill_damage": "skill_damage_delta", "max_damage": "max_damage_delta",
               "final_damage": "final_damage_delta"}
    expect = sorted((hook_of[slot], rows[key][col["BaseDamage(tenths%)"]], rows[key][col["FactorIndex"]], rows[key][col["JobStep"]], bm.UNLOCK_LEVEL[key])
                    for key, slot in bm.PASSIVE_DELTA_SLOT.items())
    got = patch_2026_11_26.to_workbook('dark_knight', ((p.hook, p.base, p.fidx, p.step, p.unlock) for p in SPEC.passive_levels))   # engine-vs-workbook differences of the 2026-11-26 patch are listed there
    assert expect == got, (expect, got)
    assert all(rows[key][col["ScalesWithLevel"]] is True for key in bm.PASSIVE_DELTA_SLOT)
    # cube / equipment / artifact-potential stat maps (api/features.py reads them from the spec)
    m = SPEC.stat_to_key
    assert m["cubes"] == bm.POTENTIAL_STAT_TO_SWEEP_KEY and m["cubes_sub_stat_pct"] == bm.POTENTIAL_SUB_STAT_PCT_LINES
    assert m["equipment"] == bm.EQUIP_COMPARE_STAT_TO_SWEEP_KEY and m["potentials"] == bm.ARTIFACT_POTENTIAL_STAT_TO_SWEEP_KEY
    assert SPEC.mainstat.flat == "flat_str" and SPEC.mainstat.pct == "str_pct"
    # the form this spec reproduces (a builder change flips these asserts, then flip the spec flag and regenerate the golden); the three gaps below were fixed 2026-11-23
    src = Path(bm.__file__).read_text()
    assert "bdi_formula = f'={ib(\"buff_duration_increase_pct\")}+{shamaness_marble_delta_block}'" in src and "bdi_block = f\"$U${row_header + 5}\"" in src   # Shamaness Marble wired into the block
    assert "{attack_speed_total_block}/150" in src and "{attack_speed_with_delta}" not in src                                   # Actions Per Second includes Athena's direct AS
    assert "athena_gloves_equipped" not in bm.STATUS_REBUILD_KEYS            # engine experiment 2026-11-23: strip reuse == re-solve for the gloves (no timing input moves with Attack Speed)
    assert "*(5000/(6000+{ib(\"monster_defense\")}*(1-{def_pen_total_block}/100)))" in src                                      # the rows' K formula reads def_pen_total_block
    assert SPEC.bdi_toggle_wired and SPEC.pin_monster_defense and SPEC.reindeer_dose_in_rows and SPEC.athena_as_in_aps


def test_baked_values():
    """The constants of the case matrix (plain data) are the artifact tables' values at the case stars."""
    TEST.baked_values(full=False)


def toggle_pairs():
    """CLAUDE.md item 15 / checklist 8c, engine-only: the same real state reached from the two directions (artifact equipped with its baked-in stat typed into the
    Inputs, or unequipped with the stat removed) reports the IDENTICAL DPS gain and % gain - in World Boss (pure boss: the time-weighted ratio blend collapses to
    the dollar delta) - and the adding gain equals the true Total delta.  Reindeer's Spear is NOT in the list: the Dark Knight workbook's block does not apply the
    spear's base Def Pen dose to the rows (the gap was fixed 2026-11-23); Shamaness Marble, Athena's Gloves and Reindeer's Spear are the golden's own chain states
    (``dark_knight_sens_cases.J_CHAIN``), the rest are built here."""
    from engine import artifacts as art
    from sens_cases import STARS
    import dark_knight_sens_cases as K
    TEST.chain_invariance("J/WB140", "J_CHAIN", "J_PAIRS")
    pairs = []
    for key in ("hexagon_necklace", "horn_flute", "candle", "secret_map", "alliance_badge", "charm_of_the_undead", "old_music_box", "ring_of_cycles"):
        pairs.append((key, {}, {}))        # live artifacts: no Inputs adjustment
    # Book of Ancient: typed Crit Rate + dependent Crit Damage (pct x the TOTAL crit rate, which includes Lord of Darkness' live bonus)
    star = STARS["book_of_ancient"]
    cr_d, pct = art.sv("book_of_ancient_crit_rate", star), art.sv("book_of_ancient_crit_damage_pct_of_crit_rate", star)
    lord = dark_knight.model(_inputs("World Boss", [])).crit_rate_bonus
    pairs.append(("book_of_ancient", dict(crit_rate=60.0, crit_damage=150.0), dict(crit_rate=60.0 + cr_d, crit_damage=150.0 + pct / 100 * (60.0 + cr_d + lord))))
    for key in ("cursed_doll", "lit_lamp"):
        fd = art.sv(f"{key}_final_damage", STARS[key])
        pairs.append((key, dict(final_damage=12.0), dict(final_damage=((1 + 12.0 / 100) * (1 + fd / 100) - 1) * 100)))
    fd_cd = art.sv("cursed_doll_final_damage", STARS["cursed_doll"])          # with a LIVE Final Damage artifact (bucket a > 1) equipped as well
    pairs.append(("cursed_doll", dict(final_damage=12.0), dict(final_damage=((1 + 12.0 / 100) * (1 + fd_cd / 100) - 1) * 100), "flaming_lava"))
    return pairs


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


def test_baked_chain_golden():
    TEST.baked_chain_golden("J/WB140", "J_PAIRS")


EXTRA = [test_baked_values]            # engine-only tests of this class
GOLDEN_EXTRA = [test_baked_fd_both_directions_golden, test_baked_chain_golden]      # checks of the golden file's own states (run when the file exists)
