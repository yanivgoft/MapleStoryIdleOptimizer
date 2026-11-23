#!/usr/bin/env python3
"""Check that the workbook-free stand-in of run_reference_marksman.py serves the verify script exactly the cells the REAL workbook holds (the shared
body is ``check_fake_common.py``; only the Inputs and CompanionsInput sheets of ``Marksman/Marksman-DPS-Calculator.xlsx`` are streamed).

    python3 tests/golden/check_marksman_fake.py            # check only
    python3 tests/golden/check_marksman_fake.py --write    # also write tests/golden/marksman_real_inputs.json (the 10 real columns as golden cases)
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check_fake_common  # noqa: E402
import run_reference_marksman as rr  # noqa: E402

CHECK = check_fake_common.Check(rr.REF, "marksman", "Marksman")
bm, ck = CHECK.bm, CHECK.ck


def check_data_sync():
    """engine/data/marksman.py vs the tables the builder exports (the verify script imports these from the builder, so they must agree) and vs the
    static numbers of the builder's SKILL_ROWS (job step, cooldown, hits, ICD, window, base damage, factor index, normal-monster targets)."""
    sys.path.insert(0, str(HERE.parents[1]))
    from engine.common import content
    from engine.data import marksman as D
    pairs = [("UNLOCK_LEVEL", D.UNLOCK_LEVEL, bm.UNLOCK_LEVEL), ("MAPLE_HERO_RATIOS", D.MAPLE_HERO_RATIOS, bm.MAPLE_HERO_RATIOS),
             ("STATUS_GROUPS", D.STATUS_GROUPS, bm.STATUS_GROUPS), ("STATUS_BUFFS", D.STATUS_BUFFS, bm.STATUS_BUFFS),
             ("STATUS_UNIFORM_ROWS", D.STATUS_UNIFORM_ROWS, bm.STATUS_UNIFORM_ROWS), ("STATUS_CAST_PREFIX", D.STATUS_CAST_PREFIX, bm.STATUS_CAST_PREFIX),
             ("STATUS_PHI_ROWS", D.STATUS_PHI_ROWS, bm.STATUS_PHI_ROWS), ("STATUS_FS_KEYS", D.STATUS_FS_KEYS, bm.STATUS_FS_KEYS),
             ("CDR_EXEMPT", D.CDR_EXEMPT, bm.CDR_EXEMPT_ROW_KEYS),
             # the three player stuns: (id, row, typ, dur, p, Lv mastery gate, periodic tick, periodic window); the builder omits tick/win for casts
             # (the verify script uses 1.0 / 0.0) and min_level for Frostprey (0)
             ("PLAYER_STUN", [(e["id"], e["key"], e["typ"], e["dur"], e["p"], e["min_level"], e["tick"], e["win"]) for e in D.PLAYER_STUN],
              [(e["id"], e["row"], e["typ"], e["dur"], e["p"], e.get("min_level", 0), e.get("tick", 1.0), e.get("win", 0.0))
               for e in bm.STATUS_PLAYER_STUN]),
             ("CONTENT_TYPES (as a set)", sorted(content.CONTENT_TYPES), sorted(bm.CONTENT_TYPES))]
    rows = {r[0]: r for r in bm.SKILL_ROWS}
    # SKILL_ROWS columns: key, name, jobstep, cooldown, costsAction, actionsPerCast, hits, icd, window, chance, rolls, baseDamage, factorIndex, scales,
    # mastery, boss mastery, normal mastery, normalMonsterTargets ...  Compare every static (non-formula) number of the rows the engine models.
    for key, t in list(D.DAMAGE_SKILLS.items()) + [("BOLT_SURPLUS", dict(step=D.BOLT_SURPLUS["step"], base=D.BOLT_SURPLUS["base"],
                                                                         fidx=D.BOLT_SURPLUS["fidx"]))]:
        r = rows[key]
        pairs.append((f"{key} step", t["step"], r[2]))
        pairs.append((f"{key} base", t["base"], r[11]))
        pairs.append((f"{key} fidx", t["fidx"], r[12]))
        if key in D.DAMAGE_SKILLS:
            if isinstance(r[3], (int, float)):
                pairs.append((f"{key} cooldown", t["cooldown"], r[3]))
            else:                                    # Frostprey: =IF(level>=104,60*0.6,60)
                pairs.append((f"{key} cooldown formula", f"=IF(Inputs!$B$3>={t['haste'][0]},{t['cooldown']}*{t['haste'][1]},{t['cooldown']})", r[3]))
            if isinstance(r[6], (int, float)):
                pairs.append((f"{key} hits", t["hits"], r[6]))
            pairs.append((f"{key} icd", t.get("icd", 0), r[7]))
            pairs.append((f"{key} window", t.get("window", 0), r[8]))
            if isinstance(r[17], (int, float)):
                pairs.append((f"{key} targets", t["targets"], r[17]))
            else:                                    # =3+IF(level>=78,2,0)
                (lvl_t, add_t), = t["extra_targets"]
                pairs.append((f"{key} targets formula", f"=3+IF(Inputs!$B$3>={lvl_t},{add_t},0)", r[17]))
    bs = D.BOLT_SURPLUS
    pairs.append(("BOLT_SURPLUS hits formula", f"=2+IF(Inputs!$B$3>={bs['hits'][1]},{bs['hits'][2]},0)", rows["BOLT_SURPLUS"][6]))
    pairs.append(("BOLT_SURPLUS targets formula", f"=3+IF(Inputs!$B$3>={bs['targets'][1]},{bs['targets'][2]},0)", rows["BOLT_SURPLUS"][17]))
    pairs.append(("BOLT_SURPLUS chance", bs["chance"] * 100, rows["BOLT_SURPLUS"][9]))
    bad = [name for name, a, b in pairs if a != b]
    for name in bad:
        print("DATA OUT OF SYNC:", name)
    return not bad


def pre_check():
    if not check_data_sync():
        sys.exit(1)
    print("OK: engine/data/marksman.py agrees with the builder's tables and SKILL_ROWS")


def main():
    CHECK.main(pre_check=pre_check)


if __name__ == "__main__":
    main()
