#!/usr/bin/env python3
"""Regenerate tests/golden/bowmaster_golden.json: run the original Bowmaster verify script (via run_reference_bowmaster.py, in ONE subprocess,
workbook-free) over the case matrix of bowmaster_cases.py and freeze its numbers.  The golden file is the reference; the engine is tested against it.

    python3 tests/golden/make_golden_bowmaster.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bowmaster_cases as bowmaster_cases  # noqa: E402
import make_golden_common  # noqa: E402


def main():
    make_golden_common.regenerate("bowmaster", bowmaster_cases.bowmaster_cases)


if __name__ == "__main__":
    main()
