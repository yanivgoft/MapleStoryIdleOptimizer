#!/usr/bin/env python3
"""
Derives each Bowmaster scaling skill's (baseDamage(tenths%), factorIndex) tuple by matching its
wiki per-skill-level damage curve against src/ts/data/factor-table-data.ts's
SKILL_LEVEL_FACTOR_TABLE, same method as tools/_reverse_engineer_shadower_factors.py and its own
siblings. Curve data transcribed from idle.maplestorywiki.net's individual skill pages and the
Bowmaster/Skills overview page, fetched live via curl this session (domain already allowlisted in
.claude/apple/dangerous_allowed_domains.csv; the WebFetch tool itself 403s on this domain, plain
curl works) — see /Users/yaniv/.claude/plans/so-basically-we-were-magical-iverson.md for the full
patch-note reconciliation (Aug 13 2026 patch notes PDF) this incorporates. Several curves below
are the wiki's PRE-patch values, rescaled by the patch's own before/after ratio prior to
reverse-engineering (Quiver Cartridge 50/22=2.2727x, Enchanted Quiver 300/500=0.6x, Mortal Blow
12/10=1.2x) — same rescale technique already established for Shadower's own Blood Money.

Arrow Platter is deliberately NOT included here — idle.maplestorywiki.net/w/Arrow_Platter has a
confirmed wiki content bug (renders Wind Arrow II's own infobox/table instead of Arrow Platter's
own data, confirmed via the page's single-revision edit history), so no real curve could be
recovered this session. It is modeled non-scaling in the build script instead (FLAGGED).
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
    # Arrow Stream (4th-job basic attack) — confirmed identical to every other class's own
    # 4th-job basic attack ("290% damage to 6 target(s) in front 5 time(s)").
    "ARROW_STREAM": [
        (1, 290), (10, 301.6), (20, 313.2), (30, 324.8), (40, 336.4), (50, 348), (60, 359.6),
        (70, 371.2), (80, 382.8), (90, 394.4), (100, 406), (110, 417.6), (120, 429.2),
        (130, 440.8), (140, 452.4), (150, 464), (160, 475.6), (170, 487.2), (180, 498.8),
        (190, 510.4), (200, 522),
    ],
    "COVERING_FIRE": [
        (1, 250), (10, 262.5), (20, 275), (30, 287.5), (40, 300), (50, 312.5), (60, 325),
        (70, 337.5), (80, 350), (90, 362.5), (100, 375),
    ],
    # Quiver Cartridge: wiki's own PRE-patch curve (22%->30.8%, levels 1-100), rescaled 50/22
    # =2.2727x per the Aug 13 patch (22%->50% at level 1) before resolving factorIndex.
    "QUIVER_CARTRIDGE": [
        (lvl, val * 50 / 22) for lvl, val in [
            (1, 22), (10, 22.8), (20, 23.7), (30, 24.6), (40, 25.5), (50, 26.4), (60, 27.2),
            (70, 28.1), (80, 29), (90, 29.9), (100, 30.8),
        ]
    ],
    "PHOENIX": [
        (1, 600), (10, 630), (20, 660), (30, 690), (40, 720), (50, 750), (60, 780), (70, 810),
        (80, 840), (90, 870), (100, 900), (110, 930), (120, 960), (130, 990), (140, 1020),
        (150, 1050), (160, 1080), (170, 1110), (180, 1140), (190, 1170), (200, 1200),
    ],
    # Flash Mirage's own damage% is confirmed non-scaling (constant 5% across every sampled
    # level 1-200 on the wiki) — not resolved here, hardcoded factorIndex=0/baseDamage=50 in the
    # build script directly.
    # Enchanted Quiver (helper row): wiki's own PRE-patch curve (500%->900%), rescaled 300/500
    # =0.6x per the Aug 13 patch (500%->300% at level 1) before resolving factorIndex.
    "ENCHANTED_QUIVER": [
        (lvl, val * 300 / 500) for lvl, val in [
            (1, 500), (10, 520), (20, 540), (30, 560), (40, 580), (50, 600), (60, 620),
            (70, 640), (80, 660), (90, 680), (100, 700), (110, 720), (120, 740), (130, 760),
            (140, 780), (150, 800), (160, 820), (170, 840), (180, 860), (190, 880), (200, 900),
        ]
    ],
    "FLASH_MIRAGE_II": [
        (1, 400), (10, 416), (20, 432), (30, 448), (40, 464), (50, 480), (60, 496), (70, 512),
        (80, 528), (90, 544), (100, 560), (110, 576), (120, 592), (130, 608), (140, 624),
        (150, 640), (160, 656), (170, 672), (180, 688), (190, 704), (200, 720),
    ],
    "MARKSMANSHIP": [
        (1, 20), (10, 20.6), (20, 21.2), (30, 21.8), (40, 22.4), (50, 23), (60, 23.6),
        (70, 24.2), (80, 24.8), (90, 25.4), (100, 26), (110, 26.6), (120, 27.2), (130, 27.8),
        (140, 28.4), (150, 29), (160, 29.6), (170, 30.2), (180, 30.8), (190, 31.4), (200, 32),
    ],
    "ILLUSION_STEP": [
        (1, 14), (10, 14.4), (20, 14.8), (30, 15.2), (40, 15.6), (50, 16.1), (60, 16.5),
        (70, 16.9), (80, 17.3), (90, 17.7), (100, 18.2), (110, 18.6), (120, 19), (130, 19.4),
        (140, 19.8), (150, 20.3), (160, 20.7), (170, 21.1), (180, 21.5), (190, 21.9), (200, 22.4),
    ],
    "SHARP_EYES_CRITDMG": [
        (1, 40), (10, 41.6), (20, 43.2), (30, 44.8), (40, 46.4), (50, 48), (60, 49.6),
        (70, 51.2), (80, 52.8), (90, 54.4), (100, 56), (110, 57.6), (120, 59.2), (130, 60.8),
        (140, 62.4), (150, 64), (160, 65.6), (170, 67.2), (180, 68.8), (190, 70.4), (200, 72),
    ],
    # Mortal Blow: wiki's own PRE-patch curve (10%->16%), rescaled 12/10=1.2x per the Aug 13
    # patch (10%->12% at level 1) before resolving factorIndex.
    "MORTAL_BLOW": [
        (lvl, val * 12 / 10) for lvl, val in [
            (1, 10), (10, 10.3), (20, 10.6), (30, 10.9), (40, 11.2), (50, 11.5), (60, 11.8),
            (70, 12.1), (80, 12.4), (90, 12.7), (100, 13), (110, 13.3), (120, 13.6), (130, 13.9),
            (140, 14.2), (150, 14.5), (160, 14.8), (170, 15.1), (180, 15.4), (190, 15.7), (200, 16),
        ]
    ],
    "ADVANCED_FINAL_ATTACK": [
        (1, 500), (10, 520), (20, 540), (30, 560), (40, 580), (50, 600), (60, 620), (70, 640),
        (80, 660), (90, 680), (100, 700), (110, 720), (120, 740), (130, 760), (140, 780),
        (150, 800), (160, 820), (170, 840), (180, 860), (190, 880), (200, 900),
    ],
    "FINAL_ATTACK_BOW": [
        (1, 35), (10, 36.4), (20, 37.8), (30, 39.2), (40, 40.6), (50, 42), (60, 43.4), (70, 44.8),
        (80, 46.2), (90, 47.6), (100, 49),
    ],
    "CRITICAL_SHOT": [
        (1, 5), (10, 5.1), (20, 5.3), (30, 5.4), (40, 5.6), (50, 5.7), (60, 5.9), (70, 6),
        (80, 6.2), (90, 6.3), (100, 6.5),
    ],
    "ARCHER_MASTERY_AS": [
        (1, 5), (10, 5.1), (20, 5.3), (30, 5.4), (40, 5.6), (50, 5.7), (60, 5.9), (70, 6),
        (80, 6.2), (90, 6.3), (100, 6.5),
    ],
    "BOW_ACCELERATION": [
        (1, 5), (10, 5.1), (20, 5.3), (30, 5.4), (40, 5.6), (50, 5.7), (60, 5.9), (70, 6),
        (80, 6.2), (90, 6.3), (100, 6.5),
    ],
    "PHYSICAL_TRAINING": [
        (1, 10), (10, 10.3), (20, 10.6), (30, 10.9), (40, 11.2), (50, 11.5), (60, 11.8),
        (70, 12.1), (80, 12.4), (90, 12.7), (100, 13),
    ],
    "BOW_MASTERY": [
        (1, 15), (10, 15.4), (20, 15.9), (30, 16.3), (40, 16.8), (50, 17.2), (60, 17.7),
        (70, 18.1), (80, 18.6), (90, 19), (100, 19.5),
    ],
    "EXTREME_ARCHERY_BOW": [
        (1, 15), (10, 15.4), (20, 15.9), (30, 16.3), (40, 16.8), (50, 17.2), (60, 17.7),
        (70, 18.1), (80, 18.6), (90, 19), (100, 19.5), (110, 19.9), (120, 20.4), (130, 20.8),
        (140, 21.3), (150, 21.7), (160, 22.2), (170, 22.6), (180, 23.1), (190, 23.5), (200, 24),
    ],
    "ARMOR_BREAK": [
        (1, 10), (10, 10.3), (20, 10.6), (30, 10.9), (40, 11.2), (50, 11.5), (60, 11.8),
        (70, 12.1), (80, 12.4), (90, 12.7), (100, 13), (110, 13.3), (120, 13.6), (130, 13.9),
        (140, 14.2), (150, 14.5), (160, 14.8), (170, 15.1), (180, 15.4), (190, 15.7), (200, 16),
    ],
    "BOW_EXPERT_SKILL": [
        (1, 15), (10, 15.4), (20, 15.9), (30, 16.3), (40, 16.8), (50, 17.2), (60, 17.7),
        (70, 18.1), (80, 18.6), (90, 19), (100, 19.5), (110, 19.9), (120, 20.4), (130, 20.8),
        (140, 21.3), (150, 21.7), (160, 22.2), (170, 22.6), (180, 23.1), (190, 23.5), (200, 24),
    ],
    "BOW_EXPERT_MAXDMG": [
        (1, 20), (10, 20.6), (20, 21.2), (30, 21.8), (40, 22.4), (50, 23), (60, 23.6), (70, 24.2),
        (80, 24.8), (90, 25.4), (100, 26), (110, 26.6), (120, 27.2), (130, 27.8), (140, 28.4),
        (150, 29), (160, 29.6), (170, 30.2), (180, 30.8), (190, 31.4), (200, 32),
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
    print("--- Python dict for copy-paste into build_bowmaster_workbook.py ---")
    for name, (base, idx) in results.items():
        print(f'    "{name}": (baseDamage={base}, factorIndex={idx}),')


if __name__ == "__main__":
    main()
