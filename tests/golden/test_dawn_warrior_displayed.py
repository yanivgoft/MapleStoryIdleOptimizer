#!/usr/bin/env python3
"""Displayed-value test of the Dawn Warrior data (the independent real-game check of an engine-native class, no workbook exists).

Every number in the user's in-game skill text (/tmp/dawn_warrior_skills.txt, character level 120, skill bonuses +67 / +67 / +81 / +121 for the 1st / 2nd / 3rd / 4th job:
total levels 127 / 157 / 201 / 181) is reproduced EXACTLY by the engine's own coefficient function (``factors.SkillLevels.coeff_pct`` = base x factor[idx][total skill level]) with the
game's rule of TRUNCATING to one decimal, from the (base, factor index, job step) stored in ``engine/data/dawn_warrior.py``.  Cooldowns (incl. the cooldown masteries cutting the BASE
before Skill Cooldown Decrease) are checked through the model.  Plain ``python3`` runnable, also collected by pytest; prints "OK: N displayed values reproduced".
"""
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from engine.classes import dawn_warrior as DW  # noqa: E402
from engine.common import factors  # noqa: E402
from engine.data import dawn_warrior as D  # noqa: E402

LEVEL = 120
BONUS = dict(skill_lvl_1st=67, skill_lvl_2nd=67, skill_lvl_3rd=81, skill_lvl_4th=121, skill_lvl_all=0)
SL = factors.SkillLevels(LEVEL, BONUS["skill_lvl_1st"], BONUS["skill_lvl_2nd"], BONUS["skill_lvl_3rd"], BONUS["skill_lvl_4th"], BONUS["skill_lvl_all"])
TOTAL_LEVEL = {1: 127, 2: 157, 3: 201, 4: 181}      # shown "Total Level" of each job step (60/90/120 + bonus; 4th: (120 - 100) x 3 = 60 + bonus)

# (skill / effect, shown value (%), base in tenths of % (the repo's BaseDamage unit), factor index, job step, key of the engine data holding the same triple or None)
TABLE = [
    # ---- active skills ----
    ("Soul Elemental: Attack", 22.6, 150, 21, 1, ("SOUL_ELEMENTAL", D.SOUL_ELEMENTAL)),
    ("Cosmic Matter: 1-target hits", 178.5, 1000, 12, 2, ("COSMIC_MATTER", D.DAMAGE_SKILLS["COSMIC_MATTER"])),
    ("Cosmic Matter: explosion", 232.0, 1300, 12, 2, ("COSMIC_MATTER_BLAST", D.DAMAGE_SKILLS["COSMIC_MATTER_BLAST"])),
    ("Equinox Cycle: Attack", 4.8, 30, 21, 2, ("EQUINOX_CYCLE", D.EQUINOX_CYCLE)),
    ("Luna Divide (Equinox Cycle text)", 32.5, 200, 21, 2, ("LUNA_BASE", dict(base=D.LUNA_BASE[0], fidx=D.LUNA_FIDX))),
    ("Sol Rush", 601.5, 3000, 12, 3, ("SOL_RUSH", D.DAMAGE_SKILLS["SOL_RUSH"])),
    ("Sol Rush (enhanced)", 862.1, 4300, 12, 3, ("SOL_RUSH_ENHANCED", D.DAMAGE_SKILLS["SOL_RUSH_ENHANCED"])),
    ("True Sight", 1563.9, 7800, 12, 3, ("TRUE_SIGHT", D.DAMAGE_SKILLS["TRUE_SIGHT"])),
    ("True Sight: damage taken", 18.0, 100, 21, 3, ("TRUE_SIGHT_TAKEN", D.TRUE_SIGHT_TAKEN)),
    ("Cosmic Shower (per tick)", 561.4, 2800, 12, 3, ("COSMIC_SHOWER", D.DAMAGE_SKILLS["COSMIC_SHOWER"])),
    ("Celestial Vision III", 499.9, 2900, 21, 4, ("CELESTIAL_VISION", dict(base=D.CV_BASE * 10, fidx=21))),
    ("Equinox Slash", 4191.0, 22000, 12, 4, ("EQUINOX_SLASH", D.DAMAGE_SKILLS["EQUINOX_SLASH"])),
    ("Impaling Rays", 3048.0, 16000, 12, 4, ("IMPALING_RAYS", D.DAMAGE_SKILLS["IMPALING_RAYS"])),
    ("Impaling Rays: delayed pierce", 2476.5, 13000, 12, 4, ("IMPALING_RAYS_PIERCE", D.DAMAGE_SKILLS["IMPALING_RAYS_PIERCE"])),
    ("Cosmic Burst", 2857.5, 15000, 12, 4, ("COSMIC_BURST", D.DAMAGE_SKILLS["COSMIC_BURST"])),
    # ---- passives ----
    ("Soul of the Guardian: Max HP", 13.8, 100, 22, 1, None),
    ("Soul of the Guardian: Defense", 20.7, 150, 22, 1, None),
    ("Soul Speed: Attack Speed", 7.3, 50, 22, 2, None),
    ("Physical Training: Basic Attack Damage", 14.7, 100, 22, 2, None),
    ("Soul Blessing: pp to Soul Elemental", 7.3, 50, 22, 2, ("SOUL_BLESSING", D.SOUL_BLESSING)),
    ("Sword Mastery: Min Damage Multiplier", 22.0, 150, 22, 2, None),
    ("Divine Hand: Attack", 11.7, 80, 22, 2, None),
    ("Will of Steel: damage taken", 8.0, 50, 22, 3, None),
    ("Will of Steel: HP recovery", 1.6, 10, 22, 3, None),
    ("Equinox Mastery: Luna Divide damage", 126.2, 700, 21, 3, ("LUNA_BASE_72", dict(base=D.LUNA_BASE[1][1], fidx=D.LUNA_FIDX))),
    ("Equinox Mastery: Basic Attack Damage", 16.0, 100, 22, 3, ("EQUINOX_MASTERY_BA", D.EQUINOX_MASTERY_BA)),
    ("Soul Blessing II: Crit Rate", 12.8, 80, 22, 3, ("SOUL_BLESSING_II_RATE", D.SOUL_BLESSING_II_RATE)),
    ("Soul Blessing II: Crit Damage", 28.8, 180, 22, 3, ("SOUL_BLESSING_II_DMG", D.SOUL_BLESSING_II_DMG)),
    ("Inner Shout: Final Damage", 24.0, 150, 22, 3, None),
    ("Call of Cygnus: Cosmic Matter", 608.8, 800, 23, 4, ("CALL_OF_CYGNUS_CM", dict(base=D.CALL_OF_CYGNUS["COSMIC_MATTER"], fidx=D.CALL_OF_CYGNUS_FIDX))),
    ("Call of Cygnus: Cosmic Shower", 190.2, 250, 23, 4, ("CALL_OF_CYGNUS_CS", dict(base=D.CALL_OF_CYGNUS["COSMIC_SHOWER"], fidx=D.CALL_OF_CYGNUS_FIDX))),
    ("Call of Cygnus: Sol Rush", 228.3, 300, 23, 4, ("CALL_OF_CYGNUS_SR", dict(base=D.CALL_OF_CYGNUS["SOL_RUSH"], fidx=D.CALL_OF_CYGNUS_FIDX))),
    ("Soul Pledge: Attack", 18.5, 120, 22, 4, None),
    ("Soul Pledge: Crit Damage", 23.1, 150, 22, 4, None),
    ("Master of the Sword: Final Damage (Luna Divide)", 327.5, 1900, 21, 4, ("MASTER_SWORD_FD", D.MASTER_SWORD_FD)),
    ("Master of the Sword: Equinox Cycle Attack pp", 18.5, 120, 22, 4, ("MASTER_SWORD_EC_ATTACK", D.MASTER_SWORD_EC_ATTACK)),
    ("Unpredictable: Basic Attack Damage", 12.3, 80, 22, 4, None),
    ("Unpredictable: Final Damage", 7.7, 50, 22, 4, None),
    ("Student of the Blade: Skill Damage", 23.1, 150, 22, 4, None),
    ("Student of the Blade: Max Damage Multiplier", 30.8, 200, 22, 4, None),
    ("Soul Blessing III: Final Damage", 30.8, 200, 22, 4, ("SOUL_BLESSING_III", D.SOUL_BLESSING_III)),
]

# shown base cooldown and the "(-x)" reduction (Skill Cooldown Decrease 1.5 s + the cooldown masteries cutting the base: Sol Rush -30 % at 90, True Sight -25 % at 98)
COOLDOWNS = [
    ("Elemental Harmony", 60, 1.5, "ELEMENTAL_HARMONY"), ("Soul Elemental", 28, 1.5, "SOUL_ELEMENTAL"), ("Cosmic Matter", 14, 1.5, "COSMIC_MATTER"),
    ("Equinox Cycle", 30, 1.5, "EQUINOX_CYCLE"), ("Sol Rush", 26, 9.3, "SOL_RUSH"), ("True Sight", 27, 8.2, "TRUE_SIGHT"),
    ("Cosmic Shower", 22, 1.5, "COSMIC_SHOWER"), ("Equinox Slash", 11, 1.5, "EQUINOX_SLASH"), ("Impaling Rays", 24, 1.5, "IMPALING_RAYS"),
    ("Cosmic Burst", 19, 1.5, "COSMIC_BURST"),
]


def trunc1(v):
    """The game truncates to one decimal (1e-7 absorbs floating-point noise on exact values like 601.5)."""
    return math.floor(v * 10 + 1e-7) / 10


def check_values():
    bad = []
    for name, shown, base, fidx, step, ref in TABLE:
        lvl = SL.input_level(step)
        if lvl != TOTAL_LEVEL[step]:
            bad.append(f"{name}: total level {lvl} != {TOTAL_LEVEL[step]}")
        got = trunc1(SL.coeff_pct(base, fidx, True, step))
        if got != shown:
            bad.append(f"{name}: engine {got} (raw {SL.coeff_pct(base, fidx, True, step)!r}) != shown {shown}")
        if ref is not None:                        # the data module stores the same triple
            key, d = ref
            if d["base"] != base or d["fidx"] != fidx or (("step" in d) and d["step"] != step):
                bad.append(f"{name}: engine data {key} = (base {d['base']}, idx {d['fidx']}, step {d.get('step')}) != table ({base}, {fidx}, {step})")
    return bad


def check_cooldowns():
    inputs = dict(DW.defaults("Chapter Hunt"), level=LEVEL, skill_cooldown_decrease=1.5, **BONUS)
    m = DW.model(inputs)
    bad = []
    for name, base, shown_reduction, key in COOLDOWNS:
        cd = m.skills[key]["cooldown"] if key in m.skills else float(D.BUFF_COOLDOWNS[key])      # (base after the mastery cut, before Skill Cooldown Decrease)
        eff = m.fight.eff_cooldown(cd, True)
        reduction = trunc1(base - eff)
        if reduction != shown_reduction:
            bad.append(f"{name}: cooldown {base} reduced by {reduction} (effective {eff}) != shown (-{shown_reduction})")
    return bad


def check_model_levels():
    """The model resolves the same total levels / unlocks as the in-game text at level 120 (Soul Blessing III needs level 125: locked)."""
    inputs = dict(DW.defaults("Chapter Hunt"), level=LEVEL, **BONUS)
    m = DW.model(inputs)
    bad = []
    if not abs(m.se_attack_full - (SL.coeff_pct(150, 21, True, 1) + SL.coeff_pct(50, 22, True, 2))) < 1e-9:
        bad.append("Soul Elemental + Soul Blessing attack")
    if m.unlocked("SOUL_BLESSING_III"):
        bad.append("Soul Blessing III must be locked below character level 125")
    if not m.unlocked("MASTER_OF_THE_SWORD"):
        bad.append("Master of the Sword unlocks at 110")
    return bad


def run(verbose=True):
    bad = check_values() + check_cooldowns() + check_model_levels()
    n = len(TABLE) + len(COOLDOWNS)
    if verbose:
        if bad:
            print("FAIL:")
            for b in bad:
                print("  -", b)
        else:
            print(f"OK: {n} displayed values reproduced")
    return n, bad


def test_dawn_warrior_displayed_values():
    n, bad = run(verbose=False)
    assert n > 0 and not bad, "\n".join(bad)


if __name__ == "__main__":
    _n, _bad = run()
    sys.exit(1 if _bad else 0)
