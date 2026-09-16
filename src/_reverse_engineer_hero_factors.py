#!/usr/bin/env python3
"""
Derives each Hero scaling skill's (baseDamage(tenths%), factorIndex) tuple by matching its wiki
per-skill-level damage curve against src/ts/data/factor-table-data.ts's SKILL_LEVEL_FACTOR_TABLE,
same method as tools/_reverse_engineer_bowmaster_factors.py. Curve data fetched live this session
from idle.maplestorywiki.net (individual skill pages, text-red/text-green span values), not
transcribed from a screenshot — see build_hero_workbook.py's own module docstring for the full
wiki-vs-patch-notes reconciliation this incorporates.

Note: an earlier pass of this script's own extraction mixed up text-white (target/chance counts)
and text-red (the actual scaling %) values for Final_Attack specifically, since its wiki wording
puts a text-white "25% chance" before the text-red "35% damage" — always extract text-red
(or text-green, for Mastery-page-style buffs) specifically, never "the first number on the row".
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
    "RAGING_BLOW": [
        (1, 290), (10, 301.6), (20, 313.2), (30, 324.8), (40, 336.4), (50, 348), (60, 359.6),
        (70, 371.2), (80, 382.8), (90, 394.4), (100, 406), (110, 417.6), (120, 429.2),
        (130, 440.8), (140, 452.4), (150, 464), (160, 475.6), (170, 487.2), (180, 498.8),
        (190, 510.4), (200, 522),
    ],
    "PUNCTURE_MAIN": [
        (1, 900), (10, 945), (20, 990), (30, 1035), (40, 1080), (50, 1125), (60, 1170),
        (70, 1215), (80, 1260), (90, 1305), (100, 1350), (110, 1395), (120, 1440), (130, 1485),
        (140, 1530), (150, 1575), (160, 1620), (170, 1665), (180, 1710), (190, 1755), (200, 1800),
    ],
    "PUNCTURE_WOUND": [
        (1, 150), (10, 157.5), (20, 165), (30, 172.5), (40, 180), (50, 187.5), (60, 195),
        (70, 202.5), (80, 210), (90, 217.5), (100, 225), (110, 232.5), (120, 240), (130, 247.5),
        (140, 255), (150, 262.5), (160, 270), (170, 277.5), (180, 285), (190, 292.5), (200, 300),
    ],
    "PUNCTURE_BOSS_BONUS": [
        (1, 10), (10, 10.4), (20, 10.8), (30, 11.2), (40, 11.6), (50, 12), (60, 12.4), (70, 12.8),
        (80, 13.2), (90, 13.6), (100, 14), (110, 14.4), (120, 14.8), (130, 15.2), (140, 15.6),
        (150, 16), (160, 16.4), (170, 16.8), (180, 17.2), (190, 17.6), (200, 18),
    ],
    "ENHANCED_RAGING_BLOW": [
        (1, 550), (10, 577.5), (20, 605), (30, 632.5), (40, 660), (50, 687.5), (60, 715),
        (70, 742.5), (80, 770), (90, 797.5), (100, 825), (110, 852.5), (120, 880), (130, 907.5),
        (140, 935), (150, 962.5), (160, 990), (170, 1017.5), (180, 1045), (190, 1072.5), (200, 1100),
    ],
    "MAGIC_CRASH": [
        (1, 4800), (10, 5040), (20, 5280), (30, 5520), (40, 5760), (50, 6000), (60, 6240),
        (70, 6480), (80, 6720), (90, 6960), (100, 7200), (110, 7440), (120, 7680), (130, 7920),
        (140, 8160), (150, 8400), (160, 8640), (170, 8880), (180, 9120), (190, 9360), (200, 9600),
    ],
    "RUSH": [
        (1, 600), (10, 630), (20, 660), (30, 690), (50, 750), (60, 780), (70, 810), (80, 840),
        (90, 870), (100, 900), (110, 930), (120, 960), (130, 990), (140, 1020), (150, 1050),
        (160, 1080), (170, 1110), (180, 1140), (190, 1170), (200, 1200),
    ],
    "BEAM_BLADE": [
        (1, 250), (10, 262.5), (20, 275), (30, 287.5), (50, 312.5), (60, 325), (70, 337.5),
        (80, 350), (90, 362.5), (100, 375), (110, 387.5), (120, 400), (130, 412.5), (140, 425),
        (150, 437.5), (160, 450), (170, 462.5), (180, 475), (190, 487.5), (200, 500),
    ],
    "FLASH_SLASH": [
        # Wiki content bug: prose claims "+5%/level" but every sampled level (1-100) shows a
        # flat 350 — trust the table, non-scaling.
        (1, 350), (10, 350), (100, 350),
    ],
    "SCARING_SWORD_ATK_DOWN": [
        (1, 10), (10, 10.4), (20, 10.8), (30, 11.2), (50, 12), (200, 18),
    ],
    "SCARING_SWORD_DMG_TAKEN": [
        (1, 20), (10, 20.8), (20, 21.6), (30, 22.4), (50, 24), (200, 36),
    ],
    "FINAL_ATTACK": [
        (1, 35), (10, 36.4), (20, 37.8), (40, 40.6), (50, 42), (60, 43.4), (70, 44.8), (80, 46.2),
        (90, 47.6), (100, 49),
    ],
    "ADVANCED_FINAL_ATTACK": [
        (1, 500), (10, 520), (20, 540), (30, 560), (100, 700), (200, 900),
    ],
    "BRANDISH": [
        (1, 40), (10, 41.6), (20, 43.2), (40, 46.4), (50, 48), (100, 56),
    ],
    "SLASH_BLAST": [
        (1, 26), (10, 27), (30, 29.1), (40, 30.1), (50, 31.2), (100, 36.4),
    ],
    "INTREPID_SLASH": [
        (1, 80), (10, 83.2), (20, 86.4), (30, 89.6), (50, 96), (200, 144),
    ],
    "MAPLE_HERO_HERO": [
        # Beam Blade's own share (Rush 1.5x, Flash Slash 4x, ratios constant at every level) —
        # confirmed +80%-growth-reduction kink after level 120, same as every other class's Maple
        # Hero.
        (1, 20), (10, 30), (20, 40), (30, 50), (40, 60), (50, 70), (60, 80), (70, 90), (80, 100),
        (90, 110), (100, 120), (110, 130), (120, 140), (130, 142), (140, 144), (150, 146),
        (160, 148), (170, 150), (180, 152), (190, 154), (200, 156),
    ],
    "WEAPON_MASTERY": [
        (1, 15), (10, 15.4), (20, 15.9), (30, 16.3), (100, 19.5),
    ],
    "COMBAT_MASTERY_SKILL_DMG": [
        (1, 15), (10, 15.4), (20, 15.9), (200, 24),
    ],
    "COMBAT_MASTERY_MAX_DMG": [
        (1, 20), (10, 20.6), (20, 21.2), (200, 32),
    ],
    "POWER_STANCE_DMG_REDUCTION": [
        (1, 5), (10, 5.1), (20, 5.3), (200, 8),
    ],
    "POWER_STANCE_FD": [
        (1, 15), (10, 15.4), (20, 15.9), (200, 24),
    ],
    "ENRAGE_FD": [
        (1, 12), (10, 12.3), (200, 19.2),
    ],
    "ENRAGE_CRIT_DMG": [
        (1, 15), (10, 15.4), (200, 24),
    ],
    "COMBO_SYNERGY": [
        (1, 5), (10, 5.1), (200, 8),
    ],
    "COMBO_ATTACK": [
        (1, 4), (10, 4.1), (100, 5.2),
    ],
    "SPIRIT_BLADE_DMG_TAKEN": [
        (1, 8), (10, 8.3), (100, 11.2),
    ],
    "SPIRIT_BLADE_ATTACK": [
        (1, 10), (10, 10.4), (100, 14),
    ],
    "CHANCE_ATTACK_CRIT": [
        (1, 8), (10, 8.2), (200, 12.8),
    ],
    "CHANCE_ATTACK_STATUS_DMG": [
        (1, 12), (10, 12.3), (200, 19.2),
    ],
}

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
    print("--- Python dict for copy-paste into build_hero_workbook.py ---")
    for name, (base, idx) in results.items():
        print(f'    "{name}": (baseDamage={base}, factorIndex={idx}),')


if __name__ == "__main__":
    main()
