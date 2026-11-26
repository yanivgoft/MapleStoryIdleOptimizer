"""API tests (FastAPI TestClient).  Run from the repo root:  python -m pytest api/tests -q"""
import json
import math
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from api.middleware import RateLimitMiddleware
from api.settings import Settings

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = json.loads((ROOT / "tests" / "golden" / "fp_mage_golden.json").read_text())


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app(Settings(rate_limit_per_minute=0)))


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok" and r.json()["classes"] >= 1
    assert "x-request-id" in r.headers


def test_classes_lists_fp_mage(client):
    ids = [c["id"] for c in client.get("/api/classes").json()["classes"]]
    assert "fp_mage" in ids
    assert ids == sorted(ids)


def test_schema(client):
    s = client.get("/api/classes/fp_mage/schema").json()
    assert s["class_id"] == "fp_mage" and len(s["fields"]) >= 44
    assert {"key", "label", "group", "type", "applicable", "computed"} <= set(s["fields"][0])


def test_defaults_per_content(client):
    d = client.get("/api/classes/fp_mage/defaults", params={"content_type": "PvP"}).json()
    assert d["content_type"] == "PvP" and d["pvp_fight_length"] == 15 and d["chapter_stage"] is None
    assert client.get("/api/classes/fp_mage/defaults").json()["content_type"]
    bad = client.get("/api/classes/fp_mage/defaults", params={"content_type": "Nope"})
    assert bad.status_code == 422 and bad.json()["errors"][0]["field"] == "content_type"


def test_unknown_class_404(client):
    for path in ("/api/classes/nope/schema", "/api/classes/nope/defaults"):
        assert client.get(path).status_code == 404
    assert client.post("/api/classes/nope/compute", json={}).status_code == 404


GOLDEN_IDS = list(GOLDEN)[:6] + [k for k in GOLDEN if "PvP" in k][:1] + [k for k in GOLDEN if "Breakthrough" in k][:2]


@pytest.mark.workbook_golden
@pytest.mark.parametrize("case_id", GOLDEN_IDS)
def test_compute_matches_golden(client, case_id):
    case = GOLDEN[case_id]
    r = client.post("/api/classes/fp_mage/compute", json=case["inputs"])
    assert r.status_code == 200, r.json()
    body = r.json()
    assert math.isclose(body["total_dps"], case["out"]["total_dps"], rel_tol=1e-12), case_id
    assert body["skills"] and "derived" in body and "engine_on" in body


def test_compute_defaults_only_body(client):
    r = client.post("/api/classes/fp_mage/compute", json={"content_type": "World Boss", "flat_attack": 1e6})
    assert r.status_code == 200 and r.json()["total_dps"] > 0


def test_compute_empty_body_uses_defaults(client):
    assert client.post("/api/classes/fp_mage/compute", json={}).status_code == 200


def test_artifacts_accepted(client):
    r = client.post("/api/classes/fp_mage/compute", json={"artifacts": [{"key": "(none)", "star": None}]})
    assert r.status_code == 200
    bad = client.post("/api/classes/fp_mage/compute", json={"artifacts": [{"key": "nonsense", "star": 9}]})
    assert bad.status_code == 422 and bad.json()["errors"][0]["field"] == "artifacts[0].key"


FIVE = ["alliance_badge", "sayrams_necklace", "flaming_lava", "icy_soul_rock", "secret_map"]


def test_five_artifact_slots(client):
    """The game has 5 artifact slots (2026-11-23; the workbooks keep 4 - engine-only composition): 5 equipped compute, a 6th entry is a clean 422."""
    for cid in ("fp_mage", "hero"):
        slots = [{"key": k, "star": 5} for k in FIVE]
        r = client.post(f"/api/classes/{cid}/compute", json={"content_type": "World Boss", "artifacts": slots})
        assert r.status_code == 200, r.text
        body = r.json()
        assert len(body["artifacts"]["equipped"]) == 5 and math.isfinite(body["total_dps"])
        four = client.post(f"/api/classes/{cid}/compute", json={"content_type": "World Boss", "artifacts": slots[:4]}).json()
        assert body["total_dps"] >= four["total_dps"]
        six = client.post(f"/api/classes/{cid}/compute", json={"artifacts": slots + [{"key": "candle", "star": 1}]})
        assert six.status_code == 422 and six.json()["errors"][0] == {"field": "artifacts", "message": "at most 5 slots"}
        sch = client.get(f"/api/classes/{cid}/schema").json()
        assert sch["artifacts"]["max_slots"] == 5


def test_legendary_artifacts_reach_star_7(client):
    """Patch 2026-11-26: Legendary artifacts go up to Awakening Stage 7 (stars 6 and 7), Epic / Unique stay at 5; the schema says each artifact's own limit."""
    sch = client.get("/api/classes/hero/schema").json()["artifacts"]
    limits = {a["key"]: a["max_star"] for a in sch["artifacts"]}
    assert all(limits[a["key"]] == (7 if a["rank"] == "Legendary" else 5) for a in sch["artifacts"]) and 7 in sch["star_options"]
    legendary = next(a["key"] for a in sch["artifacts"] if a["rank"] == "Legendary" and a["effect"] == "live")
    epic = next(a["key"] for a in sch["artifacts"] if a["rank"] == "Epic")
    totals = []
    for star in (5, 6, 7):
        r = client.post("/api/classes/hero/compute", json={"content_type": "World Boss", "artifacts": [{"key": legendary, "star": star}]})
        assert r.status_code == 200, r.text
        totals.append(r.json()["total_dps"])
    assert totals[0] <= totals[1] <= totals[2]      # a higher star never lowers the total
    bad = client.post("/api/classes/hero/compute", json={"content_type": "World Boss", "artifacts": [{"key": epic, "star": 6}]})
    assert bad.status_code == 422 and bad.json()["errors"][0]["field"] == "artifacts[0].star"
    bad = client.post("/api/classes/hero/compute", json={"content_type": "World Boss", "artifacts": [{"key": legendary, "star": 8}]})
    assert bad.status_code == 422


def test_422_field_level(client):
    r = client.post("/api/classes/fp_mage/compute", json={
        "level": 0, "flat_attack": "lots", "crit_rate": -5, "content_type": "World Boss", "bogus": 1, "skill_lvl_all": 1.5,
        "companion_choice": "Nobody", "attack_pct": 1e99})
    assert r.status_code == 422
    errs = {e["field"]: e["message"] for e in r.json()["errors"]}
    assert set(errs) == {"level", "flat_attack", "crit_rate", "bogus", "skill_lvl_all", "companion_choice", "attack_pct"}
    assert "Traceback" not in r.text


def test_chapter_stage_validation(client):
    ok = client.post("/api/classes/fp_mage/compute", json={"content_type": "Breakthrough", "chapter_stage": "30-9"})
    assert ok.status_code == 200
    bad = client.post("/api/classes/fp_mage/compute", json={"content_type": "Breakthrough", "chapter_stage": "x-y"})
    assert bad.status_code == 422 and bad.json()["errors"][0]["field"] == "chapter_stage"


def test_not_applicable_and_computed_fields_ignored(client):
    r = client.post("/api/classes/fp_mage/compute", json={"content_type": "World Boss", "pvp_fight_length": 5, "monster_defense": 1})
    assert r.status_code == 200


def test_body_must_be_object_and_json(client):
    r = client.post("/api/classes/fp_mage/compute", json=[1, 2])
    assert r.status_code == 422 and r.json()["errors"]
    r = client.post("/api/classes/fp_mage/compute", content=b"{not json", headers={"content-type": "application/json"})
    assert r.status_code == 422 and "Traceback" not in r.text


def test_body_size_limit():
    c = TestClient(create_app(Settings(rate_limit_per_minute=0, max_body_bytes=200)))
    r = c.post("/api/classes/fp_mage/compute", json={"content_type": "x" * 500})
    assert r.status_code == 413


def test_rate_limit():
    app = create_app(Settings(rate_limit_per_minute=3))
    # real clock here (the window arithmetic is unit-tested below with a fake clock): 3 allowed, then 429
    c = TestClient(app)
    codes = [c.get("/api/classes").status_code for _ in range(5)]
    assert codes == [200, 200, 200, 429, 429]
    assert c.get("/api/classes").headers["retry-after"]
    assert c.get("/api/health").status_code == 200       # health is exempt


def test_rate_limit_window_unit():
    import asyncio
    t = [0.0]
    sent = []

    async def app(scope, receive, send):
        sent.append("ok")

    async def send(m):
        if m["type"] == "http.response.start":
            sent.append(m["status"])

    mw = RateLimitMiddleware(app, limit=2, window_s=10, clock=lambda: t[0])
    scope = {"type": "http", "path": "/api/x", "method": "GET", "headers": [], "client": ("1.2.3.4", 1)}

    async def go():
        for _ in range(3):
            await mw(scope, None, send)
        t[0] = 11.0
        await mw(scope, None, send)

    asyncio.run(go())
    assert sent == ["ok", "ok", 429, "ok"]


def test_cors_headers():
    c = TestClient(create_app(Settings(rate_limit_per_minute=0, cors_origins=("http://localhost:5173",))))
    r = c.options("/api/classes", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"
    r = c.get("/api/classes", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in r.headers


def test_compute_failure_is_500_without_trace(client, monkeypatch):
    entry = client.app.state.classes["fp_mage"]

    def boom(inputs):
        raise RuntimeError("secret internals")

    monkeypatch.setattr(type(entry), "compute", lambda self, i: boom(i))
    r = client.post("/api/classes/fp_mage/compute", json={})
    assert r.status_code == 500 and "secret" not in r.text and "Traceback" not in r.text
