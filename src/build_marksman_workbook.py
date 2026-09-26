#!/usr/bin/env python3
"""
Generates Marksman-DPS-Calculator.xlsx: a live-formula Excel replica of a Marksman
skill-rotation DPS model, sibling to build_shadower_workbook.py / build_night_lord_workbook.py
(see /Users/yaniv/.claude/plans/so-basically-we-were-magical-iverson.md this was built from).
Marksman is the first DEX-main/STR-sub class built in this project (FP-Mage/ILM/Bishop are
INT-main/LUK-sub; Night Lord/Shadower are LUK-main/DEX-sub).

Sheets: Inputs, FactorTable, Skills, Calc, Summary, Sensitivity, CubeData, PotentialCubes.

Ground truth: fetched live from idle.maplestorywiki.net (curl, domain already allowlisted in
.claude/apple/dangerous_allowed_domains.csv) this session, cross-referenced against the actual
Aug 13 patch notes PDF (~/Downloads/August 13 Patch Notes - class changes.pdf) by mechanic/
description match, not name match (confirmed name divergences: wiki "Concentration" = PDF
"Focused Fury"; wiki "Flash Mirage" = PDF "Speed Mirage").

Key mechanics/simplifications specific to this kit (see the plan for full derivation):
  - Empowered Piercing Arrow (basic attack) reuses the universal 4th-job-basic-attack constant (baseDamage
    2900, factorIndex 21) confirmed identical across every class built so far, and confirmed
    fresh this session via Empowered Piercing Arrow's own wiki curve (290%->522%, levels 1-200).
  - Quiver Cartridge is a background DoT, same shape as FP-Mage's Ignite (CostsActionSlot=False,
    "always maintained"). Per user direction, its Attack-Speed-scaled tick rate uses the English
    wiki wording ("activation speed increases up to 0.4 times based on Attack Speed") over the
    Korean text's disagreeing "up to 2x" — tick multiplier = 1+0.4*(TotalAS%/150), same 150% AS
    cap as Summary!Actions Per Second (R_APS), so Cooldown(s) ranges 1s (0% AS) down to ~0.714s
    (150% AS cap) instead of a flat 1s. Base damage patched 22%->50% (rescaled 50/22=2.2727x
    before reverse-engineering), targets 1->3. Enchanted Quiver (Lv.107) is modeled as a "helper"
    row (own D/E/F Calc columns, no independent O) feeding an extra Final-Damage term + target
    count onto Quiver Cartridge's own K-column, patched 500%->300% FD (rescaled 300/500=0.6x).
  - Arrow Platter's per-level damage curve — idle.maplestorywiki.net/w/Arrow_Platter is a confirmed
    wiki content bug (renders Wind Arrow II's own infobox/table instead of Arrow Platter's own
    data, per its own single-revision edit history). RESOLVED this session: per user direction,
    the skill's real curve lives under an old/alternate page name, idle.maplestorywiki.net/w/
    Quiver_Flow — full level 1-200 curve (50%->100%, linear +2.5%/10 levels) resolving cleanly to
    factorIndex 12/baseDamage 500 tenths% (0% residual), plus the real Cooldown=40s from that
    page's own infobox (not 60s, this session's earlier unconfirmed guess that conflated cooldown
    with the skill's own 60s active-duration). Base targets patched 1->3, +1 more at Lv.98
    mastery (patched from +2).
  - Flash Mirage is a passive proc with a real 5s internal cooldown (its own wiki infobox lists
    "Cooldown: 5 sec" despite being Type=Passive) — modeled as a normal Cooldown(s)-gated row
    (CostsActionSlot=False) so its effective proc rate is capped at once per 5s times its 20%
    chance, using the same effective_cooldown/rate machinery as every cast-based row. Its own
    damage% (5%) does not scale with skill level (confirmed via the wiki's own curve, constant
    across levels 1-200) — factorIndex 0, non-scaling, matching Nimble Feet/Hurricane's own
    non-scaling treatment. Flash Mirage II (Lv.110) is a "helper" row analogous to Enchanted
    Quiver, feeding Flash Mirage's own K-column an extra FD term + target count.
  - Final Attack: Bow (Lv.50, 25% chance / 35%->49% additional damage) and Advanced Final Attack
    (Lv.105, +500%->900% FD to Final Attack specifically) are folded together as a steady-state
    average addition directly into Empowered Piercing Arrow's own coefficient (Calc!F), rather than built as
    an independent damage pipeline with its own separate Final Damage chain — a deliberate
    simplification (their own two-hop dependency, real MapleStory Final Attack triggering
    specifically off basic attacks, is folded into the basic attack's own average output instead
    of modeled as a fully independent multi-stage proc).
  - Concentration (wiki name) / Focused Fury (PDF name) — same skill, confirmed via cross-
    reference (Concentration's own wiki page + Marksman/Skills overview both show "+1 Accuracy /
    +3% Crit Damage for 4 sec, stacking up to 10 times" at level 1, matching the PDF's pre-patch
    values with an already-correct max-stack count of 10, not 7). Patched: duration 4s->6s,
    Accuracy +1->+3/stack (not modeled). Modeled at steady-state max stacks (10 x 3% = 30% Crit
    Damage), same convention as every other accumulating-stack passive in this project.
  - Mortal Blow (40 direct hits -> +10%->16% FD for 5s, patched 10%->12% base) is likewise modeled
    at steady state (assumed always active once unlocked), not as an exact hit-counter/timer state
    machine — the same simplification tier as Concentration above.
  - Marksmanship's patched "Base Attack +10%, additional +10% when 1 target" is modeled as TWO
    separate live Attack%-type rows: an unconditional half (always contributes) and a conditional
    half blended via the existing monster_blend_expr helper (boss/pvp -> full value, normal -> 0,
    breakthrough -> weighted) — the same blend mechanism already used for Boss/Normal Monster
    Damage%, just applied to the Attack% bucket instead. Combined additively with Illusion Step's
    own Attack% inside ONE bucket before the single (1+.../100) multiplication (Verification item
    6 in the plan — these must never multiply against each other).
  - Maple Hero (Lv.100, FD to Arrow Platter/Phoenix/Covering Fire) uses the same "one shared
    ratio-feeder row" mechanism as Shadower's own MAPLE_HERO_SHADOWER. Its own per-level curve
    was confirmed this session via idle.maplestorywiki.net/w/Maple_Hero_(Marksman) (full level
    1-200 curve, all three skills scale by the identical ratio at every level — 25%->195% Arrow
    Platter, 30%->234% Phoenix, 100%->780% Covering Fire — resolving cleanly to factorIndex 23/
    baseDamage 250 tenths%, 0% residual, same factorIndex Shadower's own Maple Hero uses).
  - Soul Arrow: Bow's DEX bonus (150->900, AS-scaled) and its own flat +8% Attack (patch-added) are
    always-on passives per this project's established convention (see build_shadower_workbook.py's
    README) — assumed already reflected in your own Inputs stat entries, not modeled as a live
    Calc-sheet formula. The +8% Attack component gets a Sensitivity-only delta row (matches
    Shadower's Channel Karma/Shadow Shifter Self-Attack treatment); the DEX component does NOT
    (no percentage-bucket home exists for a flat sub-stat bonus in this template — documented in
    the README instead, a deliberate scope-reduction from the plan's original ask).
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
OUT_PATH = REPO / "Marksman" / "Marksman-DPS-Calculator.xlsx"

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
# Inputs sheet row map — DEX main stat / STR sub, mechanical rename of Shadower's own LUK/DEX
# identity (formula shape unchanged, per the plan's confirmed stat-identity-agnostic finding).
# ---------------------------------------------------------------------------
# This fixed-size "Derived Values" block must stay SMALL and EARLY (right after TOTAL DPS at row
# 3), not after the variable-length summary tables — those grow with DAMAGE_DEALING_KEYS/
# STAT_SWEEP (about to grow further once Artifacts' ~36 equip-toggle rows land), and a hardcoded-
# after-them block silently collides once they grow past it (see build_bishop_workbook.py, where
# this was already happening).
DERIVED_HEADER_ROW = 5
D_ATTACK = 6                     # ATTACK = Flat ATTACK x (1+ATTACK%/100)
D_STAT_DAMAGE = 7                # STAT_DAMAGE% = 1% of total DEX + 0.25% of STR
D_BASIC_INPUT_LEVEL = 8          # Empowered Piercing Arrow input level (4th job formula)
D_BASIC_FACTOR = 9               # Empowered Piercing Arrow factor lookup (factorIndex 21)
D_SKILL_COEFFICIENT = 10         # Empowered Piercing Arrow base coefficient % before Skill Mastery
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
    "flat_dex": 12,
    "dex_pct": 13,
    "str": 14,
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


# Every Inputs row that can plausibly differ by content type (i.e. isn't itself a global/
# computed-from-content-type row) gets a per-content-type column layout — see build_inputs_sheet.
PER_CONTENT_TYPE_INPUT_KEYS = {
    k for k in IN if k not in COMPUTED_INPUT_ROWS and k not in ("level", "content_type")
}

# Equipped-artifact slots live on the Inputs sheet, appended after the class's own last existing
# row + a blank spacer row (45) — do not renumber any existing IN-dict row for this.
INPUT_ARTIFACT_SLOTS_SECTION_ROW = 46
INPUT_ARTIFACT_SLOT_ROWS = [47, 48, 49, 50]


def IB(key):
    if key in DERIVED_ROW:
        return f"Summary!$B${DERIVED_ROW[key]}"
    if key in ARTIFACT_INPUT_CELL:
        return ARTIFACT_INPUT_CELL[key]
    return f"Inputs!$B${IN[key]}"



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
    "Main Stat %": "dex_pct",
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


def build_readme_sheet(wb):
    ws = wb.active
    ws.title = "README"
    ws["A1"] = "Marksman — DPS Calculator: How to Use This Workbook"
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
        "Critical Shot, Archer Mastery, Bow Acceleration, Physical Training, Bow Mastery, "
        "Extreme Archery/Reckless Hunt: Bow's own Final Damage component, Armor Break, Bow "
        "Expert, and Soul Arrow: Bow's own DEX/Attack bonuses are always-on passives assumed to "
        "already be reflected in your own Inputs stat entries — only their Sensitivity marginal "
        "delta (what changes if their mastery level differs from what you assumed) is modeled "
        "live, matching this project's established convention (see build_shadower_workbook.py's "
        "own README). Soul Arrow: Bow's flat DEX bonus specifically has NO Sensitivity delta row "
        "(no percentage-bucket exists for a flat sub-stat bonus in this template) — just assume "
        "your own Inputs!Flat DEX already includes it.",
        "Concentration (\"Focused Fury\" in the Aug 13 patch notes — same skill, wiki and Nexon's "
        "own English patch notes use different names) and Mortal Blow are both modeled at "
        "steady-state maximum stacks/uptime once unlocked, not as exact stack-timer/hit-counter "
        "state machines — the same simplification tier as every other accumulating-stack "
        "mechanic in this project.",
        "Arrow Platter's per-level damage curve is confirmed via idle.maplestorywiki.net/w/"
        "Quiver_Flow (the skill's real curve lives under an old/alternate page name — its "
        "current-name page, .../w/Arrow_Platter, is a wiki content bug rendering Wind Arrow II's "
        "data instead). Its real cooldown (40s, not 60s) came from that same page's infobox.",
        "Quiver Cartridge's Attack-Speed-scaled tick rate uses the English wiki wording ('up to "
        "0.4 times based on Attack Speed') over the Korean text's disagreeing 'up to 2x', per "
        "user direction — tick multiplier = 1+0.4*(TotalAS%/150), same 150%-AS cap as Actions Per "
        "Second. Flash Mirage's own Attack-Speed-scaled activation-chance text is separately still "
        "too vague/self-contradictory (English vs. Korean disagree) to model precisely — it uses "
        "a flat, non-AS-scaled proc rate instead, flagged as a simplification.",
        "Final Attack: Bow + Advanced Final Attack are folded into Empowered Piercing Arrow's own coefficient "
        "as a steady-state average addition, not modeled as an independent damage pipeline with "
        "its own separate Final Damage chain.",
        "Maple Hero's own per-level scaling curve is confirmed via idle.maplestorywiki.net/w/"
        "Maple_Hero_(Marksman) — all three target skills (Arrow Platter/Phoenix/Covering Fire) "
        "scale by the identical ratio at every level, so one shared curve covers all three.",
        "Content Type (Inputs) picks what you're fighting — Chapter Boss/Breakthrough/PvP/EXP "
        "Dungeon/Equipment Dungeon/Weapon Dungeon/Enhancement Dungeon/Hero Dungeon/World Boss/"
        "Chapter Hunt — and Monster Defense and Fixed Fight Duration are both auto-computed from "
        "it (plus Chapter/Stage for the chapter- and dungeon-based types); PvP still forces its "
        "own fixed 15-second window and uses your own Defense stat as the opponent's Defense "
        "estimate. See README.md's 'Content Type' section for the exact formulas.",
        "Not modeled (out of scope): all forms of crowd control, Accuracy, Evasion, Defense "
        "reduction/penetration debuffs on the character's own Defense stat, movement speed, "
        "Illusion Step's own Evasion/damage-taken-reduction phase, and Companion Summoning Time.",
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
    ws["A1"] = "Marksman — DPS Calculator Inputs"
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
        ("attack_speed", "ATTACK_SPEED % (base, excludes Archer Mastery/Bow Acceleration)", 0),
        ("flat_dex", "Flat DEX (include Soul Arrow: Bow's own bonus if unlocked)", 0),
        ("dex_pct", "DEX %", 0),
        ("str", "STR", 0),
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
    # a given content type).
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

    # Equipped-artifact slots — one resolved column B (INDEX/MATCH against C:L, same mechanism as
    # every other per-content-type row) + per-content-type raw picks in C:L per slot. Appended
    # after everything else (row 45 left blank as a spacer) so no existing IN-dict row number has
    # to shift.
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

    ws.column_dimensions["A"].width = 55
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
    ws["A1"] = "Marksman — Artifacts (Equip Effect)"
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
        "Badge/Bottle of Emotion/Charm of the Undead — additive into the same bucket as "
        "Marksmanship's own conditional half)"
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
# Action-economy formula helpers — reused verbatim from build_shadower_workbook.py.
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


def boss_normal_dps_split_exprs(prefix_expr, monster_type_ref, boss_dmg_pct_expr,
                                 normal_dmg_pct_expr, normal_targets_ref, max_enemies_ref,
                                 extra_boss_mult_expr="1", extra_normal_mult_expr="1"):
    """Splits a row's DPS into independent boss-only and normal-only values, given `prefix_expr`
    (the H*N*rate*(extra multipliers) part shared by both). Each branch gets its own full
    (1+damage%/100)*target_count treatment; the two are blended into the real Total DPS as RATIOS
    (new/baseline) weighted by time spent, not as raw dollars weighted by branch size — dollar
    blending would let a stat's reported value be dominated by whichever branch happens to hit more
    targets, regardless of how much combat time is actually spent there. PvP is single-target with
    neither bonus, matching the old combined behavior.

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


def target_count_blend_expr(monster_type_ref, w_ref, normal_targets_ref, max_enemies_ref):
    """Target-count-only blend (no damage%) — for HitRate/trigger-frequency columns (e.g. Bolt
    Surplus's dual-trigger SUMPRODUCT), which count cast/hit frequency weighted by target count
    for multi-target trigger opportunities, but must NOT be weighted by Boss/Normal Monster
    Damage% the way a skill's own DPS contribution is (see boss_normal_dps_split_exprs). Kept
    separate since, post-split, O/N no longer cancels the damage% factor out the way the old
    single-formula O did — HitRate needs its own damage%-free reconstruction instead of O/N."""
    capped_targets = f'MIN({normal_targets_ref},{max_enemies_ref})'
    return f'IF({monster_type_ref}="pvp",1,(1-{w_ref})*1+{w_ref}*({capped_targets}))'


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
    the raw fight duration for buffs, or the buff-casting-startup-delay-reduced window for
    non-buff (damage) skills — and must match, or the last cast's truncated tick window would be
    computed against a duration inconsistent with how many casts were actually counted."""
    exact_hits = exact_total_hits_expr(row_ref, hits_ref, icd_ref, window_ref, cooldown_ref, available_duration_ref)
    return f'IF({fixed_duration_active_ref},({exact_hits}/{fight_duration_ref}),{steady_rate_ref})'


def level_gated_sum_raw(level_ref, pairs):
    ordered = sorted(pairs.items())
    thresholds = ",".join(str(level) for level, _ in ordered)
    increments = ",".join(str(inc) for _, inc in ordered)
    return f'SUMPRODUCT(({level_ref}>={{{thresholds}}})*{{{increments}}})'


def level_gated_sum(level_ref, pairs):
    return f'={level_gated_sum_raw(level_ref, pairs)}'


# ---------------------------------------------------------------------------
# Skills sheet schema — one bespoke column added vs. Bowmaster's own trimmed layout:
# TriggersBoltSurplus flags which rows' own HitRate(perSec) feed Bolt Surplus's combined
# dual-trigger rate (proc off BOTH Empowered Piercing Arrow and Snipe casts) — same
# SUMPRODUCT-over-a-boolean-column mechanism as Shadower's own TriggersToxicVenom column.
# ---------------------------------------------------------------------------
SKILL_COLUMNS = [
    "Key", "Name", "JobStep", "Cooldown(s)", "CostsActionSlot", "ActionsPerCast",
    "HitsPerCast", "ICD(s)", "ActiveWindow(s)", "ProcChance%", "RollsPerCast",
    "BaseDamage(tenths%)", "FactorIndex", "ScalesWithLevel",
    "SkillMasteryBonus%", "MasteryBossDamage%", "MasteryNormalDamage%",
    "NormalMonsterTargets", "BuffTargetStat", "BuffDuration(s)", "TriggersBoltSurplus",
    "MapleHeroBase(tenths%)", "MapleHeroFactorIndex", "Note",
]
SC = {name: get_column_letter(i + 1) for i, name in enumerate(SKILL_COLUMNS)}

# Row order (2..LAST_ROW) — derived from this list, never hand-numbered.
ROW_ORDER = [
    "EMPOWERED_PIERCING_ARROW", "FINAL_ATTACK_CROSSBOW_HELPER", "ADVANCED_FINAL_ATTACK_HELPER",
    "COVERING_FIRE", "BOLT_BURST", "FROSTPREY", "MAPLE_HERO_HELPER",
    "SNIPE", "BOLT_SURPLUS", "ARROW_ILLUSION", "BLINK_BOLT",
    "MARKSMANSHIP_BASE", "MARKSMANSHIP_COND", "ILLUSION_STEP",
    "SHARP_EYES", "MORTAL_BLOW",
    "NIMBLE_FEET",
    "CRITICAL_SHOT", "ARCHER_MASTERY", "CROSSBOW_ACCELERATION", "PHYSICAL_TRAINING",
    "CROSSBOW_MASTERY", "RECKLESS_HUNT_CROSSBOW", "LAST_MAN_STANDING_FD", "LAST_MAN_STANDING_COND",
    "CROSSBOW_EXPERT_SKILL", "CROSSBOW_EXPERT_MAXDMG", "SOUL_ARROW_CROSSBOW_ATK",
]
ROW = {key: i for i, key in enumerate(ROW_ORDER, start=2)}
LAST_ROW = 1 + len(ROW_ORDER)

# ---------------------------------------------------------------------------
# Summary-sheet row layout — fixed constants (plain literals, not len()-derived, since the
# Summary "info dump" block has a fixed size/shape across every class in this project, unlike the
# variable-length Skills-sheet table above). Defined here, ahead of SKILL_ROWS, so SKILL_ROWS
# entries (e.g. Quiver Cartridge's AS-scaled cooldown) can reference them directly — SKILL_ROWS is
# a module-level list literal evaluated immediately at import time, so any constant it references
# must already exist textually above it.
# ---------------------------------------------------------------------------
R_TOTAL = 3
R_AVGBUFF = 13                     # Attack% bucket (Marksmanship base+cond + Illusion Step)
R_CRIT_RATE_BONUS = 14              # Sharp Eyes (flat 20, duty-cycle averaged)
R_MONSTER_DMG_BONUS = 15            # Artifact Enemy Damage Taken Bonus (Peach Tree/Silver Pendant)
R_AS_BONUS = 16                     # Nimble Feet, duty-cycle averaged
R_APS = 17                          # Actions Per Second
R_CASTRATE = 18                     # Skill + buff cast rate (subtracted from Empowered Piercing Arrow)
R_BAPS = 19                         # Empowered Piercing Arrow (basic attack) Casts Per Second
R_CRIT_DAMAGE_BONUS = 20            # Sharp Eyes (scaling) + Concentration (steady-state max stacks)
R_MORTAL_BLOW_BONUS = 21            # Mortal Blow, steady-state always-active FD bonus
R_EMPOWERED_PIERCING_ARROW_DPS = 22
R_STARTUP_TIME = 23                 # Buff-Casting Startup Delay (s, fixed-duration only)
R_BOSS_ONLY_TOTAL = 24               # Total DPS if every hit were against a boss (Breakthrough Sensitivity baseline)
R_NORMAL_ONLY_TOTAL = 25             # Total DPS if every hit were against normal monsters (Breakthrough Sensitivity baseline)
# The two variable-length summary tables (Per-Skill DPS Breakdown, Marginal DPS & Stat Value)
# start after this fixed block, with a 2-row gap — not hardcoded before it, since they grow with
# DAMAGE_DEALING_KEYS/STAT_SWEEP (see the D_ATTACK block's own comment above).
BREAKDOWN_SECTION_ROW = R_NORMAL_ONLY_TOTAL + 2
SUMMARY_BREAKDOWN_HEADER_ROW = BREAKDOWN_SECTION_ROW + 1

# Unlock level for every row — gated all the way down (matches every sibling workbook's
# thorough approach). Levels confirmed live from idle.maplestorywiki.net/w/Marksman/Skills
# this session (Sept 2026).
UNLOCK_LEVEL = {
    "EMPOWERED_PIERCING_ARROW": 100,
    "FINAL_ATTACK_CROSSBOW_HELPER": 50,
    "ADVANCED_FINAL_ATTACK_HELPER": 105,
    "COVERING_FIRE": 35,
    "BOLT_BURST": 63,
    "FROSTPREY": 69,
    "MAPLE_HERO_HELPER": 100,
    "SNIPE": 103,
    "BOLT_SURPLUS": 107,
    "ARROW_ILLUSION": 110,
    "BLINK_BOLT": 60,
    "MARKSMANSHIP_BASE": 74,
    "MARKSMANSHIP_COND": 74,
    "ILLUSION_STEP": 117,
    "SHARP_EYES": 115,
    "MORTAL_BLOW": 72,
    "CRITICAL_SHOT": 15,
    "ARCHER_MASTERY": 10,
    "CROSSBOW_ACCELERATION": 33,
    "PHYSICAL_TRAINING": 38,
    "CROSSBOW_MASTERY": 43,
    "RECKLESS_HUNT_CROSSBOW": 75,
    "LAST_MAN_STANDING_FD": 125,
    "LAST_MAN_STANDING_COND": 125,
    "CROSSBOW_EXPERT_SKILL": 120,
    "CROSSBOW_EXPERT_MAXDMG": 120,
    "SOUL_ARROW_CROSSBOW_ATK": 45,
    # NIMBLE_FEET: no threshold (shared Explorer skill, level 0) — stays unconditionally unlocked.
}


def unlock_expr(key):
    level = UNLOCK_LEVEL.get(key)
    return "=TRUE" if level is None else f"={IB('level')}>={level}"


# Maple Hero (Lv.100) — confirmed live from idle.maplestorywiki.net/w/Maple_Hero_(Marksman)
# this session: uses the EXACT SAME numbers as Maple Hero (Bowmaster) at every level (25%->195%
# Bolt Burst, 30%->234% Frostprey, 100%->780% Covering Fire — byte-identical to Bowmaster's own
# Arrow Platter/Phoenix/Covering Fire slots), so both the ratios AND the resolved tuple
# (factorIndex 23/baseDamage 250 tenths%) are reused verbatim from build_bowmaster_workbook.py.
MAPLE_HERO_RATIOS = {
    "BOLT_BURST": 25 / 25,
    "FROSTPREY": 30 / 25,
    "COVERING_FIRE": 100 / 25,
}

# (key, name, jobstep, cooldown, costsAction, actionsPerCast, hits, icd, window, chance, rolls,
#  baseDamage, factorIndex, scales, skillMasteryBonusPct, masteryBossDmgPct, masteryNormalDmgPct,
#  normalMonsterTargets, buffTarget, buffDuration, triggersBoltSurplus, mapleBase, mapleFactor, note)
SKILL_ROWS = [
    ("EMPOWERED_PIERCING_ARROW", "Empowered Piercing Arrow", 4, "", False, 1,
     f'=IF({IB("level")}>=134,6,5)', 0, 0, 100, 1,
     2900, 21, True,
     # Final Attack: Crossbow (25% chance, 35%->49% additional dmg, +50% mastery @Lv.52) +
     # Advanced Final Attack (+500%->900% FD, +50% mastery @Lv.111) folded together as a
     # steady-state average addition, PLUS Empowered Piercing Arrow's own real Damage/Boss
     # Monster Damage mastery bonuses (confirmed via Marksman/Mastery this session — Lv.98/104/
     # 113/118/126/130 Damage +10/11/12/13/14/15%, Lv.108/122 Boss Monster Damage +10/10%).
     # Bowmaster's own Arrow Stream row was found missing this exact same mastery pattern (plus
     # the analogous HitsPerCast=5->6@Lv.134 fix) during this cross-check — since fixed there too.
     f"=Calc!F{{FINAL_ATTACK_CROSSBOW_HELPER}}*IF(Calc!C{{FINAL_ATTACK_CROSSBOW_HELPER}}=TRUE,1,0)/100"
     f"*(1+Calc!F{{ADVANCED_FINAL_ATTACK_HELPER}}*IF(Calc!C{{ADVANCED_FINAL_ATTACK_HELPER}}=TRUE,1,0)/100)"
     f"*25",
     level_gated_sum(IB("level"), {108: 10, 122: 10}),
     0,
     f'=6+{IB("basic_attack_target_increase")}', "", 0, True, "", "",
     "4th-job basic-attack effect (supersedes Piercing Arrow/Piercing Arrow II/Arrow Blow, "
     "confirmed identical wiki wording — 290% damage to 6 target(s) in front 5 time(s) — to "
     "every other class's own 4th-job basic attack, including Bowmaster's own Arrow Stream). "
     "factorIndex 21, baseDamage 2900 tenths%. HitsPerCast = 5 (the wiki's own 'time(s)' "
     "figure), bumping to 6 once Mastery Lv.134 'Empowered Piercing Arrow - Strike' unlocks "
     "(confirmed via Marksman/Mastery this session — same pattern/level as Bowmaster's own "
     "Arrow Stream and Night Lord's own Showdown). SkillMasteryBonus% combines Final Attack: "
     "Crossbow + Advanced Final Attack's own steady-state contribution (ProcChance x "
     "AdditionalDamage% x (1+AdvancedFD%/100) x 25, the x25 converting Final Attack's own "
     "attack-triggered percentage into an equivalent addition to Empowered Piercing Arrow's "
     "per-hit coefficient at its own 5-hit-per-cast rate) PLUS the real level-gated Damage "
     "mastery chain (98/104/113/118/126/130, cumulative +10/11/12/13/14/15% per the wiki's own "
     "tooltip display — level_gated_sum uses DELTA increments (10, then +1 five times) to "
     "reproduce that cumulative curve, not the raw displayed percentages summed directly, same "
     "convention as Night Lord's own Showdown mastery and Bowmaster's own Arrow Stream mastery; "
     "an earlier version of this row summed the raw displayed values directly, giving a wrong "
     "75% total instead of the correct 15% — caught and fixed during this session's own "
     "cross-check against Night Lord's established precedent). "
     "MasteryBossDamage% is the real Boss Monster Damage mastery sum (+10/10% at Lv.108/122, "
     "20% total). TriggersBoltSurplus=TRUE — this row's own HitRate(perSec) feeds Bolt "
     "Surplus's combined dual-trigger rate."),
    ("FINAL_ATTACK_CROSSBOW_HELPER", "Final Attack: Crossbow (helper)", 2, "", False, 1, 1, 0, 0, 100, 1,
     350, 21, True,
     level_gated_sum(IB("level"), {52: 50}), 0, 0, 0, "", 0, False, "", "",
     "Helper row only (no independent O-column DPS) — feeds Empowered Piercing Arrow's own "
     "coefficient. 25% chance, 35%->49% additional damage (levels 1-100), shared-value-"
     "different-key w/ Bowmaster's own Final Attack: Bow (confirmed identical curve via its own "
     "individual page). factorIndex 21, baseDamage 350 tenths%. Mastery Lv.52 'Final Attack - "
     "Damage' +50% (real SkillMasteryBonus%, confirmed via Marksman/Mastery this session — a "
     "bonus Bowmaster's own equivalent helper row may also be missing, not checked this "
     "session). Not otherwise patched (Aug 13 2026 patch notes make no mention of this skill)."),
    ("ADVANCED_FINAL_ATTACK_HELPER", "Advanced Final Attack (helper)", 4, "", False, 1, 1, 0, 0, 100, 1,
     5000, 21, True,
     level_gated_sum(IB("level"), {111: 50}), 0, 0, 0, "", 0, False, "", "",
     "Helper row only — feeds Empowered Piercing Arrow's own coefficient (Final Attack's own "
     "Final Damage bonus). +500%->900% FD (levels 1-200), shared verbatim w/ Bowmaster (confirmed "
     "identical curve via its own individual page). factorIndex 21, baseDamage 5000 tenths%. "
     "Mastery Lv.111 'Advanced Final Attack - Enhance' +50% (real SkillMasteryBonus%, confirmed "
     "via Marksman/Mastery this session — Bowmaster's own equivalent helper row is missing this "
     "bonus, flagged for the coordinator, not fixed here)."),
    ("COVERING_FIRE", "Covering Fire", 1, 19, True, 1, 3, 0, 0, 100, 1,
     2500, 12, True,
     level_gated_sum(IB("level"), {39: 50}), 0, 0, 1, "", 0, False, 250, 0,
     "Shared verbatim w/ Bowmaster (identical name AND numbers both classes, confirmed via its "
     "own Marksman-side page 'Retreat_Shot' this session, and via the patch notes' own shared "
     "'Covering Fire' entry). 250%->375% damage x3 hits (levels 1-100), 19s cooldown. "
     "factorIndex 12, baseDamage 2500 tenths%. Mastery Lv.39 'Covering Fire - Damage' +50% "
     "(real SkillMasteryBonus%). Patched: skill use range +~20% (not modeled). Maple Hero "
     "target — see MAPLE_HERO_RATIOS (biggest share, 4x Bolt Burst's own share)."),
    ("BOLT_BURST", "Bolt Burst", 3, 21, True, 1, 3, 0, 0, 100, 1,
     4500, 12, True,
     level_gated_sum(IB("level"), {66: 50}), 0, 0, 10, "", 0, False, 250, 0,
     "Real page name is 'Bolt Flash' (confirmed via the Marksman/Skills overview page's own "
     "<a href> link — same 'display name differs from page slug' pattern as Bowmaster's own "
     "Arrow Platter/Quiver Flow, though this page itself is NOT bugged, its content matches its "
     "own infobox/description correctly). 'Shoots arrows in multiple directions to deal 450% "
     "damage to 10 nearby target(s) 3 time(s)', 21s cooldown. PATCHED: base damage 380%->450% "
     "(curve rescaled 450/380=1.1842x before reverse-engineering — factorIndex 12, baseDamage "
     "4500 tenths% already reflects the patched value), attack range +~15% (not modeled). "
     "Mastery Lv.66 'Bolt Burst - Damage' +50% (real SkillMasteryBonus%). Maple Hero target — "
     "see MAPLE_HERO_RATIOS."),
    ("FROSTPREY", "Frostprey", 3, f'=IF({IB("level")}>=102,60*0.6,60)', True, 1,
     1, 1.5,
     30, 100, 1,
     3000, 12, True,
     level_gated_sum(IB("level"), {80: 50}), 0,
     f'=IF({IB("level")}>=92,100,0)',
     f'=3+IF({IB("level")}>=76,2,0)', "", 0, False, 250, 0,
     "Real page name is 'Freezer' (confirmed via the Marksman/Skills overview page's own href "
     "link — same page-name-differs-from-display-name pattern as Bowmaster's own Arrow Platter/"
     "Quiver Flow). Summons Frostprey, attacks nearby targets on a periodic tick (EffectiveHits "
     "= HitsPerCast x (ActiveWindow/ICD), same mechanism as FP-Mage/ILM's own summon rows and "
     "Bowmaster's own Phoenix). PATCHED: hit interval 3s->1.5s (baked into ICD(s) directly, "
     "confirmed via the PDF as belonging to Frostprey itself, not Bolt Burst — resolves the "
     "prior session's own Frostprey/Bolt Burst pairing ambiguity), damage 600%->300% (curve "
     "rescaled 300/600=0.5x before reverse-engineering — factorIndex 12, baseDamage 3000 "
     "tenths% already reflects the patched value), freeze chance 20%->10% (CC, not modeled), "
     "duration 20s->30s (target detection range +~25% not modeled). Cooldown 60s, Mastery "
     "Lv.102 'Frostprey - Reuse' -50%->-40% per the patch (this session's own live wiki fetch "
     "confirms the mastery sits at level 102, not the PDF section header's stated 'Lv.104' — "
     "same judgment call Bowmaster's own build already made for its analogous Phoenix - Reuse "
     "mastery, trusting the wiki's level-threshold table over the PDF's own row-label level). "
     "Mastery Lv.76 'Frostprey - Target' +2 targets (base 3, wiki-confirmed — NOT the same +3 "
     "Bowmaster's own Phoenix gets at its own Lv.76 slot, a genuine per-class difference despite "
     "the shared level number), Lv.80 'Frostprey - Damage' +50% (real SkillMasteryBonus%), "
     "Lv.92 'Frostprey - Normal Monster Damage' +100%p (own MasteryNormalDamage%, scoped to "
     "this row only — not the global bucket). Maple Hero target — see MAPLE_HERO_RATIOS."),
    ("MAPLE_HERO_HELPER", "Maple Hero (helper)", 4, "", False, 1, 1, 0, 0, 100, 1,
     250, 23, True,
     0, 0, 0, 0, "", 0, False, "", "",
     "Shared ratio-feeder row (see MAPLE_HERO_RATIOS) for Bolt Burst/Frostprey/Covering Fire's "
     "own Final Damage chains — mirrors Shadower's own MAPLE_HERO_SHADOWER mechanism and "
     "Bowmaster's own MAPLE_HERO_HELPER. Confirmed this session via idle.maplestorywiki.net/w/"
     "Maple_Hero_(Marksman): uses the EXACT SAME numbers as Maple Hero (Bowmaster) at every "
     "level (not just the same ratio-shape), so this row's own (baseDamage, factorIndex) tuple "
     "is reused verbatim (factorIndex 23/baseDamage 250 tenths%, 0% residual). No independent "
     "DPS row of its own (Calc columns J-N blank/0, only D/E/F computed, read directly by each "
     "target row's own K-column formula — same 'no independent row' pattern as Shadower's own "
     "Maple Hero)."),
    ("SNIPE", "Snipe", 4, 12, True, 1, 1, 0, 0, 100, 1,
     38000, 12, True,
     f'={level_gated_sum_raw(IB("level"), {106: 50})}'
     f'+IF({IB("level")}>=134,570*(Calc!E{ROW["SNIPE"]}/1000),0)',
     0, 0, 1, "", 0, True, "", "",
     "Single-target big hit: 'Aims at the target's vital point to deal 3800% damage', 12s "
     "cooldown (own wiki infobox), not patched. factorIndex 12, baseDamage 38000 tenths% "
     "(3800%->7600%, levels 1-200). Mastery Lv.106 'Snipe - Damage' +50% (real "
     "SkillMasteryBonus%). Mastery Lv.134 'Snipe - Empowered' (confirmed by user, not the "
     "wiki's own raw table order which mis-parsed as 132 due to this entry's unusually "
     "multi-part description cell): 'Leaves a mark on targets damaged by Snipe. When attacking "
     "marked targets with Snipe, deals {#expr:5700*(1+x*0.005)}% damage (Damage increases with "
     "Snipe skill level)' — resolves cleanly (0.44% max deviation) to the SAME factorIndex 12 "
     "as Snipe's own base curve, baseDamage 5700 tenths%, so it reuses Snipe's own Calc!E "
     "factor-lookup cell directly rather than needing a separate FactorTable lookup. Modeled at "
     "the same steady-state-always-active convention as Concentration/Mortal Blow, per user "
     "direction ('it's the same rate as the Snipe skill') — the mark persists across the "
     "single-target rotation this project already assumes, so every steady-state Snipe cast "
     "after unlock also deals this additive bonus. TriggersBoltSurplus=TRUE — this row's own "
     "HitRate(perSec) feeds Bolt Surplus's combined dual-trigger rate alongside Empowered "
     "Piercing Arrow."),
    ("BOLT_SURPLUS", "Bolt Surplus", 4, "", False, 1, f'=2+IF({IB("level")}>=136,1,0)', 0, 0, 15, 1,
     6500, 21, True,
     level_gated_sum(IB("level"), {120: 50}), 0, 0,
     f'=3+IF({IB("level")}>=136,2,0)', "", 0, False, "", "",
     "Dual-trigger proc: 'When attacking with Empowered Piercing Arrow and Snipe, an extra "
     "explosion occurs with a 15% [chance] to deal 650% damage to 3 nearby target(s) 2 "
     "time(s)', own wiki infobox lists 'Cooldown: 0.1 sec' (functionally non-restrictive vs. "
     "its own 15% proc gate — modeled with NO Cooldown(s) field at all, like Shadower's own "
     "Toxic Venom, since its O-column DPS bypasses the normal per-row cooldown/rate machinery "
     "entirely). Combined trigger rate = the summed per-second hit rate of every row flagged "
     "TriggersBoltSurplus=TRUE (Empowered Piercing Arrow + Snipe) — same SUMPRODUCT-over-a-"
     "boolean-column mechanism as Shadower's own TriggersToxicVenom, applied here to exactly "
     "two specific trigger sources instead of every damage row. Not patched. factorIndex 21, "
     "baseDamage 6500 tenths% (650%->1170%, levels 1-200). Mastery Lv.120 'Bolt Surplus - "
     "Damage' +50% (real SkillMasteryBonus%), Lv.136 'Bolt Surplus - Strike & Target' +1 "
     "strike/+2 targets (HitsPerCast 2->3, NormalMonsterTargets 3->5, both live level-gated "
     "once Lv.136 hits)."),
    ("ARROW_ILLUSION", "Arrow Illusion", 4, 45, True, 1, 1, 1.5, 25, 100, 1,
     12000, 12, True,
     level_gated_sum(IB("level"), {128: 50}), 0, 0, 10, "", 0, False, "", "",
     "Channeled turret: 'Summons an illusionary arrow...binds nearby targets for 3 sec (CC, "
     "not modeled), and attacks 10 nearby target(s) every 3 sec for 25 sec to deal 2400% "
     "damage', 45s cooldown (own wiki infobox), same EffectiveHits tick mechanism as Frostprey/"
     "Bowmaster's own Phoenix. PATCHED: hit interval 3s->1.5s (baked into ICD(s)), damage "
     "2400%->1200% (curve rescaled 1200/2400=0.5x before reverse-engineering — factorIndex 12, "
     "baseDamage 12000 tenths% already reflects the patched value), added 'max 1 placement at "
     "a time' (self-uptime cap already implicit in this project's single-instance summon "
     "treatment, no code change needed). Mastery Lv.128 'Arrow Illusion - Damage' +50% (real "
     "SkillMasteryBonus%; the same mastery tier also adds a bind-on-expiry CC effect, not "
     "modeled)."),
    ("BLINK_BOLT", "Blink Bolt", 3, "", False, 1, 1, 0, 0, 100, 1,
     250, 22, True,
     0, 0, 0, 0, "ATTACK", 0, False, "", "",
     "'Creates a special mark for 30 sec. While the mark lasts, increases Attack by 25%->40% "
     "(levels 1-200). When you use this skill again, you move to the mark's location and the "
     "mark disappears.' Own wiki infobox confirms Cooldown=10s (matches the prior session's own "
     "direct confirmation) — but the skill's own description is a TOGGLE (recast consumes/"
     "teleports the mark, ending the buff), not a typical refresh-on-recast buff like Nimble "
     "Feet. FLAGGED modeling caveat: this row is modeled as an unconditional always-on Attack% "
     "contribution (no duty-cycle/uptime computation at all, same treatment as Marksmanship's "
     "own unconditional half) per this session's directive to use the plan's own stated "
     "assumption ('since duration(30s) > cooldown(10s), effectively a permanent buff at full "
     "uptime') rather than modeling the toggle mechanic's real alternating on/off behavior in "
     "auto-combat, which could plausibly yield a lower ~50% uptime instead — a human should "
     "revisit this if real gameplay data suggests otherwise. Not patched. factorIndex 22, "
     "baseDamage 250 tenths%. Teleport-movement component out of scope."),
    ("MARKSMANSHIP_BASE", "Marksmanship (unconditional half)", 3, "", False, 1, 1, 0, 0, 100, 1,
     100, 22, True,
     0, 0, 0, 0, "ATTACK", 0, False, "", "",
     "PATCHED: 'Base Attack +10%, additional +10% when 1 target' replaces the old flat '+20% at "
     "1 target only' wording — modeled as two separate rows (this unconditional half + "
     "MARKSMANSHIP_COND's conditional half), summed additively into the same Attack% bucket as "
     "Illusion Step (Verification item 6 — these must never multiply against each other). Half "
     "of the wiki's own pre-patch curve (10%->16%, levels 1-200), assumed symmetric 50/50 split "
     "at every level (the patch note only confirms the level-1 split, 10/10) — factorIndex 22, "
     "baseDamage 100 tenths%. Shared verbatim w/ Bowmaster (identical name, wording, and numbers "
     "confirmed both classes via the patch notes' own shared 'Marksmanship' entry, and via this "
     "session's own live fetch of Marksman's own Marksmanship page)."),
    ("MARKSMANSHIP_COND", "Marksmanship (conditional half, 1 target)", 3, "", False, 1, 1, 0, 0, 100, 1,
     100, 22, True,
     0, 0, 0, 0, "ATTACK_COND_1TARGET", 0, False, "", "",
     "Conditional half of Marksmanship's own patched Attack% bonus — blended via the same "
     "monster_blend_expr helper already used for Boss/Normal Monster Damage% (boss/pvp -> full "
     "value, normal -> 0, breakthrough -> weighted), applied to the Attack% bucket instead. Same "
     "curve/tuple as MARKSMANSHIP_BASE (factorIndex 22, baseDamage 100 tenths%)."),
    ("ILLUSION_STEP", "Illusion Step", 4, 24, False, 1, 1, 0, 0, 100, 1,
     140, 22, True,
     0, 0, 0, 0, "ATTACK", 15, False, "", "",
     "Cycling passive: Attack+14%->22.4% for 15s, then swaps to Evasion+15->24/damage taken "
     "-10%->16% for 9s (not modeled — those components have no mechanic anywhere in this "
     "calculator). Modeled as a duty-cycled buff (Cooldown(s)=24 = full 15+9s cycle length, "
     "BuffDuration(s)=15 = the Attack-active portion, giving a 0.625 duty-cycle uptime) — same "
     "buff_uptime machinery as every other timed buff in this project. factorIndex 22, "
     "baseDamage 140 tenths%. Not patched. Shared verbatim w/ Bowmaster (confirmed via this "
     "session's own live fetch of Marksman's own Illusion Step page)."),
    ("SHARP_EYES", "Sharp Eyes", 4, 35, True, 1, 1, 0, 0, 100, 1,
     400, 21, True,
     0, 0, 0, 0, "CRIT_DAMAGE", 18, False, "", "",
     "Self-inclusive ally buff (matches Bishop's own 'allied players' precedent) — flat +20% "
     "Crit Rate (non-scaling, not represented in this row's own BaseDamage/FactorIndex; added "
     "directly as a hardcoded 20 in the Crit-Rate-bonus accumulator formula in build_summary_"
     "sheet) + scaling Crit Damage +40%->72% (levels 1-200, this row's own curve — factorIndex "
     "21, baseDamage 400 tenths%) for 18s, cooldown 35s. Not patched. Shared verbatim w/ "
     "Bowmaster (confirmed via this session's own live fetch of Marksman's own Sharp Eyes page)."),
    ("MORTAL_BLOW", "Mortal Blow", 3, "", False, 1, 1, 0, 0, 100, 1,
     120, 22, True,
     0, 0, 0, 0, "FINAL_DAMAGE", 0, False, "", "",
     "Upon attacking a target directly 40 times, +10%->16%(pre-patch curve) FD for 5s. Modeled "
     "at steady state (assumed always active once unlocked), not an exact hit-counter/timer "
     "state machine — same simplification tier every other steady-state buff in this project "
     "uses. PATCHED: base 10%->12% (curve rescaled 12/10=1.2x before reverse-engineering — "
     "factorIndex 22, baseDamage 120 tenths% already reflects the patched value). Shared "
     "verbatim w/ Bowmaster (confirmed via this session's own live fetch of Marksman's own "
     "Mortal Blow page)."),
    ("NIMBLE_FEET", "Nimble Feet", 1, 60, True, 1, 1, 0, 0, 100, 1,
     150, 0, False,
     0, 0, 0, 1, "ATTACK_SPEED", 15, False, "", "",
     "Shared cross-tree verbatim w/ Night Lord/Shadower/FP-Mage/Bowmaster (byte-identical wiki "
     "wording — '+15% Attack Speed, +10% Speed for 15 sec'). Flat +15% Attack Speed / +10% "
     "Speed for 15s, 60s cooldown, non-scaling. FactorIndex unused placeholder."),
    ("CRITICAL_SHOT", "Critical Shot", 1, "", False, 1, 1, 0, 0, 100, 1,
     50, 22, True,
     0, 0, 0, 0, "CRIT_RATE", 0, False, "", "",
     "Magic Critical pattern — already baked into Inputs!CRIT_RATE%; feeds the 1st-Job Skill "
     "Level Bonus delta. factorIndex 22, baseDamage 50 tenths% (5%->6.5%, levels 1-100). "
     "Shared verbatim w/ Bowmaster (byte-identical wiki wording, confirmed both classes)."),
    ("ARCHER_MASTERY", "Archer Mastery (Attack Speed)", 1, "", False, 1, 1, 0, 0, 100, 1,
     50, 22, True,
     0, 0, 0, 0, "ATTACK_SPEED", 0, False, "", "",
     "Magic Critical pattern — already baked into Inputs!ATTACK_SPEED%; feeds the 1st-Job Skill "
     "Level Bonus delta. factorIndex 22, baseDamage 50 tenths% (5%->6.5%, levels 1-100). Own "
     "Speed component not modeled. Shared verbatim w/ Bowmaster (byte-identical wiki wording)."),
    ("CROSSBOW_ACCELERATION", "Crossbow Acceleration", 2, "", False, 1, 1, 0, 0, 100, 1,
     50, 22, True,
     0, 0, 0, 0, "ATTACK_SPEED", 0, False, "", "",
     "Real page name is 'Crossbow_Acceleration' (not 'Agile_Crossbows', despite that being the "
     "skill's own display name on the Marksman/Skills overview page — confirmed via the "
     "overview page's own href link). Magic Critical pattern — already baked into "
     "Inputs!ATTACK_SPEED%; feeds the 2nd-Job Skill Level Bonus delta. factorIndex 22, "
     "baseDamage 50 tenths% (5%->6.5%, levels 1-100). Shared-value-different-key w/ Bowmaster's "
     "own Bow Acceleration (confirmed identical curve via its own individual page)."),
    ("PHYSICAL_TRAINING", "Physical Training", 2, "", False, 1, 1, 0, 0, 100, 1,
     100, 22, True,
     0, 0, 0, 0, "BASIC_ATTACK_DAMAGE", 0, False, "", "",
     "Magic Critical pattern — already baked into Inputs!BASIC_ATTACK_DAMAGE%; feeds the "
     "2nd-Job Skill Level Bonus delta. factorIndex 22, baseDamage 100 tenths% (10%->13%, levels "
     "1-100). Shared verbatim w/ Bowmaster (byte-identical wiki wording, confirmed both "
     "classes)."),
    ("CROSSBOW_MASTERY", "Crossbow Mastery", 2, "", False, 1, 1, 0, 0, 100, 1,
     150, 22, True,
     0, 0, 0, 0, "MIN_DAMAGE", 0, False, "", "",
     "Magic Critical pattern — already baked into Inputs!MIN_DAMAGE%; feeds the 2nd-Job Skill "
     "Level Bonus delta. factorIndex 22, baseDamage 150 tenths% (15%->19.5%, levels 1-100). "
     "Shared-value-different-key w/ Bowmaster's own Bow Mastery (confirmed identical curve via "
     "its own individual page)."),
    ("RECKLESS_HUNT_CROSSBOW", "Extreme Archery / Reckless Hunt: Crossbow", 3, "", False, 1, 1, 0, 0, 100, 1,
     150, 22, True,
     0, 0, 0, 0, "FINAL_DAMAGE", 0, False, "", "",
     "Own Final Damage component only (Defense reduction not modeled — no Defense mechanic "
     "exists anywhere in this calculator). Magic Critical pattern — already baked into "
     "Inputs!FINAL_DAMAGE%; feeds the 3rd-Job Skill Level Bonus delta. factorIndex 22, "
     "baseDamage 150 tenths% (15%->24%, levels 1-200). PATCHED name: wiki still shows 'Extreme "
     "Archery: Crossbow', Aug 13 patch notes confirm current name 'Reckless Hunt: Crossbow' "
     "(-10%->-5% Defense, not modeled either way; FD component itself unpatched). Shared-value-"
     "different-key w/ Bowmaster's own Reckless Hunt: Bow (confirmed identical curve via its "
     "own individual page)."),
    ("LAST_MAN_STANDING_FD", "Last Man Standing (base FD)", 4, "", False, 1, 1, 0, 0, 100, 1,
     150, 22, True,
     0, 0, 0, 0, "FINAL_DAMAGE", 0, False, "", "",
     "Marksman's own 4th-job Final-Damage passive slot (NOT shared with Bowmaster's Armor "
     "Break — a genuinely different mechanic per the plan). 'Increases Final Damage by "
     "15%->24% (levels 1-200). If there is 1 enemy, additionally increased by 5%->8.9%.' This "
     "row models the unconditional base-FD half; see LAST_MAN_STANDING_COND for the "
     "conditional 1-enemy half. Magic Critical pattern — already baked into "
     "Inputs!FINAL_DAMAGE%; feeds the 4th-Job Skill Level Bonus delta. factorIndex 22, "
     "baseDamage 150 tenths%. Not patched."),
    ("LAST_MAN_STANDING_COND", "Last Man Standing (1-enemy conditional FD)", 4, "", False, 1, 1, 0, 0, 100, 1,
     50, 22, True,
     0, 0, 0, 0, "FINAL_DAMAGE", 0, False, "", "",
     "Conditional +5%->6.9%(levels 1-140, own confirmed curve range) Final Damage half of Last "
     "Man Standing, active only at 1 target (boss or pvp — confirmed by user). Modeled as a "
     "LIVE row, same monster_blend_expr mechanism as Marksmanship's own conditional Attack% "
     "half (full value at boss/pvp, zero at normal, weighted at breakthrough), folded "
     "additively into R_MORTAL_BLOW_BONUS's own Final Damage bucket alongside Mortal Blow — an "
     "earlier version of this row assumed Final Damage had no per-monster-type blend mechanism "
     "and left it flat/baked into Inputs, which was wrong; the same blend mechanism Attack% "
     "already uses applies here too, just added as another multiplicative-chain contributor "
     "instead of an Attack%-bucket one. factorIndex 22, baseDamage 50 tenths%."),
    ("CROSSBOW_EXPERT_SKILL", "Crossbow Expert (Skill Damage)", 4, "", False, 1, 1, 0, 0, 100, 1,
     150, 22, True,
     0, 0, 0, 0, "SKILL_DAMAGE", 0, False, "", "",
     "Magic Critical pattern — already baked into Inputs!SKILL_DAMAGE%; feeds the 4th-Job Skill "
     "Level Bonus delta (Skill Damage side). factorIndex 22, baseDamage 150 tenths% (15%->24%, "
     "levels 1-200). Not patched. Shared-value-different-key w/ Bowmaster's own Bow Expert "
     "(confirmed identical curve via its own individual page)."),
    ("CROSSBOW_EXPERT_MAXDMG", "Crossbow Expert (Max Damage Multiplier)", 4, "", False, 1, 1, 0, 0, 100, 1,
     200, 22, True,
     0, 0, 0, 0, "MAX_DAMAGE", 0, False, "", "",
     "Same skill as Crossbow Expert (Skill Damage) above, +20%->32% Max Damage Multiplier. "
     "Magic Critical pattern — already baked into Inputs!MAX_DAMAGE%; feeds the 4th-Job Skill "
     "Level Bonus delta (Max Damage Multiplier side). factorIndex 22, baseDamage 200 tenths%."),
    ("SOUL_ARROW_CROSSBOW_ATK", "Soul Arrow: Crossbow (Attack%)", 2, "", False, 1, 1, 0, 0, 100, 1,
     120, 22, True,
     0, 0, 0, 0, "ATTACK", 0, False, "", "",
     "Genuinely different mechanic from Bowmaster's own Soul Arrow: Bow (flat Attack%, no "
     "AS-scaling, no DEX bonus at all — per the plan's own NOT-shared list). Own scaling curve "
     "confirmed via its individual page (10%->13% pre-patch), PATCHED 10%->12% at level 1 (curve "
     "rescaled 12/10=1.2x before reverse-engineering — factorIndex 22, baseDamage 120 tenths% "
     "already reflects the patched value). Magic Critical pattern — already baked into "
     "Inputs!ATTACK_PCT (folds into the attack_mult delta bucket, same slot as Shadower's own "
     "Channel Karma); feeds the 2nd-Job Skill Level Bonus delta."),
]

# Resolve the {ROW_KEY} placeholders in EMPOWERED_PIERCING_ARROW's own SkillMasteryBonus% formula (Python
# f-string braces collide with Excel's own {..} SUMPRODUCT array-constant syntax elsewhere in
# this file, so this one row's cross-references are patched in after the fact instead).
_epa_row = [list(row) for row in SKILL_ROWS if row[0] == "EMPOWERED_PIERCING_ARROW"][0]
_epa_row[14] = _epa_row[14].format(
    FINAL_ATTACK_CROSSBOW_HELPER=ROW["FINAL_ATTACK_CROSSBOW_HELPER"],
    ADVANCED_FINAL_ATTACK_HELPER=ROW["ADVANCED_FINAL_ATTACK_HELPER"],
) + "+" + level_gated_sum_raw(IB("level"), {98: 10, 104: 1, 113: 1, 118: 1, 126: 1, 130: 1})
SKILL_ROWS = [tuple(_epa_row) if row[0] == "EMPOWERED_PIERCING_ARROW" else row for row in SKILL_ROWS]

# Rows with a real Cooldown(s) value (literal or a live formula reference).
ROW_HAS_COOLDOWN = {row[0]: row[3] not in ("", None) for row in SKILL_ROWS}
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

    widths = [30, 34, 8, 11, 15, 13, 11, 8, 13, 11, 12, 18, 11, 14, 17, 16, 18,
              20, 18, 15, 20, 20, 60]
    for i, w in enumerate(widths):
        ws.column_dimensions[get_column_letter(i + 1)].width = w
    ws.freeze_panes = "A2"
    return ws


# ---------------------------------------------------------------------------
# Row categories consumed by build_calc_sheet/build_summary_sheet/build_sensitivity_sheet.
# ---------------------------------------------------------------------------
DAMAGE_ROW_KEYS = ["COVERING_FIRE", "BOLT_BURST", "FROSTPREY", "SNIPE", "ARROW_ILLUSION"]
# Real, always-on buff rows (NOT baked into Inputs) whose (F * uptime, or F alone for
# unconditional rows) feeds the shared additive Attack% bucket via BuffTargetStat="ATTACK" or
# duty-cycle FD sources. Vestigial/documentation-only list (the actual formula wiring is
# hardcoded by row-key in build_summary_sheet/build_stat_block, same as Bowmaster's own file).
ATTACK_BUFF_ROW_KEYS = ["MARKSMANSHIP_BASE", "MARKSMANSHIP_COND", "ILLUSION_STEP", "BLINK_BOLT"]
# Buff-casting-startup-delay feature: rows with a real BuffDuration(s)>0. Illusion Step doesn't
# cost an action to trigger (CostsActionSlot=False, an auto-proc buff), so it never contributes TO
# the startup delay's own SUMPRODUCT (which separately filters on CostsActionSlot=TRUE) — but its
# own cast timing is still "buff-like" (unaffected BY the delay, since it isn't sequenced by the
# player at all), so it's still listed here.
BUFF_ROW_KEYS = ["ILLUSION_STEP", "SHARP_EYES", "NIMBLE_FEET"]
# "Magic Critical pattern" rows: permanent passives assumed already reflected in a matching
# Inputs% field — Calc!F used only by the Sensitivity sheet's own marginal delta.
PASSIVE_MULT_ROW_KEYS = [
    "CRITICAL_SHOT", "ARCHER_MASTERY", "CROSSBOW_ACCELERATION", "PHYSICAL_TRAINING",
    "CROSSBOW_MASTERY", "RECKLESS_HUNT_CROSSBOW", "LAST_MAN_STANDING_FD", "LAST_MAN_STANDING_COND",
    "CROSSBOW_EXPERT_SKILL", "CROSSBOW_EXPERT_MAXDMG", "SOUL_ARROW_CROSSBOW_ATK",
]
HELPER_ROW_KEYS = [
    "FINAL_ATTACK_CROSSBOW_HELPER", "ADVANCED_FINAL_ATTACK_HELPER", "MAPLE_HERO_HELPER",
]
BOLT_SURPLUS_ROW_KEYS = ["BOLT_SURPLUS"]
MAPLE_HERO_ROW_KEYS = ["MAPLE_HERO_HELPER"]
DAMAGE_DEALING_KEYS = ["EMPOWERED_PIERCING_ARROW"] + DAMAGE_ROW_KEYS + BOLT_SURPLUS_ROW_KEYS

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


def build_calc_sheet(wb):
    ws = wb.create_sheet("Calc")
    for i, name in enumerate(CALC_HEADERS):
        ws.cell(row=1, column=i + 1, value=name)
    style_header_row(ws, 1, len(CALC_HEADERS))

    fixed_duration_active_main = fixed_duration_active_expr(IB("monster_type"), IB("fight_duration"))

    monster_dmg_bonus_ref = f"Summary!$B${R_MONSTER_DMG_BONUS}"
    crit_rate_total_ref = f'({IB("crit_rate")}+Summary!$B${R_CRIT_RATE_BONUS}+{art_ref("AGG_CRIT_RATE")})'
    crit_damage_total_ref = f'({IB("crit_damage")}+Summary!$B${R_CRIT_DAMAGE_BONUS}+{art_ref("AGG_CRIT_DAMAGE")})'
    avg_buff_mult_ref = f"Summary!$B${R_AVGBUFF}"
    final_damage_extra_ref = f"Summary!$B${R_MORTAL_BLOW_BONUS}"

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
            if key in BUFF_ROW_KEYS:
                available_duration_r = IB("fight_duration")
            else:
                available_duration_r = f'MAX(0,{IB("fight_duration")}-Summary!$B${R_STARTUP_TIME})'
            rate_r = rate_or_exact_hits_expr(
                fixed_duration_active_main, f"R{r}", S("HitsPerCast", r), S("ICD(s)", r),
                S("ActiveWindow(s)", r), eff_cd_r, available_duration_r, IB("fight_duration"), f"G{r}*Q{r}",
            )
        else:
            eff_cd_r = None
            rate_r = None

        if key in HELPER_ROW_KEYS:
            ws.cell(row=r, column=4, value=(
                f'=MAX(0,({IB("level")}-100)*3)+{IB("skill_lvl_4th")}+{IB("skill_lvl_all")}'
                if S("JobStep", r) else ""
            ))
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
            for col in (7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 22):
                ws.cell(row=r, column=col, value=("1" if col == 9 else ""))
            continue

        if key == "EMPOWERED_PIERCING_ARROW":
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

        ws.cell(row=r, column=7, value=(
            f'={S("HitsPerCast", r)}*IF({S("ICD(s)", r)}>0,{S("ActiveWindow(s)", r)}/{S("ICD(s)", r)},1)'
        ))
        ws.cell(row=r, column=8, value=f'=1-(1-{S("ProcChance%", r)}/100)^{S("RollsPerCast", r)}')
        ws.cell(row=r, column=9, value="1")

        if key in (["EMPOWERED_PIERCING_ARROW"] + DAMAGE_ROW_KEYS + BOLT_SURPLUS_ROW_KEYS):
            ws.cell(row=r, column=10, value=f'={IB("attack")}*(F{r}/100)')
            maple_ratio = MAPLE_HERO_RATIOS.get(key)
            mh_row = ROW["MAPLE_HERO_HELPER"]
            maple_hero_gated = f'IF(C{mh_row}=TRUE,F{mh_row},0)'
            maple_term = f'*(1+{maple_ratio}*{maple_hero_gated}/100)' if maple_ratio else ''
            extra_fd_term = ''
            ws.cell(row=r, column=11, value=(
                f'=J{r}*(1+{IB("stat_damage")}/100)*(1+{IB("damage")}/100)'
                f'*(1+{IB("damage_amp")}/100)'
                f'*(5000/(6000+{IB("monster_defense")}*(1-{IB("def_pen")}/100)))'
                f'*(1+({IB("final_damage")}+{final_damage_extra_ref})/100)*(1+{art_ref("AGG_FINAL_DAMAGE")}/100)'
                f'{maple_term}{extra_fd_term}'
                f'*(1+(IF({S("Key", r)}="EMPOWERED_PIERCING_ARROW",{IB("basic_attack_damage")}+{art_ref("AGG_BASIC_ATTACK_DAMAGE")},'
                f'{IB("skill_damage")}+{art_ref("AGG_SKILL_DAMAGE")}))/100)'
                f'*({avg_buff_mult_ref}*(1+{art_ref("AGG_DAMAGE")}/100)*I{r})'
            ))
            ws.cell(row=r, column=12, value=f'=K{r}*(MIN({IB("min_damage")},{IB("max_damage")})/100+{IB("max_damage")}/100)/2')
            ws.cell(row=r, column=13, value=f'=L{r}*(1+{crit_damage_total_ref}/100)')
            ws.cell(row=r, column=14, value=(
                f'=L{r}*(1-MIN({crit_rate_total_ref},100)/100)+M{r}*(MIN({crit_rate_total_ref},100)/100)'
            ))
        else:
            for col in (10, 11, 12, 13, 14):
                ws.cell(row=r, column=col, value="")

        boss_dmg_pct_r = f'{IB("boss_damage")}+{S("MasteryBossDamage%", r)}+{monster_dmg_bonus_ref}+{art_ref("AGG_BOSS_DAMAGE")}'
        normal_dmg_pct_r = f'{IB("normal_damage")}+{S("MasteryNormalDamage%", r)}+{monster_dmg_bonus_ref}+{art_ref("AGG_NORMAL_DAMAGE")}'

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
        # already-computed L{r}/M{r} cells.
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

        if key == "EMPOWERED_PIERCING_ARROW":
            prefix = f"{S('HitsPerCast', r)}*N{r}*Summary!$B${R_BAPS}"
            boss_expr, normal_expr = boss_normal_dps_split_exprs(
                prefix, IB("monster_type"), boss_dmg_pct_r, normal_dmg_pct_r,
                S("NormalMonsterTargets", r), IB("max_enemies_hit"),
                extra_boss_mult_r, extra_normal_mult_r,
            )
            ws.cell(row=r, column=20, value=f'=IF(C{r},{boss_expr},0)')
            ws.cell(row=r, column=22, value=f'=IF(C{r},{normal_expr},0)')
            hit_rate_targets_blend = target_count_blend_expr(
                IB("monster_type"), IB("normal_weight_frac"), S("NormalMonsterTargets", r), IB("max_enemies_hit"),
            )
            ws.cell(row=r, column=19, value=f'=IFERROR(({prefix})/N{r}*{hit_rate_targets_blend},0)')
        elif key in DAMAGE_ROW_KEYS:
            prefix = f'H{r}*N{r}*{rate_r}'
            boss_expr, normal_expr = boss_normal_dps_split_exprs(
                prefix, IB("monster_type"), boss_dmg_pct_r, normal_dmg_pct_r,
                S("NormalMonsterTargets", r), IB("max_enemies_hit"),
                extra_boss_mult_r, extra_normal_mult_r,
            )
            ws.cell(row=r, column=20, value=f'=IF(C{r},{boss_expr},0)')
            ws.cell(row=r, column=22, value=f'=IF(C{r},{normal_expr},0)')
            hit_rate_targets_blend = target_count_blend_expr(
                IB("monster_type"), IB("normal_weight_frac"), S("NormalMonsterTargets", r), IB("max_enemies_hit"),
            )
            ws.cell(row=r, column=19, value=f'=IFERROR(({prefix})/N{r}*{hit_rate_targets_blend},0)')
        elif key in BOLT_SURPLUS_ROW_KEYS:
            bolt_surplus_trigger_rate = (
                f'SUMPRODUCT((Skills!{SC["TriggersBoltSurplus"]}2:{SC["TriggersBoltSurplus"]}{LAST_ROW}=TRUE)*'
                f'(Calc!C2:C{LAST_ROW}=TRUE)*Calc!S2:S{LAST_ROW})'
            )
            prefix = f"0.15*{bolt_surplus_trigger_rate}*{S('HitsPerCast', r)}*N{r}"
            boss_expr, normal_expr = boss_normal_dps_split_exprs(
                prefix, IB("monster_type"), boss_dmg_pct_r, normal_dmg_pct_r,
                S("NormalMonsterTargets", r), IB("max_enemies_hit"),
                extra_boss_mult_r, extra_normal_mult_r,
            )
            ws.cell(row=r, column=20, value=f'=IF(C{r},{boss_expr},0)')
            ws.cell(row=r, column=22, value=f'=IF(C{r},{normal_expr},0)')
            ws.cell(row=r, column=19, value=0)
        else:
            ws.cell(row=r, column=20, value=0)
            ws.cell(row=r, column=22, value=0)
            ws.cell(row=r, column=19, value=0)

        ws.cell(row=r, column=15, value=f'=(1-{IB("normal_weight_frac")})*T{r}+{IB("normal_weight_frac")}*V{r}')

        ws.cell(row=r, column=16, value=f'=IF(Summary!$B${R_TOTAL}=0,0,O{r}/Summary!$B${R_TOTAL})')
        ws.cell(row=r, column=17, value=(f'=IFERROR(1/{eff_cd_r},0)' if has_cooldown else 0))

        if has_cooldown:
            casts_formula = guarded_casts_expr(available_duration_r, eff_cd_r)
            ws.cell(row=r, column=18, value=f'=IF({fixed_duration_active_main},{casts_formula},0)')
        else:
            ws.cell(row=r, column=18, value=0)

    ws.cell(row=1, column=17, value="InvCooldown")
    ws.cell(row=1, column=18, value="CastsInFight")
    ws.cell(row=1, column=19, value="HitRate(perSec)")
    ws.cell(row=1, column=20, value="BossOnlyDPS")
    ws.cell(row=1, column=22, value="NormalOnlyDPS")

    widths = [26, 34, 10, 12, 9, 15, 13, 14, 17, 13, 15, 12, 12, 17, 12, 10, 12, 12, 14]
    for i, w in enumerate(widths):
        ws.column_dimensions[get_column_letter(i + 1)].width = w
    ws.freeze_panes = "C2"
    return ws


def build_summary_sheet(wb):
    ws = wb.create_sheet("Summary")
    ws["A1"] = "Marksman — DPS Summary"
    ws["A1"].font = Font(bold=True, size=14)

    ws.cell(row=DERIVED_HEADER_ROW, column=1, value="Derived Values (read-only, computed from Inputs)").font = SECTION_FONT
    ws.cell(row=D_ATTACK, column=1, value="ATTACK (= Flat ATTACK x (1+ATTACK%/100))")
    ws.cell(row=D_ATTACK, column=2, value=f'={IB("flat_attack")}*(1+{IB("attack_pct")}/100)')

    ws.cell(row=D_STAT_DAMAGE, column=1, value="STAT_DAMAGE % (= 1% of total DEX + 0.25% of STR)")
    ws.cell(
        row=D_STAT_DAMAGE, column=2,
        value=f'=({IB("flat_dex")}*(1+{IB("dex_pct")}/100))*0.01+{IB("str")}*0.0025'
    )

    ws.cell(row=D_BASIC_INPUT_LEVEL, column=1, value="Basic Attack (Empowered Piercing Arrow) Input Level (4th job formula)")
    ws.cell(
        row=D_BASIC_INPUT_LEVEL, column=2,
        value=f'=MAX(0,({IB("level")}-100)*3)+{IB("skill_lvl_4th")}+{IB("skill_lvl_all")}'
    )
    ws.cell(row=D_BASIC_FACTOR, column=1, value="Basic Attack Factor (factorIndex 21, universal 4th-job basic attack)")
    ws.cell(
        row=D_BASIC_FACTOR, column=2,
        value=f'=INDEX(FactorTable!$B$2:$Y$301, MATCH(ROUND(MIN(300,MAX(1,{IB("basic_input_level")})),0), '
              f'FactorTable!$A$2:$A$301,0), 22)'
    )
    ws.cell(row=D_SKILL_COEFFICIENT, column=1, value="SKILL_COEFFICIENT — Empowered Piercing Arrow base coefficient % (before bonuses)")
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

    r_mb, r_mc, r_is = ROW["MARKSMANSHIP_BASE"], ROW["MARKSMANSHIP_COND"], ROW["ILLUSION_STEP"]
    r_se, r_mortal, r_bb = ROW["SHARP_EYES"], ROW["MORTAL_BLOW"], ROW["BLINK_BOLT"]
    r_nf = ROW["NIMBLE_FEET"]
    r_lms_cond = ROW["LAST_MAN_STANDING_COND"]

    marksmanship_base_avg = f'((Calc!C{r_mb}=TRUE)*Calc!F{r_mb})'
    marksmanship_cond_avg = f'((Calc!C{r_mc}=TRUE)*{monster_blend_expr(IB("monster_type"), IB("normal_weight_frac"), f"Calc!F{r_mc}", "0", f"Calc!F{r_mc}")})'
    illusion_step_avg = f'((Calc!C{r_is}=TRUE)*Calc!F{r_is}*{buff_uptime(r_is)})'
    blink_bolt_avg = f'((Calc!C{r_bb}=TRUE)*Calc!F{r_bb})'
    nimble_feet_avg = f'((Calc!C{r_nf}=TRUE)*Calc!F{r_nf}*{buff_uptime(r_nf)})'

    ws.cell(row=R_AVGBUFF, column=1, value="Attack%% Bucket Multiplier (Marksmanship base+conditional + Illusion Step + Blink Bolt + Artifact Attack%, summed additively)")
    ws.cell(row=R_AVGBUFF, column=2, value=(
        f'=1+({marksmanship_base_avg}+{marksmanship_cond_avg}+{illusion_step_avg}+{blink_bolt_avg}+{art_ref("AGG_ATTACK_PCT")})/100'
    ))

    sharp_eyes_uptime = buff_uptime(r_se)
    ws.cell(row=R_CRIT_RATE_BONUS, column=1, value="Global Crit Rate Bonus % (Sharp Eyes, flat 20, duty-cycle averaged)")
    ws.cell(row=R_CRIT_RATE_BONUS, column=2, value=f'=(Calc!C{r_se}=TRUE)*20*{sharp_eyes_uptime}')

    ws.cell(row=R_MONSTER_DMG_BONUS, column=1, value="Global Monster Damage-Taken Bonus % (Artifact Enemy Damage Taken Bonus)")
    ws.cell(row=R_MONSTER_DMG_BONUS, column=2, value=f'={art_ref("AGG_ENEMY_DMG_TAKEN")}')

    ws.cell(row=R_AS_BONUS, column=1, value="Attack Speed Buff Bonus % (Nimble Feet, duty-cycle averaged)")
    ws.cell(row=R_AS_BONUS, column=2, value=f'={nimble_feet_avg}')

    ws.cell(row=R_APS, column=1, value="Actions Per Second")
    ws.cell(row=R_APS, column=2, value=(
        f'=1+MIN(150,150*(1-(1-{IB("attack_speed")}/150)*(1-B{R_AS_BONUS}/150)))/100'
    ))

    ws.cell(row=R_CASTRATE, column=1, value="Skill + Buff Cast Rate (subtracted from Empowered Piercing Arrow, 1/s)")
    ws.cell(row=R_CASTRATE, column=2, value=(
        f'=IF({fda_main},'
        f'SUMPRODUCT((Skills!{SC["CostsActionSlot"]}2:{SC["CostsActionSlot"]}{LAST_ROW}=TRUE)*'
        f'(Calc!C2:C{LAST_ROW}=TRUE)*Calc!R2:R{LAST_ROW}*Skills!{SC["ActionsPerCast"]}2:{SC["ActionsPerCast"]}{LAST_ROW})/{IB("fight_duration")},'
        f'SUMPRODUCT((Skills!{SC["CostsActionSlot"]}2:{SC["CostsActionSlot"]}{LAST_ROW}=TRUE)*'
        f'(Calc!C2:C{LAST_ROW}=TRUE)*Calc!Q2:Q{LAST_ROW}*Skills!{SC["ActionsPerCast"]}2:{SC["ActionsPerCast"]}{LAST_ROW}))'
    ))

    ws.cell(row=R_BAPS, column=1, value="Empowered Piercing Arrow (Basic Attack) Casts Per Second")
    ws.cell(row=R_BAPS, column=2, value=f'=MAX(0,B{R_APS}-B{R_CASTRATE})')

    ws.cell(row=R_CRIT_DAMAGE_BONUS, column=1, value="Global Critical Damage Bonus % (Sharp Eyes scaling — Marksman has no Concentration-equivalent stacking passive)")
    ws.cell(row=R_CRIT_DAMAGE_BONUS, column=2, value=(
        f'=(Calc!C{r_se}=TRUE)*Calc!F{r_se}*{sharp_eyes_uptime}'
    ))

    ws.cell(row=R_MORTAL_BLOW_BONUS, column=1, value="Global Final Damage Bonus % (Mortal Blow steady-state + Last Man Standing conditional half, boss/pvp-blended)")
    ws.cell(row=R_MORTAL_BLOW_BONUS, column=2, value=(
        f'=(Calc!C{r_mortal}=TRUE)*Calc!F{r_mortal}'
        f'+((Calc!C{r_lms_cond}=TRUE)*{monster_blend_expr(IB("monster_type"), IB("normal_weight_frac"), f"Calc!F{r_lms_cond}", "0", f"Calc!F{r_lms_cond}")})'
    ))

    ws.cell(row=R_STARTUP_TIME, column=1, value=(
        "Buff-Casting Startup Delay (s, before first damage-skill cast; fixed-duration only)"
    ))
    ws.cell(row=R_STARTUP_TIME, column=2, value="=" + buff_cast_startup_time_expr(
        fda_main, SC["BuffDuration(s)"], SC["CostsActionSlot"], f"Calc!C2:C{LAST_ROW}",
        f"B{R_APS}", LAST_ROW,
    ))

    ws.cell(row=R_TOTAL, column=1, value="TOTAL DPS").font = Font(bold=True, size=13)
    ws.cell(row=R_TOTAL, column=2, value=f"=SUM(Calc!O2:O{LAST_ROW})").font = Font(bold=True, size=13)

    ws.cell(row=R_BOSS_ONLY_TOTAL, column=1, value="Boss-Only Total DPS (Sensitivity baseline)")
    ws.cell(row=R_BOSS_ONLY_TOTAL, column=2, value=f"=SUM(Calc!T2:T{LAST_ROW})")
    ws.cell(row=R_NORMAL_ONLY_TOTAL, column=1, value="Normal-Only Total DPS (Sensitivity baseline)")
    ws.cell(row=R_NORMAL_ONLY_TOTAL, column=2, value=f"=SUM(Calc!V2:V{LAST_ROW})")

    ws.cell(row=R_EMPOWERED_PIERCING_ARROW_DPS, column=1, value="Empowered Piercing Arrow (Basic Attack) DPS")
    ws.cell(row=R_EMPOWERED_PIERCING_ARROW_DPS, column=2, value=f"=Calc!O{ROW['EMPOWERED_PIERCING_ARROW']}")

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

    ws.column_dimensions["A"].width = 65
    ws.column_dimensions["B"].width = 16
    ws.column_dimensions["C"].width = 12
    return ws


# ---------------------------------------------------------------------------
# Sensitivity sheet: marginal DPS from bumping each Inputs stat by +1 — mirrors every sibling
# workbook's own STAT_SWEEP/PASSIVE_DELTA_SLOT/build_stat_block pattern (DEX main / STR sub
# identity — mechanical rename of Shadower's own LUK/DEX sweep).
# ---------------------------------------------------------------------------
STAT_SWEEP = [
    ("flat_dex", "Flat DEX", "flat"),
    ("dex_pct", "DEX %", "pct"),
    ("str", "STR", "flat"),
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

POTENTIAL_STAT_TO_SWEEP_KEY = {
    "Critical Rate %": "crit_rate",
    "Critical Damage %": "crit_damage",
    "Attack Speed %": "attack_speed",
    "Damage %": "damage",
    "Final Damage %": "final_damage",
    "Min Damage Multiplier %": "min_damage",
    "Max Damage Multiplier %": "max_damage",
    "Defense Penetration": "def_pen",
    "Dex %": "dex_pct",
    "Dex": "flat_dex",
    "Basic Attack Damage %": "basic_attack_damage",
    "Skill Damage %": "skill_damage",
    "Skill Cooldown Decrease (seconds)": "skill_cooldown_decrease",
    "Buff Duration Increase %": "buff_duration_increase_pct",
    "All Skill Level": "skill_lvl_all",
    "Basic Attack Target Increase": "basic_attack_target_increase",
}


def dps_per_unit_expr(stat_name):
    if stat_name == "Main Stat Per Level":
        return f'=Sensitivity!H{SENSITIVITY_ROW_FOR["flat_dex"]}*{IB("level")}'
    if stat_name == "Main Stat % per 4 Levels":
        return f'=Sensitivity!H{SENSITIVITY_ROW_FOR["dex_pct"]}*INT({IB("level")}/4)'
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
# delta folds into. "attack_mult" has no literal Inputs field (folded into the Attack% bucket
# multiplicatively instead) — Soul Arrow: Crossbow's own Attack% component shares it. Last Man
# Standing's unconditional half folds into "final_damage" the same way; its conditional half is
# NOT here — per user clarification it's a live, monster-type-blended row (full value at 1 target
# i.e. boss/pvp, zero at normal, weighted at breakthrough — same mechanism as Marksmanship's own
# conditional half), so it's handled directly in R_MORTAL_BLOW_BONUS/its Sensitivity mirror
# instead of as a flat Inputs-baked passive.
PASSIVE_DELTA_SLOT = {
    "CRITICAL_SHOT": "crit_rate",
    "ARCHER_MASTERY": "attack_speed",
    "CROSSBOW_ACCELERATION": "attack_speed",
    "PHYSICAL_TRAINING": "basic_attack_damage",
    "CROSSBOW_MASTERY": "min_damage",
    "RECKLESS_HUNT_CROSSBOW": "final_damage",
    "LAST_MAN_STANDING_FD": "final_damage",
    "CROSSBOW_EXPERT_SKILL": "skill_damage",
    "CROSSBOW_EXPERT_MAXDMG": "max_damage",
    "SOUL_ARROW_CROSSBOW_ATK": "attack_mult",
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
            return f'(({ib("flat_dex")}*(1+{ib("dex_pct")}/100))*0.01+{ib("str")}*0.0025)'
        return IB(key)
    return ib


BLOCK_HEIGHT = LAST_ROW + 16
BLOCK_START = SENSITIVITY_HEADER_ROW + len(STAT_SWEEP) + SENSITIVITY_ARTIFACT_TABLE_HEADER_ROWS + 3


def build_stat_block(ws, base_row, ib, stat_key, stat_label, override_expr):
    row_label = base_row
    row_header = base_row + 1
    calc_start = base_row + 2
    row_of = {key: calc_start + (r - 2) for key, r in ROW.items()}
    calc_end = calc_start + (LAST_ROW - 2)

    s_avgbuff = calc_end + 2
    s_crit_rate_bonus = calc_end + 3
    s_as_bonus = calc_end + 4
    s_aps = calc_end + 5
    s_castrate = calc_end + 6
    s_baps = calc_end + 7
    s_crit_damage_bonus = calc_end + 8
    s_mortal_blow_bonus = calc_end + 9
    s_startup = calc_end + 10
    s_boss_total = calc_end + 11
    s_normal_total = calc_end + 12
    s_total = calc_end + 13
    crit_rate_bonus_ref = f"B{s_crit_rate_bonus}"
    as_bonus_ref, aps_ref, castrate_ref, baps_ref = f"B{s_as_bonus}", f"B{s_aps}", f"B{s_castrate}", f"B{s_baps}"
    crit_damage_bonus_ref = f"B{s_crit_damage_bonus}"
    mortal_blow_bonus_ref = f"B{s_mortal_blow_bonus}"
    startup_ref = f"B{s_startup}"
    total_ref = f"B{s_total}"
    boss_total_ref, normal_total_ref = f"B{s_boss_total}", f"B{s_normal_total}"

    fda_block = fixed_duration_active_expr(ib("monster_type"), ib("fight_duration"))
    bdi_block = ib("buff_duration_increase_pct")

    def buff_uptime_block(local_row, skills_row):
        return uptime_fraction_or_exact_expr(
            fda_block, f'R{local_row}', ib("monster_type"), S("BuffDuration(s)", skills_row),
            S("Cooldown(s)", skills_row), bdi_block, ib("fight_duration"),
        )

    delta_by_slot = {}
    for row_key, slot in PASSIVE_DELTA_SLOT.items():
        term = f'((C{row_of[row_key]}=TRUE)*(F{row_of[row_key]}-Calc!F{ROW[row_key]}))'
        delta_by_slot[slot] = f'{delta_by_slot[slot]}+{term}' if slot in delta_by_slot else term
    delta = {slot: delta_by_slot.get(slot, "0") for slot in (
        "attack_speed", "basic_attack_damage", "min_damage", "max_damage", "crit_rate",
        "crit_damage", "boss_damage", "skill_damage", "final_damage", "def_pen", "attack_mult",
    )}

    # Flat ATTACK is assumed to already include the character's current DEX/STR-derived attack
    # (1 total DEX = 1 flat Attack, 1 STR = 0.25 flat Attack, added into the pool before ATTACK%
    # applies) — same "already baked into Inputs, only the Sensitivity marginal delta matters"
    # pattern used elsewhere in this block. Identically 0 for every block except the ones sweeping
    # flat_dex/dex_pct/str.
    mainstat_attack_delta = (
        f'((({ib("flat_dex")}*(1+{ib("dex_pct")}/100))-({IB("flat_dex")}*(1+{IB("dex_pct")}/100)))'
        f'+0.25*({ib("str")}-{IB("str")}))'
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
    # Reindeer's Spear's base (1x) Defense Penetration is baked into Inputs!def_pen, on top of
    # whatever live delta contributes. Defense Penetration combines like Attack Speed —
    # diminishing-returns (new = 1-(1-old)*(1-inc)), never additive. This shadow block's baseline
    # may need one extra "dose" of the spear's own contribution combined in via that formula:
    # whenever this IS the reindeer_spear_equipped block's own +1 test AND the spear isn't really
    # currently equipped. Every other block's ib(equipped) == IB(equipped) unchanged, so this
    # always evaluates to 0 there.
    reindeer_spear_base_ref_block = artifact_reindeer_spear_base_def_pen_reference_expr(
        ib("reindeer_spear_equipped"), ib("reindeer_spear_star"),
    )
    _reindeer_star_magnitude = star_lookup_expr(ib("reindeer_spear_star"), "reindeer_spear_def_pen")
    _reindeer_extra_dose_block = f'({ib("reindeer_spear_equipped")}-{IB("reindeer_spear_equipped")})'
    def_pen_total_block = (
        f'(100*(1-(1-({ib("def_pen")}+{delta["def_pen"]})/100)*(1-{_reindeer_star_magnitude}/100)^{_reindeer_extra_dose_block}))'
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
    # Bottle doesn't grant Attack Speed itself, so only the dependent bonus itself needs a
    # direction-aware sign flip, evaluated at the real current Attack Speed in both directions.
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

    r_mb, r_mc, r_is = ROW["MARKSMANSHIP_BASE"], ROW["MARKSMANSHIP_COND"], ROW["ILLUSION_STEP"]
    r_se, r_nf, r_bb = ROW["SHARP_EYES"], ROW["NIMBLE_FEET"], ROW["BLINK_BOLT"]
    marksmanship_base_avg = f'((C{row_of["MARKSMANSHIP_BASE"]}=TRUE)*F{row_of["MARKSMANSHIP_BASE"]})'
    _mc_f_ref = f'F{row_of["MARKSMANSHIP_COND"]}'
    marksmanship_cond_avg = (
        f'((C{row_of["MARKSMANSHIP_COND"]}=TRUE)*'
        f'{monster_blend_expr(ib("monster_type"), ib("normal_weight_frac"), _mc_f_ref, "0", _mc_f_ref)})'
    )
    illusion_step_avg = f'((C{row_of["ILLUSION_STEP"]}=TRUE)*F{row_of["ILLUSION_STEP"]}*{buff_uptime_block(row_of["ILLUSION_STEP"], r_is)})'
    blink_bolt_avg = f'((C{row_of["BLINK_BOLT"]}=TRUE)*F{row_of["BLINK_BOLT"]})'
    nimble_feet_avg = f'((C{row_of["NIMBLE_FEET"]}=TRUE)*F{row_of["NIMBLE_FEET"]}*{buff_uptime_block(row_of["NIMBLE_FEET"], r_nf)})'
    # Attack% bucket: every live skill/buff Attack% source sums with the delta-only Attack%
    # passives (Soul Arrow: Crossbow) and every Attack%-granting artifact into ONE combined
    # percentage before a single multiplication — matches Verification item 6 (these must never
    # multiply against each other).
    attack_bucket_block = f'(1+({marksmanship_base_avg}+{marksmanship_cond_avg}+{illusion_step_avg}+{blink_bolt_avg}+{delta["attack_mult"]}+{agg_attack_pct_block})/100)'

    ws.cell(row=row_label, column=1, value=f"Stat: {stat_label}").font = LABEL_FONT
    for i, name in enumerate(CALC_HEADERS):
        ws.cell(row=row_header, column=i + 1, value=name)
    style_header_row(ws, row_header, len(CALC_HEADERS))

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
            if key in BUFF_ROW_KEYS:
                available_duration_row = ib("fight_duration")
            else:
                available_duration_row = f'MAX(0,{ib("fight_duration")}-{startup_ref})'
            rate_row = rate_or_exact_hits_expr(
                fda_block, f"R{row}", S("HitsPerCast", r), S("ICD(s)", r), S("ActiveWindow(s)", r),
                eff_cd_row, available_duration_row, ib("fight_duration"), f"G{row}*Q{row}",
            )
        else:
            eff_cd_row = None
            rate_row = None

        if key in HELPER_ROW_KEYS:
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
            for col in (7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 22):
                ws.cell(row=row, column=col, value=("1" if col == 9 else ""))
            continue

        if key == "EMPOWERED_PIERCING_ARROW":
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

        ws.cell(row=row, column=7, value=(
            f'={S("HitsPerCast", r)}*IF({S("ICD(s)", r)}>0,{S("ActiveWindow(s)", r)}/{S("ICD(s)", r)},1)'
        ))
        ws.cell(row=row, column=8, value=f'=1-(1-{S("ProcChance%", r)}/100)^{S("RollsPerCast", r)}')
        ws.cell(row=row, column=9, value="1")

        if key in (["EMPOWERED_PIERCING_ARROW"] + DAMAGE_ROW_KEYS + BOLT_SURPLUS_ROW_KEYS):
            ws.cell(row=row, column=10, value=(
                f'=({ib("attack")}+{mainstat_attack_delta}*(1+{ib("attack_pct")}/100))*(F{row}/100)'
            ))
            max_damage_total_block = f'({ib("max_damage")}+{delta["max_damage"]}+{agg_max_damage_block})'
            crit_rate_full_block = f'({ib("crit_rate")}+{delta["crit_rate"]}+{crit_rate_bonus_ref}+{boa_direct_delta}+{agg_crit_rate_block})'
            maple_ratio = MAPLE_HERO_RATIOS.get(key)
            mh_row_of = row_of["MAPLE_HERO_HELPER"]
            maple_hero_gated_block = f'IF(C{mh_row_of}=TRUE,F{mh_row_of},0)'
            maple_term = f'*(1+{maple_ratio}*{maple_hero_gated_block}/100)' if maple_ratio else ''
            extra_fd_term = ''
            ws.cell(row=row, column=11, value=(
                f'=J{row}*(1+{ib("stat_damage")}/100)*(1+{ib("damage")}/100)'
                f'*(1+{ib("damage_amp")}/100)'
                f'*(5000/(6000+{ib("monster_defense")}*(1-{def_pen_total_block}/100)))'
                f'*(1+({ib("final_damage")}+{delta["final_damage"]}+{mortal_blow_bonus_ref})/100)*(1+{agg_final_damage_block}/100)'
                f'{maple_term}{extra_fd_term}'
                f'*(1+(IF({S("Key", r)}="EMPOWERED_PIERCING_ARROW",{ib("basic_attack_damage")}+{delta["basic_attack_damage"]}+{agg_basic_attack_damage_block},'
                f'{ib("skill_damage")}+{delta["skill_damage"]}+{agg_skill_damage_block}))/100)'
                f'*({attack_bucket_block}*(1+{agg_damage_block}/100)*I{row})'
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

        boss_dmg_pct_row = f'{ib("boss_damage")}+{delta["boss_damage"]}+{S("MasteryBossDamage%", r)}+{agg_boss_damage_block}+{agg_enemy_dmg_taken_block}'
        normal_dmg_pct_row = f'{ib("normal_damage")}+{S("MasteryNormalDamage%", r)}+{agg_normal_damage_block}+{agg_enemy_dmg_taken_block}'

        # The Contract of Darkness's boss-branch-only Crit Rate, via a crit-blend ratio correction
        # using THIS row's own L/M cells (only valid for damage-dealing rows, where
        # crit_rate_full_block was just freshly set above).
        if key in (["EMPOWERED_PIERCING_ARROW"] + DAMAGE_ROW_KEYS + BOLT_SURPLUS_ROW_KEYS):
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

        if key == "EMPOWERED_PIERCING_ARROW":
            arrow_stream_targets_expr = f'(6+{ib("basic_attack_target_increase")})'
            prefix = f"{S('HitsPerCast', r)}*N{row}*{baps_ref}"
            boss_expr, normal_expr = boss_normal_dps_split_exprs(
                prefix, ib("monster_type"), boss_dmg_pct_row, normal_dmg_pct_row,
                arrow_stream_targets_expr, ib("max_enemies_hit"),
                extra_boss_mult_block, extra_normal_mult_block,
            )
            ws.cell(row=row, column=20, value=f'=IF(C{row},{boss_expr},0)')
            ws.cell(row=row, column=22, value=f'=IF(C{row},{normal_expr},0)')
            hit_rate_targets_blend_block = target_count_blend_expr(
                ib("monster_type"), ib("normal_weight_frac"), arrow_stream_targets_expr, ib("max_enemies_hit"),
            )
            ws.cell(row=row, column=19, value=f'=IFERROR(({prefix})/N{row}*{hit_rate_targets_blend_block},0)')
        elif key in DAMAGE_ROW_KEYS:
            prefix = f'H{row}*N{row}*{rate_row}'
            boss_expr, normal_expr = boss_normal_dps_split_exprs(
                prefix, ib("monster_type"), boss_dmg_pct_row, normal_dmg_pct_row,
                S("NormalMonsterTargets", r), ib("max_enemies_hit"),
                extra_boss_mult_block, extra_normal_mult_block,
            )
            ws.cell(row=row, column=20, value=f'=IF(C{row},{boss_expr},0)')
            ws.cell(row=row, column=22, value=f'=IF(C{row},{normal_expr},0)')
            hit_rate_targets_blend_block = target_count_blend_expr(
                ib("monster_type"), ib("normal_weight_frac"), S("NormalMonsterTargets", r), ib("max_enemies_hit"),
            )
            ws.cell(row=row, column=19, value=f'=IFERROR(({prefix})/N{row}*{hit_rate_targets_blend_block},0)')
        elif key in BOLT_SURPLUS_ROW_KEYS:
            bolt_surplus_trigger_rate_block = (
                f'SUMPRODUCT((Skills!{SC["TriggersBoltSurplus"]}2:{SC["TriggersBoltSurplus"]}{LAST_ROW}=TRUE)*'
                f'(C{calc_start}:C{calc_end}=TRUE)*S{calc_start}:S{calc_end})'
            )
            prefix = f"0.15*{bolt_surplus_trigger_rate_block}*{S('HitsPerCast', r)}*N{row}"
            boss_expr, normal_expr = boss_normal_dps_split_exprs(
                prefix, ib("monster_type"), boss_dmg_pct_row, normal_dmg_pct_row,
                S("NormalMonsterTargets", r), ib("max_enemies_hit"),
                extra_boss_mult_block, extra_normal_mult_block,
            )
            ws.cell(row=row, column=20, value=f'=IF(C{row},{boss_expr},0)')
            ws.cell(row=row, column=22, value=f'=IF(C{row},{normal_expr},0)')
            ws.cell(row=row, column=19, value=0)
        else:
            ws.cell(row=row, column=20, value=0)
            ws.cell(row=row, column=22, value=0)
            ws.cell(row=row, column=19, value=0)

        ws.cell(row=row, column=15, value=f'=(1-{ib("normal_weight_frac")})*T{row}+{ib("normal_weight_frac")}*V{row}')

        ws.cell(row=row, column=16, value=f'=IF({total_ref}=0,0,O{row}/{total_ref})')
        ws.cell(row=row, column=17, value=(f'=IFERROR(1/{eff_cd_row},0)' if has_cooldown else 0))
        if has_cooldown:
            casts_formula_block = guarded_casts_expr(available_duration_row, eff_cd_row)
            ws.cell(row=row, column=18, value=f'=IF({fda_block},{casts_formula_block},0)')
        else:
            ws.cell(row=row, column=18, value=0)

    attack_speed_with_delta = f'({ib("attack_speed")}+{delta["attack_speed"]})'

    ws.cell(row=s_avgbuff, column=1, value="Attack% Bucket Multiplier")
    ws.cell(row=s_avgbuff, column=2, value=f'={attack_bucket_block}')

    ws.cell(row=s_crit_rate_bonus, column=1, value="Global Crit Rate Bonus %")
    ws.cell(row=s_crit_rate_bonus, column=2, value=f'=(C{row_of["SHARP_EYES"]}=TRUE)*20*{buff_uptime_block(row_of["SHARP_EYES"], r_se)}')

    ws.cell(row=s_as_bonus, column=1, value="Attack Speed Buff Bonus %")
    ws.cell(row=s_as_bonus, column=2, value=f'={nimble_feet_avg}')

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

    ws.cell(row=s_baps, column=1, value="Empowered Piercing Arrow Casts Per Second")
    ws.cell(row=s_baps, column=2, value=f'=MAX(0,{aps_ref}-{castrate_ref})')

    ws.cell(row=s_crit_damage_bonus, column=1, value="Global Critical Damage Bonus % (Sharp Eyes)")
    ws.cell(row=s_crit_damage_bonus, column=2, value=(
        f'=(C{row_of["SHARP_EYES"]}=TRUE)*F{row_of["SHARP_EYES"]}*{buff_uptime_block(row_of["SHARP_EYES"], r_se)}'
    ))

    ws.cell(row=s_mortal_blow_bonus, column=1, value="Global Final Damage Bonus % (Mortal Blow + Last Man Standing conditional half)")
    _lms_cond_f_ref = f'F{row_of["LAST_MAN_STANDING_COND"]}'
    lms_cond_avg = (
        f'((C{row_of["LAST_MAN_STANDING_COND"]}=TRUE)*'
        f'{monster_blend_expr(ib("monster_type"), ib("normal_weight_frac"), _lms_cond_f_ref, "0", _lms_cond_f_ref)})'
    )
    ws.cell(row=s_mortal_blow_bonus, column=2, value=(
        f'=(C{row_of["MORTAL_BLOW"]}=TRUE)*F{row_of["MORTAL_BLOW"]}+{lms_cond_avg}'
    ))

    ws.cell(row=s_startup, column=1, value="Buff-Casting Startup Delay (s, fixed-duration only)")
    ws.cell(row=s_startup, column=2, value="=" + buff_cast_startup_time_expr(
        fda_block, SC["BuffDuration(s)"], SC["CostsActionSlot"], f"C{calc_start}:C{calc_end}",
        aps_ref, LAST_ROW,
    ))

    ws.cell(row=s_boss_total, column=1, value="Boss-Only Total DPS (this block's swept value)")
    ws.cell(row=s_boss_total, column=2, value=f"=SUM(T{calc_start}:T{calc_end})")
    ws.cell(row=s_normal_total, column=1, value="Normal-Only Total DPS (this block's swept value)")
    ws.cell(row=s_normal_total, column=2, value=f"=SUM(V{calc_start}:V{calc_end})")

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
    # Value" are meaningless for a toggle, so it only shows the DPS/% gain from equipping.
    # Positioned right after the "Stat" table (sized off SENSITIVITY_ARTIFACT_TABLE_HEADER_ROWS,
    # kept in sync with BLOCK_START's own buffer math above it). Row constants live at module
    # level (ARTIFACT_TABLE_*) so build_summary_sheet can reference the same rows.
    artifact_title_row = ARTIFACT_TABLE_TITLE_ROW
    artifact_header_row = ARTIFACT_TABLE_HEADER_ROW
    # The visible A/B/C columns show only UNLOCKED artifacts, sorted best-to-worst by % Gain; locked
    # artifacts are dropped entirely rather than shown at the bottom. Since there's no raw unsorted
    # source to rank/filter against once A/B/C themselves become sorted, the raw per-artifact values
    # go into a hidden staging block (columns AA-AE, far from every other column this sheet uses —
    # including the many-column shadow-block copies below — to avoid hiding anything else when this
    # range gets column-hidden); A/B/C then pull each display row from staging via INDEX/MATCH on a
    # rank computed among unlocked artifacts only. % Gain is a strictly increasing linear function
    # of DPS Gain (same Total DPS baseline for every artifact), so ranking by either column produces
    # the identical order.
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
            # (>100%/positive $ = beneficial).
            currently_equipped_expr = IB(key)
            # Potential lines only apply while the artifact is actually equipped, so equipping/
            # un-equipping must also gain/lose whatever this artifact's CURRENT potential rolls are
            # worth — added unsigned in both directions (it's already a positive "value of having
            # this," same framing as the toggle result itself), unlike the base equip effect above
            # which needs the sign flip. ArtifactsInput's own gating (Star Level per line) already
            # zeroes out locked lines, and its "tracked regardless of equip state" design means
            # this reference value exists whether or not the artifact is currently in a slot.
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
            # table shows only as many rows as are actually unlocked — not shown at the bottom,
            # dropped entirely). Several artifacts are modeled as always exactly 0 DPS impact (see
            # KNOWN_GAPS.md), so ties happen for real; broken by each tied artifact's own position
            # from the top of the staging block (SUMPRODUCT "strictly better" count + COUNTIFS
            # running tally of ties-so-far) so every rank 1..count(unlocked) is produced exactly
            # once, with no gaps for MATCH() below to trip on.
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
# Sensitivity/verify_marksman_workbook.py changes are needed for this feature at all.
# ---------------------------------------------------------------------------
EQUIP_COMPARE_STAT_TO_SWEEP_KEY = {
    "Main Stat (flat)": "flat_dex",
    "Main Stat %": "dex_pct",
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

    ws["A1"] = "Marksman — Equipment Compare"
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
    """Raw data for the PotentialCubes sheet — verbatim structure, class-agnostic in shape."""
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
    ws["A1"] = "Marksman — Artifacts (Star Level + Potentials)"
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


def load_existing_workbook_state(path):
    """If a previous Marksman-DPS-Calculator.xlsx already exists at `path`, read back its
    Inputs values, ArtifactsInput gear state, and PotentialCubes current-gear table so
    regenerating the workbook doesn't clobber the user's real character stats and gear state with
    the hardcoded defaults."""
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

        if ws.cell(row=INPUT_ARTIFACT_SLOTS_SECTION_ROW, column=1).value == "Equipped Artifacts (up to 4)":
            existing_inputs["artifact_slots"] = {
                ct: [ws.cell(row=r, column=col).value or "(none)" for r in INPUT_ARTIFACT_SLOT_ROWS]
                for ct, col in col_for_ct.items()
            }

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
