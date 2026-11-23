#!/usr/bin/env python3
"""
Cross-checks Buccaneer-DPS-Calculator.xlsx against an independent Python port of the same logic,
using the workbook's own default Inputs values. Then loads the live workbook with the `formulas`
package and diffs Total DPS + every per-skill DPS cell (Calc!O<row>) against this script's
independent numbers. Mirrors verify_hero_workbook.py in structure and method.

Also mirrors the Status Effect Damage / KO timeline engine (src/status_timeline.py `solve`) and the Companion model (src/companion_python_model.py).
Artifacts are not modelled here: run it on a copy with the artifact slots cleared (data/porting/helpers/sv.py does that).
"""
import json
import math
import os
import re
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
XLSX_PATH = REPO / "Buccaneer" / "Buccaneer-DPS-Calculator.xlsx"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_buccaneer_workbook import ROW, IN, UNLOCK_LEVEL, MAPLE_HERO_RATIOS, R_TOTAL  # noqa: E402
from build_buccaneer_workbook import STATUS_CAST_PREFIX, STATUS_GROUPS, STATUS_BUFFS, STATUS_UNIFORM_ROWS, STATUS_PHI_ROWS, STATUS_FS_KEYS, STATUS_MAIN_LAYOUT  # noqa: E402
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
from build_buccaneer_workbook import CONTENT_TYPES  # noqa: E402

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
flat_str, str_pct, dex_stat = _in("flat_str"), _in("str_pct"), _in("dex")
stat_damage = (flat_str * (1 + str_pct / 100)) * 0.01 + dex_stat * 0.0025
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



# ---- live workbook access (the `formulas` evaluation is loaded lazily: the companion mirror needs a few cells of the strip) ----
import formulas  # noqa: E402

_SOLUTION = []


def _get_solution():
    if not _SOLUTION:
        print(f"Loading live workbook: {XLSX_PATH}")
        _SOLUTION.append(formulas.ExcelModel().loads(str(XLSX_PATH)).finish().calculate())
    return _SOLUTION[0]


def scalar(value):
    return float(np.asarray(value).reshape(-1)[0])


def read_cell(sheet, cell):
    suffix = f"{sheet.upper()}'!{cell.upper()}"
    for k, v in _get_solution().items():
        if k.upper().endswith(suffix):
            return scalar(v.value)
    raise KeyError(f"cell not found in workbook: {sheet}!{cell}")


# Buff-casting startup delay (set below once the Actions Per Second and the engine state are known; 0 when the Status/KO engine is on)
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
        uptime = min(1.0, eff_duration(duration) / eff_cd)
    return pct * uptime


_BRANCH_PAIRS = {}   # key -> (boss DPS, normal DPS) of the row (incl. the timing factors); filled by blend_branches / the Nautilus proc


def branch_multipliers(targets, mastery_boss=0, mastery_normal=0):
    """(boss_branch, normal_branch) damage multipliers; PvP is single-enemy with neither bonus."""
    if monster_type == "pvp":
        return 1.0, 1.0
    t = min(targets, max_enemies_hit)
    return 1 + (boss_damage + mastery_boss + monster_dmg_bonus) / 100, (1 + (normal_damage + mastery_normal + monster_dmg_bonus) / 100) * t


def blend_branches(key, unit, targets, mastery_boss=0, mastery_normal=0):
    """Time-weighted DPS of one row: (1-w)*unit*boss_branch*timing_boss + w*unit*normal_branch*timing_normal.  Correct for the real Total DPS; Sensitivity's
    marginal-value ranking uses a separate, ratio-based blend instead (see build_sensitivity_sheet)."""
    b, n = branch_multipliers(targets, mastery_boss, mastery_normal)
    fb, fn = timing_factors(key)
    _BRANCH_PAIRS[key] = (unit * b * fb, unit * n * fn)
    return (1 - normal_weight) * unit * b * fb + normal_weight * unit * n * fn


def roll_prob(chance, targets):
    """P(at least one success) over the per-enemy chance rolls of ONE attack hitting N = min(targets, max_enemies) enemies."""
    return 1 - (1 - chance) ** min(targets, max_enemies_hit)


def coeff_pct(base, fidx, scales, job_step):
    lvl = input_level(job_step, level, skill1, skill2, skill3, skill4, skill_all)
    if not scales:
        return base / 10
    return (base / 10) * (get_factor(lvl, fidx) / 1000)


# ---- Maple Hero (Serpent Assault / Corkscrew Blow: see the build script) ----
maple_hero_pct = coeff_pct(600, 23, True, 4) if unlocked("MAPLE_HERO_HELPER") else 0.0

hook_bomber_targets = 6 + basic_attack_target_increase
HOOK_BOMBER_HITS = 6 if level >= 136 else 5
hook_bomber_mastery_damage = level_gated_sum({102: 10, 106: 11, 116: 12, 120: 13, 128: 14, 132: 15})
hook_bomber_mastery_boss_damage = level_gated_sum({111: 10, 124: 10})
hook_bomber_pct = skill_coefficient_base * (1 + hook_bomber_mastery_damage / 100)


def exact_buff_uptime(cooldown, buff_duration):
    casts = exact_casts(cooldown)
    remaining_after_last = max(0.0, fight_duration - (casts - 1) * cooldown)
    last_uptime = min(buff_duration, remaining_after_last)
    return (casts - 1) * min(buff_duration, cooldown) + last_uptime


def exact_uptime_at(n, cooldown, buff_duration):
    """The workbook's exact-uptime formula (exact_buff_uptime_expr) at a GIVEN cast count n: (n-1)*MIN(dur, cd) + MIN(dur, remaining after the last cast)."""
    remaining_after_last = max(0.0, fight_duration - (n - 1) * cooldown)
    return ((n - 1) * min(buff_duration, cooldown) + min(buff_duration, remaining_after_last)) / fight_duration


def duty_cycle_uptime(cooldown, duration):
    """Exact/fixed-duration-aware uptime fraction for a real cooldown-gated buff — shared by
    Nimble Feet/Crossbones/Time Leap/Speed Infusion (all real Type=Active casts confirmed via maplestoryidle.info)."""
    eff_cd = eff_cooldown(cooldown, True)
    if fixed_duration_active:
        return exact_buff_uptime(eff_cd, eff_duration(duration)) / fight_duration
    elif monster_type == "pvp":
        return min(eff_duration(duration), PVP_FIGHT_DURATION) / PVP_FIGHT_DURATION
    return min(1.0, eff_duration(duration) / eff_cd)


def _nimble_feet_as_avg():
    """Nimble Feet's own duty-cycle-averaged Attack Speed% — independent of actions_per_second
    (fixed 60s cooldown/15s duration, not AS-scaled), so no circularity computing this first."""
    if not unlocked("NIMBLE_FEET"):
        return 0.0
    pct = coeff_pct(150, 0, False, 1)
    return pct * duty_cycle_uptime(60, 15)


speed_infusion_pct = coeff_pct(200, 21, True, 4) if unlocked("SPEED_INFUSION") else 0.0


def _speed_infusion_as_avg():
    """Speed Infusion's duty-cycle-averaged Attack Speed% (real action-costing buff, 35s cd / 15s)."""
    return speed_infusion_pct * duty_cycle_uptime(35, 15) if unlocked("SPEED_INFUSION") else 0.0


def _aps_with_extra_as(as_extra):
    return 1 + min(150, 150 * (1 - (1 - attack_speed_base / 150) * (1 - as_extra / 150))) / 100


# Actions Per Second combines raw Inputs!attack_speed with the duty-cycle-averaged AS buffs (Nimble Feet + Speed Infusion) via the standard
# diminishing-returns stack (factor 150).  Neither is an engine buff (Attack Speed buffs the engine does not time).
actions_per_second = _aps_with_extra_as(_nimble_feet_as_avg() + _speed_infusion_as_avg())

# ---------------------------------------------------------------------------------------------------------------
# Status Effect Damage / KO timeline engine (src/status_timeline.py `solve`, the plain-Python reference): fixed-length single-target content with
# KO phases (World Boss, Enhancement Dungeon) or a stunning/freezing source (the companion's stuns, the player's own Corkscrew Blow).  The player casts the
# engine buffs (Crossbones, Time Leap: Final Damage) and the cooldown skills when they pay most.
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
# The player's own stunning skills (game table): Corkscrew Blow stuns for 1.8 s (cooldown 21 s), cast on cooldown from the start
CORKSCREW_COOLDOWN = 21
PLAYER_STUN = [dict(id="CORK", key="CORKSCREW_BLOW", typ="cast", dur=1.8, p=1.0, cd=CORKSCREW_COOLDOWN)]
_pl_on = any(unlocked(e["key"]) for e in PLAYER_STUN)
# The workbook's effective Companion Summoning Time Increase is the Inputs value + Arwen's Glass Shoes (+20% star 0 .. +40% star 5, Artifacts row
# arwens_glass_shoes_summon_time_increase_pct).  The verify run clears the artifact slots, so the artifact term is 0 here (all three cpm.run calls read
# the plain Inputs value); it is covered by the equivalence test (artifact at Inputs x == no artifact at Inputs x + star value,
# tests/golden/buccaneer_artifact_cases.py EQUIV_PAIRS).
stun_info = (cpm.run(_stub, _companion_choice0, c_level0, _in("companion_summon_time_increase_pct"))
             if (_companion_choice0 != "None" and c_level0 >= 1) else None)
hasstun = bool(stun_info and stun_info.get("hasstun")) or _pl_on
KO_WINDOWS = {"World Boss": [(24, 34), (59, 69)], "Enhancement Dungeon": [(fight_duration - 4.5, fight_duration)]}
status_on = fixed_duration_active and normal_weight == 0 and (content_type in KO_WINDOWS or hasstun)

# Buff-Casting Startup Delay: in fixed-duration fights, the character casts every currently-unlocked, actively-cast buff sequentially at fight start (1/APS seconds
# each) before their first damage-skill cast - the workbook's Summary!R_STARTUP_TIME (0 when the engine is on: buffs are cast when they pay).
if fixed_duration_active and not status_on:
    buff_cast_startup_time = (
        (1 if unlocked("NIMBLE_FEET") else 0)
        + (1 if unlocked("CROSSBONES_FD") else 0)
        + (1 if unlocked("TIME_LEAP_FD") else 0)
        + (1 if unlocked("SPEED_INFUSION") else 0)
    ) / actions_per_second
else:
    buff_cast_startup_time = 0.0
_t0_pl = 0.0 if status_on else buff_cast_startup_time
PST = [dict(id=e["id"], typ=e["typ"], cd=eff_cooldown(e["cd"], True), dur=e["dur"],
            p=e["p"], on=unlocked(e["key"]), t0=_t0_pl, tick=1.0, win=0.0) for e in PLAYER_STUN]
_stub["pst"] = PST
stun_info = cpm.run(_stub, _companion_choice0 if (_companion_choice0 != "None" and c_level0 >= 1) else "None", c_level0, _in("companion_summon_time_increase_pct"))
stf_b = stun_info["stunfracB"]
stf_n = stun_info["stunfracN"]
_stun_vec = None
if status_on:
    _stun_vec = [min(1.0, a + b) for a, b in zip(stun_info["stun_vector"](stl.NB_MAX), stl.pl_stun_vector([dict(e, t0=0.0) for e in PST], fight_duration, stl.NB_MAX))]

# ---- Cast rate (subtracted from Hook Bomber) — action-costing skills and buffs ----
OCTOPUNCH_COOLDOWN = (16 * 0.7) if level >= 134 else 16
SKILL_CAST_ROWS = [("CORKSCREW_BLOW", CORKSCREW_COOLDOWN), ("OCTOPUNCH", OCTOPUNCH_COOLDOWN), ("NAUTILUS_STRIKE", 33)]
BUFF_CAST_ROWS = [("NIMBLE_FEET", 60), ("CROSSBONES_FD", 28), ("TIME_LEAP_FD", 65), ("SPEED_INFUSION", 35)]


def cast_rate_with(counts):
    """Skill + buff cast rate; `counts` maps row key -> engine cast count (the engine's schedule), other rows use the averaged formulas."""
    if fixed_duration_active:
        tot = 0.0
        for k, cd in SKILL_CAST_ROWS:
            if unlocked(k):
                tot += counts[k] if k in counts else non_buff_casts(eff_cooldown(cd, True))
        for k, cd in BUFF_CAST_ROWS:
            if unlocked(k):
                tot += counts[k] if k in counts else exact_casts(eff_cooldown(cd, True))
        return tot / fight_duration
    return sum(1 / eff_cooldown(cd, True) for k, cd in SKILL_CAST_ROWS + BUFF_CAST_ROWS if unlocked(k))


# The AVERAGED model's cast rate / Hook Bomber rate (pre-engine cast counts = Calc!Z): the Assault Mode interval and uptime read this one (no dependence on the engine's casts).
cast_rate_avg = cast_rate_with({})
hook_bomber_per_second_avg = max(0, actions_per_second - cast_rate_avg)

# ---- Assault Mode economy: activations every T = SSB cooldown + half a basic-attack period ----
ssb_cooldown = 7 - (2 if level >= 78 else 0) - (2 if level >= 118 else 0)
serpent_T = eff_cooldown(ssb_cooldown, True) + (0.5 / hook_bomber_per_second_avg if hook_bomber_per_second_avg > 0 else 0.0)


def assault_duration():
    return 10 + (5 if level >= 94 else 0)


activations_to_assault = 3 if level >= 104 else 5
uptime = (
    assault_duration() / (assault_duration() + activations_to_assault * serpent_T)
    if unlocked("SERPENT_SCALE_FD") else 0.0
)

# ---- Global Final Damage bucket: Serpent Scale (Assault-Mode-gated) + Crossbones + Time Leap + Speed Infusion (live AS-linked formula) ----
serpent_scale_pct = coeff_pct(250, 21, True, 3) if unlocked("SERPENT_SCALE_FD") else 0.0
# +25% FD while in Assault Mode (uptime u) + average 2 held scales x 2% = 4% while rebuilding (1-u)
serpent_scale_avg = (serpent_scale_pct * uptime + 4 * (1 - uptime)) if unlocked("SERPENT_SCALE_FD") else 0.0
crossbones_full = coeff_pct(100, 21, True, 4) if unlocked("CROSSBONES_FD") else 0.0
time_leap_full = (coeff_pct(150, 21, True, 4) + level_gated_sum({138: 10})) if unlocked("TIME_LEAP_FD") else 0.0
# Speed Infusion FD = 20% of Attack Speed WHILE the buff is up (APS incl. its own +AS), over its uptime.
speed_infusion_full = 20 * (_aps_with_extra_as(_nimble_feet_as_avg() + speed_infusion_pct) - 1) if unlocked("SPEED_INFUSION") else 0.0
speed_infusion_avg = speed_infusion_full * duty_cycle_uptime(35, 15) if unlocked("SPEED_INFUSION") else 0.0
final_damage_rest = serpent_scale_avg + speed_infusion_avg                     # the Final Damage the engine does not time
crossbones_pct = crossbones_full * duty_cycle_uptime(28, 12) if unlocked("CROSSBONES_FD") else 0.0
time_leap_pct = time_leap_full * duty_cycle_uptime(65, 40) if unlocked("TIME_LEAP_FD") else 0.0
final_damage_extra = final_damage_rest + crossbones_pct + time_leap_pct        # averaged model (engine off)

# ---- Attack% bucket: Roll of the Dice's dice component only (real 5s/7s duty cycle) ----
roll_of_dice_pct = coeff_pct(25, 22, True, 3) * 5 / 7 if unlocked("ROLL_OF_THE_DICE_DICE") else 0.0
attack_bucket_mult = 1 + roll_of_dice_pct / 100

crit_rate_bonus = 0.0
crit_damage_bonus = 0.0
# Sea Serpent's Rage Assault Mark: +15% x f21 damage taken for 5s (x (1+BDI)) per Octopunch cast.
ssr_weaken_pct = coeff_pct(150, 21, True, 4) if unlocked("SSR_WEAKEN") else 0.0
monster_dmg_bonus = ssr_weaken_pct * min(1.0, 5 * (1 + buff_duration_increase_pct / 100) / eff_cooldown(OCTOPUNCH_COOLDOWN, True))

# ---- Engine pass 1: the buff schedule (independent of the skill weights) ----
BUFF_SPEC = {   # engine id -> (row key, base cooldown, base duration)
    "CB": ("CROSSBONES_FD", 28, 12), "TL": ("TIME_LEAP_FD", 65, 40),
}
ENGINE_N = {}
E_ENGINE = None
E_FS = {}
PHI_ROWS = {}
PHI_UNIF = 1.0
_eng_base = dict(T=fight_duration, S=status_effect_damage, ko=KO_WINDOWS.get(content_type, []), hex_v=0.0, hex_period=20, hex_max=3,
                 hex_avg=0.0, charm_v=0.0, c_slot=0.0, stun=_stun_vec, groups=[])


def _engine_buff(bid, F):
    key, cd0, dur0 = BUFF_SPEC[bid]
    cd, dur = eff_cooldown(cd0, True), eff_duration(dur0)
    return dict(id=bid, kind="ramp", F=F, dur=min(dur, cd), cd=cd, on=unlocked(key), p0=1, p1=1, ramp_t=1, dur0=1)


if status_on:
    fd_scale = 100 / (100 + final_damage + final_damage_rest)
    _buffs = [_engine_buff("CB", crossbones_full * fd_scale), _engine_buff("TL", time_leap_full * fd_scale)]
    _eng_host = dict(_eng_base, A0=roll_of_dice_pct, buffs=_buffs)
    _e1 = stl.solve(_eng_host)
    attack_bucket_mult = _e1["Bbuff_mean"]
    final_damage_extra = final_damage_rest
    for _bid, (_key, _cd0, _dur0) in BUFF_SPEC.items():
        ENGINE_N[_key] = _e1["buffs"][_bid]["n"]


def _avg_at(key, full, cd0, dur0):
    if not unlocked(key):
        return 0.0
    if key in ENGINE_N:
        return full * exact_uptime_at(ENGINE_N[key], eff_cooldown(cd0, True), eff_duration(dur0))
    return full * duty_cycle_uptime(cd0, dur0)


def hit_damage(coeff_pct_val, is_basic, maple_ratio=0.0, extra_fd_pct=0.0):
    base_damage = attack * (coeff_pct_val / 100)
    dmg_reduction = 5000 / (6000 + monster_defense * (1 - def_pen / 100))
    maple_mult = (1 + maple_ratio * maple_hero_pct / 100) if maple_ratio else 1.0
    if extra_fd_pct:
        maple_mult *= (1 + extra_fd_pct / 100)
    final_mult = (1 + (final_damage + final_damage_extra) / 100) * maple_mult
    source_pct = basic_attack_damage if is_basic else skill_damage
    # Boss/Normal Monster Damage% is deliberately NOT applied here — it's blended per-branch
    # (its own multiplier * its own target count) in blend_branches, applied by the
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


# ---- Hook Bomber (basic attack) hit (needed by the engine weights) ----
hook_bomber_hit = hit_damage(hook_bomber_pct, True)

# ---- Sea Serpent Burst / Serpent Assault pieces ----
gss1 = level >= 72
sea_serpent_burst_pct = (
    coeff_pct(4300 if gss1 else 1300, 12, True, 3 if gss1 else 2) * (1 + level_gated_sum({39: 50}) / 100)
    if unlocked("SEA_SERPENT_BURST") else 0.0
)
gss2_fd_pct = coeff_pct(1000, 22, True, 4) if unlocked("GSS_II_FD") else 0.0
sea_serpent_burst_hit = hit_damage(sea_serpent_burst_pct, False, extra_fd_pct=gss2_fd_pct)
ssb_hits = 2 + (1 if level >= 118 else 0)
ssb_targets = 5 + (2 if gss1 else 0) + (2 if level >= 110 else 0)
serpent_assault_pct = (coeff_pct(4800, 12, True, 3) * (1 + level_gated_sum({82: 50}) / 100)) if unlocked("SERPENT_ASSAULT") else 0.0
serpent_assault_hit = hit_damage(serpent_assault_pct, False, maple_ratio=MAPLE_HERO_RATIOS.get("SERPENT_ASSAULT", 0))

# ---- Other damage skills ----
DAMAGE_SKILLS = {
    "CORKSCREW_BLOW": dict(job_step=3, cooldown=CORKSCREW_COOLDOWN, hits=2, base=3400, fidx=12, scales=True,
                            mastery=level_gated_sum({73: 80}), mastery_boss=0, mastery_normal=0,
                            costs_action=True, targets=7, maple_ratio=MAPLE_HERO_RATIOS.get("CORKSCREW_BLOW", 0)),
    "OCTOPUNCH": dict(job_step=4, cooldown=OCTOPUNCH_COOLDOWN,
                       hits=(5 if monster_type in ("boss", "pvp") else 3),
                       base=9000, fidx=12, scales=True,
                       mastery=level_gated_sum({108: 50}), mastery_boss=0, mastery_normal=0,
                       costs_action=True, targets=4),
    # Sea Serpent's Rage / Raging Serpent Assault share Octopunch's live cooldown and CDR eligibility.
    "SEA_SERPENTS_RAGE": dict(job_step=4, cooldown=OCTOPUNCH_COOLDOWN, hits=2, base=17000, fidx=21, scales=True,
                               mastery=level_gated_sum({122: 100}), mastery_boss=0, mastery_normal=0,
                               costs_action=True, targets=8),
    "RAGING_SERPENT_ASSAULT": dict(job_step=4, cooldown=OCTOPUNCH_COOLDOWN, hits=2, icd=1, window=5, base=13000,
                                    fidx=12, scales=True, mastery=level_gated_sum({130: 50}), mastery_boss=0, mastery_normal=0,
                                    costs_action=True, targets=9, proc_chance=uptime),
    "NAUTILUS_STRIKE": dict(job_step=4, cooldown=33, hits=5, base=19500, fidx=12, scales=True,
                             mastery=level_gated_sum({126: 50}), mastery_boss=0, mastery_normal=0,
                             costs_action=True, targets=15),
}
NORMAL_MONSTER_TARGETS = {k: v["targets"] for k, v in DAMAGE_SKILLS.items()}


def skill_hit(key, s):
    """Expected damage of one hit of a damage skill (before the boss/normal branch multipliers)."""
    pct = coeff_pct(s["base"], s["fidx"], s["scales"], s["job_step"]) * (1 + s.get("mastery", 0) / 100) + s.get("fold", 0)  # a skill mastery MULTIPLIES the skill's damage (game-confirmed 2026-11-03); fold-ins stay additive
    return hit_damage(pct, False, maple_ratio=s.get("maple_ratio", MAPLE_HERO_RATIOS.get(key, 0)))


# ---- Status/KO engine pass 2: the damage skills' casts (weight of one cast = its boss damage before any timing factor) ----
if status_on:
    def _percast(key):
        if not unlocked(key):
            return 0.0
        sk = DAMAGE_SKILLS[key]
        hits = sk["hits"] * (ticks(capped_window(sk["window"]), sk["icd"]) if sk.get("icd") else 1)
        return sk.get("proc_chance", 1.0) * hits * skill_hit(key, sk) * branch_multipliers(sk["targets"], sk.get("mastery_boss", 0), sk.get("mastery_normal", 0))[0]
    _c_slot = HOOK_BOMBER_HITS * hook_bomber_hit * branch_multipliers(hook_bomber_targets, hook_bomber_mastery_boss_damage, 0)[0]
    _groups = []
    for _gid, _cast, _ents in STATUS_GROUPS:
        _entries = []
        for _row, _typ, _win, _gate, _wk in _ents:
            _w = _percast(_wk)
            if _gate and not unlocked(_gate):
                _w = 0.0
            _entries.append(dict(row=_row, typ=_typ, w=_w, L=(capped_window(DAMAGE_SKILLS[_win]["window"]) if _win else 1),
                                 on=(1 if (not _gate or unlocked(_gate)) else 0)))
        _groups.append(dict(id=_gid, cd=eff_cooldown(DAMAGE_SKILLS[_cast]["cooldown"], True),
                            on=unlocked(_cast), slot=True, entries=_entries, fixed=_cast in {e["key"] for e in PLAYER_STUN}, t0=0.0))
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


# ---- Cast rate with the engine's cast counts ----
cast_rate = cast_rate_with({k: v for k, v in ENGINE_N.items() if k in dict(SKILL_CAST_ROWS + BUFF_CAST_ROWS)})
hook_bomber_per_second = max(0, actions_per_second - cast_rate)

# ---- Hook Bomber (basic attack) DPS ----
hook_bomber_dps = (blend_branches("HOOK_BOMBER", HOOK_BOMBER_HITS * hook_bomber_hit * hook_bomber_per_second, hook_bomber_targets, hook_bomber_mastery_boss_damage, 0)
                   if unlocked("HOOK_BOMBER") else 0.0)

# ---- Sea Serpent Burst / Serpent Assault: one activation every T seconds, split (1-u)/u ----
sea_serpent_burst_dps = (
    blend_branches("SEA_SERPENT_BURST", ssb_hits * sea_serpent_burst_hit * ((1 - uptime) if unlocked("SERPENT_ASSAULT") else 1.0) / serpent_T, ssb_targets)
    if unlocked("SEA_SERPENT_BURST") else 0.0
)
serpent_assault_dps = (
    blend_branches("SERPENT_ASSAULT", 3 * serpent_assault_hit * uptime / serpent_T, 12)
    if unlocked("SERPENT_ASSAULT") else 0.0
)

skill_dps = {}
for key, s in DAMAGE_SKILLS.items():
    if not unlocked(key):
        skill_dps[key] = 0.0
        continue
    hd = skill_hit(key, s)
    proc_prob = s.get("proc_chance", 1.0)
    eff_cd = eff_cooldown(s["cooldown"], s["costs_action"])
    if status_on and key in ENGINE_N:
        # engine casts: a DoT row's hits = hits per full window x effective casts (last window truncated at the fight end)
        _per_cast = s["hits"] * (ticks(capped_window(s["window"]), s["icd"]) if s.get("icd") else 1)
        rate = _per_cast * (E_FS[key] if key in STATUS_FS_KEYS else ENGINE_N[key]) / fight_duration
    elif fixed_duration_active:
        rate = non_buff_total_hits(eff_cd, s["hits"], s.get("icd"), s.get("window")) / fight_duration
    else:
        hits = s["hits"] * (ticks(capped_window(s["window"]), s["icd"]) if s.get("icd") else 1)
        rate = hits / eff_cd
    skill_dps[key] = blend_branches(key, proc_prob * rate * hd, s["targets"], s.get("mastery_boss", 0), s.get("mastery_normal", 0))

# ---- Nautilus Strike - Final Attack: any attack, 30% chance per attack per enemy hit, 1s ICD => X/(1+ICD*X),
#      X = sum over Hook Bomber + the action-costing damage skills of rate*(1-(1-c)^N) (N=1 on boss/PvP) ----
if unlocked("NAUTILUS_FINAL_ATTACK"):
    _sources = [(hook_bomber_per_second, hook_bomber_targets)]
    for _k in ("CORKSCREW_BLOW", "OCTOPUNCH", "NAUTILUS_STRIKE"):
        if unlocked(_k):
            _cd = eff_cooldown(DAMAGE_SKILLS[_k]["cooldown"], DAMAGE_SKILLS[_k]["costs_action"])
            _casts = ENGINE_N[_k] if (status_on and _k in ENGINE_N) else non_buff_casts(_cd)
            _sources.append((((_casts / fight_duration) if fixed_duration_active else (1 / _cd)), DAMAGE_SKILLS[_k]["targets"]))
    _hit = hit_damage(coeff_pct(8500, 21, True, 4), False)
    _chance, _icd = 0.30, 1.0
    _x_boss = _chance * sum(r for r, _ in _sources)
    _x_norm = sum(r * roll_prob(_chance, t) for r, t in _sources)
    _b, _n = branch_multipliers(1)
    _fb, _fn = timing_factors("NAUTILUS_FINAL_ATTACK")
    _bp, _np = _x_boss / (1 + _icd * _x_boss) * _hit * _b * _fb, _x_norm / (1 + _icd * _x_norm) * _hit * _n * _fn
    _BRANCH_PAIRS["NAUTILUS_FINAL_ATTACK"] = (_bp, _np)
    skill_dps["NAUTILUS_FINAL_ATTACK"] = (1 - normal_weight) * _bp + normal_weight * _np
else:
    skill_dps["NAUTILUS_FINAL_ATTACK"] = 0.0

total_dps = hook_bomber_dps + sea_serpent_burst_dps + serpent_assault_dps + sum(skill_dps.values())

# ---------------------------------------------------------------------------------------------------------------
# Companion: plain-Python port (src/companion_python_model.py) of src/companion_model.py's rules, fed with this script's own numbers for the
# player's pipeline.  The verify run clears the artifact slots, so the artifact snapshot terms (Hexagon, Charm, Chalice) are zero here; they are
# covered by the dedicated hand checks instead.
# ---------------------------------------------------------------------------------------------------------------
companion_choice = _in("companion_choice")
c_level = c_level0
companion_dps = 0.0
companion_result = None
if (companion_choice != "None" and c_level >= 1) or _pl_on:
    pb_total = sum(v[0] for v in _BRANCH_PAIRS.values())
    pn_total = sum(v[1] for v in _BRANCH_PAIRS.values())
    pu_total = sum(_BRANCH_PAIRS[k][0] for k in STATUS_UNIFORM_ROWS if k in _BRANCH_PAIRS)
    basic_b, basic_n = _BRANCH_PAIRS.get("HOOK_BOMBER", (0.0, 0.0))
    _fdpart = 1 + (final_damage + serpent_scale_avg + crossbones_full + time_leap_full + speed_infusion_full) / 100
    _boss_pct = boss_damage + monster_dmg_bonus
    _norm_pct = normal_damage + monster_dmg_bonus
    comp_host = dict(
        mt=monster_type, T=fight_duration, content=content_type, pvp_len=PVP_FIGHT_DURATION, cap=max_enemies_hit, w=normal_weight,
        unit=hit_damage(100.0, True) / 100,
        bad=basic_attack_damage, sd=skill_damage, aps=actions_per_second,
        avgbuff=attack_bucket_mult * (1 + (final_damage + final_damage_extra) / 100), attack_bucket_avg=roll_of_dice_pct,
        charm_val=0.0, agg_damage_avg=0.0, hex_avg=0.0, hex_snap=lambda st: 0.0,
        avgbuff_snap=lambda charm, extra: (1 + (roll_of_dice_pct + charm + extra) / 100) * _fdpart,
        agg_fd_boss_only=0.0, agg_fd_norm_only=0.0, chalice_avg_boss=0.0, chalice_avg_norm=0.0, chalice_full=0.0, horn_avg=0.0, horn_full=0.0,
        boss_pct=_boss_pct, norm_pct=_norm_pct, extra_boss=1.0, extra_norm=1.0,
        player_boss=pb_total, player_norm=pn_total,
        player_uniform_boss=pu_total, player_basic_boss=basic_b, player_basic_norm=basic_n,
        cr_total=crit_rate + crit_rate_bonus, cd_total=crit_damage + crit_damage_bonus, min_dmg=min_damage, max_dmg=max_damage, defense=monster_defense,
        def_pen=def_pen, taken_bucket=0.0 if monster_type == "pvp" else ((1 - normal_weight) * _boss_pct + normal_weight * _norm_pct),
        pst=PST,
        st=dict(on=status_on, S=status_effect_damage,
                mult=(list(E_ENGINE["mult"]) + [1.0] * (stl.NB_MAX - E_ENGINE["nb"])) if status_on else None,
                act=(list(E_ENGINE["act"]) + [0.0] * (stl.NB_MAX - E_ENGINE["nb"])) if status_on else None),
    )
    companion_result = cpm.run(comp_host, companion_choice if (companion_choice != "None" and c_level >= 1) else "None", c_level, _in("companion_summon_time_increase_pct"))
    companion_dps = companion_result["comp_blend_dps"]
    print(f"Companion ({companion_choice} Lv{c_level}) DPS = {companion_dps:.4f}  (best candidate {companion_result['best']}, s={companion_result['s']}, "
          f"W={companion_result['W']:.2f}; damage {(1 - normal_weight) * companion_result['dmg_b'] + normal_weight * companion_result['dmg_n']:.4f}, "
          f"uplift {(1 - normal_weight) * companion_result['upl_b'] + normal_weight * companion_result['upl_n']:.4f})")
total_dps += companion_dps

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
print()
solution = _get_solution()

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

if status_on:
    # the engine strip itself: cast counts and timing factors against the Python reference
    for _row, _pfx in STATUS_CAST_PREFIX.items():
        if _row not in ENGINE_N:
            continue
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
