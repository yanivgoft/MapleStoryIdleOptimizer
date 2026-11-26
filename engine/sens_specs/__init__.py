"""Per-class Sensitivity specs (pure data, see ``engine/common/sens.py::SensSpec``).  ``get(class_id)`` -> the spec, or None when the class has none yet.

Adding a class: write ``engine/sens_specs/<class_id>.py`` exposing ``SPEC`` and add the id to ``CLASS_IDS`` (recipe: engine/README.md "How to add a class to the
sensitivity engine")."""
import dataclasses
import importlib

CLASS_IDS = ("fp_mage", "dark_knight", "hero", "ice_lightning_mage", "blaze_wizard", "bishop", "buccaneer", "marksman", "bowmaster", "corsair", "paladin", "shadower", "night_lord", "dawn_warrior", "night_walker")
_cache = {}

# toggles of the artifacts the game added after the frozen workbooks (patch 2026-11-26) that the specs of the workbook classes do not list: Shiny Watch and Mummydog's Bandages
# grant Attack% (the timeline strip's Attack% bucket moves with them: the block re-runs the strip), Shiny Watch also changes the companion's damage (its summon-time
# search runs in full); Athena's Gloves' direct Attack Speed moves the first cast of a player's own stun (Poison Breath, patch 2026-11-26) and so the companion's summon choice; Sealed Bottle only touches Final Damage / Normal / Boss Monster Damage (like Sayram's Necklace / Candle's value part, no timing input).
# The workbook checks (``tests/golden/sens_extras``) compare the specs WITHOUT these keys (``tests/golden/patch_2026_11_26.py::workbook_keys``).
EXTRA_STATUS_REBUILD_KEYS = ("shiny_watch_equipped", "mummydogs_bandages_equipped")
EXTRA_COMPANION_FULL_SEARCH_KEYS = ("shiny_watch_equipped", "athena_gloves_equipped")


def get(class_id):
    if class_id not in CLASS_IDS:
        return None
    if class_id not in _cache:
        spec = importlib.import_module(f"{__name__}.{class_id}").SPEC
        _cache[class_id] = dataclasses.replace(
            spec, status_rebuild_keys=tuple(spec.status_rebuild_keys) + EXTRA_STATUS_REBUILD_KEYS,
            companion_full_search_keys=tuple(spec.companion_full_search_keys) + EXTRA_COMPANION_FULL_SEARCH_KEYS)
    return _cache[class_id]
