"""Blaze Wizard Sensitivity spec (engine-native, PROVISIONAL: no workbook builder exists, so nothing is cross-checked against one; the structure copies Dawn Warrior's / FP-Mage's).

Blaze Wizard specifics:

* main stat INT / sub stat LUK (bug 7): ``mainstat_attack_delta = (INT x (1 + INT%)) delta + 0.25 x LUK delta``.
* the always-on passives whose level-dependent values are baked into the typed Inputs (the stat screen contains them) add the DELTA of their value to a skill-level block
  (``PASSIVE_LEVELS``): Fire Repulsion and Flame Barrier (Attack %, ``attack_mult_delta``: applied to the typed ATTACK %), Word of Fire (Attack Speed), Spell Control and Brilliant
  Enlightenment (Min / Max Damage), Burning Focus (Crit Rate, Crit Damage), Liberated Magic, Phoenix Run and Wild Blaze (Final Damage, additive next to the typed value), Pure Magic
  (Skill Damage, Max Damage), Fires of Creation's equipped Final Damage.  The conditional / timed effects (Flame Elemental and its Greater / Grand / Final sub-effects, Flashfire,
  Burning Conduit, Fires of Creation's Lion / Fox damage, Call of Cygnus, Orbital Explosion, Cinder Maelstrom's weaken) are LIVE in the model and need no delta.
* Blaze Wizard retypes ``Inputs!final_damage`` INSIDE the additive Final Damage bucket (typed + the live Final Flame Elemental / Burning Conduit share + passive deltas): the baked-in Final
  Damage artifacts are a factor on the TYPED value (``baked_fd_form="typed"``) and the Final Damage sweep bumps the full bucket (``mult_extra``), like Hero / Dawn Warrior.
* The Status/KO strip has no engine-timed buff, so the rebuild set is only what moves cooldowns, the per-cast weights' relative sizes and the strip's constant Attack % / Hexagon / Charm.
* Two things are NOT sweepable deltas: Wild Blaze's +6 % Buff Duration (a typed input, its level dependence is unknown) and the passives' mastery raw values (do not scale).
"""
from ..common import sens as sens_mod
from ..common.sens import MainStat, PassiveLevel, SensSpec

STAT_LIST = sens_mod.stat_list((
    ("flat_int", "Flat INT", "flat"),
    ("int_pct", "INT %", "pct"),
    ("luk", "LUK", "flat"),
))

_INT_NOTE = "adds the main stat's flat-Attack channel (1 INT = 1 Attack, 1 LUK = 0.25 Attack, before ATTACK%) next to STAT_DAMAGE"
SEMANTICS = {
    "flat_int": _INT_NOTE,
    "int_pct": _INT_NOTE,
    "luk": _INT_NOTE,
    "final_damage": "the +1% multiplicative step bumps the whole Final Damage bucket, including the live Final Flame Elemental / Burning Conduit share (Current / New include it)",
    "skill_lvl_1st": "adds Fire Repulsion's (Attack %) level delta",
    "skill_lvl_2nd": "adds Word of Fire's (Attack Speed), Spell Control's (Min Damage) and Fires of Creation's (Final Damage) level deltas",
    "skill_lvl_3rd": "adds Brilliant Enlightenment's (Min / Max Damage), Burning Focus' (Crit Rate / Crit Damage) and Liberated Magic's (Final Damage) level deltas",
    "skill_lvl_4th": "adds Phoenix Run's and Wild Blaze's (Final Damage), Flame Barrier's (Attack %) and Pure Magic's (Skill Damage, Max Damage) level deltas",
    "skill_lvl_all": "adds every passive's level delta (Fire Repulsion, Word of Fire, Spell Control, Fires of Creation, Brilliant Enlightenment, Burning Focus, Liberated Magic, Phoenix Run, Wild Blaze, Flame Barrier, Pure Magic)",
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

# (hook, base tenths-of-%, factor index, job step, unlock level) of each always-on passive baked into the typed Inputs (all PROVISIONAL, factor 22 / 21 by convention: see
# engine/data/blaze_wizard.py CURVES, which this table mirrors)
PASSIVE_LEVELS = (
    PassiveLevel("attack_mult_delta", 30, 22, 1, None),           # Fire Repulsion (Attack %)
    PassiveLevel("attack_speed_extra", 50, 22, 2, 33),            # Word of Fire (Attack Speed)
    PassiveLevel("min_damage_delta", 150, 22, 2, 43),             # Spell Control (Min Damage Multiplier)
    PassiveLevel("final_damage_delta", 30, 21, 2, 50),            # Fires of Creation (Final Damage while equipped; an active skill: idx 21)
    PassiveLevel("min_damage_delta", 100, 22, 3, 66),             # Brilliant Enlightenment (Min Damage Multiplier)
    PassiveLevel("max_damage_delta", 200, 22, 3, 66),             # Brilliant Enlightenment (Max Damage Multiplier)
    PassiveLevel("crit_rate_delta", 80, 22, 3, 72),               # Burning Focus (Crit Rate)
    PassiveLevel("crit_damage_delta", 160, 22, 3, 72),            # Burning Focus (Crit Damage)
    PassiveLevel("final_damage_delta", 150, 22, 3, 75),           # Liberated Magic (Final Damage, MP >= 35 %)
    PassiveLevel("final_damage_delta", 100, 22, 4, 107),          # Phoenix Run (Final Damage) ...
    PassiveLevel("final_damage_delta", 100, 22, 4, 118),          # ... + the Lv118 mastery "boost +100 %" (x2 = a second copy of the same curve)
    PassiveLevel("attack_mult_delta", 50, 22, 4, 117),            # Flame Barrier (Attack %)
    PassiveLevel("skill_damage_delta", 150, 22, 4, 120),          # Pure Magic (Skill Damage)
    PassiveLevel("max_damage_delta", 200, 22, 4, 120),            # Pure Magic (Max Damage Multiplier)
    PassiveLevel("final_damage_delta", 120, 22, 4, 125),          # Wild Blaze (Final Damage)
)

# potential-line / equipment-dropdown / artifact-potential stat -> sweep key maps; "Defense (flat)" has no sweep row in this class: a key without a rate prices as 0
STAT_TO_KEY = sens_mod.standard_stat_to_key("Int", "flat_int", "int_pct", sub=("Luk", "luk"))

SPEC = SensSpec(
    class_id="blaze_wizard", stat_list=STAT_LIST, mainstat=MainStat("flat_int", "int_pct", subs=(("luk", 0.25),)),
    status_rebuild_keys=STATUS_REBUILD_KEYS, companion_full_search_keys=COMPANION_FULL_SEARCH_KEYS, summon_time_keys=SUMMON_TIME_KEYS,
    passive_levels=PASSIVE_LEVELS, semantics=SEMANTICS, bdi_toggle_wired=True, pin_monster_defense=False, baked_fd_form="typed",
    reindeer_dose_in_rows=True, athena_as_in_aps=True, stat_to_key=STAT_TO_KEY, mult_extra=(("final_damage", "final_damage_extra"),),
)
