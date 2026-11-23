#!/usr/bin/env python3
"""Regenerate tests/golden/hero_golden.json: run the original Hero verify script (via run_reference_hero.py, in ONE subprocess,
workbook-free) over the case matrix of hero_cases.py and freeze its numbers.  The golden file is the reference; the engine is tested against it.

    python3 tests/golden/make_golden_hero.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hero_cases as hero_cases  # noqa: E402
import make_golden_common  # noqa: E402


def main():
    make_golden_common.regenerate("hero", hero_cases.hero_cases)


if __name__ == "__main__":
    main()
