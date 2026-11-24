"""Night Walker (Cygnus Knight, LUK main / DEX sub thief) static game data - ENGINE-NATIVE: there is no workbook, builder or verify script for this class.  Every scaled
number is CONFIRMED (site table or the user's higher-level in-game readings, see ``CONFIRMED_BY_READINGS``).

Sources
* the user's LEVEL-1 in-game screenshots (``data/cygnus/night_walker_ingame.md``; fresh character, every pop-up "Lv. 1", so the shown numbers are the BASE values at factor 1.0) AND his
  higher-level readings (character level 128, pop-ups "Lv. A + B" = total skill level 151 / 219 / 279 / 322 per job tier, 2026-11-24, "Scaling readings" in the same file); both are
  reproduced by ``tests/golden/test_night_walker_displayed.py``.
* the live site table ``data/ref_maplestoryidle_info/site_job_skill_impact_all.json`` (job ``night-walker``): the real ``(ratioE3, factorIndex)`` of the damage lines, the stat
  operations (Attack / Final Damage / Attack Speed / passive values) and the unlock levels.  The same test asserts every curve marked site-confirmed here equals the site's.

Conventions follow ``engine/data/dawn_warrior.py``: base values in TENTHS of a percent (``base``; the basic attack's own constant is in percent like Hero's / Dawn's), ``fidx`` the
FactorTable column, ``step`` the job tier (1-4) whose total skill level scales the skill.

CURVES: ``CURVES`` holds (base, factor index, job step) of every number the engine scales.  ``PROVISIONAL`` is empty now: the curves the site table does not cover were resolved by the user's
readings (``CONFIRMED_BY_READINGS``).  Every judgement call is flagged in ``ROW_NOTES`` and in KNOWN_GAPS.md ("Night Walker").
"""

CLASS_ID = "night_walker"

SKILL_NAMES = {
    "QUINTUPLE_STAR": "Quintuple Star (basic attack)",
    "SHADOW_DOUBLE": "Shadow Double (clone's extra damage)",
    "SHADOW_SPARK": "Shadow Spark",
    "SHADOW_SPARK_EXPLOSION": "Shadow Spark (explosion)",
    "SHADOW_STITCH": "Shadow Stitch",
    "SHADOW_BAT": "Shadow Bat (attacks)",
    "BAT_EXPLOSION": "Bat Affinity II (first-attack explosion)",
    "MARK_OF_DARKNESS": "Mark of Darkness (Dark Elemental)",
}

# Result rows (damage rows only)
DPS_ROW_ORDER = ["QUINTUPLE_STAR", "SHADOW_DOUBLE", "SHADOW_SPARK", "SHADOW_SPARK_EXPLOSION", "SHADOW_STITCH", "SHADOW_BAT", "BAT_EXPLOSION", "MARK_OF_DARKNESS"]

# Unlock level of every row / effect that has a threshold.  Site ``requiredLevel`` (the in-game grids show no "Lv." label for Dark Elemental / Shadow Bat: unlocked for the
# screenshot character; the site says 10 / 15).  Quad Star, Lucky Seven, Triple Throw and Shadow Jump are NOT modelled; the basic attack is Quintuple Star (4th job, level 100) and
# is ABSENT below level 100 exactly like every other class's basic attack.
UNLOCK_LEVEL = {
    "QUINTUPLE_STAR": 100,
    "SHADOW_DOUBLE": 63,
    "SHADOW_SPARK": 35,
    "SHADOW_SPARK_EXPLOSION": 35,
    "SHADOW_STITCH": 105,
    "SHADOW_BAT": 15,
    "BAT_EXPLOSION": 66,                # Bat Affinity II
    "MARK_OF_DARKNESS": 10,             # Dark Elemental
    "ELEMENTAL_HARMONY": 0,
    "DARK_ELEMENTAL": 10,
    "BAT_AFFINITY": 40,
    "ADAPTIVE_DARKNESS": 50,
    "BAT_AFFINITY_II": 66,
    "DARKNESS_ASCENDING": 69,
    "ADAPTIVE_DARKNESS_II": 72,
    "SHADOW_MOMENTUM": 74,
    "CALL_OF_CYGNUS": 100,
    "DARK_OMEN": 103,
    "BAT_AFFINITY_III": 107,
    "ADAPTIVE_DARKNESS_III": 110,
    "DARK_EVASION": 115,
}

# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# CURVES: key -> (base in tenths of %, factor index or None = does not scale with the skill level, job step).  The game shows ``trunc_1dp(base x factor[idx][total level of the step])``.
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
CURVES = {
    # ---- site-confirmed (maplestoryidle.info job-skill-impact: the damage ops' ratioE3 / factorIndex, the stat ops' value / factorIndex, ModSkillStat / SetServantSkill ops) ----
    "SHADOW_SPARK": (2200, 12, 2),                    # 220 %, direct damage op, factor 12
    "SHADOW_STITCH": (28500, 12, 4),                  # 2850 % x 4 hits, 15 targets, factor 12
    "DARK_ELEMENTAL_ATTACK": (100, 21, 1),            # Attack +10 %
    "DARKNESS_ASCENDING_ATTACK": (250, 21, 3),        # Attack +25 %
    "DARK_EVASION_FD": (200, 21, 4),                  # Final Damage +20 %
    "ELEMENTAL_HARMONY_AS": (150, None, 1),           # Attack Speed +15 % (no level shown: non-scaling)
    "SHADOW_MOMENTUM_AS": (40, 22, 3),                # Attack Speed +4 % per stack ($CreatureStateCount x 40, factor 22)
    "SHADOW_DOUBLE_SHARE": (200, 22, 3),              # the clone's 20 % of the original skill's damage (SetServantSkill op, factor 22, step 3)
    "CALL_OF_CYGNUS_BAT": (1200, 23, 4),              # Final Damage 120 % on Shadow Bat (ModSkillStat 131042)
    "CALL_OF_CYGNUS_SPARK": (1500, 23, 4),            # Final Damage 150 % on Shadow Spark (ModSkillStat 132020 and 132021: both lines)
    "BAT_AFFINITY_III_FD": (1500, 21, 4),             # Final Damage +150 % on Bat Affinity II's explosion (ModSkillStat 131043, factor 21)
    "ADAPTIVE_DARKNESS_III_FD": (1500, 21, 4),        # Final Damage +150 % on Dark Elemental's Mark of Darkness (ModSkillStat 131033, factor 21)
    # ---- confirmed by the user's higher-level readings (not in the site table; see CONFIRMED_BY_READINGS) ----
    "QUINTUPLE_STAR": (2900, 21, 4),
    "SHADOW_SPARK_EXPLOSION": (3300, 12, 2),
    "SHADOW_BAT": (360, 21, 1),
    "BAT_AFFINITY": (900, 21, 2),
    "BAT_AFFINITY_II_EXPLOSION": (3000, 21, 3),
    "MARK_OF_DARKNESS": (380, 12, 1),                 # factor 12, NOT the passive-proc 21 first guessed (66.6 % at total level 151)
    "ADAPTIVE_DARKNESS": (750, 12, 2),                # factor 12 (157.1 % at total level 219)
    "ADAPTIVE_DARKNESS_II": (1450, 12, 3),            # factor 12 (347.2 % at total level 279)
}

# Nothing is provisional any more.  CONFIRMED_BY_READINGS: the curves the site table does not cover, each resolved by a higher-level in-game reading (character level 128, total skill level
# per job tier 151 / 219 / 279 / 322; the game truncates to 1 decimal): key -> (shown value, total skill level).  Asserted by tests/golden/test_night_walker_displayed.py.
PROVISIONAL = {}
CONFIRMED_BY_READINGS = {
    "QUINTUPLE_STAR": (663.5, 322),
    "SHADOW_SPARK_EXPLOSION": (691.3, 219),
    "SHADOW_BAT": (57.7, 151),
    "BAT_AFFINITY": (168.8, 219),
    "BAT_AFFINITY_II_EXPLOSION": (634.8, 279),
    "MARK_OF_DARKNESS": (66.6, 151),
    "ADAPTIVE_DARKNESS": (157.1, 219),
    "ADAPTIVE_DARKNESS_II": (347.2, 279),
}

# ---- Quintuple Star (the basic attack): 290 % x factor 21, 5 lines (6 from Lv136), targets 6 + Basic Attack Target Increase (that input already holds the Lv64 mastery) ----
QS_HITS = (5, 136, 6)
QS_MASTERY = {102: 10, 106: 11, 116: 12, 120: 13, 128: 14, 132: 15}      # Damage mastery chain: raw tiers, summed, then x(1 + m/100) (CLAUDE.md bug 2)
QS_BOSS_MASTERY = {111: 10, 124: 10}                                      # "+X% Boss Monster Damage to Quintuple Star"

# ---- damage rows cast on a cooldown ----
# step / base / fidx come from CURVES (``curve=`` key); cooldown (s) [+ haste (level, multiplier): cooldown masteries cut the BASE cooldown before Skill Cooldown Decrease], hits,
# mastery {level: %} (multiplies the skill), normal-monster targets, costs_action, ``cygnus``: key of the Call of Cygnus Final Damage, ``cast_row``: the row whose casts this row follows
DAMAGE_SKILLS = {
    "SHADOW_SPARK": dict(curve="SHADOW_SPARK", cooldown=19, hits=1, mastery={39: 80}, costs_action=True, targets=7, cygnus="CALL_OF_CYGNUS_SPARK"),
    "SHADOW_SPARK_EXPLOSION": dict(curve="SHADOW_SPARK_EXPLOSION", cooldown=19, hits=1, mastery={39: 80}, costs_action=False, targets=7, cygnus="CALL_OF_CYGNUS_SPARK",
                                   cast_row="SHADOW_SPARK"),
    "SHADOW_STITCH": dict(curve="SHADOW_STITCH", cooldown=27, hits=4, mastery={113: 50}, costs_action=True, targets=15),
}

# ---- timed buffs (cast on cooldown from t = 0, duty-cycle averages) ----
# duration (s) [+ (level, multiplier) from that level on], cooldown (s) [+ haste]
DARK_ELEMENTAL = dict(duration=12, duration_mastery=(21, 1.5), cooldown=28)           # Attack +10 % (CURVES DARK_ELEMENTAL_ATTACK), the Mark of Darkness window
DARKNESS_ASCENDING = dict(duration=15, cooldown=36, haste=(78, 0.7))                  # Attack +25 %
DARK_EVASION = dict(duration=15, duration_mastery=(126, 1.5), cooldown=40)            # Final Damage +20 %
SHADOW_DOUBLE = dict(duration=15, duration_mastery=(104, 1.3), cooldown=30, ba_mastery=(68, 10))      # clone 20 % of Quintuple Star's damage; Basic Attack Damage +10 during it (Lv68)
ELEMENTAL_HARMONY = dict(duration=15, cooldown=60)                                    # Attack Speed +15 % (CURVES ELEMENTAL_HARMONY_AS, non-scaling), +10 % Speed ignored

# ---- Shadow Momentum: every skill activation adds a stack (Attack Speed +4 % x factor each), 2 s, max 5; +10 Attack while it is up (Lv90 mastery) ----
SHADOW_MOMENTUM = dict(duration=2.0, max_stacks=5, attack_mastery=(90, 10))

# ---- Shadow Bat (on-attack proc) ----
SHADOW_BAT_PROC = dict(chance=20, chance_mastery=(24, 15), icd=1.0)                    # % per attack per enemy hit; Lv24 mastery +15 pp; internal cooldown 1 s
BAT_ATTACKS = dict(base=3, bat_affinity=1, mastery=(138, 2))                          # max attacks per bat: 3, +1 (Bat Affinity, Lv40), +2 (Bat Affinity III mastery, Lv138)
BAT_ATTACK_STEP = 0.25                                                                # each further attack deals 25 % less than the first ...
BAT_ATTACK_FLOOR = 0.25                                                               # ... down to a floor of 25 % of the first attack
BAT_DAMAGE_MASTERY = (44, 50)                                                         # "Bat Affinity - Damage": Shadow Bat damage +50 % (multiplies)
BAT_EXPLOSION = dict(targets=3, targets_mastery=(94, 1), mastery=(73, 50), boost=(118, 1.5))   # Bat Affinity II: 300 % on the first attack; +1 target (Lv94), +50 % (Lv73), FD boost x1.5 (Lv118)
BAT_AFFINITY_III_UNLOCK = "BAT_AFFINITY_III"

# ---- Dark Omen (summons Shadow Bats, no damage of its own) ----
DARK_OMEN = dict(cooldown=38, window=5, interval=0.7, interval_mastery=(108, 0.5), burst=(130, 4))     # a bat every 0.7 s (0.5 s from Lv108) for 5 s; +4 bats at once (Lv130)

# ---- Mark of Darkness (Dark Elemental) ----
MARK = dict(chance=20, chance_normal_mult=(72, 2.0), duration=5.0, tick=1.0,
            max_stacks=1, stacks=((50, 1), (54, 1), (72, 1)),                          # max stacks 1, +1 at 50 (Adaptive Darkness), +1 at 54 (mastery), +1 at 72 (Adaptive Darkness II)
            mastery=(82, 50),                                                          # "Adaptive Darkness II - Damage" +50 % (multiplies the 145 % tier)
            boost=(122, 1.5),                                                          # Adaptive Darkness III Final Damage boost x1.5 (Lv122)
            weaken=(134, 5.0))                                                         # Lv134: target damage taken +5 % while it carries a mark
# which row of CURVES gives the per-tick damage at a level: (from level, key); the later entry replaces the earlier one
MARK_TIERS = ((10, "MARK_OF_DARKNESS"), (50, "ADAPTIVE_DARKNESS"), (72, "ADAPTIVE_DARKNESS_II"))
BAT_TIERS = ((15, "SHADOW_BAT"), (40, "BAT_AFFINITY"))

# ---- the player's own stun: Shadow Spark stuns 1 s from level 49 (mastery) ----
PLAYER_STUN = [dict(id="SPARK", key="SHADOW_SPARK", typ="cast", dur=1.0, p=1.0, min_level=49, tick=1.0, win=0.0)]

# ---- action slots: every action-costing cooldown row takes one action (Dark Omen too), in this order ----
COST_ACTION_ORDER = ["SHADOW_SPARK", "SHADOW_STITCH", "DARK_OMEN", "DARK_ELEMENTAL", "DARKNESS_ASCENDING", "DARK_EVASION", "SHADOW_DOUBLE", "ELEMENTAL_HARMONY"]
BUFF_ROW_KEYS = ["DARK_ELEMENTAL", "DARKNESS_ASCENDING", "DARK_EVASION", "SHADOW_DOUBLE", "ELEMENTAL_HARMONY"]
STARTUP_BUFFS = list(BUFF_ROW_KEYS)                                                    # actively cast buffs -> startup delay / engine-off t0
# attacks that roll Shadow Bat / Mark of Darkness (per attack per enemy hit): the basic attack and the action-costing damage skills (summons, bats and DoT ticks excluded)
TRIGGER_ROWS = ["SHADOW_SPARK", "SHADOW_STITCH"]

# ---- Status Effect Damage / KO timeline engine spec (src/status_timeline.py) ----
# No engine-timed buff: the buffs are cast on cooldown from t = 0 and averaged (their Attack % is the engine's constant A0), as in Dawn Warrior.
STATUS_BUFFS = []
STATUS_GROUPS = [
    ("SPARK", "SHADOW_SPARK", [
        ("SHADOW_SPARK", "burst", None, None, "SHADOW_SPARK"),
        ("SHADOW_SPARK_EXPLOSION", "burst", None, None, "SHADOW_SPARK_EXPLOSION")]),
    ("STITCH", "SHADOW_STITCH", [("SHADOW_STITCH", "burst", None, None, "SHADOW_STITCH")]),
]
# spread uniformly over the fight: the basic attack and everything that follows its rate (clone, bats, explosions, marks)
STATUS_UNIFORM_ROWS = ["QUINTUPLE_STAR", "SHADOW_DOUBLE", "SHADOW_BAT", "BAT_EXPLOSION", "MARK_OF_DARKNESS"]
STATUS_CAST_PREFIX = {}
for _gid, _cast, _ents in STATUS_GROUPS:
    for _e in _ents:
        STATUS_CAST_PREFIX.setdefault(_e[0], f"grp.{_gid}")
    STATUS_CAST_PREFIX[_cast] = f"grp.{_gid}"
STATUS_FS_KEYS = [e[0] for _g, _c, ents in STATUS_GROUPS for e in ents if e[1] in ("dot", "end")]
STATUS_PHI_ROWS = sorted({e[0] for _g, _c, ents in STATUS_GROUPS for e in ents})

# ---- flagged assumptions, one line per row (also listed in data/cygnus/night_walker_known_gaps.md) ----
ROW_NOTES = {
    "QUINTUPLE_STAR": "Basic attack from level 100 (absent below, like every class); 290 % x factor 21 (confirmed: 663.5 % at total level 322).  Damage chain = raw tiers 10/11/12/13/14/15 summed then x(1+m/100); "
                      "+10 / +10 Boss Damage (Lv111 / Lv124) is this row's own boss mastery; 5 lines, 6 from Lv136; target count 6 + Basic Attack Target Increase.",
    "SHADOW_DOUBLE": "FLAGGED: the clone adds 20 % x factor 22 (step 3, site SetServantSkill op) of Quintuple Star's damage while up (15 s, x1.3 from Lv104, cooldown 30 s), same lines / targets / "
                     "boss mastery as the original; only the basic attack is mimicked (the other Basic-Attack-Effect skills are not modelled).  The Lv68 Basic Attack Damage +10 counts at its "
                     "time-average on Quintuple Star and at full strength on the clone's own row.  Clone hits do NOT roll Shadow Bat / Mark of Darkness; the clone is not mirrored by companions.",
    "SHADOW_SPARK": "220 % x1 on 7 targets (factor 12, site); +80 % damage (Lv39) multiplies; Call of Cygnus Final Damage 150 x factor 23 as 1 + pct/100 (site: both lines); stuns 1 s from Lv49.",
    "SHADOW_SPARK_EXPLOSION": "FLAGGED: 330 % x1 on 7 targets after the shuriken, same cast; factor 12 / step 2 assumed like the first line (site lists only the first line); the same Lv39 +80 % "
                              "and Call of Cygnus FD apply (site: Call of Cygnus modifies both lines).",
    "SHADOW_STITCH": "2850 % x4 hits on 15 targets (factor 12, site), cooldown 27 s; +50 % damage (Lv113).",
    "SHADOW_BAT": "FLAGGED: each attack (basic attack / Shadow Spark / Shadow Stitch cast) rolls once per ENEMY HIT (q = 1-(1-c)^N, N = 1 on boss / PvP), c = 20 % (+15 pp Lv24), 1 s internal "
                  "cooldown: rate = X/(1+ICD*X).  A bat attacks 3 times (+1 Bat Affinity, +2 Lv138), each at one random target; damage 36 % (90 % from Bat Affinity, x1.5 from Lv44), every further "
                  "attack 25 % LESS than the first down to a floor of 25 % (1, .75, .5, .25, .25 ...).  Dark Omen's bats (5 s / 0.7 s) feed the same row without a roll or ICD.  Counted as Skill "
                  "Damage; Call of Cygnus FD 120 x factor 23 as 1 + pct/100.  A bat always completes all its attacks (also with a single enemy).",
    "BAT_EXPLOSION": "FLAGGED: Bat Affinity II's 300 % explosion on the FIRST attack of every bat (also Dark Omen's), on 3 targets (+1 Lv94) assumed to include the main target (so one hit on a "
                     "boss); +50 % (Lv73) multiplies; Bat Affinity III's Final Damage +150 % (x1.5 boost from Lv118, same 'boost the boost' reading as Dawn's Master of the Sword) is a "
                     "per-row factor 1 + pct/100.  Call of Cygnus does not apply to it (site: Shadow Bat only).",
    "MARK_OF_DARKNESS": "FLAGGED proc-fed DoT: only while Dark Elemental is up (12 s, x1.5 from Lv21, cooldown 28 s) every attack (basic / Spark / Stitch) rolls once per enemy hit, 20 % (x2 on "
                        "non-boss from Lv72, capped at 100 %); a mark lasts 5 s and ticks every 1 s at 38 % (75 % Adaptive Darkness, 145 % Adaptive Darkness II, x1.5 from Lv82), all growing with factor 12; each mark has its "
                        "own timer, at most 1 / 2 / 3 / 4 marks per enemy (Lv50 / 54 / 72); marks beyond the cap are lost.  Expected simultaneously live marks per enemy come from a Poisson count "
                        "over the window, integrated in closed form (ramp up, plateau, ramp down incl. the 5 s after the buff ends); boss branch = one target, normal branch = every enemy in "
                        "range with the attacks spread over them.  Adaptive Darkness III's Final Damage +150 % (x1.5 from Lv122) is a per-row factor; Lv134 Weaken (+5 % damage taken while marked) "
                        "joins the monster-damage-taken term of every row by the marked time share.",
}
