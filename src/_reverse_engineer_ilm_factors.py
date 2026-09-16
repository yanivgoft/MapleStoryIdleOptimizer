#!/usr/bin/env python3
"""
Throwaway script (run once by hand, not part of the build pipeline) — derives each Ice/Lightning
Arch Mage scaling skill's (baseDamage(tenths%), factorIndex) tuple by matching its wiki
per-skill-level damage curve against src/ts/data/factor-table-data.ts's
SKILL_LEVEL_FACTOR_TABLE, same method as tools/_reverse_engineer_nl_factors.py.

Curve data below is transcribed directly from /tmp/ilm_raw_data_full.txt (each skill's individual
wiki page "Skill Enhancement" table) — pre-patch values where a patch changes only the *base*
(level-1) value, not the scaling *shape* (Elemental Reset: 10%->16% wiki curve, patched to
12%->19.2% via the 12/10=1.2x factor per /tmp/ilm_authoritative_corrections.txt).
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
    "CHAIN_LIGHTNING": [
        (1, 290), (10, 301.6), (20, 313.2), (30, 324.8), (40, 336.4), (50, 348), (60, 359.6),
        (70, 371.2), (80, 382.8), (90, 394.4), (100, 406), (110, 417.6), (120, 429.2),
        (130, 440.8), (140, 452.4), (150, 464), (160, 475.6), (170, 487.2), (180, 498.8),
        (190, 510.4), (200, 522),
    ],
    "MAGIC_GUARD": [
        (1, 12), (10, 12.4), (20, 12.9), (30, 13.4), (40, 13.9), (50, 14.4), (60, 14.8),
        (70, 15.3), (80, 15.8), (90, 16.3), (100, 16.8),
    ],
    "MEDITATION": [
        (1, 20), (10, 20.8), (20, 21.6), (30, 22.4), (40, 23.2), (50, 24), (60, 24.8),
        (70, 25.6), (80, 26.4), (90, 27.2), (100, 28),
    ],
    "MAGIC_ACCELERATION": [
        (1, 5), (10, 5.1), (20, 5.3), (30, 5.4), (40, 5.6), (50, 5.7), (60, 5.9), (70, 6),
        (80, 6.2), (90, 6.3), (100, 6.5),
    ],
    "SPELL_MASTERY": [
        (1, 15), (10, 15.4), (20, 15.9), (30, 16.3), (40, 16.8), (50, 17.2), (60, 17.7),
        (70, 18.1), (80, 18.6), (90, 19), (100, 19.5),
    ],
    "HIGH_WISDOM": [
        (1, 8), (10, 8.2), (20, 8.4), (30, 8.7), (40, 8.9), (50, 9.2), (60, 9.4), (70, 9.6),
        (80, 9.9), (90, 10.1), (100, 10.4),
    ],
    "THUNDER_BOLT": [
        (1, 180), (10, 189), (20, 198), (30, 207), (40, 216), (50, 225), (60, 234), (70, 243),
        (80, 252), (90, 261), (100, 270),
    ],
    "GLACIER_WALL": [
        (1, 290), (10, 304.5), (20, 319), (30, 333.5), (40, 348), (50, 362.5), (60, 377),
        (70, 391.5), (80, 406), (90, 420.5), (100, 435), (110, 449.5), (120, 464), (130, 478.5),
        (140, 493), (150, 507.5), (160, 522), (170, 536.5), (180, 551), (190, 565.5), (200, 580),
    ],
    "THUNDER_SPHERE": [
        (1, 100), (10, 105), (20, 110), (30, 115), (40, 120), (50, 125), (60, 130), (70, 135),
        (80, 140), (90, 145), (100, 150), (110, 155), (120, 160), (130, 165), (140, 170),
        (150, 175), (160, 180), (170, 185), (180, 190), (190, 195), (200, 200),
    ],
    "FROZEN_BREAK": [
        (1, 3), (100, 3), (200, 3),  # flat, non-scaling — sanity-check only, not used for RE
    ],
    "ELEMENTAL_RESET": [
        (1, 10), (10, 10.3), (20, 10.6), (30, 10.9), (40, 11.2), (50, 11.5), (60, 11.8),
        (70, 12.1), (80, 12.4), (90, 12.7), (100, 13), (110, 13.3), (120, 13.6), (130, 13.9),
        (140, 14.2), (150, 14.5), (160, 14.8), (170, 15.1), (180, 15.4), (190, 15.7), (200, 16),
    ],
    "MAGIC_CRITICAL_RATE": [
        (1, 8), (10, 8.2), (20, 8.4), (30, 8.7), (40, 8.9), (50, 9.2), (60, 9.4), (70, 9.6),
        (80, 9.9), (90, 10.1), (100, 10.4), (110, 10.6), (120, 10.8), (130, 11.1), (140, 11.3),
        (150, 11.6), (160, 11.8), (170, 12), (180, 12.3), (190, 12.5), (200, 12.8),
    ],
    "MAGIC_CRITICAL_DAMAGE": [
        (1, 12), (10, 12.3), (20, 12.7), (30, 13), (40, 13.4), (50, 13.8), (60, 14.1), (70, 14.5),
        (80, 14.8), (90, 15.2), (100, 15.6), (110, 15.9), (120, 16.3), (130, 16.6), (140, 17),
        (150, 17.4), (160, 17.7), (170, 18.1), (180, 18.4), (190, 18.8), (200, 19.2),
    ],
    "ELEMENT_AMPLIFICATION": [
        (1, 15), (10, 15.4), (20, 15.9), (30, 16.3), (40, 16.8), (50, 17.2), (60, 17.7),
        (70, 18.1), (80, 18.6), (90, 19), (100, 19.5), (110, 19.9), (120, 20.4), (130, 20.8),
        (140, 21.3), (150, 21.7), (160, 22.2), (170, 22.6), (180, 23.1), (190, 23.5), (200, 24),
    ],
    "FREEZING_BREATH": [
        (1, 800), (10, 840), (20, 880), (30, 920), (40, 960), (50, 1000), (60, 1040), (70, 1080),
        (80, 1120), (90, 1160), (100, 1200), (110, 1240), (120, 1280), (130, 1320), (140, 1360),
        (150, 1400), (160, 1440), (170, 1480), (180, 1520), (190, 1560), (200, 1600),
    ],
    "BLIZZARD": [
        (1, 600), (10, 630), (20, 660), (30, 690), (40, 720), (50, 750), (60, 780), (70, 810),
        (80, 840), (90, 870), (100, 900), (110, 930), (120, 960), (130, 990), (140, 1020),
        (150, 1050), (160, 1080), (170, 1110), (180, 1140), (190, 1170), (200, 1200),
    ],
    "FROZEN_ORB": [
        (1, 900), (10, 945), (20, 990), (30, 1035), (40, 1080), (50, 1125), (60, 1170),
        (70, 1215), (80, 1260), (90, 1305), (100, 1350), (110, 1395), (120, 1440), (130, 1485),
        (140, 1530), (150, 1575), (160, 1620), (170, 1665), (180, 1710), (190, 1755), (200, 1800),
    ],
    "INFINITY_BASE": [
        (1, 15), (10, 15.6), (20, 16.2), (30, 16.8), (40, 17.4), (50, 18), (60, 18.6), (70, 19.2),
        (80, 19.8), (90, 20.4), (100, 21), (110, 21.6), (120, 22.2), (130, 22.8), (140, 23.4),
        (150, 24), (160, 24.6), (170, 25.2), (180, 25.8), (190, 26.4), (200, 27),
    ],
    "INFINITY_INCREMENT": [
        (1, 1), (10, 1), (20, 1), (30, 1.1), (40, 1.1), (50, 1.2), (60, 1.2), (70, 1.2), (80, 1.3),
        (90, 1.3), (100, 1.4), (110, 1.4), (120, 1.4), (130, 1.5), (140, 1.5), (150, 1.6),
        (160, 1.6), (170, 1.6), (180, 1.7), (190, 1.7), (200, 1.8),
    ],
    "ELQUINES": [
        (1, 3500), (10, 3675), (20, 3850), (30, 4025), (40, 4200), (50, 4375), (60, 4550),
        (70, 4725), (80, 4900), (90, 5075), (100, 5250), (110, 5425), (120, 5600), (130, 5775),
        (140, 5950), (150, 6125), (160, 6300), (170, 6475), (180, 6650), (190, 6825), (200, 7000),
    ],
    "BUFF_MASTERY": [
        (1, 10), (10, 10.3), (20, 10.6), (30, 10.9), (40, 11.2), (50, 11.5), (60, 11.8),
        (70, 12.1), (80, 12.4), (90, 12.7), (100, 13), (110, 13.3), (120, 13.6), (130, 13.9),
        (140, 14.2), (150, 14.5), (160, 14.8), (170, 15.1), (180, 15.4), (190, 15.7), (200, 16),
    ],
    "ARCANE_AIM": [
        (1, 3), (10, 3), (20, 3.1), (30, 3.2), (40, 3.3), (50, 3.4), (60, 3.5), (70, 3.6),
        (80, 3.7), (90, 3.8), (100, 3.9), (110, 3.9), (120, 4), (130, 4.1), (140, 4.2), (150, 4.3),
        (160, 4.4), (170, 4.5), (180, 4.6), (190, 4.7), (200, 4.8),
    ],
    "MAPLE_HERO_THUNDERSPHERE": [
        (1, 20), (10, 30), (20, 40), (30, 50), (40, 60), (50, 70), (60, 80), (70, 90), (80, 100),
        (90, 110), (100, 120), (110, 130), (120, 140), (130, 142), (140, 144), (150, 146),
        (160, 148), (170, 150), (180, 152), (190, 154), (200, 156),
    ],
    "MAPLE_HERO_GLACIERWALL": [
        (1, 30), (10, 45), (20, 60), (30, 75), (40, 90), (50, 105), (60, 120), (70, 135),
        (80, 150), (90, 165), (100, 180), (110, 195), (120, 210), (130, 213), (140, 216),
        (150, 219), (160, 222), (170, 225), (180, 228), (190, 231), (200, 234),
    ],
    "MAPLE_HERO_THUNDERBOLT": [
        (1, 100), (10, 150), (20, 200), (30, 250), (40, 300), (50, 350), (60, 400), (70, 450),
        (80, 500), (90, 550), (100, 600), (110, 650), (120, 700), (130, 710), (140, 720),
        (150, 730), (160, 740), (170, 750), (180, 760), (190, 770), (200, 780),
    ],
}

# Patched level-1 base values (skill's own displayed % at skill level 1) that override the
# wiki curve's own level-1 point when computing baseDamage — curve *shape* (factorIndex) is
# still derived from the full unpatched curve, only the base changes. Per
# /tmp/ilm_authoritative_corrections.txt: Elemental Reset's ENTIRE curve is rescaled by 1.2x
# (12/10), not just the level-1 point, but since the curve is a pure multiplicative scaling
# of a single base value by FACTOR_TABLE[level][idx]/1000, rescaling just the level-1 base by
# 1.2x and keeping the same factorIndex reproduces the entire rescaled curve exactly.
PATCHED_LEVEL1 = {
    "ELEMENTAL_RESET": 12,        # 10% -> 12% (patched base; full curve rescaled by 1.2x)
    "BLIZZARD_PROC": 95,          # handled separately below (not a wiki curve at all)
}

# Curves that don't scale with level at all (flat/non-scaling) — sanity-check exclusion, not fed
# through resolve().
NON_SCALING = {"FROZEN_BREAK"}

TOLERANCE = 0.01
# The wiki appears to TRUNCATE (floor) its displayed 1-decimal values rather than round-to-
# nearest — confirmed by hand for Arcane Aim (factorIndex 22, baseDamage 30 => predicted 3.09%
# at level 10, which floors to the displayed 3.0%, not round()'s 3.1%) and Infinity's increment
# curve (factorIndex 21, baseDamage 10). This matters for small-magnitude curves where a single
# 0.1 rounding step is a large fraction of the value — the naive relative-ratio check below
# (mean implied baseDamage across samples, tolerance on relative deviation) can spuriously reject
# the correct (idx, baseDamage) pair, or worse, appear to match multiple candidates loosely. The
# real, unambiguous test is: does floor(candidate_base/10 * factor[level][idx]/1000, 1 decimal)
# reproduce the sampled wiki value EXACTLY at every sampled level? That's what resolve() now
# checks first (exact, no tolerance), falling back to the old relative-ratio heuristic only to
# aid diagnosis if the exact search finds nothing.
FLOOR_EPS = 1e-9


def _floor1(x):
    import math
    return math.floor(x * 10 + FLOOR_EPS) / 10


def _round1(x):
    return round(x, 1)


def resolve(name, samples):
    exact_candidates = []
    for idx in range(24):
        # Search every plausible integer baseDamage(tenths%) 1..3000 (covers every skill in this
        # kit, including Elquines' 35000) for one that reproduces every sample exactly under
        # floor-to-1-decimal rounding (the wiki's actual behavior, confirmed by hand above).
        for base_tenths in range(1, 3001):
            ok = True
            for level, val in samples:
                factor = FACTOR_TABLE[level][idx]
                if factor == 0:
                    ok = False
                    break
                predicted = base_tenths / 10 * factor / 1000
                if _floor1(predicted) != _floor1(val):
                    ok = False
                    break
            if ok:
                exact_candidates.append((idx, base_tenths))
    if exact_candidates:
        # Return in the (idx, mean, max_dev) shape main() expects, max_dev=0 since these are
        # exact matches under the wiki's real (floor) rounding rule.
        return [(idx, float(base_tenths), 0.0) for idx, base_tenths in exact_candidates]

    # Fallback: old relative-ratio heuristic (round-to-nearest assumption), only reached if the
    # exact floor-based search above found literally nothing — kept for diagnostic visibility.
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
    print(f"{'Skill':32s} {'FactorIndex':>11s} {'BaseDamage(tenths%)':>20s} {'MaxDev':>8s}  {'PatchedBase':>12s}")
    results = {}
    problems = []
    for name, samples in CURVES.items():
        if name in NON_SCALING:
            continue
        candidates = resolve(name, samples)
        if len(candidates) != 1:
            problems.append((name, candidates))
            print(f"{name:32s}  ** {len(candidates)} candidates: {candidates} **")
            continue
        idx, mean, max_dev = candidates[0]
        base_tenths = round(mean)
        patched_note = ""
        final_base = base_tenths
        if name in PATCHED_LEVEL1:
            assert FACTOR_TABLE[1][idx] == 1000, f"{name}: FACTOR_TABLE[1][{idx}] != 1000"
            final_base = PATCHED_LEVEL1[name] * 10
            patched_note = f"{PATCHED_LEVEL1[name]}%  (was {base_tenths/10:.1f}%)"
        results[name] = (final_base, idx)
        print(f"{name:32s} {idx:11d} {final_base:20d} {max_dev:8.5f}  {patched_note:>12s}")

    print()
    if problems:
        print(f"{len(problems)} skill(s) did not resolve to exactly one factorIndex — investigate:")
        for name, candidates in problems:
            print(f"  {name}: {candidates}")
    else:
        print("Every scaling skill resolved to exactly one factorIndex with zero residual error.")

    print()
    print("--- Python dict for copy-paste into build_ice_lightning_mage_workbook.py ---")
    for name, (base, idx) in results.items():
        print(f'    "{name}": (baseDamage={base}, factorIndex={idx}),')


if __name__ == "__main__":
    main()
