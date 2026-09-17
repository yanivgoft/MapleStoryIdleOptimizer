#!/usr/bin/env python3
"""
Cross-checks Buccaneer-DPS-Calculator.xlsx against an independent Python port of the same logic,
using the workbook's own default Inputs values. Then loads the live workbook with the `formulas`
package and diffs Total DPS + every per-skill DPS cell (Calc!O<row>) against this script's
independent numbers. Mirrors verify_hero_workbook.py in structure and method.
"""
import json
import math
import re
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
XLSX_PATH = REPO / "Buccaneer" / "Buccaneer-DPS-Calculator.xlsx"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_buccaneer_workbook import ROW, IN, UNLOCK_LEVEL, MAPLE_HERO_RATIOS, R_TOTAL, R_BAPS  # noqa: E402

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


def buff_avg(pct, duration, cooldown, costs_action):
    eff_cd = eff_cooldown(cooldown, costs_action)
    if fixed_duration_active:
        casts = exact_casts(eff_cd)
        remaining_after_last = max(0.0, fight_duration - (casts - 1) * eff_cd)
        last_uptime = min(eff_duration(duration), remaining_after_last)
        uptime = ((casts - 1) * eff_duration(duration) + last_uptime) / fight_duration
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


def coeff_pct(base, fidx, scales, job_step):
    lvl = input_level(job_step, level, skill1, skill2, skill3, skill4, skill_all)
    if not scales:
        return base / 10
    return (base / 10) * (get_factor(lvl, fidx) / 1000)


# ---- Maple Hero (Serpent Assault only — the wiki's own source is truncated, see build script) ----
maple_hero_pct = coeff_pct(600, 23, True, 4) if unlocked("MAPLE_HERO_HELPER") else 0.0

# ---- Assault Mode duty-cycle economy (see build script's assault_uptime_expr for derivation) ----
hook_bomber_targets = 6 + basic_attack_target_increase
HOOK_BOMBER_HITS = 6 if level >= 136 else 5
hook_bomber_mastery_damage = level_gated_sum({102: 10, 106: 1, 116: 1, 120: 1, 128: 1, 132: 1})
hook_bomber_mastery_boss_damage = level_gated_sum({111: 10, 124: 10})
hook_bomber_pct = skill_coefficient_base + hook_bomber_mastery_damage


def _actions_per_second_placeholder():
    # Actions Per Second has no live AS-buff source in this kit (no Nimble-Feet-equivalent),
    # so it's just a function of the raw Inputs!attack_speed value.
    return 1 + min(150, 150 * (attack_speed_base / 150)) / 100


# Two-step resolution: Hook Bomber's cast rate (BAPS) feeds the Assault-Mode uptime fraction,
# which in turn is needed for Sea Serpent Burst/Serpent Assault's own trigger weighting — but
# BAPS itself only depends on the ACTION-COSTING skills' own cast rates, none of which depend on
# the Assault-Mode uptime, so there's no real circularity, just an ordering requirement.
actions_per_second = _actions_per_second_placeholder()


def assault_duration():
    return 10 + (5 if level >= 94 else 0)


def scale_gain_rate(baps):
    return baps * (2 if level >= 104 else 1)


def assault_uptime(baps):
    dur = assault_duration()
    rate = scale_gain_rate(baps)
    return dur / (dur + 5 / rate)


# ---- Cast rate (subtracted from Hook Bomber) — action-costing skills only ----
COST_ACTION_ROWS = [
    ("CORKSCREW_BLOW", 20, True, 1),
    ("OCTOPUNCH", 15, True, 1),
    ("NAUTILUS_STRIKE", 45, True, 1),
]
if fixed_duration_active:
    cast_rate = sum(exact_casts(eff_cooldown(cd, ca)) * aps for k, cd, ca, aps in COST_ACTION_ROWS if ca and unlocked(k)) / fight_duration
else:
    cast_rate = sum((1 / eff_cooldown(cd, ca)) * aps for k, cd, ca, aps in COST_ACTION_ROWS if ca and unlocked(k))
hook_bomber_per_second = max(0, actions_per_second - cast_rate)

uptime = assault_uptime(hook_bomber_per_second)

# ---- Global Final Damage bucket: Serpent Scale (Assault-Mode-gated) + Crossbones + Time Leap +
#      Speed Infusion (live AS-linked formula) ----
serpent_scale_pct = coeff_pct(250, 22, True, 2) if unlocked("SERPENT_SCALE_FD") else 0.0
serpent_scale_avg = serpent_scale_pct * uptime if unlocked("SERPENT_SCALE_FD") else 0.0
crossbones_pct = coeff_pct(100, 22, True, 4) if unlocked("CROSSBONES_FD") else 0.0
time_leap_pct = coeff_pct(150, 22, True, 4) if unlocked("TIME_LEAP_FD") else 0.0
speed_infusion_avg = 20 * (actions_per_second - 1) if level >= 110 else 0.0
final_damage_extra = serpent_scale_avg + crossbones_pct + time_leap_pct + speed_infusion_avg

# ---- Attack% bucket: Roll of the Dice's dice component only (always-active, no cooldown known) ----
roll_of_dice_pct = coeff_pct(25, 0, False, 2) if unlocked("ROLL_OF_THE_DICE_DICE") else 0.0
attack_bucket_mult = 1 + roll_of_dice_pct / 100

crit_rate_bonus = 0.0
crit_damage_bonus = 0.0
monster_dmg_bonus = 0.0


def hit_damage(coeff_pct_val, is_basic, mastery_boss, mastery_normal, maple_ratio=0.0):
    base_damage = attack * (coeff_pct_val / 100)
    dmg_reduction = 5000 / (6000 + monster_defense * (1 - def_pen / 100))
    boss_term = boss_damage + mastery_boss + monster_dmg_bonus
    normal_term = normal_damage + mastery_normal + monster_dmg_bonus
    monster_dmg = 0 if monster_type == "pvp" else monster_blend(boss_term, normal_term)
    maple_mult = (1 + maple_ratio * maple_hero_pct / 100) if maple_ratio else 1.0
    final_mult = (1 + (final_damage + final_damage_extra) / 100) * maple_mult
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


# ---- Hook Bomber (basic attack) ----
hook_bomber_hit = hit_damage(hook_bomber_pct, True, hook_bomber_mastery_boss_damage, 0)
hook_bomber_dps = HOOK_BOMBER_HITS * hook_bomber_hit * hook_bomber_per_second * target_multiplier(hook_bomber_targets) if unlocked("HOOK_BOMBER") else 0.0

# ---- Sea Serpent Burst / Serpent Assault (ride on Hook Bomber's own cast rate, weighted by the
#      Assault-Mode duty cycle instead of a real ProcChance% RNG) ----
sea_serpent_burst_pct = coeff_pct(1300, 12, True, 2) if unlocked("SEA_SERPENT_BURST") else 0.0
sea_serpent_burst_hit = hit_damage(sea_serpent_burst_pct, False, 0, 0)
sea_serpent_burst_dps = (
    2 * sea_serpent_burst_hit * hook_bomber_per_second * (1 - uptime) * target_multiplier(5)
    if unlocked("SEA_SERPENT_BURST") else 0.0
)

serpent_assault_pct = coeff_pct(4800, 12, True, 2) if unlocked("SERPENT_ASSAULT") else 0.0
serpent_assault_hit = hit_damage(serpent_assault_pct, False, 0, 0, maple_ratio=MAPLE_HERO_RATIOS.get("SERPENT_ASSAULT", 0))
serpent_assault_dps = (
    3 * serpent_assault_hit * hook_bomber_per_second * uptime * target_multiplier(12)
    if unlocked("SERPENT_ASSAULT") else 0.0
)

# ---- Other damage skills ----
DAMAGE_SKILLS = {
    "CORKSCREW_BLOW": dict(job_step=3, cooldown=20, hits=2, base=3400, fidx=12, scales=True,
                            mastery=level_gated_sum({73: 80}), mastery_boss=0, mastery_normal=0,
                            costs_action=True, targets=7),
    "OCTOPUNCH": dict(job_step=4, cooldown=15,
                       hits=(5 if monster_type in ("boss", "pvp") else 3),
                       base=9000, fidx=12, scales=True,
                       mastery=level_gated_sum({108: 50}), mastery_boss=0, mastery_normal=0,
                       costs_action=True, targets=4),
    "SEA_SERPENTS_RAGE": dict(job_step=4, cooldown=15, hits=2, base=17000, fidx=12, scales=True,
                               mastery=0, mastery_boss=0, mastery_normal=0,
                               costs_action=False, targets=8),
    "RAGING_SERPENT_ASSAULT": dict(job_step=4, cooldown=15, hits=1, icd=1, window=5, base=13000,
                                    fidx=12, scales=True, mastery=0, mastery_boss=0, mastery_normal=0,
                                    costs_action=False, targets=9, proc_chance=uptime),
    "NAUTILUS_STRIKE": dict(job_step=4, cooldown=45, hits=5, base=19500, fidx=12, scales=True,
                             mastery=0, mastery_boss=0, mastery_normal=0,
                             costs_action=True, targets=15),
    "NAUTILUS_FINAL_ATTACK": dict(job_step=4, cooldown=1, hits=1, base=8500, fidx=21, scales=True,
                                   mastery=0, mastery_boss=0, mastery_normal=0,
                                   costs_action=False, targets=1, proc_chance=0.30),
}
NORMAL_MONSTER_TARGETS = {k: v["targets"] for k, v in DAMAGE_SKILLS.items()}

skill_dps = {}
for key, s in DAMAGE_SKILLS.items():
    if not unlocked(key):
        skill_dps[key] = 0.0
        continue
    pct = coeff_pct(s["base"], s["fidx"], s["scales"], s["job_step"]) + s.get("mastery", 0)
    hd = hit_damage(pct, False, s.get("mastery_boss", 0), s.get("mastery_normal", 0))
    proc_prob = s.get("proc_chance", 1.0)
    eff_cd = eff_cooldown(s["cooldown"], s["costs_action"])
    if fixed_duration_active:
        rate = exact_total_hits(eff_cd, s["hits"], s.get("icd"), s.get("window")) / fight_duration
    else:
        hits = s["hits"] * ((s["window"] / s["icd"]) if s.get("icd") else 1)
        rate = hits / eff_cd
    skill_dps[key] = proc_prob * rate * hd * target_multiplier(s["targets"])

total_dps = hook_bomber_dps + sea_serpent_burst_dps + serpent_assault_dps + sum(skill_dps.values())

print(f"Attack%% bucket multiplier = {attack_bucket_mult:.6f}")
print(f"Global Final Damage Bonus % = {final_damage_extra:.6f}")
print(f"Actions/sec = {actions_per_second:.6f}")
print(f"Cast rate = {cast_rate:.6f}")
print(f"Hook Bomber casts/sec = {hook_bomber_per_second:.6f}")
print(f"Assault Mode uptime = {uptime:.6f}")
print(f"Hook Bomber DPS = {hook_bomber_dps:.4f}")
print(f"Sea Serpent Burst DPS = {sea_serpent_burst_dps:.4f}")
print(f"Serpent Assault DPS = {serpent_assault_dps:.4f}")
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
py_skill_dps["HOOK_BOMBER"] = hook_bomber_dps
py_skill_dps["SEA_SERPENT_BURST"] = sea_serpent_burst_dps
py_skill_dps["SERPENT_ASSAULT"] = serpent_assault_dps

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
