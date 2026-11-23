"""MapleStory Idle DPS engine: a plain-Python (stdlib only) calculation package.

``engine.classes.<class>.compute(inputs) -> dict`` is the single entry point per class.  See engine/README.md.
"""
from . import _src  # noqa: F401  (side effect: makes src/'s shared pure-Python modules importable)

CLASSES = ("fp_mage", "hero", "ice_lightning_mage", "paladin", "bowmaster", "bishop", "dark_knight",
           "marksman", "buccaneer", "corsair", "night_lord", "shadower", "dawn_warrior")
