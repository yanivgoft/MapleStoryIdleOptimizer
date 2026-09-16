#!/usr/bin/env python3
"""
Generates Paladin-DPS-Calculator.xlsx: a live-formula Excel replica of a Paladin skill-rotation
DPS model, sibling to build_hero_workbook.py (see
/Users/yaniv/.claude/plans/so-basically-we-were-magical-iverson.md this was built from). Paladin
is STR-main/DEX-sub, identical stat identity to Hero (no rename needed).

Sheets: Inputs, FactorTable, Skills, Calc, Summary, Sensitivity, CubeData, PotentialCubes.

IMPORTANT DATA-QUALITY CAVEAT (confirmed by user — Paladin was added to the wiki alongside Bishop
and has the same root-cause gap): Paladin's own 6 unique damage/buff skills (Close Combat, Noble
Demand, Heaven's Hammer, Divine Mark, Divine Judgment, and Maple Hero (Paladin) itself) have NO
individual wiki page — confirmed genuine 404s, no alternate-name links to follow (unlike
Bowmaster's Arrow Platter/Quiver Flow case). Same FLAGGED ASSUMPTION convention as
build_bishop_workbook.py: `(baseDamage, factorIndex)` derived from the single known level-1 value
using the per-skill-type factorIndex convention (burst/DoT->12, buffs/passives->22, basic
attack->21), each such row's own Note says so explicitly. The Mastery table's own discrete
level-gated deltas ARE separately confirmed real data and are layered on top of these assumed base
curves. Divine Swing (1st job) and Divine Charge (3rd job) are both superseded basic-attack-effect
skills once Blast (4th job) unlocks — same "job-tier-is-gone scope" convention as every other
class's superseded early basics, no row needed, their own separate Mastery chains (Lv.32-58 for
Divine Swing... actually Divine Swing has none; Lv.62-92 for Divine Charge) don't carry forward.

Ground truth: fetched live from idle.maplestorywiki.net this session (full skill list + Mastery
table), cross-referenced against the actual Aug 13 patch notes PDF. Both of Paladin's patched
skills (Divine Shield, Magic Crash) are confirmed STALE on the live wiki.

Key mechanics/simplifications specific to this kit:
  - Blast (basic attack) reuses the universal 4th-job-basic-attack constant (baseDamage 2900,
    factorIndex 21). HitsPerCast=5, bumping to 6 once Mastery Lv.136 "Blast - Strike" unlocks
    (identical level to Hero's own Raging Blow - Strike). Real Damage mastery chain (102/106/116/
    120/128/132, summed as DELTAS not raw cumulative values) and Boss Monster Damage chain
    (111/124, +10% each) both included, same universal 4th-job-basic-attack mastery pattern
    confirmed across every class in this project.
  - Final Attack (Lv.50, 25% chance/35%->49% dmg) folds into Blast's own coefficient exactly like
    Hero's own Raging Blow pattern — resolves to the IDENTICAL (350,21) tuple Hero/Bowmaster
    already established (confirmed cross-tree shared skill). Paladin has NO Advanced Final Attack
    at all (confirmed absent from its skill list) — Final Attack folds in as a single-stage bonus
    only, no two-stage helper multiplier.
  - Magic Crash and Rush are shared verbatim with Hero (single wiki page each, same curve/cooldown/
    targets) — reuse Hero's own already-resolved (48000,12)/(6000,12) tuples directly, no
    re-derivation. Magic Crash PATCHED: targets 5->9 (effect range +50% not modeled).
  - Close Combat, Noble Demand, Heaven's Hammer, Divine Mark (split into main hit + detonation,
    same pattern as Hero's Puncture/FP-Mage's Poison Mist split), and Divine Judgment (modeled as
    detonation only — the proc fires "every 10 basic attacks," approximated via a live
    Cooldown(s) formula referencing Summary!B{R_BAPS} directly, i.e. 10/basic-attack-rate; its own
    +30% Basic Attack Damage buff component is FLAGGED, not modeled, since stacking another
    duty-cycle layer on an already-dynamic proc rate was judged out of scope for this pass) are
    all FLAGGED ASSUMPTIONS per the caveat above.
  - Maple Hero (Paladin) has no wiki page at all — FLAGGED ASSUMPTION using the level-1 baseline
    values only (Noble Demand 20%, Rush 30%, Close Combat 80%, Final Attack 150% — the biggest
    share), factorIndex 23 convention (matching every other class's own Maple Hero), assumed to
    follow the same "80%-growth-reduction after Lv.120" shape already confirmed on every other
    class's own Maple Hero curve. Final Attack's own Maple Hero share is folded as an extra
    multiplier directly on its helper-row contribution inside Blast's own SkillMasteryBonus%
    formula (a bespoke pattern — Hero's own Maple Hero never targeted a helper-folded skill).
  - Vessel of Light (Lv.45): proc-based Attack% buff (15% chance per basic attack, +15%->22%
    Attack for 10s) with no stated internal cooldown — its own uptime is FLAGGED/approximated as
    `MIN(1, Duration * ProcChance%/100 * BasicAttackRate)` rather than the standard
    cooldown-driven duty-cycle helper used everywhere else, since there's no cooldown field to
    drive that helper. Greater Vessel of Light (Lv.110, +18% FD "for the duration of Vessel of
    Light") reuses that SAME computed uptime fraction directly rather than having its own
    cooldown/duration — also FLAGGED (no individual curve, single known value).
  - Divine Shield (Lv.75, patched): fixed-interval buff (not player-cast, same duty-cycle
    treatment as Hero's own Enrage) — +15% Final Damage for 10s every 15s. Barrier-blocking
    component not modeled. PATCHED: new "activates at combat start" behavior not modeled (no such
    mechanic exists anywhere in this project).
  - Guardian (Lv.105, +10% FD/20s/24s CD) and Divine Blessing (Lv.115, +12% FD/22s/30s CD, self-
    inclusive ally buff matching Bishop's own precedent) are live duty-cycled Final Damage buffs.
    HP Recovery's own +12% Attack/20s/25s CD component is modeled the same way; its own instant
    HP-restore component is not modeled (no HP tracking anywhere in this project).
  - Iron Body's flat STR bonus, Warrior Mastery's Max HP/Speed bonus, and Paladin's own 2nd-job
    Power Stance (3% dmg reduction/8% Attack) have no rows at all — Iron Body's STR and Power
    Stance's Attack% are assumed already reflected in your own Inputs entries (same convention as
    Hero's own Iron Body/Bowmaster's Soul Arrow: Bow), Warrior Mastery has zero DPS-relevant
    mechanic.
  - Weapon Acceleration, Physical Training, Weapon Mastery reuse Hero's own already-resolved
    tuples directly (shared-value-different-key, byte-identical wiki wording confirmed across
    Hero/Paladin/Dark Knight). Paladin Expert (Lv.120, Skill Damage/Max Damage) matches Hero's own
    Combat Mastery pattern exactly.
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
OUT_PATH = REPO / "Paladin" / "Paladin-DPS-Calculator.xlsx"

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
    ws["A1"] = "Paladin — DPS Calculator: How to Use This Workbook"
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
        "Iron Body's flat +30 STR, Warrior Mastery, Paladin's own 2nd-job Power Stance (Attack%), "
        "Weapon Acceleration, Physical Training, Weapon Mastery, and Paladin Expert are always-on "
        "passives assumed to already be reflected in your own Inputs stat entries — only their "
        "Sensitivity marginal delta is modeled live. Iron Body's flat STR and Power Stance's own "
        "damage-reduction component have NO Sensitivity delta row at all (no percentage-bucket "
        "exists for a flat sub-stat bonus, and no damage-taken mechanic exists in this template).",
        "DATA-QUALITY CAVEAT: Close Combat, Noble Demand, Heaven's Hammer, Divine Mark, Divine "
        "Judgment, and Maple Hero (Paladin) all have NO individual wiki page (confirmed genuine "
        "404s) — same root-cause gap as Bishop. Each row's (baseDamage, factorIndex) is a FLAGGED "
        "ASSUMPTION derived from the single known level-1 value + a per-skill-type factorIndex "
        "convention, not a verified curve. The Mastery table's own discrete level-gated deltas "
        "layered on top of those assumed curves ARE separately confirmed real data.",
        "Divine Mark is split into two rows (main hit + detonation), same pattern as Hero's own "
        "Puncture / FP-Mage's Poison Mist Burst-DoT split. Divine Judgment is modeled as its own "
        "detonation only — the proc fires 'every 10 basic attacks,' approximated via a live "
        "Cooldown(s) formula referencing the Basic Attack Casts Per Second cell directly (10 / "
        "rate); its own +30% Basic Attack Damage buff component is FLAGGED, not modeled.",
        "Vessel of Light is a proc (15% chance per basic attack) with no stated internal cooldown "
        "— its uptime is approximated as MIN(1, Duration x ProcChance% x Basic Attack Rate) "
        "rather than the standard cooldown-driven duty-cycle helper used everywhere else in this "
        "project. Greater Vessel of Light (+18% FD 'for the duration of Vessel of Light') reuses "
        "that same computed uptime fraction directly rather than having its own duty cycle.",
        "Divine Shield fires on its own fixed interval (not a player-cast cooldown) — modeled the "
        "same way as Hero's own Enrage, treating the interval as the row's own Cooldown(s). Its "
        "new Aug-13-patch 'activates at combat start' behavior is not modeled (no start-of-combat "
        "mechanic exists anywhere in this project). Its own barrier-blocking component (defensive) "
        "is also not modeled.",
        "Blast (basic attack) reuses the universal 4th-job-basic-attack constant (baseDamage 2900, "
        "factorIndex 21) confirmed identical across every class in this project. Final Attack "
        "folds into its own coefficient exactly like Hero's own Raging Blow pattern (resolves to "
        "the identical tuple Hero/Bowmaster already established) — Paladin has NO Advanced Final "
        "Attack at all, so this is a single-stage fold only, unlike Hero/Dark Knight's two-stage "
        "version.",
        "Magic Crash and Rush are shared verbatim with Hero (single wiki page each) — reused "
        "Hero's own already-resolved tuples directly rather than re-deriving. Magic Crash PATCHED: "
        "targets 5->9 (effect range +50% not modeled, no such mechanic exists).",
        "Monster Type blends Boss/Normal Monster Damage% by the Chapter Breakthrough weight %; "
        "PvP forces a fixed 15-second window regardless of the Fixed Fight Duration input.",
        "Not modeled (out of scope): all forms of crowd control, Accuracy, Evasion, Defense, "
        "HP/MP recovery, movement speed, Companion Summoning Time, and pure support/defensive "
        "skills with no DPS-relevant mechanic (Combat Orders, Achilles, Parashock Guard).",
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
    ws["A1"] = "Paladin — DPS Calculator Inputs"
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
    "BLAST", "FINAL_ATTACK_HELPER",
    "CLOSE_COMBAT", "NOBLE_DEMAND", "HEAVENS_HAMMER",
    "DIVINE_MARK_MAIN", "DIVINE_MARK_DETONATION", "DIVINE_JUDGMENT",
    "MAGIC_CRASH", "RUSH", "MAPLE_HERO_HELPER",
    "VESSEL_OF_LIGHT", "GREATER_VESSEL_OF_LIGHT",
    "DIVINE_SHIELD", "GUARDIAN", "DIVINE_BLESSING", "HP_RECOVERY_ATK",
    "NIMBLE_FEET",
    "WEAPON_ACCELERATION", "PHYSICAL_TRAINING", "WEAPON_MASTERY",
    "PALADIN_EXPERT_SKILL", "PALADIN_EXPERT_MAXDMG",
]
ROW = {key: i for i, key in enumerate(ROW_ORDER, start=2)}
LAST_ROW = 1 + len(ROW_ORDER)

# ---------------------------------------------------------------------------
# Summary-sheet row layout — fixed constants, defined ahead of SKILL_ROWS (module-level list
# literal evaluated at import time) so any row needing to self-reference one of these can.
# ---------------------------------------------------------------------------
R_TOTAL = 3
SUMMARY_BREAKDOWN_HEADER_ROW = 6
R_AVGBUFF = 57                      # Attack% bucket (Vessel of Light + HP Recovery, duty-cycled)
R_CRIT_RATE_BONUS = 58              # unused placeholder (no live Crit-Rate-buff source exists)
R_MONSTER_DMG_BONUS = 59            # unused placeholder (no live monster-dmg-taken source modeled)
R_AS_BONUS = 60                     # unused placeholder (no live AS-buff source exists)
R_APS = 61                          # Actions Per Second
R_CASTRATE = 62                     # Skill + buff cast rate (subtracted from Blast)
R_BAPS = 63                         # Blast (basic attack) Casts Per Second
R_CRIT_DAMAGE_BONUS = 64            # unused placeholder (no live Crit-Damage-buff source exists)
R_FD_BONUS = 65                     # Divine Shield + Guardian + Divine Blessing + Greater Vessel of Light
R_BLAST_DPS = 66

UNLOCK_LEVEL = {
    "BLAST": 100,
    "FINAL_ATTACK_HELPER": 50,
    "CLOSE_COMBAT": 35,
    "NOBLE_DEMAND": 66,
    "HEAVENS_HAMMER": 103,
    "DIVINE_MARK_MAIN": 107,
    "DIVINE_MARK_DETONATION": 107,
    "DIVINE_JUDGMENT": 125,
    "MAGIC_CRASH": 117,
    "RUSH": 63,
    "MAPLE_HERO_HELPER": 100,
    "VESSEL_OF_LIGHT": 45,
    "GREATER_VESSEL_OF_LIGHT": 110,
    "DIVINE_SHIELD": 75,
    "GUARDIAN": 105,
    "DIVINE_BLESSING": 115,
    "HP_RECOVERY_ATK": 74,
    "WEAPON_ACCELERATION": 33,
    "PHYSICAL_TRAINING": 38,
    "WEAPON_MASTERY": 43,
    "PALADIN_EXPERT_SKILL": 120,
    "PALADIN_EXPERT_MAXDMG": 120,
    # NIMBLE_FEET: no threshold (shared Explorer skill, level 0) — stays unconditionally unlocked.
}


def unlock_expr(key):
    level = UNLOCK_LEVEL.get(key)
    return "=TRUE" if level is None else f"={IB('level')}>={level}"


# Maple Hero (Lv.100) — FLAGGED ASSUMPTION, no wiki page exists for Maple Hero (Paladin) at all
# (confirmed 404, unlike Hero/Bowmaster/Dark Knight's own Maple Hero pages). Using the level-1
# baseline values only (Noble Demand 20%, Rush 30%, Close Combat 80%, Final Attack 150% — the
# biggest share) as ratios against Noble Demand's own 1x share, factorIndex 23 convention
# (matching every other class's own Maple Hero), assumed to follow the same curve shape already
# confirmed on Hero/Bowmaster/Dark Knight's own Maple Hero (80%-growth-reduction after Lv.120).
# Final Attack's own 7.5x share is folded directly into BLAST's own SkillMasteryBonus% formula
# below (a bespoke pattern, since Final Attack is a HELPER row, not a DAMAGE_ROW_KEYS/basic-attack
# row — the generic MAPLE_HERO_RATIOS.get() mechanism only applies to those).
MAPLE_HERO_RATIOS = {
    "NOBLE_DEMAND": 20 / 20,
    "RUSH": 30 / 20,
    "CLOSE_COMBAT": 80 / 20,
}

# (key, name, jobstep, cooldown, costsAction, actionsPerCast, hits, icd, window, chance, rolls,
#  baseDamage, factorIndex, scales, skillMasteryBonusPct, masteryBossDmgPct, masteryNormalDmgPct,
#  normalMonsterTargets, buffTarget, buffDuration, mapleBase, mapleFactor, note)
SKILL_ROWS = [
    ("BLAST", "Blast", 4, "", False, 1,
     f'=IF({IB("level")}>=136,6,5)', 0, 0, 100, 1,
     2900, 21, True,
     f"=Calc!F{{FINAL_ATTACK_HELPER}}*IF(Calc!C{{FINAL_ATTACK_HELPER}}=TRUE,1,0)/100*25"
     f"*(1+7.5*IF(Calc!C{{MAPLE_HERO_HELPER}}=TRUE,Calc!F{{MAPLE_HERO_HELPER}},0)/100)"
     f"+{level_gated_sum_raw(IB('level'), {102: 10, 106: 1, 116: 1, 120: 1, 128: 1, 132: 1}).replace('{', '{{').replace('}', '}}')}",
     level_gated_sum(IB("level"), {111: 10, 124: 10}), 0,
     f'=6+{IB("basic_attack_target_increase")}', "", 0, "", "",
     "4th-job basic-attack effect (supersedes Divine Swing/Divine Charge, confirmed identical "
     "wiki wording — 290% damage to 6 target(s) in front 5 time(s) — to every other class's own "
     "4th-job basic attack). factorIndex 21, baseDamage 2900 tenths%. HitsPerCast=5, bumping to "
     "6 once Mastery Lv.136 'Blast - Strike' unlocks (identical level to Hero's own Raging Blow - "
     "Strike). SkillMasteryBonus% is Final Attack's own steady-state contribution (ProcChance x "
     "AdditionalDamage% x 25, single-stage since Paladin has no Advanced Final Attack), further "
     "multiplied by Maple Hero's own +150% FD share targeting Final Attack specifically (a "
     "bespoke fold — Final Attack is a HELPER row, not a normal Maple Hero target), PLUS the real "
     "Blast - Damage mastery chain (102/106/116/120/128/132, summed as DELTAS). "
     "MasteryBossDamage% is the real 2-tier Blast - Boss Monster Damage chain (111/124, +10% "
     "each, +20% total)."),
    ("FINAL_ATTACK_HELPER", "Final Attack (helper)", 2, "", False, 1, 1, 0, 0, 100, 1,
     350, 21, True,
     level_gated_sum(IB("level"), {54: 50}), 0, 0, 0, "", 0, "", "",
     "Helper row only — feeds Blast's own coefficient. 25% chance, 35%->49% additional damage "
     "(levels 1-100), factorIndex 21/baseDamage 350 tenths% — resolves to the IDENTICAL tuple "
     "Hero/Bowmaster's own Final Attack helper uses, confirming this is genuinely the same "
     "cross-tree shared skill. Mastery Lv.54 'Final Attack - Damage' +50% (real "
     "SkillMasteryBonus%, same level as Hero's own chain). Paladin has NO Advanced Final Attack "
     "at all (confirmed absent from its skill list) — no second-stage helper needed."),
    ("CLOSE_COMBAT", "Close Combat", 2, 18, True, 1, 1, 0, 0, 100, 1,
     4600, 12, True,
     level_gated_sum(IB("level"), {39: 50}), 0, 0, 7, "", 0, "", "",
     "FLAGGED ASSUMPTION (no individual wiki page exists — confirmed genuine 404, same root-cause "
     "gap as Bishop): factorIndex 12 (burst convention), baseDamage 4600 tenths% (460% level-1). "
     "'Deals 460% damage to 7 nearby target(s)', 18s cooldown. Mastery Lv.39 'Close Combat - "
     "Damage' +50% (real SkillMasteryBonus%). Mastery Lv.44 'Close Combat - Weaken' (+10%p target "
     "damage taken for an unstated duration) is FLAGGED, not modeled — no duration/chance given "
     "on the Mastery table to drive a duty-cycle calc. Maple Hero target (4x share, the biggest) "
     "— see MAPLE_HERO_RATIOS."),
    ("NOBLE_DEMAND", "Noble Demand", 3, 30, True, 1, 1, 0, 0, 100, 1,
     16000, 12, True,
     level_gated_sum(IB("level"), {73: 50}), 0, 0, 8, "", 0, "", "",
     "FLAGGED ASSUMPTION (no individual wiki page exists): factorIndex 12, baseDamage 16000 "
     "tenths% (1600% level-1). 'Deals 1600% damage to 8 nearby target(s) and increases their "
     "damage taken by 12% for 10 sec' — the damage-taken-increase component is FLAGGED, not "
     "modeled (would need its own duty-cycle bucket wiring, judged out of scope for a flagged-"
     "assumption skill). 30s cooldown. Mastery Lv.73 'Noble Demand - Damage' +50% (real "
     "SkillMasteryBonus%). Mastery Lv.94 'Noble Demand - Reuse' (-30% cooldown) not separately "
     "modeled, same treatment as Hero's own Rush cooldown masteries. Maple Hero target (1x "
     "share, the smallest) — see MAPLE_HERO_RATIOS."),
    ("HEAVENS_HAMMER", "Heaven's Hammer", 4, 18, True, 1, 5, 0, 0, 100, 1,
     7800, 12, True,
     level_gated_sum(IB("level"), {108: 50}),
     f"=100+IF({IB('level')}>=134,100,0)", 0,
     7, "", 0, "", "",
     "FLAGGED ASSUMPTION (no individual wiki page exists): factorIndex 12, baseDamage 7800 "
     "tenths% (780% level-1). 'Slams a large hammer to deal 780% damage to 7 target(s) in front "
     "5 time(s). Deals additional 100% Boss Monster Damage' — the +100% Boss Monster Damage is "
     "the skill's own innate effect (baked into MasteryBossDamage%'s base 100), with Mastery "
     "Lv.134 'Heaven's Hammer - Boss Monster Damage' adding another +100% tier on top (total 200% "
     "once both are active). 18s cooldown. Mastery Lv.108 'Heaven's Hammer - Damage' +50% (real "
     "SkillMasteryBonus%). Not patched (absent from the Aug 13 patch notes PDF's 2-skill Paladin "
     "section)."),
    ("DIVINE_MARK_MAIN", "Divine Mark (main hit)", 4, 16, True, 1, 6, 0, 0, 100, 1,
     4600, 12, True,
     level_gated_sum(IB("level"), {122: 50}), 0, 0, 8, "", 0, "", "",
     "FLAGGED ASSUMPTION (no individual wiki page exists): factorIndex 12, baseDamage 4600 "
     "tenths% (460% level-1). 'Deals 460% damage to 8 target(s) in front 6 time(s), then "
     "detonates stigmata of light' (see DIVINE_MARK_DETONATION for the second half — same cast, "
     "same cooldown/targets). 16s cooldown. Mastery Lv.122 'Divine Mark - Damage' +50% (real "
     "SkillMasteryBonus%, applies to the main hit only — the wiki doesn't specify it applying to "
     "the detonation too). Mastery Lv.138 'Divine Mark - Weaken' (+20% target damage taken for "
     "10s) is FLAGGED, not modeled (same reasoning as Noble Demand's own weaken effect)."),
    ("DIVINE_MARK_DETONATION", "Divine Mark (detonation)", 4, 16, False, 1, 4, 0, 0, 100, 1,
     4000, 12, True,
     0, 0, 0, 8, "", 0, "", "",
     "Detonation half of the same Divine Mark cast — 'dealing 400% damage to 8 nearby target(s) 4 "
     "time(s)'. Shares Divine Mark's own cooldown/cast (CostsActionSlot=False here since "
     "DIVINE_MARK_MAIN already costs the action slot for this cast). factorIndex 12, baseDamage "
     "4000 tenths% (400% level-1). FLAGGED ASSUMPTION, same root-cause gap as its main-hit "
     "sibling. No own Skill/Boss Mastery (Lv.122's own mastery only mentions 'Divine Mark - "
     "Damage' without specifying the detonation, so it's not applied here to avoid "
     "double-counting an ambiguous mastery scope)."),
    ("DIVINE_JUDGMENT", "Divine Judgment (detonation)", 4, f'=10/Summary!$B${R_APS}', False, 1, 4, 0, 0, 100, 1,
     8500, 12, True,
     0, 0, 0, 4, "", 0, "", "",
     "FLAGGED ASSUMPTION (no individual wiki page exists), AND a bespoke trigger-rate "
     "approximation: 'Every 10 basic attacks, increases Basic Attack Damage by 30% for 5 sec and "
     "creates a Divine Brand that explodes after 1 sec dealing 850% damage to 4 nearby target(s) "
     "4 time(s)'. Modeled as detonation-only — Cooldown(s) is a LIVE formula (10/Summary!Actions "
     "Per Second, NOT Basic-Attack-specific Casts Per Second — referencing that cell instead "
     "would create a genuine circular reference, since R_BAPS is downstream of the same "
     "cast-rate SUMPRODUCT this row's own Q-column formula feeds into, regardless of "
     "CostsActionSlot=False) approximating the 'every 10 basic attacks' trigger as a steady-"
     "state period, the same self-referencing-a-Summary-constant pattern already established for "
     "Marksman's own Quiver Cartridge AS-scaled cooldown. The +30% Basic Attack Damage buff "
     "component is FLAGGED, not modeled — stacking another duty-cycle layer on an already-"
     "dynamic proc rate was judged out of scope for this pass. factorIndex 12, baseDamage 8500 "
     "tenths% (850% level-1). CostsActionSlot=False (the detonation itself doesn't consume the "
     "action queue — it's a delayed proc off basic attacks, which already have their own slot)."),
    ("MAGIC_CRASH", "Magic Crash", 4, 28, True, 1, 1, 0, 0, 100, 1,
     48000, 12, True,
     0, 0, 0,
     f'=5+IF({IB("level")}>=100,4,0)', "", 0, "", "",
     "Summons a rock at the target's location, removing 1 buff and dealing 4800%->9600% damage "
     "to 5 nearby target(s), 1 time. factorIndex 12, baseDamage 48000 tenths%. Shared verbatim "
     "with Hero and Dark Knight (single wiki page, /w/Magic_Crash) — reuses Hero's own already-"
     "resolved tuple directly, not re-derived. PATCHED: targets 5->9 (effect range +50% not "
     "modeled, no such mechanic exists in this project)."),
    ("RUSH", "Rush", 3, 22, True, 1, 1, 0, 0, 100, 1,
     6000, 12, True,
     0, 0, 0, 12, "", 0, "", "",
     "Charges to the front to deal 600%->1200% damage to 12 target(s) (stun 2.5s not modeled). "
     "factorIndex 12, baseDamage 6000 tenths%, 22s cooldown. Shared verbatim with Hero and Dark "
     "Knight — reuses Hero's own already-resolved tuple directly. Not patched (Mastery Lv.68/90 "
     "own cooldown/damage tiers not separately modeled here, same treatment as Hero's own build). "
     "Maple Hero target (1.5x share) — see MAPLE_HERO_RATIOS."),
    ("MAPLE_HERO_HELPER", "Maple Hero (helper)", 4, "", False, 1, 1, 0, 0, 100, 1,
     200, 23, True,
     0, 0, 0, 0, "", 0, "", "",
     "FLAGGED ASSUMPTION — Maple_Hero_(Paladin) 404s, confirmed no wiki page exists at all "
     "(unlike Hero/Bowmaster/Dark Knight's own Maple Hero pages). Shared ratio-feeder row (see "
     "MAPLE_HERO_RATIOS) for Noble Demand/Rush/Close Combat's own Final Damage chains, PLUS a "
     "bespoke direct fold into Final Attack's own contribution inside BLAST's SkillMasteryBonus% "
     "(see that row's own Note). Using only the confirmed level-1 baseline values (factorIndex 23 "
     "convention, baseDamage 200 tenths% = Noble Demand's own 20% 1x share), assumed to follow "
     "the same '80%-growth-reduction after Lv.120' curve shape already confirmed on every other "
     "class's own Maple Hero. No independent DPS row of its own (Calc columns J-N blank/0, only "
     "D/E/F computed, read directly by each target row's own K-column formula)."),
    ("VESSEL_OF_LIGHT", "Vessel of Light", 2, "", False, 1, 1, 0, 0, 15, 1,
     150, 22, True,
     0, 0, 0, 0, "ATTACK", 10, "", "",
     "'When attacking with Basic Attack, increases Attack by 15%->22% for 10 sec with a 15% "
     "chance.' FLAGGED simplification: this is a proc with no stated internal cooldown, so its "
     "uptime can't use the standard cooldown-driven duty-cycle helper used everywhere else in "
     "this project — instead approximated in Summary as MIN(1, Duration x ProcChance%/100 x "
     "Basic Attack Casts Per Second). factorIndex 22, baseDamage 150 tenths% (15%->22%, levels "
     "1-200). Not patched."),
    ("GREATER_VESSEL_OF_LIGHT", "Greater Vessel of Light", 4, "", False, 1, 1, 0, 0, 100, 1,
     180, 22, True,
     0, 0, 0, 0, "FINAL_DAMAGE", 0, "", "",
     "FLAGGED ASSUMPTION (no individual wiki page, single known value): 'Increases Final Damage "
     "by 18% for the duration of Vessel of Light.' No own Cooldown/BuffDuration — reuses Vessel "
     "of Light's own computed uptime fraction directly in the Summary-sheet formula rather than "
     "having an independent duty cycle. factorIndex 22, baseDamage 180 tenths% (18% level-1)."),
    ("DIVINE_SHIELD", "Divine Shield", 3, 15, False, 1, 1, 0, 0, 100, 1,
     150, 22, True,
     0, 0, 0, 0, "FINAL_DAMAGE", 10, "", "",
     "'Every 15 sec creates a barrier that lasts for 5 sec to block damage up to 6% of Max HP. "
     "Also increases Final Damage by 15% for 10 sec.' Fires on its own fixed interval (not a "
     "player-cast cooldown) — modeled the same way as Hero's own Enrage, treating the interval "
     "as this row's own Cooldown(s). Barrier-blocking component (defensive) not modeled. "
     "factorIndex 22, baseDamage 150 tenths% (15% level-1, no individual wiki page — FLAGGED "
     "ASSUMPTION). PATCHED: new 'activates at combat start' behavior not modeled (no such "
     "mechanic exists anywhere in this project)."),
    ("GUARDIAN", "Guardian", 4, 24, True, 1, 1, 0, 0, 100, 1,
     100, 22, True,
     0, 0, 0, 0, "FINAL_DAMAGE", 20, "", "",
     "FLAGGED ASSUMPTION (no individual wiki page exists): factorIndex 22, baseDamage 100 "
     "tenths% (10% level-1). 'Increases your Final Damage by 10% for 20 sec and grants "
     "Continuous Recovery to 1 nearby ally for 20 sec, recovering 0.8% HP/sec' — the ally-HP-"
     "recovery component not modeled (no HP tracking anywhere in this project). 24s cooldown. "
     "Not patched."),
    ("DIVINE_BLESSING", "Divine Blessing", 4, 30, True, 1, 1, 0, 0, 100, 1,
     120, 22, True,
     0, 0, 0, 0, "FINAL_DAMAGE", 22, "", "",
     "FLAGGED ASSUMPTION (no individual wiki page exists): factorIndex 22, baseDamage 120 "
     "tenths% (12% level-1). Self-inclusive ally buff (matches Bishop's own 'allied players' "
     "precedent) — 'Increases your and 1 nearby ally's Final Damage by 12% for 22 sec', 30s "
     "cooldown. Not patched."),
    ("HP_RECOVERY_ATK", "HP Recovery (Attack buff)", 3, 25, True, 1, 1, 0, 0, 100, 1,
     120, 22, True,
     0, 0, 0, 0, "ATTACK", 20, "", "",
     "FLAGGED ASSUMPTION (no individual wiki page exists): factorIndex 22, baseDamage 120 "
     "tenths% (12% level-1). 'Immediately recovers HP by 9% and increases Attack by 12% for 20 "
     "sec' — the instant HP-restore component not modeled (no HP tracking anywhere in this "
     "project). 25s cooldown. Not patched."),
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
     "Level Bonus delta. Reuses Hero's own Weapon Acceleration tuple directly (byte-identical "
     "wiki wording — '+5% Attack Speed'). factorIndex 22, baseDamage 50 tenths% (5%->6.5%, "
     "levels 1-100)."),
    ("PHYSICAL_TRAINING", "Physical Training", 2, "", False, 1, 1, 0, 0, 100, 1,
     100, 22, True,
     0, 0, 0, 0, "BASIC_ATTACK_DAMAGE", 0, "", "",
     "Magic Critical pattern — already baked into Inputs!BASIC_ATTACK_DAMAGE%; feeds the "
     "2nd-Job Skill Level Bonus delta. Reuses Hero's own Physical Training tuple directly "
     "(byte-identical wiki wording — '+10% Basic Attack Damage'). factorIndex 22, baseDamage "
     "100 tenths% (10%->13%, levels 1-100)."),
    ("WEAPON_MASTERY", "Weapon Mastery", 2, "", False, 1, 1, 0, 0, 100, 1,
     150, 22, True,
     0, 0, 0, 0, "MIN_DAMAGE", 0, "", "",
     "Magic Critical pattern — already baked into Inputs!MIN_DAMAGE%; feeds the 2nd-Job Skill "
     "Level Bonus delta. Reuses Hero's own Weapon Mastery tuple directly. factorIndex 22, "
     "baseDamage 150 tenths% (15%->19.5%, levels 1-100)."),
    ("PALADIN_EXPERT_SKILL", "Paladin Expert (Skill Damage)", 4, "", False, 1, 1, 0, 0, 100, 1,
     150, 22, True,
     0, 0, 0, 0, "SKILL_DAMAGE", 0, "", "",
     "Magic Critical pattern — already baked into Inputs!SKILL_DAMAGE%; feeds the 4th-Job Skill "
     "Level Bonus delta (Skill Damage side). Matches Hero's own Combat Mastery pattern exactly. "
     "factorIndex 22, baseDamage 150 tenths% (15%->24%, levels 1-200)."),
    ("PALADIN_EXPERT_MAXDMG", "Paladin Expert (Max Damage Multiplier)", 4, "", False, 1, 1, 0, 0, 100, 1,
     200, 22, True,
     0, 0, 0, 0, "MAX_DAMAGE", 0, "", "",
     "Same skill as Paladin Expert (Skill Damage) above, +20%->32% Max Damage Multiplier. Magic "
     "Critical pattern — already baked into Inputs!MAX_DAMAGE%; feeds the 4th-Job Skill Level "
     "Bonus delta (Max Damage Multiplier side). factorIndex 22, baseDamage 200 tenths%."),
]

# Resolve the {ROW_KEY} placeholders in BLAST's own SkillMasteryBonus% formula (Python
# f-string braces collide with Excel's own {..} SUMPRODUCT array-constant syntax elsewhere in
# this file, so this one row's cross-references are patched in after the fact instead).
_raging_blow_row = [list(row) for row in SKILL_ROWS if row[0] == "BLAST"][0]
_raging_blow_row[14] = _raging_blow_row[14].format(
    FINAL_ATTACK_HELPER=ROW["FINAL_ATTACK_HELPER"],
    MAPLE_HERO_HELPER=ROW["MAPLE_HERO_HELPER"],
)
SKILL_ROWS = [tuple(_raging_blow_row) if row[0] == "BLAST" else row for row in SKILL_ROWS]

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
    "CLOSE_COMBAT", "NOBLE_DEMAND", "HEAVENS_HAMMER",
    "DIVINE_MARK_MAIN", "DIVINE_MARK_DETONATION", "DIVINE_JUDGMENT",
    "MAGIC_CRASH", "RUSH",
]
ATTACK_BUFF_ROW_KEYS = ["VESSEL_OF_LIGHT", "HP_RECOVERY_ATK"]
PASSIVE_MULT_ROW_KEYS = [
    "WEAPON_ACCELERATION", "PHYSICAL_TRAINING", "WEAPON_MASTERY",
    "PALADIN_EXPERT_SKILL", "PALADIN_EXPERT_MAXDMG",
]
HELPER_ROW_KEYS = ["FINAL_ATTACK_HELPER", "MAPLE_HERO_HELPER"]
MAPLE_HERO_ROW_KEYS = ["MAPLE_HERO_HELPER"]
DAMAGE_DEALING_KEYS = ["BLAST"] + DAMAGE_ROW_KEYS

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

        if key == "BLAST":
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

        if key in (["BLAST"] + DAMAGE_ROW_KEYS):
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
            ws.cell(row=r, column=11, value=(
                f'=J{r}*(1+{IB("stat_damage")}/100)*(1+{IB("damage")}/100)'
                f'*(1+{monster_dmg_term}/100)'
                f'*(1+{IB("damage_amp")}/100)'
                f'*(5000/(6000+{IB("monster_defense")}*(1-{IB("def_pen")}/100)))'
                f'*(1+({IB("final_damage")}+{final_damage_extra_ref})/100)'
                f'{maple_term}'
                f'*(1+(IF({S("Key", r)}="BLAST",{IB("basic_attack_damage")},{IB("skill_damage")}))/100)'
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

        if key == "BLAST":
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
    ws["A1"] = "Paladin — DPS Summary"
    ws["A1"].font = Font(bold=True, size=14)

    ws.cell(row=DERIVED_HEADER_ROW, column=1, value="Derived Values (read-only, computed from Inputs)").font = SECTION_FONT
    ws.cell(row=D_ATTACK, column=1, value="ATTACK (= Flat ATTACK x (1+ATTACK%/100))")
    ws.cell(row=D_ATTACK, column=2, value=f'={IB("flat_attack")}*(1+{IB("attack_pct")}/100)')

    ws.cell(row=D_STAT_DAMAGE, column=1, value="STAT_DAMAGE % (= 1% of total STR + 0.25% of DEX)")
    ws.cell(
        row=D_STAT_DAMAGE, column=2,
        value=f'=({IB("flat_str")}*(1+{IB("str_pct")}/100))*0.01+{IB("dex")}*0.0025'
    )

    ws.cell(row=D_BASIC_INPUT_LEVEL, column=1, value="Basic Attack (Blast) Input Level (4th job formula)")
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
    ws.cell(row=D_SKILL_COEFFICIENT, column=1, value="SKILL_COEFFICIENT — Blast base coefficient % (before bonuses)")
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

    r_vol, r_gvol = ROW["VESSEL_OF_LIGHT"], ROW["GREATER_VESSEL_OF_LIGHT"]
    r_ds, r_gu, r_db = ROW["DIVINE_SHIELD"], ROW["GUARDIAN"], ROW["DIVINE_BLESSING"]
    r_hpr = ROW["HP_RECOVERY_ATK"]
    r_nf = ROW["NIMBLE_FEET"]

    # Vessel of Light: proc off basic attacks with no stated internal cooldown, so its uptime
    # can't use the standard cooldown-driven buff_uptime() helper — approximated instead as
    # MIN(1, Duration x ProcChance%/100 x Basic Attack Casts Per Second). Greater Vessel of Light
    # has no own duty cycle at all and reuses this SAME uptime fraction directly (its own effect
    # only exists "for the duration of Vessel of Light").
    vessel_of_light_uptime = f'MIN(1,{S("BuffDuration(s)", r_vol)}*({S("ProcChance%", r_vol)}/100)*Summary!$B${R_BAPS})'
    vessel_of_light_avg = f'((Calc!C{r_vol}=TRUE)*Calc!F{r_vol}*{vessel_of_light_uptime})'
    greater_vessel_avg = f'((Calc!C{r_gvol}=TRUE)*Calc!F{r_gvol}*{vessel_of_light_uptime})'
    hp_recovery_avg = f'((Calc!C{r_hpr}=TRUE)*Calc!F{r_hpr}*{buff_uptime(r_hpr)})'
    divine_shield_avg = f'((Calc!C{r_ds}=TRUE)*Calc!F{r_ds}*{buff_uptime(r_ds)})'
    guardian_avg = f'((Calc!C{r_gu}=TRUE)*Calc!F{r_gu}*{buff_uptime(r_gu)})'
    divine_blessing_avg = f'((Calc!C{r_db}=TRUE)*Calc!F{r_db}*{buff_uptime(r_db)})'
    nimble_feet_avg = f'((Calc!C{r_nf}=TRUE)*Calc!F{r_nf}*{buff_uptime(r_nf)})'

    ws.cell(row=R_AVGBUFF, column=1, value="Attack%% Bucket Multiplier (Vessel of Light + HP Recovery, summed additively)")
    ws.cell(row=R_AVGBUFF, column=2, value=f'=1+({vessel_of_light_avg}+{hp_recovery_avg})/100')

    ws.cell(row=R_CRIT_RATE_BONUS, column=1, value="Global Crit Rate Bonus % (unused — no live Crit-Rate-buff source exists)")
    ws.cell(row=R_CRIT_RATE_BONUS, column=2, value=0)

    ws.cell(row=R_MONSTER_DMG_BONUS, column=1, value="Global Monster Damage-Taken Bonus % (unused — Close Combat/Noble Demand/Divine Mark's own weaken effects flagged, not modeled)")
    ws.cell(row=R_MONSTER_DMG_BONUS, column=2, value=0)

    ws.cell(row=R_AS_BONUS, column=1, value="Attack Speed Buff Bonus % (Nimble Feet, duty-cycle averaged)")
    ws.cell(row=R_AS_BONUS, column=2, value=f'={nimble_feet_avg}')

    ws.cell(row=R_APS, column=1, value="Actions Per Second")
    ws.cell(row=R_APS, column=2, value=(
        f'=1+MIN(150,150*(1-(1-{IB("attack_speed")}/150)*(1-B{R_AS_BONUS}/150)))/100'
    ))

    ws.cell(row=R_CASTRATE, column=1, value="Skill + Buff Cast Rate (subtracted from Blast, 1/s)")
    ws.cell(row=R_CASTRATE, column=2, value=(
        f'=IF({fda_main},'
        f'SUMPRODUCT((Skills!{SC["CostsActionSlot"]}2:{SC["CostsActionSlot"]}{LAST_ROW}=TRUE)*'
        f'(Calc!C2:C{LAST_ROW}=TRUE)*Calc!R2:R{LAST_ROW}*Skills!{SC["ActionsPerCast"]}2:{SC["ActionsPerCast"]}{LAST_ROW})/{IB("fight_duration")},'
        f'SUMPRODUCT((Skills!{SC["CostsActionSlot"]}2:{SC["CostsActionSlot"]}{LAST_ROW}=TRUE)*'
        f'(Calc!C2:C{LAST_ROW}=TRUE)*Calc!Q2:Q{LAST_ROW}*Skills!{SC["ActionsPerCast"]}2:{SC["ActionsPerCast"]}{LAST_ROW}))'
    ))

    ws.cell(row=R_BAPS, column=1, value="Blast (Basic Attack) Casts Per Second")
    ws.cell(row=R_BAPS, column=2, value=f'=MAX(0,B{R_APS}-B{R_CASTRATE})')

    ws.cell(row=R_CRIT_DAMAGE_BONUS, column=1, value="Global Critical Damage Bonus % (unused — no live Crit-Damage-buff source exists)")
    ws.cell(row=R_CRIT_DAMAGE_BONUS, column=2, value=0)

    ws.cell(row=R_FD_BONUS, column=1, value="Global Final Damage Bonus % (Divine Shield + Guardian + Divine Blessing + Greater Vessel of Light)")
    ws.cell(row=R_FD_BONUS, column=2, value=f'={divine_shield_avg}+{guardian_avg}+{divine_blessing_avg}+{greater_vessel_avg}')

    ws.cell(row=R_TOTAL, column=1, value="TOTAL DPS").font = Font(bold=True, size=13)
    ws.cell(row=R_TOTAL, column=2, value=f"=SUM(Calc!O2:O{LAST_ROW})").font = Font(bold=True, size=13)

    ws.cell(row=R_BLAST_DPS, column=1, value="Blast (Basic Attack) DPS")
    ws.cell(row=R_BLAST_DPS, column=2, value=f"=Calc!O{ROW['BLAST']}")

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
# delta folds into. "attack_mult" has no literal Inputs field but is unused here (Paladin has no
# Soul-Arrow-style flat Attack% passive needing this slot).
PASSIVE_DELTA_SLOT = {
    "WEAPON_ACCELERATION": "attack_speed",
    "PHYSICAL_TRAINING": "basic_attack_damage",
    "WEAPON_MASTERY": "min_damage",
    "PALADIN_EXPERT_SKILL": "skill_damage",
    "PALADIN_EXPERT_MAXDMG": "max_damage",
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

    r_vol, r_gvol = ROW["VESSEL_OF_LIGHT"], ROW["GREATER_VESSEL_OF_LIGHT"]
    r_ds, r_gu, r_db = ROW["DIVINE_SHIELD"], ROW["GUARDIAN"], ROW["DIVINE_BLESSING"]
    r_hpr, r_nf = ROW["HP_RECOVERY_ATK"], ROW["NIMBLE_FEET"]

    vessel_of_light_uptime_block = f'MIN(1,{S("BuffDuration(s)", r_vol)}*({S("ProcChance%", r_vol)}/100)*{baps_ref})'
    vessel_of_light_avg = f'((C{row_of["VESSEL_OF_LIGHT"]}=TRUE)*F{row_of["VESSEL_OF_LIGHT"]}*{vessel_of_light_uptime_block})'
    greater_vessel_avg = f'((C{row_of["GREATER_VESSEL_OF_LIGHT"]}=TRUE)*F{row_of["GREATER_VESSEL_OF_LIGHT"]}*{vessel_of_light_uptime_block})'
    hp_recovery_avg = f'((C{row_of["HP_RECOVERY_ATK"]}=TRUE)*F{row_of["HP_RECOVERY_ATK"]}*{buff_uptime_block(row_of["HP_RECOVERY_ATK"], r_hpr)})'
    divine_shield_avg = f'((C{row_of["DIVINE_SHIELD"]}=TRUE)*F{row_of["DIVINE_SHIELD"]}*{buff_uptime_block(row_of["DIVINE_SHIELD"], r_ds)})'
    guardian_avg = f'((C{row_of["GUARDIAN"]}=TRUE)*F{row_of["GUARDIAN"]}*{buff_uptime_block(row_of["GUARDIAN"], r_gu)})'
    divine_blessing_avg = f'((C{row_of["DIVINE_BLESSING"]}=TRUE)*F{row_of["DIVINE_BLESSING"]}*{buff_uptime_block(row_of["DIVINE_BLESSING"], r_db)})'
    nimble_feet_avg = f'((C{row_of["NIMBLE_FEET"]}=TRUE)*F{row_of["NIMBLE_FEET"]}*{buff_uptime_block(row_of["NIMBLE_FEET"], r_nf)})'
    # Attack% bucket: every live skill/buff Attack% source sums additively into ONE combined
    # percentage before a single multiplication — matches Verification item 6.
    attack_bucket_block = f'(1+({vessel_of_light_avg}+{hp_recovery_avg}+{delta["attack_mult"]})/100)'

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

        if key == "BLAST":
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

        if key in (["BLAST"] + DAMAGE_ROW_KEYS):
            ws.cell(row=row, column=10, value=f'={ib("attack")}*(F{row}/100)')
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
            ws.cell(row=row, column=11, value=(
                f'=J{row}*(1+{ib("stat_damage")}/100)*(1+{ib("damage")}/100)'
                f'*(1+{monster_dmg_term}/100)'
                f'*(1+{ib("damage_amp")}/100)'
                f'*(5000/(6000+{ib("monster_defense")}*(1-({ib("def_pen")}+{delta["def_pen"]})/100)))'
                f'*(1+({ib("final_damage")}+{delta["final_damage"]}+{fd_bonus_ref})/100)'
                f'{maple_term}'
                f'*(1+(IF({S("Key", r)}="BLAST",{ib("basic_attack_damage")}+{delta["basic_attack_damage"]},'
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

        if key == "BLAST":
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

    ws.cell(row=s_baps, column=1, value="Blast Casts Per Second")
    ws.cell(row=s_baps, column=2, value=f'=MAX(0,{aps_ref}-{castrate_ref})')

    ws.cell(row=s_crit_damage_bonus, column=1, value="Global Critical Damage Bonus % (unused)")
    ws.cell(row=s_crit_damage_bonus, column=2, value=0)

    ws.cell(row=s_fd_bonus, column=1, value="Global Final Damage Bonus % (Divine Shield + Guardian + Divine Blessing + Greater Vessel of Light)")
    ws.cell(row=s_fd_bonus, column=2, value=f'={divine_shield_avg}+{guardian_avg}+{divine_blessing_avg}+{greater_vessel_avg}')

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
    """If a previous Paladin-DPS-Calculator.xlsx already exists at `path`, read back its Inputs
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
