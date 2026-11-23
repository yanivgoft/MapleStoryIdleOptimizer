"""Bowmaster static game data, as plain Python data (transcribed from ``src/build_bowmaster_workbook.py`` / ``src/verify_bowmaster_workbook.py``;
the builder stays the workbook's source, this module is the engine's copy - keep both in sync when a skill changes).  Level-dependent values
(hit counts, cooldown haste, target counts, mastery bonuses that switch on at a level) are described here as ``(threshold, value)`` tuples /
``{level: tier value}`` chains and resolved by the model in ``engine/classes/bowmaster.py``.

Base-damage numbers are in tenths of a percent (``base``); ``fidx`` is the FactorTable column; ``step`` the job tier (1-4) whose skill level
scales the skill.  ``gated`` chains are raw tier values summed over every reached level (CLAUDE.md bug 2).
"""

SKILL_NAMES = {
    "ARROW_STREAM": "Arrow Stream",
    "COVERING_FIRE": "Covering Fire",
    "QUIVER_CARTRIDGE": "Quiver Cartridge",
    "ENCHANTED_QUIVER_DRAIN": "Enchanted Quiver (Drain)",
    "PHOENIX": "Phoenix",
    "ARROW_PLATTER": "Arrow Platter",
    "FLASH_MIRAGE": "Flash Mirage",
    "HURRICANE": "Hurricane",
    "FINAL_ATTACK_BOW": "Final Attack: Bow",
}

# Result rows = the verify script's own order: Arrow Stream first, then DAMAGE_SKILLS (also the order of its _BRANCH_PAIRS insertion)
DPS_ROW_ORDER = ["ARROW_STREAM", "COVERING_FIRE", "QUIVER_CARTRIDGE", "ENCHANTED_QUIVER_DRAIN", "PHOENIX", "ARROW_PLATTER", "FLASH_MIRAGE",
                 "HURRICANE", "FINAL_ATTACK_BOW"]

# Unlock level of every row that has a threshold (rows not listed - Nimble Feet - are unlocked from the start)
UNLOCK_LEVEL = {
    "ADVANCED_FINAL_ATTACK_HELPER": 105,
    "ARCHER_MASTERY": 10,
    "ARMOR_BREAK_DEFPEN": 125,
    "ARMOR_BREAK_FD": 125,
    "ARROW_PLATTER": 63,
    "ARROW_STREAM": 100,
    "BOW_ACCELERATION": 33,
    "BOW_EXPERT_MAXDMG": 120,
    "BOW_EXPERT_SKILL": 120,
    "BOW_MASTERY": 43,
    "CONCENTRATION": 66,
    "COVERING_FIRE": 35,
    "CRITICAL_SHOT": 15,
    "ENCHANTED_QUIVER_DRAIN": 130,
    "ENCHANTED_QUIVER_HELPER": 107,
    "EXTREME_ARCHERY_BOW": 75,
    "FINAL_ATTACK_BOW": 50,
    "FLASH_MIRAGE": 60,
    "FLASH_MIRAGE_II_HELPER": 110,
    "HURRICANE": 103,
    "ILLUSION_STEP": 117,
    "MAPLE_HERO_HELPER": 100,
    "MARKSMANSHIP_BASE": 74,
    "MARKSMANSHIP_COND": 74,
    "MORTAL_BLOW": 72,
    "PHOENIX": 69,
    "PHYSICAL_TRAINING": 38,
    "QUIVER_CARTRIDGE": 40,
    "SHARP_EYES": 115,
    "SOUL_ARROW_BOW_ATK": 45,
}

# Maple Hero (Lv.100): each skill's share relative to the 20-base reference
MAPLE_HERO_RATIOS = {"ARROW_PLATTER": 1.0, "COVERING_FIRE": 4.0, "PHOENIX": 1.2}
MAPLE_HERO = dict(base=250, fidx=23, step=4)

# ---- Arrow Stream (basic attack) ----
ARROW_STREAM_BASE = 290                     # tenths of %, factor index 21, 4th job
ARROW_STREAM_HITS = (5, 136, 6)             # 5 hits, 6 from level 136
ARROW_STREAM_MASTERY = {102: 10, 106: 11, 116: 12, 120: 13, 128: 14, 132: 15}     # Damage mastery chain (raw tiers)
ARROW_STREAM_BOSS_MASTERY = {111: 10, 124: 10}                                      # Boss Damage mastery chain

# ---- helper rows (own coefficient only, folded into another row's extra Final Damage term) ----
FINAL_ATTACK_BOW = dict(base=350, fidx=21, step=2, gated={54: 50})                  # helper coefficient (not a DPS row of its own)
ADVANCED_FINAL_ATTACK = dict(base=5000, fidx=21, step=4, gated={113: 50})
ENCHANTED_QUIVER = dict(base=3000, fidx=21, step=4)
FLASH_MIRAGE_II = dict(base=4000, fidx=21, step=4)

# ---- Attack% bucket: Marksmanship (base + conditional) + Illusion Step ----
MARKSMANSHIP = dict(base=100, fidx=22, step=3)
ILLUSION_STEP = dict(base=140, fidx=22, step=4, boost=(118, 0.375), duration=(15, 118, 24), cooldown=24)   # 15 s, 24 s from Lv118; +37.5% from Lv118

# ---- Sharp Eyes / Concentration / Mortal Blow / Nimble Feet ----
SHARP_EYES = dict(base=400, fidx=21, step=4, duration=(18, 126, 27), cooldown=35)    # Crit Damage; 18 s, 27 s from Lv126
CONCENTRATION = dict(base=30, fidx=22, step=3, stacks=7)                             # 7 stacks of Crit Damage at steady state
MORTAL_BLOW = dict(base=120, fidx=22, step=3)                                        # Final Damage, always on
NIMBLE_FEET = dict(base=150, fidx=0, step=1, duration=15, cooldown=60)               # Attack Speed % (non-scaling)

# Quiver Cartridge's attack-speed-scaled tick: cooldown = 1 - 0.4 x min(1, (APS - 1) / 1.5)
QUIVER_CD = dict(base=1, scale=0.4, cap=1.0, aps_span=1.5)
# Flash Mirage's activation chance: 20% + 30% x (APS - 1) x 100 / 150
FM_CHANCE = dict(base=20, per=30, span=150)

# Rows exempt from Skill Cooldown Decrease (trigger-rate / internal-interval surrogates; mirror of the build script's CDR_EXEMPT_ROW_KEYS)
CDR_EXEMPT = ["QUIVER_CARTRIDGE", "ENCHANTED_QUIVER_DRAIN", "FLASH_MIRAGE"]

# ---- damage rows (the verify script's DAMAGE_SKILLS dict order; summation order matters bit-for-bit) ----
# cooldown (s) [+ haste (level, multiplier)] (QUIVER rows: ``"quiver"`` = the attack-speed-scaled tick; FINAL ATTACK: None = chance per attack),
# hits [+ extra_hits (level, n)], ICD [+ icd_haste], base damage (tenths of %), factor index, skill mastery chain (``mastery``), boss / normal
# mastery % (``mastery_normal`` may be ``(level, value)``), normal-monster targets [+ extra_targets: list of (level, n)], proc chance %,
# extra Final Damage helper (name of the helper whose coefficient feeds it, with its unlock gate).
DAMAGE_SKILLS = {
    "COVERING_FIRE": dict(step=1, cooldown=19, hits=3, base=2500, fidx=12, mastery={39: 50}, mastery_boss=0, mastery_normal=0,
                          costs_action=True, targets=1, extra_targets=[]),
    "QUIVER_CARTRIDGE": dict(step=3, cooldown="quiver", hits=1, base=500, fidx=21, mastery={44: 50}, mastery_boss=0, mastery_normal=0,
                             costs_action=False, targets=3, extra_targets=[(107, 3)], extra_fd="ENCHANTED_QUIVER_HELPER"),
    "ENCHANTED_QUIVER_DRAIN": dict(step=4, cooldown="quiver", hits=1, base=10500, fidx=21, mastery={}, mastery_boss=0, mastery_normal=0,
                                   costs_action=False, targets=3, extra_targets=[(107, 3)], proc_chance=30),
    "PHOENIX": dict(step=3, cooldown=60, haste=(104, 0.6), hits=1, icd=3, icd_haste=(82, 0.7), window=30, base=6000, fidx=12, mastery={},
                    mastery_boss=0, mastery_normal=(94, 100), costs_action=True, targets=5, extra_targets=[(78, 3)]),
    "ARROW_PLATTER": dict(step=3, cooldown=40, hits=1, icd=0.3, window=60, base=500, fidx=12, mastery={73: 50}, mastery_boss=0,
                          mastery_normal=200, costs_action=True, targets=3, extra_targets=[(98, 1)]),
    "FLASH_MIRAGE": dict(step=3, cooldown=5, cooldown_alt=(122, 3), hits=1, base=5500, fidx=21, mastery={68: 50}, mastery_boss=0,
                         mastery_normal=0, costs_action=False, targets=7, extra_targets=[(110, 4), (138, 1)], proc_chance=100,
                         extra_fd="FLASH_MIRAGE_II_HELPER"),
    "HURRICANE": dict(step=4, cooldown=40, hits=20, extra_hits=(134, 15), base=8000, fidx=12, mastery={108: 50}, mastery_boss=0,
                      mastery_normal=0, costs_action=True, targets=11, extra_targets=[]),
    "FINAL_ATTACK_BOW": dict(step=2, cooldown=None, hits=1, base=350, fidx=21, mastery={54: 50}, mastery_boss=0, mastery_normal=0,
                             costs_action=False, targets=1, extra_targets=[], proc_chance=25, extra_fd="ADVANCED_FINAL_ATTACK_HELPER"),
}

# Action-costing rows in the verify script's COST_ACTION_ROWS order: (row key, cooldown source).  A key in DAMAGE_SKILLS reads its resolved
# cooldown; the buffs have their own.  (Covering Fire / Arrow Platter / Hurricane / Sharp Eyes / Nimble Feet read the literal the script uses.)
COST_ACTION_ORDER = ["COVERING_FIRE", "PHOENIX", "ARROW_PLATTER", "HURRICANE", "SHARP_EYES", "NIMBLE_FEET"]
BUFF_COOLDOWNS = {"SHARP_EYES": 35, "NIMBLE_FEET": 60}
BUFF_KEYS_STARTUP = ["SHARP_EYES", "NIMBLE_FEET"]            # actively cast buffs: startup delay / their own cast count
STARTUP_BUFFS = ["SHARP_EYES", "NIMBLE_FEET"]                # (Illusion Step costs no action, so it never counts)
# Rows whose casts trigger the chance procs (Final Attack: Bow, Flash Mirage); Hurricane's arrows are each their own attack
TRIGGER_CAST_ROWS = ["COVERING_FIRE", "PHOENIX", "ARROW_PLATTER", "HURRICANE"]

# ---- player's own stun (game table): Covering Fire stuns for 1 s (cooldown 19 s), from the Lv49 mastery on, cast on cooldown from the start ----
PLAYER_STUN = [dict(id="COVER", key="COVERING_FIRE", typ="cast", dur=1.0, p=1.0, cd=19, min_level=49)]

# ---- Status Effect Damage / KO timeline engine spec (src/status_timeline.py) ----
# Illusion Step is the only engine-timed buff (Sharp Eyes / Nimble Feet / Concentration / Mortal Blow keep their averaged formulas).
STATUS_BUFFS = [("IS", "ILLUSION_STEP", "atk")]
# (group id, row key whose cooldown gives the cast spacing, [(row key, type, window row key or None, unlock-gate row key or None, weight row key)])
STATUS_GROUPS = [
    ("COVER", "COVERING_FIRE", [("COVERING_FIRE", "burst", None, None, "COVERING_FIRE")]),
    ("PHOENIX", "PHOENIX", [("PHOENIX", "dot", "PHOENIX", None, "PHOENIX")]),
    ("PLATTER", "ARROW_PLATTER", [("ARROW_PLATTER", "dot", "ARROW_PLATTER", None, "ARROW_PLATTER")]),
    ("HURR", "HURRICANE", [("HURRICANE", "burst", None, None, "HURRICANE")]),
]
# rows spread uniformly over the fight (the order is the verify script's summation order of the uniform boss total)
STATUS_UNIFORM_ROWS = ["ARROW_STREAM", "FINAL_ATTACK_BOW", "FLASH_MIRAGE", "QUIVER_CARTRIDGE", "ENCHANTED_QUIVER_DRAIN"]
STATUS_CAST_PREFIX = {key: f"buff.{bid}" for bid, key, _k in STATUS_BUFFS}
for _gid, _cast, _ents in STATUS_GROUPS:
    for _e in _ents:
        STATUS_CAST_PREFIX.setdefault(_e[0], f"grp.{_gid}")
    STATUS_CAST_PREFIX[_cast] = f"grp.{_gid}"
# rows whose hits/s come from the engine's effective cast count (last DoT window truncated by the fight end)
STATUS_FS_KEYS = [e[0] for _g, _c, ents in STATUS_GROUPS for e in ents if e[1] in ("dot", "end")]
STATUS_PHI_ROWS = sorted({e[0] for _g, _c, ents in STATUS_GROUPS for e in ents})
