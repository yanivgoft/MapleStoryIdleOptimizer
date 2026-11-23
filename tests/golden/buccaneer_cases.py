"""The golden input matrix for Buccaneer (plain data, no workbook, no engine import).

``buccaneer_cases()`` returns ``[(case_id, inputs_dict), ...]``; an inputs dict has exactly the shape ``engine.classes.buccaneer.compute`` takes (see
``cases.py`` for FP-Mage: the workbook's Inputs keys resolved for the content type, ``None`` for "not applicable" keys, plus ``level``,
``content_type``, ``companion_choice``, ``companion_level``).  Artifact slots are not part of the inputs (the verify script ignores them).
"""
from case_common import APPLICABLE, COMPANIONS, CONTENT_TYPES, DEFAULT_CHAPTER_STAGE, make_inputs  # noqa: F401

# Stat set A: late-game magnitudes.  Stat set B: a weaker, rounder character (low crit, wide min/max gap, no skill-level bonuses).
STATS_A = dict(
    flat_attack=1209199, attack_pct=34372.5, defense=54763, crit_rate=152.5, crit_damage=370.4, attack_speed=55.5,
    flat_str=67948, str_pct=344.2, dex=896, damage=978.6, damage_amp=102.5, basic_attack_damage=38, skill_damage=123,
    def_pen=50, boss_damage=303.3, normal_damage=249.7, status_effect_damage=0, min_damage=282.2, max_damage=310.4,
    final_damage=108.1, skill_lvl_1st=0, skill_lvl_2nd=0, skill_lvl_3rd=16, skill_lvl_4th=120, skill_lvl_all=63,
    skill_cooldown_decrease=0, basic_attack_target_increase=6, buff_duration_increase_pct=22.2,
    companion_summon_time_increase_pct=0, boss_normal_weight_choice="Equal", max_enemies_hit=999, pvp_fight_length=15,
)
STATS_B = dict(
    flat_attack=250000, attack_pct=1800, defense=12000, crit_rate=60, crit_damage=180, attack_speed=20,
    flat_str=15000, str_pct=120, dex=300, damage=250, damage_amp=20, basic_attack_damage=10, skill_damage=40,
    def_pen=20, boss_damage=80, normal_damage=60, status_effect_damage=0, min_damage=100, max_damage=140,
    final_damage=30, skill_lvl_1st=0, skill_lvl_2nd=0, skill_lvl_3rd=0, skill_lvl_4th=0, skill_lvl_all=0,
    skill_cooldown_decrease=0, basic_attack_target_increase=1, buff_duration_increase_pct=0,
    companion_summon_time_increase_pct=0, boss_normal_weight_choice="A Little More Normal", max_enemies_hit=999, pvp_fight_length=15,
)

# Stat set C: a mid-game character WITH skill-level bonuses (they scale every skill's FactorTable lookup) and a high Cooldown Decrease.
STATS_C = dict(
    flat_attack=640000, attack_pct=9000.5, defense=30000, crit_rate=100, crit_damage=250.5, attack_speed=35,
    flat_str=36000, str_pct=210, dex=500, damage=500, damage_amp=60, basic_attack_damage=22, skill_damage=75,
    def_pen=35, boss_damage=150, normal_damage=120, status_effect_damage=0, min_damage=180, max_damage=200,
    final_damage=60, skill_lvl_1st=3, skill_lvl_2nd=5, skill_lvl_3rd=30, skill_lvl_4th=45, skill_lvl_all=20,
    skill_cooldown_decrease=1.5, basic_attack_target_increase=3, buff_duration_increase_pct=10,
    companion_summon_time_increase_pct=0, boss_normal_weight_choice="Equal", max_enemies_hit=999, pvp_fight_length=15,
)


# Buccaneer's own level thresholds (UNLOCK_LEVEL + every mastery / haste / target-count / hit-count / assault-mode breakpoint of the verify script)
UNLOCK_AND_MASTERY_LEVELS = [10, 15, 33, 35, 38, 39, 40, 43, 63, 66, 68, 69, 72, 73, 74, 75, 78, 82, 94, 100, 102, 103, 104, 105, 106, 107, 108, 110,
                             111, 113, 115, 116, 117, 118, 120, 122, 124, 125, 126, 128, 130, 132, 134, 136, 138]


def buccaneer_cases():
    cases = []

    seen = set()

    def add(cid, *a, **k):
        if cid not in seen:                      # the level sweeps overlap the matrix above
            seen.add(cid)
            cases.append((cid, make_inputs(*a, **k)))

    # 1. content type x companion at level 140, stat set A (Blaze runs with Status Effect Damage 30; Wind Archer with +20% summoning time)
    for ct in CONTENT_TYPES:
        for comp in COMPANIONS:
            over = {}
            if comp == "blaze":
                over["status_effect_damage"] = 30
            if comp == "wind":
                over["companion_summon_time_increase_pct"] = 20
            add(f"A140/{ct}/{comp}", ct, 140, STATS_A, comp, **over)

    # 2. content type x level, no companion, stat set B (Corkscrew Blow: Lv63 unlock = the player's stun; Hook Bomber Lv100; Octopunch haste Lv134)
    for lv in (30, 62, 63, 100, 200):
        for ct in CONTENT_TYPES:
            add(f"B{lv}/{ct}/none", ct, lv, STATS_B, "none")
    # ... and a companion at those levels for four representative contents (one KO, one phase, one steady, PvP)
    for lv in (100, 125, 200):
        for ct in ("World Boss", "Breakthrough", "Chapter Hunt", "PvP"):
            add(f"B{lv}/{ct}/blaze", ct, lv, STATS_B, "blaze", status_effect_damage=30)

    # 3. summoning time (the flip cases), buff duration, cooldown decrease
    for st in (12, 14):
        for ct in ("World Boss", "Breakthrough", "Chapter Hunt", "Chapter Boss", "PvP"):
            add(f"A140/{ct}/blaze/summon{st}", ct, 140, STATS_A, "blaze", status_effect_damage=30, companion_summon_time_increase_pct=st)
    for ct in ("World Boss", "Hero Dungeon", "Chapter Hunt"):
        add(f"A140/{ct}/none/buff40", ct, 140, STATS_A, "none", buff_duration_increase_pct=40)
        add(f"A140/{ct}/blaze/buff40", ct, 140, STATS_A, "blaze", buff_duration_increase_pct=40, status_effect_damage=30)
    for ct in ("World Boss", "Breakthrough", "Chapter Hunt", "Enhancement Dungeon"):
        add(f"A140/{ct}/none/cdr3", ct, 140, STATS_A, "none", skill_cooldown_decrease=3)
    add("A140/World Boss/blaze/cdr3", "World Boss", 140, STATS_A, "blaze", skill_cooldown_decrease=3, status_effect_damage=30)
    add("A140/Chapter Hunt/wind/cdr3", "Chapter Hunt", 140, STATS_A, "wind", skill_cooldown_decrease=3, companion_summon_time_increase_pct=20)

    # 4. Status Effect Damage on the KO / stun contents without a companion
    for ct in ("World Boss", "Enhancement Dungeon"):
        add(f"A140/{ct}/none/status65", ct, 140, STATS_A, "none", status_effect_damage=65.6)
        add(f"B125/{ct}/none/status40", ct, 125, STATS_B, "none", status_effect_damage=40)
    add("A140/Chapter Boss/none/status65", "Chapter Boss", 140, STATS_A, "none", status_effect_damage=65.6)
    add("A140/Breakthrough/none/status65", "Breakthrough", 140, STATS_A, "none", status_effect_damage=65.6)

    # 5. chapter / stage boundaries (28-9, 28->29, 38->39, 39->40) for Breakthrough / Chapter Hunt / Chapter Boss
    for stage in ("28-9", "28-20", "29-1", "38-14", "39-1", "40-5", "45-3"):
        add(f"A140/Breakthrough/none/{stage}", "Breakthrough", 140, STATS_A, "none", chapter_stage=stage)
    add("A140/Chapter Hunt/blaze/39-4", "Chapter Hunt", 140, STATS_A, "blaze", chapter_stage="39-4", status_effect_damage=30)
    add("A140/Chapter Hunt/none/38-14", "Chapter Hunt", 140, STATS_A, "none", chapter_stage="38-14")
    add("A140/Chapter Boss/none/28", "Chapter Boss", 140, STATS_A, "none", chapter_stage="28")
    add("A140/Chapter Boss/none/bad", "Chapter Boss", 140, STATS_A, "none", chapter_stage="x-y")
    add("A140/Weapon Dungeon/none/150", "Weapon Dungeon", 140, STATS_A, "none", chapter_stage="150")

    # 6. enemy cap, target increase, boss/normal emphasis, PvP length
    for cap in (1, 3, 8):
        add(f"A140/Chapter Hunt/none/cap{cap}", "Chapter Hunt", 140, STATS_A, "none", max_enemies_hit=cap)
    add("A140/Breakthrough/blaze/cap3", "Breakthrough", 140, STATS_A, "blaze", max_enemies_hit=3, status_effect_damage=30)
    add("A140/Chapter Hunt/none/tgt0", "Chapter Hunt", 140, STATS_A, "none", basic_attack_target_increase=0)
    for emph in ("More Normal", "A Little More Normal", "A Little More Boss", "More Boss"):
        add(f"A140/Breakthrough/none/{emph}", "Breakthrough", 140, STATS_A, "none", boss_normal_weight_choice=emph)
        add(f"A140/Hero Dungeon/bow/{emph}", "Hero Dungeon", 140, STATS_A, "bow", boss_normal_weight_choice=emph)
    add("A140/Hero Dungeon/blaze/More Boss", "Hero Dungeon", 140, STATS_A, "blaze", boss_normal_weight_choice="More Boss", status_effect_damage=30)
    add("A140/PvP/none/len30", "PvP", 140, STATS_A, "none", pvp_fight_length=30)
    add("A140/PvP/none/len5", "PvP", 140, STATS_A, "none", pvp_fight_length=5)
    add("A140/PvP/wind/len30", "PvP", 140, STATS_A, "wind", pvp_fight_length=30, companion_summon_time_increase_pct=20)

    # 7. unlock / mastery level boundaries: World Boss (engine on: Corkscrew stun + KO), Chapter Hunt (steady state), Breakthrough (stun lengthens
    # the boss phase), Hero Dungeon (blended, no KO), Enhancement Dungeon (engine on, short fight), Equipment Dungeon (fixed fight, normal monsters,
    # startup delay without the engine)
    for lv in UNLOCK_AND_MASTERY_LEVELS:
        add(f"B{lv}/World Boss/none", "World Boss", lv, STATS_B, "none")
    for lv in (35, 63, 66, 69, 72, 78, 94, 100, 104, 107, 118, 138):
        add(f"B{lv}/Chapter Hunt/none", "Chapter Hunt", lv, STATS_B, "none")
    for lv in (62, 63, 100, 107, 125, 134):
        add(f"B{lv}/Breakthrough/none", "Breakthrough", lv, STATS_B, "none")
        add(f"B{lv}/Enhancement Dungeon/none", "Enhancement Dungeon", lv, STATS_B, "none")
    for lv in (62, 94, 107, 118, 134):
        add(f"B{lv}/Equipment Dungeon/none", "Equipment Dungeon", lv, STATS_B, "none")
    for lv in (100, 117, 130, 138):
        add(f"A{lv}/Hero Dungeon/none", "Hero Dungeon", lv, STATS_A, "none")
    for lv in (63, 100, 120, 134, 138):
        add(f"B{lv}/PvP/none", "PvP", lv, STATS_B, "none")

    # 8. skill-level bonuses (stat set C: they move every FactorTable lookup, incl. Maple Hero / Crossbones / Time Leap / Speed Infusion / Serpent Scale)
    # with Buff Duration / Cooldown Decrease moving the buff windows, across the content shapes (engine on / off, steady state, PvP, blended)
    for lv in (66, 107, 125, 200):
        for ct in ("World Boss", "Chapter Hunt", "Breakthrough", "PvP"):
            add(f"C{lv}/{ct}/none", ct, lv, STATS_C, "none")
    for lv in (66, 107, 125, 140):
        add(f"C{lv}/World Boss/blaze", "World Boss", lv, STATS_C, "blaze", status_effect_damage=30)
        add(f"C{lv}/Hero Dungeon/wind", "Hero Dungeon", lv, STATS_C, "wind", companion_summon_time_increase_pct=20)
    for bd in (40, 60, 150):
        for ct in ("World Boss", "Chapter Hunt", "Equipment Dungeon"):
            add(f"C140/{ct}/none/buff{bd}", ct, 140, STATS_C, "none", buff_duration_increase_pct=bd)
    for cdr in (0, 3, 5, 10):
        for ct in ("World Boss", "Chapter Hunt", "PvP", "Equipment Dungeon"):
            add(f"C140/{ct}/bow/cdr{cdr}", ct, 140, STATS_C, "bow", skill_cooldown_decrease=cdr)
    add("C140/World Boss/none/cdr30", "World Boss", 140, STATS_C, "none", skill_cooldown_decrease=30)     # every cooldown at the 0.1 s floor
    add("C140/Chapter Hunt/none/cdr30", "Chapter Hunt", 140, STATS_C, "none", skill_cooldown_decrease=30)
    add("C140/Equipment Dungeon/none/cdr30", "Equipment Dungeon", 140, STATS_C, "none", skill_cooldown_decrease=30)

    # 9. attack-speed extremes: the Hook Bomber rate (what is left after the cast rate) and the Assault Mode interval T = cooldown + 0.5 / rate
    for ct in ("Chapter Hunt", "World Boss", "Equipment Dungeon", "Breakthrough", "PvP"):
        add(f"C140/{ct}/none/as150", ct, 140, STATS_C, "none", attack_speed=150)
        add(f"C140/{ct}/none/as0", ct, 140, STATS_C, "none", attack_speed=0)
    add("C140/Chapter Hunt/none/as0_cdr10", "Chapter Hunt", 140, STATS_C, "none", attack_speed=0, skill_cooldown_decrease=10)
    add("C140/Chapter Hunt/none/as0_cdr30", "Chapter Hunt", 140, STATS_C, "none", attack_speed=0, skill_cooldown_decrease=30)   # the cast rate eats every action
    add("C140/Breakthrough/none/as0_tgt0", "Breakthrough", 140, STATS_C, "none", attack_speed=0, basic_attack_target_increase=0)
    add("C140/World Boss/none/fd0", "World Boss", 140, STATS_C, "none", final_damage=0, status_effect_damage=65.6)
    add("C140/Chapter Hunt/none/cap0", "Chapter Hunt", 140, STATS_C, "none", max_enemies_hit=0)      # a blank Max Enemies cell reads as 0
    add("C140/Chapter Hunt/none/cap2_as100", "Chapter Hunt", 140, STATS_C, "none", max_enemies_hit=2, attack_speed=100)   # Nautilus FA normal-branch roll with N capped

    # 10. companion kinds at the boundaries where the Buccaneer kit changes (a companion + the Corkscrew stun together, KO and non-KO)
    for comp in ("blaze", "wind", "bow"):
        for lv in (63, 138):
            add(f"B{lv}/World Boss/{comp}", "World Boss", lv, STATS_B, comp, status_effect_damage=30,
                companion_summon_time_increase_pct=(20 if comp == "wind" else 0))
            add(f"C{lv}/Equipment Dungeon/{comp}", "Equipment Dungeon", lv, STATS_C, comp, status_effect_damage=30)
            add(f"C{lv}/Breakthrough/{comp}", "Breakthrough", lv, STATS_C, comp, status_effect_damage=30)

    return cases


if __name__ == "__main__":
    cs = buccaneer_cases()
    print(len(cs), "cases;", len({c for c, _ in cs}), "unique ids")
