"""Class discovery: every module ``engine/classes/<id>.py`` that exposes callables ``compute`` / ``defaults`` / ``schema`` is a class.

Done once at startup (``discover()``); a module that fails to import is logged and skipped so one half-finished class never takes the API
down.

PUBLISH GATE: a class module that exports ``PUBLISHED = False`` is hidden (not listed, 404 "unknown class" everywhere) unless the environment variable
``MSI_INCLUDE_UNPUBLISHED=1`` is set; tests/run_all.py sets it so unpublished classes are still tested.  A missing ``PUBLISHED`` means published.
"""
import importlib
import logging
import os
import pkgutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:               # the engine package lives at the repo root (engine/_src.py then adds src/)
    sys.path.insert(0, str(REPO_ROOT))

log = logging.getLogger("msi.registry")


# job family per class id (presentation only; an unknown class falls under "Other")
FAMILIES = {
    "hero": "Warrior", "paladin": "Warrior", "dark_knight": "Warrior", "dawn_warrior": "Warrior",
    "fp_mage": "Mage", "ice_lightning_mage": "Mage", "blaze_wizard": "Mage", "bishop": "Mage",
    "bowmaster": "Archer", "marksman": "Archer", "wind_archer": "Archer",
    "night_lord": "Thief", "shadower": "Thief", "night_walker": "Thief",
    "buccaneer": "Pirate", "corsair": "Pirate",
}


# Classes with a stat-values (sensitivity) module.  THE single place to extend when another class gets one; if ``engine.sensitivity`` grows a
# ``supports(class_module)`` function that is asked instead (this tuple is then only the fallback).
SENSITIVITY_CLASSES = ("fp_mage", "dark_knight", "hero", "ice_lightning_mage", "buccaneer", "bishop", "marksman", "bowmaster", "corsair", "paladin", "night_lord", "shadower", "dawn_warrior")
SENSITIVITY_PARTS = ("stats", "artifacts", "companions", "summon_time", "cdr")


def _sensitivity_module():
    try:
        from engine import sensitivity
    except Exception:                              # noqa: BLE001 - a broken sensitivity module only disables the feature
        log.exception("engine.sensitivity failed to import; stat values disabled")
        return None
    return sensitivity


class ClassEntry:
    __slots__ = ("id", "module", "name", "_schema", "_sens_meta")

    def __init__(self, id_, module):
        self.id = id_
        self.module = module
        self._schema = module.schema()
        self._sens_meta = None
        self.name = self._schema.get("name") or getattr(module, "CLASS_NAME", id_)

    @property
    def schema(self):
        return self._schema

    @property
    def family(self):
        return FAMILIES.get(self.id, "Other")

    def info(self):
        """Entry of ``GET /api/classes``: identity, family and what is modelled (``status``: feature -> bool)."""
        sch = self._schema
        companions = any(f["key"] == "companion_choice" for f in sch["fields"])
        return {"id": self.id, "name": self.name, "family": self.family, "stat_identity": sch.get("stat_identity"),
                "artifacts_modelled": bool(sch.get("artifacts_modelled")),
                "status": {"companions": companions, "artifacts": bool(sch.get("artifacts_modelled")), "stat_values": self.supports_sensitivity}}

    @property
    def supports_sensitivity(self):
        """Does the engine model stat values (marginal DPS tables) for this class?"""
        sens = _sensitivity_module()
        if sens is None:
            return False
        check = getattr(sens, "supports", None)
        if callable(check):
            try:
                return bool(check(self.module))
            except Exception:                      # noqa: BLE001
                log.exception("sensitivity.supports failed for %s", self.id)
                return False
        return self.id in SENSITIVITY_CLASSES

    def sensitivity(self, inputs, which=None, companion_level=None):
        """Engine ``sensitivity.run`` (raises NotImplementedError when unsupported)."""
        sens = _sensitivity_module()
        if sens is None or not self.supports_sensitivity:
            raise NotImplementedError("stat values are not modelled for this class yet")
        kwargs = {} if companion_level is None else {"companion_level": companion_level}
        return sens.run(self.module, inputs, which=which, **kwargs)

    def sensitivity_meta(self):
        """Static metadata for rendering the tables without computing: stats, artifact toggles, parts."""
        if self._sens_meta is None:
            sens = _sensitivity_module()
            if sens is None or not self.supports_sensitivity:
                raise NotImplementedError("stat values are not modelled for this class yet")
            per_class = sens.meta(self.module) if callable(getattr(sens, "meta", None)) else None      # (the class's own stat list)
            self._sens_meta = {
                "class_id": self.id,
                "parts": list(getattr(sens, "PARTS", SENSITIVITY_PARTS)),
                "stats": list(per_class["stats"] if per_class else sens.STAT_SWEEP),
                "artifacts": list(sens.ARTIFACT_TOGGLES),
                "cdr_values": list(getattr(sens, "CDR_SWEEP_VALUES", [])),
                "metric": {
                    "units_per_1pct": "units of the stat needed for +1% DPS (1 / (% gain of one step - 100)); LOWER = more valuable per unit; null = n/a (no gain)",
                    "dps_gain": "total DPS gained by ONE step of the stat (the 'DPS per +1')",
                    "pct_gain": "new total / baseline total x 100 (100 = no change)",
                    "equip": "artifacts are ranked by % gain among unlocked ones; no_dps_effect artifacts do not change the model",
                },
            }
        return self._sens_meta

    def defaults(self, content_type=None):
        return self.module.defaults(content_type) if content_type else self.module.defaults()

    def compute(self, inputs):
        return self.module.compute(inputs)


def include_unpublished():
    """Does the environment ask for classes that are still ``PUBLISHED = False``?  (``MSI_INCLUDE_UNPUBLISHED=1``; anything else = no)"""
    from engine import INCLUDE_UNPUBLISHED_ENV
    return os.environ.get(INCLUDE_UNPUBLISHED_ENV, "").strip().lower() in ("1", "true", "yes", "on")


def discover():
    """``{class id: ClassEntry}`` in alphabetical order; classes with ``PUBLISHED = False`` only when ``MSI_INCLUDE_UNPUBLISHED=1``."""
    import engine.classes as pkg
    from engine import is_published
    with_unpublished = include_unpublished()

    found = {}
    for info in sorted(pkgutil.iter_modules(pkg.__path__), key=lambda m: m.name):
        if info.name.startswith("_"):
            continue
        try:
            mod = importlib.import_module(f"engine.classes.{info.name}")
        except Exception:                          # noqa: BLE001 - a broken class module must not stop the others
            log.exception("class module %s failed to import; skipped", info.name)
            continue
        if not all(callable(getattr(mod, attr, None)) for attr in ("compute", "defaults", "schema")):
            continue
        if not with_unpublished and not is_published(mod):
            log.info("class %s is unpublished (PUBLISHED = False): hidden (set MSI_INCLUDE_UNPUBLISHED=1 to serve it)", info.name)
            continue
        try:
            found[info.name] = ClassEntry(info.name, mod)
        except Exception:                          # noqa: BLE001
            log.exception("class %s: schema() failed; skipped", info.name)
    return found
