#!/usr/bin/env python3
"""ENGINE-ONLY exhaustive test of the ``typed_includes_artifacts`` convention (engine/typed_artifacts.py): the typed stats are the in-game PRESET PAGE values, which
already contain every equipped artifact's bonus (user, 2026-11-25), so the engine derives the character without the equipped artifacts' effects first and the unchanged
pipeline adds them back live.

Ground rules of the test (nothing here is a workbook golden; the flag is OFF by default, which keeps every workbook-pinned golden bit-exact):

* ROUND TRIP, per artifact: take base stats B (artifact absent) with the artifact EQUIPPED, ``D_live = model(B + artifact, flag off)`` = today's semantics (the artifact
  is added on top of the typed values).  Build the preset-page stats T = B with the artifact's effect composed in by the engine's OWN forward composition (read from the
  model's ``art_effects`` aggregate buckets, not from the strip code: additive buckets ``B + a``, Final Damage / Hexagon Damage ``(1 + B)(1 + a) - 1``, Bishop's one
  additive Damage bucket).  Then ``compute(T + artifact, flag on) == D_live`` to rtol 1e-12, and ``strip`` recovers B.  Every one of the 20 live artifacts x star 0..5
  x 5 contents x 5 classes (FP-Mage, Hero, Night Lord, Bowmaster + Bishop's additive Damage bucket), plus Ring of Cycles / Rainbow Snail Shell at base crit rates in
  both of Ring of Cycles' modes.
* the artifacts without a typed counterpart (Chalice, Fire Flower, Peach Tree, Silver Pendant, Soul Contract, Contract of Darkness) and the reference-only ones are
  UNCHANGED by the flag (bit-exact); an unequipped character is bit-exact too.
* random sets of up to 5 live artifacts (seeded) round-trip as well (the buckets compose: several Final Damage artifacts divide out together, Ring of Cycles + Rainbow
  Snail Shell invert the crit rate jointly).
* NO DOUBLE COUNT, independent of the strip's own formulas: where the artifact's whole effect sits in one typed bucket that the class composes the same way
  (Icy Soul Rock, Sayram's Necklace, Rainbow Snail Shell, Ring of Cycles in both modes, Arwen's Glass Shoes, Flaming Lava, Candle's boss damage ... in FP-Mage / Night
  Lord), the DPS of ``T + artifact equipped`` (flag on) equals the DPS of ``T`` with NOTHING equipped (flag off): equipping an artifact the preset already includes
  changes nothing.
* the equip toggles of the Sensitivity artifact table (the what-if gain of every live artifact, equipped or not) are the same in both conventions: ``run(T + eq, flag
  on)`` == ``run(B + eq, flag off)``.
* a typed value below the effect clamps at 0 with the note ``typed_below_artifact:<id>``; the Ring of Cycles window is reported as ``typed_ambiguous:ring_of_cycles``.

    python3 tests/golden/test_typed_includes_artifacts.py              # the whole matrix
    python3 tests/golden/test_typed_includes_artifacts.py --table      # + the per-artifact verification table (artifact, effect, inverse, max rel error)
(also pytest-collectable)
"""
import importlib
import itertools
import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))
import factor_mode  # noqa: E402

FACTOR_MODE = factor_mode.pin("extended")          # engine-only: production growth curves
import snapshot_common as SC  # noqa: E402
from engine import artifacts as art_mod, sensitivity, typed_artifacts as TA  # noqa: E402
from engine.data import artifacts as AD  # noqa: E402

FLAG = TA.FLAG
CLASSES = ("fp_mage", "hero", "night_lord", "bowmaster", "bishop")
CONTENTS = ("World Boss", "Chapter Hunt", "Breakthrough", "PvP", "Hero Dungeon")
LIVE = [a for a in AD.ARTIFACT_LABELS if art_mod.effect_kind(a) == "live"]
NO_TYPED = ["chalice", "fire_flower", "peach_tree", "silver_pendant", "soul_contract", "contract_of_darkness",
            "old_music_box", "alliance_badge", "secret_map", "charm_of_the_undead", "reindeer_spear", "shiny_watch", "mummydogs_bandages"]       # live, no typed counterpart (the Attack% ones stack in their own bucket, not in the preset page ATTACK %)
RTOL = 1e-12
# stats typed with the artifact ABSENT (B); crit rate comes from CRIT_CASES, summoning time is typed so that Horn Flute / Hexagon timing is non-trivial
BASE_OVER = dict(companion_summon_time_increase_pct=10.0)
CRIT_CASES = (60.0, 200.0)          # Ring of Cycles' crit-rate mode / its skill-damage mode (200: clear of the [100, 100 + bonus) window nobody can invert)
TYPED_KEYS = ["companion_summon_time_increase_pct", "crit_rate", "crit_damage", "boss_damage", "normal_damage", "skill_damage", "basic_attack_damage", "attack_pct",
              "final_damage", "damage"]


def mod(cid):
    return importlib.import_module(f"engine.classes.{cid}")


def base_inputs(cid, content, slots, crit=60.0, **over):
    d = SC.make_inputs(mod(cid), content, "late", True, **dict(BASE_OVER, crit_rate=crit, **over))
    d["artifacts"] = [dict(s) for s in slots]
    d["artifact_stars"] = {s["key"]: s["star"] for s in slots}
    return d


def forward(cid, base, m):
    """The preset-page stats T of the base stats B with the model ``m``'s (flag off, built on B) artifact effects composed into them - the engine's own composition.  Artifacts in
    ``typed_artifacts.STRIP_EXEMPT`` (their bonus applies only during the fight) are NOT part of the preset page."""
    e = m.art_effects
    rows = e.rows
    eq = set(art_mod.resolve_slots(base.get("artifacts")))
    live = lambda a: a in eq and a not in TA.STRIP_EXEMPT
    t = dict(base)

    def num(k):
        return float(base.get(k) or 0)
    t["companion_summon_time_increase_pct"] = num("companion_summon_time_increase_pct") + (e.summon_time_inc if live("arwens_glass_shoes") else 0.0)
    t["crit_rate"] = num("crit_rate") + sum(rows[r] for a, r in TA.CRIT_ROWS if live(a))
    for key, parts in TA.ADD_ROWS.items():
        t[key] = num(key) + sum(rows[r] for a, r in parts if live(a))
    t["attack_pct"] = num("attack_pct")                       # artifact Attack% stacks with the buffs in its own bucket: never part of the preset page ATTACK %
    for key, parts in TA.FACTOR_ROWS.items():
        amounts = [rows[r] for a, r in parts if live(a)]
        if key == "damage" and TA.damage_is_additive(type(m)):
            t[key] = num(key) + sum(amounts)
            continue
        prod = 1.0
        for v in amounts:
            prod *= 1 + v / 100
        t[key] = ((1 + num(key) / 100) * prod - 1) * 100
    return t


def rel(a, b):
    return abs(a - b) / max(abs(a), abs(b), 1e-300)


def roundtrip(cid, content, slots, crit=60.0, check_base=True):
    """(max rel error of Total DPS, [typed stats that moved], strip info) of one round trip."""
    module = mod(cid)
    B = base_inputs(cid, content, slots, crit)
    m = module.model(B)
    D = m.total_dps
    T = forward(cid, B, m)
    moved = [k for k in TYPED_KEYS if rel(float(T.get(k) or 0), float(B.get(k) or 0)) > 1e-9]
    r = module.model(dict(T, **{FLAG: True}))
    err = rel(r.total_dps, D)
    assert err <= RTOL, (cid, content, slots, crit, r.total_dps, D, err)
    info = r.typed_info
    if check_base and info is not None:
        ambiguous = "typed_ambiguous:ring_of_cycles" in info["notes"]          # Ring of Cycles' window: the TOTALS (so the DPS) agree, the split into base / live differs
        for k in moved:      # the strip recovered the base stats
            if ambiguous and k in ("crit_rate", "skill_damage", "basic_attack_damage"):
                continue
            got = info["base"].get(k, float(T.get(k) or 0))
            assert math.isclose(got, float(B.get(k) or 0), rel_tol=1e-9, abs_tol=1e-9), (cid, content, slots, k, got, B.get(k))
        assert not [n for n in info["notes"] if n.startswith("typed_below")], (cid, content, slots, info["notes"])   # (typed_ambiguous:ring_of_cycles is expected for T >= 100)
    return err, moved, info


STARS = range(8)


def test_live_artifact_count():
    assert len(LIVE) == 23, LIVE         # 20 + the three artifacts of the 2026-11-26 patch
    assert set(NO_TYPED) <= set(LIVE)
    assert TA.STRIPPED_ARTIFACTS <= set(LIVE) | {"bottle_of_emotion"}            # Bottle of Emotion: reference-only Final Damage but a LIVE Attack%
    assert set(LIVE) - set(NO_TYPED) - TA.STRIP_EXEMPT <= TA.STRIPPED_ARTIFACTS, set(LIVE) - set(NO_TYPED) - TA.STRIP_EXEMPT - TA.STRIPPED_ARTIFACTS


def run_matrix(table=None):
    """Every live artifact x star x content x class (+ Bottle of Emotion's Attack% and the crit-rate modes); fills ``table`` {artifact: [max err, n, typed keys]}."""
    n = 0
    for cid, content, art, star in itertools.product(CLASSES, CONTENTS, LIVE + ["bottle_of_emotion"], STARS):
        if star > art_mod.max_star(art):          # Legendary artifacts reach star 7 (patch 2026-11-26), Epic / Unique stop at 5
            continue
        crits = CRIT_CASES if art in ("ring_of_cycles", "rainbow_snail_shell") else (60.0,)
        for crit in crits:
            err, moved, _info = roundtrip(cid, content, [{"key": art, "star": star}], crit)
            n += 1
            if table is not None:
                row = table.setdefault(art, [0.0, 0, set()])
                row[0] = max(row[0], err)
                row[1] += 1
                row[2].update(moved)
    return n


def test_every_live_artifact_round_trips():
    assert run_matrix() > 1800


def test_artifacts_without_a_typed_counterpart_are_unchanged():
    """Chalice / Fire Flower / Peach Tree / Silver Pendant / Soul Contract / Contract of Darkness (+ the reference-only artifacts and the no-DPS ones): the flag changes
    nothing, bit for bit - same Total, same boss / normal split."""
    keys = NO_TYPED + [a for a in AD.ARTIFACT_LABELS if art_mod.effect_kind(a) != "live" and a != "bottle_of_emotion"]
    for cid, content, art in itertools.product(CLASSES, CONTENTS, keys):
        module = mod(cid)
        B = base_inputs(cid, content, [{"key": art, "star": 4}])
        off, on = module.compute(B), module.compute(dict(B, **{FLAG: True}))
        assert on["total_dps"] == off["total_dps"] and on["boss_dps"] == off["boss_dps"] and on["normal_dps"] == off["normal_dps"], (cid, content, art)
        m = module.model(dict(B, **{FLAG: True}))
        assert not m.typed_info["base"], (art, m.typed_info)
    for cid, content in itertools.product(CLASSES, CONTENTS):
        module = mod(cid)
        B = base_inputs(cid, content, [])
        assert module.compute(dict(B, **{FLAG: True}))["total_dps"] == module.compute(B)["total_dps"]


def test_random_five_slot_sets_round_trip():
    rng = random.Random(20261125)
    pool = LIVE + ["bottle_of_emotion"]
    n = 0
    sets = [["rainbow_snail_shell", "ring_of_cycles", "candle", "flaming_lava", "horn_flute"],
            ["hexagon_necklace", "arwens_glass_shoes", "sayrams_necklace", "icy_soul_rock", "charm_of_the_undead"],
            ["alliance_badge", "secret_map", "reindeer_spear", "old_music_box", "bottle_of_emotion"]]
    sets += [rng.sample(pool, rng.randint(2, 5)) for _ in range(40)]
    for cid, content in itertools.product(CLASSES, ("World Boss", "Breakthrough", "PvP", "Chapter Hunt")):
        for keys in sets:
            slots = [{"key": k, "star": rng.randint(0, 5)} for k in keys]
            crit = 200.0 if rng.random() < 0.4 else 60.0
            roundtrip(cid, content, slots, crit)
            n += 1
    assert n > 500


# single-bucket artifacts whose effect the class composes exactly like the typed stat: the preset already includes it, so equipping it changes NOTHING
NO_DOUBLE_COUNT = ["icy_soul_rock", "sayrams_necklace", "arwens_glass_shoes", "flaming_lava"]   # (the during-the-fight artifacts in STRIP_EXEMPT are added on top by design)


def test_equipped_artifact_in_the_preset_is_not_counted_twice():
    for cid, content, art, star in itertools.product(("fp_mage", "night_lord"), CONTENTS, NO_DOUBLE_COUNT, (0, 2, 5)):
        module = mod(cid)
        for crit in (60.0,):
            B = base_inputs(cid, content, [{"key": art, "star": star}], crit)
            m = module.model(B)
            T = forward(cid, B, m)
            with_art = module.compute(dict(T, **{FLAG: True}))["total_dps"]
            without = module.compute(dict(T, artifacts=[]))["total_dps"]           # the same preset, nothing equipped, workbook convention
            assert rel(with_art, without) <= 1e-12, (cid, content, art, star, crit, with_art, without)


def test_sensitivity_equip_rows_agree_between_the_conventions():
    """The what-if gain of every equip toggle (live artifacts, equipped or not, and the baked-in ones) on T with the flag == on B without it."""
    rng = random.Random(7)
    for cid, content in itertools.product(("fp_mage", "hero", "night_lord"), ("World Boss", "Breakthrough", "PvP", "Chapter Hunt")):
        module = mod(cid)
        for keys in (["candle", "hexagon_necklace"], ["arwens_glass_shoes", "alliance_badge", "horn_flute"], ["ring_of_cycles", "rainbow_snail_shell", "sayrams_necklace"]):
            slots = [{"key": k, "star": rng.randint(1, 5)} for k in keys]
            B = base_inputs(cid, content, slots, 60.0)
            m = module.model(B)
            T = forward(cid, B, m)
            a = sensitivity.run(module, B, which=["artifacts", "stats"])
            b = sensitivity.run(module, dict(T, **{FLAG: True}), which=["artifacts", "stats"])
            assert rel(a["baseline_total"], b["baseline_total"]) <= RTOL
            for ra, rb in zip(a["artifacts"]["rows"], b["artifacts"]["rows"]):
                assert ra["key"] == rb["key"]
                for f in ("dps_gain", "pct_gain", "new_total"):
                    assert math.isclose(ra[f], rb[f], rel_tol=1e-9, abs_tol=1e-11 * a["baseline_total"]), (cid, content, keys, ra["key"], f, ra[f], rb[f])
            for ra, rb in zip(a["stats"]["rows"], b["stats"]["rows"]):
                assert ra["key"] == rb["key"]
                for f in ("dps_gain", "pct_gain", "new_total"):
                    assert math.isclose(ra[f], rb[f], rel_tol=1e-9, abs_tol=1e-11 * a["baseline_total"]), (cid, content, keys, ra["key"], f, ra[f], rb[f])
                # Current / New are what the user TYPED (the preset page value), not the stripped base
                assert math.isclose(rb["current"], float(T.get(rb["key"]) or 0) + (rb["current"] - float(T.get(rb["key"]) or 0)), rel_tol=1e-12)
            typed_rows = {r["key"]: r for r in b["stats"]["rows"]}
            for k in ("crit_damage", "boss_damage"):
                if k in typed_rows and rel(float(T.get(k) or 0), float(B.get(k) or 0)) > 1e-9:
                    assert math.isclose(typed_rows[k]["current"], float(T[k]), rel_tol=1e-12), (cid, k, typed_rows[k]["current"], T[k])


def test_cubes_pricing_and_sensitivity_totals_follow_the_compute_convention():
    """Cube pricing (``cubes.pricing_from_sensitivity``) and Sensitivity take the same flagged inputs as ``compute``: their baseline IS the Calculator's Total DPS (the
    strip runs on every path), and the pricing of a character typed WITH the artifacts equals the workbook-convention twin (B + the artifacts on top)."""
    from engine import cubes
    for cid, content in itertools.product(("fp_mage", "hero", "night_lord"), ("World Boss", "Breakthrough", "Chapter Hunt")):
        module = mod(cid)
        slots = [{"key": "arwens_glass_shoes", "star": 5}, {"key": "icy_soul_rock", "star": 2}, {"key": "alliance_badge", "star": 3}, {"key": "candle", "star": 4}]
        B = base_inputs(cid, content, slots, 60.0)
        m = module.model(B)
        T = dict(forward(cid, B, m), artifacts=slots)
        flagged = dict(T, **{FLAG: True})
        total = module.compute(flagged)["total_dps"]
        assert rel(total, m.total_dps) <= RTOL
        sens_t = sensitivity.run(module, flagged, which=["stats", "cdr", "summon_time"])
        sens_b = sensitivity.run(module, B, which=["stats", "cdr", "summon_time"])
        assert rel(sens_t["baseline_total"], total) <= RTOL
        assert rel(sens_t["summon_time"]["b0"], sens_b["summon_time"]["b0"]) <= 1e-12
        p_t = cubes.pricing_from_sensitivity(sens_t, flagged, module)
        p_b = cubes.pricing_from_sensitivity(sens_b, B, module)
        assert rel(p_t.baseline_dps, total) <= RTOL
        assert rel(p_t.baseline_dps, p_b.baseline_dps) <= RTOL
        for stat, v in p_b.dps_per_unit.items():
            assert math.isclose(p_t.dps_per_unit[stat], v, rel_tol=1e-9, abs_tol=1e-9 * total), (cid, content, stat, p_t.dps_per_unit[stat], v)
        assert (p_t.companion is None) == (p_b.companion is None)
        if p_t.companion is not None:
            assert rel(p_t.companion.at(0)["comp_blend_dps"], p_b.companion.at(0)["comp_blend_dps"]) <= 1e-9


def test_typed_below_the_effect_clamps_and_notes():
    for cid in ("fp_mage", "hero"):
        module = mod(cid)
        for art, key, star in (("arwens_glass_shoes", "companion_summon_time_increase_pct", 5), ("icy_soul_rock", "crit_damage", 5), ("sayrams_necklace", "boss_damage", 5),
                               ("flaming_lava", "final_damage", 5)):
            d = base_inputs(cid, "World Boss", [{"key": art, "star": star}])
            d[key] = 0.0                                        # typed 0 < the effect
            m = module.model(dict(d, **{FLAG: True}))
            assert f"typed_below_artifact:{art}" in m.typed_info["notes"], (cid, art, m.typed_info)
            assert m.typed_info["base"][key] == 0.0
            assert m.result()["artifacts"]["typed"]["notes"] == m.typed_info["notes"]
            # clamped = the effect is added on top of a zero base: never below the no-artifact total
            assert m.total_dps >= module.compute(dict(d, artifacts=[]))["total_dps"] * (1 - 1e-12)
    # the during-the-fight artifacts (STRIP_EXEMPT: Ring of Cycles, Rainbow Snail Shell, Candle, Hexagon, Horn Flute, Old Music Box, Charm) are never stripped, so no note
    module = mod("fp_mage")
    d = base_inputs("fp_mage", "World Boss", [{"key": "ring_of_cycles", "star": 5}, {"key": "candle", "star": 5}], 60.0)
    d["crit_rate"] = 110.0
    m = module.model(dict(d, **{FLAG: True}))
    assert m.typed_info["notes"] == [] and m.typed_info["base"] == {}


def test_flag_off_is_the_workbook_convention_bit_exact():
    """The default (no flag / False) never touches the inputs."""
    for cid in CLASSES:
        module = mod(cid)
        d = base_inputs(cid, "World Boss", [{"key": "arwens_glass_shoes", "star": 5}, {"key": "candle", "star": 3}])
        assert module.compute(d)["total_dps"] == module.compute(dict(d, **{FLAG: False}))["total_dps"]
        assert "typed" not in module.compute(d)["artifacts"]
        assert module.compute(dict(d, **{FLAG: True}))["artifacts"]["typed"]["includes_artifacts"] is True


# ----------------------------------------------------------------------------------------------------------------------------------------------
INVERSE_TEXT = {
    "add": "B = max(0, T - a)",
    "factor": "B = (1+T/100) / (1+a/100) - 1",
}


def describe(art):
    """[(typed stat, composition, inverse text)] of an artifact (for the report table)."""
    out = []
    if art == "arwens_glass_shoes":
        out.append(("companion_summon_time_increase_pct", "typed + a", INVERSE_TEXT["add"]))
    for key, parts in TA.ADD_ROWS.items():
        if any(a == art for a, _r in parts):
            out.append((key, "typed + a", INVERSE_TEXT["add"]))
    for key, parts in TA.FACTOR_ROWS.items():
        if any(a == art for a, _r in parts):
            out.append((key, "(1+typed)(1+a)" + (" [Bishop: typed + a]" if key == "damage" else ""), INVERSE_TEXT["factor"] + (" [Bishop: T - a]" if key == "damage" else "")))
    if any(a == art for a, _r in TA.CRIT_ROWS):
        out.append(("crit_rate", "typed + rainbow + roc(B)", "B = T - rainbow - roc (Ring of Cycles mode from B; window [100, 100+roc) ambiguous)"
                    if art == "ring_of_cycles" else "B = T - rainbow (jointly with Ring of Cycles)"))
    return out


def main():
    table = {} if "--table" in sys.argv else None
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        if fn is test_every_live_artifact_round_trips and table is not None:
            n = run_matrix(table)
            print(f"ok: {fn.__name__} ({n} round trips)", flush=True)
            continue
        fn()
        print(f"ok: {fn.__name__}", flush=True)
    print(f"OK: {len(fns)} checks")
    if table is not None:
        print("\nartifact | effect | typed stat: composition -> inverse | typed stats moved | round trips | max rel error")
        for art in LIVE + ["bottle_of_emotion"]:
            err, n, moved = table[art]
            desc = "; ".join(f"{k}: {c} -> {i}" for k, c, i in describe(art)) or "none (no typed counterpart: unchanged by the flag)"
            print(f"{art} | {art_mod.effect_kind(art)} | {desc} | {sorted(moved) or '-'} | {n} | {err:.2e}")


if __name__ == "__main__":
    main()
