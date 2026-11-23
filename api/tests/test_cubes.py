"""POST /api/classes/{id}/cubes, /equipment-compare, /artifact-potentials and GET .../cubes/meta: golden vs the engine, validation, 501, row cache,
rate limits, timeout / failure paths.

Run from the repo root:  python -m pytest api/tests -q   (a handful of real engine evaluations, ~1-3 s each; the 30-row call is ~6 s without numpy)
"""
import math
import time

import pytest
from fastapi.testclient import TestClient

from api import features, registry
from api.main import create_app
from api.settings import Settings
from api.tests._unsupported import unsupported_class
from engine import cubes, equipment, potentials, sensitivity
from engine.classes import fp_mage

CASE = {"content_type": "World Boss", "companion_choice": "Blaze Wizard", "companion_level": 10}
CUBES = "/api/classes/fp_mage/cubes"
EQUIP = "/api/classes/fp_mage/equipment-compare"
POTS = "/api/classes/fp_mage/artifact-potentials"

GEAR = [
    {"slot": "head", "potential_type": "Potential", "rarity": "epic", "pity": 12,
     "lines": [{"stat": "Damage %", "value": 12}, {"stat": "Critical Rate %", "value": 3}, {"stat": "Skill Cooldown Decrease (seconds)", "value": 0.5}]},
    {"slot": "boots", "potential_type": "Bonus Potential", "rarity": "unique", "pity": 0,
     "lines": [{"stat": "Companion Summoning Time Increase %", "value": 8}]},
    {"slot": "ring", "potential_type": "Potential", "rarity": "legendary", "pity": 100, "lines": [{"stat": "Final Damage %", "value": 6}]},
]


def make_client(**kw):
    for k in ("rate_limit_per_minute", "rate_limit_sens_per_minute", "rate_limit_cubes_per_minute", "rate_limit_compare_per_minute"):
        kw.setdefault(k, 0)
    return TestClient(create_app(Settings(**kw)))


@pytest.fixture(scope="module")
def client():
    return make_client()


def _same(a, b, path=""):
    """Deep equality of engine output vs the API's JSON (tuples are lists, NaN / inf are null, int dict keys are strings)."""
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


def engine_inputs(body):
    from api.validation import validate_inputs
    entry = registry.discover()["fp_mage"]
    clean, errors = validate_inputs(entry.schema, entry.defaults, body)
    assert not errors
    return clean


def engine_gear(raw):
    rows, errors = features.validate_gear(raw)
    assert not errors
    return rows


# ---- meta ------------------------------------------------------------------------------------------------------------------------------------
def test_meta_matches_engine_tables(client):
    r = client.get(CUBES + "/meta")
    assert r.status_code == 200
    m = r.json()
    assert [s["key"] for s in m["slots"]] == cubes.CUBE_SLOTS and len(m["slots"]) == 15
    assert m["potential_types"] == ["Potential", "Bonus Potential"]
    assert [x["key"] for x in m["rarities"]] == cubes.RARITY_ORDER
    assert m["stats"] == cubes.all_potential_stats()
    assert m["pity_caps"]["Potential"]["normal"] == 30 and m["pity_caps"]["Bonus Potential"]["normal"] == 42       # CLAUDE.md item 17: separate caps
    assert m["pity_caps"]["Potential"]["legendary"] == m["pity_caps"]["Bonus Potential"]["legendary"] == 714
    assert m["milestones"] == cubes.CUBE_MILESTONES and m["csv_columns"] == cubes.CSV_COLUMNS and len(m["csv_columns"]) == 57
    assert "Companion Summoning Time Increase %" in m["stats_by_slot"]["boots"] and "Companion Summoning Time Increase %" not in m["stats_by_slot"]["head"]
    assert "Skill Cooldown Decrease (seconds)" in m["stats_by_slot"]["head"]
    assert m["equipment"]["stats"] == equipment.DROPDOWN_STATS and len(m["equipment"]["stats"]) == 21 and m["equipment"]["lines"] == 5
    ap = m["artifact_potentials"]
    assert ap["rarities"] == potentials.RARITIES and ap["line_min_star"] == [1, 2, 5] and len(ap["artifacts"]) == 36
    assert {a["lines"] for a in ap["artifacts"]} == {2, 3} and ap["values"]["Damage %"]["Legendary"] == 14
    assert m["class_id"] == "fp_mage"


def test_unsupported_class_is_501_before_validation(client, monkeypatch):
    for cid in (unsupported_class(monkeypatch),):
        for method, suffix in (("get", "/cubes/meta"), ("post", "/cubes"), ("post", "/equipment-compare"), ("post", "/artifact-potentials")):
            r = getattr(client, method)(f"/api/classes/{cid}{suffix}", **({"json": {"gear": "nonsense", "bogus": 1}} if method == "post" else {}))
            assert r.status_code == 501, (cid, suffix)
            assert r.json()["detail"].endswith("modelled for this class yet")
    assert client.post("/api/classes/nope/cubes", json={}).status_code == 404
    assert client.get("/api/classes/nope/cubes/meta").status_code == 404
    assert client.post("/api/classes/nope/equipment-compare", json={}).status_code == 404


# ---- cubes: golden ---------------------------------------------------------------------------------------------------------------------------
def test_cubes_match_engine_directly(client):
    body = {**CASE, "gear": GEAR, "only": ["head", "boots"]}
    r = client.post(CUBES, json=body)
    assert r.status_code == 200, r.text
    out = r.json()
    inputs = dict(engine_inputs(CASE))
    gear = engine_gear(GEAR)
    inputs["companion_potential_lines_pct"] = cubes.companion_lines_pct(gear)
    sens = sensitivity.run(fp_mage, dict(inputs), which=["stats", "cdr", "summon_time"])
    pricing = cubes.pricing_from_sensitivity(sens, dict(inputs), fp_mage)
    idx = {i for i, g in enumerate(gear) if g["slot"] in ("head", "boots")}
    direct = cubes.recommend(gear, pricing, only=idx)
    assert len(out["rows"]) == len(direct) == 4
    _same(direct, out["rows"])
    assert out["baseline_total"] == pytest.approx(sens["baseline_total"], rel=1e-12)
    assert out["milestones"] == cubes.CUBE_MILESTONES and out["csv_columns"] == cubes.CSV_COLUMNS
    assert r.headers["x-cache"] == "MISS"
    head = next(x for x in out["rows"] if x["slot"] == "head" and x["potential_type"] == "Potential")
    assert head["rarity"] == "epic" and head["lines"][0] == ["Damage %", 12.0] and head["current_value"] > 0 and head["milestone_ev"]["100"] >= head["milestone_ev"]["5"]
    assert "NaN" not in r.text and "Infinity" not in r.text


def test_only_selects_rows_and_types(client):
    r = client.post(CUBES, json={**CASE, "gear": GEAR, "only": [{"slot": "ring", "potential_type": "Potential"}]})
    assert r.status_code == 200, r.text
    rows = r.json()["rows"]
    assert [(x["slot"], x["potential_type"]) for x in rows] == [("ring", "Potential")]
    assert rows[0]["rarity"] == "legendary" and rows[0]["pity"] == 100


def test_full_call_has_30_rows():
    c = make_client()
    t0 = time.perf_counter()
    r = c.post(CUBES, json={**CASE, "gear": GEAR})
    assert r.status_code == 200, r.text
    rows = r.json()["rows"]
    assert len(rows) == 30 and {(x["slot"], x["potential_type"]) for x in rows} == {(s, t) for s in cubes.CUBE_SLOTS for t in cubes.POTENTIAL_TYPES}
    # CSV order: Potential first, then Bonus Potential, each by smallest N ascending (never-positive last)
    assert [x["potential_type"] for x in rows] == ["Potential"] * 15 + ["Bonus Potential"] * 15
    for t in cubes.POTENTIAL_TYPES:
        ns = [x["smallest_n"] if x["smallest_n"] is not None else math.inf for x in rows if x["potential_type"] == t]
        assert ns == sorted(ns)
    assert time.perf_counter() - t0 < 60


# ---- cubes: row cache ------------------------------------------------------------------------------------------------------------------------
def test_row_cache_hit_partial_and_invalidation():
    c = make_client()
    body = {**CASE, "gear": GEAR, "only": ["head"]}
    a = c.post(CUBES, json=body)
    assert a.headers["x-cache"] == "MISS"
    b = c.post(CUBES, json=body)
    assert b.headers["x-cache"] == "HIT" and b.content == a.content
    assert c.app.state.pricing.pricing_builds == 1
    # a different slot's lines do not touch the head rows (no summoning-time lines involved): head is a HIT, ring is computed -> PARTIAL
    gear2 = [dict(g) for g in GEAR]
    gear2[2] = dict(gear2[2], lines=[{"stat": "Damage %", "value": 5}])
    p = c.post(CUBES, json={**CASE, "gear": gear2, "only": ["head", "ring"]})
    assert p.headers["x-cache"] == "PARTIAL"
    assert c.post(CUBES, json={**CASE, "gear": gear2, "only": ["head", "ring"]}).headers["x-cache"] == "HIT"
    # changing the boots' summoning-time lines moves the pricing for everybody
    gear3 = [dict(g) for g in GEAR]
    gear3[1] = dict(gear3[1], lines=[{"stat": "Companion Summoning Time Increase %", "value": 12}])
    assert c.post(CUBES, json={**CASE, "gear": gear3, "only": ["head"]}).headers["x-cache"] == "MISS"
    assert c.post(CUBES, json={**CASE, "gear": GEAR, "only": ["head"], "flat_attack": 123456}).headers["x-cache"] == "MISS"


def test_cache_disabled():
    c = make_client(cubes_cache_entries=0)
    body = {**CASE, "gear": GEAR[:1], "only": ["ring"]}
    assert [c.post(CUBES, json=body).headers["x-cache"] for _ in range(2)] == ["MISS", "MISS"]


# ---- cubes: validation -----------------------------------------------------------------------------------------------------------------------
def test_cubes_validation_errors(client):
    bad = {"level": 0, "flat_attack": "lots", "bogus": 1,
           "gear": [{"slot": "hat", "rarity": "epic"},
                    {"slot": "head", "potential_type": "Potential", "rarity": "godly", "pity": -1, "lines": [{"stat": "Nope", "value": 1}]},
                    {"slot": "head", "potential_type": "Potential"},
                    {"slot": "cape", "pity": 1.5, "lines": [{"stat": "Damage %", "value": "x"}] * 4, "extra": 1}],
           "only": ["head", "tail"]}
    r = client.post(CUBES, json=bad)
    assert r.status_code == 422
    errs = {e["field"]: e["message"] for e in r.json()["errors"]}
    assert {"level", "flat_attack", "bogus", "gear[0].slot", "gear[1].rarity", "gear[1].pity", "gear[1].lines[0].stat", "gear[2]", "gear[3]", "gear[3].pity",
            "gear[3].lines"} <= set(errs)
    assert "Traceback" not in r.text
    for body in ({"gear": "x"}, {"gear": {}}, {"gear": [1]}, {"gear": [{"slot": "head", "lines": "x"}]}, {"gear": [{"slot": "head", "lines": [1]}]},
                 {"gear": [{"slot": "head", "lines": [{"stat": "Damage %", "value": -1}]}]}, {"gear": [{"slot": "head", "lines": [{"stat": "Damage %", "value": 1e12}]}]},
                 {"gear": [{"slot": "head", "rarity": 5}]}, {"gear": [{"slot": "head", "pity": 100000}]}, {"gear": [{"slot": "head", "pity": True}]},
                 {"only": []}, {"only": "head"}, {"only": [5]}, {"only": [{"slot": "head", "potential_type": "Mega"}]},
                 {"gear": [{"slot": s, "potential_type": t} for s in cubes.CUBE_SLOTS for t in cubes.POTENTIAL_TYPES] + [{"slot": "head"}]}):
        rr = client.post(CUBES, json=body)
        assert rr.status_code == 422, body
    assert client.post(CUBES, json=[1, 2]).status_code == 422
    assert client.post(CUBES, content=b"{nope", headers={"content-type": "application/json"}).status_code == 422


def test_rarity_is_case_insensitive_and_defaults_fill_in(client):
    rows, errors = features.validate_gear([{"slot": "cape", "rarity": " Epic "}])
    assert not errors and len(rows) == 30 and next(r for r in rows if r["slot"] == "cape" and r["potential_type"] == "Potential")["rarity"] == "epic"
    assert [(r["slot"], r["potential_type"]) for r in rows] == [(g["slot"], g["potential_type"]) for g in cubes.default_gear()]
    full, errors = features.validate_gear(None)
    assert not errors and full == [dict(g, lines=list(g["lines"]), pity=0) for g in cubes.default_gear()]


# ---- cubes: limits / failures ----------------------------------------------------------------------------------------------------------------
def test_cubes_has_its_own_rate_limit():
    c = make_client(rate_limit_per_minute=100, rate_limit_cubes_per_minute=2)
    body = {**CASE, "gear": GEAR[:1], "only": ["ring"]}
    codes = [c.post(CUBES, json=body).status_code for _ in range(4)]
    assert codes == [200, 200, 429, 429]
    assert c.post(CUBES, json=body).headers["retry-after"]
    assert c.get("/api/classes").status_code == 200
    assert c.get(CUBES + "/meta").status_code == 200                      # static, not part of the cubes limit
    assert c.post("/api/classes/fp_mage/compute", json={}).status_code == 200


def test_compare_endpoints_share_their_own_limit():
    c = make_client(rate_limit_per_minute=100, rate_limit_compare_per_minute=3)
    codes = [c.post(EQUIP, json=CASE).status_code for _ in range(2)] + [c.post(POTS, json=CASE).status_code for _ in range(2)]
    assert codes == [200, 200, 200, 429]
    assert c.post(CUBES, json={**CASE, "only": ["ring"]}).status_code == 200      # cubes keeps its own allowance


def test_settings_defaults_and_env(monkeypatch):
    s = Settings()
    assert (s.rate_limit_cubes_per_minute, s.cubes_timeout_s, s.cubes_workers, s.cubes_cache_ttl_s, s.rate_limit_compare_per_minute) == (20, 45, 2, 600, 60)
    monkeypatch.setenv("MSI_RATE_LIMIT_CUBES_PER_MIN", "3")
    monkeypatch.setenv("MSI_RATE_LIMIT_COMPARE_PER_MIN", "9")
    monkeypatch.setenv("MSI_CUBES_TIMEOUT_S", "7")
    monkeypatch.setenv("MSI_CUBES_WORKERS", "1")
    monkeypatch.setenv("MSI_CUBES_CACHE_ENTRIES", "5")
    monkeypatch.setenv("MSI_CUBES_CACHE_TTL_S", "11")
    s = Settings.from_env()
    assert (s.rate_limit_cubes_per_minute, s.rate_limit_compare_per_minute, s.cubes_timeout_s, s.cubes_workers, s.cubes_cache_entries, s.cubes_cache_ttl_s) == (3, 9, 7, 1, 5, 11)


def test_cubes_failure_is_500_without_trace(monkeypatch):
    c = make_client()

    def boom(*a, **k):
        raise RuntimeError("secret internals")

    monkeypatch.setattr(features, "run_cubes", boom)
    r = c.post(CUBES, json={**CASE, "gear": GEAR[:1], "only": ["ring"]})
    assert r.status_code == 500 and "secret" not in r.text and "Traceback" not in r.text
    assert len(c.app.state.cubes_cache) == 0


def test_cubes_timeout_guard_is_504(monkeypatch):
    c = make_client(cubes_timeout_s=1)

    def slow(*a, **k):
        time.sleep(1.6)
        return {}

    monkeypatch.setattr(features, "run_cubes", slow)
    r = c.post(CUBES, json={**CASE, "gear": GEAR[:1], "only": ["ring"]})
    assert r.status_code == 504 and "longer than 1 s" in r.json()["detail"]
    time.sleep(0.8)                                                       # let the worker thread finish before the monkeypatch is undone
    assert len(c.app.state.cubes_cache) == 0


def test_cubes_concurrency_cap_queues_requests(monkeypatch):
    """One worker: two concurrent requests are serialised (the second waits for the first), never run side by side."""
    import threading
    c = make_client(cubes_workers=1, cubes_timeout_s=20)
    state = {"now": 0, "peak": 0}
    lock = threading.Lock()

    def fake(service, entry, clean, gear, indices, cache=None, class_id=None):
        with lock:
            state["now"] += 1
            state["peak"] = max(state["peak"], state["now"])
        time.sleep(0.3)
        with lock:
            state["now"] -= 1
        raise RuntimeError("done")

    monkeypatch.setattr(features, "run_cubes", fake)
    ts = [threading.Thread(target=lambda: c.post(CUBES, json={**CASE, "only": ["ring"]})) for _ in range(3)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert state["peak"] == 1


# ---- equipment compare -----------------------------------------------------------------------------------------------------------------------
EQ_BODY = {**CASE, "current": {"attack": 1500, "lines": [{"stat": "Damage %", "value": 14}, {"stat": "Critical Rate %", "value": 3}]},
           "new": {"attack": 2200, "lines": [{"stat": "Final Damage %", "value": 6}, {"stat": "Min Damage %", "value": 15}, {"stat": "Damage %", "value": 5}]}}


def test_equipment_matches_engine_directly(client):
    r = client.post(EQUIP, json=EQ_BODY)
    assert r.status_code == 200, r.text
    out = r.json()
    inputs = engine_inputs(CASE)
    sens = sensitivity.run(fp_mage, dict(inputs), which=["stats"])
    rates, total = cubes.sweep_rates(sens), sens["baseline_total"]
    m = fp_mage.model(dict(inputs))
    direct = equipment.compare({"attack": 1500, "lines": [("Damage %", 14), ("Critical Rate %", 3)]},
                               {"attack": 2200, "lines": [("Final Damage %", 6), ("Min Damage %", 15), ("Damage %", 5)]}, rates, total, m.crit_rate)
    for k in ("current", "new", "delta_pct", "delta_dps", "better"):
        _same(direct[k], out[k], k)
    assert out["baseline_total"] == pytest.approx(total, rel=1e-12) and out["crit_priced_as_crit_damage"] is False
    assert len(out["current"]["rows"]) == 6 and len(out["new"]["rows"]) == 6 and set(out["rate_by_stat"]) == set(equipment.DROPDOWN_STATS)
    assert out["delta_pct"] == pytest.approx(out["new"]["pct"] - out["current"]["pct"], rel=1e-12)


def test_equipment_same_stat_lines_merge_and_blank_sides(client):
    one = client.post(EQUIP, json={**CASE, "current": {"attack": 0, "lines": [{"stat": "Damage %", "value": 10}]}, "new": {"attack": 0, "lines": [
        {"stat": "Damage %", "value": 4}, {"stat": "Damage %", "value": 6}]}}).json()
    assert one["delta_pct"] == pytest.approx(0, abs=1e-12) and one["better"] == "equal"
    blank = client.post(EQUIP, json=CASE).json()                            # no current / new at all: nothing to compare
    assert blank["current"]["total_gain"] == 0 and blank["new"]["total_gain"] == 0 and blank["better"] == "equal"


def test_equipment_rates_are_cached_between_edits():
    c = make_client()
    assert c.post(EQUIP, json=EQ_BODY).status_code == 200
    t0 = time.perf_counter()
    other = {**EQ_BODY, "new": {"attack": 9999, "lines": []}}
    assert c.post(EQUIP, json=other).status_code == 200
    assert c.app.state.pricing.rates_builds == 1 and time.perf_counter() - t0 < 0.5
    assert c.post(EQUIP, json={**EQ_BODY, "flat_attack": 777777}).status_code == 200
    assert c.app.state.pricing.rates_builds == 2


def test_equipment_validation(client):
    r = client.post(EQUIP, json={"level": 0, "current": {"attack": -1, "lines": [{"stat": "Int", "value": 1}] * 6, "x": 1}, "new": {"attack": "a", "lines": [
        {"stat": "Damage %", "value": float("1e30")}]}})
    assert r.status_code == 422
    fields = {e["field"] for e in r.json()["errors"]}
    assert {"level", "current", "current.attack", "current.lines", "current.lines[0].stat", "new.attack", "new.lines[0].value"} <= fields
    for body in ({"current": []}, {"new": "x"}, {"current": {"lines": {}}}, {"current": {"lines": [["Damage %", 1]]}}):
        assert client.post(EQUIP, json=body).status_code == 422, body


def test_equipment_failure_paths(monkeypatch):
    c = make_client(sens_timeout_s=1)
    entry = c.app.state.classes["fp_mage"]

    def slow(self, inputs, which=None, companion_level=None):
        time.sleep(1.6)
        return {}

    monkeypatch.setattr(type(entry), "sensitivity", slow)
    r = c.post(EQUIP, json=CASE)
    assert r.status_code == 504 and "longer than 1 s" in r.json()["detail"]
    time.sleep(0.8)
    monkeypatch.undo()
    c2 = make_client()
    monkeypatch.setattr(type(c2.app.state.classes["fp_mage"]), "sensitivity", lambda self, inputs, which=None, companion_level=None: (_ for _ in ()).throw(RuntimeError("secret")))
    r = c2.post(EQUIP, json=CASE)
    assert r.status_code == 500 and "secret" not in r.text


def test_equipment_zero_total_dps_is_422():
    c = make_client()
    svc = c.app.state.pricing
    svc.cached_rates = lambda *a: True
    svc.rates_context = lambda entry, clean: {"rates": {}, "total_dps": 0.0, "crit_rate_total": 0, "ring_of_cycles_equipped": False, "book_of_ancient_equipped": False}
    r = c.post(EQUIP, json=CASE)
    assert r.status_code == 422 and "Total DPS is 0" in r.json()["errors"][0]["message"]


# ---- artifact potentials ---------------------------------------------------------------------------------------------------------------------
POT_BODY = {**CASE, "artifacts": [{"key": "book_of_ancient", "star": 5}],
            "potentials": {"book_of_ancient": {"lines": [{"rarity": "Legendary", "stat": "Damage %"}, {"rarity": "Epic", "stat": "Critical Rate %"}, {"rarity": "Unique", "stat": "Damage %"}]},
                           "pigs_ribbon": {"star": 3, "lines": [{"rarity": "Mystic (Prime)", "stat": "Defense Penetration %"}]}}}


def test_potentials_match_engine_directly(client):
    r = client.post(POTS, json=POT_BODY)
    assert r.status_code == 200, r.text
    out = r.json()
    inputs = engine_inputs({k: v for k, v in POT_BODY.items() if k != "potentials"})
    sens = sensitivity.run(fp_mage, dict(inputs), which=["stats"])
    rates, total = cubes.sweep_rates(sens), sens["baseline_total"]
    state = {"book_of_ancient": {"star": 5, "lines": [("Legendary", "Damage %"), ("Epic", "Critical Rate %"), ("Unique", "Damage %")]},
             "pigs_ribbon": {"star": 3, "lines": [("Mystic (Prime)", "Defense Penetration %")]}}
    direct = potentials.potential_table(state, rates, total, ["book_of_ancient"])
    _same(direct, out["rows"])
    rows = {x["key"]: x for x in out["rows"]}
    assert len(out["rows"]) == 36 and rows["book_of_ancient"]["equipped"] is True and rows["pigs_ribbon"]["equipped"] is False
    book = rows["book_of_ancient"]
    assert book["star"] == 5 and len(book["lines"]) == (3 if book["rank"] == "Legendary" else 2) and book["total"] > 0
    assert rows["pigs_ribbon"]["total"] > 0


def test_potentials_slot_star_and_line_gating(client):
    # Not Unlocked (star 0) activates nothing; the equipped artifact takes its slot's star unless the potentials entry sets one
    body = {**CASE, "artifacts": [{"key": "book_of_ancient", "star": "Not Unlocked"}],
            "potentials": {"book_of_ancient": {"lines": [{"rarity": "Legendary", "stat": "Damage %"}]}}}
    row = next(x for x in client.post(POTS, json=body).json()["rows"] if x["key"] == "book_of_ancient")
    assert row["star"] == 0 and row["total"] == 0 and row["lines"][0]["active"] is False
    body["potentials"]["book_of_ancient"]["star"] = 1
    row = next(x for x in client.post(POTS, json=body).json()["rows"] if x["key"] == "book_of_ancient")
    assert row["star"] == 1 and row["lines"][0]["active"] is True and row["total"] > 0
    # the line list is capped by the artifact's rank
    legend = next(a for a in features.cubes_meta()["artifact_potentials"]["artifacts"] if a["lines"] == 3)["key"]
    epic = next(a for a in features.cubes_meta()["artifact_potentials"]["artifacts"] if a["lines"] == 2)["key"]
    three = [{"rarity": "Rare", "stat": "Damage %"}] * 3
    assert client.post(POTS, json={**CASE, "potentials": {legend: {"star": 5, "lines": three}}}).status_code == 200
    r = client.post(POTS, json={**CASE, "potentials": {epic: {"star": 5, "lines": three}}})
    assert r.status_code == 422 and r.json()["errors"][0]["field"] == f"potentials.{epic}.lines"


def test_potentials_feed_the_sensitivity_hook(client):
    """The per-artifact totals are exactly what ``engine.sensitivity`` takes as ``artifact_potential_gain`` (so a later include_potentials flag is a pure wiring job)."""
    out = client.post(POTS, json=POT_BODY).json()
    inputs = engine_inputs({k: v for k, v in POT_BODY.items() if k != "potentials"})
    gain = {x["key"]: x["total"] for x in out["rows"]}
    sens = sensitivity.run(fp_mage, dict(inputs, artifact_potential_gain=gain), which=["artifacts"])
    row = next(x for x in sens["artifacts"]["rows"] if x["key"] == "book_of_ancient")
    assert row["potential_gain"] == pytest.approx(gain["book_of_ancient"], rel=1e-12)


def test_potentials_validation(client):
    r = client.post(POTS, json={"level": 0, "potentials": {"nope": {}, "pigs_ribbon": {"star": 9, "lines": [{"rarity": "Godly", "stat": "Damage %"}, {"rarity": "Rare", "stat": "Zzz"}, 1],
                                                                                    "bogus": 1}}})
    assert r.status_code == 422
    fields = {e["field"] for e in r.json()["errors"]}
    assert {"level", "potentials.nope", "potentials.pigs_ribbon", "potentials.pigs_ribbon.star", "potentials.pigs_ribbon.lines[0].rarity",
            "potentials.pigs_ribbon.lines[1].stat", "potentials.pigs_ribbon.lines"} <= fields
    for body in ({"potentials": []}, {"potentials": {"pigs_ribbon": 3}}, {"potentials": {"pigs_ribbon": {"lines": "x"}}}):
        assert client.post(POTS, json=body).status_code == 422, body
    assert client.post(POTS, json={**CASE}).status_code == 200                 # no potentials at all: every artifact at its default (nothing rolled)


def test_sensitivity_endpoint_is_untouched_by_the_new_extras(client):
    # include_potentials is deliberately NOT part of /sensitivity (see api/README): an unknown key is still rejected there
    r = client.post("/api/classes/fp_mage/sensitivity", json={**CASE, "include_potentials": True})
    assert r.status_code == 422 and r.json()["errors"][0]["field"] == "include_potentials"
