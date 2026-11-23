#!/usr/bin/env python3
"""Golden test: ``engine.classes.dark_knight.compute`` WITH artifacts equipped against the Dark Knight WORKBOOK (evaluated with ``formulas`` by
``dark_knight_artifact_reference.py``; numbers frozen in tests/golden/dark_knight_artifacts_golden.json).  Plain ``python3`` runnable, also pytest-collectable.

    python3 tests/golden/test_dark_knight_artifacts.py             # rel 1e-9 on every compared value; exits 1 on any difference
    python3 tests/golden/test_dark_knight_artifacts.py --rtol 1e-6 -v

The shared body is ``artifacts_harness.py``.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))
from engine.classes import dark_knight  # noqa: E402
import artifacts_harness as AH  # noqa: E402

GOLDEN = HERE / "dark_knight_artifacts_golden.json"
# Summary rows compared besides the ones stored under golden["rows"] (builder constants R_*; Dark Knight's Lord of Darkness bonuses sit under the artifact
# crit sources, the Monster Damage-Taken bucket carries Peach Tree / Silver Pendant)
SUMMARY_ROWS = {"crit_rate_bonus": (14, "crit_rate_bonus"), "monster_dmg_bonus": (15, "monster_dmg_bonus"), "baps": (19, "basic_attacks_per_second"),
                "crit_damage_bonus": (20, "crit_damage_bonus")}


TEST = AH.ArtifactsTest(dark_knight, GOLDEN, summary_rows=SUMMARY_ROWS)
compare, run = TEST.compare, TEST.run


def test_dark_knight_artifacts_match_workbook():
    TEST.assert_matches()


if __name__ == "__main__":
    TEST.main()
