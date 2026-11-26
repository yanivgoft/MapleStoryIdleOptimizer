"""Class-specific sensitivity tests of Paladin (the tests every class repeats - hooks are no-ops, API shape, the equip-toggle direction-invariance loop, the golden - are in
``sens_test_common.py`` / ``test_sensitivity.py``; this module holds what only Paladin has: the spec == builder check, the baked-in artifact pairs and the DATA of the shared tests).
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
from engine.classes import paladin  # noqa: E402
from engine.data import artifacts as AD  # noqa: E402
import sens_compare_generic as C  # noqa: E402
import sens_test_common as SC  # noqa: E402
import patch_2026_11_26  # noqa: E402

TEST = SC.SensTest.from_registry("paladin")
GOLDEN = TEST.GOLDEN
SPEC = sens_specs.get("paladin")


_builder, _inputs = TEST.builder, TEST.inputs


# data of the shared test_api_shape
API = dict(content="Breakthrough", shamaness="positive", naive_rows=28, keys_prefix=['flat_str', 'str_pct', 'dex', 'damage'], keys_absent=['defense'])
FD_SWEEP = "strip_under"          # shared sweep (sens_test_common.final_damage_sweep)

def test_static():
    """The spec reproduces the builder's tables (so a builder change that is not mirrored in the spec fails here)."""
    assert [t["key"] for t in sensitivity.ARTIFACT_TOGGLES] == list(AD.ARTIFACT_LABELS), "toggle list must come from the engine's artifact table"
    assert sensitivity.supports(paladin) and sensitivity.meta(paladin)["class_id"] == "paladin"
    assert len(sensitivity.stat_sweep(paladin)) == 28 and len(sensitivity.ARTIFACT_TOGGLES) == len(AD.ARTIFACT_LABELS)
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
    hook_of = {"attack_speed": "attack_speed_extra", "basic_attack_damage": "basic_attack_damage_delta", "min_damage": "min_damage_delta", "attack_mult": "attack_mult_delta",
               "skill_damage": "skill_damage_delta", "max_damage": "max_damage_delta"}
    expect = sorted((hook_of[slot], rows[key][col["BaseDamage(tenths%)"]], rows[key][col["FactorIndex"]], rows[key][col["JobStep"]], bm.UNLOCK_LEVEL[key])
                    for key, slot in bm.PASSIVE_DELTA_SLOT.items())
    got = patch_2026_11_26.to_workbook('paladin', ((p.hook, p.base, p.fidx, p.step, p.unlock) for p in SPEC.passive_levels))   # engine-vs-workbook differences of the 2026-11-26 patch are listed there
    assert expect == got, (expect, got)
    assert all(rows[key][col["ScalesWithLevel"]] is True for key in bm.PASSIVE_DELTA_SLOT)
    # cube / equipment / artifact-potential stat maps (api/features.py reads them from the spec)
    m = SPEC.stat_to_key
    assert m["cubes"] == bm.POTENTIAL_STAT_TO_SWEEP_KEY and m["cubes_sub_stat_pct"] == bm.POTENTIAL_SUB_STAT_PCT_LINES
    assert m["equipment"] == bm.EQUIP_COMPARE_STAT_TO_SWEEP_KEY and m["potentials"] == bm.ARTIFACT_POTENTIAL_STAT_TO_SWEEP_KEY
    assert SPEC.mainstat.flat == "flat_str" and SPEC.mainstat.pct == "str_pct" and SPEC.mainstat.subs == (("dex", 0.25),)
    # the form this spec reproduces (a builder change flips these asserts, then flip the spec flag and regenerate the golden)
    src = Path(bm.__file__).read_text()
    assert "{attack_speed_total_block}/150" in src and "{attack_speed_with_delta}" not in src                                     # Actions Per Second includes Athena's direct AS (fixed 2026-11-22)
    assert "athena_gloves_equipped" in bm.STATUS_REBUILD_KEYS                                                                     # ... and the toggle re-solves its own strip
    assert "bdi_block = f\"$U${row_header + 5}\"" in src and "bdi_formula = f'={ib(\"buff_duration_increase_pct\")}+{shamaness_marble_delta_block}'" in src   # ... through a helper cell (the 8192-character cap)
    assert SPEC.passive_deltas_in_model                                                                                           # the class module computes the (Combat-Orders-averaged) passive deltas
    assert "*(5000/(6000+{ib(\"monster_defense\")}*(1-{def_pen_total_block}/100)))" in src                                        # the rows' K formula reads def_pen_total_block
    assert "fd_typed_formula = " in src and "{ib(\"final_damage\")}+{delta[\"final_damage\"]}+{fd_bonus_ref}" in src              # baked FD retypes the typed value in the additive bucket
    assert bm.MULT_KIND_EXTRA_REF == {"final_damage": f"Summary!$B${bm.R_FD_ALL}"} and SPEC.mult_extra == (("final_damage", "final_damage_all"),)
    assert "roc_threshold_cr_block = f'({ib(\"crit_rate\")}+{delta[\"crit_rate\"]}+{crit_rate_bonus_ref}+{boa_direct_delta}+{rainbow_crit_rate_block})'" in src   # (no passive crit delta in this kit: 0)
    assert SPEC.bdi_toggle_wired and SPEC.reindeer_dose_in_rows and SPEC.athena_as_in_aps and not SPEC.pin_monster_defense and SPEC.baked_fd_form == "typed"


def test_baked_values():
    """The constants of the case matrix (plain data) are the artifact tables' values at the case stars."""
    TEST.baked_values(full=True)


class _no_passive_residual:
    """Context manager: the Sensitivity spec WITHOUT ``passive_deltas_in_model`` - blocks add no (Combat-Orders-averaged) passive-level delta.  A hypothetical used to prove the
    residual is the ONLY difference between a Shamaness Marble block and a toggled copy of the workbook (the passives' baked-in values keep their typed value in the copy)."""

    def __enter__(self):
        import dataclasses
        self.old = sens_specs._cache["paladin"] = sens_specs.get("paladin")
        sens_specs._cache["paladin"] = dataclasses.replace(SPEC, passive_deltas_in_model=False)

    def __exit__(self, *exc):
        sens_specs._cache["paladin"] = self.old


def test_toggle_direction_invariance():
    """CLAUDE.md item 15 / checklist 8c, engine-only: the same real state reached from the two directions (artifact equipped with its baked-in stat typed into the
    Inputs, or unequipped with the stat removed) reports the IDENTICAL DPS gain and % gain - in World Boss (pure boss: the time-weighted ratio blend collapses to
    the dollar delta) - and the adding gain equals the true Total delta.  The baked-in artifacts of the chain (Shamaness Marble, Athena's Gloves, Reindeer's Spear, Cursed
    Doll, Bottle of Emotion) are the golden's own states (``paladin_sens_cases.CHAIN``); the rest are built here."""
    from engine import artifacts as art
    from sens_cases import STARS
    import paladin_sens_cases as K
    cases = {c["id"]: c for c in K.sens_cases()}
    tot, rows, rows_nr = {}, {}, {}
    for suffix, _eq, _flags in K.CHAIN:
        out = sensitivity.run(paladin, cases[f"I/WB140/{suffix}"]["inputs"], which="artifacts")
        tot[suffix] = out["baseline_total"]
        rows[suffix] = {r["key"]: r for r in out["artifacts"]["rows"]}
        with _no_passive_residual():
            rows_nr[suffix] = {r["key"]: r for r in sensitivity.run(paladin, cases[f"I/WB140/{suffix}"]["inputs"], which="artifacts")["artifacts"]["rows"]}
    for key, add, rem in K.CHAIN_PAIRS:
        true = tot[rem] - tot[add]
        # the rows WITHOUT the passive-level residual (see ``_no_passive_residual``) are the exact toggled-copy delta in both directions for every baked-in artifact
        a, r = rows_nr[add][key], rows_nr[rem][key]
        assert math.isclose(a["dps_gain"], true, rel_tol=1e-9), (key, a["dps_gain"], true)             # adding = the true delta
        assert math.isclose(r["dps_gain"], true, rel_tol=1e-9), (key, r["dps_gain"], true)             # removing = the same value
        assert math.isclose(a["pct_gain"], r["pct_gain"], rel_tol=1e-11), (key, a["pct_gain"], r["pct_gain"])
        a, r = rows[add][key], rows[rem][key]
        if key != "shamaness_marble":                  # only a Buff Duration change moves Combat Orders' uptime, hence Parashock Guard's / Paladin Expert's factor: the rows are exact
            assert math.isclose(a["dps_gain"], true, rel_tol=1e-9), (key, a["dps_gain"], true)
            assert math.isclose(r["dps_gain"], true, rel_tol=1e-9), (key, r["dps_gain"], true)
            assert math.isclose(a["pct_gain"], r["pct_gain"], rel_tol=1e-11), (key, a["pct_gain"], r["pct_gain"])
        else:                                          # documented passive-delta residual (KNOWN_GAPS "Paladin Sensitivity port"): +2.8% / +2.7% of the gain, never invariant
            assert 1.0 < a["dps_gain"] / true < 1.05 and 1.0 < r["dps_gain"] / true < 1.05, (a["dps_gain"] / true, r["dps_gain"] / true)
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
        t_off = paladin.compute(_inputs("World Boss", base_slots, **off_over))["total_dps"]
        t_on = paladin.compute(_inputs("World Boss", slot, **on_over))["total_dps"]
        for residual in (False, True):
            def rows_of(inputs):
                return {r["key"]: r for r in sensitivity.run(paladin, inputs, which="artifacts")["artifacts"]["rows"]}
            if residual:
                off, on = rows_of(_inputs("World Boss", base_slots, **off_over)), rows_of(_inputs("World Boss", slot, **on_over))
            else:
                with _no_passive_residual():
                    off, on = rows_of(_inputs("World Boss", base_slots, **off_over)), rows_of(_inputs("World Boss", slot, **on_over))
            r_off, r_on = off[key], on[key]
            if not residual:       # the exact toggled-copy delta, from both directions
                assert math.isclose(r_off["dps_gain"], t_on - t_off, rel_tol=1e-9), (key, r_off["dps_gain"], t_on - t_off)      # adding = the true delta
                assert math.isclose(r_on["dps_gain"], r_off["dps_gain"], rel_tol=1e-9), (key, r_off["dps_gain"], r_on["dps_gain"])
                assert math.isclose(r_off["pct_gain"], r_on["pct_gain"], rel_tol=1e-11), (key, r_off["pct_gain"], r_on["pct_gain"])
            elif key in ("hexagon_necklace", "horn_flute", "candle", "ring_of_cycles", "secret_map", "alliance_badge", "charm_of_the_undead", "old_music_box"):
                # artifacts that move the strip's schedule (Hexagon Necklace's stacks reach Combat Orders' own engine run) carry the documented passive-delta residual (<= ~1%)
                assert 0.97 < r_off["dps_gain"] / (t_on - t_off) < 1.03, (key, r_off["dps_gain"] / (t_on - t_off))
            else:                  # everything else is exact with the residual too
                assert math.isclose(r_off["dps_gain"], t_on - t_off, rel_tol=1e-9), (key, r_off["dps_gain"], t_on - t_off)
                assert math.isclose(r_on["dps_gain"], r_off["dps_gain"], rel_tol=1e-9), (key, r_off["dps_gain"], r_on["dps_gain"])
                assert math.isclose(r_off["pct_gain"], r_on["pct_gain"], rel_tol=1e-11), (key, r_off["pct_gain"], r_on["pct_gain"])


def test_baked_chain_golden():
    TEST.baked_chain_golden("I/WB140", "CHAIN_PAIRS", shamaness_residual=True)


EXTRA = [test_baked_values]            # engine-only tests of this class
GOLDEN_EXTRA = [test_baked_chain_golden]      # checks of the golden file's own states (run when the file exists)
