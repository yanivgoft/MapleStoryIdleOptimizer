"""Ice/Lightning Arch Mage (ILM) static game data, as plain Python data (transcribed from ``src/build_ice_lightning_mage_workbook.py`` /
``src/verify_ice_lightning_mage_workbook.py``; the builder stays the workbook's source, this module is the engine's copy - keep both in sync
when a skill changes).

Base-damage numbers are in tenths of a percent (``base``); ``fidx`` is the FactorTable column; ``job_step`` the job tier (1-4) whose skill
level scales the skill.  Level-dependent values are written as a *tier* ``(default, (threshold, value))`` - "``value`` from character level
``threshold`` on, else ``default``" - and resolved by ``engine/classes/ice_lightning_mage.py``.  ``mastery`` chains are raw tier values summed
over every reached level (CLAUDE.md bug 2).
"""

SKILL_NAMES = {
    "CHAIN_LIGHTNING": "Chain Lightning",
    "THUNDER_BOLT": "Thunder Bolt",
    "GLACIER_WALL": "Glacier Wall",
    "THUNDER_SPHERE": "Thunder Sphere",
    "FREEZING_BREATH": "Freezing Breath",
    "BLIZZARD": "Blizzard",
    "BLIZZARD_FINAL_ATTACK": "Blizzard - Final Attack",
    "FROZEN_ORB": "Frozen Orb",
    "ELQUINES": "Elquines",
}

# Result rows in the workbook's Skills-sheet order (damage rows only)
DPS_ROW_ORDER = ["CHAIN_LIGHTNING", "THUNDER_BOLT", "GLACIER_WALL", "THUNDER_SPHERE", "FREEZING_BREATH", "BLIZZARD", "BLIZZARD_FINAL_ATTACK",
                 "FROZEN_ORB", "ELQUINES"]

# Unlock level of every row that has a threshold (the builder's UNLOCK_LEVEL; rows not listed - Nimble Feet - are unlocked from the start)
UNLOCK_LEVEL = {
    "CHAIN_LIGHTNING": 100,
    "MAGIC_GUARD": 15,
    "MEDITATION": 40,
    "THUNDER_BOLT": 38,
    "GLACIER_WALL": 63,
    "THUNDER_SPHERE": 69,
    "FREEZING_BREATH": 103,
    "BLIZZARD": 105,
    "BLIZZARD_FINAL_ATTACK": 113,
    "FROZEN_ORB": 107,
    "ELQUINES": 115,
    "MP_EATER_MP_BOOST": 49,
    "ELEMENTAL_RESET": 72,
    "ELEMENT_AMPLIFICATION": 75,
    "INFINITY": 110,
    "MAGIC_ACCELERATION": 33,
    "SPELL_MASTERY": 43,
    "HIGH_WISDOM": 50,
    "MAGIC_CRITICAL_RATE": 74,
    "MAGIC_CRITICAL_DAMAGE": 74,
    "BUFF_MASTERY": 117,
    "ARCANE_AIM": 120,
}

# ---- Chain Lightning (basic attack, 4th job, factor 21) ----
CHAIN_LIGHTNING_BASE = 290                                              # tenths of %
CHAIN_LIGHTNING_HITS = (5, (136, 6))                                    # 5 hits, 6 from level 136
CHAIN_LIGHTNING_MASTERY = {102: 10, 106: 11, 116: 12, 120: 13, 128: 14, 132: 15}    # Damage mastery chain (raw tiers)
CHAIN_LIGHTNING_BOSS_MASTERY = {111: 10, 124: 10}                       # Boss Monster Damage mastery chain

# ---- damage rows after Chain Lightning, in the verify script's SKILLS dict order (summation order matters bit-for-bit) ----
# cooldown tier (s), hits, icd tier (s, DoT / summon rows), window (s), base damage, factor index, skill mastery chain, boss / normal
# mastery % (normal: tier), costs an action slot; chance / rolls (proc rows).
SKILL_TEMPLATES = {
    "THUNDER_BOLT": dict(job_step=2, cooldown=18, hits=3, base=1800, fidx=12, mastery={39: 70}, mastery_boss=0, mastery_normal=0,
                         costs_action=True),
    "GLACIER_WALL": dict(job_step=3, cooldown=(22, (90, 22 * 0.7)), hits=3, base=2900, fidx=12, mastery={68: 80}, mastery_boss=0,
                         mastery_normal=0, costs_action=True),
    "THUNDER_SPHERE": dict(job_step=3, cooldown=(30, (78, 30 * 0.7)), hits=3, icd=(2, (104, 2 * 0.7)), window=10, base=1000, fidx=12,
                           mastery={73: 50}, mastery_boss=0, mastery_normal=(150, (94, 150 + 100)), costs_action=True),
    "FREEZING_BREATH": dict(job_step=4, cooldown=40, hits=1, icd=0.5, window=5, base=8000, fidx=12, mastery={108: 50}, mastery_boss=0,
                            mastery_normal=0, costs_action=True),
    "BLIZZARD": dict(job_step=4, cooldown=33, hits=3, base=6000, fidx=12, mastery={134: 50}, mastery_boss=0, mastery_normal=0,
                     costs_action=True),
    "BLIZZARD_FINAL_ATTACK": dict(job_step=4, cooldown=None, hits=1, base=9500, fidx=21, chance=30, rolls=1, icd=1, mastery={134: 50},
                                  mastery_boss=0, mastery_normal=0, costs_action=False),
    "FROZEN_ORB": dict(job_step=4, cooldown=23, hits=1, icd=(0.5, (126, 0.5 - 0.2)), window=6, base=9000, fidx=12, mastery={122: 50},
                       mastery_boss=0, mastery_normal=0, costs_action=True),
    "ELQUINES": dict(job_step=4, cooldown=80, hits=1, icd=(4, (130, 4 * 0.8)), window=30, base=35000, fidx=12, mastery={138: 50},
                     mastery_boss=0, mastery_normal=0, costs_action=True),
}

# Cast buffs (BUFFS dict order of the verify script): job_step, cooldown tier, duration tier, base, factor index, target stat, costs an action
# slot; Infinity's Final Damage is the time-average of its ramp (x64/45).
BUFFS = {
    "MAGIC_GUARD": dict(job_step=1, cooldown=(30, (21, 30 * 0.7)), duration=15, base=120, fidx=21, scales=True, target="ATTACK",
                        costs_action=True),
    "MEDITATION": dict(job_step=2, cooldown=30, duration=(15, (44, 15 * 1.3)), base=200, fidx=21, scales=True, target="ATTACK",
                       costs_action=True),
    "INFINITY": dict(job_step=4, cooldown=30, duration=15, base=150, fidx=21, scales=True, target="FINAL_DAMAGE", costs_action=True,
                     ramp_mult=64 / 45),
}

# Passives (factor 22 unless non-scaling), in the verify script's order
PASSIVES = {
    "BUFF_MASTERY": dict(job_step=4, base=100, fidx=22, scales=True),
    "ARCANE_AIM": dict(job_step=4, base=30, fidx=22, scales=True),
    "ELEMENT_AMPLIFICATION": dict(job_step=3, base=150, fidx=22, scales=True),
    "ELEMENTAL_RESET": dict(job_step=3, base=120, fidx=22, scales=True),
    "MP_EATER_MP_BOOST": dict(job_step=2, base=70, fidx=0, scales=False),
}

NIMBLE_FEET = dict(job_step=1, base=150, fidx=0, scales=False, cooldown=60, duration=15)       # Attack Speed % (non-scaling)

# Freezing Breath - Weaken (Mastery Lv.118): +15% Damage Taken, 30 s, duty-cycle averaged off Freezing Breath's own 40 s cooldown
FREEZING_BREATH_WEAKEN = dict(level=118, pct=15, duration=30, cooldown=40)
# Frozen Break (Lv.66, +2%p/stack mastery Lv.98, 5 stacks) + Frost Clutch (Lv.125, 4%/stack, 5 stacks): flat level-gated Damage%
DAMAGE_BONUS = [(66, 15), (98, 10), (125, 20)]

# Maple Hero: target share (tenths of %) through factor 23 of the 4th-job level
MAPLE_TARGETS = {"THUNDER_BOLT": 1000, "GLACIER_WALL": 300, "THUNDER_SPHERE": 200}

# Normal-monster targets of each AoE (boss / PvP are single target); Chain Lightning: 6 + Basic Attack Target Increase, Elquines: tier
NORMAL_MONSTER_TARGETS = {
    "THUNDER_BOLT": 8, "GLACIER_WALL": 8, "THUNDER_SPHERE": 6, "FREEZING_BREATH": 10,
    "BLIZZARD": 7, "BLIZZARD_FINAL_ATTACK": 1, "FROZEN_ORB": 10,
}
ELQUINES_TARGETS = (3, (138, 6))

# Blizzard - Final Attack: 30% per enemy hit of any attack, 1 s ICD; triggers per cast of each source (Chain Lightning always counts once)
BLIZZARD_PROC_TRIGGERS = {"THUNDER_BOLT": 1, "GLACIER_WALL": 1, "FREEZING_BREATH": 1, "BLIZZARD": 3, "FROZEN_ORB": 1}

# Frozen Orb halves its damage against a single target (boss / PvP)
FROZEN_ORB_SINGLE_TARGET_FACTOR = 0.5

# Rows without a cooldown-decrease exemption; the trigger-rate surrogate rows (Chain Lightning, Blizzard - Final Attack) have no cooldown.
CDR_EXEMPT = []

# ---- player's own stun (game table): Glacier Wall freezes for 2 s, cast on cooldown from the start (its cooldown tier is the row's own) ----
PLAYER_STUN = [dict(id="WALL", key="GLACIER_WALL", typ="cast", dur=2.0, p=1.0)]

# ---- Status Effect Damage / KO timeline engine spec (src/status_timeline.py) ----
STATUS_BUFFS = [("MED", "MEDITATION", "atk"), ("MG", "MAGIC_GUARD", "atk"), ("INF", "INFINITY", "ramp")]
INFINITY_RAMP = dict(p0=15, p1=25, ramp_t=10, dur0=15)     # Infinity: +15% -> +25% Final Damage over 10 s of its 15 s
# (group id, row key whose cooldown gives the cast spacing, [(row key, type, window row key or None, unlock-gate row key or None, weight row key)])
STATUS_GROUPS = [
    ("BOLT", "THUNDER_BOLT", [("THUNDER_BOLT", "burst", None, None, "THUNDER_BOLT")]),
    ("WALL", "GLACIER_WALL", [("GLACIER_WALL", "burst", None, None, "GLACIER_WALL")]),
    ("SPHERE", "THUNDER_SPHERE", [("THUNDER_SPHERE", "dot", "THUNDER_SPHERE", None, "THUNDER_SPHERE")]),
    ("BREATH", "FREEZING_BREATH", [("FREEZING_BREATH", "dot", "FREEZING_BREATH", None, "FREEZING_BREATH")]),
    ("BLIZZARD", "BLIZZARD", [("BLIZZARD", "burst", None, None, "BLIZZARD")]),
    ("ORB", "FROZEN_ORB", [("FROZEN_ORB", "dot", "FROZEN_ORB", None, "FROZEN_ORB")]),
    ("ELQUINES", "ELQUINES", [("ELQUINES", "dot", "ELQUINES", None, "ELQUINES")]),
]
# rows spread uniformly over the fight: the basic attack and the Blizzard Final Attack proc (triggered by any attack)
STATUS_UNIFORM_ROWS = ["CHAIN_LIGHTNING", "BLIZZARD_FINAL_ATTACK"]
STATUS_CAST_PREFIX = {key: f"buff.{bid}" for bid, key, _k in STATUS_BUFFS}
for _gid, _cast, _ents in STATUS_GROUPS:
    for _e in _ents:
        STATUS_CAST_PREFIX.setdefault(_e[0], f"grp.{_gid}")
    STATUS_CAST_PREFIX[_cast] = f"grp.{_gid}"
# rows whose hits/s come from the engine's effective cast count (last DoT / summon window truncated by the fight end)
STATUS_FS_KEYS = [e[0] for _g, _c, ents in STATUS_GROUPS for e in ents if e[1] in ("dot", "end")]
STATUS_PHI_ROWS = sorted({e[0] for _g, _c, ents in STATUS_GROUPS for e in ents})
