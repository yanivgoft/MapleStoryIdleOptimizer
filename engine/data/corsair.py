"""Corsair static game data, as plain Python data (transcribed from ``src/build_corsair_workbook.py`` / ``src/verify_corsair_workbook.py``; the
builder stays the workbook's source, this module is the engine's copy - keep both in sync when a skill changes).  Level-dependent values
(hit counts, windows, target counts, mastery bonuses that switch on at a level) are described here as ``(threshold, value)`` tuples /
``{level: tier value}`` chains and resolved by the model in ``engine/classes/corsair.py``.

Base-damage numbers are in tenths of a percent (``base``); ``fidx`` is the FactorTable column; ``step`` the job tier (1-4) whose skill level
scales the skill.  ``mastery`` chains are raw tier values summed over every reached level (CLAUDE.md bug 2) and MULTIPLY the skill's damage.
"""

SKILL_NAMES = {
    "EIGHT_LEGS_EASTON": "Eight-Legs Easton",
    "SWIFT_FIRE": "Swift Fire",
    "SCURVY_SUMMONS": "Scurvy Summons",
    "ALL_ABOARD": "All Aboard",
    "BLACKBOOT_BILL": "Blackboot Bill",
    "SIEGE_BOMBER": "Siege Bomber",
    "BRAIN_SCRAMBLER": "Brain Scrambler",
    "NAUTILUS_STRIKE": "Nautilus Strike",
    "NAUTILUS_FINAL_ATTACK": "Nautilus Strike - Final Attack",
    "RAPID_FIRE": "Rapid Fire",
    "BROADSIDE_BURST": "Broadside (initial burst)",
    "BROADSIDE_SUSTAINED": "Broadside (sustained turret)",
    "MAJESTIC_PRESENCE": "Majestic Presence",
}

# Result rows = the workbook's Skills-sheet order (damage rows only)
DPS_ROW_ORDER = ["EIGHT_LEGS_EASTON", "SWIFT_FIRE", "SCURVY_SUMMONS", "ALL_ABOARD", "BLACKBOOT_BILL", "SIEGE_BOMBER", "BRAIN_SCRAMBLER",
                 "NAUTILUS_STRIKE", "NAUTILUS_FINAL_ATTACK", "RAPID_FIRE", "BROADSIDE_BURST", "BROADSIDE_SUSTAINED", "MAJESTIC_PRESENCE"]

# Unlock level of every row that has a threshold (rows not listed - Nimble Feet - are unlocked from the start)
UNLOCK_LEVEL = {
    "EIGHT_LEGS_EASTON": 100,
    "SWIFT_FIRE": 33,
    "SCURVY_SUMMONS": 35,
    "ALL_ABOARD": 69,
    "BLACKBOOT_BILL": 66,
    "SIEGE_BOMBER": 63,
    "BRAIN_SCRAMBLER": 103,
    "NAUTILUS_STRIKE": 105,
    "NAUTILUS_FINAL_ATTACK": 113,
    "RAPID_FIRE": 117,
    "BROADSIDE_BURST": 110,
    "BROADSIDE_SUSTAINED": 110,
    "MAJESTIC_PRESENCE": 120,
    "MAPLE_HERO_HELPER": 100,
    "AHOY_MATEYS_HELPER": 107,
    "ROLL_OF_THE_DICE_DICE": 74,
    "JOLLY_ROGER_FD": 115,
    "SHADOW_HEART": 10,
    "QUICK_MOTION": 15,
    "AGILE_GUNS": 40,
    "GUN_MASTERY": 43,
    "PHYSICAL_TRAINING": 38,
    "INFINITY_BLAST_ATK": 45,
    "FULLMETAL_JACKET_CD": 72,
    "CROSS_CUT_BLAST_FD": 75,
    "QUICKDRAW_BAD": 125,
}

# Maple Hero (Lv.100) helper: level-1 anchors Siege Bomber 20%, Blackboot Bill 40%, Swift Fire 80% => each skill's share relative to the 20 reference
# (the division is kept literal: identical float to the builder's)
MAPLE_HERO_RATIOS = {"SIEGE_BOMBER": 20 / 20, "BLACKBOOT_BILL": 40 / 20, "SWIFT_FIRE": 80 / 20}
MAPLE_HERO = dict(base=200, fidx=23, step=4)
# Ahoy Mateys (Lv.107): +250% Final Damage of Scurvy Summons (Dual Pistol Crew) / +100% of All Aboard (Sharpshooter Crew)
AHOY_MATEYS_RATIOS = {"SCURVY_SUMMONS": 250 / 250, "ALL_ABOARD": 100 / 250}
AHOY_MATEYS = dict(base=2500, fidx=21, step=4)

# ---- Eight-Legs Easton (basic attack) ----
EASTON_BASE = 290                                                       # %, factor index 21, 4th job (the script's literal 290)
EASTON_HITS = (5, 136, 6)                                               # 5 lines, 6 from level 136
EASTON_MASTERY = {102: 10, 106: 11, 116: 12, 120: 13, 128: 14, 132: 15}  # Damage mastery chain (raw tiers)
EASTON_BOSS_MASTERY = {111: 10, 124: 10}                                 # Boss Damage mastery chain
EASTON_QUICKDRAW_MULT = 1 + 1 / 3                                        # Quickdraw (Lv125): every 3rd Easton cast deals double damage

# ---- Roll of the Dice (dice component only, Attack%): 5 s of every 7 s roll ----
ROLL_OF_THE_DICE = dict(base=25, fidx=22, step=3, num=5, den=7)
# ---- Jolly Roger (Final Damage buff, 42 s cooldown / 18 s) ----
JOLLY_ROGER = dict(base=150, fidx=21, step=4, cooldown=42, duration=18)
# ---- Ahoy Mateys - Final Damage proc (mastery Lv122): +20% FD for 20 s, tied to Scurvy Summons' cooldown ----
AHOY_FD_PROC = dict(level=122, pct=20, duration=20, cooldown=35)
# ---- Nimble Feet (Attack Speed %, non-scaling, 60 s / 15 s) ----
NIMBLE_FEET = dict(base=150, fidx=0, step=1, duration=15, cooldown=60)
# ---- Swift Fire - Weaken (Lv54): 3 strikes x 3% (max 3 stacks = 9%) for 8 s per cast ----
SWIFT_WEAKEN = dict(level=54, pct=9, duration=8, cooldown=17)

# ---- Crew windows: 20 s, x(1 + Buff Duration) from All Aboard - Persistence @104 capped at the 35 s cooldown; strike intervals -30% @94 ----
CREW = dict(base_window=20, persistence_level=104, cap=35, strike_level=94, strike_mult=0.7, scurvy_icd=1.5, all_aboard_icd=2)
SIEGE_WINDOW = (22, 68, 30)             # 22 s, 30 s from Lv68
BOMBARD_LEVEL = 118                     # Broadside Bombardment replaces the turret ticks
BROADSIDE_SETUP_LEVEL = 138             # Setup: 30 s window

# ---- Quickdraw (Lv125) cooldown effect: closed-form fixed point of the basic-attack rate (see the verify script) ----
QD_COOLDOWN_KEYS = ("BRAIN_SCRAMBLER", "RAPID_FIRE")
QD_K = 0.25                             # 1.5 s per 3 Easton casts, split between the two skills: 1.5/3/2

# Action-costing rows in the verify script's COST_ACTION_ROWS order: (key, base cooldown, costs_action, actions per cast).  Summation order matters bit-for-bit.
BLACKBOOT_COOLDOWN = 23
COST_ACTION_ROWS = [
    ("SWIFT_FIRE", 17, True, 1),
    ("SCURVY_SUMMONS", 35, True, 1),
    ("BLACKBOOT_BILL", BLACKBOOT_COOLDOWN, True, 1),
    ("SIEGE_BOMBER", 22, True, 1),
    ("BRAIN_SCRAMBLER", 18, True, 1),
    ("NAUTILUS_STRIKE", 33, True, 1),
    ("RAPID_FIRE", 17, True, 1),
    ("BROADSIDE_BURST", 20, True, 1),
]
# actively cast buffs that count in the cast rate / the startup delay (Nimble Feet 60 s, Jolly Roger 42 s)
CAST_BUFFS = [("NIMBLE_FEET", 60), ("JOLLY_ROGER_FD", 42)]

# ---- damage rows (the verify script's DAMAGE_SKILLS dict order; summation order matters bit-for-bit) ----
# Level-dependent entries are resolved by the model: ``icd`` / ``window`` / ``hits`` / ``base`` / ``targets`` that are tuples ``(threshold, below, at_or_above)``
# are picked by level; the string "crew" marks the crew window / strike interval of Scurvy Summons and All Aboard.
DAMAGE_SKILLS = {
    "SWIFT_FIRE": dict(step=2, cooldown=17, hits=3, base=1800, fidx=12, mastery={39: 50}, costs_action=True, targets=8),
    "SCURVY_SUMMONS": dict(step=2, cooldown=35, hits=2, icd="crew_scurvy", window="crew", base=950, fidx=12, mastery={49: 50}, costs_action=True,
                           targets=3),
    "ALL_ABOARD": dict(step=3, cooldown=35, hits=3, icd="crew_all_aboard", window="crew", base=1100, fidx=12, mastery={78: 50}, costs_action=True,
                       targets=8),
    "BLACKBOOT_BILL": dict(step=3, cooldown=BLACKBOOT_COOLDOWN, hits=4, base=1700, fidx=12, mastery={73: 50}, costs_action=True, targets=9),
    "SIEGE_BOMBER": dict(step=3, cooldown=22, hits=1, icd=1.5, window="siege", base=1900, fidx=12, mastery={82: 50}, costs_action=True, targets=6),
    "BRAIN_SCRAMBLER": dict(step=4, cooldown=18, hits=2, base=29000, fidx=12, mastery={108: 100}, costs_action=True, targets=1),
    "NAUTILUS_STRIKE": dict(step=4, cooldown=33, hits=5, base=19500, fidx=12, mastery={126: 50}, costs_action=True, targets=15),
    "RAPID_FIRE": dict(step=4, cooldown=17, hits=7, base=18000, fidx=12, mastery={130: 70}, costs_action=True, targets=9),
    "BROADSIDE_BURST": dict(step=4, cooldown=20, hits=2, base=50000, fidx=12, mastery={}, costs_action=True, targets=10),
    # Bombardment @118 replaces the turret ticks (19000 tenths% x3 hits x8 targets); Setup @138 => 30 s window
    "BROADSIDE_SUSTAINED": dict(step=4, cooldown=20, hits=(118, 1, 3), icd=2, window=(138, 20, 30), base=(118, 3300, 19000), fidx=12, mastery={},
                                costs_action=True, targets=(118, 5, 8)),
}

# ---- chance procs ----
NAUTILUS_FA = dict(base=8500, fidx=21, step=4, chance=0.30, icd=1.0, targets=1)                      # any attack, 30%, 1 s ICD
NAUTILUS_FA_TRIGGERS = ("SWIFT_FIRE", "BLACKBOOT_BILL", "BRAIN_SCRAMBLER", "NAUTILUS_STRIKE", "RAPID_FIRE")   # direct-attack skills (+ Easton)
MAJESTIC_PRESENCE = dict(base=18000, fidx=21, step=4, mastery={134: 50}, chance=0.25, icd=0.5, targets=6)
# patch 2026-11-26: every Majestic Presence proc also gives the player +8 % Final Damage for 5 s (a proc-refreshed buff: Poisson uptime 1 - exp(-rate x 5), not timed by the strip)
MAJESTIC_FD = dict(pct=8.0, duration=5.0)
MAJESTIC_SOURCES = ("BRAIN_SCRAMBLER", "RAPID_FIRE")                                                  # (+ Easton)

# ---- player's own stun (game table): Blackboot Bill stuns for 2 s (cooldown 23 s), cast on cooldown from the start (from its unlock, Lv66) ----
PLAYER_STUN = [dict(id="BILL", key="BLACKBOOT_BILL", typ="cast", dur=2.0, p=1.0, cd=BLACKBOOT_COOLDOWN)]

# ---- Status Effect Damage / KO timeline engine spec (src/status_timeline.py) ----
# Jolly Roger (Final Damage) is the only engine-timed buff ('ramp' kind with a flat profile).
STATUS_BUFFS = [("JR", "JOLLY_ROGER_FD", "ramp")]
# (group id, row key whose cooldown gives the cast spacing, [(row key, type, window row key or None, unlock-gate row key or None, weight row key)])
STATUS_GROUPS = [
    ("SWIFT", "SWIFT_FIRE", [("SWIFT_FIRE", "burst", None, None, "SWIFT_FIRE")]),
    ("SCURVY", "SCURVY_SUMMONS", [
        ("SCURVY_SUMMONS", "dot", "SCURVY_SUMMONS", None, "SCURVY_SUMMONS"),
        ("ALL_ABOARD", "dot", "ALL_ABOARD", "ALL_ABOARD", "ALL_ABOARD")]),
    ("BILL", "BLACKBOOT_BILL", [("BLACKBOOT_BILL", "burst", None, None, "BLACKBOOT_BILL")]),
    ("SIEGE", "SIEGE_BOMBER", [("SIEGE_BOMBER", "dot", "SIEGE_BOMBER", None, "SIEGE_BOMBER")]),
    ("BRAIN", "BRAIN_SCRAMBLER", [("BRAIN_SCRAMBLER", "burst", None, None, "BRAIN_SCRAMBLER")]),
    ("NAUT", "NAUTILUS_STRIKE", [("NAUTILUS_STRIKE", "burst", None, None, "NAUTILUS_STRIKE")]),
    ("RAPID", "RAPID_FIRE", [("RAPID_FIRE", "burst", None, None, "RAPID_FIRE")]),
    ("BROAD", "BROADSIDE_BURST", [
        ("BROADSIDE_BURST", "burst", None, None, "BROADSIDE_BURST"),
        ("BROADSIDE_SUSTAINED", "dot", "BROADSIDE_SUSTAINED", None, "BROADSIDE_SUSTAINED")]),
]
# rows spread uniformly over the fight (the order is the verify script's summation order of the uniform boss total)
STATUS_UNIFORM_ROWS = ["EIGHT_LEGS_EASTON", "NAUTILUS_FINAL_ATTACK", "MAJESTIC_PRESENCE"]
STATUS_CAST_PREFIX = {key: f"buff.{bid}" for bid, key, _k in STATUS_BUFFS}
for _gid, _cast, _ents in STATUS_GROUPS:
    for _e in _ents:
        STATUS_CAST_PREFIX.setdefault(_e[0], f"grp.{_gid}")
    STATUS_CAST_PREFIX[_cast] = f"grp.{_gid}"
# rows whose hits/s come from the engine's effective cast count (last DoT window truncated by the fight end)
STATUS_FS_KEYS = [e[0] for _g, _c, ents in STATUS_GROUPS for e in ents if e[1] in ("dot", "end")]
STATUS_PHI_ROWS = sorted({e[0] for _g, _c, ents in STATUS_GROUPS for e in ents})
