"""Paladin static game data, as plain Python data (transcribed from ``src/build_paladin_workbook.py`` / ``src/verify_paladin_workbook.py``; the
builder stays the workbook's source, this module is the engine's copy - keep both in sync when a skill changes; ``tests/golden/check_paladin_fake.py``
cross-checks the tables that the builder exports).  Level-dependent values (cooldown haste, target counts, mastery bonuses that switch on at a level)
are described here as ``(threshold, value)`` tuples / ``{level: tier value}`` chains and resolved by the model in ``engine/classes/paladin.py``.

Base-damage numbers are in tenths of a percent (``base``); ``fidx`` is the FactorTable column; ``step`` the job tier (1-4) whose skill level
scales the skill.  ``gated`` chains are raw tier values summed over every reached level (CLAUDE.md bug 2).
"""

SKILL_NAMES = {
    "BLAST": "Blast",
    "CLOSE_COMBAT": "Close Combat",
    "NOBLE_DEMAND": "Noble Demand",
    "HEAVENS_HAMMER": "Heaven's Hammer",
    "DIVINE_MARK_MAIN": "Divine Mark (main hit)",
    "DIVINE_MARK_DETONATION": "Divine Mark (detonation)",
    "DIVINE_JUDGMENT": "Divine Judgment (detonation)",
    "MAGIC_CRASH": "Magic Crash",
    "RUSH": "Rush",
}

# Result rows in the workbook's Skills-sheet order (damage rows only)
DPS_ROW_ORDER = ["BLAST", "CLOSE_COMBAT", "NOBLE_DEMAND", "HEAVENS_HAMMER", "DIVINE_MARK_MAIN", "DIVINE_MARK_DETONATION", "DIVINE_JUDGMENT",
                 "MAGIC_CRASH", "RUSH"]

# Unlock level of every row that has a threshold (rows not listed - Nimble Feet - are unlocked from the start)
UNLOCK_LEVEL = {
    "BLAST": 100,
    "FINAL_ATTACK_HELPER": 50,
    "CLOSE_COMBAT": 35,
    "NOBLE_DEMAND": 66,
    "HEAVENS_HAMMER": 103,
    "DIVINE_MARK_MAIN": 107,
    "DIVINE_MARK_DETONATION": 107,
    "DIVINE_JUDGMENT": 125,
    "MAGIC_CRASH": 117,
    "RUSH": 63,
    "MAPLE_HERO_HELPER": 100,
    "VESSEL_OF_LIGHT": 45,
    "GREATER_VESSEL_OF_LIGHT": 110,
    "DIVINE_SHIELD": 75,
    "GUARDIAN": 105,
    "DIVINE_BLESSING": 115,
    "HP_RECOVERY_ATK": 74,
    "COMBAT_ORDERS": 69,
    "PARASHOCK_GUARD": 72,
    "WEAPON_ACCELERATION": 33,
    "PHYSICAL_TRAINING": 38,
    "WEAPON_MASTERY": 43,
    "PALADIN_EXPERT_SKILL": 120,
    "PALADIN_EXPERT_MAXDMG": 120,
}

# Maple Hero (Lv.100): each skill's share relative to the 20-base reference (Final Attack's own 7.5x share is folded into Blast, see below)
MAPLE_HERO_RATIOS = {
    "NOBLE_DEMAND": 20 / 20,
    "RUSH": 30 / 20,
    "CLOSE_COMBAT": 80 / 20,
}
MAPLE_HERO = dict(base=200, fidx=23, step=4)

# ---- Blast (basic attack) ----
BLAST_BASE = 290                                                          # x10 %, factor index 21, 4th job (the time-averaged factor)
BLAST_HITS = (5, 136, 6)                                                  # 5 hits, 6 from level 136
BLAST_MASTERY = {102: 10, 106: 11, 116: 12, 120: 13, 128: 14, 132: 15}    # Damage mastery chain (raw tiers)
BLAST_BOSS_MASTERY = {111: 10, 124: 10}                                   # Boss Damage mastery chain

# ---- helper row folded into Blast: Final Attack (no Advanced Final Attack in this kit) ----
FINAL_ATTACK = dict(base=350, fidx=21, step=2, gated={54: 50})
FINAL_ATTACK_BLAST_SHARE = 25                    # Final Attack's share folded into Blast's coefficient (%)
FINAL_ATTACK_MAPLE_SHARE = 7.5                   # ... multiplied by Maple Hero's own +150% FD share (7.5 x Maple Hero's value)

# ---- buffs / passives (base = tenths of %, fidx, step; cooldown / duration in seconds) ----
VESSEL_OF_LIGHT = dict(base=150, fidx=22, step=2, gated={49: 5}, proc_chance=0.15, duration=10)       # Attack% proc buff
GREATER_VESSEL = dict(base=180, fidx=22, step=4, gated={118: 10})                                      # Final Damage (shares Vessel's uptime)
HP_RECOVERY = dict(base=120, fidx=21, step=3, gated={78: 10}, duration=20, cooldown=25)                # Attack%
DIVINE_SHIELD = dict(base=150, fidx=22, step=3, duration=10, cooldown=15)                              # Final Damage, fixed interval (no action)
GUARDIAN = dict(base=100, fidx=21, step=4, duration=20, cooldown=24)                                   # Final Damage
DIVINE_BLESSING = dict(base=120, fidx=21, step=4, gated={126: 12}, duration=22, cooldown=30)           # Final Damage
COMBAT_ORDERS = dict(base=180, fidx=21, step=3, duration=25, cooldown=35, attack_pct=25, attack_min_level=82)   # +skill levels, +25%p Attack from Lv82
NIMBLE_FEET = dict(base=150, fidx=0, step=1, duration=15, cooldown=60)                                 # Attack Speed % (non-scaling)
COMBAT_ORDERS_JOB4_BONUS = (104, 18)                                                                  # the 4th-job skills get +18 levels from Lv104

# Debuffs ("weaken"): global monster damage-taken bonus (pct, duration, cooldown, unlock level or None = always)
CLOSE_COMBAT_WEAKEN = dict(level=44, pct=10, duration=10, cooldown=18)
NOBLE_DEMAND_WEAKEN = dict(pct=12, duration=10, cooldown=30, haste=(94, 0.7))      # (no unlock gate in the verify script)
DIVINE_MARK_WEAKEN = dict(level=138, pct=20, duration=10, cooldown=16)

# ---- damage rows (the verify script's DAMAGE_SKILLS dict order; summation order matters bit-for-bit) ----
# cooldown (s) [+ haste (level, multiplier)], hits, base damage (tenths of %), factor index, skill mastery chain, boss / normal mastery %,
# normal-monster targets [+ extra_targets (level, n)].  Divine Judgment's cooldown is a rate surrogate (10 basic attacks): 10 / actions-per-second,
# exempt from Cooldown Decrease.  Heaven's Hammer's Boss-Damage mastery is 100 (+100 from Lv134).
DAMAGE_SKILLS = {
    "CLOSE_COMBAT": dict(step=2, cooldown=18, hits=1, base=4600, fidx=12, mastery={39: 50}, mastery_boss=0, mastery_normal=0,
                         costs_action=True, targets=7),
    "NOBLE_DEMAND": dict(step=3, cooldown=30, haste=(94, 0.7), hits=1, base=16000, fidx=12, mastery={73: 50}, mastery_boss=0, mastery_normal=0,
                         costs_action=True, targets=8),
    "HEAVENS_HAMMER": dict(step=4, cooldown=18, hits=5, base=7800, fidx=12, mastery={108: 50}, mastery_boss=(100, 134, 100), mastery_normal=0,
                           costs_action=True, targets=7),
    "DIVINE_MARK_MAIN": dict(step=4, cooldown=16, hits=6, base=4600, fidx=12, mastery={122: 50}, mastery_boss=0, mastery_normal=0,
                             costs_action=True, targets=8),
    "DIVINE_MARK_DETONATION": dict(step=4, cooldown=16, hits=4, base=4000, fidx=12, mastery={122: 50}, mastery_boss=0, mastery_normal=0,
                                   costs_action=False, targets=8),
    "DIVINE_JUDGMENT": dict(step=4, cooldown=None, hits=4, base=8500, fidx=12, mastery={130: 50}, mastery_boss=0, mastery_normal=0,
                            costs_action=False, targets=4),
    "MAGIC_CRASH": dict(step=4, cooldown=28, hits=1, base=48000, fidx=12, mastery={}, mastery_boss=0, mastery_normal=0,
                        costs_action=True, targets=5, extra_targets=(100, 4)),
    "RUSH": dict(step=3, cooldown=22, haste=(90, 0.7), hits=1, base=6000, fidx=12, mastery={68: 80}, mastery_boss=0, mastery_normal=0,
                 costs_action=True, targets=12),
}
JUDGMENT_RATE_ATTACKS = 10         # Divine Judgment fires every 10 basic attacks: cooldown = 10 / actions-per-second
CDR_EXEMPT = ["DIVINE_JUDGMENT"]   # rate-surrogate cooldown: Skill Cooldown Decrease does not apply

# Action-costing rows in the verify script's COST_ACTION_ORDER (damage rows read their cooldown from DAMAGE_SKILLS, the buffs from BUFF_COOLDOWNS)
COST_ACTION_ORDER = ["CLOSE_COMBAT", "NOBLE_DEMAND", "HEAVENS_HAMMER", "DIVINE_MARK_MAIN", "MAGIC_CRASH", "RUSH", "GUARDIAN", "DIVINE_BLESSING",
                     "HP_RECOVERY_ATK", "COMBAT_ORDERS", "NIMBLE_FEET"]
BUFF_COOLDOWNS = {"GUARDIAN": 24, "DIVINE_BLESSING": 30, "HP_RECOVERY_ATK": 25, "COMBAT_ORDERS": 35, "NIMBLE_FEET": 60}
# Rows exempt from the buff-casting startup delay's reduction of their own cast count (they ARE the buffs)
BUFF_ROW_KEYS = ["GUARDIAN", "DIVINE_BLESSING", "HP_RECOVERY_ATK", "COMBAT_ORDERS", "NIMBLE_FEET"]
STARTUP_BUFFS = ["GUARDIAN", "DIVINE_BLESSING", "HP_RECOVERY_ATK", "COMBAT_ORDERS", "NIMBLE_FEET"]   # actively cast buffs -> startup delay / engine-off t0

# ---- player's own stun (game table): Rush stuns for 2.5 s, cast on cooldown from the start (cooldown = Rush's, resolved by the model) ----
PLAYER_STUN = [dict(id="RUSH", key="RUSH", typ="cast", dur=2.5, p=1.0)]

# ---- Status Effect Damage / KO timeline engine spec (src/status_timeline.py) ----
# engine id -> (row key, kind, base cooldown, base duration): HP Recovery / Combat Orders = Attack% buffs, Guardian / Divine Blessing = Final Damage 'ramp'
STATUS_BUFFS = [("HPR", "HP_RECOVERY_ATK", "atk"), ("CO", "COMBAT_ORDERS", "atk"), ("GU", "GUARDIAN", "ramp"), ("DB", "DIVINE_BLESSING", "ramp")]
BUFF_SPEC = {
    "HPR": ("HP_RECOVERY_ATK", "atk", 25, 20), "CO": ("COMBAT_ORDERS", "atk", 35, 25),
    "GU": ("GUARDIAN", "ramp", 24, 20), "DB": ("DIVINE_BLESSING", "ramp", 30, 22),
}
# rows whose engine buff only exists from a level on (Combat Orders' Attack% half is the Lv82 'Damage Boost' mastery)
STATUS_ROW_MIN_LEVEL = {"COMBAT_ORDERS": 82}
COMBAT_ORDERS_ATTACK_PCT = 25
# (group id, row key whose cooldown gives the cast spacing, [(row key, type, window row key or None, unlock-gate row key or None, weight row key)])
STATUS_GROUPS = [
    ("CLOSE", "CLOSE_COMBAT", [("CLOSE_COMBAT", "burst", None, None, "CLOSE_COMBAT")]),
    ("NOBLE", "NOBLE_DEMAND", [("NOBLE_DEMAND", "burst", None, None, "NOBLE_DEMAND")]),
    ("HAMMER", "HEAVENS_HAMMER", [("HEAVENS_HAMMER", "burst", None, None, "HEAVENS_HAMMER")]),
    ("MARK", "DIVINE_MARK_MAIN", [
        ("DIVINE_MARK_MAIN", "burst", None, None, "DIVINE_MARK_MAIN"),
        ("DIVINE_MARK_DETONATION", "burst", None, None, "DIVINE_MARK_DETONATION")]),
    ("CRASH", "MAGIC_CRASH", [("MAGIC_CRASH", "burst", None, None, "MAGIC_CRASH")]),
    ("RUSH", "RUSH", [("RUSH", "burst", None, None, "RUSH")]),
]
# Spread uniformly over the fight: Blast (the basic attack) and Divine Judgment (a proc triggered by every 10 basic attacks)
STATUS_UNIFORM_ROWS = ["BLAST", "DIVINE_JUDGMENT"]
STATUS_CAST_PREFIX = {key: f"buff.{bid}" for bid, key, _k in STATUS_BUFFS}
for _gid, _cast, _ents in STATUS_GROUPS:
    for _e in _ents:
        STATUS_CAST_PREFIX.setdefault(_e[0], f"grp.{_gid}")
    STATUS_CAST_PREFIX[_cast] = f"grp.{_gid}"
# rows whose hits/s come from the engine's effective cast count (none for Paladin: no DoT / eruption rows)
STATUS_FS_KEYS = [e[0] for _g, _c, ents in STATUS_GROUPS for e in ents if e[1] in ("dot", "end")]
STATUS_PHI_ROWS = sorted({e[0] for _g, _c, ents in STATUS_GROUPS for e in ents})
