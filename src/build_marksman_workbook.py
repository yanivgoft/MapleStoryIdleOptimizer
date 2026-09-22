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
DERIVED_HEADER_ROW = 49
D_ATTACK = 50                    # ATTACK = Flat ATTACK x (1+ATTACK%/100)
D_STAT_DAMAGE = 51               # STAT_DAMAGE% = 1% of total DEX + 0.25% of STR
D_BASIC_INPUT_LEVEL = 52         # Empowered Piercing Arrow input level (4th job formula)
D_BASIC_FACTOR = 53              # Empowered Piercing Arrow factor lookup (factorIndex 21)
D_SKILL_COEFFICIENT = 54         # Empowered Piercing Arrow base coefficient % before Skill Mastery
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


def boss_normal_dps_split_exprs(prefix_expr, monster_type_ref, boss_dmg_pct_expr,
                                 normal_dmg_pct_expr, normal_targets_ref, max_enemies_ref):
    """Splits a row's DPS into independent boss-only and normal-only values, given `prefix_expr`
    (the H*N*rate*(extra multipliers) part shared by both). Each branch gets its own full
    (1+damage%/100)*target_count treatment; the two are blended into the real Total DPS as RATIOS
    (new/baseline) weighted by time spent, not as raw dollars weighted by branch size — dollar
    blending would let a stat's reported value be dominated by whichever branch happens to hit more
    targets, regardless of how much combat time is actually spent there. PvP is single-target with
    neither bonus, matching the old combined behavior."""
    capped_targets = f'MIN({normal_targets_ref},{max_enemies_ref})'
    boss_mult = f'IF({monster_type_ref}="pvp",1,1+({boss_dmg_pct_expr})/100)'
    normal_mult = f'IF({monster_type_ref}="pvp",1,(1+({normal_dmg_pct_expr})/100)*({capped_targets}))'
    return f'({prefix_expr})*{boss_mult}', f'({prefix_expr})*{normal_mult}'


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
SUMMARY_BREAKDOWN_HEADER_ROW = 6
R_AVGBUFF = 57                     # Attack% bucket (Marksmanship base+cond + Illusion Step)
R_CRIT_RATE_BONUS = 58              # Sharp Eyes (flat 20, duty-cycle averaged)
R_MONSTER_DMG_BONUS = 59            # unused placeholder (no global monster-dmg-taken source exists)
R_AS_BONUS = 60                     # Nimble Feet, duty-cycle averaged
R_APS = 61                          # Actions Per Second
R_CASTRATE = 62                     # Skill + buff cast rate (subtracted from Empowered Piercing Arrow)
R_BAPS = 63                         # Empowered Piercing Arrow (basic attack) Casts Per Second
R_CRIT_DAMAGE_BONUS = 64            # Sharp Eyes (scaling) + Concentration (steady-state max stacks)
R_MORTAL_BLOW_BONUS = 65            # Mortal Blow, steady-state always-active FD bonus
R_EMPOWERED_PIERCING_ARROW_DPS = 66
R_STARTUP_TIME = 67                 # Buff-Casting Startup Delay (s, fixed-duration only)
R_BOSS_ONLY_TOTAL = 68               # Total DPS if every hit were against a boss (Breakthrough Sensitivity baseline)
R_NORMAL_ONLY_TOTAL = 69             # Total DPS if every hit were against normal monsters (Breakthrough Sensitivity baseline)

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
                f'*(1+({IB("final_damage")}+{final_damage_extra_ref})/100)'
                f'{maple_term}{extra_fd_term}'
                f'*(1+(IF({S("Key", r)}="EMPOWERED_PIERCING_ARROW",{IB("basic_attack_damage")},{IB("skill_damage")}))/100)'
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

        boss_dmg_pct_r = f'{IB("boss_damage")}+{S("MasteryBossDamage%", r)}+{monster_dmg_bonus_ref}'
        normal_dmg_pct_r = f'{IB("normal_damage")}+{S("MasteryNormalDamage%", r)}+{monster_dmg_bonus_ref}'

        if key == "EMPOWERED_PIERCING_ARROW":
            prefix = f"{S('HitsPerCast', r)}*N{r}*Summary!$B${R_BAPS}"
            boss_expr, normal_expr = boss_normal_dps_split_exprs(
                prefix, IB("monster_type"), boss_dmg_pct_r, normal_dmg_pct_r,
                S("NormalMonsterTargets", r), IB("max_enemies_hit"),
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

    ws.cell(row=R_AVGBUFF, column=1, value="Attack%% Bucket Multiplier (Marksmanship base+conditional + Illusion Step + Blink Bolt, summed additively)")
    ws.cell(row=R_AVGBUFF, column=2, value=(
        f'=1+({marksmanship_base_avg}+{marksmanship_cond_avg}+{illusion_step_avg}+{blink_bolt_avg})/100'
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

# Absolute CDR values (seconds) swept by the Sensitivity sheet's CDR Milestone Sweep section
# (see build_sensitivity_sheet) — chosen by the user to cover the range where fixed-duration
# skill cast counts are likely to cross an INT()-floor threshold and jump.
CDR_SWEEP_VALUES = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]

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
    # passives (Soul Arrow: Crossbow) into ONE combined percentage before a single
    # multiplication — matches Verification item 6 (these must never multiply against each
    # other).
    attack_bucket_block = f'(1+({marksmanship_base_avg}+{marksmanship_cond_avg}+{illusion_step_avg}+{blink_bolt_avg}+{delta["attack_mult"]})/100)'

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
            crit_rate_total_block = f'({ib("crit_rate")}+{delta["crit_rate"]}+{crit_rate_bonus_ref})'
            maple_ratio = MAPLE_HERO_RATIOS.get(key)
            mh_row_of = row_of["MAPLE_HERO_HELPER"]
            maple_hero_gated_block = f'IF(C{mh_row_of}=TRUE,F{mh_row_of},0)'
            maple_term = f'*(1+{maple_ratio}*{maple_hero_gated_block}/100)' if maple_ratio else ''
            extra_fd_term = ''
            ws.cell(row=row, column=11, value=(
                f'=J{row}*(1+{ib("stat_damage")}/100)*(1+{ib("damage")}/100)'
                f'*(1+{ib("damage_amp")}/100)'
                f'*(5000/(6000+{ib("monster_defense")}*(1-({ib("def_pen")}+{delta["def_pen"]})/100)))'
                f'*(1+({ib("final_damage")}+{delta["final_damage"]}+{mortal_blow_bonus_ref})/100)'
                f'{maple_term}{extra_fd_term}'
                f'*(1+(IF({S("Key", r)}="EMPOWERED_PIERCING_ARROW",{ib("basic_attack_damage")}+{delta["basic_attack_damage"]},'
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

        boss_dmg_pct_row = f'{ib("boss_damage")}+{delta["boss_damage"]}+{S("MasteryBossDamage%", r)}'
        normal_dmg_pct_row = f'{ib("normal_damage")}+{S("MasteryNormalDamage%", r)}'

        if key == "EMPOWERED_PIERCING_ARROW":
            arrow_stream_targets_expr = f'(6+{ib("basic_attack_target_increase")})'
            prefix = f"{S('HitsPerCast', r)}*N{row}*{baps_ref}"
            boss_expr, normal_expr = boss_normal_dps_split_exprs(
                prefix, ib("monster_type"), boss_dmg_pct_row, normal_dmg_pct_row,
                arrow_stream_targets_expr, ib("max_enemies_hit"),
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
        boss_ratio = f'IFERROR({boss_total_ref}/Summary!$B${R_BOSS_ONLY_TOTAL},1)'
        normal_ratio = f'IFERROR({normal_total_ref}/Summary!$B${R_NORMAL_ONLY_TOTAL},1)'
        weighted_ratio = f'((1-{IB("normal_weight_frac")})*{boss_ratio}+{IB("normal_weight_frac")}*{normal_ratio})'
        ws.cell(row=row, column=8, value=f"=Summary!$B${R_TOTAL}*({weighted_ratio}-1)")
        ws.cell(row=row, column=9, value=f"={weighted_ratio}*100")
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
    """If a previous Marksman-DPS-Calculator.xlsx already exists at `path`, read back its
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
