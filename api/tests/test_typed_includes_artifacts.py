"""API: ``typed_includes_artifacts`` (the typed stats are the in-game preset page values, which already include every equipped artifact; engine/typed_artifacts.py).

* the API fills it TRUE when a request omits it; it is an optional boolean outside the schema fields (like ``artifacts``);
* Calculator / Stat values / Cubes / Equipment compare / Artifact potentials all go through the same strip step: their ``baseline_total`` is the Calculator's Total DPS,
  and a character typed WITH the artifact's bonus prices exactly like the same character typed WITHOUT it and the artifact added on top (the workbooks' convention).

Run from the repo root:  python -m pytest api/tests/test_typed_includes_artifacts.py -q
"""
import math

import pytest
from fastapi.testclient import TestClient

from api import registry
from api.main import create_app
from api.settings import Settings
from api.validation import validate_inputs
from engine import artifacts as art_mod

CID = "fp_mage"
COMPUTE = f"/api/classes/{CID}/compute"
SENS = f"/api/classes/{CID}/sensitivity"
CUBES = f"/api/classes/{CID}/cubes"
EQUIP = f"/api/classes/{CID}/equipment-compare"
POTS = f"/api/classes/{CID}/artifact-potentials"

ARTS = [{"key": "arwens_glass_shoes", "star": 5}, {"key": "icy_soul_rock", "star": 3}, {"key": "alliance_badge", "star": 4}, {"key": "sayrams_necklace", "star": 2}]
# the character WITHOUT any artifact bonus in its stats (B) ...
BASE = {"content_type": "World Boss", "companion_choice": "Blaze Wizard", "companion_level": 10, "companion_summon_time_increase_pct": 8, "crit_damage": 150,
        "attack_pct": 1500, "boss_damage": 40, "final_damage": 12}
GEAR = [{"slot": "boots", "potential_type": "Bonus Potential", "rarity": "unique", "pity": 0, "lines": [{"stat": "Companion Summoning Time Increase %", "value": 8}]},
        {"slot": "ring", "potential_type": "Potential", "rarity": "legendary", "pity": 100, "lines": [{"stat": "Final Damage %", "value": 6}]}]


def make_client(**kw):
    for k in ("rate_limit_per_minute", "rate_limit_sens_per_minute", "rate_limit_cubes_per_minute", "rate_limit_compare_per_minute"):
        kw.setdefault(k, 0)
    return TestClient(create_app(Settings(**kw)))


@pytest.fixture(scope="module")
def client():
    return make_client()


def _entry():
    return registry.discover()[CID]


def typed_body():
    """The same character typed the way the preset page shows it: B with every equipped artifact's effect already inside (the engine's own composition)."""
    from engine.classes import fp_mage
    ok, errors = validate_inputs(_entry().schema, _entry().defaults, dict(BASE, artifacts=ARTS, typed_includes_artifacts=False))
    assert not errors
    m = fp_mage.model(ok)
    e = m.art_effects
    t = dict(BASE)
    t["companion_summon_time_increase_pct"] = BASE["companion_summon_time_increase_pct"] + e.summon_time_inc
    t["crit_damage"] = BASE["crit_damage"] + e.agg_crit_damage
    t["attack_pct"] = BASE["attack_pct"]                       # artifact Attack% is its own bucket, not in the preset page ATTACK %
    t["boss_damage"] = BASE["boss_damage"] + e.agg_boss_damage
    t["normal_damage"] = float(BASE.get("normal_damage") or 0) + e.agg_normal_damage
    t["final_damage"] = ((1 + BASE["final_damage"] / 100) * (1 + e.agg_final_damage / 100) - 1) * 100
    return t, m.total_dps


def test_default_is_true_and_the_flag_is_validated():
    entry = _entry()
    ok, errors = validate_inputs(entry.schema, entry.defaults, {"content_type": "World Boss"})
    assert not errors and ok["typed_includes_artifacts"] is True
    ok, errors = validate_inputs(entry.schema, entry.defaults, {"content_type": "World Boss", "typed_includes_artifacts": False})
    assert not errors and ok["typed_includes_artifacts"] is False
    for bad in (1, "yes", None, [True]):
        ok, errors = validate_inputs(entry.schema, entry.defaults, {"content_type": "World Boss", "typed_includes_artifacts": bad})
        assert ok is None and {e["field"] for e in errors} == {"typed_includes_artifacts"}, bad
    ok, errors = validate_inputs(entry.schema, entry.defaults, {"content_type": "World Boss", "typed_includes_arifacts": True})        # a typo stays rejected
    assert ok is None and errors[0]["field"] == "typed_includes_arifacts"
    assert "typed_includes_artifacts" not in {f["key"] for f in entry.schema["fields"]}                                              # not a schema field


def test_compute_counts_the_equipped_artifacts_once(client):
    t, workbook_total = typed_body()
    typed = client.post(COMPUTE, json=dict(t, artifacts=ARTS))                       # API default: typed stats include the artifacts
    assert typed.status_code == 200, typed.text
    assert typed.json()["total_dps"] == pytest.approx(workbook_total, rel=1e-12)
    old = client.post(COMPUTE, json=dict(t, artifacts=ARTS, typed_includes_artifacts=False)).json()["total_dps"]      # the same numbers read the workbook way: counted twice
    assert old > workbook_total * 1.01
    rep = typed.json()["artifacts"]["typed"]
    assert rep["includes_artifacts"] is True and rep["notes"] == [] and set(rep["base"]) >= {"companion_summon_time_increase_pct", "crit_damage"} and "attack_pct" not in rep["amounts"]
    assert rep["base"]["companion_summon_time_increase_pct"] == pytest.approx(BASE["companion_summon_time_increase_pct"])
    plain = client.post(COMPUTE, json=dict(BASE, artifacts=ARTS, typed_includes_artifacts=False)).json()
    assert "typed" not in plain["artifacts"]                                          # the workbook convention reports nothing extra


def _close(a, b, rel=1e-9):
    if isinstance(a, float) or isinstance(b, float):
        assert a == pytest.approx(b, rel=rel, abs=1e-6), (a, b)
    elif isinstance(a, dict):
        assert set(a) == set(b)
        for k in a:
            _close(a[k], b[k], rel)
    elif isinstance(a, list):
        assert len(a) == len(b)
        for x, y in zip(a, b):
            _close(x, y, rel)
    else:
        assert a == b, (a, b)


def test_every_tab_prices_the_same_character_as_the_calculator(client):
    """Sensitivity / Cubes / Equipment compare / Artifact potentials: ``baseline_total`` == the Calculator's Total DPS (no double count), and the character typed WITH
    the artifacts prices exactly like the workbook-convention character (B + the artifacts on top)."""
    t, total = typed_body()
    new, old = dict(t, artifacts=ARTS), dict(BASE, artifacts=ARTS, typed_includes_artifacts=False)
    calc = client.post(COMPUTE, json=new).json()["total_dps"]
    assert calc == pytest.approx(total, rel=1e-12)
    s_new = client.post(SENS, json=dict(new, which=["stats", "artifacts", "summon_time"])).json()
    s_old = client.post(SENS, json=dict(old, which=["stats", "artifacts", "summon_time"])).json()
    assert s_new["baseline_total"] == pytest.approx(calc, rel=1e-12)
    for part in ("stats", "artifacts"):
        for a, b in zip(s_new[part]["rows"], s_old[part]["rows"]):
            for f in ("dps_gain", "pct_gain", "new_total"):
                assert a[f] == pytest.approx(b[f], rel=1e-9, abs=1e-6), (part, a["key"], f)
    # Current / New of the stat table are the TYPED numbers (preset page values), not the stripped base
    cur = {r["key"]: r["current"] for r in s_new["stats"]["rows"]}
    assert cur["crit_damage"] == pytest.approx(t["crit_damage"]) and cur["attack_pct"] == pytest.approx(t["attack_pct"])
    assert cur["companion_summon_time_increase_pct"] == pytest.approx(t["companion_summon_time_increase_pct"])
    assert s_new["summon_time"]["b0"] == pytest.approx(s_old["summon_time"]["b0"], rel=1e-12)
    # the gear's lines are inside the typed value: typed T = B + shoes + the boots lines; the workbook-convention twin types B + the lines
    gear_pct = 8
    new_g = dict(new, companion_summon_time_increase_pct=new["companion_summon_time_increase_pct"] + gear_pct)
    old_g = dict(old, companion_summon_time_increase_pct=old["companion_summon_time_increase_pct"] + gear_pct)
    c_new = client.post(CUBES, json=dict(new_g, gear=GEAR))
    c_old = client.post(CUBES, json=dict(old_g, gear=GEAR))
    assert c_new.status_code == 200 and c_old.status_code == 200, (c_new.text, c_old.text)
    _close(c_new.json()["rows"], c_old.json()["rows"])
    cur_e = {"attack": 1500, "lines": [{"stat": "Damage %", "value": 14}, {"stat": "Critical Rate %", "value": 3}]}
    new_e = {"attack": 2200, "lines": [{"stat": "Final Damage %", "value": 6}, {"stat": "Min Damage %", "value": 15}]}
    e_new = client.post(EQUIP, json=dict(new, current=cur_e, new=new_e)).json()
    e_old = client.post(EQUIP, json=dict(old, current=cur_e, new=new_e)).json()
    assert e_new["baseline_total"] == pytest.approx(calc, rel=1e-12)
    _close(e_new["delta_pct"], e_old["delta_pct"])
    p_body = {"potentials": {"arwens_glass_shoes": {"star": 5, "lines": [{"rarity": "Legendary", "stat": "Damage %"}]}}}
    p_new = client.post(POTS, json=dict(new, **p_body)).json()
    p_old = client.post(POTS, json=dict(old, **p_body)).json()
    assert p_new["baseline_total"] == pytest.approx(calc, rel=1e-12)
    _close(p_new["rows"], p_old["rows"])


def test_the_cubes_baseline_is_the_calculator_total(client):
    t, total = typed_body()
    body = dict(t, artifacts=ARTS, gear=GEAR[:1])
    r = client.post(CUBES, json=body)
    assert r.status_code == 200, r.text
    assert r.json()["baseline_total"] == pytest.approx(client.post(COMPUTE, json={k: v for k, v in body.items() if k != "gear"}).json()["total_dps"], rel=1e-12)


def test_an_unequipped_character_is_unchanged_by_the_flag(client):
    base = dict(BASE, artifacts=[])
    a = client.post(COMPUTE, json=base).json()
    b = client.post(COMPUTE, json=dict(base, typed_includes_artifacts=False)).json()
    assert a == b
    assert math.isfinite(a["total_dps"]) and "typed" not in a["artifacts"]
    assert art_mod.MAX_SLOTS == 5
