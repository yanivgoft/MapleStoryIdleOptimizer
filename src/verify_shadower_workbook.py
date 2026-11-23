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
import os
import re
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
XLSX_PATH = REPO / "Shadower" / "Shadower-DPS-Calculator.xlsx"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_shadower_workbook import ROW, IN, UNLOCK_LEVEL, MAPLE_HERO_SHADOWER_RATIOS, R_TOTAL, CONTENT_TYPES  # noqa: E402
from build_shadower_workbook import STATUS_CAST_PREFIX, STATUS_GROUPS, STATUS_BUFFS, STATUS_UNIFORM_ROWS, STATUS_PHI_ROWS, STATUS_FS_KEYS, STATUS_MAIN_LAYOUT  # noqa: E402
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
flat_luk, luk_pct, dex = _in("flat_luk"), _in("luk_pct"), _in("dex")
stat_damage = (flat_luk * (1 + luk_pct / 100)) * 0.01 + dex * 0.0025
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
incoming_hit_rate = _in("incoming_hit_rate")


fixed_duration_active = monster_type != "pvp" and fight_duration > 0

basic_lvl = input_level(4, level, skill1, skill2, skill3, skill4, skill_all)
skill_coefficient_base = 290 * get_factor(basic_lvl, 21) / 1000
print(f"SKILL_COEFFICIENT (base) = {skill_coefficient_base:.4f}")


def level_gated_sum(pairs):
    return sum(inc for lvl, inc in pairs.items() if level >= lvl)


cruel_stab_mastery = level_gated_sum({102: 10, 106: 11, 116: 12, 120: 13, 128: 14, 132: 15})
cruel_stab_boss_mastery = level_gated_sum({111: 10, 124: 10})
cruel_stab_hits = 6 if level >= 136 else 5

dark_flare_cooldown = (45 * 0.7) if level >= 94 else 45
dark_flare_hits = 3 if level >= 78 else 2
dark_flare_icd = (2 * 0.75) if level >= 104 else 2
bm_target_mult = 3 if level >= 138 else (2 if level >= 122 else 1)


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


CDR_EXEMPT = {"VENOM"}  # mirrors the build script (rate-surrogate cooldown)


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


def exact_buff_uptime(cooldown, buff_duration, casts=None):
    casts = exact_casts(cooldown) if casts is None else casts
    remaining_after_last = max(0.0, fight_duration - (casts - 1) * cooldown)
    last_uptime = min(buff_duration, remaining_after_last)
    return (casts - 1) * min(buff_duration, cooldown) + last_uptime


def coeff_pct(base, fidx, scales, job_step):
    lvl = input_level(job_step, level, skill1, skill2, skill3, skill4, skill_all)
    if not scales:
        return base / 10
    return (base / 10) * (get_factor(lvl, fidx) / 1000)


def buff_uptime(cooldown, duration, casts=None):
    """Uptime of a cast buff.  `casts` = the Status/KO engine's cast count of that buff (Calc!R is overridden by it with the engine on); None = the averaged model's own count."""
    cd = eff_cooldown(cooldown, True)   # CDR applies to every cooldown
    scaled = eff_duration(duration)
    if fixed_duration_active:
        return exact_buff_uptime(cd, scaled, casts) / fight_duration
    if monster_type == "pvp":
        return min(scaled, PVP_FIGHT_DURATION) / PVP_FIGHT_DURATION
    return min(1.0, scaled / cd)


# ---- Buffs (rows of the Skills sheet; cast rows cost an action slot) ----
dark_sight_duration = 12 if level >= 24 else 8
BUFFS = {
    "NIMBLE_FEET": dict(job_step=1, cooldown=60, duration=15, base=150, fidx=0, scales=False, costs_action=True, actions_per_cast=1),
    "DARK_SIGHT_CRIT": dict(job_step=1, cooldown=25, duration=dark_sight_duration, base=60, fidx=21, scales=True, costs_action=False, actions_per_cast=1),
    "DARK_SIGHT_ATK": dict(job_step=1, cooldown=25, duration=dark_sight_duration, base=100, fidx=21, scales=True, costs_action=True, actions_per_cast=2),
    "INTO_DARKNESS": dict(job_step=3, cooldown=40, duration=13, base=200, fidx=21, scales=True, costs_action=True, actions_per_cast=1),
    "SMOKESCREEN": dict(job_step=4, cooldown=45, duration=20, base=130, fidx=22, scales=True, costs_action=True, actions_per_cast=1),
}


def buff_pct(key):
    b = BUFFS[key]
    return coeff_pct(b["base"], b["fidx"], b["scales"], b["job_step"]) if unlocked(key) else 0.0


dsc_pct, dsa_pct, id_pct, ss_pct = buff_pct("DARK_SIGHT_CRIT"), buff_pct("DARK_SIGHT_ATK"), buff_pct("INTO_DARKNESS"), buff_pct("SMOKESCREEN")

# ---- Nimble Feet / Steal / Meso Mastery / Actions per second (none of them is engine-timed) ----
nimble_feet_avg = buff_pct("NIMBLE_FEET") * buff_uptime(60, 15) if unlocked("NIMBLE_FEET") else 0.0
as_bonus = nimble_feet_avg
actions_per_second = 1 + min(150, 150 * (1 - (1 - attack_speed_base / 150) * (1 - as_bonus / 150))) / 100
steal_pct = coeff_pct(50, 22, True, 2) if unlocked("STEAL") else 0.0
steal_avg = steal_pct * 3 if unlocked("STEAL") else 0.0
meso_mastery_avg = (25.0 * (1 - math.exp(-0.75 * actions_per_second * 5))) if unlocked("MESO_MASTERY") else 0.0

# ---- Maple Hero (Shadower), Shadow Partner ----
maple_hero_pct = coeff_pct(150, 23, True, 4) if unlocked("MAPLE_HERO_SHADOWER") else 0.0
sp_pct = coeff_pct(600, 21, True, 3) * (1 + level_gated_sum({68: 100}) / 100) if unlocked("SHADOW_PARTNER") else 0.0
sp_maple_ratio = MAPLE_HERO_SHADOWER_RATIOS["SHADOW_PARTNER"]
sp_pct_with_maple = sp_pct * (1 + sp_maple_ratio * maple_hero_pct / 100)
shadow_partner_mult = 1 + (sp_pct_with_maple * 1.0 * 25 / 100) / 100 if unlocked("SHADOW_PARTNER") else 1.0

# ---- Skill definitions: coefficient % (mastery MULTIPLIES), hits per cast, window / ICD, targets, boss/normal masteries ----
meso_chance = 0.75 if level >= 75 else 0.5
meso_stack_avg = min(10, meso_chance * actions_per_second * eff_cooldown(11, True))
bm_stack_avg = min(5, 0.5 * meso_chance * actions_per_second * eff_cooldown(11, True))
assassinate_eff_cd = eff_cooldown(13, True)
assassinate_rate_q = 1 / assassinate_eff_cd
bm_rate_q = 1 / eff_cooldown(11, True)
murderous_intent_mult = 1 + min(1, (bm_rate_q * 2) / assassinate_rate_q) if unlocked("ASSASSINATE") and unlocked("BLOOD_MONEY") else (1.0 if unlocked("ASSASSINATE") else 0.0)
asn_pct = ((coeff_pct(14000, 12, True, 4) + (50 if level >= 134 else 0)) + 0.5 * coeff_pct(30000, 12, True, 4) * murderous_intent_mult) if unlocked("ASSASSINATE") else 0.0

DAMAGE_SKILLS = {
    "PHASE_DASH": dict(cooldown=23, hits=2, pct=coeff_pct(4500, 12, True, 3) * (1 + level_gated_sum({73: 80}) / 100), costs_action=True, targets=9),
    "MESO_EXPLOSION": dict(cooldown=11, hits=3, pct=coeff_pct(2700, 12, True, 3) * (1 + level_gated_sum({90: 100}) / 100), costs_action=True, targets=meso_stack_avg),
    "BLOOD_MONEY": dict(cooldown=11, hits=3, pct=coeff_pct(36000, 12, True, 4) * (1 + level_gated_sum({122: 50, 138: 50}) / 100), costs_action=False,
                        targets=bm_stack_avg * bm_target_mult),
    "DARK_FLARE": dict(cooldown=dark_flare_cooldown, hits=dark_flare_hits, icd=dark_flare_icd, window=20, pct=coeff_pct(3300, 12, True, 3), costs_action=True, targets=8),
    "VENOM": dict(cooldown=1, hits=1, pct=coeff_pct(450, 21, True, 3), costs_action=False, targets=1),
    "ASSASSINATE": dict(cooldown=13, hits=2, pct=asn_pct, costs_action=True, targets=1),
    "SUDDEN_RAID_BURST": dict(cooldown=19, hits=3, pct=coeff_pct(14000, 12, True, 4) * (1 + level_gated_sum({126: 50}) / 100), costs_action=True, targets=8),
    "SUDDEN_RAID_DOT": dict(cooldown=19, hits=1, icd=1, window=5, pct=coeff_pct(3600, 12, True, 4), costs_action=False, targets=8),
}
for _k, _s in DAMAGE_SKILLS.items():
    _s.setdefault("mastery_boss", 0.0)
    _s.setdefault("mastery_normal", 0.0)
    _s["maple_ratio"] = MAPLE_HERO_SHADOWER_RATIOS.get(_k, 0.0)
CRUEL_STAB_TARGETS = 6 + basic_attack_target_increase
TRIGGERS_TOXIC_VENOM = {"CRUEL_STAB", "MESO_EXPLOSION", "PHASE_DASH", "DARK_FLARE", "ASSASSINATE", "SUDDEN_RAID_BURST", "SUDDEN_RAID_DOT", "BLOOD_MONEY"}

_BRANCH_PAIRS = {}   # key -> (boss DPS, normal DPS) of the last branch_pair call (companion host: player boss / normal DPS of every row)


def branch_pair(key, rate_boss, rate_normal, hd_, mastery_boss, mastery_normal, targets):
    """Boss and normal DPS of one row (before weighting): rate x hit x its own branch multiplier x the row's timing factor (Status Effect Damage / KO
    engine).  Each branch gets its own full (1+damage%/100)*target_count treatment; the two are blended into the real Total DPS by the time weight w
    (a plain dollar blend - correct for the real Total DPS), while Sensitivity's marginal-value ranking uses a separate ratio-based blend (Excel side
    only).  PvP is single-enemy with neither bonus."""
    fb, fn = timing_factors(key)
    if monster_type == "pvp":
        b, n = 1.0, 1.0
    else:
        b = 1 + (boss_damage + mastery_boss + monster_dmg_bonus) / 100
        n = (1 + (normal_damage + mastery_normal + monster_dmg_bonus) / 100) * min(targets, max_enemies_hit)
    pair = (rate_boss * hd_ * b * fb, rate_normal * hd_ * n * fn)
    _BRANCH_PAIRS[key] = pair
    return pair


def blended(pair):
    return (1 - normal_weight) * pair[0] + normal_weight * pair[1]


def target_count_mult(targets):
    """Damage%-FREE target-count blend for hit-count / proc-trigger rates (Toxic Venom rolls once per target hit)."""
    if monster_type == "pvp":
        return 1
    return (1 - normal_weight) + normal_weight * min(targets, max_enemies_hit)


# ---------------------------------------------------------------------------------------------------------------
# Status Effect Damage / KO timeline engine (src/status_timeline.py `solve`, the plain-Python reference): fixed-length single-target content with KO phases
# (World Boss, Enhancement Dungeon) or any stun/freeze (companion or the player's own Phase Dash).  The player casts Dark Sight (Attack), Into Darkness and
# Smokescreen and the cooldown skills when they pay most; Steal / Meso Mastery / Nimble Feet / Shadow Partner / Venom's Weaken keep their averaged formulas.
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
# The player's own stunning skill (game table): Phase Dash stuns for 2 s (cooldown 23 s, no Reuse mastery), cast on cooldown from the start.
PLAYER_STUN = [
    dict(id="DASH", key="PHASE_DASH", typ="cast", dur=2.0, p=1.0, cd=23, min_level=0, tick=1.0, win=0.0),
]
_pl_on = any(unlocked(e["key"]) and level >= e["min_level"] for e in PLAYER_STUN)
# The workbook's effective Companion Summoning Time Increase is the Inputs value + Arwen's Glass Shoes (+20% star 0 .. +40% star 5, Artifacts row
# arwens_glass_shoes_summon_time_increase_pct).  The verify run clears the artifact slots, so the artifact term is 0 in every cpm.run below; it is
# covered by the equivalence test (artifact at Inputs x == no artifact at Inputs x + star value, tests/golden/shadower_artifact_cases.py EQUIV_PAIRS).
_stun_in0 = _companion_choice0 != "None" and c_level0 >= 1
hasstun = (_stun_in0 and bool(cpm.run(_stub, _companion_choice0, c_level0, _in("companion_summon_time_increase_pct")).get("hasstun"))) or _pl_on
KO_WINDOWS = {"World Boss": [(24, 34), (59, 69)], "Enhancement Dungeon": [(fight_duration - 4.5, fight_duration)]}
status_on = fixed_duration_active and normal_weight == 0 and (content_type in KO_WINDOWS or hasstun)
# the stun skill's first cast: t=0 with the engine on, otherwise after the buff-casting startup (Nimble Feet + Dark Sight + Into Darkness + Smokescreen), like Summary's startup cell
_startup_plain = (sum(1 for k in BUFFS if BUFFS[k]["costs_action"] and unlocked(k)) / actions_per_second) if fixed_duration_active else 0.0
_t0_pl = 0.0 if status_on else _startup_plain
PST = [dict(id=e["id"], typ=e["typ"], cd=eff_cooldown(e["cd"], True), dur=e["dur"], p=e["p"], on=unlocked(e["key"]) and level >= e["min_level"],
            t0=_t0_pl, tick=e["tick"], win=e["win"]) for e in PLAYER_STUN]
_stub["pst"] = PST
stun_info = cpm.run(_stub, _companion_choice0 if _stun_in0 else "None", c_level0, _in("companion_summon_time_increase_pct"))
stf_b = stun_info["stunfracB"]
stf_n = stun_info["stunfracN"]
E_ENGINE = None
ENGINE_N = {}
engine_bbuff_mean = None
if status_on:
    # companion stun windows (none when no companion stuns and no player stun exists: the mirror then returns no stun_vector) + the player's own
    _comp_stun = stun_info["stun_vector"](stl.NB_MAX) if "stun_vector" in stun_info else [0.0] * stl.NB_MAX
    _stun_vec = [min(1.0, a + b) for a, b in zip(_comp_stun, stl.pl_stun_vector([dict(e, t0=0.0) for e in PST], fight_duration, stl.NB_MAX))]
    _ds_dur = BUFFS["DARK_SIGHT_ATK"]["duration"] * (1 + buff_duration_increase_pct / 100)
    _ds_cd = eff_cooldown(BUFFS["DARK_SIGHT_ATK"]["cooldown"], True)
    _id_dur = BUFFS["INTO_DARKNESS"]["duration"] * (1 + buff_duration_increase_pct / 100)
    _id_cd = eff_cooldown(BUFFS["INTO_DARKNESS"]["cooldown"], True)
    _ss_dur = BUFFS["SMOKESCREEN"]["duration"] * (1 + buff_duration_increase_pct / 100)
    _ss_cd = eff_cooldown(BUFFS["SMOKESCREEN"]["cooldown"], True)
    # Smokescreen's strip effect carries Into Darkness's steady-state average (mean-field cross term, see fd_cross_scale in the builder)
    _cross = 1 + (id_pct * min(1.0, _id_dur / _id_cd) / 100 if unlocked("INTO_DARKNESS") else 0.0)
    _buffs = [dict(id="DS", kind="atk", F=dsa_pct, dur=_ds_dur, cd=_ds_cd, on=unlocked("DARK_SIGHT_ATK")),
              dict(id="ID", kind="ramp", F=id_pct, dur=min(_id_dur, _id_cd), cd=_id_cd, on=unlocked("INTO_DARKNESS"), p0=1, p1=1, ramp_t=1, dur0=1),
              dict(id="SS", kind="ramp", F=ss_pct * _cross, dur=min(_ss_dur, _ss_cd), cd=_ss_cd, on=unlocked("SMOKESCREEN"), p0=1, p1=1, ramp_t=1, dur0=1)]
    _eng_host = dict(T=fight_duration, S=status_effect_damage, ko=KO_WINDOWS.get(content_type, []), hex_v=0.0, hex_period=20, hex_max=3,
                     A0=steal_avg + meso_mastery_avg, charm_v=0.0, hex_avg=0.0, c_slot=0.0, stun=_stun_vec, buffs=_buffs, groups=[])
    _e1 = stl.solve(_eng_host)               # pass 1: the buff schedule (independent of the skill weights)
    engine_bbuff_mean = _e1["Bbuff_mean"]
    for _row, _pfx in STATUS_CAST_PREFIX.items():
        if _pfx.startswith("buff."):
            ENGINE_N[_row] = _e1["buffs"][_pfx[5:]]["n"]

# ---------------------------------------------------------------------------
# Global helper bonuses (mirrors Summary!R_CRIT_RATE_BONUS / R_MONSTER_DMG_BONUS / R_CRIT_DAMAGE_BONUS / R_AVGBUFF / R_SHADOW_PARTNER_MULT).
# With the engine on, the buff rows' uptimes use the engine's cast counts (Calc!R).
# ---------------------------------------------------------------------------
dark_sight_crit_avg = dsc_pct * buff_uptime(25, dark_sight_duration, casts=ENGINE_N.get("DARK_SIGHT_CRIT")) if unlocked("DARK_SIGHT_CRIT") else 0.0
dark_sight_atk_avg = dsa_pct * buff_uptime(25, dark_sight_duration, casts=ENGINE_N.get("DARK_SIGHT_ATK")) if unlocked("DARK_SIGHT_ATK") else 0.0
into_darkness_avg = id_pct * buff_uptime(40, 13, casts=ENGINE_N.get("INTO_DARKNESS")) if unlocked("INTO_DARKNESS") else 0.0
smokescreen_avg = ss_pct * buff_uptime(45, 20, casts=ENGINE_N.get("SMOKESCREEN")) if unlocked("SMOKESCREEN") else 0.0
crit_rate_bonus = dark_sight_crit_avg
monster_dmg_bonus = 15 if level >= 82 else 0
crit_damage_bonus = (30 * buff_uptime(45, 20, casts=ENGINE_N.get("SMOKESCREEN"))) if level >= 113 else 0.0

if status_on:
    avg_buff_mult = engine_bbuff_mean
else:
    avg_buff_mult = (1 + (dark_sight_atk_avg + steal_avg + meso_mastery_avg) / 100) * (1 + into_darkness_avg / 100) * (1 + smokescreen_avg / 100)

# Buff-Casting Startup Delay: in fixed-duration fights, the character casts every currently-unlocked, actively-cast buff sequentially at fight start
# (1/APS seconds each) before their first damage-skill cast.  With the engine on the buffs are cast when they pay: no start-up delay.
STARTUP_BUFF_KEYS = {"INTO_DARKNESS", "SMOKESCREEN", "NIMBLE_FEET", "DARK_SIGHT_ATK"}
if fixed_duration_active and not status_on:
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


def hit_damage(coeff_pct_val, is_basic, maple_ratio=0.0):
    """Expected damage of one hit at coefficient % `coeff_pct_val` (masteries are already multiplied into it).  Boss/Normal Monster Damage% is applied by the caller."""
    base_damage = attack * (coeff_pct_val / 100)
    dmg_reduction = 5000 / (6000 + monster_defense * (1 - def_pen / 100))
    maple_mult = (1 + maple_ratio * maple_hero_pct / 100) if maple_ratio else 1.0
    final_mult = (1 + final_damage / 100) * maple_mult
    source_pct = basic_attack_damage if is_basic else skill_damage
    extra_mult = avg_buff_mult * shadow_partner_mult
    base_hit = (
        base_damage * (1 + stat_damage / 100) * (1 + damage / 100)
        * (1 + damage_amp / 100) * dmg_reduction * final_mult * (1 + source_pct / 100) * extra_mult
    )
    non_crit_min = base_hit * min(min_damage, max_damage) / 100
    non_crit_max = base_hit * max_damage / 100
    non_crit_avg = (non_crit_min + non_crit_max) / 2
    crit_avg = non_crit_avg * (1 + (crit_damage + crit_damage_bonus) / 100)
    cr = min(crit_rate + crit_rate_bonus, 100) / 100
    return non_crit_avg * (1 - cr) + crit_avg * cr


# ---- Status/KO engine pass 2: the skills' casts.  Weight of one cast = its boss damage before any timing factor (hits x expected hit x boss multiplier).
PHI_ROWS = {}
PHI_UNIF = 1.0
E_FS = {}
cruel_stab_pct = skill_coefficient_base * (1 + cruel_stab_mastery / 100)
cruel_stab_hit = hit_damage(cruel_stab_pct, True)
if status_on:
    def _percast(key):
        if not unlocked(key):
            return 0.0
        sk = DAMAGE_SKILLS[key]
        hd = hit_damage(sk["pct"], False, sk["maple_ratio"])
        hits = sk["hits"] * (ticks(capped_window(sk["window"]), sk["icd"]) if sk.get("icd") else 1)
        b_mult = 1.0 if monster_type == "pvp" else 1 + (boss_damage + sk["mastery_boss"] + monster_dmg_bonus) / 100
        return hits * hd * b_mult
    _c_slot = (cruel_stab_hits * cruel_stab_hit * (1.0 if monster_type == "pvp" else 1 + (boss_damage + cruel_stab_boss_mastery + monster_dmg_bonus) / 100)
               if unlocked("CRUEL_STAB") else 0.0)
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


# ---- Cast rate (subtracted from Cruel Stab): every action-costing row, weighted by ActionsPerCast; engine on: the engine's cast counts ----
if fixed_duration_active:
    cast_rate = sum(
        BUFFS[k]["actions_per_cast"] * (ENGINE_N[k] if k in ENGINE_N else exact_casts(eff_cooldown(BUFFS[k]["cooldown"], BUFFS[k]["costs_action"])))
        for k in BUFFS if BUFFS[k]["costs_action"] and unlocked(k)
    )
    cast_rate += sum(
        (ENGINE_N[k] if k in ENGINE_N else non_buff_casts(eff_cooldown(DAMAGE_SKILLS[k]["cooldown"], DAMAGE_SKILLS[k]["costs_action"])))
        for k in DAMAGE_SKILLS if DAMAGE_SKILLS[k]["costs_action"] and unlocked(k)
    )
    cast_rate /= fight_duration
else:
    cast_rate = sum(
        BUFFS[k]["actions_per_cast"] / eff_cooldown(BUFFS[k]["cooldown"], BUFFS[k]["costs_action"])
        for k in BUFFS if BUFFS[k]["costs_action"] and unlocked(k)
    )
    cast_rate += sum(
        1 / eff_cooldown(DAMAGE_SKILLS[k]["cooldown"], DAMAGE_SKILLS[k]["costs_action"])
        for k in DAMAGE_SKILLS if DAMAGE_SKILLS[k]["costs_action"] and unlocked(k)
    )
cruel_stab_per_second = max(0, actions_per_second - cast_rate)

skill_dps = {}
hit_rate = {}  # per-skill attacks/sec landing damage (target-multiplied), feeds Toxic Venom

cs_pair = branch_pair("CRUEL_STAB", cruel_stab_per_second, cruel_stab_per_second, cruel_stab_hits * cruel_stab_hit, cruel_stab_boss_mastery, 0.0, CRUEL_STAB_TARGETS)
if not unlocked("CRUEL_STAB"):
    _BRANCH_PAIRS["CRUEL_STAB"] = (0.0, 0.0)
cruel_stab_dps = blended(_BRANCH_PAIRS["CRUEL_STAB"])
skill_dps["CRUEL_STAB"] = cruel_stab_dps
hit_rate["CRUEL_STAB"] = cruel_stab_per_second * target_count_mult(CRUEL_STAB_TARGETS) if unlocked("CRUEL_STAB") else 0.0

for key, s in DAMAGE_SKILLS.items():
    if not unlocked(key):
        skill_dps[key] = 0.0
        hit_rate[key] = 0.0
        _BRANCH_PAIRS[key] = (0.0, 0.0)
        continue
    hd = hit_damage(s["pct"], False, s["maple_ratio"])
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
    pb_, pn_ = branch_pair(key, rate, rate, hd, s["mastery_boss"], s["mastery_normal"], s["targets"])
    skill_dps[key] = blended((pb_, pn_))
    hit_rate[key] = rate / s["hits"] * target_count_mult(s["targets"])   # proc rolls: once per attack per enemy hit, not per damage line

# ---- Toxic Venom: no ICD; trigger rate = combined per-second hit rate (already target-multiplied) of every triggering row ----
if unlocked("TOXIC_VENOM"):
    total_hit_rate = sum(hit_rate[k] for k in TRIGGERS_TOXIC_VENOM)
    toxic_venom_pct = coeff_pct(6000, 21, True, 4) * (1 + level_gated_sum({130: 100}) / 100)
    toxic_hd = hit_damage(toxic_venom_pct, False)
    skill_dps["TOXIC_VENOM"] = blended(branch_pair("TOXIC_VENOM", 0.2 * total_hit_rate, 0.2 * total_hit_rate, toxic_hd, 0.0, 0.0, 1))
else:
    skill_dps["TOXIC_VENOM"] = 0.0
    _BRANCH_PAIRS["TOXIC_VENOM"] = (0.0, 0.0)

# ---- Shadow Shifter: counterattack driven by incoming_hit_rate ----
if unlocked("SHADOW_SHIFTER"):
    ss_counter_pct = coeff_pct(25000, 21, True, 4)
    ss_hd = hit_damage(ss_counter_pct, False)
    skill_dps["SHADOW_SHIFTER"] = blended(branch_pair("SHADOW_SHIFTER", incoming_hit_rate * 0.2, incoming_hit_rate * 0.2, ss_hd, 0.0, 0.0, 1))
else:
    skill_dps["SHADOW_SHIFTER"] = 0.0
    _BRANCH_PAIRS["SHADOW_SHIFTER"] = (0.0, 0.0)

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
    pb_total = sum(p[0] for p in _BRANCH_PAIRS.values())
    pn_total = sum(p[1] for p in _BRANCH_PAIRS.values())
    pu_total = sum(_BRANCH_PAIRS[k][0] for k in STATUS_UNIFORM_ROWS)
    basic_b, basic_n = _BRANCH_PAIRS["CRUEL_STAB"]
    boss_pct_c = boss_damage + monster_dmg_bonus
    norm_pct_c = normal_damage + monster_dmg_bonus
    _fdpart = (1 + id_pct / 100) * (1 + ss_pct / 100)
    _ds_full = dsa_pct
    _atk_bucket_avg = dark_sight_atk_avg + steal_avg + meso_mastery_avg
    comp_host = dict(
        mt=monster_type, T=fight_duration, content=content_type, pvp_len=PVP_FIGHT_DURATION, cap=max_enemies_hit, w=normal_weight,
        unit=hit_damage(100.0, True) / 100 / shadow_partner_mult,
        bad=basic_attack_damage, sd=skill_damage, aps=actions_per_second,
        avgbuff=avg_buff_mult, attack_bucket_avg=_atk_bucket_avg,
        charm_val=0.0, agg_damage_avg=0.0, hex_avg=0.0, hex_snap=lambda st: 0.0,
        avgbuff_snap=lambda charm, extra: (1 + (_ds_full + steal_avg + meso_mastery_avg + charm + extra) / 100) * _fdpart,
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
    _base = sum(skill_dps.values())
    for _name in cpm.ck.COMPANIONS_ORDER:
        _r = cpm.run(_hb, _name, 10, _in("companion_summon_time_increase_pct"))
        print(f"  [compare Lv10] {_name:14s} blend DPS {_r['comp_blend_dps']:.4e}  = +{_r['comp_blend_dps'] / _base * 100:6.2f}% of player total (s={_r['s']:.1f}, W={_r['W']:.1f})")

total_dps = sum(skill_dps.values()) + companion_dps

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
    if k == "CRUEL_STAB":
        continue
    print(f"  {k:28s} DPS = {v:.4f}")
print(f"TOTAL DPS = {total_dps:.4f}")

# ---------------------------------------------------------------------------
# Cross-check against the actual live workbook (evaluated with `formulas`, not just the static values openpyxl wrote)
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
