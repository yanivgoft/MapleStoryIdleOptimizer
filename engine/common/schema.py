"""Input schema shared by every class: the field list (key, label, group, type, unit, default, applicability, options, computed) the
UI / API render, derived from the workbook's Inputs sheet (``build_inputs_sheet``).

A class contributes only its main-stat fields (FP-Mage: Flat INT / INT % / LUK) and, later, class-specific extras; the rest of the
list is common.  Field dict::

    key           inputs-dict key (= the builder's IN key)
    label         short label ('help' carries the workbook's long description)
    group         section the UI puts it in
    type          'int' | 'float' | 'text' | 'enum'
    unit          '%', 's', 'flat', '' ...
    default       workbook default (for 'chapter_stage' see default_by_content)
    per_content   True: the workbook keeps one value per content type (columns C-L); False: one shared value
    applicable    list of content types the field applies to, None = all ten (a non-applicable field is None / 0)
    options       dropdown values for 'enum' fields, else None
    computed      True: derived by the engine from other inputs (read-only, ignored if passed)
    min, max      inclusive numeric bounds (numeric fields only; None for enum / text / computed).  Deliberately permissive: they only reject
                  values that are certainly a typo or would break the maths (negative percentages, Defense Penetration above 100, ...).  Resolved
                  from FIELD_BOUNDS by key, else from the unit (UNIT_BOUNDS), unless the caller passes them explicitly.
    help          one-line hint the UI shows under the field (the workbook's own note where it has one)
"""
from . import content as C


MAX_FLAT = 1e13          # flat stats (Attack, Defense, main / sub stat)
MAX_PCT = 1e8            # percentage stats (late-game Attack % reaches the tens of thousands)

# inclusive (min, max) per key; anything not listed falls back to UNIT_BOUNDS
FIELD_BOUNDS = {
    "level": (1, 300),
    "crit_rate": (0, 500),                       # only the first 100% pays directly; the excess matters for Ring of Cycles / Book of Ancient
    "attack_speed": (0, 150),                    # the 150% combined cap of the Actions/s formula
    "def_pen": (0, 100),                         # above 100 would make the defense term negative
    "min_damage": (0, 1000), "max_damage": (0, 1000),
    "skill_lvl_1st": (0, 1000), "skill_lvl_2nd": (0, 1000), "skill_lvl_3rd": (0, 1000), "skill_lvl_4th": (0, 1000),
    "skill_lvl_all": (0, 1000),
    "skill_cooldown_decrease": (0, 60),
    "basic_attack_target_increase": (0, 100),
    "buff_duration_increase_pct": (0, 10000),
    "companion_summon_time_increase_pct": (0, 10000),
    "max_enemies_hit": (0, 100000),
    "companion_level": (0, 18),
    "pvp_fight_length": (1, 600),                # the workbook's own validation is >= 1
    "incoming_hit_rate": (0, 100),
}
UNIT_BOUNDS = {"%": (0, MAX_PCT), "s": (0, 1e4), "flat": (0, MAX_FLAT), "": (0, MAX_FLAT)}

# one-line hints for the common fields (a class / call site may pass its own ``help``; that wins)
FIELD_HELP = {
    "level": "Character level, 1-300; unlocks skills and masteries.",
    "flat_attack": "Flat ATTACK from your stat screen (the model does not add a main-stat conversion on top).",
    "attack_pct": "Total ATTACK % bonus (large late-game values are normal).",
    "crit_rate": "Crit Rate in %; only the first 100% counts directly (Ring of Cycles / Book of Ancient use the excess).",
    "crit_damage": "Critical Damage bonus in % (on top of the base crit multiplier).",
    "damage": "DAMAGE % from your stat screen.",
    "damage_amp": "DAMAGE AMP % from your stat screen.",
    "basic_attack_damage": "Extra damage % applied to basic attacks only.",
    "skill_damage": "Extra damage % applied to skills only.",
    "def_pen": "Defense Penetration in %, 0-100 (the total shown on your stat screen).",
    "boss_damage": "Extra damage % against bosses.",
    "normal_damage": "Extra damage % against normal monsters.",
    "min_damage": "Lower end of your damage range in % of the max (the model averages min and max).",
    "max_damage": "Upper end of your damage range in %; 100 = no bonus.",
    "skill_lvl_1st": "Flat skill levels added to every 1st-job skill.",
    "skill_lvl_2nd": "Flat skill levels added to every 2nd-job skill.",
    "skill_lvl_3rd": "Flat skill levels added to every 3rd-job skill.",
    "skill_lvl_4th": "Flat skill levels added to every 4th-job skill.",
    "skill_lvl_all": "Flat skill levels added to every skill.",
    "buff_duration_increase_pct": "Extends the duration of your buffs and timed effects in %.",
    "flat_int": "Flat INT from your stat screen.", "int_pct": "INT % bonus.", "luk": "LUK (sub stat of INT classes).",
    "flat_str": "Flat STR from your stat screen.", "str_pct": "STR % bonus.", "str": "STR (sub stat of DEX classes).",
    "flat_dex": "Flat DEX from your stat screen.", "dex_pct": "DEX % bonus.", "dex": "DEX (sub stat of STR / LUK classes).",
    "flat_luk": "Flat LUK from your stat screen.", "luk_pct": "LUK % bonus.",
}


def _bounds(key, type, unit):
    if type not in ("int", "float"):
        return None, None
    if key in FIELD_BOUNDS:
        return FIELD_BOUNDS[key]
    return UNIT_BOUNDS.get(unit, (0, MAX_FLAT))


def field(key, label, group, type="float", unit="", default=0, per_content=True, applicable=None, options=None, computed=False,
          help=None, default_by_content=None, min=None, max=None):
    lo, hi = _bounds(key, type, unit)
    if computed:
        lo = hi = None
    return dict(key=key, label=label, group=group, type=type, unit=unit, default=default, per_content=per_content,
                applicable=applicable, options=options, computed=computed, help=help if help is not None else FIELD_HELP.get(key),
                default_by_content=default_by_content, min=lo if min is None else min, max=hi if max is None else max)


def common_fields(main_stat_fields, companion_choices):
    """Ordered field list.  ``main_stat_fields``: the class's own (flat main stat, main stat %, sub stat) fields, in workbook order."""
    f = field
    app = C.INPUT_APPLICABLE_CONTENT_TYPES
    return [
        f("level", "Character Level", "Character", "int", "", 200, per_content=False),
        f("content_type", "Content Type", "Character", "enum", "", "Chapter Boss", per_content=False, options=list(C.CONTENT_TYPES)),
        f("chapter_stage", "Chapter-Stage", "Character", "text", "", None, applicable=app["chapter_stage"],
          default_by_content=dict(C.CHAPTER_STAGE_DEFAULT_BY_CONTENT_TYPE),
          help="'chapter-substage' (e.g. '28-9') for Breakthrough/Chapter Hunt, just the chapter number for Chapter Boss, or just the "
               "stage number for Weapon/Equipment/Enhancement/EXP/Hero Dungeon. Not applicable to World Boss/PvP."),
        f("flat_attack", "Flat ATTACK", "Offense", "float", "flat", 10000),
        f("attack_pct", "ATTACK %", "Offense", "float", "%", 0),
        f("defense", "Defense", "Offense", "float", "flat", 0,
          help="Your own DEF stat; PvP assumes the opponent has the same Defense as you."),
        f("crit_rate", "Crit Rate", "Offense", "float", "%", 0),
        f("crit_damage", "Crit Damage", "Offense", "float", "%", 0),
        f("attack_speed", "Attack Speed", "Offense", "float", "%", 0, help="Base value, excludes Nimble Feet."),
        *main_stat_fields,
        f("damage", "Damage", "Damage modifiers", "float", "%", 0),
        f("damage_amp", "Damage Amp", "Damage modifiers", "float", "%", 0),
        f("basic_attack_damage", "Basic Attack Damage", "Damage modifiers", "float", "%", 0),
        f("skill_damage", "Skill Damage", "Damage modifiers", "float", "%", 0),
        f("def_pen", "Defense Penetration", "Damage modifiers", "float", "%", 0),
        f("boss_damage", "Boss Damage", "Damage modifiers", "float", "%", 0),
        f("normal_damage", "Normal Damage", "Damage modifiers", "float", "%", 0),
        f("status_effect_damage", "Status Effect Damage", "Damage modifiers", "float", "%", 0,
          help="Extra damage while the enemy is frozen/stunned/KO'd; 0 = no bonus (KO still doubles damage)."),
        f("min_damage", "Min Damage", "Damage modifiers", "float", "%", 100),
        f("max_damage", "Max Damage", "Damage modifiers", "float", "%", 100),
        f("final_damage", "Final Damage", "Damage modifiers", "float", "%", 0, help="Base value, excludes Infinity."),
        f("skill_lvl_1st", "Skill Level Bonus - 1st Job", "Skill levels", "int", "", 0),
        f("skill_lvl_2nd", "Skill Level Bonus - 2nd Job", "Skill levels", "int", "", 0),
        f("skill_lvl_3rd", "Skill Level Bonus - 3rd Job", "Skill levels", "int", "", 0),
        f("skill_lvl_4th", "Skill Level Bonus - 4th Job", "Skill levels", "int", "", 0),
        f("skill_lvl_all", "Skill Level Bonus - All Skills", "Skill levels", "int", "", 0),
        f("skill_cooldown_decrease", "Skill Cooldown Decrease", "Additional bonuses", "float", "s", 0,
          help="Seconds; applies to every cooldown (skills, buffs and passives)."),
        f("basic_attack_target_increase", "Basic Attack Target Increase", "Additional bonuses", "int", "", 1,
          help="Flat, adds to the 6-target normal-monster base."),
        f("buff_duration_increase_pct", "Buff Duration Increase", "Additional bonuses", "float", "%", 0),
        f("companion_summon_time_increase_pct", "Companion Summoning Time Increase", "Additional bonuses", "float", "%", 0,
          help="Companion duration = 30 s x (1 + this/100); summon cooldown is always 90 s."),
        f("boss_normal_weight_choice", "Boss/Normal Emphasis", "Additional bonuses", "enum", "", "A Little More Normal",
          applicable=app["boss_normal_weight_choice"], options=list(C.BOSS_NORMAL_WEIGHT_CHOICES),
          help="Breakthrough / Hero Dungeon only: how the fight time splits between normal monsters and the boss."),
        f("max_enemies_hit", "Max Enemies In Range", "Additional bonuses", "int", "", 999, applicable=app["max_enemies_hit"],
          help="Normal-monster content only; 999 = uncapped."),
        f("companion_choice", "Companion", "Companion", "enum", "", "None", options=list(companion_choices),
          help="The companion summoned in this content type."),
        f("companion_level", "Companion Level", "Companion", "int", "", 0, per_content=False,
          help="Level of the chosen companion (0 = not unlocked, 1-18); the workbook keeps one level per companion."),
        f("pvp_fight_length", "PvP Fight Length", "PvP", "float", "s", C.DEFAULT_PVP_FIGHT_LENGTH, applicable=app["pvp_fight_length"],
          help="PvP content only; shorter fights cut DoT/summon ticks and buff uptime."),
        # computed by the engine (workbook: hidden computed rows of the Inputs sheet)
        f("monster_type", "Monster Type", "Computed", "text", "", None, per_content=False, computed=True),
        f("chapter", "Chapter", "Computed", "float", "", None, per_content=False, computed=True),
        f("stage", "Stage", "Computed", "float", "", None, per_content=False, computed=True),
        f("breakthrough_normal_weight_pct", "Boss/Normal Weight", "Computed", "float", "%", None, per_content=False, computed=True),
        f("breakthrough_stage_index", "Breakthrough Global Stage Index", "Computed", "float", "", None, per_content=False, computed=True),
        f("monster_defense", "Monster Defense", "Computed", "float", "", None, per_content=False, computed=True),
        f("fight_duration", "Fixed Fight Duration", "Computed", "float", "s", None, per_content=False, computed=True,
          help="0 = steady state (Chapter Hunt)."),
    ]


def applicable_to(field_, content_type):
    return field_["applicable"] is None or content_type in field_["applicable"]


def default_inputs(fields, content_type="Chapter Boss"):
    """Resolved defaults for one content type: fields that do not apply to it are None (blank cell); computed fields are omitted."""
    out = {}
    for fl in fields:
        if fl["computed"]:
            continue
        key = fl["key"]
        if key == "content_type":
            out[key] = content_type
        elif not applicable_to(fl, content_type):
            out[key] = None
        elif fl["default_by_content"] is not None:
            out[key] = fl["default_by_content"][content_type]
        else:
            out[key] = fl["default"]
    return out
