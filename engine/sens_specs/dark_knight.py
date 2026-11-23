"""Dark Knight Sensitivity spec: the builder's ``STAT_SWEEP`` (stat entries), ``STATUS_REBUILD_KEYS``, ``COMPANION_FULL_SEARCH_KEYS``, ``SUMMON_TIME_KEYS`` and
``PASSIVE_DELTA_SLOT`` of ``src/build_dark_knight_workbook.py`` (cross-checked against the builder by ``tests/golden/test_sensitivity.py --class dark_knight``).

Dark Knight specifics (all reproduced from ``build_stat_block``):

* main stat STR / sub stat DEX (bug 7): ``mainstat_attack_delta = (STR x (1 + STR%)) delta + 0.25 x DEX delta`` - Iron Wall's STR and the Defense sweeps add NO
  flat-Attack channel (the delta uses the typed flat STR only); Iron Wall itself (a share of the TOTAL Defense becomes STR before STR %) is part of STAT_DAMAGE
  and moves with Defense / Defense % through the normal model (``stat_damage``).
* the passive skills whose level-dependent values are baked into the typed Inputs - Weapon Acceleration (Attack Speed), Weapon Mastery (Min Damage), Barricade
  Mastery (Skill Damage + Max Damage), Power Stance and Final Pact (Final Damage) - add the DELTA of their value to a skill-level block (``PASSIVE_DELTA_SLOT``).
  Power Stance / Final Pact enter the ADDITIVE Final Damage bracket next to ``Inputs!final_damage`` (a typed ``final_damage`` + delta), the baked-in Final Damage
  ARTIFACTS multiply on top as the artifact bucket (``final_damage_factor`` form).
* the PvP opponent's Defense is the total Defense of the MAIN sheet in every block (the block's ``ib("monster_defense")`` is the baseline Inputs cell): sweeping
  Defense / Defense % never moves the opponent (``pin_monster_defense``).
* the three equip-toggle gaps the first version of this spec REPRODUCED (Reindeer's Spear dose missing from the rows' defense reduction, Athena's Gloves' direct Attack
  Speed missing from the block's Actions Per Second, the inert Shamaness Marble row) were FIXED in the builder 2026-11-23 (``reindeer_dose_in_rows`` / ``athena_as_in_aps`` /
  ``bdi_toggle_wired`` all True; KNOWN_GAPS "Dark Knight: Sensitivity in the engine").  ``athena_gloves_equipped`` stays OUT of ``STATUS_REBUILD_KEYS``: no input of the timeline
  strip moves with Attack Speed in this kit (engine experiment: strip reuse == re-solve, row == true delta at 1.0000000000 in World Boss / Enhancement Dungeon).
"""
from ..common import sens as sens_mod
from ..common.sens import MainStat, PassiveLevel, SensSpec

STAT_LIST = sens_mod.stat_list((
    ("flat_str", "Flat STR", "flat"),
    ("str_pct", "STR %", "pct"),
    ("dex", "DEX", "flat"),
    ("defense", "Defense (flat) — Iron Wall converts a level-scaling % (10%+) into STR", "flat"),
    ("defense_pct", "Defense %", "pct"),
))

_STR_NOTE = "adds the main stat's flat-Attack channel (1 STR = 1 Attack, 1 DEX = 0.25 Attack, before ATTACK%) next to STAT_DAMAGE"
SEMANTICS = {
    "flat_str": _STR_NOTE,
    "str_pct": _STR_NOTE,
    "dex": _STR_NOTE,
    "defense": "Iron Wall: a level-scaling share of the TOTAL Defense becomes STR (part of STAT_DAMAGE); no flat-Attack channel; PvP opponent Defense stays at the current value",
    "defense_pct": "Iron Wall: a level-scaling share of the TOTAL Defense becomes STR (part of STAT_DAMAGE); no flat-Attack channel; PvP opponent Defense stays at the current value",
    "skill_lvl_2nd": "adds Weapon Acceleration's (Attack Speed) and Weapon Mastery's (Min Damage) level deltas",
    "skill_lvl_4th": "adds Barricade Mastery's (Skill Damage, Max Damage), Power Stance's and Final Pact's (Final Damage) level deltas",
    "skill_lvl_all": "adds Weapon Acceleration, Weapon Mastery, Barricade Mastery, Power Stance and Final Pact level deltas",
    "crit_rate": "Book of Ancient (if equipped): Crit Damage follows the crit-rate change",
    "attack_speed": "Athena's Gloves (if equipped): Max Damage follows; Bottle of Emotion (if equipped): Final Damage follows",
}

STATUS_REBUILD_KEYS = (
    "skill_cooldown_decrease", "buff_duration_increase_pct", "shamaness_marble_equipped", "status_effect_damage",
    "companion_summon_time_increase_pct", "hexagon_necklace_equipped", "arwens_glass_shoes_equipped",
    # everything that moves the engine's Attack% bucket (A0 / Charm / the cast buffs' F)
    "charm_of_the_undead_equipped", "old_music_box_equipped", "secret_map_equipped", "reindeer_spear_equipped",
    "alliance_badge_equipped", "bottle_of_emotion_equipped", "skill_lvl_2nd", "skill_lvl_3rd", "skill_lvl_4th", "skill_lvl_all",
    # Sensitivity fix 1 (2026-11-20): stats that change the RELATIVE per-cast weights (skill vs basic attack, Dark Impale's own Boss Mastery, Ring of Cycles)
    "skill_damage", "basic_attack_damage", "boss_damage", "crit_rate",
    "ring_of_cycles_equipped", "book_of_ancient_equipped", "rainbow_snail_shell_equipped", "contract_of_darkness_equipped",
    "candle_equipped", "sayrams_necklace_equipped", "star_rock_equipped", "peach_tree_equipped", "silver_pendant_equipped",
)
COMPANION_FULL_SEARCH_KEYS = ("companion_summon_time_increase_pct", "hexagon_necklace_equipped", "horn_flute_equipped", "skill_cooldown_decrease",
                              "arwens_glass_shoes_equipped")
SUMMON_TIME_KEYS = ("companion_summon_time_increase_pct", "arwens_glass_shoes_equipped")

# PASSIVE_DELTA_SLOT of the builder: (hook, base tenths-of-%, factor index, job step, unlock level) of each Skills-sheet passive row (all factor 22, scaling)
PASSIVE_LEVELS = (
    PassiveLevel("attack_speed_extra", 50, 22, 2, 33),      # Weapon Acceleration
    PassiveLevel("min_damage_delta", 150, 22, 2, 43),       # Weapon Mastery
    PassiveLevel("skill_damage_delta", 150, 22, 4, 120),    # Barricade Mastery (Skill Damage)
    PassiveLevel("max_damage_delta", 200, 22, 4, 120),      # Barricade Mastery (Max Damage Multiplier)
    PassiveLevel("final_damage_delta", 150, 22, 4, 125),    # Power Stance (Final Damage)
    PassiveLevel("final_damage_delta", 100, 22, 4, 107),    # Final Pact
)

# the builder's POTENTIAL_STAT_TO_SWEEP_KEY / POTENTIAL_SUB_STAT_PCT_LINES / EQUIP_COMPARE_STAT_TO_SWEEP_KEY / ARTIFACT_POTENTIAL_STAT_TO_SWEEP_KEY (checked against it by
# tests/golden/test_sensitivity.py::test_static[dark_knight]); Iron Wall makes "Defense" / "Defense %" lines real here (they are worth 0 in most classes)
STAT_TO_KEY = sens_mod.standard_stat_to_key("Str", "flat_str", "str_pct", sub=("Dex", "dex"), defense_pct="defense_pct")

SPEC = SensSpec(
    class_id="dark_knight", stat_list=STAT_LIST, mainstat=MainStat("flat_str", "str_pct", subs=(("dex", 0.25),)),
    status_rebuild_keys=STATUS_REBUILD_KEYS, companion_full_search_keys=COMPANION_FULL_SEARCH_KEYS, summon_time_keys=SUMMON_TIME_KEYS,
    passive_levels=PASSIVE_LEVELS, semantics=SEMANTICS, bdi_toggle_wired=True, pin_monster_defense=True, reindeer_dose_in_rows=True,
    athena_as_in_aps=True, stat_to_key=STAT_TO_KEY,
)
