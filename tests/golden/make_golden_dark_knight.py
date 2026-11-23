#!/usr/bin/env python3
"""Regenerate tests/golden/dark_knight_golden.json: run the original Dark Knight verify script (via run_reference_dark_knight.py, in ONE subprocess,
workbook-free) over the case matrix of dark_knight_cases.py and freeze its numbers.  The golden file is the reference; the engine is tested against it.

    python3 tests/golden/make_golden_dark_knight.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dark_knight_cases as dark_knight_cases  # noqa: E402
import make_golden_common  # noqa: E402


def main():
    make_golden_common.regenerate("dark_knight", dark_knight_cases.dark_knight_cases)


if __name__ == "__main__":
    main()
