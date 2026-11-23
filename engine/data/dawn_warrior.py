"""Dawn Warrior (Cygnus Knight, STR main / DEX sub) static game data - ENGINE-NATIVE: there is no workbook, builder or verify script for this class.

Source: the user's in-game skill / mastery text (2026-11, character level 120; every number reproduced exactly by ``tests/golden/test_dawn_warrior_displayed.py`` with the
game's truncation rule ``trunc_1dp(base x factor[idx][total skill level])``).  The live site data (maplestoryidle.info) has no Dawn Warrior rows.

Conventions follow ``engine/data/hero.py``: base damage in TENTHS of a percent (``base``), ``fidx`` the FactorTable column, ``step`` the job tier (1-4) whose skill level
scales the skill; ``(threshold, value)`` tuples / ``{level: tier value}`` chains are resolved by the model in ``engine/classes/dawn_warrior.py``.

Every judgement call is flagged in ``ROW_NOTES`` and in KNOWN_GAPS.md ("Dawn Warrior (engine-native, no workbook)").
"""

CLASS_ID = "dawn_warrior"

SKILL_NAMES = {
    "CELESTIAL_VISION": "Celestial Vision III (basic attack)",
    "LUNA_DIVIDE": "Luna Divide (Equinox Cycle basic-attack effect)",
    "COSMIC_MATTER": "Cosmic Matter (single-target hits)",
    "COSMIC_MATTER_BLAST": "Cosmic Matter (explosion)",
    "SOL_RUSH": "Sol Rush",
    "SOL_RUSH_ENHANCED": "Sol Rush (enhanced, during Equinox Cycle)",
    "TRUE_SIGHT": "True Sight",
    "COSMIC_SHOWER": "Cosmic Shower",
    "EQUINOX_SLASH": "Equinox Slash",
    "IMPALING_RAYS": "Impaling Rays",
    "IMPALING_RAYS_PIERCE": "Impaling Rays (delayed pierce on stun-immune enemies)",
    "COSMIC_BURST": "Cosmic Burst",
}

# Result rows (damage rows only)
DPS_ROW_ORDER = ["CELESTIAL_VISION", "LUNA_DIVIDE", "COSMIC_MATTER", "COSMIC_MATTER_BLAST", "SOL_RUSH", "SOL_RUSH_ENHANCED", "TRUE_SIGHT",
                 "COSMIC_SHOWER", "EQUINOX_SLASH", "IMPALING_RAYS", "IMPALING_RAYS_PIERCE", "COSMIC_BURST"]

# Unlock level of every row that has a threshold (the in-game skill list: active skills 0/15/35/45/63/66/69/100/103/105/115, passives 33/38/40/43/50/60/72/74/75/100/107/110/117/120/125).
# The basic attack (Celestial Vision III) is the 4th-job one: unlocked at level 100 and ABSENT below it, exactly like Hero's Raging Blow (no pre-100 basic attack data exists for any class).
UNLOCK_LEVEL = {
    "CELESTIAL_VISION": 100,
    "LUNA_DIVIDE": 100,                 # triggered by Basic Attack skills = Celestial Vision III (level 100), Equinox Cycle (45)
    "COSMIC_MATTER": 35,
    "COSMIC_MATTER_BLAST": 35,
    "SOL_RUSH": 63,
    "SOL_RUSH_ENHANCED": 63,
    "TRUE_SIGHT": 66,
    "COSMIC_SHOWER": 69,
    "EQUINOX_SLASH": 103,
    "IMPALING_RAYS": 105,
    "IMPALING_RAYS_PIERCE": 105,
    "COSMIC_BURST": 115,
    # buffs / passives with a live (timed / conditional) effect
    "ELEMENTAL_HARMONY": 0,
    "SOUL_ELEMENTAL": 15,
    "EQUINOX_CYCLE": 45,
    "SOUL_BLESSING": 40,
    "EQUINOX_MASTERY": 72,
    "SOUL_BLESSING_II": 74,
    "CALL_OF_CYGNUS": 100,
    "MASTER_OF_THE_SWORD": 110,
    "SOUL_BLESSING_III": 125,
}

# ---- Celestial Vision III (the basic attack) ----
CV_BASE = 290                                       # in % (Hero's RAGING_BLOW_BASE convention), factor index 21, 4th job (499.9 % at total level 181)
CV_HITS = (5, 136, 6)                               # 5 hits, +1 strike from level 136 (mastery "Celestial Vision III - Strike")
CV_MASTERY = {102: 10, 106: 11, 116: 12, 120: 13, 128: 14, 132: 15}      # Damage mastery chain: raw tiers, summed, then x(1 + m/100) (CLAUDE.md bug 2)
CV_BOSS_MASTERY = {111: 10, 124: 10}                                      # "+X% Boss Monster Damage to Celestial Vision III"

# ---- Luna Divide (Equinox Cycle's basic-attack effect) ----
LUNA_BASE = (200, (72, 700))                        # 20 (idx 21, 2nd job) -> 70 (idx 21, 3rd job) once Equinox Mastery (72) is learned
LUNA_FIDX = 21
LUNA_HITS = 2
LUNA_TARGETS = 5
LUNA_TARGET_BONUS = ((49, 2), (72, 2), (110, 1))    # mastery (49), Equinox Mastery (72), Master of the Sword (110): cumulative max-target increases
LUNA_MASTERY = {94: 40}                             # "Equinox Mastery - Damage": Luna Divide damage +40 %

# ---- timed buffs ----
SOUL_ELEMENTAL = dict(base=150, fidx=21, step=1, duration=12, cooldown=28, duration_mastery=(21, 1.5))       # Attack %, 12 s x1.5 from the level 21 mastery
SOUL_BLESSING = dict(base=50, fidx=22, step=2)                      # +pp to Soul Elemental's Attack effect
SOUL_BLESSING_II_RATE = dict(base=80, fidx=22, step=3)              # Crit Rate % while Soul Elemental is up
SOUL_BLESSING_II_DMG = dict(base=180, fidx=22, step=3, gated={82: 10})       # Crit Damage % while Soul Elemental is up (+10 pp from level 82)
SOUL_BLESSING_III = dict(base=200, fidx=22, step=4, gated={130: 10})         # Final Damage % while Soul Elemental is up (+10 pp from level 130)
EQUINOX_CYCLE = dict(base=30, fidx=21, step=2, duration=15, cooldown=30, duration_mastery=(54, 1.3))        # Attack %, 15 s x1.3 from the level 54 mastery
EQUINOX_MASTERY_BA = dict(base=100, fidx=22, step=3)                # Basic Attack Damage % during Equinox Cycle
MASTER_SWORD_EC_ATTACK = dict(base=120, fidx=22, step=4)            # +pp to Equinox Cycle's Attack effect (Master of the Sword)
MASTER_SWORD_FD = dict(base=1900, fidx=21, step=4, boost=(118, 1.8))     # Luna Divide's own Final Damage multiplier 1 + pct/100 (x1.8 from the level 118 mastery)
MASTER_SWORD_EC_FD = (134, 8)                                       # +8 % Final Damage for the duration of Equinox Cycle (level 134 mastery)
ELEMENTAL_HARMONY = dict(duration=15, cooldown=60, attack_speed=15)  # Attack Speed +15 % (+10 % movement speed ignored); no level shown in game -> not level-scaling
CALL_OF_CYGNUS = {"COSMIC_MATTER": 800, "COSMIC_SHOWER": 250, "SOL_RUSH": 300}     # per-skill Final Damage multiplier 1 + pct/100 (base tenths, idx 23, 4th job)
CALL_OF_CYGNUS_FIDX = 23

# ---- debuffs on the enemy ----
TRUE_SIGHT_TAKEN = dict(base=100, fidx=21, step=3, duration=15)     # target damage taken +10 % x factor, 15 s
IMPALING_WEAKEN = dict(level=138, pct=15, duration=10)              # stun-immune targets take +15 % for 10 s (level 138 mastery)

# ---- Cosmic Shower (tick summon) and its same-target decay ----
SHOWER_DECAY_STEP = 0.2                                             # -20 % per strike on the same target ...
SHOWER_DECAY_MAX_STEPS = 4                                          # ... up to 4 times (floor x0.2)

# ---- damage rows ----
# step, cooldown (s) [+ haste (level, multiplier): the cooldown masteries cut the BASE cooldown before Skill Cooldown Decrease], hits, base (tenths of %), factor index,
# mastery chain {level: %} (multiplies the skill), boss mastery %, normal-monster targets [+ extra_targets (level, n)], costs_action; ``icd`` / ``window`` = tick rows;
# ``share``: fraction of the cast row's casts that this row takes (Sol Rush normal / enhanced); ``cygnus``: key into CALL_OF_CYGNUS; ``boss_only``: no normal-branch damage.
DAMAGE_SKILLS = {
    "COSMIC_MATTER": dict(step=2, cooldown=14, hits=2, base=1000, fidx=12, mastery={39: 50}, mastery_boss=0, costs_action=True, targets=1, cygnus="COSMIC_MATTER"),
    "COSMIC_MATTER_BLAST": dict(step=2, cooldown=14, hits=3, base=1300, fidx=12, mastery={39: 50}, mastery_boss=0, costs_action=False, targets=6,
                                cygnus="COSMIC_MATTER", cast_row="COSMIC_MATTER"),
    "SOL_RUSH": dict(step=3, cooldown=26, haste=(90, 0.7), hits=2, base=3000, fidx=12, mastery={68: 50}, mastery_boss=0, costs_action=True, targets=7,
                     cygnus="SOL_RUSH", share="normal"),
    "SOL_RUSH_ENHANCED": dict(step=3, cooldown=26, haste=(90, 0.7), hits=2, base=4300, fidx=12, mastery={68: 50}, mastery_boss=0, costs_action=False, targets=8,
                              cygnus="SOL_RUSH", share="enhanced", cast_row="SOL_RUSH", ec_only=True),
    "TRUE_SIGHT": dict(step=3, cooldown=27, haste=(98, 0.75), hits=1, base=7800, fidx=12, mastery={78: 100}, mastery_boss=0, costs_action=True, targets=15),
    "COSMIC_SHOWER": dict(step=3, cooldown=22, hits=1, icd=(0.3, (104, 0.2)), window=15, base=2800, fidx=12, mastery={73: 50}, mastery_boss=0, costs_action=True,
                          targets=1, cygnus="COSMIC_SHOWER"),
    "EQUINOX_SLASH": dict(step=4, cooldown=11, haste=(126, 0.7), hits=2, base=22000, fidx=12, mastery={108: 50}, mastery_boss=0, costs_action=True, targets=7,
                          extra_targets=(126, 3), ec_only=True),
    "IMPALING_RAYS": dict(step=4, cooldown=24, hits=3, base=16000, fidx=12, mastery={113: 100}, mastery_boss=0, costs_action=True, targets=14),
    "IMPALING_RAYS_PIERCE": dict(step=4, cooldown=24, hits=3, base=13000, fidx=12, mastery={113: 100}, mastery_boss=0, costs_action=False, targets=1,
                                 window=5, cast_row="IMPALING_RAYS", boss_only=True),
    "COSMIC_BURST": dict(step=4, cooldown=19, hits=4, base=15000, fidx=12, mastery={122: 50}, mastery_boss=0, costs_action=True, targets=12),
}

# Action-costing rows (cast rate subtracted from the basic attack), in order: damage rows read DAMAGE_SKILLS, buffs BUFF_COOLDOWNS
COST_ACTION_ORDER = ["COSMIC_MATTER", "SOL_RUSH", "TRUE_SIGHT", "COSMIC_SHOWER", "EQUINOX_SLASH", "IMPALING_RAYS", "COSMIC_BURST",
                     "SOUL_ELEMENTAL", "EQUINOX_CYCLE", "ELEMENTAL_HARMONY"]
BUFF_COOLDOWNS = {"SOUL_ELEMENTAL": 28, "EQUINOX_CYCLE": 30, "ELEMENTAL_HARMONY": 60}
BUFF_ROW_KEYS = ["SOUL_ELEMENTAL", "EQUINOX_CYCLE", "ELEMENTAL_HARMONY"]
STARTUP_BUFFS = ["SOUL_ELEMENTAL", "EQUINOX_CYCLE", "ELEMENTAL_HARMONY"]       # actively cast buffs -> startup delay / engine-off t0

# ---- player's own stuns: Sol Rush 1 s (1.5 s while Equinox Cycle is up), Impaling Rays 1.5 s; cast on cooldown from the start ----
# (``dur`` of Sol Rush is the Equinox-uptime mix; the model overwrites it)
PLAYER_STUN = [dict(id="SOLRUSH", key="SOL_RUSH", typ="cast", dur=1.0, p=1.0),
               dict(id="IMPALE", key="IMPALING_RAYS", typ="cast", dur=1.5, p=1.0)]
SOL_RUSH_STUN = (1.0, 1.5)

# ---- Status Effect Damage / KO timeline engine spec (src/status_timeline.py) ----
# No engine-timed buff: Soul Elemental / Equinox Cycle / Elemental Harmony are cast on cooldown from t = 0 and averaged (their attack effect is in the engine's constant A0).
STATUS_BUFFS = []
STATUS_GROUPS = [
    ("MATTER", "COSMIC_MATTER", [
        ("COSMIC_MATTER", "burst", None, None, "COSMIC_MATTER"),
        ("COSMIC_MATTER_BLAST", "burst", None, None, "COSMIC_MATTER_BLAST")]),
    ("RUSH", "SOL_RUSH", [
        ("SOL_RUSH", "burst", None, None, "SOL_RUSH"),
        ("SOL_RUSH_ENHANCED", "burst", None, None, "SOL_RUSH_ENHANCED")]),
    ("SIGHT", "TRUE_SIGHT", [("TRUE_SIGHT", "burst", None, None, "TRUE_SIGHT")]),
    ("SHOWER", "COSMIC_SHOWER", [("COSMIC_SHOWER", "dot", "COSMIC_SHOWER", None, "COSMIC_SHOWER")]),
    ("RAYS", "IMPALING_RAYS", [
        ("IMPALING_RAYS", "burst", None, None, "IMPALING_RAYS"),
        ("IMPALING_RAYS_PIERCE", "end", "IMPALING_RAYS_PIERCE", None, "IMPALING_RAYS_PIERCE")]),
    ("BURST", "COSMIC_BURST", [("COSMIC_BURST", "burst", None, None, "COSMIC_BURST")]),
]
# Equinox Slash can only be cast INSIDE Equinox Cycle, so the optimiser may not place it freely: it is spread uniformly like the basic attack (flagged)
STATUS_UNIFORM_ROWS = ["CELESTIAL_VISION", "LUNA_DIVIDE", "EQUINOX_SLASH"]
STATUS_CAST_PREFIX = {}
for _gid, _cast, _ents in STATUS_GROUPS:
    for _e in _ents:
        STATUS_CAST_PREFIX.setdefault(_e[0], f"grp.{_gid}")
    STATUS_CAST_PREFIX[_cast] = f"grp.{_gid}"
# rows whose hits/s come from the engine's effective cast count (last DoT window / delayed hit truncated by the fight end)
STATUS_FS_KEYS = [e[0] for _g, _c, ents in STATUS_GROUPS for e in ents if e[1] in ("dot", "end")]
STATUS_PHI_ROWS = sorted({e[0] for _g, _c, ents in STATUS_GROUPS for e in ents})

# ---- flagged assumptions, one line per row (also listed in KNOWN_GAPS.md "Dawn Warrior (engine-native, no workbook)") ----
ROW_NOTES = {
    "CELESTIAL_VISION": "Basic attack from level 100 (absent below, like every class).  Damage chain = raw tiers 10/11/12/13/14/15 summed then x(1+m/100); +10 / +10 Boss Damage "
                        "(Lv111 / Lv124) is this row's own boss mastery.  Target count 6 + Basic Attack Target Increase (that input already includes the Lv64 mastery).",
    "LUNA_DIVIDE": "FLAGGED: one Luna Divide (2 hits) per Celestial Vision III swing while Equinox Cycle is up (only Basic Attack skills trigger it; no other basic attack exists "
                   "in this model).  Counted as a Basic Attack damage line ([Basic Attack Effect]); max targets 5 +2 (Lv49) +2 (Equinox Mastery) +1 (Master of the Sword); "
                   "Equinox Mastery sets its damage to 70 (idx 21), +40 % (Lv94); Master of the Sword's Final Damage is a 1 + pct/100 multiplier on THIS row only (user-confirmed target; "
                   "exact form assumed, x1.8 from Lv118 = 'boost by 80 %' read as +80 % of the boost).  Equinox Cycle's Attack and +16 Basic Attack Damage count at "
                   "full strength here (the row only exists while the Cycle is up); the +8 Final Damage is time-averaged like for every row.",
    "COSMIC_MATTER": "Two hits on 1 target, then the explosion row (3 hits, 6 targets); shared cooldown 14 s.  Call of Cygnus Final Damage is a per-skill multiplier 1 + pct/100 "
                     "(Maple Hero convention) - assumed multiplicative with the Final Damage bucket.",
    "COSMIC_MATTER_BLAST": "See Cosmic Matter (same cast).",
    "SOL_RUSH": "Normal Sol Rush takes the share of casts made while Equinox Cycle is NOT up (1 - Cycle uptime).  Cooldown 26 s, -30 % at Lv90 (cuts the base before Skill Cooldown "
                "Decrease).  Call of Cygnus Final Damage 30 as for Cosmic Matter.",
    "SOL_RUSH_ENHANCED": "FLAGGED: the Cycle-uptime share of Sol Rush casts are enhanced (430 x2, 8 targets); the stun lasts 1.5 s there (PLAYER_STUN uses the uptime mix).  The Cycle's "
                         "Attack counts at full strength.",
    "TRUE_SIGHT": "780 x1 on 15 targets; Damage +100 % (Lv78), cooldown -25 % (Lv98).  Its 'target damage taken +x %' (10 x idx 21, 15 s) joins the monster-damage-taken bucket "
                  "of every row for its uptime (Hero's Scaring Sword convention).",
    "COSMIC_SHOWER": "280 per tick, 0.3 s (0.2 s from Lv104), 15 s, 1 random target.  FLAGGED: same-target decay -20 % per strike (floor x0.2).  Boss / PvP: always the same target, "
                     "ticks multiplied 1, 0.8, 0.6, 0.4, then 0.2 (window average used for every cast).  Normal monsters: the next target repeats with probability 1/Max Enemies In Range "
                     "(blank = uncapped = no decay); the tick count is NOT multiplied by a target count (1 target per tick).  The window is not extended by Buff Duration Increase.",
    "EQUINOX_SLASH": "FLAGGED: castable only inside Equinox Cycle; casts per Cycle = floor(window / own cooldown) + 1 (first cast at the window start), capped by 1/cooldown when the windows "
                     "overlap; cooldown 11 s, -30 % at Lv126 (base before Skill Cooldown Decrease); +3 targets at Lv126; spread uniformly in the Status/KO timeline.  Cycle Attack at "
                     "full strength.",
    "IMPALING_RAYS": "1600 x3 on 14 targets, stun 1.5 s.  Damage +100 % at Lv113.",
    "IMPALING_RAYS_PIERCE": "FLAGGED: the delayed 1300 x3 hit 5 s later exists only on stun-immune enemies = the boss branch (and PvP); normal monsters get no such hit.  Casts whose pierce "
                            "would land after the fight ends do not count.  The same Lv113 +100 % mastery assumed to apply to it.",
    "COSMIC_BURST": "1500 x4 on 12 targets; Damage +50 % (Lv122).",
}
