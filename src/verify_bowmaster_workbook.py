#!/usr/bin/env python3
"""
Cross-checks Bowmaster-DPS-Calculator.xlsx against an independent Python port of the same logic,
using the workbook's own default Inputs values. Then loads the live workbook with the `formulas`
package (a real formula evaluator, not just the static values openpyxl wrote) and diffs Total DPS
+ every per-skill DPS cell (Calc!O<row>) against this script's independent numbers. Mirrors the
sibling verify_*_workbook.py scripts in structure and method.
"""
import json
import math
import re
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
XLSX_PATH = REPO / "Bowmaster" / "Bowmaster-DPS-Calculator.xlsx"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_bowmaster_workbook import ROW, IN, UNLOCK_LEVEL, MAPLE_HERO_RATIOS, R_TOTAL  # noqa: E402

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
def _compute_monster_type(content_type):
    if content_type == "PvP":
        return "pvp"
    if content_type in ("Breakthrough", "Hero Dungeon"):
        return "breakthrough"
    if content_type in ("EXP Dungeon", "Equipment Dungeon", "Chapter Hunt"):
        return "normal"
    return "boss"


def _compute_breakthrough_stage_index(chapter, stage):
    if chapter == 28:
        return stage - 9
    return stage + 14 * max(0, min(chapter - 1, 38) - 28) + 19 * max(0, chapter - 39)


def _compute_monster_defense(content_type, chapter, stage, defense):
    if content_type == "Chapter Boss":
        return 3200 + 50 * (chapter - 28)
    if content_type == "World Boss":
        return 62100
    if content_type == "Weapon Dungeon":
        return stage * 50
    if content_type == "Enhancement Dungeon":
        return 950 + stage * 50
    if content_type in ("EXP Dungeon", "Equipment Dungeon"):
        return 250 + stage * 50
    if content_type == "Hero Dungeon":
        return 650 + stage * 50
    if content_type in ("Breakthrough", "Chapter Hunt"):
        return 4860 + 20 * _compute_breakthrough_stage_index(chapter, stage)
    return defense  # PvP fallback — manual, opponent-dependent


def _compute_fight_duration(content_type):
    return {
        "Chapter Hunt": 0, "Weapon Dungeon": 22, "Equipment Dungeon": 40,
        "Enhancement Dungeon": 25, "Hero Dungeon": 50, "EXP Dungeon": 40,
        "World Boss": 75, "Chapter Boss": 70, "Breakthrough": 40,
    }.get(content_type, 0)


content_type = _in("content_type")
chapter = _in("chapter")
stage = _in("stage")
defense = _in("defense")
monster_type = _compute_monster_type(content_type)
breakthrough_normal_weight_pct = _in("breakthrough_normal_weight_pct")
normal_weight = (
    1.0 if monster_type == "normal"
    else breakthrough_normal_weight_pct / 100 if monster_type == "breakthrough"
    else 0.0
)
skill1, skill2, skill3, skill4, skill_all = (
    _in("skill_lvl_1st"), _in("skill_lvl_2nd"), _in("skill_lvl_3rd"), _in("skill_lvl_4th"), _in("skill_lvl_all")
)
monster_defense = _compute_monster_defense(content_type, chapter, stage, defense)
flat_attack, attack_pct = _in("flat_attack"), _in("attack_pct")
attack = flat_attack * (1 + attack_pct / 100)
flat_dex, dex_pct, str_stat = _in("flat_dex"), _in("dex_pct"), _in("str")
stat_damage = (flat_dex * (1 + dex_pct / 100)) * 0.01 + str_stat * 0.0025
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
fight_duration = _compute_fight_duration(content_type)
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


# ---- Helper rows (Final Attack: Bow, Advanced Final Attack, Enchanted Quiver, Maple Hero,
#      Flash Mirage II) — own D/E/F only, no independent DPS. ----
final_attack_bow_pct = (
    coeff_pct(350, 21, True, 2) + level_gated_sum({52: 50})
    if unlocked("FINAL_ATTACK_BOW_HELPER") else 0.0
)
advanced_final_attack_pct = (
    coeff_pct(5000, 21, True, 4) + level_gated_sum({111: 50})
    if unlocked("ADVANCED_FINAL_ATTACK_HELPER") else 0.0
)
enchanted_quiver_pct = coeff_pct(3000, 21, True, 4) if unlocked("ENCHANTED_QUIVER_HELPER") else 0.0
maple_hero_pct = coeff_pct(250, 23, True, 4) if unlocked("MAPLE_HERO_HELPER") else 0.0
flash_mirage_ii_pct = coeff_pct(4000, 21, True, 4) if unlocked("FLASH_MIRAGE_II_HELPER") else 0.0

# Arrow Stream's own coefficient includes Final Attack: Bow + Advanced Final Attack folded in
# (see build_bowmaster_workbook.py's ARROW_STREAM row Note for the exact formula shape).
arrow_stream_final_attack_addition = (
    final_attack_bow_pct / 100 * (1 + advanced_final_attack_pct / 100) * 25
    if unlocked("FINAL_ATTACK_BOW_HELPER") else 0.0
)

# ---- Attack% bucket: Marksmanship (base + conditional) + Illusion Step, summed additively ----
marksmanship_base_pct = coeff_pct(100, 22, True, 3) if unlocked("MARKSMANSHIP_BASE") else 0.0
marksmanship_cond_pct_raw = coeff_pct(100, 22, True, 3) if unlocked("MARKSMANSHIP_COND") else 0.0
marksmanship_cond_avg = monster_blend(marksmanship_cond_pct_raw, 0.0) if unlocked("MARKSMANSHIP_COND") else 0.0
illusion_step_pct = coeff_pct(140, 22, True, 4) if unlocked("ILLUSION_STEP") else 0.0
illusion_step_avg = buff_avg(illusion_step_pct, 15, 24, False) if unlocked("ILLUSION_STEP") else 0.0

attack_bucket_mult = 1 + (marksmanship_base_pct + marksmanship_cond_avg + illusion_step_avg) / 100

# ---- Sharp Eyes (self-inclusive ally buff: flat 20 Crit Rate + scaling Crit Damage) ----
sharp_eyes_crit_damage_pct = coeff_pct(400, 21, True, 4) if unlocked("SHARP_EYES") else 0.0
sharp_eyes_uptime = (
    buff_avg(1.0, 18, 35, True) if unlocked("SHARP_EYES") else 0.0
)  # buff_avg(1,...) returns the uptime fraction itself
crit_rate_bonus = (20 * sharp_eyes_uptime) if unlocked("SHARP_EYES") else 0.0
sharp_eyes_crit_damage_avg = sharp_eyes_crit_damage_pct * sharp_eyes_uptime if unlocked("SHARP_EYES") else 0.0

# ---- Concentration (steady-state max stacks, 10 x 3% = 30% Crit Damage) ----
concentration_crit_damage = 30.0 if unlocked("CONCENTRATION") else 0.0
crit_damage_bonus = sharp_eyes_crit_damage_avg + concentration_crit_damage

monster_dmg_bonus = 0.0  # no global monster-damage-taken source exists in this kit

# ---- Mortal Blow (steady-state always-active Final Damage bonus) ----
mortal_blow_pct = coeff_pct(120, 22, True, 3) if unlocked("MORTAL_BLOW") else 0.0
mortal_blow_bonus = mortal_blow_pct if unlocked("MORTAL_BLOW") else 0.0

# ---- Nimble Feet (Attack Speed buff, duty-cycle averaged) ----
nimble_feet_pct = coeff_pct(150, 0, False, 1)
nimble_avg = buff_avg(nimble_feet_pct, 15, 60, True) if unlocked("NIMBLE_FEET") else 0.0
as_bonus = nimble_avg
actions_per_second = 1 + min(150, 150 * (1 - (1 - attack_speed_base / 150) * (1 - as_bonus / 150))) / 100

# Quiver Cartridge's own AS-scaled tick rate (English wiki wording: "up to 0.4 times based on
# Attack Speed"), same 150%-AS cap as actions_per_second above.
quiver_cartridge_tick_mult = 1 + 0.4 * (actions_per_second - 1) * 100 / 150
quiver_cartridge_cooldown = 1 / quiver_cartridge_tick_mult

# ---- Cast rate (subtracted from Arrow Stream) ----
COST_ACTION_ROWS = [
    ("COVERING_FIRE", 19, True, 1),
    ("PHOENIX", (60 * 0.6) if level >= 102 else 60, True, 1),
    ("ARROW_PLATTER", 40, True, 1),
    ("SHARP_EYES", 35, True, 1),
    ("NIMBLE_FEET", 60, True, 1),
]
if fixed_duration_active:
    cast_rate = sum(exact_casts(eff_cooldown(cd, ca)) * aps for k, cd, ca, aps in COST_ACTION_ROWS if ca and unlocked(k)) / fight_duration
else:
    cast_rate = sum((1 / eff_cooldown(cd, ca)) * aps for k, cd, ca, aps in COST_ACTION_ROWS if ca and unlocked(k))
arrow_stream_per_second = max(0, actions_per_second - cast_rate)


def hit_damage(coeff_pct_val, is_basic, mastery_boss, mastery_normal, maple_ratio=0.0, extra_fd_pct=0.0):
    base_damage = attack * (coeff_pct_val / 100)
    dmg_reduction = 5000 / (6000 + monster_defense * (1 - def_pen / 100))
    boss_term = boss_damage + mastery_boss + monster_dmg_bonus
    normal_term = normal_damage + mastery_normal + monster_dmg_bonus
    monster_dmg = 0 if monster_type == "pvp" else monster_blend(boss_term, normal_term)
    maple_mult = (1 + maple_ratio * maple_hero_pct / 100) if maple_ratio else 1.0
    extra_fd_mult = (1 + extra_fd_pct / 100)
    final_mult = (1 + (final_damage + mortal_blow_bonus) / 100) * maple_mult * extra_fd_mult
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


# ---- Arrow Stream (basic attack) ----
arrow_stream_mastery_damage = level_gated_sum({98: 10, 104: 1, 113: 1, 118: 1, 126: 1, 130: 1})
arrow_stream_mastery_boss_damage = level_gated_sum({108: 10, 122: 10})
arrow_stream_pct = skill_coefficient_base + arrow_stream_final_attack_addition + arrow_stream_mastery_damage
arrow_stream_targets = 6 + basic_attack_target_increase
arrow_stream_hit = hit_damage(arrow_stream_pct, True, arrow_stream_mastery_boss_damage, 0)
ARROW_STREAM_HITS = 6 if level >= 134 else 5
arrow_stream_dps = ARROW_STREAM_HITS * arrow_stream_hit * arrow_stream_per_second * target_multiplier(arrow_stream_targets) if unlocked("ARROW_STREAM") else 0.0

# ---- Damage skills ----
DAMAGE_SKILLS = {
    "COVERING_FIRE": dict(job_step=1, cooldown=19, hits=3, base=2500, fidx=12, scales=True,
                           mastery=level_gated_sum({39: 50}), mastery_boss=0, mastery_normal=0,
                           costs_action=True, targets=1, maple_ratio=MAPLE_HERO_RATIOS.get("COVERING_FIRE", 0)),
    "QUIVER_CARTRIDGE": dict(job_step=3, cooldown=quiver_cartridge_cooldown, hits=(3 + (3 if level >= 107 else 0)), base=500, fidx=21,
                              scales=True, mastery=0, mastery_boss=0, mastery_normal=200,
                              costs_action=False, targets=(3 + (3 if level >= 107 else 0)),
                              extra_fd=enchanted_quiver_pct if unlocked("ENCHANTED_QUIVER_HELPER") else 0.0),
    "PHOENIX": dict(job_step=3, cooldown=(60 * 0.6) if level >= 102 else 60,
                     hits=1,
                     icd=(3 * 0.7) if level >= 80 else 3, window=30 if level >= 102 else 20,
                     base=6000, fidx=12, scales=True, mastery=0, mastery_boss=0,
                     mastery_normal=100 if level >= 92 else 0, costs_action=True,
                     targets=5 + (3 if level >= 76 else 0),
                     maple_ratio=MAPLE_HERO_RATIOS.get("PHOENIX", 0)),
    "ARROW_PLATTER": dict(job_step=3, cooldown=40, hits=1, icd=0.3, window=60, base=500, fidx=12,
                           scales=True, mastery=0, mastery_boss=0, mastery_normal=200,
                           costs_action=True, targets=(3 + (1 if level >= 98 else 0)),
                           maple_ratio=MAPLE_HERO_RATIOS.get("ARROW_PLATTER", 0)),
    "FLASH_MIRAGE": dict(job_step=3, cooldown=5, hits=1, base=50, fidx=0, scales=False,
                          mastery=0, mastery_boss=0, mastery_normal=0, costs_action=False,
                          targets=(5 + (1 if level >= 136 else 0)), proc_chance=20,
                          extra_fd=flash_mirage_ii_pct if unlocked("FLASH_MIRAGE_II_HELPER") else 0.0),
}
NORMAL_MONSTER_TARGETS = {k: v["targets"] for k, v in DAMAGE_SKILLS.items()}

skill_dps = {}
for key, s in DAMAGE_SKILLS.items():
    if not unlocked(key):
        skill_dps[key] = 0.0
        continue
    pct = coeff_pct(s["base"], s["fidx"], s["scales"], s["job_step"]) + s.get("mastery", 0)
    hd = hit_damage(
        pct, False, s.get("mastery_boss", 0), s.get("mastery_normal", 0),
        maple_ratio=s.get("maple_ratio", 0.0), extra_fd_pct=s.get("extra_fd", 0.0),
    )
    proc_prob = 1 - (1 - s.get("proc_chance", 100) / 100) ** 1
    eff_cd = eff_cooldown(s["cooldown"], s["costs_action"])
    if fixed_duration_active:
        rate = exact_total_hits(eff_cd, s["hits"], s.get("icd"), s.get("window")) / fight_duration
    else:
        hits = s["hits"] * ((s["window"] / s["icd"]) if s.get("icd") else 1)
        rate = hits / eff_cd
    skill_dps[key] = proc_prob * rate * hd * target_multiplier(s["targets"])

total_dps = arrow_stream_dps + sum(skill_dps.values())

print(f"Attack%% bucket multiplier = {attack_bucket_mult:.6f}")
print(f"Global Crit Rate Bonus % = {crit_rate_bonus:.6f}")
print(f"Global Crit Damage Bonus % = {crit_damage_bonus:.6f}")
print(f"Global Final Damage Bonus % (Mortal Blow) = {mortal_blow_bonus:.6f}")
print(f"Actions/sec = {actions_per_second:.6f}")
print(f"Cast rate = {cast_rate:.6f}")
print(f"Arrow Stream casts/sec = {arrow_stream_per_second:.6f}")
print(f"Arrow Stream DPS = {arrow_stream_dps:.4f}")
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
py_skill_dps["ARROW_STREAM"] = arrow_stream_dps

xl_total = read_cell("SUMMARY", f"B{R_TOTAL}")
mismatches = []
print()
print(f"{'Skill':32s} {'Python DPS':>16s} {'Workbook DPS':>16s}  match")
for key, row in ROW.items():
    if key not in py_skill_dps:
        continue  # helper/passive rows never post an O-column DPS value
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
