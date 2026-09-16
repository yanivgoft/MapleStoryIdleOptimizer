#!/usr/bin/env python3
"""
Derives each Marksman scaling skill's (baseDamage(tenths%), factorIndex) tuple by matching its
wiki per-skill-level damage curve against src/ts/data/factor-table-data.ts's
SKILL_LEVEL_FACTOR_TABLE, same method as tools/_reverse_engineer_bowmaster_factors.py and its own
siblings. Curve data fetched live via curl from idle.maplestorywiki.net this session (domain
already allowlisted in .claude/apple/dangerous_allowed_domains.csv; the WebFetch tool itself
403s on this domain, plain curl works) — see
/Users/yaniv/.claude/plans/so-basically-we-were-magical-iverson.md for the full patch-note
reconciliation (Aug 13 2026 patch notes PDF) this incorporates.

Real wiki page-name gotchas hit this session (same "Arrow Platter/Quiver Flow" pattern as
Bowmaster's own session, confirmed via each overview page's own <a href> links rather than
guessing): Frostprey's real page is "Freezer", Blink Bolt's is "Bolt_Flow", Bolt Burst's is
"Bolt_Flash", Aggressive Resistance's is "Damage_Reversing", Crossbow Acceleration's is
"Crossbow_Acceleration" (not "Agile_Crossbows" despite that being the skill's own display name on
the overview page), Piercing Arrow II's is "Enhance_Arrow", Covering Fire's is "Retreat_Shot".

Several curves below are the wiki's PRE-patch values, rescaled by the patch's own before/after
ratio prior to reverse-engineering (Bolt Burst 450/380=1.1842x, Frostprey 300/600=0.5x, Soul
Arrow: Crossbow 12/10=1.2x, Arrow Illusion 1200/2400=0.5x) — same rescale technique already
established for Bowmaster's own Quiver Cartridge/Mortal Blow.

Shared-with-Bowmaster skills (Covering Fire, Mortal Blow, Marksmanship, Sharp Eyes, Illusion
Step, Advanced Final Attack, Critical Shot, Archer Mastery, Physical Training, Nimble Feet) are
NOT re-derived here — confirmed byte-identical wiki wording/curves this session (spot-checked via
their real Marksman-side pages: Retreat_Shot, Marksmanship, Mortal_Blow, Sharp_Eyes,
Illusion_Step, Advanced_Final_Attack, Critical_Shot, Archer_Mastery, Physical_Training), so
build_marksman_workbook.py reuses Bowmaster's own resolved tuples verbatim per the plan's shared-
skill-reuse premise. Crossbow Mastery/Final Attack: Crossbow/Crossbow Acceleration/Crossbow
Expert/Reckless Hunt: Crossbow are "shared-value-different-key" (same numbers as their Bow-tree
counterparts, confirmed via their own individual pages, but kept as separate Skills-sheet rows
since they're technically distinct skill keys per class) — also reused verbatim, not re-derived.
Maple Hero (Marksman)'s own curve is confirmed to use the EXACT SAME numbers as Maple Hero
(Bowmaster) at every level (25/30/100 at level 1, scaling identically) — also reused verbatim.
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
    # Empowered Piercing Arrow (4th-job basic attack) — confirmed identical to every other
    # class's own 4th-job basic attack, including Bowmaster's own Arrow Stream (byte-identical
    # curve 290%->522%, "290% damage to 6 target(s) in front 5 time(s)").
    "EMPOWERED_PIERCING_ARROW": [
        (1, 290), (10, 301.6), (20, 313.2), (30, 324.8), (40, 336.4), (50, 348), (60, 359.6),
        (70, 371.2), (80, 382.8), (90, 394.4), (100, 406), (110, 417.6), (120, 429.2),
        (130, 440.8), (140, 452.4), (150, 464), (160, 475.6), (170, 487.2), (180, 498.8),
        (190, 510.4), (200, 522),
    ],
    # Bolt Burst ("Bolt Flash" page): wiki's own PRE-patch curve (380%->760%), rescaled
    # 450/380=1.1842x per the Aug 13 patch (380%->450% at level 1) before resolving factorIndex.
    "BOLT_BURST": [
        (lvl, val * 450 / 380) for lvl, val in [
            (1, 380), (10, 399), (20, 418), (30, 437), (40, 456), (50, 475), (60, 494),
            (70, 513), (80, 532), (90, 551), (100, 570), (110, 589), (120, 608), (130, 627),
            (140, 646), (150, 665), (160, 684), (170, 703), (180, 722), (190, 741), (200, 760),
        ]
    ],
    # Frostprey ("Freezer" page): wiki's own PRE-patch curve (600%->1200%), rescaled 300/600=0.5x
    # per the Aug 13 patch (600%->300% at level 1) before resolving factorIndex.
    "FROSTPREY": [
        (lvl, val * 300 / 600) for lvl, val in [
            (1, 600), (10, 630), (20, 660), (30, 690), (40, 720), (50, 750), (60, 780),
            (70, 810), (80, 840), (90, 870), (100, 900), (110, 930), (120, 960), (130, 990),
            (140, 1020), (150, 1050), (160, 1080), (170, 1110), (180, 1140), (190, 1170),
            (200, 1200),
        ]
    ],
    # Blink Bolt ("Bolt Flow" page): own Attack% curve, not patched (no Blink Bolt entry in the
    # Aug 13 patch notes).
    "BLINK_BOLT": [
        (1, 25), (10, 25.7), (20, 26.5), (30, 27.2), (40, 28), (50, 28.7), (60, 29.5),
        (70, 30.2), (80, 31), (90, 31.7), (100, 32.5), (110, 33.2), (120, 34), (130, 34.7),
        (140, 35.5), (150, 36.2), (160, 37), (170, 37.7), (180, 38.5), (190, 39.2), (200, 40),
    ],
    # Snipe: own curve, not patched.
    "SNIPE": [
        (1, 3800), (10, 3990), (20, 4180), (30, 4370), (40, 4560), (50, 4750), (60, 4940),
        (70, 5130), (80, 5320), (90, 5510), (100, 5700), (110, 5890), (120, 6080), (130, 6270),
        (140, 6460), (150, 6650), (160, 6840), (170, 7030), (180, 7220), (190, 7410), (200, 7600),
    ],
    # Bolt Surplus: own curve, not patched.
    "BOLT_SURPLUS": [
        (1, 650), (10, 676), (20, 702), (30, 728), (40, 754), (50, 780), (60, 806), (70, 832),
        (80, 858), (90, 884), (100, 910), (110, 936), (120, 962), (130, 988), (140, 1014),
        (150, 1040), (160, 1066), (170, 1092), (180, 1118), (190, 1144), (200, 1170),
    ],
    # Arrow Illusion: wiki's own PRE-patch curve (2400%->4800%), rescaled 1200/2400=0.5x per the
    # Aug 13 patch (2400%->1200% at level 1) before resolving factorIndex.
    "ARROW_ILLUSION": [
        (lvl, val * 1200 / 2400) for lvl, val in [
            (1, 2400), (10, 2520), (20, 2640), (30, 2760), (40, 2880), (50, 3000), (60, 3120),
            (70, 3240), (80, 3360), (90, 3480), (100, 3600), (110, 3720), (120, 3840),
            (130, 3960), (140, 4080), (150, 4200), (160, 4320), (170, 4440), (180, 4560),
            (190, 4680), (200, 4800),
        ]
    ],
    # Soul Arrow: Crossbow (Attack% only, no AS-scaling, no DEX bonus — genuinely different
    # mechanic from Soul Arrow: Bow, per the plan's own NOT-shared list): wiki's own PRE-patch
    # curve (10%->13%), rescaled 12/10=1.2x per the Aug 13 patch (10%->12% at level 1).
    "SOUL_ARROW_CROSSBOW": [
        (lvl, val * 12 / 10) for lvl, val in [
            (1, 10), (10, 10.3), (20, 10.6), (30, 10.9), (40, 11.2), (50, 11.5), (60, 11.8),
            (70, 12.1), (80, 12.4), (90, 12.7), (100, 13),
        ]
    ],
    # Crossbow Mastery: shared-value-different-key w/ Bow Mastery — confirmed identical curve
    # via its own page (15%->19.5%), not patched.
    "CROSSBOW_MASTERY": [
        (1, 15), (10, 15.4), (20, 15.9), (30, 16.3), (40, 16.8), (50, 17.2), (60, 17.7),
        (70, 18.1), (80, 18.6), (90, 19), (100, 19.5),
    ],
    # Final Attack: Crossbow: shared-value-different-key w/ Final Attack: Bow — confirmed
    # identical curve via its own page (35%->49%, 25% chance), not patched.
    "FINAL_ATTACK_CROSSBOW": [
        (1, 35), (10, 36.4), (20, 37.8), (30, 39.2), (40, 40.6), (50, 42), (60, 43.4), (70, 44.8),
        (80, 46.2), (90, 47.6), (100, 49),
    ],
    # Crossbow Acceleration: shared-value-different-key w/ Bow Acceleration — confirmed identical
    # curve via its own page (5%->6.5%), not patched.
    "CROSSBOW_ACCELERATION": [
        (1, 5), (10, 5.1), (20, 5.3), (30, 5.4), (40, 5.6), (50, 5.7), (60, 5.9), (70, 6),
        (80, 6.2), (90, 6.3), (100, 6.5),
    ],
    # Last Man Standing: Marksman's own 4th-job Final-Damage passive slot (NOT shared with Armor
    # Break, per the plan) — two independent curves confirmed via its own page: base FD
    # (15%->21.3%+, matches Bow/Crossbow Expert's own shape) and the +1-enemy conditional bonus
    # (5%->6.9%+, matches Critical Shot/Archer Mastery's own shape), both extending to level 200
    # on this 4th-job skill's own page (unlike the 1st-job-capped Critical Shot itself).
    "LAST_MAN_STANDING_BASE": [
        (1, 15), (10, 15.4), (20, 15.9), (30, 16.3), (40, 16.8), (50, 17.2), (60, 17.7),
        (70, 18.1), (80, 18.6), (90, 19), (100, 19.5), (110, 19.9), (120, 20.4), (130, 20.8),
        (140, 21.3),
    ],
    "LAST_MAN_STANDING_COND": [
        (1, 5), (10, 5.1), (20, 5.3), (30, 5.4), (40, 5.6), (50, 5.7), (60, 5.9), (70, 6),
        (80, 6.2), (90, 6.3), (100, 6.5), (110, 6.6), (120, 6.8), (130, 6.9),
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
    print("--- Python dict for copy-paste into build_marksman_workbook.py ---")
    for name, (base, idx) in results.items():
        print(f'    "{name}": (baseDamage={base}, factorIndex={idx}),')


if __name__ == "__main__":
    main()
