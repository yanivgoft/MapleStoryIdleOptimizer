"""Hero static game data, as plain Python data (transcribed from ``src/build_hero_workbook.py`` / ``src/verify_hero_workbook.py``; the
builder stays the workbook's source, this module is the engine's copy - keep both in sync when a skill changes).  Level-dependent values
(hit counts, cooldown haste, target counts, mastery bonuses that switch on at a level) are described here as ``(threshold, value)``
tuples / ``{level: tier value}`` chains and resolved by the model in ``engine/classes/hero.py``.

Base-damage numbers are in tenths of a percent (``base``); ``fidx`` is the FactorTable column; ``step`` the job tier (1-4) whose skill level
scales the skill.  ``gated`` chains are raw tier values summed over every reached level (CLAUDE.md bug 2).
"""

SKILL_NAMES = {
    "RAGING_BLOW": "Raging Blow",
    "PUNCTURE": "Puncture",
    "PUNCTURE_WOUND": "Puncture (wound DoT)",
    "ENHANCED_RAGING_BLOW": "Enhanced Raging Blow",
    "MAGIC_CRASH": "Magic Crash",
    "BEAM_BLADE": "Beam Blade",
    "RUSH": "Rush",
    "FLASH_SLASH": "Flash Slash",
}

# Result rows in the workbook's Skills-sheet order (damage rows only)
DPS_ROW_ORDER = ["RAGING_BLOW", "PUNCTURE", "PUNCTURE_WOUND", "ENHANCED_RAGING_BLOW", "MAGIC_CRASH", "BEAM_BLADE", "RUSH", "FLASH_SLASH"]

# Unlock level of every row that has a threshold (rows not listed - Nimble Feet - are unlocked from the start)
UNLOCK_LEVEL = {
    "RAGING_BLOW": 100,
    "FINAL_ATTACK_HELPER": 50,
    "ADVANCED_FINAL_ATTACK_HELPER": 105,
    "PUNCTURE": 103,
    "PUNCTURE_WOUND": 103,
    "ENHANCED_RAGING_BLOW": 107,
    "MAGIC_CRASH": 117,
    "BEAM_BLADE": 69,
    "RUSH": 63,
    "FLASH_SLASH": 35,
    "MAPLE_HERO_HELPER": 100,
    "COMBO_ATTACK": 45,
    "COMBO_SYNERGY": 75,
    "SPIRIT_BLADE": 40,
    "SCARING_SWORD": 66,
    "ENRAGE_FD": 115,
    "ENRAGE_CRITDMG": 115,
    "WEAPON_ACCELERATION": 33,
    "PHYSICAL_TRAINING": 38,
    "WEAPON_MASTERY": 43,
    "COMBAT_MASTERY_SKILL": 120,
    "COMBAT_MASTERY_MAXDMG": 120,
    "POWER_STANCE_FD": 125,
    "CHANCE_ATTACK_CRIT": 72,
}

# Maple Hero (Lv.100): each skill's share relative to the 20-base reference (idle.maplestorywiki.net/w/Maple_Hero_(Hero))
MAPLE_HERO_RATIOS = {
    "BEAM_BLADE": 20 / 20,
    "RUSH": 30 / 20,
    "FLASH_SLASH": 80 / 20,
}
MAPLE_HERO = dict(base=200, fidx=23, step=4)

# ---- Raging Blow (basic attack) ----
RAGING_BLOW_BASE = 290                      # tenths of %, factor index 21, 4th job
RAGING_BLOW_HITS = (5, 136, 6)              # 5 hits, 6 from level 136
RAGING_BLOW_MASTERY = {102: 10, 106: 11, 116: 12, 120: 13, 128: 14, 132: 15}        # Damage mastery chain (raw tiers)
RAGING_BLOW_BOSS_MASTERY = {111: 10, 124: 10}                                        # Boss Damage mastery chain

# ---- helper rows folded into Raging Blow / hits ----
FINAL_ATTACK = dict(base=350, fidx=21, step=2, gated={54: 50})
ADVANCED_FINAL_ATTACK = dict(base=5000, fidx=21, step=4, gated={113: 50})
FINAL_ATTACK_RAGING_BLOW_SHARE = 25                    # Final Attack's share folded into Raging Blow's coefficient (%)
ENHANCED_RB_COMBO_FD = dict(level=138, per_stack=50, free_stacks=5)   # Enhanced Raging Blow: +50% FD per combo stack beyond 5 (level >= 138)

# ---- Combo Attack / Combo Synergy (steady-state max stacks) ----
COMBO_STACKS = ((118, 8), (110, 7), 5)                  # 8 stacks from Lv118, 7 from Lv110, else 5
COMBO_ATTACK = dict(base=40, fidx=22, step=2, gated={49: 1.5})                # Attack% per stack
COMBO_SYNERGY = dict(base=50, fidx=22, step=3, gated={82: 1})                 # Final Damage% per stack
LIVE_DEFPEN = (130, ((118, 8), (110, 7), 5))            # Advanced Combo (Lv130): +1% Defense Penetration per stack, 5 / 7 / 8 stacks

# ---- buffs ----
SPIRIT_BLADE = dict(base=100, fidx=21, step=2, duration=20, cooldown=45, haste=(44, 0.7))   # Attack%
SCARING_SWORD = dict(base=200, fidx=21, step=3, gated={78: 8}, proc_chance=25, uptime_duration=10, uptime_cooldown=30)
ENRAGE_FD = dict(base=120, fidx=22, step=4, duration=7, cooldown=12)
ENRAGE_CRITDMG = dict(base=150, fidx=22, step=4, duration=7, cooldown=12)
NIMBLE_FEET = dict(base=150, fidx=0, step=1, duration=15, cooldown=60)          # Attack Speed % (non-scaling)
FLAT_FINAL_DAMAGE = (98, 5)                                                     # +5% Final Damage from level 98
MAGIC_CRASH_WEAKEN = dict(level=126, pct=10, window=15, cooldown=28)
PUNCTURE_WEAKEN = dict(base=100, fidx=21, step=4, boost=(134, 1.5), window=10, cooldown=17)

# ---- damage rows (the verify script's DAMAGE_SKILLS dict order; summation order matters bit-for-bit) ----
# cooldown (s) [+ haste (level, multiplier)], hits [+ extra_hits (level, n)], base damage (tenths of %), factor index, skill mastery chain,
# boss / normal mastery %, normal-monster targets [+ extra_targets (level, n)].  PUNCTURE_WOUND is the 1 s DoT of Puncture's wound.
DAMAGE_SKILLS = {
    "PUNCTURE": dict(step=4, cooldown=17, hits=3, base=9000, fidx=12, mastery={108: 50}, mastery_boss=0, mastery_normal=0,
                     costs_action=True, targets=5, extra_targets=(100, 5)),
    "PUNCTURE_WOUND": dict(step=4, cooldown=17, hits=1, icd=1, window=10, base=1500, fidx=12, mastery={}, mastery_boss=0, mastery_normal=0,
                           costs_action=False, targets=5, extra_targets=(100, 5)),
    "ENHANCED_RAGING_BLOW": dict(step=4, cooldown=17, hits=6, base=6100, fidx=12, mastery={122: 50}, mastery_boss=100, mastery_normal=0,
                                 costs_action=True, targets=9, extra_targets=(100, 3)),
    "MAGIC_CRASH": dict(step=4, cooldown=28, hits=1, base=48000, fidx=12, mastery={}, mastery_boss=0, mastery_normal=0,
                        costs_action=True, targets=5, extra_targets=(100, 4)),
    "BEAM_BLADE": dict(step=3, cooldown=16, haste=(104, 0.7), hits=4, extra_hits=(94, 1), base=2500, fidx=12, mastery={73: 50},
                       mastery_boss=0, mastery_normal=0, costs_action=True, targets=8),
    "RUSH": dict(step=3, cooldown=22, haste=(90, 0.7), hits=1, base=6000, fidx=12, mastery={68: 80}, mastery_boss=0, mastery_normal=0,
                 costs_action=True, targets=12),
    "FLASH_SLASH": dict(step=2, cooldown=16, hits=1, base=3500, fidx=12, mastery={39: 50}, mastery_boss=0, mastery_normal=0,
                        costs_action=True, targets=7),
}

# Action-costing rows, in the verify script's COST_ACTION_ROWS order: (row key, source).  Damage rows read their cooldown from
# DAMAGE_SKILLS; the three buffs have their own (Spirit Blade: haste 0.7 from Lv44).
COST_ACTION_ORDER = ["PUNCTURE", "ENHANCED_RAGING_BLOW", "MAGIC_CRASH", "BEAM_BLADE", "RUSH", "FLASH_SLASH", "SPIRIT_BLADE", "SCARING_SWORD",
                     "NIMBLE_FEET"]
BUFF_COOLDOWNS = {"SPIRIT_BLADE": (45, (44, 0.7)), "SCARING_SWORD": (30, None), "NIMBLE_FEET": (60, None)}
# Rows exempt from the buff-casting startup delay's reduction of their own cast count (they ARE the buffs)
BUFF_ROW_KEYS = ["SPIRIT_BLADE", "SCARING_SWORD", "NIMBLE_FEET", "ENRAGE_FD", "ENRAGE_CRITDMG"]
STARTUP_BUFFS = ["SPIRIT_BLADE", "SCARING_SWORD", "NIMBLE_FEET"]       # actively cast buffs (cost an action) -> startup delay / engine-off t0

# ---- player's own stun (game table): Rush stuns for 2.5 s, cast on cooldown from the start ----
PLAYER_STUN = [dict(id="RUSH", key="RUSH", typ="cast", dur=2.5, p=1.0)]

# ---- Status Effect Damage / KO timeline engine spec (src/status_timeline.py) ----
# Spirit Blade is the only engine-timed buff (Combo Attack = constant A0; Enrage / Scaring Sword / weakens stay averaged).
STATUS_BUFFS = [("SB", "SPIRIT_BLADE", "atk")]
# (group id, row key whose cooldown gives the cast spacing, [(row key, type, window row key or None, unlock-gate row key or None, weight row key)])
STATUS_GROUPS = [
    ("PUNCTURE", "PUNCTURE", [
        ("PUNCTURE", "burst", None, None, "PUNCTURE"),
        ("PUNCTURE_WOUND", "dot", "PUNCTURE_WOUND", None, "PUNCTURE_WOUND")]),
    ("ERB", "ENHANCED_RAGING_BLOW", [("ENHANCED_RAGING_BLOW", "burst", None, None, "ENHANCED_RAGING_BLOW")]),
    ("CRASH", "MAGIC_CRASH", [("MAGIC_CRASH", "burst", None, None, "MAGIC_CRASH")]),
    ("BEAM", "BEAM_BLADE", [("BEAM_BLADE", "burst", None, None, "BEAM_BLADE")]),
    ("RUSH", "RUSH", [("RUSH", "burst", None, None, "RUSH")]),
    ("SLASH", "FLASH_SLASH", [("FLASH_SLASH", "burst", None, None, "FLASH_SLASH")]),
]
STATUS_UNIFORM_ROWS = ["RAGING_BLOW"]
STATUS_CAST_PREFIX = {key: f"buff.{bid}" for bid, key, _k in STATUS_BUFFS}
for _gid, _cast, _ents in STATUS_GROUPS:
    for _e in _ents:
        STATUS_CAST_PREFIX.setdefault(_e[0], f"grp.{_gid}")
    STATUS_CAST_PREFIX[_cast] = f"grp.{_gid}"
# rows whose hits/s come from the engine's effective cast count (last DoT window truncated by the fight end)
STATUS_FS_KEYS = [e[0] for _g, _c, ents in STATUS_GROUPS for e in ents if e[1] in ("dot", "end")]
STATUS_PHI_ROWS = sorted({e[0] for _g, _c, ents in STATUS_GROUPS for e in ents})
