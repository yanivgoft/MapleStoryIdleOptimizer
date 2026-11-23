#!/usr/bin/env python3
"""Golden test: ``engine.classes.marksman.compute`` WITH artifacts equipped against the Marksman WORKBOOK (evaluated with ``formulas`` by
``marksman_artifact_reference.py``; numbers frozen in tests/golden/marksman_artifacts_golden.json).  Plain ``python3`` runnable, also pytest-collectable.

    python3 tests/golden/test_marksman_artifacts.py             # rel 1e-9 on every compared value; exits 1 on any difference
    python3 tests/golden/test_marksman_artifacts.py --rtol 1e-6 -v

The shared body is ``artifacts_harness.py``.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))
from engine.classes import marksman  # noqa: E402
import artifacts_harness as AH  # noqa: E402

GOLDEN = HERE / "marksman_artifacts_golden.json"
# Summary rows compared besides the ones stored under golden["rows"] (builder constants R_*)
SUMMARY_ROWS = {"monster_dmg_bonus": (15, "monster_dmg_bonus"), "as_bonus": (16, "as_bonus"), "baps": (19, "basic_attacks_per_second"),
                "mortal_blow": (21, "mortal_blow_bonus")}


def extra_summary(chk, wb, s, d):
    # Summary's Global Critical Damage Bonus (row 20) is Sharp Eyes' average alone; the engine's ``crit_damage_bonus`` adds the Crit Damage artifacts
    chk("summary.crit_damage_bonus", s["20"] + wb["artifacts"]["AGG_CRIT_DAMAGE"], d["crit_damage_bonus"])


TEST = AH.ArtifactsTest(marksman, GOLDEN, summary_rows=SUMMARY_ROWS, extra_summary=extra_summary)
compare, run = TEST.compare, TEST.run


def test_marksman_artifacts_match_workbook():
    TEST.assert_matches()


if __name__ == "__main__":
    TEST.main()
