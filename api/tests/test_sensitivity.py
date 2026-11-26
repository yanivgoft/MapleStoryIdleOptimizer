"""POST /api/classes/{id}/sensitivity and GET .../sensitivity/meta: golden vs the engine, 501, cache, rate limit, validation, timeout.

Run from the repo root:  python -m pytest api/tests -q   (a few real engine evaluations, ~1 s each)
"""
import json
import math
import time

import pytest
from fastapi.testclient import TestClient

from engine.data import artifacts as artifact_data
from api import registry
from api.cache import TTLCache, cache_key
from api.main import create_app
from api.settings import Settings
from api.tests._unsupported import unsupported_class
from engine import sensitivity
from engine.classes import fp_mage

URL = "/api/classes/fp_mage/sensitivity"
CASE = {"content_type": "World Boss", "companion_choice": "Blaze Wizard", "companion_level": 10}


def make_client(**kw):
    kw.setdefault("rate_limit_per_minute", 0)
    kw.setdefault("rate_limit_sens_per_minute", 0)
    return TestClient(create_app(Settings(**kw)))


@pytest.fixture(scope="module")
def client():
    return make_client()


def _same(a, b, path=""):
    """Deep equality of engine output vs the API's JSON (NaN / inf -> None)."""
    if isinstance(a, float):
        if not math.isfinite(a):
            assert b is None, path
        else:
            assert math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12), path
    elif isinstance(a, dict):
        assert set(a) == set(b), path
        for k in a:
            _same(a[k], b[k], f"{path}.{k}")
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


# ---- golden ----------------------------------------------------------------------------------------------------------------------------------
def test_matches_engine_directly(client):
    r = client.post(URL, json=CASE)
    assert r.status_code == 200, r.text
    body = r.json()
    direct = sensitivity.run(fp_mage, engine_inputs(CASE))
    _same(direct, body)
    assert len(body["stats"]["rows"]) == 27 and len(body["artifacts"]["rows"]) == len(artifact_data.ARTIFACT_LABELS) and len(body["companions"]["rows"]) == 16
    assert r.headers["x-cache"] == "MISS"
    json.loads(r.text)                                   # strictly valid JSON (no NaN / Infinity tokens)
    assert "NaN" not in r.text and "Infinity" not in r.text


def test_which_selects_parts_and_options(client):
    body = {**CASE, "which": ["cdr", "stats"], "companion_comparison_level": 5, "artifact_stars": {"charm_of_the_undead": 0}}
    r = client.post(URL, json=body)
    assert r.status_code == 200, r.text
    out = r.json()
    assert "stats" in out and "cdr" in out and not {"artifacts", "companions", "summon_time"} & set(out)
    direct = sensitivity.run(fp_mage, dict(engine_inputs(CASE), artifact_stars={"charm_of_the_undead": 0}), which=["stats", "cdr"], companion_level=5)
    _same(direct, out)
    r2 = client.post(URL, json={**CASE, "which": ["companions"], "companion_comparison_level": 5})
    assert {x["level"] for x in r2.json()["companions"]["rows"]} == {5}


def test_artifacts_slots_reach_the_engine(client):
    body = {**CASE, "which": ["artifacts"], "artifacts": [{"key": "charm_of_the_undead", "star": 5}]}
    rows = {x["key"]: x for x in client.post(URL, json=body).json()["artifacts"]["rows"]}
    assert rows["charm_of_the_undead"]["equipped"] is True
    plain = {x["key"]: x for x in client.post(URL, json={**CASE, "which": ["artifacts"]}).json()["artifacts"]["rows"]}
    assert plain["charm_of_the_undead"]["equipped"] is False


# ---- 501 / 404 / meta ------------------------------------------------------------------------------------------------------------------------
def test_unsupported_class_is_501(client, monkeypatch):
    for cid in (unsupported_class(monkeypatch),):
        r = client.post(f"/api/classes/{cid}/sensitivity", json={})
        assert r.status_code == 501 and r.json() == {"detail": "stat values are not modelled for this class yet"}
        assert client.get(f"/api/classes/{cid}/sensitivity/meta").status_code == 501
    assert client.post("/api/classes/nope/sensitivity", json={}).status_code == 404
    assert client.get("/api/classes/nope/sensitivity/meta").status_code == 404


def test_501_comes_before_validation(client, monkeypatch):
    # a body that would be a 422 for the class's compute (bogus part) is still a plain 501 here
    assert client.post(f"/api/classes/{unsupported_class(monkeypatch)}/sensitivity", json={"artifacts": [], "which": ["bogus"]}).status_code == 501


def test_status_flag_follows_the_capability_check(client):
    st = {c["id"]: c["status"]["stat_values"] for c in client.get("/api/classes").json()["classes"]}
    assert st["fp_mage"] is True
    assert all(v is False for k, v in st.items() if k not in registry.SENSITIVITY_CLASSES and not hasattr(sensitivity, "supports"))


def test_meta(client):
    r = client.get(URL + "/meta")
    assert r.status_code == 200
    m = r.json()
    assert m["parts"] == ["stats", "artifacts", "companions", "summon_time", "cdr"]
    assert [s["key"] for s in m["stats"]] == [s["key"] for s in sensitivity.STAT_SWEEP] and len(m["stats"]) == 27
    assert {"key", "label", "type", "step", "semantics"} <= set(m["stats"][0])
    assert len(m["artifacts"]) == len(artifact_data.ARTIFACT_LABELS) and {"key", "label", "rank", "no_dps_effect", "reason"} <= set(m["artifacts"][0])
    assert m["cdr_values"][0] == 0.5 and "LOWER" in m["metric"]["units_per_1pct"]


# ---- cache -----------------------------------------------------------------------------------------------------------------------------------
def test_cache_hit_is_identical_and_fast():
    c = make_client()
    body = {**CASE, "which": ["stats"]}
    t0 = time.perf_counter()
    a = c.post(URL, json=body)
    t1 = time.perf_counter()
    b = c.post(URL, json=body)
    t2 = time.perf_counter()
    assert (a.headers["x-cache"], b.headers["x-cache"]) == ("MISS", "HIT")
    assert a.content == b.content
    assert (t2 - t1) < (t1 - t0)
    # a defaults-spelled-out body is the same canonical request: hit as well
    full = {**body, **{k: v for k, v in registry.discover()["fp_mage"].defaults("World Boss").items() if k == "level"}}
    assert c.post(URL, json=full).headers["x-cache"] == "HIT"
    other = c.post(URL, json={**body, "flat_attack": 5e5})
    assert other.headers["x-cache"] == "MISS"
    assert c.post(URL, json={**body, "which": ["stats", "cdr"]}).headers["x-cache"] == "MISS"


def test_cache_disabled():
    c = make_client(sens_cache_entries=0)
    body = {**CASE, "which": ["cdr"]}
    assert [c.post(URL, json=body).headers["x-cache"] for _ in range(2)] == ["MISS", "MISS"]


def test_ttlcache_lru_and_expiry():
    t = [0.0]
    c = TTLCache(max_entries=2, ttl_s=10, clock=lambda: t[0])
    c.put("a", 1)
    c.put("b", 2)
    assert c.get("a") == 1                     # a is now the most recently used
    c.put("c", 3)                              # evicts b
    assert c.get("b") is None and c.get("a") == 1 and c.get("c") == 3
    t[0] = 11.0
    assert c.get("a") is None and len(c) <= 2
    assert (c.hits, c.misses) == (3, 2)
    assert cache_key("x", {"a": 1, "b": 2}) == cache_key("x", {"b": 2, "a": 1}) != cache_key("x", {"a": 1, "b": 3})


# ---- rate limit ------------------------------------------------------------------------------------------------------------------------------
def test_sensitivity_has_its_own_tighter_rate_limit():
    c = make_client(rate_limit_per_minute=100, rate_limit_sens_per_minute=2)
    body = {**CASE, "which": ["cdr"]}
    codes = [c.post(URL, json=body).status_code for _ in range(4)]
    assert codes == [200, 200, 429, 429]
    assert c.post(URL, json=body).headers["retry-after"]
    assert c.get("/api/classes").status_code == 200                       # other endpoints keep their own (larger) allowance
    assert c.post("/api/classes/fp_mage/compute", json={}).status_code == 200
    assert c.get(URL + "/meta").status_code == 200                        # the static metadata is cheap and not part of the sensitivity limit


def test_sensitivity_limit_default_is_20():
    assert Settings().rate_limit_sens_per_minute == 20 and Settings().sens_cache_entries == 128 and Settings().sens_cache_ttl_s == 600


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("MSI_RATE_LIMIT_SENS_PER_MIN", "7")
    monkeypatch.setenv("MSI_SENS_CACHE_ENTRIES", "5")
    monkeypatch.setenv("MSI_SENS_CACHE_TTL_S", "30")
    monkeypatch.setenv("MSI_SENS_TIMEOUT_S", "9")
    s = Settings.from_env()
    assert (s.rate_limit_sens_per_minute, s.sens_cache_entries, s.sens_cache_ttl_s, s.sens_timeout_s) == (7, 5, 30, 9)


# ---- validation ------------------------------------------------------------------------------------------------------------------------------
def test_validation_errors(client):
    r = client.post(URL, json={"level": 0, "flat_attack": "lots", "bogus": 1, "which": ["stats", "nope"], "companion_comparison_level": 2.5,
                               "artifact_stars": {"nonsense": 1, "pigs_ribbon": 9}})
    assert r.status_code == 422
    errs = {e["field"]: e["message"] for e in r.json()["errors"]}
    assert set(errs) == {"level", "flat_attack", "bogus", "which", "companion_comparison_level", "artifact_stars.nonsense", "artifact_stars.pigs_ribbon"}
    assert "Traceback" not in r.text
    for bad in ({"which": []}, {"which": "stats"}, {"which": [1]}, {"companion_comparison_level": 0}, {"companion_comparison_level": "x"},
                {"artifact_stars": [1]}):
        rr = client.post(URL, json=bad)
        assert rr.status_code == 422, bad
    assert client.post(URL, json=[1, 2]).status_code == 422
    assert client.post(URL, content=b"{nope", headers={"content-type": "application/json"}).status_code == 422
    assert client.post(URL, json={"artifacts": [{"key": "zzz", "star": 1}]}).json()["errors"][0]["field"] == "artifacts[0].key"


# ---- failure modes ---------------------------------------------------------------------------------------------------------------------------
def test_engine_failure_is_500_without_trace(monkeypatch):
    c = make_client()
    entry = c.app.state.classes["fp_mage"]

    def boom(self, inputs, which=None, companion_level=None):
        raise RuntimeError("secret internals")

    monkeypatch.setattr(type(entry), "sensitivity", boom)
    r = c.post(URL, json=CASE)
    assert r.status_code == 500 and "secret" not in r.text and "Traceback" not in r.text
    monkeypatch.undo()


def test_timeout_guard_is_504(monkeypatch):
    c = make_client(sens_timeout_s=1)
    entry = c.app.state.classes["fp_mage"]

    def slow(self, inputs, which=None, companion_level=None):
        time.sleep(1.6)
        return {}

    monkeypatch.setattr(type(entry), "sensitivity", slow)
    r = c.post(URL, json=CASE)
    assert r.status_code == 504 and "longer than 1 s" in r.json()["detail"]
    time.sleep(0.8)                                                            # let the worker thread finish before the monkeypatch is undone
    assert len(c.app.state.sens_cache) == 0


def test_allowlist_fallback(monkeypatch):
    # without ``sensitivity.supports`` the SENSITIVITY_CLASSES tuple decides - the one place to extend
    monkeypatch.delattr(sensitivity, "supports", raising=False)
    classes = registry.discover()
    monkeypatch.setattr(registry, "SENSITIVITY_CLASSES", ("fp_mage",))
    assert classes["fp_mage"].supports_sensitivity is True and classes["night_lord"].supports_sensitivity is False
    monkeypatch.setattr(registry, "SENSITIVITY_CLASSES", ("fp_mage", "night_lord"))
    assert classes["night_lord"].supports_sensitivity is True


def test_companion_levels_and_potential_lines_reach_the_engine(client):
    """The web Companions page sends every companion's level (0 = not unlocked) and the boots lines already inside the Summoning Time input."""
    levels = {"Wind Archer": 7, "Blaze Wizard": 10, "Hero": 0}
    body = {**CASE, "which": ["companions", "summon_time"], "companion_levels": levels, "companion_potential_lines_pct": 12}
    r = client.post(URL, json=body)
    assert r.status_code == 200, r.text
    out = r.json()
    rows = {x["name"]: x for x in out["companions"]["rows"]}
    assert rows["Wind Archer"]["level"] == 7 and rows["Wind Archer"]["unlocked"] is True
    assert rows["Hero"]["unlocked"] is False and rows["Hero"]["rank_position"] is None
    direct = sensitivity.run(fp_mage, dict(engine_inputs(CASE), companion_levels=levels, companion_potential_lines_pct=12), which=["companions", "summon_time"])
    _same(direct, out)
    assert out["summon_time"]["b0"] == direct["summon_time"]["b0"]


def test_companion_levels_validation(client):
    for bad, field in (({"companion_levels": []}, "companion_levels"), ({"companion_levels": {"Nobody": 3}}, "companion_levels.Nobody"),
                       ({"companion_levels": {"Hero": 19}}, "companion_levels.Hero"), ({"companion_levels": {"Hero": 2.5}}, "companion_levels.Hero"),
                       ({"companion_potential_lines_pct": -1}, "companion_potential_lines_pct"), ({"companion_potential_lines_pct": "x"}, "companion_potential_lines_pct")):
        r = client.post(URL, json={**CASE, "which": ["companions"], **bad})
        assert r.status_code == 422, bad
        assert field in {e["field"] for e in r.json()["errors"]}


# ---- artifact_lines: the potential lines entered on the Artifacts tab value the equip / removal row ---------------------------------------------
# (``typed_includes_artifacts`` False = the workbooks' convention these cases were written for: typed 60 EXCLUDES the shoes, so equipped means 60 + 40 = 100 and the effect is
# saturated.  With the API default True the typed 40 already contains the shoes: see api/tests/test_typed_includes_artifacts.py)
ARWEN_CASE = {"content_type": "Breakthrough", "companion_choice": "Blaze Wizard", "companion_level": 10, "companion_summon_time_increase_pct": 60,
              "artifacts": [{"key": "arwens_glass_shoes", "star": 5}], "which": ["artifacts"], "artifact_stars": {"arwens_glass_shoes": 5},
              "typed_includes_artifacts": False}
ARWEN_LINES = {"arwens_glass_shoes": {"star": 5, "lines": [{"rarity": "Legendary", "stat": "Damage %"}, {"rarity": "Epic", "stat": "Boss Monster Damage %"}]}}


def _arwen(out):
    return next(r for r in out["artifacts"]["rows"] if r["key"] == "arwens_glass_shoes")


def test_artifact_lines_value_an_equipped_row(client):
    """Reported: Arwen's Glass Shoes equipped (typed 60 + the shoes' 40 is already past the last useful step of Blaze Wizard with Poison Breath's stun) showed 0% although it carries potential lines.  Without lines
    the row stays 0 (the effect is saturated); with them it is the lines' value, computed like the Artifacts tab's own numbers (same engine, same rates)."""
    plain = client.post(URL, json=ARWEN_CASE)
    assert plain.status_code == 200, plain.text
    row0 = _arwen(plain.json())
    assert row0["equipped"] is True and row0["dps_gain"] == 0.0 and row0["pct_gain"] == 100.0 and row0["potential_gain"] == 0.0
    r = client.post(URL, json={**ARWEN_CASE, "artifact_lines": ARWEN_LINES})
    assert r.status_code == 200, r.text
    row = _arwen(r.json())
    assert row["equipped"] is True and row["potential_gain"] > 0 and row["dps_gain"] == pytest.approx(row["potential_gain"], rel=1e-12) and row["pct_gain"] > 100
    # the same number the Artifacts tab shows as "Potential total" (POST .../artifact-potentials)
    pot = client.post("/api/classes/fp_mage/artifact-potentials", json={k: v for k, v in ARWEN_CASE.items() if k not in ("which", "artifact_stars")}
                      | {"potentials": ARWEN_LINES})
    assert pot.status_code == 200, pot.text
    total = next(x for x in pot.json()["rows"] if x["key"] == "arwens_glass_shoes")["total"]
    assert row["potential_gain"] == pytest.approx(total, rel=1e-9)
    # engine parity
    direct = sensitivity.run(fp_mage, dict(engine_inputs({k: v for k, v in ARWEN_CASE.items() if k not in ("which", "artifact_stars")}),
                                           artifact_stars={"arwens_glass_shoes": 5}, artifact_lines=ARWEN_LINES), which=["artifacts"])
    assert _arwen(direct)["dps_gain"] == pytest.approx(row["dps_gain"], rel=1e-12)


def test_artifact_lines_unequipped_row_and_cache_key(client):
    body = {**ARWEN_CASE, "artifacts": [], "companion_summon_time_increase_pct": 10}
    plain = _arwen(client.post(URL, json=body).json())
    with_lines = client.post(URL, json={**body, "artifact_lines": ARWEN_LINES})
    assert with_lines.headers["x-cache"] == "MISS"                 # the lines are part of the cache key
    row = _arwen(with_lines.json())
    assert row["equipped"] is False and plain["potential_gain"] == 0 and row["potential_gain"] > 0
    assert row["dps_gain"] == pytest.approx(plain["dps_gain"] + row["potential_gain"], rel=1e-12)
    assert client.post(URL, json={**body, "artifact_lines": ARWEN_LINES}).headers["x-cache"] == "HIT"


def test_artifact_lines_validation(client):
    for bad, field in (({"artifact_lines": []}, "artifact_lines"), ({"artifact_lines": {"nobody": {"lines": []}}}, "artifact_lines.nobody"),
                       ({"artifact_lines": {"arwens_glass_shoes": {"lines": [{"rarity": "Legendary", "stat": "Bogus %"}]}}}, "artifact_lines.arwens_glass_shoes.lines[0].stat"),
                       ({"artifact_lines": {"arwens_glass_shoes": {"lines": [{"rarity": "Nope", "stat": "Damage %"}]}}}, "artifact_lines.arwens_glass_shoes.lines[0].rarity")):
        r = client.post(URL, json={**ARWEN_CASE, **bad})
        assert r.status_code == 422, bad
        assert field in {e["field"] for e in r.json()["errors"]}, (field, r.json())
