"""Buccaneer static game data, as plain Python data (transcribed from ``src/build_buccaneer_workbook.py`` / ``src/verify_buccaneer_workbook.py``; the
builder stays the workbook's source, this module is the engine's copy - keep both in sync when a skill changes; ``tests/golden/check_buccaneer_fake.py``
cross-checks the tables that the builder exports).  Level-dependent values (cooldown haste, hit / target counts, mastery bonuses that switch on at a
level) are described here as ``(threshold, value)`` tuples / ``{level: tier value}`` chains and resolved by the model in
``engine/classes/buccaneer.py``.

Base-damage numbers are in tenths of a percent (``base``); ``fidx`` is the FactorTable column; ``step`` the job tier (1-4) whose skill level
scales the skill.  ``gated`` chains are raw tier values summed over every reached level (CLAUDE.md bug 2).
"""

SKILL_NAMES = {
    "HOOK_BOMBER": "Hook Bomber",
    "SEA_SERPENT_BURST": "Sea Serpent Burst",
    "SERPENT_ASSAULT": "Serpent Assault",
    "CORKSCREW_BLOW": "Corkscrew Blow",
    "OCTOPUNCH": "Octopunch",
    "SEA_SERPENTS_RAGE": "Sea Serpent's Rage",
    "RAGING_SERPENT_ASSAULT": "Raging Serpent Assault",
    "NAUTILUS_STRIKE": "Nautilus Strike",
    "NAUTILUS_FINAL_ATTACK": "Nautilus Strike - Final Attack",
}

# Result rows in the workbook's Skills-sheet order (damage rows only)
DPS_ROW_ORDER = ["HOOK_BOMBER", "SEA_SERPENT_BURST", "SERPENT_ASSAULT", "CORKSCREW_BLOW", "OCTOPUNCH", "SEA_SERPENTS_RAGE",
                 "RAGING_SERPENT_ASSAULT", "NAUTILUS_STRIKE", "NAUTILUS_FINAL_ATTACK"]

# Unlock level of every row that has a threshold (Nimble Feet - a shared Explorer skill - is unlocked from the start)
UNLOCK_LEVEL = {
    "HOOK_BOMBER": 100,
    "SEA_SERPENT_BURST": 35,
    "SERPENT_ASSAULT": 69,
    "SERPENT_SCALE_FD": 66,
    "CORKSCREW_BLOW": 63,
    "OCTOPUNCH": 103,
    "SEA_SERPENTS_RAGE": 117,
    "RAGING_SERPENT_ASSAULT": 120,
    "NAUTILUS_STRIKE": 105,
    "NAUTILUS_FINAL_ATTACK": 113,
    "MAPLE_HERO_HELPER": 100,
    "ROLL_OF_THE_DICE_DICE": 74,
    "CROSSBONES_FD": 115,
    "TIME_LEAP_FD": 125,
    "SHADOW_HEART": 10,
    "QUICK_MOTION": 15,
    "AGILE_KNUCKLES": 33,
    "DARK_CLARITY": 40,
    "KNUCKLE_MASTERY": 43,
    "PHYSICAL_TRAINING": 38,
    "GROGGY_MASTERY_FD": 75,
    "SPEED_INFUSION": 107,
    "GSS_II_FD": 110,
    "SSR_WEAKEN": 117,
}

# Maple Hero (Lv.100): each skill's share relative to the 60-base reference (Serpent Assault 60%, Corkscrew Blow 40%)
MAPLE_HERO_RATIOS = {
    "SERPENT_ASSAULT": 60 / 60,
    "CORKSCREW_BLOW": 40 / 60,
}
MAPLE_HERO = dict(base=600, fidx=23, step=4)

# ---- Hook Bomber (basic attack) ----
HOOK_BOMBER_BASE = 290                                                    # x10 %, factor index 21, 4th job
HOOK_BOMBER_HITS = (5, 136, 6)                                            # 5 hits, 6 from level 136
HOOK_BOMBER_MASTERY = {102: 10, 106: 11, 116: 12, 120: 13, 128: 14, 132: 15}   # Damage mastery chain (raw tiers)
HOOK_BOMBER_BOSS_MASTERY = {111: 10, 124: 10}                             # Boss Damage mastery chain

# ---- Sea Serpent Burst / Greater Sea Serpent I / II, Serpent Assault, Assault Mode (Serpent Scale) ----
GSS1_LEVEL = 72                                                           # Greater Sea Serpent I: 130% -> 430%, job step 2 -> 3
SEA_SERPENT_BURST = dict(base=(1300, 4300), step=(2, 3), fidx=12, mastery={39: 50})
GSS_II_FD = dict(base=1000, fidx=22, step=4)                              # extra Final Damage of the burst (Greater Sea Serpent II)
SSB_COOLDOWN = (7, ((78, 2), (118, 2)))                                   # 7 s, -2 s at Lv78, -2 s at Lv118 (Greater Sea Serpent reuse masteries)
SSB_HITS = (2, 118, 1)                                                    # 2 hits, +1 from Lv118
SSB_TARGETS = (5, ((GSS1_LEVEL, 2), (110, 2)))                            # 5 targets, +2 from Lv72, +2 from Lv110
SERPENT_ASSAULT = dict(base=4800, fidx=12, step=3, mastery={82: 50}, hits=3, targets=12)
ASSAULT_DURATION = (10, 94, 5)                                            # 10 s, +5 s from Lv94 (Serpent Scale - Persistence)
ACTIVATIONS_TO_ASSAULT = (5, 104, 3)                                      # 5 activations to refill the scales, 3 from Lv104
SERPENT_SCALE = dict(base=250, fidx=21, step=3, held_scales_pct=4)        # +25% x F FD in Assault Mode; 2 held scales x 2% while rebuilding

# ---- buffs / passives (base = tenths of %, fidx, step; cooldown / duration in seconds) ----
NIMBLE_FEET = dict(base=150, fidx=0, step=1, duration=15, cooldown=60, scales=False)         # Attack Speed % (non-scaling)
SPEED_INFUSION = dict(base=200, fidx=21, step=4, duration=15, cooldown=35, fd_share=20)       # Attack Speed %; FD = 20% of the Attack Speed it grants
CROSSBONES = dict(base=100, fidx=21, step=4, duration=12, cooldown=28)                        # Final Damage
TIME_LEAP = dict(base=150, fidx=21, step=4, duration=40, cooldown=65, gated={138: 10})        # Final Damage
ROLL_OF_THE_DICE = dict(base=25, fidx=22, step=3, duty=(5, 7))                                # Attack% dice component, 5 s of every 7 s
SSR_WEAKEN = dict(base=150, fidx=21, step=4, duration=5)                                      # Assault Mark: damage-taken bonus for 5 s per Octopunch

# ---- damage rows (the verify script's DAMAGE_SKILLS dict order; summation order matters bit-for-bit) ----
# cooldown (s) [+ haste (level, multiplier)], hits, base damage (tenths of %), factor index, skill mastery chain, normal-monster targets.
# Octopunch's hit count depends on the monster type (5 on boss / PvP, 3 otherwise: ``hits_boss`` / ``hits_other``).  Sea Serpent's Rage and Raging
# Serpent Assault share Octopunch's live cooldown (``cooldown_of``).  Raging Serpent Assault is a 5 s window of 1 s ticks gated by the Assault Mode
# uptime (``proc_chance="assault_uptime"``).
CORKSCREW_COOLDOWN = 21
OCTOPUNCH_COOLDOWN = (16, 134, 0.7)           # 16 s; x0.7 from Lv134
NAUTILUS_STRIKE_COOLDOWN = 33
DAMAGE_SKILLS = {
    "CORKSCREW_BLOW": dict(step=3, cooldown=CORKSCREW_COOLDOWN, hits=2, base=3400, fidx=12, mastery={73: 80}, costs_action=True, targets=7),
    "OCTOPUNCH": dict(step=4, cooldown="octopunch", hits=("boss", 5, 3), base=9000, fidx=12, mastery={108: 50}, costs_action=True, targets=4),
    "SEA_SERPENTS_RAGE": dict(step=4, cooldown="octopunch", hits=2, base=17000, fidx=21, mastery={122: 100}, costs_action=True, targets=8),
    "RAGING_SERPENT_ASSAULT": dict(step=4, cooldown="octopunch", hits=2, icd=1, window=5, base=13000, fidx=12, mastery={130: 50},
                                   costs_action=True, targets=9, proc_chance="assault_uptime"),
    "NAUTILUS_STRIKE": dict(step=4, cooldown=NAUTILUS_STRIKE_COOLDOWN, hits=5, base=19500, fidx=12, mastery={126: 50}, costs_action=True, targets=15),
}

# ---- Nautilus Strike - Final Attack: any attack, 30% chance per attack per enemy hit, 1 s ICD ----
NAUTILUS_FINAL_ATTACK = dict(base=8500, fidx=21, step=4, chance=0.30, icd=1.0)
NAUTILUS_TRIGGER_KEYS = ["CORKSCREW_BLOW", "OCTOPUNCH", "NAUTILUS_STRIKE"]        # action-costing damage rows that trigger it (plus Hook Bomber)

# Action-costing rows (damage skills, then buffs) with their BASE cooldowns, in the verify script's cast-rate order
SKILL_CAST_ROWS = ["CORKSCREW_BLOW", "OCTOPUNCH", "NAUTILUS_STRIKE"]
BUFF_CAST_ROWS = [("NIMBLE_FEET", 60), ("CROSSBONES_FD", 28), ("TIME_LEAP_FD", 65), ("SPEED_INFUSION", 35)]
# actively cast buffs: each costs 1/APS s of start-up delay in fixed-duration fights without the engine
STARTUP_BUFFS = ["NIMBLE_FEET", "CROSSBONES_FD", "TIME_LEAP_FD", "SPEED_INFUSION"]

# ---- player's own stun (game table): Corkscrew Blow stuns for 1.8 s (cooldown 21 s), cast on cooldown from the start ----
PLAYER_STUN = [dict(id="CORK", key="CORKSCREW_BLOW", typ="cast", dur=1.8, p=1.0, cd=CORKSCREW_COOLDOWN)]

# ---- Status Effect Damage / KO timeline engine spec (src/status_timeline.py) ----
# engine id -> (row key, base cooldown, base duration): Crossbones / Time Leap = Final Damage buffs ('ramp' kind with a flat profile)
STATUS_BUFFS = [("CB", "CROSSBONES_FD", "ramp"), ("TL", "TIME_LEAP_FD", "ramp")]
BUFF_SPEC = {
    "CB": ("CROSSBONES_FD", 28, 12), "TL": ("TIME_LEAP_FD", 65, 40),
}
# (group id, row key whose cooldown gives the cast spacing, [(row key, type, window row key or None, unlock-gate row key or None, weight row key)])
STATUS_GROUPS = [
    ("CORK", "CORKSCREW_BLOW", [("CORKSCREW_BLOW", "burst", None, None, "CORKSCREW_BLOW")]),
    ("OCTO", "OCTOPUNCH", [
        ("OCTOPUNCH", "burst", None, None, "OCTOPUNCH"),
        ("SEA_SERPENTS_RAGE", "burst", None, None, "SEA_SERPENTS_RAGE"),
        ("RAGING_SERPENT_ASSAULT", "dot", "RAGING_SERPENT_ASSAULT", None, "RAGING_SERPENT_ASSAULT")]),
    ("NAUT", "NAUTILUS_STRIKE", [("NAUTILUS_STRIKE", "burst", None, None, "NAUTILUS_STRIKE")]),
]
# Spread uniformly over the fight: Hook Bomber (the basic attack) and the procs that trigger off basic attacks / any attack
STATUS_UNIFORM_ROWS = ["HOOK_BOMBER", "SEA_SERPENT_BURST", "SERPENT_ASSAULT", "NAUTILUS_FINAL_ATTACK"]
STATUS_CAST_PREFIX = {key: f"buff.{bid}" for bid, key, _k in STATUS_BUFFS}
for _gid, _cast, _ents in STATUS_GROUPS:
    for _e in _ents:
        STATUS_CAST_PREFIX.setdefault(_e[0], f"grp.{_gid}")
    STATUS_CAST_PREFIX[_cast] = f"grp.{_gid}"
# rows whose hits/s come from the engine's effective cast count (last DoT window truncated by the fight end)
STATUS_FS_KEYS = [e[0] for _g, _c, ents in STATUS_GROUPS for e in ents if e[1] in ("dot", "end")]
STATUS_PHI_ROWS = sorted({e[0] for _g, _c, ents in STATUS_GROUPS for e in ents})
