#!/usr/bin/env python3
"""Regenerate tests/golden/marksman_golden.json: run the original Marksman verify script (via run_reference_marksman.py, in ONE subprocess,
workbook-free) over the case matrix of marksman_cases.py and freeze its numbers.  The golden file is the reference; the engine is tested against it.

    python3 tests/golden/make_golden_marksman.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import marksman_cases as marksman_cases  # noqa: E402
import make_golden_common  # noqa: E402


def main():
    make_golden_common.regenerate("marksman", marksman_cases.marksman_cases)


if __name__ == "__main__":
    main()
