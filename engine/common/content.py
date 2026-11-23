"""Content-type tables and formulas shared by every class.

Everything here mirrors the workbook's Inputs-sheet computed rows (``monster_type``, ``chapter``/``stage``, ``breakthrough_stage_index``,
``monster_defense``, ``fight_duration``, ``breakthrough_normal_weight_pct``) and the status/KO windows, as identical to the
``_compute_*`` helpers of the ``src/verify_<class>_workbook.py`` scripts (the three classes compared - FP-Mage, Hero, Shadower -
carry byte-identical copies).
"""

CONTENT_TYPES = [
    "Chapter Boss", "Breakthrough", "PvP", "EXP Dungeon", "Equipment Dungeon",
    "Weapon Dungeon", "Enhancement Dungeon", "Hero Dungeon", "World Boss", "Chapter Hunt",
]

BOSS_NORMAL_WEIGHT_CHOICES = ["More Normal", "A Little More Normal", "Equal", "A Little More Boss", "More Boss"]

# Per-content-type fields that do not apply to every content type (workbook: INPUT_ROW_APPLICABLE_CONTENT_TYPES).  Keys not
# listed apply to all ten.  A field that does not apply is passed as None / omitted and reads as 0 (blank Excel cell).
INPUT_APPLICABLE_CONTENT_TYPES = {
    "chapter_stage": ["Chapter Boss", "Breakthrough", "Chapter Hunt", "Weapon Dungeon", "Equipment Dungeon",
                      "Enhancement Dungeon", "EXP Dungeon", "Hero Dungeon"],
    "boss_normal_weight_choice": ["Breakthrough", "Hero Dungeon"],
    "pvp_fight_length": ["PvP"],
    "max_enemies_hit": ["EXP Dungeon", "Equipment Dungeon", "Chapter Hunt", "Breakthrough", "Hero Dungeon"],
}

CHAPTER_STAGE_DEFAULT_BY_CONTENT_TYPE = {
    "Chapter Boss": "28", "Breakthrough": "28-9", "Chapter Hunt": "28-9",
    "Weapon Dungeon": "80", "Equipment Dungeon": "80", "Enhancement Dungeon": "80",
    "EXP Dungeon": "80", "Hero Dungeon": "80",
}

DEFAULT_PVP_FIGHT_LENGTH = 15


def compute_monster_type(content_type):
    if content_type == "PvP":
        return "pvp"
    if content_type in ("Breakthrough", "Hero Dungeon"):
        return "breakthrough"
    if content_type in ("EXP Dungeon", "Equipment Dungeon", "Chapter Hunt"):
        return "normal"
    return "boss"


def compute_breakthrough_stage_index(chapter, stage):
    if chapter == 28:
        return stage - 9
    return stage + 14 * max(0, min(chapter - 1, 38) - 28) + 19 * max(0, chapter - 39)


def compute_monster_defense(content_type, chapter, stage, defense):
    if content_type == "Chapter Boss":
        return 3200 + 50 * (chapter - 28)
    if content_type == "World Boss":
        return 62100
    if content_type == "Weapon Dungeon":
        return stage * 50
    if content_type == "Enhancement Dungeon":
        return 950 + stage * 50
    if content_type in ("EXP Dungeon", "Equipment Dungeon"):
        return 250 + stage * 50
    if content_type == "Hero Dungeon":
        return 650 + stage * 50
    if content_type in ("Breakthrough", "Chapter Hunt"):
        return 4860 + 20 * compute_breakthrough_stage_index(chapter, stage)
    return defense  # PvP fallback - manual, opponent-dependent


def compute_fight_duration(content_type):
    return {
        "Chapter Hunt": 0, "Weapon Dungeon": 22, "Equipment Dungeon": 40,
        "Enhancement Dungeon": 25, "Hero Dungeon": 50, "EXP Dungeon": 40,
        "World Boss": 75, "Chapter Boss": 70, "Breakthrough": 40,
    }.get(content_type, 0)


def parse_chapter_stage(raw):
    """'28-9' -> (28, 9); '37' -> (37, 37) (a bare number serves as chapter AND stage); unparsable -> (28, 9)."""
    raw = str(raw)
    if "-" in raw:
        left, right = raw.split("-", 1)
        try:
            return float(left), float(right)
        except ValueError:
            return 28.0, 9.0
    try:
        v = float(raw)
        return v, v
    except ValueError:
        return 28.0, 9.0


def compute_breakthrough_normal_weight_pct(choice):
    return {
        "More Normal": 70, "A Little More Normal": 60, "Equal": 50,
        "A Little More Boss": 40, "More Boss": 30,
    }.get(choice, 60)


def compute_normal_weight(monster_type, breakthrough_normal_weight_pct):
    """Time weight of the normal-monster branch: 1 for normal content, the emphasis % for Breakthrough / Hero Dungeon (boss and
    normal phases), 0 for boss content and PvP (PvP never blends)."""
    return (
        1.0 if monster_type == "normal"
        else breakthrough_normal_weight_pct / 100 if monster_type == "breakthrough"
        else 0.0
    )


def ko_windows(fight_duration):
    """KO (knocked-out boss) windows of the fixed-length contents (user, 2026-11-14): World Boss 24-34 s and 59-69 s, Enhancement
    Dungeon the last 4.5 s."""
    return {"World Boss": [(24, 34), (59, 69)], "Enhancement Dungeon": [(fight_duration - 4.5, fight_duration)]}


class Content:
    """Everything the Inputs sheet derives from the content type (and chapter-stage / defense / emphasis inputs)."""

    __slots__ = ("content_type", "chapter", "stage", "monster_type", "breakthrough_normal_weight_pct", "normal_weight",
                 "monster_defense", "fight_duration", "fixed_duration_active", "breakthrough_stage_index")

    def __init__(self, content_type, chapter_stage_raw, defense, weight_choice):
        self.content_type = content_type
        self.chapter, self.stage = parse_chapter_stage(chapter_stage_raw)
        self.monster_type = compute_monster_type(content_type)
        self.breakthrough_normal_weight_pct = compute_breakthrough_normal_weight_pct(weight_choice)
        self.normal_weight = compute_normal_weight(self.monster_type, self.breakthrough_normal_weight_pct)
        self.monster_defense = compute_monster_defense(content_type, self.chapter, self.stage, defense)
        self.breakthrough_stage_index = compute_breakthrough_stage_index(self.chapter, self.stage)
        self.fight_duration = compute_fight_duration(content_type)
        # Fixed fight-duration mode: off for PvP (own always-on fixed-duration model) or when no duration is set (steady state)
        self.fixed_duration_active = self.monster_type != "pvp" and self.fight_duration > 0
