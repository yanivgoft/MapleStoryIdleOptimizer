"""Hero Sensitivity spec: the builder's ``STAT_SWEEP`` (stat entries), ``STATUS_REBUILD_KEYS``, ``COMPANION_FULL_SEARCH_KEYS``, ``SUMMON_TIME_KEYS`` and
``PASSIVE_DELTA_SLOT`` of ``src/build_hero_workbook.py`` (cross-checked against the builder by ``tests/golden/test_sensitivity.py --class hero``).

Hero specifics (all reproduced from ``build_stat_block``):

* main stat STR / sub stat DEX (bug 7): ``mainstat_attack_delta = (STR x (1 + STR%)) delta + 0.25 x DEX delta`` (no Defense stat in this class: Hero has no Iron Wall).
* the passive skills whose level-dependent values are baked into the typed Inputs - Weapon Acceleration (Attack Speed), Physical Training (Basic Attack Damage), Weapon
  Mastery (Min Damage), Combat Mastery (Skill Damage + Max Damage), Chance Attack (Crit Rate) and Power Stance (Final Damage) - add the DELTA of their value to a skill-level
  block (``PASSIVE_DELTA_SLOT``).  Chance Attack's Crit Rate delta feeds the live crit rate but NOT Ring of Cycles' threshold (the block's ``roc_threshold_cr_block`` has no passive
  delta: a pre-existing approximation of the builder, reproduced - the class module keeps ``crit_rate_input`` for the Ring and ``crit_rate`` for the rows).
* Hero retypes ``Inputs!final_damage`` INSIDE the additive Final Damage bucket ``(1 + (final_damage + passive + Enrage / Combo Synergy / Lv98 +5) / 100)``: the baked-in Final
  Damage artifacts (Cursed Doll, Lit Lamp, Clear Spring Water, Soul Pouch, Bottle of Emotion) are a factor on the TYPED value, not on the artifact bucket
  (``baked_fd_form="typed"``), and the Final Damage sweep (+1% multiplicative) bumps the FULL bucket including the live Enrage / Combo Synergy share
  (``MULT_KIND_EXTRA_REF``; ``mult_extra`` -> ``model.final_damage_extra``; the table's Current / New value include it).
* Reindeer's Spear: the block's rows read ``def_pen_total_block`` (the dose reaches the rows' defense reduction, the boss-branch correction and the companion): flag True.
  Shamaness Marble: wired (``bdi_block``; it also moves Puncture's window).  Athena's Gloves: the block's Actions Per Second now includes the gloves' direct Attack Speed
  (builder fixed 2026-11-22, the same day the engine side was added; before it the row only saw the dependent Max Damage): flag True.
"""
from ..common import sens as sens_mod
from ..common.sens import MainStat, PassiveLevel, SensSpec

STAT_LIST = sens_mod.stat_list((
    ("flat_str", "Flat STR", "flat"),
    ("str_pct", "STR %", "pct"),
    ("dex", "DEX", "flat"),
))

_STR_NOTE = "adds the main stat's flat-Attack channel (1 STR = 1 Attack, 1 DEX = 0.25 Attack, before ATTACK%) next to STAT_DAMAGE"
SEMANTICS = {
    "flat_str": _STR_NOTE,
    "str_pct": _STR_NOTE,
    "dex": _STR_NOTE,
    "final_damage": "the +1% multiplicative step bumps the whole Final Damage bucket, including the live Enrage / Combo Synergy / Lv98 share (Current / New include it)",
    "skill_lvl_2nd": "adds Weapon Acceleration's (Attack Speed), Physical Training's (Basic Attack Damage) and Weapon Mastery's (Min Damage) level deltas",
    "skill_lvl_3rd": "adds Chance Attack's Crit Rate level delta (not into Ring of Cycles' threshold)",
    "skill_lvl_4th": "adds Combat Mastery's (Skill Damage, Max Damage) and Power Stance's (Final Damage) level deltas",
    "skill_lvl_all": "adds every passive's level delta (Weapon Acceleration, Physical Training, Weapon Mastery, Chance Attack, Combat Mastery, Power Stance)",
    "crit_rate": "Book of Ancient (if equipped): Crit Damage follows the crit-rate change",
    "attack_speed": "Athena's Gloves (if equipped): Max Damage follows; Bottle of Emotion (if equipped): Final Damage follows",
}

STATUS_REBUILD_KEYS = (
    "skill_cooldown_decrease", "buff_duration_increase_pct", "shamaness_marble_equipped", "status_effect_damage",
    "companion_summon_time_increase_pct", "hexagon_necklace_equipped", "arwens_glass_shoes_equipped",
    # everything that moves the engine's Attack% bucket (A0 / Charm / Spirit Blade's F)
    "charm_of_the_undead_equipped", "old_music_box_equipped", "secret_map_equipped", "reindeer_spear_equipped",
    "alliance_badge_equipped", "bottle_of_emotion_equipped", "skill_lvl_2nd", "skill_lvl_all",
    # Sensitivity fix 1 (2026-11-21): stats that change the RELATIVE per-cast weights (skill vs Raging Blow, its own Boss Mastery, Ring of Cycles) and the passive deltas
    "skill_damage", "basic_attack_damage", "boss_damage", "crit_rate", "skill_lvl_3rd", "skill_lvl_4th",
    "ring_of_cycles_equipped", "book_of_ancient_equipped", "rainbow_snail_shell_equipped",
    "candle_equipped", "sayrams_necklace_equipped", "star_rock_equipped",
)
COMPANION_FULL_SEARCH_KEYS = ("companion_summon_time_increase_pct", "hexagon_necklace_equipped", "horn_flute_equipped", "skill_cooldown_decrease",
                              "arwens_glass_shoes_equipped")
SUMMON_TIME_KEYS = ("companion_summon_time_increase_pct", "arwens_glass_shoes_equipped")

# PASSIVE_DELTA_SLOT of the builder: (hook, base tenths-of-%, factor index, job step, unlock level) of each Skills-sheet passive row (all factor 22, scaling)
PASSIVE_LEVELS = (
    PassiveLevel("attack_speed_extra", 50, 22, 2, 33),          # Weapon Acceleration
    PassiveLevel("basic_attack_damage_delta", 100, 22, 2, 38),   # Physical Training
    PassiveLevel("min_damage_delta", 150, 22, 2, 43),            # Weapon Mastery
    PassiveLevel("skill_damage_delta", 150, 22, 4, 120),         # Combat Mastery (Skill Damage)
    PassiveLevel("max_damage_delta", 300, 22, 4, 120),           # Combat Mastery (Max Damage Multiplier)
    PassiveLevel("final_damage_delta", 180, 22, 4, 125),         # Power Stance (Final Damage)
    PassiveLevel("crit_rate_delta", 80, 22, 3, 72),              # Chance Attack (Crit Rate)
)

# the builder's POTENTIAL_STAT_TO_SWEEP_KEY / POTENTIAL_SUB_STAT_PCT_LINES / EQUIP_COMPARE_STAT_TO_SWEEP_KEY / ARTIFACT_POTENTIAL_STAT_TO_SWEEP_KEY (checked against it by
# tests/golden/test_sensitivity.py::test_static[hero]); "Defense (flat)" has no sweep row in this class (no Iron Wall): a key without a rate prices as 0
STAT_TO_KEY = sens_mod.standard_stat_to_key("Str", "flat_str", "str_pct", sub=("Dex", "dex"))

SPEC = SensSpec(
    class_id="hero", stat_list=STAT_LIST, mainstat=MainStat("flat_str", "str_pct", subs=(("dex", 0.25),)),
    status_rebuild_keys=STATUS_REBUILD_KEYS, companion_full_search_keys=COMPANION_FULL_SEARCH_KEYS, summon_time_keys=SUMMON_TIME_KEYS,
    passive_levels=PASSIVE_LEVELS, semantics=SEMANTICS, bdi_toggle_wired=True, pin_monster_defense=False, baked_fd_form="typed",
    reindeer_dose_in_rows=True, athena_as_in_aps=True, stat_to_key=STAT_TO_KEY, mult_extra=(("final_damage", "final_damage_extra"),),
)
