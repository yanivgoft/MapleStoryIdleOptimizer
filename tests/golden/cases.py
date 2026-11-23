"""The golden input matrix for FP-Mage (plain data, no workbook, no engine import).

``fp_mage_cases()`` returns ``[(case_id, inputs_dict), ...]``.  An inputs dict has exactly the shape ``engine.classes.fp_mage.compute``
takes: the Inputs keys of the workbook already resolved for the chosen content type (a key that is "not applicable" to that
content type is ``None``, exactly like the blank grey cell of the workbook), plus ``level``, ``content_type``, ``companion_choice``
and ``companion_level`` (the level of the chosen companion, 0 = none / not unlocked).  Artifact slots are not part of the inputs:
the verify script does not model artifacts, so every case corresponds to "(none)" in all four slots.
"""
from case_common import APPLICABLE, COMPANIONS, CONTENT_TYPES, DEFAULT_CHAPTER_STAGE, make_inputs  # noqa: F401

# Stat set A: late-game magnitudes (a real FP-Mage's Breakthrough column).  Stat set B: a weaker, rounder character
# (low crit, wide min/max gap, no skill-level bonuses, small attack speed) that exercises other branches of the formulas.
STATS_A = dict(
    flat_attack=1209199, attack_pct=34372.5, defense=54763, crit_rate=152.5, crit_damage=370.4, attack_speed=55.5,
    flat_int=67948, int_pct=344.2, luk=896, damage=978.6, damage_amp=102.5, basic_attack_damage=38, skill_damage=123,
    def_pen=50, boss_damage=303.3, normal_damage=249.7, status_effect_damage=0, min_damage=282.2, max_damage=310.4,
    final_damage=108.1, skill_lvl_1st=0, skill_lvl_2nd=0, skill_lvl_3rd=16, skill_lvl_4th=120, skill_lvl_all=63,
    skill_cooldown_decrease=0, basic_attack_target_increase=6, buff_duration_increase_pct=22.2,
    companion_summon_time_increase_pct=0, boss_normal_weight_choice="Equal", max_enemies_hit=999, pvp_fight_length=15,
)
STATS_B = dict(
    flat_attack=250000, attack_pct=1800, defense=12000, crit_rate=60, crit_damage=180, attack_speed=20,
    flat_int=15000, int_pct=120, luk=300, damage=250, damage_amp=20, basic_attack_damage=10, skill_damage=40,
    def_pen=20, boss_damage=80, normal_damage=60, status_effect_damage=0, min_damage=100, max_damage=140,
    final_damage=30, skill_lvl_1st=0, skill_lvl_2nd=0, skill_lvl_3rd=0, skill_lvl_4th=0, skill_lvl_all=0,
    skill_cooldown_decrease=0, basic_attack_target_increase=1, buff_duration_increase_pct=0,
    companion_summon_time_increase_pct=0, boss_normal_weight_choice="A Little More Normal", max_enemies_hit=999, pvp_fight_length=15,
)


def fp_mage_cases():
    cases = []

    def add(cid, *a, **k):
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

    # 2. content type x level, no companion, stat set B
    for lv in (70, 100, 125, 200):
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

    # 4. Status Effect Damage on the KO contents without a companion
    for ct in ("World Boss", "Enhancement Dungeon"):
        add(f"A140/{ct}/none/status65", ct, 140, STATS_A, "none", status_effect_damage=65.6)
        add(f"B125/{ct}/none/status40", ct, 125, STATS_B, "none", status_effect_damage=40)

    # 5. chapter / stage boundaries (28-9, 28->29, 38->39, 39->40) for Breakthrough / Chapter Hunt / Chapter Boss
    for stage in ("28-9", "28-20", "29-1", "38-14", "39-1", "40-5", "45-3"):
        add(f"A140/Breakthrough/none/{stage}", "Breakthrough", 140, STATS_A, "none", chapter_stage=stage)
    add("A140/Chapter Hunt/blaze/39-4", "Chapter Hunt", 140, STATS_A, "blaze", chapter_stage="39-4", status_effect_damage=30)
    add("A140/Chapter Boss/none/28", "Chapter Boss", 140, STATS_A, "none", chapter_stage="28")
    add("A140/Chapter Boss/none/bad", "Chapter Boss", 140, STATS_A, "none", chapter_stage="x-y")
    add("A140/Weapon Dungeon/none/150", "Weapon Dungeon", 140, STATS_A, "none", chapter_stage="150")

    # 6. enemy cap, target increase, boss/normal emphasis
    for cap in (1, 3, 8):
        add(f"A140/Chapter Hunt/none/cap{cap}", "Chapter Hunt", 140, STATS_A, "none", max_enemies_hit=cap)
    add("A140/Breakthrough/blaze/cap3", "Breakthrough", 140, STATS_A, "blaze", max_enemies_hit=3, status_effect_damage=30)
    add("A140/Chapter Hunt/none/tgt0", "Chapter Hunt", 140, STATS_A, "none", basic_attack_target_increase=0)
    for emph in ("More Normal", "A Little More Normal", "A Little More Boss", "More Boss"):
        add(f"A140/Breakthrough/none/{emph}", "Breakthrough", 140, STATS_A, "none", boss_normal_weight_choice=emph)
    add("A140/Hero Dungeon/blaze/More Boss", "Hero Dungeon", 140, STATS_A, "blaze", boss_normal_weight_choice="More Boss", status_effect_damage=30)
    add("A140/PvP/none/len30", "PvP", 140, STATS_A, "none", pvp_fight_length=30)
    add("A140/PvP/wind/len30", "PvP", 140, STATS_A, "wind", pvp_fight_length=30, companion_summon_time_increase_pct=20)

    # 7. mastery / unlock level boundaries (World Boss: engine on; Chapter Hunt: steady state)
    for lv in (103, 105, 107, 110, 113, 115, 118, 120, 126, 130, 136, 138):
        add(f"B{lv}/World Boss/none", "World Boss", lv, STATS_B, "none")
    for lv in (104, 108, 122, 134, 138):
        add(f"B{lv}/Chapter Hunt/none", "Chapter Hunt", lv, STATS_B, "none")

    return cases


if __name__ == "__main__":
    cs = fp_mage_cases()
    print(len(cs), "cases;", len({c for c, _ in cs}), "unique ids")
