# Known Gaps & Assumptions

This file catalogs every place where a class's DPS workbook relies on an assumption, an
approximation, or an unmodeled mechanic — as opposed to a value directly confirmed from the
live wiki (`idle.maplestorywiki.net`) and cross-referenced against the official patch notes.
Each class's own workbook (`README` sheet, and the `Note` column on the `Skills` sheet for
individual rows) documents the same information in context; this file exists as a single
project-wide index so gaps are easy to audit without opening every workbook.

**Every workbook is a live-formula Excel model, independently re-derived in Python
(`src/verify_<class>_workbook.py`) and checked cell-for-cell against the Excel formulas.**
"Gap" below never means "untested" — every number, including assumed ones, flows through the
same full verification pipeline (exact match, categorical sweep across
`monster_type × fixed-duration`, and a level-boundary sweep for unexplained decreases). A gap
means *the underlying game value itself* is uncertain, not that the spreadsheet math is unverified.

## How curves are normally resolved (for contrast)

For a class with good wiki data, each scaling skill's damage is stored as a
`(baseDamage, factorIndex)` pair: `baseDamage` in tenths-of-a-percent, and `factorIndex` selecting
one of 24 pre-built growth curves in `data/factor_table.json` (a level 1→300 table).
This pair is resolved by sampling a skill's real per-level values from its own individual wiki
page and finding the `factorIndex` whose curve reproduces those samples with ~0% residual error
(see any `src/_reverse_engineer_<class>_factors.py`). This is the high-confidence path.

## Gap tiers used below

- **FLAGGED ASSUMPTION** — no individual wiki page exists for this skill, so only its level-1
  value is known. `(baseDamage, factorIndex)` is derived from that single point using a
  per-skill-type convention (burst/DoT → factorIndex 12, buffs/passives → 22, basic attack → 21).
  The curve *shape* past level 1 is unverified.
- **ASSUMED MASTERY SHAPE** — a mastery bonus's existence and rough size is known, but its exact
  level breakpoints/deltas are borrowed from a sibling class's real mastery table rather than
  the class's own (which doesn't exist).
- **Documented simplification** — the underlying mechanic is fully known, but modeling it exactly
  would require state-machine tracking (exact proc timing, HP thresholds, resource-stack economies)
  that doesn't exist anywhere in this project; a steady-state or duty-cycle approximation is used
  instead, matching how every other class in this project handles the same class of mechanic
  (see the Shadower/Night Lord precedent for accumulating-stack passives).
- **Not modeled (out of scope)** — the mechanic has no DPS effect representable in this project at
  all (crowd control, Accuracy/Evasion/Defense, HP/MP recovery, movement speed, range/AoE-radius
  increases, Companion Summoning Time). This tier is intentional scope, not a gap to close later.

---

## Clean — no flagged gaps

**FP-Mage, Ice-Lightning-Mage, Night Lord.** Every scaling skill has a confirmed individual wiki
page with a full level 1→200 curve; every mastery bonus is a real, directly-sourced value.

---

## Minor, self-contained flags

### Bowmaster
- **Flash Mirage**: its own "activation chance/damage increases based on Attack Speed" text is
  self-contradictory between English and Korean wiki text (0.4× vs 2×) — left at a flat,
  non-AS-scaled proc rate. *Documented simplification.*

### Marksman
- **Blink Bolt**: a toggle mechanic (recasting consumes/teleports the mark, ending the buff early)
  modeled as an unconditional always-on Attack% buff (100% uptime) rather than its real
  alternating on/off behavior. Real gameplay could plausibly show ~50% uptime instead.
  *Documented simplification, flagged as a likely overestimate.*

### Shadower
- **Into Darkness**: full verified curve, but no sibling skill anywhere in this project to
  cross-check the resolved tuple against (lower confidence than usual, not missing data).
- **Channel Karma**: no individual wiki page exists, but it's a flat Attack% passive already
  assumed reflected in the user's own Inputs (per this project's "always-on passive" convention)
  — only its Sensitivity-sheet marginal delta is affected, not live DPS.

### Hero
*(Two gaps originally flagged here — Puncture's wound boss-damage curve and Enhanced Raging
Blow's Lv.134 combo-excess-stack mastery — were closed after this file was first written; see
"Gaps closed" below.)*

### Dark Knight
*(Two gaps originally flagged here — Gungnir's Descent's Lv.134 mastery and Iron Wall's
Defense→STR conversion — were closed after this file was first written; see "Gaps closed" below.)*

---

## Systemic gaps — the wiki itself lacks the data

These classes were added to `idle.maplestorywiki.net` without individual per-skill pages ever
being written (confirmed via direct 404s on every plausible skill-page URL, cross-checked against
known-good control pages to rule out rate-limiting/fetch errors). This is a wiki-side data gap,
not something resolvable by trying harder against the same source — closing these would require
either a different data source (community spreadsheets, in-game data mining) or accepting the
FLAGGED-ASSUMPTION convention permanently.

### Bishop
*(Most of this class's original gaps were closed via real user-provided in-game data points —
see "Gaps closed" below. What's left:)*

**Divine Protection** is FLAGGED ASSUMPTION: only its level-1 value (25% Defense) is confirmed;
no second data point exists yet to resolve its real growth curve (currently assumed factorIndex
22, the standard buff/passive convention).

Two Big Bang/Bahamut precedent-reuses remain unaffected and still high-confidence: they reuse
Ice-Lightning-Mage's own already-verified Chain Lightning/Elquines tuples directly, since their
level-1 wiki wording is word-for-word identical — and this was independently re-confirmed via a
real level-182 data point for both, matching with ~0% residual.

### Paladin
6 of its own unique skills are **FLAGGED ASSUMPTION**: Close Combat, Noble Demand, Heaven's
Hammer, Divine Mark, Divine Judgment, Maple Hero (Paladin).

Additional documented simplifications specific to Paladin:
- Close Combat / Noble Demand / Divine Mark's own damage-taken-increase "Weaken" effects have no
  stated duration/proc-chance on the Mastery table — left unmodeled entirely.
- Divine Judgment's own "+30% Basic Attack Damage" buff component is unmodeled (only its
  detonation proc is modeled) — stacking another duty-cycle layer on an already-dynamic proc rate
  was judged out of scope.
- Vessel of Light has no stated internal cooldown anywhere (pure proc) — its uptime uses a
  bespoke approximation (`MIN(1, Duration × ProcChance% × Basic Attack Rate)`) instead of the
  standard cooldown-driven helper every other buff in this project uses.

Blast (Paladin's own 4th-job basic attack) is **not** a gap — it reuses the universal
cross-class basic-attack constant, same as every other class.

### Buccaneer
**Every skill except Hook Bomber is FLAGGED ASSUMPTION** — zero individual wiki pages exist for
any of Buccaneer's 28 skills (worse than Bishop). Hook Bomber (basic attack) is the one exception,
reusing the universal cross-class constant.

Additional gaps specific to Buccaneer:
- **Maple Hero (Buccaneer)**: the wiki's own source text is genuinely truncated mid-sentence —
  `"Increases Final Damage of the following skills: Serpent Assault 60%, Corkscrew..."` — cutting
  off before Corkscrew Blow's own percentage and a likely third buffed skill (Corsair's own Maple
  Hero has exactly 3 entries, so Buccaneer's probably does too). Only Serpent Assault's confirmed
  60% is modeled; Corkscrew Blow's share and the missing third skill are unmodeled. **Incomplete,
  flagged for later** — if the wiki is ever fixed, or another source surfaces the real numbers,
  this should be revisited.
- **Perseverance**'s Mastery "+5% Attack when HP≥50%" needs HP tracking that doesn't exist
  anywhere in this project — unmodeled.
- **Mastery Lv.54 "Advanced Dash - Protection"** references a skill ("Advanced Dash") absent from
  the entire skill overview list — unmodeled, no base skill to attach the bonus to.
- **Crossbones, Speed Infusion, Time Leap, Roll of the Dice** have no cooldown data anywhere on
  the wiki — modeled as always-active once unlocked, a likely overestimate versus their real
  (unknown) cooldowns.
- **Assault Mode** (Sea Serpent Burst ↔ Serpent Assault ↔ Serpent Scale's stacking resource economy)
  is modeled as a steady-state duty cycle, not an exact stack-gain/mode-toggle state machine.
  *Documented simplification.*

### Corsair
**The deepest gap of any class in this project.** In addition to every base curve being FLAGGED
ASSUMPTION (same as Buccaneer, zero individual pages), **Corsair has no Mastery page at all** —
confirmed via a redlink on its own overview page's navigation footer and a direct 404. No other
class in this project — including Bishop, Paladin, and Buccaneer — is missing its Mastery data
entirely.

Per direct project decision, every Corsair mastery bonus is an **ASSUMED MASTERY SHAPE** — mapped
from Buccaneer's own real mastery table by matching skill-slot roles (e.g. Corsair's own basic
attack, Eight-Legs Easton, assumes the identical level breakpoints/deltas as Buccaneer's Hook
Bomber chain). This mapping is **incomplete, flagged for later**: five skills — Scurvy Summons,
All Aboard, Siege Bomber, Rapid Fire, Majestic Presence — got no mastery bonus at all, because no
clean Buccaneer analog exists for their crew-summon/resource-economy mechanics; they're left at
`SkillMasteryBonus% = 0` rather than forcing a poor mapping.

The wiki also provides **no job-tier, Type, Required Level, or Cooldown data whatsoever** for any
Corsair skill (a flat two-column Skill/Description table only) — every cooldown value used in
Corsair's workbook is itself an assumption by convention, not sourced.

One item with only partial patch coverage: **Broadside**'s Aug 13 patch note only covers its
initial summon-burst damage (3800%→5000%); the sustained "3300% every 2s" follow-up phase's patch
status is unstated, so it's left at its (also-assumed) wiki level-1 value.

---

## Gaps closed since this file was first written

These were flagged in an earlier pass and have since been fixed — kept here for the audit trail,
since "why did the DPS number change" is a fair question to be able to answer later.

- **Hero — Puncture's wound boss-damage-taken curve**: previously a flat level-200 ceiling value
  (18%); now a live FactorTable lookup (factorIndex 21/baseDamage 100 tenths%, already fully
  resolved in `_reverse_engineer_hero_factors.py` but not wired into the row — the data existed,
  it just wasn't connected).
- **Hero — Enhanced Raging Blow's Lv.134 "combo final damage per excess stack" mastery**:
  previously entirely unmodeled; now a flat +100% Final Damage term once level ≥134 (2 excess
  stacks above the 5 required to use the skill, once Advanced Combo's 7-stack cap unlocks at
  Lv.110, × 50% each) — reusing the same steady-state max-stacks convention Combo Attack/Combo
  Synergy already use.
- **Dark Knight — Gungnir's Descent's Lv.134 "base damage -50%, +4 strike count" mastery**:
  previously entirely unmodeled; now a level-gated flip of the row's own BaseDamage
  (18000→9000 tenths%) and HitsPerCast (2→6), net +50% total damage.
- **Hero — Sensitivity-sheet Global Monster Damage-Taken Bonus% bucket**: the main Calc sheet
  correctly included Scaring Sword's contribution in its boss/normal blend formula, but the
  Sensitivity sheet's own mirror of that same formula silently omitted it — meaning the
  Sensitivity sheet's own "Baseline Total DPS" didn't match `Summary!TOTAL DPS` whenever Scaring
  Sword was active. Fixed by hoisting the reference to a module-level constant so both formula
  builders share it.
- **Dark Knight — Iron Wall (+10% of total Defense as STR, Lv.38+)**: previously entirely
  unmodeled (no Defense-tracking input existed anywhere in the project). A tracked Defense (flat)
  + Defense % Inputs pair was added project-wide (originally for the Content Type feature's PvP
  opponent-defense estimate); Iron Wall now feeds that pair directly into STAT_DAMAGE, with its
  own Sensitivity marginal-value rows and PotentialCubes Defense % support.
- **Bishop — Invincible (+10% of total Defense as INT, Lv.35+)**: same gap and same fix as Iron
  Wall above — Bishop's own Defense-conversion skill, previously unmodeled for the same reason.
- **Sensitivity sheet — wrong-column references in several classes' per-stat recompute blocks**:
  found while verifying the Content Type feature (which made fixed-duration mode the default for
  9 of 10 content types, exposing a bug that previously only ever ran in the rarely-used
  fixed-duration mode). Several classes' Sensitivity-sheet blocks referenced column `S`/`V`
  instead of `R`/`Q` (the block's own local "CastsInFight"/"InvCooldown" columns) in their
  buff-uptime and cast-rate SUMPRODUCT formulas — silently corrupting the entire Attack% bucket
  and Basic-Attack-rate calculation for every stat's marginal-DPS test whenever fixed-duration
  mode was active. Bishop, FP-Mage, and Ice-Lightning-Mage additionally had their own block-local
  "CastsInFight"/"InvCooldown" helper columns written to the wrong column index entirely (19/22
  instead of 18/17), and FP-Mage/Ice-Lightning-Mage had a Maple Hero helper-cell placement that
  collided with (overwrote) the first two skill rows' own CastsInFight values. All fixed; see
  `CLAUDE.md`'s structural-bug catalog for the general pattern to avoid re-introducing it.
- **All 12 classes — Sensitivity sheet was missing the main-stat/sub-stat → flat Attack marginal
  delta**: this is a real, intentional in-game mechanic (1 main stat's final/effective value = 1
  flat Attack; 1 sub stat's raw value = 0.25 flat Attack, both added into the pool before ATTACK%
  applies) documented in this project's very first commit, but it was only ever implemented for
  Bishop/FP-Mage/Ice-Lightning-Mage, and even there only for the main-stat half (the sub-stat/LUK
  half was never implemented at all). A user cross-checking the Sensitivity sheet's Flat INT row
  by hand ("we should be gaining here from both the stat prop and the flat attack gain") flagged
  that the numbers looked too low. Investigating that led me to mistakenly conclude the existing
  `int_attack_delta` term was a double-counting bug (it looked like it duplicated the same delta
  already flowing through STAT_DAMAGE) and remove it — this was wrong; the two contributions are
  independent stat mechanics, not duplicates. The user caught this ("Did we mistakenly delete this
  logic?") and clarified the exact ratios. Fix: restored the term as `mainstat_attack_delta`
  (main-stat ratio 1, sub-stat ratio 0.25) for Bishop/FP-Mage/Ice-Lightning-Mage, and extended it
  — at the user's explicit request — to all 12 classes, using each class's own main/sub stat pair
  (STR/DEX for Hero/Paladin/Dark Knight/Buccaneer, DEX/STR for Bowmaster/Marksman/Corsair, LUK/DEX
  for Night Lord/Shadower). Remains Sensitivity-only (a marginal-delta correction for the "+1 unit"
  test), not part of the live main-sheet Total DPS — matching the original design intent, since the
  main Calc sheet still assumes the user's own Flat ATTACK entry already includes this
  contribution. Verified per class: TOTAL DPS unchanged, Sensitivity main/sub-stat rows' marginal
  DPS increased appropriately.
- **Bishop — real in-game data closed most of the class's remaining gaps**: the user provided
  real level-N values (mostly at level 111/182/192) for Heal, Bless, Angel Ray, Genesis, Advanced
  Blessing, Holy Magic Shell, Holy Symbol, Triumph Feather, Maple Hero, Blood of the Divine, and
  Invincible. Combined with each skill's already-known level-1 anchor, this let every one of them
  be resolved via the same 2-point curve-matching method `_reverse_engineer_<class>_factors.py`
  scripts use — all matched an existing factorIndex with ~0% residual (mostly factorIndex 21,
  correcting the FLAGGED-ASSUMPTION default of 22 for these specific skills; Angel Ray/Genesis
  confirmed 12; Holy Symbol/Maple Hero/Blood of the Divine confirmed their existing assumed
  factorIndex). None of these are FLAGGED ASSUMPTION anymore. Also found via a fresh wiki fetch
  (the Mastery page didn't exist the first time this class was built — it now does, fully
  populated, confirming every mastery bonus already coded was correct) and one previously-unknown
  skill: **Divine Protection** (Lv.60, +25%→X% Defense for 15s every 20s, duty-cycle-averaged into
  a new Defense%-bonus bucket that feeds both Invincible and the PvP-defense estimate) — added as
  a new SKILL_ROWS entry. **Shining Ray** (Lv.60, 3rd-job basic attack, confirmed real) stays
  unmodeled by explicit decision, since it's fully superseded by Big Bang at Lv.100 and every
  workbook defaults to level 200.
- **Bishop — Invincible's Defense→INT conversion rate isn't flat 10%, it scales with level**: the
  user's real level-111 data point (13.3%, vs. the wiki's flat-looking "10%") resolved to
  factorIndex 22 with ~0% residual — the same growth curve every other buff/passive skill in this
  project already uses. Fixed by computing the rate live via a FactorTable lookup instead of a
  hardcoded 0.10.
- **Dark Knight — Iron Wall given the same level-scaling treatment as Bishop's Invincible, by
  user request**: unlike Invincible, Iron Wall's own wiki page still shows a flat, unchanging 10%
  at every sampled level (1 through 100) — so this is applied by analogy to Invincible's confirmed
  behavior, not from independently-confirmed Dark-Knight-specific data. Flagged in the build
  script's own docstring; revisit if real Dark Knight data ever contradicts the flat-10%-per-wiki
  reading.
- **All 12 classes — added a buff-casting startup delay to fixed-duration DPS, plus a CDR
  Milestone Sweep on the Sensitivity sheet**: Cooldown Reduction behaves unlike every other stat in
  fixed-duration content (dungeon/boss fights with a time cap) — a skill's cast count is
  `INT(fight_duration/effective_cooldown)+1`, so DPS only improves in discrete jumps when reduced
  cooldown lets one more full cast fit, not smoothly. The Sensitivity sheet's existing single "+1
  second" test couldn't show where those jumps are or how big they are, so a new dedicated section
  (10 full shadow Calc+Summary recomputes, one per absolute CDR value from 0.5s to 5.0s) was added
  after all the normal STAT_SWEEP blocks, with a compact "CDR (s) / Total DPS / Gain vs prior step
  / % Gain vs current CDR" table on top. While building this, we also found the existing
  fixed-duration model had **no start-of-fight delay at all** — every skill (and every buff) was
  assumed to fire its first cast at `t=0`, as if cast in parallel with everything else. In reality
  the character casts their buffs first, sequentially, before their first damage-skill cast, so the
  real usable window for a damage skill's cast count is `fight_duration -
  buff_cast_startup_time`, not the raw fight duration. `buff_cast_startup_time` = (count of
  currently-unlocked, actively-cast [`CostsActionSlot=TRUE`] buff-category [`BuffDuration(s)>0`]
  skills) × (1 / Actions Per Second) — a new Summary-sheet row, applied to every content type (not
  just the new sweep), gated behind the same `fixed_duration_active` flag every other
  fixed-duration-only formula already uses (steady-state DPS is completely unaffected — confirmed
  identical before/after per class). Buffs themselves keep their own unmodified `t=0` cast-count
  math (they're what causes the delay, not affected further by it); only non-buff (damage) rows
  have their available duration reduced, floored at 0 casts (not the naive formula's "always at
  least 1") if buff-casting alone would consume the whole fight. A subtle bug surfaced during
  implementation, worth remembering for any future duration-related change: a skill's own DPS-rate
  formula (`rate_or_exact_hits_expr`/`exact_total_hits_expr`) takes the cast count as one input
  and a *separate* duration argument for the last cast's partial-tick-window truncation — both
  must use the identical (startup-reduced, for non-buff rows) duration, or multi-tick DoT-style
  skills (ICD>0) silently compute a wrong rate even though single-hit skills look fine. Each
  class's own buff-row list differs (a few classes — Corsair, Buccaneer — have zero real recastable
  buffs at all, so `buff_cast_startup_time` is always 0 there and this is a no-op); see each
  `build_<class>_workbook.py`'s own `BUFF_ROW_KEYS`/`STARTUP_BUFF_ROW_KEYS` for the exact list.
- **Open, not yet fixed — buff recast-timing uses a buff's raw cooldown instead of its
  CDR-reduced cooldown**: found while implementing the entry above, out of scope for that change.
  A buff's own cast *count* in fixed-duration mode (`CastsInFight`/`R{row}`) correctly reflects
  Cooldown Reduction (via `effective_cooldown_expr`). But `buff_uptime`/`buff_uptime_block`'s own
  `uptime_fraction_or_exact_expr` call passes the buff's *raw* `Cooldown(s)` (not the CDR-adjusted
  value) as the spacing between recasts when computing `exact_buff_uptime_expr`'s
  `last_cast_start = (casts-1)*cooldown`. Currently invisible at the default `skill_cooldown_decrease
  = 0`, since raw and effective cooldown are identical there — but once a user has real CDR, this
  will understate how tightly-packed a buff's recasts actually are (using the wider raw-cooldown
  spacing while the cast count itself already assumes the narrower CDR-reduced one), slightly
  underestimating that buff's uptime. Present in every class that has a recastable buff row.
