"""Shadower Sensitivity spec: the builder's ``STAT_SWEEP`` (stat entries), ``STATUS_REBUILD_KEYS``, ``COMPANION_FULL_SEARCH_KEYS``, ``SUMMON_TIME_KEYS`` and
``PASSIVE_DELTA_SLOT`` of ``src/build_shadower_workbook.py`` (cross-checked against the builder by ``tests/golden/test_shadower_sensitivity.py``).

Shadower specifics (all reproduced from ``build_stat_block``):

* main stat LUK / sub stat DEX (bug 7): ``mainstat_attack_delta = (LUK x (1 + LUK%)) delta + 0.25 x DEX delta`` (no Defense stat in this class); ``incoming_hit_rate`` (Shadow
  Shifter's counterattack, hits/s taken, +1 flat) is a normal stat: the engine's own ``incoming_hit_rate`` input.
* the passive skills whose level-dependent values are baked into the typed Inputs - Agile Daggers (Attack Speed), Channel Karma (Attack%, joins the additive Attack% bucket next to
  Dark Sight (Attack) / Steal / Meso Mastery: the bucket, the strip's A0, the companion's snapshot and the phase ratios: hook ``attack_mult_delta``), Dagger Mastery (Min Damage),
  Critical Edge (Crit Rate AND Crit Damage; the Crit Rate delta feeds Ring of Cycles' threshold), Physical Training (Basic Attack Damage), Dagger Expert (Skill Damage + Max
  Damage) and Shadower Instinct + Shadow Shifter's self Final Damage (typed Final Damage, additive with each other and the typed value: the typed value is its own factor in K)
  - add the DELTA of their value to a skill-level block (``PASSIVE_DELTA_SLOT``).  Shadow Shifter's Lv118 mastery (+10) cancels in the delta (its row is additive).
* Final Damage: K = ``(1 + (typed + passive deltas)/100)`` x ``(1 + artifact bucket/100)``; Into Darkness / Smokescreen are separate buff factors (``(1+a)(1+b)``).  The baked-in
  Final Damage artifacts (Cursed Doll, Lit Lamp, Clear Spring Water, Soul Pouch, Bottle of Emotion) are a FACTOR on the artifact bucket (``fd_baked_factor``, helper cells in column
  U), i.e. on the whole product (``baked_fd_form="factor"``).  There is no live additive source in the typed bracket (no ``MULT_KIND_EXTRA_REF``): the Final Damage sweep (+1%
  multiplicative) is exactly x1.01 outside the strip / companion.
* Reindeer's Spear: the block's rows read ``def_pen_total_block`` (rows' defense reduction, the boss-branch correction and the companion): flag True.  Shamaness Marble and
  Athena's Gloves had the two Dark Knight gaps in this builder too (Shamaness inert: ``bdi_block`` was ``ib(buff_duration_increase_pct)``; Athena's direct Attack Speed missing from
  the block's Actions Per Second) and were FIXED on 2026-11-23 (Sensitivity only, main sheets formula-identical): ``bdi_block`` is a block-local helper cell (column U, 6th row:
  swept value + ``shamaness_marble_delta_block``), ``s_aps`` reads ``attack_speed_total_block``; ``athena_gloves_equipped`` was already in ``STATUS_REBUILD_KEYS``: flags True.
* No Defense Penetration source and no live global Final Damage / Attack% passive besides the ones above.  Dark Sight (Crit) is the class's live crit-rate source
  (``model.crit_rate_bonus``, Ring of Cycles' threshold and Book of Ancient's removal reference include it), the artifact crit rate is ``model.art_crit_rate``.
* Toxic Venom (20% proc, one roll per attack per enemy hit) follows ``attack_speed`` (Athena) / skill levels through the engine's own hit-rate blend; Blood Money / Meso
  Explosion stacks read the block's own Actions Per Second.
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
    "final_damage": "the +1% multiplicative step is exactly x1.01 on the typed Final Damage factor (Into Darkness / Smokescreen / the artifact bucket are separate factors)",
    "skill_lvl_2nd": "adds Agile Daggers' (Attack Speed), Channel Karma's (Attack%), Dagger Mastery's (Min Damage), Critical Edge's (Crit Rate, Crit Damage) and Physical Training's (Basic Attack Damage) level deltas",
    "skill_lvl_4th": "adds Dagger Expert's (Skill Damage, Max Damage), Shadower Instinct's and Shadow Shifter's (Final Damage) level deltas",
    "skill_lvl_all": "adds every passive's level delta (Agile Daggers, Channel Karma, Dagger Mastery, Critical Edge, Physical Training, Dagger Expert, Shadower Instinct, Shadow Shifter)",
    "crit_rate": "Book of Ancient (if equipped): Crit Damage follows the crit-rate change",
    "attack_speed": "Athena's Gloves (if equipped): Max Damage follows; Bottle of Emotion (if equipped): Final Damage follows",
    "incoming_hit_rate": "Shadow Shifter's counterattack only: hits per second taken x 20% x its hit",
}

STATUS_REBUILD_KEYS = (
    "skill_cooldown_decrease", "buff_duration_increase_pct", "shamaness_marble_equipped", "status_effect_damage",
    "companion_summon_time_increase_pct", "hexagon_necklace_equipped", "arwens_glass_shoes_equipped",
    # everything that moves the engine's buff bucket (A0 / Charm / Steal / Meso Mastery's Attack Speed -> Actions Per Second / Dark Sight, Into Darkness, Smokescreen)
    "charm_of_the_undead_equipped", "old_music_box_equipped", "secret_map_equipped", "reindeer_spear_equipped",
    "alliance_badge_equipped", "bottle_of_emotion_equipped", "athena_gloves_equipped", "attack_speed",
    "skill_lvl_1st", "skill_lvl_2nd", "skill_lvl_3rd", "skill_lvl_4th", "skill_lvl_all",
    # the strip consumes the per-cast damage weights and the basic attack a cast replaces, through their RELATIVE sizes
    "skill_damage", "basic_attack_damage", "boss_damage", "crit_rate",
    "ring_of_cycles_equipped", "book_of_ancient_equipped", "rainbow_snail_shell_equipped",
    "candle_equipped", "sayrams_necklace_equipped", "star_rock_equipped",
)
COMPANION_FULL_SEARCH_KEYS = ("companion_summon_time_increase_pct", "hexagon_necklace_equipped", "horn_flute_equipped", "skill_cooldown_decrease",
                              "arwens_glass_shoes_equipped")
SUMMON_TIME_KEYS = ("companion_summon_time_increase_pct", "arwens_glass_shoes_equipped")

# PASSIVE_DELTA_SLOT of the builder: (hook, base tenths-of-%, factor index, job step, unlock level) of each Skills-sheet passive row (all factor 22, scaling)
PASSIVE_LEVELS = (
    PassiveLevel("attack_speed_extra", 50, 22, 2, 33),          # Agile Daggers
    PassiveLevel("attack_mult_delta", 80, 22, 2, 40),           # Channel Karma (Attack%, additive bucket)
    PassiveLevel("min_damage_delta", 150, 22, 2, 43),           # Dagger Mastery
    PassiveLevel("crit_rate_delta", 60, 22, 2, 50),             # Critical Edge (Crit Rate)
    PassiveLevel("crit_damage_delta", 100, 22, 2, 50),          # Critical Edge (Crit Damage)
    PassiveLevel("basic_attack_damage_delta", 100, 22, 2, 38),  # Physical Training
    PassiveLevel("skill_damage_delta", 150, 22, 4, 120),        # Dagger Expert (Skill Damage)
    PassiveLevel("max_damage_delta", 200, 22, 4, 120),          # Dagger Expert (Max Damage Multiplier)
    PassiveLevel("final_damage_delta", 200, 22, 4, 125),        # Shadower Instinct
    PassiveLevel("final_damage_delta", 100, 22, 4, 115),        # Shadow Shifter (self Final Damage; its Lv118 +10 mastery is a constant)
)

# the builder's POTENTIAL_STAT_TO_SWEEP_KEY / POTENTIAL_SUB_STAT_PCT_LINES / EQUIP_COMPARE_STAT_TO_SWEEP_KEY / ARTIFACT_POTENTIAL_STAT_TO_SWEEP_KEY (checked against it by
# tests/golden/test_shadower_sensitivity.py::test_static); "Defense (flat)" has no sweep row in this class: a key without a rate prices as 0
STAT_TO_KEY = sens_mod.standard_stat_to_key("Luk", "flat_luk", "luk_pct", sub=("Dex", "dex"))

SPEC = SensSpec(
    class_id="shadower", stat_list=STAT_LIST, mainstat=MainStat("flat_luk", "luk_pct", subs=(("dex", 0.25),)),
    status_rebuild_keys=STATUS_REBUILD_KEYS, companion_full_search_keys=COMPANION_FULL_SEARCH_KEYS, summon_time_keys=SUMMON_TIME_KEYS,
    passive_levels=PASSIVE_LEVELS, semantics=SEMANTICS, bdi_toggle_wired=True, pin_monster_defense=False, baked_fd_form="factor",
    reindeer_dose_in_rows=True, athena_as_in_aps=True, stat_to_key=STAT_TO_KEY,
)
