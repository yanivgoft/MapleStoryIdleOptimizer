"""The golden input matrix for Night Lord WITH artifacts equipped (plain data: no workbook, no engine import).

``artifact_cases()`` returns ``[(case_id, inputs_dict), ...]``; an inputs dict is the ``tests/golden/night_lord_cases.py`` shape plus
``inputs["artifacts"] = [{"key": <artifact id>, "star": 0..5 | None}, ...]`` (<= 4 equipped slots; ``star`` None = "Not Unlocked").
``TOGGLE_PAIRS`` lists ``(with_case, without_case, label)`` triples whose workbook totals give the equip-toggle delta; ``EQUIV_PAIRS`` the Arwen's
Glass Shoes equivalence pairs (artifact at Inputs x == no artifact at Inputs x + star value).

Same structure as ``artifact_cases.py`` (FP-Mage): every one of the 36 artifacts is equipped at least once at star 5 in World Boss (fixed length,
timeline engine ON) with Blaze Wizard Lv10 (groups G1..G9); further runs cover the other fight shapes (steady state, phased contents, PvP, KO
dungeons, Chapter Boss), star-dependent values (star 0 / 2 / 3 / "Not Unlocked"), Book of Ancient + Ring of Cycles around the 100% crit-rate line,
Reindeer's Spear at def pen 50 / 80 / 99, matched with / without pairs for the toggle deltas, and Night Lord-specific shapes (levels around Gust Charm 35 / Adrenalin 66 / Showdown 100 / Frailty Curse 110, incoming_hit_rate 0 / 2 / 5, no Defense at all, stat set C with skill-level bonuses and Cooldown Decrease / Buff Duration, with Soul Contract / Shamaness Marble).
"""
import artifact_cases_common as C
from artifact_cases_common import BLAZE, EQUIV_PAIRS, arts  # noqa: F401
from night_lord_cases import STATS_A, make_inputs

# Stat set C: a mid-game character WITH skill-level bonuses (they move every skill's FactorTable lookup and the buffs' Attack% / Final Damage) and a Cooldown
# Decrease; incoming_hit_rate 2 (Shadow Shifter's counterattack)
STATS_C = dict(
    flat_attack=640000, attack_pct=9000.5, defense=30000, crit_rate=100, crit_damage=250.5, attack_speed=35,
    flat_luk=36000, luk_pct=210, dex=500, damage=500, damage_amp=60, basic_attack_damage=22, skill_damage=75,
    def_pen=35, boss_damage=150, normal_damage=120, status_effect_damage=0, min_damage=180, max_damage=200,
    final_damage=60, skill_lvl_1st=3, skill_lvl_2nd=5, skill_lvl_3rd=30, skill_lvl_4th=45, skill_lvl_all=20,
    skill_cooldown_decrease=1.5, basic_attack_target_increase=3, buff_duration_increase_pct=10,
    companion_summon_time_increase_pct=0, boss_normal_weight_choice="Equal", max_enemies_hit=999, incoming_hit_rate=2, pvp_fight_length=15,
)

TOGGLE_PAIRS = C.toggle_pairs()


def artifact_cases():
    cases, add = C.begin(make_inputs)
    C.common_cases(add, STATS_A)
    # ---- Night Lord-specific shapes: no player stun below Lv35 (KO windows only), Gust Charm alone from Lv35 (the stun probe's s0 / W0 incl. Gust Charm feed the Horn
    #      Flute window), Adrenalin Lv66, Showdown Lv100, Frailty Curse Lv110, Shadow Shifter Lv115 (incoming_hit_rate), no Defense at all ----
    add("NL/BT/C35/horn+hexagon+charm+candle/none", "Breakthrough", 35, STATS_C, "none",
        arts(["horn_flute", "hexagon_necklace", "charm_of_the_undead", "candle"]))
    add("NL/WB/C34/horn+hexagon+charm+candle/blaze", "World Boss", 34, STATS_C, "blaze",
        arts(["horn_flute", "hexagon_necklace", "charm_of_the_undead", "candle"]), **BLAZE)
    add("NL/WB/C35/horn+hexagon+charm+candle/none", "World Boss", 35, STATS_C, "none",
        arts(["horn_flute", "hexagon_necklace", "charm_of_the_undead", "candle"]))
    add("NL/WB/C66/bottle+secret_map+charm+shamaness/none", "World Boss", 66, STATS_C, "none",
        arts(["bottle_of_emotion", "secret_map", "charm_of_the_undead", "shamaness_marble"]))
    add("NL/WB/C99/bottle+secret_map+charm+shamaness/blaze", "World Boss", 99, STATS_C, "blaze",
        arts(["bottle_of_emotion", "secret_map", "charm_of_the_undead", "shamaness_marble"]), **BLAZE)
    add("NL/WB/C100/reindeer+ring+horn+peach/blaze", "World Boss", 100, STATS_C, "blaze",
        arts(["reindeer_spear", "ring_of_cycles", "horn_flute", "peach_tree"]), **BLAZE)
    add("NL/CH/C105/soul+reindeer+ring+horn/blaze", "Chapter Hunt", 105, STATS_C, "blaze",
        arts(["soul_contract", "reindeer_spear", "ring_of_cycles", "horn_flute"]), **BLAZE)
    add("NL/WB/C110/soul+shamaness+bottle+chalice/none", "World Boss", 110, STATS_C, "none",
        arts(["soul_contract", "shamaness_marble", "bottle_of_emotion", "chalice"]))
    add("NL/PvP/C117/soul+shamaness+candle+hexagon/none", "PvP", 117, STATS_C, "none",
        arts(["soul_contract", "shamaness_marble", "candle", "hexagon_necklace"]))
    add("NL/WB/C140/soul+shamaness+old_music_box+charm/blaze", "World Boss", 140, STATS_C, "blaze",
        arts(["soul_contract", "shamaness_marble", "old_music_box", "charm_of_the_undead"]), **BLAZE)
    add("NL/HD/C140/soul+shamaness+secret_map+horn/wind/MoreBoss", "Hero Dungeon", 140, STATS_C, "wind",
        arts(["soul_contract", "shamaness_marble", "secret_map", "horn_flute"]), boss_normal_weight_choice="More Boss",
        companion_summon_time_increase_pct=20)
    add("NL/CH/C140/soul+shamaness+bottle+alliance/none", "Chapter Hunt", 140, STATS_C, "none",
        arts(["soul_contract", "shamaness_marble", "bottle_of_emotion", "alliance_badge"]))
    add("NL/CH/C140/soul+bottle+alliance+hexagon/wind", "Chapter Hunt", 140, STATS_C, "wind",
        arts(["soul_contract", "bottle_of_emotion", "alliance_badge", "hexagon_necklace"]), companion_summon_time_increase_pct=20)
    add("NL/ED/C140/hexagon+charm+candle+horn/blaze", "Enhancement Dungeon", 140, STATS_C, "blaze",
        arts(["hexagon_necklace", "charm_of_the_undead", "candle", "horn_flute"]), **BLAZE)
    add("NL/WB/def0/horn+hexagon+reindeer+ring/blaze", "World Boss", 140, dict(STATS_A, defense=0), "blaze",
        arts(["horn_flute", "hexagon_necklace", "reindeer_spear", "ring_of_cycles"]), **BLAZE)
    add("NL/PvP/def0/candle+reindeer+soul_pouch+horn/blaze", "PvP", 140, dict(STATS_A, defense=0), "blaze",
        arts(["candle", "reindeer_spear", "soul_pouch", "horn_flute"]), **BLAZE)
    add("NL/WB/peach+silver+sayrams+star_rock/blaze", "World Boss", 140, STATS_A, "blaze",
        arts(["peach_tree", "silver_pendant", "sayrams_necklace", "star_rock"]), **BLAZE)
    add("NL/WB/hit0/bottle+candle+reindeer+ring/blaze", "World Boss", 140, dict(STATS_A, incoming_hit_rate=0), "blaze",
        arts(["bottle_of_emotion", "candle", "reindeer_spear", "ring_of_cycles"]), **BLAZE)
    add("NL/WB/hit5/bottle+candle+reindeer+ring/blaze", "World Boss", 140, dict(STATS_A, incoming_hit_rate=5), "blaze",
        arts(["bottle_of_emotion", "candle", "reindeer_spear", "ring_of_cycles"]), **BLAZE)
    add("NL/BT/hit5/bottle+candle+reindeer+ring/wind", "Breakthrough", 140, dict(STATS_A, incoming_hit_rate=5), "wind",
        arts(["bottle_of_emotion", "candle", "reindeer_spear", "ring_of_cycles"]))
    C.arwen_cases(add, STATS_A)
    return cases


if __name__ == "__main__":
    cs = artifact_cases()
    ids = [c for c, _ in cs]
    assert len(ids) == len(set(ids))
    seen = {a["key"] for _, d in cs for a in d["artifacts"]}
    print(len(cs), "cases;", len(seen), "distinct artifacts equipped")
