#!/usr/bin/env python3
"""
Generates Dark-Knight-DPS-Calculator.xlsx: a live-formula Excel replica of a Dark Knight
skill-rotation DPS model, sibling to build_hero_workbook.py (see
/Users/yaniv/.claude/plans/so-basically-we-were-magical-iverson.md this was built from). Dark
Knight is STR-main/DEX-sub, same identity as Hero (no rename needed).

Sheets: Inputs, FactorTable, Skills, Calc, Summary, Sensitivity, CubeData, PotentialCubes.

Ground truth: fetched live from idle.maplestorywiki.net (curl, domain already allowlisted in
.claude/apple/dangerous_allowed_domains.csv) this session, cross-referenced against the actual
Aug 13 patch notes PDF. All patched Dark Knight skills (Evil Eye/Evil Eye Shock range, Lord of
Darkness, Dark Resonance, Magic Crash) are confirmed STALE on the live wiki (pre-patch
numbers/behavior) — patch deltas applied manually on top of the wiki-scraped curves.

Key mechanics/simplifications specific to this kit:
  - Dark Impale (basic attack) reuses the universal 4th-job-basic-attack constant (baseDamage
    2900, factorIndex 21) — cross-checked, resolves to the identical tuple Hero/Bowmaster/Marksman
    already established. HitsPerCast=5, bumping to 6 once Mastery Lv.136 "Dark Impale - Strike"
    unlocks (same level as Hero's own Raging Blow - Strike, confirmed independently from Dark
    Knight/Mastery, not assumed). Real Damage mastery chain (102/106/116/120/128/132, cumulative
    +10/11/12/13/14/15% — summed as DELTAS: {102:10,106:1,116:1,120:1,128:1,132:1}) and Boss
    Monster Damage chain (111/124, +10% each) both included.
  - Final Attack (Lv.50, 25% chance/35%->49% dmg, factorIndex 21/baseDamage 350) + Advanced Final
    Attack (Lv.105, +500%->900% FD, factorIndex 21/baseDamage 5000) fold into Dark Impale's own
    coefficient exactly like Hero's own Raging Blow / Bowmaster's Arrow Stream — cross-checked,
    both resolve to the IDENTICAL tuples already established cross-tree. Unlike Hero, Dark
    Knight's own Mastery table has no "Final Attack - Damage" tier at all (confirmed absent) — so
    FINAL_ATTACK_HELPER's own SkillMasteryBonus% stays 0 here, only Advanced Final Attack has a
    real mastery (Lv.113 'Advanced Final Attack - Enhance' +50%, same level as Hero's own).
  - Magic Crash: shared verbatim with Hero and Paladin (single wiki page, `/w/Magic_Crash`) —
    resolves to the IDENTICAL (48000,12) tuple Hero already established. PATCHED targets 5->9
    (effect range +50% not modeled). Mastery Lv.126 "Magic Crash - Weaken" (+15% dmg taken to
    struck targets) folded into both MasteryBossDamage%/MasteryNormalDamage% (Hero's own build
    missed this same mastery on its own Magic Crash row — not fixed there, out of scope for this
    fork, but included correctly here).
  - Maple Hero (Dark Knight): confirmed via /w/Maple_Hero_(Dark_Knight), full level 1-200 curve,
    resolves cleanly to factorIndex 23/baseDamage 400 tenths% (0% residual). Targets: Evil Eye of
    Dominant (1x share), Rush (0.75x), Evil Eye Shock (0.75x).
  - Rush: shared verbatim with Hero (confirmed identical wiki page/curve, 600%->1200%/12
    targets/22s CD) — reuses Hero's own (6000,12) tuple directly. Nimble Feet reuses the
    established cross-tree (150,0) tuple. Weapon Acceleration reuses Hero's/Bowmaster's own
    (50,22) tuple (byte-identical wiki wording). Weapon Mastery, Power Stance (Lv.125, -5% dmg
    taken/+15% FD — byte-identical wording to Hero's own) reuse Hero's own tuples directly.
    Dark Knight has NO "Physical Training" or "Endure" skill at all (confirmed absent from its
    own skill list, despite being present on Hero's) — not built here.
  - Evil Eye (Lv.35, 2nd job, JobStep=2/effective-level-capped ~100): on-summon debuff increasing
    6 nearby targets' damage taken by 15%->19.2% for its own 20s duration/30s cooldown — feeds the
    Global Monster Damage-Taken Bonus% bucket (same mechanism Hero's own Scaring Sword pioneered),
    duty-cycle averaged (no proc-chance gate, always-on while summoned). Mastery Lv.39 "Evil Eye -
    Damage Taken" +10 percentage points (real, flat add once unlocked).
  - Evil Eye Shock (Lv.40, requires Evil Eye summoned): 70%->105% damage to 6 (then 9 once Lv.75's
    Evil Eye Shock Enhancement unlocks) targets, 6 times, 18s cooldown — a normal actively-cast
    damage row, modeled as always-castable once unlocked (Evil Eye's own uptime not gating this
    row's own cast rate, a documented simplification — the "must summon Evil Eye" precondition
    isn't tracked as a live gate elsewhere in this project either). Evil Eye Shock Enhancement
    (Lv.75) is a "helper" row (own D/E/F only) adding +100%->127%(capped at level 100, own curve)
    Final Damage to Evil Eye Shock's own K-column, same Enchanted-Quiver-helper pattern from
    Bowmaster. Mastery Lv.44 "Evil Eye Shock - Damage" +50% real.
  - Evil Eye of Dominant (Lv.60, requires Evil Eye summoned, passive): "60%->84% continuous
    damage to 6 nearby targets every 1 sec" — modeled as a background DoT tied to Evil Eye's own
    cast cycle (CostsActionSlot=False, Cooldown=30s/ActiveWindow=20s matching Evil Eye's own
    duration, ICD=1s — same FP-Mage Poison-Mist-DoT-tied-to-a-parent-skill pattern). Mastery
    Lv.78 "+50% Damage" and Lv.94 "+3 targets" (6->9) both real.
  - Hex of the Evil Eye (Lv.69, requires Evil Eye summoned, passive): "+15%->18.6% Attack to
    allied players for the summoning duration" — self-inclusive ally buff (matches Hero's own
    Spirit Blade / Bishop's own precedent), tied to Evil Eye's own duty cycle. Mastery Lv.98
    "+50% additionally" (real, applied as a SkillMasteryBonus% addition). Lv.82's own "+20
    Accuracy to allies" not modeled (no Accuracy mechanic exists).
  - Lord of Darkness (Lv.72, passive proc): "when attacking, 30% chance to recover 1.5% HP and
    grant +Crit Rate/+Crit Damage for 5s" (HP recovery not modeled) — split into two rows
    (CRITRATE/CRITDMG, same BuffTargetStat-column-only-holds-one-stat reason as Hero's own Enrage
    split), modeled as ProcChance% x duty-cycle uptime (same Scaring-Sword-style simplification).
    PATCHED: duration 5->8s, Crit Rate 8->10% (curve rescaled 10/8=1.25x), Crit Damage 30->40%
    (rescaled 40/30=1.3333x), cooldown 2->3s.
  - Dark Resonance (Lv.115, active): "+30%->44.4% Attack for 20s," 35s cooldown — modeled as a
    live duty-cycled Attack% buff. PATCHED: cooldown 35->32s, new "+20% boss monster damage while
    active" clause added — folded into the Global Monster Damage-Taken Bonus% bucket (boss-only
    via monster_blend_expr), duty-cycle averaged by Dark Resonance's own uptime, alongside Evil
    Eye's own contribution. Mastery Lv.130 "Dark Resonance - Persistence" +40% duration (real,
    BuffDuration becomes 20*1.4=28s once unlocked).
  - Cross Over Chains (Lv.66, active): "+15%->18.6% Attack for 15s (if HP<=50%, Attack effect
    disappears, damage taken -10%->12% instead)," 30s cooldown — modeled assuming steady-state
    HP>50% (Attack% component only; the HP<=50% swap-to-defensive branch not modeled, matches this
    project's general non-modeling of the character's own damage-taken). Mastery Lv.73 "+100%
    additionally" to the Attack bonus (real, taken literally as +100 percentage points per this
    project's established additive-mastery convention).
  - Hyper Body (Lv.45, 2nd job, JobStep=2): "+12%->16.8% Attack for 15s, +Defense to allies" (own
    Defense-of-allies component not modeled) — live duty-cycled Attack% buff, 30s cooldown.
    Mastery Lv.49 "+50% duration."
  - Revenge of the Evil Eye (Lv.110, passive, requires Evil Eye summoned): "vengeful brand deals
    850%->1700% additional damage, 2 times" — modeled as its own damage row (Cooldown=5s,
    CostsActionSlot=False, i.e. a self-triggered proc-shaped row same treatment as Marksman's own
    Bolt Surplus). Mastery Lv.122 "+50% Damage" real. Mastery Lv.138 "Spectral Shadows" is a raw
    unevaluated wikitext formula on the live wiki (`{{#expr:2200*(1+x*0.005)}}%`) — resolved via
    the same curve-matching method already used for Marksman's Snipe-Empowered mastery this
    session (sample the formula at several levels, match against the 24-column factor table):
    resolves cleanly to factorIndex 12/baseDamage 2200 tenths% (0.44% max deviation), reusing
    Revenge's own factor-table lookup since it shares the same factorIndex.
  - Final Pact (Lv.107, passive, Magic Critical pattern): +10%->13% Final Damage (own
    death-prevention mechanic not modeled) — baked into Inputs!FINAL_DAMAGE, Sensitivity-delta
    only. Mastery Lv.118 "+100% Final Damage boost" (real, +100 percentage points, Sensitivity-
    delta only since the whole row is a passive assumed reflected in Inputs).
  - Barricade Mastery (Lv.120, Magic Critical pattern, same slot as Hero's own Combat Mastery):
    +15%->21.3%(by lvl140) Skill Damage / +20%->27.8% Max Damage Multiplier, split into two rows.
  - Gungnir's Descent (Lv.103, active): "1800%->3600% damage, 2 times," 13s cooldown — Mastery
    Lv.134 "base damage -50%, +4 strike count" is modeled as a level-gated flip of this row's own
    BaseDamage (18000->9000 tenths%) and HitsPerCast (2->6) once Lv.134 unlocks, net +50% total
    damage (6*0.5 vs 2*1.0) — same "flip fields at a level threshold" pattern used for
    Strike-mastery hit-count bumps elsewhere, just applied to both fields simultaneously.
  - Iron Wall (converts total Defense into STR at a level-scaling rate — 10% at Lv.1, applied
    via the same factorIndex 22 growth curve confirmed for Bishop's own Invincible by a real
    2-point data match, per user request to model both classes' Defense-conversion skill the same
    way; DK's own curve isn't independently confirmed yet, since the wiki's own Iron Wall page
    still shows a flat unchanging 10% at every sampled level — flagged, not yet cross-checked
    against real DK-specific in-game data — Lv.38+) is modeled live via a tracked Defense/
    Defense % Inputs pair feeding STAT_DAMAGE directly (added when the project-wide Content-Type
    feature introduced a Defense stat for the PvP opponent-defense estimate). Warrior Mastery/
    Iron Body-equivalent flat-stat passives still have no rows (zero DPS-relevant mechanic).
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
OUT_PATH = REPO / "Dark-Knight" / "Dark-Knight-DPS-Calculator.xlsx"

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
    "crit_rate": 10,
    "crit_damage": 11,
    "attack_speed": 12,
    "flat_str": 13,
    "str_pct": 14,
    "dex": 15,
    "damage": 16,
    "damage_amp": 17,
    "basic_attack_damage": 18,
    "skill_damage": 19,
    "def_pen": 20,
    "boss_damage": 21,
    "normal_damage": 22,
    "min_damage": 23,
    "max_damage": 24,
    "final_damage": 25,
    "skill_lvl_1st": 26,
    "skill_lvl_2nd": 27,
    "skill_lvl_3rd": 28,
    "skill_lvl_4th": 29,
    "skill_lvl_all": 30,
    "skill_cooldown_decrease": 33,
    "basic_attack_target_increase": 34,
    "buff_duration_increase_pct": 35,
    "companion_summon_time_increase_pct": 36,
    "boss_normal_weight_choice": 37,
    "max_enemies_hit": 38,
    "monster_type": 39,
    "chapter": 40,
    "stage": 41,
    "breakthrough_stage_index": 42,
    "monster_defense": 43,
    "fight_duration": 44,
    "defense_pct": 9,
    "breakthrough_normal_weight_pct": 45,
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


def total_defense_expr(ib_fn):
    return f'({ib_fn("defense")}*(1+{ib_fn("defense_pct")}/100))'


def iron_wall_conversion_rate_expr(ib_fn):
    lvl = ib_fn("level")
    factor_lookup = (
        f'INDEX(FactorTable!$B$2:$Y$301, MATCH(ROUND(MIN(300,MAX(1,{lvl})),0), '
        f'FactorTable!$A$2:$A$301,0), 23)'
    )
    return f'(10*{factor_lookup}/1000)'


def iron_wall_str_bonus_expr(ib_fn):
    return f'IF({ib_fn("level")}>=38,{iron_wall_conversion_rate_expr(ib_fn)}/100*{total_defense_expr(ib_fn)},0)'


def build_readme_sheet(wb):
    ws = wb.active
    ws.title = "README"
    ws["A1"] = "Dark Knight — DPS Calculator: How to Use This Workbook"
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
        "Weapon Acceleration, Weapon Mastery, Barricade Mastery, Power Stance's own Final Damage "
        "component, and Final Pact's own Final Damage component are always-on passives assumed to "
        "already be reflected in your own Inputs stat entries — only their Sensitivity marginal "
        "delta is modeled live, matching this project's established convention. Iron Wall "
        "(a level-scaling % of your total Defense as STR — 10% at Lv.1, growing with level, once "
        "Lv.38 unlocks) IS modeled live — Defense (flat) "
        "and Defense % are their own tracked Inputs, feeding STAT_DAMAGE directly, with their own "
        "Sensitivity marginal-value rows and PotentialCubes Defense % support. Warrior-Mastery-"
        "equivalent flat-stat passives have zero DPS-relevant mechanic and get no row at all. "
        "Dark Knight has NO Physical Training or Endure skill at all (confirmed absent "
        "from its own skill list, despite both being present on Hero's).",
        "Evil Eye and Dark Resonance both drive the Global Monster Damage-Taken Bonus% bucket "
        "(the mechanism Hero's own Scaring Sword pioneered) — Evil Eye's own +15%->19.2% applies "
        "to all monster types (duty-cycle averaged, always-on while summoned, no proc-chance "
        "gate), Dark Resonance's patch-added +20% applies boss-only (monster_blend_expr-gated), "
        "both summed into the same bucket.",
        "Evil Eye Shock, Evil Eye of Dominant, Hex of the Evil Eye, and Revenge of the Evil Eye "
        "all nominally require Evil Eye to be summoned first — this precondition is NOT modeled "
        "as a live gate (they're treated as always-castable once individually unlocked), a "
        "documented simplification consistent with this project not tracking buff-precondition "
        "chains elsewhere either.",
        "Evil Eye of Dominant is modeled as a background DoT tied to Evil Eye's own cast cycle "
        "(Cooldown=30s/ActiveWindow=20s matching Evil Eye's own duration, ICD=1s) — same pattern "
        "as FP-Mage's own Poison Mist fog DoT tied to its parent skill.",
        "Lord of Darkness is split into two rows (Crit Rate half, Crit Damage half) since this "
        "schema's BuffTargetStat column only holds one stat per row — same reason Hero's own "
        "Enrage is split. Both modeled as ProcChance% x duty-cycle uptime (Scaring-Sword-style "
        "simplification), not an exact per-attack RNG state machine. Its own HP-recovery "
        "component is not modeled.",
        "Cross Over Chains and Gungnir's Descent both have an HP-conditional or mastery-driven "
        "mechanic: Cross Over Chains assumes steady-state HP>50% (its own Attack% buff only, not "
        "the HP<=50% damage-taken-reduction swap, still an unmodeled gap); Gungnir's Descent's "
        "own Lv.134 mastery ('base damage -50%, +4 strike count') is modeled directly as a "
        "level-gated flip of its own BaseDamage/HitsPerCast fields (net +50% total damage), not "
        "left unmodeled.",
        "Revenge of the Evil Eye's own Lv.138 'Spectral Shadows' mastery is a raw unevaluated "
        "wikitext formula on the live wiki page ({{#expr:2200*(1+x*0.005)}}%) — resolved via the "
        "same curve-matching method already used for Marksman's own Snipe-Empowered mastery this "
        "session (sample the formula at several levels, match against the 24-column factor "
        "table): resolves cleanly to factorIndex 12/baseDamage 2200 tenths%, reusing Revenge's "
        "own factor lookup since it shares the same factorIndex.",
        "Dark Impale (basic attack) reuses the universal 4th-job-basic-attack constant "
        "(baseDamage 2900, factorIndex 21) confirmed identical across every class in this "
        "project. Final Attack + Advanced Final Attack fold into its own coefficient exactly "
        "like Hero's own Raging Blow / Bowmaster's own Arrow Stream — both resolve to the "
        "identical tuples already established, confirming they're genuinely the same cross-tree "
        "shared skills. Unlike Hero, this class's own Mastery table has no 'Final Attack - "
        "Damage' tier at all (confirmed absent), so that helper row's own SkillMasteryBonus% "
        "stays 0 here.",
        "Magic Crash is shared verbatim with Hero and Paladin (single wiki page) — patched "
        "targets 5->9 (effect range +50% not modeled). Its own Lv.126 'Magic Crash - Weaken' "
        "mastery (+15% damage taken to struck targets) is included here on both "
        "MasteryBossDamage%/MasteryNormalDamage% — Hero's own build happened to miss this same "
        "mastery on its own Magic Crash row, not fixed there (out of scope for this fork).",
        "Content Type (Inputs) picks what you're fighting — Chapter Boss/Breakthrough/PvP/EXP "
        "Dungeon/Equipment Dungeon/Weapon Dungeon/Enhancement Dungeon/Hero Dungeon/World Boss/"
        "Chapter Hunt — and Monster Defense and Fixed Fight Duration are both auto-computed from "
        "it (plus Chapter/Stage for the chapter- and dungeon-based types); PvP still forces its "
        "own fixed 15-second window and uses your own Defense stat as the opponent's Defense "
        "estimate. See README.md's 'Content Type' section for the exact formulas.",
        "Not modeled (out of scope): all forms of crowd control (Evil Eye Shock stun), Accuracy, "
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
    ws["A1"] = "Dark Knight — DPS Calculator Inputs"
    ws["A1"].font = Font(bold=True, size=14)

    rows = [
        ("level", "Character Level", 200),
        ("content_type", "Content Type", "Chapter Boss"),
        ("chapter_stage", "Chapter-Stage — e.g. '28-9' for Chapter Boss/Breakthrough/Chapter Hunt "
                          "(chapter-substage, the boss chapter number alone also works), or just the "
                          "stage number (e.g. '80') for Weapon/Enhancement/EXP/Equipment/Hero Dungeon", "28-9"),
        ("flat_attack", "Flat ATTACK", 10000),
        ("attack_pct", "ATTACK %", 0),
        ("defense", "Defense (flat) — your own DEF stat; Iron Wall converts a level-scaling % "
                    "(10% at Lv.1, growing with level) of it into STR, "
                    "and PvP assumes the opponent has the same total Defense as you", 0),
        ("defense_pct", "Defense % (Iron Wall converts total Defense, incl. this %, into STR, "
                    "at a level-scaling rate)", 0),
        ("crit_rate", "CRIT_RATE %", 0),
        ("crit_damage", "CRIT_DAMAGE %", 0),
        ("attack_speed", "ATTACK_SPEED % (base, excludes Weapon Acceleration)", 0),
        ("flat_str", "Flat STR", 0),
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

    ws.cell(row=32, column=1, value="Additional Bonuses").font = SECTION_FONT
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
            f'({IB("defense")}*(1+{IB("defense_pct")}/100)))))))))'
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


def monster_blend_expr(monster_type_ref, w_ref, boss_expr, normal_expr, pvp_expr):
    return f'IF({monster_type_ref}="pvp",{pvp_expr},(1-{w_ref})*({boss_expr})+{w_ref}*({normal_expr}))'


def boss_normal_dps_split_exprs(prefix_expr, monster_type_ref, boss_dmg_pct_expr,
                                 normal_dmg_pct_expr, normal_targets_ref, max_enemies_ref):
    """Splits a row's DPS into independent boss-only and normal-only values, given `prefix_expr`
    (the H*N*rate*(extra multipliers) part shared by both). Each branch gets its own full
    (1+damage%/100)*target_count treatment; blended into the real Total DPS as a plain dollar sum
    (correct there), but Sensitivity blends the two branches' RATIOS (new/baseline) instead, time-
    weighted — a dollar blend would let a stat's reported value be dominated by whichever branch
    happens to hit more targets, regardless of how much combat time is spent there."""
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
    "DARK_IMPALE", "FINAL_ATTACK_HELPER", "ADVANCED_FINAL_ATTACK_HELPER",
    "MAGIC_CRASH", "GUNGNIRS_DESCENT",
    "EVIL_EYE_SHOCK", "EVIL_EYE_SHOCK_ENH", "EVIL_EYE_OF_DOMINANT", "REVENGE_OF_THE_EVIL_EYE",
    "MAPLE_HERO_HELPER", "RUSH",
    "HEX_OF_THE_EVIL_EYE", "DARK_RESONANCE", "CROSS_OVER_CHAINS", "HYPER_BODY", "EVIL_EYE",
    "LORD_OF_DARKNESS_CRITRATE", "LORD_OF_DARKNESS_CRITDMG",
    "NIMBLE_FEET",
    "WEAPON_ACCELERATION", "WEAPON_MASTERY",
    "BARRICADE_SKILL_DMG", "BARRICADE_MAXDMG", "POWER_STANCE_FD", "FINAL_PACT",
]
ROW = {key: i for i, key in enumerate(ROW_ORDER, start=2)}
LAST_ROW = 1 + len(ROW_ORDER)

# ---------------------------------------------------------------------------
# Summary-sheet row layout — fixed constants, defined ahead of SKILL_ROWS (module-level list
# literal evaluated at import time) so any row needing to self-reference one of these can.
# ---------------------------------------------------------------------------
R_TOTAL = 3
SUMMARY_BREAKDOWN_HEADER_ROW = 6
R_AVGBUFF = 57                      # Attack% bucket (Hex/Dark Resonance/Cross Over Chains/Hyper Body)
R_CRIT_RATE_BONUS = 58              # Lord of Darkness (Crit Rate half), proc x duty-cycle
R_MONSTER_DMG_BONUS = 59            # Evil Eye (all types) + Dark Resonance (boss-only)
R_AS_BONUS = 60                     # unused placeholder (no live AS-buff source exists)
R_APS = 61                          # Actions Per Second
R_CASTRATE = 62                     # Skill + buff cast rate (subtracted from Dark Impale)
R_BAPS = 63                         # Dark Impale (basic attack) Casts Per Second
R_CRIT_DAMAGE_BONUS = 64            # Lord of Darkness (Crit Damage half), proc x duty-cycle
R_FD_BONUS = 65                     # unused placeholder (no live Final-Damage-buff source exists)
R_DARK_IMPALE_DPS = 66
R_STARTUP_TIME = 67                 # Buff-Casting Startup Delay (s, fixed-duration only)
R_BOSS_ONLY_TOTAL = 68               # Total DPS if every hit were against a boss (Breakthrough Sensitivity baseline)
R_NORMAL_ONLY_TOTAL = 69             # Total DPS if every hit were against normal monsters (Breakthrough Sensitivity baseline)

# Rows (BuffDuration(s) > 0) exempt from the buff-casting startup delay's reduction of their own
# CastsInFight — these ARE the buffs (whether actively cast or passively triggered), not the
# damage rotation waiting on them, so they keep the raw fight duration. Only actively-cast buffs
# (CostsActionSlot=TRUE) contribute to the delay itself (see buff_cast_startup_time_expr's own
# Skills-sheet filter).
BUFF_ROW_KEYS = [
    "HEX_OF_THE_EVIL_EYE", "DARK_RESONANCE", "CROSS_OVER_CHAINS", "HYPER_BODY", "EVIL_EYE",
    "LORD_OF_DARKNESS_CRITRATE", "LORD_OF_DARKNESS_CRITDMG", "NIMBLE_FEET",
]

UNLOCK_LEVEL = {
    "DARK_IMPALE": 100,
    "FINAL_ATTACK_HELPER": 50,
    "ADVANCED_FINAL_ATTACK_HELPER": 105,
    "MAGIC_CRASH": 117,
    "GUNGNIRS_DESCENT": 103,
    "EVIL_EYE_SHOCK": 40,
    "EVIL_EYE_SHOCK_ENH": 75,
    "EVIL_EYE_OF_DOMINANT": 60,
    "REVENGE_OF_THE_EVIL_EYE": 110,
    "MAPLE_HERO_HELPER": 100,
    "RUSH": 63,
    "HEX_OF_THE_EVIL_EYE": 69,
    "DARK_RESONANCE": 115,
    "CROSS_OVER_CHAINS": 66,
    "HYPER_BODY": 45,
    "EVIL_EYE": 35,
    "LORD_OF_DARKNESS_CRITRATE": 72,
    "LORD_OF_DARKNESS_CRITDMG": 72,
    "WEAPON_ACCELERATION": 33,
    "WEAPON_MASTERY": 43,
    "BARRICADE_SKILL_DMG": 120,
    "BARRICADE_MAXDMG": 120,
    "POWER_STANCE_FD": 125,
    "FINAL_PACT": 107,
    # NIMBLE_FEET: no threshold (shared Explorer skill, level 0) — stays unconditionally unlocked.
}


def unlock_expr(key):
    level = UNLOCK_LEVEL.get(key)
    return "=TRUE" if level is None else f"={IB('level')}>={level}"


# Maple Hero (Lv.100) — confirmed live from idle.maplestorywiki.net/w/Maple_Hero_(Dark_Knight)
# this session: Evil Eye of Dominant 1x share (own curve, 40%->312%), Rush 0.75x, Evil Eye Shock
# 0.75x — resolves cleanly to factorIndex 23/baseDamage 400 tenths% (0% residual).
MAPLE_HERO_RATIOS = {
    "EVIL_EYE_OF_DOMINANT": 40 / 40,
    "RUSH": 30 / 40,
    "EVIL_EYE_SHOCK": 30 / 40,
}

# (key, name, jobstep, cooldown, costsAction, actionsPerCast, hits, icd, window, chance, rolls,
#  baseDamage, factorIndex, scales, skillMasteryBonusPct, masteryBossDmgPct, masteryNormalDmgPct,
#  normalMonsterTargets, buffTarget, buffDuration, mapleBase, mapleFactor, note)
SKILL_ROWS = [
    ("DARK_IMPALE", "Dark Impale", 4, "", False, 1,
     f'=IF({IB("level")}>=136,6,5)', 0, 0, 100, 1,
     2900, 21, True,
     f"=Calc!F{{FINAL_ATTACK_HELPER}}*IF(Calc!C{{FINAL_ATTACK_HELPER}}=TRUE,1,0)/100"
     f"*(1+Calc!F{{ADVANCED_FINAL_ATTACK_HELPER}}*IF(Calc!C{{ADVANCED_FINAL_ATTACK_HELPER}}=TRUE,1,0)/100)"
     f"*25"
     f"+{level_gated_sum_raw(IB('level'), {102: 10, 106: 1, 116: 1, 120: 1, 128: 1, 132: 1}).replace('{', '{{').replace('}', '}}')}",
     level_gated_sum(IB("level"), {111: 10, 124: 10}), 0,
     f'=6+{IB("basic_attack_target_increase")}', "", 0, "", "",
     "4th-job basic-attack effect (supersedes Slash Blast/Spear Sweep/La Mancha Spear, confirmed "
     "identical wiki wording — 290% damage to 6 target(s) in front 5 time(s) — to every other "
     "class's own 4th-job basic attack). factorIndex 21, baseDamage 2900 tenths%. HitsPerCast=5, "
     "bumping to 6 once Mastery Lv.136 'Dark Impale - Strike' unlocks (same level as Hero's own "
     "equivalent, confirmed independently from Dark Knight/Mastery). SkillMasteryBonus% is Final "
     "Attack + Advanced Final Attack's own combined steady-state contribution (same folding "
     "mechanism as Hero's own Raging Blow) PLUS the real Dark Impale - Damage mastery chain "
     "(102/106/116/120/128/132, cumulative +10/11/12/13/14/15% — summed as DELTAS, not the raw "
     "displayed values). MasteryBossDamage% is the real 2-tier Dark Impale - Boss Monster Damage "
     "chain (111/124, +10% each, +20% total)."),
    ("FINAL_ATTACK_HELPER", "Final Attack (helper)", 2, "", False, 1, 1, 0, 0, 100, 1,
     350, 21, True,
     0, 0, 0, 0, "", 0, "", "",
     "Helper row only — feeds Dark Impale's own coefficient. 25% chance, 35%->49% additional "
     "damage (levels 1-100), factorIndex 21/baseDamage 350 tenths% — resolves to the IDENTICAL "
     "tuple Hero's/Bowmaster's own Final Attack helper uses, confirming this is genuinely the "
     "same cross-tree shared skill. Unlike Hero, Dark Knight's own Mastery table has NO 'Final "
     "Attack - Damage' tier at all (confirmed absent) — SkillMasteryBonus% stays 0 here."),
    ("ADVANCED_FINAL_ATTACK_HELPER", "Advanced Final Attack (helper)", 4, "", False, 1, 1, 0, 0, 100, 1,
     5000, 21, True,
     level_gated_sum(IB("level"), {113: 50}), 0, 0, 0, "", 0, "", "",
     "Helper row only — feeds Dark Impale's own coefficient (Final Attack's own Final Damage "
     "bonus). +500%->900% FD (levels 1-200), factorIndex 21/baseDamage 5000 tenths% — resolves "
     "to the IDENTICAL tuple Hero's/Bowmaster's own Advanced Final Attack helper uses. Mastery "
     "Lv.113 'Advanced Final Attack - Enhance' +50% (real SkillMasteryBonus%, same level as "
     "Hero's own)."),
    ("MAGIC_CRASH", "Magic Crash", 4, 28, True, 1, 1, 0, 0, 100, 1,
     48000, 12, True,
     level_gated_sum(IB("level"), {126: 15}),
     level_gated_sum(IB("level"), {126: 15}),
     level_gated_sum(IB("level"), {126: 15}),
     f'=5+IF({IB("level")}>=100,4,0)', "", 0, "", "",
     "Summons a rock at the target's location, removing 1 buff and dealing 4800%->9600% damage "
     "to 5 nearby target(s), 1 time. factorIndex 12, baseDamage 48000 tenths% — resolves to the "
     "IDENTICAL tuple Hero's own Magic Crash uses (shared verbatim, single wiki page, "
     "/w/Magic_Crash). PATCHED: targets 5->9 (effect range +50% not modeled, no such mechanic "
     "exists). Mastery Lv.126 'Magic Crash - Weaken' (+15% damage taken to struck targets) baked "
     "into SkillMasteryBonus%/MasteryBossDamage%/MasteryNormalDamage% alike (a real mastery Hero's "
     "own build happened to miss on its own Magic Crash row — not fixed there, out of scope for "
     "this fork)."),
    ("GUNGNIRS_DESCENT", "Gungnir's Descent", 4, 13, True, 1,
     f'=IF({IB("level")}>=134,6,2)', 0, 0, 100, 1,
     f'=IF({IB("level")}>=134,9000,18000)', 12, True,
     0, 0, 0, 1, "", 0, "", "",
     "Throws a mythical spear at the target to deal 1800%->3600% damage, 2 times. factorIndex 12, "
     "baseDamage 18000 tenths%, 13s cooldown. Single-target (NormalMonsterTargets=1). Mastery "
     "Lv.134 'Gungnir's Descent - Strike' ('base damage -50%, +4 strike count') is modeled "
     "directly as a level-gated rebalance of this row's own BaseDamage (18000->9000 tenths%) "
     "and HitsPerCast (2->6) once Lv.134 unlocks — net +50% total damage (6*0.5 vs 2*1.0), "
     "same 'flip two fields at a level threshold' pattern already used elsewhere in this "
     "project for Strike-mastery hit-count bumps, just applied to both BaseDamage and "
     "HitsPerCast simultaneously instead of HitsPerCast alone. An earlier version of this row "
     "left this mastery completely unmodeled, documented as an under-estimate at high level — "
     "fixed."),
    ("EVIL_EYE_SHOCK", "Evil Eye Shock", 2, 18, True, 1, 6, 0, 0, 100, 1,
     700, 12, True,
     f'={level_gated_sum_raw(IB("level"), {44: 50})}'
     f'+IF({IB("level")}>=75,Calc!F{ROW["EVIL_EYE_SHOCK_ENH"]}*IF(Calc!C{ROW["EVIL_EYE_SHOCK_ENH"]}=TRUE,1,0),0)',
     0, 0,
     f'=6+IF({IB("level")}>=75,3,0)', "", 0, 400, 23,
     "[Must Summon Evil Eye — precondition not modeled as a live gate, treated as always-"
     "castable once unlocked] The Evil Eye attacks 6 (then 9 once Lv.75's Evil Eye Shock "
     "Enhancement unlocks) nearby target(s), dealing 70%->105% damage (levels 1-100, 2nd-job "
     "capped), 6 times, 18s cooldown, stun 1.5s not modeled. factorIndex 12, baseDamage 700 "
     "tenths%. Mastery Lv.44 'Evil Eye Shock - Damage' +50% real. Evil Eye Shock Enhancement's "
     "own +100%->127% Final Damage curve is folded directly into this row's own "
     "SkillMasteryBonus% as an additive coefficient bonus (a documented approximation — true "
     "Final Damage multiplies after the crit/defense pipeline, this applies it pre-pipeline "
     "instead — same simplification tier as folding Final Attack's own proc into a basic "
     "attack's coefficient elsewhere in this project). Maple Hero target (0.75x share) — see "
     "MAPLE_HERO_RATIOS."),
    ("EVIL_EYE_SHOCK_ENH", "Evil Eye Shock Enhancement (helper)", 3, "", False, 1, 1, 0, 0, 100, 1,
     1000, 22, True,
     0, 0, 0, 0, "", 0, "", "",
     "Helper row only (no independent O-column DPS) — feeds Evil Eye Shock's own K-column extra "
     "Final Damage term (target-count bump baked directly into EVIL_EYE_SHOCK's own "
     "NormalMonsterTargets formula instead). 'Target count changes to 9, Final Damage +100%->"
     "127%' (levels 1-100, own curve). factorIndex 22, baseDamage 1000 tenths%."),
    ("EVIL_EYE_OF_DOMINANT", "Evil Eye of Dominant", 3, 30, False, 1, 1, 1, 20, 100, 1,
     600, 21, True,
     level_gated_sum(IB("level"), {78: 50}), 0, 0,
     f'=6+IF({IB("level")}>=94,3,0)', "", 0, 400, 23,
     "[Must Summon Evil Eye] Background DoT tied to Evil Eye's own cast cycle (CostsActionSlot="
     "False, Cooldown=30s/ActiveWindow=20s matching Evil Eye's own duration, ICD=1s — EffectiveHits "
     "= ActiveWindow/ICD = 20 ticks/cast, same FP-Mage Poison-Mist-DoT-tied-to-a-parent-skill "
     "pattern): 'deals 60%->84% continuous damage to 6 nearby targets every 1 sec' (levels "
     "1-200). factorIndex 21, baseDamage 600 tenths%. Mastery Lv.78 'Evil Eye of Dominant - "
     "Damage' +50% and Lv.94 'Evil Eye of Dominant - Target' +3 (6->9) both real. Maple Hero "
     "target (1x share, biggest) — see MAPLE_HERO_RATIOS."),
    ("REVENGE_OF_THE_EVIL_EYE", "Revenge of the Evil Eye", 4, 5, False, 1, 2, 0, 0, 100, 1,
     8500, 12, True,
     f'={level_gated_sum_raw(IB("level"), {122: 50})}'
     f'+IF({IB("level")}>=138,220*(Calc!E{ROW["REVENGE_OF_THE_EVIL_EYE"]}/1000),0)',
     0, 0, 1, "", 0, "", "",
     "[Must Summon Evil Eye] Self-triggered proc-shaped row (Cooldown=5s, CostsActionSlot=False "
     "— same treatment as Marksman's own Bolt Surplus): 'engraves a vengeful brand dealing "
     "850%->1700% additional damage, 2 times' (levels 1-200). factorIndex 12, baseDamage 8500 "
     "tenths%. Mastery Lv.122 'Revenge of the Evil Eye - Damage' +50% real. Mastery Lv.138 "
     "'Spectral Shadows' is a raw unevaluated wikitext formula on the live wiki page "
     "({{#expr:2200*(1+x*0.005)}}%) — resolved via the same curve-matching method already used "
     "for Marksman's own Snipe-Empowered mastery this session (sample the formula at several "
     "levels treating x=character level, match against the 24-column factor table): resolves "
     "cleanly to factorIndex 12/baseDamage 2200 tenths% (0.44% max deviation) — since it shares "
     "the SAME factorIndex as this row's own base curve, it reuses this row's own Calc!E factor "
     "lookup directly rather than needing a separate FactorTable lookup (same trick as Snipe's "
     "own Empowered mastery)."),
    ("MAPLE_HERO_HELPER", "Maple Hero (helper)", 4, "", False, 1, 1, 0, 0, 100, 1,
     400, 23, True,
     0, 0, 0, 0, "", 0, "", "",
     "Shared ratio-feeder row (see MAPLE_HERO_RATIOS) for Evil Eye of Dominant/Rush/Evil Eye "
     "Shock's own Final Damage chains — mirrors Hero/Shadower/Bowmaster's own Maple Hero "
     "mechanism. Confirmed via idle.maplestorywiki.net/w/Maple_Hero_(Dark_Knight) (full level "
     "1-200 curve, resolves cleanly to factorIndex 23/baseDamage 400 tenths%, 0% residual, same "
     "'80%-growth-reduction after Lv.120' kink already confirmed on Hero/Bowmaster's own Maple "
     "Hero curves). No independent DPS row of its own (Calc columns J-N blank/0, only D/E/F "
     "computed, read directly by each target row's own K-column formula)."),
    ("RUSH", "Rush", 3, 22, True, 1, 1, 0, 0, 100, 1,
     6000, 12, True,
     0, 0, 0, 12, "", 0, 300, 23,
     "Charges to the front to deal 600%->1200% damage to 12 target(s) (stun 2.5s not modeled). "
     "factorIndex 12, baseDamage 6000 tenths%, 22s cooldown — resolves to the IDENTICAL tuple "
     "Hero's own Rush uses (shared verbatim, confirmed identical wiki page). Not patched "
     "(Mastery Lv.68/90 own damage/cooldown tiers not separately modeled here, same treatment as "
     "Hero's own Rush row — kept consistent for this genuinely shared skill). Maple Hero target "
     "(0.75x share) — see MAPLE_HERO_RATIOS."),
    ("HEX_OF_THE_EVIL_EYE", "Hex of the Evil Eye", 3, 30, False, 1, 1, 0, 0, 100, 1,
     150, 22, True,
     level_gated_sum(IB("level"), {98: 50}), 0, 0, 0, "ATTACK", 20, "", "",
     "[Must Summon Evil Eye] Self-inclusive ally buff (matches Hero's own Spirit Blade / "
     "Bishop's own 'allied players' precedent), tied to Evil Eye's own duty cycle (Cooldown=30s/"
     "BuffDuration=20s matching Evil Eye's own): '+15%->18.6% Attack to allied players for the "
     "summoning duration' (levels 1-100, 3rd-job capped). factorIndex 22, baseDamage 150 "
     "tenths%. Mastery Lv.98 'Hex of the Evil Eye - Attack' +50% additionally, real. Lv.82's own "
     "'+20 Accuracy to allies' not modeled (no Accuracy mechanic exists)."),
    ("DARK_RESONANCE", "Dark Resonance", 4, 32, True, 1, 1, 0, 0, 100, 1,
     300, 21, True,
     0, 0, 0, 0, "ATTACK",
     f'=IF({IB("level")}>=130,20*1.4,20)', "", "",
     "'Unlocks the power of pure darkness to increase Attack by 30%->44.4% for 20s' (levels "
     "1-200). factorIndex 21, baseDamage 300 tenths% (curve rescaled 300/240=1.25x from the "
     "pre-patch 8%-at-Lv1 baseline... actually: PATCHED level-1 Attack 30%->still 30% per the "
     "patch notes, own cooldown 35->32s — this row models the CURRENT/patched Attack% curve "
     "directly since the wiki's own level-1 value (30%) already matched the patch notes' stated "
     "Attack% exactly, only cooldown/boss-bonus needed patching). PATCHED: cooldown 35->32s "
     "(baked into Cooldown(s)), new '+20% boss monster damage while active' clause added — folded "
     "into the Global Monster Damage-Taken Bonus% bucket (boss-only via monster_blend_expr), "
     "duty-cycle averaged by this row's own uptime, alongside Evil Eye's own contribution (see "
     "Summary sheet). Mastery Lv.130 'Dark Resonance - Persistence' +40% duration (real, "
     "BuffDuration becomes 20*1.4=28s once unlocked)."),
    ("CROSS_OVER_CHAINS", "Cross Over Chains", 3, 30, True, 1, 1, 0, 0, 100, 1,
     150, 21, True,
     level_gated_sum(IB("level"), {73: 100}), 0, 0, 0, "ATTACK", 15, "", "",
     "'Increases Attack by 15%->18.6% for 15 sec (levels 1-60, own curve). If current HP is 50% "
     "or lower, the Attack increase effect disappears and damage taken is decreased by 10%->12% "
     "instead' — modeled assuming steady-state HP>50% (Attack% component only; the HP<=50% swap-"
     "to-defensive branch not modeled, matches this project's general non-modeling of the "
     "character's own damage-taken). factorIndex 21, baseDamage 150 tenths%, 30s cooldown. "
     "Mastery Lv.73 'Cross Over Chains - Attack' +100% additionally (real, taken literally as "
     "+100 percentage points per this project's established additive-mastery convention)."),
    ("HYPER_BODY", "Hyper Body", 2, 30, True, 1, 1, 0, 0, 100, 1,
     120, 21, True,
     level_gated_sum(IB("level"), {49: 50}), 0, 0, 0, "ATTACK", 15, "", "",
     "'Increases Attack by 12%->16.8% for 15 sec (levels 1-100, 2nd-job capped), and the Defense "
     "of allied players by 15%->21%' (Defense-of-allies component not modeled — no Defense "
     "mechanic exists). factorIndex 21, baseDamage 120 tenths%, 30s cooldown. Mastery Lv.49 "
     "'Hyper Body - Persistence' +50% duration (real, applied as a SkillMasteryBonus%-style "
     "percentage addition since this schema has no separate duration-mastery mechanism — treated "
     "as a documented approximation)."),
    ("EVIL_EYE", "Evil Eye", 2, 30, True, 1, 1, 0, 0, 100, 1,
     150, 21, True,
     level_gated_sum(IB("level"), {39: 10}), 0, 0, 0, "MONSTER_DMG", 20, "", "",
     "'Summons Evil Eye. Evil Eye follows you for 20 sec and increases the damage taken by 6 "
     "nearby target(s) by 15%->19.2%' (levels 1-100, 2nd-job capped) — drives the Global Monster "
     "Damage-Taken Bonus% bucket (Hero's own Scaring-Sword-pioneered mechanism), duty-cycle "
     "averaged, no proc-chance gate (always-on while summoned, unlike Scaring Sword's proc). "
     "factorIndex 21, baseDamage 150 tenths%, 30s cooldown. Mastery Lv.39 'Evil Eye - Damage "
     "Taken' +10 percentage points, real, flat add once unlocked."),
    ("LORD_OF_DARKNESS_CRITRATE", "Lord of Darkness (Crit Rate half)", 3, 3, False, 1, 1, 0, 0, 30, 1,
     100, 22, True,
     0, 0, 0, 0, "CRIT_RATE", 8, "", "",
     "On-attack proc (30% chance, own internal cooldown) granting +Crit Rate/+Crit Damage for a "
     "duration (HP-recovery component not modeled) — split into two rows since this schema's "
     "BuffTargetStat column only holds one stat per row (same reason as Hero's own Enrage split). "
     "Modeled as ProcChance% x duty-cycle uptime (Scaring-Sword-style simplification), not an "
     "exact per-attack RNG state machine. PATCHED: duration 5->8s (baked into BuffDuration(s)), "
     "Crit Rate 8%->10% (curve rescaled 10/8=1.25x, giving the 100 stored here vs. the pre-patch "
     "curve's own 80), cooldown 2->3s (baked into Cooldown(s))."),
    ("LORD_OF_DARKNESS_CRITDMG", "Lord of Darkness (Crit Damage half)", 3, 3, False, 1, 1, 0, 0, 30, 1,
     400, 22, True,
     0, 0, 0, 0, "CRIT_DAMAGE", 8, "", "",
     "Crit Damage half of Lord of Darkness — same proc-chance/cooldown/duration as "
     "LORD_OF_DARKNESS_CRITRATE. PATCHED: Crit Damage 30%->40% (curve rescaled 40/30=1.3333x, "
     "giving the 400 stored here vs. the pre-patch curve's own 300)."),
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
     "Level Bonus delta. Reuses Hero's/Bowmaster's own tuple directly (shared-value-different-"
     "key, byte-identical wiki wording — '+5% Attack Speed'). factorIndex 22, baseDamage 50 "
     "tenths% (5%->6.5%, levels 1-100)."),
    ("WEAPON_MASTERY", "Weapon Mastery", 2, "", False, 1, 1, 0, 0, 100, 1,
     150, 22, True,
     0, 0, 0, 0, "MIN_DAMAGE", 0, "", "",
     "Magic Critical pattern — already baked into Inputs!MIN_DAMAGE%; feeds the 2nd-Job Skill "
     "Level Bonus delta. factorIndex 22, baseDamage 150 tenths% (15%->19.5%, levels 1-100)."),
    ("BARRICADE_SKILL_DMG", "Barricade Mastery (Skill Damage)", 4, "", False, 1, 1, 0, 0, 100, 1,
     150, 22, True,
     0, 0, 0, 0, "SKILL_DAMAGE", 0, "", "",
     "Magic Critical pattern — already baked into Inputs!SKILL_DAMAGE%; feeds the 4th-Job Skill "
     "Level Bonus delta (Skill Damage side). Same slot as Hero's own Combat Mastery, just "
     "renamed. factorIndex 22, baseDamage 150 tenths% (15%->21.3% at Lv140, own curve)."),
    ("BARRICADE_MAXDMG", "Barricade Mastery (Max Damage Multiplier)", 4, "", False, 1, 1, 0, 0, 100, 1,
     200, 22, True,
     0, 0, 0, 0, "MAX_DAMAGE", 0, "", "",
     "Same skill as Barricade Mastery (Skill Damage) above, +20%->27.8% Max Damage Multiplier "
     "(at Lv140, own curve). Magic Critical pattern — already baked into Inputs!MAX_DAMAGE%; "
     "feeds the 4th-Job Skill Level Bonus delta (Max Damage Multiplier side). factorIndex 22, "
     "baseDamage 200 tenths%."),
    ("POWER_STANCE_FD", "Power Stance (Final Damage)", 4, "", False, 1, 1, 0, 0, 100, 1,
     150, 22, True,
     0, 0, 0, 0, "FINAL_DAMAGE", 0, "", "",
     "Own damage-taken-reduction component (5%->8%) not modeled (no such mechanic exists). "
     "Byte-identical wiki wording to Hero's own Power Stance — reuses that tuple directly. Magic "
     "Critical pattern — already baked into Inputs!FINAL_DAMAGE%; feeds the 4th-Job Skill Level "
     "Bonus delta. factorIndex 22, baseDamage 150 tenths% (15%->24%, levels 1-200)."),
    ("FINAL_PACT", "Final Pact", 4, "", False, 1, 1, 0, 0, 100, 1,
     100, 22, True,
     level_gated_sum(IB("level"), {118: 100}), 0, 0, 0, "FINAL_DAMAGE", 0, "", "",
     "'Increases Final Damage by 10%->13% (levels 1-200, own curve). When HP falls below 1%, "
     "the Final Damage increase disappears and you become immune to damage for 2 sec (once per "
     "battle, prevents death)' — death-prevention mechanic not modeled. Magic Critical pattern "
     "— already baked into Inputs!FINAL_DAMAGE%; feeds the 4th-Job Skill Level Bonus delta "
     "(Sensitivity-only, same as every other Magic-Critical-pattern row). factorIndex 22, "
     "baseDamage 100 tenths%. Mastery Lv.118 'Final Pact - Recovery' +100% Final Damage boost "
     "(real, +100 percentage points, Sensitivity-delta only since the whole row is a passive "
     "assumed reflected in Inputs)."),
]

# Resolve the {ROW_KEY} placeholders in DARK_IMPALE's own SkillMasteryBonus% formula (Python
# f-string braces collide with Excel's own {..} SUMPRODUCT array-constant syntax elsewhere in
# this file, so this one row's cross-references are patched in after the fact instead).
_raging_blow_row = [list(row) for row in SKILL_ROWS if row[0] == "DARK_IMPALE"][0]
_raging_blow_row[14] = _raging_blow_row[14].format(
    FINAL_ATTACK_HELPER=ROW["FINAL_ATTACK_HELPER"],
    ADVANCED_FINAL_ATTACK_HELPER=ROW["ADVANCED_FINAL_ATTACK_HELPER"],
)
SKILL_ROWS = [tuple(_raging_blow_row) if row[0] == "DARK_IMPALE" else row for row in SKILL_ROWS]

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
    "MAGIC_CRASH", "GUNGNIRS_DESCENT", "EVIL_EYE_SHOCK", "EVIL_EYE_OF_DOMINANT",
    "REVENGE_OF_THE_EVIL_EYE", "RUSH",
]
ATTACK_BUFF_ROW_KEYS = ["HEX_OF_THE_EVIL_EYE", "DARK_RESONANCE", "CROSS_OVER_CHAINS", "HYPER_BODY"]
PASSIVE_MULT_ROW_KEYS = [
    "WEAPON_ACCELERATION", "WEAPON_MASTERY",
    "BARRICADE_SKILL_DMG", "BARRICADE_MAXDMG", "POWER_STANCE_FD", "FINAL_PACT",
]
HELPER_ROW_KEYS = [
    "FINAL_ATTACK_HELPER", "ADVANCED_FINAL_ATTACK_HELPER", "MAPLE_HERO_HELPER", "EVIL_EYE_SHOCK_ENH",
]
MAPLE_HERO_ROW_KEYS = ["MAPLE_HERO_HELPER"]
DAMAGE_DEALING_KEYS = ["DARK_IMPALE"] + DAMAGE_ROW_KEYS

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
            for col in (7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19):
                ws.cell(row=r, column=col, value=("1" if col == 9 else ""))
            continue

        if key == "DARK_IMPALE":
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

        if key in (["DARK_IMPALE"] + DAMAGE_ROW_KEYS):
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
                f'*(1+(IF({S("Key", r)}="DARK_IMPALE",{IB("basic_attack_damage")},{IB("skill_damage")}))/100)'
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

        if key == "DARK_IMPALE":
            prefix = f"{S('HitsPerCast', r)}*N{r}*Summary!$B${R_BAPS}"
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
    ws["A1"] = "Dark Knight — DPS Summary"
    ws["A1"].font = Font(bold=True, size=14)

    ws.cell(row=DERIVED_HEADER_ROW, column=1, value="Derived Values (read-only, computed from Inputs)").font = SECTION_FONT
    ws.cell(row=D_ATTACK, column=1, value="ATTACK (= Flat ATTACK x (1+ATTACK%/100))")
    ws.cell(row=D_ATTACK, column=2, value=f'={IB("flat_attack")}*(1+{IB("attack_pct")}/100)')

    ws.cell(row=D_STAT_DAMAGE, column=1, value="STAT_DAMAGE % (= 1% of total STR [incl. Iron Wall's Defense-> STR] + 0.25% of DEX)")
    ws.cell(
        row=D_STAT_DAMAGE, column=2,
        value=f'=(({IB("flat_str")}+{iron_wall_str_bonus_expr(IB)})*(1+{IB("str_pct")}/100))*0.01+{IB("dex")}*0.0025'
    )

    ws.cell(row=D_BASIC_INPUT_LEVEL, column=1, value="Basic Attack (Dark Impale) Input Level (4th job formula)")
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
    ws.cell(row=D_SKILL_COEFFICIENT, column=1, value="SKILL_COEFFICIENT — Dark Impale base coefficient % (before bonuses)")
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

    r_hex = ROW["HEX_OF_THE_EVIL_EYE"]
    r_dr = ROW["DARK_RESONANCE"]
    r_coc = ROW["CROSS_OVER_CHAINS"]
    r_hb = ROW["HYPER_BODY"]
    r_ee = ROW["EVIL_EYE"]
    r_ldcr, r_ldcd = ROW["LORD_OF_DARKNESS_CRITRATE"], ROW["LORD_OF_DARKNESS_CRITDMG"]
    r_nf = ROW["NIMBLE_FEET"]

    hex_avg = f'((Calc!C{r_hex}=TRUE)*Calc!F{r_hex}*{buff_uptime(r_hex)})'
    dark_resonance_avg = f'((Calc!C{r_dr}=TRUE)*Calc!F{r_dr}*{buff_uptime(r_dr)})'
    cross_over_chains_avg = f'((Calc!C{r_coc}=TRUE)*Calc!F{r_coc}*{buff_uptime(r_coc)})'
    hyper_body_avg = f'((Calc!C{r_hb}=TRUE)*Calc!F{r_hb}*{buff_uptime(r_hb)})'
    nimble_feet_avg = f'((Calc!C{r_nf}=TRUE)*Calc!F{r_nf}*{buff_uptime(r_nf)})'
    evil_eye_avg = f'((Calc!C{r_ee}=TRUE)*Calc!F{r_ee}*{buff_uptime(r_ee)})'
    # Dark Resonance's own patch-added "+20% boss monster damage while active" clause — boss-only
    # (monster_blend_expr-gated), duty-cycled by the same uptime as its own Attack% component.
    dark_resonance_boss_avg = (
        f'((Calc!C{r_dr}=TRUE)*{monster_blend_expr(IB("monster_type"), IB("normal_weight_frac"), "20", "0", "20")}'
        f'*{buff_uptime(r_dr)})'
    )
    lord_of_darkness_critrate_avg = (
        f'((Calc!C{r_ldcr}=TRUE)*Calc!F{r_ldcr}*(Skills!{SC["ProcChance%"]}{r_ldcr}/100)*{buff_uptime(r_ldcr)})'
    )
    lord_of_darkness_critdmg_avg = (
        f'((Calc!C{r_ldcd}=TRUE)*Calc!F{r_ldcd}*(Skills!{SC["ProcChance%"]}{r_ldcd}/100)*{buff_uptime(r_ldcd)})'
    )

    ws.cell(row=R_AVGBUFF, column=1, value="Attack%% Bucket Multiplier (Hex of the Evil Eye + Dark Resonance + Cross Over Chains + Hyper Body, summed additively)")
    ws.cell(row=R_AVGBUFF, column=2, value=f'=1+({hex_avg}+{dark_resonance_avg}+{cross_over_chains_avg}+{hyper_body_avg})/100')

    ws.cell(row=R_CRIT_RATE_BONUS, column=1, value="Global Crit Rate Bonus % (Lord of Darkness, proc-chance x duty-cycle)")
    ws.cell(row=R_CRIT_RATE_BONUS, column=2, value=f'={lord_of_darkness_critrate_avg}')

    ws.cell(row=R_MONSTER_DMG_BONUS, column=1, value="Global Monster Damage-Taken Bonus % (Evil Eye, all types + Dark Resonance, boss-only)")
    ws.cell(row=R_MONSTER_DMG_BONUS, column=2, value=f'={evil_eye_avg}+{dark_resonance_boss_avg}')

    ws.cell(row=R_AS_BONUS, column=1, value="Attack Speed Buff Bonus % (Nimble Feet, duty-cycle averaged)")
    ws.cell(row=R_AS_BONUS, column=2, value=f'={nimble_feet_avg}')

    ws.cell(row=R_APS, column=1, value="Actions Per Second")
    ws.cell(row=R_APS, column=2, value=(
        f'=1+MIN(150,150*(1-(1-{IB("attack_speed")}/150)*(1-B{R_AS_BONUS}/150)))/100'
    ))

    ws.cell(row=R_CASTRATE, column=1, value="Skill + Buff Cast Rate (subtracted from Dark Impale, 1/s)")
    ws.cell(row=R_CASTRATE, column=2, value=(
        f'=IF({fda_main},'
        f'SUMPRODUCT((Skills!{SC["CostsActionSlot"]}2:{SC["CostsActionSlot"]}{LAST_ROW}=TRUE)*'
        f'(Calc!C2:C{LAST_ROW}=TRUE)*Calc!R2:R{LAST_ROW}*Skills!{SC["ActionsPerCast"]}2:{SC["ActionsPerCast"]}{LAST_ROW})/{IB("fight_duration")},'
        f'SUMPRODUCT((Skills!{SC["CostsActionSlot"]}2:{SC["CostsActionSlot"]}{LAST_ROW}=TRUE)*'
        f'(Calc!C2:C{LAST_ROW}=TRUE)*Calc!Q2:Q{LAST_ROW}*Skills!{SC["ActionsPerCast"]}2:{SC["ActionsPerCast"]}{LAST_ROW}))'
    ))

    ws.cell(row=R_BAPS, column=1, value="Dark Impale (Basic Attack) Casts Per Second")
    ws.cell(row=R_BAPS, column=2, value=f'=MAX(0,B{R_APS}-B{R_CASTRATE})')

    ws.cell(row=R_CRIT_DAMAGE_BONUS, column=1, value="Global Critical Damage Bonus % (Lord of Darkness, proc-chance x duty-cycle)")
    ws.cell(row=R_CRIT_DAMAGE_BONUS, column=2, value=f'={lord_of_darkness_critdmg_avg}')

    ws.cell(row=R_FD_BONUS, column=1, value="Global Final Damage Bonus % (unused — no live Final-Damage-buff source exists in this kit)")
    ws.cell(row=R_FD_BONUS, column=2, value=0)

    ws.cell(row=R_TOTAL, column=1, value="TOTAL DPS").font = Font(bold=True, size=13)
    ws.cell(row=R_TOTAL, column=2, value=f"=SUM(Calc!O2:O{LAST_ROW})").font = Font(bold=True, size=13)

    ws.cell(row=R_DARK_IMPALE_DPS, column=1, value="Dark Impale (Basic Attack) DPS")
    ws.cell(row=R_DARK_IMPALE_DPS, column=2, value=f"=Calc!O{ROW['DARK_IMPALE']}")

    ws.cell(row=R_STARTUP_TIME, column=1, value=(
        "Buff-Casting Startup Delay (s, before first damage-skill cast; fixed-duration only)"
    ))
    ws.cell(row=R_STARTUP_TIME, column=2, value="=" + buff_cast_startup_time_expr(
        fda_main, SC["BuffDuration(s)"], SC["CostsActionSlot"], f"Calc!C2:C{LAST_ROW}",
        f"B{R_APS}", LAST_ROW,
    ))

    ws.cell(row=R_BOSS_ONLY_TOTAL, column=1, value="Boss-Only Total DPS (Sensitivity baseline)")
    ws.cell(row=R_BOSS_ONLY_TOTAL, column=2, value=f"=SUM(Calc!T2:T{LAST_ROW})")
    ws.cell(row=R_NORMAL_ONLY_TOTAL, column=1, value="Normal-Only Total DPS (Sensitivity baseline)")
    ws.cell(row=R_NORMAL_ONLY_TOTAL, column=2, value=f"=SUM(Calc!V2:V{LAST_ROW})")

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
    ("defense", "Defense (flat) — Iron Wall converts a level-scaling % (10%+) into STR", "flat"),
    ("defense_pct", "Defense %", "pct"),
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
    "Defense %": "defense_pct",
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
# delta folds into. "attack_mult" has no literal Inputs field but is unused here (Dark Knight has
# no Soul-Arrow-style flat Attack% passive needing this slot).
PASSIVE_DELTA_SLOT = {
    "WEAPON_ACCELERATION": "attack_speed",
    "WEAPON_MASTERY": "min_damage",
    "BARRICADE_SKILL_DMG": "skill_damage",
    "BARRICADE_MAXDMG": "max_damage",
    "POWER_STANCE_FD": "final_damage",
    "FINAL_PACT": "final_damage",
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
            return f'((({ib("flat_str")}+{iron_wall_str_bonus_expr(ib)})*(1+{ib("str_pct")}/100))*0.01+{ib("dex")}*0.0025)'
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

    r_hex = ROW["HEX_OF_THE_EVIL_EYE"]
    r_dr = ROW["DARK_RESONANCE"]
    r_coc = ROW["CROSS_OVER_CHAINS"]
    r_hb = ROW["HYPER_BODY"]
    r_ee = ROW["EVIL_EYE"]
    r_ldcr, r_ldcd, r_nf = ROW["LORD_OF_DARKNESS_CRITRATE"], ROW["LORD_OF_DARKNESS_CRITDMG"], ROW["NIMBLE_FEET"]

    hex_avg = f'((C{row_of["HEX_OF_THE_EVIL_EYE"]}=TRUE)*F{row_of["HEX_OF_THE_EVIL_EYE"]}*{buff_uptime_block(row_of["HEX_OF_THE_EVIL_EYE"], r_hex)})'
    dark_resonance_avg = f'((C{row_of["DARK_RESONANCE"]}=TRUE)*F{row_of["DARK_RESONANCE"]}*{buff_uptime_block(row_of["DARK_RESONANCE"], r_dr)})'
    cross_over_chains_avg = f'((C{row_of["CROSS_OVER_CHAINS"]}=TRUE)*F{row_of["CROSS_OVER_CHAINS"]}*{buff_uptime_block(row_of["CROSS_OVER_CHAINS"], r_coc)})'
    hyper_body_avg = f'((C{row_of["HYPER_BODY"]}=TRUE)*F{row_of["HYPER_BODY"]}*{buff_uptime_block(row_of["HYPER_BODY"], r_hb)})'
    nimble_feet_avg = f'((C{row_of["NIMBLE_FEET"]}=TRUE)*F{row_of["NIMBLE_FEET"]}*{buff_uptime_block(row_of["NIMBLE_FEET"], r_nf)})'
    evil_eye_avg = f'((C{row_of["EVIL_EYE"]}=TRUE)*F{row_of["EVIL_EYE"]}*{buff_uptime_block(row_of["EVIL_EYE"], r_ee)})'
    dark_resonance_boss_avg = (
        f'((C{row_of["DARK_RESONANCE"]}=TRUE)*{monster_blend_expr(ib("monster_type"), ib("normal_weight_frac"), "20", "0", "20")}'
        f'*{buff_uptime_block(row_of["DARK_RESONANCE"], r_dr)})'
    )
    lord_of_darkness_critrate_avg = (
        f'((C{row_of["LORD_OF_DARKNESS_CRITRATE"]}=TRUE)*F{row_of["LORD_OF_DARKNESS_CRITRATE"]}*'
        f'(Skills!{SC["ProcChance%"]}{r_ldcr}/100)*{buff_uptime_block(row_of["LORD_OF_DARKNESS_CRITRATE"], r_ldcr)})'
    )
    lord_of_darkness_critdmg_avg = (
        f'((C{row_of["LORD_OF_DARKNESS_CRITDMG"]}=TRUE)*F{row_of["LORD_OF_DARKNESS_CRITDMG"]}*'
        f'(Skills!{SC["ProcChance%"]}{r_ldcd}/100)*{buff_uptime_block(row_of["LORD_OF_DARKNESS_CRITDMG"], r_ldcd)})'
    )
    # Attack% bucket: every live skill/buff Attack% source sums additively into ONE combined
    # percentage before a single multiplication — matches Verification item 6.
    attack_bucket_block = f'(1+({hex_avg}+{dark_resonance_avg}+{cross_over_chains_avg}+{hyper_body_avg}+{delta["attack_mult"]})/100)'

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
            for col in (7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19):
                ws.cell(row=row, column=col, value=("1" if col == 9 else ""))
            continue

        if key == "DARK_IMPALE":
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

        if key in (["DARK_IMPALE"] + DAMAGE_ROW_KEYS):
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
                f'*(1+(IF({S("Key", r)}="DARK_IMPALE",{ib("basic_attack_damage")}+{delta["basic_attack_damage"]},'
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

        boss_dmg_pct_row = f'{ib("boss_damage")}+{delta["boss_damage"]}+{S("MasteryBossDamage%", r)}+{evil_eye_avg}+{dark_resonance_boss_avg}'
        normal_dmg_pct_row = f'{ib("normal_damage")}+{S("MasteryNormalDamage%", r)}+{evil_eye_avg}+{dark_resonance_boss_avg}'

        if key == "DARK_IMPALE":
            raging_blow_targets_expr = f'(6+{ib("basic_attack_target_increase")})'
            prefix = f"{S('HitsPerCast', r)}*N{row}*{baps_ref}"
            boss_expr, normal_expr = boss_normal_dps_split_exprs(
                prefix, ib("monster_type"), boss_dmg_pct_row, normal_dmg_pct_row,
                raging_blow_targets_expr, ib("max_enemies_hit"),
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

    ws.cell(row=s_crit_rate_bonus, column=1, value="Global Crit Rate Bonus % (Lord of Darkness)")
    ws.cell(row=s_crit_rate_bonus, column=2, value=f'={lord_of_darkness_critrate_avg}')

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

    ws.cell(row=s_baps, column=1, value="Dark Impale Casts Per Second")
    ws.cell(row=s_baps, column=2, value=f'=MAX(0,{aps_ref}-{castrate_ref})')

    ws.cell(row=s_crit_damage_bonus, column=1, value="Global Critical Damage Bonus % (Lord of Darkness)")
    ws.cell(row=s_crit_damage_bonus, column=2, value=f'={lord_of_darkness_critdmg_avg}')

    ws.cell(row=s_fd_bonus, column=1, value="Global Final Damage Bonus % (unused)")
    ws.cell(row=s_fd_bonus, column=2, value=0)

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
    """If a previous Dark-Knight-DPS-Calculator.xlsx already exists at `path`, read back its Inputs
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
