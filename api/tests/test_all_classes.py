"""Multi-class API tests (every class the API serves, through FastAPI's TestClient).  Run from the repo root:  python -m pytest api/tests -q

The class list is the API's own (``api.registry.discover()``: every ``engine/classes/<id>.py``), not a hand-kept one.  The 12 workbook-verified classes
(``WORKBOOK_CLASSES``: their expectations below were checked against the workbooks) get the golden-backed cases (only a class with ``tests/golden/<id>_golden.json``);
every other class is ENGINE-NATIVE (the Cygnus classes: no workbook, validated against the user's in-game numbers) and gets the generic checks - list, schema,
defaults, compute, companions, artifacts, sensitivity shape (``test_engine_native_*``)."""
import json
import math
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api import registry as api_registry
from api.main import create_app
from api.settings import Settings
from engine import sens_specs

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIR = ROOT / "tests" / "golden"
WORKBOOK_CLASSES = ["fp_mage", "hero", "ice_lightning_mage", "paladin", "bowmaster", "bishop", "dark_knight", "marksman", "buccaneer", "corsair",
                    "night_lord", "shadower"]
_DISCOVERED = api_registry.discover()
CLASS_IDS = list(_DISCOVERED)                                                   # everything the API serves
GOLDEN_IDS = [c for c in CLASS_IDS if (GOLDEN_DIR / f"{c}_golden.json").exists()]              # golden-backed (workbook) classes
# engine-native = served without a workbook golden; MSI_NATIVE_CLASSES (the tests/golden/registry.py test hook) additionally treats a workbook class as one
NATIVE_IDS = [c for c in CLASS_IDS if c not in GOLDEN_IDS] + [c for c in os.environ.get("MSI_NATIVE_CLASSES", "").split(",") if c in CLASS_IDS and c in GOLDEN_IDS]
CONTENT_TYPES = ["Chapter Boss", "Breakthrough", "PvP", "EXP Dungeon", "Equipment Dungeon", "Weapon Dungeon", "Enhancement Dungeon",
                 "Hero Dungeon", "World Boss", "Chapter Hunt"]
MAIN_STAT_FIELDS = {          # class -> (flat main stat, main stat %, sub stat) keys of its schema
    "fp_mage": ("flat_int", "int_pct", "luk"), "ice_lightning_mage": ("flat_int", "int_pct", "luk"), "bishop": ("flat_int", "int_pct", "luk"),
    "hero": ("flat_str", "str_pct", "dex"), "paladin": ("flat_str", "str_pct", "dex"), "dark_knight": ("flat_str", "str_pct", "dex"),
    "buccaneer": ("flat_str", "str_pct", "dex"),
    "bowmaster": ("flat_dex", "dex_pct", "str"), "marksman": ("flat_dex", "dex_pct", "str"), "corsair": ("flat_dex", "dex_pct", "str"),
    "night_lord": ("flat_luk", "luk_pct", "dex"), "shadower": ("flat_luk", "luk_pct", "dex"),
}
EXTRA_FIELDS = {"bishop": {"defense_pct"}, "dark_knight": {"defense_pct"}, "night_lord": {"incoming_hit_rate"}, "shadower": {"incoming_hit_rate"}}


def main_fields(cid, schema):
    """(flat main stat, main stat %, sub stat) keys of a class: the table of the workbook classes, else derived from the schema's stat identity (flat_<main>, <main>_pct, <sub>)."""
    if cid in MAIN_STAT_FIELDS:
        return MAIN_STAT_FIELDS[cid]
    main, sub = schema["stat_identity"]["main"].lower(), schema["stat_identity"]["sub"].lower()
    return (f"flat_{main}", f"{main}_pct", sub)


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app(Settings(rate_limit_per_minute=0)))


def test_every_class_listed(client):
    classes = client.get("/api/classes").json()["classes"]
    assert sorted(c["id"] for c in classes) == sorted(CLASS_IDS)
    assert set(WORKBOOK_CLASSES) <= set(CLASS_IDS), "a workbook-verified class disappeared from the API"
    assert not set(GOLDEN_IDS) - set(WORKBOOK_CLASSES), "a class has a workbook golden but is not in WORKBOOK_CLASSES"
    by_id = {c["id"]: c for c in classes}
    for cid in CLASS_IDS:
        c = by_id[cid]
        assert c["name"] and c["name"] != cid                         # a human name, not the module id
        assert set(c["stat_identity"]) == {"main", "sub"}
        assert c["family"] in {"Warrior", "Mage", "Archer", "Thief", "Pirate"}
        assert set(c["status"]) >= {"companions", "artifacts"} and c["status"]["artifacts"] == c["artifacts_modelled"]
    for cid in NATIVE_IDS:
        assert by_id[cid]["status"]["stat_values"] is True, f"{cid}: an engine-native class needs its Sensitivity spec (engine/sens_specs/{cid}.py): stat values and the cube tab depend on it"
    assert by_id["fp_mage"]["artifacts_modelled"] is True
    assert by_id["night_lord"]["stat_identity"] == {"main": "LUK", "sub": "DEX"}
    assert by_id["corsair"]["stat_identity"] == {"main": "DEX", "sub": "STR"}


@pytest.mark.parametrize("cid", CLASS_IDS)
def test_schema(client, cid):
    s = client.get(f"/api/classes/{cid}/schema").json()
    assert s["class_id"] == cid and s["content_types"] == CONTENT_TYPES
    keys = {f["key"] for f in s["fields"]}
    flat, pct, sub = main_fields(cid, s)
    assert {flat, pct, sub} <= keys
    assert EXTRA_FIELDS.get(cid, set()) <= keys
    main = s["stat_identity"]["main"].lower()
    assert flat == f"flat_{main}" and pct == f"{main}_pct"
    comp = next(f for f in s["fields"] if f["key"] == "companion_choice")
    assert comp["options"][0] == "None" and len(comp["options"]) == 17 and len(set(comp["options"])) == 17
    assert sorted(s["companions"]) == sorted(comp["options"][1:])
    for f in s["fields"]:
        assert "min" in f and "max" in f and "help" in f
        if f["type"] in ("int", "float") and not f["computed"]:
            assert f["min"] is not None and f["max"] is not None and f["min"] <= f["max"], f["key"]
            assert f["min"] <= (f["default"] or 0) <= f["max"] or f["default"] is None, f["key"]
        else:
            assert f["min"] is None and f["max"] is None, f["key"]
    by = {f["key"]: f for f in s["fields"]}
    assert (by["level"]["min"], by["level"]["max"]) == (1, 300)
    assert (by["def_pen"]["min"], by["def_pen"]["max"]) == (0, 100)
    assert (by["companion_level"]["min"], by["companion_level"]["max"]) == (0, 18)


@pytest.mark.parametrize("cid", CLASS_IDS)
def test_defaults_all_content_types(client, cid):
    schema = client.get(f"/api/classes/{cid}/schema").json()
    for ct in CONTENT_TYPES:
        r = client.get(f"/api/classes/{cid}/defaults", params={"content_type": ct})
        assert r.status_code == 200, (cid, ct, r.text)
        d = r.json()
        assert d["content_type"] == ct and d["companion_choice"] == "None"
        for f in schema["fields"]:
            if f["computed"]:
                continue
            applicable = f["applicable"] is None or ct in f["applicable"]
            assert (d[f["key"]] is not None) == (applicable and f["default"] is not None or bool(f["default_by_content"] and applicable)), (ct, f["key"])


@pytest.mark.parametrize("cid", CLASS_IDS)
def test_compute_defaults_every_content_type(client, cid):
    for ct in CONTENT_TYPES:
        r = client.post(f"/api/classes/{cid}/compute", json={"content_type": ct})
        assert r.status_code == 200, (cid, ct, r.text)
        b = r.json()
        assert math.isfinite(b["total_dps"]) and b["total_dps"] > 0, (cid, ct)
        assert b["skills"] and all({"key", "name", "dps", "share", "boss_dps", "normal_dps", "unlocked"} <= set(s) for s in b["skills"])
        assert isinstance(b["derived"], dict) and isinstance(b["engine_on"], bool)
        comp = b["companion"]
        # no companion chosen: absent (FP-Mage), or the stun-only block (classes with a player stun, e.g. Hero's Rush, report its effect
        # on the boss phase as a small non-negative 'companion' dps even with choice None)
        assert comp is None or (comp["choice"] == "None" and comp["level"] == 0 and comp["dps"] >= 0)


@pytest.mark.parametrize("cid", CLASS_IDS)
def test_compute_edited_values(client, cid):
    flat, pct, sub = main_fields(cid, client.get(f"/api/classes/{cid}/schema").json())
    base = {"content_type": "World Boss", "level": 140, "flat_attack": 1_000_000, flat: 50000, pct: 300, sub: 800, "crit_rate": 80, "crit_damage": 120,
            "def_pen": 50, "boss_damage": 100, "final_damage": 30}
    t0 = client.post(f"/api/classes/{cid}/compute", json=base).json()["total_dps"]
    for key, value in (("flat_attack", 2_000_000), (flat, 100000), ("boss_damage", 200), ("final_damage", 60)):
        t1 = client.post(f"/api/classes/{cid}/compute", json=dict(base, **{key: value})).json()["total_dps"]
        assert t1 > t0, (cid, key)
    for extra in EXTRA_FIELDS.get(cid, ()):                              # class-specific fields are accepted and move nothing out of range
        r = client.post(f"/api/classes/{cid}/compute", json=dict(base, **{extra: 5}))
        assert r.status_code == 200, (cid, extra, r.text)
    # the main-stat fields of ANOTHER class are unknown here
    other = "flat_dex" if flat != "flat_dex" else "flat_str"
    bad = client.post(f"/api/classes/{cid}/compute", json=dict(base, **{other: 1}))
    assert bad.status_code == 422 and bad.json()["errors"][0]["field"] == other


@pytest.mark.parametrize("cid", CLASS_IDS)
def test_companion_choice_none_and_chosen(client, cid):
    schema = client.get(f"/api/classes/{cid}/schema").json()
    base = {"content_type": "Chapter Boss", "level": 140, "flat_attack": 1_000_000}
    none = client.post(f"/api/classes/{cid}/compute", json=dict(base, companion_choice="None", companion_level=7)).json()
    assert none["companion"] is None or none["companion"]["choice"] == "None"
    # companion_level only matters once a companion is chosen
    assert none["total_dps"] == client.post(f"/api/classes/{cid}/compute", json=dict(base, companion_choice="None", companion_level=0)).json()["total_dps"]
    chosen = schema["companions"][0]
    one = client.post(f"/api/classes/{cid}/compute", json=dict(base, companion_choice=chosen, companion_level=10, companion_summon_time_increase_pct=20))
    assert one.status_code == 200
    comp = one.json()["companion"]
    assert comp["choice"] == chosen and comp["level"] == 10 and comp["dps"] > 0
    assert one.json()["total_dps"] > none["total_dps"]
    # every dropdown option is accepted
    for name in schema["companions"]:
        assert client.post(f"/api/classes/{cid}/compute", json=dict(base, companion_choice=name, companion_level=1)).status_code == 200, name
    assert client.post(f"/api/classes/{cid}/compute", json=dict(base, companion_level=19)).status_code == 422


# classes whose engine models artifacts: read from the schema each class reports (the 12 workbook classes all do: asserted by test_every_workbook_class_models_artifacts)
ARTIFACT_CLASSES = tuple(c for c in CLASS_IDS if _DISCOVERED[c].schema.get("artifacts_modelled"))


def test_every_workbook_class_models_artifacts():
    assert set(WORKBOOK_CLASSES) <= set(ARTIFACT_CLASSES)


@pytest.mark.parametrize("cid", ARTIFACT_CLASSES)
def test_artifacts_accepted_where_modelled(client, cid):
    r = client.post(f"/api/classes/{cid}/compute", json={"artifacts": [{"key": "arwens_glass_shoes", "star": 5}, {"key": "(none)", "star": None}]})
    assert r.status_code == 200 and r.json()["artifacts"]["buckets"]["companion_summon_time_increase_pct"] == 40


@pytest.mark.parametrize("cid", [c for c in CLASS_IDS if c not in ARTIFACT_CLASSES])
def test_artifacts_rejected_where_not_modelled(client, cid):
    r = client.post(f"/api/classes/{cid}/compute", json={"artifacts": [{"key": "(none)", "star": None}]})
    assert r.status_code == 422
    err = r.json()["errors"][0]
    assert err["field"] == "artifacts" and "not modelled" in err["message"]


def test_schema_ranges_drive_validation(client):
    ok = client.post("/api/classes/hero/compute", json={"crit_rate": 150, "chapter_stage": 39})        # excess crit rate is legal; bare chapter number
    assert ok.status_code == 200
    r = client.post("/api/classes/hero/compute", json={"level": 301, "def_pen": 150, "attack_speed": 151, "crit_rate": 501, "min_damage": -1})
    assert r.status_code == 422
    errs = {e["field"]: e["message"] for e in r.json()["errors"]}
    assert set(errs) == {"level", "def_pen", "attack_speed", "crit_rate", "min_damage"}
    assert errs["level"] == "must be between 1 and 300" and errs["def_pen"] == "must be between 0 and 100"
    r = client.post("/api/classes/hero/compute", json={"level": None})                                    # a blank level would read as 0
    assert r.status_code == 422 and r.json()["errors"][0] == {"field": "level", "message": "is required"}
    r = client.post("/api/classes/hero/compute", json={"content_type": "PvP", "pvp_fight_length": 0})
    assert r.status_code == 422 and r.json()["errors"][0]["field"] == "pvp_fight_length"
    r = client.post("/api/classes/night_lord/compute", json={"incoming_hit_rate": 1000})
    assert r.status_code == 422 and r.json()["errors"][0]["field"] == "incoming_hit_rate"


# ---- golden totals: the first three cases of each class + a spread of content types ----

def _golden_ids(golden):
    ids = list(golden)[:3]
    for marker in ("PvP", "Breakthrough", "World Boss", "Chapter Hunt", "REAL/"):
        ids += [k for k in golden if marker in k and k not in ids][:1]
    return ids


GOLDEN_CASES = []
for _cid in GOLDEN_IDS:
    _g = json.loads((GOLDEN_DIR / f"{_cid}_golden.json").read_text())
    GOLDEN_CASES += [(_cid, k, _g[k]) for k in _golden_ids(_g)]
SKIPPED = []                                                              # (class, case, reason) filled while the tests run


@pytest.mark.workbook_golden
@pytest.mark.parametrize("cid,case_id,case", GOLDEN_CASES, ids=[f"{c}:{k}" for c, k, _ in GOLDEN_CASES])
def test_compute_matches_golden(client, cid, case_id, case):
    if "reference_error" in case["out"]:
        SKIPPED.append((cid, case_id, "verify script itself crashes here (no reference number)"))
        pytest.skip("no reference number")
    fields = {f["key"] for f in client.get(f"/api/classes/{cid}/schema").json()["fields"] if not f["computed"]}
    missing = sorted(set(case["inputs"]) - fields)
    if missing:
        SKIPPED.append((cid, case_id, f"golden inputs not exposed by the form: {missing}"))
        pytest.skip(f"keys not in the API schema: {missing}")
    r = client.post(f"/api/classes/{cid}/compute", json=case["inputs"])
    if r.status_code == 422:
        fields_bad = [e["field"] for e in r.json()["errors"]]
        SKIPPED.append((cid, case_id, f"inputs outside the schema's permissive ranges: {fields_bad}"))
        pytest.skip(f"outside ranges: {fields_bad}")
    assert r.status_code == 200, r.json()
    assert math.isclose(r.json()["total_dps"], case["out"]["total_dps"], rel_tol=1e-12, abs_tol=0.0), (cid, case_id)


def test_first_three_golden_cases_per_class_are_not_skipped():
    for cid in GOLDEN_IDS:
        g = json.loads((GOLDEN_DIR / f"{cid}_golden.json").read_text())
        for k in list(g)[:3]:
            assert "reference_error" not in g[k]["out"], (cid, k)


# ---- engine-native classes (no workbook, no golden): the generic API contract ----

@pytest.mark.parametrize("cid", NATIVE_IDS)
def test_engine_native_result_rows_match_the_schema(client, cid):
    """The schema's ``dps_rows`` are exactly the rows of a compute result, in the same order; shares are a partition of the player's damage."""
    schema = client.get(f"/api/classes/{cid}/schema").json()
    rows = [tuple(r) for r in schema["dps_rows"]]
    assert rows and len({k for k, _n in rows}) == len(rows) and all(n for _k, n in rows)
    for ct in ("World Boss", "Chapter Hunt", "Breakthrough"):
        b = client.post(f"/api/classes/{cid}/compute", json={"content_type": ct, "level": 140, "flat_attack": 250000}).json()
        assert [(s["key"], s["name"]) for s in b["skills"]] == rows, ct
        assert all(math.isfinite(s["dps"]) and s["dps"] >= 0 for s in b["skills"])
        assert math.isclose(sum(s["dps"] for s in b["skills"]), b["player_dps"], rel_tol=1e-9), (cid, ct)


@pytest.mark.parametrize("cid", NATIVE_IDS)
def test_engine_native_sensitivity_and_cube_tabs(client, cid):
    """Stat values, the sensitivity meta and the three cube-tab endpoints answer for the class (its spec maps its stats): shape + the engine called directly."""
    entry = _DISCOVERED[cid]
    body = {"content_type": "World Boss", "level": 140, "flat_attack": 250000, "companion_choice": "Blaze Wizard", "companion_level": 10}
    r = client.post(f"/api/classes/{cid}/sensitivity", json=body)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["class_id"] == cid and out["baseline_total"] > 0 and {"stats", "artifacts", "companions", "summon_time", "cdr"} <= set(out)
    meta = client.get(f"/api/classes/{cid}/sensitivity/meta").json()
    assert [x["key"] for x in out["stats"]["rows"]] == [x["key"] for x in meta["stats"]] and len(out["artifacts"]["rows"]) == 36 and len(out["companions"]["rows"]) == 16
    assert "NaN" not in r.text
    assert client.get(f"/api/classes/{cid}/cubes/meta").status_code == 200
    gear = [{"slot": "head", "potential_type": "Potential", "rarity": "epic", "pity": 12, "lines": [{"stat": "Damage %", "value": 12}, {"stat": "Critical Rate %", "value": 3}]}]
    c = client.post(f"/api/classes/{cid}/cubes", json={**body, "gear": gear, "only": ["head"]})
    assert c.status_code == 200 and c.json()["baseline_total"] == pytest.approx(out["baseline_total"], rel=1e-12), c.text
    e = client.post(f"/api/classes/{cid}/equipment-compare", json={**body, "current": {"attack": 1000, "lines": []}, "new": {"attack": 1500, "lines": [{"stat": "Main Stat (flat)", "value": 300}]}})
    assert e.status_code == 200, e.text
    spec = sens_specs.get(cid)
    assert e.json()["rate_by_stat"]["Main Stat (flat)"] > 0 and e.json()["rate_by_stat"]["Main Stat (flat)"] == pytest.approx(
        next(x["dps_gain"] for x in out["stats"]["rows"] if x["key"] == spec.mainstat.flat), rel=1e-12)
    p = client.post(f"/api/classes/{cid}/artifact-potentials", json={**body, "potentials": {"hexagon_necklace": {"star": 5, "lines": [{"rarity": "Legendary", "stat": "Damage %"}]}}})
    assert p.status_code == 200 and next(x for x in p.json()["rows"] if x["key"] == "hexagon_necklace")["total"] > 0, p.text
    assert entry.supports_sensitivity
