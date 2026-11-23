"""Case matrix of the Dark Knight Sensitivity golden file (plain data: no workbook, no engine import; same structure and rules as ``sens_cases.py``).

``sens_cases()`` returns ``[case, ...]``, one case = ONE evaluation of the (Sensitivity-slimmed) Dark Knight workbook:

    id         unique name
    inputs     engine input dict (``dark_knight.compute`` shape) + ``artifact_stars`` {id: star | None} for ALL 36 artifacts + ``companion_levels`` {name: level}
    stats      stat keys whose block / table row are read from the workbook
    toggles    artifact ids whose "(Equip)" block / staging row are read
    cdr        True: the 10 CDR milestone blocks; a list: only those CDR values (<= 5 per evaluation, memory)
    tables     True: the Companion Comparison table (+ the Summoning-Time table); needs the full Companion sheet (heavier)
    potential  {artifact id: DPS} constants written over ArtifactsInput!L (potential-line gain) - exercises the potential term of the equip rows

Every case lists only what is compared (<= 8 blocks); the rest of the Sensitivity sheet is deleted from the scratch copy.  Dark Knight shape: Lv140 (every
passive / buff of the kit is unlocked; Lv200 would cap the 4th-job skill level at 300), the player's own stuns (Rush + Evil Eye Shock) are always on, Blaze Wizard
Lv10 as the companion (a stun), stat set S has a non-zero value everywhere (Defense and Defense %, DEX, the five skill-level bonuses, a Cooldown Decrease).
"""
from dark_knight_cases import make_inputs
from sens_cases import COMPANION_NAMES, case_builder

STATS_S = dict(
    flat_attack=250000, attack_pct=1800, defense=12000, defense_pct=15, crit_rate=60, crit_damage=150, attack_speed=20, flat_str=5000, str_pct=40, dex=800,
    damage=30, damage_amp=20, basic_attack_damage=15, skill_damage=20, def_pen=35, boss_damage=40, normal_damage=25, status_effect_damage=30,
    min_damage=80, max_damage=130, final_damage=12, skill_lvl_1st=3, skill_lvl_2nd=5, skill_lvl_3rd=10, skill_lvl_4th=15, skill_lvl_all=20,
    skill_cooldown_decrease=1, basic_attack_target_increase=2, buff_duration_increase_pct=15, companion_summon_time_increase_pct=0,
    boss_normal_weight_choice="A Little More Normal", max_enemies_hit=999, pvp_fight_length=15,
)

ALL_STATS = ["flat_str", "str_pct", "dex", "defense", "defense_pct", "damage", "damage_amp", "boss_damage", "normal_damage", "status_effect_damage",
             "final_damage", "min_damage", "max_damage", "crit_rate", "crit_damage", "attack_speed", "def_pen", "basic_attack_damage", "skill_damage",
             "skill_lvl_1st", "skill_lvl_2nd", "skill_lvl_3rd", "skill_lvl_4th", "skill_lvl_all", "flat_attack", "attack_pct", "skill_cooldown_decrease",
             "basic_attack_target_increase", "buff_duration_increase_pct", "companion_summon_time_increase_pct"]
assert len(ALL_STATS) == 30


case = case_builder(make_inputs)


# the baked-in artifact values at the stars of ``sens_cases.STARS`` (same artifact tables as Buccaneer's chain; checked by test_dark_knight_sensitivity.test_baked_values)
SHAMANESS_BDI = 12.0            # star 5
ATHENA_AS, ATHENA_MAX_PCT = 14.4, 45.0      # star 4: direct Attack Speed, Max Damage = 45% of the total Attack Speed
REINDEER_DEF_PEN = 8.0          # star 3
J_AS = 100.0                    # the typed Attack Speed of the chain states


def j_chain_over(sham=False, athena=False, reindeer=False):
    """Inputs overrides of a chain state: the baked-in stats of the equipped chain artifacts typed in (base: Buff Duration 15, Max Damage 130, Def Pen 35)."""
    as_total = J_AS + (ATHENA_AS if athena else 0.0)
    return dict(attack_speed=as_total, buff_duration_increase_pct=15.0 + (SHAMANESS_BDI if sham else 0.0),
                max_damage=130.0 + (ATHENA_MAX_PCT / 100 * as_total if athena else 0.0),
                def_pen=100 * (1 - (1 - 35.0 / 100) * (1 - REINDEER_DEF_PEN / 100)) if reindeer else 35.0)


J_CHAIN = [
    ("0", [], {}),
    ("1", ["shamaness_marble"], dict(sham=True)),
    ("2", ["shamaness_marble", "athena_gloves"], dict(sham=True, athena=True)),
    ("3", ["shamaness_marble", "athena_gloves", "reindeer_spear"], dict(sham=True, athena=True, reindeer=True)),
]
# (artifact, state adding it, state removing it)
J_PAIRS = [("shamaness_marble", "0", "1"), ("athena_gloves", "1", "2"), ("reindeer_spear", "2", "3")]


def sens_cases():
    cs = []
    S = STATS_S
    BB = ["bottle_of_emotion", "reindeer_spear"]
    # ------------------------------------------------------------------------------------------------------------------ every stat, World Boss (timeline strip on)
    cs.append(case("S/WB140/a", "World Boss", 140, S, "blaze", BB, stats=ALL_STATS[0:8]))
    cs.append(case("S/WB140/b", "World Boss", 140, S, "blaze", BB, stats=ALL_STATS[8:16]))
    cs.append(case("S/WB140/c", "World Boss", 140, S, "blaze", BB, stats=ALL_STATS[16:24]))
    cs.append(case("S/WB140/d", "World Boss", 140, S, "blaze", BB, stats=ALL_STATS[24:30], toggles=["hexagon_necklace", "horn_flute"]))
    # Book of Ancient / Athena's Gloves / Ring of Cycles / Bottle equipped: their dependent terms follow Crit Rate / Attack Speed / the skill levels; removal direction
    cs.append(case("S/WB140/art", "World Boss", 140, S, "blaze", ["book_of_ancient", "athena_gloves", "bottle_of_emotion", "ring_of_cycles"],
                   stats=["crit_rate", "attack_speed", "skill_lvl_all", "crit_damage"],
                   toggles=["book_of_ancient", "athena_gloves", "bottle_of_emotion", "ring_of_cycles"]))
    # ------------------------------------------------------------------------------------------------------------------ equip toggles
    cs.append(case("T/WB140/a", "World Boss", 140, S, "blaze", [],
                   toggles=["arwens_glass_shoes", "hexagon_necklace", "horn_flute", "charm_of_the_undead", "candle", "cursed_doll", "lit_lamp", "star_rock"]))
    cs.append(case("T/WB140/b", "World Boss", 140, S, "blaze", [],
                   toggles=["book_of_ancient", "athena_gloves", "ring_of_cycles", "contract_of_darkness", "peach_tree", "silver_pendant", "shamaness_marble",
                            "rainbow_snail_shell"]))
    cs.append(case("T/WB140/eq", "World Boss", 140, S, "blaze", ["cursed_doll", "reindeer_spear", "hexagon_necklace", "horn_flute"],
                   toggles=["cursed_doll", "reindeer_spear", "hexagon_necklace", "horn_flute", "soul_contract", "sayrams_necklace", "arwens_glass_shoes",
                            "secret_map"],
                   potential={"hexagon_necklace": 2.5e12, "cursed_doll": 1.0e12, "lunar_dew": 3.0e11, "pigs_ribbon": 5.0e11}))
    # ------------------------------------------------------------------------------------------------------------------ Enhancement Dungeon (KO strip), Breakthrough, Chapter Hunt, PvP
    cs.append(case("S/ED140", "Enhancement Dungeon", 140, S, "blaze", ["ring_of_cycles", "clear_spring_water", "star_rock"],
                   stats=["skill_lvl_1st", "skill_lvl_2nd", "skill_lvl_4th", "skill_lvl_all", "skill_damage", "boss_damage", "crit_rate"],
                   toggles=["clear_spring_water"]))
    cs.append(case("S/BT140/a", "Breakthrough", 140, S, "blaze", BB,
                   stats=["flat_str", "defense", "boss_damage", "normal_damage", "status_effect_damage", "crit_rate", "attack_speed", "skill_lvl_all"]))
    # Summoning Time Increase 12.9: the summon-time candidate flips (pinned blocks must keep the main sheet's choice)
    cs.append(case("S/BT140/b", "Breakthrough", 140, S, "blaze", ["hexagon_necklace", "bottle_of_emotion"], over=dict(companion_summon_time_increase_pct=12.9),
                   stats=["skill_cooldown_decrease", "buff_duration_increase_pct", "companion_summon_time_increase_pct", "final_damage", "def_pen"],
                   toggles=["horn_flute", "hexagon_necklace", "arwens_glass_shoes"]))
    cs.append(case("S/CH140", "Chapter Hunt", 140, S, "blaze", ["bottle_of_emotion", "soul_contract", "book_of_ancient"],
                   stats=["skill_cooldown_decrease", "buff_duration_increase_pct", "attack_speed", "crit_rate", "normal_damage", "skill_lvl_all", "str_pct",
                          "basic_attack_target_increase"],
                   toggles=[]))
    # PvP: the opponent's Defense is the main sheet's total Defense in every block (a Defense / Defense % sweep must not move it)
    cs.append(case("S/PvP140", "PvP", 140, S, "blaze", ["soul_pouch", "reindeer_spear"],
                   stats=["defense", "defense_pct", "flat_str", "def_pen", "skill_lvl_all"], toggles=["soul_pouch", "reindeer_spear", "candle"]))
    # ------------------------------------------------------------------------------------------------------------------ baked-in Final Damage artifacts, both directions
    # State k has artifacts 1..k equipped and their Final Damage typed (multiplied) into Inputs!final_damage; artifact k's toggle row read in state k-1 (adding)
    # and in state k (removing) must give the same gain and % gain, equal to Summary Total(k) - Total(k-1).  Attack Speed 100: Bottle's Final Damage is non-zero.

    def fd_typed(base, *xs):
        m = 1 + base / 100
        for x in xs:
            m *= 1 + x / 100
        return (m - 1) * 100
    bottle_x = min(20.0, max(0.0, (1 / 3) * (100 - 60)))        # star 5: +1% per 3% AS over 60, cap 20
    inv = dict(attack_speed=100)
    chain = [("cursed_doll", 14.0), ("bottle_of_emotion", bottle_x)]
    for k in range(len(chain) + 1):
        cs.append(case(f"I/WB140/{k}", "World Boss", 140, S, "blaze", [a for a, _x in chain[:k]],
                       over=dict(inv, final_damage=fd_typed(12.0, *[x for _a, x in chain[:k]])), toggles=[a for a, _x in chain]))
    # ------------------------------------------------------------------------------------------------------------------ Shamaness Marble / Athena's Gloves / Reindeer's Spear chain
    # (the three block gaps fixed 2026-11-23: row == true Summary Total delta, both directions).  State k has the first k artifacts equipped with their baked-in stats typed
    # into the Inputs (Buff Duration +12; Attack Speed +14.4 AND Max Damage +45% of the total Attack Speed; Def Pen combined by diminishing returns with the spear's 8);
    # the toggle row of artifact k is read in state k-1 (adding) and in state k (removing).  Reindeer's Attack% is a LIVE effect (not typed).
    for suffix, equipped, flags in J_CHAIN:
        cs.append(case(f"J/WB140/{suffix}", "World Boss", 140, S, "blaze", equipped, over=dict(j_chain_over(**flags)),
                       toggles=[a for a, add, rem in J_PAIRS if suffix in (add, rem)]))
    # ------------------------------------------------------------------------------------------------------------------ CDR milestones, companion tables
    cs.append(case("D/WB140/a", "World Boss", 140, S, "blaze", BB, cdr=[0.5, 1.0, 1.5, 2.0, 2.5]))
    cs.append(case("D/WB140/b", "World Boss", 140, S, "blaze", BB, cdr=[3.0, 3.5, 4.0, 4.5, 5.0]))
    levels = {n: (10, 7, 5, 1, 0)[i % 5] for i, n in enumerate(COMPANION_NAMES)}
    cs.append(case("C/BT140", "Breakthrough", 140, S, "blaze", ["hexagon_necklace", "bottle_of_emotion"], tables=True, companion_levels=levels))
    cs.append(case("C/WB140", "World Boss", 140, S, "blaze", BB, tables=True, companion_levels={n: 10 for n in COMPANION_NAMES}))
    return cs


if __name__ == "__main__":
    cs = sens_cases()
    ids = [c["id"] for c in cs]
    assert len(ids) == len(set(ids))
    stats = {s for c in cs for s in c["stats"]}
    tog = {a for c in cs for a in c["toggles"]}
    n = lambda c: len(c["stats"]) + len(c["toggles"]) + (len(c["cdr"]) if isinstance(c["cdr"], list) else (10 if c["cdr"] else 0))  # noqa: E731
    print(len(cs), "cases;", len(stats), "stats;", len(tog), "toggles;", sum(n(c) for c in cs), "blocks; max per case", max(n(c) for c in cs))
