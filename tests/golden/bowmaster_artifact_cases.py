"""The golden input matrix for Bowmaster WITH artifacts equipped (plain data: no workbook, no engine import).

``artifact_cases()`` returns ``[(case_id, inputs_dict), ...]``; an inputs dict is the ``tests/golden/bowmaster_cases.py`` shape plus
``inputs["artifacts"] = [{"key": <artifact id>, "star": 0..5 | None}, ...]`` (<= 4 equipped slots; ``star`` None = "Not Unlocked").
``TOGGLE_PAIRS`` lists ``(with_case, without_case, label)`` triples whose workbook totals give the equip-toggle delta; ``EQUIV_PAIRS`` the Arwen's
Glass Shoes equivalence pairs (artifact at Inputs x == no artifact at Inputs x + star value).

Same structure as ``hero_artifact_cases.py`` / ``artifact_cases.py`` (FP-Mage): every one of the 36 artifacts is equipped at least once at star 5 in World
Boss (fixed length, timeline engine ON) with Blaze Wizard Lv10 (groups G1..G9); further runs cover the other fight shapes (steady state, phased contents,
PvP, KO dungeons, Chapter Boss), star-dependent values (star 0 / 2 / 3 / "Not Unlocked"), Book of Ancient + Ring of Cycles around the 100% crit-rate line,
Reindeer's Spear at def pen 50 / 80 / 99 (Bowmaster has no live Defense Penetration of its own), matched with / without pairs for the toggle deltas, and
Bowmaster-specific shapes: Covering Fire's 1 s stun (Lv49 mastery) with and without a companion, Lv48 (no stun) vs Lv49, Illusion Step (Lv117 unlock,
Lv118 boost), Lv100 (Arrow Stream unlock), and Peach Tree / Silver Pendant / Candle in the boss bucket the basic attack's own Boss Mastery shares.
"""
import artifact_cases_common as C
from artifact_cases_common import BLAZE, EQUIV_PAIRS, arts  # noqa: F401
from bowmaster_cases import STATS_A, make_inputs

TOGGLE_PAIRS = C.toggle_pairs()


def artifact_cases():
    cases, add = C.begin(make_inputs)
    C.common_cases(add, STATS_A)
    # ---- Bowmaster-specific shapes: Covering Fire's stun (Lv49 mastery) with / without a companion; Illusion Step Lv117 / Lv118; Lv100 ----
    add("BOW/BT/horn+hexagon+charm+candle/none", "Breakthrough", 140, STATS_A, "none",
        arts(["horn_flute", "hexagon_necklace", "charm_of_the_undead", "candle"]))
    add("BOW/BT/horn+hexagon+charm+reindeer/wind", "Breakthrough", 140, STATS_A, "wind",
        arts(["horn_flute", "hexagon_necklace", "charm_of_the_undead", "reindeer_spear"]))
    add("BOW/BT/lv49/hexagon+charm+candle+bottle/none", "Breakthrough", 49, STATS_A, "none",
        arts(["hexagon_necklace", "charm_of_the_undead", "candle", "bottle_of_emotion"]))
    add("BOW/BT/lv48/hexagon+charm+candle+bottle/none", "Breakthrough", 48, STATS_A, "none",
        arts(["hexagon_necklace", "charm_of_the_undead", "candle", "bottle_of_emotion"]))
    add("BOW/WB/lv49/hexagon+charm+candle+bottle/none", "World Boss", 49, STATS_A, "none",
        arts(["hexagon_necklace", "charm_of_the_undead", "candle", "bottle_of_emotion"]))
    add("BOW/WB/lv48/hexagon+charm+candle+bottle/none", "World Boss", 48, STATS_A, "none",
        arts(["hexagon_necklace", "charm_of_the_undead", "candle", "bottle_of_emotion"]))
    add("BOW/WB/lv117/horn+hexagon+charm+candle/blaze", "World Boss", 117, STATS_A, "blaze",
        arts(["horn_flute", "hexagon_necklace", "charm_of_the_undead", "candle"]), **BLAZE)
    add("BOW/WB/lv118/horn+hexagon+charm+candle/blaze", "World Boss", 118, STATS_A, "blaze",
        arts(["horn_flute", "hexagon_necklace", "charm_of_the_undead", "candle"]), **BLAZE)
    add("BOW/WB/lv100/horn+hexagon+charm+candle/none", "World Boss", 100, STATS_A, "none",
        arts(["horn_flute", "hexagon_necklace", "charm_of_the_undead", "candle"]))
    add("BOW/CH/lv100/soul+reindeer+ring+horn/blaze", "Chapter Hunt", 100, STATS_A, "blaze",
        arts(["soul_contract", "reindeer_spear", "ring_of_cycles", "horn_flute"]), **BLAZE)
    add("BOW/WB/boss_bucket/peach+silver+sayrams+star_rock/blaze", "World Boss", 140, STATS_A, "blaze",
        arts(["peach_tree", "silver_pendant", "sayrams_necklace", "star_rock"]), **BLAZE)
    add("BOW/ED/lv140/bow/horn+bottle+secret_map+charm", "Enhancement Dungeon", 140, STATS_A, "bow",
        arts(["horn_flute", "bottle_of_emotion", "secret_map", "charm_of_the_undead"]), **BLAZE)
    C.arwen_cases(add, STATS_A)
    return cases


if __name__ == "__main__":
    cs = artifact_cases()
    ids = [c for c, _ in cs]
    assert len(ids) == len(set(ids))
    seen = {a["key"] for _, d in cs for a in d["artifacts"]}
    print(len(cs), "cases;", len(seen), "distinct artifacts equipped")
