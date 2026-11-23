"""The golden input matrix for Corsair WITH artifacts equipped (plain data: no workbook, no engine import).

``artifact_cases()`` returns ``[(case_id, inputs_dict), ...]``; an inputs dict is the ``tests/golden/corsair_cases.py`` shape plus
``inputs["artifacts"] = [{"key": <artifact id>, "star": 0..5 | None}, ...]`` (<= 4 equipped slots; ``star`` None = "Not Unlocked").
``TOGGLE_PAIRS`` lists ``(with_case, without_case, label)`` triples whose workbook totals give the equip-toggle delta; ``EQUIV_PAIRS`` the Arwen's
Glass Shoes equivalence pairs (artifact at Inputs x == no artifact at Inputs x + star value).

Same structure as ``hero_artifact_cases.py`` / ``artifact_cases.py`` (FP-Mage): every one of the 36 artifacts is equipped at least once at star 5 in World
Boss (fixed length, timeline engine ON) with Blaze Wizard Lv10 (groups G1..G9); further runs cover the other fight shapes (steady state, phased contents,
PvP, KO dungeons, Chapter Boss), star-dependent values (star 0 / 2 / 3 / "Not Unlocked"), Book of Ancient + Ring of Cycles around the 100% crit-rate line,
Reindeer's Spear at def pen 50 / 80 / 99 (Corsair has no live Defense Penetration of its own), matched with / without pairs for the toggle deltas, and
Corsair-specific shapes: Blackboot Bill's 2 s stun (Lv66) with and without a companion, Lv65 (no stun) vs Lv66, Broadside's sustained turret (Lv117 / Lv118 / Lv138),
Quickdraw (Lv124 / Lv125: Brain Scrambler's / Rapid Fire's cooldowns divided by the closed-form fixed point) with Soul Contract in Chapter Hunt, Jolly Roger's
Final Damage ramp next to the Final Damage artifacts, and Peach Tree / Silver Pendant / Candle / Sayram's / Star Rock in the boss bucket.
"""
import artifact_cases_common as C
from artifact_cases_common import BLAZE, EQUIV_PAIRS, arts  # noqa: F401
from corsair_cases import STATS_A, make_inputs

TOGGLE_PAIRS = C.toggle_pairs([
    ("COR/CH/lv140/soul/blaze", "COR/CH/lv140/base/blaze", "soul_contract@ChapterHunt(Quickdraw)"),
])


def artifact_cases():
    cases, add = C.begin(make_inputs)
    C.common_cases(add, STATS_A)
    # ---- Corsair-specific shapes: Blackboot Bill's stun (Lv66; companion or not), Lv117 / Lv118 (Broadside's sustained turret 330% -> 1900%), Lv125 (Quickdraw
    #      divides Brain Scrambler's / Rapid Fire's cooldowns by the closed-form fixed point: Soul Contract must reach the divided cooldowns too), Lv138 (Broadside
    #      window 30 s, two Battleships), Lv122 (Ahoy Mateys FD proc), Lv100 ----
    add("COR/BT/horn+hexagon+charm+candle/none", "Breakthrough", 140, STATS_A, "none",
        arts(["horn_flute", "hexagon_necklace", "charm_of_the_undead", "candle"]))
    add("COR/BT/horn+hexagon+charm+reindeer/wind", "Breakthrough", 140, STATS_A, "wind",
        arts(["horn_flute", "hexagon_necklace", "charm_of_the_undead", "reindeer_spear"]))
    add("COR/BT/lv66/hexagon+charm+candle+bottle/none", "Breakthrough", 66, STATS_A, "none",
        arts(["hexagon_necklace", "charm_of_the_undead", "candle", "bottle_of_emotion"]))
    add("COR/BT/lv65/hexagon+charm+candle+bottle/none", "Breakthrough", 65, STATS_A, "none",
        arts(["hexagon_necklace", "charm_of_the_undead", "candle", "bottle_of_emotion"]))
    add("COR/WB/lv66/hexagon+charm+candle+bottle/none", "World Boss", 66, STATS_A, "none",
        arts(["hexagon_necklace", "charm_of_the_undead", "candle", "bottle_of_emotion"]))
    add("COR/WB/lv65/hexagon+charm+candle+bottle/none", "World Boss", 65, STATS_A, "none",
        arts(["hexagon_necklace", "charm_of_the_undead", "candle", "bottle_of_emotion"]))
    add("COR/WB/lv117/horn+hexagon+charm+candle/blaze", "World Boss", 117, STATS_A, "blaze",
        arts(["horn_flute", "hexagon_necklace", "charm_of_the_undead", "candle"]), **BLAZE)
    add("COR/WB/lv118/horn+hexagon+charm+candle/blaze", "World Boss", 118, STATS_A, "blaze",
        arts(["horn_flute", "hexagon_necklace", "charm_of_the_undead", "candle"]), **BLAZE)
    add("COR/WB/lv124/horn+hexagon+charm+candle/blaze", "World Boss", 124, STATS_A, "blaze",
        arts(["horn_flute", "hexagon_necklace", "charm_of_the_undead", "candle"]), **BLAZE)
    add("COR/WB/lv125/horn+hexagon+charm+candle/blaze", "World Boss", 125, STATS_A, "blaze",
        arts(["horn_flute", "hexagon_necklace", "charm_of_the_undead", "candle"]), **BLAZE)
    add("COR/WB/lv138/horn+hexagon+charm+candle/blaze", "World Boss", 138, STATS_A, "blaze",
        arts(["horn_flute", "hexagon_necklace", "charm_of_the_undead", "candle"]), **BLAZE)
    add("COR/CH/lv125/soul+reindeer+ring+horn/blaze", "Chapter Hunt", 125, STATS_A, "blaze",
        arts(["soul_contract", "reindeer_spear", "ring_of_cycles", "horn_flute"]), **BLAZE)
    add("COR/CH/lv124/soul+chalice+charm+horn/wind", "Chapter Hunt", 124, STATS_A, "wind",
        arts(["soul_contract", "chalice", "charm_of_the_undead", "horn_flute"]))
    add("COR/CH/lv140/soul/blaze", "Chapter Hunt", 140, STATS_A, "blaze", arts(["soul_contract"]), **BLAZE)
    add("COR/CH/lv140/base/blaze", "Chapter Hunt", 140, STATS_A, "blaze", [], **BLAZE)
    add("COR/WB/boss_bucket/peach+silver+sayrams+star_rock/blaze", "World Boss", 140, STATS_A, "blaze",
        arts(["peach_tree", "silver_pendant", "sayrams_necklace", "star_rock"]), **BLAZE)
    add("COR/ED/lv140/bow/horn+bottle+secret_map+charm", "Enhancement Dungeon", 140, STATS_A, "bow",
        arts(["horn_flute", "bottle_of_emotion", "secret_map", "charm_of_the_undead"]), **BLAZE)
    add("COR/WB/lv140/jolly_roger/fd+attack/wind", "World Boss", 140, dict(STATS_A, final_damage=30), "wind",
        arts(["candle", "flaming_lava", "bottle_of_emotion", "old_music_box"]))
    C.arwen_cases(add, STATS_A)
    return cases


if __name__ == "__main__":
    cs = artifact_cases()
    ids = [c for c, _ in cs]
    assert len(ids) == len(set(ids))
    seen = {a["key"] for _, d in cs for a in d["artifacts"]}
    print(len(cs), "cases;", len(seen), "distinct artifacts equipped")
