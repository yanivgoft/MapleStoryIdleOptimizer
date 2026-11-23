"""Ice/Lightning Mage Sensitivity spec: the builder's ``STAT_SWEEP`` (stat entries), ``STATUS_REBUILD_KEYS``, ``COMPANION_FULL_SEARCH_KEYS``, ``SUMMON_TIME_KEYS`` and
the passive-skill level deltas of ``src/build_ice_lightning_mage_workbook.py`` (cross-checked against the builder by ``tests/golden/test_ice_lightning_mage_sensitivity.py``).

Ice/Lightning Mage specifics (all reproduced from ``build_stat_block``):

* main stat INT / sub stat LUK (bug 7): ``mainstat_attack_delta`` = the INT x (1 + INT%) change; LUK is typed but not a sweep stat, so there is no sub-stat term.
* the passive skills whose level-dependent values are baked into the typed Inputs add the DELTA of their value to a skill-level block: High Wisdom + Magic Critical (Crit
  Rate) -> Crit Rate (it also feeds Ring of Cycles' threshold, the "Magic Critical ``crit_rate_delta`` fix" of the builder), Magic Critical (Crit Damage) -> Crit Damage,
  Spell Mastery -> Min Damage, Magic Acceleration -> Attack Speed.  Like every Magic-Critical-pattern row of the workbook the delta is NOT gated on the passive's unlock level
  (the block reads the Skills-sheet F cell, which has no unlock gate), except Magic Acceleration: its delta is added to MP Eater's flat Attack Speed inside
  ``IF(C{MP Eater}, F + delta, 0)``, i.e. it only counts once MP Eater (Lv49) is unlocked, and it joins the bonus side (``as_bonus_extra``) of the Attack Speed diminishing
  returns, not the typed side.
* the Shamaness Marble equip block feeds its Buff Duration what-if into the block (``bdi_toggle_wired``; fixed 2026-11-22, the builder defined the helper and never used it,
  so the row was inert), the Reindeer's Spear dose reaches the rows' defense reduction and Athena's Gloves' direct Attack Speed joins the block's Actions Per Second (both
  were already correct in this builder).
* the baked-in Final Damage artifacts are a factor on the whole Final Damage product (``fd_baked_factor``: the live bucket x the factors, ``baked_fd_form = "factor"``).
"""
from ..common import sens as sens_mod
from ..common.sens import MainStat, PassiveLevel, SensSpec

STAT_LIST = sens_mod.stat_list((
    ("flat_int", "Flat INT", "flat"),
    ("int_pct", "INT %", "pct"),
))

_INT_NOTE = "adds the main stat's flat-Attack channel (1 INT = 1 Attack before ATTACK%) next to STAT_DAMAGE"
SEMANTICS = {
    "flat_int": _INT_NOTE,
    "int_pct": _INT_NOTE,
    "skill_lvl_2nd": "adds High Wisdom's (Crit Rate), Spell Mastery's (Min Damage) and Magic Acceleration's (Attack Speed) level deltas",
    "skill_lvl_3rd": "adds Magic Critical's Crit Rate / Crit Damage level delta",
    "skill_lvl_all": "adds High Wisdom, Magic Critical (Crit Rate / Crit Damage), Spell Mastery and Magic Acceleration level deltas",
    "crit_rate": "Book of Ancient (if equipped): Crit Damage follows the crit-rate change",
    "attack_speed": "Athena's Gloves (if equipped): Max Damage follows; Bottle of Emotion (if equipped): Final Damage follows",
}

# stat sweeps whose block re-solves the Status/KO strip (the others reuse the main strip) - the builder's STATUS_REBUILD_KEYS
STATUS_REBUILD_KEYS = (
    "skill_cooldown_decrease", "buff_duration_increase_pct", "shamaness_marble_equipped", "status_effect_damage",
    "companion_summon_time_increase_pct", "hexagon_necklace_equipped", "arwens_glass_shoes_equipped",
    "charm_of_the_undead_equipped", "old_music_box_equipped", "secret_map_equipped", "reindeer_spear_equipped",
    "alliance_badge_equipped", "bottle_of_emotion_equipped", "skill_lvl_1st", "skill_lvl_2nd", "skill_lvl_4th", "skill_lvl_all",
    "skill_lvl_3rd", "skill_damage", "basic_attack_damage", "boss_damage", "crit_rate",
    "ring_of_cycles_equipped", "book_of_ancient_equipped", "rainbow_snail_shell_equipped",
    "candle_equipped", "sayrams_necklace_equipped", "star_rock_equipped",
)
# blocks that search the three summon-time candidates again (the rest pin the main sheet's choice) - the builder's COMPANION_FULL_SEARCH_KEYS
COMPANION_FULL_SEARCH_KEYS = ("companion_summon_time_increase_pct", "hexagon_necklace_equipped", "horn_flute_equipped", "skill_cooldown_decrease",
                              "arwens_glass_shoes_equipped")
SUMMON_TIME_KEYS = ("companion_summon_time_increase_pct", "arwens_glass_shoes_equipped")

# Skills-sheet rows (all factor 22, scaling, no mastery): (hook, base tenths-of-%, factor index, job step) - the block's crit_rate_delta / crit_dmg_delta / min_dmg_delta /
# attack_speed_delta cells (unlock None: F has no unlock gate, see the module docstring)
PASSIVE_LEVELS = (
    PassiveLevel("crit_rate_delta", 80, 22, 3),      # Magic Critical (Crit Rate)
    PassiveLevel("crit_rate_delta", 80, 22, 2),      # High Wisdom
    PassiveLevel("crit_damage_delta", 120, 22, 3),   # Magic Critical (Crit Damage)
    PassiveLevel("min_damage_delta", 150, 22, 2),    # Spell Mastery
    PassiveLevel("as_bonus_extra", 50, 22, 2),       # Magic Acceleration (counted only while MP Eater is unlocked)
)

SPEC = SensSpec(
    class_id="ice_lightning_mage", stat_list=STAT_LIST, mainstat=MainStat("flat_int", "int_pct"),
    status_rebuild_keys=STATUS_REBUILD_KEYS, companion_full_search_keys=COMPANION_FULL_SEARCH_KEYS, summon_time_keys=SUMMON_TIME_KEYS,
    passive_levels=PASSIVE_LEVELS, semantics=SEMANTICS,
    bdi_toggle_wired=True, reindeer_dose_in_rows=True, athena_as_in_aps=True,
)
