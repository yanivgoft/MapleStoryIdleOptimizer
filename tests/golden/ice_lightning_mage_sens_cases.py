"""Case matrix of the Ice/Lightning Mage Sensitivity golden file (plain data: no workbook, no engine import; same structure and rules as ``dark_knight_sens_cases.py``).

``sens_cases()`` returns ``[case, ...]``, one case = ONE evaluation of the (Sensitivity-slimmed) Ice/Lightning Mage workbook:

    id         unique name
    inputs     engine input dict (``ice_lightning_mage.compute`` shape) + ``artifact_stars`` {id: star | None} for ALL 36 artifacts + ``companion_levels`` {name: level}
    stats      stat keys whose block / table row are read from the workbook
    toggles    artifact ids whose "(Equip)" block / staging row are read
    cdr        True: the 10 CDR milestone blocks; a list: only those CDR values (<= 5 per evaluation, memory)
    tables     True: the Companion Comparison table (+ the Summoning-Time table); needs the full Companion sheet (heavier)
    potential  {artifact id: DPS} constants written over ArtifactsInput!L (potential-line gain) - exercises the potential term of the equip rows

12 evaluations, <= 8 blocks each (the rest of the Sensitivity sheet is deleted from the scratch copy).  Ice/Lightning Mage shape: Lv140 (every passive / buff of the kit
is unlocked, Elquines' 6 targets from Lv138), Blaze Wizard Lv10 as the companion (a stun) next to the player's own Glacier Wall freeze (always on from Lv63), stat set S has a
non-zero value everywhere (all five skill-level bonuses, a Cooldown Decrease, Status Effect Damage, LUK).  The World Boss cases have the timeline strip on (engine on),
Enhancement Dungeon the KO strip, Breakthrough / Chapter Hunt the strip off (Breakthrough: boss phase + normal phase blend, summon-time candidate flip at +12.9%).
"""
from ice_lightning_mage_cases import make_inputs
from sens_cases import COMPANION_NAMES, case_builder

STATS_S = dict(
    flat_attack=250000, attack_pct=1800, defense=12000, crit_rate=60, crit_damage=150, attack_speed=20, flat_int=5000, int_pct=40, luk=800,
    damage=30, damage_amp=20, basic_attack_damage=15, skill_damage=20, def_pen=35, boss_damage=40, normal_damage=25, status_effect_damage=30,
    min_damage=80, max_damage=130, final_damage=12, skill_lvl_1st=3, skill_lvl_2nd=5, skill_lvl_3rd=10, skill_lvl_4th=15, skill_lvl_all=20,
    skill_cooldown_decrease=1, basic_attack_target_increase=2, buff_duration_increase_pct=15, companion_summon_time_increase_pct=0,
    boss_normal_weight_choice="A Little More Normal", max_enemies_hit=999, pvp_fight_length=15,
)

ALL_STATS = ["flat_int", "int_pct", "damage", "damage_amp", "boss_damage", "normal_damage", "status_effect_damage", "final_damage", "min_damage", "max_damage",
             "crit_rate", "crit_damage", "attack_speed", "def_pen", "basic_attack_damage", "skill_damage", "skill_lvl_1st", "skill_lvl_2nd", "skill_lvl_3rd",
             "skill_lvl_4th", "skill_lvl_all", "flat_attack", "attack_pct", "skill_cooldown_decrease", "basic_attack_target_increase", "buff_duration_increase_pct",
             "companion_summon_time_increase_pct"]
assert len(ALL_STATS) == 27


case = case_builder(make_inputs)


def sens_cases():
    cs = []
    S = STATS_S
    # ------------------------------------------------------------------------------------------------------------------ every stat, World Boss (timeline strip on)
    # (Bottle of Emotion + Reindeer's Spear equipped: their Attack% / Def Pen sit in the live buckets of every block)
    BB = ["bottle_of_emotion", "reindeer_spear"]
    cs.append(case("S/WB140/a", "World Boss", 140, S, "blaze", BB, stats=ALL_STATS[0:8]))
    cs.append(case("S/WB140/b", "World Boss", 140, S, "blaze", BB, stats=ALL_STATS[8:16]))
    cs.append(case("S/WB140/c", "World Boss", 140, S, "blaze", BB, stats=ALL_STATS[16:24]))
    # the last three stats + five Cooldown Decrease milestones (a 5-value subset: the step is the difference to the previous kept milestone only when consecutive)
    cs.append(case("S/WB140/d", "World Boss", 140, S, "blaze", BB, stats=ALL_STATS[24:27], cdr=[0.5, 1.0, 2.5, 3.0, 5.0]))
    # ------------------------------------------------------------------------------------------------------------------ baked-in Final Damage artifacts, both directions + the equip toggles
    # State k has artifacts 1..k equipped and their Final Damage typed (multiplied) into Inputs!final_damage; artifact k's toggle row read in state k-1 (adding) and in state k
    # (removing) must give the same gain and % gain, equal to Summary Total(k) - Total(k-1).  Attack Speed 100: Bottle's Final Damage is non-zero.

    def fd_typed(base, *xs):
        m = 1 + base / 100
        for x in xs:
            m *= 1 + x / 100
        return (m - 1) * 100
    bottle_x = min(20.0, max(0.0, (1 / 3) * (100 - 60)))        # star 5: +1% per 3% AS over 60, cap 20
    inv = dict(attack_speed=100)
    chain = [("cursed_doll", 14.0), ("bottle_of_emotion", bottle_x)]
    others = [
        ["arwens_glass_shoes", "hexagon_necklace", "horn_flute", "charm_of_the_undead", "candle", "lit_lamp"],                       # unequipped state: adding direction
        ["book_of_ancient", "athena_gloves", "ring_of_cycles", "contract_of_darkness", "star_rock", "peach_tree"],
        ["shamaness_marble", "silver_pendant", "rainbow_snail_shell", "sayrams_necklace", "soul_contract", "secret_map"],
    ]
    for k in range(len(chain) + 1):
        cs.append(case(f"I/WB140/{k}", "World Boss", 140, S, "blaze", [a for a, _x in chain[:k]],
                       over=dict(inv, final_damage=fd_typed(12.0, *[x for _a, x in chain[:k]])), toggles=[a for a, _x in chain] + others[k],
                       # (potential-line gains: Hexagon Necklace is NOT a chain artifact, so the chain rows stay exact; the term is exercised on the live Hexagon row)
                       potential=({"hexagon_necklace": 2.5e12, "candle": 4.0e11} if k == 0 else {})))
    # ------------------------------------------------------------------------------------------------------------------ Enhancement Dungeon (KO strip), REMOVAL direction
    # Ring of Cycles with the total crit rate above 100% (the Magic Critical delta moves the ring's excess), Reindeer's Spear / Shamaness Marble removal (Shamaness: the strip's
    # buff windows), Clear Spring Water adding (Enhancement Dungeon is a growth dungeon: its Final Damage applies)
    cs.append(case("S/ED140", "Enhancement Dungeon", 140, S, "blaze", ["ring_of_cycles", "reindeer_spear", "shamaness_marble", "book_of_ancient"], over=dict(crit_rate=110),
                   stats=["crit_rate", "def_pen", "skill_lvl_all", "skill_damage"],
                   toggles=["ring_of_cycles", "reindeer_spear", "shamaness_marble", "clear_spring_water"]))
    # ------------------------------------------------------------------------------------------------------------------ Breakthrough (strip off), Chapter Hunt (steady state)
    levels = {n: (10, 7, 5, 1, 0)[i % 5] for i, n in enumerate(COMPANION_NAMES)}
    cs.append(case("S/BT140/a", "Breakthrough", 140, S, "blaze", BB,
                   stats=["flat_int", "boss_damage", "normal_damage", "status_effect_damage", "crit_rate", "attack_speed"], tables=True, companion_levels=levels))
    # Summoning Time Increase 12.9: the summon-time candidate flips (pinned blocks must keep the main sheet's choice)
    cs.append(case("S/BT140/b", "Breakthrough", 140, S, "blaze", ["hexagon_necklace", "bottle_of_emotion"], over=dict(companion_summon_time_increase_pct=12.9),
                   stats=["skill_cooldown_decrease", "buff_duration_increase_pct", "companion_summon_time_increase_pct", "def_pen"],
                   toggles=["horn_flute", "hexagon_necklace", "arwens_glass_shoes", "shamaness_marble"]))
    cs.append(case("S/CH140", "Chapter Hunt", 140, S, "blaze", ["bottle_of_emotion", "soul_contract", "book_of_ancient"],
                   stats=["skill_cooldown_decrease", "buff_duration_increase_pct", "attack_speed", "crit_rate", "normal_damage", "skill_lvl_all", "int_pct",
                          "basic_attack_target_increase"]))
    # ------------------------------------------------------------------------------------------------------------------ companion tables (World Boss: no boss phase)
    cs.append(case("C/WB140", "World Boss", 140, S, "blaze", BB, stats=["flat_int", "status_effect_damage"], tables=True, companion_levels={n: 10 for n in COMPANION_NAMES}))
    return cs


if __name__ == "__main__":
    cs = sens_cases()
    ids = [c["id"] for c in cs]
    assert len(ids) == len(set(ids))
    stats = {s for c in cs for s in c["stats"]}
    tog = {a for c in cs for a in c["toggles"]}
    n = lambda c: len(c["stats"]) + len(c["toggles"]) + (len(c["cdr"]) if isinstance(c["cdr"], list) else (10 if c["cdr"] else 0))  # noqa: E731
    print(len(cs), "cases;", len(stats), "stats;", len(tog), "toggles;", sum(n(c) for c in cs), "blocks; max per case", max(n(c) for c in cs))
    assert set(ALL_STATS) <= stats
