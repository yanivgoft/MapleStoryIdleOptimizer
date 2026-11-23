"""The golden input matrix for Marksman WITH artifacts equipped (plain data: no workbook, no engine import).

``artifact_cases()`` returns ``[(case_id, inputs_dict), ...]``; an inputs dict is the ``tests/golden/marksman_cases.py`` shape plus
``inputs["artifacts"] = [{"key": <artifact id>, "star": 0..5 | None}, ...]`` (<= 4 equipped slots; ``star`` None = "Not Unlocked").
``TOGGLE_PAIRS`` lists ``(with_case, without_case, label)`` triples whose workbook totals give the equip-toggle delta; ``EQUIV_PAIRS`` the Arwen's
Glass Shoes equivalence pairs (artifact at Inputs x == no artifact at Inputs x + star value).

Same structure as ``paladin_artifact_cases.py``: every one of the 36 artifacts is equipped at least once at star 5 in World Boss (fixed length,
timeline engine ON) with Blaze Wizard Lv10 (groups G1..G9); further runs cover the other fight shapes (steady state, phased contents, PvP, KO
dungeons, Chapter Boss), star-dependent values (star 0 / 2 / 3 / "Not Unlocked"), Book of Ancient + Ring of Cycles around the 100% crit-rate line,
Reindeer's Spear at def pen 50 / 80 / 99, matched with / without pairs for the toggle deltas, and Marksman-specific shapes (the three player stuns -
Covering Fire from Lv49, Bolt Burst from Lv98, Frostprey's periodic freeze (cooldown x0.6 from Lv104) - with no companion and with one; Illusion Step
(Lv117, the engine's only timed buff, which Shamaness Marble / Soul Contract / the Attack% artifacts move) and Sharp Eyes (Lv115)).
"""
import artifact_cases_common as C
from artifact_cases_common import BLAZE, EQUIV_PAIRS, arts  # noqa: F401
from marksman_cases import STATS_A, STATS_B, make_inputs

TOGGLE_PAIRS = C.toggle_pairs()


def artifact_cases():
    cases, add = C.begin(make_inputs)
    C.common_cases(add, STATS_A)
    # ---- Marksman-specific shapes: the three player stuns (Covering Fire Lv49, Bolt Burst Lv98, Frostprey periodic freeze, cooldown x0.6 from Lv104) with /
    # without a companion; Illusion Step (Lv117) and Sharp Eyes (Lv115) around their unlock levels; STATS_B = a weak character without skill-level bonuses ----
    add("MK/BT/L49/horn+hexagon+charm+candle/none", "Breakthrough", 49, STATS_B, "none",
        arts(["horn_flute", "hexagon_necklace", "charm_of_the_undead", "candle"]))
    add("MK/WB/L60/hexagon+charm+candle+bottle/none", "World Boss", 60, STATS_B, "none",
        arts(["hexagon_necklace", "charm_of_the_undead", "candle", "bottle_of_emotion"]))
    add("MK/BT/L98/horn+hexagon+charm+reindeer/wind", "Breakthrough", 98, STATS_B, "wind",
        arts(["horn_flute", "hexagon_necklace", "charm_of_the_undead", "reindeer_spear"]))
    add("MK/WB/L104/soul+shamaness+bottle+chalice/blaze", "World Boss", 104, STATS_A, "blaze",
        arts(["soul_contract", "shamaness_marble", "bottle_of_emotion", "chalice"]), **BLAZE)
    add("MK/WB/L117/shamaness+old_music_box+charm+hexagon/none", "World Boss", 117, STATS_A, "none",
        arts(["shamaness_marble", "old_music_box", "charm_of_the_undead", "hexagon_necklace"]))
    add("MK/BT/L140/horn+hexagon+charm+candle/none", "Breakthrough", 140, STATS_A, "none",
        arts(["horn_flute", "hexagon_necklace", "charm_of_the_undead", "candle"]))
    add("MK/BT/L140/horn+hexagon+charm+reindeer/wind", "Breakthrough", 140, STATS_A, "wind",
        arts(["horn_flute", "hexagon_necklace", "charm_of_the_undead", "reindeer_spear"]))
    add("MK/WB/L118/shamaness+secret_map+alliance+bottle/blaze", "World Boss", 118, STATS_A, "blaze",
        arts(["shamaness_marble", "secret_map", "alliance_badge", "bottle_of_emotion"]), **BLAZE)
    add("MK/CH/L118/soul+shamaness+ring+horn/blaze", "Chapter Hunt", 118, STATS_A, "blaze",
        arts(["soul_contract", "shamaness_marble", "ring_of_cycles", "horn_flute"]), **BLAZE)
    add("MK/PvP/L140/soul+shamaness+candle+hexagon/none", "PvP", 140, STATS_A, "none",
        arts(["soul_contract", "shamaness_marble", "candle", "hexagon_necklace"]))
    add("MK/HD/L140/soul+shamaness+secret_map+horn/wind/MoreBoss", "Hero Dungeon", 140, STATS_A, "wind",
        arts(["soul_contract", "shamaness_marble", "secret_map", "horn_flute"]), boss_normal_weight_choice="More Boss",
        companion_summon_time_increase_pct=20)
    add("MK/CH/L140/soul+shamaness+bottle+alliance/none", "Chapter Hunt", 140, STATS_A, "none",
        arts(["soul_contract", "shamaness_marble", "bottle_of_emotion", "alliance_badge"]))
    add("MK/ED/L140/hexagon+charm+candle+horn/blaze", "Enhancement Dungeon", 140, STATS_A, "blaze",
        arts(["hexagon_necklace", "charm_of_the_undead", "candle", "horn_flute"]), **BLAZE)
    add("MK/ED/L140/star_rock+cursed_doll+lit_lamp+clear_spring/none", "Enhancement Dungeon", 140, STATS_A, "none",
        arts(["star_rock", "cursed_doll", "clear_spring_water", "sayrams_necklace"]))
    C.arwen_cases(add, STATS_A)
    return cases


if __name__ == "__main__":
    cs = artifact_cases()
    ids = [c for c, _ in cs]
    assert len(ids) == len(set(ids))
    seen = {a["key"] for _, d in cs for a in d["artifacts"]}
    print(len(cs), "cases;", len(seen), "distinct artifacts equipped")
