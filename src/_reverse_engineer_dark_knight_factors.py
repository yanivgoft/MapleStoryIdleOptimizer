#!/usr/bin/env python3
"""
Derives each Dark Knight scaling skill's (baseDamage(tenths%), factorIndex) tuple by matching its
wiki per-skill-level damage curve against src/ts/data/factor-table-data.ts's 24-column factor
table, same method as tools/_reverse_engineer_hero_factors.py. Curve data fetched live this
session from idle.maplestorywiki.net (individual skill pages) — see build_dark_knight_workbook.py's
own module docstring for the full wiki-vs-patch-notes reconciliation this incorporates.
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

# (level, value) samples fetched from each skill's own individual wiki page this session.
CURVES = {
    # Basic attack (4th job) — confirmed identical to every other class's own universal
    # 4th-job-basic-attack constant ("290% damage to 6 target(s) in front 5 time(s)").
    "DARK_IMPALE": [
        (1, 290), (10, 301.6), (20, 313.2), (30, 324.8), (40, 336.4), (50, 348), (60, 359.6),
        (70, 371.2), (80, 382.8), (90, 394.4), (100, 406), (110, 417.6),
    ],
    "SPEAR_SWEEP": [
        (1, 40), (10, 41.6), (20, 43.2), (30, 44.8), (40, 46.4), (50, 48), (60, 49.6), (70, 51.2),
        (80, 52.8), (90, 54.4), (100, 56),
    ],
    "LA_MANCHA_SPEAR": [
        (1, 80), (10, 83.2), (20, 86.4), (30, 89.6), (40, 92.8), (50, 96), (60, 99.2), (70, 102.4),
        (80, 105.6), (90, 108.8), (100, 112), (110, 115.2),
    ],
    "GUNGNIRS_DESCENT": [
        (1, 1800), (10, 1890), (20, 1980), (30, 2070), (40, 2160), (50, 2250), (60, 2340),
        (70, 2430), (80, 2520), (90, 2610), (100, 2700), (110, 2790), (120, 2880),
    ],
    "EVIL_EYE_SHOCK": [
        (1, 70), (10, 73.5), (20, 77), (30, 80.5), (40, 84), (50, 87.5), (60, 91), (70, 94.5),
    ],
    "EVIL_EYE_OF_DOMINANT": [
        (1, 60), (10, 62.4), (20, 64.8), (30, 67.2), (40, 69.6), (50, 72), (60, 74.4), (70, 76.8),
        (80, 79.2),
    ],
    "EVIL_EYE_SHOCK_ENH": [
        (1, 100), (10, 103), (20, 106), (30, 109), (40, 112), (50, 115), (60, 118), (70, 121),
        (80, 124),
    ],
    "HEX_OF_THE_EVIL_EYE": [
        (1, 15), (10, 15.4), (20, 15.9), (30, 16.3), (40, 16.8), (50, 17.2), (60, 17.7), (70, 18.1),
    ],
    "FINAL_PACT": [
        (1, 10), (10, 10.3), (20, 10.6), (30, 10.9), (40, 11.2),
    ],
    "REVENGE_OF_THE_EVIL_EYE": [
        (1, 850), (10, 892.5), (20, 935), (30, 977.5), (40, 1020), (50, 1062.5), (60, 1105),
    ],
    "BARRICADE_SKILL_DMG": [
        (1, 15), (10, 15.4), (20, 15.9), (30, 16.3), (40, 16.8), (50, 17.2), (60, 17.7), (70, 18.1),
        (80, 18.6), (90, 19), (100, 19.5), (110, 19.9), (120, 20.4), (130, 20.8),
    ],
    "BARRICADE_MAXDMG": [
        (1, 20), (10, 20.6), (20, 21.2), (30, 21.8), (40, 22.4), (50, 23), (60, 23.6), (70, 24.2),
        (80, 24.8), (90, 25.4), (100, 26), (110, 26.6), (120, 27.2), (130, 27.8),
    ],
    "DARK_RESONANCE": [
        (1, 30), (10, 31.2), (20, 32.4), (30, 33.6), (40, 34.8), (50, 36), (60, 37.2), (70, 38.4),
        (80, 39.6), (90, 40.8), (100, 42), (110, 43.2), (120, 44.4),
    ],
    "CROSS_OVER_CHAINS_ATK": [
        (1, 15), (10, 15.6), (20, 16.2), (30, 16.8), (40, 17.4), (50, 18), (60, 18.6),
    ],
    "CROSS_OVER_CHAINS_DMGTAKEN": [
        (1, 10), (10, 10.4), (20, 10.8), (30, 11.2), (40, 11.6), (50, 12),
    ],
    "HYPER_BODY_ATK": [
        (1, 12), (10, 12.4), (20, 12.9), (30, 13.4), (40, 13.9), (50, 14.4), (60, 14.8), (70, 15.3),
        (80, 15.8), (90, 16.3), (100, 16.8),
    ],
    "HYPER_BODY_DEF": [
        (1, 15), (10, 15.6), (20, 16.2), (30, 16.8), (40, 17.4), (50, 18), (60, 18.6), (70, 19.2),
        (80, 19.8), (90, 20.4), (100, 21),
    ],
    "EVIL_EYE_DMGTAKEN": [
        (1, 15), (10, 15.6), (20, 16.2), (30, 16.8), (40, 17.4), (50, 18), (60, 18.6), (70, 19.2),
    ],
    "LORD_OF_DARKNESS_CRITRATE_PREPATCH": [
        (1, 8), (10, 8.2), (20, 8.4), (30, 8.7), (40, 8.9), (50, 9.2), (60, 9.4),
    ],
    "LORD_OF_DARKNESS_CRITDMG_PREPATCH": [
        (1, 30), (10, 30.9), (20, 31.8), (30, 32.7), (40, 33.6), (50, 34.5), (60, 35.4),
    ],
    "WEAPON_MASTERY": [
        (1, 15), (10, 15.4), (20, 15.9), (30, 16.3), (100, 19.5),
    ],
    "IRON_WALL": [
        # Flat, non-scaling: identical text ("10% of Defense") at every sampled level 1-100.
        (1, 10), (10, 10), (100, 10),
    ],
}

# Extra sample points for Maple Hero (Dark Knight)'s own curve, resolved separately below via
# its own Evil Eye of Dominant share (1x, biggest) — full level 1-200 curve confirmed live.
MAPLE_HERO_DK = [
    (1, 40), (10, 60), (20, 80), (30, 100), (40, 120), (50, 140), (60, 160), (70, 180), (80, 200),
    (90, 220), (100, 240), (110, 260), (120, 280), (130, 284), (140, 288), (150, 292), (160, 296),
    (170, 300), (180, 304), (190, 308), (200, 312),
]

# Revenge of the Evil Eye's own Lv.138 "Spectral Shadows" mastery — a raw unevaluated wikitext
# formula on the live wiki page ({{#expr:2200*(1+x*0.005)}}%), resolved the same way as
# Marksman's own Snipe-Empowered mastery this session (x = character level).
SPECTRAL_SHADOWS_LEVELS = [1, 10, 20, 50, 100, 134, 150, 200]
SPECTRAL_SHADOWS_SAMPLES = [(l, 220 * (1 + l * 0.005)) for l in SPECTRAL_SHADOWS_LEVELS]

TOLERANCE = 0.02


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
    print(f"{'Skill':32s} {'FactorIndex':>11s} {'BaseDamage(tenths%)':>20s} {'MaxDev':>10s}")
    results = {}
    problems = []
    all_curves = dict(CURVES)
    all_curves["MAPLE_HERO_DK"] = MAPLE_HERO_DK
    all_curves["SPECTRAL_SHADOWS"] = SPECTRAL_SHADOWS_SAMPLES
    for name, samples in all_curves.items():
        candidates = resolve(name, samples)
        if len(candidates) != 1:
            problems.append((name, candidates))
            print(f"{name:32s}  ** {len(candidates)} candidates: {candidates} **")
            continue
        idx, mean, max_dev = candidates[0]
        base_tenths = round(mean)
        results[name] = (base_tenths, idx)
        print(f"{name:32s} {idx:11d} {base_tenths:20d} {max_dev:10.6f}")

    print()
    if problems:
        print(f"{len(problems)} skill(s) did not resolve to exactly one factorIndex:")
        for name, candidates in problems:
            print(f"  {name}: {candidates}")
    else:
        print("Every scaling skill resolved to exactly one factorIndex with acceptable residual error.")

    print()
    print("--- Python dict for copy-paste into build_dark_knight_workbook.py ---")
    for name, (base, idx) in results.items():
        print(f'    "{name}": (baseDamage={base}, factorIndex={idx}),')


if __name__ == "__main__":
    main()
