"""Wind Archer (Cygnus Knight, DEX main / STR sub bowman) static game data - ENGINE-NATIVE and PROVISIONAL: there is no workbook, builder or verify script for this class, and the user has so
far supplied only LEVEL-1 pop-ups (fresh character, "Lv. 1" everywhere = the BASE value, factor 1.0; /Users/yaniv/private/wind_archer, transcribed in ``data/cygnus/wind_archer_ingame.md``).

A level-1 reading gives each base EXACTLY but says nothing about the growth curve, and the live site data (maplestoryidle.info) has NO Wind Archer rows with masteries, so EVERY factor index below is a
CONVENTION (the one that held for Dawn Warrior, Night Walker and 38 of Blaze Wizard's 40 curves: burst damage 12; basic attack, additional-damage procs and active buffs / debuffs 21; passives 22;
per-skill Final Damage "Call of Cygnus" 23) and is marked PROVISIONAL in ``CURVES`` / ``PROVISIONAL`` (ONE place to edit per skill: change the triple in ``CURVES`` and nothing else).  The class
module stays ``PUBLISHED = False`` until the user supplies one higher-level reading per skill (data/cygnus/README.md, the Blaze Wizard readings of 2026-11-27 are the template).

Conventions follow ``engine/data/blaze_wizard.py``: base damage in TENTHS of a percent (``base``), ``fidx`` the FactorTable column, ``step`` the job tier (1-4) whose skill level scales the skill
(1st job 60 + bonus, 2nd 90 +, 3rd 120 +, 4th (character level - 100) x 3 + bonus); ``{level: tier value}`` chains are resolved by the model in ``engine/classes/wind_archer.py``.  Mastery percentages are
fixed numbers (they do not grow with the skill level).  Every judgement call is flagged in ``ROW_NOTES`` / ``FLAGS`` and in KNOWN_GAPS.md ("Wind Archer").

Patch 2026-11-26 values are already applied: Emerald Dust's Final Damage is a standalone 20 s buff (Buff Duration Increase applies), Bow Expert's Max Damage Multiplier is 30 %.
"""
from collections import namedtuple

CLASS_ID = "wind_archer"

Curve = namedtuple("Curve", "base fidx step")        # base in tenths of %, FactorTable column, job tier

# ---- EVERY scaling curve of the class (all PROVISIONAL: bases = the level-1 values read in game, factor index and job step = convention) ----
CURVES = {
    # damage skills (burst convention: idx 12)
    "SPIRALING_VORTEX": Curve(2500, 12, 2),                  # 250 % x 2 hits on 9 targets
    "PINPOINT_PIERCE_ARROW1": Curve(3300, 12, 3),            # first arrow 330 % (one target)
    "PINPOINT_PIERCE_ARROW2": Curve(7400, 12, 3),            # second arrow 740 % (same target)
    "SONG_OF_HEAVEN": Curve(7800, 12, 4),                    # 780 % per arrow, 13 volleys, 9 targets each
    # basic attack and the additional-damage procs (idx 21: Dawn Warrior's Luna Divide, Blaze Wizard's Orbital Explosion)
    "FAIRY_SPIRAL": Curve(2900, 21, 4),                      # 290 % x 6 targets x 5 hits (basic attack, 4th job)
    "TRIFLING_WIND_I": Curve(360, 21, 2),                    # Spirit Arrow 36 % additional damage (Lv40)
    "TRIFLING_WIND_II": Curve(1000, 21, 3),                  # "damage changes to 100 %" from Lv66 (replaces Trifling Wind I's 36 %)
    "TRIFLING_WIND_III_FD": Curve(1000, 21, 4),              # Final Damage of Trifling Wind +100 % (Lv105)
    "STORM_BRINGER": Curve(11000, 21, 4),                    # giant arrow 1100 % on 12 targets
    # timed buffs / debuffs (idx 21: active skills)
    "STORM_ELEMENTAL_ATTACK": Curve(120, 21, 1),             # Attack +12 % for 12 s
    "STORM_ELEMENTAL_DAMAGE": Curve(40, 21, 1),              # Damage +4 % for 12 s
    "SHARP_EYES_CRIT_DAMAGE": Curve(400, 21, 4),             # YOUR Critical Damage +40 % for 18 s (allied players get 20 % of it: not modelled)
    "EMERALD_FLOWER_BOSS_TAKEN": Curve(150, 21, 3),          # boss damage taken +15 % while the flower lasts (20 s)
    # passives (idx 22): live (conditional) ones
    "EMERALD_DUST_TAKEN": Curve(80, 22, 4),                  # Emerald Flower: damage taken +8 % in range
    "EMERALD_DUST_FD": Curve(30, 22, 4),                     # YOUR Final Damage +3 % for 20 s after Emerald Flower (patch 2026-11-26: standalone buff)
    "SECOND_WIND_AS": Curve(150, 22, 3),                     # Attack Speed +15 % for 8 s
    # passives (idx 22): always-on, "already in the stat screen" (Sensitivity level deltas only)
    "WHISPERS_ATTACK": Curve(30, 22, 1),                     # Attack +3 %
    "WHISPERS_AS": Curve(30, 22, 1),                         # Attack Speed +3 %
    "AGILE_BOWS_AS": Curve(50, 22, 2),                       # Attack Speed +5 %
    "PHYSICAL_TRAINING_BASIC": Curve(100, 22, 2),            # Basic Attack Damage +10 %
    "BOW_MASTERY_MIN": Curve(150, 22, 2),                    # Min Damage Multiplier +15 %
    "SYLVAN_AID_ATTACK": Curve(120, 22, 2),                  # Attack +12 %
    "SYLVAN_AID_CRIT_RATE": Curve(60, 22, 2),                # Critical Rate +6 %
    "SECOND_WIND_ATTACK": Curve(120, 22, 3),                 # Attack +12 %
    "FEATHERWEIGHT_DAMAGE": Curve(300, 22, 3),               # Damage +30 %
    "FEATHERWEIGHT_NORMAL": Curve(150, 22, 3),               # Normal Monster Damage +15 %
    "EAGLE_EYE_FD": Curve(150, 22, 3),                       # Final Damage +15 %
    "TOUCH_OF_THE_WIND_ATTACK": Curve(100, 22, 4),           # Attack +10 % (its Max HP +10 % is not a DPS stat)
    "BOW_EXPERT_SKILL": Curve(150, 22, 4),                   # Skill Damage +15 %
    "BOW_EXPERT_MAX": Curve(300, 22, 4),                     # Max Damage Multiplier +30 % (patch 2026-11-26: 20 -> 30)
    "ALBATROSS_FD": Curve(100, 22, 4),                       # Final Damage +10 %
    "ALBATROSS_DEF_PEN": Curve(80, 22, 4),                   # Defense Penetration +8 %
    # Call of Cygnus: per-skill Final Damage multiplier 1 + pct/100 (idx 23, 4th job)
    "CYGNUS_PINPOINT_PIERCE": Curve(400, 23, 4),
    "CYGNUS_SPIRALING_VORTEX": Curve(1000, 23, 4),
}
# Every curve is a convention (no site table row, no higher-level reading yet): the flag the user's later scaling data flips one skill at a time (move a name out of this set once resolved).
PROVISIONAL = set(CURVES)
CONFIRMED_BY_READINGS = {}


def is_provisional(name):
    return name in PROVISIONAL


SKILL_NAMES = {
    "FAIRY_SPIRAL": "Fairy Spiral (basic attack)",
    "TRIFLING_WIND": "Trifling Wind (Spirit Arrows from skills)",
    "SONG_SPIRIT_ARROWS": "Song of Heaven (Spirit Arrows)",
    "STORM_BRINGER": "Storm Bringer (giant arrow)",
    "SPIRALING_VORTEX": "Spiraling Vortex",
    "PINPOINT_PIERCE_ARROW1": "Pinpoint Pierce (first arrow)",
    "PINPOINT_PIERCE_ARROW2": "Pinpoint Pierce (second arrow)",
    "SONG_OF_HEAVEN": "Song of Heaven",
}

# Result rows (damage rows only)
DPS_ROW_ORDER = ["FAIRY_SPIRAL", "TRIFLING_WIND", "SONG_SPIRIT_ARROWS", "STORM_BRINGER", "SPIRALING_VORTEX", "PINPOINT_PIERCE_ARROW1", "PINPOINT_PIERCE_ARROW2", "SONG_OF_HEAVEN"]

# Unlock levels (FLAGGED: the skill windows' icon grids were matched to the skills BY ICON, the user has not confirmed the mapping).  Active grid: [equipped basic attack, Elemental Harmony, Storm Elemental
# (no badge)] then Lv30, 35, 50, 60, 63, 69, 100, 103, 115 (9 badges for the 8 transcribed actives + one untranscribed 2nd-job icon): Spiraling Vortex 30 (Blaze's Flame Vortex is 30 and its
# damage mastery is also Lv39), Wind Walk 50, Sentient Arrow 60 (the 3rd-job basic attack: not modelled), Pinpoint Pierce 63, Emerald Flower 69, Fairy Spiral 100, Song of Heaven 103, Sharp Eyes 115.
# Passive grid (icon + badge): Whispers of the Wind (none), Agile Bows 33, Physical Training 38, Trifling Wind I 40, Bow Mastery 43, Sylvan Aid 45, Evasion Boost 60, Trifling Wind II 66,
# Second Wind 72, Featherweight 74, Eagle Eye 75, Call of Cygnus 100, Trifling Wind III 105, Emerald Dust 107, Storm Bringer 110, Touch of the Wind 117, Bow Expert 120, Albatross Max 125.
# The basic attack (Fairy Spiral) is the 4th-job one: unlocked at 100 and ABSENT below it, like every class (no pre-100 / 3rd-job basic attack is modelled).
UNLOCK_LEVEL = {
    "FAIRY_SPIRAL": 100,
    "SPIRALING_VORTEX": 30,
    "PINPOINT_PIERCE_ARROW1": 63,
    "PINPOINT_PIERCE_ARROW2": 63,
    "SONG_OF_HEAVEN": 103,
    "STORM_ELEMENTAL": 0,
    "ELEMENTAL_HARMONY": 0,
    "EMERALD_FLOWER": 69,
    "SHARP_EYES": 115,
    "TRIFLING_WIND": 40,
    "SONG_SPIRIT_ARROWS": 103,
    "TRIFLING_WIND_I": 40,
    "TRIFLING_WIND_II": 66,
    "TRIFLING_WIND_III": 105,
    "SECOND_WIND": 72,
    "CALL_OF_CYGNUS": 100,
    "EMERALD_DUST": 107,
    "STORM_BRINGER": 110,
}

# ---- Fairy Spiral (the basic attack) ----
FS_HITS = (5, 136, 6)                               # 5 hits, +1 strike from level 136 (mastery "Fairy Spiral - Strike")
FS_MASTERY = {102: 10, 106: 11, 116: 12, 120: 13, 128: 14, 132: 15}      # Damage mastery chain: raw tiers, summed, then x(1 + m/100) (CLAUDE.md bug 2)
FS_BOSS_MASTERY = {111: 10, 124: 10}                                       # "Adds 10% Boss Monster Damage to Fairy Spiral"
FS_BASE_TARGETS = 6                                 # + the Basic Attack Target Increase input (already contains the Lv64 mastery)

# ---- damage rows cast on a cooldown ----
# step / base / fidx come from CURVES (``curve`` key); cooldown (s), hits, mastery {level: %} (multiplies the skill), normal-monster targets, costs_action, ``cygnus``: key of the Call of Cygnus
# Final Damage, ``cast_row``: the row whose cast this row shares (cooldown / action slot).
DAMAGE_SKILLS = {
    "SPIRALING_VORTEX": dict(curve="SPIRALING_VORTEX", cooldown=19, hits=2, mastery={39: 50}, targets=9, costs_action=True, cygnus="CYGNUS_SPIRALING_VORTEX"),
    "PINPOINT_PIERCE_ARROW1": dict(curve="PINPOINT_PIERCE_ARROW1", cooldown=20, hits=1, mastery={68: 50}, targets=1, costs_action=True, cygnus="CYGNUS_PINPOINT_PIERCE"),
    "PINPOINT_PIERCE_ARROW2": dict(curve="PINPOINT_PIERCE_ARROW2", cooldown=20, hits=1, mastery={68: 50}, targets=1, costs_action=False, cygnus="CYGNUS_PINPOINT_PIERCE",
                                   cast_row="PINPOINT_PIERCE_ARROW1"),
    "SONG_OF_HEAVEN": dict(curve="SONG_OF_HEAVEN", cooldown=40, hits=13, mastery={108: 50}, targets=9, costs_action=True),
}
PINPOINT_WEAKEN = dict(level=94, pct=10, duration=12)      # the second arrow's target takes +10 % damage for 12 s (boss / PvP branch only: one target)

# ---- Trifling Wind (Spirit Arrows) ----
# "When a skill is activated" creates 3 Spirit Arrows (+2 at Lv104, +2 more at Lv130) dealing the additional damage to random nearby targets, 2 s cooldown; Trifling Wind II (Lv66) changes the damage
# to 100 % with a chance (25 %, +15 pp at Lv90) of x2; masteries +50 % (Lv44) and +80 % (Lv73) damage; Trifling Wind III (Lv105) adds Final Damage +100 % (+35 at Lv113).  Against ONE target every
# consecutive strike within 0.5 s lowers the arrows' damage by 20 % (up to 4 times = -80 %).
TRIFLING_WIND = dict(icd=2.0, arrows=3, arrows_bonus=((104, 2), (130, 2)), mastery={44: 50, 73: 80}, double_chance=25.0, double_chance_bonus={90: 15.0},
                     fd_bonus={113: 35.0}, ladder=(1.0, 0.8, 0.6, 0.4, 0.2))
SONG_SPIRIT = dict(per_volley=2, per_volley_bonus=((134, 3),), volleys=13)     # "Every time the arrows are fired, creates 2 Spirit Arrow(s)" (+3 at Lv134)

# ---- Storm Bringer ----
# "When a skill is activated, calls down a torrential storm with a 50 % chance for 15 s; when attacking during the storm fires a giant arrow with a 30 % chance (+30 pp at Lv138) for 1100 %
# damage on 12 targets, giant arrow cooldown 0.5 s"; the skill's own cooldown shown is 25 s; mastery +50 % damage at Lv122.
STORM_BRINGER_RULES = dict(trigger_chance=0.5, duration=15.0, cooldown=25.0, chance=0.30, chance_bonus={138: 0.30}, icd=0.5, hits=1, targets=12, mastery={122: 50})

# ---- timed buffs ----
STORM_ELEMENTAL = dict(duration=12, cooldown=28, duration_mastery=(21, 1.5))       # Attack +12 % and Damage +4 % for 12 s, x1.5 from the level 21 mastery
ELEMENTAL_HARMONY = dict(duration=15, cooldown=60, attack_speed=15)                # Attack Speed +15 % (+10 % movement speed ignored); no level shown in game -> not level-scaling
SHARP_EYES = dict(duration=18, cooldown=35, duration_mastery=(126, 1.5))           # YOUR Critical Damage +40 %; Lv126 "Persistence": duration +50 %
EMERALD_FLOWER = dict(duration=20, cooldown=38, cooldown_mastery=(78, 0.7))        # damage taken (boss +15 %); Lv78 "Reuse": cooldown -30 %
EMERALD_DUST = dict(fd_duration=20, fd_mastery={118: 6.0})                         # Final Damage +3 % (+6 pp at Lv118) for 20 s, Buff Duration Increase applies (patch 2026-11-26)
SECOND_WIND = dict(duration=8.0, activations=8, activations_mastery=(82, 4), dead_time=4.0)     # Attack Speed +15 % for 8 s after N skill activations; no new stacks for 4 s after it ends

# Action-costing rows (cast rate subtracted from the basic attack), in order: damage rows read DAMAGE_SKILLS, buffs BUFF_COOLDOWNS
COST_ACTION_ORDER = ["SPIRALING_VORTEX", "PINPOINT_PIERCE_ARROW1", "SONG_OF_HEAVEN", "STORM_ELEMENTAL", "EMERALD_FLOWER", "SHARP_EYES", "ELEMENTAL_HARMONY"]
BUFF_COOLDOWNS = {"STORM_ELEMENTAL": 28, "EMERALD_FLOWER": 38, "SHARP_EYES": 35, "ELEMENTAL_HARMONY": 60}
BUFF_ROW_KEYS = ["STORM_ELEMENTAL", "EMERALD_FLOWER", "SHARP_EYES", "ELEMENTAL_HARMONY"]
STARTUP_BUFFS = ["STORM_ELEMENTAL", "EMERALD_FLOWER", "SHARP_EYES", "ELEMENTAL_HARMONY"]       # actively cast buffs -> startup delay / engine-off t0

# ---- player's own stun: Spiraling Vortex 1.5 s from Lv49 (mastery "Spiraling Vortex - Stun"); cast on cooldown from the start ----
PLAYER_STUN = [dict(id="VORTEX", key="SPIRALING_VORTEX", typ="cast", dur=1.5, p=1.0, level=49)]

# ---- always-on effects classed as "already in the stat screen" (documentation + the Sensitivity spec's PASSIVE_LEVELS; NOT added to the model) ----
STAT_SCREEN_EFFECTS = (
    "Whispers of the Wind (Attack +3, Attack Speed +3; +5 pp Attack at Lv24)", "Agile Bows (Attack Speed +5)", "Physical Training (Basic Attack Damage +10)", "Bow Mastery (Min Damage +15)",
    "Sylvan Aid (Attack +12, Critical Rate +6)", "Second Wind (Attack +12; its Attack Speed part is live)", "Featherweight (Damage +30, Normal Monster Damage +15; +half of it as Boss Monster Damage from Lv98)",
    "Eagle Eye (Final Damage +15)", "Touch of the Wind (Attack +10, Max HP +10)", "Bow Expert (Skill Damage +15, Max Damage +30)", "Albatross Max (Final Damage +10, Defense Penetration +8)",
    "masteries: Main Stat +30, Critical Rate +5, Basic Attack Damage +15, Accuracy +5, Max Damage Multiplier +10, Skill Damage +15, Basic Attack Target +1 (Lv64)",
)
FEATHERWEIGHT_BOSS_LEVEL = 98                       # mastery "Featherweight - Boss Monster Damage": Boss Monster Damage + half of Featherweight's Normal Monster Damage (typed: only the delta is modelled)

# ---- Status Effect Damage / KO timeline engine spec (src/status_timeline.py) ----
# No engine-timed buff: the buffs are cast on cooldown from t = 0 and averaged (their Attack % / Damage % are in the engine's constant A0 / bucket).
STATUS_BUFFS = []
STATUS_GROUPS = [
    ("VORTEX", "SPIRALING_VORTEX", [("SPIRALING_VORTEX", "burst", None, None, "SPIRALING_VORTEX")]),
    ("PIERCE", "PINPOINT_PIERCE_ARROW1", [
        ("PINPOINT_PIERCE_ARROW1", "burst", None, None, "PINPOINT_PIERCE_ARROW1"),
        ("PINPOINT_PIERCE_ARROW2", "burst", None, None, "PINPOINT_PIERCE_ARROW2")]),
    ("SONG", "SONG_OF_HEAVEN", [("SONG_OF_HEAVEN", "burst", None, None, "SONG_OF_HEAVEN")]),
]
# the basic attack and the procs are spread uniformly like every non-cast row
STATUS_UNIFORM_ROWS = ["FAIRY_SPIRAL", "TRIFLING_WIND", "SONG_SPIRIT_ARROWS", "STORM_BRINGER"]
STATUS_CAST_PREFIX = {}
for _gid, _cast, _ents in STATUS_GROUPS:
    for _e in _ents:
        STATUS_CAST_PREFIX.setdefault(_e[0], f"grp.{_gid}")
    STATUS_CAST_PREFIX[_cast] = f"grp.{_gid}"
# rows whose hits/s come from the engine's effective cast count (last DoT window truncated by the fight end)
STATUS_FS_KEYS = [e[0] for _g, _c, ents in STATUS_GROUPS for e in ents if e[1] in ("dot", "end")]
STATUS_PHI_ROWS = sorted({e[0] for _g, _c, ents in STATUS_GROUPS for e in ents})

# ---- flagged assumptions, one line per row (also listed in KNOWN_GAPS.md "Wind Archer") ----
ROW_NOTES = {
    "FAIRY_SPIRAL": "PROVISIONAL curve (base 2900 = 290 %, idx 21, step 4).  Basic attack from level 100 (absent below, like every class).  Damage chain = raw tiers 10/11/12/13/14/15 at 102/106/116/120/128/132 "
                    "summed, then x(1+m/100); +10 / +10 Boss Damage (Lv111 / Lv124) is its own boss mastery; +1 strike at 136.  Targets 6 + Basic Attack Target Increase (that input already contains the Lv64 mastery).",
    "SPIRALING_VORTEX": "PROVISIONAL curve (base 2500 = 250 %, idx 12, step 2).  250 x2 on 9 targets, +50 % at 39, stun 1.5 s from 49 (player stun for Status Effect Damage), Call of Cygnus Final Damage 100.  "
                        "FLAGGED unlock 30 (icon order; 30 or 35).",
    "PINPOINT_PIERCE_ARROW1": "PROVISIONAL curve (base 3300 = 330 %, idx 12, step 3).  First arrow on ONE target (boss and normal), +50 % at 68, Call of Cygnus Final Damage 40.  The second arrow is its own row "
                              "(same cast).  Weaken (Lv94): the second arrow's target takes +10 % damage for 12 s: boss / PvP branch only (one target in a pack).",
    "PINPOINT_PIERCE_ARROW2": "PROVISIONAL curve (base 7400 = 740 %, idx 12, step 3).  Second arrow of the same cast, same target.",
    "SONG_OF_HEAVEN": "PROVISIONAL curve (base 7800 = 780 %, idx 12, step 4).  13 volleys x 780 % on 9 targets (the volleys fire faster with Attack Speed: the count is fixed), +50 % at 108.  Each volley also creates "
                      "2 Spirit Arrows (+3 from Lv134), see SONG_SPIRIT_ARROWS.",
    "TRIFLING_WIND": "PROVISIONAL curves (Trifling Wind I 36 % idx 21 step 2; Trifling Wind II 100 % idx 21 step 3 REPLACES it from Lv66; Trifling Wind III Final Damage +100 % idx 21 step 4, +35 at 113).  FLAGGED: "
                     "'a skill is activated' = every cooldown cast (damage skills and buffs), at most once per 2 s; 3 arrows (+2 at 104, +2 at 130) of one random target each; masteries +50 (44) and +80 (73) "
                     "are SUMMED then multiply; the x2 chance (25 %, +15 pp at 90) is applied as its expected value 1 + p; against ONE target (boss / PvP) the arrows of a burst follow the consecutive-strike ladder "
                     "1, .8, .6, .4, .2, .2 ... (all within 0.5 s), in a pack each arrow is assumed to pick another target (no reduction).",
    "SONG_SPIRIT_ARROWS": "No own curve: the Spirit Arrows of Song of Heaven use Trifling Wind's current damage (FLAGGED).  13 volleys x 2 arrows (+3 from Lv134); consecutive on one target: the ladder floors at 20 %.",
    "STORM_BRINGER": "PROVISIONAL curve (base 11000 = 1100 %, idx 21, step 4).  FLAGGED: a skill activation starts the storm with 50 % while the skill is off its 25 s cooldown (cooldown reduced by Skill Cooldown Decrease), "
                     "the storm lasts 15 s (not extended by Buff Duration); during it every attack (basic attack, Spiraling Vortex, Pinpoint Pierce, Song of Heaven casts) rolls 30 % (+30 pp at 138) per enemy hit "
                     "(q = 1-(1-c)^N), the giant arrow has a 0.5 s cooldown (rate X/(1+0.5 X)); 1100 % on 12 targets, +50 % at 122.  Steady-state expected values (no exact windows).",
}

# ---- cross-cutting FLAGS (numbered in KNOWN_GAPS.md "Wind Archer") ----
FLAGS = {
    "unlock_icons": "unlock levels matched to the icon grid by icon (Spiraling Vortex 30, Pinpoint Pierce 63, Emerald Flower 69, Song of Heaven 103 ...)",
    "stat_screen": "always-on passives / stat masteries are NOT added (the Inputs come from the in-game stat screen); only their Sensitivity level deltas are modelled",
    "timed_buffs_averaged": "Storm Elemental / Emerald Flower (Dust) / Sharp Eyes / Elemental Harmony are cast on cooldown from t = 0 and averaged by their uptime (no engine-timed buff)",
    "emerald_taken": "Emerald Flower +15 % boss damage taken and Emerald Dust's +8 % damage taken in range are ADDED (boss 23 %, normal 8 %) while the flower lasts (20 s)",
    "stat_identity": "DEX main / STR sub assumed (a bowman like Bowmaster / Marksman)",
}
