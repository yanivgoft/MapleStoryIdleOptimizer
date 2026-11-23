"""FP-Mage Sensitivity spec: the builder's ``STAT_SWEEP`` (stat entries), ``STATUS_REBUILD_KEYS``, ``COMPANION_FULL_SEARCH_KEYS``, ``SUMMON_TIME_KEYS`` and the
passive-skill level deltas of ``src/build_fp_mage_workbook.py`` (checked by ``tests/golden/test_*_sensitivity.py``)."""
from ..common import sens as sens_mod
from ..common.sens import MainStat, PassiveLevel, SensSpec

STAT_LIST = sens_mod.stat_list((
    ("flat_int", "Flat INT", "flat"),
    ("int_pct", "INT %", "pct"),
))

SEMANTICS = {
    "flat_int": "adds the main stat's flat-Attack channel (1 INT = 1 Attack before ATTACK%) next to STAT_DAMAGE",
    "int_pct": "adds the main stat's flat-Attack channel (1 INT = 1 Attack before ATTACK%) next to STAT_DAMAGE",
    "skill_lvl_2nd": "adds Spell Mastery's (Min Damage) level delta",
    "skill_lvl_3rd": "adds Magic Critical's Crit Rate / Crit Damage level delta",
    "skill_lvl_all": "adds Spell Mastery (Min Damage) and Magic Critical (Crit Rate / Crit Damage) level deltas",
    "crit_rate": "Book of Ancient (if equipped): Crit Damage follows the crit-rate change",
    "attack_speed": "Athena's Gloves (if equipped): Max Damage follows; Bottle of Emotion (if equipped): Final Damage follows",
}

# stat sweeps whose block re-solves the Status/KO strip (the others reuse the main strip) - the builder's STATUS_REBUILD_KEYS
STATUS_REBUILD_KEYS = (
    "skill_cooldown_decrease", "buff_duration_increase_pct", "shamaness_marble_equipped", "status_effect_damage",
    "companion_summon_time_increase_pct", "hexagon_necklace_equipped", "arwens_glass_shoes_equipped",
    "charm_of_the_undead_equipped", "old_music_box_equipped", "secret_map_equipped", "reindeer_spear_equipped",
    "alliance_badge_equipped", "bottle_of_emotion_equipped",
    # (2026-11-19) every other stat whose value changes what the strip consumes: buff values / cooldowns (skill levels, Soul Contract) and the
    # RELATIVE per-cast damage weights (skill vs basic attack: Skill / Basic Attack Damage, Boss Damage with the Basic Attack's own Boss Mastery,
    # Crit Rate through Ring of Cycles).  Stats that scale every damage row alike keep reusing the main strip (exact).
    "skill_lvl_1st", "skill_lvl_2nd", "skill_lvl_3rd", "skill_lvl_4th", "skill_lvl_all",
    "skill_damage", "basic_attack_damage", "boss_damage", "crit_rate",
    "ring_of_cycles_equipped", "book_of_ancient_equipped", "rainbow_snail_shell_equipped",
    "candle_equipped", "sayrams_necklace_equipped", "star_rock_equipped",
)
# blocks that search the three summon-time candidates again (the rest pin the main sheet's choice) - the builder's COMPANION_FULL_SEARCH_KEYS
COMPANION_FULL_SEARCH_KEYS = ("companion_summon_time_increase_pct", "hexagon_necklace_equipped", "horn_flute_equipped", "skill_cooldown_decrease",
                              "arwens_glass_shoes_equipped")
SUMMON_TIME_KEYS = ("companion_summon_time_increase_pct", "arwens_glass_shoes_equipped")

# Spell Mastery / Magic Critical passives: (base tenths-of-%, factor index, job step).  Their contribution is baked into the typed Inputs; a block adds the
# delta of their level-dependent value (Skills sheet rows MAGIC_CRITICAL_RATE / MAGIC_CRITICAL_DAMAGE / SPELL_MASTERY: factor 22, no mastery)
PASSIVE_LEVELS = (
    PassiveLevel("crit_rate_delta", 80, 22, 3),
    PassiveLevel("crit_damage_delta", 120, 22, 3),
    PassiveLevel("min_damage_delta", 150, 22, 2),
)

SPEC = SensSpec(
    class_id="fp_mage", stat_list=STAT_LIST, mainstat=MainStat("flat_int", "int_pct"),
    status_rebuild_keys=STATUS_REBUILD_KEYS, companion_full_search_keys=COMPANION_FULL_SEARCH_KEYS, summon_time_keys=SUMMON_TIME_KEYS,
    passive_levels=PASSIVE_LEVELS, semantics=SEMANTICS,
)
