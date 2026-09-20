#!/usr/bin/env python3
"""
Cross-checks Night-Lord-DPS-Calculator.xlsx against an independent Python re-derivation of the
same mechanics (not transcribed from the Excel formula strings — a from-scratch port of the
underlying model described in tools/build_night_lord_workbook.py's docstrings/Notes), using the
workbook's own default Inputs values. Then loads the live workbook with the `formulas` package
(a real Excel formula evaluator) and diffs Total DPS + every per-skill DPS cell (Calc!O<row>)
against this script's independent numbers. Mirrors verify_fp_mage_workbook.py's own structure.
"""
import json
import math
import re
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
XLSX_PATH = REPO / "Night-Lord" / "Night-Lord-DPS-Calculator.xlsx"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_night_lord_workbook import ROW, IN, UNLOCK_LEVEL, R_TOTAL  # noqa: E402

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
fight_duration = _compute_fight_duration(content_type)
max_enemies_hit = _in("max_enemies_hit")
incoming_hit_rate = _in("incoming_hit_rate")

fixed_duration_active = monster_type != "pvp" and fight_duration > 0

basic_lvl = input_level(4, level, skill1, skill2, skill3, skill4, skill_all)
skill_coefficient_base = 290 * get_factor(basic_lvl, 21) / 1000
print(f"SKILL_COEFFICIENT (Showdown base) = {skill_coefficient_base:.4f}")


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


# ---------------------------------------------------------------------------
# Skill definitions (base, factorIndex, jobStep) — mirrors the reverse-engineered values in
# Skills!BaseDamage(tenths%)/FactorIndex, transcribed independently from the plan, not from the
# Excel formula strings.
# ---------------------------------------------------------------------------
SHOWDOWN_TARGETS = 6 + basic_attack_target_increase
showdown_hits = 6 if level >= 134 else 5
showdown_mastery = level_gated_sum({98: 10, 104: 1, 113: 1, 118: 1, 126: 1, 130: 1})
showdown_mastery_boss = level_gated_sum({108: 10, 122: 10})

gust_charm_mastery = level_gated_sum({39: 80})
quad_star_mastery = level_gated_sum({132: 50})
sudden_raid_mastery = level_gated_sum({124: 50})
triple_throw_mastery = level_gated_sum({71: 100})
toxic_venom_mastery = level_gated_sum({128: 100})
mark_of_assassin_cooldown = 2.0 if level >= 138 else 2.5
mark_of_assassin_targets = 10 if level >= 107 else 7
mark_of_assassin_mastery = level_gated_sum({42: 80})
dark_flare_cooldown = 45 * 0.7 if level >= 92 else 45
dark_flare_icd = 2 * 0.75 if level >= 104 else 2
dark_flare_hits = 3 if level >= 76 else 2
quad_star_cooldown = 10 * 0.7 if level >= 106 else 10
adrenalin_buff_duration = 15 if level >= 88 else 10
dark_sight_duration = 12 if level >= 24 else 8

night_lords_mark_pct = coeff_pct(3000, 21, True, 4) if level >= 107 else 0.0
# Mastery Lv.122 ("Weaken", patched): +8% Damage Taken for 2s to marked targets. Since Assassin's
# Mark's own tick both places AND consumes the mark in the same instant (no separate "hit lands
# on an already-marked target" event exists under the simplified periodic-tick model), this is a
# flat per-tick bonus on Assassin's Mark's own hit only — not a duty-cycle-averaged global term.
mark_of_assassin_weaken = 8.0 if level >= 122 else 0.0

DAMAGE_SKILLS = {
    "SHOWDOWN": dict(job_step=4, cooldown=None, hits=showdown_hits, base=None, fidx=None, scales=True,
                      mastery=showdown_mastery, mastery_boss=showdown_mastery_boss, mastery_normal=0.0, mastery_final=0.0,
                      costs_action=False, targets=SHOWDOWN_TARGETS),
    "GUST_CHARM": dict(job_step=2, cooldown=24, hits=1, base=4000, fidx=12, scales=True,
                        mastery=gust_charm_mastery, mastery_boss=0.0, mastery_normal=0.0, mastery_final=0.0,
                        costs_action=True, targets=8),
    "MARK_OF_ASSASSIN": dict(job_step=2, cooldown=mark_of_assassin_cooldown, hits=1, base=1900, fidx=21,
                              scales=True, mastery=mark_of_assassin_mastery, mastery_boss=mark_of_assassin_weaken,
                              mastery_normal=mark_of_assassin_weaken,
                              mastery_final=night_lords_mark_pct, costs_action=False, targets=mark_of_assassin_targets),
    "TRIPLE_THROW": dict(job_step=3, cooldown=13, hits=3, base=3600, fidx=12, scales=True,
                          mastery=triple_throw_mastery, mastery_boss=0.0, mastery_normal=0.0, mastery_final=0.0,
                          costs_action=True, targets=1),
    "DARK_FLARE": dict(job_step=3, cooldown=dark_flare_cooldown, hits=dark_flare_hits, icd=dark_flare_icd, window=20,
                        base=3300, fidx=12, scales=True, mastery=0.0, mastery_boss=0.0, mastery_normal=0.0,
                        mastery_final=0.0, costs_action=True, targets=8),
    "VENOM": dict(job_step=3, cooldown=1, hits=1, base=450, fidx=21, scales=True,
                  mastery=0.0, mastery_boss=0.0, mastery_normal=0.0, mastery_final=0.0,
                  costs_action=False, targets=1),
    "QUAD_STAR": dict(job_step=4, cooldown=quad_star_cooldown, hits=4, base=11500, fidx=12, scales=True,
                       mastery=quad_star_mastery, mastery_boss=0.0, mastery_normal=0.0, mastery_final=0.0,
                       costs_action=True, targets=1),
    "SUDDEN_RAID_BURST": dict(job_step=4, cooldown=19, hits=3, base=14000, fidx=12, scales=True,
                               mastery=sudden_raid_mastery, mastery_boss=0.0, mastery_normal=0.0, mastery_final=0.0,
                               costs_action=True, targets=8),
    "SUDDEN_RAID_DOT": dict(job_step=4, cooldown=19, hits=1, icd=1, window=5, base=3600, fidx=12, scales=True,
                             mastery=0.0, mastery_boss=0.0, mastery_normal=0.0, mastery_final=0.0,
                             costs_action=False, targets=8),
}
# Sudden Raid (DoT) shares Sudden Raid (burst)'s cooldown (19s, unaffected by any modeled mastery).

TOXIC_VENOM = dict(base=6000, fidx=21, job_step=4)
SHADOW_SHIFTER = dict(base=25000, fidx=21, job_step=4)
SHADOW_PARTNER = dict(base=840, fidx=21, job_step=3, maple_base=500)
MAPLE_TARGETS = {
    "DARK_FLARE": 150, "VENOM": 500, "SHADOW_PARTNER": 500, "GUST_CHARM": 1300,
}
TRIGGERS_TOXIC_VENOM = {"SHOWDOWN", "GUST_CHARM", "MARK_OF_ASSASSIN", "TRIPLE_THROW",
                         "DARK_FLARE", "QUAD_STAR", "SUDDEN_RAID_BURST", "SUDDEN_RAID_DOT"}

BUFFS = {
    "NIMBLE_FEET": dict(job_step=1, cooldown=60, duration=15, base=150, fidx=0, scales=False, target="ATTACK_SPEED", costs_action=True, actions_per_cast=1),
    "DARK_SIGHT_CRIT": dict(job_step=1, cooldown=25, duration=dark_sight_duration, base=60, fidx=21, scales=True, target="CRIT_RATE", costs_action=False, actions_per_cast=1),
    "DARK_SIGHT_ATK": dict(job_step=1, cooldown=25, duration=dark_sight_duration, base=100, fidx=21, scales=True, target="ATTACK", costs_action=True, actions_per_cast=2),
    "FRAILTY_CURSE_SELF_FD": dict(job_step=4, cooldown=45, duration=20, base=130, fidx=22, scales=True, target="FINAL_DAMAGE", costs_action=True, actions_per_cast=1),
    "FRAILTY_CURSE_DEBUFF": dict(job_step=4, cooldown=45, duration=20, base=180, fidx=21, scales=True, target="MONSTER_DMG", costs_action=False, actions_per_cast=1),
}
ADRENALIN = {
    "ADRENALIN_FD": dict(job_step=3, base=150, fidx=22, scales=True, target="FINAL_DAMAGE"),
    "ADRENALIN_AS": dict(job_step=3, base=80, fidx=22, scales=True, target="ATTACK_SPEED"),
}
PASSIVE_MULT = {
    "AGILE_CLAWS": dict(job_step=2, base=50, fidx=22, scales=True),
    "PHYSICAL_TRAINING": dict(job_step=2, base=100, fidx=22, scales=True),
    "CLAW_MASTERY": dict(job_step=2, base=150, fidx=22, scales=True),
    "CRITICAL_THROW_RATE": dict(job_step=2, base=60, fidx=22, scales=True),
    "CRITICAL_THROW_DMG": dict(job_step=2, base=100, fidx=22, scales=True),
    "ENVELOPING_DARKNESS": dict(job_step=3, base=180, fidx=22, scales=True),
    "EXPERT_THROWING_STAR_HANDLING": dict(job_step=3, base=180, fidx=22, scales=True),
    "CLAW_EXPERT": dict(job_step=4, base=150, fidx=22, scales=True),
    "DARK_HARMONY": dict(job_step=4, base=120, fidx=22, scales=True),
    "SHADOW_SHIFTER_SELF_ATK": dict(job_step=4, base=100, fidx=22, scales=True),
}


def target_multiplier(targets):
    if monster_type == "pvp":
        return 1
    targets = min(targets, max_enemies_hit)
    return (1 - normal_weight) * 1 + normal_weight * targets


def buff_uptime(cooldown, duration, bdi_extra=0.0):
    bdi = buff_duration_increase_pct + bdi_extra
    scaled_duration = duration * (1 + bdi / 100)
    if fixed_duration_active:
        return exact_buff_uptime(cooldown, scaled_duration) / fight_duration
    if monster_type == "pvp":
        return min(scaled_duration, PVP_FIGHT_DURATION) / PVP_FIGHT_DURATION
    return scaled_duration / cooldown


# ---------------------------------------------------------------------------
# Global helper bonuses (mirrors Summary!R_CRIT_RATE_BONUS / R_MONSTER_DMG_BONUS / R_AVGBUFF /
# R_SHADOW_PARTNER_MULT).
# ---------------------------------------------------------------------------
def passive_row_pct(key, table):
    p = table[key]
    return coeff_pct(p["base"], p["fidx"], p["scales"], p["job_step"]) if unlocked(key) else 0.0


dark_sight_crit_pct = passive_row_pct("DARK_SIGHT_CRIT", BUFFS) if unlocked("DARK_SIGHT_CRIT") else 0.0
dark_sight_crit_uptime = buff_uptime(BUFFS["DARK_SIGHT_CRIT"]["cooldown"], BUFFS["DARK_SIGHT_CRIT"]["duration"])
dark_sight_crit_avg = dark_sight_crit_pct * dark_sight_crit_uptime if unlocked("DARK_SIGHT_CRIT") else 0.0

frailty_debuff_pct = coeff_pct(BUFFS["FRAILTY_CURSE_DEBUFF"]["base"], BUFFS["FRAILTY_CURSE_DEBUFF"]["fidx"], True, 4) if unlocked("FRAILTY_CURSE_DEBUFF") else 0.0
frailty_debuff_uptime = buff_uptime(BUFFS["FRAILTY_CURSE_DEBUFF"]["cooldown"], BUFFS["FRAILTY_CURSE_DEBUFF"]["duration"])
frailty_debuff_avg = frailty_debuff_pct * frailty_debuff_uptime if unlocked("FRAILTY_CURSE_DEBUFF") else 0.0
# Mastery Lv.111 ("Frailty Curse - Critical"): +30% Critical Damage Taken to enemies in the same
# zone, duty-cycle-averaged over the same uptime as the enemy debuff row above (per the user's
# direction, only the Critical Damage half is modeled — the Critical Resistance half has no
# matching mechanic anywhere in this calculator).
crit_damage_bonus = (30.0 * frailty_debuff_uptime) if level >= 111 else 0.0

critical_throw_lv47 = 8.0 if level >= 47 else 0.0
venom_lv82 = 15.0 if level >= 82 else 0.0

crit_rate_bonus = critical_throw_lv47 + dark_sight_crit_avg
monster_dmg_bonus = venom_lv82 + frailty_debuff_avg

dark_sight_atk_pct = coeff_pct(BUFFS["DARK_SIGHT_ATK"]["base"], BUFFS["DARK_SIGHT_ATK"]["fidx"], True, 1) if unlocked("DARK_SIGHT_ATK") else 0.0
dark_sight_atk_uptime = buff_uptime(BUFFS["DARK_SIGHT_ATK"]["cooldown"], BUFFS["DARK_SIGHT_ATK"]["duration"])
dark_sight_atk_avg = dark_sight_atk_pct * dark_sight_atk_uptime if unlocked("DARK_SIGHT_ATK") else 0.0

frailty_self_pct = coeff_pct(BUFFS["FRAILTY_CURSE_SELF_FD"]["base"], BUFFS["FRAILTY_CURSE_SELF_FD"]["fidx"], True, 4) if unlocked("FRAILTY_CURSE_SELF_FD") else 0.0
frailty_self_uptime = buff_uptime(BUFFS["FRAILTY_CURSE_SELF_FD"]["cooldown"], BUFFS["FRAILTY_CURSE_SELF_FD"]["duration"])
frailty_self_avg = frailty_self_pct * frailty_self_uptime if unlocked("FRAILTY_CURSE_SELF_FD") else 0.0

# --- Actions per second / Alchemic Adrenaline (bespoke, breaks the circular dependency by using
# a "pre-Adrenalin" actions/sec for the accumulation phase — see build_night_lord_workbook.py's
# build_summary_sheet docstring). ---
nimble_feet_pct = coeff_pct(BUFFS["NIMBLE_FEET"]["base"], BUFFS["NIMBLE_FEET"]["fidx"], False, 1)
nimble_feet_uptime = buff_uptime(BUFFS["NIMBLE_FEET"]["cooldown"], BUFFS["NIMBLE_FEET"]["duration"])
nimble_feet_avg = nimble_feet_pct * nimble_feet_uptime

aps_pre_adrenalin = 1 + min(150, 150 * (1 - (1 - attack_speed_base / 150) * (1 - nimble_feet_avg / 150))) / 100

activations_needed = 5
adrenalin_duration_scaled = adrenalin_buff_duration * (1 + buff_duration_increase_pct / 100)
adrenalin_accumulate_time = activations_needed / aps_pre_adrenalin
adrenalin_uptime = adrenalin_duration_scaled / (adrenalin_duration_scaled + adrenalin_accumulate_time) if unlocked("ADRENALIN_FD") else 0.0

adrenalin_as_pct = coeff_pct(ADRENALIN["ADRENALIN_AS"]["base"], ADRENALIN["ADRENALIN_AS"]["fidx"], True, 3) if unlocked("ADRENALIN_AS") else 0.0
adrenalin_fd_pct = coeff_pct(ADRENALIN["ADRENALIN_FD"]["base"], ADRENALIN["ADRENALIN_FD"]["fidx"], True, 3) if unlocked("ADRENALIN_FD") else 0.0
adrenalin_as_avg = adrenalin_as_pct * adrenalin_uptime
adrenalin_fd_avg = adrenalin_fd_pct * adrenalin_uptime

as_bonus = nimble_feet_avg + adrenalin_as_avg
actions_per_second = 1 + min(150, 150 * (1 - (1 - attack_speed_base / 150) * (1 - as_bonus / 150))) / 100

# Buff-Casting Startup Delay: in fixed-duration fights, the character casts every currently-
# unlocked, actively-cast buff sequentially at fight start (1/APS seconds each) before their
# first damage-skill cast — so damage skills' usable window is reduced by this amount. Buffs
# themselves keep their own t=0 uptime math unchanged.
if fixed_duration_active:
    buff_cast_startup_time = sum(1 for k in BUFFS if BUFFS[k]["costs_action"] and unlocked(k)) / actions_per_second
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


if fixed_duration_active:
    cast_rate = sum(
        BUFFS[k]["actions_per_cast"] * exact_casts(eff_cooldown(BUFFS[k]["cooldown"], BUFFS[k]["costs_action"]))
        for k in BUFFS if BUFFS[k]["costs_action"] and unlocked(k)
    )
    cast_rate += sum(
        non_buff_casts(eff_cooldown(DAMAGE_SKILLS[k]["cooldown"], DAMAGE_SKILLS[k]["costs_action"]))
        for k in DAMAGE_SKILLS if k != "SHOWDOWN" and DAMAGE_SKILLS[k]["costs_action"] and unlocked(k)
    )
    cast_rate /= fight_duration
else:
    cast_rate = sum(
        BUFFS[k]["actions_per_cast"] / eff_cooldown(BUFFS[k]["cooldown"], BUFFS[k]["costs_action"])
        for k in BUFFS if BUFFS[k]["costs_action"] and unlocked(k)
    )
    cast_rate += sum(
        1 / eff_cooldown(DAMAGE_SKILLS[k]["cooldown"], DAMAGE_SKILLS[k]["costs_action"])
        for k in DAMAGE_SKILLS if k != "SHOWDOWN" and DAMAGE_SKILLS[k]["costs_action"] and unlocked(k)
    )
showdown_per_second = max(0, actions_per_second - cast_rate)

avg_buff_mult = (1 + dark_sight_atk_avg / 100) * (1 + frailty_self_avg / 100) * (1 + adrenalin_fd_avg / 100)

shadow_partner_mastery = level_gated_sum({66: 100})
shadow_partner_pct = (coeff_pct(SHADOW_PARTNER["base"], SHADOW_PARTNER["fidx"], True, SHADOW_PARTNER["job_step"]) + shadow_partner_mastery) if unlocked("SHADOW_PARTNER") else 0.0
maple_lvl = input_level(4, level, skill1, skill2, skill3, skill4, skill_all)
maple_factor = get_factor(maple_lvl, 23)


def maple_mult(key):
    if key not in MAPLE_TARGETS:
        return 1.0
    return 1 + (MAPLE_TARGETS[key] / 10) * (maple_factor / 1000) / 100


shadow_partner_maple = maple_mult("SHADOW_PARTNER") if unlocked("SHADOW_PARTNER") else 1.0
shadow_partner_mult = 1 + (shadow_partner_pct * shadow_partner_maple * 25 / 100) / 100 if unlocked("SHADOW_PARTNER") else 1.0

print(f"Avg Buff Multiplier        = {avg_buff_mult:.6f}")
print(f"Crit Rate Bonus %          = {crit_rate_bonus:.6f}")
print(f"Monster Dmg-Taken Bonus %  = {monster_dmg_bonus:.6f}")
print(f"Shadow Partner Mult        = {shadow_partner_mult:.6f}")
print(f"Actions/sec (pre-Adrenalin)= {aps_pre_adrenalin:.6f}")
print(f"Adrenalin Uptime           = {adrenalin_uptime:.6f}")
print(f"Actions/sec (final)        = {actions_per_second:.6f}")
print(f"Cast rate                  = {cast_rate:.6f}")
print(f"Showdown/sec                = {showdown_per_second:.6f}")


def hit_damage(coeff_pct_val, is_basic, maple_mult_val, mastery, mastery_boss, mastery_normal, mastery_final):
    effective_coeff = coeff_pct_val + mastery
    base_damage = attack * (effective_coeff / 100)
    dmg_reduction = 5000 / (6000 + monster_defense * (1 - def_pen / 100))
    if monster_type == "pvp":
        monster_dmg = 0
    else:
        boss_term = boss_damage + mastery_boss + monster_dmg_bonus
        normal_term = normal_damage + mastery_normal + monster_dmg_bonus
        monster_dmg = (1 - normal_weight) * boss_term + normal_weight * normal_term
    final_mult = (1 + final_damage / 100) * (1 + mastery_final / 100)
    source_pct = basic_attack_damage if is_basic else skill_damage
    extra_mult = avg_buff_mult * shadow_partner_mult * maple_mult_val
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


skill_dps = {}
hit_rate = {}  # per-skill hits/sec landing damage (target-multiplied), feeds Toxic Venom

showdown_s = DAMAGE_SKILLS["SHOWDOWN"]
showdown_hit = hit_damage(skill_coefficient_base, True, 1.0, showdown_mastery, showdown_mastery_boss, 0.0, 0.0)
showdown_target_mult = target_multiplier(showdown_s["targets"])
showdown_dps = showdown_hits * showdown_hit * showdown_per_second * showdown_target_mult
hit_rate["SHOWDOWN"] = showdown_hits * showdown_per_second * showdown_target_mult if unlocked("SHOWDOWN") else 0.0
skill_dps["SHOWDOWN"] = showdown_dps if unlocked("SHOWDOWN") else 0.0

for key, s in DAMAGE_SKILLS.items():
    if key == "SHOWDOWN":
        continue
    if not unlocked(key):
        skill_dps[key] = 0.0
        hit_rate[key] = 0.0
        continue
    pct = coeff_pct(s["base"], s["fidx"], s["scales"], s["job_step"])
    hd = hit_damage(pct, False, maple_mult(key), s["mastery"], s["mastery_boss"], s["mastery_normal"], s["mastery_final"])
    eff_cd = eff_cooldown(s["cooldown"], s["costs_action"])
    if fixed_duration_active:
        rate = non_buff_total_hits(eff_cd, s["hits"], s.get("icd"), s.get("window")) / fight_duration
    else:
        hits = s["hits"] * ((s["window"] / s["icd"]) if s.get("icd") else 1)
        rate = hits / eff_cd
    tm = target_multiplier(s["targets"])
    skill_dps[key] = rate * hd * tm
    hit_rate[key] = rate * tm

# Toxic Venom — no ICD; trigger rate = combined per-second hit rate (already target-multiplied)
# of every row in TRIGGERS_TOXIC_VENOM.
if unlocked("TOXIC_VENOM"):
    total_hit_rate = sum(hit_rate[k] for k in TRIGGERS_TOXIC_VENOM)
    toxic_pct = coeff_pct(TOXIC_VENOM["base"], TOXIC_VENOM["fidx"], True, TOXIC_VENOM["job_step"])
    toxic_hd = hit_damage(toxic_pct, False, 1.0, toxic_venom_mastery, 0.0, 0.0, 0.0)
    skill_dps["TOXIC_VENOM"] = 0.2 * total_hit_rate * toxic_hd
else:
    skill_dps["TOXIC_VENOM"] = 0.0

# Shadow Shifter counterattack — driven by incoming_hit_rate, not the character's own cast rate.
if unlocked("SHADOW_SHIFTER"):
    shifter_pct = coeff_pct(SHADOW_SHIFTER["base"], SHADOW_SHIFTER["fidx"], True, SHADOW_SHIFTER["job_step"])
    shifter_hd = hit_damage(shifter_pct, False, 1.0, 0.0, 0.0, 0.0, 0.0)
    skill_dps["SHADOW_SHIFTER"] = incoming_hit_rate * 0.2 * shifter_hd
else:
    skill_dps["SHADOW_SHIFTER"] = 0.0

# Shadow Partner (hybrid) and every passive-mult / buff / Night Lord's Mark row contribute 0 DPS
# directly — their contributions are already folded into avg_buff_mult / crit_rate_bonus /
# monster_dmg_bonus / shadow_partner_mult / MasteryFinalDamage% above.
for key in ["SHADOW_PARTNER", "NIGHT_LORDS_MARK"] + list(BUFFS) + list(ADRENALIN) + list(PASSIVE_MULT):
    skill_dps[key] = 0.0

total_dps = sum(skill_dps.values())

print(f"Showdown DPS                = {showdown_dps:.4f}")
for k, v in skill_dps.items():
    if k == "SHOWDOWN":
        continue
    print(f"  {k:28s} DPS = {v:.4f}")
print(f"TOTAL DPS                  = {total_dps:.4f}")

# ---------------------------------------------------------------------------
# Cross-check against the actual live workbook (evaluated with `formulas`, not just the static
# values openpyxl wrote).
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


xl_total = read_cell("SUMMARY", f"B{R_TOTAL}")
mismatches = []
print()
print(f"{'Skill':28s} {'Python DPS':>16s} {'Workbook DPS':>16s}  match")
for key, row in ROW.items():
    py_val = skill_dps.get(key, 0.0)
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
