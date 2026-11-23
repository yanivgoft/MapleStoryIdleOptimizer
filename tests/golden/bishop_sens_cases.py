"""Case matrix of the Bishop Sensitivity golden file (plain data: no workbook, no engine import; same structure and rules as ``sens_cases.py`` / ``dark_knight_sens_cases.py``).

``sens_cases()`` returns ``[case, ...]``, one case = ONE evaluation of the (Sensitivity-slimmed) Bishop workbook:

    id         unique name
    inputs     engine input dict (``bishop.compute`` shape) + ``artifact_stars`` {id: star | None} for ALL 36 artifacts + ``companion_levels`` {name: level}
    stats      stat keys whose block / table row are read from the workbook
    toggles    artifact ids whose "(Equip)" block / staging row are read
    cdr        True: the 10 CDR milestone blocks; a list: only those CDR values (<= 5 per evaluation, memory)
    tables     True: the Companion Comparison table (+ the Summoning-Time table); needs the full Companion sheet (heavier)
    potential  {artifact id: DPS} constants written over ArtifactsInput!L (potential-line gain) - exercises the potential term of the equip rows

11 evaluations, every case lists only what is compared (<= 8 blocks); the rest of the Sensitivity sheet is deleted from the scratch copy.  Bishop shape: Lv140 (every passive
and buff of the kit unlocked: Bahamut, Blood of the Divine, Arcane Aim, the 6th Big Bang hit, Angel Ray's boss proc; Lv200 would cap the 4th-job skill level at 300), Angel Ray's
own stun always on (so a "companion" result exists even with no companion chosen: the Enhancement Dungeon case picks none), Blaze Wizard Lv10 as the companion elsewhere (a stun),
stat set S non-zero everywhere (Defense and Defense % - Invincible's INT share -, LUK, the five skill-level bonuses, a Cooldown Decrease, Buff Duration).  One Lv118 case
(``S/CH118``: Arcane Aim 120 / Blood of the Divine 125 / Angel Ray's boss proc 122 / the Lv134 Attack Speed locked, Soul Contract in Chapter Hunt) exercises the passive gating.
Every one of the 29 stats is read once (the strip-rebuild stats in World Boss AND Enhancement Dungeon, Defense / Defense % in World Boss, Enhancement Dungeon, Breakthrough
and PvP), 22 artifact toggles (the baked-in ones in both directions: ``T/WB140/a`` = the unequipped state and ``T/WB140/eq`` = the same state with the Cursed Doll equipped and
its Final Damage typed in; Book / Athena / Bottle / Ring / Reindeer / Hexagon / Horn Flute / Soul Pouch / Soul Contract by removal, the others by adding).
"""
from bishop_cases import make_inputs
from sens_cases import COMPANION_NAMES, case_builder, fd_typed

STATS_S = dict(
    flat_attack=250000, attack_pct=1800, defense=12000, defense_pct=15, crit_rate=60, crit_damage=150, attack_speed=20, flat_int=5000, int_pct=40, luk=800,
    damage=30, damage_amp=20, basic_attack_damage=15, skill_damage=20, def_pen=35, boss_damage=40, normal_damage=25, status_effect_damage=30,
    min_damage=80, max_damage=130, final_damage=12, skill_lvl_1st=3, skill_lvl_2nd=5, skill_lvl_3rd=10, skill_lvl_4th=15, skill_lvl_all=20,
    skill_cooldown_decrease=1, basic_attack_target_increase=2, buff_duration_increase_pct=15, companion_summon_time_increase_pct=0,
    boss_normal_weight_choice="A Little More Normal", max_enemies_hit=999, pvp_fight_length=15,
)

ALL_STATS = ["flat_int", "int_pct", "defense", "defense_pct", "damage", "damage_amp", "boss_damage", "normal_damage", "status_effect_damage", "final_damage",
             "min_damage", "max_damage", "crit_rate", "crit_damage", "attack_speed", "def_pen", "basic_attack_damage", "skill_damage", "skill_lvl_1st",
             "skill_lvl_2nd", "skill_lvl_3rd", "skill_lvl_4th", "skill_lvl_all", "flat_attack", "attack_pct", "skill_cooldown_decrease",
             "basic_attack_target_increase", "buff_duration_increase_pct", "companion_summon_time_increase_pct"]
assert len(ALL_STATS) == 29


case = case_builder(make_inputs)


CURSED_DOLL_FD = 14.0        # star 5 (checked against the artifact table by test_bishop_sensitivity.test_cursed_doll_value)


def sens_cases():
    cs = []
    S = STATS_S
    BB = ["bottle_of_emotion", "reindeer_spear"]
    ART4 = ["book_of_ancient", "athena_gloves", "bottle_of_emotion", "ring_of_cycles"]
    LIVE3 = ["reindeer_spear", "hexagon_necklace", "horn_flute"]
    # ------------------------------------------------------------------------------------------------------------------ every stat, World Boss (timeline strip on)
    # Flat INT / INT % (flat-Attack channel + STAT_DAMAGE), Defense / Defense % (Invincible's INT share), Damage % (the joint Damage% bucket) ...
    cs.append(case("S/WB140/a", "World Boss", 140, S, "blaze", BB,
                   stats=["flat_int", "int_pct", "defense", "defense_pct", "damage", "damage_amp", "boss_damage", "status_effect_damage"]))
    # Book of Ancient / Athena's Gloves / Ring of Cycles / Bottle equipped (Attack Speed 100: Bottle's Final Damage is non-zero): the dependent terms follow Crit Rate /
    # Attack Speed; removal direction of the four toggles
    cs.append(case("S/WB140/b", "World Boss", 140, S, "blaze", ART4, over=dict(attack_speed=100),
                   stats=["crit_rate", "crit_damage", "attack_speed", "final_damage"], toggles=ART4))
    cs.append(case("S/WB140/c", "World Boss", 140, S, "blaze", BB,
                   stats=["min_damage", "max_damage", "basic_attack_damage", "skill_damage", "flat_attack", "attack_pct", "buff_duration_increase_pct",
                          "companion_summon_time_increase_pct"]))
    # skill levels (the passive deltas, Ring / Book dependent) + Cooldown Decrease, Glass Shoes / Hexagon / Horn Flute (the three companion-searching toggles)
    cs.append(case("S/WB140/d", "World Boss", 140, S, "blaze", ART4,
                   stats=["skill_lvl_2nd", "skill_lvl_3rd", "skill_lvl_4th", "skill_lvl_all", "skill_cooldown_decrease"],
                   toggles=["arwens_glass_shoes", "hexagon_necklace", "horn_flute"]))
    # ------------------------------------------------------------------------------------------------------------------ equip toggles
    # state 0: Cursed Doll NOT equipped, its Final Damage not typed; state 1 (T/WB140/eq): equipped and typed (multiplied into Inputs!final_damage)
    cs.append(case("T/WB140/a", "World Boss", 140, S, "blaze", LIVE3,
                   toggles=["charm_of_the_undead", "candle", "cursed_doll", "lit_lamp", "star_rock", "athena_gloves", "peach_tree", "silver_pendant"]))
    cs.append(case("T/WB140/eq", "World Boss", 140, S, "blaze", ["cursed_doll"] + LIVE3, over=dict(final_damage=fd_typed(12.0, CURSED_DOLL_FD)),
                   toggles=["cursed_doll", "reindeer_spear", "hexagon_necklace", "horn_flute", "shamaness_marble", "sayrams_necklace", "contract_of_darkness",
                            "rainbow_snail_shell"],
                   potential={"hexagon_necklace": 2.5e9, "cursed_doll": 1.0e9, "lunar_dew": 3.0e8, "pigs_ribbon": 5.0e8}))
    # ------------------------------------------------------------------------------------------------------------------ Enhancement Dungeon (KO strip, Angel Ray only: no companion chosen), Breakthrough
    cs.append(case("S/ED140", "Enhancement Dungeon", 140, S, "none", ["ring_of_cycles", "clear_spring_water", "star_rock"],
                   stats=["skill_lvl_1st", "skill_lvl_2nd", "skill_lvl_4th", "skill_lvl_all", "boss_damage", "defense", "def_pen"],
                   toggles=["clear_spring_water"]))
    # Lv118: Arcane Aim (120), Blood of the Divine (125), Angel Ray's boss proc (122) and the Lv134 Attack Speed are locked; Soul Contract is a Chapter Hunt effect
    # (Triumph Feather's cooldown)
    cs.append(case("S/CH118", "Chapter Hunt", 118, S, "blaze", ["bottle_of_emotion", "soul_contract", "book_of_ancient"],
                   stats=["normal_damage", "basic_attack_target_increase", "int_pct", "skill_cooldown_decrease", "buff_duration_increase_pct", "skill_lvl_3rd",
                          "skill_lvl_all"],
                   toggles=["soul_contract"]))
    # PvP: the opponent's Defense is the main sheet's total Defense (Defense x (1 + (Defense % + Divine Protection)/100)) in every block (a Defense / Defense % sweep
    # must not move it); Reindeer's Spear by adding, Soul Pouch (Final Damage in PvP) by removal
    cs.append(case("S/PvP140", "PvP", 140, S, "blaze", ["soul_pouch", "bottle_of_emotion"],
                   stats=["defense", "defense_pct", "flat_int", "def_pen", "skill_lvl_all"], toggles=["reindeer_spear", "soul_pouch", "candle"]))
    # ------------------------------------------------------------------------------------------------------------------ CDR milestones, companion tables
    cs.append(case("D/WB140", "World Boss", 140, S, "blaze", BB, cdr=[0.5, 1.0, 2.0, 3.5, 5.0]))
    # Summoning Time Increase 12.9: the summon-time candidate flips (pinned blocks must keep the main sheet's choice); both comparison tables
    levels = {n: (10, 7, 5, 1, 0)[i % 5] for i, n in enumerate(COMPANION_NAMES)}
    cs.append(case("C/BT140", "Breakthrough", 140, S, "blaze", ["hexagon_necklace", "bottle_of_emotion"], over=dict(companion_summon_time_increase_pct=12.9),
                   stats=["skill_cooldown_decrease", "companion_summon_time_increase_pct", "defense", "normal_damage"],
                   toggles=["horn_flute", "arwens_glass_shoes"], tables=True, companion_levels=levels))
    return cs


if __name__ == "__main__":
    cs = sens_cases()
    ids = [c["id"] for c in cs]
    assert len(ids) == len(set(ids))
    stats = {s for c in cs for s in c["stats"]}
    tog = {a for c in cs for a in c["toggles"]}
    n = lambda c: len(c["stats"]) + len(c["toggles"]) + (len(c["cdr"]) if isinstance(c["cdr"], list) else (10 if c["cdr"] else 0))  # noqa: E731
    print(len(cs), "cases;", len(stats), "stats;", len(tog), "toggles;", sum(n(c) for c in cs), "blocks; max per case", max(n(c) for c in cs))
    missing = set(ALL_STATS) - stats
    print("stats not covered:", sorted(missing))
