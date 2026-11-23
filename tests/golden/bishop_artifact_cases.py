"""The golden input matrix for Bishop WITH artifacts equipped (plain data: no workbook, no engine import).

``artifact_cases()`` returns ``[(case_id, inputs_dict), ...]``; an inputs dict is the ``tests/golden/bishop_cases.py`` shape plus
``inputs["artifacts"] = [{"key": <artifact id>, "star": 0..5 | None}, ...]`` (<= 4 equipped slots; ``star`` None = "Not Unlocked").
``TOGGLE_PAIRS`` lists ``(with_case, without_case, label)`` triples whose workbook totals give the equip-toggle delta; ``EQUIV_PAIRS`` the Arwen's
Glass Shoes equivalence pairs (artifact at Inputs x == no artifact at Inputs x + star value).

Same structure as ``artifact_cases.py`` (FP-Mage): every one of the 36 artifacts is equipped at least once at star 5 in World Boss (fixed length,
timeline engine ON) with Blaze Wizard Lv10 (groups G1..G9); further runs cover the other fight shapes (steady state, phased contents, PvP, KO
dungeons, Chapter Boss), star-dependent values (star 0 / 2 / 3 / "Not Unlocked"), Book of Ancient + Ring of Cycles around the 100% crit-rate line,
Reindeer's Spear at def pen 50 / 80 / 99, matched with / without pairs for the toggle deltas, and
Bishop-specific shapes (the player's own Angel Ray stun from Lv103 with no companion and its Breakthrough boss-phase extension, Lv 99 = Big Bang locked (no basic
attack row), Lv 100 = Big Bang just unlocked, Lv 102 / 103 = Angel Ray locked / just unlocked, Lv 112 = Advanced Blessing + Infinity live, Lv 122 = Angel Ray's boss
proc; Defense > 0 everywhere: Invincible's INT bonus and the PvP monster defense are the character's own total Defense).
"""
import artifact_cases_common as C
from artifact_cases_common import BLAZE, EQUIV_PAIRS, arts  # noqa: F401
from bishop_cases import STATS_A, make_inputs

TOGGLE_PAIRS = C.toggle_pairs()


def artifact_cases():
    cases, add = C.begin(make_inputs)
    C.common_cases(add, STATS_A)
    # ---- Bishop-specific shapes: Angel Ray (Lv103+) with / without a companion; Big Bang Lv100; Advanced Blessing + Infinity (Lv112); the boss proc (Lv122) ----
    add("BS/BT/horn+hexagon+charm+candle/none", "Breakthrough", 140, STATS_A, "none",
        arts(["horn_flute", "hexagon_necklace", "charm_of_the_undead", "candle"]))
    add("BS/BT/horn+hexagon+charm+reindeer/wind", "Breakthrough", 140, STATS_A, "wind",
        arts(["horn_flute", "hexagon_necklace", "charm_of_the_undead", "reindeer_spear"]))
    add("BS/WB/lv103/horn+hexagon+charm+candle/none", "World Boss", 103, STATS_A, "none",
        arts(["horn_flute", "hexagon_necklace", "charm_of_the_undead", "candle"]))
    add("BS/WB/lv102/horn+hexagon+charm+bottle/none", "World Boss", 102, STATS_A, "none",
        arts(["horn_flute", "hexagon_necklace", "charm_of_the_undead", "bottle_of_emotion"]))
    add("BS/CH/lv100/soul+reindeer+ring+horn/blaze", "Chapter Hunt", 100, STATS_A, "blaze",
        arts(["soul_contract", "reindeer_spear", "ring_of_cycles", "horn_flute"]), **BLAZE)
    add("BS/WB/lv99/hexagon+charm+candle+bottle/blaze", "World Boss", 99, STATS_A, "blaze",
        arts(["hexagon_necklace", "charm_of_the_undead", "candle", "bottle_of_emotion"]), **BLAZE)
    add("BS/WB/lv112/horn+bottle+secret_map+charm/blaze", "World Boss", 112, STATS_A, "blaze",
        arts(["horn_flute", "bottle_of_emotion", "secret_map", "charm_of_the_undead"]), **BLAZE)
    add("BS/WB/lv125/horn+hexagon+charm+ring/blaze", "World Boss", 125, STATS_A, "blaze",
        arts(["horn_flute", "hexagon_necklace", "charm_of_the_undead", "ring_of_cycles"]), **BLAZE)
    add("BS/ED/lv103/hexagon+charm+candle+horn/none", "Enhancement Dungeon", 103, STATS_A, "none",
        arts(["hexagon_necklace", "charm_of_the_undead", "candle", "horn_flute"]))
    add("BS/PvP/lv103/reindeer+hexagon+bottle+peach/none", "PvP", 103, STATS_A, "none",
        arts(["reindeer_spear", "hexagon_necklace", "bottle_of_emotion", "peach_tree"]), defense_pct=100)
    add("BS/HD/lv140/hexagon+charm+silver+peach/wind", "Hero Dungeon", 140, STATS_A, "wind",
        arts(["hexagon_necklace", "charm_of_the_undead", "silver_pendant", "peach_tree"]))
    C.arwen_cases(add, STATS_A)
    return cases


if __name__ == "__main__":
    cs = artifact_cases()
    ids = [c for c, _ in cs]
    assert len(ids) == len(set(ids))
    seen = {a["key"] for _, d in cs for a in d["artifacts"]}
    print(len(cs), "cases;", len(seen), "distinct artifacts equipped")
