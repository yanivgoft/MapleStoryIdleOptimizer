"""The golden input matrix for Shadower WITH artifacts equipped (plain data: no workbook, no engine import).

``artifact_cases()`` returns ``[(case_id, inputs_dict), ...]``; an inputs dict is the ``tests/golden/shadower_cases.py`` shape plus
``inputs["artifacts"] = [{"key": <artifact id>, "star": 0..5 | None}, ...]`` (<= 4 equipped slots; ``star`` None = "Not Unlocked").
``TOGGLE_PAIRS`` lists ``(with_case, without_case, label)`` triples whose workbook totals give the equip-toggle delta; ``EQUIV_PAIRS`` the Arwen's
Glass Shoes equivalence pairs (artifact at Inputs x == no artifact at Inputs x + star value).

Same structure as ``buccaneer_artifact_cases.py``: every one of the 36 artifacts is equipped at least once at star 5 in World Boss (fixed length,
timeline engine ON) with Blaze Wizard Lv10 (groups G1..G9); further runs cover the other fight shapes (steady state, phased contents, PvP, KO
dungeons, Chapter Boss), star-dependent values (star 0 / 2 / 3 / "Not Unlocked"), Book of Ancient + Ring of Cycles around the 100% crit-rate line (Dark
Sight's Crit Rate counts towards the threshold), Reindeer's Spear at def pen 50 / 80 / 99, matched with / without pairs for the toggle deltas, and
Shadower-specific shapes: Phase Dash (Lv63, the player's own 2 s stun: Lv62 = locked, Lv63 = just unlocked, with / without a companion and its Breakthrough boss-phase
extension), Lv75 (Meso Mastery / Meso chance), Lv82 (Venom's Weaken, enemy-damage-taken artifacts), Lv99 / 100 (Cruel Stab locked / just unlocked), Lv110 / 113
(Smokescreen / its Crit Damage mastery with Contract of Darkness / Book of Ancient), Lv115 (Shadow Shifter, incoming hit rate 0 / 2.5 / 6), Lv125 (Shadower
Instinct), Lv136 (Cruel Stab's sixth line) and Soul Contract in Chapter Hunt (every cooldown incl. Phase Dash's and the buffs').
"""
import artifact_cases_common as C
from artifact_cases_common import BLAZE, EQUIV_PAIRS, arts  # noqa: F401
from shadower_cases import STATS_A, STATS_B, make_inputs


def make_stats_b():
    return dict(STATS_B)

TOGGLE_PAIRS = C.toggle_pairs([
    ("SH/CH/lv140/soul+hexagon+charm+horn/wind", "SH/CH/lv140/base/wind", "soul_contract@Chapter Hunt"),
])


def artifact_cases():
    cases, add = C.begin(make_inputs)
    C.common_cases(add, STATS_A)
    # ---- Shadower-specific shapes (Phase Dash from Lv63 is the player's own 2 s stun, cast on cooldown from the start; no companion needed) ----
    add("SH/BT/horn+hexagon+charm+candle/none", "Breakthrough", 140, STATS_A, "none",
        arts(["horn_flute", "hexagon_necklace", "charm_of_the_undead", "candle"]))
    add("SH/BT/horn+hexagon+charm+reindeer/wind", "Breakthrough", 140, STATS_A, "wind",
        arts(["horn_flute", "hexagon_necklace", "charm_of_the_undead", "reindeer_spear"]))
    add("SH/WB/lv63/horn+hexagon+charm+candle/none", "World Boss", 63, STATS_A, "none",
        arts(["horn_flute", "hexagon_necklace", "charm_of_the_undead", "candle"]))
    add("SH/WB/lv62/horn+hexagon+charm+bottle/blaze", "World Boss", 62, STATS_A, "blaze",
        arts(["horn_flute", "hexagon_necklace", "charm_of_the_undead", "bottle_of_emotion"]), **BLAZE)
    add("SH/WB/lv75/horn+bottle+secret_map+ring/blaze", "World Boss", 75, STATS_A, "blaze",
        arts(["horn_flute", "bottle_of_emotion", "secret_map", "ring_of_cycles"]), **BLAZE)
    add("SH/WB/lv82/peach+silver+candle+charm/blaze", "World Boss", 82, STATS_A, "blaze",
        arts(["peach_tree", "silver_pendant", "candle", "charm_of_the_undead"]), **BLAZE)
    add("SH/WB/lv99/hexagon+charm+candle+bottle/blaze", "World Boss", 99, STATS_A, "blaze",
        arts(["hexagon_necklace", "charm_of_the_undead", "candle", "bottle_of_emotion"]), **BLAZE)
    add("SH/WB/lv100/horn+hexagon+charm+candle/blaze", "World Boss", 100, STATS_A, "blaze",
        arts(["horn_flute", "hexagon_necklace", "charm_of_the_undead", "candle"]), **BLAZE)
    add("SH/WB/lv110/horn+bottle+secret_map+charm/blaze", "World Boss", 110, STATS_A, "blaze",
        arts(["horn_flute", "bottle_of_emotion", "secret_map", "charm_of_the_undead"]), **BLAZE)
    add("SH/WB/lv113/ring+book+contract+rainbow/crit70/blaze", "World Boss", 113, dict(STATS_A, crit_rate=70), "blaze",
        arts(["ring_of_cycles", "book_of_ancient", "contract_of_darkness", "rainbow_snail_shell"]), **BLAZE)
    add("SH/WB/lv115/horn+hexagon+charm+ring/hit0/blaze", "World Boss", 115, dict(STATS_A, incoming_hit_rate=0), "blaze",
        arts(["horn_flute", "hexagon_necklace", "charm_of_the_undead", "ring_of_cycles"]), **BLAZE)
    add("SH/WB/lv125/horn+hexagon+charm+candle/hit6/blaze", "World Boss", 125, dict(STATS_A, incoming_hit_rate=6), "blaze",
        arts(["horn_flute", "hexagon_necklace", "charm_of_the_undead", "candle"]), **BLAZE)
    add("SH/WB/lv136/horn+hexagon+charm+candle/blaze", "World Boss", 136, STATS_A, "blaze",
        arts(["horn_flute", "hexagon_necklace", "charm_of_the_undead", "candle"]), **BLAZE)
    add("SH/CH/lv100/soul+reindeer+ring+horn/blaze", "Chapter Hunt", 100, STATS_A, "blaze",
        arts(["soul_contract", "reindeer_spear", "ring_of_cycles", "horn_flute"]), **BLAZE)
    add("SH/CH/lv140/soul+peach+silver+alliance/none", "Chapter Hunt", 140, STATS_A, "none",
        arts(["soul_contract", "peach_tree", "silver_pendant", "alliance_badge"]))
    add("SH/CH/lv140/soul+hexagon+charm+horn/wind", "Chapter Hunt", 140, STATS_A, "wind",
        arts(["soul_contract", "hexagon_necklace", "charm_of_the_undead", "horn_flute"]))
    add("SH/CH/lv140/base/wind", "Chapter Hunt", 140, STATS_A, "wind", arts(["hexagon_necklace", "charm_of_the_undead", "horn_flute"]))
    add("SH/ED/lv103/hexagon+charm+candle+horn/none", "Enhancement Dungeon", 103, STATS_A, "none",
        arts(["hexagon_necklace", "charm_of_the_undead", "candle", "horn_flute"]))
    add("SH/PvP/lv103/reindeer+hexagon+bottle+peach/none", "PvP", 103, STATS_A, "none",
        arts(["reindeer_spear", "hexagon_necklace", "bottle_of_emotion", "peach_tree"]))
    add("SH/PvP/lv140/soul_pouch+candle+rainbow+silver/bow", "PvP", 140, STATS_A, "bow",
        arts(["soul_pouch", "candle", "rainbow_snail_shell", "silver_pendant"]))
    add("SH/HD/lv140/hexagon+charm+silver+peach/wind", "Hero Dungeon", 140, STATS_A, "wind",
        arts(["hexagon_necklace", "charm_of_the_undead", "silver_pendant", "peach_tree"]))
    add("SH/WB/lv200/statsB/horn+hexagon+charm+candle/blaze", "World Boss", 200, make_stats_b(), "blaze",
        arts(["horn_flute", "hexagon_necklace", "charm_of_the_undead", "candle"]), **BLAZE)
    C.arwen_cases(add, STATS_A)
    return cases


if __name__ == "__main__":
    cs = artifact_cases()
    ids = [c for c, _ in cs]
    assert len(ids) == len(set(ids))
    seen = {a["key"] for _, d in cs for a in d["artifacts"]}
    print(len(cs), "cases;", len(seen), "distinct artifacts equipped")
