"""MapleStory Idle DPS engine: a plain-Python (stdlib only) calculation package.

``engine.classes.<class>.compute(inputs) -> dict`` is the single entry point per class.  See engine/README.md.

PUBLISH GATE: a class module may export ``PUBLISHED = False`` (a class under development: it lives in the repo and is fully tested, but the live site must
not serve it).  A missing attribute means published, so finished classes need no edit.  The API hides an unpublished class unless the environment variable
``MSI_INCLUDE_UNPUBLISHED=1`` is set (tests/run_all.py sets it for every test process); ``deploy/redeploy.sh`` expects ``published_classes()``.
"""
import importlib
import pkgutil

from . import _src  # noqa: F401  (side effect: makes src/'s shared pure-Python modules importable)

# Every class id the repo knows, published or not (the tests that loop over ``CLASSES`` therefore cover a class that is still unpublished).  A new class is added here.
CLASSES = ("fp_mage", "hero", "ice_lightning_mage", "blaze_wizard", "paladin", "bowmaster", "bishop", "dark_knight",
           "marksman", "buccaneer", "corsair", "night_lord", "shadower", "dawn_warrior", "night_walker")

INCLUDE_UNPUBLISHED_ENV = "MSI_INCLUDE_UNPUBLISHED"       # "1" = the API serves unpublished classes too (tests, fixture generation with --include-unpublished)


def is_published(module):
    """Is this class module served on the live site?  ``PUBLISHED`` missing = True; only an explicit ``PUBLISHED = False`` hides a class."""
    return getattr(module, "PUBLISHED", True) is not False


def published_classes():
    """Ids of the classes the live site serves: every ``engine/classes/<id>.py`` (the ids of ``CLASSES`` first, in that order, then any module not listed there,
    alphabetically) whose module does not export ``PUBLISHED = False``.  Ignores ``MSI_INCLUDE_UNPUBLISHED`` (that only affects what the API serves).  Imports the
    class modules (stdlib only, ~30 ms for all of them); a module that fails to import is skipped, as the API does."""
    from . import classes as pkg
    ids = list(CLASSES) + sorted(m.name for m in pkgutil.iter_modules(pkg.__path__) if not m.name.startswith("_") and m.name not in CLASSES)
    out = []
    for cid in ids:
        try:
            mod = importlib.import_module(f"{__name__}.classes.{cid}")
        except Exception:                                                  # noqa: BLE001 - mirror api.registry.discover
            continue
        if all(callable(getattr(mod, a, None)) for a in ("compute", "defaults", "schema")) and is_published(mod):
            out.append(cid)
    return out
