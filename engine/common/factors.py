"""Skill-level growth factors (``data/factor_table.json``: level 1..300 -> 24 columns; the curves in use are also available as exact linear formulas, extended past 300) and the coefficient helpers built on it.

LEGACY CLAMP MODE (default OFF): the frozen Excel workbooks (and the goldens generated from them) hold the table only up to level 300 and clamp there.  The engine
now continues the growth curves past 300 (see ``LINEAR_CURVES``), so every test that compares the engine with a WORKBOOK-derived golden must pin the old behaviour:
``set_legacy_clamp(True)`` / the ``MSI_FACTOR_LEGACY_CLAMP=1`` environment variable (read at import) / ``with legacy_clamp():``.  When ON, ``get_factor`` clamps the level at 300
for EVERY curve, bit-exactly like the pre-extension code.  Production never sets it.  (Engine-native classes and the factor tests run in the default extended mode.)
"""
import json
import os
from contextlib import contextmanager

from .._src import DATA_DIR

_TABLE = None
_LEGACY_CLAMP = os.environ.get("MSI_FACTOR_LEGACY_CLAMP", "").strip().lower() in ("1", "true", "yes", "on")


def set_legacy_clamp(on):
    """Switch the legacy 300-clamp on/off (tests only); returns the previous setting."""
    global _LEGACY_CLAMP
    prev, _LEGACY_CLAMP = _LEGACY_CLAMP, bool(on)
    return prev


def legacy_clamp_enabled():
    return _LEGACY_CLAMP


@contextmanager
def legacy_clamp(on=True):
    """``with legacy_clamp():`` - the legacy 300-clamp inside the block, the previous mode restored afterwards."""
    prev = set_legacy_clamp(on)
    try:
        yield
    finally:
        set_legacy_clamp(prev)


def factor_table():
    """The table as ``{level: [F0..F23]}`` (loaded once, plain json - no numpy / openpyxl)."""
    global _TABLE
    if _TABLE is None:
        raw = json.loads((DATA_DIR / "factor_table.json").read_text())
        _TABLE = {int(k): v for k, v in raw.items()}
    return _TABLE


# The growth curves in use are exactly piecewise LINEAR in the skill level (checked against the table for levels 1..300 by tests/golden/test_factor_formulas.py), and
# the game keeps growing them past 300 (user's Night Walker readings at total level 322 match the straight-line continuation for curves 12, 21, 22 and 23).  Each entry:
# idx -> ((first level, slope per level), ...); the factor is 1000 at level 1 and, from each segment's first level on, grows by that slope per level.  The value at the
# start of a segment follows from the previous ones.  A curve not listed here (the irregular / exponential columns, 0 = non-scaling) is looked up in the table, held at level 300.
LINEAR_CURVES = {
    8: ((1, 20), (2, 10), (100, 0)),
    10: ((1, 20), (2, 10), (150, 0)),
    11: ((1, 0), (100, 1), (200, 0)),
    12: ((1, 10), (2, 5)),
    13: ((1, 20), (2, 10)),
    14: ((1, 30), (2, 15)),
    15: ((1, 40), (2, 20)),
    16: ((1, 50), (2, 25)),
    17: ((1, 60), (2, 30)),
    18: ((1, 70), (2, 35)),
    19: ((1, 80), (2, 40)),
    21: ((1, 8), (2, 4)),
    22: ((1, 6), (2, 3)),
    23: ((1, 100), (2, 50), (120, 10)),
}


def linear_factor(level, idx):
    """The piecewise-linear curve ``idx`` (``LINEAR_CURVES``) at an integer ``level >= 1``, extended past 300 with its last slope."""
    value, at = 1000, 1
    for (start, slope), nxt in zip(LINEAR_CURVES[idx], list(LINEAR_CURVES[idx][1:]) + [(None, None)]):
        end = level if nxt[0] is None or level < nxt[0] else nxt[0]
        if end > at:
            value += slope * (end - at)
            at = end
        if nxt[0] is None or level < nxt[0]:
            break
    return value


def get_factor(level, idx):
    level = max(1, round(level))
    if _LEGACY_CLAMP:
        return factor_table()[min(300, level)][idx]
    if idx in LINEAR_CURVES:
        return linear_factor(level, idx)
    return factor_table()[min(300, level)][idx]


def input_level(job_step, level, skill1, skill2, skill3, skill4, skill_all):
    """Effective skill level of a job tier: tier base (60/90/120) + that tier's bonus + the all-skills bonus; 4th job scales with
    character level beyond 100."""
    if job_step == 1:
        return 60 + skill1 + skill_all
    if job_step == 2:
        return 90 + skill2 + skill_all
    if job_step == 3:
        return 120 + skill3 + skill_all
    return max(0, (level - 100) * 3) + skill4 + skill_all


class SkillLevels:
    """Character level + the five skill-level bonus inputs; resolves a skill's coefficient (% of attack) from its table row."""

    __slots__ = ("level", "skill1", "skill2", "skill3", "skill4", "skill_all")

    def __init__(self, level, skill1, skill2, skill3, skill4, skill_all):
        self.level, self.skill1, self.skill2, self.skill3, self.skill4, self.skill_all = level, skill1, skill2, skill3, skill4, skill_all

    def input_level(self, job_step):
        return input_level(job_step, self.level, self.skill1, self.skill2, self.skill3, self.skill4, self.skill_all)

    def coeff_pct(self, base, fidx, scales, job_step):
        """(BaseDamage in tenths-of-%) x factor[fidx] at the skill's effective level, in %; non-scaling skills ignore the factor."""
        lvl = self.input_level(job_step)
        if not scales:
            return base / 10
        return (base / 10) * (get_factor(lvl, fidx) / 1000)


def level_gated_sum(level, pairs):
    """Cumulative sum of every (threshold, increment) pair the character's level has reached (mastery chains: raw tier values)."""
    return sum(inc for lvl, inc in pairs.items() if level >= lvl)
