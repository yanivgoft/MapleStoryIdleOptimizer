#!/usr/bin/env python3
"""
Throwaway script (run once by hand, not part of the build pipeline) — derives each Night Lord
scaling skill's (baseDamage(tenths%), factorIndex) tuple by matching its wiki per-skill-level
damage curve against src/ts/data/factor-table-data.ts's SKILL_LEVEL_FACTOR_TABLE, exactly the
method described in the approved plan (vectorized-shimmying-pony.md) section 5:

  For each skill, for each candidate factorIndex 0-23:
    implied_base(L) = value[L] * 10 * 1000 / FACTOR_TABLE[L][idx]
  should be constant (within wiki-rounding tolerance) across every sampled level L for exactly
  one idx. That idx is FactorIndex; round(mean(implied_base)) is BaseDamage(tenths%).

Curve data below is transcribed directly from /tmp/night_lord_raw_data_full.txt (each skill's
individual wiki page "Skill Enhancement" table) — pre-patch values, since the patch only changes
each skill's *base* value (the level-1 point), not the scaling *shape*. Where the plan's patch
notes give a different level-1 base (e.g. Assassin's Mark 300%->190%, Dark Flare 400%->330%,
Adrenalin FD 10%->15%, Dark Harmony FD 15%->12%), the factorIndex is still derived from the
unpatched curve shape, then baseDamage is recomputed from the patched level-1 value using that
same factorIndex (since FACTOR_TABLE[1][idx] == 1000 for every idx 1-23, baseDamage(tenths%) is
just patched_level1_pct * 10 in that case).
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

# name -> list of (level, value%) sample points, transcribed verbatim from each skill's wiki page.
CURVES = {
    "SHOWDOWN": [
        (1, 290), (10, 301.6), (20, 313.2), (30, 324.8), (40, 336.4), (50, 348), (60, 359.6),
        (70, 371.2), (80, 382.8), (90, 394.4), (100, 406), (110, 417.6), (120, 429.2),
        (130, 440.8), (140, 452.4), (150, 464), (160, 475.6), (170, 487.2), (180, 498.8),
        (190, 510.4), (200, 522),
    ],
    "GUST_CHARM": [
        (1, 400), (10, 420), (20, 440), (30, 460), (40, 480), (50, 500), (60, 520), (70, 540),
        (80, 560), (90, 580), (100, 600),
    ],
    "MARK_OF_ASSASSIN": [
        (1, 300), (10, 312), (20, 324), (30, 336), (40, 348), (50, 360), (60, 372), (70, 384),
        (80, 396), (90, 408), (100, 420),
    ],
    "CRITICAL_THROW_RATE": [
        (1, 6), (10, 6.1), (20, 6.3), (30, 6.5), (40, 6.7), (50, 6.9), (60, 7.0), (70, 7.2),
        (80, 7.4), (90, 7.6), (100, 7.8),
    ],
    "CRITICAL_THROW_DMG": [
        (1, 10), (10, 10.3), (20, 10.6), (30, 10.9), (40, 11.2), (50, 11.5), (60, 11.8),
        (70, 12.1), (80, 12.4), (90, 12.7), (100, 13.0),
    ],
    "SHADOW_PARTNER": [
        (1, 84), (10, 87.3), (20, 90.7), (30, 94), (40, 97.4), (50, 100.8), (60, 104.1),
        (70, 107.5), (80, 110.8), (90, 114.2), (100, 117.6), (110, 120.9), (120, 124.3),
        (130, 127.6), (140, 131), (150, 134.4), (160, 137.7), (170, 141.1), (180, 144.4),
        (190, 147.8), (200, 151.2),
    ],
    "TRIPLE_THROW": [
        (1, 360), (10, 378), (20, 396), (30, 414), (40, 432), (50, 450), (60, 468), (70, 486),
        (80, 504), (90, 522), (100, 540), (110, 558), (120, 576), (130, 594), (140, 612),
        (150, 630), (160, 648), (170, 666), (180, 684), (190, 702), (200, 720),
    ],
    "ADRENALIN_FD": [
        (1, 10), (10, 10.3), (20, 10.6), (30, 10.9), (40, 11.2), (50, 11.5), (60, 11.8),
        (70, 12.1), (80, 12.4), (90, 12.7), (100, 13), (110, 13.3), (120, 13.6), (130, 13.9),
        (140, 14.2), (150, 14.5), (160, 14.8), (170, 15.1), (180, 15.4), (190, 15.7), (200, 16),
    ],
    "ADRENALIN_AS": [
        (1, 8), (10, 8.2), (20, 8.4), (30, 8.7), (40, 8.9), (50, 9.2), (60, 9.4), (70, 9.6),
        (80, 9.9), (90, 10.1), (100, 10.4), (110, 10.6), (120, 10.8), (130, 11.1), (140, 11.3),
        (150, 11.6), (160, 11.8), (170, 12), (180, 12.3), (190, 12.5), (200, 12.8),
    ],
    "DARK_FLARE": [
        (1, 400), (10, 420), (20, 440), (30, 460), (40, 480), (50, 500), (60, 520), (70, 540),
        (80, 560), (90, 580), (100, 600), (110, 620), (120, 640), (130, 660), (140, 680),
        (150, 700), (160, 720), (170, 740), (180, 760), (190, 780), (200, 800),
    ],
    "VENOM": [
        (1, 45), (10, 46.8), (20, 48.6), (30, 50.4), (40, 52.2), (50, 54), (60, 55.8), (70, 57.6),
        (80, 59.4), (90, 61.2), (100, 63), (110, 64.8), (120, 66.6), (130, 68.4), (140, 70.2),
        (150, 72), (160, 73.8), (170, 75.6), (180, 77.4), (190, 79.2), (200, 81),
    ],
    "DARK_SIGHT_CRIT": [
        (1, 6), (10, 6.2), (20, 6.4), (30, 6.7), (40, 6.9), (50, 7.2), (60, 7.4), (70, 7.6),
        (80, 7.9), (90, 8.1), (100, 8.4),
    ],
    "DARK_SIGHT_ATK": [
        (1, 10), (10, 10.4), (20, 10.8), (30, 11.2), (40, 11.6), (50, 12), (60, 12.4), (70, 12.8),
        (80, 13.2), (90, 13.6), (100, 14),
    ],
    "QUAD_STAR": [
        (1, 1150), (10, 1207.5), (20, 1265), (30, 1322.5), (40, 1380), (50, 1437.5), (60, 1495),
        (70, 1552.5), (80, 1610), (90, 1667.5), (100, 1725), (110, 1782.5), (120, 1840),
        (130, 1897.5), (140, 1955), (150, 2012.5), (160, 2070), (170, 2127.5), (180, 2185),
        (190, 2242.5), (200, 2300),
    ],
    "SUDDEN_RAID_BURST": [
        (1, 1400), (10, 1470), (20, 1540), (30, 1610), (40, 1680), (50, 1750), (60, 1820),
        (70, 1890), (80, 1960), (90, 2030), (100, 2100), (110, 2170), (120, 2240), (130, 2310),
        (140, 2380), (150, 2450), (160, 2520), (170, 2590), (180, 2660), (190, 2730), (200, 2800),
    ],
    "SUDDEN_RAID_DOT": [
        (1, 360), (10, 378), (20, 396), (30, 414), (40, 432), (50, 450), (60, 468), (70, 486),
        (80, 504), (90, 522), (100, 540), (110, 558), (120, 576), (130, 594), (140, 612),
        (150, 630), (160, 648), (170, 666), (180, 684), (190, 702), (200, 720),
    ],
    "FRAILTY_CURSE_DEBUFF": [
        (1, 18), (10, 18.7), (20, 19.4), (30, 20.1), (40, 20.8), (50, 21.6), (60, 22.3),
        (70, 23), (80, 23.7), (90, 24.4), (100, 25.2), (110, 25.9), (120, 26.6), (130, 27.3),
        (140, 28), (150, 28.8), (160, 29.5), (170, 30.2), (180, 30.9), (190, 31.6), (200, 32.4),
    ],
    "FRAILTY_CURSE_SELF_FD": [
        (1, 13), (10, 13.3), (20, 13.7), (30, 14.1), (40, 14.5), (50, 14.9), (60, 15.3),
        (70, 15.7), (80, 16.1), (90, 16.5), (100, 16.9), (110, 17.2), (120, 17.6), (130, 18),
        (140, 18.4), (150, 18.8), (160, 19.2), (170, 19.6), (180, 20), (190, 20.4), (200, 20.8),
    ],
    "SHADOW_SHIFTER_ATK": [
        (1, 10), (10, 10.3), (20, 10.6), (30, 10.9), (40, 11.2), (50, 11.5), (60, 11.8),
        (70, 12.1), (80, 12.4), (90, 12.7), (100, 13), (110, 13.3), (120, 13.6), (130, 13.9),
        (140, 14.2), (150, 14.5), (160, 14.8), (170, 15.1), (180, 15.4), (190, 15.7), (200, 16),
    ],
    "SHADOW_SHIFTER_COUNTER": [
        (1, 2500), (10, 2600), (20, 2700), (30, 2800), (40, 2900), (50, 3000), (60, 3100),
        (70, 3200), (80, 3300), (90, 3400), (100, 3500), (110, 3600), (120, 3700), (130, 3800),
        (140, 3900), (150, 4000), (160, 4100), (170, 4200), (180, 4300), (190, 4400), (200, 4500),
    ],
    "TOXIC_VENOM": [
        (1, 600), (10, 624), (20, 648), (30, 672), (40, 696), (50, 720), (60, 744), (70, 768),
        (80, 792), (90, 816), (100, 840), (110, 864), (120, 888), (130, 912), (140, 936),
        (150, 960), (160, 984), (170, 1008), (180, 1032), (190, 1056), (200, 1080),
    ],
    "NIGHT_LORDS_MARK": [
        (1, 300), (10, 312), (20, 324), (30, 336), (40, 348), (50, 360), (60, 372), (70, 384),
        (80, 396), (90, 408), (100, 420), (110, 432), (120, 444), (130, 456), (140, 468),
        (150, 480), (160, 492), (170, 504), (180, 516), (190, 528), (200, 540),
    ],
    "MAPLE_HERO_DARKFLARE": [
        (1, 15), (10, 22.5), (20, 30), (30, 37.5), (40, 45), (50, 52.5), (60, 60), (70, 67.5),
        (80, 75), (90, 82.5), (100, 90), (110, 97.5), (120, 105), (130, 106.5), (140, 108),
        (150, 109.5), (160, 111), (170, 112.5), (180, 114), (190, 115.5), (200, 117),
    ],
    "MAPLE_HERO_VENOM": [
        (1, 50), (10, 75), (20, 100), (30, 125), (40, 150), (50, 175), (60, 200), (70, 225),
        (80, 250), (90, 275), (100, 300), (110, 325), (120, 350), (130, 355), (140, 360),
        (150, 365), (160, 370), (170, 375), (180, 380), (190, 385), (200, 390),
    ],
    "MAPLE_HERO_SHADOWPARTNER": [
        (1, 50), (10, 75), (20, 100), (30, 125), (40, 150), (50, 175), (60, 200), (70, 225),
        (80, 250), (90, 275), (100, 300), (110, 325), (120, 350), (130, 355), (140, 360),
        (150, 365), (160, 370), (170, 375), (180, 380), (190, 385), (200, 390),
    ],
    "MAPLE_HERO_GUSTCHARM": [
        (1, 130), (10, 195), (20, 260), (30, 325), (40, 390), (50, 455), (60, 520), (70, 585),
        (80, 650), (90, 715), (100, 780), (110, 845), (120, 910), (130, 923), (140, 936),
        (150, 949), (160, 962), (170, 975), (180, 988), (190, 1001), (200, 1014),
    ],
    "CLAW_EXPERT_SKILLDMG": [
        (1, 15), (10, 15.4), (20, 15.9), (30, 16.3), (40, 16.8), (50, 17.2), (60, 17.7),
        (70, 18.1), (80, 18.6), (90, 19), (100, 19.5), (110, 19.9), (120, 20.4), (130, 20.8),
        (140, 21.3), (150, 21.7), (160, 22.2), (170, 22.6), (180, 23.1), (190, 23.5), (200, 24),
    ],
    "CLAW_EXPERT_MAXDMG": [
        (1, 20), (10, 20.6), (20, 21.2), (30, 21.8), (40, 22.4), (50, 23), (60, 23.6), (70, 24.2),
        (80, 24.8), (90, 25.4), (100, 26), (110, 26.6), (120, 27.2), (130, 27.8), (140, 28.4),
        (150, 29), (160, 29.6), (170, 30.2), (180, 30.8), (190, 31.4), (200, 32),
    ],
    "DARK_HARMONY_FD": [
        (1, 15), (10, 15.4), (20, 15.9), (30, 16.3), (40, 16.8), (50, 17.2), (60, 17.7),
        (70, 18.1), (80, 18.6), (90, 19), (100, 19.5), (110, 19.9), (120, 20.4), (130, 20.8),
        (140, 21.3), (150, 21.7), (160, 22.2), (170, 22.6), (180, 23.1), (190, 23.5), (200, 24),
    ],
    "DARK_HARMONY_MINDMG": [
        (1, 20), (10, 20.6), (20, 21.2), (30, 21.8), (40, 22.4), (50, 23), (60, 23.6), (70, 24.2),
        (80, 24.8), (90, 25.4), (100, 26), (110, 26.6), (120, 27.2), (130, 27.8), (140, 28.4),
        (150, 29), (160, 29.6), (170, 30.2), (180, 30.8), (190, 31.4), (200, 32),
    ],
    "ENVELOPING_DARKNESS": [
        (1, 18), (10, 18.5), (20, 19), (30, 19.6), (40, 20.1), (50, 20.7), (60, 21.2), (70, 21.7),
        (80, 22.3), (90, 22.8), (100, 23.4), (110, 23.9), (120, 24.4), (130, 25), (140, 25.5),
        (150, 26.1), (160, 26.6), (170, 27.1), (180, 27.7), (190, 28.2), (200, 28.8),
    ],
    "EXPERT_THROWING_STAR_HANDLING": [
        (1, 18), (10, 18.5), (20, 19), (30, 19.6), (40, 20.1), (50, 20.7), (60, 21.2), (70, 21.7),
        (80, 22.3), (90, 22.8), (100, 23.4), (110, 23.9), (120, 24.4), (130, 25), (140, 25.5),
        (150, 26.1), (160, 26.6), (170, 27.1), (180, 27.7), (190, 28.2), (200, 28.8),
    ],
    "PHYSICAL_TRAINING": [
        (1, 10), (10, 10.3), (20, 10.6), (30, 10.9), (40, 11.2), (50, 11.5), (60, 11.8),
        (70, 12.1), (80, 12.4), (90, 12.7), (100, 13),
    ],
    "CLAW_MASTERY": [
        (1, 15), (10, 15.4), (20, 15.9), (30, 16.3), (40, 16.8), (50, 17.2), (60, 17.7),
        (70, 18.1), (80, 18.6), (90, 19), (100, 19.5),
    ],
    "AGILE_CLAWS": [
        (1, 5), (10, 5.1), (20, 5.3), (30, 5.4), (40, 5.6), (50, 5.7), (60, 5.9), (70, 6),
        (80, 6.2), (90, 6.3), (100, 6.5),
    ],
}

# Patched level-1 base values (skill's own displayed % at skill level 1) that override the
# wiki curve's own level-1 point when computing baseDamage — the curve *shape* (factorIndex) is
# still derived from the full unpatched curve above, only the base changes.
PATCHED_LEVEL1 = {
    "MARK_OF_ASSASSIN": 190,      # 300% -> 190%
    "DARK_FLARE": 330,            # 400% -> 330%
    "ADRENALIN_FD": 15,           # 10% -> 15% (base; ratio/shape preserved)
    "DARK_HARMONY_FD": 12,        # 15% -> 12%
}

TOLERANCE = 0.01  # 1% relative tolerance — generous enough for 1-decimal wiki rounding on
# small-percentage curves (Critical Throw/Dark Sight's Crit Rate curves have very coarse
# 1-decimal rounding relative to their small absolute values); still tight enough that no
# skill below resolves to more than one candidate factorIndex.


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
    print(f"{'Skill':32s} {'FactorIndex':>11s} {'BaseDamage(tenths%)':>20s} {'MaxDev':>8s}  {'PatchedBase':>12s}")
    results = {}
    problems = []
    for name, samples in CURVES.items():
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
            # FACTOR_TABLE[1][idx] == 1000 for every idx 1-23 (verified below), so the patched
            # level-1 base is simply the patched %, in tenths.
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
    print("--- Python dict for copy-paste into build_night_lord_workbook.py ---")
    for name, (base, idx) in results.items():
        print(f'    "{name}": (baseDamage={base}, factorIndex={idx}),')


if __name__ == "__main__":
    main()
