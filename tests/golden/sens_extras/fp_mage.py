"""Class-specific sensitivity tests of FP-Mage.  FP-Mage is the one class WITHOUT a spec-driven engine sensitivity (``engine/sens_specs``) and without the
``<class>_cases`` / hook plumbing: its API-shape and toggle direction-invariance tests are its own, so they replace the shared ones
(``sens_test_common.plan``).  Its golden comparison is the class-agnostic ``sens_compare_generic.py`` (this file used to carry its own copy; the output was
identical: 36 cases, 2320 values, 0 differences).  Besides: potential_line_totals() == companion_model's and the data-driven toggle list.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))
from engine import sensitivity  # noqa: E402
from engine.classes import fp_mage  # noqa: E402
from engine.data import artifacts as AD  # noqa: E402
import sens_test_common as SC  # noqa: E402

TEST = SC.SensTest.from_registry("fp_mage")
GOLDEN = TEST.GOLDEN


def test_static():
    """Pieces that need no workbook."""
    assert [t["key"] for t in sensitivity.ARTIFACT_TOGGLES] == list(AD.ARTIFACT_LABELS), "toggle list must come from the engine's artifact table"
    assert len(sensitivity.ARTIFACT_TOGGLES) == len(AD.ARTIFACT_LABELS) and len(sensitivity.STAT_SWEEP) == 27
    sys.path.insert(0, str(HERE.parents[1] / "src"))
    try:
        import companion_model as cm      # needs openpyxl (the Excel generator); skipped without it
    except ImportError:
        return
    assert sensitivity.potential_line_totals() == cm.potential_line_totals()
    assert sensitivity.POTENTIAL_LINE_TIERS == cm.POTENTIAL_LINE_TIERS and sensitivity.POTENTIAL_MAX_LINES == cm.POTENTIAL_MAX_LINES


def _inputs_for_invariance(content, artifacts, **over):
    from cases import make_inputs
    from sens_cases import STATS_S
    from sens_cases import STARS
    d = make_inputs(content, 200, STATS_S, "blaze", **over)
    d["artifacts"] = artifacts
    d["artifact_stars"] = dict(STARS)
    return d


def test_toggle_direction_invariance():
    """CLAUDE.md item 15 / checklist 8c, engine-only: the same real state reached from the two directions (artifact equipped with its baked-in stat typed
    into the Inputs, or unequipped with the stat removed) reports the IDENTICAL DPS gain and % gain (to full precision) - in a pure-boss content (World
    Boss), where the time-weighted ratio blend collapses to the dollar delta.  (Breakthrough / Hero Dungeon blend RELATIVE gains by the time weight; since
    2026-11-25 the equipped row inverts the per-branch removal ratios first, so the two directions agree there too: ``tests/golden/test_equip_blended.py``.)

    The baked-in FINAL DAMAGE artifacts (Cursed Doll, Lit Lamp, Clear Spring Water, Soul Pouch, Bottle of Emotion's Final Damage) were once removed ADDITIVELY
    inside the artifact Final Damage bucket (removal gain = (1 + x/100) x adding gain); since 2026-11-19 removal is the exact inverse step of adding
    (a / (a + x/100), a = 1 + live bucket/100), so the pairs below report identical gains and % gains in both directions."""
    import math
    from engine import artifacts as art
    from sens_cases import STARS
    content = "World Boss"
    pairs = []
    for key in ("hexagon_necklace", "horn_flute", "candle", "secret_map", "alliance_badge", "charm_of_the_undead", "old_music_box", "ring_of_cycles"):
        pairs.append((key, {}, {}, 1.0))        # live artifacts: no Inputs adjustment
    star = STARS["reindeer_spear"]
    mag = art.sv("reindeer_spear_def_pen", star)
    pairs.append(("reindeer_spear", dict(def_pen=35.0), dict(def_pen=100 * (1 - (1 - 0.35) * (1 - mag / 100))), 1.0))
    star = STARS["book_of_ancient"]
    cr_d, pct = art.sv("book_of_ancient_crit_rate", star), art.sv("book_of_ancient_crit_damage_pct_of_crit_rate", star)
    pairs.append(("book_of_ancient", dict(crit_rate=60.0, crit_damage=150.0), dict(crit_rate=60.0 + cr_d, crit_damage=150.0 + pct / 100 * (60.0 + cr_d)), 1.0))
    fd = art.sv("cursed_doll_final_damage", STARS["cursed_doll"])
    pairs.append(("cursed_doll", dict(final_damage=12.0), dict(final_damage=((1 + 12.0 / 100) * (1 + fd / 100) - 1) * 100), 1.0))
    fd = art.sv("lit_lamp_final_damage", STARS["lit_lamp"])          # World Boss only
    pairs.append(("lit_lamp", dict(final_damage=12.0), dict(final_damage=((1 + 12.0 / 100) * (1 + fd / 100) - 1) * 100), 1.0))
    # with a LIVE Final Damage artifact (Flaming Lava, bucket a > 1) equipped as well: the baked-in what-if is a factor on the whole product, so the adding gain
    # is still the true delta and the removal still its inverse
    fd_cd = art.sv("cursed_doll_final_damage", STARS["cursed_doll"])
    pairs.append(("cursed_doll", dict(final_damage=12.0), dict(final_damage=((1 + 12.0 / 100) * (1 + fd_cd / 100) - 1) * 100), 1.0, "flaming_lava"))
    for key, off_over, on_over, removal_factor, *live in pairs:
        base_slots = [{"key": k, "star": STARS[k]} for k in live]
        slot = base_slots + [{"key": key, "star": STARS[key]}]
        off = sensitivity.run(fp_mage, _inputs_for_invariance(content, base_slots, **off_over), which="artifacts")["artifacts"]["rows"]
        on = sensitivity.run(fp_mage, _inputs_for_invariance(content, slot, **on_over), which="artifacts")["artifacts"]["rows"]
        r_off = next(r for r in off if r["key"] == key)
        r_on = next(r for r in on if r["key"] == key)
        t_off = fp_mage.compute(_inputs_for_invariance(content, base_slots, **off_over))["total_dps"]
        t_on = fp_mage.compute(_inputs_for_invariance(content, slot, **on_over))["total_dps"]
        assert math.isclose(r_off["dps_gain"], t_on - t_off, rel_tol=1e-9), (key, r_off["dps_gain"], t_on - t_off)      # adding = the true delta
        assert math.isclose(r_on["dps_gain"], removal_factor * r_off["dps_gain"], rel_tol=1e-9), (key, r_off["dps_gain"], r_on["dps_gain"])
        if removal_factor == 1.0:
            assert math.isclose(r_off["pct_gain"], r_on["pct_gain"], rel_tol=1e-11), (key, r_off["pct_gain"], r_on["pct_gain"])


def test_baked_fd_both_directions_golden():
    """Workbook ground truth (cases I/*): state k has artifacts 1..k equipped with their Final Damage typed into Inputs!final_damage; the toggle row of artifact k read in
    state k-1 (adding) and in state k (removing) gives the identical gain and % Gain, equal to Summary Total(k) - Total(k-1)."""
    import math
    g = json.loads(GOLDEN.read_text())["cases"]

    def pair(u, e, art):
        wu, we = g[u]["workbook"], g[e]["workbook"]
        add, rem = wu["toggles"][art], we["toggles"][art]
        true = we["summary"]["total"] - wu["summary"]["total"]
        assert math.isclose(add["dps_gain"], rem["dps_gain"], rel_tol=1e-12), (art, add["dps_gain"], rem["dps_gain"])
        assert math.isclose(add["pct_gain"], rem["pct_gain"], rel_tol=1e-13), (art, add["pct_gain"], rem["pct_gain"])
        assert math.isclose(add["dps_gain"], true, rel_tol=1e-12), (art, add["dps_gain"], true)
    for k, art in enumerate(["cursed_doll", "lit_lamp", "bottle_of_emotion"]):
        pair(f"I/WB200/{k}", f"I/WB200/{k + 1}", art)
    pair("I/ED140/0", "I/ED140/1", "clear_spring_water")
    pair("I/PvP140/0", "I/PvP140/1", "soul_pouch")


def test_api_shape():
    """`which` selection, JSON-serialisable output, the no-effect flag, the potential-gain term and the naive switch."""
    from cases import make_inputs
    from sens_cases import STATS_S
    inp = make_inputs("Breakthrough", 140, STATS_S, "blaze")
    inp["artifacts"] = [{"key": "hexagon_necklace", "star": 5}]
    out = sensitivity.run(fp_mage, inp, which=["artifacts", "cdr"])
    assert set(out) >= {"artifacts", "cdr", "baseline_total"} and "stats" not in out and "companions" not in out
    json.dumps(out)
    rows = {r["key"]: r for r in out["artifacts"]["rows"]}
    assert rows["pigs_ribbon"]["no_dps_effect"] and rows["pigs_ribbon"]["dps_gain"] == 0.0 and rows["pigs_ribbon"]["pct_gain"] == 100.0
    assert rows["hexagon_necklace"]["equipped"] and rows["hexagon_necklace"]["dps_gain"] > 0
    inp2 = dict(inp, artifact_potential_gain={"pigs_ribbon": 1.0e9})
    out2 = sensitivity.run(fp_mage, inp2, which="artifacts")
    assert {r["key"]: r for r in out2["artifacts"]["rows"]}["pigs_ribbon"]["dps_gain"] == 1.0e9
    naive = sensitivity.run(fp_mage, inp, which="stats", naive=True)
    assert naive["semantics"] == "naive" and len(naive["stats"]["rows"]) == 27


HOOKS = False                       # no ``fp_mage_cases`` module: the hooks-are-no-ops test does not apply
GOLDEN_EXTRA = [test_baked_fd_both_directions_golden]
