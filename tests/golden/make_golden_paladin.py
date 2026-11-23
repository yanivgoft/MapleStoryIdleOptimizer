#!/usr/bin/env python3
"""Regenerate tests/golden/paladin_golden.json: run the original Paladin verify script (via run_reference_paladin.py, in ONE subprocess,
workbook-free) over the case matrix of paladin_cases.py and freeze its numbers.  The golden file is the reference; the engine is tested against it.

    python3 tests/golden/make_golden_paladin.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paladin_cases as paladin_cases  # noqa: E402
import make_golden_common  # noqa: E402


def main():
    make_golden_common.regenerate("paladin", paladin_cases.paladin_cases)


if __name__ == "__main__":
    main()
