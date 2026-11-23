#!/usr/bin/env python3
"""Regenerate tests/golden/bishop_golden.json: run the original Bishop verify script (via run_reference_bishop.py, in ONE subprocess,
workbook-free) over the case matrix of bishop_cases.py and freeze its numbers.  The golden file is the reference; the engine is tested against it.

    python3 tests/golden/make_golden_bishop.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bishop_cases as bishop_cases  # noqa: E402
import make_golden_common  # noqa: E402


def main():
    make_golden_common.regenerate("bishop", bishop_cases.bishop_cases)


if __name__ == "__main__":
    main()
