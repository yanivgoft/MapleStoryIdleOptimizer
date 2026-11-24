"""Blaze Wizard (Cygnus Knight, INT main / LUK sub mage) static game data - ENGINE-NATIVE and PROVISIONAL: there is no workbook, builder or verify script for this class,
and (unlike Dawn Warrior) the user has so far supplied only LEVEL-1 pop-ups (fresh character, "Lv. 1" everywhere = the BASE value, factor 1.0).

Source: ``data/cygnus/blaze_wizard_ingame.md`` (the user's transcribed screenshots).  A level-1 reading gives each base EXACTLY but says nothing about the growth curve, and the
live site data (maplestoryidle.info) has NO Blaze Wizard rows, so EVERY factor index below is a CONVENTION (Dawn Warrior's: burst damage 12; basic attack, additional-damage procs and
active buffs / debuffs 21; passives 22; per-skill Final Damage "Call of Cygnus" 23) and is marked PROVISIONAL in ``CURVES`` / ``PROVISIONAL`` (ONE place to edit per skill: change the
triple in ``CURVES`` and nothing else).  The class module stays ``PUBLISHED = False`` until the user supplies one higher-level reading per skill (data/cygnus/README.md).

Conventions follow ``engine/data/dawn_warrior.py``: base damage in TENTHS of a percent (``base``), ``fidx`` the FactorTable column, ``step`` the job tier (1-4) whose skill level
scales the skill (1st job 60 + bonus, 2nd 90 +, 3rd 120 +, 4th (character level - 100) x 3 + bonus); ``(threshold, value)`` tuples / ``{level: tier value}`` chains are resolved by the
model in ``engine/classes/blaze_wizard.py``.  Mastery percentages are fixed numbers (they do not grow with the skill level).

Every judgement call is flagged in ``ROW_NOTES`` / ``FLAGS`` and in ``data/cygnus/blaze_wizard_known_gaps.md``.
"""
from collections import namedtuple

CLASS_ID = "blaze_wizard"

Curve = namedtuple("Curve", "base fidx step")        # base in tenths of %, FactorTable column, job tier

# ---- EVERY scaling curve of the class (all PROVISIONAL: bases = the level-1 values read in game, factor index and job step = convention) ----
CURVES = {
    # damage skills (burst convention: idx 12)
    "FLAME_VORTEX": Curve(2600, 12, 2),                      # 260 % x 7 targets x 2
    "FLAME_TEMPEST": Curve(3000, 12, 3),                     # 300 % x 8 x 2
    "CINDER_MAELSTROM": Curve(2700, 12, 3),                  # 270 % x 6 x 3
    "BLAZING_EXTINCTION_LION": Curve(12000, 12, 4),          # 1200 % x 9 targets every 0.5 s for 3 s
    "BLAZING_EXTINCTION_FOX": Curve(16000, 12, 4),           # 1600 % x 3 targets every 0.7 s for 5 s
    "TOWERING_INFERNO_LION": Curve(13500, 12, 4),            # 1350 % x 12 targets x 5
    "TOWERING_INFERNO_FOX": Curve(24000, 12, 4),             # 2400 % x 4 targets x 2
    "TOWERING_INFERNO_FOX_STRIKES": Curve(5500, 12, 4),      # boss only: 3 flame strikes of 550 % x 2
    # basic attack and the additional-damage proc (idx 21: Dawn Warrior's Celestial Vision III / Luna Divide, FP-Mage's Meteor Proc)
    "FINAL_ORBITAL_FLAME": Curve(2900, 21, 4),               # 290 % x 6 targets x 5 (basic attack, 4th job)
    "ORBITAL_EXPLOSION": Curve(500, 21, 2),                  # 50 % additional damage x 5 targets x 2 (passive, unlock 45)
    # timed / equipped buffs and effects (idx 21: active skills)
    "FLAME_ELEMENTAL_ATTACK": Curve(150, 21, 1),             # Attack +15 %, 12 s
    "FLASHFIRE_ATTACK": Curve(120, 21, 2),                   # Attack +12 % while the mark lasts (30 s)
    "FIRES_LION_NORMAL_DAMAGE": Curve(200, 21, 2),           # Fire Lion: Normal Monster Damage +20 %
    "FIRES_FOX_BOSS_DAMAGE": Curve(200, 21, 2),              # Flame Fox: Boss Monster Damage +20 %
    "FIRES_FINAL_DAMAGE": Curve(30, 21, 2),                  # while equipped: Final Damage +3 % (stat screen, Sensitivity delta only)
    "BURNING_CONDUIT_FD": Curve(50, 21, 4),                  # YOUR Final Damage +5 %, 20 s
    # passives (idx 22)
    "GREATER_FE_DAMAGE": Curve(200, 22, 2),                  # damage +20 % during Flame Elemental
    "GRAND_FE_BASIC_ATTACK": Curve(150, 22, 3),              # Basic Attack Damage +15 % during Flame Elemental
    "FINAL_FE_DEF_PEN": Curve(30, 22, 4),                    # Defense Penetration +3 % during Flame Elemental
    "FINAL_FE_CRIT_DAMAGE": Curve(280, 22, 4),               # Critical Damage +28 % during Flame Elemental
    "FIRE_REPULSION_ATTACK": Curve(30, 22, 1),               # Attack +3 % (stat screen, Sensitivity delta only)
    "WORD_OF_FIRE_AS": Curve(50, 22, 2),                     # Attack Speed +5 (stat screen)
    "SPELL_CONTROL_MIN": Curve(150, 22, 2),                  # Min Damage Multiplier +15 (stat screen)
    "BRILLIANT_MIN": Curve(100, 22, 3),                      # Min Damage Multiplier +10 (stat screen)
    "BRILLIANT_MAX": Curve(200, 22, 3),                      # Max Damage Multiplier +20 (stat screen)
    "BURNING_FOCUS_CRIT_RATE": Curve(80, 22, 3),             # Critical Rate +8 (stat screen)
    "BURNING_FOCUS_CRIT_DAMAGE": Curve(160, 22, 3),          # Critical Damage +16 (stat screen)
    "LIBERATED_MAGIC_FD": Curve(150, 22, 3),                 # Final Damage +15 while MP >= 35 % (stat screen)
    "PHOENIX_RUN_FD": Curve(100, 22, 4),                     # Final Damage +10 (stat screen)
    "FLAME_BARRIER_ATTACK": Curve(50, 22, 4),                # Attack +5 (stat screen)
    "PURE_MAGIC_SKILL": Curve(150, 22, 4),                   # Skill Damage +15 (stat screen)
    "PURE_MAGIC_MAX": Curve(200, 22, 4),                     # Max Damage Multiplier +20 (stat screen)
    "WILD_BLAZE_FD": Curve(120, 22, 4),                      # Final Damage +12 (stat screen); its +6 % Buff Duration is a typed input
    # Call of Cygnus: per-skill Final Damage multiplier 1 + pct/100 (idx 23, 4th job)
    "CYGNUS_FLAME_VORTEX": Curve(600, 23, 4),
    "CYGNUS_FLAME_TEMPEST": Curve(350, 23, 4),
    "CYGNUS_CINDER_MAELSTROM": Curve(300, 23, 4),
    "CYGNUS_ORBITAL_EXPLOSION": Curve(700, 23, 4),
}
# Every curve is a convention (no site table row, no higher-level reading yet): the flag the user's later scaling data flips one skill at a time (move a name out of this set once resolved).
PROVISIONAL = set(CURVES)


def is_provisional(name):
    return name in PROVISIONAL


SKILL_NAMES = {
    "FINAL_ORBITAL_FLAME": "Final Orbital Flame (basic attack)",
    "ORBITAL_EXPLOSION": "Orbital Explosion (basic-attack proc)",
    "FLAME_VORTEX": "Flame Vortex",
    "FLAME_TEMPEST": "Flame Tempest",
    "CINDER_MAELSTROM": "Cinder Maelstrom",
    "BLAZING_EXTINCTION_FOX": "Blazing Extinction (Flame Fox: boss)",
    "BLAZING_EXTINCTION_LION": "Blazing Extinction (Fire Lion: normal monsters)",
    "TOWERING_INFERNO_FOX": "Towering Inferno (Flame Fox: boss)",
    "TOWERING_INFERNO_FOX_STRIKES": "Towering Inferno (Flame Fox: boss flame strikes)",
    "TOWERING_INFERNO_LION": "Towering Inferno (Fire Lion: normal monsters)",
}

# Result rows (damage rows only)
DPS_ROW_ORDER = ["FINAL_ORBITAL_FLAME", "ORBITAL_EXPLOSION", "FLAME_VORTEX", "FLAME_TEMPEST", "CINDER_MAELSTROM", "BLAZING_EXTINCTION_FOX",
                 "BLAZING_EXTINCTION_LION", "TOWERING_INFERNO_FOX", "TOWERING_INFERNO_FOX_STRIKES", "TOWERING_INFERNO_LION"]

# Unlock levels (FLAGGED: matched to the two Skill-window grids BY ICON ORDER, the user has not confirmed the mapping).  Active grid: three level-less icons, 30, 35, 50, 60, 60, 63, 69, 100,
# 103, 110, 115 (14 icons for the 11 transcribed actives: Flame Tempest 60, Cinder Maelstrom 63 are the most plausible reading; the extra 60 / 69 / level-less icons are not DPS skills of this
# model).  Passive grid: none, none, 33, 38, 40, 43, 45, 66, 72, 74, 75, 100, 105, 107, 117, 120, 125 (read in the order of the transcription).
# The basic attack (Final Orbital Flame) is the 4th-job one: unlocked at 100 and ABSENT below it, like every class (no pre-100 / 3rd-job basic attack is modelled).
UNLOCK_LEVEL = {
    "FINAL_ORBITAL_FLAME": 100,
    "ORBITAL_EXPLOSION": 45,
    "FLAME_VORTEX": 30,
    "FLAME_TEMPEST": 60,
    "CINDER_MAELSTROM": 63,
    "BLAZING_EXTINCTION_FOX": 103,
    "BLAZING_EXTINCTION_LION": 103,
    "TOWERING_INFERNO_FOX": 110,
    "TOWERING_INFERNO_FOX_STRIKES": 110,
    "TOWERING_INFERNO_LION": 110,
    # buffs / passives with a live (timed / conditional / per-skill) effect
    "ELEMENTAL_HARMONY": 0,
    "FLAME_ELEMENTAL": 0,
    "FLASHFIRE": 35,
    "FIRES_OF_CREATION": 50,
    "BURNING_CONDUIT": 115,
    "GREATER_FLAME_ELEMENTAL": 40,
    "GRAND_FLAME_ELEMENTAL": 74,
    "FINAL_FLAME_ELEMENTAL": 105,
    "CALL_OF_CYGNUS": 100,
}

# ---- Final Orbital Flame (the basic attack) ----
FOF_HITS = (5, 136, 6)                              # 5 hits, +1 strike from level 136 (mastery "Final Orbital Flame - Strike")
FOF_MASTERY = {102: 10, 106: 11, 116: 12, 120: 13, 128: 14, 132: 15}      # Damage mastery chain: raw tiers, summed, then x(1 + m/100) (CLAUDE.md bug 2)
FOF_BOSS_MASTERY = {111: 10, 124: 10}                                      # "+X% Boss Monster Damage to Final Orbital Flame"
FOF_BASE_TARGETS = 6                                # + the Basic Attack Target Increase input (already contains the Lv64 mastery)
LION_BASIC_TARGET = (73, 1)                         # (threshold, +targets) Fires of Creation - Lion: +1 Basic Attack target while Fire Lion is summoned (normal-monster branch)

# ---- Orbital Explosion (passive, unlock 45) ----
ORBITAL_EXPLOSION = dict(chance=60, icd=1.0, hits=2, targets=5, window=15.0, period=30.0, mastery={54: 50})
ORBITAL_EXPLOSION_CYGNUS = "CYGNUS_ORBITAL_EXPLOSION"

# ---- timed buffs ----
FLAME_ELEMENTAL = dict(duration=12, cooldown=28, duration_mastery=(21, 1.5))      # Attack %, 12 s x1.5 from the level 21 mastery
GREATER_FE_MASTERY = {44: 10}                       # "Greater Flame Elemental - Damage: additionally +10 %p" (raw, adds to the scaled 20)
GRAND_FE_SKILL_DAMAGE = {82: 15}                    # "Grand Flame Elemental - Skill Damage: +15 % for the duration of Flame Elemental" (raw)
FINAL_FE_FD = {130: 3}                              # "Final Flame Elemental - Final Damage: +3 % for the duration of Flame Elemental" (raw)
FLASHFIRE = dict(duration=30, cooldown=10)          # Attack % while the fire mark lasts (30 s)
BURNING_CONDUIT = dict(duration=20, cooldown=40)    # YOUR Final Damage % for 20 s (allied players' buffs ignored)
ELEMENTAL_HARMONY = dict(duration=15, cooldown=60, attack_speed=15)   # Attack Speed +15 % (+10 % movement speed ignored); no level shown in game -> not level-scaling

# ---- Fires of Creation (Lion / Fox incarnate) ----
FOX_DEF_PEN = {94: 5}                               # "Fires of Creation - Fox: Defense Penetration +5 %" (raw, boss branch)
FIRES_FD_MASTERY = {104: 3}                         # "Fires of Creation - Final Damage: additionally +3 %p" (stat screen, Sensitivity delta only is level-dependent: this is raw)
LION_TOWERING_NORMAL_DAMAGE = {138: 150}            # "Towering Inferno - Incarnation: Fire Lion +150 % additional Normal Monster Damage" (that row only)
FOX_TOWERING_STRIKES = (3, 138, 4)                  # Flame Fox: 3 flame strikes against bosses, +1 at the level 138 mastery
FOX_TOWERING_STRIKE_HITS = 2                        # each strike deals 550 % 2 times

# ---- Cinder Maelstrom's weaken (mastery 98): targets take +9 % damage for 14 s ----
CINDER_WEAKEN = dict(level=98, pct=9, duration=14)

# ---- damage rows ----
# step, cooldown (s), hits, base / fidx (from CURVES), mastery chain {level: %} (multiplies the skill), boss / normal mastery %, normal-monster targets, costs_action;
# ``icd`` / ``window`` = tick rows (``icd`` is a (default, (threshold, value)) tier); ``branch``: "both" (default) / "boss" (Flame Fox variant, boss / PvP branch only) / "normal" (Fire Lion variant);
# ``cast_row``: the row whose cast this row shares (cooldown / action slot); ``cygnus``: key into CURVES (per-skill Final Damage multiplier 1 + pct/100).
DAMAGE_SKILLS = {
    "FLAME_VORTEX": dict(curve="FLAME_VORTEX", cooldown=18, hits=2, mastery={39: 70}, targets=7, costs_action=True, cygnus="CYGNUS_FLAME_VORTEX"),
    "FLAME_TEMPEST": dict(curve="FLAME_TEMPEST", cooldown=20, hits=2, mastery={68: 80}, targets=8, costs_action=True, cygnus="CYGNUS_FLAME_TEMPEST"),
    "CINDER_MAELSTROM": dict(curve="CINDER_MAELSTROM", cooldown=23, hits=3, mastery={78: 50}, targets=6, costs_action=True, cygnus="CYGNUS_CINDER_MAELSTROM"),
    "BLAZING_EXTINCTION_FOX": dict(curve="BLAZING_EXTINCTION_FOX", cooldown=32, hits=1, icd=(0.7, (126, 0.5)), window=5, mastery={108: 50}, targets=3,
                                   costs_action=True, branch="boss"),
    "BLAZING_EXTINCTION_LION": dict(curve="BLAZING_EXTINCTION_LION", cooldown=32, hits=1, icd=(0.5, (126, 0.4)), window=3, mastery={108: 50}, targets=9,
                                    costs_action=False, branch="normal", cast_row="BLAZING_EXTINCTION_FOX"),
    "TOWERING_INFERNO_FOX": dict(curve="TOWERING_INFERNO_FOX", cooldown=21, hits=2, mastery={113: 50}, targets=4, costs_action=True, branch="boss"),
    "TOWERING_INFERNO_FOX_STRIKES": dict(curve="TOWERING_INFERNO_FOX_STRIKES", cooldown=21, hits=None, mastery={113: 50}, targets=1, costs_action=False,
                                         branch="boss", cast_row="TOWERING_INFERNO_FOX"),
    "TOWERING_INFERNO_LION": dict(curve="TOWERING_INFERNO_LION", cooldown=21, hits=5, mastery={113: 50}, mastery_normal=LION_TOWERING_NORMAL_DAMAGE, targets=12,
                                  costs_action=False, branch="normal", cast_row="TOWERING_INFERNO_FOX"),
}

# Action-costing rows (cast rate subtracted from the basic attack), in order: damage rows read DAMAGE_SKILLS, buffs BUFF_COOLDOWNS
COST_ACTION_ORDER = ["FLAME_VORTEX", "FLAME_TEMPEST", "CINDER_MAELSTROM", "BLAZING_EXTINCTION_FOX", "TOWERING_INFERNO_FOX",
                     "FLAME_ELEMENTAL", "FLASHFIRE", "BURNING_CONDUIT", "ELEMENTAL_HARMONY"]
BUFF_COOLDOWNS = {"FLAME_ELEMENTAL": 28, "FLASHFIRE": 10, "BURNING_CONDUIT": 40, "ELEMENTAL_HARMONY": 60}
BUFF_ROW_KEYS = ["FLAME_ELEMENTAL", "FLASHFIRE", "BURNING_CONDUIT", "ELEMENTAL_HARMONY"]
STARTUP_BUFFS = ["FLAME_ELEMENTAL", "FLASHFIRE", "BURNING_CONDUIT", "ELEMENTAL_HARMONY"]       # actively cast buffs -> startup delay / engine-off t0

# ---- player's own stuns: Cinder Maelstrom 1.5 s, Flame Tempest 1 s from level 90; cast on cooldown from the start ----
PLAYER_STUN = [dict(id="MAELSTROM", key="CINDER_MAELSTROM", typ="cast", dur=1.5, p=1.0),
               dict(id="TEMPEST", key="FLAME_TEMPEST", typ="cast", dur=1.0, p=1.0, level=90)]

# ---- always-on effects classed as "already in the stat screen" (documentation + the Sensitivity spec's PASSIVE_LEVELS; NOT added to the model) ----
STAT_SCREEN_EFFECTS = (
    "Fire Repulsion (Attack +3, +5 pp at Lv24; its Defense is not a DPS stat)", "Word of Fire (Attack Speed +5)", "Controlled Burn mastery (Lv49: Attack Speed +7 while MP >= 35 %)",
    "Spell Control (Min Damage +15)", "Brilliant Enlightenment (Min +10 / Max +20)", "Burning Focus (Crit Rate +8, Crit Damage +16)",
    "Liberated Magic (Final Damage +15 while MP >= 35 %)", "Phoenix Run (Final Damage +10, x2 from Lv118)", "Flame Barrier (Attack +5, +10 pp at Lv134)",
    "Pure Magic (Skill Damage +15, Max Damage +20)", "Wild Blaze (Final Damage +12, Buff Duration +6)", "Fires of Creation (Final Damage +3, +3 pp at Lv104, while equipped)",
    "masteries: Main Stat +30, Critical Rate +5, Basic Attack Damage +15, Accuracy +5, Max Damage Multiplier +10, Skill Damage +15, Basic Attack Target +1 (Lv64)",
)

# ---- Status Effect Damage / KO timeline engine spec (src/status_timeline.py) ----
# No engine-timed buff: Flame Elemental / Flashfire / Burning Conduit / Elemental Harmony are cast on cooldown from t = 0 and averaged (their Attack % is in the engine's constant A0).
STATUS_BUFFS = []
STATUS_GROUPS = [
    ("VORTEX", "FLAME_VORTEX", [("FLAME_VORTEX", "burst", None, None, "FLAME_VORTEX")]),
    ("TEMPEST", "FLAME_TEMPEST", [("FLAME_TEMPEST", "burst", None, None, "FLAME_TEMPEST")]),
    ("MAELSTROM", "CINDER_MAELSTROM", [("CINDER_MAELSTROM", "burst", None, None, "CINDER_MAELSTROM")]),
    ("EXTINCTION", "BLAZING_EXTINCTION_FOX", [("BLAZING_EXTINCTION_FOX", "dot", "BLAZING_EXTINCTION_FOX", None, "BLAZING_EXTINCTION_FOX")]),
    ("INFERNO", "TOWERING_INFERNO_FOX", [
        ("TOWERING_INFERNO_FOX", "burst", None, None, "TOWERING_INFERNO_FOX"),
        ("TOWERING_INFERNO_FOX_STRIKES", "burst", None, None, "TOWERING_INFERNO_FOX_STRIKES")]),
]
# The Fire Lion rows are the normal-monster branch (the timeline is boss-branch only); the basic attack and the proc are spread uniformly like every non-cast row
STATUS_UNIFORM_ROWS = ["FINAL_ORBITAL_FLAME", "ORBITAL_EXPLOSION"]
STATUS_CAST_PREFIX = {}
for _gid, _cast, _ents in STATUS_GROUPS:
    for _e in _ents:
        STATUS_CAST_PREFIX.setdefault(_e[0], f"grp.{_gid}")
    STATUS_CAST_PREFIX[_cast] = f"grp.{_gid}"
# rows whose hits/s come from the engine's effective cast count (last DoT window truncated by the fight end)
STATUS_FS_KEYS = [e[0] for _g, _c, ents in STATUS_GROUPS for e in ents if e[1] in ("dot", "end")]
STATUS_PHI_ROWS = sorted({e[0] for _g, _c, ents in STATUS_GROUPS for e in ents})

# ---- flagged assumptions, one line per row (also listed in data/cygnus/blaze_wizard_known_gaps.md) ----
ROW_NOTES = {
    "FINAL_ORBITAL_FLAME": "PROVISIONAL curve (base 2900 = 290 %, idx 21, step 4).  Basic attack from level 100 (absent below, like every class).  Damage chain = raw tiers 10/11/12/13/14/15 summed then "
                           "x(1+m/100); +10 / +10 Boss Damage (Lv111 / Lv124) is its own boss mastery; +1 strike at 136.  Targets 6 + Basic Attack Target Increase (that input already "
                           "contains the Lv64 mastery); FLAGGED: +1 more target in the NORMAL branch from Lv73 (Fires of Creation - Fire Lion).  Grand Flame Elemental's Basic Attack "
                           "Damage is time-averaged by Flame Elemental's uptime.",
    "ORBITAL_EXPLOSION": "PROVISIONAL curve (base 500 = 50 %, idx 21, step 2).  FLAGGED: counted as SKILL damage (no [Basic Attack Effect] tag, like Meteor Proc); fire energy "
                         "lasts 15 s from the battle start and 'activates every 30 s' (window average 15/30, exact windows in fixed fights: [0,15) [30,45) [60,75); no Skill Cooldown "
                         "Decrease / Buff Duration on this interval); while it is up each Basic Attack rolls 60 % per enemy hit (q = 1-(1-0.6)^N, N = enemies the basic attack hits: 1 on "
                         "boss / PvP), at most one explosion per 1 s (rate X/(1+X)); 2 hits on 5 targets; +50 % damage at 54 (multiplies); Call of Cygnus +70 % Final Damage (per-skill).",
    "FLAME_VORTEX": "PROVISIONAL curve (base 2600 = 260 %, idx 12, step 2).  260 x2 on 7 targets, +70 % damage at 39, Call of Cygnus Final Damage 60 (per-skill multiplier 1 + pct/100, Dawn Warrior's convention).",
    "FLAME_TEMPEST": "PROVISIONAL curve (base 3000 = 300 %, idx 12, step 3).  300 x2 on 8 targets, +80 % at 68, stun 1 s from 90 (player stun for Status Effect Damage), Call of Cygnus Final Damage 35.",
    "CINDER_MAELSTROM": "PROVISIONAL curve (base 2700 = 270 %, idx 12, step 3).  270 x3 on 6 targets, +50 % at 78, stun 1.5 s, Call of Cygnus Final Damage 30.  FLAGGED unlock 63 (icon order).  Weaken (Lv98): "
                        "+9 % damage taken for 14 s joins the monster-damage-taken term of BOTH branches (True Sight convention), uptime = 14 s x (1 + Buff Duration) / effective cooldown.",
    "BLAZING_EXTINCTION_FOX": "PROVISIONAL curve (base 16000 = 1600 %, idx 12, step 4).  FLAGGED: the Flame Fox variant is the BOSS / PvP branch (the game summons the Fox against a boss, the Lion otherwise): 1600 per "
                              "strike on 3 targets every 0.7 s for 5 s (0.5 s from Lv126 = 'Fox -0.2 s'); +50 % at 108; the window is not extended by Buff Duration Increase.  Requires Fires of "
                              "Creation (Lv50).  A swap between incarnates (3 s cooldown skill) is not charged.",
    "BLAZING_EXTINCTION_LION": "PROVISIONAL curve (base 12000 = 1200 %, idx 12, step 4).  FLAGGED: the Fire Lion variant is the NORMAL-monster branch only: 1200 per strike on 9 targets every 0.5 s for 3 s "
                               "(0.4 s from Lv126), same cast / cooldown as the Fox row; strikes counted whole (floor(window / interval)).",
    "TOWERING_INFERNO_FOX": "PROVISIONAL curve (base 24000 = 2400 %, idx 12, step 4).  Boss / PvP branch (Flame Fox): 2400 x2 on 4 targets, +50 % at 113.",
    "TOWERING_INFERNO_FOX_STRIKES": "PROVISIONAL curve (base 5500 = 550 %, idx 12, step 4).  Boss branch only: 3 flame strikes (4 from Lv138) of 550 x2 each ('against bosses').  FLAGGED: the Lv113 +50 % mastery "
                                    "is assumed to apply to it; counted as part of the same Towering Inferno cast.",
    "TOWERING_INFERNO_LION": "PROVISIONAL curve (base 13500 = 1350 %, idx 12, step 4).  Normal branch only (Fire Lion): 1350 x5 on 12 targets, +50 % at 113, and from Lv138 +150 % Normal Monster Damage for THIS row "
                             "(added to the row's own Normal Monster Damage term).",
}

# ---- cross-cutting FLAGS (numbered in data/cygnus/blaze_wizard_known_gaps.md) ----
FLAGS = {
    "unlock_icons": "unlock levels matched to the icon grid by ORDER (Flame Tempest 60, Cinder Maelstrom 63, Towering Inferno 110 ...)",
    "stat_screen": "always-on passives / stat masteries are NOT added (the Inputs come from the in-game stat screen); only their Sensitivity level deltas are modelled",
    "incarnate_branch": "Fox = boss / PvP branch, Lion = normal-monster branch (the game picks Fox vs a boss, Lion otherwise)",
    "timed_buffs_averaged": "Flame Elemental / Flashfire / Burning Conduit / Elemental Harmony are cast on cooldown from t = 0 and averaged by their uptime (no engine-timed buff)",
}
