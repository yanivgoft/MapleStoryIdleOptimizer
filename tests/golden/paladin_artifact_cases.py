"""The golden input matrix for Paladin WITH artifacts equipped (plain data: no workbook, no engine import).

``artifact_cases()`` returns ``[(case_id, inputs_dict), ...]``; an inputs dict is the ``tests/golden/paladin_cases.py`` shape plus
``inputs["artifacts"] = [{"key": <artifact id>, "star": 0..5 | None}, ...]`` (<= 4 equipped slots; ``star`` None = "Not Unlocked").
``TOGGLE_PAIRS`` lists ``(with_case, without_case, label)`` triples whose workbook totals give the equip-toggle delta; ``EQUIV_PAIRS`` the Arwen's
Glass Shoes equivalence pairs (artifact at Inputs x == no artifact at Inputs x + star value).

Same structure as ``artifact_cases.py`` (FP-Mage): every one of the 36 artifacts is equipped at least once at star 5 in World Boss (fixed length,
timeline engine ON) with Blaze Wizard Lv10 (groups G1..G9); further runs cover the other fight shapes (steady state, phased contents, PvP, KO
dungeons, Chapter Boss), star-dependent values (star 0 / 2 / 3 / "Not Unlocked"), Book of Ancient + Ring of Cycles around the 100% crit-rate line,
Reindeer's Spear at def pen 50 / 80 / 99, matched with / without pairs for the toggle deltas, and Paladin-specific shapes (the player's own Rush
stun with no companion; Combat Orders' unlock levels 68 / 69 / 82 / 105 with stat set C, whose skill-level bonuses make the temporary +skill-level buff
matter, with Soul Contract / Shamaness Marble moving its uptime; below Lv 63 there is no Rush).
"""
import artifact_cases_common as C
from artifact_cases_common import BLAZE, EQUIV_PAIRS, arts  # noqa: F401
from paladin_cases import STATS_A, STATS_C, make_inputs

TOGGLE_PAIRS = C.toggle_pairs()


def artifact_cases():
    cases, add = C.begin(make_inputs)
    C.common_cases(add, STATS_A)
    # ---- Paladin-specific shapes: the player's own Rush stun (Lv63+) with / without a companion; Combat Orders (Lv69, Attack% from Lv82) ----
    add("PAL/BT/horn+hexagon+charm+candle/none", "Breakthrough", 140, STATS_A, "none",
        arts(["horn_flute", "hexagon_necklace", "charm_of_the_undead", "candle"]))
    add("PAL/BT/horn+hexagon+charm+reindeer/wind", "Breakthrough", 140, STATS_A, "wind",
        arts(["horn_flute", "hexagon_necklace", "charm_of_the_undead", "reindeer_spear"]))
    add("PAL/WB/C68/horn+hexagon+charm+candle/none", "World Boss", 68, STATS_C, "none",
        arts(["horn_flute", "hexagon_necklace", "charm_of_the_undead", "candle"]))
    add("PAL/WB/C69/bottle+secret_map+charm+shamaness/blaze", "World Boss", 69, STATS_C, "blaze",
        arts(["bottle_of_emotion", "secret_map", "charm_of_the_undead", "shamaness_marble"]), **BLAZE)
    add("PAL/CH/C82/soul+reindeer+ring+horn/blaze", "Chapter Hunt", 82, STATS_C, "blaze",
        arts(["soul_contract", "reindeer_spear", "ring_of_cycles", "horn_flute"]), **BLAZE)
    add("PAL/WB/C105/soul+shamaness+bottle+chalice/none", "World Boss", 105, STATS_C, "none",
        arts(["soul_contract", "shamaness_marble", "bottle_of_emotion", "chalice"]))
    add("PAL/PvP/C105/soul+shamaness+candle+hexagon/none", "PvP", 105, STATS_C, "none",
        arts(["soul_contract", "shamaness_marble", "candle", "hexagon_necklace"]))
    add("PAL/WB/C140/soul+shamaness+old_music_box+charm/blaze", "World Boss", 140, STATS_C, "blaze",
        arts(["soul_contract", "shamaness_marble", "old_music_box", "charm_of_the_undead"]), **BLAZE)
    add("PAL/HD/C140/soul+shamaness+secret_map+horn/wind/MoreBoss", "Hero Dungeon", 140, STATS_C, "wind",
        arts(["soul_contract", "shamaness_marble", "secret_map", "horn_flute"]), boss_normal_weight_choice="More Boss",
        companion_summon_time_increase_pct=20)
    add("PAL/CH/C140/soul+shamaness+bottle+alliance/none", "Chapter Hunt", 140, STATS_C, "none",
        arts(["soul_contract", "shamaness_marble", "bottle_of_emotion", "alliance_badge"]))
    add("PAL/ED/C140/hexagon+charm+candle+horn/blaze", "Enhancement Dungeon", 140, STATS_C, "blaze",
        arts(["hexagon_necklace", "charm_of_the_undead", "candle", "horn_flute"]), **BLAZE)
    C.arwen_cases(add, STATS_A)
    return cases


if __name__ == "__main__":
    cs = artifact_cases()
    ids = [c for c, _ in cs]
    assert len(ids) == len(set(ids))
    seen = {a["key"] for _, d in cs for a in d["artifacts"]}
    print(len(cs), "cases;", len(seen), "distinct artifacts equipped")
