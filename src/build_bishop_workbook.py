#!/usr/bin/env python3
"""
Generates Bishop-DPS-Calculator.xlsx: a live-formula Excel replica of a Bishop skill-rotation DPS
model, sibling to build_fp_mage_workbook.py / build_night_lord_workbook.py /
build_ice_lightning_mage_workbook.py (see /Users/yaniv/.claude/plans/vectorized-shimmying-pony.md
this was built from). Bishop is INT main stat / LUK sub stat — identical stat identity to
FP-Mage/Ice-Lightning-Mage (no Inputs rename needed).

Sheets: Inputs, FactorTable, Skills, Calc, Summary, Sensitivity, CubeData, PotentialCubes.

IMPORTANT DATA-QUALITY CAVEAT (see the plan's Context section for full justification): unlike
every prior class, Bishop's individual per-skill "Skill Enhancement" wiki pages do not exist yet
(checked under every plausible title) — only each skill's level-1 value is available for ~11
Bishop-specific skills, not a full level-1..200 curve. Those skills' (baseDamage, factorIndex)
values are FLAGGED ASSUMPTIONS (derived from the single level-1 point using a per-skill-type
factorIndex convention: burst/DoT->12, buffs/passives->22, basic attack->21), not the
zero-residual-error reverse-engineering used for every other skill in this project. Each such
row's own Note says so explicitly. Two exceptions get a higher-confidence exception: Big Bang and
Bahamut's level-1 text is word-for-word identical to Ice/Lightning Mage's Chain Lightning /
Elquines, so they reuse those exact (baseDamage, factorIndex) tuples directly.

Key mechanics specific to this kit (see the plan for full derivation/justification):
  - Big Bang (basic attack) requires level 100, same "Unlocked-Gate Bypass" lesson as every prior
    class's basic-attack-equivalent row — its own Calc!O DPS dispatch is gated on Calc!C.
  - Angel Ray - Boss Monster Damage (Mastery Lv.122) is its own standalone proc row (mirrors
    Blizzard - Final Attack's precedent in Ice-Lightning-Mage): triggers on every boss-target
    Angel Ray hit (not a percentage roll — the wiki's own wording is unconditional "when hitting a
    boss monster"), scales with Angel Ray's own skill level per the wiki text.
  - Holy Fountain's Mastery Lv.68 "Boss Monster Damage" (patched 10%->20%, wiki stale) is a
    duty-cycle-averaged self Boss Monster Damage buff tied to Holy Fountain's own (patched 40s->
    30s) cooldown — mirrors Ice-Lightning-Mage's Freezing Breath - Weaken treatment. Holy
    Fountain's own base skill (pure HP recovery) has no Skills row of its own beyond this.
  - Holy Symbol's Mastery Lv.90 "Damage Boost" (+25% Damage% if allies excluding self <=2) is
    ALWAYS TRUE for a solo player, so it becomes an unconditional flat Damage% bonus once
    unlocked — folds into the same Summary R_DAMAGE_BONUS-style slot Ice-Lightning-Mage's Frozen
    Break/Frost Clutch use.
  - Triumph Feather is a genuinely new 2-stage-proc mechanic: a chance/attack to enter a
    "harnessing" window, then a second independent chance/attack (only while harnessing) to
    trigger the real damage proc. Modeled via a steady-state busy-fraction approximation for the
    outer (harnessing) stage, mirroring the queueing-rate approximation FP-Mage's own Meteor Proc
    uses, with the inner proc's own rate nested inside that fraction.
  - Bishop's own Maple Hero targets Triumph Feather with a DIFFERENT mechanic shape than every
    other class's Maple Hero (+50% Final Damage specifically, not a MapleHeroBase-scaled
    "additional damage%" multiplier) — implemented as its own Final-Damage-chain term on that row.
  - Blood of the Divine is an HP-scaling passive; HP isn't tracked anywhere in this calculator, so
    it's modeled assuming permanently 100% HP (steady-state favorable assumption, same tier as
    Ice-Lightning-Mage's always-5-Frost-stacks convention) -> flat Final Damage/Crit Damage/Attack
    Speed bonuses once unlocked, no HP-tracking machinery needed.
  - Heal's "+10% Attack while target HP>=70%" component is likewise modeled always-on (steady-
    state "healthy" assumption).
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
OUT_PATH = REPO / "Bishop" / "Bishop-DPS-Calculator.xlsx"

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
DERIVED_HEADER_ROW = 42
D_ATTACK = 43
D_STAT_DAMAGE = 44
D_BASIC_INPUT_LEVEL = 45
D_BASIC_FACTOR = 46
D_SKILL_COEFFICIENT = 47
D_NORMAL_WEIGHT_FRAC = 48
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

IN = {
    "level": 3,
    "content_type": 4,
    "flat_attack": 7,
    "attack_pct": 8,
    "defense": 9,
    "crit_rate": 11,
    "crit_damage": 12,
    "attack_speed": 13,
    "flat_int": 14,
    "int_pct": 15,
    "luk": 16,
    "damage": 17,
    "damage_amp": 18,
    "basic_attack_damage": 19,
    "skill_damage": 20,
    "def_pen": 21,
    "boss_damage": 22,
    "normal_damage": 23,
    "min_damage": 24,
    "max_damage": 25,
    "final_damage": 26,
    "skill_lvl_1st": 27,
    "skill_lvl_2nd": 28,
    "skill_lvl_3rd": 29,
    "skill_lvl_4th": 30,
    "skill_lvl_all": 31,
    "skill_cooldown_decrease": 34,
    "basic_attack_target_increase": 35,
    "buff_duration_increase_pct": 36,
    "companion_summon_time_increase_pct": 37,
    "chapter": 5,
    "breakthrough_normal_weight_pct": 38,
    "max_enemies_hit": 39,
    "stage": 6,
    "monster_type": 40,
    "breakthrough_stage_index": 41,
    "monster_defense": 42,
    "fight_duration": 43,
    "defense_pct": 10,
}

# Rows computed by formula on the Inputs sheet itself (not user-editable) — see
# build_inputs_sheet's "Computed (do not edit)" block below.
COMPUTED_INPUT_ROWS = {
    IN["monster_type"], IN["breakthrough_stage_index"], IN["monster_defense"], IN["fight_duration"],
}

# These 6 values are computed (not user-entered) and live on the Summary sheet's "Derived Values"
# block instead of cluttering Inputs — see DERIVED_ROW above and build_summary_sheet.


def IB(key):
    if key in DERIVED_ROW:
        return f"Summary!$B${DERIVED_ROW[key]}"
    return f"Inputs!$B${IN[key]}"


def total_defense_expr(ib_fn):
    return f'({ib_fn("defense")}*(1+{ib_fn("defense_pct")}/100))'


def invincible_int_bonus_expr(ib_fn):
    return f'IF({ib_fn("level")}>=35,0.10*{total_defense_expr(ib_fn)},0)'


def build_readme_sheet(wb):
    ws = wb.active
    ws.title = "README"
    ws["A1"] = "Bishop — DPS Calculator: How to Use This Workbook"
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
        "Blood of the Divine's HP-scaling Crit Damage bonus is assumed active at 100% HP "
        "(the best case), since HP fluctuation isn't otherwise modeled.",
        "Crit Rate pushed above 100% (e.g. by cube potential lines) automatically redirects "
        "its stat-value to Crit Damage's own per-unit DPS value on the PotentialCubes sheet, "
        "since excess Crit Rate cannot do anything past 100%.",
        "Buffs (Magic Guard, Heal, Bless, Holy Magic Shell, Advanced Blessing, Infinity) are "
        "modeled at steady-state duty-cycle average uptime, not as an exact moment-to-moment "
        "state machine. Heal's own self-Attack% component is assumed active whenever target "
        "HP >= 70%.",
        "Triumph Feather's two-stage proc and Angel Ray's boss-only proc are modeled as "
        "steady-state average multipliers rather than an exact proc-by-proc simulation.",
        "Content Type (Inputs) picks what you're fighting — Chapter Boss/Breakthrough/PvP/EXP "
        "Dungeon/Equipment Dungeon/Weapon Dungeon/Enhancement Dungeon/Hero Dungeon/World Boss/"
        "Chapter Hunt — and Monster Defense and Fixed Fight Duration are both auto-computed from "
        "it (plus Chapter/Stage for the chapter- and dungeon-based types); PvP still forces its "
        "own fixed 15-second window and uses your own Defense stat as the opponent's Defense "
        "estimate. See README.md's 'Content Type' section for the exact formulas.",
        "Invincible (+10% of your total Defense as INT, once Lv.35 unlocks) IS modeled live — "
        "Defense (flat) and Defense % are their own tracked Inputs, feeding STAT_DAMAGE directly, "
        "with their own Sensitivity marginal-value rows and PotentialCubes Defense % support.",
        "Not modeled (out of scope): crowd control, Accuracy/Evasion/Defense reduction, "
        "movement speed, and Companion Summoning Time.",
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
    ws["A1"] = "Bishop — DPS Calculator Inputs"
    ws["A1"].font = Font(bold=True, size=14)

    rows = [
        ("level", "Character Level", 200),
        ("content_type", "Content Type", "Chapter Boss"),
        ("chapter", "Chapter (used when Content Type is Chapter Boss / Breakthrough / Chapter Hunt)", 28),
        ("stage", "Stage — sub-stage within Chapter for Breakthrough/Chapter Hunt (e.g. the '9' in 28-9), "
                  "or Dungeon Stage number for Weapon/Enhancement/EXP/Equipment/Hero Dungeon; ignored otherwise", 9),
        ("flat_attack", "Flat ATTACK", 10000),
        ("attack_pct", "ATTACK %", 0),
        ("defense", "Defense (flat) — your own DEF stat; Invincible converts 10% of it into INT, "
                    "and PvP assumes the opponent has the same total Defense as you", 0),
        ("defense_pct", "Defense % (Invincible converts total Defense, incl. this %, into INT)", 0),
        ("crit_rate", "CRIT_RATE %", 0),
        ("crit_damage", "CRIT_DAMAGE %", 0),
        ("attack_speed", "ATTACK_SPEED % (base, excludes Nimble Feet/MP Eater/Blood of the Divine)", 0),
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
        ("final_damage", "FINAL_DAMAGE % (base, excludes Infinity/Blood of the Divine)", 0),
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

    ws.cell(row=33, column=1, value="Additional Bonuses").font = SECTION_FONT
    bonus_rows = [
        ("skill_cooldown_decrease", "Skill Cooldown Decrease (seconds, only skills/buffs the character actively casts)", 0),
        ("basic_attack_target_increase", "Basic Attack Target Increase (flat, adds to the 6-target normal-monster base)", 1),
        ("buff_duration_increase_pct", "Buff Duration Increase %", 0),
        ("companion_summon_time_increase_pct", "Companion Summoning Time Increase % (companions not modeled — always 0 DPS impact)", 0),
        ("breakthrough_normal_weight_pct", "Boss/Normal Weight % (used when Content Type is Breakthrough or Hero Dungeon)", 60),
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

    COMPUTED_FILL = PatternFill("solid", fgColor="D9D9D9")
    computed_rows = [
        ("monster_type", "Monster Type (auto-computed from Content Type)", (
            f'=IF({IB("content_type")}="PvP","pvp",'
            f'IF(OR({IB("content_type")}="Breakthrough",{IB("content_type")}="Hero Dungeon"),"breakthrough",'
            f'IF(OR({IB("content_type")}="EXP Dungeon",{IB("content_type")}="Equipment Dungeon",{IB("content_type")}="Chapter Hunt"),"normal",'
            f'"boss")))'
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
            f'({IB("defense")}*(1+{IB("defense_pct")}/100)))))))))'
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
    """SUMPRODUCT(...) fragment WITHOUT the leading '=' — for embedding as a sub-expression."""
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
# Skills sheet schema — identical trimmed layout to build_ice_lightning_mage_workbook.py's own
# (no "Element" column, no Meteor-Proc-style multi-skill trigger columns — nothing in this kit
# needs either).
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

# Row order (2..LAST_ROW) — derived from this list, never hand-numbered.
ROW_ORDER = [
    "BIG_BANG", "MAGIC_GUARD", "HEAL", "BLESS", "ANGEL_RAY", "ANGEL_RAY_BOSS_PROC", "GENESIS",
    "BAHAMUT", "HOLY_FOUNTAIN", "HOLY_MAGIC_SHELL", "HOLY_SYMBOL", "ADVANCED_BLESSING",
    "TRIUMPH_FEATHER", "MAPLE_HERO_BISHOP", "MP_EATER_MP_BOOST", "ELEMENT_AMPLIFICATION",
    "INFINITY", "BLOOD_OF_THE_DIVINE", "MAGIC_ACCELERATION", "SPELL_MASTERY", "HIGH_WISDOM",
    "MAGIC_CRITICAL_RATE", "MAGIC_CRITICAL_DAMAGE", "BUFF_MASTERY", "ARCANE_AIM",
]
ROW = {key: i for i, key in enumerate(ROW_ORDER, start=2)}
LAST_ROW = 1 + len(ROW_ORDER)

# Unlock level for every row, taken from Bishop/Skills' own "Req. Level" column (or the mastery
# table for mastery-only rows) — gated all the way down, matching Ice-Lightning-Mage's thorough
# approach (not FP-Mage's "only gate the late batch" shortcut), since the verification sweep
# tests levels well below 100.
UNLOCK_LEVEL = {
    "BIG_BANG": 100,
    "MAGIC_GUARD": 15,
    "HEAL": 38,
    "BLESS": 40,
    "ANGEL_RAY": 103,
    "ANGEL_RAY_BOSS_PROC": 122,
    "GENESIS": 105,
    "BAHAMUT": 115,
    "HOLY_FOUNTAIN": 66,
    "HOLY_MAGIC_SHELL": 69,
    "HOLY_SYMBOL": 72,
    "ADVANCED_BLESSING": 107,
    "TRIUMPH_FEATHER": 63,
    "MAPLE_HERO_BISHOP": 100,
    "MP_EATER_MP_BOOST": 49,
    "ELEMENT_AMPLIFICATION": 75,
    "INFINITY": 110,
    "BLOOD_OF_THE_DIVINE": 125,
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


# Angel Ray - Boss Monster Damage (Mastery Lv.122) procs only off Angel Ray's own casts (mirrors
# Ice-Lightning-Mage's Blizzard - Final Attack precedent) — shares Angel Ray's own live
# Cooldown(s) cell.
_ANGEL_RAY_BOSS_PROC_COOLDOWN = f"=Skills!{SC['Cooldown(s)']}{ROW['ANGEL_RAY']}"

# (key, name, jobstep, cooldown, costsAction, hits, icd, window, chance, rolls,
#  baseDamage, factorIndex, scales, skillMasteryBonusPct, masteryBossDmgPct, masteryNormalDmgPct,
#  normalMonsterTargets, buffTarget, buffDuration, mapleBase, mapleFactor, stacks, note)
SKILL_ROWS = [
    ("BIG_BANG", "Big Bang", 4, "", False,
     f'=IF({IB("level")}>=136,6,5)', 0, 0, 100, 1,
     "", "", True,
     level_gated_sum(IB("level"), {102: 10, 106: 1, 116: 1, 120: 1, 128: 1, 132: 1}),
     level_gated_sum(IB("level"), {111: 10, 124: 10}),
     0,
     f'=6+{IB("basic_attack_target_increase")}', "", 0, "", "", "",
     "4th-job basic-attack effect (supersedes Energy Bolt/Holy Arrow/Shining Ray). HIGH-CONFIDENCE "
     "REUSE (not independently reverse-engineered — Bishop has no individual skill wiki pages at "
     "all): level-1 text ('290% damage to 6 target(s) 5 time(s)') is word-for-word identical to "
     "Ice-Lightning-Mage's own Chain Lightning, so this reuses that exact factorIndex 21/baseDamage "
     "2900 tenths% pair, matching Inputs!skill_coefficient (=290*basic_factor/1000) exactly, same "
     "mechanism as every sibling class's own basic-attack row. SkillMasteryBonus% is the 6-tier "
     "'Big Bang - Damage' mastery chain (102/106/116/120/128/132, cumulative totals 10%->15%, "
     "DELTA increments 10 then +1 five times). MasteryBossDamage% is the 2-tier 'Big Bang - Boss "
     "Monster Damage' chain (111/124, +10% each, +20% total). HitsPerCast 5->6 once the level-136 "
     "'Strike' mastery unlocks."),
    ("MAGIC_GUARD", "Magic Guard", 1,
     f'=IF({IB("level")}>=21,30*0.7,30)', True, 1, 0, 0, 100, 1,
     120, 21, True,
     0, 0, 0, 1, "ATTACK", 15,
     "", "", "",
     "Self-buff, +12%->16.8% Attack, 15s duration/30s cooldown (Mastery Lv.21 -30% cooldown -> "
     "21s). factorIndex 21, baseDamage 120 tenths%. Shared verbatim w/ FP-Mage/Ice-Lightning-Mage "
     "(identical wiki wording and numbers)."),
    ("HEAL", "Heal (self Attack%)", 2, 18, True, 1, 0, 0, 100, 1,
     100, 22, True,
     level_gated_sum(IB("level"), {54: 8}),
     0, 0, 1, "ATTACK",
     f'=IF({IB("level")}>=39,10*1.5,10)',
     "", "", "",
     "FLAGGED ASSUMPTION (no wiki curve — only the level-1 value is known): factorIndex 22 "
     "(buff/passive convention), baseDamage 100 tenths% (10% level-1). Heal's own HP-recovery "
     "component is entirely out of scope (no HP tracking anywhere in this calculator). The "
     "conditional '+10% Attack while target HP>=70%' component is modeled always-on (steady-state "
     "'healthy' assumption, same tier as Ice-Lightning-Mage's always-5-Frost-stacks convention). "
     "Self-inclusive ('allied players' — matches Meditation's own established self-inclusive "
     "precedent in FP-Mage/Ice-Lightning-Mage). Duration 10s (Mastery Lv.39 'Heal - Persistence' "
     "+50% -> 15s), cooldown 18s. SkillMasteryBonus% is the SEPARATE Mastery Lv.54 'Heal - "
     "Attack' (+8% Attack when the caster's OWN HP>=50%) — a distinct mastery from the base "
     "skill's own conditional effect, also modeled always-on under the same 100%-HP assumption."),
    ("BLESS", "Bless", 2, 24, True, 1, 0, 0, 100, 1,
     160, 22, True,
     0, 0, 0, 1, "ATTACK",
     f'=IF({IB("level")}>=44,15*1.3,15)',
     "", "", "",
     "FLAGGED ASSUMPTION: factorIndex 22, baseDamage 160 tenths% (16% level-1). Bishop's own "
     "Meditation-equivalent (near-identical wording: 'Increases the Attack of allied players by "
     "16% for 15 sec'), self-inclusive. Duration 15s (Mastery Lv.44 'Bless - Persistence' +30% -> "
     "19.5s), cooldown 24s."),
    ("ANGEL_RAY", "Angel Ray", 4, 17, True, 6, 0, 0, 100, 1,
     6800, 12, True,
     level_gated_sum(IB("level"), {108: 50}),
     0, 0, 1, "", 0,
     "", "", "",
     "FLAGGED ASSUMPTION: factorIndex 12 (burst convention), baseDamage 6800 tenths% (680% "
     "level-1). Wiki: 'Attacks the target with a holy sword 3 times to deal 680% damage 2 "
     "time(s) each' — read as 6 total hits (3 strikes x 2), single-target (no target count given, "
     "stun not modeled). Cooldown 17s. Mastery Lv.108 'Angel Ray - Damage' +50% (real "
     "SkillMasteryBonus%, separate from the Lv.122 Boss Monster Damage proc mastery)."),
    ("ANGEL_RAY_BOSS_PROC", "Angel Ray - Boss Monster Damage (Mastery Lv.122)", 4,
     _ANGEL_RAY_BOSS_PROC_COOLDOWN, False, 1, 0, 0, 100, 1,
     6800, 12, True,
     0, 0, 0, 1, "", 0,
     "", "", "",
     "FLAGGED ASSUMPTION: factorIndex 12 (same as its parent), baseDamage 6800 tenths% (matches "
     "the mastery's own stated 680%, which the wiki confirms 'increases with Angel Ray skill "
     "level' — i.e. it scales, not a flat bonus). Standalone proc row mirroring Ice-Lightning-"
     "Mage's Blizzard - Final Attack precedent: shares Angel Ray's own live Cooldown(s) cell. "
     "Unconditional on a boss hit (not a percentage roll — the wiki's own wording is 'when "
     "hitting a boss monster', no chance given), so ProcChance%=100 here is a placeholder; the "
     "boss-only condition is applied directly in this row's own bespoke Calc!O formula via "
     "(1-Inputs!normal_weight_frac) instead of the generic target-multiplier, since it must be "
     "1 for boss AND pvp (both single-target) but 0 for pure normal-monster fights."),
    ("GENESIS", "Genesis", 4,
     f'=IF({IB("level")}>=126,23*0.7,23)', True, 6, 0, 0, 100, 1,
     7000, 12, True,
     level_gated_sum(IB("level"), {118: 50}),
     0, 0, 10, "", 0,
     "", "", "",
     "FLAGGED ASSUMPTION: factorIndex 12, baseDamage 7000 tenths% (700% level-1). Wiki: 'Drops a "
     "pillar of holy light on 10 nearby target(s) to deal 700% damage 6 time(s)' — burst, not a "
     "DoT (no duration/tick-interval given). Cooldown 23s. Mastery Lv.118 'Genesis - Damage' +50% "
     "(real SkillMasteryBonus%), Lv.126 'Genesis - Reuse' -30% cooldown (baked into the "
     "Cooldown(s) formula)."),
    ("BAHAMUT", "Bahamut", 4,
     f'=IF({IB("level")}>=138,80*0.7,80)', True, 1, 4, 30, 100, 1,
     35000, 12, True,
     level_gated_sum(IB("level"), {130: 50}),
     0, 0,
     f'=IF({IB("level")}>=130,6,3)', "", 0,
     "", "", "",
     "HIGH-CONFIDENCE REUSE (see BIG_BANG's own note on the data-gap situation): level-1 text "
     "('3500% damage every 4 sec to 3 target(s)... 30 sec... 80 sec cooldown') is word-for-word "
     "identical to Ice-Lightning-Mage's own Elquines, so this reuses that exact factorIndex "
     "12/baseDamage 35000 tenths% pair. Mastery Lv.130 'Bahamut - Damage & Target' +50% dmg AND "
     "+3 max targets (3->6, baked into the NormalMonsterTargets formula), Lv.138 'Bahamut - "
     "Reuse' -30% cooldown."),
    ("HOLY_FOUNTAIN", "Holy Fountain (Boss Dmg mastery only)", 3, 30, True, 1, 0, 0, 100, 1,
     "", "", False,
     0, 0, 0, 1, "", 0,
     "", "", "",
     "Holy Fountain's own base skill is pure HP recovery — entirely out of scope (no HP tracking "
     "anywhere in this calculator), so this row carries no BaseDamage/FactorIndex of its own; it "
     "exists only to hold a live Cooldown(s) cell (patched 40s->30s per the Aug 13 2026 patch "
     "note — the wiki page itself is stale) for Mastery Lv.68's own duty-cycle uptime reference "
     "(see build_summary_sheet) and to participate correctly in the cast-rate action-economy sum "
     "(CostsActionSlot=True). Mastery Lv.68 'Holy Fountain - Boss Monster Damage' (patched "
     "10%->20%, confirmed in the Aug 13 2026 patch PDF) is a flat, non-scaling bonus (matches "
     "every other '-Boss Monster Damage' mastery elsewhere in this project, which are all flat "
     "level_gated_sum values, not factor-curve-scaled) — modeled as a duty-cycle-averaged self "
     "Boss Monster Damage buff tied to this row's own cooldown, mirroring Ice-Lightning-Mage's "
     "Freezing Breath - Weaken treatment exactly."),
    ("HOLY_MAGIC_SHELL", "Holy Magic Shell (self Attack%)", 3, 27, True, 1, 0, 0, 100, 1,
     150, 22, True,
     0, 0, 0, 1, "ATTACK", 22,
     "", "", "",
     "FLAGGED ASSUMPTION: factorIndex 22, baseDamage 150 tenths% (15% level-1). Wiki: 'Increases "
     "Attack by 15%... decreases damage taken by allied players by 5%' — the damage-taken "
     "reduction is defensive, out of scope (same exclusion precedent as Ice-Lightning-Mage's "
     "Frozen Break -5%-damage-taken note). Attack component modeled like Magic Guard, "
     "self-inclusive. Duration 22s, cooldown 27s. Mastery Lv.82 'Purification' (removes 1 "
     "debuff) not modeled — no debuff mechanic exists anywhere in this calculator."),
    ("HOLY_SYMBOL", "Holy Symbol", 3, 28, False, 1, 0, 0, 100, 1,
     150, 22, True,
     0,
     level_gated_sum(IB("level"), {90: 25}), 0, 1, "", f'=IF({IB("level")}>=98,14*1.5,14)',
     "", "", "",
     "FLAGGED ASSUMPTION: factorIndex 22, baseDamage 150 tenths% (15% level-1). Wiki: 'Increases "
     "allied players' Normal Monster Damage by 15%... every 28 sec' — auto-triggering passive, "
     "not player-cast (CostsActionSlot=False). Duration 14s (Mastery Lv.98 'Holy Symbol - "
     "Persistence' +50% -> 21s). This row's own F-value feeds a duty-cycle-averaged bespoke "
     "Normal-Monster-only global bonus in build_summary_sheet (a new R_NORMAL_DMG_BONUS slot, "
     "structurally the normal-monster-only mirror of R_MONSTER_DMG_BONUS/Freezing Breath - "
     "Weaken), NOT the generic BuffTargetStat mechanism (left blank here since NM-only doesn't "
     "map onto any existing generic target). Debuff Tolerance component not modeled (no debuff "
     "mechanic exists). MasteryBossDamage% here holds Mastery Lv.90 'Holy Symbol - Damage Boost' "
     "(+25% flat Damage% if allied players excluding self <=2) — ALWAYS TRUE for a solo player, "
     "so this becomes an unconditional flat Damage% bonus once unlocked, folded into the same "
     "Summary R_DAMAGE_BONUS-style slot Ice-Lightning-Mage's Frozen Break/Frost Clutch use (NOT "
     "consumed as MasteryBossDamage% normally would be — this row isn't a DAMAGE_ROW_KEYS row at "
     "all, so that field is otherwise unused here, safe to reuse purely as storage. Deliberately "
     "NOT stored in SkillMasteryBonus% — that field IS consumed unconditionally by the generic "
     "F-column formula for every row, which would have silently contaminated this row's own "
     "F-value (also legitimately used above for the Normal Monster Damage bonus calculation) — "
     "caught via the categorical monster_type sweep, not by the default-boss verification alone."),
    ("ADVANCED_BLESSING", "Advanced Blessing", 4, 26, True, 1, 0, 0, 100, 1,
     70, 22, True,
     level_gated_sum(IB("level"), {113: 4}),
     0, 0, 1, "FINAL_DAMAGE", 20,
     "", "", "",
     "FLAGGED ASSUMPTION: factorIndex 22, baseDamage 70 tenths% (7% level-1). Wiki: 'Increases "
     "Final Damage of allied players by 7%... decreases their MP Cost by 7%' — MP-cost reduction "
     "out of scope (MP not tracked). Self-inclusive, FINAL_DAMAGE target (joins the Average Buff "
     "Multiplier chain in Summary alongside Magic Guard/Heal/Bless/Holy Magic Shell/Infinity). "
     "Duration 20s, cooldown 26s. Mastery Lv.113 '+4% Final Damage while MP>=50%' modeled "
     "always-on (MP-condition-ignored, same decision as MP Eater/Element Amplification) — folded "
     "additively into this row's own SkillMasteryBonus%."),
    ("TRIUMPH_FEATHER", "Triumph Feather", 3, "", False,
     f'=IF({IB("level")}>=104,3,2)', 1, 0, 35, 1,
     1500, 12, True,
     level_gated_sum(IB("level"), {73: 50}),
     0, 0,
     f'=IF({IB("level")}>=94,7,1)', "", 0,
     "", "", "",
     "FLAGGED ASSUMPTION: factorIndex 12, baseDamage 1500 tenths% (150% level-1). Genuinely new "
     "2-stage-proc mechanic: wiki says 'When attacking, harnesses the power of the angel for 10 "
     "sec with a 15% chance [Mastery Lv.78 +10%p -> 25%]. While harnessing, 35% chance/attack to "
     "create angel feathers dealing 150% additional damage 2 time(s), 1s ICD per target (treated "
     "as a single global ICD in this per-second-DPS model, not per-target).' Modeled as: this "
     "row's own ProcChance%=35 is stage 2's chance; stage 1's own steady-state busy-fraction "
     "(chance 15%/25%, duration 10s, driven by the character's own attack rate) is computed in "
     "build_calc_sheet as a bespoke multiplier on this row's own Calc!O formula, mirroring the "
     "queueing-rate approximation FP-Mage's own Meteor Proc uses — NOT the generic H-column "
     "ProcProbability-only pattern every other row uses, since this needs BOTH stages combined. "
     "Mastery Lv.73 +50% dmg (real SkillMasteryBonus%), Lv.94 'Harnessing' removes the 1s-per-"
     "target activation limit and spreads to 7 random targets (modeled here purely as the "
     "already-uncapped ICD assumption plus NormalMonsterTargets 1->7 — the ICD-removal itself is "
     "a known simplification, effectively a no-op under the already-global-ICD treatment, "
     "flagged as a known simplification), Lv.104 'Triumph Feather - Strike' +1 hit count (2->3, "
     "baked into the HitsPerCast formula — same convention as every other Strike+1 mastery "
     "elsewhere in this project). Maple Hero (Bishop's own, different "
     "mechanic shape — see MAPLE_HERO_BISHOP row) feeds this row's own Final Damage chain "
     "directly, not the generic MapleHeroMultiplier (I) column."),
    ("MAPLE_HERO_BISHOP", "Maple Hero", 4, "", False, 1, 0, 0, 100, 1,
     500, 23, True,
     0, 0, 0, 1, "", 0,
     "", "", "",
     "FLAGGED ASSUMPTION: factorIndex 23 (Maple Hero convention, matching every other class's own "
     "Maple Hero factorIndex), baseDamage 500 tenths% (50% level-1). Bishop's own Maple Hero "
     "targets Triumph Feather with a DIFFERENT mechanic shape than every other class's Maple "
     "Hero: 'Increases Final Damage of [Triumph Feather] by 50%' — a genuine Final-Damage-chain "
     "additive term (like Element Amplification), NOT a MapleHeroBase-scaled 'additional damage%' "
     "multiplier. No independent DPS row of its own (Calc columns J-N stay blank/0, same "
     "'no independent row' pattern as Night Lord's own Night Lord's Mark) — only D/E/F (its own "
     "scaling coefficient) are computed, read directly by Triumph Feather's own Calc!K formula. "
     "Also increases HP Recovery of Heal/Holy Fountain (out of scope, no HP tracking)."),
    ("MP_EATER_MP_BOOST", "MP Eater - MP Boost (Mastery Lv.49)", 2, "", False, 1, 0, 0, 100, 1,
     70, 0, False,
     0, 0, 0, 1, "", 0,
     "", "", "",
     "Shared verbatim w/ FP-Mage/Ice-Lightning-Mage: flat always-on +7% Attack Speed once "
     "unlocked (MP>=50%(patched 35%) condition ignored per the always-on decision). Real, "
     "always-on contributor (NOT baked into Inputs) — folds into the Attack Speed diminishing-"
     "returns stack in Summary once unlocked, no uptime averaging (not a timed buff). "
     "FactorIndex is an unused placeholder (ScalesWithLevel=False)."),
    ("ELEMENT_AMPLIFICATION", "Element Amplification", 3, "", False, 1, 0, 0, 100, 1,
     150, 22, True,
     0, 0, 0, 1, "FINAL_DAMAGE", 0,
     "", "", "",
     "Shared verbatim w/ FP-Mage/Ice-Lightning-Mage: +15%->24% Final Damage, unconditional "
     "(ignore the MP>=50%(patched 35%) condition per the same always-on decision applied "
     "everywhere else). Not reflected in Inputs — added directly into the Final Damage chain."),
    ("INFINITY", "Infinity", 4, 30, True, 1, 0, 0, 100, 1,
     150, 21, True,
     0, 0, 0, 1, "FINAL_DAMAGE", 15,
     "", "", "",
     "Shared verbatim w/ Ice-Lightning-Mage: base +15%->27% Final Damage for 15s, additionally "
     "+1%->1.8%/sec stacking up to 10 times — time-averaged total collapses to base*64/45 exactly "
     "(reverse-engineered for Ice-Lightning-Mage, identical wiki wording here). This row's own "
     "Calc!F needs the same bespoke base*64/45 formula in build_calc_sheet as every other class's "
     "Infinity, not the generic F-column formula."),
    ("BLOOD_OF_THE_DIVINE", "Blood of the Divine", 4, "", False, 1, 0, 0, 100, 1,
     50, 22, True,
     0, 0, 0, 1, "", 0,
     "", "", "",
     "FLAGGED ASSUMPTION: factorIndex 22, baseDamage 50 tenths% (5% level-1, the Final Damage "
     "component). HP-scaling passive — HP isn't tracked anywhere in this calculator, so modeled "
     "assuming permanently 100% HP (steady-state favorable assumption, same tier as Ice-"
     "Lightning-Mage's always-5-Frost-stacks convention). Wiki: 'Increases Final Damage by 5%. "
     "For every 10% of current HP increases Critical Damage by 2%' -> at 100% HP, +20% Crit "
     "Damage, modeled as 4x this row's own F-value (preserving the level-1 5%FD:20%CD ratio "
     "across the same factor curve, a further simplification since no separate curve data exists "
     "for the Crit Damage component) — feeds a new Summary R_CRIT_DAMAGE_BONUS slot (mirrors "
     "Night Lord's own R_CRIT_DAMAGE_BONUS for Frailty Curse). Final Damage component feeds the "
     "Final Damage chain directly (like Element Amplification). Mastery Lv.134 '+1.5% Attack "
     "Speed per 10% HP' -> flat +15% Attack Speed at 100% HP, modeled as a FLAT non-scaling "
     "addition (matches how masteries are typically flat elsewhere in this project, independent "
     "of this row's own F-value) once level>=134, folded into the same always-on AS_BONUS slot "
     "MP_EATER_MP_BOOST feeds."),
    ("MAGIC_ACCELERATION", "Magic Acceleration", 2, "", False, 1, 0, 0, 100, 1,
     50, 22, True,
     0, 0, 0, 1, "ATTACK_SPEED", 0,
     "", "", "",
     "Shared verbatim w/ FP-Mage/Ice-Lightning-Mage: Magic Critical pattern, already baked into "
     "Inputs!ATTACK_SPEED%; feeds the 2nd-Job Skill Level Bonus Sensitivity delta only."),
    ("SPELL_MASTERY", "Spell Mastery", 2, "", False, 1, 0, 0, 100, 1,
     150, 22, True,
     0, 0, 0, 1, "MIN_DAMAGE", 0,
     "", "", "",
     "Shared verbatim w/ FP-Mage/Ice-Lightning-Mage: Magic Critical pattern, already baked into "
     "Inputs!MIN_DAMAGE%; feeds the 2nd-Job Skill Level Bonus delta."),
    ("HIGH_WISDOM", "High Wisdom", 2, "", False, 1, 0, 0, 100, 1,
     80, 22, True,
     0, 0, 0, 1, "CRIT_RATE", 0,
     "", "", "",
     "Shared verbatim w/ Ice-Lightning-Mage: Magic Critical pattern, already baked into "
     "Inputs!CRIT_RATE% (jointly with Magic Critical (Crit Rate) below); feeds the 2nd-Job Skill "
     "Level Bonus delta."),
    ("MAGIC_CRITICAL_RATE", "Magic Critical (Crit Rate)", 3, "", False, 1, 0, 0, 100, 1,
     80, 22, True,
     0, 0, 0, 1, "CRIT_RATE", 0,
     "", "", "",
     "Shared verbatim w/ FP-Mage/Ice-Lightning-Mage: Magic Critical pattern, already baked into "
     "Inputs!CRIT_RATE%; feeds the 3rd-Job Skill Level Bonus delta."),
    ("MAGIC_CRITICAL_DAMAGE", "Magic Critical (Crit Damage)", 3, "", False, 1, 0, 0, 100, 1,
     120, 22, True,
     0, 0, 0, 1, "CRIT_DAMAGE", 0,
     "", "", "",
     "Shared verbatim w/ FP-Mage/Ice-Lightning-Mage: Magic Critical pattern, already baked into "
     "Inputs!CRIT_DAMAGE%; feeds the 3rd-Job Skill Level Bonus delta."),
    ("BUFF_MASTERY", "Buff Mastery", 4, "", False, 1, 0, 0, 100, 1,
     100, 22, True,
     0, 0, 0, 1, "", 0,
     "", "", "",
     "Shared verbatim w/ FP-Mage/Ice-Lightning-Mage: feeds bdi_with_buff_mastery_expr (Buff "
     "Duration Increase %) at unlock level 117 — not reflected in Inputs."),
    ("ARCANE_AIM", "Arcane Aim", 4, "", False, 1, 0, 0, 100, 1,
     30, 22, True,
     0, 0, 0, 1, "", 0,
     "", "", "",
     "Shared verbatim w/ FP-Mage/Ice-Lightning-Mage: 25% chance, +Final Damage% for 10s, stacks "
     "x5 — modeled always at max 5 stacks, combined multiplicatively as (1+Calc!F/100)^5."),
]

# Rows with a real Cooldown(s) value (literal or a live formula reference) — CastsInFight
# (fixed-duration mode) is only meaningful for these.
ROW_HAS_COOLDOWN = {row[0]: row[3] not in ("", None) for row in SKILL_ROWS}

# Angel Ray - Boss Monster Damage shares Angel Ray's own live Cooldown(s) cell (its RAW,
# un-CDR'd literal), but its proc cadence should track how often Angel Ray is ACTUALLY cast,
# which does get shortened by Skill Cooldown Decrease (Angel Ray's own CostsActionSlot=True) —
# same fix already applied to Ice-Lightning-Mage's Blizzard - Final Attack (see that file's own
# comment on this exact pattern).
CDR_COSTS_ACTION_ROW = {key: r for key, r in ROW.items()}
CDR_COSTS_ACTION_ROW["ANGEL_RAY_BOSS_PROC"] = ROW["ANGEL_RAY"]


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

    widths = [30, 40, 8, 11, 15, 13, 8, 15, 11, 12, 18, 11, 14, 17, 16, 18, 20, 16, 15,
              20, 20, 8, 60]
    for i, w in enumerate(widths):
        ws.column_dimensions[get_column_letter(i + 1)].width = w
    ws.freeze_panes = "A2"
    return ws


# ---------------------------------------------------------------------------
# Row categories consumed by build_calc_sheet/build_summary_sheet/build_sensitivity_sheet.
# ---------------------------------------------------------------------------
DAMAGE_ROW_KEYS = ["ANGEL_RAY", "ANGEL_RAY_BOSS_PROC", "GENESIS", "BAHAMUT", "TRIUMPH_FEATHER"]
BUFF_ROW_KEYS = ["MAGIC_GUARD", "HEAL", "BLESS", "HOLY_MAGIC_SHELL", "ADVANCED_BLESSING", "INFINITY"]
# Every row that can ever post a nonzero Calc!O DPS value — used to filter the Summary sheet's
# per-skill breakdown table down to real damage sources (buffs/passives always show 0.0000 there).
DAMAGE_DEALING_KEYS = ["BIG_BANG"] + DAMAGE_ROW_KEYS

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
# Summary-sheet row numbers, fixed here (build_calc_sheet needs to embed live references to
# them before build_summary_sheet runs) — mirrors Ice-Lightning-Mage's own SUMMARY_ROW pattern.
# ---------------------------------------------------------------------------
SUMMARY_ROW = {
    "AVG_BUFF_MULT": 50,
    "MONSTER_DMG_BONUS": 51,
    "NORMAL_DMG_BONUS": 52,
    "DAMAGE_BONUS": 53,
    "CRIT_DAMAGE_BONUS": 54,
    "AS_BONUS": 55,
    "APS": 56,
    "CAST_RATE": 57,
    "BASIC_ATTACKS_PER_SEC": 58,
    "TOTAL_DPS": 3,
    "BASIC_ATTACK_DPS": 59,
}


def build_calc_sheet(wb):
    ws = wb.create_sheet("Calc")
    for i, name in enumerate(CALC_HEADERS):
        ws.cell(row=1, column=i + 1, value=name)
    style_header_row(ws, 1, len(CALC_HEADERS))

    # Generic per-row Maple Hero mechanism (Z2/Z3 + MapleHeroBase/MapleHeroFactorIndex columns) —
    # unused by every row in this kit: Bishop's own Maple Hero (+50% Final Damage to Triumph
    # Feather) is a structurally different mechanic, implemented via the standalone
    # MAPLE_HERO_BISHOP row's own F-value referenced directly in Triumph Feather's K-column
    # formula instead (see maple_hero_bishop_gated below). Kept only so every row's generic
    # MapleHeroMultiplier (I column) formula still resolves cleanly to 1 (no row sets its own
    # MapleHeroBase, so this is inert, not a live mechanic).
    ws["Z1"] = "Maple Hero helper (unused — see Note on MAPLE_HERO_BISHOP row)"
    ws["Z1"].font = LABEL_FONT
    ws["Z2"] = f'=MAX(0,({IB("level")}-100)*3)+{IB("skill_lvl_4th")}+{IB("skill_lvl_all")}'
    ws["Z3"] = f'=INDEX(FactorTable!$B$2:$Y$301, MATCH(ROUND(MIN(300,MAX(1,Z2)),0), FactorTable!$A$2:$A$301,0), 24)'

    fixed_duration_active_main = fixed_duration_active_expr(IB("monster_type"), IB("fight_duration"))

    ea_row = ROW["ELEMENT_AMPLIFICATION"]
    aa_row = ROW["ARCANE_AIM"]
    bd_row = ROW["BLOOD_OF_THE_DIVINE"]
    mhb_row = ROW["MAPLE_HERO_BISHOP"]
    elem_amp_gated = f'IF(C{ea_row}=TRUE,F{ea_row},0)'
    arcane_aim_gated = f'IF(C{aa_row}=TRUE,F{aa_row},0)'
    blood_divine_gated = f'IF(C{bd_row}=TRUE,F{bd_row},0)'
    maple_hero_bishop_gated = f'IF(C{mhb_row}=TRUE,F{mhb_row},0)'

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

        if key == "BIG_BANG":
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
                ws.cell(
                    row=r, column=6,
                    value=f"=({S('BaseDamage(tenths%)', r)}/10)*(E{r}/1000)*64/45+{S('SkillMasteryBonus%', r)}",
                )
            elif key == "HOLY_FOUNTAIN":
                # No BaseDamage/FactorIndex of its own — this row exists only for its live
                # Cooldown(s) cell and cast-rate participation (see its own Skills-sheet Note).
                ws.cell(row=r, column=6, value=0)
            else:
                ws.cell(
                    row=r, column=6,
                    value=(
                        f'=IF({S("ScalesWithLevel", r)}=TRUE,({S("BaseDamage(tenths%)", r)}/10)*(E{r}/1000),'
                        f'{S("BaseDamage(tenths%)", r)}/10)+{S("SkillMasteryBonus%", r)}'
                    ),
                )

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

        if key == "BIG_BANG" or key in DAMAGE_ROW_KEYS:
            ws.cell(row=r, column=10, value=f'={IB("attack")}*(F{r}/100)')
            monster_dmg_term = monster_blend_expr(
                IB("monster_type"), IB("normal_weight_frac"),
                f'{IB("boss_damage")}+{S("MasteryBossDamage%", r)}+Summary!$B${SUMMARY_ROW["MONSTER_DMG_BONUS"]}',
                f'{IB("normal_damage")}+{S("MasteryNormalDamage%", r)}+Summary!$B${SUMMARY_ROW["NORMAL_DMG_BONUS"]}',
                "0",
            )
            triumph_maple_term = f'IF({S("Key", r)}="TRIUMPH_FEATHER",{maple_hero_bishop_gated},0)'
            ws.cell(row=r, column=11, value=(
                f'=J{r}*(1+{IB("stat_damage")}/100)'
                f'*(1+({IB("damage")}+Summary!$B${SUMMARY_ROW["DAMAGE_BONUS"]})/100)'
                f'*(1+{monster_dmg_term}/100)'
                f'*(1+{IB("damage_amp")}/100)'
                f'*(5000/(6000+{IB("monster_defense")}*(1-{IB("def_pen")}/100)))'
                f'*(1+{IB("final_damage")}/100)*(1+{elem_amp_gated}/100)*(1+{blood_divine_gated}/100)'
                f'*(1+{triumph_maple_term}/100)'
                f'*(1+{arcane_aim_gated}/100)^5'
                f'*(1+(IF({S("Key", r)}="BIG_BANG",{IB("basic_attack_damage")},'
                f'{IB("skill_damage")}))/100)'
                f'*(Summary!$B${SUMMARY_ROW["AVG_BUFF_MULT"]}*I{r})'
            ))
            ws.cell(row=r, column=12, value=f'=K{r}*(MIN({IB("min_damage")},{IB("max_damage")})/100+{IB("max_damage")}/100)/2')
            ws.cell(row=r, column=13, value=(
                f'=L{r}*(1+({IB("crit_damage")}+Summary!$B${SUMMARY_ROW["CRIT_DAMAGE_BONUS"]})/100)'
            ))
            ws.cell(row=r, column=14, value=(
                f'=L{r}*(1-MIN({IB("crit_rate")},100)/100)+M{r}*(MIN({IB("crit_rate")},100)/100)'
            ))
        else:
            for col in (10, 11, 12, 13, 14):
                ws.cell(row=r, column=col, value="")

        if key == "BIG_BANG":
            ws.cell(row=r, column=15, value=(
                f"=IF(C{r},{S('HitsPerCast', r)}*N{r}*Summary!$B${SUMMARY_ROW['BASIC_ATTACKS_PER_SEC']}*"
                f"{target_multiplier_expr(IB('monster_type'), IB('normal_weight_frac'), S('NormalMonsterTargets', r), IB('max_enemies_hit'))},0)"
            ))
        elif key == "ANGEL_RAY_BOSS_PROC":
            # Unconditional on a boss hit from Angel Ray's own casts — (1-normal_weight_frac)
            # is 1 for boss/pvp (both single-target), 0 for pure normal-monster fights, and
            # blends correctly for Chapter Breakthrough.
            ws.cell(row=r, column=15, value=(
                f'=IF(C{r},H{r}*N{r}*{rate_r}*(1-{IB("normal_weight_frac")}),0)'
            ))
        elif key == "TRIUMPH_FEATHER":
            # Bespoke 2-stage steady-state proc (see this row's own Skills-sheet Note): stage 1
            # ("harnessing") busy-fraction = (p1*R*d1)/(1+p1*R*d1) — an on/off renewal process
            # with mean off-time 1/(p1*R) and mean on-time d1, same derivation family as
            # FP-Mage's own meteor_proc_rate_expr queueing formula. Stage 2 (feather proc) uses
            # that exact queueing formula for its own rate, nested inside stage 1's fraction.
            # R = the character's total attack rate (Summary!APS, every action counts as
            # "attacking" per the wiki's own unconditional "When attacking..." wording).
            r_total = f'Summary!$B${SUMMARY_ROW["APS"]}'
            p1 = f'IF({IB("level")}>=78,25,15)'
            d1 = 10
            harness_fraction = f'(({p1}/100*{r_total}*{d1})/(1+{p1}/100*{r_total}*{d1}))'
            feather_rate = (
                f'({S("ProcChance%", r)}/100*{r_total})/'
                f'(1+{S("ICD(s)", r)}*{S("ProcChance%", r)}/100*{r_total})'
            )
            ws.cell(row=r, column=15, value=(
                f'=IF(C{r},{S("HitsPerCast", r)}*N{r}*{harness_fraction}*{feather_rate}*'
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
        ws.cell(row=r, column=17, value=f'=IFERROR(1/{eff_cd_r},0)')

        if ROW_HAS_COOLDOWN[key]:
            ws.cell(row=r, column=18, value=(
                f'=IF({fixed_duration_active_main},{exact_casts_expr(IB("fight_duration"), eff_cd_r)},0)'
            ))
        else:
            ws.cell(row=r, column=18, value=0)

    ws.cell(row=1, column=17, value="InvCooldown")
    ws.cell(row=1, column=18, value="CastsInFight")

    widths = [26, 40, 10, 12, 9, 15, 13, 14, 17, 13, 15, 12, 12, 17, 12, 10]
    for i, w in enumerate(widths):
        ws.column_dimensions[get_column_letter(i + 1)].width = w
    ws.freeze_panes = "C2"
    return ws


def build_summary_sheet(wb):
    ws = wb.create_sheet("Summary")
    ws["A1"] = "Bishop — DPS Summary"
    ws["A1"].font = Font(bold=True, size=14)

    ws.cell(row=DERIVED_HEADER_ROW, column=1, value="Derived Values (read-only, computed from Inputs)").font = SECTION_FONT
    ws.cell(row=D_ATTACK, column=1, value="ATTACK (= Flat ATTACK x (1+ATTACK%/100))")
    ws.cell(row=D_ATTACK, column=2, value=f'={IB("flat_attack")}*(1+{IB("attack_pct")}/100)')

    ws.cell(row=D_STAT_DAMAGE, column=1, value="STAT_DAMAGE % (= 1% of total INT [incl. Invincible's Defense-> INT] + 0.25% of LUK)")
    ws.cell(
        row=D_STAT_DAMAGE, column=2,
        value=f'=(({IB("flat_int")}+{invincible_int_bonus_expr(IB)})*(1+{IB("int_pct")}/100))*0.01+{IB("luk")}*0.0025'
    )

    ws.cell(row=D_BASIC_INPUT_LEVEL, column=1, value="Basic Attack (Big Bang) Input Level (4th job formula)")
    ws.cell(
        row=D_BASIC_INPUT_LEVEL, column=2,
        value=f'=MAX(0,({IB("level")}-100)*3)+{IB("skill_lvl_4th")}+{IB("skill_lvl_all")}'
    )
    ws.cell(row=D_BASIC_FACTOR, column=1, value="Basic Attack Factor (factorIndex 21, from Big Bang == Chain Lightning reuse)")
    ws.cell(
        row=D_BASIC_FACTOR, column=2,
        value=f'=INDEX(FactorTable!$B$2:$Y$301, MATCH(ROUND(MIN(300,MAX(1,{IB("basic_input_level")})),0), '
              f'FactorTable!$A$2:$A$301,0), 22)'
    )
    ws.cell(row=D_SKILL_COEFFICIENT, column=1, value="SKILL_COEFFICIENT — Big Bang base coefficient % (before Skill Mastery)")
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

    r_avgbuff, r_mdb, r_ndb, r_db, r_cdb, r_asb, r_aps, r_castrate, r_baps = (
        SUMMARY_ROW["AVG_BUFF_MULT"], SUMMARY_ROW["MONSTER_DMG_BONUS"], SUMMARY_ROW["NORMAL_DMG_BONUS"],
        SUMMARY_ROW["DAMAGE_BONUS"], SUMMARY_ROW["CRIT_DAMAGE_BONUS"], SUMMARY_ROW["AS_BONUS"],
        SUMMARY_ROW["APS"], SUMMARY_ROW["CAST_RATE"], SUMMARY_ROW["BASIC_ATTACKS_PER_SEC"],
    )
    r_total, r_basic = SUMMARY_ROW["TOTAL_DPS"], SUMMARY_ROW["BASIC_ATTACK_DPS"]

    mg, heal, bless, hms, ab, inf = (
        ROW["MAGIC_GUARD"], ROW["HEAL"], ROW["BLESS"], ROW["HOLY_MAGIC_SHELL"],
        ROW["ADVANCED_BLESSING"], ROW["INFINITY"],
    )
    bdi_main = bdi_with_buff_mastery_expr(IB("buff_duration_increase_pct"), IB("level"), f'Calc!F{ROW["BUFF_MASTERY"]}')
    fda_main = fixed_duration_active_expr(IB("monster_type"), IB("fight_duration"))

    def buff_uptime(row):
        return uptime_fraction_or_exact_expr(
            fda_main, f'Calc!R{row}', IB("monster_type"), S("BuffDuration(s)", row), S("Cooldown(s)", row),
            bdi_main, IB("fight_duration"),
        )

    ws.cell(row=r_avgbuff, column=1, value="Average Buff Multiplier (Magic Guard + Heal + Bless + Holy Magic Shell, summed; then Advanced Blessing, Infinity)")
    ws.cell(row=r_avgbuff, column=2, value=(
        # Magic Guard, Heal, Bless, and Holy Magic Shell are all "+X% Attack" sources — same
        # bucket, so they sum into one combined percentage before a single multiplication,
        # instead of each compounding against the others. Advanced Blessing and Infinity are
        # both Final Damage, a different (and deliberately still multiplicative) bucket, so they
        # stay their own separate factors.
        f'=(1+(IF(Calc!C{mg}=TRUE,Calc!F{mg}*{buff_uptime(mg)},0)'
        f'+IF(Calc!C{heal}=TRUE,Calc!F{heal}*{buff_uptime(heal)},0)'
        f'+IF(Calc!C{bless}=TRUE,Calc!F{bless}*{buff_uptime(bless)},0)'
        f'+IF(Calc!C{hms}=TRUE,Calc!F{hms}*{buff_uptime(hms)},0))/100)'
        f'*IF(Calc!C{ab}=TRUE,(1+Calc!F{ab}*{buff_uptime(ab)}/100),1)'
        f'*IF(Calc!C{inf}=TRUE,(1+Calc!F{inf}*{buff_uptime(inf)}/100),1)'
    ))

    # Holy Fountain - Boss Monster Damage (Mastery Lv.68, patched 10%->20%): flat, non-scaling
    # bonus (matches every other "-Boss Monster Damage" mastery elsewhere in this project),
    # duty-cycle-averaged off Holy Fountain's own (patched 30s) cooldown, linger 15s. Steady-
    # state only (no fixed-duration exactness), same simplification tier as Ice-Lightning-Mage's
    # Freezing Breath - Weaken.
    hf_cd = S("Cooldown(s)", ROW["HOLY_FOUNTAIN"])
    ws.cell(row=r_mdb, column=1, value="Monster Damage Taken Bonus % (Holy Fountain - Boss Monster Damage, averaged)")
    ws.cell(row=r_mdb, column=2, value=(
        f'=IF({IB("level")}>=68,20*{uptime_fraction_expr(IB("monster_type"), 15, hf_cd, bdi_main)},0)'
    ))

    # Holy Symbol's own base effect (+15%->X% Normal Monster Damage, duty-cycle-averaged off its
    # own cooldown/duration) — feeds only the normal-monster side of monster_dmg_term.
    hsym = ROW["HOLY_SYMBOL"]
    ws.cell(row=r_ndb, column=1, value="Normal Monster Damage Bonus % (Holy Symbol, averaged)")
    ws.cell(row=r_ndb, column=2, value=(
        f'=IF(Calc!C{hsym}=TRUE,Calc!F{hsym}*{buff_uptime(hsym)},0)'
    ))

    # Holy Symbol's Mastery Lv.90 "Damage Boost" (+25% flat Damage% if allies excluding self
    # <=2) — ALWAYS TRUE for a solo player, so this is just its own SkillMasteryBonus% once the
    # skill itself is unlocked (90 > Holy Symbol's own unlock 72, so the level_gated_sum already
    # self-gates correctly without needing a separate Calc!C check).
    ws.cell(row=r_db, column=1, value="Damage % Bonus (Holy Symbol - Damage Boost, solo-always-true)")
    ws.cell(row=r_db, column=2, value=f'={S("MasteryBossDamage%", hsym)}')

    # Blood of the Divine: assumed permanently 100% HP -> +20% Crit Damage (4x this row's own
    # Final-Damage-scaled F-value, preserving the level-1 5%FD:20%CD ratio — see its own Note).
    bd = ROW["BLOOD_OF_THE_DIVINE"]
    ws.cell(row=r_cdb, column=1, value="Crit Damage % Bonus (Blood of the Divine, assumed 100% HP)")
    ws.cell(row=r_cdb, column=2, value=f'=4*IF(Calc!C{bd}=TRUE,Calc!F{bd},0)')

    # MP Eater - MP Boost (flat +7% AS once unlocked) + Blood of the Divine's own Lv.134 mastery
    # (+1.5% AS per 10% HP -> flat +15% at assumed 100% HP) — both real, always-on contributors,
    # no uptime averaging (neither is a timed buff).
    me = ROW["MP_EATER_MP_BOOST"]
    ws.cell(row=r_asb, column=1, value="Attack Speed Bonus % (MP Eater - MP Boost + Blood of the Divine - Attack Speed, always-on)")
    ws.cell(row=r_asb, column=2, value=(
        f'=IF(Calc!C{me}=TRUE,Calc!F{me},0)+IF({IB("level")}>=134,15,0)'
    ))

    ws.cell(row=r_aps, column=1, value="Actions Per Second (Attack Speed combined via diminishing-returns stack, factor 150, then capped)")
    ws.cell(row=r_aps, column=2, value=(
        f'=1+MIN(150,150*(1-(1-{IB("attack_speed")}/150)*(1-B{r_asb}/150)))/100'
    ))

    ws.cell(row=r_castrate, column=1, value="Skill + Buff Cast Rate (subtracted from Big Bang, 1/s)")
    ws.cell(row=r_castrate, column=2, value=(
        f'=IF({fda_main},'
        f'SUMPRODUCT((Skills!{SC["CostsActionSlot"]}2:{SC["CostsActionSlot"]}{LAST_ROW}=TRUE)*'
        f'(Calc!C2:C{LAST_ROW}=TRUE)*Calc!R2:R{LAST_ROW})/{IB("fight_duration")},'
        f'SUMPRODUCT((Skills!{SC["CostsActionSlot"]}2:{SC["CostsActionSlot"]}{LAST_ROW}=TRUE)*'
        f'(Calc!C2:C{LAST_ROW}=TRUE)*Calc!Q2:Q{LAST_ROW}))'
    ))

    ws.cell(row=r_baps, column=1, value="Big Bang Casts Per Second (basic-attack rate)")
    ws.cell(row=r_baps, column=2, value=f'=MAX(0,B{r_aps}-B{r_castrate})')

    ws.cell(row=r_total, column=1, value="TOTAL DPS").font = Font(bold=True, size=13)
    ws.cell(row=r_total, column=2, value=f"=SUM(Calc!O2:O{LAST_ROW})").font = Font(bold=True, size=13)

    ws.cell(row=r_basic, column=1, value="Big Bang DPS")
    ws.cell(row=r_basic, column=2, value=f"=Calc!O{ROW['BIG_BANG']}")

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

    ws.column_dimensions["A"].width = 65
    ws.column_dimensions["B"].width = 16
    ws.column_dimensions["C"].width = 12
    return ws


# ---------------------------------------------------------------------------
# Sensitivity sheet: marginal DPS from bumping each Inputs stat by +1 — same STAT_SWEEP list and
# mechanism as build_ice_lightning_mage_workbook.py (identical Inputs-sheet stat pool, INT-main/
# LUK-sub stat identity).
# ---------------------------------------------------------------------------
STAT_SWEEP = [
    ("flat_int", "Flat INT", "flat"),
    ("int_pct", "INT %", "pct"),
    ("defense", "Defense (flat) — Invincible converts 10% into INT", "flat"),
    ("defense_pct", "Defense %", "pct"),
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
    "Defense %": "defense_pct",
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
# row (2..LAST_ROW) + 9 local summary-equivalent rows (avgbuff/mdb/ndb/db/cdb/asb/aps/castrate/
# baps — one more than Ice-Lightning-Mage's own 8, since Bishop has both a Normal-Monster-only
# bonus AND a Crit-Damage bonus slot) + 1 blank + total + 2 blank spacer rows before the next
# block. Derived from LAST_ROW so it can't drift out of sync.
BLOCK_HEIGHT = LAST_ROW + 15
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
            return f'((({ib("flat_int")}+{invincible_int_bonus_expr(ib)})*(1+{ib("int_pct")}/100))*0.01+{ib("luk")}*0.0025)'
        return IB(key)
    return ib


def build_stat_block(ws, base_row, ib, stat_key, stat_label, override_expr):
    """Self-contained local Calc+Summary DPS pipeline (mirrors build_ice_lightning_mage_workbook.py's
    own build_stat_block). Returns the cell reference holding this block's Total DPS."""
    row_label = base_row
    row_header = base_row + 1
    calc_start = base_row + 2
    row_of = {key: calc_start + (r - 2) for key, r in ROW.items()}
    calc_end = calc_start + (LAST_ROW - 2)

    s_avgbuff = calc_end + 2
    s_mdb = calc_end + 3
    s_ndb = calc_end + 4
    s_db = calc_end + 5
    s_cdb = calc_end + 6
    s_asb = calc_end + 7
    s_aps = calc_end + 8
    s_castrate = calc_end + 9
    s_baps = calc_end + 10
    s_total = calc_end + 12
    avgbuff_ref, mdb_ref, ndb_ref = f"B{s_avgbuff}", f"B{s_mdb}", f"B{s_ndb}"
    db_ref, cdb_ref, asb_ref = f"B{s_db}", f"B{s_cdb}", f"B{s_asb}"
    aps_ref, castrate_ref, baps_ref = f"B{s_aps}", f"B{s_castrate}", f"B{s_baps}"
    total_ref = f"B{s_total}"

    crit_rate_delta = (
        f'((F{row_of["MAGIC_CRITICAL_RATE"]}-Calc!F{ROW["MAGIC_CRITICAL_RATE"]})'
        f'+(F{row_of["HIGH_WISDOM"]}-Calc!F{ROW["HIGH_WISDOM"]}))'
    )
    crit_dmg_delta = f'(F{row_of["MAGIC_CRITICAL_DAMAGE"]}-Calc!F{ROW["MAGIC_CRITICAL_DAMAGE"]})'
    min_dmg_delta = f'(F{row_of["SPELL_MASTERY"]}-Calc!F{ROW["SPELL_MASTERY"]})'
    attack_speed_delta = f'(F{row_of["MAGIC_ACCELERATION"]}-Calc!F{ROW["MAGIC_ACCELERATION"]})'

    fda_block = fixed_duration_active_expr(ib("monster_type"), ib("fight_duration"))

    ea_row_of = row_of["ELEMENT_AMPLIFICATION"]
    aa_row_of = row_of["ARCANE_AIM"]
    bd_row_of = row_of["BLOOD_OF_THE_DIVINE"]
    mhb_row_of = row_of["MAPLE_HERO_BISHOP"]
    elem_amp_gated_block = f'IF(C{ea_row_of}=TRUE,F{ea_row_of},0)'
    arcane_aim_gated_block = f'IF(C{aa_row_of}=TRUE,F{aa_row_of},0)'
    blood_divine_gated_block = f'IF(C{bd_row_of}=TRUE,F{bd_row_of},0)'
    maple_hero_bishop_gated_block = f'IF(C{mhb_row_of}=TRUE,F{mhb_row_of},0)'

    ws.cell(row=row_label, column=1, value=f"Stat: {stat_label}").font = LABEL_FONT
    for i, name in enumerate(CALC_HEADERS):
        ws.cell(row=row_header, column=i + 1, value=name)
    style_header_row(ws, row_header, len(CALC_HEADERS))

    ws.cell(row=row_header, column=18, value="helpers")
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

        if key == "BIG_BANG":
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
            elif key == "HOLY_FOUNTAIN":
                ws.cell(row=row, column=6, value=0)
            else:
                ws.cell(row=row, column=6, value=(
                    f'=IF({S("ScalesWithLevel", r)}=TRUE,({S("BaseDamage(tenths%)", r)}/10)*(E{row}/1000),'
                    f'{S("BaseDamage(tenths%)", r)}/10)+{S("SkillMasteryBonus%", r)}'
                ))

        ws.cell(row=row, column=7, value=f"=Calc!G{r}")
        ws.cell(row=row, column=8, value=f"=Calc!H{r}")
        ws.cell(row=row, column=9, value=(
            f'=IF({S("MapleHeroBase(tenths%)", r)}<>"",'
            f'1+({S("MapleHeroBase(tenths%)", r)}/10)*($Z$3/1000)/100,1)'
        ))

        if key == "BIG_BANG" or key in DAMAGE_ROW_KEYS:
            ws.cell(row=row, column=10, value=(
                f'={ib("attack")}*(F{row}/100)'
            ))
            monster_dmg_term = monster_blend_expr(
                ib("monster_type"), ib("normal_weight_frac"),
                f'{ib("boss_damage")}+{S("MasteryBossDamage%", r)}+{mdb_ref}',
                f'{ib("normal_damage")}+{S("MasteryNormalDamage%", r)}+{ndb_ref}',
                "0",
            )
            triumph_maple_term_block = f'IF({S("Key", r)}="TRIUMPH_FEATHER",{maple_hero_bishop_gated_block},0)'
            ws.cell(row=row, column=11, value=(
                f'=J{row}*(1+{ib("stat_damage")}/100)'
                f'*(1+({ib("damage")}+{db_ref})/100)'
                f'*(1+{monster_dmg_term}/100)'
                f'*(1+{ib("damage_amp")}/100)'
                f'*(5000/(6000+{ib("monster_defense")}*(1-{ib("def_pen")}/100)))'
                f'*(1+{ib("final_damage")}/100)*(1+{elem_amp_gated_block}/100)*(1+{blood_divine_gated_block}/100)'
                f'*(1+{triumph_maple_term_block}/100)'
                f'*(1+{arcane_aim_gated_block}/100)^5'
                f'*(1+(IF({S("Key", r)}="BIG_BANG",{ib("basic_attack_damage")},'
                f'{ib("skill_damage")}))/100)'
                f'*({avgbuff_ref}*I{row})'
            ))
            ws.cell(row=row, column=12, value=(
                f'=K{row}*(MIN({ib("min_damage")}+{min_dmg_delta},{ib("max_damage")})/100+{ib("max_damage")}/100)/2'
            ))
            ws.cell(row=row, column=13, value=(
                f'=L{row}*(1+({ib("crit_damage")}+{cdb_ref}+{crit_dmg_delta})/100)'
            ))
            ws.cell(row=row, column=14, value=(
                f'=L{row}*(1-MIN({ib("crit_rate")}+{crit_rate_delta},100)/100)'
                f'+M{row}*(MIN({ib("crit_rate")}+{crit_rate_delta},100)/100)'
            ))
        else:
            for col in (10, 11, 12, 13, 14):
                ws.cell(row=row, column=col, value="")

        if key == "BIG_BANG":
            big_bang_targets_expr = f'(6+{ib("basic_attack_target_increase")})'
            ws.cell(row=row, column=15, value=(
                f"=IF(C{row},{S('HitsPerCast', r)}*N{row}*{baps_ref}*"
                f"{target_multiplier_expr(ib('monster_type'), ib('normal_weight_frac'), big_bang_targets_expr, ib('max_enemies_hit'))},0)"
            ))
        elif key == "ANGEL_RAY_BOSS_PROC":
            ws.cell(row=row, column=15, value=(
                f'=IF(C{row},H{row}*N{row}*{rate_row}*(1-{ib("normal_weight_frac")}),0)'
            ))
        elif key == "TRIUMPH_FEATHER":
            r_total = aps_ref
            p1 = f'IF({ib("level")}>=78,25,15)'
            d1 = 10
            harness_fraction = f'(({p1}/100*{r_total}*{d1})/(1+{p1}/100*{r_total}*{d1}))'
            feather_rate = (
                f'({S("ProcChance%", r)}/100*{r_total})/'
                f'(1+{S("ICD(s)", r)}*{S("ProcChance%", r)}/100*{r_total})'
            )
            ws.cell(row=row, column=15, value=(
                f'=IF(C{row},{S("HitsPerCast", r)}*N{row}*{harness_fraction}*{feather_rate}*'
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

    mg, heal, bless, hms, ab, inf = (
        row_of["MAGIC_GUARD"], row_of["HEAL"], row_of["BLESS"], row_of["HOLY_MAGIC_SHELL"],
        row_of["ADVANCED_BLESSING"], row_of["INFINITY"],
    )
    bdi_block = bdi_with_buff_mastery_expr(ib("buff_duration_increase_pct"), ib("level"), f'F{row_of["BUFF_MASTERY"]}')

    def buff_uptime_block(local_row, skills_row):
        return uptime_fraction_or_exact_expr(
            fda_block, f'R{local_row}', ib("monster_type"), S("BuffDuration(s)", skills_row),
            S("Cooldown(s)", skills_row), bdi_block, ib("fight_duration"),
        )

    ws.cell(row=s_avgbuff, column=1, value="Average Buff Multiplier")
    ws.cell(row=s_avgbuff, column=2, value=(
        f'=(1+(IF(C{mg}=TRUE,F{mg}*{buff_uptime_block(mg, ROW["MAGIC_GUARD"])},0)'
        f'+IF(C{heal}=TRUE,F{heal}*{buff_uptime_block(heal, ROW["HEAL"])},0)'
        f'+IF(C{bless}=TRUE,F{bless}*{buff_uptime_block(bless, ROW["BLESS"])},0)'
        f'+IF(C{hms}=TRUE,F{hms}*{buff_uptime_block(hms, ROW["HOLY_MAGIC_SHELL"])},0))/100)'
        f'*IF(C{ab}=TRUE,(1+F{ab}*{buff_uptime_block(ab, ROW["ADVANCED_BLESSING"])}/100),1)'
        f'*IF(C{inf}=TRUE,(1+F{inf}*{buff_uptime_block(inf, ROW["INFINITY"])}/100),1)'
    ))

    hf_cd_block = S("Cooldown(s)", ROW["HOLY_FOUNTAIN"])
    ws.cell(row=s_mdb, column=1, value="Monster Damage Taken Bonus % (Holy Fountain)")
    ws.cell(row=s_mdb, column=2, value=(
        f'=IF({ib("level")}>=68,20*{uptime_fraction_expr(ib("monster_type"), 15, hf_cd_block, bdi_block)},0)'
    ))

    hsym = row_of["HOLY_SYMBOL"]
    ws.cell(row=s_ndb, column=1, value="Normal Monster Damage Bonus % (Holy Symbol)")
    ws.cell(row=s_ndb, column=2, value=f'=IF(C{hsym}=TRUE,F{hsym}*{buff_uptime_block(hsym, ROW["HOLY_SYMBOL"])},0)')

    ws.cell(row=s_db, column=1, value="Damage % Bonus (Holy Symbol - Damage Boost)")
    ws.cell(row=s_db, column=2, value=f'={S("MasteryBossDamage%", ROW["HOLY_SYMBOL"])}')

    bd = row_of["BLOOD_OF_THE_DIVINE"]
    ws.cell(row=s_cdb, column=1, value="Crit Damage % Bonus (Blood of the Divine)")
    ws.cell(row=s_cdb, column=2, value=f'=4*IF(C{bd}=TRUE,F{bd},0)')

    me = row_of["MP_EATER_MP_BOOST"]
    ws.cell(row=s_asb, column=1, value="Attack Speed Bonus %")
    ws.cell(row=s_asb, column=2, value=(
        f'=IF(C{me}=TRUE,F{me}+{attack_speed_delta},0)+IF({ib("level")}>=134,15,0)'
    ))

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

    ws.cell(row=s_baps, column=1, value="Big Bang Casts Per Second")
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
    """If a previous Bishop-DPS-Calculator.xlsx already exists at `path`, read back its Inputs
    values and PotentialCubes current-gear table so regenerating the workbook doesn't clobber
    the user's real character stats and gear state with the hardcoded defaults."""
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
            existing_inputs.pop("chapter", None)

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

