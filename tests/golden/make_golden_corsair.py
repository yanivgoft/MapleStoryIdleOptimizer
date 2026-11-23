#!/usr/bin/env python3
"""Regenerate tests/golden/corsair_golden.json: run the original Corsair verify script (via run_reference_corsair.py, in ONE subprocess,
workbook-free) over the case matrix of corsair_cases.py and freeze its numbers.  The golden file is the reference; the engine is tested against it.

    python3 tests/golden/make_golden_corsair.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import corsair_cases as corsair_cases  # noqa: E402
import make_golden_common  # noqa: E402


def main():
    make_golden_common.regenerate("corsair", corsair_cases.corsair_cases)


if __name__ == "__main__":
    main()
