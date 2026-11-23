"""The golden input matrix for FP-Mage WITH artifacts equipped (plain data: no workbook, no engine import).

``artifact_cases()`` returns ``[(case_id, inputs_dict), ...]``; an inputs dict is the ``tests/golden/cases.py`` shape plus
``inputs["artifacts"] = [{"key": <artifact id>, "star": 0..5 | None}, ...]`` (<= 4 equipped slots; ``star`` None = "Not Unlocked").
``TOGGLE_PAIRS`` lists ``(with_case, without_case, label)`` triples whose workbook totals give the equip-toggle delta.

Every one of the 36 artifacts is equipped at least once at star 5 in World Boss (fixed length, timeline engine ON) with Blaze Wizard Lv10
(groups G1..G9); further runs cover the other fight shapes (steady state, phased contents, PvP, KO dungeons, Chapter Boss), star-dependent
values (star 0 / 2 / 3 / "Not Unlocked"), Book of Ancient + Ring of Cycles around the 100% crit-rate line, Reindeer's Spear at def pen 50 / 99
and matched with / without pairs for the toggle deltas.
"""
from cases import STATS_A, make_inputs

GROUPS = {
    "G1": ["hexagon_necklace", "charm_of_the_undead", "horn_flute", "bottle_of_emotion"],
    "G2": ["candle", "chalice", "ring_of_cycles", "book_of_ancient"],
    "G3": ["reindeer_spear", "contract_of_darkness", "rainbow_snail_shell", "icy_soul_rock"],
    "G4": ["peach_tree", "silver_pendant", "flaming_lava", "fire_flower"],
    "G5": ["secret_map", "old_music_box", "alliance_badge", "sayrams_necklace"],
    "G6": ["clear_spring_water", "athena_gloves", "soul_pouch", "lit_lamp"],
    "G7": ["star_rock", "cursed_doll", "shamaness_marble", "soul_contract"],
    "G8": ["pigs_ribbon", "arwens_glass_shoes", "mushmoms_cap", "zakums_stone_piece"],
    "G9": ["horntails_scale", "pink_beans_giant_rib", "ancient_text_piece", "lunar_dew"],
}


def arts(keys, star=5):
    """Slot list; ``star`` may be one value for all or a list per slot."""
    stars = star if isinstance(star, (list, tuple)) else [star] * len(keys)
    return [{"key": k, "star": s} for k, s in zip(keys, stars)]


def artifact_cases():
    cases = []

    def add(cid, content, level, stats, companion, slots, **over):
        d = make_inputs(content, level, stats, companion, **over)
        d["artifacts"] = slots
        cases.append((cid, d))

    BLAZE = dict(status_effect_damage=30)
    # ---- baselines (no artifact) for the toggle deltas ----
    add("base/World Boss/blaze", "World Boss", 140, STATS_A, "blaze", [], **BLAZE)
    # ---- every artifact at star 5: World Boss (engine ON), Blaze Wizard Lv10 ----
    for gid, keys in GROUPS.items():
        add(f"{gid}/World Boss/blaze", "World Boss", 140, STATS_A, "blaze", arts(keys), **BLAZE)
    # ---- toggle pairs: one artifact alone vs the baseline ----
    for key in ("horn_flute", "reindeer_spear", "ring_of_cycles", "hexagon_necklace"):
        add(f"solo/{key}/World Boss/blaze", "World Boss", 140, STATS_A, "blaze", arts([key]), **BLAZE)
    # ---- other fight shapes ----
    add("CH/soul_contract+chalice+charm+horn/blaze", "Chapter Hunt", 140, STATS_A, "blaze",
        arts(["soul_contract", "chalice", "charm_of_the_undead", "horn_flute"]), **BLAZE)
    add("CH/hexagon+ring+secret_map+fire_flower/none", "Chapter Hunt", 140, STATS_A, "none",
        arts(["hexagon_necklace", "ring_of_cycles", "secret_map", "fire_flower"]))
    add("BT/hexagon+charm+candle+chalice/blaze", "Breakthrough", 140, STATS_A, "blaze",
        arts(["hexagon_necklace", "charm_of_the_undead", "candle", "chalice"]), **BLAZE)
    add("BT/reindeer+secret_map+fire_flower+sayrams/blaze", "Breakthrough", 140, STATS_A, "blaze",
        arts(["reindeer_spear", "secret_map", "fire_flower", "sayrams_necklace"]), **BLAZE)
    add("PvP/candle+rainbow+hexagon+charm/blaze", "PvP", 140, STATS_A, "blaze",
        arts(["candle", "rainbow_snail_shell", "hexagon_necklace", "charm_of_the_undead"]), **BLAZE)
    add("PvP/reindeer+soul_pouch+ring+horn/blaze", "PvP", 140, STATS_A, "blaze",
        arts(["reindeer_spear", "soul_pouch", "ring_of_cycles", "horn_flute"]), **BLAZE, def_pen=80)
    add("HD/hexagon+charm+chalice+candle/blaze/MoreBoss", "Hero Dungeon", 140, STATS_A, "blaze",
        arts(["hexagon_necklace", "charm_of_the_undead", "chalice", "candle"]), boss_normal_weight_choice="More Boss", **BLAZE)
    add("CB/horn+old_music_box+hexagon+charm/blaze", "Chapter Boss", 140, STATS_A, "blaze",
        arts(["horn_flute", "old_music_box", "hexagon_necklace", "charm_of_the_undead"]), **BLAZE)
    add("WD/secret_map+flaming_lava+silver+peach/none", "Weapon Dungeon", 140, STATS_A, "none",
        arts(["secret_map", "flaming_lava", "silver_pendant", "peach_tree"]))
    add("ED/hexagon+charm+candle+horn/blaze", "Enhancement Dungeon", 140, STATS_A, "blaze",
        arts(["hexagon_necklace", "charm_of_the_undead", "candle", "horn_flute"]), **BLAZE)
    add("WB/horn_flute/none", "World Boss", 140, STATS_A, "none", arts(["horn_flute"]))
    # ---- crit rate around 100%: Ring of Cycles' two branches, Book of Ancient, Rainbow Snail Shell raising the threshold ----
    low_crit = dict(STATS_A, crit_rate=85)
    add("WB/ring+rainbow+book+bottle/crit85/blaze", "World Boss", 140, low_crit, "blaze",
        arts(["ring_of_cycles", "rainbow_snail_shell", "book_of_ancient", "bottle_of_emotion"]), **BLAZE)
    add("WB/ring+contract_of_darkness/crit98/blaze", "World Boss", 140, dict(STATS_A, crit_rate=98), "blaze",
        arts(["ring_of_cycles", "contract_of_darkness"]), **BLAZE)
    # ---- Reindeer's Spear: diminishing returns on the boss / PvP Defense Penetration ----
    add("WB/reindeer/defpen99/blaze", "World Boss", 140, STATS_A, "blaze", arts(["reindeer_spear"]), def_pen=99, **BLAZE)
    add("WB/base/defpen99/blaze", "World Boss", 140, STATS_A, "blaze", [], def_pen=99, **BLAZE)
    # ---- lower stars (star 0, 2, 3, "Not Unlocked" = star 0) ----
    add("L1/World Boss/blaze", "World Boss", 140, STATS_A, "blaze",
        arts(["hexagon_necklace", "charm_of_the_undead", "horn_flute", "bottle_of_emotion"], [0, 2, 3, None]), **BLAZE)
    add("L2/World Boss/blaze", "World Boss", 140, STATS_A, "blaze",
        arts(["candle", "ring_of_cycles", "reindeer_spear", "contract_of_darkness"], [2, 0, 3, None]), **BLAZE)
    add("L3/Breakthrough/blaze", "Breakthrough", 140, STATS_A, "blaze",
        arts(["chalice", "fire_flower", "sayrams_necklace", "alliance_badge"], [3, 0, 2, 3]), **BLAZE)
    add("L4/Chapter Hunt/none", "Chapter Hunt", 140, STATS_A, "none",
        arts(["soul_contract", "old_music_box", "icy_soul_rock", "peach_tree"], [3, 2, 0, 3]))
    # ---- Arwen's Glass Shoes (Companion Summoning Time Increase %: star 0 = +20, star 5 = +40; EQUIV_PAIRS below) ----
    AW0, AW5 = ["arwens_glass_shoes"], ["arwens_glass_shoes"]
    for ct, comp, over in (("World Boss", "blaze", BLAZE), ("Breakthrough", "wind", {}), ("Chapter Hunt", "wind", {})):
        tag = f"{ct}/{comp}"
        add(f"AW/star0/{tag}", ct, 140, STATS_A, comp, arts(AW0, 0), **over)
        add(f"AW/star5/{tag}", ct, 140, STATS_A, comp, arts(AW5, 5), **over)
        add(f"AWref/in20/{tag}", ct, 140, STATS_A, comp, [], companion_summon_time_increase_pct=20, **over)
        add(f"AWref/in40/{tag}", ct, 140, STATS_A, comp, [], companion_summon_time_increase_pct=40, **over)
    # crosses the Blaze 3rd-stun flip: Inputs 5 + star 5 (= 45) against Inputs 45
    add("AW/star5+in5/World Boss/blaze", "World Boss", 140, STATS_A, "blaze", arts(AW5, 5), companion_summon_time_increase_pct=5, **BLAZE)
    add("AWref/in45/World Boss/blaze", "World Boss", 140, STATS_A, "blaze", [], companion_summon_time_increase_pct=45, **BLAZE)
    add("AW/star5+in5/Breakthrough/wind", "Breakthrough", 140, STATS_A, "wind", arts(AW5, 5), companion_summon_time_increase_pct=5)
    add("AWref/in45/Breakthrough/wind", "Breakthrough", 140, STATS_A, "wind", [], companion_summon_time_increase_pct=45)
    # with other artifacts equipped (Attack% bucket, Hexagon stacks, Horn Flute's uptime all depend on the window)
    others = ["bottle_of_emotion", "hexagon_necklace", "horn_flute"]
    add("AW/star5+others+in5/World Boss/blaze", "World Boss", 140, STATS_A, "blaze", arts(AW5 + others, 5), companion_summon_time_increase_pct=5, **BLAZE)
    add("AWref/others+in45/World Boss/blaze", "World Boss", 140, STATS_A, "blaze", arts(others, 5), companion_summon_time_increase_pct=45, **BLAZE)
    add("AW/star5+others+in5/Breakthrough/wind", "Breakthrough", 140, STATS_A, "wind", arts(AW5 + others, 5), companion_summon_time_increase_pct=5)
    add("AWref/others+in45/Breakthrough/wind", "Breakthrough", 140, STATS_A, "wind", arts(others, 5), companion_summon_time_increase_pct=45)
    return cases


# (case with the artifact, matching case without, label): the workbook's toggled-copy delta
TOGGLE_PAIRS = [
    ("solo/horn_flute/World Boss/blaze", "base/World Boss/blaze", "horn_flute"),
    ("solo/reindeer_spear/World Boss/blaze", "base/World Boss/blaze", "reindeer_spear"),
    ("solo/ring_of_cycles/World Boss/blaze", "base/World Boss/blaze", "ring_of_cycles"),
    ("solo/hexagon_necklace/World Boss/blaze", "base/World Boss/blaze", "hexagon_necklace"),
    ("WB/reindeer/defpen99/blaze", "WB/base/defpen99/blaze", "reindeer_spear@defpen99"),
    ("AW/star5/World Boss/blaze", "base/World Boss/blaze", "arwens_glass_shoes@star5"),
]

# Arwen's Glass Shoes equivalence: (case with the artifact, artifact-free case whose Inputs summoning time = Inputs + artifact value, label);
# the workbook's Total DPS (and the engine's) must be IDENTICAL
EQUIV_PAIRS = [
    ("AW/star0/World Boss/blaze", "AWref/in20/World Boss/blaze", "WB blaze star0 = in20"),
    ("AW/star5/World Boss/blaze", "AWref/in40/World Boss/blaze", "WB blaze star5 = in40"),
    ("AW/star5+in5/World Boss/blaze", "AWref/in45/World Boss/blaze", "WB blaze star5+in5 = in45 (3rd-stun flip)"),
    ("AW/star5+others+in5/World Boss/blaze", "AWref/others+in45/World Boss/blaze", "WB blaze +bottle+hexagon+horn star5+in5 = in45"),
    ("AW/star0/Breakthrough/wind", "AWref/in20/Breakthrough/wind", "BT wind star0 = in20"),
    ("AW/star5/Breakthrough/wind", "AWref/in40/Breakthrough/wind", "BT wind star5 = in40"),
    ("AW/star5+in5/Breakthrough/wind", "AWref/in45/Breakthrough/wind", "BT wind star5+in5 = in45"),
    ("AW/star5+others+in5/Breakthrough/wind", "AWref/others+in45/Breakthrough/wind", "BT wind +bottle+hexagon+horn star5+in5 = in45"),
    ("AW/star0/Chapter Hunt/wind", "AWref/in20/Chapter Hunt/wind", "CH wind star0 = in20"),
    ("AW/star5/Chapter Hunt/wind", "AWref/in40/Chapter Hunt/wind", "CH wind star5 = in40"),
]

if __name__ == "__main__":
    cs = artifact_cases()
    ids = [c for c, _ in cs]
    assert len(ids) == len(set(ids))
    seen = {a["key"] for _, d in cs for a in d["artifacts"]}
    print(len(cs), "cases;", len(seen), "distinct artifacts equipped")
