#!/usr/bin/env python3
"""Golden test: ``engine.classes.corsair.compute`` WITH artifacts equipped against the Corsair WORKBOOK (evaluated with ``formulas`` by
``corsair_artifact_reference.py``; numbers frozen in tests/golden/corsair_artifacts_golden.json).  Plain ``python3`` runnable, also pytest-collectable.

    python3 tests/golden/test_corsair_artifacts.py             # rel 1e-9 on every compared value; exits 1 on any difference
    python3 tests/golden/test_corsair_artifacts.py --rtol 1e-6 -v

The shared body is ``artifacts_harness.py``.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))
from engine.classes import corsair  # noqa: E402
import artifacts_harness as AH  # noqa: E402

GOLDEN = HERE / "corsair_artifacts_golden.json"


TEST = AH.ArtifactsTest(corsair, GOLDEN)
compare, run = TEST.compare, TEST.run


def test_corsair_artifacts_match_workbook():
    TEST.assert_matches()


if __name__ == "__main__":
    TEST.main()
