"""Every class with stat values (all but FP-Mage, which has its own ``test_sensitivity.py``) through the API: POST /api/classes/<id>/sensitivity (+ meta), and the
cube / equipment / artifact-potential features that price their stats with it (the class's stat maps come from its Sensitivity spec).  Golden vs the engine
called directly; the engine itself is checked against the workbook by tests/golden/test_sensitivity.py --class <class>.

One parametrized module for the former ``test_sensitivity_<class>.py`` files: ``CLASSES`` holds what differs per class (main / sub stat, Defense stats, the
Inputs the cases use, the shape of the stat sweep); the checks are the same.

Run from the repo root:  python -m pytest api/tests -q
"""
import math
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from api import features, registry
from api.main import create_app
from api.settings import Settings
from api.tests._unsupported import unsupported_class
from engine import cubes, equipment, potentials, sensitivity
from engine.classes import (bishop, bowmaster, buccaneer, corsair, dark_knight, hero, ice_lightning_mage, marksman, night_lord, paladin,
                            shadower)

_BASE = {"content_type": "World Boss", "companion_choice": "Blaze Wizard", "companion_level": 10}
_TAIL = {"flat_attack": 250000, "attack_pct": 1800, "crit_rate": 60, "status_effect_damage": 30}
_DEF = {"defense": 12000, "defense_pct": 15}


def _cfg(module, case, main, first_keys, n_stats, has, lacks, semantic, gear_head, gear_ring, sub=None, defense_stat=False, defense_rates=False, spec_maps=True,
         int_zero=True, str_pct_optional_zero=False, nan_filter=None, equip_line=("Defense (flat)", 100), check_shamaness=False, fp_meta=True, semantic_has=None,
         companion_lines=False):
    """``main`` = (the main stat's potential-line name, its flat Inputs key, its % Inputs key), ``sub`` = (the sub stat's "<name> %" line, its Inputs key) when it
    is priced as a % of the Inputs value, ``defense_stat`` / ``defense_rates``: the class sweeps Defense / Defense % (its rates are priced), ``has`` / ``lacks``: the
    stat keys the meta must / must not list, ``semantic``: a stat key whose row carries a ``semantics`` text."""
    return SimpleNamespace(module=module, case={**_BASE, **case, **_TAIL}, main=main, sub=sub, first_keys=first_keys, n_stats=n_stats, has=set(has), lacks=set(lacks),
                           semantic=semantic, gear_head=gear_head, gear_ring=gear_ring, defense_stat=defense_stat, defense_rates=defense_rates, spec_maps=spec_maps,
                           int_zero=int_zero, str_pct_optional_zero=str_pct_optional_zero, nan_filter=nan_filter, equip_line=equip_line,
                           check_shamaness=check_shamaness, fp_meta=fp_meta, semantic_has=semantic_has, companion_lines=companion_lines)


_STR = ("Str", "flat_str", "str_pct")
_DEX = ("Dex", "flat_dex", "dex_pct")
_LUK = ("Luk", "flat_luk", "luk_pct")
_INT = ("Int", "flat_int", "int_pct")
_NOT_INT_DEF = {"flat_int", "defense", "defense_pct"}
_H_STR = [{"stat": "Dex %", "value": 6}, {"stat": "Attack Speed %", "value": 5}, {"stat": "Critical Rate %", "value": 3}]
_H_DEX = [{"stat": "Str %", "value": 6}, {"stat": "Attack Speed %", "value": 5}, {"stat": "Critical Rate %", "value": 3}]
_H_INT = [{"stat": "Int %", "value": 6}, {"stat": "Defense %", "value": 5}, {"stat": "Critical Rate %", "value": 3}]
_H_DK = [{"stat": "Dex %", "value": 6}, {"stat": "Defense %", "value": 5}, {"stat": "Critical Rate %", "value": 3}]


def _ring(label):
    return [{"stat": label, "value": 7}, {"stat": "Final Damage %", "value": 6}]


CLASSES = {
    "hero": _cfg(hero, {"dex": 800, "flat_str": 20000, "str_pct": 300}, _STR, ["flat_str", "str_pct", "dex", "damage", "damage_amp"], 28,
                 {"flat_str", "str_pct", "dex"}, _NOT_INT_DEF, "final_damage", _H_STR, _ring("Str %"), sub=("Dex %", "dex")),
    "dark_knight": _cfg(dark_knight, {**_DEF, "dex": 800, "flat_str": 20000, "str_pct": 300}, _STR, ["flat_str", "str_pct", "dex", "defense", "defense_pct"], 30,
                        {"flat_str", "str_pct", "dex", "defense", "defense_pct"}, {"flat_int"}, "defense", _H_DK, _ring("Str %"), sub=("Dex %", "dex"),
                        defense_stat=True, defense_rates=True),
    "bishop": _cfg(bishop, {**_DEF, "luk": 800, "flat_int": 20000, "int_pct": 300}, _INT, ["flat_int", "int_pct", "defense", "defense_pct"], 29,
                   {"flat_int", "int_pct", "defense", "defense_pct"}, {"flat_str", "dex"}, "defense", _H_INT, _ring("Int %"), defense_stat=True,
                   defense_rates=True, int_zero=False, str_pct_optional_zero=True),
    "ice_lightning_mage": _cfg(ice_lightning_mage, {"defense": 12000, "luk": 800, "flat_int": 20000, "int_pct": 300}, _INT, ["flat_int", "int_pct", "damage"], 27,
                               {"flat_int", "int_pct"}, {"flat_str"}, "skill_lvl_2nd", _H_INT, _ring("Int %"), int_zero=False, spec_maps=False,
                               equip_line=("Skill Level Bonus — 3rd Job", 2), check_shamaness=True, fp_meta=False, semantic_has="Magic Acceleration",
                               companion_lines=True),
    "paladin": _cfg(paladin, {"dex": 800, "flat_str": 20000, "str_pct": 300}, _STR, ["flat_str", "str_pct", "dex", "damage", "damage_amp"], 28,
                    {"flat_str", "str_pct", "dex"}, _NOT_INT_DEF, "final_damage", _H_STR, _ring("Str %"), sub=("Dex %", "dex")),
    "buccaneer": _cfg(buccaneer, {"dex": 800, "flat_str": 20000, "str_pct": 300}, _STR, ["flat_str", "str_pct", "dex", "damage", "damage_amp"], 28,
                      {"flat_str", "str_pct", "dex"}, _NOT_INT_DEF, "final_damage", _H_STR, _ring("Str %"), sub=("Dex %", "dex")),
    "bowmaster": _cfg(bowmaster, {"str": 800, "flat_dex": 20000, "dex_pct": 300}, _DEX, ["flat_dex", "dex_pct", "str", "damage", "damage_amp"], 28,
                      {"flat_dex", "dex_pct", "str"}, _NOT_INT_DEF, "final_damage", _H_DEX, _ring("Dex %"), sub=("Str %", "str")),
    "marksman": _cfg(marksman, {"str": 800, "flat_dex": 20000, "dex_pct": 300}, _DEX, ["flat_dex", "dex_pct", "str", "damage", "damage_amp"], 28,
                     {"flat_dex", "dex_pct", "str"}, _NOT_INT_DEF, "final_damage", _H_DEX, _ring("Dex %"), sub=("Str %", "str")),
    "corsair": _cfg(corsair, {"str": 800, "flat_dex": 20000, "dex_pct": 300}, _DEX, ["flat_dex", "dex_pct", "str", "damage", "damage_amp"], 28,
                    {"flat_dex", "dex_pct", "str"}, _NOT_INT_DEF, "final_damage", _H_DEX, _ring("Dex %"), sub=("Str %", "str"),
                    nan_filter=("Infinity Blast", "")),      # (a skill of the kit is literally named "Infinity Blast")
    "night_lord": _cfg(night_lord, {"dex": 800, "flat_luk": 20000, "luk_pct": 300, "incoming_hit_rate": 2}, _LUK, ["flat_luk", "luk_pct", "dex", "damage", "damage_amp"], 29,
                       {"flat_luk", "luk_pct", "dex", "incoming_hit_rate"}, _NOT_INT_DEF, "flat_luk", _H_STR, _ring("Luk %"), sub=("Dex %", "dex")),
    "shadower": _cfg(shadower, {"dex": 800, "flat_luk": 20000, "luk_pct": 300}, _LUK, ["flat_luk", "luk_pct", "dex", "damage", "damage_amp"], 29,
                     {"flat_luk", "luk_pct", "dex", "incoming_hit_rate"}, _NOT_INT_DEF, "final_damage", _H_STR, _ring("Luk %"), sub=("Dex %", "dex")),
}
IDS = list(CLASSES)
GOLDEN_DIR = Path(__file__).resolve().parents[2] / "tests" / "golden"


def make_client(**kw):
    for k in ("rate_limit_per_minute", "rate_limit_sens_per_minute", "rate_limit_cubes_per_minute", "rate_limit_compare_per_minute"):
        kw.setdefault(k, 0)
    return TestClient(create_app(Settings(**kw)))


@pytest.fixture(scope="module")
def client():
    return make_client()


@pytest.fixture(params=IDS)
def cid(request):
    return request.param


def _same(a, b, path=""):
    if isinstance(a, float):
        if not math.isfinite(a):
            assert b is None, path
        else:
            assert math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12), path
    elif isinstance(a, dict):
        assert {str(k) for k in a} == set(b), path
        for k in a:
            _same(a[k], b[str(k)], f"{path}.{k}")
    elif isinstance(a, (list, tuple)):
        assert len(a) == len(b), path
        for i, (x, y) in enumerate(zip(a, b)):
            _same(x, y, f"{path}[{i}]")
    else:
        assert a == b, path


def engine_inputs(cid, body):
    from api.validation import validate_inputs
    entry = registry.discover()[cid]
    clean, errors = validate_inputs(entry.schema, entry.defaults, body)
    assert not errors, errors
    return clean


def test_every_served_class_is_covered():
    """Derived from the API's own class list: a class that has a workbook golden (``tests/golden/<id>_golden.json``) needs its ``CLASSES`` config above (checked against the
    workbook); every other served class is ENGINE-NATIVE and is covered by the generic contract of ``test_all_classes.py::test_engine_native_*`` (stat values, meta, cube /
    equipment / artifact-potential tabs) - FP-Mage is the one class with its own ``test_sensitivity.py``."""
    served = set(registry.discover())
    assert set(IDS) | {"fp_mage"} <= served
    workbook_backed = {c for c in served if (GOLDEN_DIR / f"{c}_golden.json").exists()}
    assert workbook_backed <= set(IDS) | {"fp_mage"}, f"add a CLASSES config for {sorted(workbook_backed - set(IDS) - {'fp_mage'})}"


def test_capability_flags(client, monkeypatch, cid):
    st = {c["id"]: c["status"]["stat_values"] for c in client.get("/api/classes").json()["classes"]}
    assert st[cid] is True and st["fp_mage"] is True
    assert cid in registry.SENSITIVITY_CLASSES
    assert client.post(f"/api/classes/{unsupported_class(monkeypatch)}/sensitivity", json={}).status_code == 501


def test_sensitivity_matches_engine_directly(client, cid):
    c = CLASSES[cid]
    r = client.post(f"/api/classes/{cid}/sensitivity", json=c.case)
    assert r.status_code == 200, r.text
    body = r.json()
    direct = sensitivity.run(c.module, engine_inputs(cid, c.case))
    _same(direct, body)
    assert body["class_id"] == cid
    assert [x["key"] for x in body["stats"]["rows"]][:len(c.first_keys)] == c.first_keys
    assert len(body["stats"]["rows"]) == c.n_stats and len(body["artifacts"]["rows"]) == 36 and len(body["companions"]["rows"]) == 16
    text = r.text if c.nan_filter is None else r.text.replace(*c.nan_filter)
    assert "NaN" not in r.text and "Infinity" not in text


def test_meta_is_the_class_own_sweep(client, cid):
    c = CLASSES[cid]
    m = client.get(f"/api/classes/{cid}/sensitivity/meta").json()
    keys = {s["key"] for s in m["stats"]}
    assert m["class_id"] == cid and [s["key"] for s in m["stats"]] == [s["key"] for s in sensitivity.stat_sweep(c.module)] and len(m["stats"]) == c.n_stats
    assert keys >= c.has and not keys & c.lacks
    if c.fp_meta:
        fp = client.get("/api/classes/fp_mage/sensitivity/meta").json()
        assert len(fp["stats"]) == 27 and fp["stats"][0]["key"] == "flat_int"
    assert any(s["key"] == c.semantic and s["semantics"] and (c.semantic_has is None or c.semantic_has in s["semantics"]) for s in m["stats"])


def test_parts_selection_and_artifacts(client, cid):
    c = CLASSES[cid]
    body = {**c.case, "which": ["artifacts"], "artifacts": [{"key": "bottle_of_emotion", "star": 5}], "artifact_stars": {"candle": 2}}
    out = client.post(f"/api/classes/{cid}/sensitivity", json=body).json()
    rows = {x["key"]: x for x in out["artifacts"]["rows"]}
    assert rows["bottle_of_emotion"]["equipped"] is True and rows["candle"]["equipped"] is False and rows["candle"]["star"] == 2
    if c.check_shamaness:
        assert rows["shamaness_marble"]["dps_gain"] != 0.0                       # the Buff Duration what-if is wired in this class's workbook block
    direct = sensitivity.run(c.module, dict(engine_inputs(cid, c.case), artifacts=[{"key": "bottle_of_emotion", "star": 5}], artifact_stars={"candle": 2}),
                             which=["artifacts"])
    _same(direct, out)


# ---- the features priced by the sensitivity rates ------------------------------------------------------------------------------------------------
def _gear(c):
    return [{"slot": "head", "potential_type": "Potential", "rarity": "epic", "pity": 12, "lines": c.gear_head},
            {"slot": "ring", "potential_type": "Potential", "rarity": "legendary", "pity": 100, "lines": c.gear_ring}]


def test_cubes_use_the_class_stat_maps(client, cid):
    c = CLASSES[cid]
    GEAR = _gear(c)
    r = client.post(f"/api/classes/{cid}/cubes", json={**c.case, "gear": GEAR, "only": ["head", "ring"]})
    assert r.status_code == 200, r.text
    out = r.json()
    inputs = engine_inputs(cid, c.case)
    if c.companion_lines:
        inputs["companion_potential_lines_pct"] = cubes.companion_lines_pct(features.validate_gear(GEAR)[0])
    sens = sensitivity.run(c.module, dict(inputs), which=["stats", "cdr", "summon_time"])
    if c.spec_maps:
        spec_maps = features.STAT_TO_KEY_BY_CLASS[cid]
        pricing = cubes.pricing_from_sensitivity(sens, dict(inputs), c.module, stat_to_key=spec_maps["cubes"], sub_stat_pct_lines=spec_maps["cubes_sub_stat_pct"])
    else:
        pricing = cubes.pricing_from_sensitivity(sens, dict(inputs), c.module)
    gear = features.validate_gear(GEAR)[0]
    direct = cubes.recommend(gear, pricing, only={i for i, g in enumerate(gear) if g["slot"] in ("head", "ring")}, include_curve=True)
    _same(direct, out["rows"])
    # the class's own priced stats (not the INT defaults): the main stat's lines = its sweep, a sub stat's % line = rate(sub) x its Inputs value / 100, the
    # Defense % line = the Defense sweep (worth 0 in the classes without one), main stat per level
    rates = cubes.sweep_rates(sens)
    t = pricing.dps_per_unit
    name, flat, pct = c.main
    assert t[f"{name} %"] == rates[pct] > 0 and t[name] == rates[flat] > 0
    if c.defense_rates:
        assert t["Defense %"] == rates["defense_pct"] > 0
    elif not c.defense_stat and c.spec_maps:
        assert t.get("Defense %", 0.0) == 0.0
    if c.sub:
        label, key = c.sub
        assert t[label] == pytest.approx(rates[key] * inputs[key] / 100, rel=1e-12) and t[label] > 0
    assert t["Main Stat Per Level"] == pytest.approx(rates[flat] * inputs["level"], rel=1e-12)
    assert t["Main Stat % per 4 Levels"] == pytest.approx(rates[pct] * int(inputs["level"] / 4), rel=1e-12)
    if c.int_zero:
        assert t["Int"] == 0 and t["Int %"] == 0
    if c.str_pct_optional_zero:
        assert "Str %" not in t or t["Str %"] == 0


def test_equipment_compare_main_stat(client, cid):
    c = CLASSES[cid]
    line, line_value = c.equip_line
    body = {**c.case, "current": {"attack": 1000, "lines": [{"stat": "Main Stat %", "value": 5}, {"stat": line, "value": line_value}]},
            "new": {"attack": 1500, "lines": [{"stat": "Main Stat (flat)", "value": 300}]}}
    r = client.post(f"/api/classes/{cid}/equipment-compare", json=body)
    assert r.status_code == 200, r.text
    out = r.json()
    inputs = engine_inputs(cid, c.case)
    sens = sensitivity.run(c.module, dict(inputs), which=["stats"])
    rates = cubes.sweep_rates(sens)
    m = c.module.model(dict(inputs))
    kw = {"stat_to_key": features.STAT_TO_KEY_BY_CLASS[cid]["equipment"]} if c.spec_maps else {}
    direct = equipment.compare({"attack": 1000, "lines": [("Main Stat %", 5), (line, line_value)]}, {"attack": 1500, "lines": [("Main Stat (flat)", 300)]},
                               rates, sens["baseline_total"], m.crit_rate_total, **kw)
    for k in ("current", "new", "delta_pct", "delta_dps", "better"):
        _same(direct[k], out[k], k)
    flat = c.main[1]
    assert out["rate_by_stat"]["Main Stat (flat)"] == rates[flat] > 0
    if c.defense_rates:
        assert out["rate_by_stat"]["Defense (flat)"] == rates["defense"] > 0
    elif c.spec_maps:
        assert out["rate_by_stat"]["Defense (flat)"] == 0
    assert out["crit_rate_total"] == pytest.approx(m.crit_rate_total, rel=1e-12)


def test_artifact_potentials_main_stat(client, cid):
    c = CLASSES[cid]
    body = {**c.case, "potentials": {"hexagon_necklace": {"star": 5, "lines": [{"rarity": "Legendary", "stat": "Main Stat %"}, {"rarity": "Epic", "stat": "Damage %"}]}}}
    r = client.post(f"/api/classes/{cid}/artifact-potentials", json=body)
    assert r.status_code == 200, r.text
    out = r.json()
    inputs = engine_inputs(cid, c.case)
    sens = sensitivity.run(c.module, dict(inputs), which=["stats"])
    rates = cubes.sweep_rates(sens)
    state = {"hexagon_necklace": {"star": 5, "lines": [("Legendary", "Main Stat %"), ("Epic", "Damage %")]}}
    kw = {"stat_to_key": features.STAT_TO_KEY_BY_CLASS[cid]["potentials"]} if c.spec_maps else {}
    direct = potentials.potential_table(state, rates, sens["baseline_total"], [], **kw)
    row = next(x for x in out["rows"] if x["key"] == "hexagon_necklace")
    dr = next(x for x in direct if x["key"] == "hexagon_necklace")
    _same(dr["total"], row["total"], "total")
    assert row["total"] > 0
