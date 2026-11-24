"""Night Walker Sensitivity spec (engine-native: no workbook builder exists, so nothing is cross-checked against one; the structure copies Dawn Warrior's / Night Lord's).

Night Walker specifics:

* main stat LUK / sub stat DEX (bug 7): ``mainstat_attack_delta = (LUK x (1 + LUK%)) delta + 0.25 x DEX delta``.
* the always-on passives whose level-dependent values are baked into the typed Inputs (the stat screen contains them) add the DELTA of their value to a skill-level block
  (``PASSIVE_LEVELS``, values / factor index 22 / job step / unlock level all from the site table): Agile Throwing (Attack Speed), Physical Training (Basic Attack Damage), Throwing Mastery
  (Min Damage), Critical Throw (Crit Rate AND Crit Damage), Enveloping Darkness (Boss Damage), Spirit Projection and Vitality Siphon (Attack %, ``attack_mult_delta``: applied to the typed
  ATTACK %), Throwing Expert (Skill Damage and Max Damage), Dark Blessing (Final Damage, additive next to the typed value, and Defense Penetration, ``def_pen_delta``).  The conditional /
  timed / per-skill effects (Dark Elemental, Darkness Ascending, Dark Evasion, Shadow Momentum, Shadow Double, Call of Cygnus, Bat Affinity I-III, Adaptive Darkness I-III, Shadow Bat, Mark of
  Darkness) are LIVE in the model and need no delta.  (Enveloping Darkness' / Vitality Siphon's Max HP and barrier have no DPS effect.)
* Night Walker retypes ``Inputs!final_damage`` INSIDE the additive Final Damage bucket (typed + Dark Evasion's live share + passive deltas): the baked-in Final Damage artifacts are a factor
  on the TYPED value (``baked_fd_form="typed"``) and the Final Damage sweep bumps the full bucket (``mult_extra``), like Dawn Warrior.
* The Status/KO strip has no engine-timed buff, so the rebuild set is only what moves cooldowns, the per-cast weights' relative sizes and the strip's constant Attack % / Hexagon / Charm.
"""
from ..common import sens as sens_mod
from ..common.sens import MainStat, PassiveLevel, SensSpec

STAT_LIST = sens_mod.stat_list((
    ("flat_luk", "Flat LUK", "flat"),
    ("luk_pct", "LUK %", "pct"),
    ("dex", "DEX", "flat"),
))

_LUK_NOTE = "adds the main stat's flat-Attack channel (1 LUK = 1 Attack, 1 DEX = 0.25 Attack, before ATTACK%) next to STAT_DAMAGE"
SEMANTICS = {
    "flat_luk": _LUK_NOTE,
    "luk_pct": _LUK_NOTE,
    "dex": _LUK_NOTE,
    "final_damage": "the +1% multiplicative step bumps the whole Final Damage bucket, including the live Dark Evasion share (Current / New include it)",
    "skill_lvl_2nd": "adds Agile Throwing's (Attack Speed), Physical Training's (Basic Attack Damage), Throwing Mastery's (Min Damage) and Critical Throw's (Crit Rate, Crit Damage) level deltas",
    "skill_lvl_3rd": "adds Enveloping Darkness' (Boss Damage) and Spirit Projection's (Attack %) level deltas",
    "skill_lvl_4th": "adds Vitality Siphon's (Attack %), Throwing Expert's (Skill Damage, Max Damage) and Dark Blessing's (Final Damage, Defense Penetration) level deltas",
    "skill_lvl_all": "adds every passive's level delta (Agile Throwing, Physical Training, Throwing Mastery, Critical Throw, Enveloping Darkness, Spirit Projection, Vitality Siphon, Throwing Expert, Dark Blessing)",
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

# (hook, base tenths-of-%, factor index, job step, unlock level) of each always-on passive baked into the typed Inputs (all factor 22, scaling; the site table's statOps)
PASSIVE_LEVELS = (
    PassiveLevel("attack_speed_extra", 50, 22, 2, 33),            # Agile Throwing (Attack Speed)
    PassiveLevel("basic_attack_damage_delta", 100, 22, 2, 38),    # Physical Training
    PassiveLevel("min_damage_delta", 150, 22, 2, 43),             # Throwing Mastery (Min Damage Multiplier)
    PassiveLevel("crit_rate_delta", 60, 22, 2, 45),               # Critical Throw (Crit Rate)
    PassiveLevel("crit_damage_delta", 100, 22, 2, 45),            # Critical Throw (Crit Damage)
    PassiveLevel("boss_damage_delta", 180, 22, 3, 60),            # Enveloping Darkness (Boss Monster Damage)
    PassiveLevel("attack_mult_delta", 150, 22, 3, 75),            # Spirit Projection (Attack %)
    PassiveLevel("attack_mult_delta", 150, 22, 4, 117),           # Vitality Siphon (Attack %)
    PassiveLevel("skill_damage_delta", 150, 22, 4, 120),          # Throwing Expert (Skill Damage)
    PassiveLevel("max_damage_delta", 200, 22, 4, 120),            # Throwing Expert (Max Damage Multiplier)
    PassiveLevel("final_damage_delta", 120, 22, 4, 125),          # Dark Blessing (Final Damage)
    PassiveLevel("def_pen_delta", 50, 22, 4, 125),                # Dark Blessing (Defense Penetration)
)

# potential-line / equipment-dropdown / artifact-potential stat -> sweep key maps; "Defense (flat)" has no sweep row in this class: a key without a rate prices as 0
STAT_TO_KEY = sens_mod.standard_stat_to_key("Luk", "flat_luk", "luk_pct", sub=("Dex", "dex"))

SPEC = SensSpec(
    class_id="night_walker", stat_list=STAT_LIST, mainstat=MainStat("flat_luk", "luk_pct", subs=(("dex", 0.25),)),
    status_rebuild_keys=STATUS_REBUILD_KEYS, companion_full_search_keys=COMPANION_FULL_SEARCH_KEYS, summon_time_keys=SUMMON_TIME_KEYS,
    passive_levels=PASSIVE_LEVELS, semantics=SEMANTICS, bdi_toggle_wired=True, pin_monster_defense=False, baked_fd_form="typed",
    reindeer_dose_in_rows=True, athena_as_in_aps=True, stat_to_key=STAT_TO_KEY, mult_extra=(("final_damage", "final_damage_extra"),),
)
