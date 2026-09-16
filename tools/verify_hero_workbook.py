#!/usr/bin/env python3
"""
Cross-checks Hero-DPS-Calculator.xlsx against an independent Python port of the same logic, using
the workbook's own default Inputs values. Then loads the live workbook with the `formulas` package
and diffs Total DPS + every per-skill DPS cell (Calc!O<row>) against this script's independent
numbers. Mirrors verify_bowmaster_workbook.py in structure and method.
"""
import json
import math
import re
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
XLSX_PATH = REPO / "Hero-DPS-Calculator.xlsx"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_hero_workbook import ROW, IN, UNLOCK_LEVEL, MAPLE_HERO_RATIOS, R_TOTAL  # noqa: E402

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
flat_str, str_pct, dex_stat = _in("flat_str"), _in("str_pct"), _in("dex")
stat_damage = (flat_str * (1 + str_pct / 100)) * 0.01 + dex_stat * 0.0025
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


def unlocked(key):
    threshold = UNLOCK_LEVEL.get(key)
    return threshold is None or level >= threshold


PVP_FIGHT_DURATION = 15


def eff_cooldown(cooldown, costs_action):
    if monster_type == "pvp":
        return PVP_FIGHT_DURATION
    return max(0.1, cooldown - (skill_cooldown_decrease if costs_action else 0))


def eff_duration(duration):
    return duration * (1 + buff_duration_increase_pct / 100)


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


def buff_avg(pct, duration, cooldown, costs_action):
    eff_cd = eff_cooldown(cooldown, costs_action)
    if fixed_duration_active:
        uptime = exact_buff_uptime(eff_cd, eff_duration(duration)) / fight_duration
    elif monster_type == "pvp":
        uptime = min(eff_duration(duration), PVP_FIGHT_DURATION) / PVP_FIGHT_DURATION
    else:
        uptime = eff_duration(duration) / eff_cd
    return pct * uptime


def target_multiplier(targets):
    if monster_type == "pvp":
        return 1
    targets = min(targets, max_enemies_hit)
    return (1 - normal_weight) * 1 + normal_weight * targets


def monster_blend(boss_val, normal_val):
    if monster_type == "pvp":
        return boss_val
    return (1 - normal_weight) * boss_val + normal_weight * normal_val


# ---- Helper rows (Final Attack, Advanced Final Attack, Maple Hero) — own D/E/F only, no
#      independent DPS. ----
final_attack_pct = (
    coeff_pct(350, 21, True, 2) + level_gated_sum({54: 50})
    if unlocked("FINAL_ATTACK_HELPER") else 0.0
)
advanced_final_attack_pct = (
    coeff_pct(5000, 21, True, 4) + level_gated_sum({113: 50})
    if unlocked("ADVANCED_FINAL_ATTACK_HELPER") else 0.0
)
maple_hero_pct = coeff_pct(200, 23, True, 4) if unlocked("MAPLE_HERO_HELPER") else 0.0

# Raging Blow's own coefficient includes Final Attack + Advanced Final Attack folded in, PLUS
# its own real Damage/Boss-Monster-Damage mastery chains (deltas, not raw displayed values).
raging_blow_final_attack_addition = (
    final_attack_pct / 100 * (1 + advanced_final_attack_pct / 100) * 25
    if unlocked("FINAL_ATTACK_HELPER") else 0.0
)
raging_blow_mastery_damage = level_gated_sum({102: 10, 106: 1, 116: 1, 120: 1, 128: 1, 132: 1})
raging_blow_mastery_boss_damage = level_gated_sum({111: 10, 124: 10})
raging_blow_pct = skill_coefficient_base + raging_blow_final_attack_addition + raging_blow_mastery_damage
raging_blow_targets = 6 + basic_attack_target_increase
RAGING_BLOW_HITS = 6 if level >= 136 else 5

# ---- Attack% bucket: Combo Attack (steady-state max stacks) + Spirit Blade (duty-cycle) ----
combo_stacks = 7 if level >= 110 else 5
combo_attack_pct = coeff_pct(40, 22, True, 2) if unlocked("COMBO_ATTACK") else 0.0
combo_attack_avg = combo_attack_pct * combo_stacks if unlocked("COMBO_ATTACK") else 0.0
spirit_blade_pct = coeff_pct(100, 21, True, 2) if unlocked("SPIRIT_BLADE") else 0.0
spirit_blade_avg = buff_avg(spirit_blade_pct, 20, 45, True) if unlocked("SPIRIT_BLADE") else 0.0

attack_bucket_mult = 1 + (combo_attack_avg + spirit_blade_avg) / 100

# ---- Combo Synergy (steady-state max stacks, Final Damage per stack) ----
combo_synergy_pct = coeff_pct(50, 22, True, 3) if unlocked("COMBO_SYNERGY") else 0.0
combo_synergy_avg = combo_synergy_pct * combo_stacks if unlocked("COMBO_SYNERGY") else 0.0

# ---- Enrage (fires on its own fixed interval, treated as this row's own Cooldown(s)) ----
enrage_fd_pct = coeff_pct(120, 22, True, 4) if unlocked("ENRAGE_FD") else 0.0
enrage_fd_avg = buff_avg(enrage_fd_pct, 7, 12, False) if unlocked("ENRAGE_FD") else 0.0
enrage_critdmg_pct = coeff_pct(150, 22, True, 4) if unlocked("ENRAGE_CRITDMG") else 0.0
enrage_critdmg_avg = buff_avg(enrage_critdmg_pct, 7, 12, False) if unlocked("ENRAGE_CRITDMG") else 0.0

crit_rate_bonus = 0.0  # no live Crit-Rate-buff source exists in this kit
crit_damage_bonus = enrage_critdmg_avg
final_damage_extra = enrage_fd_avg + combo_synergy_avg

# ---- Scaring Sword (proc-chance x duty-cycle, drives the Global Monster Damage-Taken Bonus%) ----
scaring_sword_pct = (
    coeff_pct(200, 21, True, 3) + level_gated_sum({78: 8})
    if unlocked("SCARING_SWORD") else 0.0
)
scaring_sword_proc_chance = 35
scaring_sword_avg = (
    scaring_sword_pct * (scaring_sword_proc_chance / 100) * buff_avg(1.0, 10, 30, True)
    if unlocked("SCARING_SWORD") else 0.0
)
monster_dmg_bonus = scaring_sword_avg

# ---- Nimble Feet (Attack Speed buff, duty-cycle averaged) ----
nimble_feet_pct = coeff_pct(150, 0, False, 1)
nimble_avg = buff_avg(nimble_feet_pct, 15, 60, True) if unlocked("NIMBLE_FEET") else 0.0
as_bonus = nimble_avg
actions_per_second = 1 + min(150, 150 * (1 - (1 - attack_speed_base / 150) * (1 - as_bonus / 150))) / 100

# ---- Cast rate (subtracted from Raging Blow) ----
COST_ACTION_ROWS = [
    ("PUNCTURE", 17, True, 1),
    ("ENHANCED_RAGING_BLOW", 17, True, 1),
    ("MAGIC_CRASH", 28, True, 1),
    ("BEAM_BLADE", 16, True, 1),
    ("RUSH", 22, True, 1),
    ("FLASH_SLASH", 16, True, 1),
    ("SPIRIT_BLADE", 45, True, 1),
    ("SCARING_SWORD", 30, True, 1),
    ("NIMBLE_FEET", 60, True, 1),
]
if fixed_duration_active:
    cast_rate = sum(exact_casts(eff_cooldown(cd, ca)) * aps for k, cd, ca, aps in COST_ACTION_ROWS if ca and unlocked(k)) / fight_duration
else:
    cast_rate = sum((1 / eff_cooldown(cd, ca)) * aps for k, cd, ca, aps in COST_ACTION_ROWS if ca and unlocked(k))
raging_blow_per_second = max(0, actions_per_second - cast_rate)


def hit_damage(coeff_pct_val, is_basic, mastery_boss, mastery_normal, maple_ratio=0.0, extra_fd_pct=0.0):
    base_damage = attack * (coeff_pct_val / 100)
    dmg_reduction = 5000 / (6000 + monster_defense * (1 - def_pen / 100))
    boss_term = boss_damage + mastery_boss + monster_dmg_bonus
    normal_term = normal_damage + mastery_normal + monster_dmg_bonus
    monster_dmg = 0 if monster_type == "pvp" else monster_blend(boss_term, normal_term)
    maple_mult = (1 + maple_ratio * maple_hero_pct / 100) if maple_ratio else 1.0
    final_mult = (1 + (final_damage + final_damage_extra) / 100) * maple_mult * (1 + extra_fd_pct / 100)
    source_pct = basic_attack_damage if is_basic else skill_damage
    base_hit = (
        base_damage * (1 + stat_damage / 100) * (1 + damage / 100) * (1 + monster_dmg / 100)
        * (1 + damage_amp / 100) * dmg_reduction * final_mult * (1 + source_pct / 100)
        * attack_bucket_mult
    )
    non_crit_min = base_hit * min(min_damage, max_damage) / 100
    non_crit_max = base_hit * max_damage / 100
    non_crit_avg = (non_crit_min + non_crit_max) / 2
    crit_avg = non_crit_avg * (1 + (crit_damage + crit_damage_bonus) / 100)
    cr = min(crit_rate + crit_rate_bonus, 100) / 100
    return non_crit_avg * (1 - cr) + crit_avg * cr


# ---- Raging Blow (basic attack) ----
raging_blow_hit = hit_damage(raging_blow_pct, True, raging_blow_mastery_boss_damage, 0)
raging_blow_dps = RAGING_BLOW_HITS * raging_blow_hit * raging_blow_per_second * target_multiplier(raging_blow_targets) if unlocked("RAGING_BLOW") else 0.0

# ---- Damage skills ----
puncture_targets = 5 + (5 if level >= 100 else 0)
puncture_mastery_boss = coeff_pct(100, 21, True, 4) + (20 if level >= 138 else 0)
enhanced_targets = 9 + (3 if level >= 100 else 0)
magic_crash_targets = 5 + (4 if level >= 100 else 0)

DAMAGE_SKILLS = {
    "PUNCTURE": dict(job_step=4, cooldown=17, hits=3, base=9000, fidx=12, scales=True,
                      mastery=level_gated_sum({122: 50}), mastery_boss=puncture_mastery_boss,
                      mastery_normal=0, costs_action=True, targets=puncture_targets),
    "PUNCTURE_WOUND": dict(job_step=4, cooldown=17, hits=1, icd=1, window=10, base=1500, fidx=12,
                            scales=True, mastery=0, mastery_boss=0, mastery_normal=0,
                            costs_action=False, targets=puncture_targets),
    "ENHANCED_RAGING_BLOW": dict(job_step=4, cooldown=17, hits=6, base=6105, fidx=12, scales=True,
                                  mastery=level_gated_sum({108: 50}), mastery_boss=100, mastery_normal=0,
                                  costs_action=True, targets=enhanced_targets),
    "MAGIC_CRASH": dict(job_step=4, cooldown=28, hits=1, base=48000, fidx=12, scales=True,
                         mastery=0, mastery_boss=0, mastery_normal=0, costs_action=True,
                         targets=magic_crash_targets),
    "BEAM_BLADE": dict(job_step=3, cooldown=16, hits=4, base=2500, fidx=12, scales=True,
                        mastery=0, mastery_boss=0, mastery_normal=0, costs_action=True,
                        targets=8, maple_ratio=MAPLE_HERO_RATIOS.get("BEAM_BLADE", 0)),
    "RUSH": dict(job_step=3, cooldown=22, hits=1, base=6000, fidx=12, scales=True,
                 mastery=0, mastery_boss=0, mastery_normal=0, costs_action=True,
                 targets=12, maple_ratio=MAPLE_HERO_RATIOS.get("RUSH", 0)),
    "FLASH_SLASH": dict(job_step=2, cooldown=16, hits=1, base=3500, fidx=0, scales=False,
                         mastery=level_gated_sum({39: 50}), mastery_boss=0, mastery_normal=0,
                         costs_action=True, targets=7, maple_ratio=MAPLE_HERO_RATIOS.get("FLASH_SLASH", 0)),
}
NORMAL_MONSTER_TARGETS = {k: v["targets"] for k, v in DAMAGE_SKILLS.items()}

skill_dps = {}
for key, s in DAMAGE_SKILLS.items():
    if not unlocked(key):
        skill_dps[key] = 0.0
        continue
    pct = coeff_pct(s["base"], s["fidx"], s["scales"], s["job_step"]) + s.get("mastery", 0)
    combo_excess_fd = (50 * max(0, (7 if level >= 110 else 5) - 5)) if (key == "ENHANCED_RAGING_BLOW" and level >= 134) else 0.0
    hd = hit_damage(
        pct, False, s.get("mastery_boss", 0), s.get("mastery_normal", 0),
        maple_ratio=s.get("maple_ratio", 0.0), extra_fd_pct=combo_excess_fd,
    )
    proc_prob = 1.0
    eff_cd = eff_cooldown(s["cooldown"], s["costs_action"])
    if fixed_duration_active:
        rate = exact_total_hits(eff_cd, s["hits"], s.get("icd"), s.get("window")) / fight_duration
    else:
        hits = s["hits"] * ((s["window"] / s["icd"]) if s.get("icd") else 1)
        rate = hits / eff_cd
    skill_dps[key] = proc_prob * rate * hd * target_multiplier(s["targets"])

total_dps = raging_blow_dps + sum(skill_dps.values())

print(f"Attack%% bucket multiplier = {attack_bucket_mult:.6f}")
print(f"Global Crit Damage Bonus % = {crit_damage_bonus:.6f}")
print(f"Global Final Damage Bonus % = {final_damage_extra:.6f}")
print(f"Global Monster Damage-Taken Bonus % = {monster_dmg_bonus:.6f}")
print(f"Actions/sec = {actions_per_second:.6f}")
print(f"Cast rate = {cast_rate:.6f}")
print(f"Raging Blow casts/sec = {raging_blow_per_second:.6f}")
print(f"Raging Blow DPS = {raging_blow_dps:.4f}")
for k, v in skill_dps.items():
    print(f"  {k:28s} DPS = {v:.4f}")
print(f"TOTAL DPS = {total_dps:.4f}")

# ---------------------------------------------------------------------------
# Cross-check against the actual live workbook
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
py_skill_dps["RAGING_BLOW"] = raging_blow_dps

xl_total = read_cell("SUMMARY", f"B{R_TOTAL}")
mismatches = []
print()
print(f"{'Skill':32s} {'Python DPS':>16s} {'Workbook DPS':>16s}  match")
for key, row in ROW.items():
    if key not in py_skill_dps:
        continue
    py_val = py_skill_dps.get(key, 0.0)
    xl_val = read_cell("CALC", f"O{row}")
    ok = np.isclose(py_val, xl_val, rtol=1e-6, atol=1e-3)
    print(f"{key:32s} {py_val:16.4f} {xl_val:16.4f}  {'OK' if ok else 'MISMATCH'}")
    if not ok:
        mismatches.append((key, py_val, xl_val))

print()
total_ok = np.isclose(total_dps, xl_total, rtol=1e-6, atol=1e-3)
print(f"{'TOTAL DPS':32s} {total_dps:16.4f} {xl_total:16.4f}  {'OK' if total_ok else 'MISMATCH'}")
if not total_ok:
    mismatches.append(("TOTAL DPS", total_dps, xl_total))

if mismatches:
    print(f"\n{len(mismatches)} mismatch(es) between the independent model and the live workbook.")
    sys.exit(1)
print("\nAll rows match between the independent model and the live workbook.")
