"""The golden input matrix for Dark Knight (plain data, no workbook, no engine import).

``dark_knight_cases()`` returns ``[(case_id, inputs_dict), ...]``; an inputs dict has exactly the shape ``engine.classes.dark_knight.compute`` takes (see
``cases.py`` for FP-Mage: the workbook's Inputs keys resolved for the content type, ``None`` for "not applicable" keys, plus ``level``,
``content_type``, ``companion_choice``, ``companion_level``).  Artifact slots are not part of the inputs (the verify script ignores them).
"""
from case_common import APPLICABLE, COMPANIONS, CONTENT_TYPES, DEFAULT_CHAPTER_STAGE, make_inputs  # noqa: F401

# Stat set A: late-game magnitudes.  Stat set B: a weaker, rounder character (low crit, wide min/max gap, no skill-level bonuses).
STATS_A = dict(
    flat_attack=1209199, attack_pct=34372.5, defense=54763, defense_pct=38.5, crit_rate=152.5, crit_damage=370.4, attack_speed=55.5,
    flat_str=67948, str_pct=344.2, dex=896, damage=978.6, damage_amp=102.5, basic_attack_damage=38, skill_damage=123,
    def_pen=50, boss_damage=303.3, normal_damage=249.7, status_effect_damage=0, min_damage=282.2, max_damage=310.4,
    final_damage=108.1, skill_lvl_1st=0, skill_lvl_2nd=0, skill_lvl_3rd=16, skill_lvl_4th=120, skill_lvl_all=63,
    skill_cooldown_decrease=0, basic_attack_target_increase=6, buff_duration_increase_pct=22.2,
    companion_summon_time_increase_pct=0, boss_normal_weight_choice="Equal", max_enemies_hit=999, pvp_fight_length=15,
)
STATS_B = dict(
    flat_attack=250000, attack_pct=1800, defense=12000, defense_pct=0, crit_rate=60, crit_damage=180, attack_speed=20,
    flat_str=15000, str_pct=120, dex=300, damage=250, damage_amp=20, basic_attack_damage=10, skill_damage=40,
    def_pen=20, boss_damage=80, normal_damage=60, status_effect_damage=0, min_damage=100, max_damage=140,
    final_damage=30, skill_lvl_1st=0, skill_lvl_2nd=0, skill_lvl_3rd=0, skill_lvl_4th=0, skill_lvl_all=0,
    skill_cooldown_decrease=0, basic_attack_target_increase=1, buff_duration_increase_pct=0,
    companion_summon_time_increase_pct=0, boss_normal_weight_choice="A Little More Normal", max_enemies_hit=999, pvp_fight_length=15,
)

# Stat set C: a mid-game character WITH skill-level bonuses (they move every skill's FactorTable lookup and the buffs' Attack%) and a Cooldown Decrease.
STATS_C = dict(
    flat_attack=640000, attack_pct=9000.5, defense=30000, defense_pct=12.25, crit_rate=100, crit_damage=250.5, attack_speed=35,
    flat_str=36000, str_pct=210, dex=500, damage=500, damage_amp=60, basic_attack_damage=22, skill_damage=75,
    def_pen=35, boss_damage=150, normal_damage=120, status_effect_damage=0, min_damage=180, max_damage=200,
    final_damage=60, skill_lvl_1st=3, skill_lvl_2nd=5, skill_lvl_3rd=30, skill_lvl_4th=45, skill_lvl_all=20,
    skill_cooldown_decrease=1.5, basic_attack_target_increase=3, buff_duration_increase_pct=10,
    companion_summon_time_increase_pct=0, boss_normal_weight_choice="Equal", max_enemies_hit=999, pvp_fight_length=15,
)


# Dark Knight's own level thresholds (UNLOCK_LEVEL + mastery / haste / target-count / boss-clause / Weaken breakpoints of the verify script; Iron Wall Lv38)
UNLOCK_AND_MASTERY_LEVELS = [33, 35, 38, 39, 40, 43, 44, 45, 49, 50, 54, 60, 63, 66, 68, 69, 72, 73, 75, 78, 82, 90, 94, 98, 100, 102, 103, 104,
                             105, 106, 107, 108, 110, 111, 113, 115, 116, 117, 118, 120, 122, 124, 125, 126, 128, 130, 132, 134, 136, 138]


def dark_knight_cases():
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

    # 2. content type x level, no companion, stat set B (Evil Eye Shock Lv40 + Rush Lv63 are the player stuns; Rush haste at Lv90)
    for lv in (39, 40, 63, 100, 200):
        for ct in CONTENT_TYPES:
            add(f"B{lv}/{ct}/none", ct, lv, STATS_B, "none")
    # ... and a companion at those levels for four representative contents (one KO, one phase, one steady, PvP)
    for lv in (30, 125, 200):
        for ct in ("World Boss", "Breakthrough", "Chapter Hunt", "PvP"):
            add(f"B{lv}/{ct}/blaze", ct, lv, STATS_B, "blaze", status_effect_damage=30)

    # 3. summoning time (the flip cases), buff duration, cooldown decrease
    for st in (12, 14):
        for ct in ("World Boss", "Breakthrough", "Chapter Hunt", "Chapter Boss", "PvP"):
            add(f"A140/{ct}/blaze/summon{st}", ct, 140, STATS_A, "blaze", status_effect_damage=30, companion_summon_time_increase_pct=st)
    for bd in (40, 60):
        for ct in ("World Boss", "Hero Dungeon", "Chapter Hunt"):
            add(f"A140/{ct}/none/buff{bd}", ct, 140, STATS_A, "none", buff_duration_increase_pct=bd)
            add(f"A140/{ct}/blaze/buff{bd}", ct, 140, STATS_A, "blaze", buff_duration_increase_pct=bd, status_effect_damage=30)
    for cdr in (3, 5):
        for ct in ("World Boss", "Breakthrough", "Chapter Hunt", "Enhancement Dungeon", "PvP"):
            add(f"A140/{ct}/none/cdr{cdr}", ct, 140, STATS_A, "none", skill_cooldown_decrease=cdr)
        add(f"A140/World Boss/blaze/cdr{cdr}", "World Boss", 140, STATS_A, "blaze", skill_cooldown_decrease=cdr, status_effect_damage=30)
        add(f"A140/Chapter Hunt/wind/cdr{cdr}", "Chapter Hunt", 140, STATS_A, "wind", skill_cooldown_decrease=cdr, companion_summon_time_increase_pct=20)

    # 4. Status Effect Damage on the KO / stun contents without a companion
    for ct in ("World Boss", "Enhancement Dungeon"):
        add(f"A140/{ct}/none/status65", ct, 140, STATS_A, "none", status_effect_damage=65.6)
        add(f"B125/{ct}/none/status40", ct, 125, STATS_B, "none", status_effect_damage=40)
        add(f"B45/{ct}/none/status40", ct, 45, STATS_B, "none", status_effect_damage=40)      # only Evil Eye Shock's stun is unlocked
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
    add("A140/PvP/wind/len30", "PvP", 140, STATS_A, "wind", pvp_fight_length=30, companion_summon_time_increase_pct=20)
    add("A140/PvP/none/len5", "PvP", 140, STATS_A, "none", pvp_fight_length=5)

    # 7. unlock / mastery level boundaries: World Boss (engine on: player stuns + KO), Chapter Hunt (steady state), Breakthrough (stun lengthens
    # the boss phase), Hero Dungeon (blended, no KO), Enhancement Dungeon (engine on, short fight)
    for lv in UNLOCK_AND_MASTERY_LEVELS:
        add(f"B{lv}/World Boss/none", "World Boss", lv, STATS_B, "none")
    for lv in (38, 45, 69, 94, 104, 115, 126, 138):
        add(f"B{lv}/Chapter Hunt/none", "Chapter Hunt", lv, STATS_B, "none")
    for lv in (40, 63, 82, 90, 115, 136, 138):
        add(f"B{lv}/Breakthrough/none", "Breakthrough", lv, STATS_B, "none")
        add(f"B{lv}/Enhancement Dungeon/none", "Enhancement Dungeon", lv, STATS_B, "none")
    for lv in (100, 117, 130, 138):
        add(f"A{lv}/Hero Dungeon/none", "Hero Dungeon", lv, STATS_A, "none")
    add("B90/PvP/none", "PvP", 90, STATS_B, "none")
    add("B130/PvP/none", "PvP", 130, STATS_B, "none")
    add("B82/PvP/none", "PvP", 82, STATS_B, "none")

    # 8. skill-level bonuses (stat set C: every FactorTable lookup moves) and Iron Wall (Lv38: Defense / Defense % -> STR) across the content shapes
    for lv in (37, 38, 105, 140, 200):
        for ct in ("World Boss", "Chapter Hunt", "Breakthrough", "PvP"):
            add(f"C{lv}/{ct}/none", ct, lv, STATS_C, "none")
    for lv in (40, 69, 104, 140):
        add(f"C{lv}/World Boss/blaze", "World Boss", lv, STATS_C, "blaze", status_effect_damage=30)
        add(f"C{lv}/Hero Dungeon/wind", "Hero Dungeon", lv, STATS_C, "wind", companion_summon_time_increase_pct=20)
    for ct in ("World Boss", "Chapter Hunt", "PvP", "Chapter Boss"):
        add(f"A140/{ct}/none/def0", ct, 140, STATS_A, "none", defense=0, defense_pct=0)
        add(f"A140/{ct}/none/def_huge", ct, 140, STATS_A, "none", defense=900000, defense_pct=250)
    for bd in (60, 150):
        for ct in ("World Boss", "Chapter Hunt", "Hero Dungeon"):
            add(f"C140/{ct}/none/buff{bd}", ct, 140, STATS_C, "none", buff_duration_increase_pct=bd)
    for cdr in (0, 5, 10):
        for ct in ("World Boss", "Chapter Hunt", "PvP"):
            add(f"C140/{ct}/bow/cdr{cdr}", ct, 140, STATS_C, "bow", skill_cooldown_decrease=cdr)
    add("C140/World Boss/none/cdr30", "World Boss", 140, STATS_C, "none", skill_cooldown_decrease=30)     # every cooldown at the 0.1 s floor
    add("C140/Chapter Hunt/none/cdr30", "Chapter Hunt", 140, STATS_C, "none", skill_cooldown_decrease=30)
    # attack speed extremes: the cast rate eats every action / no attack speed at all
    add("C140/Chapter Hunt/none/as150", "Chapter Hunt", 140, STATS_C, "none", attack_speed=150)
    add("C140/World Boss/none/as150", "World Boss", 140, STATS_C, "none", attack_speed=150)
    add("C140/Breakthrough/none/as0", "Breakthrough", 140, STATS_C, "none", attack_speed=0, basic_attack_target_increase=0)
    add("C140/World Boss/none/as0", "World Boss", 140, STATS_C, "none", attack_speed=0)
    add("C140/World Boss/none/fd0", "World Boss", 140, STATS_C, "none", final_damage=0, status_effect_damage=65.6)
    add("C140/Chapter Hunt/none/cap0", "Chapter Hunt", 140, STATS_C, "none", max_enemies_hit=0)      # a blank Max Enemies cell reads as 0
    # companions at the other levels (stat set C: skill-level bonuses) and the three summoning-time / CDR combinations that flip the candidate choice
    for comp in ("blaze", "wind", "bow"):
        for ct in ("World Boss", "Enhancement Dungeon", "Chapter Boss"):
            over = {"status_effect_damage": 30} if comp == "blaze" else ({"companion_summon_time_increase_pct": 20} if comp == "wind" else {})
            add(f"C140/{ct}/{comp}", ct, 140, STATS_C, comp, **over)

    return cases


if __name__ == "__main__":
    cs = dark_knight_cases()
    print(len(cs), "cases;", len({c for c, _ in cs}), "unique ids")
