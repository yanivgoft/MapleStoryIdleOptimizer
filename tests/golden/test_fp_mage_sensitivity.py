#!/usr/bin/env python3
"""Golden test: ``engine.sensitivity`` against the FP-Mage WORKBOOK's Sensitivity sheet (evaluated with ``formulas`` on Sensitivity-slimmed copies by
``sens_reference.py``; numbers frozen in tests/golden/fp_mage_sensitivity_golden.json).  Plain ``python3`` runnable, also pytest-collectable.

    python3 tests/golden/test_fp_mage_sensitivity.py              # rel 1e-9 on every compared value; exits 1 on any difference
    python3 tests/golden/test_fp_mage_sensitivity.py -v --rtol 1e-6
    python3 tests/golden/test_fp_mage_sensitivity.py --case "S/WB200/a"

Compared per case: the workbook's Summary baselines (Total / boss-only / normal-only); per stat the Sensitivity table row (Units per +1%, Current, New,
Baseline, New Total, DPS Gain, % Gain) and the block's own Total / boss-only / normal-only; per equip toggle the staging row (DPS Gain, % Gain, unlocked) and
the block totals; the CDR milestone table; the Companion Comparison table (gain, % gain, unlocked, rank) and the Summoning-Time breakdown table.
Besides: the ranking order, the engine's no-DPS-effect artifacts (gain 0), potential_line_totals() == companion_model's, and the data-driven toggle list.
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))
from engine import sensitivity  # noqa: E402
from engine.classes import fp_mage  # noqa: E402
from engine.data import artifacts as AD  # noqa: E402

GOLDEN = HERE / "fp_mage_sensitivity_golden.json"
# Workbook numerics: the companion chain's elementwise MIN is written (a+b-ABS(a-b))/2 and a permanent kit effect has the 1e9 "NEVER" sentinel as one
# operand, which loses ~5e-8 absolute of the other operand in double precision.  For a window of whole seconds (D = 30 s, 45 s ...) that is exact, for a
# FRACTIONAL window (summoning time +1% -> 30.3 s, any non-integer increase) a permanent buff's uptime reads 1 - 1.57e-9 in the workbook instead of 1
# (verified cell by cell: the block's atk_c / skill_dmg_c / boss_dmg_c cells are exactly 20/25/8 x (1 - 1.5737e-9) = the formula's (1e9 + W - |1e9 - W|)/2).
# The engine (like src/companion_python_model.py) computes the exact value, so every companion quantity at a fractional window differs from the
# workbook by up to ~2e-9 relative; a DPS GAIN (a small difference of two totals) inherits an absolute error of ~1e-9 x Total.
FRAC_RTOL = 5e-9
FRAC_ATOL = 2e-9          # x Total DPS, on gains


def close(a, b, rtol, atol=0.0):
    if a == b:
        return True
    if a is None or b is None or isinstance(a, str) or isinstance(b, str):
        return a == b
    return abs(a - b) <= rtol * max(abs(a), abs(b)) + atol


def engine_inputs(case):
    d = dict(case["inputs"])
    d["artifact_potential_gain"] = dict(case.get("potential") or {})
    return d


def compare_case(cid, case, rtol):
    wb = case["workbook"]
    inputs = engine_inputs(case)
    inc = inputs.get("companion_summon_time_increase_pct") or 0
    frac_case = (inc % 1 != 0)          # the baseline's own window is fractional
    which = []
    if case["stats"]:
        which.append("stats")
    if case["toggles"]:
        which.append("artifacts")
    if case["cdr"]:
        which.append("cdr")
    if case["tables"]:
        which += ["companions", "summon_time"]
    out = sensitivity.run(fp_mage, inputs, which=which)
    diffs = []
    n = [0]

    def chk(name, wbv, eng, atol=0.0, frac=False, dimensionless=False):
        """atol = absolute slack (dollars unless ``dimensionless``); ``frac`` = the compared quantity depends on a fractional companion window."""
        n[0] += 1
        frac = frac or frac_case
        if frac and atol and not dimensionless:
            atol = max(atol, FRAC_ATOL * base_total)
        if not close(wbv, eng, max(rtol, FRAC_RTOL) if frac else rtol, atol):
            diffs.append((name, wbv, eng))
    # 'which' is a selection: the baseline always comes with it
    base_total = wb["summary"]["total"]
    atol_total = 1e-12 * base_total       # a zero gain is a difference of two huge totals: a few ulp of the total is rounding noise
    chk("baseline.total", base_total, out["baseline_total"])
    chk("baseline.boss_only", wb["summary"]["boss_only"], out["baseline_boss_total"])
    chk("baseline.normal_only", wb["summary"]["normal_only"], out["baseline_normal_total"])
    if "stats" in out:
        rows = {r["key"]: r for r in out["stats"]["rows"]}
        for key, blk in wb["stats"].items():
            r = rows[key]
            fr = key == "companion_summon_time_increase_pct"      # window 30 x (1 + (inc + 1)/100): fractional
            chk(f"stat.{key}.block_total", blk["total"], r["new_total"], frac=fr)
            chk(f"stat.{key}.block_boss", blk["boss"], r["new_boss_total"], frac=fr)
            chk(f"stat.{key}.block_normal", blk["normal"], r["new_normal_total"], frac=fr)
            chk(f"stat.{key}.current", blk["current"], r["current"])
            chk(f"stat.{key}.new", blk["new"], r["new"])
            chk(f"stat.{key}.dps_gain", blk["dps_gain"], r["dps_gain"], atol_total, frac=fr)
            chk(f"stat.{key}.pct_gain", blk["pct_gain"], r["pct_gain"], 1e-12 * 100, frac=fr, dimensionless=True)
            if fr or frac_case:      # 1 / (a gain error of ~1e-9 x Total): compared loosely
                if not isinstance(blk["units_per_1pct"], str):
                    n[0] += 1
                    if not close(blk["units_per_1pct"], r["units_per_1pct"], 1e-4):
                        diffs.append((f"stat.{key}.units_per_1pct", blk["units_per_1pct"], r["units_per_1pct"]))
                continue
            u = blk["units_per_1pct"]
            if isinstance(u, str):                       # "n/a" (no gain)
                chk(f"stat.{key}.units_per_1pct", None, r["units_per_1pct"])
            elif r["units_per_1pct"] is not None and abs(r["pct_gain"] - 100) < 1e-9:
                pass                                     # 1/(tiny rounding noise): not meaningful
            else:
                chk(f"stat.{key}.units_per_1pct", u, r["units_per_1pct"])
    if "artifacts" in out:
        rows = {r["key"]: r for r in out["artifacts"]["rows"]}
        for art, blk in wb["toggles"].items():
            r = rows[art]
            fr = art == "arwens_glass_shoes"       # adds a fractional amount to the summoning window (see FRAC_RTOL)
            chk(f"toggle.{art}.dps_gain", blk["dps_gain"], r["dps_gain"], atol_total, frac=fr)
            chk(f"toggle.{art}.pct_gain", blk["pct_gain"], r["pct_gain"], 1e-12 * 100, frac=fr, dimensionless=True)
            chk(f"toggle.{art}.unlocked", bool(blk["unlocked"]), r["unlocked"])
            if not r["no_dps_effect"]:
                chk(f"toggle.{art}.block_total", blk["total"], r["new_total"], frac=fr)
            if r["no_dps_effect"]:
                chk(f"toggle.{art}.no_dps_effect_gain", case["potential"].get(art, 0.0), r["dps_gain"], atol_total)
        # ranking among the compared toggles: same order as the workbook's pct gain (ties by table position, near-ties ignored)
        order_wb = sorted(wb["toggles"], key=lambda a: -wb["toggles"][a]["pct_gain"])
        pos = {k: i for i, k in enumerate(out["artifacts"]["ranking"])}
        for a_, b_ in zip(order_wb, order_wb[1:]):
            if not (wb["toggles"][a_]["unlocked"] and wb["toggles"][b_]["unlocked"]):
                continue
            pa, pb = wb["toggles"][a_]["pct_gain"], wb["toggles"][b_]["pct_gain"]
            if close(pa, pb, 1e-9):
                continue
            n[0] += 1
            if pos[a_] > pos[b_]:
                diffs.append((f"ranking.{a_}>{b_}", pa, pb))
    if "cdr" in out:
        for blk, r in zip(wb["cdr"], out["cdr"]["rows"]):
            chk(f"cdr.{blk['cdr']}.total", blk["table_total"], r["total_dps"])
            chk(f"cdr.{blk['cdr']}.block_total", blk["total"], r["total_dps"])
            chk(f"cdr.{blk['cdr']}.step", blk["table_step"], r["step_gain"], atol_total)
            chk(f"cdr.{blk['cdr']}.pct", blk["table_pct"], r["pct_gain"], 1e-12 * 100, dimensionless=True)
    if "companions" in out:
        rows = {r["name"]: r for r in out["companions"]["rows"]}
        for c in wb["companions"]:
            r = rows[c["name"]]
            chk(f"companion.{c['name']}.level", c["level"], r["level"])
            chk(f"companion.{c['name']}.gain", c["gain"], r["dps_gain"], atol_total, frac=True)
            chk(f"companion.{c['name']}.pct", c["pct"], r["pct_gain"], 1e-12 * 100, frac=True, dimensionless=True)
            chk(f"companion.{c['name']}.unlocked", bool(c["unlocked"]), r["unlocked"])
            if r["unlocked"]:
                chk(f"companion.{c['name']}.rank", c["rank"], r["rank_position"])
    if "summon_time" in out:
        for blk, r in zip(wb["summon_time"], out["summon_time"]["rows"]):
            x = blk["total_pct"]
            chk(f"summon.{x}.total", x, r["total_pct"])
            # (relative changes between two windows, both fractional: the 1e-9-level artifact of each shows up as an absolute 1e-8 on a ratio)
            for k in ("avg_boss_dps_change", "boss_phase_time_factor", "boss_damage_change"):
                chk(f"summon.{x}.{k}", None if isinstance(blk[k], str) else blk[k], r[k], 1e-8, frac=True, dimensionless=True)
            chk(f"summon.{x}.normal_dps_change", blk["normal_dps_change"], r["normal_dps_change"], 1e-8, frac=True, dimensionless=True)
            chk(f"summon.{x}.weighted_dps_change", blk["weighted_dps_change"], r["weighted_dps_change"], 1e-8, frac=True, dimensionless=True)
    return n[0], diffs


def run(rtol=1e-9, verbose=False, only=None):
    golden = json.loads(GOLDEN.read_text())
    bad, total = {}, 0
    for cid, case in golden["cases"].items():
        if only and cid != only:
            continue
        n, diffs = compare_case(cid, case, rtol)
        total += n
        if verbose:
            print(f"{'ok  ' if not diffs else 'DIFF'} {cid:22s} {n:4d} values", flush=True)
        if diffs:
            bad[cid] = diffs
    return len(golden["cases"]), total, bad


def test_static():
    """Pieces that need no workbook."""
    assert [t["key"] for t in sensitivity.ARTIFACT_TOGGLES] == list(AD.ARTIFACT_LABELS), "toggle list must come from the engine's artifact table"
    assert len(sensitivity.ARTIFACT_TOGGLES) == 36 and len(sensitivity.STAT_SWEEP) == 27
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
    Boss), where the time-weighted ratio blend collapses to the dollar delta.  (Breakthrough / Hero Dungeon blend RELATIVE gains by the time weight, so
    the two directions legitimately differ there.)

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


def test_golden():
    n_cases, n_values, bad = run()
    assert not bad, {k: v[:5] for k, v in bad.items()}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rtol", type=float, default=1e-9)
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--case")
    a = ap.parse_args()
    test_static()
    test_api_shape()
    test_toggle_direction_invariance()
    if GOLDEN.exists():
        test_baked_fd_both_directions_golden()
    print("ok: static pieces, API shape, toggle direction invariance (engine + workbook golden)")
    if not GOLDEN.exists():
        print("no golden file yet")
        sys.exit(1)
    n_cases, n_values, bad = run(a.rtol, a.verbose, a.case)
    for cid, diffs in bad.items():
        for name, wbv, eng in diffs[:25]:
            rel = abs(wbv - eng) / max(abs(wbv), abs(eng), 1e-300) if isinstance(wbv, (int, float)) and isinstance(eng, (int, float)) else float("nan")
            print(f"  {cid}: {name}: workbook {wbv!r} engine {eng!r} rel {rel:.2e}")
    print(f"{'OK' if not bad else 'FAIL'}: {n_cases} cases, {n_values} values compared, {sum(len(v) for v in bad.values())} differences (rtol {a.rtol})")
    sys.exit(1 if bad else 0)
