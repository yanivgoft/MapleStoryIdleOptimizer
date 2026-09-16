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
*(One gap originally flagged here — Gungnir's Descent's Lv.134 mastery — was closed after this
file was first written; see "Gaps closed" below.)*

---

## Systemic gaps — the wiki itself lacks the data

These classes were added to `idle.maplestorywiki.net` without individual per-skill pages ever
being written (confirmed via direct 404s on every plausible skill-page URL, cross-checked against
known-good control pages to rule out rate-limiting/fetch errors). This is a wiki-side data gap,
not something resolvable by trying harder against the same source — closing these would require
either a different data source (community spreadsheets, in-game data mining) or accepting the
FLAGGED-ASSUMPTION convention permanently.

### Bishop
~11 of ~15 skills are **FLAGGED ASSUMPTION**: Magic Guard, Heal, Bless, Angel Ray (+ its own Boss
Monster Damage proc row), Genesis, Holy Magic Shell, Holy Symbol, Advanced Blessing, Triumph
Feather, Maple Hero, Infinity, Blood of the Divine.

Two exceptions are higher-confidence: **Big Bang** and **Bahamut** reuse Ice-Lightning-Mage's own
already-verified Chain Lightning/Elquines tuples directly, since their level-1 wiki wording is
word-for-word identical.

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
