# Contributor / Agent Guide

This file is for anyone — human or AI — picking up this codebase to add a class, fix a workbook,
or extend the tooling. It captures conventions and pitfalls that were only discovered by building
all 12 classes; following them will save you from re-discovering the same bugs.

**Current priority** (see README.md's "Future work" section): a full 12-class data audit against
`maplestoryidle.info`'s embedded game tables was completed 2026-10-21 (findings, the user's per-item
decisions and the raw source snapshots live in `data/ref_maplestoryidle_info/`, start with
`VERIFICATION_FINDINGS_2026-10-20.md`); see "Ground truth sourcing → game tables" below for what
changed in the method. Bishop's own remaining gap (Divine Protection's growth curve) is the last
significant per-skill data hole in the four historically weakest classes — Paladin, Buccaneer, and
Corsair were substantially closed out via `maplestoryidle.info`. MP consumption and Companions are
planned after that, project-wide, though MP consumption specifically has no scaling data on either
source (see that section) and may stay permanently out of scope. Artifacts (Equip Effects
for all 36 artifacts, plus a reference-only Artifact Potentials calculator) has already shipped for
all 12 classes — see the "Artifacts (\<Class\>)" sections in `KNOWN_GAPS.md` for each class's own
wiring decisions.

## What this project is

Per-class Excel DPS calculators for MapleStory Idle RPG. Each class gets:
- `<Class>/<Class>-DPS-Calculator.xlsx` — a live-formula workbook (Inputs, FactorTable, Skills,
  Calc, Summary, Sensitivity, Artifacts, ArtifactsInput, CubeData, PotentialCubes sheets).
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
- **`maplestoryidle.info`** is a second, independent data source — structured skill data embedded
  directly in that site's own `app.js` (fetch it directly and regex/parse the `jobs` array's
  `skills`/`masteries` objects, plus a separate `AUGUST_13_SKILL_UPDATES` overlay object keyed by
  job id that represents the CURRENT, patched state layered on top of the base `skills` array's
  pre-patch values — check both). For Buccaneer and Corsair specifically, this source is marked
  `"Game capture provided by player"` — a direct screenshot/capture of the live game client, not a
  community-edited wiki page — and should be trusted over `idle.maplestorywiki.net` on any
  disagreement. It has independently caught: two skills with damage/target counts wrong by ~100x
  on the wiki (Bowmaster's Hurricane, Flash Mirage), a **10x magnitude bug** (Corsair's Broadside
  sustained-turret tick, wiki said 3300%/tick, real value is 330%/tick), several wrong/missing
  masteries, and numerous wrong assumed cooldowns across Buccaneer/Corsair (both classes had *no*
  cooldown data on the wiki at all, so this is a straight resolve, not just a cross-check). Caveat
  learned the hard way: this site's own schema NOT listing a field (e.g. no `cooldown:` key) is
  NOT reliable evidence that field doesn't apply to that skill — confirm the real mechanic (e.g. by
  asking the user, who may have direct in-game knowledge) before inferring absence-of-data means
  absence-of-mechanic.

### Game tables (the strongest ground truth — added 2026-10-21)

`maplestoryidle.info` ships its own structured game tables (`job-skill-impact.json`, snapshot in
`data/ref_maplestoryidle_info/site_job_skill_impact_all.json`): per skill, the real `ratioE3`
(= BaseDamage in tenths-of-%), `factorIndex`, `hitCount`/`maxHitCount` (hits / max targets),
`cooldownMs`/`durationMs`/`tickTimeMs`, trigger rules (`OnAttack`, trigger %, cooldown, condition
expression) and `statOps` (stat buffs/debuffs with their own factorIndex). It beat the site's own
rendered description text on every disagreement tested (the text said Poison Breath 160% / Elemental
Drain 8%; tables and the user's in-game numbers say 200% x F12 / 12% x F21). Resolve a skill's
`(baseDamage, factorIndex)` from the table first; the old "burst -> 12, buff -> 22" FLAGGED-ASSUMPTION
guess was wrong for several buffs (Paladin Guardian/Divine Blessing/HP Recovery, Buccaneer Serpent
Scale/Crossbones/Time Leap, Corsair Majestic Presence/Jolly Roger/Ahoy Mateys, FP Meditation, ...).
When the table has no row for a variant (e.g. Greater Sea Serpent I's 430% line) the factorIndex is
still a flagged assumption — say so in the row's Note. Site `reqLevel` is the unlock level.

Patterns introduced by that audit (reuse them, don't reinvent):
- **"When attacking ... X% chance, 1s cooldown" mastery procs** (Meteor/Blizzard/Nautilus Final
  Attack, Majestic Presence) trigger off ANY attack: steady-state rate `(c*R)/(1+ICD*c*R)` with R the
  combined cast rate of the triggering attacks (Basic attack rate + action-costing damage skills;
  summons and DoT ticks excluded, per the user's FP-Mage precedent). They have no Cooldown of their
  own (ICD(s) column, RollsPerCast 1) and a Summary "trigger rate" cell mirrored in every Sensitivity
  block with the BLOCK-LOCAL `C/Q/R` columns (bug #6).
- **Temporary skill-level buffs (Paladin's Combat Orders)** are modeled by time-averaging the
  FactorTable lookup: `(1-u)*F(D) + u*F(D+bonus)`, u = the buff's uptime (a Summary cell).
- **Resource loops (Buccaneer's Serpent Scales/Assault Mode)** use a smoothed steady-state cycle
  (activation interval T = trigger cooldown + half a basic-attack period; uptime u = A/(A+N*T)).
- **A circular dependency can hide inside a SUMPRODUCT range**: excluding a row with a `<>` mask still
  makes that row's cell a precedent. When a quantity feeds back into some rows' cooldowns (Corsair's
  Quickdraw), sum the OTHER rows' cells explicitly instead of ranging over the whole column, and solve
  the fixed point in closed form. The `formulas` package silently drops circular cells (the symptom is
  `KeyError: cell not found in workbook: SUMMARY!B3` in a verify script).
- **Skills-sheet formulas that read Inputs (e.g. a window that depends on Buff Duration Increase)
  are invisible to Sensitivity blocks** — those must re-read the Input through the block's own `ib()`.
- Verify scripts do not model artifacts: run them against a copy with the artifact slots cleared
  (`Inputs` rows "Slot 1-4" → "(none)"), otherwise a saved workbook that has artifacts equipped will
  "mismatch" by exactly the artifact bonus.

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
2. **Mastery chains showing per-tier percentages are summed as RAW tier values — every tier is its
   own add-on.** (REVERSED 2026-10-21 on the user's in-game confirmation; this item used to say the
   opposite, "sum as deltas", which silently under-counted the basic-attack chain in 11 classes.) A
   chain that shows 10%/11%/12%/13%/14%/15% across six level tiers is
   `{lvl1: 10, lvl2: 11, lvl3: 12, lvl4: 13, lvl5: 14, lvl6: 15}` → 75% at max (e.g. 33% at Lv117 for
   the 102/106/116 tiers), NOT `{10, 1, 1, 1, 1, 1}` (15%). Percent masteries add *points* to the
   skill's displayed coefficient% (a 363% skill with a "+70%" mastery shows 433%), they are not
   relative multipliers; a plain "%" in Nexon's text is points unless the user says otherwise (Dark
   Knight's Cross Over Chains/Hex "+100%/+50% Attack" are points — they look huge but are real).
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
10. **Artifact Star Level is 0-indexed.** `star_lookup_expr` resolves a star tier via
    `CHOOSE(star_ref+1, v0,v1,v2,v3,v4,v5)` — star levels run 0 to 5 (6 tiers), where 5 is the
    MAXIMUM tier, not "5th of 6." When hand-spot-checking an artifact by setting its Star Level
    cell directly via openpyxl, use `ARTIFACT_STAR_VALUES[key][star]` (not `[star-1]`) as the
    expected value, or you'll chase a numeric mismatch that isn't a real bug.
11. **An artifact effect that wraps an existing helper function must be wired at every call site
    of that helper, in both the main Calc sheet and its Sensitivity mirror — not just given a
    reference-only row on the Artifacts sheet.** Soul Contract's Chapter-Hunt-only cooldown
    decrease shipped in several classes' Artifacts sheet as a correctly-computed value that was
    never actually multiplied into any skill's `effective_cooldown_expr(...)` result — the
    artifact looked "modeled" (it had its own row, its own star-value lookup) but had zero actual
    DPS effect. Any new artifact that modifies an existing per-skill quantity (cooldown, cast
    rate, hit count) needs its own grep across every call site of that quantity's helper function,
    not just a single wiring point.
12. **Once artifact equip-toggle bool entries are added to `STAT_SWEEP`, `build_summary_sheet`'s
    "Marginal DPS & Stat Value" mirror loop must iterate `STAT_SWEEP_STAT_ENTRIES`, never raw
    `STAT_SWEEP`** — `SENSITIVITY_ROW_FOR` is keyed only by stat entries, so iterating the full
    list (including the 36 new bool entries) throws a `KeyError` the first time that loop runs.
    Found and fixed in every class's port; check for this specifically before considering a new
    class's Artifacts port "done."
13. **PotentialCubes-EV's "Critical Rate %" cap-check must test the FULL live crit rate total**
    (`Inputs!crit_rate` + any live global crit-rate bonus the class has, e.g. Sharp Eyes/Dark
    Sight Crit + `art_ref("AGG_CRIT_RATE")` from other equipped artifacts) **against the 100% cap
    — not raw `Inputs!crit_rate` alone.** Testing the raw Inputs value lets the cap-check fire
    late, still recommending Crit Rate% potential lines past the point they're actually worth 0%
    DPS gain. Shipped incorrectly in more than one class; always re-derive this check's comparison
    value the same way the real Calc-sheet crit-rate-total formula does. Found missing entirely
    (not just incomplete) in Buccaneer/Corsair/Dark Knight/Marksman — these 4 had no crit-rate-total
    check at all, just raw `Inputs!crit_rate>=100` — even though Dark Knight (Lord of Darkness) and
    Marksman (Sharp Eyes) both have a real, nonzero live crit-rate skill source the check was
    silently ignoring. **Separately, the cap-check's own premise — that Crit Rate past 100% is
    worth substituting with Critical Damage's value — is wrong whenever Ring of Cycles or Book of
    Ancient is equipped**, since both have a dependent mechanic that keeps scaling with raw Crit
    Rate past 100% (Ring of Cycles' Basic Attack Damage bonus scales continuously with Crit Rate
    excess up to 200% total; Book of Ancient's Crit-Damage-from-Crit-Rate conversion has no upper
    bound at all) — in that case the literal `Sensitivity!H` value for Crit Rate already correctly
    reflects real, continuing marginal value (confirmed directly: in one test case it was *larger*
    than the Crit Damage substitute, in another *smaller* — the substitute isn't even a safe
    one-directional approximation once either artifact is in play), so the substitution must be
    skipped (gated on `NOT(ring_of_cycles_equipped)` and `NOT(book_of_ancient_equipped)`) whenever
    either is equipped, same treatment as any other stat.
14. **A big artifacts-feature splice copied verbatim from a template class's file can leave that
    template class's own literal strings behind** — e.g. a new `ArtifactsInput` sheet's title
    still reading "Fire/Poison Arch Mage" after being spliced into a different class. Grep the
    finished file for the template class's own name after any large copy-paste splice.
15. **An equip-toggle artifact's "% Gain" column must divide by the HYPOTHETICAL-UNEQUIPPED
    total in both toggle directions, not whichever total happens to be real right now.** The
    "bool"-kind `artifact_pct_gain_expr` tests on->off when currently equipped and off->on when
    not — its own code comment said this should "reciprocal the % gain so both directions report
    the same...convention," but the actual formula in all 12 classes computed
    `(Summary!TOTAL_DPS + dollar_gain)/Summary!TOTAL_DPS*100` unconditionally, i.e. always divided
    by the CURRENT real total. Since the dollar gain is correctly direction-invariant (confirmed:
    equipping or unequipping the same real pair of states always nets the identical $ delta either
    way) but the real total itself differs between "equipped" and "unequipped," this made the same
    artifact report two different % Gain values depending purely on which state you happened to be
    testing from — found by a user noticing Reindeer's Spear showed 115.98% unequipped vs 113.78%
    equipped for the mathematically identical real state (def_pen manually adjusted to match).
    Fix: `IF(currently_equipped, TOTAL/(TOTAL-dollar_gain)*100, (TOTAL+dollar_gain)/TOTAL*100)` —
    i.e. actually implement the "reciprocal" the comment already promised. The $ `DPS Gain` column
    itself was never wrong; only `% Gain` needed the fix. Ground-truth-tested by directly editing
    `Inputs!def_pen`/the ArtifactsInput equip slot in a scratch copy and comparing
    `Summary!TOTAL_DPS` before/after against the Sensitivity row's own reported numbers — the same
    technique as the Book of Ancient/Reindeer's Spear hand-spot-checks in the Verification
    checklist below, just run in BOTH toggle directions instead of one.
16. **A "carry over the user's real values on rebuild" migration fix must be scoped to ONE
    rebuild, never left as a standing rule, or it silently re-breaks the exact thing it was
    migrating away from, forever.** `build_inputs_sheet`'s own `load_existing_workbook_state`
    carries forward every per-content-type Inputs value by default — but a past one-time cleanup
    for Chapter-Stage (an earlier migration had wrongly duplicated Breakthrough/Chapter Hunt's own
    "28-9" text into the other 6 applicable content types, which need a bare number instead) was
    implemented as an *unconditional* `CHAPTER_STAGE_TRUST_EXISTING_FOR = {"Breakthrough", "Chapter
    Hunt"}` allowlist, rather than something that ran once and was then removed — so it kept
    discarding the user's own correctly-entered values for those 6 content types on *every*
    subsequent rebuild, not just the one rebuild that needed the cleanup. Found by a user noticing
    their real Chapter-Stage values reset to generic defaults after a routine rebuild. If you ever
    add a similar "clean up a known-bad carried-over shape" migration, either (a) make it
    self-expiring (detect the specific bad shape — e.g. dash-formatted text in a bare-number column
    — and only reset THAT case, trusting anything already correctly shaped), or (b) explicitly flag
    it as one-time-only and remove it in a follow-up commit once you've confirmed it ran.
17. **Potential and Bonus Potential are separate roll tracks with genuinely different pity caps —
    don't let them share one `RARITY_UPGRADE_RATES` table.** Both share the same roll VALUE table
    (what stats/values are available per rarity/line, and at what weight — keyed only by
    `(slot, rarity, line)`, no potential-type dimension), but their pity (forced-upgrade) caps
    differ at every tier except Legendary (confirmed by the user: Bonus Potential's real caps are
    42/75/150/417/714 vs regular Potential's 30/60/120/333/714). `data/cube_potential_data.json`'s
    `RARITY_UPGRADE_RATES` is now keyed by potential type first, then rarity;
    `potential_cubes_ev.py`'s `optimal_stopping_trace`/`probability_any_better_roll` both take
    `potential_type` as an explicit parameter and index into the matching sub-table — never
    reintroduce a single shared pity table across both tracks.

18. **Skill Cooldown Decrease applies to every REAL cooldown** (skills, buffs and passives; user decision
    2026-10-21) — not just `CostsActionSlot` rows. Each build script routes every effective-cooldown call
    through `cdr_applies_expr(key)`; rows whose `Cooldown(s)` is a trigger-rate / internal-interval SURROGATE
    (e.g. `1/APS`, a 1s tick) must be listed in that script's `CDR_EXEMPT_ROW_KEYS` or CDR would crush them to
    the 0.1s floor. Buff/debuff UPTIMES must use the row's effective cooldown (`1/Calc!Q{row}` on the main
    sheet, the block-local `1/Q{row}` in a Sensitivity block), never the raw Skills-sheet cell, and are capped
    at 100% (`MIN(1, dur/cd)` steady state, `(casts-1)*MIN(dur, cd) + last` when fixed-duration exact).
19. **A Skills-sheet formula that reads a swept Input (or the main Summary) is invisible to Sensitivity
    blocks.** Level is never swept so `IF(Inputs!level>=...)` is fine, but `6+basic_attack_target_increase`,
    attack-speed-scaled cooldowns (`Summary!APS`), Buff-Duration-dependent windows and any `Summary!...`
    ProcChance% must be re-derived inside the block from its own `ib()` / local cells (see Bowmaster's
    `AS_SCALED_COOLDOWN_EXPR`, Corsair's `crew_window_expr`, Buccaneer's block-local Assault uptime).
    Check with a full-model run: set a swept stat's Input to the Sensitivity row's "New Value" in a stripped
    copy of the workbook and compare Summary!Total DPS with the Sensitivity "New Total DPS" (pure-boss and
    pure-normal content, where the time-weighted and dollar blends coincide).

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
8. Three mandatory Artifacts hand-spot-checks, since a clean zero-error scan + verify-script pass
   alone does not catch wiring bugs in artifact-toggle math (see item 11 above for a real example
   that slipped through both): (a) **Book of Ancient compounding-order test** — build two
   `openpyxl`-edited copies of the rebuilt workbook, one with Book equipped (remember Star Level
   is 0-indexed — item 10 above) and its direct + dependent bonus manually folded into
   `Inputs!crit_rate`/`crit_damage`, one without; the `formulas`-package Total DPS delta between
   them must exactly match Sensitivity's own "Book of Ancient (Equip)" row's reported DPS Gain
   (found by searching resolved cells for the literal label text, since the visible sorted column
   is an INDEX/MATCH formula). Include any live global crit-rate bonus (Sharp Eyes, Dark Sight
   Crit, etc.) in the folded-in total if the class has one. (b) **Reindeer's Spear
   diminishing-returns test** — unlock star 5 but leave unequipped, sweep `Inputs!def_pen` from 50
   to 99.9, confirm the Sensitivity "Reindeer's Spear (Equip)" row's % Gain *decreases* as
   `def_pen` rises (saturating). (c) **Equip-toggle direction-invariance test** (added after item
   15's bug) — for any bool-kind artifact, build the matched equipped/unequipped pair as in (a)
   (same real state, just toggled, with any "baked into Inputs" dependent value — e.g.
   `def_pen` — manually adjusted to match), and confirm the Sensitivity row's **% Gain**, not just
   its $ `DPS Gain`, is identical to full floating-point precision from EITHER direction — testing
   only the dollar column does not catch item 15's bug, since that column was never wrong.

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
   categorical sweep → level-boundary sweep → additive-vs-multiplicative audit → Artifacts port
   (copy the data model and ~32 `artifact_*_expr()` helpers verbatim from any existing class, then
   adapt the class-specific wiring points — see items 10-14 above and each existing class's
   "Artifacts (\<Class\>)" section in `KNOWN_GAPS.md` for the exact pattern). Don't write 2000
   lines and try to debug it as a whole afterward.
5. Update `KNOWN_GAPS.md` and this class's own workbook README sheet with anything you had to
   assume, approximate, or leave out of scope.
