#!/usr/bin/env python3
"""
Derives each Shadower scaling skill's (baseDamage(tenths%), factorIndex) tuple by matching its
wiki per-skill-level damage curve against src/ts/data/factor-table-data.ts's
SKILL_LEVEL_FACTOR_TABLE, same method as tools/_reverse_engineer_nl_factors.py /
_reverse_engineer_ilm_factors.py. Curve data transcribed from the individual wiki pages fetched
during planning (see /Users/yaniv/.claude/plans/vectorized-shimmying-pony.md for the full
patch-note reconciliation this incorporates — Blood Money's curve below is already rescaled by
3600/2800=1.2857x per that reconciliation).
"""
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FACTOR_TABLE_JSON = REPO / "data/factor_table.json"


def load_factor_table():
    data = json.loads(FACTOR_TABLE_JSON.read_text())
    return {int(k): v for k, v in data.items()}


FACTOR_TABLE = load_factor_table()
assert len(FACTOR_TABLE) == 300 and len(FACTOR_TABLE[1]) == 24

CURVES = {
    # Cross-validation against Night Lord's own already-known values (must resolve to the exact
    # same tuples Night Lord uses) — Dark Flare/Venom curves are the UNPATCHED wiki curves (same
    # as Night Lord's own build script reverse-engineered from), the patch-note corrections are
    # applied as base-value overrides afterward, exactly mirroring Night Lord's own treatment.
    "DARK_FLARE": [
        (1, 400), (10, 420), (20, 440), (30, 460), (40, 480), (50, 500), (60, 520), (70, 540),
        (80, 560), (90, 580), (100, 600), (110, 620), (120, 640), (130, 660), (140, 680),
        (150, 700), (160, 720), (170, 740), (180, 760), (190, 780), (200, 800),
    ],
    "VENOM": [
        (1, 45), (10, 46.8), (20, 48.6), (30, 50.4), (40, 52.2), (50, 54), (60, 55.8),
        (70, 57.6), (80, 59.4), (90, 61.2), (100, 63), (110, 64.8), (120, 66.6),
    ],
    "STEAL": [
        (1, 5), (10, 5.1), (20, 5.3), (30, 5.4), (40, 5.6), (50, 5.7), (60, 5.9), (70, 6),
        (80, 6.2), (90, 6.3), (100, 6.5),
    ],
    "MESO_EXPLOSION": [
        (1, 270), (10, 283.5), (20, 297), (30, 310.5), (40, 324), (50, 337.5),
    ],
    "PHASE_DASH": [
        (1, 450), (10, 472.5), (20, 495), (30, 517.5), (40, 540), (50, 562.5),
    ],
    "INTO_DARKNESS": [
        (1, 20), (10, 20.8), (20, 21.6), (30, 22.4), (40, 23.2), (50, 24),
    ],
    "ASSASSINATE_BASE": [
        (1, 1400), (10, 1456), (20, 1512), (30, 1568), (40, 1624), (50, 1680),
    ],
    "ASSASSINATE_FINISHER": [
        (1, 3000), (10, 3150), (20, 3300), (30, 3450), (40, 3600), (50, 3750),
    ],
    # Blood Money: wiki's own stale 2800%-anchored curve, PRE-rescale (rescale by 3600/2800
    # applied after resolving factorIndex, per the patch reconciliation — matches the
    # Elemental-Reset-rescale technique: shape/factorIndex unaffected by a base-value patch).
    "BLOOD_MONEY": [
        (1, 2800), (10, 2940), (20, 3080), (30, 3220), (40, 3360), (50, 3500),
    ],
    "SMOKESCREEN": [
        (1, 13), (10, 13.3), (20, 13.7), (30, 14.1), (40, 14.5), (50, 14.9),
    ],
    "HASTE": [
        (1, 15), (10, 15.4), (20, 15.9), (30, 16.3), (40, 16.8),
    ],
    "DAGGER_MASTERY": [
        (1, 15), (10, 15.4), (20, 15.9), (30, 16.3), (40, 16.8), (50, 17.2),
    ],
    "CRITICAL_EDGE_RATE": [
        (1, 6), (10, 6.1), (20, 6.3), (30, 6.5), (40, 6.7), (50, 6.9),
    ],
    "CRITICAL_EDGE_DMG": [
        (1, 10), (10, 10.3), (20, 10.6), (30, 10.9), (40, 11.2), (50, 11.5),
    ],
    "PHYSICAL_TRAINING": [
        (1, 10), (10, 10.3), (20, 10.6), (30, 10.9), (40, 11.2),
    ],
    "DAGGER_EXPERT_SKILL": [
        (1, 15), (10, 15.4), (20, 15.9), (30, 16.3), (40, 16.8), (50, 17.2),
    ],
    "DAGGER_EXPERT_MAXDMG": [
        (1, 20), (10, 20.6), (20, 21.2), (30, 21.8), (40, 22.4), (50, 23),
    ],
    "SHADOWER_INSTINCT": [
        (1, 20), (10, 20.6), (20, 21.2), (30, 21.8), (40, 22.4), (50, 23),
    ],
    "MAPLE_HERO_SHADOWER": [
        (1, 15), (10, 22.5), (20, 30), (30, 37.5), (60, 60), (100, 90), (120, 105),
        (130, 106.5), (140, 108), (150, 109.5),
    ],
}

TOLERANCE = 0.01


def resolve(name, samples):
    candidates = []
    for idx in range(24):
        implied = []
        ok = True
        for level, val in samples:
            factor = FACTOR_TABLE[level][idx]
            if factor == 0:
                ok = False
                break
            implied.append(val * 10 * 1000 / factor)
        if not ok:
            continue
        mean = sum(implied) / len(implied)
        if mean == 0:
            continue
        max_dev = max(abs(v - mean) / mean for v in implied)
        if max_dev <= TOLERANCE:
            candidates.append((idx, mean, max_dev))
    return candidates


def main():
    print(f"{'Skill':28s} {'FactorIndex':>11s} {'BaseDamage(tenths%)':>20s} {'MaxDev':>10s}")
    results = {}
    problems = []
    for name, samples in CURVES.items():
        candidates = resolve(name, samples)
        if len(candidates) != 1:
            problems.append((name, candidates))
            print(f"{name:28s}  ** {len(candidates)} candidates: {candidates} **")
            continue
        idx, mean, max_dev = candidates[0]
        base_tenths = round(mean)
        results[name] = (base_tenths, idx)
        print(f"{name:28s} {idx:11d} {base_tenths:20d} {max_dev:10.6f}")

    print()
    if problems:
        print(f"{len(problems)} skill(s) did not resolve to exactly one factorIndex:")
        for name, candidates in problems:
            print(f"  {name}: {candidates}")
    else:
        print("Every scaling skill resolved to exactly one factorIndex with acceptable residual error.")

    print()
    print("--- Python dict for copy-paste into build_shadower_workbook.py ---")
    for name, (base, idx) in results.items():
        print(f'    "{name}": (baseDamage={base}, factorIndex={idx}),')


if __name__ == "__main__":
    main()
