"""Night Lord static game data, as plain Python data (transcribed from ``src/verify_night_lord_workbook.py`` and the builder
``src/build_night_lord_workbook.py``; the builder stays the workbook's source, this module is the engine's copy - keep both in sync when a skill
changes; ``tests/golden/check_night_lord_fake.py`` cross-checks the tables that the builder exports and every static number of its SKILL_ROWS).

Level-dependent values (cooldown / ICD haste, hit counts, target counts, masteries that switch on at a level) are described as ``(default, level,
value-from-that-level)`` tuples and ``{level: tier value}`` chains and resolved by the model in ``engine/classes/night_lord.py``.

Base-damage numbers are in tenths of a percent (``base``); ``fidx`` is the FactorTable column; ``step`` the job tier (1-4) whose skill level scales the
skill.  ``mastery`` chains are raw tier values summed over every reached level (CLAUDE.md bug 2).
"""

SKILL_NAMES = {
    "SHOWDOWN": "Showdown",
    "GUST_CHARM": "Gust Charm",
    "MARK_OF_ASSASSIN": "Assassin's Mark",
    "TRIPLE_THROW": "Triple Throw",
    "DARK_FLARE": "Dark Flare",
    "VENOM": "Venom",
    "QUAD_STAR": "Quad Star",
    "SUDDEN_RAID_BURST": "Sudden Raid (burst)",
    "SUDDEN_RAID_DOT": "Sudden Raid (DoT)",
    "TOXIC_VENOM": "Toxic Venom",
    "SHADOW_SHIFTER": "Shadow Shifter (counterattack)",
}

# Result rows = the verify script's skill_dps order (also the order of its _BRANCH_PAIRS insertion, which the boss-only / normal-only sums follow):
# Showdown first, DAMAGE_SKILLS in dict order, then Toxic Venom and Shadow Shifter.  (Shadow Partner, Night Lord's Mark, every buff / Alchemic
# Adrenaline / passive row contribute 0 DPS directly: they only feed multipliers.)
DPS_ROW_ORDER = ["SHOWDOWN", "GUST_CHARM", "MARK_OF_ASSASSIN", "TRIPLE_THROW", "DARK_FLARE", "VENOM", "QUAD_STAR", "SUDDEN_RAID_BURST",
                 "SUDDEN_RAID_DOT", "TOXIC_VENOM", "SHADOW_SHIFTER"]

# Unlock level of every row that has a threshold (Nimble Feet - not listed - is unlocked from the start)
UNLOCK_LEVEL = {
    "SHOWDOWN": 100,
    "GUST_CHARM": 35,
    "MARK_OF_ASSASSIN": 43,
    "TRIPLE_THROW": 63,
    "ADRENALIN_FD": 66,
    "ADRENALIN_AS": 66,
    "DARK_FLARE": 69,
    "VENOM": 74,
    "TOXIC_VENOM": 117,
    "SHADOW_PARTNER": 60,
    "QUAD_STAR": 103,
    "SUDDEN_RAID_BURST": 105,
    "SUDDEN_RAID_DOT": 105,
    "FRAILTY_CURSE_SELF_FD": 110,
    "FRAILTY_CURSE_DEBUFF": 110,
    "SHADOW_SHIFTER": 115,
    "SHADOW_SHIFTER_SELF_ATK": 115,
    "DARK_SIGHT_CRIT": 15,
    "DARK_SIGHT_ATK": 15,
    "AGILE_CLAWS": 33,
    "PHYSICAL_TRAINING": 38,
    "CLAW_MASTERY": 40,
    "CRITICAL_THROW_RATE": 45,
    "CRITICAL_THROW_DMG": 45,
    "ENVELOPING_DARKNESS": 72,
    "EXPERT_THROWING_STAR_HANDLING": 75,
    "CLAW_EXPERT": 120,
    "DARK_HARMONY": 125,
    "NIGHT_LORDS_MARK": 107,
}

# ---- Showdown (basic attack): 290% x F21, 5 lines (6 from Lv136), 6 + Basic Attack Target Increase targets ----
SHOWDOWN_BASE = 290                                                       # tenths of %, factor index 21, 4th job
SHOWDOWN_HITS = (5, 136, 6)
SHOWDOWN_MASTERY = {102: 10, 106: 11, 116: 12, 120: 13, 128: 14, 132: 15}   # Damage mastery chain (raw tiers)
SHOWDOWN_MASTERY_BOSS = {111: 10, 124: 10}                                  # Boss Damage mastery chain

# ---- damage rows after Showdown (the verify script's DAMAGE_SKILLS dict order; summation order matters bit-for-bit) ----
# cooldown / hits / icd / mastery_boss / mastery_normal / targets are either a number or ``(default, level, value from that level)``; ``haste`` /
# ``icd_haste`` = (level, multiplier) applied to the cooldown / ICD from that level on (Dark Flare Lv94 / Lv104, Quad Star Lv108);
# ``final`` = (level, base, fidx, step): Final Damage % of another passive (Night Lord's Mark) from that level on.
DAMAGE_SKILLS = {
    "GUST_CHARM": dict(step=2, cooldown=24, hits=1, base=4000, fidx=12, mastery={39: 80}, mastery_boss=0.0, mastery_normal=0.0, costs_action=True,
                       targets=8),
    "MARK_OF_ASSASSIN": dict(step=2, cooldown=(2.5, 138, 2.0), hits=1, base=1900, fidx=21, mastery={44: 80}, mastery_boss=(0.0, 122, 8.0),
                             mastery_normal=(0.0, 122, 8.0), final=(107, 3000, 21, 4), costs_action=False, targets=(7, 107, 10)),
    "TRIPLE_THROW": dict(step=3, cooldown=13, hits=3, base=3600, fidx=12, mastery={73: 100}, mastery_boss=0.0, mastery_normal=0.0, costs_action=True,
                         targets=1),
    "DARK_FLARE": dict(step=3, cooldown=45, haste=(94, 0.7), hits=(2, 78, 3), icd=2, icd_haste=(104, 0.75), window=20, base=3300, fidx=12, mastery={},
                       mastery_boss=0.0, mastery_normal=0.0, costs_action=True, targets=8),
    "VENOM": dict(step=3, cooldown=1, hits=1, base=450, fidx=21, mastery={}, mastery_boss=0.0, mastery_normal=0.0, costs_action=False, targets=1),
    "QUAD_STAR": dict(step=4, cooldown=10, haste=(108, 0.7), hits=4, base=11500, fidx=12, mastery={134: 50}, mastery_boss=0.0, mastery_normal=0.0,
                      costs_action=True, targets=1),
    "SUDDEN_RAID_BURST": dict(step=4, cooldown=19, hits=3, base=14000, fidx=12, mastery={126: 50}, mastery_boss=0.0, mastery_normal=0.0,
                              costs_action=True, targets=8),
    "SUDDEN_RAID_DOT": dict(step=4, cooldown=19, hits=1, icd=1, window=5, base=3600, fidx=12, mastery={}, mastery_boss=0.0, mastery_normal=0.0,
                            costs_action=False, targets=8),     # shares Sudden Raid (burst)'s cooldown
}

# ---- procs / counterattacks handled outside the loop ----
TOXIC_VENOM = dict(base=6000, fidx=21, step=4, mastery={130: 100}, chance=0.2)        # no ICD: 20% per attack per enemy hit
SHADOW_SHIFTER = dict(base=25000, fidx=21, step=4, chance=0.2)                        # counterattack: incoming_hit_rate x 20%
SHADOW_PARTNER = dict(base=600, fidx=21, step=3, mastery={68: 100}, share=25)         # average multiplier only (the clone mirrors the player's attacks)
# Maple Hero (NL) targets per row (tenths of %, factor index 23, 4th-job level); Showdown and the rows not listed use none
MAPLE_FACTOR_IDX = 23
MAPLE_TARGETS = {"DARK_FLARE": 150, "VENOM": 500, "SHADOW_PARTNER": 500, "GUST_CHARM": 1300}
# Rows whose attacks can roll Toxic Venom.  The verify script holds them in a Python ``set`` and sums their hit rates in set-iteration order, which
# depends on PYTHONHASHSEED (ulp-level noise in the trigger rate).  The engine fixes the order to the one the set has under PYTHONHASHSEED=0 (the seed
# the golden file is generated with), so ``compute`` no longer depends on the hash seed.
TRIGGERS_TOXIC_VENOM = ["MARK_OF_ASSASSIN", "SHOWDOWN", "GUST_CHARM", "QUAD_STAR", "SUDDEN_RAID_DOT", "TRIPLE_THROW", "SUDDEN_RAID_BURST", "DARK_FLARE"]

# ---- buffs (the verify script's BUFFS dict order: it is the order of the cast-rate / startup sums) ----
# duration: a number or (default, level, value from that level); ``scales`` False = ignores the factor table
BUFFS = {
    "NIMBLE_FEET": dict(step=1, cooldown=60, duration=15, base=150, fidx=0, scales=False, target="ATTACK_SPEED", costs_action=True, actions_per_cast=1),
    "DARK_SIGHT_CRIT": dict(step=1, cooldown=25, duration=(8, 24, 12), base=60, fidx=21, scales=True, target="CRIT_RATE", costs_action=False,
                            actions_per_cast=1),
    "DARK_SIGHT_ATK": dict(step=1, cooldown=25, duration=(8, 24, 12), base=100, fidx=21, scales=True, target="ATTACK", costs_action=True,
                           actions_per_cast=2),
    "FRAILTY_CURSE_SELF_FD": dict(step=4, cooldown=45, duration=20, base=130, fidx=22, scales=True, target="FINAL_DAMAGE", costs_action=True,
                                  actions_per_cast=1),
    "FRAILTY_CURSE_DEBUFF": dict(step=4, cooldown=45, duration=20, base=180, fidx=21, scales=True, target="MONSTER_DMG", costs_action=False,
                                 actions_per_cast=1),
}
# Alchemic Adrenaline: an action-rate-driven proc (5 attacks to trigger), averaged: duration 10 s (15 s from Lv90), Final Damage + Attack Speed
ADRENALIN = {
    "ADRENALIN_FD": dict(step=3, base=150, fidx=22, scales=True, target="FINAL_DAMAGE", gated={90: 6}),
    "ADRENALIN_AS": dict(step=3, base=80, fidx=22, scales=True, target="ATTACK_SPEED"),
}
ADRENALIN_DURATION = (10, 90, 15)
ADRENALIN_ACTIVATIONS = 5
# permanent passive rows: baked into the user's Inputs (no DPS term of their own; kept only so the Skills sheet / tests can list them)
PASSIVE_MULT = {
    "AGILE_CLAWS": dict(step=2, base=50, fidx=22),
    "PHYSICAL_TRAINING": dict(step=2, base=100, fidx=22),
    "CLAW_MASTERY": dict(step=2, base=150, fidx=22),
    "CRITICAL_THROW_RATE": dict(step=2, base=60, fidx=22),
    "CRITICAL_THROW_DMG": dict(step=2, base=100, fidx=22),
    "ENVELOPING_DARKNESS": dict(step=3, base=180, fidx=22),
    "EXPERT_THROWING_STAR_HANDLING": dict(step=3, base=180, fidx=22),
    "CLAW_EXPERT": dict(step=4, base=150, fidx=22),
    "DARK_HARMONY": dict(step=4, base=120, fidx=22),
    "SHADOW_SHIFTER_SELF_ATK": dict(step=4, base=100, fidx=22),
}
NIGHT_LORDS_MARK = dict(step=4, base=3000, fidx=21, level=107)       # Final Damage of Assassin's Mark from Lv107
CRITICAL_THROW_LV47 = (47, 8.0)         # +8 %p Crit Rate from Lv47 (always on)
VENOM_WEAKEN = (82, 15.0)               # Venom's Weaken: +15 %p enemy damage taken from Lv82 (always on)
FRAILTY_CRIT_DAMAGE_TAKEN = (111, 30.0)  # Lv111 mastery: +30% Critical Damage Taken x the Frailty Curse debuff uptime

# ---- the player's own stun (game table): Gust Charm stuns 8 targets for 2 s, cooldown 24 s, no Reuse mastery; cast on cooldown from the start ----
PLAYER_STUN = [
    dict(id="GUST", key="GUST_CHARM", typ="cast", dur=2.0, p=1.0, cd=24, min_level=0, tick=1.0, win=0.0),
]

# ---- Status Effect Damage / KO timeline engine spec (src/status_timeline.py) ----
# Dark Sight (Attack) (an Attack% buff in the additive bucket) and Frailty Curse (self Final Damage, ramp profile) are the engine-timed buffs; the
# Dark Sight Crit Rate / Frailty Curse debuff rows follow their cast counts.
STATUS_BUFFS = [("DS", "DARK_SIGHT_ATK", "atk"), ("FC", "FRAILTY_CURSE_SELF_FD", "ramp")]
# (group id, row key whose cooldown gives the cast spacing, [(row key, type, window row key or None, unlock-gate row key or None, weight row key)])
STATUS_GROUPS = [
    ("GUST", "GUST_CHARM", [("GUST_CHARM", "burst", None, None, "GUST_CHARM")]),
    ("TRIPLE", "TRIPLE_THROW", [("TRIPLE_THROW", "burst", None, None, "TRIPLE_THROW")]),
    ("FLARE", "DARK_FLARE", [("DARK_FLARE", "dot", "DARK_FLARE", None, "DARK_FLARE")]),
    ("QUAD", "QUAD_STAR", [("QUAD_STAR", "burst", None, None, "QUAD_STAR")]),
    ("RAID", "SUDDEN_RAID_BURST", [
        ("SUDDEN_RAID_BURST", "burst", None, None, "SUDDEN_RAID_BURST"),
        ("SUDDEN_RAID_DOT", "dot", "SUDDEN_RAID_DOT", None, "SUDDEN_RAID_DOT")]),
]
# rows spread uniformly over the fight (the order is the verify script's summation order of the uniform boss total)
STATUS_UNIFORM_ROWS = ["SHOWDOWN", "MARK_OF_ASSASSIN", "VENOM", "TOXIC_VENOM", "SHADOW_SHIFTER"]
STATUS_CAST_PREFIX = {key: f"buff.{bid}" for bid, key, _k in STATUS_BUFFS}
STATUS_CAST_PREFIX["DARK_SIGHT_CRIT"] = "buff.DS"
STATUS_CAST_PREFIX["FRAILTY_CURSE_DEBUFF"] = "buff.FC"
for _gid, _cast, _ents in STATUS_GROUPS:
    for _e in _ents:
        STATUS_CAST_PREFIX.setdefault(_e[0], f"grp.{_gid}")
    STATUS_CAST_PREFIX[_cast] = f"grp.{_gid}"
# rows whose hits/s come from the engine's effective cast count (last DoT window truncated by the fight end)
STATUS_FS_KEYS = [e[0] for _g, _c, ents in STATUS_GROUPS for e in ents if e[1] in ("dot", "end")]
STATUS_PHI_ROWS = sorted({e[0] for _g, _c, ents in STATUS_GROUPS for e in ents})
# rows with a Cooldown(s) that is a trigger-rate surrogate (CDR must not shrink it)
CDR_EXEMPT = ["VENOM", "MARK_OF_ASSASSIN"]
