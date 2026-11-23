#!/usr/bin/env python3
"""Check that the workbook-free stand-in of run_reference_paladin.py serves the verify script exactly the cells the REAL workbook holds (the shared
body is ``check_fake_common.py``; only the Inputs and CompanionsInput sheets of ``Paladin/Paladin-DPS-Calculator.xlsx`` are streamed).

    python3 tests/golden/check_paladin_fake.py            # check only
    python3 tests/golden/check_paladin_fake.py --write    # also write tests/golden/paladin_real_inputs.json (the 10 real columns as golden cases)
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check_fake_common  # noqa: E402
import run_reference_paladin as rr  # noqa: E402

CHECK = check_fake_common.Check(rr.REF, "paladin", "Paladin")
bm, ck = CHECK.bm, CHECK.ck


def check_data_sync():
    """engine/data/paladin.py vs the tables the builder exports (the verify script imports these from the builder, so they must agree)."""
    sys.path.insert(0, str(HERE.parents[1]))
    from engine.data import paladin as D
    pairs = [("UNLOCK_LEVEL", D.UNLOCK_LEVEL, bm.UNLOCK_LEVEL), ("MAPLE_HERO_RATIOS", D.MAPLE_HERO_RATIOS, bm.MAPLE_HERO_RATIOS),
             ("STATUS_GROUPS", D.STATUS_GROUPS, bm.STATUS_GROUPS), ("STATUS_BUFFS", D.STATUS_BUFFS, bm.STATUS_BUFFS),
             ("STATUS_UNIFORM_ROWS", D.STATUS_UNIFORM_ROWS, bm.STATUS_UNIFORM_ROWS), ("STATUS_CAST_PREFIX", D.STATUS_CAST_PREFIX, bm.STATUS_CAST_PREFIX),
             ("STATUS_PHI_ROWS", D.STATUS_PHI_ROWS, bm.STATUS_PHI_ROWS), ("STATUS_FS_KEYS", D.STATUS_FS_KEYS, bm.STATUS_FS_KEYS),
             ("STATUS_ROW_MIN_LEVEL", D.STATUS_ROW_MIN_LEVEL, bm.STATUS_ROW_MIN_LEVEL),
             ("COMBAT_ORDERS_ATTACK_PCT", D.COMBAT_ORDERS_ATTACK_PCT, bm.COMBAT_ORDERS_ATTACK_PCT),
             ("PLAYER_STUN", [(e["id"], e["key"], e["typ"], e["dur"], e["p"]) for e in D.PLAYER_STUN],
              [(e["id"], e["row"], e["typ"], e["dur"], e["p"]) for e in bm.STATUS_PLAYER_STUN]),
             ("CONTENT_TYPES (as a set)",) + D_content_types()]
    bad = [name for name, a, b in pairs if a != b]
    for name in bad:
        print("DATA OUT OF SYNC:", name)
    return not bad


def D_content_types():
    from engine.common import content
    return sorted(content.CONTENT_TYPES), sorted(bm.CONTENT_TYPES)


def pre_check():
    if not check_data_sync():
        sys.exit(1)
    print("OK: engine/data/paladin.py agrees with the builder's tables")


def main():
    CHECK.main(pre_check=pre_check)


if __name__ == "__main__":
    main()
