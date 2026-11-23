"""What every ``<class>_cases.py`` golden input matrix shares: the content types, which inputs apply to which content type, the default chapter / stage
per content type, the companion presets and ``make_inputs`` (plain data, no workbook, no engine import)."""

CONTENT_TYPES = [
    "Chapter Boss", "World Boss", "Enhancement Dungeon", "Breakthrough", "Hero Dungeon",
    "Chapter Hunt", "EXP Dungeon", "Equipment Dungeon", "Weapon Dungeon", "PvP",
]

# which content types a per-content-type field applies to (mirrors build_inputs_sheet's INPUT_ROW_APPLICABLE_CONTENT_TYPES)
APPLICABLE = {
    "chapter_stage": ["Chapter Boss", "Breakthrough", "Chapter Hunt", "Weapon Dungeon", "Equipment Dungeon",
                      "Enhancement Dungeon", "EXP Dungeon", "Hero Dungeon"],
    "boss_normal_weight_choice": ["Breakthrough", "Hero Dungeon"],
    "pvp_fight_length": ["PvP"],
    "max_enemies_hit": ["EXP Dungeon", "Equipment Dungeon", "Chapter Hunt", "Breakthrough", "Hero Dungeon"],
}

DEFAULT_CHAPTER_STAGE = {
    "Chapter Boss": "37", "Breakthrough": "38-9", "Chapter Hunt": "38-9",
    "Weapon Dungeon": "80", "Equipment Dungeon": "80", "Enhancement Dungeon": "80", "EXP Dungeon": "80", "Hero Dungeon": "80",
}

COMPANIONS = {
    "none": ("None", 0),
    "blaze": ("Blaze Wizard", 10),
    "wind": ("Wind Archer", 7),
    "bow": ("Bow Master", 10),
}


def make_inputs(content_type, level, stats, companion="none", chapter_stage=None, **over):
    d = dict(stats)
    d.update(over)
    d["level"] = level
    d["content_type"] = content_type
    d["chapter_stage"] = chapter_stage if chapter_stage is not None else DEFAULT_CHAPTER_STAGE.get(content_type)
    for key, cts in APPLICABLE.items():
        if content_type not in cts:
            d[key] = None
    choice, clevel = COMPANIONS[companion]
    d["companion_choice"] = choice
    d["companion_level"] = clevel
    return d
