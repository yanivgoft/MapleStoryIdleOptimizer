#!/usr/bin/env python3
"""Displayed-value test of the Night Walker data (the independent real-game check of an engine-native class, no workbook exists).

THREE independent checks:

1. Every number in the user's LEVEL-1 in-game text (``data/cygnus/night_walker_ingame.md``; fresh character, every pop-up "Lv. 1", so the shown value is the BASE at factor 1.0) is reproduced
   EXACTLY by the engine's own coefficient function (``factors.SkillLevels.coeff_pct`` = base x factor[idx][total skill level], the game truncates to 1 decimal) from the
   ``(base, factor index, job step)`` stored in ``engine/data/night_walker.py``, at total skill level 1 for every job step; cooldowns / durations / mastery tiers / counts are checked
   against the data module and through the model at the unlock levels.
2. The user's HIGHER-LEVEL readings (character level 128, pop-ups "Lv. A + B": total skill level 151 / 219 / 279 / 322 for the 1st / 2nd / 3rd / 4th job tier, resolved through the
   engine's own level resolution from ``level=128`` and the four per-job skill-level bonuses 91 / 129 / 159 / 238) - ``READINGS`` below, the evidence of every growth curve that is not in
   the site table - plus the cooldown readings with Skill Cooldown Decrease 3.5 s and the Darkness Ascending -30 % mastery.  Runs in the (default) EXTENDED factor mode (levels above 300).
3. Every curve the data module does NOT list in ``CONFIRMED_BY_READINGS`` (and every sensitivity-spec passive, unlock level, cooldown, duration, hit and target count the site table covers)
   is ASSERTED equal to the live site table ``data/ref_maplestoryidle_info/site_job_skill_impact_all.json`` (job ``night-walker``): ratioE3 / value, factorIndex, jobStep, requiredLevel,
   cooldownMs, durations - read from the JSON, never hand-copied.

Plain ``python3`` runnable, also collected by pytest; prints "OK: N displayed values reproduced".
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from engine.classes import night_walker as NW  # noqa: E402
from engine.common import factors  # noqa: E402
from engine.data import night_walker as D  # noqa: E402
from engine.sens_specs import night_walker as NS  # noqa: E402
sys.path.insert(0, str(HERE))
import factor_mode  # noqa: E402
import patch_2026_11_26 as PM  # noqa: E402

FACTOR_MODE = factor_mode.pin("extended")        # production mode: growth curves continue past level 300

SITE_FILE = ROOT / "data" / "ref_maplestoryidle_info" / "site_job_skill_impact_all.json"

# Level 1 for every job step: 1st = 60 + b, 2nd = 90 + b, 3rd = 120 + b, 4th = (level - 100) x 3 clamped to 0 + b  ->  bonuses -59 / -89 / -119 / +1 give total level 1 everywhere (factor 1.0).
SL = factors.SkillLevels(1, -59, -89, -119, 1, 0)


def trunc1(v):
    """The game truncates to one decimal (1e-7 absorbs floating-point noise on exact values)."""
    return math.floor(v * 10 + 1e-7) / 10


# (shown value (%), what it is, CURVES key or None)   -- the user's level-1 pop-ups
SHOWN = [
    # ---- active skills ----
    (15.0, "Elemental Harmony: Attack Speed", "ELEMENTAL_HARMONY_AS"),
    (10.0, "Dark Elemental: Attack", "DARK_ELEMENTAL_ATTACK"),
    (38.0, "Dark Elemental: Mark of Darkness continuous damage", "MARK_OF_DARKNESS"),
    (220.0, "Shadow Spark: shuriken", "SHADOW_SPARK"),
    (330.0, "Shadow Spark: explosion", "SHADOW_SPARK_EXPLOSION"),
    (20.0, "Shadow Double: share of the original skill's damage", "SHADOW_DOUBLE_SHARE"),
    (25.0, "Darkness Ascending: Attack", "DARKNESS_ASCENDING_ATTACK"),
    (290.0, "Quintuple Star", "QUINTUPLE_STAR"),
    (2850.0, "Shadow Stitch", "SHADOW_STITCH"),
    (20.0, "Dark Evasion: Final Damage", "DARK_EVASION_FD"),
    # ---- passive skills with a scaled value in the engine ----
    (36.0, "Shadow Bat: damage", "SHADOW_BAT"),
    (90.0, "Bat Affinity: Shadow Bat damage", "BAT_AFFINITY"),
    (75.0, "Adaptive Darkness: damage per stack", "ADAPTIVE_DARKNESS"),
    (300.0, "Bat Affinity II: explosion", "BAT_AFFINITY_II_EXPLOSION"),
    (145.0, "Adaptive Darkness II: damage per stack", "ADAPTIVE_DARKNESS_II"),
    (4.0, "Shadow Momentum: Attack Speed per stack", "SHADOW_MOMENTUM_AS"),
    (120.0, "Call of Cygnus: Shadow Bat Final Damage", "CALL_OF_CYGNUS_BAT"),
    (150.0, "Call of Cygnus: Shadow Spark Final Damage", "CALL_OF_CYGNUS_SPARK"),
    (150.0, "Bat Affinity III: Final Damage of Bat Affinity II", "BAT_AFFINITY_III_FD"),
    (150.0, "Adaptive Darkness III: Final Damage of Dark Elemental", "ADAPTIVE_DARKNESS_III_FD"),
]

# always-on passives (the stat screen holds them; only their Sensitivity level delta is modelled): (shown, what, spec hook, spec base) - looked up in NS.PASSIVE_LEVELS
PASSIVES = [
    (5.0, "Agile Throwing: Attack Speed", "attack_speed_extra", 50),
    (10.0, "Physical Training: Basic Attack Damage", "basic_attack_damage_delta", 100),
    (15.0, "Throwing Mastery: Min Damage Multiplier", "min_damage_delta", 150),
    (6.0, "Critical Throw: Critical Rate", "crit_rate_delta", 60),
    (10.0, "Critical Throw: Critical Damage", "crit_damage_delta", 100),
    (18.0, "Enveloping Darkness: Boss Monster Damage", "boss_damage_delta", 180),
    (15.0, "Spirit Projection: Attack", "attack_mult_delta", 150),
    (15.0, "Vitality Siphon: Attack", "attack_mult_delta", 150),
    (15.0, "Throwing Expert: Skill Damage", "skill_damage_delta", 150),
    (30.0, "Throwing Expert: Max Damage Multiplier", "max_damage_delta", 300),   # 20.0 / 200 before the 2026-11-26 patch (patch-derived: x1.5, not a reading)
    (12.0, "Dark Blessing: Final Damage", "final_damage_delta", 120),
    (5.0, "Dark Blessing: Defense Penetration", "def_pen_delta", 50),
]

# shown base cooldown (s) / duration (s) / count: (what, shown, value in the data module)
TIMING = [
    ("Elemental Harmony cooldown", 60, D.ELEMENTAL_HARMONY["cooldown"]), ("Elemental Harmony duration", 15, D.ELEMENTAL_HARMONY["duration"]),
    ("Dark Elemental cooldown", 28, D.DARK_ELEMENTAL["cooldown"]), ("Dark Elemental duration", 12, D.DARK_ELEMENTAL["duration"]),
    ("Mark of Darkness duration", 5, D.MARK["duration"]), ("Mark of Darkness tick interval", 1, D.MARK["tick"]), ("Mark of Darkness chance (%)", 20, D.MARK["chance"]),
    ("Shadow Spark cooldown", 19, D.DAMAGE_SKILLS["SHADOW_SPARK"]["cooldown"]), ("Shadow Spark targets", 7, D.DAMAGE_SKILLS["SHADOW_SPARK"]["targets"]),
    ("Shadow Spark explosion targets", 7, D.DAMAGE_SKILLS["SHADOW_SPARK_EXPLOSION"]["targets"]),
    ("Shadow Double cooldown", 30, D.SHADOW_DOUBLE["cooldown"]), ("Shadow Double duration", 15, D.SHADOW_DOUBLE["duration"]),
    ("Darkness Ascending cooldown", 36, D.DARKNESS_ASCENDING["cooldown"]), ("Darkness Ascending duration", 15, D.DARKNESS_ASCENDING["duration"]),
    ("Quintuple Star lines", 5, D.QS_HITS[0]),
    ("Dark Omen cooldown", 38, D.DARK_OMEN["cooldown"]), ("Dark Omen pack duration", 5, D.DARK_OMEN["window"]), ("Dark Omen summoning interval", 0.7, D.DARK_OMEN["interval"]),
    ("Shadow Stitch cooldown", 27, D.DAMAGE_SKILLS["SHADOW_STITCH"]["cooldown"]), ("Shadow Stitch lines", 4, D.DAMAGE_SKILLS["SHADOW_STITCH"]["hits"]),
    ("Shadow Stitch targets", 15, D.DAMAGE_SKILLS["SHADOW_STITCH"]["targets"]),
    ("Dark Evasion cooldown", 40, D.DARK_EVASION["cooldown"]), ("Dark Evasion duration", 15, D.DARK_EVASION["duration"]),
    ("Shadow Bat chance (%)", 20, D.SHADOW_BAT_PROC["chance"]), ("Shadow Bat cooldown (ICD)", 1, D.SHADOW_BAT_PROC["icd"]),
    ("Shadow Bat max attacks", 3, D.BAT_ATTACKS["base"]), ("Shadow Bat damage decrease per attack (%)", 25, D.BAT_ATTACK_STEP * 100), ("Shadow Bat damage floor (%)", 25, D.BAT_ATTACK_FLOOR * 100),
    ("Bat Affinity: max attack count +", 1, D.BAT_ATTACKS["bat_affinity"]), ("Bat Affinity II explosion targets", 3, D.BAT_EXPLOSION["targets"]),
    ("Adaptive Darkness: max stacks 2 (= base 1 + 1)", 2, D.MARK["max_stacks"] + D.MARK["stacks"][0][1]),
    ("Adaptive Darkness II: stacks +", 1, dict(D.MARK["stacks"])[72]),
    ("Adaptive Darkness II: Mark chance multiplier", 2, D.MARK["chance_normal_mult"][1]),
    ("Shadow Momentum duration", 2, D.SHADOW_MOMENTUM["duration"]), ("Shadow Momentum max stacks", 5, D.SHADOW_MOMENTUM["max_stacks"]),
]

# the masteries (level, shown value): thresholds and values of the data module
MASTERIES = [
    ("Dark Elemental duration +50 % (Lv21)", (21, 1.5), D.DARK_ELEMENTAL["duration_mastery"]),
    ("Shadow Bat chance +15 % (Lv24)", (24, 15), D.SHADOW_BAT_PROC["chance_mastery"]),
    ("Shadow Spark damage +80 % (Lv39)", {39: 80}, D.DAMAGE_SKILLS["SHADOW_SPARK"]["mastery"]),
    ("Shadow Spark explosion follows the +80 % (Lv39)", {39: 80}, D.DAMAGE_SKILLS["SHADOW_SPARK_EXPLOSION"]["mastery"]),
    ("Shadow Bat damage +50 % (Lv44)", (44, 50), D.BAT_DAMAGE_MASTERY),
    ("Shadow Spark stun 1 s (Lv49)", (49, 1.0), (D.PLAYER_STUN[0]["min_level"], D.PLAYER_STUN[0]["dur"])),
    ("Mark max stack +1 (Lv54)", (54, 1), D.MARK["stacks"][1]),
    ("Shadow Double: Basic Attack Damage +10 (Lv68)", (68, 10), D.SHADOW_DOUBLE["ba_mastery"]),
    ("Bat Affinity II damage +50 % (Lv73)", (73, 50), D.BAT_EXPLOSION["mastery"]),
    ("Darkness Ascending cooldown -30 % (Lv78)", (78, 0.7), D.DARKNESS_ASCENDING["haste"]),
    ("Adaptive Darkness II damage +50 % (Lv82)", (82, 50), D.MARK["mastery"]),
    ("Shadow Momentum: Attack +10 % (Lv90)", (90, 10), D.SHADOW_MOMENTUM["attack_mastery"]),
    ("Bat Affinity II targets +1 (Lv94)", (94, 1), D.BAT_EXPLOSION["targets_mastery"]),
    ("Quintuple Star damage chain 10/11/12/13/14/15 (Lv102/106/116/120/128/132)", {102: 10, 106: 11, 116: 12, 120: 13, 128: 14, 132: 15}, D.QS_MASTERY),
    ("Shadow Double duration +30 % (Lv104)", (104, 1.3), D.SHADOW_DOUBLE["duration_mastery"]),
    ("Dark Omen interval -0.2 s (Lv108)", (108, 0.5), D.DARK_OMEN["interval_mastery"]),
    ("Quintuple Star Boss Monster Damage +10 / +10 (Lv111 / Lv124)", {111: 10, 124: 10}, D.QS_BOSS_MASTERY),
    ("Shadow Stitch damage +50 % (Lv113)", {113: 50}, D.DAMAGE_SKILLS["SHADOW_STITCH"]["mastery"]),
    ("Bat Affinity III Final Damage boost +50 % (Lv118)", (118, 1.5), D.BAT_EXPLOSION["boost"]),
    ("Adaptive Darkness III Final Damage boost +50 % (Lv122)", (122, 1.5), D.MARK["boost"]),
    ("Dark Evasion duration +50 % (Lv126)", (126, 1.5), D.DARK_EVASION["duration_mastery"]),
    ("Dark Omen: 4 more bats at once (Lv130)", (130, 4), D.DARK_OMEN["burst"]),
    ("Adaptive Darkness III Weaken +5 % (Lv134)", (134, 5.0), D.MARK["weaken"]),
    ("Quintuple Star strike +1 (Lv136)", (5, 136, 6), D.QS_HITS),
    ("Bat Affinity III: Shadow Bat max attacks +2 (Lv138)", (138, 2), D.BAT_ATTACKS["mastery"]),
]


# ---- the higher-level readings (character level 128; total skill level = tier base + that tier's displayed bonus: 1st 60+91, 2nd 90+129, 3rd 120+159, 4th 84+238) ----
READING_LEVEL = 128
READING_BONUS = dict(skill_lvl_1st=91, skill_lvl_2nd=129, skill_lvl_3rd=159, skill_lvl_4th=238, skill_lvl_all=0)
TOTAL_OF_STEP = {1: 151, 2: 219, 3: 279, 4: 322}

# (what, level-1 base in %, shown value at the total level, job step, factor index, source)
# source: ("curve", CURVES key) = a number the engine scales (checked against D.CURVES AND evaluated through the model);
#         ("passive", hook, base in tenths) = a Sensitivity passive (engine/sens_specs/night_walker.py PASSIVE_LEVELS);  None = not modelled (no DPS effect), curve checked as a pure number.
READINGS = [
    ("Dark Elemental: Attack", 10, 16.0, 1, 21, ("curve", "DARK_ELEMENTAL_ATTACK")),
    ("Dark Elemental: Mark of Darkness damage", 38, 66.6, 1, 12, ("curve", "MARK_OF_DARKNESS")),
    ("Shadow Spark: shuriken", 220, 460.9, 2, 12, ("curve", "SHADOW_SPARK")),
    ("Shadow Spark: explosion", 330, 691.3, 2, 12, ("curve", "SHADOW_SPARK_EXPLOSION")),
    ("Shadow Double: share of the original's damage", 20, 36.7, 3, 22, ("curve", "SHADOW_DOUBLE_SHARE")),
    ("Darkness Ascending: Attack", 25, 52.9, 3, 21, ("curve", "DARKNESS_ASCENDING_ATTACK")),
    ("Darkness Ascending: HP recovery", 4, 7.3, 3, 22, None),
    ("Quintuple Star", 290, 663.5, 4, 21, ("curve", "QUINTUPLE_STAR")),
    ("Shadow Stitch", 2850, 7438.5, 4, 12, ("curve", "SHADOW_STITCH")),
    ("Dark Evasion: Final Damage", 20, 45.7, 4, 21, ("curve", "DARK_EVASION_FD")),
    ("Dark Evasion: damage taken", 20, 39.3, 4, 22, None),
    ("Shadow Bat", 36, 57.7, 1, 21, ("curve", "SHADOW_BAT")),
    ("Agile Throwing: Attack Speed", 5, 8.2, 2, 22, ("passive", "attack_speed_extra", 50)),
    ("Physical Training: Basic Attack Damage", 10, 16.5, 2, 22, ("passive", "basic_attack_damage_delta", 100)),
    ("Bat Affinity: Shadow Bat damage", 90, 168.8, 2, 21, ("curve", "BAT_AFFINITY")),
    ("Throwing Mastery: Min Damage Multiplier", 15, 24.8, 2, 22, ("passive", "min_damage_delta", 150)),
    ("Critical Throw: Critical Rate", 6, 9.9, 2, 22, ("passive", "crit_rate_delta", 60)),
    ("Critical Throw: Critical Damage", 10, 16.5, 2, 22, ("passive", "crit_damage_delta", 100)),
    ("Adaptive Darkness: damage per stack", 75, 157.1, 2, 12, ("curve", "ADAPTIVE_DARKNESS")),
    ("Enveloping Darkness: Max HP", 10, 18.3, 3, 22, None),
    ("Enveloping Darkness: Boss Monster Damage", 18, 33.0, 3, 22, ("passive", "boss_damage_delta", 180)),
    ("Bat Affinity II: explosion", 300, 634.8, 3, 21, ("curve", "BAT_AFFINITY_II_EXPLOSION")),
    ("Adaptive Darkness II: damage per stack", 145, 347.2, 3, 12, ("curve", "ADAPTIVE_DARKNESS_II")),
    ("Shadow Momentum: Attack Speed per stack", 4, 7.3, 3, 22, ("curve", "SHADOW_MOMENTUM_AS")),
    ("Spirit Projection: Attack", 15, 27.5, 3, 22, ("passive", "attack_mult_delta", 150)),
    ("Call of Cygnus: Shadow Bat Final Damage", 120, 1082.4, 4, 23, ("curve", "CALL_OF_CYGNUS_BAT")),
    ("Call of Cygnus: Shadow Spark Final Damage", 150, 1353.0, 4, 23, ("curve", "CALL_OF_CYGNUS_SPARK")),
    ("Bat Affinity III: Final Damage", 150, 343.2, 4, 21, ("curve", "BAT_AFFINITY_III_FD")),
    ("Adaptive Darkness III: Final Damage", 150, 343.2, 4, 21, ("curve", "ADAPTIVE_DARKNESS_III_FD")),
    ("Vitality Siphon: Attack", 15, 29.4, 4, 22, ("passive", "attack_mult_delta", 150)),
    ("Vitality Siphon: barrier", 10, 19.6, 4, 22, None),
    ("Throwing Expert: Skill Damage", 15, 29.4, 4, 22, ("passive", "skill_damage_delta", 150)),
    ("Throwing Expert: Max Damage Multiplier", 30, 58.9, 4, 22, ("passive", "max_damage_delta", 300)),   # 20 / 39.3 / 200 before the 2026-11-26 patch (patch-derived x1.5)
    ("Dark Blessing: Final Damage", 12, 23.5, 4, 22, ("passive", "final_damage_delta", 120)),
    ("Dark Blessing: Defense Penetration", 5, 9.8, 4, 22, ("passive", "def_pen_delta", 50)),
]

# Skill Cooldown Decrease 3.5 s: the pop-up shows "base (-reduction)": (what, base cooldown, shown reduction, model key of D / cd_of)
READING_CDR = 3.5
CDR_READINGS = [
    ("Elemental Harmony 60(-3.5)", 60, 3.5, "ELEMENTAL_HARMONY"), ("Dark Omen 38(-3.5)", 38, 3.5, "DARK_OMEN"), ("Dark Elemental 28(-3.5)", 28, 3.5, "DARK_ELEMENTAL"),
    ("Shadow Spark 19(-3.5)", 19, 3.5, "SHADOW_SPARK"), ("Shadow Stitch 27(-3.5)", 27, 3.5, "SHADOW_STITCH"), ("Dark Evasion 40(-3.5)", 40, 3.5, "DARK_EVASION"),
    ("Shadow Double 30(-3.5)", 30, 3.5, "SHADOW_DOUBLE"),
    # Darkness Ascending: 36 x 0.3 (Lv78 Reuse mastery, -30 %) + 3.5 = 14.3
    ("Darkness Ascending 36(-14.3) = 36 x 0.3 + 3.5", 36, 14.3, "DARKNESS_ASCENDING"),
]


def _tuple_eq(a, b):
    if isinstance(a, dict) or isinstance(b, dict):
        return a == b
    return len(a) == len(b) and all(math.isclose(x, y, rel_tol=1e-12) for x, y in zip(a, b))


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------- check 1: level-1 values
def check_values():
    bad = []
    for step in (1, 2, 3, 4):
        if SL.input_level(step) != 1:
            bad.append(f"job step {step}: total level {SL.input_level(step)} != 1")
    for shown, what, key in SHOWN:
        base, fidx, step = D.CURVES[key]
        got = trunc1(SL.coeff_pct(base, fidx, fidx is not None, step))
        if got != shown:
            bad.append(f"{what}: engine {got} (raw {SL.coeff_pct(base, fidx, fidx is not None, step)!r}) != shown {shown}")
    by_hook = {}
    for p in NS.PASSIVE_LEVELS:
        by_hook.setdefault((p.hook, p.base), []).append(p)
    for shown, what, hook, base in PASSIVES:
        ps = by_hook.get((hook, base))
        if not ps:
            bad.append(f"{what}: no PassiveLevel({hook!r}, base {base}) in engine/sens_specs/night_walker.py")
            continue
        p = ps[0]
        got = trunc1(SL.coeff_pct(p.base, p.fidx, True, p.step))
        if got != shown:
            bad.append(f"{what}: engine {got} != shown {shown}")
    for what, shown, got in TIMING:
        if not math.isclose(shown, got, rel_tol=1e-12):
            bad.append(f"{what}: data {got} != shown {shown}")
    for what, shown, got in MASTERIES:
        if not _tuple_eq(shown, got):
            bad.append(f"{what}: data {got} != shown {shown}")
    return bad


def check_model_levels():
    """The model resolves the same unlocks / counts / cooldowns as the in-game text at the threshold levels (default Chapter Hunt inputs, no companion)."""
    def model(level, **over):
        return NW.model(dict(NW.defaults("Chapter Hunt"), level=level, skill_cooldown_decrease=0.0, **over))
    bad = []

    def eq(what, got, want):
        if not math.isclose(float(got), float(want), rel_tol=1e-12, abs_tol=1e-12):
            bad.append(f"{what}: model {got} != {want}")
    eq("Darkness Ascending cooldown at Lv77", model(77).cd_of["DARKNESS_ASCENDING"], 36)
    eq("Darkness Ascending cooldown at Lv78 (-30 %)", model(78).cd_of["DARKNESS_ASCENDING"], 25.2)
    eq("Shadow Bat attacks at Lv39", model(39).bat_attacks, 3)
    eq("Shadow Bat attacks at Lv40 (+1 Bat Affinity)", model(40).bat_attacks, 4)
    eq("Shadow Bat attacks at Lv138 (+2)", model(138).bat_attacks, 6)
    eq("Mark max stacks at Lv49", model(49).mark_max, 1)
    eq("Mark max stacks at Lv50 (Adaptive Darkness: 2)", model(50).mark_max, 2)
    eq("Mark max stacks at Lv53", model(53).mark_max, 2)
    eq("Mark max stacks at Lv54", model(54).mark_max, 3)
    eq("Mark max stacks at Lv72", model(72).mark_max, 4)
    eq("Mark max stacks at Lv9 (Dark Elemental locked, base 1)", model(9).mark_max, 1)
    eq("Bat Affinity II explosion targets at Lv93", model(93).explosion_targets, 3)
    eq("Bat Affinity II explosion targets at Lv94", model(94).explosion_targets, 4)
    eq("Shadow Spark stun off at Lv48", model(48).pl_on, False)
    eq("Shadow Spark stun on at Lv49", model(49).pl_on, True)
    eq("Quad Star / Lucky Seven / Triple Throw are not rows", len([k for k in D.DPS_ROW_ORDER if "QUAD" in k or "LUCKY" in k or "TRIPLE" in k]), 0)
    if model(99).qs_dps != 0.0 or model(99).skill_dps["SHADOW_STITCH"] != 0.0:
        bad.append("below level 100 there is no basic attack and Shadow Stitch (Lv105) is locked")
    if model(100).qs_dps <= 0.0:
        bad.append("Quintuple Star must exist at level 100")
    # Shadow Bat's per-attack damage ladder 1, .75, .5, .25, .25, .25
    eq("bat attack ladder (6 attacks)", NW.bat_attack_sum(6), 3.0)
    eq("bat attack ladder (3 attacks)", NW.bat_attack_sum(3), 2.25)
    # Dark Omen: 5 s / 0.7 s = 7 bats, 5 s / 0.5 s = 10 bats, +4 at Lv130
    import engine.common.fight as fm
    eq("Dark Omen bats per cast at Lv103", fm.ticks(D.DARK_OMEN["window"], D.DARK_OMEN["interval"]), 7)
    eq("Dark Omen bats per cast at Lv108", fm.ticks(D.DARK_OMEN["window"], D.DARK_OMEN["interval_mastery"][1]), 10)
    return bad


def check_readings():
    """The higher-level readings reproduced (truncated to 1 decimal) through the engine's own level resolution and coefficient function, in the default (extended) factor mode."""
    bad = []
    with factors.legacy_clamp(False):
        m = NW.model(dict(NW.defaults("Chapter Hunt"), level=READING_LEVEL, skill_cooldown_decrease=0.0, **READING_BONUS))
        for step, total in TOTAL_OF_STEP.items():
            if m.sl.input_level(step) != total:
                bad.append(f"job step {step}: engine total skill level {m.sl.input_level(step)} != the readings' {total}")
        if factors.legacy_clamp_enabled():
            bad.append("the readings need the extended factor mode (levels above 300)")
        for what, base, shown, step, idx, src in READINGS:
            if src is None:
                got = trunc1(m.sl.coeff_pct(base * 10, idx, True, step))
            elif src[0] == "curve":
                cb, cidx, cstep = D.CURVES[src[1]]
                if (cb, cidx, cstep) != (base * 10, idx, step):
                    bad.append(f"{what}: CURVES[{src[1]}] = {(cb, cidx, cstep)} != the reading's {(base * 10, idx, step)}")
                got = trunc1(m.curve_pct(src[1]))
            else:
                ps = [p for p in NS.PASSIVE_LEVELS if p.hook == src[1] and p.base == src[2] and p.step == step]
                if len(ps) != 1:
                    bad.append(f"{what}: no unique PassiveLevel({src[1]!r}, base {src[2]}, step {step})")
                    continue
                if ps[0].fidx != idx:
                    bad.append(f"{what}: PassiveLevel factor index {ps[0].fidx} != {idx}")
                got = trunc1(m.sl.coeff_pct(ps[0].base, ps[0].fidx, True, ps[0].step))
            if got != shown:
                bad.append(f"{what}: engine {got} != shown {shown} (total level {TOTAL_OF_STEP[step]}, factor {idx})")
        # the model's own derived values (what the Result shows) for the three live buffs
        r = NW.compute(dict(NW.defaults("Chapter Hunt"), level=READING_LEVEL, **READING_BONUS))["derived"]
        for key, shown in (("dark_elemental_attack", 16.0), ("darkness_ascending_attack", 52.9), ("dark_evasion_final_damage", 45.7)):
            if trunc1(r[key]) != shown:
                bad.append(f"derived {key}: {r[key]} (trunc {trunc1(r[key])}) != shown {shown}")
        # the cooldown readings: base cooldown (Darkness Ascending after its Lv78 -30 % mastery) minus the effective cooldown with CDR 3.5
        mc = NW.model(dict(NW.defaults("Chapter Hunt"), level=READING_LEVEL, skill_cooldown_decrease=READING_CDR, **READING_BONUS))
        for what, base, shown, key in CDR_READINGS:
            if key == "ELEMENTAL_HARMONY":
                cd = D.ELEMENTAL_HARMONY["cooldown"]
            elif key == "DARK_OMEN":
                cd = D.DARK_OMEN["cooldown"]
            elif key == "DARK_ELEMENTAL":
                cd = D.DARK_ELEMENTAL["cooldown"]
            elif key == "DARK_EVASION":
                cd = D.DARK_EVASION["cooldown"]
            elif key == "SHADOW_DOUBLE":
                cd = D.SHADOW_DOUBLE["cooldown"]
            else:
                cd = mc.cd_of[key]
            if key in mc.cd_of and not math.isclose(cd, mc.cd_of[key], rel_tol=1e-12):
                bad.append(f"{what}: data cooldown {cd} != model cd_of {mc.cd_of[key]}")
            reduction = round(base - mc.fight.eff_cooldown(cd, True), 9)
            if not math.isclose(reduction, shown, rel_tol=0, abs_tol=1e-9):
                bad.append(f"{what}: engine reduction {reduction} != shown {shown}")
        if not math.isclose(mc.cd_of["DARKNESS_ASCENDING"], 36 * 0.7, rel_tol=1e-12):
            bad.append("Darkness Ascending base cooldown at level 128 must be 36 x 0.7 (Lv78 mastery)")
    return bad


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------- check 2: the site table
def _site():
    d = json.loads(SITE_FILE.read_text())
    job = next(j for j in d["jobs"] if j["id"] == "night-walker")
    return {s["displayName"]: s for s in job["skills"]}


def check_site():
    """Assert the engine data against the site table; returns (problems, number of facts checked)."""
    S = _site()
    bad = []
    n = 0

    def eq(what, got, want):
        nonlocal n
        n += 1
        if got != want and not (isinstance(got, float) and isinstance(want, (int, float)) and math.isclose(got, want, rel_tol=1e-12)):
            bad.append(f"site {what}: engine {got!r} != site {want!r}")

    def curve(key, name, src, tag):
        """CURVES[key] == the site op (base, factor index, job step)."""
        base, fidx, step = D.CURVES[key]
        sk = S[name]
        eq(f"{key} job step", step, sk["jobStep"])
        if src == "damage":
            op = sk["directOps"][tag]
            eq(f"{key} ratioE3", base, op["ratioE3"])
            eq(f"{key} factorIndex", fidx, op["factorIndex"])
        elif src == "stat":
            op = next(o for o in sk["statOps"] if o["statType"] == tag)
            value = op["value"] if op.get("value") is not None else int(op["valueExpression"].split("*")[-1])      # Shadow Momentum: "$CreatureStateCount(...) * 40"
            eq(f"{key} value", base, value)
            eq(f"{key} factorIndex", fidx, op["factorIndex"])
        elif src == "mod":
            ops = [o for o in sk["otherOps"] if o["type"] == "ModSkillStat" and o["rawValues"][0] == tag]
            assert ops, f"{name}: no ModSkillStat on skill {tag}"
            eq(f"{key} FinalDamage value", base, int(ops[0]["rawValues"][3]))
            eq(f"{key} factorIndex", fidx, ops[0]["factorIndex"])
        elif src == "servant":
            ops = [o for o in sk["otherOps"] if o["type"] == "SetServantSkill" and o["rawValues"][1] == tag]
            assert ops, f"{name}: no SetServantSkill for skill {tag}"
            eq(f"{key} share value", base, int(ops[0]["rawValues"][3]))
            eq(f"{key} factorIndex", fidx, ops[0]["factorIndex"])
            eq(f"{key} job step (valueLevelFactors)", step, ops[0]["valueLevelFactors"][0])

    curve("SHADOW_SPARK", "Shadow Spark", "damage", 0)
    curve("SHADOW_STITCH", "Shadow Stitch", "damage", 0)
    curve("DARK_ELEMENTAL_ATTACK", "Dark Elemental", "stat", "Attack")
    curve("DARKNESS_ASCENDING_ATTACK", "Darkness Ascending", "stat", "Attack")
    curve("DARK_EVASION_FD", "Dark Evasion", "stat", "FinalDamage")
    curve("SHADOW_MOMENTUM_AS", "Shadow Momentum", "stat", "AttackSpeed")
    curve("CALL_OF_CYGNUS_BAT", "Call of Cygnus", "mod", "131042")
    curve("CALL_OF_CYGNUS_SPARK", "Call of Cygnus", "mod", "132020")
    n_extra = next(o for o in S["Call of Cygnus"]["otherOps"] if o["rawValues"][0] == "132021")        # the explosion line carries the same Final Damage
    eq("Call of Cygnus on the explosion line: value", D.CURVES["CALL_OF_CYGNUS_SPARK"][0], int(n_extra["rawValues"][3]))
    eq("Call of Cygnus on the explosion line: factorIndex", D.CURVES["CALL_OF_CYGNUS_SPARK"][1], n_extra["factorIndex"])
    curve("BAT_AFFINITY_III_FD", "Bat Affinity III", "mod", "131043")
    curve("ADAPTIVE_DARKNESS_III_FD", "Adaptive Darkness III", "mod", "131033")
    curve("SHADOW_DOUBLE_SHARE", "Shadow Double", "servant", "134010")
    # Elemental Harmony: the site carries no factorIndex = does not scale
    eh = next(o for o in S["Elemental Harmony"]["statOps"] if o["statType"] == "AttackSpeed")
    eq("ELEMENTAL_HARMONY_AS value", D.CURVES["ELEMENTAL_HARMONY_AS"][0], eh["value"])
    eq("ELEMENTAL_HARMONY_AS factorIndex (none = non-scaling)", D.CURVES["ELEMENTAL_HARMONY_AS"][1], eh.get("factorIndex"))
    # the sensitivity spec's passives: value, factor index, job step, unlock level
    passive_sources = [("Agile Throwing", "AttackSpeed"), ("Physical Training", "BaseAttackPower"), ("Throwing Mastery", "MinDamageRatio"), ("Critical Throw", "CriticalChance"),
                       ("Critical Throw", "CriticalPower"), ("Enveloping Darkness", "AttackPowerToBoss"), ("Spirit Projection", "Attack"), ("Vitality Siphon", "Attack"),
                       ("Throwing Expert", "SkillPower"), ("Throwing Expert", "MaxDamageRatio"), ("Dark Blessing", "FinalDamage"), ("Dark Blessing", "PiercePower")]
    eq("number of sensitivity passives", len(NS.PASSIVE_LEVELS), len(passive_sources))
    for p, (name, stat) in zip(NS.PASSIVE_LEVELS, passive_sources):
        sk = S[name]
        op = next(o for o in sk["statOps"] if o["statType"] == stat)
        eq(f"{name}/{stat} value", PM.pre_patch_base("night_walker", p.hook, p.base), op["value"])   # (the site snapshot predates the 2026-11-26 patch)
        eq(f"{name}/{stat} factorIndex", p.fidx, op["factorIndex"])
        eq(f"{name}/{stat} job step", p.step, sk["jobStep"])
        eq(f"{name}/{stat} unlock level", p.unlock, sk["requiredLevel"])
    # unlock levels of every engine skill the site lists (Elemental Harmony: the site says 1 = from the start)
    unlock_names = {"QUINTUPLE_STAR": "Quintuple Star", "SHADOW_DOUBLE": "Shadow Double", "SHADOW_SPARK": "Shadow Spark", "SHADOW_STITCH": "Shadow Stitch", "SHADOW_BAT": "Shadow Bat",
                    "BAT_EXPLOSION": "Bat Affinity II", "MARK_OF_DARKNESS": "Dark Elemental", "DARK_ELEMENTAL": "Dark Elemental", "BAT_AFFINITY": "Bat Affinity",
                    "ADAPTIVE_DARKNESS": "Adaptive Darkness", "BAT_AFFINITY_II": "Bat Affinity II", "DARKNESS_ASCENDING": "Darkness Ascending",
                    "ADAPTIVE_DARKNESS_II": "Adaptive Darkness II", "SHADOW_MOMENTUM": "Shadow Momentum", "CALL_OF_CYGNUS": "Call of Cygnus", "DARK_OMEN": "Dark Omen",
                    "BAT_AFFINITY_III": "Bat Affinity III", "ADAPTIVE_DARKNESS_III": "Adaptive Darkness III", "DARK_EVASION": "Dark Evasion"}
    for key, name in unlock_names.items():
        eq(f"{key} unlock level", D.UNLOCK_LEVEL[key], S[name]["requiredLevel"])
    eq("ELEMENTAL_HARMONY unlock level (site 1 = from the start)", max(D.UNLOCK_LEVEL["ELEMENTAL_HARMONY"], 1), S["Elemental Harmony"]["requiredLevel"])
    assert set(D.UNLOCK_LEVEL) == set(unlock_names) | {"ELEMENTAL_HARMONY", "SHADOW_SPARK_EXPLOSION"}, "UNLOCK_LEVEL keys not covered by the site check"
    eq("SHADOW_SPARK_EXPLOSION unlock level (same cast)", D.UNLOCK_LEVEL["SHADOW_SPARK_EXPLOSION"], D.UNLOCK_LEVEL["SHADOW_SPARK"])
    # cooldowns (s), durations, hits and targets
    cds = {"Shadow Spark": D.DAMAGE_SKILLS["SHADOW_SPARK"]["cooldown"], "Shadow Stitch": D.DAMAGE_SKILLS["SHADOW_STITCH"]["cooldown"], "Dark Omen": D.DARK_OMEN["cooldown"],
           "Dark Elemental": D.DARK_ELEMENTAL["cooldown"], "Darkness Ascending": D.DARKNESS_ASCENDING["cooldown"], "Dark Evasion": D.DARK_EVASION["cooldown"],
           "Shadow Double": D.SHADOW_DOUBLE["cooldown"], "Elemental Harmony": D.ELEMENTAL_HARMONY["cooldown"], "Shadow Bat": D.SHADOW_BAT_PROC["icd"]}
    for name, cd in cds.items():
        eq(f"{name} cooldown (s)", cd * 1000, S[name]["cooldownMs"])
    eq("Elemental Harmony duration (s)", D.ELEMENTAL_HARMONY["duration"] * 1000, next(o for o in S["Elemental Harmony"]["statOps"] if o["statType"] == "AttackSpeed")["durationMs"])
    eq("Dark Evasion duration (s)", D.DARK_EVASION["duration"] * 1000, S["Dark Evasion"]["statOps"][0]["durationMs"])
    eq("Dark Elemental duration (s)", D.DARK_ELEMENTAL["duration"] * 1000, next(o for o in S["Dark Elemental"]["otherOps"] if o["type"] == "UsePassiveSkill")["durationMs"])
    eq("Shadow Double duration (s)", D.SHADOW_DOUBLE["duration"] * 1000, next(o for o in S["Shadow Double"]["otherOps"] if o["type"] == "SpawnServant")["durationMs"])
    eq("Shadow Momentum duration (s)", D.SHADOW_MOMENTUM["duration"] * 1000, next(o for o in S["Shadow Momentum"]["otherOps"] if o["type"] == "State")["durationMs"])
    eq("Shadow Spark hits", D.DAMAGE_SKILLS["SHADOW_SPARK"]["hits"], S["Shadow Spark"]["directOps"][0]["hitCount"])
    eq("Shadow Spark max targets", D.DAMAGE_SKILLS["SHADOW_SPARK"]["targets"], S["Shadow Spark"]["directOps"][0]["maxHitCount"])
    eq("Shadow Stitch hits", D.DAMAGE_SKILLS["SHADOW_STITCH"]["hits"], S["Shadow Stitch"]["directOps"][0]["hitCount"])
    eq("Shadow Stitch max targets", D.DAMAGE_SKILLS["SHADOW_STITCH"]["targets"], S["Shadow Stitch"]["directOps"][0]["maxHitCount"])
    eq("Shadow Spark stun (s)", D.PLAYER_STUN[0]["dur"] * 1000, next(o for o in S["Shadow Spark"]["otherOps"] if o["type"] == "Stun")["durationMs"])
    eq("Shadow Bat chance (%)", D.SHADOW_BAT_PROC["chance"] * 10, S["Shadow Bat"]["triggerRatio"])
    # the curves the site does not cover are exactly the ones the user's readings confirm (so a curve cannot be silently provisional or silently confirmed)
    site_covered = {"SHADOW_SPARK", "SHADOW_STITCH", "DARK_ELEMENTAL_ATTACK", "DARKNESS_ASCENDING_ATTACK", "DARK_EVASION_FD", "SHADOW_MOMENTUM_AS", "CALL_OF_CYGNUS_BAT",
                    "CALL_OF_CYGNUS_SPARK", "BAT_AFFINITY_III_FD", "ADAPTIVE_DARKNESS_III_FD", "SHADOW_DOUBLE_SHARE", "ELEMENTAL_HARMONY_AS"}
    eq("PROVISIONAL is empty", sorted(D.PROVISIONAL), [])
    eq("CONFIRMED_BY_READINGS == CURVES minus the site-covered curves", sorted(D.CONFIRMED_BY_READINGS), sorted(set(D.CURVES) - site_covered))
    by_key = {src[1]: (shown, TOTAL_OF_STEP[step]) for _w, _b, shown, step, _i, src in READINGS if src and src[0] == "curve"}
    for key, (shown, total) in D.CONFIRMED_BY_READINGS.items():
        eq(f"CONFIRMED_BY_READINGS[{key}] (shown value, total level) == the READINGS table", (shown, total), by_key.get(key))
    return bad, n


def run(verbose=True):
    bad = check_values() + check_model_levels() + check_readings()
    site_bad, site_n = check_site()
    bad += site_bad
    n = len(SHOWN) + len(PASSIVES) + len(TIMING) + len(MASTERIES) + len(READINGS) + len(CDR_READINGS) + 3
    if verbose:
        if bad:
            print("FAIL:")
            for b in bad:
                print("  -", b)
        else:
            print(f"OK: {n} displayed values reproduced ({len(SHOWN) + len(PASSIVES)} level-1 values, {len(READINGS)} higher-level readings at total level 151/219/279/322, "
                  f"{len(CDR_READINGS)} cooldown readings with CDR {READING_CDR}, timings / masteries / buff derived values)")
            print(f"OK: {site_n} site-table facts equal the engine data ({len(D.CURVES) - len(D.CONFIRMED_BY_READINGS)} site-confirmed curves, "
                  f"{len(D.CONFIRMED_BY_READINGS)} confirmed by the readings, {len(D.PROVISIONAL)} PROVISIONAL)")
    return n, site_n, bad


def test_night_walker_displayed_values():
    n, site_n, bad = run(verbose=False)
    assert n > 0 and site_n > 0 and not bad, "\n".join(bad)


if __name__ == "__main__":
    _n, _sn, _bad = run()
    sys.exit(1 if _bad else 0)
