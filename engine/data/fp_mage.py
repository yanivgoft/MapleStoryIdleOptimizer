"""FP-Mage (Fire/Poison Arch Mage) static game data, as plain Python data (transcribed from ``src/build_fp_mage_workbook.py`` /
``src/verify_fp_mage_workbook.py``; the builder stays the workbook's source, this module is the engine's copy - keep both in sync
when a skill changes).  Level-dependent values (hit counts, windows, mastery bonuses that switch on at a level) are resolved by the
model in ``engine/classes/fp_mage.py``; only the constants live here.
"""

# row key -> display name (Skills sheet "Name" column)
SKILL_NAMES = {
    "BASIC_ATTACK": "Basic Attack",
    "IGNITE": "Ignite",
    "POISON_BREATH": "Poison Breath",
    "ELEMENTAL_DRAIN": "Elemental Drain",
    "MEDITATION": "Meditation",
    "POISON_MIST_BURST": "Poison Mist (burst)",
    "POISON_MIST_DOT": "Poison Mist (fog DoT)",
    "MIST_ERUPTION": "Mist Eruption",
    "CREEPING_TOXIN": "Creeping Toxin",
    "BURNING_MAGIC": "Burning Magic",
    "ELEMENTAL_DECREASE": "Elemental Decrease",
    "METEOR_SHOWER_BURST": "Meteor Shower (burst)",
    "METEOR_PROC": "Meteor Proc (30% on-hit, 1s ICD)",
    "FLAME_HAZE_BURST": "Flame Haze (burst)",
    "FLAME_HAZE_DOT": "Flame Haze (burn DoT)",
    "MAGIC_GUARD": "Magic Guard",
    "NIMBLE_FEET": "Nimble Feet",
    "INFINITY": "Infinity",
    "MAGIC_CRITICAL_RATE": "Magic Critical (Crit Rate)",
    "MAGIC_CRITICAL_DAMAGE": "Magic Critical (Crit Damage)",
    "SPELL_MASTERY": "Spell Mastery",
    "ELEMENT_AMPLIFICATION": "Element Amplification",
    "IFRIT": "Ifrit",
    "BUFF_MASTERY": "Buff Mastery",
    "ARCANE_AIM": "Arcane Aim",
    "FERVENT_DRAIN": "Fervent Drain",
    "FLAME_HAZE_FOG": "Flame Haze (poison fog DoT)",
}

# Result rows in the workbook's Skills-sheet order (damage rows only)
DPS_ROW_ORDER = ["BASIC_ATTACK", "IGNITE", "POISON_BREATH", "ELEMENTAL_DRAIN", "POISON_MIST_BURST", "POISON_MIST_DOT", "MIST_ERUPTION",
                 "CREEPING_TOXIN", "METEOR_SHOWER_BURST", "METEOR_PROC", "FLAME_HAZE_BURST", "FLAME_HAZE_DOT", "IFRIT", "FLAME_HAZE_FOG"]

# Unlock level of skills / masteries added between level 102-138; rows not listed are unlocked from the start.
UNLOCK_LEVEL = {
    "MIST_ERUPTION": 103,
    "METEOR_SHOWER_BURST": 105,
    "FLAME_HAZE_BURST": 107,
    "FLAME_HAZE_DOT": 107,
    "INFINITY": 110,
    "METEOR_PROC": 113,
    "IFRIT": 115,
    "BUFF_MASTERY": 117,
    "FLAME_HAZE_FOG": 118,
    "ARCANE_AIM": 120,
    "FERVENT_DRAIN": 125,
}

# Basic Attack Mastery (raw tier values summed, then ONE multiplier) and Boss Mastery, as {unlock level: tier value}
BASIC_ATTACK_MASTERY = {102: 10, 106: 11, 116: 12, 120: 13, 128: 14, 132: 15}
BASIC_ATTACK_BOSS_MASTERY = {111: 10, 124: 10}

BASIC_ATTACK_BASE = 290          # tenths of %, factor index 21
BASIC_ATTACK_HITS = 5

# Damage / DoT rows: job_step, cooldown (s), hits per cast, ICD (s, DoT rows), window (s, DoT rows), base damage (tenths of %),
# factor index, skill mastery %, boss mastery %, normal mastery %, costs an action slot.  Rows whose values change with the
# character level (marked LV) are filled in by the model:
#   POISON_MIST_DOT.icd / FLAME_HAZE_FOG.icd (0.8 -> 0.4 at 104), MIST_ERUPTION.hits / mastery (3 -> 4 normal hits at 108; +100% at
#   122; 1 boss hit), METEOR_SHOWER_BURST.mastery (+50% at 134), FLAME_HAZE_DOT.window (20 boss / 10 normal), IFRIT.window (30 -> 40
#   at 138) and normal targets (3 -> 6 at 138), BASIC_ATTACK mastery.
SKILL_TEMPLATES = {
    "IGNITE": dict(job_step=2, cooldown=1, hits=1, base=130, fidx=21, mastery=100, mastery_boss=0, mastery_normal=0, costs_action=False),
    "POISON_BREATH": dict(job_step=2, cooldown=18, hits=3, base=2000, fidx=12, mastery=70, mastery_boss=0, mastery_normal=0, costs_action=True),
    "ELEMENTAL_DRAIN": dict(job_step=2, cooldown=1, hits=5, base=120, fidx=21, mastery=0, mastery_boss=0, mastery_normal=0, costs_action=False),
    "POISON_MIST_BURST": dict(job_step=3, cooldown=24.5, hits=3, base=1600, fidx=12, mastery=50, mastery_boss=0, mastery_normal=0, costs_action=True),
    "POISON_MIST_DOT": dict(job_step=3, cooldown=24.5, hits=1, window=20, base=700, fidx=12, mastery=0, mastery_boss=0, mastery_normal=0, costs_action=False),
    "MIST_ERUPTION": dict(job_step=4, cooldown=24.5, base=30000, fidx=12, mastery_boss=0, mastery_normal=0, costs_action=False),
    "CREEPING_TOXIN": dict(job_step=3, cooldown=27, hits=2, icd=2, window=15, base=1200, fidx=12, mastery=50, mastery_boss=0, mastery_normal=100, costs_action=True),
    "METEOR_SHOWER_BURST": dict(job_step=4, cooldown=33, hits=9, base=6000, fidx=12, mastery_boss=0, mastery_normal=0, costs_action=True),
    "FLAME_HAZE_BURST": dict(job_step=4, cooldown=25, hits=3, base=12000, fidx=12, mastery=0, mastery_boss=0, mastery_normal=0, costs_action=True),
    "FLAME_HAZE_DOT": dict(job_step=4, cooldown=25, hits=1, icd=0.5, base=1500, fidx=12, mastery=0, mastery_boss=0, mastery_normal=0, costs_action=False),
    "IFRIT": dict(job_step=4, cooldown=80, hits=1, icd=4, base=35000, fidx=12, mastery=0, mastery_boss=0, mastery_normal=0, costs_action=True),
    "FLAME_HAZE_FOG": dict(job_step=3, cooldown=25, hits=1, window=20, base=700, fidx=12, mastery=0, mastery_boss=0, mastery_normal=0, costs_action=False),
}
# Evaluation order of the damage rows (the verify script's SKILLS dict order; summation order matters bit-for-bit)
SKILL_ORDER = ["IGNITE", "POISON_BREATH", "ELEMENTAL_DRAIN", "POISON_MIST_BURST", "POISON_MIST_DOT", "MIST_ERUPTION", "CREEPING_TOXIN",
               "METEOR_SHOWER_BURST", "FLAME_HAZE_BURST", "FLAME_HAZE_DOT", "IFRIT", "FLAME_HAZE_FOG"]

# Cast buffs: job_step, cooldown, duration, base, factor index, scales with level?, target stat, costs an action slot
BUFFS = {
    "MEDITATION": dict(job_step=2, cooldown=30, duration=19.5, base=200, fidx=21, scales=True, target="ATTACK", costs_action=True),
    "MAGIC_GUARD": dict(job_step=1, cooldown=21, duration=15, base=120, fidx=21, scales=True, target="ATTACK", costs_action=True),
    "NIMBLE_FEET": dict(job_step=1, cooldown=60, duration=15, base=150, fidx=0, scales=False, target="ATTACK_SPEED", costs_action=True),
    "INFINITY": dict(job_step=4, cooldown=30, duration=15, base=216.67, fidx=21, scales=True, target="FINAL_DAMAGE", costs_action=True),
}

# Level 102..138 passives (factor 22); each feeds a specific shared formula (buff duration / Final Damage / skill damage)
PASSIVES = {
    "BUFF_MASTERY": dict(job_step=4, base=100, fidx=22, scales=True),
    "ARCANE_AIM": dict(job_step=4, base=30, fidx=22, scales=True),
    "FERVENT_DRAIN": dict(job_step=4, base=40, fidx=22, scales=True),
}

# Maple Hero (Maple Warrior-style) per-row share, tenths of %, applied through factor 23 of the 4th-job level
MAPLE_TARGETS = {
    "IGNITE": 500, "POISON_BREATH": 800, "ELEMENTAL_DRAIN": 1500,
    "POISON_MIST_BURST": 100, "POISON_MIST_DOT": 100, "CREEPING_TOXIN": 100,
    "FLAME_HAZE_FOG": 100,  # Poison Mist's own fog, just cast by Flame Haze (level-118 mastery)
}

# Meteor Proc: 30% on every qualifying attack, shared 1 s ICD; Basic Attack always counts, Creeping Toxin / Ifrit do not
# The verify script keeps these in a set, so its float summation order depends on PYTHONHASHSEED (ulp-level noise).  The engine
# fixes the order below = the set's iteration order under PYTHONHASHSEED=0, the seed the golden file is generated with.
TRIGGERS_METEOR = ["METEOR_SHOWER_BURST", "FLAME_HAZE_BURST", "POISON_MIST_BURST", "POISON_BREATH"]
METEOR_PROC_TRIGGERS_PER_CAST = {"METEOR_SHOWER_BURST": 3}     # each of Meteor Shower's 3 meteors is its own attack
METEOR_PROC_CHANCE = 30
METEOR_PROC_ICD = 1
METEOR_PROC_BASE = 9500
METEOR_PROC_FIDX = 21

# Normal-monster targets of each AoE (boss / PvP are single target); Ifrit's and Basic Attack's depend on level / inputs
NORMAL_MONSTER_TARGETS = {
    "IGNITE": 3, "POISON_BREATH": 6, "POISON_MIST_BURST": 10,
    "POISON_MIST_DOT": 10, "MIST_ERUPTION": 10, "METEOR_SHOWER_BURST": 7,
    "FLAME_HAZE_BURST": 10, "FLAME_HAZE_DOT": 10,
    "FLAME_HAZE_FOG": 10, "CREEPING_TOXIN": 10,
}  # + IFRIT: 3 (6 from level 138); BASIC_ATTACK: 6 + target increase (+1 from level 136)

CDR_EXEMPT = ["IGNITE", "ELEMENTAL_DRAIN"]   # rate-surrogate cooldowns, not real ones

# Ignite (game table skillIndex 52060): 50% per enemy hit to create a wall (2.5 s ICD after each success), up to 3 walls ticking every second
IGNITE_CHANCE, IGNITE_ICD, IGNITE_WALLS = 0.5, 2.5, 3

# ---- Status Effect Damage / KO timeline engine spec (src/status_timeline.py) ----
STATUS_BUFFS = [("MED", "MEDITATION", "atk"), ("MG", "MAGIC_GUARD", "atk"), ("INF", "INFINITY", "ramp")]
INFINITY_RAMP = dict(p0=15, p1=25, ramp_t=10, dur0=15)     # Infinity: +15% -> +25% Final Damage over 10 s of its 15 s
# (group id, row key whose cooldown gives the cast spacing, [(row key, type, window row key or None, unlock-gate row key or None, weight row key)])
STATUS_GROUPS = [
    ("BREATH", "POISON_BREATH", [("POISON_BREATH", "burst", None, None, "POISON_BREATH")]),
    ("MIST", "POISON_MIST_BURST", [
        ("POISON_MIST_BURST", "burst", None, None, "POISON_MIST_BURST"),
        ("POISON_MIST_DOT", "dot", "POISON_MIST_DOT", None, "POISON_MIST_DOT"),
        ("MIST_ERUPTION", "end", "POISON_MIST_DOT", None, "MIST_ERUPTION")]),
    ("HAZE", "FLAME_HAZE_BURST", [
        ("FLAME_HAZE_BURST", "burst", None, None, "FLAME_HAZE_BURST"),
        ("FLAME_HAZE_DOT", "dot", "FLAME_HAZE_DOT", None, "FLAME_HAZE_DOT"),
        ("FLAME_HAZE_FOG", "dot", "FLAME_HAZE_FOG", "FLAME_HAZE_FOG", "FLAME_HAZE_FOG"),
        ("MIST_ERUPTION", "end", "FLAME_HAZE_FOG", "FLAME_HAZE_FOG", "MIST_ERUPTION")]),
    ("TOXIN", "CREEPING_TOXIN", [("CREEPING_TOXIN", "dot", "CREEPING_TOXIN", None, "CREEPING_TOXIN")]),
    ("METEOR", "METEOR_SHOWER_BURST", [("METEOR_SHOWER_BURST", "burst", None, None, "METEOR_SHOWER_BURST")]),
    ("IFRIT", "IFRIT", [("IFRIT", "dot", "IFRIT", None, "IFRIT")]),
]
STATUS_UNIFORM_ROWS = ["BASIC_ATTACK", "METEOR_PROC", "IGNITE", "ELEMENTAL_DRAIN"]
STATUS_CAST_PREFIX = {key: f"buff.{bid}" for bid, key, _k in STATUS_BUFFS}
for _gid, _cast, _ents in STATUS_GROUPS:
    for _e in _ents:
        STATUS_CAST_PREFIX.setdefault(_e[0], f"grp.{_gid}")
    STATUS_CAST_PREFIX[_cast] = f"grp.{_gid}"
# rows whose hits/s come from the engine's effective cast count (last DoT window / eruption truncated by the fight end)
STATUS_FS_KEYS = [e[0] for _g, _c, ents in STATUS_GROUPS for e in ents if e[1] in ("dot", "end")]
STATUS_PHI_ROWS = sorted({e[0] for _g, _c, ents in STATUS_GROUPS for e in ents})
