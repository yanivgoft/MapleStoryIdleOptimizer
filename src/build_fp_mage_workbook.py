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
# Layout: TOTAL DPS sits at row 3; the small, fixed-size "Derived Values"/"info dump" block
# (D_ATTACK.../R_BM..., ~18 rows) is placed right below it; the two VARIABLE-length summary
# tables (Per-Skill Breakdown, sized off DAMAGE_DEALING_KEYS, and Marginal DPS & Stat Value,
# sized off STAT_SWEEP) are placed AFTER that fixed block instead of before it, so they can grow
# downward forever without ever colliding with a hardcoded row number below them (this collided
# twice already when STAT_SWEEP grew: once needing this same fix pattern elsewhere in this file,
# and again when the 8 new artifact equip-toggle STAT_SWEEP rows silently overwrote D_SKILL_
# COEFFICIENT/D_NORMAL_WEIGHT_FRAC). D_NORMAL_WEIGHT_FRAC in particular can't itself be computed
# from len(STAT_SWEEP)/len(DAMAGE_DEALING_KEYS) even in principle: its value is baked into a
# formula string (_MIST_ERUPTION_HITS_EXPR) at module-load time, long before either list is
# defined further down this file — so this block's rows must stay small, fixed, and first.
# ---------------------------------------------------------------------------
R_TOTAL = 3
DERIVED_HEADER_ROW = 5           # "Derived Values" section header
D_ATTACK = 6                     # ATTACK = Flat ATTACK x (1+ATTACK%/100)
D_STAT_DAMAGE = 7                # STAT_DAMAGE% = 1% of total INT + 0.25% of LUK
D_BASIC_INPUT_LEVEL = 8          # Basic Attack input level (4th job formula)
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
R_BM = 13                        # Burning Magic Multiplier
R_ED_MULT = 14                   # Elemental Decrease Multiplier
R_AVGBUFF = 15                   # Average Buff Multiplier (Magic Guard + Meditation, summed; then Infinity)
R_ASBONUS = 16                   # Attack Speed Buff Bonus % (Nimble Feet, averaged)
R_APS = 17                       # Actions Per Second
R_CASTRATE = 18                  # Skill + Buff Cast Rate (subtracted from Basic Attack)
R_BAPS = 19                      # Basic Attacks Per Second
R_BASIC = 20                     # Basic Attack DPS
METEOR_PROC_RATE_ROW = 21
R_STARTUP_TIME = 22              # Buff-Casting Startup Delay (s, fixed-duration only)
R_BOSS_ONLY_TOTAL = 23           # Total DPS if every hit were against a boss (Breakthrough Sensitivity baseline)
R_NORMAL_ONLY_TOTAL = 24         # Total DPS if every hit were against normal monsters (Breakthrough Sensitivity baseline)
# The two variable-length summary tables start after this fixed block, with a 2-row gap — same
# gap convention the old (now-removed) hardcoded-after layout used.
BREAKDOWN_SECTION_ROW = R_NORMAL_ONLY_TOTAL + 2

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

# Rows 46-77 used to hold the 16 artifacts' Equipped?/Star Level cells directly on the Inputs
# sheet; they now live on the ArtifactsInput sheet instead (see ARTIFACT_INPUT_CELL/IB below), and
# the Inputs sheet no longer shows them at all — kept here ONLY so
# load_existing_workbook_state can still migrate a pre-ArtifactsInput-sheet workbook's real gear
# state (see its "elif" branch) without losing it.
LEGACY_ARTIFACT_INPUT_ROWS = {
    "book_of_ancient_equipped": 46,
    "book_of_ancient_star": 47,
    "ring_of_cycles_equipped": 48,
    "ring_of_cycles_star": 49,
    "candle_equipped": 50,
    "candle_star": 51,
    "peach_tree_equipped": 52,
    "peach_tree_star": 53,
    "silver_pendant_equipped": 54,
    "silver_pendant_star": 55,
    "athena_gloves_equipped": 56,
    "athena_gloves_star": 57,
    "hexagon_necklace_equipped": 58,
    "hexagon_necklace_star": 59,
    "rainbow_snail_shell_equipped": 60,
    "rainbow_snail_shell_star": 61,
    "clear_spring_water_equipped": 62,
    "clear_spring_water_star": 63,
    "old_music_box_equipped": 64,
    "old_music_box_star": 65,
    "soul_contract_equipped": 66,
    "soul_contract_star": 67,
    "soul_pouch_equipped": 68,
    "soul_pouch_star": 69,
    "flaming_lava_equipped": 70,
    "flaming_lava_star": 71,
    "icy_soul_rock_equipped": 72,
    "icy_soul_rock_star": 73,
    "secret_map_equipped": 74,
    "secret_map_star": 75,
    "reindeer_spear_equipped": 76,
    "reindeer_spear_star": 77,
}

# Artifacts (Equip Effect only) — 16 artifacts, star-tier values (index 0-5) taken verbatim from
# idle.maplestorywiki.net/w/Artifacts. Book of Ancient and Athena Pierce's Old Gloves are the two
# whose *direct* stat contribution (Crit Rate%/Attack Speed%) is assumed already reflected in the
# character's own Inputs!crit_rate/attack_speed when equipped — same "already baked in, only the
# Sensitivity marginal delta matters" convention used all session for Magic Critical/Spell
# Mastery/mainstat-attack. Only their *dependent* bonus (computed from the character's resulting
# total stat) is a new, real Calc-sheet term. Clear Spring Water, Soul Pouch (their only stat), and
# Reindeer's Spear (only its BASE, un-multiplied Defense Penetration) extend this same "baked into
# Inputs" convention — confirmed by the user.
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
# 45 left blank as a spacer) so no existing IN-dict row number has to shift. One resolved column B
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
# Defense %/Accuracy/Status Effect Damage %. NOTE for when this expands to other classes: Defense
# % will need real modeling for Dark Knight (Iron Wall's Defense->STR conversion) and Bishop.
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


def artifact_ring_of_cycles_exprs(eq_expr, star_expr, threshold_cr_expr):
    """Returns (crit_rate_bonus, skill_dmg_bonus, basic_attack_dmg_bonus) expression strings.
    Basic Attack Damage scales continuously per 1% of Crit Rate excess above 100% (capped at
    100 excess points, i.e. 200% Crit Rate) rather than jumping every 10 points — modeled this
    way per the user's explicit choice, so Sensitivity's "+1%" test reflects a smooth marginal
    value everywhere instead of aliasing depending on how close the current value sits to a
    10-point boundary."""
    crit_rate = f'IF(AND({eq_expr},({threshold_cr_expr})<100),{star_lookup_expr(star_expr, "ring_of_cycles_crit_rate")},0)'
    skill_dmg = f'IF(AND({eq_expr},({threshold_cr_expr})>=100),{star_lookup_expr(star_expr, "ring_of_cycles_skill_damage")},0)'
    excess_points = f'IF(AND({eq_expr},({threshold_cr_expr})>=100),MIN(100,({threshold_cr_expr})-100),0)'
    basic_atk = f'(({excess_points})*{star_lookup_expr(star_expr, "ring_of_cycles_basic_attack_damage_per_point")})'
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


def artifact_horn_flute_expr(eq_expr, monster_type_expr, content_type_expr, fight_duration_expr, star_expr):
    """Real, live Final Damage source — only the character's own portion (the Companion's own
    damage isn't modeled at all, per the user). Companion summoned at t=7s, active 30s (window
    [7,37], per the user); doubled in Chapter Boss. 0 in PvP/Chapter Hunt (fight_duration=0) — no
    discrete battle-start event exists in either, same convention as Candle/Rainbow Snail Shell."""
    uptime = f'MIN(30,MAX(0,{fight_duration_expr}-7))/{fight_duration_expr}'
    mult = f'IF({content_type_expr}="Chapter Boss",2,1)'
    return (
        f'IF(AND({eq_expr},{monster_type_expr}<>"pvp",{fight_duration_expr}>0),'
        f'{star_lookup_expr(star_expr, "horn_flute_final_damage")}*({uptime})*{mult},0)'
    )


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


def IB(key):
    if key in DERIVED_ROW:
        return f"Summary!$B${DERIVED_ROW[key]}"
    if key in ARTIFACT_INPUT_CELL:
        return ARTIFACT_INPUT_CELL[key]
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
    ws["A1"] = "Fire/Poison Arch Mage — Artifacts (Star Level + Potentials)"
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

        # Columns M/N — resolved Equipped?/Star Level, consumed by IB() (see ARTIFACT_INPUT_CELL)
        # instead of anything on the Inputs sheet.
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


def build_inputs_sheet(wb, existing=None):
    existing = existing or {}
    ws = wb.create_sheet("Inputs")
    ws["A1"] = "Fire/Poison Arch Mage — DPS Calculator Inputs"
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

    # Ordered to match how these stats are laid out in-game, for quick copy-in.
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

    # A few per-content-type rows aren't relevant for every content type (confirmed by the user)
    # — columns for content types NOT listed here are left entirely blank (gray, no value, no
    # dropdown) rather than showing an unused default. Keys not listed here apply to all 10.
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
    # Chapter-Stage's expected FORMAT differs by content type (chapter-substage vs. a bare
    # chapter number vs. a bare stage number — see chapter/stage's own IFERROR-guarded parsing,
    # which already tolerates all three shapes and just ignores whichever half isn't consumed for
    # a given content type). Only Breakthrough/Chapter Hunt keep the chapter-substage shape they
    # already had; the other 6 applicable columns previously (incorrectly) carried that SAME text
    # via the initial "duplicate into all 10 columns" migration, so they're reset to a correctly-
    # shaped default here instead of perpetuating the wrong format (confirmed by the user).
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

    # Equipped-artifact slots — moved here from the ArtifactsInput sheet per the user, so equip
    # state sits alongside the rest of the per-content-type loadout instead of on a separate
    # sheet. Appended after everything else (row 45 left blank as a spacer) so no existing IN-dict
    # row number has to shift. One resolved column B (INDEX/MATCH against C:L, same mechanism as
    # every other per-content-type row) + per-content-type raw picks in C:L per slot.
    ws.cell(row=INPUT_ARTIFACT_SLOTS_SECTION_ROW, column=1, value="Equipped Artifacts (up to 4)").font = SECTION_FONT
    artifact_names = list(ARTIFACT_LABELS.values())
    # Data validation's inline quoted-list form is capped at 255 characters by Excel — the 36
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


# Artifacts sheet row layout — per-artifact intermediate/bonus rows, then aggregate bucket totals
# consumed by the main Calc/Summary pipeline (and mirrored in Sensitivity's build_stat_block).
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
    assumed already baked into Inputs!crit_rate/attack_speed (see the "baked into Inputs" convention) —
    only their dependent bonus is computed here. Every other artifact's full bonus is a real,
    additive term on top of Inputs, rolled up into the aggregate bucket rows at the bottom, which
    the main Calc/Summary pipeline (and Sensitivity's build_stat_block mirror) consume directly."""
    ws = wb.create_sheet("Artifacts")
    ws["A1"] = "Fire/Poison Arch Mage — Artifacts (Equip Effect)"
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
        f'*({IB("crit_rate")}+B{r["roc_crit_rate"]}+B{r["rainbow_crit_rate"]}),0)'
    ))

    # Ring of Cycles — the "every 5 seconds, cycles based on current Crit Rate" description
    # stabilizes to a static threshold branch, since Crit Rate doesn't fluctuate mid-fight in this
    # model. Threshold uses every OTHER real Crit Rate source (Inputs, already includes Book of
    # Ancient if equipped, plus Rainbow Snail Shell) — not its own contribution, avoiding self-reference.
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
        f'=B{r["roc_excess_points"]}*{star_lookup_expr(star["ring_of_cycles"], "ring_of_cycles_basic_attack_damage_per_point")}'
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
    ws.cell(row=r["horn_flute"], column=1, value="Horn Flute — Final Damage (character's own portion only)")
    ws.cell(row=r["horn_flute"], column=2, value="=" + artifact_horn_flute_expr(
        eq["horn_flute"], IB("monster_type"), IB("content_type"), IB("fight_duration"), star["horn_flute"],
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

    # Always-0 artifacts — raid content (Pink Bean/Horntail/Zakum), Guild Conquest (Ancient Text
    # Piece), companion-only or non-attacking procs (Lunar Dew, Mushmom's Cap, Arwen's Glass Shoes,
    # Pig's Ribbon) this project doesn't model at all. Trivial rows kept only so ArtifactsInput
    # still tracks star level/equip state consistently — see KNOWN_GAPS.md for why each is 0.
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
                                 normal_dmg_pct_expr, normal_targets_ref, max_enemies_ref,
                                 extra_boss_mult_expr="1", extra_normal_mult_expr="1"):
    """Splits a row's DPS into independent boss-only and normal-only values, given `prefix_expr`
    (the H*N*rate*(extra multipliers) part shared by both — everything upstream of the monster-type
    split is already monster-type-independent). Each branch gets its own full
    (1+damage%/100)*target_count treatment; the two are blended into the real Total DPS as RATIOS
    (new/baseline) weighted by time spent, not as raw dollars weighted by branch size — dollar
    blending would let a stat's reported value be dominated by whichever branch happens to hit more
    targets, regardless of how much combat time is actually spent there (confirmed bug, fixed this
    session). PvP is single-target with neither bonus, matching the old combined behavior.
    `extra_boss_mult_expr`/`extra_normal_mult_expr` (default "1", a no-op) are applied
    UNCONDITIONALLY, outside the `IF(pvp,1,...)` gating above — used for artifact bonuses that are
    genuinely branch-specific but unrelated to the boss_damage%/normal_damage% buckets themselves
    (Reindeer's Spear's boss/PvP-only Defense Penetration correction on the boss side; Secret
    Map's normal-monster-only Final Damage bonus on the normal side, which must stay 0 for PvP
    too — see its own gating in artifact_secret_map_exprs)."""
    capped_targets = f'MIN({normal_targets_ref},{max_enemies_ref})'
    boss_mult = f'IF({monster_type_ref}="pvp",1,1+({boss_dmg_pct_expr})/100)'
    normal_mult = f'IF({monster_type_ref}="pvp",1,(1+({normal_dmg_pct_expr})/100)*({capped_targets}))'
    return (
        f'({prefix_expr})*{boss_mult}*({extra_boss_mult_expr})',
        f'({prefix_expr})*{normal_mult}*({extra_normal_mult_expr})',
    )


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
        # Soul Contract's % Skill Cooldown Decrease (Chapter Hunt only) is applied as an extra
        # multiplicative wrapper here rather than inside effective_cooldown_expr itself, since it's
        # a simple postfix scale and keeps that well-tested function untouched.
        eff_cd_r = (
            f'({effective_cooldown_expr(IB("monster_type"), S("Cooldown(s)", r), IB("skill_cooldown_decrease"), S("CostsActionSlot", CDR_COSTS_ACTION_ROW[key]))}'
            f'*(1-{artifact_soul_contract_pct_expr(IB("soul_contract_equipped"), IB("content_type"), IB("soul_contract_star"))}/100))'
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
            max_damage_total_r = f'{IB("max_damage")}'
            crit_rate_total_r = f'({IB("crit_rate")}+{art_ref("AGG_CRIT_RATE")})'
            ws.cell(row=r, column=11, value=(
                f'=J{r}*(1+{IB("stat_damage")}/100)*(1+{IB("damage")}/100)'
                f'*(1+{IB("damage_amp")}/100)'
                f'*(5000/(6000+{IB("monster_defense")}*(1-{IB("def_pen")}/100)))'
                f'*(1+{IB("final_damage")}/100)*(1+{art_ref("AGG_FINAL_DAMAGE")}/100)*(1+F{ROW["ELEMENT_AMPLIFICATION"]}/100)'
                f'*(1+IF({IB("level")}>=120,F{ROW["ARCANE_AIM"]},0)/100)^5'
                f'*(1+(IF({S("Key", r)}="BASIC_ATTACK",{IB("basic_attack_damage")}+{art_ref("AGG_BASIC_ATTACK_DAMAGE")},'
                f'{IB("skill_damage")}+{art_ref("AGG_SKILL_DAMAGE")}+IF({IB("level")}>=125,F{ROW["FERVENT_DRAIN"]}*5,0)))/100)'
                f'*(Summary!$B${R_BM}*Summary!$B${R_ED_MULT}*Summary!$B${R_AVGBUFF}*(1+{art_ref("AGG_DAMAGE")}/100)*I{r})'
            ))
            ws.cell(row=r, column=12, value=f'=K{r}*(MIN({IB("min_damage")},{max_damage_total_r})/100+{max_damage_total_r}/100)/2')
            ws.cell(row=r, column=13, value=f'=L{r}*(1+({IB("crit_damage")}+{art_ref("AGG_CRIT_DAMAGE")})/100)')
            ws.cell(row=r, column=14, value=(
                f'=L{r}*(1-MIN({crit_rate_total_r},100)/100)+M{r}*(MIN({crit_rate_total_r},100)/100)'
            ))
        else:
            for col in (10, 11, 12, 13, 14):
                ws.cell(row=r, column=col, value="")

        # Boss/Normal Monster Damage% — Mastery-derived bonuses add in here, per-row via
        # MasteryBossDamage%/MasteryNormalDamage% (e.g. Basic Attack's Boss Mastery, Creeping
        # Toxin's Normal Monster Damage mastery). Kept as two independent branch percentages,
        # never blended into one shared value — see boss_normal_dps_split_exprs.
        boss_dmg_pct_r = f'{IB("boss_damage")}+{S("MasteryBossDamage%", r)}+{art_ref("AGG_BOSS_DAMAGE")}'
        normal_dmg_pct_r = f'{IB("normal_damage")}+{S("MasteryNormalDamage%", r)}+{art_ref("AGG_NORMAL_DAMAGE")}'

        # Reindeer's Spear — only its BASE (1x) Defense Penetration is baked into Inputs!def_pen;
        # the extra multiple beyond that (1 more for PvP's 2x total, 2 more for boss's 3x total) is
        # a real, live, boss/PvP-branch-only correction ratio between the nonlinear defense factor
        # computed with vs. without that extra amount (see artifact_reindeer_spear_extra_mult_expr).
        # Defense Penetration combines like Attack Speed — diminishing-returns
        # (new = 1-(1-old)*(1-inc)), never additive — so granting `extra_mult` more copies of the
        # spear's own per-dose value `s` on top of whatever's already baked into the baseline means
        # multiplying in (1-s)^extra_mult, not adding extra_mult*s (confirmed by the user; an
        # additive stack let Def Pen exceed 100% and made the defense factor blow up instead of
        # saturate at high Def Pen).
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
        # already-computed L{r}/M{r} cells.
        _cr_baseline_r = f'MIN(100,{crit_rate_total_r})'
        _cr_boss_r = f'MIN(100,{crit_rate_total_r}+{art_ref("contract_of_darkness_crit_rate_bonus")})'
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
        # normal-monster branch, never boss/PvP (see each's own formula-builder function).
        extra_normal_mult_r = f'(1+{art_ref("AGG_FINAL_DAMAGE_NORMAL_ONLY")}/100)'

        if key == "BASIC_ATTACK":
            prefix = f"{S('HitsPerCast', r)}*N{r}*Summary!$B${R_BAPS}"
            boss_expr, normal_expr = boss_normal_dps_split_exprs(
                prefix, IB("monster_type"), boss_dmg_pct_r, normal_dmg_pct_r,
                S("NormalMonsterTargets", r), IB("max_enemies_hit"),
                extra_boss_mult_r, extra_normal_mult_r,
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
                extra_boss_mult_r, extra_normal_mult_r,
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
                extra_boss_mult_r, extra_normal_mult_r,
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
                extra_boss_mult_r, extra_normal_mult_r,
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
                extra_boss_mult_r, extra_normal_mult_r,
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
    ws.cell(row=r_ed_mult, column=1, value="Elemental Decrease Multiplier (always-on) + Artifact Enemy Damage Taken Bonus")
    ws.cell(row=r_ed_mult, column=2, value=f'=1+(Calc!F{ed}+{art_ref("AGG_ENEMY_DMG_TAKEN")})/100')

    med, mg, nf, inf = ROW["MEDITATION"], ROW["MAGIC_GUARD"], ROW["NIMBLE_FEET"], ROW["INFINITY"]
    bdi_main = bdi_with_buff_mastery_expr(IB("buff_duration_increase_pct"), IB("level"), f'Calc!F{ROW["BUFF_MASTERY"]}')
    fda_main = fixed_duration_active_expr(IB("monster_type"), IB("fight_duration"))

    def buff_uptime(row):
        return uptime_fraction_or_exact_expr(
            fda_main, f'Calc!R{row}', IB("monster_type"), S("BuffDuration(s)", row), S("Cooldown(s)", row),
            bdi_main, IB("fight_duration"),
        )

    ws.cell(row=r_avgbuff, column=1, value=(
        "Average Buff Multiplier (Magic Guard + Meditation + Artifact Attack%, summed; then Infinity)"
    ))
    ws.cell(row=r_avgbuff, column=2, value=(
        # Magic Guard and Meditation are both "+X% Attack" sources — same bucket, so they sum into
        # one combined percentage before a single multiplication, instead of each compounding
        # against the other. Old Music Box/Secret Map/Reindeer's Spear's Attack% bonuses join this
        # same bucket (confirmed by the user). Infinity is Final Damage, a different (and
        # deliberately still multiplicative) bucket, so it stays its own separate factor.
        f'=(1+(Calc!F{med}*{buff_uptime(med)}+Calc!F{mg}*{buff_uptime(mg)}+{art_ref("AGG_ATTACK_PCT")})/100)'
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
# (see build_sensitivity_sheet) — chosen by the user to cover the range where fixed-duration
# skill cast counts are likely to cross an INT()-floor threshold and jump.
CDR_SWEEP_VALUES = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]


# Row on the Sensitivity results table (header at SENSITIVITY_HEADER_ROW) holding each swept
# stat's own row — used by the PotentialCubes sheet to pull each stat's "DPS gain per +1 unit"
# (column H, a linear approximation per the user's explicit delta-method instruction) without
# re-deriving it. Must stay in sync with build_sensitivity_sheet's own row assignment below.
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
            f'=IF({IB("crit_rate")}+{art_ref("AGG_CRIT_RATE")}>=100,Sensitivity!H{SENSITIVITY_ROW_FOR["crit_damage"]},'
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
# Derived from the two Results tables' own combined size (SENSITIVITY_HEADER_ROW + 1 row per
# STAT_SWEEP entry, split across the "Stat" and "Artifact Equip-Toggle" tables with
# SENSITIVITY_ARTIFACT_TABLE_HEADER_ROWS of structure between them) plus a small buffer, rather
# than a hardcoded row number — a hardcoded BLOCK_START previously drifted out of sync when this
# session's 3 new STAT_SWEEP entries grew the Results table past row 26, silently corrupting the
# first block (Flat INT)'s calc rows with the *last* 3 stats' results-row writes, since both
# landed on rows 27-29.
BLOCK_START = SENSITIVITY_HEADER_ROW + len(STAT_SWEEP) + SENSITIVITY_ARTIFACT_TABLE_HEADER_ROWS + 3


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
    if kind == "bool":
        # Equip-toggle test: always report "the value of having this equipped," in the same
        # positive direction regardless of current state (confirmed by the user — otherwise
        # already-equipped artifacts show a meaningless 0 while unequipped ones show their real
        # value, making them impossible to compare). Off->on if not currently equipped, on->off
        # if it is.
        return f'IF({base},FALSE,TRUE)'
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

    # Artifacts — block-local mirror of build_artifacts_sheet, so a swept stat correctly
    # propagates through whichever artifact depends on it (Book of Ancient/Ring of Cycles via
    # Crit Rate, Athena's Gloves via Attack Speed, Peach Tree/Silver Pendant via Actions Per
    # Second), and so each artifact's own equip-toggle STAT_SWEEP test ("what if I equipped
    # this") correctly reflects adding its bonus. Book of Ancient/Athena's Gloves' own direct stat
    # bonus is assumed already baked into Inputs!crit_rate/attack_speed (see
    # the "baked into Inputs" convention) — only a DELTA is needed here, identically 0 except when that
    # specific artifact's own equip-toggle is being tested (ib(...)-IB(...) is 0 unless this
    # block's override just flipped it from FALSE to TRUE).
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
    # Book of Ancient's dependent Crit-Damage-from-Crit-Rate bonus is also assumed already baked
    # into Inputs!crit_damage FOR WHATEVER CRIT RATE IS CURRENTLY EQUIPPED WITH — but Sensitivity
    # must still show its knock-on effect (confirmed by the user). Three cases:
    #   - Book's own equip-toggle block, adding (currently unequipped): the gain is the FULL
    #     dependent value from the resulting TOTAL Crit Rate (current Inputs value plus every
    #     other real artifact crit-rate source plus this block's own newly-granted direct
    #     portion) — not an increment, since there is no existing baked-in amount to double-count.
    #   - Book's own equip-toggle block, removing (currently equipped): the amount to strip must
    #     be computed using the REAL crit rate that actually produced today's baked-in
    #     Inputs!crit_damage value (IB("crit_rate") plus the real, un-recomputed Ring of
    #     Cycles/Rainbow Snail Shell contributions from the Artifacts sheet) — NOT a crit rate
    #     that's already had Book's own contribution subtracted out first, and not a hypothetical
    #     Ring of Cycles re-threshold-check against the post-removal total (confirmed by the user:
    #     compute how much Crit Damage Book gave before touching Crit Rate itself, not after).
    #   - Every other block (in particular the "crit_rate" sweep, with Book already equipped for
    #     real): only the MARGINAL Crit Rate introduced by that block's own override matters
    #     (ib(crit_rate)-IB(crit_rate)), since the baseline contribution is already manually baked
    #     into Inputs!crit_damage and must not be double-counted.
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
    # Athena Pierce's Old Gloves' dependent Max-Damage-from-Attack-Speed bonus — same direction-
    # aware treatment as Book of Ancient's Crit Damage above. No other artifact grants raw Attack
    # Speed, so the "remove" case's reference is simply the real, frozen IB("attack_speed") (the
    # value that actually produced today's baked-in Inputs!max_damage) — no art_ref needed.
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

    # Clear Spring Water / Soul Pouch — baked into Inputs when equipped (see
    # the "baked into Inputs" convention); each is a flat, content-type-gated value with no dependency on
    # any OTHER swept stat (unlike Book of Ancient/Athena's Gloves' dependent bonuses), so a single
    # toggle-delta (0 everywhere except that artifact's own equip-toggle block) suffices — no
    # stat_key branching needed.
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
    # Reindeer's Spear's base (1x) Defense Penetration is baked into Inputs!def_pen. Defense
    # Penetration combines like Attack Speed — diminishing-returns (new = 1-(1-old)*(1-inc)),
    # never additive (confirmed by the user; additive stacking let Def Pen exceed 100% and made
    # the defense factor blow up at high values instead of saturate). This shadow block's baseline
    # may need one extra "dose" of the spear's own contribution combined in via that formula:
    # whenever this IS the reindeer_spear_equipped block's own +1 test AND the spear isn't really
    # currently equipped (so ib("def_pen") doesn't already include it). Every other block's
    # ib(equipped) == IB(equipped) unchanged, so this always evaluates to 0 there (no spurious
    # effect on that stat's own test).
    reindeer_spear_base_ref_block = artifact_reindeer_spear_base_def_pen_reference_expr(
        ib("reindeer_spear_equipped"), ib("reindeer_spear_star"),
    )
    # Signed dose count: +1 adding (not currently equipped), -1 removing (currently equipped, per
    # override_expr_for's now-bidirectional "bool" toggle), 0 for every other block (ib==IB
    # unchanged there). A negative exponent correctly un-folds one dose via the diminishing-
    # returns formula's own algebra ((1-s)^-1 = 1/(1-s)) — this needs the UNGATED per-dose
    # magnitude (reindeer_spear_base_ref_block gates to 0 whenever ib(equipped) is false, which
    # would zero out the very thing a -1 exponent needs to un-fold).
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
    # Bottle of Emotion's Attack-Speed-dependent Final Damage — baked into Inputs!final_damage.
    # Bottle doesn't grant Attack Speed itself, so there's no "own contribution" to add/remove
    # from the AS total (unlike Book of Ancient/Athena's Gloves above) — only the dependent bonus
    # itself needs a direction-aware sign flip, evaluated at the real current Attack Speed in
    # both directions (Bottle's own toggle never changes ib("attack_speed")).
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

    # Aggregate bucket totals — block-local mirror of the Artifacts sheet's AGG_* rows.
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
        # Soul Contract's % CDR (Chapter Hunt only) applied the same way as the main Calc sheet.
        eff_cd_row = (
            f'({effective_cooldown_expr(ib("monster_type"), S("Cooldown(s)", r), ib("skill_cooldown_decrease"), S("CostsActionSlot", CDR_COSTS_ACTION_ROW[key]))}'
            f'*(1-{artifact_soul_contract_pct_expr(ib("soul_contract_equipped"), ib("content_type"), ib("soul_contract_star"))}/100))'
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
            max_damage_total_block = f'({ib("max_damage")}+{agg_max_damage_block})'
            crit_rate_full_block = f'({ib("crit_rate")}+{crit_rate_delta}+{boa_direct_delta}+{agg_crit_rate_block})'
            ws.cell(row=row, column=11, value=(
                f'=J{row}*(1+{ib("stat_damage")}/100)*(1+{ib("damage")}/100)'
                f'*(1+{ib("damage_amp")}/100)'
                f'*(5000/(6000+{ib("monster_defense")}*(1-{def_pen_total_block}/100)))'
                f'*(1+{ib("final_damage")}/100)*(1+{agg_final_damage_block}/100)*(1+F{row_of["ELEMENT_AMPLIFICATION"]}/100)'
                f'*(1+IF({ib("level")}>=120,F{row_of["ARCANE_AIM"]},0)/100)^5'
                f'*(1+(IF({S("Key", r)}="BASIC_ATTACK",{ib("basic_attack_damage")}+{agg_basic_attack_damage_block},'
                f'{ib("skill_damage")}+{agg_skill_damage_block}+IF({ib("level")}>=125,F{row_of["FERVENT_DRAIN"]}*5,0)))/100)'
                f'*({bm_ref}*{ed_ref}*{avgbuff_ref}*(1+{agg_damage_block}/100)*I{row})'
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

        boss_dmg_pct_row = f'{ib("boss_damage")}+{S("MasteryBossDamage%", r)}+{agg_boss_damage_block}'
        normal_dmg_pct_row = f'{ib("normal_damage")}+{S("MasteryNormalDamage%", r)}+{agg_normal_damage_block}'

        # The Contract of Darkness's boss-branch-only Crit Rate, via a crit-blend ratio correction
        # using THIS row's own L/M cells (only valid for damage-dealing rows, where crit_rate_full_
        # block was just freshly set above — matches every row that will actually consume this).
        _cr_baseline_block = f'MIN(100,{crit_rate_full_block})'
        _cr_boss_block = f'MIN(100,{crit_rate_full_block}+{contract_of_darkness_crit_rate_block})'
        cod_crit_ratio_block = (
            f'((L{row}*(1-{_cr_boss_block}/100)+M{row}*({_cr_boss_block}/100))'
            f'/(L{row}*(1-{_cr_baseline_block}/100)+M{row}*({_cr_baseline_block}/100)))'
        )
        extra_boss_mult_block = (
            f'({spear_def_ratio_block}*{cod_crit_ratio_block}*(1+{agg_final_damage_boss_only_block}/100))'
        )

        if key == "BASIC_ATTACK":
            # Local override-aware target count (6 + Inputs, not Skills!NormalMonsterTargets'
            # own formula, which always reads the global Inputs cell and wouldn't reflect this
            # block's override when "basic_attack_target_increase" itself is the swept stat).
            basic_targets_expr = f'(6+{ib("basic_attack_target_increase")}+IF({ib("level")}>=136,1,0))'
            prefix = f"{S('HitsPerCast', r)}*N{row}*{baps_ref}"
            boss_expr, normal_expr = boss_normal_dps_split_exprs(
                prefix, ib("monster_type"), boss_dmg_pct_row, normal_dmg_pct_row,
                basic_targets_expr, ib("max_enemies_hit"),
                extra_boss_mult_block, extra_normal_mult_block,
            )
            ws.cell(row=row, column=19, value=f'={boss_expr}')
            ws.cell(row=row, column=21, value=f'={normal_expr}')
        elif key == "METEOR_PROC":
            prefix = f'{meteor_proc_rate_block}*N{row}'
            boss_expr, normal_expr = boss_normal_dps_split_exprs(
                prefix, ib("monster_type"), boss_dmg_pct_row, normal_dmg_pct_row,
                S("NormalMonsterTargets", r), ib("max_enemies_hit"),
                extra_boss_mult_block, extra_normal_mult_block,
            )
            ws.cell(row=row, column=19, value=f'=IF(C{row},{boss_expr},0)')
            ws.cell(row=row, column=21, value=f'=IF(C{row},{normal_expr},0)')
        elif key == "FLAME_HAZE_DOT":
            prefix = f'H{row}*N{row}*{rate_row}*{flame_haze_dot_multiplier_block}'
            boss_expr, normal_expr = boss_normal_dps_split_exprs(
                prefix, ib("monster_type"), boss_dmg_pct_row, normal_dmg_pct_row,
                S("NormalMonsterTargets", r), ib("max_enemies_hit"),
                extra_boss_mult_block, extra_normal_mult_block,
            )
            ws.cell(row=row, column=19, value=f'=IF(C{row},{boss_expr},0)')
            ws.cell(row=row, column=21, value=f'=IF(C{row},{normal_expr},0)')
        elif key == "IFRIT":
            prefix = f'H{row}*N{row}*{rate_row}*(1+IF({ib("level")}>=130,0.2*{flame_haze_total_stacks_block},0))'
            boss_expr, normal_expr = boss_normal_dps_split_exprs(
                prefix, ib("monster_type"), boss_dmg_pct_row, normal_dmg_pct_row,
                S("NormalMonsterTargets", r), ib("max_enemies_hit"),
                extra_boss_mult_block, extra_normal_mult_block,
            )
            ws.cell(row=row, column=19, value=f'=IF(C{row},{boss_expr},0)')
            ws.cell(row=row, column=21, value=f'=IF(C{row},{normal_expr},0)')
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
    ws.cell(row=s_ed, column=2, value=f'=1+(F{row_of["ELEMENTAL_DECREASE"]}+{agg_enemy_dmg_taken_block})/100')

    med, mg, nf, inf = row_of["MEDITATION"], row_of["MAGIC_GUARD"], row_of["NIMBLE_FEET"], row_of["INFINITY"]
    bdi_block = bdi_with_buff_mastery_expr(
        f'({ib("buff_duration_increase_pct")}+{shamaness_marble_delta_block})', ib("level"), f'F{row_of["BUFF_MASTERY"]}',
    )

    def buff_uptime_block(local_row, skills_row):
        return uptime_fraction_or_exact_expr(
            fda_block, f'R{local_row}', ib("monster_type"), S("BuffDuration(s)", skills_row),
            S("Cooldown(s)", skills_row), bdi_block, ib("fight_duration"),
        )

    ws.cell(row=s_avgbuff, column=1, value="Average Buff Multiplier (Magic Guard + Meditation + Artifact Attack%, summed; then Infinity)")
    ws.cell(row=s_avgbuff, column=2, value=(
        f'=(1+(F{med}*{buff_uptime_block(med, ROW["MEDITATION"])}+F{mg}*{buff_uptime_block(mg, ROW["MAGIC_GUARD"])}+{agg_attack_pct_block})/100)'
        f'*IF(C{inf}=TRUE,(1+F{inf}*{buff_uptime_block(inf, ROW["INFINITY"])}/100),1)'
    ))

    ws.cell(row=s_asbonus, column=1, value="Attack Speed Buff Bonus % (Nimble Feet, averaged)")
    ws.cell(row=s_asbonus, column=2, value=(
        f'=F{nf}*{buff_uptime_block(nf, ROW["NIMBLE_FEET"])}'
    ))

    ws.cell(row=s_aps, column=1, value="Actions Per Second")
    ws.cell(row=s_aps, column=2, value=f'=1+MIN(150,150*(1-(1-{attack_speed_total_block}/150)*(1-{asbonus_ref}/150)))/100')

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

    # 2nd, simpler table for boolean artifact equip-toggles — "Units per +1% DPS"/"Current-New
    # Value" are meaningless for a toggle, per the user, so it only shows the DPS/% gain from
    # equipping. Positioned right after the "Stat" table (sized off SENSITIVITY_ARTIFACT_TABLE_
    # HEADER_ROWS, kept in sync with BLOCK_START's own buffer math above it). Row constants live
    # at module level (ARTIFACT_TABLE_*) so build_summary_sheet can reference the same rows.
    artifact_title_row = ARTIFACT_TABLE_TITLE_ROW
    artifact_header_row = ARTIFACT_TABLE_HEADER_ROW
    # The visible A/B/C columns show only UNLOCKED artifacts, sorted best-to-worst by % Gain
    # (confirmed by the user — only the artifact table, not the "Stat" table above, and locked
    # artifacts are dropped entirely rather than shown at the bottom). Since there's no raw
    # unsorted source to rank/filter against once A/B/C themselves become sorted, the raw
    # per-artifact values are computed into a hidden staging block (columns AA-AE, far from every
    # other column this sheet uses — including the many-column shadow-block copies below — to
    # avoid hiding anything else when this range gets column-hidden); A/B/C then pull each display
    # row from staging via INDEX/MATCH on a rank computed among unlocked artifacts only. % Gain is
    # a strictly increasing linear function of DPS Gain (same Total DPS baseline for every
    # artifact), so ranking by either column produces the identical order.
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
            # Units of this stat needed for a full +1% DPS gain, linearly extrapolated from the
            # +1-sized marginal test above: 1 / (percentage-point gain from that +1, i.e. %Gain-100).
            ws.cell(row=row, column=2, value=f'=IFERROR(1/(I{row}-100),"n/a")')
        else:
            row = artifact_header_row + 1 + artifact_idx
            artifact_idx += 1
            # Already-equipped artifacts test on->off (see override_expr_for's "bool" branch), so
            # weighted_ratio is hypothetical-removed/real (<1 if beneficial) instead of
            # hypothetical-added/real (>1) — sign-flip the dollar gain and reciprocal the %
            # gain so both directions report the same "value of having this equipped" convention
            # (>100%/positive $ = beneficial), confirmed by the user.
            currently_equipped_expr = IB(key)
            # Potential lines only apply while the artifact is actually equipped (confirmed by the
            # user), so equipping/un-equipping must also gain/lose whatever this artifact's
            # CURRENT potential rolls are worth — added unsigned in both directions (it's already
            # a positive "value of having this," same framing as the toggle result itself), unlike
            # the base equip effect above which needs the sign flip. ArtifactsInput's own gating
            # (Star Level per line) already zeroes out locked lines, and its "tracked regardless of
            # equip state" design means this reference value exists whether or not the artifact is
            # currently in a slot.
            art_key = key[: -len("_equipped")]
            potential_dps_ref = f'ArtifactsInput!$L${ARTIFACTS_INPUT_ROW[art_key]}'
            total_gain_dollar_expr = (
                f'(IF({currently_equipped_expr},-1,1)*Summary!$B${R_TOTAL}*({weighted_ratio}-1)'
                f'+{potential_dps_ref})'
            )
            artifact_dps_gain_expr = f"={total_gain_dollar_expr}"
            artifact_pct_gain_expr = f"=(Summary!$B${R_TOTAL}+{total_gain_dollar_expr})/Summary!$B${R_TOTAL}*100"
            # Raw (unsorted, wiki-order) values go into the hidden staging block; the visible row
            # instead shows whichever artifact ranks (among unlocked artifacts only) in THIS row's
            # display position (artifact_idx, 1=best) via INDEX/MATCH against the staging block's
            # own Rank column. Rows past the count of unlocked artifacts stay blank.
            ws.cell(row=row, column=artifact_staging_col["label"], value=label)
            ws.cell(row=row, column=artifact_staging_col["dps_gain"], value=artifact_dps_gain_expr)
            ws.cell(row=row, column=artifact_staging_col["pct_gain"], value=artifact_pct_gain_expr)
            ws.cell(row=row, column=artifact_staging_col["unlocked"], value=(
                f'=ArtifactsInput!$B${ARTIFACTS_INPUT_ROW[art_key]}<>"Not Unlocked"'
            ))
            # Rank among unlocked artifacts only (locked ones never occupy a rank, so the visible
            # table shows only as many rows as are actually unlocked, per the user — not shown at
            # the bottom, dropped entirely). Several artifacts are modeled as always exactly 0 DPS
            # impact (see KNOWN_GAPS.md), so ties happen for real; broken by each tied artifact's
            # own position from the top of the staging block (SUMPRODUCT "strictly better" count +
            # COUNTIFS running tally of ties-so-far) so every rank 1..count(unlocked) is produced
            # exactly once, with no gaps for MATCH() below to trip on.
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
    for col in artifact_staging_col.values():
        ws.column_dimensions[get_column_letter(col)].hidden = True
    ws.freeze_panes = "A5"
    return ws


# ---------------------------------------------------------------------------
# Equipment Compare — pick a "Current Equip" and a "New Equip" (an Attack line + up to 5 more
# stat lines each) and see which is the bigger upgrade, as a DPS % delta. Reuses the exact same
# Sensitivity!H<row> "$/unit" marginal-DPS values Potential Cubes/Artifact Potentials already use
# — a pure calculator sheet, nothing else in the workbook reads from it, so no Calc/Summary/
# Sensitivity/verify_fp_mage_workbook.py changes are needed for this feature at all.
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

    ws["A1"] = "Fire/Poison Arch Mage — Equipment Compare"
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
    Inputs values, ArtifactsInput gear state, and PotentialCubes current-gear table so
    regenerating the workbook (e.g. to pick up a data/formula change) doesn't clobber the user's
    real character stats and gear state with the hardcoded defaults. Matches PotentialCubes rows
    by (slot, potential type), not row position, so it's robust even if CUBE_SLOTS/POTENTIAL_TYPES
    order ever changes."""
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
        # CONTENT_TYPES is ever reordered — same philosophy as label_to_old_row below.
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
                # duplicating it into every content-type column so nothing suddenly zeroes out
                # (confirmed by the user), rather than losing it or leaving 9 columns at defaults.
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
            # Old file: equipped-artifact slots still lived on the ArtifactsInput sheet — either
            # per-content-type columns (from the earlier per-content-type rework) or a single flat
            # column from before that. Migrated forward onto the Inputs sheet's own slots section
            # regardless of which old shape is found (moved there per the user).
            slot_col_for_ct = {}
            for c in range(3, 3 + len(CONTENT_TYPES)):
                name = aws.cell(row=3, column=c).value
                if name in CONTENT_TYPES:
                    slot_col_for_ct[name] = c
            if slot_col_for_ct:
                existing_inputs["artifact_slots"] = {
                    ct: [aws.cell(row=r, column=col).value or "(none)" for r in LEGACY_ARTIFACTS_INPUT_SLOT_ROWS]
                    for ct, col in slot_col_for_ct.items()
                }
            else:
                old_slots = [aws.cell(row=r, column=2).value or "(none)" for r in LEGACY_ARTIFACTS_INPUT_SLOT_ROWS]
                existing_inputs["artifact_slots"] = {ct: list(old_slots) for ct in CONTENT_TYPES}
        # Rows are matched by the artifact's own label text (column A), NOT by the row number
        # this build assigns it (ARTIFACTS_INPUT_ROW) — the reorder-by-rank + blank-separator-row
        # layout means an artifact's row number can differ between the old file and this build, so
        # position-based lookup would silently read a different artifact's cells (or, before the
        # Potentials columns existed, the old Equipped?/Star-resolved formulas at columns F/G).
        # Scanned across the WHOLE sheet (not from a header-row constant) since that constant's
        # own value changed when the equip slots moved off this sheet — old files may have their
        # header at a different row than this build expects.
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
    elif "Inputs" in wb.sheetnames:
        # Migrate from the old raw Inputs!{key}_equipped/{key}_star literals (pre-ArtifactsInput
        # workbooks) so upgrading to this layout doesn't silently un-equip real gear. Artifacts
        # added after that layout was retired (not present in LEGACY_ARTIFACT_INPUT_ROWS) simply
        # aren't migrated — harmless, falls through to the "not equipped / not unlocked" defaults.
        ws = wb["Inputs"]
        old_slots, stars = [], {}
        for art_key, art_label in ARTIFACT_LABELS.items():
            eq_row = LEGACY_ARTIFACT_INPUT_ROWS.get(f"{art_key}_equipped")
            star_row = LEGACY_ARTIFACT_INPUT_ROWS.get(f"{art_key}_star")
            if eq_row is None or star_row is None:
                continue
            eq_val = ws.cell(row=eq_row, column=2).value
            star_val = ws.cell(row=star_row, column=2).value
            if eq_val is True and len(old_slots) < 4:
                old_slots.append(art_label)
            stars[art_key] = star_val if isinstance(star_val, (int, float)) else "Not Unlocked"
        while len(old_slots) < 4:
            old_slots.append("(none)")
        if "artifact_slots" not in existing_inputs:
            existing_inputs["artifact_slots"] = {ct: list(old_slots) for ct in CONTENT_TYPES}
        existing_artifacts_input = {"stars": stars}

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
        print("Carried over Inputs/PotentialCubes values from the previous workbook.")


if __name__ == "__main__":
    main()
