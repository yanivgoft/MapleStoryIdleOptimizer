"""Dark Knight static game data, as plain Python data (transcribed from ``src/build_dark_knight_workbook.py`` / ``src/verify_dark_knight_workbook.py``;
the builder stays the workbook's source, this module is the engine's copy - keep both in sync when a skill changes;
``tests/golden/check_dark_knight_fake.py`` cross-checks the tables that the builder exports).  Level-dependent values (cooldown haste, target counts,
mastery bonuses that switch on at a level) are described here as ``(threshold, value)`` tuples / ``{level: tier value}`` chains and resolved by the
model in ``engine/classes/dark_knight.py``.

Base-damage numbers are in tenths of a percent (``base``); ``fidx`` is the FactorTable column; ``step`` the job tier (1-4) whose skill level scales the
skill.  ``gated`` chains are raw tier values summed over every reached level (CLAUDE.md bug 2).
"""

SKILL_NAMES = {
    "DARK_IMPALE": "Dark Impale",
    "MAGIC_CRASH": "Magic Crash",
    "GUNGNIRS_DESCENT": "Gungnir's Descent",
    "EVIL_EYE_SHOCK": "Evil Eye Shock",
    "EVIL_EYE_OF_DOMINANT": "Evil Eye of Dominant",
    "REVENGE_OF_THE_EVIL_EYE": "Revenge of the Evil Eye",
    "RUSH": "Rush",
}

# Result rows in the workbook's Skills-sheet order (damage rows only)
DPS_ROW_ORDER = ["DARK_IMPALE", "MAGIC_CRASH", "GUNGNIRS_DESCENT", "EVIL_EYE_SHOCK", "EVIL_EYE_OF_DOMINANT", "REVENGE_OF_THE_EVIL_EYE", "RUSH"]

# Unlock level of every row that has a threshold (rows not listed - Nimble Feet - are unlocked from the start)
UNLOCK_LEVEL = {
    "DARK_IMPALE": 100,
    "FINAL_ATTACK_HELPER": 50,
    "ADVANCED_FINAL_ATTACK_HELPER": 105,
    "MAGIC_CRASH": 117,
    "GUNGNIRS_DESCENT": 103,
    "EVIL_EYE_SHOCK": 40,
    "EVIL_EYE_SHOCK_ENH": 75,
    "EVIL_EYE_OF_DOMINANT": 60,
    "REVENGE_OF_THE_EVIL_EYE": 110,
    "MAPLE_HERO_HELPER": 100,
    "RUSH": 63,
    "HEX_OF_THE_EVIL_EYE": 69,
    "DARK_RESONANCE": 115,
    "CROSS_OVER_CHAINS": 66,
    "HYPER_BODY": 45,
    "EVIL_EYE": 35,
    "LORD_OF_DARKNESS_CRITRATE": 72,
    "LORD_OF_DARKNESS_CRITDMG": 72,
    "WEAPON_ACCELERATION": 33,
    "WEAPON_MASTERY": 43,
    "BARRICADE_SKILL_DMG": 120,
    "BARRICADE_MAXDMG": 120,
    "POWER_STANCE_FD": 125,
    "FINAL_PACT": 107,
}

# Maple Hero (Lv.100): each skill's share relative to the 40-base reference (Evil Eye of Dominant 1x, Rush / Evil Eye Shock 0.75x)
MAPLE_HERO_RATIOS = {
    "EVIL_EYE_OF_DOMINANT": 40 / 40,
    "RUSH": 30 / 40,
    "EVIL_EYE_SHOCK": 30 / 40,
}
MAPLE_HERO = dict(base=400, fidx=23, step=4)

# ---- Iron Wall: converts a level-scaling share of the TOTAL Defense (flat x (1 + Defense%)) into STR (from Lv38) ----
IRON_WALL = dict(rate_factor_idx=22, rate_base=10, min_level=38)       # rate % = 10 x FactorTable[level][22] / 1000

# ---- Dark Impale (basic attack) ----
DARK_IMPALE_BASE = 290                                                    # x10 %, factor index 21, 4th job
DARK_IMPALE_HITS = (5, 136, 6)                                            # 5 hits, 6 from level 136
DARK_IMPALE_MASTERY = {102: 10, 106: 11, 116: 12, 120: 13, 128: 14, 132: 15}    # Damage mastery chain (raw tiers)
DARK_IMPALE_BOSS_MASTERY = {111: 10, 124: 10}                             # Boss Damage mastery chain

# ---- helper rows folded into Dark Impale / Evil Eye Shock ----
FINAL_ATTACK = dict(base=350, fidx=21, step=2, gated={54: 50})
# Final Pact (patch 2026-11-26): on appearing / at the battle start the character enters Death Avoidance and gains Final Damage +1% every second, up to 12 stacks
# (before: a flat +10%, which the typed Final Damage contained).  Per-stack value = 10 tenths-of-% x factor 22 (the old +10% curve, so 1% at level 1).
FINAL_PACT = dict(base=10, fidx=22, step=4, max_stacks=12, interval=1.0, boost=(118, 2.0))      # Lv118 'Final Pact - Recovery': Final Damage boost +100 % = x2

ADVANCED_FINAL_ATTACK = dict(base=5000, fidx=21, step=4, gated={113: 100})        # mastery is ADDITIVE (percentage points) on this helper
FINAL_ATTACK_SHARE = 25                    # Final Attack's share folded into Dark Impale's coefficient (%)
EVIL_EYE_SHOCK_ENH = dict(base=1000, fidx=22, step=3)

# ---- Attack% buffs (timed by the engine in Status/KO content): base = tenths of %, fidx, step, mastery chain, base duration, base cooldown ----
# (engine id, row key) in the verify script's ATTACK_BUFFS order (the order of the Attack% bucket sum)
ATTACK_BUFF_ORDER = [("HEX", "HEX_OF_THE_EVIL_EYE"), ("DR", "DARK_RESONANCE"), ("COC", "CROSS_OVER_CHAINS"), ("HB", "HYPER_BODY")]
EVIL_EYE_COOLDOWN = (30, 104, 0.7)         # base, haste level, multiplier: also Hex's and Evil Eye of Dominant's cooldown
HEX = dict(base=150, fidx=22, step=3, gated={98: 50}, duration=20, boss_clause_level=82)
DARK_RESONANCE = dict(base=300, fidx=21, step=4, duration=20, duration_level=130, duration_mult=1.4, cooldown=32)
CROSS_OVER_CHAINS = dict(base=150, fidx=21, step=3, gated={73: 100}, duration=15, cooldown=30)
HYPER_BODY = dict(base=120, fidx=21, step=2, gated={49: 50}, duration=15, cooldown=30)
BOSS_CLAUSE_PCT = 20                       # Dark Resonance / Hex (Lv82): +20% boss damage while the buff is up (boss branch only)

# ---- Nimble Feet (Attack Speed buff, non-scaling) ----
NIMBLE_FEET = dict(base=150, fidx=0, step=1, duration=15, cooldown=60)

# ---- Lord of Darkness (proc x duty-cycle; Crit Rate / Crit Damage halves) ----
LORD_OF_DARKNESS_CRITRATE = dict(base=100, fidx=22, step=3)
LORD_OF_DARKNESS_CRITDMG = dict(base=400, fidx=22, step=3)
LORD_OF_DARKNESS = dict(proc_chance=30, duration=8, cooldown=3)

# ---- Evil Eye's damage-taken debuff and Magic Crash's Lv126 Weaken: the global monster damage-taken bonus ----
EVIL_EYE = dict(base=150, fidx=21, step=2, gated={39: 10}, duration=20)
MAGIC_CRASH_WEAKEN = dict(level=126, pct=10, duration=15, cooldown=28)

# ---- damage rows (the verify script's DAMAGE_SKILLS dict order; summation order matters bit-for-bit) ----
# cooldown (s) [+ haste (level, multiplier)], hits, base damage (tenths of %), factor index, skill mastery chain, boss / normal mastery %,
# normal-monster targets [+ extra_targets (level, n)].  ``hits_gate`` / ``base_gate``: (level, value from that level on) overrides (Gungnir's Descent's
# Lv134 "Strike" mastery halves the base and triples the hits).  ``fold``: coefficient points ADDED after the multiplicative mastery.
DAMAGE_SKILLS = {
    "MAGIC_CRASH": dict(step=4, cooldown=28, hits=1, base=65000, fidx=12, mastery={}, costs_action=True, targets=5, extra_targets=(100, 4)),
    "GUNGNIRS_DESCENT": dict(step=4, cooldown=13, hits=2, hits_gate=(134, 6), base=18000, base_gate=(134, 9000), fidx=12, mastery={108: 50},
                             costs_action=True, targets=1),
    "EVIL_EYE_SHOCK": dict(step=2, cooldown=18, hits=6, base=700, fidx=12, mastery={44: 50}, costs_action=True, targets=6, extra_targets=(75, 3),
                           fold_level=75),
    "EVIL_EYE_OF_DOMINANT": dict(step=3, cooldown=30, haste=(104, 0.7), hits=1, icd=1, window=20, base=600, fidx=21, mastery={78: 50},
                                 costs_action=False, targets=6, extra_targets=(94, 3)),
    "REVENGE_OF_THE_EVIL_EYE": dict(step=4, cooldown=5, hits=2, base=8500, fidx=12, mastery={122: 50}, costs_action=False, targets=1,
                                    revenge_fold=dict(level=138, base=2200, fidx=12)),
    "RUSH": dict(step=3, cooldown=22, haste=(90, 0.7), hits=1, base=6000, fidx=12, mastery={68: 80}, costs_action=True, targets=12),
}

# Action-costing / cast rows in the verify script's COST_ACTION_ROWS order: (key, cooldown spec, costs action).  Damage rows read their cooldown from
# DAMAGE_SKILLS; the others from BUFF_COOLDOWNS (``"EVIL_EYE_CD"`` = the haste-resolved Evil Eye cooldown).  Only rows with costs_action count.
COST_ACTION_ORDER = [
    ("MAGIC_CRASH", True), ("GUNGNIRS_DESCENT", True), ("EVIL_EYE_SHOCK", True), ("RUSH", True),
    ("HEX_OF_THE_EVIL_EYE", False), ("DARK_RESONANCE", True), ("CROSS_OVER_CHAINS", True), ("HYPER_BODY", True),
    ("EVIL_EYE", True), ("LORD_OF_DARKNESS_CRITRATE", False), ("LORD_OF_DARKNESS_CRITDMG", False), ("NIMBLE_FEET", True),
]
BUFF_COOLDOWNS = {"HEX_OF_THE_EVIL_EYE": "EVIL_EYE_CD", "DARK_RESONANCE": 32, "CROSS_OVER_CHAINS": 30, "HYPER_BODY": 30, "EVIL_EYE": "EVIL_EYE_CD",
                  "LORD_OF_DARKNESS_CRITRATE": 3, "LORD_OF_DARKNESS_CRITDMG": 3, "NIMBLE_FEET": 60}
# Rows whose cast count is the plain exact-cast count (not reduced by the buff-casting startup delay): the buff rows
BUFF_ROW_KEYS = ["DARK_RESONANCE", "CROSS_OVER_CHAINS", "HYPER_BODY", "EVIL_EYE", "NIMBLE_FEET", "HEX_OF_THE_EVIL_EYE",
                 "LORD_OF_DARKNESS_CRITRATE", "LORD_OF_DARKNESS_CRITDMG"]
STARTUP_BUFFS = ["DARK_RESONANCE", "CROSS_OVER_CHAINS", "HYPER_BODY", "EVIL_EYE", "NIMBLE_FEET"]   # actively cast buffs -> startup delay / engine-off t0

# ---- the player's own stuns (game table): Rush 2.5 s (cooldown = Rush's, resolved by the model) and Evil Eye Shock 1.5 s (cooldown 18 s; it needs the
# Evil Eye summon - assumed up whenever the skill is unlocked); both cast on cooldown from the start ----
PLAYER_STUN = [dict(id="RUSH", key="RUSH", typ="cast", dur=2.5, p=1.0),
               dict(id="SHOCK", key="EVIL_EYE_SHOCK", typ="cast", dur=1.5, p=1.0, cd=18)]

# ---- Status Effect Damage / KO timeline engine spec (src/status_timeline.py) ----
STATUS_BUFFS = [("HEX", "HEX_OF_THE_EVIL_EYE", "atk"), ("DR", "DARK_RESONANCE", "atk"), ("COC", "CROSS_OVER_CHAINS", "atk"), ("HB", "HYPER_BODY", "atk")]
# (group id, row key whose cooldown gives the cast spacing, [(row key, type, window row key or None, unlock-gate row key or None, weight row key)])
STATUS_GROUPS = [
    ("CRASH", "MAGIC_CRASH", [("MAGIC_CRASH", "burst", None, None, "MAGIC_CRASH")]),
    ("GUNGNIR", "GUNGNIRS_DESCENT", [("GUNGNIRS_DESCENT", "burst", None, None, "GUNGNIRS_DESCENT")]),
    ("SHOCK", "EVIL_EYE_SHOCK", [("EVIL_EYE_SHOCK", "burst", None, None, "EVIL_EYE_SHOCK")]),
    # Evil Eye of Dominant: the Evil Eye's 20 s of 1 s ticks, recast with the summon (no action slot of its own)
    ("DOMINANT", "EVIL_EYE_OF_DOMINANT", [("EVIL_EYE_OF_DOMINANT", "dot", "EVIL_EYE_OF_DOMINANT", None, "EVIL_EYE_OF_DOMINANT")]),
    ("RUSH", "RUSH", [("RUSH", "burst", None, None, "RUSH")]),
]
# groups whose cast takes an action slot (the cast replaces a basic attack): the cast row's costs_action (Evil Eye of Dominant is tied to the summon)
STATUS_GROUP_TAKES_SLOT = {"CRASH": True, "GUNGNIR": True, "SHOCK": True, "DOMINANT": False, "RUSH": True}
# Spread uniformly over the fight: Dark Impale (the basic attack) and Revenge of the Evil Eye (a 5 s-cooldown self-triggered proc, never a player-timed cast)
STATUS_UNIFORM_ROWS = ["DARK_IMPALE", "REVENGE_OF_THE_EVIL_EYE"]
STATUS_CAST_PREFIX = {key: f"buff.{bid}" for bid, key, _k in STATUS_BUFFS}
for _gid, _cast, _ents in STATUS_GROUPS:
    for _e in _ents:
        STATUS_CAST_PREFIX.setdefault(_e[0], f"grp.{_gid}")
    STATUS_CAST_PREFIX[_cast] = f"grp.{_gid}"
# rows whose hits/s come from the engine's effective cast count (last DoT window truncated by the fight end)
STATUS_FS_KEYS = [e[0] for _g, _c, ents in STATUS_GROUPS for e in ents if e[1] in ("dot", "end")]
STATUS_PHI_ROWS = sorted({e[0] for _g, _c, ents in STATUS_GROUPS for e in ents})
