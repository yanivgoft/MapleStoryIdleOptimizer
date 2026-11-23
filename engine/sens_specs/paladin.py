"""Paladin Sensitivity spec: the builder's ``STAT_SWEEP`` (stat entries), ``STATUS_REBUILD_KEYS``, ``COMPANION_FULL_SEARCH_KEYS``, ``SUMMON_TIME_KEYS`` and
``PASSIVE_DELTA_SLOT`` of ``src/build_paladin_workbook.py`` (cross-checked against the builder by ``tests/golden/test_paladin_sensitivity.py``).

Paladin specifics (all reproduced from ``build_stat_block``):

* main stat STR / sub stat DEX (bug 7): ``mainstat_attack_delta = (STR x (1 + STR%)) delta + 0.25 x DEX delta`` (no Defense stat in this class).
* the passive skills whose level-dependent values are baked into the typed Inputs - Weapon Acceleration (Attack Speed), Physical Training (Basic Attack Damage), Weapon Mastery
  (Min Damage), Parashock Guard (Attack%, joins the additive Attack% bucket next to Vessel of Light / HP Recovery / Combat Orders: the bucket, the strip's A0, the companion's
  snapshot) and Paladin Expert (Skill Damage + Max Damage, 4th job) - are added by every block as ``unlocked x (F of the block's own state - the MAIN sheet's F)``
  (``PASSIVE_DELTA_SLOT``).  Their F is time-averaged with Combat Orders' temporary skill-level bonus (job steps 3 / 4), so the delta ALSO moves with the block's own Combat Orders
  uptime: a Cooldown Decrease / Buff Duration / Shamaness sweep changes Parashock Guard's and Paladin Expert's factor although no skill level was swept (the documented ~1.6e-4
  Breakthrough CDR / ~4.5e-5 Buff Duration residual of KNOWN_GAPS "Back-port of the Buccaneer-port recipe").  The engine reproduces that in the MODEL (``passive_deltas_in_model``:
  the class module computes ``passive_values`` at its own state, the main model's values arrive as ``_sens["passive_ref"]``), not through the spec's level-only ``PassiveLevel``
  loop (the rows below stay as the data table the model and the static test read).  1st job levels are not in ``STATUS_REBUILD_KEYS`` (Nimble Feet is the only 1st-job row and
  does not scale); the 2nd / 3rd / 4th job levels and ``skill_lvl_all`` re-solve the strip.
* Paladin retypes ``Inputs!final_damage`` INSIDE the additive Final Damage bucket ``(1 + (final_damage + R_FD_BONUS) / 100)`` (R_FD_BONUS = Divine Shield + Guardian + Divine
  Blessing + Greater Vessel of Light [Guardian / Divine Blessing sit in the engine's own buff bucket while the strip is on]): the baked-in Final Damage artifacts (Cursed Doll,
  Lit Lamp, Clear Spring Water, Soul Pouch, Bottle of Emotion) are a factor on the TYPED value, not on the artifact bucket (``baked_fd_form="typed"``), and the Final Damage sweep
  (+1% multiplicative) bumps the FULL bucket including the buffs' live share (``MULT_KIND_EXTRA_REF`` = Summary R_FD_ALL = all four buffs at the current cast counts;
  ``mult_extra`` -> ``model.final_damage_all``; the table's Current / New include it).
* Reindeer's Spear / Shamaness Marble / Athena's Gloves: three workbook gaps found by the Dark Knight port were fixed in this builder on 2026-11-22 (the rows' K formula now
  reads ``def_pen_total_block``; ``bdi_block`` adds ``shamaness_marble_delta_block`` through a helper cell; the block's Actions Per Second reads ``attack_speed_total_block`` and
  ``athena_gloves_equipped`` re-solves its own strip): all three flags True.
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
    "final_damage": "the +1% multiplicative step bumps the whole Final Damage bucket, including the live Divine Shield / Guardian / Divine Blessing / Greater Vessel share (Current / New include it)",
    "skill_lvl_2nd": "adds Weapon Acceleration's (Attack Speed), Physical Training's (Basic Attack Damage) and Weapon Mastery's (Min Damage) level deltas",
    "skill_lvl_3rd": "adds Parashock Guard's Attack% level delta (and Combat Orders' own skill-level bonus moves every 3rd-job factor)",
    "skill_lvl_4th": "adds Paladin Expert's (Skill Damage, Max Damage) level deltas",
    "skill_lvl_all": "adds every passive's level delta (Weapon Acceleration, Physical Training, Weapon Mastery, Parashock Guard, Paladin Expert)",
    "skill_cooldown_decrease": "Combat Orders' uptime moves with the cooldown, and with it the skill-level factor of Parashock Guard / Paladin Expert (block F minus the main sheet's F)",
    "buff_duration_increase_pct": "Combat Orders' uptime moves with the duration, and with it the skill-level factor of Parashock Guard / Paladin Expert (block F minus the main sheet's F)",
    "crit_rate": "Book of Ancient (if equipped): Crit Damage follows the crit-rate change",
    "attack_speed": "Athena's Gloves (if equipped): Max Damage follows; Bottle of Emotion (if equipped): Final Damage follows",
}

STATUS_REBUILD_KEYS = (
    'skill_cooldown_decrease', 'buff_duration_increase_pct', 'shamaness_marble_equipped', 'status_effect_damage',
    'companion_summon_time_increase_pct', 'hexagon_necklace_equipped', 'arwens_glass_shoes_equipped',
    # everything that moves the strip's buff bucket (A0 incl. Vessel of Light / Charm / the Attack% artifacts, the cast buffs' F incl. the skill-level inputs of their job step,
    # the Final Damage scale of Guardian / Divine Blessing, the Basic-Attack-rate-driven Vessel of Light)
    'charm_of_the_undead_equipped', 'old_music_box_equipped', 'secret_map_equipped', 'reindeer_spear_equipped',
    'alliance_badge_equipped', 'bottle_of_emotion_equipped', 'skill_lvl_3rd', 'skill_lvl_4th', 'skill_lvl_all', 'final_damage',
    'attack_speed', 'basic_attack_target_increase',
    # Athena's Gloves' direct Attack Speed moves the strip like the Attack Speed sweep (builder fixed 2026-11-22)
    'athena_gloves_equipped',
    # Sensitivity fix 1 (2026-11-21): stats that change the RELATIVE per-cast weights (skill vs Blast, its own Boss Mastery, Ring of Cycles) and the 2nd-job passive deltas
    'skill_lvl_2nd', 'skill_damage', 'basic_attack_damage', 'boss_damage', 'crit_rate',
    'ring_of_cycles_equipped', 'book_of_ancient_equipped', 'rainbow_snail_shell_equipped',
    'candle_equipped', 'sayrams_necklace_equipped', 'star_rock_equipped',
    'cursed_doll_equipped', 'lit_lamp_equipped', 'clear_spring_water_equipped', 'soul_pouch_equipped',
)
COMPANION_FULL_SEARCH_KEYS = ("companion_summon_time_increase_pct", "hexagon_necklace_equipped", "horn_flute_equipped", "skill_cooldown_decrease",
                              "arwens_glass_shoes_equipped")
SUMMON_TIME_KEYS = ("companion_summon_time_increase_pct", "arwens_glass_shoes_equipped")

# PASSIVE_DELTA_SLOT of the builder: (hook, base tenths-of-%, factor index, job step, unlock level) of each Skills-sheet passive row (all factor 22, scaling).
# The class module (engine/classes/paladin.py) reads this table to compute each row's value at its own state (``passive_values``)
PASSIVE_LEVELS = (
    PassiveLevel("attack_speed_extra", 50, 22, 2, 33),          # Weapon Acceleration
    PassiveLevel("basic_attack_damage_delta", 100, 22, 2, 38),  # Physical Training
    PassiveLevel("min_damage_delta", 150, 22, 2, 43),           # Weapon Mastery
    PassiveLevel("attack_mult_delta", 180, 22, 3, 72),          # Parashock Guard (Attack%, additive bucket)
    PassiveLevel("skill_damage_delta", 150, 22, 4, 120),        # Paladin Expert (Skill Damage)
    PassiveLevel("max_damage_delta", 200, 22, 4, 120),          # Paladin Expert (Max Damage Multiplier)
)

# the builder's POTENTIAL_STAT_TO_SWEEP_KEY / POTENTIAL_SUB_STAT_PCT_LINES / EQUIP_COMPARE_STAT_TO_SWEEP_KEY / ARTIFACT_POTENTIAL_STAT_TO_SWEEP_KEY (checked against it by
# tests/golden/test_buccaneer_sensitivity.py::test_static); "Defense (flat)" has no sweep row in this class: a key without a rate prices as 0
STAT_TO_KEY = sens_mod.standard_stat_to_key("Str", "flat_str", "str_pct", sub=("Dex", "dex"))

SPEC = SensSpec(
    class_id="paladin", stat_list=STAT_LIST, mainstat=MainStat("flat_str", "str_pct", subs=(("dex", 0.25),)),
    status_rebuild_keys=STATUS_REBUILD_KEYS, companion_full_search_keys=COMPANION_FULL_SEARCH_KEYS, summon_time_keys=SUMMON_TIME_KEYS,
    passive_levels=PASSIVE_LEVELS, semantics=SEMANTICS, bdi_toggle_wired=True, pin_monster_defense=False, baked_fd_form="typed",
    reindeer_dose_in_rows=True, athena_as_in_aps=True, stat_to_key=STAT_TO_KEY, mult_extra=(("final_damage", "final_damage_all"),),
    passive_deltas_in_model=True,
)
