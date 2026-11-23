"""The golden input matrix for Ice/Lightning Mage WITH artifacts equipped (plain data: no workbook, no engine import).

``artifact_cases()`` returns ``[(case_id, inputs_dict), ...]``; an inputs dict is the ``tests/golden/ice_lightning_mage_cases.py`` shape plus
``inputs["artifacts"] = [{"key": <artifact id>, "star": 0..5 | None}, ...]`` (<= 4 equipped slots; ``star`` None = "Not Unlocked").
``TOGGLE_PAIRS`` lists ``(with_case, without_case, label)`` triples whose workbook totals give the equip-toggle delta; ``EQUIV_PAIRS`` the Arwen's
Glass Shoes equivalence pairs (artifact at Inputs x == no artifact at Inputs x + star value).

Same structure as ``artifact_cases.py`` (FP-Mage): every one of the 36 artifacts is equipped at least once at star 5 in World Boss (fixed length,
timeline engine ON) with Blaze Wizard Lv10 (groups G1..G9); further runs cover the other fight shapes (steady state, phased contents, PvP, KO
dungeons, Chapter Boss), star-dependent values (star 0 / 2 / 3 / "Not Unlocked"), Book of Ancient + Ring of Cycles around the 100% crit-rate line,
Reindeer's Spear at def pen 50 / 80 / 99, matched with / without pairs for the toggle deltas, and
ILM-specific shapes (the player's own Glacier Wall stun with no companion, Breakthrough boss-phase extension, Lv 105 / 112 = Infinity locked / just unlocked
with Meditation + Magic Guard live; below Lv 100 Chain Lightning is locked and the basic attack row is 0).
"""
import artifact_cases_common as C
from artifact_cases_common import BLAZE, EQUIV_PAIRS, arts  # noqa: F401
from ice_lightning_mage_cases import STATS_A, make_inputs

TOGGLE_PAIRS = C.toggle_pairs()


def artifact_cases():
    cases, add = C.begin(make_inputs)
    C.common_cases(add, STATS_A)
    # ---- ILM-specific shapes: the player's own Glacier Wall stun (Lv63+) with / without a companion; Infinity locked (Lv105) / unlocked (Lv112) ----
    add("ILM/BT/horn+hexagon+charm+candle/none", "Breakthrough", 140, STATS_A, "none",
        arts(["horn_flute", "hexagon_necklace", "charm_of_the_undead", "candle"]))
    add("ILM/BT/horn+hexagon+charm+reindeer/wind", "Breakthrough", 140, STATS_A, "wind",
        arts(["horn_flute", "hexagon_necklace", "charm_of_the_undead", "reindeer_spear"]))
    add("ILM/WB/lv105/horn+hexagon+charm+candle/none", "World Boss", 105, STATS_A, "none",
        arts(["horn_flute", "hexagon_necklace", "charm_of_the_undead", "candle"]))
    add("ILM/CH/lv105/soul+reindeer+ring+horn/blaze", "Chapter Hunt", 105, STATS_A, "blaze",
        arts(["soul_contract", "reindeer_spear", "ring_of_cycles", "horn_flute"]), **BLAZE)
    add("ILM/WB/lv112/horn+bottle+secret_map+charm/blaze", "World Boss", 112, STATS_A, "blaze",
        arts(["horn_flute", "bottle_of_emotion", "secret_map", "charm_of_the_undead"]), **BLAZE)
    C.arwen_cases(add, STATS_A)
    return cases


if __name__ == "__main__":
    cs = artifact_cases()
    ids = [c for c, _ in cs]
    assert len(ids) == len(set(ids))
    seen = {a["key"] for _, d in cs for a in d["artifacts"]}
    print(len(cs), "cases;", len(seen), "distinct artifacts equipped")
