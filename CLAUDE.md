# Contributor / Agent Guide

This file is for anyone — human or AI — picking up this codebase to add a class, fix a workbook,
or extend the tooling. It captures conventions and pitfalls that were only discovered by building
all 12 classes; following them will save you from re-discovering the same bugs.

**Current priority** (see README.md's "Future work" section): verifying and closing the data
gaps in Bishop, Paladin, Buccaneer, and Corsair — `KNOWN_GAPS.md` lists exactly what's flagged in
each. MP consumption, Artifacts, and Companions are planned after that, project-wide.

## What this project is

Per-class Excel DPS calculators for MapleStory Idle RPG. Each class gets:
- `<Class>/<Class>-DPS-Calculator.xlsx` — a live-formula workbook (Inputs, FactorTable, Skills,
  Calc, Summary, Sensitivity, CubeData, PotentialCubes sheets).
- `src/build_<class>_workbook.py` — generates that workbook from a `SKILL_ROWS` data table.
- `src/verify_<class>_workbook.py` — an independent, from-scratch Python re-derivation of the
  same DPS math, checked cell-for-cell against the live Excel formulas via the `formulas` package.
- `src/_reverse_engineer_<class>_factors.py` (where wiki data supports it) — resolves each
  skill's `(baseDamage, factorIndex)` tuple from its wiki per-level curve.

Read `KNOWN_GAPS.md` before touching any class's data — it lists every place a class relies on an
assumption instead of a verified wiki value, and why.

## Ground truth sourcing

- Wiki: `idle.maplestorywiki.net`. Fetch via `curl -sL -A "Mozilla/5.0" --max-time 20 "<url>"` —
  the wiki's own bot-detection blocks bare `curl`/most HTTP clients without a User-Agent, and
  intermittently Cloudflare-rate-limits fast batches of requests (~17-byte "error 1015" bodies) —
  add sleep+retry to any fetch loop.
- **A skill's individual wiki page can render a completely different skill's data under the
  right title** — a confirmed, real wiki content bug (e.g. `/w/Arrow_Platter` once rendered Wind
  Arrow II's own table). Always sanity-check a fetched page's level-1 description against the
  class overview page's description for that same skill before trusting its curve.
- If a page 404s, don't assume the skill has no page at all — try an old/alternate slug first
  (Bowmaster's Arrow Platter's real curve lived at `/w/Quiver_Flow`, an old name, found only by
  following the overview page's own outgoing link). Only fall back to the
  FLAGGED-ASSUMPTION convention (below) once you've confirmed via a genuine 404 (compare byte
  size against a known-good and known-bad control page) *and* there's no outgoing link to follow.
- Nexon's own English patch-note skill names sometimes differ from the wiki's chosen translation
  for the identical skill (confirmed instances: wiki "Concentration" = patch notes "Focused
  Fury"; wiki "Flash Mirage" = patch notes "Speed Mirage"). Match by mechanic/description, not
  name string, when cross-referencing patch notes.
- The wiki is usually **behind** the current patch — most classes' wiki pages showed pre-patch
  numbers well after the patch had shipped. Apply patch deltas manually on top of the wiki's base
  curve/shape; never assume the wiki is current.

## The FLAGGED ASSUMPTION convention

Some classes (Bishop, Paladin, Buccaneer, Corsair) have little or no individual per-skill wiki
data — confirmed via exhaustive 404 checks, not assumed. For those skills:
- Derive `(baseDamage, factorIndex)` from the single known level-1 value using a per-skill-type
  factorIndex convention: burst/DoT → 12, buffs/passives → 22, basic attack → 21.
- Say so explicitly in that row's own `Note` text — never silently present a guess as verified
  data.
- If a real Mastery table exists for the class (it usually does, even when individual skill pages
  don't), layer its real level-gated deltas on top of the assumed base curve — those numbers ARE
  real.
- If even the Mastery table doesn't exist (Corsair is the only such case so far), an
  **ASSUMED MASTERY SHAPE** — borrowing a sibling class's real mastery level-breakpoints/deltas
  by matching skill-slot roles — is the documented last resort. Flag it as an assumed mapping,
  not real Corsair-specific data.
- Update `KNOWN_GAPS.md` whenever you add, close, or change a flagged gap.

## Structural bugs already found once — don't reintroduce them

These were each found by building a second class and cross-checking it against the first. If
you're building a new class, check for all of these *before* your first build, not after:

1. **`HitsPerCast` must be the wiki's own hit/"time(s)" count**, e.g. a basic attack described as
   "290% damage to 6 target(s) in front 5 time(s)" has `HitsPerCast=5` (bumping to 6 at whatever
   level that class's own "Strike" mastery unlocks — check each class's own Mastery table for the
   exact level, it varies: 134 for some classes, 136 for others). Never default to the
   *target*-count formula (`=6+basic_attack_target_increase`) for this field — that's a different
   field (`NormalMonsterTargets`) entirely, and confusing the two silently inflates DPS.
2. **Mastery chains showing cumulative per-tier displayed percentages must be summed as DELTAS**,
   not the raw displayed values. If a chain shows 10%/11%/12%/13%/14%/15% across six level tiers,
   the correct `level_gated_sum` dict is `{lvl1: 10, lvl2: 1, lvl3: 1, lvl4: 1, lvl5: 1, lvl6: 1}`
   (10, then +1 five times → correct max total 15%), not the raw values (`{...: 15}`, which sums
   to a wrong 75%).
3. **Any "helper row"** (used when one skill's effect folds into another's coefficient, e.g. Final
   Attack folding into a basic attack) **must have its `SkillMasteryBonus%` actually wired into
   the Calc-sheet F-column formula** — in *both* the main Calc sheet and the Sensitivity sheet's
   own separate mirror of that formula. An early version of the `HELPER_ROW_KEYS` branch computed
   `F = base_curve_value` with no `+SkillMasteryBonus%` term at all, silently discarding any
   mastery bonus placed on a helper row.
4. **Any `SKILL_ROWS` entry that self-references a Summary-row constant** (e.g. an
   Attack-Speed-scaled cooldown referencing `R_APS`) needs that constant defined *before*
   `SKILL_ROWS` in the file — `SKILL_ROWS` is a module-level list literal evaluated immediately at
   import time, so a constant defined later in the file doesn't exist yet when Python evaluates
   the list.
5. **The Sensitivity sheet has its own separate copy of the Calc sheet's boss/normal
   monster-damage-taken blend formula** — if a class has a live "global damage-taken bonus"
   source (like a debuff proc), make sure that bucket's reference is included in *both* copies.
   One class shipped with it correctly in the main Calc sheet but silently missing from the
   Sensitivity mirror, for weeks, before being caught by comparing two classes' Sensitivity
   sheets against each other.
6. **The Sensitivity sheet's per-stat recompute block has its own local `InvCooldown`/
   `CastsInFight` columns (17/`Q` and 18/`R`), separate from the main Calc sheet's identically-
   positioned columns — any formula inside a block that needs "this row's exact-casts count" or
   "this row's inverse cooldown" must reference the *block's own* `R{row}`/`Q{row}`, never a
   column letter one or more off (`S`/`V` are unrelated columns — `S` is the diagnostic
   `O/N` ratio, `V`+ are typically blank). Three classes shipped with several call sites
   (buff-uptime helpers, the Skill+Buff-Cast-Rate `SUMPRODUCT`, and — in two classes — the block's
   own `InvCooldown`/`CastsInFight` *write* itself) pointing at the wrong column, which silently
   collapsed the Attack% bucket and/or Basic-Attack rate for every marginal-DPS test done in
   fixed-duration mode. It went unnoticed for a long time because fixed-duration mode was rarely
   exercised (steady-state was the default) — **any per-stat recompute block copied from another
   class's file needs every column-letter reference in it individually checked against that same
   class's own main-Calc-sheet equivalent**, not just skimmed for "looks structurally similar."
   Also watch for scratch/helper cells (e.g. a Maple Hero level/factor lookup) placed at a
   block-local row that's still within the normal per-skill column range (1–19ish) — they'll
   silently collide with that row's own real skill data; place them well beyond it (e.g. column
   `Z`), matching wherever the main Calc sheet puts its own equivalent scratch cells.
7. **Main-stat's flat-Attack contribution and STAT_DAMAGE are two independent mechanics, not
   duplicates — don't "fix" one by deleting the other.** Every class's `ib("stat_damage")` key
   (main stat final value * 0.01 + sub stat * 0.0025, feeding the STAT_DAMAGE% bucket) and the
   Sensitivity block's `mainstat_attack_delta` term (same main/sub stat pair, feeding flat Attack
   at ratio 1/0.25 before ATTACK% applies) are both real, separate in-game conversions — the
   character's main/sub stat contributes to damage through *two* independent channels. It's easy
   to mistake this for double-counting when cross-checking Sensitivity numbers by hand, since both
   terms move together whenever the swept stat is Flat main-stat/main-stat %. Before removing
   either term, verify by hand-deriving the *expected* marginal DPS from the in-game mechanic
   description, not just by comparing the Sensitivity block's internal consistency against the
   main Calc sheet — the main Calc sheet deliberately never implements the flat-Attack half at all
   (it assumes the user's own Flat ATTACK entry already includes it), so an internal-consistency
   check alone cannot distinguish "real mechanic implemented only in delta form" from "duplicated
   bug."
8. **A skill's cast *count* and the duration used for its last-cast tick-window truncation must
   always agree.** `rate_or_exact_hits_expr`/`exact_total_hits_expr` take a pre-computed cast-count
   cell reference (`CastsInFight`/`R{row}`) AND a separate duration argument, used internally for
   `remaining_after_last = duration - (casts-1)*cooldown`. If some future change reduces the
   duration used to compute the cast count (e.g. the buff-casting startup delay) without passing
   that *same* reduced duration into the rate formula's own duration argument, single-hit skills
   (ICD=0) will look completely fine — the mismatch is only visible on multi-tick DoT-style rows
   (ICD>0), since only they use `remaining_after_last` for anything. Always verify a
   duration-related change against at least one ICD>0 row per class before trusting a clean
   verify-script diff on ICD=0 rows alone.
9. **Sensitivity's marginal-value metric must weight branches by time, not by dollars — a plain
   `NewBlendedTotal - BaselineBlendedTotal` is NOT the same as a fair per-stat comparison whenever
   two blended branches (e.g. Boss/Normal Monster combat) have different raw DPS magnitudes.**
   Blending two branches' dollar totals `(1-w)*DPS_boss + w*DPS_normal` is correct for the real
   Total DPS (hitting more targets really does more damage), but using that same blended dollar
   delta for Sensitivity lets a stat's reported value be dominated by whichever branch happens to
   have a bigger dollar total (e.g. more targets), regardless of the user's actual time-weight `w`.
   The fix: Sensitivity blends the two branches' *relative growth ratios* (`new/baseline`) by `w`
   instead — a ratio cancels out any per-branch constant (target count, defense) the swept stat
   doesn't touch. Any class-specific code path that independently reads/derives a boss/normal-blended
   value (a mastery bonus, a HitRate-style metric built by dividing one blended column by another,
   a Sensitivity shadow-block mirror recomputing the blend on its own) needs the SAME treatment —
   check every such path individually; a clean pure-boss/pure-normal edge-case test does NOT catch
   an asymmetric bug that's equally wrong on both branches (only a blended, both-nonzero regression
   test does, since edge cases collapse to a single branch where symmetric bugs go unnoticed).

## Cross-checking a new class against its siblings

Classes ship in sibling groups sharing a stat identity and often several literal skills (Warrior
tree: Hero/Paladin/Dark-Knight/Buccaneer are all STR-main/DEX-sub and share Magic Crash, Rush,
Nimble Feet, and more verbatim). When adding a class to an existing sibling group:
- Reuse the group's proven template file as your starting point, not a blank slate.
- Any skill you believe is shared should resolve to the *exact same* `(baseDamage, factorIndex)`
  tuple as the sibling's own already-verified row — diff the tuples, don't just compare
  descriptions.
- This cross-check is how bugs #1–#5 above were actually found: not by re-reading your own code
  carefully, but by comparing two independently-built classes that were supposed to agree and
  finding they didn't.

## Verification checklist (every class, every change)

1. Build succeeds, zero `formulas`-evaluated error cells, checked incrementally sheet-by-sheet
   for a new class.
2. `verify_<class>_workbook.py` matches the live workbook exactly at default Inputs.
3. Full categorical sweep over the Inputs sheet's `content_type` (all 10 values), not
   `monster_type`/`fight_duration` directly — those two are now computed from `content_type` (plus
   `chapter`/`stage` for the chapter- and dungeon-based types) via the Inputs-sheet formulas at
   `IN["monster_type"]`/`IN["monster_defense"]`/`IN["fight_duration"]` (see `build_hero_workbook.py`'s
   `build_inputs_sheet`, the reference implementation). Include a couple of `chapter`/`stage`
   values spanning the 28→29 and 38→39/39→40 sub-stage-count boundaries for
   Breakthrough/Chapter Hunt. Never trust "the checks pass" from only the default combination.
4. Level-boundary sweep across every mastery/unlock threshold from 1–200, checking specifically
   for unexplained DPS *decreases* as level increases.
5. If shared skills exist with a sibling class, diff their resolved tuples.
6. Additive-vs-multiplicative audit: any two live, fight-state-dependent bonuses of the same type
   (e.g. two Attack%-type buffs) must sum additively in one bucket before a single multiplication
   — never multiply against each other.
7. Row constants derived via `len()`/`enumerate()`, never hand-numbered, for any variable-length
   table (the Skills sheet). The Summary sheet's own "info dump" block is a fixed, always-the-same
   layout across every class, so *that* block's row constants are legitimately hardcoded — don't
   confuse the two.

### Running sweeps without hanging

The categorical and level-boundary sweeps both re-evaluate the live workbook via the `formulas`
package, which takes ~30-40s per full load+calculate. Two hard-won lessons:
- **Never reuse one long-lived `formulas.ExcelModel()` object across many levels in a loop** — it
  degrades and effectively hangs after a few dozen iterations. Run
  `verify_<class>_workbook.py` as a **fresh subprocess** per level/combination instead (set
  `Inputs` via `openpyxl`, then `subprocess.run([sys.executable, "src/verify_<class>_workbook.py"])`
  and parse its printed `TOTAL DPS` line).
- **Before trusting any result, confirm no background sweep process is still running** and
  silently overwriting the workbook's `Inputs` — a background process that outlived its own
  wrapping task once corrupted a workbook entirely (unreadable `.xlsx`, `BadZipFile`). Do a hard
  `rm` + rebuild (no carried-over `Inputs`) before your final verification pass on any class you
  touch, and check the same `Inputs` cell twice, 10-20s apart, to confirm the file has gone quiet.

## Adding a new class

1. Confirm its stat identity (STR/DEX/INT/LUK main+sub) — don't assume from name similarity to
   another class; siblings in the same job tree can have *opposite* stat identities (Buccaneer is
   STR-main/DEX-sub, its own sibling Corsair is DEX-main/STR-sub).
2. Fetch the class's `/w/<Class>/Skills` and `/w/<Class>/Mastery` overview pages first, to scope
   what data actually exists before assuming the standard reverse-engineering path is available.
3. Identify shared skills with any existing sibling class up front — build the richer/more
   wiki-complete sibling first if there's a choice, then derive the other from it.
4. Work incrementally: reverse-engineer script → build script sheet-by-sheet → verify script →
   categorical sweep → level-boundary sweep → additive-vs-multiplicative audit. Don't write 2000
   lines and try to debug it as a whole afterward.
5. Update `KNOWN_GAPS.md` and this class's own workbook README sheet with anything you had to
   assume, approximate, or leave out of scope.
