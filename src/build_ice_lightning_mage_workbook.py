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
# This fixed-size "Derived Values"/info-dump block must stay SMALL and EARLY (right after
# TOTAL DPS at row 3), not after the variable-length summary tables — those grow with
# DAMAGE_DEALING_KEYS/STAT_SWEEP (about to grow further once a future Artifacts feature lands),
# and a hardcoded-after-them block silently collides once they grow past it. See
# build_fp_mage_workbook.py / build_bishop_workbook.py for the reference pattern this mirrors.
DERIVED_HEADER_ROW = 5
D_ATTACK = 6
D_STAT_DAMAGE = 7
D_BASIC_INPUT_LEVEL = 8
D_BASIC_FACTOR = 9
D_SKILL_COEFFICIENT = 10
D_NORMAL_WEIGHT_FRAC = 11
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

# NOTE: PVP_FIGHT_DURATION is defined later in this file (with the other action-economy helpers)
# but referenced by the artifact formula builders below — safe, since those are function bodies
# resolved at call time (after the whole module has loaded), not at def time.

# ---------------------------------------------------------------------------
# Artifacts — verbatim data model/copy from build_fp_mage_workbook.py (Artifacts are account-wide,
# not class-specific; see [[fp_mage_artifacts]]/KNOWN_GAPS.md). Only ARTIFACT_POTENTIAL_STAT_TO_
# SWEEP_KEY's "Main Stat %" entry is class-specific (int_pct, same as FP-Mage — both INT classes).
# ---------------------------------------------------------------------------
ARTIFACT_LABELS = {
    # Epic
    "charm_of_the_undead": "Charm of the Undead",
    "pigs_ribbon": "Pig's Ribbon",
    "shamaness_marble": "Shamaness Marble",
    "contract_of_darkness": "The Contract of Darkness",
    # Unique
    "rainbow_snail_shell": "Rainbow-colored Snail Shell",
    "hexagon_necklace": "Hexagon Necklace",
    "arwens_glass_shoes": "Arwen's Glass Shoes",
    "mushmoms_cap": "Mushmom's Cap",
    "clear_spring_water": "Clear Spring Water",
    "athena_gloves": "Athena Pierce's Old Gloves",
    "zakums_stone_piece": "Zakum's Stone Piece",
    "horntails_scale": "Horntail's Scale",
    "pink_beans_giant_rib": "Pink Bean's Giant Rib",
    # Legendary
    "chalice": "Chalice",
    "old_music_box": "Old Music Box",
    "silver_pendant": "Silver Pendant",
    "star_rock": "Star Rock",
    "book_of_ancient": "Book of Ancient",
    "lunar_dew": "Lunar Dew",
    "fire_flower": "Fire Flower",
    "soul_contract": "Soul Contract",
    "lit_lamp": "Lit Lamp",
    "soul_pouch": "Soul Pouch",
    "ancient_text_piece": "Ancient Text Piece",
    "icy_soul_rock": "Icy Soul Rock",
    "flaming_lava": "Flaming Lava",
    "sayrams_necklace": "Sayram's Necklace",
    "bottle_of_emotion": "Bottle of Emotion",
    "peach_tree": "Peach Tree Herb Pouch",
    "candle": "Candle",
    "alliance_badge": "Alliance Badge",
    "horn_flute": "Horn Flute",
    "cursed_doll": "Cursed Doll",
    "reindeer_spear": "Reindeer's Spear",
    "secret_map": "Secret Map",
    "ring_of_cycles": "Ring of Cycles",
}
# Every artifact's Rank (wiki-confirmed) — no Mystic/Rare-rank ARTIFACTS exist; those tiers only
# appear as POTENTIAL LINE rarities (see ARTIFACT_POTENTIAL_VALUES). Drives ArtifactsInput's
# per-rank grouping/default Star Level and Potentials' line-count/unlock gating (Epic/Unique cap
# at 2 lines, Legendary at 3).
ARTIFACT_RANK = {key: "Epic" for key in ["charm_of_the_undead", "pigs_ribbon", "shamaness_marble", "contract_of_darkness"]}
ARTIFACT_RANK.update({key: "Unique" for key in [
    "rainbow_snail_shell", "hexagon_necklace", "arwens_glass_shoes", "mushmoms_cap",
    "clear_spring_water", "athena_gloves", "zakums_stone_piece", "horntails_scale",
    "pink_beans_giant_rib",
]})
ARTIFACT_RANK.update({key: "Legendary" for key in ARTIFACT_LABELS if key not in ARTIFACT_RANK})
ARTIFACT_RANK_DEFAULT_STAR = {"Epic": 5, "Unique": 3, "Legendary": "Not Unlocked"}

# Content types treated as "[Growth Dungeon]" for Clear Spring Water/Secret Map/Old Music Box's
# "dungeons" clause — confirmed by the user as all 5 dungeon-named content types.
GROWTH_DUNGEON_CONTENT_TYPES = [
    "Weapon Dungeon", "Equipment Dungeon", "Enhancement Dungeon", "EXP Dungeon", "Hero Dungeon",
]
# Artifacts whose stat is assumed already manually folded into the character's own Inputs when
# equipped (Book of Ancient/Athena's Gloves — both their direct AND dependent stat; Clear Spring
# Water/Soul Pouch — their only stat; Reindeer's Spear — only its BASE, un-multiplied Defense
# Penetration) — each contributes 0 to the real/live Calc pipeline; Sensitivity reacts via an
# equip-toggle delta only, same shape as Book of Ancient's own direct-stat delta.
ARTIFACT_STAR_VALUES = {
    "book_of_ancient_crit_rate": [10, 12, 14, 16, 18, 20],
    "book_of_ancient_crit_damage_pct_of_crit_rate": [30, 36, 42, 48, 54, 60],
    "ring_of_cycles_crit_rate": [30, 36, 42, 48, 54, 60],
    "ring_of_cycles_skill_damage": [40, 48, 56, 64, 72, 80],
    "ring_of_cycles_basic_attack_damage_per_point": [0.6, 0.72, 0.84, 0.96, 1.08, 1.2],
    "candle_final_damage": [8, 9.6, 11.2, 12.8, 14.4, 16],
    "candle_boss_damage": [30, 36, 42, 48, 54, 60],
    "peach_tree_enemy_dmg_taken": [15, 18, 21, 24, 27, 30],
    "silver_pendant_enemy_dmg_taken": [10, 12, 14, 16, 18, 20],
    "athena_gloves_attack_speed": [8, 9.6, 11.2, 12.8, 14.4, 16],
    "athena_gloves_max_damage_pct_of_attack_speed": [25, 30, 35, 40, 45, 50],
    "hexagon_necklace_damage": [15, 18, 21, 24, 27, 30],
    "rainbow_snail_shell_crit_rate": [15, 18, 21, 24, 27, 30],
    "rainbow_snail_shell_crit_damage": [20, 24, 28, 32, 36, 40],
    "clear_spring_water_final_damage": [10, 12, 14, 16, 18, 20],
    "old_music_box_attack_pct": [25, 30, 35, 40, 45, 50],
    "soul_contract_cooldown_decrease_pct": [20, 24, 28, 32, 36, 40],
    "soul_pouch_final_damage": [20, 24, 28, 32, 36, 40],
    "flaming_lava_final_damage_debuffed": [8, 9.6, 11.2, 12.8, 14.4, 16],
    "icy_soul_rock_crit_damage": [20, 24, 28, 32, 36, 40],
    "secret_map_attack_pct": [5, 6, 7, 8, 9, 10],
    "secret_map_final_damage": [5, 6, 7, 8, 9, 10],
    "reindeer_spear_attack_pct": [5, 6, 7, 8, 9, 10],
    "reindeer_spear_def_pen": [5, 6, 7, 8, 9, 10],
    "cursed_doll_final_damage": [7, 8.4, 9.8, 11.2, 12.6, 14],
    "horn_flute_final_damage": [10, 12, 14, 16, 18, 20],
    "bottle_of_emotion_attack_pct": [15, 18, 21, 24, 27, 30],
    "bottle_of_emotion_final_damage_per_3pct_as": [0.5, 0.6, 0.7, 0.8, 0.9, 1],
    "bottle_of_emotion_final_damage_cap": [10, 12, 14, 16, 18, 20],
    "alliance_badge_attack_pct": [10, 12, 14, 16, 18, 20],
    "sayrams_necklace_normal_damage": [30, 36, 42, 48, 54, 60],
    "sayrams_necklace_boss_damage": [10, 12, 14, 16, 18, 20],
    "lit_lamp_final_damage": [20, 24, 28, 32, 36, 40],
    "fire_flower_final_damage_per_target": [1, 1.2, 1.4, 1.6, 1.8, 2],
    "star_rock_boss_damage": [50, 60, 70, 80, 90, 100],
    "chalice_final_damage": [15, 18, 21, 24, 27, 30],
    "contract_of_darkness_crit_rate": [8, 9.6, 11.2, 12.8, 14.4, 16],
    "shamaness_marble_buff_duration_increase_pct": [6, 7.2, 8.4, 9.6, 10.8, 12],
    "charm_of_the_undead_attack_pct": [10, 12, 14, 16, 18, 20],
}

# ArtifactsInput sheet layout — a friendlier "current state" sheet (styled after PotentialCubes)
# where the user actually edits star-level/potential state, instead of raw text on Inputs. The 4
# equipped-artifact slots live on the Inputs sheet instead (see INPUT_ARTIFACT_SLOT_ROWS) — moved
# there per the user, so equip state sits alongside the rest of the per-content-type loadout
# instead of on a separate sheet. LEGACY_ARTIFACTS_INPUT_SLOT_ROWS is kept only so
# load_existing_workbook_state can still migrate a pre-move file's slot picks forward.
LEGACY_ARTIFACTS_INPUT_SLOT_ROWS = [4, 5, 6, 7]
ARTIFACTS_INPUT_TABLE_HEADER_ROW = 4
ARTIFACTS_INPUT_FIRST_DATA_ROW = ARTIFACTS_INPUT_TABLE_HEADER_ROW + 1
# Row assignment follows the wiki's own artifact listing order (see ARTIFACT_LABELS), grouped by
# Rank with one blank separator row between groups, per the user.
ARTIFACTS_INPUT_ROW = {}
_row_cursor = ARTIFACTS_INPUT_FIRST_DATA_ROW
_prev_rank = None
for _art_key in ARTIFACT_LABELS:
    _rank = ARTIFACT_RANK[_art_key]
    if _prev_rank is not None and _rank != _prev_rank:
        _row_cursor += 1
    ARTIFACTS_INPUT_ROW[_art_key] = _row_cursor
    _row_cursor += 1
    _prev_rank = _rank
ARTIFACTS_INPUT_LAST_ROW = _row_cursor - 1

# Equipped-artifact slots now live on the Inputs sheet, appended after everything else there (row
# 46 left blank as a spacer) so no existing IN-dict row number has to shift. One resolved column B
# + per-content-type C-L columns each, exactly like every other per-content-type Inputs row.
INPUT_ARTIFACT_SLOTS_SECTION_ROW = 46
INPUT_ARTIFACT_SLOT_ROWS = [47, 48, 49, 50]

# Columns C-L hold up to 3 Potential lines (Rarity/Stat dropdowns + computed % DPS Gain each,
# Line 3 Legendary-only) — see build_artifacts_input_sheet/ARTIFACT_POTENTIAL_VALUES. Columns M/N
# hold each artifact's resolved Equipped?/Star Level (computed from the 4 slot pickers + column
# B's own Star Level cell) — IB() resolves every "{art_key}_equipped"/"{art_key}_star" key straight
# to these cells, so the Inputs sheet no longer needs to show them at all (removed per the user).
ARTIFACT_INPUT_CELL = {}
for _art_key in ARTIFACT_LABELS:
    _row = ARTIFACTS_INPUT_ROW[_art_key]
    ARTIFACT_INPUT_CELL[f"{_art_key}_equipped"] = f"ArtifactsInput!$M${_row}"
    ARTIFACT_INPUT_CELL[f"{_art_key}_star"] = f"ArtifactsInput!$N${_row}"


def star_lookup_expr(star_ref, value_key):
    """CHOOSE-based lookup of a star-tier value array (0-5) by the artifact's own Star Level
    Inputs cell — e.g. CHOOSE(star+1, 10,12,14,16,18,20)."""
    values = ARTIFACT_STAR_VALUES[value_key]
    return f'CHOOSE({star_ref}+1,{",".join(str(v) for v in values)})'


# Artifact Potentials — a third stat source (alongside Inventory Effect [out of scope] and Equip
# Effect [done]): up to 2 lines for Epic/Unique artifacts, 3 for Legendary, gated by the
# artifact's own Star Level (line 1 at 1*, line 2 at 2*, line 3 at 5* — Legendary only). Each line
# independently rolls a rarity (Rare/Epic/Unique/Legendary/Mystic/Mystic Prime) and a stat. Per
# the user, this is NOT a live Calc-sheet term — the actual stat impact is assumed already
# manually folded into the character's Inputs (same "baked into Inputs" convention as Book of
# Ancient/Clear Spring Water/etc.) — this is purely a reference calculator (like Potential Cubes'
# own EV report) showing the DPS Gain a given roll represents, using the SAME
# Sensitivity!H<row> DPS-per-unit values and stat-name convention as equipment Potential Cubes.
# Values taken verbatim from the project's own equipment-potential-style source (confirmed
# accurate by the user).
ARTIFACT_POTENTIAL_RARITIES = ["Rare", "Epic", "Unique", "Legendary", "Mystic", "Mystic (Prime)"]
ARTIFACT_POTENTIAL_VALUES = {
    "Main Stat %": {"Rare": 2, "Epic": 3, "Unique": 4.5, "Legendary": 7, "Mystic": 10, "Mystic (Prime)": 12},
    "Damage Taken Decrease %": {"Rare": 1, "Epic": 1.5, "Unique": 2.3, "Legendary": 3.5, "Mystic": 5, "Mystic (Prime)": 6},
    "Defense %": {"Rare": 2, "Epic": 3, "Unique": 4.5, "Legendary": 7, "Mystic": 10, "Mystic (Prime)": 12},
    "Accuracy": {"Rare": 2, "Epic": 3, "Unique": 4, "Legendary": 7, "Mystic": 10, "Mystic (Prime)": 12},
    "Critical Rate %": {"Rare": 2, "Epic": 3, "Unique": 4.5, "Legendary": 7, "Mystic": 10, "Mystic (Prime)": 12},
    "Min Damage Multiplier %": {"Rare": 2, "Epic": 3, "Unique": 4.5, "Legendary": 7, "Mystic": 10, "Mystic (Prime)": 12},
    "Max Damage Multiplier %": {"Rare": 2, "Epic": 3, "Unique": 4.5, "Legendary": 7, "Mystic": 10, "Mystic (Prime)": 12},
    "Boss Monster Damage %": {"Rare": 4, "Epic": 6, "Unique": 9, "Legendary": 14, "Mystic": 20, "Mystic (Prime)": 24},
    "Normal Monster Damage %": {"Rare": 4, "Epic": 6, "Unique": 9, "Legendary": 14, "Mystic": 20, "Mystic (Prime)": 24},
    "Status Effect Damage %": {"Rare": 4, "Epic": 6, "Unique": 9, "Legendary": 14, "Mystic": 20, "Mystic (Prime)": 24},
    "Damage %": {"Rare": 4, "Epic": 6, "Unique": 9, "Legendary": 14, "Mystic": 20, "Mystic (Prime)": 24},
    "Defense Penetration %": {"Rare": 2, "Epic": 3, "Unique": 4.5, "Legendary": 7, "Mystic": 10, "Mystic (Prime)": 12},
}
# Maps each potential stat name to its Sensitivity STAT_SWEEP key — reuses the exact same
# DPS-per-unit values equipment Potential Cubes already use. None = no such bucket exists
# anywhere in this project, always 0 DPS impact (per the user) — Damage Taken Decrease %/
# Defense %/Accuracy/Status Effect Damage %.
ARTIFACT_POTENTIAL_STAT_TO_SWEEP_KEY = {
    "Main Stat %": "int_pct",
    "Damage Taken Decrease %": None,
    "Defense %": None,
    "Accuracy": None,
    "Critical Rate %": "crit_rate",
    "Min Damage Multiplier %": "min_damage",
    "Max Damage Multiplier %": "max_damage",
    "Boss Monster Damage %": "boss_damage",
    "Normal Monster Damage %": "normal_damage",
    "Status Effect Damage %": None,
    "Damage %": "damage",
    "Defense Penetration %": "def_pen",
}


def artifact_potential_gain_expr(rarity_ref, stat_ref):
    """DPS Gain a potential line's current (rarity, stat) roll represents — value (from
    ARTIFACT_POTENTIAL_VALUES) x DPS-per-unit (Sensitivity!H<row>, via SENSITIVITY_ROW_FOR).
    0 for "(none)"/unrecognized stats and for the 4 stats with no mapped DPS bucket."""
    branches = []
    for stat_name, values_by_rarity in ARTIFACT_POTENTIAL_VALUES.items():
        sweep_key = ARTIFACT_POTENTIAL_STAT_TO_SWEEP_KEY.get(stat_name)
        if sweep_key is None:
            branches.append(f'IF({stat_ref}="{stat_name}",0,')
        else:
            rarity_choose = (
                f'CHOOSE(MATCH({rarity_ref},{{"' + '","'.join(ARTIFACT_POTENTIAL_RARITIES) + '"},0),'
                + ",".join(str(values_by_rarity[rarity]) for rarity in ARTIFACT_POTENTIAL_RARITIES) + ")"
            )
            branches.append(
                f'IF({stat_ref}="{stat_name}",({rarity_choose})*Sensitivity!$H${SENSITIVITY_ROW_FOR[sweep_key]},'
            )
    return "".join(branches) + "0" + ")" * len(branches)


# Reusable, fully-parameterized artifact formula builders — verbatim from build_fp_mage_workbook.py
# (used both by build_artifacts_sheet and build_stat_block's Sensitivity shadow-block mirror).
def artifact_book_of_ancient_crit_damage_expr(eq_expr, star_expr, crit_rate_total_expr):
    return f'IF({eq_expr},{star_lookup_expr(star_expr, "book_of_ancient_crit_damage_pct_of_crit_rate")}/100*({crit_rate_total_expr}),0)'


def artifact_ring_of_cycles_exprs(eq_expr, star_expr, threshold_cr_expr):
    """Returns (crit_rate_bonus, skill_dmg_bonus, basic_attack_dmg_bonus)."""
    crit_rate = f'IF(AND({eq_expr},({threshold_cr_expr})<100),{star_lookup_expr(star_expr, "ring_of_cycles_crit_rate")},0)'
    skill_dmg = f'IF(AND({eq_expr},({threshold_cr_expr})>=100),{star_lookup_expr(star_expr, "ring_of_cycles_skill_damage")},0)'
    excess_points = f'IF(AND({eq_expr},({threshold_cr_expr})>=100),MIN(100,({threshold_cr_expr})-100),0)'
    basic_atk = f'(({excess_points})*{star_lookup_expr(star_expr, "ring_of_cycles_basic_attack_damage_per_point")})'
    return crit_rate, skill_dmg, basic_atk


def artifact_candle_exprs(eq_expr, monster_type_expr, content_type_expr, fight_duration_expr, fda_expr, star_expr):
    """Returns (final_damage_bonus, boss_damage_bonus)."""
    eff_duration = f'IF({monster_type_expr}="pvp",{PVP_FIGHT_DURATION},{fight_duration_expr})'
    eff_active = f'IF({monster_type_expr}="pvp",TRUE,{fda_expr})'
    boss_appear = f'IF({content_type_expr}="Breakthrough",20,IF({content_type_expr}="Hero Dungeon",30,0))'
    boss_present_duration = f'({eff_duration}-{boss_appear})'
    final_dmg = (
        f'IF(AND({eq_expr},{eff_active}),{star_lookup_expr(star_expr, "candle_final_damage")},0)'
    )
    boss_dmg = (
        f'IF(AND({eq_expr},{eff_active}),MAX(0,MIN(40,{eff_duration})-MAX(20,{boss_appear}))/{boss_present_duration}'
        f'*{star_lookup_expr(star_expr, "candle_boss_damage")},0)'
    )
    return final_dmg, boss_dmg


def artifact_peach_tree_expr(eq_expr, star_expr, aps_expr, content_type_expr):
    uptime = f'(1-EXP(-(0.2*{aps_expr})*5))'
    return f'IF(AND({eq_expr},{content_type_expr}<>"Chapter Hunt"),{star_lookup_expr(star_expr, "peach_tree_enemy_dmg_taken")}*{uptime},0)'


def artifact_silver_pendant_expr(eq_expr, star_expr, aps_expr, content_type_expr):
    rho = f'(0.15*{aps_expr}*5)'
    weights = [f'({rho})^{n}/{f}' for n, f in enumerate([1, 1, 2, 6, 24, 120])]
    weight_sum = "+".join(f'({w})' for w in weights)
    weighted_sum = "+".join(f'{n}*({w})' for n, w in enumerate(weights))
    avg_stacks = f'(({weighted_sum})/({weight_sum}))'
    return f'IF(AND({eq_expr},{content_type_expr}<>"Chapter Hunt"),{star_lookup_expr(star_expr, "silver_pendant_enemy_dmg_taken")}*{avg_stacks},0)'


def artifact_athena_max_damage_expr(eq_expr, star_expr, attack_speed_total_expr):
    return f'IF({eq_expr},{star_lookup_expr(star_expr, "athena_gloves_max_damage_pct_of_attack_speed")}/100*({attack_speed_total_expr}),0)'


def artifact_hexagon_expr(eq_expr, monster_type_expr, fight_duration_expr, star_expr):
    eff_d = f'IF({monster_type_expr}="pvp",{PVP_FIGHT_DURATION},{fight_duration_expr})'
    steady = f'AND({monster_type_expr}<>"pvp",{fight_duration_expr}=0)'
    avg_stacks = (
        f'IF({steady},3,IF({eff_d}<=20,0,IF({eff_d}<=40,({eff_d}-20)/({eff_d}),'
        f'IF({eff_d}<=60,(2*{eff_d}-60)/({eff_d}),(3*{eff_d}-120)/({eff_d})))))'
    )
    return f'IF({eq_expr},{star_lookup_expr(star_expr, "hexagon_necklace_damage")}*({avg_stacks}),0)'


def artifact_rainbow_snail_exprs(eq_expr, monster_type_expr, fight_duration_expr, fda_expr, star_expr):
    """Returns (crit_rate_bonus, crit_damage_bonus)."""
    uptime = (
        f'IF({monster_type_expr}="pvp",MIN(15,{PVP_FIGHT_DURATION})/{PVP_FIGHT_DURATION},'
        f'IF({fda_expr},MIN(15,{fight_duration_expr})/({fight_duration_expr}),0))'
    )
    crit_rate = f'IF({eq_expr},{star_lookup_expr(star_expr, "rainbow_snail_shell_crit_rate")}*({uptime}),0)'
    crit_damage = f'IF({eq_expr},{star_lookup_expr(star_expr, "rainbow_snail_shell_crit_damage")}*({uptime}),0)'
    return crit_rate, crit_damage


def _growth_dungeon_gate_expr(content_type_expr):
    return "OR(" + ",".join(f'{content_type_expr}="{c}"' for c in GROWTH_DUNGEON_CONTENT_TYPES) + ")"


def artifact_clear_spring_water_reference_expr(eq_expr, content_type_expr, star_expr):
    return f'IF(AND({eq_expr},{_growth_dungeon_gate_expr(content_type_expr)}),{star_lookup_expr(star_expr, "clear_spring_water_final_damage")},0)'


def artifact_old_music_box_expr(eq_expr, content_type_expr, star_expr):
    never_cond = "OR(" + ",".join(
        f'{content_type_expr}="{c}"' for c in ["Chapter Hunt", "Breakthrough"] + GROWTH_DUNGEON_CONTENT_TYPES
    ) + ")"
    always_cond = f'OR({content_type_expr}="World Boss",{content_type_expr}="PvP")'
    uptime = f'IF({never_cond},0,IF({always_cond},1,IF({content_type_expr}="Chapter Boss",60/70,0)))'
    return f'IF({eq_expr},{star_lookup_expr(star_expr, "old_music_box_attack_pct")}*({uptime}),0)'


def artifact_soul_contract_pct_expr(eq_expr, content_type_expr, star_expr):
    return f'IF(AND({eq_expr},{content_type_expr}="Chapter Hunt"),{star_lookup_expr(star_expr, "soul_contract_cooldown_decrease_pct")},0)'


def artifact_soul_pouch_reference_expr(eq_expr, monster_type_expr, star_expr):
    return f'IF(AND({eq_expr},{monster_type_expr}="pvp"),{star_lookup_expr(star_expr, "soul_pouch_final_damage")},0)'


def artifact_flaming_lava_expr(eq_expr, star_expr, content_type_expr):
    return f'IF(AND({eq_expr},{content_type_expr}<>"Chapter Hunt"),{star_lookup_expr(star_expr, "flaming_lava_final_damage_debuffed")},0)'


def artifact_icy_soul_rock_expr(eq_expr, star_expr):
    return f'IF({eq_expr},1.5*{star_lookup_expr(star_expr, "icy_soul_rock_crit_damage")},0)'


def artifact_secret_map_exprs(eq_expr, monster_type_expr, content_type_expr, star_expr):
    """Returns (attack_pct_bonus, normal_branch_final_damage_bonus)."""
    attack_pct = f'IF({eq_expr},{star_lookup_expr(star_expr, "secret_map_attack_pct")},0)'
    final_dmg_normal = (
        f'IF(AND({eq_expr},{monster_type_expr}<>"pvp"),'
        f'{star_lookup_expr(star_expr, "secret_map_final_damage")}*IF({_growth_dungeon_gate_expr(content_type_expr)},3,1),0)'
    )
    return attack_pct, final_dmg_normal


def artifact_reindeer_spear_attack_pct_expr(eq_expr, star_expr):
    return f'IF({eq_expr},{star_lookup_expr(star_expr, "reindeer_spear_attack_pct")},0)'


def artifact_reindeer_spear_base_def_pen_reference_expr(eq_expr, star_expr):
    return f'IF({eq_expr},{star_lookup_expr(star_expr, "reindeer_spear_def_pen")},0)'


def artifact_reindeer_spear_extra_mult_expr(monster_type_expr):
    return f'IF({monster_type_expr}="pvp",1,2)'


def artifact_cursed_doll_reference_expr(eq_expr, star_expr):
    return f'IF({eq_expr},{star_lookup_expr(star_expr, "cursed_doll_final_damage")},0)'


def artifact_horn_flute_expr(eq_expr, monster_type_expr, content_type_expr, fight_duration_expr, star_expr):
    uptime = f'MIN(30,MAX(0,{fight_duration_expr}-7))/{fight_duration_expr}'
    mult = f'IF({content_type_expr}="Chapter Boss",2,1)'
    return (
        f'IF(AND({eq_expr},{monster_type_expr}<>"pvp",{fight_duration_expr}>0),'
        f'{star_lookup_expr(star_expr, "horn_flute_final_damage")}*({uptime})*{mult},0)'
    )


def artifact_bottle_of_emotion_attack_pct_expr(eq_expr, star_expr):
    return f'IF({eq_expr},{star_lookup_expr(star_expr, "bottle_of_emotion_attack_pct")},0)'


def artifact_bottle_of_emotion_final_damage_value_expr(eq_expr, star_expr, attack_speed_expr):
    per_point = f'({star_lookup_expr(star_expr, "bottle_of_emotion_final_damage_per_3pct_as")}/3)'
    cap = star_lookup_expr(star_expr, "bottle_of_emotion_final_damage_cap")
    return f'IF({eq_expr},MIN({cap},MAX(0,{per_point}*({attack_speed_expr}-60))),0)'


def artifact_alliance_badge_expr(eq_expr, star_expr):
    return f'IF({eq_expr},{star_lookup_expr(star_expr, "alliance_badge_attack_pct")},0)'


def artifact_sayrams_necklace_exprs(eq_expr, star_expr):
    """Returns (normal_damage_bonus, boss_damage_bonus)."""
    normal = f'IF({eq_expr},{star_lookup_expr(star_expr, "sayrams_necklace_normal_damage")},0)'
    boss = f'IF({eq_expr},{star_lookup_expr(star_expr, "sayrams_necklace_boss_damage")},0)'
    return normal, boss


def artifact_lit_lamp_reference_expr(eq_expr, content_type_expr, star_expr):
    return f'IF(AND({eq_expr},{content_type_expr}="World Boss"),{star_lookup_expr(star_expr, "lit_lamp_final_damage")},0)'


def artifact_fire_flower_exprs(eq_expr, star_expr):
    """Returns (normal_branch_final_damage_bonus, boss_pvp_branch_final_damage_bonus)."""
    per_target = star_lookup_expr(star_expr, "fire_flower_final_damage_per_target")
    normal = f'IF({eq_expr},10*{per_target},0)'
    boss = f'IF({eq_expr},1*{per_target},0)'
    return normal, boss


def artifact_star_rock_reference_expr(eq_expr, star_expr):
    return f'IF({eq_expr},{star_lookup_expr(star_expr, "star_rock_boss_damage")},0)'


def artifact_chalice_exprs(eq_expr, monster_type_expr, content_type_expr, fight_duration_expr, star_expr):
    """Returns (normal_branch_final_damage_bonus, boss_branch_final_damage_bonus)."""
    boss_appear = f'IF({content_type_expr}="Breakthrough",20,IF({content_type_expr}="Hero Dungeon",30,0))'
    normal_phase_end = f'IF({monster_type_expr}="breakthrough",{boss_appear},{fight_duration_expr})'
    activation_start = f'MAX(0,{fight_duration_expr}-30)'
    normal_uptime = (
        f'IF(OR({fight_duration_expr}=0,{normal_phase_end}=0),0,'
        f'MAX(0,{normal_phase_end}-{activation_start})/{normal_phase_end})'
    )
    boss_window = f'({fight_duration_expr}-{normal_phase_end})'
    boss_uptime = (
        f'IF({boss_window}=0,0,'
        f'MAX(0,{fight_duration_expr}-MAX({activation_start},{normal_phase_end}))/{boss_window})'
    )
    star_val = star_lookup_expr(star_expr, "chalice_final_damage")
    active_gate = f'AND({eq_expr},OR({monster_type_expr}="normal",{monster_type_expr}="breakthrough"))'
    normal_bonus = f'IF({active_gate},{star_val}*({normal_uptime}),0)'
    boss_bonus = f'IF({active_gate},{star_val}*({boss_uptime}),0)'
    return normal_bonus, boss_bonus


def artifact_contract_of_darkness_crit_rate_bonus_expr(eq_expr, monster_type_expr, star_expr):
    return f'IF(AND({eq_expr},{monster_type_expr}<>"pvp"),{star_lookup_expr(star_expr, "contract_of_darkness_crit_rate")},0)'


def artifact_shamaness_marble_reference_expr(eq_expr, star_expr):
    return f'IF({eq_expr},{star_lookup_expr(star_expr, "shamaness_marble_buff_duration_increase_pct")},0)'


def artifact_charm_of_the_undead_expr(eq_expr, monster_type_expr, fight_duration_expr, star_expr):
    eff_duration = f'IF({monster_type_expr}="pvp",{PVP_FIGHT_DURATION},{fight_duration_expr})'
    steady_state = f'AND({monster_type_expr}<>"pvp",{fight_duration_expr}=0)'
    dprime = f'MAX(0,{eff_duration}-10)'
    full_cycles = f'INT({dprime}/10)'
    remainder = f'({dprime}-10*{full_cycles})'
    active = f'(5*{full_cycles}+MIN({remainder},5))'
    uptime = f'IF({steady_state},0.5,{active}/{eff_duration})'
    return f'IF({eq_expr},{star_lookup_expr(star_expr, "charm_of_the_undead_attack_pct")}*({uptime}),0)'


# Every Inputs row that gets its own column per content type (see build_inputs_sheet) — i.e.
# everything except the character-wide "level", the "content_type" selector itself, and the
# existing computed rows. Derived from IN/COMPUTED_INPUT_ROWS rather than hand-listed so it can't
# drift out of sync if a row is ever added or removed.
PER_CONTENT_TYPE_INPUT_KEYS = [
    k for k in IN
    if k not in ("level", "content_type") and IN[k] not in COMPUTED_INPUT_ROWS
]


def IB(key):
    if key in DERIVED_ROW:
        return f"Summary!$B${DERIVED_ROW[key]}"
    if key in ARTIFACT_INPUT_CELL:
        return ARTIFACT_INPUT_CELL[key]
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

    COMPUTED_FILL = PatternFill("solid", fgColor="D9D9D9")

    # One column per content type (C-L) for every row that can plausibly differ by loadout —
    # same per-content-type mechanism as build_fp_mage_workbook.py (see PER_CONTENT_TYPE_INPUT_KEYS).
    for i, ct in enumerate(CONTENT_TYPES):
        ws.cell(row=2, column=3 + i, value=ct)
    for c in range(3, 3 + len(CONTENT_TYPES)):
        cell = ws.cell(row=2, column=c)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center")

    rows = [
        ("level", "Character Level", 200),
        ("content_type", "Content Type", "Chapter Boss"),
        ("chapter_stage", (
            "Chapter-Stage — 'chapter-substage' (e.g. '28-9') for Breakthrough/Chapter Hunt, just "
            "the chapter number for Chapter Boss, or just the stage number for Weapon/Equipment/"
            "Enhancement/EXP/Hero Dungeon. Not applicable to World Boss/PvP."
        ), None),
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

    # A few per-content-type rows aren't relevant for every content type (same scoping as
    # build_fp_mage_workbook.py) — columns for content types NOT listed here are left entirely
    # blank (gray, no value, no dropdown) rather than showing an unused default.
    INPUT_ROW_APPLICABLE_CONTENT_TYPES = {
        "chapter_stage": [
            "Chapter Boss", "Breakthrough", "Chapter Hunt", "Weapon Dungeon",
            "Equipment Dungeon", "Enhancement Dungeon", "EXP Dungeon", "Hero Dungeon",
        ],
        "boss_normal_weight_choice": ["Breakthrough", "Hero Dungeon"],
        "max_enemies_hit": [
            "EXP Dungeon", "Equipment Dungeon", "Chapter Hunt", "Breakthrough", "Hero Dungeon",
        ],
    }
    CHAPTER_STAGE_DEFAULT_BY_CONTENT_TYPE = {
        "Chapter Boss": "28", "Breakthrough": "28-9", "Chapter Hunt": "28-9",
        "Weapon Dungeon": "80", "Equipment Dungeon": "80", "Enhancement Dungeon": "80",
        "EXP Dungeon": "80", "Hero Dungeon": "80",
    }
    CHAPTER_STAGE_TRUST_EXISTING_FOR = {"Breakthrough", "Chapter Hunt"}

    def _write_input_row(key, label, default):
        r = IN[key]
        ws.cell(row=r, column=1, value=label).font = LABEL_FONT
        if key not in PER_CONTENT_TYPE_INPUT_KEYS:
            cell = ws.cell(row=r, column=2, value=existing.get(key, default))
            cell.fill = INPUT_FILL
            return
        applicable = INPUT_ROW_APPLICABLE_CONTENT_TYPES.get(key, CONTENT_TYPES)
        per_ct = existing.get(key, {})
        for i, ct in enumerate(CONTENT_TYPES):
            cell = ws.cell(row=r, column=3 + i)
            if ct not in applicable:
                cell.fill = COMPUTED_FILL
                continue
            if key == "chapter_stage":
                row_default = CHAPTER_STAGE_DEFAULT_BY_CONTENT_TYPE[ct]
                cell.value = per_ct.get(ct, row_default) if ct in CHAPTER_STAGE_TRUST_EXISTING_FOR else row_default
            else:
                cell.value = per_ct.get(ct, default)
            cell.fill = INPUT_FILL
        resolved = ws.cell(row=r, column=2, value=f'=INDEX($C${r}:$L${r},MATCH($B$4,$C$2:$L$2,0))')
        resolved.fill = COMPUTED_FILL

    for key, label, default in rows:
        _write_input_row(key, label, default)

    ws.cell(row=31, column=1, value="Additional Bonuses").font = SECTION_FONT
    bonus_rows = [
        ("skill_cooldown_decrease", "Skill Cooldown Decrease (seconds, only skills/buffs the character actively casts)", 0),
        ("basic_attack_target_increase", "Basic Attack Target Increase (flat, adds to the 6-target normal-monster base)", 1),
        ("buff_duration_increase_pct", "Buff Duration Increase %", 0),
        ("companion_summon_time_increase_pct", "Companion Summoning Time Increase % (companions not modeled — always 0 DPS impact)", 0),
        ("boss_normal_weight_choice", "Boss/Normal Emphasis (Breakthrough/Hero Dungeon only)", "A Little More Normal"),
        ("max_enemies_hit", "Max Enemies Actually In Range (normal-monster content only; default 999 = uncapped)", 999),
    ]
    for key, label, default in bonus_rows:
        _write_input_row(key, label, default)

    # Artifacts' Equipped?/Star Level no longer appear on this sheet at all — set them on the
    # ArtifactsInput sheet instead (see build_artifacts_input_sheet); IB() resolves every
    # "{art_key}_equipped"/"{art_key}_star" key straight there (see ARTIFACT_INPUT_CELL).

    dv_content_type = DataValidation(
        type="list", formula1='"' + ",".join(CONTENT_TYPES) + '"', allow_blank=False
    )
    ws.add_data_validation(dv_content_type)
    dv_content_type.add(ws.cell(row=IN["content_type"], column=2))

    dv_boss_normal_weight = DataValidation(
        type="list", formula1='"' + ",".join(BOSS_NORMAL_WEIGHT_CHOICES) + '"', allow_blank=False
    )
    ws.add_data_validation(dv_boss_normal_weight)
    _bnw_row = IN["boss_normal_weight_choice"]
    for ct in INPUT_ROW_APPLICABLE_CONTENT_TYPES["boss_normal_weight_choice"]:
        dv_boss_normal_weight.add(ws.cell(row=_bnw_row, column=3 + CONTENT_TYPES.index(ct)))

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

    # Equipped-artifact slots — appended after everything else (row 46 left blank as a spacer) so
    # no existing IN-dict row number has to shift. One resolved column B (INDEX/MATCH against
    # C:L, same mechanism as every other per-content-type row) + per-content-type raw picks in
    # C:L per slot — verbatim mechanism from build_fp_mage_workbook.py.
    ws.cell(row=INPUT_ARTIFACT_SLOTS_SECTION_ROW, column=1, value="Equipped Artifacts (up to 4)").font = SECTION_FONT
    artifact_names = list(ARTIFACT_LABELS.values())
    dv_slot_options_col = 14
    ws.cell(row=1, column=dv_slot_options_col, value="(none)")
    for i, name in enumerate(artifact_names):
        ws.cell(row=2 + i, column=dv_slot_options_col, value=name)
    dv_slot_options_range = f"${get_column_letter(dv_slot_options_col)}$1:${get_column_letter(dv_slot_options_col)}${1 + len(artifact_names)}"
    dv_slot = DataValidation(type="list", formula1=f"={dv_slot_options_range}", allow_blank=False)
    ws.add_data_validation(dv_slot)
    slot_values = existing.get("artifact_slots", {})
    for i, row in enumerate(INPUT_ARTIFACT_SLOT_ROWS):
        ws.cell(row=row, column=1, value=f"Slot {i + 1}").font = LABEL_FONT
        per_ct = {ct: vals[i] if i < len(vals) else "(none)" for ct, vals in slot_values.items()}
        for j, ct in enumerate(CONTENT_TYPES):
            cell = ws.cell(row=row, column=3 + j, value=per_ct.get(ct, "(none)"))
            cell.fill = INPUT_FILL
            dv_slot.add(cell)
        resolved = ws.cell(row=row, column=2, value=(
            f'=INDEX($C${row}:$L${row},MATCH($B$4,$C$2:$L$2,0))'
        ))
        resolved.fill = COMPUTED_FILL

    ws.column_dimensions["A"].width = 46
    ws.column_dimensions["B"].width = 16
    for c in range(3, 3 + len(CONTENT_TYPES)):
        ws.column_dimensions[get_column_letter(c)].width = 14
    ws.column_dimensions[get_column_letter(dv_slot_options_col)].hidden = True
    ws.freeze_panes = "C3"
    return ws


def build_artifacts_input_sheet(wb, existing=None):
    """A dedicated "current gear state" sheet for Artifacts, styled after PotentialCubes — verbatim
    structure from build_fp_mage_workbook.py's own build_artifacts_input_sheet (Artifacts are
    account-wide, not class-specific)."""
    existing = existing or {}
    ws = wb.create_sheet("ArtifactsInput")
    ws["A1"] = "Arch Mage (Ice/Lightning) — Artifacts (Star Level + Potentials)"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = (
        "Equipped artifacts are picked on the Inputs sheet now (Equipped Artifacts section, per "
        "content type). Every artifact's Star Level (or \"Not Unlocked\") and Potential lines are "
        "tracked separately regardless of whether it's currently equipped, so swapping gear "
        "doesn't lose your progress. Potential lines are reference-only (their DPS Gain is NOT "
        "added to live Total DPS) — the assumption is the same as Book of Ancient etc.: once you "
        "decide to keep a roll, fold its value into your own Inputs manually. Sensitivity's "
        "Artifact Equip-Toggle table DOES include each artifact's current potential-line DPS "
        "Gain, since potentials only apply while the artifact is actually equipped."
    )

    ws.cell(row=ARTIFACTS_INPUT_TABLE_HEADER_ROW - 1, column=1, value="All Artifacts — Star Level + Potentials").font = SECTION_FONT

    headers = [
        "Artifact", "Star Level",
        "Line 1 Rarity", "Line 1 Stat", "Line 1 DPS Gain",
        "Line 2 Rarity", "Line 2 Stat", "Line 2 DPS Gain",
        "Line 3 Rarity (Legendary only)", "Line 3 Stat (Legendary only)", "Line 3 DPS Gain",
        "Total Potential DPS Gain",
        "Equipped? (computed)", "Star Level, resolved (computed)",
    ]
    for i, name in enumerate(headers):
        ws.cell(row=ARTIFACTS_INPUT_TABLE_HEADER_ROW, column=i + 1, value=name)
    style_header_row(ws, ARTIFACTS_INPUT_TABLE_HEADER_ROW, len(headers))

    dv_star = DataValidation(type="list", formula1='"Not Unlocked,0,1,2,3,4,5"', allow_blank=False)
    ws.add_data_validation(dv_star)
    dv_rarity = DataValidation(
        type="list", formula1='"' + ",".join(ARTIFACT_POTENTIAL_RARITIES) + '"', allow_blank=False,
    )
    ws.add_data_validation(dv_rarity)
    dv_pot_stat = DataValidation(
        type="list", formula1='"(none),' + ",".join(ARTIFACT_POTENTIAL_VALUES) + '"', allow_blank=False,
    )
    ws.add_data_validation(dv_pot_stat)
    stars = existing.get("stars", {})
    lines_existing = existing.get("lines", {})
    for art_key, art_label in ARTIFACT_LABELS.items():
        row = ARTIFACTS_INPUT_ROW[art_key]
        rank = ARTIFACT_RANK[art_key]
        ws.cell(row=row, column=1, value=art_label).font = LABEL_FONT
        default_star = ARTIFACT_RANK_DEFAULT_STAR[rank]
        star_cell = ws.cell(row=row, column=2, value=stars.get(art_key, default_star))
        star_cell.fill = INPUT_FILL
        dv_star.add(star_cell)

        saved_lines = lines_existing.get(art_key, {})
        num_lines = 3 if rank == "Legendary" else 2
        line_cols = [(3, 4, 5), (6, 7, 8), (9, 10, 11)]
        line_min_star = [1, 2, 5]
        for line_idx in range(num_lines):
            rarity_col, stat_col, gain_col = line_cols[line_idx]
            saved = saved_lines.get(line_idx + 1, {})
            rarity_cell = ws.cell(row=row, column=rarity_col, value=saved.get("rarity", "Rare"))
            rarity_cell.fill = INPUT_FILL
            dv_rarity.add(rarity_cell)
            stat_cell = ws.cell(row=row, column=stat_col, value=saved.get("stat", "(none)"))
            stat_cell.fill = INPUT_FILL
            dv_pot_stat.add(stat_cell)
            rarity_ref = f"${get_column_letter(rarity_col)}${row}"
            stat_ref = f"${get_column_letter(stat_col)}${row}"
            gain_expr = artifact_potential_gain_expr(rarity_ref, stat_ref)
            ws.cell(row=row, column=gain_col, value=(
                f'=IF($N${row}>={line_min_star[line_idx]},{gain_expr},0)'
            ))
        # Line 3 columns (I/J/K) simply don't exist for Epic/Unique rows (2-line cap regardless of
        # Star Level, per the user) — left entirely blank, not just gated to 0.

        # Total Potential DPS Gain: group lines by stat first (two lines on the SAME stat are
        # correctly additive — two 5% Max Damage lines really are one 10% Max Damage bucket), then
        # combine DIFFERENT stats' groups multiplicatively (each stat's own DPS Gain is only exact
        # holding every other stat fixed, so two different stats each independently worth 1% DPS
        # truly compound to 1.01*1.01-1=2.0201%, not a naive 2% sum) — same methodology as
        # potential_cubes_ev.py's combined_dps_gain(). J/K (Line 3) may be entirely blank for
        # Epic/Unique rows, hence the extra J{row}="" guard on factor_3.
        grouped_1 = f'E{row}+IF(G{row}=D{row},H{row},0)+IF(J{row}=D{row},K{row},0)'
        grouped_2 = f'H{row}+IF(D{row}=G{row},E{row},0)+IF(J{row}=G{row},K{row},0)'
        grouped_3 = f'K{row}+IF(D{row}=J{row},E{row},0)+IF(G{row}=J{row},H{row},0)'
        factor_1 = f'IF(D{row}="(none)",1,1+({grouped_1})/Summary!$B$3)'
        factor_2 = f'IF(OR(G{row}="(none)",G{row}=D{row}),1,1+({grouped_2})/Summary!$B$3)'
        factor_3 = f'IF(OR(J{row}="",J{row}="(none)",J{row}=D{row},J{row}=G{row}),1,1+({grouped_3})/Summary!$B$3)'
        ws.cell(row=row, column=12, value=f'=Summary!$B$3*(({factor_1})*({factor_2})*({factor_3})-1)')

        eq_formula = "=OR(" + ",".join(
            f'Inputs!$B${slot_row}="{art_label}"' for slot_row in INPUT_ARTIFACT_SLOT_ROWS
        ) + ")"
        ws.cell(row=row, column=13, value=eq_formula)
        ws.cell(row=row, column=14, value=f'=IF(B{row}="Not Unlocked",0,B{row})')

    widths = [42, 12, 12, 26, 14, 12, 26, 14, 12, 26, 14, 16, 18, 20]
    for i, w in enumerate(widths):
        ws.column_dimensions[get_column_letter(i + 1)].width = w
    ws.freeze_panes = f"A{ARTIFACTS_INPUT_TABLE_HEADER_ROW + 1}"
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


# Artifacts sheet row layout — per-artifact intermediate/bonus rows, then aggregate bucket totals
# consumed by the main Calc/Summary pipeline (and mirrored in Sensitivity's build_stat_block).
# Verbatim row layout from build_fp_mage_workbook.py (Artifacts are account-wide, not class-specific).
ART_ROW = {
    "boa_crit_damage": 3,
    "roc_threshold_cr": 4,
    "roc_crit_rate": 5,
    "roc_skill_damage": 6,
    "roc_excess_points": 7,
    "roc_basic_attack_damage": 8,
    "candle_eff_duration": 9,
    "candle_eff_active": 10,
    "candle_final_damage": 11,
    "candle_boss_damage": 12,
    "peach_lambda": 13,
    "peach_uptime": 14,
    "peach_enemy_dmg_taken": 15,
    "silver_rho": 16,
    "silver_w0": 17,
    "silver_w1": 18,
    "silver_w2": 19,
    "silver_w3": 20,
    "silver_w4": 21,
    "silver_w5": 22,
    "silver_avg_stacks": 23,
    "silver_enemy_dmg_taken": 24,
    "athena_max_damage": 25,
    "hexagon_avg_stacks": 26,
    "hexagon_damage": 27,
    "rainbow_uptime": 28,
    "rainbow_crit_rate": 29,
    "rainbow_crit_damage": 30,
    "AGG_CRIT_RATE": 32,
    "AGG_CRIT_DAMAGE": 33,
    "AGG_FINAL_DAMAGE": 34,
    "AGG_BOSS_DAMAGE": 35,
    "AGG_ENEMY_DMG_TAKEN": 36,
    "AGG_DAMAGE": 38,
    "AGG_SKILL_DAMAGE": 39,
    "AGG_BASIC_ATTACK_DAMAGE": 40,
    "candle_boss_appear_time": 41,
    "csw_reference": 42,
    "old_music_box_attack_pct": 43,
    "soul_contract_pct": 44,
    "soul_pouch_reference": 45,
    "flaming_lava": 46,
    "icy_soul_rock": 47,
    "secret_map_attack_pct": 48,
    "secret_map_final_dmg_normal": 49,
    "reindeer_spear_attack_pct": 50,
    "reindeer_spear_base_def_pen_reference": 51,
    "AGG_ATTACK_PCT": 52,
    "AGG_FINAL_DAMAGE_NORMAL_ONLY": 53,
    "cursed_doll_reference": 54,
    "horn_flute": 55,
    "bottle_of_emotion_attack_pct": 56,
    "bottle_of_emotion_final_damage_reference": 57,
    "alliance_badge": 58,
    "sayrams_necklace_normal": 59,
    "sayrams_necklace_boss": 60,
    "lit_lamp_reference": 61,
    "fire_flower_normal": 62,
    "fire_flower_boss": 63,
    "star_rock_reference": 64,
    "chalice_normal": 65,
    "chalice_boss": 66,
    "contract_of_darkness_crit_rate_bonus": 69,
    "shamaness_marble_reference": 70,
    "charm_of_the_undead": 71,
    # Always-0 artifacts (raid content / companion-only / non-attacking procs this project
    # doesn't model at all) — trivial rows kept only for ArtifactsInput tracking consistency.
    "ancient_text_piece_reference": 72,
    "lunar_dew_reference": 73,
    "pink_beans_giant_rib_reference": 74,
    "horntails_scale_reference": 75,
    "zakums_stone_piece_reference": 76,
    "mushmoms_cap_reference": 77,
    "arwens_glass_shoes_reference": 78,
    "pigs_ribbon_reference": 79,
    "AGG_NORMAL_DAMAGE": 80,
    "AGG_FINAL_DAMAGE_BOSS_ONLY": 81,
}


def art_ref(key):
    """Cross-sheet reference to a named Artifacts-sheet row, e.g. 'Artifacts!$B$32'."""
    return f"Artifacts!$B${ART_ROW[key]}"


def build_artifacts_sheet(wb):
    """Equip Effect only (Inventory Effect/Potentials/Resonance Amplification not modeled) for the
    8 starting artifacts. Book of Ancient and Athena Pierce's Old Gloves' own direct stat bonus is
    assumed already baked into Inputs!crit_rate/attack_speed — only their dependent bonus is
    computed here. Every other artifact's full bonus is a real, additive term on top of Inputs,
    rolled up into the aggregate bucket rows at the bottom — verbatim structure from
    build_fp_mage_workbook.py's own build_artifacts_sheet, since Artifacts are account-wide."""
    ws = wb.create_sheet("Artifacts")
    ws["A1"] = "Arch Mage (Ice/Lightning) — Artifacts (Equip Effect)"
    ws["A1"].font = Font(bold=True, size=14)

    r = ART_ROW
    eq = {k: IB(f"{k}_equipped") for k in ARTIFACT_LABELS}
    star = {k: IB(f"{k}_star") for k in ARTIFACT_LABELS}

    ws.cell(row=r["boa_crit_damage"], column=1, value="Book of Ancient — Crit Damage (from Crit Rate, reference only)")
    ws.cell(row=r["boa_crit_damage"], column=2, value=(
        f'=IF({eq["book_of_ancient"]},{star_lookup_expr(star["book_of_ancient"], "book_of_ancient_crit_damage_pct_of_crit_rate")}/100'
        f'*({IB("crit_rate")}+B{r["roc_crit_rate"]}+B{r["rainbow_crit_rate"]}),0)'
    ))

    ws.cell(row=r["roc_threshold_cr"], column=1, value="Ring of Cycles — Threshold Crit Rate (excl. self)")
    ws.cell(row=r["roc_threshold_cr"], column=2, value=f'={IB("crit_rate")}+B{r["rainbow_crit_rate"]}')
    ws.cell(row=r["roc_crit_rate"], column=1, value="Ring of Cycles — Crit Rate (if threshold < 100%)")
    ws.cell(row=r["roc_crit_rate"], column=2, value=(
        f'=IF(AND({eq["ring_of_cycles"]},B{r["roc_threshold_cr"]}<100),'
        f'{star_lookup_expr(star["ring_of_cycles"], "ring_of_cycles_crit_rate")},0)'
    ))
    ws.cell(row=r["roc_skill_damage"], column=1, value="Ring of Cycles — Skill Damage (if threshold >= 100%)")
    ws.cell(row=r["roc_skill_damage"], column=2, value=(
        f'=IF(AND({eq["ring_of_cycles"]},B{r["roc_threshold_cr"]}>=100),'
        f'{star_lookup_expr(star["ring_of_cycles"], "ring_of_cycles_skill_damage")},0)'
    ))
    ws.cell(row=r["roc_excess_points"], column=1, value="Ring of Cycles — Excess-100% Points (capped at 100)")
    ws.cell(row=r["roc_excess_points"], column=2, value=(
        f'=IF(AND({eq["ring_of_cycles"]},B{r["roc_threshold_cr"]}>=100),'
        f'MIN(100,B{r["roc_threshold_cr"]}-100),0)'
    ))
    ws.cell(row=r["roc_basic_attack_damage"], column=1, value="Ring of Cycles — Basic Attack Damage (excess points x per-point)")
    ws.cell(row=r["roc_basic_attack_damage"], column=2, value=(
        f'=B{r["roc_excess_points"]}*{star_lookup_expr(star["ring_of_cycles"], "ring_of_cycles_basic_attack_damage_per_point")}'
    ))

    fda = fixed_duration_active_expr(IB("monster_type"), IB("fight_duration"))
    ws.cell(row=r["candle_eff_duration"], column=1, value="Candle — Effective Fight Duration")
    ws.cell(row=r["candle_eff_duration"], column=2, value=(
        f'=IF({IB("monster_type")}="pvp",{PVP_FIGHT_DURATION},{IB("fight_duration")})'
    ))
    ws.cell(row=r["candle_eff_active"], column=1, value="Candle — Effective Active (fixed-duration or PvP)")
    ws.cell(row=r["candle_eff_active"], column=2, value=f'=IF({IB("monster_type")}="pvp",TRUE,{fda})')
    ws.cell(row=r["candle_final_damage"], column=1, value="Candle — Final Damage (100% uptime, patched)")
    ws.cell(row=r["candle_final_damage"], column=2, value=(
        f'=IF(AND({eq["candle"]},B{r["candle_eff_active"]}),'
        f'{star_lookup_expr(star["candle"], "candle_final_damage")},0)'
    ))
    ws.cell(row=r["candle_boss_appear_time"], column=1, value="Candle — Boss Appear Time (Breakthrough/Hero Dungeon only)")
    ws.cell(row=r["candle_boss_appear_time"], column=2, value=(
        f'=IF({IB("content_type")}="Breakthrough",20,IF({IB("content_type")}="Hero Dungeon",30,0))'
    ))
    ws.cell(row=r["candle_boss_damage"], column=1, value=(
        "Candle — Boss Monster Damage (20-40s window / boss-present-time uptime, patched)"
    ))
    ws.cell(row=r["candle_boss_damage"], column=2, value=(
        f'=IF(AND({eq["candle"]},B{r["candle_eff_active"]}),'
        f'MAX(0,MIN(40,B{r["candle_eff_duration"]})-MAX(20,B{r["candle_boss_appear_time"]}))'
        f'/(B{r["candle_eff_duration"]}-B{r["candle_boss_appear_time"]})'
        f'*{star_lookup_expr(star["candle"], "candle_boss_damage")},0)'
    ))

    ws.cell(row=r["peach_lambda"], column=1, value="Peach Tree Herb Pouch — Proc Rate (per second)")
    ws.cell(row=r["peach_lambda"], column=2, value=f'=0.2*Summary!$B${SUMMARY_ROW["APS"]}')
    ws.cell(row=r["peach_uptime"], column=1, value="Peach Tree Herb Pouch — Uptime (refreshing 5s timer)")
    ws.cell(row=r["peach_uptime"], column=2, value=f'=1-EXP(-B{r["peach_lambda"]}*5)')
    ws.cell(row=r["peach_enemy_dmg_taken"], column=1, value="Peach Tree Herb Pouch — Enemy Damage Taken")
    ws.cell(row=r["peach_enemy_dmg_taken"], column=2, value=(
        f'=IF(AND({eq["peach_tree"]},{IB("content_type")}<>"Chapter Hunt"),'
        f'{star_lookup_expr(star["peach_tree"], "peach_tree_enemy_dmg_taken")}*B{r["peach_uptime"]},0)'
    ))

    ws.cell(row=r["silver_rho"], column=1, value="Silver Pendant — Offered Load (rho = lambda x duration)")
    ws.cell(row=r["silver_rho"], column=2, value=f'=0.15*Summary!$B${SUMMARY_ROW["APS"]}*5')
    weight_rows = ["silver_w0", "silver_w1", "silver_w2", "silver_w3", "silver_w4", "silver_w5"]
    factorials = [1, 1, 2, 6, 24, 120]
    for n, (wkey, fact) in enumerate(zip(weight_rows, factorials)):
        ws.cell(row=r[wkey], column=1, value=f"Silver Pendant — Erlang Loss Weight (n={n})")
        ws.cell(row=r[wkey], column=2, value=f'=B{r["silver_rho"]}^{n}/{fact}')
    weight_sum = "+".join(f'B{r[w]}' for w in weight_rows)
    weighted_sum = "+".join(f'{n}*B{r[w]}' for n, w in enumerate(weight_rows))
    ws.cell(row=r["silver_avg_stacks"], column=1, value="Silver Pendant — Average Stacks (Erlang-loss mean)")
    ws.cell(row=r["silver_avg_stacks"], column=2, value=f'=({weighted_sum})/({weight_sum})')
    ws.cell(row=r["silver_enemy_dmg_taken"], column=1, value="Silver Pendant — Enemy Damage Taken")
    ws.cell(row=r["silver_enemy_dmg_taken"], column=2, value=(
        f'=IF(AND({eq["silver_pendant"]},{IB("content_type")}<>"Chapter Hunt"),'
        f'{star_lookup_expr(star["silver_pendant"], "silver_pendant_enemy_dmg_taken")}*B{r["silver_avg_stacks"]},0)'
    ))

    ws.cell(row=r["athena_max_damage"], column=1, value="Athena Pierce's Old Gloves — Max Damage (from Attack Speed, reference only)")
    ws.cell(row=r["athena_max_damage"], column=2, value=(
        f'=IF({eq["athena_gloves"]},{star_lookup_expr(star["athena_gloves"], "athena_gloves_max_damage_pct_of_attack_speed")}/100'
        f'*{IB("attack_speed")},0)'
    ))

    eff_d = f'IF({IB("monster_type")}="pvp",{PVP_FIGHT_DURATION},{IB("fight_duration")})'
    steady_state = f'AND({IB("monster_type")}<>"pvp",{IB("fight_duration")}=0)'
    ws.cell(row=r["hexagon_avg_stacks"], column=1, value="Hexagon Necklace — Average Stacks")
    ws.cell(row=r["hexagon_avg_stacks"], column=2, value=(
        f'=IF({steady_state},3,'
        f'IF({eff_d}<=20,0,'
        f'IF({eff_d}<=40,({eff_d}-20)/{eff_d},'
        f'IF({eff_d}<=60,(2*{eff_d}-60)/{eff_d},'
        f'(3*{eff_d}-120)/{eff_d}))))'
    ))
    ws.cell(row=r["hexagon_damage"], column=1, value="Hexagon Necklace — Damage %")
    ws.cell(row=r["hexagon_damage"], column=2, value=(
        f'=IF({eq["hexagon_necklace"]},{star_lookup_expr(star["hexagon_necklace"], "hexagon_necklace_damage")}*B{r["hexagon_avg_stacks"]},0)'
    ))

    ws.cell(row=r["rainbow_uptime"], column=1, value="Rainbow-colored Snail Shell — Uptime (0-15s window)")
    ws.cell(row=r["rainbow_uptime"], column=2, value=(
        f'=IF({IB("monster_type")}="pvp",MIN(15,{PVP_FIGHT_DURATION})/{PVP_FIGHT_DURATION},'
        f'IF({fda},MIN(15,{IB("fight_duration")})/{IB("fight_duration")},0))'
    ))
    ws.cell(row=r["rainbow_crit_rate"], column=1, value="Rainbow-colored Snail Shell — Crit Rate")
    ws.cell(row=r["rainbow_crit_rate"], column=2, value=(
        f'=IF({eq["rainbow_snail_shell"]},{star_lookup_expr(star["rainbow_snail_shell"], "rainbow_snail_shell_crit_rate")}*B{r["rainbow_uptime"]},0)'
    ))
    ws.cell(row=r["rainbow_crit_damage"], column=1, value="Rainbow-colored Snail Shell — Crit Damage")
    ws.cell(row=r["rainbow_crit_damage"], column=2, value=(
        f'=IF({eq["rainbow_snail_shell"]},{star_lookup_expr(star["rainbow_snail_shell"], "rainbow_snail_shell_crit_damage")}*B{r["rainbow_uptime"]},0)'
    ))

    ws.cell(row=r["csw_reference"], column=1, value="Clear Spring Water — Final Damage (reference only, Growth Dungeon types)")
    ws.cell(row=r["csw_reference"], column=2, value="=" + artifact_clear_spring_water_reference_expr(
        eq["clear_spring_water"], IB("content_type"), star["clear_spring_water"],
    ))

    ws.cell(row=r["old_music_box_attack_pct"], column=1, value="Old Music Box — Attack % (content-type uptime assumption)")
    ws.cell(row=r["old_music_box_attack_pct"], column=2, value="=" + artifact_old_music_box_expr(
        eq["old_music_box"], IB("content_type"), star["old_music_box"],
    ))

    ws.cell(row=r["soul_contract_pct"], column=1, value="Soul Contract — Skill Cooldown Decrease % (Chapter Hunt only)")
    ws.cell(row=r["soul_contract_pct"], column=2, value="=" + artifact_soul_contract_pct_expr(
        eq["soul_contract"], IB("content_type"), star["soul_contract"],
    ))

    ws.cell(row=r["soul_pouch_reference"], column=1, value="Soul Pouch — Final Damage (reference only, PvP/\"Arena\")")
    ws.cell(row=r["soul_pouch_reference"], column=2, value="=" + artifact_soul_pouch_reference_expr(
        eq["soul_pouch"], IB("monster_type"), star["soul_pouch"],
    ))

    ws.cell(row=r["flaming_lava"], column=1, value="Flaming Lava — Final Damage (always assumes target is debuffed)")
    ws.cell(row=r["flaming_lava"], column=2, value="=" + artifact_flaming_lava_expr(eq["flaming_lava"], star["flaming_lava"], IB("content_type")))

    ws.cell(row=r["icy_soul_rock"], column=1, value="Icy Soul Rock — Crit Damage (1.5x-averaged, MP not modeled)")
    ws.cell(row=r["icy_soul_rock"], column=2, value="=" + artifact_icy_soul_rock_expr(eq["icy_soul_rock"], star["icy_soul_rock"]))

    secret_map_attack_pct_expr, secret_map_final_dmg_normal_expr = artifact_secret_map_exprs(
        eq["secret_map"], IB("monster_type"), IB("content_type"), star["secret_map"],
    )
    ws.cell(row=r["secret_map_attack_pct"], column=1, value="Secret Map — Attack %")
    ws.cell(row=r["secret_map_attack_pct"], column=2, value="=" + secret_map_attack_pct_expr)
    ws.cell(row=r["secret_map_final_dmg_normal"], column=1, value="Secret Map — Final Damage (normal-monster branch only)")
    ws.cell(row=r["secret_map_final_dmg_normal"], column=2, value="=" + secret_map_final_dmg_normal_expr)

    ws.cell(row=r["reindeer_spear_attack_pct"], column=1, value="Reindeer's Spear — Attack %")
    ws.cell(row=r["reindeer_spear_attack_pct"], column=2, value="=" + artifact_reindeer_spear_attack_pct_expr(
        eq["reindeer_spear"], star["reindeer_spear"],
    ))
    ws.cell(row=r["reindeer_spear_base_def_pen_reference"], column=1, value="Reindeer's Spear — Base (1x) Defense Penetration (reference only)")
    ws.cell(row=r["reindeer_spear_base_def_pen_reference"], column=2, value="=" + artifact_reindeer_spear_base_def_pen_reference_expr(
        eq["reindeer_spear"], star["reindeer_spear"],
    ))

    ws.cell(row=r["cursed_doll_reference"], column=1, value="Cursed Doll — Final Damage (reference only)")
    ws.cell(row=r["cursed_doll_reference"], column=2, value="=" + artifact_cursed_doll_reference_expr(
        eq["cursed_doll"], star["cursed_doll"],
    ))

    ws.cell(row=r["horn_flute"], column=1, value="Horn Flute — Final Damage (character's own portion only)")
    ws.cell(row=r["horn_flute"], column=2, value="=" + artifact_horn_flute_expr(
        eq["horn_flute"], IB("monster_type"), IB("content_type"), IB("fight_duration"), star["horn_flute"],
    ))

    ws.cell(row=r["bottle_of_emotion_attack_pct"], column=1, value="Bottle of Emotion — Attack %")
    ws.cell(row=r["bottle_of_emotion_attack_pct"], column=2, value="=" + artifact_bottle_of_emotion_attack_pct_expr(
        eq["bottle_of_emotion"], star["bottle_of_emotion"],
    ))
    ws.cell(row=r["bottle_of_emotion_final_damage_reference"], column=1, value=(
        "Bottle of Emotion — Final Damage from Attack Speed (reference only)"
    ))
    ws.cell(row=r["bottle_of_emotion_final_damage_reference"], column=2, value="=" + artifact_bottle_of_emotion_final_damage_value_expr(
        eq["bottle_of_emotion"], star["bottle_of_emotion"], IB("attack_speed"),
    ))

    ws.cell(row=r["alliance_badge"], column=1, value="Alliance Badge — Attack %")
    ws.cell(row=r["alliance_badge"], column=2, value="=" + artifact_alliance_badge_expr(
        eq["alliance_badge"], star["alliance_badge"],
    ))

    sayrams_normal_expr, sayrams_boss_expr = artifact_sayrams_necklace_exprs(eq["sayrams_necklace"], star["sayrams_necklace"])
    ws.cell(row=r["sayrams_necklace_normal"], column=1, value="Sayram's Necklace — Normal Monster Damage")
    ws.cell(row=r["sayrams_necklace_normal"], column=2, value="=" + sayrams_normal_expr)
    ws.cell(row=r["sayrams_necklace_boss"], column=1, value="Sayram's Necklace — Boss Monster Damage")
    ws.cell(row=r["sayrams_necklace_boss"], column=2, value="=" + sayrams_boss_expr)

    ws.cell(row=r["lit_lamp_reference"], column=1, value="Lit Lamp — Final Damage (reference only, World Boss)")
    ws.cell(row=r["lit_lamp_reference"], column=2, value="=" + artifact_lit_lamp_reference_expr(
        eq["lit_lamp"], IB("content_type"), star["lit_lamp"],
    ))

    fire_flower_normal_expr, fire_flower_boss_expr = artifact_fire_flower_exprs(eq["fire_flower"], star["fire_flower"])
    ws.cell(row=r["fire_flower_normal"], column=1, value="Fire Flower — Final Damage (normal-monster branch, 10 targets assumed)")
    ws.cell(row=r["fire_flower_normal"], column=2, value="=" + fire_flower_normal_expr)
    ws.cell(row=r["fire_flower_boss"], column=1, value="Fire Flower — Final Damage (boss/PvP branch, 1 target assumed)")
    ws.cell(row=r["fire_flower_boss"], column=2, value="=" + fire_flower_boss_expr)

    ws.cell(row=r["star_rock_reference"], column=1, value="Star Rock — Boss Monster Damage (reference only)")
    ws.cell(row=r["star_rock_reference"], column=2, value="=" + artifact_star_rock_reference_expr(
        eq["star_rock"], star["star_rock"],
    ))

    chalice_normal_expr, chalice_boss_expr = artifact_chalice_exprs(
        eq["chalice"], IB("monster_type"), IB("content_type"), IB("fight_duration"), star["chalice"],
    )
    ws.cell(row=r["chalice_normal"], column=1, value="Chalice — Final Damage (normal-monster branch)")
    ws.cell(row=r["chalice_normal"], column=2, value="=" + chalice_normal_expr)
    ws.cell(row=r["chalice_boss"], column=1, value="Chalice — Final Damage (boss branch)")
    ws.cell(row=r["chalice_boss"], column=2, value="=" + chalice_boss_expr)

    ws.cell(row=r["contract_of_darkness_crit_rate_bonus"], column=1, value="The Contract of Darkness — Crit Rate (boss branch only)")
    ws.cell(row=r["contract_of_darkness_crit_rate_bonus"], column=2, value="=" + artifact_contract_of_darkness_crit_rate_bonus_expr(
        eq["contract_of_darkness"], IB("monster_type"), star["contract_of_darkness"],
    ))

    ws.cell(row=r["shamaness_marble_reference"], column=1, value="Shamaness Marble — Buff Duration Increase % (reference only)")
    ws.cell(row=r["shamaness_marble_reference"], column=2, value="=" + artifact_shamaness_marble_reference_expr(
        eq["shamaness_marble"], star["shamaness_marble"],
    ))

    ws.cell(row=r["charm_of_the_undead"], column=1, value="Charm of the Undead — Attack % (periodic uptime)")
    ws.cell(row=r["charm_of_the_undead"], column=2, value="=" + artifact_charm_of_the_undead_expr(
        eq["charm_of_the_undead"], IB("monster_type"), IB("fight_duration"), star["charm_of_the_undead"],
    ))

    for zero_key, zero_label in [
        ("ancient_text_piece_reference", "Ancient Text Piece — always 0 (Guild Conquest not modeled)"),
        ("lunar_dew_reference", "Lunar Dew — always 0 (no attacking effect)"),
        ("pink_beans_giant_rib_reference", "Pink Bean's Giant Rib — always 0 (raid content not modeled)"),
        ("horntails_scale_reference", "Horntail's Scale — always 0 (raid content not modeled)"),
        ("zakums_stone_piece_reference", "Zakum's Stone Piece — always 0 (raid content not modeled)"),
        ("mushmoms_cap_reference", "Mushmom's Cap — always 0 (Accuracy-vs-Evasion not modeled)"),
        ("arwens_glass_shoes_reference", "Arwen's Glass Shoes — always 0 (companions not modeled)"),
        ("pigs_ribbon_reference", "Pig's Ribbon — always 0 (no attacking effect)"),
    ]:
        ws.cell(row=r[zero_key], column=1, value=zero_label)
        ws.cell(row=r[zero_key], column=2, value=0)

    ws.cell(row=r["AGG_CRIT_RATE"], column=1, value="TOTAL — Artifact Crit Rate Bonus").font = LABEL_FONT
    ws.cell(row=r["AGG_CRIT_RATE"], column=2, value=f'=B{r["roc_crit_rate"]}+B{r["rainbow_crit_rate"]}').font = LABEL_FONT
    ws.cell(row=r["AGG_CRIT_DAMAGE"], column=1, value="TOTAL — Artifact Crit Damage Bonus").font = LABEL_FONT
    ws.cell(row=r["AGG_CRIT_DAMAGE"], column=2, value=f'=B{r["rainbow_crit_damage"]}+B{r["icy_soul_rock"]}').font = LABEL_FONT
    ws.cell(row=r["AGG_FINAL_DAMAGE"], column=1, value=(
        "TOTAL — Artifact Final Damage Bonus (equivalent %, each real source combines "
        "MULTIPLICATIVELY — Candle x Flaming Lava x Horn Flute, not summed)"
    )).font = LABEL_FONT
    ws.cell(row=r["AGG_FINAL_DAMAGE"], column=2, value=(
        f'=((1+B{r["candle_final_damage"]}/100)*(1+B{r["flaming_lava"]}/100)*(1+B{r["horn_flute"]}/100)-1)*100'
    )).font = LABEL_FONT
    ws.cell(row=r["AGG_BOSS_DAMAGE"], column=1, value="TOTAL — Artifact Boss Monster Damage Bonus").font = LABEL_FONT
    ws.cell(row=r["AGG_BOSS_DAMAGE"], column=2, value=f'=B{r["candle_boss_damage"]}+B{r["sayrams_necklace_boss"]}').font = LABEL_FONT
    ws.cell(row=r["AGG_NORMAL_DAMAGE"], column=1, value="TOTAL — Artifact Normal Monster Damage Bonus").font = LABEL_FONT
    ws.cell(row=r["AGG_NORMAL_DAMAGE"], column=2, value=f'=B{r["sayrams_necklace_normal"]}').font = LABEL_FONT
    ws.cell(row=r["AGG_ENEMY_DMG_TAKEN"], column=1, value="TOTAL — Artifact Enemy Damage Taken Bonus").font = LABEL_FONT
    ws.cell(row=r["AGG_ENEMY_DMG_TAKEN"], column=2, value=f'=B{r["peach_enemy_dmg_taken"]}+B{r["silver_enemy_dmg_taken"]}').font = LABEL_FONT
    ws.cell(row=r["AGG_DAMAGE"], column=1, value=(
        "TOTAL — Artifact Damage Bonus (own separate final multiplier — not blended into Inputs!DAMAGE%)"
    )).font = LABEL_FONT
    ws.cell(row=r["AGG_DAMAGE"], column=2, value=f'=B{r["hexagon_damage"]}').font = LABEL_FONT
    ws.cell(row=r["AGG_ATTACK_PCT"], column=1, value=(
        "TOTAL — Artifact Attack % Bonus (Old Music Box/Secret Map/Reindeer's Spear/Alliance "
        "Badge/Bottle of Emotion/Charm of the Undead)"
    )).font = LABEL_FONT
    ws.cell(row=r["AGG_ATTACK_PCT"], column=2, value=(
        f'=B{r["old_music_box_attack_pct"]}+B{r["secret_map_attack_pct"]}+B{r["reindeer_spear_attack_pct"]}'
        f'+B{r["alliance_badge"]}+B{r["bottle_of_emotion_attack_pct"]}+B{r["charm_of_the_undead"]}'
    )).font = LABEL_FONT
    ws.cell(row=r["AGG_FINAL_DAMAGE_NORMAL_ONLY"], column=1, value=(
        "TOTAL — Artifact Final Damage Bonus, NORMAL-MONSTER BRANCH ONLY (Secret Map/Fire Flower/Chalice)"
    )).font = LABEL_FONT
    ws.cell(row=r["AGG_FINAL_DAMAGE_NORMAL_ONLY"], column=2, value=(
        f'=B{r["secret_map_final_dmg_normal"]}+B{r["fire_flower_normal"]}+B{r["chalice_normal"]}'
    )).font = LABEL_FONT
    ws.cell(row=r["AGG_FINAL_DAMAGE_BOSS_ONLY"], column=1, value=(
        "TOTAL — Artifact Final Damage Bonus, BOSS BRANCH ONLY (Fire Flower/Chalice)"
    )).font = LABEL_FONT
    ws.cell(row=r["AGG_FINAL_DAMAGE_BOSS_ONLY"], column=2, value=(
        f'=B{r["fire_flower_boss"]}+B{r["chalice_boss"]}'
    )).font = LABEL_FONT
    ws.cell(row=r["AGG_SKILL_DAMAGE"], column=1, value="TOTAL — Artifact Skill Damage Bonus").font = LABEL_FONT
    ws.cell(row=r["AGG_SKILL_DAMAGE"], column=2, value=f'=B{r["roc_skill_damage"]}').font = LABEL_FONT
    ws.cell(row=r["AGG_BASIC_ATTACK_DAMAGE"], column=1, value="TOTAL — Artifact Basic Attack Damage Bonus").font = LABEL_FONT
    ws.cell(row=r["AGG_BASIC_ATTACK_DAMAGE"], column=2, value=f'=B{r["roc_basic_attack_damage"]}').font = LABEL_FONT

    ws.column_dimensions["A"].width = 55
    ws.column_dimensions["B"].width = 16
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
    """Only for skill-intrinsic constants where a plain linear blend of the RAW VALUES is correct
    (e.g. Frozen Orb's boss/normal damage-multiplier constant) — NOT for Boss/Normal Monster
    Damage% or anything downstream of it (DPS), where the two branches must be kept independent
    until blended as RATIOS — see boss_normal_dps_split_exprs below."""
    return f'IF({monster_type_ref}="pvp",{pvp_expr},(1-{w_ref})*({boss_expr})+{w_ref}*({normal_expr}))'


def boss_normal_dps_split_exprs(prefix_expr, monster_type_ref, boss_dmg_pct_expr,
                                 normal_dmg_pct_expr, normal_targets_ref, max_enemies_ref,
                                 extra_boss_mult_expr="1", extra_normal_mult_expr="1"):
    """Splits a row's DPS into independent boss-only and normal-only values — see
    build_fp_mage_workbook.py's copy of this function for the full rationale.
    `extra_boss_mult_expr`/`extra_normal_mult_expr` (default "1", a no-op) are applied
    UNCONDITIONALLY, outside the `IF(pvp,1,...)` gating above — used for artifact bonuses
    (Reindeer's Spear/Contract of Darkness/Fire Flower/Chalice) that still apply in PvP."""
    capped_targets = f'MIN({normal_targets_ref},{max_enemies_ref})'
    boss_mult = f'IF({monster_type_ref}="pvp",1,1+({boss_dmg_pct_expr})/100)'
    normal_mult = f'IF({monster_type_ref}="pvp",1,(1+({normal_dmg_pct_expr})/100)*({capped_targets}))'
    return (
        f'({prefix_expr})*{boss_mult}*({extra_boss_mult_expr})',
        f'({prefix_expr})*{normal_mult}*({extra_normal_mult_expr})',
    )


def fixed_duration_active_expr(monster_type_ref, fight_duration_ref):
    return f'AND({monster_type_ref}<>"pvp",{fight_duration_ref}>0)'


def exact_casts_expr(duration_ref, cooldown_ref):
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
                             cooldown_ref, available_duration_ref, fight_duration_ref, steady_rate_ref):
    """`available_duration_ref` is the duration actually used to derive `row_ref`'s cast count —
    the raw fight duration for buffs, or the buff-casting-startup-delay-reduced window for non-buff
    (damage) skills — and must match, or the last cast's truncated tick window would be computed
    against a duration inconsistent with how many casts were actually counted."""
    exact_hits = exact_total_hits_expr(row_ref, hits_ref, icd_ref, window_ref, cooldown_ref, available_duration_ref)
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
    "AVG_BUFF_MULT": 13,
    "MONSTER_DMG_BONUS": 14,
    "DAMAGE_BONUS": 15,
    "AS_BONUS": 16,
    "APS": 17,
    "CAST_RATE": 18,
    "BASIC_ATTACKS_PER_SEC": 19,
    "TOTAL_DPS": 3,
    "BASIC_ATTACK_DPS": 20,
    "STARTUP_TIME": 21,
    "BOSS_ONLY_TOTAL": 22,
    "NORMAL_ONLY_TOTAL": 23,
}
# The two variable-length summary tables (Per-Skill Breakdown, sized off DAMAGE_DEALING_KEYS, and
# Marginal DPS & Stat Value, sized off STAT_SWEEP) start after this fixed block, with a 2-row gap.
BREAKDOWN_SECTION_ROW = SUMMARY_ROW["NORMAL_ONLY_TOTAL"] + 2


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

    # Frozen Orb's single-target (boss/pvp) halving is now applied directly inside its own
    # boss/normal branch split (see the FROZEN_ORB case below) rather than as a shared w-blended
    # scalar here — folding a per-branch-dependent 0.5/1.0 multiplier into a value multiplied by
    # BOTH branches equally would reintroduce the exact cross-branch contamination this fix
    # removes elsewhere (see Bishop's ANGEL_RAY_BOSS_PROC comment for the detailed rationale).


    for key, r in ROW.items():
        ws.cell(row=r, column=1, value=f"={S('Key', r)}")
        ws.cell(row=r, column=2, value=f"={S('Name', r)}")
        ws.cell(row=r, column=3, value=unlock_expr(key))

        eff_cd_r = (
            f'({effective_cooldown_expr(IB("monster_type"), S("Cooldown(s)", r), IB("skill_cooldown_decrease"), S("CostsActionSlot", CDR_COSTS_ACTION_ROW[key]))}'
            f'*(1-{artifact_soul_contract_pct_expr(IB("soul_contract_equipped"), IB("content_type"), IB("soul_contract_star"))}/100))'
        )
        # Duration actually available for this row's casts in fixed-duration mode: the raw fight
        # duration for buffs (unaffected by the startup delay they themselves cause), or that
        # duration reduced by Summary!STARTUP_TIME for non-buff (damage) rows, since they can't
        # start until every buff has been cast once. Must match whatever CastsInFight (column R,
        # below) uses, or the last cast's truncated tick window (rate_r) would be computed against
        # an inconsistent duration.
        if key in BUFF_ROW_KEYS:
            available_duration_r = IB("fight_duration")
        else:
            available_duration_r = f'MAX(0,{IB("fight_duration")}-Summary!$B${SUMMARY_ROW["STARTUP_TIME"]})'
        rate_r = rate_or_exact_hits_expr(
            fixed_duration_active_main, f"R{r}", S("HitsPerCast", r), S("ICD(s)", r),
            S("ActiveWindow(s)", r), eff_cd_r, available_duration_r, IB("fight_duration"), f"G{r}*Q{r}",
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
            max_damage_total_r = f'{IB("max_damage")}'
            crit_rate_total_r = f'({IB("crit_rate")}+{art_ref("AGG_CRIT_RATE")})'
            ws.cell(row=r, column=11, value=(
                f'=J{r}*(1+{IB("stat_damage")}/100)'
                f'*(1+({IB("damage")}+Summary!$B${SUMMARY_ROW["DAMAGE_BONUS"]})/100)'
                f'*(1+{IB("damage_amp")}/100)'
                f'*(5000/(6000+{IB("monster_defense")}*(1-{IB("def_pen")}/100)))'
                f'*(1+{IB("final_damage")}/100)*(1+{art_ref("AGG_FINAL_DAMAGE")}/100)*(1+{elem_amp_gated}/100)'
                f'*(1+{arcane_aim_gated}/100)^5'
                f'*(1+(IF({S("Key", r)}="CHAIN_LIGHTNING",{IB("basic_attack_damage")}+{art_ref("AGG_BASIC_ATTACK_DAMAGE")},'
                f'{IB("skill_damage")}+{art_ref("AGG_SKILL_DAMAGE")}))/100)'
                f'*(Summary!$B${SUMMARY_ROW["AVG_BUFF_MULT"]}*(1+{art_ref("AGG_DAMAGE")}/100)*I{r})'
            ))
            ws.cell(row=r, column=12, value=f'=K{r}*(MIN({IB("min_damage")},{max_damage_total_r})/100+{max_damage_total_r}/100)/2')
            ws.cell(row=r, column=13, value=f'=L{r}*(1+({IB("crit_damage")}+{art_ref("AGG_CRIT_DAMAGE")})/100)')
            ws.cell(row=r, column=14, value=(
                f'=L{r}*(1-MIN({crit_rate_total_r},100)/100)+M{r}*(MIN({crit_rate_total_r},100)/100)'
            ))
        else:
            for col in (10, 11, 12, 13, 14):
                ws.cell(row=r, column=col, value="")

        boss_dmg_pct_r = (
            f'{IB("boss_damage")}+{S("MasteryBossDamage%", r)}+Summary!$B${SUMMARY_ROW["MONSTER_DMG_BONUS"]}'
            f'+{art_ref("AGG_BOSS_DAMAGE")}'
        )
        normal_dmg_pct_r = (
            f'{IB("normal_damage")}+{S("MasteryNormalDamage%", r)}+Summary!$B${SUMMARY_ROW["MONSTER_DMG_BONUS"]}'
            f'+{art_ref("AGG_NORMAL_DAMAGE")}'
        )

        # Reindeer's Spear — only its BASE (1x) Defense Penetration is baked into Inputs!def_pen;
        # the extra multiple beyond that (1 more for PvP's 2x total, 2 more for boss's 3x total) is
        # a real, live, boss/PvP-branch-only correction ratio — see build_fp_mage_workbook.py's own
        # copy of this block for the full rationale (Defense Penetration combines via diminishing
        # returns, never additive).
        _def_pen_baseline_r = IB("def_pen")
        _reindeer_s_r = art_ref("reindeer_spear_base_def_pen_reference")
        _def_pen_boss_r = (
            f'(100*(1-(1-{_def_pen_baseline_r}/100)*(1-{_reindeer_s_r}/100)^'
            f'{artifact_reindeer_spear_extra_mult_expr(IB("monster_type"))}))'
        )
        _spear_def_ratio_r = (
            f'((5000/(6000+{IB("monster_defense")}*(1-{_def_pen_boss_r}/100)))'
            f'/(5000/(6000+{IB("monster_defense")}*(1-{_def_pen_baseline_r}/100))))'
        )
        # The Contract of Darkness — boss-branch-only Crit Rate, composed via a ratio between two
        # evaluations of this row's own crit-blend formula (N = L*(1-cr/100)+M*(cr/100)), only
        # valid for damage-dealing rows (where crit_rate_total_r/L/M were just freshly set above).
        if key == "CHAIN_LIGHTNING" or key in DAMAGE_ROW_KEYS:
            _cr_baseline_r = f'MIN(100,{crit_rate_total_r})'
            _cr_boss_r = f'MIN(100,{crit_rate_total_r}+{art_ref("contract_of_darkness_crit_rate_bonus")})'
            _cod_crit_ratio_r = (
                f'((L{r}*(1-{_cr_boss_r}/100)+M{r}*({_cr_boss_r}/100))'
                f'/(L{r}*(1-{_cr_baseline_r}/100)+M{r}*({_cr_baseline_r}/100)))'
            )
        else:
            _cod_crit_ratio_r = "1"
        extra_boss_mult_r = (
            f'({_spear_def_ratio_r}*{_cod_crit_ratio_r}*(1+{art_ref("AGG_FINAL_DAMAGE_BOSS_ONLY")}/100))'
        )
        extra_normal_mult_r = f'(1+{art_ref("AGG_FINAL_DAMAGE_NORMAL_ONLY")}/100)'

        if key == "CHAIN_LIGHTNING":
            prefix = f"{S('HitsPerCast', r)}*N{r}*Summary!$B${SUMMARY_ROW['BASIC_ATTACKS_PER_SEC']}"
            boss_expr, normal_expr = boss_normal_dps_split_exprs(
                prefix, IB("monster_type"), boss_dmg_pct_r, normal_dmg_pct_r,
                S("NormalMonsterTargets", r), IB("max_enemies_hit"),
                extra_boss_mult_r, extra_normal_mult_r,
            )
            ws.cell(row=r, column=19, value=f'=IF(C{r},{boss_expr},0)')
            ws.cell(row=r, column=21, value=f'=IF(C{r},{normal_expr},0)')
        elif key == "FROZEN_ORB":
            # Frozen Orb's own boss/normal damage-multiplier constant (0.5 vs single target,
            # 1.0 vs normal-monster AoE) must be applied INSIDE each branch, not as a shared
            # w-blended scalar multiplied on top — otherwise it reintroduces the same
            # blend-then-multiply mismatch this whole fix removes elsewhere (see
            # build_fp_mage_workbook.py's ANGEL_RAY_BOSS_PROC-equivalent comment in Bishop for the
            # detailed rationale of why that's wrong). extra_boss_mult_r/extra_normal_mult_r are
            # multiplied in directly here too, since this branch bypasses boss_normal_dps_split_exprs.
            frozen_orb_boss_mult = f'IF({IB("monster_type")}="pvp",1,1+({boss_dmg_pct_r})/100)'
            frozen_orb_normal_mult = (
                f'IF({IB("monster_type")}="pvp",1,(1+({normal_dmg_pct_r})/100)'
                f'*(MIN({S("NormalMonsterTargets", r)},{IB("max_enemies_hit")})))'
            )
            ws.cell(row=r, column=19, value=(
                f'=IF(C{r},H{r}*N{r}*{rate_r}*0.5*{frozen_orb_boss_mult}*{extra_boss_mult_r},0)'
            ))
            ws.cell(row=r, column=21, value=(
                f'=IF(C{r},H{r}*N{r}*{rate_r}*1*{frozen_orb_normal_mult}*{extra_normal_mult_r},0)'
            ))
        elif key in DAMAGE_ROW_KEYS:
            prefix = f'H{r}*N{r}*{rate_r}'
            boss_expr, normal_expr = boss_normal_dps_split_exprs(
                prefix, IB("monster_type"), boss_dmg_pct_r, normal_dmg_pct_r,
                S("NormalMonsterTargets", r), IB("max_enemies_hit"),
                extra_boss_mult_r, extra_normal_mult_r,
            )
            ws.cell(row=r, column=19, value=f'=IF(C{r},{boss_expr},0)')
            ws.cell(row=r, column=21, value=f'=IF(C{r},{normal_expr},0)')
        else:
            ws.cell(row=r, column=19, value=0)
            ws.cell(row=r, column=21, value=0)

        ws.cell(row=r, column=15, value=f'=(1-{IB("normal_weight_frac")})*S{r}+{IB("normal_weight_frac")}*U{r}')

        ws.cell(row=r, column=16, value=f'=IF(Summary!$B${SUMMARY_ROW["TOTAL_DPS"]}=0,0,O{r}/Summary!$B${SUMMARY_ROW["TOTAL_DPS"]})')

        # Safe per-row reciprocal cooldown (see build_fp_mage_workbook.py's own comment on this
        # exact cell for why a bare IFERROR(1/x) is used instead of nesting it inside SUMPRODUCT).
        ws.cell(row=r, column=17, value=f'=IFERROR(1/{eff_cd_r},0)')

        if ROW_HAS_COOLDOWN[key]:
            casts_formula = guarded_casts_expr(available_duration_r, eff_cd_r)
            ws.cell(row=r, column=18, value=f'=IF({fixed_duration_active_main},{casts_formula},0)')
        else:
            ws.cell(row=r, column=18, value=0)

    ws.cell(row=1, column=17, value="InvCooldown")
    ws.cell(row=1, column=18, value="CastsInFight")
    ws.cell(row=1, column=19, value="BossOnlyDPS")
    ws.cell(row=1, column=21, value="NormalOnlyDPS")

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

    ws.cell(row=r_avgbuff, column=1, value="Average Buff Multiplier (Magic Guard + Meditation + Artifact Attack%, summed; then Infinity)")
    ws.cell(row=r_avgbuff, column=2, value=(
        # Magic Guard and Meditation are both "+X% Attack" sources — same bucket, so they sum into
        # one combined percentage before a single multiplication, instead of each compounding
        # against the other. Infinity is Final Damage, a different (and deliberately still
        # multiplicative) bucket, so it stays its own separate factor. Artifact Attack% (Old Music
        # Box/Secret Map/Reindeer's Spear/Alliance Badge/Bottle of Emotion/Charm of the Undead) is
        # the same kind of "+X% Attack" source, so it joins the same additive bucket.
        f'=(1+(IF(Calc!C{mg}=TRUE,Calc!F{mg}*{buff_uptime(mg)},0)'
        f'+IF(Calc!C{med}=TRUE,Calc!F{med}*{buff_uptime(med)},0)+{art_ref("AGG_ATTACK_PCT")})/100)'
        f'*IF(Calc!C{inf}=TRUE,(1+Calc!F{inf}*{buff_uptime(inf)}/100),1)'
    ))

    # Freezing Breath - Weaken (Mastery Lv.118): +15% Damage Taken debuff for 30s, tied to
    # Freezing Breath's own (patched) 40s cooldown — duty-cycle averaged (steady-state only, no
    # fixed-duration exactness, a documented simplification for this secondary mastery effect,
    # same tier as Night Lord's own Frailty Curse Lv.111 simplification). Elemental Reset's own
    # Damage Taken bonus is the SAME kind of bonus (target damage-taken%), so it's summed into
    # this same bucket rather than kept as its own separate multiplicative factor — Peach Tree/
    # Silver Pendant's Artifact Enemy Damage Taken bonus is exactly the same kind of bonus too
    # (ILM has no separate multiplicative "ED_MULT" bucket like FP-Mage's own Elemental Decrease,
    # so it joins this additive bucket instead — a genuine ILM-specific adaptation). Feeds into
    # both boss_dmg_pct_r/row and normal_dmg_pct_r/row additively (both branches).
    fb_cd = S("Cooldown(s)", ROW["FREEZING_BREATH"])
    ws.cell(row=r_mdb, column=1, value=(
        "Monster Damage Taken Bonus % (Freezing Breath - Weaken + Elemental Reset + Artifact "
        "Enemy Damage Taken, summed)"
    ))
    ws.cell(row=r_mdb, column=2, value=(
        f'=IF({IB("level")}>=118,15*{uptime_fraction_expr(IB("monster_type"), 30, fb_cd, bdi_main)},0)'
        f'+IF(Calc!C{ed}=TRUE,Calc!F{ed},0)+{art_ref("AGG_ENEMY_DMG_TAKEN")}'
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

    r_startup = SUMMARY_ROW["STARTUP_TIME"]
    ws.cell(row=r_startup, column=1, value=(
        "Buff-Casting Startup Delay (s, before first damage-skill cast; fixed-duration only)"
    ))
    ws.cell(row=r_startup, column=2, value="=" + buff_cast_startup_time_expr(
        fda_main, SC["BuffDuration(s)"], SC["CostsActionSlot"], f"Calc!C2:C{LAST_ROW}",
        f"B{r_aps}", LAST_ROW,
    ))

    ws.cell(row=r_total, column=1, value="TOTAL DPS").font = Font(bold=True, size=13)
    ws.cell(row=r_total, column=2, value=f"=SUM(Calc!O2:O{LAST_ROW})").font = Font(bold=True, size=13)

    r_bot, r_not = SUMMARY_ROW["BOSS_ONLY_TOTAL"], SUMMARY_ROW["NORMAL_ONLY_TOTAL"]
    ws.cell(row=r_bot, column=1, value="Boss-Only Total DPS (Sensitivity baseline)")
    ws.cell(row=r_bot, column=2, value=f"=SUM(Calc!S2:S{LAST_ROW})")
    ws.cell(row=r_not, column=1, value="Normal-Only Total DPS (Sensitivity baseline)")
    ws.cell(row=r_not, column=2, value=f"=SUM(Calc!U2:U{LAST_ROW})")

    ws.cell(row=r_basic, column=1, value="Chain Lightning DPS")
    ws.cell(row=r_basic, column=2, value=f"=Calc!O{ROW['CHAIN_LIGHTNING']}")

    ws.cell(row=BREAKDOWN_SECTION_ROW, column=1, value="Per-Skill DPS Breakdown").font = SECTION_FONT
    breakdown_header_row = BREAKDOWN_SECTION_ROW + 1
    ws.cell(row=breakdown_header_row, column=1, value="Skill")
    ws.cell(row=breakdown_header_row, column=2, value="DPS")
    ws.cell(row=breakdown_header_row, column=3, value="% of Total")
    style_header_row(ws, breakdown_header_row, 3)
    row_cursor = breakdown_header_row + 1
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
    for stat_key, stat_label, _kind in STAT_SWEEP_STAT_ENTRIES:
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
] + [
    (f"{art_key}_equipped", f"{art_label} (Equip)", "bool")
    for art_key, art_label in ARTIFACT_LABELS.items()
]

# Split for the Sensitivity sheet's two results tables (see build_sensitivity_sheet): continuous
# stats (where "Units per +1% DPS" is meaningful) get the full "Stat" table, boolean artifact
# equip-toggles get their own simpler "Artifact Equip-Toggle DPS Gain" table — verbatim mechanism
# from build_fp_mage_workbook.py. Every entry still gets its own full shadow calc block regardless
# of which table displays it — only the results-table presentation is split.
STAT_SWEEP_STAT_ENTRIES = [e for e in STAT_SWEEP if e[2] != "bool"]
STAT_SWEEP_ARTIFACT_ENTRIES = [e for e in STAT_SWEEP if e[2] == "bool"]
SENSITIVITY_ARTIFACT_TABLE_HEADER_ROWS = 2

# Absolute CDR values (seconds) swept by the Sensitivity sheet's CDR Milestone Sweep section
# (see build_sensitivity_sheet) — chosen by the user to cover the range where fixed-duration
# skill cast counts are likely to cross an INT()-floor threshold and jump.
CDR_SWEEP_VALUES = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]

SENSITIVITY_HEADER_ROW = 4
SENSITIVITY_ROW_FOR = {key: SENSITIVITY_HEADER_ROW + 1 + idx for idx, (key, _, _) in enumerate(STAT_SWEEP_STAT_ENTRIES)}

# Row constants for the Sensitivity sheet's 2nd ("Artifact Equip-Toggle DPS Gain") table, derived
# the same way build_sensitivity_sheet computes them locally — shared here so build_summary_sheet
# can reference the same (sorted) rows without duplicating the row math.
ARTIFACT_TABLE_TITLE_ROW = SENSITIVITY_HEADER_ROW + len(STAT_SWEEP_STAT_ENTRIES) + 1
ARTIFACT_TABLE_HEADER_ROW = ARTIFACT_TABLE_TITLE_ROW + 1
ARTIFACT_TABLE_FIRST_DATA_ROW = ARTIFACT_TABLE_HEADER_ROW + 1
ARTIFACT_TABLE_LAST_DATA_ROW = ARTIFACT_TABLE_HEADER_ROW + len(STAT_SWEEP_ARTIFACT_ENTRIES)

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
            f'=IF({IB("crit_rate")}+{art_ref("AGG_CRIT_RATE")}>=100,Sensitivity!H{SENSITIVITY_ROW_FOR["crit_damage"]},'
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
BLOCK_HEIGHT = LAST_ROW + 16
BLOCK_START = SENSITIVITY_HEADER_ROW + len(STAT_SWEEP) + SENSITIVITY_ARTIFACT_TABLE_HEADER_ROWS + 3


def override_expr_for(kind, key):
    base = IB(key)
    if kind == "dr150":
        return f'((1-(1-{base}/150)*(1-1/150))*150)'
    if kind == "dr100":
        return f'((1-(1-{base}/100)*(1-1/100))*100)'
    if kind == "mult":
        return f'((((1+{base}/100)*(1.01))-1)*100)'
    if kind == "bool":
        return f'IF({base},FALSE,TRUE)'
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
    s_startup = calc_end + 10
    s_boss_total = calc_end + 11
    s_normal_total = calc_end + 12
    s_total = calc_end + 13
    avgbuff_ref, mdb_ref = f"B{s_avgbuff}", f"B{s_mdb}"
    db_ref, asb_ref, aps_ref = f"B{s_db}", f"B{s_asb}", f"B{s_aps}"
    castrate_ref, baps_ref, total_ref = f"B{s_castrate}", f"B{s_baps}", f"B{s_total}"
    startup_ref = f"B{s_startup}"
    boss_total_ref, normal_total_ref = f"B{s_boss_total}", f"B{s_normal_total}"

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

    # Artifacts — block-local mirror of build_artifacts_sheet, so a swept stat correctly
    # propagates through whichever artifact depends on it, and so each artifact's own equip-toggle
    # STAT_SWEEP test correctly reflects adding its bonus — verbatim mechanism from
    # build_fp_mage_workbook.py's own build_stat_block (see its comments for the full rationale of
    # each direction-aware delta below).
    boa_direct_delta = (
        f'({ib("book_of_ancient_equipped")}-{IB("book_of_ancient_equipped")})'
        f'*{star_lookup_expr(ib("book_of_ancient_star"), "book_of_ancient_crit_rate")}'
    )
    athena_direct_delta = (
        f'({ib("athena_gloves_equipped")}-{IB("athena_gloves_equipped")})'
        f'*{star_lookup_expr(ib("athena_gloves_star"), "athena_gloves_attack_speed")}'
    )
    rainbow_crit_rate_block, rainbow_crit_damage_block = artifact_rainbow_snail_exprs(
        ib("rainbow_snail_shell_equipped"), ib("monster_type"), ib("fight_duration"), fda_block,
        ib("rainbow_snail_shell_star"),
    )
    roc_threshold_cr_block = f'({ib("crit_rate")}+{boa_direct_delta}+{rainbow_crit_rate_block})'
    roc_crit_rate_block, roc_skill_dmg_block, roc_basic_atk_dmg_block = artifact_ring_of_cycles_exprs(
        ib("ring_of_cycles_equipped"), ib("ring_of_cycles_star"), roc_threshold_cr_block,
    )
    if stat_key == "book_of_ancient_equipped":
        _boa_crit_rate_add_case = f'({ib("crit_rate")}+{boa_direct_delta}+{roc_crit_rate_block}+{rainbow_crit_rate_block})'
        _boa_crit_rate_remove_case = f'({IB("crit_rate")}+{art_ref("roc_crit_rate")}+{art_ref("rainbow_crit_rate")})'
        boa_crit_damage_delta = (
            f'(IF({ib("book_of_ancient_equipped")},1,-1)*'
            f'{star_lookup_expr(ib("book_of_ancient_star"), "book_of_ancient_crit_damage_pct_of_crit_rate")}/100'
            f'*IF({ib("book_of_ancient_equipped")},{_boa_crit_rate_add_case},{_boa_crit_rate_remove_case}))'
        )
    else:
        boa_crit_damage_delta = (
            f'IF({ib("book_of_ancient_equipped")},'
            f'{star_lookup_expr(ib("book_of_ancient_star"), "book_of_ancient_crit_damage_pct_of_crit_rate")}/100'
            f'*({ib("crit_rate")}-{IB("crit_rate")}),0)'
        )
    candle_final_dmg_block, candle_boss_dmg_block = artifact_candle_exprs(
        ib("candle_equipped"), ib("monster_type"), ib("content_type"), ib("fight_duration"), fda_block,
        ib("candle_star"),
    )
    peach_tree_block = artifact_peach_tree_expr(ib("peach_tree_equipped"), ib("peach_tree_star"), aps_ref, ib("content_type"))
    silver_pendant_block = artifact_silver_pendant_expr(ib("silver_pendant_equipped"), ib("silver_pendant_star"), aps_ref, ib("content_type"))
    attack_speed_total_block = f'({ib("attack_speed")}+{athena_direct_delta})'
    if stat_key == "athena_gloves_equipped":
        _athena_as_remove_case = IB("attack_speed")
        athena_max_dmg_delta = (
            f'(IF({ib("athena_gloves_equipped")},1,-1)*'
            f'{star_lookup_expr(ib("athena_gloves_star"), "athena_gloves_max_damage_pct_of_attack_speed")}/100'
            f'*IF({ib("athena_gloves_equipped")},{attack_speed_total_block},{_athena_as_remove_case}))'
        )
    else:
        athena_max_dmg_delta = (
            f'IF({ib("athena_gloves_equipped")},'
            f'{star_lookup_expr(ib("athena_gloves_star"), "athena_gloves_max_damage_pct_of_attack_speed")}/100'
            f'*({ib("attack_speed")}-{IB("attack_speed")}),0)'
        )
    hexagon_dmg_block = artifact_hexagon_expr(
        ib("hexagon_necklace_equipped"), ib("monster_type"), ib("fight_duration"), ib("hexagon_necklace_star"),
    )
    csw_delta_block = (
        f'({ib("clear_spring_water_equipped")}-{IB("clear_spring_water_equipped")})'
        f'*IF({_growth_dungeon_gate_expr(ib("content_type"))},{star_lookup_expr(ib("clear_spring_water_star"), "clear_spring_water_final_damage")},0)'
    )
    soul_pouch_delta_block = (
        f'({ib("soul_pouch_equipped")}-{IB("soul_pouch_equipped")})'
        f'*IF({ib("monster_type")}="pvp",{star_lookup_expr(ib("soul_pouch_star"), "soul_pouch_final_damage")},0)'
    )
    old_music_box_block = artifact_old_music_box_expr(
        ib("old_music_box_equipped"), ib("content_type"), ib("old_music_box_star"),
    )
    flaming_lava_block = artifact_flaming_lava_expr(ib("flaming_lava_equipped"), ib("flaming_lava_star"), ib("content_type"))
    icy_soul_rock_block = artifact_icy_soul_rock_expr(ib("icy_soul_rock_equipped"), ib("icy_soul_rock_star"))
    secret_map_attack_pct_block, secret_map_final_dmg_normal_block = artifact_secret_map_exprs(
        ib("secret_map_equipped"), ib("monster_type"), ib("content_type"), ib("secret_map_star"),
    )
    reindeer_spear_attack_pct_block = artifact_reindeer_spear_attack_pct_expr(
        ib("reindeer_spear_equipped"), ib("reindeer_spear_star"),
    )
    reindeer_spear_base_ref_block = artifact_reindeer_spear_base_def_pen_reference_expr(
        ib("reindeer_spear_equipped"), ib("reindeer_spear_star"),
    )
    _reindeer_star_magnitude = star_lookup_expr(ib("reindeer_spear_star"), "reindeer_spear_def_pen")
    _reindeer_extra_dose_block = f'({ib("reindeer_spear_equipped")}-{IB("reindeer_spear_equipped")})'
    def_pen_total_block = (
        f'(100*(1-(1-{ib("def_pen")}/100)*(1-{_reindeer_star_magnitude}/100)^{_reindeer_extra_dose_block}))'
    )
    cursed_doll_delta_block = (
        f'({ib("cursed_doll_equipped")}-{IB("cursed_doll_equipped")})'
        f'*{star_lookup_expr(ib("cursed_doll_star"), "cursed_doll_final_damage")}'
    )
    horn_flute_block = artifact_horn_flute_expr(
        ib("horn_flute_equipped"), ib("monster_type"), ib("content_type"), ib("fight_duration"), ib("horn_flute_star"),
    )
    bottle_of_emotion_attack_pct_block = artifact_bottle_of_emotion_attack_pct_expr(
        ib("bottle_of_emotion_equipped"), ib("bottle_of_emotion_star"),
    )
    if stat_key == "bottle_of_emotion_equipped":
        _boe_magnitude = artifact_bottle_of_emotion_final_damage_value_expr(
            "TRUE", ib("bottle_of_emotion_star"), IB("attack_speed"),
        )
        bottle_of_emotion_final_damage_delta_block = (
            f'(IF({ib("bottle_of_emotion_equipped")},1,-1)*{_boe_magnitude})'
        )
    else:
        _boe_new = artifact_bottle_of_emotion_final_damage_value_expr(
            ib("bottle_of_emotion_equipped"), ib("bottle_of_emotion_star"), ib("attack_speed"),
        )
        _boe_baseline = artifact_bottle_of_emotion_final_damage_value_expr(
            ib("bottle_of_emotion_equipped"), ib("bottle_of_emotion_star"), IB("attack_speed"),
        )
        bottle_of_emotion_final_damage_delta_block = f'({_boe_new}-{_boe_baseline})'
    alliance_badge_block = artifact_alliance_badge_expr(ib("alliance_badge_equipped"), ib("alliance_badge_star"))
    sayrams_normal_block, sayrams_boss_block = artifact_sayrams_necklace_exprs(
        ib("sayrams_necklace_equipped"), ib("sayrams_necklace_star"),
    )
    lit_lamp_delta_block = (
        f'({ib("lit_lamp_equipped")}-{IB("lit_lamp_equipped")})'
        f'*IF({ib("content_type")}="World Boss",{star_lookup_expr(ib("lit_lamp_star"), "lit_lamp_final_damage")},0)'
    )
    fire_flower_normal_block, fire_flower_boss_block = artifact_fire_flower_exprs(
        ib("fire_flower_equipped"), ib("fire_flower_star"),
    )
    star_rock_delta_block = (
        f'({ib("star_rock_equipped")}-{IB("star_rock_equipped")})'
        f'*{star_lookup_expr(ib("star_rock_star"), "star_rock_boss_damage")}'
    )
    chalice_normal_block, chalice_boss_block = artifact_chalice_exprs(
        ib("chalice_equipped"), ib("monster_type"), ib("content_type"), ib("fight_duration"), ib("chalice_star"),
    )
    contract_of_darkness_crit_rate_block = artifact_contract_of_darkness_crit_rate_bonus_expr(
        ib("contract_of_darkness_equipped"), ib("monster_type"), ib("contract_of_darkness_star"),
    )
    shamaness_marble_delta_block = (
        f'({ib("shamaness_marble_equipped")}-{IB("shamaness_marble_equipped")})'
        f'*{star_lookup_expr(ib("shamaness_marble_star"), "shamaness_marble_buff_duration_increase_pct")}'
    )
    charm_of_the_undead_block = artifact_charm_of_the_undead_expr(
        ib("charm_of_the_undead_equipped"), ib("monster_type"), ib("fight_duration"), ib("charm_of_the_undead_star"),
    )

    agg_crit_rate_block = f'({roc_crit_rate_block}+{rainbow_crit_rate_block})'
    agg_crit_damage_block = f'({boa_crit_damage_delta}+{rainbow_crit_damage_block}+{icy_soul_rock_block})'
    agg_final_damage_block = (
        f'(((1+{candle_final_dmg_block}/100)*(1+{flaming_lava_block}/100)*(1+{horn_flute_block}/100)-1)*100'
        f'+{csw_delta_block}+{soul_pouch_delta_block}+{cursed_doll_delta_block}+{lit_lamp_delta_block}'
        f'+{bottle_of_emotion_final_damage_delta_block})'
    )
    agg_boss_damage_block = f'({candle_boss_dmg_block}+{sayrams_boss_block}+{star_rock_delta_block})'
    agg_normal_damage_block = f'({sayrams_normal_block})'
    agg_enemy_dmg_taken_block = f'({peach_tree_block}+{silver_pendant_block})'
    agg_max_damage_block = f'({athena_max_dmg_delta})'
    agg_damage_block = f'({hexagon_dmg_block})'
    agg_attack_pct_block = (
        f'({old_music_box_block}+{secret_map_attack_pct_block}+{reindeer_spear_attack_pct_block}'
        f'+{alliance_badge_block}+{bottle_of_emotion_attack_pct_block}+{charm_of_the_undead_block})'
    )
    agg_final_damage_normal_only_block = (
        f'({secret_map_final_dmg_normal_block}+{fire_flower_normal_block}+{chalice_normal_block})'
    )
    agg_final_damage_boss_only_block = (
        f'({fire_flower_boss_block}+{chalice_boss_block})'
    )
    agg_skill_damage_block = f'({roc_skill_dmg_block})'
    agg_basic_attack_damage_block = f'({roc_basic_atk_dmg_block})'
    spear_extra_mult_block = artifact_reindeer_spear_extra_mult_expr(ib("monster_type"))
    _def_pen_boss_block = (
        f'(100*(1-(1-{def_pen_total_block}/100)*(1-{reindeer_spear_base_ref_block}/100)^{spear_extra_mult_block}))'
    )
    spear_def_ratio_block = (
        f'((5000/(6000+{ib("monster_defense")}*(1-{_def_pen_boss_block}/100)))'
        f'/(5000/(6000+{ib("monster_defense")}*(1-{def_pen_total_block}/100))))'
    )
    extra_normal_mult_block = f'(1+{agg_final_damage_normal_only_block}/100)'

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
            max_damage_total_block = f'({ib("max_damage")}+{agg_max_damage_block})'
            crit_rate_full_block = f'({ib("crit_rate")}+{crit_rate_delta}+{boa_direct_delta}+{agg_crit_rate_block})'
            ws.cell(row=row, column=11, value=(
                f'=J{row}*(1+{ib("stat_damage")}/100)'
                f'*(1+({ib("damage")}+{db_ref})/100)'
                f'*(1+{ib("damage_amp")}/100)'
                f'*(5000/(6000+{ib("monster_defense")}*(1-{def_pen_total_block}/100)))'
                f'*(1+{ib("final_damage")}/100)*(1+{agg_final_damage_block}/100)*(1+{elem_amp_gated_block}/100)'
                f'*(1+{arcane_aim_gated_block}/100)^5'
                f'*(1+(IF({S("Key", r)}="CHAIN_LIGHTNING",{ib("basic_attack_damage")}+{agg_basic_attack_damage_block},'
                f'{ib("skill_damage")}+{agg_skill_damage_block}))/100)'
                f'*({avgbuff_ref}*(1+{agg_damage_block}/100)*I{row})'
            ))
            ws.cell(row=row, column=12, value=(
                f'=K{row}*(MIN({ib("min_damage")}+{min_dmg_delta},{max_damage_total_block})/100+{max_damage_total_block}/100)/2'
            ))
            ws.cell(row=row, column=13, value=f'=L{row}*(1+({ib("crit_damage")}+{crit_dmg_delta}+{agg_crit_damage_block})/100)')
            ws.cell(row=row, column=14, value=(
                f'=L{row}*(1-MIN({crit_rate_full_block},100)/100)'
                f'+M{row}*(MIN({crit_rate_full_block},100)/100)'
            ))
        else:
            for col in (10, 11, 12, 13, 14):
                ws.cell(row=row, column=col, value="")

        boss_dmg_pct_row = f'{ib("boss_damage")}+{S("MasteryBossDamage%", r)}+{mdb_ref}+{agg_boss_damage_block}'
        normal_dmg_pct_row = f'{ib("normal_damage")}+{S("MasteryNormalDamage%", r)}+{mdb_ref}+{agg_normal_damage_block}'

        # The Contract of Darkness's boss-branch-only Crit Rate, via a crit-blend ratio correction
        # using THIS row's own L/M cells — only valid for damage-dealing rows, where
        # crit_rate_full_block was just freshly set above.
        if key == "CHAIN_LIGHTNING" or key in DAMAGE_ROW_KEYS:
            _cr_baseline_block = f'MIN(100,{crit_rate_full_block})'
            _cr_boss_block = f'MIN(100,{crit_rate_full_block}+{contract_of_darkness_crit_rate_block})'
            cod_crit_ratio_block = (
                f'((L{row}*(1-{_cr_boss_block}/100)+M{row}*({_cr_boss_block}/100))'
                f'/(L{row}*(1-{_cr_baseline_block}/100)+M{row}*({_cr_baseline_block}/100)))'
            )
        else:
            cod_crit_ratio_block = "1"
        extra_boss_mult_block = (
            f'({spear_def_ratio_block}*{cod_crit_ratio_block}*(1+{agg_final_damage_boss_only_block}/100))'
        )

        if key == "CHAIN_LIGHTNING":
            chain_targets_expr = f'(6+{ib("basic_attack_target_increase")})'
            prefix = f"{S('HitsPerCast', r)}*N{row}*{baps_ref}"
            boss_expr, normal_expr = boss_normal_dps_split_exprs(
                prefix, ib("monster_type"), boss_dmg_pct_row, normal_dmg_pct_row,
                chain_targets_expr, ib("max_enemies_hit"),
                extra_boss_mult_block, extra_normal_mult_block,
            )
            ws.cell(row=row, column=19, value=f'=IF(C{row},{boss_expr},0)')
            ws.cell(row=row, column=21, value=f'=IF(C{row},{normal_expr},0)')
        elif key == "FROZEN_ORB":
            frozen_orb_boss_mult_block = f'IF({ib("monster_type")}="pvp",1,1+({boss_dmg_pct_row})/100)'
            frozen_orb_normal_mult_block = (
                f'IF({ib("monster_type")}="pvp",1,(1+({normal_dmg_pct_row})/100)'
                f'*(MIN({S("NormalMonsterTargets", r)},{ib("max_enemies_hit")})))'
            )
            ws.cell(row=row, column=19, value=(
                f'=IF(C{row},H{row}*N{row}*{rate_row}*0.5*{frozen_orb_boss_mult_block}*{extra_boss_mult_block},0)'
            ))
            ws.cell(row=row, column=21, value=(
                f'=IF(C{row},H{row}*N{row}*{rate_row}*1*{frozen_orb_normal_mult_block}*{extra_normal_mult_block},0)'
            ))
        elif key in DAMAGE_ROW_KEYS:
            prefix = f'H{row}*N{row}*{rate_row}'
            boss_expr, normal_expr = boss_normal_dps_split_exprs(
                prefix, ib("monster_type"), boss_dmg_pct_row, normal_dmg_pct_row,
                S("NormalMonsterTargets", r), ib("max_enemies_hit"),
                extra_boss_mult_block, extra_normal_mult_block,
            )
            ws.cell(row=row, column=19, value=f'=IF(C{row},{boss_expr},0)')
            ws.cell(row=row, column=21, value=f'=IF(C{row},{normal_expr},0)')
        else:
            ws.cell(row=row, column=19, value=0)
            ws.cell(row=row, column=21, value=0)

        ws.cell(row=row, column=15, value=f'=(1-{ib("normal_weight_frac")})*S{row}+{ib("normal_weight_frac")}*U{row}')

        ws.cell(row=row, column=16, value=f'=IF({total_ref}=0,0,O{row}/{total_ref})')
        ws.cell(row=row, column=17, value=f'=IFERROR(1/{eff_cd_row},0)')

        if ROW_HAS_COOLDOWN[key]:
            casts_formula_block = guarded_casts_expr(available_duration_row, eff_cd_row)
            ws.cell(row=row, column=18, value=f'=IF({fda_block},{casts_formula_block},0)')
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

    ws.cell(row=s_avgbuff, column=1, value="Average Buff Multiplier (Magic Guard + Meditation + Artifact Attack%, summed; then Infinity)")
    ws.cell(row=s_avgbuff, column=2, value=(
        f'=(1+(IF(C{mg}=TRUE,F{mg}*{buff_uptime_block(mg, ROW["MAGIC_GUARD"])},0)'
        f'+IF(C{med}=TRUE,F{med}*{buff_uptime_block(med, ROW["MEDITATION"])},0)+{agg_attack_pct_block})/100)'
        f'*IF(C{inf}=TRUE,(1+F{inf}*{buff_uptime_block(inf, ROW["INFINITY"])}/100),1)'
    ))

    fb_cd_block = S("Cooldown(s)", ROW["FREEZING_BREATH"])
    ws.cell(row=s_mdb, column=1, value=(
        "Monster Damage Taken Bonus % (Freezing Breath - Weaken + Elemental Reset + Artifact "
        "Enemy Damage Taken, summed)"
    ))
    ws.cell(row=s_mdb, column=2, value=(
        f'=IF({ib("level")}>=118,15*{uptime_fraction_expr(ib("monster_type"), 30, fb_cd_block, bdi_block)},0)'
        f'+IF(C{ed}=TRUE,F{ed},0)+{agg_enemy_dmg_taken_block}'
    ))

    ws.cell(row=s_db, column=1, value="Damage % Bonus (Frozen Break + Frost Clutch, flat)")
    ws.cell(row=s_db, column=2, value=(
        f'=IF({ib("level")}>=66,15,0)+IF({ib("level")}>=98,10,0)+IF({ib("level")}>=125,20,0)'
    ))

    me = row_of["MP_EATER_MP_BOOST"]
    ws.cell(row=s_asb, column=1, value="Attack Speed Bonus % (MP Eater - MP Boost, always-on once unlocked)")
    ws.cell(row=s_asb, column=2, value=f'=IF(C{me}=TRUE,F{me}+{attack_speed_delta},0)')

    ws.cell(row=s_aps, column=1, value="Actions Per Second")
    ws.cell(row=s_aps, column=2, value=f'=1+MIN(150,150*(1-(1-{attack_speed_total_block}/150)*(1-{asb_ref}/150)))/100')

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

    # 2nd, simpler table for boolean artifact equip-toggles — verbatim mechanism from
    # build_fp_mage_workbook.py's own build_sensitivity_sheet (see its comments for the full
    # rationale of the hidden staging block / rank-based sort-and-filter).
    artifact_title_row = ARTIFACT_TABLE_TITLE_ROW
    artifact_header_row = ARTIFACT_TABLE_HEADER_ROW
    artifact_staging_col = {"label": 27, "dps_gain": 28, "pct_gain": 29, "unlocked": 30, "rank": 31}  # AA-AE
    artifact_first_row = ARTIFACT_TABLE_FIRST_DATA_ROW
    artifact_last_row = ARTIFACT_TABLE_LAST_DATA_ROW
    _stg = {
        k: f'${get_column_letter(c)}${artifact_first_row}:${get_column_letter(c)}${artifact_last_row}'
        for k, c in artifact_staging_col.items()
    }
    _stg_count_unlocked = f'COUNTIF({_stg["unlocked"]},TRUE)'
    ws.cell(row=artifact_title_row, column=1, value="Artifact Equip-Toggle DPS Gain").font = SECTION_FONT
    artifact_headers = ["Artifact", "DPS Gain", "% Gain"]
    for i, name in enumerate(artifact_headers):
        ws.cell(row=artifact_header_row, column=i + 1, value=name)
    style_header_row(ws, artifact_header_row, len(artifact_headers))

    stat_idx = 0
    artifact_idx = 0
    for idx, (key, label, kind) in enumerate(STAT_SWEEP):
        base_row = BLOCK_START + idx * BLOCK_HEIGHT
        override_expr = override_expr_for(kind, key)
        ib = make_ib(key, override_expr)
        total_ref, boss_total_ref, normal_total_ref = build_stat_block(ws, base_row, ib, key, label, override_expr)

        boss_ratio = f'IFERROR({boss_total_ref}/Summary!$B${SUMMARY_ROW["BOSS_ONLY_TOTAL"]},1)'
        normal_ratio = f'IFERROR({normal_total_ref}/Summary!$B${SUMMARY_ROW["NORMAL_ONLY_TOTAL"]},1)'
        weighted_ratio = f'((1-{IB("normal_weight_frac")})*{boss_ratio}+{IB("normal_weight_frac")}*{normal_ratio})'
        dps_gain_expr = f"=Summary!$B${SUMMARY_ROW['TOTAL_DPS']}*({weighted_ratio}-1)"
        pct_gain_expr = f"={weighted_ratio}*100"

        if kind != "bool":
            row = header_row + 1 + stat_idx
            stat_idx += 1
            ws.cell(row=row, column=1, value=label)
            ws.cell(row=row, column=3, value=kind)
            ws.cell(row=row, column=4, value=f"={IB(key)}")
            ws.cell(row=row, column=5, value=f"={override_expr}")
            ws.cell(row=row, column=6, value=f"=Summary!$B${SUMMARY_ROW['TOTAL_DPS']}")
            ws.cell(row=row, column=7, value=f"={total_ref}")
            ws.cell(row=row, column=8, value=dps_gain_expr)
            ws.cell(row=row, column=9, value=pct_gain_expr)
            ws.cell(row=row, column=2, value=f'=IFERROR(1/(I{row}-100),"n/a")')
        else:
            row = artifact_header_row + 1 + artifact_idx
            artifact_idx += 1
            currently_equipped_expr = IB(key)
            art_key = key[: -len("_equipped")]
            potential_dps_ref = f'ArtifactsInput!$L${ARTIFACTS_INPUT_ROW[art_key]}'
            total_gain_dollar_expr = (
                f'(IF({currently_equipped_expr},-1,1)*Summary!$B${SUMMARY_ROW["TOTAL_DPS"]}*({weighted_ratio}-1)'
                f'+{potential_dps_ref})'
            )
            artifact_dps_gain_expr = f"={total_gain_dollar_expr}"
            artifact_pct_gain_expr = (
                f"=(Summary!$B${SUMMARY_ROW['TOTAL_DPS']}+{total_gain_dollar_expr})"
                f"/Summary!$B${SUMMARY_ROW['TOTAL_DPS']}*100"
            )
            ws.cell(row=row, column=artifact_staging_col["label"], value=label)
            ws.cell(row=row, column=artifact_staging_col["dps_gain"], value=artifact_dps_gain_expr)
            ws.cell(row=row, column=artifact_staging_col["pct_gain"], value=artifact_pct_gain_expr)
            ws.cell(row=row, column=artifact_staging_col["unlocked"], value=(
                f'=ArtifactsInput!$B${ARTIFACTS_INPUT_ROW[art_key]}<>"Not Unlocked"'
            ))
            _pct_col = get_column_letter(artifact_staging_col["pct_gain"])
            _unlocked_col = get_column_letter(artifact_staging_col["unlocked"])
            ws.cell(row=row, column=artifact_staging_col["rank"], value=(
                f'=IF({_unlocked_col}{row},'
                f'SUMPRODUCT(({_stg["unlocked"]})*({_stg["pct_gain"]}>{_pct_col}{row}))'
                f'+COUNTIFS(${_unlocked_col}${artifact_first_row}:{_unlocked_col}{row},TRUE,'
                f'${_pct_col}${artifact_first_row}:{_pct_col}{row},{_pct_col}{row}),"")'
            ))
            display_rank = artifact_idx
            _blank_if_past_count = f'{display_rank}>{_stg_count_unlocked}'
            ws.cell(row=row, column=1, value=(
                f'=IF({_blank_if_past_count},"",INDEX({_stg["label"]},MATCH({display_rank},{_stg["rank"]},0)))'
            ))
            ws.cell(row=row, column=2, value=(
                f'=IF({_blank_if_past_count},"",INDEX({_stg["dps_gain"]},MATCH({display_rank},{_stg["rank"]},0)))'
            ))
            ws.cell(row=row, column=3, value=(
                f'=IF({_blank_if_past_count},"",INDEX({_stg["pct_gain"]},MATCH({display_rank},{_stg["rank"]},0)))'
            ))

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
            f"=IF(Summary!$B${SUMMARY_ROW['TOTAL_DPS']}=0,0,"
            f"(B{row}-Summary!$B${SUMMARY_ROW['TOTAL_DPS']})/Summary!$B${SUMMARY_ROW['TOTAL_DPS']}*100)"
        ))

    widths = [40, 16, 8, 14, 14, 16, 14, 12, 10]
    for i, w in enumerate(widths):
        ws.column_dimensions[get_column_letter(i + 1)].width = w
    for col in artifact_staging_col.values():
        ws.column_dimensions[get_column_letter(col)].hidden = True
    ws.freeze_panes = "A5"
    return ws


# ---------------------------------------------------------------------------
# Equipment Compare — pick a "Current Equip" and a "New Equip" (an Attack line + up to 5 more
# stat lines each) and see which is the bigger upgrade, as a DPS % delta. Reuses the exact same
# Sensitivity!H<row> "$/unit" marginal-DPS values Potential Cubes/Artifact Potentials already use
# — a pure calculator sheet, nothing else in the workbook reads from it, so no Calc/Summary/
# Sensitivity/verify_ice_lightning_mage_workbook.py changes are needed for this feature at all.
# Verbatim mechanism from build_fp_mage_workbook.py's own Equipment Compare feature.
# ---------------------------------------------------------------------------
EQUIP_COMPARE_STAT_TO_SWEEP_KEY = {
    "Main Stat (flat)": "flat_int",
    "Main Stat %": "int_pct",
    "Attack (flat)": "flat_attack",
    "Min Damage %": "min_damage",
    "Max Damage %": "max_damage",
    "Damage %": "damage",
    "Critical Rate %": "crit_rate",
    "Critical Damage %": "crit_damage",
    "Boss Monster Damage %": "boss_damage",
    "Normal Monster Damage %": "normal_damage",
    "Defense Penetration %": "def_pen",
    "Defense (flat)": "defense",
    "Skill Level Bonus — 1st Job": "skill_lvl_1st",
    "Skill Level Bonus — 2nd Job": "skill_lvl_2nd",
    "Skill Level Bonus — 3rd Job": "skill_lvl_3rd",
    "Skill Level Bonus — 4th Job": "skill_lvl_4th",
    "Skill Level Bonus — All Skills": "skill_lvl_all",
    "Final Damage %": "final_damage",
    "Basic Attack Damage %": "basic_attack_damage",
    "Skill Damage %": "skill_damage",
    "Attack Speed %": "attack_speed",
}
EQUIP_COMPARE_DROPDOWN_STATS = list(EQUIP_COMPARE_STAT_TO_SWEEP_KEY.keys())
EQUIP_COMPARE_LINE_ROWS = list(range(6, 11))  # 5 dropdown lines; row 5 is the fixed Attack line
EQUIP_COMPARE_ALL_ROWS = [5] + EQUIP_COMPARE_LINE_ROWS


def equip_compare_per_unit_rate_expr(stat_name):
    """A stat's $/unit DPS rate — reuses dps_per_unit_expr's own Critical-Rate-at-cap fallback
    logic verbatim rather than reimplementing it (same reasoning as Potential Cubes). Falls back
    to "0" for stats with no Sensitivity row in this particular class (e.g. "Defense (flat)" has
    no DPS effect at all except in Dark Knight/Bishop, which convert part of it into STR/INT via
    Iron Wall/Invincible — same defensive fallback dps_per_unit_expr itself uses)."""
    if stat_name == "Critical Rate %":
        return dps_per_unit_expr("Critical Rate %").lstrip("=")
    key = EQUIP_COMPARE_STAT_TO_SWEEP_KEY[stat_name]
    row = SENSITIVITY_ROW_FOR.get(key)
    return f"Sensitivity!H{row}" if row is not None else "0"


def equip_compare_dropdown_rate_expr(dropdown_ref):
    """Nested-IF chain resolving whichever stat is LIVE-selected in `dropdown_ref` to its $/unit
    rate — same shape as ArtifactsInput's own potential-line stat lookup, just without a rarity
    multiplier (the roll's raw value is typed directly here, not derived from a rarity table)."""
    body = "0"
    for name in reversed(EQUIP_COMPARE_DROPDOWN_STATS):
        body = f'IF({dropdown_ref}="{name}",{equip_compare_per_unit_rate_expr(name)},{body})'
    return body


def build_equipment_compare_sheet(wb, existing=None):
    existing = existing or {}
    ws = wb.create_sheet("Equipment Compare")
    HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
    HEADER_FONT = Font(bold=True, color="FFFFFF")
    INPUT_FILL = PatternFill("solid", fgColor="FFF2CC")
    COMPUTED_FILL = PatternFill("solid", fgColor="D9D9D9")

    ws["A1"] = "Arch Mage (Ice/Lightning) — Equipment Compare"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = (
        "Compare a candidate replacement equip against what you currently have, one Attack line "
        "plus up to 5 more stat lines each. Uses the same $/unit marginal-DPS values as Potential "
        "Cubes/Artifact Potentials: two lines of the SAME stat correctly add (two 5% Max Damage "
        "lines = one 10% Max Damage bucket), but two DIFFERENT stats correctly compound "
        "multiplicatively rather than just summing (two independent 1% gains combine to "
        "1.01x1.01-1=2.0201%, not a naive 2%) — exact, not an approximation, since both equips are "
        "concrete/fixed sets of lines rather than an open-ended reroll search."
    )

    blocks = [
        ("Current Equip", 2, 3, 4, 5, 6, 7),   # (label, stat_col, val_col, gain_col, grp_col, first_col, factor_col)
        ("New Equip", 9, 10, 11, 12, 13, 14),
    ]

    for title, stat_c, val_c, gain_c, grp_c, first_c, factor_c in blocks:
        ws.cell(row=4, column=stat_c, value=title).font = HEADER_FONT
        for c in (stat_c, val_c, gain_c, grp_c, first_c, factor_c):
            ws.cell(row=4, column=c).fill = HEADER_FILL

    ws.cell(row=5, column=1, value="Attack (flat)").font = LABEL_FONT
    for i, row in enumerate(EQUIP_COMPARE_LINE_ROWS):
        ws.cell(row=row, column=1, value=f"Line {i + 2}").font = LABEL_FONT

    # Dropdown option list: a hidden helper range (Excel's inline-list formula1 is capped at ~255
    # chars, far too short for 21 names) — same range-reference pattern as Inputs' own
    # dv_slot_options_range for equipped-artifact slots.
    dv_options_col = 17
    for i, name in enumerate(EQUIP_COMPARE_DROPDOWN_STATS):
        ws.cell(row=1 + i, column=dv_options_col, value=name)
    dv_range = f"${get_column_letter(dv_options_col)}$1:${get_column_letter(dv_options_col)}${len(EQUIP_COMPARE_DROPDOWN_STATS)}"
    dv_stat = DataValidation(type="list", formula1=f"={dv_range}", allow_blank=False)
    ws.add_data_validation(dv_stat)

    existing_lines = existing.get("lines", {})  # {"current"/"new": {row: {"stat":..,"value":..}}}
    for equip_key, (title, stat_c, val_c, gain_c, grp_c, first_c, factor_c) in zip(("current", "new"), blocks):
        saved = existing_lines.get(equip_key, {})

        # Row 5 — Attack (flat): fixed stat identity (no dropdown), still participates in the same
        # grouping logic below so a dropdown line that ALSO picks "Attack (flat)" combines with it
        # correctly instead of double-counting.
        ws.cell(row=5, column=stat_c, value="Attack (flat)").fill = COMPUTED_FILL
        val_cell = ws.cell(row=5, column=val_c, value=saved.get(5, {}).get("value", 0))
        val_cell.fill = INPUT_FILL
        ws.cell(row=5, column=gain_c, value=(
            f"={get_column_letter(val_c)}5*{equip_compare_per_unit_rate_expr('Attack (flat)')}"
        ))
        ws.cell(row=5, column=first_c, value="=TRUE")

        for row in EQUIP_COMPARE_LINE_ROWS:
            row_saved = saved.get(row, {})
            stat_cell = ws.cell(row=row, column=stat_c, value=row_saved.get("stat", "(none)"))
            stat_cell.fill = INPUT_FILL
            dv_stat.add(stat_cell)
            val_cell = ws.cell(row=row, column=val_c, value=row_saved.get("value", 0))
            val_cell.fill = INPUT_FILL
            stat_ref = f"{get_column_letter(stat_c)}{row}"
            val_ref = f"{get_column_letter(val_c)}{row}"
            ws.cell(row=row, column=gain_c, value=(
                f'=IF({stat_ref}="(none)",0,{val_ref}*({equip_compare_dropdown_rate_expr(stat_ref)}))'
            ))
            prior_range = f"${get_column_letter(stat_c)}$5:{get_column_letter(stat_c)}{row - 1}"
            ws.cell(row=row, column=first_c, value=(
                f'=AND({stat_ref}<>"(none)",COUNTIF({prior_range},{stat_ref})=0)'
            ))

        stat_range = f"${get_column_letter(stat_c)}$5:${get_column_letter(stat_c)}$10"
        gain_range = f"${get_column_letter(gain_c)}$5:${get_column_letter(gain_c)}$10"
        for row in EQUIP_COMPARE_ALL_ROWS:
            stat_ref = f"{get_column_letter(stat_c)}{row}"
            first_ref = f"{get_column_letter(first_c)}{row}"
            ws.cell(row=row, column=grp_c, value=f"=SUMIF({stat_range},{stat_ref},{gain_range})")
            ws.cell(row=row, column=factor_c, value=(
                f"=IF(NOT({first_ref}),1,1+{get_column_letter(grp_c)}{row}/Summary!$B$3)"
            ))
            for c in (grp_c, first_c, factor_c):
                ws.column_dimensions[get_column_letter(c)].hidden = True

        factor_range = f"${get_column_letter(factor_c)}$5:${get_column_letter(factor_c)}$10"
        ws.cell(row=12, column=1, value="Total DPS Gain").font = LABEL_FONT
        ws.cell(row=12, column=gain_c, value=f"=Summary!$B$3*(PRODUCT({factor_range})-1)")
        ws.cell(row=13, column=1, value="% of Total DPS").font = LABEL_FONT
        pct_cell = ws.cell(row=13, column=gain_c, value=f"={get_column_letter(gain_c)}12/Summary!$B$3*100")
        pct_cell.number_format = '0.00"%"'

    ws.cell(row=15, column=1, value="New vs Current — DPS % Delta").font = Font(bold=True, size=12)
    delta_cell = ws.cell(row=15, column=4, value="=K13-D13")
    delta_cell.font = Font(bold=True, size=12)
    delta_cell.number_format = '+0.00"%";-0.00"%";0.00"%"'

    ws.column_dimensions["A"].width = 26
    for c in (2, 9):
        ws.column_dimensions[get_column_letter(c)].width = 22
    for c in (3, 10):
        ws.column_dimensions[get_column_letter(c)].width = 12
    ws.column_dimensions[get_column_letter(dv_options_col)].hidden = True
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
    its Inputs values, ArtifactsInput gear state, and PotentialCubes current-gear table so
    regenerating the workbook doesn't clobber the user's real character stats and gear state with
    the hardcoded defaults. Matches PotentialCubes rows by (slot, potential type), not row
    position — verbatim mechanism from build_fp_mage_workbook.py's own load_existing_workbook_state."""
    if not path.exists():
        return {}, {}, {}, {}
    try:
        wb = openpyxl.load_workbook(path)
    except Exception as e:
        print(f"Warning: couldn't read existing {path} to carry over values ({e}); using defaults.")
        return {}, {}, {}, {}

    existing_inputs = {}
    if "Inputs" in wb.sheetnames:
        ws = wb["Inputs"]
        # New-format detection: row 2, columns C onward hold the content-type header row (see
        # build_inputs_sheet). Matched by header TEXT, not position, so this stays robust even if
        # CONTENT_TYPES is ever reordered.
        col_for_ct = {}
        for c in range(3, 3 + len(CONTENT_TYPES)):
            name = ws.cell(row=2, column=c).value
            if name in CONTENT_TYPES:
                col_for_ct[name] = c
        has_ct_columns = bool(col_for_ct)

        def _clean(value):
            if value is None or (isinstance(value, str) and value.startswith("=")):
                return None
            return value

        for key, row in IN.items():
            if row in COMPUTED_INPUT_ROWS:
                continue
            if key not in PER_CONTENT_TYPE_INPUT_KEYS:
                value = _clean(ws.cell(row=row, column=2).value)
                if value is not None:
                    existing_inputs[key] = value
                continue
            if has_ct_columns:
                per_ct = {}
                for ct, col in col_for_ct.items():
                    value = _clean(ws.cell(row=row, column=col).value)
                    if value is not None:
                        per_ct[ct] = value
                if per_ct:
                    existing_inputs[key] = per_ct
            else:
                # Old single-column file — column B still holds the one real literal; migrate by
                # duplicating it into every content-type column so nothing suddenly zeroes out,
                # rather than losing it or leaving 9 columns at defaults.
                value = _clean(ws.cell(row=row, column=2).value)
                if value is not None:
                    existing_inputs[key] = {ct: value for ct in CONTENT_TYPES}

        old_label = ws.cell(row=IN["content_type"], column=1).value or ""
        if "Content Type" not in old_label:
            existing_inputs.pop("content_type", None)
            existing_inputs.pop("chapter_stage", None)

        # Equipped-artifact slots, new format: already on this sheet (see
        # INPUT_ARTIFACT_SLOTS_SECTION_ROW/INPUT_ARTIFACT_SLOT_ROWS in build_inputs_sheet).
        if ws.cell(row=INPUT_ARTIFACT_SLOTS_SECTION_ROW, column=1).value == "Equipped Artifacts (up to 4)":
            artifact_slots = {
                ct: [ws.cell(row=r, column=col).value or "(none)" for r in INPUT_ARTIFACT_SLOT_ROWS]
                for ct, col in col_for_ct.items()
            }
            existing_inputs["artifact_slots"] = artifact_slots

    existing_artifacts_input = {}
    if "ArtifactsInput" in wb.sheetnames:
        aws = wb["ArtifactsInput"]
        if "artifact_slots" not in existing_inputs:
            # Old file: equipped-artifact slots still lived on the ArtifactsInput sheet (a
            # single flat column, since ILM never had a per-content-type-on-ArtifactsInput phase)
            # — migrated forward onto the Inputs sheet's own slots section.
            old_slots = [aws.cell(row=r, column=2).value or "(none)" for r in LEGACY_ARTIFACTS_INPUT_SLOT_ROWS]
            existing_inputs["artifact_slots"] = {ct: list(old_slots) for ct in CONTENT_TYPES}
        # Rows are matched by the artifact's own label text (column A), NOT by the row number
        # this build assigns it — the reorder-by-rank + blank-separator-row layout means an
        # artifact's row number can differ between the old file and this build.
        label_to_old_row = {}
        for r in range(1, aws.max_row + 1):
            label = aws.cell(row=r, column=1).value
            if label in ARTIFACT_LABELS.values():
                label_to_old_row[label] = r
        has_potential_cols = any(
            aws.cell(row=r, column=3).value == "Line 1 Rarity" for r in range(1, aws.max_row + 1)
        )
        stars = {}
        lines = {}
        line_cols = [(3, 4), (6, 7), (9, 10)]
        for art_key, art_label in ARTIFACT_LABELS.items():
            old_row = label_to_old_row.get(art_label)
            if old_row is None:
                continue
            val = aws.cell(row=old_row, column=2).value
            stars[art_key] = val if val is not None else "Not Unlocked"
            if not has_potential_cols:
                continue
            num_lines = 3 if ARTIFACT_RANK[art_key] == "Legendary" else 2
            art_lines = {}
            for line_idx in range(num_lines):
                rarity_col, stat_col = line_cols[line_idx]
                rarity_val = aws.cell(row=old_row, column=rarity_col).value
                stat_val = aws.cell(row=old_row, column=stat_col).value
                if rarity_val is not None or stat_val is not None:
                    art_lines[line_idx + 1] = {"rarity": rarity_val or "Rare", "stat": stat_val or "(none)"}
            if art_lines:
                lines[art_key] = art_lines
        existing_artifacts_input = {"stars": stars, "lines": lines}

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
    existing_equipment_compare = {}
    if "Equipment Compare" in wb.sheetnames:
        ws = wb["Equipment Compare"]
        blocks = [("current", 2, 3), ("new", 9, 10)]  # (equip_key, stat_col, val_col)
        for equip_key, stat_c, val_c in blocks:
            lines = {}
            for row in EQUIP_COMPARE_ALL_ROWS:
                val = ws.cell(row=row, column=val_c).value
                if row == 5:
                    lines[row] = {"value": val if val is not None else 0}
                    continue
                stat = ws.cell(row=row, column=stat_c).value
                lines[row] = {
                    "stat": stat if stat is not None else "(none)",
                    "value": val if val is not None else 0,
                }
            existing_equipment_compare[equip_key] = lines
        existing_equipment_compare = {"lines": existing_equipment_compare}

    return existing_inputs, existing_artifacts_input, existing_potential_cubes, existing_equipment_compare


def main():
    existing_inputs, existing_artifacts_input, existing_potential_cubes, existing_equipment_compare = load_existing_workbook_state(OUT_PATH)
    wb = openpyxl.Workbook()
    build_readme_sheet(wb)
    build_inputs_sheet(wb, existing=existing_inputs)
    build_factor_table_sheet(wb)
    build_skills_sheet(wb)
    build_artifacts_sheet(wb)
    build_calc_sheet(wb)
    build_summary_sheet(wb)
    build_sensitivity_sheet(wb)
    build_equipment_compare_sheet(wb, existing=existing_equipment_compare)
    build_cube_data_sheet(wb)
    build_artifacts_input_sheet(wb, existing=existing_artifacts_input)
    build_potential_cubes_sheet(wb, existing=existing_potential_cubes)
    wb.active = 0
    wb.save(OUT_PATH)
    print(f"Wrote {OUT_PATH}")
    if existing_inputs or existing_artifacts_input or existing_potential_cubes or existing_equipment_compare:
        print("Carried over Inputs/ArtifactsInput/PotentialCubes values from the previous workbook.")


if __name__ == "__main__":
    main()
