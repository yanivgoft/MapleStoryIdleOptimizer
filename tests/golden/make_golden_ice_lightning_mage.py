#!/usr/bin/env python3
"""Regenerate tests/golden/ice_lightning_mage_golden.json: run the original Ice/Lightning Mage verify script (via run_reference_ice_lightning_mage.py, in ONE subprocess,
workbook-free) over the case matrix of ice_lightning_mage_cases.py and freeze its numbers.  The golden file is the reference; the engine is tested against it.

    python3 tests/golden/make_golden_ice_lightning_mage.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ice_lightning_mage_cases as ilm_cases  # noqa: E402
import make_golden_common  # noqa: E402


def main():
    make_golden_common.regenerate("ice_lightning_mage", ilm_cases.ice_lightning_mage_cases)


if __name__ == "__main__":
    main()
