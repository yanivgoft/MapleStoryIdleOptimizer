#!/usr/bin/env python3
"""
Cross-checks Corsair-DPS-Calculator.xlsx against an independent Python port of the same logic,
using the workbook's own default Inputs values. Then loads the live workbook with the `formulas`
package and diffs Total DPS + every per-skill DPS cell (Calc!O<row>) against this script's
independent numbers. Mirrors verify_buccaneer_workbook.py in structure and method.
"""
import json
import math
import re
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
XLSX_PATH = REPO / "Corsair" / "Corsair-DPS-Calculator.xlsx"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_corsair_workbook import ROW, IN, UNLOCK_LEVEL, MAPLE_HERO_RATIOS, AHOY_MATEYS_RATIOS, R_TOTAL, R_BAPS  # noqa: E402

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
flat_dex, dex_pct, str_stat = _in("flat_dex"), _in("dex_pct"), _in("str")
stat_damage = (flat_dex * (1 + dex_pct / 100)) * 0.01 + str_stat * 0.0025
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
        uptime = eff_duration(duration) / eff_cd
    return pct * uptime


def target_multiplier(targets):
    if monster_type == "pvp":
        return 1
    targets = min(targets, max_enemies_hit)
    return (1 - normal_weight) * 1 + normal_weight * targets


def monster_blend(boss_val, normal_val):
    if monster_type == "pvp":
        return boss_val
    return (1 - normal_weight) * boss_val + normal_weight * normal_val


def coeff_pct(base, fidx, scales, job_step):
    lvl = input_level(job_step, level, skill1, skill2, skill3, skill4, skill_all)
    if not scales:
        return base / 10
    return (base / 10) * (get_factor(lvl, fidx) / 1000)


# ---- Maple Hero (real/confirmed level-1 anchors: Siege Bomber 20%, Blackboot Bill 40%, Swift
#      Fire 80% — only the growth curve shape is a FLAGGED ASSUMPTION) + Ahoy Mateys (a SEPARATE
#      helper, +250%/+100% FD to Scurvy Summons/All Aboard) ----
maple_hero_pct = coeff_pct(200, 23, True, 4) if unlocked("MAPLE_HERO_HELPER") else 0.0
ahoy_mateys_pct = coeff_pct(2500, 22, True, 4) if unlocked("AHOY_MATEYS_HELPER") else 0.0

# ---- Actions Per Second — no live AS-buff source in this kit (no Nimble-Feet-equivalent),
#      same as Buccaneer ----
actions_per_second = 1 + min(150, 150 * (attack_speed_base / 150)) / 100

# Buff-Casting Startup Delay: Corsair has no recast-able buff skills (no BUFFS-equivalent dict
# exists in this model — Roll of the Dice's dice component is an always-active flat
# approximation, not a timed recast), so this is always 0 — kept for architectural consistency
# with the other 11 classes' identical wiring.
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


# ---- Basic attack (Eight-Legs Easton) ----
eight_legs_easton_targets = 6 + basic_attack_target_increase
EIGHT_LEGS_EASTON_HITS = 6 if level >= 136 else 5
eight_legs_easton_mastery_damage = level_gated_sum({102: 10, 106: 1, 116: 1, 120: 1, 128: 1, 132: 1})
eight_legs_easton_mastery_boss_damage = level_gated_sum({111: 10, 124: 10})
eight_legs_easton_pct = skill_coefficient_base + eight_legs_easton_mastery_damage

# ---- Cast rate (subtracted from Eight-Legs Easton) — action-costing skills only ----
COST_ACTION_ROWS = [
    ("SWIFT_FIRE", 18, True, 1),
    ("SCURVY_SUMMONS", 20, True, 1),
    ("BLACKBOOT_BILL", 20, True, 1),
    ("SIEGE_BOMBER", 30, True, 1),
    ("BRAIN_SCRAMBLER", 15, True, 1),
    ("NAUTILUS_STRIKE", 45, True, 1),
    ("RAPID_FIRE", 17, True, 1),
    ("BROADSIDE_BURST", 30, True, 1),
]
if fixed_duration_active:
    cast_rate = sum(non_buff_casts(eff_cooldown(cd, ca)) * aps for k, cd, ca, aps in COST_ACTION_ROWS if ca and unlocked(k)) / fight_duration
else:
    cast_rate = sum((1 / eff_cooldown(cd, ca)) * aps for k, cd, ca, aps in COST_ACTION_ROWS if ca and unlocked(k))
eight_legs_easton_per_second = max(0, actions_per_second - cast_rate)

# ---- Global Final Damage bucket: Jolly Roger only (always-active once unlocked, no cooldown known) ----
jolly_roger_pct = coeff_pct(150, 22, True, 4) if unlocked("JOLLY_ROGER_FD") else 0.0
final_damage_extra = jolly_roger_pct

# ---- Attack% bucket: Roll of the Dice's dice component only (shared verbatim w/ Buccaneer) ----
roll_of_dice_pct = coeff_pct(25, 0, False, 3) if unlocked("ROLL_OF_THE_DICE_DICE") else 0.0
attack_bucket_mult = 1 + roll_of_dice_pct / 100

crit_rate_bonus = 0.0
crit_damage_bonus = 0.0
monster_dmg_bonus = 0.0


def hit_damage(coeff_pct_val, is_basic, mastery_boss, mastery_normal, maple_ratio=0.0, ahoy_ratio=0.0):
    base_damage = attack * (coeff_pct_val / 100)
    dmg_reduction = 5000 / (6000 + monster_defense * (1 - def_pen / 100))
    boss_term = boss_damage + mastery_boss + monster_dmg_bonus
    normal_term = normal_damage + mastery_normal + monster_dmg_bonus
    monster_dmg = 0 if monster_type == "pvp" else monster_blend(boss_term, normal_term)
    helper_mult = 1.0
    if maple_ratio:
        helper_mult *= (1 + maple_ratio * maple_hero_pct / 100)
    if ahoy_ratio:
        helper_mult *= (1 + ahoy_ratio * ahoy_mateys_pct / 100)
    final_mult = (1 + (final_damage + final_damage_extra) / 100) * helper_mult
    source_pct = basic_attack_damage if is_basic else skill_damage
    base_hit = (
        base_damage * (1 + stat_damage / 100) * (1 + damage / 100) * (1 + monster_dmg / 100)
        * (1 + damage_amp / 100) * dmg_reduction * final_mult * (1 + source_pct / 100)
        * attack_bucket_mult
    )
    non_crit_min = base_hit * min(min_damage, max_damage) / 100
    non_crit_max = base_hit * max_damage / 100
    non_crit_avg = (non_crit_min + non_crit_max) / 2
    crit_avg = non_crit_avg * (1 + (crit_damage + crit_damage_bonus) / 100)
    cr = min(crit_rate + crit_rate_bonus, 100) / 100
    return non_crit_avg * (1 - cr) + crit_avg * cr


# ---- Eight-Legs Easton (basic attack) ----
eight_legs_easton_hit = hit_damage(eight_legs_easton_pct, True, eight_legs_easton_mastery_boss_damage, 0)
eight_legs_easton_dps = (
    EIGHT_LEGS_EASTON_HITS * eight_legs_easton_hit * eight_legs_easton_per_second * target_multiplier(eight_legs_easton_targets)
    if unlocked("EIGHT_LEGS_EASTON") else 0.0
)

# ---- Other damage skills ----
DAMAGE_SKILLS = {
    "SWIFT_FIRE": dict(job_step=2, cooldown=18, hits=3, base=1800, fidx=12, scales=True,
                        mastery=level_gated_sum({39: 50}), mastery_boss=0, mastery_normal=0,
                        costs_action=True, targets=8, maple_ratio=MAPLE_HERO_RATIOS.get("SWIFT_FIRE", 0)),
    "SCURVY_SUMMONS": dict(job_step=2, cooldown=20, hits=2, icd=1.5, window=20, base=950, fidx=12,
                            scales=True, mastery=0, mastery_boss=0, mastery_normal=0,
                            costs_action=True, targets=3, ahoy_ratio=AHOY_MATEYS_RATIOS.get("SCURVY_SUMMONS", 0)),
    "ALL_ABOARD": dict(job_step=2, cooldown=20, hits=3, icd=2, window=20, base=1100, fidx=12,
                        scales=True, mastery=0, mastery_boss=0, mastery_normal=0,
                        costs_action=False, targets=8, ahoy_ratio=AHOY_MATEYS_RATIOS.get("ALL_ABOARD", 0)),
    "BLACKBOOT_BILL": dict(job_step=3, cooldown=20, hits=4, base=1700, fidx=12, scales=True,
                            mastery=level_gated_sum({73: 80}), mastery_boss=0, mastery_normal=0,
                            costs_action=True, targets=9, maple_ratio=MAPLE_HERO_RATIOS.get("BLACKBOOT_BILL", 0)),
    "SIEGE_BOMBER": dict(job_step=3, cooldown=30, hits=1, icd=1.5, window=30, base=1900, fidx=12,
                          scales=True, mastery=0, mastery_boss=0, mastery_normal=0,
                          costs_action=True, targets=6, maple_ratio=MAPLE_HERO_RATIOS.get("SIEGE_BOMBER", 0)),
    "BRAIN_SCRAMBLER": dict(job_step=4, cooldown=15, hits=2, base=29000, fidx=12, scales=True,
                             mastery=level_gated_sum({108: 50}), mastery_boss=0, mastery_normal=0,
                             costs_action=True, targets=1),
    "NAUTILUS_STRIKE": dict(job_step=4, cooldown=45, hits=5, base=19500, fidx=12, scales=True,
                             mastery=level_gated_sum({126: 50}), mastery_boss=0, mastery_normal=0,
                             costs_action=True, targets=15),
    "NAUTILUS_FINAL_ATTACK": dict(job_step=4, cooldown=1, hits=1, base=8500, fidx=21, scales=True,
                                   mastery=0, mastery_boss=0, mastery_normal=0,
                                   costs_action=False, targets=1, proc_chance=0.30),
    "RAPID_FIRE": dict(job_step=4, cooldown=17, hits=7, base=18000, fidx=12, scales=True,
                        mastery=0, mastery_boss=0, mastery_normal=0,
                        costs_action=True, targets=9),
    "BROADSIDE_BURST": dict(job_step=4, cooldown=30, hits=2, base=50000, fidx=12, scales=True,
                             mastery=level_gated_sum({122: 100}), mastery_boss=0, mastery_normal=0,
                             costs_action=True, targets=10),
    "BROADSIDE_SUSTAINED": dict(job_step=4, cooldown=30, hits=1, icd=2, window=30, base=33000,
                                 fidx=12, scales=True, mastery=0, mastery_boss=0, mastery_normal=0,
                                 costs_action=False, targets=5),
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
        maple_ratio=s.get("maple_ratio", 0.0), ahoy_ratio=s.get("ahoy_ratio", 0.0),
    )
    proc_prob = s.get("proc_chance", 1.0)
    eff_cd = eff_cooldown(s["cooldown"], s["costs_action"])
    if fixed_duration_active:
        rate = non_buff_total_hits(eff_cd, s["hits"], s.get("icd"), s.get("window")) / fight_duration
    else:
        hits = s["hits"] * ((s["window"] / s["icd"]) if s.get("icd") else 1)
        rate = hits / eff_cd
    skill_dps[key] = proc_prob * rate * hd * target_multiplier(s["targets"])

# ---- Majestic Presence (procs off 3 independent sources: Basic Attack + Brain Scrambler + Rapid
#      Fire — no Cooldown(s) of its own, combined trigger rate is the sum of the 3 sources' own
#      hit rates) ----
if unlocked("MAJESTIC_PRESENCE"):
    mp_pct = coeff_pct(18000, 12, True, 4)
    mp_hit = hit_damage(mp_pct, False, 0, 0)

    def _source_rate(key):
        s = DAMAGE_SKILLS[key]
        if not unlocked(key):
            return 0.0
        eff_cd = eff_cooldown(s["cooldown"], s["costs_action"])
        if fixed_duration_active:
            return non_buff_total_hits(eff_cd, s["hits"], s.get("icd"), s.get("window")) / fight_duration
        hits = s["hits"] * ((s["window"] / s["icd"]) if s.get("icd") else 1)
        return hits / eff_cd

    mp_combined_rate = eight_legs_easton_per_second + _source_rate("BRAIN_SCRAMBLER") + _source_rate("RAPID_FIRE")
    majestic_presence_dps = 0.25 * mp_combined_rate * mp_hit * target_multiplier(6)
else:
    majestic_presence_dps = 0.0
skill_dps["MAJESTIC_PRESENCE"] = majestic_presence_dps

total_dps = eight_legs_easton_dps + sum(skill_dps.values())

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

if mismatches:
    print(f"\n{len(mismatches)} mismatch(es) between the independent model and the live workbook.")
    sys.exit(1)
print("\nAll rows match between the independent model and the live workbook.")
