#!/usr/bin/env python3
"""
Cross-checks Paladin-DPS-Calculator.xlsx against an independent Python port of the same logic, using
the workbook's own default Inputs values. Then loads the live workbook with the `formulas` package
and diffs Total DPS + every per-skill DPS cell (Calc!O<row>) against this script's independent
numbers. Mirrors verify_bowmaster_workbook.py in structure and method.

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
XLSX_PATH = REPO / "Paladin" / "Paladin-DPS-Calculator.xlsx"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_paladin_workbook import ROW, IN, UNLOCK_LEVEL, MAPLE_HERO_RATIOS, R_TOTAL, CONTENT_TYPES  # noqa: E402
from build_paladin_workbook import STATUS_CAST_PREFIX, STATUS_GROUPS, STATUS_BUFFS, STATUS_UNIFORM_ROWS, STATUS_PHI_ROWS, STATUS_FS_KEYS, STATUS_MAIN_LAYOUT  # noqa: E402
from build_paladin_workbook import STATUS_ROW_MIN_LEVEL, COMBAT_ORDERS_ATTACK_PCT  # noqa: E402
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
skill_coefficient_base = None  # set once Combat Orders' uptime is known (below)


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


CDR_EXEMPT = {"DIVINE_JUDGMENT"}  # mirrors the build script (rate-surrogate cooldown)


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


def buff_avg(pct, duration, cooldown, costs_action):
    eff_cd = eff_cooldown(cooldown, costs_action)
    if fixed_duration_active:
        uptime = exact_buff_uptime(eff_cd, eff_duration(duration)) / fight_duration
    elif monster_type == "pvp":
        uptime = min(eff_duration(duration), PVP_FIGHT_DURATION) / PVP_FIGHT_DURATION
    else:
        uptime = min(1.0, eff_duration(duration) / eff_cd)
    return pct * uptime


# ---- live workbook access (the `formulas` evaluation is loaded lazily) ----
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


def exact_uptime_at(n, cooldown, buff_duration):
    """The workbook's exact-uptime formula (exact_buff_uptime_expr) at a GIVEN cast count n: (n-1)*MIN(dur, cd) + MIN(dur, remaining after the last cast)."""
    remaining_after_last = max(0.0, fight_duration - (n - 1) * cooldown)
    return ((n - 1) * min(buff_duration, cooldown) + min(buff_duration, remaining_after_last)) / fight_duration


# ---- Nimble Feet (Attack Speed buff, duty-cycle averaged) - independent of everything below ----
nimble_feet_pct = 150 / 10     # coeff_pct(150, 0, False, 1): a non-scaling buff
nimble_avg = buff_avg(nimble_feet_pct, 15, 60, True) if unlocked("NIMBLE_FEET") else 0.0
as_bonus = nimble_avg
actions_per_second = 1 + min(150, 150 * (1 - (1 - attack_speed_base / 150) * (1 - as_bonus / 150))) / 100

# ---------------------------------------------------------------------------------------------------------------
# Status Effect Damage / KO timeline engine (src/status_timeline.py `solve`, the plain-Python reference): fixed-length single-target content with
# KO phases (World Boss, Enhancement Dungeon) or a stunning/freezing source (the companion's stuns, the player's own Rush).  The player casts the engine
# buffs (HP Recovery, Combat Orders' Attack%, Guardian, Divine Blessing) and the cooldown skills when they pay most.
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
# The player's own stunning skills (game table): Rush stuns for 2.5 s, cast on cooldown from the start
RUSH_COOLDOWN = (22 * 0.7) if level >= 90 else 22
PLAYER_STUN = [dict(id="RUSH", key="RUSH", typ="cast", dur=2.5, p=1.0, cd=RUSH_COOLDOWN)]
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
BUFF_ROW_KEYS = {"GUARDIAN", "DIVINE_BLESSING", "HP_RECOVERY_ATK", "COMBAT_ORDERS", "NIMBLE_FEET"}
if fixed_duration_active and not status_on:
    buff_cast_startup_time = sum(
        1 for k in ("GUARDIAN", "DIVINE_BLESSING", "HP_RECOVERY_ATK", "COMBAT_ORDERS", "NIMBLE_FEET") if unlocked(k)
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

# ---- the engine's buff list (engine pass 1) needs the buffs' cooldowns / durations / (later) their effect values ----
BUFF_SPEC = {   # engine id -> (row key, kind, base cooldown, base duration)
    "HPR": ("HP_RECOVERY_ATK", "atk", 25, 20), "CO": ("COMBAT_ORDERS", "atk", 35, 25),
    "GU": ("GUARDIAN", "ramp", 24, 20), "DB": ("DIVINE_BLESSING", "ramp", 30, 22),
}
ENGINE_N = {}
E_ENGINE = None
E_FS = {}
PHI_ROWS = {}
PHI_UNIF = 1.0
co_engine = False        # Combat Orders' casts come from the engine (level >= its Lv82 Damage Boost mastery)
_stun_vec = None
if status_on:
    _stun_vec = [min(1.0, a + b) for a, b in zip(stun_info["stun_vector"](stl.NB_MAX), stl.pl_stun_vector([dict(e, t0=0.0) for e in PST], fight_duration, stl.NB_MAX))]
    co_engine = unlocked("COMBAT_ORDERS") and level >= STATUS_ROW_MIN_LEVEL["COMBAT_ORDERS"]


def _engine_buff(bid, F, **extra):
    key, kind, cd0, dur0 = BUFF_SPEC[bid]
    cd, dur = eff_cooldown(cd0, True), eff_duration(dur0)
    on = unlocked(key) and (key != "COMBAT_ORDERS" or level >= STATUS_ROW_MIN_LEVEL[key])
    if kind == "ramp":
        return dict(id=bid, kind=kind, F=F, dur=min(dur, cd), cd=cd, on=on, p0=1, p1=1, ramp_t=1, dur0=1)
    return dict(id=bid, kind=kind, F=F, dur=dur, cd=cd, on=on)


_eng_base = dict(T=fight_duration, S=status_effect_damage, ko=KO_WINDOWS.get(content_type, []), hex_v=0.0, hex_period=20, hex_max=3,
                 hex_avg=0.0, charm_v=0.0, c_slot=0.0, stun=_stun_vec, groups=[])

# ---- Combat Orders' uptime (feeds the +skill-level factor averaging of every row): the engine's cast count when it times Combat Orders ----
co_u = 0.0   # Combat Orders uptime
co_f = 0.0   # Combat Orders' own scaling value = its 3rd-job skill-level bonus
if status_on and co_engine:
    _e_co = stl.solve(dict(_eng_base, A0=0.0, buffs=[_engine_buff("CO", COMBAT_ORDERS_ATTACK_PCT)]))
    ENGINE_N["COMBAT_ORDERS"] = _e_co["buffs"]["CO"]["n"]


def factor_eff(lvl, fidx, job_step, is_co=False):
    """FactorTable value time-averaged with Combat Orders' temporary skill-level bonus."""
    if is_co:
        return get_factor(lvl, fidx)
    bonus = co_f if job_step == 3 else (18 if (job_step == 4 and level >= 104) else 0)
    return (1 - co_u) * get_factor(lvl, fidx) + co_u * get_factor(lvl + bonus, fidx)


def coeff_pct(base, fidx, scales, job_step, is_co=False):
    lvl = input_level(job_step, level, skill1, skill2, skill3, skill4, skill_all)
    if not scales:
        return base / 10
    return (base / 10) * (factor_eff(lvl, fidx, job_step, is_co) / 1000)


# ---- Combat Orders (user: applies to the player too): +skill levels time-averaged via factor_eff ----
if unlocked("COMBAT_ORDERS"):
    co_f = coeff_pct(180, 21, True, 3, is_co=True)
    if "COMBAT_ORDERS" in ENGINE_N:
        co_u = exact_uptime_at(ENGINE_N["COMBAT_ORDERS"], eff_cooldown(35, True), eff_duration(25))
    else:
        co_u = buff_avg(1.0, 25, 35, True)
skill_coefficient_base = 290 * factor_eff(basic_lvl, 21, 4) / 1000
print(f"SKILL_COEFFICIENT (base) = {skill_coefficient_base:.4f}")
combat_orders_attack_avg = (COMBAT_ORDERS_ATTACK_PCT * co_u) if level >= 82 else 0.0


_BRANCH_PAIRS = {}   # key -> (boss DPS, normal DPS) of the row (incl. the timing factors); filled by blend_branches


def branch_multipliers(mastery_boss, mastery_normal, targets):
    """(boss branch, normal branch) multiplier of a row: each branch gets its own full (1+damage%/100) [x target count for the normal branch]."""
    if monster_type == "pvp":
        return 1.0, 1.0
    targets = min(targets, max_enemies_hit)
    boss_term = boss_damage + mastery_boss + monster_dmg_bonus
    normal_term = normal_damage + mastery_normal + monster_dmg_bonus
    return 1 + boss_term / 100, (1 + normal_term / 100) * targets


def blend_branches(key, unit, mastery_boss, mastery_normal, targets):
    """Time-weighted DPS of one row: (1-w)*unit*boss_branch*timing_boss + w*unit*normal_branch*timing_normal.  Correct for the real Total DPS; Sensitivity's
    marginal-value ranking uses a separate, ratio-based blend instead (see build_sensitivity_sheet)."""
    b, n = branch_multipliers(mastery_boss, mastery_normal, targets)
    fb, fn = timing_factors(key)
    _BRANCH_PAIRS[key] = (unit * b * fb, unit * n * fn)
    return (1 - normal_weight) * unit * b * fb + normal_weight * unit * n * fn


# ---- Helper rows (Final Attack, Maple Hero) — own D/E/F only, no independent DPS. Paladin has
#      NO Advanced Final Attack at all (confirmed absent from its skill list). ----
final_attack_pct = (
    coeff_pct(350, 21, True, 2) * (1 + level_gated_sum({54: 50}) / 100)
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
blast_mastery_damage = level_gated_sum({102: 10, 106: 11, 116: 12, 120: 13, 128: 14, 132: 15})
blast_mastery_boss_damage = level_gated_sum({111: 10, 124: 10})
blast_pct = skill_coefficient_base * (1 + blast_mastery_damage / 100) + blast_final_attack_addition
blast_targets = 6 + basic_attack_target_increase
BLAST_HITS = 6 if level >= 136 else 5


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
    ("NOBLE_DEMAND", (30 * 0.7) if level >= 94 else 30, True, 1),
    ("HEAVENS_HAMMER", 18, True, 1),
    ("DIVINE_MARK_MAIN", 16, True, 1),
    ("MAGIC_CRASH", 28, True, 1),
    ("RUSH", RUSH_COOLDOWN, True, 1),
    ("GUARDIAN", 24, True, 1),
    ("DIVINE_BLESSING", 30, True, 1),
    ("HP_RECOVERY_ATK", 25, True, 1),
    ("COMBAT_ORDERS", 35, True, 1),
    ("NIMBLE_FEET", 60, True, 1),
]


def cast_rate_with(counts):
    """Skill + buff cast rate; `counts` maps row key -> engine cast count (the engine's schedule), other rows use the averaged formulas."""
    if fixed_duration_active:
        return sum(
            (counts[k] if k in counts else (exact_casts(eff_cooldown(cd, ca)) if k in BUFF_ROW_KEYS else non_buff_casts(eff_cooldown(cd, ca)))) * aps
            for k, cd, ca, aps in COST_ACTION_ROWS if ca and unlocked(k)
        ) / fight_duration
    return sum((1 / eff_cooldown(cd, ca)) * aps for k, cd, ca, aps in COST_ACTION_ROWS if ca and unlocked(k))


# The AVERAGED model's cast rate / Blast rate (pre-engine cast counts = Calc!Z): Vessel of Light's uptime reads this one (no dependence on the engine's casts).
cast_rate_avg = cast_rate_with({})
blast_per_second_avg = max(0, actions_per_second - cast_rate_avg)

# ---- Vessel of Light (proc off basic attacks, no stated internal cooldown — uptime
#      approximated as MIN(1, Duration x ProcChance%/100 x Basic Attack Rate)). Greater Vessel of
#      Light has no own duty cycle and reuses this same uptime fraction directly. ----
vessel_of_light_pct = (coeff_pct(150, 22, True, 2) + level_gated_sum({49: 5})) if unlocked("VESSEL_OF_LIGHT") else 0.0
# PROC RULE (2026-11-04): the 15% rolls once per basic ATTACK per ENEMY HIT -> 1-(1-c)^N activations per attack
# (boss / PvP N=1; normal N = 6+Basic Attack Target Increase capped by Max Enemies Hit), blended by time per branch.
_vol_n = min(6 + basic_attack_target_increase, max_enemies_hit)
_vol_u_boss = min(1.0, 10 * 0.15 * blast_per_second_avg)
_vol_u_normal = min(1.0, 10 * (1 - (1 - 0.15) ** _vol_n) * blast_per_second_avg)
vessel_of_light_uptime = (
    (_vol_u_boss if monster_type == "pvp" else (1 - normal_weight) * _vol_u_boss + normal_weight * _vol_u_normal)
    if unlocked("VESSEL_OF_LIGHT") else 0.0
)
vessel_of_light_avg = vessel_of_light_pct * vessel_of_light_uptime if unlocked("VESSEL_OF_LIGHT") else 0.0
greater_vessel_pct = (coeff_pct(180, 22, True, 4) + level_gated_sum({118: 10})) if unlocked("GREATER_VESSEL_OF_LIGHT") else 0.0
greater_vessel_avg = greater_vessel_pct * vessel_of_light_uptime if unlocked("GREATER_VESSEL_OF_LIGHT") else 0.0

hp_recovery_pct = (coeff_pct(120, 21, True, 3) + level_gated_sum({78: 10})) if unlocked("HP_RECOVERY_ATK") else 0.0
hp_recovery_avg = buff_avg(hp_recovery_pct, 20, 25, True) if unlocked("HP_RECOVERY_ATK") else 0.0

# ---- Divine Shield (fixed-interval buff, treated as its own Cooldown(s)), Guardian, Divine
#      Blessing (all live duty-cycled Final Damage buffs) ----
divine_shield_pct = coeff_pct(150, 22, True, 3) if unlocked("DIVINE_SHIELD") else 0.0
divine_shield_avg = buff_avg(divine_shield_pct, 10, 15, False) if unlocked("DIVINE_SHIELD") else 0.0
guardian_pct = coeff_pct(100, 21, True, 4) if unlocked("GUARDIAN") else 0.0
guardian_avg = buff_avg(guardian_pct, 20, 24, True) if unlocked("GUARDIAN") else 0.0
divine_blessing_pct = (coeff_pct(120, 21, True, 4) + level_gated_sum({126: 12})) if unlocked("DIVINE_BLESSING") else 0.0
divine_blessing_avg = buff_avg(divine_blessing_pct, 22, 30, True) if unlocked("DIVINE_BLESSING") else 0.0

crit_rate_bonus = 0.0  # no live Crit-Rate-buff source exists in this kit
crit_damage_bonus = 0.0  # no live Crit-Damage-buff source exists in this kit

# ---- Engine pass 1: the buff schedule (independent of the skill weights) ----
attack_bucket_mult = 1 + (vessel_of_light_avg + hp_recovery_avg + combat_orders_attack_avg) / 100
final_damage_extra = divine_shield_avg + guardian_avg + divine_blessing_avg + greater_vessel_avg
final_damage_rest = divine_shield_avg + greater_vessel_avg
if status_on:
    fd_scale = 100 / (100 + final_damage + final_damage_rest)
    _buffs = [
        _engine_buff("HPR", hp_recovery_pct),
        _engine_buff("CO", COMBAT_ORDERS_ATTACK_PCT),
        _engine_buff("GU", guardian_pct * fd_scale),
        _engine_buff("DB", divine_blessing_pct * fd_scale),
    ]
    _eng_host = dict(_eng_base, A0=vessel_of_light_avg, buffs=_buffs)
    _e1 = stl.solve(_eng_host)
    attack_bucket_mult = _e1["Bbuff_mean"]
    final_damage_extra = final_damage_rest
    for _bid, (_key, _kind, _cd0, _dur0) in BUFF_SPEC.items():
        if _key == "COMBAT_ORDERS" and not co_engine:
            continue
        ENGINE_N[_key] = _e1["buffs"][_bid]["n"]
    if co_engine:
        assert ENGINE_N["COMBAT_ORDERS"] == _e_co["buffs"]["CO"]["n"], "Combat Orders' schedule must not depend on the other buffs"

# averages at the engine's cast counts (what the workbook's host cells read): exact-uptime formula at the engine's n
def _avg_at(key, pct, cd0, dur0):
    if not unlocked(key):
        return 0.0
    if key in ENGINE_N:
        return pct * exact_uptime_at(ENGINE_N[key], eff_cooldown(cd0, True), eff_duration(dur0))
    return buff_avg(pct, dur0, cd0, True)


hp_recovery_avg_eng = _avg_at("HP_RECOVERY_ATK", hp_recovery_pct, 25, 20)
guardian_avg_eng = _avg_at("GUARDIAN", guardian_pct, 24, 20)
divine_blessing_avg_eng = _avg_at("DIVINE_BLESSING", divine_blessing_pct, 30, 22)
attack_bucket_sum = vessel_of_light_avg + hp_recovery_avg_eng + combat_orders_attack_avg    # Attack% bucket (in %) the companion's snapshot sees on average

# ---- Nimble Feet etc. are above; the hit formula below needs every bucket ----


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


def weaken_avg(pct, duration, cooldown):
    """Steady-state duty-cycle average for a Weaken-style debuff — matches the build script's own
    uptime_fraction_expr exactly (NOT the fixed-duration-exact buff_avg() above): always the
    simple duration/cooldown ratio, no CastsInFight branching, same documented-simplification
    tier as Ice-Lightning-Mage's own Freezing Breath - Weaken."""
    if monster_type == "pvp":
        scaled_duration = min(duration * (1 + buff_duration_increase_pct / 100), PVP_FIGHT_DURATION)
        return pct * scaled_duration / PVP_FIGHT_DURATION
    scaled_duration = duration * (1 + buff_duration_increase_pct / 100)
    return pct * min(1.0, scaled_duration / cooldown)


close_combat_weaken = weaken_avg(10, 10, eff_cooldown(18, True)) if level >= 44 else 0.0
noble_demand_weaken = weaken_avg(12, 10, eff_cooldown((30 * 0.7) if level >= 94 else 30, True))
divine_mark_weaken = weaken_avg(20, 10, eff_cooldown(16, True)) if level >= 138 else 0.0
monster_dmg_bonus = close_combat_weaken + noble_demand_weaken + divine_mark_weaken

# ---- Blast (basic attack) hit (needed by the engine weights) ----
blast_hit = hit_damage(blast_pct, True, blast_mastery_boss_damage, 0)

# ---- Damage skills ----
heavens_hammer_mastery_boss = 100 + (100 if level >= 134 else 0)
divine_judgment_cooldown = 10 / actions_per_second

DAMAGE_SKILLS = {
    "CLOSE_COMBAT": dict(job_step=2, cooldown=18, hits=1, base=4600, fidx=12, scales=True,
                          mastery=level_gated_sum({39: 50}), mastery_boss=0, mastery_normal=0,
                          costs_action=True, targets=7, maple_ratio=MAPLE_HERO_RATIOS.get("CLOSE_COMBAT", 0)),
    "NOBLE_DEMAND": dict(job_step=3, cooldown=(30 * 0.7) if level >= 94 else 30, hits=1, base=16000, fidx=12, scales=True,
                          mastery=level_gated_sum({73: 50}), mastery_boss=0, mastery_normal=0,
                          costs_action=True, targets=8, maple_ratio=MAPLE_HERO_RATIOS.get("NOBLE_DEMAND", 0)),
    "HEAVENS_HAMMER": dict(job_step=4, cooldown=18, hits=5, base=7800, fidx=12, scales=True,
                            mastery=level_gated_sum({108: 50}), mastery_boss=heavens_hammer_mastery_boss,
                            mastery_normal=0, costs_action=True, targets=7),
    "DIVINE_MARK_MAIN": dict(job_step=4, cooldown=16, hits=6, base=4600, fidx=12, scales=True,
                              mastery=level_gated_sum({122: 50}), mastery_boss=0, mastery_normal=0,
                              costs_action=True, targets=8),
    "DIVINE_MARK_DETONATION": dict(job_step=4, cooldown=16, hits=4, base=4000, fidx=12, scales=True,
                                    mastery=level_gated_sum({122: 50}), mastery_boss=0, mastery_normal=0,
                                    costs_action=False, targets=8),
    "DIVINE_JUDGMENT": dict(job_step=4, cooldown=divine_judgment_cooldown, hits=4, base=8500, fidx=12,
                             scales=True, mastery=level_gated_sum({130: 50}), mastery_boss=0, mastery_normal=0,
                             costs_action=False, targets=4),
    "MAGIC_CRASH": dict(job_step=4, cooldown=28, hits=1, base=48000, fidx=12, scales=True,
                         mastery=0, mastery_boss=0, mastery_normal=0, costs_action=True,
                         targets=5 + (4 if level >= 100 else 0)),
    "RUSH": dict(job_step=3, cooldown=RUSH_COOLDOWN, hits=1, base=6000, fidx=12, scales=True,
                 mastery=level_gated_sum({68: 80}), mastery_boss=0, mastery_normal=0, costs_action=True,
                 targets=12, maple_ratio=MAPLE_HERO_RATIOS.get("RUSH", 0)),
}
NORMAL_MONSTER_TARGETS = {k: v["targets"] for k, v in DAMAGE_SKILLS.items()}
# the engine's cooldown groups use each cast row's cooldown (CDR applied; the Divine Judgment surrogate is not a cast row)


def skill_hit(key, s):
    """Expected damage of one hit of a damage skill (before the boss/normal branch multipliers)."""
    pct = coeff_pct(s["base"], s["fidx"], s["scales"], s["job_step"]) * (1 + s.get("mastery", 0) / 100) + s.get("fold", 0)  # a skill mastery MULTIPLIES the skill's damage (game-confirmed 2026-11-03); fold-ins stay additive
    return hit_damage(
        pct, False, s.get("mastery_boss", 0), s.get("mastery_normal", 0),
        maple_ratio=s.get("maple_ratio", 0.0),
    )


# ---- Status/KO engine pass 2: the damage skills' casts (weight of one cast = its boss damage before any timing factor) ----
if status_on:
    def _percast(key):
        if not unlocked(key):
            return 0.0
        sk = DAMAGE_SKILLS[key]
        hits = sk["hits"] * (ticks(capped_window(sk["window"]), sk["icd"]) if sk.get("icd") else 1)
        return hits * skill_hit(key, sk) * branch_multipliers(sk.get("mastery_boss", 0), sk.get("mastery_normal", 0), sk["targets"])[0]
    _c_slot = BLAST_HITS * blast_hit * branch_multipliers(blast_mastery_boss_damage, 0, blast_targets)[0]
    _groups = []
    for _gid, _cast, _ents in STATUS_GROUPS:
        _entries = []
        for _row, _typ, _win, _gate, _wk in _ents:
            _w = _percast(_wk)
            if _gate and not unlocked(_gate):
                _w = 0.0
            _entries.append(dict(row=_row, typ=_typ, w=_w, L=(capped_window(DAMAGE_SKILLS[_win]["window"]) if _win else 1),
                                 on=(1 if (not _gate or unlocked(_gate)) else 0)))
        _groups.append(dict(id=_gid, cd=eff_cooldown(DAMAGE_SKILLS[_cast]["cooldown"], DAMAGE_SKILLS[_cast]["costs_action"]),
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
cast_rate = cast_rate_with(ENGINE_N)
blast_per_second = max(0, actions_per_second - cast_rate)

# ---- Blast (basic attack) DPS ----
blast_dps = (blend_branches("BLAST", BLAST_HITS * blast_hit * blast_per_second, blast_mastery_boss_damage, 0, blast_targets)
             if unlocked("BLAST") else 0.0)

skill_dps = {}
for key, s in DAMAGE_SKILLS.items():
    if not unlocked(key):
        skill_dps[key] = 0.0
        continue
    hd = skill_hit(key, s)
    proc_prob = 1.0
    eff_cd = eff_cooldown(s["cooldown"], s["costs_action"], exempt=key in CDR_EXEMPT)
    if status_on and key in ENGINE_N:
        # engine casts: a DoT row's hits = hits per full window x effective casts (last window truncated at the fight end)
        _per_cast = s["hits"] * (ticks(capped_window(s["window"]), s["icd"]) if s.get("icd") else 1)
        rate = _per_cast * (E_FS[key] if key in STATUS_FS_KEYS else ENGINE_N[key]) / fight_duration
    elif fixed_duration_active:
        rate = non_buff_total_hits(eff_cd, s["hits"], s.get("icd"), s.get("window")) / fight_duration
    else:
        hits = s["hits"] * (ticks(capped_window(s["window"]), s["icd"]) if s.get("icd") else 1)
        rate = hits / eff_cd
    skill_dps[key] = blend_branches(key, proc_prob * rate * hd, s.get("mastery_boss", 0), s.get("mastery_normal", 0), s["targets"])

total_dps = blast_dps + sum(skill_dps.values())

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
    basic_b, basic_n = _BRANCH_PAIRS.get("BLAST", (0.0, 0.0))
    _hpr_full = hp_recovery_pct
    _co_full = COMBAT_ORDERS_ATTACK_PCT if (unlocked("COMBAT_ORDERS") and level >= 82) else 0.0
    _fdpart = 1 + (final_damage + divine_shield_avg + (guardian_pct if unlocked("GUARDIAN") else 0.0)
                   + (divine_blessing_pct if unlocked("DIVINE_BLESSING") else 0.0) + greater_vessel_avg) / 100
    _boss_pct = boss_damage + monster_dmg_bonus
    _norm_pct = normal_damage + monster_dmg_bonus
    comp_host = dict(
        mt=monster_type, T=fight_duration, content=content_type, pvp_len=PVP_FIGHT_DURATION, cap=max_enemies_hit, w=normal_weight,
        unit=hit_damage(100.0, True, 0, 0) / 100,
        bad=basic_attack_damage, sd=skill_damage, aps=actions_per_second,
        avgbuff=attack_bucket_mult * (1 + (final_damage + final_damage_extra) / 100), attack_bucket_avg=attack_bucket_sum,
        charm_val=0.0, agg_damage_avg=0.0, hex_avg=0.0, hex_snap=lambda st: 0.0,
        avgbuff_snap=lambda charm, extra: (1 + (vessel_of_light_avg + _hpr_full + _co_full + charm + extra) / 100) * _fdpart,
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
print()
solution = _get_solution()

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

if status_on:
    # the engine strip itself: cast counts and timing factors against the Python reference
    for _row, _pfx in STATUS_CAST_PREFIX.items():
        if _row in DAMAGE_SKILLS and not DAMAGE_SKILLS[_row]["costs_action"]:
            continue
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
