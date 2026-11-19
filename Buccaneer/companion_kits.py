"""Companion kits as DATA (one row per component), read by companion_model.py's generic formula engine.

Source: data/companions/MS_IDLE_COMPS_STATS.xlsx (hand-typed by the user) + data/companions/ANSWERS_2026-11-13.md (the user's answers);
Wind Archer's kit was given in chat on 2026-11-11.  Everything here is a transcription/interpretation - review it in the CompanionKits sheet.

Row kinds
  basic    the companion's basic attack (every companion: 290% x 5 lines x 6 targets, like Wind Archer)
  hit      one damage part of a cooldown skill or of the summoning effect: `lines` damage lines of `pct` % each to `tgt` enemies
           (`tgt_boss` on a boss, default 1), `atk` = attacks (projectiles) it counts as for "when attacking" procs, `action` = 1 on the ONE row
           of a skill that consumes an action slot per cast
  dot      damage over a duration / periodic damage: cast every `cd`, lasts `dur`, one tick (`lines` x `pct` % to `tgt`) every `tick`
  proc     chance-per-attack proc: `chance` per attack per enemy hit, `icd`, `trig` = 'basic' (basic attacks) or 'any' (basic + hit casts)
  stat     a stat/debuff effect: `stat` code, `who` = p player / c companion / b both / m monster, `val`; timed when `cd` and `dur` are finite
           (cd=NEVER and dur=NEVER = permanent while summoned), `per_tgt` = value per nearby target (capped at per_tgt targets)
  stack    stacking buff gained by chance per attack (`chance`, `icd`, `val` per stack, `smax` stacks, `sdur` s each)
  ramp     a stat that ramps while the companion is out: mode 'lin' (+val per second) or 'exp' (x(1+val/100) per second up to `ramp_cap` s)
  echo     extra spirit arrows per cast (src id) or per skill activation (echo_all)
  echoproc extra spirit arrows per proc of the proc with `slot` == src
  stunhit  extra damage per stun/freeze application on enemies (Shadower Lv3)
Gates ("-" = none; a row only exists when its gate is true): g_ct 'BT' Chapter Breakthrough / 'notBT' / 'CB' Chapter Boss / 'PvP' / 'notPvP';
  g_br 'boss' / 'nonboss' (damage rows only: evaluated per branch); g_hp 'lt50' / 'ge50' (target HP below / at-or-above 50%; damage rows
  and stat rows alike, evaluated with the boss-branch fraction f50 of the window spent below 50%).
Cast timing (2026-11-18, user's in-game measurement on Blaze Wizard at 55.5% attack speed; see START_DELAY / CAST_TIME / FIRST_SLOT below):
  a COOLDOWN SKILL row (`action` == 1 and a finite `cd`) is cast at t0 + n * (cd + CAST_TIME), n = 0, 1, ...  (relative to the summon),
  t0 = START_DELAY + k * FIRST_SLOT with k = the 0-based rank of the skill among the ACTIVE action skills in kit order (variants of one skill that
  exist in different contents - a1 / a1_bt - are ONE skill: the variant names the canonical row in `cast_of`).  Rows that belong to the same cast
  (the second part of a skill, its debuff, its end-of-window explosion, its echo arrows: `cast_of` = the id of the action row) share that skill's
  period and first-cast time.  Everything else with a finite `cd` (a passive's own timer, e.g. Paladin's barrier) keeps period = cd, t0 = 0, and the
  once-per-summon rows (cd = NEVER: summoning effects) happen at the summon.  `schedule()` is the single definition; the CompanionKits sheet carries
  its (level / content independent) result in the columns `per` and `t0`, the plain-Python mirror recomputes it from the active rows.
stat codes (player side): atk fd crit_rate crit_dmg skill_dmg bad norm_dmg boss_dmg max_dmg def_pen as   fd_pt (FD per nearby target)
  (monster side, who='m'): dmg_taken dmg_taken_b dmg_taken_n  mon_def mon_def_b mon_def_n   (b / n = boss only / normal monsters only)
"""

NEVER = 1e9   # cd / dur / tick value meaning "once" / "permanent" / "no ticks"

# ---- companion cast timing (user's in-game measurement, Blaze Wizard, 55.5% attack speed; no attack-speed scaling, no per-skill cast-time table)
START_DELAY = 0.3    # s: the companion's first action starts this long after the summon
CAST_TIME = 0.5      # s: every cooldown skill's cooldown only starts counting once the cast is finished -> period = cd + CAST_TIME
FIRST_SLOT = 0.8     # s: the k-th action skill (kit order) makes its first cast at START_DELAY + k * FIRST_SLOT (a2 = 1.1 s)

KIT_COLUMNS = [
    "comp", "id", "kind", "unlock", "maxlvl", "g_ct", "g_br", "g_hp",
    "cd", "dur", "tick", "action",
    "pct", "lines", "atk", "tgt", "tgt_boss",
    "chance", "icd", "trig",
    "stat", "who", "val", "per_tgt",
    "smax", "sdur", "ramp_mode", "ramp_cap",
    "boost_src", "boost_chance", "src", "echo_all", "cast_of",
    "stun", "stun_bt", "stun_p", "stun_skip",
    "slot", "note",
]
STATIC_COLUMNS = ["tkf", "per", "t0", "skey"]    # derived in rows_with_keys(): whole ticks of one full duration INT(dur / tick); cast period; first-cast time
_NUMERIC_DEFAULTS = dict(
    unlock=1, maxlvl=99, cd=NEVER, dur=NEVER, tick=NEVER, action=0, pct=0, lines=0, atk=0, tgt=1, tgt_boss=1,
    chance=0, icd=0, val=0, per_tgt=0, smax=0, sdur=0, ramp_cap=0, boost_chance=0, echo_all=0, stun=0, stun_bt=0,
    stun_p=1, stun_skip=0, slot=0,
)
_TEXT_DEFAULTS = dict(   # "-" = none (a literal token: empty cells compare unreliably across Excel / the `formulas` package)
    g_ct="-", g_br="-", g_hp="-", trig="-", stat="-", who="-", ramp_mode="-", boost_src="-", src="-", note="", id="", cast_of="-",
)

COMPANIONS_ORDER = [
    "Wind Archer", "Dawn Warrior", "Blaze Wizard", "IL Mage", "FP Mage", "Bishop", "Night Walker", "Hero", "Paladin",
    "Dark Knight", "Bow Master", "Marksman", "Night Lord", "Shadower", "Buccaneer", "Corsair",
]
SPIRIT_ARROW_EXPECTED_PCT = 310.0 * 1.5     # 310% with a 50% chance to double

ROWS = []


def row(comp, kind, **kw):
    r = {}
    for c in KIT_COLUMNS:
        if c == "comp":
            r[c] = comp
        elif c == "kind":
            r[c] = kind
        elif c in kw:
            r[c] = kw.pop(c)
        elif c in _NUMERIC_DEFAULTS:
            r[c] = _NUMERIC_DEFAULTS[c]
        else:
            r[c] = _TEXT_DEFAULTS[c]
    assert not kw, f"unknown columns {kw}"
    ROWS.append(r)
    return r


def common(comp, event_passive=False):
    """Rows every companion has: basic attack + the universal Lv5/8/10 Final Damage skills (companion x1.25 each)."""
    row(comp, "basic", id="basic", pct=290, lines=5, tgt=6, atk=1)
    for lv in (5, 8, 10):
        row(comp, "stat", id=f"fd_lv{lv}", unlock=lv, stat="fd", who="c", val=25, note="universal companion Final Damage skill")
    if event_passive:
        row(comp, "stat", id="event_fd", stat="fd", who="c", val=25, note="event passive (assumed always on)")


# ----------------------------------------------------------------------------------------------- Wind Archer
c = "Wind Archer"
common(c)
row(c, "hit", id="special", pct=SPIRIT_ARROW_EXPECTED_PCT, lines=15, note="15 spirit arrows on summon (310% x1.5 expected), 1 random target each")
row(c, "echo", id="trifling", echo_all=1, pct=SPIRIT_ARROW_EXPECTED_PCT, lines=3, note="Trifling Wind: 3 spirit arrows per skill activation (incl. the summon special)")
row(c, "hit", id="vortex", cd=19, action=1, pct=2300, lines=2, tgt=8, atk=1, note="Spiraling Vortex (stun 1.2 s)", stun=1.2)
row(c, "hit", id="pinpoint", cd=18, action=1, pct=2500, lines=2, atk=2, note="Pinpoint Pierce 1550% + 3450% on one target (avg 2500% x2 lines)")
row(c, "stat", id="pinpoint_debuff", cast_of="pinpoint", cd=18, dur=8, stat="dmg_taken", who="m", val=25, note="the second arrow's target takes +25% damage for 8 s")
row(c, "hit", id="song", unlock=4, cd=25, action=1, pct=780, lines=13, tgt=4, atk=13, note="Song of Heaven, 13 arrows")
row(c, "echo", id="song_cb", cast_of="song", unlock=4, cd=25, g_ct="CB", pct=SPIRIT_ARROW_EXPECTED_PCT, lines=2, note="[Chapter Boss] 2 spirit arrows per Song cast")
row(c, "proc", id="storm", unlock=3, chance=0.35, icd=0.5, trig="any", pct=750, lines=1, tgt=5, slot=1, note="Storm Bringer")
row(c, "echoproc", id="storm_cb", unlock=3, g_ct="CB", src="1", pct=SPIRIT_ARROW_EXPECTED_PCT, lines=2, note="[Chapter Boss] 2 spirit arrows per giant arrow")
row(c, "stat", id="whispers", stat="atk", who="b", val=15, note="Whispers of the Wind: +15% Attack, companion and player")
row(c, "stat", id="windwalk", unlock=2, stat="fd", who="c", val=15, note="Wind Walk: companion Final Damage +15%")
row(c, "stat", id="windwalk_cb", unlock=2, g_ct="CB", stat="fd", who="p", val=5, note="[Chapter Boss] player Final Damage +5% while summoned")

# ----------------------------------------------------------------------------------------------- Dawn Warrior
c = "Dawn Warrior"
common(c, event_passive=True)
row(c, "stat", id="sum_atk_p", dur=10, stat="atk", who="p", val=15, note="summoning effect: player Attack +15% for 10 s")
row(c, "stat", id="sum_atk_c", stat="atk", who="c", val=15, note="summoning effect: companion Attack +15% for the summoning duration")
row(c, "stat", id="sum_cd_p", dur=10, stat="crit_dmg", who="p", val=15, note="summoning effect: player Crit Damage +15% for 10 s")
row(c, "stat", id="sum_cd_c", stat="crit_dmg", who="c", val=15)
row(c, "hit", id="a1_1", cd=15, action=1, pct=710, lines=2, tgt=1, atk=1, note="dark matter 710% x2 on 1 target")
row(c, "hit", id="a1_2", cast_of="a1_1", cd=15, pct=1120, lines=3, tgt=6, note="then explodes 1120% x3 on 6 targets")
row(c, "dot", id="a2_hi", cd=20, dur=10, tick=0.3, action=1, g_hp="ge50", pct=230, lines=1, tgt=1, note="meteor shower 230% every 0.3 s for 10 s, 1 random target")
row(c, "dot", id="a2_lo", cast_of="a2_hi", cd=20, dur=10, tick=0.3, g_hp="lt50", pct=690, lines=1, tgt=1, note="x3 damage when the target HP is below 50%")
row(c, "hit", id="a3", unlock=4, cd=23, action=1, pct=1800, lines=3, tgt=10, atk=1, stun=1.5, note="1800% x3 on 10 targets, stun 1.5 s")
row(c, "hit", id="a3_lo", cast_of="a3", unlock=4, cd=23, g_hp="lt50", pct=5000, lines=1, tgt=10, note="if the target HP is below 50%: +5000% after 5 s")
row(c, "stat", id="a3_taken", cast_of="a3", unlock=4, cd=23, dur=10, g_hp="lt50", stat="dmg_taken", who="m", val=10, note="and +10% damage taken for 10 s")
row(c, "proc", id="p1", chance=0.5, icd=0, trig="basic", pct=220, lines=2, tgt=6, slot=1, note="Basic Attack: 50% for 220% x2 on 6 targets")
row(c, "stat", id="p2", stat="skill_dmg", who="b", val=20)
row(c, "stat", id="p3", unlock=2, stat="fd", who="b", val=5)
row(c, "stat", id="p4", unlock=3, stat="def_pen", who="c", val=15)
row(c, "stat", id="p4_lo", unlock=3, g_hp="lt50", stat="def_pen", who="c", val=15, note="doubled against a boss below 50% HP")

# ----------------------------------------------------------------------------------------------- Blaze Wizard
c = "Blaze Wizard"
common(c, event_passive=True)
row(c, "stat", id="sum_taken", dur=30, g_ct="notBT", stat="dmg_taken_n", who="m", val=10, note="summoning effect: non-boss enemies take +10% for 30 s")
row(c, "stat", id="sum_taken_bt", dur=30, g_ct="BT", stat="dmg_taken_n", who="m", val=30, note="[Chapter Breakthrough] applied x3 = +30%")
row(c, "hit", id="a1", cd=9, action=1, g_ct="notBT", pct=920, lines=5, tgt=7, atk=1, note="fire pillars 920% x5 on 7 targets")
row(c, "hit", id="a1_bt", cast_of="a1", cd=9, action=1, g_ct="BT", pct=920, lines=5, tgt=14, atk=1, note="[Breakthrough] max targets x2")
row(c, "hit", id="a2", cd=16, action=1, pct=1170, lines=3, tgt=12, atk=1, g_ct="notBT", stun=1.5, note="phoenix 1170% x3 on 12 targets, stun 1.5 s")
row(c, "hit", id="a2_bt", cast_of="a2", cd=16, action=1, pct=1170, lines=3, tgt=12, atk=1, g_ct="BT", stun=4.5, note="[Breakthrough] stun 1.5 s x3 = 4.5 s (user, 2026-11-14)")
row(c, "dot", id="a3", unlock=4, cd=12, dur=5, tick=0.5, action=1, g_ct="notBT", pct=430, lines=1, tgt=12, note="fire orb 430% every 0.5 s for 5 s on 12 targets")
row(c, "dot", id="a3_bt", cast_of="a3", unlock=4, cd=12, dur=5, tick=0.5, action=1, g_ct="BT", pct=860, lines=1, tgt=12, note="[Breakthrough] damage doubled")
row(c, "stat", id="p1_p", stat="atk", who="p", val=12)
row(c, "stat", id="p1_c", stat="atk", who="c", val=20)
row(c, "proc", id="p2", g_ct="notBT", chance=0.5, icd=2, trig="basic", pct=300, lines=2, tgt=8, slot=1, note="Basic Attack: 50% for 300% x2 on 8 targets, 2 s cooldown")
row(c, "proc", id="p2_bt", g_ct="BT", chance=0.5, icd=0.5, trig="basic", pct=300, lines=2, tgt=8, slot=2, note="[Breakthrough] 0.5 s cooldown")
row(c, "stat", id="p3_n", unlock=2, stat="norm_dmg", who="b", val=8)
row(c, "stat", id="p3_b", unlock=2, stat="boss_dmg", who="b", val=8, note="when a boss monster is present: Boss Monster Damage +8% (and Normal +8% more)")
row(c, "stat", id="p4", unlock=3, stat="skill_dmg", who="c", val=25)
row(c, "stat", id="p4_bt", unlock=3, g_ct="BT", stat="skill_dmg", who="p", val=25, note="[Breakthrough] player Skill Damage +25% in battle")

# ----------------------------------------------------------------------------------------------- IL Mage
c = "IL Mage"
common(c)
row(c, "hit", id="special", pct=300, lines=5, tgt=10, stun=3, note="summoning effect 300% x5 on 10 targets, freezes 3 s")
row(c, "stat", id="a1", cd=30, dur=15, action=1, stat="atk", who="b", val=20, note="Attack +20% companion and player for 15 s")
row(c, "dot", id="a2", cd=15, dur=10, tick=2, action=1, pct=600, lines=3, tgt=8, note="lightning ball 600% x3 on 8 targets every 2 s for 10 s")
row(c, "dot", id="a3", unlock=4, cd=30, dur=5, tick=0.5, action=1, pct=800, lines=1, tgt=10, note="frost breath 800% every 0.5 s for 5 s on 10 targets")
row(c, "stat", id="a3_taken", cast_of="a3", unlock=4, cd=30, dur=5, stat="dmg_taken", who="m", val=15)
row(c, "stat", id="p3", unlock=2, stat="norm_dmg", who="p", val=15)
row(c, "dot", id="p4", unlock=3, cd=NEVER, dur=NEVER, tick=5, pct=800, lines=3, tgt=5, note="frost spears every 5 s: 800% x3 on 5 targets")

# ----------------------------------------------------------------------------------------------- FP Mage
c = "FP Mage"
common(c)
row(c, "hit", id="special", pct=300, lines=5, tgt=10, note="summoning effect 300% x5 on 10 targets")
row(c, "stat", id="special_taken", dur=10, stat="dmg_taken", who="m", val=25, note="and +25% damage taken for 10 s")
row(c, "dot", id="a1", cd=15, dur=10, tick=1, action=1, pct=300, lines=1, tgt=10, note="poison fog 300% every 1 s for 10 s (cooldown 15 s: user)")
row(c, "stat", id="a1_taken", cast_of="a1", cd=15, dur=10, stat="dmg_taken", who="m", val=15)
row(c, "hit", id="a2", cd=17, action=1, pct=600, lines=3, tgt=5, atk=3, note="meteors 600% x3 on 5 targets (cooldown 17 s: user)")
row(c, "dot", id="a3", unlock=4, cd=30, dur=30, tick=4, action=1, pct=3500, lines=1, tgt=3, note="Ifrit 30 s, 3500% every 4 s on 3 targets (cooldown 30 s: user)")
row(c, "stat", id="p1", stat="atk", who="p", val=15)
row(c, "dot", id="p2", cd=NEVER, dur=NEVER, tick=1, pct=100, lines=3, tgt=3, note="wall of fire, 100% every 1 s on 3 targets; the game shows no duration, so (user, 2026-11-12) it is modelled like the regular FP-Mage: 3 walls up for the whole summon (the wall-by-wall ramp is ignored)")
row(c, "stat", id="p3", unlock=2, stat="fd_pt", who="c", val=3, per_tgt=10, note="Final Damage +3% per nearby target up to 10 (1 target on a boss)")
row(c, "dot", id="p4", cast_of="a1", unlock=3, cd=15, dur=10, tick=5, pct=2000, lines=1, tgt=10, note="the fog explodes every 5 s: 2000% on 10 targets (only while the fog exists)")

# ----------------------------------------------------------------------------------------------- Bishop
c = "Bishop"
common(c)
row(c, "stat", id="a1", cd=15, dur=10, action=1, stat="atk", who="p", val=15, note="recovery skill; Attack +15% while HP >= 30% (assumed true) for 10 s")
row(c, "stat", id="a2", cd=27, dur=15, action=1, stat="atk", who="p", val=20, note="Attack +20% for 15 s")
row(c, "hit", id="a3", unlock=4, cd=11, action=1, pct=650, lines=6, tgt=10, atk=1, note="pillar of light 650% x6 on 10 targets (cooldown 11 s: user)")
row(c, "stat", id="p1", stat="max_dmg", who="p", val=24)
row(c, "stat", id="p2", stat="fd", who="b", val=8, note="Final Damage +8% for 5 s when MP >= 50% after the 2 s recovery (assumed always) - applies to the player AND the companion (user, 2026-11-12)")
row(c, "proc", id="p3", unlock=2, chance=0.2, icd=3, trig="any", pct=2600, lines=1, tgt=7, slot=1, note="angel: 20% for 2600% on 7 random targets, 3 s cooldown")
row(c, "stat", id="p4_cd", unlock=3, stat="crit_dmg", who="b", val=40, note="per 10% of current HP +4% crit damage (full HP assumed: x10)")
row(c, "stat", id="p4_as", unlock=3, stat="as", who="b", val=20, note="and +2% attack speed per 10% HP")

# ----------------------------------------------------------------------------------------------- Night Walker
c = "Night Walker"
common(c)
row(c, "hit", id="a1_1", cd=14, action=1, pct=1400, lines=1, tgt=7, atk=1, stun=1, note="shuriken 1400% on up to 7 enemies in front")
row(c, "hit", id="a1_2", cast_of="a1_1", cd=14, pct=2100, lines=1, tgt=7, note="explosion along its path 2100% on up to 7")
row(c, "stat", id="a2", cd=21, dur=8, action=1, stat="atk", who="p", val=40, note="player Attack +40% for 8 s")
row(c, "stat", id="a3", unlock=4, cd=23, dur=15, action=1, stat="fd", who="p", val=10, note="player Final Damage +10% for 15 s")
row(c, "proc", id="p1", chance=0.3, icd=0, trig="any", pct=500, lines=1, tgt=1, slot=1, note="30% for +500% on the target")
row(c, "proc", id="p2", chance=0.5, icd=1, trig="any", pct=600, lines=1, tgt=1, slot=2, note="50% for +600% on the target, 1 s cooldown")
row(c, "stack", id="p3", unlock=2, trig="skill", stat="as", who="p", val=5, smax=5, sdur=2, note="each companion skill activation: player Attack Speed +5% for 2 s, up to 5 stacks")
row(c, "proc", id="p4", unlock=3, chance=0.3, icd=0, trig="any", pct=800, lines=1, tgt=1, slot=3, note="30% for +800% on the target")

# ----------------------------------------------------------------------------------------------- Hero
c = "Hero"
common(c)
row(c, "hit", id="a1", cd=22, action=1, pct=2400, lines=1, tgt=7, atk=1, stun=2, note="2400% on 7 targets in front, stun 2 s")
row(c, "hit", id="a2", cd=9, action=1, pct=750, lines=4, tgt=8, atk=1, note="750% x4 on 8 targets")
row(c, "hit", id="a3", unlock=4, cd=19, action=1, pct=1100, lines=3, tgt=5, atk=1, note="1100% x3 on 5 targets near the main target")
row(c, "stat", id="a3_def", cast_of="a3", unlock=4, cd=19, dur=10, stat="mon_def", who="m", val=10)
row(c, "stat", id="a3_taken", cast_of="a3", unlock=4, cd=19, dur=10, stat="dmg_taken", who="m", val=10)
row(c, "stack", id="p2", chance=0.4, icd=0.5, trig="any", stat="atk", who="b", val=5, smax=5, sdur=10, note="combo: Attack +5% per stack for 10 s, 40% per attack, up to 5")
row(c, "stat", id="p4", unlock=3, stat="fd", who="c", val=15)

# ----------------------------------------------------------------------------------------------- Paladin
c = "Paladin"
common(c)
row(c, "hit", id="a1", cd=18, action=1, pct=2300, lines=1, tgt=7, atk=1)
row(c, "stat", id="a1_def", cast_of="a1", cd=18, dur=10, stat="mon_def", who="m", val=10)
row(c, "hit", id="a2", cd=25, action=1, pct=3900, lines=1, tgt=8, atk=1)
row(c, "stat", id="a2_taken", cast_of="a2", cd=25, dur=10, stat="dmg_taken", who="m", val=10)
row(c, "stat", id="a3", unlock=4, cd=30, dur=10, action=1, stat="fd", who="b", val=8)
row(c, "stat", id="p1", stat="mon_def", who="m", val=10, note="nearby targets -10% defense")
row(c, "stack", id="p2", chance=0.15, icd=0, trig="basic", stat="crit_dmg", who="b", val=15, smax=1, sdur=10, note="basic attack: 15% for crit damage +15% for 10 s")
row(c, "stat", id="p3", unlock=2, cd=10, dur=6, stat="atk", who="p", val=10, note="barrier every 10 s lasting 6 s: Attack +10% while active")
row(c, "stat", id="p4_bad", unlock=3, stat="bad", who="p", val=15)
row(c, "proc", id="p4", unlock=3, chance=0.35, icd=5, trig="basic", pct=650, lines=4, tgt=4, slot=1, note="divine brand 650% x4 on 4 targets")

# ----------------------------------------------------------------------------------------------- Dark Knight
c = "Dark Knight"
common(c)
row(c, "hit", id="a2", cd=18, action=1, pct=2100, lines=1, tgt=12, atk=1, note="rush: 2100% on 12 targets in the path")
row(c, "hit", id="a3", unlock=4, cd=17, action=1, pct=3600, lines=1, tgt=5, atk=1, stun=2, note="rock explosion 3600% on 5 targets, stun 2 s (cooldown 17 s: user)")
row(c, "stat", id="p1", stat="as", who="c", val=25, note="companion attack speed +25%")
row(c, "stat", id="p2", stat="dmg_taken", who="m", val=15, note="Evil Eye: 6 nearby targets take +15% (applied to all hits here)")
row(c, "proc", id="p3", unlock=2, chance=0.2, icd=3, trig="any", pct=290, lines=6, tgt=8, slot=1, note="Evil Eye Shock")
row(c, "proc", id="p4", unlock=3, chance=1.0, icd=5, trig="any", pct=1000, lines=2, tgt=1, slot=2, note="Revenge brand 1000% x2, 5 s cooldown")

# ----------------------------------------------------------------------------------------------- Bow Master
c = "Bow Master"
common(c)
row(c, "stat", id="sum_as", dur=20, stat="as", who="p", val=20, note="summoning effect: player Attack Speed +20% for 20 s")
row(c, "hit", id="a1", cd=13, action=1, pct=1000, lines=3, tgt=1, atk=3, note="retreats and attacks 3 times, 1000% each")
row(c, "stat", id="a1_def", cast_of="a1", cd=13, dur=10, stat="mon_def", who="m", val=15)
row(c, "dot", id="a2", cd=30, dur=20, tick=3, action=1, pct=1400, lines=1, tgt=3, note="Phoenix 20 s, 1400% every 3 s on 3 targets, cooldown 30 s (user, 2026-11-12)")
row(c, "hit", id="a3", unlock=4, cd=23, action=1, pct=800, lines=20, tgt=1, atk=20, note="20 arrows, 800% each")
row(c, "stat", id="p1", stat="crit_rate", who="b", val=15)
row(c, "dot", id="p2", tick=1, pct=145, lines=1, tgt=1, note="magic arrow 145% every 1 s on a random nearby target")
row(c, "stat", id="p2_taken", stat="dmg_taken", who="m", val=5, note="and +5% damage taken for 3 s (refreshed every second)")
row(c, "stack", id="p3", unlock=2, chance=0.1, icd=0, trig="any", stat="atk", who="c", val=1.5, smax=100, sdur=10, note="each strike: 10% for Attack +1.5% for 10 s, up to 100 stacks (user, 2026-11-12)")
row(c, "ramp", id="p4", unlock=3, ramp_mode="lin", stat="def_pen", who="c", val=1, note="def pen +1% per second, no cap")

# ----------------------------------------------------------------------------------------------- Marksman
c = "Marksman"
common(c)
row(c, "hit", id="a1", cd=13, action=1, pct=1000, lines=3, tgt=1, atk=3)
row(c, "hit", id="a2", cd=16, action=1, pct=1300, lines=3, tgt=8, atk=1, stun=1)
row(c, "hit", id="a3", unlock=4, cd=12, action=1, pct=4200, lines=1, tgt=1, atk=1, stun=2, stun_skip=1, note="marks the target; the next cast on it stuns 2 s")
row(c, "stat", id="p1", stat="crit_rate", who="b", val=15)
row(c, "stat", id="p3", unlock=2, g_ct="notPvP", stat="fd", who="c", val=20)
row(c, "stat", id="p3_pvp", unlock=2, g_ct="PvP", stat="fd", who="c", val=40, note="x2 in Arena (PvP)")

# ----------------------------------------------------------------------------------------------- Night Lord
c = "Night Lord"
common(c)
row(c, "hit", id="special_n", g_br="nonboss", pct=300, lines=4, tgt=8, note="summoning effect 300% x4 on 8 targets")
row(c, "hit", id="special_b", g_br="boss", pct=900, lines=4, note="x3 against a boss")
row(c, "hit", id="a1", cd=11, action=1, pct=1100, lines=3, tgt=10, atk=1, note="1100% x3 on 10 targets")
row(c, "dot", id="a1_dot", cast_of="a1", cd=11, dur=10, tick=1, pct=100, lines=1, tgt=10, note="then 100% every 1 s for 10 s")
row(c, "stat", id="a1_def", cast_of="a1", cd=11, dur=10, stat="mon_def_b", who="m", val=15, note="boss: defense -15% (duration 10 s, user 2026-11-12)")
row(c, "hit", id="a2", cd=10, action=1, pct=1300, lines=4, tgt=1, atk=4)
row(c, "stat", id="a3_n", unlock=4, cd=30, dur=20, action=1, stat="dmg_taken_n", who="m", val=10)
row(c, "stat", id="a3_b", cast_of="a3_n", unlock=4, cd=30, dur=20, stat="dmg_taken_b", who="m", val=20, note="boss: the damage-taken effect is doubled")
row(c, "stat", id="p2", stat="boss_dmg", who="p", val=15)
row(c, "ramp", id="p3", unlock=2, ramp_mode="exp", stat="fd", who="c", val=1.5, ramp_cap=15, note="Final Damage x1.015 per second up to 15 s")
row(c, "proc", id="p4", unlock=3, g_br="boss", chance=0.35, icd=0, trig="any", pct=1000, lines=1, tgt=1, slot=1, note="when the companion attacks a boss: 35% for 1000%, no cooldown")

# ----------------------------------------------------------------------------------------------- Shadower
c = "Shadower"
common(c)
row(c, "hit", id="special", pct=580, lines=5, tgt=1, note="summoning effect 580% x5 on 1 target")
row(c, "hit", id="a2", cd=19, action=1, pct=650, lines=3, tgt=8, atk=1, stun=2)
row(c, "hit", id="a3", unlock=4, cd=13, action=1, pct=1400, lines=2, tgt=1, atk=1, stun=1, stun_p=0.3, note="vital point 1400% x2")
row(c, "hit", id="a3_fin", cast_of="a3", unlock=4, cd=13, pct=3000, lines=1, tgt=1, note="finishing blow +3000% (30% to stun 1 s)")
row(c, "stat", id="p1", stat="crit_dmg", who="p", val=15)
row(c, "stat", id="p2", stat="as", who="p", val=15)
# Lv2 "buff-removal" proc (1000% x3, x4 on a boss) is NOT modelled: no target buffs exist in this project, so it never triggers (user, 2026-11-14)
row(c, "stunhit", id="p4", unlock=3, pct=5000, lines=1, note="a target that gets stunned/frozen takes 5000%")

# ----------------------------------------------------------------------------------------------- Buccaneer
c = "Buccaneer"
common(c)
row(c, "stat", id="sum_as", dur=15, stat="as", who="b", val=15)
row(c, "stat", id="sum_cd", dur=15, stat="crit_dmg", who="b", val=15)
row(c, "stat", id="a1_p", cd=25, dur=12, action=1, stat="fd", who="p", val=15)
row(c, "stat", id="a1_c", cast_of="a1_p", cd=25, dur=12, stat="fd", who="c", val=30, note="also: Serpent Assault 100% chance for the duration")
row(c, "hit", id="a2", unlock=3, cd=16, action=1, g_br="nonboss", pct=900, lines=3, tgt=4, atk=1, note="Octopunch (Lv3) 900% x3 on 4 targets")
row(c, "hit", id="a2_b", cast_of="a2", unlock=3, cd=16, g_br="boss", pct=900, lines=5, atk=1, note="boss: the same damage 2 more times")
row(c, "stat", id="p1_cr", stat="crit_rate", who="p", val=15, note="Lv1 passive: player crit rate +15%")
row(c, "stat", id="p1_cd", stat="crit_dmg", who="p", val=10)
row(c, "proc", id="p2", maxlvl=2, chance=0.4, icd=3, trig="basic", pct=1050, lines=3, tgt=9, slot=1, boost_src="a1_c", boost_chance=1.0, note="Sea Serpent Burst (replaced at Lv2); Assault 100% during the Lv1 active")
row(c, "proc", id="p4", unlock=2, chance=0.5, icd=3, trig="basic", pct=1750, lines=3, tgt=12, slot=2, boost_src="a1_c", boost_chance=1.0, note="Serpent Assault replaces it at Lv2")
row(c, "hit", id="p5", cast_of="a2", unlock=3, cd=16, pct=1700, lines=2, tgt=8, note="Lv3: with Octopunch a sea serpent adds 1700% x2 on 8 targets")
row(c, "stat", id="p5_mark", cast_of="a2", unlock=3, cd=16, dur=10, stat="dmg_taken", who="m", val=15, note="assault mark: +15% damage taken for 10 s")

# ----------------------------------------------------------------------------------------------- Corsair
c = "Corsair"
common(c)
row(c, "hit", id="special", pct=300, lines=5, tgt=10, stun=3, note="summoning effect 300% x5 on 10 targets, stun 3 s")
row(c, "dot", id="a1", cd=25, dur=20, tick=3, action=1, pct=950, lines=2, tgt=1, note="dual pistol crew 20 s: 950% x2 every 3 s")
row(c, "dot", id="a2", cd=15, dur=30, tick=2.5, action=1, pct=1200, lines=1, tgt=4, note="fixed cannon 30 s, 1200% every 2.5 s on 4 targets (a second cannon stacks)")
row(c, "hit", id="a3", unlock=4, cd=20, action=1, pct=3800, lines=2, tgt=5, atk=1, note="battleship 3800% x2 on 5 targets")
row(c, "dot", id="a3_dot", cast_of="a3", unlock=4, cd=20, dur=30, tick=3, pct=3300, lines=1, tgt=5, note="then 3300% every 3 s for 30 s (targets in front: 5, user 2026-11-12)")
row(c, "stat", id="p1", stat="as", who="b", val=10)
row(c, "stat", id="p2", stat="atk", who="c", val=10)
row(c, "dot", id="p3", unlock=2, tick=4, pct=1000, lines=3, tgt=3, note="Sharpshooter crew every 4 s: 1000% x3 on 3 targets")
row(c, "stat", id="p4", unlock=3, stat="skill_dmg", who="b", val=15)

for _r in ROWS:   # the engine counts overlapping summons one by one only for the last 5 casts
    if _r["kind"] == "dot" and _r["cd"] < NEVER and _r["dur"] < NEVER:
        assert _r["dur"] <= 5 * _r["cd"], f'{_r["comp"]}/{_r["id"]}: dot duration > 5 x cooldown'
assert {r["comp"] for r in ROWS} == set(COMPANIONS_ORDER), {r["comp"] for r in ROWS} ^ set(COMPANIONS_ORDER)


def is_cd_skill(r):
    """a cooldown skill that costs an action slot (the rows that define the cast order)"""
    return r["action"] == 1 and r["cd"] < NEVER


def cast_root(r):
    """canonical id of the cast a row belongs to (itself unless `cast_of` names another row)"""
    return r["id"] if r["cast_of"] == "-" else r["cast_of"]


def schedule(rows):
    """Cast timing of ONE companion's rows (kit order).  Pass the ACTIVE rows (level unlocked, content gate true) for the exact rule, or all of the
    companion's rows for the static columns of the CompanionKits sheet (identical for every active subset: see the module-level assertions).
    Returns {row id: (per, t0)} - period between casts and the first cast's time after the summon (s):
      * cooldown action skills (and the rows `cast_of` them): per = cd + CAST_TIME, t0 = START_DELAY + k * FIRST_SLOT, k = rank of the skill
        (distinct canonical ids, first appearance in kit order) among the action skills;
      * every other row with a finite cd (a passive's own timer): per = cd, t0 = 0;
      * rows without a cooldown (cd = NEVER): per = NEVER, t0 = 0 (they happen at the summon)."""
    rank = {}
    for r in rows:
        if is_cd_skill(r) and cast_root(r) not in rank:
            rank[cast_root(r)] = len(rank)
    out = {}
    for r in rows:
        if r["cd"] >= NEVER:
            out[r["id"]] = (r["cd"], 0.0)
        elif cast_root(r) in rank:
            out[r["id"]] = (r["cd"] + CAST_TIME, START_DELAY + rank[cast_root(r)] * FIRST_SLOT)
        else:
            assert r["cast_of"] == "-", f'{r["comp"]}/{r["id"]}: cast_of {r["cast_of"]} is not an active action skill'
            out[r["id"]] = (r["cd"], 0.0)
    return out


def _check_cast_links():
    by = {}
    for r in ROWS:
        by.setdefault(r["comp"], {})[r["id"]] = r
    for comp, rows in by.items():
        for r in rows.values():
            if r["cast_of"] != "-":
                root = rows[r["cast_of"]]
                assert is_cd_skill(root) and root["cast_of"] == "-", f'{comp}/{r["id"]}: cast_of must name a canonical action skill row'
                assert root["cd"] == r["cd"], f'{comp}/{r["id"]}: cooldown differs from its cast_of row'
                assert root["unlock"] <= r["unlock"] and root["maxlvl"] >= r["maxlvl"], f'{comp}/{r["id"]}: exists at a level where its cast_of row does not'
        acts = [r for r in rows.values() if is_cd_skill(r)]
        # the static order must equal the order among the active rows at every level / content: an earlier skill never unlocks later than a later one,
        # and a skill that exists only in some contents may not shift the rank of the others (its variants carry the same canonical id)
        seen = {}
        for r in acts:
            seen.setdefault(cast_root(r), []).append(r)
        last_unlock = 0
        for root, rs in seen.items():
            assert len({(x["unlock"], x["maxlvl"]) for x in rs}) == 1, f"{comp}/{root}: variants differ in level range"
            assert rows[root]["unlock"] >= last_unlock, f"{comp}/{root}: unlocks before an earlier skill"
            last_unlock = rows[root]["unlock"]
            gates = {x["g_ct"] for x in rs}
            assert gates == {"-"} or gates == {"BT", "notBT"}, f"{comp}/{root}: content-gated action skill without a counterpart ({gates})"
        sched = schedule(list(rows.values()))
        for r in rows.values():
            per, t0 = sched[r["id"]]
            assert t0 < per, f"{comp}/{r['id']}: first cast must precede the period (count formulas rely on it)"


_check_cast_links()


def rows_with_keys():
    """ROWS with the lookup keys the sheet formulas use: idkey = comp|id, pkey = comp|kind|slot (procs/ramps), skey = comp|stun|n (stunning hit rows),
    tkf, and the static cast timing columns per / t0 (see schedule())."""
    out = []
    per_kind_count = {}
    sched = {}
    for r in ROWS:
        sched.setdefault(r["comp"], []).append(r)
    sched = {comp: schedule(rs) for comp, rs in sched.items()}
    for r in ROWS:
        rr = dict(r)
        rr["idkey"] = f'{r["comp"]}|{r["id"]}'
        if r["kind"] in ("proc", "ramp") and not r["slot"]:
            k = (r["comp"], r["kind"])
            per_kind_count[k] = per_kind_count.get(k, 0) + 1
            rr["slot"] = per_kind_count[k]
        rr["pkey"] = f'{r["comp"]}|{r["kind"]}|{rr["slot"]}' if r["kind"] in ("proc", "ramp") else ""
        rr["tkf"] = int(r["dur"] // r["tick"]) if (r["kind"] == "dot" and r["tick"] < NEVER and r["dur"] < NEVER) else 0
        rr["per"], rr["t0"] = sched[r["comp"]][r["id"]]
        if r["kind"] == "hit" and r["stun"] > 0:
            k = (r["comp"], "stun")
            per_kind_count[k] = per_kind_count.get(k, 0) + 1
            rr["skey"] = f'{r["comp"]}|stun|{per_kind_count[k]}'
        else:
            rr["skey"] = ""
        out.append(rr)
    return out


def max_stun_rows():
    """most stunning/freezing hit rows of one companion (the Companion sheet gets one scalar slot per row, see companion_model.py)"""
    n = {}
    for r in ROWS:
        if r["kind"] == "hit" and r["stun"] > 0:
            n[r["comp"]] = n.get(r["comp"], 0) + 1
    return max(n.values())
