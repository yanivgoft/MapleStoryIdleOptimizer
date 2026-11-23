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
import os
import re
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
XLSX_PATH = REPO / "Bowmaster" / "Bowmaster-DPS-Calculator.xlsx"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_bowmaster_workbook import ROW, IN, UNLOCK_LEVEL, MAPLE_HERO_RATIOS, R_TOTAL  # noqa: E402
from build_bowmaster_workbook import STATUS_CAST_PREFIX, STATUS_GROUPS, STATUS_BUFFS, STATUS_UNIFORM_ROWS, STATUS_PHI_ROWS, STATUS_FS_KEYS, STATUS_MAIN_LAYOUT  # noqa: E402
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
from build_bowmaster_workbook import CONTENT_TYPES  # noqa: E402

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
    # A blank per-content-type cell (this key isn't applicable to the active content type — see
    # INPUT_ROW_APPLICABLE_CONTENT_TYPES) mirrors Excel's own INDEX-into-an-empty-cell behavior
    # (0, not blank/None) for the live =INDEX(...) formula in column B — matching that here keeps
    # this script's numeric comparisons consistent with what the real workbook actually computes,
    # instead of crashing on a None where the real formula would have used a harmless 0 (only the
    # already-zero-weighted branch for that content type ever reads it).
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
monster_defense = _compute_monster_defense(content_type, chapter, stage, defense)
flat_attack, attack_pct = _in("flat_attack"), _in("attack_pct")
attack = flat_attack * (1 + attack_pct / 100)
flat_dex, dex_pct, str_stat = _in("flat_dex"), _in("dex_pct"), _in("str")
stat_damage = (flat_dex * (1 + dex_pct / 100)) * 0.01 + str_stat * 0.0025
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


CDR_EXEMPT = {"QUIVER_CARTRIDGE", "ENCHANTED_QUIVER_DRAIN", "FLASH_MIRAGE"}  # mirrors the build script (Final Attack has no cooldown; Flash Mirage's cooldown is its real ICD)


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


def buff_avg(pct, duration, cooldown, costs_action):
    eff_cd = eff_cooldown(cooldown, costs_action)
    if fixed_duration_active:
        uptime = exact_buff_uptime(eff_cd, eff_duration(duration)) / fight_duration
    elif monster_type == "pvp":
        uptime = min(eff_duration(duration), PVP_FIGHT_DURATION) / PVP_FIGHT_DURATION
    else:
        uptime = min(1.0, eff_duration(duration) / eff_cd)
    return pct * uptime


_BRANCH_PAIRS = {}   # key -> (boss DPS, normal DPS) of the last branch_pair call (companion host: player boss / normal DPS of every row)


def branch_pair(key, rate_boss, rate_normal, hd_, mastery_boss, mastery_normal, targets):
    """Boss and normal DPS of one row (before weighting): rate x hit x its own branch multiplier x the row's timing factor (Status Effect Damage / KO
    engine).  Each branch gets its own full (1+damage%/100)*target_count treatment; the two are blended into the real Total DPS by the
    time weight w (see branch_blend) - Sensitivity's marginal-value ranking uses a separate ratio-based blend.  PvP is single-enemy with
    neither bonus."""
    fb, fn = timing_factors(key)
    if monster_type == "pvp":
        b, n = 1.0, 1.0
    else:
        b = 1 + (boss_damage + mastery_boss + monster_dmg_bonus) / 100
        n = (1 + (normal_damage + mastery_normal + monster_dmg_bonus) / 100) * min(targets, max_enemies_hit)
    pair = (rate_boss * hd_ * b * fb, rate_normal * hd_ * n * fn)
    _BRANCH_PAIRS[key] = pair
    return pair


def monster_blend(boss_val, normal_val):
    if monster_type == "pvp":
        return boss_val
    return (1 - normal_weight) * boss_val + normal_weight * normal_val


# ---- Helper rows (Advanced Final Attack, Enchanted Quiver, Maple Hero, Flash Mirage II) — own
#      D/E/F only, no independent DPS of their own; feed another row's coefficient/extra-FD term.
#      Final Attack: Bow used to be one of these (folded into Arrow Stream's own coefficient) but
#      is now its own independent DAMAGE_SKILLS entry below, since it's affected by Skill Damage%,
#      not Basic Attack Damage% (Arrow Stream's own bucket) — split out per a Discord bug report.
final_attack_bow_pct = (
    coeff_pct(350, 21, True, 2) * (1 + level_gated_sum({54: 50}) / 100)
    if unlocked("FINAL_ATTACK_BOW") else 0.0
)
advanced_final_attack_pct = (
    coeff_pct(5000, 21, True, 4) + level_gated_sum({113: 50})
    if unlocked("ADVANCED_FINAL_ATTACK_HELPER") else 0.0
)
enchanted_quiver_pct = coeff_pct(3000, 21, True, 4) if unlocked("ENCHANTED_QUIVER_HELPER") else 0.0
maple_hero_pct = coeff_pct(250, 23, True, 4) if unlocked("MAPLE_HERO_HELPER") else 0.0
flash_mirage_ii_pct = coeff_pct(4000, 21, True, 4) if unlocked("FLASH_MIRAGE_II_HELPER") else 0.0

# ---- Attack% bucket: Marksmanship (base + conditional) + Illusion Step, summed additively ----
marksmanship_base_pct = coeff_pct(100, 22, True, 3) if unlocked("MARKSMANSHIP_BASE") else 0.0
marksmanship_cond_pct_raw = coeff_pct(100, 22, True, 3) if unlocked("MARKSMANSHIP_COND") else 0.0
marksmanship_cond_avg = monster_blend(marksmanship_cond_pct_raw, 0.0) if unlocked("MARKSMANSHIP_COND") else 0.0
illusion_step_pct = (
    coeff_pct(140, 22, True, 4) + (0.375 * coeff_pct(140, 22, True, 4) if level >= 118 else 0.0)
) if unlocked("ILLUSION_STEP") else 0.0
illusion_step_avg = buff_avg(illusion_step_pct, 24 if level >= 118 else 15, 24, False) if unlocked("ILLUSION_STEP") else 0.0

attack_bucket_mult = 1 + (marksmanship_base_pct + marksmanship_cond_avg + illusion_step_avg) / 100

# ---- Sharp Eyes (self-inclusive ally buff: flat 20 Crit Rate + scaling Crit Damage) ----
sharp_eyes_crit_damage_pct = coeff_pct(400, 21, True, 4) if unlocked("SHARP_EYES") else 0.0
sharp_eyes_uptime = (
    buff_avg(1.0, 27 if level >= 126 else 18, 35, True) if unlocked("SHARP_EYES") else 0.0
)  # buff_avg(1,...) returns the uptime fraction itself
crit_rate_bonus = 0.0  # Sharp Eyes has no Crit Rate component (audit 2026-10-21)
sharp_eyes_crit_damage_avg = sharp_eyes_crit_damage_pct * sharp_eyes_uptime if unlocked("SHARP_EYES") else 0.0

# ---- Concentration (steady-state max stacks, 10 x 3% = 30% Crit Damage) ----
concentration_crit_damage = (7 * coeff_pct(30, 22, True, 3)) if unlocked("CONCENTRATION") else 0.0
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

# ---------------------------------------------------------------------------------------------------------------
# Status Effect Damage / KO timeline engine (src/status_timeline.py `solve`, the plain-Python reference): fixed-length single-target content with
# KO phases (World Boss, Enhancement Dungeon) or a companion that stuns/freezes.  The player casts Illusion Step and the cooldown skills when they
# pay most (Sharp Eyes / Nimble Feet / Concentration / Mortal Blow keep their averaged formulas).
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
# The player's own stunning skills (game table): Covering Fire stuns for 1 s (cooldown 19 s), from the Lv49 mastery on; cast on cooldown from the start
PLAYER_STUN = [dict(id="COVER", key="COVERING_FIRE", typ="cast", dur=1.0, p=1.0, cd=19, min_level=49)]
_pl_on = any(unlocked(e["key"]) and level >= e["min_level"] for e in PLAYER_STUN)
_stun_in0 = _companion_choice0 != "None" and c_level0 >= 1
# The workbook's effective Companion Summoning Time Increase is the Inputs value + Arwen's Glass Shoes (+20% star 0 .. +40% star 5, Artifacts row
# arwens_glass_shoes_summon_time_increase_pct).  The verify run clears the artifact slots, so the artifact term is 0 in every cpm.run below; it is
# covered by the equivalence test (artifact at Inputs x == no artifact at Inputs x + star value).
hasstun = (_stun_in0 and bool(cpm.run(_stub, _companion_choice0, c_level0, _in("companion_summon_time_increase_pct")).get("hasstun"))) or _pl_on
KO_WINDOWS = {"World Boss": [(24, 34), (59, 69)], "Enhancement Dungeon": [(fight_duration - 4.5, fight_duration)]}
status_on = fixed_duration_active and normal_weight == 0 and (content_type in KO_WINDOWS or hasstun)
# the stun skills' first cast: t=0 with the engine on, otherwise after the buff-casting startup (Sharp Eyes + Nimble Feet), like Summary's startup cell
_startup_plain = (sum(1 for k in ("SHARP_EYES", "NIMBLE_FEET") if unlocked(k)) / actions_per_second) if fixed_duration_active else 0.0
_t0_pl = 0.0 if status_on else _startup_plain
PST = [dict(id=e["id"], typ=e["typ"], cd=eff_cooldown(e["cd"], True), dur=e["dur"], p=e["p"], on=unlocked(e["key"]) and level >= e["min_level"],
            t0=_t0_pl, tick=1.0, win=0.0) for e in PLAYER_STUN]
_stub["pst"] = PST
stun_info = cpm.run(_stub, _companion_choice0 if _stun_in0 else "None", c_level0, _in("companion_summon_time_increase_pct"))
stf_b = stun_info["stunfracB"]
stf_n = stun_info["stunfracN"]
E_ENGINE = None
ENGINE_N = {}
attack_bucket_sum = marksmanship_base_pct + marksmanship_cond_avg + illusion_step_avg   # the averaged Attack% bucket (without artifacts)
if status_on:
    _stun_vec = [min(1.0, a + b) for a, b in zip(stun_info["stun_vector"](stl.NB_MAX), stl.pl_stun_vector([dict(e, t0=0.0) for e in PST], fight_duration, stl.NB_MAX))]
    _is_dur, _is_cd = eff_duration(24 if level >= 118 else 15), eff_cooldown(24, False)
    _buffs = [dict(id="IS", kind="atk", F=illusion_step_pct, dur=_is_dur, cd=_is_cd, on=unlocked("ILLUSION_STEP"))]
    _eng_host = dict(T=fight_duration, S=status_effect_damage, ko=KO_WINDOWS.get(content_type, []), hex_v=0.0, hex_period=20, hex_max=3,
                     A0=marksmanship_base_pct + marksmanship_cond_avg, charm_v=0.0, hex_avg=0.0, c_slot=0.0, stun=_stun_vec, buffs=_buffs, groups=[])
    _e1 = stl.solve(_eng_host)               # pass 1: the buff schedule (independent of the skill weights)
    attack_bucket_mult = _e1["Bbuff_mean"]
    ENGINE_N["ILLUSION_STEP"] = _e1["buffs"]["IS"]["n"]
    # Excel's attack_bucket_avg for the companion snapshot: F x exact-uptime formula at the engine's cast count
    if unlocked("ILLUSION_STEP"):
        _n = ENGINE_N["ILLUSION_STEP"]
        _up = ((_n - 1) * min(_is_dur, _is_cd) + min(_is_dur, max(0.0, fight_duration - (_n - 1) * _is_cd))) / fight_duration
        attack_bucket_sum = marksmanship_base_pct + marksmanship_cond_avg + illusion_step_pct * _up

# Buff-Casting Startup Delay: in fixed-duration fights, the character casts every currently-
# unlocked, actively-cast buff sequentially at fight start (1/APS seconds each, same cadence as
# every other action-costing skill) before their first damage-skill cast — so damage skills'
# usable window is reduced by this amount. Buffs themselves (Sharp Eyes, Nimble Feet — Illusion
# Step doesn't cost an action to trigger, so it never counts) keep their own t=0 uptime math
# unchanged (they're what causes the delay, not affected further by it).
BUFF_ROWS_FOR_STARTUP = [("SHARP_EYES", True), ("NIMBLE_FEET", True)]
if fixed_duration_active and not status_on:
    buff_cast_startup_time = sum(1 for k, ca in BUFF_ROWS_FOR_STARTUP if ca and unlocked(k)) / actions_per_second
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


# Quiver Cartridge's own AS-scaled tick rate (English wiki wording: "up to 0.4 times based on
# Attack Speed"), same 150%-AS cap as actions_per_second above.
quiver_cartridge_cooldown = 1 - 0.4 * min(1.0, (actions_per_second - 1) / 1.5)

def hit_damage(coeff_pct_val, is_basic, maple_ratio=0.0, extra_fd_pct=0.0):
    base_damage = attack * (coeff_pct_val / 100)
    dmg_reduction = 5000 / (6000 + monster_defense * (1 - def_pen / 100))
    maple_mult = (1 + maple_ratio * maple_hero_pct / 100) if maple_ratio else 1.0
    extra_fd_mult = (1 + extra_fd_pct / 100)
    final_mult = (1 + (final_damage + mortal_blow_bonus) / 100) * maple_mult * extra_fd_mult
    source_pct = basic_attack_damage if is_basic else skill_damage
    # Boss/Normal Monster Damage% is deliberately NOT applied here — it's blended per-branch in
    # boss_normal_multiplier, applied by the caller.
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


# ---- Arrow Stream (basic attack) ----
arrow_stream_mastery_damage = level_gated_sum({102: 10, 106: 11, 116: 12, 120: 13, 128: 14, 132: 15})
arrow_stream_mastery_boss_damage = level_gated_sum({111: 10, 124: 10})
arrow_stream_pct = skill_coefficient_base * (1 + arrow_stream_mastery_damage / 100)
arrow_stream_targets = 6 + basic_attack_target_increase
arrow_stream_hit = hit_damage(arrow_stream_pct, True)
ARROW_STREAM_HITS = 6 if level >= 136 else 5

# ---- Damage skills ----
DAMAGE_SKILLS = {
    "COVERING_FIRE": dict(job_step=1, cooldown=19, hits=3, base=2500, fidx=12, scales=True,
                           mastery=level_gated_sum({39: 50}), mastery_boss=0, mastery_normal=0,
                           costs_action=True, targets=1, maple_ratio=MAPLE_HERO_RATIOS.get("COVERING_FIRE", 0)),
    "QUIVER_CARTRIDGE": dict(job_step=3, cooldown=quiver_cartridge_cooldown, hits=1, base=500, fidx=21,
                              scales=True, mastery=level_gated_sum({44: 50}), mastery_boss=0, mastery_normal=0,
                              costs_action=False, targets=(3 + (3 if level >= 107 else 0)),
                              extra_fd=enchanted_quiver_pct if unlocked("ENCHANTED_QUIVER_HELPER") else 0.0),
    "ENCHANTED_QUIVER_DRAIN": dict(job_step=4, cooldown=quiver_cartridge_cooldown, hits=1, base=10500, fidx=21,
                                    scales=True, mastery=0, mastery_boss=0, mastery_normal=0,
                                    costs_action=False, targets=(3 + (3 if level >= 107 else 0)),
                                    proc_chance=30),
    "PHOENIX": dict(job_step=3, cooldown=(60 * 0.6) if level >= 104 else 60,
                     hits=1,
                     icd=(3 * 0.7) if level >= 82 else 3, window=30,
                     base=6000, fidx=12, scales=True, mastery=0, mastery_boss=0,
                     mastery_normal=100 if level >= 94 else 0, costs_action=True,
                     targets=5 + (3 if level >= 78 else 0),
                     maple_ratio=MAPLE_HERO_RATIOS.get("PHOENIX", 0)),
    "ARROW_PLATTER": dict(job_step=3, cooldown=40, hits=1, icd=0.3, window=60, base=500, fidx=12,
                           scales=True, mastery=level_gated_sum({73: 50}), mastery_boss=0, mastery_normal=200,
                           costs_action=True, targets=(3 + (1 if level >= 98 else 0)),
                           maple_ratio=MAPLE_HERO_RATIOS.get("ARROW_PLATTER", 0)),
    "FLASH_MIRAGE": dict(job_step=3,
                          cooldown=(3 if level >= 122 else 5),   # the REAL internal cooldown only; the activation cycle is built per branch below
                          hits=1, base=5500, fidx=21, scales=True,
                          mastery=level_gated_sum({68: 50}), mastery_boss=0, mastery_normal=0,
                          costs_action=False,
                          targets=(7 + (4 if level >= 110 else 0) + (1 if level >= 138 else 0)),
                          proc_chance=100,
                          extra_fd=flash_mirage_ii_pct if unlocked("FLASH_MIRAGE_II_HELPER") else 0.0),
    "HURRICANE": dict(job_step=4, cooldown=40, hits=(20 + (15 if level >= 134 else 0)), base=8000,
                       fidx=12, scales=True, mastery=level_gated_sum({108: 50}), mastery_boss=0,
                       mastery_normal=0, costs_action=True, targets=11),
    "FINAL_ATTACK_BOW": dict(job_step=2, cooldown=None,   # no cooldown: chance per attack per enemy hit (see below)
                              hits=1, base=350, fidx=21, scales=True,
                              mastery=level_gated_sum({54: 50}), mastery_boss=0, mastery_normal=0,
                              costs_action=False, targets=1,
                              proc_chance=25,
                              extra_fd=advanced_final_attack_pct if unlocked("ADVANCED_FINAL_ATTACK_HELPER") else 0.0),
}
NORMAL_MONSTER_TARGETS = {k: v["targets"] for k, v in DAMAGE_SKILLS.items()}


# ---- Status/KO engine pass 2: the skills' casts.  Weight of one cast = its boss damage before any timing factor (hits x expected hit x boss multiplier).
PHI_ROWS = {}
PHI_UNIF = 1.0
E_FS = {}
if status_on:
    def _percast(key):
        if not unlocked(key):
            return 0.0
        sk = DAMAGE_SKILLS[key]
        pct = coeff_pct(sk["base"], sk["fidx"], sk["scales"], sk["job_step"]) * (1 + sk.get("mastery", 0) / 100) + sk.get("fold", 0)
        hd = hit_damage(pct, False, maple_ratio=sk.get("maple_ratio", 0.0), extra_fd_pct=sk.get("extra_fd", 0.0))
        hits = sk["hits"] * (ticks(capped_window(sk["window"]), sk["icd"]) if sk.get("icd") else 1)
        b_mult = 1.0 if monster_type == "pvp" else 1 + (boss_damage + sk.get("mastery_boss", 0) + monster_dmg_bonus) / 100
        return sk.get("proc_chance", 100) / 100 * hits * hd * b_mult
    _c_slot = (ARROW_STREAM_HITS * arrow_stream_hit
               * (1.0 if monster_type == "pvp" else 1 + (boss_damage + arrow_stream_mastery_boss_damage + monster_dmg_bonus) / 100))
    _groups = []
    for _gid, _cast, _ents in STATUS_GROUPS:
        _entries = []
        for _row, _typ, _win, _gate, _wk in _ents:
            _w = _percast(_wk)
            if _gate and not unlocked(_gate):
                _w = 0.0
            _entries.append(dict(row=_row, typ=_typ, w=_w, L=(capped_window(DAMAGE_SKILLS[_win]["window"]) if _win else 1),
                                 on=(1 if (not _gate or unlocked(_gate)) else 0)))
        _groups.append(dict(id=_gid, cd=eff_cooldown(DAMAGE_SKILLS[_cast]["cooldown"], DAMAGE_SKILLS[_cast]["costs_action"], exempt=_cast in CDR_EXEMPT),
                            on=unlocked(_cast), slot=True, entries=_entries,
                            fixed=_cast in {e["key"] for e in PLAYER_STUN}, t0=0.0))
    E_ENGINE = stl.solve(dict(_eng_host, groups=_groups, c_slot=_c_slot))
    for _row, _pfx in STATUS_CAST_PREFIX.items():
        if _pfx.startswith("grp."):
            ENGINE_N[_row] = E_ENGINE["groups"][_pfx[4:]]["n"]
    PHI_ROWS = E_ENGINE["rows"]
    PHI_UNIF = E_ENGINE["phi_unif"]
    E_FS = E_ENGINE["fs"]
    print(f"Status/KO engine ON: casts {{ {', '.join(f'{k}: {v}' for k, v in ENGINE_N.items())} }}, phi_unif {PHI_UNIF:.4f}")


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


# ---- Cast rate (subtracted from Arrow Stream) ----
BUFF_KEYS_STARTUP = {"SHARP_EYES", "NIMBLE_FEET"}
COST_ACTION_ROWS = [
    ("COVERING_FIRE", 19, True, 1),
    ("PHOENIX", (60 * 0.6) if level >= 104 else 60, True, 1),
    ("ARROW_PLATTER", 40, True, 1),
    ("HURRICANE", 40, True, 1),
    ("SHARP_EYES", 35, True, 1),
    ("NIMBLE_FEET", 60, True, 1),
]
if fixed_duration_active:
    cast_rate = sum(
        (ENGINE_N[k] if k in ENGINE_N else exact_casts(eff_cooldown(cd, ca)) if k in BUFF_KEYS_STARTUP else non_buff_casts(eff_cooldown(cd, ca))) * aps
        for k, cd, ca, aps in COST_ACTION_ROWS if ca and unlocked(k)
    ) / fight_duration
else:
    cast_rate = sum((1 / eff_cooldown(cd, ca)) * aps for k, cd, ca, aps in COST_ACTION_ROWS if ca and unlocked(k))
arrow_stream_per_second = max(0, actions_per_second - cast_rate)


arrow_stream_rate_pair = branch_pair(
    "ARROW_STREAM", arrow_stream_per_second, arrow_stream_per_second, ARROW_STREAM_HITS * arrow_stream_hit,
    arrow_stream_mastery_boss_damage, 0, arrow_stream_targets)
if not unlocked("ARROW_STREAM"):
    _BRANCH_PAIRS["ARROW_STREAM"] = (0.0, 0.0)
arrow_stream_dps = (1 - normal_weight) * _BRANCH_PAIRS["ARROW_STREAM"][0] + normal_weight * _BRANCH_PAIRS["ARROW_STREAM"][1]

# ---- PROC RULE (user, 2026-11-04): a chance proc rolls once per ATTACK per ENEMY HIT, never per damage line.
#      Arrow Stream's 5-6 lines = 1 attack; every Hurricane arrow is its own attack. Trigger set = Arrow Stream casts +
#      every action-costing damage skill's casts (buff casts are not attacks). Covering Fire's 3 hits = 1 attack (flagged).
TRIGGER_CAST_ROWS = ["COVERING_FIRE", "PHOENIX", "ARROW_PLATTER", "HURRICANE"]
ATTACKS_PER_CAST = {k: 1 for k in TRIGGER_CAST_ROWS}
ATTACKS_PER_CAST["HURRICANE"] = DAMAGE_SKILLS["HURRICANE"]["hits"]   # each arrow is its own attack
trigger_attacks = []     # (attacks per second, enemies hit per attack in the normal branch)
if unlocked("ARROW_STREAM"):
    trigger_attacks.append((arrow_stream_per_second, min(arrow_stream_targets, max_enemies_hit)))
for k in TRIGGER_CAST_ROWS:
    if not unlocked(k):
        continue
    s_ = DAMAGE_SKILLS[k]
    cd_ = eff_cooldown(s_["cooldown"], s_["costs_action"])
    casts_per_sec = ((ENGINE_N[k] if k in ENGINE_N else non_buff_casts(cd_)) / fight_duration) if fixed_duration_active else (1 / cd_)
    trigger_attacks.append((casts_per_sec * ATTACKS_PER_CAST[k], min(s_["targets"], max_enemies_hit)))
trig_attacks_total = sum(a for a, n in trigger_attacks)
trig_enemy_rolls = sum(a * n for a, n in trigger_attacks)
fm_chance = (20 + 30 * (actions_per_second - 1) * 100 / 150) / 100
fm_x_boss = fm_chance * trig_attacks_total
fm_x_normal = sum(a * (1 - (1 - fm_chance) ** n) for a, n in trigger_attacks)
print(f"Proc triggers: attacks/s = {trig_attacks_total:.6f}, attacks/s x enemies = {trig_enemy_rolls:.6f}, "
      f"FM chance = {fm_chance:.6f}, FM X boss/normal = {fm_x_boss:.6f} / {fm_x_normal:.6f}")


def branch_blend(key, rate_boss, rate_normal, hd_, mastery_boss, mastery_normal, targets):
    """skill_dps = (1-w)*rate_b*hd*bossbranch + w*rate_n*hd*normalbranch (each x the row's timing factor); PvP is single-enemy with neither bonus."""
    pb, pn = branch_pair(key, rate_boss, rate_normal, hd_, mastery_boss, mastery_normal, targets)
    return (1 - normal_weight) * pb + normal_weight * pn


def flash_mirage_rate(x):
    icd = DAMAGE_SKILLS["FLASH_MIRAGE"]["cooldown"]   # real ICD: Skill Cooldown Decrease does not apply (user, 2026-11-04)
    if x <= 0:
        return 0.0
    cycle = icd + 1 / x
    if fixed_duration_active:
        avail = max(0.0, fight_duration - buff_cast_startup_time)
        casts = 0 if avail <= 0 else math.floor(avail / cycle) + 1
        return casts / fight_duration
    return 1 / cycle


skill_dps = {}
for key, s in DAMAGE_SKILLS.items():
    if not unlocked(key):
        skill_dps[key] = 0.0
        _BRANCH_PAIRS[key] = (0.0, 0.0)
        continue
    pct = coeff_pct(s["base"], s["fidx"], s["scales"], s["job_step"]) * (1 + s.get("mastery", 0) / 100) + s.get("fold", 0)  # a skill mastery MULTIPLIES the skill's damage (game-confirmed 2026-11-03); fold-ins stay additive
    hd = hit_damage(
        pct, False,
        maple_ratio=s.get("maple_ratio", 0.0), extra_fd_pct=s.get("extra_fd", 0.0),
    )
    proc_prob = 1 - (1 - s.get("proc_chance", 100) / 100) ** 1
    if key == "FINAL_ATTACK_BOW":
        # no ICD: expected procs per attack = c (one enemy) or c x N (every enemy hit rolls); each proc hits only the enemy it rolled for
        skill_dps[key] = branch_blend(key, proc_prob * trig_attacks_total, proc_prob * trig_enemy_rolls, hd, 0, 0, 1)
        continue
    if key == "FLASH_MIRAGE":
        skill_dps[key] = branch_blend(
            key, s["hits"] * flash_mirage_rate(fm_x_boss), s["hits"] * flash_mirage_rate(fm_x_normal), hd * proc_prob, 0, 0, s["targets"])
        continue
    eff_cd = eff_cooldown(s["cooldown"], s["costs_action"], exempt=key in CDR_EXEMPT)
    if status_on and key in ENGINE_N:
        # engine casts: a summon / DoT row's hits = hits per full window x effective casts (last window truncated at the fight end)
        _per_cast = s["hits"] * (ticks(capped_window(s["window"]), s["icd"]) if s.get("icd") else 1)
        rate = _per_cast * (E_FS[key] if key in STATUS_FS_KEYS else ENGINE_N[key]) / fight_duration
    elif fixed_duration_active:
        rate = non_buff_total_hits(eff_cd, s["hits"], s.get("icd"), s.get("window")) / fight_duration
    else:
        hits = s["hits"] * (ticks(capped_window(s["window"]), s["icd"]) if s.get("icd") else 1)
        rate = hits / eff_cd
    skill_dps[key] = branch_blend(key, rate, rate, hd * proc_prob, s.get("mastery_boss", 0), s.get("mastery_normal", 0), s["targets"])

total_dps = arrow_stream_dps + sum(skill_dps.values())

# ---------------------------------------------------------------------------------------------------------------
# Companion: plain-Python port (src/companion_python_model.py) of src/companion_model.py's rules, fed with this script's own
# numbers for the player's pipeline.  The verify run clears the artifact slots, so the artifact snapshot terms (Hexagon, Charm,
# Chalice) are zero here; they are covered by the dedicated hand checks instead.
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
    pb_total = sum(p[0] for p in _BRANCH_PAIRS.values())
    pn_total = sum(p[1] for p in _BRANCH_PAIRS.values())
    pu_total = sum(_BRANCH_PAIRS[k][0] for k in STATUS_UNIFORM_ROWS)
    basic_b, basic_n = _BRANCH_PAIRS["ARROW_STREAM"]
    boss_pct_c = boss_damage + monster_dmg_bonus
    norm_pct_c = normal_damage + monster_dmg_bonus
    comp_host = dict(
        mt=monster_type, T=fight_duration, content=content_type, pvp_len=PVP_FIGHT_DURATION, cap=max_enemies_hit, w=normal_weight,
        unit=hit_damage(100.0, True) / 100,
        bad=basic_attack_damage, sd=skill_damage, aps=actions_per_second,
        avgbuff=attack_bucket_mult, attack_bucket_avg=attack_bucket_sum,
        charm_val=0.0, agg_damage_avg=0.0, hex_avg=0.0, hex_snap=lambda st: 0.0,
        avgbuff_snap=lambda charm, extra: 1 + (marksmanship_base_pct + marksmanship_cond_avg + illusion_step_pct + charm + extra) / 100,
        agg_fd_boss_only=0.0, agg_fd_norm_only=0.0, chalice_avg_boss=0.0, chalice_avg_norm=0.0, chalice_full=0.0, horn_avg=0.0, horn_full=0.0,
        boss_pct=boss_pct_c, norm_pct=norm_pct_c, extra_boss=1.0, extra_norm=1.0,
        player_boss=pb_total, player_norm=pn_total,
        player_uniform_boss=pu_total, player_basic_boss=basic_b, player_basic_norm=basic_n,
        cr_total=crit_rate + crit_rate_bonus, cd_total=crit_damage + crit_damage_bonus, min_dmg=min_damage, max_dmg=max_damage,
        defense=monster_defense, def_pen=def_pen,
        taken_bucket=0.0 if monster_type == "pvp" else (1 - normal_weight) * boss_pct_c + normal_weight * norm_pct_c,
        pst=PST,
        st=dict(on=status_on, S=status_effect_damage,
                mult=(list(E_ENGINE["mult"]) + [1.0] * (stl.NB_MAX - E_ENGINE["nb"])) if status_on else None,
                act=(list(E_ENGINE["act"]) + [0.0] * (stl.NB_MAX - E_ENGINE["nb"])) if status_on else None),
    )
    companion_result = cpm.run(comp_host, companion_choice if (companion_choice != "None" and c_level >= 1) else "None", c_level,
                               _in("companion_summon_time_increase_pct"))
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
        _r = cpm.run(_hb, _name, 10, _in("companion_summon_time_increase_pct"))
        print(f"  [compare Lv10] {_name:14s} blend DPS {_r['comp_blend_dps']:.4e}  = +{_r['comp_blend_dps'] / _base * 100:6.2f}% of player total (s={_r['s']:.1f}, W={_r['W']:.1f})")
total_dps += companion_dps

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
