#!/usr/bin/env python3
"""Regenerate tests/golden/buccaneer_golden.json: run the original Buccaneer verify script (via run_reference_buccaneer.py, in ONE subprocess,
workbook-free) over the case matrix of buccaneer_cases.py and freeze its numbers.  The golden file is the reference; the engine is tested against it.

    python3 tests/golden/make_golden_buccaneer.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import buccaneer_cases as buccaneer_cases  # noqa: E402
import make_golden_common  # noqa: E402


def main():
    make_golden_common.regenerate("buccaneer", buccaneer_cases.buccaneer_cases)


if __name__ == "__main__":
    main()
