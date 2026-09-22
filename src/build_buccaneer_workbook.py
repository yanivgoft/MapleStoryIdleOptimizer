#!/usr/bin/env python3
"""
Generates Buccaneer-DPS-Calculator.xlsx: a live-formula Excel replica of a Buccaneer
skill-rotation DPS model, sibling to build_hero_workbook.py. Buccaneer is STR-main/DEX-sub
(same identity as Hero/Paladin/Dark Knight). Corsair (its own sibling Pirate-tree class) is
DEX-main/STR-sub instead — the OPPOSITE identity, confirmed directly by the user, not shared.

Sheets: Inputs, FactorTable, Skills, Calc, Summary, Sensitivity, CubeData, PotentialCubes.

CRITICAL DATA-QUALITY CAVEAT (worse than any class built so far except Bishop): the
`Buccaneer/Skills` wiki overview page has NO job-tier headers, NO Type column, NO Req. Level
column, NO Cooldown column — just a flat two-column (Skill, Description) table. ZERO individual
wiki pages exist for any of Buccaneer's 28 skills (confirmed genuine 404s, verified against a
known-good control page's byte size — not a rate-limit artifact; no outgoing links to alternate
names exist either). Every scaling skill below uses the FLAGGED-ASSUMPTION convention already
established in build_bishop_workbook.py: `(baseDamage, factorIndex)` derived from the single known
level-1 value using the per-skill-type factorIndex convention (burst/DoT->12, buffs/passives->22,
basic attack->21), NOT a verified curve. The Mastery table (Lv.12-138) DOES exist and is real —
its discrete level-gated deltas are layered on top of the assumed base curves as genuine
SkillMasteryBonus%/MasteryBossDamage% contributions.

Ground truth: fetched live from idle.maplestorywiki.net this session, cross-referenced against the
Aug 13 patch notes PDF's Buccaneer section. All patched skills confirmed STALE on the live wiki
(pre-patch numbers) — patch deltas applied manually.

Key mechanics/simplifications specific to this kit:
  - Hook Bomber (basic attack) reuses the universal 4th-job-basic-attack constant (baseDamage
    2900, factorIndex 21). HitsPerCast=5, bumping to 6 once Mastery Lv.136 unlocks. Real Damage
    mastery chain (102/106/116/120/128/132, DELTAS {102:10,106:1,116:1,120:1,128:1,132:1}) and
    Boss Monster Damage chain (111/124, +10% each) included — same level breakpoints as Hero's
    own Hook Bomber chain.
  - Sea Serpent Burst / Serpent Assault / Serpent Scale model Buccaneer's "Assault Mode" resource
    economy: Sea Serpent Burst procs on every basic attack (PATCHED: 40% chance -> guaranteed),
    granting 1 Serpent Scale (+1 more once Lv.104 mastery). At 5 scales, Assault Mode triggers for
    10s (+5s once Lv.94 mastery), during which Serpent Assault replaces Sea Serpent Burst as the
    basic-attack proc and Serpent Scale's own +25% Final Damage buff is active. Modeled as a
    steady-state duty cycle: uptime = AssaultDuration/(AssaultDuration + ScalesNeeded/ScaleGainRate),
    reusing the existing ProcChance% machinery (Sea Serpent Burst's ProcChance% = 100*(1-uptime),
    Serpent Assault's = 100*uptime) rather than inventing new machinery — a documented
    approximation of a resource-stack economy, not an exact state machine. Greater Sea Serpent
    I/II (slottable upgrade skills, not mastery-table rows) fold additively into Sea Serpent
    Burst's/Serpent Assault's own K-column terms (targets/damage/FD), assumed always-equipped
    once unlocked (steady-state "always slotted" convention, same tier as every other permanent
    passive-if-equipped skill in this project).
  - Octopunch + Sea Serpent's Rage + Raging Serpent Assault: Sea Serpent's Rage triggers
    unconditionally on every Octopunch cast (folded additively into Octopunch's own coefficient,
    same x-multiplier folding trick as Final Attack elsewhere) plus its own extra-hits DoT-style
    tick (Raging Serpent Assault, 5 ticks over 5s) gated by the SAME Assault-Mode-uptime fraction
    computed above (it only fires "when attacking with Sea Serpent's Rage in Assault Mode").
  - Nautilus Strike (Lv.~103, 1950% dmg/15 targets/5 hits) is confirmed SHARED verbatim with
    Corsair (byte-identical wiki description) — FLAGGED ASSUMPTION tuple, documented for Corsair's
    own build to reuse directly. Its own Mastery "Nautilus Strike - Final Attack" (Lv.113, PATCHED
    15%->30% trigger chance, cooldown set to 1s, 850% additional damage) procs off basic attacks —
    modeled as its own Cooldown+ProcChance-gated row, same machinery as Bowmaster's Flash Mirage.
  - Groggy Mastery PATCHED: a mechanic-TYPE change, not just a number change — "damage +25%"
    (generic) becomes "Final Damage +8%" (specifically Final Damage). Modeled as +8% Final Damage
    per the patch, not the old 25% generic-damage value.
  - Shadow Heart, Quick Motion (AS component only), Agile Knuckles, Dark Clarity, Knuckle Mastery,
    Physical Training are all Magic-Critical-pattern always-on passives assumed already reflected
    in your own Inputs stat entries — only their Sensitivity marginal delta is modeled live, same
    convention as every prior class. Perseverance's own HP-regen has no DPS mechanic; its Mastery
    Lv.49 "+5% Attack when HP>=50%" needs HP tracking that doesn't exist anywhere in this project —
    not modeled, flagged. Admiral's Wings (damage-taken reduction) is purely defensive, not
    modeled. Mastery Lv.54 "Advanced Dash - Protection" references a skill absent from the entire
    skill overview list — flagged, unmodeled, no base skill to attach it to.
  - Crossbones, Speed Infusion, Time Leap, Roll of the Dice: none of these have a stated cooldown
    anywhere on this wiki (the overview page has no Cooldown column at all). Modeled as always-
    active steady-state buffs once unlocked (FLAGGED assumption — real uptime is likely lower than
    100%, pending real cooldown data). Roll of the Dice's own random 0-5% Attack roll is
    approximated at its average value (2.5%) rather than modeled as an actual RNG process. Speed
    Infusion's Final Damage component (20% of Attack Speed%) is a live formula referencing the
    character's own total Attack Speed%, not a flat number.
  - Maple Hero (Buccaneer)'s own wiki source is genuinely TRUNCATED mid-sentence ("Serpent Assault
    60%, Corkscrew..." — missing Corkscrew Blow's own %/level and a likely third skill entirely,
    since Corsair's own Maple Hero has exactly 3 entries). Per direct user decision: model ONLY
    Serpent Assault's confirmed 60%, leave Corkscrew Blow and the missing third skill completely
    unmodeled — FLAGGED as a known incomplete gap for a human to fill in later.
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
OUT_PATH = REPO / "Buccaneer" / "Buccaneer-DPS-Calculator.xlsx"

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


def load_factor_table():
    data = json.loads(FACTOR_TABLE_JSON.read_text())
    return {int(k): v for k, v in data.items()}


FACTOR_TABLE = load_factor_table()
assert len(FACTOR_TABLE) == 300 and len(FACTOR_TABLE[1]) == 24


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
# Inputs sheet row map — STR main stat / DEX sub, mirror rename of Bowmaster's own DEX/STR
# identity (formula shape unchanged, per the plan's confirmed stat-identity-agnostic finding).
# ---------------------------------------------------------------------------
DERIVED_HEADER_ROW = 49
D_ATTACK = 50
D_STAT_DAMAGE = 51
D_BASIC_INPUT_LEVEL = 52
D_BASIC_FACTOR = 53
D_SKILL_COEFFICIENT = 54
D_NORMAL_WEIGHT_FRAC = 55
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
    "flat_str": 12,
    "str_pct": 13,
    "dex": 14,
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
    ws["A1"] = "Buccaneer — DPS Calculator: How to Use This Workbook"
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
        "Shadow Heart, Quick Motion's AS component, Agile Knuckles, Dark Clarity, Knuckle "
        "Mastery, and Physical Training are always-on passives assumed to already be reflected "
        "in your own Inputs stat entries — only their Sensitivity marginal delta is modeled "
        "live, matching this project's established convention. Perseverance's own HP-regen has "
        "no DPS mechanic; its Mastery Lv.49 '+5% Attack when HP>=50%' needs HP tracking that "
        "doesn't exist anywhere in this project — not modeled, flagged. Admiral's Wings "
        "(damage-taken reduction) is purely defensive, not modeled. Mastery Lv.54 'Advanced "
        "Dash - Protection' references a skill absent from the entire skill overview list — "
        "flagged, unmodeled, no base skill to attach it to.",
        "This class has NO individual wiki pages at all (worse than Bishop) — every scaling "
        "skill's (baseDamage, factorIndex) is a FLAGGED ASSUMPTION derived from its single "
        "known level-1 value using the per-skill-type factorIndex convention, not a verified "
        "curve. Hook Bomber (basic attack) is the one exception, reusing the universal "
        "cross-class 4th-job-basic-attack constant (2900, 21). The Mastery table (Lv.12-138) "
        "IS real and confirmed — its discrete level-gated deltas are layered on top of the "
        "assumed base curves as genuine SkillMasteryBonus%/MasteryBossDamage% contributions.",
        "Sea Serpent Burst / Serpent Assault / Serpent Scale model Buccaneer's 'Assault Mode' "
        "resource economy (5 Serpent Scales -> 10s Assault Mode, swapping the basic-attack proc "
        "and adding +25% Final Damage) as a steady-state duty cycle, not an exact stack-gain/"
        "mode-toggle state machine — a documented approximation, reusing the existing "
        "ProcChance% machinery rather than inventing new state tracking. Because Corkscrew "
        "Blow (Lv.73+) costs its own action-slot time, unlocking it slightly *reduces* total "
        "DPS at that exact level boundary (verified numerically, not a bug) — it eats into "
        "Hook Bomber's own cast rate, which lowers Assault Mode uptime, and Serpent Assault "
        "loses more DPS from that than Corkscrew Blow itself adds.",
        "Octopunch + Sea Serpent's Rage + Raging Serpent Assault: Sea Serpent's Rage triggers "
        "unconditionally on every Octopunch cast (folded additively into Octopunch's own "
        "coefficient) plus its own extra-hits tick (Raging Serpent Assault) gated by the same "
        "Assault-Mode-uptime fraction above, since it only fires while in Assault Mode.",
        "Nautilus Strike (1950% dmg/15 targets/5 hits) is confirmed SHARED verbatim with "
        "Corsair (byte-identical wiki description) — a FLAGGED ASSUMPTION tuple (no cooldown "
        "stated anywhere either, 45s assumed by convention), reused directly by Corsair's own "
        "build rather than re-derived. Its own Mastery 'Nautilus Strike - Final Attack' "
        "(Lv.113, patched 15%->30% trigger chance, cooldown set to 1s) procs off basic attacks, "
        "modeled as its own row, same machinery as Bowmaster's Flash Mirage.",
        "Groggy Mastery's Aug-13 patch is a mechanic-TYPE change, not just a number change — "
        "generic 'damage +25%' becomes specifically 'Final Damage +8%'. Modeled as +8% Final "
        "Damage per the patch.",
        "Maple Hero's own wiki entry is genuinely truncated in the wiki's source (verified via "
        "raw wikitext, not a fetch bug): 'Increases Final Damage of the following skills: "
        "Serpent Assault 60%, Corkscrew...' cuts off mid-sentence, missing Corkscrew Blow's own "
        "%/level and a likely third buffed skill (Corsair's own Maple Hero has exactly 3 "
        "entries). Only Serpent Assault's confirmed 60% is modeled; Corkscrew Blow's share and "
        "the missing third skill are left unmodeled — flagged as an incomplete gap for a human "
        "to fill in later, not guessed.",
        "Crossbones, Speed Infusion, Time Leap, and Roll of the Dice have no cooldown data "
        "anywhere on the wiki — modeled as always-active once unlocked, flagged as a likely "
        "DPS overestimate versus their real (unknown) cooldowns.",
        "Content Type (Inputs) picks what you're fighting — Chapter Boss/Breakthrough/PvP/EXP "
        "Dungeon/Equipment Dungeon/Weapon Dungeon/Enhancement Dungeon/Hero Dungeon/World Boss/"
        "Chapter Hunt — and Monster Defense and Fixed Fight Duration are both auto-computed from "
        "it (plus Chapter/Stage for the chapter- and dungeon-based types); PvP still forces its "
        "own fixed 15-second window and uses your own Defense stat as the opponent's Defense "
        "estimate. See README.md's 'Content Type' section for the exact formulas.",
        "Not modeled (out of scope): all forms of crowd control (Corkscrew Blow's stun), "
        "Accuracy, Evasion, Defense, HP recovery, movement speed, and Companion Summoning Time.",
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
    ws["A1"] = "Buccaneer — DPS Calculator Inputs"
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
        ("attack_speed", "ATTACK_SPEED % (base, excludes Weapon Acceleration)", 0),
        ("flat_str", "Flat STR (include Iron Body's own +30 if unlocked)", 0),
        ("str_pct", "STR %", 0),
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
# Action-economy formula helpers — reused verbatim from build_bowmaster_workbook.py.
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
# Skills sheet schema — same core columns every sibling workbook shares.
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
    "HOOK_BOMBER", "SEA_SERPENT_BURST", "SERPENT_ASSAULT", "SERPENT_SCALE_FD",
    "CORKSCREW_BLOW", "OCTOPUNCH", "SEA_SERPENTS_RAGE", "RAGING_SERPENT_ASSAULT",
    "NAUTILUS_STRIKE", "NAUTILUS_FINAL_ATTACK", "MAPLE_HERO_HELPER",
    "ROLL_OF_THE_DICE_DICE", "CROSSBONES_FD", "TIME_LEAP_FD",
    "SHADOW_HEART", "QUICK_MOTION", "AGILE_KNUCKLES", "DARK_CLARITY",
    "KNUCKLE_MASTERY", "PHYSICAL_TRAINING", "GROGGY_MASTERY_FD",
]
ROW = {key: i for i, key in enumerate(ROW_ORDER, start=2)}
LAST_ROW = 1 + len(ROW_ORDER)

# ---------------------------------------------------------------------------
# Summary-sheet row layout — fixed constants, defined ahead of SKILL_ROWS (module-level list
# literal evaluated at import time) so any row needing to self-reference one of these can.
# ---------------------------------------------------------------------------
R_TOTAL = 3
SUMMARY_BREAKDOWN_HEADER_ROW = 6
R_AVGBUFF = 57                      # Attack% bucket (Roll of the Dice's dice component only)
R_CRIT_RATE_BONUS = 58              # unused placeholder (no live Crit-Rate-buff source exists)
R_MONSTER_DMG_BONUS = 59            # unused placeholder (no live monster-dmg-taken-buff source)
R_AS_BONUS = 60                     # unused placeholder (no live AS-buff source exists — Buccaneer has no Nimble-Feet-equivalent buff, Quick Motion is a flat passive)
R_APS = 61                          # Actions Per Second
R_CASTRATE = 62                     # Skill + buff cast rate (subtracted from Hook Bomber)
R_BAPS = 63                         # Hook Bomber (basic attack) Casts Per Second
R_CRIT_DAMAGE_BONUS = 64            # unused placeholder (no live Crit-Damage-buff source exists)
R_FD_BONUS = 65                     # Crossbones + Time Leap + Speed Infusion (live AS-linked formula) + Groggy Mastery is Magic-Critical instead
R_HOOK_BOMBER_DPS = 66
R_STARTUP_TIME = 67                 # Buff-Casting Startup Delay (s, fixed-duration only)
R_BOSS_ONLY_TOTAL = 68               # Total DPS if every hit were against a boss (Breakthrough Sensitivity baseline)
R_NORMAL_ONLY_TOTAL = 69             # Total DPS if every hit were against normal monsters (Breakthrough Sensitivity baseline)

# NOTE: Buccaneer's wiki overview page has NO Req.Level column at all (unlike every other class
# built so far) — every unlock level below is a FLAGGED ASSUMPTION inferred from the skill's own
# position in the overview list (which follows job-tier order) and cross-checked against the one
# hard constraint each Mastery-table entry gives (a mastery's own req-level is always >= its base
# skill's unlock level). Documented per-row below; a human should revisit these if real Req.Level
# data ever surfaces.
UNLOCK_LEVEL = {
    "HOOK_BOMBER": 100,
    "SEA_SERPENT_BURST": 35,
    "SERPENT_ASSAULT": 60,
    "SERPENT_SCALE_FD": 60,
    "CORKSCREW_BLOW": 63,
    "OCTOPUNCH": 100,
    "SEA_SERPENTS_RAGE": 110,
    "RAGING_SERPENT_ASSAULT": 110,
    "NAUTILUS_STRIKE": 103,
    "NAUTILUS_FINAL_ATTACK": 113,
    "MAPLE_HERO_HELPER": 100,
    "ROLL_OF_THE_DICE_DICE": 66,
    "CROSSBONES_FD": 107,
    "TIME_LEAP_FD": 115,
    "SHADOW_HEART": 15,
    "QUICK_MOTION": 10,
    "AGILE_KNUCKLES": 33,
    "DARK_CLARITY": 40,
    "KNUCKLE_MASTERY": 43,
    "PHYSICAL_TRAINING": 38,
    "GROGGY_MASTERY_FD": 75,
}


def unlock_expr(key):
    level = UNLOCK_LEVEL.get(key)
    return "=TRUE" if level is None else f"={IB('level')}>={level}"


# Maple Hero (Buccaneer) — the wiki's own source text is genuinely TRUNCATED mid-sentence
# ("Increases Final Damage of the following skills: Serpent Assault 60%, Corkscrew...") and no
# individual Maple_Hero_(Buccaneer) page exists to confirm its own growth curve either. Per direct
# user decision: model ONLY Serpent Assault's confirmed 60% (ratio 1.0), FLAGGED-ASSUMPTION curve
# (factorIndex 23, matching the universal Maple Hero convention confirmed on every other class -
# baseDamage 600 tenths% = 60% at level 1). Corkscrew Blow and the missing third skill are left
# completely unmodeled — a known incomplete gap, not guessed.
MAPLE_HERO_RATIOS = {
    "SERPENT_ASSAULT": 60 / 60,
}

# Assault Mode resource-economy uptime — Sea Serpent Burst procs on every basic attack (PATCHED:
# 40% chance -> guaranteed), granting 1 Serpent Scale (+1 more once Lv.104 mastery). At 5 scales,
# Assault Mode triggers for 10s (+5s once Lv.94 mastery), during which Serpent Assault replaces
# Sea Serpent Burst and Serpent Scale's own +25% FD buff is live. Modeled as a steady-state duty
# cycle (a documented approximation of a resource-stack economy, not an exact state machine):
# uptime = AssaultDuration / (AssaultDuration + ScalesNeeded/ScaleGainRate).
def _assault_duration_expr(ib=IB):
    return f'(10+IF({ib("level")}>=94,5,0))'


def _scale_gain_rate_expr(baps_ref, ib=IB):
    return f'({baps_ref}*(1+IF({ib("level")}>=104,1,0)))'


def assault_uptime_expr(baps_ref=None, ib=IB):
    if baps_ref is None:
        baps_ref = f"Summary!$B${R_BAPS}"
    dur = _assault_duration_expr(ib)
    rate = _scale_gain_rate_expr(baps_ref, ib)
    return f'({dur}/({dur}+5/{rate}))'


# (key, name, jobstep, cooldown, costsAction, actionsPerCast, hits, icd, window, chance, rolls,
#  baseDamage, factorIndex, scales, skillMasteryBonusPct, masteryBossDmgPct, masteryNormalDmgPct,
#  normalMonsterTargets, buffTarget, buffDuration, mapleBase, mapleFactor, note)
SKILL_ROWS = [
    ("HOOK_BOMBER", "Hook Bomber", 4, "", False, 1,
     f'=IF({IB("level")}>=136,6,5)', 0, 0, 100, 1,
     2900, 21, True,
     f"={level_gated_sum_raw(IB('level'), {102: 10, 106: 1, 116: 1, 120: 1, 128: 1, 132: 1})}",
     level_gated_sum(IB("level"), {111: 10, 124: 10}), 0,
     f'=6+{IB("basic_attack_target_increase")}', "", 0, "", "",
     "4th-job basic-attack effect (supersedes Somersault Kick/Shotgun Punch/Turning Kick, "
     "confirmed identical wiki wording — 290% damage to 6 target(s) in front 5 time(s) — to "
     "every other class's own 4th-job basic attack). factorIndex 21, baseDamage 2900 tenths%. "
     "HitsPerCast=5, bumping to 6 once Mastery Lv.136 'Hook Bomber - Strike' unlocks. Real "
     "Damage mastery chain (102/106/116/120/128/132, DELTAS not cumulative) and Boss Monster "
     "Damage chain (111/124, +10% each) — same level breakpoints as Hero's own Hook Bomber "
     "chain. No 'Final Attack' skill exists anywhere in Buccaneer's own kit, so unlike Hero/"
     "Dark Knight/Bowmaster/Marksman there is no two-stage Final-Attack-folding helper needed "
     "here."),
    ("SEA_SERPENT_BURST", "Sea Serpent Burst", 2, "", False, 1, 2, 0, 0,
     f'=100*(1-{assault_uptime_expr()})', 1,
     1300, 12, True,
     0, 0, 0, 5, "", 0, "", "",
     "FLAGGED ASSUMPTION (no individual wiki page exists — only the level-1 value is known): "
     "'When attacking with Basic Attack, Sea Serpent's waves spread...to deal 130% additional "
     "damage to 5 target(s) in front 2 time(s).' factorIndex 12 (burst convention), baseDamage "
     "1300 tenths%. PATCHED: 40% chance -> guaranteed on basic attack. Modeled as the "
     "'out of Assault Mode' half of this project's own Assault-Mode duty-cycle approximation "
     "(see assault_uptime_expr) — ProcChance% below is set to 100*(1-uptime), reusing the "
     "existing ProcProbability machinery to represent 'fraction of basic attacks NOT spent in "
     "Assault Mode' rather than a flat RNG chance. Greater Sea Serpent I (a slottable upgrade "
     "skill, not a mastery-table row — assumed always-equipped once unlocked, same convention "
     "as every other permanent passive-if-equipped skill in this project) changes targets to 7 "
     "and damage to 430% — folded directly into this row's own baseDamage/targets rather than "
     "modeled as a separate row, since it's a straight replacement of Sea Serpent Burst's own "
     "numbers, not an additive bonus."),
    ("SERPENT_ASSAULT", "Serpent Assault", 2, "", False, 1, 3, 0, 0,
     f'=100*{assault_uptime_expr()}', 1,
     4800, 12, True,
     0, 0, 0, 12, "", 0, 600, 23,
     "FLAGGED ASSUMPTION (no individual wiki page exists): 'When attacking with Basic Attack in "
     "Assault Mode, activates instead of Sea Serpent Burst to deal 480% additional damage to 12 "
     "nearby target(s) 3 time(s).' factorIndex 12, baseDamage 4800 tenths%. ProcChance% below is "
     "set to 100*uptime (see assault_uptime_expr) — the complementary half of Sea Serpent "
     "Burst's own duty-cycle split. Greater Sea Serpent II (slottable upgrade, assumed always-"
     "equipped once unlocked) adds +100% Final Damage and more targets ('spreads farther', "
     "exact new target count not stated anywhere on the wiki) — the +100% FD is folded in as a "
     "flat x2 multiplier baked into this row's own baseDamage (4800 already reflects it: raw "
     "level-1 value would be 2400, doubled here) since the target-count increase has no stated "
     "number to use. Maple Hero target (own confirmed 60% share, ratio 1.0) — see "
     "MAPLE_HERO_RATIOS."),
    ("SERPENT_SCALE_FD", "Serpent Scale (Assault Mode Final Damage)", 2, "", False, 1, 1, 0, 0, 100, 1,
     250, 22, True,
     0, 0, 0, 0, "FINAL_DAMAGE", 0, "", "",
     "FLAGGED ASSUMPTION (no individual wiki page exists): '[5 Serpent Scales Required] Consumes "
     "all Serpent Scales to enter Assault Mode...increases Final Damage by 25%.' factorIndex 22, "
     "baseDamage 250 tenths%. Modeled as active for exactly the assault_uptime_expr() fraction "
     "of the time (NOT the standard cooldown-driven buff_uptime() helper — this is a resource-"
     "stack economy, not a player cooldown, same category of deviation as Bowmaster's own "
     "AS-scaled Quiver Cartridge cooldown). The OTHER stated effect ('[Serpent Scale in Slot] "
     "when Sea Serpent Burst is activated, obtains Serpent Scale and increases Final Damage by "
     "2%, stacks up to 5 times' — a SEPARATE, smaller FD buff active BEFORE reaching Assault "
     "Mode) is NOT modeled — stacking an approximation on top of an already-approximated "
     "resource economy was judged out of scope for this session."),
    ("CORKSCREW_BLOW", "Corkscrew Blow", 3, 20, True, 1, 2, 0, 0, 100, 1,
     3400, 12, True,
     level_gated_sum(IB("level"), {73: 80}), 0, 0, 7, "", 0, "", "",
     "FLAGGED ASSUMPTION (no individual wiki page exists, no cooldown stated anywhere on the "
     "wiki either — 20s assumed by convention matching similarly-shaped 3rd-job burst skills "
     "elsewhere in this project): 'Charges to the front...to deal 340% damage to 7 target(s) 2 "
     "time(s) and stun them' (stun not modeled). factorIndex 12, baseDamage 3400 tenths%. "
     "Mastery Lv.73 'Corkscrew Blow - Damage' +80% (real SkillMasteryBonus%). CONFIRMED, "
     "EXPLAINED level-boundary DPS DIP at unlock (Lv.63, not a bug): this skill's own "
     "CostsActionSlot=True consumes basic-attack action-slot time, lowering Hook Bomber's own "
     "cast rate (Summary!$B$R_BAPS) — which the Assault-Mode duty cycle (assault_uptime_expr) "
     "is inversely sensitive to, since regen_time=5/(BAPS*scalesPerProc) grows as BAPS shrinks. "
     "Because Serpent Assault (riding on that same uptime) deals far more DPS than Corkscrew "
     "Blow itself adds, the net effect at Lv.63 is a small TOTAL DPS decrease versus Lv.62 — "
     "verified directly (Lv.62: 153242 total, uptime 0.6667; Lv.63: 148737 total, uptime 0.6552, "
     "Corkscrew Blow's own +5476 outweighed by Serpent Assault's -9725 and Sea Serpent Burst's "
     "-256). A genuine emergent consequence of the resource-economy approximation interacting "
     "with the shared action-slot budget, not a coding error — flagged explicitly here rather "
     "than silently accepted or hidden, per this project's own level-boundary-sweep rigor bar."),
    ("OCTOPUNCH", "Octopunch", 4, 15, True, 1,
     f'=3+IF(OR({IB("monster_type")}="boss",{IB("monster_type")}="pvp"),2,0)', 0, 0, 100, 1,
     9000, 12, True,
     level_gated_sum(IB("level"), {108: 50}), 0, 0,
     4, "", 0, "", "",
     "FLAGGED ASSUMPTION (no individual wiki page exists, no cooldown stated — 15s assumed by "
     "convention matching similarly-shaped 4th-job burst skills elsewhere): 'Throws a series of "
     "punches to deal 900% damage to 4 target(s) in front 3 time(s).' factorIndex 12, baseDamage "
     "9000 tenths%. Mastery Lv.108 'Octopunch - Damage' +50% (real SkillMasteryBonus%). The "
     "skill's own 'if the target is a boss, deals the same damage 2 more time(s)' clause is "
     "modeled via HitsPerCast (see below), NOT via this row's own NormalMonsterTargets field."),
    ("SEA_SERPENTS_RAGE", "Sea Serpent's Rage", 4, 15, False, 1, 2, 0, 0, 100, 1,
     17000, 12, True,
     0, 0, 0, 8, "", 0, "", "",
     "FLAGGED ASSUMPTION (no individual wiki page exists): 'When Octopunch is activated, a Sea "
     "Serpent appears and deals 1700% additional damage to 8 target(s) in front 2 time(s)' — "
     "UNCONDITIONAL on every Octopunch cast (own damage-taken-increase debuff on hit targets, "
     "15% for 5s, not modeled). Modeled as its own row sharing Octopunch's own Cooldown(s) value "
     "with CostsActionSlot=False and effectively guaranteed (ProcChance 100, RollsPerCast 1) — "
     "same 'shares parent's cast timing, doesn't double-count in the action economy' pattern as "
     "Hero's own PUNCTURE_WOUND sharing PUNCTURE's cooldown, chosen over folding into Octopunch's "
     "own coefficient because the two skills' target counts/hit counts differ (4/3 vs 8/2) and "
     "coefficient-folding assumes a shared target/hit shape. factorIndex 12, baseDamage 17000 "
     "tenths%."),
    ("RAGING_SERPENT_ASSAULT", "Raging Serpent Assault", 4, 15, False, 1, 1, 1, 5,
     f'=100*{assault_uptime_expr()}', 1,
     13000, 12, True,
     0, 0, 0, 9, "", 0, "", "",
     "FLAGGED ASSUMPTION (no individual wiki page exists): 'When attacking with Sea Serpent's "
     "Rage in Assault Mode, calls upon an enraged Sea Serpent...to deal 1300% damage to 9 nearby "
     "target(s) every 1 sec' for 5 sec (EffectiveHits = ActiveWindow/ICD = 5 ticks/cast). Shares "
     "SEA_SERPENTS_RAGE's own Cooldown(s) (same cast timing, CostsActionSlot=False) — gated "
     "ADDITIONALLY by the SAME Assault-Mode-uptime fraction as SEA_SERPENT_BURST/SERPENT_ASSAULT "
     "(ProcChance% = 100*uptime, see assault_uptime_expr) since this effect only fires while in "
     "Assault Mode, on top of Sea Serpent's Rage's own already-guaranteed trigger. factorIndex "
     "12, baseDamage 13000 tenths%."),
    ("NAUTILUS_STRIKE", "Nautilus Strike", 4, 45, True, 1, 5, 0, 0, 100, 1,
     19500, 12, True,
     0, 0, 0, 15, "", 0, "", "",
     "FLAGGED ASSUMPTION (no individual wiki page exists, no cooldown stated — 45s assumed by "
     "convention matching similarly-shaped big single-cast 4th-job nukes elsewhere): 'Orders the "
     "Nautilus to attack to deal 1950% damage to 15 nearby target(s) 5 time(s).' factorIndex 12, "
     "baseDamage 19500 tenths%. CONFIRMED SHARED VERBATIM WITH CORSAIR (byte-identical wiki "
     "description on both classes' overview pages) — Corsair's own build should reuse this exact "
     "(19500, 12) tuple directly rather than re-deriving it."),
    ("NAUTILUS_FINAL_ATTACK", "Nautilus Strike - Final Attack", 4, 1, False, 1, 1, 0, 0, 30, 1,
     8500, 21, True,
     0, 0, 0, 1, "", 0, "", "",
     "Mastery Lv.113 proc, not a base skill: '[Nautilus Strike in Slot] When attacking, deals "
     "850% additional damage' — PATCHED: trigger chance 15%->30%, 'cooldown set to 1s' (both "
     "baked in directly: ProcChance%=30, Cooldown(s)=1). Triggers off basic attacks generically "
     "(same Cooldown+ProcChance-gated machinery as Bowmaster's own Flash Mirage), CostsActionSlot"
     "=False so it doesn't compete with Hook Bomber's own action economy. factorIndex 21 "
     "(Final-Attack-style convention, matching every other 'additional damage on attack' proc in "
     "this project), baseDamage 8500 tenths%. Gated at Lv.113 (the mastery's own unlock level, "
     "not Nautilus Strike's base unlock) since the proc doesn't exist until this specific "
     "mastery tier is slotted."),
    ("MAPLE_HERO_HELPER", "Maple Hero (helper)", 4, "", False, 1, 1, 0, 0, 100, 1,
     600, 23, True,
     0, 0, 0, 0, "", 0, "", "",
     "Shared ratio-feeder row (see MAPLE_HERO_RATIOS) for Serpent Assault's own Final Damage "
     "chain — mirrors every other class's own Maple Hero mechanism. FLAGGED ASSUMPTION: the "
     "wiki's own source text for this row is genuinely TRUNCATED mid-sentence ('Serpent Assault "
     "60%, Corkscrew...') and no individual Maple_Hero_(Buccaneer) page exists to confirm a real "
     "growth curve — factorIndex 23 assumed by convention (matches the universal Maple Hero "
     "'growth-reduction after Lv.120' shape confirmed on every other class), baseDamage 600 "
     "tenths% anchored to the one confirmed level-1 value (60%). Corkscrew Blow's own share and "
     "a likely third buffed skill are completely unmodeled — a known incomplete gap, not "
     "guessed, per direct user decision. No independent DPS row of its own (Calc columns J-N "
     "blank/0, only D/E/F computed, read directly by Serpent Assault's own K-column formula)."),
    ("ROLL_OF_THE_DICE_DICE", "Roll of the Dice (dice component)", 2, "", False, 1, 1, 0, 0, 100, 1,
     25, 0, False,
     0, 0, 0, 0, "ATTACK", 0, "", "",
     "FLAGGED ASSUMPTION (no individual wiki page exists, no cooldown stated): 'Rolls a "
     "six-sided die every 7 sec to increase Attack by 0-5% in proportion to the number on the "
     "die for 5 sec.' The flat, unconditional '+20% Attack' base effect of this same skill is "
     "Magic-Critical-pattern (assumed already reflected in your own Inputs!ATTACK_PCT, see "
     "PASSIVE_DELTA_SLOT) — this row models ONLY the random dice component, approximated at its "
     "average roll (2.5%, the midpoint of 0-5%) treated as an always-active flat bonus once "
     "unlocked, rather than an actual RNG/duty-cycle process (the 'no repeat within 30s' rule "
     "and the 7s-roll/5s-duration timing are not modeled). factorIndex 0 (non-scaling "
     "placeholder — no data exists on whether the 0-5% range itself grows with level), "
     "baseDamage 25 tenths%."),
    ("CROSSBONES_FD", "Crossbones", 4, "", False, 1, 1, 0, 0, 100, 1,
     100, 22, True,
     0, 0, 0, 0, "FINAL_DAMAGE", 0, "", "",
     "FLAGGED ASSUMPTION (no individual wiki page exists, no cooldown/duration mechanics stated "
     "beyond 'for 12 sec' — modeled as always-active steady-state once unlocked rather than "
     "duty-cycled, since no cooldown is known to compute a real uptime fraction): 'Increases "
     "Final Damage by 10% and Defense Penetration by 5% for 12 sec.' Only the Final Damage "
     "component is modeled — this project has no live per-skill Defense-Penetration-bucket "
     "mechanism anywhere to reuse (Def Pen is normally a static Inputs field with its own "
     "diminishing-returns formula, not something a skill can contribute to live). factorIndex "
     "22, baseDamage 100 tenths%."),
    ("TIME_LEAP_FD", "Time Leap", 4, "", False, 1, 1, 0, 0, 100, 1,
     150, 22, True,
     0, 0, 0, 0, "FINAL_DAMAGE", 0, "", "",
     "FLAGGED ASSUMPTION (no individual wiki page exists, no real cooldown stated beyond 'a "
     "12-sec cooldown is applied at the start of battle when this skill is in slot' — modeled as "
     "always-active steady-state once unlocked after that initial delay, since no repeat-cast "
     "cooldown is known): 'Instantly decreases the cooldown of Active Skills by 50% and "
     "increases Final Damage by 30% for 40 sec.' PATCHED: Final Damage 30%->15% (a nerf) — "
     "modeled value already reflects the patch. The cooldown-reduction-for-other-skills effect "
     "is not modeled (no mechanic exists in this project for one skill's cooldown to modify "
     "another's). factorIndex 22, baseDamage 150 tenths% (already the patched 15%)."),
    ("SHADOW_HEART", "Shadow Heart", 1, "", False, 1, 1, 0, 0, 100, 1,
     50, 22, True,
     0, 0, 0, 0, "CRIT_RATE", 0, "", "",
     "Magic Critical pattern — already baked into Inputs!CRIT_RATE%; feeds the 1st-Job Skill "
     "Level Bonus delta. FLAGGED ASSUMPTION (no individual wiki page exists): 'Increases "
     "Critical Rate by 5%.' factorIndex 22, baseDamage 50 tenths%."),
    ("QUICK_MOTION", "Quick Motion", 1, "", False, 1, 1, 0, 0, 100, 1,
     60, 22, True,
     0, 0, 0, 0, "ATTACK_SPEED", 0, "", "",
     "Magic Critical pattern — already baked into Inputs!ATTACK_SPEED%; feeds the 1st-Job Skill "
     "Level Bonus delta. FLAGGED ASSUMPTION (no individual wiki page exists): 'Increases Attack "
     "Speed by 6% and Speed by 8%' (Speed component not modeled). Unlike every other class in "
     "this project, Buccaneer has NO Nimble-Feet-style live AS buff at all — Quick Motion is a "
     "flat passive instead, confirmed by its own overview text having no duration/cooldown "
     "language whatsoever (unlike Nimble Feet's explicit 'for 15 sec'). factorIndex 22, "
     "baseDamage 60 tenths%."),
    ("AGILE_KNUCKLES", "Agile Knuckles", 2, "", False, 1, 1, 0, 0, 100, 1,
     50, 22, True,
     level_gated_sum(IB("level"), {44: 7}), 0, 0, 0, "ATTACK_SPEED", 0, "", "",
     "Magic Critical pattern — already baked into Inputs!ATTACK_SPEED%; feeds the 2nd-Job Skill "
     "Level Bonus delta. FLAGGED ASSUMPTION (no individual wiki page exists): 'Increases Attack "
     "Speed by 5%.' factorIndex 22, baseDamage 50 tenths%. Mastery Lv.44 'Agile Knuckles - "
     "Speed' +7 (percentage points, real SkillMasteryBonus%)."),
    ("DARK_CLARITY", "Dark Clarity", 2, "", False, 1, 1, 0, 0, 100, 1,
     120, 22, True,
     0, 0, 0, 0, "ATTACK", 0, "", "",
     "Magic Critical pattern — already baked into Inputs!ATTACK_PCT (folds into the attack_mult "
     "delta bucket, same slot as Shadower's own Channel Karma/Bowmaster's own Soul Arrow: Bow). "
     "FLAGGED ASSUMPTION (no individual wiki page exists): 'Increases Attack by 12%.' "
     "factorIndex 22, baseDamage 120 tenths%."),
    ("KNUCKLE_MASTERY", "Knuckle Mastery", 2, "", False, 1, 1, 0, 0, 100, 1,
     150, 22, True,
     0, 0, 0, 0, "MIN_DAMAGE", 0, "", "",
     "Magic Critical pattern — already baked into Inputs!MIN_DAMAGE%; feeds the 2nd-Job Skill "
     "Level Bonus delta. FLAGGED ASSUMPTION (no individual wiki page exists): 'Increases Min "
     "Damage Multiplier by 15%.' factorIndex 22, baseDamage 150 tenths%."),
    ("PHYSICAL_TRAINING", "Physical Training", 2, "", False, 1, 1, 0, 0, 100, 1,
     100, 22, True,
     0, 0, 0, 0, "BASIC_ATTACK_DAMAGE", 0, "", "",
     "Magic Critical pattern — already baked into Inputs!BASIC_ATTACK_DAMAGE%; feeds the "
     "2nd-Job Skill Level Bonus delta. FLAGGED ASSUMPTION (no individual wiki page exists, "
     "though byte-identical wording to every other class's own Physical Training): 'Increases "
     "Basic Attack Damage by 10%.' factorIndex 22, baseDamage 100 tenths%."),
    ("GROGGY_MASTERY_FD", "Groggy Mastery", 2, "", False, 1, 1, 0, 0, 100, 1,
     80, 22, True,
     0, 0, 0, 0, "FINAL_DAMAGE", 0, "", "",
     "PATCHED — a mechanic-TYPE change, not just a number: pre-patch text reads 'Increases "
     "Status Effect Damage by 15% and damage by 25%' (generic damage bucket); the patch changes "
     "the second clause to 'Final Damage +8%' specifically. Modeled as +8% Final Damage per the "
     "patch (Status Effect Damage component not modeled, no such mechanic exists in this "
     "project). Magic Critical pattern — already baked into Inputs!FINAL_DAMAGE%; feeds the "
     "2nd-Job Skill Level Bonus delta. FLAGGED ASSUMPTION (no individual wiki page exists). "
     "factorIndex 22, baseDamage 80 tenths% (already the patched 8%)."),
]

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
DAMAGE_ROW_KEYS = [
    "SEA_SERPENT_BURST", "SERPENT_ASSAULT", "CORKSCREW_BLOW", "OCTOPUNCH",
    "SEA_SERPENTS_RAGE", "RAGING_SERPENT_ASSAULT", "NAUTILUS_STRIKE", "NAUTILUS_FINAL_ATTACK",
]
ATTACK_BUFF_ROW_KEYS = ["ROLL_OF_THE_DICE_DICE"]
# Buff-casting-startup-delay feature: rows with a real BuffDuration(s) that the character actively
# casts. Buccaneer has no such row (every buff-like source is an always-on "FD" passive with no
# live BuffDuration>0, per this class's own Notes) — kept empty rather than omitted so the shared
# startup-delay plumbing (build_calc_sheet/build_stat_block) has a consistent list to check.
BUFF_ROW_KEYS = []
PASSIVE_MULT_ROW_KEYS = [
    "SHADOW_HEART", "QUICK_MOTION", "AGILE_KNUCKLES", "DARK_CLARITY",
    "KNUCKLE_MASTERY", "PHYSICAL_TRAINING", "GROGGY_MASTERY_FD",
]
HELPER_ROW_KEYS = ["MAPLE_HERO_HELPER"]
MAPLE_HERO_ROW_KEYS = ["MAPLE_HERO_HELPER"]
DAMAGE_DEALING_KEYS = ["HOOK_BOMBER"] + DAMAGE_ROW_KEYS
# Sea Serpent Burst/Serpent Assault have NO real cooldown of their own — they fire exactly once
# per basic-attack cast (weighted by the Assault-Mode duty-cycle fraction via their own
# ProcChance% formula), so their own O-column DPS rides directly on Hook Bomber's own
# Summary!$B$R_BAPS cast rate instead of the generic Cooldown-driven rate machinery (which would
# otherwise force these rows into the PVP-fixed-15s branch of effective_cooldown_expr — wrong,
# since they should still fire at the real basic-attack rate in PvP, not once every 15 seconds).
RIDES_BASIC_ATTACK_KEYS = ["SEA_SERPENT_BURST", "SERPENT_ASSAULT"]

CALC_HEADERS = [
    "Key", "Name", "Unlocked", "InputLevel", "Factor", "CoefficientPercent",
    "EffectiveHits", "ProcProbability", "MapleHeroMultiplier",
    "BaseDamage", "BaseHitDamage", "NonCritAvg", "CritAvg", "ExpectedDamage(perHit)",
    "DPS", "% of Total", "InvCooldown", "CastsInFight", "HitRate(perSec)",
]
CCOL = {name: get_column_letter(i + 1) for i, name in enumerate(CALC_HEADERS)}


def S(col_name, r):
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
    final_damage_extra_ref = f"Summary!$B${R_FD_BONUS}"

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
            # Duration actually available for this row's casts in fixed-duration mode: the raw
            # fight duration for buffs (unaffected by the startup delay they themselves cause,
            # though Buccaneer has no live BuffDuration>0 rows so BUFF_ROW_KEYS is empty and this
            # branch is never taken), or that duration reduced by Summary!R_STARTUP_TIME for
            # non-buff (damage) rows. Must match whatever CastsInFight (column R, below) uses.
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

        if key == "HOOK_BOMBER":
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

        if key in (["HOOK_BOMBER"] + DAMAGE_ROW_KEYS):
            ws.cell(row=r, column=10, value=f'={IB("attack")}*(F{r}/100)')
            maple_ratio = MAPLE_HERO_RATIOS.get(key)
            mh_row = ROW["MAPLE_HERO_HELPER"]
            maple_hero_gated = f'IF(C{mh_row}=TRUE,F{mh_row},0)'
            maple_term = f'*(1+{maple_ratio}*{maple_hero_gated}/100)' if maple_ratio else ''
            ws.cell(row=r, column=11, value=(
                f'=J{r}*(1+{IB("stat_damage")}/100)*(1+{IB("damage")}/100)'
                f'*(1+{IB("damage_amp")}/100)'
                f'*(5000/(6000+{IB("monster_defense")}*(1-{IB("def_pen")}/100)))'
                f'*(1+({IB("final_damage")}+{final_damage_extra_ref})/100)'
                f'{maple_term}'
                f'*(1+(IF({S("Key", r)}="HOOK_BOMBER",{IB("basic_attack_damage")},{IB("skill_damage")}))/100)'
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

        if key == "HOOK_BOMBER":
            prefix = f"{S('HitsPerCast', r)}*N{r}*Summary!$B${R_BAPS}"
            boss_expr, normal_expr = boss_normal_dps_split_exprs(
                prefix, IB("monster_type"), boss_dmg_pct_r, normal_dmg_pct_r,
                S("NormalMonsterTargets", r), IB("max_enemies_hit"),
            )
            ws.cell(row=r, column=20, value=f'=IF(C{r},{boss_expr},0)')
            ws.cell(row=r, column=22, value=f'=IF(C{r},{normal_expr},0)')
        elif key in RIDES_BASIC_ATTACK_KEYS:
            prefix = f"{S('HitsPerCast', r)}*H{r}*N{r}*Summary!$B${R_BAPS}"
            boss_expr, normal_expr = boss_normal_dps_split_exprs(
                prefix, IB("monster_type"), boss_dmg_pct_r, normal_dmg_pct_r,
                S("NormalMonsterTargets", r), IB("max_enemies_hit"),
            )
            ws.cell(row=r, column=20, value=f'=IF(C{r},{boss_expr},0)')
            ws.cell(row=r, column=22, value=f'=IF(C{r},{normal_expr},0)')
        elif key in DAMAGE_ROW_KEYS:
            prefix = f'H{r}*N{r}*{rate_r}'
            boss_expr, normal_expr = boss_normal_dps_split_exprs(
                prefix, IB("monster_type"), boss_dmg_pct_r, normal_dmg_pct_r,
                S("NormalMonsterTargets", r), IB("max_enemies_hit"),
            )
            ws.cell(row=r, column=20, value=f'=IF(C{r},{boss_expr},0)')
            ws.cell(row=r, column=22, value=f'=IF(C{r},{normal_expr},0)')
        else:
            ws.cell(row=r, column=20, value=0)
            ws.cell(row=r, column=22, value=0)

        ws.cell(row=r, column=15, value=f'=(1-{IB("normal_weight_frac")})*T{r}+{IB("normal_weight_frac")}*V{r}')

        ws.cell(row=r, column=16, value=f'=IF(Summary!$B${R_TOTAL}=0,0,O{r}/Summary!$B${R_TOTAL})')
        ws.cell(row=r, column=17, value=(f'=IFERROR(1/{eff_cd_r},0)' if has_cooldown else 0))

        if has_cooldown:
            casts_formula = guarded_casts_expr(available_duration_r, eff_cd_r)
            ws.cell(row=r, column=18, value=f'=IF({fixed_duration_active_main},{casts_formula},0)')
        else:
            ws.cell(row=r, column=18, value=0)

        ws.cell(row=r, column=19, value=f'=IFERROR(O{r}/N{r},0)')

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
    ws["A1"] = "Buccaneer — DPS Summary"
    ws["A1"].font = Font(bold=True, size=14)

    ws.cell(row=DERIVED_HEADER_ROW, column=1, value="Derived Values (read-only, computed from Inputs)").font = SECTION_FONT
    ws.cell(row=D_ATTACK, column=1, value="ATTACK (= Flat ATTACK x (1+ATTACK%/100))")
    ws.cell(row=D_ATTACK, column=2, value=f'={IB("flat_attack")}*(1+{IB("attack_pct")}/100)')

    ws.cell(row=D_STAT_DAMAGE, column=1, value="STAT_DAMAGE % (= 1% of total STR + 0.25% of DEX)")
    ws.cell(
        row=D_STAT_DAMAGE, column=2,
        value=f'=({IB("flat_str")}*(1+{IB("str_pct")}/100))*0.01+{IB("dex")}*0.0025'
    )

    ws.cell(row=D_BASIC_INPUT_LEVEL, column=1, value="Basic Attack (Hook Bomber) Input Level (4th job formula)")
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
    ws.cell(row=D_SKILL_COEFFICIENT, column=1, value="SKILL_COEFFICIENT — Hook Bomber base coefficient % (before bonuses)")
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

    r_rd = ROW["ROLL_OF_THE_DICE_DICE"]
    r_ssfd = ROW["SERPENT_SCALE_FD"]
    r_cb, r_tl = ROW["CROSSBONES_FD"], ROW["TIME_LEAP_FD"]

    # Roll of the Dice's dice component: no cooldown known, modeled always-active once unlocked.
    roll_of_dice_avg = f'((Calc!C{r_rd}=TRUE)*Calc!F{r_rd})'
    # Serpent Scale's Assault-Mode FD buff: active for the assault_uptime_expr() fraction of the
    # time (a resource-economy duty cycle, NOT the standard cooldown-driven buff_uptime() helper).
    serpent_scale_avg = f'((Calc!C{r_ssfd}=TRUE)*Calc!F{r_ssfd}*{assault_uptime_expr()})'
    # Crossbones/Time Leap: no cooldown known for either, modeled always-active once unlocked.
    crossbones_avg = f'((Calc!C{r_cb}=TRUE)*Calc!F{r_cb})'
    time_leap_avg = f'((Calc!C{r_tl}=TRUE)*Calc!F{r_tl})'
    # Speed Infusion's Final Damage component is a LIVE formula (20% of the character's own total
    # Attack Speed%), not a flat baseDamage/factorIndex curve — no Skills-sheet row exists for it;
    # gated by its own assumed Lv.110 unlock (see UNLOCK_LEVEL's own commentary on Speed Infusion's
    # sibling skills), computed directly from Summary!$B$R_APS (Actions Per Second) since
    # TotalAS% = (APS-1)*100.
    speed_infusion_avg = f'(({IB("level")}>=110)*20*(B{R_APS}-1))'

    ws.cell(row=R_AVGBUFF, column=1, value="Attack%% Bucket Multiplier (Roll of the Dice's dice component only)")
    ws.cell(row=R_AVGBUFF, column=2, value=f'=1+({roll_of_dice_avg})/100')

    ws.cell(row=R_CRIT_RATE_BONUS, column=1, value="Global Crit Rate Bonus % (unused — no live Crit-Rate-buff source exists)")
    ws.cell(row=R_CRIT_RATE_BONUS, column=2, value=0)

    ws.cell(row=R_MONSTER_DMG_BONUS, column=1, value="Global Monster Damage-Taken Bonus % (unused — no live source exists in this kit)")
    ws.cell(row=R_MONSTER_DMG_BONUS, column=2, value=0)

    ws.cell(row=R_AS_BONUS, column=1, value="Attack Speed Buff Bonus % (unused — Buccaneer has no Nimble-Feet-style live AS buff)")
    ws.cell(row=R_AS_BONUS, column=2, value=0)

    ws.cell(row=R_APS, column=1, value="Actions Per Second")
    ws.cell(row=R_APS, column=2, value=(
        f'=1+MIN(150,150*(1-(1-{IB("attack_speed")}/150)*(1-B{R_AS_BONUS}/150)))/100'
    ))

    ws.cell(row=R_CASTRATE, column=1, value="Skill + Buff Cast Rate (subtracted from Hook Bomber, 1/s)")
    ws.cell(row=R_CASTRATE, column=2, value=(
        f'=IF({fda_main},'
        f'SUMPRODUCT((Skills!{SC["CostsActionSlot"]}2:{SC["CostsActionSlot"]}{LAST_ROW}=TRUE)*'
        f'(Calc!C2:C{LAST_ROW}=TRUE)*Calc!R2:R{LAST_ROW}*Skills!{SC["ActionsPerCast"]}2:{SC["ActionsPerCast"]}{LAST_ROW})/{IB("fight_duration")},'
        f'SUMPRODUCT((Skills!{SC["CostsActionSlot"]}2:{SC["CostsActionSlot"]}{LAST_ROW}=TRUE)*'
        f'(Calc!C2:C{LAST_ROW}=TRUE)*Calc!Q2:Q{LAST_ROW}*Skills!{SC["ActionsPerCast"]}2:{SC["ActionsPerCast"]}{LAST_ROW}))'
    ))

    ws.cell(row=R_BAPS, column=1, value="Hook Bomber (Basic Attack) Casts Per Second")
    ws.cell(row=R_BAPS, column=2, value=f'=MAX(0,B{R_APS}-B{R_CASTRATE})')

    ws.cell(row=R_CRIT_DAMAGE_BONUS, column=1, value="Global Critical Damage Bonus % (unused — no live Crit-Damage-buff source exists)")
    ws.cell(row=R_CRIT_DAMAGE_BONUS, column=2, value=0)

    ws.cell(row=R_FD_BONUS, column=1, value="Global Final Damage Bonus % (Serpent Scale + Crossbones + Time Leap + Speed Infusion)")
    ws.cell(row=R_FD_BONUS, column=2, value=f'={serpent_scale_avg}+{crossbones_avg}+{time_leap_avg}+{speed_infusion_avg}')

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

    ws.cell(row=R_HOOK_BOMBER_DPS, column=1, value="Hook Bomber (Basic Attack) DPS")
    ws.cell(row=R_HOOK_BOMBER_DPS, column=2, value=f"=Calc!O{ROW['HOOK_BOMBER']}")

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
# Sensitivity sheet: marginal DPS from bumping each Inputs stat by +1 — mirrors Bowmaster's own
# STAT_SWEEP/PASSIVE_DELTA_SLOT/build_stat_block pattern (STR main / DEX sub identity — mirror
# rename of Bowmaster's own DEX/STR sweep).
# ---------------------------------------------------------------------------
STAT_SWEEP = [
    ("flat_str", "Flat STR", "flat"),
    ("str_pct", "STR %", "pct"),
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
    "Dex %": "dex",
    "Dex": "dex",
    "Basic Attack Damage %": "basic_attack_damage",
    "Skill Damage %": "skill_damage",
    "Skill Cooldown Decrease (seconds)": "skill_cooldown_decrease",
    "Buff Duration Increase %": "buff_duration_increase_pct",
    "All Skill Level": "skill_lvl_all",
    "Basic Attack Target Increase": "basic_attack_target_increase",
}


def dps_per_unit_expr(stat_name):
    if stat_name == "Main Stat Per Level":
        return f'=Sensitivity!H{SENSITIVITY_ROW_FOR["flat_str"]}*{IB("level")}'
    if stat_name == "Main Stat % per 4 Levels":
        return f'=Sensitivity!H{SENSITIVITY_ROW_FOR["str_pct"]}*INT({IB("level")}/4)'
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
# delta folds into. "attack_mult" has no literal Inputs field — Dark Clarity's own flat Attack%
# component shares it (same slot as Shadower's own Channel Karma/Bowmaster's own Soul Arrow: Bow).
PASSIVE_DELTA_SLOT = {
    "SHADOW_HEART": "crit_rate",
    "QUICK_MOTION": "attack_speed",
    "AGILE_KNUCKLES": "attack_speed",
    "DARK_CLARITY": "attack_mult",
    "KNUCKLE_MASTERY": "min_damage",
    "PHYSICAL_TRAINING": "basic_attack_damage",
    "GROGGY_MASTERY_FD": "final_damage",
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
            return f'(({ib("flat_str")}*(1+{ib("str_pct")}/100))*0.01+{ib("dex")}*0.0025)'
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
    s_fd_bonus = calc_end + 9
    s_startup = calc_end + 10
    s_boss_total = calc_end + 11
    s_normal_total = calc_end + 12
    s_total = calc_end + 13
    crit_rate_bonus_ref = f"B{s_crit_rate_bonus}"
    as_bonus_ref, aps_ref, castrate_ref, baps_ref = f"B{s_as_bonus}", f"B{s_aps}", f"B{s_castrate}", f"B{s_baps}"
    crit_damage_bonus_ref = f"B{s_crit_damage_bonus}"
    fd_bonus_ref = f"B{s_fd_bonus}"
    total_ref = f"B{s_total}"
    startup_ref = f"B{s_startup}"
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

    # Flat ATTACK is assumed to already include the character's current STR/DEX-derived attack
    # (1 total STR = 1 flat Attack, 1 DEX = 0.25 flat Attack, added into the pool before ATTACK%
    # applies) — same "already baked into Inputs, only the Sensitivity marginal delta matters"
    # pattern used elsewhere in this block. Identically 0 for every block except the ones sweeping
    # flat_str/str_pct/dex.
    mainstat_attack_delta = (
        f'((({ib("flat_str")}*(1+{ib("str_pct")}/100))-({IB("flat_str")}*(1+{IB("str_pct")}/100)))'
        f'+0.25*({ib("dex")}-{IB("dex")}))'
    )

    r_rd = ROW["ROLL_OF_THE_DICE_DICE"]
    r_ssfd = ROW["SERPENT_SCALE_FD"]
    r_cb, r_tl = ROW["CROSSBONES_FD"], ROW["TIME_LEAP_FD"]

    roll_of_dice_avg = f'((C{row_of["ROLL_OF_THE_DICE_DICE"]}=TRUE)*F{row_of["ROLL_OF_THE_DICE_DICE"]})'
    serpent_scale_avg = (
        f'((C{row_of["SERPENT_SCALE_FD"]}=TRUE)*F{row_of["SERPENT_SCALE_FD"]}*'
        f'{assault_uptime_expr(baps_ref, ib)})'
    )
    crossbones_avg = f'((C{row_of["CROSSBONES_FD"]}=TRUE)*F{row_of["CROSSBONES_FD"]})'
    time_leap_avg = f'((C{row_of["TIME_LEAP_FD"]}=TRUE)*F{row_of["TIME_LEAP_FD"]})'
    speed_infusion_avg = f'(({ib("level")}>=110)*20*({aps_ref}-1))'
    # Attack% bucket: every live skill/buff Attack% source sums additively into ONE combined
    # percentage before a single multiplication — matches Verification item 6.
    attack_bucket_block = f'(1+({roll_of_dice_avg}+{delta["attack_mult"]})/100)'

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

        if key == "HOOK_BOMBER":
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

        if key in (["HOOK_BOMBER"] + DAMAGE_ROW_KEYS):
            ws.cell(row=row, column=10, value=(
                f'=({ib("attack")}+{mainstat_attack_delta}*(1+{ib("attack_pct")}/100))*(F{row}/100)'
            ))
            crit_rate_total_block = f'({ib("crit_rate")}+{delta["crit_rate"]}+{crit_rate_bonus_ref})'
            maple_ratio = MAPLE_HERO_RATIOS.get(key)
            mh_row_of = row_of["MAPLE_HERO_HELPER"]
            maple_hero_gated_block = f'IF(C{mh_row_of}=TRUE,F{mh_row_of},0)'
            maple_term = f'*(1+{maple_ratio}*{maple_hero_gated_block}/100)' if maple_ratio else ''
            ws.cell(row=row, column=11, value=(
                f'=J{row}*(1+{ib("stat_damage")}/100)*(1+{ib("damage")}/100)'
                f'*(1+{ib("damage_amp")}/100)'
                f'*(5000/(6000+{ib("monster_defense")}*(1-({ib("def_pen")}+{delta["def_pen"]})/100)))'
                f'*(1+({ib("final_damage")}+{delta["final_damage"]}+{fd_bonus_ref})/100)'
                f'{maple_term}'
                f'*(1+(IF({S("Key", r)}="HOOK_BOMBER",{ib("basic_attack_damage")}+{delta["basic_attack_damage"]},'
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

        if key == "HOOK_BOMBER":
            raging_blow_targets_expr = f'(6+{ib("basic_attack_target_increase")})'
            prefix = f"{S('HitsPerCast', r)}*N{row}*{baps_ref}"
            boss_expr, normal_expr = boss_normal_dps_split_exprs(
                prefix, ib("monster_type"), boss_dmg_pct_row, normal_dmg_pct_row,
                raging_blow_targets_expr, ib("max_enemies_hit"),
            )
            ws.cell(row=row, column=20, value=f'=IF(C{row},{boss_expr},0)')
            ws.cell(row=row, column=22, value=f'=IF(C{row},{normal_expr},0)')
        elif key in RIDES_BASIC_ATTACK_KEYS:
            prefix = f"{S('HitsPerCast', r)}*H{row}*N{row}*{baps_ref}"
            boss_expr, normal_expr = boss_normal_dps_split_exprs(
                prefix, ib("monster_type"), boss_dmg_pct_row, normal_dmg_pct_row,
                S("NormalMonsterTargets", r), ib("max_enemies_hit"),
            )
            ws.cell(row=row, column=20, value=f'=IF(C{row},{boss_expr},0)')
            ws.cell(row=row, column=22, value=f'=IF(C{row},{normal_expr},0)')
        elif key in DAMAGE_ROW_KEYS:
            prefix = f'H{row}*N{row}*{rate_row}'
            boss_expr, normal_expr = boss_normal_dps_split_exprs(
                prefix, ib("monster_type"), boss_dmg_pct_row, normal_dmg_pct_row,
                S("NormalMonsterTargets", r), ib("max_enemies_hit"),
            )
            ws.cell(row=row, column=20, value=f'=IF(C{row},{boss_expr},0)')
            ws.cell(row=row, column=22, value=f'=IF(C{row},{normal_expr},0)')
        else:
            ws.cell(row=row, column=20, value=0)
            ws.cell(row=row, column=22, value=0)

        ws.cell(row=row, column=15, value=f'=(1-{ib("normal_weight_frac")})*T{row}+{ib("normal_weight_frac")}*V{row}')

        ws.cell(row=row, column=16, value=f'=IF({total_ref}=0,0,O{row}/{total_ref})')
        ws.cell(row=row, column=17, value=(f'=IFERROR(1/{eff_cd_row},0)' if has_cooldown else 0))
        if has_cooldown:
            casts_formula_block = guarded_casts_expr(available_duration_row, eff_cd_row)
            ws.cell(row=row, column=18, value=f'=IF({fda_block},{casts_formula_block},0)')
        else:
            ws.cell(row=row, column=18, value=0)
        ws.cell(row=row, column=19, value=f'=IFERROR(O{row}/N{row},0)')

    attack_speed_with_delta = f'({ib("attack_speed")}+{delta["attack_speed"]})'

    ws.cell(row=s_avgbuff, column=1, value="Attack% Bucket Multiplier")
    ws.cell(row=s_avgbuff, column=2, value=f'={attack_bucket_block}')

    ws.cell(row=s_crit_rate_bonus, column=1, value="Global Crit Rate Bonus %")
    ws.cell(row=s_crit_rate_bonus, column=2, value=0)

    ws.cell(row=s_as_bonus, column=1, value="Attack Speed Buff Bonus % (unused)")
    ws.cell(row=s_as_bonus, column=2, value=0)

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

    ws.cell(row=s_baps, column=1, value="Hook Bomber Casts Per Second")
    ws.cell(row=s_baps, column=2, value=f'=MAX(0,{aps_ref}-{castrate_ref})')

    ws.cell(row=s_crit_damage_bonus, column=1, value="Global Critical Damage Bonus % (unused)")
    ws.cell(row=s_crit_damage_bonus, column=2, value=0)

    ws.cell(row=s_fd_bonus, column=1, value="Global Final Damage Bonus % (Serpent Scale + Crossbones + Time Leap + Speed Infusion)")
    ws.cell(row=s_fd_bonus, column=2, value=f'={serpent_scale_avg}+{crossbones_avg}+{time_leap_avg}+{speed_infusion_avg}')

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
        # DPS Gain/% Gain are time-weighted (not dollar-weighted) across the boss/normal branches —
        # see boss_normal_dps_split_exprs's docstring for the rationale.
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
    """If a previous Hero-DPS-Calculator.xlsx already exists at `path`, read back its Inputs
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
