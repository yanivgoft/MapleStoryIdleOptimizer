"""Corsair Sensitivity spec: the builder's ``STAT_SWEEP`` (stat entries), ``STATUS_REBUILD_KEYS``, ``COMPANION_FULL_SEARCH_KEYS``, ``SUMMON_TIME_KEYS`` and
``PASSIVE_DELTA_SLOT`` of ``src/build_corsair_workbook.py`` (cross-checked against the builder by ``tests/golden/test_sensitivity.py --class corsair``).

Corsair specifics (all reproduced from ``build_stat_block``):

* main stat DEX / sub stat STR (bug 7): ``mainstat_attack_delta = (DEX x (1 + DEX%)) delta + 0.25 x STR delta`` (no Defense stat in this class).
* the passive skills whose level-dependent values are baked into the typed Inputs - Shadow Heart (Crit Rate), Quick Motion / Agile Guns (Attack Speed), Infinity Blast
  (Attack%, the ``attack_mult_delta`` hook: it joins the additive Attack% bucket next to Roll of the Dice's dice component, the strip's A0 and the companion's snapshot), Gun
  Mastery (Min Damage), Physical Training AND Quickdraw (Basic Attack Damage), Fullmetal Jacket (Crit Damage) and Cross Cut Blast (Final Damage, additive next to the typed value)
  - add the DELTA of their value to a skill-level block (``PASSIVE_DELTA_SLOT``).  Shadow Heart's Crit Rate delta feeds the live crit rate AND Ring of Cycles' threshold
  (``roc_threshold_cr_block`` includes ``delta["crit_rate"]``).  The Attack Speed deltas move the block's Actions Per Second, the Quickdraw divisor and the companion snapshot's,
  so 1st / 2nd job levels re-solve the strip (``skill_lvl_1st`` / ``_2nd`` in ``STATUS_REBUILD_KEYS``, Sensitivity fix 2026-11-20).
* Corsair shifts ``Inputs!final_damage`` INSIDE the additive Final Damage bracket ``(1 + (Inputs + Jolly Roger + Ahoy Mateys + Cross Cut delta) / 100)``: the baked-in Final
  Damage artifacts (Cursed Doll, Lit Lamp, Clear Spring Water, Soul Pouch, Bottle of Emotion) are a factor on the TYPED value (``baked_fd_form="typed"``; the workbook writes it as a
  block-local SHIFT cell in column U that ``ib("final_damage")`` adds everywhere, incl. the strip's Jolly Roger scale 100/(100 + F0 + rest)), not on the artifact bucket, and the
  Final Damage sweep (+1% multiplicative) bumps the FULL bracket including the live Jolly Roger / Ahoy Mateys share (``MULT_KIND_EXTRA_REF`` = Summary R_FD_ALL = Jolly Roger at the
  current cast counts - the strip's count when it is on - plus Ahoy Mateys; ``mult_extra`` -> ``model.final_damage_all``; the table's Current / New include it).
* Reindeer's Spear: the block's K formula reads ``def_pen_total_block`` (the dose reaches the rows' defense reduction, the boss-branch correction and the companion): flag True
  (the Corsair builder never had that gap).  Shamaness Marble: ``bdi_block`` ignored the block's ``shamaness_marble_delta_block`` until 2026-11-22 (the row was inert); the builder now
  routes EVERY reader of the block's Buff Duration Increase (buff uptimes, Swift Fire's Weaken, Ahoy Mateys, the crew windows, the strip's durations) through one helper cell that
  adds the what-if: flag True.  Athena's Gloves: the block's Actions Per Second read ``Inputs!attack_speed + delta`` only (no direct bonus) until the same fix; it now reads
  ``attack_speed_total_block`` (Quickdraw divisor, Peach Tree / Silver Pendant, Nautilus / Majestic rates and the companion follow) and the toggle re-solves its own strip
  (``athena_gloves_equipped`` in ``STATUS_REBUILD_KEYS``): flag True.
* No live crit-rate source exists in this kit (``crit_rate_bonus`` = 0): the artifact crit rate (Ring of Cycles / Rainbow Snail Shell) is ``model.art_crit_rate``.
* Blackboot Bill's stun (Lv66) exists with no companion chosen, so the timeline strip and the companion host are live from Lv66 even with ``companion_choice == "None"``.
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
    "final_damage": "the +1% multiplicative step bumps the whole additive Final Damage bracket, including the live Jolly Roger / Ahoy Mateys share (Current / New include it)",
    "skill_lvl_1st": "adds Shadow Heart's (Crit Rate) and Quick Motion's (Attack Speed) level deltas",
    "skill_lvl_2nd": "adds Agile Guns' (Attack Speed), Gun Mastery's (Min Damage), Physical Training's (Basic Attack Damage) and Infinity Blast's (Attack%) level deltas",
    "skill_lvl_3rd": "adds Fullmetal Jacket's (Crit Damage) and Cross Cut Blast's (Final Damage) level deltas",
    "skill_lvl_4th": "adds Quickdraw's (Basic Attack Damage) level delta",
    "skill_lvl_all": "adds every passive's level delta (Shadow Heart, Quick Motion, Agile Guns, Gun Mastery, Physical Training, Infinity Blast, Fullmetal Jacket, Cross Cut Blast, Quickdraw)",
    "crit_rate": "Book of Ancient (if equipped): Crit Damage follows the crit-rate change",
    "attack_speed": "Athena's Gloves (if equipped): Max Damage follows; Bottle of Emotion (if equipped): Final Damage follows",
}

STATUS_REBUILD_KEYS = (
    "skill_cooldown_decrease", "buff_duration_increase_pct", "shamaness_marble_equipped", "status_effect_damage",
    "companion_summon_time_increase_pct", "hexagon_necklace_equipped", "arwens_glass_shoes_equipped",
    # everything that moves the strip's buff bucket (A0 incl. Charm / Roll of the Dice / the Attack% artifacts, the Final Damage scale of Jolly Roger) and the cooldowns it consumes
    "charm_of_the_undead_equipped", "old_music_box_equipped", "secret_map_equipped", "reindeer_spear_equipped",
    "alliance_badge_equipped", "bottle_of_emotion_equipped", "skill_lvl_3rd", "skill_lvl_4th", "skill_lvl_all", "final_damage",
    "attack_speed",
    # Sensitivity fixes 2026-11-20: stats that change the RELATIVE per-cast weights (skill vs the basic attack, its own Boss Mastery, Ring of Cycles) or the Quickdraw / Nimble Feet cooldowns
    "skill_lvl_1st", "skill_lvl_2nd", "skill_damage", "basic_attack_damage", "boss_damage", "crit_rate",
    # Athena's Gloves' direct Attack Speed moves the block's Actions Per Second (builder fixed 2026-11-22)
    "athena_gloves_equipped",
    "ring_of_cycles_equipped", "book_of_ancient_equipped", "rainbow_snail_shell_equipped",
    "candle_equipped", "sayrams_necklace_equipped", "star_rock_equipped", "peach_tree_equipped", "silver_pendant_equipped",
    "clear_spring_water_equipped", "soul_pouch_equipped", "cursed_doll_equipped", "lit_lamp_equipped",
)
COMPANION_FULL_SEARCH_KEYS = ("companion_summon_time_increase_pct", "hexagon_necklace_equipped", "horn_flute_equipped", "skill_cooldown_decrease",
                              "arwens_glass_shoes_equipped")
SUMMON_TIME_KEYS = ("companion_summon_time_increase_pct", "arwens_glass_shoes_equipped")

# PASSIVE_DELTA_SLOT of the builder: (hook, base tenths-of-%, factor index, job step, unlock level) of each Skills-sheet passive row (all factor 22, scaling)
PASSIVE_LEVELS = (
    PassiveLevel("crit_rate_delta", 50, 22, 1, 10),             # Shadow Heart
    PassiveLevel("attack_speed_extra", 60, 22, 1, 15),          # Quick Motion
    PassiveLevel("attack_speed_extra", 50, 22, 2, 40),          # Agile Guns
    PassiveLevel("attack_mult_delta", 120, 22, 2, 45),          # Infinity Blast (Attack%)
    PassiveLevel("min_damage_delta", 150, 22, 2, 43),           # Gun Mastery
    PassiveLevel("basic_attack_damage_delta", 100, 22, 2, 38),  # Physical Training
    PassiveLevel("crit_damage_delta", 100, 22, 3, 72),          # Fullmetal Jacket
    PassiveLevel("final_damage_delta", 120, 22, 3, 75),         # Cross Cut Blast
    PassiveLevel("basic_attack_damage_delta", 250, 22, 4, 125),  # Quickdraw
)

# the builder's POTENTIAL_STAT_TO_SWEEP_KEY / POTENTIAL_SUB_STAT_PCT_LINES / EQUIP_COMPARE_STAT_TO_SWEEP_KEY / ARTIFACT_POTENTIAL_STAT_TO_SWEEP_KEY (checked against it by
# tests/golden/test_sensitivity.py::test_static[corsair]); "Defense (flat)" has no sweep row in this class: a key without a rate prices as 0
STAT_TO_KEY = sens_mod.standard_stat_to_key("Dex", "flat_dex", "dex_pct", sub=("Str", "str"))

SPEC = SensSpec(
    class_id="corsair", stat_list=STAT_LIST, mainstat=MainStat("flat_dex", "dex_pct", subs=(("str", 0.25),)),
    status_rebuild_keys=STATUS_REBUILD_KEYS, companion_full_search_keys=COMPANION_FULL_SEARCH_KEYS, summon_time_keys=SUMMON_TIME_KEYS,
    passive_levels=PASSIVE_LEVELS, semantics=SEMANTICS, bdi_toggle_wired=True, pin_monster_defense=False, baked_fd_form="typed",
    reindeer_dose_in_rows=True, athena_as_in_aps=True, stat_to_key=STAT_TO_KEY, mult_extra=(("final_damage", "final_damage_all"),),
)
