"""Per-class Sensitivity specs (pure data, see ``engine/common/sens.py::SensSpec``).  ``get(class_id)`` -> the spec, or None when the class has none yet.

Adding a class: write ``engine/sens_specs/<class_id>.py`` exposing ``SPEC`` and add the id to ``CLASS_IDS`` (recipe: engine/README.md "How to add a class to the
sensitivity engine")."""
import importlib

CLASS_IDS = ("fp_mage", "dark_knight", "hero", "ice_lightning_mage", "bishop", "buccaneer", "marksman", "bowmaster", "corsair", "paladin", "shadower", "night_lord")
_cache = {}


def get(class_id):
    if class_id not in CLASS_IDS:
        return None
    if class_id not in _cache:
        _cache[class_id] = importlib.import_module(f"{__name__}.{class_id}").SPEC
    return _cache[class_id]
