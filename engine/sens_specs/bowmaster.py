"""Bowmaster Sensitivity spec: the builder's ``STAT_SWEEP`` (stat entries), ``STATUS_REBUILD_KEYS``, ``COMPANION_FULL_SEARCH_KEYS``, ``SUMMON_TIME_KEYS`` and
``PASSIVE_DELTA_SLOT`` of ``src/build_bowmaster_workbook.py`` (cross-checked against the builder by ``tests/golden/test_sensitivity.py --class bowmaster``).

Bowmaster specifics (all reproduced from ``build_stat_block``):

* main stat DEX / sub stat STR (bug 7): ``mainstat_attack_delta = (DEX x (1 + DEX%)) delta + 0.25 x STR delta`` (no Defense stat in this class).
* the passive skills whose level-dependent values are baked into the typed Inputs - Critical Shot (Crit Rate), Archer Mastery and Bow Acceleration (Attack Speed), Physical
  Training (Basic Attack Damage), Bow Mastery (Min Damage), Extreme Archery / Reckless Hunt: Bow and Armor Break (Final Damage), Armor Break (Defense Penetration: hook
  ``def_pen_delta``, added to the typed Def Pen BEFORE Reindeer's dose), Bow Expert (Skill Damage + Max Damage) and Soul Arrow: Bow (Attack%, joins the additive Attack% bucket:
  hook ``attack_mult_delta``) - add the DELTA of their value to a skill-level block (``PASSIVE_DELTA_SLOT``).  Critical Shot's Crit Rate delta feeds the live crit rate AND
  Ring of Cycles' threshold (``roc_threshold_cr_block`` includes ``delta["crit_rate"]``).
* Final Damage: the block's bracket is ``(1 + (typed + passive deltas + Mortal Blow)/100)`` times the artifact bucket ``(1 + agg/100)``; the baked-in Final Damage artifacts
  (Cursed Doll, Lit Lamp, Clear Spring Water, Soul Pouch, Bottle of Emotion) are a FACTOR on the artifact bucket (``fd_baked_factor`` helper cells in column U), i.e. a factor on the
  whole product (``baked_fd_form="factor"``; typing the artifact into the Inputs is ``((1+(fd+mb)/100)(1+x/100)-1) x 100 - mb``, the same bump of the bracket).  The Final Damage sweep
  (+1% multiplicative) bumps the FULL bracket including Mortal Blow (``MULT_KIND_EXTRA_REF``; ``mult_extra`` -> ``model.mortal_blow_bonus``; the table's Current / New include it).
* Reindeer's Spear: the block's rows read ``def_pen_total_block`` (the dose reaches the rows' defense reduction, the boss-branch correction and the companion): flag True.
  Shamaness Marble and Athena's Gloves had the two Dark Knight gaps in this builder too (Shamaness inert, Athena's direct Attack Speed missing from the block's Actions Per Second) and
  were FIXED on 2026-11-22 (Sensitivity only, main sheets formula-identical): ``bdi_block = (ib(bdi) + shamaness_marble_delta_block)`` and ``s_aps`` reads
  ``attack_speed_total_block``: flags True.
* Illusion Step's Lv118 boost is re-derived from the block's own ``E`` (bug 19, fixed earlier), so the engine's own-level ``coeff_pct`` is the right model; Quiver Cartridge /
  Enchanted Quiver's attack-speed-scaled cooldown reads the block's own APS.
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
    "final_damage": "the +1% multiplicative step bumps the whole Final Damage bracket, including the live Mortal Blow share (Current / New include it)",
    "skill_lvl_1st": "adds Critical Shot's (Crit Rate) and Archer Mastery's (Attack Speed) level deltas",
    "skill_lvl_2nd": "adds Bow Acceleration's (Attack Speed), Physical Training's (Basic Attack Damage), Bow Mastery's (Min Damage) and Soul Arrow: Bow's (Attack%) level deltas",
    "skill_lvl_3rd": "adds Reckless Hunt: Bow's Final Damage level delta",
    "skill_lvl_4th": "adds Armor Break's (Final Damage, Defense Penetration) and Bow Expert's (Skill Damage, Max Damage) level deltas",
    "skill_lvl_all": "adds every passive's level delta (Critical Shot, Archer Mastery, Bow Acceleration, Physical Training, Bow Mastery, Reckless Hunt, Armor Break, Bow Expert, Soul Arrow)",
    "crit_rate": "Book of Ancient (if equipped): Crit Damage follows the crit-rate change",
    "attack_speed": "Athena's Gloves (if equipped): Max Damage follows; Bottle of Emotion (if equipped): Final Damage follows",
}

STATUS_REBUILD_KEYS = (
    "skill_cooldown_decrease", "buff_duration_increase_pct", "shamaness_marble_equipped", "status_effect_damage",
    "companion_summon_time_increase_pct", "hexagon_necklace_equipped", "arwens_glass_shoes_equipped",
    # everything that moves the engine's Attack% bucket (A0 / Charm / Illusion Step's and Marksmanship's F)
    "charm_of_the_undead_equipped", "old_music_box_equipped", "secret_map_equipped", "reindeer_spear_equipped",
    "alliance_badge_equipped", "bottle_of_emotion_equipped", "skill_lvl_2nd", "skill_lvl_3rd", "skill_lvl_4th", "skill_lvl_all",
    # the strip consumes the per-cast damage weights and the basic attack a cast replaces, through their RELATIVE sizes
    "skill_damage", "basic_attack_damage", "boss_damage", "crit_rate", "attack_speed",
    "ring_of_cycles_equipped", "book_of_ancient_equipped", "rainbow_snail_shell_equipped",
    "candle_equipped", "sayrams_necklace_equipped", "star_rock_equipped", "peach_tree_equipped", "silver_pendant_equipped",
)
COMPANION_FULL_SEARCH_KEYS = ("companion_summon_time_increase_pct", "hexagon_necklace_equipped", "horn_flute_equipped", "skill_cooldown_decrease",
                              "arwens_glass_shoes_equipped")
SUMMON_TIME_KEYS = ("companion_summon_time_increase_pct", "arwens_glass_shoes_equipped")

# PASSIVE_DELTA_SLOT of the builder: (hook, base tenths-of-%, factor index, job step, unlock level) of each Skills-sheet passive row (all factor 22, scaling)
PASSIVE_LEVELS = (
    PassiveLevel("crit_rate_delta", 50, 22, 1, 15),              # Critical Shot
    PassiveLevel("attack_speed_extra", 50, 22, 1, 10),           # Archer Mastery (Attack Speed)
    PassiveLevel("attack_speed_extra", 50, 22, 2, 33),           # Bow Acceleration
    PassiveLevel("basic_attack_damage_delta", 100, 22, 2, 38),   # Physical Training
    PassiveLevel("min_damage_delta", 150, 22, 2, 43),            # Bow Mastery
    PassiveLevel("final_damage_delta", 150, 22, 3, 75),          # Extreme Archery / Reckless Hunt: Bow
    PassiveLevel("final_damage_delta", 100, 22, 4, 125),         # Armor Break (Final Damage)
    PassiveLevel("def_pen_delta", 100, 22, 4, 125),              # Armor Break (Defense Penetration)
    PassiveLevel("skill_damage_delta", 150, 22, 4, 120),         # Bow Expert (Skill Damage)
    PassiveLevel("max_damage_delta", 200, 22, 4, 120),           # Bow Expert (Max Damage Multiplier)
    PassiveLevel("attack_mult_delta", 80, 22, 2, 45),            # Soul Arrow: Bow (Attack%)
)

# the builder's POTENTIAL_STAT_TO_SWEEP_KEY / POTENTIAL_SUB_STAT_PCT_LINES / EQUIP_COMPARE_STAT_TO_SWEEP_KEY / ARTIFACT_POTENTIAL_STAT_TO_SWEEP_KEY (checked against it by
# tests/golden/test_sensitivity.py::test_static[bowmaster]); "Defense (flat)" has no sweep row in this class: a key without a rate prices as 0
STAT_TO_KEY = sens_mod.standard_stat_to_key("Dex", "flat_dex", "dex_pct", sub=("Str", "str"))

SPEC = SensSpec(
    class_id="bowmaster", stat_list=STAT_LIST, mainstat=MainStat("flat_dex", "dex_pct", subs=(("str", 0.25),)),
    status_rebuild_keys=STATUS_REBUILD_KEYS, companion_full_search_keys=COMPANION_FULL_SEARCH_KEYS, summon_time_keys=SUMMON_TIME_KEYS,
    passive_levels=PASSIVE_LEVELS, semantics=SEMANTICS, bdi_toggle_wired=True, pin_monster_defense=False, baked_fd_form="factor",
    reindeer_dose_in_rows=True, athena_as_in_aps=True, stat_to_key=STAT_TO_KEY, mult_extra=(("final_damage", "mortal_blow_bonus"),),
)
