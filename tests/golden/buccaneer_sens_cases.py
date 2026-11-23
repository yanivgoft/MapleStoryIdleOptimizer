"""Case matrix of the Buccaneer Sensitivity golden file (plain data: no workbook, no engine import; same structure and rules as ``sens_cases.py`` / ``hero_sens_cases.py``).

``sens_cases()`` returns ``[case, ...]``, one case = ONE evaluation of the (Sensitivity-slimmed) Buccaneer workbook:

    id         unique name
    inputs     engine input dict (``buccaneer.compute`` shape) + ``artifact_stars`` {id: star | None} for ALL 36 artifacts + ``companion_levels`` {name: level}
    stats      stat keys whose block / table row are read from the workbook
    toggles    artifact ids whose "(Equip)" block / staging row are read
    cdr        True: the 10 CDR milestone blocks; a list: only those CDR values (<= 5 per evaluation, memory)
    tables     True: the Companion Comparison table (+ the Summoning-Time table); needs the full Companion sheet (heavier)
    potential  {artifact id: DPS} constants written over ArtifactsInput!L (potential-line gain) - exercises the potential term of the equip rows

12 evaluations, every case lists only what is compared (<= 8 blocks); the rest of the Sensitivity sheet is deleted from the scratch copy.  Buccaneer shape: Lv140 (every
passive / buff of the kit is unlocked; Lv200 would cap the 4th-job skill level at 300; one Lv74 case exercises the passive unlock gating: Groggy Mastery (75) locked, Greater
Sea Serpent I (72) just unlocked), the player's own Corkscrew Blow stun is always on, Blaze Wizard Lv10 as the companion (a stun), stat set S has a non-zero value everywhere (DEX,
the five skill-level bonuses, a Cooldown Decrease, Buff Duration).  Every one of the 28 stats is read (the strip-rebuild stats in World Boss AND Enhancement Dungeon), 27 artifact
equip toggles.

The CHAIN ``I/WB140/*`` (state k has the first k artifacts equipped with their baked-in stats typed into the Inputs; the toggle row of artifact k read in state k-1 (adding) and in
state k (removing) must give the identical gain and % Gain, equal to Summary Total(k) - Total(k-1) - CLAUDE.md item 15 / checklist 8c, in BOTH directions, for every baked-in
artifact whose block-wiring was fixed or checked in the Buccaneer port):  Shamaness Marble (+12 Buff Duration Increase), Athena's Gloves (+14.4 Attack Speed AND +45% of the total
Attack Speed as Max Damage), Reindeer's Spear (its 8% base Def Pen combined by diminishing returns), then either Cursed Doll (+14% Final Damage, multiplied into the typed value) or
Bottle of Emotion (+1% Final Damage per 3% Attack Speed over 60, cap 20; the typed Attack Speed incl. Athena's direct bonus).  Only 4 slots exist, hence the branch S3 -> S3b / S4.
"""
from buccaneer_cases import make_inputs
from sens_cases import COMPANION_NAMES, case_builder, fd_typed

STATS_S = dict(
    flat_attack=250000, attack_pct=1800, defense=12000, crit_rate=60, crit_damage=150, attack_speed=20, flat_str=5000, str_pct=40, dex=800,
    damage=30, damage_amp=20, basic_attack_damage=15, skill_damage=20, def_pen=35, boss_damage=40, normal_damage=25, status_effect_damage=30,
    min_damage=80, max_damage=130, final_damage=12, skill_lvl_1st=3, skill_lvl_2nd=5, skill_lvl_3rd=10, skill_lvl_4th=15, skill_lvl_all=20,
    skill_cooldown_decrease=1, basic_attack_target_increase=2, buff_duration_increase_pct=15, companion_summon_time_increase_pct=0,
    boss_normal_weight_choice="A Little More Normal", max_enemies_hit=999, pvp_fight_length=15,
)

ALL_STATS = ["flat_str", "str_pct", "dex", "damage", "damage_amp", "boss_damage", "normal_damage", "status_effect_damage", "final_damage", "min_damage", "max_damage",
             "crit_rate", "crit_damage", "attack_speed", "def_pen", "basic_attack_damage", "skill_damage", "skill_lvl_1st", "skill_lvl_2nd", "skill_lvl_3rd",
             "skill_lvl_4th", "skill_lvl_all", "flat_attack", "attack_pct", "skill_cooldown_decrease", "basic_attack_target_increase", "buff_duration_increase_pct",
             "companion_summon_time_increase_pct"]
assert len(ALL_STATS) == 28

# the baked-in artifact values at the stars of ``sens_cases.STARS`` (checked against the artifact tables by sens_extras/buccaneer.py::test_baked_values)
SHAMANESS_BDI = 12.0            # star 5
ATHENA_AS, ATHENA_MAX_PCT = 14.4, 45.0      # star 4: direct Attack Speed, Max Damage = 45% of the total Attack Speed
REINDEER_DEF_PEN = 8.0          # star 3
CURSED_DOLL_FD = 14.0           # star 5
BOTTLE_PER_3PCT, BOTTLE_CAP = 1.0, 20.0     # star 5: Final Damage +1% per 3% Attack Speed over 60, capped at 20%
CHAIN_AS = 100.0                # the typed Attack Speed of the chain states (Bottle's Final Damage is non-zero from 60 up)


case = case_builder(make_inputs)


def chain_over(sham=False, athena=False, reindeer=False, doll=False, bottle=False):
    """Inputs overrides of a chain state: the baked-in stats of the equipped chain artifacts typed in (base: Buff Duration 15, Max Damage 130, Def Pen 35, Final Damage 12)."""
    as_total = CHAIN_AS + (ATHENA_AS if athena else 0.0)
    fds = []
    if doll:
        fds.append(CURSED_DOLL_FD)
    if bottle:
        fds.append(min(BOTTLE_CAP, max(0.0, BOTTLE_PER_3PCT / 3 * (as_total - 60))))
    return dict(attack_speed=as_total,
                buff_duration_increase_pct=15.0 + (SHAMANESS_BDI if sham else 0.0),
                max_damage=130.0 + (ATHENA_MAX_PCT / 100 * as_total if athena else 0.0),
                def_pen=100 * (1 - (1 - 35.0 / 100) * (1 - REINDEER_DEF_PEN / 100)) if reindeer else 35.0,
                final_damage=fd_typed(12.0, *fds))


# chain states: (id suffix, equipped artifacts, typed flags)
CHAIN = [
    ("0", [], {}),
    ("1", ["shamaness_marble"], dict(sham=True)),
    ("2", ["shamaness_marble", "athena_gloves"], dict(sham=True, athena=True)),
    ("3", ["shamaness_marble", "athena_gloves", "reindeer_spear"], dict(sham=True, athena=True, reindeer=True)),
    ("3b", ["shamaness_marble", "athena_gloves", "reindeer_spear", "bottle_of_emotion"], dict(sham=True, athena=True, reindeer=True, bottle=True)),
    ("4", ["shamaness_marble", "athena_gloves", "reindeer_spear", "cursed_doll"], dict(sham=True, athena=True, reindeer=True, doll=True)),
]
# (artifact, state adding it, state removing it)
CHAIN_PAIRS = [("shamaness_marble", "0", "1"), ("athena_gloves", "1", "2"), ("reindeer_spear", "2", "3"), ("bottle_of_emotion", "3", "3b"), ("cursed_doll", "3", "4")]


def sens_cases():
    cs = []
    S = STATS_S
    BB = ["bottle_of_emotion", "reindeer_spear"]
    # ------------------------------------------------------------------------------------------------------------------ World Boss chain (timeline strip on): every stat once,
    # the baked-in artifacts in both directions, the other toggles in the adding direction (the free block slots of each state)
    extra = {
        "0": dict(toggles=["book_of_ancient", "ring_of_cycles", "hexagon_necklace", "horn_flute"], stats=["flat_str", "dex", "skill_lvl_1st"],
                  potential={"hexagon_necklace": 2.5e12, "book_of_ancient": 1.0e12}),
        "1": dict(toggles=["arwens_glass_shoes", "candle"], stats=["skill_lvl_2nd", "buff_duration_increase_pct", "skill_cooldown_decrease", "skill_lvl_3rd"]),
        "2": dict(toggles=["star_rock", "charm_of_the_undead"], stats=["attack_speed", "crit_rate", "skill_lvl_4th", "final_damage"]),
        "3": dict(toggles=["lit_lamp"], stats=["def_pen", "skill_lvl_all", "skill_damage", "boss_damage"]),
        "3b": dict(toggles=["contract_of_darkness", "peach_tree"], stats=["status_effect_damage", "basic_attack_damage", "min_damage", "max_damage", "str_pct"]),
        "4": dict(toggles=["rainbow_snail_shell", "silver_pendant"], stats=["damage", "damage_amp", "crit_damage", "flat_attack", "attack_pct"]),
    }
    for suffix, equipped, flags in CHAIN:
        chain_toggles = [a for a, add, rem in CHAIN_PAIRS if suffix in (add, rem)]
        e = extra[suffix]
        cs.append(case(f"I/WB140/{suffix}", "World Boss", 140, S, "blaze", equipped, over=dict(chain_over(**flags)),
                       toggles=chain_toggles + e["toggles"], stats=e["stats"], potential=e.get("potential", {})))
    # ------------------------------------------------------------------------------------------------------------------ Enhancement Dungeon (KO strip), Breakthrough, Chapter Hunt
    cs.append(case("S/ED140", "Enhancement Dungeon", 140, S, "blaze", ["ring_of_cycles", "clear_spring_water", "star_rock", "book_of_ancient"],
                   stats=["skill_lvl_1st", "skill_lvl_2nd", "skill_lvl_all", "skill_damage", "boss_damage", "crit_rate", "companion_summon_time_increase_pct"],
                   toggles=["clear_spring_water"]))
    # Summoning Time Increase 12.9: the summon-time candidate flips (pinned blocks must keep the main sheet's choice); Corkscrew Blow's stun lengthens the boss phase
    cs.append(case("S/BT140", "Breakthrough", 140, S, "blaze", ["hexagon_necklace", "bottle_of_emotion"], over=dict(companion_summon_time_increase_pct=12.9),
                   stats=["skill_cooldown_decrease", "companion_summon_time_increase_pct", "status_effect_damage", "boss_damage", "def_pen"],
                   toggles=["horn_flute", "hexagon_necklace", "arwens_glass_shoes"]))
    # Soul Contract is a Chapter Hunt effect (reaches every cooldown)
    cs.append(case("S/CH140", "Chapter Hunt", 140, S, "blaze", ["bottle_of_emotion", "soul_contract", "book_of_ancient"],
                   stats=["skill_cooldown_decrease", "buff_duration_increase_pct", "attack_speed", "crit_rate", "normal_damage", "basic_attack_target_increase",
                          "str_pct"],
                   toggles=["soul_contract"]))
    # Lv74: Groggy Mastery (75) is locked (its Final Damage delta must be skipped), Greater Sea Serpent I (72) / Serpent Assault (69) / Corkscrew Blow (63) are on, the rest of the kit
    # (Octopunch 103, Crossbones 115, Speed Infusion 107, Time Leap 125) is locked
    cs.append(case("S/CH74", "Chapter Hunt", 74, S, "blaze", ["bottle_of_emotion", "reindeer_spear"],
                   stats=["skill_lvl_1st", "skill_lvl_3rd", "skill_lvl_all", "final_damage", "attack_speed", "crit_rate", "basic_attack_damage", "flat_str"]))
    # ------------------------------------------------------------------------------------------------------------------ CDR milestones, companion table
    cs.append(case("D/WB140", "World Boss", 140, S, "blaze", BB, cdr=[0.5, 1.0, 2.0, 3.5, 5.0], toggles=["secret_map", "sayrams_necklace", "old_music_box"]))
    levels = {n: (10, 7, 5, 1, 0)[i % 5] for i, n in enumerate(COMPANION_NAMES)}
    cs.append(case("C/BT140", "Breakthrough", 140, S, "blaze", ["hexagon_necklace", "bottle_of_emotion"], tables=True, companion_levels=levels,
                   toggles=["alliance_badge", "flaming_lava", "chalice", "fire_flower"]))
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
    print("blocks per case:", {c["id"]: n(c) for c in cs})
