"""Marksman Sensitivity spec: the builder's ``STAT_SWEEP`` (stat entries), ``STATUS_REBUILD_KEYS``, ``COMPANION_FULL_SEARCH_KEYS``, ``SUMMON_TIME_KEYS`` and
``PASSIVE_DELTA_SLOT`` of ``src/build_marksman_workbook.py`` (cross-checked against the builder by ``tests/golden/test_sensitivity.py --class marksman``).

Marksman specifics (all reproduced from ``build_stat_block``):

* main stat DEX / sub stat STR (bug 7): ``mainstat_attack_delta = (DEX x (1 + DEX%)) delta + 0.25 x STR delta`` (no Defense stat in this class).
* the passive skills whose level-dependent values are baked into the typed Inputs - Critical Shot (Crit Rate), Archer Mastery and Crossbow Acceleration (Attack Speed),
  Physical Training (Basic Attack Damage), Crossbow Mastery (Min Damage), Reckless Hunt: Crossbow and Last Man Standing's base Final Damage (Final Damage), Crossbow Expert
  (Skill Damage + Max Damage) and Soul Arrow: Crossbow (Attack%, joins the additive Attack% bucket: hook ``attack_mult_delta``) - add the DELTA of their value to a skill-level
  block (``PASSIVE_DELTA_SLOT``).  Critical Shot's Crit Rate delta feeds the live crit rate AND Ring of Cycles' threshold (the block's ``roc_threshold_cr_block`` includes
  ``delta["crit_rate"]``, unlike Hero's).
* Marksman adds Mortal Blow / Last Man Standing's live Final Damage to the typed ``Inputs!final_damage`` INSIDE one additive bucket ``(1 + (typed + passive deltas + Mortal Blow) / 100)``:
  the baked-in Final Damage artifacts (Cursed Doll, Lit Lamp, Clear Spring Water, Soul Pouch, Bottle of Emotion) are a factor on the TYPED value (``baked_fd_form="typed"``; a plain
  factor on the whole product overstated the gain by ~2.5%) and the Final Damage sweep (+1% multiplicative) bumps the FULL bucket including Mortal Blow
  (``MULT_KIND_EXTRA_REF``; ``mult_extra`` -> ``model.mortal_blow_bonus``; the table's Current / New value include it).
* Reindeer's Spear: the block's rows read ``def_pen_total_block`` (the dose reaches the rows' defense reduction, the boss-branch correction and the companion): flag True.
  Shamaness Marble and Athena's Gloves had the two Dark Knight gaps in this builder too and were FIXED on 2026-11-22 (the same day the engine side was added; Sensitivity only, main
  sheets formula-identical): the block's Buff Duration Increase is ``bdi_block = ib(bdi) + shamaness_marble_delta_block`` and its Actions Per Second reads
  ``attack_speed_total_block`` (incl. Athena's direct Attack Speed): flags True.
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
    "final_damage": "the +1% multiplicative step bumps the whole Final Damage bucket, including the live Mortal Blow / Last Man Standing share (Current / New include it)",
    "skill_lvl_1st": "adds Critical Shot's (Crit Rate) and Archer Mastery's (Attack Speed) level deltas",
    "skill_lvl_2nd": "adds Crossbow Acceleration's (Attack Speed), Physical Training's (Basic Attack Damage), Crossbow Mastery's (Min Damage) and Soul Arrow: Crossbow's (Attack%) level deltas",
    "skill_lvl_3rd": "adds Reckless Hunt: Crossbow's Final Damage level delta",
    "skill_lvl_4th": "adds Crossbow Expert's (Skill Damage, Max Damage) and Last Man Standing's (Final Damage) level deltas",
    "skill_lvl_all": "adds every passive's level delta (Critical Shot, Archer Mastery, Crossbow Acceleration, Physical Training, Crossbow Mastery, Reckless Hunt, Last Man Standing, Crossbow Expert, Soul Arrow)",
    "crit_rate": "Book of Ancient (if equipped): Crit Damage follows the crit-rate change",
    "attack_speed": "Athena's Gloves (if equipped): Max Damage follows; Bottle of Emotion (if equipped): Final Damage follows",
}

STATUS_REBUILD_KEYS = (
    "skill_cooldown_decrease", "buff_duration_increase_pct", "shamaness_marble_equipped", "status_effect_damage",
    "companion_summon_time_increase_pct", "hexagon_necklace_equipped", "arwens_glass_shoes_equipped",
    # everything that moves the engine's Attack% bucket (A0 / Charm / Illusion Step's and Marksmanship's F)
    "charm_of_the_undead_equipped", "old_music_box_equipped", "secret_map_equipped", "reindeer_spear_equipped",
    "alliance_badge_equipped", "bottle_of_emotion_equipped", "skill_lvl_2nd", "skill_lvl_3rd", "skill_lvl_4th", "skill_lvl_all",
)
COMPANION_FULL_SEARCH_KEYS = ("companion_summon_time_increase_pct", "hexagon_necklace_equipped", "horn_flute_equipped", "skill_cooldown_decrease",
                              "arwens_glass_shoes_equipped")
SUMMON_TIME_KEYS = ("companion_summon_time_increase_pct", "arwens_glass_shoes_equipped")

# PASSIVE_DELTA_SLOT of the builder: (hook, base tenths-of-%, factor index, job step, unlock level) of each Skills-sheet passive row (all factor 22, scaling)
PASSIVE_LEVELS = (
    PassiveLevel("crit_rate_delta", 50, 22, 1, 15),              # Critical Shot
    PassiveLevel("attack_speed_extra", 50, 22, 1, 10),           # Archer Mastery (Attack Speed)
    PassiveLevel("attack_speed_extra", 50, 22, 2, 33),           # Crossbow Acceleration
    PassiveLevel("basic_attack_damage_delta", 100, 22, 2, 38),   # Physical Training
    PassiveLevel("min_damage_delta", 150, 22, 2, 43),            # Crossbow Mastery
    PassiveLevel("final_damage_delta", 150, 22, 3, 75),          # Extreme Archery / Reckless Hunt: Crossbow
    PassiveLevel("final_damage_delta", 150, 22, 4, 125),         # Last Man Standing (base FD)
    PassiveLevel("skill_damage_delta", 150, 22, 4, 120),         # Crossbow Expert (Skill Damage)
    PassiveLevel("max_damage_delta", 300, 22, 4, 120),           # Crossbow Expert (Max Damage Multiplier)
    PassiveLevel("attack_mult_delta", 120, 22, 2, 45),           # Soul Arrow: Crossbow (Attack%)
)

# the builder's POTENTIAL_STAT_TO_SWEEP_KEY / POTENTIAL_SUB_STAT_PCT_LINES / EQUIP_COMPARE_STAT_TO_SWEEP_KEY / ARTIFACT_POTENTIAL_STAT_TO_SWEEP_KEY (checked against it by
# tests/golden/test_sensitivity.py::test_static[marksman]); "Defense (flat)" has no sweep row in this class: a key without a rate prices as 0
STAT_TO_KEY = sens_mod.standard_stat_to_key("Dex", "flat_dex", "dex_pct", sub=("Str", "str"))

SPEC = SensSpec(
    class_id="marksman", stat_list=STAT_LIST, mainstat=MainStat("flat_dex", "dex_pct", subs=(("str", 0.25),)),
    status_rebuild_keys=STATUS_REBUILD_KEYS, companion_full_search_keys=COMPANION_FULL_SEARCH_KEYS, summon_time_keys=SUMMON_TIME_KEYS,
    passive_levels=PASSIVE_LEVELS, semantics=SEMANTICS, bdi_toggle_wired=True, pin_monster_defense=False, baked_fd_form="typed",
    reindeer_dose_in_rows=True, athena_as_in_aps=True, stat_to_key=STAT_TO_KEY, mult_extra=(("final_damage", "mortal_blow_bonus"),),
)
