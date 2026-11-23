"""Case matrix of the Shadower Sensitivity golden file (plain data: no workbook, no engine import; same structure and rules as ``sens_cases.py`` / ``paladin_sens_cases.py``).

``sens_cases()`` returns ``[case, ...]``, one case = ONE evaluation of the (Sensitivity-slimmed) Shadower workbook:

    id         unique name
    inputs     engine input dict (``shadower.compute`` shape) + ``artifact_stars`` {id: star | None} for ALL 36 artifacts + ``companion_levels`` {name: level}
    stats      stat keys whose block / table row are read from the workbook
    toggles    artifact ids whose "(Equip)" block / staging row are read
    cdr        True: the 10 CDR milestone blocks; a list: only those CDR values
    tables     True: the Companion Comparison table (+ the Summoning-Time table); needs the full Companion sheet (heavier)
    potential  {artifact id: DPS} constants written over ArtifactsInput!L (potential-line gain) - exercises the potential term of the equip rows

LEAN golden (user decision 2026-11-23: fewer evaluations than the other classes): 7 evaluations.  The test Inputs are the golden ``STATS_S``-style values below (the USER's
committed Shadower Inputs are never touched).  Shadower shape: Lv140 (every passive / buff of the kit is unlocked: Dagger Expert 120, Shadower Instinct 125, Shadow Shifter 115,
Smokescreen 110; Lv200 would cap the 4th-job skill level at 300), the player's own Phase Dash stun (Lv63) is always on, Blaze Wizard Lv10 as the companion (a stun), stat set S
has a non-zero value everywhere (DEX, Incoming Hit Rate, the five skill-level bonuses, a Cooldown Decrease, Buff Duration).  One Lv118 Chapter Hunt case exercises the passive
unlock gating: Dagger Expert (120) and Shadower Instinct (125) locked, Shadow Shifter (115) on.  All 29 stats are read (the strip-rebuild stats in World Boss AND Enhancement
Dungeon), 16 artifact equip toggles (of the 29 with a DPS effect), a CDR subset, both companion tables and the Summoning Time 12.9 candidate flip.

The CHAIN ``I/WB140/0..3`` (World Boss; state k has the first k chain artifacts equipped with their baked-in stats typed into the Inputs; the toggle row of artifact k read in
the state without it (adding) and in the state with it (removing) must give the identical gain and % Gain, equal to Summary Total(with) - Total(without) - CLAUDE.md item 15 /
checklist 8c, in BOTH directions): Shamaness Marble (+12 Buff Duration Increase), Athena's Gloves (+14.4 Attack Speed AND +45% of the total Attack Speed as Max Damage),
Reindeer's Spear (its 8% base Def Pen combined by diminishing returns) - the three rows the Dark Knight port found broken, two of them (Shamaness, Athena) were broken here too.
Bottle of Emotion and Cursed Doll (typed Final Damage, a factor on the artifact bucket here) are read adding in state 3 and removing in the Enhancement Dungeon case (slot
equipped, nothing typed: engine == workbook); their toggled-copy equality is an engine-only test (``test_toggle_direction_invariance``) for the other direction, since a fifth
state per artifact is not part of the lean budget.
"""
from shadower_cases import make_inputs
from sens_cases import COMPANION_NAMES, case_builder

STATS_S = dict(
    flat_attack=250000, attack_pct=1800, defense=12000, crit_rate=60, crit_damage=150, attack_speed=20, flat_luk=5000, luk_pct=40, dex=800,
    damage=30, damage_amp=20, basic_attack_damage=15, skill_damage=20, def_pen=35, boss_damage=40, normal_damage=25, status_effect_damage=30,
    min_damage=80, max_damage=130, final_damage=12, skill_lvl_1st=3, skill_lvl_2nd=5, skill_lvl_3rd=10, skill_lvl_4th=15, skill_lvl_all=20,
    skill_cooldown_decrease=1, basic_attack_target_increase=2, buff_duration_increase_pct=15, companion_summon_time_increase_pct=0,
    boss_normal_weight_choice="A Little More Normal", max_enemies_hit=999, pvp_fight_length=15, incoming_hit_rate=2.5,
)

ALL_STATS = ["flat_luk", "luk_pct", "dex", "damage", "damage_amp", "boss_damage", "normal_damage", "status_effect_damage", "final_damage", "min_damage", "max_damage",
             "crit_rate", "crit_damage", "attack_speed", "def_pen", "basic_attack_damage", "skill_damage", "skill_lvl_1st", "skill_lvl_2nd", "skill_lvl_3rd",
             "skill_lvl_4th", "skill_lvl_all", "flat_attack", "attack_pct", "skill_cooldown_decrease", "basic_attack_target_increase", "buff_duration_increase_pct",
             "companion_summon_time_increase_pct", "incoming_hit_rate"]
assert len(ALL_STATS) == 29

# the baked-in artifact values at the stars of ``sens_cases.STARS`` (checked against the artifact tables by test_shadower_sensitivity.test_baked_values)
SHAMANESS_BDI = 12.0            # star 5
ATHENA_AS, ATHENA_MAX_PCT = 14.4, 45.0      # star 4: direct Attack Speed, Max Damage = 45% of the total Attack Speed
REINDEER_DEF_PEN = 8.0          # star 3
CURSED_DOLL_FD = 14.0           # star 5
BOTTLE_PER_3PCT, BOTTLE_CAP = 1.0, 20.0     # star 5: Final Damage +1% per 3% Attack Speed over 60, capped at 20%
BOOTS_SUMMON_LINES_PCT = 12.0     # the Companion Summoning Time lines on the committed workbook's PotentialCubes sheet (row 'boots' / Potential)
CHAIN_AS = 100.0                # the typed Attack Speed of the chain states (Bottle's Final Damage is non-zero from 60 up)


case = case_builder(make_inputs)


def chain_over(sham=False, athena=False, reindeer=False):
    """Inputs overrides of a chain state: the baked-in stats of the equipped chain artifacts typed in (base: Buff Duration 15, Max Damage 130, Def Pen 35)."""
    as_total = CHAIN_AS + (ATHENA_AS if athena else 0.0)
    return dict(attack_speed=as_total,
                buff_duration_increase_pct=15.0 + (SHAMANESS_BDI if sham else 0.0),
                max_damage=130.0 + (ATHENA_MAX_PCT / 100 * as_total if athena else 0.0),
                def_pen=100 * (1 - (1 - 35.0 / 100) * (1 - REINDEER_DEF_PEN / 100)) if reindeer else 35.0)


# chain states: (id suffix, equipped artifacts, typed flags)
CHAIN = [
    ("0", [], {}),
    ("1", ["shamaness_marble"], dict(sham=True)),
    ("2", ["shamaness_marble", "athena_gloves"], dict(sham=True, athena=True)),
    ("3", ["shamaness_marble", "athena_gloves", "reindeer_spear"], dict(sham=True, athena=True, reindeer=True)),
]
# (artifact, state adding it, state removing it)
CHAIN_PAIRS = [("shamaness_marble", "0", "1"), ("athena_gloves", "1", "2"), ("reindeer_spear", "2", "3")]


def sens_cases():
    cs = []
    S = STATS_S
    # ------------------------------------------------------------------------------------------------------------------ World Boss chain (timeline strip on): every stat once,
    # the baked-in artifacts in both directions, the other toggles in the adding direction (the free block slots of each state)
    extra = {
        "0": dict(toggles=["book_of_ancient", "ring_of_cycles", "hexagon_necklace"],
                  stats=["flat_luk", "dex", "skill_lvl_1st", "incoming_hit_rate", "damage", "damage_amp", "flat_attack", "attack_pct"],
                  potential={"hexagon_necklace": 2.5e12, "book_of_ancient": 1.0e12}),
        "1": dict(toggles=["arwens_glass_shoes", "candle"], stats=["skill_lvl_2nd", "skill_lvl_3rd", "buff_duration_increase_pct", "skill_cooldown_decrease"]),
        "2": dict(toggles=["star_rock", "charm_of_the_undead"], stats=["attack_speed", "crit_rate", "skill_lvl_4th", "final_damage"]),
        "3": dict(toggles=["lit_lamp", "bottle_of_emotion", "cursed_doll"], stats=["def_pen", "skill_lvl_all", "skill_damage", "boss_damage"]),
    }
    for suffix, equipped, flags in CHAIN:
        chain_toggles = [a for a, add, rem in CHAIN_PAIRS if suffix in (add, rem)]
        e = extra[suffix]
        cs.append(case(f"I/WB140/{suffix}", "World Boss", 140, S, "blaze", equipped, over=dict(chain_over(**flags)),
                       toggles=chain_toggles + e["toggles"], stats=e["stats"], potential=e.get("potential", {})))
    # ------------------------------------------------------------------------------------------------------------------ Enhancement Dungeon (KO strip): strip-fed stats again;
    # Bottle of Emotion / Cursed Doll / Clear Spring Water equipped (nothing typed): their rows in the REMOVING direction (engine == workbook)
    cs.append(case("S/ED140", "Enhancement Dungeon", 140, S, "blaze", ["ring_of_cycles", "clear_spring_water", "bottle_of_emotion", "cursed_doll"],
                   stats=["skill_lvl_2nd", "skill_lvl_4th", "skill_damage", "boss_damage", "crit_damage", "basic_attack_damage"],
                   toggles=["clear_spring_water", "bottle_of_emotion", "cursed_doll"]))
    # ------------------------------------------------------------------------------------------------------------------ Breakthrough: both companion tables, Summoning Time 12.9
    # (the summon-time candidate flips: pinned blocks must keep the main sheet's choice); Phase Dash's stun lengthens the boss phase
    levels = {n: (10, 7, 5, 1, 0)[i % 5] for i, n in enumerate(COMPANION_NAMES)}
    # (the committed workbook's PotentialCubes sheet - the user's data, kept as it is in the scratch copy - lists a boots line "Companion Summoning Time Increase % 12": the
    # Summoning-Time table's b0 = Inputs value - those lines = 0.9, which is the engine input ``companion_potential_lines_pct`` = 12 (``test_potential_lines_are_the_workbooks``))
    cs.append(case("S/BT140", "Breakthrough", 140, S, "blaze", ["hexagon_necklace", "bottle_of_emotion"],
                   over=dict(companion_summon_time_increase_pct=12.9, companion_potential_lines_pct=BOOTS_SUMMON_LINES_PCT),
                   tables=True, companion_levels=levels,
                   stats=["companion_summon_time_increase_pct", "status_effect_damage", "skill_cooldown_decrease"], toggles=["horn_flute"]))
    # ------------------------------------------------------------------------------------------------------------------ Chapter Hunt Lv118: Soul Contract (reaches every cooldown),
    # a CDR subset, passive unlock gating (Dagger Expert 120 / Shadower Instinct 125 locked, Shadow Shifter 115 on)
    cs.append(case("S/CH118", "Chapter Hunt", 118, S, "blaze", ["bottle_of_emotion", "soul_contract", "book_of_ancient"],
                   cdr=[1.0, 3.5, 5.0], toggles=["soul_contract"],
                   stats=["skill_lvl_all", "normal_damage", "basic_attack_target_increase", "luk_pct", "min_damage", "max_damage"]))
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
