"""Night Lord Sensitivity spec: the builder's ``STAT_SWEEP`` (stat entries), ``STATUS_REBUILD_KEYS``, ``COMPANION_FULL_SEARCH_KEYS``, ``SUMMON_TIME_KEYS`` and
``PASSIVE_DELTA_SLOT`` of ``src/build_night_lord_workbook.py`` (cross-checked against the builder by ``tests/golden/test_night_lord_sensitivity.py``).

Night Lord specifics (all reproduced from ``build_stat_block``):

* main stat LUK / sub stat DEX (bug 7): ``mainstat_attack_delta = (LUK x (1 + LUK%)) delta + 0.25 x DEX delta`` (no Defense stat in the sweep).  ``incoming_hit_rate`` is a plain
  "+1 hit/s" stat (Shadow Shifter's counterattack only).
* the passive skills whose level-dependent values are baked into the typed Inputs - Agile Claws (Attack Speed), Physical Training (Basic Attack Damage), Claw Mastery (Min Damage),
  Critical Throw (Crit Rate AND Crit Damage), Enveloping Darkness (Boss Damage: ``boss_damage_delta``, the boss branch only), Expert Throwing Star Handling (Attack%: joins the
  additive Attack% bucket next to Dark Sight and the artifacts - the strip's A0 and the companion's snapshot included), Claw Expert (Skill Damage), Dark Harmony and Shadow Shifter's
  self buff (Final Damage, ADDITIVE next to the typed value) - add the DELTA of their value to a skill-level block.  Critical Throw's Crit Rate delta feeds the live crit rate AND
  Ring of Cycles' threshold (``roc_threshold_cr_block`` includes ``delta["crit_rate"]``).  Night Lord's Mark (feeds Assassin's Mark's Final Damage) and Dark Sight / Frailty Curse (the
  live buffs) simply recompute at the swept level (Assassin's Mark reads the block's OWN Night Lord's Mark row, builder fix 2026-11-21).
* Final Damage: the typed value sits in the bracket ``(1 + (typed + passive deltas)/100)`` times the artifact bucket ``(1 + agg/100)``; Frailty Curse's and Alchemic Adrenaline's Final
  Damage are their own factors.  The baked-in Final Damage artifacts (Cursed Doll, Lit Lamp, Clear Spring Water, Soul Pouch, Bottle of Emotion) are a FACTOR on the artifact bucket
  (``fd_baked_factor`` helper cells in column U), i.e. on the whole product (``baked_fd_form="factor"``).  No live additive source shares the typed bracket (``mult_extra`` empty).
* Reindeer's Spear: the block's rows read ``def_pen_total_block`` (the dose reaches the rows' defense reduction, the boss-branch correction and the companion): flag True.  Athena's
  Gloves: the block's Actions Per Second (and Alchemic Adrenaline's accumulate time, Peach Tree / Silver Pendant) read ``attack_speed_total_block`` (direct Attack Speed incl.): flag True;
  the timeline strip does not read the Actions Per Second, so the toggle needs no strip of its own.  Shamaness Marble: ``bdi_block`` ignored the block's
  ``shamaness_marble_delta_block`` until 2026-11-23 (the row was inert, as in Dark Knight / Paladin / Corsair / Bowmaster before their fixes); the builder now routes every reader of the
  block's Buff Duration Increase (buff uptimes, Alchemic Adrenaline's window, the strip's durations) through a column-U helper cell that adds the what-if: flag True.
* Live crit-rate source: Critical Throw Lv47 (+8) and Dark Sight (Crit Rate) average = ``model.crit_rate_bonus`` (in the full crit total of the cap check and of Book of Ancient's
  dependent Crit Damage); the artifact crit rate (Ring of Cycles / Rainbow Snail Shell) is ``model.art_crit_rate``.
* Gust Charm's stun (Lv35) exists with no companion chosen, so the timeline strip and the companion host are live from Lv35 even with ``companion_choice == "None"``.
"""
from ..common import sens as sens_mod
from ..common.sens import MainStat, PassiveLevel, SensSpec

STAT_LIST = sens_mod.stat_list((
    ("flat_luk", "Flat LUK", "flat"),
    ("luk_pct", "LUK %", "pct"),
    ("dex", "DEX", "flat"),
), (
    ("incoming_hit_rate", "Incoming Hit Rate (hits/sec, Shadow Shifter only)", "flat"),
))

_LUK_NOTE = "adds the main stat's flat-Attack channel (1 LUK = 1 Attack, 1 DEX = 0.25 Attack, before ATTACK%) next to STAT_DAMAGE"
SEMANTICS = {
    "flat_luk": _LUK_NOTE,
    "luk_pct": _LUK_NOTE,
    "dex": _LUK_NOTE,
    "skill_lvl_2nd": "adds Agile Claws' (Attack Speed), Physical Training's (Basic Attack Damage), Claw Mastery's (Min Damage) and Critical Throw's (Crit Rate, Crit Damage) level deltas",
    "skill_lvl_3rd": "adds Enveloping Darkness' (Boss Damage) and Expert Throwing Star Handling's (Attack%) level deltas",
    "skill_lvl_4th": "adds Claw Expert's (Skill Damage), Dark Harmony's and Shadow Shifter's (Final Damage) level deltas; Night Lord's Mark feeds Assassin's Mark's Final Damage",
    "skill_lvl_all": "adds every passive's level delta (Agile Claws, Physical Training, Claw Mastery, Critical Throw, Enveloping Darkness, Expert Throwing Star Handling, Claw Expert, Dark Harmony, Shadow Shifter)",
    "crit_rate": "Book of Ancient (if equipped): Crit Damage follows the crit-rate change",
    "attack_speed": "Athena's Gloves (if equipped): Max Damage follows; Bottle of Emotion (if equipped): Final Damage follows",
}

STATUS_REBUILD_KEYS = (
    "skill_cooldown_decrease", "buff_duration_increase_pct", "shamaness_marble_equipped", "status_effect_damage",
    "companion_summon_time_increase_pct", "hexagon_necklace_equipped", "arwens_glass_shoes_equipped",
    # everything that moves the strip's buff bucket (A0 incl. Charm / the Attack% artifacts, Dark Sight's / Frailty Curse's F) and the cooldowns it consumes
    "charm_of_the_undead_equipped", "old_music_box_equipped", "secret_map_equipped", "reindeer_spear_equipped",
    "alliance_badge_equipped", "bottle_of_emotion_equipped", "skill_lvl_1st", "skill_lvl_3rd", "skill_lvl_4th", "skill_lvl_all",
    # Sensitivity fix 2026-11-21: stats that change the RELATIVE per-cast weights (skill vs the basic attack, its own Boss Mastery, Ring of Cycles)
    "skill_damage", "basic_attack_damage", "boss_damage", "crit_rate",
    "ring_of_cycles_equipped", "book_of_ancient_equipped", "rainbow_snail_shell_equipped",
    "candle_equipped", "sayrams_necklace_equipped", "star_rock_equipped", "peach_tree_equipped", "silver_pendant_equipped",
)
COMPANION_FULL_SEARCH_KEYS = ("companion_summon_time_increase_pct", "hexagon_necklace_equipped", "horn_flute_equipped", "skill_cooldown_decrease",
                              "arwens_glass_shoes_equipped")
SUMMON_TIME_KEYS = ("companion_summon_time_increase_pct", "arwens_glass_shoes_equipped")

# PASSIVE_DELTA_SLOT of the builder: (hook, base tenths-of-%, factor index, job step, unlock level) of each Skills-sheet passive row (all factor 22, scaling)
PASSIVE_LEVELS = (
    PassiveLevel("attack_speed_extra", 50, 22, 2, 33),             # Agile Claws
    PassiveLevel("basic_attack_damage_delta", 100, 22, 2, 38),     # Physical Training
    PassiveLevel("min_damage_delta", 150, 22, 2, 40),              # Claw Mastery
    PassiveLevel("crit_rate_delta", 60, 22, 2, 45),                # Critical Throw (Crit Rate)
    PassiveLevel("crit_damage_delta", 100, 22, 2, 45),             # Critical Throw (Crit Damage)
    PassiveLevel("boss_damage_delta", 180, 22, 3, 72),             # Enveloping Darkness
    PassiveLevel("attack_mult_delta", 180, 22, 3, 75),             # Expert Throwing Star Handling (Attack%)
    PassiveLevel("skill_damage_delta", 150, 22, 4, 120),           # Claw Expert
    PassiveLevel("final_damage_delta", 120, 22, 4, 125),           # Dark Harmony
    PassiveLevel("final_damage_delta", 100, 22, 4, 115),           # Shadow Shifter (self Final Damage)
)

# the builder's POTENTIAL_STAT_TO_SWEEP_KEY / POTENTIAL_SUB_STAT_PCT_LINES / EQUIP_COMPARE_STAT_TO_SWEEP_KEY / ARTIFACT_POTENTIAL_STAT_TO_SWEEP_KEY (checked against it by
# tests/golden/test_night_lord_sensitivity.py::test_static); "Defense (flat)" has no sweep row in this class: a key without a rate prices as 0
STAT_TO_KEY = sens_mod.standard_stat_to_key("Luk", "flat_luk", "luk_pct", sub=("Dex", "dex"))

SPEC = SensSpec(
    class_id="night_lord", stat_list=STAT_LIST, mainstat=MainStat("flat_luk", "luk_pct", subs=(("dex", 0.25),)),
    status_rebuild_keys=STATUS_REBUILD_KEYS, companion_full_search_keys=COMPANION_FULL_SEARCH_KEYS, summon_time_keys=SUMMON_TIME_KEYS,
    passive_levels=PASSIVE_LEVELS, semantics=SEMANTICS, bdi_toggle_wired=True, pin_monster_defense=False, baked_fd_form="factor",
    reindeer_dose_in_rows=True, athena_as_in_aps=True, stat_to_key=STAT_TO_KEY, mult_extra=(),
)
