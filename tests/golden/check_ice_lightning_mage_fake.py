#!/usr/bin/env python3
"""Check that the workbook-free stand-in of run_reference_ice_lightning_mage.py serves the verify script exactly the cells the REAL workbook holds (the shared
body is ``check_fake_common.py``; only the Inputs and CompanionsInput sheets of ``Ice-Lightning-Mage/Ice-Lightning-Mage-DPS-Calculator.xlsx`` are streamed).

    python3 tests/golden/check_ice_lightning_mage_fake.py            # check only
    python3 tests/golden/check_ice_lightning_mage_fake.py --write    # also write tests/golden/ice_lightning_mage_real_inputs.json (the 10 real columns as golden cases)
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check_fake_common  # noqa: E402
import run_reference_ice_lightning_mage as rr  # noqa: E402

CHECK = check_fake_common.Check(rr.REF, "ice_lightning_mage", "Ice-Lightning-Mage")
bm, ck = CHECK.bm, CHECK.ck


def main():
    CHECK.main()


if __name__ == "__main__":
    main()
