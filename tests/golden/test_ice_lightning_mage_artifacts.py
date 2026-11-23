#!/usr/bin/env python3
"""Golden test: ``engine.classes.ice_lightning_mage.compute`` WITH artifacts equipped against the Ice/Lightning Mage WORKBOOK (evaluated with ``formulas`` by
``ice_lightning_mage_artifact_reference.py``; numbers frozen in tests/golden/ice_lightning_mage_artifacts_golden.json).  Plain ``python3`` runnable, also pytest-collectable.

    python3 tests/golden/test_ice_lightning_mage_artifacts.py             # rel 1e-9 on every compared value; exits 1 on any difference
    python3 tests/golden/test_ice_lightning_mage_artifacts.py --rtol 1e-6 -v

The shared body is ``artifacts_harness.py``.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))
from engine.classes import ice_lightning_mage  # noqa: E402
import artifacts_harness as AH  # noqa: E402

GOLDEN = HERE / "ice_lightning_mage_artifacts_golden.json"


TEST = AH.ArtifactsTest(ice_lightning_mage, GOLDEN, boss_col="S", normal_col="U")
compare, run = TEST.compare, TEST.run


def test_ice_lightning_mage_artifacts_match_workbook():
    TEST.assert_matches()


if __name__ == "__main__":
    TEST.main()
