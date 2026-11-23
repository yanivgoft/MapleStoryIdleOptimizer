#!/usr/bin/env python3
"""Check that the workbook-free stand-in of run_reference_buccaneer.py serves the verify script exactly the cells the REAL workbook holds (the shared
body is ``check_fake_common.py``; only the Inputs and CompanionsInput sheets of ``Buccaneer/Buccaneer-DPS-Calculator.xlsx`` are streamed).

    python3 tests/golden/check_buccaneer_fake.py            # check only
    python3 tests/golden/check_buccaneer_fake.py --write    # also write tests/golden/buccaneer_real_inputs.json (the 10 real columns as golden cases)
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check_fake_common  # noqa: E402
import run_reference_buccaneer as rr  # noqa: E402

CHECK = check_fake_common.Check(rr.REF, "buccaneer", "Buccaneer")
bm, ck = CHECK.bm, CHECK.ck


def _chain(expr):
    """{level: raw tier value} out of a builder 'SUMPRODUCT((Inputs!$B$3>={a,b})*{x,y})' formula (0 / '' = no chain)."""
    if not isinstance(expr, str):
        return {}
    m = re.search(r">=\{([0-9,]+)\}\)\*\{([0-9,]+)\}", expr)
    if not m:
        return {}
    return dict(zip([int(x) for x in m.group(1).split(",")], [int(x) for x in m.group(2).split(",")]))


def _numbers(expr):
    return [int(x) for x in re.findall(r">=(\d+)", expr)] if isinstance(expr, str) else []


def check_data_sync():
    """engine/data/buccaneer.py vs the tables the builder exports (the verify script imports these from the builder, so they must agree) and vs the
    builder's Skills-sheet rows (SKILL_ROWS: job step / cooldown / base damage / factor index / targets / mastery chains / buff durations)."""
    sys.path.insert(0, str(HERE.parents[1]))
    from engine.data import buccaneer as D
    pairs = [("UNLOCK_LEVEL", D.UNLOCK_LEVEL, bm.UNLOCK_LEVEL), ("MAPLE_HERO_RATIOS", D.MAPLE_HERO_RATIOS, bm.MAPLE_HERO_RATIOS),
             ("STATUS_GROUPS", D.STATUS_GROUPS, bm.STATUS_GROUPS), ("STATUS_BUFFS", D.STATUS_BUFFS, bm.STATUS_BUFFS),
             ("STATUS_UNIFORM_ROWS", D.STATUS_UNIFORM_ROWS, bm.STATUS_UNIFORM_ROWS), ("STATUS_CAST_PREFIX", D.STATUS_CAST_PREFIX, bm.STATUS_CAST_PREFIX),
             ("STATUS_PHI_ROWS", D.STATUS_PHI_ROWS, bm.STATUS_PHI_ROWS), ("STATUS_FS_KEYS", D.STATUS_FS_KEYS, bm.STATUS_FS_KEYS),
             ("PLAYER_STUN", [(e["id"], e["key"], e["typ"], e["dur"], e["p"]) for e in D.PLAYER_STUN],
              [(e["id"], e["row"], e["typ"], e["dur"], e["p"]) for e in bm.STATUS_PLAYER_STUN]),
             ("NAUTILUS_TRIGGER_KEYS", D.NAUTILUS_TRIGGER_KEYS, bm.NAUTILUS_TRIGGER_KEYS),
             ("DPS_ROW_ORDER (builder row order restricted to damage rows)", D.DPS_ROW_ORDER, [k for k in bm.ROW_ORDER if k in D.DPS_ROW_ORDER]),
             ("SKILL_NAMES", D.SKILL_NAMES, {r[0]: r[1] for r in bm.SKILL_ROWS if r[0] in D.SKILL_NAMES}),
             ("CONTENT_TYPES (as a set)",) + D_content_types()]
    # builder's Skills sheet: (key, step, cooldown, hits, icd, window, base, fidx, scales, mastery chain, targets, buff duration)
    rows = {r[0]: r for r in bm.SKILL_ROWS}

    def row(k):
        r = rows[k]
        return dict(step=r[2], cooldown=r[3], hits=r[6], icd=r[7], window=r[8], chance=r[9], base=r[11], fidx=r[12], scales=r[13], mastery=r[14],
                    mastery_boss=r[15], targets=r[17], duration=r[19])

    for k, t in D.DAMAGE_SKILLS.items():
        r = row(k)
        pairs.append((f"{k} step/base/fidx/targets", (t["step"], t["base"], t["fidx"], t["targets"]), (r["step"], r["base"], r["fidx"], r["targets"])))
        pairs.append((f"{k} mastery chain", t["mastery"], _chain(r["mastery"])))
        if isinstance(t["cooldown"], int):
            pairs.append((f"{k} cooldown", t["cooldown"], r["cooldown"]))
        if isinstance(t["hits"], int):
            pairs.append((f"{k} hits", t["hits"], r["hits"]))
        if "icd" in t:
            pairs.append((f"{k} icd/window", (t["icd"], t["window"]), (r["icd"], r["window"])))
    r = row("OCTOPUNCH")
    pairs.append(("OCTOPUNCH cooldown formula", (D.OCTOPUNCH_COOLDOWN[0], D.OCTOPUNCH_COOLDOWN[1]), (16, _numbers(r["cooldown"])[0])))
    m = re.fullmatch(r'=(\d+)\+IF\(OR\(Inputs!\$B\$38="boss",Inputs!\$B\$38="pvp"\),(\d+),0\)', r["hits"])
    assert m, r["hits"]
    pairs.append(("OCTOPUNCH hits (boss/pvp, other)", D.DAMAGE_SKILLS["OCTOPUNCH"]["hits"][1:], (int(m.group(1)) + int(m.group(2)), int(m.group(1)))))
    assert "16*0.7" in r["cooldown"] and D.OCTOPUNCH_COOLDOWN == (16, 134, 0.7)
    # one-row buffs / passives: (D table, builder key)
    for name, t, key in [("MAPLE_HERO", D.MAPLE_HERO, "MAPLE_HERO_HELPER"), ("SERPENT_ASSAULT", D.SERPENT_ASSAULT, "SERPENT_ASSAULT"),
                         ("SERPENT_SCALE", D.SERPENT_SCALE, "SERPENT_SCALE_FD"), ("ROLL_OF_THE_DICE", D.ROLL_OF_THE_DICE, "ROLL_OF_THE_DICE_DICE"),
                         ("CROSSBONES", D.CROSSBONES, "CROSSBONES_FD"), ("TIME_LEAP", D.TIME_LEAP, "TIME_LEAP_FD"),
                         ("SPEED_INFUSION", D.SPEED_INFUSION, "SPEED_INFUSION"), ("NIMBLE_FEET", D.NIMBLE_FEET, "NIMBLE_FEET"),
                         ("GSS_II_FD", D.GSS_II_FD, "GSS_II_FD"), ("SSR_WEAKEN", D.SSR_WEAKEN, "SSR_WEAKEN"),
                         ("NAUTILUS_FINAL_ATTACK", D.NAUTILUS_FINAL_ATTACK, "NAUTILUS_FINAL_ATTACK")]:
        r = row(key)
        pairs.append((f"{name} base/fidx/step", (t["base"], t["fidx"], t["step"]), (r["base"], r["fidx"], r["step"])))
        if "cooldown" in t:
            pairs.append((f"{name} cooldown", t["cooldown"], r["cooldown"]))
        if "duration" in t:
            pairs.append((f"{name} duration", t["duration"], r["duration"]))
        if "gated" in t:
            pairs.append((f"{name} gated chain", t["gated"], _chain(r["mastery"])))
    pairs.append(("SERPENT_ASSAULT hits/targets", (D.SERPENT_ASSAULT["hits"], D.SERPENT_ASSAULT["targets"]), (rows["SERPENT_ASSAULT"][6], rows["SERPENT_ASSAULT"][17])))
    pairs.append(("NAUTILUS_FINAL_ATTACK chance/icd", (D.NAUTILUS_FINAL_ATTACK["chance"], D.NAUTILUS_FINAL_ATTACK["icd"]),
                  (row("NAUTILUS_FINAL_ATTACK")["chance"] / 100, row("NAUTILUS_FINAL_ATTACK")["icd"])))
    pairs.append(("ROLL_OF_THE_DICE scales / NIMBLE_FEET scales", (True, D.NIMBLE_FEET["scales"]), (row("ROLL_OF_THE_DICE_DICE")["scales"], row("NIMBLE_FEET")["scales"])))
    # Hook Bomber chains + level-gated hit / cooldown / target formulas
    r = row("HOOK_BOMBER")
    pairs.append(("HOOK_BOMBER base/fidx/step", (D.HOOK_BOMBER_BASE * 10, 21, 4), (r["base"], r["fidx"], r["step"])))
    pairs.append(("HOOK_BOMBER mastery chain", D.HOOK_BOMBER_MASTERY, _chain(r["mastery"])))
    pairs.append(("HOOK_BOMBER boss chain", D.HOOK_BOMBER_BOSS_MASTERY, _chain(r["mastery_boss"])))
    pairs.append(("HOOK_BOMBER hits level", D.HOOK_BOMBER_HITS[1], _numbers(r["hits"])[0]))
    r = row("SEA_SERPENT_BURST")
    pairs.append(("SSB gss1 level / bases / cooldown breakpoints / hits level / target breakpoints",
                  (D.GSS1_LEVEL, D.SEA_SERPENT_BURST["base"], [lv for lv, _ in D.SSB_COOLDOWN[1]], D.SSB_HITS[1], [lv for lv, _ in D.SSB_TARGETS[1]]),
                  (_numbers(r["step"])[0], tuple(int(x) for x in re.findall(r",(\d+),(\d+)\)", r["base"])[0])[::-1], _numbers(r["cooldown"]), _numbers(r["hits"])[0],
                  _numbers(rows["SEA_SERPENT_BURST"][17]))))
    pairs.append(("SSB fidx/mastery", (D.SEA_SERPENT_BURST["fidx"], D.SEA_SERPENT_BURST["mastery"]), (r["fidx"], _chain(r["mastery"]))))
    bad = [name for name, a, b in pairs if a != b]
    for name in bad:
        print("DATA OUT OF SYNC:", name)
        for n_, a, b in pairs:
            if n_ == name:
                print("    engine:", a, " builder:", b)
    return not bad


def D_content_types():
    from engine.common import content
    return sorted(content.CONTENT_TYPES), sorted(bm.CONTENT_TYPES)


def pre_check():
    if not check_data_sync():
        sys.exit(1)
    print("OK: engine/data/buccaneer.py agrees with the builder's tables")


def main():
    CHECK.main(pre_check=pre_check)


if __name__ == "__main__":
    main()
