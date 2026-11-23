#!/usr/bin/env python3
"""Engine-only checks of the ENGINE-NATIVE classes (``registry.NATIVE``: no Excel workbook, so nothing here reads a workbook or a workbook golden).

    python3 tests/golden/test_engine_native.py                       # every engine-native class
    python3 tests/golden/test_engine_native.py --class dawn_warrior -v
    python3 tests/golden/test_engine_native.py --class dawn_warrior --only level_sweep

The checks (each is one function ``check_<name>(cid)``; pytest id ``test_engine_native[<class>-<name>]``):

  spec                       the class has a Sensitivity spec + ``model``; stat list / maps are consistent (the ``static`` test of a workbook class, minus the builder)
  hooks_are_noops_without_sens   an explicit empty ``_sens`` changes nothing (sens_test_common)
  api_shape                  ``which`` selection, JSON-serialisable output, no-effect flag, potential-gain term, naive switch, a class without a spec raises (sens_test_common)
  final_damage_sweep         the +1% multiplicative Final Damage step is exactly +1%: % gain 101.000 in Chapter Hunt without a companion, never above 101 with the timeline strip
  toggle_direction_invariance    CLAUDE.md item 15 / checklist 8c: an equip toggle reports the identical $ and % gain from both directions (sens_test_common)
  no_dps_effect_artifacts    an artifact flagged ``no_dps_effect`` changes nothing, every artifact alone computes to finite numbers
  content_sweep              all 10 content types x {default, late} stats x companion on/off compute to finite numbers; DPS > 0 where the fight must produce some
  level_sweep                character level 1..200: flags every DPS DECREASE as the level rises (prints content, level, before / after), minus the explicit allow-list
                             ``tests/golden/native_level_allowlist.json`` (see below)

LEVEL-DECREASE ALLOW-LIST: a decrease that is understood and intended (e.g. a skill that is replaced by a better one at a level threshold, a cooldown breakpoint) is listed in
``native_level_allowlist.json`` as ``{"classes": {"<id>": [{"level": L, "content_type": "World Boss", "companion": false, "reason": "why"}]}}`` - ``level`` = the level at which the
total is LOWER than at ``level - 1``; ``content_type`` / ``companion`` are optional filters (omitted = any); a ``reason`` is mandatory.  An entry that matches no decrease any more
is itself an error (the list must stay honest), so removing the cause removes the entry.
"""
import argparse
import json
import math
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))
import registry  # noqa: E402
import snapshot_common as SN  # noqa: E402
import sens_test_common as SC  # noqa: E402
from engine import sensitivity, sens_specs  # noqa: E402

ALLOWLIST = HERE / "native_level_allowlist.json"
LEVEL_CONFIGS = SN.LEVEL_CONTENTS + (("Breakthrough", False),)       # (content type, companion on)
DECREASE_RTOL = 1e-9
SHEET_BUDGET = 10                                                      # decreases printed per class before "... more"


class NativeSens(SC.SensTest):
    """``sens_test_common.SensTest`` with the generic character of ``snapshot_common`` instead of the workbook's ``<id>_cases`` (everything else is inherited)."""

    def __init__(self, cid):
        super().__init__(cid, SN.class_module(cid), SN.snapshot_path(cid), registry.native_entry(cid).name)
        self.spec = sens_specs.get(cid)

    def inputs(self, content, artifacts, **over):
        d = SN.make_inputs(self.module, content, "late", True, artifacts=artifacts, **over)
        d["artifact_stars"] = SN.stars()
        return d


def finite_leaves(node, path=""):
    """Every numeric leaf of a result is a finite number (NaN / inf is a bug); returns the first bad path or None."""
    if isinstance(node, dict):
        for k, v in node.items():
            bad = finite_leaves(v, f"{path}/{k}")
            if bad:
                return bad
    elif isinstance(node, (list, tuple)):
        for i, v in enumerate(node):
            bad = finite_leaves(v, f"{path}/{i}")
            if bad:
                return bad
    elif isinstance(node, float) and not math.isfinite(node):
        return path
    return None


# --------------------------------------------------------------------------- the checks
def check_spec(cid):
    T = NativeSens(cid)
    spec, m = T.spec, T.module
    assert spec is not None, f"{cid}: no Sensitivity spec (engine/sens_specs/{cid}.py + CLASS_IDS in engine/sens_specs/__init__.py): stat values and the cube tab would be off"
    assert sensitivity.supports(m) and sensitivity.meta(m)["class_id"] == cid and spec.class_id == cid
    keys = [k for k, _l, _t in spec.stat_list]
    assert len(keys) == len(set(keys)), "duplicate stat keys in the spec"
    fields = {f["key"] for f in m.schema()["fields"]}
    assert {spec.mainstat.flat, spec.mainstat.pct, *[k for k, _r in spec.mainstat.subs]} <= fields, "main-stat keys of the spec are not schema fields"
    for k in keys:
        assert k in fields or k in ("final_damage",), f"stat {k!r} of the spec is not a schema field"
    for feature in ("cubes", "equipment", "potentials"):
        mp = (spec.stat_to_key or {}).get(feature)
        assert mp, f"spec.stat_to_key[{feature!r}] missing: the {feature} tab would price with FP-Mage's INT defaults"
        bad = sorted({v for v in mp.values() if v is not None and v not in keys and v != "defense"})      # ("defense": a class without an Iron Wall-type sweep row prices it as 0)
        assert not bad, f"spec.stat_to_key[{feature!r}] maps to sweep keys that are not in the stat list: {bad}"
    assert len(sensitivity.stat_sweep(m)) == len(keys) and len(sensitivity.ARTIFACT_TOGGLES) == 36
    return f"{len(keys)} stats"


def check_hooks_are_noops_without_sens(cid):
    NativeSens(cid).test_hooks_are_noops_without_sens()


def check_api_shape(cid):
    T = NativeSens(cid)
    keys = [k for k, _l, _t in T.spec.stat_list]
    api = dict(content="Breakthrough", shamaness="positive" if T.spec.bdi_toggle_wired else "inert", naive_rows=len(keys), keys_prefix=keys[:4], keys_absent=[], keys_last=keys[-1])
    T.test_api_shape(api)
    try:
        sensitivity.run(types.SimpleNamespace(CLASS_ID="no_such_class"), T.inputs("World Boss", []))
        raise AssertionError("a class without a spec must raise")
    except NotImplementedError:
        pass


def check_final_damage_sweep(cid):
    """The +1% multiplicative Final Damage step bumps the FULL bucket: its reported % gain is exactly 101.000 wherever nothing else moves (Chapter Hunt without a companion and
    without Status Effect Damage: no timeline strip) and in pure boss content without a strip; with the strip on (a companion / KO windows in World Boss) a time-varying term of
    the engine's own bucket may make it a little UNDER 101 (workbook behaviour), never above."""
    T = NativeSens(cid)

    def row(content, comp, **over):
        inp = T.inputs(content, [{"key": "bottle_of_emotion", "star": 5}], **over)
        if not comp:
            inp.update(companion_choice="None", companion_level=0)
        out = sensitivity.run(T.module, inp, which="stats")["stats"]["rows"]
        return next(x for x in out if x["key"] == "final_damage")
    r = row("Chapter Hunt", False, status_effect_damage=0)
    assert math.isclose(r["pct_gain"], 101.0, rel_tol=1e-12), f"Chapter Hunt, no companion: Final Damage +1% reports {r['pct_gain']!r}, must be exactly 101"
    assert r["new"] > r["current"] >= 0, (r["current"], r["new"])
    wb = row("World Boss", True)
    assert 100.9 < wb["pct_gain"] <= 101.0 + 1e-9, f"World Boss with the strip: Final Damage +1% reports {wb['pct_gain']!r}"
    return f"101.000 in Chapter Hunt, {wb['pct_gain']:.6f} in World Boss with the strip"


def toggle_pairs(T):
    """The equip-toggle pairs of the class-independent artifacts (adapted from the workbook classes' ``sens_extras``: data, no model code): the same real state reached from
    both directions - the baked-in stat typed into the Inputs or not.  Pairs whose artifact the spec says is not wired into the class's blocks are left out."""
    from engine import artifacts as art
    spec, m = T.spec, T.module
    S = SN.stars()
    pairs = [(k, {}, {}) for k in ("hexagon_necklace", "horn_flute", "candle", "secret_map", "alliance_badge", "charm_of_the_undead", "old_music_box", "ring_of_cycles")]
    model = m.model(T.inputs("World Boss", [], crit_rate=60.0, crit_damage=150.0))
    live = float(getattr(model, "crit_rate_bonus", 0.0) or 0.0)           # a class's own live Crit Rate source counts into the TOTAL the Book's dependent Crit Damage follows
    cr_d, pct = art.sv("book_of_ancient_crit_rate", S["book_of_ancient"]), art.sv("book_of_ancient_crit_damage_pct_of_crit_rate", S["book_of_ancient"])
    pairs.append(("book_of_ancient", dict(crit_rate=60.0, crit_damage=150.0), dict(crit_rate=60.0 + cr_d, crit_damage=150.0 + pct / 100 * (60.0 + cr_d + live))))
    if spec.athena_as_in_aps:
        a_d, a_pct = art.sv("athena_gloves_attack_speed", S["athena_gloves"]), art.sv("athena_gloves_max_damage_pct_of_attack_speed", S["athena_gloves"])
        pairs.append(("athena_gloves", dict(attack_speed=20.0, max_damage=130.0), dict(attack_speed=20.0 + a_d, max_damage=130.0 + a_pct / 100 * (20.0 + a_d))))
    if spec.bdi_toggle_wired:
        pairs.append(("shamaness_marble", dict(buff_duration_increase_pct=15.0),
                      dict(buff_duration_increase_pct=15.0 + art.sv("shamaness_marble_buff_duration_increase_pct", S["shamaness_marble"]))))
    if spec.reindeer_dose_in_rows:
        mag = art.sv("reindeer_spear_def_pen", S["reindeer_spear"])
        pairs.append(("reindeer_spear", dict(def_pen=35.0), dict(def_pen=100 * (1 - (1 - 35.0 / 100) * (1 - mag / 100)))))
    pairs.append(("star_rock", dict(boss_damage=40.0), dict(boss_damage=40.0 + art.sv("star_rock_boss_damage", S["star_rock"]))))
    # baked-in Final Damage: a factor on the TYPED value ("typed" form) or on the whole bracket incl. the live additive sources that share it ("factor" form)
    mb = 0.0 if spec.baked_fd_form == "typed" else sum(float(getattr(model, attr) or 0.0) for _k, attr in spec.mult_extra)

    def typed(x):
        return ((1 + (12.0 + mb) / 100) * (1 + x / 100) - 1) * 100 - mb
    for key in ("cursed_doll", "lit_lamp"):
        pairs.append((key, dict(final_damage=12.0), dict(final_damage=typed(art.sv(f"{key}_final_damage", S[key])))))
    pairs.append(("cursed_doll", dict(final_damage=12.0), dict(final_damage=typed(art.sv("cursed_doll_final_damage", S["cursed_doll"]))), "flaming_lava"))
    return pairs


def check_toggle_direction_invariance(cid):
    T = NativeSens(cid)
    pairs = toggle_pairs(T)
    T.check_toggle_pairs(pairs)
    return f"{len(pairs)} pairs"


def check_no_dps_effect_artifacts(cid):
    T = NativeSens(cid)
    m = T.module
    base = m.compute(T.inputs("World Boss", []))["total_dps"]
    from engine.data import artifacts as AD
    n = 0
    for key in AD.ARTIFACT_LABELS:
        r = m.compute(T.inputs("World Boss", [SN.slot(key)]))
        bad = finite_leaves(r)
        assert bad is None, f"{key}: non-finite value at {bad}"
        if key in AD.ARTIFACT_NO_DPS_EFFECT:
            assert r["total_dps"] == base, f"{key} is flagged no_dps_effect but changes the total ({base!r} -> {r['total_dps']!r})"
            n += 1
    return f"36 artifacts finite, {n} no-effect artifacts change nothing"


def check_content_sweep(cid):
    m = SN.class_module(cid)
    n = 0
    for content in m.schema()["content_types"]:
        for st in ("default", "late"):
            for comp in (False, True):
                d = SN.make_inputs(m, content, st, comp)
                where = f"{content} / {st} / {'companion' if comp else 'no companion'}"
                r = m.compute(d)
                bad = finite_leaves(r)
                assert bad is None, f"{where}: non-finite value at {bad}"
                assert r["total_dps"] > 0, f"{where}: Total DPS {r['total_dps']!r} (must be > 0)"
                mt = r["derived"].get("monster_type")
                if mt == "boss":
                    assert r["boss_dps"] > 0, f"{where}: boss content with Boss DPS {r['boss_dps']!r}"
                elif mt == "normal":
                    assert r["normal_dps"] > 0, f"{where}: normal-monster content with Normal DPS {r['normal_dps']!r}"
                elif mt == "breakthrough":
                    assert r["boss_dps"] > 0 and r["normal_dps"] > 0, f"{where}: blended content needs both branches ({r['boss_dps']!r} / {r['normal_dps']!r})"
                assert all(s["dps"] >= 0 for s in r["skills"]), f"{where}: a skill row has negative DPS"
                n += 1
    return f"{n} runs, {len(m.schema()['content_types'])} content types"


def load_allowlist(cid):
    if not ALLOWLIST.exists():
        return []
    entries = json.loads(ALLOWLIST.read_text()).get("classes", {}).get(cid, [])
    for e in entries:
        assert isinstance(e.get("level"), int) and str(e.get("reason", "")).strip(), f"{ALLOWLIST.name}: every entry needs an integer 'level' and a non-empty 'reason': {e}"
    return entries


def level_decreases(cid, levels=range(1, 201)):
    """[(content, companion, level, total at level-1, total at level)] - every level at which the Total DPS is LOWER than one level earlier."""
    m = SN.class_module(cid)
    out = []
    for content, comp in LEVEL_CONFIGS:
        prev = None
        for lv in levels:
            r = m.compute(SN.make_inputs(m, content, "late", comp, level=lv))
            assert finite_leaves(r) is None, f"{content} level {lv}: non-finite value"
            t = r["total_dps"]
            if prev is not None and t < prev * (1 - DECREASE_RTOL):
                out.append((content, comp, lv, prev, t))
            prev = t
    return out


def check_level_sweep(cid):
    found = level_decreases(cid)
    allow = load_allowlist(cid)
    used, unexplained = set(), []
    for content, comp, lv, before, after in found:
        hit = next((i for i, e in enumerate(allow) if e["level"] == lv and e.get("content_type", content) == content and e.get("companion", comp) == comp), None)
        if hit is None:
            unexplained.append((content, comp, lv, before, after))
        else:
            used.add(hit)
    stale = [e for i, e in enumerate(allow) if i not in used]
    msgs = [f"  level {lv} ({content}, {'with' if comp else 'no'} companion): Total DPS {before:.6e} -> {after:.6e} ({(after / before - 1) * 100:+.3f}%)"
            for content, comp, lv, before, after in unexplained[:SHEET_BUDGET]]
    if len(unexplained) > SHEET_BUDGET:
        msgs.append(f"  ... {len(unexplained) - SHEET_BUDGET} more")
    if stale:
        msgs += [f"  STALE allow-list entry (no such decrease any more): {e}" for e in stale]
    if unexplained or stale:
        head = (f"{len(unexplained)} unexplained DPS decrease(s) as the level rises (explain each in {ALLOWLIST.name} or fix the model):" if unexplained
                else f"stale entries in {ALLOWLIST.name}:")
        raise AssertionError(head + "\n" + "\n".join(msgs))
    return f"levels 1-200 x {len(LEVEL_CONFIGS)} fights, {len(found)} allow-listed decrease(s)" if found else f"levels 1-200 x {len(LEVEL_CONFIGS)} fights, no decrease"


CHECKS = {
    "spec": check_spec,
    "hooks_are_noops_without_sens": check_hooks_are_noops_without_sens,
    "api_shape": check_api_shape,
    "final_damage_sweep": check_final_damage_sweep,
    "toggle_direction_invariance": check_toggle_direction_invariance,
    "no_dps_effect_artifacts": check_no_dps_effect_artifacts,
    "content_sweep": check_content_sweep,
    "level_sweep": check_level_sweep,
}


def pytest_generate_tests(metafunc):
    if "cid" in metafunc.fixturenames and "check" in metafunc.fixturenames:
        pairs = [(cid, name) for cid in registry.NATIVE for name in CHECKS]
        metafunc.parametrize("cid,check", pairs, ids=[f"{c}-{n}" for c, n in pairs])


def test_engine_native(cid, check):
    CHECKS[check](cid)


def run_class(cid, only=None, verbose=False):
    """Run the checks of one class, collecting failures; -> (number failed, number run)."""
    failed = run = 0
    for name, fn in CHECKS.items():
        if only and name not in only:
            continue
        run += 1
        try:
            detail = fn(cid)
            print(f"  ok   {name}" + (f"  ({detail})" if detail and verbose else ""))
        except AssertionError as ex:
            failed += 1
            print(f"  FAIL {name}: {ex}")
        except Exception as ex:                              # noqa: BLE001 - an engine error is a failure of the check, not of the runner
            failed += 1
            print(f"  FAIL {name}: {type(ex).__name__}: {ex}")
    return failed, run


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--class", dest="classes", action="append", choices=list(registry.NATIVE), help="engine-native class id (repeatable); default: all of them")
    ap.add_argument("--only", action="append", choices=list(CHECKS), help="only this check (repeatable)")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    classes = a.classes or list(registry.NATIVE)
    if not classes:
        print("no engine-native class registered (every engine/classes/<id>.py without a workbook is one): nothing to do")
        return 0
    total_failed = 0
    for cid in classes:
        print(f"--- {cid}")
        failed, run = run_class(cid, a.only, a.verbose)
        total_failed += failed
        print(f"{'OK' if not failed else 'FAIL'}: {run - failed}/{run} engine-native checks of {cid}")
    return 1 if total_failed else 0


if __name__ == "__main__":
    sys.exit(main())
