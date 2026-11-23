"""Case matrix of the Sensitivity golden file (plain data: no workbook, no engine import).

``sens_cases()`` returns ``[case, ...]``, one case = ONE evaluation of the (Sensitivity-slimmed) workbook:

    id         unique name
    inputs     engine input dict (``fp_mage.compute`` shape) + ``artifact_stars`` {id: star | None} for ALL 36 artifacts + ``companion_levels`` {name: level}
    stats      stat keys whose block / table row are read from the workbook
    toggles    artifact ids whose "(Equip)" block / staging row are read
    cdr        True: the 10 CDR milestone blocks too
    tables     True: the Companion Comparison table (+ the Summoning-Time table); needs the full Companion sheet (heavier)
    potential  {artifact id: DPS} constants written over ArtifactsInput!L (potential-line gain) - exercises the potential term of the equip rows

Every case lists only what is compared; the rest of the Sensitivity sheet is deleted from the scratch copy (the full sheet is far too big to evaluate).
"""
from cases import STATS_A, STATS_B, make_inputs

# a mid-game character with non-trivial values everywhere (crit rate below the cap, Cooldown Decrease and every skill-level bonus non-zero)
STATS_S = dict(
    flat_attack=250000, attack_pct=1800, defense=12000, crit_rate=60, crit_damage=150, attack_speed=20, flat_int=5000, int_pct=40, luk=800,
    damage=30, damage_amp=20, basic_attack_damage=15, skill_damage=20, def_pen=35, boss_damage=40, normal_damage=25, status_effect_damage=30,
    min_damage=80, max_damage=130, final_damage=12, skill_lvl_1st=3, skill_lvl_2nd=5, skill_lvl_3rd=10, skill_lvl_4th=15, skill_lvl_all=20,
    skill_cooldown_decrease=1, basic_attack_target_increase=2, buff_duration_increase_pct=15, companion_summon_time_increase_pct=0,
    boss_normal_weight_choice="A Little More Normal", max_enemies_hit=999, pvp_fight_length=15,
)

ALL_STATS = ["flat_int", "int_pct", "damage", "damage_amp", "boss_damage", "normal_damage", "status_effect_damage", "final_damage", "min_damage",
             "max_damage", "crit_rate", "crit_damage", "attack_speed", "def_pen", "basic_attack_damage", "skill_damage", "skill_lvl_1st", "skill_lvl_2nd",
             "skill_lvl_3rd", "skill_lvl_4th", "skill_lvl_all", "flat_attack", "attack_pct", "skill_cooldown_decrease", "basic_attack_target_increase",
             "buff_duration_increase_pct", "companion_summon_time_increase_pct"]
ALL_ARTIFACTS = ["charm_of_the_undead", "pigs_ribbon", "shamaness_marble", "contract_of_darkness", "rainbow_snail_shell", "hexagon_necklace",
                 "arwens_glass_shoes", "mushmoms_cap", "clear_spring_water", "athena_gloves", "zakums_stone_piece", "horntails_scale",
                 "pink_beans_giant_rib", "chalice", "old_music_box", "silver_pendant", "star_rock", "book_of_ancient", "lunar_dew", "fire_flower",
                 "soul_contract", "lit_lamp", "soul_pouch", "ancient_text_piece", "icy_soul_rock", "flaming_lava", "sayrams_necklace",
                 "bottle_of_emotion", "peach_tree", "candle", "alliance_badge", "horn_flute", "cursed_doll", "reindeer_spear", "secret_map",
                 "ring_of_cycles"]

# Star Level of every artifact in the cases (None = "Not Unlocked": the equip effect still applies at the star-0 value, but the row is not ranked)
STARS = {k: 5 for k in ALL_ARTIFACTS}
STARS.update(hexagon_necklace=3, candle=2, horn_flute=4, chalice=1, secret_map=0, soul_pouch=3, star_rock=2, lunar_dew=None, arwens_glass_shoes=2,
             book_of_ancient=3, athena_gloves=4, ring_of_cycles=2, reindeer_spear=3)
COMPANION_LEVELS_UNIFORM = 10
# varied levels for the comparison table (cycle through unlocked / low / not-unlocked)
COMPANION_NAMES = ["Wind Archer", "Dawn Warrior", "Blaze Wizard", "IL Mage", "FP Mage", "Bishop", "Night Walker", "Hero", "Paladin", "Dark Knight",
                   "Bow Master", "Marksman", "Night Lord", "Shadower", "Buccaneer", "Corsair"]


def slots(keys):
    return [{"key": k, "star": STARS[k]} for k in keys]


def case_builder(make_inputs, slots_fn=slots):
    """``case(cid, content, level, base_stats, companion, equipped, **kw)`` of a class: one case = ONE evaluation of its Sensitivity-slimmed workbook."""
    def case(cid, content, level, base_stats, companion, equipped, **kw):
        over = kw.pop("over", {})
        inputs = make_inputs(content, level, base_stats, companion, **over)
        inputs["artifacts"] = slots_fn(equipped)
        inputs["artifact_stars"] = dict(STARS)
        levels = kw.pop("companion_levels", None)
        if levels is not None:
            inputs["companion_levels"] = levels
            if inputs["companion_choice"] in levels:      # the workbook has ONE level per companion (CompanionsInput): the chosen one's level is that value
                inputs["companion_level"] = levels[inputs["companion_choice"]]
        out = dict(id=cid, inputs=inputs, stats=kw.pop("stats", []), toggles=kw.pop("toggles", []), cdr=kw.pop("cdr", False),
                   tables=kw.pop("tables", False), potential=kw.pop("potential", {}))
        assert not kw, kw
        return out
    return case


def fd_typed(base, *xs):
    """Inputs!final_damage after baked-in Final Damage artifacts of x % each were typed in (multiplicative)."""
    m = 1 + base / 100
    for x in xs:
        m *= 1 + x / 100
    return (m - 1) * 100


case = case_builder(make_inputs)


def sens_cases():
    cs = []
    S = STATS_S
    # ------------------------------------------------------------------------------------------------------------------ stats
    BB = ["bottle_of_emotion", "reindeer_spear"]
    cs.append(case("S/WB200/a", "World Boss", 200, S, "blaze", BB, stats=ALL_STATS[0:9]))
    cs.append(case("S/WB200/b", "World Boss", 200, S, "blaze", BB, stats=ALL_STATS[9:18]))
    cs.append(case("S/WB200/c", "World Boss", 200, S, "blaze", BB, stats=ALL_STATS[18:27]))
    cs.append(case("S/WB200/athena", "World Boss", 200, S, "blaze", ["book_of_ancient", "athena_gloves", "bottle_of_emotion", "ring_of_cycles"],
                   stats=["crit_rate", "crit_damage", "attack_speed", "max_damage", "skill_lvl_3rd", "def_pen"]))
    cs.append(case("S/BT140/a", "Breakthrough", 140, S, "blaze", BB,
                   stats=["flat_int", "int_pct", "boss_damage", "normal_damage", "status_effect_damage", "crit_rate", "attack_speed", "def_pen",
                          "skill_lvl_all", "skill_lvl_2nd", "skill_lvl_3rd"]))
    cs.append(case("S/BT140/b", "Breakthrough", 140, S, "blaze", BB,
                   stats=["skill_cooldown_decrease", "buff_duration_increase_pct", "companion_summon_time_increase_pct", "final_damage",
                          "basic_attack_target_increase", "skill_damage", "flat_attack", "crit_damage", "damage_amp", "max_damage"]))
    cs.append(case("S/CH140", "Chapter Hunt", 140, S, "blaze", ["bottle_of_emotion", "reindeer_spear", "soul_contract", "book_of_ancient"],
                   stats=["skill_cooldown_decrease", "buff_duration_increase_pct", "companion_summon_time_increase_pct", "attack_speed", "crit_rate",
                          "normal_damage", "skill_lvl_all", "int_pct", "basic_attack_target_increase", "status_effect_damage", "def_pen"]))
    # Summoning Time Increase 12.9: the summon-time candidate flips (pinned blocks must keep the main sheet's choice)
    cs.append(case("S/WB140/inc12.9", "World Boss", 140, S, "blaze", ["hexagon_necklace", "bottle_of_emotion"],
                   over=dict(companion_summon_time_increase_pct=12.9),
                   stats=["buff_duration_increase_pct", "status_effect_damage", "attack_pct", "skill_cooldown_decrease", "companion_summon_time_increase_pct"],
                   toggles=["horn_flute", "hexagon_necklace", "charm_of_the_undead"]))
    cs.append(case("S/BT140/inc12.9", "Breakthrough", 140, S, "blaze", ["hexagon_necklace", "bottle_of_emotion"],
                   over=dict(companion_summon_time_increase_pct=12.9),
                   stats=["buff_duration_increase_pct", "status_effect_damage", "attack_pct", "skill_cooldown_decrease", "companion_summon_time_increase_pct"],
                   toggles=["horn_flute", "hexagon_necklace", "arwens_glass_shoes"]))
    # ------------------------------------------------------------------------------------------------------------------ equip toggles
    for i in range(4):
        cs.append(case(f"T/WB200/{'abcd'[i]}", "World Boss", 200, S, "blaze", [], toggles=ALL_ARTIFACTS[i * 9:(i + 1) * 9],
                       potential={}))
    # removal direction for the baked-in artifacts (BoA / Athena / Bottle / Reindeer) + additions with 4 slots full
    cs.append(case("T/WB200/equipped", "World Boss", 200, S, "blaze", ["book_of_ancient", "athena_gloves", "bottle_of_emotion", "reindeer_spear"],
                   toggles=["book_of_ancient", "athena_gloves", "bottle_of_emotion", "reindeer_spear", "cursed_doll", "star_rock", "shamaness_marble",
                            "hexagon_necklace", "ring_of_cycles", "soul_contract", "lit_lamp"],
                   potential={"hexagon_necklace": 2.5e12, "bottle_of_emotion": 1.0e12, "lunar_dew": 3.0e11, "pigs_ribbon": 5.0e11}))
    cs.append(case("T/ED140", "Enhancement Dungeon", 140, S, "blaze", ["clear_spring_water", "secret_map", "star_rock", "lit_lamp"],
                   toggles=["clear_spring_water", "secret_map", "star_rock", "lit_lamp", "arwens_glass_shoes", "hexagon_necklace", "charm_of_the_undead",
                            "candle", "horn_flute", "soul_pouch", "chalice"]))
    cs.append(case("T/PvP140", "PvP", 140, S, "blaze", ["soul_pouch", "reindeer_spear", "candle"],
                   toggles=["soul_pouch", "reindeer_spear", "candle", "rainbow_snail_shell", "hexagon_necklace", "charm_of_the_undead", "secret_map",
                            "contract_of_darkness", "ring_of_cycles", "horn_flute", "old_music_box"]))
    cs.append(case("T/BT140", "Breakthrough", 140, S, "blaze", ["chalice", "fire_flower"],
                   toggles=["chalice", "fire_flower", "hexagon_necklace", "charm_of_the_undead", "candle", "sayrams_necklace", "horn_flute",
                            "arwens_glass_shoes", "secret_map", "reindeer_spear", "contract_of_darkness", "peach_tree"]))
    cs.append(case("T/CH140", "Chapter Hunt", 140, S, "blaze", ["soul_contract", "horn_flute"],
                   toggles=["soul_contract", "horn_flute", "chalice", "peach_tree", "silver_pendant", "flaming_lava", "old_music_box", "arwens_glass_shoes",
                            "hexagon_necklace", "fire_flower", "secret_map", "ring_of_cycles"]))
    cs.append(case("T/CB140", "Chapter Boss", 140, S, "blaze", ["horn_flute", "old_music_box"],
                   toggles=["horn_flute", "old_music_box", "reindeer_spear", "candle", "hexagon_necklace", "charm_of_the_undead", "star_rock",
                            "shamaness_marble", "cursed_doll", "book_of_ancient", "athena_gloves", "bottle_of_emotion"]))
    # Enhancement Dungeon (KO strip on): every stat that changes what the timeline strip consumes (skill levels -> buff values, skill / basic attack / boss damage ->
    # relative cast weights, crit rate -> Ring of Cycles) and the artifacts that move the same buckets, both directions (ring / candle / star rock equipped)
    cs.append(case("S/ED140", "Enhancement Dungeon", 140, S, "blaze", ["ring_of_cycles", "candle", "star_rock"],
                   stats=["skill_lvl_1st", "skill_lvl_2nd", "skill_lvl_3rd", "skill_lvl_4th", "skill_lvl_all", "skill_damage", "basic_attack_damage",
                          "boss_damage", "crit_rate"],
                   toggles=["ring_of_cycles", "candle", "star_rock", "sayrams_necklace", "book_of_ancient", "rainbow_snail_shell"]))
    # Ring of Cycles' Basic Attack Damage bonus follows the crit rate: Crit Rate / Skill Damage / Basic Attack Damage change the relative cast weights
    cs.append(case("S/WB200/ring", "World Boss", 200, S, "blaze", ["ring_of_cycles", "bottle_of_emotion"],
                   stats=["crit_rate", "skill_damage", "basic_attack_damage"]))
    # ------------------------------------------------------------------------------------------------------------------ baked-in Final Damage artifacts, both directions
    # The same real state reached from two sides: state k has the artifacts 1..k equipped and their Final Damage typed into Inputs!final_damage
    # (multiplied with the user's own 12%).  Artifact k's toggle row read in state k-1 (adding) and in state k (removing) must report the same gain and % gain,
    # and the gain must equal Summary Total(state k) - Total(state k-1).  Attack Speed 100 so Bottle of Emotion's Attack-Speed-dependent Final Damage is non-zero.
    # Attack Speed 100 with Bottle of Emotion (Attack-Speed-dependent Final Damage, non-zero) and Flaming Lava (live Final Damage: bucket a > 1): the Attack Speed row
    # and the baked-in Final Damage toggles must combine multiplicatively with it
    cs.append(case("S/WB200/as100", "World Boss", 200, S, "blaze", ["bottle_of_emotion", "flaming_lava", "cursed_doll"], over=dict(attack_speed=100),
                   stats=["attack_speed", "final_damage", "boss_damage"], toggles=["bottle_of_emotion", "cursed_doll", "lit_lamp"]))

    def fd_typed(base, *xs):
        m = 1 + base / 100
        for x in xs:
            m *= 1 + x / 100
        return (m - 1) * 100
    bottle_x = min(20.0, max(0.0, (1 / 3) * (100 - 60)))        # star 5: +1% per 3% AS over 60, cap 20
    inv = dict(attack_speed=100)
    chain = [("cursed_doll", 14.0), ("lit_lamp", 40.0), ("bottle_of_emotion", bottle_x)]
    for k in range(len(chain) + 1):
        cs.append(case(f"I/WB200/{k}", "World Boss", 200, S, "blaze", [a for a, _x in chain[:k]],
                       over=dict(inv, final_damage=fd_typed(12.0, *[x for _a, x in chain[:k]])), toggles=[a for a, _x in chain]))
    for k in (0, 1):
        cs.append(case(f"I/ED140/{k}", "Enhancement Dungeon", 140, S, "blaze", ["clear_spring_water"] * k,
                       over=dict(inv, final_damage=fd_typed(12.0, *([20.0] * k))), toggles=["clear_spring_water"]))
        cs.append(case(f"I/PvP140/{k}", "PvP", 140, S, "blaze", ["soul_pouch"] * k,
                       over=dict(inv, final_damage=fd_typed(12.0, *([32.0] * k))), toggles=["soul_pouch"]))
    # ------------------------------------------------------------------------------------------------------------------ CDR milestones, companion tables
    cs.append(case("D/WB200", "World Boss", 200, S, "blaze", BB, cdr=True))
    cs.append(case("D/BT140", "Breakthrough", 140, S, "blaze", ["hexagon_necklace"], cdr=True))
    levels = {n: (10, 7, 5, 1, 0)[i % 5] for i, n in enumerate(COMPANION_NAMES)}
    cs.append(case("C/BT140", "Breakthrough", 140, S, "blaze", ["hexagon_necklace", "bottle_of_emotion"], tables=True, companion_levels=levels))
    cs.append(case("C/WB200", "World Boss", 200, S, "blaze", BB, tables=True, companion_levels={n: 10 for n in COMPANION_NAMES}))
    cs.append(case("C/CH140", "Chapter Hunt", 140, S, "blaze", ["bottle_of_emotion"], tables=True, companion_levels=levels))
    cs.append(case("C/BT140/none", "Breakthrough", 140, S, "none", [], tables=True, companion_levels={n: 8 for n in COMPANION_NAMES}))
    return cs


if __name__ == "__main__":
    cs = sens_cases()
    ids = [c["id"] for c in cs]
    assert len(ids) == len(set(ids))
    stats = {s for c in cs for s in c["stats"]}
    tog = {a for c in cs for a in c["toggles"]}
    print(len(cs), "cases;", len(stats), "stats;", len(tog), "toggles;", sum(len(c["stats"]) + len(c["toggles"]) + (10 if c["cdr"] else 0) for c in cs), "blocks")
