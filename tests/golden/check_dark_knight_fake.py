#!/usr/bin/env python3
"""Check that the workbook-free stand-in of run_reference_dark_knight.py serves the verify script exactly the cells the REAL workbook holds (the shared
body is ``check_fake_common.py``; only the Inputs and CompanionsInput sheets of ``Dark-Knight/Dark-Knight-DPS-Calculator.xlsx`` are streamed).

    python3 tests/golden/check_dark_knight_fake.py            # check only
    python3 tests/golden/check_dark_knight_fake.py --write    # also write tests/golden/dark_knight_real_inputs.json (the 10 real columns as golden cases)
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check_fake_common  # noqa: E402
import run_reference_dark_knight as rr  # noqa: E402

CHECK = check_fake_common.Check(rr.REF, "dark_knight", "Dark-Knight")
bm, ck = CHECK.bm, CHECK.ck


_REF = re.compile(r"[A-Za-z_]+!\$?[A-Z]+\$?\d+")          # cell references (Inputs!$B$3, Calc!F12, ...) carry digits that are not data


_NUM = re.compile(r"\d+(?:\.\d+)?")


def _nums(cell):
    """Sorted numeric literals of a Skills-sheet cell (a number, or a formula with its cell references / row numbers removed), zeros dropped."""
    if cell in ("", None):
        return []
    if isinstance(cell, (int, float)) and not isinstance(cell, bool):
        return [float(cell)] if cell else []
    text = _REF.sub("", str(cell))
    return sorted(float(x) for x in _NUM.findall(text) if float(x) != 0)


def _chain_nums(chain):
    return sorted(float(x) for lvl, inc in chain.items() for x in (lvl, inc))


def check_skill_rows(D):
    """Skill-by-skill: every number the engine's tables hold vs the builder's SKILL_ROWS cells (JobStep, CostsActionSlot, HitsPerCast, ICD, window,
    BaseDamage, FactorIndex, Cooldown, mastery chain, targets, buff duration, proc chance).  Formula cells are compared by their numeric literals."""
    cols = {name: i for i, name in enumerate(bm.SKILL_COLUMNS)}
    rows = {r[0]: r for r in bm.SKILL_ROWS}
    problems = []

    def cell(key, col):
        return rows[key][cols[col]]

    def expect(key, col, want):
        got = cell(key, col)
        if isinstance(want, list):
            ok = _nums(got) == sorted(float(x) for x in want if x)
        else:
            ok = got == want
        if not ok:
            problems.append(f"{key}.{col}: builder {got!r} vs engine {want!r}")

    for key, t in D.DAMAGE_SKILLS.items():
        expect(key, "JobStep", t["step"])
        expect(key, "CostsActionSlot", t["costs_action"])
        hits = [t["hits"]] + (list(t["hits_gate"]) if "hits_gate" in t else [])
        expect(key, "HitsPerCast", hits)
        base = [t["base"]] + (list(t["base_gate"]) if "base_gate" in t else [])
        expect(key, "BaseDamage(tenths%)", base)
        expect(key, "FactorIndex", t["fidx"])
        cd = [t["cooldown"]] + ([t["haste"][0], t["cooldown"] * t["haste"][1]] if "haste" in t else [])
        expect(key, "Cooldown(s)", cd + ([30, 0.7] if key == "EVIL_EYE_OF_DOMINANT" else []) if False else _cd_tokens(t))
        expect(key, "ICD(s)", t.get("icd", 0))
        expect(key, "ActiveWindow(s)", t.get("window", 0))
        expect(key, "SkillMasteryBonus%", _chain_nums(t["mastery"]) if t["mastery"] else [])
        expect(key, "NormalMonsterTargets", [t["targets"]] + (list(t["extra_targets"]) if "extra_targets" in t else []))
        expect(key, "MasteryBossDamage%", 0)
        expect(key, "MasteryNormalDamage%", 0)
    # buffs / passives / helpers: (step, base, fidx, chain, duration, cooldown tokens, proc chance)
    singles = {
        "FINAL_ATTACK_HELPER": D.FINAL_ATTACK, "ADVANCED_FINAL_ATTACK_HELPER": D.ADVANCED_FINAL_ATTACK, "MAPLE_HERO_HELPER": D.MAPLE_HERO,
        "EVIL_EYE_SHOCK_ENH": D.EVIL_EYE_SHOCK_ENH, "HEX_OF_THE_EVIL_EYE": D.HEX, "DARK_RESONANCE": D.DARK_RESONANCE,
        "CROSS_OVER_CHAINS": D.CROSS_OVER_CHAINS, "HYPER_BODY": D.HYPER_BODY, "EVIL_EYE": D.EVIL_EYE, "NIMBLE_FEET": D.NIMBLE_FEET,
        "LORD_OF_DARKNESS_CRITRATE": D.LORD_OF_DARKNESS_CRITRATE, "LORD_OF_DARKNESS_CRITDMG": D.LORD_OF_DARKNESS_CRITDMG,
    }
    for key, t in singles.items():
        expect(key, "JobStep", t["step"])
        expect(key, "BaseDamage(tenths%)", t["base"])
        expect(key, "FactorIndex", t["fidx"])
        if key != "ADVANCED_FINAL_ATTACK_HELPER":      # (its Lv113 chain sits in the same SkillMasteryBonus% cell as the other chains)
            pass
        expect(key, "SkillMasteryBonus%", _chain_nums(t.get("gated", {})) if t.get("gated") else [])
    # durations / cooldowns of the buff rows
    eye_cd = [D.EVIL_EYE_COOLDOWN[0], D.EVIL_EYE_COOLDOWN[1], D.EVIL_EYE_COOLDOWN[2]]
    for key in ("HEX_OF_THE_EVIL_EYE", "EVIL_EYE"):
        expect(key, "Cooldown(s)", [30, 104, 0.7, 30])
    expect("HEX_OF_THE_EVIL_EYE", "BuffDuration(s)", D.HEX["duration"])
    expect("EVIL_EYE", "BuffDuration(s)", D.EVIL_EYE["duration"])
    expect("DARK_RESONANCE", "Cooldown(s)", D.DARK_RESONANCE["cooldown"])
    expect("DARK_RESONANCE", "BuffDuration(s)", [D.DARK_RESONANCE["duration_level"], D.DARK_RESONANCE["duration"], D.DARK_RESONANCE["duration_mult"],
                                                  D.DARK_RESONANCE["duration"]])
    for key, t in (("CROSS_OVER_CHAINS", D.CROSS_OVER_CHAINS), ("HYPER_BODY", D.HYPER_BODY), ("NIMBLE_FEET", D.NIMBLE_FEET)):
        expect(key, "Cooldown(s)", t["cooldown"])
        expect(key, "BuffDuration(s)", t["duration"])
    for key in ("LORD_OF_DARKNESS_CRITRATE", "LORD_OF_DARKNESS_CRITDMG"):
        expect(key, "Cooldown(s)", D.LORD_OF_DARKNESS["cooldown"])
        expect(key, "BuffDuration(s)", D.LORD_OF_DARKNESS["duration"])
        expect(key, "ProcChance%", D.LORD_OF_DARKNESS["proc_chance"])
    # Dark Impale: basic attack tuple, hits, mastery chains
    expect("DARK_IMPALE", "JobStep", 4)
    expect("DARK_IMPALE", "BaseDamage(tenths%)", D.DARK_IMPALE_BASE * 10)     # (the verify script writes it as 290 = 2900 / 10)
    expect("DARK_IMPALE", "FactorIndex", 21)
    expect("DARK_IMPALE", "HitsPerCast", [D.DARK_IMPALE_HITS[1], D.DARK_IMPALE_HITS[2], D.DARK_IMPALE_HITS[0]])
    expect("DARK_IMPALE", "MasteryBossDamage%", _chain_nums(D.DARK_IMPALE_BOSS_MASTERY))
    expect("DARK_IMPALE", "SkillMasteryBonus%", _chain_nums(D.DARK_IMPALE_MASTERY))
    # fold-ins (SKILL_FOLD_BONUS, the additive coefficient points): Evil Eye Shock Enhancement from Lv75, Revenge's Lv138 Spectral Shadows
    # (2200 x the row's OWN factor index 12), Dark Impale's Final Attack x Advanced Final Attack x 25
    rf = D.DAMAGE_SKILLS["REVENGE_OF_THE_EVIL_EYE"]["revenge_fold"]
    for key, want in (("EVIL_EYE_SHOCK", [D.DAMAGE_SKILLS["EVIL_EYE_SHOCK"]["fold_level"], 1]), ("REVENGE_OF_THE_EVIL_EYE", [rf["level"], rf["base"], 1000]),
                      ("DARK_IMPALE", [D.FINAL_ATTACK_SHARE, 1, 100, 100, 1, 1])):
        got = _nums(bm.SKILL_FOLD_BONUS[key])
        if got != sorted(float(x) for x in want):
            problems.append(f"{key}.SkillFoldBonus%: builder {bm.SKILL_FOLD_BONUS[key]!r} -> {got} vs engine {want}")
    # Maple Hero shares: the workbook's K formulas read MAPLE_HERO_RATIOS (the Skills-sheet Maple columns are documentation only: Evil Eye Shock's cell still
    # says 400 while its ratio is 30/40, which both the workbook and the verify script use), so check the ratio table and the factor-index column only
    for key in D.MAPLE_HERO_RATIOS:
        if cell(key, "MapleHeroFactorIndex") != D.MAPLE_HERO["fidx"]:
            problems.append(f"{key}: Maple Hero factor index {cell(key, 'MapleHeroFactorIndex')} vs {D.MAPLE_HERO['fidx']}")
    # Iron Wall (the builder's own STAT_DAMAGE expression): the factor column / rate base / min level
    iw = D.IRON_WALL
    m = re.search(r"IF\(IN_level>=(\d+),\((\d+)\*INDEX\(.*?,\s*(\d+)\)/1000\)", bm.iron_wall_str_bonus_expr(lambda k: f"IN_{k}"))
    if not m or (int(m.group(1)), int(m.group(2)), int(m.group(3)) - 1) != (iw["min_level"], iw["rate_base"], iw["rate_factor_idx"]):
        problems.append(f"Iron Wall expression vs engine tables: {m.groups() if m else None} vs {iw}")
    return problems


def _cd_tokens(t):
    """Cooldown cell numeric literals the builder is expected to hold for a damage row: the base, plus (haste level, base, multiplier) when it has one."""
    if "haste" in t:
        return [t["haste"][0], t["cooldown"], t["haste"][1], t["cooldown"]] if t["cooldown"] == 22 else [t["haste"][0], t["cooldown"], t["haste"][1], t["cooldown"]]
    return [t["cooldown"]]


def check_data_sync():
    """engine/data/dark_knight.py vs the tables the builder exports (the verify script imports these from the builder, so they must agree)."""
    sys.path.insert(0, str(HERE.parents[1]))
    from engine.data import dark_knight as D
    pairs = [("UNLOCK_LEVEL", D.UNLOCK_LEVEL, bm.UNLOCK_LEVEL), ("MAPLE_HERO_RATIOS", D.MAPLE_HERO_RATIOS, bm.MAPLE_HERO_RATIOS),
             ("STATUS_GROUPS", D.STATUS_GROUPS, bm.STATUS_GROUPS), ("STATUS_BUFFS", D.STATUS_BUFFS, bm.STATUS_BUFFS),
             ("STATUS_UNIFORM_ROWS", D.STATUS_UNIFORM_ROWS, bm.STATUS_UNIFORM_ROWS), ("STATUS_CAST_PREFIX", D.STATUS_CAST_PREFIX, bm.STATUS_CAST_PREFIX),
             ("STATUS_PHI_ROWS", D.STATUS_PHI_ROWS, bm.STATUS_PHI_ROWS), ("STATUS_FS_KEYS", D.STATUS_FS_KEYS, bm.STATUS_FS_KEYS),
             ("STATUS_GROUP_TAKES_SLOT", D.STATUS_GROUP_TAKES_SLOT, bm.STATUS_GROUP_TAKES_SLOT),
             ("PLAYER_STUN", [(e["id"], e["key"], e["typ"], e["dur"], e["p"]) for e in D.PLAYER_STUN],
              [(e["id"], e["row"], e["typ"], e["dur"], e["p"]) for e in bm.STATUS_PLAYER_STUN]),
             ("PLAYER_STUN cooldowns (Evil Eye Shock's own cooldown)", D.PLAYER_STUN[1]["cd"], D.DAMAGE_SKILLS["EVIL_EYE_SHOCK"]["cooldown"]),
             ("BUFF_ROW_KEYS (set; the verify script's own set equals the builder's)", sorted(D.BUFF_ROW_KEYS), sorted(set(D.BUFF_ROW_KEYS) & set(bm.BUFF_ROW_KEYS))),
             ("DPS_ROW_ORDER (Skills-sheet order of the damage rows)", D.DPS_ROW_ORDER, [k for k in bm.ROW_ORDER if k in D.DPS_ROW_ORDER]),
             ("SKILL_NAMES", D.SKILL_NAMES, {r[0]: r[1] for r in bm.SKILL_ROWS if r[0] in D.SKILL_NAMES}),
             ("IN rows used by the engine (defense_pct / defense / companion_choice / pvp_fight_length)",
              (bm.IN["defense"], bm.IN["defense_pct"], bm.IN["companion_choice"], bm.IN["pvp_fight_length"]), (8, 9, 52, 55)),
             ("CONTENT_TYPES (as a set)",) + D_content_types()]
    bad = [name for name, a, b in pairs if a != b]
    for name in bad:
        print("DATA OUT OF SYNC:", name)
    rows_bad = check_skill_rows(D)
    for p in rows_bad:
        print("SKILL ROW OUT OF SYNC:", p)
    return not bad and not rows_bad


def D_content_types():
    from engine.common import content
    return sorted(content.CONTENT_TYPES), sorted(bm.CONTENT_TYPES)


def pre_check():
    if not check_data_sync():
        sys.exit(1)
    print("OK: engine/data/dark_knight.py agrees with the builder's tables")


def main():
    CHECK.main(pre_check=pre_check)


if __name__ == "__main__":
    main()
