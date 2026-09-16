#!/usr/bin/env python3
"""
Generates Shadower-DPS-Calculator.xlsx: a live-formula Excel replica of a Shadower skill-rotation
DPS model, sibling to build_night_lord_workbook.py (see
/Users/yaniv/.claude/plans/vectorized-shimmying-pony.md this was built from). Shadower is LUK
main stat / DEX sub stat — identical stat identity to Night Lord, and shares a large fraction of
its kit verbatim with Night Lord: Nimble Feet, Dark Sight, Shadow Partner, Venom (+ Lv.82 Weaken),
Toxic Venom, Sudden Raid, Dark Flare (+ Lv.104 Strike Interval mastery), Shadow Shifter all reuse
Night Lord's own already-verified (baseDamage, factorIndex) tuples directly — confirmed via the
Aug 13 2026 patch notes independently listing identical corrections for both classes' copies of
Dark Flare/Venom/their masteries.

Sheets: Inputs, FactorTable, Skills, Calc, Summary, Sensitivity, CubeData, PotentialCubes.

Key mechanics specific to this kit (see the plan for full derivation/justification):
  - Cruel Stab (basic attack) reuses the universal 4th-job-basic-attack constant (baseDamage 2900,
    factorIndex 21) confirmed identical across every class built so far (Showdown, Chain
    Lightning, Big Bang, Cruel Stab all share this exact wiki-documented curve).
  - Meso Explosion is a resource-gated activated skill: 50% chance per attack to generate a Meso
    stack (max 10), own cast (cooldown 11s) deals damage to (stack count) targets. Modeled via
    steady-state average stack count at cast time: MIN(10, 0.5*attack_rate*cooldown) — the same
    "assume steady accumulation" simplification used for Elemental Drain/Frost stacks elsewhere.
  - Blood Money piggybacks on Meso Explosion's own cast (same rate, no independent cooldown):
    50% chance PER meso-generation-roll to also create a Blood Money stack (max 5). Modeled the
    same steady-state way: MIN(5, 0.25*attack_rate*11) (0.5 meso-chance * 0.5 blood-money-chance).
    Patched (Aug 13 2026): base damage 2800%->3600% (curve rescaled 1.2857x before reverse-
    engineering, same technique as Ice-Lightning-Mage's Elemental Reset), single-target +5%/stack
    bonus REMOVED, Mastery Lv.122/138 both renamed "Damage & Target" with corrected values (see
    the plan's Context section for the full patch-note reconciliation, including how a page-break
    artifact in the PDF's own layout extraction initially mis-paired several rows).
  - Assassinate's finishing blow (+3000% additional damage) lands on average every 2nd cast —
    modeled as a flat 50% average multiplier on the finisher term, not an exact odd/even cast
    counter. Mastery Lv.108 "Murderous Intent" doubles the NEXT finishing blow after a Blood Money
    attack — modeled as a steady-state average multiplier on the finisher term as well (a proc-off-
    a-proc dependency), not an exact alternating-state machine.
  - Steal's own self-Attack-buff component (ignoring its target-debuff side, out of scope) is
    modeled at steady-state max stacks (x3), matching the Elemental-Drain-style convention.
  - Maple Hero (Shadower) uses the Bishop-discovered "Final-Damage-chain additive term per named
    skill" mechanic shape (not Night Lord's own per-skill "additional damage%" shape), affecting
    FOUR skills (Dark Flare/Venom/Shadow Partner/Phase Dash) from ONE shared curve (confirmed via
    reverse-engineering: factorIndex 23, baseDamage 150, with each target skill's own contribution
    being a fixed multiple of that shared curve — Dark Flare 1x, Venom/Shadow Partner 3.333x,
    Phase Dash 2.667x, all confirmed proportional across the full level range).
"""
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
OUT_PATH = REPO / "Shadower-DPS-Calculator.xlsx"

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
# Load the real factor table straight from the TS source (avoid re-typing it) — reused verbatim.
# ---------------------------------------------------------------------------
def load_factor_table():
    data = json.loads(FACTOR_TABLE_JSON.read_text())
    return {int(k): v for k, v in data.items()}


FACTOR_TABLE = load_factor_table()
assert len(FACTOR_TABLE) == 300 and len(FACTOR_TABLE[1]) == 24


# ---------------------------------------------------------------------------
# Load the real potential-cube data straight from the (unused) TS web app — verbatim reuse.
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

RARITY_ORDER = ["normal", "rare", "epic", "unique", "legendary", "mystic"]


def _slot_specific_tier_block(stat, values_by_tier):
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
SLOT_SPECIFIC_POTENTIALS["ring"] = _slot_specific_tier_block(
    "All Skill Level", {"epic": 5, "unique": 8, "legendary": 12, "mystic": 16}
)
SLOT_SPECIFIC_POTENTIALS["necklace"] = _slot_specific_tier_block(
    "All Skill Level", {"epic": 5, "unique": 8, "legendary": 12, "mystic": 16}
)
SLOT_SPECIFIC_POTENTIALS["head"] = _slot_specific_tier_block(
    "Skill Cooldown Decrease (seconds)", {"epic": 0.5, "unique": 1, "legendary": 1.5, "mystic": 2}
)
SLOT_SPECIFIC_POTENTIALS["chest"] = _slot_specific_tier_block(
    "Basic Attack Target Increase", {"unique": 1, "legendary": 2, "mystic": 3}
)
SLOT_SPECIFIC_POTENTIALS["belt"] = _slot_specific_tier_block(
    "Buff Duration Increase %", {"epic": 5, "unique": 8, "legendary": 12, "mystic": 20}
)
SLOT_SPECIFIC_POTENTIALS["boots"] = _slot_specific_tier_block(
    "Companion Summoning Time Increase %", {"epic": 5, "unique": 8, "legendary": 12, "mystic": 20}
)
SLOT_SPECIFIC_POTENTIALS["eye-accessory"] = _slot_specific_tier_block(
    "Main Stat Per Level", {"epic": 10, "unique": 20, "legendary": 35, "mystic": 50}
)
SLOT_SPECIFIC_POTENTIALS["pocket"] = _slot_specific_tier_block(
    "Main Stat % per 4 Levels", {"epic": 0.4, "unique": 0.6, "legendary": 0.8, "mystic": 1.2}
)

CUBE_SLOTS = [
    "head", "cape", "chest", "shoulders", "legs", "belt", "gloves", "boots",
    "ring", "neck", "eye-accessory", "ring2", "face", "earrings", "pocket",
]
SLOT_SPECIFIC_KEY = {
    "shoulders": "shoulder",
    "neck": "necklace",
}


def _iter_potential_line_entries():
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


ALL_POTENTIAL_STATS = sorted({entry["stat"] for _, _, _, entry in _iter_potential_line_entries()} | {
    "Skill Cooldown Decrease (seconds)", "Buff Duration Increase %",
})
CUBE_DATA_LAST_ROW = 1 + sum(1 for _ in _iter_potential_line_entries())

# ---------------------------------------------------------------------------
# Inputs sheet row map — LUK main stat / DEX sub, identical to build_night_lord_workbook.py's own
# (including the incoming_hit_rate field Shadow Shifter's counterattack needs).
# ---------------------------------------------------------------------------
# These 6 values are computed (not user-entered) — they live on the Summary sheet's "Derived
# Values" block (see build_summary_sheet) instead of cluttering Inputs. Pushed below the
# TOTAL DPS/breakdown/marginal-value tables so the sheet reads DPS-first (row 49+, see the
# "info dump" block near R_AVGBUFF below for why 49).
DERIVED_HEADER_ROW = 49
D_ATTACK = 50                    # ATTACK = Flat ATTACK x (1+ATTACK%/100)
D_STAT_DAMAGE = 51               # STAT_DAMAGE% = 1% of total LUK + 0.25% of DEX
D_BASIC_INPUT_LEVEL = 52         # Cruel Stab input level (4th job formula)
D_BASIC_FACTOR = 53              # Cruel Stab factor lookup (factorIndex 21)
D_SKILL_COEFFICIENT = 54         # Cruel Stab base coefficient % before Skill Mastery
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
    ws["A1"] = "Shadower — DPS Calculator: How to Use This Workbook"
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
        "steady state, not an exact on/off timer — matches every other DoT-uptime assumption "
        "in this project.",
        "Crit Rate pushed above 100% (e.g. by cube potential lines) automatically redirects "
        "its stat-value to Crit Damage's own per-unit DPS value on the PotentialCubes sheet, "
        "since excess Crit Rate cannot do anything past 100%.",
        "Buffs and stacking resources (Dark Sight Attack, Into Darkness, Smokescreen, Meso "
        "Explosion/Blood Money stacks) are modeled at steady-state duty-cycle average uptime, "
        "not as an exact moment-to-moment state machine.",
        "Assassinate's finishing blow is modeled as landing on average every 2nd cast (a flat "
        "50% average multiplier), and Mastery Lv.108 Murderous Intent's finisher-doubling is a "
        "steady-state average multiplier based on relative cast rates, not an exact alternating "
        "state machine.",
        "Channel Karma, Shadow Shifter's own Attack buff, Dagger Mastery, Critical Edge, "
        "Physical Training, Dagger Expert, and Shadower Instinct are always-on passives assumed "
        "to already be reflected in your own Inputs stat entries — only their Sensitivity "
        "marginal delta (what changes if their mastery level differs from what you assumed) is "
        "modeled live.",
        "Monster Type blends Boss/Normal Monster Damage% by the Chapter Breakthrough weight %; "
        "PvP forces a fixed 15-second window regardless of the Fixed Fight Duration input.",
        "Not modeled (out of scope): all forms of crowd control (Phase Dash/Dark Sight/"
        "Assassinate stuns), Accuracy/Evasion/Defense reduction (Smokescreen, Steal, "
        "Assassinate), movement speed (Nimble Feet, Haste), the character's own Defense stat "
        "(Shield Mastery), and Companion Summoning Time.",
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
    ws["A1"] = "Shadower — DPS Calculator Inputs"
    ws["A1"].font = Font(bold=True, size=14)

    rows = [
        ("level", "Character Level", 200),
        ("monster_type", "Monster Type (\"boss\", \"normal\", \"breakthrough\", or \"pvp\")", "boss"),
        ("flat_attack", "Flat ATTACK", 10000),
        ("attack_pct", "ATTACK %", 0),
        ("monster_defense", "Monster Defense (flat, post-x100/x10 scaling)", 0),
        ("crit_rate", "CRIT_RATE %", 0),
        ("crit_damage", "CRIT_DAMAGE %", 0),
        ("attack_speed", "ATTACK_SPEED % (base, excludes Nimble Feet/Agile Daggers)", 0),
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
        ("final_damage", "FINAL_DAMAGE % (base, excludes Into Darkness/Smokescreen)", 0),
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
        ("skill_cooldown_decrease", "Skill Cooldown Decrease (seconds, only skills/buffs the character actively casts)", 0),
        ("basic_attack_target_increase", "Basic Attack Target Increase (flat, adds to the 6-target normal-monster base)", 1),
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

    ws.column_dimensions["A"].width = 55
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
# Action-economy formula helpers — reused verbatim from build_night_lord_workbook.py.
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


def level_gated_sum_raw(level_ref, pairs):
    ordered = sorted(pairs.items())
    thresholds = ",".join(str(level) for level, _ in ordered)
    increments = ",".join(str(inc) for _, inc in ordered)
    return f'SUMPRODUCT(({level_ref}>={{{thresholds}}})*{{{increments}}})'


def level_gated_sum(level_ref, pairs):
    return f'={level_gated_sum_raw(level_ref, pairs)}'

# No Buff-Mastery-equivalent skill exists anywhere in the Thief tree (Night Lord's own build
# doesn't have one either) — every buff-uptime call in this file uses IB("buff_duration_increase_pct")
# directly, with no Buff-Mastery addition on top.


# ---------------------------------------------------------------------------
# Skills sheet schema — reuses Night Lord's own EXTENDED column layout verbatim (not the trimmed
# FP-Mage-style layout ILM/Bishop use), since Toxic Venom's own TriggersToxicVenom mechanism and
# several Mastery-* columns Night Lord's shared skills (Dark Flare/Assassin's-Mark-style rows)
# rely on are needed here too.
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

# Row order (2..LAST_ROW) — derived from this list, never hand-numbered.
ROW_ORDER = [
    "CRUEL_STAB", "STEAL", "MESO_EXPLOSION", "PHASE_DASH", "DARK_FLARE", "SHADOW_PARTNER",
    "VENOM", "TOXIC_VENOM", "INTO_DARKNESS", "ASSASSINATE", "SUDDEN_RAID_BURST",
    "SUDDEN_RAID_DOT", "BLOOD_MONEY", "SMOKESCREEN", "SHADOW_SHIFTER", "SHADOW_SHIFTER_SELF_ATK",
    "MAPLE_HERO_SHADOWER", "NIMBLE_FEET", "DARK_SIGHT_CRIT", "DARK_SIGHT_ATK",
    "AGILE_DAGGERS", "CHANNEL_KARMA", "DAGGER_MASTERY", "CRITICAL_EDGE_RATE",
    "CRITICAL_EDGE_DMG", "PHYSICAL_TRAINING", "DAGGER_EXPERT_SKILL", "DAGGER_EXPERT_MAXDMG",
    "SHADOWER_INSTINCT",
]
ROW = {key: i for i, key in enumerate(ROW_ORDER, start=2)}
LAST_ROW = 1 + len(ROW_ORDER)

# Unlock level for every row — gated all the way down (matches Ice-Lightning-Mage/Bishop's
# thorough approach). Shared-with-Night-Lord rows use Night Lord's own unlock levels directly
# (confirmed identical via Shadower's own Skills page — same "Level required" for every one).
UNLOCK_LEVEL = {
    "CRUEL_STAB": 100,
    "STEAL": 35,
    "MESO_EXPLOSION": 66,
    "PHASE_DASH": 63,
    "DARK_FLARE": 69,
    "SHADOW_PARTNER": 60,
    "VENOM": 72,
    "TOXIC_VENOM": 117,
    "INTO_DARKNESS": 74,
    "ASSASSINATE": 103,
    "SUDDEN_RAID_BURST": 105,
    "SUDDEN_RAID_DOT": 105,
    "BLOOD_MONEY": 107,
    "SMOKESCREEN": 110,
    "SHADOW_SHIFTER": 115,
    "SHADOW_SHIFTER_SELF_ATK": 115,
    "MAPLE_HERO_SHADOWER": 100,
    "DARK_SIGHT_CRIT": 15,
    "DARK_SIGHT_ATK": 15,
    "AGILE_DAGGERS": 33,
    "CHANNEL_KARMA": 40,
    "DAGGER_MASTERY": 43,
    "CRITICAL_EDGE_RATE": 50,
    "CRITICAL_EDGE_DMG": 50,
    "PHYSICAL_TRAINING": 38,
    "DAGGER_EXPERT_SKILL": 120,
    "DAGGER_EXPERT_MAXDMG": 120,
    "SHADOWER_INSTINCT": 125,
    # NIMBLE_FEET: no threshold (shared Explorer skill, level 0) — stays unconditionally unlocked.
}


def unlock_expr(key):
    level = UNLOCK_LEVEL.get(key)
    return "=TRUE" if level is None else f"={IB('level')}>={level}"


# Sudden Raid (DoT) shares Sudden Raid (burst)'s live cooldown cell (same cross-reference
# pattern as Night Lord's own build).
_SUDDEN_RAID_DOT_COOLDOWN = f"=Skills!{SC['Cooldown(s)']}{ROW['SUDDEN_RAID_BURST']}"

# Blood Money triggers alongside Meso Explosion's own cast (no independent cooldown) — shares
# its live Cooldown(s) cell the same way.
_BLOOD_MONEY_COOLDOWN = f"=Skills!{SC['Cooldown(s)']}{ROW['MESO_EXPLOSION']}"

# Maple Hero (Shadower) uses the Bishop-discovered "Final-Damage-chain additive term per named
# skill" mechanic shape, not Night Lord's own per-skill "additional damage%" shape — even though
# Dark Flare/Venom/Shadow Partner are otherwise identical shared-with-Night-Lord rows, their
# Shadower-specific copies do NOT carry MapleHeroBase/MapleHeroFactorIndex (left blank/unused
# for those 3 rows here); instead each gets its own static ratio against MAPLE_HERO_SHADOWER's
# own shared curve (factorIndex 23, baseDamage 150 — confirmed via reverse-engineering that all
# 4 target values scale proportionally across the full level range: Dark Flare 15%, Venom 50%,
# Shadow Partner 50%, Phase Dash 40% at level 1, i.e. ratios 1x/3.3333x/3.3333x/2.6667x against
# Dark Flare's own share). Applied directly in build_calc_sheet/build_sensitivity_sheet via a
# static (Python-side, not a runtime Excel lookup) per-row ratio dict.
MAPLE_HERO_SHADOWER_RATIOS = {
    "DARK_FLARE": 15 / 15,
    "VENOM": 50 / 15,
    "SHADOW_PARTNER": 50 / 15,
    "PHASE_DASH": 40 / 15,
}

# (key, name, jobstep, cooldown, costsAction, actionsPerCast, hits, icd, window, chance, rolls,
#  baseDamage, factorIndex, scales, skillMasteryBonusPct, masteryBossDmgPct, masteryNormalDmgPct,
#  masteryFinalDmgPct, masteryMaxDmgPct, masteryMinDmgPct, masteryCooldownPct,
#  masteryTargetIncrease, normalMonsterTargets, buffTarget, buffDuration, triggersToxicVenom,
#  mapleBase, mapleFactor, stacks, note)
SKILL_ROWS = [
    ("CRUEL_STAB", "Cruel Stab", 4, "", False, 1,
     f"=IF({IB('level')}>=136,6,5)", 0, 0, 100, 1,
     "", "", True,
     level_gated_sum(IB("level"), {102: 10, 106: 1, 116: 1, 120: 1, 128: 1, 132: 1}),
     level_gated_sum(IB("level"), {111: 10, 124: 10}),
     0, 0, 0, 0, 0, 0,
     f'=6+{IB("basic_attack_target_increase")}', "", 0, True, "", "", "",
     "4th-job basic-attack effect (supersedes Double Stab/Savage Blow/Midnight Carnival). "
     "HIGH-CONFIDENCE REUSE of the universal 4th-job basic-attack constant confirmed identical "
     "across every class built so far (Showdown/Chain Lightning/Big Bang/Cruel Stab all share "
     "this exact wiki-documented 290%->522% curve) — factorIndex 21, baseDamage 2900 tenths%, "
     "matching Inputs!skill_coefficient exactly. SkillMasteryBonus% is the 6-tier 'Cruel Stab - "
     "Damage' mastery chain (102-132, cumulative totals 10%->15%, DELTA increments). "
     "MasteryBossDamage% is the 2-tier 'Cruel Stab - Boss Monster Damage' chain (111/124, +20% "
     "total). HitsPerCast 5->6 once the level-136 'Strike' mastery unlocks. Triggers Toxic Venom."),
    ("STEAL", "Steal (self Attack%)", 2, "", False, 1, 1, 0, 0, 100, 1,
     50, 22, True,
     0, 0, 0, 0, 0, 0, 0, 0,
     1, "ATTACK", 0, False, "", "", "",
     "Own self-Attack-buff component only (target-debuff component out of scope — not the "
     "caster's own damage). 5%->6.5% Attack per stack (levels 1-100), stacks up to 3 — modeled "
     "at steady-state max stacks (mirrors Elemental Drain's always-max-stacks convention), so "
     "this row's own contribution is 3x its own F-value, always-on once unlocked (no uptime "
     "averaging — see build_summary_sheet). factorIndex 22, baseDamage 50 tenths%. Mastery "
     "Lv.39 '+5%p activation chance' (10%->15%) has zero DPS effect under the always-max-stacks "
     "assumption (same no-op tier as Bishop's own Elemental-Reset-chance-doubling mastery). "
     "Mastery Lv.54 '+50% Attack reduction on target' is a target-debuff, out of scope."),
    ("MESO_EXPLOSION", "Meso Explosion", 3, 11, True, 1, 3, 0, 0, 100, 1,
     2700, 12, True,
     level_gated_sum(IB("level"), {90: 100}), 0, 0, 0, 0, 0, 0, 0,
     "", "", 0, True, "", "", "",
     "Resource-gated activated skill: 50% chance per attack to generate a Meso stack (max 10); "
     "own cast (this row's own 11s cooldown) deals damage to (stack count) targets. Modeled at "
     "steady state: average stack count at cast time = MIN(10, 0.5*attack_rate*cooldown), "
     "computed as a bespoke NormalMonsterTargets-equivalent formula in build_calc_sheet (left "
     "blank here, NOT a Skills-sheet literal, since it depends on the live Summary attack-rate "
     "cell) — same 'assume steady accumulation' simplification tier as Frost stacks/Elemental "
     "Drain elsewhere. factorIndex 12, baseDamage 2700 tenths% (270% level-1). "
     "SkillMasteryBonus% is Mastery Lv.90 'Meso Explosion damage +100%' (content-based — the "
     "wiki mislabels this row 'Meso Explosion - Strike', ignore the label, the description is "
     "unambiguous). Triggers Toxic Venom."),
    ("PHASE_DASH", "Phase Dash", 3, 23, True, 1, 2, 0, 0, 100, 1,
     4500, 12, True,
     level_gated_sum(IB("level"), {73: 80}), 0, 0, 0, 0, 0, 0, 0,
     9, "", 0, True, "", "", "",
     "450%->... to 7 target(s) (patched Aug 13 2026 -> 9, confirmed no tick/interval mechanic "
     "exists on this skill's own wiki page to change, despite an initially-mis-paired patch-note "
     "line — see the plan's Context section), 2 hits, cooldown 23s, stun not modeled. "
     "factorIndex 12, baseDamage 4500 tenths%. Mastery Lv.73 'Phase Dash - Damage' +80% (real "
     "SkillMasteryBonus%). Triggers Toxic Venom."),
    ("DARK_FLARE", "Dark Flare", 3,
     f"=IF({IB('level')}>=92,45*0.7,45)", True, 1, f"=IF({IB('level')}>=76,3,2)",
     f"=IF({IB('level')}>=104,2*0.75,2)", 20, 100, 1,
     3300, 12, True,
     0, 0, 0, 0, 0, 0,
     f"=IF({IB('level')}>=92,30,0)", 0,
     8, "", 0, True, "", "", "",
     "Shared verbatim w/ Night Lord (identical wiki wording AND identical patch corrections: "
     "hit interval 5s->2s, targets 5->8, damage 400%->330%). factorIndex 12, baseDamage 3300 "
     "tenths%. Mastery Lv.104 (Shadower's own 'Dark Flare - Strike Interval', -25%, matches "
     "Night Lord's own mastery of the same name exactly) baked into the ICD(s) formula; Lv.92 "
     "-30% cooldown baked into Cooldown(s). Maple Hero (Shadower) target — see "
     "MAPLE_HERO_SHADOWER_RATIOS, NOT the generic MapleHeroBase mechanism (unlike Night Lord's "
     "own copy of this row, which uses the generic 'additional damage%' mechanism instead — the "
     "two classes' Maple Hero effects are structurally different even though the base skill is "
     "identical). Triggers Toxic Venom."),
    ("SHADOW_PARTNER", "Shadow Partner", 3, "", False, 1, 1, 0, 0, 25, 1,
     840, 21, True,
     level_gated_sum(IB("level"), {68: 100}), 0, 0, 0, 0, 0, 0, 0,
     1, "", 0, False, "", "", "",
     "Shared verbatim w/ Night Lord. Hybrid row: Calc columns D-I computed like a normal damage "
     "row but Calc!O forced to 0 — not an independent hit; Summary reads this row's Calc!F "
     "directly and folds into the shared extra_mult chain. factorIndex 21, baseDamage 840 "
     "tenths%. ProcChance% is the real 25% proc rate. SkillMasteryBonus% is Mastery Lv.68 "
     "'Shadow Partner - Damage' +100%. Maple Hero (Shadower) target — see "
     "MAPLE_HERO_SHADOWER_RATIOS (structurally different from Night Lord's own copy, same "
     "caveat as Dark Flare above)."),
    ("VENOM", "Venom", 3, 1, False, 1, 1, 0, 0, 100, 1,
     450, 21, True,
     0, 0, 0, 0, 0, 0, 0, 0,
     1, "", 0, False, "", "", "",
     "Shared verbatim w/ Night Lord (patched poison chance 30%->50%, modeled always-active at "
     "steady state — matches Night Lord's own treatment exactly, including the Cooldown=1 "
     "'always-on tick' trick). factorIndex 21, baseDamage 450 tenths% (45%->81%, levels "
     "1-200) — reverse-engineered fresh this session and confirmed to resolve to the EXACT same "
     "tuple Night Lord already uses, cross-validating the shared-skill-reuse premise. Mastery "
     "Lv.82 Weaken (+15%p Damage Taken while poisoned, patched from 12% — matches Night Lord's "
     "own Venom - Weaken mastery exactly, confirmed via the patch note despite the wiki mastery "
     "table mislabeling this row 'Meso Explosion - Damage') is a GLOBAL always-on monster-"
     "damage-taken bonus, not a per-row Mastery column — see build_summary_sheet. Maple Hero "
     "(Shadower) target — see MAPLE_HERO_SHADOWER_RATIOS (structurally different from Night "
     "Lord's own copy, same caveat as Dark Flare above)."),
    ("TOXIC_VENOM", "Toxic Venom", 4, "", False, 1, 1, 0, 0, 20, 1,
     6000, 21, True,
     level_gated_sum(IB("level"), {130: 100}),
     0, 0, 0, 0, 0, 0, 0,
     1, "", 0, False, "", "", "",
     "Shared verbatim w/ Night Lord. No ICD — every attack against a (permanently poisoned) "
     "target independently rolls the 20% chance. Trigger rate = the combined per-second hit "
     "rate of every row with TriggersToxicVenom=TRUE. factorIndex 21, baseDamage 6000 tenths% "
     "(600%->1080%, levels 1-200). SkillMasteryBonus% is Mastery Lv.130 'Toxic Venom - Damage' "
     "+100% (Shadower's own tier — same mastery name/effect as Night Lord's own Lv.128 tier, "
     "just at a different level in this class's own mastery table)."),
    ("INTO_DARKNESS", "Into Darkness", 3, 40, True, 1, 1, 0, 0, 100, 1,
     200, 21, True,
     0, 0, 0, 0, 0, 0, 0, 0,
     1, "FINAL_DAMAGE", 13, False, "", "", "",
     "FLAGGED (full curve exists, but a genuinely new skill with no cross-class precedent to "
     "sanity-check against): +20%->28% Final Damage for 13s, cooldown 40s. Basic-attack-damage "
     "immunity component (defensive) not modeled. factorIndex 21, baseDamage 200 tenths%."),
    ("ASSASSINATE", "Assassinate", 4, 13, True, 1, 2, 0, 0, 100, 1,
     14000, 21, True,
     0, 0, 0, 0, 0, 0, 0, 0,
     1, "", 0, True, "", "", "",
     "2-part damage structure: base 1400%->1680%(lvl50, curve continues) x2 hits (factorIndex "
     "21, baseDamage 14000 tenths%), PLUS a periodic finishing blow (+3000%->3750%(lvl50) "
     "additional damage, factorIndex 12, baseDamage 30000 tenths% — see FINISHER constants "
     "below) landing on average every 2nd cast (modeled as a flat 50% average multiplier, not "
     "an exact odd/even cast counter). This row needs a BESPOKE Calc!F formula (two independent "
     "FactorTable lookups combined additively, the finisher term halved for its average-every-"
     "2nd-cast frequency) — see build_calc_sheet. Mastery Lv.108 'Murderous Intent' doubles the "
     "NEXT finishing blow after a Blood Money attack — modeled as a steady-state average "
     "multiplier on the finisher term (probability = MIN(1, Blood-Money's own cast rate / "
     "Assassinate's own finisher rate)), not an exact alternating-state machine. Mastery Lv.134 "
     "'Assassinate - Damage' +50% (real, applies to the base-hit term only, matching the wiki's "
     "own 'Assassinate damage' wording which doesn't call out the finisher specifically). "
     "Curve confidence note: the patch's own qualitative text ('base hit damage now increases "
     "more significantly with skill level') has no numeric override — using the wiki's own "
     "current curve as the best available data. Triggers Toxic Venom (a genuine independent "
     "attack, unlike Venom/Shadow Partner/Shadow Shifter's own deliberate exclusions)."),
    ("SUDDEN_RAID_BURST", "Sudden Raid (burst)", 4, 19, True, 1, 3, 0, 0, 100, 1,
     14000, 12, True,
     level_gated_sum(IB("level"), {126: 50}), 0, 0, 0, 0, 0, 0, 0,
     8, "", 0, True, "", "", "",
     "Shared verbatim w/ Night Lord. factorIndex 12, baseDamage 14000 tenths% (1400%->2800%, "
     "levels 1-200). Mastery Lv.126 'Sudden Raid - Damage' +50% (Shadower's own tier, at a "
     "different level than Night Lord's own Lv.124 tier for the same mastery name — each "
     "class's mastery TABLE assigns its own level to a shared base skill's mastery, confirmed "
     "not an error). Does not apply to the DoT row below."),
    ("SUDDEN_RAID_DOT", "Sudden Raid (DoT)", 4, _SUDDEN_RAID_DOT_COOLDOWN, False, 1, 1, 1, 5, 100, 1,
     3600, 12, True,
     0, 0, 0, 0, 0, 0, 0, 0,
     8, "", 0, True, "", "", "",
     "Shared verbatim w/ Night Lord. Shares Sudden Raid (burst)'s live Cooldown(s) cell. "
     "factorIndex 12, baseDamage 3600 tenths% (360%->720%, levels 1-200), 5s window / 1s ICD = "
     "5 EffectiveHits per cast."),
    ("BLOOD_MONEY", "Blood Money", 4, _BLOOD_MONEY_COOLDOWN, False, 1, 3, 0, 0, 100, 1,
     36000, 12, True,
     level_gated_sum(IB("level"), {122: 50, 138: 50}), 0, 0, 0, 0, 0, 0,
     f'=IF({IB("level")}>=138,3,IF({IB("level")}>=122,2,1))',
     "", "", 0, True, "", "", "",
     "PATCHED (Aug 13 2026): base damage 2800%->3600% (curve rescaled 1.2857x before reverse-"
     "engineering — factorIndex 12, baseDamage 36000 tenths% already reflects the patched "
     "value), single-target +5%/stack bonus REMOVED. Triggers alongside Meso Explosion's own "
     "cast (shares its live Cooldown(s) cell, no independent cooldown) — 50% chance PER meso-"
     "generation-roll to also create a Blood Money stack (max 5), modeled at steady state: "
     "MIN(5, 0.25*attack_rate*11) (0.5 meso-chance x 0.5 blood-money-chance), a bespoke "
     "NormalMonsterTargets-equivalent formula in build_calc_sheet (left blank here, same "
     "treatment as Meso Explosion's own targets formula). MasteryTargetIncrease field repurposed "
     "here as the stack-to-targets MULTIPLIER (1x pre-122, 2x at 122, 3x at 138 — both Lv.122 "
     "and Lv.138 masteries renamed 'Damage & Target' by the patch, see the plan's Context "
     "section for the full before/after reconciliation). SkillMasteryBonus% is the combined "
     "+50%(122)+50%(138) = +100% total once both unlock. Triggers Toxic Venom."),
    ("SMOKESCREEN", "Smokescreen", 4, 45, True, 1, 1, 0, 0, 100, 1,
     130, 22, True,
     0, 0, 0, 0, 0, 0, 0, 0,
     1, "FINAL_DAMAGE", 20, False, "", "", "",
     "Enemy-debuff components (Accuracy/Evasion/Defense reduction) and ally-damage-taken-"
     "reduction not modeled (no such mechanics exist anywhere in this calculator). Self Final "
     "Damage component only: +13%->14.9%(lvl50, curve continues) for 20s, cooldown 45s. "
     "factorIndex 22, baseDamage 130 tenths% — confirmed via exact-floor curve matching (the "
     "naive mean-based resolver initially suggested 129, off by one due to this being a small-"
     "magnitude curve, same class of rounding issue flagged in this project's own memory notes "
     "for FP-Mage — resolved by checking which integer base reproduces every sampled level's "
     "value exactly under floor-to-1-decimal rounding, not just within a loose tolerance). "
     "Mastery Lv.113 'Smokescreen - Critical': -10% enemy Critical Resistance in range (not "
     "modeled) + allies' Critical Damage +30% (self-inclusive, feeds a Crit-Damage-bonus "
     "accumulator in build_summary_sheet, duty-cycle-averaged off this row's own uptime)."),
    ("SHADOW_SHIFTER", "Shadow Shifter (counterattack)", 4, "", False, 1, 1, 0, 0, 100, 1,
     25000, 21, True,
     0, 0, 0, 0, 0, 0, 0, 0,
     1, "", 0, False, "", "", "",
     "Shared verbatim w/ Night Lord. Counterattack DPS = Inputs!incoming_hit_rate * 20% * "
     "ExpectedDamage(counterHit) — bespoke O-column branch, no Cooldown(s)/rate machinery of "
     "its own. factorIndex 21, baseDamage 25000 tenths% (2500%->4500%, levels 1-200)."),
    ("SHADOW_SHIFTER_SELF_ATK", "Shadow Shifter (self Attack%)", 4, "", False, 1, 1, 0, 0, 100, 1,
     100, 22, True,
     0, 0, 0, 0, 0, 0, 0, 0,
     1, "ATTACK", 0, False, "", "", "",
     "Shared verbatim w/ Night Lord. Passive-mult delta-tracking row (10%->16% self Attack) — "
     "assumed already baked into Inputs!ATTACK_PCT (Magic Critical pattern). factorIndex 22, "
     "baseDamage 100 tenths%."),
    ("MAPLE_HERO_SHADOWER", "Maple Hero", 4, "", False, 1, 1, 0, 0, 100, 1,
     150, 23, True,
     0, 0, 0, 0, 0, 0, 0, 0,
     1, "", 0, False, "", "", "",
     "Shared curve feeding Dark Flare/Venom/Shadow Partner/Phase Dash's own Final Damage chains "
     "(see MAPLE_HERO_SHADOWER_RATIOS) — confirmed via reverse-engineering that all 4 target "
     "values scale proportionally across the full level range (factorIndex 23, baseDamage 150 "
     "tenths%, representing Dark Flare's own 1x share; Venom/Shadow Partner are 3.3333x, Phase "
     "Dash is 2.6667x). No independent DPS row of its own (Calc columns J-N stay blank/0, same "
     "'no independent row' pattern as Night Lord's own Night Lord's Mark) — only D/E/F are "
     "computed, read directly by each target row's own K-column formula."),
    ("NIMBLE_FEET", "Nimble Feet", 1, 60, True, 1, 1, 0, 0, 100, 1,
     150, 0, False,
     0, 0, 0, 0, 0, 0, 0, 0,
     1, "ATTACK_SPEED", 15, False, "", "", "",
     "Shared verbatim w/ Night Lord/FP-Mage. Flat +15% Attack Speed / +10% Speed for 15s, 60s "
     "cooldown, non-scaling. FactorIndex unused placeholder."),
    ("DARK_SIGHT_CRIT", "Dark Sight (Crit Rate)", 1, 25, False, 1, 1, 0, 0, 100, 1,
     60, 21, True,
     0, 0, 0, 0, 0, 0, 0, 0,
     1, "CRIT_RATE", f"=IF({IB('level')}>=24,12,8)", False, "", "", "",
     "Shared verbatim w/ Night Lord (identical wording). Two-stage activation grants +6%->8.4% "
     "Crit Rate for 8s (->12s once Mastery Lv.24 'Dark Sight - Persistence' unlocks). "
     "factorIndex 21, baseDamage 60 tenths%. Passenger row (CostsActionSlot=False)."),
    ("DARK_SIGHT_ATK", "Dark Sight (Attack)", 1, 25, True, 2, 1, 0, 0, 100, 1,
     100, 21, True,
     0, 0, 0, 0, 0, 0, 0, 0,
     1, "ATTACK", f"=IF({IB('level')}>=24,12,8)", False, "", "", "",
     "Shared verbatim w/ Night Lord. Same 2-stage activation, +10%->14% Attack for 8s (->12s at "
     "Mastery Lv.24). factorIndex 21, baseDamage 100 tenths%. ActionsPerCast=2."),
    ("AGILE_DAGGERS", "Agile Daggers", 2, "", False, 1, 1, 0, 0, 100, 1,
     50, 22, True,
     0, 0, 0, 0, 0, 0, 0, 0,
     1, "ATTACK_SPEED", 0, False, "", "", "",
     "HIGH-CONFIDENCE REUSE (no individual wiki page exists for this specific skill, but its "
     "level-1 text '+5% Attack Speed' is word-for-word identical to Night Lord's own Agile "
     "Claws): reuses that exact factorIndex 22/baseDamage 50 tenths% pair. Magic Critical "
     "pattern — already baked into Inputs!ATTACK_SPEED%; feeds the 2nd-Job Skill Level Bonus "
     "Sensitivity delta only."),
    ("CHANNEL_KARMA", "Channel Karma (self Attack%)", 2, "", False, 1, 1, 0, 0, 100, 1,
     80, 22, True,
     0, 0, 0, 0, 0, 0, 0, 0,
     1, "ATTACK", 0, False, "", "", "",
     "FLAGGED ASSUMPTION (no individual wiki page exists): factorIndex 22 (convention), "
     "baseDamage 80 tenths% (8% level-1 Attack component). Critical Resistance component not "
     "modeled (no such mechanic exists). Magic Critical pattern — already baked into "
     "Inputs!ATTACK_PCT; feeds the 2nd-Job Skill Level Bonus delta only."),
    ("DAGGER_MASTERY", "Dagger Mastery", 2, "", False, 1, 1, 0, 0, 100, 1,
     150, 22, True,
     0, 0, 0, 0, 0, 0, 0, 0,
     1, "MIN_DAMAGE", 0, False, "", "", "",
     "Magic Critical pattern — already baked into Inputs!MIN_DAMAGE%; feeds the 2nd-Job Skill "
     "Level Bonus delta. factorIndex 22, baseDamage 150 tenths%."),
    ("CRITICAL_EDGE_RATE", "Critical Edge (Crit Rate)", 2, "", False, 1, 1, 0, 0, 100, 1,
     60, 22, True,
     0, 0, 0, 0, 0, 0, 0, 0,
     1, "CRIT_RATE", 0, False, "", "", "",
     "Magic Critical pattern — already baked into Inputs!CRIT_RATE%; feeds the 2nd-Job Skill "
     "Level Bonus delta. factorIndex 22, baseDamage 60 tenths%."),
    ("CRITICAL_EDGE_DMG", "Critical Edge (Crit Damage)", 2, "", False, 1, 1, 0, 0, 100, 1,
     100, 22, True,
     0, 0, 0, 0, 0, 0, 0, 0,
     1, "CRIT_DAMAGE", 0, False, "", "", "",
     "Same skill as Critical Edge (Crit Rate) above. Magic Critical pattern — already baked "
     "into Inputs!CRIT_DAMAGE%; feeds the 2nd-Job Skill Level Bonus delta. factorIndex 22, "
     "baseDamage 100 tenths%."),
    ("PHYSICAL_TRAINING", "Physical Training", 2, "", False, 1, 1, 0, 0, 100, 1,
     100, 22, True,
     0, 0, 0, 0, 0, 0, 0, 0,
     1, "BASIC_ATTACK_DAMAGE", 0, False, "", "", "",
     "Magic Critical pattern — already baked into Inputs!BASIC_ATTACK_DAMAGE%; feeds the "
     "2nd-Job Skill Level Bonus delta. factorIndex 22, baseDamage 100 tenths%."),
    ("DAGGER_EXPERT_SKILL", "Dagger Expert (Skill Damage)", 4, "", False, 1, 1, 0, 0, 100, 1,
     150, 22, True,
     0, 0, 0, 0, 0, 0, 0, 0,
     1, "SKILL_DAMAGE", 0, False, "", "", "",
     "Magic Critical pattern — already baked into Inputs!SKILL_DAMAGE%; feeds the 4th-Job Skill "
     "Level Bonus delta (Skill Damage side). factorIndex 22, baseDamage 150 tenths%."),
    ("DAGGER_EXPERT_MAXDMG", "Dagger Expert (Max Damage Multiplier)", 4, "", False, 1, 1, 0, 0, 100, 1,
     200, 22, True,
     0, 0, 0, 0, 0, 0, 0, 0,
     1, "MAX_DAMAGE", 0, False, "", "", "",
     "Same skill as Dagger Expert (Skill Damage) above, +20%->23% Max Damage Multiplier. Magic "
     "Critical pattern — already baked into Inputs!MAX_DAMAGE%; feeds the 4th-Job Skill Level "
     "Bonus delta (Max Damage Multiplier side). factorIndex 22, baseDamage 200 tenths%."),
    ("SHADOWER_INSTINCT", "Shadower Instinct", 4, "", False, 1, 1, 0, 0, 100, 1,
     200, 22, True,
     0, 0, 0, 0, 0, 0, 0, 0,
     1, "FINAL_DAMAGE", 0, False, "", "", "",
     "Magic Critical pattern — already baked into Inputs!FINAL_DAMAGE%; feeds the 4th-Job Skill "
     "Level Bonus delta. factorIndex 22, baseDamage 200 tenths%."),
]

# Rows with a real Cooldown(s) value (literal or a live formula reference).
ROW_HAS_COOLDOWN = {row[0]: row[3] not in ("", None) for row in SKILL_ROWS}

# Every row checks its own CostsActionSlot for CDR eligibility (identity default) — no
# cross-row overrides needed (Sudden Raid DoT/Blood Money share a sibling's live Cooldown(s)
# cell but are themselves CostsActionSlot=False, so effective_cooldown_expr never applies CDR
# to them regardless of which row's flag is checked).
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
    "PHASE_DASH", "DARK_FLARE", "VENOM", "SUDDEN_RAID_BURST", "SUDDEN_RAID_DOT",
]
# Real, always-on buff rows (NOT baked into Inputs) whose (F * uptime) feeds the shared
# multiplicative avg_buff_mult chain.
BUFF_ROW_KEYS = ["DARK_SIGHT_ATK", "INTO_DARKNESS", "SMOKESCREEN"]
# "Magic Critical pattern" rows: permanent passives assumed already reflected in a matching
# Inputs% field — Calc!F used only by the Sensitivity sheet's own marginal delta.
PASSIVE_MULT_ROW_KEYS = [
    "AGILE_DAGGERS", "CHANNEL_KARMA", "DAGGER_MASTERY", "CRITICAL_EDGE_RATE",
    "CRITICAL_EDGE_DMG", "PHYSICAL_TRAINING", "DAGGER_EXPERT_SKILL", "DAGGER_EXPERT_MAXDMG",
    "SHADOWER_INSTINCT", "SHADOW_SHIFTER_SELF_ATK",
]
HYBRID_ROW_KEYS = ["SHADOW_PARTNER"]
TOXIC_VENOM_ROW_KEYS = ["TOXIC_VENOM"]
SHADOW_SHIFTER_ROW_KEYS = ["SHADOW_SHIFTER"]
MESO_EXPLOSION_ROW_KEYS = ["MESO_EXPLOSION"]
BLOOD_MONEY_ROW_KEYS = ["BLOOD_MONEY"]
ASSASSINATE_ROW_KEYS = ["ASSASSINATE"]
MAPLE_HERO_SHADOWER_ROW_KEYS = ["MAPLE_HERO_SHADOWER"]
# Every row that can ever post a nonzero Calc!O DPS value — used to filter the Summary sheet's
# per-skill breakdown table down to real damage sources (buffs/passives/multiplier-feeders always
# show 0.0000 there and are dropped).
DAMAGE_DEALING_KEYS = (
    ["CRUEL_STAB"] + DAMAGE_ROW_KEYS + TOXIC_VENOM_ROW_KEYS + SHADOW_SHIFTER_ROW_KEYS
    + MESO_EXPLOSION_ROW_KEYS + BLOOD_MONEY_ROW_KEYS + ASSASSINATE_ROW_KEYS
)

CALC_HEADERS = [
    "Key", "Name", "Unlocked", "InputLevel", "Factor", "CoefficientPercent",
    "EffectiveHits", "ProcProbability", "MapleHeroMultiplier",
    "BaseDamage", "BaseHitDamage", "NonCritAvg", "CritAvg", "ExpectedDamage(perHit)",
    "DPS", "% of Total", "InvCooldown", "CastsInFight", "HitRate(perSec)",
]
CCOL = {name: get_column_letter(i + 1) for i, name in enumerate(CALC_HEADERS)}


def S(col_name, r):
    """Shorthand for a Skills-sheet cell reference by column name."""
    return f"Skills!{SC[col_name]}{r}"


# ---------------------------------------------------------------------------
# Summary-sheet row layout — fixed constants (build_calc_sheet's formula strings reference them
# before build_summary_sheet runs; cross-sheet references don't care about python build order).
# Layout: TOTAL DPS + the two summary tables (breakdown, marginal-value) sit at the top of the
# sheet (rows 3-47ish, sized dynamically off DAMAGE_DEALING_KEYS/STAT_SWEEP); every other
# accumulator/derived-value row is pushed below that into an "info dump" block starting at 49.
# ---------------------------------------------------------------------------
R_TOTAL = 3
SUMMARY_BREAKDOWN_HEADER_ROW = 6
R_AVGBUFF = 57                  # Average Buff Multiplier (Dark Sight Attack + Into Darkness + Smokescreen FD)
R_CRIT_RATE_BONUS = 58         # Dark Sight (Crit Rate), duty-cycle averaged, additive to Inputs!crit_rate
R_MONSTER_DMG_BONUS = 59        # Venom Lv.82 Weaken, additive to Monster Damage%
R_SHADOW_PARTNER_MULT = 60      # Shadow Partner average multiplier
R_AS_BONUS = 61                 # Nimble Feet (duty-cycle) + Steal (always-on, 3x stacks)
R_APS = 62                      # Actions Per Second
R_CASTRATE = 63                 # Skill + buff cast rate (subtracted from Cruel Stab)
R_BAPS = 64                     # Cruel Stab (basic attack) Casts Per Second
R_CRIT_DAMAGE_BONUS = 65        # Smokescreen Mastery Lv.113, duty-cycle-averaged, additive to Inputs!crit_damage
R_MESO_STACK_AVG = 66           # Meso Explosion's own average stack count at cast time
R_BLOOD_MONEY_STACK_AVG = 67    # Blood Money's own average stack count at cast time
R_MURDEROUS_INTENT_MULT = 68    # Assassinate finisher average multiplier (Mastery Lv.108)
R_CRUEL_STAB_DPS = 69


def buff_uptime_expr(fda_ref, monster_type_ref, row, bdi_ref, fight_duration_ref, calc_r_col_ref):
    return uptime_fraction_or_exact_expr(
        fda_ref, calc_r_col_ref, monster_type_ref, S("BuffDuration(s)", row), S("Cooldown(s)", row),
        bdi_ref, fight_duration_ref,
    )


def build_calc_sheet(wb):
    ws = wb.create_sheet("Calc")
    for i, name in enumerate(CALC_HEADERS):
        ws.cell(row=1, column=i + 1, value=name)
    style_header_row(ws, 1, len(CALC_HEADERS))

    ws["U1"] = "Maple Hero (Shadower) helper — unused (see MAPLE_HERO_SHADOWER row's own Note)"
    ws["U1"].font = LABEL_FONT

    fixed_duration_active_main = fixed_duration_active_expr(IB("monster_type"), IB("fight_duration"))
    bdi_main = IB("buff_duration_increase_pct")

    monster_dmg_bonus_ref = f"Summary!$B${R_MONSTER_DMG_BONUS}"
    crit_rate_total_ref = f'({IB("crit_rate")}+Summary!$B${R_CRIT_RATE_BONUS})'
    crit_damage_total_ref = f'({IB("crit_damage")}+Summary!$B${R_CRIT_DAMAGE_BONUS})'
    avg_buff_mult_ref = f"Summary!$B${R_AVGBUFF}"
    shadow_partner_mult_ref = f"Summary!$B${R_SHADOW_PARTNER_MULT}"

    mh_row = ROW["MAPLE_HERO_SHADOWER"]
    maple_hero_gated = f'IF(C{mh_row}=TRUE,F{mh_row},0)'

    FULL_HIT_PIPELINE_KEYS = (
        ["CRUEL_STAB"] + DAMAGE_ROW_KEYS + TOXIC_VENOM_ROW_KEYS + SHADOW_SHIFTER_ROW_KEYS
        + MESO_EXPLOSION_ROW_KEYS + BLOOD_MONEY_ROW_KEYS + ASSASSINATE_ROW_KEYS
    )
    GENERIC_O_KEYS = DAMAGE_ROW_KEYS + MESO_EXPLOSION_ROW_KEYS + BLOOD_MONEY_ROW_KEYS + ASSASSINATE_ROW_KEYS

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

        if key == "CRUEL_STAB":
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
            if key == "ASSASSINATE":
                # Bespoke: base-hit term (own factorIndex 21) + mastery, PLUS the finisher term
                # (own factorIndex 12, via a second FactorTable lookup on the SAME InputLevel)
                # averaged by the murderous-intent multiplier and halved for its "every 2nd
                # cast" frequency. Finisher's own FactorIndex (12) is hardcoded here since this
                # row's own FactorIndex field (21) only describes the base-hit term.
                finisher_factor = (
                    f'INDEX(FactorTable!$B$2:$Y$301, MATCH(ROUND(MIN(300,MAX(1,D{r})),0), '
                    f'FactorTable!$A$2:$A$301,0), 13)'
                )
                finisher_pct = f'(30000/10)*({finisher_factor}/1000)'
                ws.cell(row=r, column=6, value=(
                    f"=({S('BaseDamage(tenths%)', r)}/10)*(E{r}/1000)+IF({IB('level')}>=134,50,0)"
                    f"+0.5*{finisher_pct}*Summary!$B${R_MURDEROUS_INTENT_MULT}"
                ))
            else:
                ws.cell(row=r, column=6, value=(
                    f'=IF({S("ScalesWithLevel", r)}=TRUE,({S("BaseDamage(tenths%)", r)}/10)*(E{r}/1000),'
                    f'{S("BaseDamage(tenths%)", r)}/10)+{S("SkillMasteryBonus%", r)}'
                ))

        ws.cell(row=r, column=7, value=(
            f'={S("HitsPerCast", r)}*IF({S("ICD(s)", r)}>0,{S("ActiveWindow(s)", r)}/{S("ICD(s)", r)},1)'
        ))
        ws.cell(row=r, column=8, value=f'=1-(1-{S("ProcChance%", r)}/100)^{S("RollsPerCast", r)}')
        ws.cell(row=r, column=9, value="1")

        if key in FULL_HIT_PIPELINE_KEYS:
            ws.cell(row=r, column=10, value=f'={IB("attack")}*(F{r}/100)')
            monster_dmg_term = monster_blend_expr(
                IB("monster_type"), IB("normal_weight_frac"),
                f'{IB("boss_damage")}+{S("MasteryBossDamage%", r)}+{monster_dmg_bonus_ref}',
                f'{IB("normal_damage")}+{S("MasteryNormalDamage%", r)}+{monster_dmg_bonus_ref}',
                "0",
            )
            maple_ratio = MAPLE_HERO_SHADOWER_RATIOS.get(key)
            maple_term = f'*(1+{maple_ratio}*{maple_hero_gated}/100)' if maple_ratio else ''
            ws.cell(row=r, column=11, value=(
                f'=J{r}*(1+{IB("stat_damage")}/100)*(1+{IB("damage")}/100)'
                f'*(1+{monster_dmg_term}/100)'
                f'*(1+{IB("damage_amp")}/100)'
                f'*(5000/(6000+{IB("monster_defense")}*(1-{IB("def_pen")}/100)))'
                f'*(1+{IB("final_damage")}/100)'
                f'{maple_term}'
                f'*(1+(IF({S("Key", r)}="CRUEL_STAB",{IB("basic_attack_damage")},{IB("skill_damage")}))/100)'
                f'*({avg_buff_mult_ref}*{shadow_partner_mult_ref}*I{r})'
            ))
            ws.cell(row=r, column=12, value=f'=K{r}*(MIN({IB("min_damage")},{IB("max_damage")})/100+{IB("max_damage")}/100)/2')
            ws.cell(row=r, column=13, value=f'=L{r}*(1+{crit_damage_total_ref}/100)')
            ws.cell(row=r, column=14, value=(
                f'=L{r}*(1-MIN({crit_rate_total_ref},100)/100)+M{r}*(MIN({crit_rate_total_ref},100)/100)'
            ))
        else:
            for col in (10, 11, 12, 13, 14):
                ws.cell(row=r, column=col, value="")

        if key == "CRUEL_STAB":
            ws.cell(row=r, column=15, value=(
                f"=IF(C{r},{S('HitsPerCast', r)}*N{r}*Summary!$B${R_BAPS}*"
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
        elif key in MESO_EXPLOSION_ROW_KEYS:
            stack_expr = f'MIN(10,0.5*Summary!$B${R_APS}*{S("Cooldown(s)", r)})'
            ws.cell(row=r, column=15, value=(
                f'=IF(C{r},H{r}*N{r}*{rate_r}*'
                f"{target_multiplier_expr(IB('monster_type'), IB('normal_weight_frac'), stack_expr, IB('max_enemies_hit'))},0)"
            ))
        elif key in BLOOD_MONEY_ROW_KEYS:
            stack_expr = (
                f'MIN(5,0.25*Summary!$B${R_APS}*{S("Cooldown(s)", ROW["MESO_EXPLOSION"])})'
                f'*{S("MasteryTargetIncrease", r)}'
            )
            ws.cell(row=r, column=15, value=(
                f'=IF(C{r},H{r}*N{r}*{rate_r}*'
                f"{target_multiplier_expr(IB('monster_type'), IB('normal_weight_frac'), stack_expr, IB('max_enemies_hit'))},0)"
            ))
        elif key in GENERIC_O_KEYS:
            ws.cell(row=r, column=15, value=(
                f'=IF(C{r},H{r}*N{r}*{rate_r}*'
                f"{target_multiplier_expr(IB('monster_type'), IB('normal_weight_frac'), S('NormalMonsterTargets', r), IB('max_enemies_hit'))},0)"
            ))
        else:
            ws.cell(row=r, column=15, value=0)

        ws.cell(row=r, column=16, value=f'=IF(Summary!$B${R_TOTAL}=0,0,O{r}/Summary!$B${R_TOTAL})')
        ws.cell(row=r, column=17, value=(f'=IFERROR(1/{eff_cd_r},0)' if has_cooldown else 0))

        if has_cooldown:
            ws.cell(row=r, column=18, value=(
                f'=IF({fixed_duration_active_main},{exact_casts_expr(IB("fight_duration"), eff_cd_r)},0)'
            ))
        else:
            ws.cell(row=r, column=18, value=0)

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
    ws["A1"] = "Shadower — DPS Summary"
    ws["A1"].font = Font(bold=True, size=14)

    ws.cell(row=DERIVED_HEADER_ROW, column=1, value="Derived Values (read-only, computed from Inputs)").font = SECTION_FONT
    ws.cell(row=D_ATTACK, column=1, value="ATTACK (= Flat ATTACK x (1+ATTACK%/100))")
    ws.cell(row=D_ATTACK, column=2, value=f'={IB("flat_attack")}*(1+{IB("attack_pct")}/100)')

    ws.cell(row=D_STAT_DAMAGE, column=1, value="STAT_DAMAGE % (= 1% of total LUK + 0.25% of DEX)")
    ws.cell(
        row=D_STAT_DAMAGE, column=2,
        value=f'=({IB("flat_luk")}*(1+{IB("luk_pct")}/100))*0.01+{IB("dex")}*0.0025'
    )

    ws.cell(row=D_BASIC_INPUT_LEVEL, column=1, value="Basic Attack (Cruel Stab) Input Level (4th job formula)")
    ws.cell(
        row=D_BASIC_INPUT_LEVEL, column=2,
        value=f'=MAX(0,({IB("level")}-100)*3)+{IB("skill_lvl_4th")}+{IB("skill_lvl_all")}'
    )
    ws.cell(row=D_BASIC_FACTOR, column=1, value="Basic Attack Factor (factorIndex 21, from Cruel Stab == Showdown/Chain Lightning/Big Bang reuse)")
    ws.cell(
        row=D_BASIC_FACTOR, column=2,
        value=f'=INDEX(FactorTable!$B$2:$Y$301, MATCH(ROUND(MIN(300,MAX(1,{IB("basic_input_level")})),0), '
              f'FactorTable!$A$2:$A$301,0), 22)'
    )
    ws.cell(row=D_SKILL_COEFFICIENT, column=1, value="SKILL_COEFFICIENT — Cruel Stab base coefficient % (before Skill Mastery)")
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

    r_dsc, r_dsa = ROW["DARK_SIGHT_CRIT"], ROW["DARK_SIGHT_ATK"]
    r_nf = ROW["NIMBLE_FEET"]
    r_steal = ROW["STEAL"]
    r_sp = ROW["SHADOW_PARTNER"]
    r_id, r_ss = ROW["INTO_DARKNESS"], ROW["SMOKESCREEN"]
    r_me, r_bm, r_asn = ROW["MESO_EXPLOSION"], ROW["BLOOD_MONEY"], ROW["ASSASSINATE"]

    dark_sight_crit_avg = f'((Calc!C{r_dsc}=TRUE)*Calc!F{r_dsc}*{buff_uptime(r_dsc)})'
    dark_sight_atk_avg = f'((Calc!C{r_dsa}=TRUE)*Calc!F{r_dsa}*{buff_uptime(r_dsa)})'
    into_darkness_avg = f'((Calc!C{r_id}=TRUE)*Calc!F{r_id}*{buff_uptime(r_id)})'
    smokescreen_avg = f'((Calc!C{r_ss}=TRUE)*Calc!F{r_ss}*{buff_uptime(r_ss)})'
    nimble_feet_avg = f'((Calc!C{r_nf}=TRUE)*Calc!F{r_nf}*{buff_uptime(r_nf)})'
    # Steal's own self-Attack-buff, steady-state max stacks (x3), always-on once unlocked (no
    # uptime averaging — it's a permanent proc-driven passive, not a timed buff in the
    # BuffDuration(s)/Cooldown(s) sense).
    steal_avg = f'((Calc!C{r_steal}=TRUE)*Calc!F{r_steal}*3)'

    ws.cell(row=R_AVGBUFF, column=1, value="Average Buff Multiplier (Dark Sight Attack + Into Darkness + Smokescreen FD)")
    ws.cell(row=R_AVGBUFF, column=2, value=(
        f'=(1+{dark_sight_atk_avg}/100)*(1+{into_darkness_avg}/100)*(1+{smokescreen_avg}/100)'
    ))

    ws.cell(row=R_CRIT_RATE_BONUS, column=1, value="Global Crit Rate Bonus % (Dark Sight Crit Rate, duty-cycle averaged)")
    ws.cell(row=R_CRIT_RATE_BONUS, column=2, value=f'={dark_sight_crit_avg}')

    ws.cell(row=R_MONSTER_DMG_BONUS, column=1, value="Global Monster Damage-Taken Bonus % (Venom Lv.82 Weaken, patched 12%->15%)")
    ws.cell(row=R_MONSTER_DMG_BONUS, column=2, value=f'=IF({IB("level")}>=82,15,0)')

    ws.cell(row=R_SHADOW_PARTNER_MULT, column=1, value="Shadow Partner Average Multiplier")
    mh_row = ROW["MAPLE_HERO_SHADOWER"]
    sp_maple_ratio = MAPLE_HERO_SHADOWER_RATIOS["SHADOW_PARTNER"]
    sp_maple_term = f'*(1+{sp_maple_ratio}*IF(Calc!C{mh_row}=TRUE,Calc!F{mh_row},0)/100)'
    ws.cell(row=R_SHADOW_PARTNER_MULT, column=2, value=(
        f'=1+((Calc!C{r_sp}=TRUE)*Calc!F{r_sp}{sp_maple_term}*Calc!I{r_sp}*{S("ProcChance%", r_sp)}/100)/100'
    ))

    ws.cell(row=R_AS_BONUS, column=1, value="Attack Speed Buff Bonus % (Nimble Feet, averaged + Steal, always-on)")
    ws.cell(row=R_AS_BONUS, column=2, value=f'={nimble_feet_avg}+{steal_avg}')

    ws.cell(row=R_APS, column=1, value="Actions Per Second")
    ws.cell(row=R_APS, column=2, value=(
        f'=1+MIN(150,150*(1-(1-{IB("attack_speed")}/150)*(1-B{R_AS_BONUS}/150)))/100'
    ))

    ws.cell(row=R_CASTRATE, column=1, value="Skill + Buff Cast Rate (subtracted from Cruel Stab, 1/s)")
    ws.cell(row=R_CASTRATE, column=2, value=(
        f'=IF({fda_main},'
        f'SUMPRODUCT((Skills!{SC["CostsActionSlot"]}2:{SC["CostsActionSlot"]}{LAST_ROW}=TRUE)*'
        f'(Calc!C2:C{LAST_ROW}=TRUE)*Calc!R2:R{LAST_ROW}*Skills!{SC["ActionsPerCast"]}2:{SC["ActionsPerCast"]}{LAST_ROW})/{IB("fight_duration")},'
        f'SUMPRODUCT((Skills!{SC["CostsActionSlot"]}2:{SC["CostsActionSlot"]}{LAST_ROW}=TRUE)*'
        f'(Calc!C2:C{LAST_ROW}=TRUE)*Calc!Q2:Q{LAST_ROW}*Skills!{SC["ActionsPerCast"]}2:{SC["ActionsPerCast"]}{LAST_ROW}))'
    ))

    ws.cell(row=R_BAPS, column=1, value="Cruel Stab (Basic Attack) Casts Per Second")
    ws.cell(row=R_BAPS, column=2, value=f'=MAX(0,B{R_APS}-B{R_CASTRATE})')

    ws.cell(row=R_CRIT_DAMAGE_BONUS, column=1, value="Global Critical Damage Bonus % (Smokescreen Mastery Lv.113, duty-cycle-averaged)")
    ws.cell(row=R_CRIT_DAMAGE_BONUS, column=2, value=f'=IF({IB("level")}>=113,30,0)*{buff_uptime(r_ss)}')

    ws.cell(row=R_MESO_STACK_AVG, column=1, value="Meso Explosion — average stack count at cast time (steady-state)")
    ws.cell(row=R_MESO_STACK_AVG, column=2, value=f'=MIN(10,0.5*B{R_APS}*{S("Cooldown(s)", r_me)})')

    ws.cell(row=R_BLOOD_MONEY_STACK_AVG, column=1, value="Blood Money — average stack count at cast time (steady-state)")
    ws.cell(row=R_BLOOD_MONEY_STACK_AVG, column=2, value=f'=MIN(5,0.25*B{R_APS}*{S("Cooldown(s)", r_me)})')

    ws.cell(row=R_MURDEROUS_INTENT_MULT, column=1, value="Assassinate Murderous Intent Multiplier (Mastery Lv.108, steady-state average)")
    ws.cell(row=R_MURDEROUS_INTENT_MULT, column=2, value=(
        f'=1+IFERROR(MIN(1,(Calc!C{r_bm}=TRUE)*Calc!Q{r_bm}*2/Calc!Q{r_asn}),0)'
    ))

    ws.cell(row=R_TOTAL, column=1, value="TOTAL DPS").font = Font(bold=True, size=13)
    ws.cell(row=R_TOTAL, column=2, value=f"=SUM(Calc!O2:O{LAST_ROW})").font = Font(bold=True, size=13)

    ws.cell(row=R_CRUEL_STAB_DPS, column=1, value="Cruel Stab (Basic Attack) DPS")
    ws.cell(row=R_CRUEL_STAB_DPS, column=2, value=f"=Calc!O{ROW['CRUEL_STAB']}")

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

    ws.column_dimensions["A"].width = 65
    ws.column_dimensions["B"].width = 16
    ws.column_dimensions["C"].width = 12
    return ws


# ---------------------------------------------------------------------------
# Sensitivity sheet: marginal DPS from bumping each Inputs stat by +1 — mirrors Night Lord's own
# STAT_SWEEP/PASSIVE_DELTA_SLOT/build_stat_block pattern (LUK main / DEX sub identity, plus the
# incoming_hit_rate sweep for Shadow Shifter).
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
        return f'=Sensitivity!H{SENSITIVITY_ROW_FOR["flat_luk"]}*{IB("level")}'
    if stat_name == "Main Stat % per 4 Levels":
        return f'=Sensitivity!H{SENSITIVITY_ROW_FOR["luk_pct"]}*INT({IB("level")}/4)'
    if stat_name == "Critical Rate %":
        return (
            f'=IF({IB("crit_rate")}>=100,Sensitivity!H{SENSITIVITY_ROW_FOR["crit_damage"]},'
            f'Sensitivity!H{SENSITIVITY_ROW_FOR["crit_rate"]})'
        )
    if stat_name == "Companion Summoning Time Increase %":
        return f'=Sensitivity!H{SENSITIVITY_ROW_FOR["crit_damage"]}'
    key = POTENTIAL_STAT_TO_SWEEP_KEY.get(stat_name)
    if key is None:
        return "0"
    return f"=Sensitivity!H{SENSITIVITY_ROW_FOR[key]}"


# Which Inputs-equivalent slot each "Magic Critical pattern" passive-mult row's Sensitivity-only
# delta folds into. "attack_mult" has no literal Inputs field (folded into avg_buff_mult
# multiplicatively instead) — Channel Karma and Shadow Shifter's self-Attack% both share it.
PASSIVE_DELTA_SLOT = {
    "AGILE_DAGGERS": "attack_speed",
    "CHANNEL_KARMA": "attack_mult",
    "DAGGER_MASTERY": "min_damage",
    "CRITICAL_EDGE_RATE": "crit_rate",
    "CRITICAL_EDGE_DMG": "crit_damage",
    "PHYSICAL_TRAINING": "basic_attack_damage",
    "DAGGER_EXPERT_SKILL": "skill_damage",
    "DAGGER_EXPERT_MAXDMG": "max_damage",
    "SHADOWER_INSTINCT": "final_damage",
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


BLOCK_HEIGHT = LAST_ROW + 18
BLOCK_START = SENSITIVITY_HEADER_ROW + len(STAT_SWEEP) + 3


def build_stat_block(ws, base_row, ib, stat_key, stat_label, override_expr):
    row_label = base_row
    row_header = base_row + 1
    calc_start = base_row + 2
    row_of = {key: calc_start + (r - 2) for key, r in ROW.items()}
    calc_end = calc_start + (LAST_ROW - 2)

    s_avgbuff = calc_end + 2
    s_crit_rate_bonus = calc_end + 3
    s_monster_dmg_bonus = calc_end + 4
    s_shadow_partner_mult = calc_end + 5
    s_as_bonus = calc_end + 6
    s_aps = calc_end + 7
    s_castrate = calc_end + 8
    s_baps = calc_end + 9
    s_crit_damage_bonus = calc_end + 10
    s_meso_stack = calc_end + 11
    s_bm_stack = calc_end + 12
    s_murderous = calc_end + 13
    s_total = calc_end + 15
    crit_rate_bonus_ref, monster_dmg_bonus_ref = f"B{s_crit_rate_bonus}", f"B{s_monster_dmg_bonus}"
    shadow_partner_mult_ref = f"B{s_shadow_partner_mult}"
    as_bonus_ref, aps_ref, castrate_ref, baps_ref = f"B{s_as_bonus}", f"B{s_aps}", f"B{s_castrate}", f"B{s_baps}"
    crit_damage_bonus_ref = f"B{s_crit_damage_bonus}"
    total_ref = f"B{s_total}"

    fda_block = fixed_duration_active_expr(ib("monster_type"), ib("fight_duration"))
    bdi_block = ib("buff_duration_increase_pct")

    def buff_uptime_block(local_row, skills_row):
        return uptime_fraction_or_exact_expr(
            fda_block, f'S{local_row}', ib("monster_type"), S("BuffDuration(s)", skills_row),
            S("Cooldown(s)", skills_row), bdi_block, ib("fight_duration"),
        )

    delta_by_slot = {}
    for row_key, slot in PASSIVE_DELTA_SLOT.items():
        term = f'((C{row_of[row_key]}=TRUE)*(F{row_of[row_key]}-Calc!F{ROW[row_key]}))'
        delta_by_slot[slot] = f'{delta_by_slot[slot]}+{term}' if slot in delta_by_slot else term
    delta = {slot: delta_by_slot.get(slot, "0") for slot in (
        "attack_speed", "basic_attack_damage", "min_damage", "max_damage", "crit_rate",
        "crit_damage", "boss_damage", "skill_damage", "final_damage", "attack_mult",
    )}

    r_dsa, r_id, r_ss = ROW["DARK_SIGHT_ATK"], ROW["INTO_DARKNESS"], ROW["SMOKESCREEN"]
    dark_sight_atk_avg = f'((C{row_of["DARK_SIGHT_ATK"]}=TRUE)*F{row_of["DARK_SIGHT_ATK"]}*{buff_uptime_block(row_of["DARK_SIGHT_ATK"], r_dsa)})'
    into_darkness_avg = f'((C{row_of["INTO_DARKNESS"]}=TRUE)*F{row_of["INTO_DARKNESS"]}*{buff_uptime_block(row_of["INTO_DARKNESS"], r_id)})'
    smokescreen_avg = f'((C{row_of["SMOKESCREEN"]}=TRUE)*F{row_of["SMOKESCREEN"]}*{buff_uptime_block(row_of["SMOKESCREEN"], r_ss)})'
    # ATTACK% bucket: every live skill/buff Attack% source sums with the delta-only Attack%
    # passives (Channel Karma, Shadow Shifter Self Atk) into ONE combined percentage before a
    # single multiplication — these are all the SAME bucket (skill/buff-sourced Attack%), distinct
    # from Inputs!attack_pct (gear Attack%), which stays its own separate multiplicative factor
    # elsewhere. Final Damage% (Into Darkness + Smokescreen) is a deliberate exception to this rule
    # — every Final Damage source stays its own multiplicative factor, so it is NOT folded into
    # this sum; it is combined as its own separate bucket below.
    attack_bucket_block = f'(1+({dark_sight_atk_avg}+{delta["attack_mult"]})/100)'
    final_damage_bucket_block = f'(1+{into_darkness_avg}/100)*(1+{smokescreen_avg}/100)'

    ws.cell(row=row_label, column=1, value=f"Stat: {stat_label}").font = LABEL_FONT
    for i, name in enumerate(CALC_HEADERS):
        ws.cell(row=row_header, column=i + 1, value=name)
    style_header_row(ws, row_header, len(CALC_HEADERS))

    mh_row_of = row_of["MAPLE_HERO_SHADOWER"]
    maple_hero_gated_block = f'IF(C{mh_row_of}=TRUE,F{mh_row_of},0)'

    basic_lvl_cell, basic_factor_cell, basic_coeff_cell = (
        f"U{row_header + 1}", f"U{row_header + 2}", f"U{row_header + 3}"
    )
    ws.cell(row=row_header, column=21, value="helpers")
    ws[basic_lvl_cell] = f'=MAX(0,({ib("level")}-100)*3)+{ib("skill_lvl_4th")}+{ib("skill_lvl_all")}'
    ws[basic_factor_cell] = (
        f'=INDEX(FactorTable!$B$2:$Y$301, MATCH(ROUND(MIN(300,MAX(1,{basic_lvl_cell})),0), '
        f'FactorTable!$A$2:$A$301,0), 22)'
    )
    ws[basic_coeff_cell] = f'=290*{basic_factor_cell}/1000'

    FULL_HIT_PIPELINE_KEYS = (
        ["CRUEL_STAB"] + DAMAGE_ROW_KEYS + TOXIC_VENOM_ROW_KEYS + SHADOW_SHIFTER_ROW_KEYS
        + MESO_EXPLOSION_ROW_KEYS + BLOOD_MONEY_ROW_KEYS + ASSASSINATE_ROW_KEYS
    )
    GENERIC_O_KEYS = DAMAGE_ROW_KEYS + MESO_EXPLOSION_ROW_KEYS + BLOOD_MONEY_ROW_KEYS + ASSASSINATE_ROW_KEYS

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

        if key == "CRUEL_STAB":
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
            if key == "ASSASSINATE":
                finisher_factor = (
                    f'INDEX(FactorTable!$B$2:$Y$301, MATCH(ROUND(MIN(300,MAX(1,D{row})),0), '
                    f'FactorTable!$A$2:$A$301,0), 13)'
                )
                finisher_pct = f'(30000/10)*({finisher_factor}/1000)'
                ws.cell(row=row, column=6, value=(
                    f"=({S('BaseDamage(tenths%)', r)}/10)*(E{row}/1000)+IF({ib('level')}>=134,50,0)"
                    f"+0.5*{finisher_pct}*B{s_murderous}"
                ))
            else:
                ws.cell(row=row, column=6, value=(
                    f'=IF({S("ScalesWithLevel", r)}=TRUE,({S("BaseDamage(tenths%)", r)}/10)*(E{row}/1000),'
                    f'{S("BaseDamage(tenths%)", r)}/10)+{S("SkillMasteryBonus%", r)}'
                ))

        ws.cell(row=row, column=7, value=(
            f'={S("HitsPerCast", r)}*IF({S("ICD(s)", r)}>0,{S("ActiveWindow(s)", r)}/{S("ICD(s)", r)},1)'
        ))
        ws.cell(row=row, column=8, value=f'=1-(1-{S("ProcChance%", r)}/100)^{S("RollsPerCast", r)}')
        ws.cell(row=row, column=9, value="1")

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
            maple_ratio = MAPLE_HERO_SHADOWER_RATIOS.get(key)
            maple_term = f'*(1+{maple_ratio}*{maple_hero_gated_block}/100)' if maple_ratio else ''
            ws.cell(row=row, column=11, value=(
                f'=J{row}*(1+{ib("stat_damage")}/100)*(1+{ib("damage")}/100)'
                f'*(1+{monster_dmg_term}/100)'
                f'*(1+{ib("damage_amp")}/100)'
                f'*(5000/(6000+{ib("monster_defense")}*(1-{ib("def_pen")}/100)))'
                f'*(1+({ib("final_damage")}+{delta["final_damage"]})/100)'
                f'{maple_term}'
                f'*(1+(IF({S("Key", r)}="CRUEL_STAB",{ib("basic_attack_damage")}+{delta["basic_attack_damage"]},'
                f'{ib("skill_damage")}+{delta["skill_damage"]}))/100)'
                f'*({avgbuff_with_deltas}*{shadow_partner_mult_ref}*I{row})'
            ))
            ws.cell(row=row, column=12, value=(
                f'=K{row}*(MIN({ib("min_damage")}+{delta["min_damage"]},{ib("max_damage")}+{delta["max_damage"]})/100'
                f'+({ib("max_damage")}+{delta["max_damage"]})/100)/2'
            ))
            ws.cell(row=row, column=13, value=f'=L{row}*(1+({ib("crit_damage")}+{delta["crit_damage"]}+{crit_damage_bonus_ref})/100)')
            ws.cell(row=row, column=14, value=(
                f'=L{row}*(1-MIN({crit_rate_total_block},100)/100)+M{row}*(MIN({crit_rate_total_block},100)/100)'
            ))
        else:
            for col in (10, 11, 12, 13, 14):
                ws.cell(row=row, column=col, value="")

        if key == "CRUEL_STAB":
            cruel_stab_targets_expr = f'(6+{ib("basic_attack_target_increase")})'
            ws.cell(row=row, column=15, value=(
                f"=IF(C{row},{S('HitsPerCast', r)}*N{row}*{baps_ref}*"
                f"{target_multiplier_expr(ib('monster_type'), ib('normal_weight_frac'), cruel_stab_targets_expr, ib('max_enemies_hit'))},0)"
            ))
        elif key in TOXIC_VENOM_ROW_KEYS:
            total_hit_rate = (
                f'SUMPRODUCT((Skills!{SC["TriggersToxicVenom"]}2:{SC["TriggersToxicVenom"]}{LAST_ROW}=TRUE)*'
                f'(C{calc_start}:C{calc_end}=TRUE)*S{calc_start}:S{calc_end})'
            )
            ws.cell(row=row, column=15, value=f'=IF(C{row},0.2*{total_hit_rate}*N{row},0)')
        elif key in SHADOW_SHIFTER_ROW_KEYS:
            ws.cell(row=row, column=15, value=f'=IF(C{row},{ib("incoming_hit_rate")}*0.2*N{row},0)')
        elif key in MESO_EXPLOSION_ROW_KEYS:
            stack_expr = f'MIN(10,0.5*{aps_ref}*{S("Cooldown(s)", r)})'
            ws.cell(row=row, column=15, value=(
                f'=IF(C{row},H{row}*N{row}*{rate_row}*'
                f"{target_multiplier_expr(ib('monster_type'), ib('normal_weight_frac'), stack_expr, ib('max_enemies_hit'))},0)"
            ))
        elif key in BLOOD_MONEY_ROW_KEYS:
            stack_expr = (
                f'MIN(5,0.25*{aps_ref}*{S("Cooldown(s)", ROW["MESO_EXPLOSION"])})'
                f'*{S("MasteryTargetIncrease", r)}'
            )
            ws.cell(row=row, column=15, value=(
                f'=IF(C{row},H{row}*N{row}*{rate_row}*'
                f"{target_multiplier_expr(ib('monster_type'), ib('normal_weight_frac'), stack_expr, ib('max_enemies_hit'))},0)"
            ))
        elif key in GENERIC_O_KEYS:
            ws.cell(row=row, column=15, value=(
                f'=IF(C{row},H{row}*N{row}*{rate_row}*'
                f"{target_multiplier_expr(ib('monster_type'), ib('normal_weight_frac'), S('NormalMonsterTargets', r), ib('max_enemies_hit'))},0)"
            ))
        else:
            ws.cell(row=row, column=15, value=0)

        ws.cell(row=row, column=16, value=f'=IF({total_ref}=0,0,O{row}/{total_ref})')
        ws.cell(row=row, column=17, value=(f'=IFERROR(1/{eff_cd_row},0)' if has_cooldown else 0))
        if has_cooldown:
            ws.cell(row=row, column=18, value=(
                f'=IF({fda_block},{exact_casts_expr(ib("fight_duration"), eff_cd_row)},0)'
            ))
        else:
            ws.cell(row=row, column=18, value=0)
        if key in TOXIC_VENOM_ROW_KEYS:
            ws.cell(row=row, column=19, value=0)
        else:
            ws.cell(row=row, column=19, value=f'=IFERROR(O{row}/N{row},0)')

    r_dsc = ROW["DARK_SIGHT_CRIT"]
    r_nf, r_steal = ROW["NIMBLE_FEET"], ROW["STEAL"]
    r_sp = ROW["SHADOW_PARTNER"]

    dark_sight_crit_avg = f'((C{row_of["DARK_SIGHT_CRIT"]}=TRUE)*F{row_of["DARK_SIGHT_CRIT"]}*{buff_uptime_block(row_of["DARK_SIGHT_CRIT"], r_dsc)})'
    nimble_feet_avg = f'((C{row_of["NIMBLE_FEET"]}=TRUE)*F{row_of["NIMBLE_FEET"]}*{buff_uptime_block(row_of["NIMBLE_FEET"], r_nf)})'
    steal_avg = f'((C{row_of["STEAL"]}=TRUE)*F{row_of["STEAL"]}*3)'

    attack_speed_with_delta = f'({ib("attack_speed")}+{delta["attack_speed"]})'

    ws.cell(row=s_avgbuff, column=1, value="Average Buff Multiplier")
    ws.cell(row=s_avgbuff, column=2, value=f'={attack_bucket_block}*{final_damage_bucket_block}')

    ws.cell(row=s_crit_rate_bonus, column=1, value="Global Crit Rate Bonus %")
    ws.cell(row=s_crit_rate_bonus, column=2, value=f'={dark_sight_crit_avg}')

    ws.cell(row=s_monster_dmg_bonus, column=1, value="Global Monster Damage-Taken Bonus %")
    ws.cell(row=s_monster_dmg_bonus, column=2, value=f'=IF({ib("level")}>=82,15,0)')

    sp_maple_ratio = MAPLE_HERO_SHADOWER_RATIOS["SHADOW_PARTNER"]
    sp_maple_term_block = f'*(1+{sp_maple_ratio}*{maple_hero_gated_block}/100)'
    ws.cell(row=s_shadow_partner_mult, column=1, value="Shadow Partner Average Multiplier")
    ws.cell(row=s_shadow_partner_mult, column=2, value=(
        f'=1+((C{row_of["SHADOW_PARTNER"]}=TRUE)*F{row_of["SHADOW_PARTNER"]}{sp_maple_term_block}'
        f'*I{row_of["SHADOW_PARTNER"]}*{S("ProcChance%", r_sp)}/100)/100'
    ))

    ws.cell(row=s_as_bonus, column=1, value="Attack Speed Buff Bonus %")
    ws.cell(row=s_as_bonus, column=2, value=f'={nimble_feet_avg}+{steal_avg}')

    ws.cell(row=s_aps, column=1, value="Actions Per Second")
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

    ws.cell(row=s_baps, column=1, value="Cruel Stab Casts Per Second")
    ws.cell(row=s_baps, column=2, value=f'=MAX(0,{aps_ref}-{castrate_ref})')

    ws.cell(row=s_crit_damage_bonus, column=1, value="Global Critical Damage Bonus % (Smokescreen Mastery Lv.113)")
    ws.cell(row=s_crit_damage_bonus, column=2, value=(
        f'=IF({ib("level")}>=113,30,0)*{buff_uptime_block(row_of["SMOKESCREEN"], r_ss)}'
    ))

    r_me, r_bm, r_asn = ROW["MESO_EXPLOSION"], ROW["BLOOD_MONEY"], ROW["ASSASSINATE"]
    ws.cell(row=s_meso_stack, column=1, value="Meso Explosion average stack count")
    ws.cell(row=s_meso_stack, column=2, value=f'=MIN(10,0.5*{aps_ref}*{S("Cooldown(s)", r_me)})')

    ws.cell(row=s_bm_stack, column=1, value="Blood Money average stack count")
    ws.cell(row=s_bm_stack, column=2, value=f'=MIN(5,0.25*{aps_ref}*{S("Cooldown(s)", r_me)})')

    ws.cell(row=s_murderous, column=1, value="Assassinate Murderous Intent Multiplier")
    ws.cell(row=s_murderous, column=2, value=(
        f'=1+IFERROR(MIN(1,Q{row_of["BLOOD_MONEY"]}*2/Q{row_of["ASSASSINATE"]}),0)'
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
        "(new = (1-(1-old/factor)*(1-1/factor))*factor), not a flat add."
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
    """Raw data for the PotentialCubes sheet — verbatim structure from
    build_fp_mage_workbook.py's own build_cube_data_sheet (class-agnostic in shape). Not meant
    for manual editing."""
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


CUBE_DATA_STAT_TABLE_LAST_ROW = 2 + len(ALL_POTENTIAL_STATS)
CUBE_DATA_SLOT_LIST_LAST_ROW = 1 + len(CUBE_SLOTS)


def dps_per_unit_lookup(stat_cell_ref):
    return (
        f'INDEX(CubeData!$K$2:$K${CUBE_DATA_STAT_TABLE_LAST_ROW},'
        f'MATCH({stat_cell_ref},CubeData!$J$2:$J${CUBE_DATA_STAT_TABLE_LAST_ROW},0))'
    )


CUBE_MILESTONES = [
    5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 60, 70, 80, 90, 100,
    125, 150, 175, 200, 250, 300, 400, 500, 1000,
]

POTENTIAL_CUBES_HEADER_ROW = 5
POTENTIAL_CUBES_FIRST_DATA_ROW = POTENTIAL_CUBES_HEADER_ROW + 1
POTENTIAL_TYPES = ("Potential", "Bonus Potential")
POTENTIAL_CUBES_LAST_DATA_ROW = POTENTIAL_CUBES_HEADER_ROW + len(CUBE_SLOTS) * len(POTENTIAL_TYPES)


def build_potential_cubes_sheet(wb, existing=None):
    existing = existing or {}
    ws = wb.create_sheet("PotentialCubes")
    ws["A1"] = "Potential Cubes — Current Gear State"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = (
        "Fill in your actual current gear for every slot/potential-type you want EV results for, "
        "then run `python3 tools/potential_cubes_ev.py` — it reads this table plus the live "
        "CubeData sheet and computes exact 'expected value of the best roll kept after N "
        "rerolls' for all 30 rows (printed + written to a CSV), via a full line1 x line2 x "
        "line3 enumeration per rarity/slot rather than a single-roll average."
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
    """If a previous Shadower-DPS-Calculator.xlsx already exists at `path`, read back its
    Inputs values and PotentialCubes current-gear table so regenerating the workbook doesn't
    clobber the user's real character stats and gear state with the hardcoded defaults."""
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
            # means this row held something else before a layout change (e.g. the old "Computed"
            # block's row numbers got reused for different keys); skip it rather than carry over
            # stale data from the wrong cell.
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


