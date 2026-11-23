"""The ONE list of classes the golden tests know about: which engine module, which golden files, which sensitivity spec / extras module.

Everything that has to enumerate the per-class checks reads this file: ``tests/run_all.py`` (jobs), ``test_artifacts.py`` / ``test_sensitivity.py`` (pytest
parametrisation and ``--class``), ``sens_test_common.py`` and the CI workflows (through run_all).  A new class = one ``Entry`` here (+ its golden files, its
``test_<id>.py`` class golden and ``sens_extras/<id>.py``).

Per class, three checks (the "kinds"):
  class         ``test_<id>.py``                          engine == the verify script's frozen numbers, bit-exact        (``<id>_golden.json``)
  artifacts     ``test_artifacts.py --class <id>``        engine with artifacts equipped == the workbook, rel 1e-9         (``<id>_artifacts_golden.json``)
  sensitivity   ``test_sensitivity.py --class <id>``      engine.sensitivity == the workbook's Sensitivity sheet + engine-only checks (``<id>_sensitivity_golden.json``)

ENGINE-NATIVE classes (``NATIVE``; no workbook, builder, verify script or workbook golden - the Cygnus classes): discovered, not listed.  Every
``engine/classes/<id>.py`` that is not one of ``CLASSES`` is engine-native (the API serves exactly these modules too, so no served class can escape the tests).  Their
jobs are two generic scripts plus any ``test_<id>_*.py`` of that class:
  snapshot      ``test_snapshots.py --class <id>``      engine == ``<id>_snapshot.json`` (a generic case matrix; created by ``update_goldens.py --create``)
  engine        ``test_engine_native.py --class <id>``  engine-only invariants (toggle direction, Final Damage +1%, hooks, API shape) + content sweep + level sweep
``MSI_NATIVE_CLASSES=a,b`` (environment) additionally treats those ids as engine-native: a test hook that lets a workbook class (e.g. hero) stand in for one.

``python3 tests/golden/registry.py`` prints the table and checks that every file named here exists.
"""
import importlib
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

KINDS = ("class", "artifacts", "sensitivity")

# The parametrised scripts (``--class <id>``)
PARAMETRISED = ("test_artifacts.py", "test_sensitivity.py")
NATIVE_PARAMETRISED = ("test_snapshots.py", "test_engine_native.py")      # the same for the engine-native classes


@dataclass(frozen=True)
class Entry:
    id: str
    name: str                       # display name (also the builder's class name in the workbook file name)
    sens_spec: object               # id of the engine/sens_specs spec (None: FP-Mage has its own, non-spec sensitivity engine)
    artifacts: dict = field(default_factory=dict)       # ArtifactsTest options (data only; callables are in artifacts_extras.py): boss_col, normal_col, summary_rows, extras
    prefix: str = ""                # prefix of the generation-time tooling (cases / reference / make_golden ...): "" for FP-Mage (cases.py, run_reference.py ...)
    engine_native: bool = False     # no workbook / builder / verify script / workbook goldens: pinned by a snapshot + engine-only checks (see NATIVE below)

    # --- engine
    @property
    def engine_module(self):
        return f"engine.classes.{self.id}"

    def engine(self):
        return importlib.import_module(self.engine_module)

    # --- golden files
    @property
    def class_golden(self):
        return f"{self.id}_golden.json"

    @property
    def artifacts_golden(self):
        return f"{self.id}_artifacts_golden.json"

    @property
    def sens_golden(self):
        return f"{self.id}_sensitivity_golden.json"

    @property
    def sens_golden_path(self):
        return HERE / self.sens_golden

    @property
    def artifacts_golden_path(self):
        return HERE / self.artifacts_golden

    # --- scripts / modules
    @property
    def class_script(self):
        return f"test_{self.id}.py"

    @property
    def sens_extras(self):
        return f"sens_extras.{self.id}"

    def sens_extras_module(self):
        return importlib.import_module(self.sens_extras)

    @property
    def snapshot(self):
        return f"{self.id}_snapshot.json"

    @property
    def snapshot_path(self):
        return HERE / self.snapshot

    def extra_scripts(self):
        """``test_<id>_*.py`` of an engine-native class (e.g. ``test_dawn_warrior_displayed.py``): ``run_all.py`` runs each once, in the global group of a full run and under
        ``--class <id>``; never mistaken for a per-class golden script (an engine-native class has no ``test_<id>.py``)."""
        return sorted(p.name for p in HERE.glob(f"test_{self.id}_*.py"))

    def jobs(self):
        """[(kind, argv relative to tests/golden)] - what run_all.py runs for this class."""
        if self.engine_native:
            return [("snapshot", ["test_snapshots.py", "--class", self.id]), ("engine", ["test_engine_native.py", "--class", self.id])]
        return [("class", [self.class_script]), ("artifacts", ["test_artifacts.py", "--class", self.id]),
                ("sensitivity", ["test_sensitivity.py", "--class", self.id])]

    # --- generation-time tooling (kept for regenerating goldens; not part of a regression run)
    def tooling(self):
        p = self.prefix
        if p:
            return {"cases": f"{self.id}_cases.py", "real_inputs": f"{self.id}_real_inputs.json", "sens_cases": f"{self.id}_sens_cases.py",
                    "artifact_cases": f"{self.id}_artifact_cases.py", "artifact_reference": f"{self.id}_artifact_reference.py",
                    "run_reference": f"run_reference_{self.id}.py", "make_golden": f"make_golden_{self.id}.py", "check_fake": f"check_{self.id}_fake.py"}
        return {"cases": "cases.py", "sens_cases": "sens_cases.py", "artifact_cases": "artifact_cases.py", "artifact_reference": "artifact_reference.py",
                "run_reference": "run_reference.py", "make_golden": "make_golden.py", "sens_reference": "sens_reference.py"}


def _e(cid, name, sens_spec=True, prefixed_tooling=True, **artifacts):
    return Entry(cid, name, cid if sens_spec else None, artifacts, cid if prefixed_tooling else "")


def _engine_class_file(cid):
    return REPO / "engine" / "classes" / f"{cid}.py"


def native_entry(cid, name=None):
    """The Entry of an engine-native class (``name`` default: the module's ``CLASS_NAME``, read from its source without importing it)."""
    if name is None:
        m = re.search(r'^CLASS_NAME\s*=\s*["\']([^"\']+)["\']', _engine_class_file(cid).read_text(encoding="utf-8"), re.M) if _engine_class_file(cid).exists() else None
        name = m.group(1) if m else cid.replace("_", " ").title()
    return Entry(cid, name, cid, {}, "", engine_native=True)


# Order = the order run_all.py / the pytest ids list the classes.
# artifacts options: boss_col / normal_col = the Calc columns of the boss-only / normal-only DPS (default T / V); summary = the Summary values compared
# (default the base set); summary_rows = {label: (Summary row, engine ``derived`` key)} of further Summary rows (builder constants R_*); extras = key of
# ``artifacts_extras.CONFIG`` (callables: extra Summary checks, FP-Mage's second golden file).
CLASSES = {e.id: e for e in [
    _e("fp_mage", "FP-Mage", sens_spec=False, prefixed_tooling=False, boss_col="S", normal_col="U", extras="fp_mage"),
    _e("hero", "Hero"),
    _e("ice_lightning_mage", "Ice/Lightning Mage", boss_col="S", normal_col="U"),
    # Paladin's Combat Orders uptime feeds every skill-level factor
    _e("paladin", "Paladin", summary_rows={"co_uptime": (26, "combat_orders_uptime"), "monster_dmg_bonus": (15, "monster_dmg_bonus"),
                                           "baps": (19, "basic_attacks_per_second"), "baps_avg": (28, "basic_attacks_per_second_avg"),
                                           "castrate_avg": (27, "cast_rate_avg")}),
    _e("bowmaster", "Bowmaster"),
    _e("bishop", "Bishop", boss_col="S", normal_col="U"),
    # Dark Knight's Lord of Darkness bonuses sit under the artifact crit sources, the Monster Damage-Taken bucket carries Peach Tree / Silver Pendant
    _e("dark_knight", "Dark Knight", summary_rows={"crit_rate_bonus": (14, "crit_rate_bonus"), "monster_dmg_bonus": (15, "monster_dmg_bonus"),
                                                   "baps": (19, "basic_attacks_per_second"), "crit_damage_bonus": (20, "crit_damage_bonus")}),
    _e("marksman", "Marksman", summary_rows={"monster_dmg_bonus": (15, "monster_dmg_bonus"), "as_bonus": (16, "as_bonus"),
                                             "baps": (19, "basic_attacks_per_second"), "mortal_blow": (21, "mortal_blow_bonus")}, extras="marksman"),
    _e("buccaneer", "Buccaneer"),
    _e("corsair", "Corsair"),
    # Night Lord: Critical Throw / Dark Sight's Crit Rate and Frailty Curse's Critical-Damage-Taken mastery are the live crit bonuses; Peach Tree / Silver Pendant are NOT in
    # Summary's Monster Damage-Taken row (they are their own bucket AGG_ENEMY_DMG_TAKEN)
    _e("night_lord", "Night Lord", summary_rows={"crit_rate_bonus": (14, "crit_rate_bonus"), "monster_dmg_bonus": (15, "monster_dmg_bonus"),
                                                 "baps": (22, "basic_attacks_per_second"), "crit_damage_bonus": (24, "crit_damage_bonus")}),
    _e("shadower", "Shadower"),
]}


def discover_native():
    """``{id: Entry}`` of the engine-native classes: every ``engine/classes/<id>.py`` (not ``_*``) that is not a workbook class, in alphabetical order, plus the ids of the
    ``MSI_NATIVE_CLASSES`` test hook."""
    classes_dir = REPO / "engine" / "classes"
    ids = sorted(p.stem for p in classes_dir.glob("*.py") if not p.stem.startswith("_") and p.stem not in CLASSES)
    for cid in (x.strip() for x in os.environ.get("MSI_NATIVE_CLASSES", "").split(",")):
        if cid and cid not in ids:
            ids.append(cid)
    return {cid: native_entry(cid) for cid in ids}


NATIVE = discover_native()
ALL = {**CLASSES, **NATIVE}            # every class the golden jobs know (a MSI_NATIVE_CLASSES stand-in replaces its workbook entry)


def _per_class_scripts():
    """Scripts that belong to ONE class (not global): the workbook classes' ``test_<id>.py``, the parametrised ones, the engine-native generic ones and every engine-native
    class's own ``test_<id>_*.py``."""
    names = {e.class_script for e in CLASSES.values()} | set(PARAMETRISED) | set(NATIVE_PARAMETRISED)
    return names


def global_scripts():
    """Every ``test_*.py`` that is not per class (test_cubes / test_equipment / test_potentials / test_artifact_five_slots / test_dawn_warrior_displayed ...): found by
    globbing, so a new one is picked up by run_all.py without being registered (an engine-native class's ``test_<id>_*.py`` is a global script of the full run, exactly once,
    and also one of that class's own jobs under ``--class <id>``)."""
    per_class = _per_class_scripts()
    return sorted(p.name for p in HERE.glob("test_*.py") if p.name not in per_class)


def all_jobs(only_class=None):
    """[(label, argv relative to tests/golden)] of everything run_all.py runs in the golden group: the global scripts (not with ``only_class``), then the
    per-class jobs of every class (or of ``only_class``): workbook classes = class golden, artifacts, sensitivity; engine-native = snapshot, engine-only checks and the
    class's own ``test_<id>_*.py`` scripts."""
    jobs = [] if only_class else [(s, [s]) for s in global_scripts()]
    for cid, e in ALL.items():
        if not only_class or cid == only_class:
            jobs += [(f"{cid}:{kind}", argv) for kind, argv in e.jobs()]
            if only_class and e.engine_native:
                jobs += [(f"{cid}:{s[5:-3]}", [s]) for s in e.extra_scripts()]
    if only_class and only_class not in ALL:
        return []
    return jobs


def check():
    """Every file named by the registry exists; returns the list of problems."""
    bad = []
    for cid, e in CLASSES.items():
        for name in (e.class_golden, e.artifacts_golden, e.sens_golden, e.class_script, f"sens_extras/{cid}.py", *e.tooling().values()):
            if not (HERE / name).exists():
                bad.append(f"{cid}: missing {name}")
    for s in PARAMETRISED + NATIVE_PARAMETRISED:
        if not (HERE / s).exists():
            bad.append(f"missing {s}")
    for cid, e in NATIVE.items():
        for rel in (f"engine/classes/{cid}.py", f"engine/data/{cid}.py", f"engine/sens_specs/{cid}.py"):
            if not (REPO / rel).exists():
                bad.append(f"{cid} (engine-native): missing {rel}")
        if not e.snapshot_path.exists():
            bad.append(f"{cid} (engine-native): missing {e.snapshot} - python3 tests/golden/update_goldens.py --create --class {cid} --reason \"...\"")
    return bad


if __name__ == "__main__":
    for cid, e in CLASSES.items():
        print(f"{cid:20s} {e.name:20s} spec={e.sens_spec!s:20s} {e.class_golden}, {e.artifacts_golden}, {e.sens_golden}")
    for cid, e in NATIVE.items():
        print(f"{cid:20s} {e.name:20s} engine-native: {e.snapshot} + test_engine_native.py" + ("".join(f", {x}" for x in e.extra_scripts())))
    problems = check()
    print("\n".join(problems) or f"registry OK: {len(CLASSES)} workbook classes + {len(NATIVE)} engine-native, {len(global_scripts())} global scripts")
    raise SystemExit(1 if problems else 0)
