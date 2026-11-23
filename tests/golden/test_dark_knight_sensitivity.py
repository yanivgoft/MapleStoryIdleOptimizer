#!/usr/bin/env python3
"""Golden test: ``engine.sensitivity`` for DARK KNIGHT against the Dark Knight WORKBOOK's Sensitivity sheet (evaluated with ``formulas`` on Sensitivity-slimmed
copies by ``sens_reference_generic.py --class dark_knight``; numbers frozen in tests/golden/dark_knight_sensitivity_golden.json).  Plain ``python3`` runnable, also
pytest-collectable.  The comparison logic is the class-agnostic ``sens_compare_generic.py`` (a new class's test is a wrapper like this file).

    python3 tests/golden/test_dark_knight_sensitivity.py              # rel 1e-9 on every compared value; exits 1 on any difference
    python3 tests/golden/test_dark_knight_sensitivity.py -v --rtol 1e-6
    python3 tests/golden/test_dark_knight_sensitivity.py --case "S/WB140/a"

Besides the golden: the spec == the builder's tables (STAT_SWEEP, STATUS_REBUILD_KEYS, COMPANION_FULL_SEARCH_KEYS, SUMMON_TIME_KEYS, PASSIVE_DELTA_SLOT and the
passive rows' Skills-sheet data), the engine-only direction-invariance of the equip toggles (CLAUDE.md item 15 / checklist 8c) and the API shape.
"""
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
from engine.classes import dark_knight  # noqa: E402
from engine.data import artifacts as AD  # noqa: E402
import sens_compare_generic as C  # noqa: E402
import sens_test_common as SC  # noqa: E402

GOLDEN = HERE / "dark_knight_sensitivity_golden.json"
TEST = SC.SensTest("dark_knight", dark_knight, GOLDEN, "Dark Knight")
SPEC = sens_specs.get("dark_knight")


_builder, _inputs = TEST.builder, TEST.inputs


def test_static():
    """The spec reproduces the builder's tables (so a builder change that is not mirrored in the spec fails here)."""
    assert [t["key"] for t in sensitivity.ARTIFACT_TOGGLES] == list(AD.ARTIFACT_LABELS), "toggle list must come from the engine's artifact table"
    assert sensitivity.supports(dark_knight) and sensitivity.meta(dark_knight)["class_id"] == "dark_knight"
    assert len(sensitivity.stat_sweep(dark_knight)) == 30 and len(sensitivity.ARTIFACT_TOGGLES) == 36
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
    hook_of = {"attack_speed": "attack_speed_extra", "min_damage": "min_damage_delta", "skill_damage": "skill_damage_delta", "max_damage": "max_damage_delta",
               "final_damage": "final_damage_delta"}
    expect = sorted((hook_of[slot], rows[key][col["BaseDamage(tenths%)"]], rows[key][col["FactorIndex"]], rows[key][col["JobStep"]], bm.UNLOCK_LEVEL[key])
                    for key, slot in bm.PASSIVE_DELTA_SLOT.items())
    got = sorted((p.hook, p.base, p.fidx, p.step, p.unlock) for p in SPEC.passive_levels)
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
    from engine import artifacts as art
    from sens_cases import STARS
    import dark_knight_sens_cases as K
    assert art.sv("shamaness_marble_buff_duration_increase_pct", STARS["shamaness_marble"]) == K.SHAMANESS_BDI
    assert art.sv("athena_gloves_attack_speed", STARS["athena_gloves"]) == K.ATHENA_AS
    assert art.sv("athena_gloves_max_damage_pct_of_attack_speed", STARS["athena_gloves"]) == K.ATHENA_MAX_PCT
    assert art.sv("reindeer_spear_def_pen", STARS["reindeer_spear"]) == K.REINDEER_DEF_PEN


def test_toggle_direction_invariance():
    """CLAUDE.md item 15 / checklist 8c, engine-only: the same real state reached from the two directions (artifact equipped with its baked-in stat typed into the
    Inputs, or unequipped with the stat removed) reports the IDENTICAL DPS gain and % gain - in World Boss (pure boss: the time-weighted ratio blend collapses to
    the dollar delta) - and the adding gain equals the true Total delta.  Reindeer's Spear is NOT in the list: the Dark Knight workbook's block does not apply the
    spear's base Def Pen dose to the rows (the gap was fixed 2026-11-23); Shamaness Marble, Athena's Gloves and Reindeer's Spear are the golden's own chain states
    (``dark_knight_sens_cases.J_CHAIN``), the rest are built here."""
    from engine import artifacts as art
    from sens_cases import STARS
    import dark_knight_sens_cases as K
    cases = {c["id"]: c for c in K.sens_cases()}
    tot, rows = {}, {}
    for suffix, _eq, _flags in K.J_CHAIN:
        out = sensitivity.run(dark_knight, cases[f"J/WB140/{suffix}"]["inputs"], which="artifacts")
        tot[suffix] = out["baseline_total"]
        rows[suffix] = {r["key"]: r for r in out["artifacts"]["rows"]}
    for key, add, rem in K.J_PAIRS:
        true = tot[rem] - tot[add]
        a, r = rows[add][key], rows[rem][key]
        assert math.isclose(a["dps_gain"], true, rel_tol=1e-9), (key, a["dps_gain"], true)             # adding = the true delta
        assert math.isclose(r["dps_gain"], true, rel_tol=1e-9), (key, r["dps_gain"], true)             # removing = the same value
        assert math.isclose(a["pct_gain"], r["pct_gain"], rel_tol=1e-11), (key, a["pct_gain"], r["pct_gain"])
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
    for key, off_over, on_over, *live in pairs:
        base_slots = [{"key": k, "star": STARS[k]} for k in live]
        slot = base_slots + [{"key": key, "star": STARS[key]}]
        off = sensitivity.run(dark_knight, _inputs("World Boss", base_slots, **off_over), which="artifacts")["artifacts"]["rows"]
        on = sensitivity.run(dark_knight, _inputs("World Boss", slot, **on_over), which="artifacts")["artifacts"]["rows"]
        r_off = next(r for r in off if r["key"] == key)
        r_on = next(r for r in on if r["key"] == key)
        t_off = dark_knight.compute(_inputs("World Boss", base_slots, **off_over))["total_dps"]
        t_on = dark_knight.compute(_inputs("World Boss", slot, **on_over))["total_dps"]
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


def test_baked_chain_golden():
    """Workbook ground truth (cases J/WB140/*): state k has the first k chain artifacts equipped with their baked-in stats typed into the Inputs; the toggle row of artifact k
    read in the state without it (adding) and in the state with it (removing) gives the identical gain and % Gain, equal to Summary Total(with) - Total(without) - for Shamaness
    Marble (Buff Duration), Athena's Gloves (Attack Speed + Max Damage) and Reindeer's Spear (Def Pen)."""
    if not GOLDEN.exists():
        return
    import dark_knight_sens_cases as K
    g = json.loads(GOLDEN.read_text())["cases"]
    for art, add_s, rem_s in K.J_PAIRS:
        u, e = f"J/WB140/{add_s}", f"J/WB140/{rem_s}"
        if u not in g or e not in g:
            continue
        add, rem = g[u]["workbook"]["toggles"][art], g[e]["workbook"]["toggles"][art]
        true = g[e]["workbook"]["summary"]["total"] - g[u]["workbook"]["summary"]["total"]
        assert math.isclose(add["dps_gain"], rem["dps_gain"], rel_tol=1e-9), (art, add["dps_gain"], rem["dps_gain"])
        assert math.isclose(add["pct_gain"], rem["pct_gain"], rel_tol=1e-11), (art, add["pct_gain"], rem["pct_gain"])
        assert math.isclose(add["dps_gain"], true, rel_tol=1e-9), (art, add["dps_gain"], true)


def test_hooks_are_noops_without_sens():
    TEST.test_hooks_are_noops_without_sens()


def test_api_shape():
    """`which` selection, JSON-serialisable output, the no-effect flag, the potential-gain term, the live Shamaness row and the naive switch."""
    inp = _inputs("Breakthrough", [{"key": "hexagon_necklace", "star": 5}])
    out = sensitivity.run(dark_knight, inp, which=["artifacts", "cdr"])
    assert set(out) >= {"artifacts", "cdr", "baseline_total"} and "stats" not in out and "companions" not in out and out["class_id"] == "dark_knight"
    json.dumps(out)
    rows = {r["key"]: r for r in out["artifacts"]["rows"]}
    assert rows["pigs_ribbon"]["no_dps_effect"] and rows["pigs_ribbon"]["dps_gain"] == 0.0 and rows["pigs_ribbon"]["pct_gain"] == 100.0
    assert rows["hexagon_necklace"]["equipped"] and rows["hexagon_necklace"]["dps_gain"] > 0
    assert rows["shamaness_marble"]["dps_gain"] > 0.0 and not rows["shamaness_marble"]["no_dps_effect"]      # live since 2026-11-23 (the block used to ignore the toggle)
    out2 = sensitivity.run(dark_knight, dict(inp, artifact_potential_gain={"pigs_ribbon": 1.0e9}), which="artifacts")
    assert {r["key"]: r for r in out2["artifacts"]["rows"]}["pigs_ribbon"]["dps_gain"] == 1.0e9
    naive = sensitivity.run(dark_knight, inp, which="stats", naive=True)
    assert naive["semantics"] == "naive" and len(naive["stats"]["rows"]) == 30
    keys = [r["key"] for r in naive["stats"]["rows"]]
    assert keys[:5] == ["flat_str", "str_pct", "dex", "defense", "defense_pct"]
    for cid in ("shadower", "night_lord"):      # a class without a spec must raise (a ported class is skipped: none may be left)
        if sens_specs.get(cid) is not None:
            continue
        try:
            sensitivity.run(__import__(f"engine.classes.{cid}", fromlist=["x"]), inp)
            raise AssertionError("a class without a spec must raise")
        except NotImplementedError:
            pass


def test_golden():
    TEST.test_golden()


if __name__ == "__main__":
    TEST.main([test_static, test_baked_values, test_hooks_are_noops_without_sens, test_api_shape, test_toggle_direction_invariance],
              [test_baked_fd_both_directions_golden, test_baked_chain_golden],
              "ok: spec == builder, hooks are no-ops, API shape, toggle direction invariance (engine + workbook golden)")
