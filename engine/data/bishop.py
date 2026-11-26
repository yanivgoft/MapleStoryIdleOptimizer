"""Bishop static game data, as plain Python data (transcribed from ``src/build_bishop_workbook.py`` / ``src/verify_bishop_workbook.py``; the
builder stays the workbook's source, this module is the engine's copy - keep both in sync when a skill changes).

Base-damage numbers are in tenths of a percent (``base``); ``fidx`` is the FactorTable column; ``job_step`` the job tier (1-4) whose skill
level scales the skill.  Level-dependent values are written as a *tier* ``(default, (threshold, value))`` - "``value`` from character level
``threshold`` on, else ``default``" - and resolved by ``engine/classes/bishop.py``.  ``mastery`` chains are raw tier values summed over every
reached level (CLAUDE.md bug 2).  The expressions (``30 * 0.7`` ...) are written exactly as in the verify script so the floats are identical.
"""

SKILL_NAMES = {
    "BIG_BANG": "Big Bang",
    "ANGEL_RAY": "Angel Ray",
    "ANGEL_RAY_BOSS_PROC": "Angel Ray - Boss Monster Damage (Mastery Lv.122)",
    "GENESIS": "Genesis",
    "BAHAMUT": "Bahamut",
    "TRIUMPH_FEATHER": "Triumph Feather",
}

# Result rows in the workbook's Skills-sheet order (damage rows only)
DPS_ROW_ORDER = ["BIG_BANG", "ANGEL_RAY", "ANGEL_RAY_BOSS_PROC", "GENESIS", "BAHAMUT", "TRIUMPH_FEATHER"]

# Unlock level of every row that has a threshold (the builder's UNLOCK_LEVEL; rows not listed - Nimble Feet - are unlocked from the start)
UNLOCK_LEVEL = {
    "BIG_BANG": 100,
    "MAGIC_GUARD": 15,
    "HEAL": 38,
    "BLESS": 40,
    "ANGEL_RAY": 103,
    "ANGEL_RAY_BOSS_PROC": 122,
    "GENESIS": 105,
    "BAHAMUT": 115,
    "HOLY_FOUNTAIN": 66,
    "HOLY_MAGIC_SHELL": 69,
    "HOLY_SYMBOL": 72,
    "DIVINE_PROTECTION": 60,
    "ADVANCED_BLESSING": 107,
    "TRIUMPH_FEATHER": 63,
    "MAPLE_HERO_BISHOP": 100,
    "MP_EATER_MP_BOOST": 49,
    "ELEMENT_AMPLIFICATION": 75,
    "INFINITY": 110,
    "BLOOD_OF_THE_DIVINE": 125,
    "MAGIC_ACCELERATION": 33,
    "SPELL_MASTERY": 43,
    "HIGH_WISDOM": 50,
    "MAGIC_CRITICAL_RATE": 74,
    "MAGIC_CRITICAL_DAMAGE": 74,
    "BUFF_MASTERY": 117,
    "ARCANE_AIM": 120,
}

# ---- Big Bang (basic attack, 4th job, factor 21) ----
BIG_BANG_BASE = 290                                                    # tenths of %
BIG_BANG_HITS = (5, (136, 6))                                          # 5 hits, 6 from level 136
BIG_BANG_MASTERY = {102: 10, 106: 11, 116: 12, 120: 13, 128: 14, 132: 15}    # Damage mastery chain (raw tiers)
BIG_BANG_BOSS_MASTERY = {111: 10, 124: 10}                             # Boss Monster Damage mastery chain

# ---- damage rows after Big Bang, in the verify script's SKILLS dict order (summation order matters bit-for-bit) ----
# cooldown tier (s), hits, icd (s, summon rows), window (s), base damage, factor index, skill mastery chain, costs an action slot, normal-monster targets
# (tier).  Angel Ray's Lv.122 Boss Monster Damage proc is a separate row sharing Angel Ray's cooldown, costing no action slot, boss-only.
SKILL_TEMPLATES = {
    "ANGEL_RAY": dict(job_step=4, cooldown=17, hits=6, base=6800, fidx=12, mastery={108: 50}, costs_action=True, targets=1),
    "ANGEL_RAY_BOSS_PROC": dict(job_step=4, cooldown=17, hits=1, base=6800, fidx=12, mastery={}, costs_action=False, targets=1),
    "GENESIS": dict(job_step=4, cooldown=(23, (126, 23 * 0.7)), hits=6, base=7000, fidx=12, mastery={118: 50}, costs_action=True, targets=10),
    "BAHAMUT": dict(job_step=4, cooldown=(80, (138, 80 * 0.7)), hits=1, icd=4, window=30, base=35000, fidx=12, mastery={130: 50},
                    costs_action=True, targets=(3, (130, 6))),
}

# Cast buffs (BUFFS dict order of the verify script): job_step, cooldown tier, duration tier, base, factor index, target stat, costs an action slot,
# own mastery chain (percentage points added to the buff's value); Infinity's Final Damage is the time-average of its ramp (x64/45).
BUFFS = {
    "MAGIC_GUARD": dict(job_step=1, cooldown=(30, (21, 30 * 0.7)), duration=15, base=120, fidx=21, scales=True, costs_action=True, target="ATTACK"),
    "HEAL": dict(job_step=2, cooldown=18, duration=(10, (39, 10 * 1.5)), base=100, fidx=21, scales=True, costs_action=True, mastery={54: 8},
                 target="ATTACK"),
    "BLESS": dict(job_step=2, cooldown=24, duration=(15, (44, 15 * 1.3)), base=160, fidx=21, scales=True, costs_action=True, target="ATTACK"),
    "HOLY_MAGIC_SHELL": dict(job_step=3, cooldown=27, duration=22, base=150, fidx=21, scales=True, costs_action=True, target="ATTACK"),
    "ADVANCED_BLESSING": dict(job_step=4, cooldown=26, duration=20, base=70, fidx=21, scales=True, costs_action=True, mastery={113: 4},
                              target="FINAL_DAMAGE"),
    "INFINITY": dict(job_step=4, cooldown=30, duration=15, base=150, fidx=21, scales=True, costs_action=True, ramp_mult=64 / 45,
                     target="FINAL_DAMAGE"),
}

# Passives (factor 22 unless non-scaling), in the verify script's order
PASSIVES = {
    "BUFF_MASTERY": dict(job_step=4, base=100, fidx=22, scales=True),
    "ARCANE_AIM": dict(job_step=4, base=30, fidx=22, scales=True),
    "ELEMENT_AMPLIFICATION": dict(job_step=3, base=150, fidx=22, scales=True),
    "DIVINE_PROTECTION": dict(job_step=3, base=250, fidx=22, scales=True),
    "MP_EATER_MP_BOOST": dict(job_step=2, base=70, fidx=0, scales=False),
    "BLOOD_OF_THE_DIVINE": dict(job_step=4, base=50, fidx=22, scales=True),
    "MAPLE_HERO_BISHOP": dict(job_step=4, base=500, fidx=23, scales=True),
    "HOLY_SYMBOL": dict(job_step=3, base=150, fidx=22, scales=True),
}
HOLY_SYMBOL_MASTERY = {90: 25}                                         # Damage Boost (flat Damage%, solo-always-true)
HOLY_SYMBOL_DURATION = (14, (98, 14 * 1.5))
HOLY_SYMBOL_COOLDOWN = 28

# Divine Protection: +25 % Defense, PERMANENT since the 2026-11-26 patch (was a 15 s window every 20 s): part of the typed Defense %, only the skill-level delta is modelled
DIVINE_PROTECTION = dict(base=250, fidx=22, job_step=3, cooldown=20, duration=15)
# Invincible: converts a level-scaling share of total Defense (10 x factor 22 / 1000 percent) into INT from level 35
INVINCIBLE = dict(level=35, base=10, fidx=22)
# Holy Fountain - Boss Monster Damage (Mastery Lv.68, 10% -> 20%): flat, duty-cycle averaged off Holy Fountain's own 30 s cooldown, 15 s linger
HOLY_FOUNTAIN = dict(level=68, pct=20, cooldown=30, duration=15)
# Blood of the Divine: assumed 100% HP -> +4 x its own Final-Damage value as Crit Damage
BLOOD_OF_THE_DIVINE_CRIT_FACTOR = 4
# Flat +15% Attack Speed from Lv.134
FLAT_AS_BONUS = (134, 15)

NIMBLE_FEET = dict(job_step=1, base=150, fidx=0, scales=False, cooldown=60, duration=15)       # Attack Speed % (non-scaling)

# Triumph Feather: bespoke two-stage chance proc (stage 1 starts the angel-power window, stage 2 fires inside it), uniformly spread
TRIUMPH_FEATHER = dict(base=1500, fidx=21, job_step=3, mastery={73: 50}, p1=(15, (78, 25)), d1=10, cooldown=18, p2=35, icd2=1,
                       targets=(1, (94, 7)), hits=(2, (104, 3)))

# Normal-monster targets of Big Bang: 6 + Basic Attack Target Increase (handled by the model); every other row: its template's `targets`.

# Rows of CDR exemption: none (every cooldown is real)
CDR_EXEMPT = []

# ---- player's own stun (game table): Angel Ray stuns for 1 s (cooldown 17 s, no Reuse mastery), cast on cooldown from the start ----
PLAYER_STUN = [dict(id="RAY", key="ANGEL_RAY", typ="cast", dur=1.0, p=1.0, cd=17, min_level=0, tick=1.0, win=0.0)]

# ---- Status Effect Damage / KO timeline engine spec (src/status_timeline.py) ----
STATUS_BUFFS = [("MG", "MAGIC_GUARD", "atk"), ("HEAL", "HEAL", "atk"), ("BLS", "BLESS", "atk"), ("HMS", "HOLY_MAGIC_SHELL", "atk"),
                ("AB", "ADVANCED_BLESSING", "ramp"), ("INF", "INFINITY", "ramp")]
INFINITY_RAMP = dict(p0=15, p1=25, ramp_t=10, dur0=15)     # Infinity: +15% -> +25% Final Damage over 10 s of its 15 s
# Advanced Blessing: flat (no ramp) Final Damage for the shorter of its duration / cooldown, scaled by Infinity's average (mean-field cross term)
ADVANCED_BLESSING_RAMP = dict(p0=1, p1=1, ramp_t=1, dur0=1)
# (group id, row key whose cooldown gives the cast spacing, [(row key, type, window row key or None, unlock-gate row key or None, weight row key)])
STATUS_GROUPS = [
    # Angel Ray (1 s stun, fixed on-cooldown schedule) + its Lv.122 Boss Monster Damage proc, which fires on every Angel Ray cast
    ("RAY", "ANGEL_RAY", [
        ("ANGEL_RAY", "burst", None, None, "ANGEL_RAY"),
        ("ANGEL_RAY_BOSS_PROC", "burst", None, "ANGEL_RAY_BOSS_PROC", "ANGEL_RAY_BOSS_PROC")]),
    ("GEN", "GENESIS", [("GENESIS", "burst", None, None, "GENESIS")]),
    # Bahamut: a 30 s summon (4 s ticks)
    ("BAH", "BAHAMUT", [("BAHAMUT", "dot", "BAHAMUT", None, "BAHAMUT")]),
]
# rows spread uniformly over the fight: Big Bang (the basic attack) and Triumph Feather (a chance proc triggered by every attack)
STATUS_UNIFORM_ROWS = ["BIG_BANG", "TRIUMPH_FEATHER"]
STATUS_CAST_PREFIX = {key: f"buff.{bid}" for bid, key, _k in STATUS_BUFFS}
for _gid, _cast, _ents in STATUS_GROUPS:
    for _e in _ents:
        STATUS_CAST_PREFIX.setdefault(_e[0], f"grp.{_gid}")
    STATUS_CAST_PREFIX[_cast] = f"grp.{_gid}"
# rows whose hits/s come from the engine's effective cast count (last DoT / summon window truncated by the fight end)
STATUS_FS_KEYS = [e[0] for _g, _c, ents in STATUS_GROUPS for e in ents if e[1] in ("dot", "end")]
STATUS_PHI_ROWS = sorted({e[0] for _g, _c, ents in STATUS_GROUPS for e in ents})
