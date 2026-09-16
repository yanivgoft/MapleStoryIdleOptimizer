#!/usr/bin/env python3
"""
Cross-checks Bishop-DPS-Calculator.xlsx against an independent Python port of the same logic,
using the workbook's own default Inputs values. Then loads the live workbook with the `formulas`
package (a real formula evaluator, not just the static values openpyxl wrote) and diffs Total DPS
+ every per-skill DPS cell (Calc!O<row>) against this script's independent numbers. Mirrors the
sibling verify_*_workbook.py scripts (read-only references, not modified) in structure and
method.

NOTE: several of this class's own (baseDamage, factorIndex) pairs are FLAGGED ASSUMPTIONS, not
zero-residual-error reverse-engineered values (see build_bishop_workbook.py's own module
docstring and the plan) — this script verifies internal consistency between the Excel formulas
and this independent Python model, not correctness against the game itself for those rows.
"""
import json
import math
import re
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
XLSX_PATH = REPO / "Bishop-DPS-Calculator.xlsx"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_bishop_workbook import ROW, IN, UNLOCK_LEVEL, SUMMARY_ROW  # noqa: E402

FACTOR_TABLE = json.loads((REPO / "data/factor_table.json").read_text())
FACTOR_TABLE = {int(k): v for k, v in FACTOR_TABLE.items()}


def get_factor(level, idx):
    level = min(300, max(1, round(level)))
    return FACTOR_TABLE[level][idx]


def input_level(job_step, level, skill1, skill2, skill3, skill4, skill_all):
    if job_step == 1:
        return 60 + skill1 + skill_all
    if job_step == 2:
        return 90 + skill2 + skill_all
    if job_step == 3:
        return 120 + skill3 + skill_all
    return max(0, (level - 100) * 3) + skill4 + skill_all


import openpyxl  # noqa: E402

_inputs_ws = openpyxl.load_workbook(XLSX_PATH)["Inputs"]


def _in(key):
    return _inputs_ws.cell(row=IN[key], column=2).value


level = _in("level")
monster_type = _in("monster_type")
breakthrough_normal_weight_pct = _in("breakthrough_normal_weight_pct")
normal_weight = (
    1.0 if monster_type == "normal"
    else breakthrough_normal_weight_pct / 100 if monster_type == "breakthrough"
    else 0.0
)
skill1, skill2, skill3, skill4, skill_all = (
    _in("skill_lvl_1st"), _in("skill_lvl_2nd"), _in("skill_lvl_3rd"), _in("skill_lvl_4th"), _in("skill_lvl_all")
)
monster_defense = _in("monster_defense")
flat_attack, attack_pct = _in("flat_attack"), _in("attack_pct")
attack = flat_attack * (1 + attack_pct / 100)
flat_int, int_pct, luk = _in("flat_int"), _in("int_pct"), _in("luk")
stat_damage = (flat_int * (1 + int_pct / 100)) * 0.01 + luk * 0.0025
damage = _in("damage")
damage_amp = _in("damage_amp")
boss_damage = _in("boss_damage")
normal_damage = _in("normal_damage")
final_damage = _in("final_damage")
min_damage = _in("min_damage")
max_damage = _in("max_damage")
crit_rate = _in("crit_rate")
crit_damage = _in("crit_damage")
attack_speed_base = _in("attack_speed")
def_pen = _in("def_pen")
basic_attack_damage = _in("basic_attack_damage")
skill_damage = _in("skill_damage")
skill_cooldown_decrease = _in("skill_cooldown_decrease")
basic_attack_target_increase = _in("basic_attack_target_increase")
buff_duration_increase_pct = _in("buff_duration_increase_pct")
fight_duration = _in("fight_duration")
max_enemies_hit = _in("max_enemies_hit")

fixed_duration_active = monster_type != "pvp" and fight_duration > 0

basic_lvl = input_level(4, level, skill1, skill2, skill3, skill4, skill_all)
skill_coefficient_base = 290 * get_factor(basic_lvl, 21) / 1000
print(f"SKILL_COEFFICIENT (base) = {skill_coefficient_base:.4f}")


def level_gated_sum(pairs):
    return sum(inc for lvl, inc in pairs.items() if level >= lvl)


big_bang_mastery = level_gated_sum({102: 10, 106: 1, 116: 1, 120: 1, 128: 1, 132: 1})
big_bang_boss_mastery = level_gated_sum({111: 10, 124: 10})
big_bang_hits = 6 if level >= 136 else 5

heal_duration = (10 * 1.5) if level >= 39 else 10
bless_duration = (15 * 1.3) if level >= 44 else 15
genesis_cooldown = (23 * 0.7) if level >= 126 else 23
bahamut_cooldown = (80 * 0.7) if level >= 138 else 80
bahamut_targets = 6 if level >= 130 else 3
holy_symbol_duration = (14 * 1.5) if level >= 98 else 14
triumph_feather_targets = 7 if level >= 94 else 1

SKILLS = {
    "ANGEL_RAY": dict(job_step=4, cooldown=17, hits=6, base=6800, fidx=12, scales=True,
                       mastery=level_gated_sum({108: 50}), mastery_boss=0, mastery_normal=0, costs_action=True, targets=1),
    "ANGEL_RAY_BOSS_PROC": dict(job_step=4, cooldown=17, hits=1, base=6800, fidx=12, scales=True,
                                 mastery=0, mastery_boss=0, mastery_normal=0, costs_action=False, targets=1),
    "GENESIS": dict(job_step=4, cooldown=genesis_cooldown, hits=6, base=7000, fidx=12, scales=True,
                     mastery=level_gated_sum({118: 50}), mastery_boss=0, mastery_normal=0,
                     costs_action=True, targets=10),
    "BAHAMUT": dict(job_step=4, cooldown=bahamut_cooldown, hits=1, icd=4, window=30, base=35000, fidx=12,
                     scales=True, mastery=level_gated_sum({130: 50}), mastery_boss=0, mastery_normal=0,
                     costs_action=True, targets=bahamut_targets),
}
BUFFS = {
    "MAGIC_GUARD": dict(job_step=1, cooldown=(30 * 0.7) if level >= 21 else 30, duration=15,
                         base=120, fidx=21, scales=True, costs_action=True, target="ATTACK"),
    "HEAL": dict(job_step=2, cooldown=18, duration=heal_duration, base=100, fidx=22, scales=True,
                 costs_action=True, mastery=level_gated_sum({54: 8}), target="ATTACK"),
    "BLESS": dict(job_step=2, cooldown=24, duration=bless_duration, base=160, fidx=22, scales=True,
                  costs_action=True, target="ATTACK"),
    "HOLY_MAGIC_SHELL": dict(job_step=3, cooldown=27, duration=22, base=150, fidx=22, scales=True,
                              costs_action=True, target="ATTACK"),
    "ADVANCED_BLESSING": dict(job_step=4, cooldown=26, duration=20, base=70, fidx=22, scales=True,
                               costs_action=True, mastery=level_gated_sum({113: 4}), target="FINAL_DAMAGE"),
    "INFINITY": dict(job_step=4, cooldown=30, duration=15, base=150, fidx=21, scales=True,
                      costs_action=True, ramp_mult=64 / 45, target="FINAL_DAMAGE"),
}
PASSIVES = {
    "BUFF_MASTERY": dict(job_step=4, base=100, fidx=22, scales=True),
    "ARCANE_AIM": dict(job_step=4, base=30, fidx=22, scales=True),
    "ELEMENT_AMPLIFICATION": dict(job_step=3, base=150, fidx=22, scales=True),
    "MP_EATER_MP_BOOST": dict(job_step=2, base=70, fidx=0, scales=False),
    "BLOOD_OF_THE_DIVINE": dict(job_step=4, base=50, fidx=22, scales=True),
    "MAPLE_HERO_BISHOP": dict(job_step=4, base=500, fidx=23, scales=True),
    "HOLY_SYMBOL": dict(job_step=3, base=150, fidx=22, scales=True, mastery=level_gated_sum({90: 25})),
}
NORMAL_MONSTER_TARGETS = {k: v["targets"] for k, v in SKILLS.items()}


def target_multiplier(key):
    if monster_type == "pvp":
        return 1
    if key == "BIG_BANG":
        targets = 6 + basic_attack_target_increase
    else:
        targets = NORMAL_MONSTER_TARGETS.get(key, 1)
    targets = min(targets, max_enemies_hit)
    return (1 - normal_weight) * 1 + normal_weight * targets


def unlocked(key):
    threshold = UNLOCK_LEVEL.get(key)
    return threshold is None or level >= threshold


PVP_FIGHT_DURATION = 15


def eff_cooldown(cooldown, costs_action):
    if monster_type == "pvp":
        return PVP_FIGHT_DURATION
    return max(0.1, cooldown - (skill_cooldown_decrease if costs_action else 0))


def eff_duration(duration):
    return duration * (1 + (buff_duration_increase_pct + buff_mastery_pct) / 100)


def exact_casts(cooldown):
    return math.floor(fight_duration / cooldown) + 1


def exact_total_hits(cooldown, hits_per_cast, icd, window):
    casts = exact_casts(cooldown)
    remaining_after_last = max(0.0, fight_duration - (casts - 1) * cooldown)
    if icd:
        full_window_ticks = window / icd
        last_cast_ticks = min(window, remaining_after_last) / icd
    else:
        full_window_ticks = 1
        last_cast_ticks = 1
    return hits_per_cast * ((casts - 1) * full_window_ticks + last_cast_ticks)


def exact_buff_uptime(cooldown, buff_duration):
    casts = exact_casts(cooldown)
    remaining_after_last = max(0.0, fight_duration - (casts - 1) * cooldown)
    last_uptime = min(buff_duration, remaining_after_last)
    return (casts - 1) * buff_duration + last_uptime


def coeff_pct(base, fidx, scales, job_step):
    lvl = input_level(job_step, level, skill1, skill2, skill3, skill4, skill_all)
    if not scales:
        return base / 10
    return (base / 10) * (get_factor(lvl, fidx) / 1000)


def passive_pct(key):
    p = PASSIVES[key]
    return coeff_pct(p["base"], p["fidx"], p["scales"], p["job_step"]) if unlocked(key) else 0.0


buff_mastery_pct = passive_pct("BUFF_MASTERY")
arcane_aim_pct = passive_pct("ARCANE_AIM")
element_amp_pct = passive_pct("ELEMENT_AMPLIFICATION")
mp_eater_as_pct = passive_pct("MP_EATER_MP_BOOST")
blood_divine_pct = passive_pct("BLOOD_OF_THE_DIVINE")
maple_hero_bishop_pct = passive_pct("MAPLE_HERO_BISHOP")
holy_symbol_pct = passive_pct("HOLY_SYMBOL")
holy_symbol_mastery_pct = PASSIVES["HOLY_SYMBOL"]["mastery"] if unlocked("HOLY_SYMBOL") else 0.0

# Holy Fountain - Boss Monster Damage (Mastery Lv.68, patched 10%->20%): flat, non-scaling,
# duty-cycle-averaged off Holy Fountain's own (patched 30s) cooldown, linger 15s.
holy_fountain_cooldown = 30
if level >= 68:
    hf_eff_cd = eff_cooldown(holy_fountain_cooldown, True)
    if monster_type == "pvp":
        hf_uptime = min(eff_duration(15), PVP_FIGHT_DURATION) / PVP_FIGHT_DURATION
    else:
        hf_uptime = eff_duration(15) / hf_eff_cd
    monster_dmg_bonus = 20 * hf_uptime
else:
    monster_dmg_bonus = 0.0

# Holy Symbol's own base effect (duty-cycle-averaged, Normal-Monster-only) — feeds only the
# normal side of monster_dmg_term. Unlike Holy Fountain's own steady-state-only treatment, Holy
# Symbol is built as a real buff row (build script's own `buff_uptime()`), so it DOES get the
# exact fixed-duration uptime branch.
if unlocked("HOLY_SYMBOL"):
    hsym_eff_cd = eff_cooldown(28, False)
    if fixed_duration_active:
        hsym_uptime = exact_buff_uptime(hsym_eff_cd, eff_duration(holy_symbol_duration)) / fight_duration
    elif monster_type == "pvp":
        hsym_uptime = min(eff_duration(holy_symbol_duration), PVP_FIGHT_DURATION) / PVP_FIGHT_DURATION
    else:
        hsym_uptime = eff_duration(holy_symbol_duration) / hsym_eff_cd
    normal_dmg_bonus = holy_symbol_pct * hsym_uptime
else:
    normal_dmg_bonus = 0.0

# Holy Symbol's Mastery Lv.90 "Damage Boost" — solo-always-true.
damage_bonus = holy_symbol_mastery_pct

# Blood of the Divine: assumed 100% HP -> +20% Crit Damage (4x its own Final-Damage F-value).
crit_damage_bonus = 4 * blood_divine_pct

# MP Eater + Blood of the Divine's own AS mastery (flat, always-on, no uptime averaging).
as_bonus = (mp_eater_as_pct if unlocked("MP_EATER_MP_BOOST") else 0.0) + (15 if level >= 134 else 0)

actions_per_second = 1 + min(150, 150 * (1 - (1 - attack_speed_base / 150) * (1 - as_bonus / 150))) / 100
if fixed_duration_active:
    cast_rate = sum(exact_casts(eff_cooldown(SKILLS[k]["cooldown"], SKILLS[k]["costs_action"])) for k, s in SKILLS.items() if s["costs_action"] and unlocked(k))
    cast_rate += sum(exact_casts(eff_cooldown(b["cooldown"], b["costs_action"])) for key, b in BUFFS.items() if b["costs_action"] and unlocked(key))
    cast_rate += exact_casts(eff_cooldown(holy_fountain_cooldown, True)) if unlocked("HOLY_FOUNTAIN") else 0
    cast_rate /= fight_duration
else:
    cast_rate = sum(1 / eff_cooldown(SKILLS[k]["cooldown"], s["costs_action"]) for k, s in SKILLS.items() if s["costs_action"] and unlocked(k))
    cast_rate += sum(1 / eff_cooldown(b["cooldown"], b["costs_action"]) for key, b in BUFFS.items() if b["costs_action"] and unlocked(key))
    cast_rate += (1 / eff_cooldown(holy_fountain_cooldown, True)) if unlocked("HOLY_FOUNTAIN") else 0
big_bang_per_second = max(0, actions_per_second - cast_rate)

# Average buff multiplier. Magic Guard, Heal, Bless, and Holy Magic Shell are all "+X% Attack"
# sources — same bucket, so they sum into one combined percentage before a single
# multiplication; Advanced Blessing and Infinity are both Final Damage, a different (and
# deliberately still multiplicative) bucket, so they stay their own separate factors.
attack_bucket_sum = 0.0
final_damage_mult = 1.0
for key, b in BUFFS.items():
    if not unlocked(key):
        continue
    pct = coeff_pct(b["base"], b["fidx"], b["scales"], b["job_step"])
    if "ramp_mult" in b:
        pct *= b["ramp_mult"]
    pct += b.get("mastery", 0)
    eff_cd = eff_cooldown(b["cooldown"], b["costs_action"])
    if fixed_duration_active:
        uptime_fraction = exact_buff_uptime(eff_cd, eff_duration(b["duration"])) / fight_duration
    elif monster_type == "pvp":
        uptime_fraction = min(eff_duration(b["duration"]), PVP_FIGHT_DURATION) / PVP_FIGHT_DURATION
    else:
        uptime_fraction = eff_duration(b["duration"]) / eff_cd
    avg_pct = pct * uptime_fraction
    if b["target"] == "ATTACK":
        attack_bucket_sum += avg_pct
    else:
        final_damage_mult *= 1 + avg_pct / 100
avg_buff_mult = (1 + attack_bucket_sum / 100) * final_damage_mult


def hit_damage(coeff_pct_val, is_basic, s, key):
    effective_coeff = coeff_pct_val + s.get("mastery", 0)
    base_damage = attack * (effective_coeff / 100)
    dmg_reduction = 5000 / (6000 + monster_defense * (1 - def_pen / 100))
    if monster_type == "pvp":
        monster_dmg = 0
    else:
        boss_term = boss_damage + s.get("mastery_boss", 0) + monster_dmg_bonus
        normal_term = normal_damage + s.get("mastery_normal", 0) + normal_dmg_bonus
        monster_dmg = (1 - normal_weight) * boss_term + normal_weight * normal_term
    elem_amp = element_amp_pct if unlocked("ELEMENT_AMPLIFICATION") else 0.0
    blood_divine = blood_divine_pct if unlocked("BLOOD_OF_THE_DIVINE") else 0.0
    arcane = arcane_aim_pct if unlocked("ARCANE_AIM") else 0.0
    triumph_maple = maple_hero_bishop_pct if (key == "TRIUMPH_FEATHER" and unlocked("MAPLE_HERO_BISHOP")) else 0.0
    final_mult = (
        (1 + final_damage / 100) * (1 + elem_amp / 100) * (1 + blood_divine / 100)
        * (1 + triumph_maple / 100) * (1 + arcane / 100) ** 5
    )
    source_pct = basic_attack_damage if is_basic else skill_damage
    extra_mult = avg_buff_mult
    base_hit = (
        base_damage * (1 + stat_damage / 100) * (1 + (damage + damage_bonus) / 100) * (1 + monster_dmg / 100)
        * (1 + damage_amp / 100) * dmg_reduction * final_mult * (1 + source_pct / 100) * extra_mult
    )
    non_crit_min = base_hit * min(min_damage, max_damage) / 100
    non_crit_max = base_hit * max_damage / 100
    non_crit_avg = (non_crit_min + non_crit_max) / 2
    crit_avg = non_crit_avg * (1 + (crit_damage + crit_damage_bonus) / 100)
    cr = min(crit_rate, 100) / 100
    return non_crit_avg * (1 - cr) + crit_avg * cr


big_bang_hit = hit_damage(skill_coefficient_base, True, dict(mastery=big_bang_mastery, mastery_boss=big_bang_boss_mastery), "BIG_BANG")
big_bang_dps = big_bang_hits * big_bang_hit * big_bang_per_second * target_multiplier("BIG_BANG") if unlocked("BIG_BANG") else 0.0

skill_dps = {}
for key, s in SKILLS.items():
    if not unlocked(key):
        skill_dps[key] = 0.0
        continue
    pct = coeff_pct(s["base"], s["fidx"], s["scales"], s["job_step"])
    hd = hit_damage(pct, False, s, key)
    if key == "ANGEL_RAY_BOSS_PROC":
        eff_cd = eff_cooldown(SKILLS["ANGEL_RAY"]["cooldown"], SKILLS["ANGEL_RAY"]["costs_action"])
        if fixed_duration_active:
            rate = exact_total_hits(eff_cd, s["hits"], s.get("icd"), s.get("window")) / fight_duration
        else:
            hits = s["hits"] * ((s["window"] / s["icd"]) if s.get("icd") else 1)
            rate = hits / eff_cd
        skill_dps[key] = rate * hd * (1 - normal_weight) if monster_type != "pvp" else rate * hd
        continue
    eff_cd = eff_cooldown(s["cooldown"], s["costs_action"])
    if fixed_duration_active:
        rate = exact_total_hits(eff_cd, s["hits"], s.get("icd"), s.get("window")) / fight_duration
    else:
        hits = s["hits"] * ((s["window"] / s["icd"]) if s.get("icd") else 1)
        rate = hits / eff_cd
    skill_dps[key] = rate * hd * target_multiplier(key)

# Triumph Feather: bespoke 2-stage steady-state proc (see build_bishop_workbook.py's own Note on
# this row for the full derivation). R = the character's total attack rate (Actions Per Second).
if unlocked("TRIUMPH_FEATHER"):
    tf_base = 1500
    tf_fidx = 12
    tf_pct = coeff_pct(tf_base, tf_fidx, True, 3) + level_gated_sum({73: 50})
    tf_hd = hit_damage(coeff_pct(tf_base, tf_fidx, True, 3), False, dict(mastery=level_gated_sum({73: 50})), "TRIUMPH_FEATHER")
    r_total = actions_per_second
    p1 = 25 if level >= 78 else 15
    d1 = 10
    harness_fraction = (p1 / 100 * r_total * d1) / (1 + p1 / 100 * r_total * d1)
    p2 = 35
    icd2 = 1
    feather_rate = (p2 / 100 * r_total) / (1 + icd2 * p2 / 100 * r_total)
    tf_targets = triumph_feather_targets
    tf_target_mult = (
        1 if monster_type == "pvp" else (1 - normal_weight) * 1 + normal_weight * min(tf_targets, max_enemies_hit)
    )
    tf_hits = 3 if level >= 104 else 2
    skill_dps["TRIUMPH_FEATHER"] = tf_hits * tf_hd * harness_fraction * feather_rate * tf_target_mult
else:
    skill_dps["TRIUMPH_FEATHER"] = 0.0

total_dps = big_bang_dps + sum(skill_dps.values())

print(f"Monster Damage Taken bonus % (Holy Fountain) = {monster_dmg_bonus:.6f}")
print(f"Normal Monster Damage bonus % (Holy Symbol) = {normal_dmg_bonus:.6f}")
print(f"Damage % bonus (Holy Symbol - Damage Boost) = {damage_bonus:.6f}")
print(f"Crit Damage % bonus (Blood of the Divine) = {crit_damage_bonus:.6f}")
print(f"Attack Speed bonus % = {as_bonus:.6f}")
print(f"Average buff multiplier = {avg_buff_mult:.6f}")
print(f"Actions/sec = {actions_per_second:.6f}")
print(f"Cast rate (subtracted) = {cast_rate:.6f}")
print(f"Big Bang casts/sec = {big_bang_per_second:.6f}")
print(f"Big Bang DPS = {big_bang_dps:.4f}")
for k, v in skill_dps.items():
    print(f"  {k:28s} DPS = {v:.4f}")
print(f"TOTAL DPS = {total_dps:.4f}")

# ---------------------------------------------------------------------------
# Cross-check against the actual live workbook (evaluated with `formulas`)
# ---------------------------------------------------------------------------
import formulas  # noqa: E402

print()
print(f"Loading live workbook: {XLSX_PATH}")
xl_model = formulas.ExcelModel().loads(str(XLSX_PATH)).finish()
solution = xl_model.calculate()


def scalar(value):
    return float(np.asarray(value).reshape(-1)[0])


def read_cell(sheet, cell):
    suffix = f"{sheet.upper()}'!{cell.upper()}"
    for k, v in solution.items():
        if k.upper().endswith(suffix):
            return scalar(v.value)
    raise KeyError(f"cell not found in workbook: {sheet}!{cell}")


py_skill_dps = dict(skill_dps)
py_skill_dps["BIG_BANG"] = big_bang_dps

xl_total = read_cell("SUMMARY", f"B{SUMMARY_ROW['TOTAL_DPS']}")
mismatches = []
print()
print(f"{'Skill':28s} {'Python DPS':>16s} {'Workbook DPS':>16s}  match")
for key, row in ROW.items():
    py_val = py_skill_dps.get(key, 0.0)
    xl_val = read_cell("CALC", f"O{row}")
    ok = np.isclose(py_val, xl_val, rtol=1e-6, atol=1e-3)
    print(f"{key:28s} {py_val:16.4f} {xl_val:16.4f}  {'OK' if ok else 'MISMATCH'}")
    if not ok:
        mismatches.append((key, py_val, xl_val))

print()
total_ok = np.isclose(total_dps, xl_total, rtol=1e-6, atol=1e-3)
print(f"{'TOTAL DPS':28s} {total_dps:16.4f} {xl_total:16.4f}  {'OK' if total_ok else 'MISMATCH'}")
if not total_ok:
    mismatches.append(("TOTAL DPS", total_dps, xl_total))

if mismatches:
    print(f"\n{len(mismatches)} mismatch(es) between the independent model and the live workbook.")
    sys.exit(1)
print("\nAll rows match between the independent model and the live workbook.")
