#!/usr/bin/env python3
"""
Generates Night-Lord-DPS-Calculator.xlsx: a live-formula Excel replica of a Night Lord
skill-rotation DPS model, sibling to build_fp_mage_workbook.py (see
tools/FP_MAGE_PROJECT_NOTES.md and the approved plan this was built from). Night Lord is
LUK main stat / DEX sub stat (confirmed via src/ts/page/base-stats/class-select.ts's
isLukMainStatClass).

Sheets: Inputs, FactorTable, Skills, Calc, Summary, Sensitivity (no CubeData/PotentialCubes
this pass — see the plan's §1 "Not touched this pass").

Key simplifications specific to this kit (see the plan for full derivation/justification):
  - Assassin's Mark (Mark of Assassin) is modeled as a periodic AoE tick (mark-application and
    mark-consumption collapsed into one instantaneous hit every effective cooldown), not a real
    duty cycle.
  - Alchemic Adrenaline's uptime is derived from the *pre-Adrenalin* Actions/sec (to avoid a
    circular reference against the Actions/sec calculation that Adrenalin's own Attack Speed
    bonus feeds into) — see build_summary_sheet.
  - Venom is modeled as permanently active (poison always up) at steady state, same simplification
    FP-Mage used for Elemental Drain.
  - Toxic Venom has no ICD: its trigger rate is the combined per-second hit rate (already
    target-count-multiplied) of every rotation damage skill flagged TriggersToxicVenom=TRUE.
  - Shadow Shifter's counterattack is driven by a new Inputs!incoming_hit_rate field (hits/sec
    taken), not the character's own cast rate.
  - Every "permanent passive that maps onto an existing generic Inputs% field" (Agile Claws,
    Physical Training, Claw Mastery, Critical Throw, Enveloping Darkness, Expert Throwing Star
    Handling, Claw Expert, Dark Harmony, Shadow Shifter's self-Attack%) follows the "Magic
    Critical pattern": assumed already reflected in the matching Inputs field, so its Calc!F is
    NOT added to baseline DPS — only used by the Sensitivity sheet's matching Skill-Level-Bonus
    block as a marginal delta.
"""
import ast
import json
import re
from pathlib import Path

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

REPO = Path(__file__).resolve().parent.parent
FACTOR_TABLE_JSON = REPO / "data/factor_table.json"
CUBE_POTENTIAL_JSON = REPO / "data/cube_potential_data.json"
OUT_PATH = REPO / "Night-Lord-DPS-Calculator.xlsx"

HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
HEADER_FONT = Font(bold=True, color="FFFFFF")
SECTION_FONT = Font(bold=True, size=12)
LABEL_FONT = Font(bold=True)
INPUT_FILL = PatternFill("solid", fgColor="FFF2CC")


def style_header_row(ws, row, ncols):
    for c in range(1, ncols + 1):
        cell = ws.cell(row=row, column=c)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center")


# ---------------------------------------------------------------------------
# Load the real factor table straight from the TS source (avoid re-typing it) — reused
# verbatim from build_fp_mage_workbook.py (plan §1).
# ---------------------------------------------------------------------------
def load_factor_table():
    data = json.loads(FACTOR_TABLE_JSON.read_text())
    return {int(k): v for k, v in data.items()}


FACTOR_TABLE = load_factor_table()
assert len(FACTOR_TABLE) == 300 and len(FACTOR_TABLE[1]) == 24


# ---------------------------------------------------------------------------
# Load the real potential-cube data straight from the (unused) TS web app, rather than
# re-typing 200+ weighted stat-roll rows by hand — verbatim reuse of
# build_fp_mage_workbook.py's own loader (equipment potentials aren't class-specific in this
# game, so this data is identical for every class). That file is a JS object literal, not
# strict JSON (bare keys, true/false, single quotes), so normalize it into a Python literal
# before ast.literal_eval.
# ---------------------------------------------------------------------------
def load_cube_potential_data():
    data = json.loads(CUBE_POTENTIAL_JSON.read_text())
    return (
        data["RARITY_UPGRADE_RATES"],
        data["EQUIPMENT_POTENTIAL_DATA"],
        data["SLOT_SPECIFIC_POTENTIALS"],
    )


RARITY_UPGRADE_RATES, EQUIPMENT_POTENTIAL_DATA, SLOT_SPECIFIC_POTENTIALS = load_cube_potential_data()
assert set(RARITY_UPGRADE_RATES) == {"normal", "rare", "epic", "unique", "legendary", "mystic"}
assert len(EQUIPMENT_POTENTIAL_DATA["normal"]["line1"]) == 16
assert set(EQUIPMENT_POTENTIAL_DATA) == {"normal", "rare", "epic", "unique", "legendary", "mystic"}

# Three equipment slots the TS web app never modeled (only 11 of the game's 14 slots exist
# there) — hand-added here, Python-side only, per the user's exact values (verbatim reuse of
# build_fp_mage_workbook.py's own hand-added slot-specific data — equipment potentials aren't
# class-specific). Structure mirrors the TS file's own 'gloves' entry: line1 always a
# single prime-only value at weight 1, line2/line3 split prime (new tier's value) vs
# non-prime (previous tier's value).
RARITY_ORDER = ["normal", "rare", "epic", "unique", "legendary", "mystic"]


def _slot_specific_tier_block(stat, values_by_tier):
    """values_by_tier: dict tier -> value, for whichever tiers this stat actually rolls at (in
    rarity order — a tier can be skipped, e.g. Shoulder/Chest's specials start at unique, not
    epic). The first tier present has no non-prime fallback since there's no earlier tier to
    inherit from; every later tier falls back to whichever tier immediately precedes it in this
    dict, not necessarily the previous RARITY_ORDER tier. Builds the same {line1/line2/line3}
    shape as the TS file's cape/gloves/legs/shoulder entries."""
    out = {}
    tiers = [t for t in RARITY_ORDER if t in values_by_tier]
    for i, tier in enumerate(tiers):
        value = values_by_tier[tier]
        block = {"line1": [{"stat": stat, "value": value, "weight": 1, "prime": True}]}
        if i == 0:
            block["line2"] = [{"stat": stat, "value": value, "weight": 0.24, "prime": True}]
            block["line3"] = [{"stat": stat, "value": value, "weight": 0.08, "prime": True}]
        else:
            prev_value = values_by_tier[tiers[i - 1]]
            block["line2"] = [
                {"stat": stat, "value": value, "weight": 0.24, "prime": True},
                {"stat": stat, "value": prev_value, "weight": 0.76, "prime": False},
            ]
            block["line3"] = [
                {"stat": stat, "value": value, "weight": 0.08, "prime": True},
                {"stat": stat, "value": prev_value, "weight": 0.92, "prime": False},
            ]
        out[tier] = block
    return out


SLOT_SPECIFIC_POTENTIALS["ring2"] = _slot_specific_tier_block(
    "Basic Attack Damage %", {"epic": 8, "unique": 14, "legendary": 21, "mystic": 30}
)
SLOT_SPECIFIC_POTENTIALS["face"] = _slot_specific_tier_block(
    "Final Damage %", {"epic": 3, "unique": 5, "legendary": 8, "mystic": 12}
)
SLOT_SPECIFIC_POTENTIALS["earrings"] = _slot_specific_tier_block(
    "Skill Damage %", {"epic": 8, "unique": 14, "legendary": 21, "mystic": 30}
)
# Ring and Necklace (the base slots, not ring2) share their own special stat that the TS
# source never modeled either (confirmed by the user) — All Skill Level, same weight/prime
# shape as the others, same values on both slots.
SLOT_SPECIFIC_POTENTIALS["ring"] = _slot_specific_tier_block(
    "All Skill Level", {"epic": 5, "unique": 8, "legendary": 12, "mystic": 16}
)
SLOT_SPECIFIC_POTENTIALS["necklace"] = _slot_specific_tier_block(
    "All Skill Level", {"epic": 5, "unique": 8, "legendary": 12, "mystic": 16}
)
SLOT_SPECIFIC_POTENTIALS["head"] = _slot_specific_tier_block(
    "Skill Cooldown Decrease (seconds)", {"epic": 0.5, "unique": 1, "legendary": 1.5, "mystic": 2}
)
# No epic option for Chest's special (confirmed by the user) — starts at unique.
SLOT_SPECIFIC_POTENTIALS["chest"] = _slot_specific_tier_block(
    "Basic Attack Target Increase", {"unique": 1, "legendary": 2, "mystic": 3}
)
SLOT_SPECIFIC_POTENTIALS["belt"] = _slot_specific_tier_block(
    "Buff Duration Increase %", {"epic": 5, "unique": 8, "legendary": 12, "mystic": 20}
)
# Companions aren't modeled (0 DPS impact, same as the Inputs!companion_summon_time_increase_pct
# row) — not in POTENTIAL_STAT_TO_SWEEP_KEY, so dps_per_unit_expr naturally resolves it to 0.
SLOT_SPECIFIC_POTENTIALS["boots"] = _slot_specific_tier_block(
    "Companion Summoning Time Increase %", {"epic": 5, "unique": 8, "legendary": 12, "mystic": 20}
)
# Eye Accessory's special is "N main-stat per character level" (confirmed by the user, e.g.
# level 115 x 20/level = 2300 flat main-stat) — a live, level-scaled flat main-stat roll, not a
# fixed number. The roll-table "value" here is deliberately left as the per-level coefficient
# (10/20/35/50), not the computed flat main-stat — dps_per_unit_expr special-cases this stat
# name to multiply Flat LUK's own DPS-per-unit by the live Inputs!level cell, so
# Value*DPSPerUnit still gives the right total without needing a live formula in the Value
# column itself.
SLOT_SPECIFIC_POTENTIALS["eye-accessory"] = _slot_specific_tier_block(
    "Main Stat Per Level", {"epic": 10, "unique": 20, "legendary": 35, "mystic": 50}
)
# Pocket's special is "N main-stat % per 4 character levels", stepped not continuous — confirmed
# by the user: only increases every 4 whole levels (e.g. level 115 x 0.6%/4-levels =
# 0.6*FLOOR(115/4) = 0.6*28 = 16.8% LUK, not 0.6*115/4 = 17.25%). Same "leave the roll-table
# value as the raw coefficient, fold the level scaling into DPSPerUnit" pattern as Eye
# Accessory above.
SLOT_SPECIFIC_POTENTIALS["pocket"] = _slot_specific_tier_block(
    "Main Stat % per 4 Levels", {"epic": 0.4, "unique": 0.6, "legendary": 0.8, "mystic": 1.2}
)

# Full 15-slot list: the 11 the TS app actually models + the 4 hand-added above.
CUBE_SLOTS = [
    "head", "cape", "chest", "shoulders", "legs", "belt", "gloves", "boots",
    "ring", "neck", "eye-accessory", "ring2", "face", "earrings", "pocket",
]
# SLOT_SPECIFIC_POTENTIALS keys use the TS app's own (slightly different) slot ids for the
# 11 shared slots (shoulder/necklace vs shoulders/neck) — map our CUBE_SLOTS id to that key.
SLOT_SPECIFIC_KEY = {
    "shoulders": "shoulder",
    "neck": "necklace",
}


def _iter_potential_line_entries():
    """Yields (slot, rarity, line_num, entry) for every roll-table row: the generic pool
    (slot="ALL", applies to every slot) plus every hand-confirmed slot-specific addition."""
    for rarity in RARITY_ORDER:
        for line_num in (1, 2, 3):
            for entry in EQUIPMENT_POTENTIAL_DATA[rarity][f"line{line_num}"]:
                yield "ALL", rarity, line_num, entry
    for slot in CUBE_SLOTS:
        slot_data = SLOT_SPECIFIC_POTENTIALS.get(SLOT_SPECIFIC_KEY.get(slot, slot))
        if not slot_data:
            continue
        for rarity, lines in slot_data.items():
            for line_name, entries in lines.items():
                line_num = int(line_name[-1])
                for entry in entries:
                    yield slot, rarity, line_num, entry


# Every distinct stat name that can appear on a potential line — the generic 16-stat pool +
# the 4 hand-added slot-specific stats (ring2/face/earrings/ring+necklace) + the 2 new rollable
# stats introduced this session (not present in the roll-table data itself, but the user may
# already have them equipped, so they must still be selectable in the Current-State "current
# line stat" dropdown).
ALL_POTENTIAL_STATS = sorted({entry["stat"] for _, _, _, entry in _iter_potential_line_entries()} | {
    "Skill Cooldown Decrease (seconds)", "Buff Duration Increase %",
})
CUBE_DATA_LAST_ROW = 1 + sum(1 for _ in _iter_potential_line_entries())

# ---------------------------------------------------------------------------
# Inputs sheet row map — LUK main stat / DEX sub (plan §2's stat-identity swap from FP-Mage's
# INT main / LUK sub), plus a new incoming_hit_rate field (Shadow Shifter only).
# ---------------------------------------------------------------------------
DERIVED_HEADER_ROW = 49
D_ATTACK = 50                    # ATTACK = Flat ATTACK x (1+ATTACK%/100)
D_STAT_DAMAGE = 51               # STAT_DAMAGE% = 1% of total LUK + 0.25% of DEX
D_BASIC_INPUT_LEVEL = 52         # Basic Attack (Showdown) input level (4th job formula)
D_BASIC_FACTOR = 53              # Basic Attack factor lookup (factorIndex 21)
D_SKILL_COEFFICIENT = 54         # Basic Attack base coefficient % before Skill Mastery
D_NORMAL_WEIGHT_FRAC = 55        # 0/1/breakthrough-blend/0 weight, by monster_type
DERIVED_ROW = {
    "attack": D_ATTACK,
    "stat_damage": D_STAT_DAMAGE,
    "basic_input_level": D_BASIC_INPUT_LEVEL,
    "basic_factor": D_BASIC_FACTOR,
    "skill_coefficient": D_SKILL_COEFFICIENT,
    "normal_weight_frac": D_NORMAL_WEIGHT_FRAC,
}

IN = {
    "level": 3,
    "monster_type": 4,
    "flat_attack": 5,
    "attack_pct": 6,
    "monster_defense": 7,
    "crit_rate": 8,
    "crit_damage": 9,
    "attack_speed": 10,
    "flat_luk": 11,
    "luk_pct": 12,
    "dex": 13,
    "damage": 14,
    "damage_amp": 15,
    "basic_attack_damage": 16,
    "skill_damage": 17,
    "def_pen": 18,
    "boss_damage": 19,
    "normal_damage": 20,
    "min_damage": 21,
    "max_damage": 22,
    "final_damage": 23,
    "skill_lvl_1st": 24,
    "skill_lvl_2nd": 25,
    "skill_lvl_3rd": 26,
    "skill_lvl_4th": 27,
    "skill_lvl_all": 28,
    "skill_cooldown_decrease": 31,
    "basic_attack_target_increase": 32,
    "buff_duration_increase_pct": 33,
    "companion_summon_time_increase_pct": 34,
    "fight_duration": 35,
    "breakthrough_normal_weight_pct": 36,
    "max_enemies_hit": 37,
    "incoming_hit_rate": 38,
}

# These 6 values are computed (not user-entered) and live on the Summary sheet's "Derived Values"
# block instead of cluttering Inputs — see DERIVED_ROW above and build_summary_sheet.


def IB(key):
    if key in DERIVED_ROW:
        return f"Summary!$B${DERIVED_ROW[key]}"
    return f"Inputs!$B${IN[key]}"


def build_readme_sheet(wb):
    ws = wb.active
    ws.title = "README"
    ws["A1"] = "Night Lord — DPS Calculator: How to Use This Workbook"
    ws["A1"].font = Font(bold=True, size=14)

    def section(row, title):
        ws.cell(row=row, column=1, value=title).font = SECTION_FONT

    def line(row, text):
        ws.cell(row=row, column=1, value=text)

    r = 3
    section(r, "How to use this workbook"); r += 1
    for text in [
        "Only edit the yellow-highlighted cells on the Inputs sheet — every other sheet is "
        "computed from those values and will be overwritten if you rebuild the workbook.",
        "Summary shows Total DPS, a Per-Skill DPS Breakdown (damage-dealing skills only — "
        "buffs/passives that never deal their own damage are omitted), and a Marginal DPS & "
        "Stat Value table showing the DPS gained per +1 of each stat.",
        "Sensitivity has the full detail behind that marginal-value table — one self-contained "
        "block per stat, showing exactly how bumping that stat by +1 changes every downstream "
        "number.",
        "CubeData/PotentialCubes model your current gear's Potential Cube lines and drive "
        "cube-reroll expected-value decisions. For the full standalone Potential Cube EV "
        "calculator (exact optimal-stopping math, works from this workbook alone), see "
        "tools/potential_cubes_ev.py in the project repo.",
    ]:
        line(r, text); r += 1
    r += 1

    section(r, "Design decisions & assumptions"); r += 1
    for text in [
        "Venom/Toxic Venom assume the target is permanently afflicted with Venom's poison at "
        "steady state, not an exact on/off timer.",
        "Crit Rate pushed above 100% (e.g. by cube potential lines) automatically redirects "
        "its stat-value to Crit Damage's own per-unit DPS value on the PotentialCubes sheet, "
        "since excess Crit Rate cannot do anything past 100%.",
        "Buffs (Dark Sight, Frailty Curse, Nimble Feet) are modeled at steady-state duty-cycle "
        "average uptime, not as an exact moment-to-moment state machine. Alchemic Adrenaline's "
        "own action-rate-driven stack-up cycle is likewise modeled as a steady-state average "
        "uptime rather than an exact stack counter.",
        "Shadow Partner and Shadow Shifter are modeled as steady-state average multipliers "
        "(expected extra damage per hit / expected counterattack rate) rather than an exact "
        "proc-by-proc simulation.",
        "Monster Type blends Boss/Normal Monster Damage% by the Chapter Breakthrough weight %; "
        "PvP forces a fixed 15-second window regardless of the Fixed Fight Duration input.",
        "Not modeled (out of scope): crowd control, Accuracy/Evasion/Defense reduction, "
        "movement speed, the character's own Defense stat, and Companion Summoning Time.",
    ]:
        line(r, text); r += 1

    ws.column_dimensions["A"].width = 110
    for row in ws.iter_rows(min_row=1, max_row=r, max_col=1):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    return ws


def build_inputs_sheet(wb, existing=None):
    existing = existing or {}
    ws = wb.create_sheet("Inputs")
    ws["A1"] = "Night Lord — DPS Calculator Inputs"
    ws["A1"].font = Font(bold=True, size=14)

    rows = [
        ("level", "Character Level", 200),
        ("monster_type", "Monster Type (\"boss\", \"normal\", \"breakthrough\", or \"pvp\")", "boss"),
        ("flat_attack", "Flat ATTACK", 10000),
        ("attack_pct", "ATTACK %", 0),
        ("monster_defense", "Monster Defense (flat, post-x100/x10 scaling)", 0),
        ("crit_rate", "CRIT_RATE %", 0),
        ("crit_damage", "CRIT_DAMAGE %", 0),
        ("attack_speed", "ATTACK_SPEED % (base, excludes Nimble Feet/Adrenalin)", 0),
        ("flat_luk", "Flat LUK", 0),
        ("luk_pct", "LUK %", 0),
        ("dex", "DEX", 0),
        ("damage", "DAMAGE %", 0),
        ("damage_amp", "DAMAGE_AMP %", 0),
        ("basic_attack_damage", "BASIC_ATTACK_DAMAGE %", 0),
        ("skill_damage", "SKILL_DAMAGE %", 0),
        ("def_pen", "DEF_PEN %", 0),
        ("boss_damage", "BOSS_DAMAGE %", 0),
        ("normal_damage", "NORMAL_DAMAGE %", 0),
        ("min_damage", "MIN_DAMAGE %", 100),
        ("max_damage", "MAX_DAMAGE %", 100),
        ("final_damage", "FINAL_DAMAGE % (base)", 0),
        ("skill_lvl_1st", "Skill Level Bonus — 1st Job", 0),
        ("skill_lvl_2nd", "Skill Level Bonus — 2nd Job", 0),
        ("skill_lvl_3rd", "Skill Level Bonus — 3rd Job", 0),
        ("skill_lvl_4th", "Skill Level Bonus — 4th Job", 0),
        ("skill_lvl_all", "Skill Level Bonus — All Skills", 0),
    ]
    for key, label, default in rows:
        r = IN[key]
        ws.cell(row=r, column=1, value=label).font = LABEL_FONT
        cell = ws.cell(row=r, column=2, value=existing.get(key, default))
        cell.fill = INPUT_FILL

    ws.cell(row=30, column=1, value="Additional Bonuses").font = SECTION_FONT
    bonus_rows = [
        ("skill_cooldown_decrease", "Skill Cooldown Decrease (seconds, only skills the character actively casts)", 0),
        ("basic_attack_target_increase", "Basic Attack Target Increase (flat, adds to the 6-target Showdown base)", 1),
        ("buff_duration_increase_pct", "Buff Duration Increase %", 0),
        ("companion_summon_time_increase_pct", "Companion Summoning Time Increase % (companions not modeled — always 0 DPS impact)", 0),
        ("fight_duration", "Fixed Fight Duration (seconds, boss or normal — leave 0 for steady-state DPS; ignored for pvp)", 0),
        ("breakthrough_normal_weight_pct", "Chapter Breakthrough: Normal-Monster Weight % (only used when Monster Type = breakthrough)", 60),
        ("max_enemies_hit", "Max Enemies Actually In Range (normal monsters only; default 999 = uncapped)", 999),
        ("incoming_hit_rate", "Incoming Hit Rate (hits/sec taken — user-estimated, feeds Shadow Shifter's counterattack only)", 1),
    ]
    for key, label, default in bonus_rows:
        r = IN[key]
        ws.cell(row=r, column=1, value=label).font = LABEL_FONT
        cell = ws.cell(row=r, column=2, value=existing.get(key, default))
        cell.fill = INPUT_FILL

    ws.column_dimensions["A"].width = 50
    ws.column_dimensions["B"].width = 16
    return ws


def build_factor_table_sheet(wb):
    ws = wb.create_sheet("FactorTable")
    ws.cell(row=1, column=1, value="Level")
    for idx in range(24):
        ws.cell(row=1, column=2 + idx, value=f"F{idx}")
    style_header_row(ws, 1, 25)
    for level in range(1, 301):
        r = level + 1
        ws.cell(row=r, column=1, value=level)
        for idx, val in enumerate(FACTOR_TABLE[level]):
            ws.cell(row=r, column=2 + idx, value=val)
    ws.column_dimensions["A"].width = 8
    ws.freeze_panes = "B2"
    return ws


# ---------------------------------------------------------------------------
# Action-economy formula helpers — reused verbatim from build_fp_mage_workbook.py (plan §1).
# ---------------------------------------------------------------------------
PVP_FIGHT_DURATION = 15


def effective_cooldown_expr(monster_type_ref, cooldown_ref, cdr_ref, costs_action_ref):
    return (
        f'IF({monster_type_ref}="pvp",{PVP_FIGHT_DURATION},'
        f'MAX(0.1,{cooldown_ref}-IF({costs_action_ref}=TRUE,{cdr_ref},0)))'
    )


def uptime_fraction_expr(monster_type_ref, duration_ref, cooldown_ref, bdi_ref):
    scaled_duration = f'({duration_ref}*(1+{bdi_ref}/100))'
    return (
        f'IF({monster_type_ref}="pvp",MIN({scaled_duration},{PVP_FIGHT_DURATION})/{PVP_FIGHT_DURATION},'
        f'{scaled_duration}/{cooldown_ref})'
    )


def monster_blend_expr(monster_type_ref, w_ref, boss_expr, normal_expr, pvp_expr):
    return f'IF({monster_type_ref}="pvp",{pvp_expr},(1-{w_ref})*({boss_expr})+{w_ref}*({normal_expr}))'


def target_multiplier_expr(monster_type_ref, w_ref, targets_ref, max_enemies_ref):
    capped_targets = f'MIN({targets_ref},{max_enemies_ref})'
    return monster_blend_expr(monster_type_ref, w_ref, "1", capped_targets, "1")


def fixed_duration_active_expr(monster_type_ref, fight_duration_ref):
    return f'AND({monster_type_ref}<>"pvp",{fight_duration_ref}>0)'


def exact_casts_expr(duration_ref, cooldown_ref):
    return f'(INT({duration_ref}/{cooldown_ref})+1)'


def exact_total_hits_expr(casts_ref, hits_ref, icd_ref, window_ref, cooldown_ref, duration_ref):
    last_cast_start = f'(({casts_ref}-1)*{cooldown_ref})'
    remaining_after_last = f'MAX(0,{duration_ref}-{last_cast_start})'
    full_window_ticks = f'IF({icd_ref}>0,{window_ref}/{icd_ref},1)'
    last_cast_ticks = f'IF({icd_ref}>0,MIN({window_ref},{remaining_after_last})/{icd_ref},1)'
    return f'({hits_ref}*(({casts_ref}-1)*{full_window_ticks}+{last_cast_ticks}))'


def exact_buff_uptime_expr(casts_ref, buff_duration_ref, cooldown_ref, fight_duration_ref):
    last_cast_start = f'(({casts_ref}-1)*{cooldown_ref})'
    remaining_after_last = f'MAX(0,{fight_duration_ref}-{last_cast_start})'
    last_uptime = f'MIN({buff_duration_ref},{remaining_after_last})'
    return f'(({casts_ref}-1)*{buff_duration_ref}+{last_uptime})'


def uptime_fraction_or_exact_expr(fixed_duration_active_ref, casts_ref, monster_type_ref,
                                   duration_ref, cooldown_ref, bdi_ref, fight_duration_ref):
    scaled_duration = f'({duration_ref}*(1+{bdi_ref}/100))'
    exact = f'({exact_buff_uptime_expr(casts_ref, scaled_duration, cooldown_ref, fight_duration_ref)}/{fight_duration_ref})'
    steady = uptime_fraction_expr(monster_type_ref, duration_ref, cooldown_ref, bdi_ref)
    return f'IF({fixed_duration_active_ref},{exact},{steady})'


def rate_or_exact_hits_expr(fixed_duration_active_ref, row_ref, hits_ref, icd_ref, window_ref,
                             cooldown_ref, fight_duration_ref, steady_rate_ref):
    exact_hits = exact_total_hits_expr(row_ref, hits_ref, icd_ref, window_ref, cooldown_ref, fight_duration_ref)
    return f'IF({fixed_duration_active_ref},({exact_hits}/{fight_duration_ref}),{steady_rate_ref})'


def level_gated_sum(level_ref, pairs):
    ordered = sorted(pairs.items())
    thresholds = ",".join(str(level) for level, _ in ordered)
    increments = ",".join(str(inc) for _, inc in ordered)
    return f'=SUMPRODUCT(({level_ref}>={{{thresholds}}})*{{{increments}}})'


# ---------------------------------------------------------------------------
# Skills sheet schema
# ---------------------------------------------------------------------------
SKILL_COLUMNS = [
    "Key", "Name", "JobStep", "Cooldown(s)", "CostsActionSlot", "ActionsPerCast",
    "HitsPerCast", "ICD(s)", "ActiveWindow(s)", "ProcChance%", "RollsPerCast",
    "BaseDamage(tenths%)", "FactorIndex", "ScalesWithLevel",
    "SkillMasteryBonus%", "MasteryBossDamage%", "MasteryNormalDamage%", "MasteryFinalDamage%",
    "MasteryMaxDamage%", "MasteryMinDamage%", "MasteryCooldownPct", "MasteryTargetIncrease",
    "NormalMonsterTargets", "BuffTargetStat", "BuffDuration(s)", "TriggersToxicVenom",
    "MapleHeroBase(tenths%)", "MapleHeroFactorIndex", "Stacks", "Note",
]
SC = {name: get_column_letter(i + 1) for i, name in enumerate(SKILL_COLUMNS)}

# Row order (2..LAST_ROW) — never hand-numbered; derived from this list so adding a row can't
# silently collide with another (per FP_MAGE_PROJECT_NOTES.md's hardcoded-row-offset lesson).
ROW_ORDER = [
    "SHOWDOWN", "GUST_CHARM", "MARK_OF_ASSASSIN", "TRIPLE_THROW",
    "ADRENALIN_FD", "ADRENALIN_AS", "DARK_FLARE", "VENOM", "TOXIC_VENOM", "SHADOW_PARTNER",
    "QUAD_STAR", "SUDDEN_RAID_BURST", "SUDDEN_RAID_DOT",
    "FRAILTY_CURSE_SELF_FD", "FRAILTY_CURSE_DEBUFF",
    "SHADOW_SHIFTER", "SHADOW_SHIFTER_SELF_ATK",
    "NIMBLE_FEET", "DARK_SIGHT_CRIT", "DARK_SIGHT_ATK",
    "AGILE_CLAWS", "PHYSICAL_TRAINING", "CLAW_MASTERY",
    "CRITICAL_THROW_RATE", "CRITICAL_THROW_DMG",
    "ENVELOPING_DARKNESS", "EXPERT_THROWING_STAR_HANDLING",
    "CLAW_EXPERT", "DARK_HARMONY", "NIGHT_LORDS_MARK",
]
ROW = {key: i for i, key in enumerate(ROW_ORDER, start=2)}
LAST_ROW = 1 + len(ROW_ORDER)

# Unlock level (character level) for every row — Night Lord's full kit spans req levels 0-125,
# well under a 4th-job-tier character's typical level, but gated properly (unlike FP-Mage, which
# only bothered gating its 102-138 batch) so the model stays correct at lower test levels too.
UNLOCK_LEVEL = {
    "SHOWDOWN": 100,
    "GUST_CHARM": 35,
    "MARK_OF_ASSASSIN": 40,
    "TRIPLE_THROW": 63,
    "ADRENALIN_FD": 66,
    "ADRENALIN_AS": 66,
    "DARK_FLARE": 69,
    "VENOM": 72,
    "TOXIC_VENOM": 117,
    "SHADOW_PARTNER": 60,
    "QUAD_STAR": 103,
    "SUDDEN_RAID_BURST": 105,
    "SUDDEN_RAID_DOT": 105,
    "FRAILTY_CURSE_SELF_FD": 110,
    "FRAILTY_CURSE_DEBUFF": 110,
    "SHADOW_SHIFTER": 115,
    "SHADOW_SHIFTER_SELF_ATK": 115,
    "DARK_SIGHT_CRIT": 15,
    "DARK_SIGHT_ATK": 15,
    "AGILE_CLAWS": 33,
    "PHYSICAL_TRAINING": 38,
    "CLAW_MASTERY": 40,
    "CRITICAL_THROW_RATE": 45,
    "CRITICAL_THROW_DMG": 45,
    "ENVELOPING_DARKNESS": 72,
    "EXPERT_THROWING_STAR_HANDLING": 75,
    "CLAW_EXPERT": 120,
    "DARK_HARMONY": 125,
    "NIGHT_LORDS_MARK": 107,
    # NIMBLE_FEET: no threshold (shared Explorer skill, level 0) — stays unconditionally unlocked.
}


def unlock_expr(key):
    level = UNLOCK_LEVEL.get(key)
    return "=TRUE" if level is None else f"={IB('level')}>={level}"


# Mastery-driven cooldown/ICD reductions are baked directly into the relevant row's own
# Cooldown(s)/ICD(s) cell formula (same pattern FP-Mage uses for Poison Mist's ICD/Ifrit's
# window) rather than consumed live from MasteryCooldownPct — that column is populated below
# for reference/documentation only (matches the "ProcChance%/BuffDuration(s) are real skill
# values for reference only" precedent FP-Mage already established for Elemental Decrease).

# Sudden Raid (DoT) shares Sudden Raid (burst)'s live cooldown cell (same cross-reference
# pattern as FP-Mage's Mist Eruption <-> Poison Mist (burst)).
_SUDDEN_RAID_DOT_COOLDOWN = f"=Skills!{SC['Cooldown(s)']}{ROW['SUDDEN_RAID_BURST']}"

# Night Lord's Mark's Final-Damage contribution feeds Assassin's Mark's own MasteryFinalDamage%
# term once unlocked (level 107) — a real always-on contributor (NOT baked into Inputs, unlike
# every "passive-mult" row), same "Element Amplification" treatment FP-Mage uses.
_MARK_OF_ASSASSIN_FD = (
    f"=IF({IB('level')}>=107,Calc!F{ROW['NIGHT_LORDS_MARK']},0)"
)
_MARK_OF_ASSASSIN_TARGET_INCREASE = f"=IF({IB('level')}>=107,3,0)"

# Mastery Lv.122 ("Weaken", patched): marked targets take +8% Damage Taken for 2s. Under the
# approved simplification (mark-placement and mark-consumption collapsed into one instantaneous
# tick, see MARK_OF_ASSASSIN's own Note), there is no separate "hit that consumes an already-
# placed mark" event for this debuff to attach to — the tick both places AND consumes the mark
# in the same instant, so the +8% only ever applies to that same tick's own hit, once per
# effective cooldown (not a duty-cycle-averaged window benefiting other skills' hits in between).
# Corrected per the user: modeled as a flat MasteryBossDamage%/MasteryNormalDamage% addition on
# this row only, not a global Summary!R_MONSTER_DMG_BONUS contributor.
_MARK_OF_ASSASSIN_WEAKEN = f"=IF({IB('level')}>=122,8,0)"

# (key, name, jobstep, cooldown, costsAction, actionsPerCast, hits, icd, window, chance, rolls,
#  baseDamage, factorIndex, scales, skillMasteryBonusPct, masteryBossDmgPct, masteryNormalDmgPct,
#  masteryFinalDmgPct, masteryMaxDmgPct, masteryMinDmgPct, masteryCooldownPct,
#  masteryTargetIncrease, normalMonsterTargets, buffTarget, buffDuration, triggersToxicVenom,
#  mapleBase, mapleFactor, stacks, note)
SKILL_ROWS = [
    ("SHOWDOWN", "Showdown", 4, "", False, 1, f"=IF({IB('level')}>=134,6,5)", 0, 0, 100, 1,
     "", "", True,
     level_gated_sum(IB("level"), {98: 10, 104: 1, 113: 1, 118: 1, 126: 1, 130: 1}),
     level_gated_sum(IB("level"), {108: 10, 122: 10}), 0, 0, 0, 0, 0, 0,
     f'=6+{IB("basic_attack_target_increase")}', "", 0, True, "", "", "",
     "4th-job basic-attack effect (superseded from Lucky Seven/Shuriken Burst/Shuriken "
     "Challenge, per the project's job-tier-is-gone scope). 5 hits per activation (Mastery "
     "Lv.134 'Strike' -> 6), 6+Basic Attack Target Increase targets vs normal monsters. "
     "Reverse-engineered from the wiki's 290%->522% (levels 1-200) curve: factorIndex 21, "
     "baseDamage 2900 tenths%. Coefficient = Inputs!skill_coefficient (computed from this same "
     "factor) + SkillMasteryBonus%. SkillMasteryBonus% is the 6-tier 'Showdown - Damage' "
     "mastery chain (98/104/113/118/126/130), each entry showing the CUMULATIVE total (10%, "
     "11%, ..., 15%) per the game's own tooltip convention (confirmed against the identically-"
     "shaped Shuriken Challenge/Boss-Damage mastery chains elsewhere in this table), so "
     "level_gated_sum uses DELTA increments (10, then +1 five times) to reproduce that curve, "
     "not the raw displayed percentages. MasteryBossDamage% is the 2-tier 'Showdown - Boss "
     "Monster Damage' chain (108, 122), each independently +10% (same two-tier stacking "
     "pattern as Shuriken Challenge's own Boss Damage masteries at 68/82), totaling +20%."),
    ("GUST_CHARM", "Gust Charm", 2, 24, True, 1, 1, 0, 0, 100, 1,
     4000, 12, True,
     level_gated_sum(IB("level"), {39: 80}), 0, 0, 0, 0, 0, 0, 0,
     8, "", 0, True, 1300, 23, "",
     "Patched: targets 6->8, stun 1.5s->2s (stun not modeled), Mastery Lv.39 re-typed from "
     "'+50% stun duration' to '+80% Damage' (now a real SkillMasteryBonus%). Damage curve "
     "itself (400%->600%, levels 1-100) unpatched — factorIndex 12, baseDamage 4000 tenths%. "
     "Maple Hero (NL) target: 130%->1014% (levels 1-200), factorIndex 23."),
    ("MARK_OF_ASSASSIN", "Assassin's Mark", 2,
     f"=IF({IB('level')}>=138,2,2.5)", False, 1, 1, 0, 0, 100, 1,
     1900, 21, True,
     level_gated_sum(IB("level"), {42: 80}), _MARK_OF_ASSASSIN_WEAKEN, _MARK_OF_ASSASSIN_WEAKEN, _MARK_OF_ASSASSIN_FD, 0, 0, 0, _MARK_OF_ASSASSIN_TARGET_INCREASE,
     f"=7+Skills!{SC['MasteryTargetIncrease']}{ROW['MARK_OF_ASSASSIN']}", "", 0, True, "", "", "",
     "Simplified to a periodic AoE tick per the approved plan — mark-application and "
     "mark-consumption collapsed into one instantaneous hit every effective cooldown, no "
     "mark-duty-cycle modeling. Patched: interval 5s->2.5s (then -0.5s more at Mastery Lv.138 "
     "-> 2s), duration 5s->2.5s (irrelevant under this simplification), damage 300%->190%. "
     "factorIndex 21 (from the unpatched 300%->420% wiki curve), baseDamage 1900 tenths% "
     "(190% patched base). Not a player-cast action (CostsActionSlot=False) — it's a passive, "
     "automatic AoE proc, not a deliberate cast. Base 7 targets, +3 (MasteryTargetIncrease) "
     "once Night Lord's Mark unlocks at level 107. MasteryFinalDamage% pulls Night Lord's "
     "Mark's own Calc!F live (a real, always-on contributor, not baked into Inputs). "
     "SkillMasteryBonus% is Mastery Lv.42 ('Mark of Assassin - Damage', +80%, unaffected by "
     "the patch). Mastery "
     "Lv.122 ('Weaken', patched): marked targets take +8% Damage Taken for 2s — since this "
     "row's own tick both places AND consumes the mark in the same instant (no separate "
     "'hit that lands on an already-marked target' event exists in this simplified model), "
     "the +8% is folded directly into THIS row's own MasteryBossDamage%/MasteryNormalDamage% "
     "(applies only to Assassin's Mark's own hit, once per effective cooldown — not a "
     "duty-cycle-averaged window benefiting other skills' hits in between)."),
    ("TRIPLE_THROW", "Triple Throw", 3, 13, True, 1, 3, 0, 0, 100, 1,
     3600, 12, True,
     level_gated_sum(IB("level"), {71: 100}), 0, 0, 0, 0, 0, 0, 0,
     1, "", 0, True, "", "", "",
     "Single-target. factorIndex 12, baseDamage 3600 tenths% (360%->720%, levels 1-200). "
     "SkillMasteryBonus% is Mastery Lv.71 ('Triple Throw - Damage', +100%, unaffected by "
     "the patch)."),
    ("ADRENALIN_FD", "Alchemic Adrenaline (Final Damage)", 3, "", False, 1, 1, 0, 0, 100, 1,
     150, 22, True,
     0, 0, 0, 0, 0, 0, 0, 0,
     1, "FINAL_DAMAGE", f"=IF({IB('level')}>=88,15,10)", False, "", "", "",
     "Patched: trigger 7 hits->5 hits, Final Damage base 10%->15% (curve shape/ratio preserved "
     "from the unpatched 10%->16% wiki curve; factorIndex 22, baseDamage 150 tenths%). Uptime "
     "is bespoke — see build_summary_sheet's AdrenalinUptime (action-rate-driven cycle, not the "
     "generic BuffDuration/Cooldown ratio) — so this row has no Cooldown(s) of its own and isn't "
     "consumed via the generic buff_uptime() helper. Mastery Lv.88 adds +5s to BuffDuration(s)."),
    ("ADRENALIN_AS", "Alchemic Adrenaline (Attack Speed)", 3, "", False, 1, 1, 0, 0, 100, 1,
     80, 22, True,
     0, 0, 0, 0, 0, 0, 0, 0,
     1, "ATTACK_SPEED", f"=IF({IB('level')}>=88,15,10)", False, "", "", "",
     "Same trigger/uptime as Adrenalin (Final Damage) above (8%->12.8%, levels 1-200), split "
     "into its own row since BuffTargetStat only holds one target per row (mirrors Dark Sight's "
     "own Crit Rate / Attack split below)."),
    ("DARK_FLARE", "Dark Flare", 3,
     f"=IF({IB('level')}>=92,45*0.7,45)", True, 1, f"=IF({IB('level')}>=76,3,2)",
     f"=IF({IB('level')}>=104,2*0.75,2)", 20, 100, 1,
     3300, 12, True,
     0, 0, 0, 0, 0, 0,
     f"=IF({IB('level')}>=92,30,0)", 0,
     8, "", 0, True, 150, 23, "",
     "Shared w/ Shadower, Maple Hero (NL) target (15%->117%, levels 1-200, factorIndex 23). "
     "Patched: hit interval 5s->2s, targets 5->8, "
     "damage 400%->330% (curve shape from the unpatched 400%->800% wiki curve; factorIndex 12, "
     "baseDamage 3300 tenths%). 20s active window / 2s interval = 10 tick-sets x 2 hits = 20 "
     "EffectiveHits (was 4x2=8 pre-patch); Mastery Lv.76 ('Dark Flare - Strike', +1 hit per "
     "tick-set, 2->3) brings this to 30 EffectiveHits once unlocked. Mastery Lv.92 (-30% "
     "cooldown) and Lv.104 (hit-interval "
     "-25%, patched from -40%) are both baked directly into the Cooldown(s)/ICD(s) cell formulas "
     "(MasteryCooldownPct column here is reference-only, documenting the 30% used above, per the "
     "'ProcChance%/BuffDuration(s) reference-only' precedent already established in FP-Mage)."),
    ("VENOM", "Venom", 3, 1, False, 1, 1, 0, 0, 100, 1,
     450, 21, True,
     0, 0, 0, 0, 0, 0, 0, 0,
     1, "", 0, False, 500, 23, "",
     "Shared w/ Shadower. Maple Hero (NL) target (50%->390%, levels 1-200, factorIndex 23). "
     "Patched: poison chance 30%->50% (modeled always-active at steady "
     "state regardless — Elemental-Drain-style simplification, even safer now at 50%). "
     "Cooldown=1 is the same 'always-on tick' trick FP-Mage's Elemental Drain uses (1 tick/sec "
     "forever, not a real cooldown). factorIndex 21, baseDamage 450 tenths% (45%->81%, levels "
     "1-200). Mastery Lv.82 Weaken (+15%p Damage Taken while poisoned, patched from 12%) is a "
     "GLOBAL always-on monster-damage-taken bonus (not per-row) — see "
     "global_monster_dmg_bonus_expr in build_calc_sheet, not this row's own Mastery columns."),
    ("TOXIC_VENOM", "Toxic Venom", 4, "", False, 1, 1, 0, 0, 20, 1,
     6000, 21, True,
     level_gated_sum(IB("level"), {128: 100}), 0, 0, 0, 0, 0, 0, 0,
     1, "", 0, False, "", "", "",
     "Shared w/ Shadower. No ICD — every attack against a (permanently poisoned, by the Venom "
     "assumption) target independently rolls the 20% chance. Trigger rate = the combined "
     "per-second hit rate (already target-count-multiplied) of every row with "
     "TriggersToxicVenom=TRUE (see build_calc_sheet's Calc!S 'HitRate' column and this row's own "
     "bespoke O-column formula) — deliberately excludes Venom itself, Toxic Venom itself, Shadow "
     "Partner (not an independent hit), and Shadow Shifter's counterattack (a defensive proc, "
     "scoped out for simplicity; flagged as an assumption). factorIndex 21, baseDamage 6000 "
     "tenths% (600%->1080%, levels 1-200). SkillMasteryBonus% is Mastery Lv.128 ('Toxic Venom "
     "- Damage', +100%, unaffected by the patch)."),
    ("SHADOW_PARTNER", "Shadow Partner", 3, "", False, 1, 1, 0, 0, 25, 1,
     840, 21, True,
     level_gated_sum(IB("level"), {66: 100}), 0, 0, 0, 0, 0, 0, 0,
     1, "", 0, False, 500, 23, "",
     "Shared w/ Shadower, Maple Hero (NL) target. Hybrid row: Calc columns D-I are computed "
     "exactly like a normal damage row (so Maple Hero (NL)'s MapleHeroMultiplier applies "
     "unchanged) but Calc!O is forced to 0 — it isn't an independent hit. Instead "
     "Summary!ShadowPartnerAvgMult reads this row's Calc!F/Calc!I directly and folds into the "
     "shared extra_mult chain every other row's K-column formula uses. factorIndex 21, "
     "baseDamage 840 tenths% (84%->151.2%, levels 1-200). ProcChance% is the real 25% proc rate. "
     "SkillMasteryBonus% is Mastery Lv.66 ('Shadow Partner - Damage', +100%, unaffected by "
     "the patch)."),
    ("QUAD_STAR", "Quad Star", 4,
     f"=IF({IB('level')}>=106,10*0.7,10)", True, 1, 4, 0, 0, 100, 1,
     11500, 12, True,
     level_gated_sum(IB("level"), {132: 50}), 0, 0, 0, 0, 0,
     f"=IF({IB('level')}>=106,30,0)", 0,
     1, "", 0, True, "", "", "",
     "Single-target. factorIndex 12, baseDamage 11500 tenths% (1150%->2300%, levels 1-200). "
     "Mastery Lv.106 (-30% cooldown, baked into the Cooldown(s) formula above, MasteryCooldownPct "
     "reference-only) and Lv.132 (+50% damage, real SkillMasteryBonus%)."),
    ("SUDDEN_RAID_BURST", "Sudden Raid (burst)", 4, 19, True, 1, 3, 0, 0, 100, 1,
     14000, 12, True,
     level_gated_sum(IB("level"), {124: 50}), 0, 0, 0, 0, 0, 0, 0,
     8, "", 0, True, "", "", "",
     "Shared w/ Shadower. factorIndex 12, baseDamage 14000 tenths% (1400%->2800%, levels "
     "1-200). Mastery Lv.124 +50% damage (real SkillMasteryBonus%; does not apply to the DoT "
     "row below, matching FP-Mage's own Poison Mist burst-vs-fog precedent)."),
    ("SUDDEN_RAID_DOT", "Sudden Raid (DoT)", 4, _SUDDEN_RAID_DOT_COOLDOWN, False, 1, 1, 1, 5, 100, 1,
     3600, 12, True,
     0, 0, 0, 0, 0, 0, 0, 0,
     8, "", 0, True, "", "", "",
     "Shares Sudden Raid (burst)'s live Cooldown(s) cell (same cross-reference pattern as "
     "FP-Mage's Mist Eruption <-> Poison Mist (burst)). factorIndex 12, baseDamage 3600 "
     "tenths% (360%->720%, levels 1-200), 5s window / 1s ICD = 5 EffectiveHits per cast."),
    ("FRAILTY_CURSE_SELF_FD", "Frailty Curse (self buff)", 4, 45, True, 1, 1, 0, 0, 100, 1,
     130, 22, True,
     0, 0, 0, 0, 0, 0, 0, 0,
     1, "FINAL_DAMAGE", 20, False, "", "", "",
     "20s zone / 45s cooldown, self Final Damage. factorIndex 22, baseDamage 130 tenths% "
     "(13%->20.8%, levels 1-200). Mastery Lv.111 adds a minor crit-damage-taken debuff to the "
     "enemy-facing row below — deliberately not modeled (plan calls it minor/optional; flagged "
     "as a known gap)."),
    ("FRAILTY_CURSE_DEBUFF", "Frailty Curse (enemy debuff)", 4, 45, False, 1, 1, 0, 0, 100, 1,
     180, 21, True,
     0, 0, 0, 0, 0, 0, 0, 0,
     1, "MONSTER_DMG", 20, False, "", "", "",
     "Same 20s zone / 45s cooldown as the self-buff row above (shares its Cooldown(s) literal, "
     "not a live cross-reference, since both are the same literal 45). Enemy Damage Taken +18%->"
     "32.4% (levels 1-200), factorIndex 21, baseDamage 180 tenths%. BuffTargetStat=MONSTER_DMG "
     "feeds global_monster_dmg_bonus_expr's boss/normal additive term (see build_calc_sheet), "
     "gated by the same uptime as the self-buff row (CostsActionSlot=False here — the self-buff "
     "row is the one that actually 'costs' the cast in the action economy)."),
    ("SHADOW_SHIFTER", "Shadow Shifter (counterattack)", 4, "", False, 1, 1, 0, 0, 100, 1,
     25000, 21, True,
     0, 0, 0, 0, 0, 0, 0, 0,
     1, "", 0, False, "", "", "",
     "Shared w/ Shadower. Counterattack DPS = Inputs!incoming_hit_rate * 20% * "
     "ExpectedDamage(counterHit) — driven by damage TAKEN, not the character's own cast rate, so "
     "this row has no Cooldown(s)/rate machinery of its own (bespoke O-column branch). "
     "factorIndex 21, baseDamage 25000 tenths% (2500%->4500%, levels 1-200). The wiki's own "
     "'Cooldown 12 sec' field on this skill is not modeled (the plan's formula treats the 20% "
     "chance as having no ICD at all) — flagged as an assumption to confirm."),
    ("SHADOW_SHIFTER_SELF_ATK", "Shadow Shifter (self Attack%)", 4, "", False, 1, 1, 0, 0, 100, 1,
     100, 22, True,
     0, 0, 0, 0, 0, 0, 0, 0,
     1, "ATTACK", 0, False, "", "", "",
     "Passive-mult delta-tracking row for Shadow Shifter's self Attack% (10%->16%, levels "
     "1-200) — assumed already baked into Inputs!ATTACK_PCT (Magic Critical pattern), so not "
     "added to baseline DPS. factorIndex 22, baseDamage 100 tenths%. Per the plan, this buff's "
     "*uptime* is reduced below 1 by counterattack procs (disabled 3s per proc, pre-Mastery-116) "
     "— SelfAttackBuffUptime is computed in build_summary_sheet, but the Sensitivity sheet's own "
     "delta for this row is NOT scaled by that uptime in this pass (a known simplification — "
     "flagged for human review, see the plan's explicit note that this is 'the one passive-mult "
     "row that also needs a live uptime term multiplying its Sensitivity delta')."),
    ("NIMBLE_FEET", "Nimble Feet", 1, 60, True, 1, 1, 0, 0, 100, 1,
     150, 0, False,
     0, 0, 0, 0, 0, 0, 0, 0,
     1, "ATTACK_SPEED", 15, False, "", "", "",
     "Shared Explorer skill, flat +15% Attack Speed / +10% Speed for 15s, 60s cooldown — "
     "confirmed non-scaling ('does not improve on enhancement' per its own wiki page), same "
     "convention as FP-Mage's own Nimble Feet row (FactorIndex unused placeholder)."),
    ("DARK_SIGHT_CRIT", "Dark Sight (Crit Rate)", 1, 25, False, 1, 1, 0, 0, 100, 1,
     60, 21, True,
     0, 0, 0, 0, 0, 0, 0, 0,
     1, "CRIT_RATE", f"=IF({IB('level')}>=24,12,8)", False, "", "", "",
     "Two-stage activation (hide 8s, re-press within window) grants +6%->8.4% Crit Rate for 8s "
     "(levels 1-100, ->12s once Mastery Lv.24 'Dark Sight - Persistence' unlocks: +50% buff "
     "duration) — factorIndex 21, baseDamage 60 tenths%. This row is a passenger "
     "(CostsActionSlot=False) — the Attack-targeting row below is the one that counts toward "
     "the action economy (both presses of the 2-stage activation, via ActionsPerCast=2), per "
     "the plan's 'costs 2 action-slots per 25s cycle' assumption (flagged for human review)."),
    ("DARK_SIGHT_ATK", "Dark Sight (Attack)", 1, 25, True, 2, 1, 0, 0, 100, 1,
     100, 21, True,
     0, 0, 0, 0, 0, 0, 0, 0,
     1, "ATTACK", f"=IF({IB('level')}>=24,12,8)", False, "", "", "",
     "Same 2-stage activation as the Crit Rate row above, +10%->14% Attack for 8s (levels "
     "1-100, ->12s once Mastery Lv.24 unlocks, same as the Crit Rate row) — factorIndex 21, "
     "baseDamage 100 tenths%. ActionsPerCast=2 models both presses "
     "(hide + re-press) as separate action-slot costs within the same 25s cycle."),
    ("AGILE_CLAWS", "Agile Claws (Claw Acceleration)", 2, "", False, 1, 1, 0, 0, 100, 1,
     50, 22, True,
     0, 0, 0, 0, 0, 0, 0, 0,
     1, "ATTACK_SPEED", 0, False, "", "", "",
     "Permanent passive, +5%->6.5% Attack Speed (levels 1-100) — assumed already in "
     "Inputs!ATTACK_SPEED% (Magic Critical pattern); this row only feeds the 2nd-Job Skill "
     "Level Bonus Sensitivity delta. factorIndex 22, baseDamage 50 tenths%."),
    ("PHYSICAL_TRAINING", "Physical Training", 2, "", False, 1, 1, 0, 0, 100, 1,
     100, 22, True,
     0, 0, 0, 0, 0, 0, 0, 0,
     1, "BASIC_ATTACK_DAMAGE", 0, False, "", "", "",
     "Permanent passive, +10%->13% Basic Attack Damage (levels 1-100) — assumed already in "
     "Inputs!BASIC_ATTACK_DAMAGE% (Magic Critical pattern); feeds the 2nd-Job Skill Level Bonus "
     "delta. factorIndex 22, baseDamage 100 tenths%."),
    ("CLAW_MASTERY", "Claw Mastery", 2, "", False, 1, 1, 0, 0, 100, 1,
     150, 22, True,
     0, 0, 0, 0, 0, 0, 0, 0,
     1, "MIN_DAMAGE", 0, False, "", "", "",
     "Permanent passive, +15%->19.5% Min Damage Multiplier (levels 1-100) — assumed already in "
     "Inputs!MIN_DAMAGE% (Magic Critical pattern); feeds the 2nd-Job Skill Level Bonus delta. "
     "factorIndex 22, baseDamage 150 tenths%."),
    ("CRITICAL_THROW_RATE", "Critical Throw (Crit Rate)", 2, "", False, 1, 1, 0, 0, 100, 1,
     60, 22, True,
     0, 0, 0, 0, 0, 0, 0, 0,
     1, "CRIT_RATE", 0, False, "", "", "",
     "Permanent passive, +6%->7.8% Crit Rate (levels 1-100) — assumed already in "
     "Inputs!CRIT_RATE% (Magic Critical pattern); feeds the 2nd-Job Skill Level Bonus delta. "
     "factorIndex 22, baseDamage 60 tenths%. Mastery Lv.47's +8%p Crit Rate is a SEPARATE "
     "always-on mastery addition (global_crit_rate_bonus_expr in build_calc_sheet), NOT part of "
     "this delta."),
    ("CRITICAL_THROW_DMG", "Critical Throw (Crit Damage)", 2, "", False, 1, 1, 0, 0, 100, 1,
     100, 22, True,
     0, 0, 0, 0, 0, 0, 0, 0,
     1, "CRIT_DAMAGE", 0, False, "", "", "",
     "Same skill as the Crit Rate row above, +10%->13% Crit Damage (levels 1-100) — assumed "
     "already in Inputs!CRIT_DAMAGE% (Magic Critical pattern); feeds the 2nd-Job Skill Level "
     "Bonus delta. factorIndex 22, baseDamage 100 tenths%."),
    ("ENVELOPING_DARKNESS", "Enveloping Darkness", 3, "", False, 1, 1, 0, 0, 100, 1,
     180, 22, True,
     0, 0, 0, 0, 0, 0, 0, 0,
     1, "BOSS_DAMAGE", 0, False, "", "", "",
     "Permanent passive, +18%->28.8% Boss Monster Damage (levels 1-200; Max HP part dropped, "
     "no DPS relevance) — assumed already in Inputs!BOSS_DAMAGE% (Magic Critical pattern); "
     "feeds the 3rd-Job Skill Level Bonus delta. factorIndex 22, baseDamage 180 tenths%."),
    ("EXPERT_THROWING_STAR_HANDLING", "Expert Throwing Star Handling", 3, "", False, 1, 1, 0, 0, 100, 1,
     180, 22, True,
     0, 0, 0, 0, 0, 0, 0, 0,
     1, "ATTACK", 0, False, "", "", "",
     "Permanent passive, +18%->28.8% Attack (levels 1-200) — assumed already in Inputs!ATTACK% "
     "(Magic Critical pattern); feeds the 3rd-Job Skill Level Bonus delta. factorIndex 22, "
     "baseDamage 180 tenths%."),
    ("CLAW_EXPERT", "Claw Expert", 4, "", False, 1, 1, 0, 0, 100, 1,
     150, 22, True,
     0, 0, 0, 0, 0, 0, 0, 0,
     1, "SKILL_DAMAGE", 0, False, "", "", "",
     "Permanent passive, +15%->24% Skill Damage, +20%->32% Max Damage Multiplier (levels "
     "1-200) — assumed already in Inputs!SKILL_DAMAGE%/MAX_DAMAGE% (Magic Critical pattern); "
     "feeds the 4th-Job Skill Level Bonus delta (Skill Damage side; Max Damage Multiplier isn't "
     "independently swept on the Sensitivity sheet, same as FP-Mage's own scope). factorIndex "
     "22, baseDamage 150 tenths% (Skill Damage curve; Max Damage Multiplier curve is identical "
     "in shape, 20%->32%, not separately tracked as its own row)."),
    ("DARK_HARMONY", "Dark Harmony", 4, "", False, 1, 1, 0, 0, 100, 1,
     120, 22, True,
     0, 0, 0, 0, 0, 0, 0, 0,
     1, "FINAL_DAMAGE", 0, False, "", "", "",
     "Permanent passive, Final Damage +15%(base)->patched 12% (curve shape unchanged, 12%->"
     "19.2%(@lvl100) scaled from the unpatched 15%->24% wiki curve), +20%->32% Min Damage "
     "Multiplier (levels 1-200) — assumed already in Inputs!FINAL_DAMAGE%/MIN_DAMAGE% (Magic "
     "Critical pattern); feeds the 4th-Job Skill Level Bonus delta (Final Damage side). "
     "factorIndex 22, baseDamage 120 tenths% (12% patched base)."),
    ("NIGHT_LORDS_MARK", "Night Lord's Mark", 4, "", False, 1, 1, 0, 0, 100, 1,
     3000, 21, True,
     0, 0, 0, 0, 0, 0, 0, 0,
     1, "", 0, False, "", "", "",
     "Permanent passive feeding Assassin's Mark only (+3 max targets, +300%->540% Final Damage "
     "to Assassin's Mark, levels 1-200) — a real, always-on contributor, NOT baked into Inputs "
     "(unlike every 'passive-mult' row above) since it has no matching generic Inputs field; "
     "same Element-Amplification-style treatment FP-Mage uses. No independent DPS row (Calc "
     "columns G-O blank/0) — only D/E/F (its own scaling coefficient) are computed. factorIndex "
     "21, baseDamage 3000 tenths%."),
]

# Rows with a real Cooldown(s) value (literal or a live formula reference) — CastsInFight
# (fixed-duration mode) is only meaningful for these.
ROW_HAS_COOLDOWN = {row[0]: row[3] not in ("", None) for row in SKILL_ROWS}

# Mist-Eruption-style "which row's CostsActionSlot governs this row's own CDR eligibility"
# override — every Night Lord row here checks its own CostsActionSlot (identity default), so
# this is trivial, but kept for structural parity with build_fp_mage_workbook.py.
CDR_COSTS_ACTION_ROW = {key: r for key, r in ROW.items()}


def build_skills_sheet(wb):
    ws = wb.create_sheet("Skills")
    for i, name in enumerate(SKILL_COLUMNS):
        ws.cell(row=1, column=i + 1, value=name)
    style_header_row(ws, 1, len(SKILL_COLUMNS))

    for row_data in SKILL_ROWS:
        key = row_data[0]
        r = ROW[key]
        for i, val in enumerate(row_data):
            ws.cell(row=r, column=i + 1, value=val)

    widths = [26, 30, 8, 11, 15, 13, 11, 8, 13, 11, 12, 18, 11, 14, 17, 16, 18, 17, 16, 16,
              17, 20, 18, 15, 14, 16, 20, 20, 8, 60]
    for i, w in enumerate(widths):
        ws.column_dimensions[get_column_letter(i + 1)].width = w
    ws.freeze_panes = "A2"
    return ws


# ---------------------------------------------------------------------------
# Row categories consumed by build_calc_sheet/build_summary_sheet/build_sensitivity_sheet.
# ---------------------------------------------------------------------------
DAMAGE_ROW_KEYS = [
    "GUST_CHARM", "MARK_OF_ASSASSIN", "TRIPLE_THROW", "DARK_FLARE", "VENOM",
    "QUAD_STAR", "SUDDEN_RAID_BURST", "SUDDEN_RAID_DOT",
]
# Real, always-on buff rows (NOT baked into Inputs) whose (F * uptime) feeds a shared baseline
# multiplier/additive slot every hit uses — mirrors FP-Mage's BUFF_ROW_KEYS/Magic Guard pattern.
BUFF_ROW_KEYS = ["NIMBLE_FEET", "DARK_SIGHT_CRIT", "DARK_SIGHT_ATK",
                 "FRAILTY_CURSE_SELF_FD", "FRAILTY_CURSE_DEBUFF"]
# Alchemic Adrenaline's two rows — real buff contributors like BUFF_ROW_KEYS, but with a bespoke
# action-rate-driven uptime (AdrenalinUptime in build_summary_sheet) instead of the generic
# BuffDuration(s)/Cooldown(s) ratio.
ADRENALIN_ROW_KEYS = ["ADRENALIN_FD", "ADRENALIN_AS"]
# "Magic Critical pattern" rows: permanent passives assumed already reflected in a matching
# Inputs% field. Calc columns J-O stay blank/0; Calc!F is used ONLY by the Sensitivity sheet's
# matching Skill-Level-Bonus block as a marginal delta (this row's F at the swept level minus its
# F at the current level) — never added to baseline DPS.
PASSIVE_MULT_ROW_KEYS = [
    "AGILE_CLAWS", "PHYSICAL_TRAINING", "CLAW_MASTERY", "CRITICAL_THROW_RATE",
    "CRITICAL_THROW_DMG", "ENVELOPING_DARKNESS", "EXPERT_THROWING_STAR_HANDLING",
    "CLAW_EXPERT", "DARK_HARMONY", "SHADOW_SHIFTER_SELF_ATK",
]
HYBRID_ROW_KEYS = ["SHADOW_PARTNER"]
TOXIC_VENOM_ROW_KEYS = ["TOXIC_VENOM"]
SHADOW_SHIFTER_ROW_KEYS = ["SHADOW_SHIFTER"]
# Every row that can ever post a nonzero Calc!O DPS value — used to filter the Summary sheet's
# per-skill breakdown table down to real damage sources (buffs/passives always show 0.0000 there).
DAMAGE_DEALING_KEYS = ["SHOWDOWN"] + DAMAGE_ROW_KEYS + TOXIC_VENOM_ROW_KEYS + SHADOW_SHIFTER_ROW_KEYS
# Real, always-on scaling contributor with no matching Inputs field (Element-Amplification-style)
# that feeds another row's own MasteryFinalDamage% term rather than having its own DPS.
NIGHT_LORDS_MARK_ROW_KEYS = ["NIGHT_LORDS_MARK"]
# BuffTargetStat values that fold into the shared multiplicative avg_buff_mult chain (mirrors
# FP-Mage folding both ATTACK- and FINAL_DAMAGE-target buffs into one multiplicative slot).
AVG_BUFF_MULT_TARGETS = {"ATTACK", "FINAL_DAMAGE"}
# BuffTargetStat values consumed additively into the crit-rate blend instead.
CRIT_RATE_BUFF_TARGETS = {"CRIT_RATE"}

CALC_HEADERS = [
    "Key", "Name", "Unlocked", "InputLevel", "Factor", "CoefficientPercent",
    "EffectiveHits", "ProcProbability", "MapleHeroMultiplier",
    "BaseDamage", "BaseHitDamage", "NonCritAvg", "CritAvg", "ExpectedDamage(perHit)",
    "DPS", "% of Total", "InvCooldown", "CastsInFight", "HitRate(perSec)",
]
CCOL = {name: get_column_letter(i + 1) for i, name in enumerate(CALC_HEADERS)}


def S(col_name, r):
    """Shorthand for a Skills-sheet cell reference by column name, e.g. S('Cooldown(s)', 3)."""
    return f"Skills!{SC[col_name]}{r}"


# ---------------------------------------------------------------------------
# Summary-sheet row layout — fixed constants (referenced by build_calc_sheet's formula
# strings, which are written before build_summary_sheet runs; cross-sheet references don't
# care about python build order, only true circularity, and there is none here).
# ---------------------------------------------------------------------------
R_TOTAL = 3
SUMMARY_BREAKDOWN_HEADER_ROW = 6
R_AVGBUFF = 57                 # Average Buff Multiplier (Dark Sight Attack + Frailty Curse self-FD + Adrenalin FD)
R_CRIT_RATE_BONUS = 58          # Critical Throw Lv.47 mastery + Dark Sight (Crit Rate), additive to Inputs!crit_rate
R_MONSTER_DMG_BONUS = 59        # Venom Lv.82 Weaken + Frailty Curse (enemy debuff), additive to Monster Damage%
R_SHADOW_PARTNER_MULT = 60      # Shadow Partner average multiplier
R_APS_PRE_ADRENALIN = 61        # Actions/sec using only Nimble Feet's AS bonus (breaks the Adrenalin<->ActionsPerSecond cycle)
R_ADRENALIN_UPTIME = 62         # Alchemic Adrenaline uptime (action-rate-driven cycle)
R_AS_BONUS = 63                 # Combined Attack Speed buff bonus % (Nimble Feet + Adrenalin AS, averaged)
R_APS = 64                      # Final Actions Per Second
R_CASTRATE = 65                 # Skill + buff cast rate (subtracted from Basic Attacks Per Second)
R_BAPS = 66                     # Basic Attacks (Showdown) Per Second
R_SELFATK_UPTIME = 67           # Shadow Shifter self-Attack buff uptime (informational; see Note)
R_CRIT_DAMAGE_BONUS = 68        # Frailty Curse Mastery Lv.111 (+30% Critical Damage Taken), duty-cycle-averaged, additive to Inputs!crit_damage
R_SHOWDOWN_DPS = 69

# Frailty Curse's self-buff and enemy-debuff rows share the same literal Cooldown(s)/BuffDuration(s)
# (both 45/20, mastery-unaffected in this pass) — buff_uptime() below is generic per-row.


def buff_uptime_expr(fda_ref, monster_type_ref, row, bdi_ref, fight_duration_ref, calc_r_col_ref):
    """Steady-state or exact-duration uptime fraction for a real buff row (BUFF_ROW_KEYS)."""
    return uptime_fraction_or_exact_expr(
        fda_ref, calc_r_col_ref, monster_type_ref, S("BuffDuration(s)", row), S("Cooldown(s)", row),
        bdi_ref, fight_duration_ref,
    )


def build_calc_sheet(wb):
    ws = wb.create_sheet("Calc")
    for i, name in enumerate(CALC_HEADERS):
        ws.cell(row=1, column=i + 1, value=name)
    style_header_row(ws, 1, len(CALC_HEADERS))

    # Maple Hero (NL) helper cells (jobStep4, factorIndex23) — lives off to the side, mirrors
    # build_fp_mage_workbook.py's own Z1-Z3 Maple Hero helper cells.
    ws["U1"] = "Maple Hero (NL) helper (jobStep4, factorIndex23)"
    ws["U1"].font = LABEL_FONT
    ws["U2"] = f'=MAX(0,({IB("level")}-100)*3)+{IB("skill_lvl_4th")}+{IB("skill_lvl_all")}'
    ws["U3"] = f'=INDEX(FactorTable!$B$2:$Y$301, MATCH(ROUND(MIN(300,MAX(1,U2)),0), FactorTable!$A$2:$A$301,0), 24)'

    fixed_duration_active_main = fixed_duration_active_expr(IB("monster_type"), IB("fight_duration"))
    bdi_main = IB("buff_duration_increase_pct")  # no Buff-Mastery-equivalent skill in this kit

    monster_dmg_bonus_ref = f"Summary!$B${R_MONSTER_DMG_BONUS}"
    crit_rate_total_ref = f'({IB("crit_rate")}+Summary!$B${R_CRIT_RATE_BONUS})'
    avg_buff_mult_ref = f"Summary!$B${R_AVGBUFF}"
    shadow_partner_mult_ref = f"Summary!$B${R_SHADOW_PARTNER_MULT}"

    # Rows needing the full D-N hit-damage pipeline (Showdown + every real damage row + the two
    # bespoke-rate rows that still hit like a normal attack) — everything except the hybrid row
    # (Shadow Partner, D-I only), Night Lord's Mark (D-F only), and the delta-only passive-mult/
    # buff rows (D-F + G/H/I only, no J-N/O).
    FULL_HIT_PIPELINE_KEYS = ["SHOWDOWN"] + DAMAGE_ROW_KEYS + TOXIC_VENOM_ROW_KEYS + SHADOW_SHIFTER_ROW_KEYS

    for key, r in ROW.items():
        ws.cell(row=r, column=1, value=f"={S('Key', r)}")
        ws.cell(row=r, column=2, value=f"={S('Name', r)}")
        ws.cell(row=r, column=3, value=unlock_expr(key))

        has_cooldown = ROW_HAS_COOLDOWN[key]
        if has_cooldown:
            eff_cd_r = effective_cooldown_expr(
                IB("monster_type"), S("Cooldown(s)", r), IB("skill_cooldown_decrease"),
                S("CostsActionSlot", CDR_COSTS_ACTION_ROW[key]),
            )
            rate_r = rate_or_exact_hits_expr(
                fixed_duration_active_main, f"R{r}", S("HitsPerCast", r), S("ICD(s)", r),
                S("ActiveWindow(s)", r), eff_cd_r, IB("fight_duration"), f"G{r}*Q{r}",
            )
        else:
            eff_cd_r = None
            rate_r = None

        # D/E/F — InputLevel / Factor / CoefficientPercent. Every scaling row (everything except
        # Showdown, which uses Inputs!skill_coefficient, and Nimble Feet, which is flat) shares
        # this same job-step formula.
        if key == "SHOWDOWN":
            ws.cell(row=r, column=4, value="")
            ws.cell(row=r, column=5, value="")
            ws.cell(row=r, column=6, value=f"={IB('skill_coefficient')}+{S('SkillMasteryBonus%', r)}")
        else:
            ws.cell(row=r, column=4, value=(
                f'=IF({S("JobStep", r)}=1,60+{IB("skill_lvl_1st")}+{IB("skill_lvl_all")},'
                f'IF({S("JobStep", r)}=2,90+{IB("skill_lvl_2nd")}+{IB("skill_lvl_all")},'
                f'IF({S("JobStep", r)}=3,120+{IB("skill_lvl_3rd")}+{IB("skill_lvl_all")},'
                f'MAX(0,({IB("level")}-100)*3)+{IB("skill_lvl_4th")}+{IB("skill_lvl_all")})))'
            ))
            ws.cell(row=r, column=5, value=(
                f'=INDEX(FactorTable!$B$2:$Y$301, MATCH(ROUND(MIN(300,MAX(1,D{r})),0), '
                f'FactorTable!$A$2:$A$301,0), {S("FactorIndex", r)}+1)'
            ))
            ws.cell(row=r, column=6, value=(
                f'=IF({S("ScalesWithLevel", r)}=TRUE,({S("BaseDamage(tenths%)", r)}/10)*(E{r}/1000),'
                f'{S("BaseDamage(tenths%)", r)}/10)+{S("SkillMasteryBonus%", r)}'
            ))

        # G/H/I — EffectiveHits / ProcProbability / MapleHeroMultiplier, generic for every row
        # (blank G/H/I are harmless for the D-F-only rows, matches FP-Mage's own convention).
        ws.cell(row=r, column=7, value=(
            f'={S("HitsPerCast", r)}*IF({S("ICD(s)", r)}>0,{S("ActiveWindow(s)", r)}/{S("ICD(s)", r)},1)'
        ))
        ws.cell(row=r, column=8, value=f'=1-(1-{S("ProcChance%", r)}/100)^{S("RollsPerCast", r)}')
        ws.cell(row=r, column=9, value=(
            f'=IF({S("MapleHeroBase(tenths%)", r)}<>"",'
            f'1+({S("MapleHeroBase(tenths%)", r)}/10)*($U$3/1000)/100,1)'
        ))

        if key in FULL_HIT_PIPELINE_KEYS:
            ws.cell(row=r, column=10, value=f'={IB("attack")}*(F{r}/100)')
            monster_dmg_term = monster_blend_expr(
                IB("monster_type"), IB("normal_weight_frac"),
                f'{IB("boss_damage")}+{S("MasteryBossDamage%", r)}+{monster_dmg_bonus_ref}',
                f'{IB("normal_damage")}+{S("MasteryNormalDamage%", r)}+{monster_dmg_bonus_ref}',
                "0",
            )
            ws.cell(row=r, column=11, value=(
                f'=J{r}*(1+{IB("stat_damage")}/100)*(1+{IB("damage")}/100)'
                f'*(1+{monster_dmg_term}/100)'
                f'*(1+{IB("damage_amp")}/100)'
                f'*(5000/(6000+{IB("monster_defense")}*(1-{IB("def_pen")}/100)))'
                f'*(1+{IB("final_damage")}/100)*(1+{S("MasteryFinalDamage%", r)}/100)'
                f'*(1+(IF({S("Key", r)}="SHOWDOWN",{IB("basic_attack_damage")},{IB("skill_damage")}))/100)'
                f'*({avg_buff_mult_ref}*{shadow_partner_mult_ref}*I{r})'
            ))
            ws.cell(row=r, column=12, value=f'=K{r}*(MIN({IB("min_damage")},{IB("max_damage")})/100+{IB("max_damage")}/100)/2')
            ws.cell(row=r, column=13, value=f'=L{r}*(1+({IB("crit_damage")}+Summary!$B${R_CRIT_DAMAGE_BONUS})/100)')
            ws.cell(row=r, column=14, value=(
                f'=L{r}*(1-MIN({crit_rate_total_ref},100)/100)+M{r}*(MIN({crit_rate_total_ref},100)/100)'
            ))
        elif key in HYBRID_ROW_KEYS:
            for col in (10, 11, 12, 13, 14):
                ws.cell(row=r, column=col, value="")
        else:
            for col in (10, 11, 12, 13, 14):
                ws.cell(row=r, column=col, value="")

        # O — DPS, dispatched by category.
        if key == "SHOWDOWN":
            ws.cell(row=r, column=15, value=(
                f"=IF(C{r},{S('HitsPerCast', r)}*N{r}*Summary!$B${R_BAPS}*"
                f"{target_multiplier_expr(IB('monster_type'), IB('normal_weight_frac'), S('NormalMonsterTargets', r), IB('max_enemies_hit'))},0)"
            ))
        elif key in DAMAGE_ROW_KEYS:
            ws.cell(row=r, column=15, value=(
                f'=IF(C{r},H{r}*N{r}*{rate_r}*'
                f"{target_multiplier_expr(IB('monster_type'), IB('normal_weight_frac'), S('NormalMonsterTargets', r), IB('max_enemies_hit'))},0)"
            ))
        elif key in TOXIC_VENOM_ROW_KEYS:
            total_hit_rate = (
                f'SUMPRODUCT((Skills!{SC["TriggersToxicVenom"]}2:{SC["TriggersToxicVenom"]}{LAST_ROW}=TRUE)*'
                f'(C2:C{LAST_ROW}=TRUE)*S2:S{LAST_ROW})'
            )
            ws.cell(row=r, column=15, value=f'=IF(C{r},0.2*{total_hit_rate}*N{r},0)')
        elif key in SHADOW_SHIFTER_ROW_KEYS:
            ws.cell(row=r, column=15, value=f'=IF(C{r},{IB("incoming_hit_rate")}*0.2*N{r},0)')
        else:
            ws.cell(row=r, column=15, value=0)

        ws.cell(row=r, column=16, value=f'=IF(Summary!$B${R_TOTAL}=0,0,O{r}/Summary!$B${R_TOTAL})')

        # Q — safe per-row reciprocal cooldown (Excel @-implicit-intersection workaround, see
        # FP_MAGE_PROJECT_NOTES.md — a single-cell IFERROR call, never a range nested inside one).
        ws.cell(row=r, column=17, value=(f'=IFERROR(1/{eff_cd_r},0)' if has_cooldown else 0))

        # R — CastsInFight (fixed-duration mode only).
        if has_cooldown:
            ws.cell(row=r, column=18, value=(
                f'=IF({fixed_duration_active_main},{exact_casts_expr(IB("fight_duration"), eff_cd_r)},0)'
            ))
        else:
            ws.cell(row=r, column=18, value=0)

        # S — HitRate(perSec): the same proc-adjusted, target-multiplied hit rate already baked
        # into O (before the ExpectedDamage multiply) — O{r}/N{r} recovers it exactly for every
        # row using the standard H*N*rate*targetMult / HitsPerCast*N*rate*targetMult shape
        # (Showdown, DAMAGE_ROW_KEYS); 0 for every other row (IFERROR catches blank-cell errors).
        # Feeds Toxic Venom's own trigger-rate SUMPRODUCT above, gated by Skills!TriggersToxicVenom.
        # Toxic Venom's OWN row is hardcoded to literal 0 here (never =O/N) — its own O formula
        # already reads this same S2:S{LAST_ROW} range, so S{TOXIC_VENOM row}=O{that row}/N{that
        # row} would be a genuine circular reference (harmless mathematically, since
        # TriggersToxicVenom=FALSE zeroes its contribution either way, but Excel/`formulas` still
        # has to resolve the cycle to know that).
        if key in TOXIC_VENOM_ROW_KEYS:
            ws.cell(row=r, column=19, value=0)
        else:
            ws.cell(row=r, column=19, value=f'=IFERROR(O{r}/N{r},0)')

    ws.cell(row=1, column=17, value="InvCooldown")
    ws.cell(row=1, column=18, value="CastsInFight")
    ws.cell(row=1, column=19, value="HitRate(perSec)")

    widths = [26, 30, 10, 12, 9, 15, 13, 14, 17, 13, 15, 12, 12, 17, 12, 10, 12, 12, 14]
    for i, w in enumerate(widths):
        ws.column_dimensions[get_column_letter(i + 1)].width = w
    ws.freeze_panes = "C2"
    return ws


def build_summary_sheet(wb):
    ws = wb.create_sheet("Summary")
    ws["A1"] = "Night Lord — DPS Summary"
    ws["A1"].font = Font(bold=True, size=14)

    ws.cell(row=DERIVED_HEADER_ROW, column=1, value="Derived Values (read-only, computed from Inputs)").font = SECTION_FONT
    ws.cell(row=D_ATTACK, column=1, value="ATTACK (= Flat ATTACK x (1+ATTACK%/100))")
    ws.cell(row=D_ATTACK, column=2, value=f'={IB("flat_attack")}*(1+{IB("attack_pct")}/100)')

    ws.cell(row=D_STAT_DAMAGE, column=1, value="STAT_DAMAGE % (= 1% of total LUK + 0.25% of DEX)")
    ws.cell(
        row=D_STAT_DAMAGE, column=2,
        value=f'=({IB("flat_luk")}*(1+{IB("luk_pct")}/100))*0.01+{IB("dex")}*0.0025'
    )

    ws.cell(row=D_BASIC_INPUT_LEVEL, column=1, value="Basic Attack (Showdown) Input Level (4th job formula)")
    ws.cell(
        row=D_BASIC_INPUT_LEVEL, column=2,
        value=f'=MAX(0,({IB("level")}-100)*3)+{IB("skill_lvl_4th")}+{IB("skill_lvl_all")}'
    )
    ws.cell(row=D_BASIC_FACTOR, column=1, value="Basic Attack Factor (factorIndex 21, from Showdown reverse-engineering)")
    ws.cell(
        row=D_BASIC_FACTOR, column=2,
        value=f'=INDEX(FactorTable!$B$2:$Y$301, MATCH(ROUND(MIN(300,MAX(1,{IB("basic_input_level")})),0), '
              f'FactorTable!$A$2:$A$301,0), 22)'
    )
    ws.cell(row=D_SKILL_COEFFICIENT, column=1, value="SKILL_COEFFICIENT — Showdown base coefficient % (before Skill Mastery)")
    ws.cell(row=D_SKILL_COEFFICIENT, column=2, value=f'=290*{IB("basic_factor")}/1000')

    ws.cell(row=D_NORMAL_WEIGHT_FRAC, column=1, value=(
        "Normal-Monster Weight (= 0 for boss, 1 for normal, "
        "Breakthrough Normal Weight % for breakthrough, 0 for pvp)"
    ))
    ws.cell(
        row=D_NORMAL_WEIGHT_FRAC, column=2,
        value=(
            f'=IF({IB("monster_type")}="normal",1,'
            f'IF({IB("monster_type")}="breakthrough",{IB("breakthrough_normal_weight_pct")}/100,0))'
        )
    )

    fda_main = fixed_duration_active_expr(IB("monster_type"), IB("fight_duration"))
    bdi_main = IB("buff_duration_increase_pct")

    def buff_uptime(row):
        return uptime_fraction_or_exact_expr(
            fda_main, f'Calc!R{row}', IB("monster_type"), S("BuffDuration(s)", row), S("Cooldown(s)", row),
            bdi_main, IB("fight_duration"),
        )

    r_nf, r_dsc, r_dsa = ROW["NIMBLE_FEET"], ROW["DARK_SIGHT_CRIT"], ROW["DARK_SIGHT_ATK"]
    r_fcs, r_fcd = ROW["FRAILTY_CURSE_SELF_FD"], ROW["FRAILTY_CURSE_DEBUFF"]
    r_afd, r_aas = ROW["ADRENALIN_FD"], ROW["ADRENALIN_AS"]
    r_sp = ROW["SHADOW_PARTNER"]

    # Every buff-average term below is gated by its own row's Unlocked flag (Calc!C<row>=TRUE) —
    # buff_uptime()'s steady-state/exact-duration formula does NOT itself check unlock status
    # (only Calc!O's DPS dispatch does), so omitting this multiply here would silently apply a
    # below-unlock-level buff's full value regardless of character level (the exact
    # "Unlocked-Gate Bypass" pitfall documented in FP_MAGE_PROJECT_NOTES.md).
    nimble_feet_avg = f'((Calc!C{r_nf}=TRUE)*Calc!F{r_nf}*{buff_uptime(r_nf)})'
    dark_sight_crit_avg = f'((Calc!C{r_dsc}=TRUE)*Calc!F{r_dsc}*{buff_uptime(r_dsc)})'
    dark_sight_atk_avg = f'((Calc!C{r_dsa}=TRUE)*Calc!F{r_dsa}*{buff_uptime(r_dsa)})'
    frailty_self_fd_avg = f'((Calc!C{r_fcs}=TRUE)*Calc!F{r_fcs}*{buff_uptime(r_fcs)})'
    frailty_debuff_avg = f'((Calc!C{r_fcd}=TRUE)*Calc!F{r_fcd}*{buff_uptime(r_fcd)})'

    # Actions/sec computed WITHOUT Adrenalin's own Attack Speed bonus first, specifically to
    # avoid a circular reference: Adrenalin's uptime (below) is derived from an actions/sec rate,
    # but Adrenalin's own AS bonus would otherwise feed back into that same actions/sec rate.
    # Using the "pre-Adrenalin" rate for the accumulation phase is also mechanically sensible —
    # while building toward the next Adrenalin trigger, Adrenalin itself isn't active yet.
    ws.cell(row=R_APS_PRE_ADRENALIN, column=1, value="Actions Per Second (pre-Adrenalin, Nimble Feet only — breaks the Adrenalin uptime cycle)")
    ws.cell(row=R_APS_PRE_ADRENALIN, column=2, value=(
        f'=1+MIN(150,150*(1-(1-{IB("attack_speed")}/150)*(1-{nimble_feet_avg}/150)))/100'
    ))

    activations_needed = 5  # patched from 7 (plan §3/§4)
    adrenalin_duration_scaled = f'({S("BuffDuration(s)", r_afd)}*(1+{bdi_main}/100))'
    adrenalin_accumulate_time = f'({activations_needed}/B{R_APS_PRE_ADRENALIN})'
    ws.cell(row=R_ADRENALIN_UPTIME, column=1, value="Alchemic Adrenaline Uptime (action-rate-driven cycle: BuffDuration/(BuffDuration+ActivationsNeeded/ActionsPerSecond_preAdrenalin))")
    ws.cell(row=R_ADRENALIN_UPTIME, column=2, value=(
        f'={adrenalin_duration_scaled}/({adrenalin_duration_scaled}+{adrenalin_accumulate_time})'
    ))

    adrenalin_as_avg = f'((Calc!C{r_aas}=TRUE)*Calc!F{r_aas}*B{R_ADRENALIN_UPTIME})'
    adrenalin_fd_avg = f'((Calc!C{r_afd}=TRUE)*Calc!F{r_afd}*B{R_ADRENALIN_UPTIME})'

    ws.cell(row=R_AS_BONUS, column=1, value="Attack Speed Buff Bonus % (Nimble Feet + Adrenalin, averaged)")
    ws.cell(row=R_AS_BONUS, column=2, value=f'={nimble_feet_avg}+{adrenalin_as_avg}')

    ws.cell(row=R_APS, column=1, value="Actions Per Second (final, incl. Adrenalin's own AS bonus)")
    ws.cell(row=R_APS, column=2, value=(
        f'=1+MIN(150,150*(1-(1-{IB("attack_speed")}/150)*(1-B{R_AS_BONUS}/150)))/100'
    ))

    ws.cell(row=R_CASTRATE, column=1, value="Skill + Buff Cast Rate (subtracted from Showdown, 1/s; weighted by ActionsPerCast)")
    ws.cell(row=R_CASTRATE, column=2, value=(
        f'=IF({fda_main},'
        f'SUMPRODUCT((Skills!{SC["CostsActionSlot"]}2:{SC["CostsActionSlot"]}{LAST_ROW}=TRUE)*'
        f'(Calc!C2:C{LAST_ROW}=TRUE)*Calc!R2:R{LAST_ROW}*Skills!{SC["ActionsPerCast"]}2:{SC["ActionsPerCast"]}{LAST_ROW})/{IB("fight_duration")},'
        f'SUMPRODUCT((Skills!{SC["CostsActionSlot"]}2:{SC["CostsActionSlot"]}{LAST_ROW}=TRUE)*'
        f'(Calc!C2:C{LAST_ROW}=TRUE)*Calc!Q2:Q{LAST_ROW}*Skills!{SC["ActionsPerCast"]}2:{SC["ActionsPerCast"]}{LAST_ROW}))'
    ))

    ws.cell(row=R_BAPS, column=1, value="Showdown (Basic Attack) Casts Per Second")
    ws.cell(row=R_BAPS, column=2, value=f'=MAX(0,B{R_APS}-B{R_CASTRATE})')

    ws.cell(row=R_AVGBUFF, column=1, value="Average Buff Multiplier (Dark Sight Attack + Frailty Curse self-FD + Adrenalin FD)")
    ws.cell(row=R_AVGBUFF, column=2, value=(
        f'=(1+{dark_sight_atk_avg}/100)*(1+{frailty_self_fd_avg}/100)*(1+{adrenalin_fd_avg}/100)'
    ))

    ws.cell(row=R_CRIT_RATE_BONUS, column=1, value="Global Crit Rate Bonus % (Critical Throw Lv.47 mastery + Dark Sight Crit Rate, additive)")
    ws.cell(row=R_CRIT_RATE_BONUS, column=2, value=f'=IF({IB("level")}>=47,8,0)+{dark_sight_crit_avg}')

    ws.cell(row=R_MONSTER_DMG_BONUS, column=1, value="Global Monster Damage-Taken Bonus % (Venom Lv.82 Weaken + Frailty Curse enemy debuff, additive)")
    ws.cell(row=R_MONSTER_DMG_BONUS, column=2, value=f'=IF({IB("level")}>=82,15,0)+{frailty_debuff_avg}')

    ws.cell(row=R_SHADOW_PARTNER_MULT, column=1, value="Shadow Partner Average Multiplier")
    ws.cell(row=R_SHADOW_PARTNER_MULT, column=2, value=(
        f'=1+((Calc!C{r_sp}=TRUE)*Calc!F{r_sp}*Calc!I{r_sp}*{S("ProcChance%", r_sp)}/100)/100'
    ))

    counter_proc_rate = f'({IB("incoming_hit_rate")}*0.2)'
    ws.cell(row=R_SELFATK_UPTIME, column=1, value="Shadow Shifter Self-Attack Buff Uptime (informational — see Skills!Note; Sensitivity delta not scaled by this in this pass)")
    ws.cell(row=R_SELFATK_UPTIME, column=2, value=(
        f'=IF({IB("level")}>=116,1,1-MIN(1,{counter_proc_rate}*3))'
    ))

    ws.cell(row=R_CRIT_DAMAGE_BONUS, column=1, value="Global Critical Damage Bonus % (Frailty Curse Mastery Lv.111, duty-cycle-averaged, additive)")
    ws.cell(row=R_CRIT_DAMAGE_BONUS, column=2, value=f'=IF({IB("level")}>=111,30,0)*{buff_uptime(r_fcd)}')

    ws.cell(row=R_TOTAL, column=1, value="TOTAL DPS").font = Font(bold=True, size=13)
    ws.cell(row=R_TOTAL, column=2, value=f"=SUM(Calc!O2:O{LAST_ROW})").font = Font(bold=True, size=13)

    ws.cell(row=R_SHOWDOWN_DPS, column=1, value="Showdown (Basic Attack) DPS")
    ws.cell(row=R_SHOWDOWN_DPS, column=2, value=f"=Calc!O{ROW['SHOWDOWN']}")

    ws.cell(row=SUMMARY_BREAKDOWN_HEADER_ROW - 1, column=1, value="Per-Skill DPS Breakdown").font = SECTION_FONT
    ws.cell(row=SUMMARY_BREAKDOWN_HEADER_ROW, column=1, value="Skill")
    ws.cell(row=SUMMARY_BREAKDOWN_HEADER_ROW, column=2, value="DPS")
    ws.cell(row=SUMMARY_BREAKDOWN_HEADER_ROW, column=3, value="% of Total")
    style_header_row(ws, SUMMARY_BREAKDOWN_HEADER_ROW, 3)
    row_cursor = SUMMARY_BREAKDOWN_HEADER_ROW + 1
    for key, r in ROW.items():
        if key not in DAMAGE_DEALING_KEYS:
            continue
        ws.cell(row=row_cursor, column=1, value=f"=Calc!B{r}")
        ws.cell(row=row_cursor, column=2, value=f"=Calc!O{r}")
        ws.cell(row=row_cursor, column=3, value=f"=Calc!P{r}*100")
        row_cursor += 1

    row_cursor += 1
    ws.cell(row=row_cursor - 1, column=1, value="Marginal DPS & Stat Value (see Sensitivity for full detail)").font = SECTION_FONT
    row_cursor += 1
    ws.cell(row=row_cursor, column=1, value="Stat")
    ws.cell(row=row_cursor, column=2, value="DPS per +1")
    ws.cell(row=row_cursor, column=3, value="Units per +1% DPS")
    style_header_row(ws, row_cursor, 3)
    row_cursor += 1
    for stat_key, stat_label, _kind in STAT_SWEEP:
        s_row = SENSITIVITY_ROW_FOR[stat_key]
        ws.cell(row=row_cursor, column=1, value=f"=Sensitivity!A{s_row}")
        ws.cell(row=row_cursor, column=2, value=f"=Sensitivity!H{s_row}")
        ws.cell(row=row_cursor, column=3, value=f"=Sensitivity!B{s_row}")
        row_cursor += 1

    ws.column_dimensions["A"].width = 60
    ws.column_dimensions["B"].width = 16
    ws.column_dimensions["C"].width = 12
    return ws


# ---------------------------------------------------------------------------
# Sensitivity sheet: marginal DPS from bumping each Inputs stat by +1, mirrors
# build_fp_mage_workbook.py's own Sensitivity sheet (plan §1's reuse list) — each swept stat
# gets a full, self-contained copy of the Calc+Summary formula pipeline (same-sheet refs) so
# its Total DPS is guaranteed correct by construction.
# ---------------------------------------------------------------------------
STAT_SWEEP = [
    ("flat_luk", "Flat LUK", "flat"),
    ("luk_pct", "LUK %", "pct"),
    ("dex", "DEX", "flat"),
    ("damage", "DAMAGE %", "pct"),
    ("damage_amp", "DAMAGE_AMP %", "pct"),
    ("boss_damage", "BOSS_DAMAGE %", "pct"),
    ("normal_damage", "NORMAL_DAMAGE %", "pct"),
    ("final_damage", "FINAL_DAMAGE % (multiplicative source)", "mult"),
    ("min_damage", "MIN_DAMAGE %", "pct"),
    ("max_damage", "MAX_DAMAGE %", "pct"),
    ("crit_rate", "CRIT_RATE %", "pct"),
    ("crit_damage", "CRIT_DAMAGE %", "pct"),
    ("attack_speed", "ATTACK_SPEED % (diminishing returns, factor 150)", "dr150"),
    ("def_pen", "DEF_PEN % (diminishing returns, factor 100)", "dr100"),
    ("basic_attack_damage", "BASIC_ATTACK_DAMAGE %", "pct"),
    ("skill_damage", "SKILL_DAMAGE %", "pct"),
    ("skill_lvl_1st", "Skill Level Bonus — 1st Job", "level"),
    ("skill_lvl_2nd", "Skill Level Bonus — 2nd Job", "level"),
    ("skill_lvl_3rd", "Skill Level Bonus — 3rd Job", "level"),
    ("skill_lvl_4th", "Skill Level Bonus — 4th Job", "level"),
    ("skill_lvl_all", "Skill Level Bonus — All Skills", "level"),
    ("flat_attack", "Flat ATTACK", "flat"),
    ("attack_pct", "ATTACK %", "pct"),
    ("skill_cooldown_decrease", "Skill Cooldown Decrease (seconds)", "flat"),
    ("basic_attack_target_increase", "Basic Attack Target Increase (flat)", "flat"),
    ("buff_duration_increase_pct", "Buff Duration Increase %", "pct"),
    ("incoming_hit_rate", "Incoming Hit Rate (hits/sec, Shadow Shifter only)", "flat"),
]

SENSITIVITY_HEADER_ROW = 4
SENSITIVITY_ROW_FOR = {key: SENSITIVITY_HEADER_ROW + 1 + idx for idx, (key, _, _) in enumerate(STAT_SWEEP)}

# Maps every stat name that can appear on a potential line (both the generic 16-stat pool and
# the 4 hand-added slot-specific stats, plus the 2 new rollable stats introduced this session)
# to its Sensitivity-sheet sweep key. Same shape as build_fp_mage_workbook.py's own map, with
# the main/sub stat identity swapped (LUK main / DEX sub instead of INT main / LUK sub). Stats
# not in this map (Str/Int flat & %, Dex/Dex % — Night Lord's own SUBSTAT, Defense %, Max HP %,
# Max MP %) have no combat impact for this LUK class and get a hardcoded 0 instead — mirrors
# FP-Mage's exact precedent for its own substat (Luk), a considered decision, not an oversight.
POTENTIAL_STAT_TO_SWEEP_KEY = {
    "Critical Rate %": "crit_rate",
    "Critical Damage %": "crit_damage",
    "Attack Speed %": "attack_speed",
    "Damage %": "damage",
    "Final Damage %": "final_damage",
    "Min Damage Multiplier %": "min_damage",
    "Max Damage Multiplier %": "max_damage",
    "Defense Penetration": "def_pen",
    "Luk %": "luk_pct",
    "Luk": "flat_luk",
    "Basic Attack Damage %": "basic_attack_damage",
    "Skill Damage %": "skill_damage",
    "Skill Cooldown Decrease (seconds)": "skill_cooldown_decrease",
    "Buff Duration Increase %": "buff_duration_increase_pct",
    "All Skill Level": "skill_lvl_all",
    "Basic Attack Target Increase": "basic_attack_target_increase",
}


def dps_per_unit_expr(stat_name):
    if stat_name == "Main Stat Per Level":
        # This roll's raw "value" is a per-level coefficient (e.g. 5 LUK per level), not a flat
        # amount — the actual flat LUK granted is coefficient*CharacterLevel (confirmed by the
        # user: level 115 x 5/level = 565 flat LUK). Rather than needing a live formula in the
        # Value column, fold the level scaling into DPSPerUnit instead: Flat LUK's own DPS-per-
        # unit times the live character level, so Value*DPSPerUnit still gives the right total.
        return f'=Sensitivity!H{SENSITIVITY_ROW_FOR["flat_luk"]}*{IB("level")}'
    if stat_name == "Main Stat % per 4 Levels":
        # Same pattern as Main Stat Per Level above, but stepped every 4 whole character levels,
        # not continuous (confirmed by the user) — the granted Luk % is coefficient*FLOOR(level/4),
        # so DPSPerUnit folds Luk %'s own DPS-per-unit times FLOOR(level/4) instead of level/4.
        return f'=Sensitivity!H{SENSITIVITY_ROW_FOR["luk_pct"]}*INT({IB("level")}/4)'
    if stat_name == "Critical Rate %":
        # Once Crit Rate is at/above the 100% cap, its own marginal DPS is genuinely zero — but
        # that understates its real worth for cube-EV comparisons: removing it would mean
        # replacing it with something else, and the natural replacement (same gearing "budget")
        # is Critical Damage %. So once capped, value a Crit Rate roll as if it were an
        # equal-sized Critical Damage % roll instead (confirmed by the user). This is scoped to
        # the cube-EV conversion only — the Sensitivity sheet's own Crit Rate row is left as the
        # literal (correctly zero-at-cap) marginal, since that's used for other purposes too.
        return (
            f'=IF({IB("crit_rate")}>=100,Sensitivity!H{SENSITIVITY_ROW_FOR["crit_damage"]},'
            f'Sensitivity!H{SENSITIVITY_ROW_FOR["crit_rate"]})'
        )
    if stat_name == "Companion Summoning Time Increase %":
        # Companions aren't modeled at all, so this stat's own DPS is genuinely zero — same
        # "understates its real worth" reasoning as Crit Rate above: removing it means replacing
        # it with something else, so value it as if it were an equal-sized Critical Damage %
        # roll instead (confirmed by the user). Unconditional, unlike Crit Rate's cap check,
        # since it's *never* modeled, not just past some threshold.
        return f'=Sensitivity!H{SENSITIVITY_ROW_FOR["crit_damage"]}'
    key = POTENTIAL_STAT_TO_SWEEP_KEY.get(stat_name)
    if key is None:
        return "0"
    return f"=Sensitivity!H{SENSITIVITY_ROW_FOR[key]}"


# Every "Magic Critical pattern" passive-mult row's Sensitivity-only delta consumption slot —
# which Inputs field its (local F - main F) marginal delta gets folded additively into within a
# Sensitivity block (never into the main Calc/Summary baseline). "attack_mult" has no literal
# Inputs field (mirrors FP-Mage folding ATTACK-target buffs into avg_buff_mult multiplicatively
# rather than a literal attack% field) — see build_stat_block.
PASSIVE_DELTA_SLOT = {
    "AGILE_CLAWS": "attack_speed",
    "PHYSICAL_TRAINING": "basic_attack_damage",
    "CLAW_MASTERY": "min_damage",
    "CRITICAL_THROW_RATE": "crit_rate",
    "CRITICAL_THROW_DMG": "crit_damage",
    "ENVELOPING_DARKNESS": "boss_damage",
    "EXPERT_THROWING_STAR_HANDLING": "attack_mult",
    "CLAW_EXPERT": "skill_damage",
    "DARK_HARMONY": "final_damage",
    "SHADOW_SHIFTER_SELF_ATK": "attack_mult",
}


def override_expr_for(kind, key):
    base = IB(key)
    if kind == "dr150":
        return f'((1-(1-{base}/150)*(1-1/150))*150)'
    if kind == "dr100":
        return f'((1-(1-{base}/100)*(1-1/100))*100)'
    if kind == "mult":
        return f'((((1+{base}/100)*(1.01))-1)*100)'
    return f'({base}+1)'


def make_ib(override_key, override_expr):
    def ib(key):
        if key == override_key:
            return override_expr
        if key == "attack":
            return f'({ib("flat_attack")}*(1+{ib("attack_pct")}/100))'
        if key == "stat_damage":
            return f'(({ib("flat_luk")}*(1+{ib("luk_pct")}/100))*0.01+{ib("dex")}*0.0025)'
        return IB(key)
    return ib


BLOCK_HEIGHT = LAST_ROW + 16
BLOCK_START = SENSITIVITY_HEADER_ROW + len(STAT_SWEEP) + 3


def build_stat_block(ws, base_row, ib, stat_key, stat_label, override_expr):
    row_label = base_row
    row_header = base_row + 1
    calc_start = base_row + 2
    row_of = {key: calc_start + (r - 2) for key, r in ROW.items()}
    calc_end = calc_start + (LAST_ROW - 2)

    s_aps_pre = calc_end + 2
    s_adrenalin_uptime = calc_end + 3
    s_as_bonus = calc_end + 4
    s_aps = calc_end + 5
    s_castrate = calc_end + 6
    s_baps = calc_end + 7
    s_avgbuff = calc_end + 8
    s_crit_rate_bonus = calc_end + 9
    s_monster_dmg_bonus = calc_end + 10
    s_shadow_partner_mult = calc_end + 11
    s_crit_damage_bonus = calc_end + 12
    s_total = calc_end + 13
    aps_pre_ref, adrenalin_uptime_ref = f"B{s_aps_pre}", f"B{s_adrenalin_uptime}"
    as_bonus_ref, aps_ref, castrate_ref = f"B{s_as_bonus}", f"B{s_aps}", f"B{s_castrate}"
    baps_ref = f"B{s_baps}"
    crit_rate_bonus_ref = f"B{s_crit_rate_bonus}"
    monster_dmg_bonus_ref, shadow_partner_mult_ref = f"B{s_monster_dmg_bonus}", f"B{s_shadow_partner_mult}"
    crit_damage_bonus_ref = f"B{s_crit_damage_bonus}"
    total_ref = f"B{s_total}"

    fda_block = fixed_duration_active_expr(ib("monster_type"), ib("fight_duration"))
    bdi_block = ib("buff_duration_increase_pct")

    def buff_uptime_block(local_row, skills_row):
        return uptime_fraction_or_exact_expr(
            fda_block, f'S{local_row}', ib("monster_type"), S("BuffDuration(s)", skills_row),
            S("Cooldown(s)", skills_row), bdi_block, ib("fight_duration"),
        )

    # Passive-mult delta terms (Magic Critical pattern) — 0 for every block except the one
    # sweeping the relevant skill-level-bonus (or, for ATTACK_SPEED/CRIT_RATE/etc., the block
    # sweeping that stat directly does NOT change these rows' F, since their F depends only on
    # job-step level, not on the swept Inputs%, so the delta is 0 there too — it's only ever
    # nonzero in the 5 Skill-Level-Bonus blocks). Gated by the row's own Unlocked flag: if the
    # passive isn't learned yet at the current character level, there's no meaningful "marginal
    # skill-level-bonus" to suggest (same Unlocked-Gate Bypass class of bug as the buff averages).
    delta_by_slot = {}
    for row_key, slot in PASSIVE_DELTA_SLOT.items():
        term = f'((C{row_of[row_key]}=TRUE)*(F{row_of[row_key]}-Calc!F{ROW[row_key]}))'
        delta_by_slot[slot] = f'{delta_by_slot[slot]}+{term}' if slot in delta_by_slot else term
    delta = {slot: delta_by_slot.get(slot, "0") for slot in (
        "attack_speed", "basic_attack_damage", "min_damage", "crit_rate", "crit_damage",
        "boss_damage", "skill_damage", "final_damage", "attack_mult",
    )}

    r_dsa = ROW["DARK_SIGHT_ATK"]
    r_fcs = ROW["FRAILTY_CURSE_SELF_FD"]
    dark_sight_atk_avg = f'((C{row_of["DARK_SIGHT_ATK"]}=TRUE)*F{row_of["DARK_SIGHT_ATK"]}*{buff_uptime_block(row_of["DARK_SIGHT_ATK"], r_dsa)})'
    frailty_self_fd_avg = f'((C{row_of["FRAILTY_CURSE_SELF_FD"]}=TRUE)*F{row_of["FRAILTY_CURSE_SELF_FD"]}*{buff_uptime_block(row_of["FRAILTY_CURSE_SELF_FD"], r_fcs)})'
    adrenalin_fd_avg = f'((C{row_of["ADRENALIN_FD"]}=TRUE)*F{row_of["ADRENALIN_FD"]}*{adrenalin_uptime_ref})'
    # ATTACK% bucket: Dark Sight Attack's own live percentage sums with the delta-only Attack%
    # passives (Expert Throwing Star Handling, Shadow Shifter Self Atk) into ONE combined
    # percentage before a single multiplication — same bucket (skill/buff-sourced Attack%),
    # distinct from Inputs!attack_pct (gear Attack%), which stays its own separate multiplicative
    # factor elsewhere. Final Damage% (Frailty Curse self-FD, Adrenalin FD) is a deliberate
    # exception to this rule — every Final Damage source stays its own multiplicative factor, so
    # it is NOT folded into this sum.
    attack_bucket_block = f'(1+({dark_sight_atk_avg}+{delta["attack_mult"]})/100)'
    final_damage_bucket_block = f'(1+{frailty_self_fd_avg}/100)*(1+{adrenalin_fd_avg}/100)'

    ws.cell(row=row_label, column=1, value=f"Stat: {stat_label}").font = LABEL_FONT
    for i, name in enumerate(CALC_HEADERS):
        ws.cell(row=row_header, column=i + 1, value=name)
    style_header_row(ws, row_header, len(CALC_HEADERS))

    # Helper cells live in column U (21) — past every column the per-row loop below writes to
    # (data columns run through S=19; column U is never touched by that loop).
    maple_lvl_cell, maple_factor_cell = f"U{row_header + 1}", f"U{row_header + 2}"
    ws.cell(row=row_header, column=21, value="helpers")
    ws[maple_lvl_cell] = f'=MAX(0,({ib("level")}-100)*3)+{ib("skill_lvl_4th")}+{ib("skill_lvl_all")}'
    ws[maple_factor_cell] = (
        f'=INDEX(FactorTable!$B$2:$Y$301, MATCH(ROUND(MIN(300,MAX(1,{maple_lvl_cell})),0), '
        f'FactorTable!$A$2:$A$301,0), 24)'
    )
    basic_lvl_cell, basic_factor_cell, basic_coeff_cell = (
        f"U{row_header + 3}", f"U{row_header + 4}", f"U{row_header + 5}"
    )
    ws[basic_lvl_cell] = f'=MAX(0,({ib("level")}-100)*3)+{ib("skill_lvl_4th")}+{ib("skill_lvl_all")}'
    ws[basic_factor_cell] = (
        f'=INDEX(FactorTable!$B$2:$Y$301, MATCH(ROUND(MIN(300,MAX(1,{basic_lvl_cell})),0), '
        f'FactorTable!$A$2:$A$301,0), 22)'
    )
    ws[basic_coeff_cell] = f'=290*{basic_factor_cell}/1000'

    FULL_HIT_PIPELINE_KEYS = ["SHOWDOWN"] + DAMAGE_ROW_KEYS + TOXIC_VENOM_ROW_KEYS + SHADOW_SHIFTER_ROW_KEYS

    for key, r in ROW.items():
        row = row_of[key]
        ws.cell(row=row, column=1, value=f"={S('Key', r)}")
        ws.cell(row=row, column=2, value=f"={S('Name', r)}")
        ws.cell(row=row, column=3, value=unlock_expr(key))

        has_cooldown = ROW_HAS_COOLDOWN[key]
        if has_cooldown:
            eff_cd_row = effective_cooldown_expr(
                ib("monster_type"), S("Cooldown(s)", r), ib("skill_cooldown_decrease"),
                S("CostsActionSlot", CDR_COSTS_ACTION_ROW[key]),
            )
            rate_row = rate_or_exact_hits_expr(
                fda_block, f"R{row}", S("HitsPerCast", r), S("ICD(s)", r), S("ActiveWindow(s)", r),
                eff_cd_row, ib("fight_duration"), f"G{row}*Q{row}",
            )
        else:
            eff_cd_row = None
            rate_row = None

        if key == "SHOWDOWN":
            ws.cell(row=row, column=4, value="")
            ws.cell(row=row, column=5, value="")
            ws.cell(row=row, column=6, value=f"={basic_coeff_cell}+{S('SkillMasteryBonus%', r)}")
        else:
            ws.cell(row=row, column=4, value=(
                f'=IF({S("JobStep", r)}=1,60+{ib("skill_lvl_1st")}+{ib("skill_lvl_all")},'
                f'IF({S("JobStep", r)}=2,90+{ib("skill_lvl_2nd")}+{ib("skill_lvl_all")},'
                f'IF({S("JobStep", r)}=3,120+{ib("skill_lvl_3rd")}+{ib("skill_lvl_all")},'
                f'MAX(0,({ib("level")}-100)*3)+{ib("skill_lvl_4th")}+{ib("skill_lvl_all")})))'
            ))
            ws.cell(row=row, column=5, value=(
                f'=INDEX(FactorTable!$B$2:$Y$301, MATCH(ROUND(MIN(300,MAX(1,D{row})),0), '
                f'FactorTable!$A$2:$A$301,0), {S("FactorIndex", r)}+1)'
            ))
            ws.cell(row=row, column=6, value=(
                f'=IF({S("ScalesWithLevel", r)}=TRUE,({S("BaseDamage(tenths%)", r)}/10)*(E{row}/1000),'
                f'{S("BaseDamage(tenths%)", r)}/10)+{S("SkillMasteryBonus%", r)}'
            ))

        ws.cell(row=row, column=7, value=f"=Calc!G{r}")
        ws.cell(row=row, column=8, value=f"=Calc!H{r}")
        ws.cell(row=row, column=9, value=(
            f'=IF({S("MapleHeroBase(tenths%)", r)}<>"",'
            f'1+({S("MapleHeroBase(tenths%)", r)}/10)*({maple_factor_cell}/1000)/100,1)'
        ))

        if key in FULL_HIT_PIPELINE_KEYS:
            ws.cell(row=row, column=10, value=f'={ib("attack")}*(F{row}/100)')
            monster_dmg_term = monster_blend_expr(
                ib("monster_type"), ib("normal_weight_frac"),
                f'{ib("boss_damage")}+{delta["boss_damage"]}+{S("MasteryBossDamage%", r)}+{monster_dmg_bonus_ref}',
                f'{ib("normal_damage")}+{S("MasteryNormalDamage%", r)}+{monster_dmg_bonus_ref}',
                "0",
            )
            crit_rate_total_block = f'({ib("crit_rate")}+{delta["crit_rate"]}+{crit_rate_bonus_ref})'
            avgbuff_with_deltas = f'({attack_bucket_block}*{final_damage_bucket_block})'
            ws.cell(row=row, column=11, value=(
                f'=J{row}*(1+{ib("stat_damage")}/100)*(1+{ib("damage")}/100)'
                f'*(1+{monster_dmg_term}/100)'
                f'*(1+{ib("damage_amp")}/100)'
                f'*(5000/(6000+{ib("monster_defense")}*(1-{ib("def_pen")}/100)))'
                f'*(1+({ib("final_damage")}+{delta["final_damage"]})/100)*(1+{S("MasteryFinalDamage%", r)}/100)'
                f'*(1+(IF({S("Key", r)}="SHOWDOWN",{ib("basic_attack_damage")}+{delta["basic_attack_damage"]},'
                f'{ib("skill_damage")}+{delta["skill_damage"]}))/100)'
                f'*({avgbuff_with_deltas}*{shadow_partner_mult_ref}*I{row})'
            ))
            ws.cell(row=row, column=12, value=(
                f'=K{row}*(MIN({ib("min_damage")}+{delta["min_damage"]},{ib("max_damage")})/100+{ib("max_damage")}/100)/2'
            ))
            ws.cell(row=row, column=13, value=f'=L{row}*(1+({ib("crit_damage")}+{delta["crit_damage"]}+{crit_damage_bonus_ref})/100)')
            ws.cell(row=row, column=14, value=(
                f'=L{row}*(1-MIN({crit_rate_total_block},100)/100)+M{row}*(MIN({crit_rate_total_block},100)/100)'
            ))
        else:
            for col in (10, 11, 12, 13, 14):
                ws.cell(row=row, column=col, value="")

        if key == "SHOWDOWN":
            basic_targets_expr = f'(6+{ib("basic_attack_target_increase")})'
            ws.cell(row=row, column=15, value=(
                f"=IF(C{row},{S('HitsPerCast', r)}*N{row}*{baps_ref}*"
                f"{target_multiplier_expr(ib('monster_type'), ib('normal_weight_frac'), basic_targets_expr, ib('max_enemies_hit'))},0)"
            ))
        elif key in DAMAGE_ROW_KEYS:
            ws.cell(row=row, column=15, value=(
                f'=IF(C{row},H{row}*N{row}*{rate_row}*'
                f"{target_multiplier_expr(ib('monster_type'), ib('normal_weight_frac'), S('NormalMonsterTargets', r), ib('max_enemies_hit'))},0)"
            ))
        elif key in TOXIC_VENOM_ROW_KEYS:
            total_hit_rate = (
                f'SUMPRODUCT((Skills!{SC["TriggersToxicVenom"]}2:{SC["TriggersToxicVenom"]}{LAST_ROW}=TRUE)*'
                f'(C{calc_start}:C{calc_end}=TRUE)*S{calc_start}:S{calc_end})'
            )
            ws.cell(row=row, column=15, value=f'=IF(C{row},0.2*{total_hit_rate}*N{row},0)')
        elif key in SHADOW_SHIFTER_ROW_KEYS:
            ws.cell(row=row, column=15, value=f'=IF(C{row},{ib("incoming_hit_rate")}*0.2*N{row},0)')
        else:
            ws.cell(row=row, column=15, value=0)

        ws.cell(row=row, column=16, value=f'=IF({total_ref}=0,0,O{row}/{total_ref})')

        # Q/R/S match the main Calc sheet's own column layout exactly (InvCooldown/CastsInFight/
        # HitRate(perSec)) — same header labels from CALC_HEADERS above, columns 17-19.
        ws.cell(row=row, column=17, value=(f'=IFERROR(1/{eff_cd_row},0)' if has_cooldown else 0))
        if has_cooldown:
            ws.cell(row=row, column=18, value=(
                f'=IF({fda_block},{exact_casts_expr(ib("fight_duration"), eff_cd_row)},0)'
            ))
        else:
            ws.cell(row=row, column=18, value=0)
        # Same circular-reference fix as build_calc_sheet's own S column — Toxic Venom's row is
        # hardcoded to literal 0 (never =O/N) to avoid a genuine cycle through its own O formula.
        if key in TOXIC_VENOM_ROW_KEYS:
            ws.cell(row=row, column=19, value=0)
        else:
            ws.cell(row=row, column=19, value=f'=IFERROR(O{row}/N{row},0)')

    r_nf, r_dsc = ROW["NIMBLE_FEET"], ROW["DARK_SIGHT_CRIT"]
    r_fcd = ROW["FRAILTY_CURSE_DEBUFF"]
    r_afd, r_aas = ROW["ADRENALIN_FD"], ROW["ADRENALIN_AS"]
    r_sp = ROW["SHADOW_PARTNER"]

    # Same Unlocked-gate fix as build_summary_sheet — local C column, not Calc!C, since this
    # block has its own per-row copy of every Calc column.
    nimble_feet_avg = f'((C{row_of["NIMBLE_FEET"]}=TRUE)*F{row_of["NIMBLE_FEET"]}*{buff_uptime_block(row_of["NIMBLE_FEET"], r_nf)})'
    dark_sight_crit_avg = f'((C{row_of["DARK_SIGHT_CRIT"]}=TRUE)*F{row_of["DARK_SIGHT_CRIT"]}*{buff_uptime_block(row_of["DARK_SIGHT_CRIT"], r_dsc)})'
    frailty_debuff_avg = f'((C{row_of["FRAILTY_CURSE_DEBUFF"]}=TRUE)*F{row_of["FRAILTY_CURSE_DEBUFF"]}*{buff_uptime_block(row_of["FRAILTY_CURSE_DEBUFF"], r_fcd)})'

    attack_speed_with_delta = f'({ib("attack_speed")}+{delta["attack_speed"]})'

    ws.cell(row=s_aps_pre, column=1, value="Actions Per Second (pre-Adrenalin)")
    ws.cell(row=s_aps_pre, column=2, value=(
        f'=1+MIN(150,150*(1-(1-{attack_speed_with_delta}/150)*(1-{nimble_feet_avg}/150)))/100'
    ))

    activations_needed = 5
    adrenalin_duration_scaled = f'({S("BuffDuration(s)", r_afd)}*(1+{bdi_block}/100))'
    adrenalin_accumulate_time = f'({activations_needed}/{aps_pre_ref})'
    ws.cell(row=s_adrenalin_uptime, column=1, value="Alchemic Adrenaline Uptime")
    ws.cell(row=s_adrenalin_uptime, column=2, value=(
        f'={adrenalin_duration_scaled}/({adrenalin_duration_scaled}+{adrenalin_accumulate_time})'
    ))

    adrenalin_as_avg = f'((C{row_of["ADRENALIN_AS"]}=TRUE)*F{row_of["ADRENALIN_AS"]}*{adrenalin_uptime_ref})'

    ws.cell(row=s_as_bonus, column=1, value="Attack Speed Buff Bonus %")
    ws.cell(row=s_as_bonus, column=2, value=f'={nimble_feet_avg}+{adrenalin_as_avg}')

    ws.cell(row=s_aps, column=1, value="Actions Per Second (final)")
    ws.cell(row=s_aps, column=2, value=(
        f'=1+MIN(150,150*(1-(1-{attack_speed_with_delta}/150)*(1-{as_bonus_ref}/150)))/100'
    ))

    ws.cell(row=s_castrate, column=1, value="Skill + Buff Cast Rate")
    ws.cell(row=s_castrate, column=2, value=(
        f'=IF({fda_block},'
        f'SUMPRODUCT((Skills!{SC["CostsActionSlot"]}2:{SC["CostsActionSlot"]}{LAST_ROW}=TRUE)*'
        f'(C{calc_start}:C{calc_end}=TRUE)*R{calc_start}:R{calc_end}*Skills!{SC["ActionsPerCast"]}2:{SC["ActionsPerCast"]}{LAST_ROW})/{ib("fight_duration")},'
        f'SUMPRODUCT((Skills!{SC["CostsActionSlot"]}2:{SC["CostsActionSlot"]}{LAST_ROW}=TRUE)*'
        f'(C{calc_start}:C{calc_end}=TRUE)*Q{calc_start}:Q{calc_end}*Skills!{SC["ActionsPerCast"]}2:{SC["ActionsPerCast"]}{LAST_ROW}))'
    ))

    ws.cell(row=s_baps, column=1, value="Showdown Casts Per Second")
    ws.cell(row=s_baps, column=2, value=f'=MAX(0,{aps_ref}-{castrate_ref})')

    ws.cell(row=s_avgbuff, column=1, value="Average Buff Multiplier")
    ws.cell(row=s_avgbuff, column=2, value=f'={attack_bucket_block}*{final_damage_bucket_block}')

    ws.cell(row=s_crit_rate_bonus, column=1, value="Global Crit Rate Bonus %")
    ws.cell(row=s_crit_rate_bonus, column=2, value=f'=IF({ib("level")}>=47,8,0)+{dark_sight_crit_avg}')

    ws.cell(row=s_monster_dmg_bonus, column=1, value="Global Monster Damage-Taken Bonus %")
    ws.cell(row=s_monster_dmg_bonus, column=2, value=f'=IF({ib("level")}>=82,15,0)+{frailty_debuff_avg}')

    ws.cell(row=s_shadow_partner_mult, column=1, value="Shadow Partner Average Multiplier")
    ws.cell(row=s_shadow_partner_mult, column=2, value=(
        f'=1+((C{row_of["SHADOW_PARTNER"]}=TRUE)*F{row_of["SHADOW_PARTNER"]}*I{row_of["SHADOW_PARTNER"]}*{S("ProcChance%", r_sp)}/100)/100'
    ))

    ws.cell(row=s_crit_damage_bonus, column=1, value="Global Critical Damage Bonus % (Frailty Curse Mastery Lv.111)")
    ws.cell(row=s_crit_damage_bonus, column=2, value=(
        f'=IF({ib("level")}>=111,30,0)*{buff_uptime_block(row_of["FRAILTY_CURSE_DEBUFF"], r_fcd)}'
    ))

    ws.cell(row=s_total, column=1, value="TOTAL DPS").font = LABEL_FONT
    ws.cell(row=s_total, column=2, value=f"=SUM(O{calc_start}:O{calc_end})").font = LABEL_FONT

    return total_ref


def build_sensitivity_sheet(wb):
    ws = wb.create_sheet("Sensitivity")
    ws["A1"] = "Marginal DPS per +1 (percentage point / skill level / flat point)"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = (
        "Attack Speed and Def Pen combine their +1 via the diminishing-returns formula "
        "(new = (1-(1-old/factor)*(1-inc/factor))*factor), not a flat add."
    )

    header_row = SENSITIVITY_HEADER_ROW
    headers = [
        "Stat", "Units per +1% DPS", "Type", "Current Value", "New Value",
        "Baseline Total DPS", "New Total DPS", "DPS Gain", "% Gain",
    ]
    for i, name in enumerate(headers):
        ws.cell(row=header_row, column=i + 1, value=name)
    style_header_row(ws, header_row, len(headers))

    for idx, (key, label, kind) in enumerate(STAT_SWEEP):
        base_row = BLOCK_START + idx * BLOCK_HEIGHT
        override_expr = override_expr_for(kind, key)
        ib = make_ib(key, override_expr)
        total_ref = build_stat_block(ws, base_row, ib, key, label, override_expr)

        row = header_row + 1 + idx
        ws.cell(row=row, column=1, value=label)
        ws.cell(row=row, column=3, value=kind)
        ws.cell(row=row, column=4, value=f"={IB(key)}")
        ws.cell(row=row, column=5, value=f"={override_expr}")
        ws.cell(row=row, column=6, value=f"=Summary!$B${R_TOTAL}")
        ws.cell(row=row, column=7, value=f"={total_ref}")
        ws.cell(row=row, column=8, value=f"=G{row}-F{row}")
        ws.cell(row=row, column=9, value=f"=IF(F{row}=0,0,G{row}/F{row}*100)")
        ws.cell(row=row, column=2, value=f'=IFERROR(1/(I{row}-100),"n/a")')

    widths = [40, 16, 8, 14, 14, 16, 14, 12, 10]
    for i, w in enumerate(widths):
        ws.column_dimensions[get_column_letter(i + 1)].width = w
    ws.freeze_panes = "A5"
    return ws


def build_cube_data_sheet(wb):
    """Raw data for the PotentialCubes sheet: the flattened weighted-roll table (parsed from
    the TS web app + the 3 hand-added slots, see _iter_potential_line_entries), a Stat ->
    DPS-per-unit lookup table (every distinct potential-line stat, mapped via the Sensitivity
    sheet's own +1 marginal — a linear approximation per the user's explicit delta-method
    instruction), and the rarity upgrade rates/pity caps. Not meant for manual editing.
    (Verbatim port of build_fp_mage_workbook.py's own sheet builder.)"""
    ws = wb.create_sheet("CubeData")

    headers = ["Slot", "Rarity", "Line", "Stat", "Value", "Weight", "Prime", "DPSPerUnit"]
    for i, name in enumerate(headers):
        ws.cell(row=1, column=i + 1, value=name)
    style_header_row(ws, 1, len(headers))

    row = 2
    for slot, rarity, line_num, entry in _iter_potential_line_entries():
        ws.cell(row=row, column=1, value=slot)
        ws.cell(row=row, column=2, value=rarity)
        ws.cell(row=row, column=3, value=line_num)
        ws.cell(row=row, column=4, value=entry["stat"])
        ws.cell(row=row, column=5, value=entry["value"])
        ws.cell(row=row, column=6, value=entry["weight"])
        ws.cell(row=row, column=7, value=entry["prime"])
        ws.cell(row=row, column=8, value=dps_per_unit_expr(entry["stat"]))
        row += 1
    assert row - 1 == CUBE_DATA_LAST_ROW, f"CUBE_DATA_LAST_ROW out of sync: {row - 1} vs {CUBE_DATA_LAST_ROW}"

    ws.cell(row=1, column=10, value="Stat")
    ws.cell(row=1, column=11, value="DPSPerUnit")
    for col in (10, 11):
        ws.cell(row=1, column=col).fill = HEADER_FILL
        ws.cell(row=1, column=col).font = HEADER_FONT
    stat_list = ["(none)"] + ALL_POTENTIAL_STATS
    for i, stat in enumerate(stat_list):
        r = i + 2
        ws.cell(row=r, column=10, value=stat)
        ws.cell(row=r, column=11, value=(0 if stat == "(none)" else dps_per_unit_expr(stat)))
    assert 1 + len(stat_list) == CUBE_DATA_STAT_TABLE_LAST_ROW

    ws.cell(row=1, column=13, value="Rarity")
    ws.cell(row=1, column=14, value="Rate")
    ws.cell(row=1, column=15, value="MaxPity")
    for col in (13, 14, 15):
        ws.cell(row=1, column=col).fill = HEADER_FILL
        ws.cell(row=1, column=col).font = HEADER_FONT
    for i, rarity in enumerate(RARITY_ORDER):
        r = i + 2
        ws.cell(row=r, column=13, value=rarity)
        ws.cell(row=r, column=14, value=RARITY_UPGRADE_RATES[rarity]["rate"])
        ws.cell(row=r, column=15, value=RARITY_UPGRADE_RATES[rarity]["max"])

    ws.cell(row=1, column=17, value="SlotList")
    ws.cell(row=1, column=17).fill = HEADER_FILL
    ws.cell(row=1, column=17).font = HEADER_FONT
    for i, slot in enumerate(CUBE_SLOTS):
        ws.cell(row=i + 2, column=17, value=slot)
    assert 1 + len(CUBE_SLOTS) == CUBE_DATA_SLOT_LIST_LAST_ROW

    widths = [10, 12, 6, 26, 9, 9, 8, 13, 2, 26, 13, 2, 12, 10, 9, 2, 14]
    for i, w in enumerate(widths):
        ws.column_dimensions[get_column_letter(i + 1)].width = w
    ws.freeze_panes = "A2"
    return ws


CUBE_DATA_STAT_TABLE_LAST_ROW = 2 + len(ALL_POTENTIAL_STATS)  # +1 header, +1 for "(none)" row
CUBE_DATA_SLOT_LIST_LAST_ROW = 1 + len(CUBE_SLOTS)


def dps_per_unit_lookup(stat_cell_ref):
    """Live lookup of a stat NAME cell (e.g. a Current-State dropdown cell) -> its DPS-per-unit
    factor, via the CubeData!J:K table built above. Single-cell MATCH/INDEX, not a range nested
    inside IFERROR — safe against the openpyxl/Excel implicit-intersection bug."""
    return (
        f'INDEX(CubeData!$K$2:$K${CUBE_DATA_STAT_TABLE_LAST_ROW},'
        f'MATCH({stat_cell_ref},CubeData!$J$2:$J${CUBE_DATA_STAT_TABLE_LAST_ROW},0))'
    )


# User-specified milestone cube counts for exact EV reporting (tools/potential_cubes_ev.py) —
# all multiples of 5, kept from the original 5-cube-resolution design even though the exact
# Python engine itself now runs at per-cube resolution.
CUBE_MILESTONES = [
    5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 60, 70, 80, 90, 100,
    125, 150, 175, 200, 250, 300, 400, 500, 1000,
]

# PotentialCubes sheet layout: a plain data table (no Excel-formula probability engine — that
# turned out to require either an impractically large live sheet or a joint state too big to
# express in formulas at all; the exact "expected best roll after N rerolls, with carry-forward
# across rarity upgrades" math now lives in tools/potential_cubes_ev.py, which reads this table
# plus the live Sensitivity!H DPS-per-unit values. One row per (slot, potential type) — 15
# slots x 2 types = 30 rows — so a single script run reports every piece of gear at once.
POTENTIAL_CUBES_HEADER_ROW = 5
POTENTIAL_CUBES_FIRST_DATA_ROW = POTENTIAL_CUBES_HEADER_ROW + 1
POTENTIAL_TYPES = ("Potential", "Bonus Potential")
POTENTIAL_CUBES_LAST_DATA_ROW = POTENTIAL_CUBES_HEADER_ROW + len(CUBE_SLOTS) * len(POTENTIAL_TYPES)


def build_potential_cubes_sheet(wb, existing=None):
    """(Verbatim port of build_fp_mage_workbook.py's own sheet builder.)"""
    existing = existing or {}
    ws = wb.create_sheet("PotentialCubes")
    ws["A1"] = "Potential Cubes — Current Gear State"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = (
        "Fill in your actual current gear for every slot/potential-type you want EV results for, "
        "then run `python3 tools/potential_cubes_ev.py --class night-lord` — it reads this table "
        "plus the live Sensitivity!H DPS-per-unit values and computes exact 'expected value of "
        "the best roll kept after N rerolls' for all 30 rows (printed + written to a CSV), via a "
        "full line1 x line2 x line3 enumeration per rarity/slot rather than a single-roll average."
    )
    ws["A3"] = "Leave a line's Stat as \"(none)\" if that line isn't rolled yet / doesn't matter."

    headers = [
        "Slot", "Potential Type", "Current Rarity", "Current Pity Count",
        "Line 1 Stat", "Line 1 Value", "Line 2 Stat", "Line 2 Value", "Line 3 Stat", "Line 3 Value",
    ]
    for i, name in enumerate(headers):
        ws.cell(row=POTENTIAL_CUBES_HEADER_ROW, column=i + 1, value=name)
    style_header_row(ws, POTENTIAL_CUBES_HEADER_ROW, len(headers))

    dv_rarity = DataValidation(type="list", formula1='"' + ",".join(RARITY_ORDER) + '"', allow_blank=False)
    dv_stat = DataValidation(type="list", formula1=f"=CubeData!$J$2:$J${CUBE_DATA_STAT_TABLE_LAST_ROW}", allow_blank=False)
    ws.add_data_validation(dv_rarity)
    ws.add_data_validation(dv_stat)

    row = POTENTIAL_CUBES_FIRST_DATA_ROW
    for slot in CUBE_SLOTS:
        for potential_type in POTENTIAL_TYPES:
            saved = existing.get((slot, potential_type), {})
            ws.cell(row=row, column=1, value=slot)
            ws.cell(row=row, column=2, value=potential_type)
            rarity_cell = ws.cell(row=row, column=3, value=saved.get("rarity", "normal"))
            dv_rarity.add(rarity_cell)
            ws.cell(row=row, column=4, value=saved.get("pity", 0))
            saved_lines = saved.get("lines", [])
            for i, line_col in enumerate((5, 7, 9)):
                stat, val = saved_lines[i] if i < len(saved_lines) else ("(none)", 0)
                stat_cell = ws.cell(row=row, column=line_col, value=stat)
                dv_stat.add(stat_cell)
                ws.cell(row=row, column=line_col + 1, value=val)
            row += 1
    assert row - 1 == POTENTIAL_CUBES_LAST_DATA_ROW

    widths = [12, 15, 13, 18, 26, 11, 26, 11, 26, 11]
    for i, w in enumerate(widths):
        ws.column_dimensions[get_column_letter(i + 1)].width = w
    ws.freeze_panes = f"A{POTENTIAL_CUBES_FIRST_DATA_ROW}"
    return ws


def load_existing_workbook_state(path):
    """If a previous Night-Lord-DPS-Calculator.xlsx already exists at `path`, read back its
    Inputs values and PotentialCubes current-gear table so regenerating the workbook (e.g. to
    pick up a data/formula change) doesn't clobber the user's real character stats and gear
    state with the hardcoded defaults. Matches PotentialCubes rows by (slot, potential type),
    not row position, so it's robust even if CUBE_SLOTS/POTENTIAL_TYPES order ever changes.
    (Mirrors build_fp_mage_workbook.py's own state-preservation pattern, now including its
    PotentialCubes half.)"""
    if not path.exists():
        return {}, {}
    try:
        wb = openpyxl.load_workbook(path)
    except Exception as e:
        print(f"Warning: couldn't read existing {path} to carry over values ({e}); using defaults.")
        return {}, {}

    existing_inputs = {}
    if "Inputs" in wb.sheetnames:
        ws = wb["Inputs"]
        for key, row in IN.items():
            value = ws.cell(row=row, column=2).value
            # Inputs cells are always raw literals now (never formulas) — a formula string here
            # means this row held something else before a layout change; skip it rather than
            # carry over stale data from the wrong cell.
            if value is not None and not (isinstance(value, str) and value.startswith("=")):
                existing_inputs[key] = value

    existing_potential_cubes = {}
    if "PotentialCubes" in wb.sheetnames:
        ws = wb["PotentialCubes"]
        for row in range(POTENTIAL_CUBES_FIRST_DATA_ROW, ws.max_row + 1):
            slot = ws.cell(row=row, column=1).value
            potential_type = ws.cell(row=row, column=2).value
            if not slot or not potential_type:
                continue
            lines = []
            for stat_col, val_col in ((5, 6), (7, 8), (9, 10)):
                stat = ws.cell(row=row, column=stat_col).value
                val = ws.cell(row=row, column=val_col).value
                lines.append((stat if stat is not None else "(none)", val if val is not None else 0))
            existing_potential_cubes[(slot, potential_type)] = dict(
                rarity=ws.cell(row=row, column=3).value or "normal",
                pity=ws.cell(row=row, column=4).value or 0,
                lines=lines,
            )
    return existing_inputs, existing_potential_cubes


def main():
    existing_inputs, existing_potential_cubes = load_existing_workbook_state(OUT_PATH)
    wb = openpyxl.Workbook()
    build_readme_sheet(wb)
    build_inputs_sheet(wb, existing=existing_inputs)
    build_factor_table_sheet(wb)
    build_skills_sheet(wb)
    build_calc_sheet(wb)
    build_summary_sheet(wb)
    build_sensitivity_sheet(wb)
    build_cube_data_sheet(wb)
    build_potential_cubes_sheet(wb, existing=existing_potential_cubes)
    wb.active = 0
    wb.save(OUT_PATH)
    print(f"Wrote {OUT_PATH}")
    if existing_inputs or existing_potential_cubes:
        print("Carried over Inputs/PotentialCubes values from the previous workbook.")


if __name__ == "__main__":
    main()
