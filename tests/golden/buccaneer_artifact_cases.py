"""The golden input matrix for Buccaneer WITH artifacts equipped (plain data: no workbook, no engine import).

``artifact_cases()`` returns ``[(case_id, inputs_dict), ...]``; an inputs dict is the ``tests/golden/buccaneer_cases.py`` shape plus
``inputs["artifacts"] = [{"key": <artifact id>, "star": 0..5 | None}, ...]`` (<= 4 equipped slots; ``star`` None = "Not Unlocked").
``TOGGLE_PAIRS`` lists ``(with_case, without_case, label)`` triples whose workbook totals give the equip-toggle delta; ``EQUIV_PAIRS`` the Arwen's
Glass Shoes equivalence pairs (artifact at Inputs x == no artifact at Inputs x + star value).

Same structure as ``artifact_cases.py`` (FP-Mage): every one of the 36 artifacts is equipped at least once at star 5 in World Boss (fixed length,
timeline engine ON) with Blaze Wizard Lv10 (groups G1..G9); further runs cover the other fight shapes (steady state, phased contents, PvP, KO
dungeons, Chapter Boss), star-dependent values (star 0 / 2 / 3 / "Not Unlocked"), Book of Ancient + Ring of Cycles around the 100% crit-rate line,
Reindeer's Spear at def pen 50 / 80 / 99, matched with / without pairs for the toggle deltas, and
Buccaneer-specific shapes (the player's own Corkscrew Blow stun from Lv63 with no companion and its Breakthrough boss-phase extension, Lv 62 = Corkscrew Blow
locked, Lv 99 / 100 = Hook Bomber locked / just unlocked, Lv 115 / 125 = Crossbones / Time Leap, Lv 134 = Octopunch haste).
"""
import artifact_cases_common as C
from artifact_cases_common import BLAZE, EQUIV_PAIRS, arts  # noqa: F401
from buccaneer_cases import STATS_A, make_inputs

TOGGLE_PAIRS = C.toggle_pairs()


def artifact_cases():
    cases, add = C.begin(make_inputs)
    C.common_cases(add, STATS_A)
    # ---- Buccaneer-specific shapes: Corkscrew Blow (Lv63+, the player's own 1.8 s stun) with / without a companion and its Breakthrough boss-phase extension;
    #      Lv62 = Corkscrew Blow locked; Lv99 = Hook Bomber locked (no basic attack row); Lv100 = Hook Bomber just unlocked; Lv115 = Crossbones live, Lv125 = Time Leap live;
    #      Lv134 = Octopunch haste (11.2 s); Lv104 = 3 activations to Assault Mode.  Defense > 0 everywhere: the PvP monster defense is the character's own total Defense) ----
    add("BS/BT/horn+hexagon+charm+candle/none", "Breakthrough", 140, STATS_A, "none",
        arts(["horn_flute", "hexagon_necklace", "charm_of_the_undead", "candle"]))
    add("BS/BT/horn+hexagon+charm+reindeer/wind", "Breakthrough", 140, STATS_A, "wind",
        arts(["horn_flute", "hexagon_necklace", "charm_of_the_undead", "reindeer_spear"]))
    add("BS/WB/lv63/horn+hexagon+charm+candle/none", "World Boss", 63, STATS_A, "none",
        arts(["horn_flute", "hexagon_necklace", "charm_of_the_undead", "candle"]))
    add("BS/WB/lv62/horn+hexagon+charm+bottle/none", "World Boss", 62, STATS_A, "none",
        arts(["horn_flute", "hexagon_necklace", "charm_of_the_undead", "bottle_of_emotion"]))
    add("BS/CH/lv100/soul+reindeer+ring+horn/blaze", "Chapter Hunt", 100, STATS_A, "blaze",
        arts(["soul_contract", "reindeer_spear", "ring_of_cycles", "horn_flute"]), **BLAZE)
    add("BS/WB/lv99/hexagon+charm+candle+bottle/blaze", "World Boss", 99, STATS_A, "blaze",
        arts(["hexagon_necklace", "charm_of_the_undead", "candle", "bottle_of_emotion"]), **BLAZE)
    add("BS/WB/lv115/horn+bottle+secret_map+charm/blaze", "World Boss", 115, STATS_A, "blaze",
        arts(["horn_flute", "bottle_of_emotion", "secret_map", "charm_of_the_undead"]), **BLAZE)
    add("BS/WB/lv125/horn+hexagon+charm+ring/blaze", "World Boss", 125, STATS_A, "blaze",
        arts(["horn_flute", "hexagon_necklace", "charm_of_the_undead", "ring_of_cycles"]), **BLAZE)
    add("BS/WB/lv134/horn+hexagon+charm+candle/blaze", "World Boss", 134, STATS_A, "blaze",
        arts(["horn_flute", "hexagon_necklace", "charm_of_the_undead", "candle"]), **BLAZE)
    add("BS/CH/lv140/soul+peach+silver+alliance/none", "Chapter Hunt", 140, STATS_A, "none",
        arts(["soul_contract", "peach_tree", "silver_pendant", "alliance_badge"]))
    add("BS/ED/lv103/hexagon+charm+candle+horn/none", "Enhancement Dungeon", 103, STATS_A, "none",
        arts(["hexagon_necklace", "charm_of_the_undead", "candle", "horn_flute"]))
    add("BS/PvP/lv103/reindeer+hexagon+bottle+peach/none", "PvP", 103, STATS_A, "none",
        arts(["reindeer_spear", "hexagon_necklace", "bottle_of_emotion", "peach_tree"]))
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
