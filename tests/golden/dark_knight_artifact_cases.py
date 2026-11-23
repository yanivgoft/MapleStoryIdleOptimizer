"""The golden input matrix for Dark Knight WITH artifacts equipped (plain data: no workbook, no engine import).

``artifact_cases()`` returns ``[(case_id, inputs_dict), ...]``; an inputs dict is the ``tests/golden/dark_knight_cases.py`` shape plus
``inputs["artifacts"] = [{"key": <artifact id>, "star": 0..5 | None}, ...]`` (<= 4 equipped slots; ``star`` None = "Not Unlocked").
``TOGGLE_PAIRS`` lists ``(with_case, without_case, label)`` triples whose workbook totals give the equip-toggle delta; ``EQUIV_PAIRS`` the Arwen's
Glass Shoes equivalence pairs (artifact at Inputs x == no artifact at Inputs x + star value).

Same structure as ``artifact_cases.py`` (FP-Mage): every one of the 36 artifacts is equipped at least once at star 5 in World Boss (fixed length,
timeline engine ON) with Blaze Wizard Lv10 (groups G1..G9); further runs cover the other fight shapes (steady state, phased contents, PvP, KO
dungeons, Chapter Boss), star-dependent values (star 0 / 2 / 3 / "Not Unlocked"), Book of Ancient + Ring of Cycles around the 100% crit-rate line,
Reindeer's Spear at def pen 50 / 80 / 99, matched with / without pairs for the toggle deltas, and Dark Knight-specific shapes (Evil Eye Shock's stun
alone below Lv 63, Rush + Evil Eye Shock from Lv 63, no Defense at all, the timed Attack% buffs unlocking at Lv 45 / 66 / 69 / 115 with stat set C, whose
skill-level bonuses and Cooldown Decrease / Buff Duration move the timed buffs' windows, with Soul Contract / Shamaness Marble).
"""
import artifact_cases_common as C
from artifact_cases_common import BLAZE, EQUIV_PAIRS, arts  # noqa: F401
from dark_knight_cases import STATS_A, STATS_C, make_inputs

TOGGLE_PAIRS = C.toggle_pairs()


def artifact_cases():
    cases, add = C.begin(make_inputs)
    C.common_cases(add, STATS_A)
    # ---- Dark Knight-specific shapes: Evil Eye Shock alone (Lv40-62) / + Rush (Lv63+) as the player's own stuns, the four timed Attack% buffs unlocking
    #      (Hyper Body 45, Cross Over Chains 66, Hex 69, Dark Resonance 115), no Defense (Iron Wall adds nothing) ----
    add("DK/BT/C45/horn+hexagon+charm+candle/none", "Breakthrough", 45, STATS_C, "none",
        arts(["horn_flute", "hexagon_necklace", "charm_of_the_undead", "candle"]))
    add("DK/WB/C62/horn+hexagon+charm+candle/blaze", "World Boss", 62, STATS_C, "blaze",
        arts(["horn_flute", "hexagon_necklace", "charm_of_the_undead", "candle"]), **BLAZE)
    add("DK/WB/C66/bottle+secret_map+charm+shamaness/none", "World Boss", 66, STATS_C, "none",
        arts(["bottle_of_emotion", "secret_map", "charm_of_the_undead", "shamaness_marble"]))
    add("DK/WB/C69/bottle+secret_map+charm+shamaness/blaze", "World Boss", 69, STATS_C, "blaze",
        arts(["bottle_of_emotion", "secret_map", "charm_of_the_undead", "shamaness_marble"]), **BLAZE)
    add("DK/WB/C115/reindeer+ring+horn+peach/blaze", "World Boss", 115, STATS_C, "blaze",
        arts(["reindeer_spear", "ring_of_cycles", "horn_flute", "peach_tree"]), **BLAZE)
    add("DK/CH/C82/soul+reindeer+ring+horn/blaze", "Chapter Hunt", 82, STATS_C, "blaze",
        arts(["soul_contract", "reindeer_spear", "ring_of_cycles", "horn_flute"]), **BLAZE)
    add("DK/WB/C105/soul+shamaness+bottle+chalice/none", "World Boss", 105, STATS_C, "none",
        arts(["soul_contract", "shamaness_marble", "bottle_of_emotion", "chalice"]))
    add("DK/PvP/C105/soul+shamaness+candle+hexagon/none", "PvP", 105, STATS_C, "none",
        arts(["soul_contract", "shamaness_marble", "candle", "hexagon_necklace"]))
    add("DK/WB/C140/soul+shamaness+old_music_box+charm/blaze", "World Boss", 140, STATS_C, "blaze",
        arts(["soul_contract", "shamaness_marble", "old_music_box", "charm_of_the_undead"]), **BLAZE)
    add("DK/HD/C140/soul+shamaness+secret_map+horn/wind/MoreBoss", "Hero Dungeon", 140, STATS_C, "wind",
        arts(["soul_contract", "shamaness_marble", "secret_map", "horn_flute"]), boss_normal_weight_choice="More Boss",
        companion_summon_time_increase_pct=20)
    add("DK/CH/C140/soul+shamaness+bottle+alliance/none", "Chapter Hunt", 140, STATS_C, "none",
        arts(["soul_contract", "shamaness_marble", "bottle_of_emotion", "alliance_badge"]))
    add("DK/ED/C140/hexagon+charm+candle+horn/blaze", "Enhancement Dungeon", 140, STATS_C, "blaze",
        arts(["hexagon_necklace", "charm_of_the_undead", "candle", "horn_flute"]), **BLAZE)
    add("DK/WB/def0/horn+hexagon+reindeer+ring/blaze", "World Boss", 140, dict(STATS_A, defense=0, defense_pct=0), "blaze",
        arts(["horn_flute", "hexagon_necklace", "reindeer_spear", "ring_of_cycles"]), **BLAZE)
    add("DK/PvP/def0/candle+reindeer+soul_pouch+horn/blaze", "PvP", 140, dict(STATS_A, defense=0, defense_pct=0), "blaze",
        arts(["candle", "reindeer_spear", "soul_pouch", "horn_flute"]), **BLAZE)
    add("DK/WB/peach+silver+sayrams+star_rock/blaze", "World Boss", 140, STATS_A, "blaze",
        arts(["peach_tree", "silver_pendant", "sayrams_necklace", "star_rock"]), **BLAZE)
    C.arwen_cases(add, STATS_A)
    return cases


if __name__ == "__main__":
    cs = artifact_cases()
    ids = [c for c, _ in cs]
    assert len(ids) == len(set(ids))
    seen = {a["key"] for _, d in cs for a in d["artifacts"]}
    print(len(cs), "cases;", len(seen), "distinct artifacts equipped")
