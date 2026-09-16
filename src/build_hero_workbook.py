#!/usr/bin/env python3
"""
Generates Hero-DPS-Calculator.xlsx: a live-formula Excel replica of a Hero skill-rotation DPS
model, sibling to build_bowmaster_workbook.py (see
/Users/yaniv/.claude/plans/so-basically-we-were-magical-iverson.md this was built from). Hero is
the first STR-main/DEX-sub class built in this project — the mirror image of Bowmaster/Marksman's
DEX-main/STR-sub identity (same two stats, swapped roles).

Sheets: Inputs, FactorTable, Skills, Calc, Summary, Sensitivity, CubeData, PotentialCubes.

Ground truth: fetched live from idle.maplestorywiki.net (curl, domain already allowlisted in
.claude/apple/dangerous_allowed_domains.csv) this session, cross-referenced against the actual
Aug 13 patch notes PDF. All four of Hero's patched skills (Puncture, Enhanced Raging Blow, Enrage,
Magic Crash) are confirmed STALE on the live wiki (pre-patch numbers/behavior) — patch deltas
applied manually on top of the wiki-scraped curves.

Key mechanics/simplifications specific to this kit:
  - Raging Blow (basic attack) reuses the universal 4th-job-basic-attack constant (baseDamage
    2900, factorIndex 21). HitsPerCast=5, bumping to 6 once Mastery Lv.136 "Raging Blow - Strike"
    unlocks (Hero's own Strike-mastery level differs from Bowmaster/Marksman's Lv.134 — confirmed
    directly from Hero/Mastery, not assumed universal). Real Damage mastery chain (102/106/116/
    120/128/132, cumulative +10/11/12/13/14/15% — summed as DELTAS: {102:10,106:1,116:1,120:1,
    128:1,132:1}, NOT the raw displayed values, per the Marksman-session lesson) and Boss Monster
    Damage chain (111/124, +10% each) both included.
  - CONFIRMED WIKI BUG: Hero's own Mastery table has a skill-name swap — every row labeled
    "Puncture" (Lv.108/134) actually describes an Enhanced Raging Blow effect, and every row
    labeled "Enhanced Raging Blow" (Lv.122/138) actually describes a Puncture effect. Re-attributed
    by effect description, not label: Enhanced Raging Blow gets +50% Damage at Lv.108 (its own
    combo-stack-scaling FD bonus at Lv.134 is modeled as a flat +100% Final Damage term — 2 excess
    stacks above the 5 required to use this skill, once Advanced Combo's own 7-stack cap unlocks
    at Lv.110, times 50% each); Puncture gets +50% Damage at Lv.122 and +20 (percentage points)
    added to its own wound's boss-damage-taken bonus at Lv.138 (that bonus's own base curve is a
    live FactorTable lookup, factorIndex 21/baseDamage 100, not a flat approximation).
  - Puncture is split into two rows (same pattern as FP-Mage's Poison Mist Burst/DoT): PUNCTURE
    (the direct hit, 900%->1800%, 3 hits) and PUNCTURE_WOUND (150%->300%/sec DoT, 10s). The wound's
    own boss-damage-taken-increase curve (10%->18%) is approximated as a FLAT level-200 ceiling
    value (18) plus the Lv.138 mastery's own +20 on top, folded into PUNCTURE's MasteryBossDamage%
    — a documented simplification (this is a minor secondary damage-taken-increase mechanic, not
    the skill's own primary damage output, and this project's own default Inputs are level 200
    anyway). PATCHED: targets 5->10, cooldown 19->17s (the "wound bonus expands to all targets, not
    just bosses" behavioral change has no per-target-type mechanic to hook into, so it stays
    boss-only in this model, documented as unmodeled).
  - Enhanced Raging Blow PATCHED: targets 9->12, base damage 550%->610% (curve rescaled
    610/550=1.1091x before reverse-engineering — factorIndex 12, baseDamage 5500 tenths% already
    reflects the pre-patch value; the rescale is applied as a multiplier on the resolved tuple),
    cooldown 19->17s. +100% Boss Monster Damage baked into MasteryBossDamage%.
  - Magic Crash PATCHED: targets 5->9 (effect range +50% not modeled, no such mechanic exists).
    Shared verbatim w/ Dark Knight and Paladin (single wiki page, `/w/Magic_Crash`) — cross-check
    Paladin/Dark Knight's own builds resolve to the identical (48000, 12) tuple.
  - Rush, Beam Blade, Flash Slash are all Maple Hero's own targets — Flash Slash's own page claims
    "+5%/level" in prose but its actual level table shows a flat, non-scaling 350% at every
    sampled level (a wiki content bug) — modeled non-scaling (factorIndex 0). Maple Hero's own
    curve (Beam Blade 1x share, Rush 1.5x, Flash Slash 4x — the biggest share) resolves to
    factorIndex 23/baseDamage 200 tenths%, same "80%-growth-reduction after Lv.120" kink already
    confirmed on Bowmaster/Dark Knight's own Maple Hero curves.
  - Final Attack (Lv.50, 25% chance/35%->49% dmg) + Advanced Final Attack (Lv.105, +500%->900% FD)
    fold into Raging Blow's own coefficient exactly like Bowmaster's ARROW_STREAM pattern — cross-
    checked, both resolve to the IDENTICAL (350,21)/(5000,21) tuples Bowmaster already established
    (confirmed cross-tree shared skill).
  - Combo Attack (40% chance/attack, +4%->5.2% Attack per stack, max 5 stacks, +2 more once
    Advanced Combo unlocks at Lv.110) and Combo Synergy (+5%->8% Final Damage per combo stack) are
    both modeled at steady-state MAX stacks once unlocked — same simplification tier as
    Concentration/Mortal Blow elsewhere in this project (no combo-stack-distribution state machine).
  - Spirit Blade: self-inclusive ally Attack% buff (matches Bishop's own "allied players"
    precedent), live duty-cycled (45s cooldown, 20s duration). Its own damage-taken-reduction
    component is not modeled (no such mechanic exists for the character's own damage-taken).
  - Scaring Sword: on-attack proc (35% chance, 30s cooldown, 10s duration) that increases the
    target's damage taken by 20%->36% (+8 more once Lv.78 mastery unlocks) — feeds the (previously
    unused-placeholder) Global Monster Damage-Taken Bonus% bucket via a duty-cycle-times-proc-
    chance uptime, the first class in this project where that bucket is actually live. Its own
    Attack-down component on the target is not modeled (no such mechanic exists).
  - Enrage: proc buff on its own fixed interval (10s->12s patched) granting +12%->19.2% Final
    Damage and +15%->24% Crit Damage for 5s->7s (patched) — modeled as a live duty-cycled buff
    (interval treated as the "cooldown" for uptime purposes) split into two rows (FD and Crit
    Damage) since this schema's BuffTargetStat column only holds one stat per row. Patch's new
    "activates at combat start" behavior not modeled (no start-of-combat mechanic exists).
  - Iron Body's flat STR bonus and Warrior Mastery's Max HP/Speed bonus have no rows at all —
    Iron Body's STR is assumed already reflected in your own Inputs!STR (same convention as Soul
    Arrow: Bow's DEX bonus in Bowmaster), Warrior Mastery has zero DPS-relevant mechanic (HP/Speed
    aren't modeled anywhere in this project).
  - Weapon Acceleration and Physical Training reuse Bowmaster's own already-resolved
    (50,22)/(100,22) tuples directly (shared-value-different-key, byte-identical wiki wording
    confirmed both classes).
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
OUT_PATH = REPO / "Hero" / "Hero-DPS-Calculator.xlsx"

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

IN = {
    "level": 3,
    "monster_type": 4,
    "flat_attack": 5,
    "attack_pct": 6,
    "monster_defense": 7,
    "crit_rate": 8,
    "crit_damage": 9,
    "attack_speed": 10,
    "flat_str": 11,
    "str_pct": 12,
    "dex": 13,
    "damage": 14,
    "damage_amp": 15,
    "basic_attack_damage": 16,
    "skill_damage": 17,
    "def_pen": 18,
    "boss_damage": 19,
    "normal_damage": 20,
    "min_damage": 21,
    "max_damage": 22,
    "final_damage": 23,
    "skill_lvl_1st": 24,
    "skill_lvl_2nd": 25,
    "skill_lvl_3rd": 26,
    "skill_lvl_4th": 27,
    "skill_lvl_all": 28,
    "skill_cooldown_decrease": 31,
    "basic_attack_target_increase": 32,
    "buff_duration_increase_pct": 33,
    "companion_summon_time_increase_pct": 34,
    "fight_duration": 35,
    "breakthrough_normal_weight_pct": 36,
    "max_enemies_hit": 37,
}


def IB(key):
    if key in DERIVED_ROW:
        return f"Summary!$B${DERIVED_ROW[key]}"
    return f"Inputs!$B${IN[key]}"


def build_readme_sheet(wb):
    ws = wb.active
    ws.title = "README"
    ws["A1"] = "Hero — DPS Calculator: How to Use This Workbook"
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
        "Iron Body's flat +30 STR, Weapon Acceleration, Physical Training, Weapon Mastery, "
        "Combat Mastery, and Power Stance's own Final Damage component are always-on passives "
        "assumed to already be reflected in your own Inputs stat entries — only their "
        "Sensitivity marginal delta is modeled live, matching this project's established "
        "convention. Iron Body's flat STR specifically has NO Sensitivity delta row (no "
        "percentage-bucket exists for a flat sub-stat bonus in this template) — just assume "
        "your own Inputs!STR already includes it. Warrior Mastery (Max HP/Speed) and Power "
        "Stance's own damage-reduction component have zero DPS-relevant mechanic and get no row "
        "at all.",
        "Hero's Mastery table has a confirmed skill-name swap bug: every row labeled 'Puncture' "
        "actually describes an Enhanced Raging Blow effect, and vice versa. Re-attributed by "
        "effect description, not label, throughout this workbook.",
        "Puncture is split into two rows (direct hit + wound DoT), same pattern as FP-Mage's own "
        "Poison Mist Burst/DoT split. Its wound's own continuously-scaling boss-damage-taken "
        "curve (10%->18%) is a live FactorTable lookup (factorIndex 21/baseDamage 100 tenths%, "
        "resolved via _reverse_engineer_hero_factors.py), not a flat approximation.",
        "Combo Attack and Combo Synergy (both combo-stack-scaling passives) are modeled at "
        "steady-state MAX stacks once unlocked, not as an exact stack-gain/decay state machine — "
        "the same simplification tier as Concentration/Mortal Blow elsewhere in this project. "
        "Enhanced Raging Blow's own Lv.134 mastery ('combo final damage +50% per excess stack') "
        "reuses this same steady-state assumption: 2 excess stacks above the 5 required to use "
        "the skill, once Advanced Combo's own 7-stack cap unlocks at Lv.110, giving a flat +100% "
        "Final Damage term once Lv.134 is reached.",
        "Scaring Sword is the first skill in this project to actually drive the Global Monster "
        "Damage-Taken Bonus% bucket (a placeholder left at 0 in every prior class) — modeled as "
        "proc-chance x duty-cycle uptime, feeding every damage row's own monster-damage-taken "
        "term.",
        "Enrage fires on its own fixed interval (not a player-cast cooldown) — modeled the same "
        "way as any other duty-cycled buff, treating the interval as the row's own Cooldown(s). "
        "Its new Aug-13-patch 'activates at combat start' behavior is not modeled (no "
        "start-of-combat mechanic exists anywhere in this project).",
        "Raging Blow (basic attack) reuses the universal 4th-job-basic-attack constant "
        "(baseDamage 2900, factorIndex 21) confirmed identical across every class in this "
        "project. Final Attack + Advanced Final Attack fold into its own coefficient exactly "
        "like Bowmaster's own Arrow Stream — both resolve to the identical tuples Bowmaster "
        "already established, confirming they're genuinely the same cross-tree shared skills.",
        "Magic Crash is shared verbatim with Paladin and Dark Knight (single wiki page) — "
        "patched targets 5->9 (effect range +50% not modeled, no such mechanic exists).",
        "Monster Type blends Boss/Normal Monster Damage% by the Chapter Breakthrough weight %; "
        "PvP forces a fixed 15-second window regardless of the Fixed Fight Duration input.",
        "Not modeled (out of scope): all forms of crowd control (Rush/Puncture stuns), Accuracy, "
        "Evasion, Defense, Max HP/MP recovery, movement speed, and Companion Summoning Time.",
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
    ws["A1"] = "Hero — DPS Calculator Inputs"
    ws["A1"].font = Font(bold=True, size=14)

    rows = [
        ("level", "Character Level", 200),
        ("monster_type", "Monster Type (\"boss\", \"normal\", \"breakthrough\", or \"pvp\")", "boss"),
        ("flat_attack", "Flat ATTACK", 10000),
        ("attack_pct", "ATTACK %", 0),
        ("monster_defense", "Monster Defense (flat, post-x100/x10 scaling)", 0),
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

    ws.cell(row=30, column=1, value="Additional Bonuses").font = SECTION_FONT
    bonus_rows = [
        ("skill_cooldown_decrease", "Skill Cooldown Decrease (seconds, only skills/buffs the character actively casts)", 0),
        ("basic_attack_target_increase", "Basic Attack Target Increase (flat, adds to the 6-target normal-monster base)", 1),
        ("buff_duration_increase_pct", "Buff Duration Increase %", 0),
        ("companion_summon_time_increase_pct", "Companion Summoning Time Increase % (companions not modeled — always 0 DPS impact)", 0),
        ("fight_duration", "Fixed Fight Duration (seconds, boss or normal — leave 0 for steady-state DPS; ignored for pvp)", 0),
        ("breakthrough_normal_weight_pct", "Chapter Breakthrough: Normal-Monster Weight % (only used when Monster Type = breakthrough)", 60),
        ("max_enemies_hit", "Max Enemies Actually In Range (normal monsters only; default 999 = uncapped)", 999),
    ]
    for key, label, default in bonus_rows:
        r = IN[key]
        ws.cell(row=r, column=1, value=label).font = LABEL_FONT
        cell = ws.cell(row=r, column=2, value=existing.get(key, default))
        cell.fill = INPUT_FILL

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
    "RAGING_BLOW", "FINAL_ATTACK_HELPER", "ADVANCED_FINAL_ATTACK_HELPER",
    "PUNCTURE", "PUNCTURE_WOUND", "ENHANCED_RAGING_BLOW", "MAGIC_CRASH",
    "BEAM_BLADE", "RUSH", "FLASH_SLASH", "MAPLE_HERO_HELPER",
    "COMBO_ATTACK", "COMBO_SYNERGY", "SPIRIT_BLADE", "SCARING_SWORD",
    "ENRAGE_FD", "ENRAGE_CRITDMG",
    "NIMBLE_FEET",
    "WEAPON_ACCELERATION", "PHYSICAL_TRAINING", "WEAPON_MASTERY",
    "COMBAT_MASTERY_SKILL", "COMBAT_MASTERY_MAXDMG", "POWER_STANCE_FD",
    "CHANCE_ATTACK_CRIT",
]
ROW = {key: i for i, key in enumerate(ROW_ORDER, start=2)}
LAST_ROW = 1 + len(ROW_ORDER)

# ---------------------------------------------------------------------------
# Summary-sheet row layout — fixed constants, defined ahead of SKILL_ROWS (module-level list
# literal evaluated at import time) so any row needing to self-reference one of these can.
# ---------------------------------------------------------------------------
R_TOTAL = 3
SUMMARY_BREAKDOWN_HEADER_ROW = 6
R_AVGBUFF = 57                      # Attack% bucket (Combo Attack + Spirit Blade)
R_CRIT_RATE_BONUS = 58              # unused placeholder (no live Crit-Rate-buff source exists)
R_MONSTER_DMG_BONUS = 59            # Scaring Sword, proc-chance x duty-cycle
MONSTER_DMG_BONUS_REF = f"Summary!$B${R_MONSTER_DMG_BONUS}"
R_AS_BONUS = 60                     # unused placeholder (no live AS-buff source exists — Nimble Feet's own buff folds in below)
R_APS = 61                          # Actions Per Second
R_CASTRATE = 62                     # Skill + buff cast rate (subtracted from Raging Blow)
R_BAPS = 63                         # Raging Blow (basic attack) Casts Per Second
R_CRIT_DAMAGE_BONUS = 64            # Enrage (Crit Damage half), duty-cycled
R_FD_BONUS = 65                     # Enrage (FD half) + Combo Synergy, steady-state/duty-cycled
R_RAGING_BLOW_DPS = 66

UNLOCK_LEVEL = {
    "RAGING_BLOW": 100,
    "FINAL_ATTACK_HELPER": 50,
    "ADVANCED_FINAL_ATTACK_HELPER": 105,
    "PUNCTURE": 103,
    "PUNCTURE_WOUND": 103,
    "ENHANCED_RAGING_BLOW": 107,
    "MAGIC_CRASH": 117,
    "BEAM_BLADE": 69,
    "RUSH": 63,
    "FLASH_SLASH": 35,
    "MAPLE_HERO_HELPER": 100,
    "COMBO_ATTACK": 45,
    "COMBO_SYNERGY": 75,
    "SPIRIT_BLADE": 40,
    "SCARING_SWORD": 66,
    "ENRAGE_FD": 115,
    "ENRAGE_CRITDMG": 115,
    "WEAPON_ACCELERATION": 33,
    "PHYSICAL_TRAINING": 38,
    "WEAPON_MASTERY": 43,
    "COMBAT_MASTERY_SKILL": 120,
    "COMBAT_MASTERY_MAXDMG": 120,
    "POWER_STANCE_FD": 125,
    "CHANCE_ATTACK_CRIT": 72,
    # NIMBLE_FEET: no threshold (shared Explorer skill, level 0) — stays unconditionally unlocked.
}


def unlock_expr(key):
    level = UNLOCK_LEVEL.get(key)
    return "=TRUE" if level is None else f"={IB('level')}>={level}"


# Maple Hero (Lv.100) — confirmed live from idle.maplestorywiki.net/w/Maple_Hero_(Hero) this
# session: Beam Blade 1x share (own curve, 20%->156%), Rush 1.5x, Flash Slash 4x (biggest share)
# — resolves cleanly to factorIndex 23/baseDamage 200 tenths%.
MAPLE_HERO_RATIOS = {
    "BEAM_BLADE": 20 / 20,
    "RUSH": 30 / 20,
    "FLASH_SLASH": 80 / 20,
}

# (key, name, jobstep, cooldown, costsAction, actionsPerCast, hits, icd, window, chance, rolls,
#  baseDamage, factorIndex, scales, skillMasteryBonusPct, masteryBossDmgPct, masteryNormalDmgPct,
#  normalMonsterTargets, buffTarget, buffDuration, mapleBase, mapleFactor, note)
SKILL_ROWS = [
    ("RAGING_BLOW", "Raging Blow", 4, "", False, 1,
     f'=IF({IB("level")}>=136,6,5)', 0, 0, 100, 1,
     2900, 21, True,
     f"=Calc!F{{FINAL_ATTACK_HELPER}}*IF(Calc!C{{FINAL_ATTACK_HELPER}}=TRUE,1,0)/100"
     f"*(1+Calc!F{{ADVANCED_FINAL_ATTACK_HELPER}}*IF(Calc!C{{ADVANCED_FINAL_ATTACK_HELPER}}=TRUE,1,0)/100)"
     f"*25"
     f"+{level_gated_sum_raw(IB('level'), {102: 10, 106: 1, 116: 1, 120: 1, 128: 1, 132: 1}).replace('{', '{{').replace('}', '}}')}",
     level_gated_sum(IB("level"), {111: 10, 124: 10}), 0,
     f'=6+{IB("basic_attack_target_increase")}', "", 0, "", "",
     "4th-job basic-attack effect (supersedes Slash Blast/Brandish/Intrepid Slash, confirmed "
     "identical wiki wording — 290% damage to 6 target(s) in front 5 time(s) — to every other "
     "class's own 4th-job basic attack). factorIndex 21, baseDamage 2900 tenths%. HitsPerCast=5, "
     "bumping to 6 once Mastery Lv.136 'Raging Blow - Strike' unlocks (Hero's own level for this "
     "differs from Bowmaster/Marksman's Lv.134 — confirmed directly from Hero/Mastery). "
     "SkillMasteryBonus% is Final Attack + Advanced Final Attack's own combined steady-state "
     "contribution (same folding mechanism as Bowmaster's Arrow Stream) PLUS the real Raging "
     "Blow - Damage mastery chain (102/106/116/120/128/132, cumulative +10/11/12/13/14/15% — "
     "summed as DELTAS, not the raw displayed values). MasteryBossDamage% is the real 2-tier "
     "Raging Blow - Boss Monster Damage chain (111/124, +10% each, +20% total)."),
    ("FINAL_ATTACK_HELPER", "Final Attack (helper)", 2, "", False, 1, 1, 0, 0, 100, 1,
     350, 21, True,
     level_gated_sum(IB("level"), {54: 50}), 0, 0, 0, "", 0, "", "",
     "Helper row only — feeds Raging Blow's own coefficient. 25% chance, 35%->49% additional "
     "damage (levels 1-100), factorIndex 21/baseDamage 350 tenths% — resolves to the IDENTICAL "
     "tuple Bowmaster's own Final Attack: Bow helper uses, confirming this is genuinely the same "
     "cross-tree shared skill. Mastery Lv.54 'Final Attack - Damage' +50% (real SkillMasteryBonus%)."),
    ("ADVANCED_FINAL_ATTACK_HELPER", "Advanced Final Attack (helper)", 4, "", False, 1, 1, 0, 0, 100, 1,
     5000, 21, True,
     level_gated_sum(IB("level"), {113: 50}), 0, 0, 0, "", 0, "", "",
     "Helper row only — feeds Raging Blow's own coefficient (Final Attack's own Final Damage "
     "bonus). +500%->900% FD (levels 1-200), factorIndex 21/baseDamage 5000 tenths% — resolves "
     "to the IDENTICAL tuple Bowmaster's own Advanced Final Attack helper uses. Mastery Lv.113 "
     "'Advanced Final Attack - Enhance' +50% (real SkillMasteryBonus%)."),
    ("PUNCTURE", "Puncture", 4, 17, True, 1, 3, 0, 0, 100, 1,
     9000, 12, True,
     level_gated_sum(IB("level"), {122: 50}),
     f"=(100/10)*(INDEX(FactorTable!$B$2:$Y$301,MATCH(ROUND(MIN(300,MAX(1,"
     f"MAX(0,({IB('level')}-100)*3)+{IB('skill_lvl_4th')}+{IB('skill_lvl_all')})),0),"
     f"FactorTable!$A$2:$A$301,0),22)/1000)+IF({IB('level')}>=138,20,0)", 0,
     f'=5+IF({IB("level")}>=100,5,0)', "", 0, "", "",
     "Drives a sword into the target's location: 900%->1800% damage to 5 nearby target(s), 3 "
     "times, leaving a 10-sec wound (see PUNCTURE_WOUND for the DoT half). factorIndex 12, "
     "baseDamage 9000 tenths%. PATCHED: targets 5->10 (modeled as base 5 +5 once Raging Blow's "
     "own Lv.100 unlock, a simplification standing in for 'always 10 once 4th job' since the "
     "patch made this unconditional — cooldown 19->17s. MasteryBossDamage% is the wound's own "
     "continuously-scaling boss-damage-taken bonus, resolved via "
     "_reverse_engineer_hero_factors.py to factorIndex 21/baseDamage 100 tenths% (10%->18% "
     "across levels 1-200, 0% residual) — computed live via its own FactorTable lookup at "
     "Puncture's own job-step-4 input level (this row's own factorIndex is 12, a different "
     "curve shape, so the wound's own 21 lookup can't reuse Calc!E{row} and is inlined here "
     "instead), plus the Lv.138 mastery's own +20 on top (that mastery is mislabeled 'Enhanced "
     "Raging Blow' on the wiki's own Mastery table — a confirmed skill-name swap bug, "
     "re-attributed here to Puncture by effect description). An earlier version of this row "
     "approximated the wound bonus as a flat level-200 ceiling (18) instead of this live curve "
     "— fixed. The patch's 'wound bonus expands to all targets, not just bosses' behavioral "
     "change has no per-target-type mechanic to hook into, so it stays boss-only here, "
     "documented as unmodeled. Mastery Lv.122 'Puncture - Damage' +50% (mislabeled 'Enhanced "
     "Raging Blow' on the wiki, re-attributed here — same swap bug)."),
    ("PUNCTURE_WOUND", "Puncture (wound DoT)", 4, 17, False, 1, 1, 1, 10, 100, 1,
     1500, 12, True,
     0, 0, 0,
     f'=5+IF({IB("level")}>=100,5,0)', "", 0, "", "",
     "Wound DoT half of Puncture — 150%->300% damage/sec for 10 sec (EffectiveHits = "
     "ActiveWindow/ICD = 10 ticks/cast). Shares Puncture's own cooldown/targets (same cast, same "
     "patch). factorIndex 12, baseDamage 1500 tenths%. No own Skill/Boss Mastery — those "
     "sit on PUNCTURE's own row (the wound's damage-taken-increase mastery affects the *boss "
     "taking* more damage during the wound, not the wound's own base damage)."),
    ("ENHANCED_RAGING_BLOW", "Enhanced Raging Blow", 4, 17, True, 1, 6, 0, 0, 100, 1,
     6105, 12, True,
     level_gated_sum(IB("level"), {108: 50}),
     100, 0,
     f'=9+IF({IB("level")}>=100,3,0)', "", 0, "", "",
     "Quickly slashes target(s) in front multiple times: 550%->1100% damage (pre-patch curve), "
     "6 times, usable at combo stack >=5. factorIndex 12, baseDamage 5500 tenths% pre-patch, "
     "PATCHED base damage 550%->610% (curve rescaled 610/550=1.1091x, giving the 6105 stored "
     "here), targets 9->12, cooldown 19->17s. +100% Boss Monster Damage baked into "
     "MasteryBossDamage% (own skill effect, not a mastery tier). Mastery Lv.108 'Enhanced Raging "
     "Blow - Damage' +50% (mislabeled 'Puncture' on the wiki's own Mastery table — confirmed "
     "skill-name swap bug, re-attributed here by effect description). Mastery Lv.134's own "
     "'combo final damage +50% per excess stack' (also mislabeled 'Puncture' on the wiki) is "
     "modeled directly in this row's own K-column as an extra Final-Damage-style multiplicative "
     "term: excess stacks = MAX(0, steady-state max combo stacks - 5 required to use this "
     "skill) = 2 once Advanced Combo (Lv.110) is unlocked, so the term is a flat +100% FD once "
     "Lv.134 is reached (since Lv.134 already implies Lv.110). An earlier version of this row "
     "left this completely unmodeled ('no combo-stack-distribution tracking exists') — fixed, "
     "reusing the same steady-state-max-stacks convention Combo Attack/Combo Synergy already "
     "use elsewhere in this file rather than inventing new state tracking."),
    ("MAGIC_CRASH", "Magic Crash", 4, 28, True, 1, 1, 0, 0, 100, 1,
     48000, 12, True,
     0, 0, 0,
     f'=5+IF({IB("level")}>=100,4,0)', "", 0, "", "",
     "Summons a rock at the target's location, removing 1 buff and dealing 4800%->9600% damage "
     "to 5 nearby target(s), 1 time. factorIndex 12, baseDamage 48000 tenths%. Shared verbatim "
     "with Dark Knight and Paladin (single wiki page, /w/Magic_Crash) — cross-check their own "
     "builds resolve to the identical tuple. PATCHED: targets 5->9 (effect range +50% not "
     "modeled, no such mechanic exists in this project)."),
    ("BEAM_BLADE", "Beam Blade", 3, 16, True, 1, 4, 0, 0, 100, 1,
     2500, 12, True,
     0, 0, 0, 8, "", 0, 200, 23,
     "Releases sword energy: 250%->500% damage to 8 target(s) in front, 4 times. factorIndex 12, "
     "baseDamage 2500 tenths%, 16s cooldown. Not patched. Maple Hero target (own 1x share) — see "
     "MAPLE_HERO_RATIOS."),
    ("RUSH", "Rush", 3, 22, True, 1, 1, 0, 0, 100, 1,
     6000, 12, True,
     0, 0, 0, 12, "", 0, 300, 23,
     "Charges to the front to deal 600%->1200% damage to 12 target(s) (stun 2.5s not modeled). "
     "factorIndex 12, baseDamage 6000 tenths%, 22s cooldown. Shared verbatim with Dark Knight "
     "(and, per this session's own Paladin/Dark Knight research, Paladin too). Not patched "
     "(Mastery Lv.68/90 own cooldown/damage tiers not separately modeled here — folded into the "
     "base curve/cooldown already). Maple Hero target (1.5x share) — see MAPLE_HERO_RATIOS."),
    ("FLASH_SLASH", "Flash Slash", 2, 16, True, 1, 1, 0, 0, 100, 1,
     3500, 0, False,
     level_gated_sum(IB("level"), {39: 50}), 0, 0, 7, "", 0, 800, 23,
     "Deals a flat, non-scaling 350% damage to 7 target(s) in front (own wiki page's prose "
     "claims '+5%/level' but the actual level 1-200 table shows a constant 350% at every "
     "sampled level — a wiki content bug, trust the table). If combo stack >=3, damage +50% — "
     "assumed always active once Combo Attack is unlocked (Lv.45), per this project's steady-"
     "state convention (folded directly into baseDamage: 350*1.5=525 tenths%->3500... actually "
     "kept at the raw 350% here with the +50% combo condition applied via the SAME steady-state "
     "assumption as Combo Attack/Combo Synergy elsewhere, not double-counted — see COMBO_ATTACK "
     "row). factorIndex 0 (non-scaling placeholder), baseDamage 3500 tenths% (=350%), 16s "
     "cooldown. Mastery Lv.39 'Flash Slash - Damage' +50% real SkillMasteryBonus% is captured "
     "via the level_gated_sum below."),
    ("MAPLE_HERO_HELPER", "Maple Hero (helper)", 4, "", False, 1, 1, 0, 0, 100, 1,
     200, 23, True,
     0, 0, 0, 0, "", 0, "", "",
     "Shared ratio-feeder row (see MAPLE_HERO_RATIOS) for Beam Blade/Rush/Flash Slash's own "
     "Final Damage chains — mirrors Shadower/Bowmaster's own Maple Hero mechanism. Confirmed via "
     "idle.maplestorywiki.net/w/Maple_Hero_(Hero) (full level 1-200 curve, resolves cleanly to "
     "factorIndex 23/baseDamage 200 tenths%, same '80%-growth-reduction after Lv.120' kink "
     "already confirmed on Bowmaster/Dark Knight's own Maple Hero curves). No independent DPS "
     "row of its own (Calc columns J-N blank/0, only D/E/F computed, read directly by each "
     "target row's own K-column formula)."),
    ("COMBO_ATTACK", "Combo Attack (Attack%)", 2, "", False, 1, 1, 0, 0, 100, 1,
     40, 22, True,
     0, 0, 0, 0, "ATTACK", 0, "", "",
     "On attack, 40% chance to gain a combo stack (+4%->5.2% Attack for 10s each, max 5 stacks, "
     "+2 more once Advanced Combo unlocks at Lv.110). Modeled at steady-state MAX stacks (5, or "
     "7 once Lv.110) once unlocked, not an exact stack-gain/decay state machine — same "
     "simplification tier as Concentration/Mortal Blow elsewhere. factorIndex 22, baseDamage 40 "
     "tenths% (per-stack value); the x5/x7 stack multiplier is applied via the "
     "SkillMasteryBonus% field below using a level-gated multiplier trick."),
    ("COMBO_SYNERGY", "Combo Synergy (Final Damage per stack)", 3, "", False, 1, 1, 0, 0, 100, 1,
     50, 22, True,
     0, 0, 0, 0, "FINAL_DAMAGE", 0, "", "",
     "+5%->8% Final Damage per combo stack, +10%p combo-stack-chance (not modeled, folded into "
     "the steady-state max-stacks assumption already used for Combo Attack). Modeled at "
     "steady-state MAX stacks (5, or 7 once Lv.110's Advanced Combo unlocks) — factorIndex 22, "
     "baseDamage 50 tenths% (per-stack value)."),
    ("SPIRIT_BLADE", "Spirit Blade", 2, 45, True, 1, 1, 0, 0, 100, 1,
     100, 21, True,
     0, 0, 0, 0, "ATTACK", 20, "", "",
     "Self-inclusive ally buff (matches Bishop's own 'allied players' precedent) — +10%->14% "
     "Attack for 20s, 45s cooldown. Own damage-taken-reduction component (8%->11.2%) not "
     "modeled (no such mechanic for the character's own damage-taken exists). factorIndex 21, "
     "baseDamage 100 tenths%. Not patched."),
    ("SCARING_SWORD", "Scaring Sword", 3, 30, True, 1, 1, 0, 0, 35, 1,
     200, 21, True,
     level_gated_sum(IB("level"), {78: 8}), 0, 0, 0, "MONSTER_DMG", 10, "", "",
     "On-attack proc (35% chance) that increases the target's damage taken by 20%->36% for 10s "
     "(own Attack-down component, 10%->18%, not modeled — no such mechanic exists). First skill "
     "in this project to actually drive the Global Monster Damage-Taken Bonus% bucket (a "
     "placeholder left at 0 in every prior class) — modeled as ProcChance% x duty-cycle uptime "
     "(BuffDuration/Cooldown), feeding every damage row's own monster-damage-taken term. "
     "factorIndex 21, baseDamage 200 tenths%. Mastery Lv.78 'Scaring Sword - Weaken' +8 "
     "(percentage points, real SkillMasteryBonus%). Not patched."),
    ("ENRAGE_FD", "Enrage (Final Damage half)", 4, 12, False, 1, 1, 0, 0, 100, 1,
     120, 22, True,
     0, 0, 0, 0, "FINAL_DAMAGE", 7, "", "",
     "Fires on its own fixed interval (not a player-cast cooldown — modeled the same way as any "
     "other duty-cycled buff, treating the interval as this row's own Cooldown(s)): +12%->19.2% "
     "Final Damage for 5s->7s (patched duration), interval 10s->12s (patched). factorIndex 22, "
     "baseDamage 120 tenths%. PATCHED: duration 5->7s (baked into BuffDuration(s)), interval "
     "10->12s (baked into Cooldown(s)), new 'activates at combat start' behavior not modeled (no "
     "such mechanic exists)."),
    ("ENRAGE_CRITDMG", "Enrage (Crit Damage half)", 4, 12, False, 1, 1, 0, 0, 100, 1,
     150, 22, True,
     0, 0, 0, 0, "CRIT_DAMAGE", 7, "", "",
     "Crit Damage half of Enrage — same interval/duration as ENRAGE_FD (+15%->24% Crit Damage). "
     "factorIndex 22, baseDamage 150 tenths%. Split into its own row since this schema's "
     "BuffTargetStat column only holds one stat per row."),
    ("NIMBLE_FEET", "Nimble Feet", 1, 60, True, 1, 1, 0, 0, 100, 1,
     150, 0, False,
     0, 0, 0, 1, "ATTACK_SPEED", 15, "", "",
     "Shared cross-tree verbatim w/ every class in this project (byte-identical wiki wording — "
     "'+15% Attack Speed, +10% Speed for 15 sec'). Flat +15% Attack Speed / +10% Speed for 15s, "
     "60s cooldown, non-scaling. FactorIndex unused placeholder."),
    ("WEAPON_ACCELERATION", "Weapon Acceleration", 2, "", False, 1, 1, 0, 0, 100, 1,
     50, 22, True,
     0, 0, 0, 0, "ATTACK_SPEED", 0, "", "",
     "Magic Critical pattern — already baked into Inputs!ATTACK_SPEED%; feeds the 2nd-Job Skill "
     "Level Bonus delta. Reuses Bowmaster's own Bow Acceleration tuple directly (shared-value-"
     "different-key, byte-identical wiki wording — '+5% Attack Speed'). factorIndex 22, "
     "baseDamage 50 tenths% (5%->6.5%, levels 1-100)."),
    ("PHYSICAL_TRAINING", "Physical Training", 2, "", False, 1, 1, 0, 0, 100, 1,
     100, 22, True,
     0, 0, 0, 0, "BASIC_ATTACK_DAMAGE", 0, "", "",
     "Magic Critical pattern — already baked into Inputs!BASIC_ATTACK_DAMAGE%; feeds the "
     "2nd-Job Skill Level Bonus delta. Reuses Bowmaster's own Physical Training tuple directly "
     "(byte-identical wiki wording — '+10% Basic Attack Damage'). factorIndex 22, baseDamage "
     "100 tenths% (10%->13%, levels 1-100)."),
    ("WEAPON_MASTERY", "Weapon Mastery", 2, "", False, 1, 1, 0, 0, 100, 1,
     150, 22, True,
     0, 0, 0, 0, "MIN_DAMAGE", 0, "", "",
     "Magic Critical pattern — already baked into Inputs!MIN_DAMAGE%; feeds the 2nd-Job Skill "
     "Level Bonus delta. factorIndex 22, baseDamage 150 tenths% (15%->19.5%, levels 1-100)."),
    ("COMBAT_MASTERY_SKILL", "Combat Mastery (Skill Damage)", 4, "", False, 1, 1, 0, 0, 100, 1,
     150, 22, True,
     0, 0, 0, 0, "SKILL_DAMAGE", 0, "", "",
     "Magic Critical pattern — already baked into Inputs!SKILL_DAMAGE%; feeds the 4th-Job Skill "
     "Level Bonus delta (Skill Damage side). factorIndex 22, baseDamage 150 tenths% (15%->24%, "
     "levels 1-200)."),
    ("COMBAT_MASTERY_MAXDMG", "Combat Mastery (Max Damage Multiplier)", 4, "", False, 1, 1, 0, 0, 100, 1,
     200, 22, True,
     0, 0, 0, 0, "MAX_DAMAGE", 0, "", "",
     "Same skill as Combat Mastery (Skill Damage) above, +20%->32% Max Damage Multiplier. Magic "
     "Critical pattern — already baked into Inputs!MAX_DAMAGE%; feeds the 4th-Job Skill Level "
     "Bonus delta (Max Damage Multiplier side). factorIndex 22, baseDamage 200 tenths%."),
    ("POWER_STANCE_FD", "Power Stance (Final Damage)", 4, "", False, 1, 1, 0, 0, 100, 1,
     150, 22, True,
     0, 0, 0, 0, "FINAL_DAMAGE", 0, "", "",
     "Own damage-taken-reduction component (5%->8%) not modeled (no such mechanic exists). Magic "
     "Critical pattern — already baked into Inputs!FINAL_DAMAGE%; feeds the 4th-Job Skill Level "
     "Bonus delta. factorIndex 22, baseDamage 150 tenths% (15%->24%, levels 1-200)."),
    ("CHANCE_ATTACK_CRIT", "Chance Attack (Crit Rate)", 3, "", False, 1, 1, 0, 0, 100, 1,
     80, 22, True,
     0, 0, 0, 0, "CRIT_RATE", 0, "", "",
     "Own Status Effect Damage component (12%->19.2%) not modeled (no such mechanic exists). "
     "Magic Critical pattern — already baked into Inputs!CRIT_RATE%; feeds the 3rd-Job Skill "
     "Level Bonus delta. factorIndex 22, baseDamage 80 tenths% (8%->12.8%, levels 1-200)."),
]

# Resolve the {ROW_KEY} placeholders in RAGING_BLOW's own SkillMasteryBonus% formula (Python
# f-string braces collide with Excel's own {..} SUMPRODUCT array-constant syntax elsewhere in
# this file, so this one row's cross-references are patched in after the fact instead).
_raging_blow_row = [list(row) for row in SKILL_ROWS if row[0] == "RAGING_BLOW"][0]
_raging_blow_row[14] = _raging_blow_row[14].format(
    FINAL_ATTACK_HELPER=ROW["FINAL_ATTACK_HELPER"],
    ADVANCED_FINAL_ATTACK_HELPER=ROW["ADVANCED_FINAL_ATTACK_HELPER"],
)
SKILL_ROWS = [tuple(_raging_blow_row) if row[0] == "RAGING_BLOW" else row for row in SKILL_ROWS]

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
    "PUNCTURE", "PUNCTURE_WOUND", "ENHANCED_RAGING_BLOW", "MAGIC_CRASH",
    "BEAM_BLADE", "RUSH", "FLASH_SLASH",
]
ATTACK_BUFF_ROW_KEYS = ["COMBO_ATTACK", "SPIRIT_BLADE"]
PASSIVE_MULT_ROW_KEYS = [
    "WEAPON_ACCELERATION", "PHYSICAL_TRAINING", "WEAPON_MASTERY",
    "COMBAT_MASTERY_SKILL", "COMBAT_MASTERY_MAXDMG", "POWER_STANCE_FD", "CHANCE_ATTACK_CRIT",
]
HELPER_ROW_KEYS = ["FINAL_ATTACK_HELPER", "ADVANCED_FINAL_ATTACK_HELPER", "MAPLE_HERO_HELPER"]
MAPLE_HERO_ROW_KEYS = ["MAPLE_HERO_HELPER"]
DAMAGE_DEALING_KEYS = ["RAGING_BLOW"] + DAMAGE_ROW_KEYS

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
            rate_r = rate_or_exact_hits_expr(
                fixed_duration_active_main, f"R{r}", S("HitsPerCast", r), S("ICD(s)", r),
                S("ActiveWindow(s)", r), eff_cd_r, IB("fight_duration"), f"G{r}*Q{r}",
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
            for col in (7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19):
                ws.cell(row=r, column=col, value=("1" if col == 9 else ""))
            continue

        if key == "RAGING_BLOW":
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

        if key in (["RAGING_BLOW"] + DAMAGE_ROW_KEYS):
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
            combo_excess_fd_term = (
                f'*(1+IF({S("Key", r)}="ENHANCED_RAGING_BLOW",'
                f'IF({IB("level")}>=134,MAX(0,IF({IB("level")}>=110,7,5)-5)*50,0),0)/100)'
            )
            ws.cell(row=r, column=11, value=(
                f'=J{r}*(1+{IB("stat_damage")}/100)*(1+{IB("damage")}/100)'
                f'*(1+{monster_dmg_term}/100)'
                f'*(1+{IB("damage_amp")}/100)'
                f'*(5000/(6000+{IB("monster_defense")}*(1-{IB("def_pen")}/100)))'
                f'*(1+({IB("final_damage")}+{final_damage_extra_ref})/100)'
                f'{maple_term}'
                f'{combo_excess_fd_term}'
                f'*(1+(IF({S("Key", r)}="RAGING_BLOW",{IB("basic_attack_damage")},{IB("skill_damage")}))/100)'
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

        if key == "RAGING_BLOW":
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
    ws["A1"] = "Hero — DPS Summary"
    ws["A1"].font = Font(bold=True, size=14)

    ws.cell(row=DERIVED_HEADER_ROW, column=1, value="Derived Values (read-only, computed from Inputs)").font = SECTION_FONT
    ws.cell(row=D_ATTACK, column=1, value="ATTACK (= Flat ATTACK x (1+ATTACK%/100))")
    ws.cell(row=D_ATTACK, column=2, value=f'={IB("flat_attack")}*(1+{IB("attack_pct")}/100)')

    ws.cell(row=D_STAT_DAMAGE, column=1, value="STAT_DAMAGE % (= 1% of total STR + 0.25% of DEX)")
    ws.cell(
        row=D_STAT_DAMAGE, column=2,
        value=f'=({IB("flat_str")}*(1+{IB("str_pct")}/100))*0.01+{IB("dex")}*0.0025'
    )

    ws.cell(row=D_BASIC_INPUT_LEVEL, column=1, value="Basic Attack (Raging Blow) Input Level (4th job formula)")
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
    ws.cell(row=D_SKILL_COEFFICIENT, column=1, value="SKILL_COEFFICIENT — Raging Blow base coefficient % (before bonuses)")
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

    r_ca, r_sb = ROW["COMBO_ATTACK"], ROW["SPIRIT_BLADE"]
    r_cs = ROW["COMBO_SYNERGY"]
    r_ss = ROW["SCARING_SWORD"]
    r_ef, r_ecd = ROW["ENRAGE_FD"], ROW["ENRAGE_CRITDMG"]
    r_nf = ROW["NIMBLE_FEET"]

    # Combo Attack/Combo Synergy: steady-state MAX stacks (5, or 7 once Advanced Combo unlocks
    # at Lv.110) — the stack-count multiplier is applied here, not baked into the Skills-sheet
    # row itself (Calc!F holds the PER-STACK value).
    combo_stacks_expr = f'IF({IB("level")}>=110,7,5)'
    combo_attack_avg = f'((Calc!C{r_ca}=TRUE)*Calc!F{r_ca}*{combo_stacks_expr})'
    spirit_blade_avg = f'((Calc!C{r_sb}=TRUE)*Calc!F{r_sb}*{buff_uptime(r_sb)})'
    combo_synergy_avg = f'((Calc!C{r_cs}=TRUE)*Calc!F{r_cs}*{combo_stacks_expr})'
    nimble_feet_avg = f'((Calc!C{r_nf}=TRUE)*Calc!F{r_nf}*{buff_uptime(r_nf)})'
    scaring_sword_avg = f'((Calc!C{r_ss}=TRUE)*Calc!F{r_ss}*(Skills!{SC["ProcChance%"]}{r_ss}/100)*{buff_uptime(r_ss)})'
    enrage_fd_avg = f'((Calc!C{r_ef}=TRUE)*Calc!F{r_ef}*{buff_uptime(r_ef)})'
    enrage_critdmg_avg = f'((Calc!C{r_ecd}=TRUE)*Calc!F{r_ecd}*{buff_uptime(r_ecd)})'

    ws.cell(row=R_AVGBUFF, column=1, value="Attack%% Bucket Multiplier (Combo Attack + Spirit Blade, summed additively)")
    ws.cell(row=R_AVGBUFF, column=2, value=f'=1+({combo_attack_avg}+{spirit_blade_avg})/100')

    ws.cell(row=R_CRIT_RATE_BONUS, column=1, value="Global Crit Rate Bonus % (unused — no live Crit-Rate-buff source exists)")
    ws.cell(row=R_CRIT_RATE_BONUS, column=2, value=0)

    ws.cell(row=R_MONSTER_DMG_BONUS, column=1, value="Global Monster Damage-Taken Bonus % (Scaring Sword, proc-chance x duty-cycle)")
    ws.cell(row=R_MONSTER_DMG_BONUS, column=2, value=f'={scaring_sword_avg}')

    ws.cell(row=R_AS_BONUS, column=1, value="Attack Speed Buff Bonus % (Nimble Feet, duty-cycle averaged)")
    ws.cell(row=R_AS_BONUS, column=2, value=f'={nimble_feet_avg}')

    ws.cell(row=R_APS, column=1, value="Actions Per Second")
    ws.cell(row=R_APS, column=2, value=(
        f'=1+MIN(150,150*(1-(1-{IB("attack_speed")}/150)*(1-B{R_AS_BONUS}/150)))/100'
    ))

    ws.cell(row=R_CASTRATE, column=1, value="Skill + Buff Cast Rate (subtracted from Raging Blow, 1/s)")
    ws.cell(row=R_CASTRATE, column=2, value=(
        f'=IF({fda_main},'
        f'SUMPRODUCT((Skills!{SC["CostsActionSlot"]}2:{SC["CostsActionSlot"]}{LAST_ROW}=TRUE)*'
        f'(Calc!C2:C{LAST_ROW}=TRUE)*Calc!R2:R{LAST_ROW}*Skills!{SC["ActionsPerCast"]}2:{SC["ActionsPerCast"]}{LAST_ROW})/{IB("fight_duration")},'
        f'SUMPRODUCT((Skills!{SC["CostsActionSlot"]}2:{SC["CostsActionSlot"]}{LAST_ROW}=TRUE)*'
        f'(Calc!C2:C{LAST_ROW}=TRUE)*Calc!Q2:Q{LAST_ROW}*Skills!{SC["ActionsPerCast"]}2:{SC["ActionsPerCast"]}{LAST_ROW}))'
    ))

    ws.cell(row=R_BAPS, column=1, value="Raging Blow (Basic Attack) Casts Per Second")
    ws.cell(row=R_BAPS, column=2, value=f'=MAX(0,B{R_APS}-B{R_CASTRATE})')

    ws.cell(row=R_CRIT_DAMAGE_BONUS, column=1, value="Global Critical Damage Bonus % (Enrage, duty-cycled)")
    ws.cell(row=R_CRIT_DAMAGE_BONUS, column=2, value=f'={enrage_critdmg_avg}')

    ws.cell(row=R_FD_BONUS, column=1, value="Global Final Damage Bonus % (Enrage + Combo Synergy)")
    ws.cell(row=R_FD_BONUS, column=2, value=f'={enrage_fd_avg}+{combo_synergy_avg}')

    ws.cell(row=R_TOTAL, column=1, value="TOTAL DPS").font = Font(bold=True, size=13)
    ws.cell(row=R_TOTAL, column=2, value=f"=SUM(Calc!O2:O{LAST_ROW})").font = Font(bold=True, size=13)

    ws.cell(row=R_RAGING_BLOW_DPS, column=1, value="Raging Blow (Basic Attack) DPS")
    ws.cell(row=R_RAGING_BLOW_DPS, column=2, value=f"=Calc!O{ROW['RAGING_BLOW']}")

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
# delta folds into. "attack_mult" has no literal Inputs field but is unused here (Hero has no
# Soul-Arrow-style flat Attack% passive needing this slot).
PASSIVE_DELTA_SLOT = {
    "WEAPON_ACCELERATION": "attack_speed",
    "PHYSICAL_TRAINING": "basic_attack_damage",
    "WEAPON_MASTERY": "min_damage",
    "COMBAT_MASTERY_SKILL": "skill_damage",
    "COMBAT_MASTERY_MAXDMG": "max_damage",
    "POWER_STANCE_FD": "final_damage",
    "CHANCE_ATTACK_CRIT": "crit_rate",
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
    s_fd_bonus = calc_end + 9
    s_total = calc_end + 11
    crit_rate_bonus_ref = f"B{s_crit_rate_bonus}"
    as_bonus_ref, aps_ref, castrate_ref, baps_ref = f"B{s_as_bonus}", f"B{s_aps}", f"B{s_castrate}", f"B{s_baps}"
    crit_damage_bonus_ref = f"B{s_crit_damage_bonus}"
    fd_bonus_ref = f"B{s_fd_bonus}"
    total_ref = f"B{s_total}"

    fda_block = fixed_duration_active_expr(ib("monster_type"), ib("fight_duration"))
    bdi_block = ib("buff_duration_increase_pct")

    def buff_uptime_block(local_row, skills_row):
        return uptime_fraction_or_exact_expr(
            fda_block, f'S{local_row}', ib("monster_type"), S("BuffDuration(s)", skills_row),
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

    r_ca, r_sb = ROW["COMBO_ATTACK"], ROW["SPIRIT_BLADE"]
    r_cs, r_ss = ROW["COMBO_SYNERGY"], ROW["SCARING_SWORD"]
    r_ef, r_ecd, r_nf = ROW["ENRAGE_FD"], ROW["ENRAGE_CRITDMG"], ROW["NIMBLE_FEET"]

    combo_stacks_block = f'IF({ib("level")}>=110,7,5)'
    combo_attack_avg = f'((C{row_of["COMBO_ATTACK"]}=TRUE)*F{row_of["COMBO_ATTACK"]}*{combo_stacks_block})'
    spirit_blade_avg = f'((C{row_of["SPIRIT_BLADE"]}=TRUE)*F{row_of["SPIRIT_BLADE"]}*{buff_uptime_block(row_of["SPIRIT_BLADE"], r_sb)})'
    combo_synergy_avg = f'((C{row_of["COMBO_SYNERGY"]}=TRUE)*F{row_of["COMBO_SYNERGY"]}*{combo_stacks_block})'
    nimble_feet_avg = f'((C{row_of["NIMBLE_FEET"]}=TRUE)*F{row_of["NIMBLE_FEET"]}*{buff_uptime_block(row_of["NIMBLE_FEET"], r_nf)})'
    scaring_sword_avg = (
        f'((C{row_of["SCARING_SWORD"]}=TRUE)*F{row_of["SCARING_SWORD"]}*'
        f'(Skills!{SC["ProcChance%"]}{r_ss}/100)*{buff_uptime_block(row_of["SCARING_SWORD"], r_ss)})'
    )
    enrage_fd_avg = f'((C{row_of["ENRAGE_FD"]}=TRUE)*F{row_of["ENRAGE_FD"]}*{buff_uptime_block(row_of["ENRAGE_FD"], r_ef)})'
    enrage_critdmg_avg = f'((C{row_of["ENRAGE_CRITDMG"]}=TRUE)*F{row_of["ENRAGE_CRITDMG"]}*{buff_uptime_block(row_of["ENRAGE_CRITDMG"], r_ecd)})'
    # Attack% bucket: every live skill/buff Attack% source sums additively into ONE combined
    # percentage before a single multiplication — matches Verification item 6.
    attack_bucket_block = f'(1+({combo_attack_avg}+{spirit_blade_avg}+{delta["attack_mult"]})/100)'

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

        if key == "RAGING_BLOW":
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

        if key in (["RAGING_BLOW"] + DAMAGE_ROW_KEYS):
            ws.cell(row=row, column=10, value=f'={ib("attack")}*(F{row}/100)')
            monster_dmg_term = monster_blend_expr(
                ib("monster_type"), ib("normal_weight_frac"),
                f'{ib("boss_damage")}+{delta["boss_damage"]}+{S("MasteryBossDamage%", r)}+{MONSTER_DMG_BONUS_REF}',
                f'{ib("normal_damage")}+{S("MasteryNormalDamage%", r)}+{MONSTER_DMG_BONUS_REF}',
                "0",
            )
            crit_rate_total_block = f'({ib("crit_rate")}+{delta["crit_rate"]}+{crit_rate_bonus_ref})'
            maple_ratio = MAPLE_HERO_RATIOS.get(key)
            mh_row_of = row_of["MAPLE_HERO_HELPER"]
            maple_hero_gated_block = f'IF(C{mh_row_of}=TRUE,F{mh_row_of},0)'
            maple_term = f'*(1+{maple_ratio}*{maple_hero_gated_block}/100)' if maple_ratio else ''
            combo_excess_fd_term = (
                f'*(1+IF({S("Key", r)}="ENHANCED_RAGING_BLOW",'
                f'IF({ib("level")}>=134,MAX(0,IF({ib("level")}>=110,7,5)-5)*50,0),0)/100)'
            )
            ws.cell(row=row, column=11, value=(
                f'=J{row}*(1+{ib("stat_damage")}/100)*(1+{ib("damage")}/100)'
                f'*(1+{monster_dmg_term}/100)'
                f'*(1+{ib("damage_amp")}/100)'
                f'*(5000/(6000+{ib("monster_defense")}*(1-({ib("def_pen")}+{delta["def_pen"]})/100)))'
                f'*(1+({ib("final_damage")}+{delta["final_damage"]}+{fd_bonus_ref})/100)'
                f'{maple_term}'
                f'{combo_excess_fd_term}'
                f'*(1+(IF({S("Key", r)}="RAGING_BLOW",{ib("basic_attack_damage")}+{delta["basic_attack_damage"]},'
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

        if key == "RAGING_BLOW":
            raging_blow_targets_expr = f'(6+{ib("basic_attack_target_increase")})'
            ws.cell(row=row, column=15, value=(
                f"=IF(C{row},{S('HitsPerCast', r)}*N{row}*{baps_ref}*"
                f"{target_multiplier_expr(ib('monster_type'), ib('normal_weight_frac'), raging_blow_targets_expr, ib('max_enemies_hit'))},0)"
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
    ws.cell(row=s_crit_rate_bonus, column=2, value=0)

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

    ws.cell(row=s_baps, column=1, value="Raging Blow Casts Per Second")
    ws.cell(row=s_baps, column=2, value=f'=MAX(0,{aps_ref}-{castrate_ref})')

    ws.cell(row=s_crit_damage_bonus, column=1, value="Global Critical Damage Bonus % (Enrage)")
    ws.cell(row=s_crit_damage_bonus, column=2, value=f'={enrage_critdmg_avg}')

    ws.cell(row=s_fd_bonus, column=1, value="Global Final Damage Bonus % (Enrage + Combo Synergy)")
    ws.cell(row=s_fd_bonus, column=2, value=f'={enrage_fd_avg}+{combo_synergy_avg}')

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
            value = ws.cell(row=row, column=2).value
            if value is not None and not (isinstance(value, str) and value.startswith("=")):
                existing_inputs[key] = value

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
