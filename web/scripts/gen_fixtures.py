#!/usr/bin/env python3
"""Regenerate web/src/fixtures/* (mock mode + the vitest fixtures) from the real API, for every class.

Run from the repository root with the API's virtualenv (needs fastapi + httpx):

    .venv/bin/python web/scripts/gen_fixtures.py              # everything
    .venv/bin/python web/scripts/gen_fixtures.py --artifacts  # only the Artifacts tab fixtures + web/src/lib/artifact_values.json + artifact_potential_tables.json

Per class ``<id>``: ``<id>.schema.json`` (GET /schema), ``<id>.defaults.json`` (GET /defaults for each content type), ``<id>.sample_inputs.json``
(the golden case ``A140/Chapter Boss/blaze``: level 140, Blaze Wizard companion Lv 10, real-looking stats) and ``<id>.result.json`` (POST /compute of
exactly those inputs, so the fixture is what the API answers).  Plus ``classes.json`` (GET /api/classes).

For every class whose ``status.stat_values`` is true (today 7 classes: FP-Mage, Dark Knight, Hero, Ice/Lightning Mage, Bishop, Buccaneer, Marksman): ``<id>.sensitivity.json`` (POST /sensitivity of the same sample inputs, all parts)
and ``<id>.sensitivity_meta.json`` (GET /sensitivity/meta).

    .venv/bin/python web/scripts/gen_fixtures.py --sensitivity-only    # only the sensitivity fixtures (+ the stat_values flags in classes.json)

For the same classes the cube tabs' fixtures: ``<id>.cubes_meta.json`` (GET /cubes/meta), ``<id>.cubes_case.json`` ({gear, result}: POST /cubes, all 30 rows, for a sample
gear), ``<id>.equipment_case.json`` ({request, result}: POST /equipment-compare) and ``<id>.potentials_case.json`` ({request, result, rate_by_stat}: POST /artifact-potentials;
rate_by_stat = DPS per unit of every artifact-potential stat, so mock mode can recompute edits).  The full cube call takes ~6 s without numpy.

    .venv/bin/python web/scripts/gen_fixtures.py --cubes-only          # only those four files

The sample inputs come from the class's workbook golden (``tests/golden/<id>_golden.json``, case ``A140/Chapter Boss/blaze``) when it has one.  An ENGINE-NATIVE class (no workbook,
no golden; ``tests/golden/registry.py`` NATIVE) gets the generic sample character of ``tests/golden/snapshot_common.py::sample_inputs`` instead: its schema defaults + a
late-game stat set (level 140) in Chapter Boss with a Blaze Wizard Lv10 companion - the same case as ``M/Chapter Boss/late/comp`` of the class's snapshot.

Options (any order):  ``--out DIR`` writes the fixtures to DIR (and the two web/src/lib JSON files to DIR/lib) instead of web/src/fixtures (a dry run into a temp directory);
``--class ID`` (repeatable) restricts the per-class files to those classes (classes.json always lists every class the API serves).
PUBLISH GATE: only PUBLISHED classes get fixtures (a class module that exports ``PUBLISHED = False`` is hidden from the API, see engine/__init__.py); ``--include-unpublished`` also
generates the unpublished ones (a local preview - never commit those fixtures before the class is published).  Without the flag the script ignores ``MSI_INCLUDE_UNPUBLISHED`` in the environment.
"""
import json
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
logging.disable(logging.CRITICAL)

from fastapi.testclient import TestClient  # noqa: E402

from api.main import create_app  # noqa: E402
from api.settings import Settings  # noqa: E402

OUT = ROOT / "web" / "src" / "fixtures"
LIB = ROOT / "web" / "src" / "lib"
CASE = "A140/Chapter Boss/blaze"
ONLY = None                              # --class: the class ids whose per-class files are written (None = all)


def sample_inputs(cid):
    """The sample character of a class: its workbook golden's case ``CASE`` when the class has a golden, else the generic one of ``snapshot_common`` (engine-native classes)."""
    golden = ROOT / "tests" / "golden" / f"{cid}_golden.json"
    if golden.exists():
        return json.loads(golden.read_text())[CASE]["inputs"]
    sys.path.insert(0, str(ROOT / "tests" / "golden"))
    import snapshot_common
    return snapshot_common.sample_inputs(cid)


def selected(cid):
    return ONLY is None or cid in ONLY


def dump(name, obj):
    (OUT / name).write_text(json.dumps(obj, indent=1) + "\n")


# Artifacts tab fixtures: one compute result per artifacts-modelled class with these 4 slots equipped (a live Attack% artifact, a companion one,
# a baked-into-Inputs one, a no-DPS-effect one) + the engine's star-value table the UI turns into effect text (web/src/lib/artifact_values.json) + the class-independent
# artifact potential-line tables (web/src/lib/artifact_potential_tables.json).
ARTIFACT_CASE = [{"key": "alliance_badge", "star": 4}, {"key": "arwens_glass_shoes", "star": 2},
                 {"key": "book_of_ancient", "star": 5}, {"key": "pigs_ribbon", "star": "Not Unlocked"}]


def potential_tables():
    """web/src/lib/artifact_potential_tables.json: the artifact potential-line tables (class independent), so the Artifacts table's rarity / stat dropdowns work
    before GET /cubes/meta has answered and for the classes without stat values (the meta's `artifact_potentials` is the same data; a vitest test compares them)."""
    from engine import potentials

    tables = {"rarities": list(potentials.RARITIES), "stats": list(potentials.POTENTIAL_STATS), "values": {s: dict(v) for s, v in potentials.VALUES.items()},
              "line_min_star": list(potentials.LINE_MIN_STAR), "default_rarity": potentials.DEFAULT_RARITY, "none_stat": potentials.NONE_STAT}
    (LIB / "artifact_potential_tables.json").write_text(json.dumps(tables, indent=1) + "\n")


def artifacts_fixtures(client):
    from engine.data import artifacts as AD

    (LIB / "artifact_values.json").write_text(json.dumps(AD.ARTIFACT_STAR_VALUES, indent=1) + "\n")
    potential_tables()
    for c in json.loads((OUT / "classes.json").read_text())["classes"]:       # the fixture list (what mock mode shows), not the live API
        if not c.get("artifacts_modelled") or not selected(c["id"]):
            continue
        cid = c["id"]
        inputs = json.loads((OUT / f"{cid}.sample_inputs.json").read_text())
        r = client.post(f"/api/classes/{cid}/compute", json={**inputs, "artifacts": ARTIFACT_CASE})
        assert r.status_code == 200, (cid, r.text)
        dump(f"{cid}.artifacts_case.json", {"artifacts": ARTIFACT_CASE, "result": r.json()})
        print(cid, "artifacts case ok", round(r.json()["total_dps"]))


def dump_sensitivity(client, cid):
    r = client.post(f"/api/classes/{cid}/sensitivity", json=sample_inputs(cid))
    assert r.status_code == 200, (cid, r.text)
    dump(f"{cid}.sensitivity.json", r.json())
    m = client.get(f"/api/classes/{cid}/sensitivity/meta")
    assert m.status_code == 200, (cid, m.text)
    dump(f"{cid}.sensitivity_meta.json", m.json())
    print(cid, "sensitivity ok", len(r.json()["stats"]["rows"]), "stats")


CUBES_GEAR = [
    {"slot": "head", "potential_type": "Potential", "rarity": "epic", "pity": 12,
     "lines": [{"stat": "Damage %", "value": 12}, {"stat": "Critical Rate %", "value": 3}, {"stat": "Skill Cooldown Decrease (seconds)", "value": 0.5}]},
    {"slot": "boots", "potential_type": "Bonus Potential", "rarity": "unique", "pity": 0, "lines": [{"stat": "Companion Summoning Time Increase %", "value": 8}]},
    {"slot": "ring", "potential_type": "Potential", "rarity": "legendary", "pity": 100,
     "lines": [{"stat": "Final Damage %", "value": 6}, {"stat": "Damage %", "value": 9}]},
    {"slot": "gloves", "potential_type": "Bonus Potential", "rarity": "rare", "pity": 40, "lines": [{"stat": "Critical Damage %", "value": 5}]},
]
EQUIP_CASE = {"current": {"attack": 1500, "lines": [{"stat": "Damage %", "value": 14}, {"stat": "Critical Rate %", "value": 3}]},
              "new": {"attack": 2200, "lines": [{"stat": "Final Damage %", "value": 6}, {"stat": "Min Damage %", "value": 15}, {"stat": "Damage %", "value": 5}]}}
POTENTIALS_CASE = {"potentials": {"book_of_ancient": {"star": 5, "lines": [{"rarity": "Legendary", "stat": "Damage %"}, {"rarity": "Epic", "stat": "Critical Rate %"}]},
                                  "pigs_ribbon": {"star": 3, "lines": [{"rarity": "Unique", "stat": "Defense Penetration %"}]}}}


def dump_cubes(client, cid):
    from engine import cubes, potentials, sensitivity
    inputs = sample_inputs(cid)
    meta = client.get(f"/api/classes/{cid}/cubes/meta")
    assert meta.status_code == 200, (cid, meta.text)
    dump(f"{cid}.cubes_meta.json", meta.json())
    r = client.post(f"/api/classes/{cid}/cubes", json={**inputs, "gear": CUBES_GEAR})
    assert r.status_code == 200, (cid, r.text)
    dump(f"{cid}.cubes_case.json", {"gear": CUBES_GEAR, "result": r.json()})
    e = client.post(f"/api/classes/{cid}/equipment-compare", json={**inputs, **EQUIP_CASE})
    assert e.status_code == 200, (cid, e.text)
    dump(f"{cid}.equipment_case.json", {"request": EQUIP_CASE, "result": e.json()})
    p = client.post(f"/api/classes/{cid}/artifact-potentials", json={**inputs, **POTENTIALS_CASE})
    assert p.status_code == 200, (cid, p.text)
    entry = client.app.state.classes[cid]
    from api.validation import validate_inputs
    clean, _ = validate_inputs(entry.schema, entry.defaults, inputs)
    rates = cubes.sweep_rates(sensitivity.run(entry.module, clean, which=["stats"]))
    by_stat = {stat: float(rates.get(key, 0.0)) for stat, key in potentials.STAT_TO_KEY.items() if key is not None}
    dump(f"{cid}.potentials_case.json", {"request": POTENTIALS_CASE, "result": p.json(), "rate_by_stat": by_stat})
    print(cid, "cubes ok", len(r.json()["rows"]), "rows, equipment delta", round(e.json()["delta_pct"], 3), "%")


def main():
    global OUT, LIB, ONLY
    args = sys.argv[1:]
    if "--out" in args:
        OUT = Path(args[args.index("--out") + 1]).resolve()
        LIB = OUT / "lib"
        LIB.mkdir(parents=True, exist_ok=True)
    ONLY = {args[i + 1] for i, a in enumerate(args) if a == "--class"} or None
    if "--include-unpublished" in args:      # (before create_app: the registry reads the variable when it discovers the classes)
        os.environ["MSI_INCLUDE_UNPUBLISHED"] = "1"
    else:
        os.environ.pop("MSI_INCLUDE_UNPUBLISHED", None)
    client = TestClient(create_app(Settings(rate_limit_per_minute=0, rate_limit_sens_per_minute=0, rate_limit_cubes_per_minute=0, rate_limit_compare_per_minute=0)))
    OUT.mkdir(parents=True, exist_ok=True)
    if "--sensitivity-only" in sys.argv:    # keep every other fixture; refresh only the stat_values flags and the sensitivity dumps
        live = client.get("/api/classes").json()["classes"]
        saved = json.loads((OUT / "classes.json").read_text())
        flags = {c["id"]: c["status"]["stat_values"] for c in live}
        for c in saved["classes"]:
            c.setdefault("status", {})["stat_values"] = flags.get(c["id"], False)
        dump("classes.json", saved)
        for cid, on in flags.items():
            if on and selected(cid):
                dump_sensitivity(client, cid)
        return
    if "--cubes-only" in sys.argv:       # only the cube tabs' fixtures of the classes with stat values
        for c in client.get("/api/classes").json()["classes"]:
            if c["status"]["stat_values"] and selected(c["id"]):
                dump_cubes(client, c["id"])
        return
    if "--artifacts" in sys.argv:        # only the Artifacts tab fixtures (needs the class fixtures already generated)
        artifacts_fixtures(client)
        return
    classes = client.get("/api/classes").json()
    dump("classes.json", classes)
    for c in classes["classes"]:
        cid = c["id"]
        if not selected(cid):
            continue
        schema = client.get(f"/api/classes/{cid}/schema").json()
        dump(f"{cid}.schema.json", schema)
        dump(f"{cid}.defaults.json", {ct: client.get(f"/api/classes/{cid}/defaults", params={"content_type": ct}).json()
                                      for ct in schema["content_types"]})
        inputs = sample_inputs(cid)
        dump(f"{cid}.sample_inputs.json", inputs)
        r = client.post(f"/api/classes/{cid}/compute", json=inputs)
        assert r.status_code == 200, (cid, r.text)
        dump(f"{cid}.result.json", r.json())
        print(cid, "ok", round(r.json()["total_dps"]))
        if c["status"]["stat_values"]:
            dump_sensitivity(client, cid)
            dump_cubes(client, cid)
    artifacts_fixtures(client)


if __name__ == "__main__":
    main()
