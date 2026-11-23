#!/usr/bin/env python3
"""Golden test: ``engine.classes.night_lord.compute`` WITH artifacts equipped against the Night Lord WORKBOOK (evaluated with ``formulas`` by
``night_lord_artifact_reference.py``; numbers frozen in tests/golden/night_lord_artifacts_golden.json).  Plain ``python3`` runnable, also pytest-collectable.

    python3 tests/golden/test_night_lord_artifacts.py             # rel 1e-9 on every compared value; exits 1 on any difference
    python3 tests/golden/test_night_lord_artifacts.py --rtol 1e-6 -v

The shared body is ``artifacts_harness.py``.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))
from engine.classes import night_lord  # noqa: E402
import artifacts_harness as AH  # noqa: E402

GOLDEN = HERE / "night_lord_artifacts_golden.json"
# Summary rows compared besides the ones stored under golden["rows"] (builder constants R_*; Critical Throw / Dark Sight's Crit Rate and Frailty Curse's Critical-Damage-Taken mastery are the live crit bonuses; Peach Tree / Silver Pendant
# are NOT in Summary's Monster Damage-Taken row (they are their own bucket AGG_ENEMY_DMG_TAKEN))
SUMMARY_ROWS = {"crit_rate_bonus": (14, "crit_rate_bonus"), "monster_dmg_bonus": (15, "monster_dmg_bonus"), "baps": (22, "basic_attacks_per_second"),
                "crit_damage_bonus": (24, "crit_damage_bonus")}


TEST = AH.ArtifactsTest(night_lord, GOLDEN, summary_rows=SUMMARY_ROWS)
compare, run = TEST.compare, TEST.run


def test_night_lord_artifacts_match_workbook():
    TEST.assert_matches()


if __name__ == "__main__":
    TEST.main()
