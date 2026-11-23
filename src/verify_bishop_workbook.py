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
import os
import re
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
XLSX_PATH = REPO / "Bishop" / "Bishop-DPS-Calculator.xlsx"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_bishop_workbook import ROW, IN, UNLOCK_LEVEL, SUMMARY_ROW, CONTENT_TYPES  # noqa: E402
from build_bishop_workbook import (  # noqa: E402
    STATUS_CAST_PREFIX, STATUS_GROUPS, STATUS_BUFFS, STATUS_UNIFORM_ROWS, STATUS_PHI_ROWS, STATUS_FS_KEYS, STATUS_MAIN_LAYOUT, INFINITY_RAMP,
)
import status_timeline as stl  # noqa: E402
import companion_python_model as cpm  # noqa: E402

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

# Most Inputs rows are now per-content-type (columns C-L, one per CONTENT_TYPES entry); column B
# holds a live =INDEX(...) formula picking the active one, which openpyxl can't evaluate (this
# script never round-trips through Excel, so there's no cached value either). Resolve the active
# content type first, then read straight from its own column instead of B.
_ct_col = {}
for _c in range(3, 3 + len(CONTENT_TYPES)):
    _name = _inputs_ws.cell(row=2, column=_c).value
    if _name in CONTENT_TYPES:
        _ct_col[_name] = _c


def _in(key):
    if key in ("level", "content_type"):
        return _inputs_ws.cell(row=IN[key], column=2).value
    active_ct = _inputs_ws.cell(row=IN["content_type"], column=2).value
    value = _inputs_ws.cell(row=IN[key], column=_ct_col.get(active_ct, 2)).value
    # A blank per-content-type cell (key not applicable to the active content type) mirrors Excel's
    # INDEX-into-an-empty-cell behavior (0, not None) for the workbook's live =INDEX(...) formula.
    return 0 if value is None else value


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
flat_attack, attack_pct = _in("flat_attack"), _in("attack_pct")
attack = flat_attack * (1 + attack_pct / 100)
flat_int, int_pct, luk = _in("flat_int"), _in("int_pct"), _in("luk")
defense_pct = _in("defense_pct")
damage = _in("damage")
damage_amp = _in("damage_amp")
boss_damage = _in("boss_damage")
normal_damage = _in("normal_damage")
status_effect_damage = _in("status_effect_damage")
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
max_enemies_hit = _in("max_enemies_hit") or 0  # blank for content types where it's not applicable (Excel treats blank as 0 in MIN(); doesn't affect result since normal_weight is 0 there)

fixed_duration_active = monster_type != "pvp" and fight_duration > 0

basic_lvl = input_level(4, level, skill1, skill2, skill3, skill4, skill_all)
skill_coefficient_base = 290 * get_factor(basic_lvl, 21) / 1000
print(f"SKILL_COEFFICIENT (base) = {skill_coefficient_base:.4f}")


def level_gated_sum(pairs):
    return sum(inc for lvl, inc in pairs.items() if level >= lvl)


big_bang_mastery = level_gated_sum({102: 10, 106: 11, 116: 12, 120: 13, 128: 14, 132: 15})
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
    "HEAL": dict(job_step=2, cooldown=18, duration=heal_duration, base=100, fidx=21, scales=True,
                 costs_action=True, mastery=level_gated_sum({54: 8}), target="ATTACK"),
    "BLESS": dict(job_step=2, cooldown=24, duration=bless_duration, base=160, fidx=21, scales=True,
                  costs_action=True, target="ATTACK"),
    "HOLY_MAGIC_SHELL": dict(job_step=3, cooldown=27, duration=22, base=150, fidx=21, scales=True,
                              costs_action=True, target="ATTACK"),
    "ADVANCED_BLESSING": dict(job_step=4, cooldown=26, duration=20, base=70, fidx=21, scales=True,
                               costs_action=True, mastery=level_gated_sum({113: 4}), target="FINAL_DAMAGE"),
    "INFINITY": dict(job_step=4, cooldown=30, duration=15, base=150, fidx=21, scales=True,
                      costs_action=True, ramp_mult=64 / 45, target="FINAL_DAMAGE"),
}
PASSIVES = {
    "BUFF_MASTERY": dict(job_step=4, base=100, fidx=22, scales=True),
    "ARCANE_AIM": dict(job_step=4, base=30, fidx=22, scales=True),
    "ELEMENT_AMPLIFICATION": dict(job_step=3, base=150, fidx=22, scales=True),
    "DIVINE_PROTECTION": dict(job_step=3, base=250, fidx=22, scales=True),
    "MP_EATER_MP_BOOST": dict(job_step=2, base=70, fidx=0, scales=False),
    "BLOOD_OF_THE_DIVINE": dict(job_step=4, base=50, fidx=22, scales=True),
    "MAPLE_HERO_BISHOP": dict(job_step=4, base=500, fidx=23, scales=True),
    "HOLY_SYMBOL": dict(job_step=3, base=150, fidx=22, scales=True, mastery=level_gated_sum({90: 25})),
}
NORMAL_MONSTER_TARGETS = {k: v["targets"] for k, v in SKILLS.items()}


def enemies_hit(key):
    """How many enemies one attack of this skill hits: 1 vs boss/PvP, the skill's own target count (capped by Inputs max_enemies_hit)
    vs normal monsters."""
    if monster_type == "pvp":
        return 1
    targets = 6 + basic_attack_target_increase if key == "BIG_BANG" else NORMAL_MONSTER_TARGETS.get(key, 1)
    return min(targets, max_enemies_hit)


def branch_multipliers(key, s):
    """(boss-branch, normal-branch) multiplier: Boss/Normal Monster Damage% and target count, each branch with its own full
    (1+damage%/100)*targets treatment (PvP: single target, neither bonus)."""
    if monster_type == "pvp":
        return 1.0, 1.0
    boss_term = boss_damage + s.get("mastery_boss", 0) + monster_dmg_bonus
    normal_term = normal_damage + s.get("mastery_normal", 0) + normal_dmg_bonus
    return 1 + boss_term / 100, (1 + normal_term / 100) * enemies_hit(key)


_BRANCH_PAIRS = {}   # key -> (boss DPS, normal DPS, explicit units?, boss mult, normal mult) of the last blend_branches call


def blend_branches(key, s, boss_unit, normal_unit=None):
    """Time-weighted DPS of one skill: (1-w)*boss_unit*boss_branch + w*normal_unit*normal_branch, where the units are
    the per-branch rate x damage (they differ only for the per-enemy proc rows, whose rate depends on the branch).
    The Status/KO timing factor of the row is folded into each branch."""
    explicit = normal_unit is not None
    if normal_unit is None:
        normal_unit = boss_unit
    b, n = branch_multipliers(key, s)
    fb, fn = timing_factors(key)
    b, n = b * fb, n * fn
    _BRANCH_PAIRS[key] = (boss_unit * b, normal_unit * n, explicit, b, n)
    return (1 - normal_weight) * boss_unit * b + normal_weight * normal_unit * n


def unlocked(key):
    threshold = UNLOCK_LEVEL.get(key)
    return threshold is None or level >= threshold


PVP_FIGHT_DURATION = _in("pvp_fight_length") or 15  # PvP fight length is an Inputs cell now (default 15)


def ticks(window, icd):
    """Whole ticks only: a summon / DoT cannot land a fractional hit (mirrors the workbook's INT(window/ICD+1e-9))."""
    return math.floor(window / icd + 1e-9)


def capped_window(window):
    """PvP fights last PVP_FIGHT_DURATION seconds, so a longer summon / DoT window can only tick that long."""
    return min(window, PVP_FIGHT_DURATION) if monster_type == "pvp" else window


def eff_cooldown(cooldown, costs_action=None, exempt=False):
    """Effective cooldown. Skill Cooldown Decrease applies to EVERY real cooldown — actively cast skills,
    buffs and passives alike (user decision 2026-10-21; `costs_action` is kept only for call-site
    compatibility and no longer gates CDR). `exempt=True` marks the trigger-rate / internal-interval
    surrogate rows (mirror of the build script's CDR_EXEMPT_ROW_KEYS)."""
    if monster_type == "pvp":
        return PVP_FIGHT_DURATION
    return max(0.1, cooldown - (0 if exempt else skill_cooldown_decrease))


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
        full_window_ticks = ticks(window, icd)
        last_cast_ticks = ticks(min(window, remaining_after_last), icd)
    else:
        full_window_ticks = 1
        last_cast_ticks = 1
    return hits_per_cast * ((casts - 1) * full_window_ticks + last_cast_ticks)


def exact_buff_uptime(cooldown, buff_duration):
    casts = exact_casts(cooldown)
    remaining_after_last = max(0.0, fight_duration - (casts - 1) * cooldown)
    last_uptime = min(buff_duration, remaining_after_last)
    return (casts - 1) * min(buff_duration, cooldown) + last_uptime


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

# Divine Protection: auto-triggering +25%->X% Defense buff, 15s window every 20s, duty-cycle-
# averaged exactly like Holy Symbol (real buff row, gets the exact fixed-duration branch too).
divine_protection_pct = coeff_pct(250, 22, True, 3) if unlocked("DIVINE_PROTECTION") else 0.0
if unlocked("DIVINE_PROTECTION"):
    dp_eff_cd = eff_cooldown(20, False)
    if fixed_duration_active:
        dp_uptime = exact_buff_uptime(dp_eff_cd, eff_duration(15)) / fight_duration
    elif monster_type == "pvp":
        dp_uptime = min(eff_duration(15), PVP_FIGHT_DURATION) / PVP_FIGHT_DURATION
    else:
        dp_uptime = min(1.0, eff_duration(15) / dp_eff_cd)
    divine_protection_bonus = divine_protection_pct * dp_uptime
else:
    divine_protection_bonus = 0.0

total_defense = defense * (1 + (defense_pct + divine_protection_bonus) / 100)
invincible_conversion_rate = 10 * get_factor(level, 22) / 1000
invincible_int_bonus = invincible_conversion_rate / 100 * total_defense if level >= 35 else 0.0
stat_damage = ((flat_int + invincible_int_bonus) * (1 + int_pct / 100)) * 0.01 + luk * 0.0025
monster_defense = _compute_monster_defense(content_type, chapter, stage, total_defense)

# Holy Fountain - Boss Monster Damage (Mastery Lv.68, patched 10%->20%): flat, non-scaling,
# duty-cycle-averaged off Holy Fountain's own (patched 30s) cooldown, linger 15s.
holy_fountain_cooldown = 30
if level >= 68:
    hf_eff_cd = eff_cooldown(holy_fountain_cooldown, True)
    if monster_type == "pvp":
        hf_uptime = min(eff_duration(15), PVP_FIGHT_DURATION) / PVP_FIGHT_DURATION
    else:
        hf_uptime = min(1.0, eff_duration(15) / hf_eff_cd)
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
        hsym_uptime = min(1.0, eff_duration(holy_symbol_duration) / hsym_eff_cd)
    normal_dmg_bonus = holy_symbol_pct * hsym_uptime
else:
    normal_dmg_bonus = 0.0

# Holy Symbol's Mastery Lv.90 "Damage Boost" — solo-always-true.
damage_bonus = holy_symbol_mastery_pct

# Blood of the Divine: assumed 100% HP -> +20% Crit Damage (4x its own Final-Damage F-value).
crit_damage_bonus = 4 * blood_divine_pct

# MP Eater + Blood of the Divine's own AS mastery (flat, always-on, no uptime averaging), plus
# Nimble Feet (universal 1st-Job Explorer AS buff, duty-cycle averaged — real duration/cooldown,
# not the ATTACK/FINAL_DAMAGE bucket loop above since Attack Speed combines via diminishing
# returns, not straight addition/multiplication).
nimble_feet_pct = coeff_pct(150, 0, False, 1)
nimble_feet_eff_cd = eff_cooldown(60, True)
if fixed_duration_active:
    nimble_feet_uptime = exact_buff_uptime(nimble_feet_eff_cd, eff_duration(15)) / fight_duration
elif monster_type == "pvp":
    nimble_feet_uptime = min(eff_duration(15), PVP_FIGHT_DURATION) / PVP_FIGHT_DURATION
else:
    nimble_feet_uptime = min(1.0, eff_duration(15) / nimble_feet_eff_cd)
nimble_feet_avg = nimble_feet_pct * nimble_feet_uptime if unlocked("NIMBLE_FEET") else 0.0

as_bonus = (mp_eater_as_pct if unlocked("MP_EATER_MP_BOOST") else 0.0) + (15 if level >= 134 else 0) + nimble_feet_avg

actions_per_second = 1 + min(150, 150 * (1 - (1 - attack_speed_base / 150) * (1 - as_bonus / 150))) / 100

# ---------------------------------------------------------------------------------------------------------------
# Status Effect Damage / KO timeline engine (src/status_timeline.py `solve`, the plain-Python reference): fixed-length single-target content with KO phases
# (World Boss, Enhancement Dungeon) or any stun/freeze (companion, or the player's own Angel Ray from Lv.103).  The player casts Magic Guard, Heal, Bless, Holy
# Magic Shell, Advanced Blessing, Infinity and the cooldown skills when they pay most; Nimble Feet / Holy Fountain / Holy Symbol / Divine Protection / Triumph
# Feather keep their averaged formulas.
# ---------------------------------------------------------------------------------------------------------------
_companion_choice0 = _in("companion_choice")
_ci0 = openpyxl.load_workbook(XLSX_PATH)["CompanionsInput"]
_lv0 = next((_ci0.cell(row=r, column=2).value for r in range(1, _ci0.max_row + 1) if _ci0.cell(row=r, column=1).value == _companion_choice0), None)
try:
    c_level0 = int(float(_lv0))
except (TypeError, ValueError):
    c_level0 = 0
_stub = dict(mt=monster_type, T=fight_duration, content=content_type, pvp_len=PVP_FIGHT_DURATION, cap=max_enemies_hit, w=normal_weight, unit=1.0,
             bad=0.0, sd=0.0, aps=1.5, avgbuff=1.0, attack_bucket_avg=0.0, charm_val=0.0, agg_damage_avg=0.0, hex_avg=0.0, hex_snap=lambda st: 0.0,
             avgbuff_snap=lambda charm, extra: 1.0, agg_fd_boss_only=0.0, agg_fd_norm_only=0.0, chalice_avg_boss=0.0, chalice_avg_norm=0.0,
             chalice_full=0.0, horn_avg=0.0, horn_full=0.0, boss_pct=0.0, norm_pct=0.0, extra_boss=1.0, extra_norm=1.0, player_boss=1.0, player_norm=1.0, player_uniform_boss=1.0,
             player_basic_boss=0.5, player_basic_norm=0.5, cr_total=0.0, cd_total=0.0, min_dmg=100.0, max_dmg=100.0, defense=0.0, def_pen=0.0, taken_bucket=0.0)
# The player's own stunning skill (game table): Angel Ray stuns for 1 s (cooldown 17 s, no Reuse mastery, unlock Lv.103), cast on cooldown from the start.
PLAYER_STUN = [
    dict(id="RAY", key="ANGEL_RAY", typ="cast", dur=1.0, p=1.0, cd=17, min_level=0, tick=1.0, win=0.0),
]
_pl_on = any(unlocked(e["key"]) and level >= e["min_level"] for e in PLAYER_STUN)
_stun_in0 = _companion_choice0 != "None" and c_level0 >= 1
# The workbook's effective Companion Summoning Time Increase is the Inputs value + Arwen's Glass Shoes (+20% star 0 .. +40% star 5, Artifacts row
# arwens_glass_shoes_summon_time_increase_pct).  The verify run clears the artifact slots, so the artifact term is 0 in every cpm.run below; it is
# covered by the equivalence test (artifact at Inputs x == no artifact at Inputs x + star value).
hasstun = (_stun_in0 and bool(cpm.run(_stub, _companion_choice0, c_level0, companion_summon_time_increase_pct).get("hasstun"))) or _pl_on
KO_WINDOWS = {"World Boss": [(24, 34), (59, 69)], "Enhancement Dungeon": [(fight_duration - 4.5, fight_duration)]}
status_on = fixed_duration_active and normal_weight == 0 and (content_type in KO_WINDOWS or hasstun)
# the stun skill's first cast: t=0 with the engine on, otherwise after the buff-casting startup (Summary's startup cell: every unlocked action-costing buff incl. Nimble Feet)
_startup_plain = (
    (sum(1 for _k, b in BUFFS.items() if b["costs_action"] and unlocked(_k)) + (1 if unlocked("NIMBLE_FEET") else 0)) / actions_per_second
    if fixed_duration_active else 0.0)
_t0_pl = 0.0 if status_on else _startup_plain
PST = [dict(id=e["id"], typ=e["typ"], cd=eff_cooldown(e["cd"], True), dur=e["dur"], p=e["p"], on=unlocked(e["key"]) and level >= e["min_level"],
            t0=_t0_pl, tick=e["tick"], win=e["win"]) for e in PLAYER_STUN]
_stub["pst"] = PST
stun_info = cpm.run(_stub, _companion_choice0 if _stun_in0 else "None", c_level0, companion_summon_time_increase_pct)
stf_b = stun_info["stunfracB"]
stf_n = stun_info["stunfracN"]


def buff_pct_py(key):
    """Calc!F of a buff row: the factor-curve value (Infinity: x64/45, the time-average of its ramp) + the row's own mastery (percentage points)."""
    b = BUFFS[key]
    pct = coeff_pct(b["base"], b["fidx"], b["scales"], b["job_step"])
    if "ramp_mult" in b:
        pct *= b["ramp_mult"]
    return pct + b.get("mastery", 0)


E_ENGINE = None
ENGINE_N = {}
engine_bbuff_mean = None
if status_on:
    # companion stun windows (none when no companion stuns and no player stun exists: the mirror then returns no stun_vector) + the player's own
    _comp_stun = stun_info["stun_vector"](stl.NB_MAX) if "stun_vector" in stun_info else [0.0] * stl.NB_MAX
    _stun_vec = [min(1.0, a + b) for a, b in zip(_comp_stun, stl.pl_stun_vector([dict(e, t0=0.0) for e in PST], fight_duration, stl.NB_MAX))]
    _inf_dur, _inf_cd = eff_duration(BUFFS["INFINITY"]["duration"]), eff_cooldown(BUFFS["INFINITY"]["cooldown"], True)
    # Advanced Blessing's strip effect carries Infinity's steady-state average (mean-field cross term, see fd_cross_scale in the builder)
    _cross = 1 + (buff_pct_py("INFINITY") * min(1.0, _inf_dur / _inf_cd) / 100 if unlocked("INFINITY") else 0.0)
    _buffs = []
    for _bid, _key, _kind in STATUS_BUFFS:
        _b = BUFFS[_key]
        _dur, _cd = eff_duration(_b["duration"]), eff_cooldown(_b["cooldown"], _b["costs_action"])
        _bd = dict(id=_bid, kind=_kind, F=buff_pct_py(_key), dur=_dur, cd=_cd, on=unlocked(_key))
        if _bid == "AB":
            _bd.update(F=buff_pct_py(_key) * _cross, dur=min(_dur, _cd), p0=1, p1=1, ramp_t=1, dur0=1)
        elif _kind == "ramp":
            _bd.update(INFINITY_RAMP)
        _buffs.append(_bd)
    _eng_host = dict(T=fight_duration, S=status_effect_damage, ko=KO_WINDOWS.get(content_type, []), hex_v=0.0, hex_period=20, hex_max=3, A0=0.0,
                     charm_v=0.0, hex_avg=0.0, c_slot=0.0, stun=_stun_vec, buffs=_buffs, groups=[])
    _e1 = stl.solve(_eng_host)               # pass 1: the buff schedule (independent of the skill weights)
    engine_bbuff_mean = _e1["Bbuff_mean"]
    for _bid, _key, _kind in STATUS_BUFFS:
        ENGINE_N[_key] = _e1["buffs"][_bid]["n"]

# Buff-Casting Startup Delay: in fixed-duration fights, the character casts every currently-
# unlocked, actively-cast buff sequentially at fight start (1/APS seconds each, same cadence as
# every other action-costing skill) before their first damage-skill cast — so damage skills'
# usable window is reduced by this amount.  With the engine on the buffs are cast when they pay: no start-up delay.
if fixed_duration_active and not status_on:
    buff_cast_startup_time = (
        sum(1 for key, b in BUFFS.items() if b["costs_action"] and unlocked(key))
        + (1 if unlocked("NIMBLE_FEET") else 0)
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


# Average buff multiplier. Magic Guard, Heal, Bless, and Holy Magic Shell are all "+X% Attack"
# sources — same bucket, so they sum into one combined percentage before a single
# multiplication; Advanced Blessing and Infinity are both Final Damage, a different (and
# deliberately still multiplicative) bucket, so they stay their own separate factors.
# With the engine on, every buff's uptime comes from the engine's cast count (Calc!R) and Summary's factor IS the strip's mean buff bucket.
attack_bucket_sum = 0.0
final_damage_mult = 1.0
for key, b in BUFFS.items():
    if not unlocked(key):
        continue
    pct = buff_pct_py(key)
    eff_cd = eff_cooldown(b["cooldown"], b["costs_action"])
    if fixed_duration_active:
        casts_b = ENGINE_N.get(key)
        if casts_b is None:
            uptime_fraction = exact_buff_uptime(eff_cd, eff_duration(b["duration"])) / fight_duration
        else:   # the workbook's exact-uptime formula at the engine's cast count
            _dur_b = eff_duration(b["duration"])
            uptime_fraction = ((casts_b - 1) * min(_dur_b, eff_cd) + min(_dur_b, max(0.0, fight_duration - (casts_b - 1) * eff_cd))) / fight_duration
    elif monster_type == "pvp":
        uptime_fraction = min(eff_duration(b["duration"]), PVP_FIGHT_DURATION) / PVP_FIGHT_DURATION
    else:
        uptime_fraction = min(1.0, eff_duration(b["duration"]) / eff_cd)
    avg_pct = pct * uptime_fraction
    if b["target"] == "ATTACK":
        attack_bucket_sum += avg_pct
    else:
        final_damage_mult *= 1 + avg_pct / 100
avg_buff_mult = engine_bbuff_mean if status_on else (1 + attack_bucket_sum / 100) * final_damage_mult


def hit_damage(coeff_pct_val, is_basic, s, key):
    effective_coeff = coeff_pct_val * (1 + s.get("mastery", 0) / 100)  # a skill mastery MULTIPLIES the skill's damage (game-confirmed 2026-11-03); fold-ins stay additive
    base_damage = attack * (effective_coeff / 100)
    dmg_reduction = 5000 / (6000 + monster_defense * (1 - def_pen / 100))
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
    # Boss/Normal Monster Damage% is deliberately NOT applied here — it's blended per-branch in
    # branch_multipliers, applied by the caller.
    base_hit = (
        base_damage * (1 + stat_damage / 100) * (1 + (damage + damage_bonus) / 100)
        * (1 + damage_amp / 100) * dmg_reduction * final_mult * (1 + source_pct / 100) * extra_mult
    )
    non_crit_min = base_hit * min(min_damage, max_damage) / 100
    non_crit_max = base_hit * max_damage / 100
    non_crit_avg = (non_crit_min + non_crit_max) / 2
    crit_avg = non_crit_avg * (1 + (crit_damage + crit_damage_bonus) / 100)
    cr = min(crit_rate, 100) / 100
    return non_crit_avg * (1 - cr) + crit_avg * cr


# ---- Status/KO engine pass 2: the skills' casts.  Weight of one cast = its boss damage before any timing factor (hits x expected hit x boss multiplier).
PHI_ROWS = {}
PHI_UNIF = 1.0
E_FS = {}
if status_on:
    def _percast(key):
        if not unlocked(key):
            return 0.0
        sk = SKILLS[key]
        pct = coeff_pct(sk["base"], sk["fidx"], sk["scales"], sk["job_step"])
        hd = hit_damage(pct, False, sk, key)
        hits = sk["hits"] * (ticks(capped_window(sk["window"]), sk["icd"]) if sk.get("icd") else 1)
        return hits * hd * branch_multipliers(key, sk)[0]
    _bb_s = dict(mastery=big_bang_mastery, mastery_boss=big_bang_boss_mastery)
    _c_slot = (big_bang_hits * hit_damage(skill_coefficient_base, True, _bb_s, "BIG_BANG") * branch_multipliers("BIG_BANG", _bb_s)[0]
               if unlocked("BIG_BANG") else 0.0)
    _groups = []
    for _gid, _cast, _ents in STATUS_GROUPS:
        _entries = []
        for _row, _typ, _win, _gate, _wk in _ents:
            _w = _percast(_wk)
            if _gate and not unlocked(_gate):
                _w = 0.0
            _entries.append(dict(row=_row, typ=_typ, w=_w, L=(capped_window(SKILLS[_win]["window"]) if _win else 1),
                                 on=(1 if (not _gate or unlocked(_gate)) else 0)))
        _groups.append(dict(id=_gid, cd=eff_cooldown(SKILLS[_cast]["cooldown"], SKILLS[_cast]["costs_action"]),
                            on=unlocked(_cast), slot=True, entries=_entries,
                            fixed=_cast in {e["key"] for e in PLAYER_STUN}, t0=0.0))
    E_ENGINE = stl.solve(dict(_eng_host, groups=_groups, c_slot=_c_slot))
    for _row, _pfx in STATUS_CAST_PREFIX.items():
        if _pfx.startswith("grp."):
            ENGINE_N[_row] = E_ENGINE["groups"][_pfx[4:]]["n"]
    PHI_ROWS = E_ENGINE["rows"]
    PHI_UNIF = E_ENGINE["phi_unif"]
    E_FS = E_ENGINE["fs"]
    print(f"Status/KO engine ON: casts {{ {', '.join(f'{k}: {v}' for k, v in ENGINE_N.items() if k in SKILLS or k in BUFFS)} }}, phi_unif {PHI_UNIF:.4f}")


def timing_factors(key):
    """(boss-branch, normal-branch) timing factor of a damage row: the engine's phi (rows it casts), phi_unif (uniformly spread rows)
    or, with the engine off, the uniform 1 + Status Effect Damage x stunned share.  Normal branch: always the uniform stun factor."""
    fn = 1 + status_effect_damage / 100 * stf_n
    if status_on:
        if key in STATUS_PHI_ROWS:
            return PHI_ROWS.get(key, 1.0), fn
        if key in STATUS_UNIFORM_ROWS:
            return PHI_UNIF, fn
        return 1.0, fn
    return 1 + status_effect_damage / 100 * stf_b, fn


def cast_rate_py(key):
    """Casts per second of an action-costing skill: the engine's count with the engine on, else the exact / steady-state count."""
    if key in ENGINE_N and fixed_duration_active:
        return ENGINE_N[key] / fight_duration
    eff = eff_cooldown(SKILLS[key]["cooldown"], SKILLS[key]["costs_action"])
    return non_buff_casts(eff) / fight_duration if fixed_duration_active else 1 / eff


if fixed_duration_active:
    cast_rate = sum(ENGINE_N[k] if k in ENGINE_N else non_buff_casts(eff_cooldown(SKILLS[k]["cooldown"], SKILLS[k]["costs_action"]))
                    for k, s in SKILLS.items() if s["costs_action"] and unlocked(k))
    cast_rate += sum(ENGINE_N[key] if key in ENGINE_N else exact_casts(eff_cooldown(b["cooldown"], b["costs_action"]))
                     for key, b in BUFFS.items() if b["costs_action"] and unlocked(key))
    cast_rate += non_buff_casts(eff_cooldown(holy_fountain_cooldown, True)) if unlocked("HOLY_FOUNTAIN") else 0
    cast_rate += exact_casts(nimble_feet_eff_cd) if unlocked("NIMBLE_FEET") else 0
    cast_rate /= fight_duration
else:
    cast_rate = sum(1 / eff_cooldown(SKILLS[k]["cooldown"], s["costs_action"]) for k, s in SKILLS.items() if s["costs_action"] and unlocked(k))
    cast_rate += sum(1 / eff_cooldown(b["cooldown"], b["costs_action"]) for key, b in BUFFS.items() if b["costs_action"] and unlocked(key))
    cast_rate += (1 / eff_cooldown(holy_fountain_cooldown, True)) if unlocked("HOLY_FOUNTAIN") else 0
    cast_rate += (1 / nimble_feet_eff_cd) if unlocked("NIMBLE_FEET") else 0
big_bang_per_second = max(0, actions_per_second - cast_rate)

_bb_s = dict(mastery=big_bang_mastery, mastery_boss=big_bang_boss_mastery)
big_bang_hit = hit_damage(skill_coefficient_base, True, _bb_s, "BIG_BANG")
big_bang_dps = blend_branches("BIG_BANG", _bb_s, big_bang_hits * big_bang_hit * big_bang_per_second) if unlocked("BIG_BANG") else 0.0

skill_dps = {}
for key, s in SKILLS.items():
    if not unlocked(key):
        skill_dps[key] = 0.0
        continue
    pct = coeff_pct(s["base"], s["fidx"], s["scales"], s["job_step"])
    hd = hit_damage(pct, False, s, key)
    if key == "ANGEL_RAY_BOSS_PROC":
        if status_on and key in ENGINE_N:
            rate = s["hits"] * ENGINE_N[key] / fight_duration
        else:
            eff_cd = eff_cooldown(SKILLS["ANGEL_RAY"]["cooldown"], SKILLS["ANGEL_RAY"]["costs_action"])
            if fixed_duration_active:
                rate = non_buff_total_hits(eff_cd, s["hits"], s.get("icd"), s.get("window")) / fight_duration
            else:
                hits = s["hits"] * (ticks(capped_window(s["window"]), s["icd"]) if s.get("icd") else 1)
                rate = hits / eff_cd
        # Boss-only effect (per its own name/Note) — scales with boss_dmg_pct alone, zero
        # contribution from the normal branch (U = 0); PvP keeps boss/normal damage% out entirely, matching every other skill's pvp branch.
        skill_dps[key] = blend_branches(key, s, rate * hd, 0.0)
        continue
    eff_cd = eff_cooldown(s["cooldown"], s["costs_action"])
    if status_on and key in ENGINE_N:
        # engine casts: a summon / DoT row's hits = hits per full window x effective casts (last window truncated at the fight end)
        _per_cast = s["hits"] * (ticks(capped_window(s["window"]), s["icd"]) if s.get("icd") else 1)
        rate = _per_cast * (E_FS[key] if key in STATUS_FS_KEYS else ENGINE_N[key]) / fight_duration
    elif fixed_duration_active:
        rate = non_buff_total_hits(eff_cd, s["hits"], s.get("icd"), s.get("window")) / fight_duration
    else:
        hits = s["hits"] * (ticks(capped_window(s["window"]), s["icd"]) if s.get("icd") else 1)
        rate = hits / eff_cd
    skill_dps[key] = blend_branches(key, s, rate * hd)

# Triumph Feather: bespoke 2-stage steady-state proc (see build_bishop_workbook.py's own Note on
# this row for the full derivation). R = the character's total attack rate (Actions Per Second).
if unlocked("TRIUMPH_FEATHER"):
    tf_base = 1500
    tf_fidx = 21
    tf_hd = hit_damage(coeff_pct(tf_base, tf_fidx, True, 3), False, dict(mastery=level_gated_sum({73: 50})), "TRIUMPH_FEATHER")
    p1 = 25 if level >= 78 else 15
    d1 = 10
    tf_cd = eff_cooldown(18, True)
    p2 = 35
    icd2 = 1

    # Both stages roll "When attacking, X% chance" once per ATTACK per ENEMY HIT (user, 2026-11-04): an action that
    # hits N enemies triggers a stage with q = 1-(1-c)^N. Action stream = Big Bang (6+bti targets) + every action-slot
    # cast; only Angel Ray / Genesis casts hit a known enemy count, every other cast (buffs, Bahamut's summon cast)
    # is a single roll. Rates are per branch (boss/PvP: N=1; normal: N=min(targets, max_enemies_hit)).
    def tf_hit_rate(k):
        if not (SKILLS[k]["costs_action"] and unlocked(k)):
            return 0.0
        return cast_rate_py(k)

    def tf_x(chance, normal_branch):
        def q(targets):
            n = min(targets, max_enemies_hit) if (normal_branch and monster_type != "pvp") else 1
            return 1 - (1 - chance) ** n
        hit_rates = {k: tf_hit_rate(k) for k in ("ANGEL_RAY", "GENESIS")}
        x = big_bang_per_second * q(6 + basic_attack_target_increase)
        x += (cast_rate - sum(hit_rates.values())) * chance
        x += sum(rt * q(NORMAL_MONSTER_TARGETS[k]) for k, rt in hit_rates.items())
        return x

    def tf_branch_rate(normal_branch):
        x1, x2 = tf_x(p1 / 100, normal_branch), tf_x(p2 / 100, normal_branch)
        return (x1 * d1) / (1 + x1 * tf_cd) * x2 / (1 + icd2 * x2)

    tf_targets = triumph_feather_targets
    tf_hits = 3 if level >= 104 else 2
    # the branch multipliers use the row's own target count (1, or 7 from Lv.94), capped by Max Enemies
    _tf_s = dict(mastery=level_gated_sum({73: 50}))
    NORMAL_MONSTER_TARGETS["TRIUMPH_FEATHER"] = tf_targets
    skill_dps["TRIUMPH_FEATHER"] = blend_branches("TRIUMPH_FEATHER", _tf_s, tf_hits * tf_hd * tf_branch_rate(False), tf_hits * tf_hd * tf_branch_rate(True))
else:
    skill_dps["TRIUMPH_FEATHER"] = 0.0

total_dps = big_bang_dps + sum(skill_dps.values())

# ---------------------------------------------------------------------------------------------------------------
# Companion: plain-Python port (src/companion_python_model.py) of src/companion_model.py's rules, fed with this script's own numbers for the player's
# pipeline.  The verify run clears the artifact slots, so the artifact snapshot terms (Hexagon, Charm, Chalice) are zero here; they are covered by the
# dedicated hand checks instead.
# ---------------------------------------------------------------------------------------------------------------
companion_choice = _in("companion_choice")
_ci_ws = openpyxl.load_workbook(XLSX_PATH)["CompanionsInput"]
_lv = next((_ci_ws.cell(row=r, column=2).value for r in range(1, _ci_ws.max_row + 1)
            if _ci_ws.cell(row=r, column=1).value == companion_choice), None)
try:
    c_level = int(float(_lv))
except (TypeError, ValueError):
    c_level = 0          # "Not unlocked" / no companion
companion_dps = 0.0
companion_result = None
if (companion_choice != "None" and c_level >= 1) or _pl_on:
    # boss-only / normal-only DPS of the player's rows (for the damage-share-weighted uplift)
    pb_total = pn_total = pu_total = 0.0
    for key, val in list(skill_dps.items()) + [("BIG_BANG", big_bang_dps)]:
        pair = _BRANCH_PAIRS.get(key)
        if pair is None:
            continue
        bd, nd, explicit, bm_, nm_ = pair
        if explicit:
            pb_total += bd
            pn_total += nd
            _bd_row = bd
        else:  # multiplier-style rows: DPS = K x ((1-w) b + w n)  ->  boss DPS = K b
            denom = (1 - normal_weight) * bm_ + normal_weight * nm_
            pb_total += val * bm_ / denom
            pn_total += val * nm_ / denom
            _bd_row = val * bm_ / denom
        if key in STATUS_UNIFORM_ROWS:
            pu_total += _bd_row
    basic_pair = _BRANCH_PAIRS.get("BIG_BANG")
    if basic_pair is None:
        basic_b = basic_n = 0.0
    else:
        _den = (1 - normal_weight) * basic_pair[3] + normal_weight * basic_pair[4]
        basic_b = big_bang_dps * basic_pair[3] / _den
        basic_n = big_bang_dps * basic_pair[4] / _den
    att_full, fd_full = 0.0, 1.0
    for key, b in BUFFS.items():
        if not unlocked(key):
            continue
        if b["target"] == "ATTACK":
            att_full += buff_pct_py(key)
        elif b["target"] != "ATTACK_SPEED":
            fd_full *= 1 + buff_pct_py(key) / 100
    # the engine's mean Attack% bucket for the companion's `attack_bucket_avg` (Excel: F x exact uptime at the engine's cast count; the averaged formula otherwise)
    _atk_bucket_avg = attack_bucket_sum
    # Bishop's Damage% bucket is one additive sum (Inputs Damage% + Holy Symbol's Damage Boost + artifacts): the companion's debuffs and the Hexagon snapshot ratio use it
    _joint = damage + damage_bonus
    _boss_pct_c, _norm_pct_c = boss_damage + monster_dmg_bonus, normal_damage + normal_dmg_bonus
    comp_host = dict(
        mt=monster_type, T=fight_duration, content=content_type, pvp_len=PVP_FIGHT_DURATION, cap=max_enemies_hit, w=normal_weight,
        unit=hit_damage(100.0, True, dict(mastery=0), "BIG_BANG") / 100,
        bad=basic_attack_damage, sd=skill_damage, aps=actions_per_second,
        avgbuff=avg_buff_mult, attack_bucket_avg=_atk_bucket_avg,
        charm_val=0.0, agg_damage_avg=_joint, hex_avg=0.0, hex_snap=lambda st: 0.0,
        avgbuff_snap=lambda charm, extra: (1 + (att_full + charm + extra) / 100) * fd_full,
        agg_fd_boss_only=0.0, agg_fd_norm_only=0.0, chalice_avg_boss=0.0, chalice_avg_norm=0.0, chalice_full=0.0, horn_avg=0.0, horn_full=0.0,
        boss_pct=_boss_pct_c, norm_pct=_norm_pct_c, extra_boss=1.0, extra_norm=1.0,
        player_boss=pb_total, player_norm=pn_total,
        player_uniform_boss=pu_total, player_basic_boss=basic_b, player_basic_norm=basic_n,
        cr_total=crit_rate, cd_total=crit_damage + crit_damage_bonus, min_dmg=min_damage, max_dmg=max_damage, defense=monster_defense,
        def_pen=def_pen, pst=PST,
        taken_bucket=_joint,
        st=dict(on=status_on, S=status_effect_damage,
                mult=(list(E_ENGINE["mult"]) + [1.0] * (stl.NB_MAX - E_ENGINE["nb"])) if status_on else None,
                act=(list(E_ENGINE["act"]) + [0.0] * (stl.NB_MAX - E_ENGINE["nb"])) if status_on else None),
    )
    companion_result = cpm.run(comp_host, companion_choice if (companion_choice != "None" and c_level >= 1) else "None", c_level,
                               companion_summon_time_increase_pct)
    companion_dps = companion_result["comp_blend_dps"]
    print(f"Companion ({companion_choice} Lv{c_level}) DPS = {companion_dps:.4f}  (best candidate {companion_result['best']}, s={companion_result['s']}, "
          f"W={companion_result['W']:.2f}; damage {(1 - normal_weight) * companion_result['dmg_b'] + normal_weight * companion_result['dmg_n']:.4f}, "
          f"uplift {(1 - normal_weight) * companion_result['upl_b'] + normal_weight * companion_result['upl_n']:.4f})")
if os.environ.get("COMPARE_COMPANIONS"):
    _hb = locals().get("comp_host")
    if _hb is None:
        raise SystemExit("set companion_choice to any companion to build the host values first")
    _base = total_dps
    for _name in cpm.ck.COMPANIONS_ORDER:
        _r = cpm.run(_hb, _name, 10, companion_summon_time_increase_pct)
        print(f"  [compare Lv10] {_name:14s} blend DPS {_r['comp_blend_dps']:.4e}  = +{_r['comp_blend_dps'] / _base * 100:6.2f}% of player total (s={_r['s']:.1f}, W={_r['W']:.1f})")
total_dps += companion_dps

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

if status_on:
    # the engine strip itself: cast counts and timing factors against the Python reference
    for _row, _pfx in STATUS_CAST_PREFIX.items():
        if _row in ENGINE_N and _row in ROW:
            _addr = STATUS_MAIN_LAYOUT.s(_pfx + ".n").split("!")[1].replace("$", "")
            _xl, _py = read_cell("TIMELINE", _addr), ENGINE_N[_row]
            _ok = np.isclose(_xl, _py)
            print(f"  engine casts {_row:22s} python {_py:4.0f} workbook {_xl:4.0f}  {'OK' if _ok else 'MISMATCH'}")
            if not _ok:
                mismatches.append(("engine casts " + _row, _py, _xl))
    for _row, _py in PHI_ROWS.items():
        _addr = STATUS_MAIN_LAYOUT.s("phi." + _row).split("!")[1].replace("$", "")
        _xl = read_cell("TIMELINE", _addr)
        if not np.isclose(_xl, _py, rtol=1e-6):
            print(f"  engine phi {_row:22s} python {_py:.6f} workbook {_xl:.6f}  MISMATCH")
            mismatches.append(("engine phi " + _row, _py, _xl))

if mismatches:
    print(f"\n{len(mismatches)} mismatch(es) between the independent model and the live workbook.")
    sys.exit(1)
print("\nAll rows match between the independent model and the live workbook.")
