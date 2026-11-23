#!/usr/bin/env python3
"""Regenerate tests/golden/fp_mage_golden.json: run the original verify script (via run_reference.py, in ONE subprocess, workbook-free)
over the case matrix of cases.py and freeze its numbers.  The golden file is the reference; the engine is tested against it.

    python3 tests/golden/make_golden.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cases  # noqa: E402
import make_golden_common  # noqa: E402


def main():
    make_golden_common.regenerate("fp_mage", cases.fp_mage_cases, reference="run_reference.py")


if __name__ == "__main__":
    main()
