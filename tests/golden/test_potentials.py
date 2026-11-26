#!/usr/bin/env python3
"""Golden test: ``engine.potentials`` (artifact potential lines) against the REAL ``ArtifactsInput`` sheet of the builder.

``tests/golden/tiny_golden.json`` (``tiny_reference.py``) freezes what the ``formulas`` package computed for that sheet (built by
``build_artifacts_input_sheet``) in a tiny standalone workbook: 10 cases x all 36 artifacts with varied Star Levels (Not Unlocked, 0-5), rarities and stats
(duplicate stats inside one artifact, unpriced stats, "(none)"), stub Total DPS / Sensitivity!H rates and varied equip-slot pickers.  Compared (rel 1e-9): each
line's DPS Gain, Total Potential DPS Gain, Equipped? and resolved Star Level.  Plain ``python3`` runnable, also pytest-collectable.

    python3 tests/golden/test_potentials.py [-v] [--rtol 1e-12]

Also checked: the ``artifact_potential_gain`` hook (``engine.sensitivity`` adds it, unsigned, to the artifact's equip row), ``potential_line_totals()`` of the
sensitivity module == ``src/companion_model``'s and consistent with the boots roll table of ``engine.cubes``, and the data tables == the builder's.
"""
import argparse
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from engine import potentials  # noqa: E402
from engine.data import artifacts as AD  # noqa: E402
sys.path.insert(0, str(HERE))
import factor_mode  # noqa: E402

FACTOR_MODE = factor_mode.pin("legacy")        # workbook-derived golden: skill levels clamp at 300 (engine/common/factors.py)

TINY = HERE / "tiny_golden.json"


def close(a, b, rtol, atol=1e-9):
    if a == b:
        return True
    return abs(a - b) <= rtol * max(abs(a), abs(b)) + atol


def engine_state(case):
    return {art: {"star": case["stars"][art], "lines": [tuple(x) for x in case["lines"][art]]} for art in case["stars"]}


def run(rtol=1e-9, verbose=False):
    t = json.loads(TINY.read_text())
    n, bad = 0, []
    for cid, case in t["cases"].items():
        state = engine_state(case)
        table = {r["key"]: r for r in potentials.potential_table(state, case["H"], case["total"], case["slots"])}
        hook = potentials.potential_gains(state, case["H"], case["total"])
        for art, g in t["results"][cid]["artifacts"].items():
            e = table[art]
            for i, (gg, el) in enumerate(zip(g["gains"], e["lines"])):
                n += 1
                if not close(float(gg), el["gain"], rtol):
                    bad.append((cid, art, f"line{i + 1} gain", gg, el["gain"]))
            n += 1
            if len(g["gains"]) != len(e["lines"]):
                bad.append((cid, art, "line count", len(g["gains"]), len(e["lines"])))
            n += 1
            if not close(float(g["total"]), e["total"], rtol) or hook[art] != e["total"]:
                bad.append((cid, art, "total", g["total"], e["total"]))
            n += 1
            if bool(g["equipped"]) != e["equipped"]:
                bad.append((cid, art, "equipped", g["equipped"], e["equipped"]))
            n += 1
            if g["star"] != e["star"]:
                bad.append((cid, art, "star", g["star"], e["star"]))
        if verbose:
            tot = sum(hook.values())
            print(f"  {cid}: {sum(1 for v in hook.values() if v)} artifacts with a potential gain, sum {tot:,.1f}")
    return len(t["cases"]), n, bad


def test_tables_match_builder():
    sys.path.insert(0, str(HERE.parents[1] / "src"))
    spec = importlib.util.spec_from_file_location("build_fp_mage_workbook_pot_test", HERE.parents[1] / "src" / "build_fp_mage_workbook.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert potentials.RARITIES == mod.ARTIFACT_POTENTIAL_RARITIES and potentials.VALUES == mod.ARTIFACT_POTENTIAL_VALUES
    assert potentials.STAT_TO_KEY == mod.ARTIFACT_POTENTIAL_STAT_TO_SWEEP_KEY
    assert {a: potentials.num_lines(a) for a in AD.WORKBOOK_ARTIFACT_LABELS} == {a: (3 if mod.ARTIFACT_RANK[a] == "Legendary" else 2) for a in mod.ARTIFACT_LABELS}
    assert potentials.default_star("book_of_ancient") == mod.ARTIFACT_RANK_DEFAULT_STAR[mod.ARTIFACT_RANK["book_of_ancient"]]
    # companion model: the summoning-time line tiers behind potential_line_totals()
    import companion_model as cm
    from engine import sensitivity
    assert sensitivity.potential_line_totals() == cm.potential_line_totals() and sensitivity.POTENTIAL_LINE_TIERS == cm.POTENTIAL_LINE_TIERS
    assert sensitivity.POTENTIAL_MAX_LINES == cm.POTENTIAL_MAX_LINES


def test_boots_lines_consistent_with_cube_table():
    """The summoning-time tiers of potential_line_totals() (5 / 8 / 12 / 20) are exactly the values the boots roll table rolls for that stat."""
    from engine import cubes, sensitivity
    boots = {}
    for (slot, rarity, line), entries in cubes.roll_table().items():
        if slot == "boots":
            boots.setdefault(rarity, set()).update(v for s, v, w in entries if s == cubes.COMPANION_STAT)
    tiers = dict(sensitivity.POTENTIAL_LINE_TIERS)
    for i, (tier, v) in enumerate(sensitivity.POTENTIAL_LINE_TIERS):
        allowed = {v} | ({sensitivity.POTENTIAL_LINE_TIERS[i - 1][1]} if i > 0 else set())
        assert boots[tier.lower()] == allowed, (tier, boots[tier.lower()], allowed)
    assert set(boots) == {t.lower() for t in tiers}


def test_semantics():
    """Hand-derived: line gating by Star Level, rarity values, same-stat addition, different-stat compounding, unpriced stats."""
    H = {"damage": 10_000.0, "boss_damage": 20_000.0, "crit_rate": 3_000.0, "int_pct": 5_000.0}
    T = 1_000_000.0
    art = "book_of_ancient"                                       # a Legendary artifact (3 lines)
    assert AD.ARTIFACT_RANK[art] == "Legendary"
    lines = [("Legendary", "Damage %"), ("Epic", "Damage %"), ("Mystic", "Boss Monster Damage %")]
    d = potentials.artifact_potential(art, 5, lines, H, T)
    assert [x["gain"] for x in d["lines"]] == [14 * 10_000.0, 6 * 10_000.0, 20 * 20_000.0] and all(x["active"] for x in d["lines"])
    # same stat adds (14 + 6 = 20 Damage), the other stat multiplies
    assert close(d["total"], T * ((1 + 200_000.0 / T) * (1 + 400_000.0 / T) - 1), 1e-12)
    # star gating: line 1 from star 1, line 2 from star 2, line 3 from star 5; "Not Unlocked" = star 0 = nothing
    assert [x["gain"] > 0 for x in potentials.artifact_potential(art, 1, lines, H, T)["lines"]] == [True, False, False]
    assert [x["gain"] > 0 for x in potentials.artifact_potential(art, 4, lines, H, T)["lines"]] == [True, True, False]
    assert potentials.artifact_potential(art, "Not Unlocked", lines, H, T)["total"] == 0 and potentials.artifact_potential(art, None, lines, H, T)["star"] == 0
    # unpriced stats (no DPS bucket) and (none) are worth 0 whatever the rarity; Epic / Unique artifacts have only 2 lines
    assert potentials.artifact_potential(art, 5, [("Mystic", "Accuracy"), ("Mystic", "(none)"), ("Rare", "Defense %")], H, T)["total"] == 0
    epic = next(a for a in AD.ARTIFACT_LABELS if AD.ARTIFACT_RANK[a] == "Epic")
    d2 = potentials.artifact_potential(epic, 5, [("Rare", "Damage %"), ("Rare", "Boss Monster Damage %"), ("Mystic", "Damage %")], H, T)
    assert len(d2["lines"]) == 2 and d2["lines"][0]["gain"] == 4 * 10_000.0
    # the Critical Rate line uses the literal crit_rate rate (no cap substitution for artifact potentials)
    assert potentials.line_gain("Mystic", "Critical Rate %", 5, 0, H) == 10 * 3_000.0
    # unknown rarity on a priced stat is an error (#N/A in the sheet)
    try:
        potentials.line_gain("Bogus", "Damage %", 5, 0, H)
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
    # equipped resolution by workbook name or id
    assert potentials.resolve_equipped([None, "Book of Ancient"], "book_of_ancient") and not potentials.resolve_equipped(["(none)"], "book_of_ancient")
    # defaults: an artifact missing from the state uses the rank's default star and Rare / (none) lines -> no gain
    assert all(v == 0 for v in potentials.potential_gains({}, H, T).values())


def test_sensitivity_hook():
    """potential_gains() -> inputs["artifact_potential_gain"] -> engine.sensitivity: the equip row's DPS gain grows by exactly the potential gain (added
    unsigned, both directions) and the row reports it as ``potential_gain``."""
    from engine import cubes, sensitivity
    from engine.classes import fp_mage
    inp = fp_mage.defaults("World Boss")
    inp.update(level=140, flat_attack=1_209_199, flat_int=60000, int_pct=150, luk=3000, crit_rate=80, crit_damage=150, damage=200)
    state = {"ring_of_cycles": {"star": 5, "lines": [("Legendary", "Damage %"), ("Unique", "Boss Monster Damage %")]},
             "book_of_ancient": {"star": 3, "lines": [("Mystic", "Critical Rate %"), ("Mystic (Prime)", "Final Damage %"), ("Rare", "Damage %")]}}
    gains, rates, total = potentials.hook_for(fp_mage, inp, state)
    assert total > 0 and gains["ring_of_cycles"] > 0 and gains["book_of_ancient"] > 0 and gains["pigs_ribbon"] == 0
    assert potentials.potential_gains(state, rates, total) == gains and rates == cubes.sweep_rates(sensitivity.run(fp_mage, inp, which=["stats"]))
    for equipped in (False, True):
        i = dict(inp, artifacts=[{"key": "ring_of_cycles", "star": 5}] if equipped else [])
        without = {r["key"]: r for r in sensitivity.run(fp_mage, i, which=["artifacts"])["artifacts"]["rows"]}["ring_of_cycles"]
        with_pot = {r["key"]: r for r in sensitivity.run(fp_mage, dict(i, artifact_potential_gain=gains), which=["artifacts"])["artifacts"]["rows"]}["ring_of_cycles"]
        assert with_pot["potential_gain"] == gains["ring_of_cycles"]
        assert close(with_pot["dps_gain"], without["dps_gain"] + gains["ring_of_cycles"], 1e-12, 1e-6)


def test_golden():
    n_cases, n, bad = run()
    assert not bad, bad[:5]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rtol", type=float, default=1e-9)
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()
    for fn in (test_tables_match_builder, test_boots_lines_consistent_with_cube_table, test_semantics, test_sensitivity_hook):
        fn()
        print(f"ok: {fn.__name__}", flush=True)
    n_cases, n, bad = run(a.rtol, a.verbose)
    for b in bad[:25]:
        print("  ", b)
    print(f"{'OK' if not bad else 'FAIL'}: {n_cases} cases, {n} values vs the ArtifactsInput formulas (rtol {a.rtol:g}), {len(bad)} differences")
    sys.exit(1 if bad else 0)
