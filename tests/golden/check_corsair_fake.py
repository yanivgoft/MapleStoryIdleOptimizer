#!/usr/bin/env python3
"""Check that the workbook-free stand-in of run_reference_corsair.py serves the verify script exactly the cells the REAL workbook holds (the shared
body is ``check_fake_common.py``; only the Inputs and CompanionsInput sheets of ``Corsair/Corsair-DPS-Calculator.xlsx`` are streamed).

    python3 tests/golden/check_corsair_fake.py            # check only
    python3 tests/golden/check_corsair_fake.py --write    # also write tests/golden/corsair_real_inputs.json (the 10 real columns as golden cases)
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check_fake_common  # noqa: E402
import run_reference_corsair as rr  # noqa: E402

CHECK = check_fake_common.Check(rr.REF, "corsair", "Corsair")
bm, ck = CHECK.bm, CHECK.ck


def check_tables_against_builder():
    """engine/data/corsair.py's copies of the builder's tables (unlock levels, helper ratios, status-engine spec, quickdraw constants, player stun)."""
    sys.path.insert(0, str(HERE.parents[1]))
    from engine.data import corsair as D
    problems = []

    def same(name, mine, theirs):
        if mine != theirs:
            problems.append((name, mine, theirs))
    same("UNLOCK_LEVEL", D.UNLOCK_LEVEL, {k: v for k, v in bm.UNLOCK_LEVEL.items()})
    same("MAPLE_HERO_RATIOS", D.MAPLE_HERO_RATIOS, bm.MAPLE_HERO_RATIOS)
    same("AHOY_MATEYS_RATIOS", D.AHOY_MATEYS_RATIOS, bm.AHOY_MATEYS_RATIOS)
    same("STATUS_BUFFS", D.STATUS_BUFFS, bm.STATUS_BUFFS)
    same("STATUS_GROUPS", D.STATUS_GROUPS, bm.STATUS_GROUPS)
    same("STATUS_UNIFORM_ROWS", D.STATUS_UNIFORM_ROWS, bm.STATUS_UNIFORM_ROWS)
    same("STATUS_CAST_PREFIX", D.STATUS_CAST_PREFIX, bm.STATUS_CAST_PREFIX)
    same("STATUS_FS_KEYS", D.STATUS_FS_KEYS, bm.STATUS_FS_KEYS)
    same("STATUS_PHI_ROWS", D.STATUS_PHI_ROWS, bm.STATUS_PHI_ROWS)
    same("QD_COOLDOWN_KEYS", list(D.QD_COOLDOWN_KEYS), bm.QD_COOLDOWN_KEYS)
    same("QD_K", D.QD_K, bm.QD_K)
    same("PLAYER_STUN rows/ids/durations", [(e["id"], e["key"], e["typ"], e["dur"], e["p"]) for e in D.PLAYER_STUN],
         [(e["id"], e["row"], e["typ"], e["dur"], e["p"]) for e in bm.STATUS_PLAYER_STUN])
    same("DPS rows", D.DPS_ROW_ORDER + [], [k for k in bm.ROW if k in D.SKILL_NAMES])
    names = {r[0]: r[1] for r in bm.SKILL_ROWS}
    same("SKILL_NAMES", D.SKILL_NAMES, {k: names[k] for k in D.SKILL_NAMES})
    # skill rows: base damage / factor index / job step / cooldown / hit count / target count against the builder's Skills-sheet rows
    sr = {r[0]: r for r in bm.SKILL_ROWS}
    for key, t in D.DAMAGE_SKILLS.items():
        row = sr[key]
        for label, idx, mine in (("step", 2, t["step"]), ("cooldown", 3, t["cooldown"]), ("base", 11, t["base"]), ("fidx", 12, t["fidx"]),
                                   ("hits", 6, t["hits"])):
            theirs = row[idx]
            if isinstance(mine, tuple):
                continue          # level-gated (Broadside sustained): checked through the golden against the verify script
            if label == "cooldown" and (theirs in ("", None) or (isinstance(theirs, str) and theirs.startswith("="))):
                continue          # (a cell reference to another row's cooldown, e.g. All Aboard = Scurvy Summons)
            if mine != theirs:
                problems.append((f"{key}.{label}", mine, theirs))
    if problems:
        print("TABLE PROBLEMS:", *problems, sep="\n  ")
        sys.exit(1)
    print("OK: engine/data/corsair.py tables (UNLOCK_LEVEL, helper ratios, STATUS_*, Quickdraw, player stun, skill rows) equal the builder's")


def main():
    CHECK.main(pre_check=check_tables_against_builder)


if __name__ == "__main__":
    main()
