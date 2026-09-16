#!/usr/bin/env python3
"""
Cross-checks Shadower-DPS-Calculator.xlsx against an independent Python port of the same logic,
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
XLSX_PATH = REPO / "Shadower" / "Shadower-DPS-Calculator.xlsx"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_shadower_workbook import ROW, IN, UNLOCK_LEVEL, MAPLE_HERO_SHADOWER_RATIOS, R_TOTAL  # noqa: E402

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
flat_luk, luk_pct, dex = _in("flat_luk"), _in("luk_pct"), _in("dex")
stat_damage = (flat_luk * (1 + luk_pct / 100)) * 0.01 + dex * 0.0025
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
incoming_hit_rate = _in("incoming_hit_rate")

fixed_duration_active = monster_type != "pvp" and fight_duration > 0

basic_lvl = input_level(4, level, skill1, skill2, skill3, skill4, skill_all)
skill_coefficient_base = 290 * get_factor(basic_lvl, 21) / 1000
print(f"SKILL_COEFFICIENT (base) = {skill_coefficient_base:.4f}")


def level_gated_sum(pairs):
    return sum(inc for lvl, inc in pairs.items() if level >= lvl)


cruel_stab_mastery = level_gated_sum({102: 10, 106: 1, 116: 1, 120: 1, 128: 1, 132: 1})
cruel_stab_boss_mastery = level_gated_sum({111: 10, 124: 10})
cruel_stab_hits = 6 if level >= 136 else 5

dark_flare_cooldown = (45 * 0.7) if level >= 92 else 45
dark_flare_hits = 3 if level >= 76 else 2
dark_flare_icd = (2 * 0.75) if level >= 104 else 2
bm_target_mult = 3 if level >= 138 else (2 if level >= 122 else 1)


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


DAMAGE_SKILLS = {
    "PHASE_DASH": dict(job_step=3, cooldown=23, hits=2, base=4500, fidx=12, scales=True,
                        mastery=level_gated_sum({73: 80}), mastery_boss=0, mastery_normal=0,
                        costs_action=True, targets=9),
    "DARK_FLARE": dict(job_step=3, cooldown=dark_flare_cooldown, hits=dark_flare_hits, icd=dark_flare_icd,
                        window=20, base=3300, fidx=12, scales=True, mastery=0, mastery_boss=0,
                        mastery_normal=0, costs_action=True, targets=8),
    "VENOM": dict(job_step=3, cooldown=1, hits=1, base=450, fidx=21, scales=True,
                  mastery=0, mastery_boss=0, mastery_normal=0, costs_action=False, targets=1),
    "SUDDEN_RAID_BURST": dict(job_step=4, cooldown=19, hits=3, base=14000, fidx=12, scales=True,
                               mastery=level_gated_sum({126: 50}), mastery_boss=0, mastery_normal=0,
                               costs_action=True, targets=8),
    "SUDDEN_RAID_DOT": dict(job_step=4, cooldown=19, hits=1, icd=1, window=5, base=3600, fidx=12,
                             scales=True, mastery=0, mastery_boss=0, mastery_normal=0,
                             costs_action=False, targets=8),
}
NORMAL_MONSTER_TARGETS = {k: v["targets"] for k, v in DAMAGE_SKILLS.items()}


def target_multiplier(targets):
    if monster_type == "pvp":
        return 1
    targets = min(targets, max_enemies_hit)
    return (1 - normal_weight) * 1 + normal_weight * targets


def hit_damage(coeff_pct_val, is_basic, mastery_boss, mastery_normal, maple_ratio=0.0):
    base_damage = attack * (coeff_pct_val / 100)
    dmg_reduction = 5000 / (6000 + monster_defense * (1 - def_pen / 100))
    if monster_type == "pvp":
        monster_dmg = 0
    else:
        boss_term = boss_damage + mastery_boss + monster_dmg_bonus
        normal_term = normal_damage + mastery_normal + monster_dmg_bonus
        monster_dmg = (1 - normal_weight) * boss_term + normal_weight * normal_term
    maple_mult = (1 + maple_ratio * maple_hero_pct / 100) if maple_ratio else 1.0
    final_mult = (1 + final_damage / 100) * maple_mult
    source_pct = basic_attack_damage if is_basic else skill_damage
    extra_mult = avg_buff_mult * shadow_partner_mult
    base_hit = (
        base_damage * (1 + stat_damage / 100) * (1 + damage / 100) * (1 + monster_dmg / 100)
        * (1 + damage_amp / 100) * dmg_reduction * final_mult * (1 + source_pct / 100) * extra_mult
    )
    non_crit_min = base_hit * min(min_damage, max_damage) / 100
    non_crit_max = base_hit * max_damage / 100
    non_crit_avg = (non_crit_min + non_crit_max) / 2
    crit_avg = non_crit_avg * (1 + (crit_damage + crit_damage_bonus) / 100)
    cr = min(crit_rate + crit_rate_bonus, 100) / 100
    return non_crit_avg * (1 - cr) + crit_avg * cr


# ---- Buffs (Dark Sight Attack, Into Darkness, Smokescreen FD), Dark Sight Crit Rate, Venom
#      Weaken, Shadow Partner, Nimble Feet / Steal AS ----
dark_sight_crit_duration = 12 if level >= 24 else 8
dark_sight_atk_duration = 12 if level >= 24 else 8
dsc_pct = coeff_pct(60, 21, True, 1) if unlocked("DARK_SIGHT_CRIT") else 0.0
dsa_pct = coeff_pct(100, 21, True, 1) if unlocked("DARK_SIGHT_ATK") else 0.0
id_pct = coeff_pct(200, 21, True, 3) if unlocked("INTO_DARKNESS") else 0.0
ss_pct = coeff_pct(130, 22, True, 4) if unlocked("SMOKESCREEN") else 0.0


def buff_avg(pct, duration, cooldown, costs_action):
    eff_cd = eff_cooldown(cooldown, costs_action)
    if fixed_duration_active:
        uptime = exact_buff_uptime(eff_cd, eff_duration(duration)) / fight_duration
    elif monster_type == "pvp":
        uptime = min(eff_duration(duration), PVP_FIGHT_DURATION) / PVP_FIGHT_DURATION
    else:
        uptime = eff_duration(duration) / eff_cd
    return pct * uptime


dark_sight_crit_avg = buff_avg(dsc_pct, dark_sight_crit_duration, 25, False) if unlocked("DARK_SIGHT_CRIT") else 0.0
dark_sight_atk_avg = buff_avg(dsa_pct, dark_sight_atk_duration, 25, True) if unlocked("DARK_SIGHT_ATK") else 0.0
into_darkness_avg = buff_avg(id_pct, 13, 40, True) if unlocked("INTO_DARKNESS") else 0.0
smokescreen_avg = buff_avg(ss_pct, 20, 45, True) if unlocked("SMOKESCREEN") else 0.0

avg_buff_mult = (1 + dark_sight_atk_avg / 100) * (1 + into_darkness_avg / 100) * (1 + smokescreen_avg / 100)
crit_rate_bonus = dark_sight_crit_avg
monster_dmg_bonus = 15 if level >= 82 else 0
crit_damage_bonus = (30 * buff_avg(1, 20, 45, True) / 1) if unlocked("SMOKESCREEN") and level >= 113 else 0.0
# crit_damage_bonus uses the SAME uptime as Smokescreen's own buff (30 * uptime_fraction)
smokescreen_eff_cd = eff_cooldown(45, True)
if fixed_duration_active:
    smokescreen_uptime = exact_buff_uptime(smokescreen_eff_cd, eff_duration(20)) / fight_duration
elif monster_type == "pvp":
    smokescreen_uptime = min(eff_duration(20), PVP_FIGHT_DURATION) / PVP_FIGHT_DURATION
else:
    smokescreen_uptime = eff_duration(20) / smokescreen_eff_cd
crit_damage_bonus = (30 * smokescreen_uptime) if level >= 113 else 0.0

maple_hero_pct = coeff_pct(150, 23, True, 4) if unlocked("MAPLE_HERO_SHADOWER") else 0.0

sp_pct = coeff_pct(840, 21, True, 3) + level_gated_sum({68: 100}) if unlocked("SHADOW_PARTNER") else 0.0
sp_maple_ratio = MAPLE_HERO_SHADOWER_RATIOS["SHADOW_PARTNER"]
sp_pct_with_maple = sp_pct * (1 + sp_maple_ratio * maple_hero_pct / 100)
shadow_partner_mult = 1 + (sp_pct_with_maple * 1.0 * 25 / 100) / 100 if unlocked("SHADOW_PARTNER") else 1.0

steal_pct = coeff_pct(50, 22, True, 2) if unlocked("STEAL") else 0.0
steal_avg = steal_pct * 3 if unlocked("STEAL") else 0.0
nimble_feet_pct = coeff_pct(150, 0, False, 1)
nimble_avg = buff_avg(nimble_feet_pct, 15, 60, True) if unlocked("NIMBLE_FEET") else 0.0
as_bonus = nimble_avg + steal_avg
actions_per_second = 1 + min(150, 150 * (1 - (1 - attack_speed_base / 150) * (1 - as_bonus / 150))) / 100

# ---- Cast rate (subtracted from Cruel Stab) ----
COST_ACTION_ROWS = [
    ("DARK_FLARE", dark_flare_cooldown, True, 1),
    ("VENOM", 1, False, 1),
    ("SUDDEN_RAID_BURST", 19, True, 1),
    ("PHASE_DASH", 23, True, 1),
    ("INTO_DARKNESS", 40, True, 1),
    ("ASSASSINATE", 13, True, 1),
    ("MESO_EXPLOSION", 11, True, 1),
    ("SMOKESCREEN", 45, True, 1),
    ("NIMBLE_FEET", 60, True, 1),
    ("DARK_SIGHT_ATK", 25, True, 2),
]
if fixed_duration_active:
    cast_rate = sum(exact_casts(eff_cooldown(cd, ca)) * aps for k, cd, ca, aps in COST_ACTION_ROWS if ca and unlocked(k)) / fight_duration
else:
    cast_rate = sum((1 / eff_cooldown(cd, ca)) * aps for k, cd, ca, aps in COST_ACTION_ROWS if ca and unlocked(k))
cruel_stab_per_second = max(0, actions_per_second - cast_rate)

cruel_stab_hit = hit_damage(skill_coefficient_base + cruel_stab_mastery, True, cruel_stab_boss_mastery, 0)
cruel_stab_dps = cruel_stab_hits * cruel_stab_hit * cruel_stab_per_second * target_multiplier(6 + basic_attack_target_increase) if unlocked("CRUEL_STAB") else 0.0

skill_dps = {}
for key, s in DAMAGE_SKILLS.items():
    if not unlocked(key):
        skill_dps[key] = 0.0
        continue
    pct = coeff_pct(s["base"], s["fidx"], s["scales"], s["job_step"]) + s.get("mastery", 0)
    maple_ratio = MAPLE_HERO_SHADOWER_RATIOS.get(key, 0.0)
    hd = hit_damage(pct, False, s.get("mastery_boss", 0), s.get("mastery_normal", 0), maple_ratio=maple_ratio)
    eff_cd = eff_cooldown(s["cooldown"], s["costs_action"])
    if fixed_duration_active:
        rate = exact_total_hits(eff_cd, s["hits"], s.get("icd"), s.get("window")) / fight_duration
    else:
        hits = s["hits"] * ((s["window"] / s["icd"]) if s.get("icd") else 1)
        rate = hits / eff_cd
    skill_dps[key] = rate * hd * target_multiplier(s["targets"])

# ---- Toxic Venom ----
TOXIC_VENOM_TRIGGER_SKILLS = {"PHASE_DASH", "DARK_FLARE", "SUDDEN_RAID_BURST", "SUDDEN_RAID_DOT"}
if unlocked("TOXIC_VENOM"):
    total_hit_rate = cruel_stab_hits * cruel_stab_per_second * target_multiplier(6 + basic_attack_target_increase)
    for key, s in DAMAGE_SKILLS.items():
        if key in TOXIC_VENOM_TRIGGER_SKILLS and unlocked(key):
            eff_cd = eff_cooldown(s["cooldown"], s["costs_action"])
            if fixed_duration_active:
                rate = exact_total_hits(eff_cd, s["hits"], s.get("icd"), s.get("window")) / fight_duration
            else:
                hits = s["hits"] * ((s["window"] / s["icd"]) if s.get("icd") else 1)
                rate = hits / eff_cd
            total_hit_rate += rate * target_multiplier(s["targets"])
    if unlocked("ASSASSINATE"):
        _asn_eff_cd = eff_cooldown(13, True)
        if fixed_duration_active:
            _asn_rate = exact_total_hits(_asn_eff_cd, 2, None, None) / fight_duration
        else:
            _asn_rate = 2 / _asn_eff_cd
        total_hit_rate += _asn_rate * target_multiplier(1)
    # Meso Explosion / Blood Money own hit rates added below once computed
else:
    total_hit_rate = 0.0

# ---- Shadow Shifter ----
ss_counter_pct = coeff_pct(25000, 21, True, 4) if unlocked("SHADOW_SHIFTER") else 0.0
shadow_shifter_dps = incoming_hit_rate * 0.2 * hit_damage(ss_counter_pct, False, 0, 0) if unlocked("SHADOW_SHIFTER") else 0.0

# ---- Meso Explosion / Blood Money (steady-state stack accumulation) ----
meso_stack_avg = min(10, 0.5 * actions_per_second * 11)
bm_stack_avg = min(5, 0.25 * actions_per_second * 11)

meso_pct = (coeff_pct(2700, 12, True, 3) + level_gated_sum({90: 100})) if unlocked("MESO_EXPLOSION") else 0.0
meso_hd = hit_damage(meso_pct, False, 0, 0)
meso_rate = (1 / eff_cooldown(11, True)) if not fixed_duration_active else (exact_casts(eff_cooldown(11, True)) / fight_duration)
meso_dps = 3 * meso_hd * meso_rate * target_multiplier(meso_stack_avg) if unlocked("MESO_EXPLOSION") else 0.0
skill_dps["MESO_EXPLOSION"] = meso_dps
if unlocked("TOXIC_VENOM") and unlocked("MESO_EXPLOSION"):
    total_hit_rate += 3 * meso_rate * target_multiplier(meso_stack_avg)

bm_pct = (coeff_pct(36000, 12, True, 4) + level_gated_sum({122: 50, 138: 50})) if unlocked("BLOOD_MONEY") else 0.0
bm_hd = hit_damage(bm_pct, False, 0, 0)
bm_dps = 3 * bm_hd * meso_rate * target_multiplier(bm_stack_avg * bm_target_mult) if unlocked("BLOOD_MONEY") else 0.0
skill_dps["BLOOD_MONEY"] = bm_dps
if unlocked("TOXIC_VENOM") and unlocked("BLOOD_MONEY"):
    total_hit_rate += 3 * meso_rate * target_multiplier(bm_stack_avg * bm_target_mult)

toxic_venom_pct = (coeff_pct(6000, 21, True, 4) + level_gated_sum({130: 100})) if unlocked("TOXIC_VENOM") else 0.0
toxic_venom_dps = 0.2 * total_hit_rate * hit_damage(toxic_venom_pct, False, 0, 0) if unlocked("TOXIC_VENOM") else 0.0
skill_dps["TOXIC_VENOM"] = toxic_venom_dps

# ---- Assassinate (base + finisher, murderous intent) ----
assassinate_eff_cd = eff_cooldown(13, True)
assassinate_rate_q = 1 / assassinate_eff_cd
bm_rate_q = 1 / eff_cooldown(11, True)
murderous_intent_mult = 1 + min(1, (bm_rate_q * 2) / assassinate_rate_q) if unlocked("ASSASSINATE") and unlocked("BLOOD_MONEY") else (1.0 if unlocked("ASSASSINATE") else 0.0)
if unlocked("ASSASSINATE"):
    asn_base_pct = coeff_pct(14000, 21, True, 4) + (50 if level >= 134 else 0)
    asn_finisher_pct = coeff_pct(30000, 12, True, 4)
    asn_pct = asn_base_pct + 0.5 * asn_finisher_pct * murderous_intent_mult
    asn_hd = hit_damage(asn_pct, False, 0, 0)
    if fixed_duration_active:
        asn_rate = exact_total_hits(assassinate_eff_cd, 2, None, None) / fight_duration
    else:
        asn_rate = 2 / assassinate_eff_cd
    asn_dps = asn_rate * asn_hd * target_multiplier(1)
else:
    asn_dps = 0.0
skill_dps["ASSASSINATE"] = asn_dps

total_dps = cruel_stab_dps + sum(skill_dps.values()) + shadow_shifter_dps

print(f"Global Crit Rate Bonus % = {crit_rate_bonus:.6f}")
print(f"Global Monster Damage Taken Bonus % = {monster_dmg_bonus:.6f}")
print(f"Global Crit Damage Bonus % = {crit_damage_bonus:.6f}")
print(f"Average buff multiplier = {avg_buff_mult:.6f}")
print(f"Shadow Partner mult = {shadow_partner_mult:.6f}")
print(f"Actions/sec = {actions_per_second:.6f}")
print(f"Cast rate = {cast_rate:.6f}")
print(f"Cruel Stab casts/sec = {cruel_stab_per_second:.6f}")
print(f"Meso stack avg = {meso_stack_avg:.6f}, Blood Money stack avg = {bm_stack_avg:.6f}")
print(f"Murderous Intent mult = {murderous_intent_mult:.6f}")
print(f"Cruel Stab DPS = {cruel_stab_dps:.4f}")
for k, v in skill_dps.items():
    print(f"  {k:28s} DPS = {v:.4f}")
print(f"  SHADOW_SHIFTER              DPS = {shadow_shifter_dps:.4f}")
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
py_skill_dps["CRUEL_STAB"] = cruel_stab_dps
py_skill_dps["SHADOW_SHIFTER"] = shadow_shifter_dps

xl_total = read_cell("SUMMARY", f"B{R_TOTAL}")
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
