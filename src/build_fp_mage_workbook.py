#!/usr/bin/env python3
"""
Generates FP-Mage-DPS-Calculator.xlsx: a live-formula Excel replica of the
Fire/Poison Arch Mage skill-rotation DPS model from
src/ts/services/active-skill-dps.service.ts (+ damage-calculation.service.ts,
skill-coefficient.service.ts, arch-mage-fp-active-skills.ts), extended with
Skill Mastery bonuses that the original app never modeled.

Sheets:
  Inputs      - character stats (the only cells you're meant to edit, besides Skills)
  FactorTable - SKILL_LEVEL_FACTOR_TABLE, levels 1-300 x 24 factor columns, verbatim
  Skills      - one row per skill/buff/passive; edit or add rows here to change the kit
  Calc        - per-row formula engine (mirrors calculateHitDamage + calculateArchMageFpDps)
  Summary     - shared multipliers, action economy, total DPS, per-skill breakdown

Skill Mastery model (per-row, in the Skills sheet — no separate Inputs fields):
  - SkillMasteryBonus%   adds directly onto that row's coefficient% (same row's own
                          damage-percent term, before the hit-damage formula runs).
                          Basic Attack's own Mastery (e.g. 21%) is just this column on
                          the Basic Attack row, same mechanism as every skill.
  - MasteryBossDamage%   adds directly onto Boss Monster Damage% for that row's hit
                          (e.g. Basic Attack's Boss Mastery).
  - MasteryNormalDamage% adds directly onto Normal Monster Damage% for that row's hit
                          (e.g. Creeping Toxin's Normal Monster Damage mastery).
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
OUT_PATH = REPO / "FP-Mage" / "FP-Mage-DPS-Calculator.xlsx"

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
# Load the real factor table straight from the TS source (avoid re-typing it)
# ---------------------------------------------------------------------------
def load_factor_table():
    data = json.loads(FACTOR_TABLE_JSON.read_text())
    return {int(k): v for k, v in data.items()}


FACTOR_TABLE = load_factor_table()
assert len(FACTOR_TABLE) == 300 and len(FACTOR_TABLE[1]) == 24


# ---------------------------------------------------------------------------
# Load the real potential-cube data straight from the (unused) TS web app,
# rather than re-typing 200+ weighted stat-roll rows by hand. That file is a
# JS object literal, not strict JSON (bare keys, true/false, single quotes),
# so normalize it into a Python literal before ast.literal_eval.
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
# there) — hand-added here, Python-side only, per the user's exact values. Structure mirrors
# the TS file's own 'gloves' entry: line1 always a single prime-only value at weight 1,
# line2/line3 split prime (new tier's value) vs non-prime (previous tier's value).
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
# level 115 x 20/level = 2300 flat INT) — a live, level-scaled flat INT roll, not a fixed number.
# The roll-table "value" here is deliberately left as the per-level coefficient (10/20/35/50), not
# the computed flat INT — dps_per_unit_expr special-cases this stat name to multiply Flat INT's
# own DPS-per-unit by the live Inputs!level cell, so Value*DPSPerUnit still gives the right total
# without needing a live formula in the Value column itself.
SLOT_SPECIFIC_POTENTIALS["eye-accessory"] = _slot_specific_tier_block(
    "Main Stat Per Level", {"epic": 10, "unique": 20, "legendary": 35, "mystic": 50}
)
# Pocket's special is "N main-stat % per 4 character levels", stepped not continuous — confirmed
# by the user: only increases every 4 whole levels (e.g. level 115 x 0.6%/4-levels =
# 0.6*FLOOR(115/4) = 0.6*28 = 16.8% Int, not 0.6*115/4 = 17.25%). Same "leave the roll-table value
# as the raw coefficient, fold the level scaling into DPSPerUnit" pattern as Eye Accessory above.
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
# Inputs sheet row map (kept as a dict so formulas below can't drift out of
# sync with the layout if a row is inserted later)
# Layout: TOTAL DPS + the two summary tables (breakdown, marginal-value) sit at the top of the
# sheet (rows 3-48ish, sized dynamically off DAMAGE_DEALING_KEYS/STAT_SWEEP); every other
# accumulator/derived-value row is pushed below that into an "info dump" block starting at 50.
# ---------------------------------------------------------------------------
R_TOTAL = 3
R_BM = 58                        # Burning Magic Multiplier
R_ED_MULT = 59                   # Elemental Decrease Multiplier
R_AVGBUFF = 60                   # Average Buff Multiplier (Magic Guard + Meditation, summed; then Infinity)
R_ASBONUS = 61                   # Attack Speed Buff Bonus % (Nimble Feet, averaged)
R_APS = 62                       # Actions Per Second
R_CASTRATE = 63                  # Skill + Buff Cast Rate (subtracted from Basic Attack)
R_BAPS = 64                      # Basic Attacks Per Second
R_BASIC = 65                     # Basic Attack DPS
METEOR_PROC_RATE_ROW = 66
R_STARTUP_TIME = 67              # Buff-Casting Startup Delay (s, fixed-duration only)
R_BOSS_ONLY_TOTAL = 68           # Total DPS if every hit were against a boss (Breakthrough Sensitivity baseline)
R_NORMAL_ONLY_TOTAL = 69         # Total DPS if every hit were against normal monsters (Breakthrough Sensitivity baseline)
DERIVED_HEADER_ROW = 50
D_ATTACK = 51                    # ATTACK = Flat ATTACK x (1+ATTACK%/100)
D_STAT_DAMAGE = 52               # STAT_DAMAGE% = 1% of total INT + 0.25% of LUK
D_BASIC_INPUT_LEVEL = 53         # Basic Attack input level (4th job formula)
D_BASIC_FACTOR = 54              # Basic Attack factor lookup (factorIndex 21)
D_SKILL_COEFFICIENT = 55         # Basic Attack base coefficient % before Skill Mastery
D_NORMAL_WEIGHT_FRAC = 56        # 0/1/breakthrough-blend/0 weight, by monster_type
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
    ws["A1"] = "Fire/Poison Arch Mage — DPS Calculator: How to Use This Workbook"
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
        "Poison/DoT skills (Poison Breath, Poison Mist, Creeping Toxin, Ignite) and Burning "
        "Magic/Elemental Decrease assume the target is permanently afflicted at steady state, "
        "not an exact on/off timer.",
        "Crit Rate pushed above 100% (e.g. by cube potential lines) automatically redirects "
        "its stat-value to Crit Damage's own per-unit DPS value on the PotentialCubes sheet, "
        "since excess Crit Rate cannot do anything past 100%.",
        "Buffs (Meditation, Magic Guard, Infinity, Nimble Feet) are modeled at steady-state "
        "duty-cycle average uptime, not as an exact moment-to-moment state machine.",
        "Meteor Proc's trigger rate is the combined cast rate of every attack that can trigger "
        "it (including Basic Attack), averaged rather than simulated hit-by-hit.",
        "Ifrit is a summon skill (own cooldown/duration/DoT-tick mechanism), not part of the "
        "game's separate Companion roster system — its damage is modeled as a real DPS source "
        "like any other skill.",
        "Content Type (Inputs) picks what you're fighting — Chapter Boss/Breakthrough/PvP/EXP "
        "Dungeon/Equipment Dungeon/Weapon Dungeon/Enhancement Dungeon/Hero Dungeon/World Boss/"
        "Chapter Hunt — and Monster Defense and Fixed Fight Duration are both auto-computed from "
        "it (plus Chapter/Stage for the chapter- and dungeon-based types); PvP still forces its "
        "own fixed 15-second window and uses your own Defense stat as the opponent's Defense "
        "estimate. See README.md's 'Content Type' section for the exact formulas.",
        "Not modeled (out of scope): crowd control, Accuracy/Evasion/Defense reduction, "
        "movement speed, the character's own Defense stat, and Companion Summoning Time "
        "(the Companion roster system, unrelated to Ifrit).",
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
    ws["A1"] = "Fire/Poison Arch Mage — DPS Calculator Inputs"
    ws["A1"].font = Font(bold=True, size=14)

    # Ordered to match how these stats are laid out in-game, for quick copy-in.
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
        ("attack_speed", "ATTACK_SPEED % (base, excludes Nimble Feet)", 0),
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


SKILL_COLUMNS = [
    "Key", "Name", "JobStep", "Element", "Cooldown(s)", "CostsActionSlot",
    "HitsPerCast", "ICD(s)", "ActiveWindow(s)", "ProcChance%", "RollsPerCast",
    "BaseDamage(tenths%)", "FactorIndex", "ScalesWithLevel",
    "SkillMasteryBonus%", "MasteryBossDamage%", "MasteryNormalDamage%", "NormalMonsterTargets",
    "BuffTargetStat", "BuffDuration(s)", "TriggersElementalDecrease", "TriggersMeteorProc",
    "MeteorProcTriggersPerCast", "MapleHeroBase(tenths%)", "MapleHeroFactorIndex", "Stacks", "Note",
]
# column letters for every named column above, e.g. SC["Cooldown(s)"] -> "E"
SC = {name: get_column_letter(i + 1) for i, name in enumerate(SKILL_COLUMNS)}

# key -> row (2-23), fixed so Calc-sheet formulas below can reference by row number
ROW = {
    "BASIC_ATTACK": 2,
    "IGNITE": 3,
    "POISON_BREATH": 4,
    "ELEMENTAL_DRAIN": 5,
    "MEDITATION": 6,
    "POISON_MIST_BURST": 7,
    "POISON_MIST_DOT": 8,
    "MIST_ERUPTION": 9,
    "CREEPING_TOXIN": 10,
    "BURNING_MAGIC": 11,
    "ELEMENTAL_DECREASE": 12,
    "METEOR_SHOWER_BURST": 13,
    "METEOR_PROC": 14,
    "FLAME_HAZE_BURST": 15,
    "FLAME_HAZE_DOT": 16,
    "MAGIC_GUARD": 17,
    "NIMBLE_FEET": 18,
    "INFINITY": 19,
    "MAGIC_CRITICAL_RATE": 20,
    "MAGIC_CRITICAL_DAMAGE": 21,
    "SPELL_MASTERY": 22,
    "ELEMENT_AMPLIFICATION": 23,
    "IFRIT": 24,
    "BUFF_MASTERY": 25,
    "ARCANE_AIM": 26,
    "FERVENT_DRAIN": 27,
    "FLAME_HAZE_FOG": 28,
}
LAST_ROW = 28

# Unlock level for skills/masteries added between level 102-138 (see the approved plan). Rows
# not in this dict stay unconditionally unlocked, matching the project's existing scope decision
# to only model a 4th-job-tier character for everything from earlier job tiers.
UNLOCK_LEVEL = {
    "MIST_ERUPTION": 103,
    "METEOR_SHOWER_BURST": 105,
    "FLAME_HAZE_BURST": 107,
    "FLAME_HAZE_DOT": 107,
    "INFINITY": 110,
    "METEOR_PROC": 113,
    "IFRIT": 115,
    "BUFF_MASTERY": 117,
    "FLAME_HAZE_FOG": 118,
    "ARCANE_AIM": 120,
    "FERVENT_DRAIN": 125,
}


def unlock_expr(key):
    level = UNLOCK_LEVEL.get(key)
    return "=TRUE" if level is None else f"={IB('level')}>={level}"

# Mist Eruption's own CostsActionSlot is FALSE (it's a consequence of Poison Mist's cast, not
# an independent action-economy cast), but its Cooldown(s) cell already mirrors Poison Mist
# (burst)'s live cell, and the user confirmed CDR on Poison Mist should carry over to Mist
# Eruption too. So its effective-cooldown formula checks POISON_MIST_BURST's CostsActionSlot
# instead of its own — every other skill checks its own row (the identity default below).
CDR_COSTS_ACTION_ROW = {key: r for key, r in ROW.items()}
CDR_COSTS_ACTION_ROW["MIST_ERUPTION"] = ROW["POISON_MIST_BURST"]

# Summary sheet row holding Meteor Proc's combined triggering-attack cast rate (R in the
# proc-rate formula on the Skills!Note for that row) is METEOR_PROC_RATE_ROW, defined earlier
# alongside the other Summary-sheet row constants — the row number is baked into that Note text
# too ("Summary!B{METEOR_PROC_RATE_ROW}"), so keep them in sync if this ever moves.

# PvP fights are assumed to last this long, not the infinite/steady-state duration boss/normal
# monster fights assume. Every cooldown skill and buff in this kit has a real cooldown longer
# than this, so in PvP mode each one fits at most once — see EFFECTIVE_COOLDOWN_EXPR/
# UPTIME_FRACTION_EXPR below for how that's plugged into the existing formulas.
PVP_FIGHT_DURATION = 15


def effective_cooldown_expr(monster_type_ref, cooldown_ref, cdr_ref, costs_action_ref):
    """Cooldown to actually divide by for cast-rate/DPS purposes: the skill's own cooldown
    minus Skill Cooldown Decrease (flat seconds, floored so it can't reach zero/negative) for
    a boss/normal (steady-state) fight, or PVP_FIGHT_DURATION flat for a PvP fight — every
    skill/buff cooldown in this kit is longer than the fight, so every one of them is cast
    exactly once, and CDR isn't modeled as possibly changing that (confirmed by the user —
    "not all skills are used instantly", no need to model a skill fitting twice in 15s).
    CDR only applies to skills the character actually casts (CostsActionSlot=TRUE) — confirmed
    by the user: Poison Breath, Meditation, Poison Mist (burst), Creeping Toxin, Meteor Shower
    (burst), Flame Haze (burst), Magic Guard, Nimble Feet, Infinity. It does NOT apply to
    passives/DoTs/procs (Ignite, Elemental Drain, Poison Mist's fog DoT, Flame Haze's burn DoT,
    Meteor Proc, Burning Magic, Elemental Decrease, the Magic Critical/Spell Mastery/Element
    Amplification passives) — those have no real "cast" for a cooldown reduction to shorten.
    Mist Eruption isn't its own CostsActionSlot row, but the user confirmed CDR on Poison Mist
    should carry over to it too — its caller passes POISON_MIST_BURST's CostsActionSlot cell
    instead of its own (see CDR_COSTS_ACTION_ROW) rather than this function branching on it."""
    return (
        f'IF({monster_type_ref}="pvp",{PVP_FIGHT_DURATION},'
        f'MAX(0.1,{cooldown_ref}-IF({costs_action_ref}=TRUE,{cdr_ref},0)))'
    )


def uptime_fraction_expr(monster_type_ref, duration_ref, cooldown_ref, bdi_ref):
    """Average fraction of time a cast buff is active: duration/cooldown for a steady-state
    boss/normal fight (recast every cooldown), or min(duration, PVP_FIGHT_DURATION)/
    PVP_FIGHT_DURATION for PvP — cast once at the start, up for whichever is shorter: its own
    duration or what's left of the fight. `duration_ref` is scaled up by Buff Duration
    Increase % first; the PvP branch's own MIN() already correctly caps an inflated duration
    at the fight length, no extra handling needed there."""
    scaled_duration = f'({duration_ref}*(1+{bdi_ref}/100))'
    return (
        f'IF({monster_type_ref}="pvp",MIN({scaled_duration},{PVP_FIGHT_DURATION})/{PVP_FIGHT_DURATION},'
        f'{scaled_duration}/{cooldown_ref})'
    )


def monster_blend_expr(monster_type_ref, w_ref, boss_expr, normal_expr, pvp_expr):
    """Weighted blend of a boss-only and a normal-only value by Inputs!normal_weight_frac (0 for
    boss, 1 for normal, the user-set Breakthrough % for breakthrough) — pvp keeps its own
    existing value regardless of the weight, since pvp isn't a boss/normal blend at all. Only for
    skill-intrinsic constants (hit counts, active-window durations) where a plain linear blend of
    the RAW VALUES is correct — NOT for Boss/Normal Monster Damage% or anything downstream of it
    (DPS), where the two branches must be kept independent until blended as RATIOS — see
    boss_normal_dps_split_exprs below and its rationale."""
    return f'IF({monster_type_ref}="pvp",{pvp_expr},(1-{w_ref})*({boss_expr})+{w_ref}*({normal_expr}))'


def boss_normal_dps_split_exprs(prefix_expr, monster_type_ref, boss_dmg_pct_expr,
                                 normal_dmg_pct_expr, normal_targets_ref, max_enemies_ref):
    """Splits a row's DPS into independent boss-only and normal-only values, given `prefix_expr`
    (the H*N*rate*(extra multipliers) part shared by both — everything upstream of the monster-type
    split is already monster-type-independent). Each branch gets its own full
    (1+damage%/100)*target_count treatment; the two are blended into the real Total DPS as RATIOS
    (new/baseline) weighted by time spent, not as raw dollars weighted by branch size — dollar
    blending would let a stat's reported value be dominated by whichever branch happens to hit more
    targets, regardless of how much combat time is actually spent there (confirmed bug, fixed this
    session). PvP is single-target with neither bonus, matching the old combined behavior."""
    capped_targets = f'MIN({normal_targets_ref},{max_enemies_ref})'
    boss_mult = f'IF({monster_type_ref}="pvp",1,1+({boss_dmg_pct_expr})/100)'
    normal_mult = f'IF({monster_type_ref}="pvp",1,(1+({normal_dmg_pct_expr})/100)*({capped_targets}))'
    return f'({prefix_expr})*{boss_mult}', f'({prefix_expr})*{normal_mult}'


def fixed_duration_active_expr(monster_type_ref, fight_duration_ref):
    """True when the fixed-duration exact-count model should be used instead of the
    steady-state average: a fight duration has been set, and the fight isn't PvP (PvP already
    has its own always-on fixed-duration model via PVP_FIGHT_DURATION, untouched by this)."""
    return f'AND({monster_type_ref}<>"pvp",{fight_duration_ref}>0)'


def exact_casts_expr(duration_ref, cooldown_ref):
    """Exact number of casts within a fixed fight duration: one at t=0 (character starts the
    fight fully ready), then one every effective cooldown as long as it starts before the fight
    ends. INT (not FLOOR, which needs a second "significance" argument in Excel) — safe here
    since duration/cooldown is always >= 0."""
    return f'(INT({duration_ref}/{cooldown_ref})+1)'


def buff_cast_startup_time_expr(fda_ref, buff_col, action_col, unlocked_range, aps_ref, last_row):
    """Time to sequentially cast every currently-unlocked, actively-cast buff at the start of a
    fixed-duration fight, before the first damage-skill cast — count of such buffs times 1/APS
    (one action-slot's worth of time each, same cadence as Basic Attack/other active-cast skills).
    Zero outside fixed-duration mode, where there's no start-of-fight transient to model."""
    return (
        f'IF({fda_ref},'
        f'SUMPRODUCT((Skills!{buff_col}2:{buff_col}{last_row}>0)*'
        f'(Skills!{action_col}2:{action_col}{last_row}=TRUE)*'
        f'({unlocked_range}=TRUE))/{aps_ref},0)'
    )


def guarded_casts_expr(available_duration_ref, cooldown_ref):
    """exact_casts_expr, but 0 (not the naive formula's "always at least 1") once the available
    duration has been reduced to nothing or below — e.g. a non-buff row whose buff-casting startup
    delay alone consumes the whole fixed-duration fight. A no-op guard for buff rows, whose
    available duration is always the fight's raw (always-positive, since fixed-duration mode
    requires it) duration."""
    return f'IF({available_duration_ref}<=0,0,{exact_casts_expr(available_duration_ref, cooldown_ref)})'


def exact_total_hits_expr(casts_ref, hits_ref, icd_ref, window_ref, cooldown_ref, duration_ref):
    """Exact total tick/hit count across the whole fixed-duration fight, generalizing
    EffectiveHits (HitsPerCast*(Window/ICD)) to a finite window: every cast except the last gets
    a full window of ticks; the last cast's window is truncated to whatever fight time remains
    after it starts. Collapses to casts*HitsPerCast for non-DoT rows (ICD=0), where there's no
    window to truncate."""
    last_cast_start = f'(({casts_ref}-1)*{cooldown_ref})'
    remaining_after_last = f'MAX(0,{duration_ref}-{last_cast_start})'
    full_window_ticks = f'IF({icd_ref}>0,{window_ref}/{icd_ref},1)'
    last_cast_ticks = f'IF({icd_ref}>0,MIN({window_ref},{remaining_after_last})/{icd_ref},1)'
    return f'({hits_ref}*(({casts_ref}-1)*{full_window_ticks}+{last_cast_ticks}))'


def exact_buff_uptime_expr(casts_ref, buff_duration_ref, cooldown_ref, fight_duration_ref):
    """Exact total buff-active seconds across the whole fixed-duration fight — same last-cast
    truncation as exact_total_hits_expr, but for continuous buff duration instead of discrete
    ticks. Every existing buff's own Duration < its own Cooldown, so recasts never overlap."""
    last_cast_start = f'(({casts_ref}-1)*{cooldown_ref})'
    remaining_after_last = f'MAX(0,{fight_duration_ref}-{last_cast_start})'
    last_uptime = f'MIN({buff_duration_ref},{remaining_after_last})'
    return f'(({casts_ref}-1)*{buff_duration_ref}+{last_uptime})'


def uptime_fraction_or_exact_expr(fixed_duration_active_ref, casts_ref, monster_type_ref,
                                   duration_ref, cooldown_ref, bdi_ref, fight_duration_ref):
    """uptime_fraction_expr's steady-state/PvP fraction, or (in fixed-duration mode) the exact
    fraction of the fight a cast buff is actually active — same Buff Duration Increase % scaling
    as uptime_fraction_expr applies to duration_ref before the last-cast truncation runs."""
    scaled_duration = f'({duration_ref}*(1+{bdi_ref}/100))'
    exact = f'({exact_buff_uptime_expr(casts_ref, scaled_duration, cooldown_ref, fight_duration_ref)}/{fight_duration_ref})'
    steady = uptime_fraction_expr(monster_type_ref, duration_ref, cooldown_ref, bdi_ref)
    return f'IF({fixed_duration_active_ref},{exact},{steady})'


def rate_or_exact_hits_expr(fixed_duration_active_ref, row_ref, hits_ref, icd_ref, window_ref,
                             cooldown_ref, available_duration_ref, fight_duration_ref, steady_rate_ref):
    """G*Q equivalent (EffectiveHits x InvCooldown, i.e. average ticks/sec): the exact total
    tick/hit count over the whole fixed-duration fight divided by the fight's real duration, or
    `steady_rate_ref` (the existing steady-state EffectiveHits*InvCooldown expression) otherwise.
    `available_duration_ref` is the duration actually used to derive `row_ref`'s cast count — the
    raw fight duration for buffs, or the buff-casting-startup-delay-reduced window for non-buff
    (damage) skills — and must match, or the last cast's truncated tick window would be computed
    against a duration inconsistent with how many casts were actually counted."""
    exact_hits = exact_total_hits_expr(row_ref, hits_ref, icd_ref, window_ref, cooldown_ref, available_duration_ref)
    return f'IF({fixed_duration_active_ref},({exact_hits}/{fight_duration_ref}),{steady_rate_ref})'


def level_gated_sum(level_ref, pairs):
    """Cumulative level-gated mastery bonus: SUMPRODUCT of every (level, increment) pair whose
    threshold has been reached — e.g. Basic Attack Mastery's +10 at level 102, +11 at 106, etc.
    Replaces a single hardcoded percentage with the sum of every mastery tier unlocked so far."""
    ordered = sorted(pairs.items())
    thresholds = ",".join(str(level) for level, _ in ordered)
    increments = ",".join(str(inc) for _, inc in ordered)
    return f'=SUMPRODUCT(({level_ref}>={{{thresholds}}})*{{{increments}}})'


def bdi_with_buff_mastery_expr(bdi_ref, level_ref, buff_mastery_f_ref):
    """Buff Duration Increase %, plus Buff Mastery's own contribution (Calc!F for that row) once
    unlocked at level 117 — both feed uptime_fraction_expr's bdi_ref the same additive way."""
    return f'({bdi_ref}+IF({level_ref}>=117,{buff_mastery_f_ref},0))'


def meteor_proc_rate_expr(h_ref, icd_ref, meteor_cast_rate_ref):
    """Steady-state Meteor Proc trigger rate per second: (Chance*R)/(1+ICD*Chance*R), where R is
    the combined cast rate of every triggering attack. Shared by Meteor Proc's own DPS formula and
    the level-126 Flame Haze burn-stacking mastery below (Meteor Proc is one of its trigger sources)."""
    return f'({h_ref}*{meteor_cast_rate_ref})/(1+{icd_ref}*{h_ref}*{meteor_cast_rate_ref})'


def flame_haze_extra_rate_expr(level_ref, baps_ref, meteor_shower_q_ref, meteor_proc_rate, ifrit_q_ref):
    """Level 126 mastery: Basic Attack, Meteor Shower (burst), Meteor Proc, and Ifrit each get an
    independent 5% chance per cast/proc to also inflict Flame Haze's burn DoT. Since the DoT's own
    cast can't stack with itself (cooldown exceeds its own duration) but these proc-triggered
    instances are independent and CAN coexist with it and each other, this is the combined rate of
    new instances starting per second — 0 below level 126 (this whole mastery is a no-op then).
    This derivation (Little's Law) is the project's own, not directly confirmed by the user."""
    return f'IF({level_ref}>=126,0.05*({baps_ref}+{meteor_shower_q_ref}+{meteor_proc_rate}+{ifrit_q_ref}),0)'


def flame_haze_dot_stack_multiplier_expr(extra_rate_expr, burst_cooldown_ref):
    """Flame Haze (burn DoT)'s existing DPS formula already implicitly assumes exactly
    ActiveWindow/Cooldown average concurrent instances (the base, self-triggered one); the extra
    proc-triggered instances from level 126 add extra_rate*ActiveWindow more on top. Working through
    the algebra, the ActiveWindow term cancels, leaving this clean multiplier — 1 (no-op) whenever
    extra_rate is 0, i.e. below level 126."""
    return f'(1+{extra_rate_expr}*{burst_cooldown_ref})'


def flame_haze_total_stacks_expr(extra_rate_expr, active_window_ref, burst_cooldown_ref):
    """Average concurrent Flame Haze (burn DoT) instances — base (ActiveWindow/Cooldown) plus
    proc-triggered extras (extra_rate*ActiveWindow). Feeds Ifrit's level-130 mastery below."""
    return f'({active_window_ref}/{burst_cooldown_ref}+{extra_rate_expr}*{active_window_ref})'


_MIST_ERUPTION_NORMAL_HITS = 'IF(' + IB("level") + '>=108,4,3)'
_MIST_ERUPTION_HITS_EXPR = '=' + monster_blend_expr(
    IB("monster_type"), IB("normal_weight_frac"), "1", _MIST_ERUPTION_NORMAL_HITS, "0",
)

# (key, name, jobstep, element, cooldown, costsAction, hits, icd, window, chance,
#  rolls, baseDamage, factorIndex, scales, skillMasteryBonusPct, masteryBossDmgPct,
#  masteryNormalDmgPct, normalMonsterTargets, buffTarget, buffDuration, triggersED,
#  triggersMeteorProc, meteorProcTriggersPerCast, mapleBase, mapleFactor, stacks, note)
SKILL_ROWS = [
    ("BASIC_ATTACK", "Basic Attack", 4, "Fire", "", False, 5, 0, 0, 100, 1,
     "", "", True,
     level_gated_sum(IB("level"), {102: 10, 106: 11, 116: 12, 120: 13, 128: 14, 132: 15}),
     level_gated_sum(IB("level"), {111: 10, 124: 10}),
     0, f'=6+{IB("basic_attack_target_increase")}+IF({IB("level")}>=136,1,0)', "", 0, False, False, 1, "", "", "",
     "5 lines of damage per attack cycle — 5 independent full-damage hits (HitsPerCast=5), "
     "each using the same expected-damage-per-hit; no cooldown, DPS uses Basic Attacks/sec "
     "from the action-economy block. Basic Attack Mastery (level-gated sum: +10@102, +11@106, "
     "+12@116, +13@120, +14@128, +15@132 — 75% total once every tier is unlocked) and Boss "
     "Mastery (level-gated sum: +10@111, +10@124 — 20% total) are just this row's "
     "SkillMasteryBonus%/MasteryBossDamage% — same mechanism as every other skill, no separate "
     "Inputs-sheet fields. Basic Attack's own cast rate (Summary!Basic Attacks Per Second) is "
     "always added into the Meteor Proc trigger rate directly, so it does not need "
     "TriggersMeteorProc=TRUE here. Hits 6+Basic Attack Target Increase targets vs normal "
     "monsters (confirmed by the user), +1 more once Flame Sweep Strike Count is unlocked at "
     "level 136."),
    ("IGNITE", "Ignite", 2, "", 1, False, 3, 0, 0, 100, 1,
     130, 21, True, 100, 0, 0, 3, "", 0, False, False, 1, 500, 23, "",
     "3 walls of fire assumed permanently maintained (max instances). +250% vs Normal Monster not modeled. "
     "Skill Mastery: +100% added directly to the coefficient%. Hits 3 targets vs normal monsters."),
    ("POISON_BREATH", "Poison Breath", 2, "Poison", 18, True, 3, 0, 0, 100, 1,
     2000, 12, True, 70, 0, 0, 6, "", 0, True, True, 1, 800, 23, "",
     "Skill Mastery: +70% added directly to the coefficient%. Hits 6 targets vs normal monsters."),
    ("ELEMENTAL_DRAIN", "Elemental Drain", 2, "", 1, False, 5, 0, 0, 100, 1,
     120, 21, True, 0, 0, 0, 1, "", 0, False, False, 1, 1500, 23, "",
     "Poison assumed permanently at 5 stacks (max instances)."),
    ("MEDITATION", "Meditation", 2, "", 30, True, 1, 0, 0, 100, 1,
     200, 22, True, 0, 0, 0, 1, "ATTACK", 19.5, False, False, 1, "", "", "",
     "Buff — averaged Attack% = BaseDamage/10 * Factor/1000 * Duration/Cooldown."),
    ("POISON_MIST_BURST", "Poison Mist (burst)", 3, "Poison", 24.5, True, 3, 0, 0, 100, 1,
     1600, 12, True, 50, 0, 0, 10, "", 0, True, True, 1, 100, 23, "",
     "Skill Mastery: +50% added directly to the coefficient%. (Does not apply to the fog DoT — see that row.) "
     "Hits 10 targets vs normal monsters."),
    ("POISON_MIST_DOT", "Poison Mist (fog DoT)", 3, "Poison", 24.5, False, 1, f'=IF({IB("level")}>=104,0.4,0.8)', 20, 100, 1,
     700, 12, True, 0, 0, 0, 10, "", 0, False, False, 1, 100, 23, "",
     "EffectiveHits = 1 * (ActiveWindow/ICD) = duration/tick-interval ticks per cast. Skill Mastery's +50% "
     "damage bonus does NOT apply to the fog DoT, only the burst — SkillMasteryBonus% intentionally left at "
     "0 here. Hits 10 targets vs normal monsters, same as the burst. Tick interval is 0.8s below level 104, "
     "0.4s once the level-104 mastery is unlocked."),
    ("MIST_ERUPTION", "Mist Eruption", 4, "", f"=Skills!{SC['Cooldown(s)']}{ROW['POISON_MIST_BURST']}", False,
     _MIST_ERUPTION_HITS_EXPR, 0, 0, 100, 1,
     30000, 12, True, f'=IF({IB("level")}>=122,100,0)', 0, 0, 10, "", 0, False, False, 1, "", "", "",
     "A skill of its own — only related to Poison Mist in that it's triggered while the fog is active, "
     "so it fires at the same rate as Poison Mist's own cast (Cooldown mirrors Skills!Poison Mist "
     "(burst) row's Cooldown live). Vs boss: 1 explosion per Poison Mist cast (when the fog "
     "expires, since bosses don't die mid-fog). Vs normal monster: 3 explosions per cast (base), "
     "+1 (4 total) once the level-108 mastery is unlocked, hitting 10 targets each. Vs Chapter "
     "Breakthrough: weighted average of the boss and normal counts by Inputs!normal_weight_frac. "
     "Vs PvP: 0 — it only triggers when the fog naturally expires at the end of its full duration, "
     "which never happens within the 15s PvP fight (confirmed by the user). Not affected by Poison "
     "Mist's Skill Mastery or Maple Hero bonus (confirmed by the user) — it's jobStep 4, using its "
     "own 4th-job skill level, same factorIndex 12. Its own SkillMasteryBonus% is the level-122 "
     "mastery (+100% damage), unrelated to Poison Mist's."),
    ("CREEPING_TOXIN", "Creeping Toxin", 3, "Poison", 27, True, 2, 2, 15, 100, 1,
     1200, 12, True, 50, 0, 100, 1, "", 0, True, False, 1, 100, 23, "",
     "Assumes a qualifying Fire-element hit is always available within the 2s ICD window. "
     "Skill Mastery: +50% added directly to the coefficient%, plus +100% Normal Monster Damage mastery. "
     "Deliberately excluded from Meteor Proc's trigger set (confirmed by the user)."),
    ("BURNING_MAGIC", "Burning Magic", 3, "", "", False, 1, 0, 0, 100, 1,
     50, 0, False, 0, 0, 0, 1, "", 0, False, False, 1, "", "", 5,
     "Global always-on multiplier: 1 + (BaseDamage/10 * Stacks)/100. Does not scale with level."),
    ("ELEMENTAL_DECREASE", "Elemental Decrease", 3, "", "", False, 1, 0, 0, 50, 1,
     120, 22, True, 0, 0, 0, 1, "", 7, False, False, 1, "", "", "",
     "Modeled as always-on (flat multiplier, like Burning Magic): at 50% chance per qualifying hit "
     "and a 7s duration, it gets reapplied well before it expires, so uptime is treated as 100% "
     "(confirmed by the user). ProcChance%/BuffDuration(s) are the real skill values for reference "
     "only — they no longer feed the Summary-sheet formula."),
    ("METEOR_SHOWER_BURST", "Meteor Shower (burst)", 4, "Fire", 33, True, 9, 0, 0, 100, 1,
     6000, 12, True, f'=IF({IB("level")}>=134,50,0)', 0, 0, 7, "", 0, True, True, 3, "", "", "",
     "3 meteorites x 3 hits collapsed into one 9-hit burst. Hits 7 targets vs normal monsters. "
     "MeteorProcTriggersPerCast=3 (not 1) — each of the 3 meteors is an independent Meteor Proc trigger "
     "opportunity even though all 3 land from a single cast (confirmed by the user). Skill Mastery: "
     "+50% damage once the level-134 mastery is unlocked."),
    ("METEOR_PROC", "Meteor Proc (30% on-hit, 1s ICD)", 4, "Fire", "", False, 1, 1, 0, 30, 1,
     9500, 21, True, 0, 0, 0, 1, "", 0, False, False, 1, "", "", "",
     "A skill of its own, NOT tied to Meteor Shower specifically — every cast of Basic Attack, "
     "Poison Breath, Poison Mist (burst), Meteor Shower, or Flame Haze (burst) has an independent "
     "30% chance to trigger this meteor drop, gated by a 1s internal cooldown (ICD(s) column) after "
     "each trigger. Steady-state proc rate = (Chance% * R) / (1 + ICD * Chance% * R), where R is the "
     f"combined cast rate of those qualifying attacks (Summary!B{METEOR_PROC_RATE_ROW}) — NOT the simple EffectiveHits*"
     "ProcProbability/Cooldown pattern every other row uses, since this proc has no cooldown of its "
     "own to divide by. Creeping Toxin deliberately excluded from the trigger set. 4th job only."),
    ("FLAME_HAZE_BURST", "Flame Haze (burst)", 4, "Fire", 25, True, 3, 0, 0, 100, 1,
     12000, 12, True, 0, 0, 0, 10, "", 0, True, True, 1, "", "", "",
     "Hits 10 targets vs normal monsters."),
    ("FLAME_HAZE_DOT", "Flame Haze (burn DoT)", 4, "Fire", 25, False, 1, 0.5,
     f'={monster_blend_expr(IB("monster_type"), IB("normal_weight_frac"), "20", "10", "10")}',
     100, 1, 1500, 12, True, 0, 0, 0, 10, "", 0, False, False, 1, "", "", "",
     "Burn duration is 20s vs boss, 10s vs normal monsters and PvP (confirmed by the user); "
     "Chapter Breakthrough blends the two by Inputs!normal_weight_frac. "
     "Hits 10 targets vs normal monsters, same as the burst."),
    ("MAGIC_GUARD", "Magic Guard", 1, "", 21, True, 1, 0, 0, 100, 1,
     120, 21, True, 0, 0, 0, 1, "ATTACK", 15, False, False, 1, "", "", "",
     "Buff — only the Attack component is modeled (Defense component doesn't affect own damage)."),
    ("NIMBLE_FEET", "Nimble Feet", 1, "", 60, True, 1, 0, 0, 100, 1,
     150, 0, False, 0, 0, 0, 1, "ATTACK_SPEED", 15, False, False, 1, "", "", "",
     "Buff — flat +15% Attack Speed, does not scale with level (FactorIndex is an unused "
     "placeholder here, same as Burning Magic). Averaged into effective Attack Speed before the 150% cap."),
    ("INFINITY", "Infinity", 4, "", 30, True, 1, 0, 0, 100, 1,
     216.67, 21, True, 0, 0, 0, 1, "FINAL_DAMAGE", 15, False, False, 1, "", "", "",
     "Ramps +15%->+25% Final Damage over 10s of its 15s duration; time-averaged while active = 21.6667% at factor 1000, now scaled by FactorTable[level][21]/1000 like Magic Guard/Meditation."),
    ("MAGIC_CRITICAL_RATE", "Magic Critical (Crit Rate)", 3, "", "", False, 1, 0, 0, 100, 1,
     80, 22, True, 0, 0, 0, 1, "CRIT_RATE", 0, False, False, 1, "", "", "",
     "Passive, always on (3rd job) — no cooldown/duration, not a damage row (Calc columns J-O stay blank/0). "
     "Its current contribution is already baked into Inputs!CRIT_RATE% by the user, so this row's own Calc!F "
     "value is NOT added to the baseline calculation — it's only used by the Sensitivity sheet to compute the "
     "marginal delta (this row's F at the swept level minus this row's F at the current level) when "
     "'Skill Level Bonus — 3rd Job' is the stat being tested."),
    ("MAGIC_CRITICAL_DAMAGE", "Magic Critical (Crit Damage)", 3, "", "", False, 1, 0, 0, 100, 1,
     120, 22, True, 0, 0, 0, 1, "CRIT_DAMAGE", 0, False, False, 1, "", "", "",
     "Same mechanism as Magic Critical (Crit Rate) above, targeting CRIT_DAMAGE% instead."),
    ("SPELL_MASTERY", "Spell Mastery", 2, "", "", False, 1, 0, 0, 100, 1,
     150, 22, True, 0, 0, 0, 1, "MIN_DAMAGE", 0, False, False, 1, "", "", "",
     "Passive, always on (2nd job) — no cooldown/duration, not a damage row. Its current contribution is "
     "already baked into Inputs!MIN_DAMAGE% by the user; this row's Calc!F is only used by the Sensitivity "
     "sheet to compute the marginal delta when 'Skill Level Bonus — 2nd Job' is swept."),
    ("ELEMENT_AMPLIFICATION", "Element Amplification", 4, "", "", False, 1, 0, 0, 100, 1,
     150, 22, True, 0, 0, 0, 1, "FINAL_DAMAGE", 0, False, False, 1, "", "", "",
     "Passive, always on (4th job) — no cooldown/"
     "duration, not a damage row. Unlike the two rows above, this one is NOT reflected anywhere in Inputs, "
     "so its current-level value (Calc!F23) is added directly into every hit's Final Damage term in both the "
     "main Calc sheet and every Sensitivity block — combined MULTIPLICATIVELY with Inputs!FINAL_DAMAGE% "
     "(Final Damage sources always stack as (1+a/100)*(1+b/100), never as (1+(a+b)/100))."),
    ("IFRIT", "Ifrit", 4, "Fire", 80, True, 1, 4, f'=IF({IB("level")}>=138,40,30)', 100, 1,
     35000, 12, True, 0, 0, 0, f'=IF({IB("level")}>=138,6,3)', "", 0, False, False, 1, "", "", "",
     "Summon, 80s cooldown. EffectiveHits = HitsPerCast*(ActiveWindow/ICD) — same mechanism as "
     "Poison Mist's fog DoT/Flame Haze's burn DoT, no new Calc-sheet machinery needed: attacks "
     "every 4s (ICD) for its 30s duration (ActiveWindow), hitting 3 targets vs normal monsters, "
     "for the whole 80s cast cycle (Cooldown/InvCooldown). Duration -> 40s and targets -> 6 once "
     "the level-138 mastery is unlocked. Deliberately excluded from Meteor Proc's trigger set "
     "(confirmed by the user) — it only counts as a trigger source for the level-126 Flame Haze "
     "burn-proc mastery (see build_calc_sheet) and for Fervent Drain (via DAMAGE_ROW_KEYS, same "
     "as every other non-Basic-Attack skill). Gains a level-130 mastery multiplier "
     "(1+20%*Flame Haze burn stacks) — see flame_haze_total_stacks_expr."),
    ("BUFF_MASTERY", "Buff Mastery", 4, "", "", False, 1, 0, 0, 100, 1,
     100, 22, True, 0, 0, 0, 1, "", 0, False, False, 1, "", "", "",
     "Passive, always on (4th job, unlocked level 117) — no cooldown/duration, not a damage row. "
     "Not reflected anywhere in Inputs, so its current value (Calc!F) is added directly into "
     "every uptime_fraction_expr call's Buff Duration Increase % term, in both the main Calc "
     "sheet and every Sensitivity block (see bdi_with_buff_mastery_expr) — +10% base."),
    ("ARCANE_AIM", "Arcane Aim", 4, "", "", False, 1, 0, 0, 100, 1,
     30, 22, True, 0, 0, 0, 1, "", 0, False, False, 1, "", "", "",
     "Passive, always on (4th job, unlocked level 120) — no cooldown/duration, not a damage row. "
     "25% chance per attack for +3% Final Damage for 10s, stacking up to 5 times; modeled as "
     "always at max 5 stacks (confirmed by the user, same precedent as Burning Magic/Elemental "
     "Decrease always-on). Combined MULTIPLICATIVELY into the Final Damage chain as "
     "(1+Calc!F/100)^5, alongside Element Amplification — stacks are multiplicative with each "
     "other, not additive (1.03^5, not 1+5*0.03)."),
    ("FERVENT_DRAIN", "Fervent Drain", 4, "", "", False, 1, 0, 0, 100, 1,
     40, 22, True, 0, 0, 0, 1, "", 0, False, False, 1, "", "", "",
     "Passive, always on (4th job, unlocked level 125) — no cooldown/duration, not a damage row. "
     "+4% fire/poison skill damage per Poison stack on target; reuses Elemental Drain's "
     "permanently-5-stacks assumption, so its effective contribution is Calc!F*5. Added "
     "additively inside the skill_damage term of the hit-damage formula — confirmed by the user "
     "to boost skill damage only, NOT Basic Attack (Flame Sweep), even though it does cover both "
     "fire- and poison-element skills otherwise. Structurally excluded from Basic Attack's own "
     "term, not just numerically zero."),
    ("FLAME_HAZE_FOG", "Flame Haze (poison fog DoT)", 4, "Poison",
     f"=Skills!{SC['Cooldown(s)']}{ROW['FLAME_HAZE_BURST']}", False, 1,
     f'=IF({IB("level")}>=104,0.4,0.8)', 20, 100, 1,
     700, 12, True, 0, 0, 0, 10, "", 0, False, False, 1, "", "", "",
     "Unlocked level 118: Flame Haze creates a second, fully independent poisonous fog that "
     "triggers Poison Mist's DoT mechanic too — same damage/duration/ICD-mastery-gate math as "
     "POISON_MIST_DOT, tied to Flame Haze (burst)'s own live Cooldown cell (same live-cross-"
     "reference pattern MIST_ERUPTION uses for POISON_MIST_BURST). Independent of the existing "
     "Poison Mist fog — both can be active at the same time (confirmed by the user). No Maple "
     "Hero bonus (MapleHeroBase blank), matching its jobStep-4 sibling FLAME_HAZE_DOT rather than "
     "the jobStep-3 POISON_MIST_DOT."),
]

# Which rows have a real Cooldown(s) value (literal or a live formula reference, e.g. Mist
# Eruption/Flame Haze Fog mirroring another row's cooldown) — CastsInFight (exact-duration mode)
# is only meaningful for these; blank for Basic Attack, Meteor Proc, and the no-cooldown passives.
ROW_HAS_COOLDOWN = {row[0]: row[4] not in ("", None) for row in SKILL_ROWS}


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

    widths = [24, 26, 8, 8, 11, 15, 11, 8, 13, 11, 12, 18, 11, 14, 17, 16, 18, 16, 15, 14, 22, 18, 20, 20, 20, 8, 60]
    for i, w in enumerate(widths):
        ws.column_dimensions[get_column_letter(i + 1)].width = w
    ws.freeze_panes = "A2"
    return ws


DAMAGE_ROW_KEYS = [
    "IGNITE", "POISON_BREATH", "ELEMENTAL_DRAIN", "POISON_MIST_BURST", "POISON_MIST_DOT", "MIST_ERUPTION",
    "CREEPING_TOXIN", "METEOR_SHOWER_BURST", "METEOR_PROC", "FLAME_HAZE_BURST", "FLAME_HAZE_DOT",
    "IFRIT", "FLAME_HAZE_FOG",
]
BUFF_ROW_KEYS = ["MEDITATION", "MAGIC_GUARD", "NIMBLE_FEET", "INFINITY"]
SPECIAL_ROW_KEYS = ["BURNING_MAGIC", "ELEMENTAL_DECREASE"]
# Every row that can ever post a nonzero Calc!O DPS value — used to filter the Summary sheet's
# per-skill breakdown table down to real damage sources (buffs/passives always show 0.0000 there).
DAMAGE_DEALING_KEYS = ["BASIC_ATTACK"] + DAMAGE_ROW_KEYS

CALC_HEADERS = [
    "Key", "Name", "Unlocked", "InputLevel", "Factor", "CoefficientPercent",
    "EffectiveHits", "ProcProbability", "MapleHeroMultiplier",
    "BaseDamage", "BaseHitDamage", "NonCritAvg", "CritAvg", "ExpectedDamage(perHit)",
    "DPS", "% of Total",
]
CCOL = {name: get_column_letter(i + 1) for i, name in enumerate(CALC_HEADERS)}


def S(col_name, r):
    """Shorthand for a Skills-sheet cell reference by column name, e.g. S('Cooldown(s)', 9) -> 'Skills!E9'"""
    return f"Skills!{SC[col_name]}{r}"


def build_calc_sheet(wb):
    ws = wb.create_sheet("Calc")
    for i, name in enumerate(CALC_HEADERS):
        ws.cell(row=1, column=i + 1, value=name)
    style_header_row(ws, 1, len(CALC_HEADERS))

    # Maple Hero helper cells (jobStep 4, factorIndex 23) — lives off to the side
    ws["Z1"] = "Maple Hero helper (jobStep4, factorIndex23)"
    ws["Z1"].font = LABEL_FONT
    ws["Z2"] = f'=MAX(0,({IB("level")}-100)*3)+{IB("skill_lvl_4th")}+{IB("skill_lvl_all")}'
    ws["Z3"] = f'=INDEX(FactorTable!$B$2:$Y$301, MATCH(ROUND(MIN(300,MAX(1,Z2)),0), FactorTable!$A$2:$A$301,0), 24)'

    # Level 126/130 Flame Haze burn-stacking mastery — see the helper docstrings for the
    # derivation. Computed once here (static formula strings, no dependency on the per-row loop
    # below) and referenced from the FLAME_HAZE_DOT/IFRIT branches of that loop.
    meteor_proc_rate_main = meteor_proc_rate_expr(
        f'H{ROW["METEOR_PROC"]}', S("ICD(s)", ROW["METEOR_PROC"]), f'Summary!$B${METEOR_PROC_RATE_ROW}',
    )
    flame_haze_extra_rate_main = flame_haze_extra_rate_expr(
        IB("level"), f"Summary!$B${R_BAPS}", f'Q{ROW["METEOR_SHOWER_BURST"]}', meteor_proc_rate_main, f'Q{ROW["IFRIT"]}',
    )
    flame_haze_dot_multiplier_main = flame_haze_dot_stack_multiplier_expr(
        flame_haze_extra_rate_main, S("Cooldown(s)", ROW["FLAME_HAZE_BURST"]),
    )
    flame_haze_total_stacks_main = flame_haze_total_stacks_expr(
        flame_haze_extra_rate_main, S("ActiveWindow(s)", ROW["FLAME_HAZE_DOT"]), S("Cooldown(s)", ROW["FLAME_HAZE_BURST"]),
    )

    # Fixed fight-duration mode (exact cast/tick counts instead of the steady-state average) —
    # see fixed_duration_active_expr/exact_casts_expr/exact_total_hits_expr/exact_buff_uptime_expr.
    fixed_duration_active_main = fixed_duration_active_expr(IB("monster_type"), IB("fight_duration"))

    for key, r in ROW.items():
        ws.cell(row=r, column=1, value=f"={S('Key', r)}")
        ws.cell(row=r, column=2, value=f"={S('Name', r)}")

        # Unlocked: TRUE unconditionally for skills/masteries not in UNLOCK_LEVEL (rows already
        # available at 4th job), else gated on Inputs!level for the level-102..138 unlock batch.
        ws.cell(row=r, column=3, value=unlock_expr(key))

        # This row's effective cooldown (CDR-adjusted, PvP-capped) — reused below both for the
        # steady-state InvCooldown column (Q) and the exact-duration CastsInFight column (R).
        eff_cd_r = effective_cooldown_expr(
            IB("monster_type"), S("Cooldown(s)", r), IB("skill_cooldown_decrease"),
            S("CostsActionSlot", CDR_COSTS_ACTION_ROW[key]),
        )
        # Duration actually available for this row's casts in fixed-duration mode: the raw fight
        # duration for buffs (unaffected by the startup delay they themselves cause), or that
        # duration reduced by Summary!R_STARTUP_TIME for non-buff (damage) rows, since they can't
        # start until every buff has been cast once. Must match whatever CastsInFight (column R,
        # below) uses, or the last cast's truncated tick window (rate_r) would be computed against
        # an inconsistent duration.
        if key in BUFF_ROW_KEYS:
            available_duration_r = IB("fight_duration")
        else:
            available_duration_r = f'MAX(0,{IB("fight_duration")}-Summary!$B${R_STARTUP_TIME})'
        # G*Q equivalent (EffectiveHits x InvCooldown) — exact-duration-aware for rows with a
        # real cooldown; falls back to the plain G{r}*Q{r} product otherwise (Basic Attack/
        # Meteor Proc have no Cooldown(s), so ROW_HAS_COOLDOWN is False and this is never used
        # for them — they're handled by their own dedicated branches below regardless).
        rate_r = rate_or_exact_hits_expr(
            fixed_duration_active_main, f"R{r}", S("HitsPerCast", r), S("ICD(s)", r),
            S("ActiveWindow(s)", r), eff_cd_r, available_duration_r, IB("fight_duration"), f"G{r}*Q{r}",
        )

        if key == "BASIC_ATTACK":
            ws.cell(row=r, column=4, value="")  # input level shown on Inputs sheet instead
            ws.cell(row=r, column=5, value="")
            # Basic Attack's coefficient = the job-tier base coefficient (Inputs sheet) plus
            # this row's own SkillMasteryBonus% — same mechanism as every skill below.
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
            ws.cell(
                row=r, column=6,
                value=(
                    f'=IF({S("ScalesWithLevel", r)}=TRUE,({S("BaseDamage(tenths%)", r)}/10)*(E{r}/1000),'
                    f'{S("BaseDamage(tenths%)", r)}/10)+{S("SkillMasteryBonus%", r)}'
                ),
            )

        # EffectiveHits / ProcProbability / MapleHeroMultiplier — generic for every row
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

        if key == "BASIC_ATTACK" or key in DAMAGE_ROW_KEYS:
            # BaseDamage — one formula for every row now: Mastery already lives inside F (coefficient%).
            ws.cell(row=r, column=10, value=f'={IB("attack")}*(F{r}/100)')
            ws.cell(row=r, column=11, value=(
                f'=J{r}*(1+{IB("stat_damage")}/100)*(1+{IB("damage")}/100)'
                f'*(1+{IB("damage_amp")}/100)'
                f'*(5000/(6000+{IB("monster_defense")}*(1-{IB("def_pen")}/100)))'
                f'*(1+{IB("final_damage")}/100)*(1+F{ROW["ELEMENT_AMPLIFICATION"]}/100)'
                f'*(1+IF({IB("level")}>=120,F{ROW["ARCANE_AIM"]},0)/100)^5'
                f'*(1+(IF({S("Key", r)}="BASIC_ATTACK",{IB("basic_attack_damage")},'
                f'{IB("skill_damage")}+IF({IB("level")}>=125,F{ROW["FERVENT_DRAIN"]}*5,0)))/100)'
                f'*(Summary!$B${R_BM}*Summary!$B${R_ED_MULT}*Summary!$B${R_AVGBUFF}*I{r})'
            ))
            ws.cell(row=r, column=12, value=f'=K{r}*(MIN({IB("min_damage")},{IB("max_damage")})/100+{IB("max_damage")}/100)/2')
            ws.cell(row=r, column=13, value=f'=L{r}*(1+{IB("crit_damage")}/100)')
            ws.cell(row=r, column=14, value=(
                f'=L{r}*(1-MIN({IB("crit_rate")},100)/100)+M{r}*(MIN({IB("crit_rate")},100)/100)'
            ))
        else:
            for col in (10, 11, 12, 13, 14):
                ws.cell(row=r, column=col, value="")

        # Boss/Normal Monster Damage% — Mastery-derived bonuses add in here, per-row via
        # MasteryBossDamage%/MasteryNormalDamage% (e.g. Basic Attack's Boss Mastery, Creeping
        # Toxin's Normal Monster Damage mastery). Kept as two independent branch percentages,
        # never blended into one shared value — see boss_normal_dps_split_exprs.
        boss_dmg_pct_r = f'{IB("boss_damage")}+{S("MasteryBossDamage%", r)}'
        normal_dmg_pct_r = f'{IB("normal_damage")}+{S("MasteryNormalDamage%", r)}'

        if key == "BASIC_ATTACK":
            prefix = f"{S('HitsPerCast', r)}*N{r}*Summary!$B${R_BAPS}"
            boss_expr, normal_expr = boss_normal_dps_split_exprs(
                prefix, IB("monster_type"), boss_dmg_pct_r, normal_dmg_pct_r,
                S("NormalMonsterTargets", r), IB("max_enemies_hit"),
            )
            ws.cell(row=r, column=19, value=f'={boss_expr}')
            ws.cell(row=r, column=21, value=f'={normal_expr}')
        elif key == "METEOR_PROC":
            # No cooldown of its own — steady-state proc rate from the combined cast rate of every
            # triggering attack (Summary!B{METEOR_PROC_RATE_ROW}), per this row's Note. H{r} is
            # reused as the per-attack proc chance (already 1-(1-ProcChance%/100)^RollsPerCast).
            prefix = f'{meteor_proc_rate_main}*N{r}'
            boss_expr, normal_expr = boss_normal_dps_split_exprs(
                prefix, IB("monster_type"), boss_dmg_pct_r, normal_dmg_pct_r,
                S("NormalMonsterTargets", r), IB("max_enemies_hit"),
            )
            ws.cell(row=r, column=19, value=f'=IF(C{r},{boss_expr},0)')
            ws.cell(row=r, column=21, value=f'=IF(C{r},{normal_expr},0)')
        elif key == "FLAME_HAZE_DOT":
            # Same H*N*rate pattern as every other DoT (rate = exact-duration-aware G*Q
            # equivalent), plus the level-126 stacking multiplier (kept rate-based per the user —
            # no exact-duration treatment for that one).
            prefix = f'H{r}*N{r}*{rate_r}*{flame_haze_dot_multiplier_main}'
            boss_expr, normal_expr = boss_normal_dps_split_exprs(
                prefix, IB("monster_type"), boss_dmg_pct_r, normal_dmg_pct_r,
                S("NormalMonsterTargets", r), IB("max_enemies_hit"),
            )
            ws.cell(row=r, column=19, value=f'=IF(C{r},{boss_expr},0)')
            ws.cell(row=r, column=21, value=f'=IF(C{r},{normal_expr},0)')
        elif key == "IFRIT":
            # Same H*N*rate pattern as every other cooldown skill, plus the level-130
            # per-burn-stack damage multiplier (kept rate-based per the user).
            prefix = f'H{r}*N{r}*{rate_r}*(1+IF({IB("level")}>=130,0.2*{flame_haze_total_stacks_main},0))'
            boss_expr, normal_expr = boss_normal_dps_split_exprs(
                prefix, IB("monster_type"), boss_dmg_pct_r, normal_dmg_pct_r,
                S("NormalMonsterTargets", r), IB("max_enemies_hit"),
            )
            ws.cell(row=r, column=19, value=f'=IF(C{r},{boss_expr},0)')
            ws.cell(row=r, column=21, value=f'=IF(C{r},{normal_expr},0)')
        elif key in DAMAGE_ROW_KEYS:
            # H*N*rate instead of G*H*N/Cooldown — rate is the exact-duration-aware G*Q
            # equivalent (steady-state EffectiveHits*InvCooldown, or exact total hits/duration).
            prefix = f'H{r}*N{r}*{rate_r}'
            boss_expr, normal_expr = boss_normal_dps_split_exprs(
                prefix, IB("monster_type"), boss_dmg_pct_r, normal_dmg_pct_r,
                S("NormalMonsterTargets", r), IB("max_enemies_hit"),
            )
            ws.cell(row=r, column=19, value=f'=IF(C{r},{boss_expr},0)')
            ws.cell(row=r, column=21, value=f'=IF(C{r},{normal_expr},0)')
        else:
            ws.cell(row=r, column=19, value=0)
            ws.cell(row=r, column=21, value=0)

        # DPS (blended) — a plain reference to the boss-only/normal-only split above, time-weighted
        # by Inputs!normal_weight_frac. Numerically identical to computing the old single combined
        # formula directly (w=0/1 already collapse exactly to the boss-only/normal-only branch, and
        # both branches are already individually pvp-correct) — kept as two named columns instead
        # of one inline formula so Sensitivity can independently track each branch's own relative
        # growth (see build_stat_block / build_sensitivity_sheet), rather than blending dollars.
        ws.cell(row=r, column=15, value=f'=(1-{IB("normal_weight_frac")})*S{r}+{IB("normal_weight_frac")}*U{r}')

        ws.cell(row=r, column=16, value=f'=IF(Summary!$B${R_TOTAL}=0,0,O{r}/Summary!$B${R_TOTAL})')

        # Safe per-row reciprocal cooldown, used by every SUMPRODUCT-based cast-rate formula
        # (Summary!B9/B14 and every Sensitivity block) instead of nesting IFERROR(1/<range>)
        # directly inside SUMPRODUCT — Excel's dynamic-array compatibility layer silently
        # inserts an implicit-intersection "@" in front of a range passed to IFERROR/IF when
        # the workbook was authored by an external tool (like openpyxl) rather than typed
        # directly into Excel, collapsing the range to one cell and breaking the whole term.
        # A single-cell IFERROR call here isn't a range argument, so it isn't affected.
        # Also where the PvP fight-duration cap lives: divides by the shorter of the skill's
        # own cooldown or PVP_FIGHT_DURATION when Inputs!monster_type="pvp".
        ws.cell(row=r, column=17, value=f'=IFERROR(1/{eff_cd_r},0)')

        # CastsInFight (fixed-duration mode only) — exact cast count within Inputs!fight_duration,
        # 0 when the mode is off or this row has no real cooldown to count casts against (must
        # stay numeric, not blank text, since it's summed alongside numbers in SUMPRODUCT below).
        # Reuses available_duration_r (defined above, alongside eff_cd_r) so the cast count here
        # and rate_r's last-cast truncation always agree on which duration was actually used.
        if ROW_HAS_COOLDOWN[key]:
            casts_formula = guarded_casts_expr(available_duration_r, eff_cd_r)
            ws.cell(row=r, column=18, value=f'=IF({fixed_duration_active_main},{casts_formula},0)')
        else:
            ws.cell(row=r, column=18, value=0)

    ws.cell(row=1, column=17, value="InvCooldown")
    ws.cell(row=1, column=18, value="CastsInFight")
    ws.cell(row=1, column=19, value="BossOnlyDPS")
    ws.cell(row=1, column=21, value="NormalOnlyDPS")

    widths = [22, 26, 10, 12, 9, 15, 13, 14, 17, 13, 15, 12, 12, 17, 12, 10]
    for i, w in enumerate(widths):
        ws.column_dimensions[get_column_letter(i + 1)].width = w
    ws.freeze_panes = "C2"
    return ws


def build_summary_sheet(wb):
    ws = wb.create_sheet("Summary")
    ws["A1"] = "Fire/Poison Arch Mage — DPS Summary"
    ws["A1"].font = Font(bold=True, size=14)

    ws.cell(row=DERIVED_HEADER_ROW, column=1, value="Derived Values (read-only, computed from Inputs)").font = SECTION_FONT
    ws.cell(row=D_ATTACK, column=1, value="ATTACK (= Flat ATTACK x (1+ATTACK%/100))")
    ws.cell(row=D_ATTACK, column=2, value=f'={IB("flat_attack")}*(1+{IB("attack_pct")}/100)')

    ws.cell(row=D_STAT_DAMAGE, column=1, value="STAT_DAMAGE % (= 1% of total INT + 0.25% of LUK)")
    ws.cell(
        row=D_STAT_DAMAGE, column=2,
        value=f'=({IB("flat_int")}*(1+{IB("int_pct")}/100))*0.01+{IB("luk")}*0.0025'
    )

    ws.cell(row=D_BASIC_INPUT_LEVEL, column=1, value="Basic Attack Input Level (4th job formula)")
    ws.cell(
        row=D_BASIC_INPUT_LEVEL, column=2,
        value=f'=MAX(0,({IB("level")}-100)*3)+{IB("skill_lvl_4th")}+{IB("skill_lvl_all")}'
    )
    ws.cell(row=D_BASIC_FACTOR, column=1, value="Basic Attack Factor (factorIndex 21)")
    ws.cell(
        row=D_BASIC_FACTOR, column=2,
        value=f'=INDEX(FactorTable!$B$2:$Y$301, MATCH(ROUND(MIN(300,MAX(1,{IB("basic_input_level")})),0), '
              f'FactorTable!$A$2:$A$301,0), 22)'
    )
    ws.cell(row=D_SKILL_COEFFICIENT, column=1, value="SKILL_COEFFICIENT — Basic Attack base coefficient % (before Skill Mastery)")
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

    r_bm, r_ed_mult, r_avgbuff, r_asbonus, r_aps, r_castrate, r_baps = (
        R_BM, R_ED_MULT, R_AVGBUFF, R_ASBONUS, R_APS, R_CASTRATE, R_BAPS,
    )
    r_total, r_basic = R_TOTAL, R_BASIC

    ws.cell(row=r_bm, column=1, value="Burning Magic Multiplier")
    ws.cell(row=r_bm, column=2, value=f'=1+(Calc!F{ROW["BURNING_MAGIC"]}*{S("Stacks", ROW["BURNING_MAGIC"])})/100')

    # Treated as always-on, like Burning Magic: at 50% chance per qualifying hit and a 7s
    # duration, it's reapplied well before expiring, so uptime is assumed to be 100%.
    ed = ROW["ELEMENTAL_DECREASE"]
    ws.cell(row=r_ed_mult, column=1, value="Elemental Decrease Multiplier (always-on)")
    ws.cell(row=r_ed_mult, column=2, value=f'=1+Calc!F{ed}/100')

    med, mg, nf, inf = ROW["MEDITATION"], ROW["MAGIC_GUARD"], ROW["NIMBLE_FEET"], ROW["INFINITY"]
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
        f'=(1+(Calc!F{med}*{buff_uptime(med)}+Calc!F{mg}*{buff_uptime(mg)})/100)'
        f'*IF(Calc!C{inf}=TRUE,(1+Calc!F{inf}*{buff_uptime(inf)}/100),1)'
    ))

    ws.cell(row=r_asbonus, column=1, value="Attack Speed Buff Bonus % (Nimble Feet, averaged)")
    ws.cell(row=r_asbonus, column=2, value=(
        f'=Calc!F{nf}*{buff_uptime(nf)}'
    ))

    ws.cell(row=r_aps, column=1, value="Actions Per Second (Attack Speed combined via diminishing-returns stack, factor 150, then capped)")
    ws.cell(row=r_aps, column=2, value=(
        f'=1+MIN(150,150*(1-(1-{IB("attack_speed")}/150)*(1-B{r_asbonus}/150)))/100'
    ))

    ws.cell(row=r_castrate, column=1, value="Skill + Buff Cast Rate (subtracted from Basic Attack, 1/s)")
    ws.cell(row=r_castrate, column=2, value=(
        f'=IF({fda_main},'
        f'SUMPRODUCT((Skills!{SC["CostsActionSlot"]}2:{SC["CostsActionSlot"]}{LAST_ROW}=TRUE)*'
        f'(Calc!C2:C{LAST_ROW}=TRUE)*Calc!R2:R{LAST_ROW})/{IB("fight_duration")},'
        f'SUMPRODUCT((Skills!{SC["CostsActionSlot"]}2:{SC["CostsActionSlot"]}{LAST_ROW}=TRUE)*'
        f'(Calc!C2:C{LAST_ROW}=TRUE)*Calc!Q2:Q{LAST_ROW}))'
    ))

    ws.cell(row=r_baps, column=1, value="Basic Attacks Per Second")
    ws.cell(row=r_baps, column=2, value=f'=MAX(0,B{r_aps}-B{r_castrate})')

    ws.cell(row=METEOR_PROC_RATE_ROW, column=1, value="Meteor Proc — triggering attacks' combined cast rate, incl. Basic Attack (1/s)")
    mp_col = SC["TriggersMeteorProc"]
    mptpc_col = SC["MeteorProcTriggersPerCast"]
    ws.cell(row=METEOR_PROC_RATE_ROW, column=2, value=(
        f'=IF({fda_main},'
        f'SUMPRODUCT((Skills!{mp_col}2:{mp_col}{LAST_ROW}=TRUE)*'
        f'(Calc!C2:C{LAST_ROW}=TRUE)*Calc!R2:R{LAST_ROW}*Skills!{mptpc_col}2:{mptpc_col}{LAST_ROW})/{IB("fight_duration")},'
        f'SUMPRODUCT((Skills!{mp_col}2:{mp_col}{LAST_ROW}=TRUE)*'
        f'(Calc!C2:C{LAST_ROW}=TRUE)*Calc!Q2:Q{LAST_ROW}*Skills!{mptpc_col}2:{mptpc_col}{LAST_ROW}))'
        f'+B{r_baps}'
    ))

    ws.cell(row=R_STARTUP_TIME, column=1, value=(
        "Buff-Casting Startup Delay (s, before first damage-skill cast; fixed-duration only)"
    ))
    ws.cell(row=R_STARTUP_TIME, column=2, value="=" + buff_cast_startup_time_expr(
        fda_main, SC["BuffDuration(s)"], SC["CostsActionSlot"], f"Calc!C2:C{LAST_ROW}",
        f"B{r_aps}", LAST_ROW,
    ))

    ws.cell(row=r_total, column=1, value="TOTAL DPS").font = Font(bold=True, size=13)
    ws.cell(row=r_total, column=2, value=f"=SUM(Calc!O2:O{LAST_ROW})").font = Font(bold=True, size=13)

    # Boss-only/Normal-only Total DPS — the baseline denominators for Sensitivity's time-weighted
    # (not dollar-weighted) marginal-value blend, see build_sensitivity_sheet. Not shown as "the"
    # DPS of anything real (nobody fights pure boss-or-normal in Breakthrough); purely a reference
    # point so a swept stat's relative growth in each branch can be measured independently of how
    # many targets that branch happens to hit.
    ws.cell(row=R_BOSS_ONLY_TOTAL, column=1, value="Boss-Only Total DPS (Sensitivity baseline)")
    ws.cell(row=R_BOSS_ONLY_TOTAL, column=2, value=f"=SUM(Calc!S2:S{LAST_ROW})")
    ws.cell(row=R_NORMAL_ONLY_TOTAL, column=1, value="Normal-Only Total DPS (Sensitivity baseline)")
    ws.cell(row=R_NORMAL_ONLY_TOTAL, column=2, value=f"=SUM(Calc!U2:U{LAST_ROW})")

    ws.cell(row=r_basic, column=1, value="Basic Attack DPS")
    ws.cell(row=r_basic, column=2, value=f"=Calc!O{ROW['BASIC_ATTACK']}")

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

    ws.column_dimensions["A"].width = 55
    ws.column_dimensions["B"].width = 16
    ws.column_dimensions["C"].width = 12
    return ws



# ---------------------------------------------------------------------------
# Sensitivity sheet: marginal DPS from bumping each Inputs stat by +1 (one
# percentage point / one skill level / one flat point), with Attack Speed and
# Def Pen combined via the diminishing-returns formula instead of a flat add
# (mirrors StatCalculationService.addDiminishingReturnStatCore in the TS app:
# new = (1 - (1-old/factor)*(1-inc/factor)) * factor).
#
# Each swept stat gets its own full, self-contained copy of the Calc+Summary
# formula pipeline (same formulas as build_calc_sheet/build_summary_sheet,
# just same-sheet refs instead of cross-sheet, and one Inputs value swapped
# for an override expression) so its Total DPS is guaranteed correct by
# construction rather than by a separately-reasoned shortcut formula.
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

# Absolute CDR values (seconds) swept by the Sensitivity sheet's CDR Milestone Sweep section
# (see build_sensitivity_sheet) — chosen by the user to cover the range where fixed-duration
# skill cast counts are likely to cross an INT()-floor threshold and jump.
CDR_SWEEP_VALUES = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]

# Row on the Sensitivity results table (header at SENSITIVITY_HEADER_ROW) holding each swept
# stat's own row — used by the PotentialCubes sheet to pull each stat's "DPS gain per +1 unit"
# (column H, a linear approximation per the user's explicit delta-method instruction) without
# re-deriving it. Must stay in sync with build_sensitivity_sheet's own row assignment below.
SENSITIVITY_HEADER_ROW = 4
SENSITIVITY_ROW_FOR = {key: SENSITIVITY_HEADER_ROW + 1 + idx for idx, (key, _, _) in enumerate(STAT_SWEEP)}

# Maps every stat name that can appear on a potential line (both the generic 16-stat pool and
# the 4 hand-added slot-specific stats, plus the 2 new rollable stats introduced this session)
# to its Sensitivity-sheet sweep key. Stats not in this map (Str/Dex/Luk flat & %, Defense %,
# Max HP %, Max MP %) have no combat impact for this INT class and get a hardcoded 0 instead.
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
        # This roll's raw "value" is a per-level coefficient (e.g. 5 INT per level), not a flat
        # amount — the actual flat INT granted is coefficient*CharacterLevel (confirmed by the
        # user: level 115 x 5/level = 565 flat INT). Rather than needing a live formula in the
        # Value column, fold the level scaling into DPSPerUnit instead: Flat INT's own DPS-per-
        # unit times the live character level, so Value*DPSPerUnit still gives the right total.
        return f'=Sensitivity!H{SENSITIVITY_ROW_FOR["flat_int"]}*{IB("level")}'
    if stat_name == "Main Stat % per 4 Levels":
        # Same pattern as Main Stat Per Level above, but stepped every 4 whole character levels,
        # not continuous (confirmed by the user) — the granted Int % is coefficient*FLOOR(level/4),
        # so DPSPerUnit folds Int %'s own DPS-per-unit times FLOOR(level/4) instead of level/4.
        return f'=Sensitivity!H{SENSITIVITY_ROW_FOR["int_pct"]}*INT({IB("level")}/4)'
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


# Vertical span of one Sensitivity block: label row + header row + one row per Skills-sheet
# row (2..LAST_ROW) + blank + 11 summary rows (bm/ed/avgbuff/asbonus/aps/castrate/baps/meteor/
# startup/boss_total/normal_total, +1 blank) + total, + 2 blank spacer rows before the next block.
# Derived from LAST_ROW so it can't silently drift out of sync if more Skills rows are ever added
# (as happened once already).
BLOCK_HEIGHT = LAST_ROW + 16
# Derived from the Results table's own size (SENSITIVITY_HEADER_ROW + 1 row per STAT_SWEEP
# entry) plus a small buffer, rather than a hardcoded row number — a hardcoded BLOCK_START
# previously drifted out of sync when this session's 3 new STAT_SWEEP entries grew the
# Results table past row 26, silently corrupting the first block (Flat INT)'s calc rows with
# the *last* 3 stats' results-row writes, since both landed on rows 27-29.
BLOCK_START = SENSITIVITY_HEADER_ROW + len(STAT_SWEEP) + 3


def override_expr_for(kind, key):
    base = IB(key)
    if kind == "dr150":
        return f'((1-(1-{base}/150)*(1-1/150))*150)'
    if kind == "dr100":
        return f'((1-(1-{base}/100)*(1-1/100))*100)'
    if kind == "mult":
        # Mirrors addMultiplicativeStatCore in stat-calculation-service.ts: a new Final Damage
        # source combines with the existing total multiplicatively, not additively, so
        # (1+new/100)/(1+old/100) is always exactly 1.01 regardless of the old value.
        return f'((((1+{base}/100)*(1.01))-1)*100)'
    return f'({base}+1)'


def make_ib(override_key, override_expr):
    # "attack" and "stat_damage" are themselves derived from other Inputs cells (see the
    # Inputs-sheet formulas for rows IN["attack"]/IN["stat_damage"]) — every block must
    # recompute them from their sub-components through `ib` too, or overriding
    # flat_attack/attack_pct/flat_int/int_pct/luk would silently have no effect on a
    # block's DPS (the J/K-column formulas only ever call ib("attack")/ib("stat_damage")).
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
    """
    Writes one full local Calc+Summary DPS pipeline into `ws` starting at
    `base_row` (same layout/formulas as build_calc_sheet + the Total-DPS part
    of build_summary_sheet, but every cross-sheet ref becomes a same-sheet ref
    so this block is self-contained). `ib(key)` resolves an Inputs-sheet
    reference, substituting `override_expr` for `stat_key`. Returns the cell
    reference (e.g. "B45") holding this block's Total DPS.
    """
    row_label = base_row
    row_header = base_row + 1
    calc_start = base_row + 2
    row_of = {key: calc_start + (r - 2) for key, r in ROW.items()}
    calc_end = calc_start + (LAST_ROW - 2)

    s_bm = calc_end + 2
    s_ed = calc_end + 3
    s_avgbuff = calc_end + 4
    s_asbonus = calc_end + 5
    s_aps = calc_end + 6
    s_castrate = calc_end + 7
    s_baps = calc_end + 8
    s_meteor = calc_end + 9
    s_startup = calc_end + 10
    s_boss_total = calc_end + 11
    s_normal_total = calc_end + 12
    s_total = calc_end + 13
    bm_ref, ed_ref, avgbuff_ref = f"B{s_bm}", f"B{s_ed}", f"B{s_avgbuff}"
    asbonus_ref, aps_ref, castrate_ref = f"B{s_asbonus}", f"B{s_aps}", f"B{s_castrate}"
    baps_ref, meteor_ref, total_ref = f"B{s_baps}", f"B{s_meteor}", f"B{s_total}"
    startup_ref = f"B{s_startup}"
    boss_total_ref, normal_total_ref = f"B{s_boss_total}", f"B{s_normal_total}"

    # Magic Critical / Spell Mastery: already baked into Inputs!CRIT_RATE%/CRIT_DAMAGE%/MIN_DAMAGE%
    # at the current skill level, so only the marginal delta (this block's own F value, which
    # reflects any active override, minus the same row's F on the main, un-overridden Calc sheet)
    # needs to be added — for every block except the one sweeping the relevant skill-level-bonus,
    # that delta is identically 0 since nothing overrides the level in question.
    crit_rate_delta = f'(F{row_of["MAGIC_CRITICAL_RATE"]}-Calc!F{ROW["MAGIC_CRITICAL_RATE"]})'
    crit_dmg_delta = f'(F{row_of["MAGIC_CRITICAL_DAMAGE"]}-Calc!F{ROW["MAGIC_CRITICAL_DAMAGE"]})'
    min_dmg_delta = f'(F{row_of["SPELL_MASTERY"]}-Calc!F{ROW["SPELL_MASTERY"]})'

    # Flat ATTACK already includes the character's current INT/LUK-derived attack (1 total INT =
    # 1 ATTACK, 1 LUK = 0.25 ATTACK, added into the flat pool before ATTACK% applies) — same
    # "already baked in, only the marginal delta matters" pattern as Magic Critical/Spell Mastery
    # above, just computed directly from Inputs instead of a Skills-sheet row. Identically 0 for
    # every block except the ones sweeping flat_int/int_pct/luk.
    mainstat_attack_delta = (
        f'((({ib("flat_int")}*(1+{ib("int_pct")}/100))-({IB("flat_int")}*(1+{IB("int_pct")}/100)))'
        f'+0.25*({ib("luk")}-{IB("luk")}))'
    )

    # Level 126/130 Flame Haze burn-stacking mastery — block-local mirror of the same computation
    # in build_calc_sheet (local H/V columns and baps_ref/meteor_ref instead of cross-sheet refs).
    meteor_proc_rate_block = meteor_proc_rate_expr(
        f'H{row_of["METEOR_PROC"]}', S("ICD(s)", ROW["METEOR_PROC"]), meteor_ref,
    )
    flame_haze_extra_rate_block = flame_haze_extra_rate_expr(
        ib("level"), baps_ref, f'Q{row_of["METEOR_SHOWER_BURST"]}', meteor_proc_rate_block, f'Q{row_of["IFRIT"]}',
    )
    flame_haze_dot_multiplier_block = flame_haze_dot_stack_multiplier_expr(
        flame_haze_extra_rate_block, S("Cooldown(s)", ROW["FLAME_HAZE_BURST"]),
    )
    flame_haze_total_stacks_block = flame_haze_total_stacks_expr(
        flame_haze_extra_rate_block, S("ActiveWindow(s)", ROW["FLAME_HAZE_DOT"]), S("Cooldown(s)", ROW["FLAME_HAZE_BURST"]),
    )

    # Fixed fight-duration mode — block-local mirror of the same computation in build_calc_sheet.
    fda_block = fixed_duration_active_expr(ib("monster_type"), ib("fight_duration"))


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

        # Local override-aware effective cooldown — reused below for both InvCooldown (V) and
        # CastsInFight (R), same "must be recomputed per block" reasoning as the V column always
        # needed (sweeping skill_cooldown_decrease itself needs this to reflect the override).
        eff_cd_row = effective_cooldown_expr(
            ib("monster_type"), S("Cooldown(s)", r), ib("skill_cooldown_decrease"),
            S("CostsActionSlot", CDR_COSTS_ACTION_ROW[key]),
        )
        # Block-local mirror of available_duration_r (main sheet) — must use this block's own
        # startup_ref, not the main sheet's, since sweeping skill_cooldown_decrease/attack_speed/
        # etc. changes it.
        if key in BUFF_ROW_KEYS:
            available_duration_row = ib("fight_duration")
        else:
            available_duration_row = f'MAX(0,{ib("fight_duration")}-{startup_ref})'
        rate_row = rate_or_exact_hits_expr(
            fda_block, f"R{row}", S("HitsPerCast", r), S("ICD(s)", r), S("ActiveWindow(s)", r),
            eff_cd_row, available_duration_row, ib("fight_duration"), f"G{row}*Q{row}",
        )

        if key == "BASIC_ATTACK":
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

        # EffectiveHits/ProcProbability depend only on Skills-sheet cooldown/ICD/etc, never on
        # Inputs, so they're identical to the main Calc sheet's — just reuse those cells.
        ws.cell(row=row, column=7, value=f"=Calc!G{r}")
        ws.cell(row=row, column=8, value=f"=Calc!H{r}")
        ws.cell(row=row, column=9, value=(
            f'=IF({S("MapleHeroBase(tenths%)", r)}<>"",'
            f'1+({S("MapleHeroBase(tenths%)", r)}/10)*({maple_factor_cell}/1000)/100,1)'
        ))

        if key == "BASIC_ATTACK" or key in DAMAGE_ROW_KEYS:
            ws.cell(row=row, column=10, value=(
                f'=({ib("attack")}+{mainstat_attack_delta}*(1+{ib("attack_pct")}/100))*(F{row}/100)'
            ))
            ws.cell(row=row, column=11, value=(
                f'=J{row}*(1+{ib("stat_damage")}/100)*(1+{ib("damage")}/100)'
                f'*(1+{ib("damage_amp")}/100)'
                f'*(5000/(6000+{ib("monster_defense")}*(1-{ib("def_pen")}/100)))'
                f'*(1+{ib("final_damage")}/100)*(1+F{row_of["ELEMENT_AMPLIFICATION"]}/100)'
                f'*(1+IF({ib("level")}>=120,F{row_of["ARCANE_AIM"]},0)/100)^5'
                f'*(1+(IF({S("Key", r)}="BASIC_ATTACK",{ib("basic_attack_damage")},'
                f'{ib("skill_damage")}+IF({ib("level")}>=125,F{row_of["FERVENT_DRAIN"]}*5,0)))/100)'
                f'*({bm_ref}*{ed_ref}*{avgbuff_ref}*I{row})'
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

        boss_dmg_pct_row = f'{ib("boss_damage")}+{S("MasteryBossDamage%", r)}'
        normal_dmg_pct_row = f'{ib("normal_damage")}+{S("MasteryNormalDamage%", r)}'

        if key == "BASIC_ATTACK":
            # Local override-aware target count (6 + Inputs, not Skills!NormalMonsterTargets'
            # own formula, which always reads the global Inputs cell and wouldn't reflect this
            # block's override when "basic_attack_target_increase" itself is the swept stat).
            basic_targets_expr = f'(6+{ib("basic_attack_target_increase")}+IF({ib("level")}>=136,1,0))'
            prefix = f"{S('HitsPerCast', r)}*N{row}*{baps_ref}"
            boss_expr, normal_expr = boss_normal_dps_split_exprs(
                prefix, ib("monster_type"), boss_dmg_pct_row, normal_dmg_pct_row,
                basic_targets_expr, ib("max_enemies_hit"),
            )
            ws.cell(row=row, column=19, value=f'={boss_expr}')
            ws.cell(row=row, column=21, value=f'={normal_expr}')
        elif key == "METEOR_PROC":
            prefix = f'{meteor_proc_rate_block}*N{row}'
            boss_expr, normal_expr = boss_normal_dps_split_exprs(
                prefix, ib("monster_type"), boss_dmg_pct_row, normal_dmg_pct_row,
                S("NormalMonsterTargets", r), ib("max_enemies_hit"),
            )
            ws.cell(row=row, column=19, value=f'=IF(C{row},{boss_expr},0)')
            ws.cell(row=row, column=21, value=f'=IF(C{row},{normal_expr},0)')
        elif key == "FLAME_HAZE_DOT":
            prefix = f'H{row}*N{row}*{rate_row}*{flame_haze_dot_multiplier_block}'
            boss_expr, normal_expr = boss_normal_dps_split_exprs(
                prefix, ib("monster_type"), boss_dmg_pct_row, normal_dmg_pct_row,
                S("NormalMonsterTargets", r), ib("max_enemies_hit"),
            )
            ws.cell(row=row, column=19, value=f'=IF(C{row},{boss_expr},0)')
            ws.cell(row=row, column=21, value=f'=IF(C{row},{normal_expr},0)')
        elif key == "IFRIT":
            prefix = f'H{row}*N{row}*{rate_row}*(1+IF({ib("level")}>=130,0.2*{flame_haze_total_stacks_block},0))'
            boss_expr, normal_expr = boss_normal_dps_split_exprs(
                prefix, ib("monster_type"), boss_dmg_pct_row, normal_dmg_pct_row,
                S("NormalMonsterTargets", r), ib("max_enemies_hit"),
            )
            ws.cell(row=row, column=19, value=f'=IF(C{row},{boss_expr},0)')
            ws.cell(row=row, column=21, value=f'=IF(C{row},{normal_expr},0)')
        elif key in DAMAGE_ROW_KEYS:
            prefix = f'H{row}*N{row}*{rate_row}'
            boss_expr, normal_expr = boss_normal_dps_split_exprs(
                prefix, ib("monster_type"), boss_dmg_pct_row, normal_dmg_pct_row,
                S("NormalMonsterTargets", r), ib("max_enemies_hit"),
            )
            ws.cell(row=row, column=19, value=f'=IF(C{row},{boss_expr},0)')
            ws.cell(row=row, column=21, value=f'=IF(C{row},{normal_expr},0)')
        else:
            ws.cell(row=row, column=19, value=0)
            ws.cell(row=row, column=21, value=0)

        ws.cell(row=row, column=15, value=f'=(1-{ib("normal_weight_frac")})*S{row}+{ib("normal_weight_frac")}*U{row}')

        ws.cell(row=row, column=16, value=f'=IF({total_ref}=0,0,O{row}/{total_ref})')

        # Local override-aware InvCooldown (mirrors Calc!Q on the main sheet, column 17) — must
        # be recomputed per block rather than shared, since sweeping "skill_cooldown_decrease"
        # itself needs this to reflect the active override, which a shared Calc!Q never would.
        ws.cell(row=row, column=17, value=f'=IFERROR(1/{eff_cd_row},0)')

        # CastsInFight (fixed-duration mode only) — block-local mirror of Calc!R on the main
        # sheet, but in column S (19) here, not R (18) — R is already used by this block's own
        # maple_lvl_cell/maple_factor_cell helper cells at the first two skill rows. Reuses
        # available_duration_row (defined above) so this and rate_row's last-cast truncation
        # always agree on which duration was actually used.
        if ROW_HAS_COOLDOWN[key]:
            casts_formula_block = guarded_casts_expr(available_duration_row, eff_cd_row)
            ws.cell(row=row, column=18, value=f'=IF({fda_block},{casts_formula_block},0)')
        else:
            ws.cell(row=row, column=18, value=0)

    ws.cell(row=s_bm, column=1, value="Burning Magic Multiplier")
    ws.cell(row=s_bm, column=2, value=f'=1+(F{row_of["BURNING_MAGIC"]}*{S("Stacks", ROW["BURNING_MAGIC"])})/100')

    ws.cell(row=s_ed, column=1, value="Elemental Decrease Multiplier (always-on)")
    ws.cell(row=s_ed, column=2, value=f'=1+F{row_of["ELEMENTAL_DECREASE"]}/100')

    med, mg, nf, inf = row_of["MEDITATION"], row_of["MAGIC_GUARD"], row_of["NIMBLE_FEET"], row_of["INFINITY"]
    bdi_block = bdi_with_buff_mastery_expr(ib("buff_duration_increase_pct"), ib("level"), f'F{row_of["BUFF_MASTERY"]}')

    def buff_uptime_block(local_row, skills_row):
        return uptime_fraction_or_exact_expr(
            fda_block, f'R{local_row}', ib("monster_type"), S("BuffDuration(s)", skills_row),
            S("Cooldown(s)", skills_row), bdi_block, ib("fight_duration"),
        )

    ws.cell(row=s_avgbuff, column=1, value="Average Buff Multiplier (Magic Guard + Meditation, summed; then Infinity)")
    ws.cell(row=s_avgbuff, column=2, value=(
        f'=(1+(F{med}*{buff_uptime_block(med, ROW["MEDITATION"])}+F{mg}*{buff_uptime_block(mg, ROW["MAGIC_GUARD"])})/100)'
        f'*IF(C{inf}=TRUE,(1+F{inf}*{buff_uptime_block(inf, ROW["INFINITY"])}/100),1)'
    ))

    ws.cell(row=s_asbonus, column=1, value="Attack Speed Buff Bonus % (Nimble Feet, averaged)")
    ws.cell(row=s_asbonus, column=2, value=(
        f'=F{nf}*{buff_uptime_block(nf, ROW["NIMBLE_FEET"])}'
    ))

    ws.cell(row=s_aps, column=1, value="Actions Per Second")
    ws.cell(row=s_aps, column=2, value=f'=1+MIN(150,150*(1-(1-{ib("attack_speed")}/150)*(1-{asbonus_ref}/150)))/100')

    ws.cell(row=s_castrate, column=1, value="Skill + Buff Cast Rate")
    ws.cell(row=s_castrate, column=2, value=(
        f'=IF({fda_block},'
        f'SUMPRODUCT((Skills!{SC["CostsActionSlot"]}2:{SC["CostsActionSlot"]}{LAST_ROW}=TRUE)*'
        f'(C{calc_start}:C{calc_end}=TRUE)*R{calc_start}:R{calc_end})/{ib("fight_duration")},'
        f'SUMPRODUCT((Skills!{SC["CostsActionSlot"]}2:{SC["CostsActionSlot"]}{LAST_ROW}=TRUE)*'
        f'(C{calc_start}:C{calc_end}=TRUE)*Q{calc_start}:Q{calc_end}))'
    ))

    ws.cell(row=s_baps, column=1, value="Basic Attacks Per Second")
    ws.cell(row=s_baps, column=2, value=f'=MAX(0,{aps_ref}-{castrate_ref})')

    ws.cell(row=s_meteor, column=1, value="Meteor Proc — combined trigger cast rate")
    ws.cell(row=s_meteor, column=2, value=(
        f'=IF({fda_block},'
        f'SUMPRODUCT((Skills!{SC["TriggersMeteorProc"]}2:{SC["TriggersMeteorProc"]}{LAST_ROW}=TRUE)*'
        f'(C{calc_start}:C{calc_end}=TRUE)*R{calc_start}:R{calc_end}*'
        f'Skills!{SC["MeteorProcTriggersPerCast"]}2:{SC["MeteorProcTriggersPerCast"]}{LAST_ROW})/{ib("fight_duration")},'
        f'SUMPRODUCT((Skills!{SC["TriggersMeteorProc"]}2:{SC["TriggersMeteorProc"]}{LAST_ROW}=TRUE)*'
        f'(C{calc_start}:C{calc_end}=TRUE)*Q{calc_start}:Q{calc_end}*'
        f'Skills!{SC["MeteorProcTriggersPerCast"]}2:{SC["MeteorProcTriggersPerCast"]}{LAST_ROW}))'
        f'+{baps_ref}'
    ))

    ws.cell(row=s_startup, column=1, value="Buff-Casting Startup Delay (s, fixed-duration only)")
    ws.cell(row=s_startup, column=2, value="=" + buff_cast_startup_time_expr(
        fda_block, SC["BuffDuration(s)"], SC["CostsActionSlot"], f"C{calc_start}:C{calc_end}",
        aps_ref, LAST_ROW,
    ))

    ws.cell(row=s_boss_total, column=1, value="Boss-Only Total DPS (this block's swept value)")
    ws.cell(row=s_boss_total, column=2, value=f"=SUM(S{calc_start}:S{calc_end})")
    ws.cell(row=s_normal_total, column=1, value="Normal-Only Total DPS (this block's swept value)")
    ws.cell(row=s_normal_total, column=2, value=f"=SUM(U{calc_start}:U{calc_end})")

    ws.cell(row=s_total, column=1, value="TOTAL DPS").font = LABEL_FONT
    ws.cell(row=s_total, column=2, value=f"=SUM(O{calc_start}:O{calc_end})").font = LABEL_FONT

    return total_ref, boss_total_ref, normal_total_ref


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
        total_ref, boss_total_ref, normal_total_ref = build_stat_block(ws, base_row, ib, key, label, override_expr)

        row = header_row + 1 + idx
        ws.cell(row=row, column=1, value=label)
        ws.cell(row=row, column=3, value=kind)
        ws.cell(row=row, column=4, value=f"={IB(key)}")
        ws.cell(row=row, column=5, value=f"={override_expr}")
        ws.cell(row=row, column=6, value=f"=Summary!$B${R_TOTAL}")
        ws.cell(row=row, column=7, value=f"={total_ref}")
        # DPS Gain/% Gain are time-weighted (not dollar-weighted) across the boss/normal branches:
        # each branch's own RELATIVE growth (new/baseline) is measured independently, then blended
        # by Inputs!normal_weight_frac — not the raw dollar totals, which would let a stat's
        # reported value be dominated by whichever branch happens to hit more targets, regardless
        # of how much combat time is actually spent there (confirmed bug, fixed this session).
        # Ratios collapse to a plain 1:1 blend correctly at w=0/1 (pure boss/normal/PvP), matching
        # today's numbers exactly there — only interior Breakthrough/Hero Dungeon weights change.
        boss_ratio = f'IFERROR({boss_total_ref}/Summary!$B${R_BOSS_ONLY_TOTAL},1)'
        normal_ratio = f'IFERROR({normal_total_ref}/Summary!$B${R_NORMAL_ONLY_TOTAL},1)'
        weighted_ratio = f'((1-{IB("normal_weight_frac")})*{boss_ratio}+{IB("normal_weight_frac")}*{normal_ratio})'
        ws.cell(row=row, column=8, value=f"=Summary!$B${R_TOTAL}*({weighted_ratio}-1)")
        ws.cell(row=row, column=9, value=f"={weighted_ratio}*100")
        # Units of this stat needed for a full +1% DPS gain, linearly extrapolated from the
        # +1-sized marginal test above: 1 / (percentage-point gain from that +1, i.e. %Gain-100).
        ws.cell(row=row, column=2, value=f'=IFERROR(1/(I{row}-100),"n/a")')

    # Cooldown Reduction Milestone Sweep — CDR's DPS impact is a step function in fixed-duration
    # content (CastsInFight floors via INT()), unlike every other stat's smooth marginal delta
    # above, so a single "+1" test can't show where the jumps are. This sweeps a fixed set of
    # absolute CDR values instead, each with its own full shadow recompute (same build_stat_block
    # machinery as STAT_SWEEP, just an absolute override instead of "current+1"), appended after
    # all STAT_SWEEP blocks so it can't collide with their spacing.
    milestone_section_start = BLOCK_START + len(STAT_SWEEP) * BLOCK_HEIGHT
    milestone_title_row = milestone_section_start
    milestone_header_row = milestone_title_row + 1
    ws.cell(row=milestone_title_row, column=1, value=(
        "Cooldown Reduction Milestone Sweep (absolute CDR seconds, fixed-duration content only)"
    )).font = SECTION_FONT
    milestone_headers = ["CDR (s)", "Total DPS", "DPS Gain (vs prior step)", "% Gain (vs current CDR)"]
    for i, name in enumerate(milestone_headers):
        ws.cell(row=milestone_header_row, column=i + 1, value=name)
    style_header_row(ws, milestone_header_row, len(milestone_headers))

    cdr_blocks_base_row = milestone_header_row + len(CDR_SWEEP_VALUES) + 3
    for i, cdr_value in enumerate(CDR_SWEEP_VALUES):
        base_row = cdr_blocks_base_row + i * BLOCK_HEIGHT
        override_expr = str(cdr_value)
        ib = make_ib("skill_cooldown_decrease", override_expr)
        total_ref, _boss_total_ref, _normal_total_ref = build_stat_block(
            ws, base_row, ib, "skill_cooldown_decrease", f"CDR = {cdr_value}s", override_expr,
        )

        row = milestone_header_row + 1 + i
        ws.cell(row=row, column=1, value=cdr_value)
        ws.cell(row=row, column=2, value=f"={total_ref}")
        ws.cell(row=row, column=3, value=(f"=B{row}-B{row - 1}" if i > 0 else 0))
        ws.cell(row=row, column=4, value=(
            f"=IF(Summary!$B${R_TOTAL}=0,0,(B{row}-Summary!$B${R_TOTAL})/Summary!$B${R_TOTAL}*100)"
        ))

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
    instruction), and the rarity upgrade rates/pity caps. Not meant for manual editing."""
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
    existing = existing or {}
    ws = wb.create_sheet("PotentialCubes")
    ws["A1"] = "Potential Cubes — Current Gear State"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = (
        "Fill in your actual current gear for every slot/potential-type you want EV results for, "
        "then run `python3 tools/potential_cubes_ev.py` — it reads this table plus the live "
        "Sensitivity!H DPS-per-unit values and computes exact 'expected value of the best roll "
        "kept after N rerolls' for all 30 rows (printed + written to a CSV), via a full "
        "line1 x line2 x line3 enumeration per rarity/slot rather than a single-roll average."
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
    """If a previous FP-Mage-DPS-Calculator.xlsx already exists at `path`, read back its
    Inputs values and PotentialCubes current-gear table so regenerating the workbook (e.g. to
    pick up a data/formula change) doesn't clobber the user's real character stats and gear
    state with the hardcoded defaults. Matches PotentialCubes rows by (slot, potential type),
    not row position, so it's robust even if CUBE_SLOTS/POTENTIAL_TYPES order ever changes."""
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
