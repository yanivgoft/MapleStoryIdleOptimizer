"""Bishop Sensitivity spec: the builder's ``STAT_SWEEP`` (stat entries), ``STATUS_REBUILD_KEYS``, ``COMPANION_FULL_SEARCH_KEYS``, ``SUMMON_TIME_KEYS`` and the
passive-skill level deltas of ``src/build_bishop_workbook.py`` (cross-checked against the builder by ``tests/golden/test_bishop_sensitivity.py``).

Bishop specifics (all reproduced from ``build_stat_block``):

* main stat INT / sub stat LUK (bug 7): ``mainstat_attack_delta`` = the typed INT x (1 + INT%) change; LUK is typed but not a sweep stat, so there is no sub-stat term.
  Invincible's Defense -> INT share is NOT in that flat-Attack channel (typed flat INT only); it is part of STAT_DAMAGE and moves with Defense / Defense % through the
  normal model (the block re-derives ``ib("stat_damage")`` with its own Divine Protection bonus cell).
* Defense / Defense % are real stats here (Invincible, Lv35+): the total Defense ``Defense x (1 + (Defense % + Divine Protection's averaged bonus)/100)`` feeds INT before INT %.
  The PvP opponent has the main sheet's TOTAL Defense (``Inputs!monster_defense``, Defense x (1 + (Defense % + Divine Protection)/100) of the baseline), and a block's
  ``ib("monster_defense")`` is that baseline Inputs cell: sweeping Defense / Defense % never moves the opponent (``pin_monster_defense``).
* the passive skills whose level-dependent values are baked into the typed Inputs add the DELTA of their value to a skill-level block: High Wisdom + Magic Critical (Crit Rate)
  -> Crit Rate, Magic Critical (Crit Damage) -> Crit Damage, Spell Mastery -> Min Damage, Magic Acceleration -> Attack Speed.  The delta is read from the Skills-sheet F cells (no
  unlock gate, ``unlock=None``) - except Magic Acceleration: it is added to MP Eater's flat Attack Speed inside ``IF(C{MP Eater}, F + delta, 0)``, i.e. it only counts once MP Eater
  (Lv49) is unlocked (the class module's ``as_bonus_extra``) and it joins the bonus side of the Attack Speed diminishing returns, not the typed side.  The Crit Rate delta feeds
  the live crit rate but NOT Ring of Cycles' threshold (the block's ``roc_threshold_cr_block`` has no passive delta: a builder approximation, reproduced - the class module keeps
  ``crit_rate_input`` for the Ring and ``crit_rate`` for the rows).
* the Shamaness Marble equip block feeds its Buff Duration what-if into every buff uptime / the timeline strip (``bdi_block``): flag True.  The Reindeer's Spear dose reaches the
  rows' defense reduction (``def_pen_total_block`` in the K formula): flag True.  Athena's Gloves' direct Attack Speed joins the block's Actions Per Second: flag True since the
  builder fix of 2026-11-22 (before it the block's ``s_aps`` read ``ib("attack_speed")`` without the artifact term, so the row only saw the dependent Max Damage).
* the baked-in Final Damage artifacts are a factor on the live artifact Final Damage bucket (``fd_baked_factor``, ``baked_fd_form = "factor"``); Advanced Blessing / Infinity,
  Element Amplification, Blood of the Divine and Arcane Aim are live level-dependent terms of the model (no baked-in passive Final Damage).
"""
from ..common import sens as sens_mod
from ..common.sens import MainStat, PassiveLevel, SensSpec

STAT_LIST = sens_mod.stat_list((
    ("flat_int", "Flat INT", "flat"),
    ("int_pct", "INT %", "pct"),
    ("defense", "Defense (flat) — Invincible converts a level-scaling % (10%+) into INT", "flat"),
    ("defense_pct", "Defense %", "pct"),
))

_INT_NOTE = "adds the main stat's flat-Attack channel (1 INT = 1 Attack before ATTACK%) next to STAT_DAMAGE"
_DEF_NOTE = ("Invincible: a level-scaling share of the TOTAL Defense (incl. Defense % and Divine Protection) becomes INT before INT % (part of STAT_DAMAGE); no flat-Attack channel; "
             "PvP opponent Defense stays at the current value")
SEMANTICS = {
    "flat_int": _INT_NOTE,
    "int_pct": _INT_NOTE,
    "defense": _DEF_NOTE,
    "defense_pct": _DEF_NOTE,
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
    # everything that moves the engine's buff bucket (A0 incl. Charm and the Attack% artifacts; the buffs' F incl. the skill-level inputs)
    "charm_of_the_undead_equipped", "old_music_box_equipped", "secret_map_equipped", "reindeer_spear_equipped",
    "alliance_badge_equipped", "bottle_of_emotion_equipped",
    "skill_lvl_1st", "skill_lvl_2nd", "skill_lvl_3rd", "skill_lvl_4th", "skill_lvl_all",
    # Sensitivity fix 1 (2026-11-20): stats that change the RELATIVE per-cast weights (skill rows vs Big Bang, Big Bang's own Boss Mastery, Ring of Cycles)
    "skill_damage", "basic_attack_damage", "boss_damage", "crit_rate",
    "ring_of_cycles_equipped", "book_of_ancient_equipped", "rainbow_snail_shell_equipped",
    "candle_equipped", "sayrams_necklace_equipped", "star_rock_equipped",
)
COMPANION_FULL_SEARCH_KEYS = ("companion_summon_time_increase_pct", "hexagon_necklace_equipped", "horn_flute_equipped", "skill_cooldown_decrease",
                              "arwens_glass_shoes_equipped")
SUMMON_TIME_KEYS = ("companion_summon_time_increase_pct", "arwens_glass_shoes_equipped")

# Skills-sheet rows (all factor 22, scaling, no mastery): (hook, base tenths-of-%, factor index, job step) - the block's crit_rate_delta / crit_dmg_delta / min_dmg_delta /
# attack_speed_delta cells (unlock None: F has no unlock gate; Magic Acceleration's MP Eater gate lives in the class module's ``as_bonus_extra``)
PASSIVE_LEVELS = (
    PassiveLevel("crit_rate_delta", 80, 22, 3),      # Magic Critical (Crit Rate)
    PassiveLevel("crit_rate_delta", 80, 22, 2),      # High Wisdom
    PassiveLevel("crit_damage_delta", 120, 22, 3),   # Magic Critical (Crit Damage)
    PassiveLevel("min_damage_delta", 150, 22, 2),    # Spell Mastery
    PassiveLevel("as_bonus_extra", 50, 22, 2),       # Magic Acceleration (counted only while MP Eater is unlocked)
)

# the builder's POTENTIAL_STAT_TO_SWEEP_KEY / POTENTIAL_SUB_STAT_PCT_LINES / EQUIP_COMPARE_STAT_TO_SWEEP_KEY / ARTIFACT_POTENTIAL_STAT_TO_SWEEP_KEY (checked against it by
# tests/golden/test_bishop_sensitivity.py::test_static); Invincible makes "Defense %" / "Defense (flat)" cube / equipment lines real here (artifact-potential Defense % stays
# unpriced in the builder map)
STAT_TO_KEY = sens_mod.standard_stat_to_key("Int", "flat_int", "int_pct", defense_pct="defense_pct")

SPEC = SensSpec(
    class_id="bishop", stat_list=STAT_LIST, mainstat=MainStat("flat_int", "int_pct"),
    status_rebuild_keys=STATUS_REBUILD_KEYS, companion_full_search_keys=COMPANION_FULL_SEARCH_KEYS, summon_time_keys=SUMMON_TIME_KEYS,
    passive_levels=PASSIVE_LEVELS, semantics=SEMANTICS,
    bdi_toggle_wired=True, pin_monster_defense=True, baked_fd_form="factor", reindeer_dose_in_rows=True, athena_as_in_aps=True, stat_to_key=STAT_TO_KEY,
)
