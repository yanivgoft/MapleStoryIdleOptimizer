#!/usr/bin/env python3
"""
Generates Night-Lord-DPS-Calculator.xlsx: a live-formula Excel replica of a Night Lord
skill-rotation DPS model, sibling to build_fp_mage_workbook.py (see
tools/FP_MAGE_PROJECT_NOTES.md and the approved plan this was built from). Night Lord is
LUK main stat / DEX sub stat (confirmed via src/ts/page/base-stats/class-select.ts's
isLukMainStatClass).

Sheets: Inputs, FactorTable, Skills, Calc, Summary, Sensitivity, CubeData, PotentialCubes, Artifacts, ArtifactsInput, Equipment Compare and (2026-11-16 port from
FP-Mage / Hero / Paladin / Dark Knight / Buccaneer / Corsair / Marksman, see KNOWN_GAPS.md "Night Lord: Companions + Status Effect Damage / KO timeline")
Timeline, CompanionKits, Companion, CompanionsInput.

Companions / Status Effect Damage (2026-11-16): Inputs STATUS_EFFECT_DAMAGE % + Companion; the Status/KO timeline engine (src/status_timeline.py) times Dark Sight (Attack%) and
Frailty Curse's self Final Damage (a multiplicative term) plus the cooldown casts Gust Charm / Triple Throw / Dark Flare / Quad Star / Sudden Raid (+ its DoT); Showdown (the
basic attack), Assassin's Mark, Venom, Toxic Venom and Shadow Shifter are uniform rows.  Alchemic Adrenaline, Nimble Feet, Shadow Partner and the Frailty Curse enemy debuff
stay averaged.  Gust Charm's 2 s stun is the player's own stun window (STATUS_PLAYER_STUN).

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
import os
import re
from pathlib import Path

import openpyxl
import companion_model as cm   # shared companion model (src/companion_model.py)
import status_timeline as stl  # shared status-effect / KO timeline engine (src/status_timeline.py)
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

REPO = Path(__file__).resolve().parent.parent
FACTOR_TABLE_JSON = REPO / "data/factor_table.json"
CUBE_POTENTIAL_JSON = REPO / "data/cube_potential_data.json"
OUT_PATH = REPO / "Night-Lord" / "Night-Lord-DPS-Calculator.xlsx"

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
# Potential and Bonus Potential have genuinely different pity caps in-game (confirmed by the
# user) — same rarity order/rates, but Bonus Potential's own pity max is higher at every tier
# except Legendary (which is shared). Keyed by potential type first, then rarity.
assert set(RARITY_UPGRADE_RATES) == {"Potential", "Bonus Potential"}
for _pt_rates in RARITY_UPGRADE_RATES.values():
    assert set(_pt_rates) == {"normal", "rare", "epic", "unique", "legendary", "mystic"}
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
# This fixed-size "Derived Values" block must stay SMALL and EARLY (right after TOTAL DPS at
# row 3), not after the variable-length summary tables — those grow with DAMAGE_DEALING_KEYS/
# STAT_SWEEP (about to grow further once a future Artifacts feature lands ~36 more equip-toggle
# rows project-wide), and a hardcoded-after-them block silently collides once they grow past it.
# See build_fp_mage_workbook.py/build_bishop_workbook.py for the reference pattern this mirrors.
DERIVED_HEADER_ROW = 5
D_ATTACK = 6                     # ATTACK = Flat ATTACK x (1+ATTACK%/100)
D_STAT_DAMAGE = 7                # STAT_DAMAGE% = 1% of total LUK + 0.25% of DEX
D_BASIC_INPUT_LEVEL = 8          # Basic Attack (Showdown) input level (4th job formula)
D_BASIC_FACTOR = 9               # Basic Attack factor lookup (factorIndex 21)
D_SKILL_COEFFICIENT = 10         # Basic Attack base coefficient % before Skill Mastery
D_NORMAL_WEIGHT_FRAC = 11        # 0/1/breakthrough-blend/0 weight, by monster_type
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
    "flat_luk": 12,
    "luk_pct": 13,
    "dex": 14,
    "damage": 15,
    "damage_amp": 16,
    "basic_attack_damage": 17,
    "skill_damage": 18,
    "def_pen": 19,
    "boss_damage": 20,
    "normal_damage": 21,
    "status_effect_damage": 22,
    "min_damage": 23,
    "max_damage": 24,
    "final_damage": 25,
    "skill_lvl_1st": 26,
    "skill_lvl_2nd": 27,
    "skill_lvl_3rd": 28,
    "skill_lvl_4th": 29,
    "skill_lvl_all": 30,
    "skill_cooldown_decrease": 32,
    "basic_attack_target_increase": 33,
    "buff_duration_increase_pct": 34,
    "companion_summon_time_increase_pct": 35,
    "boss_normal_weight_choice": 36,
    "max_enemies_hit": 37,
    "incoming_hit_rate": 38,
    "monster_type": 39,
    "chapter": 40,
    "stage": 41,
    "breakthrough_stage_index": 42,
    "monster_defense": 43,
    "fight_duration": 44,
    "breakthrough_normal_weight_pct": 45,
    # PvP fight length (seconds), PvP content only — rows 54-55 sit below every class's artifact-slot rows.
    "pvp_fight_length": 55,
    # Companion (rows 51-53 sit between the artifact-slot rows 46-50 and the PvP section row 54)
    "companion_choice": 51,
}
INPUT_PVP_SECTION_ROW = 54

# Rows computed by formula on the Inputs sheet itself (not user-editable) — see
# build_inputs_sheet's "Computed (do not edit)" block below.
COMPUTED_INPUT_ROWS = {
    IN["monster_type"], IN["chapter"], IN["stage"], IN["breakthrough_normal_weight_pct"],
    IN["breakthrough_stage_index"], IN["monster_defense"], IN["fight_duration"],
}

# Every Inputs row that gets its own column per content type (see build_inputs_sheet) — i.e.
# everything except the character-wide "level", the "content_type" selector itself (each column's
# own identity already IS a content type — no separate per-column meaning), and the existing
# computed rows (which already derive transitively from per-content-type inputs via IB(), so they
# need no changes of their own). Derived from IN/COMPUTED_INPUT_ROWS rather than hand-listed so it
# can't drift out of sync if a row is ever added or removed.
PER_CONTENT_TYPE_INPUT_KEYS = [
    k for k in IN
    if k not in ("level", "content_type") and IN[k] not in COMPUTED_INPUT_ROWS
]

# These 6 values are computed (not user-entered) and live on the Summary sheet's "Derived Values"
# block instead of cluttering Inputs — see DERIVED_ROW above and build_summary_sheet.


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
    # Arwen's Glass Shoes: Companion Summoning Time Increase % (percentage points added to Inputs!companion_summon_time_increase_pct while
    # equipped; Artifacts row arwens_glass_shoes_summon_time_increase_pct).  Star 0 = 20, star 5 = 40 and the linear steps
    # between them (20, 24, 28, 32, 36, 40) are USER-CONFIRMED (2026-11-19).  One table: change the values here if the game changes.
    "arwens_glass_shoes_summon_time_increase_pct": [20, 24, 28, 32, 36, 40],
}

# Artifacts that genuinely have NO DPS effect in this model (user, 2026-11-19): their stat is one the DPS model does not use, or their content
# is not modelled.  This is a statement of fact, not missing data - equipping them changes nothing and their Artifacts-sheet row is a constant 0.
# artifact id -> (short reason, shown on the Artifacts / ArtifactsInput sheets and in the engine schema)
ARTIFACT_NO_DPS_EFFECT = {
    "ancient_text_piece": "Guild Conquest content (not modelled)",
    "lunar_dew": "stat not used by the DPS model (no attacking effect)",
    "pink_beans_giant_rib": "raid content (not modelled)",
    "horntails_scale": "raid content (not modelled)",
    "zakums_stone_piece": "raid content (not modelled)",
    "mushmoms_cap": "stat not used by the DPS model (Accuracy vs Evasion not modelled)",
    "pigs_ribbon": "stat not used by the DPS model (no attacking effect)",
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
# 45 left blank as a spacer) so no existing IN-dict row number has to shift. One resolved column B
# + per-content-type C-L columns each, exactly like every other per-content-type Inputs row.
INPUT_ARTIFACT_SLOTS_SECTION_ROW = 46
INPUT_ARTIFACT_SLOT_ROWS = [47, 48, 49, 50]

# Columns C-L hold up to 3 Potential lines (Rarity/Stat dropdowns + computed % DPS Gain each,
# Line 3 Legendary-only) — see build_artifacts_input_sheet/ARTIFACT_POTENTIAL_VALUES. Columns M/N
# hold each artifact's resolved Equipped?/Star Level (computed from the 4 slot pickers + column
# B's own Star Level cell) — IB() resolves every "{art_key}_equipped"/"{art_key}_star" key straight
# to these cells, so the Inputs sheet no longer needs to show them at all (removed per the user).
# Companion levels live on the CompanionsInput sheet (one row per companion, "Not unlocked" or 1-18); IB() resolves them.
COMPANIONS_INPUT_FIRST_ROW = 5
COMPANION_INPUT_ROW = {name: COMPANIONS_INPUT_FIRST_ROW + i for i, name in enumerate(cm.COMPANIONS)}
COMPANIONS_INPUT_LAST_ROW = COMPANIONS_INPUT_FIRST_ROW + len(cm.COMPANIONS) - 1


def companion_slug(name):
    return name.lower().replace(" ", "_")


COMPANION_INPUT_CELL = {f"companion_level_{companion_slug(n)}": f"CompanionsInput!$C${r}" for n, r in COMPANION_INPUT_ROW.items()}
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
# Defense %/Accuracy/Status Effect Damage %. NOTE for when this expands to other classes: Defense
# % will need real modeling for Dark Knight (Iron Wall's Defense->STR conversion) and Bishop.
ARTIFACT_POTENTIAL_STAT_TO_SWEEP_KEY = {
    "Main Stat %": "luk_pct",
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


# ---------------------------------------------------------------------------
# Reusable, fully-parameterized artifact formula builders — used both by build_artifacts_sheet
# (the real, global computation, with its own per-step rows for transparency) and by
# build_stat_block's Sensitivity shadow-block mirror (fully inlined, no separate rows, since 8
# artifacts x ~25 swept stats would otherwise add hundreds of rows). Taking plain expression
# strings (not tied to IB/ib) keeps them usable in both contexts — same pattern this project
# already uses everywhere else (build_calc_sheet and build_stat_block are independently written,
# parallel implementations of the same formulas, not shared code).
# ---------------------------------------------------------------------------
def artifact_book_of_ancient_crit_damage_expr(eq_expr, star_expr, crit_rate_total_expr):
    """Book of Ancient's dependent Crit-Damage-from-Crit-Rate bonus. Unlike its own direct Crit
    Rate stat (assumed already baked into Inputs!crit_rate — see the "baked into Inputs" convention),
    this dependent bonus IS a real, live term: it must react to the character's actual current
    Crit Rate (direct clarification from the user — Sensitivity sweeping Crit Rate should show
    the knock-on Crit Damage gain from an equipped Book of Ancient, not just the direct stat)."""
    return f'IF({eq_expr},{star_lookup_expr(star_expr, "book_of_ancient_crit_damage_pct_of_crit_rate")}/100*({crit_rate_total_expr}),0)'


def roc_startup_uptime_expr(monster_type_expr, fight_duration_expr, startup_expr):
    """Ring of Cycles only starts activating 5 seconds into the fight (confirmed by the user), but
    the first `startup_expr` seconds are spent casting buffs with no damage dealt anyway (user's
    relaxation), so it only has to cover the damage window [startup, D]: uptime over that window
    is (D-max(5,startup))/(D-startup). Outside fixed-duration content startup is 0 (plain
    (D-5)/D, incl. PvP); steady-state content (fight_duration = 0, e.g. Chapter Hunt) has no
    meaningful startup window: full uptime."""
    eff_d = f'IF({monster_type_expr}="pvp",{PVP_FIGHT_DURATION},{fight_duration_expr})'
    steady = f'AND({monster_type_expr}<>"pvp",{fight_duration_expr}=0)'
    return f'IF({steady},1,IF({eff_d}-({startup_expr})<=0,1,MAX(0,{eff_d}-MAX(5,{startup_expr}))/({eff_d}-({startup_expr}))))'


def roc_main_startup_ref():
    return f'Summary!$B${R_STARTUP_TIME}'


def artifact_ring_of_cycles_exprs(eq_expr, star_expr, threshold_cr_expr, monster_type_expr, fight_duration_expr, startup_expr):
    """Returns (crit_rate_bonus, skill_dmg_bonus, basic_attack_dmg_bonus) expression strings.
    Basic Attack Damage scales continuously per 1% of Crit Rate excess above 100% (capped at
    100 excess points, i.e. 200% Crit Rate) rather than jumping every 10 points — modeled this
    way per the user's explicit choice, so Sensitivity's "+1%" test reflects a smooth marginal
    value everywhere instead of aliasing depending on how close the current value sits to a
    10-point boundary."""
    up = roc_startup_uptime_expr(monster_type_expr, fight_duration_expr, startup_expr)
    crit_rate = f'{up}*IF(AND({eq_expr},({threshold_cr_expr})<100),{star_lookup_expr(star_expr, "ring_of_cycles_crit_rate")},0)'
    skill_dmg = f'{up}*IF(AND({eq_expr},({threshold_cr_expr})>=100),{star_lookup_expr(star_expr, "ring_of_cycles_skill_damage")},0)'
    excess_points = f'IF(AND({eq_expr},({threshold_cr_expr})>=100),MIN(100,({threshold_cr_expr})-100),0)'
    basic_atk = f'({up}*({excess_points})*{star_lookup_expr(star_expr, "ring_of_cycles_basic_attack_damage_per_point")})'
    return crit_rate, skill_dmg, basic_atk


def artifact_candle_exprs(eq_expr, monster_type_expr, content_type_expr, fight_duration_expr, fda_expr, star_expr):
    """Returns (final_damage_bonus, boss_damage_bonus) expression strings. Per a game patch:
    Final Damage is active at 100% uptime for the whole fight (no longer a 30s window) whenever
    Candle is active at all. Boss Monster Damage only affects boss-directed damage, so its average
    must be weighted by how much of the time-the-boss-is-actually-present (not the whole fight)
    its own [20,40]s window overlaps — 20s in Breakthrough (boss present the entire 20-40s the
    boss exists, since Breakthrough's own fixed duration is exactly 40s: 100% uptime), 30s in
    Hero Dungeon (boss present 30-50s, window only overlaps 30-40s: 50% uptime), 0 (boss present
    from t=0) elsewhere, all confirmed by the user with worked examples."""
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
    """Renewal-theory coverage fraction for a Poisson-refreshed fixed-duration (5s) window. Not
    effective in Chapter Hunt (confirmed by the user)."""
    uptime = f'(1-EXP(-(0.2*{aps_expr})*5))'
    return f'IF(AND({eq_expr},{content_type_expr}<>"Chapter Hunt"),{star_lookup_expr(star_expr, "peach_tree_enemy_dmg_taken")}*{uptime},0)'


def artifact_silver_pendant_expr(eq_expr, star_expr, aps_expr, content_type_expr):
    """M/M/5/5 Erlang-loss approximation (exponential-mean-5s service in place of the true
    deterministic 5s window) — stationary distribution via the offered-load weights rho^n/n!.
    Not effective in Chapter Hunt (confirmed by the user)."""
    rho = f'(0.15*{aps_expr}*5)'
    weights = [f'({rho})^{n}/{f}' for n, f in enumerate([1, 1, 2, 6, 24, 120])]
    weight_sum = "+".join(f'({w})' for w in weights)
    weighted_sum = "+".join(f'{n}*({w})' for n, w in enumerate(weights))
    avg_stacks = f'(({weighted_sum})/({weight_sum}))'
    return f'IF(AND({eq_expr},{content_type_expr}<>"Chapter Hunt"),{star_lookup_expr(star_expr, "silver_pendant_enemy_dmg_taken")}*{avg_stacks},0)'



def artifact_athena_max_damage_expr(eq_expr, star_expr, attack_speed_total_expr):
    """Athena Pierce's Old Gloves' dependent Max-Damage-from-Attack-Speed bonus — same "live,
    reacts to current stat" treatment as Book of Ancient's Crit Damage above; only the direct
    Attack Speed stat itself is assumed baked into Inputs!attack_speed."""
    return f'IF({eq_expr},{star_lookup_expr(star_expr, "athena_gloves_max_damage_pct_of_attack_speed")}/100*({attack_speed_total_expr}),0)'


def artifact_hexagon_expr(eq_expr, monster_type_expr, fight_duration_expr, star_expr):
    """One-time battle-start ramp (not a repeating/overlapping buff) — see KNOWN_GAPS.md."""
    eff_d = f'IF({monster_type_expr}="pvp",{PVP_FIGHT_DURATION},{fight_duration_expr})'
    steady = f'AND({monster_type_expr}<>"pvp",{fight_duration_expr}=0)'
    avg_stacks = (
        f'IF({steady},3,IF({eff_d}<=20,0,IF({eff_d}<=40,({eff_d}-20)/({eff_d}),'
        f'IF({eff_d}<=60,(2*{eff_d}-60)/({eff_d}),(3*{eff_d}-120)/({eff_d})))))'
    )
    return f'IF({eq_expr},{star_lookup_expr(star_expr, "hexagon_necklace_damage")}*({avg_stacks}),0)'


def artifact_rainbow_snail_exprs(eq_expr, monster_type_expr, fight_duration_expr, fda_expr, star_expr):
    """Returns (crit_rate_bonus, crit_damage_bonus) expression strings."""
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
    """Reference value only (see the "baked into Inputs" convention) — its Final Damage bonus, active
    only in the 5 Growth Dungeon content types, is assumed already folded into Inputs!final_damage
    when equipped."""
    return f'IF(AND({eq_expr},{_growth_dungeon_gate_expr(content_type_expr)}),{star_lookup_expr(star_expr, "clear_spring_water_final_damage")},0)'


def artifact_old_music_box_expr(eq_expr, content_type_expr, star_expr):
    """Real, live Attack% bonus. The actual mechanic (proc on being debuffed, 25s duration, 20s
    cooldown) isn't modeled — collapsed to a flat content-type uptime assumption confirmed by the
    user (see KNOWN_GAPS.md): 0% in Chapter Hunt/Breakthrough/the 5 Growth Dungeon types, 100% in
    World Boss/PvP, 60/70 in Chapter Boss."""
    never_cond = "OR(" + ",".join(
        f'{content_type_expr}="{c}"' for c in ["Chapter Hunt", "Breakthrough"] + GROWTH_DUNGEON_CONTENT_TYPES
    ) + ")"
    always_cond = f'OR({content_type_expr}="World Boss",{content_type_expr}="PvP")'
    uptime = f'IF({never_cond},0,IF({always_cond},1,IF({content_type_expr}="Chapter Boss",60/70,0)))'
    return f'IF({eq_expr},{star_lookup_expr(star_expr, "old_music_box_attack_pct")}*({uptime}),0)'


def artifact_soul_contract_pct_expr(eq_expr, content_type_expr, star_expr):
    """Real, live Skill Cooldown Decrease %, active only in Chapter Hunt — applied as an extra
    multiplicative wrapper around effective_cooldown_expr(...) at every call site, not by changing
    that function's own (flat-seconds) signature."""
    return f'IF(AND({eq_expr},{content_type_expr}="Chapter Hunt"),{star_lookup_expr(star_expr, "soul_contract_cooldown_decrease_pct")},0)'


def artifact_soul_pouch_reference_expr(eq_expr, monster_type_expr, star_expr):
    """Reference value only (see the "baked into Inputs" convention) — its Final Damage bonus, active
    only in PvP ("Arena"), is assumed already folded into Inputs!final_damage when equipped."""
    return f'IF(AND({eq_expr},{monster_type_expr}="pvp"),{star_lookup_expr(star_expr, "soul_pouch_final_damage")},0)'


def artifact_flaming_lava_expr(eq_expr, star_expr, content_type_expr):
    """Real, live Final Damage source. Always assumes the target has a debuff (the wiki's middle
    tier) — buff/barrier target states aren't modeled (see KNOWN_GAPS.md) — except in Chapter
    Hunt, where the target has neither a buff, debuff, nor barrier, so this is 0 (confirmed by
    the user)."""
    return f'IF(AND({eq_expr},{content_type_expr}<>"Chapter Hunt"),{star_lookup_expr(star_expr, "flaming_lava_final_damage_debuffed")},0)'


def artifact_icy_soul_rock_expr(eq_expr, star_expr):
    """Real, live Crit Damage source. MP isn't modeled at all (see [[mp_cost_modeling_shelved]]) —
    assumes 50% of time at >=75% MP (doubled bonus) / 50% at 50-75% MP (base bonus), averaging to
    1.5x the base star value, confirmed by the user."""
    return f'IF({eq_expr},1.5*{star_lookup_expr(star_expr, "icy_soul_rock_crit_damage")},0)'


def artifact_secret_map_exprs(eq_expr, monster_type_expr, content_type_expr, star_expr):
    """Returns (attack_pct_bonus, normal_branch_final_damage_bonus), both real/live. The Final
    Damage bonus is U-column (normal branch) only — never S (boss) or PvP — per the user's
    enemy-count assumption (10+ enemies assumed whenever "normal", exactly 1 for "boss"/PvP);
    tripled in the 5 Growth Dungeon content types."""
    attack_pct = f'IF({eq_expr},{star_lookup_expr(star_expr, "secret_map_attack_pct")},0)'
    final_dmg_normal = (
        f'IF(AND({eq_expr},{monster_type_expr}<>"pvp"),'
        f'{star_lookup_expr(star_expr, "secret_map_final_damage")}*IF({_growth_dungeon_gate_expr(content_type_expr)},3,1),0)'
    )
    return attack_pct, final_dmg_normal


def artifact_reindeer_spear_attack_pct_expr(eq_expr, star_expr):
    """Real, live Attack% bonus (unlike its Defense Penetration, this is never baked into Inputs)."""
    return f'IF({eq_expr},{star_lookup_expr(star_expr, "reindeer_spear_attack_pct")},0)'


def artifact_reindeer_spear_base_def_pen_reference_expr(eq_expr, star_expr):
    """Reference value only (see the "baked into Inputs" convention) — the BASE (1x, normal-monster)
    Defense Penetration is assumed already folded into Inputs!def_pen when equipped."""
    return f'IF({eq_expr},{star_lookup_expr(star_expr, "reindeer_spear_def_pen")},0)'


def artifact_reindeer_spear_extra_mult_expr(monster_type_expr):
    """Extra multiples of the spear's own base Defense Penetration granted beyond the 1x already
    baked into Inputs!def_pen — 1 extra (2x total) for PvP, 2 extra (3x total) for boss (the
    S-column branch represents both the real "boss" hypothetical AND real PvP, since PvP routes
    100% through S via normal_weight_frac=0). The normal branch (U) always gets 0 extra — matches
    the wiki's 1x/2x/3x = normal/PvP/boss progression exactly."""
    return f'IF({monster_type_expr}="pvp",1,2)'


def artifact_cursed_doll_reference_expr(eq_expr, star_expr):
    """Reference value only (baked into Inputs!final_damage) — accuracy/evasion behavior not
    modeled at all; always assumes the "give Final Damage" branch, never the evade-triggered loss,
    per the user."""
    return f'IF({eq_expr},{star_lookup_expr(star_expr, "cursed_doll_final_damage")},0)'


def artifact_arwens_glass_shoes_expr(eq_expr, star_expr):
    """Arwen's Glass Shoes: Companion Summoning Time Increase % (percentage points; star 0 = 20, star 5 = 40, linear steps in between, all
    user-confirmed - see ARTIFACT_STAR_VALUES).  0 when not equipped."""
    return f'IF({eq_expr},{star_lookup_expr(star_expr, "arwens_glass_shoes_summon_time_increase_pct")},0)'


def companion_summon_time_inc_expr(input_expr, arwens_expr):
    """The companion's effective Summoning Time Increase % = the Inputs value + Arwen's Glass Shoes (every host `inc` goes through here)."""
    return f'({input_expr}+{arwens_expr})'


def artifact_horn_flute_full_expr(eq_expr, content_type_expr, star_expr):
    """Horn Flute's Final Damage while its companion is out (doubled in Chapter Boss)."""
    return (f'IF({eq_expr},{star_lookup_expr(star_expr, "horn_flute_final_damage")}'
            f'*IF({content_type_expr}="Chapter Boss",2,1),0)')


def artifact_horn_flute_expr(eq_expr, content_type_expr, star_expr, uptime_expr):
    """Real, live Final Damage source - the character's own portion; the companion's own portion is the Companion sheet's `rhoH` snapshot
    ratio.  The flute is on while a companion is summoned, so its fight-average value is the full value x the share of the fight the
    companion is out (`Companion!horn_uptime`: summon time and duration from the companion model; Chapter Hunt = D/90; PvP included).
    With no companion chosen the same timing is assumed (a companion is imagined to be summoned), so the artifact keeps a value."""
    return f'{artifact_horn_flute_full_expr(eq_expr, content_type_expr, star_expr)}*({uptime_expr})'


def artifact_bottle_of_emotion_attack_pct_expr(eq_expr, star_expr):
    """Real, live Attack% bonus — same shared bucket as every other skill/artifact Attack% source
    (confirmed by the user, correcting an earlier draft that had this baked in)."""
    return f'IF({eq_expr},{star_lookup_expr(star_expr, "bottle_of_emotion_attack_pct")},0)'


def artifact_bottle_of_emotion_final_damage_value_expr(eq_expr, star_expr, attack_speed_expr):
    """Attack-Speed-*dependent* Final Damage value at a given effective Attack Speed — baked into
    Inputs!final_damage when equipped (only the Sensitivity delta matters; see build_stat_block's
    two-case treatment, same shape as Book of Ancient's dependent Crit Damage). Uses the same
    continuous excess-scaling shape Ring of Cycles was fixed to use earlier this session
    (per-1%-point, not discrete 3%-steps): per_point = per_3%_value/3."""
    per_point = f'({star_lookup_expr(star_expr, "bottle_of_emotion_final_damage_per_3pct_as")}/3)'
    cap = star_lookup_expr(star_expr, "bottle_of_emotion_final_damage_cap")
    return f'IF({eq_expr},MIN({cap},MAX(0,{per_point}*({attack_speed_expr}-60))),0)'


def artifact_alliance_badge_expr(eq_expr, star_expr):
    """Real, live Attack% bonus — same shared bucket as skills/other Attack%-granting artifacts,
    per the user ("same att% as skills and music box etc")."""
    return f'IF({eq_expr},{star_lookup_expr(star_expr, "alliance_badge_attack_pct")},0)'


def artifact_sayrams_necklace_exprs(eq_expr, star_expr):
    """Returns (normal_damage_bonus, boss_damage_bonus). Per the user, ignore the wiki's
    target-count gating clause entirely and always grant both simultaneously — feeds the EXISTING
    boss_damage%/normal_damage% additive buckets directly (already branch-specific by
    construction), no new architecture needed."""
    normal = f'IF({eq_expr},{star_lookup_expr(star_expr, "sayrams_necklace_normal_damage")},0)'
    boss = f'IF({eq_expr},{star_lookup_expr(star_expr, "sayrams_necklace_boss_damage")},0)'
    return normal, boss


def artifact_lit_lamp_reference_expr(eq_expr, content_type_expr, star_expr):
    """Reference value only (baked into Inputs!final_damage) — active only in World Boss content,
    per the wiki's "[World Boss]" tag."""
    return f'IF(AND({eq_expr},{content_type_expr}="World Boss"),{star_lookup_expr(star_expr, "lit_lamp_final_damage")},0)'


def artifact_fire_flower_exprs(eq_expr, star_expr):
    """Returns (normal_branch_final_damage_bonus, boss_pvp_branch_final_damage_bonus). Per the
    user, always assume 10 targets against normal monsters, always 1 against boss/PvP (instead of
    the wiki's real per-target-count scaling, capped at 10)."""
    per_target = star_lookup_expr(star_expr, "fire_flower_final_damage_per_target")
    normal = f'IF({eq_expr},10*{per_target},0)'
    boss = f'IF({eq_expr},1*{per_target},0)'
    return normal, boss


def artifact_star_rock_reference_expr(eq_expr, star_expr):
    """Reference value only (baked into Inputs!boss_damage) — the wiki's "increases damage taken"
    clause refers to the CHARACTER's own incoming damage (a defensive downside, not enemy damage
    taken), ignored per the user."""
    return f'IF({eq_expr},{star_lookup_expr(star_expr, "star_rock_boss_damage")},0)'


# Chalice (Chapter Hunt steady state): proc chance per kill and assumed kill rate (user, 2026-11-07)
CHALICE_PROC_CHANCE = 0.02
CHALICE_KILLS_PER_MINUTE = 100


def artifact_chalice_exprs(eq_expr, monster_type_expr, content_type_expr, fight_duration_expr, star_expr):
    """Returns (normal_branch_final_damage_bonus, boss_branch_final_damage_bonus). Real, live,
    active during the LAST 30 SECONDS of the fight (simplified per the user from the real 2%-
    chance-per-hit/100%-on-boss-kill proc), relevant whenever monster_type is "normal" or
    "breakthrough" (never "boss"/"pvp" — confirmed by the user). Generalizes the boss_appear_time
    overlap concept Candle already uses to also cover pure-"normal" content (where there's no
    boss ever, so the "normal phase" is the WHOLE fight instead of [0,boss_appear])."""
    boss_appear = f'IF({content_type_expr}="Breakthrough",20,IF({content_type_expr}="Hero Dungeon",30,0))'
    normal_phase_end = f'IF({monster_type_expr}="breakthrough",{boss_appear},{fight_duration_expr})'
    activation_start = f'MAX(0,{fight_duration_expr}-30)'
    normal_uptime = (
        f'IF(OR({fight_duration_expr}=0,{normal_phase_end}=0),0,'
        f'MAX(0,{normal_phase_end}-{activation_start})/{normal_phase_end})'
    )
    # Steady-state pure-normal content (Chapter Hunt: no fixed fight length): every kill has a CHALICE_PROC_CHANCE
    # chance to (re)start the 30s buff, at CHALICE_KILLS_PER_MINUTE kills/min (user, 2026-11-07). The timer resets on
    # a new proc, so the buff is on iff at least one of the last (kills/min * 30/60) kills procced:
    # uptime = 1-(1-p)^(kills in 30s) (=63.6% for 100/min and 2%) - the expected on-time including the variance of
    # the proc, instead of the 'on for exactly 1 of every 30s' point estimate.
    chalice_steady_uptime = f'(1-(1-{CHALICE_PROC_CHANCE})^({CHALICE_KILLS_PER_MINUTE}*30/60))'
    normal_uptime = f'IF(AND({monster_type_expr}="normal",{fight_duration_expr}=0),{chalice_steady_uptime},{normal_uptime})'
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
    """Real, live Crit Rate bonus, boss-branch only (never PvP, never normal) — the wiki's own
    "when attacking a boss" condition. Composed into extra_boss_mult_r via a crit-blend ratio
    correction at the call site (see build_calc_sheet/build_stat_block), since Crit Rate feeds the
    shared, nonlinear N crit-blend formula rather than a simple multiplicative bucket."""
    return f'IF(AND({eq_expr},{monster_type_expr}<>"pvp"),{star_lookup_expr(star_expr, "contract_of_darkness_crit_rate")},0)'


def artifact_shamaness_marble_reference_expr(eq_expr, star_expr):
    """Reference value only (baked into Inputs!buff_duration_increase_pct, an existing Inputs
    stat) — no new bucket needed."""
    return f'IF({eq_expr},{star_lookup_expr(star_expr, "shamaness_marble_buff_duration_increase_pct")},0)'


def artifact_charm_of_the_undead_expr(eq_expr, monster_type_expr, fight_duration_expr, star_expr):
    """Real, live Attack% bonus (same shared bucket as Old Music Box/Secret Map/etc.), periodic
    uptime: first activates at t=10s, active 5s every 10s thereafter (10-15, 20-25, 30-35, ...,
    per the user) — a periodic pattern, distinct from Hexagon Necklace's monotonic ramp. Steady
    state (Chapter Hunt) converges to the long-run 50% duty cycle."""
    eff_duration = f'IF({monster_type_expr}="pvp",{PVP_FIGHT_DURATION},{fight_duration_expr})'
    steady_state = f'AND({monster_type_expr}<>"pvp",{fight_duration_expr}=0)'
    dprime = f'MAX(0,{eff_duration}-10)'
    full_cycles = f'INT({dprime}/10)'
    remainder = f'({dprime}-10*{full_cycles})'
    active = f'(5*{full_cycles}+MIN({remainder},5))'
    uptime = f'IF({steady_state},0.5,{active}/{eff_duration})'
    return f'IF({eq_expr},{star_lookup_expr(star_expr, "charm_of_the_undead_attack_pct")}*({uptime}),0)'

def IB(key):
    if key in DERIVED_ROW:
        return f"Summary!$B${DERIVED_ROW[key]}"
    if key in ARTIFACT_INPUT_CELL:
        return ARTIFACT_INPUT_CELL[key]
    if key in COMPANION_INPUT_CELL:
        return COMPANION_INPUT_CELL[key]
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
        "STATUS_EFFECT_DAMAGE % (Inputs) is extra damage while the enemy is frozen/stunned; World Boss and Enhancement Dungeon also have KO phases (x2). "
        "The Timeline sheet shows when the optimal player casts buffs and cooldown skills around those windows and what the windows are worth.",
        "Companion (Inputs, per content type) picks the summoned ally and CompanionsInput holds the level of each companion you own; the Companion sheet is its "
        "damage / uplift chain (shared model: see KNOWN_GAPS.md 'Companions'), Sensitivity has the Companion Comparison table.",
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
        "Content Type (Inputs) picks what you're fighting — Chapter Boss/Breakthrough/PvP/EXP "
        "Dungeon/Equipment Dungeon/Weapon Dungeon/Enhancement Dungeon/Hero Dungeon/World Boss/"
        "Chapter Hunt — and Monster Defense and Fixed Fight Duration are both auto-computed from "
        "it (plus Chapter/Stage for the chapter- and dungeon-based types); PvP still forces its "
        "own fight length (Inputs -> PvP Fight Length, default 15 seconds) and uses your own Defense stat as the opponent's Defense "
        "estimate. See README.md's 'Content Type' section for the exact formulas.",
        "The player's own stun (Gust Charm, 2 s) opens Status Effect Damage windows like the companion's (Chapter Breakthrough's boss phase is lengthened by it). "
        "Not modeled (out of scope): the player's other crowd control, Accuracy/Evasion/Defense reduction, "
        "movement speed and the character's own Defense stat.",
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

    COMPUTED_FILL = PatternFill("solid", fgColor="D9D9D9")

    # One column per content type (C-L) for every row that can plausibly differ by loadout —
    # confirmed by the user, since real gear/artifact sets often differ by content. Column B
    # becomes a resolved/computed cell (INDEX/MATCH against C:L, keyed on the SAME Content Type
    # dropdown at B4 that already exists — no new selector needed) so every downstream formula in
    # the whole workbook (Calc/Summary/Sensitivity/Artifacts, which only ever call IB()) keeps
    # working completely unmodified; see PER_CONTENT_TYPE_INPUT_KEYS.
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
        ("status_effect_damage", "STATUS_EFFECT_DAMAGE % (extra damage while the enemy is frozen/stunned/KO'd; 0 = no bonus - KO still doubles damage)", 0),
        ("min_damage", "MIN_DAMAGE %", 100),
        ("max_damage", "MAX_DAMAGE %", 100),
        ("final_damage", "FINAL_DAMAGE % (base)", 0),
        ("skill_lvl_1st", "Skill Level Bonus — 1st Job", 0),
        ("skill_lvl_2nd", "Skill Level Bonus — 2nd Job", 0),
        ("skill_lvl_3rd", "Skill Level Bonus — 3rd Job", 0),
        ("skill_lvl_4th", "Skill Level Bonus — 4th Job", 0),
        ("skill_lvl_all", "Skill Level Bonus — All Skills", 0),
    ]

    # A few per-content-type rows aren't relevant for every content type (confirmed by the user)
    # — columns for content types NOT listed here are left entirely blank (gray, no value, no
    # dropdown) rather than showing an unused default. Keys not listed here apply to all 10.
    INPUT_ROW_APPLICABLE_CONTENT_TYPES = {
        "chapter_stage": [
            "Chapter Boss", "Breakthrough", "Chapter Hunt", "Weapon Dungeon",
            "Equipment Dungeon", "Enhancement Dungeon", "EXP Dungeon", "Hero Dungeon",
        ],
        "boss_normal_weight_choice": ["Breakthrough", "Hero Dungeon"],
        "pvp_fight_length": ["PvP"],
        "max_enemies_hit": [
            "EXP Dungeon", "Equipment Dungeon", "Chapter Hunt", "Breakthrough", "Hero Dungeon",
        ],
    }
    # Chapter-Stage's expected FORMAT differs by content type (chapter-substage vs. a bare
    # chapter number vs. a bare stage number — see chapter/stage's own IFERROR-guarded parsing,
    # which already tolerates all three shapes and just ignores whichever half isn't consumed for
    # a given content type). Only Breakthrough/Chapter Hunt keep the chapter-substage shape they
    # already had; the other 6 applicable columns get a correctly-shaped default instead.
    CHAPTER_STAGE_DEFAULT_BY_CONTENT_TYPE = {
        "Chapter Boss": "28", "Breakthrough": "28-9", "Chapter Hunt": "28-9",
        "Weapon Dungeon": "80", "Equipment Dungeon": "80", "Enhancement Dungeon": "80",
        "EXP Dungeon": "80", "Hero Dungeon": "80",
    }
    # NOTE: a past migration briefly left Breakthrough/Chapter Hunt-style "28-9" text
    # duplicated into the other 6 applicable columns (which need a bare number instead) —
    # that one-time cleanup used to force those 6 columns back to a hardcoded default on
    # every rebuild, silently discarding the user's own real, correctly-formatted values on
    # every subsequent rebuild too. Fixed: carried-over values are now trusted for every
    # content type, same as any other per-content-type Inputs row — only genuinely missing
    # values fall back to the default.

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
                cell.value = per_ct.get(ct, row_default)
            else:
                cell.value = per_ct.get(ct, default)
            cell.fill = INPUT_FILL
        resolved = ws.cell(row=r, column=2, value=f'=INDEX($C${r}:$L${r},MATCH($B$4,$C$2:$L$2,0))')
        resolved.fill = COMPUTED_FILL

    for key, label, default in rows:
        _write_input_row(key, label, default)

    ws.cell(row=31, column=1, value="Additional Bonuses").font = SECTION_FONT
    bonus_rows = [
        ("skill_cooldown_decrease", "Skill Cooldown Decrease (seconds; applies to every cooldown — skills, buffs and passives)", 0),
        ("basic_attack_target_increase", "Basic Attack Target Increase (flat, adds to the 6-target Showdown base)", 1),
        ("buff_duration_increase_pct", "Buff Duration Increase %", 0),
        ("companion_summon_time_increase_pct", "Companion Summoning Time Increase % (companion duration = 30s x (1 + (this + Arwen's Glass Shoes, if equipped)/100); summon cooldown is always 90s; see Companion sheet)", 0),
        ("boss_normal_weight_choice", "Boss/Normal Emphasis (used when Content Type is Breakthrough or Hero Dungeon)", "A Little More Normal"),
        ("max_enemies_hit", "Max Enemies Actually In Range (normal monsters only; default 999 = uncapped)", 999),
        ("incoming_hit_rate", "Incoming Hit Rate (hits/sec taken — user-estimated, feeds Shadow Shifter's counterattack only)", 1),
    ]
    for key, label, default in bonus_rows:
        _write_input_row(key, label, default)

    # Companion — which companion is summoned in each content type (see the Companion sheet and src/companion_model.py).
    _write_input_row("companion_choice", "Companion (None or one of the 16) — the companion summoned in this content type (levels: CompanionsInput sheet)", "None")
    dv_companion_choice = DataValidation(type="list", formula1='"' + ",".join(cm.COMPANION_CHOICES) + '"', allow_blank=False)
    ws.add_data_validation(dv_companion_choice)
    for _i in range(len(CONTENT_TYPES)):
        dv_companion_choice.add(ws.cell(row=IN["companion_choice"], column=3 + _i))

    # PvP fight length — every PvP duration-dependent quantity (DoT/summon windows, buff uptimes, the one-cast-per-
    # fight cast rate, the time-based artifacts) reads this through PVP_FIGHT_DURATION. PvP content only.
    ws.cell(row=INPUT_PVP_SECTION_ROW, column=1, value="PvP").font = SECTION_FONT
    _write_input_row("pvp_fight_length", "PvP Fight Length (seconds; PvP content only — shorter fights cut DoT/summon ticks and buff uptime)", 15)
    dv_pvp_len = DataValidation(type="decimal", operator="greaterThanOrEqual", formula1="1", allow_blank=False)
    ws.add_data_validation(dv_pvp_len)
    dv_pvp_len.add(ws.cell(row=IN["pvp_fight_length"], column=3 + CONTENT_TYPES.index("PvP")))

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

    # Equipped-artifact slots — moved here from the ArtifactsInput sheet per the user, so equip
    # state sits alongside the rest of the per-content-type loadout instead of on a separate
    # sheet. Appended after everything else so no existing IN-dict row number has to shift. One
    # resolved column B (INDEX/MATCH against C:L, same mechanism as every other per-content-type
    # row) + per-content-type raw picks in C:L per slot.
    ws.cell(row=INPUT_ARTIFACT_SLOTS_SECTION_ROW, column=1, value="Equipped Artifacts (up to 4)").font = SECTION_FONT
    artifact_names = list(ARTIFACT_LABELS.values())
    # Data validation's inline quoted-list form is capped at 255 characters by Excel — the 34
    # artifact names plus "(none)" already exceed that, which silently corrupts the file (Excel's
    # "we found a problem with some content" repair prompt on open). Use a range-reference list
    # instead (no length limit), same pattern as PotentialCubes' stat dropdown — a tucked-away
    # helper column (N) holds the choices.
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
    # Row 37 intentionally unused (was AGG_MAX_DAMAGE — removed as redundant with athena_max_
    # damage above; Athena's Gloves' Max Damage bonus never feeds anything real, see comment
    # above athena_max_damage's row-write).
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
    # No-DPS-effect artifacts (see ARTIFACT_NO_DPS_EFFECT: raid / guild content and stats the model
    # does not use) — constant-0 rows kept only for ArtifactsInput tracking consistency.  Arwen's
    # Glass Shoes (row 78) is NOT one of them: it adds Companion Summoning Time Increase %.
    "ancient_text_piece_reference": 72,
    "lunar_dew_reference": 73,
    "pink_beans_giant_rib_reference": 74,
    "horntails_scale_reference": 75,
    "zakums_stone_piece_reference": 76,
    "mushmoms_cap_reference": 77,
    "arwens_glass_shoes_summon_time_increase_pct": 78,
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
    assumed already baked into Inputs!crit_rate/attack_speed (see the "baked into Inputs" convention) —
    only their dependent bonus is computed here. Every other artifact's full bonus is a real,
    additive term on top of Inputs, rolled up into the aggregate bucket rows at the bottom, which
    the main Calc/Summary pipeline (and Sensitivity's build_stat_block mirror) consume directly."""
    ws = wb.create_sheet("Artifacts")
    ws["A1"] = "Night Lord — Artifacts (Equip Effect)"
    ws["A1"].font = Font(bold=True, size=14)

    r = ART_ROW
    eq = {k: IB(f"{k}_equipped") for k in ARTIFACT_LABELS}
    star = {k: IB(f"{k}_star") for k in ARTIFACT_LABELS}

    # Book of Ancient — Crit Rate is assumed baked into Inputs!crit_rate, and so is this dependent
    # Crit-Damage-from-Crit-Rate bonus (both stats fully baked in, per the user) — this row is a
    # REFERENCE value only (using the FULL current Crit Rate, Inputs plus every real additive
    # artifact source — Ring of Cycles, Rainbow-colored Snail Shell — to help you keep
    # Inputs!crit_damage in sync), never summed into anything real; Sensitivity reacts to it via
    # a block-local delta instead (see build_stat_block).
    ws.cell(row=r["boa_crit_damage"], column=1, value="Book of Ancient — Crit Damage (from Crit Rate, reference only)")
    ws.cell(row=r["boa_crit_damage"], column=2, value=(
        f'=IF({eq["book_of_ancient"]},{star_lookup_expr(star["book_of_ancient"], "book_of_ancient_crit_damage_pct_of_crit_rate")}/100'
        f'*({IB("crit_rate")}+Summary!$B${R_CRIT_RATE_BONUS}+B{r["roc_crit_rate"]}+B{r["rainbow_crit_rate"]}),0)'
    ))

    # Ring of Cycles — the "every 5 seconds, cycles based on current Crit Rate" description
    # stabilizes to a static threshold branch, since Crit Rate doesn't fluctuate mid-fight in this
    # model. Threshold uses every OTHER real Crit Rate source (Inputs, the live Summary crit-rate bonus, already includes Book of
    # Ancient if equipped, plus Rainbow Snail Shell) — not its own contribution, avoiding self-reference.
    ws.cell(row=r["roc_threshold_cr"], column=1, value="Ring of Cycles — Threshold Crit Rate (excl. self)")
    ws.cell(row=r["roc_threshold_cr"], column=2, value=f'={IB("crit_rate")}+Summary!$B${R_CRIT_RATE_BONUS}+B{r["rainbow_crit_rate"]}')
    ws.cell(row=r["roc_crit_rate"], column=1, value="Ring of Cycles — Crit Rate (if threshold < 100%)")
    ws.cell(row=r["roc_crit_rate"], column=2, value=(
        f'={roc_startup_uptime_expr(IB("monster_type"), IB("fight_duration"), roc_main_startup_ref())}*IF(AND({eq["ring_of_cycles"]},B{r["roc_threshold_cr"]}<100),'
        f'{star_lookup_expr(star["ring_of_cycles"], "ring_of_cycles_crit_rate")},0)'
    ))
    ws.cell(row=r["roc_skill_damage"], column=1, value="Ring of Cycles — Skill Damage (if threshold >= 100%)")
    ws.cell(row=r["roc_skill_damage"], column=2, value=(
        f'={roc_startup_uptime_expr(IB("monster_type"), IB("fight_duration"), roc_main_startup_ref())}*IF(AND({eq["ring_of_cycles"]},B{r["roc_threshold_cr"]}>=100),'
        f'{star_lookup_expr(star["ring_of_cycles"], "ring_of_cycles_skill_damage")},0)'
    ))
    # Basic Attack Damage scales continuously per 1% of Crit Rate excess above 100% (capped at
    # 100 excess points, i.e. 200% Crit Rate), not in 10-point stacks — deliberate simplification
    # so Sensitivity's "+1%" test reflects a smooth marginal value everywhere.
    ws.cell(row=r["roc_excess_points"], column=1, value="Ring of Cycles — Excess-100% Points (capped at 100)")
    ws.cell(row=r["roc_excess_points"], column=2, value=(
        f'=IF(AND({eq["ring_of_cycles"]},B{r["roc_threshold_cr"]}>=100),'
        f'MIN(100,B{r["roc_threshold_cr"]}-100),0)'
    ))
    ws.cell(row=r["roc_basic_attack_damage"], column=1, value="Ring of Cycles — Basic Attack Damage (excess points x per-point)")
    ws.cell(row=r["roc_basic_attack_damage"], column=2, value=(
        f'={roc_startup_uptime_expr(IB("monster_type"), IB("fight_duration"), roc_main_startup_ref())}*B{r["roc_excess_points"]}*{star_lookup_expr(star["ring_of_cycles"], "ring_of_cycles_basic_attack_damage_per_point")}'
    ))

    # Candle — "at start of battle" / "after 20 seconds" windows, fixed-duration/PvP content only;
    # exactly 0 in Chapter Hunt (fight_duration=0, no discrete battle-start event in this model).
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
    # In Chapter Breakthrough/Hero Dungeon, the boss doesn't actually appear at battle start —
    # only after 20s (Breakthrough) or 30s (Hero Dungeon) of fighting normal monsters first
    # (confirmed by the user) — so the Boss Monster Damage bonus only has real effect during the
    # overlap between its own [20,30]s window and however late the boss actually shows up. Other
    # content types (pure boss or pure normal) assume the boss/target is present from t=0, as before.
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

    # Peach Tree Herb Pouch — a proc that REFRESHES a single 5s timer (not independent, non-
    # refreshing instances) on every subsequent successful proc. Standard renewal-theory coverage
    # fraction for a Poisson-arrival process with a fixed-length refresh window: uptime =
    # 1-EXP(-lambda*duration), where lambda = proc chance x the character's action rate. The "once
    # per battle, if target has buffs" clause is excluded (opponent buff-state isn't modeled
    # anywhere in this project) — flagged in KNOWN_GAPS.md.
    ws.cell(row=r["peach_lambda"], column=1, value="Peach Tree Herb Pouch — Proc Rate (per second)")
    ws.cell(row=r["peach_lambda"], column=2, value=f'=0.2*Summary!$B${R_APS}')
    ws.cell(row=r["peach_uptime"], column=1, value="Peach Tree Herb Pouch — Uptime (refreshing 5s timer)")
    ws.cell(row=r["peach_uptime"], column=2, value=f'=1-EXP(-B{r["peach_lambda"]}*5)')
    ws.cell(row=r["peach_enemy_dmg_taken"], column=1, value="Peach Tree Herb Pouch — Enemy Damage Taken")
    ws.cell(row=r["peach_enemy_dmg_taken"], column=2, value=(
        f'=IF(AND({eq["peach_tree"]},{IB("content_type")}<>"Chapter Hunt"),'
        f'{star_lookup_expr(star["peach_tree"], "peach_tree_enemy_dmg_taken")}*B{r["peach_uptime"]},0)'
    ))

    # Silver Pendant — a 5-slot FIFO queue: a successful proc fills an empty slot, or (if all 5
    # are full) refreshes the oldest slot's countdown. Modeled as an M/M/5/5 Erlang-loss
    # approximation (exponential-mean-5s service in place of the true deterministic 5s window — a
    # standard, well-established queueing approximation; flagged in KNOWN_GAPS.md, same spirit as
    # the existing Potential Cubes EV approximation note). Stationary distribution computed
    # directly via the offered-load weights rho^n/n!, not the recursive Erlang-B blocking formula
    # (mathematically the same underlying loss model; the direct weights are simpler to encode).
    # The "decreases HP Recovery" clause is excluded (affects the target's healing, not the
    # character's own DPS) and target-death resets against normal monsters are not modeled
    # (no monster time-to-kill concept exists anywhere in this project) — both flagged.
    ws.cell(row=r["silver_rho"], column=1, value="Silver Pendant — Offered Load (rho = lambda x duration)")
    ws.cell(row=r["silver_rho"], column=2, value=f'=0.15*Summary!$B${R_APS}*5')
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

    # Athena Pierce's Old Gloves — Attack Speed is assumed baked into Inputs!attack_speed, and so
    # is this dependent Max-Damage-from-Attack-Speed bonus (both stats fully baked in, per the
    # user) — this row is a REFERENCE value only (to help you keep Inputs!max_damage in sync),
    # never summed into anything real; Sensitivity reacts to it via a block-local delta instead
    # (see build_stat_block).
    ws.cell(row=r["athena_max_damage"], column=1, value="Athena Pierce's Old Gloves — Max Damage (from Attack Speed, reference only)")
    ws.cell(row=r["athena_max_damage"], column=2, value=(
        f'=IF({eq["athena_gloves"]},{star_lookup_expr(star["athena_gloves"], "athena_gloves_max_damage_pct_of_attack_speed")}/100'
        f'*{IB("attack_speed")},0)'
    ))

    # Hexagon Necklace — a one-time battle-start ramp (NOT a repeating/overlapping buff): 0 stacks
    # for the first 20s, +1 stack every 20s after, capped at 3 (reached at 60s), never decreasing
    # within a fight. Time-weighted average over a fixed-duration fight of length D derived
    # directly (piecewise), confirmed against hand-worked examples (40s->0.5, 60s->1). Steady-state
    # (Chapter Hunt) = exactly 3 (the cap — the finite ramp-up is negligible over infinite time).
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

    # Rainbow-colored Snail Shell — "at the start of battle... for 15 sec", same fixed-duration/
    # PvP-only pattern as Candle; exactly 0 in Chapter Hunt.
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

    # Clear Spring Water — baked into Inputs when equipped (see the "baked into Inputs" convention); this
    # row is a REFERENCE value only (active only in the 5 Growth Dungeon content types), never
    # summed into anything real; Sensitivity reacts via a block-local delta (see build_stat_block).
    ws.cell(row=r["csw_reference"], column=1, value="Clear Spring Water — Final Damage (reference only, Growth Dungeon types)")
    ws.cell(row=r["csw_reference"], column=2, value="=" + artifact_clear_spring_water_reference_expr(
        eq["clear_spring_water"], IB("content_type"), star["clear_spring_water"],
    ))

    # Old Music Box — real, live Attack% bonus; see artifact_old_music_box_expr for the collapsed
    # content-type uptime assumption (KNOWN_GAPS.md).
    ws.cell(row=r["old_music_box_attack_pct"], column=1, value="Old Music Box — Attack % (content-type uptime assumption)")
    ws.cell(row=r["old_music_box_attack_pct"], column=2, value="=" + artifact_old_music_box_expr(
        eq["old_music_box"], IB("content_type"), star["old_music_box"],
    ))

    # Soul Contract — real, live Skill Cooldown Decrease %, active only in Chapter Hunt; applied at
    # every effective_cooldown_expr(...) call site (see build_calc_sheet/build_stat_block), not here.
    ws.cell(row=r["soul_contract_pct"], column=1, value="Soul Contract — Skill Cooldown Decrease % (Chapter Hunt only)")
    ws.cell(row=r["soul_contract_pct"], column=2, value="=" + artifact_soul_contract_pct_expr(
        eq["soul_contract"], IB("content_type"), star["soul_contract"],
    ))

    # Soul Pouch — baked into Inputs when equipped; REFERENCE value only (active only in PvP).
    ws.cell(row=r["soul_pouch_reference"], column=1, value="Soul Pouch — Final Damage (reference only, PvP/\"Arena\")")
    ws.cell(row=r["soul_pouch_reference"], column=2, value="=" + artifact_soul_pouch_reference_expr(
        eq["soul_pouch"], IB("monster_type"), star["soul_pouch"],
    ))

    # Flaming Lava — real, live Final Damage source; always assumes the target has a debuff (see
    # artifact_flaming_lava_expr — buff/barrier target states aren't modeled, KNOWN_GAPS.md).
    ws.cell(row=r["flaming_lava"], column=1, value="Flaming Lava — Final Damage (always assumes target is debuffed)")
    ws.cell(row=r["flaming_lava"], column=2, value="=" + artifact_flaming_lava_expr(eq["flaming_lava"], star["flaming_lava"], IB("content_type")))

    # Icy Soul Rock — real, live Crit Damage source; MP not modeled, averages to 1.5x the base star
    # value (see artifact_icy_soul_rock_expr, KNOWN_GAPS.md).
    ws.cell(row=r["icy_soul_rock"], column=1, value="Icy Soul Rock — Crit Damage (1.5x-averaged, MP not modeled)")
    ws.cell(row=r["icy_soul_rock"], column=2, value="=" + artifact_icy_soul_rock_expr(eq["icy_soul_rock"], star["icy_soul_rock"]))

    # Secret Map — real, live: Attack% always-on; Final Damage bonus applies ONLY to the normal-
    # monster branch of DPS (never boss/PvP), tripled in the 5 Growth Dungeon content types — see
    # artifact_secret_map_exprs for the enemy-count assumption (KNOWN_GAPS.md).
    secret_map_attack_pct_expr, secret_map_final_dmg_normal_expr = artifact_secret_map_exprs(
        eq["secret_map"], IB("monster_type"), IB("content_type"), star["secret_map"],
    )
    ws.cell(row=r["secret_map_attack_pct"], column=1, value="Secret Map — Attack %")
    ws.cell(row=r["secret_map_attack_pct"], column=2, value="=" + secret_map_attack_pct_expr)
    ws.cell(row=r["secret_map_final_dmg_normal"], column=1, value="Secret Map — Final Damage (normal-monster branch only)")
    ws.cell(row=r["secret_map_final_dmg_normal"], column=2, value="=" + secret_map_final_dmg_normal_expr)

    # Reindeer's Spear — Attack% is real/live; only the BASE (1x) Defense Penetration is baked into
    # Inputs!def_pen (reference row only) — the extra PvP(2x)/boss(3x) multiple is a real, live,
    # S-column-only correction applied directly in build_calc_sheet/build_stat_block (not here,
    # since it depends on the CURRENT monster_type at each branch, not a single sheet-level value).
    ws.cell(row=r["reindeer_spear_attack_pct"], column=1, value="Reindeer's Spear — Attack %")
    ws.cell(row=r["reindeer_spear_attack_pct"], column=2, value="=" + artifact_reindeer_spear_attack_pct_expr(
        eq["reindeer_spear"], star["reindeer_spear"],
    ))
    ws.cell(row=r["reindeer_spear_base_def_pen_reference"], column=1, value="Reindeer's Spear — Base (1x) Defense Penetration (reference only)")
    ws.cell(row=r["reindeer_spear_base_def_pen_reference"], column=2, value="=" + artifact_reindeer_spear_base_def_pen_reference_expr(
        eq["reindeer_spear"], star["reindeer_spear"],
    ))

    # Cursed Doll — baked into Inputs when equipped; REFERENCE value only. Accuracy/evasion not
    # modeled at all (see artifact_cursed_doll_reference_expr, KNOWN_GAPS.md).
    ws.cell(row=r["cursed_doll_reference"], column=1, value="Cursed Doll — Final Damage (reference only)")
    ws.cell(row=r["cursed_doll_reference"], column=2, value="=" + artifact_cursed_doll_reference_expr(
        eq["cursed_doll"], star["cursed_doll"],
    ))

    # Horn Flute — real, live Final Damage source; only the character's own portion, companion
    # summon-window uptime + Chapter Boss doubling (see artifact_horn_flute_expr, KNOWN_GAPS.md).
    ws.cell(row=r["horn_flute"], column=1, value="Horn Flute — Final Damage (character, fight-average over the companion window)")
    ws.cell(row=r["horn_flute"], column=2, value="=" + artifact_horn_flute_expr(
        eq["horn_flute"], IB("content_type"), star["horn_flute"], companion_main_ref("horn_uptime"),
    ))

    # Bottle of Emotion — Attack% is real/live (same shared bucket as skills/other artifacts);
    # its Attack-Speed-dependent Final Damage is baked into Inputs (reference row only).
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

    # Alliance Badge — real, live Attack%, same shared bucket.
    ws.cell(row=r["alliance_badge"], column=1, value="Alliance Badge — Attack %")
    ws.cell(row=r["alliance_badge"], column=2, value="=" + artifact_alliance_badge_expr(
        eq["alliance_badge"], star["alliance_badge"],
    ))

    # Sayram's Necklace — real, live; feeds the EXISTING boss_damage%/normal_damage% buckets
    # directly (see artifact_sayrams_necklace_exprs, KNOWN_GAPS.md for the ignored target-count
    # gating clause).
    sayrams_normal_expr, sayrams_boss_expr = artifact_sayrams_necklace_exprs(eq["sayrams_necklace"], star["sayrams_necklace"])
    ws.cell(row=r["sayrams_necklace_normal"], column=1, value="Sayram's Necklace — Normal Monster Damage")
    ws.cell(row=r["sayrams_necklace_normal"], column=2, value="=" + sayrams_normal_expr)
    ws.cell(row=r["sayrams_necklace_boss"], column=1, value="Sayram's Necklace — Boss Monster Damage")
    ws.cell(row=r["sayrams_necklace_boss"], column=2, value="=" + sayrams_boss_expr)

    # Lit Lamp — baked into Inputs when equipped; REFERENCE value only (World Boss content only).
    ws.cell(row=r["lit_lamp_reference"], column=1, value="Lit Lamp — Final Damage (reference only, World Boss)")
    ws.cell(row=r["lit_lamp_reference"], column=2, value="=" + artifact_lit_lamp_reference_expr(
        eq["lit_lamp"], IB("content_type"), star["lit_lamp"],
    ))

    # Fire Flower — real, live; per-branch Final Damage (10 targets assumed vs. normal monsters, 1
    # vs. boss/PvP, per the user) — composed into extra_normal_mult_r/extra_boss_mult_r.
    fire_flower_normal_expr, fire_flower_boss_expr = artifact_fire_flower_exprs(eq["fire_flower"], star["fire_flower"])
    ws.cell(row=r["fire_flower_normal"], column=1, value="Fire Flower — Final Damage (normal-monster branch, 10 targets assumed)")
    ws.cell(row=r["fire_flower_normal"], column=2, value="=" + fire_flower_normal_expr)
    ws.cell(row=r["fire_flower_boss"], column=1, value="Fire Flower — Final Damage (boss/PvP branch, 1 target assumed)")
    ws.cell(row=r["fire_flower_boss"], column=2, value="=" + fire_flower_boss_expr)

    # Star Rock — baked into Inputs when equipped; REFERENCE value only. The "increases damage
    # taken" clause refers to the character's own incoming damage, ignored per the user.
    ws.cell(row=r["star_rock_reference"], column=1, value="Star Rock — Boss Monster Damage (reference only)")
    ws.cell(row=r["star_rock_reference"], column=2, value="=" + artifact_star_rock_reference_expr(
        eq["star_rock"], star["star_rock"],
    ))

    # Chalice (2 independent entries — 30s-duration and until-fight-end) — real, live; per-branch
    # Final Damage, only active in Breakthrough (see artifact_chalice_exprs, KNOWN_GAPS.md).
    chalice_normal_expr, chalice_boss_expr = artifact_chalice_exprs(
        eq["chalice"], IB("monster_type"), IB("content_type"), IB("fight_duration"), star["chalice"],
    )
    ws.cell(row=r["chalice_normal"], column=1, value="Chalice — Final Damage (normal-monster branch)")
    ws.cell(row=r["chalice_normal"], column=2, value="=" + chalice_normal_expr)
    ws.cell(row=r["chalice_boss"], column=1, value="Chalice — Final Damage (boss branch)")
    ws.cell(row=r["chalice_boss"], column=2, value="=" + chalice_boss_expr)

    # The Contract of Darkness — real, live Crit Rate, boss-branch only; composed into
    # extra_boss_mult_r via a crit-blend ratio correction at the call site (see build_calc_sheet).
    ws.cell(row=r["contract_of_darkness_crit_rate_bonus"], column=1, value="The Contract of Darkness — Crit Rate (boss branch only)")
    ws.cell(row=r["contract_of_darkness_crit_rate_bonus"], column=2, value="=" + artifact_contract_of_darkness_crit_rate_bonus_expr(
        eq["contract_of_darkness"], IB("monster_type"), star["contract_of_darkness"],
    ))

    # Shamaness Marble — baked into the EXISTING Inputs!buff_duration_increase_pct; REFERENCE only.
    ws.cell(row=r["shamaness_marble_reference"], column=1, value="Shamaness Marble — Buff Duration Increase % (reference only)")
    ws.cell(row=r["shamaness_marble_reference"], column=2, value="=" + artifact_shamaness_marble_reference_expr(
        eq["shamaness_marble"], star["shamaness_marble"],
    ))

    # Charm of the Undead — real, live Attack%, same shared bucket; periodic 5s-every-10s uptime.
    ws.cell(row=r["charm_of_the_undead"], column=1, value="Charm of the Undead — Attack % (periodic uptime)")
    ws.cell(row=r["charm_of_the_undead"], column=2, value="=" + artifact_charm_of_the_undead_expr(
        eq["charm_of_the_undead"], IB("monster_type"), IB("fight_duration"), star["charm_of_the_undead"],
    ))

    # Arwen's Glass Shoes — real, live: Companion Summoning Time Increase % (star-dependent; linear 20..40 steps, user-confirmed, see
    # ARTIFACT_STAR_VALUES).  Added to Inputs!companion_summon_time_increase_pct everywhere that value feeds the companion model
    # (companion_summon_time_inc_expr).
    ws.cell(row=r["arwens_glass_shoes_summon_time_increase_pct"], column=1, value=(
        "Arwen's Glass Shoes — Companion Summoning Time Increase % (added to the Inputs value; linear 20/24/28/32/36/40 by star, "
        "user-confirmed)"
    ))
    ws.cell(row=r["arwens_glass_shoes_summon_time_increase_pct"], column=2, value="=" + artifact_arwens_glass_shoes_expr(
        eq["arwens_glass_shoes"], star["arwens_glass_shoes"],
    ))

    # No-DPS-effect artifacts (ARTIFACT_NO_DPS_EFFECT) — constant 0 by design (the stat is not used by the model, or the content is not
    # modelled), not missing information.  Rows kept only so ArtifactsInput still tracks star level/equip state consistently.
    for zero_key, zero_label in [(f"{k}_reference", f"{ARTIFACT_LABELS[k]} — no DPS effect ({reason})")
                                 for k, reason in ARTIFACT_NO_DPS_EFFECT.items()]:
        ws.cell(row=r[zero_key], column=1, value=zero_label)
        ws.cell(row=r[zero_key], column=2, value=0)

    # Aggregate bucket totals — consumed directly by the main Calc/Summary pipeline and mirrored
    # in Sensitivity's build_stat_block. Book of Ancient/Athena's Gloves are excluded from EVERY
    # bucket here, both direct (AGG_CRIT_RATE/there is no AGG_ATTACK_SPEED bucket) and dependent
    # (AGG_CRIT_DAMAGE/AGG_MAX_DAMAGE) — the user confirmed both stats are already fully baked
    # into Inputs!crit_rate/crit_damage/attack_speed/max_damage when equipped, so this artifact
    # contributes nothing further to the REAL/baseline calculation (the boa_crit_damage/athena_
    # max_damage rows above exist purely as a reference value to help keep those manual Inputs
    # numbers in sync). Sensitivity DOES need to react to these artifacts though — sweeping Crit
    # Rate/Attack Speed must show the knock-on Crit Damage/Max Damage gain through an equipped
    # Book of Ancient/Athena's Gloves, and their own equip-toggle test must show the full combined
    # gain — build_stat_block implements this as an INCREMENT-based delta (reacting only to the
    # marginal crit rate/attack speed introduced by that block's override, never to the
    # already-baked-in baseline), kept entirely separate from this real/global sheet.
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
        "TOTAL — Artifact Damage Bonus (own separate final multiplier, like Magic Guard/"
        "Meditation's Average Buff Multiplier — not blended into Inputs!DAMAGE%)"
    )).font = LABEL_FONT
    ws.cell(row=r["AGG_DAMAGE"], column=2, value=f'=B{r["hexagon_damage"]}').font = LABEL_FONT
    ws.cell(row=r["AGG_ATTACK_PCT"], column=1, value=(
        "TOTAL — Artifact Attack % Bonus (Old Music Box/Secret Map/Reindeer's Spear/Alliance "
        "Badge/Bottle of Emotion/Charm of the Undead — additive into the same bucket as Magic "
        "Guard/Meditation's Average Buff Multiplier)"
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
PVP_FIGHT_DURATION = IB("pvp_fight_length")  # an Inputs cell (PvP content only; default 15 s), not a constant


def pvp_capped_window_expr(window_ref, monster_type_ref):
    """In PvP the fight lasts PVP_FIGHT_DURATION seconds, so a summon / damage-over-time window longer than the
    fight (Ifrit 30-40s, Arrow Platter 60s, ...) can only tick for the fight's length (2026-10-22 fix: PvP used
    to count the full window while only crediting one cast per fight, ~2x too many ticks for a 30s summon)."""
    return f'IF({monster_type_ref}="pvp",MIN({window_ref},{PVP_FIGHT_DURATION}),{window_ref})'


def effective_cooldown_expr(monster_type_ref, cooldown_ref, cdr_ref, costs_action_ref):
    return (
        f'IF({monster_type_ref}="pvp",{PVP_FIGHT_DURATION},'
        f'MAX(0.1,{cooldown_ref}-IF({costs_action_ref}=TRUE,{cdr_ref},0)))'
    )


def uptime_fraction_expr(monster_type_ref, duration_ref, cooldown_ref, bdi_ref):
    scaled_duration = f'({duration_ref}*(1+{bdi_ref}/100))'
    return (
        f'IF({monster_type_ref}="pvp",MIN({scaled_duration},{PVP_FIGHT_DURATION})/{PVP_FIGHT_DURATION},'
        f'MIN(1,{scaled_duration}/{cooldown_ref}))'
    )


# Records the most recent boss_normal_dps_split_exprs call's (prefix, targets, cap, monster_type) so
# the Calc/Sensitivity HitRate(perSec) column can rebuild a damage%-FREE hit count (Toxic Venom rolls
# once per target hit, so Boss/Normal Damage% of the triggering skill must not leak into its rate).
_LAST_SPLIT = [None]


def hit_count_s_expr(row, w_ref, lines_ref):
    """Calc!S for the row just built: ATTACKS per second x the target-count-only blend. Proc chances roll once per
    attack per enemy hit, never per damage line (user, 2026-11-04), so prefix/N (damage lines/s) is divided by the
    skill's HitsPerCast (lines per attack)."""
    if _LAST_SPLIT[0] is None:
        return 0
    prefix, tgt, cap, mt = _LAST_SPLIT[0]
    blend = f'IF({mt}="pvp",1,(1-{w_ref})+{w_ref}*MIN({tgt},{cap}))'
    return f'=IFERROR(({prefix})/N{row}/({lines_ref})*{blend},0)'


def boss_normal_dps_split_exprs(prefix_expr, monster_type_ref, boss_dmg_pct_expr,
                                 normal_dmg_pct_expr, normal_targets_ref, max_enemies_ref,
                                 extra_boss_mult_expr="1", extra_normal_mult_expr="1"):
    """Splits a row's DPS into independent boss-only and normal-only values, given `prefix_expr`
    (the H*N*rate*(extra multipliers) part shared by both — everything upstream of the monster-type
    split is already monster-type-independent). Each branch gets its own full
    (1+damage%/100)*target_count treatment; the two are blended into the real Total DPS as RATIOS
    (new/baseline) weighted by time spent, not as raw dollars weighted by branch size — dollar
    blending would let a stat's reported value be dominated by whichever branch happens to hit more
    targets, regardless of how much combat time is actually spent there. PvP is single-target with
    neither bonus, matching the old combined behavior. `extra_boss_mult_expr`/
    `extra_normal_mult_expr` (default "1", a no-op) are applied UNCONDITIONALLY, outside the
    `IF(pvp,1,...)` gating above — used for artifact bonuses that are genuinely branch-specific but
    unrelated to the boss_damage%/normal_damage% buckets themselves (Reindeer's Spear's boss/PvP-
    only Defense Penetration correction on the boss side; Secret Map's normal-monster-only Final
    Damage bonus on the normal side, which must stay 0 for PvP too)."""
    _LAST_SPLIT[0] = (prefix_expr, normal_targets_ref, max_enemies_ref, monster_type_ref)
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
    fixed-duration fight, before the first damage-skill cast — count of such buffs times 1/APS.
    Zero outside fixed-duration mode."""
    return (
        f'IF({fda_ref},'
        f'SUMPRODUCT((Skills!{buff_col}2:{buff_col}{last_row}>0)*'
        f'(Skills!{action_col}2:{action_col}{last_row}=TRUE)*'
        f'({unlocked_range}=TRUE))/{aps_ref},0)'
    )


def guarded_casts_expr(available_duration_ref, cooldown_ref):
    """exact_casts_expr, but 0 (not the naive formula's "always at least 1") once the available
    duration has been reduced to nothing or below."""
    return f'IF({available_duration_ref}<=0,0,{exact_casts_expr(available_duration_ref, cooldown_ref)})'


def exact_total_hits_expr(casts_ref, hits_ref, icd_ref, window_ref, cooldown_ref, duration_ref):
    last_cast_start = f'(({casts_ref}-1)*{cooldown_ref})'
    remaining_after_last = f'MAX(0,{duration_ref}-{last_cast_start})'
    # Whole ticks only: a summon / DoT cannot land a fractional hit (floor; the epsilon absorbs float error such as 6/0.3).
    full_window_ticks = f'IF({icd_ref}>0,INT({window_ref}/{icd_ref}+0.000000001),1)'
    last_cast_ticks = f'IF({icd_ref}>0,INT(MIN({window_ref},{remaining_after_last})/{icd_ref}+0.000000001),1)'
    return f'({hits_ref}*(({casts_ref}-1)*{full_window_ticks}+{last_cast_ticks}))'


def exact_buff_uptime_expr(casts_ref, buff_duration_ref, cooldown_ref, fight_duration_ref):
    last_cast_start = f'(({casts_ref}-1)*{cooldown_ref})'
    remaining_after_last = f'MAX(0,{fight_duration_ref}-{last_cast_start})'
    last_uptime = f'MIN({buff_duration_ref},{remaining_after_last})'
    # A recast that lands before the previous buff ends only extends coverage by one cooldown, so each full
    # cycle contributes MIN(duration, cooldown) of uptime — never more (otherwise uptime could exceed 100%).
    return f'(({casts_ref}-1)*MIN({buff_duration_ref},{cooldown_ref})+{last_uptime})'


def uptime_fraction_or_exact_expr(fixed_duration_active_ref, casts_ref, monster_type_ref,
                                   duration_ref, cooldown_ref, bdi_ref, fight_duration_ref):
    scaled_duration = f'({duration_ref}*(1+{bdi_ref}/100))'
    exact = f'({exact_buff_uptime_expr(casts_ref, scaled_duration, cooldown_ref, fight_duration_ref)}/{fight_duration_ref})'
    steady = uptime_fraction_expr(monster_type_ref, duration_ref, cooldown_ref, bdi_ref)
    return f'IF({fixed_duration_active_ref},{exact},{steady})'


def rate_or_exact_hits_expr(fixed_duration_active_ref, row_ref, hits_ref, icd_ref, window_ref,
                             cooldown_ref, available_duration_ref, fight_duration_ref, steady_rate_ref):
    """`available_duration_ref` is the duration actually used to derive `row_ref`'s cast count —
    must match, or the last cast's truncated tick window would be computed against a duration
    inconsistent with how many casts were actually counted."""
    exact_hits = exact_total_hits_expr(row_ref, hits_ref, icd_ref, window_ref, cooldown_ref, available_duration_ref)
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
    "MapleHeroBase(tenths%)", "MapleHeroFactorIndex", "Stacks", "SkillFoldBonus%", "Note",
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
    "MARK_OF_ASSASSIN": 43,
    "TRIPLE_THROW": 63,
    "ADRENALIN_FD": 66,
    "ADRENALIN_AS": 66,
    "DARK_FLARE": 69,
    "VENOM": 74,
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
    ("SHOWDOWN", "Showdown", 4, "", False, 1, f"=IF({IB('level')}>=136,6,5)", 0, 0, 100, 1,
     "", "", True,
     # AUDIT 2026-10-21: current table (102/106/116/120/128/132, boss 111/124, strike 136); option A
     # (user-confirmed) = every tier is its own add-on, 10+11+12+13+14+15 = 75%.
     level_gated_sum(IB("level"), {102: 10, 106: 11, 116: 12, 120: 13, 128: 14, 132: 15}),
     level_gated_sum(IB("level"), {111: 10, 124: 10}), 0, 0, 0, 0, 0, 0,
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
     "Patched: targets 6->8, stun 1.5s->2s (the 2 s stun is the player's own stun window: STATUS_PLAYER_STUN, Status Effect Damage applies and Chapter Breakthrough's boss phase is lengthened; 24 s cooldown, no Reuse mastery), Mastery Lv.39 re-typed from "
     "'+50% stun duration' to '+80% Damage' (now a real SkillMasteryBonus%). Damage curve "
     "itself (400%->600%, levels 1-100) unpatched — factorIndex 12, baseDamage 4000 tenths%. "
     "Maple Hero (NL) target: 130%->1014% (levels 1-200), factorIndex 23."),
    ("MARK_OF_ASSASSIN", "Assassin's Mark", 2,
     f"=IF({IB('level')}>=138,2,2.5)", False, 1, 1, 0, 0, 100, 1,
     1900, 21, True,
     level_gated_sum(IB("level"), {44: 80}), _MARK_OF_ASSASSIN_WEAKEN, _MARK_OF_ASSASSIN_WEAKEN, _MARK_OF_ASSASSIN_FD, 0, 0, 0, _MARK_OF_ASSASSIN_TARGET_INCREASE,
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
     level_gated_sum(IB("level"), {73: 100}), 0, 0, 0, 0, 0, 0, 0,
     1, "", 0, True, "", "", "",
     "Single-target. factorIndex 12, baseDamage 3600 tenths% (360%->720%, levels 1-200). "
     "SkillMasteryBonus% is Mastery Lv.71 ('Triple Throw - Damage', +100%, unaffected by "
     "the patch)."),
    ("ADRENALIN_FD", "Alchemic Adrenaline (Final Damage)", 3, "", False, 1, 1, 0, 0, 100, 1,
     150, 22, True,
     level_gated_sum(IB("level"), {90: 6}), 0, 0, 0, 0, 0, 0, 0,
     1, "FINAL_DAMAGE", f"=IF({IB('level')}>=90,15,10)", False, "", "", "",
     "AUDIT 2026-10-21: Mastery 'Persistence' is at Lv90 (not 88) and per the site (base AND patched) also gives Final Damage +6%p on top of +5s duration (wiki lists only the duration). "

     "Patched: trigger 7 hits->5 hits, Final Damage base 10%->15% (curve shape/ratio preserved "
     "from the unpatched 10%->16% wiki curve; factorIndex 22, baseDamage 150 tenths%). Uptime "
     "is bespoke — see build_summary_sheet's AdrenalinUptime (action-rate-driven cycle, not the "
     "generic BuffDuration/Cooldown ratio) — so this row has no Cooldown(s) of its own and isn't "
     "consumed via the generic buff_uptime() helper. Mastery Lv.88 adds +5s to BuffDuration(s)."),
    ("ADRENALIN_AS", "Alchemic Adrenaline (Attack Speed)", 3, "", False, 1, 1, 0, 0, 100, 1,
     80, 22, True,
     0, 0, 0, 0, 0, 0, 0, 0,
     1, "ATTACK_SPEED", f"=IF({IB('level')}>=90,15,10)", False, "", "", "",
     "Same trigger/uptime as Adrenalin (Final Damage) above (8%->12.8%, levels 1-200), split "
     "into its own row since BuffTargetStat only holds one target per row (mirrors Dark Sight's "
     "own Crit Rate / Attack split below)."),
    ("DARK_FLARE", "Dark Flare", 3,
     f"=IF({IB('level')}>=94,45*0.7,45)", True, 1, f"=IF({IB('level')}>=78,3,2)",
     f"=IF({IB('level')}>=104,2*0.75,2)", 20, 100, 1,
     3300, 12, True,
     0, 0, 0, 0, 0, 0,
     f"=IF({IB('level')}>=94,30,0)", 0,
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
     level_gated_sum(IB("level"), {130: 100}), 0, 0, 0, 0, 0, 0, 0,
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
     600, 21, True,
     level_gated_sum(IB("level"), {68: 100}), 0, 0, 0, 0, 0, 0, 0,
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
     f"=IF({IB('level')}>=108,10*0.7,10)", True, 1, 4, 0, 0, 100, 1,
     11500, 12, True,
     level_gated_sum(IB("level"), {134: 50}), 0, 0, 0, 0, 0,
     f"=IF({IB('level')}>=108,30,0)", 0,
     1, "", 0, True, "", "", "",
     "Single-target. factorIndex 12, baseDamage 11500 tenths% (1150%->2300%, levels 1-200). "
     "Mastery Lv.106 (-30% cooldown, baked into the Cooldown(s) formula above, MasteryCooldownPct "
     "reference-only) and Lv.132 (+50% damage, real SkillMasteryBonus%)."),
    ("SUDDEN_RAID_BURST", "Sudden Raid (burst)", 4, 19, True, 1, 3, 0, 0, 100, 1,
     14000, 12, True,
     level_gated_sum(IB("level"), {126: 50}), 0, 0, 0, 0, 0, 0, 0,
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
     "as a known gap). With the Status/KO engine on the engine picks the cast times (STATUS_BUFFS: a Final Damage buff, its own multiplicative factor); the "
     "enemy-debuff row below follows the engine's cast count."),
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
    ("SHADOW_SHIFTER_SELF_ATK", "Shadow Shifter (self Final Damage%)", 4, "", False, 1, 1, 0, 0, 100, 1,
     100, 22, True,
     level_gated_sum(IB("level"), {118: 10}), 0, 0, 0, 0, 0, 0, 0,
     1, "FINAL_DAMAGE", 0, False, "", "", "",
     "AUDIT 2026-10-21: per the site (user decision) Shadow Shifter's passive is +10% FINAL DAMAGE (the wiki said Attack); Mastery Lv118 adds +10%p. Still a baked-in-Inputs delta row (now feeding the Final Damage Sensitivity slot). "

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
     "(hide + re-press) as separate action-slot costs within the same 25s cycle. With the Status/KO engine on (World Boss / Enhancement Dungeon / any "
     "fixed-length single-target content once a stun exists) the engine picks the cast times instead of the duty-cycle average (STATUS_BUFFS: an Attack% buff in "
     "the additive bucket with the artifacts); the Crit Rate row above follows the engine's cast count of this row."),
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


# Skill Cooldown Decrease applies to EVERY real cooldown — actively cast skills, buffs and passives alike
# (user decision 2026-10-21; it used to apply only to CostsActionSlot rows). The exempt rows are NOT real
# cooldowns: their Cooldown(s) cell is a trigger-rate / internal-interval surrogate (e.g. 1 / attack speed),
# which CDR must not shrink to the 0.1s floor.
CDR_EXEMPT_ROW_KEYS = ['MARK_OF_ASSASSIN', 'VENOM']


def cdr_applies_expr(key):
    return "FALSE" if key in CDR_EXEMPT_ROW_KEYS else "TRUE"


# ---------------------------------------------------------------------------------------------------------------
# Skill masteries MULTIPLY the skill's damage (game-confirmed 2026-11-03, FP-Mage: a "+70%" mastery on a 451%-base
# skill gives 648% = base x 1.7, not 521%; Poison Breath / Ifrit / Ignite / Poison Mist hit damage matched to <0.1%).
# Calc!F for a damage row is therefore  base_curve x (1 + SkillMasteryBonus%/100) + SkillFoldBonus%, where
# SkillFoldBonus% is damage that is ADDED as coefficient points rather than multiplied (a Final Attack proc folded into
# a basic attack, a documented Final Damage approximation, ...). Rows that are buffs (BuffTargetStat set: their mastery is
# "+X percentage points") and MASTERY_ADDITIVE_EXTRA rows keep the old additive behaviour.
# ---------------------------------------------------------------------------------------------------------------
MASTERY_ADDITIVE_EXTRA = set([])
MASTERY_MIXED_ROW_KEYS = []
SKILL_FOLD_BONUS = {}


def _split_mixed_mastery_rows():
    """Splits a mixed SkillMasteryBonus% cell ("<fold-in terms> + SUMPRODUCT(level gates) * {mastery tiers}") into the
    multiplicative mastery part (stays in SkillMasteryBonus%) and the additive fold part (SKILL_FOLD_BONUS)."""
    global SKILL_ROWS
    i_sm = SKILL_COLUMNS.index("SkillMasteryBonus%")
    pattern = re.compile(r"SUMPRODUCT\(\(Inputs!\$B\$3>=\{[^}]*\}\)\*\{[^}]*\}\)")
    out = []
    for row in SKILL_ROWS:
        if row[0] in MASTERY_MIXED_ROW_KEYS:
            cell = row[i_sm]
            m = pattern.search(cell)
            assert m, (row[0], cell)
            mastery = "=" + m.group(0)
            rest = (cell[:m.start()] + cell[m.end():]).lstrip("=")
            rest = re.sub(r"^\+|\+$", "", rest.strip())
            rest = rest.replace("++", "+")
            assert rest and "SUMPRODUCT((Inputs!$B$3>={102" not in rest, (row[0], rest)
            SKILL_FOLD_BONUS[row[0]] = "=" + rest
            row = tuple(mastery if idx == i_sm else v for idx, v in enumerate(row))
        out.append(row)
    SKILL_ROWS = out


_split_mixed_mastery_rows()
MASTERY_ADDITIVE_ROW_KEYS = (
    {row[0] for row in SKILL_ROWS if row[SKILL_COLUMNS.index("BuffTargetStat")] not in ("", None)} | MASTERY_ADDITIVE_EXTRA
)


def apply_mastery_semantics(key, skills_row, formula):
    """Rewrites a Calc/Sensitivity coefficient formula "=<base curve>+<mastery ref>" into
    "=(<base curve>)*(1+<mastery ref>/100)+<fold ref>" for damage rows; buff rows / unusual shapes are left untouched."""
    sm = S("SkillMasteryBonus%", skills_row)
    tail = "+" + sm
    if key in MASTERY_ADDITIVE_ROW_KEYS or not (isinstance(formula, str) and formula.startswith("=") and formula.endswith(tail)):
        return formula
    return f"=({formula[1:-len(tail)]})*(1+{sm}/100)+{S('SkillFoldBonus%', skills_row)}"



def build_skills_sheet(wb):
    ws = wb.create_sheet("Skills")
    for i, name in enumerate(SKILL_COLUMNS):
        ws.cell(row=1, column=i + 1, value=name)
    style_header_row(ws, 1, len(SKILL_COLUMNS))

    for row_data in SKILL_ROWS:
        key = row_data[0]
        r = ROW[key]
        # SkillFoldBonus% sits just before Note (the last tuple element); 0 unless the row folds additive coefficient points in
        full_row = tuple(row_data[:-1]) + (SKILL_FOLD_BONUS.get(key, 0), row_data[-1])
        for i, val in enumerate(full_row):
            ws.cell(row=r, column=i + 1, value=val)

    widths = [26, 30, 8, 11, 15, 13, 11, 8, 13, 11, 12, 18, 11, 14, 17, 16, 18, 17, 16, 16,
              17, 20, 18, 15, 14, 16, 20, 20, 8, 60]
    widths = widths[:-1] + [14] + widths[-1:]   # SkillFoldBonus% column
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
R_AVGBUFF = 13                 # Average Buff Multiplier (Dark Sight Attack + Frailty Curse self-FD + Adrenalin FD)
R_CRIT_RATE_BONUS = 14          # Critical Throw Lv.47 mastery + Dark Sight (Crit Rate), additive to Inputs!crit_rate
R_MONSTER_DMG_BONUS = 15        # Venom Lv.82 Weaken + Frailty Curse (enemy debuff), additive to Monster Damage%
R_SHADOW_PARTNER_MULT = 16      # Shadow Partner average multiplier
R_APS_PRE_ADRENALIN = 17        # Actions/sec using only Nimble Feet's AS bonus (breaks the Adrenalin<->ActionsPerSecond cycle)
R_ADRENALIN_UPTIME = 18         # Alchemic Adrenaline uptime (action-rate-driven cycle)
R_AS_BONUS = 19                 # Combined Attack Speed buff bonus % (Nimble Feet + Adrenalin AS, averaged)
R_APS = 20                      # Final Actions Per Second
R_CASTRATE = 21                 # Skill + buff cast rate (subtracted from Basic Attacks Per Second)
R_BAPS = 22                     # Basic Attacks (Showdown) Per Second
R_SELFATK_UPTIME = 23           # Shadow Shifter self-Attack buff uptime (informational; see Note)
R_CRIT_DAMAGE_BONUS = 24        # Frailty Curse Mastery Lv.111 (+30% Critical Damage Taken), duty-cycle-averaged, additive to Inputs!crit_damage
R_SHOWDOWN_DPS = 25
R_STARTUP_TIME = 26             # Buff-Casting Startup Delay (s, fixed-duration only)
R_BOSS_ONLY_TOTAL = 27          # Total DPS if every hit were against a boss (Breakthrough Sensitivity baseline)
R_NORMAL_ONLY_TOTAL = 28        # Total DPS if every hit were against normal monsters (Breakthrough Sensitivity baseline)
# The two variable-length summary tables (Per-Skill Breakdown, sized off DAMAGE_DEALING_KEYS, and
# Marginal DPS & Stat Value, sized off STAT_SWEEP) start after this fixed block, with a 2-row gap.
BREAKDOWN_SECTION_ROW = R_NORMAL_ONLY_TOTAL + 2

# Frailty Curse's self-buff and enemy-debuff rows share the same literal Cooldown(s)/BuffDuration(s)
# (both 45/20, mastery-unaffected in this pass) — buff_uptime() below is generic per-row.


def buff_uptime_expr(fda_ref, monster_type_ref, row, bdi_ref, fight_duration_ref, calc_r_col_ref):
    """Steady-state or exact-duration uptime fraction for a real buff row (BUFF_ROW_KEYS)."""
    return uptime_fraction_or_exact_expr(
        fda_ref, calc_r_col_ref, monster_type_ref, S("BuffDuration(s)", row),
        f'(1/{re.sub(r"R(?=[0-9]+$)", "Q", calc_r_col_ref)})',
        bdi_ref, fight_duration_ref,
    )


# ---------------------------------------------------------------------------
# Status Effect Damage / KO timeline engine wiring (src/status_timeline.py).  Spec = which rows are buffs / cooldown casts and which
# damage rows hang off each cast; the engine decides WHEN to cast (see that module's docstring) and hands back timing factors.
# ---------------------------------------------------------------------------
TIMELINE_SHEET = "Timeline"
# Night Lord's player-cast buffs the engine times: Dark Sight (Attack %, 'atk' kind: part of the additive Attack% bucket) and Frailty Curse's self Final Damage ('ramp'
# kind with a flat profile: its own multiplicative factor, exactly as Summary's R_AVGBUFF multiplies it).  Dark Sight's Crit Rate half is a passenger of the same cast
# (its row keeps the averaged uptime formula, fed with the engine's cast count of Dark Sight (Attack)), as does the Frailty Curse enemy debuff (monster damage taken, crit
# damage taken: additive buckets the engine does not time).
# NOT player-timed, they stay at their averages (also in the companion's snapshot where they are not a cast): Alchemic Adrenaline (action-rate-driven proc: Final Damage
# and Attack Speed), Nimble Feet (Attack Speed), Shadow Partner (average multiplier), the Frailty Curse enemy debuff / Venom Weaken (R_MONSTER_DMG_BONUS), Dark Sight's
# Crit Rate (R_CRIT_RATE_BONUS) and the artifact damage-taken bonuses.
STATUS_BUFFS = [("DS", "DARK_SIGHT_ATK", "atk"), ("FC", "FRAILTY_CURSE_SELF_FD", "ramp")]
# (group id, row key whose Calc!C/Q give availability/cooldown, [(row key, type, window row key or None, unlock-gate row key or None, weight row key)])
STATUS_GROUPS = [
    ("GUST", "GUST_CHARM", [("GUST_CHARM", "burst", None, None, "GUST_CHARM")]),
    ("TRIPLE", "TRIPLE_THROW", [("TRIPLE_THROW", "burst", None, None, "TRIPLE_THROW")]),
    # Dark Flare: a 20 s window of 2 s ticks (3 hits each from Lv78; ICD 1.5 s from Lv104)
    ("FLARE", "DARK_FLARE", [("DARK_FLARE", "dot", "DARK_FLARE", None, "DARK_FLARE")]),
    ("QUAD", "QUAD_STAR", [("QUAD_STAR", "burst", None, None, "QUAD_STAR")]),
    # Sudden Raid: the burst + a 5 s DoT of 1 s ticks that shares the burst's cooldown (the DoT row costs no action slot of its own)
    ("RAID", "SUDDEN_RAID_BURST", [
        ("SUDDEN_RAID_BURST", "burst", None, None, "SUDDEN_RAID_BURST"),
        ("SUDDEN_RAID_DOT", "dot", "SUDDEN_RAID_DOT", None, "SUDDEN_RAID_DOT")]),
]
# Spread uniformly over the fight: Showdown (the basic attack), Assassin's Mark and Venom (periodic ticks on a surrogate interval), Toxic Venom (a chance proc triggered by
# every attack - its trigger rate already follows the engine's cast counts) and Shadow Shifter's counterattack (driven by the damage you take).
STATUS_UNIFORM_ROWS = ["SHOWDOWN", "MARK_OF_ASSASSIN", "VENOM", "TOXIC_VENOM", "SHADOW_SHIFTER"]
# The player's own stunning skill (game table): Gust Charm stuns 8 targets for 2 s (cooldown 24 s, no Reuse mastery; unlock Lv35).  Cast on cooldown from the start: its
# stun windows are part of the timeline (Status Effect Damage) and, in Chapter Breakthrough, lengthen the boss phase.
STATUS_PLAYER_STUN = [dict(id="GUST", row="GUST_CHARM", typ="cast", dur=2.0, p=1.0)]


STATUS_CAST_PREFIX = {key: f"buff.{bid}" for bid, key, _k in STATUS_BUFFS}
# passenger rows: same cast as their buff (their uptime formulas read Calc!R; the buff cells do not depend on any damage weight, so no cycle)
STATUS_CAST_PREFIX["DARK_SIGHT_CRIT"] = "buff.DS"
STATUS_CAST_PREFIX["FRAILTY_CURSE_DEBUFF"] = "buff.FC"
for _gid, _cast, _ents in STATUS_GROUPS:
    for _e in _ents:
        STATUS_CAST_PREFIX.setdefault(_e[0], f"grp.{_gid}")
    STATUS_CAST_PREFIX[_cast] = f"grp.{_gid}"
# rows whose hits/s come from the engine's effective cast count (last DoT window / eruption truncated by the fight end)
STATUS_FS_KEYS = [e[0] for _g, _c, ents in STATUS_GROUPS for e in ents if e[1] in ("dot", "end")]
STATUS_PHI_ROWS = sorted({e[0] for _g, _c, ents in STATUS_GROUPS for e in ents})
STATUS_PERCAST_KEYS = sorted({e[4] for _g, _c, ents in STATUS_GROUPS for e in ents})
# stat sweeps whose block must re-run the engine (they move cast times / buff windows / the Status Effect Damage input / Hexagon stacks)
STATUS_REBUILD_KEYS = ["skill_cooldown_decrease", "buff_duration_increase_pct", "shamaness_marble_equipped", "status_effect_damage",
                       "companion_summon_time_increase_pct", "hexagon_necklace_equipped", "arwens_glass_shoes_equipped",
                       # everything that moves the engine's buff bucket must re-run the strip too - with the engine on, Summary's Attack% bucket IS the strip's mean buff
                       # bucket (A0 incl. Charm / the Attack% artifacts, Dark Sight's and Frailty Curse's F incl. the 1st/3rd/4th-job skill-level inputs)
                       "charm_of_the_undead_equipped", "old_music_box_equipped", "secret_map_equipped", "reindeer_spear_equipped",
                       "alliance_badge_equipped", "bottle_of_emotion_equipped", "skill_lvl_1st", "skill_lvl_3rd", "skill_lvl_4th", "skill_lvl_all",
                       # Sensitivity fix 1 (2026-11-21): every other stat whose swept value changes something the strip CONSUMES must re-run its own strip.
                       # The strip reads (a) Dark Sight's / Frailty Curse's F, duration and cooldown and the cast groups' cooldowns (Gust Charm's stun window too),
                       # (b) the per-cast damage weights (Calc column Y) and the basic-attack weight c_slot (Showdown).  Weights only matter through their RELATIVE sizes
                       # (a cast is worth w*Wt - c_slot*Wt), so a stat that scales every damage row alike leaves the strip's timing factors untouched and reuse is EXACT.
                       # Engine experiment (reuse of the main strip vs a full re-solve; World Boss / Enhancement Dungeon, Lv110 / 140, stat sets A / C, with and without a
                       # companion, doses +1 / +30 / +300): exact to 1e-15 for LUK / DEX, Defense, Damage %, Damage Amp, Final Damage, Min / Max Damage, Crit Damage, Def Pen,
                       # Flat ATTACK, ATTACK %, Attack Speed, Normal Damage (the strip is boss-branch only), the Basic Attack Target Increase, Incoming Hit Rate AND the 2nd-job
                       # skill level (Gust Charm is a FIXED on-cooldown stun cast: its weight never enters a decision; Assassin's Mark is a uniformly spread row).  NOT exact
                       # (a discrete cast decision flips): the stats of the first block above, and
                       # - Skill Damage % / Basic Attack Damage %: skill rows vs Showdown, the basic attack a cast replaces (c_slot) (Skill Damage is off by 0.6 % at +1 in the
                       #   Enhancement Dungeon, Basic Attack Damage by 0.5 % at +30);
                       # - Boss Damage %: Showdown has its own Boss Mastery chain, so the boss bucket is not uniform across rows (exact at +30, off by 1 % at +300; Candle /
                       #   Sayram's Necklace / Star Rock add to it; Peach Tree / Silver Pendant add to the Monster Damage-Taken bucket that sums with it);
                       # - Crit Rate %: Ring of Cycles' Skill / Basic Attack Damage bonus follows the crit rate (Book of Ancient / Rainbow Snail Shell move it too; The Contract
                       #   of Darkness' boss-only Crit Rate does NOT enter Ring of Cycles' threshold here and scales every row alike: reuse is exact).
                       # (Soul Contract's cooldown cut only exists in Chapter Hunt, whose normal-monster weight is never 0, so the strip is never on there: reuse exact.)
                       "skill_damage", "basic_attack_damage", "boss_damage", "crit_rate",
                       "ring_of_cycles_equipped", "book_of_ancient_equipped", "rainbow_snail_shell_equipped",
                       "candle_equipped", "sayrams_necklace_equipped", "star_rock_equipped", "peach_tree_equipped", "silver_pendant_equipped"]
# Blocks that run the full 3-candidate companion summon-time search themselves (everything else reuses the main sheet's choice): guide "Gap found by the Buccaneer port", items 1-4
COMPANION_FULL_SEARCH_KEYS = ("companion_summon_time_increase_pct", "hexagon_necklace_equipped", "horn_flute_equipped", "skill_cooldown_decrease",
                              "arwens_glass_shoes_equipped")
# sweeps that change the companion's summon DURATION itself (its own s_0 / W_0 in the stun strip instead of the main sheet's)
SUMMON_TIME_KEYS = ("companion_summon_time_increase_pct", "arwens_glass_shoes_equipped")
STATUS_KO_FIRST_BIN_NOTE = "World Boss: KO 24-34 s and 59-69 s; Enhancement Dungeon: KO for the last 4.5 s (user, 2026-11-14)"


def status_ko_exprs(ct, T):
    wb_, en = f'{ct}="World Boss"', f'{ct}="Enhancement Dungeon"'
    return [
        (f'IF({wb_},24,IF({en},{T}-4.5,0))', f'IF({wb_},34,IF({en},{T},0))'),
        (f'IF({wb_},59,0)', f'IF({wb_},69,0)'),
    ]


def status_engine_host(ib, cell, win, bdi, a0, charm_v, hex_v, hex_avg, c_slot, hasstun="0", stun=None):
    """Excel host expressions for the engine.  `cell(letter, key)` = that Calc(-twin) cell; `win(key)` = the row's ActiveWindow expression.
    Per-cast damage weights are read from column Y of the Calc(-twin) rows (PerCastBossDamage)."""
    ct, T = ib("content_type"), ib("fight_duration")
    fda = fixed_duration_active_expr(ib("monster_type"), T)
    on = f'IF(AND({fda},{ib("normal_weight_frac")}=0,OR({ct}="World Boss",{ct}="Enhancement Dungeon",{hasstun}=1)),1,0)'
    buffs = []
    for bid, key, kind in STATUS_BUFFS:
        dur = f'({S("BuffDuration(s)", ROW[key])}*(1+{bdi}/100))'
        cd = f'IFERROR(1/{cell("Q", key)},1000000)'
        b = dict(id=bid, kind=kind, F=cell("F", key), dur=dur, cd=cd, on=cell("C", key))
        if kind == "ramp":
            b.update(dur=f'MIN({dur},{cd})', p0=1, p1=1, ramp_t=1, dur0=1)
        buffs.append(b)
    groups = []
    for gid, cast, ents in STATUS_GROUPS:
        entries = []
        for row_key, typ, win_key, gate_key, w_key in ents:
            w = cell("Y", w_key)
            if gate_key:
                w = f'IF({cell("C", gate_key)}=TRUE,{w},0)'
            entries.append(dict(row=row_key, typ=typ, w=w, L=(win(win_key) if win_key else 1),
                                on=(f'{cell("C", gate_key)}=TRUE' if gate_key else "TRUE")))
        groups.append(dict(id=gid, cd=f'IFERROR(1/{cell("Q", cast)},1000000)', on=cell("C", cast), slot=True, entries=entries,
                           fixed=cast in {e["row"] for e in STATUS_PLAYER_STUN}, t0="0"))
    return dict(pl_stun=stl.player_stun_entries(STATUS_PLAYER_STUN, cell, "0"), on=on, T=T, S=ib("status_effect_damage"), ko=status_ko_exprs(ct, T), hex_v=hex_v, hex_period=20, hex_max=3,
                A0=a0, charm_v=charm_v, hex_avg=hex_avg, c_slot=c_slot, stun=stun, buffs=buffs, groups=groups)


_STATUS_DUMMY_HOST = status_engine_host(
    lambda k: "0", lambda letter, key: "0", lambda key: "1", "0", "0", "0", "0", "0", "0",
)
STATUS_STRIP_ROW0 = 3
STATUS_STRIP_HEIGHT = stl.Layout(stl.cells(_STATUS_DUMMY_HOST), 0, 1).height
STATUS_MAIN_LAYOUT = stl.Layout(stl.cells(_STATUS_DUMMY_HOST), STATUS_STRIP_ROW0, 1, sheet=TIMELINE_SHEET)


def phase_state_ratios(ct, T, hex_v, hex_avg, bucket_avg, charm_v, charm_avg):
    """(boss-phase factor, normal-phase factor) for contents whose normal-monster phase comes first (Chapter Breakthrough: boss at 20 s; Hero Dungeon: 30 s).
    The averaged model uses fight-average Hexagon Necklace stacks and Charm of the Undead duty; each phase has its own: Hexagon adds a stack every 20 s,
    Charm is up 5 s of every 10 s from second 10.  factor = (state of that phase)/(fight average), applied to every damage row of that branch.
    Both are 1 in contents without phases."""
    tb0 = f'IF({ct}="Breakthrough",20,IF({ct}="Hero Dungeon",30,0))'

    def stacks(a, b):
        return f'((MAX(0,{b}-MAX({a},20))+MAX(0,{b}-MAX({a},40))+MAX(0,{b}-MAX({a},60)))/({b}-{a}))'

    def charm_on(t):   # seconds of Charm up in [0, t]
        x = f'MAX(0,{t}-10)'
        return f'(5*INT({x}/10)+MIN(5,{x}-10*INT({x}/10)))'

    def ratio(a, b):
        hex_ratio = f'((1+{hex_v}*{stacks(a, b)}/100)/(1+{hex_avg}/100))'
        duty = f'(({charm_on(b)}-{charm_on(a)})/({b}-{a}))'
        atk_ratio = f'((1+({bucket_avg}-{charm_avg}+{charm_v}*{duty})/100)/(1+{bucket_avg}/100))'
        return f'{hex_ratio}*{atk_ratio}'
    boss = f'IF({tb0}>0,{ratio(tb0, T)},1)'
    norm = f'IF({tb0}>0,{ratio("0", tb0)},1)'
    return boss, norm


def apply_status_columns(ws, row_of, strip, phi_gate, uni_b="1", uni_n="1"):
    """Post-pass over the finished Calc (or block) rows: add the timing-factor columns and fold them in.
    W (23) = timing factor boss branch, X (24) = normal branch, Y (25) = per-cast boss damage (written by the caller), R (18) = engine cast counts,
    Z (26) = the averaged model's own cast count (what R was before the engine override; kept for reference / the engine-off fallback),
    BossOnlyDPS (T, 20) / NormalOnlyDPS (V, 22) x the factors.
    `strip` = layout the strip cells are read from, `phi_gate` = its engine-on cell reference."""
    ws.cell(row=min(row_of.values()) - 1, column=23, value="TimingFactorBoss")
    ws.cell(row=min(row_of.values()) - 1, column=24, value="TimingFactorNormal")
    ws.cell(row=min(row_of.values()) - 1, column=25, value="PerCastBossDamage")
    ws.cell(row=min(row_of.values()) - 1, column=26, value="CastsInFight(averaged model)")
    for key, row in row_of.items():
        if key in STATUS_PHI_ROWS:
            phi = strip.s(f"phi.{key}")
        elif key in STATUS_UNIFORM_ROWS:
            phi = strip.s("phi_unif")
        else:
            phi = "1"
        if key in DAMAGE_DEALING_KEYS:
            ws.cell(row=row, column=23, value=f'=IF({phi_gate}=1,{phi},{uni_b})')
            ws.cell(row=row, column=24, value=f'={uni_n}')
        else:
            ws.cell(row=row, column=23, value=1)
            ws.cell(row=row, column=24, value=1)
        for col, fcol in ((20, "W"), (22, "X")):
            old = ws.cell(row=row, column=col).value
            if isinstance(old, str) and old.startswith("="):
                ws.cell(row=row, column=col, value=f"=({old[1:]})*{fcol}{row}")
        old_r = ws.cell(row=row, column=18).value
        ws.cell(row=row, column=26, value=old_r)
        if key in STATUS_CAST_PREFIX and ROW_HAS_COOLDOWN[key]:
            ws.cell(row=row, column=18, value=f'=IF({phi_gate}=1,{strip.s(STATUS_CAST_PREFIX[key] + ".n")},Z{row})')


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
    crit_rate_total_ref = f'({IB("crit_rate")}+Summary!$B${R_CRIT_RATE_BONUS}+{art_ref("AGG_CRIT_RATE")})'
    crit_damage_total_ref = f'({IB("crit_damage")}+Summary!$B${R_CRIT_DAMAGE_BONUS}+{art_ref("AGG_CRIT_DAMAGE")})'
    avg_buff_mult_ref = f"Summary!$B${R_AVGBUFF}"
    shadow_partner_mult_ref = f"Summary!$B${R_SHADOW_PARTNER_MULT}"

    # Rows needing the full D-N hit-damage pipeline (Showdown + every real damage row + the two
    # bespoke-rate rows that still hit like a normal attack) — everything except the hybrid row
    # (Shadow Partner, D-I only), Night Lord's Mark (D-F only), and the delta-only passive-mult/
    # buff rows (D-F + G/H/I only, no J-N/O).
    FULL_HIT_PIPELINE_KEYS = ["SHOWDOWN"] + DAMAGE_ROW_KEYS + TOXIC_VENOM_ROW_KEYS + SHADOW_SHIFTER_ROW_KEYS

    for key, r in ROW.items():
        _LAST_SPLIT[0] = None
        ws.cell(row=r, column=1, value=f"={S('Key', r)}")
        ws.cell(row=r, column=2, value=f"={S('Name', r)}")
        ws.cell(row=r, column=3, value=unlock_expr(key))

        has_cooldown = ROW_HAS_COOLDOWN[key]
        if has_cooldown:
            # Soul Contract's % Skill Cooldown Decrease (Chapter Hunt only) is applied as an extra
            # multiplicative wrapper here rather than inside effective_cooldown_expr itself, since
            # it's a simple postfix scale and keeps that well-tested function untouched.
            eff_cd_r = (
                f'({effective_cooldown_expr(IB("monster_type"), S("Cooldown(s)", r), IB("skill_cooldown_decrease"), cdr_applies_expr(key))}'
                f'*(1-{artifact_soul_contract_pct_expr(IB("soul_contract_equipped"), IB("content_type"), IB("soul_contract_star"))}/100))'
            )
            if key in BUFF_ROW_KEYS:
                available_duration_r = IB("fight_duration")
            else:
                available_duration_r = f'MAX(0,{IB("fight_duration")}-Summary!$B${R_STARTUP_TIME})'
            rate_r = rate_or_exact_hits_expr(
                fixed_duration_active_main, f"R{r}", S("HitsPerCast", r), S("ICD(s)", r),
                S("ActiveWindow(s)", r), eff_cd_r, available_duration_r, IB("fight_duration"), f"G{r}*Q{r}",
            )
            # Status/KO timeline engine on: hits per second of a DoT row = its per-cast hits x the engine's effective cast count
            # (the last window truncated by the fight end, at the engine's own cast times) / fight length.
            if key in STATUS_FS_KEYS:
                rate_r = (f'IF({STATUS_MAIN_LAYOUT.s("on")}=1,G{r}*{STATUS_MAIN_LAYOUT.s("fs." + key)}/{IB("fight_duration")},{rate_r})')
        else:
            eff_cd_r = None
            rate_r = None
            available_duration_r = None

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
            f'={S("HitsPerCast", r)}*IF({S("ICD(s)", r)}>0,INT({pvp_capped_window_expr(S("ActiveWindow(s)", r), IB("monster_type"))}/{S("ICD(s)", r)}+0.000000001),1)'
        ))
        ws.cell(row=r, column=8, value=f'=1-(1-{S("ProcChance%", r)}/100)^{S("RollsPerCast", r)}')
        ws.cell(row=r, column=9, value=(
            f'=IF({S("MapleHeroBase(tenths%)", r)}<>"",'
            f'1+({S("MapleHeroBase(tenths%)", r)}/10)*($U$3/1000)/100,1)'
        ))

        if key in FULL_HIT_PIPELINE_KEYS:
            ws.cell(row=r, column=10, value=f'={IB("attack")}*(F{r}/100)')
            ws.cell(row=r, column=11, value=(
                f'=J{r}*(1+{IB("stat_damage")}/100)*(1+{IB("damage")}/100)'
                f'*(1+{IB("damage_amp")}/100)'
                f'*(5000/(6000+{IB("monster_defense")}*(1-{IB("def_pen")}/100)))'
                f'*(1+{IB("final_damage")}/100)*(1+{S("MasteryFinalDamage%", r)}/100)*(1+{art_ref("AGG_FINAL_DAMAGE")}/100)'
                f'*(1+(IF({S("Key", r)}="SHOWDOWN",{IB("basic_attack_damage")}+{art_ref("AGG_BASIC_ATTACK_DAMAGE")},'
                f'{IB("skill_damage")}+{art_ref("AGG_SKILL_DAMAGE")}))/100)'
                f'*({avg_buff_mult_ref}*{shadow_partner_mult_ref}*(1+{art_ref("AGG_DAMAGE")}/100)*I{r})'
            ))
            ws.cell(row=r, column=12, value=f'=K{r}*(MIN({IB("min_damage")},{IB("max_damage")})/100+{IB("max_damage")}/100)/2')
            ws.cell(row=r, column=13, value=f'=L{r}*(1+{crit_damage_total_ref}/100)')
            ws.cell(row=r, column=14, value=(
                f'=L{r}*(1-MIN({crit_rate_total_ref},100)/100)+M{r}*(MIN({crit_rate_total_ref},100)/100)'
            ))
        elif key in HYBRID_ROW_KEYS:
            for col in (10, 11, 12, 13, 14):
                ws.cell(row=r, column=col, value="")
        else:
            for col in (10, 11, 12, 13, 14):
                ws.cell(row=r, column=col, value="")

        # AGG_ENEMY_DMG_TAKEN (Peach Tree Herb Pouch/Silver Pendant) is an unconditional, both-
        # branches-equally additive % — Night Lord's own R_MONSTER_DMG_BONUS row is already a real,
        # actively-used bucket (Venom Lv.82 Weaken + Frailty Curse), so it isn't reused here the way
        # an unused placeholder would be; added as its own extra term instead.
        boss_dmg_pct_r = (
            f'{IB("boss_damage")}+{S("MasteryBossDamage%", r)}+{monster_dmg_bonus_ref}'
            f'+{art_ref("AGG_BOSS_DAMAGE")}+{art_ref("AGG_ENEMY_DMG_TAKEN")}'
        )
        normal_dmg_pct_r = (
            f'{IB("normal_damage")}+{S("MasteryNormalDamage%", r)}+{monster_dmg_bonus_ref}'
            f'+{art_ref("AGG_NORMAL_DAMAGE")}+{art_ref("AGG_ENEMY_DMG_TAKEN")}'
        )

        # Reindeer's Spear — only its BASE (1x) Defense Penetration is baked into Inputs!def_pen;
        # the extra multiple beyond that (1 more for PvP's 2x total, 2 more for boss's 3x total) is
        # a real, live, boss/PvP-branch-only correction ratio between the nonlinear defense factor
        # computed with vs. without that extra amount (see artifact_reindeer_spear_extra_mult_expr).
        # Defense Penetration combines like Attack Speed — diminishing-returns
        # (new = 1-(1-old)*(1-inc)), never additive.
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
        # The Contract of Darkness — boss-branch-only Crit Rate, composed the same "ratio between
        # two evaluations of a nonlinear formula" way, but against the crit-blend formula
        # (N = L*(1-cr/100)+M*(cr/100)) instead of the defense factor, reusing this row's own
        # already-computed L{r}/M{r} cells (blank for HYBRID_ROW_KEYS/other non-FULL_HIT_PIPELINE
        # rows — the ratio then divides 0/0, but those rows never call boss_normal_dps_split_exprs
        # with this correction anyway since DAMAGE_ROW_KEYS/SHOWDOWN are the only consumers below).
        _cr_baseline_r = f'MIN(100,{crit_rate_total_ref})'
        _cr_boss_r = f'MIN(100,{crit_rate_total_ref}+{art_ref("contract_of_darkness_crit_rate_bonus")})'
        _cod_crit_ratio_r = (
            f'((L{r}*(1-{_cr_boss_r}/100)+M{r}*({_cr_boss_r}/100))'
            f'/(L{r}*(1-{_cr_baseline_r}/100)+M{r}*({_cr_baseline_r}/100)))'
        )
        # Fire Flower/Chalice's boss-branch Final Damage — composed as one more multiplicative
        # factor alongside the two ratio corrections above.
        extra_boss_mult_r = (
            f'({_spear_def_ratio_r}*{_cod_crit_ratio_r}*(1+{art_ref("AGG_FINAL_DAMAGE_BOSS_ONLY")}/100))'
        )
        # Secret Map/Fire Flower/Chalice — Final Damage bonuses that apply only to the
        # normal-monster branch, never boss/PvP.
        extra_normal_mult_r = f'(1+{art_ref("AGG_FINAL_DAMAGE_NORMAL_ONLY")}/100)'

        # Per-cast boss damage before any timing factor (engine weights; deliberately free of cast counts so the engine can pick them)
        if key == "SHOWDOWN":
            ws.cell(row=r, column=25, value=f"=IF(C{r}," + boss_normal_dps_split_exprs(
                f"{S('HitsPerCast', r)}*N{r}", IB("monster_type"), boss_dmg_pct_r, normal_dmg_pct_r,
                S("NormalMonsterTargets", r), IB("max_enemies_hit"), extra_boss_mult_r, extra_normal_mult_r)[0] + ",0)")
        elif key in STATUS_PERCAST_KEYS:
            ws.cell(row=r, column=25, value=f"=IF(C{r}," + boss_normal_dps_split_exprs(
                f"H{r}*N{r}*G{r}", IB("monster_type"), boss_dmg_pct_r, normal_dmg_pct_r,
                S("NormalMonsterTargets", r), IB("max_enemies_hit"), extra_boss_mult_r, extra_normal_mult_r)[0] + ",0)")

        # O — DPS, dispatched by category.
        if key == "SHOWDOWN":
            prefix = f"{S('HitsPerCast', r)}*N{r}*Summary!$B${R_BAPS}"
            boss_expr, normal_expr = boss_normal_dps_split_exprs(
                prefix, IB("monster_type"), boss_dmg_pct_r, normal_dmg_pct_r,
                S("NormalMonsterTargets", r), IB("max_enemies_hit"),
                extra_boss_mult_r, extra_normal_mult_r,
            )
            ws.cell(row=r, column=20, value=f'=IF(C{r},{boss_expr},0)')
            ws.cell(row=r, column=22, value=f'=IF(C{r},{normal_expr},0)')
        elif key in DAMAGE_ROW_KEYS:
            prefix = f'H{r}*N{r}*{rate_r}'
            boss_expr, normal_expr = boss_normal_dps_split_exprs(
                prefix, IB("monster_type"), boss_dmg_pct_r, normal_dmg_pct_r,
                S("NormalMonsterTargets", r), IB("max_enemies_hit"),
                extra_boss_mult_r, extra_normal_mult_r,
            )
            ws.cell(row=r, column=20, value=f'=IF(C{r},{boss_expr},0)')
            ws.cell(row=r, column=22, value=f'=IF(C{r},{normal_expr},0)')
        elif key in TOXIC_VENOM_ROW_KEYS:
            total_hit_rate = (
                f'SUMPRODUCT((Skills!{SC["TriggersToxicVenom"]}2:{SC["TriggersToxicVenom"]}{LAST_ROW}=TRUE)*'
                f'(C2:C{LAST_ROW}=TRUE)*S2:S{LAST_ROW})'
            )
            prefix = f'0.2*{total_hit_rate}*N{r}'
            boss_expr, normal_expr = boss_normal_dps_split_exprs(
                prefix, IB("monster_type"), boss_dmg_pct_r, normal_dmg_pct_r,
                S("NormalMonsterTargets", r), IB("max_enemies_hit"),
                extra_boss_mult_r, extra_normal_mult_r,
            )
            ws.cell(row=r, column=20, value=f'=IF(C{r},{boss_expr},0)')
            ws.cell(row=r, column=22, value=f'=IF(C{r},{normal_expr},0)')
        elif key in SHADOW_SHIFTER_ROW_KEYS:
            prefix = f'{IB("incoming_hit_rate")}*0.2*N{r}'
            boss_expr, normal_expr = boss_normal_dps_split_exprs(
                prefix, IB("monster_type"), boss_dmg_pct_r, normal_dmg_pct_r,
                S("NormalMonsterTargets", r), IB("max_enemies_hit"),
                extra_boss_mult_r, extra_normal_mult_r,
            )
            ws.cell(row=r, column=20, value=f'=IF(C{r},{boss_expr},0)')
            ws.cell(row=r, column=22, value=f'=IF(C{r},{normal_expr},0)')
        else:
            ws.cell(row=r, column=20, value=0)
            ws.cell(row=r, column=22, value=0)

        ws.cell(row=r, column=15, value=f'=(1-{IB("normal_weight_frac")})*T{r}+{IB("normal_weight_frac")}*V{r}')

        ws.cell(row=r, column=16, value=f'=IF(Summary!$B${R_TOTAL}=0,0,O{r}/Summary!$B${R_TOTAL})')

        # Q — safe per-row reciprocal cooldown (Excel @-implicit-intersection workaround, see
        # FP_MAGE_PROJECT_NOTES.md — a single-cell IFERROR call, never a range nested inside one).
        ws.cell(row=r, column=17, value=(f'=IFERROR(1/{eff_cd_r},0)' if has_cooldown else 0))

        # R — CastsInFight (fixed-duration mode only).
        if has_cooldown:
            casts_formula = guarded_casts_expr(available_duration_r, eff_cd_r)
            ws.cell(row=r, column=18, value=f'=IF({fixed_duration_active_main},{casts_formula},0)')
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
            ws.cell(row=r, column=19, value=hit_count_s_expr(r, IB("normal_weight_frac"), S("HitsPerCast", r)))

    for _key, _r in ROW.items():   # masteries multiply damage (see apply_mastery_semantics)
        ws.cell(row=_r, column=6).value = apply_mastery_semantics(_key, _r, ws.cell(row=_r, column=6).value)

    _chm = companion_host_main()
    _ph_main = phase_state_ratios(
        IB("content_type"), IB("fight_duration"), _chm["hex_phase_v"], art_ref("hexagon_damage"), _chm["attack_bucket_avg"],
        _chm["charm_val"], art_ref("charm_of_the_undead"),
    )
    apply_status_columns(
        ws, {k: v for k, v in ROW.items()}, STATUS_MAIN_LAYOUT, STATUS_MAIN_LAYOUT.s("on"),
        f'(1+{IB("status_effect_damage")}/100*{companion_main_ref("stunfracB")})*({_ph_main[0]})',
        f'(1+{IB("status_effect_damage")}/100*{companion_main_ref("stunfracN")})*({_ph_main[1]})',
    )

    ws.cell(row=1, column=17, value="InvCooldown")
    ws.cell(row=1, column=18, value="CastsInFight")
    ws.cell(row=1, column=19, value="HitRate(perSec)")
    ws.cell(row=1, column=20, value="BossOnlyDPS")
    ws.cell(row=1, column=22, value="NormalOnlyDPS")

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
            fda_main, f'Calc!R{row}', IB("monster_type"), S("BuffDuration(s)", row), f'(1/Calc!Q{row})',
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

    ws.cell(row=R_AVGBUFF, column=1, value="Average Buff Multiplier (Dark Sight Attack + Frailty Curse self-FD + Adrenalin FD + Artifact Attack%; with the Status/KO engine on: its mean buff bucket x Adrenalin FD)")
    ws.cell(row=R_AVGBUFF, column=2, value=(
        # Attack% sources (Dark Sight Attack + every Attack%-granting artifact) are ONE additive bucket, summed before a
        # single multiplication — exactly what every Sensitivity block does (attack_bucket_block) and what the other 11
        # classes' Summary does. Frailty Curse / Adrenalin are Final Damage: separate multiplicative factors.
        # (Until 2026-11-03 the artifact Attack% was a separate (1+Art/100) factor here, so Summary sat ~2.4% above every
        # Sensitivity block at the same Inputs and every swept stat showed a negative DPS gain.)
        # Status/KO engine on: its mean buff bucket (Dark Sight's Attack% inside the additive bucket with the artifacts, Frailty Curse's Final Damage as its own
        # multiplicative term, both at the engine's cast times) x Alchemic Adrenaline's averaged Final Damage factor.
        f'=IF({STATUS_MAIN_LAYOUT.s("on")}=1,{STATUS_MAIN_LAYOUT.s("Bbuff_mean")}*(1+{adrenalin_fd_avg}/100),'
        f'(1+({dark_sight_atk_avg}+{art_ref("AGG_ATTACK_PCT")})/100)*(1+{frailty_self_fd_avg}/100)*(1+{adrenalin_fd_avg}/100))'
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
    ws.cell(row=R_TOTAL, column=2, value=(
        f'=SUM(Calc!O2:O{LAST_ROW})+(1-{IB("normal_weight_frac")})*{companion_main_ref("comp_boss_dps")}'
        f'+{IB("normal_weight_frac")}*{companion_main_ref("comp_norm_dps")}'
    )).font = Font(bold=True, size=13)

    ws.cell(row=R_BOSS_ONLY_TOTAL, column=1, value="Boss-Only Total DPS (Sensitivity baseline)")
    ws.cell(row=R_BOSS_ONLY_TOTAL, column=2, value=f'=SUM(Calc!T2:T{LAST_ROW})+{companion_main_ref("comp_boss_dps")}')
    ws.cell(row=R_NORMAL_ONLY_TOTAL, column=1, value="Normal-Only Total DPS (Sensitivity baseline)")
    ws.cell(row=R_NORMAL_ONLY_TOTAL, column=2, value=f'=SUM(Calc!V2:V{LAST_ROW})+{companion_main_ref("comp_norm_dps")}')

    ws.cell(row=R_SHOWDOWN_DPS, column=1, value="Showdown (Basic Attack) DPS")
    ws.cell(row=R_SHOWDOWN_DPS, column=2, value=f"=Calc!O{ROW['SHOWDOWN']}")

    ws.cell(row=R_STARTUP_TIME, column=1, value=(
        "Buff-Casting Startup Delay (s, before first damage-skill cast; fixed-duration only)"
    ))
    ws.cell(row=R_STARTUP_TIME, column=2, value=f'=IF({STATUS_MAIN_LAYOUT.s("on")}=1,0,' + buff_cast_startup_time_expr(
        fda_main, SC["BuffDuration(s)"], SC["CostsActionSlot"], f"Calc!C2:C{LAST_ROW}",
        f"B{R_APS}", LAST_ROW,
    ) + ")")

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
    ws.cell(row=row_cursor, column=1, value="Companion (its damage + the player uplift it grants)")
    ws.cell(row=row_cursor, column=2, value=(
        f'=(1-{IB("normal_weight_frac")})*{companion_main_ref("comp_boss_dps")}'
        f'+{IB("normal_weight_frac")}*{companion_main_ref("comp_norm_dps")}'
    ))
    ws.cell(row=row_cursor, column=3, value=f"=IF(B{R_TOTAL}=0,0,B{row_cursor}/B{R_TOTAL}*100)")
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

    row_cursor += 1
    ws.cell(row=row_cursor - 1, column=1, value="Artifact Equip-Toggle DPS Gain, best to worst (see Sensitivity for full detail)").font = SECTION_FONT
    row_cursor += 1
    ws.cell(row=row_cursor, column=1, value="Artifact")
    ws.cell(row=row_cursor, column=2, value="DPS Gain")
    ws.cell(row=row_cursor, column=3, value="% Gain")
    style_header_row(ws, row_cursor, 3)
    row_cursor += 1
    # Sensitivity's own A/B/C columns are already sorted best-to-worst — just mirror them here
    # rather than re-deriving the sort (single source of truth for the ranking logic).
    for s_row in range(ARTIFACT_TABLE_FIRST_DATA_ROW, ARTIFACT_TABLE_LAST_DATA_ROW + 1):
        ws.cell(row=row_cursor, column=1, value=f"=Sensitivity!A{s_row}")
        ws.cell(row=row_cursor, column=2, value=f"=Sensitivity!B{s_row}")
        ws.cell(row=row_cursor, column=3, value=f"=Sensitivity!C{s_row}")
        row_cursor += 1

    ws.column_dimensions["A"].width = 60
    ws.column_dimensions["B"].width = 16
    ws.column_dimensions["C"].width = 12
    return ws


# ---------------------------------------------------------------------------
# Companion sheet (see src/companion_model.py for the rules and the cell definitions)
# ---------------------------------------------------------------------------
COMPANION_CELL_NAMES = cm.cell_names()
COMPANION_POTENTIAL_STAT = "Companion Summoning Time Increase %"
COMPANION_FIRST_ROW = 5
COMPANION_ROW_OF = {name: COMPANION_FIRST_ROW + i for i, name in enumerate(COMPANION_CELL_NAMES)}
COMPANION_B0_ROW = COMPANION_FIRST_ROW + len(COMPANION_CELL_NAMES) + 1     # b0 cell (column B)
COMPANION_CMP_COL = {name: 3 + i for i, name in enumerate(cm.COMPANIONS)}  # comparison columns: one per companion (C..)
# 'Summoning Time Increase = b0 + X' columns: X = 0 and every total the boots potential lines can add up to
COMPANION_POT_TOTALS = [0] + list(cm.potential_line_totals().keys())
COMPANION_POT_FIRST_COL = 3 + len(cm.COMPANIONS) + 1                       # after a blank column
COMPANION_POT_COL = {x: COMPANION_POT_FIRST_COL + i for i, x in enumerate(COMPANION_POT_TOTALS)}
COMPANION_HOST_FIRST_ROW = COMPANION_B0_ROW + 2                            # exported host values (read by the cube EV script)


def companion_main_ref(name):
    """Cross-sheet reference to a Companion-sheet cell, e.g. 'Companion!$B$12'."""
    return f"Companion!$B${COMPANION_ROW_OF[name]}"


def companion_extra_mults_main(basic_row):
    """(extra_boss_mult, extra_normal_mult) of the Showdown (basic attack) row, as cross-sheet (Calc!) expressions - the same
    Reindeer's Spear / Contract of Darkness / boss-only Final Damage composition build_calc_sheet uses per row."""
    crit_rate_total = f'({IB("crit_rate")}+Summary!$B${R_CRIT_RATE_BONUS}+{art_ref("AGG_CRIT_RATE")})'
    def_pen_base = IB("def_pen")
    reindeer_s = art_ref("reindeer_spear_base_def_pen_reference")
    def_pen_boss = f'(100*(1-(1-{def_pen_base}/100)*(1-{reindeer_s}/100)^{artifact_reindeer_spear_extra_mult_expr(IB("monster_type"))}))'
    spear_ratio = (
        f'((5000/(6000+{IB("monster_defense")}*(1-{def_pen_boss}/100)))'
        f'/(5000/(6000+{IB("monster_defense")}*(1-{def_pen_base}/100))))'
    )
    cr_base = f'MIN(100,{crit_rate_total})'
    cr_boss = f'MIN(100,{crit_rate_total}+{art_ref("contract_of_darkness_crit_rate_bonus")})'
    L, M = f"Calc!L{basic_row}", f"Calc!M{basic_row}"
    cod_ratio = f'(({L}*(1-{cr_boss}/100)+{M}*({cr_boss}/100))/({L}*(1-{cr_base}/100)+{M}*({cr_base}/100)))'
    extra_boss = f'({spear_ratio}*{cod_ratio}*(1+{art_ref("AGG_FINAL_DAMAGE_BOSS_ONLY")}/100))'
    extra_norm = f'(1+{art_ref("AGG_FINAL_DAMAGE_NORMAL_ONLY")}/100)'
    return extra_boss, extra_norm


def companion_taken_bucket(mt, w, boss_pct, norm_pct):
    """The bucket the companion's damage-taken debuffs add into.  Night Lord keeps the artifact 'enemy damage taken' bonus (and Venom Weaken / the Frailty Curse debuff) inside the
    boss / normal monster damage % buckets (Summary R_MONSTER_DMG_BONUS), so a debuff is additive there: its value is d / (100 + bucket).
    The shared model has ONE bucket for both branches, so use the boss/normal blend of the two (PvP has neither bonus: separate factor)."""
    return f'IF({mt}="pvp",0,(1-{w})*{boss_pct}+{w}*{norm_pct})'


def buff_snapshot_terms(cell, adr_uptime_ref):
    """Expressions of Night Lord's buff sources for the companion's snapshot (`cell(letter, key)` = the Calc(-twin) cell):
      ds_full   Dark Sight (Attack), a CAST buff, fully up at the summon
      fc_full   Frailty Curse (self Final Damage), a CAST buff, fully up at the summon
      adr_avg   Alchemic Adrenaline's Final Damage proc (action-rate driven: stays at its average uptime, like the dice roll / Ahoy proc in the sibling classes)"""
    c = cell
    t = {}
    t["ds_full"] = f'(({c("C", "DARK_SIGHT_ATK")}=TRUE)*{c("F", "DARK_SIGHT_ATK")})'
    t["fc_full"] = f'(({c("C", "FRAILTY_CURSE_SELF_FD")}=TRUE)*{c("F", "FRAILTY_CURSE_SELF_FD")})'
    t["adr_avg"] = f'(({c("C", "ADRENALIN_FD")}=TRUE)*{c("F", "ADRENALIN_FD")}*{adr_uptime_ref})'
    return t


def main_buff_terms():
    cell = lambda letter, key: f"Calc!{letter}{ROW[key]}"
    return buff_snapshot_terms(cell, f"Summary!$B${R_ADRENALIN_UPTIME}")


def main_buff_uptime(row):
    """Summary's own buff uptime expression (steady-state / exact-duration from the row's Calc cast count R and cooldown Q), usable outside build_summary_sheet."""
    return uptime_fraction_or_exact_expr(
        fixed_duration_active_expr(IB("monster_type"), IB("fight_duration")), f'Calc!R{row}', IB("monster_type"), S("BuffDuration(s)", row),
        f'(1/Calc!Q{row})', IB("buff_duration_increase_pct"), IB("fight_duration"),
    )


def companion_host_main():
    """Host expressions for the Companion sheet (references into Calc / Summary / Artifacts, main-sheet state).
    Night Lord specifics: `avgbuff` = Summary R_AVGBUFF (Dark Sight's Attack% inside the additive Attack% bucket with the artifacts, x Frailty Curse's and Adrenalin's
    Final Damage factors; with the engine on: its mean buff bucket x Adrenalin).  The snapshot has the CAST buffs (Dark Sight, Frailty Curse) fully up while Alchemic
    Adrenaline stays at its average.  `unit` = Showdown's N/F WITHOUT Shadow Partner's average multiplier (the clone mirrors the player's own attacks, like the Final Attack
    procs of the sibling classes it is not part of the companion's hits).
    Like the other warrior / thief classes the 'enemy damage taken' bonuses (Venom Weaken, Frailty Curse debuff, artifacts) sit INSIDE the boss / normal monster damage %
    buckets (R_MONSTER_DMG_BONUS + AGG_ENEMY_DMG_TAKEN); Showdown's own Boss Monster Damage mastery is a skill mastery and is not part of boss_pct."""
    b = ROW["SHOWDOWN"]
    t = main_buff_terms()
    extra_boss, extra_norm = companion_extra_mults_main(b)
    boss_pct = f'({IB("boss_damage")}+{art_ref("AGG_BOSS_DAMAGE")}+Summary!$B${R_MONSTER_DMG_BONUS}+{art_ref("AGG_ENEMY_DMG_TAKEN")})'
    norm_pct = f'({IB("normal_damage")}+{art_ref("AGG_NORMAL_DAMAGE")}+Summary!$B${R_MONSTER_DMG_BONUS}+{art_ref("AGG_ENEMY_DMG_TAKEN")})'
    k1 = f'({t["ds_full"]}+{art_ref("AGG_ATTACK_PCT")}-{art_ref("charm_of_the_undead")})'
    fdpart = f'((1+{t["fc_full"]}/100)*(1+{t["adr_avg"]}/100))'
    r_dsa = ROW["DARK_SIGHT_ATK"]
    attack_bucket_avg = f'((Calc!C{r_dsa}=TRUE)*Calc!F{r_dsa}*{main_buff_uptime(r_dsa)}+{art_ref("AGG_ATTACK_PCT")})'
    return {
        "choice": IB("companion_choice"),
        "inc": companion_summon_time_inc_expr(IB("companion_summon_time_increase_pct"), art_ref("arwens_glass_shoes_summon_time_increase_pct")),
        "lvl": companion_level_lookup_expr(IB("companion_choice")),
        "mt": IB("monster_type"), "T": IB("fight_duration"), "content": IB("content_type"),
        "pvp_len": PVP_FIGHT_DURATION, "cap": IB("max_enemies_hit"), "w": IB("normal_weight_frac"),
        "unit": f'IFERROR(Calc!N{b}/Calc!F{b}/Summary!$B${R_SHADOW_PARTNER_MULT},0)',
        "bad": f'({IB("basic_attack_damage")}+{art_ref("AGG_BASIC_ATTACK_DAMAGE")})',
        "sd": f'({IB("skill_damage")}+{art_ref("AGG_SKILL_DAMAGE")})',
        "aps": f"Summary!$B${R_APS}",
        "avgbuff": f'Summary!$B${R_AVGBUFF}',
        "attack_bucket_avg": attack_bucket_avg,
        "k1": k1, "fdpart": fdpart,
        "avgbuff_snap": lambda charm_expr, extra: f'((1+({k1}+{charm_expr}+{extra})/100)*{fdpart})',
        "charm_val": f'IF({IB("charm_of_the_undead_equipped")},{star_lookup_expr(IB("charm_of_the_undead_star"), "charm_of_the_undead_attack_pct")},0)',
        "agg_damage_avg": art_ref("AGG_DAMAGE"), "hex_avg": art_ref("hexagon_damage"),
        "hex_snap": lambda stacks: f'IF({IB("hexagon_necklace_equipped")},{star_lookup_expr(IB("hexagon_necklace_star"), "hexagon_necklace_damage")}*{stacks},0)',
        "agg_fd_boss_only": art_ref("AGG_FINAL_DAMAGE_BOSS_ONLY"), "agg_fd_norm_only": art_ref("AGG_FINAL_DAMAGE_NORMAL_ONLY"),
        "chalice_avg_boss": art_ref("chalice_boss"), "chalice_avg_norm": art_ref("chalice_normal"),
        "chalice_full": (
            f'IF(AND({IB("chalice_equipped")},OR({IB("monster_type")}="normal",{IB("monster_type")}="breakthrough")),'
            f'{star_lookup_expr(IB("chalice_star"), "chalice_final_damage")},0)'
        ),
        "horn_avg": art_ref("horn_flute"),
        "hex_phase_v": f'IF({IB("hexagon_necklace_equipped")},{star_lookup_expr(IB("hexagon_necklace_star"), "hexagon_necklace_damage")},0)',
        "horn_full": artifact_horn_flute_full_expr(IB("horn_flute_equipped"), IB("content_type"), IB("horn_flute_star")),
        "boss_pct": boss_pct, "norm_pct": norm_pct,
        "extra_boss": extra_boss, "extra_norm": extra_norm,
        "player_boss": f"SUM(Calc!T2:T{LAST_ROW})", "player_norm": f"SUM(Calc!V2:V{LAST_ROW})",
        "player_uniform_boss": "(" + "+".join(f"Calc!T{ROW[k]}" for k in STATUS_UNIFORM_ROWS) + ")",
        "player_basic_boss": f"Calc!T{b}", "player_basic_norm": f"Calc!V{b}",
        "cr_total": f'({IB("crit_rate")}+Summary!$B${R_CRIT_RATE_BONUS}+{art_ref("AGG_CRIT_RATE")})',
        "cd_total": f'({IB("crit_damage")}+Summary!$B${R_CRIT_DAMAGE_BONUS}+{art_ref("AGG_CRIT_DAMAGE")})',
        "min_dmg": IB("min_damage"), "max_dmg": IB("max_damage"),
        "defense": IB("monster_defense"), "def_pen": IB("def_pen"),
        "taken_bucket": companion_taken_bucket(IB("monster_type"), IB("normal_weight_frac"), boss_pct, norm_pct),
        "st_on": STATUS_MAIN_LAYOUT.s("on"), "st_S": IB("status_effect_damage"), "st_idx": STATUS_MAIN_LAYOUT.rng("idx"),
        "st_mult": STATUS_MAIN_LAYOUT.rng("mult"), "st_act": STATUS_MAIN_LAYOUT.rng("act"), "st_dw": STATUS_MAIN_LAYOUT.rng("dw"),
        "pst": stl.player_stun_entries(STATUS_PLAYER_STUN, lambda l, k: f"Calc!{l}{ROW[k]}", f"Summary!$B${R_STARTUP_TIME}"),
    }


def companion_host_export():
    """Ordered (key, expression) pairs of every numeric host value the Python mirror (src/companion_python_model.py) needs; written
    to the Companion sheet so potential_cubes_ev.py can re-run the companion model at any Summoning Time Increase."""
    h = companion_host_main()
    out = [(k, h[k]) for k in cm.HOST_KEYS if k not in ("charm_val",)]
    out += [
        ("charm_val", h["charm_val"]),
        ("k1", h["k1"]),
        ("fdpart", h["fdpart"]),
        ("hex_per_stack", f'IF({IB("hexagon_necklace_equipped")},{star_lookup_expr(IB("hexagon_necklace_star"), "hexagon_necklace_damage")},0)'),
        ("total_dps", f"Summary!$B${R_TOTAL}"),
        ("comp_blend_current", companion_main_ref("comp_blend_dps")),
        ("st_on", STATUS_MAIN_LAYOUT.s("on")),
        ("st_S", IB("status_effect_damage")),
    ] + stl.player_stun_export(h["pst"])
    return out


def companion_level_lookup_expr(choice_expr):
    """Level (0 = not unlocked / none) of the companion named by `choice_expr`, from the CompanionsInput sheet."""
    return (
        f'IFERROR(INDEX(CompanionsInput!$C${COMPANIONS_INPUT_FIRST_ROW}:$C${COMPANIONS_INPUT_LAST_ROW},'
        f'MATCH({choice_expr},CompanionsInput!$A${COMPANIONS_INPUT_FIRST_ROW}:$A${COMPANIONS_INPUT_LAST_ROW},0)),0)'
    )


def companion_weighted_ratio(col, base=None):
    """Relative DPS growth with the Companion-sheet column `col` vs `base` (None = no companion, else a Companion-sheet column letter), weighted by the
    content's boss/normal emphasis w - each branch's own relative growth (new/baseline) blended by w, never the dollar totals (project rule, CLAUDE.md #9:
    a weight is a weight on RELATIVE gains, so +18% against the boss is worth (1-w) x 18%)."""
    rb, rn = COMPANION_ROW_OF["comp_boss_dps"], COMPANION_ROW_OF["comp_norm_dps"]
    pb, pn = f"SUM(Calc!$T$2:$T${LAST_ROW})", f"SUM(Calc!$V$2:$V${LAST_ROW})"
    w = IB("normal_weight_frac")
    bb = f"Companion!${base}${rb}" if base else "0"
    bn = f"Companion!${base}${rn}" if base else "0"
    return (f"((1-{w})*IFERROR(({pb}+Companion!${col}${rb})/({pb}+{bb}),1)"
            f"+{w}*IFERROR(({pn}+Companion!${col}${rn})/({pn}+{bn}),1))")


def build_companions_input_sheet(wb, existing=None):
    """One row per companion: the level you own it at ("Not unlocked" or 1-18), shared by every content type.  Which
    companion is summoned in each content type is picked on the Inputs sheet; the Sensitivity sheet's Companion
    Comparison table (mirrored in columns D/E here) shows the DPS each unlocked companion would add."""
    existing = existing or {}
    ws = wb.create_sheet("CompanionsInput")
    ws["A1"] = "Companions - level of each companion you own"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = (
        "Set each companion's level (Not unlocked, or 1-18).  The companion summoned in each content type is chosen on the "
        "Inputs sheet.  Damage multiplier by level: 60/64/68/72/75/78/81/84/87/90% (90% from Lv10 on); +25% Final Damage at "
        "Lv5, Lv8 and Lv10 (every companion).  Columns D/E show the DPS this companion would add in the CURRENT content type."
    )
    headers = ["Companion", "Level (Not unlocked / 1-18)", "Level, resolved (computed)", "DPS gain vs no companion", "% of Total DPS (without a companion) gained"]
    for i, name in enumerate(headers):
        ws.cell(row=COMPANIONS_INPUT_FIRST_ROW - 1, column=i + 1, value=name)
    style_header_row(ws, COMPANIONS_INPUT_FIRST_ROW - 1, len(headers))
    dv = DataValidation(type="list", formula1='"' + ",".join(cm.COMPANION_LEVEL_CHOICES) + '"', allow_blank=False)
    ws.add_data_validation(dv)
    for name, row in COMPANION_INPUT_ROW.items():
        ws.cell(row=row, column=1, value=name).font = LABEL_FONT
        cell = ws.cell(row=row, column=2, value=existing.get(name, "Not unlocked"))
        cell.fill = INPUT_FILL
        dv.add(cell)
        ws.cell(row=row, column=3, value=f'=IF(ISNUMBER(B{row}),B{row},IFERROR(VALUE(B{row}),0))')
        _ratio = companion_weighted_ratio(get_column_letter(COMPANION_CMP_COL[name]))
        _player_total = f"(Summary!$B${R_TOTAL}-Companion!$B${COMPANION_ROW_OF['comp_blend_dps']})"
        ws.cell(row=row, column=4, value=f"={_player_total}*({_ratio}-1)")
        ws.cell(row=row, column=5, value=f"=({_ratio}-1)*100")
    # Companion Summoning Time Increase % potential lines (boots): DPS value of every TOTAL the lines can add up to.  Lines roll at
    # the item's tier or the tier below, so 12%+5% can never share a potential (see companion_model.potential_line_totals).
    t0 = COMPANIONS_INPUT_LAST_ROW + 3
    ws.cell(row=t0 - 1, column=1, value=(
        "Companion Summoning Time Increase % potential lines - value of each possible total (summoned companion = the one chosen "
        "for the current content type; the cube script prices rolls of this stat from this curve)"
    )).font = SECTION_FONT
    t_headers = ["Total % from lines", "Possible line combinations", "Total DPS gain vs no such lines", "% DPS gain vs no such lines", "DPS vs your current setup",
                 "Boss phase: average DPS change (over the longer phase)", "Boss phase: time factor", "Boss phase: total damage change (DPS x time)"]
    for i, name in enumerate(t_headers):
        ws.cell(row=t0, column=i + 1, value=name)
    style_header_row(ws, t0, len(t_headers))
    bl = COMPANION_ROW_OF["comp_blend_dps"]
    base_col = get_column_letter(COMPANION_POT_COL[0])
    for i, (total, combos) in enumerate(cm.potential_line_totals().items()):
        r = t0 + 1 + i
        col = get_column_letter(COMPANION_POT_COL[total])
        ws.cell(row=r, column=1, value=total)
        ws.cell(row=r, column=2, value="  |  ".join(combos))
        _ratio = companion_weighted_ratio(col, base_col)
        _base_total = f"(Summary!$B${R_TOTAL}-Companion!$B${bl}+Companion!${base_col}${bl})"
        ws.cell(row=r, column=3, value=f"={_base_total}*({_ratio}-1)")
        ws.cell(row=r, column=4, value=f"=({_ratio}-1)*100")
        ws.cell(row=r, column=5, value=f"={_base_total}*{_ratio}-Summary!$B${R_TOTAL}")
        # Boss-phase breakdown (contents with a normal-monster phase first: Breakthrough, Hero Dungeon): the boss part's total damage
        # D = player boss DPS x base boss-phase length + the companion's boss-phase damage and uplift + the player's damage in the stun extension; average DPS = D / (phase + extension),
        # so  (average-DPS change) x (time factor) = (total damage change).
        _R = COMPANION_ROW_OF
        _tb0, _tbp = f"Companion!$B${_R['tb0']}", f"Companion!$B${_R['Tbp']}"

        def _D(c):
            return (f"(Companion!${c}${_R['pb']}*{_tbp}+Companion!${c}${_R['best_dmg_b']}+Companion!${c}${_R['best_upl_b']}+Companion!${c}${_R['best_ext']})")

        def _T(c):
            return f"({_tbp}+Companion!${c}${_R['best_E']})"
        ws.cell(row=r, column=6, value=f'=IF({_tb0}>0,IFERROR(({_D(col)}/{_T(col)})/({_D(base_col)}/{_T(base_col)})-1,0),"")')
        ws.cell(row=r, column=7, value=f'=IF({_tb0}>0,{_T(col)}/{_T(base_col)},"")')
        ws.cell(row=r, column=8, value=f'=IF({_tb0}>0,IFERROR({_D(col)}/{_D(base_col)}-1,0),"")')
    for i, w in enumerate([26, 60, 30, 28, 24, 30, 22, 30]):
        ws.column_dimensions[get_column_letter(i + 1)].width = w
    return ws


def build_timeline_sheet(wb):
    """Status Effect Damage / KO timeline (main sheet): the engine strip src/status_timeline.py describes, run on this workbook's own numbers."""
    ws = wb.create_sheet(TIMELINE_SHEET)
    ws["A1"] = "Status Effect / KO timeline - when the player casts, and what the status windows are worth"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = (
        "Used in fixed-length single-target content with KO phases (World Boss, Enhancement Dungeon) and, once companions stun, wherever the enemy is stunned/frozen. "
        "The player is assumed to play optimally: buffs and cooldown skills are cast when they pay most (cooldown spacing respected), Hexagon Necklace stacks and the "
        "Charm of the Undead window are counted second by second. 'Timing factors' (Calc columns W/X) scale each row's averaged DPS. " + STATUS_KO_FIRST_BIN_NOTE + "."
    )
    ws["A2"].alignment = Alignment(wrap_text=True, vertical="top")
    cell = lambda letter, key: f"Calc!{letter}{ROW[key]}"
    host = status_engine_host(
        IB, cell, lambda key: S("ActiveWindow(s)", ROW[key]),
        IB("buff_duration_increase_pct"),
        f'({art_ref("AGG_ATTACK_PCT")}-{art_ref("charm_of_the_undead")})',
        f'IF({IB("charm_of_the_undead_equipped")},{star_lookup_expr(IB("charm_of_the_undead_star"), "charm_of_the_undead_attack_pct")},0)',
        f'IF({IB("hexagon_necklace_equipped")},{star_lookup_expr(IB("hexagon_necklace_star"), "hexagon_necklace_damage")},0)',
        art_ref("hexagon_damage"), f'Calc!Y{ROW["SHOWDOWN"]}',
        hasstun=companion_main_ref("hasstun"),
        stun=lambda i: cm.resolve_tokens(cm.stun_bin_expr(i, companion_main_ref, None), companion_main_ref),
    )
    lay = stl.Layout(stl.cells(host), STATUS_STRIP_ROW0, 1)
    lay.write(ws)
    ws.column_dimensions["A"].width = 70
    ws.column_dimensions["B"].width = 16
    ws.freeze_panes = "A4"
    return ws


def build_companion_kits_sheet(wb):
    """The kit table (one row per component of every companion) that the Companion sheet's formulas read; source of truth is
    src/companion_kits.py (transcribed from the user's MS_IDLE_COMPS_STATS.xlsx).  Not meant for manual editing."""
    ws = wb.create_sheet("CompanionKits")
    for i, name in enumerate(cm.SHEET_COLUMNS):
        ws.cell(row=1, column=i + 1, value=name)
    style_header_row(ws, 1, len(cm.SHEET_COLUMNS))
    for r, rec in enumerate(cm.KIT_ROWS):
        for i, name in enumerate(cm.SHEET_COLUMNS):
            ws.cell(row=cm.KIT_FIRST_ROW + r, column=i + 1, value=rec[name])
    for i, name in enumerate(cm.SHEET_COLUMNS):
        ws.column_dimensions[get_column_letter(i + 1)].width = 60 if name == "note" else (16 if name in ("comp", "idkey", "pkey") else 9)
    ws.freeze_panes = "D2"
    return ws


def build_companion_sheet(wb):
    ws = wb.create_sheet("Companion")
    ws["A1"] = "Companion (summoned ally) - DPS contribution of the companion chosen on the Inputs sheet"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = (
        "The companion snapshots the player's stats when summoned, then deals damage for 30s x (1 + Companion Summoning Time "
        "Increase %).  Column B = the companion chosen on the Inputs sheet; columns C.. = every companion evaluated the same way "
        "(Sensitivity / CompanionsInput comparison tables); the far-right grid re-runs the chosen companion at Summoning Time "
        "Increase = b0 + n.  See KNOWN_GAPS.md 'Companions' and the CompanionKits sheet for every rule and kit."
    )
    ws["A3"] = "Result cells 'Companion DPS' feed Summary Total DPS (boss-only and normal-only totals as well)."
    ws.cell(row=COMPANION_FIRST_ROW - 1, column=1, value="Cell").font = LABEL_FONT
    ws.cell(row=COMPANION_FIRST_ROW - 1, column=2, value="Chosen on Inputs").font = LABEL_FONT
    host = companion_host_main()

    def write(name, label, formula):
        r = COMPANION_ROW_OF[name]
        ws.cell(row=r, column=1, value=label)
        ws.cell(row=r, column=2, value=formula)

    cm.emit(cm.cells(host), lambda nm: f"$B${COMPANION_ROW_OF[nm]}", write)   # same-sheet references (shorter formulas: Excel's 8192-character cap)

    # Comparison columns: the same chain with the companion forced to each one in the catalog (level from CompanionsInput)
    for name, col_idx in ([] if os.environ.get('COMP_LIGHT') else COMPANION_CMP_COL.items()):
        col = get_column_letter(col_idx)
        ws.cell(row=COMPANION_FIRST_ROW - 1, column=col_idx, value=name).font = LABEL_FONT
        host_c = dict(host)
        host_c["choice"] = f'"{name}"'
        host_c["lvl"] = companion_level_lookup_expr(f'"{name}"')

        def write_c(nm, _label, formula, col=col):
            ws[f"{col}{COMPANION_ROW_OF[nm]}"] = formula

        cm.emit(cm.cells(host_c), lambda nm, col=col: f"{col}{COMPANION_ROW_OF[nm]}", write_c)

    # 'b0 + X' columns: the chosen companion re-evaluated at Summoning Time Increase % = b0 + X (b0 = your Inputs value WITHOUT the
    # boots potential lines currently listed on PotentialCubes) for X = 0 and every total those lines can add up to.  Feeds the
    # potential-line table on CompanionsInput.  (The cube EV script re-runs the model in Python at any other value.)
    r_b0 = COMPANION_B0_ROW
    own_lines = "+".join(
        f'SUMIF(PotentialCubes!${sc}${POTENTIAL_CUBES_FIRST_DATA_ROW}:${sc}${POTENTIAL_CUBES_LAST_DATA_ROW},"{COMPANION_POTENTIAL_STAT}",'
        f'PotentialCubes!${vc}${POTENTIAL_CUBES_FIRST_DATA_ROW}:${vc}${POTENTIAL_CUBES_LAST_DATA_ROW})'
        for sc, vc in (("E", "F"), ("G", "H"), ("I", "J"))
    )
    ws.cell(row=r_b0, column=1, value=(
        "b0 = Companion Summoning Time Increase % WITHOUT the boots potential lines listed on PotentialCubes (Arwen's Glass Shoes, when equipped, included)"
    )).font = LABEL_FONT
    ws.cell(row=r_b0, column=2, value=f'=MAX(0,{IB("companion_summon_time_increase_pct")}-({own_lines}))+{art_ref("arwens_glass_shoes_summon_time_increase_pct")}')
    ws.cell(row=COMPANION_FIRST_ROW - 2, column=COMPANION_POT_FIRST_COL, value="Summoning Time Increase % = b0 + X, X (the header) =").font = LABEL_FONT
    for x, col_idx in ([] if os.environ.get('COMP_LIGHT') else COMPANION_POT_COL.items()):
        col = get_column_letter(col_idx)
        ws.cell(row=COMPANION_FIRST_ROW - 1, column=col_idx, value=x).font = LABEL_FONT
        host_x = dict(host)
        host_x["inc"] = f"($B${r_b0}+{col}${COMPANION_FIRST_ROW - 1})"

        def write_x(nm, _label, formula, col=col):
            ws[f"{col}{COMPANION_ROW_OF[nm]}"] = formula

        cm.emit(cm.cells(host_x), lambda nm, col=col: f"{col}{COMPANION_ROW_OF[nm]}", write_x)

    # Exported host values for potential_cubes_ev.py's Python mirror of the companion model
    ws.cell(row=COMPANION_HOST_FIRST_ROW - 1, column=1, value="Host values (read by potential_cubes_ev.py's Python mirror - do not edit)").font = LABEL_FONT
    for i, (key, expr) in enumerate(companion_host_export()):
        ws.cell(row=COMPANION_HOST_FIRST_ROW + i, column=1, value=key)
        ws.cell(row=COMPANION_HOST_FIRST_ROW + i, column=2, value="=" + expr)
    ws.column_dimensions["A"].width = 88
    ws.column_dimensions["B"].width = 20
    ws.freeze_panes = "C5"
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
    ("status_effect_damage", "STATUS_EFFECT_DAMAGE %", "pct"),
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
    ("companion_summon_time_increase_pct", "Companion Summoning Time Increase %", "pct"),
    ("incoming_hit_rate", "Incoming Hit Rate (hits/sec, Shadow Shifter only)", "flat"),
] + [
    (f"{art_key}_equipped", f"{art_label} (Equip)", "bool")
    for art_key, art_label in ARTIFACT_LABELS.items()
]

# Split for the Sensitivity sheet's two results tables (see build_sensitivity_sheet): continuous
# stats (where "Units per +1% DPS" is meaningful) get the full "Stat" table, boolean artifact
# equip-toggles get their own simpler "Artifact Equip-Toggle DPS Gain" table, per the user (units
# per 1% DPS is meaningless for a toggle). Every entry still gets its own full shadow calc block
# regardless of which table displays it — only the results-table presentation is split.
STAT_SWEEP_STAT_ENTRIES = [e for e in STAT_SWEEP if e[2] != "bool"]
STAT_SWEEP_ARTIFACT_ENTRIES = [e for e in STAT_SWEEP if e[2] == "bool"]
# Rows the 2nd table's own structure needs between the two tables: its section title + its own
# header row (see build_sensitivity_sheet's artifact_title_row/artifact_header_row).
SENSITIVITY_ARTIFACT_TABLE_HEADER_ROWS = 2

# Absolute CDR values (seconds) swept by the Sensitivity sheet's CDR Milestone Sweep section
# (see build_sensitivity_sheet).
CDR_SWEEP_VALUES = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]

SENSITIVITY_HEADER_ROW = 4
SENSITIVITY_ROW_FOR = {key: SENSITIVITY_HEADER_ROW + 1 + idx for idx, (key, _, _) in enumerate(STAT_SWEEP_STAT_ENTRIES)}

# Row constants for the Sensitivity sheet's 2nd ("Artifact Equip-Toggle DPS Gain") table, derived
# the same way build_sensitivity_sheet computes them locally — shared here so build_summary_sheet
# can reference the same (sorted) rows without duplicating the row math or risking it drifting out
# of sync.
ARTIFACT_TABLE_TITLE_ROW = SENSITIVITY_HEADER_ROW + len(STAT_SWEEP_STAT_ENTRIES) + 1
ARTIFACT_TABLE_HEADER_ROW = ARTIFACT_TABLE_TITLE_ROW + 1
ARTIFACT_TABLE_FIRST_DATA_ROW = ARTIFACT_TABLE_HEADER_ROW + 1
ARTIFACT_TABLE_LAST_DATA_ROW = ARTIFACT_TABLE_HEADER_ROW + len(STAT_SWEEP_ARTIFACT_ENTRIES)

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
    "Basic Attack Damage %": "basic_attack_damage",
    "Skill Damage %": "skill_damage",
    "Skill Cooldown Decrease (seconds)": "skill_cooldown_decrease",
    "Buff Duration Increase %": "buff_duration_increase_pct",
    "All Skill Level": "skill_lvl_all",
    "Basic Attack Target Increase": "basic_attack_target_increase",
    "Luk %": "luk_pct",
    "Luk": "flat_luk",
    "Dex": "dex",
}

# Sub-stat PERCENT potential lines: the Sensitivity sweep for the sub-stat is a flat +1 point, so a
# "+N% sub-stat" roll is worth N% of the current total sub-stat in points (approximation: Inputs holds the
# final sub-stat value, no separate flat/% split). Main-stat lines map 1:1 above.
POTENTIAL_SUB_STAT_PCT_LINES = {"Dex %": ("dex", "dex")}


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
        # Once Crit Rate is at/above the 100% cap, substitute Critical Damage's own DPS-per-unit
        # value (confirmed by the user) — UNLESS Ring of Cycles or Book of Ancient is equipped,
        # since both have their own dependent mechanic that keeps scaling with raw Crit Rate even
        # past 100% (see build_fp_mage_workbook.py's own copy of this branch for the full
        # reasoning) — in that case just use the literal Sensitivity!H value directly, like any
        # other stat.
        return (
            f'=IF(AND({IB("crit_rate")}+Summary!$B${R_CRIT_RATE_BONUS}+{art_ref("AGG_CRIT_RATE")}>=100,'
            f'NOT({IB("ring_of_cycles_equipped")}),NOT({IB("book_of_ancient_equipped")})),'
            f'Sensitivity!H{SENSITIVITY_ROW_FOR["crit_damage"]},'
            f'Sensitivity!H{SENSITIVITY_ROW_FOR["crit_rate"]})'
        )
    if stat_name == "Companion Summoning Time Increase %":
        # Live now (src/companion_model.py).  If no companion is chosen for the content type the stat is genuinely worthless there (0).
        # Real value is a step function of the TOTAL summoning time (the cube EV script re-runs the model in Python at b0 + total); this
        # linear stand-in is the average DPS per 1% over a +20% roll (a mystic line), for the sheet's display columns only.
        _bl = COMPANION_ROW_OF["comp_blend_dps"]
        _c20, _c0 = get_column_letter(COMPANION_POT_COL[20]), get_column_letter(COMPANION_POT_COL[0])
        return (f'=(Summary!$B${R_TOTAL}-Companion!$B${_bl}+Companion!${_c0}${_bl})*({companion_weighted_ratio(_c20, _c0)}-1)/20')
    if stat_name in POTENTIAL_SUB_STAT_PCT_LINES:
        sweep_key, inputs_key = POTENTIAL_SUB_STAT_PCT_LINES[stat_name]
        return f'=Sensitivity!H{SENSITIVITY_ROW_FOR[sweep_key]}*{IB(inputs_key)}/100'
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
    "SHADOW_SHIFTER_SELF_ATK": "final_damage",
}


def override_expr_for(kind, key):
    base = IB(key)
    if kind == "dr150":
        return f'((1-(1-{base}/150)*(1-1/150))*150)'
    if kind == "dr100":
        return f'((1-(1-{base}/100)*(1-1/100))*100)'
    if kind == "mult":
        return f'((((1+{base}/100)*(1.01))-1)*100)'
    if kind == "bool":
        # Equip-toggle test: always report "the value of having this equipped," in the same
        # positive direction regardless of current state (confirmed by the user — otherwise
        # already-equipped artifacts show a meaningless 0 while unequipped ones show their real
        # value, making them impossible to compare). Off->on if not currently equipped, on->off
        # if it is.
        return f'IF({base},FALSE,TRUE)'
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


BLOCK_HEIGHT = LAST_ROW + 21
# Companion comparison table (below the artifact table): one row per companion in the catalog.
COMPANION_TABLE_TITLE_ROW = ARTIFACT_TABLE_LAST_DATA_ROW + 2
COMPANION_TABLE_HEADER_ROW = COMPANION_TABLE_TITLE_ROW + 1
COMPANION_TABLE_FIRST_DATA_ROW = COMPANION_TABLE_HEADER_ROW + 1
COMPANION_TABLE_ROW = {name: COMPANION_TABLE_FIRST_DATA_ROW + i for i, name in enumerate(cm.COMPANIONS)}
COMPANION_TABLE_LAST_ROW = COMPANION_TABLE_FIRST_DATA_ROW + len(cm.COMPANIONS) - 1
# Companion cells inside a Sensitivity block: a column-major grid of single cells starting at column AD, rows = the block's
# own row span (base_row .. base_row + BLOCK_HEIGHT - 2).  Absolute, same-sheet refs.
COMPANION_BLOCK_COL0 = 30
COMPANION_NAME_INDEX = {name: i for i, name in enumerate(COMPANION_CELL_NAMES)}


def companion_block_ref(base_row, name):
    idx = COMPANION_NAME_INDEX[name]
    per = BLOCK_HEIGHT - 1
    return f"${get_column_letter(COMPANION_BLOCK_COL0 + idx // per)}${base_row + idx % per}"


# Summoning-time breakdown table (Breakthrough / Hero Dungeon boss phase), one row per total the boots lines can add up to
COMPANION_BREAKDOWN_TITLE_ROW = COMPANION_TABLE_LAST_ROW + 2
COMPANION_BREAKDOWN_HEADER_ROW = COMPANION_BREAKDOWN_TITLE_ROW + 1
COMPANION_BREAKDOWN_FIRST_ROW = COMPANION_BREAKDOWN_HEADER_ROW + 1
COMPANION_BREAKDOWN_LAST_ROW = COMPANION_BREAKDOWN_FIRST_ROW + len(COMPANION_POT_TOTALS) - 1
BLOCK_START = COMPANION_BREAKDOWN_LAST_ROW + 3
# Status/KO engine strips of the re-running blocks live below the last block (stat blocks, then the CDR milestone blocks)
STATUS_STRIPS_START = (BLOCK_START + len(STAT_SWEEP) * BLOCK_HEIGHT + 1 + len(CDR_SWEEP_VALUES) + 3
                       + len(CDR_SWEEP_VALUES) * BLOCK_HEIGHT + 5)
_status_strip_counter = [0]


def alloc_status_strip_row0(stat_key):
    if stat_key not in STATUS_REBUILD_KEYS:
        return None
    row0 = STATUS_STRIPS_START + _status_strip_counter[0] * (STATUS_STRIP_HEIGHT + 3)
    _status_strip_counter[0] += 1
    return row0


def mastery_final_block_expr(key, skills_row, row_of, ib):
    """A row's MasteryFinalDamage% inside a Sensitivity block.  Assassin's Mark's cell on the Skills sheet reads the MAIN Calc!F of Night Lord's Mark
    (_MARK_OF_ASSASSIN_FD), which a block sweeping a 4th-job skill level never saw move (CLAUDE.md bug 19): read this block's own Night Lord's Mark row instead."""
    if key == "MARK_OF_ASSASSIN":
        return f'IF({ib("level")}>=107,F{row_of["NIGHT_LORDS_MARK"]},0)'
    return S("MasteryFinalDamage%", skills_row)


def build_stat_block(ws, base_row, ib, stat_key, stat_label, override_expr, strip_row0=None):
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
    s_startup = calc_end + 14
    s_boss_total = calc_end + 15
    s_normal_total = calc_end + 16
    s_bucket = calc_end + 17         # block twin of the averaged Attack% bucket sum (in %)
    aps_pre_ref, adrenalin_uptime_ref = f"B{s_aps_pre}", f"B{s_adrenalin_uptime}"
    as_bonus_ref, aps_ref, castrate_ref = f"B{s_as_bonus}", f"B{s_aps}", f"B{s_castrate}"
    baps_ref = f"B{s_baps}"
    crit_rate_bonus_ref = f"B{s_crit_rate_bonus}"
    monster_dmg_bonus_ref, shadow_partner_mult_ref = f"B{s_monster_dmg_bonus}", f"B{s_shadow_partner_mult}"
    crit_damage_bonus_ref = f"B{s_crit_damage_bonus}"
    boss_total_ref, normal_total_ref = f"B{s_boss_total}", f"B{s_normal_total}"
    total_ref = f"B{s_total}"
    startup_ref = f"B{s_startup}"
    bucket_ref = f"$B${s_bucket}"
    avgbuff_ref = f"B{s_avgbuff}"

    fda_block = fixed_duration_active_expr(ib("monster_type"), ib("fight_duration"))
    # Shamaness Marble's Buff Duration Increase is baked into Inputs!buff_duration_increase_pct, so its equip what-if is a signed DELTA (shamaness_marble_delta_block,
    # defined below, written to this helper cell).  EVERY reader of the block's Buff Duration Increase goes through bdi_block (buff uptimes, Alchemic Adrenaline's
    # window, the strip's durations); until 2026-11-23 the delta was defined but never added, so the Shamaness row was inert (same gap as Corsair / Bowmaster).
    shamaness_bdi_cell = f"U{row_header + 8}"
    bdi_block = f'({ib("buff_duration_increase_pct")}+{shamaness_bdi_cell})'

    def buff_uptime_block(local_row, skills_row):
        return uptime_fraction_or_exact_expr(
            fda_block, f'R{local_row}', ib("monster_type"), S("BuffDuration(s)", skills_row),
            f'(1/Q{local_row})', bdi_block, ib("fight_duration"),
        )

    # Status/KO timeline engine: a block that moves cast times / buff windows / Hexagon stacks / the Status Effect Damage input re-runs its
    # own strip (placed below every block on this sheet, local refs); every other block reads the main sheet's strip.
    if strip_row0 is not None and stat_key in STATUS_REBUILD_KEYS:
        lay = stl.Layout(stl.cells(_STATUS_DUMMY_HOST), strip_row0, 1)
    else:
        lay = STATUS_MAIN_LAYOUT
    st_on = lay.s("on")

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
        "attack_speed", "basic_attack_damage", "min_damage", "max_damage", "crit_rate",
        "crit_damage", "boss_damage", "skill_damage", "final_damage", "def_pen", "attack_mult",
    )}

    # Flat ATTACK is assumed to already include the character's current LUK/DEX-derived attack
    # (1 total LUK = 1 flat Attack, 1 DEX = 0.25 flat Attack, added into the pool before ATTACK%
    # applies) — same "already baked into Inputs, only the Sensitivity marginal delta matters"
    # pattern used elsewhere in this block. Identically 0 for every block except the ones sweeping
    # flat_luk/luk_pct/dex.
    mainstat_attack_delta = (
        f'((({ib("flat_luk")}*(1+{ib("luk_pct")}/100))-({IB("flat_luk")}*(1+{IB("luk_pct")}/100)))'
        f'+0.25*({ib("dex")}-{IB("dex")}))'
    )

    # Artifacts — block-local mirror of build_artifacts_sheet, so a swept stat correctly
    # propagates through whichever artifact depends on it (Book of Ancient/Ring of Cycles via
    # Crit Rate, Athena's Gloves via Attack Speed, Peach Tree/Silver Pendant via Actions Per
    # Second), and so each artifact's own equip-toggle STAT_SWEEP test ("what if I equipped
    # this") correctly reflects adding its bonus. Book of Ancient/Athena's Gloves' own direct stat
    # bonus is assumed already baked into Inputs!crit_rate/attack_speed (see the "baked into
    # Inputs" convention) — only a DELTA is needed here, identically 0 except when that specific
    # artifact's own equip-toggle is being tested (ib(...)-IB(...) is 0 unless this block's
    # override just flipped it from FALSE to TRUE).
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
    roc_threshold_cr_block = f'({ib("crit_rate")}+{delta["crit_rate"]}+{crit_rate_bonus_ref}+{boa_direct_delta}+{rainbow_crit_rate_block})'
    roc_crit_rate_block, roc_skill_dmg_block, roc_basic_atk_dmg_block = artifact_ring_of_cycles_exprs(
        ib("ring_of_cycles_equipped"), ib("ring_of_cycles_star"), roc_threshold_cr_block,
        ib("monster_type"), ib("fight_duration"), startup_ref,
    )
    # Book of Ancient's dependent Crit-Damage-from-Crit-Rate bonus is also assumed already baked
    # into Inputs!crit_damage FOR WHATEVER CRIT RATE IS CURRENTLY EQUIPPED WITH — but Sensitivity
    # must still show its knock-on effect. Three cases: Book's own equip-toggle block adding
    # (currently unequipped) uses the FULL resulting total Crit Rate; Book's own equip-toggle
    # block removing (currently equipped) strips the amount using the REAL crit rate that actually
    # produced today's baked-in value; every other block only adds the MARGINAL crit rate its own
    # override introduced.
    if stat_key == "book_of_ancient_equipped":
        _boa_crit_rate_add_case = f'({ib("crit_rate")}+{delta["crit_rate"]}+{crit_rate_bonus_ref}+{boa_direct_delta}+{roc_crit_rate_block}+{rainbow_crit_rate_block})'
        _boa_crit_rate_remove_case = f'({IB("crit_rate")}+Summary!$B${R_CRIT_RATE_BONUS}+{art_ref("roc_crit_rate")}+{art_ref("rainbow_crit_rate")})'
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
    attack_speed_total_block = f'({ib("attack_speed")}+{delta["attack_speed"]}+{athena_direct_delta})'
    # Athena Pierce's Old Gloves' dependent Max-Damage-from-Attack-Speed bonus — same direction-
    # aware treatment as Book of Ancient's Crit Damage above. No other artifact grants raw Attack
    # Speed, so the "remove" case's reference is the real, frozen IB("attack_speed") (the value
    # that actually produced today's baked-in Inputs!max_damage) — no art_ref needed.
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

    # Clear Spring Water / Soul Pouch — baked into Inputs when equipped; each is a flat,
    # content-type-gated value with no dependency on any OTHER swept stat, so a single toggle-delta
    # (0 everywhere except that artifact's own equip-toggle block) suffices.
    # The Final Damage a baked-in artifact grants is typed into Inputs!final_damage, i.e. it MULTIPLIES everything else (K carries (1+final_damage/100)*(1+bucket/100)).
    # So its what-if is a FACTOR on the whole product, in both directions: adding multiplies by (1 + x/100), removing by 1/(1 + x/100) - exact inverses (CLAUDE.md
    # item 15).  The first version put +x / -x inside the additive artifact bucket: removal read (1 + x/100) times the adding gain, and with a live Final Damage
    # artifact (Candle / Flaming Lava / Horn Flute: bucket a = 1 + L/100 > 1) adding read (a + x/100)/a instead of 1 + x/100.  The factor is applied to the live
    # bucket: bucket_block = ((1 + L/100) * product of the factors - 1) * 100.
    # fd_live_cell / agg_fd_cell are block-local helper cells (column U, 6th / 7th skill row; also keeps the long expressions out of every K formula).
    fd_live_cell, agg_fd_cell = f"U{row_header + 6}", f"U{row_header + 7}"

    def fd_baked_factor(eq_after, eq_base, magnitude):
        """Multiplicative what-if factor of a baked-in Final Damage artifact: 1 + x/100 when this block equips it, 1/(1 + x/100) when it unequips it, 1 elsewhere."""
        step = f'({eq_after}-{eq_base})'
        return f'IF({step}>0,1+({magnitude})/100,IF({step}<0,1/(1+({magnitude})/100),1))'
    csw_factor_block = fd_baked_factor(
        ib("clear_spring_water_equipped"), IB("clear_spring_water_equipped"),
        f'IF({_growth_dungeon_gate_expr(ib("content_type"))},{star_lookup_expr(ib("clear_spring_water_star"), "clear_spring_water_final_damage")},0)',
    )
    soul_pouch_factor_block = fd_baked_factor(
        ib("soul_pouch_equipped"), IB("soul_pouch_equipped"),
        f'IF({ib("monster_type")}="pvp",{star_lookup_expr(ib("soul_pouch_star"), "soul_pouch_final_damage")},0)',
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
    # Reindeer's Spear's base (1x) Defense Penetration is baked into Inputs!def_pen, on top of
    # whatever this block's own live delta contributes. Defense Penetration combines like Attack
    # Speed — diminishing-returns (new = 1-(1-old)*(1-inc)), never additive. This shadow block's
    # baseline may need one extra "dose" of the spear's own contribution combined in via that
    # formula: whenever this IS the reindeer_spear_equipped block's own +1 test AND the spear isn't
    # really currently equipped. Every other block's ib(equipped) == IB(equipped) unchanged, so
    # this always evaluates to 0 there.
    reindeer_spear_base_ref_block = artifact_reindeer_spear_base_def_pen_reference_expr(
        ib("reindeer_spear_equipped"), ib("reindeer_spear_star"),
    )
    _reindeer_star_magnitude = star_lookup_expr(ib("reindeer_spear_star"), "reindeer_spear_def_pen")
    _reindeer_extra_dose_block = f'({ib("reindeer_spear_equipped")}-{IB("reindeer_spear_equipped")})'
    def_pen_total_block = (
        f'(100*(1-(1-({ib("def_pen")}+{delta["def_pen"]})/100)*(1-{_reindeer_star_magnitude}/100)^{_reindeer_extra_dose_block}))'
    )

    cursed_doll_factor_block = fd_baked_factor(
        ib("cursed_doll_equipped"), IB("cursed_doll_equipped"),
        star_lookup_expr(ib("cursed_doll_star"), "cursed_doll_final_damage"),
    )
    horn_flute_block = artifact_horn_flute_expr(
        ib("horn_flute_equipped"), ib("content_type"), ib("horn_flute_star"), companion_block_ref(base_row, "horn_uptime"),
    )
    bottle_of_emotion_attack_pct_block = artifact_bottle_of_emotion_attack_pct_expr(
        ib("bottle_of_emotion_equipped"), ib("bottle_of_emotion_star"),
    )
    # Bottle of Emotion's Attack-Speed-dependent Final Damage — baked into Inputs!final_damage.
    # Bottle doesn't grant Attack Speed itself, so only the dependent bonus itself needs a
    # direction-aware sign flip, evaluated at the real current Attack Speed in both directions.
    if stat_key == "bottle_of_emotion_equipped":
        _boe_magnitude = artifact_bottle_of_emotion_final_damage_value_expr(
            "TRUE", ib("bottle_of_emotion_star"), IB("attack_speed"),
        )
        # same inverse-step rule as the other baked-in Final Damage artifacts (see fd_baked_factor); the toggle always reads the real Attack Speed
        bottle_of_emotion_factor_block = fd_baked_factor(
            ib("bottle_of_emotion_equipped"), IB("bottle_of_emotion_equipped"), _boe_magnitude,
        )
    else:
        _boe_new = artifact_bottle_of_emotion_final_damage_value_expr(
            ib("bottle_of_emotion_equipped"), ib("bottle_of_emotion_star"), ib("attack_speed"),
        )
        _boe_baseline = artifact_bottle_of_emotion_final_damage_value_expr(
            ib("bottle_of_emotion_equipped"), ib("bottle_of_emotion_star"), IB("attack_speed"),
        )
        # a changed Attack Speed moves the (typed) Bottle value from _boe_baseline to _boe_new: a multiplicative factor on the product, like every Final Damage source
        bottle_of_emotion_factor_block = f'((1+{_boe_new}/100)/(1+{_boe_baseline}/100))'
    alliance_badge_block = artifact_alliance_badge_expr(ib("alliance_badge_equipped"), ib("alliance_badge_star"))
    sayrams_normal_block, sayrams_boss_block = artifact_sayrams_necklace_exprs(
        ib("sayrams_necklace_equipped"), ib("sayrams_necklace_star"),
    )
    lit_lamp_factor_block = fd_baked_factor(
        ib("lit_lamp_equipped"), IB("lit_lamp_equipped"),
        f'IF({ib("content_type")}="World Boss",{star_lookup_expr(ib("lit_lamp_star"), "lit_lamp_final_damage")},0)',
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

    # Aggregate bucket totals — block-local mirror of the Artifacts sheet's AGG_* rows.
    agg_crit_rate_block = f'({roc_crit_rate_block}+{rainbow_crit_rate_block})'
    agg_crit_damage_block = f'({boa_crit_damage_delta}+{rainbow_crit_damage_block}+{icy_soul_rock_block})'
    fd_live_formula = f'=((1+{candle_final_dmg_block}/100)*(1+{flaming_lava_block}/100)*(1+{horn_flute_block}/100)-1)*100'
    agg_fd_formula = (
        f'=((1+{fd_live_cell}/100)*{csw_factor_block}*{soul_pouch_factor_block}*{cursed_doll_factor_block}*{lit_lamp_factor_block}'
        f'*{bottle_of_emotion_factor_block}-1)*100'
    )
    agg_final_damage_block = agg_fd_cell      # (helper cell: live Final Damage bucket x the baked-in what-if factor, written below)
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
    # Reindeer's Spear's extra boss/PvP-only Defense Penetration correction ratio — row-independent
    # (doesn't need L/M), so computed once here; composed with the row-dependent Contract of
    # Darkness crit-blend ratio inside the per-row loop below (see boss_dmg_pct_row).
    spear_extra_mult_block = artifact_reindeer_spear_extra_mult_expr(ib("monster_type"))
    _def_pen_boss_block = (
        f'(100*(1-(1-{def_pen_total_block}/100)*(1-{reindeer_spear_base_ref_block}/100)^{spear_extra_mult_block}))'
    )
    spear_def_ratio_block = (
        f'((5000/(6000+{ib("monster_defense")}*(1-{_def_pen_boss_block}/100)))'
        f'/(5000/(6000+{ib("monster_defense")}*(1-{def_pen_total_block}/100))))'
    )
    extra_normal_mult_block = f'(1+{agg_final_damage_normal_only_block}/100)'

    r_dsa = ROW["DARK_SIGHT_ATK"]
    r_fcs = ROW["FRAILTY_CURSE_SELF_FD"]
    dark_sight_atk_avg = f'((C{row_of["DARK_SIGHT_ATK"]}=TRUE)*F{row_of["DARK_SIGHT_ATK"]}*{buff_uptime_block(row_of["DARK_SIGHT_ATK"], r_dsa)})'
    frailty_self_fd_avg = f'((C{row_of["FRAILTY_CURSE_SELF_FD"]}=TRUE)*F{row_of["FRAILTY_CURSE_SELF_FD"]}*{buff_uptime_block(row_of["FRAILTY_CURSE_SELF_FD"], r_fcs)})'
    adrenalin_fd_avg = f'((C{row_of["ADRENALIN_FD"]}=TRUE)*F{row_of["ADRENALIN_FD"]}*{adrenalin_uptime_ref})'
    # ATTACK% bucket: Dark Sight Attack's own live percentage sums with the delta-only Attack%
    # passives (Expert Throwing Star Handling, Shadow Shifter Self Atk) and every Attack%-granting
    # artifact into ONE combined percentage before a single multiplication — same bucket (skill/
    # buff/artifact-sourced Attack%), distinct from Inputs!attack_pct (gear Attack%), which stays
    # its own separate multiplicative factor elsewhere. Final Damage% (Frailty Curse self-FD,
    # Adrenalin FD) is a deliberate exception to this rule — every Final Damage source stays its
    # own multiplicative factor, so it is NOT folded into this sum.
    attack_bucket_block = f'(1+({dark_sight_atk_avg}+{delta["attack_mult"]}+{agg_attack_pct_block})/100)'
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
    ws[fd_live_cell] = fd_live_formula
    ws[agg_fd_cell] = agg_fd_formula
    ws[shamaness_bdi_cell] = f'={shamaness_marble_delta_block}'

    FULL_HIT_PIPELINE_KEYS = ["SHOWDOWN"] + DAMAGE_ROW_KEYS + TOXIC_VENOM_ROW_KEYS + SHADOW_SHIFTER_ROW_KEYS

    for key, r in ROW.items():
        _LAST_SPLIT[0] = None
        row = row_of[key]
        ws.cell(row=row, column=1, value=f"={S('Key', r)}")
        ws.cell(row=row, column=2, value=f"={S('Name', r)}")
        ws.cell(row=row, column=3, value=unlock_expr(key))

        has_cooldown = ROW_HAS_COOLDOWN[key]
        if has_cooldown:
            # Soul Contract's Chapter-Hunt-only cooldown decrease (CLAUDE.md item 11): same multiplicative wrapper as the main Calc sheet's call site (it was
            # missing here: a Sensitivity block never saw the artifact's cooldown cut).
            eff_cd_row = (
                f'({effective_cooldown_expr(ib("monster_type"), S("Cooldown(s)", r), ib("skill_cooldown_decrease"), cdr_applies_expr(key))}'
                f'*(1-{artifact_soul_contract_pct_expr(ib("soul_contract_equipped"), ib("content_type"), ib("soul_contract_star"))}/100))'
            )
            if key in BUFF_ROW_KEYS:
                available_duration_row = ib("fight_duration")
            else:
                available_duration_row = f'MAX(0,{ib("fight_duration")}-{startup_ref})'
            rate_row = rate_or_exact_hits_expr(
                fda_block, f"R{row}", S("HitsPerCast", r), S("ICD(s)", r), S("ActiveWindow(s)", r),
                eff_cd_row, available_duration_row, ib("fight_duration"), f"G{row}*Q{row}",
            )
            if key in STATUS_FS_KEYS:
                rate_row = f'IF({st_on}=1,G{row}*{lay.s("fs." + key)}/{ib("fight_duration")},{rate_row})'
        else:
            eff_cd_row = None
            rate_row = None
            available_duration_row = None

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
            ws.cell(row=row, column=10, value=(
                f'=({ib("attack")}+{mainstat_attack_delta}*(1+{ib("attack_pct")}/100))*(F{row}/100)'
            ))
            max_damage_total_block = f'({ib("max_damage")}+{delta["max_damage"]}+{agg_max_damage_block})'
            crit_rate_full_block = f'({ib("crit_rate")}+{delta["crit_rate"]}+{crit_rate_bonus_ref}+{boa_direct_delta}+{agg_crit_rate_block})'
            avgbuff_with_deltas = f'({avgbuff_ref})'
            ws.cell(row=row, column=11, value=(
                f'=J{row}*(1+{ib("stat_damage")}/100)*(1+{ib("damage")}/100)'
                f'*(1+{ib("damage_amp")}/100)'
                f'*(5000/(6000+{ib("monster_defense")}*(1-{def_pen_total_block}/100)))'
                f'*(1+({ib("final_damage")}+{delta["final_damage"]})/100)*(1+{mastery_final_block_expr(key, r, row_of, ib)}/100)*(1+{agg_final_damage_block}/100)'
                f'*(1+(IF({S("Key", r)}="SHOWDOWN",{ib("basic_attack_damage")}+{delta["basic_attack_damage"]}+{agg_basic_attack_damage_block},'
                f'{ib("skill_damage")}+{delta["skill_damage"]}+{agg_skill_damage_block}))/100)'
                f'*({avgbuff_with_deltas}*{shadow_partner_mult_ref}*(1+{agg_damage_block}/100)*I{row})'
            ))
            ws.cell(row=row, column=12, value=(
                f'=K{row}*(MIN({ib("min_damage")}+{delta["min_damage"]},{max_damage_total_block})/100'
                f'+{max_damage_total_block}/100)/2'
            ))
            ws.cell(row=row, column=13, value=f'=L{row}*(1+({ib("crit_damage")}+{delta["crit_damage"]}+{crit_damage_bonus_ref}+{agg_crit_damage_block})/100)')
            ws.cell(row=row, column=14, value=(
                f'=L{row}*(1-MIN({crit_rate_full_block},100)/100)+M{row}*(MIN({crit_rate_full_block},100)/100)'
            ))
        else:
            for col in (10, 11, 12, 13, 14):
                ws.cell(row=row, column=col, value="")

        boss_dmg_pct_row = (
            f'{ib("boss_damage")}+{delta["boss_damage"]}+{S("MasteryBossDamage%", r)}+{monster_dmg_bonus_ref}'
            f'+{agg_boss_damage_block}+{agg_enemy_dmg_taken_block}'
        )
        normal_dmg_pct_row = (
            f'{ib("normal_damage")}+{S("MasteryNormalDamage%", r)}+{monster_dmg_bonus_ref}'
            f'+{agg_normal_damage_block}+{agg_enemy_dmg_taken_block}'
        )

        # The Contract of Darkness's boss-branch-only Crit Rate, via a crit-blend ratio correction
        # using THIS row's own L/M cells (only valid for FULL_HIT_PIPELINE_KEYS rows, where
        # crit_rate_full_block was just freshly set above).
        if key in FULL_HIT_PIPELINE_KEYS:
            _cr_baseline_block = f'MIN(100,{crit_rate_full_block})'
            _cr_boss_block = f'MIN(100,{crit_rate_full_block}+{contract_of_darkness_crit_rate_block})'
            cod_crit_ratio_block = (
                f'((L{row}*(1-{_cr_boss_block}/100)+M{row}*({_cr_boss_block}/100))'
                f'/(L{row}*(1-{_cr_baseline_block}/100)+M{row}*({_cr_baseline_block}/100)))'
            )
            extra_boss_mult_block = (
                f'({spear_def_ratio_block}*{cod_crit_ratio_block}*(1+{agg_final_damage_boss_only_block}/100))'
            )
        else:
            extra_boss_mult_block = "1"

        # Per-cast boss damage before any timing factor (engine weights; free of cast counts)
        if key == "SHOWDOWN":
            basic_targets_expr = f'(6+{ib("basic_attack_target_increase")})'
            basic_extra_boss_block = extra_boss_mult_block   # the Companion cells reuse the Showdown row's boss composition
            ws.cell(row=row, column=25, value=f"=IF(C{row}," + boss_normal_dps_split_exprs(
                f"{S('HitsPerCast', r)}*N{row}", ib("monster_type"), boss_dmg_pct_row, normal_dmg_pct_row,
                basic_targets_expr, ib("max_enemies_hit"), extra_boss_mult_block, extra_normal_mult_block)[0] + ",0)")
        elif key in STATUS_PERCAST_KEYS:
            ws.cell(row=row, column=25, value=f"=IF(C{row}," + boss_normal_dps_split_exprs(
                f"H{row}*N{row}*G{row}", ib("monster_type"), boss_dmg_pct_row, normal_dmg_pct_row,
                S("NormalMonsterTargets", r), ib("max_enemies_hit"), extra_boss_mult_block, extra_normal_mult_block)[0] + ",0)")

        if key == "SHOWDOWN":
            prefix = f"{S('HitsPerCast', r)}*N{row}*{baps_ref}"
            boss_expr, normal_expr = boss_normal_dps_split_exprs(
                prefix, ib("monster_type"), boss_dmg_pct_row, normal_dmg_pct_row,
                basic_targets_expr, ib("max_enemies_hit"),
                extra_boss_mult_block, extra_normal_mult_block,
            )
            ws.cell(row=row, column=20, value=f'=IF(C{row},{boss_expr},0)')
            ws.cell(row=row, column=22, value=f'=IF(C{row},{normal_expr},0)')
        elif key in DAMAGE_ROW_KEYS:
            prefix = f'H{row}*N{row}*{rate_row}'
            boss_expr, normal_expr = boss_normal_dps_split_exprs(
                prefix, ib("monster_type"), boss_dmg_pct_row, normal_dmg_pct_row,
                S("NormalMonsterTargets", r), ib("max_enemies_hit"),
                extra_boss_mult_block, extra_normal_mult_block,
            )
            ws.cell(row=row, column=20, value=f'=IF(C{row},{boss_expr},0)')
            ws.cell(row=row, column=22, value=f'=IF(C{row},{normal_expr},0)')
        elif key in TOXIC_VENOM_ROW_KEYS:
            total_hit_rate = (
                f'SUMPRODUCT((Skills!{SC["TriggersToxicVenom"]}2:{SC["TriggersToxicVenom"]}{LAST_ROW}=TRUE)*'
                f'(C{calc_start}:C{calc_end}=TRUE)*S{calc_start}:S{calc_end})'
            )
            prefix = f'0.2*{total_hit_rate}*N{row}'
            boss_expr, normal_expr = boss_normal_dps_split_exprs(
                prefix, ib("monster_type"), boss_dmg_pct_row, normal_dmg_pct_row,
                S("NormalMonsterTargets", r), ib("max_enemies_hit"),
                extra_boss_mult_block, extra_normal_mult_block,
            )
            ws.cell(row=row, column=20, value=f'=IF(C{row},{boss_expr},0)')
            ws.cell(row=row, column=22, value=f'=IF(C{row},{normal_expr},0)')
        elif key in SHADOW_SHIFTER_ROW_KEYS:
            prefix = f'{ib("incoming_hit_rate")}*0.2*N{row}'
            boss_expr, normal_expr = boss_normal_dps_split_exprs(
                prefix, ib("monster_type"), boss_dmg_pct_row, normal_dmg_pct_row,
                S("NormalMonsterTargets", r), ib("max_enemies_hit"),
                extra_boss_mult_block, extra_normal_mult_block,
            )
            ws.cell(row=row, column=20, value=f'=IF(C{row},{boss_expr},0)')
            ws.cell(row=row, column=22, value=f'=IF(C{row},{normal_expr},0)')
        else:
            ws.cell(row=row, column=20, value=0)
            ws.cell(row=row, column=22, value=0)

        ws.cell(row=row, column=15, value=f'=(1-{ib("normal_weight_frac")})*T{row}+{ib("normal_weight_frac")}*V{row}')

        ws.cell(row=row, column=16, value=f'=IF({total_ref}=0,0,O{row}/{total_ref})')

        # Q/R/S match the main Calc sheet's own column layout exactly (InvCooldown/CastsInFight/
        # HitRate(perSec)) — same header labels from CALC_HEADERS above, columns 17-19.
        ws.cell(row=row, column=17, value=(f'=IFERROR(1/{eff_cd_row},0)' if has_cooldown else 0))
        if has_cooldown:
            casts_formula_block = guarded_casts_expr(available_duration_row, eff_cd_row)
            ws.cell(row=row, column=18, value=f'=IF({fda_block},{casts_formula_block},0)')
        else:
            ws.cell(row=row, column=18, value=0)
        # Same circular-reference fix as build_calc_sheet's own S column — Toxic Venom's row is
        # hardcoded to literal 0 (never =O/N) to avoid a genuine cycle through its own O formula.
        if key in TOXIC_VENOM_ROW_KEYS:
            ws.cell(row=row, column=19, value=0)
        else:
            ws.cell(row=row, column=19, value=hit_count_s_expr(row, ib("normal_weight_frac"), S("HitsPerCast", r)))

    _ph_block = phase_state_ratios(
        ib("content_type"), ib("fight_duration"),
        f'IF({ib("hexagon_necklace_equipped")},{star_lookup_expr(ib("hexagon_necklace_star"), "hexagon_necklace_damage")},0)',
        hexagon_dmg_block, bucket_ref,
        f'IF({ib("charm_of_the_undead_equipped")},{star_lookup_expr(ib("charm_of_the_undead_star"), "charm_of_the_undead_attack_pct")},0)',
        charm_of_the_undead_block,
    )
    apply_status_columns(
        ws, row_of, lay, st_on,
        f'(1+{ib("status_effect_damage")}/100*{companion_block_ref(base_row, "stunfracB")})*({_ph_block[0]})',
        f'(1+{ib("status_effect_damage")}/100*{companion_block_ref(base_row, "stunfracN")})*({_ph_block[1]})',
    )

    r_nf, r_dsc = ROW["NIMBLE_FEET"], ROW["DARK_SIGHT_CRIT"]
    r_fcd = ROW["FRAILTY_CURSE_DEBUFF"]
    r_afd, r_aas = ROW["ADRENALIN_FD"], ROW["ADRENALIN_AS"]
    r_sp = ROW["SHADOW_PARTNER"]

    # Same Unlocked-gate fix as build_summary_sheet — local C column, not Calc!C, since this
    # block has its own per-row copy of every Calc column.
    nimble_feet_avg = f'((C{row_of["NIMBLE_FEET"]}=TRUE)*F{row_of["NIMBLE_FEET"]}*{buff_uptime_block(row_of["NIMBLE_FEET"], r_nf)})'
    dark_sight_crit_avg = f'((C{row_of["DARK_SIGHT_CRIT"]}=TRUE)*F{row_of["DARK_SIGHT_CRIT"]}*{buff_uptime_block(row_of["DARK_SIGHT_CRIT"], r_dsc)})'
    frailty_debuff_avg = f'((C{row_of["FRAILTY_CURSE_DEBUFF"]}=TRUE)*F{row_of["FRAILTY_CURSE_DEBUFF"]}*{buff_uptime_block(row_of["FRAILTY_CURSE_DEBUFF"], r_fcd)})'

    ws.cell(row=s_aps_pre, column=1, value="Actions Per Second (pre-Adrenalin)")
    ws.cell(row=s_aps_pre, column=2, value=(
        f'=1+MIN(150,150*(1-(1-{attack_speed_total_block}/150)*(1-{nimble_feet_avg}/150)))/100'
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
        f'=1+MIN(150,150*(1-(1-{attack_speed_total_block}/150)*(1-{as_bonus_ref}/150)))/100'
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

    ws.cell(row=s_bucket, column=1, value="Averaged Attack% bucket sum (%) - Dark Sight (Attack) + passives + artifacts")
    ws.cell(row=s_bucket, column=2, value=f'={dark_sight_atk_avg}+{delta["attack_mult"]}+{agg_attack_pct_block}')
    ws.cell(row=s_avgbuff, column=1, value="Average Buff Multiplier")
    ws.cell(row=s_avgbuff, column=2, value=f'=IF({st_on}=1,{lay.s("Bbuff_mean")}*(1+{adrenalin_fd_avg}/100),{attack_bucket_block}*{final_damage_bucket_block})')

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

    comp_ref = lambda name: companion_block_ref(base_row, name)
    ws.cell(row=s_total, column=1, value="TOTAL DPS").font = LABEL_FONT
    ws.cell(row=s_total, column=2, value=(
        f'=SUM(O{calc_start}:O{calc_end})+(1-{ib("normal_weight_frac")})*{comp_ref("comp_boss_dps")}'
        f'+{ib("normal_weight_frac")}*{comp_ref("comp_norm_dps")}'
    )).font = LABEL_FONT

    ws.cell(row=s_startup, column=1, value="Buff-Casting Startup Delay (s, fixed-duration only)")
    ws.cell(row=s_startup, column=2, value=f'=IF({st_on}=1,0,' + buff_cast_startup_time_expr(
        fda_block, SC["BuffDuration(s)"], SC["CostsActionSlot"], f"C{calc_start}:C{calc_end}",
        aps_ref, LAST_ROW,
    ) + ")")

    ws.cell(row=s_boss_total, column=1, value="Boss-Only Total DPS (this block's swept value)")
    ws.cell(row=s_boss_total, column=2, value=f"=SUM(T{calc_start}:T{calc_end})+{comp_ref('comp_boss_dps')}")
    ws.cell(row=s_normal_total, column=1, value="Normal-Only Total DPS (this block's swept value)")
    ws.cell(row=s_normal_total, column=2, value=f"=SUM(V{calc_start}:V{calc_end})+{comp_ref('comp_norm_dps')}")

    for _key, _r in ROW.items():   # same mastery semantics as the main Calc sheet
        ws.cell(row=row_of[_key], column=6).value = apply_mastery_semantics(_key, _r, ws.cell(row=row_of[_key], column=6).value)

    # Companion: block-local copy of the Companion sheet's cells (every reference resolves inside this block, bugs #6/#19)
    b_row = row_of["SHOWDOWN"]
    _bt = buff_snapshot_terms(lambda letter, key: f"{letter}{row_of[key]}", adrenalin_uptime_ref)
    _k1_block = f'({_bt["ds_full"]}+{delta["attack_mult"]}+{agg_attack_pct_block}-{charm_of_the_undead_block})'
    _fdpart_block = f'((1+{_bt["fc_full"]}/100)*(1+{_bt["adr_avg"]}/100))'
    _boss_pct_block = f'({ib("boss_damage")}+{delta["boss_damage"]}+{agg_boss_damage_block}+{monster_dmg_bonus_ref}+{agg_enemy_dmg_taken_block})'
    _norm_pct_block = f'({ib("normal_damage")}+{agg_normal_damage_block}+{monster_dmg_bonus_ref}+{agg_enemy_dmg_taken_block})'
    _charm_val_block = f'IF({ib("charm_of_the_undead_equipped")},{star_lookup_expr(ib("charm_of_the_undead_star"), "charm_of_the_undead_attack_pct")},0)'
    _hex_v_block = f'IF({ib("hexagon_necklace_equipped")},{star_lookup_expr(ib("hexagon_necklace_star"), "hexagon_necklace_damage")},0)'
    block_host = {
        "choice": ib("companion_choice"),
        "inc": companion_summon_time_inc_expr(
            ib("companion_summon_time_increase_pct"),
            artifact_arwens_glass_shoes_expr(ib("arwens_glass_shoes_equipped"), ib("arwens_glass_shoes_star"))),
        "lvl": companion_level_lookup_expr(ib("companion_choice")),
        "mt": ib("monster_type"), "T": ib("fight_duration"), "content": ib("content_type"),
        "pvp_len": PVP_FIGHT_DURATION, "cap": ib("max_enemies_hit"), "w": ib("normal_weight_frac"),
        "unit": f'IFERROR(N{b_row}/F{b_row}/{shadow_partner_mult_ref},0)',
        "bad": f'({ib("basic_attack_damage")}+{delta["basic_attack_damage"]}+{agg_basic_attack_damage_block})',
        "sd": f'({ib("skill_damage")}+{delta["skill_damage"]}+{agg_skill_damage_block})',
        "aps": aps_ref,
        "avgbuff": avgbuff_ref,
        "attack_bucket_avg": bucket_ref,
        "k1": _k1_block, "fdpart": _fdpart_block,
        "avgbuff_snap": lambda charm_expr, extra: f'((1+({_k1_block}+{charm_expr}+{extra})/100)*{_fdpart_block})',
        "charm_val": _charm_val_block,
        "agg_damage_avg": agg_damage_block, "hex_avg": hexagon_dmg_block,
        "hex_snap": lambda stacks: f'IF({ib("hexagon_necklace_equipped")},{star_lookup_expr(ib("hexagon_necklace_star"), "hexagon_necklace_damage")}*{stacks},0)',
        "agg_fd_boss_only": agg_final_damage_boss_only_block, "agg_fd_norm_only": agg_final_damage_normal_only_block,
        "chalice_avg_boss": chalice_boss_block, "chalice_avg_norm": chalice_normal_block,
        "chalice_full": (
            f'IF(AND({ib("chalice_equipped")},OR({ib("monster_type")}="normal",{ib("monster_type")}="breakthrough")),'
            f'{star_lookup_expr(ib("chalice_star"), "chalice_final_damage")},0)'
        ),
        "horn_avg": horn_flute_block,
        "horn_full": artifact_horn_flute_full_expr(ib("horn_flute_equipped"), ib("content_type"), ib("horn_flute_star")),
        "boss_pct": _boss_pct_block, "norm_pct": _norm_pct_block,
        "extra_boss": basic_extra_boss_block, "extra_norm": extra_normal_mult_block,
        "player_boss": f"SUM(T{calc_start}:T{calc_end})", "player_norm": f"SUM(V{calc_start}:V{calc_end})",
        "player_uniform_boss": "(" + "+".join(f"T{row_of[k]}" for k in STATUS_UNIFORM_ROWS) + ")",
        "player_basic_boss": f"T{b_row}", "player_basic_norm": f"V{b_row}",
        "cr_total": f'({ib("crit_rate")}+{delta["crit_rate"]}+{crit_rate_bonus_ref}+{boa_direct_delta}+{agg_crit_rate_block})',
        "cd_total": f'({ib("crit_damage")}+{delta["crit_damage"]}+{crit_damage_bonus_ref}+{agg_crit_damage_block})',
        "min_dmg": f'({ib("min_damage")}+{delta["min_damage"]})',
        "max_dmg": f'({ib("max_damage")}+{delta["max_damage"]}+{agg_max_damage_block})',
        "defense": ib("monster_defense"), "def_pen": def_pen_total_block,
        "taken_bucket": companion_taken_bucket(ib("monster_type"), ib("normal_weight_frac"), _boss_pct_block, _norm_pct_block),
        "st_on": lay.s("on"), "st_S": ib("status_effect_damage"), "st_idx": lay.rng("idx"),
        "st_mult": lay.rng("mult"), "st_act": lay.rng("act"), "st_dw": lay.rng("dw"),
        "pst": stl.player_stun_entries(STATUS_PLAYER_STUN, lambda l, k: f"{l}{row_of[k]}", startup_ref),
    }

    def _write_block_companion(name, _label, formula):
        idx = COMPANION_NAME_INDEX[name]
        per = BLOCK_HEIGHT - 1
        ws.cell(row=base_row + idx % per, column=COMPANION_BLOCK_COL0 + idx // per, value=formula)

    # Blocks reuse the summon time the main sheet chose (one candidate) - except the block sweeping Summoning Time Increase itself,
    # which must search again.  Hexagon Necklace / Horn Flute equip toggles change what the candidate summon times are worth (stack times, the flute's own
    # Final Damage), and Skill Cooldown Decrease re-times every cooldown cast and the player's own stun, so those blocks search the candidates themselves too
    # (guide "Gap found by the Buccaneer port", items 1-4).
    if stat_key in COMPANION_FULL_SEARCH_KEYS:
        _block_cells = cm.cells(block_host)
    else:
        _block_cells = cm.cells(block_host, ncand=1, fixed_s=companion_main_ref("best_s"),
                               fixed_tend=companion_main_ref("best_Tend"), fixed_e=companion_main_ref("best_E"))
    cm.emit(_block_cells, comp_ref, _write_block_companion)

    if lay is not STATUS_MAIN_LAYOUT:
        # The strip's stun vector uses CANDIDATE-0 timing (summon time s_0 / window W_0, see cm.stun_bin_expr).  A block's own chain pins its candidate 0 to the
        # summon time the main sheet CHOSE (which can be another candidate), so read the main sheet's s_0 / W_0 here - exactly what the main strip (and a full
        # re-evaluation at the swept value) uses.  Only the Summoning-Time block, which sweeps the duration itself, keeps its own s_0 / W_0.
        def _stun_ref(name):
            if name in ("s_0", "W_0") and stat_key not in SUMMON_TIME_KEYS:
                return companion_main_ref(name)
            return comp_ref(name)
        _bhost = status_engine_host(
            ib, lambda letter, key: f"{letter}{row_of[key]}", lambda key: S("ActiveWindow(s)", ROW[key]), bdi_block,
            f'({delta["attack_mult"]}+{agg_attack_pct_block}-{charm_of_the_undead_block})',
            _charm_val_block, _hex_v_block, hexagon_dmg_block, f'Y{row_of["SHOWDOWN"]}',
            hasstun=comp_ref("hasstun"),
            stun=lambda i: cm.resolve_tokens(cm.stun_bin_expr(i, _stun_ref, None), _stun_ref),
        )
        stl.Layout(stl.cells(_bhost), strip_row0, 1).write(ws)

    return total_ref, boss_total_ref, normal_total_ref


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

    # 2nd, simpler table for boolean artifact equip-toggles — "Units per +1% DPS"/"Current-New
    # Value" are meaningless for a toggle, per the user, so it only shows the DPS/% gain from
    # equipping. Positioned right after the "Stat" table (sized off SENSITIVITY_ARTIFACT_TABLE_
    # HEADER_ROWS, kept in sync with BLOCK_START's own buffer math above it). Row constants live
    # at module level (ARTIFACT_TABLE_*) so build_summary_sheet can reference the same rows.
    artifact_title_row = ARTIFACT_TABLE_TITLE_ROW
    artifact_header_row = ARTIFACT_TABLE_HEADER_ROW
    # The visible A/B/C columns show only UNLOCKED artifacts, sorted best-to-worst by % Gain
    # (confirmed by the user). Raw per-artifact values go into a hidden staging block (columns
    # AA-AE, far from every other column this sheet uses); A/B/C then pull each display row from
    # staging via INDEX/MATCH on a rank computed among unlocked artifacts only.
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
        total_ref, boss_total_ref, normal_total_ref = build_stat_block(
            ws, base_row, ib, key, label, override_expr, strip_row0=alloc_status_strip_row0(key))

        # DPS Gain/% Gain are time-weighted (not dollar-weighted) across the boss/normal branches:
        # each branch's own RELATIVE growth (new/baseline) is measured independently, then blended
        # by Inputs!normal_weight_frac — not the raw dollar totals, which would let a stat's
        # reported value be dominated by whichever branch happens to hit more targets, regardless
        # of how much combat time is actually spent there.
        boss_ratio = f'IFERROR({boss_total_ref}/Summary!$B${R_BOSS_ONLY_TOTAL},1)'
        normal_ratio = f'IFERROR({normal_total_ref}/Summary!$B${R_NORMAL_ONLY_TOTAL},1)'
        weighted_ratio = f'((1-{IB("normal_weight_frac")})*{boss_ratio}+{IB("normal_weight_frac")}*{normal_ratio})'
        dps_gain_expr = f"=Summary!$B${R_TOTAL}*({weighted_ratio}-1)"
        pct_gain_expr = f"={weighted_ratio}*100"

        if kind != "bool":
            row = header_row + 1 + stat_idx
            stat_idx += 1
            ws.cell(row=row, column=1, value=label)
            ws.cell(row=row, column=3, value=kind)
            ws.cell(row=row, column=4, value=f"={IB(key)}")
            ws.cell(row=row, column=5, value=f"={override_expr}")
            ws.cell(row=row, column=6, value=f"=Summary!$B${R_TOTAL}")
            ws.cell(row=row, column=7, value=f"={total_ref}")
            ws.cell(row=row, column=8, value=dps_gain_expr)
            ws.cell(row=row, column=9, value=pct_gain_expr)
            ws.cell(row=row, column=2, value=f'=IFERROR(1/(I{row}-100),"n/a")')
        else:
            row = artifact_header_row + 1 + artifact_idx
            artifact_idx += 1
            # Already-equipped artifacts test on->off (see override_expr_for's "bool" branch), so
            # weighted_ratio is hypothetical-removed/real (<1 if beneficial) instead of
            # hypothetical-added/real (>1) — sign-flip the dollar gain and divide by the
            # HYPOTHETICAL-UNEQUIPPED total (not whichever total happens to be "real" right now)
            # so both directions report the exact same "value of having this equipped" % (>100%/
            # positive $ = beneficial), confirmed by the user. The hypothetical-unequipped total is
            # Summary!TOTAL_DPS itself when not currently equipped (that IS the real/unequipped
            # state), or Summary!TOTAL_DPS minus this same signed dollar gain when currently
            # equipped (undoing it) — a real, previously-unfixed bug: dividing by Summary!TOTAL_DPS
            # unconditionally in both directions made the reported % differ depending on current
            # equip state even though the dollar gain itself was already direction-invariant.
            currently_equipped_expr = IB(key)
            # Potential lines only apply while the artifact is actually equipped (confirmed by the
            # user), so equipping/un-equipping must also gain/lose whatever this artifact's
            # CURRENT potential rolls are worth — added unsigned in both directions.
            art_key = key[: -len("_equipped")]
            potential_dps_ref = f'ArtifactsInput!$L${ARTIFACTS_INPUT_ROW[art_key]}'
            total_gain_dollar_expr = (
                f'(IF({currently_equipped_expr},-1,1)*Summary!$B${R_TOTAL}*({weighted_ratio}-1)'
                f'+{potential_dps_ref})'
            )
            artifact_dps_gain_expr = f"={total_gain_dollar_expr}"
            artifact_pct_gain_expr = (
                f"=IF({currently_equipped_expr},"
                f"Summary!$B${R_TOTAL}/(Summary!$B${R_TOTAL}-{total_gain_dollar_expr})*100,"
                f"(Summary!$B${R_TOTAL}+{total_gain_dollar_expr})/Summary!$B${R_TOTAL}*100)"
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
            display_rank = artifact_idx  # already incremented above, so this is 1-based
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

    # Companion comparison: DPS gained by summoning each companion (at its CompanionsInput level) instead of none, from the
    # Companion sheet's comparison columns (the player's own damage is unchanged, so Total with = Total without + the companion's
    # damage and the uplift it grants).  % Gain = (Total without + gain) / Total without.  Shown best-to-worst among the UNLOCKED
    # companions only (same staging + rank + INDEX/MATCH technique as the artifact table above; staging in hidden columns AG-AL).
    ws.cell(row=COMPANION_TABLE_TITLE_ROW, column=1, value="Companion Comparison (DPS gain of summoning each unlocked companion vs. none, current content type)").font = SECTION_FONT
    for i, name in enumerate(["Companion", "Level", "DPS Gain", "% Gain"]):
        ws.cell(row=COMPANION_TABLE_HEADER_ROW, column=i + 1, value=name)
    style_header_row(ws, COMPANION_TABLE_HEADER_ROW, 4)
    cur = f"Companion!$B${COMPANION_ROW_OF['comp_blend_dps']}"
    stg = {"label": 33, "level": 34, "gain": 35, "pct": 36, "unlocked": 37, "rank": 38}   # AG-AL
    first_r, last_r = COMPANION_TABLE_FIRST_DATA_ROW, COMPANION_TABLE_LAST_ROW
    rng = {k: f"${get_column_letter(c)}${first_r}:${get_column_letter(c)}${last_r}" for k, c in stg.items()}
    n_unlocked = f"COUNTIF({rng['unlocked']},TRUE)"
    gcol, ucol = get_column_letter(stg["gain"]), get_column_letter(stg["unlocked"])
    for k_idx, (name, crow) in enumerate(COMPANION_TABLE_ROW.items(), start=1):
        col = get_column_letter(COMPANION_CMP_COL[name])
        gain = f"Companion!${col}${COMPANION_ROW_OF['comp_blend_dps']}"
        ws.cell(row=crow, column=stg["label"], value=name)
        ws.cell(row=crow, column=stg["level"], value=f"=CompanionsInput!$C${COMPANION_INPUT_ROW[name]}")
        _ratio = companion_weighted_ratio(col)
        ws.cell(row=crow, column=stg["gain"], value=f"=(Summary!$B${R_TOTAL}-{cur})*({_ratio}-1)")
        ws.cell(row=crow, column=stg["pct"], value=f"=({_ratio}-1)*100+100")
        ws.cell(row=crow, column=stg["unlocked"], value=f"={get_column_letter(stg['level'])}{crow}>=1")
        ws.cell(row=crow, column=stg["rank"], value=(
            f'=IF({ucol}{crow},SUMPRODUCT(({rng["unlocked"]})*({rng["gain"]}>{gcol}{crow}))'
            f'+COUNTIFS(${ucol}${first_r}:{ucol}{crow},TRUE,${gcol}${first_r}:{gcol}{crow},{gcol}{crow}),"")'
        ))
        for disp_col, key in ((1, "label"), (2, "level"), (3, "gain"), (4, "pct")):
            ws.cell(row=crow, column=disp_col, value=(
                f'=IF({k_idx}>{n_unlocked},"",INDEX({rng[key]},MATCH({k_idx},{rng["rank"]},0)))'
            ))
    for c in stg.values():
        ws.column_dimensions[get_column_letter(c)].hidden = True

    # Companion Summoning Time Increase: what each total is worth, split the way the boss phase works (contents with a normal-monster phase first:
    # Breakthrough, Hero Dungeon).  average boss DPS change x boss-time factor = boss damage change; the content's emphasis w weights boss and normal.
    ws.cell(row=COMPANION_BREAKDOWN_TITLE_ROW, column=1, value=(
        "Companion Summoning Time Increase % - value of each total from the boots lines (Breakthrough / Hero Dungeon: boss phase = average DPS x time)"
    )).font = SECTION_FONT
    for i, name in enumerate(["Total % from lines", "Average boss DPS change", "Boss-phase time factor", "Boss damage change (DPS x time)",
                              "Normal-monster DPS change", "Weighted DPS change (boss/normal emphasis)"]):
        ws.cell(row=COMPANION_BREAKDOWN_HEADER_ROW, column=i + 1, value=name)
    style_header_row(ws, COMPANION_BREAKDOWN_HEADER_ROW, 6)
    _Rr = COMPANION_ROW_OF
    _tb0, _tbp = f"Companion!$B${_Rr['tb0']}", f"Companion!$B${_Rr['Tbp']}"
    _base = get_column_letter(COMPANION_POT_COL[0])
    _pn = f"SUM(Calc!$V$2:$V${LAST_ROW})"

    def _Dm(c):
        return (f"(Companion!${c}${_Rr['pb']}*{_tbp}+Companion!${c}${_Rr['best_dmg_b']}+Companion!${c}${_Rr['best_upl_b']}+Companion!${c}${_Rr['best_ext']})")

    def _Tm(c):
        return f"({_tbp}+Companion!${c}${_Rr['best_E']})"
    for i, x in enumerate(COMPANION_POT_TOTALS):
        r = COMPANION_BREAKDOWN_FIRST_ROW + i
        c = get_column_letter(COMPANION_POT_COL[x])
        ws.cell(row=r, column=1, value=x)
        ws.cell(row=r, column=2, value=f'=IF({_tb0}>0,IFERROR(({_Dm(c)}/{_Tm(c)})/({_Dm(_base)}/{_Tm(_base)})-1,0),"")')
        ws.cell(row=r, column=3, value=f'=IF({_tb0}>0,{_Tm(c)}/{_Tm(_base)},"")')
        ws.cell(row=r, column=4, value=f'=IF({_tb0}>0,IFERROR({_Dm(c)}/{_Dm(_base)}-1,0),"")')
        ws.cell(row=r, column=5, value=(
            f"=IFERROR(({_pn}+Companion!${c}${_Rr['comp_norm_dps']})/({_pn}+Companion!${_base}${_Rr['comp_norm_dps']})-1,0)"
        ))
        ws.cell(row=r, column=6, value=f"=({companion_weighted_ratio(c, _base)}-1)")

    # Cooldown Reduction Milestone Sweep — CDR's DPS impact is a step function in fixed-duration
    # content (CastsInFight floors via INT()), unlike every other stat's smooth marginal delta
    # above. Sweeps a fixed set of absolute CDR values, each with its own full shadow recompute,
    # appended after all STAT_SWEEP blocks so it can't collide with their spacing.
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
            strip_row0=alloc_status_strip_row0("skill_cooldown_decrease"),
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
    for col in artifact_staging_col.values():
        ws.column_dimensions[get_column_letter(col)].hidden = True
    ws.freeze_panes = "A5"
    return ws


# ---------------------------------------------------------------------------
# Equipment Compare — pick a "Current Equip" and a "New Equip" (an Attack line + up to 5 more
# stat lines each) and see which is the bigger upgrade, as a DPS % delta. Reuses the exact same
# Sensitivity!H<row> "$/unit" marginal-DPS values Potential Cubes/Artifact Potentials already use
# — a pure calculator sheet, nothing else in the workbook reads from it, so no Calc/Summary/
# Sensitivity/verify_night_lord_workbook.py changes are needed for this feature at all.
# ---------------------------------------------------------------------------
EQUIP_COMPARE_STAT_TO_SWEEP_KEY = {
    "Main Stat (flat)": "flat_luk",
    "Main Stat %": "luk_pct",
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

    ws["A1"] = "Night Lord — Equipment Compare"
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
    ws.cell(row=1, column=16, value="PotentialType")
    for col in (13, 14, 15, 16):
        ws.cell(row=1, column=col).fill = HEADER_FILL
        ws.cell(row=1, column=col).font = HEADER_FONT
    r = 2
    for potential_type, rates in RARITY_UPGRADE_RATES.items():
        for rarity in RARITY_ORDER:
            ws.cell(row=r, column=13, value=rarity)
            ws.cell(row=r, column=14, value=rates[rarity]["rate"])
            ws.cell(row=r, column=15, value=rates[rarity]["max"])
            ws.cell(row=r, column=16, value=potential_type)
            r += 1

    ws.cell(row=1, column=17, value="SlotList")
    ws.cell(row=1, column=17).fill = HEADER_FILL
    ws.cell(row=1, column=17).font = HEADER_FONT
    for i, slot in enumerate(CUBE_SLOTS):
        ws.cell(row=i + 2, column=17, value=slot)
    assert 1 + len(CUBE_SLOTS) == CUBE_DATA_SLOT_LIST_LAST_ROW

    widths = [10, 12, 6, 26, 9, 9, 8, 13, 2, 26, 13, 2, 12, 10, 9, 15, 14]
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



def build_artifacts_input_sheet(wb, existing=None):
    """A dedicated "current gear state" sheet for Artifacts, styled after PotentialCubes: set
    every artifact's Star Level (or "Not Unlocked") and roll up to 3 Potential lines per artifact
    (2 for Epic/Unique, 3 for Legendary — gated by Star Level; see ARTIFACT_POTENTIAL_VALUES).
    Rows follow the wiki's own artifact order grouped by Rank, with a blank separator row between
    groups, per the user. Column M resolves each artifact's Equipped? from the 4 equip-slot
    pickers on the Inputs sheet instead (see INPUT_ARTIFACT_SLOT_ROWS) — moved there per the user
    so equip state sits alongside the rest of the per-content-type loadout. IB() reads every
    "{art_key}_equipped"/"{art_key}_star" key straight from this sheet's M/N columns (see
    ARTIFACT_INPUT_CELL)."""
    existing = existing or {}
    ws = wb.create_sheet("ArtifactsInput")
    ws["A1"] = "Night Lord — Artifacts (Star Level + Potentials)"
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

    COMPUTED_FILL = PatternFill("solid", fgColor="D9D9D9")

    ws.cell(row=ARTIFACTS_INPUT_TABLE_HEADER_ROW - 1, column=1, value="All Artifacts — Star Level + Potentials").font = SECTION_FONT

    headers = [
        "Artifact", "Star Level",
        "Line 1 Rarity", "Line 1 Stat", "Line 1 DPS Gain",
        "Line 2 Rarity", "Line 2 Stat", "Line 2 DPS Gain",
        "Line 3 Rarity (Legendary only)", "Line 3 Stat (Legendary only)", "Line 3 DPS Gain",
        "Total Potential DPS Gain",
        "Equipped? (computed)", "Star Level, resolved (computed)", "Equip effect in the DPS model",
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

        # Columns M/N — resolved Equipped?/Star Level, consumed by IB() (see ARTIFACT_INPUT_CELL)
        # instead of anything on the Inputs sheet.
        eq_formula = "=OR(" + ",".join(
            f'Inputs!$B${slot_row}="{art_label}"' for slot_row in INPUT_ARTIFACT_SLOT_ROWS
        ) + ")"
        ws.cell(row=row, column=13, value=eq_formula)
        ws.cell(row=row, column=14, value=f'=IF(B{row}="Not Unlocked",0,B{row})')
        if art_key in ARTIFACT_NO_DPS_EFFECT:
            ws.cell(row=row, column=15, value=f"No DPS effect ({ARTIFACT_NO_DPS_EFFECT[art_key]})")
        elif art_key == "arwens_glass_shoes":
            ws.cell(row=row, column=15, value=(
                "Companion Summoning Time Increase % (live): +20% at star 0 and +40% at star 5 (confirmed), linear steps "
                "20/24/28/32/36/40 in between (confirmed; ARTIFACT_STAR_VALUES) - added to the Inputs value"))

    widths = [42, 12, 12, 26, 14, 12, 26, 14, 12, 26, 14, 16, 18, 20, 60]
    for i, w in enumerate(widths):
        ws.column_dimensions[get_column_letter(i + 1)].width = w
    ws.freeze_panes = f"A{ARTIFACTS_INPUT_TABLE_HEADER_ROW + 1}"
    return ws




def load_existing_workbook_state(path):
    """If a previous Night-Lord-DPS-Calculator.xlsx already exists at `path`, read back its
    Inputs values, ArtifactsInput gear state, and PotentialCubes current-gear table so
    regenerating the workbook doesn't clobber the user's real character stats and gear state with
    the hardcoded defaults. No older Artifacts-era layout to migrate from (brand new to this
    class) — only the pre-per-content-type single-column Inputs format needs a migration path."""
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
            # Inputs cells are always raw literals now (never formulas) — a formula string here
            # means this row held something else before a layout change; skip it rather than
            # carry over stale data from the wrong cell.
            if value is None or (isinstance(value, str) and value.startswith("=")):
                return None
            return value

        # One-time layout migration (self-detecting: only fires on a workbook whose row 22 is still MIN_DAMAGE %): Status Effect Damage % was
        # inserted at row 22, pushing Min Damage .. Skill Level All down by one row.
        _old_layout = str(ws.cell(row=IN["status_effect_damage"], column=1).value or "").startswith("MIN_DAMAGE")
        _shifted = {"min_damage", "max_damage", "final_damage", "skill_lvl_1st", "skill_lvl_2nd", "skill_lvl_3rd", "skill_lvl_4th", "skill_lvl_all"}
        for key, row in IN.items():
            if row in COMPUTED_INPUT_ROWS:
                continue
            if key == "status_effect_damage" and _old_layout:
                continue
            if _old_layout and key in _shifted:
                row -= 1
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

        if ws.cell(row=INPUT_ARTIFACT_SLOTS_SECTION_ROW, column=1).value == "Equipped Artifacts (up to 4)":
            existing_inputs["artifact_slots"] = {
                ct: [ws.cell(row=r, column=col).value or "(none)" for r in INPUT_ARTIFACT_SLOT_ROWS]
                for ct, col in col_for_ct.items()
            }

    if "CompanionsInput" in wb.sheetnames:
        cws = wb["CompanionsInput"]
        levels = {}
        for r in range(COMPANIONS_INPUT_FIRST_ROW, cws.max_row + 1):
            nm, lv = cws.cell(row=r, column=1).value, cws.cell(row=r, column=2).value
            if nm in cm.COMPANIONS and lv is not None and not (isinstance(lv, str) and lv.startswith("=")):
                levels[nm] = lv
        if levels:
            existing_inputs["companion_levels"] = levels

    existing_artifacts_input = {}
    if "ArtifactsInput" in wb.sheetnames:
        aws = wb["ArtifactsInput"]
        # Rows are matched by the artifact's own label text (column A), not by the row number this
        # build assigns it (ARTIFACTS_INPUT_ROW) — the rank-grouped + blank-separator-row layout
        # means an artifact's row number could differ between builds if ARTIFACT_LABELS ever
        # changes order.
        label_to_old_row = {}
        for r in range(1, aws.max_row + 1):
            label = aws.cell(row=r, column=1).value
            if label in ARTIFACT_LABELS.values():
                label_to_old_row[label] = r
        stars = {}
        lines = {}
        line_cols = [(3, 4), (6, 7), (9, 10)]
        for art_key, art_label in ARTIFACT_LABELS.items():
            old_row = label_to_old_row.get(art_label)
            if old_row is None:
                continue
            val = aws.cell(row=old_row, column=2).value
            stars[art_key] = val if val is not None else "Not Unlocked"
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
    build_calc_sheet(wb)
    build_summary_sheet(wb)
    build_timeline_sheet(wb)
    build_companion_kits_sheet(wb)
    build_companion_sheet(wb)
    build_artifacts_sheet(wb)
    build_sensitivity_sheet(wb)
    build_equipment_compare_sheet(wb, existing=existing_equipment_compare)
    build_cube_data_sheet(wb)
    build_potential_cubes_sheet(wb, existing=existing_potential_cubes)
    build_artifacts_input_sheet(wb, existing=existing_artifacts_input)
    build_companions_input_sheet(wb, existing=existing_inputs.get("companion_levels"))
    wb.active = 0
    wb.save(OUT_PATH)
    print(f"Wrote {OUT_PATH}")
    if existing_inputs or existing_artifacts_input or existing_potential_cubes or existing_equipment_compare:
        print("Carried over Inputs/ArtifactsInput/PotentialCubes values from the previous workbook.")


if __name__ == "__main__":
    main()
