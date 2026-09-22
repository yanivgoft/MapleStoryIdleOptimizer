#!/usr/bin/env python3
"""
Generates Corsair-DPS-Calculator.xlsx: a live-formula Excel replica of a Corsair skill-rotation
DPS model, sibling to build_buccaneer_workbook.py. Corsair is DEX-main/STR-sub (same identity as
Bowmaster/Marksman) — the OPPOSITE identity from its own sibling Pirate-tree class Buccaneer
(STR-main/DEX-sub), confirmed directly by the user, not shared.

Sheets: Inputs, FactorTable, Skills, Calc, Summary, Sensitivity, CubeData, PotentialCubes.

CRITICAL DATA-QUALITY CAVEAT (worse than any class built so far, including Buccaneer/Bishop):
the `Corsair/Skills` wiki overview page is a bare two-column (Skill, Description) table — no
job-tier headers, no Type, no Req. Level, no Cooldown columns at all. ZERO individual wiki pages
exist for any of Corsair's 29 skills (confirmed genuine 404s). `Corsair/Mastery` DOES NOT EXIST AS
A PAGE AT ALL (confirmed redlink + 404) — unlike every other class built so far (even Buccaneer/
Bishop have real mastery tables), Corsair has ZERO mastery data of any kind on the wiki.

Per direct user decision on both gaps:
  1. Every scaling skill uses the FLAGGED-ASSUMPTION convention (baseDamage/factorIndex derived
     from the single known level-1 value using the per-skill-type factorIndex convention:
     burst/DoT->12, buffs/passives->22, basic attack->21) — same as Buccaneer/Bishop.
  2. Mastery bonuses are modeled by ASSUMING Corsair's own mastery table has the SAME STRUCTURAL
     SHAPE as Buccaneer's own real, confirmed mastery table — same level breakpoints/delta
     patterns applied to Corsair's own analogous skill-slot roles where a reasonable mapping
     exists (the universal 4th-job-basic-attack chain, and Nautilus Strike's own two mastery
     tiers, both of which are literally the SAME shared skill/mechanic as Buccaneer's). For
     Corsair-unique skills with no clean 1:1 Buccaneer analog (the two kits' unique mechanics
     don't correspond skill-for-skill — Buccaneer's is a resource-stack economy, Corsair's is
     crew-summon/turret-based), NO mastery bonus is assumed rather than forcing a poor mapping;
     documented per-row as "no clean Buccaneer analog, left unmodeled."
  BOTH gaps (no Mastery page, no individual pages) are incomplete-for-later per the user's own
  words — this entire mastery layer is a documented ASSUMPTION, not verified data.

Ground truth: fetched live from idle.maplestorywiki.net this session, cross-referenced against the
Aug 13 patch notes PDF's Corsair section. All patched skills confirmed STALE on the live wiki
(pre-patch numbers) — patch deltas applied manually.

Key mechanics/simplifications specific to this kit:
  - Eight-Legs Easton (basic attack) reuses the universal 4th-job-basic-attack constant (baseDamage
    2900, factorIndex 21). HitsPerCast=5, bumping to 6 once the assumed Mastery Lv.136 tier
    unlocks (mapped from Buccaneer's own Hook Bomber - Strike slot). Real Damage mastery chain
    (102/106/116/120/128/132, DELTAS) and Boss Monster Damage chain (111/124, +10% each) —
    mapped directly from Buccaneer's own Hook Bomber chain, which is itself the same universal
    pattern confirmed across every class in this project.
  - Nautilus Strike (1950% dmg/15 targets/5 hits) is CONFIRMED SHARED VERBATIM with Buccaneer
    (byte-identical wiki description) — reuses Buccaneer's exact (19500, 12) FLAGGED-ASSUMPTION
    tuple directly, not re-derived. Its own "Nautilus Strike - Final Attack" mastery proc
    (Lv.113, PATCHED 15%->30% trigger chance/cooldown set to 1s/850% dmg) is ALSO confirmed
    shared (same patch note applies to both classes identically) — reuses Buccaneer's exact row
    shape.
  - Roll of the Dice is ALSO confirmed shared verbatim with Buccaneer (byte-identical wiki
    description, not previously flagged by the research report but discovered during this
    build) — reuses Buccaneer's exact (25, 0) dice-component tuple + the same flat +20% Attack
    Magic-Critical treatment.
  - Scurvy Summons / All Aboard: crew-summon mechanics (NOT Buccaneer's resource-economy —
    Corsair's own kit has no analogous mechanic). Modeled with the standard generic
    ActiveWindow/ICD tick machinery already used for every summon/turret skill in this project
    (Bowmaster's Phoenix/Arrow Platter, FP-Mage's Ifrit) — no bespoke code needed. All Aboard is
    triggered by Scurvy Summons and shares its own Cooldown(s)/duration values directly
    (CostsActionSlot=False so it doesn't double-count the action economy), same pattern as
    Buccaneer's own Sea Serpent's Rage riding Octopunch's cast timing.
  - Broadside splits into two rows (initial burst + sustained turret), same pattern as Hero's own
    Puncture (direct hit + wound DoT) — the burst pays the real Cooldown(s)/action-slot cost, the
    sustained phase rides the same Cooldown(s) value with CostsActionSlot=False.
  - Majestic Presence procs off THREE independent sources (Basic Attack, Brain Scrambler, Rapid
    Fire) — modeled as its own bespoke combined-trigger-rate row (summing the three sources' own
    HitRate(perSec) values directly), structurally similar to Marksman's own Bolt Surplus
    dual-trigger pattern extended to three sources instead of two.
  - Ahoy Mateys (+250% FD to Scurvy Summons, +100% to All Aboard) is its own helper row, same
    "shared ratio-feeder, no independent DPS row" mechanism as Maple Hero, just a second,
    independent helper feeding the same two skills' K-column terms alongside Maple Hero's own.
  - Maple Hero (Corsair)'s own level-1 anchor values ARE real/confirmed (Siege Bomber 20%,
    Blackboot Bill 40%, Swift Fire 80%, unlike Buccaneer's own truncated entry) — only the
    growth curve shape is a FLAGGED ASSUMPTION (factorIndex 23, the universal Maple Hero
    convention confirmed on every other class).
  - Recoil Shot's own wiki text explicitly states "This skill is not used automatically" —
    excluded entirely, no row, matching this project's treatment of manually-triggered skills.
  - Outlaw's Code (Defense/Debuff Tolerance) is purely defensive, not modeled. Shadow Heart,
    Quick Motion (AS component only), Agile Guns, Gun Mastery, Physical Training, Infinity Blast,
    Fullmetal Jacket, Cross Cut Blast, Quickdraw's own flat +25% Basic Attack Damage component are
    all Magic-Critical-pattern always-on passives assumed already reflected in your own Inputs
    stat entries — only their Sensitivity marginal delta is modeled live. Quickdraw's own
    triple-cast-damage-doubling proc and cross-skill cooldown reduction are not modeled (no
    mechanic exists in this project for one skill's cast count to modify another's cooldown).
  - Jolly Roger (PATCHED FD 18%->15%, a nerf) has no stated cooldown — modeled always-active
    steady-state once unlocked, same FLAGGED-assumption tier as Buccaneer's own Crossbones/Time
    Leap. This is Corsair's only live (non-Magic-Critical) Final Damage source.
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
OUT_PATH = REPO / "Corsair" / "Corsair-DPS-Calculator.xlsx"

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
    ws["A1"] = "Corsair — DPS Calculator: How to Use This Workbook"
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
        "CRITICAL: Corsair has ZERO individual wiki pages AND no Mastery page at all — worse than "
        "any other class built in this project. Every scaling skill's (baseDamage, factorIndex) "
        "is a FLAGGED ASSUMPTION from its own level-1 value; every mastery bonus below is a "
        "FLAGGED ASSUMPTION mapped from Buccaneer's own real mastery table by skill-slot role, "
        "per direct user decision. This entire workbook's accuracy ceiling is lower than every "
        "sibling class — treat every number as a documented estimate, not verified data.",
        "Shadow Heart, Quick Motion (AS component only), Agile Guns, Gun Mastery, Physical "
        "Training, Infinity Blast, Fullmetal Jacket, Cross Cut Blast, and Quickdraw's own flat "
        "+25% Basic Attack Damage component are always-on passives assumed to already be "
        "reflected in your own Inputs stat entries — only their Sensitivity marginal delta is "
        "modeled live, matching this project's established convention.",
        "Eight-Legs Easton (basic attack) reuses the universal 4th-job-basic-attack constant "
        "(baseDamage 2900, factorIndex 21) confirmed identical across every class in this "
        "project. Its own Mastery chain is mapped from Buccaneer's own Hook Bomber chain (same "
        "universal pattern).",
        "Nautilus Strike and Roll of the Dice are both CONFIRMED SHARED verbatim with Buccaneer "
        "(byte-identical wiki descriptions) — reuse Buccaneer's exact resolved tuples directly, "
        "not re-derived.",
        "Scurvy Summons / All Aboard (crew summons) and Broadside's burst+sustained split use "
        "the standard generic ActiveWindow/ICD tick machinery already used for every summon/"
        "turret skill in this project (Bowmaster's Phoenix, FP-Mage's Ifrit) — no bespoke "
        "mechanics needed.",
        "Majestic Presence procs off three independent sources (Basic Attack, Brain Scrambler, "
        "Rapid Fire) — modeled as its own combined-trigger-rate row summing the three sources' "
        "own hit rates directly, extending Marksman's own Bolt Surplus dual-trigger pattern to "
        "three sources.",
        "Ahoy Mateys (+250%/+100% FD to Scurvy Summons/All Aboard) is its own helper row, same "
        "mechanism as Maple Hero — both feed the same two skills' K-column terms independently.",
        "Recoil Shot is explicitly 'not used automatically' per its own wiki text — excluded "
        "entirely, no row. Outlaw's Code (Defense/Debuff Tolerance) is purely defensive, not "
        "modeled.",
        "Jolly Roger (PATCHED FD 18%->15%, a nerf) has no stated cooldown — modeled always-active "
        "steady-state once unlocked, same tier as Buccaneer's own Crossbones/Time Leap.",
        "Content Type (Inputs) picks what you're fighting — Chapter Boss/Breakthrough/PvP/EXP "
        "Dungeon/Equipment Dungeon/Weapon Dungeon/Enhancement Dungeon/Hero Dungeon/World Boss/"
        "Chapter Hunt — and Monster Defense and Fixed Fight Duration are both auto-computed from "
        "it (plus Chapter/Stage for the chapter- and dungeon-based types); PvP still forces its "
        "own fixed 15-second window and uses your own Defense stat as the opponent's Defense "
        "estimate. See README.md's 'Content Type' section for the exact formulas.",
        "Not modeled (out of scope): all forms of crowd control (Blackboot Bill's stun), "
        "Accuracy, Evasion, Defense, movement speed, and Companion Summoning Time.",
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
    ws["A1"] = "Corsair — DPS Calculator Inputs"
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
        ("flat_dex", "Flat DEX", 0),
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
    (the H*N*rate*(extra multipliers) part shared by both — everything upstream of the monster-type
    split is already monster-type-independent). Each branch gets its own full
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
    (one action-slot's worth of time each, same cadence as every other active-cast skill). Zero
    outside fixed-duration mode. Corsair has no BuffDuration(s)>0 rows today, so this is currently
    always 0 — kept for architectural consistency with the other 11 classes and in case a future
    Corsair buff skill is added."""
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
    must match, or the last cast's truncated tick window would be computed against a duration
    inconsistent with how many casts were actually counted."""
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
    "EIGHT_LEGS_EASTON", "SWIFT_FIRE", "SCURVY_SUMMONS", "ALL_ABOARD",
    "BLACKBOOT_BILL", "SIEGE_BOMBER", "BRAIN_SCRAMBLER",
    "NAUTILUS_STRIKE", "NAUTILUS_FINAL_ATTACK", "RAPID_FIRE",
    "BROADSIDE_BURST", "BROADSIDE_SUSTAINED", "MAJESTIC_PRESENCE",
    "MAPLE_HERO_HELPER", "AHOY_MATEYS_HELPER",
    "ROLL_OF_THE_DICE_DICE", "JOLLY_ROGER_FD",
    "SHADOW_HEART", "QUICK_MOTION", "AGILE_GUNS", "GUN_MASTERY",
    "PHYSICAL_TRAINING", "INFINITY_BLAST_ATK", "FULLMETAL_JACKET_CD",
    "CROSS_CUT_BLAST_FD", "QUICKDRAW_BAD",
]
ROW = {key: i for i, key in enumerate(ROW_ORDER, start=2)}
LAST_ROW = 1 + len(ROW_ORDER)

# ---------------------------------------------------------------------------
# Summary-sheet row layout — fixed constants, defined ahead of SKILL_ROWS (module-level list
# literal evaluated at import time) so any row needing to self-reference one of these can.
# Corsair's own live-buff buckets are SIMPLER than Buccaneer's (no Assault-Mode-style resource
# economy) — most of Corsair's buff-like skills are Magic-Critical-pattern (baked into Inputs),
# leaving only Roll of the Dice's dice component (Attack% bucket) and Jolly Roger (FD bucket) as
# genuinely live sources.
# ---------------------------------------------------------------------------
R_TOTAL = 3
SUMMARY_BREAKDOWN_HEADER_ROW = 6
R_AVGBUFF = 57                      # Attack% bucket (Roll of the Dice's dice component only — shared skill w/ Buccaneer)
R_CRIT_RATE_BONUS = 58              # unused placeholder (no live Crit-Rate-buff source exists)
R_MONSTER_DMG_BONUS = 59            # unused placeholder (no live monster-dmg-taken-buff source)
R_AS_BONUS = 60                     # unused placeholder (no live AS-buff source exists — Corsair has no Nimble-Feet-equivalent buff, Quick Motion is a flat passive, same as Buccaneer)
R_APS = 61                          # Actions Per Second
R_CASTRATE = 62                     # Skill + buff cast rate (subtracted from Eight-Legs Easton)
R_BAPS = 63                         # Eight-Legs Easton (basic attack) Casts Per Second
R_CRIT_DAMAGE_BONUS = 64            # unused placeholder (no live Crit-Damage-buff source exists)
R_FD_BONUS = 65                     # Jolly Roger only (live, always-active-once-unlocked FD buff)
R_EIGHT_LEGS_EASTON_DPS = 66
R_STARTUP_TIME = 67                 # Buff-Casting Startup Delay (s, fixed-duration only)
R_BOSS_ONLY_TOTAL = 68               # Total DPS if every hit were against a boss (Breakthrough Sensitivity baseline)
R_NORMAL_ONLY_TOTAL = 69             # Total DPS if every hit were against normal monsters (Breakthrough Sensitivity baseline)

# Corsair has no BuffDuration(s)>0 skill rows at all (confirmed: no recast-able timed buffs exist
# in this class's kit — Roll of the Dice's dice component is modeled as an always-active flat
# approximation instead, see ATTACK_BUFF_ROW_KEYS/PASSIVE_DELTA_SLOT). Kept as an explicit empty
# list (not omitted) for architectural consistency with the other 11 classes' identical
# buff-casting-startup-delay wiring — currently always 0 for Corsair as a result.
BUFF_ROW_KEYS = []

# NOTE: Corsair's wiki overview page is EVEN WORSE than Buccaneer's — no Req.Level column, AND no
# Mastery page at all (confirmed 404/redlink). Every unlock level below is a FLAGGED ASSUMPTION
# inferred purely from the skill's own position in the overview list (which follows job-tier
# order) and cross-checked against Buccaneer's own analogous-role unlock levels where a role
# mapping exists. A human should revisit these if real data ever surfaces.
UNLOCK_LEVEL = {
    "EIGHT_LEGS_EASTON": 100,
    "SWIFT_FIRE": 35,
    "SCURVY_SUMMONS": 40,
    "ALL_ABOARD": 45,
    "BLACKBOOT_BILL": 63,
    "SIEGE_BOMBER": 66,
    "BRAIN_SCRAMBLER": 100,
    "NAUTILUS_STRIKE": 103,
    "NAUTILUS_FINAL_ATTACK": 113,
    "RAPID_FIRE": 107,
    "BROADSIDE_BURST": 110,
    "BROADSIDE_SUSTAINED": 110,
    "MAJESTIC_PRESENCE": 125,
    "MAPLE_HERO_HELPER": 100,
    "AHOY_MATEYS_HELPER": 120,
    "ROLL_OF_THE_DICE_DICE": 66,
    "JOLLY_ROGER_FD": 115,
    "SHADOW_HEART": 15,
    "QUICK_MOTION": 10,
    "AGILE_GUNS": 33,
    "GUN_MASTERY": 43,
    "PHYSICAL_TRAINING": 38,
    "INFINITY_BLAST_ATK": 40,
    "FULLMETAL_JACKET_CD": 72,
    "CROSS_CUT_BLAST_FD": 75,
    "QUICKDRAW_BAD": 117,
}


def unlock_expr(key):
    level = UNLOCK_LEVEL.get(key)
    return "=TRUE" if level is None else f"={IB('level')}>={level}"


# Maple Hero (Corsair) — UNLIKE Buccaneer's own truncated entry, Corsair's level-1 anchor values
# ARE real/confirmed from the overview page: "Siege Bomber 20%, Blackboot Bill 40%, Swift Fire
# 80%". Only the growth-curve SHAPE is a FLAGGED ASSUMPTION (factorIndex 23, the universal Maple
# Hero convention confirmed on every other class — no individual Maple_Hero_(Corsair) page exists
# to verify the real curve).
MAPLE_HERO_RATIOS = {
    "SIEGE_BOMBER": 20 / 20,
    "BLACKBOOT_BILL": 40 / 20,
    "SWIFT_FIRE": 80 / 20,
}

# Ahoy Mateys — a SEPARATE, independent helper skill (not "Maple Hero"): "Increases Final Damage
# of Dual Pistol Crew by 250% and Sharpshooter Crew by 100%." Real/confirmed level-1 values, own
# FLAGGED-ASSUMPTION growth curve (factorIndex 22, generic buff convention — not tied to Maple
# Hero's own factorIndex 23 special-case since this is a genuinely different skill).
AHOY_MATEYS_RATIOS = {
    "SCURVY_SUMMONS": 250 / 250,
    "ALL_ABOARD": 100 / 250,
}

# Every row that can carry a shared-ratio-feeder helper term in its own K-column formula — a
# small generalization over Buccaneer's own single-helper (Maple Hero only) pattern, since
# Corsair has TWO independent helpers (Maple Hero + Ahoy Mateys) that can both apply to the same
# target row (Scurvy Summons/All Aboard get Ahoy Mateys only; Siege Bomber/Blackboot Bill/Swift
# Fire get Maple Hero only — no row currently needs both, but the mechanism supports it).
HELPER_SPECS = [
    ("MAPLE_HERO_HELPER", MAPLE_HERO_RATIOS),
    ("AHOY_MATEYS_HELPER", AHOY_MATEYS_RATIOS),
]


# (key, name, jobstep, cooldown, costsAction, actionsPerCast, hits, icd, window, chance, rolls,
#  baseDamage, factorIndex, scales, skillMasteryBonusPct, masteryBossDmgPct, masteryNormalDmgPct,
#  normalMonsterTargets, buffTarget, buffDuration, mapleBase, mapleFactor, note)
SKILL_ROWS = [
    ("EIGHT_LEGS_EASTON", "Eight-Legs Easton", 4, "", False, 1,
     f'=IF({IB("level")}>=136,6,5)', 0, 0, 100, 1,
     2900, 21, True,
     f"={level_gated_sum_raw(IB('level'), {102: 10, 106: 1, 116: 1, 120: 1, 128: 1, 132: 1})}",
     level_gated_sum(IB("level"), {111: 10, 124: 10}), 0,
     f'=6+{IB("basic_attack_target_increase")}', "", 0, "", "",
     "4th-job basic-attack effect (supersedes Double Shot/Rapid Blast/Blunderbuster, confirmed "
     "identical wiki wording — 290% damage to 6 target(s) in front 5 time(s) — to every other "
     "class's own 4th-job basic attack). factorIndex 21, baseDamage 2900 tenths%. HitsPerCast=5, "
     "bumping to 6 once the ASSUMED Mastery Lv.136 tier unlocks (mapped from Buccaneer's own "
     "Hook Bomber - Strike slot — Corsair has no Mastery page at all to confirm this "
     "independently). Real Damage mastery chain (102/106/116/120/128/132, DELTAS) and Boss "
     "Monster Damage chain (111/124, +10% each) mapped directly from Buccaneer's own Hook "
     "Bomber chain — this is the same universal 4th-job-basic-attack mastery pattern confirmed "
     "across every class in this project, so this specific mapping is high-confidence despite "
     "the overall lack of Corsair mastery data."),
    ("SWIFT_FIRE", "Swift Fire", 2, 18, True, 1, 3, 0, 0, 100, 1,
     1800, 12, True,
     level_gated_sum(IB("level"), {39: 50}), 0, 0, 8, "", 0, 200, 23,
     "FLAGGED ASSUMPTION (no individual wiki page exists, no cooldown stated — 18s assumed by "
     "convention matching similarly-shaped 2nd-job burst skills elsewhere): 'Fires three bullets "
     "consecutively at the target to deal 180% damage each.' factorIndex 12, baseDamage 1800 "
     "tenths%. PATCHED: single-target -> up to 8 enemies ahead (targets field reflects this). "
     "Mastery mapped from Buccaneer's own Sea Serpent Burst - Damage @39 (+50%) slot — no exact "
     "1:1 analog exists since Corsair has no mastery data at all, but both are the class's own "
     "2nd-job attack-proc-shaped skill, so this role-mapping is a reasonable assumption. Maple "
     "Hero target — see MAPLE_HERO_RATIOS (biggest share, 4x Siege Bomber's own)."),
    ("SCURVY_SUMMONS", "Scurvy Summons", 2, 20, True, 1, 2, 1.5, 20, 100, 1,
     950, 12, True,
     0, 0, 0, 3, "", 0, "", "",
     "FLAGGED ASSUMPTION (no individual wiki page exists, cooldown assumed = its own 20s "
     "duration, recast-on-expiry, same convention as every other summon/turret skill in this "
     "project): 'Summons the Dual Pistol Crew of the Nautilus for 20 sec. The Dual Pistol Crew "
     "deals 95% damage to the target 2 time(s) every 3 sec.' factorIndex 12, baseDamage 950 "
     "tenths%. PATCHED: tick interval 3s->1.5s (baked into ICD(s)), crew now hits up to 3 nearby "
     "targets instead of single-target (targets field reflects this). Standard "
     "ActiveWindow/ICD tick machinery (EffectiveHits = 2*(20/1.5) per cast) — no bespoke "
     "mechanics needed, unlike Buccaneer's own resource-economy skills. No clean Buccaneer "
     "mastery-slot analog exists for this specific crew-summon mechanic — left unmodeled "
     "(SkillMasteryBonus%=0) rather than forcing a poor mapping. Ahoy Mateys target — see "
     "AHOY_MATEYS_RATIOS (biggest share, ratio 1.0)."),
    ("ALL_ABOARD", "All Aboard", 2, 20, False, 1, 3, 2, 20, 100, 1,
     1100, 12, True,
     0, 0, 0, 8, "", 0, "", "",
     "FLAGGED ASSUMPTION (no individual wiki page exists): 'Summons the Sharpshooter Crew upon "
     "using Scurvy Summons. The Sharpshooter Crew fires bullets every 4 sec to deal 190% damage "
     "to 3 target(s) near the main target 3 time(s).' Triggered BY Scurvy Summons — shares its "
     "own Cooldown(s)/duration values directly (CostsActionSlot=False so it doesn't double-count "
     "the action economy), same 'rides the parent skill's cast timing' pattern as Buccaneer's "
     "own Sea Serpent's Rage riding Octopunch. factorIndex 12, baseDamage 1100 tenths%. PATCHED: "
     "tick interval 4s->2s (baked into ICD(s)), damage 190%->110%, targets 3->8. No clean "
     "Buccaneer mastery-slot analog — left unmodeled. Ahoy Mateys target — see "
     "AHOY_MATEYS_RATIOS (0.4x Scurvy Summons' own share)."),
    ("BLACKBOOT_BILL", "Blackboot Bill", 3, 20, True, 1, 4, 0, 0, 100, 1,
     1700, 12, True,
     level_gated_sum(IB("level"), {73: 80}), 0, 0, 9, "", 0, 400, 23,
     "FLAGGED ASSUMPTION (no individual wiki page exists, no cooldown stated — 20s assumed by "
     "convention matching Buccaneer's own similarly-shaped Corkscrew Blow): 'Fires a giant "
     "bullet to deal 170% damage to 6 target(s) in front 4 time(s) and stun them for 2 sec' "
     "(stun not modeled). factorIndex 12, baseDamage 1700 tenths%. PATCHED: targets 6->9. "
     "Mastery mapped from Buccaneer's own Corkscrew Blow - Damage @73 (+80%) slot — both are "
     "the class's own 3rd-job unique burst skill. Maple Hero target — see MAPLE_HERO_RATIOS "
     "(2x Siege Bomber's own share)."),
    ("SIEGE_BOMBER", "Siege Bomber", 3, 30, True, 1, 1, 1.5, 30, 100, 1,
     1900, 12, True,
     0, 0, 0, 6, "", 0, 100, 23,
     "FLAGGED ASSUMPTION (no individual wiki page exists, cooldown assumed = its own 30s "
     "duration, recast-on-expiry): 'Installs a fixed cannon for 30 sec to deal 290% damage to 4 "
     "target(s) near the main target every 2.5 sec.' factorIndex 12, baseDamage 1900 tenths%. "
     "PATCHED: tick interval 2.5s->1.5s (baked into ICD(s)), damage 290%->190%, targets 4->6. "
     "Standard ActiveWindow/ICD turret machinery, same as Bowmaster's own Arrow Platter. No "
     "clean Buccaneer mastery-slot analog — left unmodeled. Maple Hero target — see "
     "MAPLE_HERO_RATIOS (smallest share, ratio 1.0)."),
    ("BRAIN_SCRAMBLER", "Brain Scrambler", 4, 15, True, 1, 2, 0, 0, 100, 1,
     29000, 12, True,
     level_gated_sum(IB("level"), {108: 50}), 0, 0, 1, "", 0, "", "",
     "FLAGGED ASSUMPTION (no individual wiki page exists, no cooldown stated — 15s assumed by "
     "convention matching Buccaneer's own similarly-shaped 4th-job burst skill Octopunch): "
     "'Hits the target's head to deal 2900% damage 2 time(s).' factorIndex 12, baseDamage 29000 "
     "tenths%, single target. Mastery mapped from Buccaneer's own Octopunch - Damage @108 "
     "(+50%) slot — both are the class's own 4th-job single-target burst skill. Also feeds "
     "Majestic Presence's own combined trigger rate — see MAJESTIC_PRESENCE's own Note."),
    ("NAUTILUS_STRIKE", "Nautilus Strike", 4, 45, True, 1, 5, 0, 0, 100, 1,
     19500, 12, True,
     level_gated_sum(IB("level"), {126: 50}), 0, 0, 15, "", 0, "", "",
     "CONFIRMED SHARED VERBATIM WITH BUCCANEER (byte-identical wiki description on both "
     "classes' overview pages: 'Orders the Nautilus to attack to deal 1950% damage to 15 nearby "
     "target(s) 5 time(s).') — reuses Buccaneer's exact FLAGGED-ASSUMPTION (19500, 12) tuple "
     "directly, not re-derived. Cooldown (45s) also reused from Buccaneer's own assumption. "
     "Mastery mapped from Buccaneer's own Nautilus Strike - Damage @126 (+50%) slot — since "
     "this is the SAME shared skill, this mapping is higher-confidence than most other "
     "role-mapped masteries in this workbook."),
    ("NAUTILUS_FINAL_ATTACK", "Nautilus Strike - Final Attack", 4, 1, False, 1, 1, 0, 0, 30, 1,
     8500, 21, True,
     0, 0, 0, 1, "", 0, "", "",
     "CONFIRMED SHARED VERBATIM WITH BUCCANEER — same Mastery Lv.113 proc mechanic, same patch "
     "note applies identically to both classes: '[Nautilus Strike in Slot] When attacking, "
     "deals 850% additional damage' — PATCHED: trigger chance 15%->30%, 'cooldown set to 1s' "
     "(both baked in directly: ProcChance%=30, Cooldown(s)=1). Reuses Buccaneer's exact row "
     "shape/tuple directly. Triggers off basic attacks generically (CostsActionSlot=False), "
     "factorIndex 21, baseDamage 8500 tenths%."),
    ("RAPID_FIRE", "Rapid Fire", 4, 17, True, 1, 7, 0, 0, 100, 1,
     18000, 12, True,
     0, 0, 0, 9, "", 0, "", "",
     "FLAGGED ASSUMPTION (no individual wiki page exists, but cooldown IS explicitly stated in "
     "the patch notes — see below): 'Fires bullets at a very high speed 7 time(s) to deal 1350% "
     "damage each.' factorIndex 12, baseDamage 18000 tenths% (already reflects the patch). "
     "PATCHED: single-target -> up to 9 enemies (targets field), damage 1350%->1800% (curve "
     "rescaled 1800/1350=1.333x before applying), cooldown 21s->17s (Cooldown(s) already "
     "reflects the patched value directly, unlike every other assumed cooldown in this "
     "workbook — this one has an actual documented number). No clean Buccaneer mastery-slot "
     "analog — left unmodeled. Also feeds Majestic Presence's own combined trigger rate."),
    ("BROADSIDE_BURST", "Broadside (initial burst)", 4, 30, True, 1, 2, 0, 0, 100, 1,
     50000, 12, True,
     level_gated_sum(IB("level"), {122: 100}), 0, 0, 10, "", 0, "", "",
     "FLAGGED ASSUMPTION (no individual wiki page exists, cooldown assumed = its own 30s "
     "sustained-phase duration, recast-on-expiry): 'Summons the Nautilus's Battleship. The "
     "Battleship arrives behind 3 sec later and deals 3800% damage to 5 nearby target(s) 2 "
     "time(s).' (the 3s arrival delay is not modeled — folded into a same-cast instant hit, "
     "same simplification tier as every other 'delayed burst' skill in this project). "
     "factorIndex 12, baseDamage 50000 tenths% (already reflects the patch). PATCHED: damage "
     "3800%->5000%, targets 5->10. This row pays the real Cooldown(s)/action-slot cost; see "
     "BROADSIDE_SUSTAINED for the follow-up turret phase, which rides this row's own cast "
     "timing. Mastery mapped from Buccaneer's own Sea Serpent's Rage - Damage @122 (+100%) "
     "slot — both are the class's own 4th-job summon-triggered burst effect."),
    ("BROADSIDE_SUSTAINED", "Broadside (sustained turret)", 4, 30, False, 1, 1, 2, 30, 100, 1,
     33000, 12, True,
     0, 0, 0, 5, "", 0, "", "",
     "FLAGGED ASSUMPTION (no individual wiki page exists, target count assumed = the burst "
     "phase's own PRE-patch value of 5, since the Aug 13 patch notes only cover the initial "
     "burst numbers, not this sustained phase — its patch status is genuinely unstated, not "
     "necessarily unchanged): 'Afterward it stays for 30 sec and deals 3300% damage to "
     "target(s) in front of the Battleship every 2 sec.' factorIndex 12, baseDamage 33000 "
     "tenths%. Shares BROADSIDE_BURST's own Cooldown(s) value (same cast timing, "
     "CostsActionSlot=False so it doesn't double-count the action economy) — same 'rides the "
     "parent's cast timing' pattern as ALL_ABOARD riding SCURVY_SUMMONS."),
    ("MAJESTIC_PRESENCE", "Majestic Presence", 4, "", False, 1, 1, 0, 0, 25, 1,
     18000, 12, True,
     0, 0, 0, 6, "", 0, "", "",
     "FLAGGED ASSUMPTION (no individual wiki page exists): 'When attacking with Basic Attacks "
     "Brain Scrambler or Rapid Fire deals 1800% additional damage with a 25% chance.' PATCHED: "
     "single-target -> up to 6 enemies near target (targets field). factorIndex 12, baseDamage "
     "18000 tenths%. Procs off THREE independent sources (Basic Attack + Brain Scrambler + "
     "Rapid Fire) — has no Cooldown(s) of its own at all (CostsActionSlot=False); its own "
     "combined trigger rate is built directly in build_calc_sheet/build_stat_block as "
     "Summary!$B$R_BAPS (basic attack rate) + Brain Scrambler's own HitRate(perSec) + Rapid "
     "Fire's own HitRate(perSec), extending Marksman's own Bolt Surplus dual-trigger pattern to "
     "three sources instead of two. No clean Buccaneer mastery-slot analog — left unmodeled."),
    ("MAPLE_HERO_HELPER", "Maple Hero (helper)", 4, "", False, 1, 1, 0, 0, 100, 1,
     200, 23, True,
     0, 0, 0, 0, "", 0, "", "",
     "Shared ratio-feeder row (see MAPLE_HERO_RATIOS) for Siege Bomber/Blackboot Bill/Swift "
     "Fire's own Final Damage chains — mirrors every other class's own Maple Hero mechanism. "
     "UNLIKE Buccaneer's own truncated entry, Corsair's level-1 anchor values ARE real/"
     "confirmed: 'Siege Bomber 20%, Blackboot Bill 40%, Swift Fire 80%.' FLAGGED ASSUMPTION: "
     "factorIndex 23 (the universal Maple Hero growth-curve convention confirmed on every "
     "other class), baseDamage 200 tenths% anchored to the confirmed level-1 value (20%). No "
     "individual Maple_Hero_(Corsair) page exists to verify the real growth curve. No "
     "independent DPS row of its own (Calc columns J-N blank/0, only D/E/F computed, read "
     "directly by each target row's own K-column formula)."),
    ("AHOY_MATEYS_HELPER", "Ahoy Mateys (helper)", 4, "", False, 1, 1, 0, 0, 100, 1,
     2500, 22, True,
     0, 0, 0, 0, "", 0, "", "",
     "Shared ratio-feeder row (see AHOY_MATEYS_RATIOS) for Scurvy Summons/All Aboard's own "
     "Final Damage chains — a SEPARATE, independent helper from Maple Hero (Ahoy Mateys is its "
     "own skill, not literally 'Maple Hero'), same 'no independent DPS row' mechanism. "
     "FLAGGED ASSUMPTION: factorIndex 22 (generic buff-growth convention, not tied to Maple "
     "Hero's own special factorIndex 23 since this is a genuinely different skill), baseDamage "
     "2500 tenths% anchored to the confirmed level-1 value (250%, Scurvy Summons' own share). "
     "No individual wiki page exists for this skill at all — even its unlock level is a bare "
     "position-in-list assumption."),
    ("ROLL_OF_THE_DICE_DICE", "Roll of the Dice (dice component)", 3, "", False, 1, 1, 0, 0, 100, 1,
     25, 0, False,
     0, 0, 0, 0, "ATTACK", 0, "", "",
     "CONFIRMED SHARED VERBATIM WITH BUCCANEER (byte-identical wiki description, discovered "
     "during this build — not called out by the original research report): 'Increases Attack "
     "by 20%. Rolls a six-sided die every 7 sec to increase Attack by 0-5% in proportion to the "
     "number on the die for 5 sec. A number that has appeared once does not appear again for "
     "30 sec.' Reuses Buccaneer's exact treatment: this row models ONLY the random dice "
     "component, approximated at its average roll (2.5%, the midpoint of 0-5%) treated as an "
     "always-active flat bonus once unlocked. The flat, unconditional '+20% Attack' base effect "
     "is Magic-Critical-pattern (assumed already reflected in your own Inputs!ATTACK_PCT, see "
     "PASSIVE_DELTA_SLOT). factorIndex 0 (non-scaling placeholder), baseDamage 25 tenths%."),
    ("JOLLY_ROGER_FD", "Jolly Roger", 4, "", False, 1, 1, 0, 0, 100, 1,
     150, 22, True,
     0, 0, 0, 0, "FINAL_DAMAGE", 0, "", "",
     "FLAGGED ASSUMPTION (no individual wiki page exists, no cooldown stated — modeled as "
     "always-active steady-state once unlocked, same tier as Buccaneer's own Crossbones/Time "
     "Leap): 'Increases Final Damage by 18% for 18 sec but decreases Evasion by 5' (Evasion not "
     "modeled). PATCHED: Final Damage 18%->15% (a nerf — baseDamage already reflects this). "
     "factorIndex 22, baseDamage 150 tenths%. Corsair's ONLY live (non-Magic-Critical) Final "
     "Damage source — feeds R_FD_BONUS directly."),
    ("SHADOW_HEART", "Shadow Heart", 1, "", False, 1, 1, 0, 0, 100, 1,
     50, 22, True,
     0, 0, 0, 0, "CRIT_RATE", 0, "", "",
     "Magic Critical pattern — already baked into Inputs!CRIT_RATE%; feeds the 1st-Job Skill "
     "Level Bonus delta. FLAGGED ASSUMPTION (no individual wiki page exists, though byte-"
     "identical wording to Buccaneer's own Shadow Heart): 'Increases Critical Rate by 5%.' "
     "factorIndex 22, baseDamage 50 tenths%."),
    ("QUICK_MOTION", "Quick Motion", 1, "", False, 1, 1, 0, 0, 100, 1,
     60, 22, True,
     0, 0, 0, 0, "ATTACK_SPEED", 0, "", "",
     "Magic Critical pattern — already baked into Inputs!ATTACK_SPEED%; feeds the 1st-Job "
     "Skill Level Bonus delta. FLAGGED ASSUMPTION (no individual wiki page exists, though "
     "byte-identical wording to Buccaneer's own Quick Motion): 'Increases Attack Speed by 6% "
     "and Speed by 8%' (Speed not modeled). Like Buccaneer, Corsair has NO Nimble-Feet-style "
     "live AS buff — Quick Motion is a flat passive. factorIndex 22, baseDamage 60 tenths%."),
    ("AGILE_GUNS", "Agile Guns", 2, "", False, 1, 1, 0, 0, 100, 1,
     50, 22, True,
     level_gated_sum(IB("level"), {44: 7}), 0, 0, 0, "ATTACK_SPEED", 0, "", "",
     "Magic Critical pattern — already baked into Inputs!ATTACK_SPEED%; feeds the 2nd-Job "
     "Skill Level Bonus delta. FLAGGED ASSUMPTION (no individual wiki page exists): "
     "'Increases Attack Speed by 5%.' factorIndex 22, baseDamage 50 tenths%. Mastery mapped "
     "from Buccaneer's own Agile Knuckles - Speed @44 (+7) slot — both are the class's own AS "
     "passive in the same kit-slot role."),
    ("GUN_MASTERY", "Gun Mastery", 2, "", False, 1, 1, 0, 0, 100, 1,
     150, 22, True,
     0, 0, 0, 0, "MIN_DAMAGE", 0, "", "",
     "Magic Critical pattern — already baked into Inputs!MIN_DAMAGE%; feeds the 2nd-Job Skill "
     "Level Bonus delta. FLAGGED ASSUMPTION (no individual wiki page exists): 'Increases Min "
     "Damage Multiplier by 15%.' factorIndex 22, baseDamage 150 tenths% — matches Buccaneer's "
     "own Knuckle Mastery exactly (same kit-slot role, no mastery bonus in either class)."),
    ("PHYSICAL_TRAINING", "Physical Training", 2, "", False, 1, 1, 0, 0, 100, 1,
     100, 22, True,
     0, 0, 0, 0, "BASIC_ATTACK_DAMAGE", 0, "", "",
     "Magic Critical pattern — already baked into Inputs!BASIC_ATTACK_DAMAGE%; feeds the "
     "2nd-Job Skill Level Bonus delta. FLAGGED ASSUMPTION (no individual wiki page exists, "
     "though byte-identical wording to every other class's own Physical Training): 'Increases "
     "Basic Attack Damage by 10%.' factorIndex 22, baseDamage 100 tenths%."),
    ("INFINITY_BLAST_ATK", "Infinity Blast", 2, "", False, 1, 1, 0, 0, 100, 1,
     120, 22, True,
     0, 0, 0, 0, "ATTACK", 0, "", "",
     "Magic Critical pattern — already baked into Inputs!ATTACK_PCT (folds into the "
     "attack_mult delta bucket, same slot as Buccaneer's own Dark Clarity). FLAGGED ASSUMPTION "
     "(no individual wiki page exists): 'Increases Attack by 10%.' PATCHED: 10%->12% "
     "(baseDamage already reflects this). factorIndex 22, baseDamage 120 tenths%."),
    ("FULLMETAL_JACKET_CD", "Fullmetal Jacket", 3, "", False, 1, 1, 0, 0, 100, 1,
     100, 22, True,
     0, 0, 0, 0, "CRIT_DAMAGE", 0, "", "",
     "Magic Critical pattern — already baked into Inputs!CRIT_DAMAGE%; feeds the 3rd-Job "
     "Skill Level Bonus delta. FLAGGED ASSUMPTION (no individual wiki page exists): "
     "'Increases Critical Damage by 10%.' factorIndex 22, baseDamage 100 tenths%."),
    ("CROSS_CUT_BLAST_FD", "Cross Cut Blast", 3, "", False, 1, 1, 0, 0, 100, 1,
     120, 22, True,
     0, 0, 0, 0, "FINAL_DAMAGE", 0, "", "",
     "Magic Critical pattern — already baked into Inputs!FINAL_DAMAGE%; feeds the 3rd-Job "
     "Skill Level Bonus delta. FLAGGED ASSUMPTION (no individual wiki page exists): "
     "'Increases Final Damage by 10%.' PATCHED: 10%->12% (baseDamage already reflects this). "
     "factorIndex 22, baseDamage 120 tenths%."),
    ("QUICKDRAW_BAD", "Quickdraw", 4, "", False, 1, 1, 0, 0, 100, 1,
     250, 22, True,
     0, 0, 0, 0, "BASIC_ATTACK_DAMAGE", 0, "", "",
     "Magic Critical pattern — already baked into Inputs!BASIC_ATTACK_DAMAGE%; feeds the "
     "4th-Job Skill Level Bonus delta. FLAGGED ASSUMPTION (no individual wiki page exists): "
     "only the flat, unconditional 'Increases Basic Attack Damage by 25%' component is "
     "modeled here. factorIndex 22, baseDamage 250 tenths%. NOT modeled (out of scope): its "
     "own 'every 3rd Eight-Legs Easton cast doubles the damage and reduces Brain Scrambler/"
     "Rapid Fire cooldown by 1.5s' proc — no mechanic exists in this project for one skill's "
     "cast count to modify another's cooldown, and stacking that on top of an already-assumed "
     "kit was judged out of scope for this session."),
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
    "SWIFT_FIRE", "SCURVY_SUMMONS", "ALL_ABOARD", "BLACKBOOT_BILL", "SIEGE_BOMBER",
    "BRAIN_SCRAMBLER", "NAUTILUS_STRIKE", "NAUTILUS_FINAL_ATTACK", "RAPID_FIRE",
    "BROADSIDE_BURST", "BROADSIDE_SUSTAINED", "MAJESTIC_PRESENCE",
]
ATTACK_BUFF_ROW_KEYS = ["ROLL_OF_THE_DICE_DICE"]
PASSIVE_MULT_ROW_KEYS = [
    "SHADOW_HEART", "QUICK_MOTION", "AGILE_GUNS", "GUN_MASTERY", "PHYSICAL_TRAINING",
    "INFINITY_BLAST_ATK", "FULLMETAL_JACKET_CD", "CROSS_CUT_BLAST_FD", "QUICKDRAW_BAD",
]
HELPER_ROW_KEYS = ["MAPLE_HERO_HELPER", "AHOY_MATEYS_HELPER"]
MAPLE_HERO_ROW_KEYS = ["MAPLE_HERO_HELPER"]
DAMAGE_DEALING_KEYS = ["EIGHT_LEGS_EASTON"] + DAMAGE_ROW_KEYS
# Corsair has no Buccaneer-style "rides basic attack's own cast rate" skills — All Aboard and
# Broadside (sustained) instead ride their OWN parent skill's Cooldown(s)/duration value
# directly (a literal copy of the number, CostsActionSlot=False), which the standard generic
# ActiveWindow/ICD/Cooldown machinery already handles with no special casing needed. Only
# Majestic Presence needs bespoke O-column treatment — it procs off THREE independent sources
# (Basic Attack + Brain Scrambler + Rapid Fire) and has no Cooldown(s) of its own at all.
RIDES_BASIC_ATTACK_KEYS = []
MULTI_TRIGGER_KEYS = ["MAJESTIC_PRESENCE"]
MULTI_TRIGGER_SOURCES = {
    "MAJESTIC_PRESENCE": ["BRAIN_SCRAMBLER", "RAPID_FIRE"],  # + Summary!$B$R_BAPS (basic attack) added separately
}

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
            # Duration actually available for this row's casts in fixed-duration mode — raw fight
            # duration for buffs, or reduced by Summary!R_STARTUP_TIME for non-buff rows. Corsair
            # has no buff rows today (BUFF_ROW_KEYS is empty), so this is currently always equal
            # to the raw fight duration, but kept for consistency with the other 11 classes.
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
            available_duration_r = None

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
            for col in (7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19):
                ws.cell(row=r, column=col, value=("1" if col == 9 else ""))
            continue

        if key == "EIGHT_LEGS_EASTON":
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

        if key in (["EIGHT_LEGS_EASTON"] + DAMAGE_ROW_KEYS):
            ws.cell(row=r, column=10, value=f'={IB("attack")}*(F{r}/100)')
            helper_terms = ''
            for helper_key, ratios in HELPER_SPECS:
                ratio = ratios.get(key)
                if not ratio:
                    continue
                h_row = ROW[helper_key]
                h_gated = f'IF(C{h_row}=TRUE,F{h_row},0)'
                helper_terms += f'*(1+{ratio}*{h_gated}/100)'
            ws.cell(row=r, column=11, value=(
                f'=J{r}*(1+{IB("stat_damage")}/100)*(1+{IB("damage")}/100)'
                f'*(1+{IB("damage_amp")}/100)'
                f'*(5000/(6000+{IB("monster_defense")}*(1-{IB("def_pen")}/100)))'
                f'*(1+({IB("final_damage")}+{final_damage_extra_ref})/100)'
                f'{helper_terms}'
                f'*(1+(IF({S("Key", r)}="EIGHT_LEGS_EASTON",{IB("basic_attack_damage")},{IB("skill_damage")}))/100)'
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

        if key == "EIGHT_LEGS_EASTON":
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
        elif key in MULTI_TRIGGER_KEYS:
            source_rate_terms = []
            for src_key in MULTI_TRIGGER_SOURCES[key]:
                src_row = ROW[src_key]
                src_eff_cd = effective_cooldown_expr(
                    IB("monster_type"), S("Cooldown(s)", src_row), IB("skill_cooldown_decrease"),
                    S("CostsActionSlot", src_row),
                )
                if src_key in BUFF_ROW_KEYS:
                    src_available_duration = IB("fight_duration")
                else:
                    src_available_duration = f'MAX(0,{IB("fight_duration")}-Summary!$B${R_STARTUP_TIME})'
                # Target-count-INDEPENDENT rate — deliberately NOT Calc!S (HitRate(perSec)),
                # which bakes in that row's own target_multiplier and would over-count Rapid
                # Fire's own 9-target multiplier in normal/breakthrough mode (a real bug caught
                # by this workbook's own categorical sweep before shipping).
                source_rate_terms.append(rate_or_exact_hits_expr(
                    fixed_duration_active_main, f"R{src_row}", S("HitsPerCast", src_row),
                    S("ICD(s)", src_row), S("ActiveWindow(s)", src_row), src_eff_cd,
                    src_available_duration, IB("fight_duration"), f"G{src_row}*Q{src_row}",
                ))
            combined_rate = f"(Summary!$B${R_BAPS}+{'+'.join(source_rate_terms)})"
            prefix = f"H{r}*N{r}*{combined_rate}"
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
        value=f'=({IB("flat_dex")}*(1+{IB("dex_pct")}/100))*0.01+{IB("str")}*0.0025'
    )

    ws.cell(row=D_BASIC_INPUT_LEVEL, column=1, value="Basic Attack (Eight-Legs Easton) Input Level (4th job formula)")
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
    ws.cell(row=D_SKILL_COEFFICIENT, column=1, value="SKILL_COEFFICIENT — Eight-Legs Easton base coefficient % (before bonuses)")
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
    r_jr = ROW["JOLLY_ROGER_FD"]

    # Roll of the Dice's dice component: no cooldown known, modeled always-active once unlocked
    # (CONFIRMED SHARED VERBATIM WITH BUCCANEER — same skill, same treatment).
    roll_of_dice_avg = f'((Calc!C{r_rd}=TRUE)*Calc!F{r_rd})'
    # Jolly Roger: no cooldown known, modeled always-active once unlocked — Corsair's ONLY live
    # (non-Magic-Critical) Final Damage source, much simpler than Buccaneer's own 4-source bucket
    # since Corsair has no Assault-Mode-style resource economy.
    jolly_roger_avg = f'((Calc!C{r_jr}=TRUE)*Calc!F{r_jr})'

    ws.cell(row=R_AVGBUFF, column=1, value="Attack%% Bucket Multiplier (Roll of the Dice's dice component only)")
    ws.cell(row=R_AVGBUFF, column=2, value=f'=1+({roll_of_dice_avg})/100')

    ws.cell(row=R_CRIT_RATE_BONUS, column=1, value="Global Crit Rate Bonus % (unused — no live Crit-Rate-buff source exists)")
    ws.cell(row=R_CRIT_RATE_BONUS, column=2, value=0)

    ws.cell(row=R_MONSTER_DMG_BONUS, column=1, value="Global Monster Damage-Taken Bonus % (unused — no live source exists in this kit)")
    ws.cell(row=R_MONSTER_DMG_BONUS, column=2, value=0)

    ws.cell(row=R_AS_BONUS, column=1, value="Attack Speed Buff Bonus % (unused — Corsair has no Nimble-Feet-style live AS buff, same as Buccaneer)")
    ws.cell(row=R_AS_BONUS, column=2, value=0)

    ws.cell(row=R_APS, column=1, value="Actions Per Second")
    ws.cell(row=R_APS, column=2, value=(
        f'=1+MIN(150,150*(1-(1-{IB("attack_speed")}/150)*(1-B{R_AS_BONUS}/150)))/100'
    ))

    ws.cell(row=R_CASTRATE, column=1, value="Skill + Buff Cast Rate (subtracted from Eight-Legs Easton, 1/s)")
    ws.cell(row=R_CASTRATE, column=2, value=(
        f'=IF({fda_main},'
        f'SUMPRODUCT((Skills!{SC["CostsActionSlot"]}2:{SC["CostsActionSlot"]}{LAST_ROW}=TRUE)*'
        f'(Calc!C2:C{LAST_ROW}=TRUE)*Calc!R2:R{LAST_ROW}*Skills!{SC["ActionsPerCast"]}2:{SC["ActionsPerCast"]}{LAST_ROW})/{IB("fight_duration")},'
        f'SUMPRODUCT((Skills!{SC["CostsActionSlot"]}2:{SC["CostsActionSlot"]}{LAST_ROW}=TRUE)*'
        f'(Calc!C2:C{LAST_ROW}=TRUE)*Calc!Q2:Q{LAST_ROW}*Skills!{SC["ActionsPerCast"]}2:{SC["ActionsPerCast"]}{LAST_ROW}))'
    ))

    ws.cell(row=R_BAPS, column=1, value="Eight-Legs Easton (Basic Attack) Casts Per Second")
    ws.cell(row=R_BAPS, column=2, value=f'=MAX(0,B{R_APS}-B{R_CASTRATE})')

    ws.cell(row=R_CRIT_DAMAGE_BONUS, column=1, value="Global Critical Damage Bonus % (unused — no live Crit-Damage-buff source exists)")
    ws.cell(row=R_CRIT_DAMAGE_BONUS, column=2, value=0)

    ws.cell(row=R_FD_BONUS, column=1, value="Global Final Damage Bonus % (Jolly Roger only)")
    ws.cell(row=R_FD_BONUS, column=2, value=f'={jolly_roger_avg}')

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

    ws.cell(row=R_EIGHT_LEGS_EASTON_DPS, column=1, value="Eight-Legs Easton (Basic Attack) DPS")
    ws.cell(row=R_EIGHT_LEGS_EASTON_DPS, column=2, value=f"=Calc!O{ROW['EIGHT_LEGS_EASTON']}")

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
# (see build_sensitivity_sheet).
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
# delta folds into. "attack_mult" has no literal Inputs field — Dark Clarity's own flat Attack%
# component shares it (same slot as Shadower's own Channel Karma/Bowmaster's own Soul Arrow: Bow).
PASSIVE_DELTA_SLOT = {
    "SHADOW_HEART": "crit_rate",
    "QUICK_MOTION": "attack_speed",
    "AGILE_GUNS": "attack_speed",
    "INFINITY_BLAST_ATK": "attack_mult",
    "GUN_MASTERY": "min_damage",
    "PHYSICAL_TRAINING": "basic_attack_damage",
    "FULLMETAL_JACKET_CD": "crit_damage",
    "CROSS_CUT_BLAST_FD": "final_damage",
    "QUICKDRAW_BAD": "basic_attack_damage",
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

    # Flat ATTACK is assumed to already include the character's current DEX/STR-derived attack
    # (1 total DEX = 1 flat Attack, 1 STR = 0.25 flat Attack, added into the pool before ATTACK%
    # applies) — same "already baked into Inputs, only the Sensitivity marginal delta matters"
    # pattern used elsewhere in this block. Identically 0 for every block except the ones sweeping
    # flat_dex/dex_pct/str.
    mainstat_attack_delta = (
        f'((({ib("flat_dex")}*(1+{ib("dex_pct")}/100))-({IB("flat_dex")}*(1+{IB("dex_pct")}/100)))'
        f'+0.25*({ib("str")}-{IB("str")}))'
    )

    r_rd = ROW["ROLL_OF_THE_DICE_DICE"]
    r_jr = ROW["JOLLY_ROGER_FD"]

    roll_of_dice_avg = f'((C{row_of["ROLL_OF_THE_DICE_DICE"]}=TRUE)*F{row_of["ROLL_OF_THE_DICE_DICE"]})'
    jolly_roger_avg = f'((C{row_of["JOLLY_ROGER_FD"]}=TRUE)*F{row_of["JOLLY_ROGER_FD"]})'
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
            available_duration_row = None

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

        if key == "EIGHT_LEGS_EASTON":
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

        if key in (["EIGHT_LEGS_EASTON"] + DAMAGE_ROW_KEYS):
            ws.cell(row=row, column=10, value=(
                f'=({ib("attack")}+{mainstat_attack_delta}*(1+{ib("attack_pct")}/100))*(F{row}/100)'
            ))
            crit_rate_total_block = f'({ib("crit_rate")}+{delta["crit_rate"]}+{crit_rate_bonus_ref})'
            helper_terms_block = ''
            for helper_key, ratios in HELPER_SPECS:
                ratio = ratios.get(key)
                if not ratio:
                    continue
                h_row_of = row_of[helper_key]
                h_gated_block = f'IF(C{h_row_of}=TRUE,F{h_row_of},0)'
                helper_terms_block += f'*(1+{ratio}*{h_gated_block}/100)'
            ws.cell(row=row, column=11, value=(
                f'=J{row}*(1+{ib("stat_damage")}/100)*(1+{ib("damage")}/100)'
                f'*(1+{ib("damage_amp")}/100)'
                f'*(5000/(6000+{ib("monster_defense")}*(1-({ib("def_pen")}+{delta["def_pen"]})/100)))'
                f'*(1+({ib("final_damage")}+{delta["final_damage"]}+{fd_bonus_ref})/100)'
                f'{helper_terms_block}'
                f'*(1+(IF({S("Key", r)}="EIGHT_LEGS_EASTON",{ib("basic_attack_damage")}+{delta["basic_attack_damage"]},'
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

        if key == "EIGHT_LEGS_EASTON":
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
        elif key in MULTI_TRIGGER_KEYS:
            source_rate_terms_block = []
            for src_key in MULTI_TRIGGER_SOURCES[key]:
                src_global_row = ROW[src_key]
                src_local_row = row_of[src_key]
                src_eff_cd_block = effective_cooldown_expr(
                    ib("monster_type"), S("Cooldown(s)", src_global_row), ib("skill_cooldown_decrease"),
                    S("CostsActionSlot", src_global_row),
                )
                if src_key in BUFF_ROW_KEYS:
                    src_available_duration_block = ib("fight_duration")
                else:
                    src_available_duration_block = f'MAX(0,{ib("fight_duration")}-{startup_ref})'
                # Target-count-INDEPENDENT rate — see build_calc_sheet's own identical fix/comment.
                source_rate_terms_block.append(rate_or_exact_hits_expr(
                    fda_block, f"R{src_local_row}", S("HitsPerCast", src_global_row),
                    S("ICD(s)", src_global_row), S("ActiveWindow(s)", src_global_row), src_eff_cd_block,
                    src_available_duration_block, ib("fight_duration"), f"G{src_local_row}*Q{src_local_row}",
                ))
            combined_rate_block = f"({baps_ref}+{'+'.join(source_rate_terms_block)})"
            prefix = f"H{row}*N{row}*{combined_rate_block}"
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

    ws.cell(row=s_baps, column=1, value="Eight-Legs Easton Casts Per Second")
    ws.cell(row=s_baps, column=2, value=f'=MAX(0,{aps_ref}-{castrate_ref})')

    ws.cell(row=s_crit_damage_bonus, column=1, value="Global Critical Damage Bonus % (unused)")
    ws.cell(row=s_crit_damage_bonus, column=2, value=0)

    ws.cell(row=s_fd_bonus, column=1, value="Global Final Damage Bonus % (Jolly Roger only)")
    ws.cell(row=s_fd_bonus, column=2, value=f'={jolly_roger_avg}')

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
        # DPS Gain/% Gain are time-weighted (not dollar-weighted) across the boss/normal branches:
        # each branch's own RELATIVE growth (new/baseline) is measured independently, then blended
        # by Inputs!normal_weight_frac — not the raw dollar totals, which would let a stat's
        # reported value be dominated by whichever branch happens to hit more targets, regardless
        # of how much combat time is actually spent there (confirmed bug, fixed this session).
        boss_ratio = f'IFERROR({boss_total_ref}/Summary!$B${R_BOSS_ONLY_TOTAL},1)'
        normal_ratio = f'IFERROR({normal_total_ref}/Summary!$B${R_NORMAL_ONLY_TOTAL},1)'
        weighted_ratio = f'((1-{IB("normal_weight_frac")})*{boss_ratio}+{IB("normal_weight_frac")}*{normal_ratio})'
        ws.cell(row=row, column=8, value=f"=Summary!$B${R_TOTAL}*({weighted_ratio}-1)")
        ws.cell(row=row, column=9, value=f"={weighted_ratio}*100")
        ws.cell(row=row, column=2, value=f'=IFERROR(1/(I{row}-100),"n/a")')

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
