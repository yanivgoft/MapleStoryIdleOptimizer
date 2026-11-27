"""Wind Archer Sensitivity spec (engine-native, PROVISIONAL: no workbook builder exists, so nothing is cross-checked against one; the structure copies Blaze Wizard's / Bowmaster's).

Wind Archer specifics:

* main stat DEX / sub stat STR (bug 7): ``mainstat_attack_delta = (DEX x (1 + DEX%)) delta + 0.25 x STR delta``.
* the always-on passives whose level-dependent values are baked into the typed Inputs (the stat screen contains them) add the DELTA of their value to a skill-level block
  (``PASSIVE_LEVELS``): Whispers of the Wind, Sylvan Aid, Second Wind and Touch of the Wind (Attack %, ``attack_mult_delta``: applied to the typed ATTACK %), Whispers and Agile Bows (Attack
  Speed), Physical Training (Basic Attack Damage), Bow Mastery (Min Damage), Sylvan Aid (Critical Rate), Featherweight (Damage, Normal Monster Damage, and from Lv98 Boss Monster Damage = half),
  Eagle Eye and Albatross Max (Final Damage, additive next to the typed value), Albatross Max (Defense Penetration), Bow Expert (Skill Damage, Max Damage).  The conditional / timed effects
  (Storm Elemental, Sharp Eyes, Elemental Harmony, Second Wind's Attack Speed, Emerald Flower / Dust, Pinpoint Pierce's weaken, Trifling Wind, Storm Bringer, Call of Cygnus) are LIVE in the model
  and need no delta.
* Wind Archer retypes ``Inputs!final_damage`` INSIDE the additive Final Damage bucket (typed + the live Emerald Dust share + passive deltas): the baked-in Final Damage artifacts are a factor on
  the TYPED value (``baked_fd_form="typed"``) and the Final Damage sweep bumps the full bucket (``mult_extra``), like Hero / Blaze Wizard.
* The Status/KO strip has no engine-timed buff, so the rebuild set is only what moves cooldowns, the per-cast weights' relative sizes and the strip's constant Attack % / Hexagon / Charm.
"""
from ..common import sens as sens_mod
from ..common.sens import MainStat, PassiveLevel, SensSpec

STAT_LIST = sens_mod.stat_list((
    ("flat_dex", "Flat DEX", "flat"),
    ("dex_pct", "DEX %", "pct"),
    ("str", "STR", "flat"),
))

_DEX_NOTE = "adds the main stat's flat-Attack channel (1 DEX = 1 Attack, 1 STR = 0.25 Attack, before ATTACK%) next to STAT_DAMAGE"
SEMANTICS = {
    "flat_dex": _DEX_NOTE,
    "dex_pct": _DEX_NOTE,
    "str": _DEX_NOTE,
    "final_damage": "the +1% multiplicative step bumps the whole Final Damage bucket, including the live Emerald Dust share (Current / New include it)",
    "skill_lvl_1st": "adds Whispers of the Wind's (Attack %, Attack Speed) level deltas",
    "skill_lvl_2nd": "adds Agile Bows' (Attack Speed), Physical Training's (Basic Attack Damage), Bow Mastery's (Min Damage) and Sylvan Aid's (Attack %, Critical Rate) level deltas",
    "skill_lvl_3rd": "adds Second Wind's (Attack %), Featherweight's (Damage, Normal / Boss Monster Damage) and Eagle Eye's (Final Damage) level deltas",
    "skill_lvl_4th": "adds Touch of the Wind's (Attack %), Bow Expert's (Skill Damage, Max Damage) and Albatross Max's (Final Damage, Defense Penetration) level deltas",
    "skill_lvl_all": "adds every passive's level delta (Whispers of the Wind, Agile Bows, Physical Training, Bow Mastery, Sylvan Aid, Second Wind, Featherweight, Eagle Eye, Touch of the Wind, Bow Expert, Albatross Max)",
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

# (hook, base tenths-of-%, factor index, job step, unlock level) of each always-on passive baked into the typed Inputs (all PROVISIONAL, factor 22 by convention: see
# engine/data/wind_archer.py CURVES, which this table mirrors)
PASSIVE_LEVELS = (
    PassiveLevel("attack_mult_delta", 30, 22, 1, None),           # Whispers of the Wind (Attack %)
    PassiveLevel("attack_speed_extra", 30, 22, 1, None),          # Whispers of the Wind (Attack Speed)
    PassiveLevel("attack_speed_extra", 50, 22, 2, 33),            # Agile Bows (Attack Speed)
    PassiveLevel("basic_attack_damage_delta", 100, 22, 2, 38),    # Physical Training (Basic Attack Damage)
    PassiveLevel("min_damage_delta", 150, 22, 2, 43),             # Bow Mastery (Min Damage Multiplier)
    PassiveLevel("attack_mult_delta", 120, 22, 2, 45),            # Sylvan Aid (Attack %)
    PassiveLevel("crit_rate_delta", 60, 22, 2, 45),               # Sylvan Aid (Critical Rate)
    PassiveLevel("attack_mult_delta", 120, 22, 3, 72),            # Second Wind (Attack %)
    PassiveLevel("damage_delta", 300, 22, 3, 74),                 # Featherweight (Damage)
    PassiveLevel("normal_damage_delta", 150, 22, 3, 74),          # Featherweight (Normal Monster Damage)
    PassiveLevel("boss_damage_delta", 75, 22, 3, 98),             # Featherweight - Boss Monster Damage (half of the Normal Monster Damage boost)
    PassiveLevel("final_damage_delta", 150, 22, 3, 75),           # Eagle Eye (Final Damage)
    PassiveLevel("attack_mult_delta", 100, 22, 4, 117),           # Touch of the Wind (Attack %)
    PassiveLevel("skill_damage_delta", 150, 22, 4, 120),          # Bow Expert (Skill Damage)
    PassiveLevel("max_damage_delta", 300, 22, 4, 120),            # Bow Expert (Max Damage Multiplier)
    PassiveLevel("final_damage_delta", 100, 22, 4, 125),          # Albatross Max (Final Damage)
    PassiveLevel("def_pen_delta", 80, 22, 4, 125),                # Albatross Max (Defense Penetration)
)

# potential-line / equipment-dropdown / artifact-potential stat -> sweep key maps; "Defense (flat)" has no sweep row in this class: a key without a rate prices as 0
STAT_TO_KEY = sens_mod.standard_stat_to_key("Dex", "flat_dex", "dex_pct", sub=("Str", "str"))

SPEC = SensSpec(
    class_id="wind_archer", stat_list=STAT_LIST, mainstat=MainStat("flat_dex", "dex_pct", subs=(("str", 0.25),)),
    status_rebuild_keys=STATUS_REBUILD_KEYS, companion_full_search_keys=COMPANION_FULL_SEARCH_KEYS, summon_time_keys=SUMMON_TIME_KEYS,
    passive_levels=PASSIVE_LEVELS, semantics=SEMANTICS, bdi_toggle_wired=True, pin_monster_defense=False, baked_fd_form="typed",
    reindeer_dose_in_rows=True, athena_as_in_aps=True, stat_to_key=STAT_TO_KEY, mult_extra=(("final_damage", "final_damage_extra"),),
)
