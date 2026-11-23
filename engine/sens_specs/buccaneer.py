"""Buccaneer Sensitivity spec: the builder's ``STAT_SWEEP`` (stat entries), ``STATUS_REBUILD_KEYS``, ``COMPANION_FULL_SEARCH_KEYS``, ``SUMMON_TIME_KEYS`` and
``PASSIVE_DELTA_SLOT`` of ``src/build_buccaneer_workbook.py`` (cross-checked against the builder by ``tests/golden/test_buccaneer_sensitivity.py``).

Buccaneer specifics (all reproduced from ``build_stat_block``):

* main stat STR / sub stat DEX (bug 7): ``mainstat_attack_delta = (STR x (1 + STR%)) delta + 0.25 x DEX delta`` (no Defense stat in this class).
* the passive skills whose level-dependent values are baked into the typed Inputs - Shadow Heart (Crit Rate), Quick Motion / Agile Knuckles (Attack Speed), Dark Clarity
  (Attack%, the ``attack_mult_delta`` hook: it joins the additive Attack% bucket next to Roll of the Dice's dice component, the strip's A0 and the companion's snapshot),
  Knuckle Mastery (Min Damage), Physical Training (Basic Attack Damage) and Groggy Mastery (Final Damage, additive next to the typed value) - add the DELTA of their value to
  a skill-level block (``PASSIVE_DELTA_SLOT``).  Shadow Heart's Crit Rate delta feeds the live crit rate AND Ring of Cycles' threshold (``roc_threshold_cr_block`` includes
  ``delta["crit_rate"]`` here, unlike Hero).  The Attack Speed deltas move the block's Actions Per Second, the Speed Infusion APS (its Final Damage = 20 x (APS - 1)) and the
  companion snapshot's.  1st / 2nd job levels therefore re-solve the strip (``skill_lvl_1st`` / ``_2nd`` in ``STATUS_REBUILD_KEYS``).
* Buccaneer retypes ``Inputs!final_damage`` INSIDE the additive Final Damage bucket ``(1 + (final_damage + Groggy delta + R_FD_BONUS) / 100)`` (R_FD_BONUS = Serpent Scale +
  Speed Infusion [+ Crossbones + Time Leap while the strip is off]): the baked-in Final Damage artifacts (Cursed Doll, Lit Lamp, Clear Spring Water, Soul Pouch, Bottle of
  Emotion) are a factor on the TYPED value, not on the artifact bucket (``baked_fd_form="typed"``), and the Final Damage sweep (+1% multiplicative) bumps the FULL bucket
  including the buffs' live share (``MULT_KIND_EXTRA_REF`` = Summary R_FD_ALL = all four buffs at the current cast counts, the strip's counts for Crossbones / Time Leap when it
  is on; ``mult_extra`` -> ``model.final_damage_all``; the table's Current / New include it).
* Reindeer's Spear: the block's K formula reads ``def_pen_total_block`` (the dose reaches the rows' defense reduction, the boss-branch correction and the companion): flag True.
  Shamaness Marble: wired into ``bdi_block`` (builder fixed 2026-11-22: the helper cell was defined and never read, the row was inert); the toggle moves every buff uptime, the
  Assault Mark window and the strip's buff durations.  Athena's Gloves: the block's Actions Per Second, Speed Infusion APS and companion snapshot now include the gloves' direct
  Attack Speed (``attack_speed_total_block``, builder fixed 2026-11-22: before it the row only saw the dependent Max Damage): flag True.  That direct Attack Speed also moves
  the timeline strip (Speed Infusion's Final Damage in ``fd_scale``, the Assault Mode uptime), so the toggle re-solves its own strip (``athena_gloves_equipped`` is in
  ``STATUS_REBUILD_KEYS`` since the same fix; without it the adding row read +0.6% and the removing row +0.5% above the true delta).
* No live crit-rate source exists in this kit (``crit_rate_bonus`` = 0): the artifact crit rate (Ring of Cycles / Rainbow Snail Shell) is ``model.art_crit_rate``.
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
    "final_damage": "the +1% multiplicative step bumps the whole Final Damage bucket, including the live Serpent Scale / Crossbones / Time Leap / Speed Infusion share (Current / New include it)",
    "skill_lvl_1st": "adds Shadow Heart's (Crit Rate) and Quick Motion's (Attack Speed) level deltas",
    "skill_lvl_2nd": "adds Agile Knuckles' (Attack Speed), Dark Clarity's (Attack%), Knuckle Mastery's (Min Damage) and Physical Training's (Basic Attack Damage) level deltas",
    "skill_lvl_3rd": "adds Groggy Mastery's Final Damage level delta",
    "skill_lvl_all": "adds every passive's level delta (Shadow Heart, Quick Motion, Agile Knuckles, Dark Clarity, Knuckle Mastery, Physical Training, Groggy Mastery)",
    "crit_rate": "Book of Ancient (if equipped): Crit Damage follows the crit-rate change",
    "attack_speed": "Athena's Gloves (if equipped): Max Damage follows; Bottle of Emotion (if equipped): Final Damage follows",
}

STATUS_REBUILD_KEYS = (
    "skill_cooldown_decrease", "buff_duration_increase_pct", "shamaness_marble_equipped", "status_effect_damage",
    "companion_summon_time_increase_pct", "hexagon_necklace_equipped", "arwens_glass_shoes_equipped",
    # everything that moves the strip's buff bucket (A0 incl. Charm / Roll of the Dice / the Attack% artifacts, the Final Damage scale of Crossbones / Time Leap)
    "charm_of_the_undead_equipped", "old_music_box_equipped", "secret_map_equipped", "reindeer_spear_equipped",
    "alliance_badge_equipped", "bottle_of_emotion_equipped", "skill_lvl_3rd", "skill_lvl_4th", "skill_lvl_all", "final_damage",
    "attack_speed", "skill_lvl_1st", "skill_lvl_2nd",
    # Athena's Gloves' direct Attack Speed moves the strip like the Attack Speed sweep (builder fixed 2026-11-22)
    "athena_gloves_equipped",
    "cursed_doll_equipped", "lit_lamp_equipped", "clear_spring_water_equipped", "soul_pouch_equipped",
    # Sensitivity fix 1 (2026-11-20): stats that change the RELATIVE per-cast weights (skill vs Hook Bomber, its own Boss Mastery, Ring of Cycles)
    "skill_damage", "basic_attack_damage", "boss_damage", "crit_rate",
    "ring_of_cycles_equipped", "book_of_ancient_equipped", "rainbow_snail_shell_equipped",
    "candle_equipped", "sayrams_necklace_equipped", "star_rock_equipped",
)
COMPANION_FULL_SEARCH_KEYS = ("companion_summon_time_increase_pct", "hexagon_necklace_equipped", "horn_flute_equipped", "skill_cooldown_decrease",
                              "arwens_glass_shoes_equipped")
SUMMON_TIME_KEYS = ("companion_summon_time_increase_pct", "arwens_glass_shoes_equipped")

# PASSIVE_DELTA_SLOT of the builder: (hook, base tenths-of-%, factor index, job step, unlock level) of each Skills-sheet passive row (all factor 22, scaling)
PASSIVE_LEVELS = (
    PassiveLevel("crit_rate_delta", 50, 22, 1, 10),             # Shadow Heart
    PassiveLevel("attack_speed_extra", 60, 22, 1, 15),          # Quick Motion
    PassiveLevel("attack_speed_extra", 50, 22, 2, 33),          # Agile Knuckles
    PassiveLevel("attack_mult_delta", 120, 22, 2, 40),          # Dark Clarity (Attack%)
    PassiveLevel("min_damage_delta", 150, 22, 2, 43),           # Knuckle Mastery
    PassiveLevel("basic_attack_damage_delta", 100, 22, 2, 38),  # Physical Training
    PassiveLevel("final_damage_delta", 80, 22, 3, 75),          # Groggy Mastery
)

# the builder's POTENTIAL_STAT_TO_SWEEP_KEY / POTENTIAL_SUB_STAT_PCT_LINES / EQUIP_COMPARE_STAT_TO_SWEEP_KEY / ARTIFACT_POTENTIAL_STAT_TO_SWEEP_KEY (checked against it by
# tests/golden/test_buccaneer_sensitivity.py::test_static); "Defense (flat)" has no sweep row in this class: a key without a rate prices as 0
STAT_TO_KEY = sens_mod.standard_stat_to_key("Str", "flat_str", "str_pct", sub=("Dex", "dex"))

SPEC = SensSpec(
    class_id="buccaneer", stat_list=STAT_LIST, mainstat=MainStat("flat_str", "str_pct", subs=(("dex", 0.25),)),
    status_rebuild_keys=STATUS_REBUILD_KEYS, companion_full_search_keys=COMPANION_FULL_SEARCH_KEYS, summon_time_keys=SUMMON_TIME_KEYS,
    passive_levels=PASSIVE_LEVELS, semantics=SEMANTICS, bdi_toggle_wired=True, pin_monster_defense=False, baked_fd_form="typed",
    reindeer_dose_in_rows=True, athena_as_in_aps=True, stat_to_key=STAT_TO_KEY, mult_extra=(("final_damage", "final_damage_all"),),
)
