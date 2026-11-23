"""Skill-level factor table (``data/factor_table.json``: level 1..300 -> 24 factors) and the coefficient helpers built on it."""
import json

from .._src import DATA_DIR

_TABLE = None


def factor_table():
    """The table as ``{level: [F0..F23]}`` (loaded once, plain json - no numpy / openpyxl)."""
    global _TABLE
    if _TABLE is None:
        raw = json.loads((DATA_DIR / "factor_table.json").read_text())
        _TABLE = {int(k): v for k, v in raw.items()}
    return _TABLE


def get_factor(level, idx):
    level = min(300, max(1, round(level)))
    return factor_table()[level][idx]


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
