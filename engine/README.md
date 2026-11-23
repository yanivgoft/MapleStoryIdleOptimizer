# engine/ - the plain-Python DPS engine

Pure standard-library Python (no openpyxl / formulas / numpy anywhere in this package).  It is the calculation source for the web app; the
Excel workbooks and their builders stay maintained alongside it.

```
engine/
  __init__.py        CLASSES = ("fp_mage",)
  _src.py            path shim: puts the repo's src/ on sys.path so the already-pure shared modules
                     companion_kits, companion_python_model, status_timeline are imported (not copied) from src/
  common/            class-agnostic pieces extracted from the verify scripts
    content.py       content types, monster type / defense / fight duration / boss-normal weight, chapter-stage parsing,
                     Breakthrough stage index, KO windows, per-content applicability of inputs  (class Content)
    factors.py       data/factor_table.json loader (json), get_factor, input_level, SkillLevels.coeff_pct, level_gated_sum
    fight.py         ticks / eff_cooldown / eff_duration / exact_casts / exact_total_hits / exact_buff_uptime (pure functions)
                     + class Fight binding them to one fight (CDR, Buff Duration, PvP length, startup delay, enemy cap)
    damage.py        defense reduction, min/max + crit expectation, actions/s, per-enemy proc roll q_roll
    blend.py         BranchLedger: boss/normal time-weighted blend (`blend`, `blend_unit`, `blend_pair`, `put`), per-row branch values, boss-only / normal-only totals
    companion.py     stub host + stun probe + choice/level normalisation around companion_python_model; `read_choice`, `stun_windows`, `horn_window`, `host_common`
    schema.py        field list (key, label, group, type, unit, default, applicability, options, computed) + default_inputs
    model.py         `Inputs` (missing / None reads as 0) + `ModelBase`, the base of every class's `_Model`: level / content / skill-level prelude (`read_content`), `unlocked`,
                     `gated`, `coeff_pct`, `timing_factors`, `branch_multipliers`, `haste`, the companion run (`begin_companion` / `run_companion`) and the whole `result()` dict
                     (a class only supplies `row_dps(key)` and `derived_extra()`)
    classapi.py      `make(...)` -> a class module's `fields` / `schema` / `defaults`, `artifact_schema`, the shared `INCOMING_HIT_RATE` field
    status.py        Status Effect / KO timeline pass 2: `build_groups`, `solve_groups`
    sens.py          (also) `COMMON_STATS` / `stat_list` and `standard_stat_to_key` that the `engine/sens_specs/<class>.py` files build their stat tables from
  artifacts.py       the 36 artifacts' EQUIP effects (ports of the artifact_*_expr generators): Pre (Attack% bucket / Hexagon / Charm, needed by the
                     timeline strip), Effects (all buckets, per-artifact rows, reference-only values, boss/normal extra multipliers),
                     time-dependent shapes (Hexagon ramp, Charm duty, Ring of Cycles uptime, Chalice, Peach/Silver Erlang ...), Horn Flute's uptime
  data/
    fp_mage.py       FP-Mage constants: skill templates, buffs, passives, unlock levels, mastery chains, status/KO spec
    artifacts.py     GENERATED copy of the builder's artifact tables (labels, ranks, star values, potential-line tables) - tests/golden/gen_artifact_data.py
  classes/
    fp_mage.py       compute(inputs), defaults(content_type), schema()
tests/run_all.py   ONE-COMMAND REGRESSION RUN (all golden jobs in parallel + api pytest in 4 processes + web vitest/tsc/xlsx-map check; ~80 s; `--changed`, `--class <id>`, `--only`; see its docstring)
tests/golden/
    cases.py         the golden input matrix (158 FP-Mage cases)
    artifact_cases.py        the 33 artifact cases (every artifact at star 5 in World Boss + Blaze Wizard Lv10, other fight shapes, stars, toggles)
    artifact_reference.py    ground truth: evaluates the WORKBOOK (stripped copy, `formulas`) per case, one evaluation at a time (~37 s, ~1.6 GB)
    fp_mage_artifacts_golden.json  frozen workbook values of those cases (+ workbook commit / sha256)
    test_artifacts.py --class fp_mage      engine vs workbook with artifacts equipped (rel 1e-9) + equip-toggle deltas; also reads the *_special.json file
    gen_artifact_data.py     regenerates / --check engine/data/artifacts.py from the builder's tables
    run_reference.py runs the ORIGINAL src/verify_fp_mage_workbook.py workbook-free (see below)
    make_golden.py   regenerates fp_mage_golden.json (one subprocess, PYTHONHASHSEED=0)
    fp_mage_golden.json   frozen numbers of the verify script
    test_fp_mage.py  engine vs golden, exact ==
    registry.py      ONE list of the 12 classes: engine module, golden files, sens spec, per-class options; run_all.py / pytest / --class all read it (`python3 tests/golden/registry.py` checks the files)
    update_goldens.py  refresh a golden from the CURRENT ENGINE after an on-purpose model change (dry run by default, --write --reason; logs to golden_refresh_log.md); test_update_goldens.py
    test_artifacts.py     ONE parametrised test for all classes (`--class <id>`, `-v`, `--rtol`; pytest id `test_artifacts_match_workbook[<id>]`); per-class options in registry.py + artifacts_extras.py
    test_sensitivity.py   ONE parametrised test for all classes (`--class <id>`, `-v`, `--rtol`, `--case`); shared tests in sens_test_common.py, class-specific ones in sens_extras/<id>.py
```

## The `compute(inputs)` contract

```python
from engine.classes import fp_mage
inputs = fp_mage.defaults("World Boss")           # workbook defaults resolved for a content type
inputs.update(level=140, flat_attack=1_209_199, companion_choice="Blaze Wizard", companion_level=10)
result = fp_mage.compute(inputs)                  # JSON-friendly dict
```

`inputs` is a flat dict: the Inputs keys of the workbook (`IN` in `build_fp_mage_workbook.py`) already resolved for the chosen content type,
plus `level`, `content_type`, `companion_choice` and `companion_level` (level of the chosen companion, 0 = not unlocked).  A key that does not
apply to the content type (see `schema()["fields"][i]["applicable"]`) is `None`; **a missing / `None` value reads as 0**, exactly like a blank
workbook cell (so Max Enemies In Range is 0 outside normal-monster content, which makes the normal-only branch 0 there).  Computed Inputs rows
(monster type, defense, fight duration, ...) are derived by the engine and returned under `derived`.

**Artifacts**: `inputs["artifacts"] = [{"key": <artifact id or workbook name>, "star": 0..5 | None}, ...]` (<= 5 equipped slots, `MAX_SLOTS`; the workbooks have 4, see "Fifth artifact slot" below; `star` None /
"Not Unlocked" reads as star 0, exactly like the workbook; `(none)` / blank slots are skipped, the same artifact twice counts once).  Absent = no
artifact (the 158-case verify-script golden is unchanged).  `schema()["artifacts"]` lists the dropdown names (+ "(none)"), star options, default
star by rank and per-artifact info (`effect`: `live` | `reference_only` | `no_dps_effect`; the explicit `no_dps_effect: bool` + `reason` flag artifacts that
genuinely have no DPS effect - stat not used by the model / raid or guild content not modelled; they are a statement of fact, not missing data).  The result's `artifacts` block reports the equipped
artifacts, the bucket totals they feed (Attack%, Final Damage, Damage, Skill/Basic Attack Damage, Crit Rate/Damage, Boss/Normal Damage, enemy
damage taken, branch-only Final Damage, Soul Contract's cooldown decrease, ...), the per-artifact rows (named like the Artifacts sheet),
`reference_only` values (artifacts whose stat the workbook expects the user to type into Inputs by hand: Book of Ancient, Athena's Gloves, Clear
Spring Water, Soul Pouch, Lit Lamp, Star Rock, Cursed Doll, Shamaness Marble, Bottle of Emotion's Final Damage, Reindeer's base Def Pen - equipping
changes nothing live), the Horn Flute uptime, the boss / normal extra multipliers and Hexagon / Charm numbers.  **Arwen's Glass Shoes is live**: it adds
Companion Summoning Time Increase % (star 0 = +20 .. star 5 = +40 in linear steps, user-confirmed 2026-11-19) to the `companion_summon_time_increase_pct`
input everywhere the companion model reads it (stun probe, Horn Flute window, companion run); reported as `artifacts.buckets.companion_summon_time_increase_pct`
and `artifacts.rows.arwens_glass_shoes_summon_time_increase_pct`.  Golden: artifact at Inputs x == no artifact at Inputs x + star value, exactly
(`tests/golden/artifact_cases.py` `EQUIV_PAIRS`, checked in the workbook and the engine by `test_artifacts.py --class fp_mage`).

**Fifth artifact slot** (2026-11-23): the game now has 5 artifact slots, so `engine/artifacts.py` `MAX_SLOTS` = 5 and every class's `schema()["artifacts"]["max_slots"]` / `resolve_slots` / the API's validation follow it (a 6th entry is
rejected: `ValueError "at most 5 artifact slots"` / API 422 `at most 5 slots`).  The 12 workbooks keep **4** slot rows on their Inputs sheet (`WORKBOOK_SLOTS` = 4; changing 12 builders is a separate task), so everything
verified against Excel (`tests/golden/test_artifacts.py --class <class>`, the sensitivity goldens, all <= 4 equipped) is bit-for-bit unchanged, and **the behaviour with 5 equipped cannot be checked against the workbooks**: it is
the engine's own composition of the verified per-artifact effects.  Nothing in an effect depends on the slot it sits in (each contributes to additive / multiplicative buckets or to a per-artifact row exactly as in the
4-slot case, the same artifact counts once), so a 5th artifact is the same step that a 4th already was.  `tests/golden/test_artifact_five_slots.py` (engine-only, ~5 s) pins that: the schema offers 5 slots in all 12 classes;
5 equipped compute without error to finite numbers in every class and fight shape tried; permuting the slots gives the same total (all 120 orders of a mixed set in FP-Mage and Hero, 1e-12); the same artifact twice
or a "(none)" slot changes nothing; adding the 5th never lowers DPS for non-negative artifacts; and the Sensitivity equip-toggle row of the 5th artifact (adding to 4 equipped) equals the engine's own 5-slot minus
4-slot total to 1e-12 (FP-Mage, Hero), as does the row of a SIXTH what-if on top of 5 equipped (the toggle builds its equipped set directly: `engine/sensitivity.py` `_toggle_sens` has no slot cap, by design).

Result: `total_dps`, `player_dps`, `boss_dps` / `normal_dps` (every row's boss-only / normal-only branch summed, companion included),
`player_boss_dps` / `player_normal_dps`, `skills` (per damage row: key, name, dps, share of total, boss_dps, normal_dps, unlocked), `companion`
(None or dps / boss_dps / normal_dps / share / damage / uplift / best_candidate / summon_time_s / window_s / details), `engine_on` (Status
Effect / KO timeline engine active) and `engine` (its cast counts and timing factors), `derived` (ATTACK, STAT_DAMAGE, actions/s, cast rate,
buff multipliers, computed Inputs rows, ...).

`schema()` describes the form: fields with key, label, group, type (`int|float|text|enum`), unit, default (+ `default_by_content` for
Chapter-Stage), `per_content` (the workbook keeps one value per content type), `applicable` (list of content types or None = all), `options`
(dropdowns), `computed`, `help`.  `defaults(content_type)` builds a ready inputs dict.

## Golden tests

```
python3 tests/golden/make_golden.py     # regenerate fp_mage_golden.json from the verify script
python3 tests/golden/test_fp_mage.py    # engine == golden, bit-exact (also pytest-collectable; --rtol 1e-12 to relax)
```

`run_reference.py` executes the verify script's own source text unchanged, up to (not including) its `import formulas` cross-check, with
`openpyxl.load_workbook` patched by a tiny fake serving exactly the cells the script reads (Inputs: row 2 content-type headers, column B for
`level` / `content_type`, the active content type's column for everything else; CompanionsInput: name in column A, level in column B).  No
workbook is opened, no `formulas` evaluation happens.  The verify script is NOT modified and remains the independent reference.  The golden
file is generated with `PYTHONHASHSEED=0` because the verify script sums Meteor Proc's trigger rates over a Python `set` (ulp-level noise
depending on the hash seed); the engine fixes that summation order (`TRIGGERS_METEOR` in `data/fp_mage.py`).

### Refreshing a golden from the engine (`tests/golden/update_goldens.py`, Excel retired)

When a model rule is changed ON PURPOSE the goldens (frozen from the verify scripts / workbooks) must move with it.  Do not hand-edit them and do not regenerate them from a workbook:

```
python3 tests/golden/update_goldens.py --class hero                  # DRY RUN: cases / values changed, max rel diff, the 10 most-changed fields (old -> new), verdict
python3 tests/golden/update_goldens.py --class hero --kind sensitivity --case "S/WB140"      # narrow it (--class all, --max-cases N, --exact, -v, --golden-dir DIR)
python3 tests/golden/update_goldens.py --class hero --write --reason "Raging Blow base 360 -> 380 (user, 2026-12-01)"     # rewrite + one line in golden_refresh_log.md
```

How: every compared leaf of a golden (`out` of the class goldens, `workbook` of the artifacts / sensitivity goldens) is loaded as a tracked float / int / str / bool that remembers its JSON path;
the class's OWN comparer (`test_<id>.py::compare`, `ArtifactsTest.compare`, `sens_compare_generic.compare_case`) runs unchanged and each `chk(name, golden, engine)` whose golden value is a tracked leaf
gives `path -> engine value`.  A value is rewritten when the comparer's own check fails (class goldens: any difference; artifacts / sensitivity: outside rel 1e-9 + the comparer's atol; `--exact`: anything
not bit-equal), the file is dumped in its own JSON format (class goldens `json.dumps`, the others `indent=0`; a no-op refresh is byte-identical) and keeps its `meta` header untouched.  Checks against a
literal or an arithmetically derived golden value (`{}` / `None` / `bool(...)` / `x or 0.0`: ~3% of all checks, all equal today) cannot be refreshed: if one differs it is reported as UNREFRESHABLE (e.g. the
timeline engine switching on for a case, ranking changes) and the exit code is 1.  **A refreshed golden pins the ENGINE's behaviour, it is no longer an independent workbook value** (the log header says so).
Tests: `tests/golden/test_update_goldens.py` (~9 s; every write goes to a temp copy via `--golden-dir`).

### Shared test harness (the per-class files are thin wrappers)

Everything the per-class golden files have in common lives in `tests/golden/`: `golden_harness.py` (`test_<class>.py`: engine vs the verify-script golden, only the class's own checks stay
in its `compare`), `artifacts_harness.py` (`test_artifacts.py --class <class>`: `ArtifactsTest(class_module, golden, boss_col, normal_col, summary_rows=...)`), `artifact_reference_common.py`
(`<class>_artifact_reference.py`: `ArtifactReference(...)`), `reference_fake.py` (the workbook-free stand-in of `run_reference_<class>.py`: `Reference(verify_script, builder).run_case(...)`),
`make_golden_common.py`, `check_fake_common.py` (`Check(...).main(pre_check=..., post_check=...)`), `sens_test_common.py` (`test_sensitivity.py --class <class>`), `case_common.py` (content types,
`make_inputs`), `artifact_cases_common.py` (the artifact matrix every class shares; a class adds its own shapes between `common_cases` and `arwen_cases`) and `sens_cases.case_builder`.
A new class is one `registry.py` entry + a ~10-line wrapper around each of the others (`sens_extras/<id>.py` holds its sensitivity-specific tests).  The command lines (`python3 tests/golden/test_<class>.py [--rtol ...]`, `--list / --case / --run-all / --assemble` of the reference scripts,
`make_golden_<class>.py`, `check_<class>_fake.py [--write]`) are unchanged.  The API side is one parametrized `api/tests/test_sensitivity_classes.py` (a row of `CLASSES` per class).

## How to add a class (the recipe used for FP-Mage)

1. Read `src/verify_<class>_workbook.py` completely and diff it against `verify_fp_mage_workbook.py`; everything identical is already in `common/`.
2. `engine/data/<class>.py`: copy the constants (skill tables, UNLOCK_LEVEL, buffs, passives, status spec, display names) as plain data.
3. `engine/classes/<class>.py`: a model class whose `_build` is the verify script top to bottom with module globals turned into attributes, the
   helpers replaced by `common` (`Content`, `Fight`, `SkillLevels`, `BranchLedger`, `damage.*`).  Keep the operation order identical, including
   dict / list iteration orders that feed float sums.  Add `schema()` (class main-stat fields) and `defaults()`.
4. `tests/golden/cases.py`: a case builder for the class; extend `run_reference.py` (verify path, fake workbook rows from that builder's `IN`).
5. Generate the golden, run the test, require bit-exact equality.

```
python3 tests/golden/test_artifacts.py --class fp_mage -v     # engine == workbook (formulas) with artifacts equipped
python3 tests/golden/gen_artifact_data.py --check      # engine/data/artifacts.py == the builder's tables
python3 tests/golden/artifact_reference.py --run-all   # (re)evaluate the workbook for every missing case, then --assemble
```

## Hero (second class; artifacts ported 2026-11-19)

Files: `engine/classes/hero.py` (`compute`, `defaults`, `schema`), `engine/data/hero.py` (plain-data constants), golden harness
`tests/golden/hero_cases.py` (252-case matrix) + `run_reference_hero.py` + `make_golden_hero.py` + `check_hero_fake.py` + `test_hero.py`,
frozen numbers in `hero_golden.json` (262 cases = the matrix + the 10 real content-type columns of `Hero/Hero-DPS-Calculator.xlsx`, stored in
`hero_real_inputs.json`).

```
python3 tests/golden/make_golden_hero.py      # regenerate hero_golden.json from src/verify_hero_workbook.py (workbook-free, one subprocess)
python3 tests/golden/test_hero.py             # engine == golden, exact ==   -> "OK: 262 golden cases match the verify script bit-exactly"
python3 tests/golden/test_artifacts.py --class hero    # engine (artifacts equipped) == the Hero workbook, rel 1e-9
python3 tests/golden/check_hero_fake.py       # streams ONLY the real Inputs / CompanionsInput cells (read_only, ~64 MB, 0.4 s, no `formulas`) through the
                                              # stand-in and checks it serves the verify script the same cells (add --write to refresh hero_real_inputs.json)
```

Hero-specific points (all taken from the verify script, numerics identical):

* Inputs: main stat = `flat_str` / `str_pct` / `dex`; everything else is the common field list.  No class-specific input beyond that.
* The basic attack is Raging Blow (5 hits, 6 from Lv136; target count `6 + increase`, no Lv136 bonus target, unlike FP-Mage), with Final Attack and
  Advanced Final Attack folded into its coefficient.  Damage rows: Puncture (+ wound DoT), Enhanced Raging Blow, Magic Crash, Beam Blade, Rush, Flash
  Slash (Maple Hero ratios on the last three).
* **Player stun**: Rush (22 s, 15.4 s from Lv90, stuns 2.5 s) is part of the Status Effect Damage / KO timeline (`PST`, `pl_stun_vector`) and in
  Breakthrough / Hero Dungeon lengthens the boss phase, so from Lv63 the companion model runs even with no companion chosen.  `result["companion"]`
  is then a dict with `choice == "None"` (only the stun uplift; `total_dps` includes it).  `status_on` = fixed duration and no normal weight and (KO
  content or any stun source).
* Spirit Blade is the only engine-timed buff; Combo Attack / Combo Synergy are constant (max stacks 5 / 7 at Lv110 / 8 at Lv118); Enrage, Scaring Sword
  and the Puncture / Magic Crash weakens stay duty-cycle averages (`monster_dmg_bonus` joins both the boss and the normal branch term).
* `def_pen_eff`: Advanced Combo (Lv130+) adds 5 / 7 / 8 stacks of +1% Defense Penetration (diminishing-returns combination), used in the hit and
  handed to the companion model.
* Blend association: Hero evaluates `(1-w) * unit * b * fb + w * unit * n * fn` left to right (timing factors NOT pre-multiplied into `b` / `n`), which
  differs by an ulp from the shared `BranchLedger.blend`; `hero._Ledger.blend_hero` reproduces it (row pairs stored as explicit per-branch DPS).
* The verify script's `stl._dp = _tie_aware_dp` monkeypatch is a pure delegation to the original `_dp` (the shared dynamic programme carries the 1e-9
  relative tie tolerance since the FP-Mage work) - a no-op, not reproduced.
* The verify script has no float sum over a `set` (PYTHONHASHSEED-independent; checked with seeds 0 / 7 / 123); the golden is still generated with seed 0.
* Latent verify-script crash: KO content (World Boss, Enhancement Dungeon) at level < 63 with no companion raises `KeyError: 'stun_vector'` (the
  companion model's early return carries no stun vector).  11 golden cases record `reference_error`; the engine reads the missing vector as "no stun"
  and the test only checks it returns a finite total there.
* **Artifacts** (`inputs["artifacts"]`, same contract and `schema()["artifacts"]` as FP-Mage, reusing `engine/artifacts.py` unchanged: the Artifacts sheet of the
  Hero and FP-Mage builders is identical, `engine/data/artifacts.py` is generated from the FP-Mage builder and the tables are equal in the Hero builder).  Hero's wiring differs
  from FP-Mage's in these places (all mirror `src/build_hero_workbook.py`): the Attack% bucket is `1 + (Combo Attack + Spirit Blade + artifact Attack%)/100` (engine on: the strip's
  `Bbuff_mean`, strip `A0 = Combo Attack + the artifact Attack% bucket without Charm`); Hexagon Damage% and Peach Tree / Silver Pendant enemy-damage-taken share ONE multiplicative
  term `(1 + (AGG_DAMAGE + AGG_ENEMY_DMG_TAKEN)/100)` (also the companion's `agg_damage_avg` and `taken_bucket`); boss / normal damage% = Inputs + mastery + the global
  damage-taken bonus (Scaring Sword / weakens) + the artifact bucket; crit totals = Inputs + Enrage Crit Damage average + artifact; Reindeer's Spear's correction uses Hero's live def pen
  (`def_pen_eff`, Advanced Combo included); Horn Flute's uptime uses the stub-host run WITH the player's Rush stun entries (`s0` / `W0`; W_0 reads 0 when no companion is chosen even
  though the stun still shifts `s0`), and the damage-weight vector's `A0` carries Combo Attack.  With no artifact every term is neutral (x1.0 / +0.0), `test_hero.py` stays bit-exact.
  Arwen's Glass Shoes adds its Summoning Time Increase to the Inputs value before the stun probe, the stun run, the Horn Flute window and the companion run.
  Golden: `tests/golden/hero_artifact_cases.py` (58 workbook evaluations: every artifact at star 5 in World Boss with Blaze Wizard Lv10, other fight shapes, stars, crit-rate
  branches, Reindeer def pen 50 / 80 / 99, Hero-specific Rush-stun shapes, the Glass Shoes equivalence pairs) -> `hero_artifact_reference.py` (stripped workbook copy, `formulas`, one
  evaluation at a time, ~30 s and ~1.2 GB each) -> `hero_artifacts_golden.json` -> `test_artifacts.py --class hero` (engine == workbook within rel 1e-9, 6 equip-toggle deltas, 10 equivalence pairs).
* Not modelled (same as the verify script): Weapon Acceleration / Physical Training / Weapon Mastery / Combat Mastery / Power Stance /
  Chance Attack rows: listed on the Skills sheet, no separate DPS term in the verify script (so none in the engine).

## Ice/Lightning Mage (artifacts ported 2026-11-20)

Files: `engine/classes/ice_lightning_mage.py` (`compute`, `defaults`, `schema`), `engine/data/ice_lightning_mage.py`, golden harness `tests/golden/ice_lightning_mage_cases.py` +
`run_reference_ice_lightning_mage.py` + `make_golden_ice_lightning_mage.py` + `check_ice_lightning_mage_fake.py` + `test_ice_lightning_mage.py` (265 cases, bit-exact against the verify script).
Artifacts (`inputs["artifacts"]`, same contract / `schema()["artifacts"]` as FP-Mage and Hero, `engine/artifacts.py` reused unchanged) are wired the way
`src/build_ice_lightning_mage_workbook.py` wires them: the Attack% bucket is `1 + (Magic Guard + Meditation + artifact Attack%)/100` times Infinity's Final Damage (engine on: the strip's `Bbuff_mean`,
strip `A0` = the artifact Attack% bucket without Charm); Hexagon Damage% is its own multiplicative term next to the buffs; Peach Tree / Silver Pendant enemy damage taken is summed into
the monster damage-taken bucket (`monster_dmg_bonus`: Freezing Breath Weaken + Elemental Reset + artifact) that feeds BOTH the Boss and the Normal Monster Damage terms (and so the companion's
`boss_pct` / `norm_pct` / `taken_bucket`); crit totals = Inputs + artifact (no live crit buff in this kit); Reindeer's Spear's correction uses the Inputs def pen; Soul Contract via
`fight.cd_extra_pct`; Horn Flute's uptime uses the stub-host run WITH the player's Glacier Wall entries (`s0` / `W0`, `A0` = the artifact bucket).  Arwen's Glass Shoes adds its Summoning Time Increase
to the Inputs value before the stun probe, the stun run, the Horn Flute window and the companion run.  With no artifact every term is neutral (x1.0 / +0.0) and `test_ice_lightning_mage.py` stays bit-exact.
Golden: `tests/golden/ice_lightning_mage_artifact_cases.py` (58 workbook evaluations: every artifact at star 5 in World Boss with Blaze Wizard Lv10, other fight shapes, stars, crit-rate branches,
Reindeer def pen 50 / 80 / 99, Glacier-Wall-stun shapes, Lv 105 / 112, the Glass Shoes equivalence pairs) -> `ice_lightning_mage_artifact_reference.py` (stripped workbook copy, `formulas`, one evaluation
at a time, ~35 s and ~1.6 GB each) -> `ice_lightning_mage_artifacts_golden.json` -> `test_artifacts.py --class ice_lightning_mage` (engine == workbook within rel 1e-9, 6 equip-toggle deltas, 10 equivalence pairs).

## Paladin (artifacts ported 2026-11-20)

Files: `engine/classes/paladin.py` (`compute`, `defaults`, `schema`), `engine/data/paladin.py`, golden harness `tests/golden/paladin_cases.py` + `test_paladin.py` (295 cases, bit-exact against the verify
script).  Artifacts (`inputs["artifacts"]`, same contract / `schema()["artifacts"]` as FP-Mage / Hero / ILM, `engine/artifacts.py` reused unchanged) are wired the way `src/build_paladin_workbook.py`
wires them: the Attack% bucket is `1 + (Vessel of Light + HP Recovery + Combat Orders' Lv82 half + artifact Attack%)/100` (engine on: the strip's `Bbuff_mean`, strip `A0` = Vessel of Light + the artifact
Attack% bucket without Charm); Final Damage artifacts (Candle, Flaming Lava, Horn Flute, branch-only Final Damage) multiply on top of the Final Damage bucket that already holds Guardian / Divine Blessing /
Divine Shield / Greater Vessel of Light; Hexagon Damage% is its own multiplicative term; Peach Tree / Silver Pendant enemy damage taken is summed into `monster_dmg_bonus` (Close Combat + Noble Demand +
Divine Mark weakens + artifact), which feeds BOTH the Boss and the Normal Monster Damage terms (and so the companion's `boss_pct` / `norm_pct` / `taken_bucket`); crit totals = Inputs + artifact (no live crit
buff in this kit); Reindeer's Spear's correction uses the Inputs def pen; Soul Contract via `fight.cd_extra_pct` (it reaches Combat Orders' uptime, the weakens' windows and Rush too); Horn Flute's uptime
uses the stub-host run WITH the player's Rush entries (`s0` / `W0`, `A0` = Vessel of Light + the artifact bucket).  Combat Orders' engine run (its cast count feeds the temporary skill-level averaging
`factor_eff`) carries Hexagon Necklace's stack values, because the strip's buff schedule is weighted by them.  Arwen's Glass Shoes adds its Summoning Time Increase to the Inputs value before the stun
probe, the stun run, the Horn Flute window and the companion run.  With no artifact every term is neutral (x1.0 / +0.0) and `test_paladin.py` stays bit-exact.
Golden: `tests/golden/paladin_artifact_cases.py` (64 workbook evaluations: every artifact at star 5 in World Boss with Blaze Wizard Lv10, other fight shapes, stars, crit-rate branches, Reindeer def pen
50 / 80 / 99, Rush-stun shapes, Combat Orders at Lv68 / 69 / 82 / 105 / 140 with skill-level bonuses and Soul Contract / Shamaness Marble, the Glass Shoes equivalence pairs) -> `paladin_artifact_reference.py`
(stripped workbook copy, `formulas`, one evaluation at a time, ~30 s and ~1.5 GB each) -> `paladin_artifacts_golden.json` -> `test_artifacts.py --class paladin` (engine == workbook within rel 1e-9, 6 equip-toggle
deltas, 10 equivalence pairs).

## Bowmaster (artifacts ported 2026-11-20)

Files: `engine/classes/bowmaster.py` (`compute`, `defaults`, `schema`), `engine/data/bowmaster.py`, golden harness `tests/golden/bowmaster_cases.py` + `test_bowmaster.py` (324 cases, bit-exact against the verify
script).  Artifacts (`inputs["artifacts"]`, same contract / `schema()["artifacts"]` as FP-Mage / Hero / ILM / Paladin, `engine/artifacts.py` reused unchanged) are wired the way
`src/build_bowmaster_workbook.py` wires them: the Attack% bucket is `1 + (Marksmanship base + conditional + Illusion Step + artifact Attack%)/100` (engine on: the strip's `Bbuff_mean`, strip `A0` =
Marksmanship + the artifact Attack% bucket without Charm); Final Damage artifacts multiply on top of Mortal Blow's Final Damage bucket; Hexagon Damage% is its own multiplicative term; Peach Tree /
Silver Pendant enemy damage taken is `monster_dmg_bonus` (Summary's Global Monster Damage-Taken Bonus%, additive INSIDE the Boss / Normal Monster Damage terms next to each row's own mastery bonus, and so in
the companion's `boss_pct` / `norm_pct` / `taken_bucket`); crit totals = Inputs + Sharp Eyes (Crit Damage, uptime) + Concentration + artifact (no live Crit Rate buff: Sharp Eyes has no Crit Rate
component); Reindeer's Spear's correction uses the Inputs def pen (Bowmaster has no live Defense Penetration); Soul Contract via `fight.cd_extra_pct`; Horn Flute's uptime uses the stub-host run WITH
Covering Fire's stun entry (`s0` / `W0`, Lv49+, `A0` = Marksmanship + the artifact bucket).  Arwen's Glass Shoes adds its Summoning Time Increase to the Inputs value before the stun probe, the stun
run, the Horn Flute window and the companion run.  Illusion Step is the only engine-timed buff, so there is no second engine run (Paladin's `e_co` has no counterpart).  With no artifact every term is
neutral (x1.0 / +0.0) and `test_bowmaster.py` stays bit-exact.
Golden: `tests/golden/bowmaster_artifact_cases.py` (65 workbook evaluations: every artifact at star 5 in World Boss with Blaze Wizard Lv10, other fight shapes, stars, crit-rate branches, Reindeer def pen
50 / 80 / 99, Covering-Fire-stun shapes with and without a companion (Lv48 / Lv49 in Breakthrough and World Boss), Illusion Step Lv117 / 118, Lv100, the boss-bucket artifacts, the Glass Shoes equivalence
pairs) -> `bowmaster_artifact_reference.py` (stripped workbook copy, `formulas`, one evaluation at a time, ~25 s and ~1.2 GB each) -> `bowmaster_artifacts_golden.json` ->
`test_artifacts.py --class bowmaster` (engine == workbook within rel 1e-9 (worst 1.2e-10), 6 equip-toggle deltas, 10 equivalence pairs).  Sensitivity support was added 2026-11-22 (`sens_specs/bowmaster.py`, `bowmaster_sens_cases.py`, `test_sensitivity.py --class bowmaster`; KNOWN_GAPS "Bowmaster: Sensitivity in the engine"); the
Sensitivity strip-rebuild set of the workbook was chosen with the engine's reuse-vs-re-solve experiment (see KNOWN_GAPS "Bowmaster: Companions + Status Effect Damage / KO timeline port", last bullet).

## Bishop (artifacts ported 2026-11-20)

Files: `engine/classes/bishop.py` (`compute`, `defaults`, `schema`), `engine/data/bishop.py`, golden harness `tests/golden/bishop_cases.py` + `test_bishop.py` (299 cases, bit-exact against the verify script).
Artifacts (`inputs["artifacts"]`, same contract / `schema()["artifacts"]` as the other artifact classes, `engine/artifacts.py` reused unchanged) are wired the way `src/build_bishop_workbook.py` wires them:
Damage% is ONE additive bucket here (Inputs Damage% + Holy Symbol's Damage Boost + the Hexagon Necklace average + Peach Tree / Silver Pendant enemy damage taken, `(1 + (...)/100)` in `Calc!K`), so the
companion's `agg_damage_avg` / `taken_bucket` (Hexagon snapshot ratio, damage-taken debuff) read that joint bucket including the artifacts; the Attack% artifacts (Old Music Box, Secret Map, Reindeer's Spear,
Alliance Badge, Bottle of Emotion, Charm's average) join Magic Guard / Heal / Bless / Holy Magic Shell in the Attack% bucket (engine on: the strip's `Bbuff_mean`, strip `A0` = the artifact bucket without Charm);
the Final Damage artifacts multiply on top of the Final Damage input (Advanced Blessing / Infinity stay their own factors); the boss / normal Damage terms get Candle / Sayram's / branch-only artifacts, `boss_pct` /
`norm_pct` of the companion host keep Holy Fountain / Holy Symbol; crit totals = Inputs + artifact (Blood of the Divine's Crit Damage stays in `crit_damage_bonus`); Reindeer's Spear's correction uses the Inputs
def pen (also in PvP, where the monster defense is Bishop's own total Defense); Soul Contract via `fight.cd_extra_pct` (it reaches every cooldown incl. Triumph Feather's 18 s trigger cooldown - the workbook
was missing that call site until 2026-11-20); Horn Flute's uptime uses the stub-host run WITH Angel Ray's entries (`s0` / `W0`, `A0` = the artifact bucket).  Arwen's Glass Shoes adds its Summoning Time Increase to the
Inputs value before the stun probe, the stun run, the Horn Flute window and the companion run.  With no artifact every term is neutral (x1.0 / +0.0) and `test_bishop.py` stays bit-exact.
Golden: `tests/golden/bishop_artifact_cases.py` (64 workbook evaluations: every artifact at star 5 in World Boss with Blaze Wizard Lv10, other fight shapes, stars, crit-rate branches, Reindeer def pen 50 / 80 / 99,
Bishop shapes around Big Bang Lv100 / Angel Ray Lv103 (Lv 99 / 100 / 102 / 103 / 112 / 125, Angel Ray's stun without a companion, PvP with Defense %), the Glass Shoes equivalence pairs) -> `bishop_artifact_reference.py`
(stripped workbook copy, `formulas`, one evaluation at a time, ~35 s and ~1.5 GB each) -> `bishop_artifacts_golden.json` -> `test_artifacts.py --class bishop` (engine == workbook within rel 1.4e-10 worst case, ~2e-16 typically; 6 equip-toggle
deltas, 10 equivalence pairs).

## Marksman (artifacts ported 2026-11-20)

Files: `engine/classes/marksman.py` (`compute`, `defaults`, `schema`), `engine/data/marksman.py`, golden harness `tests/golden/marksman_cases.py` + `test_marksman.py` (368 cases, bit-exact against the verify
script).  Artifacts (`inputs["artifacts"]`, same contract / `schema()["artifacts"]` as the other artifact classes, `engine/artifacts.py` reused unchanged) are wired the way
`src/build_marksman_workbook.py` wires them: the Attack% bucket is `1 + (Marksmanship base + conditional + Illusion Step + Blink Bolt + artifact Attack%)/100` (engine on: the strip's `Bbuff_mean`, strip
`A0` = Marksmanship + Blink Bolt + the artifact Attack% bucket without Charm; Illusion Step is the only timed buff); Final Damage artifacts multiply on top of Mortal Blow's Final Damage bucket; Hexagon Damage% is its own
multiplicative term; Peach Tree / Silver Pendant enemy damage taken is `monster_dmg_bonus` (additive INSIDE the Boss / Normal Monster Damage terms next to each row's mastery bonus, and so in the companion's `boss_pct` /
`norm_pct` / `taken_bucket`); crit totals = Inputs + artifact (Crit Rate) and Inputs + Sharp Eyes' Crit Damage uptime average + artifact (Crit Damage); Reindeer's Spear's correction uses the Inputs def pen; Soul Contract
via `fight.cd_extra_pct` (it reaches the three player stuns, Illusion Step / Sharp Eyes / Nimble Feet and every cooldown row); Horn Flute's uptime uses the stub-host run WITH the three player stuns
(`s0` / `W0`, Frostprey is the periodic one; `A0` = Marksmanship + Blink Bolt + the artifact bucket).  Arwen's Glass Shoes adds its Summoning Time Increase to the Inputs value before the stun probe, the stun run, the
Horn Flute window and the companion run.  With no artifact every term is neutral (x1.0 / +0.0) and `test_marksman.py` stays bit-exact.
Golden: `tests/golden/marksman_artifact_cases.py` (67 workbook evaluations: every artifact at star 5 in World Boss with Blaze Wizard Lv10, other fight shapes, stars, crit-rate branches, Reindeer def pen 50 / 80 / 99,
the three-stun shapes (Lv49 / 60 / 98 / 104 / 117 / 118 / 140, with and without a companion), Illusion Step / Sharp Eyes around Lv115-118, Soul Contract in Chapter Hunt, the Glass Shoes equivalence pairs) ->
`marksman_artifact_reference.py` (stripped workbook copy, `formulas`, one evaluation at a time, ~30 s and ~1.2 GB each) -> `marksman_artifacts_golden.json` -> `test_artifacts.py --class marksman` (engine == workbook within
rel 1e-9 (worst 4.9e-11, the fractional-window artifact of Wind Archer at +45%), 6 equip-toggle deltas, 10 equivalence pairs).  The golden run found that the Marksman workbook never wired Soul Contract's cooldown
decrease into its cooldown formulas (CLAUDE.md item 11; fixed in the builder, see the 2026-11-21 bullet of KNOWN_GAPS "Marksman: Companions + Status Effect Damage / KO timeline").  Sensitivity support was added 2026-11-22 (`sens_specs/marksman.py`, `marksman_sens_cases.py`, `test_sensitivity.py --class marksman`; KNOWN_GAPS "Marksman: Sensitivity in the engine"); the workbook's Sensitivity
strip-rebuild set was chosen with the engine's reuse-vs-re-solve experiment.

## Dark Knight (artifacts ported 2026-11-21)

Files: `engine/classes/dark_knight.py` (`compute`, `defaults`, `schema`), `engine/data/dark_knight.py`, golden harness `tests/golden/dark_knight_cases.py` + `test_dark_knight.py` (323 cases, bit-exact against
the verify script).  Artifacts (`inputs["artifacts"]`, same contract / `schema()["artifacts"]` as FP-Mage / Hero / ILM / Paladin, `engine/artifacts.py` reused unchanged) are wired the way
`src/build_dark_knight_workbook.py` wires them: the Attack% bucket is `1 + (Hex + Dark Resonance + Cross Over Chains + Hyper Body + artifact Attack%)/100` (engine on: the strip's `Bbuff_mean`, strip `A0` = the
artifact Attack% bucket without Charm, plus the Hexagon / Charm values); Final Damage artifacts multiply on top of the Final Damage input; Hexagon Damage% is its own term; Peach Tree / Silver Pendant
enemy damage taken is summed into `monster_dmg_bonus` (Evil Eye + Magic Crash Weaken + the Dark Resonance / Hex boss clauses + artifact), which feeds BOTH the Boss and the Normal Monster Damage terms (and the
companion's `boss_pct` / `norm_pct` / `taken_bucket`); crit totals = Inputs + Lord of Darkness (proc x duty cycle) + artifact, and Ring of Cycles' threshold includes Lord of Darkness' Crit Rate; Reindeer's
Spear's correction uses the Inputs def pen; Soul Contract via `fight.cd_extra_pct` (every cooldown: both player stuns, the buffs, Magic Crash's Weaken window); Horn Flute's uptime uses the stub-host run WITH BOTH
player stun entries (Rush + Evil Eye Shock, `s0` / `W0`).  Arwen's Glass Shoes adds its Summoning Time Increase to the Inputs value before the stun probe, the stun run, the Horn Flute window and the companion
run.  Defense / Iron Wall are untouched by artifacts.  With no artifact every term is neutral (x1.0 / +0.0) and `test_dark_knight.py` stays bit-exact.
Two corrections found by this port (details in KNOWN_GAPS "Dark Knight: Arwen's Glass Shoes ..."): the workbook never wired Soul Contract's cooldown decrease (fixed in the builder), and the verify script / engine
used the flat Defense as the PvP opponent's Defense while the workbook (and the Inputs label) use the TOTAL Defense (Defense x (1 + Defense %)): fixed in both, `dark_knight_golden.json` regenerated (only the 20
PvP cases with Defense % != 0 changed).
Golden: `tests/golden/dark_knight_artifact_cases.py` (68 workbook evaluations: every artifact at star 5 in World Boss with Blaze Wizard Lv10, other fight shapes, stars, crit-rate branches, Reindeer def pen
50 / 80 / 99, Evil Eye Shock alone (Lv45 / 62) vs + Rush (Lv63+), the timed buffs unlocking at Lv45 / 66 / 69 / 115 with skill-level bonuses and Soul Contract / Shamaness Marble, Defense 0, the Glass Shoes
equivalence pairs) -> `dark_knight_artifact_reference.py` (stripped workbook copy, `formulas`, one evaluation at a time, ~30 s and ~1.3 GB each) -> `dark_knight_artifacts_golden.json` ->
`test_artifacts.py --class dark_knight` (engine == workbook within rel 1e-9 (worst 4.8e-11, typically 1e-16), 6 equip-toggle deltas, 10 equivalence pairs).  Sensitivity: see "Sensitivity for more than one class" below (Dark Knight is the second class with a spec).

## Buccaneer (artifacts ported 2026-11-21)

Files: `engine/classes/buccaneer.py` (`compute`, `defaults`, `schema`), `engine/data/buccaneer.py`, golden harness `tests/golden/buccaneer_cases.py` + `test_buccaneer.py` (325 cases, bit-exact against the verify script).
Artifacts (`inputs["artifacts"]`, same contract / `schema()["artifacts"]` as the other artifact classes, `engine/artifacts.py` reused unchanged) are wired the way `src/build_buccaneer_workbook.py` wires them:
the Attack% artifacts (Old Music Box, Secret Map, Reindeer's Spear, Alliance Badge, Bottle of Emotion, Charm's average) join Roll of the Dice's dice component in the Attack% bucket (engine on: the strip's
`Bbuff_mean`, strip `A0` = dice + the artifact bucket without Charm); the Final Damage artifacts (Candle, Flaming Lava, Horn Flute, branch-only Final Damage) multiply on top of the Final Damage bucket that already
holds Serpent Scale / Crossbones / Time Leap / Speed Infusion (so the strip's `fd_scale` and the companion's `fdpart` do not see them); Hexagon Damage% is its own multiplicative term; Peach Tree / Silver Pendant
enemy damage taken is summed into `monster_dmg_bonus` (Assault Mark + artifact) which feeds BOTH Boss and Normal Monster Damage terms (and the companion's `boss_pct` / `norm_pct` / `taken_bucket`); crit totals =
Inputs + artifact (no live crit buff in this kit); Reindeer's Spear's correction uses the Inputs def pen; Soul Contract via `fight.cd_extra_pct` (it reaches every cooldown: all rows, Assault Mode's interval T,
the Octopunch window of the Assault Mark, Corkscrew Blow's stun - the workbook already applied it at its single call site, `Calc!Q`); Horn Flute's uptime uses the stub-host run WITH Corkscrew Blow's entry (`s0` /
`W0`, `A0` = dice + the artifact bucket).  Arwen's Glass Shoes adds its Summoning Time Increase to the Inputs value before the stun probe, the stun run, the Horn Flute window and the companion run.  There is no
second (Hexagon-weighted) engine run: nothing here is a skill-level buff.  With no artifact every term is neutral (x1.0 / +0.0) and `test_buccaneer.py` stays bit-exact.
Golden: `tests/golden/buccaneer_artifact_cases.py` (66 workbook evaluations: every artifact at star 5 in World Boss with Blaze Wizard Lv10, other fight shapes, stars, crit-rate branches, Reindeer def pen 50 / 80 / 99,
Corkscrew-Blow shapes with and without a companion (Lv62 / 63, Breakthrough boss-phase extension), Hook Bomber Lv99 / 100, Crossbones Lv115, Time Leap Lv125, Octopunch haste Lv134, Soul Contract in Chapter Hunt,
the Glass Shoes equivalence pairs) -> `buccaneer_artifact_reference.py` (stripped workbook copy, `formulas`, one evaluation at a time, ~25 s and ~1.3 GB each) -> `buccaneer_artifacts_golden.json` ->
`test_artifacts.py --class buccaneer` (engine == workbook within rel 6.3e-16 worst case, 6 equip-toggle deltas, 10 equivalence pairs).  Sensitivity: `engine/sens_specs/buccaneer.py` + `tests/golden/test_sensitivity.py --class buccaneer` (2026-11-22, see KNOWN_GAPS "Buccaneer: Sensitivity in the engine").

## Corsair (artifacts ported 2026-11-21)

Files: `engine/classes/corsair.py`, `engine/data/corsair.py`, golden harness `tests/golden/corsair_cases.py` + `test_corsair.py` (323 cases, bit-exact against the verify script).  Artifacts
(`inputs["artifacts"]`, same contract / `schema()["artifacts"]` as the other ported classes, `engine/artifacts.py` reused unchanged) are wired the way `src/build_corsair_workbook.py` wires them:
the Attack% bucket is `1 + (Roll of the Dice's dice component + artifact Attack%)/100` (engine on: the strip's `Bbuff_mean`, strip `A0` = dice component + the artifact bucket without Charm;
Jolly Roger stays the one engine-timed buff and its Final Damage F is still scaled by `100/(100 + Inputs FD + R_FD_REST)`); Corsair's Final Damage bracket `(1 + (Inputs + Jolly Roger + Ahoy
Mateys)/100)` is ADDITIVE and the live Final Damage artifacts (Candle / Flaming Lava / Horn Flute) multiply on top as their own bucket; Hexagon Damage% is its own multiplicative term; Peach Tree /
Silver Pendant enemy damage taken joins Swift Fire's Weaken in `monster_dmg_bonus` (Summary R_MONSTER_DMG_BONUS, inside the Boss / Normal Monster Damage terms and the companion's `boss_pct` /
`norm_pct` / `taken_bucket`); crit totals = Inputs + artifact (Corsair has no live Crit Rate / Crit Damage source); Soul Contract through `fight.cd_extra_pct` - `Fight.eff_cooldown` is the one
place every cooldown goes through (skills, buffs, Quickdraw's closed form incl. the divided Brain Scrambler / Rapid Fire, Swift Fire's Weaken, Ahoy Mateys, Blackboot Bill's stun entry), exactly
like the workbook's `base_eff_cd_expr`; Horn Flute's uptime uses the stub-host run WITH Blackboot Bill's stun entry (`s0` / `W0`, Lv66+).  Arwen's Glass Shoes adds its Summoning Time Increase to
the Inputs value before the stun probe, the stun run, the Horn Flute window and the companion run.  There is no second engine run.  With no artifact every term is neutral (x1.0 / +0.0) and
`test_corsair.py` stays bit-exact.
Golden: `tests/golden/corsair_artifact_cases.py` (71 workbook evaluations: every artifact at star 5 in World Boss with Blaze Wizard Lv10, other fight shapes, stars, crit-rate branches, Reindeer def pen
50 / 80 / 99, Blackboot Bill Lv65 / Lv66 in World Boss and Breakthrough, Broadside Lv117 / 118 / 138, Quickdraw Lv124 / 125 with Soul Contract in Chapter Hunt, Jolly Roger next to the Final Damage
artifacts, the boss-bucket artifacts, the Glass Shoes equivalence pairs) -> `corsair_artifact_reference.py` (stripped workbook copy, `formulas`, one evaluation at a time, ~33 s and ~1.4 GB each) ->
`corsair_artifacts_golden.json` -> `test_artifacts.py --class corsair` (engine == workbook within rel 1e-9 (worst 1.5e-10, Breakthrough + Wind Archer's fractional-window noise), 7 equip-toggle deltas incl.
Soul Contract in Chapter Hunt with Quickdraw (rel 2.5e-16), 10 equivalence pairs).  Sensitivity: `engine/sens_specs/corsair.py` + `tests/golden/test_sensitivity.py --class corsair` (12 slimmed-copy evaluations, 823 values, rel 1e-9; KNOWN_GAPS "Corsair: Sensitivity in the engine"); the workbook's Sensitivity strip-rebuild set was chosen
with the engine's reuse-vs-re-solve experiment (see KNOWN_GAPS "Corsair: Companions + Status Effect Damage / KO timeline", last bullet).

## Night Lord (artifacts ported 2026-11-21)

Files: `engine/classes/night_lord.py` (`compute`, `defaults`, `schema`), `engine/data/night_lord.py`, golden harness `tests/golden/night_lord_cases.py` + `test_night_lord.py` (380 cases, bit-exact against the
verify script, with no artifact equipped).  Artifacts (`inputs["artifacts"]`, same contract / `schema()["artifacts"]` as the other artifact classes, `engine/artifacts.py` reused unchanged) are wired the way
`src/build_night_lord_workbook.py` wires them: the Attack% artifacts (Old Music Box, Secret Map, Reindeer's Spear, Alliance Badge, Bottle of Emotion, Charm's average) join Dark Sight's Attack% in ONE additive bucket
(engine off: `(1 + (DarkSight + Art)/100)(1 + Frailty)(1 + Adrenalin)`; engine on: the strip's `Bbuff_mean` x Alchemic Adrenaline's averaged Final Damage, strip `A0` = the artifact bucket without Charm plus the
Hexagon / Charm values; the companion snapshot's `k1` uses the same `A0`); Frailty Curse's and Alchemic Adrenaline's Final Damage stay their own factors.  The old `artifact_attack_pct` hook (default 0) is kept
and simply ADDS to the artifact Attack% (`test_night_lord.py::check_artifact_hook`).  The Final Damage artifacts (Candle, Flaming Lava, Horn Flute) multiply on top of the Final Damage input / the mastery Final
Damage; Hexagon Damage% is the `(1 + Damage%)` factor next to Shadow Partner; Peach Tree / Silver Pendant (enemy damage taken) add to BOTH the Boss and the Normal Monster Damage terms next to Venom's Weaken +
the Frailty Curse debuff (kept separate from `derived.monster_dmg_bonus`, which is Summary's row without the artifacts); crit totals = Inputs + Critical Throw / Dark Sight's Crit Rate + artifact (Ring of Cycles'
threshold is Inputs + that live bonus + Rainbow Snail Shell), Crit Damage = Inputs + Frailty Curse's Critical-Damage-Taken mastery + artifact; Reindeer's Spear / Contract of Darkness / branch-only Final Damage
are the boss / normal branch extras (`Effects.extras`, also on every per-cast weight of the strip); Hexagon / Charm phase factors scale the engine-off rows of Breakthrough / Hero Dungeon.  Soul Contract reaches
every cooldown through `fight.cd_extra_pct` (Gust Charm, both buffs, the debuff windows, every skill row); Horn Flute's uptime is read from the stub-host run WITH Gust Charm's entry (`s0` / `W0`, `A0` = the artifact
bucket without Charm), so it is also defined from Lv35 with no companion chosen.  Arwen's Glass Shoes adds its Summoning Time Increase to the Inputs value before the stun probe, the stun run, the Horn Flute window and
the companion run.  Shadow Partner's average multiplier stays divided out of the companion's `unit` with or without artifacts.  There is no second (Hexagon-weighted) engine run: no skill-level-derived Attack% sources
besides Dark Sight.  With no artifact every term is neutral (x1.0 / +0.0).  Night Lord has no Defense % (PvP's opponent has the flat Defense, workbook and engine agree).
Golden: `tests/golden/night_lord_artifact_cases.py` (73 workbook evaluations: every artifact at star 5 in World Boss with Blaze Wizard Lv10 (9 groups of 4), other fight shapes, stars, crit-rate branches, Reindeer
def pen 50 / 80 / 99, Gust Charm alone at Lv34 / 35, Adrenalin Lv66, Showdown Lv99 / 100, Frailty Curse Lv110, Soul Contract / Shamaness Marble with skill-level bonuses and a Cooldown Decrease, `incoming_hit_rate`
0 / 2 / 5, Defense 0, the Glass Shoes equivalence pairs) -> `night_lord_artifact_reference.py` (stripped workbook copy, `formulas`, one evaluation at a time, ~35 s and ~1.3 GB each) ->
`night_lord_artifacts_golden.json` -> `test_artifacts.py --class night_lord` (engine == workbook within rel 1.4e-10 worst case - the Breakthrough Wind Archer cases at a +40% summon window, the documented
fractional-window artifact - 67 of 73 below 1e-14, 6 equip-toggle deltas, 10 equivalence pairs).  The engine has no `sensitivity` support for Night Lord yet.

## Shadower (artifacts ported 2026-11-21)

Files: `engine/classes/shadower.py` (`compute`, `defaults`, `schema`), `engine/data/shadower.py`, golden harness `tests/golden/shadower_cases.py` + `test_shadower.py` (391 cases, bit-exact against the verify script).
Artifacts (`inputs["artifacts"]`, same contract / `schema()["artifacts"]` as the other artifact classes, `engine/artifacts.py` reused unchanged) are wired the way `src/build_shadower_workbook.py` wires them:
the Attack% artifacts (Old Music Box, Secret Map, Reindeer's Spear, Alliance Badge, Bottle of Emotion, Charm's average) join Dark Sight's additive Attack% bucket next to Steal / Meso Mastery (engine on: the strip's
`Bbuff_mean`, strip `A0` = Steal + Meso Mastery + the artifact bucket without Charm; Into Darkness / Smokescreen stay their own Final Damage factors); the Final Damage artifacts (Candle, Flaming Lava, Horn Flute, branch-only
Final Damage) multiply on top of `(1 + Final Damage input)`; Hexagon Damage% is the `(1 + Damage%)` factor next to Shadow Partner; Peach Tree / Silver Pendant enemy damage taken is the workbook's `AGG_ENEMY_DMG_TAKEN`
inside `R_MONSTER_DMG_BONUS`: added to BOTH Boss and Normal Monster Damage terms and to the companion's `boss_pct` / `norm_pct` / `taken_bucket` (the former input hook `artifact_monster_dmg_bonus` carries it, plus a manual
additive, default 0); crit totals = Inputs + Dark Sight's Crit Rate / Smokescreen's Crit Damage + artifact (Ring of Cycles' threshold uses Inputs + Dark Sight's Crit Rate); Reindeer's Spear's correction uses the Inputs def pen;
Soul Contract via `fight.cd_extra_pct` (every row, both cast buffs, Phase Dash's stun entry; the workbook did NOT apply it at all until 2026-11-21 - it now wraps both `effective_cooldown_expr` call sites); Horn Flute's uptime uses
the stub-host run WITH Phase Dash's entry (`s0` / `W0`, `A0` as above).  Arwen's Glass Shoes adds its Summoning Time Increase to the Inputs value before the stun probe, the stun run, the Horn Flute window and the companion
run; Shadow Partner's average multiplier stays divided out of the companion `unit`.  There is no second (Hexagon-weighted) engine run.  With no artifact every term is neutral (x1.0 / +0.0) and `test_shadower.py` stays bit-exact.
Golden: `tests/golden/shadower_artifact_cases.py` (75 workbook evaluations: every artifact at star 5 in World Boss with Blaze Wizard Lv10, other fight shapes, stars, crit-rate branches with Dark Sight Crit at the 100% line,
Reindeer def pen 50 / 80 / 99, Phase Dash Lv62 / 63 with and without a companion (Breakthrough boss-phase extension), Lv75 / 82 / 99 / 100 / 110 / 113 / 115 (incoming hit rate 0 / 2.5 / 6) / 125 / 136, stat set B, Soul Contract in
Chapter Hunt, the Glass Shoes equivalence pairs) -> `shadower_artifact_reference.py` (stripped workbook copy, `formulas`, one evaluation at a time, ~34 s and ~1.4 GB each) -> `shadower_artifacts_golden.json` ->
`test_artifacts.py --class shadower` (engine == workbook within rel 1e-9 (worst 9.8e-11, Breakthrough + Wind Archer's fractional-window noise; otherwise <= 6e-16), 7 equip-toggle deltas incl. Soul Contract in Chapter Hunt, 10 equivalence
pairs).  The engine has no `sensitivity` support for Shadower yet (`engine/sensitivity.py::STATUS_REBUILD_KEYS` would need the workbook's list, see KNOWN_GAPS "Shadower: Companions ..." -> Sensitivity fixes).

## Sensitivity / stat values (Phase 3)

`engine/sensitivity.py` reproduces the workbook's `Sensitivity` sheet top section and the Summary "Marginal DPS & Stat Value" block with the same numerics.

```python
from engine import sensitivity
out = sensitivity.run(fp_mage, inputs)                                    # everything, JSON-serialisable (~0.5 s in World Boss with a companion)
out = sensitivity.run(fp_mage, inputs, which=["stats", "artifacts"])      # parts: stats | artifacts | companions | summon_time | cdr
sensitivity.STAT_SWEEP / STAT_LIST / ARTIFACT_TOGGLES                      # metadata for a UI: key, label, type (flat/pct/mult/dr150/dr100/level), step text,
                                                                           # the stat's semantic note; the toggle list comes from the engine's artifact table
```

* **stats** (27 continuous stats; the workbook's `STAT_SWEEP` has 63 entries = these + the 36 toggles): per row `current`, `new`, `baseline_total`, `new_total`,
  `dps_gain` (= "DPS per +1"), `pct_gain` ("100 + gain" convention), `units_per_1pct` (None = "n/a"), boss / normal ratios.  Boss and normal branches are blended by
  the time weight on their RELATIVE growth (CLAUDE.md bug 9).
* **artifacts**: the 36 equip toggles, the workbook's direction-invariant % rule (item 15), ranking among unlocked artifacts (`rank_position`, `ranking`);
  `no_dps_effect` artifacts report gain 0 (+ their potential gain) with the flag.  Baked-into-Inputs artifacts get the what-if gain exactly as the blocks compute it
  (signed: adding when unequipped, removing when equipped).  Extra optional input keys: `artifact_stars` {id: 0..5 | None} (the ArtifactsInput Star Levels of artifacts
  that are not equipped; default = the workbook's default by rank), `artifact_potential_gain` {id: DPS} (the ArtifactsInput "Total Potential DPS Gain", added to the equip gain).
* **companions** (comparison table at `inputs["companion_levels"]` {name: level}, else `companion_level=` / `companion_comparison_level` for all, else the chosen
  companion's level), **summon_time** (value of each total the boots lines can reach; `companion_potential_lines_pct` = the lines already on PotentialCubes, b0 includes
  Arwen's Glass Shoes), **cdr** (absolute CDR 0.5 .. 5.0 s).
* A block is one more `fp_mage.model()` run with the swept value replaced PLUS the workbook's block-only terms, passed through `inputs["_sens"]` (an empty dict for every
  normal `compute`): main-stat flat-Attack channel (flat_int / int_pct), Spell Mastery / Magic Critical level deltas (skill_lvl_2nd / 3rd / all), Book of Ancient / Athena's
  Gloves / Bottle of Emotion dependent terms (crit_rate, attack_speed), the baked-in artifact what-ifs, the REUSED Status/KO strip (every stat except `STATUS_REBUILD_KEYS`)
  and the PINNED summon-time candidate (every stat except `COMPANION_FULL_SEARCH_KEYS`; `engine/common/companion.run(..., pin=(s, E))`, built from
  `src/companion_python_model.py` by guarded textual patches because src/ is not edited).  `naive=True` evaluates plain re-runs instead; `semantic_differences()` lists where
  the two differ.  Known consequences of the workbook's semantics (reproduced, flagged per row as `strip_reused` / `summon_time_pinned`): in Breakthrough / Hero Dungeon the blended
  RELATIVE gain is not the dollar delta of the two real states (bug 9, by design).  Fixed 2026-11-19 (were documented quirks): every stat that changes what the timeline strip
  consumes re-runs its own strip (`STATUS_REBUILD_KEYS`: + the five Skill Level stats, Skill / Basic Attack / Boss Damage, Crit Rate, Ring of Cycles / Book of Ancient /
  Rainbow Snail Shell / Candle / Sayram's Necklace / Star Rock equips; before, a World Boss `skill_lvl_1st` block read -86% of the plain re-run), and a baked-in Final Damage
  artifact (Cursed Doll, Lit Lamp, Clear Spring Water, Soul Pouch, Bottle of Emotion's FD) is a multiplicative factor on the whole product in both directions
  (`sens["final_damage_factor"]`: 1+x/100 adding, 1/(1+x/100) removing), so removal reports the same dollar gain and % Gain as adding.
* Golden: `tests/golden/sens_cases.py` (36 cases) -> `sens_reference.py` (Sensitivity-slimmed copies of the workbook, one `formulas` evaluation at a time, ~2-4 min and 4-8 GB each)
  -> `fp_mage_sensitivity_golden.json` -> `test_sensitivity.py --class fp_mage` (rel 1e-9; companion quantities at a FRACTIONAL window carry the workbook's ~1.6e-9 `(a+b-|a-b|)/2`
  precision artifact, see `FRAC_RTOL` there).

### Sensitivity for more than one class (generalised 2026-11-21; FP-Mage + Dark Knight)

`engine/sensitivity.py` is a class-agnostic core.  Everything that differs between classes is in two places: a **spec** (pure data, `engine/sens_specs/<class>.py` -> `SPEC = SensSpec(...)`,
type in `engine/common/sens.py`) and the class module's **`model(inputs)`** entry, which honours the `inputs["_sens"]` hooks (vocabulary + shared helpers `def_pen_with_dose`,
`final_damage_bucket`, `boa_crit_damage_delta` in `engine/common/sens.py`; every hook is a no-op without `_sens`, so `compute` stays bit-exact).  Public API:
`sensitivity.run(class_module, inputs, which, naive, companion_level)` (NotImplementedError without a spec), `supports(class_module)`, `meta(class_module)` / `stat_sweep(class_module)` (the class's own
stat list for a UI); the module-level `STAT_SWEEP` / `STAT_LIST` / `STATUS_REBUILD_KEYS` / `COMPANION_FULL_SEARCH_KEYS` names are FP-Mage's (unchanged).  Dark Knight: 30 stats (Flat STR, STR %, DEX,
Defense and Defense % with Iron Wall, ...), 36 toggles, companion / summon-time / CDR tables, `tests/golden/test_sensitivity.py --class dark_knight` (workbook golden), `api/tests/test_sensitivity_classes.py`.  Hero (2026-11-22): 28 stats, 36 toggles, tables as above, `tests/golden/test_sensitivity.py --class hero` (12 workbook evaluations), `api/tests/test_sensitivity_classes.py`; its spec flags: `baked_fd_form="typed"` (the builder retypes `Inputs!final_damage` inside the additive Final Damage bucket, so a baked-in Final Damage what-if is a factor on the TYPED value: `final_damage_factor` in `engine/classes/hero.py`) and `mult_extra` (the Final Damage +1% step bumps the whole bucket incl. Enrage / Combo Synergy, `MULT_KIND_EXTRA_REF`); Hero's block wires Reindeer's dose, Shamaness Marble and (since the 2026-11-22 builder fix) Athena's Attack Speed correctly.  Ice/Lightning Mage (2026-11-22): 27 stats, 36 toggles, tables as above, `tests/golden/test_sensitivity.py --class ice_lightning_mage` (12 workbook evaluations, 88 blocks, engine == workbook within rel 1e-9), `api/tests/test_sensitivity_classes.py`; the builder's inert Shamaness Marble row was FIXED (`bdi_block` adds `shamaness_marble_delta_block`), Reindeer's dose and Athena's Attack Speed were already wired; new hook `as_bonus_extra` (Magic Acceleration's delta joins MP Eater's flat Attack Speed, i.e. the bonus side of the Attack Speed diminishing returns, gated on MP Eater's unlock); the class's `crit_rate_bonus` is 0 (its artifact crit bucket is `art_crit_rate`), `crit_rate_total` is exposed.

**How to add a class to the sensitivity engine** (Shadower is done (`sens_specs/shadower.py`, `shadower_sens_cases.py`: `baked_fd_form="factor"` - the typed Final Damage is its own factor in K next to the artifact bucket, no `mult_extra`; 10 passive deltas incl. Channel Karma's Attack% (`attack_mult_delta`) and Critical Edge's Crit Rate AND Crit Damage; `incoming_hit_rate` is a plain stat; its builder had the Athena / Shamaness gaps, fixed 2026-11-23, Reindeer was already correct; LEAN golden of 7 evaluations: the baked-in chain of four World Boss states, Enhancement Dungeon, Breakthrough with both tables, Chapter Hunt Lv118; the case matrix must mirror the PotentialCubes sheet's boots Summoning-Time line, see `companion_potential_lines_pct`); Paladin is done - `sens_specs/paladin.py`, `paladin_sens_cases.py`: typed Final Damage like Hero / Buccaneer, plus `passive_deltas_in_model=True` because Paladin's passives are time-averaged with Combat Orders' skill-level bonus, so the class module computes the passive deltas itself and the engine hands it the main model's `passive_values` as `_sens["passive_ref"]`; Bowmaster is done (`sens_specs/bowmaster.py`, `bowmaster_sens_cases.py`: the plain-factor Final Damage form on the artifact bucket (`baked_fd_form="factor"`) with Mortal Blow in the `mult_extra` bracket, 11 passive deltas incl. Armor Break's Def Pen (new hook `def_pen_delta`) and `attack_mult_delta`; its builder had the Athena / Shamaness gaps, fixed; the golden is a CHAIN of baked-in states because the workbook has only 4 artifact slots), Night Lord is done (`sens_specs/night_lord.py`, `night_lord_sens_cases.py`: `baked_fd_form="factor"` on the artifact bucket, no `mult_extra`, 10 passive deltas incl. `boss_damage_delta` / `attack_mult_delta` / `crit_damage_delta`, its builder had the Shamaness gap only, fixed; the strip does not read Actions Per Second so Athena needs no rebuild), Shadower is next - Corsair is done (`sens_specs/corsair.py`, `corsair_sens_cases.py`: `baked_fd_form="typed"` through a block-local SHIFT cell inside the additive Final Damage bracket, Jolly Roger / Ahoy Mateys in `mult_extra` (`final_damage_all`), 9 passive deltas incl. `attack_mult_delta` / `crit_damage_delta`; its builder had the Athena / Shamaness gaps, fixed, Reindeer was already correct), Marksman is done (`sens_specs/marksman.py`, `marksman_sens_cases.py`: `baked_fd_form="typed"` with Mortal Blow in the bucket, 10 passive deltas incl. `attack_mult_delta`, Illusion Step's boost re-pointed in the builder), Bishop is done (`sens_specs/bishop.py`, `bishop_sens_cases.py`: Defense / Invincible, pinned PvP opponent Defense, Magic-pattern passive deltas incl. `as_bonus_extra`), Hero is done, see its files as the template for a class with an ADDITIVE typed Final Damage bucket; Buccaneer is done (additive typed Final Damage like Hero, plus passive Attack%/Attack Speed deltas: hook `attack_mult_delta`), Ice/Lightning Mage is done, the template for the mage / plain-factor Final Damage form with passive deltas; the class must already have `model()` + artifacts):

1. **Class module hooks** (`engine/classes/<class>.py`; copy the edits of `dark_knight.py`, each is 1-3 lines, grep `sens` there; read the class's `build_stat_block` for where the workbook block differs):
   `sens = self.sens = inp.d.get("_sens") or {}` at the top of `_build` (before the Content is built) and `model(inputs)` at the bottom;
   `mainstat_attack_delta` (`self.attack += delta x (1 + ATTACK%/100)`); `min_damage_delta` / `max_damage_delta` / `skill_damage_delta` / `basic_attack_damage_delta` / `final_damage_delta` /
   `crit_rate_delta` / `crit_damage_delta` / `attack_speed_extra` (additive deltas of the passives baked into the Inputs and of Athena's Gloves; put each where the workbook's `delta[...]` /
   `agg_*_block` enters the SAME bracket); `crit_rate_threshold_extra` (add to the Inputs crit rate BEFORE the artifact Ctx is built: it feeds Ring of Cycles' threshold and the live crit);
   `def_pen_dose` via `sens_mod.def_pen_with_dose` (and see the Reindeer quirk below); `bdi_extra` (added to the Buff Duration Increase of the Fight); `boss_damage_extra` (Star Rock, into the
   artifact boss bucket); `eq` (`self.eq = sens["eq"] if "eq" in sens else resolve_slots(...)`); `final_damage_bucket(eff.agg_final_damage, sens)` on the class's multiplicative artifact Final
   Damage bucket; `boa_crit_damage_delta(sens, total crit rate incl. the class's live crit source)` added to the artifact crit damage; strip reuse (`e1 = sens["strip"][0] if "strip" in sens else
   stl.solve(...)`, same for the pass-2 `E_ENGINE`, and `self.e1 = e1`); `comp_pin` (a SECOND stun probe `run(..., pin=sens["comp_pin"])` feeding the stunned shares and the Horn Flute
   `s0` / `W0`, the strip's stun vector keeps the unpinned probe; pass `pin=` to the final companion run too); `want_comp_host` (build `self.comp_host` even with no companion; only run the companion when
   one is active); `monster_defense` (PvP classes whose Defense is an input); expose `summon_time_inc`, `comp_host`, `crit_rate_total` (the FULL live crit total) and `crit_rate_bonus` (a live
   crit-rate source such as Lord of Darkness / Sharp Eyes, 0 otherwise).  The model attributes the core reads: `total_dps`, `result()`, `normal_weight`, `eq`, `status_on`, `e1`, `e_engine`,
   `companion_result` (`s`, `E`), `comp_host`, `companion_choice`, `companion_level`, `companion_dps`, `pb_total`, `pn_total`, `summon_time_inc`, `pvp_len`, `fight_duration`, `monster_type`,
   `content_type`, `art_effects.rows`.  Re-run `test_<class>.py` / `test_artifacts.py --class <class>` (bit-exact / unchanged) after the edits.
2. **Spec** (`engine/sens_specs/<class>.py`, register the id in `sens_specs.CLASS_IDS`): `stat_list` = the builder's `STAT_SWEEP_STAT_ENTRIES`; `status_rebuild_keys`, `companion_full_search_keys`,
   `summon_time_keys` = the builder's lists (the test compares them); `mainstat = MainStat(flat key, % key, subs=((sub stat key, ratio), ...))` for the flat-Attack channel of CLAUDE.md bug 7 (the
   sub stats that ARE sweep stats); `passive_levels` = one `PassiveLevel(hook, base, fidx, step, unlock)` per `PASSIVE_DELTA_SLOT` row (the Skills-sheet tuple; the hook names above);
   `semantics` notes; `stat_to_key` = the builder's potential / equipment / artifact-potential maps (+ `cubes_sub_stat_pct`), which `api/features.py` picks up.  **Check the workbook block for
   the quirks and set the flags accordingly** (each found in the Dark Knight builder; `grep` the class's `build_stat_block`): `bdi_toggle_wired` (is `shamaness_marble_delta_block` used in `bdi_block`?
   unused in Dark Knight / Paladin / Bowmaster's builders until fixed 2026-11-22/23: then the Shamaness row is inert), `reindeer_dose_in_rows` (does the K formula read `def_pen_total_block`? Dark Knight / Paladin had `Inputs!def_pen + delta`, fixed 2026-11-22/23: the dose only reached the
   boss-branch correction and the companion), `athena_as_in_aps` (does the block's `s_aps` include Athena's direct Attack Speed? `attack_speed_total_block` yes, the old Dark Knight `attack_speed_with_delta` no, fixed 2026-11-23), `pin_monster_defense` (a Defense input + PvP), `baked_fd_form` (how `fd_baked_factor` feeds the class's Final Damage; if the baked-in artifacts land in an ADDITIVE
   Final Damage bracket the class module's `final_damage_factor` use must follow the builder), `extra_stat_sens` / `extra_toggle_sens` (class-specific block-only terms that fit no hook).  `mult_extra` (("final_damage", "<model attr>"),): the builder's `MULT_KIND_EXTRA_REF` (a live additive Final Damage source in the same bucket as the typed value, Hero / Bowmaster / Corsair / Buccaneer / Paladin / Marksman: the +1% multiplicative step bumps the full bucket, and the row's Current / New include it); `baked_fd_form="typed"` when the block retypes `Inputs!final_damage` inside that bucket (the class module then applies `sens["final_damage_factor"]` to the TYPED value, see `engine/classes/hero.py`).
3. **Golden**: `tests/golden/<class>_sens_cases.py` (copy `dark_knight_sens_cases.py`: <= 8 blocks per case, every stat once, the strip-rebuild stats in World Boss AND Enhancement Dungeon, the toggles
   incl. baked-in artifacts in both directions (`I/` chain), CDR milestones as 5-value subsets (`cdr=[...]`), the two companion tables, PvP when the class has a Defense input), a row in
   `CLASSES` of `tests/golden/sens_reference_generic.py` (slimmed workbook copies, ONE `formulas` evaluation at a time, ~2.5-5 min and 3.5-4.5 GB each; `--class <id> --run-all`, `--assemble`), and a
   a `tests/golden/registry.py` entry + `tests/golden/sens_extras/<class>.py` (copy Dark Knight's: the static spec == builder test, the toggle pairs of the direction-invariance test and the `API` data of the shared tests; `test_sensitivity.py --class <class>` runs it around `sens_compare_generic.run_golden`).
   Any difference above rel 1e-9 must be understood and documented as a replicated workbook semantic (Dark Knight found three real workbook gaps this way: the inert Shamaness row, the Reindeer dose missing from the rows' defense reduction and Athena's Attack Speed missing from the block's APS; all three fixed in the Dark Knight builder 2026-11-23).
4. **API**: add the id to `api/registry.py::SENSITIVITY_CLASSES` (only once 1-3 are green), run `/tmp/api_venv/bin/python -m pytest api/tests -q`, add a row to `CLASSES` of `api/tests/test_sensitivity_classes.py` (the one parametrized API test of every class with stat values).

## Not done yet

The Artifact POTENTIAL-lines calculator (the data tables are in `engine/data/artifacts.py`: `ARTIFACT_POTENTIAL_*`, reference-only in the workbook; its output is what
`artifact_potential_gain` feeds into the equip rows); cube-optimizer extraction; the FastAPI layer; the web UI; the sensitivity of the other 10 classes (recipe above);
engine vs Excel golden for the main compute (the verify script already matched Excel, so engine == verify == Excel by transitivity).

Rule: the `src/verify_<class>_workbook.py` scripts stay untouched and remain the independent reference the engine is checked against.

## Cubes / Equipment / Potentials (Phase 4b)

* `engine/cubes.py` - the cube optimizer of `src/potential_cubes_ev.py` as pure functions: `recommend(gear_rows, pricing)` -> one dict per (slot, potential type) with the
  CSV columns (`current_value`, `smallest_n`, `n_for_50pct` / `n_for_75pct`, `milestone_ev` / `milestone_ev_pct` at the 24 milestones, CSV order via `sort=True`; `csv_row`).
  `Pricing` = baseline DPS + stat-name -> DPS per unit + CDR curve (+ optional exact-CDR callable) + optional `CompanionPricing` (summoning-time model);
  `Pricing.from_dict` for classes without a sensitivity module, `pricing_from_sensitivity(sens_result, inputs)` (FP-Mage: `sensitivity.run(..., which=["stats","cdr","summon_time"])`)
  builds the CubeData!J:K table (`dps_per_unit_table`: Main Stat Per Level x level, Critical Rate at the FULL live crit total >= 100 priced as Critical Damage unless Ring of
  Cycles / Book of Ancient is equipped - CLAUDE.md item 13) and the companion pricing; Potential and Bonus Potential use separate pity tables (item 17).  `only=` computes a subset
  of rows while the others still define cross-row baselines.  Pure Python by default-fallback, numpy (optional, only here) when importable: **numpy is not needed** - 30 rows, 1000
  cubes, all starting at `normal` (worst case): 2.7 s numpy, 6.3 s pure Python (the roll enumeration has a bit-identical fast path; no API image dependency).
* `engine/equipment.py` - Equipment Compare (fixed Attack line + 5 dropdown lines per equip, 21 stats, duplicates merge, different stats compound): `compare(current, new, rates, total_dps)`.
* `engine/potentials.py` - ArtifactsInput potential lines: `artifact_potential`, `potential_table`, `potential_gains(state, rates, total_dps)` = the `inputs["artifact_potential_gain"]`
  hook value of `engine.sensitivity` (`hook_for` runs the stats part for you); Equipped? / Star Level resolution.  Rates = `cubes.sweep_rates(sens_result)` (the Sensitivity column H).
* Golden (all runnable with plain `python3`): `tests/golden/test_cubes.py` (engine == the original script's functions executed unmodified on constructed gear / pricing:
  522 rows, 10 cases, both backends, rel 1e-9 - observed bit-identical; `cubes_reference.py --write` regenerates `cubes_golden.json`), `test_equipment.py` and `test_potentials.py`
  (engine == the builder's REAL `Equipment Compare` / `ArtifactsInput` / CubeData!J:K formulas evaluated by `formulas` in one TINY workbook with stub Total DPS / Sensitivity rates,
  ~5 s: `tiny_reference.py --write` regenerates `tiny_golden.json`).  Adding a class = a `stat_to_key` map (`cubes.dps_per_unit_table`, `equipment.compare`, `potentials`) from its builder.
