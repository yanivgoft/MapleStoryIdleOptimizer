"""The golden input matrix for Marksman (plain data, no workbook, no engine import).

``marksman_cases()`` returns ``[(case_id, inputs_dict), ...]``; an inputs dict has exactly the shape ``engine.classes.marksman.compute`` takes (see
``cases.py`` for FP-Mage: the workbook's Inputs keys resolved for the content type, ``None`` for "not applicable" keys, plus ``level``,
``content_type``, ``companion_choice``, ``companion_level``).  Artifact slots are not part of the inputs (the verify script ignores them).
"""
from case_common import APPLICABLE, COMPANIONS, CONTENT_TYPES, DEFAULT_CHAPTER_STAGE, make_inputs  # noqa: F401

# Stat set A: late-game magnitudes.  Stat set B: a weaker, rounder character (low crit, wide min/max gap, no skill-level bonuses).
STATS_A = dict(
    flat_attack=1209199, attack_pct=34372.5, defense=54763, crit_rate=152.5, crit_damage=370.4, attack_speed=55.5,
    flat_dex=67948, dex_pct=344.2, str=896, damage=978.6, damage_amp=102.5, basic_attack_damage=38, skill_damage=123,
    def_pen=50, boss_damage=303.3, normal_damage=249.7, status_effect_damage=0, min_damage=282.2, max_damage=310.4,
    final_damage=108.1, skill_lvl_1st=0, skill_lvl_2nd=0, skill_lvl_3rd=16, skill_lvl_4th=120, skill_lvl_all=63,
    skill_cooldown_decrease=0, basic_attack_target_increase=6, buff_duration_increase_pct=22.2,
    companion_summon_time_increase_pct=0, boss_normal_weight_choice="Equal", max_enemies_hit=999, pvp_fight_length=15,
)
STATS_B = dict(
    flat_attack=250000, attack_pct=1800, defense=12000, crit_rate=60, crit_damage=180, attack_speed=20,
    flat_dex=15000, dex_pct=120, str=300, damage=250, damage_amp=20, basic_attack_damage=10, skill_damage=40,
    def_pen=20, boss_damage=80, normal_damage=60, status_effect_damage=0, min_damage=100, max_damage=140,
    final_damage=30, skill_lvl_1st=0, skill_lvl_2nd=0, skill_lvl_3rd=0, skill_lvl_4th=0, skill_lvl_all=0,
    skill_cooldown_decrease=0, basic_attack_target_increase=1, buff_duration_increase_pct=0,
    companion_summon_time_increase_pct=0, boss_normal_weight_choice="A Little More Normal", max_enemies_hit=999, pvp_fight_length=15,
)


# Marksman's own level thresholds: every UNLOCK_LEVEL (Lv10..125) plus the mastery / hit-count / target-count / duration / stun breakpoints of the
# verify script (39 54 68 78 82 94 98 102 104 106 108 111 113 116 118 120 122 124 126 128 130 132 134 136 138) and the stun masteries (Lv49 Covering Fire,
# Lv98 Bolt Burst; Frostprey's periodic freeze from its Lv69 unlock)
THRESHOLDS = [10, 15, 33, 35, 38, 39, 43, 45, 49, 50, 54, 60, 63, 68, 69, 72, 74, 75, 78, 82, 94, 98, 100, 102, 103, 104, 105, 106, 107, 108,
              110, 111, 113, 115, 116, 117, 118, 120, 122, 124, 125, 126, 128, 130, 132, 134, 136, 138]
# the threshold and the level just below it (an off-by-one in a ``level >= T`` gate is caught at T - 1 as well as at T)
UNLOCK_AND_MASTERY_LEVELS = sorted(set(THRESHOLDS) | {t - 1 for t in THRESHOLDS})


def marksman_cases():
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

    # 2. content type x level, no companion, stat set B (the stuns: Covering Fire Lv49, Bolt Burst Lv98 / unlock 63, Frostprey unlock 69)
    for lv in (30, 48, 49, 100, 200):
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
        add(f"A140/{ct}/none/buff60", ct, 140, STATS_A, "none", buff_duration_increase_pct=60)
    for ct in ("World Boss", "Breakthrough", "Chapter Hunt", "Enhancement Dungeon"):
        add(f"A140/{ct}/none/cdr3", ct, 140, STATS_A, "none", skill_cooldown_decrease=3)
    add("A140/World Boss/blaze/cdr3", "World Boss", 140, STATS_A, "blaze", skill_cooldown_decrease=3, status_effect_damage=30)
    for ct, comp in (("World Boss", "none"), ("Enhancement Dungeon", "none"), ("Breakthrough", "bow"), ("Chapter Hunt", "none"),
                     ("World Boss", "blaze")):
        add(f"A140/{ct}/{comp}/cdr10", ct, 140, STATS_A, comp, skill_cooldown_decrease=10,
            **(dict(status_effect_damage=30) if comp == "blaze" else {}))
    add("A140/Chapter Hunt/wind/cdr3", "Chapter Hunt", 140, STATS_A, "wind", skill_cooldown_decrease=3, companion_summon_time_increase_pct=20)

    # 4. Status Effect Damage on the KO / stun contents without a companion
    for ct in ("World Boss", "Enhancement Dungeon"):
        add(f"A140/{ct}/none/status65", ct, 140, STATS_A, "none", status_effect_damage=65.6)
        add(f"B125/{ct}/none/status40", ct, 125, STATS_B, "none", status_effect_damage=40)
    add("A140/Chapter Boss/none/status65", "Chapter Boss", 140, STATS_A, "none", status_effect_damage=65.6)
    add("A140/Breakthrough/none/status65", "Breakthrough", 140, STATS_A, "none", status_effect_damage=65.6)
    add("B104/Chapter Boss/none/status40", "Chapter Boss", 104, STATS_B, "none", status_effect_damage=40)

    # 5. chapter / stage boundaries (28-9, 28->29, 38->39, 39->40) for Breakthrough / Chapter Hunt / Chapter Boss
    for stage in ("28-9", "28-20", "29-1", "38-14", "39-1", "40-5", "45-3"):
        add(f"A140/Breakthrough/none/{stage}", "Breakthrough", 140, STATS_A, "none", chapter_stage=stage)
    add("A140/Chapter Hunt/blaze/39-4", "Chapter Hunt", 140, STATS_A, "blaze", chapter_stage="39-4", status_effect_damage=30)
    add("A140/Chapter Hunt/none/28-9", "Chapter Hunt", 140, STATS_A, "none", chapter_stage="28-9")
    add("A140/Chapter Boss/none/28", "Chapter Boss", 140, STATS_A, "none", chapter_stage="28")
    add("A140/Chapter Boss/none/bad", "Chapter Boss", 140, STATS_A, "none", chapter_stage="x-y")
    add("A140/Weapon Dungeon/none/150", "Weapon Dungeon", 140, STATS_A, "none", chapter_stage="150")

    # 6. enemy cap, target increase, boss/normal emphasis, PvP length
    for cap in (1, 3, 8):
        add(f"A140/Chapter Hunt/none/cap{cap}", "Chapter Hunt", 140, STATS_A, "none", max_enemies_hit=cap)
        add(f"A104/EXP Dungeon/none/cap{cap}", "EXP Dungeon", 104, STATS_A, "none", max_enemies_hit=cap)
    add("A140/Breakthrough/blaze/cap3", "Breakthrough", 140, STATS_A, "blaze", max_enemies_hit=3, status_effect_damage=30)
    add("A140/Chapter Hunt/none/tgt0", "Chapter Hunt", 140, STATS_A, "none", basic_attack_target_increase=0)
    for emph in ("More Normal", "A Little More Normal", "A Little More Boss", "More Boss"):
        add(f"A140/Breakthrough/none/{emph}", "Breakthrough", 140, STATS_A, "none", boss_normal_weight_choice=emph)
        add(f"A140/Hero Dungeon/bow/{emph}", "Hero Dungeon", 140, STATS_A, "bow", boss_normal_weight_choice=emph)
    add("A140/Hero Dungeon/blaze/More Boss", "Hero Dungeon", 140, STATS_A, "blaze", boss_normal_weight_choice="More Boss", status_effect_damage=30)
    add("A140/PvP/none/len30", "PvP", 140, STATS_A, "none", pvp_fight_length=30)
    add("A140/PvP/none/len5", "PvP", 140, STATS_A, "none", pvp_fight_length=5)
    add("A140/PvP/wind/len30", "PvP", 140, STATS_A, "wind", pvp_fight_length=30, companion_summon_time_increase_pct=20)

    # 7. unlock / mastery level boundaries: World Boss (engine on: the three stuns + KO), Chapter Hunt (steady state), Breakthrough (stuns lengthen
    # the boss phase), Hero Dungeon (blended, no KO), Enhancement Dungeon (engine on, short fight)
    for lv in UNLOCK_AND_MASTERY_LEVELS:
        add(f"B{lv}/World Boss/none", "World Boss", lv, STATS_B, "none")
    # (normal-monster content: every target-count gate - Frostprey 78, Bolt Surplus 138 - on both sides, every row's unlock)
    for lv in THRESHOLDS[::2] + [49, 50, 100, 117, 118, 77, 78, 97, 98, 103, 104, 106, 107, 137, 138, 34, 35, 62, 63, 68, 69, 102]:
        add(f"B{lv}/Chapter Hunt/none", "Chapter Hunt", lv, STATS_B, "none")
    for lv in (48, 49, 50, 62, 63, 68, 69, 97, 98, 99, 103, 104, 117, 118, 126, 130, 136, 138):
        add(f"B{lv}/Breakthrough/none", "Breakthrough", lv, STATS_B, "none")
    for lv in (48, 49, 50, 68, 69, 97, 98, 100, 104, 117, 118, 126, 130, 136, 138):
        add(f"B{lv}/Enhancement Dungeon/none", "Enhancement Dungeon", lv, STATS_B, "none")
    for lv in (48, 49, 69, 98, 100, 104, 117, 126, 130, 138):
        add(f"A{lv}/Hero Dungeon/none", "Hero Dungeon", lv, STATS_A, "none")
    for lv in (49, 63, 69, 90, 98, 104, 117, 130, 138):
        add(f"B{lv}/PvP/none", "PvP", lv, STATS_B, "none")
    # a companion across the stun / engine-buff boundaries (the player's three stuns and the companion's own windows overlap)
    for lv in (49, 69, 98, 104, 117, 118):
        add(f"A{lv}/World Boss/wind", "World Boss", lv, STATS_A, "wind", companion_summon_time_increase_pct=20)
        add(f"A{lv}/Breakthrough/blaze", "Breakthrough", lv, STATS_A, "blaze", status_effect_damage=30)

    # 8. attack speed extremes (Nimble Feet / actions per second), crit rate below the cap, big skill-level bonuses and the min / max damage spread
    for aspd in (0, 100, 150):
        for ct in ("World Boss", "Chapter Hunt", "Breakthrough"):
            add(f"A140/{ct}/none/as{aspd}", ct, 140, STATS_A, "none", attack_speed=aspd)
    add("B140/Chapter Hunt/none/as150/cap2", "Chapter Hunt", 140, STATS_B, "none", attack_speed=150, max_enemies_hit=2)
    add("A140/World Boss/none/cr60", "World Boss", 140, STATS_A, "none", crit_rate=60, crit_damage=200)
    add("A140/World Boss/bow/skill+30", "World Boss", 140, STATS_A, "bow", skill_lvl_1st=30, skill_lvl_2nd=30, skill_lvl_3rd=30,
        skill_lvl_4th=30, skill_lvl_all=10)
    add("A200/Chapter Hunt/blaze", "Chapter Hunt", 200, STATS_A, "blaze", status_effect_damage=30)
    add("A200/World Boss/wind", "World Boss", 200, STATS_A, "wind", companion_summon_time_increase_pct=20)
    add("B200/World Boss/none/def0", "World Boss", 200, STATS_B, "none", def_pen=0, status_effect_damage=80)
    add("A140/PvP/blaze/defense", "PvP", 140, STATS_A, "blaze", status_effect_damage=30, defense=80000)

    return cases


if __name__ == "__main__":
    cs = marksman_cases()
    print(len(cs), "cases;", len({c for c, _ in cs}), "unique ids")
