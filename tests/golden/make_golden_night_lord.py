#!/usr/bin/env python3
"""Regenerate tests/golden/night_lord_golden.json: run the original Night Lord verify script (via run_reference_night_lord.py, in ONE subprocess,
workbook-free) over the case matrix of night_lord_cases.py and freeze its numbers.  The golden file is the reference; the engine is tested against it.

    python3 tests/golden/make_golden_night_lord.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import night_lord_cases as night_lord_cases  # noqa: E402
import make_golden_common  # noqa: E402


def main():
    make_golden_common.regenerate("night_lord", night_lord_cases.night_lord_cases)


if __name__ == "__main__":
    main()
