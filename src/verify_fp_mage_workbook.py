#!/usr/bin/env python3
"""
Cross-checks FP-Mage-DPS-Calculator.xlsx against an independent Python port of
the same logic from active-skill-dps.service.ts / damage-calculation.service.ts
(extended with per-row Skill Mastery bonuses and the Meteor Proc queueing model
described on that row's Skills!Note), using the workbook's own default Inputs
values. Then actually loads the live workbook with the `formulas` package (a
real formula evaluator, not just the static values openpyxl wrote) and diffs
Total DPS + every per-skill DPS cell (Calc!O<row>, via the row map imported
from build_fp_mage_workbook) against this script's independent numbers.
"""
import json
import math
import re
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
XLSX_PATH = REPO / "FP-Mage" / "FP-Mage-DPS-Calculator.xlsx"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_fp_mage_workbook import ROW, IN, UNLOCK_LEVEL, R_TOTAL  # noqa: E402  (kept in sync with the workbook by construction)

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


# ---- read the live Inputs sheet's actual values (not hardcoded defaults) — the workbook now
#      carries over the user's real character stats across rebuilds, so this script needs to
#      test whatever state Inputs is actually in, not a canned default ----
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
# Chapter Breakthrough blends boss and normal by this weight (0=pure boss, 1=pure normal);
# boss=0, normal=1, pvp is its own thing entirely and never blends (mirrors Inputs!normal_weight_frac).
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
attack = flat_attack * (1 + attack_pct / 100)  # mirrors Inputs!B31's own formula
flat_int, int_pct, luk = _in("flat_int"), _in("int_pct"), _in("luk")
stat_damage = (flat_int * (1 + int_pct / 100)) * 0.01 + luk * 0.0025  # mirrors Inputs!B32
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
companion_summon_time_increase_pct = _in("companion_summon_time_increase_pct")
fight_duration = _compute_fight_duration(content_type)
max_enemies_hit = _in("max_enemies_hit")

# Fixed fight-duration mode — independent re-derivation of the workbook's exact-count model
# (not transcribed from the Excel formula strings), gated the same way: off for pvp (which
# already has its own always-on fixed-duration model) or when no duration is set.
fixed_duration_active = monster_type != "pvp" and fight_duration > 0

# ---- skill coefficient (basic attack base, before Skill Mastery), mirrors
#      calculate4thJobSkillCoefficient ----
basic_lvl = input_level(4, level, skill1, skill2, skill3, skill4, skill_all)
skill_coefficient_base = 290 * get_factor(basic_lvl, 21) / 1000
print(f"SKILL_COEFFICIENT (base) = {skill_coefficient_base:.4f}")

# mastery/mastery_boss/mastery_normal are per-row additive %, same mechanism for every row


def level_gated_sum(pairs):
    """Independent re-derivation of the workbook's level_gated_sum SUMPRODUCT helper: cumulative
    sum of every (threshold, increment) pair the character's level has reached."""
    return sum(inc for lvl, inc in pairs.items() if level >= lvl)


# Basic Attack Mastery (+10@102, +11@106, +12@116, +13@120, +14@128, +15@132 — 75% total) and
# Boss Mastery (+10@111, +10@124 — 20% total) — the old hardcoded 21/10 were themselves just
# these masteries evaluated at the user's then-current level, not separate base values.
basic_attack_mastery = level_gated_sum({102: 10, 106: 11, 116: 12, 120: 13, 128: 14, 132: 15})
basic_attack_boss_mastery = level_gated_sum({111: 10, 124: 10})
mist_eruption_hits_normal = 4 if level >= 108 else 3
mist_eruption_mastery = 100 if level >= 122 else 0
meteor_shower_mastery = 50 if level >= 134 else 0
poison_mist_dot_icd = 0.4 if level >= 104 else 0.8
ifrit_window = 40 if level >= 138 else 30
ifrit_targets = 6 if level >= 138 else 3
# Mist Eruption's explosion count and Flame Haze DoT's burn window both differ by boss vs
# normal monster; Chapter Breakthrough blends the two by normal_weight, pvp keeps its own value.
mist_eruption_hits = 0.0 if monster_type == "pvp" else (1 - normal_weight) * 1 + normal_weight * mist_eruption_hits_normal
flame_haze_dot_window = 10.0 if monster_type == "pvp" else (1 - normal_weight) * 20 + normal_weight * 10

SKILLS = {
    "BASIC_ATTACK": dict(job_step=4, cooldown=None, hits=5, base=None, fidx=None, scales=True, mastery=basic_attack_mastery, mastery_boss=basic_attack_boss_mastery, mastery_normal=0, costs_action=False),
    "IGNITE": dict(job_step=2, cooldown=1, hits=3, base=130, fidx=21, scales=True, mastery=100, mastery_boss=0, mastery_normal=0, costs_action=False),
    "POISON_BREATH": dict(job_step=2, cooldown=18, hits=3, base=2000, fidx=12, scales=True, mastery=70, mastery_boss=0, mastery_normal=0, costs_action=True),
    "ELEMENTAL_DRAIN": dict(job_step=2, cooldown=1, hits=5, base=120, fidx=21, scales=True, mastery=0, mastery_boss=0, mastery_normal=0, costs_action=False),
    "POISON_MIST_BURST": dict(job_step=3, cooldown=24.5, hits=3, base=1600, fidx=12, scales=True, mastery=50, mastery_boss=0, mastery_normal=0, costs_action=True),
    "POISON_MIST_DOT": dict(job_step=3, cooldown=24.5, hits=1, icd=poison_mist_dot_icd, window=20, base=700, fidx=12, scales=True, mastery=0, mastery_boss=0, mastery_normal=0, costs_action=False),
    "MIST_ERUPTION": dict(job_step=4, cooldown=24.5, hits=mist_eruption_hits, base=30000, fidx=12, scales=True, mastery=mist_eruption_mastery, mastery_boss=0, mastery_normal=0, costs_action=False),
    "CREEPING_TOXIN": dict(job_step=3, cooldown=27, hits=2, icd=2, window=15, base=1200, fidx=12, scales=True, mastery=50, mastery_boss=0, mastery_normal=100, costs_action=True),
    "METEOR_SHOWER_BURST": dict(job_step=4, cooldown=33, hits=9, base=6000, fidx=12, scales=True, mastery=meteor_shower_mastery, mastery_boss=0, mastery_normal=0, costs_action=True),
    "FLAME_HAZE_BURST": dict(job_step=4, cooldown=25, hits=3, base=12000, fidx=12, scales=True, mastery=0, mastery_boss=0, mastery_normal=0, costs_action=True),
    "FLAME_HAZE_DOT": dict(job_step=4, cooldown=25, hits=1, icd=0.5, window=flame_haze_dot_window, base=1500, fidx=12, scales=True, mastery=0, mastery_boss=0, mastery_normal=0, costs_action=False),
    "IFRIT": dict(job_step=4, cooldown=80, hits=1, icd=4, window=ifrit_window, base=35000, fidx=12, scales=True, mastery=0, mastery_boss=0, mastery_normal=0, costs_action=True),
    "FLAME_HAZE_FOG": dict(job_step=4, cooldown=25, hits=1, icd=poison_mist_dot_icd, window=20, base=700, fidx=12, scales=True, mastery=0, mastery_boss=0, mastery_normal=0, costs_action=False),
}
BUFFS = {
    "MEDITATION": dict(job_step=2, cooldown=30, duration=19.5, base=200, fidx=22, scales=True, target="ATTACK", costs_action=True),
    "MAGIC_GUARD": dict(job_step=1, cooldown=21, duration=15, base=120, fidx=21, scales=True, target="ATTACK", costs_action=True),
    "NIMBLE_FEET": dict(job_step=1, cooldown=60, duration=15, base=150, fidx=0, scales=False, target="ATTACK_SPEED", costs_action=True),
    "INFINITY": dict(job_step=4, cooldown=30, duration=15, base=216.67, fidx=21, scales=True, target="FINAL_DAMAGE", costs_action=True),
}
# New level-102..138 passives — factor 22, not a cooldown/damage row; each row's own contribution
# (0 while locked) feeds a specific shared formula below (buff duration / Final Damage / skill
# damage) rather than being its own DPS line.
PASSIVES = {
    "BUFF_MASTERY": dict(job_step=4, base=100, fidx=22, scales=True),
    "ARCANE_AIM": dict(job_step=4, base=30, fidx=22, scales=True),
    "FERVENT_DRAIN": dict(job_step=4, base=40, fidx=22, scales=True),
}
MAPLE_TARGETS = {
    "IGNITE": 500, "POISON_BREATH": 800, "ELEMENTAL_DRAIN": 1500,
    "POISON_MIST_BURST": 100, "POISON_MIST_DOT": 100, "CREEPING_TOXIN": 100,
}
# Meteor Proc: independent 30% chance on every qualifying attack, gated by a shared 1s ICD.
# Basic Attack always counts (added via basic_attacks_per_second below); Creeping Toxin and Ifrit
# are deliberately excluded (mirrors Skills!TriggersMeteorProc on the real workbook) — Ifrit only
# counts as a trigger source for the level-126 Flame Haze burn-proc mastery, not Meteor Proc.
TRIGGERS_METEOR = {"POISON_BREATH", "POISON_MIST_BURST", "METEOR_SHOWER_BURST", "FLAME_HAZE_BURST"}
# Meteor Shower's 3 meteors are each an independent trigger opportunity even though they land
# from a single cast (confirmed by the user) — everything else triggers once per cast.
METEOR_PROC_TRIGGERS_PER_CAST = {"METEOR_SHOWER_BURST": 3}
METEOR_PROC_CHANCE = 30
METEOR_PROC_ICD = 1
METEOR_PROC_BASE = 9500
METEOR_PROC_FIDX = 21

# Number of normal-monster targets each skill's AoE actually connects with — only relevant vs
# normal monsters (boss/PvP are single-target); confirmed by the user. Basic Attack's is
# 6 (base) + basic_attack_target_increase, not a fixed constant like the others.
NORMAL_MONSTER_TARGETS = {
    "IGNITE": 3, "POISON_BREATH": 6, "POISON_MIST_BURST": 10,
    "POISON_MIST_DOT": 10, "MIST_ERUPTION": 10, "METEOR_SHOWER_BURST": 7,
    "FLAME_HAZE_BURST": 10, "FLAME_HAZE_DOT": 10,
    "IFRIT": ifrit_targets, "FLAME_HAZE_FOG": 10,
}


def boss_normal_multiplier(key, s):
    """Correctly blends Boss/Normal Monster Damage% and target count: each branch gets its own
    full (1+damage%/100)*targets treatment. The two branches are combined here as a plain dollar
    blend for the real Total DPS (correct — this IS what your actual DPS output looks like when
    time-averaged across both target types); Sensitivity's marginal-value ranking uses a separate,
    ratio-based blend instead (see build_sensitivity_sheet), since a dollar blend would let a
    stat's reported "value" be dominated by whichever branch hits more targets. `s` is the skill's
    own mastery dict (mastery_boss/mastery_normal), same as hit_damage already reads."""
    if monster_type == "pvp":
        return 1
    if key == "BASIC_ATTACK":
        targets = 6 + basic_attack_target_increase + (1 if level >= 136 else 0)
    else:
        targets = NORMAL_MONSTER_TARGETS.get(key, 1)
    # A skill that could theoretically hit more targets than are actually in range only hits
    # what's there (confirmed by the user) — capped before the Chapter Breakthrough blend.
    targets = min(targets, max_enemies_hit)
    boss_term = boss_damage + s["mastery_boss"]
    normal_term = normal_damage + s["mastery_normal"]
    boss_branch = 1 + boss_term / 100
    normal_branch = (1 + normal_term / 100) * targets
    # Chapter Breakthrough blends the two branches by normal_weight — the edge cases (weight=0/1)
    # reduce exactly to pure boss/normal.
    return (1 - normal_weight) * boss_branch + normal_weight * normal_branch


def unlocked(key):
    threshold = UNLOCK_LEVEL.get(key)
    return threshold is None or level >= threshold


PVP_FIGHT_DURATION = 15  # mirrors build_fp_mage_workbook.PVP_FIGHT_DURATION


def eff_cooldown(cooldown, costs_action):
    # CDR only applies to skills/buffs the character actually casts (confirmed by the user) —
    # Mist Eruption (costs_action=False) is passed POISON_MIST_BURST's costs_action instead by
    # its caller below, mirroring the workbook's CDR_COSTS_ACTION_ROW override. PvP fights are
    # capped at PVP_FIGHT_DURATION regardless of a skill's own real cooldown (pre-existing gap —
    # this branch was missing entirely before this session, so PvP was never actually verified).
    if monster_type == "pvp":
        return PVP_FIGHT_DURATION
    return max(0.1, cooldown - (skill_cooldown_decrease if costs_action else 0))


def eff_duration(duration):
    return duration * (1 + (buff_duration_increase_pct + buff_mastery_pct) / 100)


def exact_casts(cooldown, duration=None):
    """Exact number of casts within the fixed fight duration: one at t=0 (character starts the
    fight fully ready), then one every effective cooldown as long as it starts before the fight
    ends. math.floor (not a plain int() truncation) to be unambiguous about negative-adjacent
    edge cases, though cooldown/duration are always positive here. `duration` defaults to the
    whole fight; non-buff skills pass a reduced value (see non_buff_casts)."""
    d = fight_duration if duration is None else duration
    return math.floor(d / cooldown) + 1


def exact_total_hits(cooldown, hits_per_cast, icd, window, duration=None):
    """Exact total tick/hit count across the whole fixed-duration fight: every cast except the
    last gets a full window of ticks; the last cast's window is truncated to whatever fight time
    remains after it starts. Collapses to casts*hits_per_cast for non-DoT rows (icd falsy)."""
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
    """Exact total buff-active seconds across the fixed-duration fight — same last-cast
    truncation as exact_total_hits, but for continuous duration instead of discrete ticks."""
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
    """A new level-102..138 passive's own contribution — 0 while locked, matching the workbook's
    IF(level>=threshold, Calc!F, 0) guard at every consumption site."""
    p = PASSIVES[key]
    return coeff_pct(p["base"], p["fidx"], p["scales"], p["job_step"]) if unlocked(key) else 0.0


buff_mastery_pct = passive_pct("BUFF_MASTERY")
arcane_aim_pct = passive_pct("ARCANE_AIM")
fervent_drain_pct = passive_pct("FERVENT_DRAIN")

# Burning Magic
bm_pct = coeff_pct(50, 0, False, 3) * 5
burning_magic_mult = 1 + bm_pct / 100

# Elemental Decrease — treated as always-on (flat multiplier, like Burning Magic): at 50%
# chance per qualifying hit and a 7s duration it's reapplied well before expiring, so uptime
# is assumed to be 100% (confirmed by the user).
ed_pct = coeff_pct(120, 22, True, 3)

# Element Amplification (4th job passive, factor 22) — NOT reflected in Inputs!FINAL_DAMAGE%,
# so it's added as its own always-on Final Damage source, combined multiplicatively (not
# additively) with the base Final Damage input, mirroring Final Damage's real stacking rule.
element_amp_pct = coeff_pct(150, 22, True, 4)
elemental_decrease_mult = 1 + ed_pct / 100

# Average buff multiplier (Attack + FinalDamage) and attack-speed bonus. Same-bucket Attack%
# sources (Meditation + Magic Guard) sum into one combined percentage before a single
# multiplication; Final Damage (Infinity) is a deliberate exception and stays its own
# multiplicative factor.
attack_bucket_sum = 0.0
final_damage_mult = 1.0
as_bonus = 0.0
for key, b in BUFFS.items():
    if not unlocked(key):
        continue
    pct = coeff_pct(b["base"], b["fidx"], b["scales"], b["job_step"])
    eff_cd = eff_cooldown(b["cooldown"], b["costs_action"])
    if fixed_duration_active:
        uptime_fraction = exact_buff_uptime(eff_cd, eff_duration(b["duration"])) / fight_duration
    elif monster_type == "pvp":
        # Cast once at t=0, up for whichever is shorter: its own (scaled) duration or the fight
        # itself — pre-existing gap, this branch was missing entirely before this session.
        uptime_fraction = min(eff_duration(b["duration"]), PVP_FIGHT_DURATION) / PVP_FIGHT_DURATION
    else:
        uptime_fraction = eff_duration(b["duration"]) / eff_cd
    avg_pct = pct * uptime_fraction
    if b["target"] == "ATTACK_SPEED":
        as_bonus += avg_pct
    elif b["target"] == "ATTACK":
        attack_bucket_sum += avg_pct
    else:
        final_damage_mult *= 1 + avg_pct / 100
avg_buff_mult = (1 + attack_bucket_sum / 100) * final_damage_mult

actions_per_second = 1 + min(150, 150 * (1 - (1 - attack_speed_base / 150) * (1 - as_bonus / 150))) / 100

# Buff-Casting Startup Delay: in fixed-duration fights, the character casts every currently-
# unlocked, actively-cast buff sequentially at fight start (1/APS seconds each, same cadence as
# every other action-costing skill) before their first damage-skill cast — so damage skills'
# usable window is reduced by this amount. Buffs themselves keep their own t=0 uptime math
# unchanged (they're what causes the delay, not affected further by it).
if fixed_duration_active:
    buff_cast_startup_time = sum(1 for key, b in BUFFS.items() if b["costs_action"] and unlocked(key)) / actions_per_second
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
    cast_rate = sum(non_buff_casts(eff_cooldown(SKILLS[k]["cooldown"], s["costs_action"])) for k, s in SKILLS.items() if s["costs_action"] and unlocked(k))
    cast_rate += sum(exact_casts(eff_cooldown(b["cooldown"], b["costs_action"])) for key, b in BUFFS.items() if b["costs_action"] and unlocked(key))
    cast_rate /= fight_duration
else:
    cast_rate = sum(1 / eff_cooldown(SKILLS[k]["cooldown"], s["costs_action"]) for k, s in SKILLS.items() if s["costs_action"] and unlocked(k))
    cast_rate += sum(1 / eff_cooldown(b["cooldown"], b["costs_action"]) for key, b in BUFFS.items() if b["costs_action"] and unlocked(key))
basic_attacks_per_second = max(0, actions_per_second - cast_rate)

maple_lvl = input_level(4, level, skill1, skill2, skill3, skill4, skill_all)
maple_factor = get_factor(maple_lvl, 23)


def maple_mult(key):
    if key not in MAPLE_TARGETS:
        return 1.0
    return 1 + (MAPLE_TARGETS[key] / 10) * (maple_factor / 1000) / 100


def hit_damage(coeff_pct_val, is_basic, maple_mult_val, s):
    effective_coeff = coeff_pct_val + s["mastery"]
    base_damage = attack * (effective_coeff / 100)
    dmg_reduction = 5000 / (6000 + monster_defense * (1 - def_pen / 100))
    final_mult = (1 + final_damage / 100) * (1 + element_amp_pct / 100) * (1 + arcane_aim_pct / 100) ** 5
    source_pct = basic_attack_damage if is_basic else skill_damage + fervent_drain_pct * 5
    extra_mult = burning_magic_mult * elemental_decrease_mult * avg_buff_mult * maple_mult_val
    # Boss/Normal Monster Damage% is deliberately NOT applied here — it's blended per-branch
    # (its own multiplier * its own target count) in boss_normal_multiplier, applied by the
    # caller, rather than summed into base_hit before a single shared multiplication.
    base_hit = (
        base_damage * (1 + stat_damage / 100) * (1 + damage / 100)
        * (1 + damage_amp / 100) * dmg_reduction * final_mult * (1 + source_pct / 100) * extra_mult
    )
    non_crit_min = base_hit * min(min_damage, max_damage) / 100
    non_crit_max = base_hit * max_damage / 100
    non_crit_avg = (non_crit_min + non_crit_max) / 2
    crit_avg = non_crit_avg * (1 + crit_damage / 100)
    cr = min(crit_rate, 100) / 100
    return non_crit_avg * (1 - cr) + crit_avg * cr


basic_s = SKILLS["BASIC_ATTACK"]
basic_hit = hit_damage(skill_coefficient_base, True, 1.0, basic_s)
basic_dps = 5 * basic_hit * basic_attacks_per_second * boss_normal_multiplier("BASIC_ATTACK", basic_s)

skill_dps = {}
for key, s in SKILLS.items():
    if key == "BASIC_ATTACK":
        continue
    if not unlocked(key):
        skill_dps[key] = 0.0
        continue
    pct = coeff_pct(s["base"], s["fidx"], s["scales"], s["job_step"])
    proc = 1 - (1 - s.get("chance", 100) / 100) ** s.get("rolls", 1)
    hd = hit_damage(pct, False, maple_mult(key), s)
    # Mist Eruption's own costs_action is False, but the user confirmed CDR on Poison Mist
    # should carry over to it too (mirrors CDR_COSTS_ACTION_ROW in the workbook).
    cdr_costs_action = SKILLS["POISON_MIST_BURST"]["costs_action"] if key == "MIST_ERUPTION" else s["costs_action"]
    eff_cd = eff_cooldown(s["cooldown"], cdr_costs_action)
    if fixed_duration_active:
        rate = non_buff_total_hits(eff_cd, s["hits"], s.get("icd"), s.get("window")) / fight_duration
    else:
        hits = s["hits"] * ((s["window"] / s["icd"]) if s.get("icd") else 1)
        rate = hits / eff_cd
    skill_dps[key] = rate * proc * hd * boss_normal_multiplier(key, s)

# Meteor Proc: no cooldown of its own — steady-state proc rate from the combined cast rate R of
# every triggering attack (mirrors Summary!B14 + Calc!O14's formula in the real workbook).
if fixed_duration_active:
    meteor_trigger_rate = sum(
        METEOR_PROC_TRIGGERS_PER_CAST.get(k, 1) * non_buff_casts(eff_cooldown(SKILLS[k]["cooldown"], SKILLS[k]["costs_action"]))
        for k in TRIGGERS_METEOR if unlocked(k)
    ) / fight_duration + basic_attacks_per_second
else:
    meteor_trigger_rate = sum(
        METEOR_PROC_TRIGGERS_PER_CAST.get(k, 1) / eff_cooldown(SKILLS[k]["cooldown"], SKILLS[k]["costs_action"])
        for k in TRIGGERS_METEOR if unlocked(k)
    ) + basic_attacks_per_second
meteor_chance = METEOR_PROC_CHANCE / 100
meteor_proc_rate = (meteor_chance * meteor_trigger_rate) / (1 + METEOR_PROC_ICD * meteor_chance * meteor_trigger_rate)
meteor_pct = coeff_pct(METEOR_PROC_BASE, METEOR_PROC_FIDX, True, 4)
meteor_hit = hit_damage(meteor_pct, False, maple_mult("METEOR_PROC"), dict(mastery=0, mastery_boss=0, mastery_normal=0))
skill_dps["METEOR_PROC"] = meteor_proc_rate * meteor_hit * boss_normal_multiplier("METEOR_PROC", dict(mastery_boss=0, mastery_normal=0)) if unlocked("METEOR_PROC") else 0.0

# Level 126/130 Flame Haze burn-stacking mastery — independent re-derivation (Little's Law), not
# transcribed from the Excel formula strings (see build_fp_mage_workbook's own docstrings for the
# same derivation): Basic Attack/Meteor Shower/Meteor Proc/Ifrit each add an independent 5%-per-
# cast/proc chance to also inflict Flame Haze's burn DoT, whose own cast can't stack with itself
# but these proc-triggered instances can coexist with it and each other.
meteor_shower_rate = 1 / eff_cooldown(SKILLS["METEOR_SHOWER_BURST"]["cooldown"], SKILLS["METEOR_SHOWER_BURST"]["costs_action"])
ifrit_rate = 1 / eff_cooldown(SKILLS["IFRIT"]["cooldown"], SKILLS["IFRIT"]["costs_action"])
flame_haze_extra_rate = 0.05 * (basic_attacks_per_second + meteor_shower_rate + meteor_proc_rate + ifrit_rate) if level >= 126 else 0.0
flame_haze_burst_cooldown = SKILLS["FLAME_HAZE_BURST"]["cooldown"]
flame_haze_dot_stack_multiplier = 1 + flame_haze_extra_rate * flame_haze_burst_cooldown
flame_haze_total_stacks = (
    SKILLS["FLAME_HAZE_DOT"]["window"] / flame_haze_burst_cooldown + flame_haze_extra_rate * SKILLS["FLAME_HAZE_DOT"]["window"]
)
skill_dps["FLAME_HAZE_DOT"] *= flame_haze_dot_stack_multiplier
if level >= 130:
    skill_dps["IFRIT"] *= 1 + 0.2 * flame_haze_total_stacks

total_dps = basic_dps + sum(skill_dps.values())

print(f"Burning Magic multiplier   = {burning_magic_mult:.6f}")
print(f"Elemental Decrease multiplier (always-on) = {elemental_decrease_mult:.6f}")
print(f"Average buff multiplier    = {avg_buff_mult:.6f}")
print(f"Attack speed buff bonus %  = {as_bonus:.6f}")
print(f"Actions/sec                = {actions_per_second:.6f}")
print(f"Cast rate (subtracted)     = {cast_rate:.6f}")
print(f"Basic attacks/sec          = {basic_attacks_per_second:.6f}")
print(f"Meteor Proc trigger rate R = {meteor_trigger_rate:.6f}, proc rate = {meteor_proc_rate:.6f}")
print(f"Basic Attack DPS           = {basic_dps:.4f}")
for k, v in skill_dps.items():
    print(f"  {k:28s} DPS = {v:.4f}")
print(f"TOTAL DPS                  = {total_dps:.4f}")

# ---------------------------------------------------------------------------
# Cross-check against the actual live workbook (evaluated with `formulas`,
# not just the static values openpyxl wrote)
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
py_skill_dps["BASIC_ATTACK"] = basic_dps

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
