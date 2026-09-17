#!/usr/bin/env python3
"""
Generates Ice-Lightning-Mage-DPS-Calculator.xlsx: a live-formula Excel replica of an Ice/Lightning
Arch Mage skill-rotation DPS model, sibling to build_fp_mage_workbook.py /
build_night_lord_workbook.py (see /Users/yaniv/.claude/plans/vectorized-shimmying-pony.md and
/tmp/ilm_authoritative_corrections.txt this was built from). Ice/Lightning Mage is INT main
stat / LUK sub stat — identical stat identity to FP-Mage (no Inputs rename needed).

Sheets: Inputs, FactorTable, Skills, Calc, Summary, Sensitivity, CubeData, PotentialCubes.

Key mechanics specific to this kit (see the plan for full derivation/justification):
  - Chain Lightning (basic attack) requires level 100, same "Unlocked-Gate Bypass" lesson learned
    from Night Lord's build — its own Calc!O DPS dispatch is gated on Calc!C, not unconditional.
  - Thunder Sphere has a skill-intrinsic (unconditional, not mastery-gated) +150% Normal Monster
    Damage baked into MasteryNormalDamage%, with Mastery Lv.94 adding +100%p on top of that base.
  - Frozen Orb halves its own damage vs a single (boss) target — a per-row target-count-
    conditional multiplier folded into its own Calc!O formula only.
  - Infinity's ramp-average: the wiki's displayed "+1%/sec, stacks x10" increment turns out to be
    exactly BaseFinalDamage%/15 (verified by reverse-engineering — not an independently-scaled
    curve), so the time-averaged total (base + increment*6.3333) collapses to base*64/45, no
    second FactorTable lookup needed.
  - Frozen Break / Frost Clutch: assumed permanently at 5 Frost stacks (steady-state, matches
    FP-Mage's Ignite/Elemental Drain precedent) — implemented as flat, level-gated additive
    Damage% terms directly in Summary (no dedicated Skills row), feeding a new R_DAMAGE_BONUS slot.
  - Elemental Reset: modeled always-on (100% uptime), same precedent as FP-Mage's own Elemental
    Decrease — chance/duration fields are documentation-only.
  - Freezing Breath's Mastery Lv.118 "Weaken" (+15% Damage Taken, 30s) is a duty-cycle-averaged
    global monster-damage-taken bonus (R_MONSTER_DMG_BONUS), mirroring Night Lord's Venom Lv.82/
    Frailty Curse Debuff precedent.
  - Blizzard's Mastery Lv.113 "Final Attack" is its own standalone proc row (mirrors FP-Mage's
    METEOR_PROC row exactly), but procs ONLY off Blizzard's own casts (simpler than FP-Mage's
    multi-skill-triggered Meteor Proc) — modeled as a normal DAMAGE_ROW_KEYS row sharing Blizzard's
    own live Cooldown(s) cell, with RollsPerCast=3 (Blizzard's own HitsPerCast) capturing "at least
    one of Blizzard's 3 hits procs, ICD caps it at one proc per cast".
  - MP Eater's Mastery Lv.49 "MP Boost" (+7% Attack Speed, MP condition ignored per user decision)
    is a real, always-on Attack Speed contributor (NOT baked into Inputs) that folds into the same
    diminishing-returns AS stack Nimble Feet feeds.
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
OUT_PATH = REPO / "Ice-Lightning-Mage" / "Ice-Lightning-Mage-DPS-Calculator.xlsx"

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
# Load the real factor table straight from the TS source (avoid re-typing it) — reused verbatim
# from build_fp_mage_workbook.py (plan §1).
# ---------------------------------------------------------------------------
def load_factor_table():
    data = json.loads(FACTOR_TABLE_JSON.read_text())
    return {int(k): v for k, v in data.items()}


FACTOR_TABLE = load_factor_table()
assert len(FACTOR_TABLE) == 300 and len(FACTOR_TABLE[1]) == 24


# ---------------------------------------------------------------------------
# Load the real potential-cube data straight from the (unused) TS web app — verbatim reuse of
# build_fp_mage_workbook.py's own loader (equipment potentials aren't class-specific).
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
# Inputs sheet row map — identical to build_fp_mage_workbook.py's own (INT main / LUK sub, no
# rename needed per the plan).
# ---------------------------------------------------------------------------
DERIVED_HEADER_ROW = 45
D_ATTACK = 46
D_STAT_DAMAGE = 47
D_BASIC_INPUT_LEVEL = 48
D_BASIC_FACTOR = 49
D_SKILL_COEFFICIENT = 50
D_NORMAL_WEIGHT_FRAC = 51
DERIVED_ROW = {
    "attack": D_ATTACK,
    "stat_damage": D_STAT_DAMAGE,
    "basic_input_level": D_BASIC_INPUT_LEVEL,
    "basic_factor": D_BASIC_FACTOR,
    "skill_coefficient": D_SKILL_COEFFICIENT,
    "normal_weight_frac": D_NORMAL_WEIGHT_FRAC,
}

CONTENT_TYPES = [
    "Chapter Boss", "Breakthrough", "PvP", "EXP Dungeon", "Equipment Dungeon",
    "Weapon Dungeon", "Enhancement Dungeon", "Hero Dungeon", "World Boss", "Chapter Hunt",
]

BOSS_NORMAL_WEIGHT_CHOICES = [
    "More Normal", "A Little More Normal", "Equal", "A Little More Boss", "More Boss",
]

IN = {
    "level": 3,
    "content_type": 4,
    "chapter_stage": 5,
    "flat_attack": 6,
    "attack_pct": 7,
    "defense": 8,
    "crit_rate": 9,
    "crit_damage": 10,
    "attack_speed": 11,
    "flat_int": 12,
    "int_pct": 13,
    "luk": 14,
    "damage": 15,
    "damage_amp": 16,
    "basic_attack_damage": 17,
    "skill_damage": 18,
    "def_pen": 19,
    "boss_damage": 20,
    "normal_damage": 21,
    "min_damage": 22,
    "max_damage": 23,
    "final_damage": 24,
    "skill_lvl_1st": 25,
    "skill_lvl_2nd": 26,
    "skill_lvl_3rd": 27,
    "skill_lvl_4th": 28,
    "skill_lvl_all": 29,
    "skill_cooldown_decrease": 32,
    "basic_attack_target_increase": 33,
    "buff_duration_increase_pct": 34,
    "companion_summon_time_increase_pct": 35,
    "boss_normal_weight_choice": 36,
    "max_enemies_hit": 37,
    "monster_type": 38,
    "chapter": 39,
    "stage": 40,
    "breakthrough_stage_index": 41,
    "monster_defense": 42,
    "fight_duration": 43,
    "breakthrough_normal_weight_pct": 44,
}

# Rows computed by formula on the Inputs sheet itself (not user-editable) — see
# build_inputs_sheet's "Computed (do not edit)" block below.
COMPUTED_INPUT_ROWS = {
    IN["monster_type"], IN["chapter"], IN["stage"], IN["breakthrough_normal_weight_pct"],
    IN["breakthrough_stage_index"], IN["monster_defense"], IN["fight_duration"],
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
    ws["A1"] = "Arch Mage (Ice/Lightning) — DPS Calculator: How to Use This Workbook"
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
        "Freezing Breath's Weaken debuff and Elemental Reset's own Damage Taken bonus assume "
        "the target is permanently afflicted at steady state, not an exact on/off timer.",
        "Crit Rate pushed above 100% (e.g. by cube potential lines) automatically redirects "
        "its stat-value to Crit Damage's own per-unit DPS value on the PotentialCubes sheet, "
        "since excess Crit Rate cannot do anything past 100%.",
        "Buffs (Magic Guard, Meditation, Infinity) are modeled at steady-state duty-cycle "
        "average uptime, not as an exact moment-to-moment state machine.",
        "Content Type (Inputs) picks what you're fighting — Chapter Boss/Breakthrough/PvP/EXP "
        "Dungeon/Equipment Dungeon/Weapon Dungeon/Enhancement Dungeon/Hero Dungeon/World Boss/"
        "Chapter Hunt — and Monster Defense and Fixed Fight Duration are both auto-computed from "
        "it (plus Chapter/Stage for the chapter- and dungeon-based types); PvP still forces its "
        "own fixed 15-second window and uses your own Defense stat as the opponent's Defense "
        "estimate. See README.md's 'Content Type' section for the exact formulas.",
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
    ws["A1"] = "Arch Mage (Ice/Lightning) — DPS Calculator Inputs"
    ws["A1"].font = Font(bold=True, size=14)

    rows = [
        ("level", "Character Level", 200),
        ("content_type", "Content Type", "Chapter Boss"),
        ("chapter_stage", "Chapter-Stage — e.g. '28-9' for Chapter Boss/Breakthrough/Chapter Hunt "
                          "(chapter-substage, the boss chapter number alone also works), or just the "
                          "stage number (e.g. '80') for Weapon/Enhancement/EXP/Equipment/Hero Dungeon", "28-9"),
        ("flat_attack", "Flat ATTACK", 10000),
        ("attack_pct", "ATTACK %", 0),
        ("defense", "Defense (your own DEF stat; PvP assumes the opponent has the same Defense as you)", 0),
        ("crit_rate", "CRIT_RATE %", 0),
        ("crit_damage", "CRIT_DAMAGE %", 0),
        ("attack_speed", "ATTACK_SPEED % (base, excludes Nimble Feet/MP Eater)", 0),
        ("flat_int", "Flat INT", 0),
        ("int_pct", "INT %", 0),
        ("luk", "LUK", 0),
        ("damage", "DAMAGE %", 0),
        ("damage_amp", "DAMAGE_AMP %", 0),
        ("basic_attack_damage", "BASIC_ATTACK_DAMAGE %", 0),
        ("skill_damage", "SKILL_DAMAGE %", 0),
        ("def_pen", "DEF_PEN %", 0),
        ("boss_damage", "BOSS_DAMAGE %", 0),
        ("normal_damage", "NORMAL_DAMAGE %", 0),
        ("min_damage", "MIN_DAMAGE %", 100),
        ("max_damage", "MAX_DAMAGE %", 100),
        ("final_damage", "FINAL_DAMAGE % (base, excludes Infinity)", 0),
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

    ws.cell(row=31, column=1, value="Additional Bonuses").font = SECTION_FONT
    bonus_rows = [
        ("skill_cooldown_decrease", "Skill Cooldown Decrease (seconds, only skills/buffs the character actively casts)", 0),
        ("basic_attack_target_increase", "Basic Attack Target Increase (flat, adds to the 6-target normal-monster base)", 1),
        ("buff_duration_increase_pct", "Buff Duration Increase %", 0),
        ("companion_summon_time_increase_pct", "Companion Summoning Time Increase % (companions not modeled — always 0 DPS impact)", 0),
        ("boss_normal_weight_choice", "Boss/Normal Emphasis (used when Content Type is Breakthrough or Hero Dungeon)", "A Little More Normal"),
        ("max_enemies_hit", "Max Enemies Actually In Range (normal monsters only; default 999 = uncapped)", 999),
    ]
    for key, label, default in bonus_rows:
        r = IN[key]
        ws.cell(row=r, column=1, value=label).font = LABEL_FONT
        cell = ws.cell(row=r, column=2, value=existing.get(key, default))
        cell.fill = INPUT_FILL

    dv_content_type = DataValidation(
        type="list", formula1='"' + ",".join(CONTENT_TYPES) + '"', allow_blank=False
    )
    ws.add_data_validation(dv_content_type)
    dv_content_type.add(ws.cell(row=IN["content_type"], column=2))

    dv_boss_normal_weight = DataValidation(
        type="list", formula1='"' + ",".join(BOSS_NORMAL_WEIGHT_CHOICES) + '"', allow_blank=False
    )
    ws.add_data_validation(dv_boss_normal_weight)
    dv_boss_normal_weight.add(ws.cell(row=IN["boss_normal_weight_choice"], column=2))

    COMPUTED_FILL = PatternFill("solid", fgColor="D9D9D9")
    computed_rows = [
        ("monster_type", "Monster Type (auto-computed from Content Type)", (
            f'=IF({IB("content_type")}="PvP","pvp",'
            f'IF(OR({IB("content_type")}="Breakthrough",{IB("content_type")}="Hero Dungeon"),"breakthrough",'
            f'IF(OR({IB("content_type")}="EXP Dungeon",{IB("content_type")}="Equipment Dungeon",{IB("content_type")}="Chapter Hunt"),"normal",'
            f'"boss")))'
        )),
        ("chapter", "Chapter (parsed from Chapter-Stage)", (
            f'=IFERROR(IF(ISNUMBER(FIND("-",{IB("chapter_stage")})),'
            f'VALUE(LEFT({IB("chapter_stage")},FIND("-",{IB("chapter_stage")})-1)),'
            f'VALUE({IB("chapter_stage")})),28)'
        )),
        ("stage", "Stage (parsed from Chapter-Stage)", (
            f'=IFERROR(IF(ISNUMBER(FIND("-",{IB("chapter_stage")})),'
            f'VALUE(MID({IB("chapter_stage")},FIND("-",{IB("chapter_stage")})+1,50)),'
            f'VALUE({IB("chapter_stage")})),9)'
        )),
        ("breakthrough_normal_weight_pct", "Boss/Normal Weight % (parsed from Boss/Normal Emphasis)", (
            f'=IF({IB("boss_normal_weight_choice")}="More Normal",70,'
            f'IF({IB("boss_normal_weight_choice")}="A Little More Normal",60,'
            f'IF({IB("boss_normal_weight_choice")}="Equal",50,'
            f'IF({IB("boss_normal_weight_choice")}="A Little More Boss",40,'
            f'IF({IB("boss_normal_weight_choice")}="More Boss",30,'
            f'60)))))'
        )),
        ("breakthrough_stage_index", "Breakthrough Global Stage Index (helper)", (
            f'=IF({IB("chapter")}=28,{IB("stage")}-9,'
            f'{IB("stage")}+14*MAX(0,MIN({IB("chapter")}-1,38)-28)+19*MAX(0,{IB("chapter")}-39))'
        )),
        ("monster_defense", "Monster Defense (auto-computed from Content Type)", (
            f'=IF({IB("content_type")}="Chapter Boss",3200+50*({IB("chapter")}-28),'
            f'IF({IB("content_type")}="World Boss",62100,'
            f'IF({IB("content_type")}="Weapon Dungeon",{IB("stage")}*50,'
            f'IF({IB("content_type")}="Enhancement Dungeon",950+{IB("stage")}*50,'
            f'IF(OR({IB("content_type")}="EXP Dungeon",{IB("content_type")}="Equipment Dungeon"),250+{IB("stage")}*50,'
            f'IF({IB("content_type")}="Hero Dungeon",650+{IB("stage")}*50,'
            f'IF(OR({IB("content_type")}="Breakthrough",{IB("content_type")}="Chapter Hunt"),4860+20*{IB("breakthrough_stage_index")},'
            f'{IB("defense")})))))))'
        )),
        ("fight_duration", "Fixed Fight Duration (auto-computed from Content Type; 0 = steady-state)", (
            f'=IF({IB("content_type")}="Chapter Hunt",0,'
            f'IF({IB("content_type")}="Weapon Dungeon",22,'
            f'IF({IB("content_type")}="Equipment Dungeon",40,'
            f'IF({IB("content_type")}="Enhancement Dungeon",25,'
            f'IF({IB("content_type")}="Hero Dungeon",50,'
            f'IF({IB("content_type")}="EXP Dungeon",40,'
            f'IF({IB("content_type")}="World Boss",75,'
            f'IF({IB("content_type")}="Chapter Boss",70,'
            f'IF({IB("content_type")}="Breakthrough",40,'
            f'0)))))))))'
        )),
    ]
    for key, label, formula in computed_rows:
        r = IN[key]
        ws.cell(row=r, column=1, value=f"{label} — computed, do not edit").font = LABEL_FONT
        cell = ws.cell(row=r, column=2, value=formula)
        cell.fill = COMPUTED_FILL
        ws.row_dimensions[r].hidden = True

    ws.column_dimensions["A"].width = 46
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


def level_gated_sum_raw(level_ref, pairs):
    """SUMPRODUCT(...) fragment WITHOUT the leading '=' — for embedding as a sub-expression
    inside another formula (e.g. Thunder Sphere's MasteryNormalDamage% = 150 + <this>)."""
    ordered = sorted(pairs.items())
    thresholds = ",".join(str(level) for level, _ in ordered)
    increments = ",".join(str(inc) for _, inc in ordered)
    return f'SUMPRODUCT(({level_ref}>={{{thresholds}}})*{{{increments}}})'


def level_gated_sum(level_ref, pairs):
    """Cumulative level-gated mastery bonus as a standalone cell formula (with leading '=')."""
    return f'={level_gated_sum_raw(level_ref, pairs)}'


def bdi_with_buff_mastery_expr(bdi_ref, level_ref, buff_mastery_f_ref):
    return f'({bdi_ref}+IF({level_ref}>=117,{buff_mastery_f_ref},0))'


# ---------------------------------------------------------------------------
# Skills sheet schema — a trimmed version of build_fp_mage_workbook.py's own SKILL_COLUMNS
# (this class is structurally closer to FP-Mage than Night Lord — same INT-main/LUK-sub stat
# identity, same shared skills: Magic Guard, Meditation, Element Amplification, Buff Mastery,
# Arcane Aim, the Magic-Critical-pattern passives). Dropped from FP-Mage's own layout: "Element"
# (no skill here needs element categorization — Frost Clutch's own element restriction was
# removed by the Aug-13 patch) and "TriggersElementalDecrease"/"TriggersMeteorProc"/
# "MeteorProcTriggersPerCast" (both vestigial-or-single-purpose in FP-Mage; Blizzard's own
# Lv.113 Final Attack proc procs only off Blizzard's own casts via a live Cooldown(s)
# cross-reference, so it needs none of that multi-skill-trigger-rate machinery).
# ---------------------------------------------------------------------------
SKILL_COLUMNS = [
    "Key", "Name", "JobStep", "Cooldown(s)", "CostsActionSlot",
    "HitsPerCast", "ICD(s)", "ActiveWindow(s)", "ProcChance%", "RollsPerCast",
    "BaseDamage(tenths%)", "FactorIndex", "ScalesWithLevel",
    "SkillMasteryBonus%", "MasteryBossDamage%", "MasteryNormalDamage%", "NormalMonsterTargets",
    "BuffTargetStat", "BuffDuration(s)", "MapleHeroBase(tenths%)", "MapleHeroFactorIndex",
    "Stacks", "Note",
]
SC = {name: get_column_letter(i + 1) for i, name in enumerate(SKILL_COLUMNS)}

# Row order (2..LAST_ROW) — derived from this list, never hand-numbered (per the project's own
# hardcoded-row-offset lesson).
ROW_ORDER = [
    "CHAIN_LIGHTNING", "MAGIC_GUARD", "MEDITATION", "THUNDER_BOLT", "GLACIER_WALL",
    "THUNDER_SPHERE", "FREEZING_BREATH", "BLIZZARD", "BLIZZARD_FINAL_ATTACK", "FROZEN_ORB",
    "ELQUINES", "MP_EATER_MP_BOOST", "ELEMENTAL_RESET", "ELEMENT_AMPLIFICATION", "INFINITY",
    "MAGIC_ACCELERATION", "SPELL_MASTERY", "HIGH_WISDOM", "MAGIC_CRITICAL_RATE",
    "MAGIC_CRITICAL_DAMAGE", "BUFF_MASTERY", "ARCANE_AIM",
]
ROW = {key: i for i, key in enumerate(ROW_ORDER, start=2)}
LAST_ROW = 1 + len(ROW_ORDER)

# Unlock level (character level) for every row, taken directly from each skill's own wiki page
# ("Level Required") or (for mastery-only rows) the mastery table — gated all the way down
# (unlike FP-Mage's own "only bothered gating the 102-138 batch" shortcut), matching Night
# Lord's more thorough approach, since the plan's verification sweep tests levels well below 100.
UNLOCK_LEVEL = {
    "CHAIN_LIGHTNING": 100,
    "MAGIC_GUARD": 15,
    "MEDITATION": 40,
    "THUNDER_BOLT": 38,
    "GLACIER_WALL": 63,
    "THUNDER_SPHERE": 69,
    "FREEZING_BREATH": 103,
    "BLIZZARD": 105,
    "BLIZZARD_FINAL_ATTACK": 113,
    "FROZEN_ORB": 107,
    "ELQUINES": 115,
    # Corrections file's "Decision #3" text says Lv.47, but the raw mastery-table extraction
    # (same file, full-table section) literally shows level 49 for this exact row ("MP Eater -
    # MP Boost") — 47 is the adjacent row's level (Cold Beam - Boss Monster Damage, an N/A
    # excluded skill). Using the raw table's literal value (49) as authoritative.
    "MP_EATER_MP_BOOST": 49,
    "ELEMENTAL_RESET": 72,
    "ELEMENT_AMPLIFICATION": 75,
    "INFINITY": 110,
    "MAGIC_ACCELERATION": 33,
    "SPELL_MASTERY": 43,
    "HIGH_WISDOM": 50,
    "MAGIC_CRITICAL_RATE": 74,
    "MAGIC_CRITICAL_DAMAGE": 74,
    "BUFF_MASTERY": 117,
    "ARCANE_AIM": 120,
}


def unlock_expr(key):
    level = UNLOCK_LEVEL.get(key)
    return "=TRUE" if level is None else f"={IB('level')}>={level}"


# Blizzard - Final Attack (Mastery Lv.113) procs only off Blizzard's own casts, not an external
# multi-skill trigger set (simpler than FP-Mage's Meteor Proc) — shares Blizzard's own live
# Cooldown(s) cell, same cross-reference pattern as Night Lord's SUDDEN_RAID_DOT mirroring
# SUDDEN_RAID_BURST's cooldown / FP-Mage's Mist Eruption mirroring Poison Mist (burst)'s.
_BLIZZARD_FINAL_ATTACK_COOLDOWN = f"=Skills!{SC['Cooldown(s)']}{ROW['BLIZZARD']}"

# (key, name, jobstep, cooldown, costsAction, hits, icd, window, chance, rolls,
#  baseDamage, factorIndex, scales, skillMasteryBonusPct, masteryBossDmgPct, masteryNormalDmgPct,
#  normalMonsterTargets, buffTarget, buffDuration, mapleBase, mapleFactor, stacks, note)
SKILL_ROWS = [
    ("CHAIN_LIGHTNING", "Chain Lightning", 4, "", False,
     f'=IF({IB("level")}>=136,6,5)', 0, 0, 100, 1,
     "", "", True,
     level_gated_sum(IB("level"), {102: 10, 106: 1, 116: 1, 120: 1, 128: 1, 132: 1}),
     level_gated_sum(IB("level"), {111: 10, 124: 10}),
     0,
     f'=6+{IB("basic_attack_target_increase")}', "", 0, "", "", "",
     "4th-job basic-attack effect (supersedes Energy Bolt/Cold Beam/Ice Strike, out of scope "
     "per the project's job-tier-is-gone convention). Wiki: 290%->522% (levels 1-200) to 6 "
     "target(s) 5 time(s) — factorIndex 21, baseDamage 2900 tenths%, matching "
     "Inputs!skill_coefficient (=290*basic_factor/1000) exactly, so this row's own coefficient "
     "is just that Inputs value + SkillMasteryBonus% (same mechanism as FP-Mage/Night Lord's "
     "own Basic Attack/Showdown rows). SkillMasteryBonus% is the 6-tier 'Chain Lightning - "
     "Damage' mastery chain (102/106/116/120/128/132), cumulative totals 10%->15% per the "
     "game's own tooltip convention, so level_gated_sum uses DELTA increments (10, then +1 "
     "five times). MasteryBossDamage% is the 2-tier 'Chain Lightning - Boss Monster Damage' "
     "chain (111/124), each independently +10%, totaling +20%. HitsPerCast 5->6 once the "
     "level-136 'Strike' mastery unlocks."),
    ("MAGIC_GUARD", "Magic Guard", 1,
     f'=IF({IB("level")}>=21,30*0.7,30)', True, 1, 0, 0, 100, 1,
     120, 21, True,
     0, 0, 0, 1, "ATTACK", 15,
     "", "", "",
     "Self-buff, +12%->16.8% Attack (levels 1-100), 15s duration/30s cooldown (Mastery Lv.21 "
     "'Magic Guard - Reuse' -30% cooldown -> 21s, baked directly into the Cooldown(s) formula). "
     "factorIndex 21, baseDamage 120 tenths%. Shared w/ FP-Mage."),
    ("MEDITATION", "Meditation", 2, 30, True, 1, 0, 0, 100, 1,
     200, 21, True,
     0, 0, 0, 1, "ATTACK",
     f'=IF({IB("level")}>=44,15*1.3,15)',
     "", "", "",
     "Self-buff, +20%->28% Attack (levels 1-100), 15s duration (Mastery Lv.44 'Meditation - "
     "Persistence' +30% duration -> 19.5s, baked directly into the BuffDuration(s) formula), "
     "30s cooldown. factorIndex 21, baseDamage 200 tenths%. Shared w/ FP-Mage."),
    ("THUNDER_BOLT", "Thunder Bolt", 2, 18, True, 3, 0, 0, 100, 1,
     1800, 12, True,
     level_gated_sum(IB("level"), {39: 70}),
     0, 0, 8, "", 0,
     1000, 23, "",
     "Wiki: 180%->270% (levels 1-100) to 8 target(s) 3 time(s), cooldown 18s. "
     "factorIndex 12, baseDamage 1800 tenths%. Mastery Lv.39 'Thunder Bolt - Damage' +70% "
     "(single-tier, real SkillMasteryBonus%). Maple Hero (Ice/Lightning) target: 100%->780% "
     "(levels 1-200), factorIndex 23, baseDamage 1000 tenths% (jointly reverse-engineered with "
     "Glacier Wall's and Thunder Sphere's own Maple Hero curves, confirmed same factorIndex)."),
    ("GLACIER_WALL", "Glacier Wall", 3,
     f'=IF({IB("level")}>=90,22*0.7,22)', True, 3, 0, 0, 100, 1,
     2900, 12, True,
     level_gated_sum(IB("level"), {68: 80}),
     0, 0, 8, "", 0,
     300, 23, "",
     "Wiki: 290%->580% (levels 1-200) to 8 target(s) 3 time(s), freezing them for 2s (freeze "
     "not modeled — no CC mechanic anywhere in this calculator), cooldown 22s. factorIndex 12, "
     "baseDamage 2900 tenths%. Mastery Lv.68 'Glacier Wall - Damage' +80% (real "
     "SkillMasteryBonus%), Lv.90 'Glacier Wall - Reuse' -30% cooldown -> 15.4s (baked into the "
     "Cooldown(s) formula). Maple Hero target: 30%->234% (levels 1-200), factorIndex 23, "
     "baseDamage 300 tenths%."),
    ("THUNDER_SPHERE", "Thunder Sphere", 3,
     f'=IF({IB("level")}>=78,30*0.7,30)', True, 3,
     f'=IF({IB("level")}>=104,2*0.7,2)', 10, 100, 1,
     1000, 12, True,
     level_gated_sum(IB("level"), {73: 50}),
     0,
     f'=150+{level_gated_sum_raw(IB("level"), {94: 100})}',
     6, "", 0,
     200, 23, "",
     "Wiki: 100%->200% (levels 1-200) to 6 target(s) 3 time(s) every 2s, for a 10s duration, "
     "cooldown 30s. factorIndex 12, baseDamage 1000 tenths%. Skill-intrinsic (unconditional, "
     "NOT mastery-gated) +150% Normal Monster Damage baked directly into this row's own "
     "MasteryNormalDamage% field, PLUS Mastery Lv.94's +100%p on top (so the field itself is "
     "'150 + level_gated_sum'). Mastery Lv.73 'Thunder Sphere - Damage' +50% (real "
     "SkillMasteryBonus%), Lv.78 'Thunder Sphere - Reuse' -30% cooldown -> 21s, Lv.104 "
     "'Thunder Sphere - Strike Interval' -30% tick interval (2s->1.4s, baked into the ICD(s) "
     "formula). Maple Hero target: 20%->200% (levels 1-200), factorIndex 23, baseDamage 200 "
     "tenths%."),
    ("FREEZING_BREATH", "Freezing Breath", 4, 40, True, 1, 0.5, 5, 100, 1,
     8000, 12, True,
     level_gated_sum(IB("level"), {108: 50}),
     0, 0, 10, "", 0,
     "", "", "",
     "Wiki: 800%->1600% (levels 1-200) to 10 target(s) every 0.5s for a 5s duration, cooldown "
     "45s (patched -> 40s, Aug 13 2026 patch note — the wiki page itself is stale). factorIndex "
     "12, baseDamage 8000 tenths%. EffectiveHits = 1*(5/0.5) = 10 ticks per cast. Mastery "
     "Lv.108 'Freezing Breath - Damage' +50% (real SkillMasteryBonus%). Mastery Lv.118 "
     "'Freezing Breath - Weaken' (+15% Damage Taken debuff, 30s) is NOT part of this row — it's "
     "a separate global Summary-sheet duty-cycle-averaged monster-damage bonus (see "
     "build_summary_sheet, mirrors Night Lord's Venom Lv.82/Frailty Curse Debuff precedent), "
     "added in a later build stage."),
    ("BLIZZARD", "Blizzard", 4, 33, True, 3, 0, 0, 100, 1,
     6000, 12, True,
     level_gated_sum(IB("level"), {130: 40}),
     0, 0, 7, "", 0,
     "", "", "",
     "Wiki: 600%->1200% (levels 1-200) to 5 target(s) 3 time(s) (patched targets 5->7, Aug 13 "
     "2026 patch note — the wiki page is stale), cooldown 33s. factorIndex 12, baseDamage 6000 "
     "tenths%. Mastery Lv.130 (corrected name/description pairing — wiki mismatch resolved via "
     "content-matching, see the plan) 'Blizzard - Damage' +40% flat (real SkillMasteryBonus%). "
     "Mastery Lv.113 'Blizzard - Final Attack' is its own separate proc row, see "
     "BLIZZARD_FINAL_ATTACK below, not part of this row's own fields."),
    ("BLIZZARD_FINAL_ATTACK", "Blizzard - Final Attack (Mastery Lv.113)", 4,
     _BLIZZARD_FINAL_ATTACK_COOLDOWN, False, 1, 0, 0, 30, 3,
     9500, 21, True,
     0, 0, 0, 1, "", 0,
     "", "", "",
     "Standalone proc row, mirrors FP-Mage's own METEOR_PROC row structure but simpler: procs "
     "only off Blizzard's own casts (per the wiki's own '[Blizzard in Slot] When attacking, "
     "deals...' phrasing — self-contained, not a multi-skill trigger set), so it shares "
     "Blizzard's own live Cooldown(s) cell directly instead of needing an external combined-"
     "cast-rate formula. Wiki formula ({#expr:750*(1+x*0.004)}%, patched base 750->950%, "
     "chance 20%->30%): reverse-engineered as factorIndex 21, baseDamage 9500 tenths% (950%, "
     "already the patched value). RollsPerCast=3 (Blizzard's own 3 hits, each an independent "
     "30% roll -> ProcProbability = 1-(1-0.3)^3 = 65.7% chance per Blizzard cast), ICD(s)=0 "
     "(already capped to at most one proc per Blizzard cast via HitsPerCast=1, no further ICD "
     "needed). Single-target (NormalMonsterTargets=1), matching FP-Mage's own Meteor Proc "
     "precedent for an 'additional damage on a hit' style proc, absent any wiki text "
     "specifying a target count of its own."),
    ("FROZEN_ORB", "Frozen Orb", 4, 23, True, 1,
     f'=IF({IB("level")}>=134,0.5*0.5,0.5)', 6, 100, 1,
     9000, 12, True,
     level_gated_sum(IB("level"), {122: 50}),
     0, 0, 10, "", 0,
     "", "", "",
     "Wiki: 900%->1800% (levels 1-200) to 10 target(s) every 0.5s for a 5s duration (patched -> "
     "6s, Aug 13 2026 patch note), cooldown 23s. factorIndex 12, baseDamage 9000 tenths%. "
     "'If there is 1 target near the orb, the damage is halved' — a single-target (boss) "
     "halving mechanic implemented ONLY in this row's own Calc!O (DPS) formula in a later build "
     "stage (x0.5 when monster_type=boss, x1 otherwise), not a Skills-sheet field. Mastery "
     "Lv.122 'Frozen Orb - Damage' +50% (real SkillMasteryBonus%), Lv.134 (corrected "
     "name/description pairing) 'Frozen Orb - Strike Interval' -50% tick interval (0.5s->0.25s, "
     "baked into the ICD(s) formula)."),
    ("ELQUINES", "Elquines", 4, 80, True, 1,
     f'=IF({IB("level")}>=126,4*0.8,4)', 30, 100, 1,
     35000, 12, True,
     level_gated_sum(IB("level"), {138: 50}),
     0, 0,
     f'=IF({IB("level")}>=138,6,3)', "", 0,
     "", "", "",
     "Summon, wiki: 3500%->7000% (levels 1-200) to 3 target(s) every 4s for a 30s duration, "
     "cooldown 80s. factorIndex 12, baseDamage 35000 tenths%. Mastery Lv.126 (corrected "
     "name/description pairing, user-confirmed 20% not the wiki's typo'd 0.2%) 'Elquines - "
     "Strike Interval' -20% attack interval (4s->3.2s, baked into the ICD(s) formula), Lv.138 "
     "'Elquines - Damage & Target' +50% damage (real SkillMasteryBonus%) AND +3 max targets "
     "(3->6, baked into the NormalMonsterTargets formula)."),
    ("MP_EATER_MP_BOOST", "MP Eater - MP Boost (Mastery Lv.49)", 2, "", False, 1, 0, 0, 100, 1,
     70, 0, False,
     0, 0, 0, 1, "", 0,
     "", "", "",
     "Mastery-only row (MP Eater's own base MP-recovery mechanic is not modeled — MP isn't "
     "tracked anywhere in this calculator). Flat +7% Attack Speed once unlocked (level 49, see "
     "UNLOCK_LEVEL's own note on the 47-vs-49 discrepancy), ignoring the MP>=50% condition per "
     "the user's always-on decision (same treatment as Element Amplification). This IS a real, "
     "always-on contributor (NOT baked into Inputs, unlike the Magic-Critical-pattern rows "
     "below) — folds into the Attack Speed diminishing-returns stack in Summary once unlocked, "
     "with no uptime averaging (it's a permanent passive, not a timed buff — BuffTargetStat "
     "deliberately left blank so the generic buff-uptime machinery doesn't try to average it; "
     "Summary reads this row's Calc!F and Calc!C directly instead). FactorIndex is an unused "
     "placeholder (ScalesWithLevel=False), same convention as Nimble Feet's own non-scaling row "
     "in FP-Mage/Night Lord."),
    ("ELEMENTAL_RESET", "Elemental Reset", 3, "", False, 1, 0, 0,
     f'=IF({IB("level")}>=82,50,25)', 1,
     120, 22, True,
     0, 0, 0, 1, "", 7,
     "", "", "",
     "User-confirmed: this is the patch note's 'Elemental Decrease' entry (patched base chance "
     "20%->25%, base Damage Taken 10%->12% — the wiki's own 10%->16% curve rescaled by the "
     "patch's 12/10=1.2x factor, giving the reverse-engineered factorIndex 22/baseDamage 120 "
     "used here, which already reflects the patched 12%->19.2% curve). Mastery Lv.82 'Elemental "
     "Reset - Chance' doubles the PATCHED chance (25%->50%, NOT the stale wiki 20%->40%). "
     "Modeled always-on (100% uptime), same precedent as FP-Mage's own Elemental Decrease — "
     "ProcChance%/BuffDuration(s) here are reference-only, they do not feed the Summary "
     "formula (which instead just adds Calc!F/100 as an unconditional multiplier)."),
    ("ELEMENT_AMPLIFICATION", "Element Amplification", 3, "", False, 1, 0, 0, 100, 1,
     150, 22, True,
     0, 0, 0, 1, "FINAL_DAMAGE", 0,
     "", "", "",
     "Wiki: +15%->24% Final Damage (levels 1-200), unconditional (ignore the MP>=50% condition "
     "and MP-cost increase per the user's decision, matching FP-Mage's own established "
     "treatment of this exact shared-kit passive). factorIndex 22, baseDamage 150 tenths%. Not "
     "reflected anywhere in Inputs — added directly into the Final Damage chain (multiplied "
     "in, same as Arcane Aim/Element Amplification are combined in FP-Mage) in a later build "
     "stage."),
    ("INFINITY", "Infinity", 4, 30, True, 1, 0, 0, 100, 1,
     150, 21, True,
     0, 0, 0, 1, "FINAL_DAMAGE", 15,
     "", "", "",
     "Wiki: base +15%->27% Final Damage for 15s, ADDITIONALLY +1%->1.8% per second, stacking up "
     "to 10 times (levels 1-200), cooldown 30s. Both curves reverse-engineered independently: "
     "base factorIndex 21/baseDamage 150 tenths%, increment factorIndex 21/baseDamage 10 "
     "tenths% — the increment is EXACTLY base/15 at every sampled level (zero residual error), "
     "confirming the ramp is a fixed fraction of the base, not an independently-scaled curve. "
     "Time-averaged stacks over the 15s window = (0+1+...+9+10*5)/15 = 6.3333, so the "
     "time-averaged total = base*(1+6.3333/15) = base*64/45 exactly. This row's own Calc!F "
     "needs a BESPOKE formula in build_calc_sheet (base_pct * 64/45, using the single "
     "factorIndex-21 lookup for 'base_pct') instead of the generic F-column formula every "
     "other row uses — flagged here so the Calc-sheet build stage doesn't miss it."),
    ("MAGIC_ACCELERATION", "Magic Acceleration", 2, "", False, 1, 0, 0, 100, 1,
     50, 22, True,
     0, 0, 0, 1, "ATTACK_SPEED", 0,
     "", "", "",
     "Permanent passive, +5%->6.5% Attack Speed (levels 1-100) — Magic Critical pattern, "
     "already baked into Inputs!ATTACK_SPEED%; this row only feeds the 2nd-Job Skill Level "
     "Bonus Sensitivity delta. factorIndex 22, baseDamage 50 tenths%."),
    ("SPELL_MASTERY", "Spell Mastery", 2, "", False, 1, 0, 0, 100, 1,
     150, 22, True,
     0, 0, 0, 1, "MIN_DAMAGE", 0,
     "", "", "",
     "Permanent passive, +15%->19.5% Min Damage Multiplier (levels 1-100) — Magic Critical "
     "pattern, already baked into Inputs!MIN_DAMAGE%; feeds the 2nd-Job Skill Level Bonus "
     "delta. factorIndex 22, baseDamage 150 tenths%."),
    ("HIGH_WISDOM", "High Wisdom", 2, "", False, 1, 0, 0, 100, 1,
     80, 22, True,
     0, 0, 0, 1, "CRIT_RATE", 0,
     "", "", "",
     "Permanent passive, +8%->10.4% Critical Rate (levels 1-100) — Magic Critical pattern, "
     "already baked into Inputs!CRIT_RATE% (jointly with Magic Critical (Crit Rate) below, "
     "both are separate skills contributing to the same Inputs field); feeds the 2nd-Job Skill "
     "Level Bonus delta. factorIndex 22, baseDamage 80 tenths%."),
    ("MAGIC_CRITICAL_RATE", "Magic Critical (Crit Rate)", 3, "", False, 1, 0, 0, 100, 1,
     80, 22, True,
     0, 0, 0, 1, "CRIT_RATE", 0,
     "", "", "",
     "Permanent passive, +8%->12.8% Critical Rate (levels 1-200) — Magic Critical pattern, "
     "already baked into Inputs!CRIT_RATE%; feeds the 3rd-Job Skill Level Bonus delta. "
     "factorIndex 22, baseDamage 80 tenths%."),
    ("MAGIC_CRITICAL_DAMAGE", "Magic Critical (Crit Damage)", 3, "", False, 1, 0, 0, 100, 1,
     120, 22, True,
     0, 0, 0, 1, "CRIT_DAMAGE", 0,
     "", "", "",
     "Same skill as Magic Critical (Crit Rate) above, +12%->19.2% Critical Damage (levels "
     "1-200) — Magic Critical pattern, already baked into Inputs!CRIT_DAMAGE%; feeds the "
     "3rd-Job Skill Level Bonus delta. factorIndex 22, baseDamage 120 tenths%."),
    ("BUFF_MASTERY", "Buff Mastery", 4, "", False, 1, 0, 0, 100, 1,
     100, 22, True,
     0, 0, 0, 1, "", 0,
     "", "", "",
     "Permanent passive (unlocked level 117), +10%->16% Buff Duration (levels 1-200) — not "
     "reflected anywhere in Inputs, so its current value (Calc!F) is added directly into every "
     "uptime_fraction_expr call's Buff Duration Increase % term (see "
     "bdi_with_buff_mastery_expr, already defined above). factorIndex 22, baseDamage 100 "
     "tenths%. Shared w/ FP-Mage."),
    ("ARCANE_AIM", "Arcane Aim", 4, "", False, 1, 0, 0, 100, 1,
     30, 22, True,
     0, 0, 0, 1, "", 0,
     "", "", "",
     "Permanent passive (unlocked level 120), 25% chance per attack for +3%->4.8% Final Damage "
     "(levels 1-200) for 10s, stacking up to 5 times — modeled as always at max 5 stacks (same "
     "always-on-proc-stack precedent as Elemental Reset/FP-Mage's own Arcane Aim). Combined "
     "MULTIPLICATIVELY into the Final Damage chain as (1+Calc!F/100)^5 in a later build stage. "
     "factorIndex 22, baseDamage 30 tenths%. Shared w/ FP-Mage."),
]

# Rows with a real Cooldown(s) value (literal or a live formula reference) — CastsInFight
# (fixed-duration mode) is only meaningful for these.
ROW_HAS_COOLDOWN = {row[0]: row[3] not in ("", None) for row in SKILL_ROWS}

# Blizzard - Final Attack shares Blizzard's own live Cooldown(s) cell (its RAW, un-CDR'd 33s
# literal), but its proc cadence should track how often Blizzard is ACTUALLY cast, which does
# get shortened by Skill Cooldown Decrease (Blizzard's own CostsActionSlot=True). Since this
# row's own CostsActionSlot is False, checking its own flag would silently never apply CDR here
# even when the player has real CDR invested — override to check Blizzard's own flag instead,
# the same cross-row-CDR-eligibility pattern as Night Lord's SUDDEN_RAID_DOT mirroring
# SUDDEN_RAID_BURST / FP-Mage's MIST_ERUPTION mirroring POISON_MIST_BURST.
CDR_COSTS_ACTION_ROW = {key: r for key, r in ROW.items()}
CDR_COSTS_ACTION_ROW["BLIZZARD_FINAL_ATTACK"] = ROW["BLIZZARD"]


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

    widths = [24, 34, 8, 11, 15, 13, 8, 15, 11, 12, 18, 11, 14, 17, 16, 18, 20, 16, 15,
              20, 20, 8, 60]
    for i, w in enumerate(widths):
        ws.column_dimensions[get_column_letter(i + 1)].width = w
    ws.freeze_panes = "A2"
    return ws


# ---------------------------------------------------------------------------
# Row categories consumed by build_calc_sheet/build_summary_sheet/build_sensitivity_sheet.
# ---------------------------------------------------------------------------
DAMAGE_ROW_KEYS = [
    "THUNDER_BOLT", "GLACIER_WALL", "THUNDER_SPHERE", "FREEZING_BREATH", "BLIZZARD",
    "BLIZZARD_FINAL_ATTACK", "FROZEN_ORB", "ELQUINES",
]
BUFF_ROW_KEYS = ["MAGIC_GUARD", "MEDITATION", "INFINITY"]
SPECIAL_ROW_KEYS = ["ELEMENTAL_RESET"]
# Every row that can ever post a nonzero Calc!O DPS value — used to filter the Summary sheet's
# per-skill breakdown table down to real damage sources (buffs/passives always show 0.0000 there).
DAMAGE_DEALING_KEYS = ["CHAIN_LIGHTNING"] + DAMAGE_ROW_KEYS

CALC_HEADERS = [
    "Key", "Name", "Unlocked", "InputLevel", "Factor", "CoefficientPercent",
    "EffectiveHits", "ProcProbability", "MapleHeroMultiplier",
    "BaseDamage", "BaseHitDamage", "NonCritAvg", "CritAvg", "ExpectedDamage(perHit)",
    "DPS", "% of Total",
]
CCOL = {name: get_column_letter(i + 1) for i, name in enumerate(CALC_HEADERS)}


def S(col_name, r):
    """Shorthand for a Skills-sheet cell reference by column name, e.g. S('Cooldown(s)', 9) -> 'Skills!D9'"""
    return f"Skills!{SC[col_name]}{r}"


# ---------------------------------------------------------------------------
# Summary-sheet row numbers, fixed here (not derived) since build_calc_sheet needs to embed
# live references to them before build_summary_sheet runs — kept in one place so the two
# functions can't silently drift apart (mirrors FP-Mage's own r_bm/r_ed_mult/... local-variable
# pattern, just promoted to module level so both functions can share it).
SUMMARY_ROW = {
    "AVG_BUFF_MULT": 53,
    "MONSTER_DMG_BONUS": 54,
    "DAMAGE_BONUS": 55,
    "AS_BONUS": 56,
    "APS": 57,
    "CAST_RATE": 58,
    "BASIC_ATTACKS_PER_SEC": 59,
    "TOTAL_DPS": 3,
    "BASIC_ATTACK_DPS": 60,
}


def build_calc_sheet(wb):
    ws = wb.create_sheet("Calc")
    for i, name in enumerate(CALC_HEADERS):
        ws.cell(row=1, column=i + 1, value=name)
    style_header_row(ws, 1, len(CALC_HEADERS))

    # Maple Hero helper cells (jobStep 4, factorIndex 23) — lives off to the side, reused by
    # every row's own MapleHeroMultiplier (column I) via the MapleHeroBase(tenths%)/
    # MapleHeroFactorIndex fields on the Skills sheet (Thunder Bolt/Glacier Wall/Thunder
    # Sphere only — every other row's MapleHeroBase is blank, making I{r}=1 for them).
    ws["Z1"] = "Maple Hero helper (jobStep4, factorIndex23)"
    ws["Z1"].font = LABEL_FONT
    ws["Z2"] = f'=MAX(0,({IB("level")}-100)*3)+{IB("skill_lvl_4th")}+{IB("skill_lvl_all")}'
    ws["Z3"] = f'=INDEX(FactorTable!$B$2:$Y$301, MATCH(ROUND(MIN(300,MAX(1,Z2)),0), FactorTable!$A$2:$A$301,0), 24)'

    fixed_duration_active_main = fixed_duration_active_expr(IB("monster_type"), IB("fight_duration"))

    ea_row = ROW["ELEMENT_AMPLIFICATION"]
    aa_row = ROW["ARCANE_AIM"]
    # Both gated in this build (unlike FP-Mage, which never gates either) — must check Unlocked
    # explicitly here or their contribution would leak below their own unlock levels (the exact
    # "Unlocked-Gate Bypass" bug class documented from Night Lord's build).
    elem_amp_gated = f'IF(C{ea_row}=TRUE,F{ea_row},0)'
    arcane_aim_gated = f'IF(C{aa_row}=TRUE,F{aa_row},0)'

    # Single-target (boss/pvp) halving — Frozen Orb only ("if there is 1 target near the orb,
    # the damage is halved"). A Chapter Breakthrough fight is itself a weighted blend of a
    # single (boss-like) target and multiple normal-monster targets (Inputs!normal_weight_frac)
    # — the halving should apply to that same boss-weighted portion, not be either fully on or
    # fully off, so this blends the 0.5/1.0 multiplier by the same weight every other per-target
    # effect in this workbook uses (monster_blend_expr's own pattern) rather than a binary IF.
    # PvP is 1v1, so it halves there too, same as pure boss.
    frozen_orb_single_target_mult = (
        f'IF({IB("monster_type")}="pvp",0.5,'
        f'(1-{IB("normal_weight_frac")})*0.5+{IB("normal_weight_frac")}*1)'
    )

    for key, r in ROW.items():
        ws.cell(row=r, column=1, value=f"={S('Key', r)}")
        ws.cell(row=r, column=2, value=f"={S('Name', r)}")
        ws.cell(row=r, column=3, value=unlock_expr(key))

        eff_cd_r = effective_cooldown_expr(
            IB("monster_type"), S("Cooldown(s)", r), IB("skill_cooldown_decrease"),
            S("CostsActionSlot", CDR_COSTS_ACTION_ROW[key]),
        )
        rate_r = rate_or_exact_hits_expr(
            fixed_duration_active_main, f"R{r}", S("HitsPerCast", r), S("ICD(s)", r),
            S("ActiveWindow(s)", r), eff_cd_r, IB("fight_duration"), f"G{r}*Q{r}",
        )

        if key == "CHAIN_LIGHTNING":
            # Basic-attack row — coefficient comes from Inputs!skill_coefficient (already
            # computed there from factorIndex 21/baseDamage 2900, the same values this row's
            # own BaseDamage(tenths%)/FactorIndex fields document but don't drive), plus this
            # row's own mastery chain.
            ws.cell(row=r, column=4, value="")
            ws.cell(row=r, column=5, value="")
            ws.cell(row=r, column=6, value=f"={IB('skill_coefficient')}+{S('SkillMasteryBonus%', r)}")
        else:
            ws.cell(
                row=r, column=4,
                value=(
                    f'=IF({S("JobStep", r)}=1,60+{IB("skill_lvl_1st")}+{IB("skill_lvl_all")},'
                    f'IF({S("JobStep", r)}=2,90+{IB("skill_lvl_2nd")}+{IB("skill_lvl_all")},'
                    f'IF({S("JobStep", r)}=3,120+{IB("skill_lvl_3rd")}+{IB("skill_lvl_all")},'
                    f'MAX(0,({IB("level")}-100)*3)+{IB("skill_lvl_4th")}+{IB("skill_lvl_all")})))'
                ),
            )
            ws.cell(
                row=r, column=5,
                value=(
                    f'=INDEX(FactorTable!$B$2:$Y$301, MATCH(ROUND(MIN(300,MAX(1,D{r})),0), '
                    f'FactorTable!$A$2:$A$301,0), {S("FactorIndex", r)}+1)'
                ),
            )
            if key == "INFINITY":
                # Base Final Damage% ramps +Base/15 per second up to 10 stacks over its 15s
                # duration; the increment is exactly Base/15 (reverse-engineered, zero residual
                # error), so the time-average collapses to Base*64/45 — see this row's own Note
                # on the Skills sheet for the derivation. No second FactorTable lookup needed.
                ws.cell(
                    row=r, column=6,
                    value=f"=({S('BaseDamage(tenths%)', r)}/10)*(E{r}/1000)*64/45+{S('SkillMasteryBonus%', r)}",
                )
            else:
                ws.cell(
                    row=r, column=6,
                    value=(
                        f'=IF({S("ScalesWithLevel", r)}=TRUE,({S("BaseDamage(tenths%)", r)}/10)*(E{r}/1000),'
                        f'{S("BaseDamage(tenths%)", r)}/10)+{S("SkillMasteryBonus%", r)}'
                    ),
                )

        # EffectiveHits / ProcProbability / MapleHeroMultiplier — generic for every row.
        ws.cell(row=r, column=7, value=(
            f'={S("HitsPerCast", r)}*IF({S("ICD(s)", r)}>0,{S("ActiveWindow(s)", r)}/{S("ICD(s)", r)},1)'
        ))
        ws.cell(row=r, column=8, value=f'=1-(1-{S("ProcChance%", r)}/100)^{S("RollsPerCast", r)}')
        ws.cell(
            row=r, column=9,
            value=(
                f'=IF({S("MapleHeroBase(tenths%)", r)}<>"",'
                f'1+({S("MapleHeroBase(tenths%)", r)}/10)*($Z$3/1000)/100,1)'
            ),
        )

        if key == "CHAIN_LIGHTNING" or key in DAMAGE_ROW_KEYS:
            ws.cell(row=r, column=10, value=f'={IB("attack")}*(F{r}/100)')
            monster_dmg_term = monster_blend_expr(
                IB("monster_type"), IB("normal_weight_frac"),
                f'{IB("boss_damage")}+{S("MasteryBossDamage%", r)}+Summary!$B${SUMMARY_ROW["MONSTER_DMG_BONUS"]}',
                f'{IB("normal_damage")}+{S("MasteryNormalDamage%", r)}+Summary!$B${SUMMARY_ROW["MONSTER_DMG_BONUS"]}',
                "0",
            )
            ws.cell(row=r, column=11, value=(
                f'=J{r}*(1+{IB("stat_damage")}/100)'
                f'*(1+({IB("damage")}+Summary!$B${SUMMARY_ROW["DAMAGE_BONUS"]})/100)'
                f'*(1+{monster_dmg_term}/100)'
                f'*(1+{IB("damage_amp")}/100)'
                f'*(5000/(6000+{IB("monster_defense")}*(1-{IB("def_pen")}/100)))'
                f'*(1+{IB("final_damage")}/100)*(1+{elem_amp_gated}/100)'
                f'*(1+{arcane_aim_gated}/100)^5'
                f'*(1+(IF({S("Key", r)}="CHAIN_LIGHTNING",{IB("basic_attack_damage")},'
                f'{IB("skill_damage")}))/100)'
                f'*(Summary!$B${SUMMARY_ROW["AVG_BUFF_MULT"]}*I{r})'
            ))
            ws.cell(row=r, column=12, value=f'=K{r}*(MIN({IB("min_damage")},{IB("max_damage")})/100+{IB("max_damage")}/100)/2')
            ws.cell(row=r, column=13, value=f'=L{r}*(1+{IB("crit_damage")}/100)')
            ws.cell(row=r, column=14, value=(
                f'=L{r}*(1-MIN({IB("crit_rate")},100)/100)+M{r}*(MIN({IB("crit_rate")},100)/100)'
            ))
        else:
            for col in (10, 11, 12, 13, 14):
                ws.cell(row=r, column=col, value="")

        if key == "CHAIN_LIGHTNING":
            ws.cell(row=r, column=15, value=(
                f"=IF(C{r},{S('HitsPerCast', r)}*N{r}*Summary!$B${SUMMARY_ROW['BASIC_ATTACKS_PER_SEC']}*"
                f"{target_multiplier_expr(IB('monster_type'), IB('normal_weight_frac'), S('NormalMonsterTargets', r), IB('max_enemies_hit'))},0)"
            ))
        elif key == "FROZEN_ORB":
            ws.cell(row=r, column=15, value=(
                f'=IF(C{r},H{r}*N{r}*{rate_r}*{frozen_orb_single_target_mult}*'
                f"{target_multiplier_expr(IB('monster_type'), IB('normal_weight_frac'), S('NormalMonsterTargets', r), IB('max_enemies_hit'))},0)"
            ))
        elif key in DAMAGE_ROW_KEYS:
            ws.cell(row=r, column=15, value=(
                f'=IF(C{r},H{r}*N{r}*{rate_r}*'
                f"{target_multiplier_expr(IB('monster_type'), IB('normal_weight_frac'), S('NormalMonsterTargets', r), IB('max_enemies_hit'))},0)"
            ))
        else:
            ws.cell(row=r, column=15, value=0)

        ws.cell(row=r, column=16, value=f'=IF(Summary!$B${SUMMARY_ROW["TOTAL_DPS"]}=0,0,O{r}/Summary!$B${SUMMARY_ROW["TOTAL_DPS"]})')

        # Safe per-row reciprocal cooldown (see build_fp_mage_workbook.py's own comment on this
        # exact cell for why a bare IFERROR(1/x) is used instead of nesting it inside SUMPRODUCT).
        ws.cell(row=r, column=17, value=f'=IFERROR(1/{eff_cd_r},0)')

        if ROW_HAS_COOLDOWN[key]:
            ws.cell(row=r, column=18, value=(
                f'=IF({fixed_duration_active_main},{exact_casts_expr(IB("fight_duration"), eff_cd_r)},0)'
            ))
        else:
            ws.cell(row=r, column=18, value=0)

    ws.cell(row=1, column=17, value="InvCooldown")
    ws.cell(row=1, column=18, value="CastsInFight")

    widths = [22, 30, 10, 12, 9, 15, 13, 14, 17, 13, 15, 12, 12, 17, 12, 10]
    for i, w in enumerate(widths):
        ws.column_dimensions[get_column_letter(i + 1)].width = w
    ws.freeze_panes = "C2"
    return ws


def build_summary_sheet(wb):
    ws = wb.create_sheet("Summary")
    ws["A1"] = "Arch Mage (Ice/Lightning) — DPS Summary"
    ws["A1"].font = Font(bold=True, size=14)

    ws.cell(row=DERIVED_HEADER_ROW, column=1, value="Derived Values (read-only, computed from Inputs)").font = SECTION_FONT
    ws.cell(row=D_ATTACK, column=1, value="ATTACK (= Flat ATTACK x (1+ATTACK%/100))")
    ws.cell(row=D_ATTACK, column=2, value=f'={IB("flat_attack")}*(1+{IB("attack_pct")}/100)')

    ws.cell(row=D_STAT_DAMAGE, column=1, value="STAT_DAMAGE % (= 1% of total INT + 0.25% of LUK)")
    ws.cell(
        row=D_STAT_DAMAGE, column=2,
        value=f'=({IB("flat_int")}*(1+{IB("int_pct")}/100))*0.01+{IB("luk")}*0.0025'
    )

    ws.cell(row=D_BASIC_INPUT_LEVEL, column=1, value="Basic Attack (Chain Lightning) Input Level (4th job formula)")
    ws.cell(
        row=D_BASIC_INPUT_LEVEL, column=2,
        value=f'=MAX(0,({IB("level")}-100)*3)+{IB("skill_lvl_4th")}+{IB("skill_lvl_all")}'
    )
    ws.cell(row=D_BASIC_FACTOR, column=1, value="Basic Attack Factor (factorIndex 21, from Chain Lightning reverse-engineering)")
    ws.cell(
        row=D_BASIC_FACTOR, column=2,
        value=f'=INDEX(FactorTable!$B$2:$Y$301, MATCH(ROUND(MIN(300,MAX(1,{IB("basic_input_level")})),0), '
              f'FactorTable!$A$2:$A$301,0), 22)'
    )
    ws.cell(row=D_SKILL_COEFFICIENT, column=1, value="SKILL_COEFFICIENT — Chain Lightning base coefficient % (before Skill Mastery)")
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

    r_avgbuff, r_mdb, r_db, r_asb, r_aps, r_castrate, r_baps = (
        SUMMARY_ROW["AVG_BUFF_MULT"],
        SUMMARY_ROW["MONSTER_DMG_BONUS"], SUMMARY_ROW["DAMAGE_BONUS"], SUMMARY_ROW["AS_BONUS"],
        SUMMARY_ROW["APS"], SUMMARY_ROW["CAST_RATE"], SUMMARY_ROW["BASIC_ATTACKS_PER_SEC"],
    )
    r_total, r_basic = SUMMARY_ROW["TOTAL_DPS"], SUMMARY_ROW["BASIC_ATTACK_DPS"]

    ed = ROW["ELEMENTAL_RESET"]

    med, mg, inf = ROW["MEDITATION"], ROW["MAGIC_GUARD"], ROW["INFINITY"]
    bdi_main = bdi_with_buff_mastery_expr(IB("buff_duration_increase_pct"), IB("level"), f'Calc!F{ROW["BUFF_MASTERY"]}')
    fda_main = fixed_duration_active_expr(IB("monster_type"), IB("fight_duration"))

    def buff_uptime(row):
        return uptime_fraction_or_exact_expr(
            fda_main, f'Calc!R{row}', IB("monster_type"), S("BuffDuration(s)", row), S("Cooldown(s)", row),
            bdi_main, IB("fight_duration"),
        )

    ws.cell(row=r_avgbuff, column=1, value="Average Buff Multiplier (Magic Guard + Meditation, summed; then Infinity)")
    ws.cell(row=r_avgbuff, column=2, value=(
        # Magic Guard and Meditation are both "+X% Attack" sources — same bucket, so they sum into
        # one combined percentage before a single multiplication, instead of each compounding
        # against the other. Infinity is Final Damage, a different (and deliberately still
        # multiplicative) bucket, so it stays its own separate factor.
        f'=(1+(IF(Calc!C{mg}=TRUE,Calc!F{mg}*{buff_uptime(mg)},0)'
        f'+IF(Calc!C{med}=TRUE,Calc!F{med}*{buff_uptime(med)},0))/100)'
        f'*IF(Calc!C{inf}=TRUE,(1+Calc!F{inf}*{buff_uptime(inf)}/100),1)'
    ))

    # Freezing Breath - Weaken (Mastery Lv.118): +15% Damage Taken debuff for 30s, tied to
    # Freezing Breath's own (patched) 40s cooldown — duty-cycle averaged (steady-state only, no
    # fixed-duration exactness, a documented simplification for this secondary mastery effect,
    # same tier as Night Lord's own Frailty Curse Lv.111 simplification). Elemental Reset's own
    # Damage Taken bonus is the SAME kind of bonus (target damage-taken%), so it's summed into
    # this same bucket rather than kept as its own separate multiplicative factor. Feeds into
    # Calc!K's monster_dmg_term additively (both boss and normal branches).
    fb_cd = S("Cooldown(s)", ROW["FREEZING_BREATH"])
    ws.cell(row=r_mdb, column=1, value="Monster Damage Taken Bonus % (Freezing Breath - Weaken + Elemental Reset, summed)")
    ws.cell(row=r_mdb, column=2, value=(
        f'=IF({IB("level")}>=118,15*{uptime_fraction_expr(IB("monster_type"), 30, fb_cd, bdi_main)},0)'
        f'+IF(Calc!C{ed}=TRUE,Calc!F{ed},0)'
    ))

    # Frozen Break (Lv.66 base +2%p/stack Mastery Lv.98, always 5 Frost stacks) + Frost Clutch
    # (Lv.125, 4%/stack patched, always 5 stacks, now applies to ALL skills) — both flat,
    # level-gated additive Damage% terms, no per-row Skills/Calc mechanics needed. Feeds
    # Calc!K's damage% term additively.
    ws.cell(row=r_db, column=1, value="Damage % Bonus (Frozen Break + Frost Clutch, flat)")
    ws.cell(row=r_db, column=2, value=(
        f'=IF({IB("level")}>=66,15,0)+IF({IB("level")}>=98,10,0)+IF({IB("level")}>=125,20,0)'
    ))

    # MP Eater - MP Boost (Mastery Lv.49): flat +7% Attack Speed once unlocked, ignoring the
    # MP>=50% condition (always-on per the user's decision) — a real, always-on contributor
    # (not baked into Inputs), so it's read directly here rather than via the generic
    # buff-uptime machinery (it isn't a timed buff at all).
    me = ROW["MP_EATER_MP_BOOST"]
    ws.cell(row=r_asb, column=1, value="Attack Speed Bonus % (MP Eater - MP Boost, always-on once unlocked)")
    ws.cell(row=r_asb, column=2, value=f'=IF(Calc!C{me}=TRUE,Calc!F{me},0)')

    ws.cell(row=r_aps, column=1, value="Actions Per Second (Attack Speed combined via diminishing-returns stack, factor 150, then capped)")
    ws.cell(row=r_aps, column=2, value=(
        f'=1+MIN(150,150*(1-(1-{IB("attack_speed")}/150)*(1-B{r_asb}/150)))/100'
    ))

    ws.cell(row=r_castrate, column=1, value="Skill + Buff Cast Rate (subtracted from Chain Lightning, 1/s)")
    ws.cell(row=r_castrate, column=2, value=(
        f'=IF({fda_main},'
        f'SUMPRODUCT((Skills!{SC["CostsActionSlot"]}2:{SC["CostsActionSlot"]}{LAST_ROW}=TRUE)*'
        f'(Calc!C2:C{LAST_ROW}=TRUE)*Calc!R2:R{LAST_ROW})/{IB("fight_duration")},'
        f'SUMPRODUCT((Skills!{SC["CostsActionSlot"]}2:{SC["CostsActionSlot"]}{LAST_ROW}=TRUE)*'
        f'(Calc!C2:C{LAST_ROW}=TRUE)*Calc!Q2:Q{LAST_ROW}))'
    ))

    ws.cell(row=r_baps, column=1, value="Chain Lightning Casts Per Second (basic-attack rate)")
    ws.cell(row=r_baps, column=2, value=f'=MAX(0,B{r_aps}-B{r_castrate})')

    ws.cell(row=r_total, column=1, value="TOTAL DPS").font = Font(bold=True, size=13)
    ws.cell(row=r_total, column=2, value=f"=SUM(Calc!O2:O{LAST_ROW})").font = Font(bold=True, size=13)

    ws.cell(row=r_basic, column=1, value="Chain Lightning DPS")
    ws.cell(row=r_basic, column=2, value=f"=Calc!O{ROW['CHAIN_LIGHTNING']}")

    ws.cell(row=5, column=1, value="Per-Skill DPS Breakdown").font = SECTION_FONT
    ws.cell(row=6, column=1, value="Skill")
    ws.cell(row=6, column=2, value="DPS")
    ws.cell(row=6, column=3, value="% of Total")
    style_header_row(ws, 6, 3)
    row_cursor = 7
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
# Sensitivity sheet: marginal DPS from bumping each Inputs stat by +1 — same STAT_SWEEP list
# and mechanism as build_fp_mage_workbook.py (identical Inputs-sheet stat pool, INT-main/LUK-sub
# stat identity, no rename needed). Each swept stat gets its own full, self-contained copy of
# the Calc+Summary formula pipeline so its Total DPS is guaranteed correct by construction.
# ---------------------------------------------------------------------------
STAT_SWEEP = [
    ("flat_int", "Flat INT", "flat"),
    ("int_pct", "INT %", "pct"),
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
]

SENSITIVITY_HEADER_ROW = 4
SENSITIVITY_ROW_FOR = {key: SENSITIVITY_HEADER_ROW + 1 + idx for idx, (key, _, _) in enumerate(STAT_SWEEP)}

# Same 16-stat generic pool + hand-added slot-specific stats as FP-Mage (identical INT/LUK
# stat identity, identical TS-sourced potential data) — no ILM-specific changes needed.
POTENTIAL_STAT_TO_SWEEP_KEY = {
    "Critical Rate %": "crit_rate",
    "Critical Damage %": "crit_damage",
    "Attack Speed %": "attack_speed",
    "Damage %": "damage",
    "Final Damage %": "final_damage",
    "Min Damage Multiplier %": "min_damage",
    "Max Damage Multiplier %": "max_damage",
    "Defense Penetration": "def_pen",
    "Int %": "int_pct",
    "Int": "flat_int",
    "Basic Attack Damage %": "basic_attack_damage",
    "Skill Damage %": "skill_damage",
    "Skill Cooldown Decrease (seconds)": "skill_cooldown_decrease",
    "Buff Duration Increase %": "buff_duration_increase_pct",
    "All Skill Level": "skill_lvl_all",
    "Basic Attack Target Increase": "basic_attack_target_increase",
}


def dps_per_unit_expr(stat_name):
    if stat_name == "Main Stat Per Level":
        return f'=Sensitivity!H{SENSITIVITY_ROW_FOR["flat_int"]}*{IB("level")}'
    if stat_name == "Main Stat % per 4 Levels":
        return f'=Sensitivity!H{SENSITIVITY_ROW_FOR["int_pct"]}*INT({IB("level")}/4)'
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


# Vertical span of one Sensitivity block: label + header (2 rows) + one row per Skills-sheet
# row (2..LAST_ROW) + 8 local summary rows (ed/avgbuff/mdb/db/asb/aps/castrate/baps, same count
# as FP-Mage's own 8: bm/ed/avgbuff/asbonus/aps/castrate/baps/meteor) + 1 blank + total + 2
# blank spacer rows before the next block. Derived from LAST_ROW so it can't drift out of sync.
BLOCK_HEIGHT = LAST_ROW + 14
BLOCK_START = SENSITIVITY_HEADER_ROW + len(STAT_SWEEP) + 3


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
            return f'(({ib("flat_int")}*(1+{ib("int_pct")}/100))*0.01+{ib("luk")}*0.0025)'
        return IB(key)
    return ib


def build_stat_block(ws, base_row, ib, stat_key, stat_label, override_expr):
    """Self-contained local Calc+Summary DPS pipeline (mirrors build_fp_mage_workbook.py's own
    build_stat_block — see its docstring for the general approach). Returns the cell reference
    holding this block's Total DPS."""
    row_label = base_row
    row_header = base_row + 1
    calc_start = base_row + 2
    row_of = {key: calc_start + (r - 2) for key, r in ROW.items()}
    calc_end = calc_start + (LAST_ROW - 2)

    s_avgbuff = calc_end + 3
    s_mdb = calc_end + 4
    s_db = calc_end + 5
    s_asb = calc_end + 6
    s_aps = calc_end + 7
    s_castrate = calc_end + 8
    s_baps = calc_end + 9
    s_total = calc_end + 11
    avgbuff_ref, mdb_ref = f"B{s_avgbuff}", f"B{s_mdb}"
    db_ref, asb_ref, aps_ref = f"B{s_db}", f"B{s_asb}", f"B{s_aps}"
    castrate_ref, baps_ref, total_ref = f"B{s_castrate}", f"B{s_baps}", f"B{s_total}"

    # Magic Critical pattern deltas — already baked into the matching Inputs field at the
    # current skill level, so only the marginal delta (this block's own F, reflecting any
    # active override, minus the main Calc sheet's F) needs adding. Identically 0 for every
    # block except the one sweeping the relevant skill-level-bonus. Crit Rate has TWO
    # contributing rows (High Wisdom + Magic Critical (Crit Rate), both feeding the same
    # Inputs field) — both deltas must be summed, not just one.
    crit_rate_delta = (
        f'((F{row_of["MAGIC_CRITICAL_RATE"]}-Calc!F{ROW["MAGIC_CRITICAL_RATE"]})'
        f'+(F{row_of["HIGH_WISDOM"]}-Calc!F{ROW["HIGH_WISDOM"]}))'
    )
    crit_dmg_delta = f'(F{row_of["MAGIC_CRITICAL_DAMAGE"]}-Calc!F{ROW["MAGIC_CRITICAL_DAMAGE"]})'
    min_dmg_delta = f'(F{row_of["SPELL_MASTERY"]}-Calc!F{ROW["SPELL_MASTERY"]})'
    # Magic Acceleration feeds Attack Speed % — no FP-Mage analog for this delta (FP-Mage's own
    # Magic-Critical-pattern rows never target Attack Speed), needed here since Attack Speed
    # flows through the local Actions-Per-Second formula, not the K-column chain.
    attack_speed_delta = f'(F{row_of["MAGIC_ACCELERATION"]}-Calc!F{ROW["MAGIC_ACCELERATION"]})'

    # Flat ATTACK is assumed to already include the character's current INT/LUK-derived attack
    # (1 total INT = 1 flat Attack, 1 LUK = 0.25 flat Attack, added into the pool before ATTACK%
    # applies) — same "already baked into Inputs, only the Sensitivity marginal delta matters"
    # pattern as Magic Critical/Spell Mastery above. Identically 0 for every block except the
    # ones sweeping flat_int/int_pct/luk.
    mainstat_attack_delta = (
        f'((({ib("flat_int")}*(1+{ib("int_pct")}/100))-({IB("flat_int")}*(1+{IB("int_pct")}/100)))'
        f'+0.25*({ib("luk")}-{IB("luk")}))'
    )


    fda_block = fixed_duration_active_expr(ib("monster_type"), ib("fight_duration"))

    ea_row_of, aa_row_of = row_of["ELEMENT_AMPLIFICATION"], row_of["ARCANE_AIM"]
    elem_amp_gated_block = f'IF(C{ea_row_of}=TRUE,F{ea_row_of},0)'
    arcane_aim_gated_block = f'IF(C{aa_row_of}=TRUE,F{aa_row_of},0)'
    frozen_orb_single_target_mult_block = (
        f'IF({ib("monster_type")}="pvp",0.5,'
        f'(1-{ib("normal_weight_frac")})*0.5+{ib("normal_weight_frac")}*1)'
    )

    ws.cell(row=row_label, column=1, value=f"Stat: {stat_label}").font = LABEL_FONT
    for i, name in enumerate(CALC_HEADERS):
        ws.cell(row=row_header, column=i + 1, value=name)
    style_header_row(ws, row_header, len(CALC_HEADERS))

    maple_lvl_cell, maple_factor_cell = f"Z{row_header + 1}", f"Z{row_header + 2}"
    ws.cell(row=row_header, column=18, value="helpers")
    ws[maple_lvl_cell] = f'=MAX(0,({ib("level")}-100)*3)+{ib("skill_lvl_4th")}+{ib("skill_lvl_all")}'
    ws[maple_factor_cell] = (
        f'=INDEX(FactorTable!$B$2:$Y$301, MATCH(ROUND(MIN(300,MAX(1,{maple_lvl_cell})),0), '
        f'FactorTable!$A$2:$A$301,0), 24)'
    )
    basic_lvl_cell, basic_factor_cell, basic_coeff_cell = (
        f"T{row_header + 1}", f"T{row_header + 2}", f"T{row_header + 3}"
    )
    ws[basic_lvl_cell] = f'=MAX(0,({ib("level")}-100)*3)+{ib("skill_lvl_4th")}+{ib("skill_lvl_all")}'
    ws[basic_factor_cell] = (
        f'=INDEX(FactorTable!$B$2:$Y$301, MATCH(ROUND(MIN(300,MAX(1,{basic_lvl_cell})),0), '
        f'FactorTable!$A$2:$A$301,0), 22)'
    )
    ws[basic_coeff_cell] = f'=290*{basic_factor_cell}/1000'

    for key, r in ROW.items():
        row = row_of[key]
        ws.cell(row=row, column=1, value=f"={S('Key', r)}")
        ws.cell(row=row, column=2, value=f"={S('Name', r)}")
        ws.cell(row=row, column=3, value=unlock_expr(key))

        eff_cd_row = effective_cooldown_expr(
            ib("monster_type"), S("Cooldown(s)", r), ib("skill_cooldown_decrease"),
            S("CostsActionSlot", CDR_COSTS_ACTION_ROW[key]),
        )
        rate_row = rate_or_exact_hits_expr(
            fda_block, f"R{row}", S("HitsPerCast", r), S("ICD(s)", r), S("ActiveWindow(s)", r),
            eff_cd_row, ib("fight_duration"), f"G{row}*Q{row}",
        )

        if key == "CHAIN_LIGHTNING":
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
            if key == "INFINITY":
                ws.cell(row=row, column=6, value=(
                    f"=({S('BaseDamage(tenths%)', r)}/10)*(E{row}/1000)*64/45+{S('SkillMasteryBonus%', r)}"
                ))
            else:
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

        if key == "CHAIN_LIGHTNING" or key in DAMAGE_ROW_KEYS:
            ws.cell(row=row, column=10, value=(
                f'=({ib("attack")}+{mainstat_attack_delta}*(1+{ib("attack_pct")}/100))*(F{row}/100)'
            ))
            monster_dmg_term = monster_blend_expr(
                ib("monster_type"), ib("normal_weight_frac"),
                f'{ib("boss_damage")}+{S("MasteryBossDamage%", r)}+{mdb_ref}',
                f'{ib("normal_damage")}+{S("MasteryNormalDamage%", r)}+{mdb_ref}',
                "0",
            )
            ws.cell(row=row, column=11, value=(
                f'=J{row}*(1+{ib("stat_damage")}/100)'
                f'*(1+({ib("damage")}+{db_ref})/100)'
                f'*(1+{monster_dmg_term}/100)'
                f'*(1+{ib("damage_amp")}/100)'
                f'*(5000/(6000+{ib("monster_defense")}*(1-{ib("def_pen")}/100)))'
                f'*(1+{ib("final_damage")}/100)*(1+{elem_amp_gated_block}/100)'
                f'*(1+{arcane_aim_gated_block}/100)^5'
                f'*(1+(IF({S("Key", r)}="CHAIN_LIGHTNING",{ib("basic_attack_damage")},'
                f'{ib("skill_damage")}))/100)'
                f'*({avgbuff_ref}*I{row})'
            ))
            ws.cell(row=row, column=12, value=(
                f'=K{row}*(MIN({ib("min_damage")}+{min_dmg_delta},{ib("max_damage")})/100+{ib("max_damage")}/100)/2'
            ))
            ws.cell(row=row, column=13, value=f'=L{row}*(1+({ib("crit_damage")}+{crit_dmg_delta})/100)')
            ws.cell(row=row, column=14, value=(
                f'=L{row}*(1-MIN({ib("crit_rate")}+{crit_rate_delta},100)/100)'
                f'+M{row}*(MIN({ib("crit_rate")}+{crit_rate_delta},100)/100)'
            ))
        else:
            for col in (10, 11, 12, 13, 14):
                ws.cell(row=row, column=col, value="")

        if key == "CHAIN_LIGHTNING":
            chain_targets_expr = f'(6+{ib("basic_attack_target_increase")})'
            ws.cell(row=row, column=15, value=(
                f"=IF(C{row},{S('HitsPerCast', r)}*N{row}*{baps_ref}*"
                f"{target_multiplier_expr(ib('monster_type'), ib('normal_weight_frac'), chain_targets_expr, ib('max_enemies_hit'))},0)"
            ))
        elif key == "FROZEN_ORB":
            ws.cell(row=row, column=15, value=(
                f'=IF(C{row},H{row}*N{row}*{rate_row}*{frozen_orb_single_target_mult_block}*'
                f"{target_multiplier_expr(ib('monster_type'), ib('normal_weight_frac'), S('NormalMonsterTargets', r), ib('max_enemies_hit'))},0)"
            ))
        elif key in DAMAGE_ROW_KEYS:
            ws.cell(row=row, column=15, value=(
                f'=IF(C{row},H{row}*N{row}*{rate_row}*'
                f"{target_multiplier_expr(ib('monster_type'), ib('normal_weight_frac'), S('NormalMonsterTargets', r), ib('max_enemies_hit'))},0)"
            ))
        else:
            ws.cell(row=row, column=15, value=0)

        ws.cell(row=row, column=16, value=f'=IF({total_ref}=0,0,O{row}/{total_ref})')
        ws.cell(row=row, column=17, value=f'=IFERROR(1/{eff_cd_row},0)')

        if ROW_HAS_COOLDOWN[key]:
            ws.cell(row=row, column=18, value=(
                f'=IF({fda_block},{exact_casts_expr(ib("fight_duration"), eff_cd_row)},0)'
            ))
        else:
            ws.cell(row=row, column=18, value=0)

    ed = row_of["ELEMENTAL_RESET"]

    med, mg, inf = row_of["MEDITATION"], row_of["MAGIC_GUARD"], row_of["INFINITY"]
    bdi_block = bdi_with_buff_mastery_expr(ib("buff_duration_increase_pct"), ib("level"), f'F{row_of["BUFF_MASTERY"]}')

    def buff_uptime_block(local_row, skills_row):
        return uptime_fraction_or_exact_expr(
            fda_block, f'R{local_row}', ib("monster_type"), S("BuffDuration(s)", skills_row),
            S("Cooldown(s)", skills_row), bdi_block, ib("fight_duration"),
        )

    ws.cell(row=s_avgbuff, column=1, value="Average Buff Multiplier (Magic Guard + Meditation, summed; then Infinity)")
    ws.cell(row=s_avgbuff, column=2, value=(
        f'=(1+(IF(C{mg}=TRUE,F{mg}*{buff_uptime_block(mg, ROW["MAGIC_GUARD"])},0)'
        f'+IF(C{med}=TRUE,F{med}*{buff_uptime_block(med, ROW["MEDITATION"])},0))/100)'
        f'*IF(C{inf}=TRUE,(1+F{inf}*{buff_uptime_block(inf, ROW["INFINITY"])}/100),1)'
    ))

    fb_cd_block = S("Cooldown(s)", ROW["FREEZING_BREATH"])
    ws.cell(row=s_mdb, column=1, value="Monster Damage Taken Bonus % (Freezing Breath - Weaken + Elemental Reset, summed)")
    ws.cell(row=s_mdb, column=2, value=(
        f'=IF({ib("level")}>=118,15*{uptime_fraction_expr(ib("monster_type"), 30, fb_cd_block, bdi_block)},0)'
        f'+IF(C{ed}=TRUE,F{ed},0)'
    ))

    ws.cell(row=s_db, column=1, value="Damage % Bonus (Frozen Break + Frost Clutch, flat)")
    ws.cell(row=s_db, column=2, value=(
        f'=IF({ib("level")}>=66,15,0)+IF({ib("level")}>=98,10,0)+IF({ib("level")}>=125,20,0)'
    ))

    me = row_of["MP_EATER_MP_BOOST"]
    ws.cell(row=s_asb, column=1, value="Attack Speed Bonus % (MP Eater - MP Boost, always-on once unlocked)")
    ws.cell(row=s_asb, column=2, value=f'=IF(C{me}=TRUE,F{me}+{attack_speed_delta},0)')

    ws.cell(row=s_aps, column=1, value="Actions Per Second")
    ws.cell(row=s_aps, column=2, value=f'=1+MIN(150,150*(1-(1-{ib("attack_speed")}/150)*(1-{asb_ref}/150)))/100')

    ws.cell(row=s_castrate, column=1, value="Skill + Buff Cast Rate")
    ws.cell(row=s_castrate, column=2, value=(
        f'=IF({fda_block},'
        f'SUMPRODUCT((Skills!{SC["CostsActionSlot"]}2:{SC["CostsActionSlot"]}{LAST_ROW}=TRUE)*'
        f'(C{calc_start}:C{calc_end}=TRUE)*R{calc_start}:R{calc_end})/{ib("fight_duration")},'
        f'SUMPRODUCT((Skills!{SC["CostsActionSlot"]}2:{SC["CostsActionSlot"]}{LAST_ROW}=TRUE)*'
        f'(C{calc_start}:C{calc_end}=TRUE)*Q{calc_start}:Q{calc_end}))'
    ))

    ws.cell(row=s_baps, column=1, value="Chain Lightning Casts Per Second")
    ws.cell(row=s_baps, column=2, value=f'=MAX(0,{aps_ref}-{castrate_ref})')

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
        ws.cell(row=row, column=6, value=f"=Summary!$B${SUMMARY_ROW['TOTAL_DPS']}")
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
    build_fp_mage_workbook.py's own build_cube_data_sheet (class-agnostic in shape; the only
    class-specific piece is dps_per_unit_expr, already defined above for this class' own
    Sensitivity-sheet row layout). Not meant for manual editing."""
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
    """Live lookup of a stat NAME cell -> its DPS-per-unit factor, via CubeData!J:K."""
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
    """If a previous Ice-Lightning-Mage-DPS-Calculator.xlsx already exists at `path`, read back
    its Inputs values and PotentialCubes current-gear table so regenerating the workbook doesn't
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
            if row in COMPUTED_INPUT_ROWS:
                continue
            value = ws.cell(row=row, column=2).value
            # Inputs cells are always raw literals now (never formulas) — a formula string here
            # means this row held something else before a layout change; skip it rather than
            # carry over stale data from the wrong cell.
            if value is not None and not (isinstance(value, str) and value.startswith("=")):
                existing_inputs[key] = value

        old_label = ws.cell(row=IN["content_type"], column=1).value or ""
        if "Content Type" not in old_label:
            existing_inputs.pop("content_type", None)
            existing_inputs.pop("chapter_stage", None)

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
