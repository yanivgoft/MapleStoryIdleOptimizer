"""Case matrix of the Night Lord Sensitivity golden file (plain data: no workbook, no engine import; same structure and rules as ``sens_cases.py`` / ``corsair_sens_cases.py``).

``sens_cases()`` returns ``[case, ...]``, one case = ONE evaluation of the (Sensitivity-slimmed) Night Lord workbook:

    id         unique name
    inputs     engine input dict (``night_lord.compute`` shape) + ``artifact_stars`` {id: star | None} for ALL 36 artifacts + ``companion_levels`` {name: level}
    stats      stat keys whose block / table row are read from the workbook
    toggles    artifact ids whose "(Equip)" block / staging row are read
    cdr        True: the 10 CDR milestone blocks; a list: only those CDR values (<= 5 per evaluation, memory)
    tables     True: the Companion Comparison table (+ the Summoning-Time table); needs the full Companion sheet (heavier)
    potential  {artifact id: DPS} constants written over ArtifactsInput!L (potential-line gain) - exercises the potential term of the equip rows

LEAN golden (user budget decision 2026-11-23): 10 evaluations, every case lists only what is compared (<= ~9 blocks); the rest of the Sensitivity sheet is deleted from the
scratch copy.  Night Lord shape: Lv140 (every passive / buff of the kit is unlocked - Claw Expert 120, Dark Harmony 125, Shadow Shifter 115, Frailty Curse 110, Toxic Venom 117;
Lv200 would cap the 4th-job skill level at 300), Gust Charm (Lv35) is the player's own stun, always on, Blaze Wizard Lv10 as the companion (a second stun), stat set S has a
non-zero value everywhere (DEX, the five skill-level bonuses, a Cooldown Decrease, Buff Duration, Incoming Hit Rate).  One Lv118 Chapter Hunt case exercises the passive unlock
gating (Claw Expert 120 and Dark Harmony 125 locked, Shadow Shifter 115 / Critical Throw / Enveloping Darkness / Expert Throwing Star Handling unlocked).  Every one of the 29
stats is read (the strip-rebuild stats in World Boss AND Enhancement Dungeon), most artifact equip toggles.

The CHAIN ``I/WB140/*`` (state k has the first k artifacts equipped with their baked-in stats typed into the Inputs; the toggle row of artifact k read in state k-1 (adding) and in
state k (removing) must give the identical gain and % Gain, equal to Summary Total(k) - Total(k-1) - CLAUDE.md item 15 / checklist 8c, in BOTH directions, for every baked-in
artifact whose block-wiring was fixed or checked in the Night Lord port):  Shamaness Marble (+12 Buff Duration Increase; the row was inert until 2026-11-23), Athena's Gloves (+14.4
Attack Speed AND +45% of the total Attack Speed as Max Damage), Reindeer's Spear (its 8% base Def Pen combined by diminishing returns), then Bottle of Emotion (+1% Final Damage per 3%
Attack Speed over 60, cap 20; the typed Attack Speed incl. Athena's direct bonus) and Cursed Doll (+14% Final Damage, multiplied into the typed value).  Only 4 slots exist, hence
the branch S3 -> S3b / S4.
"""
from night_lord_cases import make_inputs
from sens_cases import COMPANION_NAMES, case_builder, fd_typed

STATS_S = dict(
    flat_attack=250000, attack_pct=1800, defense=12000, crit_rate=60, crit_damage=150, attack_speed=20, flat_luk=5000, luk_pct=40, dex=800,
    damage=30, damage_amp=20, basic_attack_damage=15, skill_damage=20, def_pen=35, boss_damage=40, normal_damage=25, status_effect_damage=30,
    min_damage=80, max_damage=130, final_damage=12, skill_lvl_1st=3, skill_lvl_2nd=5, skill_lvl_3rd=10, skill_lvl_4th=15, skill_lvl_all=20,
    skill_cooldown_decrease=1, basic_attack_target_increase=2, buff_duration_increase_pct=15, companion_summon_time_increase_pct=0,
    boss_normal_weight_choice="A Little More Normal", max_enemies_hit=999, incoming_hit_rate=1.5, pvp_fight_length=15,
)

ALL_STATS = ["flat_luk", "luk_pct", "dex", "damage", "damage_amp", "boss_damage", "normal_damage", "status_effect_damage", "final_damage", "min_damage", "max_damage",
             "crit_rate", "crit_damage", "attack_speed", "def_pen", "basic_attack_damage", "skill_damage", "skill_lvl_1st", "skill_lvl_2nd", "skill_lvl_3rd",
             "skill_lvl_4th", "skill_lvl_all", "flat_attack", "attack_pct", "skill_cooldown_decrease", "basic_attack_target_increase", "buff_duration_increase_pct",
             "companion_summon_time_increase_pct", "incoming_hit_rate"]
assert len(ALL_STATS) == 29

# the baked-in artifact values at the stars of ``sens_cases.STARS`` (checked against the artifact tables by test_night_lord_sensitivity.test_baked_values)
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
    # ------------------------------------------------------------------------------------------------------------------ World Boss chain (timeline strip on): every stat once,
    # the baked-in artifacts in both directions, the other toggles in the adding direction (the free block slots of each state)
    extra = {
        "0": dict(toggles=["book_of_ancient", "ring_of_cycles", "hexagon_necklace"], stats=["flat_luk", "dex", "skill_lvl_1st", "incoming_hit_rate"],
                  potential={"hexagon_necklace": 2.5e14, "book_of_ancient": 1.0e14}),
        "1": dict(toggles=["arwens_glass_shoes"], stats=["skill_lvl_2nd", "buff_duration_increase_pct", "skill_cooldown_decrease", "skill_lvl_3rd"]),
        "2": dict(toggles=["horn_flute", "charm_of_the_undead"], stats=["attack_speed", "crit_rate", "skill_lvl_4th", "final_damage"]),
        "3": dict(toggles=["cursed_doll"], stats=["def_pen", "skill_lvl_all", "skill_damage", "boss_damage"]),
        "3b": dict(toggles=["star_rock", "candle"], stats=["status_effect_damage", "basic_attack_damage", "min_damage", "max_damage", "luk_pct"]),
        "4": dict(toggles=["lit_lamp", "peach_tree"], stats=["damage", "damage_amp", "crit_damage", "flat_attack", "attack_pct"]),
    }
    for suffix, equipped, flags in CHAIN:
        chain_toggles = [a for a, add, rem in CHAIN_PAIRS if suffix in (add, rem)]
        e = extra[suffix]
        tog = chain_toggles + [t for t in e["toggles"] if t not in chain_toggles]
        cs.append(case(f"I/WB140/{suffix}", "World Boss", 140, S, "blaze", equipped, over=dict(chain_over(**flags)),
                       toggles=tog, stats=e["stats"], potential=e.get("potential", {})))
    # ------------------------------------------------------------------------------------------------------------------ Enhancement Dungeon (KO strip), Breakthrough, Chapter Hunt
    cs.append(case("S/ED140", "Enhancement Dungeon", 140, S, "blaze", ["ring_of_cycles", "clear_spring_water", "star_rock", "book_of_ancient"],
                   stats=["skill_lvl_1st", "skill_lvl_3rd", "skill_damage", "boss_damage", "crit_rate", "companion_summon_time_increase_pct", "status_effect_damage"],
                   toggles=["clear_spring_water"]))
    # Summoning Time Increase 12.9: the summon-time candidate flips (pinned blocks must keep the main sheet's choice); Gust Charm's / Blaze Wizard's stun lengthens the boss phase;
    # the Companion Comparison + Summoning-Time tables
    levels = {n: (10, 7, 5, 1, 0)[i % 5] for i, n in enumerate(COMPANION_NAMES)}
    cs.append(case("S/BT140", "Breakthrough", 140, S, "blaze", ["hexagon_necklace", "bottle_of_emotion"], over=dict(companion_summon_time_increase_pct=12.9),
                   stats=["skill_cooldown_decrease", "companion_summon_time_increase_pct", "boss_damage", "def_pen"],
                   toggles=["horn_flute", "hexagon_necklace", "arwens_glass_shoes"]))
    # the tables on their own (the first version put them next to 8 blocks: 10.5 GB, over the 8 GB budget)
    cs.append(case("C/BT140", "Breakthrough", 140, S, "blaze", ["hexagon_necklace", "bottle_of_emotion"], over=dict(companion_summon_time_increase_pct=12.9),
                   toggles=["alliance_badge"], tables=True, companion_levels=levels))
    # Soul Contract is a Chapter Hunt effect (reaches every cooldown); Lv118: Claw Expert (120) and Dark Harmony (125) are locked (their deltas must be skipped), Shadow Shifter (115),
    # Critical Throw (45), Enveloping Darkness (72) and Expert Throwing Star Handling (75) are unlocked; a CDR subset
    cs.append(case("S/CH118", "Chapter Hunt", 118, S, "blaze", ["bottle_of_emotion", "soul_contract", "book_of_ancient"],
                   stats=["skill_cooldown_decrease", "skill_lvl_4th", "skill_lvl_all", "attack_speed", "normal_damage", "basic_attack_target_increase"],
                   toggles=["soul_contract", "contract_of_darkness"], cdr=[0.5, 2.0, 5.0]))
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
