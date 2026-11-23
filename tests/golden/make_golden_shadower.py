#!/usr/bin/env python3
"""Regenerate tests/golden/shadower_golden.json: run the original Shadower verify script (via run_reference_shadower.py, in ONE subprocess,
workbook-free) over the case matrix of shadower_cases.py and freeze its numbers.  The golden file is the reference; the engine is tested against it.

    python3 tests/golden/make_golden_shadower.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import shadower_cases as shadower_cases  # noqa: E402
import make_golden_common  # noqa: E402


def main():
    make_golden_common.regenerate("shadower", shadower_cases.shadower_cases)


if __name__ == "__main__":
    main()
