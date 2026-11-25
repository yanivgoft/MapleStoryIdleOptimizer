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
    "level": "Your character level (1-300); it unlocks skills and masteries.",
    "flat_attack": "Flat ATTACK, as shown on your preset page.",
    "attack_pct": "Total ATTACK % (very large values are normal late game).",
    "crit_rate": "Only the first 100% counts directly; Ring of Cycles and Book of Ancient also use the excess.",
    "crit_damage": "Critical Damage bonus in % (on top of the base crit multiplier).",
    "attack_speed": "Attack Speed in %, as shown on your preset page.",
    "damage": "DAMAGE %, as shown on your preset page.",
    "damage_amp": "DAMAGE AMP %, as shown on your preset page.",
    "basic_attack_damage": "Extra damage % for basic attacks only.",
    "skill_damage": "Extra damage % for skills only.",
    "def_pen": "Defense Penetration in %, 0-100 (the total shown on your preset page).",
    "boss_damage": "Extra damage % against bosses.",
    "normal_damage": "Extra damage % against normal monsters.",
    "min_damage": "Lower end of your damage range, in % of the max (the average of min and max is used).",
    "max_damage": "Upper end of your damage range in %; 100 = no bonus.",
    "final_damage": "Final Damage in %, as shown on your preset page.",
    "skill_lvl_1st": "Flat skill levels added to every 1st-job skill.",
    "skill_lvl_2nd": "Flat skill levels added to every 2nd-job skill.",
    "skill_lvl_3rd": "Flat skill levels added to every 3rd-job skill.",
    "skill_lvl_4th": "Flat skill levels added to every 4th-job skill.",
    "skill_lvl_all": "Flat skill levels added to every skill.",
    "buff_duration_increase_pct": "Makes your buffs and timed effects last longer, in %.",
    "flat_int": "Flat INT, as shown on your preset page.", "int_pct": "INT % bonus.", "luk": "LUK (the sub stat of INT classes).",
    "flat_str": "Flat STR, as shown on your preset page.", "str_pct": "STR % bonus.", "str": "STR (the sub stat of DEX classes).",
    "flat_dex": "Flat DEX, as shown on your preset page.", "dex_pct": "DEX % bonus.", "dex": "DEX (the sub stat of STR / LUK classes).",
    "flat_luk": "Flat LUK, as shown on your preset page.", "luk_pct": "LUK % bonus.",
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
          help="Breakthrough and Chapter Hunt: chapter and stage like 28-9. Chapter Boss: the chapter number. Dungeons: the stage number."),
        f("flat_attack", "Flat ATTACK", "Offense", "float", "flat", 10000),
        f("attack_pct", "ATTACK %", "Offense", "float", "%", 0),
        f("defense", "Defense", "Offense", "float", "flat", 0,
          help="Your own Defense. In PvP the opponent is assumed to have the same Defense as you."),
        f("crit_rate", "Crit Rate", "Offense", "float", "%", 0),
        f("crit_damage", "Crit Damage", "Offense", "float", "%", 0),
        f("attack_speed", "Attack Speed", "Offense", "float", "%", 0),
        *main_stat_fields,
        f("damage", "Damage", "Damage modifiers", "float", "%", 0),
        f("damage_amp", "Damage Amp", "Damage modifiers", "float", "%", 0),
        f("basic_attack_damage", "Basic Attack Damage", "Damage modifiers", "float", "%", 0),
        f("skill_damage", "Skill Damage", "Damage modifiers", "float", "%", 0),
        f("def_pen", "Defense Penetration", "Damage modifiers", "float", "%", 0),
        f("boss_damage", "Boss Damage", "Damage modifiers", "float", "%", 0),
        f("normal_damage", "Normal Damage", "Damage modifiers", "float", "%", 0),
        f("status_effect_damage", "Status Effect Damage", "Damage modifiers", "float", "%", 0,
          help="Extra damage while the enemy is frozen, stunned or KO'd; 0 = no bonus (a KO also doubles damage)."),
        f("min_damage", "Min Damage", "Damage modifiers", "float", "%", 100),
        f("max_damage", "Max Damage", "Damage modifiers", "float", "%", 100),
        f("final_damage", "Final Damage", "Damage modifiers", "float", "%", 0),
        f("skill_lvl_1st", "Skill Level Bonus - 1st Job", "Skill levels", "int", "", 0),
        f("skill_lvl_2nd", "Skill Level Bonus - 2nd Job", "Skill levels", "int", "", 0),
        f("skill_lvl_3rd", "Skill Level Bonus - 3rd Job", "Skill levels", "int", "", 0),
        f("skill_lvl_4th", "Skill Level Bonus - 4th Job", "Skill levels", "int", "", 0),
        f("skill_lvl_all", "Skill Level Bonus - All Skills", "Skill levels", "int", "", 0),
        f("skill_cooldown_decrease", "Skill Cooldown Decrease", "Additional bonuses", "float", "s", 0,
          help="Seconds taken off every cooldown (skills, buffs and passives)."),
        f("basic_attack_target_increase", "Basic Attack Target Increase", "Additional bonuses", "int", "", 1,
          help="Extra targets for basic attacks, on top of the base 6 against normal monsters."),
        f("buff_duration_increase_pct", "Buff Duration Increase", "Additional bonuses", "float", "%", 0),
        f("companion_summon_time_increase_pct", "Companion Summoning Time Increase", "Additional bonuses", "float", "%", 0,
          help="The companion stays 30 s x (1 + this/100); its 90 s summon cooldown never changes."),
        f("boss_normal_weight_choice", "Boss/Normal Emphasis", "Additional bonuses", "enum", "", "A Little More Normal",
          applicable=app["boss_normal_weight_choice"], options=list(C.BOSS_NORMAL_WEIGHT_CHOICES),
          help="How the fight time splits between normal monsters and the boss."),
        f("max_enemies_hit", "Max Enemies In Range", "Additional bonuses", "int", "", 999, applicable=app["max_enemies_hit"],
          help="Normal-monster content only; 999 = no limit."),
        f("companion_choice", "Companion", "Main companion", "enum", "", "None", options=list(companion_choices),
          help="The companion summoned in this content type."),
        f("companion_level", "Companion Level", "Main companion", "int", "", 0, per_content=False,
          help="Level of the chosen companion (0 = not unlocked, 1-18); set on the Companions tab."),
        f("pvp_fight_length", "PvP Fight Length", "PvP", "float", "s", C.DEFAULT_PVP_FIGHT_LENGTH, applicable=app["pvp_fight_length"],
          help="Shorter fights count fewer damage-over-time and summon ticks and less buff uptime."),
        # calculated from the content type and the chapter / stage
        f("monster_type", "Monster Type", "Computed", "text", "", None, per_content=False, computed=True),
        f("chapter", "Chapter", "Computed", "float", "", None, per_content=False, computed=True),
        f("stage", "Stage", "Computed", "float", "", None, per_content=False, computed=True),
        f("breakthrough_normal_weight_pct", "Boss/Normal Weight", "Computed", "float", "%", None, per_content=False, computed=True),
        f("breakthrough_stage_index", "Breakthrough Global Stage Index", "Computed", "float", "", None, per_content=False, computed=True),
        f("monster_defense", "Monster Defense", "Computed", "float", "", None, per_content=False, computed=True),
        f("fight_duration", "Fixed Fight Duration", "Computed", "float", "s", None, per_content=False, computed=True,
          help="0 = no time limit (Chapter Hunt)."),
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
