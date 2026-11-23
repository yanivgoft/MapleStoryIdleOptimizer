#!/usr/bin/env python3
"""
Cross-checks Corsair-DPS-Calculator.xlsx against an independent Python port of the same logic,
using the workbook's own default Inputs values. Then loads the live workbook with the `formulas`
package and diffs Total DPS + every per-skill DPS cell (Calc!O<row>) against this script's
independent numbers. Mirrors verify_buccaneer_workbook.py in structure and method.

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
XLSX_PATH = REPO / "Corsair" / "Corsair-DPS-Calculator.xlsx"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_corsair_workbook import ROW, IN, UNLOCK_LEVEL, MAPLE_HERO_RATIOS, AHOY_MATEYS_RATIOS, R_TOTAL, CONTENT_TYPES  # noqa: E402
from build_corsair_workbook import STATUS_CAST_PREFIX, STATUS_GROUPS, STATUS_BUFFS, STATUS_UNIFORM_ROWS, STATUS_PHI_ROWS, STATUS_FS_KEYS, STATUS_MAIN_LAYOUT  # noqa: E402
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

_ct_col = {}
for _c in range(3, 13):
    _name = _inputs_ws.cell(row=2, column=_c).value
    if _name in CONTENT_TYPES:
        _ct_col[_name] = _c


def _in(key):
    if key in ("level", "content_type"):
        return _inputs_ws.cell(row=IN[key], column=2).value
    active_ct = _inputs_ws.cell(row=IN["content_type"], column=2).value
    val = _inputs_ws.cell(row=IN[key], column=_ct_col.get(active_ct, 2)).value
    return 0 if val is None else val


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


_BRANCH_PAIRS = {}   # key -> (boss DPS, normal DPS) of the row (incl. the timing factors); filled by blend_branches / the proc rows


def branch_multipliers(targets, mastery_boss=0, mastery_normal=0):
    """(boss_branch, normal_branch) damage multipliers; PvP is single-enemy with neither bonus."""
    if monster_type == "pvp":
        return 1.0, 1.0
    t = min(targets, max_enemies_hit)
    return 1 + (boss_damage + mastery_boss + monster_dmg_bonus) / 100, (1 + (normal_damage + mastery_normal + monster_dmg_bonus) / 100) * t


def roll_prob(chance, targets):
    """P(at least one success) over the per-enemy chance rolls of ONE attack hitting N = min(targets, max_enemies) enemies."""
    return 1 - (1 - chance) ** min(targets, max_enemies_hit)


def blend_branches(key, unit, targets, mastery_boss=0, mastery_normal=0):
    """Time-weighted DPS of one row: (1-w)*unit*boss_branch*timing_boss + w*unit*normal_branch*timing_normal.  Correct for the real Total DPS; Sensitivity's
    marginal-value ranking uses a separate, ratio-based blend instead (see build_sensitivity_sheet)."""
    b, n = branch_multipliers(targets, mastery_boss, mastery_normal)
    fb, fn = timing_factors(key)
    _BRANCH_PAIRS[key] = (unit * b * fb, unit * n * fn)
    return (1 - normal_weight) * unit * b * fb + normal_weight * unit * n * fn


def proc_branch_dps(key, chance, icd, sources, payoff_hit, payoff_targets):
    """A 'When attacking ... X% chance' proc rolls once per attack per ENEMY HIT (user decision 2026-11-04).
    sources = [(attack_rate_per_s, targets_of_that_attack)]. Boss/PvP branch: 1 enemy => X = c*sum(rate);
    normal branch: X = sum(rate*(1-(1-c)^N)). Proc rate = X/(1+ICD*X); the two branches blend by time weight (with the rows' timing factors)."""
    x_boss = chance * sum(r for r, _ in sources)
    x_norm = sum(r * roll_prob(chance, t) for r, t in sources)
    boss_b, norm_b = branch_multipliers(payoff_targets)
    rate_boss = x_boss / (1 + icd * x_boss)
    rate_norm = x_norm / (1 + icd * x_norm)
    fb, fn = timing_factors(key)
    pair = (rate_boss * payoff_hit * boss_b * fb, rate_norm * payoff_hit * norm_b * fn)
    _BRANCH_PAIRS[key] = pair
    return (1 - normal_weight) * pair[0] + normal_weight * pair[1]


def coeff_pct(base, fidx, scales, job_step):
    lvl = input_level(job_step, level, skill1, skill2, skill3, skill4, skill_all)
    if not scales:
        return base / 10
    return (base / 10) * (get_factor(lvl, fidx) / 1000)


# ---- Maple Hero (real/confirmed level-1 anchors: Siege Bomber 20%, Blackboot Bill 40%, Swift
#      Fire 80% — only the growth curve shape is a FLAGGED ASSUMPTION) + Ahoy Mateys (a SEPARATE
#      helper, +250%/+100% FD to Scurvy Summons/All Aboard) ----
maple_hero_pct = coeff_pct(200, 23, True, 4) if unlocked("MAPLE_HERO_HELPER") else 0.0
ahoy_mateys_pct = coeff_pct(2500, 21, True, 4) if unlocked("AHOY_MATEYS_HELPER") else 0.0

# ---- Actions Per Second — combines raw Inputs!attack_speed with Nimble Feet's own duty-cycle-
#      averaged AS bonus via the standard diminishing-returns stack (factor 150) ----
def exact_buff_uptime(cooldown, buff_duration):
    casts = exact_casts(cooldown)
    remaining_after_last = max(0.0, fight_duration - (casts - 1) * cooldown)
    last_uptime = min(buff_duration, remaining_after_last)
    return (casts - 1) * min(buff_duration, cooldown) + last_uptime


def duty_cycle_uptime(cooldown, duration):
    """Exact/fixed-duration-aware uptime fraction for a real cooldown-gated buff — shared by
    Nimble Feet/Jolly Roger (both real Type=Active casts confirmed via maplestoryidle.info)."""
    eff_cd = eff_cooldown(cooldown, True)
    if fixed_duration_active:
        return exact_buff_uptime(eff_cd, eff_duration(duration)) / fight_duration
    elif monster_type == "pvp":
        return min(eff_duration(duration), PVP_FIGHT_DURATION) / PVP_FIGHT_DURATION
    return min(1.0, eff_duration(duration) / eff_cd)


def uptime_fraction_steady(duration, cooldown):
    """Steady-state duty cycle (matches the build script's own uptime_fraction_expr exactly, NOT
    duty_cycle_uptime's fixed-duration-exact math) — used for the Ahoy Mateys - Final Damage
    proc, which is a live formula with no Skills-sheet row/Calc!R CastsInFight column to drive
    the exact version."""
    scaled_duration = duration * (1 + buff_duration_increase_pct / 100)
    if monster_type == "pvp":
        return min(scaled_duration, PVP_FIGHT_DURATION) / PVP_FIGHT_DURATION
    return min(1.0, scaled_duration / cooldown)


def _nimble_feet_as_avg():
    """Nimble Feet's own duty-cycle-averaged Attack Speed% — independent of actions_per_second
    (fixed 60s cooldown/15s duration, not AS-scaled), so no circularity computing this first."""
    if not unlocked("NIMBLE_FEET"):
        return 0.0
    pct = coeff_pct(150, 0, False, 1)
    return pct * duty_cycle_uptime(60, 15)


_nimble_feet_as_bonus = _nimble_feet_as_avg()
actions_per_second = 1 + min(150, 150 * (1 - (1 - attack_speed_base / 150) * (1 - _nimble_feet_as_bonus / 150))) / 100

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


# ---------------------------------------------------------------------------------------------------------------
# Status Effect Damage / KO timeline engine (src/status_timeline.py `solve`, the plain-Python reference): fixed-length single-target content with
# KO phases (World Boss, Enhancement Dungeon) or a stunning/freezing source (the companion's stuns, the player's own Blackboot Bill).  The player casts the
# engine buff (Jolly Roger: Final Damage) and the cooldown skills when they pay most.
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
# The player's own stunning skills (game table): Blackboot Bill stuns for 2 s (cooldown 23 s, no Reuse mastery), cast on cooldown from the start
BLACKBOOT_COOLDOWN = 23
PLAYER_STUN = [dict(id="BILL", key="BLACKBOOT_BILL", typ="cast", dur=2.0, p=1.0, cd=BLACKBOOT_COOLDOWN)]
_pl_on = any(unlocked(e["key"]) for e in PLAYER_STUN)
# The workbook's effective Companion Summoning Time Increase is the Inputs value + Arwen's Glass Shoes (+20% star 0 .. +40% star 5, Artifacts row
# arwens_glass_shoes_summon_time_increase_pct).  The verify run clears the artifact slots, so the artifact term is 0 in every cpm.run below; it is
# covered by the equivalence test (artifact at Inputs x == no artifact at Inputs x + star value).
stun_info = (cpm.run(_stub, _companion_choice0, c_level0, _in("companion_summon_time_increase_pct"))
             if (_companion_choice0 != "None" and c_level0 >= 1) else None)
hasstun = bool(stun_info and stun_info.get("hasstun")) or _pl_on
KO_WINDOWS = {"World Boss": [(24, 34), (59, 69)], "Enhancement Dungeon": [(fight_duration - 4.5, fight_duration)]}
status_on = fixed_duration_active and normal_weight == 0 and (content_type in KO_WINDOWS or hasstun)

# Buff-Casting Startup Delay: in fixed-duration fights, the character casts every currently-unlocked, actively-cast buff sequentially at fight start (1/APS seconds
# each) before their first damage-skill cast - the workbook's Summary!R_STARTUP_TIME (0 when the engine is on: buffs are cast when they pay).
if fixed_duration_active and not status_on:
    buff_cast_startup_time = (
        (1 if unlocked("NIMBLE_FEET") else 0) + (1 if unlocked("JOLLY_ROGER_FD") else 0)
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


# ---- Basic attack (Eight-Legs Easton) ----
eight_legs_easton_targets = 6 + basic_attack_target_increase
EIGHT_LEGS_EASTON_HITS = 6 if level >= 136 else 5
eight_legs_easton_mastery_damage = level_gated_sum({102: 10, 106: 11, 116: 12, 120: 13, 128: 14, 132: 15})
eight_legs_easton_mastery_boss_damage = level_gated_sum({111: 10, 124: 10})
eight_legs_easton_pct = skill_coefficient_base * (1 + eight_legs_easton_mastery_damage / 100)

# ---- Cast rate (subtracted from Eight-Legs Easton) — action-costing skills only ----
# (key, base cooldown, costs_action, actions per cast).  Brain Scrambler / Rapid Fire's EFFECTIVE cooldown is
# divided by the Quickdraw factor f (below); all the rest use eff_cooldown directly.
COST_ACTION_ROWS = [
    ("SWIFT_FIRE", 17, True, 1),
    ("SCURVY_SUMMONS", 35, True, 1),
    ("BLACKBOOT_BILL", BLACKBOOT_COOLDOWN, True, 1),
    ("SIEGE_BOMBER", 22, True, 1),
    ("BRAIN_SCRAMBLER", 18, True, 1),
    ("NAUTILUS_STRIKE", 33, True, 1),
    ("RAPID_FIRE", 17, True, 1),
    ("BROADSIDE_BURST", 20, True, 1),
]
QD_COOLDOWN_KEYS = ("BRAIN_SCRAMBLER", "RAPID_FIRE")
QD_K = 0.25   # 1.5s per 3 Easton casts, split between the two skills: 1.5/3/2

# Quickdraw (Lv125) closed-form fixed point: B* = (APS - c0 - x0)/(1 + K*x0); f = 1 + K*B*.
# (Steady-state quantities - the engine reads the resulting cooldowns, it does not feed back into the divisor.)
if unlocked("QUICKDRAW_BAD") and monster_type != "pvp":
    _c0 = sum((1 / eff_cooldown(cd, ca)) * aps for k, cd, ca, aps in COST_ACTION_ROWS
              if ca and unlocked(k) and k not in QD_COOLDOWN_KEYS)
    _c0 += (1 / eff_cooldown(60, True)) if unlocked("NIMBLE_FEET") else 0
    _c0 += (1 / eff_cooldown(42, True)) if unlocked("JOLLY_ROGER_FD") else 0
    _x0 = sum(1 / eff_cooldown(cd, ca) for k, cd, ca, aps in COST_ACTION_ROWS if k in QD_COOLDOWN_KEYS and unlocked(k))
    qd_factor = 1 + QD_K * max(0.0, (actions_per_second - _c0 - _x0) / (1 + QD_K * _x0))
else:
    qd_factor = 1.0


def eff_cd_of(key, cd, ca):
    return eff_cooldown(cd, ca) / (qd_factor if key in QD_COOLDOWN_KEYS else 1.0)


def cast_rate_with(counts):
    """Skill + buff cast rate; `counts` maps row key -> engine cast count (the engine's schedule), other rows use the averaged formulas."""
    if fixed_duration_active:
        tot = 0.0
        for k, cd, ca, aps in COST_ACTION_ROWS:
            if ca and unlocked(k):
                tot += (counts[k] if k in counts else non_buff_casts(eff_cd_of(k, cd, ca))) * aps
        if unlocked("NIMBLE_FEET"):
            tot += counts["NIMBLE_FEET"] if "NIMBLE_FEET" in counts else exact_casts(eff_cooldown(60, True))
        if unlocked("JOLLY_ROGER_FD"):
            tot += counts["JOLLY_ROGER_FD"] if "JOLLY_ROGER_FD" in counts else exact_casts(eff_cooldown(42, True))
        return tot / fight_duration
    r = sum((1 / eff_cd_of(k, cd, ca)) * aps for k, cd, ca, aps in COST_ACTION_ROWS if ca and unlocked(k))
    r += (1 / eff_cooldown(60, True)) if unlocked("NIMBLE_FEET") else 0
    r += (1 / eff_cooldown(42, True)) if unlocked("JOLLY_ROGER_FD") else 0
    return r


# ---- Swift Fire - Weaken (Lv54): 3 strikes x 3% (max 3 stacks = 9%) for 8s per cast ----
monster_dmg_bonus = (
    9 * min(1.0, 8 * (1 + buff_duration_increase_pct / 100) / eff_cooldown(17, True))
    if (level >= 54 and unlocked("SWIFT_FIRE")) else 0.0
)

# ---- Global Final Damage bucket: Jolly Roger (real 42s/18s duty cycle) + Ahoy Mateys - Final
#      Damage proc (Mastery Lv.122, +20% FD for 20s on Scurvy Summons cast) ----
jolly_roger_full = coeff_pct(150, 21, True, 4) if unlocked("JOLLY_ROGER_FD") else 0.0
ahoy_mateys_proc_fd = 20 * uptime_fraction_steady(20, eff_cooldown(35, True)) if level >= 122 else 0.0
final_damage_rest = ahoy_mateys_proc_fd                                  # the Final Damage the engine does not time
jolly_roger_pct = jolly_roger_full * duty_cycle_uptime(42, 18) if unlocked("JOLLY_ROGER_FD") else 0.0
final_damage_extra = jolly_roger_pct + ahoy_mateys_proc_fd               # averaged model (engine off)

# ---- Attack% bucket: Roll of the Dice's dice component only (shared verbatim w/ Buccaneer) ----
roll_of_dice_pct = coeff_pct(25, 22, True, 3) * 5 / 7 if unlocked("ROLL_OF_THE_DICE_DICE") else 0.0
attack_bucket_mult = 1 + roll_of_dice_pct / 100

crit_rate_bonus = 0.0
crit_damage_bonus = 0.0

# ---- Engine pass 1: the buff schedule (independent of the skill weights) ----
ENGINE_N = {}
E_ENGINE = None
E_FS = {}
PHI_ROWS = {}
PHI_UNIF = 1.0
_eng_base = dict(T=fight_duration, S=status_effect_damage, ko=KO_WINDOWS.get(content_type, []), hex_v=0.0, hex_period=20, hex_max=3,
                 hex_avg=0.0, charm_v=0.0, c_slot=0.0, stun=_stun_vec, groups=[])
if status_on:
    _cd_jr, _dur_jr = eff_cooldown(42, True), eff_duration(18)
    fd_scale = 100 / (100 + final_damage + final_damage_rest)
    _buffs = [dict(id="JR", kind="ramp", F=jolly_roger_full * fd_scale, dur=min(_dur_jr, _cd_jr), cd=_cd_jr, on=unlocked("JOLLY_ROGER_FD"),
                   p0=1, p1=1, ramp_t=1, dur0=1)]
    _eng_host = dict(_eng_base, A0=roll_of_dice_pct, buffs=_buffs)
    _e1 = stl.solve(_eng_host)
    attack_bucket_mult = _e1["Bbuff_mean"]
    final_damage_extra = final_damage_rest
    ENGINE_N["JOLLY_ROGER_FD"] = _e1["buffs"]["JR"]["n"]


def hit_damage(coeff_pct_val, is_basic, mastery_boss, mastery_normal, maple_ratio=0.0, ahoy_ratio=0.0):
    # mastery_boss/mastery_normal are unused here now (Boss/Normal Monster Damage% is applied by
    # the caller via blend_branches, not blended into base_hit) — kept in the signature so
    # every existing call site (which passes each skill's own mastery values) doesn't need editing.
    base_damage = attack * (coeff_pct_val / 100)
    dmg_reduction = 5000 / (6000 + monster_defense * (1 - def_pen / 100))
    helper_mult = 1.0
    if maple_ratio:
        helper_mult *= (1 + maple_ratio * maple_hero_pct / 100)
    if ahoy_ratio:
        helper_mult *= (1 + ahoy_ratio * ahoy_mateys_pct / 100)
    final_mult = (1 + (final_damage + final_damage_extra) / 100) * helper_mult
    source_pct = basic_attack_damage if is_basic else skill_damage
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


# ---- Eight-Legs Easton (basic attack) hit (needed by the engine weights); Quickdraw doubles every 3rd cast => x(1 + 1/3) ----
eight_legs_easton_hit = hit_damage(eight_legs_easton_pct, True, eight_legs_easton_mastery_boss_damage, 0)
qd_damage_mult = (1 + 1 / 3) if unlocked("QUICKDRAW_BAD") else 1.0

# ---- Other damage skills ----
# Crew window/ICD: 20s (x(1+BDI) from All Aboard - Persistence @104, capped at the 35s cooldown); strike
# intervals -30% @94 (All Aboard - Strike Interval).
crew_window = min(35, 20 * (1 + buff_duration_increase_pct / 100)) if level >= 104 else 20
scurvy_icd = 1.5 * 0.7 if level >= 94 else 1.5
all_aboard_icd = 2 * 0.7 if level >= 94 else 2
siege_window = 30 if level >= 68 else 22
bombard = level >= 118
DAMAGE_SKILLS = {
    "SWIFT_FIRE": dict(job_step=2, cooldown=17, hits=3, base=1800, fidx=12, scales=True,
                        mastery=level_gated_sum({39: 50}), mastery_boss=0, mastery_normal=0,
                        costs_action=True, targets=8, maple_ratio=MAPLE_HERO_RATIOS.get("SWIFT_FIRE", 0)),
    "SCURVY_SUMMONS": dict(job_step=2, cooldown=35, hits=2, icd=scurvy_icd, window=crew_window, base=950, fidx=12,
                            scales=True, mastery=level_gated_sum({49: 50}), mastery_boss=0, mastery_normal=0,
                            costs_action=True, targets=3, ahoy_ratio=AHOY_MATEYS_RATIOS.get("SCURVY_SUMMONS", 0)),
    "ALL_ABOARD": dict(job_step=3, cooldown=35, hits=3, icd=all_aboard_icd, window=crew_window, base=1100, fidx=12,
                        scales=True, mastery=level_gated_sum({78: 50}), mastery_boss=0, mastery_normal=0,
                        costs_action=True, targets=8, ahoy_ratio=AHOY_MATEYS_RATIOS.get("ALL_ABOARD", 0)),
    "BLACKBOOT_BILL": dict(job_step=3, cooldown=BLACKBOOT_COOLDOWN, hits=4, base=1700, fidx=12, scales=True,
                            mastery=level_gated_sum({73: 50}), mastery_boss=0, mastery_normal=0,
                            costs_action=True, targets=9, maple_ratio=MAPLE_HERO_RATIOS.get("BLACKBOOT_BILL", 0)),
    "SIEGE_BOMBER": dict(job_step=3, cooldown=22, hits=1, icd=1.5, window=siege_window, base=1900, fidx=12,
                          scales=True, mastery=level_gated_sum({82: 50}), mastery_boss=0, mastery_normal=0,
                          costs_action=True, targets=6, maple_ratio=MAPLE_HERO_RATIOS.get("SIEGE_BOMBER", 0)),
    "BRAIN_SCRAMBLER": dict(job_step=4, cooldown=18, hits=2, base=29000, fidx=12, scales=True,
                             mastery=level_gated_sum({108: 100}), mastery_boss=0, mastery_normal=0,
                             costs_action=True, targets=1),
    "NAUTILUS_STRIKE": dict(job_step=4, cooldown=33, hits=5, base=19500, fidx=12, scales=True,
                             mastery=level_gated_sum({126: 50}), mastery_boss=0, mastery_normal=0,
                             costs_action=True, targets=15),
    "RAPID_FIRE": dict(job_step=4, cooldown=17, hits=7, base=18000, fidx=12, scales=True,
                        mastery=level_gated_sum({130: 70}), mastery_boss=0, mastery_normal=0,
                        costs_action=True, targets=9),
    "BROADSIDE_BURST": dict(job_step=4, cooldown=20, hits=2, base=50000, fidx=12, scales=True,
                             mastery=0, mastery_boss=0, mastery_normal=0,
                             costs_action=True, targets=10),
    # Bombardment @118 replaces the turret ticks (19000 tenths% x3 hits x8 targets); Setup @138 => 30s window.
    "BROADSIDE_SUSTAINED": dict(job_step=4, cooldown=20, hits=(3 if bombard else 1), icd=2,
                                 window=(30 if level >= 138 else 20),
                                 base=(19000 if bombard else 3300),
                                 fidx=12, scales=True, mastery=0, mastery_boss=0, mastery_normal=0,
                                 costs_action=True, targets=(8 if bombard else 5)),
}
NORMAL_MONSTER_TARGETS = {k: v["targets"] for k, v in DAMAGE_SKILLS.items()}


def skill_hit(key, s):
    """Expected damage of one hit of a damage skill (before the boss/normal branch multipliers)."""
    pct = coeff_pct(s["base"], s["fidx"], s["scales"], s["job_step"]) * (1 + s.get("mastery", 0) / 100) + s.get("fold", 0)  # a skill mastery MULTIPLIES the skill's damage (game-confirmed 2026-11-03); fold-ins stay additive
    return hit_damage(pct, False, s.get("mastery_boss", 0), s.get("mastery_normal", 0),
                      maple_ratio=s.get("maple_ratio", 0.0), ahoy_ratio=s.get("ahoy_ratio", 0.0))


# ---- Status/KO engine pass 2: the damage skills' casts (weight of one cast = its boss damage before any timing factor) ----
if status_on:
    def _percast(key):
        if not unlocked(key):
            return 0.0
        sk = DAMAGE_SKILLS[key]
        hits = sk["hits"] * (ticks(capped_window(sk["window"]), sk["icd"]) if sk.get("icd") else 1)
        return hits * skill_hit(key, sk) * branch_multipliers(sk["targets"], sk.get("mastery_boss", 0), sk.get("mastery_normal", 0))[0]
    _c_slot = EIGHT_LEGS_EASTON_HITS * eight_legs_easton_hit * qd_damage_mult * branch_multipliers(eight_legs_easton_targets, eight_legs_easton_mastery_boss_damage, 0)[0]
    _groups = []
    for _gid, _cast, _ents in STATUS_GROUPS:
        _entries = []
        for _row, _typ, _win, _gate, _wk in _ents:
            _w = _percast(_wk)
            if _gate and not unlocked(_gate):
                _w = 0.0
            _entries.append(dict(row=_row, typ=_typ, w=_w, L=(capped_window(DAMAGE_SKILLS[_win]["window"]) if _win else 1),
                                 on=(1 if (not _gate or unlocked(_gate)) else 0)))
        _groups.append(dict(id=_gid, cd=eff_cd_of(_cast, DAMAGE_SKILLS[_cast]["cooldown"], True),
                            on=unlocked(_cast), slot=True, entries=_entries, fixed=_cast in {e["key"] for e in PLAYER_STUN}, t0=0.0))
    E_ENGINE = stl.solve(dict(_eng_host, groups=_groups, c_slot=_c_slot))
    for _row, _pfx in STATUS_CAST_PREFIX.items():
        if _pfx.startswith("grp."):
            ENGINE_N[_row] = E_ENGINE["groups"][_pfx[4:]]["n"]
    PHI_ROWS = E_ENGINE["rows"]
    PHI_UNIF = E_ENGINE["phi_unif"]
    E_FS = E_ENGINE["fs"]
    print(f"Status/KO engine ON: casts {{ {', '.join(f'{k}: {v}' for k, v in ENGINE_N.items())} }}, phi_unif {PHI_UNIF:.4f}")
    print("Status/KO engine schedule (cast times, s): JR " + str([i for i, c in enumerate(_e1['buffs']['JR']['cast']) if c]) + "; "
          + "; ".join(f"{g}: {[i for i, c in enumerate(v['cast']) if c]}" for g, v in E_ENGINE["groups"].items()))
    print("Status/KO engine phi: " + ", ".join(f"{k} {v:.4f}" for k, v in PHI_ROWS.items()))


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
cast_rate_avg = cast_rate_with({})
cast_rate = cast_rate_with({k: v for k, v in ENGINE_N.items() if k in {c[0] for c in COST_ACTION_ROWS} | {"JOLLY_ROGER_FD"}})
eight_legs_easton_per_second = max(0, actions_per_second - cast_rate)

# ---- Eight-Legs Easton (basic attack) DPS ----
eight_legs_easton_dps = (
    blend_branches("EIGHT_LEGS_EASTON", EIGHT_LEGS_EASTON_HITS * eight_legs_easton_hit * eight_legs_easton_per_second * qd_damage_mult,
                   eight_legs_easton_targets, eight_legs_easton_mastery_boss_damage, 0)
    if unlocked("EIGHT_LEGS_EASTON") else 0.0
)


def cast_count(key):
    """Casts of an action-costing damage skill in the fight (engine schedule or the averaged exact count)."""
    if status_on and key in ENGINE_N:
        return ENGINE_N[key]
    return non_buff_casts(eff_cd_of(key, DAMAGE_SKILLS[key]["cooldown"], DAMAGE_SKILLS[key]["costs_action"]))


def skill_rate(key, s):
    if status_on and key in ENGINE_N:
        # engine casts: a DoT row's hits = hits per full window x effective casts (last window truncated at the fight end)
        _per_cast = s["hits"] * (ticks(capped_window(s["window"]), s["icd"]) if s.get("icd") else 1)
        return _per_cast * (E_FS[key] if key in STATUS_FS_KEYS else ENGINE_N[key]) / fight_duration
    eff_cd = eff_cd_of(key, s["cooldown"], s["costs_action"])
    if fixed_duration_active:
        return non_buff_total_hits(eff_cd, s["hits"], s.get("icd"), s.get("window")) / fight_duration
    hits = s["hits"] * (ticks(capped_window(s["window"]), s["icd"]) if s.get("icd") else 1)
    return hits / eff_cd


skill_dps = {}
for key, s in DAMAGE_SKILLS.items():
    if not unlocked(key):
        skill_dps[key] = 0.0
        continue
    skill_dps[key] = blend_branches(key, skill_rate(key, s) * skill_hit(key, s), s["targets"], s.get("mastery_boss", 0), s.get("mastery_normal", 0))

# ---- Nautilus Strike - Final Attack: any attack, 30% chance, 1s ICD => (c*R)/(1+ICD*c*R) with R = the
#      combined cast rate of Easton + the direct-attack action-costing skills ----
if unlocked("NAUTILUS_FINAL_ATTACK"):
    _sources = [(eight_legs_easton_per_second, eight_legs_easton_targets)]
    for _k in ("SWIFT_FIRE", "BLACKBOOT_BILL", "BRAIN_SCRAMBLER", "NAUTILUS_STRIKE", "RAPID_FIRE"):
        if unlocked(_k):
            _cd = eff_cd_of(_k, DAMAGE_SKILLS[_k]["cooldown"], DAMAGE_SKILLS[_k]["costs_action"])
            _sources.append((((cast_count(_k) / fight_duration) if fixed_duration_active else (1 / _cd)),
                             DAMAGE_SKILLS[_k]["targets"]))
    skill_dps["NAUTILUS_FINAL_ATTACK"] = proc_branch_dps(
        "NAUTILUS_FINAL_ATTACK", 0.30, 1.0, _sources, hit_damage(coeff_pct(8500, 21, True, 4), False, 0, 0), 1)
else:
    skill_dps["NAUTILUS_FINAL_ATTACK"] = 0.0

# ---- Majestic Presence (procs off 3 independent sources: Basic Attack + Brain Scrambler + Rapid
#      Fire; 25% per attack per enemy hit with a 0.5s internal cooldown => X/(1+ICD*X)) ----
if unlocked("MAJESTIC_PRESENCE"):
    mp_pct = coeff_pct(18000, 21, True, 4) * (1 + level_gated_sum({134: 50}) / 100)
    mp_hit = hit_damage(mp_pct, False, 0, 0)

    def _source_rate(key):
        if not unlocked(key):
            return 0.0
        return skill_rate(key, DAMAGE_SKILLS[key])

    _mp_sources = [
        (eight_legs_easton_per_second, eight_legs_easton_targets),
        (_source_rate("BRAIN_SCRAMBLER"), DAMAGE_SKILLS["BRAIN_SCRAMBLER"]["targets"]),
        (_source_rate("RAPID_FIRE"), DAMAGE_SKILLS["RAPID_FIRE"]["targets"]),
    ]
    majestic_presence_dps = proc_branch_dps("MAJESTIC_PRESENCE", 0.25, 0.5, _mp_sources, mp_hit, 6)
else:
    majestic_presence_dps = 0.0
skill_dps["MAJESTIC_PRESENCE"] = majestic_presence_dps

total_dps = eight_legs_easton_dps + sum(skill_dps.values())

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
    basic_b, basic_n = _BRANCH_PAIRS.get("EIGHT_LEGS_EASTON", (0.0, 0.0))
    _fdpart = 1 + (final_damage + ahoy_mateys_proc_fd + jolly_roger_full) / 100
    _boss_pct = boss_damage + monster_dmg_bonus
    _norm_pct = normal_damage + monster_dmg_bonus
    comp_host = dict(
        mt=monster_type, T=fight_duration, content=content_type, pvp_len=PVP_FIGHT_DURATION, cap=max_enemies_hit, w=normal_weight,
        unit=hit_damage(100.0, True, 0, 0) / 100,
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
print(f"Eight-Legs Easton casts/sec = {eight_legs_easton_per_second:.6f}")
print(f"Eight-Legs Easton DPS = {eight_legs_easton_dps:.4f}")
for k, v in skill_dps.items():
    print(f"  {k:28s} DPS = {v:.4f}")
print(f"TOTAL DPS = {total_dps:.4f}")

# ---------------------------------------------------------------------------
# Cross-check against the actual live workbook
# ---------------------------------------------------------------------------
print()
solution = _get_solution()

py_skill_dps = dict(skill_dps)
py_skill_dps["EIGHT_LEGS_EASTON"] = eight_legs_easton_dps

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
