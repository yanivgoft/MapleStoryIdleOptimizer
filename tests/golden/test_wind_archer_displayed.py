#!/usr/bin/env python3
"""Displayed-value test of the Wind Archer data (the only real-game check of this engine-native, PROVISIONAL, unpublished class; no workbook exists).

SOURCE: ``data/cygnus/wind_archer_ingame.md`` = the user's LEVEL-1 pop-ups (fresh character, "Lv. 1" everywhere: the displayed value IS the base, factor 1.0).  There is NO site cross-check
for this class and no higher-level reading yet, so every factor index (the growth curve) is a convention (Dawn Warrior / Night Walker / Blaze Wizard: damage 12, basic attack / active buffs
21, passives 22, Call of Cygnus 23) and every curve is PROVISIONAL (``engine/data/wind_archer.py`` ``CURVES`` / ``PROVISIONAL``).  What this test pins is therefore only what a level-1 reading can
pin: every transcribed damage / buff / passive / mastery value, hit and target count, cooldown, duration, interval and unlock level is reproduced by the engine at total skill level 1 (all
skill-level bonuses set to -1000 so every job tier clamps to level 1, factor 1.0), through the engine's own coefficient function (``factors.SkillLevels.coeff_pct`` with the game's truncation to one
decimal) AND through the model's resolved values (``m.skills``, buff values, uptimes).  Once the user supplies a higher-level reading per skill (data/cygnus/README.md, the Blaze Wizard test is the
template), rows move out of ``PROVISIONAL`` and get a second reading here.

Plain ``python3`` runnable, also collected by pytest; prints "OK: N displayed values reproduced".
"""
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from engine.classes import wind_archer as WA  # noqa: E402
from engine.common import factors  # noqa: E402
from engine.data import wind_archer as D  # noqa: E402
sys.path.insert(0, str(HERE))
import factor_mode  # noqa: E402

FACTOR_MODE = factor_mode.pin("extended")        # production mode: growth curves continue past level 300

LEVEL = 140                                  # character level of the model checks: everything is unlocked
LEVEL1 = dict(skill_lvl_1st=-1000, skill_lvl_2nd=-1000, skill_lvl_3rd=-1000, skill_lvl_4th=-1000, skill_lvl_all=-1000)     # every job tier clamps to total level 1
SL1 = factors.SkillLevels(LEVEL, -1000, -1000, -1000, -1000, -1000)

# (name, shown value (%), CURVES key)
TABLE = [
    ("Storm Elemental: Attack", 12.0, "STORM_ELEMENTAL_ATTACK"), ("Storm Elemental: Damage", 4.0, "STORM_ELEMENTAL_DAMAGE"),
    ("Spiraling Vortex", 250.0, "SPIRALING_VORTEX"), ("Pinpoint Pierce: first arrow", 330.0, "PINPOINT_PIERCE_ARROW1"), ("Pinpoint Pierce: second arrow", 740.0, "PINPOINT_PIERCE_ARROW2"),
    ("Song of Heaven", 780.0, "SONG_OF_HEAVEN"), ("Fairy Spiral (basic attack)", 290.0, "FAIRY_SPIRAL"),
    ("Trifling Wind I", 36.0, "TRIFLING_WIND_I"), ("Trifling Wind II", 100.0, "TRIFLING_WIND_II"), ("Trifling Wind III: Final Damage", 100.0, "TRIFLING_WIND_III_FD"),
    ("Storm Bringer: giant arrow", 1100.0, "STORM_BRINGER"), ("Sharp Eyes: own Critical Damage", 40.0, "SHARP_EYES_CRIT_DAMAGE"),
    ("Emerald Flower: boss damage taken", 15.0, "EMERALD_FLOWER_BOSS_TAKEN"), ("Emerald Dust: damage taken", 8.0, "EMERALD_DUST_TAKEN"), ("Emerald Dust: Final Damage", 3.0, "EMERALD_DUST_FD"),
    ("Second Wind: Attack Speed", 15.0, "SECOND_WIND_AS"),
    ("Whispers of the Wind: Attack", 3.0, "WHISPERS_ATTACK"), ("Whispers of the Wind: Attack Speed", 3.0, "WHISPERS_AS"), ("Agile Bows: Attack Speed", 5.0, "AGILE_BOWS_AS"),
    ("Physical Training: Basic Attack Damage", 10.0, "PHYSICAL_TRAINING_BASIC"), ("Bow Mastery: Min Damage Multiplier", 15.0, "BOW_MASTERY_MIN"),
    ("Sylvan Aid: Attack", 12.0, "SYLVAN_AID_ATTACK"), ("Sylvan Aid: Critical Rate", 6.0, "SYLVAN_AID_CRIT_RATE"), ("Second Wind: Attack", 12.0, "SECOND_WIND_ATTACK"),
    ("Featherweight: Damage", 30.0, "FEATHERWEIGHT_DAMAGE"), ("Featherweight: Normal Monster Damage", 15.0, "FEATHERWEIGHT_NORMAL"), ("Eagle Eye: Final Damage", 15.0, "EAGLE_EYE_FD"),
    ("Touch of the Wind: Attack", 10.0, "TOUCH_OF_THE_WIND_ATTACK"), ("Bow Expert: Skill Damage", 15.0, "BOW_EXPERT_SKILL"), ("Bow Expert: Max Damage Multiplier", 30.0, "BOW_EXPERT_MAX"),
    ("Albatross Max: Final Damage", 10.0, "ALBATROSS_FD"), ("Albatross Max: Defense Penetration", 8.0, "ALBATROSS_DEF_PEN"),
    ("Call of Cygnus: Pinpoint Pierce", 40.0, "CYGNUS_PINPOINT_PIERCE"), ("Call of Cygnus: Spiraling Vortex", 100.0, "CYGNUS_SPIRALING_VORTEX"),
]

# fixed (non-growing) mastery / passive values: (what, shown, value in the data module)
MASTERY_VALUES = [
    ("Spiraling Vortex - Damage (Lv39)", 50, D.DAMAGE_SKILLS["SPIRALING_VORTEX"]["mastery"][39]), ("Pinpoint Pierce - Damage (Lv68)", 50, D.DAMAGE_SKILLS["PINPOINT_PIERCE_ARROW1"]["mastery"][68]),
    ("Song of Heaven - Damage (Lv108)", 50, D.DAMAGE_SKILLS["SONG_OF_HEAVEN"]["mastery"][108]), ("Pinpoint Pierce - Weaken: +10 % damage taken", 10, D.PINPOINT_WEAKEN["pct"]),
    ("Pinpoint Pierce - Weaken: 12 s", 12, D.PINPOINT_WEAKEN["duration"]), ("Trifling Wind I - Damage (Lv44)", 50, D.TRIFLING_WIND["mastery"][44]),
    ("Trifling Wind II - Damage (Lv73)", 80, D.TRIFLING_WIND["mastery"][73]), ("Trifling Wind II: x2 chance", 25, D.TRIFLING_WIND["double_chance"]),
    ("Trifling Wind II - Chance (Lv90)", 15, D.TRIFLING_WIND["double_chance_bonus"][90]), ("Trifling Wind III - Enhance (Lv113)", 35, D.TRIFLING_WIND["fd_bonus"][113]),
    ("Trifling Wind: 3 Spirit Arrows", 3, D.TRIFLING_WIND["arrows"]), ("Trifling Wind II - Additional Creation (Lv104)", 2, dict(D.TRIFLING_WIND["arrows_bonus"])[104]),
    ("Trifling Wind III - Additional Creation (Lv130)", 2, dict(D.TRIFLING_WIND["arrows_bonus"])[130]), ("Trifling Wind cooldown", 2, D.TRIFLING_WIND["icd"]),
    ("Song of Heaven: 13 volleys", 13, D.SONG_SPIRIT["volleys"]), ("Song of Heaven: 2 Spirit Arrows per volley", 2, D.SONG_SPIRIT["per_volley"]),
    ("Song of Heaven - Additional Creation (Lv134)", 3, dict(D.SONG_SPIRIT["per_volley_bonus"])[134]),
    ("Storm Bringer: 50 % storm chance", 0.5, D.STORM_BRINGER_RULES["trigger_chance"]), ("Storm Bringer: 15 s", 15, D.STORM_BRINGER_RULES["duration"]),
    ("Storm Bringer cooldown", 25, D.STORM_BRINGER_RULES["cooldown"]), ("Storm Bringer: giant arrow chance", 0.30, D.STORM_BRINGER_RULES["chance"]),
    ("Storm Bringer - Chance (Lv138)", 0.30, D.STORM_BRINGER_RULES["chance_bonus"][138]), ("Storm Bringer: giant arrow cooldown", 0.5, D.STORM_BRINGER_RULES["icd"]),
    ("Storm Bringer: 12 targets", 12, D.STORM_BRINGER_RULES["targets"]), ("Storm Bringer - Damage (Lv122)", 50, D.STORM_BRINGER_RULES["mastery"][122]),
    ("Storm Elemental: 12 s", 12, D.STORM_ELEMENTAL["duration"]), ("Storm Elemental cooldown", 28, D.STORM_ELEMENTAL["cooldown"]),
    ("Storm Elemental - Persistence (Lv21): +50 %", 1.5, D.STORM_ELEMENTAL["duration_mastery"][1]),
    ("Elemental Harmony: 15 s", 15, D.ELEMENTAL_HARMONY["duration"]), ("Elemental Harmony cooldown", 60, D.ELEMENTAL_HARMONY["cooldown"]), ("Elemental Harmony: Attack Speed", 15, D.ELEMENTAL_HARMONY["attack_speed"]),
    ("Sharp Eyes: 18 s", 18, D.SHARP_EYES["duration"]), ("Sharp Eyes cooldown", 35, D.SHARP_EYES["cooldown"]), ("Sharp Eyes - Persistence (Lv126): +50 %", 1.5, D.SHARP_EYES["duration_mastery"][1]),
    ("Emerald Flower: 20 s", 20, D.EMERALD_FLOWER["duration"]), ("Emerald Flower cooldown", 38, D.EMERALD_FLOWER["cooldown"]),
    ("Emerald Flower - Reuse (Lv78): -30 %", 0.7, D.EMERALD_FLOWER["cooldown_mastery"][1]), ("Emerald Dust: 20 s", 20, D.EMERALD_DUST["fd_duration"]),
    ("Emerald Dust - Final Damage (Lv118)", 6, D.EMERALD_DUST["fd_mastery"][118]), ("Second Wind: 8 s", 8, D.SECOND_WIND["duration"]), ("Second Wind: 8 activations", 8, D.SECOND_WIND["activations"]),
    ("Second Wind - Stack (Lv82): -4", 4, D.SECOND_WIND["activations_mastery"][1]), ("Second Wind: 4 s without new stacks", 4, D.SECOND_WIND["dead_time"]),
    ("Spiraling Vortex - Stun: 1.5 s", 1.5, D.PLAYER_STUN[0]["dur"]), ("Spiraling Vortex - Stun (Lv49)", 49, D.PLAYER_STUN[0]["level"]),
    ("Spiraling Vortex cooldown", 19, D.DAMAGE_SKILLS["SPIRALING_VORTEX"]["cooldown"]), ("Pinpoint Pierce cooldown", 20, D.DAMAGE_SKILLS["PINPOINT_PIERCE_ARROW1"]["cooldown"]),
    ("Song of Heaven cooldown", 40, D.DAMAGE_SKILLS["SONG_OF_HEAVEN"]["cooldown"]), ("Fairy Spiral: 5 hits", 5, D.FS_HITS[0]), ("Fairy Spiral - Strike (Lv136): +1", 1, D.FS_HITS[2] - D.FS_HITS[0]),
    ("Fairy Spiral: 6 targets", 6, D.FS_BASE_TARGETS), ("Spiraling Vortex: 9 targets", 9, D.DAMAGE_SKILLS["SPIRALING_VORTEX"]["targets"]), ("Spiraling Vortex: 2 hits", 2, D.DAMAGE_SKILLS["SPIRALING_VORTEX"]["hits"]),
    ("Song of Heaven: 9 targets", 9, D.DAMAGE_SKILLS["SONG_OF_HEAVEN"]["targets"]), ("Pinpoint Pierce: one target", 1, D.DAMAGE_SKILLS["PINPOINT_PIERCE_ARROW1"]["targets"]),
    ("Featherweight - Boss Monster Damage (Lv98)", 98, D.FEATHERWEIGHT_BOSS_LEVEL),
]
FS_CHAIN = {102: 10, 106: 11, 116: 12, 120: 13, 128: 14, 132: 15}
FS_BOSS_CHAIN = {111: 10, 124: 10}
# the two skill-window icon grids (badges): every unlock level of the data must occur in them (the icon -> skill assignment itself is FLAGGED, the user to confirm)
UNLOCK_GRID_ACTIVES = {0, 30, 35, 50, 60, 63, 69, 100, 103, 115}
UNLOCK_GRID_PASSIVES = {0, 33, 38, 40, 43, 45, 60, 66, 72, 74, 75, 100, 105, 107, 110, 117, 120, 125}


def trunc1(v):
    """The game truncates to one decimal (1e-7 absorbs floating-point noise on exact values)."""
    return math.floor(v * 10 + 1e-7) / 10


def check_coefficients():
    """Every curve at total level 1 through the engine's coefficient function == the level-1 pop-up; the data module holds exactly that base."""
    bad = []
    for name, shown, key in TABLE:
        c = D.CURVES[key]
        if not D.is_provisional(key):
            bad.append(f"{name}: {key} is not marked PROVISIONAL (no higher-level reading exists yet)")
        if SL1.input_level(c.step) > 1:
            bad.append(f"{name}: total level {SL1.input_level(c.step)} > 1")
        if factors.get_factor(1, c.fidx) != 1000:
            bad.append(f"{name}: factor index {c.fidx} at level 1 is {factors.get_factor(1, c.fidx)}, not 1000")
        got = trunc1(SL1.coeff_pct(c.base, c.fidx, True, c.step))
        if got != shown:
            bad.append(f"{name}: engine {got} (raw {SL1.coeff_pct(c.base, c.fidx, True, c.step)!r}) != shown {shown}")
    missing = sorted(set(D.CURVES) - {k for _n, _s, k in TABLE})
    if missing:
        bad.append(f"curves with no displayed value in this test: {missing}")
    return bad


def model(**over):
    inputs = dict(WA.defaults("Chapter Hunt"), level=LEVEL, **LEVEL1)
    inputs.update(over)
    return WA.model(inputs)


def close(a, b):
    return abs(a - b) < 1e-9


def check_model_values():
    """The model's own resolved values at total level 1 (factor 1.0): buff / effect values, per-skill coefficients, per-skill Call of Cygnus multipliers, hits, targets, arrows."""
    m = model(skill_cooldown_decrease=0, buff_duration_increase_pct=0)
    bad = []
    count = [0]

    def eq(name, got, want):
        count[0] += 1
        if not close(got, want):
            bad.append(f"{name}: model {got!r} != displayed {want!r}")
    for name, got, want in [
        ("Storm Elemental Attack", m.se_attack_full, 12.0), ("Storm Elemental Damage", m.se_damage_full, 4.0), ("Sharp Eyes own Critical Damage", m.sye_crit_full, 40.0),
        ("Emerald Flower boss damage taken", m.ef_boss_taken_full, 15.0), ("Emerald Dust damage taken", m.ed_taken_full, 8.0),
        ("Emerald Dust Final Damage (3 + 6 pp at Lv118)", m.ed_fd_full, 9.0), ("Second Wind Attack Speed", m.sw_as_full, 15.0),
        ("Fairy Spiral coefficient", m.skill_coefficient_base, 290.0), ("Trifling Wind II arrow (x1 + 130 % mastery x 1.4 chance)", m.tw_arrow_pct, 100.0 * (1 + 130 / 100) * (1 + 40 / 100)),
        ("Trifling Wind III Final Damage (100 + 35)", m.tw_fd, 135.0), ("Trifling Wind arrows per activation (3 + 2 + 2)", m.tw_arrows_per_cast, 7),
        ("Song of Heaven arrows per cast (13 x (2 + 3))", m.song_arrows_per_cast, 65),
    ]:
        eq(name, got, want)
    for key, coef, cyg in [("SPIRALING_VORTEX", 250.0, 100.0), ("PINPOINT_PIERCE_ARROW1", 330.0, 40.0), ("PINPOINT_PIERCE_ARROW2", 740.0, 40.0), ("SONG_OF_HEAVEN", 780.0, 0.0)]:
        eq(f"{key} coefficient", m.skills[key]["coef_pct"], coef)
        eq(f"{key} Call of Cygnus", m.skills[key]["cygnus_pct"], cyg)
    for key, hits, targets, cd in [("SPIRALING_VORTEX", 2, 9, 19), ("PINPOINT_PIERCE_ARROW1", 1, 1, 20), ("PINPOINT_PIERCE_ARROW2", 1, 1, 20), ("SONG_OF_HEAVEN", 13, 9, 40)]:
        s = m.skills[key]
        for what, got, want in (("hits", s["hits"], hits), ("targets", s["targets"], targets), ("cooldown", s["cooldown"], cd)):
            eq(f"{key} {what}", got, want)
    # the basic attack: 5 hits (6 from Lv136), 6 targets + the Basic Attack Target Increase input (which already contains the Lv64 mastery)
    inc = WA.defaults("Chapter Hunt")["basic_attack_target_increase"] or 0
    eq("Fairy Spiral targets", m.fs_targets, 6 + inc)
    # the Spirit Arrow ladder: -20 % per consecutive strike on ONE target, floor 20 %
    eq("ladder mean of 5 arrows", WA.ladder_mean(5), (1.0 + 0.8 + 0.6 + 0.4 + 0.2) / 5)
    eq("ladder mean of 7 arrows", WA.ladder_mean(7), (1.0 + 0.8 + 0.6 + 0.4 + 0.2 + 0.2 + 0.2) / 7)
    # level gates of the arrow counts / chances
    for lv, arrows, per_volley in ((103, 3, 2), (104, 5, 2), (130, 7, 2), (134, 7, 5)):
        ml = model(level=lv)
        eq(f"Trifling Wind arrows at Lv{lv}", ml.tw_arrows_per_cast, arrows)
        eq(f"Song of Heaven arrows per volley at Lv{lv}", ml.song_arrows_per_cast, 13 * per_volley)
    return count[0], bad


def check_cooldowns_and_uptimes():
    """Displayed cooldowns (Skill Cooldown Decrease 0) and the uptimes they imply in steady state (Chapter Hunt)."""
    m = model(skill_cooldown_decrease=0, buff_duration_increase_pct=0)
    bad = []
    n = 0
    for name, got, want in [("Storm Elemental uptime (12 s x 1.5 / 28 s)", m.se_up, 12 * 1.5 / 28), ("Sharp Eyes uptime (18 s x 1.5 / 35 s)", m.sye_up, 18 * 1.5 / 35),
                            ("Emerald Flower uptime (20 s / (38 s x 0.7))", m.ef_up, 20 / (38 * 0.7)), ("Emerald Dust Final Damage uptime (20 s / (38 s x 0.7))", m.ed_up, 20 / (38 * 0.7)),
                            ("Pinpoint Pierce weaken (10 % for 12 s / 20 s)", m.pinpoint_weaken_avg, 10 * 12 / 20)]:
        n += 1
        if not close(got, want):
            bad.append(f"{name}: model {got!r} != {want!r}")
    # patch 2026-11-26: Emerald Dust's Final Damage is a standalone 20 s buff, Buff Duration Increase applies to IT (not to the flower's own damage-taken window)
    m2 = model(skill_cooldown_decrease=0, buff_duration_increase_pct=20)
    for name, got, want in [("Emerald Dust Final Damage with Buff Duration +20 %", m2.ed_up, min(1.0, 24 / (38 * 0.7))), ("Emerald Flower window ignores Buff Duration", m2.ef_up, 20 / (38 * 0.7))]:
        n += 1
        if not close(got, want):
            bad.append(f"{name}: model {got!r} != {want!r}")
    # Skill Cooldown Decrease applies to the displayed base cooldown (1.5 s here)
    m3 = model(skill_cooldown_decrease=1.5, buff_duration_increase_pct=0)
    for key, cd in (("SPIRALING_VORTEX", 19), ("PINPOINT_PIERCE_ARROW1", 20), ("SONG_OF_HEAVEN", 40)):
        n += 1
        if not close(m3.fight.eff_cooldown(m3.skills[key]["cooldown"], True), cd - 1.5):
            bad.append(f"{key}: effective cooldown {m3.fight.eff_cooldown(m3.skills[key]['cooldown'], True)} != {cd} - 1.5")
    return n, bad


def check_mastery_values_and_unlocks():
    bad = []
    n = 0
    for name, shown, got in MASTERY_VALUES:
        n += 1
        if got != shown:
            bad.append(f"{name}: data {got} != shown {shown}")
    n += 2
    if D.FS_MASTERY != FS_CHAIN:
        bad.append(f"Fairy Spiral chain {D.FS_MASTERY} != {FS_CHAIN}")
    if D.FS_BOSS_MASTERY != FS_BOSS_CHAIN:
        bad.append(f"Fairy Spiral boss chain {D.FS_BOSS_MASTERY} != {FS_BOSS_CHAIN}")
    active_keys = ["SPIRALING_VORTEX", "PINPOINT_PIERCE_ARROW1", "SONG_OF_HEAVEN", "STORM_ELEMENTAL", "ELEMENTAL_HARMONY", "EMERALD_FLOWER", "SHARP_EYES", "FAIRY_SPIRAL"]
    passive_keys = ["TRIFLING_WIND_I", "TRIFLING_WIND_II", "TRIFLING_WIND_III", "SECOND_WIND", "CALL_OF_CYGNUS", "EMERALD_DUST", "STORM_BRINGER"]
    for k in active_keys:
        n += 1
        if D.UNLOCK_LEVEL[k] not in UNLOCK_GRID_ACTIVES:
            bad.append(f"{k}: unlock {D.UNLOCK_LEVEL[k]} is not an active-grid level")
    for k in passive_keys:
        n += 1
        if D.UNLOCK_LEVEL[k] not in UNLOCK_GRID_PASSIVES:
            bad.append(f"{k}: unlock {D.UNLOCK_LEVEL[k]} is not a passive-grid level")
    # the basic attack is absent below Lv100 (no 3rd-job basic attack is modelled)
    low = model(level=99)
    n += 1
    if low.fs_dps != 0.0:
        bad.append("Fairy Spiral must be absent below level 100")
    return n, bad


def run(verbose=True):
    bad = check_coefficients()
    n = len(TABLE)
    n2, bad2 = check_model_values()
    n3, bad3 = check_cooldowns_and_uptimes()
    n4, bad4 = check_mastery_values_and_unlocks()
    bad += bad2 + bad3 + bad4
    n += n2 + n3 + n4
    if verbose:
        if bad:
            print("FAIL:")
            for b in bad:
                print("  -", b)
        else:
            print(f"OK: {n} displayed values reproduced")
    return n, bad


def test_wind_archer_displayed_values():
    n, bad = run(verbose=False)
    assert n > 0 and not bad, "\n".join(bad)


if __name__ == "__main__":
    _n, _bad = run()
    sys.exit(1 if _bad else 0)
