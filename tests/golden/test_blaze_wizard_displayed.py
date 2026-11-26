#!/usr/bin/env python3
"""Displayed-value test of the Blaze Wizard data (the only real-game check of this engine-native, PROVISIONAL, unpublished class; no workbook exists).

SOURCE: ``data/cygnus/blaze_wizard_ingame.md`` = the user's LEVEL-1 pop-ups (fresh character, "Lv. 1" everywhere: the displayed value IS the base, factor 1.0).  There is NO site
cross-check for this class: ``maplestoryidle.info``'s job-skill-impact table has no Blaze Wizard rows, so every factor index (the growth curve) is a convention (Dawn Warrior's:
damage 12, basic attack / active buffs 21, passives 22, Call of Cygnus 23) and every curve is PROVISIONAL (``engine/data/blaze_wizard.py`` ``CURVES`` / ``PROVISIONAL``).  What this test
pins is therefore only what a level-1 reading can pin: every transcribed damage / buff / passive / mastery value, hit and target count, cooldown, duration, interval and unlock level is
reproduced by the engine at total skill level 1 (all skill-level bonuses set to -1000 so every job tier clamps to level 1, factor 1.0), through the engine's own coefficient function
(``factors.SkillLevels.coeff_pct`` with the game's truncation to one decimal) AND through the model's resolved values (``m.skills``, buff values, uptimes).  Once the user supplies a
higher-level reading per skill (data/cygnus/README.md), rows move out of ``PROVISIONAL`` and get a second reading here (the Dawn Warrior test is the template).

Plain ``python3`` runnable, also collected by pytest; prints "OK: N displayed values reproduced".
"""
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from engine.classes import blaze_wizard as BW  # noqa: E402
from engine.common import factors  # noqa: E402
from engine.data import blaze_wizard as D  # noqa: E402
sys.path.insert(0, str(HERE))
import factor_mode  # noqa: E402

FACTOR_MODE = factor_mode.pin("extended")        # production mode: growth curves continue past level 300

LEVEL = 120                                  # character level of the model checks: everything but the Lv125+ / Lv130+ / Lv138 effects is unlocked
LEVEL1 = dict(skill_lvl_1st=-1000, skill_lvl_2nd=-1000, skill_lvl_3rd=-1000, skill_lvl_4th=-1000, skill_lvl_all=-1000)     # every job tier clamps to total level 1
SL1 = factors.SkillLevels(LEVEL, -1000, -1000, -1000, -1000, -1000)

# (name, shown value (%), CURVES key or None, base in tenths of % when there is no curve, factor index when there is no curve, step when there is no curve)
# ---- active skills / damage ----
TABLE = [
    ("Flame Elemental: Attack", 15.0, "FLAME_ELEMENTAL_ATTACK"),
    ("Flame Vortex", 260.0, "FLAME_VORTEX"),
    ("Flashfire: Attack", 12.0, "FLASHFIRE_ATTACK"),
    ("Fires of Creation: Fire Lion Normal Monster Damage", 20.0, "FIRES_LION_NORMAL_DAMAGE"),
    ("Fires of Creation: Flame Fox Boss Monster Damage", 20.0, "FIRES_FOX_BOSS_DAMAGE"),
    ("Fires of Creation: Final Damage", 3.0, "FIRES_FINAL_DAMAGE"),
    ("Flame Tempest", 300.0, "FLAME_TEMPEST"),
    ("Cinder Maelstrom", 270.0, "CINDER_MAELSTROM"),
    ("Final Orbital Flame (basic attack)", 290.0, "FINAL_ORBITAL_FLAME"),
    ("Blazing Extinction: Fire Lion", 1200.0, "BLAZING_EXTINCTION_LION"),
    ("Blazing Extinction: Flame Fox", 1600.0, "BLAZING_EXTINCTION_FOX"),
    ("Towering Inferno: Fire Lion", 1350.0, "TOWERING_INFERNO_LION"),
    ("Towering Inferno: Flame Fox", 2400.0, "TOWERING_INFERNO_FOX"),
    ("Towering Inferno: Flame Fox boss flame strike", 550.0, "TOWERING_INFERNO_FOX_STRIKES"),
    ("Burning Conduit: own Final Damage", 5.0, "BURNING_CONDUIT_FD"),
    # ---- passives ----
    ("Fire Repulsion: Attack", 3.0, "FIRE_REPULSION_ATTACK"),
    ("Word of Fire: Attack Speed", 5.0, "WORD_OF_FIRE_AS"),
    ("Greater Flame Elemental: damage", 20.0, "GREATER_FE_DAMAGE"),
    ("Spell Control: Min Damage Multiplier", 15.0, "SPELL_CONTROL_MIN"),
    ("Orbital Explosion: additional damage", 50.0, "ORBITAL_EXPLOSION"),
    ("Brilliant Enlightenment: Min Damage Multiplier", 10.0, "BRILLIANT_MIN"),
    ("Brilliant Enlightenment: Max Damage Multiplier", 20.0, "BRILLIANT_MAX"),
    ("Burning Focus: Critical Rate", 8.0, "BURNING_FOCUS_CRIT_RATE"),
    ("Burning Focus: Critical Damage", 16.0, "BURNING_FOCUS_CRIT_DAMAGE"),
    ("Grand Flame Elemental: Basic Attack Damage", 15.0, "GRAND_FE_BASIC_ATTACK"),
    ("Liberated Magic: Final Damage", 15.0, "LIBERATED_MAGIC_FD"),
    ("Call of Cygnus: Flame Vortex", 60.0, "CYGNUS_FLAME_VORTEX"),
    ("Call of Cygnus: Flame Tempest", 35.0, "CYGNUS_FLAME_TEMPEST"),
    ("Call of Cygnus: Cinder Maelstrom", 30.0, "CYGNUS_CINDER_MAELSTROM"),
    ("Call of Cygnus: Orbital Explosion", 70.0, "CYGNUS_ORBITAL_EXPLOSION"),
    ("Final Flame Elemental: Defense Penetration", 3.0, "FINAL_FE_DEF_PEN"),
    ("Final Flame Elemental: Critical Damage", 28.0, "FINAL_FE_CRIT_DAMAGE"),
    ("Phoenix Run: Final Damage (per stack)", 1.0, "PHOENIX_RUN_FD"),   # a flat 10.0 before the 2026-11-26 patch (+1 % per second, 12 stacks now; patch-derived)
    ("Flame Barrier: Attack", 5.0, "FLAME_BARRIER_ATTACK"),
    ("Pure Magic: Skill Damage", 15.0, "PURE_MAGIC_SKILL"),
    ("Pure Magic: Max Damage Multiplier", 30.0, "PURE_MAGIC_MAX"),   # 20.0 before the 2026-11-26 patch (patch-derived)
    ("Wild Blaze: Final Damage", 12.0, "WILD_BLAZE_FD"),
]
# transcribed passives with no DPS role (barrier / Defense / MP): only the convention triple is checked (nothing in the model reads them): (name, shown, base, fidx, step)
UNMODELLED = [
    ("Fire Repulsion: Defense", 15.0, 150, 22, 1), ("Controlled Burn: MP recovery", 1.5, 15, 22, 2), ("Liberated Magic: MP cost increase", 10.0, 100, 22, 3),
    ("Flame Barrier: barrier (% of Max HP)", 10.0, 100, 22, 4),   # 6.0 / 60 before the 2026-11-26 patch
]
# fixed (non-growing) mastery / passive values: shown, value in the data / model
MASTERY_VALUES = [
    ("Fire Repulsion mastery (Lv24): Attack +5 pp", 5, None),
    ("Greater Flame Elemental mastery (Lv44): +10 pp", 10, D.GREATER_FE_MASTERY[44]),
    ("Grand Flame Elemental mastery (Lv82): Skill Damage +15", 15, D.GRAND_FE_SKILL_DAMAGE[82]),
    ("Final Flame Elemental mastery (Lv130): Final Damage +3", 3, D.FINAL_FE_FD[130]),
    ("Fires of Creation mastery (Lv104): Final Damage +3 pp", 3, D.FIRES_FD_MASTERY[104]),
    ("Fox mastery (Lv94): Defense Penetration +5", 5, D.FOX_DEF_PEN[94]),
    ("Towering Inferno mastery (Lv138): Fire Lion +150 Normal Monster Damage", 150, D.LION_TOWERING_NORMAL_DAMAGE[138]),
    ("Flame Vortex mastery (Lv39): Damage +70", 70, D.DAMAGE_SKILLS["FLAME_VORTEX"]["mastery"][39]),
    ("Orbital Explosion mastery (Lv54): Damage +50", 50, D.ORBITAL_EXPLOSION["mastery"][54]),
    ("Flame Tempest mastery (Lv68): Damage +80", 80, D.DAMAGE_SKILLS["FLAME_TEMPEST"]["mastery"][68]),
    ("Cinder Maelstrom mastery (Lv78): Damage +50", 50, D.DAMAGE_SKILLS["CINDER_MAELSTROM"]["mastery"][78]),
    ("Cinder Maelstrom mastery (Lv98): Weaken +9", 9, D.CINDER_WEAKEN["pct"]),
    ("Blazing Extinction mastery (Lv108): Damage +50", 50, D.DAMAGE_SKILLS["BLAZING_EXTINCTION_FOX"]["mastery"][108]),
    ("Towering Inferno mastery (Lv113): Damage +50", 50, D.DAMAGE_SKILLS["TOWERING_INFERNO_FOX"]["mastery"][113]),
    ("Final Orbital Flame Boss Monster Damage (Lv111)", 10, D.FOF_BOSS_MASTERY[111]),
    ("Final Orbital Flame Boss Monster Damage (Lv124)", 10, D.FOF_BOSS_MASTERY[124]),
]
FOF_CHAIN = {102: 10, 106: 11, 116: 12, 120: 13, 128: 14, 132: 15}
UNLOCK_GRID_ACTIVES = {0, 30, 35, 50, 60, 63, 69, 100, 103, 110, 115}          # the icon grid (level-less icons = 0)
UNLOCK_GRID_PASSIVES = {0, 33, 38, 40, 43, 45, 66, 72, 74, 75, 100, 105, 107, 117, 120, 125}


def trunc1(v):
    """The game truncates to one decimal (1e-7 absorbs floating-point noise on exact values)."""
    return math.floor(v * 10 + 1e-7) / 10


def check_coefficients():
    """Every curve at total level 1 through the engine's coefficient function == the level-1 pop-up; the data module holds exactly that base."""
    bad = []
    for name, shown, key in TABLE:
        c = D.CURVES[key]
        if not D.is_provisional(key):
            bad.append(f"{name}: {key} is not marked PROVISIONAL (no higher-level reading exists)")
        if SL1.input_level(c.step) > 1:
            bad.append(f"{name}: total level {SL1.input_level(c.step)} > 1")
        if factors.get_factor(1, c.fidx) != 1000:
            bad.append(f"{name}: factor index {c.fidx} at level 1 is {factors.get_factor(1, c.fidx)}, not 1000")
        got = trunc1(SL1.coeff_pct(c.base, c.fidx, True, c.step))
        if got != shown:
            bad.append(f"{name}: engine {got} (raw {SL1.coeff_pct(c.base, c.fidx, True, c.step)!r}) != shown {shown}")
    for name, shown, base, fidx, step in UNMODELLED:
        got = trunc1(SL1.coeff_pct(base, fidx, True, step))
        if got != shown:
            bad.append(f"{name} (not modelled): engine {got} != shown {shown}")
    missing = sorted(set(D.CURVES) - {k for _n, _s, k in TABLE})
    if missing:
        bad.append(f"curves with no displayed value in this test: {missing}")
    return bad


def model(**over):
    inputs = dict(BW.defaults("Chapter Hunt"), level=LEVEL, **LEVEL1)
    inputs.update(over)
    return BW.model(inputs)


def close(a, b):
    return abs(a - b) < 1e-9


def check_model_values():
    """The model's own resolved values at total level 1 (factor 1.0): buff / effect values, per-skill coefficients, per-skill Call of Cygnus multipliers, hits, targets, ticks."""
    m = model(skill_cooldown_decrease=0, buff_duration_increase_pct=0)
    bad = []
    count = [0]

    def eq(name, got, want):
        count[0] += 1
        if not close(got, want):
            bad.append(f"{name}: model {got!r} != displayed {want!r}")
    for name, got, want in [
        ("Flame Elemental Attack", m.fe_attack_full, 15.0), ("Flashfire Attack", m.ff_attack_full, 12.0), ("Fire Lion Normal Monster Damage", m.lion_normal_damage, 20.0),
        ("Flame Fox Boss Monster Damage", m.fox_boss_damage, 20.0), ("Fox Defense Penetration (Lv94 mastery)", m.fox_def_pen, 5.0),
        ("Greater Flame Elemental damage (20 + 10 pp at Lv44)", m.gfe_damage_full, 30.0), ("Grand Flame Elemental Basic Attack Damage", m.gfe_basic_full, 15.0),
        ("Grand Flame Elemental Skill Damage (Lv82)", m.gfe_skill_full, 15.0), ("Final Flame Elemental Def Pen", m.ffe_def_pen_full, 3.0),
        ("Final Flame Elemental Crit Damage", m.ffe_crit_damage_full, 28.0), ("Final Flame Elemental Final Damage (Lv130: locked at 120)", m.ffe_fd_full, 0.0),
        ("Burning Conduit Final Damage", m.bc_fd_full, 5.0), ("Final Orbital Flame coefficient", m.skill_coefficient_base, 290.0),
    ]:
        eq(name, got, want)
    for key, coef, cyg in [("FLAME_VORTEX", 260.0, 60.0), ("FLAME_TEMPEST", 300.0, 35.0), ("CINDER_MAELSTROM", 270.0, 30.0), ("BLAZING_EXTINCTION_FOX", 1600.0, 0.0),
                           ("BLAZING_EXTINCTION_LION", 1200.0, 0.0), ("TOWERING_INFERNO_FOX", 2400.0, 0.0), ("TOWERING_INFERNO_FOX_STRIKES", 550.0, 0.0),
                           ("TOWERING_INFERNO_LION", 1350.0, 0.0)]:
        eq(f"{key} coefficient", m.skills[key]["coef_pct"], coef)
        eq(f"{key} Call of Cygnus", m.skills[key]["cygnus_pct"], cyg)
    # hits / targets / cooldowns / windows / intervals (displayed text; character level 120: the Lv126 interval mastery and the Lv136 / Lv138 masteries are off)
    for key, hits, targets, cd in [("FLAME_VORTEX", 2, 7, 18), ("FLAME_TEMPEST", 2, 8, 20), ("CINDER_MAELSTROM", 3, 6, 23), ("TOWERING_INFERNO_LION", 5, 12, 21),
                                   ("TOWERING_INFERNO_FOX", 2, 4, 21), ("TOWERING_INFERNO_FOX_STRIKES", 3 * 2, 1, 21), ("BLAZING_EXTINCTION_LION", 1, 9, 32),
                                   ("BLAZING_EXTINCTION_FOX", 1, 3, 32)]:
        s = m.skills[key]
        for what, got, want in (("hits", s["hits"], hits), ("targets", s["targets"], targets), ("cooldown", s["cooldown"], cd)):
            eq(f"{key} {what}", got, want)
    for key, window, icd in [("BLAZING_EXTINCTION_LION", 3, 0.5), ("BLAZING_EXTINCTION_FOX", 5, 0.7)]:
        eq(f"{key} window", m.skills[key]["window"], window)
        eq(f"{key} strike interval", m.skills[key]["icd"], icd)
    # the Lv126 mastery: Lion -0.1 s, Fox -0.2 s; Towering Inferno +1 Fox flame strike at Lv138
    m126 = model(level=126)
    eq("Blazing Extinction Lion interval at Lv126", m126.skills["BLAZING_EXTINCTION_LION"]["icd"], 0.4)
    eq("Blazing Extinction Fox interval at Lv126", m126.skills["BLAZING_EXTINCTION_FOX"]["icd"], 0.5)
    eq("Towering Inferno Fox strikes at Lv138", model(level=138).skills["TOWERING_INFERNO_FOX_STRIKES"]["hits"], 4 * 2)
    # basic attack: 5 hits (6 from Lv136), 6 targets (+1 with the Fire Lion from Lv73, normal branch)
    inc = BW.defaults("Chapter Hunt")["basic_attack_target_increase"] or 0
    eq("Final Orbital Flame targets (normal branch, Lv120: 6 + input + 1 with the Fire Lion)", m.fof_targets_normal, 6 + inc + 1)
    eq("Final Orbital Flame targets (boss branch: no Lion target)", m.fof_targets_boss, 6 + inc)
    eq("Final Orbital Flame base targets", D.FOF_BASE_TARGETS, 6)
    eq("Final Orbital Flame hits", D.FOF_HITS[0], 5)
    eq("Final Orbital Flame extra strike (Lv136)", D.FOF_HITS[2] - D.FOF_HITS[0], 1)
    # Orbital Explosion text: 60 %, ICD 1 s, 5 targets x 2, 15 s every 30 s
    oe = D.ORBITAL_EXPLOSION
    for name, got, want in (("chance", oe["chance"], 60), ("ICD", oe["icd"], 1.0), ("targets", oe["targets"], 5), ("hits", oe["hits"], 2), ("fire energy", oe["window"], 15),
                            ("period", oe["period"], 30)):
        eq(f"Orbital Explosion {name}", got, want)
    # Cinder Maelstrom weaken duration; durations
    eq("Cinder weaken duration", D.CINDER_WEAKEN["duration"], 14)
    eq("Flame Elemental duration", D.FLAME_ELEMENTAL["duration"], 12)
    eq("Flashfire duration", D.FLASHFIRE["duration"], 30)
    eq("Burning Conduit duration", D.BURNING_CONDUIT["duration"], 20)
    eq("Elemental Harmony duration", D.ELEMENTAL_HARMONY["duration"], 15)
    eq("Elemental Harmony Attack Speed", D.ELEMENTAL_HARMONY["attack_speed"], 15)
    return count[0], bad


def check_cooldowns_and_uptimes():
    """Displayed cooldowns (Skill Cooldown Decrease 0) and the uptimes they imply in steady state (Chapter Hunt)."""
    m = model(skill_cooldown_decrease=0, buff_duration_increase_pct=0)
    bad = []
    n = 0
    for name, shown, got in [("Elemental Harmony", 60, D.BUFF_COOLDOWNS["ELEMENTAL_HARMONY"]), ("Flame Elemental", 28, D.BUFF_COOLDOWNS["FLAME_ELEMENTAL"]),
                             ("Flashfire", 10, D.BUFF_COOLDOWNS["FLASHFIRE"]), ("Burning Conduit", 40, D.BUFF_COOLDOWNS["BURNING_CONDUIT"]),
                             ("Fires of Creation", 3, None)]:
        n += 1
        if got is not None and got != shown:
            bad.append(f"{name} cooldown {got} != shown {shown}")
    # Flame Elemental 12 s x1.5 (Lv21 mastery) every 28 s; Flashfire's 30 s mark re-cast when it expires (period = max(10, 30), 100 %); Burning Conduit 20 s / 40 s; Orbital Explosion 15 s / 30 s
    for name, got, want in [("Flame Elemental uptime", m.fe_up, 12 * 1.5 / 28), ("Flashfire uptime", m.ff_up, 1.0), ("Burning Conduit uptime", m.bc_up, 20 / 40),
                            ("Orbital Explosion uptime", m.oe_uptime, 15 / 30), ("Cinder weaken (9 for 14 s / 23 s) average", m.weaken_avg, 9 * 14 / 23)]:
        n += 1
        if not close(got, want):
            bad.append(f"{name}: model {got!r} != {want!r}")
    # Skill Cooldown Decrease applies to the displayed base cooldown (1.5 s here), Buff Duration Increase extends the buffs (not Orbital Explosion's fixed 15 s / 30 s)
    m2 = model(skill_cooldown_decrease=1.5, buff_duration_increase_pct=50)
    for name, got, want in [("Flame Elemental uptime with Buff Duration +50 % and Cooldown -1.5 s", m2.fe_up, min(1.0, 12 * 1.5 * 1.5 / 26.5)),
                            ("Orbital Explosion ignores both", m2.oe_uptime, 15 / 30)]:
        n += 1
        if not close(got, want):
            bad.append(f"{name}: model {got!r} != {want!r}")
    for key, cd in (("FLAME_VORTEX", 18), ("FLAME_TEMPEST", 20), ("CINDER_MAELSTROM", 23), ("BLAZING_EXTINCTION_FOX", 32), ("TOWERING_INFERNO_FOX", 21)):
        n += 1
        if not close(m2.fight.eff_cooldown(m2.skills[key]["cooldown"], True), cd - 1.5):
            bad.append(f"{key}: effective cooldown {m2.fight.eff_cooldown(m2.skills[key]['cooldown'], True)} != {cd} - 1.5")
    return n, bad


def check_mastery_values_and_unlocks():
    bad = []
    n = 0
    for name, shown, got in MASTERY_VALUES:
        n += 1
        if got is not None and got != shown:
            bad.append(f"{name}: data {got} != shown {shown}")
    n += 1
    if D.FOF_MASTERY != FOF_CHAIN:
        bad.append(f"Final Orbital Flame chain {D.FOF_MASTERY} != {FOF_CHAIN}")
    # unlock levels: only values that occur in the icon grids (the icon -> skill order mapping itself is flagged, user to confirm)
    active_keys = ["FLAME_VORTEX", "FLASHFIRE", "FIRES_OF_CREATION", "FLAME_TEMPEST", "CINDER_MAELSTROM", "FINAL_ORBITAL_FLAME", "BLAZING_EXTINCTION_FOX",
                   "BLAZING_EXTINCTION_LION", "TOWERING_INFERNO_FOX", "TOWERING_INFERNO_LION", "BURNING_CONDUIT", "FLAME_ELEMENTAL", "ELEMENTAL_HARMONY"]
    passive_keys = ["ORBITAL_EXPLOSION", "GREATER_FLAME_ELEMENTAL", "GRAND_FLAME_ELEMENTAL", "FINAL_FLAME_ELEMENTAL", "CALL_OF_CYGNUS"]
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
    n += 2
    if low.fof_dps != 0.0 or low.oe_dps != 0.0:
        bad.append("Final Orbital Flame / Orbital Explosion must be absent below level 100")
    if not model(level=100).unlocked("FINAL_ORBITAL_FLAME"):
        bad.append("Final Orbital Flame unlocks at 100")
    return n, bad


def run(verbose=True):
    bad = check_coefficients()
    n = len(TABLE) + len(UNMODELLED)
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


def test_blaze_wizard_displayed_values():
    n, bad = run(verbose=False)
    assert n > 0 and not bad, "\n".join(bad)


if __name__ == "__main__":
    _n, _bad = run()
    sys.exit(1 if _bad else 0)
