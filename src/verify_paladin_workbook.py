#!/usr/bin/env python3
"""
Cross-checks Paladin-DPS-Calculator.xlsx against an independent Python port of the same logic, using
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
XLSX_PATH = REPO / "Paladin" / "Paladin-DPS-Calculator.xlsx"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_paladin_workbook import ROW, IN, UNLOCK_LEVEL, MAPLE_HERO_RATIOS, R_TOTAL  # noqa: E402

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


def _parse_chapter_stage(raw):
    raw = str(raw)
    if "-" in raw:
        left, right = raw.split("-", 1)
        try:
            return float(left), float(right)
        except ValueError:
            return 28.0, 9.0
    try:
        v = float(raw)
        return v, v
    except ValueError:
        return 28.0, 9.0


def _compute_breakthrough_normal_weight_pct(choice):
    return {
        "More Normal": 70, "A Little More Normal": 60, "Equal": 50,
        "A Little More Boss": 40, "More Boss": 30,
    }.get(choice, 60)


content_type = _in("content_type")
chapter, stage = _parse_chapter_stage(_in("chapter_stage"))
defense = _in("defense")
monster_type = _compute_monster_type(content_type)
breakthrough_normal_weight_pct = _compute_breakthrough_normal_weight_pct(_in("boss_normal_weight_choice"))
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


def exact_casts(cooldown, duration=None):
    d = fight_duration if duration is None else duration
    return math.floor(d / cooldown) + 1


def exact_total_hits(cooldown, hits_per_cast, icd, window, duration=None):
    d = fight_duration if duration is None else duration
    casts = exact_casts(cooldown, d)
    remaining_after_last = max(0.0, d - (casts - 1) * cooldown)
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


def boss_normal_multiplier(mastery_boss, mastery_normal, targets):
    """Correctly blends Boss/Normal Monster Damage% and target count: each branch gets its own
    full (1+damage%/100)*targets treatment, combined here as a plain dollar blend (correct for the
    real Total DPS). Sensitivity's marginal-value ranking uses a separate, ratio-based blend
    instead (see build_sensitivity_sheet), since a dollar blend would let a stat's reported
    "value" be dominated by whichever branch hits more targets."""
    if monster_type == "pvp":
        return 1
    targets = min(targets, max_enemies_hit)
    boss_term = boss_damage + mastery_boss + monster_dmg_bonus
    normal_term = normal_damage + mastery_normal + monster_dmg_bonus
    boss_branch = 1 + boss_term / 100
    normal_branch = (1 + normal_term / 100) * targets
    return (1 - normal_weight) * boss_branch + normal_weight * normal_branch


# ---- Helper rows (Final Attack, Maple Hero) — own D/E/F only, no independent DPS. Paladin has
#      NO Advanced Final Attack at all (confirmed absent from its skill list). ----
final_attack_pct = (
    coeff_pct(350, 21, True, 2) + level_gated_sum({54: 50})
    if unlocked("FINAL_ATTACK_HELPER") else 0.0
)
maple_hero_pct = coeff_pct(200, 23, True, 4) if unlocked("MAPLE_HERO_HELPER") else 0.0

# Blast's own coefficient includes Final Attack folded in (single-stage — no Advanced Final
# Attack), further multiplied by Maple Hero's own +150% FD share targeting Final Attack
# specifically (a bespoke fold, since Final Attack is a HELPER row not a normal Maple Hero
# target), PLUS its own real Damage/Boss-Monster-Damage mastery chains (deltas).
blast_final_attack_addition = (
    final_attack_pct / 100 * 25 * (1 + 7.5 * maple_hero_pct / 100)
    if unlocked("FINAL_ATTACK_HELPER") else 0.0
)
blast_mastery_damage = level_gated_sum({102: 10, 106: 1, 116: 1, 120: 1, 128: 1, 132: 1})
blast_mastery_boss_damage = level_gated_sum({111: 10, 124: 10})
blast_pct = skill_coefficient_base + blast_final_attack_addition + blast_mastery_damage
blast_targets = 6 + basic_attack_target_increase
BLAST_HITS = 6 if level >= 136 else 5

# ---- Nimble Feet (Attack Speed buff, duty-cycle averaged) ----
nimble_feet_pct = coeff_pct(150, 0, False, 1)
nimble_avg = buff_avg(nimble_feet_pct, 15, 60, True) if unlocked("NIMBLE_FEET") else 0.0
as_bonus = nimble_avg
actions_per_second = 1 + min(150, 150 * (1 - (1 - attack_speed_base / 150) * (1 - as_bonus / 150))) / 100

# Buff-Casting Startup Delay: in fixed-duration fights, the character casts every currently-
# unlocked, actively-cast buff sequentially at fight start (1/APS seconds each, same cadence as
# every other action-costing skill) before their first damage-skill cast — so damage skills'
# usable window is reduced by this amount. Buffs themselves keep their own t=0 uptime math
# unchanged (they're what causes the delay, not affected further by it). VESSEL_OF_LIGHT/
# DIVINE_SHIELD are buff-category too but costs_action=False (not actively cast), so they don't
# contribute to the delay and are irrelevant here (they're not in COST_ACTION_ROWS/DAMAGE_SKILLS).
BUFF_ROW_KEYS = {"GUARDIAN", "DIVINE_BLESSING", "HP_RECOVERY_ATK", "NIMBLE_FEET"}
if fixed_duration_active:
    buff_cast_startup_time = sum(
        1 for k in ("GUARDIAN", "DIVINE_BLESSING", "HP_RECOVERY_ATK", "NIMBLE_FEET") if unlocked(k)
    ) / actions_per_second
else:
    buff_cast_startup_time = 0.0


def non_buff_casts(cooldown):
    """CastsInFight for a non-buff (damage) skill, reduced by the buff-casting startup delay."""
    if buff_cast_startup_time >= fight_duration:
        return 0
    return exact_casts(cooldown, max(0.0, fight_duration - buff_cast_startup_time))


def non_buff_total_hits(cooldown, hits_per_cast, icd, window):
    """exact_total_hits for a non-buff (damage) skill, reduced by the startup delay."""
    if buff_cast_startup_time >= fight_duration:
        return 0.0
    return exact_total_hits(cooldown, hits_per_cast, icd, window, max(0.0, fight_duration - buff_cast_startup_time))


# ---- Cast rate (subtracted from Blast) ----
COST_ACTION_ROWS = [
    ("CLOSE_COMBAT", 18, True, 1),
    ("NOBLE_DEMAND", 30, True, 1),
    ("HEAVENS_HAMMER", 18, True, 1),
    ("DIVINE_MARK_MAIN", 16, True, 1),
    ("MAGIC_CRASH", 28, True, 1),
    ("RUSH", 22, True, 1),
    ("GUARDIAN", 24, True, 1),
    ("DIVINE_BLESSING", 30, True, 1),
    ("HP_RECOVERY_ATK", 25, True, 1),
    ("NIMBLE_FEET", 60, True, 1),
]
if fixed_duration_active:
    cast_rate = sum(
        (exact_casts(eff_cooldown(cd, ca)) if k in BUFF_ROW_KEYS else non_buff_casts(eff_cooldown(cd, ca))) * aps
        for k, cd, ca, aps in COST_ACTION_ROWS if ca and unlocked(k)
    ) / fight_duration
else:
    cast_rate = sum((1 / eff_cooldown(cd, ca)) * aps for k, cd, ca, aps in COST_ACTION_ROWS if ca and unlocked(k))
blast_per_second = max(0, actions_per_second - cast_rate)

# ---- Vessel of Light (proc off basic attacks, no stated internal cooldown — uptime
#      approximated as MIN(1, Duration x ProcChance%/100 x Basic Attack Rate)). Greater Vessel of
#      Light has no own duty cycle and reuses this same uptime fraction directly. ----
vessel_of_light_pct = coeff_pct(150, 22, True, 2) if unlocked("VESSEL_OF_LIGHT") else 0.0
vessel_of_light_uptime = min(1.0, 10 * (15 / 100) * blast_per_second) if unlocked("VESSEL_OF_LIGHT") else 0.0
vessel_of_light_avg = vessel_of_light_pct * vessel_of_light_uptime if unlocked("VESSEL_OF_LIGHT") else 0.0
greater_vessel_pct = coeff_pct(180, 22, True, 4) if unlocked("GREATER_VESSEL_OF_LIGHT") else 0.0
greater_vessel_avg = greater_vessel_pct * vessel_of_light_uptime if unlocked("GREATER_VESSEL_OF_LIGHT") else 0.0

hp_recovery_pct = coeff_pct(120, 22, True, 3) if unlocked("HP_RECOVERY_ATK") else 0.0
hp_recovery_avg = buff_avg(hp_recovery_pct, 20, 25, True) if unlocked("HP_RECOVERY_ATK") else 0.0

attack_bucket_mult = 1 + (vessel_of_light_avg + hp_recovery_avg) / 100

# ---- Divine Shield (fixed-interval buff, treated as its own Cooldown(s)), Guardian, Divine
#      Blessing (all live duty-cycled Final Damage buffs) ----
divine_shield_pct = coeff_pct(150, 22, True, 3) if unlocked("DIVINE_SHIELD") else 0.0
divine_shield_avg = buff_avg(divine_shield_pct, 10, 15, False) if unlocked("DIVINE_SHIELD") else 0.0
guardian_pct = coeff_pct(100, 22, True, 4) if unlocked("GUARDIAN") else 0.0
guardian_avg = buff_avg(guardian_pct, 20, 24, True) if unlocked("GUARDIAN") else 0.0
divine_blessing_pct = coeff_pct(120, 22, True, 4) if unlocked("DIVINE_BLESSING") else 0.0
divine_blessing_avg = buff_avg(divine_blessing_pct, 22, 30, True) if unlocked("DIVINE_BLESSING") else 0.0

crit_rate_bonus = 0.0  # no live Crit-Rate-buff source exists in this kit
crit_damage_bonus = 0.0  # no live Crit-Damage-buff source exists in this kit
final_damage_extra = divine_shield_avg + guardian_avg + divine_blessing_avg + greater_vessel_avg
monster_dmg_bonus = 0.0  # no live monster-dmg-taken source modeled (Close Combat/Noble Demand/Divine Mark's own weaken effects flagged)


def hit_damage(coeff_pct_val, is_basic, mastery_boss, mastery_normal, maple_ratio=0.0):
    base_damage = attack * (coeff_pct_val / 100)
    dmg_reduction = 5000 / (6000 + monster_defense * (1 - def_pen / 100))
    maple_mult = (1 + maple_ratio * maple_hero_pct / 100) if maple_ratio else 1.0
    final_mult = (1 + (final_damage + final_damage_extra) / 100) * maple_mult
    source_pct = basic_attack_damage if is_basic else skill_damage
    # Boss/Normal Monster Damage% is deliberately NOT applied here — it's blended per-branch
    # (its own multiplier * its own target count) in boss_normal_multiplier, applied by the
    # caller, rather than summed into base_hit before a single shared multiplication.
    base_hit = (
        base_damage * (1 + stat_damage / 100) * (1 + damage / 100)
        * (1 + damage_amp / 100) * dmg_reduction * final_mult * (1 + source_pct / 100)
        * attack_bucket_mult
    )
    non_crit_min = base_hit * min(min_damage, max_damage) / 100
    non_crit_max = base_hit * max_damage / 100
    non_crit_avg = (non_crit_min + non_crit_max) / 2
    crit_avg = non_crit_avg * (1 + (crit_damage + crit_damage_bonus) / 100)
    cr = min(crit_rate + crit_rate_bonus, 100) / 100
    return non_crit_avg * (1 - cr) + crit_avg * cr


# ---- Blast (basic attack) ----
blast_hit = hit_damage(blast_pct, True, blast_mastery_boss_damage, 0)
blast_dps = BLAST_HITS * blast_hit * blast_per_second * boss_normal_multiplier(blast_mastery_boss_damage, 0, blast_targets) if unlocked("BLAST") else 0.0

# ---- Damage skills ----
heavens_hammer_mastery_boss = 100 + (100 if level >= 134 else 0)
divine_judgment_cooldown = 10 / actions_per_second

DAMAGE_SKILLS = {
    "CLOSE_COMBAT": dict(job_step=2, cooldown=18, hits=1, base=4600, fidx=12, scales=True,
                          mastery=level_gated_sum({39: 50}), mastery_boss=0, mastery_normal=0,
                          costs_action=True, targets=7, maple_ratio=MAPLE_HERO_RATIOS.get("CLOSE_COMBAT", 0)),
    "NOBLE_DEMAND": dict(job_step=3, cooldown=30, hits=1, base=16000, fidx=12, scales=True,
                          mastery=level_gated_sum({73: 50}), mastery_boss=0, mastery_normal=0,
                          costs_action=True, targets=8, maple_ratio=MAPLE_HERO_RATIOS.get("NOBLE_DEMAND", 0)),
    "HEAVENS_HAMMER": dict(job_step=4, cooldown=18, hits=5, base=7800, fidx=12, scales=True,
                            mastery=level_gated_sum({108: 50}), mastery_boss=heavens_hammer_mastery_boss,
                            mastery_normal=0, costs_action=True, targets=7),
    "DIVINE_MARK_MAIN": dict(job_step=4, cooldown=16, hits=6, base=4600, fidx=12, scales=True,
                              mastery=level_gated_sum({122: 50}), mastery_boss=0, mastery_normal=0,
                              costs_action=True, targets=8),
    "DIVINE_MARK_DETONATION": dict(job_step=4, cooldown=16, hits=4, base=4000, fidx=12, scales=True,
                                    mastery=0, mastery_boss=0, mastery_normal=0,
                                    costs_action=False, targets=8),
    "DIVINE_JUDGMENT": dict(job_step=4, cooldown=divine_judgment_cooldown, hits=4, base=8500, fidx=12,
                             scales=True, mastery=0, mastery_boss=0, mastery_normal=0,
                             costs_action=False, targets=4),
    "MAGIC_CRASH": dict(job_step=4, cooldown=28, hits=1, base=48000, fidx=12, scales=True,
                         mastery=0, mastery_boss=0, mastery_normal=0, costs_action=True,
                         targets=5 + (4 if level >= 100 else 0)),
    "RUSH": dict(job_step=3, cooldown=22, hits=1, base=6000, fidx=12, scales=True,
                 mastery=0, mastery_boss=0, mastery_normal=0, costs_action=True,
                 targets=12, maple_ratio=MAPLE_HERO_RATIOS.get("RUSH", 0)),
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
        maple_ratio=s.get("maple_ratio", 0.0),
    )
    proc_prob = 1.0
    eff_cd = eff_cooldown(s["cooldown"], s["costs_action"])
    if fixed_duration_active:
        rate = non_buff_total_hits(eff_cd, s["hits"], s.get("icd"), s.get("window")) / fight_duration
    else:
        hits = s["hits"] * ((s["window"] / s["icd"]) if s.get("icd") else 1)
        rate = hits / eff_cd
    skill_dps[key] = proc_prob * rate * hd * boss_normal_multiplier(s.get("mastery_boss", 0), s.get("mastery_normal", 0), s["targets"])

total_dps = blast_dps + sum(skill_dps.values())

print(f"Attack%% bucket multiplier = {attack_bucket_mult:.6f}")
print(f"Global Crit Damage Bonus % = {crit_damage_bonus:.6f}")
print(f"Global Final Damage Bonus % = {final_damage_extra:.6f}")
print(f"Global Monster Damage-Taken Bonus % = {monster_dmg_bonus:.6f}")
print(f"Actions/sec = {actions_per_second:.6f}")
print(f"Cast rate = {cast_rate:.6f}")
print(f"Blast casts/sec = {blast_per_second:.6f}")
print(f"Blast DPS = {blast_dps:.4f}")
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
py_skill_dps["BLAST"] = blast_dps

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
