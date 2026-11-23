"""The ONE list of classes the golden tests know about: which engine module, which golden files, which sensitivity spec / extras module.

Everything that has to enumerate the per-class checks reads this file: ``tests/run_all.py`` (jobs), ``test_artifacts.py`` / ``test_sensitivity.py`` (pytest
parametrisation and ``--class``), ``sens_test_common.py`` and the CI workflows (through run_all).  A new class = one ``Entry`` here (+ its golden files, its
``test_<id>.py`` class golden and ``sens_extras/<id>.py``).

Per class, three checks (the "kinds"):
  class         ``test_<id>.py``                          engine == the verify script's frozen numbers, bit-exact        (``<id>_golden.json``)
  artifacts     ``test_artifacts.py --class <id>``        engine with artifacts equipped == the workbook, rel 1e-9         (``<id>_artifacts_golden.json``)
  sensitivity   ``test_sensitivity.py --class <id>``      engine.sensitivity == the workbook's Sensitivity sheet + engine-only checks (``<id>_sensitivity_golden.json``)

``python3 tests/golden/registry.py`` prints the table and checks that every file named here exists.
"""
import importlib
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

KINDS = ("class", "artifacts", "sensitivity")

# The parametrised scripts (``--class <id>``)
PARAMETRISED = ("test_artifacts.py", "test_sensitivity.py")


@dataclass(frozen=True)
class Entry:
    id: str
    name: str                       # display name (also the builder's class name in the workbook file name)
    sens_spec: object               # id of the engine/sens_specs spec (None: FP-Mage has its own, non-spec sensitivity engine)
    artifacts: dict = field(default_factory=dict)       # ArtifactsTest options (data only; callables are in artifacts_extras.py): boss_col, normal_col, summary_rows, extras
    prefix: str = ""                # prefix of the generation-time tooling (cases / reference / make_golden ...): "" for FP-Mage (cases.py, run_reference.py ...)

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

    def jobs(self):
        """[(kind, argv relative to tests/golden)] - what run_all.py runs for this class."""
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


def global_scripts():
    """Every ``test_*.py`` that is not per class (test_cubes / test_equipment / test_potentials / test_artifact_five_slots ...): found by globbing, so a new one is
    picked up by run_all.py without being registered."""
    per_class = {e.class_script for e in CLASSES.values()} | set(PARAMETRISED)
    return sorted(p.name for p in HERE.glob("test_*.py") if p.name not in per_class)


def all_jobs(only_class=None):
    """[(label, argv relative to tests/golden)] of everything run_all.py runs in the golden group: the global scripts (not with ``only_class``), then the
    per-class jobs (class golden, artifacts, sensitivity) of every class (or of ``only_class``)."""
    jobs = [] if only_class else [(s, [s]) for s in global_scripts()]
    for cid, e in CLASSES.items():
        if not only_class or cid == only_class:
            jobs += [(f"{cid}:{kind}", argv) for kind, argv in e.jobs()]
    return jobs


def check():
    """Every file named by the registry exists; returns the list of problems."""
    bad = []
    for cid, e in CLASSES.items():
        for name in (e.class_golden, e.artifacts_golden, e.sens_golden, e.class_script, f"sens_extras/{cid}.py", *e.tooling().values()):
            if not (HERE / name).exists():
                bad.append(f"{cid}: missing {name}")
    for s in PARAMETRISED:
        if not (HERE / s).exists():
            bad.append(f"missing {s}")
    return bad


if __name__ == "__main__":
    for cid, e in CLASSES.items():
        print(f"{cid:20s} {e.name:20s} spec={e.sens_spec!s:20s} {e.class_golden}, {e.artifacts_golden}, {e.sens_golden}")
    problems = check()
    print("\n".join(problems) or f"registry OK: {len(CLASSES)} classes, {len(global_scripts())} global scripts")
    raise SystemExit(1 if problems else 0)
