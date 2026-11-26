"""Dawn Warrior Sensitivity spec (engine-native: no workbook builder exists, so nothing is cross-checked against one; the structure copies Hero's / Buccaneer's).

Dawn Warrior specifics:

* main stat STR / sub stat DEX (bug 7): ``mainstat_attack_delta = (STR x (1 + STR%)) delta + 0.25 x DEX delta``.
* the always-on passives whose level-dependent values are baked into the typed Inputs (the stat screen contains them) add the DELTA of their value to a skill-level block
  (``PASSIVE_LEVELS``): Soul Speed (Attack Speed), Physical Training and Unpredictable (Basic Attack Damage), Sword Mastery (Min Damage), Divine Hand and Soul Pledge (Attack %,
  ``attack_mult_delta``: applied to the typed ATTACK %), Inner Shout and Unpredictable (Final Damage, additive next to the typed value), Soul Pledge (Crit Damage), Student of the Blade
  (Skill Damage, Max Damage).  The conditional / timed effects (Soul Elemental, Equinox Cycle, Soul Blessing I-III, Equinox Mastery, Call of Cygnus, Master of the Sword) are LIVE in
  the model and need no delta.
* Dawn Warrior retypes ``Inputs!final_damage`` INSIDE the additive Final Damage bucket (typed + Soul Blessing III / Master of the Sword live share + passive deltas): the baked-in
  Final Damage artifacts are a factor on the TYPED value (``baked_fd_form="typed"``) and the Final Damage sweep bumps the full bucket (``mult_extra``), like Hero.
* The Status/KO strip has no engine-timed buff, so the rebuild set is only what moves cooldowns, the per-cast weights' relative sizes and the strip's constant Attack % / Hexagon / Charm.
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
    "final_damage": "the +1% multiplicative step bumps the whole Final Damage bucket, including the live Soul Blessing III / Master of the Sword share (Current / New include it)",
    "skill_lvl_2nd": "adds Soul Speed's (Attack Speed), Physical Training's (Basic Attack Damage), Sword Mastery's (Min Damage) and Divine Hand's (Attack %) level deltas",
    "skill_lvl_3rd": "adds Inner Shout's Final Damage level delta",
    "skill_lvl_4th": "adds Soul Pledge's (Attack %, Crit Damage), Unpredictable's (Basic Attack Damage, Final Damage) and Student of the Blade's (Skill Damage, Max Damage) level deltas",
    "skill_lvl_all": "adds every passive's level delta (Soul Speed, Physical Training, Sword Mastery, Divine Hand, Inner Shout, Soul Pledge, Unpredictable, Student of the Blade)",
    "crit_rate": "Book of Ancient (if equipped): Crit Damage follows the crit-rate change",
    "attack_speed": "Athena's Gloves (if equipped): Max Damage follows; Bottle of Emotion (if equipped): Final Damage follows",
}

STATUS_REBUILD_KEYS = (
    "skill_cooldown_decrease", "buff_duration_increase_pct", "shamaness_marble_equipped", "status_effect_damage",
    "companion_summon_time_increase_pct", "hexagon_necklace_equipped", "arwens_glass_shoes_equipped",
    # everything that moves the engine's constant Attack% bucket (A0 / Charm)
    "charm_of_the_undead_equipped", "old_music_box_equipped", "secret_map_equipped", "reindeer_spear_equipped",
    "alliance_badge_equipped", "bottle_of_emotion_equipped", "skill_lvl_1st", "skill_lvl_2nd", "skill_lvl_all",
    # stats that change the RELATIVE per-cast weights (skill vs the basic attack, its own Boss Mastery, Ring of Cycles) and the passive deltas
    "skill_damage", "basic_attack_damage", "boss_damage", "crit_rate", "skill_lvl_3rd", "skill_lvl_4th",
    "ring_of_cycles_equipped", "book_of_ancient_equipped", "rainbow_snail_shell_equipped",
    "candle_equipped", "sayrams_necklace_equipped", "star_rock_equipped",
)
COMPANION_FULL_SEARCH_KEYS = ("companion_summon_time_increase_pct", "hexagon_necklace_equipped", "horn_flute_equipped", "skill_cooldown_decrease",
                              "arwens_glass_shoes_equipped")
SUMMON_TIME_KEYS = ("companion_summon_time_increase_pct", "arwens_glass_shoes_equipped")

# (hook, base tenths-of-%, factor index, job step, unlock level) of each always-on passive baked into the typed Inputs (all factor 22, scaling)
PASSIVE_LEVELS = (
    PassiveLevel("attack_speed_extra", 50, 22, 2, 33),            # Soul Speed (Attack Speed)
    PassiveLevel("basic_attack_damage_delta", 100, 22, 2, 38),    # Physical Training
    PassiveLevel("min_damage_delta", 150, 22, 2, 43),             # Sword Mastery (Min Damage Multiplier)
    PassiveLevel("attack_mult_delta", 80, 22, 2, 50),             # Divine Hand (Attack %)
    PassiveLevel("final_damage_delta", 150, 22, 3, 75),           # Inner Shout (Final Damage)
    PassiveLevel("attack_mult_delta", 120, 22, 4, 107),           # Soul Pledge (Attack %)
    PassiveLevel("crit_damage_delta", 150, 22, 4, 107),           # Soul Pledge (Crit Damage)
    PassiveLevel("basic_attack_damage_delta", 80, 22, 4, 117),    # Unpredictable (Basic Attack Damage)
    PassiveLevel("final_damage_delta", 50, 22, 4, 117),           # Unpredictable (Final Damage)
    PassiveLevel("skill_damage_delta", 150, 22, 4, 120),          # Student of the Blade (Skill Damage)
    PassiveLevel("max_damage_delta", 300, 22, 4, 120),            # Student of the Blade (Max Damage Multiplier)
)

# potential-line / equipment-dropdown / artifact-potential stat -> sweep key maps; "Defense (flat)" has no sweep row in this class: a key without a rate prices as 0
STAT_TO_KEY = sens_mod.standard_stat_to_key("Str", "flat_str", "str_pct", sub=("Dex", "dex"))

SPEC = SensSpec(
    class_id="dawn_warrior", stat_list=STAT_LIST, mainstat=MainStat("flat_str", "str_pct", subs=(("dex", 0.25),)),
    status_rebuild_keys=STATUS_REBUILD_KEYS, companion_full_search_keys=COMPANION_FULL_SEARCH_KEYS, summon_time_keys=SUMMON_TIME_KEYS,
    passive_levels=PASSIVE_LEVELS, semantics=SEMANTICS, bdi_toggle_wired=True, pin_monster_defense=False, baked_fd_form="typed",
    reindeer_dose_in_rows=True, athena_as_in_aps=True, stat_to_key=STAT_TO_KEY, mult_extra=(("final_damage", "final_damage_extra"),),
)
