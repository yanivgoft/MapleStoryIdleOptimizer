"""Marksman static game data, as plain Python data (transcribed from ``src/build_marksman_workbook.py`` / ``src/verify_marksman_workbook.py``; the
builder stays the workbook's source, this module is the engine's copy - keep both in sync when a skill changes; ``tests/golden/check_marksman_fake.py``
cross-checks the tables that the builder exports and the static numbers of its SKILL_ROWS).  Level-dependent values (cooldown haste, target counts,
mastery bonuses that switch on at a level) are described here as ``(threshold, value)`` tuples / ``{level: tier value}`` chains and resolved by the
model in ``engine/classes/marksman.py``.

Base-damage numbers are in tenths of a percent (``base``); ``fidx`` is the FactorTable column; ``step`` the job tier (1-4) whose skill level
scales the skill.  ``gated`` chains are raw tier values summed over every reached level (CLAUDE.md bug 2).
"""

SKILL_NAMES = {
    "EMPOWERED_PIERCING_ARROW": "Empowered Piercing Arrow",
    "COVERING_FIRE": "Covering Fire",
    "BOLT_BURST": "Bolt Burst",
    "FROSTPREY": "Frostprey",
    "SNIPE": "Snipe",
    "ARROW_ILLUSION": "Arrow Illusion",
    "BOLT_SURPLUS": "Bolt Surplus",
}

# Result rows = the verify script's own order: Empowered Piercing Arrow first, then DAMAGE_SKILLS, Bolt Surplus last (also the order of its
# _BRANCH_PAIRS insertion, which the boss-only / normal-only sums follow)
DPS_ROW_ORDER = ["EMPOWERED_PIERCING_ARROW", "COVERING_FIRE", "BOLT_BURST", "FROSTPREY", "SNIPE", "ARROW_ILLUSION", "BOLT_SURPLUS"]

# Unlock level of every row that has a threshold (rows not listed - Nimble Feet - are unlocked from the start)
UNLOCK_LEVEL = {
    "EMPOWERED_PIERCING_ARROW": 100,
    "FINAL_ATTACK_CROSSBOW_HELPER": 50,
    "ADVANCED_FINAL_ATTACK_HELPER": 105,
    "COVERING_FIRE": 35,
    "BOLT_BURST": 63,
    "FROSTPREY": 69,
    "MAPLE_HERO_HELPER": 100,
    "SNIPE": 103,
    "BOLT_SURPLUS": 107,
    "ARROW_ILLUSION": 110,
    "BLINK_BOLT": 60,
    "MARKSMANSHIP_BASE": 74,
    "MARKSMANSHIP_COND": 74,
    "ILLUSION_STEP": 117,
    "SHARP_EYES": 115,
    "MORTAL_BLOW": 72,
    "CRITICAL_SHOT": 15,
    "ARCHER_MASTERY": 10,
    "CROSSBOW_ACCELERATION": 33,
    "PHYSICAL_TRAINING": 38,
    "CROSSBOW_MASTERY": 43,
    "RECKLESS_HUNT_CROSSBOW": 75,
    "LAST_MAN_STANDING_FD": 125,
    "LAST_MAN_STANDING_COND": 125,
    "CROSSBOW_EXPERT_SKILL": 120,
    "CROSSBOW_EXPERT_MAXDMG": 120,
    "SOUL_ARROW_CROSSBOW_ATK": 45,
}

# Maple Hero (Lv.100): each skill's share relative to the 25-base reference (the builder writes them as ratios of 25)
MAPLE_HERO_RATIOS = {
    "BOLT_BURST": 25 / 25,
    "FROSTPREY": 30 / 25,
    "COVERING_FIRE": 100 / 25,
}
MAPLE_HERO = dict(base=250, fidx=23, step=4)

# ---- Empowered Piercing Arrow (basic attack) ----
EPA_BASE = 290                                                              # tenths of %, factor index 21, 4th job
EPA_HITS = (5, 136, 6)                                                      # 5 hits, 6 from level 136
EPA_MASTERY = {102: 10, 106: 11, 116: 12, 120: 13, 128: 14, 132: 15}        # Damage mastery chain (raw tiers)
EPA_BOSS_MASTERY = {111: 10, 124: 10}                                       # Boss Damage mastery chain
# Final Attack: Crossbow + Advanced Final Attack folded into its coefficient: FA% / 100 x (1 + AFA% / 100) x 25
FINAL_ATTACK_CROSSBOW = dict(base=350, fidx=21, step=2, gated={54: 50})
ADVANCED_FINAL_ATTACK = dict(base=5000, fidx=21, step=4, gated={113: 100})
EPA_FINAL_ATTACK_SHARE = 25

# ---- Attack% bucket: Marksmanship (base + conditional) + Illusion Step + Blink Bolt (unconditional) ----
MARKSMANSHIP = dict(base=100, fidx=22, step=3)
ILLUSION_STEP = dict(base=150, fidx=22, step=4, boost=(118, 1.375), duration=(15, 118, 24), cooldown=24)     # x1.375 and 24 s from Lv118
BLINK_BOLT = dict(base=250, fidx=22, step=3)

# ---- Sharp Eyes / Mortal Blow / Last Man Standing / Nimble Feet ----
SHARP_EYES = dict(base=400, fidx=21, step=4, duration=(18, 126, 27), cooldown=35)    # Crit Damage; 18 s, 27 s from Lv126
MORTAL_BLOW = dict(base=120, fidx=22, step=3)                                        # Final Damage, always on
LAST_MAN_STANDING_COND = dict(base=50, fidx=22, step=4)                              # Final Damage, 1-enemy conditional half (boss / PvP)
NIMBLE_FEET = dict(base=150, fidx=0, step=1, duration=15, cooldown=60)               # Attack Speed % (non-scaling)

# ---- Bolt Surplus: 15% proc off every Empowered Piercing Arrow and Snipe attack ----
BOLT_SURPLUS = dict(base=7500, fidx=21, step=4, gated={122: 50}, chance=0.15, hits=(2, 138, 1), targets=(3, 138, 2))   # (base, level, added from that level)

# ---- damage rows (the verify script's DAMAGE_SKILLS dict order; summation order matters bit-for-bit; Bolt Surplus is handled separately) ----
# cooldown (s) [+ haste (level, multiplier)], hits, ICD / window (DoT rows), base damage (tenths of %), factor index, skill mastery chain,
# boss / normal mastery % (``mastery_normal`` may be ``(level, value)``), normal-monster targets [+ extra_targets: list of (level, n)],
# ``fold`` = (level, base, fidx, step) of an additive fold-in (Snipe's Lv134 fold of the 570% line).
DAMAGE_SKILLS = {
    "COVERING_FIRE": dict(step=1, cooldown=19, hits=3, base=2500, fidx=12, mastery={39: 50}, mastery_boss=0, mastery_normal=0,
                          costs_action=True, targets=1, extra_targets=[]),
    "BOLT_BURST": dict(step=3, cooldown=21, hits=3, base=4500, fidx=12, mastery={68: 50}, mastery_boss=0, mastery_normal=0,
                       costs_action=True, targets=10, extra_targets=[]),
    "FROSTPREY": dict(step=3, cooldown=60, haste=(104, 0.6), hits=1, icd=1.5, window=30, base=3000, fidx=12, mastery={82: 50}, mastery_boss=0,
                      mastery_normal=(94, 100), costs_action=True, targets=3, extra_targets=[(78, 2)]),
    "SNIPE": dict(step=4, cooldown=12, hits=1, base=38000, fidx=12, mastery={108: 50}, fold=(134, 57000, 12, 4), mastery_boss=0,
                  mastery_normal=0, costs_action=True, targets=1, extra_targets=[]),
    "ARROW_ILLUSION": dict(step=4, cooldown=45, hits=1, icd=1.5, window=25, base=14000, fidx=12, mastery={130: 50}, mastery_boss=0,
                           mastery_normal=0, costs_action=True, targets=10, extra_targets=[]),
}

# Action-costing rows in the verify script's COST_ACTION_ROWS order.  A key in DAMAGE_SKILLS reads its resolved cooldown; the buffs have their own.
COST_ACTION_ORDER = ["COVERING_FIRE", "BOLT_BURST", "FROSTPREY", "SNIPE", "ARROW_ILLUSION", "SHARP_EYES", "NIMBLE_FEET"]
BUFF_COOLDOWNS = {"SHARP_EYES": 35, "NIMBLE_FEET": 60}
BUFF_KEYS_STARTUP = ["SHARP_EYES", "NIMBLE_FEET"]            # actively cast buffs: startup delay / their own cast count
STARTUP_BUFFS = ["SHARP_EYES", "NIMBLE_FEET"]                # (Illusion Step costs no action, so it never counts)
CDR_EXEMPT = []                                              # no rate-surrogate cooldown in this kit

# ---- the player's own stuns (game tables): Covering Fire 1 s / 19 s cooldown from the Lv49 mastery on, Bolt Burst 1.5 s / 21 s from the Lv98 mastery on,
# Frostprey a PERIODIC freeze (10% chance, 1 s, every 1.5 s tick, 30 s window, cooldown 60 s / x0.6 from Lv104).  Cast on cooldown from the start.
# ``cd`` = base cooldown, ``cd_haste`` = (level, multiplier) like DAMAGE_SKILLS' ``haste``.
PLAYER_STUN = [
    dict(id="COVER", key="COVERING_FIRE", typ="cast", dur=1.0, p=1.0, cd=19, min_level=49, tick=1.0, win=0.0),
    dict(id="BBURST", key="BOLT_BURST", typ="cast", dur=1.5, p=1.0, cd=21, min_level=98, tick=1.0, win=0.0),
    dict(id="FROST", key="FROSTPREY", typ="periodic", dur=1.0, p=0.1, cd=60, cd_haste=(104, 0.6), min_level=0, tick=1.5, win=30.0),
]

# ---- Status Effect Damage / KO timeline engine spec (src/status_timeline.py) ----
# Illusion Step is the only engine-timed buff (Marksmanship / Blink Bolt are the engine's constant Attack% A0; Sharp Eyes / Nimble Feet / Mortal Blow keep
# their averaged formulas).
STATUS_BUFFS = [("IS", "ILLUSION_STEP", "atk")]
# (group id, row key whose cooldown gives the cast spacing, [(row key, type, window row key or None, unlock-gate row key or None, weight row key)])
STATUS_GROUPS = [
    ("COVER", "COVERING_FIRE", [("COVERING_FIRE", "burst", None, None, "COVERING_FIRE")]),
    ("BBURST", "BOLT_BURST", [("BOLT_BURST", "burst", None, None, "BOLT_BURST")]),
    ("FROST", "FROSTPREY", [("FROSTPREY", "dot", "FROSTPREY", None, "FROSTPREY")]),
    ("SNIPE", "SNIPE", [("SNIPE", "burst", None, None, "SNIPE")]),
    ("ILLU", "ARROW_ILLUSION", [("ARROW_ILLUSION", "dot", "ARROW_ILLUSION", None, "ARROW_ILLUSION")]),
]
# rows spread uniformly over the fight (the order is the verify script's summation order of the uniform boss total)
STATUS_UNIFORM_ROWS = ["EMPOWERED_PIERCING_ARROW", "BOLT_SURPLUS"]
STATUS_CAST_PREFIX = {key: f"buff.{bid}" for bid, key, _k in STATUS_BUFFS}
for _gid, _cast, _ents in STATUS_GROUPS:
    for _e in _ents:
        STATUS_CAST_PREFIX.setdefault(_e[0], f"grp.{_gid}")
    STATUS_CAST_PREFIX[_cast] = f"grp.{_gid}"
# rows whose hits/s come from the engine's effective cast count (last DoT window truncated by the fight end)
STATUS_FS_KEYS = [e[0] for _g, _c, ents in STATUS_GROUPS for e in ents if e[1] in ("dot", "end")]
STATUS_PHI_ROWS = sorted({e[0] for _g, _c, ents in STATUS_GROUPS for e in ents})
