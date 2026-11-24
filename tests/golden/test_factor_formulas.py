#!/usr/bin/env python3
"""The growth curves in use are exact piecewise-linear formulas (engine/common/factors.py LINEAR_CURVES): equal to data/factor_table.json for every level 1..300, and
extended past 300 with their last slope (the game does not stop at 300: Night Walker readings at total level 322 match, below).  Plain python, also pytest-collectable."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from engine.common import factors as F  # noqa: E402
sys.path.insert(0, str(HERE))
import factor_mode  # noqa: E402

FACTOR_MODE = factor_mode.pin("extended")        # production mode: growth curves continue past level 300

TABLE = {int(k): v for k, v in json.loads((HERE.parents[1] / "data" / "factor_table.json").read_text()).items()}

# (base, shown value, total level, curve idx): in-game readings of a Night Walker (user, 2026-11-24); the game truncates to 1 decimal
READINGS = [(290, 663.5, 322, 21), (2850, 7438.5, 322, 12), (20, 45.7, 322, 21), (120, 1082.4, 322, 23), (150, 1353, 322, 23), (150, 343.2, 322, 21),
            (15, 29.4, 322, 22), (20, 39.3, 322, 22), (12, 23.5, 322, 22), (5, 9.8, 322, 22), (300, 634.8, 279, 21), (145, 347.2, 279, 12),
            (15, 27.5, 279, 22), (220, 460.9, 219, 12), (10, 16.5, 219, 22), (10, 16, 151, 21), (38, 66.6, 151, 12)]


def trunc1(x):
    return int(x * 10 + 1e-9) / 10


def test_formulas_equal_the_table():
    bad = [(i, lvl) for i in F.LINEAR_CURVES for lvl in range(1, 301) if F.linear_factor(lvl, i) != TABLE[lvl][i]]
    assert not bad, bad[:5]


def test_non_linear_columns_still_use_the_table_clamped_at_300():
    assert F.get_factor(250, 3) == TABLE[250][3] and F.get_factor(400, 3) == TABLE[300][3]
    assert F.get_factor(10, 0) == 0 and F.get_factor(0, 12) == F.get_factor(1, 12) == 1000


def test_extension_past_300_matches_the_in_game_readings():
    for base, shown, level, idx in READINGS:
        assert trunc1(base * F.get_factor(level, idx) / 1000) == shown, (base, shown, level, idx)
    assert [F.get_factor(322, i) for i in (12, 21, 22, 23)] == [2610, 2288, 1966, 9020]


if __name__ == "__main__":
    for t in (test_formulas_equal_the_table, test_non_linear_columns_still_use_the_table_clamped_at_300, test_extension_past_300_matches_the_in_game_readings):
        t()
    print(f"OK: {len(F.LINEAR_CURVES)} linear curves == the table for levels 1..300; {len(READINGS)} in-game readings (incl. total level 322) reproduced")
