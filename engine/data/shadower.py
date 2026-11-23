"""Shadower static game data, as plain Python data (transcribed from ``src/build_shadower_workbook.py`` / ``src/verify_shadower_workbook.py``; the
builder stays the workbook's source, this module is the engine's copy - keep both in sync when a skill changes; ``tests/golden/check_shadower_fake.py``
cross-checks the tables that the builder exports and the static numbers of its SKILL_ROWS).  Level-dependent values (cooldown haste, hit counts, ICD,
mastery bonuses that switch on at a level) are described here as ``(threshold, value)`` tuples / ``{level: tier value}`` chains and resolved by the
model in ``engine/classes/shadower.py``.

Base-damage numbers are in tenths of a percent (``base``); ``fidx`` is the FactorTable column; ``step`` the job tier (1-4) whose skill level
scales the skill.  ``gated`` / ``mastery`` chains are raw tier values summed over every reached level (CLAUDE.md bug 2).
"""

SKILL_NAMES = {
    "CRUEL_STAB": "Cruel Stab",
    "PHASE_DASH": "Phase Dash",
    "MESO_EXPLOSION": "Meso Explosion",
    "BLOOD_MONEY": "Blood Money",
    "DARK_FLARE": "Dark Flare",
    "VENOM": "Venom",
    "ASSASSINATE": "Assassinate",
    "SUDDEN_RAID_BURST": "Sudden Raid (burst)",
    "SUDDEN_RAID_DOT": "Sudden Raid (DoT)",
    "TOXIC_VENOM": "Toxic Venom",
    "SHADOW_SHIFTER": "Shadow Shifter (counterattack)",
}

# Result rows = the verify script's skill_dps order (also the order of its _BRANCH_PAIRS insertion, which the boss-only / normal-only sums follow)
DPS_ROW_ORDER = ["CRUEL_STAB", "PHASE_DASH", "MESO_EXPLOSION", "BLOOD_MONEY", "DARK_FLARE", "VENOM", "ASSASSINATE", "SUDDEN_RAID_BURST",
                 "SUDDEN_RAID_DOT", "TOXIC_VENOM", "SHADOW_SHIFTER"]

# Unlock level of every row that has a threshold (rows not listed - Nimble Feet - are unlocked from the start)
UNLOCK_LEVEL = {
    "CRUEL_STAB": 100,
    "STEAL": 35,
    "MESO_MASTERY": 75,
    "MESO_EXPLOSION": 66,
    "PHASE_DASH": 63,
    "DARK_FLARE": 69,
    "SHADOW_PARTNER": 60,
    "VENOM": 72,
    "TOXIC_VENOM": 117,
    "INTO_DARKNESS": 74,
    "ASSASSINATE": 103,
    "SUDDEN_RAID_BURST": 105,
    "SUDDEN_RAID_DOT": 105,
    "BLOOD_MONEY": 107,
    "SMOKESCREEN": 110,
    "SHADOW_SHIFTER": 115,
    "SHADOW_SHIFTER_SELF_ATK": 115,
    "MAPLE_HERO_SHADOWER": 100,
    "DARK_SIGHT_CRIT": 15,
    "DARK_SIGHT_ATK": 15,
    "AGILE_DAGGERS": 33,
    "CHANNEL_KARMA": 40,
    "DAGGER_MASTERY": 43,
    "CRITICAL_EDGE_RATE": 50,
    "CRITICAL_EDGE_DMG": 50,
    "PHYSICAL_TRAINING": 38,
    "DAGGER_EXPERT_SKILL": 120,
    "DAGGER_EXPERT_MAXDMG": 120,
    "SHADOWER_INSTINCT": 125,
}

# Maple Hero (Shadower): each target row's static share against Dark Flare's own 1x (the builder writes them as ratios of 15)
MAPLE_HERO_SHADOWER_RATIOS = {
    "DARK_FLARE": 15 / 15,
    "VENOM": 50 / 15,
    "SHADOW_PARTNER": 50 / 15,
    "PHASE_DASH": 40 / 15,
}
MAPLE_HERO = dict(base=150, fidx=23, step=4)

# ---- Cruel Stab (basic attack): 290 tenths-of-% x factor 21, 4th job ----
CRUEL_STAB_BASE = 290
CRUEL_STAB_HITS = (5, 136, 6)                                                    # 5 hits, 6 from level 136
CRUEL_STAB_MASTERY = {102: 10, 106: 11, 116: 12, 120: 13, 128: 14, 132: 15}      # Damage mastery chain (raw tiers)
CRUEL_STAB_BOSS_MASTERY = {111: 10, 124: 10}                                     # Boss Damage mastery chain
CRUEL_STAB_TARGET_BASE = 6                                                       # + Basic Attack Target Increase

# ---- buffs (cast rows of the Skills sheet).  ``duration`` = number, or (value, level, value from that level); ``scales`` False = non-scaling ----
DARK_SIGHT_DURATION = (8, 24, 12)
BUFFS = {
    "NIMBLE_FEET": dict(job_step=1, cooldown=60, duration=15, base=150, fidx=0, scales=False, costs_action=True, actions_per_cast=1),
    "DARK_SIGHT_CRIT": dict(job_step=1, cooldown=25, duration=DARK_SIGHT_DURATION, base=60, fidx=21, scales=True, costs_action=False, actions_per_cast=1),
    "DARK_SIGHT_ATK": dict(job_step=1, cooldown=25, duration=DARK_SIGHT_DURATION, base=100, fidx=21, scales=True, costs_action=True, actions_per_cast=2),
    "INTO_DARKNESS": dict(job_step=3, cooldown=40, duration=13, base=200, fidx=21, scales=True, costs_action=True, actions_per_cast=1),
    "SMOKESCREEN": dict(job_step=4, cooldown=45, duration=20, base=130, fidx=22, scales=True, costs_action=True, actions_per_cast=1),
}
SMOKESCREEN_CRIT_DAMAGE = (113, 30)       # Lv113 mastery: allies' Critical Damage +30 (x Smokescreen's uptime)

# ---- Steal / Meso Mastery / Shadow Partner (averaged) ----
STEAL = dict(base=50, fidx=22, step=2, stacks=3)                                # Attack% x 3 stacks, always on
MESO_MASTERY = dict(attack=25.0, rate=0.75, window=5)                           # Attack +25% for 5 s per Meso generation: 25 x (1 - exp(-0.75 x APS x 5))
MESO_CHANCE = (0.5, 75, 0.75)                                                   # Meso generation chance (base, level, value from that level)
SHADOW_PARTNER = dict(base=600, fidx=21, step=3, gated={68: 100}, proc=25)      # 25% proc: mult = 1 + (pct x 1.0 x 25 / 100) / 100

# ---- Meso Explosion / Blood Money stack models and Assassinate's Murderous Intent ----
MESO_STACK_MAX = 10
BLOOD_MONEY_STACK_MAX = 5
BLOOD_MONEY_CHANCE = 0.5
BLOOD_MONEY_TARGET_MULT = [(138, 3), (122, 2)]            # checked in order; 1 below Lv122
MESO_EXPLOSION_COOLDOWN = 11
ASSASSINATE = dict(base=14000, fidx=12, step=4, fold=(134, 50), finisher_base=30000, finisher_fidx=12, finisher_step=4, finisher_share=0.5,
                   cooldown=13, murderous_intent_trigger=2)

# ---- damage rows (the verify script's DAMAGE_SKILLS dict order; summation order matters bit-for-bit) ----
# ``cooldown`` / ``hits`` / ``icd``: a number or (base, level, value from that level); ``mastery`` = skill damage mastery chain (MULTIPLIES the skill);
# ``targets`` = number | the string naming a model-computed average.  Assassinate's coefficient is composed by the model (ASSASSINATE above).
DAMAGE_SKILLS = {
    "PHASE_DASH": dict(step=3, cooldown=23, hits=2, base=4500, fidx=12, mastery={73: 80}, costs_action=True, targets=9),
    "MESO_EXPLOSION": dict(step=3, cooldown=11, hits=3, base=2700, fidx=12, mastery={90: 100}, costs_action=True, targets="meso_stack_avg"),
    "BLOOD_MONEY": dict(step=4, cooldown=11, hits=3, base=36000, fidx=12, mastery={122: 50, 138: 50}, costs_action=False, targets="blood_money"),
    "DARK_FLARE": dict(step=3, cooldown=(45, 94, 45 * 0.7), hits=(2, 78, 3), icd=(2, 104, 2 * 0.75), window=20, base=3300, fidx=12, mastery={},
                       costs_action=True, targets=8),
    "VENOM": dict(step=3, cooldown=1, hits=1, base=450, fidx=21, mastery={}, costs_action=False, targets=1),
    "ASSASSINATE": dict(step=4, cooldown=13, hits=2, base=None, fidx=None, mastery=None, costs_action=True, targets=1),
    "SUDDEN_RAID_BURST": dict(step=4, cooldown=19, hits=3, base=14000, fidx=12, mastery={126: 50}, costs_action=True, targets=8),
    "SUDDEN_RAID_DOT": dict(step=4, cooldown=19, hits=1, icd=1, window=5, base=3600, fidx=12, mastery={}, costs_action=False, targets=8),
}
CDR_EXEMPT = ["VENOM"]                                      # rate-surrogate cooldown

# ---- Toxic Venom: 20% proc off every row below (no ICD); Shadow Shifter: incoming_hit_rate x 20% counterattack ----
TOXIC_VENOM = dict(base=6000, fidx=21, step=4, gated={130: 100}, chance=0.2)
# The verify script sums the trigger rates over a Python ``set`` literal (ulp-level noise depending on PYTHONHASHSEED).  The golden is generated with
# PYTHONHASHSEED=0; the engine fixes that order (the iteration order of the set under seed 0).
TRIGGERS_TOXIC_VENOM = ["ASSASSINATE", "CRUEL_STAB", "MESO_EXPLOSION", "PHASE_DASH", "BLOOD_MONEY", "SUDDEN_RAID_DOT", "SUDDEN_RAID_BURST", "DARK_FLARE"]
SHADOW_SHIFTER = dict(base=25000, fidx=21, step=4, chance=0.2)

# Global bonuses
MONSTER_DMG_BONUS = (82, 15)              # Venom's Weaken mastery: +15% damage taken from Lv82 (global, always on)

# ---- the player's own stun (game table): Phase Dash 2 s, cooldown 23 s, no Reuse mastery; cast on cooldown from the start ----
PLAYER_STUN = [
    dict(id="DASH", key="PHASE_DASH", typ="cast", dur=2.0, p=1.0, cd=23, min_level=0, tick=1.0, win=0.0),
]

# ---- Status Effect Damage / KO timeline engine spec (src/status_timeline.py) ----
# Dark Sight (Attack) = an Attack% buff ("atk": additive bucket with Steal / Meso Mastery); Into Darkness and Smokescreen = two separate multiplicative Final
# Damage buffs ("ramp"), Smokescreen's effect carrying the mean-field cross term (1 + Into Darkness's steady-state average).
STATUS_BUFFS = [("DS", "DARK_SIGHT_ATK", "atk"), ("ID", "INTO_DARKNESS", "ramp"), ("SS", "SMOKESCREEN", "ramp")]
# (group id, row key whose cooldown gives the cast spacing, [(row key, type, window row key or None, unlock-gate row key or None, weight row key)])
STATUS_GROUPS = [
    ("DASH", "PHASE_DASH", [("PHASE_DASH", "burst", None, None, "PHASE_DASH")]),
    ("MESO", "MESO_EXPLOSION", [
        ("MESO_EXPLOSION", "burst", None, None, "MESO_EXPLOSION"),
        ("BLOOD_MONEY", "burst", None, "BLOOD_MONEY", "BLOOD_MONEY")]),
    ("FLARE", "DARK_FLARE", [("DARK_FLARE", "dot", "DARK_FLARE", None, "DARK_FLARE")]),
    ("ASSN", "ASSASSINATE", [("ASSASSINATE", "burst", None, None, "ASSASSINATE")]),
    ("RAID", "SUDDEN_RAID_BURST", [
        ("SUDDEN_RAID_BURST", "burst", None, None, "SUDDEN_RAID_BURST"),
        ("SUDDEN_RAID_DOT", "dot", "SUDDEN_RAID_DOT", None, "SUDDEN_RAID_DOT")]),
]
# rows spread uniformly over the fight (the order is the verify script's summation order of the uniform boss total)
STATUS_UNIFORM_ROWS = ["CRUEL_STAB", "VENOM", "TOXIC_VENOM", "SHADOW_SHIFTER"]
STATUS_CAST_PREFIX = {key: f"buff.{bid}" for bid, key, _k in STATUS_BUFFS}
STATUS_CAST_PREFIX["DARK_SIGHT_CRIT"] = "buff.DS"          # passenger row: same cast as Dark Sight (Attack)
for _gid, _cast, _ents in STATUS_GROUPS:
    for _e in _ents:
        STATUS_CAST_PREFIX.setdefault(_e[0], f"grp.{_gid}")
    STATUS_CAST_PREFIX[_cast] = f"grp.{_gid}"
# rows whose hits/s come from the engine's effective cast count (last DoT window truncated by the fight end)
STATUS_FS_KEYS = [e[0] for _g, _c, ents in STATUS_GROUPS for e in ents if e[1] in ("dot", "end")]
STATUS_PHI_ROWS = sorted({e[0] for _g, _c, ents in STATUS_GROUPS for e in ents})
