#!/usr/bin/env python3
"""Check that the workbook-free stand-in of run_reference_night_lord.py serves the verify script exactly the cells the REAL workbook holds (the shared
body is ``check_fake_common.py``; only the Inputs and CompanionsInput sheets of ``Night-Lord/Night-Lord-DPS-Calculator.xlsx`` are streamed).

    python3 tests/golden/check_night_lord_fake.py            # check only
    python3 tests/golden/check_night_lord_fake.py --write    # also write tests/golden/night_lord_real_inputs.json (the 10 real columns as golden cases)
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check_fake_common  # noqa: E402
import run_reference_night_lord as rr  # noqa: E402

CHECK = check_fake_common.Check(rr.REF, "night_lord", "Night-Lord")
bm, ck = CHECK.bm, CHECK.ck


_REF = re.compile(r"[A-Za-z_]+!\$?[A-Z]+\$?\d+")          # cell references (Inputs!$B$3, Calc!F12, Skills!V4 ...) carry digits that are not data


_NUM = re.compile(r"\d+(?:\.\d+)?")


def _nums(cell):
    """Sorted numeric literals of a Skills-sheet cell (a number, or a formula with its cell references removed), zeros dropped."""
    if cell in ("", None):
        return []
    if isinstance(cell, (int, float)) and not isinstance(cell, bool):
        return [float(cell)] if cell else []
    return sorted(float(x) for x in _NUM.findall(_REF.sub("", str(cell))) if float(x) != 0)


def _want(*xs):
    """Sorted non-zero floats of a flat list of numbers / (default, level, value) tuples."""
    out = []
    for x in xs:
        out += list(x) if isinstance(x, tuple) else [x]
    return sorted(float(x) for x in out if x)


def check_skill_rows(D):
    """Every static number of the engine's tables vs the builder's SKILL_ROWS cells (Formula cells are compared by their numeric literals; the
    mastery chains by the builder's own ``level_gated_sum`` text)."""
    cols = {name: i for i, name in enumerate(bm.SKILL_COLUMNS)}
    rows = {r[0]: r for r in bm.SKILL_ROWS}
    problems = []

    def cell(key, col):
        return rows[key][cols[col]]

    def expect(key, col, want, nums=False):
        got = cell(key, col)
        ok = (_nums(got) == want) if nums else (got == want)
        if not ok:
            problems.append(f"{key}.{col}: builder {got!r} vs engine {want!r}")

    def chain(key, ch):
        expect(key, "SkillMasteryBonus%", bm.level_gated_sum(bm.IB("level"), ch) if ch else 0)

    for key in D.DPS_ROW_ORDER:
        if rows[key][1] != D.SKILL_NAMES[key]:
            problems.append(f"{key}: name {rows[key][1]!r} vs {D.SKILL_NAMES[key]!r}")
    # Showdown: hits 5 / 6 from Lv136, 6 + Basic Attack Target Increase targets, the two mastery chains; the coefficient lives in the Inputs / Summary
    # derived rows (290 x F21) and is not a SKILL_ROWS cell
    expect("SHOWDOWN", "JobStep", 4)
    expect("SHOWDOWN", "HitsPerCast", _want(D.SHOWDOWN_HITS[1], D.SHOWDOWN_HITS[0], D.SHOWDOWN_HITS[2]), nums=True)
    expect("SHOWDOWN", "NormalMonsterTargets", _want(6), nums=True)
    chain("SHOWDOWN", D.SHOWDOWN_MASTERY)
    expect("SHOWDOWN", "MasteryBossDamage%", bm.level_gated_sum(bm.IB("level"), D.SHOWDOWN_MASTERY_BOSS))
    for key, t in D.DAMAGE_SKILLS.items():
        expect(key, "JobStep", t["step"])
        expect(key, "CostsActionSlot", t["costs_action"])
        expect(key, "ActionsPerCast", 1)
        expect(key, "HitsPerCast", _want(t["hits"]), nums=True)
        cd = [t["cooldown"]] + ([t["haste"][0], t["haste"][1]] if "haste" in t else [])
        if isinstance(t["cooldown"], tuple):
            cd = list(t["cooldown"])
        if key == "SUDDEN_RAID_DOT":                      # =Skills!D<burst row>: shares the burst's live cooldown cell
            expect(key, "Cooldown(s)", bm._SUDDEN_RAID_DOT_COOLDOWN)
            if t["cooldown"] != D.DAMAGE_SKILLS["SUDDEN_RAID_BURST"]["cooldown"]:
                problems.append("SUDDEN_RAID_DOT cooldown differs from the burst's")
        else:
            expect(key, "Cooldown(s)", _want(*cd, *([t["cooldown"]] if "haste" in t else [])), nums=True)
        icd = [t.get("icd", 0)] + ([t["icd_haste"][0], t["icd_haste"][1], t["icd"]] if "icd_haste" in t else [])
        expect(key, "ICD(s)", _want(*icd), nums=True)
        expect(key, "ActiveWindow(s)", _want(t.get("window", 0)), nums=True)
        expect(key, "BaseDamage(tenths%)", t["base"])
        expect(key, "FactorIndex", t["fidx"])
        expect(key, "ScalesWithLevel", True)
        chain(key, t["mastery"])
        expect(key, "MasteryBossDamage%", _want(t["mastery_boss"]), nums=True)
        expect(key, "MasteryNormalDamage%", _want(t["mastery_normal"]), nums=True)
        expect(key, "MasteryFinalDamage%", _want(t["final"][0]) if "final" in t else [], nums=True)
        if key != "MARK_OF_ASSASSIN":
            expect(key, "NormalMonsterTargets", _want(t["targets"]), nums=True)
        if key in D.MAPLE_TARGETS:
            expect(key, "MapleHeroBase(tenths%)", D.MAPLE_TARGETS[key])
            expect(key, "MapleHeroFactorIndex", D.MAPLE_FACTOR_IDX)
    # Assassin's Mark: 7 targets + MasteryTargetIncrease (+3 from Lv107, when Night Lord's Mark unlocks) and Final Damage from Night Lord's Mark's own row
    mk = D.DAMAGE_SKILLS["MARK_OF_ASSASSIN"]
    expect("MARK_OF_ASSASSIN", "NormalMonsterTargets", _want(mk["targets"][0]), nums=True)
    expect("MARK_OF_ASSASSIN", "MasteryTargetIncrease", _want(mk["targets"][1], mk["targets"][2] - mk["targets"][0]), nums=True)
    expect("MARK_OF_ASSASSIN", "MasteryFinalDamage%", bm._MARK_OF_ASSASSIN_FD)
    nl = D.NIGHT_LORDS_MARK
    if (mk["final"][0], mk["final"][1:]) != (nl["level"], (nl["base"], nl["fidx"], nl["step"])):
        problems.append("Assassin's Mark's final-damage fold-in differs from Night Lord's Mark's own row")
    if D.UNLOCK_LEVEL["NIGHT_LORDS_MARK"] != nl["level"]:
        problems.append("Night Lord's Mark level vs UNLOCK_LEVEL")
    for key, t in (("NIGHT_LORDS_MARK", nl), ("TOXIC_VENOM", D.TOXIC_VENOM), ("SHADOW_SHIFTER", D.SHADOW_SHIFTER), ("SHADOW_PARTNER", D.SHADOW_PARTNER)):
        expect(key, "JobStep", t["step"])
        expect(key, "BaseDamage(tenths%)", t["base"])
        expect(key, "FactorIndex", t["fidx"])
    chain("TOXIC_VENOM", D.TOXIC_VENOM["mastery"])
    chain("SHADOW_PARTNER", D.SHADOW_PARTNER["mastery"])
    expect("TOXIC_VENOM", "ProcChance%", round(D.TOXIC_VENOM["chance"] * 100))
    expect("SHADOW_SHIFTER", "ProcChance%", 100)               # (the 20% counterattack chance lives in the O-column formula: incoming_hit_rate * 0.2)
    expect("SHADOW_PARTNER", "ProcChance%", D.SHADOW_PARTNER["share"])
    # buffs
    for key, t in D.BUFFS.items():
        expect(key, "JobStep", t["step"])
        expect(key, "Cooldown(s)", t["cooldown"])
        expect(key, "BuffDuration(s)", _want(t["duration"]), nums=True)
        expect(key, "BaseDamage(tenths%)", t["base"])
        expect(key, "FactorIndex", t["fidx"])
        expect(key, "ScalesWithLevel", t["scales"])
        expect(key, "BuffTargetStat", t["target"])
        expect(key, "CostsActionSlot", t["costs_action"])
        expect(key, "ActionsPerCast", t["actions_per_cast"])
    for key, t in D.ADRENALIN.items():
        expect(key, "JobStep", t["step"])
        expect(key, "BaseDamage(tenths%)", t["base"])
        expect(key, "FactorIndex", t["fidx"])
        expect(key, "BuffTargetStat", t["target"])
        expect(key, "BuffDuration(s)", _want(D.ADRENALIN_DURATION[1], D.ADRENALIN_DURATION[2], D.ADRENALIN_DURATION[0]), nums=True)
        chain(key, t.get("gated", {}))
    for key, t in D.PASSIVE_MULT.items():
        expect(key, "JobStep", t["step"])
        expect(key, "BaseDamage(tenths%)", t["base"])
        expect(key, "FactorIndex", t["fidx"])
    # the player's own stun (game table): Gust Charm's cooldown / the unlock level, and the stun's own duration comes from the builder's STATUS_PLAYER_STUN
    expect("GUST_CHARM", "Cooldown(s)", D.PLAYER_STUN[0]["cd"])
    # Toxic Venom's trigger rows = the rows flagged TriggersToxicVenom
    flagged = sorted(r[0] for r in bm.SKILL_ROWS if r[cols["TriggersToxicVenom"]] is True)
    if flagged != sorted(D.TRIGGERS_TOXIC_VENOM):
        problems.append(f"TriggersToxicVenom rows: builder {flagged} vs engine {sorted(D.TRIGGERS_TOXIC_VENOM)}")
    # constants the builder keeps inside its Summary-sheet formulas (checked on the builder's source text): Showdown's 290 x F21 coefficient, Alchemic
    # Adrenaline's 5 activations, Critical Throw Lv47 +8, Venom Weaken Lv82 +15, Frailty Curse - Critical Lv111 +30
    src = (rr.REF.SRC / "build_night_lord_workbook.py").read_text()
    for lit in (f"value=f'={D.SHOWDOWN_BASE}*{{IB(\"basic_factor\")}}/1000')", f"activations_needed = {D.ADRENALIN_ACTIVATIONS}",
                f'>={D.CRITICAL_THROW_LV47[0]},{D.CRITICAL_THROW_LV47[1]:g},0)', f'>={D.VENOM_WEAKEN[0]},{D.VENOM_WEAKEN[1]:g},0)'):   # (the frozen builder's Frailty Curse - Critical Lv111 +30 differs on purpose: patch 2026-11-26)
        if lit not in src:
            problems.append(f"builder source lacks {lit!r}")
    return problems


def check_data_sync():
    """engine/data/night_lord.py vs the tables the builder exports (the verify script imports these from the builder, so they must agree) and vs the
    static numbers of the builder's SKILL_ROWS (job step, cooldown, hits, ICD, window, base damage, factor index, masteries, targets, buffs)."""
    sys.path.insert(0, str(HERE.parents[1]))
    from engine.common import content
    from engine.data import night_lord as D
    pairs = [("UNLOCK_LEVEL", D.UNLOCK_LEVEL, bm.UNLOCK_LEVEL),
             ("STATUS_GROUPS", D.STATUS_GROUPS, bm.STATUS_GROUPS), ("STATUS_BUFFS", D.STATUS_BUFFS, bm.STATUS_BUFFS),
             ("STATUS_UNIFORM_ROWS", D.STATUS_UNIFORM_ROWS, bm.STATUS_UNIFORM_ROWS), ("STATUS_CAST_PREFIX", D.STATUS_CAST_PREFIX, bm.STATUS_CAST_PREFIX),
             ("STATUS_PHI_ROWS", D.STATUS_PHI_ROWS, bm.STATUS_PHI_ROWS), ("STATUS_FS_KEYS", D.STATUS_FS_KEYS, bm.STATUS_FS_KEYS),
             ("CDR_EXEMPT", sorted(D.CDR_EXEMPT), sorted(bm.CDR_EXEMPT_ROW_KEYS)),
             # the player's stun: (id, row, typ, dur, p); the builder omits tick / win (the verify script uses 1.0 / 0.0 for a cast) and min_level (0)
             ("PLAYER_STUN", [(e["id"], e["key"], e["typ"], e["dur"], e["p"], e["min_level"], e["tick"], e["win"]) for e in D.PLAYER_STUN],
              [(e["id"], e["row"], e["typ"], e["dur"], e["p"], e.get("min_level", 0), e.get("tick", 1.0), e.get("win", 0.0))
               for e in bm.STATUS_PLAYER_STUN]),
             ("CONTENT_TYPES (as a set)", sorted(content.CONTENT_TYPES), sorted(bm.CONTENT_TYPES)),
             ]
    all_keys = set(D.DPS_ROW_ORDER) | set(D.BUFFS) | set(D.ADRENALIN) | set(D.PASSIVE_MULT) | {"SHADOW_PARTNER", "NIGHT_LORDS_MARK"}
    pairs.append(("every row key exists on the Skills sheet", sorted(all_keys), sorted(all_keys & set(bm.ROW))))
    bad = [name for name, a, b in pairs if a != b]
    for name in bad:
        print("DATA OUT OF SYNC:", name)
    problems = check_skill_rows(D)
    for p in problems:
        print("DATA OUT OF SYNC:", p)
    return not bad and not problems


def pre_check():
    if not check_data_sync():
        sys.exit(1)
    print("OK: engine/data/night_lord.py agrees with the builder's tables and SKILL_ROWS")


def main():
    CHECK.main(pre_check=pre_check)


if __name__ == "__main__":
    main()
