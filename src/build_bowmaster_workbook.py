#!/usr/bin/env python3
"""
Generates Bowmaster-DPS-Calculator.xlsx: a live-formula Excel replica of a Bowmaster
skill-rotation DPS model, sibling to build_shadower_workbook.py / build_night_lord_workbook.py
(see /Users/yaniv/.claude/plans/so-basically-we-were-magical-iverson.md this was built from).
Bowmaster is the first DEX-main/STR-sub class built in this project (FP-Mage/ILM/Bishop are
INT-main/LUK-sub; Night Lord/Shadower are LUK-main/DEX-sub).

Sheets: Inputs, FactorTable, Skills, Calc, Summary, Sensitivity, CubeData, PotentialCubes.

Ground truth: fetched live from idle.maplestorywiki.net (curl, domain already allowlisted in
.claude/apple/dangerous_allowed_domains.csv) this session, cross-referenced against the actual
Aug 13 patch notes PDF (~/Downloads/August 13 Patch Notes - class changes.pdf) by mechanic/
description match, not name match (confirmed name divergences: wiki "Concentration" = PDF
"Focused Fury"; wiki "Flash Mirage" = PDF "Speed Mirage").

Key mechanics/simplifications specific to this kit (see the plan for full derivation):
  - Arrow Stream (basic attack) reuses the universal 4th-job-basic-attack constant (baseDamage
    2900, factorIndex 21) confirmed identical across every class built so far, and confirmed
    fresh this session via Arrow Stream's own wiki curve (290%->522%, levels 1-200).
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
    average addition directly into Arrow Stream's own coefficient (Calc!F), rather than built as
    an independent damage pipeline with its own separate Final Damage chain — a deliberate
    simplification (their own two-hop dependency, real MapleStory Final Attack triggering
    specifically off basic attacks, is folded into the basic attack's own average output instead
    of modeled as a fully independent multi-stage proc).
  - Concentration (wiki name) / Focused Fury (PDF name) — same skill, confirmed via cross-
    reference (Concentration's own wiki page + Bowmaster/Skills overview both show "+1 Accuracy /
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
    was confirmed this session via idle.maplestorywiki.net/w/Maple_Hero_(Bowmaster) (full level
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
OUT_PATH = REPO / "Bowmaster" / "Bowmaster-DPS-Calculator.xlsx"

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
DERIVED_HEADER_ROW = 49
D_ATTACK = 50                    # ATTACK = Flat ATTACK x (1+ATTACK%/100)
D_STAT_DAMAGE = 51               # STAT_DAMAGE% = 1% of total DEX + 0.25% of STR
D_BASIC_INPUT_LEVEL = 52         # Arrow Stream input level (4th job formula)
D_BASIC_FACTOR = 53              # Arrow Stream factor lookup (factorIndex 21)
D_SKILL_COEFFICIENT = 54         # Arrow Stream base coefficient % before Skill Mastery
D_NORMAL_WEIGHT_FRAC = 55        # 0/1/breakthrough-blend/0 weight, by monster_type
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


def IB(key):
    if key in DERIVED_ROW:
        return f"Summary!$B${DERIVED_ROW[key]}"
    return f"Inputs!$B${IN[key]}"


def build_readme_sheet(wb):
    ws = wb.active
    ws.title = "README"
    ws["A1"] = "Bowmaster — DPS Calculator: How to Use This Workbook"
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
        "Final Attack: Bow + Advanced Final Attack are folded into Arrow Stream's own coefficient "
        "as a steady-state average addition, not modeled as an independent damage pipeline with "
        "its own separate Final Damage chain.",
        "Maple Hero's own per-level scaling curve is confirmed via idle.maplestorywiki.net/w/"
        "Maple_Hero_(Bowmaster) — all three target skills (Arrow Platter/Phoenix/Covering Fire) "
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
    ws["A1"] = "Bowmaster — DPS Calculator Inputs"
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


# ---------------------------------------------------------------------------
# Skills sheet schema — trimmed layout (no Toxic-Venom/Shadow-Shifter/Meso-Explosion-style
# bespoke columns needed; Bowmaster has none of those mechanics). Reuses the same core columns
# every sibling workbook shares.
# ---------------------------------------------------------------------------
SKILL_COLUMNS = [
    "Key", "Name", "JobStep", "Cooldown(s)", "CostsActionSlot", "ActionsPerCast",
    "HitsPerCast", "ICD(s)", "ActiveWindow(s)", "ProcChance%", "RollsPerCast",
    "BaseDamage(tenths%)", "FactorIndex", "ScalesWithLevel",
    "SkillMasteryBonus%", "MasteryBossDamage%", "MasteryNormalDamage%",
    "NormalMonsterTargets", "BuffTargetStat", "BuffDuration(s)",
    "MapleHeroBase(tenths%)", "MapleHeroFactorIndex", "Note",
]
SC = {name: get_column_letter(i + 1) for i, name in enumerate(SKILL_COLUMNS)}

# Row order (2..LAST_ROW) — derived from this list, never hand-numbered.
ROW_ORDER = [
    "ARROW_STREAM", "FINAL_ATTACK_BOW_HELPER", "ADVANCED_FINAL_ATTACK_HELPER",
    "COVERING_FIRE", "QUIVER_CARTRIDGE", "ENCHANTED_QUIVER_HELPER",
    "PHOENIX", "ARROW_PLATTER", "MAPLE_HERO_HELPER",
    "FLASH_MIRAGE", "FLASH_MIRAGE_II_HELPER",
    "MARKSMANSHIP_BASE", "MARKSMANSHIP_COND", "ILLUSION_STEP",
    "SHARP_EYES", "CONCENTRATION", "MORTAL_BLOW",
    "NIMBLE_FEET",
    "CRITICAL_SHOT", "ARCHER_MASTERY", "BOW_ACCELERATION", "PHYSICAL_TRAINING",
    "BOW_MASTERY", "EXTREME_ARCHERY_BOW", "ARMOR_BREAK_FD", "ARMOR_BREAK_DEFPEN",
    "BOW_EXPERT_SKILL", "BOW_EXPERT_MAXDMG", "SOUL_ARROW_BOW_ATK",
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
SUMMARY_BREAKDOWN_HEADER_ROW = 6
R_AVGBUFF = 57                     # Attack% bucket (Marksmanship base+cond + Illusion Step)
R_CRIT_RATE_BONUS = 58              # Sharp Eyes (flat 20, duty-cycle averaged)
R_MONSTER_DMG_BONUS = 59            # unused placeholder (no global monster-dmg-taken source exists)
R_AS_BONUS = 60                     # Nimble Feet, duty-cycle averaged
R_APS = 61                          # Actions Per Second
R_CASTRATE = 62                     # Skill + buff cast rate (subtracted from Arrow Stream)
R_BAPS = 63                         # Arrow Stream (basic attack) Casts Per Second
R_CRIT_DAMAGE_BONUS = 64            # Sharp Eyes (scaling) + Concentration (steady-state max stacks)
R_MORTAL_BLOW_BONUS = 65            # Mortal Blow, steady-state always-active FD bonus
R_ARROW_STREAM_DPS = 66

# Unlock level for every row — gated all the way down (matches every sibling workbook's
# thorough approach). Levels confirmed live from idle.maplestorywiki.net/w/Bowmaster/Skills
# this session (Sept 2026).
UNLOCK_LEVEL = {
    "ARROW_STREAM": 100,
    "FINAL_ATTACK_BOW_HELPER": 50,
    "ADVANCED_FINAL_ATTACK_HELPER": 105,
    "COVERING_FIRE": 35,
    "QUIVER_CARTRIDGE": 40,
    "ENCHANTED_QUIVER_HELPER": 107,
    "PHOENIX": 69,
    "ARROW_PLATTER": 63,
    "MAPLE_HERO_HELPER": 100,
    "FLASH_MIRAGE": 60,
    "FLASH_MIRAGE_II_HELPER": 110,
    "MARKSMANSHIP_BASE": 74,
    "MARKSMANSHIP_COND": 74,
    "ILLUSION_STEP": 117,
    "SHARP_EYES": 115,
    "CONCENTRATION": 66,
    "MORTAL_BLOW": 72,
    "CRITICAL_SHOT": 15,
    "ARCHER_MASTERY": 10,
    "BOW_ACCELERATION": 33,
    "PHYSICAL_TRAINING": 38,
    "BOW_MASTERY": 43,
    "EXTREME_ARCHERY_BOW": 75,
    "ARMOR_BREAK_FD": 125,
    "ARMOR_BREAK_DEFPEN": 125,
    "BOW_EXPERT_SKILL": 120,
    "BOW_EXPERT_MAXDMG": 120,
    "SOUL_ARROW_BOW_ATK": 45,
    # NIMBLE_FEET: no threshold (shared Explorer skill, level 0) — stays unconditionally unlocked.
}


def unlock_expr(key):
    level = UNLOCK_LEVEL.get(key)
    return "=TRUE" if level is None else f"={IB('level')}>={level}"


# Maple Hero (Lv.100) — confirmed live from idle.maplestorywiki.net/w/Maple_Hero_(Bowmaster)
# this session: all three skills scale by the exact same curve (Arrow Platter 25%->195%, Phoenix
# 30%->234%, Covering Fire 100%->780% across levels 1-200), so the ratios below stay constant at
# every level — resolves cleanly to factorIndex 23/baseDamage 250 tenths% (0% residual, same
# factorIndex Shadower's own MAPLE_HERO_SHADOWER uses).
MAPLE_HERO_RATIOS = {
    "ARROW_PLATTER": 25 / 25,
    "PHOENIX": 30 / 25,
    "COVERING_FIRE": 100 / 25,
}

# (key, name, jobstep, cooldown, costsAction, actionsPerCast, hits, icd, window, chance, rolls,
#  baseDamage, factorIndex, scales, skillMasteryBonusPct, masteryBossDmgPct, masteryNormalDmgPct,
#  normalMonsterTargets, buffTarget, buffDuration, mapleBase, mapleFactor, note)
SKILL_ROWS = [
    ("ARROW_STREAM", "Arrow Stream", 4, "", False, 1,
     f'=IF({IB("level")}>=134,6,5)', 0, 0, 100, 1,
     2900, 21, True,
     # Final Attack: Bow (25% chance, 35%->49% additional dmg) + Advanced Final Attack (+500%->
     # 900% FD to Final Attack specifically) folded together as a steady-state average addition,
     # PLUS Arrow Stream's own real Damage mastery chain (98/104/113/118/126/130, cumulative
     # +10/11/12/13/14/15%, confirmed live via idle.maplestorywiki.net/w/Bowmaster/Mastery —
     # identical level breakpoints/deltas to Night Lord's own Showdown mastery chain, the same
     # universal 4th-job-basic-attack mastery pattern) — see FINAL_ATTACK_BOW_HELPER/
     # ADVANCED_FINAL_ATTACK_HELPER rows below for the Final Attack piece.
     f"=Calc!F{{FINAL_ATTACK_BOW_HELPER}}*IF(Calc!C{{FINAL_ATTACK_BOW_HELPER}}=TRUE,1,0)/100"
     f"*(1+Calc!F{{ADVANCED_FINAL_ATTACK_HELPER}}*IF(Calc!C{{ADVANCED_FINAL_ATTACK_HELPER}}=TRUE,1,0)/100)"
     f"*25"
     f"+{level_gated_sum_raw(IB('level'), {98: 10, 104: 1, 113: 1, 118: 1, 126: 1, 130: 1}).replace('{', '{{').replace('}', '}}')}",
     level_gated_sum(IB("level"), {108: 10, 122: 10}), 0,
     f'=6+{IB("basic_attack_target_increase")}', "", 0, "", "",
     "4th-job basic-attack effect (supersedes Wind Arrow/Wind Arrow II/Arrow Blow, confirmed "
     "identical wiki wording — 290% damage to 6 target(s) in front 5 time(s) — to every other "
     "class's own 4th-job basic attack). factorIndex 21, baseDamage 2900 tenths%. HitsPerCast "
     "= 5 (the wiki's own 'time(s)' figure), bumping to 6 once Mastery Lv.134 'Arrow Stream - "
     "Strike' unlocks — same pattern/level as Night Lord's own Showdown mastery. "
     "SkillMasteryBonus% is Final Attack: Bow + Advanced Final Attack's own combined "
     "steady-state contribution (ProcChance x AdditionalDamage% x (1+AdvancedFD%/100) x 25, the "
     "x25 converting Final Attack's own attack-triggered percentage into an equivalent addition "
     "to Arrow Stream's per-hit coefficient at Arrow Stream's own 5-hit-per-cast rate — see the "
     "module docstring for why this is folded in rather than an independent pipeline) PLUS the "
     "real Arrow Stream - Damage mastery chain (98/104/113/118/126/130, cumulative "
     "+10/11/12/13/14/15%). MasteryBossDamage% is the real 2-tier Arrow Stream - Boss Monster "
     "Damage chain (108, 122), each independently +10%, totaling +20% — this and the Damage "
     "mastery chain above were both caught missing entirely during the Marksman build's own "
     "shared-skill cross-check (Verification item 5) and fixed here."),
    ("FINAL_ATTACK_BOW_HELPER", "Final Attack: Bow (helper)", 2, "", False, 1, 1, 0, 0, 100, 1,
     350, 21, True,
     level_gated_sum(IB("level"), {52: 50}), 0, 0, 0, "", 0, "", "",
     "Helper row only (no independent O-column DPS) — feeds Arrow Stream's own coefficient. "
     "25% chance, 35%->49% additional damage (levels 1-100). factorIndex 21, baseDamage 350 "
     "tenths%. Mastery Lv.52 'Final Attack - Damage' +50% (real SkillMasteryBonus%, confirmed "
     "via Bowmaster/Mastery — same pattern/level as Marksman's own Final Attack: Crossbow "
     "helper, missing from this row until caught during the Marksman build's own cross-check). "
     "Not otherwise patched (Aug 13 2026 patch notes make no mention of this skill)."),
    ("ADVANCED_FINAL_ATTACK_HELPER", "Advanced Final Attack (helper)", 4, "", False, 1, 1, 0, 0, 100, 1,
     5000, 21, True,
     level_gated_sum(IB("level"), {111: 50}), 0, 0, 0, "", 0, "", "",
     "Helper row only — feeds Arrow Stream's own coefficient (Final Attack's own Final Damage "
     "bonus). +500%->900% FD (levels 1-200). factorIndex 21, baseDamage 5000 tenths%. Mastery "
     "Lv.111 'Advanced Final Attack - Enhance' +50% (real SkillMasteryBonus%, confirmed via "
     "Bowmaster/Mastery — same treatment as FINAL_ATTACK_BOW_HELPER above). Not otherwise "
     "patched."),
    ("COVERING_FIRE", "Covering Fire", 1, 19, True, 1, 3, 0, 0, 100, 1,
     2500, 12, True,
     level_gated_sum(IB("level"), {39: 50}), 0, 0, 1, "", 0, 250, 0,
     "Shared verbatim w/ Marksman (identical name AND numbers both classes, confirmed via the "
     "patch notes' own shared 'Covering Fire' entry). 250%->375% damage x3 hits (levels "
     "1-100), 19s cooldown. factorIndex 12, baseDamage 2500 tenths%. Mastery Lv.39 'Covering "
     "Fire - Damage' +50% (real SkillMasteryBonus%). Patched: skill use range +~20% (not "
     "modeled). Maple Hero target — see MAPLE_HERO_RATIOS (biggest share, 4x Arrow Platter's "
     "own share)."),
    ("QUIVER_CARTRIDGE", "Quiver Cartridge", 3, f'=1/(1+(Summary!$B${R_APS}-1)*4/15)', False, 1,
     f'=3+IF({IB("level")}>=107,3,0)', 0, 0, 100, 1,
     500, 21, True,
     0, 0, 200,
     f'=3+IF({IB("level")}>=107,3,0)', "", 0, "", "",
     "Background periodic DoT, same shape as FP-Mage's Ignite (CostsActionSlot=False, 'always "
     "maintained'), but with a real AS-scaled tick rate per user direction to use the English "
     "wiki wording ('activation speed increases up to 0.4 times based on Attack Speed') over the "
     "self-contradictory Korean text ('up to 2x'). Modeled as: tick multiplier = "
     "1+0.4*(TotalAS%/150), i.e. up to +40% faster ticking at the same 150%-AS cap already used "
     "by Summary!Actions Per Second (R_APS) — Cooldown(s) = 1/tick_multiplier, base 1s at 0% AS "
     "down to ~0.7143s at the 150% AS cap. PATCHED: base damage "
     "22%->50% (curve rescaled 50/22=2.2727x before reverse-engineering — factorIndex 21, "
     "baseDamage 500 tenths% already reflects the patched value), targets 1->3, +3 more once "
     "Enchanted Quiver unlocks at Lv.107 (see ENCHANTED_QUIVER_HELPER). Flat +8% Attack "
     "(patch-added) assumed already reflected in your own Inputs — see SOUL_ARROW_BOW_ATK's own "
     "Note (same treatment, both are flat unconditional Attack% bonuses)."),
    ("ENCHANTED_QUIVER_HELPER", "Enchanted Quiver (helper)", 4, "", False, 1, 1, 0, 0, 100, 1,
     3000, 21, True,
     0, 0, 0, 0, "", 0, "", "",
     "Helper row only — feeds Quiver Cartridge's own K-column extra Final Damage term (see "
     "QUIVER_CARTRIDGE's own targets formula for the +3 targets side). PATCHED: FD 500%->300% "
     "(curve rescaled 300/500=0.6x before reverse-engineering — factorIndex 21, baseDamage 3000 "
     "tenths% already reflects the patched value)."),
    ("PHOENIX", "Phoenix", 3, f'=IF({IB("level")}>=102,60*0.6,60)', True, 1,
     1, f'=IF({IB("level")}>=80,3*0.7,3)',
     f'=IF({IB("level")}>=102,30,20)', 100, 1,
     6000, 12, True,
     0, 0,
     f'=IF({IB("level")}>=92,100,0)',
     f'=5+IF({IB("level")}>=76,3,0)', "", 0, 250, 0,
     "Summons Phoenix, attacks nearby targets on a periodic tick (EffectiveHits = HitsPerCast x "
     "(ActiveWindow/ICD), same mechanism as FP-Mage/ILM's own summon rows). PATCHED: duration "
     "20s->30s (target detection range +~25% not modeled), cooldown 60s (Mastery Lv.102 'Phoenix "
     "- Reuse' -50%->-40% per the patch, baked into the Cooldown(s) formula). factorIndex 12, "
     "baseDamage 6000 tenths% (600%->1200%, levels 1-200) — not itself patched (only duration/"
     "detection range changed). Mastery Lv.76 '+3 targets', Lv.80 '-30% strike interval' (baked "
     "into ICD(s)), Lv.92 '+100%p Normal Monster Damage' (own MasteryNormalDamage%, scoped to "
     "this row only — not the global bucket). Maple Hero target — see MAPLE_HERO_RATIOS."),
    ("ARROW_PLATTER", "Arrow Platter", 3, 40, True, 1, 1, 0.3, 60, 100, 1,
     500, 12, True,
     0, 0, 200,
     f'=3+IF({IB("level")}>=98,1,0)', "", 0, 250, 0,
     "RESOLVED this session — idle.maplestorywiki.net/w/Arrow_Platter is a confirmed wiki content "
     "bug (renders Wind Arrow II's data under Arrow Platter's own infobox), but the skill's real "
     "current-name page is 'Quiver Flow' (idle.maplestorywiki.net/w/Quiver_Flow, per user "
     "direction — an old/alternate name the wiki still hosts the real curve under), which gives "
     "the full level 1-200 curve (50%->100%, linear +2.5% per 10 levels) resolving cleanly to "
     "factorIndex 12/baseDamage 500 tenths% (0% residual), plus the real Cooldown=40s (its own "
     "infobox — NOT 60s, which was this session's earlier unconfirmed guess matching the "
     "skill's own 60s active-duration instead of its actual cooldown). Duration(60s) > "
     "Cooldown(40s) so it's maintained at 100% uptime once off cooldown (re-placed immediately). "
     "Stationary turret: fires every 0.3s for 60s (EffectiveHits = 60/0.3=200/cast). PATCHED: "
     "base targets 1->3, +1 more once Lv.98 mastery unlocks (patched from +2). Own +200% Normal "
     "Monster Damage baked into MasteryNormalDamage% (scoped to this row only, per its own skill "
     "description, not the global bucket). Maple Hero target — see MAPLE_HERO_RATIOS."),
    ("MAPLE_HERO_HELPER", "Maple Hero (helper)", 4, "", False, 1, 1, 0, 0, 100, 1,
     250, 23, True,
     0, 0, 0, 0, "", 0, "", "",
     "Shared ratio-feeder row (see MAPLE_HERO_RATIOS) for Arrow Platter/Phoenix/Covering Fire's "
     "own Final Damage chains — mirrors Shadower's own MAPLE_HERO_SHADOWER mechanism. RESOLVED "
     "this session via idle.maplestorywiki.net/w/Maple_Hero_(Bowmaster) (full level 1-200 "
     "curve, resolves to factorIndex 23/baseDamage 250 tenths%, 0% residual). No independent DPS "
     "row of its own (Calc columns J-N blank/0, only D/E/F computed, read directly by each "
     "target row's own K-column formula — same 'no independent row' pattern as Shadower's own "
     "Maple Hero)."),
    ("FLASH_MIRAGE", "Flash Mirage", 3, 5, False, 1, 1, 0, 0, 20, 1,
     50, 0, False,
     0, 0, 0,
     f'=5+IF({IB("level")}>=136,1,0)', "", 0, "", "",
     "Passive proc with a real 5s internal cooldown (own wiki infobox lists 'Cooldown: 5 sec' "
     "despite Type=Passive) — modeled as a normal Cooldown(s)-gated row (CostsActionSlot=False) "
     "so effective proc rate is capped at once per 5s x 20% chance. Own damage% (5%) confirmed "
     "non-scaling across all sampled levels 1-200 — factorIndex 0, baseDamage 50 tenths%. Its "
     "own 'activation chance/damage increases based on Attack Speed' text (550->990 across "
     "levels) is too vague to model precisely (unclear whether it means chance, damage, or a "
     "hard cap) — FLAGGED, not modeled, flat 20%/5% used throughout. Wiki calls this skill "
     "'Flash Mirage'; the Aug 13 patch notes call the SAME skill 'Speed Mirage' (confirmed via "
     "mechanic match — targets 5->7, detection range +~14%, target count not modeled here since "
     "this row is single-target-proc shaped). Flash Mirage II (Lv.110, see "
     "FLASH_MIRAGE_II_HELPER) adds +targets/+FD once unlocked, baked into "
     "NormalMonsterTargets/K-column."),
    ("FLASH_MIRAGE_II_HELPER", "Flash Mirage II (helper)", 4, "", False, 1, 1, 0, 0, 100, 1,
     4000, 21, True,
     0, 0, 0, 0, "", 0, "", "",
     "Helper row only — feeds Flash Mirage's own K-column extra Final Damage term (see "
     "FLASH_MIRAGE's own targets formula for the +4 targets side, +1 more once Mastery Lv.138 "
     "unlocks, patched from +3). +400%->720% FD (levels 1-200), not itself patched (only the "
     "Lv.138 mastery's own target-count bonus changed, 3->1)."),
    ("MARKSMANSHIP_BASE", "Marksmanship (unconditional half)", 3, "", False, 1, 1, 0, 0, 100, 1,
     100, 22, True,
     0, 0, 0, 0, "ATTACK", 0, "", "",
     "PATCHED: 'Base Attack +10%, additional +10% when 1 target' replaces the old flat '+20% at "
     "1 target only' wording — modeled as two separate rows (this unconditional half + "
     "MARKSMANSHIP_COND's conditional half), summed additively into the same Attack% bucket as "
     "Illusion Step (Verification item 6 — these must never multiply against each other). Half "
     "of the wiki's own pre-patch curve (10%->16%, levels 1-200), assumed symmetric 50/50 split "
     "at every level (the patch note only confirms the level-1 split, 10/10) — factorIndex 22, "
     "baseDamage 100 tenths%. Shared verbatim w/ Marksman (identical name, wording, and numbers "
     "confirmed both classes via the patch notes' own shared 'Marksmanship' entry)."),
    ("MARKSMANSHIP_COND", "Marksmanship (conditional half, 1 target)", 3, "", False, 1, 1, 0, 0, 100, 1,
     100, 22, True,
     0, 0, 0, 0, "ATTACK_COND_1TARGET", 0, "", "",
     "Conditional half of Marksmanship's own patched Attack% bonus — blended via the same "
     "monster_blend_expr helper already used for Boss/Normal Monster Damage% (boss/pvp -> full "
     "value, normal -> 0, breakthrough -> weighted), applied to the Attack% bucket instead. Same "
     "curve/tuple as MARKSMANSHIP_BASE (factorIndex 22, baseDamage 100 tenths%)."),
    ("ILLUSION_STEP", "Illusion Step", 4, 24, False, 1, 1, 0, 0, 100, 1,
     140, 22, True,
     0, 0, 0, 0, "ATTACK", 15, "", "",
     "Cycling passive: Attack+14%->22.4% for 15s, then swaps to Evasion+15->24/damage taken "
     "-10%->16% for 9s (not modeled — those components have no mechanic anywhere in this "
     "calculator). Modeled as a duty-cycled buff (Cooldown(s)=24 = full 15+9s cycle length, "
     "BuffDuration(s)=15 = the Attack-active portion, giving a 0.625 duty-cycle uptime) — same "
     "buff_uptime machinery as every other timed buff in this project. factorIndex 22, "
     "baseDamage 140 tenths%. Not patched. Shared verbatim w/ Marksman."),
    ("SHARP_EYES", "Sharp Eyes", 4, 35, True, 1, 1, 0, 0, 100, 1,
     400, 21, True,
     0, 0, 0, 0, "CRIT_DAMAGE", 18, "", "",
     "Self-inclusive ally buff (matches Bishop's own 'allied players' precedent) — flat +20% "
     "Crit Rate (non-scaling, not represented in this row's own BaseDamage/FactorIndex; added "
     "directly as a hardcoded 20 in the Crit-Rate-bonus accumulator formula in build_summary_"
     "sheet) + scaling Crit Damage +40%->72% (levels 1-200, this row's own curve — factorIndex "
     "21, baseDamage 400 tenths%) for 18s, cooldown 35s. Not patched. Shared verbatim w/ "
     "Marksman."),
    ("CONCENTRATION", "Concentration", 3, "", False, 1, 1, 0, 0, 100, 1,
     0, 0, False,
     0, 0, 0, 0, "CRIT_DAMAGE", 0, "", "",
     "Wiki name 'Concentration' = Aug 13 patch notes' 'Focused Fury' (same skill — both wiki's "
     "own Concentration page and the Bowmaster/Skills overview show '+1 Accuracy/+3% Crit "
     "Damage for 4 sec, stacking up to 10 times' at level 1, matching the patch's own pre-patch "
     "values with an already-correct 10-stack max, confirmed directly against the live wiki "
     "this session — not 7 as an earlier session's notes mistakenly recorded). Modeled at "
     "steady-state maximum stacks (10 x 3% = 30% Crit Damage, flat, once unlocked at Lv.66) — "
     "same convention as every other accumulating-stack passive in this project. PATCHED: "
     "duration 4s->6s, Accuracy +1->+3/stack (Accuracy not modeled either way). BaseDamage/"
     "FactorIndex left blank/0 (unused placeholder) since this row contributes a flat 30 "
     "directly via the R_CONCENTRATION_BONUS accumulator, not a level-scaled Calc!F value."),
    ("MORTAL_BLOW", "Mortal Blow", 3, "", False, 1, 1, 0, 0, 100, 1,
     120, 22, True,
     0, 0, 0, 0, "FINAL_DAMAGE", 0, "", "",
     "Upon attacking a target directly 40 times, +10%->16%(pre-patch curve) FD for 5s. Modeled "
     "at steady state (assumed always active once unlocked), not an exact hit-counter/timer "
     "state machine — same simplification tier as Concentration above. PATCHED: base 10%->12% "
     "(curve rescaled 12/10=1.2x before reverse-engineering — factorIndex 22, baseDamage 120 "
     "tenths% already reflects the patched value). Shared verbatim w/ Marksman."),
    ("NIMBLE_FEET", "Nimble Feet", 1, 60, True, 1, 1, 0, 0, 100, 1,
     150, 0, False,
     0, 0, 0, 1, "ATTACK_SPEED", 15, "", "",
     "Shared cross-tree verbatim w/ Night Lord/Shadower/FP-Mage (byte-identical wiki wording — "
     "'+15% Attack Speed, +10% Speed for 15 sec'). Flat +15% Attack Speed / +10% Speed for 15s, "
     "60s cooldown, non-scaling. FactorIndex unused placeholder."),
    ("CRITICAL_SHOT", "Critical Shot", 1, "", False, 1, 1, 0, 0, 100, 1,
     50, 22, True,
     0, 0, 0, 0, "CRIT_RATE", 0, "", "",
     "Magic Critical pattern — already baked into Inputs!CRIT_RATE%; feeds the 1st-Job Skill "
     "Level Bonus delta. factorIndex 22, baseDamage 50 tenths% (5%->6.5%, levels 1-100)."),
    ("ARCHER_MASTERY", "Archer Mastery (Attack Speed)", 1, "", False, 1, 1, 0, 0, 100, 1,
     50, 22, True,
     0, 0, 0, 0, "ATTACK_SPEED", 0, "", "",
     "Magic Critical pattern — already baked into Inputs!ATTACK_SPEED%; feeds the 1st-Job Skill "
     "Level Bonus delta. factorIndex 22, baseDamage 50 tenths% (5%->6.5%, levels 1-100). Own "
     "Speed component not modeled."),
    ("BOW_ACCELERATION", "Bow Acceleration", 2, "", False, 1, 1, 0, 0, 100, 1,
     50, 22, True,
     0, 0, 0, 0, "ATTACK_SPEED", 0, "", "",
     "Magic Critical pattern — already baked into Inputs!ATTACK_SPEED%; feeds the 2nd-Job Skill "
     "Level Bonus delta. factorIndex 22, baseDamage 50 tenths% (5%->6.5%, levels 1-100)."),
    ("PHYSICAL_TRAINING", "Physical Training", 2, "", False, 1, 1, 0, 0, 100, 1,
     100, 22, True,
     0, 0, 0, 0, "BASIC_ATTACK_DAMAGE", 0, "", "",
     "Magic Critical pattern — already baked into Inputs!BASIC_ATTACK_DAMAGE%; feeds the "
     "2nd-Job Skill Level Bonus delta. factorIndex 22, baseDamage 100 tenths% (10%->13%, levels "
     "1-100)."),
    ("BOW_MASTERY", "Bow Mastery", 2, "", False, 1, 1, 0, 0, 100, 1,
     150, 22, True,
     0, 0, 0, 0, "MIN_DAMAGE", 0, "", "",
     "Magic Critical pattern — already baked into Inputs!MIN_DAMAGE%; feeds the 2nd-Job Skill "
     "Level Bonus delta. factorIndex 22, baseDamage 150 tenths% (15%->19.5%, levels 1-100)."),
    ("EXTREME_ARCHERY_BOW", "Extreme Archery / Reckless Hunt: Bow", 3, "", False, 1, 1, 0, 0, 100, 1,
     150, 22, True,
     0, 0, 0, 0, "FINAL_DAMAGE", 0, "", "",
     "Own Final Damage component only (Defense reduction not modeled — no Defense mechanic "
     "exists anywhere in this calculator). Magic Critical pattern — already baked into "
     "Inputs!FINAL_DAMAGE%; feeds the 3rd-Job Skill Level Bonus delta. factorIndex 22, "
     "baseDamage 150 tenths% (15%->24%, levels 1-200). PATCHED name: wiki still shows 'Extreme "
     "Archery: Bow', Aug 13 patch notes confirm current name 'Reckless Hunt: Bow' (-10%->-5% "
     "Defense, not modeled either way; FD component itself unpatched)."),
    ("ARMOR_BREAK_FD", "Armor Break (Final Damage)", 4, "", False, 1, 1, 0, 0, 100, 1,
     100, 22, True,
     0, 0, 0, 0, "FINAL_DAMAGE", 0, "", "",
     "Magic Critical pattern — already baked into Inputs!FINAL_DAMAGE%; feeds the 4th-Job Skill "
     "Level Bonus delta (Final Damage side). factorIndex 22, baseDamage 100 tenths% (10%->16%, "
     "levels 1-200). Not patched. Marksman's own equivalent-slot skill ('Last Man Standing') is "
     "a genuinely different mechanic, not shared."),
    ("ARMOR_BREAK_DEFPEN", "Armor Break (Defense Penetration)", 4, "", False, 1, 1, 0, 0, 100, 1,
     100, 22, True,
     0, 0, 0, 0, "DEF_PEN", 0, "", "",
     "Same skill as Armor Break (Final Damage) above, +10%->16% Defense Penetration. Magic "
     "Critical pattern — already baked into Inputs!DEF_PEN%; feeds the 4th-Job Skill Level "
     "Bonus delta (Defense Penetration side). factorIndex 22, baseDamage 100 tenths%."),
    ("BOW_EXPERT_SKILL", "Bow Expert (Skill Damage)", 4, "", False, 1, 1, 0, 0, 100, 1,
     150, 22, True,
     0, 0, 0, 0, "SKILL_DAMAGE", 0, "", "",
     "Magic Critical pattern — already baked into Inputs!SKILL_DAMAGE%; feeds the 4th-Job Skill "
     "Level Bonus delta (Skill Damage side). factorIndex 22, baseDamage 150 tenths% (15%->24%, "
     "levels 1-200). Not patched."),
    ("BOW_EXPERT_MAXDMG", "Bow Expert (Max Damage Multiplier)", 4, "", False, 1, 1, 0, 0, 100, 1,
     200, 22, True,
     0, 0, 0, 0, "MAX_DAMAGE", 0, "", "",
     "Same skill as Bow Expert (Skill Damage) above, +20%->32% Max Damage Multiplier. Magic "
     "Critical pattern — already baked into Inputs!MAX_DAMAGE%; feeds the 4th-Job Skill Level "
     "Bonus delta (Max Damage Multiplier side). factorIndex 22, baseDamage 200 tenths%."),
    ("SOUL_ARROW_BOW_ATK", "Soul Arrow: Bow (Attack%)", 2, "", False, 1, 1, 0, 0, 100, 1,
     80, 0, False,
     0, 0, 0, 0, "ATTACK", 0, "", "",
     "Own flat +8% Attack component only (patch-added; the DEX+150->900(AS-scaled) component "
     "has NO row here at all — assume your own Inputs!Flat DEX already includes it, per the "
     "README; no percentage-bucket exists in this template for a flat sub-stat bonus, a "
     "deliberate scope-reduction). Magic Critical pattern — already baked into Inputs!ATTACK_"
     "PCT (folds into the attack_mult delta bucket, same slot as Shadower's own Channel Karma); "
     "feeds the 2nd-Job Skill Level Bonus delta. factorIndex 0 (non-scaling, flat 8%), "
     "baseDamage 80 tenths%."),
]

# Resolve the {ROW_KEY} placeholders in ARROW_STREAM's own SkillMasteryBonus% formula (Python
# f-string braces collide with Excel's own {..} SUMPRODUCT array-constant syntax elsewhere in
# this file, so this one row's cross-references are patched in after the fact instead).
_arrow_stream_row = [list(row) for row in SKILL_ROWS if row[0] == "ARROW_STREAM"][0]
_arrow_stream_row[14] = _arrow_stream_row[14].format(
    FINAL_ATTACK_BOW_HELPER=ROW["FINAL_ATTACK_BOW_HELPER"],
    ADVANCED_FINAL_ATTACK_HELPER=ROW["ADVANCED_FINAL_ATTACK_HELPER"],
)
SKILL_ROWS = [tuple(_arrow_stream_row) if row[0] == "ARROW_STREAM" else row for row in SKILL_ROWS]

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
DAMAGE_ROW_KEYS = ["COVERING_FIRE", "QUIVER_CARTRIDGE", "PHOENIX", "ARROW_PLATTER", "FLASH_MIRAGE"]
# Real, always-on buff rows (NOT baked into Inputs) whose (F * uptime) feeds the shared
# multiplicative avg_buff_mult chain via BuffTargetStat="ATTACK" or duty-cycle FD sources.
ATTACK_BUFF_ROW_KEYS = ["MARKSMANSHIP_BASE", "MARKSMANSHIP_COND", "ILLUSION_STEP"]
# "Magic Critical pattern" rows: permanent passives assumed already reflected in a matching
# Inputs% field — Calc!F used only by the Sensitivity sheet's own marginal delta.
PASSIVE_MULT_ROW_KEYS = [
    "CRITICAL_SHOT", "ARCHER_MASTERY", "BOW_ACCELERATION", "PHYSICAL_TRAINING", "BOW_MASTERY",
    "EXTREME_ARCHERY_BOW", "ARMOR_BREAK_FD", "ARMOR_BREAK_DEFPEN", "BOW_EXPERT_SKILL",
    "BOW_EXPERT_MAXDMG", "SOUL_ARROW_BOW_ATK",
]
HELPER_ROW_KEYS = [
    "FINAL_ATTACK_BOW_HELPER", "ADVANCED_FINAL_ATTACK_HELPER", "ENCHANTED_QUIVER_HELPER",
    "MAPLE_HERO_HELPER", "FLASH_MIRAGE_II_HELPER",
]
MAPLE_HERO_ROW_KEYS = ["MAPLE_HERO_HELPER"]
DAMAGE_DEALING_KEYS = ["ARROW_STREAM"] + DAMAGE_ROW_KEYS

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
    crit_rate_total_ref = f'({IB("crit_rate")}+Summary!$B${R_CRIT_RATE_BONUS})'
    crit_damage_total_ref = f'({IB("crit_damage")}+Summary!$B${R_CRIT_DAMAGE_BONUS})'
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
            rate_r = rate_or_exact_hits_expr(
                fixed_duration_active_main, f"R{r}", S("HitsPerCast", r), S("ICD(s)", r),
                S("ActiveWindow(s)", r), eff_cd_r, IB("fight_duration"), f"G{r}*Q{r}",
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
            for col in (7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19):
                ws.cell(row=r, column=col, value=("1" if col == 9 else ""))
            continue

        if key == "ARROW_STREAM":
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

        if key in (["ARROW_STREAM"] + DAMAGE_ROW_KEYS):
            ws.cell(row=r, column=10, value=f'={IB("attack")}*(F{r}/100)')
            monster_dmg_term = monster_blend_expr(
                IB("monster_type"), IB("normal_weight_frac"),
                f'{IB("boss_damage")}+{S("MasteryBossDamage%", r)}+{monster_dmg_bonus_ref}',
                f'{IB("normal_damage")}+{S("MasteryNormalDamage%", r)}+{monster_dmg_bonus_ref}',
                "0",
            )
            maple_ratio = MAPLE_HERO_RATIOS.get(key)
            mh_row = ROW["MAPLE_HERO_HELPER"]
            maple_hero_gated = f'IF(C{mh_row}=TRUE,F{mh_row},0)'
            maple_term = f'*(1+{maple_ratio}*{maple_hero_gated}/100)' if maple_ratio else ''
            extra_fd_term = ''
            if key == "QUIVER_CARTRIDGE":
                eq_row = ROW["ENCHANTED_QUIVER_HELPER"]
                extra_fd_term = f'*(1+IF(C{eq_row}=TRUE,F{eq_row},0)/100)'
            elif key == "FLASH_MIRAGE":
                fm2_row = ROW["FLASH_MIRAGE_II_HELPER"]
                extra_fd_term = f'*(1+IF(C{fm2_row}=TRUE,F{fm2_row},0)/100)'
            ws.cell(row=r, column=11, value=(
                f'=J{r}*(1+{IB("stat_damage")}/100)*(1+{IB("damage")}/100)'
                f'*(1+{monster_dmg_term}/100)'
                f'*(1+{IB("damage_amp")}/100)'
                f'*(5000/(6000+{IB("monster_defense")}*(1-{IB("def_pen")}/100)))'
                f'*(1+({IB("final_damage")}+{final_damage_extra_ref})/100)'
                f'{maple_term}{extra_fd_term}'
                f'*(1+(IF({S("Key", r)}="ARROW_STREAM",{IB("basic_attack_damage")},{IB("skill_damage")}))/100)'
                f'*({avg_buff_mult_ref}*I{r})'
            ))
            ws.cell(row=r, column=12, value=f'=K{r}*(MIN({IB("min_damage")},{IB("max_damage")})/100+{IB("max_damage")}/100)/2')
            ws.cell(row=r, column=13, value=f'=L{r}*(1+{crit_damage_total_ref}/100)')
            ws.cell(row=r, column=14, value=(
                f'=L{r}*(1-MIN({crit_rate_total_ref},100)/100)+M{r}*(MIN({crit_rate_total_ref},100)/100)'
            ))
        else:
            for col in (10, 11, 12, 13, 14):
                ws.cell(row=r, column=col, value="")

        if key == "ARROW_STREAM":
            ws.cell(row=r, column=15, value=(
                f"=IF(C{r},{S('HitsPerCast', r)}*N{r}*Summary!$B${R_BAPS}*"
                f"{target_multiplier_expr(IB('monster_type'), IB('normal_weight_frac'), S('NormalMonsterTargets', r), IB('max_enemies_hit'))},0)"
            ))
        elif key in DAMAGE_ROW_KEYS:
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

        ws.cell(row=r, column=19, value=f'=IFERROR(O{r}/N{r},0)')

    ws.cell(row=1, column=17, value="InvCooldown")
    ws.cell(row=1, column=18, value="CastsInFight")
    ws.cell(row=1, column=19, value="HitRate(perSec)")

    widths = [26, 34, 10, 12, 9, 15, 13, 14, 17, 13, 15, 12, 12, 17, 12, 10, 12, 12, 14]
    for i, w in enumerate(widths):
        ws.column_dimensions[get_column_letter(i + 1)].width = w
    ws.freeze_panes = "C2"
    return ws


def build_summary_sheet(wb):
    ws = wb.create_sheet("Summary")
    ws["A1"] = "Bowmaster — DPS Summary"
    ws["A1"].font = Font(bold=True, size=14)

    ws.cell(row=DERIVED_HEADER_ROW, column=1, value="Derived Values (read-only, computed from Inputs)").font = SECTION_FONT
    ws.cell(row=D_ATTACK, column=1, value="ATTACK (= Flat ATTACK x (1+ATTACK%/100))")
    ws.cell(row=D_ATTACK, column=2, value=f'={IB("flat_attack")}*(1+{IB("attack_pct")}/100)')

    ws.cell(row=D_STAT_DAMAGE, column=1, value="STAT_DAMAGE % (= 1% of total DEX + 0.25% of STR)")
    ws.cell(
        row=D_STAT_DAMAGE, column=2,
        value=f'=({IB("flat_dex")}*(1+{IB("dex_pct")}/100))*0.01+{IB("str")}*0.0025'
    )

    ws.cell(row=D_BASIC_INPUT_LEVEL, column=1, value="Basic Attack (Arrow Stream) Input Level (4th job formula)")
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
    ws.cell(row=D_SKILL_COEFFICIENT, column=1, value="SKILL_COEFFICIENT — Arrow Stream base coefficient % (before bonuses)")
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
    r_se, r_conc, r_mortal = ROW["SHARP_EYES"], ROW["CONCENTRATION"], ROW["MORTAL_BLOW"]
    r_nf = ROW["NIMBLE_FEET"]

    marksmanship_base_avg = f'((Calc!C{r_mb}=TRUE)*Calc!F{r_mb})'
    marksmanship_cond_avg = f'((Calc!C{r_mc}=TRUE)*{monster_blend_expr(IB("monster_type"), IB("normal_weight_frac"), f"Calc!F{r_mc}", "0", f"Calc!F{r_mc}")})'
    illusion_step_avg = f'((Calc!C{r_is}=TRUE)*Calc!F{r_is}*{buff_uptime(r_is)})'
    nimble_feet_avg = f'((Calc!C{r_nf}=TRUE)*Calc!F{r_nf}*{buff_uptime(r_nf)})'

    ws.cell(row=R_AVGBUFF, column=1, value="Attack%% Bucket Multiplier (Marksmanship base+conditional + Illusion Step, summed additively)")
    ws.cell(row=R_AVGBUFF, column=2, value=(
        f'=1+({marksmanship_base_avg}+{marksmanship_cond_avg}+{illusion_step_avg})/100'
    ))

    sharp_eyes_uptime = buff_uptime(r_se)
    ws.cell(row=R_CRIT_RATE_BONUS, column=1, value="Global Crit Rate Bonus % (Sharp Eyes, flat 20, duty-cycle averaged)")
    ws.cell(row=R_CRIT_RATE_BONUS, column=2, value=f'=(Calc!C{r_se}=TRUE)*20*{sharp_eyes_uptime}')

    ws.cell(row=R_MONSTER_DMG_BONUS, column=1, value="Global Monster Damage-Taken Bonus % (unused — no such source exists in this kit)")
    ws.cell(row=R_MONSTER_DMG_BONUS, column=2, value=0)

    ws.cell(row=R_AS_BONUS, column=1, value="Attack Speed Buff Bonus % (Nimble Feet, duty-cycle averaged)")
    ws.cell(row=R_AS_BONUS, column=2, value=f'={nimble_feet_avg}')

    ws.cell(row=R_APS, column=1, value="Actions Per Second")
    ws.cell(row=R_APS, column=2, value=(
        f'=1+MIN(150,150*(1-(1-{IB("attack_speed")}/150)*(1-B{R_AS_BONUS}/150)))/100'
    ))

    ws.cell(row=R_CASTRATE, column=1, value="Skill + Buff Cast Rate (subtracted from Arrow Stream, 1/s)")
    ws.cell(row=R_CASTRATE, column=2, value=(
        f'=IF({fda_main},'
        f'SUMPRODUCT((Skills!{SC["CostsActionSlot"]}2:{SC["CostsActionSlot"]}{LAST_ROW}=TRUE)*'
        f'(Calc!C2:C{LAST_ROW}=TRUE)*Calc!R2:R{LAST_ROW}*Skills!{SC["ActionsPerCast"]}2:{SC["ActionsPerCast"]}{LAST_ROW})/{IB("fight_duration")},'
        f'SUMPRODUCT((Skills!{SC["CostsActionSlot"]}2:{SC["CostsActionSlot"]}{LAST_ROW}=TRUE)*'
        f'(Calc!C2:C{LAST_ROW}=TRUE)*Calc!Q2:Q{LAST_ROW}*Skills!{SC["ActionsPerCast"]}2:{SC["ActionsPerCast"]}{LAST_ROW}))'
    ))

    ws.cell(row=R_BAPS, column=1, value="Arrow Stream (Basic Attack) Casts Per Second")
    ws.cell(row=R_BAPS, column=2, value=f'=MAX(0,B{R_APS}-B{R_CASTRATE})')

    ws.cell(row=R_CRIT_DAMAGE_BONUS, column=1, value="Global Critical Damage Bonus % (Sharp Eyes scaling + Concentration steady-state max stacks)")
    ws.cell(row=R_CRIT_DAMAGE_BONUS, column=2, value=(
        f'=(Calc!C{r_se}=TRUE)*Calc!F{r_se}*{sharp_eyes_uptime}+(Calc!C{r_conc}=TRUE)*30'
    ))

    ws.cell(row=R_MORTAL_BLOW_BONUS, column=1, value="Global Final Damage Bonus % (Mortal Blow, steady-state always-active)")
    ws.cell(row=R_MORTAL_BLOW_BONUS, column=2, value=f'=(Calc!C{r_mortal}=TRUE)*Calc!F{r_mortal}')

    ws.cell(row=R_TOTAL, column=1, value="TOTAL DPS").font = Font(bold=True, size=13)
    ws.cell(row=R_TOTAL, column=2, value=f"=SUM(Calc!O2:O{LAST_ROW})").font = Font(bold=True, size=13)

    ws.cell(row=R_ARROW_STREAM_DPS, column=1, value="Arrow Stream (Basic Attack) DPS")
    ws.cell(row=R_ARROW_STREAM_DPS, column=2, value=f"=Calc!O{ROW['ARROW_STREAM']}")

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
# multiplicatively instead) — Soul Arrow: Bow's own Attack% component shares it.
PASSIVE_DELTA_SLOT = {
    "CRITICAL_SHOT": "crit_rate",
    "ARCHER_MASTERY": "attack_speed",
    "BOW_ACCELERATION": "attack_speed",
    "PHYSICAL_TRAINING": "basic_attack_damage",
    "BOW_MASTERY": "min_damage",
    "EXTREME_ARCHERY_BOW": "final_damage",
    "ARMOR_BREAK_FD": "final_damage",
    "ARMOR_BREAK_DEFPEN": "def_pen",
    "BOW_EXPERT_SKILL": "skill_damage",
    "BOW_EXPERT_MAXDMG": "max_damage",
    "SOUL_ARROW_BOW_ATK": "attack_mult",
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
            return f'(({ib("flat_dex")}*(1+{ib("dex_pct")}/100))*0.01+{ib("str")}*0.0025)'
        return IB(key)
    return ib


BLOCK_HEIGHT = LAST_ROW + 14
BLOCK_START = SENSITIVITY_HEADER_ROW + len(STAT_SWEEP) + 3


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
    s_total = calc_end + 11
    crit_rate_bonus_ref = f"B{s_crit_rate_bonus}"
    as_bonus_ref, aps_ref, castrate_ref, baps_ref = f"B{s_as_bonus}", f"B{s_aps}", f"B{s_castrate}", f"B{s_baps}"
    crit_damage_bonus_ref = f"B{s_crit_damage_bonus}"
    mortal_blow_bonus_ref = f"B{s_mortal_blow_bonus}"
    total_ref = f"B{s_total}"

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

    r_mb, r_mc, r_is = ROW["MARKSMANSHIP_BASE"], ROW["MARKSMANSHIP_COND"], ROW["ILLUSION_STEP"]
    r_se, r_nf = ROW["SHARP_EYES"], ROW["NIMBLE_FEET"]
    marksmanship_base_avg = f'((C{row_of["MARKSMANSHIP_BASE"]}=TRUE)*F{row_of["MARKSMANSHIP_BASE"]})'
    _mc_f_ref = f'F{row_of["MARKSMANSHIP_COND"]}'
    marksmanship_cond_avg = (
        f'((C{row_of["MARKSMANSHIP_COND"]}=TRUE)*'
        f'{monster_blend_expr(ib("monster_type"), ib("normal_weight_frac"), _mc_f_ref, "0", _mc_f_ref)})'
    )
    illusion_step_avg = f'((C{row_of["ILLUSION_STEP"]}=TRUE)*F{row_of["ILLUSION_STEP"]}*{buff_uptime_block(row_of["ILLUSION_STEP"], r_is)})'
    nimble_feet_avg = f'((C{row_of["NIMBLE_FEET"]}=TRUE)*F{row_of["NIMBLE_FEET"]}*{buff_uptime_block(row_of["NIMBLE_FEET"], r_nf)})'
    # Attack% bucket: every live skill/buff Attack% source sums with the delta-only Attack%
    # passives (Soul Arrow: Bow) into ONE combined percentage before a single multiplication —
    # matches Verification item 6 (these must never multiply against each other).
    attack_bucket_block = f'(1+({marksmanship_base_avg}+{marksmanship_cond_avg}+{illusion_step_avg}+{delta["attack_mult"]})/100)'

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
            rate_row = rate_or_exact_hits_expr(
                fda_block, f"R{row}", S("HitsPerCast", r), S("ICD(s)", r), S("ActiveWindow(s)", r),
                eff_cd_row, ib("fight_duration"), f"G{row}*Q{row}",
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
            for col in (7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19):
                ws.cell(row=row, column=col, value=("1" if col == 9 else ""))
            continue

        if key == "ARROW_STREAM":
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

        if key in (["ARROW_STREAM"] + DAMAGE_ROW_KEYS):
            ws.cell(row=row, column=10, value=(
                f'=({ib("attack")}+{mainstat_attack_delta}*(1+{ib("attack_pct")}/100))*(F{row}/100)'
            ))
            monster_dmg_term = monster_blend_expr(
                ib("monster_type"), ib("normal_weight_frac"),
                f'{ib("boss_damage")}+{delta["boss_damage"]}+{S("MasteryBossDamage%", r)}',
                f'{ib("normal_damage")}+{S("MasteryNormalDamage%", r)}',
                "0",
            )
            crit_rate_total_block = f'({ib("crit_rate")}+{delta["crit_rate"]}+{crit_rate_bonus_ref})'
            maple_ratio = MAPLE_HERO_RATIOS.get(key)
            mh_row_of = row_of["MAPLE_HERO_HELPER"]
            maple_hero_gated_block = f'IF(C{mh_row_of}=TRUE,F{mh_row_of},0)'
            maple_term = f'*(1+{maple_ratio}*{maple_hero_gated_block}/100)' if maple_ratio else ''
            extra_fd_term = ''
            if key == "QUIVER_CARTRIDGE":
                eq_row_of = row_of["ENCHANTED_QUIVER_HELPER"]
                extra_fd_term = f'*(1+IF(C{eq_row_of}=TRUE,F{eq_row_of},0)/100)'
            elif key == "FLASH_MIRAGE":
                fm2_row_of = row_of["FLASH_MIRAGE_II_HELPER"]
                extra_fd_term = f'*(1+IF(C{fm2_row_of}=TRUE,F{fm2_row_of},0)/100)'
            ws.cell(row=row, column=11, value=(
                f'=J{row}*(1+{ib("stat_damage")}/100)*(1+{ib("damage")}/100)'
                f'*(1+{monster_dmg_term}/100)'
                f'*(1+{ib("damage_amp")}/100)'
                f'*(5000/(6000+{ib("monster_defense")}*(1-({ib("def_pen")}+{delta["def_pen"]})/100)))'
                f'*(1+({ib("final_damage")}+{delta["final_damage"]}+{mortal_blow_bonus_ref})/100)'
                f'{maple_term}{extra_fd_term}'
                f'*(1+(IF({S("Key", r)}="ARROW_STREAM",{ib("basic_attack_damage")}+{delta["basic_attack_damage"]},'
                f'{ib("skill_damage")}+{delta["skill_damage"]}))/100)'
                f'*({attack_bucket_block}*I{row})'
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

        if key == "ARROW_STREAM":
            arrow_stream_targets_expr = f'(6+{ib("basic_attack_target_increase")})'
            ws.cell(row=row, column=15, value=(
                f"=IF(C{row},{S('HitsPerCast', r)}*N{row}*{baps_ref}*"
                f"{target_multiplier_expr(ib('monster_type'), ib('normal_weight_frac'), arrow_stream_targets_expr, ib('max_enemies_hit'))},0)"
            ))
        elif key in DAMAGE_ROW_KEYS:
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
        ws.cell(row=row, column=19, value=f'=IFERROR(O{row}/N{row},0)')

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

    ws.cell(row=s_baps, column=1, value="Arrow Stream Casts Per Second")
    ws.cell(row=s_baps, column=2, value=f'=MAX(0,{aps_ref}-{castrate_ref})')

    ws.cell(row=s_crit_damage_bonus, column=1, value="Global Critical Damage Bonus % (Sharp Eyes + Concentration)")
    ws.cell(row=s_crit_damage_bonus, column=2, value=(
        f'=(C{row_of["SHARP_EYES"]}=TRUE)*F{row_of["SHARP_EYES"]}*{buff_uptime_block(row_of["SHARP_EYES"], r_se)}'
        f'+(C{row_of["CONCENTRATION"]}=TRUE)*30'
    ))

    ws.cell(row=s_mortal_blow_bonus, column=1, value="Global Final Damage Bonus % (Mortal Blow)")
    ws.cell(row=s_mortal_blow_bonus, column=2, value=f'=(C{row_of["MORTAL_BLOW"]}=TRUE)*F{row_of["MORTAL_BLOW"]}')

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


def load_existing_workbook_state(path):
    """If a previous Bowmaster-DPS-Calculator.xlsx already exists at `path`, read back its
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
            if row in COMPUTED_INPUT_ROWS:
                continue
            value = ws.cell(row=row, column=2).value
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
