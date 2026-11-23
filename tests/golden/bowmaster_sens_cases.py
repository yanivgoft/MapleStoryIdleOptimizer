"""Case matrix of the Bowmaster Sensitivity golden file (plain data: no workbook, no engine import; same structure and rules as ``marksman_sens_cases.py`` / ``hero_sens_cases.py``).

``sens_cases()`` returns ``[case, ...]``, one case = ONE evaluation of the (Sensitivity-slimmed) Bowmaster workbook:

    id         unique name
    inputs     engine input dict (``bowmaster.compute`` shape) + ``artifact_stars`` {id: star | None} for ALL 36 artifacts + ``companion_levels`` {name: level}
    stats      stat keys whose block / table row are read from the workbook
    toggles    artifact ids whose "(Equip)" block / staging row are read
    cdr        True: the 10 CDR milestone blocks; a list: only those CDR values (<= 5 per evaluation, memory)
    tables     True: the Companion Comparison table (+ the Summoning-Time table); needs the full Companion sheet (heavier)
    potential  {artifact id: DPS} constants written over ArtifactsInput!L (potential-line gain) - exercises the potential term of the equip rows

12 evaluations, every case lists only what is compared (<= 8 blocks); the rest of the Sensitivity sheet is deleted from the scratch copy.  Bowmaster shape: Lv140 (every passive of the
kit unlocked: Armor Break 125, Bow Expert 120, Sharp Eyes 115, Illusion Step 117 + its Lv118 boost; Lv200 would cap the 4th-job skill level at 300; one Lv118 case exercises the
passive unlock gating: Bow Expert 120 and Armor Break 125 locked, Illusion Step's x1.375 boost live), the player's own Covering Fire stun is on (engine on in the fixed-length contents),
Blaze Wizard Lv10 as the companion, stat set S has a non-zero value everywhere (STR, the five skill-level bonuses, a Cooldown Decrease, Buff Duration, Attack Speed 70 so the Bottle of
Emotion's Attack-Speed Final Damage is live).

The four baked-in what-ifs the Dark Knight audit found wrong or tricky (Cursed Doll's typed Final Damage inside the Mortal Blow bracket, Athena's Gloves' Actions Per Second, Shamaness
Marble's Buff Duration, Reindeer's Spear's Def Pen in the rows) are checked as a CHAIN of World Boss states ``T/WB140/a`` -> ``doll`` -> ``ath`` -> ``sham`` -> ``rei``: each state
adds ONE more artifact (equipped AND its stat typed into the Inputs) to the previous one (no other artifact: the workbook has 4 slots), and reads the REMOVING row of the artifact it just added plus the ADDING row of the next
one - so Total(state n) - Total(state n-1) is the true delta of both rows, from both directions.  The stat sweeps ride along in those states (the later states carry the earlier artifacts'
dependent terms: Athena's Max Damage under an Attack Speed sweep, ...).  Every one of the 28 stats is read once (the strip-rebuild stats in World Boss AND Enhancement Dungeon); 28 of
the 29 artifacts with a DPS effect have a toggle read (Soul Pouch is PvP only: not covered).
"""
from bowmaster_cases import make_inputs
from sens_cases import COMPANION_NAMES, STARS, case_builder

STATS_S = dict(
    flat_attack=250000, attack_pct=1800, defense=12000, crit_rate=60, crit_damage=150, attack_speed=70, flat_dex=5000, dex_pct=40, str=800,
    damage=30, damage_amp=20, basic_attack_damage=15, skill_damage=20, def_pen=35, boss_damage=40, normal_damage=25, status_effect_damage=30,
    min_damage=80, max_damage=130, final_damage=12, skill_lvl_1st=3, skill_lvl_2nd=5, skill_lvl_3rd=10, skill_lvl_4th=15, skill_lvl_all=20,
    skill_cooldown_decrease=1, basic_attack_target_increase=2, buff_duration_increase_pct=15, companion_summon_time_increase_pct=0,
    boss_normal_weight_choice="A Little More Normal", max_enemies_hit=999, pvp_fight_length=15,
)

ALL_STATS = ["flat_dex", "dex_pct", "str", "damage", "damage_amp", "boss_damage", "normal_damage", "status_effect_damage", "final_damage", "min_damage", "max_damage",
             "crit_rate", "crit_damage", "attack_speed", "def_pen", "basic_attack_damage", "skill_damage", "skill_lvl_1st", "skill_lvl_2nd", "skill_lvl_3rd",
             "skill_lvl_4th", "skill_lvl_all", "flat_attack", "attack_pct", "skill_cooldown_decrease", "basic_attack_target_increase", "buff_duration_increase_pct",
             "companion_summon_time_increase_pct"]
assert len(ALL_STATS) == 28

# baked-in artifact magnitudes at the STARS of sens_cases (checked against the artifact table by sens_extras/bowmaster.py::test_constants)
CURSED_DOLL_FD = 14.0           # star 5
ATHENA_AS, ATHENA_MAX_PCT = 14.4, 45.0      # star 4: direct Attack Speed, Max Damage % of the total Attack Speed
SHAMANESS_BDI = 12.0            # star 5
REINDEER_DEF_PEN = 8.0          # star 3
# Mortal Blow's live Final Damage at Lv140 (Lv118: the same) with STATS_S: it shares the Final Damage bracket (1 + (typed + Mortal Blow)/100) with the typed Inputs value
# (checked against the engine by sens_extras/bowmaster.py::test_constants)
MORTAL_BLOW = 17.4


def slots(keys):
    assert len(keys) <= 4, keys          # the workbook (and the engine) have 4 artifact slots: a 5th would be silently dropped by the workbook copy
    return [{"key": k, "star": STARS[k]} for k in keys]


case = case_builder(make_inputs, slots)


def fd_typed(base, *xs):
    """Inputs!final_damage after baked-in Final Damage artifacts of x % each were typed in: the bracket ``1 + (typed + Mortal Blow)/100`` grows by the factor
    ``1 + x/100`` of each artifact (what the workbook's block does to the whole product)."""
    m = 1 + (base + MORTAL_BLOW) / 100
    for x in xs:
        m *= 1 + x / 100
    return (m - 1) * 100 - MORTAL_BLOW


def sens_cases():
    cs = []
    S = STATS_S
    BB = ["bottle_of_emotion", "reindeer_spear"]
    ART4 = ["book_of_ancient", "athena_gloves", "bottle_of_emotion", "ring_of_cycles"]
    fd1 = fd_typed(12.0, CURSED_DOLL_FD)
    as2 = S["attack_speed"] + ATHENA_AS
    md2 = S["max_damage"] + ATHENA_MAX_PCT / 100 * as2
    bdi3 = S["buff_duration_increase_pct"] + SHAMANESS_BDI
    dp4 = 100 * (1 - (1 - S["def_pen"] / 100) * (1 - REINDEER_DEF_PEN / 100))
    o1 = dict(final_damage=fd1)
    o2 = dict(o1, attack_speed=as2, max_damage=md2)
    o3 = dict(o2, buff_duration_increase_pct=bdi3)
    o4 = dict(o3, def_pen=dp4)
    # ------------------------------------------------------------------------------------------------------------------ the baked-in chain, World Boss (timeline strip on)
    cs.append(case("T/WB140/a", "World Boss", 140, S, "blaze", [],
                   toggles=["cursed_doll", "athena_gloves", "shamaness_marble", "reindeer_spear"], stats=["flat_dex", "dex_pct", "str", "damage"]))
    cs.append(case("T/WB140/doll", "World Boss", 140, S, "blaze", ["cursed_doll"], over=o1,
                   toggles=["cursed_doll", "athena_gloves"],
                   stats=["damage_amp", "boss_damage", "status_effect_damage", "def_pen", "crit_damage", "skill_damage"],
                   potential={"hexagon_necklace": 2.5e12, "cursed_doll": 1.0e12, "lunar_dew": 3.0e11, "pigs_ribbon": 5.0e11}))
    cs.append(case("T/WB140/ath", "World Boss", 140, S, "blaze", ["cursed_doll", "athena_gloves"], over=o2,
                   toggles=["athena_gloves", "shamaness_marble"],
                   stats=["attack_speed", "final_damage", "min_damage", "max_damage", "basic_attack_damage", "crit_rate"]))
    cs.append(case("T/WB140/sham", "World Boss", 140, S, "blaze", ["cursed_doll", "athena_gloves", "shamaness_marble"], over=o3,
                   toggles=["shamaness_marble", "reindeer_spear", "sayrams_necklace", "rainbow_snail_shell"],
                   stats=["flat_attack", "attack_pct", "buff_duration_increase_pct", "companion_summon_time_increase_pct"]))
    cs.append(case("T/WB140/rei", "World Boss", 140, S, "blaze", ["cursed_doll", "athena_gloves", "shamaness_marble", "reindeer_spear"], over=o4,
                   toggles=["reindeer_spear", "star_rock", "lit_lamp", "candle", "charm_of_the_undead", "old_music_box", "alliance_badge", "contract_of_darkness"]))
    # ------------------------------------------------------------------------------------------------------------------ dependent terms of Crit Rate / Attack Speed / Final Damage
    # Book of Ancient / Athena's Gloves / Ring of Cycles / Bottle equipped: their dependent terms follow Crit Rate / Attack Speed; both directions of the four toggles
    cs.append(case("S/WB140/b", "World Boss", 140, S, "blaze", ART4, stats=["crit_rate", "crit_damage", "attack_speed", "final_damage"], toggles=ART4))
    # ------------------------------------------------------------------------------------------------------------------ Enhancement Dungeon (KO strip), Breakthrough, Chapter Hunt
    cs.append(case("S/ED140", "Enhancement Dungeon", 140, S, "blaze", ["ring_of_cycles", "clear_spring_water", "star_rock"],
                   stats=["skill_lvl_2nd", "skill_lvl_3rd", "skill_lvl_4th", "skill_lvl_all", "skill_damage", "boss_damage", "crit_rate"],
                   toggles=["clear_spring_water"]))
    cs.append(case("S/BT140/a", "Breakthrough", 140, S, "blaze", BB,
                   stats=["boss_damage", "normal_damage", "status_effect_damage", "crit_rate", "attack_speed", "final_damage"], toggles=["chalice", "secret_map"]))
    # Summoning Time Increase 12.9: the summon-time candidate flips (pinned blocks must keep the main sheet's choice)
    cs.append(case("S/BT140/b", "Breakthrough", 140, S, "blaze", ["hexagon_necklace", "bottle_of_emotion"], over=dict(companion_summon_time_increase_pct=12.9),
                   stats=["skill_cooldown_decrease", "buff_duration_increase_pct", "companion_summon_time_increase_pct", "def_pen"],
                   toggles=["horn_flute", "hexagon_necklace", "arwens_glass_shoes", "peach_tree"]))
    # Lv118: Bow Expert (120) and Armor Break (125) are locked (the passive deltas skip them), Illusion Step's Lv118 boost is live; Soul Contract is a Chapter Hunt effect
    cs.append(case("S/CH118", "Chapter Hunt", 118, S, "blaze", ["bottle_of_emotion", "soul_contract", "book_of_ancient"],
                   stats=["skill_lvl_1st", "skill_lvl_all", "skill_lvl_4th", "normal_damage", "basic_attack_target_increase", "skill_cooldown_decrease"],
                   toggles=["soul_contract", "fire_flower"]))
    # ------------------------------------------------------------------------------------------------------------------ CDR milestones + companion tables (two evaluations: memory)
    levels = {n: (10, 7, 5, 1, 0)[i % 5] for i, n in enumerate(COMPANION_NAMES)}
    cs.append(case("D/BT140/tables", "Breakthrough", 140, S, "blaze", ["hexagon_necklace", "bottle_of_emotion"], tables=True, companion_levels=levels))
    cs.append(case("D/BT140/cdr", "Breakthrough", 140, S, "blaze", ["hexagon_necklace", "bottle_of_emotion"], cdr=[0.5, 1.0, 2.0, 3.5, 5.0],
                   toggles=["silver_pendant", "flaming_lava", "icy_soul_rock"]))
    return cs


if __name__ == "__main__":
    cs = sens_cases()
    ids = [c["id"] for c in cs]
    assert len(ids) == len(set(ids))
    stats = {s for c in cs for s in c["stats"]}
    tog = {a for c in cs for a in c["toggles"]}
    n = lambda c: len(c["stats"]) + len(c["toggles"]) + (len(c["cdr"]) if isinstance(c["cdr"], list) else (10 if c["cdr"] else 0))  # noqa: E731
    print(len(cs), "cases;", len(stats), "stats;", len(tog), "toggles;", sum(n(c) for c in cs), "blocks; max per case", max(n(c) for c in cs))
    missing = set(ALL_STATS) - stats
    print("stats not covered:", sorted(missing))
    from sens_cases import ALL_ARTIFACTS
    print("toggles not covered:", sorted(set(ALL_ARTIFACTS) - tog))
