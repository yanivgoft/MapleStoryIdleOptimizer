"""Engine-native classes (no Excel workbook): the generic case matrix, the snapshot file format and the leaf comparison.

An ENGINE-NATIVE class (``registry.NATIVE``) has ``engine/classes/<id>.py`` + ``engine/data/<id>.py`` + ``engine/sens_specs/<id>.py`` but no workbook, builder, verify
script or workbook golden.  Its regression pin is ONE snapshot file, ``tests/golden/<id>_snapshot.json``, written from the CURRENT engine by
``update_goldens.py --create --class <id>`` (labelled "engine-native snapshot: pins the engine, no independent source" in golden_refresh_log.md) and compared leaf by
leaf by ``test_snapshots.py``.  The independent checks of such a class are elsewhere: the displayed-value test against the user's in-game numbers
(``test_<id>_displayed.py``) and the engine-only invariants / sweeps of ``test_engine_native.py``.

THE CASE MATRIX is generic: it is derived from the class's own schema (field keys, groups, content types) and its data module (``UNLOCK_LEVEL`` + every mastery /
gated chain keyed by character level), so a new class needs no per-class case file:

  M/<content>/<set>/<comp|nocomp>       10 content types x stat sets {default, late, weak} x companion {Blaze Wizard Lv10, none}          (full ``compute`` output)
  CS/<content>/<chapter-stage>          Breakthrough / Chapter Hunt at stages spanning the 28->29 and 38->39 sub-stage-count boundaries     (full)
  L/<content>/<comp>/<level>            level sweep around every unlock / mastery threshold (t-1 and t) + 1 and 200                       (slim output)
  A/<artifact>                          every one of the 36 artifacts alone at its sens-case star, World Boss                              (full)
  AS/<content>/<artifact>               the same in Chapter Hunt (normal monsters)                                                         (slim)
  AN/<n>slots/<content>                 2, 3, 4 and 5 equipped artifacts                                                                    (full)
  S/<name>                              ``engine.sensitivity.run`` (stats / artifacts / companions / summon_time / cdr parts) for a few cases
  C/<name>                              the cube / equipment / artifact-potential pricing derived from a sensitivity run (stat -> value maps of the spec)

``sample_inputs(cid)`` = the late-game Chapter Boss + Blaze Wizard case (what ``web/scripts/gen_fixtures.py`` uses for a class that has no workbook golden).
Plain data in, JSON-able data out; imports only the engine and the shared test helpers.
"""
import importlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

SNAPSHOT_SUFFIX = "_snapshot.json"
VERSION = 1
DEFAULT_RTOL = 1e-9
SAMPLE_CASE_ID = "M/Chapter Boss/late/comp"          # the case ``sample_inputs`` returns (and the web fixtures are generated from)

# A generic late-game character and a generic weak one.  Applied key by key, only where the class has the field AND it applies to the content type; the main-stat fields
# (group "Main stats": flat main stat, main stat %, sub stats ...) are filled by position.
LATE = dict(
    level=140, flat_attack=250000, attack_pct=1800, defense=12000, crit_rate=60, crit_damage=150, attack_speed=20,
    damage=30, damage_amp=20, basic_attack_damage=15, skill_damage=20, def_pen=35, boss_damage=40, normal_damage=25, status_effect_damage=30,
    min_damage=80, max_damage=130, final_damage=12, skill_lvl_1st=3, skill_lvl_2nd=5, skill_lvl_3rd=10, skill_lvl_4th=15, skill_lvl_all=20,
    skill_cooldown_decrease=1, basic_attack_target_increase=2, buff_duration_increase_pct=15, companion_summon_time_increase_pct=0,
    boss_normal_weight_choice="A Little More Normal", max_enemies_hit=999, pvp_fight_length=15, incoming_hit_rate=2)
LATE_MAIN = (5000, 40, 800, 600)                     # flat main stat, main stat %, sub stat, 2nd sub stat
WEAK = dict(
    level=80, flat_attack=30000, attack_pct=200, defense=2000, crit_rate=10, crit_damage=50, attack_speed=5, damage=5, basic_attack_damage=5, skill_damage=5,
    def_pen=5, boss_damage=5, min_damage=60, max_damage=100, skill_lvl_1st=1, skill_cooldown_decrease=0, basic_attack_target_increase=1,
    boss_normal_weight_choice="Equal", max_enemies_hit=3, pvp_fight_length=15, incoming_hit_rate=1)
WEAK_MAIN = (800, 5, 100, 100)
STAT_SETS = ("default", "late", "weak")
COMPANION = ("Blaze Wizard", 10)                     # CLAUDE.md precedent: a stun companion at Lv10
CHAPTER_STAGES = ("28-9", "29-1", "38-14", "39-1", "45-3")
LEVEL_CONTENTS = (("World Boss", False), ("Chapter Hunt", True))      # (content type, companion on): boss with the KO timeline strip / normal monsters with a companion
EXTRA_LEVELS = (1, 2, 5, 10, 20, 30, 200)
CDR_SENS_PARTS = ("stats", "cdr")


def snapshot_path(cid, gdir=None):
    return Path(gdir or HERE) / f"{cid}{SNAPSHOT_SUFFIX}"


# --------------------------------------------------------------------------- the class's own data
def class_module(cid):
    return importlib.import_module(f"engine.classes.{cid}")


def data_module(cid):
    return importlib.import_module(f"engine.data.{cid}")


def thresholds(data):
    """Every character level the class's data module switches something on at: ``UNLOCK_LEVEL`` values, every dict keyed by level (mastery chains, ``gated``), every
    ``level=`` / ``unlock=`` entry and every small numeric tuple that holds a level ((threshold, value) / (base, threshold, value))."""
    out = set()

    def num(x):
        return isinstance(x, (int, float)) and not isinstance(x, bool)

    def walk(x):
        if isinstance(x, dict):
            if x and all(isinstance(k, int) and not isinstance(k, bool) for k in x):
                out.update(k for k in x if 2 <= k <= 200)
            for k, v in x.items():
                if k in ("level", "unlock", "unlock_level") and isinstance(v, int) and not isinstance(v, bool):
                    out.add(v)
                walk(v)
        elif isinstance(x, (list, tuple)):
            if 2 <= len(x) <= 3 and all(num(v) for v in x):
                out.update(v for v in x if isinstance(v, int) and not isinstance(v, bool) and 20 <= v <= 200)
            for v in x:
                walk(v)

    for name in dir(data):
        if name.startswith("_"):
            continue
        v = getattr(data, name)
        if name == "UNLOCK_LEVEL" and isinstance(v, dict):
            out.update(i for i in v.values() if isinstance(i, int) and not isinstance(i, bool))
        elif isinstance(v, (dict, list, tuple)):
            walk(v)
    return sorted(i for i in out if 1 <= i <= 200)


def sweep_levels(data):
    """The levels of the level sweep: every threshold t and t-1, plus ``EXTRA_LEVELS``."""
    ts = thresholds(data)
    return sorted({lv for t in ts for lv in (t - 1, t) if 1 <= lv <= 200} | set(EXTRA_LEVELS))


# --------------------------------------------------------------------------- inputs
def _main_fields(schema):
    return [f["key"] for f in schema["fields"] if f["group"] == "Main stats" and f["type"] in ("float", "int")]


def stat_values(schema, which):
    """{field key: value} of the stat set ``which`` ('late' / 'weak') for this class's schema (main-stat fields by position)."""
    table, main = (LATE, LATE_MAIN) if which == "late" else (WEAK, WEAK_MAIN)
    vals = dict(table)
    for key, v in zip(_main_fields(schema), main):
        vals[key] = v
    return vals


def make_inputs(module, content, stats="late", comp=False, level=None, artifacts=None, **over):
    """Engine inputs: the class's defaults for ``content`` + a stat set (only fields that exist and apply to the content type) + the companion + artifacts."""
    schema = module.schema()
    d = dict(module.defaults(content))
    if stats != "default":
        for k, v in stat_values(schema, stats).items():
            if k not in d or d[k] is None:
                continue                                     # not a field of this class / does not apply to this content type
            f = next(f for f in schema["fields"] if f["key"] == k)
            if f.get("options") and v not in f["options"]:
                continue
            d[k] = v
    if level is not None:
        d["level"] = level
    if comp:
        d["companion_choice"], d["companion_level"] = COMPANION
    if artifacts:
        d["artifacts"] = [dict(a) for a in artifacts]
    d.update(over)
    return d


def sample_inputs(cid):
    """The sample character of the web fixtures of a class that has no workbook golden: late-game stats, Chapter Boss, Blaze Wizard Lv10 (= snapshot case ``M/Chapter Boss/late/comp``)."""
    return make_inputs(class_module(cid), "Chapter Boss", "late", True)


def stars():
    from sens_cases import STARS
    return dict(STARS)


def artifact_keys():
    from engine.data import artifacts as AD
    return list(AD.ARTIFACT_LABELS)


def slot(key, star=None):
    return {"key": key, "star": stars()[key] if star is None else star}


# the equipped sets of the multi-slot cases (artifact ids exist in every class: the 36 artifacts are class independent)
SLOT_SETS = {
    2: ("bottle_of_emotion", "reindeer_spear"),
    3: ("hexagon_necklace", "horn_flute", "candle"),
    4: ("book_of_ancient", "athena_gloves", "ring_of_cycles", "bottle_of_emotion"),
    5: ("arwens_glass_shoes", "charm_of_the_undead", "alliance_badge", "secret_map", "shamaness_marble"),
}


# --------------------------------------------------------------------------- the case matrix
def slim(result):
    """The part of a ``compute`` result kept for the level-sweep / single-artifact cases: totals, every skill's DPS, the companion's DPS, the artifact buckets."""
    comp = result.get("companion")
    return dict(
        total_dps=result["total_dps"], boss_dps=result["boss_dps"], normal_dps=result["normal_dps"], player_dps=result["player_dps"],
        skills=[dict(key=s["key"], dps=s["dps"], boss_dps=s["boss_dps"], normal_dps=s["normal_dps"]) for s in result["skills"]],
        companion=None if not comp else dict(dps=comp["dps"], boss_dps=comp["boss_dps"], normal_dps=comp["normal_dps"]),
        buckets=result["artifacts"]["buckets"] if result.get("artifacts") else None)


def compute_cases(cid):
    """[(case id, inputs, 'full' | 'slim')] of every ``compute`` case of the class."""
    m = class_module(cid)
    schema = m.schema()
    cases = []
    for content in schema["content_types"]:
        for st in STAT_SETS:
            for comp in (False, True):
                cases.append((f"M/{content}/{st}/{'comp' if comp else 'nocomp'}", make_inputs(m, content, st, comp), "full"))
    for content in ("Breakthrough", "Chapter Hunt"):
        if content in schema["content_types"]:
            for cs in CHAPTER_STAGES:
                cases.append((f"CS/{content}/{cs}", make_inputs(m, content, "late", False, chapter_stage=cs), "full"))
    for content, comp in LEVEL_CONTENTS:
        for lv in sweep_levels(data_module(cid)):
            cases.append((f"L/{content}/{'comp' if comp else 'nocomp'}/{lv:03d}", make_inputs(m, content, "late", comp, level=lv), "slim"))
    for key in artifact_keys():
        cases.append((f"A/{key}", make_inputs(m, "World Boss", "late", True, artifacts=[slot(key)]), "full"))
        cases.append((f"AS/Chapter Hunt/{key}", make_inputs(m, "Chapter Hunt", "late", True, artifacts=[slot(key)]), "slim"))
    for n, keys in SLOT_SETS.items():
        for content in ("World Boss", "Chapter Hunt"):
            cases.append((f"AN/{n}slots/{content}", make_inputs(m, content, "late", True, artifacts=[slot(k) for k in keys]), "full"))
    return cases


def sens_inputs(cid, content, stats, comp, arts):
    d = make_inputs(class_module(cid), content, stats, comp, artifacts=[slot(k) for k in arts])
    d["artifact_stars"] = stars()
    return d


def sens_cases(cid):
    """[(case id, inputs, which)] of the sensitivity runs (``which`` None = every part)."""
    return [
        ("S/WB-late-comp-all", sens_inputs(cid, "World Boss", "late", True, ("bottle_of_emotion", "reindeer_spear")), None),
        ("S/CH-late-nocomp", sens_inputs(cid, "Chapter Hunt", "late", False, ("hexagon_necklace", "secret_map")), list(CDR_SENS_PARTS) + ["artifacts"]),
        ("S/BT-weak-comp", sens_inputs(cid, "Breakthrough", "weak", True, ()), list(CDR_SENS_PARTS)),
        ("S/CB-default", sens_inputs(cid, "Chapter Boss", "default", False, ()), list(CDR_SENS_PARTS)),
    ]


CUBES_GEAR = [
    {"slot": "head", "potential_type": "Potential", "rarity": "epic", "pity": 12,
     "lines": [{"stat": "Damage %", "value": 12}, {"stat": "Critical Rate %", "value": 3}, {"stat": "Skill Cooldown Decrease (seconds)", "value": 0.5}]},
    {"slot": "boots", "potential_type": "Bonus Potential", "rarity": "unique", "pity": 0, "lines": [{"stat": "Companion Summoning Time Increase %", "value": 8}]},
]
EQUIP_CASE = {"current": {"attack": 1500, "lines": [("Damage %", 14), ("Critical Rate %", 3)]},
              "new": {"attack": 2200, "lines": [("Final Damage %", 6), ("Min Damage %", 15), ("Damage %", 5)]}}
POTENTIALS_STATE = {"book_of_ancient": {"star": 5, "lines": [("Legendary", "Damage %"), ("Epic", "Critical Rate %")]},
                    "pigs_ribbon": {"star": 3, "lines": [("Unique", "Defense Penetration %")]}}


def cube_cases(cid):
    """[(case id, inputs)]: the pricing the cube / equipment / artifact-potential tabs derive from a sensitivity run."""
    return [("C/WB-late-comp", sens_inputs(cid, "World Boss", "late", True, ("bottle_of_emotion",))),
            ("C/CH-late-nocomp", sens_inputs(cid, "Chapter Hunt", "late", False, ()))]


def run_cubes(cid, inputs):
    """Pricing dict + the equipment-compare and artifact-potential results of ``inputs`` (the same calls ``api/features.py`` makes, without the cache layer)."""
    from engine import cubes, equipment, potentials, sensitivity
    from engine import sens_specs
    m = class_module(cid)
    spec = sens_specs.get(cid)
    maps = spec.stat_to_key or {}
    sens = sensitivity.run(m, dict(inputs), which=["stats", "cdr", "summon_time"])
    pricing = cubes.pricing_from_sensitivity(sens, dict(inputs), m, stat_to_key=maps.get("cubes"), sub_stat_pct_lines=maps.get("cubes_sub_stat_pct"))
    rows = cubes.recommend(CUBES_GEAR, pricing, sort=False)
    rates = cubes.sweep_rates(sens)
    model = m.model(dict(inputs))
    crit = float(getattr(model, "crit_rate_total", model.crit_rate))
    ring, book = "ring_of_cycles" in model.eq, "book_of_ancient" in model.eq
    equip = equipment.compare(EQUIP_CASE["current"], EQUIP_CASE["new"], rates, sens["baseline_total"], crit, ring, book, stat_to_key=maps.get("equipment"))
    state = {k: dict(v, lines=[tuple(x) for x in v["lines"]]) for k, v in POTENTIALS_STATE.items()}
    slots = [a["key"] for a in inputs.get("artifacts") or []]
    pot = potentials.potential_table(state, rates, sens["baseline_total"], slots, stat_to_key=maps.get("potentials"))
    return dict(baseline_dps=pricing.baseline_dps, dps_per_unit=pricing.dps_per_unit, cdr_current=pricing.cdr_current, cdr_points=pricing.cdr_points,
                rows=rows, equipment=equip, potentials=pot)


# --------------------------------------------------------------------------- running a case
def plain(v):
    """JSON round trip normalisation (tuples -> lists, int keys -> str, subclasses -> builtins); NaN / inf are kept as the json module writes them."""
    return json.loads(json.dumps(v))


def run_case(cid, kind, inputs, which=None, shape="full"):
    m = class_module(cid)
    if kind == "compute":
        r = m.compute(dict(inputs))
        return plain(r if shape == "full" else slim(r))
    if kind == "sens":
        from engine import sensitivity
        return plain(sensitivity.run(m, dict(inputs), which=which))
    if kind == "cubes":
        return plain(run_cubes(cid, dict(inputs)))
    raise ValueError(kind)


def matrix(cid):
    """{case id: (kind, inputs, extra)} of the whole case matrix, in file order (nothing is computed here): ``extra`` = the output shape ('full' / 'slim') of a compute case,
    the ``which`` parts of a sensitivity case, None for a cube case."""
    cases = {}
    for case_id, inputs, shape in compute_cases(cid):
        cases[case_id] = ("compute", inputs, shape)
    for case_id, inputs, which in sens_cases(cid):
        cases[case_id] = ("sens", inputs, which)
    for case_id, inputs in cube_cases(cid):
        cases[case_id] = ("cubes", inputs, None)
    return cases


def build_case(cid, kind, inputs, extra):
    """One stored case (``{"kind", "inputs", "out", ...}``) from the CURRENT engine."""
    if kind == "compute":
        return dict(kind=kind, shape=extra, inputs=plain(inputs), out=run_case(cid, kind, inputs, shape=extra))
    if kind == "sens":
        return dict(kind=kind, which=extra, inputs=plain(inputs), out=run_case(cid, kind, inputs, extra))
    return dict(kind=kind, inputs=plain(inputs), out=run_case(cid, kind, inputs))


def generate(cid, only=None, ids=None):
    """The whole snapshot of the class from the CURRENT engine: {"meta": ..., "cases": {id: {"kind", "inputs", ("which",) "out"}}} (``only``: substring filter of the case
    ids; ``ids``: only these case ids)."""
    cases = {cid_: build_case(cid, *spec) for cid_, spec in matrix(cid).items() if (not only or only in cid_) and (ids is None or cid_ in ids)}
    return dict(meta=meta(cid, len(cases)), cases=cases)


def meta(cid, n_cases):
    return dict(version=VERSION, class_id=cid, source="engine-native snapshot: pins the engine, no independent source", n_cases=n_cases)


def rerun(cid, case):
    """The engine output of a STORED case (its own inputs, so the comparison does not depend on the generator)."""
    return run_case(cid, case["kind"], case["inputs"], case.get("which"), case.get("shape", "full"))


# --------------------------------------------------------------------------- file format + leaf comparison
def dumps(data):
    return json.dumps(data)


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _close(a, b, rtol):
    if a == b:
        return True
    scale = max(abs(a), abs(b))
    return abs(a - b) <= rtol * scale + 1e-12


def diff_leaves(old, new, rtol=DEFAULT_RTOL, path=()):
    """[(path, old, new)] of every difference between two JSON trees: a number outside ``rtol`` (relative, 1e-12 absolute floor), a differing string / bool / None, a key or
    list item present on one side only (the missing side is ``MISSING``), a different node type."""
    out = []
    if isinstance(old, dict) and isinstance(new, dict):
        for k in old:
            out += diff_leaves(old[k], new[k], rtol, path + (k,)) if k in new else [(path + (k,), old[k], MISSING)]
        out += [(path + (k,), MISSING, new[k]) for k in new if k not in old]
    elif isinstance(old, list) and isinstance(new, list):
        for i in range(max(len(old), len(new))):
            if i >= len(old):
                out.append((path + (i,), MISSING, new[i]))
            elif i >= len(new):
                out.append((path + (i,), old[i], MISSING))
            else:
                out += diff_leaves(old[i], new[i], rtol, path + (i,))
    elif isinstance(old, bool) or isinstance(new, bool) or old is None or new is None or isinstance(old, str) or isinstance(new, str):
        if type(old) is not type(new) or old != new:
            out.append((path, old, new))
    elif isinstance(old, (int, float)) and isinstance(new, (int, float)):
        if not _close(old, new, rtol):
            out.append((path, old, new))
    elif old != new:
        out.append((path, old, new))
    return out


def bit_differences(old, new):
    """Number of numeric leaves that are not bit-equal (within-tolerance drift; compared with ==)."""
    n = 0
    if isinstance(old, dict) and isinstance(new, dict):
        for k in old:
            n += bit_differences(old[k], new[k]) if k in new else 0
    elif isinstance(old, list) and isinstance(new, list):
        for a, b in zip(old, new):
            n += bit_differences(a, b)
    elif isinstance(old, (int, float)) and isinstance(new, (int, float)) and not isinstance(old, bool) and not isinstance(new, bool):
        n += old != new
    return n


def count_leaves(node):
    if isinstance(node, dict):
        return sum(count_leaves(v) for v in node.values())
    if isinstance(node, list):
        return sum(count_leaves(v) for v in node)
    return 0 if node is None else 1


class _Missing:
    def __repr__(self):
        return "<missing>"


MISSING = _Missing()


def fmt_path(path):
    return "/".join(str(p) for p in path)
