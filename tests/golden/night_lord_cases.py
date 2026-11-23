"""The golden input matrix for Night Lord (plain data, no workbook, no engine import).

``night_lord_cases()`` returns ``[(case_id, inputs_dict), ...]``; an inputs dict has exactly the shape ``engine.classes.night_lord.compute`` takes (see
``cases.py`` for FP-Mage: the workbook's Inputs keys resolved for the content type, ``None`` for "not applicable" keys, plus ``level``,
``content_type``, ``companion_choice``, ``companion_level``).  Night Lord's own keys: ``flat_luk`` / ``luk_pct`` / ``dex`` and ``incoming_hit_rate``
(Shadow Shifter's counterattack).  Artifact slots are not part of the inputs (the verify script ignores them).
"""
from case_common import APPLICABLE, COMPANIONS, CONTENT_TYPES, DEFAULT_CHAPTER_STAGE, make_inputs  # noqa: F401

# Stat set A: late-game magnitudes.  Stat set B: a weaker, rounder character (low crit, wide min/max gap, no skill-level bonuses).
STATS_A = dict(
    flat_attack=1209199, attack_pct=34372.5, defense=54763, crit_rate=152.5, crit_damage=370.4, attack_speed=55.5,
    flat_luk=67948, luk_pct=344.2, dex=896, damage=978.6, damage_amp=102.5, basic_attack_damage=38, skill_damage=123,
    def_pen=50, boss_damage=303.3, normal_damage=249.7, status_effect_damage=0, min_damage=282.2, max_damage=310.4,
    final_damage=108.1, skill_lvl_1st=0, skill_lvl_2nd=0, skill_lvl_3rd=16, skill_lvl_4th=120, skill_lvl_all=63,
    skill_cooldown_decrease=0, basic_attack_target_increase=6, buff_duration_increase_pct=22.2,
    companion_summon_time_increase_pct=0, boss_normal_weight_choice="Equal", max_enemies_hit=999, incoming_hit_rate=1, pvp_fight_length=15,
)
STATS_B = dict(
    flat_attack=250000, attack_pct=1800, defense=12000, crit_rate=60, crit_damage=180, attack_speed=20,
    flat_luk=15000, luk_pct=120, dex=300, damage=250, damage_amp=20, basic_attack_damage=10, skill_damage=40,
    def_pen=20, boss_damage=80, normal_damage=60, status_effect_damage=0, min_damage=100, max_damage=140,
    final_damage=30, skill_lvl_1st=0, skill_lvl_2nd=0, skill_lvl_3rd=0, skill_lvl_4th=0, skill_lvl_all=0,
    skill_cooldown_decrease=0, basic_attack_target_increase=1, buff_duration_increase_pct=0,
    companion_summon_time_increase_pct=0, boss_normal_weight_choice="A Little More Normal", max_enemies_hit=999, incoming_hit_rate=1,
    pvp_fight_length=15,
)


# Night Lord's own level thresholds: every UNLOCK_LEVEL (Lv15..125) plus the mastery / hit-count / target-count / duration / cooldown breakpoints of the
# verify script (24 Dark Sight duration; the passive rows' unlocks 38 40 45 72 75 gate nothing numerically, 33 / 125 kept as the sample), 39 44 47 68 73 78 82 90 94 104 106 108 107 111 122 126 130 134 138 and the Showdown chains 102 106 111 116 120 124
# 128 132 136) and the stun skill's own unlock (Gust Charm Lv35: the first level with a player stun)
THRESHOLDS = [15, 24, 33, 35, 39, 43, 44, 47, 60, 63, 66, 68, 69, 73, 74, 78, 82, 90, 94, 100, 102, 103, 104, 105, 106, 107, 108,
              110, 111, 115, 116, 117, 118, 120, 122, 124, 125, 126, 128, 130, 132, 134, 136, 138]
# the threshold and the level just below it (an off-by-one in a ``level >= T`` gate is caught at T - 1 as well as at T)
UNLOCK_AND_MASTERY_LEVELS = sorted(set(THRESHOLDS) | {t - 1 for t in THRESHOLDS})


def night_lord_cases():
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

    # 2. content type x level, no companion, stat set B (the stun: Gust Charm Lv35; Showdown Lv100; the first levels have no row at all)
    for lv in (14, 34, 35, 100, 200):
        for ct in CONTENT_TYPES:
            add(f"B{lv}/{ct}/none", ct, lv, STATS_B, "none")
    # ... and a companion at those levels for four representative contents (one KO, one phase, one steady, PvP)
    for lv in (35, 100, 200):
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
                     ("World Boss", "blaze"), ("PvP", "none")):
        add(f"A140/{ct}/{comp}/cdr10", ct, 140, STATS_A, comp, skill_cooldown_decrease=10,
            **(dict(status_effect_damage=30) if comp == "blaze" else {}))
    add("A140/Chapter Hunt/wind/cdr3", "Chapter Hunt", 140, STATS_A, "wind", skill_cooldown_decrease=3, companion_summon_time_increase_pct=20)
    # (CDR above the surrogate-cooldown rows' own values: Assassin's Mark 2-2.5 s and Venom 1 s are exempt, everything else floors at 0.1 s)
    add("A140/Chapter Hunt/none/cdr50", "Chapter Hunt", 140, STATS_A, "none", skill_cooldown_decrease=50)
    add("A140/World Boss/none/cdr50", "World Boss", 140, STATS_A, "none", skill_cooldown_decrease=50)

    # 4. Status Effect Damage on the KO / stun contents without a companion (Gust Charm's own stun from Lv35)
    for ct in ("World Boss", "Enhancement Dungeon"):
        add(f"A140/{ct}/none/status65", ct, 140, STATS_A, "none", status_effect_damage=65.6)
        add(f"B125/{ct}/none/status40", ct, 125, STATS_B, "none", status_effect_damage=40)
    add("A140/Chapter Boss/none/status65", "Chapter Boss", 140, STATS_A, "none", status_effect_damage=65.6)
    add("A140/Breakthrough/none/status65", "Breakthrough", 140, STATS_A, "none", status_effect_damage=65.6)
    add("B104/Chapter Boss/none/status40", "Chapter Boss", 104, STATS_B, "none", status_effect_damage=40)
    add("B34/Chapter Boss/none/status40", "Chapter Boss", 34, STATS_B, "none", status_effect_damage=40)
    add("B35/Chapter Boss/none/status40", "Chapter Boss", 35, STATS_B, "none", status_effect_damage=40)

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

    # 7. unlock / mastery level boundaries: World Boss (engine on: Gust Charm's stun + KO), Chapter Hunt (steady state), Breakthrough (the stun lengthens
    # the boss phase), Hero Dungeon (blended, no KO), Enhancement Dungeon (engine on, short fight)
    for lv in UNLOCK_AND_MASTERY_LEVELS:
        add(f"B{lv}/World Boss/none", "World Boss", lv, STATS_B, "none")
    # (normal-monster content: every target-count gate - Assassin's Mark 107 - on both sides, every row's unlock; Toxic Venom Lv117)
    for lv in THRESHOLDS[::3] + [34, 35, 62, 63, 77, 78, 93, 94, 103, 104, 106, 107, 108, 116, 117, 137, 138, 121, 122, 131, 132]:
        add(f"B{lv}/Chapter Hunt/none", "Chapter Hunt", lv, STATS_B, "none")
    for lv in (34, 35, 36, 62, 63, 68, 69, 99, 103, 104, 107, 108, 117, 126, 130, 136, 138):
        add(f"B{lv}/Breakthrough/none", "Breakthrough", lv, STATS_B, "none")
    for lv in (34, 35, 68, 69, 99, 100, 104, 105, 109, 110, 114, 115, 117, 126, 130, 136, 138):
        add(f"B{lv}/Enhancement Dungeon/none", "Enhancement Dungeon", lv, STATS_B, "none")
    for lv in (34, 35, 69, 100, 104, 110, 117, 126, 130, 138):
        add(f"A{lv}/Hero Dungeon/none", "Hero Dungeon", lv, STATS_A, "none")
    for lv in (35, 63, 69, 90, 104, 110, 117, 130, 138):
        add(f"B{lv}/PvP/none", "PvP", lv, STATS_B, "none")
    # a companion across the stun / engine-buff boundaries (Gust Charm's own stun and the companion's windows overlap)
    for lv in (35, 69, 105, 110, 115, 117):
        add(f"A{lv}/World Boss/wind", "World Boss", lv, STATS_A, "wind", companion_summon_time_increase_pct=20)
        add(f"A{lv}/Breakthrough/blaze", "Breakthrough", lv, STATS_A, "blaze", status_effect_damage=30)

    # 8. attack speed extremes (Nimble Feet / Alchemic Adrenaline / actions per second), crit rate below the cap, big skill-level bonuses, the min / max
    # damage spread and Shadow Shifter's incoming hit rate
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
    for ihr in (0, 0.5, 3, 12):
        for ct in ("World Boss", "Chapter Hunt", "Breakthrough", "PvP"):
            add(f"A140/{ct}/none/ihr{ihr}", ct, 140, STATS_A, "none", incoming_hit_rate=ihr)
    for lv in (114, 115):
        add(f"B{lv}/Chapter Hunt/none/ihr5", "Chapter Hunt", lv, STATS_B, "none", incoming_hit_rate=5)
        add(f"B{lv}/World Boss/blaze/ihr5", "World Boss", lv, STATS_B, "blaze", incoming_hit_rate=5, status_effect_damage=30)
    # extremes of the Dark Sight / Frailty Curse / Alchemic Adrenaline averages
    add("A140/Chapter Hunt/none/buff100", "Chapter Hunt", 140, STATS_A, "none", buff_duration_increase_pct=100)
    add("A140/World Boss/none/buff100", "World Boss", 140, STATS_A, "none", buff_duration_increase_pct=100)
    add("A140/PvP/none/buff100/len5", "PvP", 140, STATS_A, "none", buff_duration_increase_pct=100, pvp_fight_length=5)

    return cases


if __name__ == "__main__":
    cs = night_lord_cases()
    print(len(cs), "cases;", len({c for c, _ in cs}), "unique ids")
