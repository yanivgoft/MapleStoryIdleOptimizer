#!/usr/bin/env python3
"""Check that the workbook-free stand-in of run_reference_shadower.py serves the verify script exactly the cells the REAL workbook holds (the shared
body is ``check_fake_common.py``; only the Inputs and CompanionsInput sheets of ``Shadower/Shadower-DPS-Calculator.xlsx`` are streamed).

    python3 tests/golden/check_shadower_fake.py            # check only
    python3 tests/golden/check_shadower_fake.py --write    # also write tests/golden/shadower_real_inputs.json (the 10 real columns as golden cases)
"""
import ast
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check_fake_common  # noqa: E402
import run_reference_shadower as rr  # noqa: E402

CHECK = check_fake_common.Check(rr.REF, "shadower", "Shadower")
bm, ck = CHECK.bm, CHECK.ck


def _chain(expr):
    """{level: raw tier value} out of a builder 'SUMPRODUCT((Inputs!$B$3>={a,b})*{x,y})' formula (0 / '' = no chain)."""
    if not isinstance(expr, str):
        return {}
    m = re.search(r">=\{([0-9,]+)\}\)\*\{([0-9,]+)\}", expr)
    if not m:
        return {}
    return dict(zip([int(x) for x in m.group(1).split(",")], [int(x) for x in m.group(2).split(",")]))


def _verify_set_literal(name):
    """The set literal ``name = {...}`` of the verify script's source (parsed, not executed)."""
    m = re.search(rf"^{name} = (\{{[^}}]*\}})", rr.REF._SOURCE, re.M)
    assert m, name
    return ast.literal_eval(m.group(1))


def _if_formula(text):
    """'=IF(Inputs!$B$3>=94,45*0.7,45)' -> (94, value below, value from the level); the two branches may be simple products like 45*0.7 (evaluated
    with Python's own float arithmetic, exactly like the verify script's literals)."""
    m = re.fullmatch(r"=IF\(Inputs!\$B\$3>=(\d+),([0-9.*]+),([0-9.*]+)\)", text)
    assert m, text
    num = lambda x: eval(x, {"__builtins__": {}})   # digits, '.', '*' only (matched above)
    return int(m.group(1)), num(m.group(3)), num(m.group(2))


def check_data_sync(ns):
    """engine/data/shadower.py vs the tables the builder exports (the verify script imports these from the builder, so they must agree), vs the
    verify script's own tables (``ns`` = its namespace after a run) and vs the static numbers of the builder's SKILL_ROWS (job step / cooldown /
    hits / ICD / window / base damage / factor index / scaling / targets / mastery chains / buff durations / proc chances)."""
    sys.path.insert(0, str(HERE.parents[1]))
    from engine.common import content
    from engine.data import shadower as D
    pairs = [("UNLOCK_LEVEL", D.UNLOCK_LEVEL, bm.UNLOCK_LEVEL), ("UNLOCK_LEVEL vs verify", D.UNLOCK_LEVEL, ns["UNLOCK_LEVEL"]),
             ("MAPLE_HERO_SHADOWER_RATIOS", D.MAPLE_HERO_SHADOWER_RATIOS, bm.MAPLE_HERO_SHADOWER_RATIOS),
             ("STATUS_GROUPS", D.STATUS_GROUPS, bm.STATUS_GROUPS), ("STATUS_BUFFS", D.STATUS_BUFFS, bm.STATUS_BUFFS),
             ("STATUS_UNIFORM_ROWS", D.STATUS_UNIFORM_ROWS, bm.STATUS_UNIFORM_ROWS),
             ("STATUS_CAST_PREFIX (items, in order)", list(D.STATUS_CAST_PREFIX.items()), list(bm.STATUS_CAST_PREFIX.items())),
             ("STATUS_PHI_ROWS", D.STATUS_PHI_ROWS, bm.STATUS_PHI_ROWS), ("STATUS_FS_KEYS", D.STATUS_FS_KEYS, bm.STATUS_FS_KEYS),
             ("CDR_EXEMPT", D.CDR_EXEMPT, bm.CDR_EXEMPT_ROW_KEYS), ("CDR_EXEMPT vs verify", set(D.CDR_EXEMPT), ns["CDR_EXEMPT"]),
             # the player's stun: the builder carries (id, row, typ, dur, p); the verify script's own table (cd, min_level, tick, win) must equal ours exactly
             ("PLAYER_STUN vs builder", [(e["id"], e["key"], e["typ"], e["dur"], e["p"]) for e in D.PLAYER_STUN],
              [(e["id"], e["row"], e["typ"], e["dur"], e["p"]) for e in bm.STATUS_PLAYER_STUN]),
             ("PLAYER_STUN vs verify", D.PLAYER_STUN, ns["PLAYER_STUN"]),
             ("DPS_ROW_ORDER (verify skill_dps order)", D.DPS_ROW_ORDER, list(ns["skill_dps"])),
             ("SKILL_NAMES", D.SKILL_NAMES, {r[0]: r[1] for r in bm.SKILL_ROWS if r[0] in D.SKILL_NAMES}),
             ("CONTENT_TYPES (as a set)", sorted(content.CONTENT_TYPES), sorted(bm.CONTENT_TYPES))]
    # the Toxic Venom trigger set: same members as the verify script's set literal ...
    pairs.append(("TRIGGERS_TOXIC_VENOM members", set(D.TRIGGERS_TOXIC_VENOM), _verify_set_literal("TRIGGERS_TOXIC_VENOM")))
    pairs.append(("TRIGGERS_TOXIC_VENOM has no duplicates", len(D.TRIGGERS_TOXIC_VENOM), len(set(D.TRIGGERS_TOXIC_VENOM))))
    # ... and our fixed summation order is the literal's iteration order under PYTHONHASHSEED=0 (the seed the golden is generated with)
    lit = re.search(r"^TRIGGERS_TOXIC_VENOM = (\{[^}]*\})", rr.REF._SOURCE, re.M).group(1)
    out = subprocess.run([sys.executable, "-c", f"print(list({lit}))"], env={"PYTHONHASHSEED": "0", "PATH": ""}, capture_output=True, text=True, check=True).stdout
    pairs.append(("TRIGGERS_TOXIC_VENOM order == set iteration order under PYTHONHASHSEED=0", D.TRIGGERS_TOXIC_VENOM, ast.literal_eval(out.strip())))

    rows = {r[0]: r for r in bm.SKILL_ROWS}
    # SKILL_ROWS columns: 0 key, 1 name, 2 jobstep, 3 cooldown, 4 costsAction, 5 actionsPerCast, 6 hits, 7 icd, 8 window, 9 chance, 10 rolls, 11 baseDamage,
    # 12 factorIndex, 13 scales, 14 mastery chain, 15 boss mastery chain, 16 normal mastery, 21 target increase, 22 normalMonsterTargets, 23 buff target,
    # 24 buff duration, 25 triggersToxicVenom
    IF = lambda lv, a, b: f"=IF(Inputs!$B$3>={lv},{a},{b})"
    for key, t in D.DAMAGE_SKILLS.items():
        r = rows[key]
        pairs.append((f"{key} step", t["step"], r[2]))
        pairs.append((f"{key} costs_action", t["costs_action"], r[4]))
        if key != "ASSASSINATE":
            pairs.append((f"{key} base/fidx", (t["base"], t["fidx"]), (r[11], r[12])))
            pairs.append((f"{key} mastery chain", t["mastery"], _chain(r[14])))
        else:
            a = D.ASSASSINATE
            pairs.append((f"{key} base/fidx", (a["base"], a["fidx"]), (r[11], r[12])))
            pairs.append((f"{key} mastery chain (none: the Lv134 +50 is a fold)", {}, _chain(r[14])))
            note = r[29]
            pairs.append((f"{key} finisher / fold / Murderous Intent are in the builder's note",
                          (True, True, True), (f"factorIndex {a['finisher_fidx']}, baseDamage {a['finisher_base']} tenths%" in note,
                                               f"Mastery Lv.{a['fold'][0]} 'Assassinate - Damage' +{a['fold'][1]}%" in note,
                                               "50% average multiplier" in note and "Murderous Intent" in note)))
        for field, col in (("cooldown", 3), ("hits", 6), ("icd", 7)):
            spec = t.get(field)
            if spec is None:
                if field == "icd":
                    pairs.append((f"{key} icd", 0, r[7]))
                continue
            if isinstance(spec, tuple):
                pairs.append((f"{key} {field} formula (level, below, from level)", (spec[1], spec[0], spec[2]), _if_formula(r[col])))
            elif field == "cooldown" and key in ("SUDDEN_RAID_DOT", "BLOOD_MONEY"):
                sibling = "SUDDEN_RAID_BURST" if key == "SUDDEN_RAID_DOT" else "MESO_EXPLOSION"
                pairs.append((f"{key} cooldown = the sibling's own live cell ({sibling})", (spec, D.DAMAGE_SKILLS[sibling]["cooldown"]),
                              (D.DAMAGE_SKILLS[sibling]["cooldown"], rows[sibling][3])))
                pairs.append((f"{key} cooldown formula text", getattr(bm, "_SUDDEN_RAID_DOT_COOLDOWN" if key == "SUDDEN_RAID_DOT" else "_BLOOD_MONEY_COOLDOWN"), r[3]))
            else:
                pairs.append((f"{key} {field}", spec, r[col]))
        if "window" in t:
            pairs.append((f"{key} window", t["window"], r[8]))
        else:
            pairs.append((f"{key} window", 0, r[8]))
        if isinstance(t["targets"], int):
            pairs.append((f"{key} targets", t["targets"], r[22]))
        else:
            pairs.append((f"{key} targets (model-computed stack average: blank in the builder)", "", r[22]))
    mult = D.BLOOD_MONEY_TARGET_MULT
    pairs.append(("BLOOD_MONEY stack-to-target multiplier formula", f"=IF(Inputs!$B$3>={mult[0][0]},{mult[0][1]},IF(Inputs!$B$3>={mult[1][0]},{mult[1][1]},1))",
                  rows["BLOOD_MONEY"][21]))
    pairs.append(("MESO_EXPLOSION cooldown = D.MESO_EXPLOSION_COOLDOWN", D.MESO_EXPLOSION_COOLDOWN, rows["MESO_EXPLOSION"][3]))
    # Cruel Stab: base 290 / factor 21 (the universal 4th-job basic attack, not in the row: '' in the builder), chains, hit and target formulas
    r = rows["CRUEL_STAB"]
    pairs.append(("CRUEL_STAB mastery chain", D.CRUEL_STAB_MASTERY, _chain(r[14])))
    pairs.append(("CRUEL_STAB boss mastery chain", D.CRUEL_STAB_BOSS_MASTERY, _chain(r[15])))
    h0, hl, h1 = D.CRUEL_STAB_HITS
    pairs.append(("CRUEL_STAB hits formula", IF(hl, h1, h0), r[6]))
    pairs.append(("CRUEL_STAB targets formula", f"={D.CRUEL_STAB_TARGET_BASE}+Inputs!$B${bm.IN['basic_attack_target_increase']}", r[22]))
    pairs.append(("CRUEL_STAB base 290 / fidx 21 in the builder's note", (True, True), (f"factorIndex 21, baseDamage {D.CRUEL_STAB_BASE * 10} tenths%" in r[29],
                                                                                       "Strike" in r[29])))
    # buffs: (D table, builder key)
    for key, t in D.BUFFS.items():
        r = rows[key]
        pairs.append((f"{key} step/cooldown/base/fidx/scales", (t["job_step"], t["cooldown"], t["base"], t["fidx"], t["scales"]),
                      (r[2], r[3], r[11], r[12], r[13])))
        pairs.append((f"{key} costs_action/actions_per_cast", (t["costs_action"], t["actions_per_cast"]), (r[4], r[5])))
        d = t["duration"]
        pairs.append((f"{key} duration", IF(d[1], d[2], d[0]) if isinstance(d, tuple) else d, r[24]))
        pairs.append((f"{key} vs verify BUFFS", {k: v for k, v in t.items() if k != "duration"}, {k: v for k, v in ns["BUFFS"][key].items() if k != "duration"}))
    # Steal / Shadow Partner / Toxic Venom / Shadow Shifter / Maple Hero / Meso Mastery
    st = D.STEAL
    pairs.append(("STEAL base/fidx/step/stacks", (st["base"], st["fidx"], st["step"]), (rows["STEAL"][11], rows["STEAL"][12], rows["STEAL"][2])))
    sp = D.SHADOW_PARTNER
    r = rows["SHADOW_PARTNER"]
    pairs.append(("SHADOW_PARTNER base/fidx/step/proc/chain", (sp["base"], sp["fidx"], sp["step"], sp["proc"], sp["gated"]),
                  (r[11], r[12], r[2], r[9], _chain(r[14]))))
    tv = D.TOXIC_VENOM
    r = rows["TOXIC_VENOM"]
    pairs.append(("TOXIC_VENOM base/fidx/step/chance/chain", (tv["base"], tv["fidx"], tv["step"], tv["chance"] * 100, tv["gated"]),
                  (r[11], r[12], r[2], r[9], _chain(r[14]))))
    ss = D.SHADOW_SHIFTER
    r = rows["SHADOW_SHIFTER"]
    pairs.append(("SHADOW_SHIFTER base/fidx/step", (ss["base"], ss["fidx"], ss["step"]), (r[11], r[12], r[2])))
    pairs.append(("SHADOW_SHIFTER chance 20% in the builder's note", True, "* 20% *" in r[29]))
    mh = D.MAPLE_HERO
    r = rows["MAPLE_HERO_SHADOWER"]
    pairs.append(("MAPLE_HERO base/fidx/step", (mh["base"], mh["fidx"], mh["step"]), (r[11], r[12], r[2])))
    r = rows["MESO_MASTERY"]
    pairs.append(("MESO_MASTERY 25% attack / 75% chance in the builder's note", (True, True), ("Attack +25% for 5 sec" in r[29], "50% -> 75%" in r[29])))
    pairs.append(("Venom's Weaken +15% damage taken from Lv82 (builder note)", (True, True),
                  (f"Lv.{D.MONSTER_DMG_BONUS[0]} Weaken (+{D.MONSTER_DMG_BONUS[1]}%p" in rows["VENOM"][29], True)))
    pairs.append(("Smokescreen Crit Damage +30 from Lv113 (builder note)", True, f"Mastery Lv.{D.SMOKESCREEN_CRIT_DAMAGE[0]} 'Smokescreen - Critical'" in rows["SMOKESCREEN"][29]
                  and f"{D.SMOKESCREEN_CRIT_DAMAGE[1]}%" in rows["SMOKESCREEN"][29]))
    pairs.append(("MESO_CHANCE (50% -> 75% at Lv75): unlock of Meso Mastery", D.MESO_CHANCE[1], D.UNLOCK_LEVEL["MESO_MASTERY"]))
    bad = [name for name, a, b in pairs if a != b]
    for name in bad:
        print("DATA OUT OF SYNC:", name)
        for n_, a, b in pairs:
            if n_ == name:
                print("    engine:", a, " builder / verify:", b)
    return not bad, len(pairs)


def post_check(ns0):
    ok, n_pairs = check_data_sync(ns0)
    if not ok:
        sys.exit(1)
    print(f"OK: engine/data/shadower.py agrees with the builder's tables, the verify script's tables and SKILL_ROWS ({n_pairs} comparisons)")


def main():
    CHECK.main(post_check=post_check, line_extra=("incoming_hit_rate",))


if __name__ == "__main__":
    main()
