# Known Gaps & Assumptions

> **Status (2026-11-24):** these gaps are properties of the MODEL, so they apply equally to the web app (`engine/`, which reproduces each workbook's model bit-exact for
> up to 4 equipped artifacts) and to the frozen Excel workbooks. Wording below often says "workbook"; read it as "the model". Where the app differs from the workbooks it is
> noted in `engine/README.md` and `APP.md` (5 artifact slots, blank "Max Enemies In Range" = uncapped, equipped artifacts per content type). Test file names mentioned in
> older entries (`test_<class>_artifacts.py`, `test_<class>_sensitivity.py`) are now `tests/golden/test_artifacts.py` / `test_sensitivity.py --class <class>`.

This file catalogs every place where a class's DPS workbook relies on an assumption, an
approximation, or an unmodeled mechanic — as opposed to a value directly confirmed from the
live wiki (`idle.maplestorywiki.net`), a second independent source (`maplestoryidle.info` — see
below), and cross-referenced against the official patch notes.
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
- **Flash Mirage**: real mechanic confirmed via a second, more authoritative source
  (maplestoryidle.info/jobs.html — added to the project's domain allowlist specifically for this
  cross-check) after a Discord report flagged the wiki's own numbers as wrong. Real: 20% chance
  (scaling linearly up to 50% as Attack Speed goes 0%→150%, confirmed with the user) to hit up to 5
  nearby enemies for **550%** damage (previously modeled as a flat 20% chance for 5% damage — off
  by two orders of magnitude). Its "chance per attack" is per *attack line* — one per cast of any
  of the character's own active-slot attacks (Arrow Stream, Covering Fire, Phoenix, Arrow Platter,
  Hurricane, ...), each counted once regardless of its own hit count (Hurricane's 20-hit volley is
  1 attack line, not 20 — confirmed with the user; an earlier version of this fix wrongly
  multiplied by Arrow Stream's own HitsPerCast, over-counting by ~6x). The wiki's own infobox claim
  of a real 5-second internal cooldown turned out to be correct after all — a mid-session
  correction wrongly discarded it, inferring "no cooldown" purely from maplestoryidle.info's schema
  not surfacing a cooldown field for this skill, caught by a user follow-up question. Modeled as a
  genuine 5s floor between procs, with the chance re-rolling on every attack line once the floor
  expires (confirmed with the user as the intended mechanic, vs. the alternative of "one roll per
  5s window, no retries") — average cycle time = `5 + 1/(chance × Summary!APS)`, folded into
  Cooldown(s) with ProcChance%=100 since the additive `+5` floor doesn't decompose into independent
  Cooldown/ProcChance columns the way a pure no-floor chance does. Also added a previously-unmodeled
  mastery ("Flash Mirage - Damage" +50% at Lv.68). FactorIndex corrected from an initial 0
  (non-scaling) to 21 (per user direction — the same curve as this class's own Final Attack: Bow/
  Advanced Final Attack, both also Type=Passive skills dealing a direct % damage proc): the "0"
  assumption came from the wiki's own per-level table showing a uniform value at every sampled
  level, which turned out to be unreliable for this skill (the same page also had the damage/target
  numbers themselves wrong). baseDamage 5500 tenths% is treated as the level-1 anchor — *FLAGGED
  ASSUMPTION*, since maplestoryidle.info gives only a single snapshot value with no level context.
- **Hurricane**: was missing entirely from this workbook until a Discord bug report caught it, and
  once added, a second report + the same maplestoryidle.info cross-reference caught the wiki's own
  numbers as wrong too: real Lv.103 4th-job active skill, 20 hits (35 once Lv.134 mastery unlocks)
  for **800% damage to up to 7 enemies** in front (previously modeled as 7% to a single target —
  again off by roughly two orders of magnitude, and single-target instead of AoE). Real 40s
  cooldown (confirmed by both sources) — its own 20 hits fire within that one cast/cooldown, so
  (per the Flash Mirage note above) it only ever contributes ONE attack-line opportunity to other
  skills' "chance per attack" mechanics, not 20. Mastery level thresholds also corrected
  (Lv.108/134, not the wiki Mastery page's Lv.106/132). FactorIndex corrected from an initial 0
  (non-scaling) to 12 (per user direction — the same multi-hit-active-skill curve as its closest
  mechanical siblings, Covering Fire/Phoenix/Arrow Platter), for the same "wiki's flat-per-level
  table was unreliable" reason as Flash Mirage above; baseDamage 8000 tenths% treated as the
  level-1 anchor — *FLAGGED ASSUMPTION*, same caveat as Flash Mirage's own. Its own "fire faster
  with higher Attack Speed" text remains too vague to model precisely (unclear what specifically
  speeds up) — *Documented simplification* for that part only; the skill itself is now fully and
  correctly modeled.
- **Final Attack: Bow**: previously folded into Arrow Stream's own coefficient as a steady-state
  average addition (scaling with Basic Attack Damage%, since that's Arrow Stream's own bucket) —
  per user direction, split out into its own independent skill row, since Final Attack is actually
  affected by Skill Damage%, not Basic Attack Damage%. Modeled as a real, undecomposed
  ProcChance%=25 against the character's own total attack-line rate (Cooldown(s) = 1/Summary!APS —
  one attack line per cast across every active-slot skill, same accounting as Flash Mirage above;
  no real internal cooldown of its own, unlike Flash Mirage). Also corrected two mastery level
  thresholds against maplestoryidle.info (Final Attack - Damage: Lv.54 not the wiki's Lv.52;
  Advanced Final Attack - Enhance: Lv.113 not the wiki's Lv.111).
- **Soul Arrow: Bow (Attack%)**: factorIndex corrected from an inconsistent 0 (non-scaling) to 22,
  per user direction — every other "Magic Critical pattern" row in this file (Armor Break, Bow
  Expert, Extreme Archery) already uses 22; this row was the one outlier. Purely a reference/
  display correction — this row's own coefficient is never wired into Total DPS (its Attack% is
  assumed already baked into your own Inputs, per its own Note), so this does not change any DPS
  number, only what the Skills/Calc sheet displays as the "expected" value at your level.

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

- **Flash Slash**: factorIndex corrected from 0 (non-scaling) to 12, per direct user correction.
  The wiki's own per-level table showed a flat 350% at every sampled level, which was originally
  trusted over the wiki's own prose ("+5%/level") as a "wiki content bug" — this was backwards:
  the flat table was itself the error, the same failure mode already caught on Bowmaster's
  Hurricane/Flash Mirage/Soul Arrow (a wiki per-level table reading flat is not reliable evidence
  a skill is truly non-scaling).

### Dark Knight
*(Two gaps originally flagged here — Gungnir's Descent's Lv.134 mastery and Iron Wall's
Defense→STR conversion — were closed after this file was first written; see "Gaps closed" below.)*

---

## Skill-level growth beyond 300 (2026-11-24, all classes) — engine differs from the frozen workbooks above total level 300

The frozen Excel workbooks (FactorTable sheet, `data/factor_table.json`) stop at skill level 300 and clamp there; the engine (`engine/common/factors.py`) does NOT: the growth curves in use
(8, 10-19, 21, 22, 23) are exact piecewise-linear formulas (equal to the table for levels 1..300, `tests/golden/test_factor_formulas.py`) continued past 300 with their last slope.
- Evidence: the user's Night Walker readings at total level 322 (17 readings, four curves: 12, 21, 22, 23) equal the straight-line continuation (and the 279 / 219 / 151 readings equal the table).
- Effect: a character whose total skill level exceeds 300 (4th job = `(character level - 100) x 3 + skill4 + all`, common at level 200; 3rd job with large bonuses) now gets higher damage than the workbooks
  show for the same inputs (late-game test character: +30 to +70% total DPS depending on the class, `tests/golden/test_factor_extension.py`); at total level <= 300 engine and workbook are bit-identical.
- The Excel workbooks / builders / verify scripts were NOT updated (frozen reference). The workbook goldens are kept untouched and compared in the engine's LEGACY CLAMP mode (`MSI_FACTOR_LEGACY_CLAMP=1` /
  `factors.legacy_clamp()`; never set in production), so the independent workbook verification of the 12 classes still holds exactly for everything the workbooks can express. The Dawn Warrior engine-native
  snapshot was refreshed in the extended mode (`golden_refresh_log.md`).

## Fifth artifact slot (all 12 classes, 2026-11-23) — engine-only, NOT verifiable against the workbooks

The game gained a 5th artifact slot.  The app / engine / API accept up to **5** equipped artifacts (`engine/artifacts.py` `MAX_SLOTS` = 5), but the 12 workbooks still have **4** slot rows on
their Inputs sheet (`WORKBOOK_SLOTS` = 4; adding a row means editing all 12 builders, the golden references and the Excel import map — a separate, heavy task).  So:

- Everything verified against Excel (the per-class `test_<class>_artifacts.py` goldens and the sensitivity goldens, all with <= 4 equipped) is unchanged and bit-exact.
- **With 5 equipped the result is the engine's own composition of the workbook-verified per-artifact effects**, not a number Excel ever produced.  Each effect only feeds buckets / per-artifact rows and
  does not depend on its slot, so a 5th artifact is the same step a 4th already is; `tests/golden/test_artifact_five_slots.py` checks the internal consistency (finite, order-independent, same
  artifact once, non-negative artifacts never lower DPS, Sensitivity's equip-toggle row == the engine's 5-slot minus 4-slot total to 1e-12, a 6th what-if on 5 equipped works).  A user who equips 5
  artifacts in the app and the same 4 in Excel will see the 5th artifact's effect only in the app.
- The workbook import (web) reads the 4 slot rows; the 5th slot is left to the user.  Potential lines / star levels are per artifact (not per slot) and unaffected.

---

## Artifacts (FP-Mage) — Documented simplifications

Equip Effect for all 36 artifacts, plus a reference-only Artifact Potentials calculator (see its
own bullet below) — Inventory Effect and Resonance Amplification remain out of scope entirely.
Each item below is a **Documented simplification** (the mechanic is fully known, but exact
state-machine tracking — real MP, real target buff/debuff state, real per-second enemy counts,
real proc timing, companions — doesn't exist anywhere in this project), confirmed with the user.

- **Book of Ancient / Athena Pierce's Old Gloves**: both the direct stat (Crit Rate%/Attack Speed%)
  AND the dependent bonus computed from it (Crit Damage/Max Damage) are assumed already manually
  folded into the character's own Inputs when equipped — only Sensitivity's marginal delta reacts
  to them (the "baked into Inputs" convention, extended below to 3 more artifacts).
- **Clear Spring Water / Soul Pouch**: same "baked into Inputs" convention — their Final Damage
  bonus (active only in the 5 dungeon-named content types / PvP respectively) is assumed already
  reflected in `Inputs!final_damage` when equipped.
- **Reindeer's Spear**: only its BASE (1x, normal-monster) Defense Penetration is baked into
  `Inputs!def_pen`; its Attack% and its extra PvP(2x total)/boss(3x total) Defense Penetration
  multiple are real, live terms.
- **"Growth Dungeon"** (Clear Spring Water's gate, Secret Map's tripling, part of Old Music Box's
  "dungeons" clause) is mapped to all 5 dungeon-named content types (Weapon/Equipment/
  Enhancement/EXP/Hero Dungeon) — confirmed by the user, since this content type doesn't exist by
  that name in the workbook's own Content Type list.
- **"Arena"** (Soul Pouch's gate) is mapped to the existing PvP content type — confirmed by the user.
- **Old Music Box**: the real mechanic (a proc on being inflicted with a debuff, 25s duration, 20s
  cooldown) isn't modeled — no debuff-infliction rate exists anywhere in this project. Collapsed to
  a flat content-type uptime assumption per the user: 0% in Chapter Hunt/Breakthrough/the 5
  Growth Dungeon types, 100% in World Boss/PvP, 60/70 (≈85.7%) in Chapter Boss.
- **Flaming Lava**: the target's buff/debuff/barrier state isn't modeled at all — always assumes
  the target has a debuff (the wiki's middle tier), per the user, except in Chapter Hunt, where the
  target has none of the three (buff/debuff/barrier) and this is exactly 0.
- **Icy Soul Rock**: MP isn't modeled (see `[[mp_cost_modeling_shelved]]`) — assumes 50% of time
  at ≥75% MP (doubled Crit Damage bonus) and 50% at 50-75% MP (base bonus), averaging to 1.5x the
  base star value, per the user.
- **Secret Map / Reindeer's Spear enemy count**: no per-second enemy-count concept exists anywhere
  in this project — "every content with normal monsters" is assumed to have 10+ enemies, "boss" is
  assumed to have exactly 1, per the user. Secret Map's Final Damage bonus therefore only affects
  the normal-monster branch of Breakthrough/Hero Dungeon's DPS split, never the boss branch (and
  Reindeer's Spear's boss/PvP-only Defense Penetration correction is the mirror image — boss/PvP
  branch only, never normal).
- **Peach Tree Herb Pouch / Silver Pendant**: opponent buff-state (Peach Tree's "once per battle if
  target has buffs" clause) and target-death resets against normal monsters (both would restart
  the enemy-damage-taken debuff early) aren't modeled — no monster-time-to-kill concept exists
  anywhere in this project. Silver Pendant's 5-slot FIFO queue is further approximated as an M/M/5/5
  Erlang-loss queue (deterministic 5s window → exponential-mean-5s service), the same class of
  approximation as the Potential Cubes EV model's plug-in reroll-count formula. Both are exactly 0
  in Chapter Hunt, per the user (not relevant to that content type).
- **Hexagon Necklace**: models a one-time, monotonic battle-start stack ramp (0→3 over 60s, never
  decreasing within a fight) — confirmed directly from the user's own worked examples, not the
  wiki's own (less precise) text.
- **Cursed Doll / Lit Lamp / Star Rock**: extend the "baked into Inputs" convention further —
  Cursed Doll's Final Damage (accuracy/evasion behavior not modeled at all — always assumes the
  "give Final Damage" branch, never the evade-triggered loss), Lit Lamp's Final Damage (World Boss
  content only), and Star Rock's Boss Monster Damage. Star Rock's wiki text also increases the
  *character's own* incoming damage taken — a defensive downside with no DPS effect — ignored per
  the user (not to be confused with *enemy* damage taken, an existing, different bucket).
- **Bottle of Emotion**: its flat Attack% is real/live (same shared bucket as every other
  Attack%-granting artifact); its Attack-Speed-*dependent* Final Damage (continuous "for every 3%
  of Attack Speed exceeding 60%" scaling, converted to a continuous per-1%-point shape the same
  way Ring of Cycles was fixed earlier this session) is baked into Inputs — delta-only in
  Sensitivity, same shape as Book of Ancient's dependent Crit Damage.
- **Horn Flute** (FP-Mage, rewired 2026-11-12): Final Damage while a companion is out (doubled in Chapter Boss). The character's own portion is the full
  value x `Companion!horn_uptime` (share of the player's boss DAMAGE - not of the time - dealt while the summoned companion is out; each second is weighted by Hexagon stacks, Charm and KO/stun windows from the Timeline strip, so a 30 s window at the end of a 70 s fight counts ~53%, not 43%; falls back to the time share when no fixed fight length exists. The window itself: summon time, duration, Breakthrough extension and Chapter Hunt's D/90 all come
  from the companion model; PvP and Chapter Hunt now count, the old fixed [7 s, 37 s] window and its PvP/Hunt exclusion are gone). The companion's own portion is the
  snapshot ratio `rhoH` = (1 + full)/(1 + fight-average): the unit already carries the player's fight-average flute, so this swaps it for ONE full flute. The companion
  does NOT get the player's flute on top of its own - the flute only starts when the companion is summoned, after the snapshot (user, 2026-11-12). The uptime uses the full-coverage
  summon (candidate 0) so it cannot depend on the damage numbers (that would be a circular reference); if the chosen candidate is a later summon the flute
  uptime is slightly over-stated. With no companion chosen the same timing is assumed, so the artifact keeps a value. Cube pricing for Summoning Time Increase
  holds the flute's fight-average fixed (second-order). Other classes still use the old fixed window until their companion port.
- **Arwen's Glass Shoes** (FP-Mage, wired 2026-11-19): a REAL, live effect — Companion Summoning Time Increase % (star 0 = +20, star 5 = +40, user-confirmed
  2026-11-19). While equipped (any slot) the companion's effective summoning time increase = the Inputs value + the artifact's value; it flows everywhere the
  Inputs value flows (Companion sheet host `inc`, every Sensitivity block - the swept stat still sweeps the INPUT, the artifact stays added -, the Companion
  sheet's `b0` baseline of the Summoning-Time potential lines table and so the CompanionsInput table and the cube script's `b0 + roll`, the engine's
  `summon_time_inc`). Its Sensitivity "(Equip)" row re-runs the full summon-time search and the Status/KO strip (the extra duration can flip summon timings,
  e.g. Blaze Wizard's 3rd stun cast at +13.667%). Stars 1-4 are linear steps (user-confirmed 2026-11-19):
  20 / 24 / 28 / 32 / 36 / 40 (`ARTIFACT_STAR_VALUES["arwens_glass_shoes_summon_time_increase_pct"]` in the builder, one table). Verified by equivalence:
  Total DPS with the shoes at Inputs x equals Total DPS without them at Inputs x + the star value, bit-for-bit (tests/golden/artifact_cases.py `EQUIV_PAIRS`).
  The verify scripts ignore artifacts (slots cleared), so they never see this term.
- **Artifacts with NO DPS effect** (user, 2026-11-19; a fact, not missing information - the Artifacts sheet rows are labelled
  "no DPS effect (reason)", `ARTIFACT_NO_DPS_EFFECT` in the builder, `no_dps_effect` / `reason` in the engine schema): Pig's Ribbon, Mushmom's Cap, Lunar Dew
  (stats the model does not use), Zakum's Stone Piece, Horntail's Scale, Pink Bean's Giant Rib (raid content), Ancient Text Piece (Guild Conquest content).
- **Alliance Badge / Charm of the Undead**: real, live Attack%, same shared bucket as every other
  skill/artifact Attack% source. Charm of the Undead's periodic uptime (5s active every 10s,
  starting at t=10s) is a new pattern for this project (distinct from Hexagon Necklace's monotonic
  ramp) — verified by hand against the user's own timing description.
- **Sayram's Necklace**: the wiki's 2+-target/1-target gating is ignored entirely per the user —
  both the Normal Monster Damage and Boss Monster Damage bonuses are always granted simultaneously,
  feeding the existing branch-specific `boss_damage%`/`normal_damage%` buckets directly.
- **Ancient Text Piece**: gated on "[Guild Conquest]", a content type this project doesn't model at
  all — no DPS effect (see "Artifacts with NO DPS effect" above).
- **Fire Flower**: the wiki's real per-nearby-target scaling (capped at 10) is replaced with a
  fixed assumption per the user — always exactly 10 targets against normal monsters, always
  exactly 1 against boss/PvP.
- **Lunar Dew / Pig's Ribbon**: pure defensive/recovery procs (HP/MP regen, damage immunity) with
  no DPS effect at all, per the user (see "Artifacts with NO DPS effect" above).
- **Chalice**: the real mechanic (2%-chance-per-hit proc, 100% on a boss kill, granting a 30s Final
  Damage buff, re-appliable) collapses to a single simplified model per the user: always active
  during exactly the last 30 seconds of the fight (`[MAX(0,duration-30), duration]`), relevant
  whenever `monster_type` is `"normal"` or `"breakthrough"` — 0 in pure boss-only content and PvP.
  Uses branch-specific overlap math against the same `boss_appear_time` concept Candle already
  uses (generalized to handle pure-"normal" content, where there's no boss phase at all); verified
  against hand-worked numbers for Breakthrough, Hero Dungeon, and pure-normal content.
  **Chapter Hunt (steady state, updated 2026-11-07):** modeled as a renewal process instead: 100 kills/min (`CHALICE_KILLS_PER_MINUTE`)
  x 2% proc chance per kill (`CHALICE_PROC_CHANCE`), the 30s timer resets on a new proc, so the buff is on iff at least one of the
  last 50 kills procced: uptime = 1-0.98^50 = 63.6% (not the 'on for 1 of every 30s' point estimate, and not 0 as before) -> Chalice
  adds 63.6% x the star value (19.07% at star 5) to the normal-branch Final Damage; total DPS x1.1907 at star 5. Assumes proc per
  KILL (not per hit) and a refresh (not stacking) on re-proc; fixed-duration normal content (EXP/Equipment/Weapon/Enhancement
  dungeons) and Breakthrough/Hero Dungeon keep the last-30-seconds model.
- **Pink Bean's Giant Rib / Horntail's Scale / Zakum's Stone Piece**: each has a generic-looking
  "+Final Damage%" clause on the wiki, but these are raid-boss-specific artifacts for content this
  project doesn't model at all — no DPS effect, per the user (see "Artifacts with NO DPS effect" above).
- **Mushmom's Cap** (the user's "Mushroom Cap"): Accuracy-vs-target's-Evasion conditional damage,
  not modeled (same category as Cursed Doll's ignored accuracy behavior) — no DPS effect in this model.
- **The Contract of Darkness**: real, live Crit Rate, gated to the boss branch only (never PvP,
  never normal) — the first artifact needing a *crit-blend* ratio correction (analogous to
  Reindeer's Spear's defense-factor ratio correction, but against `N = L*(1-cr/100)+M*(cr/100)`
  instead of the defense formula).
- **Shamaness Marble**: baked directly into the *existing* `Inputs!buff_duration_increase_pct`
  stat — no new bucket needed.
- **Artifact Potentials** (up to 3 rollable stat lines per artifact, gated by the artifact's own
  Star Level — 2 lines for Epic/Unique, 3 for Legendary): modeled as a **pure reference
  calculator** on the ArtifactsInput sheet, not a live Calc-sheet term — per the user, a line's
  real stat impact is assumed already manually folded into the character's own Inputs once kept
  (same "baked into Inputs" convention as Book of Ancient etc.), so no potential selection changes
  Total DPS. Reuses the same `Sensitivity!H<row>` DPS-per-unit values and stat-name conventions as
  equipment Potential Cubes. 4 of the 12 possible stats (Damage Taken Decrease %, Defense %,
  Accuracy, Status Effect Damage %) have no matching DPS bucket anywhere in this project and always
  show 0% DPS gain — Defense % in particular will need real modeling once this expands to Dark
  Knight (Iron Wall's Defense→STR conversion) and Bishop.

---

## Artifacts (Bishop) — Documented simplifications

Same Equip Effect model, data tables, and per-artifact simplifications as FP-Mage (see the
section above) — no Bishop-specific differences in any artifact's own assumptions. One forward
reference now applies for real rather than hypothetically: Bishop's own Invincible mechanic
converts a level-scaling % of Defense into INT, so a "Defense %" potential-line roll is not
*entirely* inert for Bishop the way it is for every other class modeled so far — it's still 0 DPS
impact for now (no Defense-related potential bucket is wired into that conversion), but Bishop is
the first class where modeling it for real would actually change a number, not just be a
theoretical gap. Not modeled this pass; flagged for whenever Defense-related potentials get
real treatment project-wide.

## Artifacts (Bowmaster) — Documented simplifications

Same Equip Effect model, data tables, and per-artifact simplifications as FP-Mage/Bishop (see
above) — no Bowmaster-specific differences in any artifact's own assumptions. Two Bowmaster-
specific wiring decisions from this port, both verified numerically (Book of Ancient's compounding-
order hand-check, matched exactly):

- Book of Ancient's dependent Crit-Damage-from-Crit-Rate bonus reacts to Bowmaster's own **live**
  global Crit Rate source (Sharp Eyes, duty-cycle averaged) in addition to Inputs!crit_rate and any
  other equipped artifacts — unlike FP-Mage/Bishop, where every Crit Rate source besides artifacts
  is already baked into Inputs. Both the add case (currently unequipped) and the remove case
  (currently equipped) include Summary's own Sharp Eyes bonus row, matching whatever real total
  crit rate actually produced today's baked-in Inputs!crit_damage value.
- The previously-unused "Global Monster Damage-Taken Bonus %" placeholder on the Summary sheet
  (`R_MONSTER_DMG_BONUS`, a hardcoded 0 stub with no real source in this kit) now holds
  `AGG_ENEMY_DMG_TAKEN` (Peach Tree/Silver Pendant's combined bonus), applied additively to both the
  boss and normal branches — reusing an existing bucket rather than adding a new one, since the
  semantics (an unconditional, both-branches-equally additive %) already matched exactly.

Two real bugs in this port were found later, while porting Artifacts to other classes by
comparison against Bowmaster's own file, and have since been fixed directly in
`build_bowmaster_workbook.py` (both re-verified: zero-error `formulas` scan, `verify_bowmaster_workbook.py`
exact match, unaffected at default Inputs):
- Soul Contract's Chapter-Hunt-only cooldown decrease was computed (`artifact_soul_contract_pct_expr`)
  but never actually multiplied into any skill's effective cooldown, on either the main Calc sheet or
  its Sensitivity-sheet mirror — found while porting to Corsair, which does wire it correctly.
- The PotentialCubes-EV "Critical Rate %" cap-check (`dps_per_unit_expr`) tested raw `Inputs!crit_rate`
  against the 100% cap, ignoring Sharp Eyes' own live bonus (`R_CRIT_RATE_BONUS`) and any equipped
  artifacts' `AGG_CRIT_RATE` — meaning the cap could flip late (still recommending Crit Rate% potential
  lines past the point they're actually worth 0) — found while porting to Night Lord.

---

## Artifacts (Buccaneer) — Documented simplifications

Same Equip Effect model, data tables, and per-artifact simplifications as FP-Mage/Bishop/Bowmaster
(see above) — no Buccaneer-specific differences in any artifact's own assumptions. Unlike
Bowmaster, Buccaneer has no live global Crit Rate/Attack Speed/Crit Damage buff bucket of its own
(`R_CRIT_RATE_BONUS`/`R_AS_BONUS`/`R_CRIT_DAMAGE_BONUS` are unused placeholders on Buccaneer's
Summary sheet), so Book of Ancient/Athena's Gloves' dependent-bonus deltas only need
`Inputs!crit_rate`/`Inputs!attack_speed` plus other artifacts — the same shape as FP-Mage/Bishop,
not Bowmaster's Sharp-Eyes wrinkle.


## Artifacts (Ice-Lightning-Mage) — Documented simplifications

Same Equip Effect model, data tables, and per-artifact simplifications as FP-Mage/Bishop/Bowmaster/
Buccaneer (see above) — no ILM-specific differences in any artifact's own assumptions. Like
Buccaneer (not Bowmaster/Marksman), ILM has no live global Crit Rate/Attack Speed buff bucket, so
Book of Ancient/Athena's Gloves' dependent-bonus deltas only need `Inputs!crit_rate`/
`Inputs!attack_speed` plus other equipped artifacts. The "Global Monster Damage-Taken Bonus %"
bucket (`AGG_ENEMY_DMG_TAKEN`) is folded additively into ILM's existing `MONSTER_DMG_BONUS` Summary
row rather than a separate placeholder, since ILM has no unused `R_MONSTER_DMG_BONUS` stub the way
Bowmaster did. Both mandatory hand-spot-checks pass: Book of Ancient's compounding-order delta
(Sensitivity's reported DPS Gain) matches an independent full-rebuild-vs-baseline delta exactly;
Reindeer's Spear's Sensitivity "% Gain" row decreases (113.92% → 107.43%) as `def_pen` sweeps
50→99.9, confirming diminishing-returns saturation.

---

## Artifacts (Marksman) — Documented simplifications

Same Equip Effect model, data tables, and per-artifact simplifications as FP-Mage/Bishop/Bowmaster
(see above) — no Marksman-specific differences in any artifact's own assumptions. Like Bowmaster,
Marksman has its own live global Crit Rate source (Sharp Eyes, duty-cycle averaged) — Book of
Ancient's dependent Crit-Damage-from-Crit-Rate bonus correctly includes it in both the add case
(currently unequipped) and remove case (currently equipped), matching Bowmaster's precedent exactly.
Both mandatory hand-spot-checks pass: Book of Ancient's compounding-order delta (Sensitivity's
reported DPS Gain, 220,890.895) matches an independent full-rebuild-vs-baseline delta exactly;
Reindeer's Spear's Sensitivity "% Gain" row decreases (112.00% → 105.62%) as `def_pen` sweeps
50→99.9, confirming diminishing-returns saturation.

---

## Artifacts (Corsair) — Documented simplifications

Same Equip Effect model, data tables, and per-artifact simplifications as FP-Mage/Bishop/Bowmaster
(see above) — no Corsair-specific differences in any artifact's own assumptions. Like Buccaneer/
Ice-Lightning-Mage (not Bowmaster/Marksman), Corsair has no live global Crit Rate buff bucket
(`R_CRIT_RATE_BONUS` is an unused placeholder), so Book of Ancient's dependent Crit-Damage bonus
only needs `Inputs!crit_rate` plus other equipped artifacts. Unlike Bowmaster, Corsair's Soul
Contract cooldown-decrease IS correctly wired into `eff_cd_r`/`eff_cd_row` on both the main Calc
sheet and its Sensitivity mirror (this port is what surfaced the Bowmaster gap, since fixed there —
see "Artifacts (Bowmaster)" above). Both mandatory hand-spot-checks pass: Book of Ancient's
compounding-order delta (Sensitivity's reported DPS Gain, 29,076.492) matches an independent
full-rebuild-vs-baseline delta exactly; Reindeer's Spear's Sensitivity "% Gain" row decreases
(116.40% → 109.77%) as `def_pen` sweeps 50→99.9, confirming diminishing-returns saturation.

## Artifacts (Dark Knight) — Documented simplifications

Same Equip Effect model, data tables, and per-artifact simplifications as FP-Mage/Bishop/Bowmaster
(see above) — no Dark-Knight-specific differences in any artifact's own assumptions. Like
Bowmaster/Marksman, Dark Knight has its own live global Crit Rate/Crit Damage source (Lord of
Darkness, proc-chance × duty-cycle averaged) — Book of Ancient's dependent Crit-Damage-from-Crit-
Rate bonus correctly includes it (via `R_CRIT_RATE_BONUS`) in both the add case (currently
unequipped) and remove case (currently equipped), matching Bowmaster/Marksman's precedent exactly.
The "Global Monster Damage-Taken Bonus %" bucket (`AGG_ENEMY_DMG_TAKEN`) is folded additively into
Dark Knight's existing `R_MONSTER_DMG_BONUS` Summary row (Evil Eye, all-types + Dark Resonance,
boss-only), applied to both the boss and normal branches — reusing an existing bucket rather than
adding a new one, since Dark Knight has no unused placeholder row the way Bowmaster did.

One forward reference now applies for real rather than hypothetically, same as Bishop's own
Invincible note above: Dark Knight's Iron Wall mechanic converts a level-scaling % of Defense into
STR, so a "Defense %" potential-line roll is not *entirely* inert for Dark Knight the way it is for
every other class without such a conversion — it's still 0 DPS impact for now (no Defense-related
potential bucket is wired into that conversion, matching Bishop's own choice), but flagged for
whenever Defense-related potentials get real treatment project-wide. Nothing added by this port
touches, duplicates, or otherwise interacts with the Iron Wall conversion itself
(`iron_wall_str_bonus_expr`/`STAT_DAMAGE`) — it remains exactly as it was before Artifacts.

Both mandatory hand-spot-checks pass: Book of Ancient's compounding-order delta (Sensitivity's
reported DPS Gain, 246,061.971) matches an independent full-rebuild-vs-baseline delta exactly
(2,045,318.352 equipped − 1,799,256.381 unequipped = 246,061.971); Reindeer's Spear's Sensitivity
"% Gain" row decreases (106.94% → 103.07%) as `def_pen` sweeps 50→99.9, confirming diminishing-
returns saturation.

---

## Artifacts (Hero) — Documented simplifications

Same Equip Effect model, data tables, and per-artifact simplifications as FP-Mage/Bishop/Bowmaster
(see above) — no Hero-specific differences in any artifact's own assumptions. Like Buccaneer/
Ice-Lightning-Mage/Corsair (not Bowmaster/Marksman/Dark Knight), Hero has **no live global Crit
Rate buff bucket** — `R_CRIT_RATE_BONUS` on the Summary sheet is an unused placeholder ("no live
Crit-Rate-buff source exists in this kit") — so Book of Ancient's dependent Crit-Damage-from-
Crit-Rate bonus only needs `Inputs!crit_rate` plus other equipped artifacts, the same shape as
FP-Mage/Bishop. The "Global Monster Damage-Taken Bonus %" bucket (`AGG_ENEMY_DMG_TAKEN`) has no
existing multiplicative bucket to fold into (Hero has neither an Elemental Decrease Multiplier nor
a spare placeholder row the way Bowmaster/Dark Knight/ILM did), so it's combined additively with
`AGG_DAMAGE` into a single new `(1+(AGG_DAMAGE+AGG_ENEMY_DMG_TAKEN)/100)` multiplicative term in
the main damage formula (and its Sensitivity mirror) instead of reusing an existing row.

While porting, also found and fixed two of the same real bugs already documented above (both
existed in Hero's own file before this port, matching the same root causes found for Bowmaster/
Night Lord and fixed the same way here):
- Soul Contract's Chapter-Hunt-only cooldown decrease was computed on the Artifacts sheet but never
  actually multiplied into any skill's effective cooldown (`eff_cd_r`/`eff_cd_row`) on either the
  main Calc sheet or its Sensitivity mirror — fixed by wrapping both with the same
  `*(1-artifact_soul_contract_pct_expr(...)/100)` factor Corsair already uses.
- The PotentialCubes-EV "Critical Rate %" cap-check (`dps_per_unit_expr`) tested raw
  `Inputs!crit_rate` against the 100% cap, ignoring equipped artifacts' `AGG_CRIT_RATE` (Hero has
  no live Crit Rate bonus bucket to also ignore, unlike Bowmaster/Night Lord's version of this same
  bug) — fixed to include `Summary!$B$R_CRIT_RATE_BONUS+AGG_CRIT_RATE` in the cap check, same as
  Night Lord's fix.

Both mandatory hand-spot-checks pass: Book of Ancient's compounding-order delta (Sensitivity's
reported DPS Gain, 63,383.274) matches an independent full-rebuild-vs-baseline delta exactly
(1,152,442.960 equipped [crit_rate=20, crit_damage=12, star 5] − 1,089,059.686 unequipped
[crit_rate=0, crit_damage=0] = 63,383.274); Reindeer's Spear's Sensitivity "% Gain" row decreases
(113.45% → 106.99%) as `def_pen` sweeps 50→99.9, confirming diminishing-returns saturation.

---

## Artifacts (Night Lord) — Documented simplifications

Same Equip Effect model, data tables, and per-artifact simplifications as FP-Mage/Bishop/Bowmaster
(see above) — no Night-Lord-specific differences in any artifact's own assumptions. Like Bowmaster/
Marksman/Dark Knight, Night Lord has its own live global Crit Rate source (`R_CRIT_RATE_BONUS`:
Critical Throw Lv.47 mastery + Dark Sight Crit Rate, duty-cycle averaged) — Book of Ancient's
dependent Crit-Damage-from-Crit-Rate bonus correctly includes it in both the add case (currently
unequipped) and remove case (currently equipped), matching Bowmaster's precedent exactly. The
"Global Monster Damage-Taken Bonus %" bucket (`AGG_ENEMY_DMG_TAKEN`) is added as its own extra
additive term inside `boss_dmg_pct_r`/`normal_dmg_pct_r` (and their Sensitivity mirror) rather than
folded into an existing Summary row — Night Lord's own `R_MONSTER_DMG_BONUS` (Venom Lv.82 Weaken +
Frailty Curse enemy debuff) is a real, already-in-use bucket, not an unused placeholder the way
Bowmaster's was, so reusing it would have double-purposed a row that already has its own meaning.

While porting, also found and fixed the same PotentialCubes-EV "Critical Rate %" cap-check bug
later found in Bowmaster's own file (see "Artifacts (Bowmaster)" above) directly in this port
before it ever shipped: `dps_per_unit_expr`'s cap-check now tests
`Inputs!crit_rate+Summary!$B$R_CRIT_RATE_BONUS+AGG_CRIT_RATE` against the 100% cap, not raw
`Inputs!crit_rate` alone.

Both mandatory hand-spot-checks pass: Book of Ancient's compounding-order delta (Sensitivity's
reported DPS Gain, 1,896,399.813) matches an independent full-rebuild-vs-baseline delta exactly
(8,734,040.572 equipped [crit_rate=50, crit_damage=77.096, star 5] − 6,837,640.759 unequipped
[crit_rate=30, crit_damage=40] = 1,896,399.813); Reindeer's Spear's Sensitivity "% Gain" row
decreases (117.00% → 109.42%) as `def_pen` sweeps 50→99.9, confirming diminishing-returns
saturation.

---

## Artifacts (Shadower) — Documented simplifications

Same Equip Effect model, data tables, and per-artifact simplifications as FP-Mage/Bishop/Bowmaster
(see above) — no Shadower-specific differences in any artifact's own assumptions. Like Bowmaster/
Marksman/Dark Knight/Night Lord, Shadower has its own live global Crit Rate source
(`R_CRIT_RATE_BONUS`: Dark Sight Crit, duty-cycle averaged) — Book of Ancient's dependent
Crit-Damage-from-Crit-Rate bonus correctly includes it in both the add case (currently unequipped)
and remove case (currently equipped), matching Bowmaster's precedent exactly. The "Global Monster
Damage-Taken Bonus %" bucket (`AGG_ENEMY_DMG_TAKEN`) is folded directly into the existing
`R_MONSTER_DMG_BONUS` Summary row's own formula (which already carries a real bucket, Venom Lv.82
Weaken) on the main Calc/Summary sheets, since addition is associative and doing so needed no new
row; the Sensitivity shadow-block mirror instead adds it as its own separate additive term
alongside the block-local (level-gated) Venom Weaken recompute, since the shadow block can't
reference a single live Summary cell's sub-components — both produce the identical total.

While porting, also found and fixed the same PotentialCubes-EV "Critical Rate %" cap-check bug
documented in Bowmaster's own entry above (see "Artifacts (Bowmaster)"), directly in this port
before it ever shipped: `dps_per_unit_expr`'s cap-check now tests
`Inputs!crit_rate+Summary!$B$R_CRIT_RATE_BONUS+AGG_CRIT_RATE` against the 100% cap, not raw
`Inputs!crit_rate` alone.

Both mandatory hand-spot-checks pass: Book of Ancient's compounding-order delta (Sensitivity's
reported DPS Gain, 343,976.690) matches an independent full-rebuild-vs-baseline delta exactly
(5,409,770.342 equipped [crit_rate=20, crit_damage=14.296, star 5] − 5,065,793.650 unequipped
[crit_rate=0, crit_damage=0] = 343,976.692); Reindeer's Spear's Sensitivity "% Gain" row decreases
(116.78% → 109.42%) as `def_pen` sweeps 50→99.9, confirming diminishing-returns saturation.

---

## Artifacts (Paladin) — Documented simplifications

Same Equip Effect model, data tables, and per-artifact simplifications as FP-Mage/Bishop/Bowmaster
(see above) — no Paladin-specific differences in any artifact's own assumptions. Like Buccaneer/
Ice-Lightning-Mage/Corsair/Hero (not Bowmaster/Marksman/Dark Knight/Night Lord/Shadower), Paladin
has **no live global Crit Rate buff bucket** — `R_CRIT_RATE_BONUS` on the Summary sheet is an
unused placeholder ("no live Crit-Rate-buff source exists") — so Book of Ancient's dependent
Crit-Damage-from-Crit-Rate bonus only needs `Inputs!crit_rate` plus other equipped artifacts, the
same shape as FP-Mage/Bishop/Hero. The "Global Monster Damage-Taken Bonus %" bucket
(`AGG_ENEMY_DMG_TAKEN`) is written directly into Paladin's own previously-unused
`R_MONSTER_DMG_BONUS` placeholder (a hardcoded 0 stub — Close Combat/Noble Demand/Divine Mark's own
weaken effects are flagged but not modeled), same pattern as Bowmaster's own port. The "Attack%
Bucket Multiplier" (`R_AVGBUFF`, Vessel of Light + HP Recovery) similarly gained `AGG_ATTACK_PCT`
as one more additive term inside the existing bucket.

Before any of the above could be wired in, this port found and fixed a real corruption bug left
over from an earlier session's data-model extraction: a stray, over-long FP-Mage text extraction
had duplicated `COMPUTED_INPUT_ROWS`/`IB()`/`build_readme_sheet` into `build_paladin_workbook.py`.
Since Python keeps the *last* definition of a duplicated top-level name, the duplicate
`build_readme_sheet` — still titled "Fire/Poison Arch Mage — DPS Calculator: How to Use This
Workbook" — would have silently overridden Paladin's real README sheet on every rebuild. Fixed by
deleting the duplicate block and merging its one genuinely new addition (the `ARTIFACT_INPUT_CELL`
lookup) into the original, correctly-titled `IB()`.

While porting, also found and fixed the same two bugs already documented for Bowmaster/Night
Lord/Hero above (both existed in Paladin's own file before this port, matching the same root
causes):
- Soul Contract's Chapter-Hunt-only cooldown decrease was computed on the Artifacts sheet but never
  actually multiplied into any skill's effective cooldown (`eff_cd_r`/`eff_cd_row`) on either the
  main Calc sheet or its Sensitivity mirror — fixed by wrapping both with the same
  `*(1-artifact_soul_contract_pct_expr(...)/100)` factor Corsair already uses.
- The PotentialCubes-EV "Critical Rate %" cap-check (`dps_per_unit_expr`) tested raw
  `Inputs!crit_rate` against the 100% cap, ignoring equipped artifacts' `AGG_CRIT_RATE` (Paladin has
  no live Crit Rate bonus bucket to also ignore, unlike Bowmaster/Night Lord/Shadower's version of
  this same bug) — fixed to include `Summary!$B$R_CRIT_RATE_BONUS+AGG_CRIT_RATE` in the cap check,
  same as Night Lord/Hero's fix.

Both mandatory hand-spot-checks pass: Book of Ancient's compounding-order delta (Sensitivity's
reported DPS Gain, 99,562.236) matches an independent full-rebuild-vs-baseline delta exactly
(1,106,247.071 equipped [crit_rate=50, crit_damage=0, star 5] − 1,006,684.834 unequipped
[real crit_rate=50, frozen at the moment of removal] = 99,562.236); Reindeer's Spear's Sensitivity
"% Gain" row decreases (114.75% → 109.50%) as `def_pen` sweeps 0→80, confirming diminishing-returns
saturation.

---

## Equipment Compare (new sheet) + a real DPS-Gain compounding fix (all 12 classes)

Every per-line "DPS Gain" total in this project — Artifact Potentials' `Total Potential DPS Gain`,
Potential Cubes EV's "current value," and the new Equipment Compare sheet below — is built from
`Sensitivity!H<row>` "$/unit" marginal-DPS values. Those are true partial derivatives (each one
computed holding every other stat fixed), so combining *two lines of the same stat* by simply
adding their raw values first is exact (two 5% Max Damage lines really are one 10% Max Damage
bucket before the damage formula ever sees it), but combining *two different stats'* independently-
computed gains by summing them is a linear/first-order approximation that silently drops a real
second-order compounding term — two stats each independently worth 1% DPS truly combine to
`1.01×1.01−1=2.0201%`, not a naive `2%`, since they live in different multiplicative buckets of the
damage formula. The gap is quadratically small for small individual gains and grows for larger
ones (two 10% lines: `21%` true vs `20%` naive).

Fixed project-wide by grouping lines by stat first (summing raw values within a group), then
combining the resulting *distinct-stat* groups multiplicatively — `combined_multiplier =
∏(1+group_i_gain/BaselineTotalDPS)`, `TotalDPSGain = BaselineTotalDPS×(combined_multiplier−1)`:
- **Artifact Potentials' `Total Potential DPS Gain`** (`ArtifactsInput!L<row>`, all 12 classes):
  was a naive `=E+H+K` sum of the 3 lines' independent gains; now grouped-then-multiplied. Hand-
  verified per class: 2-same-stat-lines still collapses to exactly the old sum (proving the fix
  doesn't change anything for the common case), 2-different-stat-lines now exceeds the old sum by
  the expected second-order amount.
- **`potential_cubes_ev.py`'s `current_dps_value()`** (what your currently-rolled 3 lines are
  worth) and its core `roll_distribution()` enumeration (the `line1×line2×line3` combinatorial
  model every EV/optimal-stopping calculation is built on) both had the same bug — `roll_distribution`
  in particular used to pre-convert each rolled line straight to a DPS number and discard *which
  stat it was* before summing, meaning a single cube's own 3 lines already compounded incorrectly,
  not just across separate items. Both now route through one shared `combined_dps_gain()` helper.
  This is a single canonical script (`src/potential_cubes_ev.py`), copied identically into all 12
  class folders — the fix only had to happen once.
- **New "Equipment Compare" sheet** (all 12 classes): lets you enter a "Current Equip" and a
  "New Equip" — a fixed Attack line plus up to 5 more stat lines each, picked from a 21-stat
  dropdown (Main Stat flat/%, Attack, Min/Max Damage %, Damage %, Crit Rate/Damage %, Boss/Normal
  Monster Damage %, Defense Penetration %, Defense (flat), the 5 Skill Level Bonus tiers, Final
  Damage %, Basic Attack Damage %, Skill Damage %, Attack Speed %) — and reports the DPS% delta
  between them (`New% − Current%`), using the same grouped-then-multiplied math, made *exact* here
  (not an approximation) since both equips are concrete, fixed sets of lines rather than an
  open-ended reroll search. Pure calculator sheet — nothing else in the workbook reads from it, so
  it needed no Calc/Summary/Sensitivity/`verify_<class>_workbook.py` changes anywhere. "Defense
  (flat)" has no DPS effect (and no Sensitivity row) in any class except Dark Knight (Iron Wall) and
  Bishop (Invincible), which convert part of it into a damage stat — the dropdown option exists
  everywhere for consistency but resolves to 0 DPS gain in the other 10 classes.

Every hand-spot-check (compounding vs. naive sum, same-stat-collapses-to-a-plain-sum, and the
Equipment Compare delta cell) matched the expected math exactly in all 12 classes — see each class's
own git history for the exact numbers if needed.

---

## Sensitivity "mult"-kind invariant fix — checked and fixed across all 12 classes

A real bug, found via a Discord bug report: a purely multiplicative stat (currently only "Final
Damage %", `STAT_SWEEP` kind `"mult"`) is tested in Sensitivity via a "+1% of the current
multiplier" bump — `override_expr_for("mult", key)`. Since Total DPS is exactly proportional to
`(1+FinalDamage/100)` (it's just one factor in a product), this test should **always** report
exactly 101% (+1.00% DPS) in every class, at every character state — a simple, universal invariant
worth spot-checking after any change near this bucket. Bowmaster's own Sensitivity sheet reported
less than that (confirmed independently against the real Calc sheet, not just the Sensitivity
shadow block: ~100.896% instead of 101%) whenever Mortal Blow's steady-state Final Damage bonus was
nonzero — root cause: `override_expr_for`'s "mult" branch only bumped the raw `Inputs!final_damage`
value, but the K-column formula's actual Final-Damage bucket is `(1+(Inputs!final_damage+Mortal
Blow's bonus)/100)` — two terms sharing one bucket. A flat +1%-of-raw-value bump undershoots a true
+1%-of-the-combined-bucket bump whenever the bucket has *other* baked-in additive terms besides the
raw Input.

Fix, applied identically in every affected class: `override_expr_for` now bumps `(base+extra)`
together (via a small `MULT_KIND_EXTRA_REF` map, `{"final_damage": "Summary!$B$<row>"}` pointing at
whatever skill's bonus shares the bucket) and solves back for the correct raw override value; the
Sensitivity table's displayed Old/New Value columns for "mult" kind now also show the combined
bucket total (not just the raw Input) so a user's own manual new/old sanity check matches the real
DPS ratio.

Checked all 12 classes' Sensitivity Final Damage row against the "always exactly 101%" invariant —
**6 needed the fix, 6 were already correct** (either no same-bucket extra term exists, or none is
currently nonzero by default):

| Class | Extra bucket-mate | Fixed? |
|---|---|---|
| Bowmaster | Mortal Blow (steady-state FD bonus) | Yes |
| Marksman | Mortal Blow (steady-state FD bonus) | Yes |
| Buccaneer | Crossbones + Time Leap + Speed Infusion (live AS-linked) | Yes |
| Corsair | Jolly Roger (live, always-active-once-unlocked) | Yes |
| Hero | Enrage (FD half) + Combo Synergy (steady-state/duty-cycled) | Yes |
| Paladin | Divine Shield + Guardian + Divine Blessing + Greater Vessel of Light | Yes |
| Bishop, FP-Mage, Ice-Lightning-Mage, Dark Knight, Night Lord, Shadower | none / already correct | No fix needed |

Verified per fixed class: Sensitivity's Final Damage row now reads exactly 101.00000...% regardless
of the extra bucket-mate's value, Total DPS unchanged, `verify_<class>_workbook.py` still matches,
zero-error `formulas` scan clean.

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
5 of its own unique skills are **FLAGGED ASSUMPTION**: Close Combat, Noble Demand, Heaven's
Hammer, Divine Mark, Divine Judgment.

**Maple Hero (Paladin)** was originally FLAGGED ASSUMPTION too (no wiki page exists at all) — its
level-1 ratios (Noble Demand 20%, Rush 30%, Close Combat 80%, Final Attack 150%) are now
**CONFIRMED** via a maplestoryidle.info cross-reference that states the same four numbers
verbatim. The growth curve past level 1 is still an assumed shape (matching Hero/Bowmaster/Dark
Knight's own Maple Hero), since neither source gives a full per-level table for this skill.

**Close Combat / Noble Demand / Divine Mark's own damage-taken-increase "Weaken" effects** were
originally unmodeled (the wiki gave no duration to drive a duty-cycle calc) — now modeled as a
duty-cycle-averaged addition to the Global Monster Damage-Taken Bonus % bucket, using real
durations confirmed via maplestoryidle.info (Close Combat +10%/10s @ Mastery Lv.44, Noble Demand
+12%/10s innate, Divine Mark +20%/10s @ Mastery Lv.138) — same steady-state-duty-cycle pattern as
Ice-Lightning-Mage's own Freezing Breath - Weaken.

Additional documented simplifications specific to Paladin:
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
- **Maple Hero (Buccaneer)**: RESOLVED via maplestoryidle.info cross-reference (a direct game
  capture, not a wiki page), which gives the full, untruncated text: "Increases Final Damage of
  the following skills: Serpent Assault 60%, Corkscrew Blow 40%." — only TWO skills, not a guessed
  third. Corkscrew Blow's own 40% share is now modeled (MAPLE_HERO_RATIOS).
- **Perseverance**'s Mastery "+5% Attack when HP≥50%" needs HP tracking that doesn't exist
  anywhere in this project — unmodeled.
- **Mastery Lv.54 "Advanced Dash - Protection"** now has a real base skill to attach to (Advanced
  Dash's own full kit is visible via maplestoryidle.info — mobility skill, 6s cooldown, "cancels
  the skill being used") — still unmodeled, since its usage pattern in an auto-combat rotation is
  ambiguous (it's not a normal damage/buff cast).
- **Crossbones, Time Leap**: RESOLVED — both are real, action-costing Type=Active casts (confirmed
  via maplestoryidle.info, not passives as previously assumed), with real cooldowns (Crossbones
  28s/12s duration, Time Leap 65s/40s duration). CostsActionSlot corrected False->True, duty-cycle
  averaged instead of always-active.
- **Speed Infusion**: RESOLVED — real 35s cooldown/15s duration confirmed via maplestoryidle.info
  (previously modeled as always-active once unlocked); its live AS-linked Final Damage formula is
  now multiplied by the real duty cycle.
- **Roll of the Dice's own dice component**: RESOLVED — confirmed via maplestoryidle.info
  (identical wording to the wiki) to have a real 7s-roll/5s-duration duty cycle, now modeled as a
  5/7 multiplier instead of always-active; factorIndex corrected from 0 to 22.
- **Several real cooldown/mastery bugs found via maplestoryidle.info cross-reference** (a direct
  game capture, treated as more authoritative than the wiki's own assumed-by-convention values):
  Corkscrew Blow cooldown 20s->21s, Octopunch 15s->16s (Sea Serpent's Rage/Raging Serpent Assault
  share this cooldown, updated in lockstep), Nautilus Strike 45s->33s (~36% faster casts). Three
  masteries were missing entirely and are now added: Sea Serpent's Rage - Damage +100% @Lv.122,
  Raging Serpent Assault - Damage +50% @Lv.130, Nautilus Strike - Damage +50% @Lv.126. Quick
  Motion's own AS%/mastery corrected (6%->6.1%, added a previously-missing +5%p @Lv.24 mastery).
- **Assault Mode** (Sea Serpent Burst ↔ Serpent Assault ↔ Serpent Scale's stacking resource economy)
  is modeled as a steady-state duty cycle, not an exact stack-gain/mode-toggle state machine.
  *Documented simplification.*

### Corsair
**The deepest gap of any class in this project** — until this session. In addition to every base
curve being FLAGGED ASSUMPTION (same as Buccaneer, zero individual wiki pages), **Corsair has no
Mastery page on idle.maplestorywiki.net at all** — confirmed via a redlink on its own overview
page's navigation footer and a direct 404. maplestoryidle.info, however, has a full "game capture
provided by player" data set for Corsair (same as Buccaneer) — cross-referencing it closed the
overwhelming majority of this class's gaps.

Per direct project decision (pre-dating this session), every Corsair mastery bonus had been an
**ASSUMED MASTERY SHAPE** — mapped from Buccaneer's own real mastery table by matching skill-slot
roles. maplestoryidle.info now provides Corsair's own REAL, independent mastery/cooldown data,
which **confirmed several of those role-mapped assumptions were exactly right** (Eight-Legs
Easton's full damage/boss-damage/strike mastery chain, Nautilus Strike's shared-with-Buccaneer
tuple and mastery) but also **found real, sizable errors**:
- **A genuine 10x magnitude bug**: Broadside's sustained-turret phase was modeled at 3300%
  damage/tick (following the wiki's own text) — maplestoryidle.info (both its base skill
  description AND its own Aug 13 patch overlay, consistently) confirms the real value is **330%**,
  a full order of magnitude smaller. Fixed.
- **Several real cooldown corrections**, all confirmed via maplestoryidle.info's direct game
  capture (more authoritative than this project's own by-convention assumptions): Swift Fire
  18s->17s, Scurvy Summons 20s->35s (previously wrongly assumed = the crew's own 20s duration with
  immediate recast — the real mechanic has a genuine ~15s gap with no crew active), All Aboard
  updated to match Scurvy Summons' real cooldown, Blackboot Bill 20s->23s, Siege Bomber 30s->22s
  (with ActiveWindow also capped 30s->22s, since the real mechanic — confirmed by the Aug 13 patch
  text "it can immediately replace itself in auto mode" — recasts before the cannon's own natural
  30s duration ends), Brain Scrambler 15s->18s, Nautilus Strike 45s->33s, Broadside (both rows)
  30s->20s, Jolly Roger given a real 42s cooldown/18s duration (previously modeled as an
  always-active passive — it's a real Type=Active cast).
- **Real mastery corrections**: Brain Scrambler - Damage is a real +100% (not the role-mapped
  +50% taken from Buccaneer's Octopunch — Corsair's own value is double that). Majestic Presence -
  Damage +50% @Lv.134 was missing entirely, now added. The previously role-mapped Broadside +100%
  damage mastery @Lv.122 (from Buccaneer's Sea Serpent's Rage) is REMOVED — Corsair's own real
  Broadside masteries are only Lv.118 "Bombardment" (a mastery-gated attack-pattern swap, not a
  flat damage bonus) and Lv.138 "Setup" (a stacking economy), neither modeled here; the phantom
  +100% flat bonus was never real.
- **Ahoy Mateys - Final Damage** (Mastery Lv.122, +20% Final Damage for 20s upon casting Scurvy
  Summons) was entirely unmodeled — now added as a duty-cycle-averaged Final Damage term.
- Shadow Heart (5%->5.4% Crit Rate) and Quick Motion (6%->6.5% AS, +5%p @Lv.24 mastery added) were
  both assumed byte-identical to Buccaneer's own copies — maplestoryidle.info shows Corsair's real
  values are close but not identical; corrected.
- **Swift Fire - Weaken** (Mastery Lv.54, +3% target damage taken per strike, max 3 stacks/9%) and
  **Siege Bomber - Setup** / **Broadside - Setup** (max-instance-count increases) are all now known
  precisely but remain unmodeled — same complexity tier as Paladin's own Weaken debuffs / a
  multi-instance stacking economy this project has no mechanism for, judged out of scope for this
  pass.

The wiki still provides **no job-tier, Type, Required Level, or Cooldown data whatsoever** for any
Corsair skill on idle.maplestorywiki.net (a flat two-column Skill/Description table only) — but
this is now moot for every skill maplestoryidle.info covers (all of them).

**Roll of the Dice's own dice component** (shared verbatim with Buccaneer) got the same fix: real
7s-roll/5s-duration duty cycle (5/7 multiplier) confirmed via maplestoryidle.info, factorIndex
corrected from 0 to 22.

---

## Nimble Feet missing from 4 of 12 classes — a real cross-class DPS bug, not a design difference

Cross-referencing every class's Skills sheet in one table (to eyeball for more Bowmaster-style
factorIndex bugs) turned up a different kind of bug: **Bishop, Buccaneer, Corsair, and
Ice-Lightning-Mage had no "Nimble Feet" row at all**, while the other 8 classes did. Nimble Feet is
a universal 1st-Job Explorer skill — confirmed identical wording ("Increases Attack Speed by 15%
and Speed by 10% for 15 sec", 60s cooldown, reqLevel 5) on both `idle.maplestorywiki.net` and
`maplestoryidle.info` for literally every one of the 12 classes. Its absence in these 4 workbooks
was a genuine oversight (not a class-design difference — Buccaneer/Corsair's own "Quick Motion" is
a separate, unrelated flat passive), and since it's a real +15% Attack Speed self-buff that costs
an action slot, it was silently understating Total DPS in all 4 workbooks (both from the missing
AS% itself, and from missing its own small cast-rate cost).

Added to all 4 classes with the standard tuple (matching the other 8 classes' own row exactly),
wired into each class's own Attack Speed Bonus / Actions-Per-Second chain, `BUFF_ROW_KEYS`, and
(for Buccaneer/Corsair, which previously had zero live timed buffs) the buff-casting-startup-delay
and cast-rate machinery, which needed real wiring instead of a hardcoded 0/empty-list placeholder.
Verified per class: zero-error `formulas` scan, `verify_<class>_workbook.py` exact match.



## Artifact Equip-Toggle "% Gain" direction-dependence bug — fixed across all 12 classes

User-reported: the Sensitivity page's "Artifact Equip-Toggle DPS Gain" table showed a *different*
% Gain for the same artifact depending on whether it happened to currently be equipped or not,
even after manually adjusting the dependent Inputs value (e.g. Defense Penetration, for Reindeer's
Spear) to match. Example repro (FP-Mage, Reindeer's Spear, World Boss content): unequipped with
Inputs!def_pen=65.0526% showed 115.980%; equipped with Inputs!def_pen=66.8% (the same real state,
1 dose folded in) showed 113.778%.

Root cause: the underlying **dollar** gain (`DPS Gain` column) was already correct and perfectly
direction-invariant — confirmed via ground-truth testing (building a scratch copy of the workbook,
manually equipping/unequipping Reindeer's Spear and adjusting `def_pen` to match, then reading
`Summary!TOTAL_DPS` directly) across three scenarios (World Boss star 0, normal-monster star 0,
World Boss star 5): the reported `DPS Gain` matched the real difference to floating-point
precision every time. The bug was specifically in **% Gain**: its own code comment said the
"already equipped" (test-removal) direction should "reciprocal the % gain so both directions
report the same...convention" — but the formula actually implemented never did that. It divided
by `Summary!TOTAL_DPS` unconditionally in both directions, i.e. by whichever total happens to be
"real" right now — which differs depending on current equip state, even though the dollar gain
itself doesn't.

Fix: when currently equipped (testing removal), divide by the **hypothetical-unequipped** total
(`Summary!TOTAL_DPS − DollarGain`, i.e. undoing this same signed gain) instead of the real/current
total — this exactly reconstructs the invariant `(DPS with item)/(DPS without item)×100` ratio in
both directions. Verified: both equip states now report the identical % Gain to full floating-point
precision in all three re-tested scenarios. Present identically in all 12 classes (copy-pasted
code); fixed in all 12. Zero-error `formulas` scan clean on every rebuilt workbook. The underlying
`DPS Gain` ($) column was never wrong and needed no change.


## Crit Rate cap-check didn't account for Ring of Cycles / Book of Ancient — fixed in all 12 classes

User-reported: does the Potential Cubes calculator's "once Crit Rate is capped, value a roll as if
it were Critical Damage instead" substitution correctly stack with Ring of Cycles/Book of Ancient's
own crit-rate-dependent bonuses? It does not — both artifacts have a *dependent* mechanic that
keeps scaling with raw Crit Rate even past the 100% chance-to-crit cap, so the substitution's own
premise ("past 100%, Crit Rate is worth nothing on its own") is false whenever either is equipped:

- **Ring of Cycles**: once total Crit Rate >= 100%, it grants Basic Attack Damage scaling
  continuously with Crit Rate *excess* above 100%, capped at 100 excess points (200% Crit Rate
  total) — confirmed deliberately modeled this way (not a 10-point-stepped jump) specifically so a
  Crit Rate roll keeps having a smooth, real marginal value in this range.
- **Book of Ancient**: its own Crit-Damage-from-Crit-Rate conversion is a flat ratio of the *raw*
  total Crit Rate value, with no upper bound at all — it keeps converting indefinitely past 100%.

Fix: `dps_per_unit_expr("Critical Rate %")` now only substitutes Critical Damage's own DPS-per-unit
value when Crit Rate is capped **and** neither Ring of Cycles nor Book of Ancient is equipped;
otherwise it uses the literal `Sensitivity!H` value for Crit Rate directly, exactly like every
other stat. Verified directly: with Ring of Cycles equipped and total Crit Rate pushed to 143%, the
real literal value and the Crit Damage substitute differed by nearly 3x — and which one was larger
flipped between two different test scenarios, confirming the substitute isn't even a one-directional
safe approximation once either artifact is in play. The unequipped/genuinely-capped case was
re-verified unchanged (still correctly substitutes).

While fixing this, also found and closed a related, narrower pre-existing gap: **Buccaneer,
Corsair, Dark Knight, and Marksman's own cap-check never included the live crit-rate total at
all** — it tested bare `Inputs!crit_rate>=100`, missing both `Summary!R_CRIT_RATE_BONUS` (a real,
nonzero source for Dark Knight's Lord of Darkness and Marksman's Sharp Eyes specifically — not just
an unused placeholder) and any equipped artifacts' own `AGG_CRIT_RATE`. Every other class already
had this fixed from an earlier pass (see each class's own "Artifacts (\<Class\>)" section above).
Fixed identically in all 12 classes; zero-error `formulas` scan clean on every rebuilt workbook.


## Chapter-Stage carried-over value silently discarded on every rebuild — fixed in all 12 classes

User-reported: rebuilding a workbook (e.g. to pick up a source change) reset the per-content-type
`Chapter-Stage` Inputs row back to a generic default for most content types, discarding whatever
the user had actually entered. Root cause: a one-time migration fix from when this project moved
Chapter-Stage from one shared value to one-per-content-type values — the migration had briefly
left Breakthrough/Chapter Hunt's own "28-9"-style text wrongly duplicated into the other 6
applicable content types (which need a bare number instead, e.g. "80") — got implemented as an
unconditional rule (`CHAPTER_STAGE_TRUST_EXISTING_FOR = {"Breakthrough", "Chapter Hunt"}`) instead
of a one-time cleanup, so it kept firing on *every* rebuild forever after, silently throwing away
the user's own correctly-entered values for Chapter Boss/Weapon/Equipment/Enhancement/EXP/Hero
Dungeon and replacing them with the hardcoded default every single time. Confirmed directly: FP-Mage's
own real values (Chapter Boss 36, EXP Dungeon 112, Equipment Dungeon 110, Weapon Dungeon 112,
Enhancement Dungeon 92, Hero Dungeon 111) were reset to defaults (28/80/80/80/80/80) on rebuild;
restored by hand after the fix, confirmed to survive a subsequent rebuild correctly. Fixed in all
12 classes: carried-over values are now trusted for every content type, same as any other
per-content-type Inputs row. **If you rebuilt any class between this bug's introduction and this
fix and had customized Chapter-Stage for Chapter Boss/Weapon/Equipment/Enhancement/EXP/Hero
Dungeon, check that row after updating — only FP-Mage's loss was caught and restored directly;
other classes' real values from before this session's earlier rebuilds could not be recovered the
same way.**


## Potential vs Bonus Potential shared one pity-cap table — fixed in all 12 classes

User-reported real pity (forced-upgrade) caps for Bonus Potential: 42 (normal), 75 (rare), 150
(epic), 417 (unique), 714 (legendary) — different from regular Potential's own 30/60/120/333/714
at every tier except Legendary. This project already tracks Potential and Bonus Potential as
separate roll tracks per equipment slot, but both shared the exact same `RARITY_UPGRADE_RATES`
table (one set of pity caps applied to both), understating how much Bonus Potential cubing is
worth (a lower pity cap than reality means the EV model wrongly assumes a guaranteed upgrade kicks
in sooner than it really does).

Fix: `data/cube_potential_data.json`'s `RARITY_UPGRADE_RATES` is now keyed by potential type first
(`"Potential"`/`"Bonus Potential"`), then rarity — the roll-upgrade *rate* per tier is unchanged
(the user's correction was specifically about the pity cap, not the rate) and the roll VALUE
table itself (what stats/values are available to roll, and at what weight) is unaffected, since
that's a separate, shared table keyed only by (slot, rarity, line) with no potential-type
dimension at all. `CubeData`'s own Rarity/Rate/MaxPity reference table gained a 4th column
(`PotentialType`) and now has 12 rows instead of 6 (one full rarity progression per potential
type) — repurposing what was a pure visual spacer column (not a live-formula-consumed range, so
safe to widen). `potential_cubes_ev.py`'s `optimal_stopping_trace`/`probability_any_better_roll`
both now take `potential_type` as a parameter and index into the correct sub-table. Verified: the
standalone script runs cleanly end-to-end on every class, producing visibly different EV numbers
between the "Potential" and "Bonus Potential" sections (previously, since both just read the same
shared table, any difference between the two sections came only from each row's own current gear
state, never from the pity progression itself). Fixed in `src/potential_cubes_ev.py` and
re-copied to all 12 class folders (per this project's own "plain copy, not a symlink" convention);
zero-error `formulas` scan clean on every rebuilt workbook.



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
- **All 12 classes — Boss/Normal Monster Damage% were blended incorrectly in Breakthrough/Hero
  Dungeon content, biasing Sensitivity's marginal-value reporting toward whichever branch hits
  more targets**: the user reported that changing Boss Monster Damage% shifted how much marginal
  DPS Normal Monster Damage% appeared to be worth, even with the Boss/Normal weight held constant.
  Root cause, found in two stages:
  1. Boss/Normal Monster Damage% were summed into one shared percentage bucket
     (`(1-w)*boss_damage + w*normal_damage`) before a single multiplication — a flat +X to either
     stat produced identical dollar DPS gain regardless of how disparate the current values were
     (1000% vs 100%). Fixed by giving each branch (boss = 1 target, normal = capped target count)
     its own independent `(1+damage%/100)*targets` multiplier, blended only as the two branches'
     final DPS values — correct for the real Total DPS number, since hitting more targets really
     does more total damage.
  2. That fix alone was still wrong for Sensitivity specifically: blending the two branches'
     *dollar* DPS totals weights the comparison by each branch's raw dollar size, and the normal
     branch is inherently bigger (it hits several targets, boss hits one) — so any stat that helps
     both branches got its reported marginal value dominated by the normal branch's dollar volume,
     regardless of the actual time-weight `w` (confirmed via a regression test: Boss=1000%,
     Normal=100%, Equal/50-50 weight showed Normal's gain at 6.35x Boss's — far more than the
     ~5.5x pure diminishing-returns-from-current-value would predict). Fixed by changing
     Sensitivity's "DPS Gain"/"% Gain" columns to a time-weighted average of each branch's own
     *relative* growth ratio (`new/baseline`) instead of a dollar delta of the dollar-blended
     total — a ratio cancels out any per-branch constant a swept stat doesn't touch (target count,
     defense, crit), fixing the bias while still correctly reflecting real
     diminishing-returns-from-current-value and within-branch skill-to-skill weighting (a skill
     that hits 10 targets should still matter more to "how much does my normal-monster performance
     improve" than one that hits 3 — that part was never the bug). This also fixes Potential Cubes
     EV, which reads Sensitivity's DPS-gain numbers as its "$/unit" conversion factor for every
     potential-line stat. Monster Defense stays a single shared value for both branches in
     Breakthrough (not split) — out of scope, since splitting it would need currently-nonexistent
     data on normal-monster defense in Breakthrough content.
  While replicating this fix, found and fixed the same root-cause bug hiding in three
  class-specific code paths that had grown their own independent (and non-obvious) boss/normal
  handling: Bishop's Angel Ray boss-proc mastery (was additionally multiplying by
  `(1-normal_weight_frac)` on top of the shared blend, letting Normal Monster Damage% leak into a
  boss-only proc, and not excluding boss_damage% during PvP); Dark Knight's Sensitivity
  shadow-block mirror (applied Evil Eye + Dark Resonance's combined bonus to only one branch there,
  vs. both branches on the main Calc sheet — invisible under the old dollar-blend math since both
  sides were equally wrong, but broke the new ratio-based math since baseline and swept values then
  used inconsistent formulas); and Marksman's Bolt Surplus trigger-rate metric (derived via
  `HitRate = O/N`, which used to accidentally cancel out the shared boss/normal factor since it
  lived in both O and N — once the fix moved that factor out of N, HitRate silently absorbed a full
  Boss Monster Damage%/Mastery multiplier it was never supposed to see, until it was rebuilt as a
  dedicated target-count-only blend instead of reusing O/N division).



## Buff Mastery / Arcane Aim double-counted on top of Inputs — fixed (FP-Mage, Ice-Lightning, Bishop)

User-reported: raising Character Level from 116 to 117 (unlocking the Buff Duration passive) moved
the Buff Duration Increase sensitivity from 3.19 to 3.84, although Inputs!buff_duration_increase_pct
(the in-game stat) already includes that passive. `bdi_with_buff_mastery_expr` was adding the
passive's Calc!F value on top at level >= 117. It now returns the Inputs value unchanged; the verify
scripts match. The passive's skill row stays as an informational row.


## PvP summon / DoT windows are capped at the 15s fight (2026-10-22, all 12 classes)

Reported on FP-Mage: Ifrit was ~35% of PvP DPS (vs ~7% in boss content). PvP credits one cast per 15s fight
(cooldown = 15s) but used to tick the skill for its FULL ActiveWindow, so a 30-40s summon got ~2x the ticks that
fit in the fight (Arrow Platter's 60s window ~4x). The Calc/Sensitivity EffectiveHits column now caps the window
at `PVP_FIGHT_DURATION` in PvP (`pvp_capped_window_expr`); verify scripts mirror it (`capped_window`). Not caused
by the audit (Ifrit's own row was untouched; its +2% in the audit came from the Meditation factor fix). Effect on
PvP totals at the saved Inputs: Bowmaster -32%, Corsair -28%, Bishop -23%, Ice/Lightning -21%, FP-Mage -20%,
Marksman -17%, Night Lord -8%, Shadower -7%, Dark Knight -3%; Buccaneer/Hero/Paladin unchanged (no window > 15s).
Still a simplification: PvP gives every skill exactly one cast per fight regardless of its real cooldown.

**Whole ticks (2026-10-22, all 12 classes):** every summon / DoT now lands WHOLE hits — `INT(window/ICD + 1e-9)`
per cast (the epsilon absorbs float error such as 6/0.3), in the steady-state / PvP EffectiveHits column and in the
exact fixed-duration tick count (full windows and the truncated last cast). It used to credit fractional ticks
(Ifrit in PvP: 15s/4s = 3.75 hits; now 3, so FP-Mage Ifrit is ~19% of PvP DPS instead of 22%, and its full 30s
window in boss content is 7 hits instead of 7.5). Ticks are assumed to start one interval after the cast; if a
skill actually strikes the instant it appears it would be one more hit.

## Potential Cubes price Skill Cooldown Decrease from the CDR table (2026-10-26, all 12 classes)

`potential_cubes_ev.py` used to value every potential line as `value x CubeData's DPS-per-unit rate`; for Skill
Cooldown Decrease that rate is Sensitivity's single "+1 second" test, scaled linearly. CDR is a step function (a
fixed-duration fight only gains a cast when a cooldown crosses a threshold), so that badly misprices bigger rolls:
on the FP-Mage workbook +1s = +1.09% but the CDR milestone table says +2s = +3.44% and +3s = +5.79% (linear: 2.17% /
3.26%). The script now reads the Sensitivity sheet's "Cooldown Reduction Milestone Sweep" table instead and
interpolates it. Details worth knowing:
- Your Inputs CDR already includes the CDR on gear, so each (slot, potential type) row is priced against its own
  baseline = Inputs CDR minus that row's current CDR lines (`row_cdr_baseline`).
- If that baseline is below the table's first step (0.5s) — you have CDR in Inputs and one row holds all of it — the
  script re-evaluates the workbook once at that CDR (takes about as long as the initial load); if that fails it falls
  back to the old +1s rate. Totals above the table's top step (5.0s) extend the last segment's slope.
- The table's "Total DPS" is a dollar blend, while the Sensitivity table's % Gain is time-weighted, so in blended
  content (Breakthrough, Hero Dungeon) the table's +1s (0.99%) differs slightly from the Sensitivity "+1" row (1.09%).
  The cube calculator follows the table.
- Not changed: CubeData!K and the workbook's other consumers of `Sensitivity!H` still use the linear +1s rate (Equipment
  Compare has no CDR option; Artifact Potentials has no CDR line). The prebuilt `potential_cubes_ev-*` release
  executables need rebuilding to pick this up.

### Update 2026-11-25: step stats are priced on the real model, held lines on the same scale (web app / engine)

The engine no longer interpolates the CDR table or applies a linear rate for these stats when it has the character's inputs (`engine.cubes.pricing_from_sensitivity(..., inputs)`; the
workbook script above is unchanged).  Skill Cooldown Decrease (hat), Buff Duration Increase % (belt) and Companion Summoning Time Increase % (boots) are evaluated by re-running the
class model at the exact TOTAL (`ExactCurve` / `CompanionPricing`, memoised: ~70 runs for a full 30-row sheet).  The typed Inputs value INCLUDES the gear's lines, so
`b0 = max(0, typed - all held lines of that stat)` and a row is priced on top of `b0 + the other rows' lines`: a held line is worth `f(base + own)/f(base)`, a reroll
`f(base + candidate)/f(base)`, so a candidate that crosses a threshold (Blaze Wizard's 3rd stun at +13.667 % summoning time) shows the jump only from the totals it really
crosses it from.  The old table interpolation was off by up to 0.4 % between steps / when the typed total is off the 0.5 s grid, and by 7.8 % at +7 s (last-slope extrapolation).
Held lines above the typed total are noted (`cdr_/buff_/companion_lines_exceed_inputs:slot/type`) and b0 clamps at 0.  Every row also reports the DPS lost by removing a held
line / the row (`line_loss`, `row_loss`).  If NO lines are entered on the gear while the typed total contains them, the whole typed total is "other sources" (b0 = typed) and every
candidate is priced on top of it - enter the held lines in the Cubes tab.  Still approximate (linear rate at the typed point): Defense Penetration, Attack Speed, Critical Rate
across the 100 % cap, Basic Attack Target Increase, All Skill Level.  Cooldown Decrease is blended like Summoning Time and Buff Duration: the time-weighted relative growth of the
boss and normal branches (bug 9; user decision 2026-11-26, `engine.cubes.EXACT_STATS`); the old CDR milestone table used the dollar-blended Total.

## FP-Mage: Flame Haze's level-118 fog is Poison Mist's own fog (2026-10-26)

The mastery text is "Creates Poison Mist poisonous fog upon using Flame Haze. Poison Mist max count +1", but the
`FLAME_HAZE_FOG` row had been modeled as a Flame Haze effect (4th-job level pool, no Maple Hero bonus) and Mist
Eruption ignored the second fog. Reported by the user (fog 3.79% vs Poison Mist's 6.74% of DPS, no Mist Eruption
increase). Now: the fog row uses the 3rd-job level pool and Poison Mist's Maple Hero bonus exactly like
`POISON_MIST_DOT` (only its cast rate differs: Flame Haze's 25s vs Poison Mist's 24.5s), and from level 118 Mist
Eruption gets one more batch of explosions per Flame Haze cast (each fog explodes on its own). At the user's Inputs:
fog +74%, Mist Eruption +100%, Total DPS +12% (verify script and Sensitivity blocks updated and checked). Assumption:
both fogs' explosions are independent, each fog having its own 4s-cooldown explosions.

## PvP fight length is an Input (2026-11-01, all 12 classes)

`PVP_FIGHT_DURATION` used to be a hard-coded 15; it is now an Inputs cell ("PvP Fight Length", row 55, PvP column only,
default 15) and every PvP duration-dependent formula reads it: DoT / summon windows (capped at the fight), the
one-cast-per-fight cast rate, buff uptimes, and the time-based artifacts (Candle, Hexagon, Rainbow Snail, Charm of the
Undead, Ring of Cycles). Reported DPS is total damage / fight length, so a DoT's DPS stays the same while it is active
(its TOTAL damage shrinks with a shorter fight) and a burst skill's DPS rises (the same one cast in less time).
- **Assumption (user decision 2026-11-01) — action budget:** PvP gives every skill exactly one cast per fight, and the
  PvP Fight Length is assumed long enough to fit all of those casts. Basic Attacks only get whatever actions are left
  (possibly none). If you enter a fight length too short for the casts to fit (with the saved Inputs a 5s fight needs
  more cast actions than `Actions/s x 5` in 9 of 12 classes; FP-Mage: 10 casts vs 8.5 actions), Basic Attacks drop to 0
  but every skill is still counted in full, so DPS is overstated — the model deliberately does not correct for it.

## FP-Mage: Ignite builds up wall by wall (2026-11-01)

Ignite used to assume its 3 walls of fire were up for the whole fight (and in PvP its "cooldown 1" tick interval was
mistaken for a once-per-fight cast, which made it ~15x too low). From the game table (skill 52060): each FIRE attack
has a 50% chance to create a wall, with a **2.5s internal cooldown after each creation**; up to 3 walls, each ticking
every 1s (13% to 3 targets) for 20s. Modeled (user request): the k-th wall arrives after `k/(0.5*R) + (k-1)*2.5` s on
average (R = successful wall rolls/s - see "Proc chances roll per attack per enemy hit"; originally fire attacks/s: Basic Attacks, Flame Haze casts, Meteor Shower casts x3 meteors, Meteor Proc's procs, Ifrit's
attacks — Summary row 25, mirrored in every Sensitivity block), then the 3-wall steady state holds for the rest of the
fight (the 20s wall life is ignored, as before); whole ticks only. Steady-state content (Chapter Hunt) is unchanged
(3 ticks/s). Effect at the saved Inputs: Ignite -14% Breakthrough (40s), -8% Chapter Boss (70s), +~870% in a 15s PvP
fight (it was nearly missing), total DPS -1.1% / -1.4% / +12.9% respectively. Open assumptions: the 2.5s cooldown comes
from the game table (the in-game text doesn't mention it; set `IGNITE_TRIGGER_ICD = 0` to drop it); Flame Haze's burn
ticks and Ignite's own walls do not trigger walls. Elemental Drain (poison stacks, 50%, up to 5) has the same shape
but is still modeled as permanently maxed (and, in PvP, as a once-per-fight cast).

## Night Lord: artifact Attack% was a separate multiplier in Summary (2026-11-03)

User-reported ("Dark Sight is still broken"): all Sensitivity "DPS per +1" values and all artifact gains were negative.
Root cause: Night Lord's `Summary!B13` (Average Buff Multiplier) multiplied `(1+Art/100)` as its own factor, while every
Sensitivity block summed the artifact Attack% (Bottle of Emotion + Reindeer's Spear = 31% in the report) into the SAME
additive bucket as Dark Sight (Attack), as the other 11 classes' Summary also does and as CLAUDE.md's additive-bucket rule
requires. So Summary sat above every block by a constant factor (1.45957 vs 1.42418 in the report; 1.7% of Total DPS in
our test). Fix: `=(1+(DarkSightAtk + Artifacts!AGG_ATTACK_PCT)/100)*(1+FrailtySelfFD/100)*(1+AdrenalinFD/100)`. Verified: with
the two artifacts equipped each swept stat's Sensitivity block now equals the main sheet re-evaluated at the same Input
(ratio 1.00000); Shadower (the other Dark Sight class) was already consistent. Night Lord's total with those artifacts
drops 1.7%. Why it went unseen: the verify scripts ignore artifacts, and the Sensitivity-vs-main check had been run with
artifact slots cleared.

## Skill damage masteries MULTIPLY the skill's damage (2026-11-03, all 12 classes)

User-reported (FP-Mage): Poison Breath did 147.4T per line vs Ifrit 210.2T in the same fight, which made no sense with
the old model. Four independent in-game numbers (Poison Breath, Ifrit, Ignite, Poison Mist impact) all fit one rule: a
skill's damage mastery (e.g. "+70% damage") multiplies the skill's damage, `coefficient x (1 + m/100)` (a 363% skill with
"+70%" does 363% x 1.7, not 433%). The old "+m points" model (Option B) was off by 0.03-0.07% only on the cases where the
mastery was small relative to the base, and by tens of percent on low-base skills.
Implementation (all builders): F = `base_curve x (1 + SkillMasteryBonus%/100) + SkillFoldBonus%`, applied by a post-pass
(`apply_mastery_semantics`) over the Calc and Sensitivity-block F formulas. The new Skills column `SkillFoldBonus%` holds
terms that are NOT masteries and stay additive: Final Attack fold-ins and mixed cells that used to hold both
(Dark Knight Dark Impale / Evil Eye Shock / Revenge of the Evil Eye, Hero Raging Blow, Marksman Empowered Piercing Arrow /
Snipe, Paladin Blast). Maple Hero and Flame Haze's Poison Mist fog use the multiplier form too.
Still additive on purpose: (1) buff/debuff rows (`BuffTargetStat` set) - their masteries are "+X percentage points" of a
stat, not damage; (2) the `ADVANCED_FINAL_ATTACK_HELPER` rows (Bowmaster, Dark Knight, Hero, Marksman) - their F is a
Final Damage %, unverified in game. Basic-attack tier chains (10/11/12/13/14/15%) still sum as raw tier values first, then
multiply once (that part is unchanged from CLAUDE.md bug #2).
**Only FP-Mage was measured in game for skill masteries (Poison Breath, Ifrit, Ignite, Poison Mist); the other 11 classes assume the same mechanic.** The Basic Attack tier chain (summed raw, then one multiplier, e.g. x1.75 at 75%) was confirmed by the user in game on 2026-11-07 (class not recorded). Please confirm with one skill per
class when convenient. Verify scripts were ported (`* (1 + mastery/100) + fold`) and match the workbooks in all content
types / level boundaries tested.

## FP-Mage: Creeping Toxin hits 10 targets in normal content (2026-11-03)

Creeping Toxin's explosions chain to every nearby Poisoned target and the 2s lockout is per target, so a pack gets
about one explosion per mob per 2s. `NormalMonsterTargets` went 1 -> 10 (same as Poison Mist; user decision). Boss/PvP
unchanged. Chapter Hunt: the row's DPS x10 (0.5% -> 4.7% of total); Breakthrough x6. Assumes the pack stays Poisoned
and in range (`Max Enemies Actually In Range` still caps it). Its small boss share (about 3.5%) is real: Maple Hero
gives it only 10% Final Damage (Poison Breath 80%, Elemental Drain 150%).

## Night Lord / Shadower: Toxic Venom's trigger rate carried the triggering skills' damage% (2026-11-04)

User-reported: Toxic Venom showed about 50% of Shadower's DPS. Cause: Toxic Venom rolls 20% per target hit, and its rate
came from `Calc!S` (HitRate) = `O/N`. Since the Boss/Normal split, `O/N` is no longer a plain hit count: it carries the
triggering row's Boss Damage% / mastery / damage-taken bonus / artifact boss mults (Reindeer's Spear, Contract of Darkness,
Final Damage) in boss content (Normal Damage% in normal content), and Toxic Venom then applied its own again. Boss Damage
235% (the saved Shadower Inputs) therefore counted twice, x3.35. Fix (Marksman and Corsair already did this): `S` is now
`prefix/N x target-count-only blend` (`hit_count_s_expr`, Calc and every Sensitivity block); the verify scripts use
`target_count_mult`. Chapter Boss share with typical inputs: Shadower 16%, Night Lord 20%.
Proc rule (user, 2026-11-04): a proc chance rolls once per ATTACK per enemy hit, never per damage line. A basic attack's
5-6 damage lines are one attack; hitting 10 enemies rolls 10 times; a skill that fires several projectiles (3 meteors,
Hurricane's 20 arrows) rolls once per projectile. Toxic Venom (Night Lord, Shadower) and Marksman's Bolt Surplus were
rolling per damage line x target; `Calc!S` is now ATTACKS per second x the target-count blend (the old lines/second divided
by the row's HitsPerCast; summon/DoT ticks stay one attack per tick). Chapter Boss / Chapter Hunt share after the change:
Toxic Venom Night Lord 7.4% / 9.7%, Shadower 4.5% / 4.3%; Bolt Surplus 5.2% / 24.3% (was 23% / 65%). See "Proc chances roll per attack per enemy hit" below for the other classes.

## Proc chances roll per attack per enemy hit (2026-11-04, all classes with chance procs)

User rule: a proc chance rolls once per ATTACK per ENEMY HIT - a basic attack's 5-6 damage lines are one attack, 10 enemies hit =
10 rolls, every projectile (3 meteors, Hurricane's 20 arrows) is its own attack. Procs with a shared internal cooldown use the
probability of at least one success per attack, q = 1-(1-c)^N (N = enemies that attack hits: boss/PvP 1; normal monsters the
triggering skill's own NormalMonsterTargets, Basic Attack 6+Basic Attack Target Increase(+1 at Lv136), capped by Max Enemies In
Range), and the steady-state rate X/(1+ICD*X) with X = sum(attack rate x q). Because q depends on the branch, these procs have a
boss/PvP rate and a normal-monster rate (separate Summary cells and block-local twins in every Sensitivity block; the row's
boss-only column uses the first, normal-only column the second; the O blend is unchanged). Boss/World Boss/PvP totals do not move;
normal content goes up. Chapter Hunt effect: FP Meteor Proc 0.6% -> 1.1% of DPS (total +0.5%; +1.2% at Lv200 incl. Flame Haze DoT /
Ifrit stacks), Ignite unchanged (its 2.5s cooldown and 3-wall cap dominate), ILM Blizzard FA 0.7% -> 1.4%, Bishop Triumph Feather
8.5% -> 14.2%, Corsair Majestic Presence 4.2% -> 10.0%, Corsair/Buccaneer Nautilus FA ~x2 (<1%), Bowmaster Flash Mirage 13% -> 23.6%
and Final Attack: Bow 1.1% -> 2.1% (Chapter Boss also moved: the trigger set now counts attack casts and Hurricane's 20 arrows, not buff
casts). Toxic Venom / Bolt Surplus (no ICD): see the two sections above.
Per-class notes and choices that can be reversed:
- **Bowmaster**: Final Attack: Bow lost its surrogate cooldown (25% x attacks/s, normal: x enemies hit, 1-target payoff); Flash Mirage's
  Cooldown(s) is now only the real 5s ICD (3s from Lv122) with cycle ICD+1/X; Skill Cooldown Decrease / Soul Contract do NOT shorten it
  (user decision 2026-11-04; `FLASH_MIRAGE` is in `CDR_EXEMPT_ROW_KEYS`). PvP Final Attack and Flash Mirage used to run at 1/15 per second because the PvP
  cooldown override hit a surrogate (FA 2.4k -> 116k, FM 127k -> 439k); Quiver Cartridge / Drain still have that 1/15 PvP behaviour.
  Covering Fire's 3 hits count as one attack and Phoenix / Arrow Platter casts as one each (flagged; `ATTACKS_PER_CAST_IS_HITS_KEYS`).
- **FP-Mage**: Meteor Proc and Ignite per-branch rates (new Calc column V "EnemiesHit(normal)"); Flame Haze / Ifrit stack multipliers
  read the branch Meteor rate. The Lv126 Flame Haze burn-stacking mastery (5% per cast) is NOT rolled per enemy (each extra burn is already
  modelled as a full 10-target DoT instance; rolling per enemy would double count targets).
- **Corsair / Buccaneer**: Nautilus FA counts one attack per cast of Swift Fire, Blackboot Bill, Nautilus Strike, Rapid Fire, Brain
  Scrambler (Swift Fire's 3 bullets / Blackboot Bill's 4 hits are NOT separate attacks - flagged), Majestic Presence counts Brain Scrambler
  and Rapid Fire hits. Buccaneer's Sea Serpent Burst / Serpent Assault / Serpent Scale are guaranteed (no chance roll); Raging Serpent
  Assault's ProcChance is an uptime factor.
- **Paladin Vessel of Light**: uptime = MIN(1, duration x q x basic-attack rate) per branch; no change at default inputs (already 100%).
- **Bishop Triumph Feather**: both stages roll per enemy hit (four Summary cells TF_X1/X2 boss/normal); buff casts and Bahamut's cast stay a
  single roll. **ILM** Elemental Reset is an uptime proxy, not a roll - unchanged.
- **Still NOT per enemy (audit, flagged)**: the Final Attack folds in Hero / Paladin / Dark Knight (0.25 x FA% added to every damage LINE: per
  enemy already, but per line, not per attack; dividing by HitsPerCast would cut the basic attack ~14-16%, ~6-7% of total DPS - needs a
  decision); Hero Scaring Sword (row ProcChance 25 vs Note 35%, ~8% uptime vs ~30% under the rule); Dark Knight Lord of Darkness (30%,
  3s ICD, 8s: ~30% of the buff now vs ~100% under the rule); Hero Combo Attack / Synergy are modelled at the stack cap (the rule gives ~4.8
  concurrent stacks in boss content). Paladin Divine Judgment (every 10 basic attacks) and Dark Knight Revenge (5s cooldown) are not chance rolls.

## Companions (2026-11-11 .. 2026-11-13, FP-Mage first; all 16 companions)

Shared, table-driven engine: `src/companion_kits.py` (every companion's kit as DATA, transcribed from the user's `data/companions/MS_IDLE_COMPS_STATS.xlsx`
+ chat; human-readable dump in `data/companions/KITS_ENCODED.md`, the user's answers in `data/companions/ANSWERS_2026-11-13.md`),
`src/companion_model.py` (Excel formula generator; one chain of cells serves every companion through SUMPRODUCT masks on the `CompanionKits` sheet),
`src/companion_python_model.py` (plain-Python port: the independent check in the verify scripts AND what `potential_cubes_ev.py` re-runs).
FP-Mage is the host class so far (the other 11 classes need the same host wiring).

Inputs (per content type): `Companion` (None or any of the 16, default None) and the live `Companion Summoning Time Increase %`; each companion's
LEVEL ("Not unlocked" or 1-18) lives on the new `CompanionsInput` sheet; the summon cooldown is a constant 90 s.  Outputs: the `Companion` sheet
(column B = the chosen companion, columns C.. = every companion, then the 'b0 + X' columns and the exported host values), Summary Total / boss-only /
normal-only totals, a Sensitivity "Companion Comparison" table and a swept stat `Companion Summoning Time Increase %`.

**Effective increase = Inputs value + Arwen's Glass Shoes** (2026-11-19, FP-Mage first): the artifact adds +20% (star 0) .. +40% (star 5) while equipped (linear 20..40 steps by star, user-confirmed;
see "Artifacts (FP-Mage)"); `b0` includes it, so the potential-line tables / cube script price rolls on top of the shoes.

Rules (user): duration D = 30 s x (1 + increase%); one companion at a time; summoned >= 7 s into a fight, once, up to the end of fixed-length content
(candidate summon times are scored, best wins: s0 = T+E-D [companion lasts to the fight end], the next Hexagon Necklace stack time after s0, and the earliest summon (7 s)); Chapter Hunt period = max(D, 90).  The
companion uses the player's stat snapshot at the summon (buffs up; Hexagon stacks; Charm window; Chalice assumed procced; Defense Penetration) x level
multiplier (60/64/68/72/75/78/81/84/87/90%, Lv10+ = 90%) x its own passives (Final Damage x1.25 at Lv5/8/10 are kit rows); no skill levels, Basic Attack
Target Increase, Buff Duration or CDR.  Same action economy as the player (each cooldown skill cast takes an action slot; skills cast at the summon and
on cooldown; the 290% x5 x6 basic attack fills the rest).  Proc chances follow the per-attack-per-enemy-hit rule.  Damage-taken debuffs add into the host's
existing "enemy damage taken" bucket (like the Silver Pendant artifact); defense debuffs reduce the monster's defense value.  Stat effects of the kit are
applied as ratios on the player's buckets (Attack%, Final Damage, crit, skill/basic/boss/normal damage, max damage, defense penetration, attack speed) for
the companion AND for the player's own rows during the window (the uplift), so a support companion shows up as `uplift`.
`Companion Summoning Time Increase %`: the +1% marginal is often exactly 0 (n/a in "Units per +1% DPS"; 0.3 s would force an earlier summon that loses a
Hexagon stack).  `CompanionsInput` therefore lists the DPS of every total the boots potential lines can add up to (5, 8, 10, 12, 13, 15, 16, 18, 20, 21, 24,
28, 32, 36, 40, 44, 52, 60; lines roll at the item's tier or the tier below), computed live on the Companion sheet at b0 + X (b0 = Inputs minus the boots
lines listed on PotentialCubes), and `potential_cubes_ev.py` prices rolls of this stat by RE-RUNNING the Python port at b0 + roll (per-row baseline = the
summoning time on every other row's current lines, like Skill Cooldown Decrease).  Needs a chosen, unlocked companion (otherwise worth 0).
Calibration: the user's Chapter Boss with a Lv5 Wind Archer showed ~65% of the damage without the companion; the model (artifacts equipped) gives ~68%.

Confirmed by the user 2026-11-12: Bow Master Phoenix 20 s / cooldown 30 s; Corsair battleship sustained hits 5 targets; Night Lord boss defense -15% lasts 10 s;
Bow Master's attack stacks cap at 100; FP-Mage's companion wall of fire shows no duration, so it is modelled like the regular FP-Mage: 3 walls (100% every 1 s on 3 targets
each) up for the whole summon - the wall-by-wall ramp is ignored.
Shadower's Lv2 buff-removal proc (1000% x3, x4 on a boss) is not modelled at all (user, 2026-11-14: no target buffs exist in this project, so it never
triggers, in any content).
Assumptions / transcriptions to confirm (see KITS_ENCODED.md): Bishop's +8% Final Damage applies to the player AND the companion (user, 2026-11-12), its +15% & +20% Attack are the player's; Dark Knight's Evil Eye (+15% damage taken) is
applied to all hits (the 6-target limit is ignored); event passives (Dawn Warrior, Blaze Wizard) always on; stacking buffs use the boss-unit attack rate; "player" effects are not part of the companion's own snapshot.
Dawn Warrior's "target HP below 50%" assumes damage is uniform until the boss dies on the buzzer, so the boss is under 50% in the second half of the boss phase
(normal monsters: half the time); the companion's extra damage shifting that point is ignored.
Boss/normal weighting of the companion window (2026-11-14): in Chapter Breakthrough / Hero Dungeon the normal-monster phase comes first (boss at 20 s / 30 s). The companion's
damage is split BY PHASE (cooldown casts and DoT ticks by the phase of the cast, everything else by time share; basic attacks = each phase's seconds x actions/s minus the casts made
in it), the boss-only DPS = boss-phase damage / boss-phase length and the normal-only DPS = normal-phase damage / normal-phase length, and the content's emphasis w weights them
(user's rule: a weight is a weight on RELATIVE gains, so +18% boss time is worth (1-w) x 18%).  The fight extension is valued at the player's boss DPS with the Hexagon stacks of
that moment.  Candidate summon times: the end-aligned one (T+E-D), the next Hexagon stack time, and the earliest summon (7 s).  Known approximation: averaged effects of fixed
length (e.g. a 30 s damage-taken debuff) are averaged over the whole window, so between the jumps (a new stun fits) the companion's gain from MORE duration drifts about
-0.5% .. +0.5% instead of rising smoothly; the proper fix is to run the companion on the timeline engine.  Excel returns #NUM! for 0^0, so the companion's "max enemies in range"
is floored at 1 (the input is blank in boss / PvP content).
Hero Dungeon is timed: a stun does NOT lengthen it (only Chapter Breakthrough has the stun extension; user, 2026-11-14), but both contents get the phase split below.
Breakthrough / Hero Dungeon boss phase (2026-11-14, simplified at the user's request): (1) every damage row's boss and normal columns carry a PHASE factor - Hexagon Necklace stacks and
Charm of the Undead's duty cycle averaged over the boss phase [boss appears, T] / the normal phase [0, boss appears] relative to the fight average the rest of the model uses; (2) the
stun extension is valued as the player's basic-attack-type rows only (Basic Attack, Meteor Proc, Ignite, Elemental Drain: no extra skill casts are assumed to fit) at the Hexagon stacks of
that moment relative to the boss-phase average, and the companion is NOT assumed present in it; (3) the potential-line table on CompanionsInput shows the breakdown: average boss DPS change
over the longer boss phase x boss-time factor = total boss damage change, which the emphasis w then weights.  Example: average DPS -5.5% x time 1.1837 = +11.8% boss damage, +5.3% weighted.  Other time-dependent artifacts (Candle,
Rainbow Snail Shell, Chalice, Ring of Cycles) and Infinity stay at fight averages in this split.
Companion gain displays (2026-11-14): the per-companion table (CompanionsInput D/E, Sensitivity Companion Comparison), the summoning-time potential table and the cube-EV curve now report the WEIGHTED RELATIVE gain - boss-only and normal-only DPS (player + companion) each grow by their own ratio and the content's emphasis w blends the ratios - instead of the dollar-blended totals, which let the normal-monster branch (several times bigger in dollars) swamp a boss-side gain.
Chapter Breakthrough fight extension (modelled 2026-11-11): the boss stands still while stunned/frozen, so every companion stun/freeze that
lands on the boss once it is there (t >= 20 s) pushes the fight end back by that stun's length (Blaze Wizard 4.5 s in Breakthrough (1.5 s x3), 1.5 s elsewhere where it does
not matter). The summon time is then s = T + E - D, which can allow one more stunning cast, so E is solved by three unrolled iterations
(`E_a`, `E_b`, `E_0` on the Companion sheet); `best_E` / `best_Tend` hold the chosen values, the companion window covers the extended fight, and the player's own
boss damage during the E extra seconds (`E x player boss DPS`) is added to the companion's boss DPS (`best_ext / (1 - w) / period`). Example (Blaze Wizard Lv10, T=40,
boss at 20 s, cast every 16 s, 4.5 s stun): D=30 -> E=4.5, s=14.5; D=32.4 (+8%) -> E=9 (a second stun fits), s=16.6, boss time 29 s. Stun chance (`stun_p`, e.g. Shadower's 30%) is multiplied in as an
expected value; `stun_skip` skips the first casts (Night Walker's marker). Normal monsters never lengthen anything. The PLAYER's own stunning skills ARE modelled (2026-11-15/17, see each class's "Companions + Status Effect Damage" section); Shadower's Lv3 5000% hit counts only the companion's own stuns/freezes.
Not modelled yet: buff-alignment cost (recasting the player's buffs so they are
up at the summon), Rainbow Snail Shell / Ring of Cycles / Candle snapshot terms (kept at fight averages), Nimble Feet in the snapshot Attack Speed, the other 11 classes.

Cast timing (2026-11-18).  User's in-game measurement (Blaze Wizard, 55.5% attack speed): the companion's first action starts ~0.3 s after the summon click, its 2nd action skill
(phoenix, 16 s cooldown, stun) lands ~1.1 s after the click and the casts repeat every ~16.5 s = cooldown + 0.5 s (the cooldown only starts counting when
the cast is finished); with +12% summoning time (33.6 s) the 3rd stun did NOT happen (1.1 + 2 x 16.5 = 34.1 s).  Model (user decision: no attack-speed scaling,
no per-skill cast-time table): constants in `src/companion_kits.py` START_DELAY = 0.3 s, CAST_TIME = 0.5 s, FIRST_SLOT = 0.8 s (`schedule(rows)` is the single rule).  A cooldown ACTION skill
(action = 1, finite cd) is cast at t0 + n x (cd + CAST_TIME) after the summon, t0 = START_DELAY + k x FIRST_SLOT, k = 0-based rank of the skill among the companion's action skills in kit order
(a1_bt / a2_bt style content variants share their canonical id: `cast_of`); rows of the same cast (second hit part, debuff stat row, end-of-window explosion, echo arrows) carry
`cast_of` = the action row and share its period / first cast; passives with their own timer keep period = cd, t0 = 0; summoning effects (cd = NEVER) happen at the summon.
Casts in a window W = INT((W - 1e-9 - t0) / per) + 1 (0 when W <= t0); uptimes of timed stat rows, DoT windows (cut by the window end), the phase split of Breakthrough / Hero Dungeon,
stun windows and Breakthrough's boss-phase extension all use these times (CompanionKits sheet columns `cast_of`, `per`, `t0`, `skey`).  Blaze's 3rd stun now needs a window >= 34.1 s (+13.67% summoning time).
Caveats: the cast order is the kit order (Dark Knight's kit has no a1, so its a2 is the first action: t0 = 0.3 s); the cast time does not depend on the skill (real casts differ), and attack-speed scaling is ignored;
the player's own stun skills keep their old timing (cooldown from the startup time).  Effect on the companion DPS (+12% summon time, level 10, synthetic host): Hero / Dark Knight / Shadower /
Wind Archer unchanged (same cast counts), -0.5..-7% elsewhere (IL Mage -6% to -7%, Buccaneer -5%, Blaze Breakthrough -12.8% = one stun cast fewer).
FP-Mage workbook rebuilt with it (2026-11-18; same Inputs, level 200, status 30): Total DPS vs before, Blaze Wizard Lv10 / Wind Archer Lv7 (+20% summoning time): World Boss -0.92% / -0.23%,
Breakthrough -4.98% / 0, Chapter Hunt -0.39% / 0, PvP 0 / -1.66% (one pinpoint cast fewer in the 36 s window).  Blaze Breakthrough at +13.6% -> +13.7% summoning time: 1.3958e12 -> 1.4500e12 (the 3rd stun cast
appears at 13.667%).

Workbook numerics of the companion chain (documented 2026-11-19, shared model NOT changed): the chain's elementwise MIN is written `(a+b-|a-b|)/2` and a permanent kit
effect carries the 1e9 NEVER sentinel as one operand, which in double precision loses ~5e-8 absolute of the other operand.  For a window of WHOLE seconds (D = 30, 45 ...) that is
exact; at a FRACTIONAL window (summoning time not a whole number of seconds, e.g. +1% -> 30.3 s, or Arwen's Glass Shoes' +24%) such an effect's uptime reads `1 - 1.5737e-9` instead
of 1 (relative 1e-9, far below any practical significance; the plain-Python port `companion_python_model.py` and `engine/common/companion.py` are exact).  Consequence for tests:
`tests/golden/test_fp_mage_sensitivity.py` compares companion-dependent quantities at a fractional window with `FRAC_RTOL = 5e-9` (and gains with an absolute slack of
`FRAC_ATOL = 2e-9` x Total DPS) instead of its default 1e-9; whole-second windows are bit-exact.

## Status Effect Damage, KO phases and the timeline engine (2026-11-14, FP-Mage first)

New Inputs row **STATUS_EFFECT_DAMAGE %** (after Normal Monster Damage %, per content type): extra damage while the enemy is frozen/stunned; 0 = no bonus.
KO (World Boss: 24-34 s and 59-69 s; Enhancement Dungeon: the last 4.5 s; boss only) doubles damage and ALSO uses the input (user, 2026-11-14), so a KO second
is worth `2 x (1 + S/100)` and a stunned second `1 + S/100`.  Source of the stuns: the companion's stunning/freezing casts (kits `stun`, `stun_p`, `stun_skip`);
FP-Mage has no stunning skill of its own (other classes will add theirs when ported).

**Why a new engine**: the rest of the model is time-averaged, but these effects only pay when damage lands inside the window.  `src/status_timeline.py` (plain-Python
`solve`, Excel generator `cells`, tested equal on three scenarios) works in 1-second bins on the `Timeline` sheet and lets the PLAYER play optimally (user: "assume the
player maximises DPS while the enemy is stunned/frozen"): buffs and cooldown skills are cast at the times that maximise the weighted damage subject to their cooldown
(a dynamic programme, so it decides for itself whether holding a skill for a window is worth skipping a cooldown cast), Hexagon Necklace stacks (20/40/60 s) and Charm
of the Undead's 5 s-on/5 s-off window are counted second by second.  Examples with the default FP numbers: World Boss - Meteor Shower is cast at 0, 33 and 68 s (two casts
inside KO), Poison Breath 10/32/50/68; Enhancement Dungeon - Poison Mist and Flame Haze go early so the eruption lands in the KO, Meteor Shower waits for it, buffs line up
with the last 4.5 s.  The `Timeline` sheet shows every group's cast times.

**How it feeds the model**: engine ON when the fight has a fixed length, the branch is single-target (normal weight 0) and there is a KO or a stunning companion.  Then
(1) `Calc!R` of every cast row = the engine's cast count, (2) DoT / eruption rows' hits = hits per window x the engine's effective casts / T, (3) `Summary!R_AVGBUFF` = the
engine's mean buff bucket and the buff-casting start-up delay is 0 (buffs are cast when they pay), (4) every damage row's boss DPS (Calc `S`) is multiplied by its timing
factor (Calc `W`: phi of the row; uniformly spread rows - Basic Attack, Meteor Proc, Ignite, Elemental Drain - use phi_unif).  Calc `Y` = a row's boss damage PER CAST before
timing (the engine's weights; free of cast counts so there is no circular reference).  With the engine OFF (Chapter Hunt, blended content) the factor is the uniform
`1 + S/100 x (companion's stunned share)` (columns W/X), which is also the normal-monster factor.  The companion's own damage is multiplied by the mean status multiplier
over its window (engine ON) or the same uniform factor.  Engine ON with S = 0 and a stunning companion still re-times buffs/skills (the optimiser has nothing to gain from
mult = 1 but still aligns with Hexagon/Charm) - deliberate, so toggling S never switches the model.

**Sensitivity**: new row STATUS_EFFECT_DAMAGE %.  Blocks that move cast times / buff windows / Hexagon stacks / S (Skill Cooldown Decrease and its 10 milestone blocks, Buff
Duration, Shamaness Marble, Status Effect Damage, Companion Summoning Time, Hexagon Necklace equip) re-run their own strip (placed below the last block); every other block
reuses the main strip's cast counts and timing factors.  (The "second-order approximation, e.g. Meditation's level" that used to stand here was a real error in KO contents:
fixed 2026-11-19, see "FP-Mage Sensitivity: strip rebuild set ..." below.)

**Limitations**: no potential line carries Status Effect Damage in the cube data (nothing to price); the Summoning-Time cube pricing re-runs the companion mirror from the exported host values (incl. Status Effect Damage and the Timeline strip's per-second multiplier) and prices each roll by the weighted relative gain (checked equal to the Companion tables for Breakthrough and World Boss); cooldown spacing uses whole bins (ROUNDUP of the cooldown, so a
cooldown of 24.5 s counts as 25); a stun on the NORMAL branch gets no alignment; companion stun windows use the full-coverage summon (candidate 0); Candle / Rainbow
Snail Shell / Chalice / Ring of Cycles stay at their fight averages in the engine (only Hexagon and Charm are time-resolved); the cast window of a burst is its whole
second (meteor travel time ignored); other classes still run without it.

**Back-port of the Buccaneer-port recipe (2026-11-17)**: (1) the re-running Sensitivity blocks (strip rebuilt) now read the MAIN sheet's `s_0` / `W_0` for the strip's stun vector
(`companion_main_ref`), only the Summoning-Time block keeps its own; (2) `COMPANION_FULL_SEARCH_KEYS` = Summoning Time, Hexagon Necklace equip, Horn Flute equip and Skill Cooldown Decrease
(+ its 10 milestone blocks, same stat key) run the full 3-candidate companion search instead of pinning the main sheet's choice; every other block still reuses it (a flip of the chosen
candidate between base and swept value stays the remaining second-order approximation).  Main sheet / engine unchanged (Summary Total DPS identical before and after; no helper cells, BLOCK_HEIGHT unchanged).
On FP-Mage the gap was NOT visible in the scenarios tried (sens-vs-main ratios were already 1.00000000 before the fix: World Boss and Breakthrough with Blaze Wizard Lv10 and with Wind Archer Lv7 + Summoning Time +20%, S=30) - FP-Mage has no player stun and
its blocks' own chain tracked the full search in those cases - so this is a consistency port.  Not a divergence but worth knowing: in blended content (Breakthrough) the Hexagon / Horn Flute artifact-table DPS gain is time-weighted per branch
(bug #9), so it differs from the toggled copy's dollar delta by design; the block totals equal the toggled copy exactly.  Longest formulas now: Sensitivity 7468, Timeline 7369, Companion 6376 (cap 8192).

## FP-Mage Sensitivity: strip rebuild set and baked-in Final Damage what-ifs (2026-11-19, FP-Mage reference; the other 11 builders still have the old behaviour)

Two inaccuracies found while building `engine/sensitivity.py` (Phase 3), both Sensitivity-sheet only (main sheets formula-for-formula identical before / after; Total DPS unchanged):
1. **Strip reuse in KO / stun contents.**  Every block outside `STATUS_REBUILD_KEYS` reused the MAIN timeline strip.  That is exact only for stats that scale every damage row alike.
   A buff's level bonus changes the strip's buff values (Magic Guard / Meditation / Infinity), so the five Skill Level stats barely registered: World Boss `skill_lvl_1st`
   read 0.44M instead of 3.11M DPS (plain re-run), Enhancement Dungeon 3.75M instead of 15.9M.  `STATUS_REBUILD_KEYS` now also holds `skill_lvl_1st/2nd/3rd/4th/all`,
   `skill_damage`, `basic_attack_damage`, `boss_damage` (the Basic Attack has its own Boss Mastery), `crit_rate` (Ring of Cycles' Basic Attack Damage bonus) and the artifacts that
   feed those buckets (`ring_of_cycles`, `book_of_ancient`, `rainbow_snail_shell`, `candle`, `sayrams_necklace`, `star_rock`); every other stat was checked exact under reuse
   (reuse vs re-solve < 1e-11 of Total in World Boss and Enhancement Dungeon).  Breakthrough / Hero Dungeon / Chapter Hunt have the engine OFF (normal weight > 0) so nothing changes there.
   Remaining documented block-only terms (by design): the main-stat flat-Attack channel (Flat INT / INT %, bug 7) and the passive deltas Spell Mastery / Magic Critical of
   `skill_lvl_2nd/3rd/all`.  Cost: 11 more strips (the workbook grows ~1.2 MB); longest formula still 7468 (cap 8192); BLOCK_HEIGHT unchanged.
2. **Baked-in Final Damage artifacts** (Cursed Doll, Lit Lamp, Clear Spring Water, Soul Pouch, Bottle of Emotion's Attack-Speed-dependent value).  Their value is typed into
   `Inputs!final_damage`, but the what-if was added / subtracted inside the ADDITIVE artifact bucket: removal gain = (1 + x/100) x adding gain (Cursed Doll star 5: 1.14x), so the same
   real pair of states reported two different gains / % Gains (CLAUDE.md item 15), and with a live Final Damage artifact equipped (a = 1 + bucket/100 > 1: Candle, Flaming
   Lava, Horn Flute) even the adding direction read (a + x/100)/a instead of 1 + x/100.  Now the what-if is a FACTOR on the whole product: multiply by (1 + x/100) when adding, by 1/(1 + x/100)
   when removing; the Bottle's Attack Speed sweep uses (1 + new)/(1 + old) (was additive: ~5% off the Attack Speed row with the Bottle equipped).  Block-local helper cells
   (column Z of the 3rd / 4th skill row) hold the live bucket and the factored bucket.  Verified by toggled-copy pairs in both directions (Cursed Doll, Lit Lamp, Bottle of
   Emotion in World Boss; Clear Spring Water in Enhancement Dungeon; Soul Pouch in PvP): identical gain and % Gain from either side to 1e-16, gain == Total(equipped) - Total(unequipped).
   Other baked-in artifacts re-checked: Book of Ancient, Athena's Gloves, Reindeer's Spear, Star Rock, Shamaness Marble were already exact inverses (additive stat in one shared
   additive bucket / diminishing-returns dose).  Blended contents (Breakthrough / Hero Dungeon) still differ between directions by design (bug 9: relative branch gains are blended).

## Ice-Lightning-Mage: Companions + Status Effect Damage / KO timeline port (2026-11-14)

Ported from FP-Mage (`data/porting/COMPANION_STATUS_PORT_GUIDE.md`): Inputs row 22 Status Effect Damage % (self-detecting row-shift migration), `companion_choice` (row 51),
live Companion Summoning Time Increase %, sheets `Timeline` / `CompanionKits` / `Companion` / `CompanionsInput`, Sensitivity Companion Comparison + summoning-time tables,
the two new STAT_SWEEP rows, Horn Flute rewired to `Companion!horn_uptime`, cube-script host export.  Class-specific decisions:
- **Engine spec**: buffs Meditation / Magic Guard ('atk') and Infinity ('ramp', shape 15 -> 25 = base -> base x 5/3 over 10 s; `Calc!F` is the time-average base x 64/45, the
  engine normalises the ramp to that average); cooldown groups Thunder Bolt / Glacier Wall / Blizzard (bursts), Thunder Sphere / Freezing Breath / Frozen Orb / Elquines (DoT or summon
  windows, hits from the engine's effective cast count); uniform rows Chain Lightning and Blizzard Final Attack (the any-attack proc keeps its own trigger-rate formula).  Frozen Orb's
  single-target halving is part of its per-cast weight (`Calc!Y`).  Nimble Feet keeps its exact-cast formula (an Attack Speed buff, not in the engine).
  Freezing Breath's Weaken and Elemental Reset (monster damage taken) stay steady-state averages (not re-timed by the engine).
- **Player stun**: Glacier Wall freezes for 2 s on its 22 s cooldown (Reuse Lv90 already in Calc!Q): a fixed on-cooldown stun group (`STATUS_PLAYER_STUN`), so the engine is ON in every
  fixed-length single-target content and Breakthrough's boss phase is lengthened by the freezes; Frost (slow) is not a stun.
- **Host**: this class has no separate damage-taken multiplier - the monster damage-taken bonus (Weaken + Elemental Reset + artifacts) is part of the additive Boss/Normal Monster
  Damage bucket, so `boss_pct` / `norm_pct` include it and `taken_bucket` = that bucket (boss/normal blended by w; 0 in PvP, where no bucket applies and the player's own bonus is not applied
  either) so a companion's damage-taken debuff adds into the same sum.  The player's uplift ratio uses the host bucket without the skill's own mastery boss/normal bonus (small overstatement).
  Buffs are gated on the unlock level in `avgbuff_snap` / `attack_bucket_avg` / `k1`; Infinity's `Calc!F` (time-average) is the snapshot value.
- Re-run-own-strip Sensitivity blocks also cover the Attack% artifact toggles and the 1st/2nd/4th-job / all-skill level sweeps (the cast buffs' F feeds the strip's buff bucket).
- Verified 2026-11-14: verify script == workbook for Chapter Boss / World Boss / Enhancement Dungeon / Breakthrough / Hero Dungeon / Chapter Hunt / EXP / Equipment / PvP with Blaze Wizard,
  Wind Archer, Bow Master and no companion; Chapter Hunt (companion None, status 0) total 22,207,284.92 identical to pre-port; no error cells (4 contents, artifacts equipped in one);
  `cyc.py` 0 cyclic components; longest formula 7606 characters (Timeline); Sensitivity vs full model (World Boss, Blaze Wizard Lv10, artifacts Hexagon/Charm/Horn Flute/Reindeer's Spear):
  `damage`, `status_effect_damage` ratio 1.00000000, Hexagon / Charm / Horn Flute toggle rows == total delta of the toggled copy (Horn Flute +12.5%).
- Known limits: `status_timeline.solve` (Python) stacks an Attack% buff recast while still active (duration > cooldown, e.g. Magic Guard with CDR 3 and +30% Buff Duration) while the Excel
  strip caps the overlap at one buff (the Excel behaviour is the correct one): the verify script then mismatches the workbook in exactly that corner (matches when the Python line is capped).
  The companion's `taken_bucket` blend and the Glacier Wall freeze being a fixed schedule (not optimised) are approximations.
- **Back-port of the Buccaneer-port recipe (2026-11-18)**: the re-running Sensitivity blocks now read the MAIN sheet's `s_0` / `W_0` for the strip's companion stun vector (`_stun_ref` -> `companion_main_ref`; the player's Glacier Wall entries were already block-local), only the Summoning-Time block keeps its own, and `COMPANION_FULL_SEARCH_KEYS` (Summoning Time, Hexagon Necklace equip, Horn Flute equip, Skill Cooldown Decrease + its 10 milestone blocks) run the full 3-candidate companion search instead of pinning the main sheet's choice.  Main sheet / engine unchanged (0 Input diffs, only Sensitivity formulas differ, baseline Total DPS identical; no helper cells, BLOCK_HEIGHT unchanged, longest formula 7606).  Sens-vs-main (Blaze Wizard Lv10, status 30, Lv200, Bottle of Emotion + Reindeer's Spear): this class was NOT off before the fix in any case tested (World Boss, Breakthrough, Enhancement Dungeon, Bow Master, Wind Archer Lv7 + Summoning Time +20% at World Boss and at Breakthrough - the latter two pick a non-zero candidate, best_s 7 vs s_0 16.5 / 7.2); all 1.00000000 after as well.  At World Boss this class always chooses candidate 0 (summon 45 s / 39 s), unlike Hero.  Hexagon / Charm / Horn Flute equip rows (gain and % gain) equal the toggled-copy delta at World Boss (ratio 1.00000000).  A flip of the chosen candidate between base and swept value stays a second-order approximation for the other blocks.
- **Rebuilt for the companion cast timing rule (2026-11-18)** (see "Companions" -> Cast timing): Glacier Wall keeps its old timing (player stun, cooldown from the startup time); total shifts vs the previous workbook at the same Inputs (Lv200, status 30, Blaze Wizard Lv10 / Wind Archer Lv7 +20): World Boss -0.43% / -0.31%, Breakthrough -5.87% / 0.00%, Chapter Hunt -0.51% / 0.00%, PvP 0.00% / -1.90%; verify script == workbook (all contents, Blaze at +0/12/14%), Sensitivity vs full model ratio 1.00000000 (incl. +12.9% base), 0 error cells, cube mirror ~1e-16, longest formula 6903 (Sensitivity).
- **Arwen's Glass Shoes + "no DPS effect" relabelling (2026-11-20, replayed from FP-Mage / Hero)**: the shoes are a REAL, live Companion Summoning Time Increase (+20% star 0 .. +40% star 5, linear 20/24/28/32/36/40, all user-confirmed 2026-11-19); effective increase = Inputs value + artifact (`companion_summon_time_inc_expr`) in the Companion host, every Sensitivity block, `b0` (artifact added outside the `MAX(0, ...)`) and so the CompanionsInput table / cube script; the equip row is in `STATUS_REBUILD_KEYS`, `COMPANION_FULL_SEARCH_KEYS` and `SUMMON_TIME_KEYS`.  The seven artifacts without a DPS effect are labelled "no DPS effect (reason)" (`ARTIFACT_NO_DPS_EFFECT`; ArtifactsInput has a 15th column "Equip effect in the DPS model").  Inputs / ArtifactsInput / PotentialCubes carried over with 0 diffs (only the Companion Summoning Time Increase label changed); Sensitivity grew by one strip (+200 rows); `cyc.py` 0 cyclic components; longest formula 6903 (Sensitivity AG1026, unchanged), Companion 6054 (cap 8192).  Verified on the ILM workbook: equivalence (Total DPS with shoes star s at Inputs x == without shoes at x + 20..40) bit-for-bit on 10/10 pairs (World Boss Blaze Lv10 star 0 = in20, star 5 = in40, star 5 + in5 = in45 across the 3rd-stun flip, + Bottle / Hexagon / Horn Flute; Breakthrough Wind Archer Lv7 x4; Chapter Hunt x2); Sensitivity equip row == toggled-copy delta 1.00000000 (World Boss, from BOTH directions: % Gain 107.50044120974084 each; Hexagon + Horn Flute + Bottle base 105.00726538298781; Chapter Hunt 107.6509416883892), Summoning-Time stat and damage blocks with the shoes equipped 1.00000000, Breakthrough equip row == time-weighted expected 1.00000000 (its dollar delta differs by design, CLAUDE.md item 9); 0 error cells and cube mirror <= 2e-16 (World Boss, Breakthrough Blaze Lv10; Wind Archer Lv7 6e-10, fractional-window artifact) with shoes + Hexagon + Horn Flute + Bottle equipped.  The engine side (`engine/classes/ice_lightning_mage.py`) models the artifacts since the same day: `tests/golden/ice_lightning_mage_artifacts_golden.json` / `test_ice_lightning_mage_artifacts.py`.
- **Ice/Lightning Mage Sensitivity fixes (2026-11-22; FP-Mage's two fixes replayed per stat)**: (1) strip rebuild set.  ILM already re-ran its strip for the Magic Guard / Meditation / Infinity skill levels (1st / 2nd / 4th / all), CDR, Buff Duration, Status Effect Damage, Summoning Time, Glass Shoes, Shamaness Marble, Hexagon and the Attack%-artifact toggles; added now: `skill_lvl_3rd` (Glacier Wall / Thunder Sphere / Element Amplification F vs the other steps' rows), `skill_damage`, `basic_attack_damage`, `boss_damage`, `crit_rate` and the toggles `ring_of_cycles`, `book_of_ancient`, `rainbow_snail_shell`, `candle`, `sayrams_necklace`, `star_rock` (+11 strips).  Per-stat decision by an engine experiment (`stl.solve` captured for the base inputs and replayed for the swept inputs, 10 World Boss / Enhancement Dungeon configurations x stat sets A/B, Chapter Hunt / Breakthrough have the strip off): reuse == re-solve (< 1e-11 of Total) at +1 AND at huge deltas for Flat INT, INT %, LUK, Damage %, Damage Amp, Normal Damage, Final Damage, Min / Max Damage, Crit Damage, Def Pen, Attack Speed, Flat ATTACK, ATTACK %, Target Increase (stay reused); Skill Damage already flips the schedule at +1 (4 of 120 random configurations), Basic Attack Damage / Boss Damage / Skill Level 3rd and the Ring-of-Cycles-dependent Crit Rate flip at larger deltas.  Sens-vs-main (swept Input set to the block's New Value in a Sensitivity-emptied copy, Ring of Cycles + Bottle of Emotion + Reindeer's Spear equipped, Lv200, Blaze Wizard Lv10, S = 30): `skill_damage`, `basic_attack_damage`, `boss_damage`, `crit_rate`, `final_damage`, `damage`, `def_pen`, `attack_speed` ratio 1.0000000000 in World Boss AND Enhancement Dungeon (`flat_int` 1.0000056 = the mainstat flat-Attack channel, bug 7, by design); `skill_lvl_1st` / `_2nd` / `_3rd` / `_4th` / `_all` ratio 1.0000000000 against a main re-run that also receives the documented passive deltas of the Magic Critical / High Wisdom / Spell Mastery / Magic Acceleration rows (per level: Crit Rate +0.024, Crit Damage +0.036, Min Damage +0.045, Attack Speed +0.015 points; 2nd +CR/+Min/+AS, 3rd +CR/+CD, all both).  Found by this test: Ring of Cycles' threshold in a block read the unchanged crit rate, so with the ring above 100% crit the skill-level blocks missed the passive crit delta (ratio 0.99993 for 3rd, 0.99987 for all at Crit 120); `roc_threshold_cr_block` (and Book of Ancient's add case) now include `crit_rate_delta` (0 in every other block; main sheets untouched; longest formula 6903 -> 6919, Sensitivity S1395).  Book of Ancient's crit-damage conversion in a skill-level block still ignores the passive crit delta (same as every sibling class, ~1e-6).  Soul Contract's Chapter-Hunt cut is applied at BOTH real-cooldown call sites (main Calc and the block, plus Triumph Feather's 18 s) - nothing missing; Skills-sheet formulas read only Inputs level (never swept) and `basic_attack_target_increase` (re-derived per block as `chain_targets_expr`) - no bug-19 cell found; PvP opponent defense is the plain Defense input (ILM has no Defense %).  (2) baked-in Final Damage what-ifs (Cursed Doll, Lit Lamp, Clear Spring Water, Soul Pouch, Bottle of Emotion's Attack-Speed-dependent value) are a FACTOR on the whole `(1 + final_damage/100) x (1 + bucket/100)` product, `1 + x/100` when adding, `1/(1 + x/100)` when removing (block-local helper cells Z+3 / Z+4 of the 3rd / 4th skill row); matched pairs (state 1 = artifact equipped with its Final Damage typed multiplicatively into `Inputs!final_damage`): block read in state 0 == Total of state 1 and read in state 1 == Total of state 0 to 1e-16, gain and % Gain identical from both directions: Cursed Doll 114.0% (Candle live), Lit Lamp 140.0%, Bottle of Emotion 130.96531019639022% (Attack Speed 84), Clear Spring Water 120.0% (Enhancement Dungeon), Soul Pouch 140.0% (PvP).  Glass Shoes equip row vs toggled copy 1.0000000000 in both directions (World Boss, % Gain 107.50044120974084).  Rebuild: Inputs / ArtifactsInput / PotentialCubes 0 diffs, every sheet except Sensitivity formula-identical, `cyc.py` 0 cyclic components, 0 error cells and cube mirror <= 1.4e-16 in World Boss and Breakthrough (full workbook, Sensitivity stripped); the ILM engine goldens (265 + 58 cases) pass unchanged.

## Bowmaster: Companions + Status Effect Damage / KO timeline port (2026-11-14)

Ported from FP-Mage (`COMPANION_STATUS_PORT_GUIDE.md`): Inputs row `STATUS_EFFECT_DAMAGE %` (row 22, self-detecting carry-over migration of the shifted rows), `Companion` choice per content
type (row 51) + the live `Companion Summoning Time Increase %`, sheets `Timeline` / `CompanionKits` / `Companion` / `CompanionsInput`, Sensitivity rows for both new stats, the Companion
Comparison + Summoning-Time breakdown tables (weighted-ratio form), the Horn Flute rewire (`Companion!horn_uptime`) and the exported host values for `potential_cubes_ev.py`.  With the companion on
"None" and Status Effect Damage 0 the steady-state total is unchanged (Chapter Hunt 13439558.2696 before and after).  Fixed-length contents changed on purpose: Covering Fire is a stunning skill (see below),
so the engine is on whenever it is unlocked (Breakthrough, companion None, S 0: 8325857.08 -> 8360799.54 from the boss-phase extension).

Engine spec (derived from Bowmaster's own rows; `STATUS_*` in `build_bowmaster_workbook.py`):
- Buff list: only **Illusion Step** ('atk', Attack% - cast when it pays; at Lv118+ it is always on so nothing moves).  Sharp Eyes (Crit Damage), Nimble Feet (Attack Speed), Concentration and Mortal Blow
  (steady-state stacks) are not Attack%/Final-Damage ramps the engine knows, so they keep their averaged formulas (their action-slot cost stays in `Summary!Skill + Buff Cast Rate`).  Marksmanship (both halves)
  and the artifact Attack% sit in the engine's `A0`.  Bowmaster has no multiplicative class buff (no Infinity-like row), so the snapshot's `fdpart` is 1.
- Cast groups: Covering Fire (burst), Hurricane (burst), Phoenix and Arrow Platter (summon DoTs, window = ActiveWindow; Arrow Platter's 60 s window overlaps its 40 s cooldown - overlapping casts add, as in the averaged model).
  `STATUS_FS_KEYS` = Phoenix, Arrow Platter (hits/s = per-cast hits x the engine's effective casts / T).
- Uniform rows (phi_unif): Arrow Stream, Final Attack: Bow, Flash Mirage (chance procs triggered by every attack, timed or not), Quiver Cartridge and Enchanted Quiver - Drain (background ticks).
- Calc layout: boss / normal DPS are columns **T / V** here (not S / U), X / Y are the proc-trigger columns, so the timing factors live in **Z** (boss), **AA** (normal) and **AB** (per-cast boss damage); the Sensitivity blocks use the same letters.
- Companion host: `unit` = Calc!N/F of Arrow Stream; `avgbuff` = Summary R_AVGBUFF (engine-aware); `attack_bucket_avg` = Marksmanship base + conditional half + Illusion Step average + artifacts; the snapshot bucket has
  Illusion Step fully up; `cr_total` / `cd_total` are the fight-average totals incl. Sharp Eyes / Concentration (Sharp Eyes is NOT treated as "up" in the snapshot - small approximation).
- Damage-taken debuffs: this class keeps the artifact "enemy damage taken" bonus INSIDE the boss / normal monster damage % buckets (Summary R_MONSTER_DMG_BONUS), so the host's `taken_bucket` is the boss / normal
  blend of those buckets (0 in PvP): a debuff of d% adds d / (100 + bucket) instead of a separate x(1+d/100) (FP-Mage's separate Elemental Decrease bucket).  Assumption, same bucket logic as the Silver Pendant.
- Illusion Step is an auto-cycling passive in game; letting the engine place its Attack window is the one optimistic simplification (only matters below Lv118, where its uptime is 62.5%).
- **Player stun**: Covering Fire (19 s cooldown, 1 s stun, only from the Lv49 mastery: `STATUS_PLAYER_STUN`, `min_level=49`) is cast on cooldown from the start (`fixed=True` engine group, `pst` host entries in the
  main / block / exported hosts); it counts as a stun window for Status Effect Damage and extends Chapter Breakthrough's boss phase (not Hero Dungeon).  Because it is unlocked at Lv49 the engine is ON in every
  fixed-length single-target content for any character above that level.
- `STATUS_REBUILD_KEYS` also re-runs the strip for the Attack%-feeding toggles (Charm, Old Music Box, Secret Map, Reindeer's Spear, Alliance Badge, Bottle of Emotion) and for `skill_lvl_2nd/3rd/4th/all`
  (Soul Arrow, Marksmanship and Illusion Step F values).
- Verified: verify script == workbook (light build) for World Boss / Enhancement Dungeon / Chapter Boss / Breakthrough / Hero Dungeon / Chapter Hunt / EXP Dungeon / PvP with stunning (Blaze Wizard, Wind Archer) and
  non-stunning (Bow Master) companions and with None; Sensitivity-vs-main for World Boss (keys damage, status_effect_damage) ratio 1.0000; cycle detector 0; longest formula 7606.
- Also fixed: the Bowmaster Artifacts / ArtifactsInput sheet titles still read "Fire/Poison Arch Mage" (template leftover).
- **Back-port of the Buccaneer-port recipe (2026-11-18)**: the re-running Sensitivity blocks now read the MAIN sheet's `s_0` / `W_0` for the strip's companion stun vector (`_stun_ref` -> `companion_main_ref`; the player's Covering Fire entries were already block-local), only the Summoning-Time block keeps its own, and `COMPANION_FULL_SEARCH_KEYS` (Summoning Time, Hexagon Necklace equip, Horn Flute equip, Skill Cooldown Decrease + its 10 milestone blocks) run the full 3-candidate companion search instead of pinning the main sheet's choice.  Main sheet / engine unchanged (0 Input diffs, only Sensitivity formulas differ, baseline Total DPS identical; no helper cells, BLOCK_HEIGHT unchanged, longest formula 7606).  Sens-vs-main (Blaze Wizard Lv10, status 30, Lv200, Bottle of Emotion + Reindeer's Spear): before the fix only Skill Cooldown Decrease was off, and only where the chosen candidate is not candidate 0: Breakthrough Blaze Wizard 1.00107358 (best_s 7 vs s_0 16.5), Breakthrough Wind Archer Lv7 + Summoning Time +20% 1.00086713 (best_s 7 vs s_0 7.2); World Boss (best_s = s_0 = 45 / 39 s), the Bow Master case and every other key (damage, status_effect_damage, summon time, buff duration, attack_pct) were already 1.00000000.  After: 1.00000000 everywhere tested.  Hexagon / Charm / Horn Flute equip rows (gain and % gain) equal the toggled-copy delta at World Boss (ratio 1.00000000).  A flip of the chosen candidate between base and swept value stays a second-order approximation for the other blocks.
- **Rebuilt for the companion cast timing rule (2026-11-18)** (see "Companions" -> Cast timing): 0 Input / ArtifactsInput / PotentialCubes diffs, Calc / Summary / Artifacts differ only in Companion-sheet row references, the Companion / CompanionKits / Timeline-strip / Sensitivity companion cells are regenerated (no hand-typed cell lost), cycle detector 0, longest formula 7560 (Companion 6054).  The player's Covering Fire stun is unchanged.  Total shifts at the verify-script default Inputs (Lv200, status 30, Companion Lv10 / Wind Archer Lv7 + 20% summoning time): Blaze Wizard World Boss -0.24%, Breakthrough -3.98%, Chapter Hunt -0.32%, PvP 0; Wind Archer World Boss -0.16%, PvP -1.85%, Breakthrough / Chapter Hunt 0.  Blaze's 3rd stun now needs +13.667% summoning time (Breakthrough +3.8% between +12% and +14%).  Verified: verify script == workbook (light build) for World Boss / Breakthrough at +0 / +12 / +14, Wind Archer, companion None, Chapter Hunt, PvP, Hero Dungeon, Enhancement Dungeon; Sensitivity-vs-main ratio 1.00000000 (World Boss + Breakthrough, damage / status_effect_damage / skill_cooldown_decrease / companion_summon_time_increase_pct, also at +12.9% base), Hexagon / Charm / Horn Flute rows == toggled-copy delta; 0 error cells and cube-mirror agreement to ~4e-16.

- **Arwen's Glass Shoes + "no DPS effect" relabelling + Sensitivity fixes + engine artifacts (2026-11-20, replayed from FP-Mage / Hero / Paladin)**:
  - *Shoes*: a REAL, live Companion Summoning Time Increase (+20% star 0 .. +40% star 5, linear 20/24/28/32/36/40, all user-confirmed 2026-11-19); effective increase = Inputs value + artifact (`companion_summon_time_inc_expr`) in the Companion host, every Sensitivity block, `b0` (artifact added outside the `MAX(0, ...)`), so the CompanionsInput table / cube script too; equip row in `STATUS_REBUILD_KEYS`, `COMPANION_FULL_SEARCH_KEYS`, `SUMMON_TIME_KEYS`.  The seven no-effect artifacts are labelled "no DPS effect (reason)" (`ARTIFACT_NO_DPS_EFFECT`; ArtifactsInput 15th column).  Main sheets formula-identical before / after (Calc / Summary / Timeline 0 diffs; Companion only the shoes term in the 20 `inc` / `b0` cells; Inputs only the label; Artifacts only the 9 relabelled / shoes rows).
  - *Sensitivity: strip rebuild set* (`STATUS_REBUILD_KEYS`, decided per stat from what the strip consumes: Illusion Step F / duration / cooldown, Marksmanship `A0`, the per-cast weights `Calc!AB` and `c_slot`).  Added: `skill_damage`, `basic_attack_damage`, `boss_damage` (Arrow Stream carries its own +20% Boss Mastery), `crit_rate` and `ring_of_cycles` / `book_of_ancient` / `rainbow_snail_shell` (Ring of Cycles' Skill / Basic Attack Damage), `candle`, `sayrams_necklace`, `star_rock`, `peach_tree`, `silver_pendant` (all additive inside the boss bucket next to each row's own mastery; Peach / Silver follow Attack Speed, so `attack_speed` too), `arwens_glass_shoes`; `skill_lvl_2nd/3rd/4th/all` were already in.  NOT added (reused strip, exact): `skill_lvl_1st` (Covering Fire is a fixed on-cooldown group: its weight cancels), `normal_damage`, `basic_attack_target_increase`, `final_damage`, `flat_*`, `damage*`, `min/max_damage`, `crit_damage`, `def_pen`, the uniform Final Damage / crit / max-damage artifacts.  Exactness experiment (engine, reuse of the main strip's solve outputs vs a re-solve at the swept value, +1 steps, 148 engine-on cases of the golden matrix + 6 artifact setups): only `status_effect_damage`, `skill_lvl_3rd` / `all` / `4th`, `skill_cooldown_decrease`, `companion_summon_time_increase_pct`, `buff_duration_increase_pct` and the Attack%-artifact / Hexagon / Charm / Shoes toggles were ever non-exact (rel up to 0.25 for CDR); every other stat and artifact toggle was exact (< 1e-11), the additions above are therefore insurance: Phoenix / Arrow Platter are DoT casts worth `w x mean(Wt over the window) - c_slot x Wt`, so a relative weight change can in principle move a placement.  Cost: +14 strips (Sensitivity 8181 -> 10365 rows, workbook 6.3 -> 6.9 MB as written by the builder), longest formula 7543 (Sensitivity T1852; cap 8192), `cyc.py` 0 cyclic components.
  - *Baked-in Final Damage artifacts* (Cursed Doll, Lit Lamp, Clear Spring Water, Soul Pouch, Bottle of Emotion's Attack-Speed-dependent value) are now multiplicative factors on the whole Final Damage product (adding `1 + x/100`, removing its exact inverse; Bottle with Attack Speed swept: `(1+new)/(1+old)`), through block-local helper cells in column **U** (rows +4 / +5 below the basic-attack helpers; Bowmaster's Z / AA / AB are the timing-factor columns, unlike FP-Mage's Z).  The `Inputs!final_damage` bracket here is `1 + (Final Damage + Mortal Blow)/100` (like the `mult`-kind sweep, `MULT_KIND_EXTRA_REF`): the what-if bumps the whole bracket by exactly `1 + x/100`; a toggled copy that types the artifact into the Inputs must therefore be typed as `((1 + (fd + mortal)/100)(1 + x/100) - 1) x 100 - mortal` (typing `(1 + fd)(1 + x) - 1` into the Inputs bumps the bracket by 1.0983 instead of 1.14 at Mortal Blow 16: the inherent small inconsistency of the additive Mortal Blow term, as for Hero's Enrage / Combo Synergy).
  - *Illusion Step Lv118 bonus in blocks (found by the sens-vs-main check)*: `Skills!SkillMasteryBonus%` of Illusion Step is `5.25 x Calc!E / 1000` - it read the MAIN sheet's factor, so the 4th-job / all-skill level blocks left that part of F at the main level (F 6e-4 low, rows 0.99992 vs a main re-run).  Re-derived from the block's own `E` (`build_stat_block`, end); Sensitivity-only fix.
  - *Verification* (formulas package, one evaluation at a time): Glass Shoes equivalence (shoes star s at Inputs x == no shoes at x + 20..40) bit-for-bit on 10/10 workbook pairs (World Boss Blaze Lv10 star 0 = in20, star 5 = in40, star 5 + in5 = in45 across the 3rd-stun flip, + Bottle / Hexagon / Horn Flute; Breakthrough Wind Archer Lv7 x4; Chapter Hunt Wind Archer x2); equip row == toggled copy 1.00000000 in World Boss from both directions (% Gain 105.53876887730536 each) and with Hexagon / Horn Flute / Bottle (104.88365005468945), Chapter Hunt 106.27843035435069; in Breakthrough the block == toggled copy (1.00000000) and the table gain == the time-weighted expected gain (the dollar delta differs by design, bug #9).  Sens-vs-main (Summary Total of the main sheet with the swept Input set to the block's New Value, Bottle + Reindeer + Ring of Cycles + Peach / Silver equipped, World Boss and Enhancement Dungeon): ratio 1.00000000 for `skill_damage`, `basic_attack_damage`, `boss_damage`, `crit_rate`, `attack_speed`, `buff_duration_increase_pct`, `skill_cooldown_decrease`, `status_effect_damage`, `flat_attack`, `def_pen`, `normal_damage`, `companion_summon_time_increase_pct`, `damage`; `final_damage` block = baseline x 1.01 exactly (the check script has to subtract the Mortal Blow term from the New Value it re-types); `skill_lvl_1st/2nd/3rd/4th/all` differ from a plain main re-run by exactly the documented passive-delta terms (Critical Shot / Archer Mastery / Bow Acceleration / Physical Training / Bow Mastery / Extreme Archery / Armor Break / Bow Expert / Soul Arrow, 0.006% / 0.05% / 0.035% / 0.11% / 0.20% in World Boss; additive: 1st + 2nd + 3rd + 4th = all) and are exactly 1.00000000 once those passives' F are neutralised (4th / all only after the Illusion Step fix; before it 0.999922).  Two-direction check of the five baked-in Final Damage artifacts (World Boss Cursed Doll 114%, Lit Lamp 140%, Bottle of Emotion 125.43% at Attack Speed 80; Enhancement Dungeon Clear Spring Water 120%; PvP Soul Pouch 140%; Flaming Lava equipped as a live Final Damage artifact): gain and % Gain identical from either side to 1e-16 and == Total(equipped) - Total(unequipped).  0 error cells (World Boss, Breakthrough, Breakthrough + Wind Archer Lv7; Sensitivity stripped; Shoes + Hexagon + Horn Flute + Bottle equipped); cube mirror (`potential_cubes_ev.py`'s Python model rebuilt from the exported host values vs the Companion sheet) 3.8e-16 (World Boss), 2.3e-16 (Breakthrough), 5.9e-10 (Breakthrough + Wind Archer Lv7: the usual ~1e-9 `INT(x + 1e-9)` window effects).
  - *Engine* (`engine/classes/bowmaster.py`): artifact equip effects ported (`inputs["artifacts"]`, `schema()["artifacts"]`, `artifacts_modelled = True`), golden `tests/golden/bowmaster_artifact_cases.py` / `bowmaster_artifact_reference.py` / `bowmaster_artifacts_golden.json` / `test_bowmaster_artifacts.py`: 65 workbook evaluations (~25 s each), engine == workbook within rel 1e-9 (worst 1.2e-10, Breakthrough with Wind Archer), 6 equip-toggle deltas and the 10 equivalence pairs; `test_bowmaster.py` stays bit-exact (324).  Bowmaster-specific wiring: enemy damage taken (Peach / Silver) is `monster_dmg_bonus`, additive inside each row's Boss / Normal Monster Damage term; Hexagon Damage% multiplies the Attack% bucket; Sharp Eyes is a Crit Damage source only (no Crit Rate); Horn Flute's uptime uses the stub run WITH Covering Fire's entry; a local named `eq` in the engine is Enchanted Quiver (the artifact slots are `art_eq`).
  - The workbook may be open in Excel on the user's machine (`Bowmaster/~$Bowmaster-DPS-Calculator.xlsx` lock file present): close it before the next build.

## 2026-10-21 full data audit (all 12 classes) — what changed, and what is still an assumption

Source: `maplestoryidle.info`'s embedded game tables (+ its patched/base skill text), `idle.maplestorywiki.net`
(pre-Aug-13) and the Aug-13 patch notes. Raw snapshots, the per-class findings and the user's decisions are in
`data/ref_maplestoryidle_info/` (`VERIFICATION_FINDINGS_2026-10-20.md` is the entry point). Every class was
rebuilt and re-verified against its independent `verify_<class>_workbook.py` afterwards.

### Cross-class changes
- **Basic-attack mastery chains are RAW tiers** (+10/+11/+12/+13/+14/+15 = 75% at max) in all 12 classes — 11
  of them used `{10, 1, 1, 1, 1, 1}` (15%). CLAUDE.md structural-bug #2 was reversed accordingly.
- **Skill Cooldown Decrease now applies to EVERY real cooldown** — actively cast skills, buffs and passives
  (user request). It used to apply only to `CostsActionSlot` rows. Buff / debuff uptimes (main sheet AND every
  Sensitivity block) now use the row's *effective* cooldown (CDR + Soul Contract + any class-specific divisor)
  instead of the raw Skills-sheet cooldown, so CDR finally moves buff uptime. Rows whose `Cooldown(s)` is a
  trigger-rate / internal-interval SURROGATE (not a real cooldown) are exempt (`CDR_EXEMPT_ROW_KEYS` in each
  build script): Bowmaster Final Attack / Quiver Cartridge / Enchanted Quiver Drain / Flash Mirage, FP-Mage Ignite /
  Elemental Drain, Night Lord Venom / Mark of Assassin, Paladin Divine Judgment, Shadower Venom. Proc internal
  cooldowns that live in the `ICD(s)` column (Meteor / Blizzard / Nautilus Final Attack, Majestic Presence) are
  NOT reduced by CDR — assumption; tell me if the game does reduce them.
- **Buff-uptime caps**: uptime is now `MIN(1, duration/cooldown)` (steady state) and exact fixed-duration uptime
  counts `(casts-1)*MIN(duration, cooldown)`; a buff whose (Buff-Duration-boosted) duration exceeds its cooldown
  used to report >100% uptime (e.g. Paladin Combat Orders, 35s vs a 32.5s effective cooldown).
- **Soul Contract** (Chapter Hunt cooldown artifact) is now wired into Ice/Lightning's Sensitivity blocks (was
  main-sheet only).
- Potential Cubes: the DPS value of a "<Main stat> %" / "<Main stat>" / sub-stat line now maps to the class's real
  main/sub stat (Paladin showed DEX instead of STR).
- Multi-trigger "When attacking ... chance, 1s cooldown" Final Attack masteries (Ice/Lightning Blizzard FA,
  Buccaneer/Corsair Nautilus Strike FA, Corsair Majestic Presence) use the FP-Mage Meteor-Proc steady-state formula
  `(c*R)/(1+ICD*c*R)`. Trigger set = basic attack + the class's action-costing direct-attack skills; summons,
  turrets and DoT ticks are excluded (ASSUMPTION copied from the user's FP-Mage decision).

### Per-class highlights (full list: the findings file + `git log`)
- **Bowmaster / Marksman / Night Lord**: stale shifted mastery tables replaced by the current one (chain levels
  102/106/116/120/128/132, boss 111/124, Strike 136, many 2nd-4th job masteries), Quiver Cartridge 1 hit with an
  attack-speed-scaled interval, Hurricane / Flash Mirage targets, Phoenix window, Enchanted Quiver Drain (new
  row), Sharp Eyes = Crit Damage only, Concentration 7 stacks scaling with level, Snipe-Empowered / Spectral
  Shadows / Drain "N*(1+0.005x)%" masteries entered as literal percent, Night Lord Shadow Partner / Shadow
  Shifter (-> Final Damage) / Venom unlock 74 / Toxic Venom 130 ...
- **Shadower**: Assassinate factorIndex 12, Meso Mastery (Lv75, new row, 75% Meso chance, Attack buff), Steal moved
  from the Attack Speed stack (bug) to the Attack% bucket.
- **Hero / Dark Knight**: Puncture / Enhanced Raging Blow / Beam Blade / Rush / Spirit Blade / Combo masteries,
  Evil Eye / Hex / Rush reuse masteries, Magic Crash weaken as a GLOBAL damage-taken bonus (DK's old hack
  removed), Hex boss +20%, Final Attack mastery @54, Self Recovery FD.
- **Paladin**: Combat Orders now modeled for the player (time-averaged +skill-level factor lookup, +25%p Attack at
  Lv82, +18 levels for 4th-job skills at Lv104), Parashock Guard (+10%p on the skill used, as a live term), buff
  factorIndices 22 -> 21, missing masteries (HP Recovery, Divine Blessing, Vessel, Greater Vessel, Rush,
  Noble Demand reuse, Divine Mark detonation, Divine Judgment).
- **Ice/Lightning**: Blizzard Final Attack off any attack; Blizzard +50% @134 (incl. FA); Frozen Orb interval
  -0.2s @126 (0.5 -> 0.3); Elquines interval -20% moved 126 -> 130 (**level and value still unverified in game —
  the wiki's text is garbled**).
- **FP-Mage**: Meditation factorIndex 22 -> 21 (the other items the audit raised were confirmed correct by the user).
- **Bishop**: Triumph Feather's angel-power window has an 18s cooldown (on-fraction `p*R*10/(1+p*R*18)`).
- **Buccaneer** (rebuilt from the game capture): Sea Serpent Burst has a 7s cooldown (5s @78, 3s @118; it used to
  fire on every basic attack), Greater Sea Serpent I/II implemented (430% / +targets / +100% FD on Sea Serpent
  Burst only), Serpent Assault shares Sea Serpent Burst's trigger + cooldown (game table), Assault-Mode uptime
  `u = A/(A+N*T)` with activation interval `T = cooldown + 0.5/basic-attack-rate`, Serpent Scale pre-Assault +2%
  per held scale (avg 4% while rebuilding), Speed Infusion as a real action-costing buff (AS +20% x f21 and FD =
  20% of AS), Sea Serpent's Rage factorIndex 21 + Assault Mark (+15% x f21 damage taken, 5s per Octopunch cast),
  Raging Serpent Assault 2 hits per tick, Octopunch reuse @134, unlock levels, JobSteps (Serpent Assault / Serpent
  Scale / Roll of the Dice / Groggy are 3rd job), Crossbones / Time Leap factorIndex 21, Time Leap Grant +10%p.
  Assumptions: Serpent Assault shares the 7s cooldown; the 430% Greater-Sea-Serpent-I line uses factorIndex 12
  (no table ratio); smoothed (non-integer) activations per Assault window.
- **Corsair**: real mastery table (Blackboot +50 @73, Scurvy +50 @49, All Aboard +50 @78 and -30% intervals @94,
  Siege Bomber +50 @82 and Setup @68, Rapid Fire +70 @130, Swift Fire Weaken @54, Broadside Bombardment @118 /
  Setup @138), unlock levels, factorIndices (Majestic Presence 21 + 0.5s ICD, Jolly Roger 21, Ahoy Mateys 21),
  **Quickdraw second effect modeled** (every 3rd Easton doubled -> x(1+1/3); Brain Scrambler / Rapid Fire
  cooldown divided by `1+0.25*B*`, B* solved in closed form; the 1.5s cut per 3 casts is **assumed split evenly**
  between the two skills).
  Assumption to double-check: Bombardment (Lv118) replaces the Battleship's 330% ticks with 1900% x3 hits on 8
  targets every 2s — it is a large share of Corsair's DPS.

### Still open / needs an in-game check
- Ice/Lightning Elquines strike-interval mastery (level 126 vs 130, -20% vs the garbled "0.2%").
- Illusion Step Lv118 semantics (Bowmaster/Marksman): modeled as always-on, 28% during the 9s evasion window.
- Hero Puncture's wound damage-taken debuff — see the Hero entry above.
- Groggy Mastery's conditional Final Damage (Buccaneer), Fullmetal Jacket Def-Pen mastery (Corsair), Perseverance
  and other HP-conditional masteries: not modeled (assumed inside your Inputs).
- Final Attack / Majestic Presence internal cooldowns are not reduced by CDR (see above).

## Hero: Companions + Status Effect Damage / KO timeline (2026-11-14 port from FP-Mage)

Same feature set and rules as the FP-Mage sections above ("Companions", "Status Effect Damage, KO phases and the timeline engine"): Inputs `STATUS_EFFECT_DAMAGE %` (row 22; everything
from Min Damage down shifted one row, carry-over migration is self-detecting), `Companion` (row 51) + the new `Companion` / `CompanionKits` / `CompanionsInput` / `Timeline` sheets, Sensitivity
rows `STATUS_EFFECT_DAMAGE %` and `Companion Summoning Time Increase %`, the Companion Comparison and summoning-time tables, the Horn Flute rewire, weighted-ratio companion tables.  With
Companion = None, Status Effect Damage = 0 and a content without KO phases (Chapter Boss, Breakthrough, Hero Dungeon, PvP, EXP / Equipment Dungeon, Chapter Hunt) every total is bit-identical to the pre-port workbook.
Hero-specific wiring (everything else is the FP-Mage recipe):
- **Engine buffs**: Spirit Blade only (`STATUS_BUFFS = [("SB", SPIRIT_BLADE, "atk")]`).  Combo Attack (constant max stacks) is part of the engine's constant Attack% term `A0`; Enrage (FD / Crit Damage), Scaring
  Sword, Nimble Feet and the Puncture / Magic Crash damage-taken weakens are duty-cycled or proc effects the player cannot time and stay at their averages (also in the companion's snapshot).
- **Engine groups** (cast row -> rows): Puncture -> Puncture burst + wound DoT (`dot`, 10 s); Enhanced Raging Blow, Magic Crash, Beam Blade, Rush, Flash Slash -> one burst row each.  Uniform row: Raging Blow (the basic attack).
  Hero's boss / normal DPS columns are `T` / `V` (FP-Mage: `S` / `U`), so the timing factors `W`/`X` multiply those; `Y` = per-cast boss damage.
- **Companion host**: `unit` = Raging Blow's `N/F`; `bad` / `sd` = Basic Attack / Skill Damage buckets (+ Ring of Cycles); crit uses Hero's live crit bonus rows (Enrage Crit Damage average); `def_pen` is Hero's LIVE Defense Penetration (Advanced Combo stacks, `live_def_pen`)
  also inside the Reindeer's Spear extra-boss ratio; `avgbuff` = Summary `R_AVGBUFF` (Combo Attack + Spirit Blade + artifacts), `avgbuff_snap` has Combo at max stacks and Spirit Blade up; the companion's own boss / normal %
  bucket includes Hero's Global Monster Damage-Taken Bonus (Scaring Sword, Puncture wound, Magic Crash weaken) because that sits inside the Boss / Normal Monster Damage% buckets of every Hero row.  The "enemy damage taken" bucket the companion's
  debuffs add into is Hero's K-column bucket `1 + (Hexagon Damage% + Peach Tree / Silver Pendant)/100`: `agg_damage_avg` and `taken_bucket` are both that joint bucket (the Hexagon snapshot ratio and the debuff ratio are then exact up to a cross term).
- **Engine-on contents change by design**: World Boss and Enhancement Dungeon (KO phases) now run the optimal-player engine even with Status Effect Damage 0 and no companion.  Beam Blade, Rush and Flash Slash are worth less than the Raging Blow
  actions they replace (Raging Blow carries +75% mastery and the Final Attack fold-in), so the "optimal player" never casts them there (0 casts, 0 DPS from those rows); the averaged contents still cast them.
- **Not modelled**: Hero's own stuns (Rush 2.5 s, Puncture) as a source of Status Effect Damage windows - only the companion's stuns / freezes open windows (as the rest of the project: crowd control was already out of scope).  Chance Attack's own
  Status Effect Damage passive (12%->19.2%) is assumed baked into the `STATUS_EFFECT_DAMAGE %` Input like every other Magic-Critical-pattern passive.  The companion's Final Damage effects (x1.25 at Lv5/8/10, Bishop +8%...) multiply, while
  Hero's own Final Damage bucket is additive with Enrage / Combo Synergy (`(1 + (Final Damage% + Enrage + Combo Synergy)/100)`); ratios on the additive bucket would differ slightly.
- **Sensitivity strips**: besides FP-Mage's rebuild keys (CDR, Buff Duration, Shamaness Marble, Status Effect Damage, Summoning Time, Hexagon equip) Hero's blocks for Charm of the Undead / Old Music Box / Secret Map / Reindeer's Spear /
  Alliance Badge / Bottle of Emotion equip and for the 2nd-job / all-skill level inputs also re-run their own strip, because with the engine on Summary's Attack% bucket IS the strip's mean buff bucket (A0 incl. Charm and artifact Attack%,
  Spirit Blade's F).  Without this the Charm equip row read ~0 (found by the equipped-copy hand check; the same gap exists in the FP-Mage recipe for its Attack% artifacts).  Checked on World Boss / Blaze Wizard Lv10 / S=30 with
  Hexagon, Charm, Horn Flute and Bottle of Emotion equipped: every artifact row equals the total delta of the toggled copy to full precision; Sensitivity-vs-main OK for damage and status_effect_damage; skill_lvl_all differs by 7e-5
  (consistent with a different exact-tie Spirit Blade placement in the block's own strip, see below).
- **Verification**: `verify_hero_workbook.py` mirrors the engine and the companion; where the workbook's DP schedule is exactly as good as the script's own optimum the workbook's tie-break is adopted (many placements of Spirit Blade
- **Back-port of the Buccaneer-port recipe (2026-11-18)**: the re-running Sensitivity blocks now read the MAIN sheet's `s_0` / `W_0` for the strip's stun vector (companion stun; the player's Rush entries were already block-local), only the Summoning-Time block keeps its own, and `COMPANION_FULL_SEARCH_KEYS` (Summoning Time, Hexagon Necklace equip, Horn Flute equip, Skill Cooldown Decrease + its 10 milestone blocks) run the full 3-candidate companion search.  Main sheet / engine unchanged (every non-Sensitivity formula identical, Inputs identical; baseline Total DPS identical).  Sens-vs-main before the fix: only Breakthrough Skill Cooldown Decrease was off (0.99836335, Blaze Wizard Lv10, S=30); World Boss, the Wind Archer Lv7 + Summoning Time +20% case and the Bow Master case were already 1.00000000.  After: 1.00000000 everywhere tested (World Boss / Breakthrough: damage, status_effect_damage, skill_cooldown_decrease, summon time, buff duration, attack_pct; the flip and Bow Master cases).  Hexagon / Charm / Horn Flute equip rows equal the toggled-copy delta (World Boss, ratio 1.00000000).  A flip of the chosen candidate between base and swept value stays a second-order approximation for the other blocks.  Longest formulas unchanged (Sensitivity 8144, cap 8192).
  tie exactly without artifacts and floating-point noise decides; see the comment in the verify script).  Longest formulas: Sensitivity 8144 characters (the pre-port workbook already had 8087), Timeline 7362, Companion 6376.
- **Rebuilt for the companion cast timing rule (2026-11-18)** (see "Companions" -> "Cast timing"): Inputs / ArtifactsInput / PotentialCubes identical, only Companion-chain references and the CompanionKits columns changed (Hero's own Rush stun timing is unchanged).  Total shifts at the verify-script base Inputs (Lv200, Status Effect Damage 30, skills Lv10, no artifacts), Blaze Wizard Lv10 / Wind Archer Lv7 with Summoning Time +20%: World Boss -0.44% / -0.22%, Chapter Breakthrough -6.21% / 0.00% (Blaze loses a stun cast), Chapter Hunt -0.50% / 0.00%, PvP 0.00% / -1.94%.  Longest formulas now Sensitivity 8144 (cap 8192), Companion 6054, Timeline 1721.  Verify script == workbook on 12 scenarios, Sensitivity-vs-main ratio 1.00000000 (World Boss / Breakthrough, incl. the +12.9% flip), equip rows == toggled-copy delta, 0 error cells, cube mirror ~1e-16.
- **Arwen's Glass Shoes + "no DPS effect" relabelling (2026-11-19, replayed from FP-Mage)**: the shoes are a REAL, live Companion Summoning Time Increase (+20% star 0 .. +40% star 5, linear 20/24/28/32/36/40, all user-confirmed 2026-11-19); effective increase = Inputs value + artifact (`companion_summon_time_inc_expr`) in the Companion host, every Sensitivity block, `b0` (artifact added outside the `MAX(0, ...)`) and so the CompanionsInput table / cube script; the equip row is in `STATUS_REBUILD_KEYS`, `COMPANION_FULL_SEARCH_KEYS` and `SUMMON_TIME_KEYS`.  The seven artifacts without a DPS effect are labelled "no DPS effect (reason)" (`ARTIFACT_NO_DPS_EFFECT`; ArtifactsInput has a 15th column "Equip effect in the DPS model").  Inputs / ArtifactsInput / PotentialCubes carried over with 0 diffs (only the Companion Summoning Time Increase label changed); Sensitivity grew by one strip (+181 rows); `cyc.py` 0 cyclic components; longest formula 8144 (Sensitivity T1464, unchanged; cap 8192), Companion 6054.  Verified on the Hero workbook: equivalence (Total DPS with shoes star s at Inputs x == without shoes at x + 20..40) bit-for-bit on 10/10 pairs (World Boss Blaze Lv10 star 0 = in20, star 5 = in40, star 5 + in5 = in45 across the 3rd-stun flip, + Bottle / Hexagon / Horn Flute; Breakthrough Wind Archer Lv7 x4; Chapter Hunt x2); Sensitivity equip row == toggled-copy delta 1.00000000 (World Boss, from BOTH directions: % Gain 107.44578562073409 each; Hexagon + Horn Flute + Bottle base; Chapter Hunt), Summoning-Time stat and damage blocks with the shoes equipped 1.00000000, Breakthrough equip row == time-weighted expected 1.00000000 (its dollar delta differs by design, CLAUDE.md item 9); 0 error cells and cube mirror ~2e-16 (World Boss, Breakthrough Blaze Lv10; Wind Archer Lv7 5e-10, fractional-window artifact) with shoes + Hexagon + Horn Flute + Bottle equipped.  The engine side (`engine/classes/hero.py`) models the artifacts since the same day: `tests/golden/hero_artifacts_golden.json` / `test_hero_artifacts.py`.
- **Hero Sensitivity fixes (2026-11-21; FP-Mage's two fixes replayed per stat)**: (1) strip rebuild set.  Added `skill_damage`, `basic_attack_damage`, `boss_damage`, `crit_rate`, `skill_lvl_3rd` / `_4th` and the toggles `ring_of_cycles`, `book_of_ancient`, `rainbow_snail_shell`, `candle`, `sayrams_necklace`, `star_rock` (12 more strips, Sensitivity 7762 -> 9934 rows).  Engine experiment (`stl.solve` captured base vs swept, ~620 engine-on configs, World Boss / Enhancement Dungeon / Chapter Boss, Lv63-200, five stat sets, deltas +1 .. +1000): Basic Attack Damage flips the schedule in ~40% of the configs (the Raging Blow a cast replaces is the discrete decision), Skill Damage, Crit Rate (Ring of Cycles) and the Ring toggle in some; Boss Damage was exact in the first two stat sets and moved the total -2.0% at +100 (-3.4% at +300) in the third (Raging Blow / Enhanced Raging Blow carry their own Boss Mastery), so it and the boss-bucket artifacts (Candle, Sayram's, Star Rock: baked, its what-if is exactly Boss Damage +100) were added after the first build (Star Rock read 0.98899 of the toggled copy before).  `skill_lvl_3rd` / `_4th` are listed for their PASSIVE deltas (Chance Attack / Combat Mastery / Power Stance), which the engine cannot see; `skill_lvl_1st` stays reused (Nimble Feet, unscaled, is the only step-1 skill).  Everything else (Flat STR .. Flat ATTACK, Attack Speed, Final Damage, Contract of Darkness, every other artifact) is exact under reuse (240 configs re-checked with the final set: 0 outside it).  (2) baked-in Final Damage what-ifs (Cursed Doll, Lit Lamp, Clear Spring Water, Soul Pouch, Bottle of Emotion's Attack-Speed-dependent value) are multiplicative factors on the TYPED `Inputs!final_damage`, applied INSIDE the additive bucket `(1 + (final_damage + passive + Enrage/Combo Synergy/Lv98)/100)` through block-local helper cells (column U, 4th / 5th skill row): adding = `1 + x/100`, removing = its exact inverse.  (3) **Bug 19 found and fixed**: Raging Blow's `SkillFoldBonus%` (Final Attack x Advanced Final Attack) read the MAIN Calc helper rows, so Sensitivity blocks sweeping `skill_lvl_2nd` / `_4th` / `_all` never saw it move; each block now re-points the fold at its own helper rows.  Soul Contract: only two cooldown call sites exist (main Calc, Sensitivity block), both wired; Chapter Hunt toggled-copy test 1.000000000000 (% Gain 143.4087).  Not changed (pre-existing approximation): Ring of Cycles' crit-rate threshold in a block does not include the passive Crit Rate delta of `skill_lvl_3rd` (too few characters left in the cap-tight formulas; no effect while the crit rate sits away from 100%).  Verified on the final workbook (Sensitivity-slimmed copies <= 8 blocks, Ring of Cycles + Bottle + Reindeer equipped, Lv150): sens-vs-main (swept Input set to the block's New Value) ratio 1.000000000000 for `skill_damage`, `basic_attack_damage`, `boss_damage`, `crit_rate`, `attack_speed` (Bottle FD retyped), `final_damage` (Input = New Value - R_FD_BONUS) in World Boss AND Enhancement Dungeon; `skill_lvl_1st/2nd/3rd/4th/all` 1.000000000000 against a main re-run carrying the block's documented passive deltas; Ring / Rainbow / Candle / Sayram's / Star Rock (Boss Damage +100 typed) / Glass Shoes / Soul Contract rows == toggled copy 1.000000000000 (gain and table gain).  Baked-in Final Damage pairs identical from BOTH directions (gain and % Gain, rel diff <= 3.5e-16) and == Total(equipped) - Total(unequipped): Cursed Doll 108.1210% (Flaming Lava live), Lit Lamp 123.2028%, Bottle of Emotion 122.2022% (Attack Speed 80), Clear Spring Water 111.6014% (Enhancement Dungeon), Soul Pouch 123.5740% (PvP); Book of Ancient (direct + dependent typed) 135.8634% both directions; Glass Shoes 107.2797% from both directions.  0 error cells (World Boss, Breakthrough, Breakthrough + Wind Archer Lv7; Sensitivity stripped; Shoes + Hexagon + Horn Flute + Bottle) and cube mirror 4.9e-16 / 2.1e-16 / 5.4e-10 (the usual fractional-window effect); `cyc.py` 0 cyclic components; longest formula 8127 (Sensitivity T1464 / T2010, boss-DPS cells of two re-running blocks; it was 8144 before; cap 8192), Companion 6054, Timeline 1721.  Inputs / ArtifactsInput / PotentialCubes and every non-Sensitivity sheet formula-identical before / after (0 cell diffs); Hero engine goldens unchanged (`test_hero.py` 262, `test_hero_artifacts.py` 58 green).  (Hero's engine Sensitivity followed on 2026-11-22: see "Hero: Sensitivity in the engine".)

## Paladin: Companions + Status Effect Damage / KO timeline (2026-11-15 port from FP-Mage / Hero)

Same feature set and rules as the FP-Mage / Hero sections above: Inputs `STATUS_EFFECT_DAMAGE %` (row 22, self-detecting row-shift migration), `Companion` (row 51) + live `Companion Summoning Time Increase %`, sheets
`Timeline` / `CompanionKits` / `Companion` / `CompanionsInput`, Sensitivity rows for both stats, the Companion Comparison and summoning-time tables (weighted-ratio form), the Horn Flute rewire (`Companion!horn_uptime`) and the
exported host values for `potential_cubes_ev.py` (checked: the Python mirror rebuilt from the exported values reproduces the sheet's companion DPS and its b0+20 grid column to 1e-15 for World Boss / Breakthrough / Chapter Hunt / Hero Dungeon).
With Companion = None, Status Effect Damage = 0 and a steady-state content (Chapter Hunt) the total is bit-identical to the pre-port workbook (86022698488133888 on the user's Inputs).
Paladin-specific wiring (the rest is the recipe):
- **Engine buffs** (`STATUS_BUFFS`): HP Recovery and Combat Orders (its Lv82 +25%p Damage Boost; below Lv82 its casts keep the averaged formula) as Attack% buffs; **Guardian and Divine Blessing as Final Damage buffs**.  Paladin's FD bucket is
  ADDITIVE with the base FINAL_DAMAGE % and the other FD buffs, `1 + (F0 + FDrest + g(t))/100`, so a time-varying g(t) enters the engine's multiplicative term as `g(t) x 100/(100 + F0 + FDrest)` (`fd_scale`; flat 'ramp' profile, duration capped at the cooldown
  so a recast never stacks).  With the engine on `Summary!R_AVGBUFF` = the strip's mean buff bucket and `R_FD_BONUS` = `R_FD_REST` (Divine Shield + Greater Vessel only); engine off = the old averages.  `R_FD_ALL` (all four) is what the Final Damage
  "+1% mult" Sensitivity test scales.  Not player-timed, so averaged: Vessel of Light / Greater Vessel (procs), Divine Shield (fixed interval), Nimble Feet, the Weaken debuffs.  Combat Orders' +skill-level half stays the time-averaged FactorTable lookup, with the uptime of the engine's cast count.
- **Engine groups**: Close Combat, Noble Demand, Heaven's Hammer, Divine Mark (main hit + detonation share one cast), Magic Crash, Rush (all bursts).  Uniform rows: Blast and Divine Judgment (a proc off every 10 basic attacks, its `10/APS` cooldown is a rate surrogate, never a cast).  No DoT rows (`STATUS_FS_KEYS` empty).
  Boss / normal DPS columns are `T` / `V` (as Hero); `W`/`X` timing factors, `Y` per-cast boss damage, **`Z` = the pre-engine (averaged-model) cast count**.
- **Vessel of Light must not read the engine's cast counts**: its uptime depends on the Blast rate, which depends on the engine's casts, which depend on the engine's value of a cast, which includes the constant Attack% term A0 that holds Vessel of Light - a real loop.
  So Vessel of Light / Greater Vessel use `Summary!R_BAPS_AVG` (Blast rate from `R_CASTRATE_AVG`, the SUMPRODUCT over column Z), identical to the old rate whenever the engine is off; with the engine on it can differ slightly from the engine-aware `R_BAPS` (the slots the optimal player's different cast counts free or use).
- **Player stun**: Rush (2.5 s, cooldown 22 s, Reuse Lv90 already in `Calc!Q`) as a fixed on-cooldown stun group (`STATUS_PLAYER_STUN`, host `pst` in the main / block / exported hosts, `pl_stun` in the engine host).  Rush unlocks at Lv63, so the engine is ON in every
  fixed-length single-target content from there (Breakthrough's boss phase is lengthened by the stuns; Hero Dungeon is not).  Fixed (not optimised) means Rush no longer waits for a KO window.
- **Companion host**: `unit` = Blast's `N/F`; `avgbuff` = `R_AVGBUFF` x the Final Damage factor `(1 + (F0 + R_FD_BONUS)/100)` (Paladin's buffs live in BOTH buckets); the snapshot has the CAST buffs (HP Recovery, Combat Orders, Guardian, Divine Blessing) fully up and the procs / fixed-interval buff at their averages
  (`k1` and `fdpart` exported for the cube script); like Bowmaster, the "enemy damage taken" bonuses (artifacts, Close Combat / Noble Demand / Divine Mark Weaken) sit INSIDE the boss / normal monster damage % buckets (`R_MONSTER_DMG_BONUS`), so `taken_bucket` is the boss/normal blend (0 in PvP).
  The companion's own Final Damage effects (x1.25 at Lv5/8/10, Bishop +8%) multiply, while Paladin's own FD bucket is additive (same approximation as Hero).
- **Formula-loop fixes found by `cyc.py`** (pure-syntax loops, values unchanged): factor lookups of 1st/2nd-job rows, Nimble Feet and Combat Orders no longer read Combat Orders' uptime / `F` (`CO_PLAIN_FACTOR_KEYS`; the bonus only reaches 3rd/4th-job skills anyway).
  Blocks now use their OWN Combat Orders uptime (extra block cell `Combat Orders uptime of this block`, rows `R_CASTRATE_AVG`..`R_FD_ALL` mirrored too: BLOCK_HEIGHT = LAST_ROW + 21), so CDR / Buff Duration sweeps move the skill-level averaging as the full model does.
  Divine Judgment's `10/Summary!APS` cooldown is re-derived from the block's own Actions Per Second (bug #19 pattern; it was invisible to the Attack Speed block).
- `STATUS_REBUILD_KEYS` (blocks that re-run their own strip) = FP-Mage's plus the Attack%-artifact toggles, `skill_lvl_3rd/4th/all`, `final_damage` (the FD scale) and `attack_speed` (Vessel of Light's rate).
- **Not modelled**: the player's other crowd control; the Combat Orders skill-level half as a timed effect; Divine Judgment's +30% Basic Attack Damage (was already flagged).
- **Verification** (2026-11-15, artifacts cleared, Sensitivity stripped): `verify_paladin_workbook.py` == workbook for Chapter Boss / World Boss / Enhancement Dungeon / Breakthrough (companion None = the Rush extension, and Blaze Wizard / Bow Master) / Hero Dungeon / Chapter Hunt / EXP /
  Equipment / Weapon Dungeon / PvP with Blaze Wizard (stunning), Wind Archer and Bow Master (non-stunning) and None, at Lv 50 / 70 / 80 / 110 / 125 / 200 and with Buff Duration +40% + CDR 3 s.  `cyc.py` 0 cyclic components; longest formulas Sensitivity 7625, Timeline 7606, Companion 6376;
  zero error cells (World Boss and Breakthrough, Hexagon + Charm + Horn Flute + Bottle of Emotion equipped).  Sensitivity-vs-main (World Boss, Blaze Wizard Lv10, S=30, Lv200, Bottle of Emotion + Reindeer's Spear; run on a Sensitivity-SLIMMED copy: only the tested blocks and their strips kept, see below):
  `damage`, `status_effect_damage`, `skill_cooldown_decrease`, `buff_duration_increase_pct`, `companion_summon_time_increase_pct`, `attack_pct`, `final_damage` ratio 1.00000000.  Two deliberate differences: `skill_lvl_3rd` / `skill_lvl_all` read +2.0e-4 / +2.3e-4 high
  (the Sensitivity block adds Parashock Guard's +Attack% growth, a "Magic Critical pattern" delta the main sheet assumes baked into the Inputs) and `attack_speed` reads +1.3e-3 high with Bottle of Emotion equipped (its Attack-Speed-dependent Final Damage, same pattern; ratio 1.00000000 without the Bottle).
  Hexagon Necklace / Charm of the Undead / Horn Flute equip rows == total delta of the toggled copy (ratio 1.00000000; slimmed Sensitivity: the ArtifactsInput potential-line term, which reads every other Sensitivity row, was subtracted).  The slimmed runs keep one block per tested stat (the stock `sens_comp.py` evaluates the whole Sensitivity sheet, ~1.5 h per run; the slimmed runs took 3-7 min).
- **Back-port of the Buccaneer-port recipe (2026-11-18)**: the re-running Sensitivity blocks now read the MAIN sheet's `s_0` / `W_0` for the strip's stun vector (companion stun; the player's Rush entries were already block-local), only the Summoning-Time block keeps its own, and `COMPANION_FULL_SEARCH_KEYS` (Summoning Time, Hexagon Necklace equip, Horn Flute equip, Skill Cooldown Decrease + its 10 milestone blocks) run the full 3-candidate companion search.  Main sheet / engine unchanged (every non-Sensitivity formula and every Input identical to the pre-rebuild workbook; baseline Total DPS identical).  Sens-vs-main (Blaze Wizard Lv10, S=30, Lv200, Bottle of Emotion + Reindeer's Spear) before the fix: Breakthrough Skill Cooldown Decrease was off by 1.00252053 (Blaze Wizard), 1.00489322 (Wind Archer Lv7 + Summoning Time +20%, chosen summon 7 s vs candidate-0 10.2 s) and 1.00494164 (Bow Master); World Boss was already 1.00000000.  After: 1.00016261 / 1.00016644 / 1.00017521; `damage`, `status_effect_damage`, `companion_summon_time_increase_pct`, `attack_pct` are 1.00000000 everywhere tested (World Boss + Breakthrough).  The remaining ~1.6e-4 on Breakthrough CDR and ~4.5e-5 on `buff_duration_increase_pct` (all contents) is NOT the companion gap: it is exactly the Parashock Guard "baked into Inputs" delta (block F 35.60995 vs main base F 35.5735 = +0.03645 on the strip's constant Attack% term) - a CDR / Buff Duration sweep moves Combat Orders' uptime and with it Parashock Guard's skill-level factor, which the main sheet leaves in the Inputs but the block adds as a delta (same pattern as the `skill_lvl_*` +2e-4 above).  Hexagon / Charm / Horn Flute equip rows equal the toggled-copy delta (World Boss, ratio 1.00000000).  A flip of the chosen candidate between base and swept value stays a second-order approximation for the other blocks.  Longest formulas unchanged (Sensitivity 7625, cap 8192); `cyc.py` 0 cyclic components.
- **Rebuilt for the cast timing rule (2026-11-18)** (see "Companions" -> Cast timing): every Input / ArtifactsInput / PotentialCubes value identical to the pre-rebuild workbook; Calc / Summary / Skills / Artifacts / CubeData / CompanionsInput identical up to Companion-sheet row references; only the Companion chain, CompanionKits columns and the Timeline stun vector changed.  Total-DPS shifts (verify-script totals on a synthetic Lv200 set, Status Effect 30): World Boss Blaze Wizard Lv10 -0.58% / Wind Archer Lv7 +20% -0.24%; Breakthrough Blaze -6.48% / Wind Archer 0.00%; Chapter Hunt Blaze -0.53% / Wind Archer 0.00%; PvP Blaze 0.00% / Wind Archer -1.94%.  Sens-vs-main (Blaze Lv10, S=30, Lv200, Bottle of Emotion + Reindeer's Spear): `damage`, `status_effect_damage`, `companion_summon_time_increase_pct` 1.00000000 (World Boss, Breakthrough, also from a +12.9% base, New Value 13.9 crosses 13.667); Breakthrough `skill_cooldown_decrease` 1.000163 (1.000163 before the rebuild too; the documented Parashock Guard residual), World Boss 1.00000000; Hexagon / Charm / Horn Flute equip rows == toggled copy.  Longest formulas Sensitivity 7625, Companion 6054 (< 8192); `cyc.py` 0 cyclic components.
- **Arwen's Glass Shoes + "no DPS effect" relabelling (2026-11-20, replayed from FP-Mage / Hero)**: the shoes are a REAL, live Companion Summoning Time Increase (+20% star 0 .. +40% star 5, linear 20/24/28/32/36/40, all user-confirmed 2026-11-19); effective increase = Inputs value + artifact (`companion_summon_time_inc_expr`) in the Companion host, every Sensitivity block, `b0` (artifact added outside the `MAX(0, ...)`) and so the CompanionsInput table / cube script; the equip row is in `STATUS_REBUILD_KEYS`, `COMPANION_FULL_SEARCH_KEYS` and `SUMMON_TIME_KEYS`.  The seven artifacts without a DPS effect are labelled "no DPS effect (reason)" (`ARTIFACT_NO_DPS_EFFECT`; ArtifactsInput has a 15th column "Equip effect in the DPS model").  Inputs / ArtifactsInput / PotentialCubes carried over with 0 diffs (only the Companion Summoning Time Increase label changed); Sensitivity grew by one strip (+202 rows); `cyc.py` 0 cyclic components; longest formula 7625 (Sensitivity T1628, unchanged; cap 8192), Companion 6054.  Verified on the Paladin workbook (the 64-case artifact golden set doubles as the equivalence test): Total DPS with shoes star s at Inputs x == without shoes at x + 20..40 bit-for-bit on 10/10 pairs (World Boss Blaze Lv10 star 0 = in20, star 5 = in40, star 5 + in5 = in45 across the 3rd-stun flip, + Bottle / Hexagon / Horn Flute; Breakthrough Wind Archer Lv7 x4; Chapter Hunt x2); Sensitivity equip row == toggled-copy delta 1.00000000 (World Boss, from BOTH directions: % Gain 105.99779814104784 each; Hexagon + Horn Flute + Bottle base 104.61031471365013; Chapter Hunt 107.22501923988399), Summoning-Time stat and damage blocks with the shoes equipped 1.00000000, Breakthrough equip row == time-weighted expected 1.00000000 (its dollar delta differs by design, CLAUDE.md item 9); 0 error cells and cube mirror <= 4e-16 (World Boss, Breakthrough Blaze Lv10; Wind Archer Lv7 5e-10, fractional-window artifact) with shoes + Hexagon + Horn Flute + Bottle equipped.  The documented ~1.6e-4 Parashock Guard Breakthrough CDR residual is unrelated and unchanged.  The engine side (`engine/classes/paladin.py`) models the artifacts since the same day: `tests/golden/paladin_artifacts_golden.json` / `test_paladin_artifacts.py` (64 workbook evaluations, engine == workbook within rel 1.3e-10 worst case, ~1e-15 typically).
- **Paladin Sensitivity fixes (2026-11-22, replayed from FP-Mage / Buccaneer)**: (1) strip rebuild set (`STATUS_REBUILD_KEYS`).  Engine experiment (`stl.solve` outputs of the main run REUSED vs re-solved at the swept value, World Boss / Enhancement Dungeon, Lv 63-200, stat sets A/B/C, Blaze / none, small and big deltas, with / without Ring of Cycles; ~3000 further extreme-delta runs): the strip moves only for the stats already in the set plus `skill_lvl_2nd` (Close Combat, Weapon Acceleration -> Attack Speed -> Vessel of Light's rate / A0), `skill_damage` / `basic_attack_damage` (skill rows vs the Blast a cast replaces; x4 at +300), `crit_rate` with Ring of Cycles (its Skill / Basic Attack bonus follows the crit rate) and `boss_damage` (Blast's own +20% Boss Mastery; only at extreme negatives).  Added: those five, the toggles `ring_of_cycles`, `book_of_ancient`, `rainbow_snail_shell`, `candle`, `sayrams_necklace`, `star_rock` (insurance / Ring feeds) and the four baked-in Final Damage toggles (`BAKED_FD_KEYS`).  NOT added (reused strip, exact < 1e-14): `skill_lvl_1st` (Nimble Feet is the only 1st-job row and does not scale: zero gain), every uniform stat.  `skill_lvl_4th` is capped at Lv200 (FactorTable lookup min(300, .)): +1 reads zero there by design.  Cost: +15 strips (Sensitivity 9465 -> 12495 rows).  (2) baked-in Final Damage what-ifs (Cursed Doll, Lit Lamp, Clear Spring Water, Soul Pouch, Bottle of Emotion's Attack-Speed-dependent value) are a RETYPED `Inputs!final_damage` in the block (helper cell `U` of the 4th skill row; `ib("final_damage")` reads it everywhere incl. the strip's `fd_scale` and the companion snapshot): adding = `((1+F/100)(1+x/100)-1)*100`, removing = `((1+F/100)/(1+x/100)-1)*100`, exact inverses; deliberately NOT FP-Mage's plain factor on the product because Paladin's Input sits in the ADDITIVE bucket with Divine Shield / Guardian / Divine Blessing / Greater Vessel (a toggled copy of the workbook gives a smaller ratio than 1 + x/100 and moves `fd_scale`).  (3) bug 19: Blast's `SkillFoldBonus%` (Final Attack helper F x Maple Hero helper F) read the MAIN Calc rows - re-derived from the block's own helper rows (`build_stat_block`, end), so `skill_lvl_2nd` / `_all` now move Final Attack inside the blocks.  Soul Contract: applied at both real cooldown call sites (main `Calc!Q`, block `Q`; every buff uptime / the strip read `1/Q`), none missing.  Observation, NOT changed (main sheets + engine would move): Divine Judgment's `10/APS` trigger-interval surrogate is CDR-exempt but still gets Soul Contract's Chapter-Hunt cut in the workbook AND the engine (same in Night Lord's exempt rows) - a proc every 10 basic attacks is not a real cooldown.  PvP: Paladin has no Defense % input, workbook and engine both use flat Defense.  Main sheets formula-identical before / after (Inputs / Skills / Artifacts / Calc / Summary / Timeline / Companion / CompanionKits / ArtifactsInput / PotentialCubes 0 diffs; Sensitivity only), 0 Input diffs, `cyc.py` 0 cyclic components, longest formula 7625 (Sensitivity T1628, unchanged; cap 8192).  Verification (one evaluation at a time, slimmed Sensitivity, Sensitivity-emptied main re-run with the swept Input set to the block's New Value; Ring of Cycles / Bottle / Reindeer's equipped, Lv200 World Boss, Lv140 Enhancement Dungeon, Breakthrough): `skill_damage`, `basic_attack_damage`, `boss_damage`, `crit_rate` (also at crit 10 with the Ring, below the cap), `final_damage`, `attack_speed` (Bottle), `flat_attack` ratio 1.0000000000 in World Boss and Enhancement Dungeon (Breakthrough too for skill_damage / crit_rate); `skill_lvl_2nd` / `_3rd` / `_all` differ from a plain main re-run by exactly the documented passive-delta terms (+0.0466% / +0.0233% / +0.0700% WB, +0.0438% / +0.0671% ED) and are 1.000000000000 once those deltas are applied; the Parashock Guard Breakthrough residual is unchanged and exactly that delta: CDR plain 1.00016182 (was 1.00016261), Buff Duration 1.00004044, both 1.000000000000 with the delta folded into the main re-run.  Two-direction check of the five baked-in Final Damage artifacts (matched typed pairs; block read in state 0 == Total(state 1), read in state 1 == Total(state 0), gain and % Gain identical from both sides to <= 5.3e-16): Cursed Doll 106.4854% (WB, with Candle), Lit Lamp 118.5295% (WB), Bottle of Emotion 119.8963% (WB, Attack Speed 84), Clear Spring Water 109.5079% (ED), Soul Pouch 119.7907% (PvP).  Equip rows == toggled copy (gain and table gain 1.00000000, WB): Ring of Cycles 131.58%, Candle 125.09%, Sayram's Necklace 109.79%, Rainbow Snail Shell 107.52%, Arwen's Glass Shoes % Gain 105.99779814104784 (unchanged).  Star Rock / Book of Ancient are baked-in additive Inputs (their toggled copy needs the value typed; same pattern as before).  0 error cells and cube mirror 3.5e-16 (World Boss), 0 (Breakthrough), 5.3e-10 (Breakthrough + Wind Archer Lv7, the usual `INT(x + 1e-9)` window effect).  `test_paladin.py` (295) and `test_paladin_artifacts.py` (64) stay green with no golden regeneration; `engine/sensitivity.py` is not updated here (the engine-side Paladin Sensitivity is a separate job).

## Dark Knight: Companions + Status Effect Damage / KO timeline (2026-11-15 port from FP-Mage / Hero / Paladin)

Same feature set and rules as the FP-Mage / Hero / Paladin sections above: Inputs `STATUS_EFFECT_DAMAGE %` (row 23, self-detecting row-shift migration; Dark Knight's Inputs sit one row below Hero's because of the Defense % row), `Companion` (row 52; rows 48-51 are the artifact slots) + live
`Companion Summoning Time Increase %`, sheets `Timeline` / `CompanionKits` / `Companion` / `CompanionsInput`, Sensitivity rows for both stats, the Companion Comparison and summoning-time tables (weighted-ratio form), the Horn Flute rewire (`Companion!horn_uptime`) and the exported
host values for `potential_cubes_ev.py` (checked: the Python mirror rebuilt from the exported cells reproduces the sheet's companion DPS and its b0+20 grid column to 1e-15, Breakthrough, Hexagon + Charm + Horn Flute + Bottle of Emotion equipped).  With Companion = None, Status Effect Damage = 0 and a content
where the engine stays off (Chapter Hunt, PvP, EXP / Equipment dungeon) every total is bit-identical to the pre-port workbook (Chapter Hunt 69462246.06591031, PvP 12301836.558148105, EXP Dungeon 77273929.12046549 on a test input set).  Dark Knight-specific wiring:
- **Engine buffs** (`STATUS_BUFFS`, all Attack% 'atk'): Hex of the Evil Eye, Dark Resonance, Cross Over Chains, Hyper Body.  Dark Knight has no constant Attack% skill, so the engine's constant term A0 is just the artifact Attack% (without Charm).  NOT player-timed, they stay at averages (also in the
  companion's snapshot): Evil Eye's damage-taken debuff, Dark Resonance's +20% boss damage clause, Hex's Lv82 boss-damage clause, Magic Crash's Lv126 Weaken (all additive inside Summary `R_MONSTER_DMG_BONUS`, i.e. inside the boss / normal monster damage % buckets; the Hex / Dark Resonance uptimes
  used there are the ENGINE's cast counts), Lord of Darkness (proc) and Nimble Feet.  Hex of the Evil Eye and Evil Eye of Dominant are tied to the Evil Eye summon in the game; the engine times each on its own cooldown spacing (30 s, 21 s from Lv104) independent of each other and of the Evil Eye cast itself
  (which stays an averaged action-slot row) - the summon is assumed up whenever they are cast.
- **Engine groups**: Magic Crash, Gungnir's Descent, Evil Eye Shock, Rush (bursts) and Evil Eye of Dominant (a `dot` over its 20 s window, no action slot: `STATUS_GROUP_TAKES_SLOT`; its hits come from the engine's effective cast count like Puncture's wound in Hero).  Uniform rows: Dark Impale (basic attack) and
  Revenge of the Evil Eye (a 5 s-cooldown self-triggered proc).  Boss / normal DPS columns are `T` / `V`, timing factors `W`/`X`, per-cast boss damage `Y`.
- **Player stuns**: Rush (2.5 s, cooldown 22 s, Reuse Lv90 already in `Calc!Q`) and Evil Eye Shock (1.5 s, cooldown 18 s; it needs the Evil Eye summon, assumed up while the skill is unlocked) are fixed on-cooldown stun groups (`STATUS_PLAYER_STUN`: host `pst` in the main / block / exported hosts,
  `pl_stun` in the engine host).  Evil Eye Shock unlocks at Lv40, so the engine is ON in every fixed-length single-target content from there; in Chapter Breakthrough the stuns lengthen the boss phase (also with Companion = None), Hero Dungeon is timed (no extension).  Fixed means those two no longer wait for a KO window.
- **Engine-on contents change by design**: World Boss, Enhancement Dungeon and (single-target) Chapter Boss / Weapon Dungeon run the optimal-player engine even with Status Effect Damage 0 and no companion, because a player stun exists from Lv40.
- **Companion host**: `unit` = Dark Impale's `N/F`; `avgbuff` = Summary `R_AVGBUFF` (no separate Final Damage buff factor, `fdpart` = 1); the snapshot has the four CAST buffs fully up (`k1`); like Paladin / Bowmaster the 'enemy damage taken' bonuses sit inside the boss / normal monster damage % buckets, so `taken_bucket`
  is the boss/normal blend (0 in PvP) and `agg_damage_avg` is just the Hexagon part of the Damage bucket.  Dark Impale's Boss Monster Damage mastery is a skill mastery and is not part of the companion's `boss_pct`.
- **Formula cap**: the pre-port workbook already had Sensitivity row formulas past Excel's 8192 characters (8368).  Each Sensitivity block now keeps the block twin of `R_MONSTER_DMG_BONUS` and of the averaged Attack% bucket sum in two own cells (rows `calc_end+14` / `calc_end+15`, inside the unchanged `BLOCK_HEIGHT`)
  instead of inlining the Evil Eye / Dark Resonance / Hex uptime expressions in every row; longest formulas now Sensitivity 7225, Timeline 7843, Companion 6376, Calc 4326.
- `STATUS_REBUILD_KEYS` (blocks that re-run their own strip) = FP-Mage's plus the Attack%-artifact toggles and `skill_lvl_2nd/3rd/4th/all` (the four buffs' F).
- **Not modelled**: the player's other crowd control; Evil Eye's debuff / Dark Resonance's boss clause / Magic Crash's Weaken as time-resolved effects; Hex / Evil Eye of Dominant sharing one Evil Eye cast with the summon itself; Iron Wall's Defense -> STR conversion is a stat-side input (unchanged).
- **Verification** (2026-11-15, artifacts cleared, Sensitivity stripped, non-trivial Inputs: crit / boss / skill damage / def pen / STR / min-max damage): `verify_dark_knight_workbook.py` == workbook (via `data/porting/helpers/sv.py`) for World Boss (None and Blaze Wizard Lv10, S=30; Lv 30 / 45 / 65 / 80 / 100 / 110 / 125 / 140),
  Enhancement Dungeon (Blaze Wizard; Wind Archer Lv7 with Buff Duration +40% and CDR 3 s), Chapter Boss, Breakthrough (None = the player-stun extension, Blaze Wizard, Bow Master; Lv50 None), Hero Dungeon, Chapter Hunt, EXP / Equipment / Weapon Dungeon, PvP with Blaze Wizard (stunning) and Bow Master (non-stunning).
  `cyc.py` 0 cyclic components; zero error cells (World Boss and Breakthrough, Hexagon + Charm + Horn Flute + Bottle of Emotion equipped).  Sensitivity-vs-main (World Boss, Blaze Wizard Lv10, S=30, Lv200, Bottle of Emotion + Reindeer's Spear equipped; Breakthrough with the same setup; run on a Sensitivity-SLIMMED copy
  with only the tested blocks and their strips kept, the stock `sens_comp.py` evaluates the whole sheet): `damage`, `status_effect_damage`, `skill_cooldown_decrease`, `companion_summon_time_increase_pct` ratio 1.00000000 in both contents.  Hexagon Necklace / Charm of the Undead / Horn Flute equip blocks == the total of the matching toggled copy
  (World Boss, Bottle of Emotion baseline, ratio 1.00000000; gains +4.15M / +0.19M / +0.91M on 8.42M).
- **Back-port of the Buccaneer-port recipe (2026-11-19)**: the re-running Sensitivity blocks now read the MAIN sheet's `s_0` / `W_0` for the strip's stun vector (`_stun_ref`; covers the companion stun, the Rush / Evil Eye Shock entries were already block-local), only the Summoning-Time block keeps its own, and `COMPANION_FULL_SEARCH_KEYS` (Summoning Time, Hexagon Necklace equip, Horn Flute equip, Skill Cooldown Decrease + its 10 milestone blocks) run the full 3-candidate companion search.  Only Sensitivity formulas changed (every other sheet and every Input identical to the pre-fix workbook).  Sens-vs-main (Blaze Wizard Lv10, S=30, Lv200, Bottle of Emotion + Reindeer's Spear, slimmed copy) before the fix: Breakthrough Skill Cooldown Decrease 1.00463165 (chosen summon 7 s vs candidate-0 31 s); World Boss and every other key 1.00000000.  After: 1.00000000 for `damage`, `status_effect_damage`, `skill_cooldown_decrease`, `companion_summon_time_increase_pct`, `buff_duration_increase_pct`, `attack_pct` in World Boss and Breakthrough with Blaze Wizard Lv10, Wind Archer Lv7 + Summoning Time +20% (chosen summon 7 s vs s_0 13.2 s) and Bow Master (Breakthrough); candidate-flip case Blaze Wizard with base Summoning Time +12.9% (the Sensitivity "New Value" is 13.9, crossing the 13.667 threshold of Blaze's 3rd stun cast): CDR and Summoning Time 1.00000000 in World Boss and Breakthrough.  Hexagon / Charm / Horn Flute equip rows equal the toggled-copy delta (World Boss, ratio 1.00000000).  A flip of the chosen candidate between base and swept value stays a second-order approximation for the other blocks.  Longest formulas unchanged (Sensitivity 6903, cap 8192); `cyc.py` 0 cyclic components.
- **Rebuilt for the companion cast timing rule 2026-11-18** (see Companions -> "Cast timing"; Rush / Evil Eye Shock player stun timing unchanged; 0 Input / ArtifactsInput / PotentialCubes diffs, no hand-typed cell dropped).  Total shifts vs the pre-change workbook (test inputs, Lv200, S = 30): Blaze Wizard Lv10 World Boss -0.40%, Breakthrough -7.20%, Chapter Hunt -0.65%, PvP 0.00%; Wind Archer Lv7 +20% World Boss -0.31%, Breakthrough 0.00%, Chapter Hunt 0.00%, PvP -1.92%.  Blaze's 3rd stun cast now needs Summoning Time >= 13.667% (Breakthrough total +4.3% between 12 and 14).  Longest formulas: Sensitivity 6903, Companion 6054, Calc 4326, Timeline 1721.
- **Arwen's Glass Shoes + "no DPS effect" relabelling, Sensitivity fixes, artifacts in the engine (2026-11-21, replayed from FP-Mage / Hero / Paladin)**: the shoes are a REAL, live Companion Summoning Time Increase (+20% star 0 .. +40% star 5, linear 20/24/28/32/36/40, all user-confirmed 2026-11-19); effective increase = Inputs value + artifact (`companion_summon_time_inc_expr`) in the Companion host, every Sensitivity block, `b0` (artifact added outside the `MAX(0, ...)`) and so the CompanionsInput table / cube script; the equip row is in `STATUS_REBUILD_KEYS`, `COMPANION_FULL_SEARCH_KEYS` and `SUMMON_TIME_KEYS`.  The seven artifacts without a DPS effect are labelled "no DPS effect (reason)" (`ARTIFACT_NO_DPS_EFFECT`; ArtifactsInput has a 15th column).  **Sensitivity fix 1** (strip rebuild set): engine experiment (reuse vs re-solve of the timeline strip, World Boss / Enhancement Dungeon, 4 configs): every stat is exact under reuse at +1 EXCEPT those already in the set; Skill / Basic Attack / Boss Damage happen to be exact at +1 too but Basic Attack Damage +300 moves the total 0.3-1.6% (the cast schedule is a discrete decision that flips), so `skill_damage`, `basic_attack_damage`, `boss_damage` (Dark Impale has its own Boss Mastery; Candle / Sayram's / Star Rock / Peach Tree / Silver Pendant add to the same buckets), `crit_rate` (Ring of Cycles) and the artifacts `ring_of_cycles`, `book_of_ancient`, `rainbow_snail_shell`, `contract_of_darkness`, `candle`, `sayrams_necklace`, `star_rock`, `peach_tree`, `silver_pendant` were added to `STATUS_REBUILD_KEYS` (14 more strips, Sensitivity +2730 rows); `skill_lvl_1st` stays reused (its only user is Nimble Feet, not a strip input).  **Sensitivity fix 2**: baked-in Final Damage what-ifs (Cursed Doll, Lit Lamp, Clear Spring Water, Soul Pouch, Bottle of Emotion) are multiplicative factors, exact inverses on removal (helper cells Z, 3rd / 4th skill row of each block).  **Two further real bugs found and fixed**: (a) Soul Contract's Chapter-Hunt cooldown decrease was computed on the Artifacts sheet but never multiplied into any effective cooldown (CLAUDE.md item 11: same fix as Hero / Paladin, Calc `Q/R/T/V` formulas of the 14 cooldown rows change, values identical without the artifact); (b) the Skills-sheet fold-in cells of Dark Impale (Final Attack x Advanced Final Attack), Evil Eye Shock (its Enhancement) and Revenge of the Evil Eye (Lv138) read the MAIN Calc rows, so Sensitivity blocks sweeping a skill level never saw them move (CLAUDE.md bug 19; `skill_lvl_3rd` read 0.99998): the blocks now re-point those folds at their own rows.  (c) the verify script and the engine used the flat Defense as the PvP opponent's Defense while the workbook (and the Inputs label "PvP assumes the opponent has the same total Defense as you") use Defense x (1 + Defense %/100): both now use the total (golden regenerated; only the 20 PvP cases with Defense % != 0 changed).  Inputs / ArtifactsInput / PotentialCubes carried over with 0 diffs (only the Companion Summoning Time Increase label changed); every non-Sensitivity sheet is formula-identical except the Companion-sheet refs and the Soul Contract factor; `cyc.py` 0 cyclic components; longest formula 6903 (Sensitivity AG1048, unchanged; Companion 6054, cap 8192).  Verified on the Dark Knight workbook: Glass Shoes equivalence (Total DPS with shoes star s at Inputs x == without shoes at x + 20..40) bit-for-bit on 10/10 pairs (World Boss Blaze Lv10 star 0 = in20, star 5 = in40, star 5 + in5 = in45 across the 3rd-stun flip, + Bottle / Hexagon / Horn Flute; Breakthrough Wind Archer Lv7 x4; Chapter Hunt x2); Sensitivity equip row == toggled-copy delta 1.00000000 (World Boss, BOTH directions, % Gain 107.02358220284663 each; Hexagon + Horn Flute + Bottle base 104.23165704980961; Chapter Hunt 108.28399131268509), Summoning-Time stat and damage blocks with the shoes equipped 1.00000000, Breakthrough equip row == time-weighted expected 1.00000000 (its dollar delta differs by design, CLAUDE.md item 9); sens-vs-main (swept Input set to the block's New Value in a Sensitivity-emptied copy, Ring of Cycles + Bottle + Reindeer equipped) ratio 1.0000000000 for skill_damage, basic_attack_damage, boss_damage, crit_rate, skill_lvl_1st/3rd/4th, final_damage, defense (World Boss) and skill_damage ... skill_lvl_4th / 3rd (Enhancement Dungeon), the six rebuilt artifact toggles (ring, candle, peach tree, silver pendant, Sayram's, Contract of Darkness) == toggled copy 1.00000000; `skill_lvl_2nd` / `skill_lvl_all` differ from the plain main re-run by exactly the documented passive-delta term (Weapon Acceleration / Weapon Mastery levels baked into Inputs: +2.9e-4 World Boss) and equal the main re-run WITH those deltas to 1.000000000000 (World Boss and Enhancement Dungeon); baked-in Final Damage pairs in both directions identical to 1e-16 (gain and % Gain) and == Total(equipped) - Total(unequipped): Cursed Doll 114.0%, Lit Lamp 140.0%, Bottle of Emotion 122.60995600919411% (World Boss), Clear Spring Water 120% (Enhancement Dungeon), Soul Pouch 140% (PvP); 0 error cells (World Boss, Breakthrough; Shoes + Hexagon + Horn Flute + Bottle equipped, Sensitivity stripped) and cube mirror <= 3.4e-16 (World Boss, Breakthrough Blaze Lv10; Wind Archer Lv7 1.9e-10, fractional-window artifact).  The engine side (`engine/classes/dark_knight.py`) models the artifacts: `tests/golden/dark_knight_artifacts_golden.json` / `test_dark_knight_artifacts.py` (68 workbook evaluations, engine == workbook within rel 4.8e-11 worst case, ~1e-16 typically; `test_dark_knight.py` stays bit-exact, 323).

## Dark Knight: Sensitivity in the engine - three workbook gaps found (2026-11-21) and FIXED in the builder (2026-11-23)

The class-agnostic Sensitivity engine (`engine/sensitivity.py` + `engine/sens_specs/dark_knight.py`, engine/README.md "How to add a class to the sensitivity engine") was checked against the Dark Knight workbook's Sensitivity sheet block by block (`tests/golden/test_dark_knight_sensitivity.py`).  Three places where the builder's `build_stat_block` was incomplete were found (and first REPRODUCED by the engine through spec flags); all three were fixed 2026-11-23, Sensitivity formulas only: after ONE full rebuild every other sheet is formula-identical (0 Input / ArtifactsInput / PotentialCubes diffs; 1224 Sensitivity cells differ: the Reindeer / Athena / Shamaness blocks' own formulas + the buff-uptime / strip-host formulas that now read the `bdi_block` helper cell), longest formula 6903 unchanged (cap 8192), `cyc.py` 0 cyclic components.  The spec flags are now `reindeer_dose_in_rows=True`, `athena_as_in_aps=True`, `bdi_toggle_wired=True`.  Before -> after of the equip rows (stat set S, World Boss unless noted; each gain is on the same baseline as its "before"):
- **Reindeer's Spear equip row - FIXED**: the rows' `K` formula read `Inputs!def_pen + delta` instead of `def_pen_total_block`, so the spear's base Def Pen dose never reached the rows' defense reduction (only the boss-branch Reindeer correction and the companion).  `K` now reads `def_pen_total_block` (numerically the plain Input in every other block: the dose exponent is 0).  Gain 2.3215e9 (117.85%) -> 3.2366e9 (126.78%) on 1.5325e10 (World Boss, spear equipped: the removal direction); PvP (spear equipped, removal) 5.380e8 (107.02%) -> 9.174e8 (112.60%) on 8.199e9.  `reindeer_dose_in_rows=True`.
- **Athena Pierce's Old Gloves equip row - FIXED**: the block's Actions Per Second read `attack_speed_with_delta` (no Athena term); it now reads `attack_speed_total_block` (typed Attack Speed + passive delta + the gloves' direct Attack Speed what-if), as FP-Mage / Hero / Paladin / Buccaneer.  Gain 6.118e8 (107.37%) -> 1.2689e9 (115.29%) on 8.300e9 (adding); the removal direction (gloves equipped alongside Book / Bottle / Ring) 4.943e8 (104.48%) -> 1.3108e9 (112.82%) on 1.1533e10.  Unlike Buccaneer / Corsair the toggle does NOT join `STATUS_REBUILD_KEYS`: nothing the timeline strip consumes moves with Attack Speed in this kit (engine experiment in World Boss, Enhancement Dungeon, with and without Bottle / Ring of Cycles: strip reuse and a re-solve give the same row, both == the true delta at 1.0000000000; Breakthrough's 0.3-0.4% is the time-weighted ratio blend vs dollars, the usual bug-9 convention), and the verified rows below were read with the main strip reused.  `athena_as_in_aps=True`.
- **Shamaness Marble equip row - FIXED (was inert)**: `shamaness_marble_delta_block` was defined and never read.  `bdi_block` is now a block-local helper cell (`$U${row_header + 5}`, Paladin's pattern, keeps the uptime formulas short) holding `Inputs BDI + shamaness_marble_delta_block`: every buff uptime and the block's own timeline strip (buff durations) follow the toggle.  Gain 0 (100.00%) -> 1.3712e8 (101.652%) on 8.300e9.  `bdi_toggle_wired=True`.
Verified against toggled copies (World Boss, pure boss, `tests/golden/dark_knight_sens_cases.py` chain `J/WB140/0..3`: state k has the first k of Shamaness Marble / Athena's Gloves / Reindeer's Spear equipped with their baked-in stats typed into the Inputs - Buff Duration +12; Attack Speed +14.4 AND Max Damage +45% of the total Attack Speed; Def Pen combined by diminishing returns with the spear's 8 - the toggle row of artifact k read in state k-1 (adding) and in state k (removing), 4 workbook evaluations): row gain / true Summary Total delta = 1.0000000000000 in BOTH directions for all three, and % Gain identical from both directions (Shamaness 101.612046516584, Athena 130.985725735006, Reindeer 126.463442901973; true deltas +1.884e8 / +3.680e9 / +4.117e9).  `dark_knight_sensitivity_golden.json`: the 4 cases containing those toggles (`S/WB140/art`, `T/WB140/b`, `T/WB140/eq`, `S/PvP140`) regenerated + the 4 new chain cases, the other 20 cases kept (every other stat / toggle value of the regenerated cases is unchanged); `test_dark_knight_sensitivity.py` 24 cases, 1262 values, engine == workbook within rel 1e-9, 0 differences.
Also reproduced (not a gap, the workbook's own convention): in PvP a Defense / Defense % sweep leaves the opponent's Defense at the main sheet's value (the block reads the baseline `Inputs!monster_defense` cell).

## Hero: Sensitivity in the engine (2026-11-22)

`engine/sens_specs/hero.py` + the `_sens` hooks of `engine/classes/hero.py` (`model()`, `e1`, `comp_host`, `summon_time_inc`, `crit_rate_total`; every hook is a no-op without `_sens`: `test_hero.py` 262 bit-exact, `test_hero_artifacts.py` 58) + `tests/golden/test_hero_sensitivity.py` (12 workbook evaluations, 785 values, engine == workbook within rel 1e-9: worst 7e-11 on one `units_per_1pct` = 1/(tiny gain), everything else <= ~2e-12) + `api/tests/test_sensitivity_classes.py`.  The three Dark Knight workbook gaps, checked in Hero's `build_stat_block`:
- **Athena Pierce's Old Gloves equip row - Hero HAD the gap, FIXED in the builder** (Sensitivity only): `s_aps` read `attack_speed_with_delta` (no Athena term); it now reads `attack_speed_total_block` (typed Attack Speed + passive delta + the gloves' direct Attack Speed what-if, as FP-Mage).  74 Sensitivity cells (28 stat + 36 toggle + 10 CDR blocks' `Actions Per Second`) differ, every other cell of every sheet is identical (0 Input / ArtifactsInput / PotentialCubes diffs, main sheets formula-identical, `cyc.py` 0 cyclic components, longest formula 8127 unchanged, cap 8192).  The old row understated the gloves: Lv140 World Boss, stat set S, nothing equipped: +327.8M (107.37%) instead of the real +703.2M (115.81%).  Verified against toggled copies (World Boss, pure boss: Total(gloves equipped, direct Attack Speed ADDED to the typed value and the dependent Max Damage typed in) - Total(unequipped)): the row == the toggled-copy delta 1.0000000000000 from BOTH directions (% Gain 115.81334532004706 each).  `athena_as_in_aps=True`.
- **Reindeer's Spear equip row - Hero is correct**: the rows' `K` formula reads `def_pen_total_block`, so the dose reaches the rows' defense reduction, the boss-branch correction and the companion.  Toggled-copy delta ratio 1.000000000000 both directions (% Gain 129.18329808991786 each, Def Pen typed through the diminishing-returns combine, Attack% live).  `reindeer_dose_in_rows=True`.
- **Shamaness Marble equip row - Hero is correct**: `bdi_block = Inputs BDI + shamaness_marble_delta_block` is wired (and moves Puncture's window, which the engine's `bdi_extra` now reaches too).  Toggled-copy delta ratio 1.000000000000 both directions (% Gain 102.51480320690331 each).  `bdi_toggle_wired=True`.
Hero-specific semantics reproduced (spec docstring): (1) Hero retypes `Inputs!final_damage` INSIDE the additive Final Damage bucket `(1 + (typed + passive + Enrage / Combo Synergy / Lv98 +5)/100)`, so the baked-in Final Damage artifacts are a factor on the TYPED value (`baked_fd_form="typed"`; the other classes' form is a factor on the artifact bucket), and the Final Damage +1% sweep bumps the full bucket (`MULT_KIND_EXTRA_REF`, new `SensSpec.mult_extra`; the table's Current / New include the live share, the ratio is exactly 1.01); (2) Ring of Cycles' crit-rate threshold in a block has no Chance Attack (`skill_lvl_3rd`) Crit Rate delta (the pre-existing approximation of "Hero Sensitivity fixes" above): the engine keeps `crit_rate_input` for the Ring and `crit_rate` for the rows; (3) Hero has no Defense stat (no Iron Wall): the equipment table's "Defense (flat)" prices 0; (4) the engine's `crit_rate_bonus` stays 0 (no live crit source in the kit) and the artifact bucket is `art_crit_rate` (`crit_rate_total` = Inputs + artifacts), so Book of Ancient's removal what-if does not double-count Ring / Rainbow.  Coverage: all 28 stats (the strip-rebuild stats in World Boss AND Enhancement Dungeon, Lv118 Chapter Hunt for the passive unlock gating), 22 of the toggles in both directions where baked-in (Book of Ancient, Athena, Bottle, Ring, Hexagon, Horn Flute, Glass Shoes, Cursed Doll, Lit Lamp, Clear Spring Water, Star Rock, Reindeer, Shamaness, Soul Contract ...), CDR milestones 0.5 / 1 / 2 / 3.5 / 5, both companion tables (Breakthrough, 16 companions at five levels + the Summoning-Time table), the Summoning Time 12.9 candidate flip.  Peak RAM 7.4 GB (8-block slimmed copy with three toggle strips), 2.5-6 min per evaluation, 15 min for the table case, 64 min for all 12.

## Ice-Lightning-Mage: Sensitivity in the engine (2026-11-22; one workbook gap fixed)

`engine/sens_specs/ice_lightning_mage.py` + the `_sens` hooks of `engine/classes/ice_lightning_mage.py` (no-ops without `_sens`: `test_ice_lightning_mage.py` 265 cases bit-exact, `test_ice_lightning_mage_artifacts.py` 58 green) were checked against the ILM workbook's Sensitivity sheet (`tests/golden/test_ice_lightning_mage_sensitivity.py`, 12 slimmed-copy evaluations, engine == workbook within rel 1e-9 on every value).  The three gaps the Dark Knight port found were checked in ILM's `build_stat_block`:
- **Shamaness Marble equip row - FIXED in the builder (was inert).**  `shamaness_marble_delta_block` was defined and never used (`bdi_block` read the plain Input), so the row was 0 + potential.  `bdi_block` now adds it (`({ib("buff_duration_increase_pct")}+{shamaness_marble_delta_block})`, FP-Mage / Hero / Bishop form): buff uptimes, the Weaken window and the block's own timeline strip follow the toggle.  Sensitivity-only: after the single full rebuild every other sheet is formula-for-formula identical, 0 Input diffs (the 1853 changed cells are all in `Sensitivity`: every block's buff-uptime / Weaken / strip-host formulas carry the `+0` delta term; the Shamaness block itself moved).  Longest formula 7528 (cap 8192), `cyc.py` 0 cyclic components.  Verified against the toggled copy (Total with `Inputs!buff_duration_increase_pct` +12, star 5, vs the block): see the verification line below.  `bdi_toggle_wired=True`.
- **Reindeer's Spear equip row - already correct.**  The K formula reads `def_pen_total_block` (the dose reaches the rows' defense reduction, the boss-branch correction and the companion).  `reindeer_dose_in_rows=True`.
- **Athena's Gloves equip row - already correct.**  `s_aps` reads `attack_speed_total_block` (typed Attack Speed + the gloves' direct Attack Speed).  `athena_as_in_aps=True`.
ILM-specific block terms reproduced by the engine (documented in the spec): the main stat is INT (LUK is typed, not a sweep stat: `mainstat_attack_delta` has no sub-stat term); the passive deltas of the skill-level stats are High Wisdom + Magic Critical (Crit Rate) -> `crit_rate_delta` (+ Magic Critical's Crit Damage, Spell Mastery's Min Damage), all read from the Skills-sheet F cells WITHOUT an unlock gate (like FP-Mage's); the crit-rate delta also feeds Ring of Cycles' threshold (the builder's "Magic Critical `crit_rate_delta` fix"); Magic Acceleration's Attack Speed delta is added to MP Eater's flat Attack Speed inside `IF(MP Eater unlocked, F + delta, 0)` (Lv49) and so joins the BONUS side of the Attack Speed diminishing returns, not the typed side (hook `as_bonus_extra`, new); the baked-in Final Damage artifacts are the FP-Mage / Bishop plain factor on the live bucket (`fd_baked_factor`, helper cells `Z{row_header+3}` / `Z{row_header+4}`).  Not part of the golden by design: nothing.

## Buccaneer: Sensitivity in the engine (2026-11-22; two workbook gaps fixed, one more found)

`engine/sens_specs/buccaneer.py` + the `_sens` hooks and `model()` of `engine/classes/buccaneer.py` (no-ops without `_sens`: `test_buccaneer.py` 325 bit-exact, `test_buccaneer_artifacts.py` 66 green; `crit_rate_bonus` is now 0 and the artifact bucket is `art_crit_rate`, `crit_rate_total` exposed; new `final_damage_all` = Summary R_FD_ALL; new hook `attack_mult_delta` for Dark Clarity) + `tests/golden/test_buccaneer_sensitivity.py` (12 slimmed-copy evaluations, 823 values, engine == workbook within rel 1e-9, worst 1.1e-10 on one `units_per_1pct`) + `api/tests/test_sensitivity_classes.py`.  The three gaps the Dark Knight port found, checked in Buccaneer's `build_stat_block` (builder changes are Sensitivity-only: after ONE full rebuild all other sheets are formula-identical, 0 Input diffs, longest formula 6938 unchanged, `cyc.py` 0 cyclic components):
- **Shamaness Marble equip row - Buccaneer HAD the gap, FIXED**: `shamaness_marble_delta_block` was defined and never read (row inert).  `bdi_block` now adds it (moved above `bdi_block`): buff uptimes, the Assault Mark window and the strip's buff durations follow the toggle.  `bdi_toggle_wired=True`.
- **Athena's Gloves equip row - Buccaneer HAD the gap, FIXED (two parts)**: (1) `s_aps` read `attack_speed_with_delta` (no Athena term); it, the Speed Infusion APS (`_aps_during_si_block`) and the companion snapshot now read `attack_speed_total_block`.  (2) Found by the chain golden: that direct Attack Speed moves the timeline strip (Speed Infusion's Final Damage in `fd_scale`, the Assault Mode uptime), so `athena_gloves_equipped` had to join `STATUS_REBUILD_KEYS` (own strip); with the main strip reused the adding row read +0.6% and the removing row +0.5% above the true delta.  `athena_as_in_aps=True`.
- **Reindeer's Spear equip row - already correct** (K reads `def_pen_total_block`).  `reindeer_dose_in_rows=True`.
Verified on the final workbook against toggled copies (chain `I/WB140/*`, World Boss, baked stats typed into the Inputs, adding row in the state without the artifact, removing row in the state with it, true delta = Summary Total difference): Shamaness Marble (+12 Buff Duration) add/true 1.000000000000, rem/true 1.000000000000 (% Gain 102.6024043560); Athena's Gloves (+14.4 Attack Speed, Max Damage +45% of the total) 1.000000000000 / 1.000000000000 (129.490038482); Reindeer's Spear 1.000000000000 / 1.000000000000 (132.880220428); Bottle of Emotion and Cursed Doll (typed Final Damage): identical from both directions and == the true delta (golden test `test_baked_chain_golden`).
Buccaneer-specific block semantics reproduced (spec docstring): the typed-Final-Damage form (`baked_fd_form="typed"`; the Final Damage +1% step bumps the whole bucket incl. Serpent Scale / Crossbones / Time Leap / Speed Infusion, `mult_extra` -> `final_damage_all`; exactly 1.01 without strip and companion, a little under it in World Boss because the strip's Crossbones / Time Leap are time-varying), the passive deltas (Shadow Heart -> Crit Rate incl. Ring of Cycles' threshold, Quick Motion / Agile Knuckles -> Attack Speed, Dark Clarity -> Attack% bucket, Knuckle Mastery, Physical Training, Groggy Mastery -> Final Damage; unlock-gated), `skill_lvl_1st` / `_2nd` re-solve the strip.  Coverage: all 28 stats (strip-rebuild stats in World Boss and Enhancement Dungeon, Lv74 Chapter Hunt for the unlock gating), 27 toggles (5 baked-in ones in both directions), CDR 0.5 / 1 / 2 / 3.5 / 5, the companion table + Summoning-Time table (Breakthrough), the Summoning Time 12.9 candidate flip, Soul Contract in Chapter Hunt.  Run time 2-14 min per evaluation (peak 7.5 GB), 51 min in total.

## Buccaneer: Companions + Status Effect Damage / KO timeline (2026-11-15 port from FP-Mage / Hero / Paladin / Dark Knight)

Same feature set and rules as the FP-Mage / Hero / Paladin / Dark Knight sections above: Inputs `STATUS_EFFECT_DAMAGE %` (row 22, self-detecting row-shift migration), `Companion` (row 51; rows 47-50 are the artifact slots) + live `Companion Summoning Time Increase %`, sheets
`Timeline` / `CompanionKits` / `Companion` / `CompanionsInput`, Sensitivity rows for both stats, the Companion Comparison and summoning-time tables (weighted-ratio form), the Horn Flute rewire (`Companion!horn_uptime`) and the exported host values for `potential_cubes_ev.py`
(checked: the Python mirror rebuilt from the exported cells reproduces the sheet's companion DPS and its b0+20 grid column to 1e-16, Breakthrough, Hexagon + Charm + Horn Flute + Bottle of Emotion equipped).  With Companion = None, Status Effect Damage = 0 and a content where the engine stays off
(Chapter Hunt, PvP, EXP / Equipment Dungeon, Hero Dungeon) every total is bit-identical to the pre-port workbook (test inputs: Chapter Hunt 3018449163.2983, PvP 347368142.9735, EXP / Equipment Dungeon 3763437931.2831, Hero Dungeon 2238197793.1709).  Buccaneer-specific wiring:
- **Engine buffs** (`STATUS_BUFFS`): Crossbones (28 s / 12 s) and Time Leap (65 s / 40 s) as **Final Damage buffs** (`ramp` kind with a flat profile).  Buccaneer's FD bucket is ADDITIVE with the base FINAL_DAMAGE % and the other FD sources, so g(t) enters the engine's multiplicative term as
  `g(t) x 100/(100 + F0 + R_FD_REST)` (`fd_scale`, as Paladin's Guardian); with the engine on `Summary!R_AVGBUFF` = the strip's mean buff bucket and `R_FD_BONUS` = `R_FD_REST` (Serpent Scale + Speed Infusion); `R_FD_ALL` (all four) is what the Final Damage "+1% mult" Sensitivity test scales.
  There is no player-cast Attack% buff: Roll of the Dice's random dice component (7 s roll, 5 s) is part of the engine's constant Attack% term `A0`.  NOT player-timed, they stay averaged (also in the companion's snapshot where they are not a cast): the **Serpent Scale / Assault Mode resource loop**
  (the smoothed steady-state cycle: interval T, uptime u, Serpent Scale's +25% / +4% Final Damage, the Sea Serpent Burst <-> Serpent Assault split), Speed Infusion (Attack Speed buff; its FD = 20 x (APS during the buff - 1) is in `R_FD_REST`), Nimble Feet and the Assault Mark weaken (Octopunch-cooldown based).
- **Engine groups**: Corkscrew Blow (burst, fixed player-stun schedule), Octopunch (burst) + Sea Serpent's Rage (burst, fires on every Octopunch, no action slot) + Raging Serpent Assault (`dot`, 5 s window of 1 s ticks; its Assault-Mode gating `u` sits in its per-cast weight, its hits come from the
  engine's effective cast count `STATUS_FS_KEYS`), Nautilus Strike (burst).  Uniform rows: Hook Bomber (basic attack), Sea Serpent Burst, Serpent Assault, Nautilus Strike - Final Attack (basic-attack / any-attack procs).  Boss / normal DPS columns are `T` / `V`, timing factors `W`/`X`, per-cast boss damage `Y`,
  **`Z` = the pre-engine (averaged-model) cast count**.
- **Circularity avoidance**: Assault Mode's T / u (and through them Serpent Scale's FD, Raging Serpent Assault's per-cast weight) feed the engine's inputs, and T depends on the Hook Bomber rate, which depends on the engine's cast counts - a real loop.  So T / u read `Summary!R_BAPS_AVG` (Hook Bomber rate from `R_CASTRATE_AVG`,
  the SUMPRODUCT over column Z); identical to `R_BAPS` whenever the engine is off, slightly different with it on (the slots the optimal player's different cast counts free or use).  The Nautilus FA trigger rate and the Hook Bomber DPS use the engine-aware rate.  `cyc.py`: 0 cyclic components.
- **Player stun**: Corkscrew Blow (1.8 s, cooldown 21 s, no Reuse mastery; unlock Lv63) as a fixed on-cooldown stun group (`STATUS_PLAYER_STUN`, host `pst` in the main / block / exported hosts, `pl_stun` in the engine host).  The engine is ON in every fixed-length single-target content from Lv63 (World Boss, Enhancement Dungeon, Chapter Boss, Weapon Dungeon),
  Breakthrough's boss phase is lengthened by the stuns (also with Companion = None: 2348879999 -> 2359766289 on the test inputs), Hero Dungeon is timed (no extension, unchanged).  Fixed means Corkscrew Blow no longer waits for a KO window; Octopunch / Nautilus Strike / Crossbones / Time Leap are optimised (e.g. World Boss Lv200: Octopunch 7 casts, Nautilus 3, Crossbones 3, Time Leap 2).
- **Companion host**: `unit` = Hook Bomber's `N/F`; `avgbuff` = `R_AVGBUFF` x `(1 + (FD + R_FD_BONUS)/100)`; the snapshot has the CAST buffs (Crossbones, Time Leap, Speed Infusion's FD) fully up and the dice roll / Serpent Scale loop at their averages (`k1`, `fdpart` exported for the cube script); like Paladin / Dark Knight the 'enemy damage taken'
  bonuses (artifacts, Assault Mark) sit inside the boss / normal monster damage % buckets (`R_MONSTER_DMG_BONUS`), so `taken_bucket` is the boss/normal blend (0 in PvP) and `agg_damage_avg` is just the Hexagon part of the Damage bucket.  Hook Bomber's Boss Monster Damage mastery is a skill mastery, not part of `boss_pct`.
- **Sensitivity strips**: `STATUS_REBUILD_KEYS` = FP-Mage's plus the Attack%-artifact toggles, `skill_lvl_3rd/4th/all`, `final_damage` (the FD scale) and `attack_speed` (the Assault Mode uptime).  Block twin cells (BLOCK_HEIGHT = LAST_ROW + 25): `R_CASTRATE_AVG` / `R_BAPS_AVG` / `R_FD_REST` / `R_FD_ALL` / monster-damage-taken bonus / averaged Attack% sum.
  **Shared-recipe gap found and fixed locally**: the strip's stun vector uses candidate-0 timing (`s_0`, `W_0`), but a block's own companion chain pins its candidate 0 to the summon time the MAIN sheet chose; when that is another candidate (here the earliest summon, s = 7 s, in the default World Boss setup) the block's strip placed the stun windows differently from the main strip
  (status_effect_damage / CDR blocks read +0.5% / +0.3% high).  Rebuilding blocks now read the main sheet's `s_0` / `W_0` for the stun vector (only the Summoning-Time block keeps its own).  Hexagon Necklace and Horn Flute equip blocks additionally run the full 3-candidate summon search (the toggle changes what the candidates are worth); every other block still reuses the main sheet's
  chosen summon time (a flip of the chosen candidate between the base and the swept value is the remaining second-order approximation).
- **Not modelled**: the player's other crowd control; Time Leap's cooldown-halving of the active skills and its start-of-battle delay; Crossbones' Defense Penetration; the Serpent Scale loop and Speed Infusion as time-resolved effects (a smoothed average, as before); the Assault Mark / Weaken as timed effects.
- **Verification** (2026-11-15, artifacts cleared, Sensitivity stripped, non-trivial Inputs: crit / boss / normal / skill / basic damage / def pen / STR / DEX / min-max / attack speed / flat attack): `verify_buccaneer_workbook.py` == workbook (`data/porting/helpers/sv.py` logic) for Chapter Boss, World Boss (None and Blaze Wizard Lv10, S=30; Lv 50 / 70 / 110 / 118 / 125 / 140 / 200),
  Enhancement Dungeon (Blaze Wizard; Wind Archer with Buff Duration +40% and CDR 3 s at Lv121), Weapon Dungeon, Breakthrough (None = the player-stun extension, Blaze Wizard, Bow Master; Lv50 None), Hero Dungeon, Chapter Hunt, EXP / Equipment Dungeon, PvP with Blaze Wizard (stunning) and Bow Master (non-stunning), Chapter Boss Lv62 (no stun yet).
  `cyc.py` 0 cyclic components; longest formulas Sensitivity 7225, Timeline 7606, Companion 6376; zero error cells (World Boss and Breakthrough, NOSENS, Hexagon + Charm + Horn Flute + Bottle of Emotion equipped, Blaze Wizard Lv10, S=30).  Sensitivity-vs-main (Blaze Wizard Lv10, S=30, Lv200, Bottle of Emotion + Reindeer's Spear equipped, run on a Sensitivity-SLIMMED COMP_LIGHT copy):
  World Boss and Breakthrough `damage`, `status_effect_damage`, `skill_cooldown_decrease`, `companion_summon_time_increase_pct` ratio 1.00000000; World Boss also `final_damage` (new value = table value minus the FD-buff extras), `buff_duration_increase_pct`, `skill_lvl_4th`, `attack_speed`, `attack_pct` 1.00000000.
  Hexagon Necklace / Charm of the Undead / Horn Flute equip rows (block total AND the artifact-table DPS gain) == the toggled copy's total delta (World Boss, ratio 1.00000000; gains +137.1M / +15.7M / +28.6M on 277.7M).
- **Rebuilt for the companion cast timing rule (2026-11-18)** (see "Companions" -> Cast timing): Inputs / ArtifactsInput / PotentialCubes identical, only Companion-chain references and the CompanionKits columns changed (Corkscrew Blow keeps its old timing: player stun, cooldown from the startup time); total shifts at the verify-script base Inputs (Lv200, status 30, Blaze Wizard Lv10 / Wind Archer Lv7 +20): World Boss -0.20% / +0.15%, Breakthrough -3.05% / 0.00%, Chapter Hunt -0.23% / 0.00%, PvP 0.00% / -1.94%.  Back-port found by the Sensitivity-vs-main check (World Boss, +12.9% summon time: CDR block ratio 0.99982631): the Skill Cooldown Decrease block (and the CDR milestone blocks) now run the full 3-candidate summon search (`COMPANION_FULL_SEARCH_KEYS`, guide "Gap found by the Buccaneer port" item 4), as in the other ports.  Longest formulas Sensitivity 6955, Companion 6054, Timeline 1709; verify script == workbook on 12 scenarios (Blaze at +0/12/14%), Sensitivity-vs-main ratio 1.00000000 (World Boss / Breakthrough, incl. the +12.9% flip), equip rows == toggled-copy delta, 0 error cells, cube mirror <= 4.5e-16.
- **Arwen's Glass Shoes + "no DPS effect" relabelling + Sensitivity fixes (2026-11-21, replayed from FP-Mage / Bishop; engine port the same day)**: the shoes are a REAL, live Companion Summoning Time Increase (+20% star 0 .. +40% star 5, linear 20/24/28/32/36/40, all user-confirmed 2026-11-19); effective increase = Inputs value + artifact (`companion_summon_time_inc_expr`) in the Companion host, every Sensitivity block, `b0` (artifact outside the `MAX(0, ...)`) and so the CompanionsInput table / cube script; the equip row is in `STATUS_REBUILD_KEYS`, `COMPANION_FULL_SEARCH_KEYS` and `SUMMON_TIME_KEYS`.  The seven artifacts without a DPS effect are labelled "no DPS effect (reason)" (ArtifactsInput gets a 15th column).  Rebuilt once: Inputs / ArtifactsInput / PotentialCubes carried over with 0 diffs (only the Summoning Time label), Calc / Summary / Timeline formula-identical (Companion differs only in the 17 `inc` refs + `b0`), `cyc.py` 0 cyclic components, longest formula 6938 (Sensitivity T1755), Companion 6054 (cap 8192).  Soul Contract: checked at every cooldown call site - Buccaneer has a single one (`Calc!Q`, main and Sensitivity blocks; Assault Mode's T, the Assault Mark window, buff uptimes, the Corkscrew stun and the strip all read `1/Q`), no omission (the Chapter Hunt golden cases agree with the engine).
- **Buccaneer Sensitivity fixes (2026-11-21)**: (1) strip rebuild set.  Added `skill_damage`, `basic_attack_damage`, `boss_damage`, `crit_rate`, the toggles `ring_of_cycles`, `book_of_ancient`, `rainbow_snail_shell`, `candle`, `sayrams_necklace`, `star_rock`, `skill_lvl_1st` / `_2nd` and the four baked-in Final Damage toggles.  Engine experiment (`stl.solve` captured base vs swept, 2376 big-delta runs, Lv 63-200): Skill / Basic Attack / Boss Damage flip the schedule or the cast values (Hook Bomber has its own Boss Mastery, the three cast groups weigh against it); every uniform stat does not.  The engine cannot see two feeds, found by the sens-vs-main check: the skill-level stats' PASSIVE deltas (Quick Motion / Agile Knuckles' Attack Speed -> Speed Infusion FD -> `fd_scale`, Dark Clarity's Attack% -> `A0`, Groggy Mastery's Final Damage; hence `skill_lvl_1st` / `_2nd`, which were reading +0.019% / +0.015% off) and the baked-in Final Damage what-ifs (below).  (2) baked-in Final Damage what-ifs (Cursed Doll, Lit Lamp, Clear Spring Water, Soul Pouch, Bottle of Emotion's Attack-Speed-dependent value) are now a RETYPED `Inputs!final_damage` in the block (helper cell U, 4th skill row; `ib("final_damage")` reads it everywhere incl. the strip's `fd_scale`): adding = `((1+F/100)(1+x/100)-1)*100`, removing = `((1+F/100)/(1+x/100)-1)*100`, exact inverses.  Deliberately NOT a plain factor on the whole product (FP-Mage's form): here the Input sits in an ADDITIVE bucket with Serpent Scale / Crossbones / Time Leap / Speed Infusion, so a toggled copy of the workbook (user retypes the new total) gives a smaller ratio than 1 + x/100 and the strip's `fd_scale` moves too.  Verified by matched pairs (state 0 / state 1 with the typed value): block read in state 0 == Total(state 1), read in state 1 == Total(state 0), gain and % Gain identical from both directions (rel diff <= 2.3e-16): Cursed Doll 108.33%, Lit Lamp 123.81%, Bottle of Emotion 133.29% (World Boss), Clear Spring Water 111.04% (Enhancement Dungeon), Soul Pouch 122.40% (PvP).  Sens-vs-main (swept Input set to the block's New Value in a Sensitivity-emptied copy, Lv200, Blaze Wizard Lv10, Bottle + Reindeer's Spear / Ring of Cycles + Bottle): `skill_damage`, `basic_attack_damage`, `boss_damage`, `crit_rate`, `final_damage` (Input = New Value - R_FD_ALL, the 'mult' kind's extra) ratio 1.00000000 in World Boss AND Enhancement Dungeon; `skill_lvl_1st` / `_2nd` / `_3rd` / `_all` (main re-run carrying the block's documented passive deltas) 1.000000000000; Ring of Cycles / Candle / Sayram's equip rows == toggled copy (gain and table gain 1.00000000).  Glass Shoes equip row == toggled copy 1.00000000 (World Boss, % Gain 106.62558479646658 from BOTH directions; with Hexagon + Horn Flute + Bottle 105.1535; Chapter Hunt 107.0959), Summoning-Time stat / damage blocks with the shoes equipped 1.00000000, Breakthrough equip row == time-weighted expected 1.00000000 (its dollar delta differs by design, CLAUDE.md item 9).  Cost: 17 more strips (Sensitivity 8304 -> 11075 rows).  `engine/sensitivity.py` is not updated (Buccaneer has no engine sensitivity yet).
- **Engine (2026-11-21)**: `engine/classes/buccaneer.py` models the artifacts (`inputs["artifacts"]`, `artifacts` result block, `schema()["artifacts"]`); `tests/golden/buccaneer_artifacts_golden.json` / `test_buccaneer_artifacts.py`: 66 workbook evaluations (every artifact at star 5 in World Boss with Blaze Wizard Lv10, other fight shapes, stars, crit-rate branches, Reindeer def pen 50 / 80 / 99, Corkscrew Blow Lv62 / 63 shapes, Hook Bomber Lv99 / 100, Crossbones Lv115, Time Leap Lv125, Octopunch haste Lv134, Soul Contract, the Glass Shoes equivalence pairs): engine == workbook within rel 6.3e-16 worst case; 6 equip-toggle deltas and 10 equivalence pairs identical (bit-for-bit in the workbook, incl. the Blaze 3rd-stun flip).  Cube mirror (World Boss, Breakthrough Blaze Lv10, Breakthrough Wind Archer Lv7, shoes + Hexagon + Horn Flute + Bottle equipped, 0 error cells): 3.3e-16 / 0 / 1.1e-16 on the sheet's column, b0+20 grid column 0 / 4.9e-10 (fractional summoning window artifact) / 1.1e-16.

## Corsair: Companions + Status Effect Damage / KO timeline (2026-11-16 port from FP-Mage / Hero / Paladin / Dark Knight / Buccaneer)

Same feature set and rules as the FP-Mage / Hero / Paladin / Dark Knight / Buccaneer sections above: Inputs `STATUS_EFFECT_DAMAGE %` (row 22, self-detecting row-shift migration), `Companion` (row 51; rows 47-50 are the artifact slots) + live `Companion Summoning Time Increase %`, sheets
`Timeline` / `CompanionKits` / `Companion` / `CompanionsInput`, Sensitivity rows for both stats, the Companion Comparison and summoning-time tables (weighted-ratio form), the Horn Flute rewire (`Companion!horn_uptime`) and the exported host values for `potential_cubes_ev.py`
(checked: the Python mirror rebuilt from the exported cells reproduces the sheet's companion DPS and its b0+20 grid column exactly, World Boss and Breakthrough, Hexagon + Charm + Horn Flute + Bottle of Emotion equipped).  With Companion = None, Status Effect Damage = 0 and a content where the engine stays off
(Chapter Hunt, PvP, EXP / Equipment Dungeon, Hero Dungeon) every total is bit-identical to the pre-port workbook (test inputs: Chapter Hunt 6811825959.4529, PvP 980830935.8060, EXP / Equipment Dungeon 6917019634.1942, Hero Dungeon 4682135692.3810).  Corsair-specific wiring:
- **Engine buff** (`STATUS_BUFFS`): only **Jolly Roger** (+15% Final Damage, 42 s cooldown / 18 s) as a Final Damage buff (`ramp` kind with a flat profile).  Corsair's FD bucket is ADDITIVE with the base FINAL_DAMAGE % and the other FD source, so g(t) enters the engine's multiplicative term as
  `g(t) x 100/(100 + F0 + R_FD_REST)` (`fd_scale`, as Paladin's Guardian / Buccaneer's Crossbones); with the engine on `Summary!R_AVGBUFF` = the strip's mean buff bucket and `R_FD_BONUS` = `R_FD_REST` (new Summary row 31: Ahoy Mateys' +20% Final Damage proc only);
  `R_FD_ALL` (row 32: Jolly Roger at the current cast count + the Ahoy proc) is what the Final Damage "+1% mult" Sensitivity test scales.  There is no player-cast Attack% buff: Roll of the Dice's dice component (7 s roll, 5 s) is part of the engine's constant Attack% term `A0`.
  NOT player-timed, they stay averaged (also in the companion's snapshot where they are not a cast): the **Ahoy Mateys +20% FD proc** (tied to the Scurvy Summons cast but kept at its steady-state uptime of 1/Q, so it does not follow the engine's Scurvy casts), Nimble Feet (Attack Speed), Swift Fire's Weaken and the artifact damage-taken bonuses
  (`R_MONSTER_DMG_BONUS`), and the Maple Hero / Ahoy Mateys constant Final Damage terms of the helper-fed rows.
- **Engine groups** (cast row -> rows): Swift Fire, Blackboot Bill, Brain Scrambler, Nautilus Strike, Rapid Fire (one burst row each), Scurvy Summons -> Dual Pistol Crew (`dot`, its 20 s window, longer with All Aboard - Persistence) + All Aboard (the Sharpshooter Crew: no action slot, cooldown = Scurvy's live cooldown, gated on its own unlock),
  Siege Bomber (`dot`, 22 s / 30 s window), Broadside -> initial burst + the sustained Battleship / bombardment ticks (`dot`, 20 s window, 30 s with Lv138 Setup: overlapping windows add, as in the averaged model).  `STATUS_FS_KEYS` (hits from the engine's effective cast count) = Scurvy Summons, All Aboard, Siege Bomber, Broadside (sustained).
  Uniform rows: Eight-Legs Easton (basic attack) and the chance procs Nautilus Strike - Final Attack and Majestic Presence (their trigger rates already read the engine-aware cast counts / `Summary!R_BAPS`).  Boss / normal DPS columns are `T` / `V`, timing factors `W`/`X`, per-cast boss damage `Y` (Easton's includes the Quickdraw x(1+1/3)),
  **`Z` = the pre-engine (averaged-model) cast count**.
- **Quickdraw / no averaged-model twins needed**: Quickdraw's cooldown divisor (`R_QD_FACTOR`, closed-form fixed point), Swift Fire's Weaken and the Ahoy proc only read steady-state `1/cd`, never cast counts, so (unlike Paladin's Vessel of Light or Buccaneer's Assault Mode) no `R_CASTRATE_AVG` / `R_BAPS_AVG` twin was needed and `cyc.py` reports 0 cyclic components.
  The divisor therefore stays the averaged model's value (it assumes every other skill is cast at its full rate) and the engine only reads the resulting cooldowns; with Quickdraw Brain Scrambler / Rapid Fire cooldowns are fractional (e.g. 14.5 s) and the engine spaces casts in WHOLE one-second bins (`ROUNDUP`), a small systematic loss against the averaged model.
- **Player stun**: Blackboot Bill (2 s stun, cooldown 23 s, no Reuse mastery, unlock Lv66) as a fixed on-cooldown stun group (`STATUS_PLAYER_STUN`, host `pst` in the main / block / exported hosts, `pl_stun` in the engine host).  The engine is ON in every fixed-length single-target content from Lv66 (World Boss, Enhancement Dungeon, Chapter Boss, Weapon Dungeon),
  Breakthrough's boss phase is lengthened by the stuns (also with Companion = None), Hero Dungeon is timed (no extension, unchanged).  Fixed means Blackboot Bill no longer waits for a KO window.
- **Engine-on contents change by design** (test inputs, Companion None, S = 0, vs the pre-port workbook): World Boss +39% and Enhancement Dungeon +35% (KO phases: the optimal player), Breakthrough +0.3% (stun extension), Chapter Boss -0.8%, Weapon Dungeon -4.4%.  The two small drops are not a bug: (1) the averaged model truncates only the LAST cast of a DoT / summon at the fight end, so a
  non-last cast whose window exceeds the remaining fight (Broadside's 30 s Setup window against a 20 s cooldown, Siege Bomber's 30 s window) was counted in full - the engine truncates every window; (2) the whole-bin spacing of Quickdraw's fractional cooldowns (above).  In single-target content the optimal player also never casts Swift Fire when the 1-second bins show it is worth less than the
  Easton actions it replaces (0 casts, 0 DPS on that row; the averaged contents still cast it), the same as Hero's Beam Blade.  Shared-engine approximation (all classes): different skills may be cast in the SAME one-second bin (e.g. every cooldown skill at t = 0 in a short fight), beyond the actions per second the character really has.
- **Companion host**: `unit` = Easton's `N/F` (the Quickdraw doubling is part of the player's Easton DPS only, not of the companion); `avgbuff` = `R_AVGBUFF` x `(1 + (FD + R_FD_BONUS)/100)`; the snapshot has the CAST buff (Jolly Roger) fully up and the dice roll / Ahoy proc at their averages (`k1`, `fdpart` exported for the cube script);
  like Paladin / Dark Knight / Buccaneer the 'enemy damage taken' bonuses (artifacts, Swift Fire's Weaken) sit inside the boss / normal monster damage % buckets (`R_MONSTER_DMG_BONUS`), so `taken_bucket` is the boss/normal blend (0 in PvP) and `agg_damage_avg` is just the Hexagon part of the Damage bucket.  Easton's Boss Monster Damage mastery is a skill mastery, not part of `boss_pct`.
- **Sensitivity strips**: `STATUS_REBUILD_KEYS` = FP-Mage's plus the Attack%-artifact toggles, `skill_lvl_3rd/4th/all` (Roll of the Dice / Jolly Roger F), `final_damage` (the FD scale) and `attack_speed` (Quickdraw's divisor moves Brain Scrambler / Rapid Fire's cooldowns).  Block twin cells (BLOCK_HEIGHT = LAST_ROW + 25): `R_FD_REST` / `R_FD_ALL` / monster-damage-taken bonus /
  averaged Attack% sum.  Rebuilding blocks read the main sheet's `s_0` / `W_0` for the stun vector (the Buccaneer recipe fix).  **Further gap found here**: Skill Cooldown Decrease changes the player's whole cast schedule, so on Corsair the chosen companion summon candidate can flip between the base and the swept value (World Boss default: base = candidate 1, CDR +1 s = the earliest summon, 7 s):
  the block that pinned the summon time read -2.7e-4 against a full re-evaluation (player rows identical, only the companion differs).  The CDR block and the 10 CDR milestone blocks now run the full 3-candidate search like the Hexagon Necklace / Horn Flute / Summoning-Time blocks (ratio 1.00000000 afterwards).
- **Not modelled**: the player's other crowd control; the Ahoy Mateys proc, Nimble Feet, Swift Fire's Weaken and Quickdraw's cooldown feedback as time-resolved effects; the Scurvy Summons -> Ahoy proc alignment; Siege Bomber's / Broadside's first-setup -15 s cooldown and the 3 s Battleship arrival (a same-cast hit, as before).
- **Verification** (2026-11-16, artifacts cleared, Sensitivity stripped, non-trivial Inputs: crit / boss / normal / skill / basic damage / def pen / STR / DEX / min-max / attack speed / flat attack / Final Damage; COMP_LIGHT builds for the matrix, a full build for the first run and the full-workbook checks): `verify_corsair_workbook.py` == workbook (`data/porting/helpers/sv.py` logic) for
  Chapter Boss / World Boss / Enhancement Dungeon / Breakthrough / Hero Dungeon / Chapter Hunt / EXP / Equipment / Weapon Dungeon / PvP with Blaze Wizard Lv10 (S=30), Bow Master Lv10 and no companion (None = the Blackboot Bill extension in Breakthrough, uniform factor in Chapter Hunt); World Boss at Lv 30 / 50 / 66 / 70 / 100 / 110 / 118 / 122 / 125 / 138 / 140
  (Blaze Wizard), Breakthrough Lv 50 / 65 with no companion, Wind Archer Lv7 with Buff Duration +40% and CDR 3 s (World Boss Lv121, Enhancement Dungeon Lv200), Chapter Boss with BDI +60% and CDR 5, Weapon Dungeon / Chapter Hunt with CDR 2: 49 runs, all OK.
  `cyc.py` 0 cyclic components; longest formulas Sensitivity 7225, Timeline 7606, Companion 6376, Calc 1316; zero error cells on the FULL workbook (World Boss and Breakthrough, Sensitivity stripped, Hexagon + Charm + Horn Flute + Bottle of Emotion equipped, Blaze Wizard Lv10, S=30; World Boss also with the Sensitivity sheet).
  Sensitivity-vs-main (Blaze Wizard Lv10, S=30, Lv200, Bottle of Emotion + Reindeer's Spear equipped, run on a Sensitivity-SLIMMED COMP_LIGHT copy with only the tested blocks and their strips kept): World Boss and Breakthrough `damage`, `status_effect_damage`, `skill_cooldown_decrease`, `companion_summon_time_increase_pct` ratio 1.00000000;
  World Boss also `final_damage` (new value = table value minus the FD-buff extras), `buff_duration_increase_pct`, `skill_lvl_4th`, `attack_speed`, `attack_pct` 1.00000000.  Hexagon Necklace / Charm of the Undead / Horn Flute equip rows (block total AND the artifact-table DPS gain) == the toggled copy's total delta (World Boss, ratio 1.00000000; gains +160.4M / +20.0M / +30.4M on 314.3M).
- **Rebuilt for the companion cast timing rule (2026-11-18)** (see "Companions" -> "Cast timing"): 0 Input / ArtifactsInput / PotentialCubes diffs, Calc / Summary / Artifacts differ only in Companion-sheet row references, Companion / CompanionKits / Timeline-strip / Sensitivity companion cells regenerated (no hand-typed cell lost); Blackboot Bill keeps its old timing and Quickdraw / crew windows are untouched.  Total shifts at the verify-script base Inputs (Lv200, status 30, no artifacts), Blaze Wizard Lv10 / Wind Archer Lv7 with Summoning Time +20%: World Boss -0.17% / -0.13%, Breakthrough -3.21% / 0.00%, Chapter Hunt -0.24% / 0.00%, PvP 0.00% / -1.83%.  Blaze's 3rd stun now needs +13.667% summoning time (Breakthrough +3.5% between +12% and +14%).  Verified: verify script == workbook (World Boss / Breakthrough at +0 / +12 / +14, Wind Archer, companion None, Chapter Hunt, PvP, Hero Dungeon, Enhancement Dungeon), Sensitivity vs full model ratio 1.00000000 (World Boss + Breakthrough: damage / status_effect_damage / skill_cooldown_decrease / companion_summon_time_increase_pct, also at +12.9% base), Hexagon / Charm / Horn Flute rows == toggled-copy delta, `cyc.py` 0 cyclic components, 0 error cells and cube mirror to ~2e-16, longest formula 7048 (Sensitivity; Companion 6054).
- **Arwen's Glass Shoes + "no DPS effect" relabelling + Sensitivity fixes + engine artifacts (2026-11-21, replayed from FP-Mage / Hero / Paladin / Bishop / Bowmaster)**: the shoes are a REAL Companion Summoning Time Increase (+20% star 0 .. +40% star 5, linear 20/24/28/32/36/40, all user-confirmed); effective increase = Inputs value + artifact in the Companion host, every Sensitivity block, `b0` and so the CompanionsInput table / cube script; the equip row is in `STATUS_REBUILD_KEYS`, `COMPANION_FULL_SEARCH_KEYS` (now a module constant here) and `SUMMON_TIME_KEYS`.  The seven artifacts without a DPS effect are labelled "no DPS effect (reason)" (ArtifactsInput column 15).  Inputs / ArtifactsInput / PotentialCubes carried over with 0 diffs (only the Companion Summoning Time Increase label changed); Calc / Summary / Timeline formula-identical; Sensitivity grew from 9613 to 13527 rows (strips: 17 -> 36).  **Sensitivity strip-rebuild set** (`STATUS_REBUILD_KEYS`, re-derived for Corsair's strip = Jolly Roger's F / duration / cooldown, the cast groups' cooldowns incl. the Quickdraw divisor, the per-cast damage weights and c_slot): added `skill_damage`, `basic_attack_damage` (the engine experiment over all 313 golden inputs found real reuse errors of up to 2.7e-3 of Total for exactly these two), `boss_damage` + Candle / Sayram's / Star Rock / Peach Tree / Silver Pendant (the basic attack's own Boss Mastery shares the additive boss bucket; Peach / Silver follow Attack Speed), `crit_rate` + Ring of Cycles / Book of Ancient / Rainbow Snail Shell (Ring's Skill / Basic Attack Damage follows the crit rate), `skill_lvl_1st` (Nimble Feet -> Actions Per Second -> Quickdraw) / `skill_lvl_2nd` (Swift Fire / Scurvy only), and the four baked-in Final Damage artifacts (Clear Spring Water / Soul Pouch / Cursed Doll / Lit Lamp; Bottle of Emotion and `final_damage` were already in): they shift Inputs!final_damage, which scales Jolly Roger's strip F.  **Baked-in Final Damage artifacts on Corsair**: typed into `Inputs!final_damage` a value MULTIPLIES into the Input (F' = (1 + F/100)(1 + x/100) - 1); Corsair's Final Damage bracket is `(1 + (Inputs + Jolly Roger + Ahoy Mateys)/100)` (additive), so the what-if is a multiplicative FACTOR on the INPUT (adding 1 + x/100, removing 1/(1 + x/100), exact inverses) written as a block-local Input SHIFT (Sensitivity column U, 4th skill row) that `ib("final_damage")` adds everywhere the block reads the Input (K, the companion's Final Damage part, the strip's Jolly Roger scale) - NOT a plain 1 + x/100 on the whole product (as on classes whose bracket is only the Input), which a toggled copy typed the same way would not reproduce here because Jolly Roger's time-varying part sits inside the bracket (Cursed Doll star 5 reads 111.2% in World Boss, not 114%).  Bottle of Emotion's Attack-Speed-dependent value follows the same rule (ratio of (1 + value at the swept / real Attack Speed)).  No Skills-sheet formula reads Calc / Summary here (the Illusion-Step-style Skills!SkillMasteryBonus% leak of Bowmaster does not exist on Corsair); crew windows / Quickdraw / Ahoy proc are re-derived block-locally already.  **Soul Contract**: every real cooldown goes through `base_eff_cd_expr` (skills, All Aboard / Broadside's sustained rows that read another row's cooldown, the Quickdraw `x0`, Majestic's source rates; buffs / the stun entry / Swift Weaken / Ahoy read the resulting `Calc!Q`) - no omission found (engine == workbook 2.5e-16 in Chapter Hunt Lv140 with Quickdraw + companion).  Verified (formulas package, one evaluation at a time, slimmed COMP_LIGHT copies): Glass Shoes equivalence bit-for-bit on 10/10 pairs of the 71-case artifact golden set (World Boss Blaze Lv10 star 0 = in20, star 5 = in40, star 5 + in5 = in45 across the 3rd-stun flip, + Bottle / Hexagon / Horn Flute; Breakthrough Wind Archer Lv7 x4; Chapter Hunt x2); equip row == toggled copy 1.00000000 in World Boss from BOTH directions (gain 5.600544e7, % Gain 105.7902934581515 each), with Hexagon + Horn Flute + Bottle (104.92819925288588), Breakthrough block == toggled copy 1.00000000 and table gain == the time-weighted expected gain 1.00000000 (its dollar delta differs by design, item 9); Summoning-Time stat block with / without the shoes 1.00000000.  Sens-vs-main (main sheet with the swept Input set to the block's New Value, Bottle + Reindeer / Ring / Candle / Peach / Silver Pendant equipped): ratio 1.0000000000 in World Boss for `skill_damage`, `basic_attack_damage`, `boss_damage`, `final_damage` (New Value minus R_FD_ALL), `attack_speed`, `crit_rate` (Ring equipped) and in Enhancement Dungeon for `skill_damage`, `basic_attack_damage`, `boss_damage`, `final_damage`, `crit_rate`; `skill_lvl_1st/2nd/3rd/4th/all` 1.0000000000 in both once the documented passive-delta terms are neutralised; equip rows of Ring of Cycles / Peach Tree / Candle / Sayram's == toggled copy 1.00000000 (Star Rock / Book of Ancient are baked-in what-ifs: a toggled copy changes nothing by design).  Two-direction check of the five baked-in Final Damage artifacts (World Boss Cursed Doll 111.2338%, Lit Lamp 132.0953%, Bottle of Emotion 134.2980% at Attack Speed 80; Enhancement Dungeon Clear Spring Water 115.6853%; PvP Soul Pouch 129.0532%): gain and % Gain identical from either side to 6e-14 and == Total(equipped) - Total(unequipped).  `cyc.py` 0 cyclic components; longest formula 7030 (Sensitivity T1814; Companion 6054; cap 8192); 0 error cells on the FULL workbook (World Boss, Breakthrough, Breakthrough + Wind Archer Lv7; Sensitivity stripped; Shoes + Hexagon + Horn Flute + Bottle equipped); cube mirror 1.5e-16 (World Boss), 0 (Breakthrough), 6.9e-10 (Wind Archer Lv7, fractional-window artifact).  The engine side (`engine/classes/corsair.py`) models the artifacts since the same day: `tests/golden/corsair_artifacts_golden.json` / `test_corsair_artifacts.py` (71 workbook evaluations, engine == workbook within rel 1.5e-10 worst case, 7 toggle deltas, 10 equivalence pairs incl. Blackboot Bill Lv65 / 66, Broadside Lv117 / 118 / 138, Quickdraw Lv124 / 125 with Soul Contract in Chapter Hunt).

## Marksman: Companions + Status Effect Damage / KO timeline (2026-11-16 port from FP-Mage / Hero / Paladin / Dark Knight / Buccaneer / Corsair / Bowmaster)

Same feature set and rules as the sections above (Bowmaster's is the closest sibling): Inputs `STATUS_EFFECT_DAMAGE %` (row 22, self-detecting row-shift migration), `Companion` (row 51; rows 47-50 are the artifact slots) + live `Companion Summoning Time Increase %`, sheets `Timeline` / `CompanionKits` / `Companion` / `CompanionsInput`, Sensitivity rows for both stats, the Companion Comparison and summoning-time tables (weighted-ratio form), the Horn Flute rewire (`Companion!horn_uptime`) and the exported host values for `potential_cubes_ev.py` (+ `companion_kits.py` / `companion_python_model.py` copies in `Marksman/`).  With Companion = None, Status Effect Damage = 0 and a content where the engine stays off (Chapter Hunt, PvP, EXP / Equipment Dungeon, Hero Dungeon) the totals are bit-identical to the pre-port workbook (python mirror of the pre-port and new verify scripts, same non-trivial Inputs: Chapter Hunt 231464694.8832, PvP 39696932.7330, EXP / Equipment Dungeon 236102282.4773, Hero Dungeon 153240664.7043).  Marksman-specific wiring:
- **Engine buff** (`STATUS_BUFFS`): only **Illusion Step** ('atk', as Bowmaster; from Lv118 it is always on so nothing moves).  Marksmanship (both halves) and **Blink Bolt** (modelled always on) are constant terms of the engine's `A0`, via `marks_attack_terms` (Blink Bolt is folded into its `base` term, so the companion snapshot `k1`, `attack_bucket_avg` and the block twins carry it too).  Sharp Eyes (Crit Damage), Nimble Feet (Attack Speed) and Mortal Blow / Last Man Standing (steady-state Final Damage) are not Attack% ramps, so they stay averaged.
- **Engine groups**: Covering Fire, Bolt Burst, Snipe (bursts), Frostprey and Arrow Illusion (`dot`: 30 s / 25 s windows, `STATUS_FS_KEYS`).  Uniform rows (phi_unif): Empowered Piercing Arrow (the basic attack) and the Bolt Surplus chance proc (its trigger rate reads the engine-aware cast counts of Empowered Piercing Arrow and Snipe; the proc is spread uniformly although half of its triggers are timed Snipe casts - approximation).  Boss / normal DPS columns are `T` / `V` (as Bowmaster), timing factors `Z` / `AA`, per-cast boss damage `AB`.  Snipe's Lv134 'Empowered' fold-in and Empowered Piercing Arrow's Final Attack fold are part of the per-cast weights (they sit in `N`).
- **Player stun** (`STATUS_PLAYER_STUN`, host `pst` in the main / block / exported hosts, `pl_stun` in the engine host): Covering Fire 1 s every 19 s from the Lv49 mastery, Bolt Burst 1.5 s every 21 s from the Lv98 mastery (both `typ="cast"`), and **Frostprey as the `typ="periodic"` kind** (`tick` 1.5 s, `win` 30 s, p 0.1, dur 1 s: expected stunned share p x dur / tick = 6.7% for the whole 30 s window after every cast; cooldown 60 s, 36 s from Lv104, read from the row's live effective cooldown).  The three skills are `fixed=True` engine groups (cast on cooldown from t = 0, not optimised), so the engine is ON in every fixed-length single-target content once any of them is unlocked (Covering Fire Lv35+ is enough for the unlock gate of the group, the stun itself needs Lv49 / Lv98 / Lv69); Breakthrough's boss phase is lengthened by the stuns (also with Companion = None), Hero Dungeon is timed (no extension).  Group fixedness is not level-gated (Covering Fire Lv35-48 and Bolt Burst Lv63-97 are cast on cooldown from t = 0 without having a stun yet - tiny effect).  Arrow Illusion's 3 s bind is crowd control other than stun/freeze and is not modelled.  The shared engine supports the periodic kind as is: no shared-module change was needed.
- **Engine-on contents change by design** (test inputs, Companion None, S = 0, vs the pre-port workbook): World Boss +26.1%, Enhancement Dungeon +29.1% (KO phases: the optimal player), Breakthrough +3.0% (stun extension), Weapon Dungeon +2.8%, Chapter Boss +0.4%; the truncation of non-last DoT windows (Frostprey 30 s, Arrow Illusion 25 s against their cooldowns) and the engine's whole-bin cooldown spacing account for the small ones.
- **Companion host**: `unit` = Empowered Piercing Arrow's `N/F`; `avgbuff` = Summary `R_AVGBUFF` (= the strip's mean Attack% bucket with the engine on); snapshot `fdpart` 1 (Mortal Blow / Last Man Standing are inside `unit`); Marksman keeps the artifact 'enemy damage taken' bonus inside the boss / normal monster damage % buckets, so `taken_bucket` is the boss/normal blend (0 in PvP), as Bowmaster.
- **Sensitivity strips**: `STATUS_REBUILD_KEYS` as Bowmaster (the Attack%-feeding artifact toggles and `skill_lvl_2nd/3rd/4th/all`).  Rebuilding blocks read the main sheet's `s_0` / `W_0` for the stun vector; the Summoning-Time, Hexagon Necklace, Horn Flute and Skill Cooldown Decrease (+ its 10 milestone blocks) blocks run the full 3-candidate companion search (guide "Gap found by the Buccaneer port", items 1-4, from the start).  Longest formulas: Timeline strip 8092 (cap 8192 - five engine groups + three stun entries make this the tightest class; adding a group needs a check), Sensitivity 7383, Companion 6376, Calc 2324.
- **Verification** (2026-11-16, artifacts cleared, Sensitivity stripped, non-trivial Inputs: crit / boss / normal / skill / basic damage / def pen / DEX / STR / min-max / attack speed / Final Damage / damage; COMP_LIGHT build): `verify_marksman_workbook.py` == workbook (`helpers/sv.py` logic) for Chapter Boss (Bow Master), World Boss (Blaze Wizard, None, Wind Archer Lv10 with Buff Duration +40% / CDR 3 / Summoning Time +20%), Enhancement Dungeon, Breakthrough (None and Blaze Wizard), Hero Dungeon, Chapter Hunt (None, Wind Archer), EXP Dungeon, Equipment Dungeon (None), Weapon Dungeon, PvP (Blaze Wizard, Bow Master), Chapter Boss with BDI +60% / CDR 5, World Boss at Lv 48 / 49 / 62 / 63 / 69 / 97 / 98 / 103 / 104 / 110 / 118 / 136 and Breakthrough Lv 40 / 50 / 100 with no companion: 31 runs, all OK.  `cyc.py` 0 cyclic components; zero error cells on the FULL workbook (World Boss and Breakthrough, Sensitivity stripped, Hexagon + Charm + Horn Flute + Bottle of Emotion equipped; the Python mirror rebuilt from the exported host values reproduces the sheet's companion DPS and its b0+20 grid column to 1e-16).
  Sensitivity-vs-main (Blaze Wizard Lv10, S=30, Lv200, Bottle of Emotion + Reindeer's Spear equipped, run on a Sensitivity-SLIMMED COMP_LIGHT copy with only the tested blocks and their strips kept): World Boss and Breakthrough `damage`, `status_effect_damage`, `skill_cooldown_decrease`, `companion_summon_time_increase_pct` ratio 1.00000000; World Boss also `attack_pct`, `buff_duration_increase_pct`, `crit_damage`, `skill_lvl_4th` 1.00000000.  Hexagon Necklace / Charm of the Undead / Horn Flute equip rows (block total AND the artifact-table DPS gain) == the toggled copy's total delta (World Boss, ratio 1.00000000; gains +141.3M / +10.6M / +30.2M on 292.7M).

- **Rebuilt for the companion cast timing rule (2026-11-18, see "Companions" -> "Cast timing")**: 0 Input diffs, no hand-typed Sensitivity cell dropped; the Timeline strip shrank from 8092 to 1859 characters (longest formulas now Sensitivity 7383, Companion 6054).  Total shifts vs the pre-change workbook (test inputs, Lv200, S=30, artifacts cleared): Blaze Wizard Lv10 World Boss -0.27%, Breakthrough -5.28%, Chapter Hunt -0.38%, PvP 0.00%; Wind Archer Lv7 +20% summon time World Boss +0.12%, Breakthrough 0.00%, Chapter Hunt 0.00%, PvP -1.87%.  Re-verified: verify script == workbook (12 scenarios), Sensitivity-vs-main ratio 1.00000000 incl. the summoning-time +12.9 base (New Value 13.9 crosses Blaze's 13.667% third-stun flip), Hexagon / Charm / Horn Flute rows == toggled copy, 0 error cells and cube mirror rel diff 0 (World Boss, Breakthrough).

- **Arwen's Glass Shoes + "no DPS effect" relabelling, Sensitivity fixes, Soul Contract wiring, engine artifacts (2026-11-21, replayed from FP-Mage / Hero / Paladin / Bowmaster)**: (1) the shoes are a REAL, live Companion Summoning Time Increase (+20% star 0 .. +40% star 5, linear steps, all user-confirmed 2026-11-19); effective increase = Inputs value + artifact (`companion_summon_time_inc_expr`) in the Companion host, every Sensitivity block, `b0` (artifact outside the `MAX(0, ...)`), the CompanionsInput table and the cube script; the equip row is in `STATUS_REBUILD_KEYS`, `COMPANION_FULL_SEARCH_KEYS` and `SUMMON_TIME_KEYS`; the seven artifacts without a DPS effect are labelled "no DPS effect (reason)" (`ARTIFACT_NO_DPS_EFFECT`, ArtifactsInput column 15).  (2) **Strip rebuild set decided per stat with the engine** (frozen main strip vs re-solve, 40 engine-on configs World Boss / Enhancement Dungeon x Lv60-160 x two stat sets x Blaze / none; and every non-no-effect artifact toggle on three base sets): reuse is exact (<= 5e-16 of Total) for every stat NOT already in the set (Flat DEX .. Flat ATTACK, Skill / Basic Attack Damage, Boss Damage, Crit Rate, Attack Speed, Skill Level 1st incl. artifact-sized moves) and for Ring of Cycles, Candle, Sayram's, Peach Tree, Silver Pendant, Star Rock, Rainbow Snail Shell, Book of Ancient, ... because Illusion Step is the only timed buff and all three player stuns are fixed casts, so no relative damage weight can re-place a cast; the Attack%-feeding artifacts (Old Music Box / Secret Map / Reindeer / Alliance / Bottle / Charm / Hexagon: up to 37% error under reuse) and `skill_lvl_2nd/3rd/4th/all` were already in the set.  Only the shoes toggle was added.  (3) **Baked-in Final Damage artifacts** (Clear Spring Water, Soul Pouch, Cursed Doll, Lit Lamp, Bottle of Emotion's FD): multiplicative what-if factor, exact inverse on removal, applied to the TYPED `Inputs!final_damage` inside the additive bucket that also holds Mortal Blow / Last Man Standing (`(1+(F'+MB)/100)`, F' = (1+F/100)(1+x/100)-1) - a factor on the whole product would overstate the gain by ~2.5% here.  Verified with typed toggled-copy pairs (World Boss: Cursed Doll 111.377%, Lit Lamp 133.272%, Bottle 128.003%; Enhancement Dungeon Clear Spring Water 116.253%; PvP Soul Pouch 132.506%): gain and % Gain identical from BOTH directions and == Total(equipped) - Total(unequipped) to 1e-16.  (4) **Found by the engine golden test: the workbook never wired Soul Contract's Chapter-Hunt cooldown decrease** into any cooldown formula (CLAUDE.md item 11; Artifacts row only) - now `eff_cd_r` / `eff_cd_row` multiply by `(1 - pct/100)` like the other classes (Chapter Hunt + Soul Contract only; every other state unchanged).  (5) **Found by the skill-level sens-vs-main check: a block's Empowered Piercing Arrow / Snipe `SkillFoldBonus%` read the MAIN Calc rows** (Final Attack: Crossbow x Advanced Final Attack helpers, Snipe's factor E; bug #19), so `skill_lvl_2nd/all` blocks missed Final Attack's level response (~2e-4 of Total per level); the fold is now re-derived from the block's own rows.  Verified on the final workbook (Sensitivity-slimmed copies, <= 8 blocks): equivalence (shoes star s at Inputs x == no shoes at x + 20..40) bit-for-bit on 10/10 pairs (World Boss Blaze Lv10 star 0 = in20, star 5 = in40, star 5 + in5 = in45, + Bottle / Hexagon / Horn Flute; Breakthrough Wind Archer Lv7 x4; Chapter Hunt x2); Sensitivity shoes row == toggled copy 1.00000000, % Gain 106.34695171489288 from BOTH directions (Hexagon + Horn Flute + Bottle base 105.25775931; Chapter Hunt 106.62235; Breakthrough table == time-weighted expected 1.00000000, dollar delta differs by design); Soul Contract row (Chapter Hunt) == toggled copy 1.00000000 (116.953%); sens-vs-main in World Boss and Enhancement Dungeon: `skill_damage`, `basic_attack_damage`, `boss_damage`, `crit_rate`, `attack_speed`, `skill_lvl_4th` 1.0000000000; `skill_lvl_1st/2nd/3rd/all` differ by exactly the documented passive-delta terms (checked against the engine: 1st 1.00022502, 2nd 1.00056953, 3rd 1.00032643 predicted == measured).  0 error cells and cube mirror <= 2.6e-16 (World Boss / Breakthrough Blaze Lv10; Wind Archer Lv7 +2e-10, fractional-window artifact) with shoes + Hexagon + Horn Flute + Bottle equipped; `cyc.py` 0 cyclic components; longest formula 7501 (Sensitivity T1565, cap 8192); Inputs / ArtifactsInput / PotentialCubes carried over with 0 diffs (only the summoning-time label changed); Sensitivity grew by one strip (+182 rows).  The engine side (`engine/classes/marksman.py`) models the artifacts since the same day: `tests/golden/marksman_artifacts_golden.json` / `test_marksman_artifacts.py` (67 workbook evaluations, engine == workbook within rel 4.9e-11 worst case, ~1e-16 typically).

## Night Lord: Companions + Status Effect Damage / KO timeline (2026-11-16 port from FP-Mage / Hero / Paladin / Dark Knight / Buccaneer / Corsair / Marksman)

Same feature set and rules as the sections above (Corsair / Buccaneer share the Calc layout): Inputs `STATUS_EFFECT_DAMAGE %` (row 22, self-detecting row-shift migration), `Companion` (row 51; rows 47-50 are the artifact slots) + live `Companion Summoning Time Increase %`, sheets `Timeline` / `CompanionKits` / `Companion` / `CompanionsInput`, Sensitivity rows for both stats, the Companion Comparison and summoning-time tables (weighted-ratio form), the Horn Flute rewire (`Companion!horn_uptime`) and the exported host values for `potential_cubes_ev.py` (+ `companion_kits.py` / `companion_python_model.py` copies in `Night-Lord/`).  With Companion = None, Status Effect Damage = 0 and a content where the engine stays off (Chapter Hunt, PvP, EXP / Equipment Dungeon, Hero Dungeon) the totals are bit-identical to the pre-port workbook (python mirror of the pre-port and new verify scripts, same non-trivial Inputs at Lv200: Chapter Hunt 20471992962.8178, PvP 3624063466.2928, EXP / Equipment Dungeon 22082141151.1045, Hero Dungeon 14428800499.6616).  Night Lord-specific wiring:
- **Engine buffs** (`STATUS_BUFFS`): **Dark Sight (Attack)** as an 'atk' buff (inside the additive Attack% bucket with the artifacts - the 2026-11-03 `R_AVGBUFF` rule is kept: with the engine on `R_AVGBUFF` = the strip's mean buff bucket x Alchemic Adrenaline's averaged Final Damage factor, off = the old `(1+(DarkSight+Art)/100)(1+Frailty)(1+Adrenalin)`) and **Frailty Curse (self Final Damage)** as a `ramp` buff with a flat profile (its own multiplicative factor in the bucket, exactly as in `R_AVGBUFF`: no `fd_scale` needed).  Dark Sight (Crit Rate) and the Frailty Curse enemy debuff (monster damage taken, Lv111 crit damage taken) are passengers of the same casts: their rows' `Calc!R` equals the engine's cast count of the buff (the buff cells do not depend on any damage weight, so no cycle) but their effect stays the averaged additive bucket (`R_CRIT_RATE_BONUS`, `R_MONSTER_DMG_BONUS`, `R_CRIT_DAMAGE_BONUS`).  NOT player-timed, they stay averaged (also in the companion's snapshot where they are not a cast): **Alchemic Adrenaline** (action-rate-driven proc: Final Damage and Attack Speed), Nimble Feet, Shadow Partner's average multiplier, Venom's Weaken and the artifact damage-taken bonuses.
- **Engine groups**: Gust Charm (burst, fixed player-stun schedule), Triple Throw (burst), Dark Flare (`dot`: 20 s window of 2 s ticks, 3 hits each from Lv78, ICD 1.5 s from Lv104), Quad Star (burst), Sudden Raid (burst + its 5 s `dot` row, which shares the burst's cooldown and costs no action slot).  `STATUS_FS_KEYS` (hits from the engine's effective cast count) = Dark Flare, Sudden Raid (DoT).  Uniform rows (phi_unif): Showdown (the basic attack), Assassin's Mark and Venom (periodic ticks on a surrogate interval), Toxic Venom (chance proc: its trigger rate reads `Calc!S` of the triggering rows and therefore already follows the engine's cast counts) and Shadow Shifter's counterattack (driven by incoming hits).  Boss / normal DPS columns are `T` / `V` (the `U1:U3` helper cells are unchanged), timing factors `W`/`X`, per-cast boss damage `Y` (Showdown's is the engine's basic-attack weight, 0 while it is locked below Lv100), **`Z` = the pre-engine (averaged-model) cast count**.  No new Summary rows and no averaged-model twins were needed: Adrenalin's uptime reads `R_APS_PRE_ADRENALIN` (never a cast count), the buff counts that feed `R_CRIT_RATE_BONUS` / `R_MONSTER_DMG_BONUS` come from the buff cells, and `cyc.py` reports 0 cyclic components.
- **Player stun**: **Gust Charm** (Lv35 unlock; 2 s stun on 8 targets, patched from 1.5 s; cooldown 24 s, no Reuse mastery; `STATUS_PLAYER_STUN`, host `pst` in the main / block / exported hosts, `pl_stun` in the engine host) as a fixed on-cooldown stun group.  The engine is ON in every fixed-length single-target content from Lv35 (World Boss, Enhancement Dungeon, Chapter Boss, Weapon Dungeon), Breakthrough's boss phase is lengthened by the stuns (also with Companion = None), Hero Dungeon is timed (no extension).  Fixed means Gust Charm no longer waits for a KO window (World Boss Lv200: Gust Charm 4 casts at t = 0 / 24 / 48 / 72 s, Dark Sight 3, Frailty Curse 2, Quad Star 11, Dark Flare 2, Sudden Raid 4).
- **Triple Throw is never cast by the engine**: at Lv200 a Triple Throw cast (720% x2 x3 hits) is worth less than the Showdown action (522% x1.75 x6 hits) it replaces, so the optimal player skips it (0 DPS on that row in World Boss / Enhancement / Chapter Boss ... the engine-on contents; the averaged contents, e.g. Chapter Hunt, still cast it on cooldown) - the same engine behaviour as Hero's Beam Blade / Corsair's Swift Fire.
- **Engine-on contents change by design** (test inputs, Companion None, S = 0, vs the pre-port workbook): World Boss +38.3% and Enhancement Dungeon +37.2% (KO phases: the optimal player), Weapon Dungeon +8.6% (no start-up delay: buffs are cast when they pay, + optimal placement), Chapter Boss +3.5%, Breakthrough +1.0% (Gust Charm's stun extension).  Shared-engine approximation (all classes): different skills may be cast in the SAME one-second bin (e.g. Gust Charm, Quad Star and Dark Sight all at t = 0), beyond the actions per second the character really has.
- **Companion host**: `unit` = Showdown's `N/F` **divided by Shadow Partner's average multiplier** (decision: the shadow clone mirrors the PLAYER's own attacks, like the Final Attack procs of the sibling classes it is not part of the companion's hits - flip `unit` in `companion_host_main()` / the block host to include it); `avgbuff` = `R_AVGBUFF`; the snapshot has the CAST buffs (Dark Sight, Frailty Curse) fully up and Adrenalin at its average (`k1`, `fdpart` exported for the cube script); `attack_bucket_avg` = Dark Sight's average + artifacts; like the other warrior / thief classes the 'enemy damage taken' bonuses (Venom Weaken, Frailty Curse debuff, artifacts: `R_MONSTER_DMG_BONUS` + `AGG_ENEMY_DMG_TAKEN`) sit inside the boss / normal monster damage % buckets, so `taken_bucket` is the boss/normal blend (0 in PvP); Showdown's own Boss Monster Damage mastery is a skill mastery, not part of `boss_pct`.
- **Sensitivity strips**: `STATUS_REBUILD_KEYS` = FP-Mage's plus the Attack%-artifact toggles and `skill_lvl_1st/3rd/4th/all` (Dark Sight's / Frailty Curse's `F` and the Expert Throwing Star delta feed the strip's buff bucket).  Block twin cell `s_bucket` (calc_end + 17, the averaged Attack% sum; BLOCK_HEIGHT = LAST_ROW + 21); in a block `R_AVGBUFF`'s twin is `IF(engine, Bbuff_mean x Adrenalin, old product)` and the per-row `K` reads that cell.  Rebuilding blocks read the main sheet's `s_0` / `W_0` for the stun vector; the Summoning-Time, Hexagon Necklace, Horn Flute and Skill Cooldown Decrease (+ its 10 milestone blocks) blocks run the full 3-candidate companion search (guide "Gap found by the Buccaneer port", items 1-4, from the start).  Longest formulas: Timeline strip 7606, Sensitivity 7418, Companion 6376, Calc 2013 (cap 8192).
- **Not modelled**: the player's other crowd control; Adrenalin / Nimble Feet / Shadow Partner / the Frailty Curse debuff and Dark Sight's Crit Rate as time-resolved effects (averaged, fed with the engine's cast counts where they have one); Shadow Shifter's counterattack timing.  `skill_lvl_2nd/3rd/all` and `flat_luk` Sensitivity blocks include the passive "Magic Critical pattern" deltas / the main-stat flat Attack channel (CLAUDE.md bug 7) that the main sheet never implements, so against a re-evaluated main sheet they read +0.06% (2nd, 3rd) / +0.12% (all) / +0.0006% (`flat_luk`) high BY DESIGN (the same blocks equal the main sheet exactly at a level where no such passive is unlocked, e.g. `skill_lvl_3rd` at Lv70).
- **Verification** (2026-11-16, artifacts cleared, Sensitivity stripped, non-trivial Inputs: crit / boss / normal / skill / basic damage / def pen / LUK / DEX / min-max / attack speed / Final Damage / damage; COMP_LIGHT builds for the matrix, a full build for the full-workbook checks): `verify_night_lord_workbook.py` == workbook (`data/porting/helpers/sv.py` logic) for Chapter Boss (Bow Master; None with BDI +60% / CDR 5), World Boss (Blaze Wizard, None, Wind Archer Lv10 with Buff Duration +40% / CDR 3 / Summoning Time +20%), Enhancement Dungeon (Blaze Wizard; Wind Archer Lv7 with BDI +40% / CDR 3 at Lv121), Breakthrough (None, Blaze Wizard, Bow Master; Lv50 None), Hero Dungeon, Chapter Hunt (None, Wind Archer), EXP Dungeon, Equipment Dungeon, Weapon Dungeon, PvP (Blaze Wizard, Bow Master), World Boss at Lv 14 / 15 / 23 / 24 / 34 / 35 / 39 / 43 / 59 / 60 / 62 / 63 / 66 / 69 / 74 / 78 / 82 / 90 / 94 / 99 / 100 / 103 / 104 / 105 / 107 / 108 / 110 / 115 / 117 / 120 / 122 / 125 / 126 / 130 / 134 / 136 / 138 and Breakthrough Lv 34 / 35 / 62 / 63 / 99 / 100 with no companion: 62 runs, all OK.
  `cyc.py` 0 cyclic components; zero error cells on the FULL workbook (World Boss and Breakthrough, Sensitivity stripped, Hexagon + Charm + Horn Flute + Bottle of Emotion equipped, Blaze Wizard Lv10, S=30; World Boss also with the Sensitivity sheet); the Python mirror rebuilt from the exported host values reproduces the sheet's companion DPS and its b0+20 grid column (World Boss 0 / 2e-16, Breakthrough 0 / 0).
  Sensitivity-vs-main (Blaze Wizard Lv10, S=30, Lv200, Bottle of Emotion + Reindeer's Spear equipped, run on a Sensitivity-SLIMMED COMP_LIGHT copy with only the tested blocks and their strips kept): World Boss and Breakthrough `damage`, `status_effect_damage`, `skill_cooldown_decrease`, `companion_summon_time_increase_pct`, `buff_duration_increase_pct` ratio 1.00000000; World Boss also `attack_pct`, `crit_rate`, `final_damage`, `attack_speed`, `boss_damage`, `def_pen`, `incoming_hit_rate`, `skill_lvl_1st/4th`, `basic_attack_target_increase`, and with Wind Archer Lv7 + Summoning Time +20% (a non-zero candidate flip case) CDR / summoning time / `status_effect_damage` / `damage` 1.00000000.  Hexagon Necklace / Charm of the Undead / Horn Flute equip rows (block total AND the artifact-table DPS gain) == the toggled copy's total delta (World Boss, ratio 1.00000000; gains +398.8M / +48.1M / +75.2M on 802.2M; Bottle of Emotion / Old Music Box toggles also exact; Reindeer's Spear's toggle is not comparable to a plain toggled copy because its base Defense Penetration is baked into `Inputs!def_pen`, see guide item 15 / CLAUDE.md checklist 8).
- **Rebuilt for the companion cast timing rule (2026-11-18)** (see "Companions" -> "Cast timing"): 0 Input / ArtifactsInput / PotentialCubes diffs, Calc / Summary / Artifacts differ only in Companion-sheet row references, Companion / CompanionKits / Timeline-strip / Sensitivity companion cells regenerated (no hand-typed cell lost); Gust Charm (the player's stun) keeps its old timing and Shadow Partner stays divided out of the companion unit.  Total shifts at the verify-script base Inputs (Lv200, status 30, no artifacts), Blaze Wizard Lv10 / Wind Archer Lv7 with Summoning Time +20%: World Boss +0.05% / -0.24%, Breakthrough -2.59% / 0.00%, Chapter Hunt -0.19% / 0.00%, PvP 0.00% / -1.78%.  Blaze's 3rd stun now needs +13.667% summoning time (Breakthrough +4.8% between +12% and +14%).  Verified: verify script == workbook (World Boss / Breakthrough at +0 / +12 / +14, Wind Archer, companion None, Chapter Hunt, PvP, Hero Dungeon, Enhancement Dungeon), Sensitivity vs full model ratio 1.00000000 (World Boss + Breakthrough: damage / status_effect_damage / skill_cooldown_decrease / companion_summon_time_increase_pct, also at +12.9% base where the summoning-time step crosses 13.667 (New Value 13.9)), Hexagon / Charm / Horn Flute rows == toggled-copy delta, `cyc.py` 0 cyclic components, 0 error cells and cube mirror to ~1e-16, longest formula 7418 (Sensitivity; Companion 6054).

- **Arwen's Glass Shoes + "no DPS effect" relabelling + Sensitivity fixes + Soul Contract / Mark FD wiring + engine artifacts (2026-11-21, replayed from FP-Mage / Dark Knight / Bishop)**: (1) the shoes are a REAL, live Companion Summoning Time Increase (+20% star 0 .. +40% star 5, linear 20/24/28/32/36/40, all user-confirmed 2026-11-19); effective increase = Inputs value + artifact (`companion_summon_time_inc_expr`) in the Companion host, every Sensitivity block, `b0` (artifact outside the `MAX(0, ...)`) and so the CompanionsInput table / cube script; the equip row is in `STATUS_REBUILD_KEYS`, `COMPANION_FULL_SEARCH_KEYS` and `SUMMON_TIME_KEYS` (the latter two are new module constants: the block code used inline tuples before).  The seven artifacts without a DPS effect are labelled "no DPS effect (reason)" (`ARTIFACT_NO_DPS_EFFECT`; ArtifactsInput gets a 15th column).  (2) **Sensitivity fix 1** - strip rebuild set, decided PER STAT with an engine experiment (reuse of the main timeline strip vs a full re-solve, World Boss / Enhancement Dungeon, Lv110 / 140, stat sets A / C, with / without a companion, doses +1 / +30 / +300; and every artifact toggled as the 4th slot): exact to 1e-15 for LUK / DEX, Defense, Damage %, Damage Amp, Final Damage, Min / Max Damage, Crit Damage, Def Pen, Flat ATTACK, ATTACK %, Attack Speed, Normal Damage, Basic Attack Target Increase, Incoming Hit Rate and the 2nd-job skill level (Gust Charm is a FIXED on-cooldown stun cast, Assassin's Mark a uniform row); NOT exact: `skill_damage` (0.6% off at +1 in the Enhancement Dungeon), `basic_attack_damage` (0.5% at +30), `boss_damage` (exact at +30, 1% at +300: Showdown has its own Boss Mastery chain), the buff-value / timing stats already in the set and the Attack%-bucket artifacts.  Added to `STATUS_REBUILD_KEYS`: `skill_damage`, `basic_attack_damage`, `boss_damage`, `crit_rate` (Ring of Cycles), the artifacts `ring_of_cycles`, `book_of_ancient`, `rainbow_snail_shell` (they move Ring of Cycles' threshold), `candle`, `sayrams_necklace`, `star_rock`, `peach_tree`, `silver_pendant` (the boss bucket, which is not uniform across rows) and the shoes; NOT added: `skill_lvl_2nd` and `contract_of_darkness` (exact: the Contract's boss-only Crit Rate does not enter Ring of Cycles' threshold here and scales every row alike).  Sensitivity grew by 13 strips (+2314 rows).  **Sensitivity fix 2**: the baked-in Final Damage what-ifs (Cursed Doll, Lit Lamp, Clear Spring Water, Soul Pouch, Bottle of Emotion) are multiplicative factors, exact inverses on removal (helper cells `U` of the 6th / 7th skill row of each block: Night Lord's own columns W / X / Y / Z are the timing columns).  (3) **Two real omissions found and fixed in the Sensitivity blocks** (main sheets unchanged): (a) Soul Contract's Chapter-Hunt cooldown decrease was wired at the main `Calc!Q` call site but missing from the Sensitivity block's own `effective_cooldown_expr(...)` call (CLAUDE.md item 11): a block never saw the artifact's cooldown cut, so the Soul Contract equip row and every Cooldown Decrease block read the wrong cooldowns in Chapter Hunt; now multiplied in like the main sheet.  (b) CLAUDE.md bug 19: Assassin's Mark's `MasteryFinalDamage%` (Skills sheet, `_MARK_OF_ASSASSIN_FD`) reads the MAIN `Calc!F` of Night Lord's Mark, so blocks sweeping a 4th-job skill level never saw it move; the block's K formula now reads its own Night Lord's Mark row (`mastery_final_block_expr`).  Night Lord has no Defense % (PvP's opponent has the flat Defense in workbook, verify script and engine alike): no PvP mismatch.  Rebuilt once: Inputs / ArtifactsInput / PotentialCubes carried over with 0 diffs (only the Companion Summoning Time Increase label changed), Calc / Summary / Timeline / Skills formula-identical (Companion differs only in the 17 `inc` references + `b0`), `cyc.py` 0 cyclic components, longest formula 7519 (Sensitivity T1845; Companion 6054; cap 8192).  Verified on the Night Lord workbook: Glass Shoes equivalence (Total DPS with shoes star s at Inputs x == without shoes at x + 20..40) bit-for-bit on 10/10 pairs (World Boss Blaze Lv10 star 0 = in20 2.127975622548321e16, star 5 = in40 2.158039749690518e16, star 5 + in5 = in45 2.160773127006149e16 across the 3rd-stun flip, + Bottle / Hexagon / Horn Flute 4.564085635819307e16; Breakthrough Wind Archer Lv7 x4; Chapter Hunt x2); Sensitivity equip row == toggled-copy delta 1.000000000000 (World Boss, BOTH directions, % Gain 103.47520216685223 each; Hexagon + Horn Flute + Bottle base 104.2878450293645; Chapter Hunt 105.98404219498735), Summoning-Time stat and damage blocks with the shoes equipped 1.000000000000, Breakthrough equip row block == toggled copy 1.000000000000 and == time-weighted expected 1.000000000000 (its dollar delta differs by design, CLAUDE.md item 9); sens-vs-main (swept Input set to the block's New Value in a Sensitivity-emptied copy, Ring of Cycles + Bottle + Reindeer equipped) ratio 1.000000000000 for skill_damage, basic_attack_damage, boss_damage, crit_rate, skill_lvl_4th (World Boss and Enhancement Dungeon; Lv200 caps the 4th-job input level, the skill-level rows use Lv140); the rebuilt artifact toggles (ring, candle, peach tree, silver pendant, Sayram's, Rainbow Snail Shell, Contract of Darkness, Charm) == toggled copy 1.000000000000; Star Rock (baked +100 Boss Damage) block == main with it folded into Inputs 1.000000000000; Reindeer's Spear equip % Gain 138.36% at def pen 50 -> 109.73% at 99 (saturating); `skill_lvl_1st/2nd/3rd/4th/all` differ from the plain main re-run by exactly the documented passive-delta term (Agile Claws / Physical Training / Claw Mastery / Critical Throw / Enveloping Darkness / Expert Throwing Star Handling / Claw Expert / Dark Harmony levels baked into Inputs; Expert Throwing Star's Attack% delta baked into the Attack% bucket for the test) and equal the main re-run WITH those deltas to 1.000000000000 (World Boss 1st / 2nd / 3rd / 4th / all, Enhancement Dungeon 4th / all; this is also the Mark of Assassin fix); Soul Contract (Chapter Hunt) equip row == toggled copy 1.000000000000 and % Gain 150.1986019662869 from BOTH directions, `skill_cooldown_decrease` block == main with and without Soul Contract equipped; baked-in Final Damage pairs in both directions identical to 1e-16 (gain and % Gain) and == Total(equipped) - Total(unequipped): Cursed Doll 114.0%, Lit Lamp 140.0%, Bottle of Emotion 143.1328329303398% (World Boss, Attack Speed 100), Clear Spring Water 120% (Enhancement Dungeon), Soul Pouch 140% (PvP); 0 error cells (World Boss, Breakthrough; Shoes + Hexagon + Horn Flute + Bottle equipped, Sensitivity stripped) and cube mirror 2.1e-16 (World Boss), 0 (Breakthrough Blaze Lv10), 6.6e-10 (Breakthrough Wind Archer Lv7, fractional-window artifact).  (4) The engine side (`engine/classes/night_lord.py`) models the artifacts (the old `artifact_attack_pct` hook now adds to the artifact Attack%): `tests/golden/night_lord_artifacts_golden.json` / `test_night_lord_artifacts.py` (73 workbook evaluations, engine == workbook within rel 1.4e-10 worst case - the Breakthrough Wind Archer cases at a +40% summon window - 67 of 73 below 1e-14, 6 equip-toggle deltas, 10 equivalence pairs; `test_night_lord.py` stays bit-exact, 380).

## Shadower: Companions + Status Effect Damage / KO timeline (2026-11-16 port from FP-Mage / Hero / Paladin / Dark Knight / Buccaneer / Corsair / Marksman / Night Lord)

Same feature set and rules as the sections above (Night Lord is the closest sibling): Inputs `STATUS_EFFECT_DAMAGE %` (row 22, self-detecting row-shift migration), `Companion` (row 51; rows 47-50 are the artifact slots) + live `Companion Summoning Time Increase %`, sheets `Timeline` / `CompanionKits` / `Companion` / `CompanionsInput`, Sensitivity rows for both stats, the Companion Comparison and summoning-time tables (weighted-ratio form), the Horn Flute rewire (`Companion!horn_uptime`) and the exported host values for `potential_cubes_ev.py` (+ `companion_kits.py` / `companion_python_model.py` copies in `Shadower/`).  With Companion = None, Status Effect Damage = 0 and a content where the engine stays off (Chapter Hunt, PvP, EXP / Equipment Dungeon, Hero Dungeon) the totals equal the pre-port workbook (python mirror of the pre-port and new verify scripts, same non-trivial Inputs at Lv200: Chapter Hunt 1854375515034.726 (differs from the pre-port value in the last digit only: summation order), PvP 168202436121.1350, EXP / Equipment Dungeon 2107151264647.1765, Hero Dungeon 1376310782409.3289).  Shadower-specific wiring:
- **Engine buffs** (`STATUS_BUFFS`): **Dark Sight (Attack)** as an 'atk' buff (additive Attack% bucket with Steal, Meso Mastery and the artifacts) and **Into Darkness** and **Smokescreen** as `ramp` buffs with flat profiles (Final Damage).  Summary's averaged model multiplies the two Final Damage buffs, the engine adds them, so Smokescreen's strip effect is scaled by `1 + Into Darkness's steady-state average Final Damage %/100` (`fd_cross_scale`: mean-field cross term, independent of the engine's cast counts; the verify script mirrors it).  Dark Sight (Crit Rate) and Smokescreen's Lv113 Crit Damage +30% are passengers of their casts (`Calc!R` = the engine's cast count, effect stays an averaged additive bucket).  NOT player-timed, they stay averaged (also in the companion snapshot where they are not a cast): **Steal** (always on, x3), **Meso Mastery** (Attack +25% for 5 s per Meso generation: action-rate driven, folded into the engine's constant `A0`), Nimble Feet, Shadow Partner's average multiplier, Venom's Weaken / the artifact damage-taken bonuses (`R_MONSTER_DMG_BONUS`), Murderous Intent's multiplier and the Meso / Blood Money stack averages (they only affect the normal-monster target counts, the engine runs single-target).
- **Engine groups**: Phase Dash (burst, fixed player-stun schedule), Meso Explosion + Blood Money (one group: Blood Money rides on every Meso Explosion cast, shares its cooldown, costs no action slot), Dark Flare (`dot`: 20 s window of 2 s ticks, 3 hits each from Lv78, ICD 1.5 s from Lv104), Assassinate (burst; the finisher average and Murderous Intent are inside its per-cast weight), Sudden Raid (burst + its 5 s `dot` row sharing the burst's cooldown).  `STATUS_FS_KEYS` = Dark Flare, Sudden Raid (DoT).  Uniform rows (phi_unif): Cruel Stab (the basic attack), Venom, Toxic Venom (chance proc: its trigger rate reads `Calc!S` of the triggering rows and already follows the engine's cast counts) and Shadow Shifter.  Boss / normal DPS columns `T` / `V`, timing factors `W` / `X`, per-cast boss damage `Y`, `Z` = the averaged model's cast count.
- **Player stun**: **Phase Dash** (Lv63 unlock; 2 s stun, cooldown 23 s, no Reuse mastery; `STATUS_PLAYER_STUN`, host `pst` in the main / block / exported hosts, `pl_stun` in the engine host) as a fixed on-cooldown stun group.  The engine is ON in every fixed-length single-target content from Lv63 (and in World Boss / Enhancement Dungeon at any level for the KO phases), Breakthrough's boss phase is lengthened by the stuns (also with Companion = None), Hero Dungeon is timed (no extension).
- **Engine-on contents change by design** (test inputs, Companion None, S = 0, vs the pre-port workbook): World Boss +35.5% and Enhancement Dungeon +32.6% (KO phases: the optimal player), Chapter Boss +2.2%, Weapon Dungeon +0.9%, Breakthrough +0.6% (Phase Dash's stun extension).  Shared-engine approximation: different skills may be cast in the same one-second bin.
- **Companion host**: `unit` = Cruel Stab's `N/F` **divided by Shadow Partner's average multiplier** (user, 2026-11-16: a clone mirrors only the player's own attacks, never the companion's); `avgbuff` = `R_AVGBUFF` (engine on: the strip's mean buff bucket); the snapshot has the CAST buffs (Dark Sight, Into Darkness, Smokescreen) fully up, Steal and Meso Mastery at their averages (`k1`, `fdpart` exported for the cube script); `attack_bucket_avg` = Dark Sight's average + Steal + Meso Mastery + artifacts.  Summary's `R_MONSTER_DMG_BONUS` already contains `AGG_ENEMY_DMG_TAKEN` here, so the main-sheet `boss_pct` / `norm_pct` must not add it again (the block twin does, since its `R_MONSTER_DMG_BONUS` twin has only Venom's Weaken); `taken_bucket` is the boss/normal blend (0 in PvP).
- **Sensitivity strips**: `STATUS_REBUILD_KEYS` = the Night Lord list plus `skill_lvl_2nd` (Steal's F is in `A0`), `attack_speed` and `athena_gloves_equipped` (Meso Mastery's uptime depends on Actions/s).  Block twin cell `s_bucket` (calc_end + 18), BLOCK_HEIGHT = LAST_ROW + 21.  Rebuilding blocks read the main sheet's `s_0` / `W_0`; Summoning-Time, Hexagon Necklace, Horn Flute and Skill Cooldown Decrease (+ its 10 milestone blocks) run the full 3-candidate companion search.  Longest formulas: Timeline strip 7606, Sensitivity 7381, Companion 6376, Calc 2180 (cap 8192).
- **Not modelled**: the player's other crowd control; Steal / Meso Mastery / Nimble Feet / Shadow Partner / Venom's Weaken as time-resolved effects; Shadow Shifter's counterattack timing.  `skill_lvl_2nd` / `_all` / `_4th`-type Sensitivity blocks include the passive "Magic Critical pattern" deltas that the main sheet never implements, so against a re-evaluated main sheet `skill_lvl_2nd` reads +0.07% high BY DESIGN.  The shared `companion_python_model.run` returns no `stun_vector` key when there is no companion and no active player stun; the verify script treats that as an all-zero vector (shared-module quirk, not changed).
- **Verification** (2026-11-16/17, artifacts cleared, Sensitivity stripped, non-trivial Inputs, Lv200 unless stated, COMP_LIGHT builds for the matrix): `verify_shadower_workbook.py` == workbook (`data/porting/helpers/sv.py` logic) for Chapter Boss (Bow Master; None with BDI +60% / CDR 5; Blaze Wizard Lv12 at Lv118, S = 0), World Boss (Blaze Wizard, None, Wind Archer Lv10 with Buff Duration +40% / CDR 3 / Summoning Time +20%), Enhancement Dungeon (Blaze Wizard; Wind Archer Lv7 with BDI +40% / CDR 3 at Lv121; None at Lv138), Breakthrough (None, Blaze Wizard, Bow Master), Hero Dungeon, Chapter Hunt (None, Wind Archer, Blaze Wizard with CDR 6 / BDI +100%), EXP / Equipment / Weapon Dungeon, PvP (Blaze Wizard, Bow Master, None), World Boss with no companion at Lv 14 / 15 / 23 / 24 / 33-35 / 37 / 38 / 42 / 43 / 49 / 50 / 59 / 60 / 62 / 63 / 65-69 / 71-75 / 77 / 78 / 81 / 82 / 89 / 90 / 93 / 94 / 99-138 (every level 99-138), Breakthrough Lv 62 / 63 / 99 / 100 / 107 / 138 and World Boss / Breakthrough Lv62-63 with Blaze Wizard: about 130 runs, all OK.  Below Lv63 there is no damaging skill (Cruel Stab Lv100), so those totals are 0 without a companion.  `cyc.py` 0 cyclic components; the Python mirror rebuilt from the exported host values reproduces the sheet's companion DPS and its b0+20 grid column (FULL build, World Boss 0 / 3.5e-16, Breakthrough 0 / 0; zero error cells in both, Hexagon + Charm + Horn Flute + Bottle of Emotion equipped, Sensitivity stripped).
  Sensitivity-vs-main (Blaze Wizard Lv10, S=30, Lv200, Bottle of Emotion + Reindeer's Spear equipped, Sensitivity-SLIMMED COMP_LIGHT copy): World Boss `damage`, `status_effect_damage`, `skill_cooldown_decrease`, `companion_summon_time_increase_pct`, `buff_duration_increase_pct`, `attack_pct`, `crit_rate`, `attack_speed`, `skill_lvl_1st`, `skill_lvl_3rd`, `skill_lvl_4th`; Breakthrough `damage`, `status_effect_damage`, `skill_cooldown_decrease`, `companion_summon_time_increase_pct`, `buff_duration_increase_pct`, `attack_pct`; and with Wind Archer Lv7 + Summoning Time +20% (candidate flip case) CDR / summoning time / `status_effect_damage` / `damage`: ratio 1.00000000.  Hexagon Necklace / Charm of the Undead / Horn Flute equip rows (block total AND the artifact-table DPS gain) == the toggled copy's total delta (World Boss, ratio 1.00000000; gains +925.3M / +115.6M / +162.5M on 1.796B).
- **Rebuilt for the companion cast timing rule (2026-11-18)** (see "Companions" -> "Cast timing"; the player's own Phase Dash timing is unchanged): Inputs carried over with 0 diffs, no formula over 8192 characters (Sensitivity 7381, Companion 6054), 0 cyclic components, 0 error cells (World Boss / Breakthrough, Hexagon + Charm + Horn Flute + Bottle of Emotion equipped), cube-mirror match to ~2e-16.  Totals vs the pre-change workbook (test inputs, Lv200, status 30, Blaze Wizard Lv10 at +0% / Wind Archer Lv7 at +20%): World Boss -0.11% / -0.13%, Breakthrough -1.91% / 0.00%, Chapter Hunt -0.14% / 0.00%, PvP 0.00% / -1.75%.  Verify script == workbook for World Boss and Breakthrough with Blaze Lv10 at +0 / +12 / +14 (Breakthrough jumps +4.0% between +12 and +14: Blaze's 3rd stun cast, needs >= 13.667%), Wind Archer Lv7 +20, Breakthrough with no companion, Chapter Hunt, PvP, Hero Dungeon, Enhancement Dungeon; Sensitivity-vs-main ratio 1.00000000 for `damage`, `status_effect_damage`, `skill_cooldown_decrease`, `companion_summon_time_increase_pct` at World Boss and Breakthrough, and for the last two at the +12.9 summoning-time base (New Value 13.9, crosses 13.667); Hexagon / Charm / Horn Flute equip rows == toggled-copy delta.
- **Arwen's Glass Shoes + "no DPS effect" relabelling + Sensitivity fixes + Soul Contract wiring (2026-11-21, replayed from FP-Mage / Buccaneer / Dark Knight; engine port the same day)**: the shoes are a REAL, live Companion Summoning Time Increase (+20% star 0 .. +40% star 5, linear 20/24/28/32/36/40, all user-confirmed 2026-11-19); effective increase = Inputs value + artifact (`companion_summon_time_inc_expr`) in the Companion host, every Sensitivity block, `b0` (artifact outside the `MAX(0, ...)`) and so the CompanionsInput table / cube script; the equip row is in `STATUS_REBUILD_KEYS`, `COMPANION_FULL_SEARCH_KEYS` (new constant, the old inline tuple) and `SUMMON_TIME_KEYS`.  The seven artifacts without a DPS effect are labelled "no DPS effect (reason)" (ArtifactsInput gets a 15th column).  **Soul Contract was missing at BOTH cooldown call sites** (`Calc` eff_cd and the Sensitivity block's; the row on the Artifacts sheet was computed but never read - the DK / Bishop bug, CLAUDE.md item 11): now `effective_cooldown_expr(...) * (1 - soul_pct/100)` at both, so every `Q` / `R` / buff uptime / Phase Dash entry / strip cooldown follows (Calc: 52 formula cells changed, nothing else; the workbook / engine Chapter Hunt golden cases and the Soul Contract equip-toggle delta (+5.2e17, rel 0.0) agree).  The PvP defense wiring was checked (no Defense % input here: the workbook's `monster_defense` PvP branch reads `Inputs!defense`, like the verify script / engine); the only Skills-sheet formula that reads a swept Input (Cruel Stab's `6+basic_attack_target_increase`) is re-derived in the block already (bug 19).  Rebuilt once: Inputs / ArtifactsInput / PotentialCubes carried over with 0 diffs (only the Summoning Time label), Summary / Timeline / Skills formula-identical, Companion differs only in the 17 `inc` refs + `b0`, `cyc.py` 0 cyclic components, longest formula 7481 (Sensitivity T1845; was 7381; Companion 6054; cap 8192), Sensitivity 9540 -> 11630 rows (more strips).
  - *Sensitivity fixes*: strip rebuild set (derived from `/tmp` engine experiments `stl.solve` base vs swept, 2592 big-delta runs over Lv63-200 in World Boss / Enhancement Dungeon / Chapter Boss, plus 6144 runs with artifacts equipped): Skill Damage % / Basic Attack Damage % / Boss Damage % flip the schedule or the per-cast weights (Cruel Stab has its own Boss Mastery; the cast groups weigh against it); Crit Rate % does with Ring of Cycles equipped (its Skill / Basic Attack Damage follows the crit rate), so the toggles `ring_of_cycles`, `book_of_ancient`, `rainbow_snail_shell`, `candle`, `sayrams_necklace`, `star_rock` join them; uniform stats (LUK, DEX, Damage %, Damage Amp, Final Damage, Min / Max, Crit Damage, Def Pen, ATTACK, Normal Damage, the target increase) and the baked-in Final Damage artifacts do not (Shadower's strip never reads `Inputs!final_damage`: it is a separate multiplicative factor next to Into Darkness / Smokescreen).  `skill_lvl_1st` .. `_all`, `attack_speed`, Status Effect Damage, CDR, buff duration and the Attack%-artifact toggles were already in the list (the skill levels also feed the passive deltas).  Baked-in Final Damage what-ifs (Cursed Doll, Lit Lamp, Clear Spring Water, Soul Pouch, Bottle of Emotion's Attack-Speed-dependent value) are now a multiplicative FACTOR in both directions (helper cells U row_header+4 / +5: column Z is Shadower's `CastsInFight(averaged)`), exact inverses; the Buccaneer-style typed-Input approach is NOT needed here because the Input FD is its own factor in K (verified: Cursed Doll 114.0%, Lit Lamp 140.0%, Clear Spring Water 120.0% exactly).
  - *Verification* (`formulas`, one evaluation at a time, Lv200, Blaze Wizard Lv10, Sensitivity-slimmed COMP_LIGHT copy, test Inputs = the golden `STATS_A` (not the committed, row-shifted Inputs)): Glass Shoes equivalence (shoes star s at Inputs x == no shoes at x + 20..40) bit-for-bit on 10/10 workbook pairs (World Boss Blaze star0 = in20 3.2514e16, star5 = in40 3.3043e16, star5+in5 = in45 3.2895e16 across the 3rd-stun flip, + Bottle / Hexagon / Horn Flute 6.5829e16; Breakthrough Wind Archer Lv7 x4, Chapter Hunt x2); equip row block == toggled copy 1.00000000 in World Boss (% Gain 102.63085238116516 from BOTH directions, Hexagon + Horn Flute base 104.9993), Chapter Hunt 1.00000000 (102.15), Breakthrough table gain == time-weighted expected 1.00000000 (its dollar delta differs BY DESIGN, CLAUDE.md item 9); Summoning-Time stat with / without the shoes 1.00000000.  Sens-vs-main (swept Input set to the block's New Value in a Sensitivity-emptied copy; ratio 1.0000000000): `skill_damage`, `basic_attack_damage`, `boss_damage`, `crit_rate` (Ring of Cycles + Bottle equipped) in World Boss AND Enhancement Dungeon, `final_damage`, `attack_speed`, `def_pen`, `damage` (World Boss), `skill_lvl_1st` / `_2nd` / `_3rd` / `_4th` / `_all` (World Boss) and `_1st` / `_3rd` (Enhancement Dungeon) with the block's documented passive deltas carried (`skill_lvl_2nd`'s deltas: Agile Daggers / Channel Karma / Dagger Mastery / Critical Edge / Physical Training); `flat_luk` reads +3.7e-6 high BY DESIGN (the main-stat's flat-Attack half exists only in the block, CLAUDE.md item 7).  Equip rows == toggled copy: Ring of Cycles, Candle, Sayram's Necklace, Rainbow Snail Shell (1.00000000).  Reference-only artifacts (typed into Inputs by the user): Book of Ancient (+20 crit rate, dependent +84.75 crit damage incl. Dark Sight Crit's 5.25 and Ring's 56) and Star Rock (+100 Boss Damage) == the copy with their stats folded into Inputs, 1.0000000000 (item 8a).  Reindeer's Spear % Gain falls with `def_pen`: 137.29% (50) -> 129.84% (80) -> 106.41% (99.9) (item 8b).  Two-direction % Gain of the baked-in Final Damage artifacts (item 15; state 0 / state 1 with the typed value): Cursed Doll 114.0000% (with Candle live), Lit Lamp 140.0000%, Bottle of Emotion 127.7853% (Attack Speed 84), Clear Spring Water 120.0000%, Soul Pouch 140.0000%: block read in state 0 == Total(state 1), read in state 1 == Total(state 0), gain and % Gain identical from both directions (rel diff <= 4.1e-16).  0 error cells (110838 cells, World Boss + Breakthrough, Sensitivity stripped, shoes + Hexagon + Horn Flute + Bottle equipped); cube mirror World Boss 0 / 2.0e-16 (sheet column / b0+20 grid), Breakthrough Blaze 0 / 0, Breakthrough Wind Archer Lv7 7.3e-10 / 7.3e-10 (the documented fractional-window noise of the permanent-effect uptime).
- **Engine (2026-11-21)**: `engine/classes/shadower.py` models the artifacts (`inputs["artifacts"]`, `artifacts` result block, `schema()["artifacts"]`, `artifacts_modelled=True`); `tests/golden/shadower_artifacts_golden.json` / `test_shadower_artifacts.py`: 75 workbook evaluations (every artifact at star 5 in World Boss with Blaze Wizard Lv10, other fight shapes, stars, crit-rate branches incl. Dark Sight Crit at the 100% line, Reindeer def pen 50 / 80 / 99, Phase Dash Lv62 / 63 with and without a companion, Lv75 / 82 / 99 / 100 / 110 / 113 / 115 (incoming hit rate 0 / 2.5 / 6) / 125 / 136, stats set B, Soul Contract in Chapter Hunt, the Glass Shoes equivalence pairs): engine == workbook within rel 1e-9 on every case (worst 9.8e-11: Breakthrough + Wind Archer's fractional-window noise; otherwise <= 6e-16), 7 equip-toggle deltas (incl. Soul Contract in Chapter Hunt) and 10 equivalence pairs identical; `test_shadower.py` stays bit-exact (391 cases).  Wiring decisions: the Attack% artifacts join Dark Sight's additive bucket (strip `A0` = Steal + Meso Mastery + the artifact bucket without Charm); the artifacts' enemy-damage-taken (Peach Tree / Silver Pendant) is the workbook's `AGG_ENEMY_DMG_TAKEN` inside Summary's `R_MONSTER_DMG_BONUS`, i.e. added to BOTH the Boss and the Normal Monster Damage terms AND to the companion's `boss_pct` / `norm_pct` (the engine hook `artifact_monster_dmg_bonus` now carries it, plus any manual value); Ring of Cycles' threshold = Inputs + Dark Sight's Crit Rate; Soul Contract through `fight.cd_extra_pct` (every row, the buffs, Phase Dash's stun entry); Horn Flute's uptime from the stub run WITH Phase Dash; Shadow Partner divided out of the companion unit with or without artifacts.  No second (Hexagon-weighted) engine run exists in this kit.

## Bishop: Companions + Status Effect Damage / KO timeline (2026-11-17 port from FP-Mage / Hero / Paladin / Dark Knight / Buccaneer / Corsair / Marksman / Night Lord / Shadower; Ice-Lightning-Mage is the mage template)

Same feature set and rules as the sections above: Inputs `STATUS_EFFECT_DAMAGE %` (row 23: Bishop's Inputs sit one row below Ice-Lightning-Mage's because of the Defense / Defense % rows; self-detecting row-shift migration of Min Damage .. Skill Level All), `Companion` (row 52; rows 48-51 are the artifact slots) + live
`Companion Summoning Time Increase %`, sheets `Timeline` / `CompanionKits` / `Companion` / `CompanionsInput`, Sensitivity rows for both stats, the Companion Comparison and summoning-time tables (weighted-ratio form), the Horn Flute rewire (`Companion!horn_uptime`) and the exported host values for `potential_cubes_ev.py`
(+ `companion_kits.py` / `companion_python_model.py` / `potential_cubes_ev.py` copies in `Bishop/`).  With Companion = None, Status Effect Damage = 0 and a content where the engine stays off (Chapter Hunt, PvP, EXP / Equipment Dungeon, Hero Dungeon) the totals are identical to the pre-port workbook (python mirror of the pre-port
and new verify scripts, and the pre-port workbook itself for Chapter Hunt, with the Breakthrough column's real inputs copied into every content, Lv200: Chapter Hunt 181121820879735808, PvP 774291400821208.75, EXP / Equipment Dungeon 198922631530076736, Hero Dungeon 123111009975030528).  Bishop-specific wiring:
- **Engine buffs** (`STATUS_BUFFS`): **Magic Guard, Heal, Bless and Holy Magic Shell** as Attack% buffs (`atk`: one additive bucket with the artifacts, as in Summary's `R_AVGBUFF`) and **Advanced Blessing** (flat) and **Infinity** (the 15 s -> 25 s ramp, `Calc!F` = the x64/45 time-average, normalised by the engine) as Final Damage buffs (`ramp` kind).  Summary's averaged model multiplies the
  two Final Damage buffs ((1+a)(1+b)) while the engine adds them, so Advanced Blessing's strip effect is scaled by `1 + Infinity's steady-state average F x MIN(1, duration/cooldown)/100` (`fd_cross_scale`, the mean-field cross term of Shadower's Smokescreen; the verify script mirrors it).  With the engine on `Summary!R_AVGBUFF` = the strip's mean buff bucket and the buff-casting
  start-up delay is 0.  NOT player-timed, they stay averaged (also in the companion snapshot where they are not a cast): **Nimble Feet** (Attack Speed), **Holy Fountain**'s Lv68 Boss Monster Damage, **Holy Symbol** (Normal Monster Damage + the Lv90 Damage Boost), **Divine Protection** (Defense -> Invincible's INT), **Triumph Feather**'s angel-power window (18 s cooldown, 10 s) and Blood of the Divine / Element Amplification / Arcane Aim (passives).
- **Engine groups**: Angel Ray (burst, fixed player-stun schedule) + **Angel Ray - Boss Monster Damage** (Lv122 proc: shares Angel Ray's cooldown and fires on every cast, no action slot; gated on its own unlock) in one group, Genesis (burst), Bahamut (`dot`: 30 s summon with 4 s ticks, hits from the engine's effective cast count, `STATUS_FS_KEYS`).  Uniform rows (phi_unif): Big Bang (the basic attack) and Triumph Feather
  (a two-stage chance proc triggered by every attack: its trigger rates already read the engine-aware cast counts through `Summary!R_CASTRATE` / `Calc!R`).  Boss / normal DPS columns are `S` / `U` (as Ice-Lightning-Mage), timing factors `W`/`X`, per-cast boss damage `Y` (Big Bang's `Y` is 0 while it is locked below Lv100: there is no basic attack for a cast to give up).  No averaged-model cast-count twin was needed: nothing that feeds the engine reads a cast count
  (buff F / cooldowns / weights read levels, CDR and `Calc!N`), and `cyc.py` reports 0 cyclic components.
- **Player stun**: **Angel Ray** (Lv103 unlock; 1 s stun, cooldown 17 s, no Reuse mastery; `STATUS_PLAYER_STUN`, host `pst` in the main / block / exported hosts, `pl_stun` in the engine host) as a fixed on-cooldown stun group.  The engine is ON in every fixed-length single-target content from Lv103 (World Boss, Enhancement Dungeon, Chapter Boss, Weapon Dungeon; World Boss / Enhancement
  Dungeon at any level for their KO phases), Breakthrough's boss phase is lengthened by the stuns (also with Companion = None), Hero Dungeon is timed (no extension).  Fixed means Angel Ray no longer waits for a KO window (World Boss Lv200, Companion None, S = 0: Angel Ray / its boss proc 5 casts at t = 0 / 17 / 34 / 51 / 68 s, Genesis 4, Bahamut 2, Magic Guard 4, Heal 5, Bless 4, Holy Magic Shell 3, Advanced Blessing 3, Infinity 3).
- **Engine-on contents change by design** (test inputs, Companion None, S = 0, vs the pre-port workbook): World Boss 4.368e15 -> 5.690e15 (+30.3%) and Enhancement Dungeon 22.10e15 -> 27.62e15 (+25.0%) (KO phases: the optimal player), Chapter Boss +3.3% and Weapon Dungeon +2.6% (no start-up delay: buffs are cast when they pay, optimal placement), Breakthrough +0.6% (Angel Ray's stun extension: 92.908e15 -> 93.470e15).
  Lv102 -> Lv103 (Angel Ray's unlock) lowers the Breakthrough total by 1.0% before the port and 0.6% after it: Angel Ray's single-target casts replace Big Bang actions that hit 6 targets in the normal-monster phase (a pre-existing action-slot effect, not a port artifact; the stun extension gives back +0.4%).  Shared-engine approximation (all classes): different skills may be cast in the same one-second bin.
- **Companion host**: `unit` = Big Bang's `N/F`; `avgbuff` = `R_AVGBUFF` (engine on: the strip's mean buff bucket); the snapshot has the CAST buffs fully up (Magic Guard + Heal + Bless + Holy Magic Shell in the additive Attack% bucket, x Advanced Blessing x Infinity as the multiplicative Final Damage factor `fdpart`; `k1` / `fdpart` exported for the cube script) and the proc / duty-cycle effects at their averages;
  `attack_bucket_avg` = the four Attack% buffs' F x uptime + artifacts.  **Joint Damage bucket**: Bishop's `Calc!K` keeps Inputs Damage%, Holy Symbol's Damage Boost, the Hexagon Necklace and the artifacts' enemy-damage-taken bonuses (Peach Tree / Silver Pendant) in ONE additive `(1 + (...)/100)` factor, so the Hexagon snapshot ratio (`agg_damage_avg`) and a companion's damage-taken debuff (`taken_bucket`) are both taken
  against that joint bucket (not FP-Mage's separate Elemental Decrease factor, not the boss / normal bucket).  `boss_pct` includes Holy Fountain's Boss Monster Damage, `norm_pct` Holy Symbol's Normal Monster Damage; `cd_total` includes Blood of the Divine's Crit Damage; Big Bang's own Boss Monster Damage mastery is a skill mastery and is not part of `boss_pct`.
- **Sensitivity strips**: `STATUS_REBUILD_KEYS` = FP-Mage's list (CDR, Buff Duration, Shamaness Marble, Status Effect Damage, Summoning Time, Hexagon equip) plus the Attack%-artifact toggles (Charm, Old Music Box, Secret Map, Reindeer's Spear, Alliance Badge, Bottle of Emotion) and `skill_lvl_1st/2nd/3rd/4th/all` (the six buffs' F).  New block-local cell `s_bucket` (calc_end + 20: the block's averaged Attack% bucket; inlining it pushed the timing-factor formula to
  10780 characters), `BLOCK_HEIGHT = LAST_ROW + 22`.  Rebuilding blocks read the main sheet's `s_0` / `W_0` for the stun vector; the Summoning-Time, Hexagon Necklace, Horn Flute and Skill Cooldown Decrease (+ its 10 milestone blocks) blocks run the full 3-candidate companion search (guide "Gap found by the Buccaneer port", items 1-4, from the start).  Longest formulas: Timeline strip 7606, Sensitivity 7225, Companion 6376, Calc 4292 (cap 8192).
- **Not modelled**: the player's other crowd control; Nimble Feet / Holy Fountain / Holy Symbol / Divine Protection / Triumph Feather's angel power / Heal's and Bless' HP-gated halves as time-resolved effects; Angel Ray's Boss Monster Damage proc is cast with Angel Ray (its own game cooldown is not separate).  `skill_lvl_2nd` / `_3rd` / `_all` Sensitivity blocks include the passive "Magic Critical pattern" deltas (and `flat_int` / `int_pct` / `luk` the main-stat flat-Attack channel, CLAUDE.md bug 7) that the main sheet never implements, so against a re-evaluated main sheet those read slightly high BY DESIGN
  (not tested against the main sheet for that reason; `skill_lvl_1st` / `_4th` equal it exactly).  The shared `companion_python_model.run` returns no `stun_vector` key when there is no companion and no active player stun; the verify script treats that as an all-zero vector (shared-module quirk, not changed).
- **Verification** (2026-11-17, artifacts cleared, Sensitivity stripped, the user's Breakthrough inputs copied into every content, Lv200 unless stated, COMP_LIGHT builds for the matrix, the final FULL build for Chapter Hunt and the full-workbook checks): `verify_bishop_workbook.py` (the existing flat script, extended with the engine + the companion mirror) == workbook for Chapter Boss (None; Bow Master; None with BDI +60% / CDR 5; Blaze Wizard Lv12 at Lv118; None at Lv102 / Lv103), World Boss
  (Blaze Wizard S = 30, None, Wind Archer Lv10 with BDI +40% / CDR 3 / Summoning Time +20%, None with BDI +100%, Blaze Wizard with CDR 8), Enhancement Dungeon (Blaze Wizard; Wind Archer Lv7 with BDI +40% / CDR 3 at Lv121; None at Lv138), Breakthrough (None = the Angel Ray extension, Blaze Wizard, Bow Master, Wind Archer with Summoning Time +20% at chapter 29-3, Blaze Wizard at 39-1 with "More Boss", None at 40-2; Lv 50 / 62 / 63 / 99 / 100 / 102 / 103 / 104 / 115 / 138 with no companion), Hero Dungeon (None, Blaze Wizard,
  Wind Archer Lv7 with Summoning Time +20%), Chapter Hunt (None, Wind Archer with max enemies 3, Blaze Wizard with CDR 6 / BDI +100%), EXP / Equipment / Weapon Dungeon, PvP with Blaze Wizard (stunning), Bow Master (non-stunning) and None, and World Boss with no companion at Lv 14 / 15 / 21 / 22 / 34 / 35 / 38 / 39 / 40 / 44 / 49 / 54 / 60 / 63 / 66 / 68 / 69 / 72 / 73 / 75 / 78 / 90 / 94 / 98 / 100 / 102-108 / 110 / 111 / 113 / 115 / 117 / 118 / 120 / 122 / 124 / 126 / 128 / 130 / 134 / 136 / 138 and with Blaze Wizard at Lv 102 / 103 / 122 / 138: about 100 runs, all OK.
  `cyc.py` 0 cyclic components; zero error cells on the FULL workbook (World Boss and Breakthrough, Sensitivity stripped, Hexagon + Charm + Horn Flute + Bottle of Emotion equipped, Blaze Wizard Lv10, S = 30); the Python mirror rebuilt from the exported host values reproduces the sheet's companion DPS and its b0+20 grid column (World Boss 2.2e-16 / 4.4e-16, Breakthrough 2.2e-16 / 2.2e-16).
  Sensitivity-vs-main (Blaze Wizard Lv10, S = 30, Lv200, Bottle of Emotion + Reindeer's Spear equipped, Sensitivity-SLIMMED COMP_LIGHT copy with only the tested blocks and their strips kept): World Boss `damage`, `status_effect_damage`, `skill_cooldown_decrease`, `companion_summon_time_increase_pct`, `buff_duration_increase_pct`, `attack_pct`, `final_damage`, `skill_lvl_1st`, `skill_lvl_4th`, `crit_rate`, `boss_damage`; Breakthrough `damage`, `status_effect_damage`,
  `skill_cooldown_decrease`, `companion_summon_time_increase_pct`, `buff_duration_increase_pct`, `attack_pct`; Enhancement Dungeon `damage`, `status_effect_damage`, `skill_cooldown_decrease`, `companion_summon_time_increase_pct`; and with Wind Archer Lv7 + Summoning Time +20% (a non-zero candidate-flip case) World Boss CDR / summoning time / `status_effect_damage` / `damage`: ratio 1.00000000.  Hexagon Necklace / Charm of the Undead / Horn Flute equip rows (block total AND the artifact-table DPS gain) == the toggled copy's total delta
  (World Boss, Bottle of Emotion baseline, ratio 1.00000000; gains +8.9e14 / +3.2e14 / +1.2e15 on 1.052e16, i.e. +8.4% / +3.0% / +11.3%).
- **Rebuilt for the companion cast timing rule 2026-11-18** (see Companions -> "Cast timing"; Inputs / ArtifactsInput / PotentialCubes / Equipment Compare unchanged, the Angel Ray player stun keeps its old timing).  Total shifts vs the pre-change workbook (test inputs, Lv200, S = 30, COMP_LIGHT builds, verify script == workbook everywhere): Blaze Wizard Lv10 World Boss -0.15%, Breakthrough -5.69%, Chapter Hunt -0.64%, PvP 0.00%; Wind Archer Lv7 + 20% summoning time World Boss -0.12%, Breakthrough 0.00%, Chapter Hunt 0.00%, PvP -0.87%.  Blaze's 3rd stun cast needs +13.667% summoning time (Breakthrough total +4.1% between +12 and +14).
- **Arwen's Glass Shoes + "no DPS effect" relabelling + Sensitivity fixes (2026-11-20, replayed from FP-Mage; engine port the same day)**: the shoes are a REAL, live Companion Summoning Time Increase (+20% star 0 .. +40% star 5, linear 20/24/28/32/36/40, all user-confirmed 2026-11-19); effective increase = Inputs value + artifact (`companion_summon_time_inc_expr`) in the Companion host, every Sensitivity block, `b0` (artifact added outside the `MAX(0, ...)`) and so the CompanionsInput table / cube script; the equip row is in `STATUS_REBUILD_KEYS`, `COMPANION_FULL_SEARCH_KEYS` and `SUMMON_TIME_KEYS`.  The seven artifacts without a DPS effect are labelled "no DPS effect (reason)" (`ARTIFACT_NO_DPS_EFFECT`; ArtifactsInput has a 15th column "Equip effect in the DPS model").  Inputs / ArtifactsInput / PotentialCubes carried over with 0 diffs (only the Companion Summoning Time Increase label changed); `cyc.py` 0 cyclic components; longest formula 6903 (Sensitivity AF1048; it was 7225 before: the baked-in Final Damage helper cells shortened every K formula), Companion 6054 (cap 8192).  Verified on the Bishop workbook (the 64-case artifact golden set doubles as the equivalence test): Total DPS with shoes star s at Inputs x == without shoes at x + 20..40 bit-for-bit on 10/10 pairs (World Boss Blaze Lv10 star 0 = in20, star 5 = in40, star 5 + in5 = in45 across the 3rd-stun flip, + Bottle / Hexagon / Horn Flute; Breakthrough Wind Archer Lv7 x4; Chapter Hunt x2); Sensitivity equip row == toggled-copy delta 1.00000000 (World Boss, from BOTH directions: % Gain 108.24901447801658 each; Hexagon + Horn Flute + Bottle base 106.76360628859692; Chapter Hunt 108.69768508699458), Summoning-Time stat and damage blocks with the shoes equipped 1.00000000, Breakthrough equip row == time-weighted expected 1.00000000 (its dollar delta differs by design, CLAUDE.md item 9); 0 error cells and cube mirror <= 3e-16 (World Boss, Breakthrough Blaze Lv10; Wind Archer Lv7 5e-10, fractional-window artifact) with shoes + Hexagon + Horn Flute + Bottle equipped.
- **Bishop Sensitivity fixes (2026-11-20; FP-Mage's two fixes replayed per stat)**: (1) strip rebuild set.  Bishop already re-ran its strip for the six buffs' skill levels, CDR, Buff Duration, Status Effect Damage, Summoning Time, Shamaness Marble, Hexagon and the Attack%-artifact toggles; added now: `skill_damage`, `basic_attack_damage`, `boss_damage`, `crit_rate` and the toggles `ring_of_cycles`, `book_of_ancient`, `rainbow_snail_shell`, `candle`, `sayrams_necklace`, `star_rock`.  Why only these: Angel Ray is a fixed on-cooldown cast and Genesis / Bahamut are single-entry groups, so a cast's value is (w - c_slot) x Wt and only the SIGN of w - c_slot (Bahamut's late, window-truncated casts against the Big Bang they replace; Big Bang has its own Boss Mastery) can move the schedule; every stat that scales all damage rows alike (Flat INT, INT %, Defense, Defense %, Damage %, Damage Amp, Final Damage, Min / Max Damage, Crit Damage, Def Pen, Flat ATTACK, ATTACK %, Attack Speed, Normal Damage, Target Increase) cannot.  Engine experiment (`stl.solve` captured for base vs swept inputs, World Boss / Enhancement Dungeon / Chapter Boss, Lv 103-200, stat sets A / B, with and without Blaze): 0 strip moves for those at +1 .. +50, while Skill Damage / Basic Attack Damage / Boss Damage DO flip the schedule at large deltas (123 of 522 runs with deltas up to +1000 / -100 / -200, e.g. Bahamut's first casts at Lv115).  Sens-vs-main (swept Input set to the block's New Value in a Sensitivity-emptied copy; Ring of Cycles + Bottle of Emotion equipped, Lv200, Blaze Wizard Lv10, S = 30): `skill_damage`, `basic_attack_damage`, `boss_damage`, `crit_rate` ratio 1.00000000 in World Boss AND Enhancement Dungeon; `skill_lvl_1st` / `_4th` 1.00000000; `skill_lvl_3rd` 1.00031 = the documented passive "Magic Critical" delta of the 2nd / 3rd / all blocks; Ring of Cycles / Candle / Sayram's Necklace equip rows == toggled-copy delta 1.00000000 (gain and % Gain).  Cost: 10 more strips (Sensitivity 8902 -> 10948 rows with the shoes' strip).  (2) baked-in Final Damage what-ifs (Cursed Doll, Lit Lamp, Clear Spring Water, Soul Pouch, Bottle of Emotion's Attack-Speed-dependent value) are a FACTOR on the whole Final Damage product, `1 + x/100` when adding and `1/(1 + x/100)` when removing, through block-local helper cells (column Z, 3rd / 4th skill row); verified by matched pairs (state k equipped with its Final Damage typed multiplicatively into `Inputs!final_damage`): the block read in state 0 == Total of state 1 and read in state 1 == Total of state 0, identical gain and % Gain from both directions to 4e-16: Cursed Doll 114.0% (with Candle live), Lit Lamp 140.0%, Bottle of Emotion 125.96251205187987% (Attack Speed 84), Clear Spring Water 120.0% (Enhancement Dungeon), Soul Pouch 140.0% (PvP).
- **Soul Contract now also cuts Triumph Feather's 18 s trigger cooldown (2026-11-20, found by the engine port)**: the workbook's Triumph Feather rows (Calc and every Sensitivity block) applied only the flat Skill Cooldown Decrease to the stage-1 cooldown (`tf_cd`, a direct `effective_cooldown_expr` call), not Soul Contract's Chapter-Hunt percentage that every other cooldown carries (CLAUDE.md item 11).  Fixed in both copies; with Soul Contract not equipped (or outside Chapter Hunt) every number is unchanged (2 Calc cells differ in formula, none in value); Chapter Hunt with Soul Contract equipped rises by +7.2% (star 5, Blaze Wizard, Chalice / Charm / Horn Flute), +6.3% (star 3, no companion), +9.8% (Lv100, Reindeer's Spear / Ring of Cycles / Horn Flute).
- **Engine (2026-11-20)**: `engine/classes/bishop.py` models the artifacts (`inputs["artifacts"]`, `artifacts` result block, `schema()["artifacts"]`); `tests/golden/bishop_artifacts_golden.json` / `test_bishop_artifacts.py`: 64 workbook evaluations (every artifact at star 5 in World Boss with Blaze Wizard Lv10, other fight shapes, stars, crit-rate branches, Reindeer def pen 50 / 80 / 99, Lv 99 / 100 / 102 / 103 / 112 / 125 shapes, Angel Ray's stun without a companion, PvP with Defense %, the Glass Shoes equivalence pairs): engine == workbook within rel 1.4e-10 worst case (Breakthrough Wind Archer, fractional summoning window), ~2e-16 typically; 6 equip-toggle deltas and 10 equivalence pairs identical.

## Bishop: Sensitivity in the engine (2026-11-22)

Bishop joined the class-agnostic Sensitivity engine (`engine/sens_specs/bishop.py`, hooks in `engine/classes/bishop.py`; `tests/golden/test_bishop_sensitivity.py`: 11 slimmed-workbook evaluations, 767 values, 0 differences at rel 1e-9).  The three workbook gaps the Dark Knight port found, checked in Bishop's `build_stat_block`:
- **Reindeer's Spear row**: already correct (the K formula reads `def_pen_total_block`, the dose reaches the rows) -> `reindeer_dose_in_rows=True`.  **Shamaness Marble row**: already wired (`bdi_block` adds `shamaness_marble_delta_block`) -> `bdi_toggle_wired=True`.
- **Athena's Gloves row**: GAP present - the block's Actions Per Second read `ib("attack_speed")` without the gloves' direct Attack Speed (`attack_speed_total_block` was defined, used only for the dependent Max Damage).  FIXED in `build_stat_block` (Sensitivity blocks only; main sheets unchanged) -> `athena_as_in_aps=True`.  Verified against a toggled copy: (Total equipped - Total unequipped) / row gain = 1.0000000000000004 (Shamaness 1.0000000000000022, Reindeer removal 1.0).
- **Extra finding, main sheet (fixed)**: Holy Symbol and Divine Protection were missing from `BUFF_ROW_KEYS`, so their cast count (Calc!R) used the fight duration reduced by the buff-casting startup delay instead of the raw fight duration the verify script / engine use (`fight.buff_uptime`).  Latent: it only shows when the cooldown straddles a cast-count boundary (Breakthrough 40 s with Cooldown Decrease 1: Divine Protection 2 casts instead of 3, Defense bonus 31.27 instead of 33.08, every row 0.21% low).  Fixed (two keys; only Calc R12/R13 and the same cells in every Sensitivity block change; identical at the default Inputs).
Reproduced workbook conventions: Ring of Cycles' threshold takes no Magic Critical / High Wisdom delta (live crit rate does); Magic Acceleration's Attack Speed delta only counts while MP Eater (Lv49) is unlocked and joins the bonus side; LUK is not a sweep stat (no sub-stat term); Defense has no flat-Attack channel; in PvP a Defense / Defense % sweep leaves the opponent's Defense (Defense x (1 + (Defense % + Divine Protection)/100) of the baseline) unchanged.

## Marksman: Sensitivity in the engine (2026-11-22; two workbook gaps fixed, one more found and fixed)

`engine/sens_specs/marksman.py` + the `_sens` hooks and `model()` of `engine/classes/marksman.py` (no-ops without `_sens`: `test_marksman.py` 368 bit-exact, `test_marksman_artifacts.py` 67 green; `crit_rate_bonus` is now 0 and the artifact bucket is `art_crit_rate` (the result's `derived.crit_rate_bonus` still reports their sum), `crit_rate_total`, `comp_host`, `summon_time_inc`, `e1` exposed) + `tests/golden/test_marksman_sensitivity.py` (13 slimmed-copy evaluations, 805 values, engine == workbook within rel 1e-9: worst 7.1e-11 on one `units_per_1pct` = 1/(tiny gain), everything else <= ~2e-12; `marksman_sens_cases.py`, `marksman_sensitivity_golden.json`) + `api/tests/test_sensitivity_classes.py`.  The three gaps the Dark Knight port found, checked in Marksman's `build_stat_block` (builder changes are Sensitivity-only: every non-Sensitivity sheet formula-identical, 0 Input / ArtifactsInput / PotentialCubes diffs, `cyc.py` 0 cyclic components, longest formula 7501 (Sensitivity T1565; cap 8192)):
- **Athena Pierce's Old Gloves equip row - Marksman HAD the gap, FIXED**: `s_aps` read `attack_speed_with_delta` (no Athena term); it now reads `attack_speed_total_block` (typed Attack Speed + passive delta + the gloves' direct Attack Speed).  Old row (Lv140 World Boss, stat set S, nothing equipped): +1.270e9 (118.09%); real +1.767e9 (125.16%).  `athena_as_in_aps=True`.
- **Shamaness Marble equip row - Marksman HAD the gap, FIXED (was inert)**: `shamaness_marble_delta_block` was defined and never read, so the row was 0 (+ potential).  `bdi_block` is now `ib(buff_duration_increase_pct) + shamaness_marble_delta_block` (defined after the delta cell; Illusion Step / Sharp Eyes / Nimble Feet uptimes and the strip's buff durations follow it).  Real value +1.219e8 (101.74%).  `bdi_toggle_wired=True`.
- **Reindeer's Spear equip row - already correct**: the K formula reads `def_pen_total_block`.  `reindeer_dose_in_rows=True`.
- **Extra finding (bug 19, fixed)**: Illusion Step's Lv118 x1.375 boost is the Skills-sheet `SkillMasteryBonus%` `5.25 * Calc!E15 / 1000`, which reads the MAIN Calc sheet's own factor: a block sweeping the 4th-job level (4th / All) kept the boost part of Illusion Step's F at the main level's value, so those two rows' Total sat 7e-5 below the true re-run (~2% of the +1-level gain; every damage row alike through the Attack% bucket; found as the only golden difference, at Lv118 Chapter Hunt, Lv140 Enhancement Dungeon and Breakthrough).  The block's F now re-derives it from its own E cell (same device as the Snipe fold fix).  74 Sensitivity F cells changed (28 stat + 36 toggle + 10 CDR blocks).
Verified with toggled copies: the workbook rows of the four baked-in artifacts (golden cases `T/WB140/a` = nothing equipped / typed, `T/WB140/<art>` = that ONE artifact equipped and its stat typed into Inputs; pure boss content) equal Summary Total(equipped) - Total(unequipped) from BOTH directions, ratio 1.0000000000000 (rel <= 4.4e-14): Athena 125.15727875668618% each (adding / removing), Shamaness 101.73637393001631%, Reindeer 128.79592157764947%, Cursed Doll (typed Final Damage inside the Mortal Blow bucket) +805390948.11 each way (the plain factor on the whole product overstated this by ~2.5%).  `test_baked_pairs_golden` re-checks it from the golden.
Marksman-specific semantics reproduced (spec docstring): (1) `baked_fd_form="typed"`: the typed `Inputs!final_damage` shares the additive bucket `(1 + (typed + passive deltas + Mortal Blow / Last Man Standing's 1-enemy half)/100)`, so the baked-in Final Damage artifacts are a factor on the TYPED value and the Final Damage +1% step bumps the full bucket (`mult_extra` -> `model.mortal_blow_bonus`; the table's Current / New include it; the ratio is exactly 1.01); (2) ten passive deltas (`PASSIVE_DELTA_SLOT`): Critical Shot (Crit Rate), Archer Mastery + Crossbow Acceleration (Attack Speed), Physical Training, Crossbow Mastery, Reckless Hunt: Crossbow + Last Man Standing (Final Damage), Crossbow Expert (Skill + Max Damage), Soul Arrow: Crossbow (Attack%, hook `attack_mult_delta`, also in the strip's `A0`, the companion snapshot and the phase ratios), each gated by its own unlock level (Lv118 case: Crossbow Expert 120 / Last Man Standing 125 locked); (3) unlike Hero's, Ring of Cycles' crit-rate threshold in a block DOES include Critical Shot's Crit Rate delta; (4) the strip-rebuild set is the builder's (it lacks skill / basic-attack / boss damage, Crit Rate and the Ring: the builder's reuse-vs-re-solve experiment found those exact for Marksman, and the golden agrees); (5) no Defense stat, "Defense (flat)" prices 0.  Coverage: all 28 stats (the strip-rebuild ones in World Boss AND Enhancement Dungeon), 29 of the toggles (the baked-in ones from both directions), CDR 0.5 / 1 / 2 / 3.5 / 5, both companion tables and the Summoning-Time table (Breakthrough), the Summoning Time 12.9 candidate flip, Soul Contract in Chapter Hunt.  Not covered: PvP (no Defense input).  2-4 min per evaluation (3.5-6.5 GB); the table + CDR case ran 11 min at 13.9 GB (more than the usual 8-block guideline: split it next time), ~40 min for the 13, three of them twice (the Illusion Step fix).

## Corsair: Sensitivity in the engine (2026-11-22; two workbook gaps fixed, Reindeer already correct)

`engine/sens_specs/corsair.py` + the `_sens` hooks and `model()` of `engine/classes/corsair.py` (no-ops without `_sens`: `test_corsair.py` 323 bit-exact, `test_corsair_artifacts.py` 71 green; `crit_rate_bonus` is now 0 and the artifact crit rate is `art_crit_rate` (the result's `derived.crit_rate_bonus` still reports their sum), `crit_rate_total`, `comp_host`, `summon_time_inc`, `e1` and the new `final_damage_all` (= Summary R_FD_ALL: Jolly Roger at the current cast counts + Ahoy Mateys) exposed; hooks incl. `attack_mult_delta` (Infinity Blast) and `crit_damage_delta` (Fullmetal Jacket)) + `tests/golden/test_corsair_sensitivity.py` (12 slimmed-copy evaluations, 823 values, engine == workbook within rel 1e-9: worst 7.1e-11 on one `units_per_1pct`, everything else <= ~5e-12; `corsair_sens_cases.py`, `corsair_sensitivity_golden.json`) + `api/tests/test_sensitivity_classes.py`.  The three gaps the Dark Knight port found, checked in Corsair's `build_stat_block` (builder changes are Sensitivity-only: after ONE full rebuild every non-Sensitivity sheet is formula-identical, 0 Input diffs, longest formula 7020 (Sensitivity T1814; cap 8192; the old workbook's 7030), `cyc.py` 0 cyclic components):
- **Shamaness Marble equip row - Corsair HAD the gap, FIXED (was inert)**: `shamaness_marble_delta_block` was defined and never read (`bdi_block = ib("buff_duration_increase_pct")`), so the row was 0 (+ potential).  Corsair also reads Buff Duration Increase in places beyond `bdi_block` (the crew windows of Scurvy Summons / All Aboard are Skills-sheet formulas re-derived through `crew_window_expr(ib)`), so the block's `ib("buff_duration_increase_pct")` itself now returns a block-local helper cell (`$U${row_header+5}` = swept value + `shamaness_marble_delta_block`; a cell, not inline text, keeps the row formulas short): buff uptimes (Nimble Feet, Jolly Roger), Swift Fire's Weaken, Ahoy Mateys' proc, the crew windows and the strip's buff durations all follow the toggle.  Real value (Lv140 World Boss, stat set S, nothing equipped): +2.453% (was +0%).  `bdi_toggle_wired=True`.
- **Athena's Gloves equip row - Corsair HAD the gap, FIXED (two parts, as in Buccaneer)**: (1) `s_aps` read `attack_speed_with_delta` (typed + passive delta, no Athena term, so the row only saw the dependent Max Damage); it now reads `attack_speed_total_block` (Quickdraw divisor, Peach Tree / Silver Pendant, the Nautilus / Majestic trigger rates and the companion snapshot follow).  (2) that direct Attack Speed moves the Quickdraw divisor and with it the cooldowns the timeline strip consumes, so `athena_gloves_equipped` joined `STATUS_REBUILD_KEYS` (own strip; before it the toggle reused the main strip).  Real value at the same state: +28.83% (the engine replaying the old form reads +24.51%).  `athena_as_in_aps=True`.
- **Reindeer's Spear equip row - already correct**: the K formula reads `def_pen_total_block` (rows' defense reduction, the boss-branch correction and the companion).  `reindeer_dose_in_rows=True`.
Verified with toggled copies (golden chain `I/WB140/0..4`: state k has the first k chain artifacts equipped with their baked-in stats typed into the Inputs; World Boss, pure boss): the workbook row of each baked-in artifact read from BOTH directions equals Summary Total(with) - Total(without), ratio 1.000000000000 and identical % Gain to 12 digits: Shamaness Marble 102.4532%, Athena's Gloves 128.8310% (Attack Speed + Max Damage), Reindeer's Spear 132.9417%, Bottle of Emotion 143.1129%, Cursed Doll 110.7625% (typed Final Damage).  `test_baked_chain_golden` re-checks it from the golden.
Corsair-specific semantics reproduced (spec docstring): (1) `baked_fd_form="typed"` through a SHIFT cell: the typed `Inputs!final_damage` sits in the additive bracket `(1 + (typed + Cross Cut delta + Jolly Roger + Ahoy Mateys)/100)` next to the multiplicative artifact bucket, so a baked-in Final Damage artifact is a factor on the TYPED value (the builder writes it as block-local shift cell `U{row_header+4}` that `ib("final_damage")` adds everywhere, incl. the strip's Jolly Roger scale `100/(100 + F0 + rest)`), and the Final Damage +1% step bumps the full bracket (`mult_extra` -> `model.final_damage_all`; Current / New include it; the ratio is exactly 1.01 outside the strip); (2) nine passive deltas (`PASSIVE_DELTA_SLOT`): Shadow Heart (Crit Rate, also in Ring of Cycles' threshold), Quick Motion + Agile Guns (Attack Speed), Gun Mastery (Min Damage), Physical Training + Quickdraw (Basic Attack Damage; Quickdraw is job step 4, unlock 125), Infinity Blast (Attack%, `attack_mult_delta`, also in the strip's `A0`, the companion snapshot and the phase ratios), Fullmetal Jacket (Crit Damage), Cross Cut Blast (Final Damage), each gated by its own unlock level (the Lv74 case: Cross Cut Blast 75 locked, Fullmetal Jacket 72 / Roll of the Dice 74 on); (3) Blackboot Bill (Lv66) stuns with no companion chosen, so the strip and the companion host exist from Lv66 on; (4) no Defense stat, "Defense (flat)" prices 0.  Coverage: all 28 stats (the strip-rebuild ones in World Boss AND Enhancement Dungeon), 27 toggles (the five baked-in ones from both directions), CDR 0.5 / 1 / 2 / 3.5 / 5, both companion tables and the Summoning-Time table (Breakthrough), the Summoning Time 12.9 candidate flip, Soul Contract in Chapter Hunt with Quickdraw, Lv74 gating.  Not covered: PvP (no Defense input), Lv < 66 (no stun).  Runtime: 3.5-6.5 min per evaluation, 5.6-8.6 GB; the CDR case (5 strips + 3 toggles) 6.8 min at 9.7 GB and the table case 16.5 min at 9.6 GB (over the 8 GB guideline: the CDR blocks each carry their own strip; the table case needs the full Companion sheet); 71 min for the 12.
- **Observation, not a Sensitivity issue (model semantics, replicated by engine and workbook)**: in World Boss the Buff Duration Increase row reads about -0.15% per +1 (Nautilus Strike's DPS drops 4.3%, Scurvy Summons / All Aboard 0.14%, everything else rises): cause not investigated (the strip re-solves its cast schedule when a buff / window duration changes).  Engine and workbook block agree to 1e-12 on that row, so it is the model's own behaviour, not a block bug; worth a look when the timeline engine is next reviewed.

## Bowmaster: Sensitivity in the engine (2026-11-22; two workbook gaps fixed, Reindeer already correct)

`engine/sens_specs/bowmaster.py` + the `_sens` hooks and `model()` of `engine/classes/bowmaster.py` (no-ops without `_sens`: `test_bowmaster.py` 324 bit-exact, `test_bowmaster_artifacts.py` 65 green; `crit_rate_bonus` is now 0 and the artifact crit bucket is `art_crit_rate` (the result's `derived.crit_rate_bonus` still reports their sum), `crit_rate_total`, `comp_host`, `summon_time_inc`, `e1` exposed; new hook `def_pen_delta`) + `tests/golden/test_bowmaster_sensitivity.py` (12 slimmed-copy evaluations, 789 values, engine == workbook within rel 1e-9: worst 3.6e-11 on one `units_per_1pct` = 1/(tiny gain), every other value <= ~2e-12; `bowmaster_sens_cases.py`, `bowmaster_sensitivity_golden.json`) + `api/tests/test_sensitivity_classes.py` (Bowmaster is in `registry.SENSITIVITY_CLASSES`).  The three gaps the Dark Knight port found, checked in Bowmaster's `build_stat_block` (builder changes are Sensitivity-only: after ONE full rebuild every non-Sensitivity sheet is formula-identical (0 cell diffs), 0 Input / ArtifactsInput / PotentialCubes diffs, 2542 Sensitivity cells changed, longest formula 7543 unchanged (Sensitivity T1852; cap 8192), `cyc.py` 0 cyclic components):
- **Athena Pierce's Old Gloves equip row - Bowmaster HAD the gap, FIXED**: `s_aps` read `attack_speed_with_delta` (no Athena term; `attack_speed_total_block` was defined and used only for the dependent Max Damage); it now reads `attack_speed_total_block` (typed Attack Speed + passive delta + the gloves' direct Attack Speed what-if).  Old row (Lv140 World Boss, stat set S, nothing equipped): +7.95e8 (118.09%); real +1.02e9 (123.27%).  Keeping the strip reused for this toggle is exact (engine experiment with Peach Tree / Silver Pendant equipped, World Boss and Enhancement Dungeon: reuse == re-solve to 1e-15), so `athena_gloves_equipped` stays out of `STATUS_REBUILD_KEYS`.  `athena_as_in_aps=True`.
- **Shamaness Marble equip row - Bowmaster HAD the gap, FIXED (was inert)**: `shamaness_marble_delta_block` was defined and never read, so the row was 0 (+ potential).  `bdi_block` is now `(ib(buff_duration_increase_pct) + shamaness_marble_delta_block)` (defined after the delta cell; Illusion Step / Sharp Eyes / Nimble Feet uptimes and the strip's buff durations follow it).  Real value +6.8e7 (101.55%).  `bdi_toggle_wired=True`.
- **Reindeer's Spear equip row - already correct**: the K formula reads `def_pen_total_block` (the dose reaches the rows' defense reduction, the boss-branch correction and the companion).  `reindeer_dose_in_rows=True`.
Verified with toggled states (golden chain `T/WB140/a` -> `doll` -> `ath` -> `sham` -> `rei`: every state adds ONE baked-in artifact - equipped AND its stat typed into the Inputs - to the previous one, World Boss, pure boss content; the adding row of the artifact is read in the state without it, the removing row in the state with it, true delta = Summary Total difference of the two states): Cursed Doll adding / true 1.0000000000000002, removing / true 0.9999999999999024 (% Gain 114.0000, typed Final Damage as the bracket factor `((1+(fd+mb)/100)(1+x/100)-1) x 100 - mb`), Athena's Gloves 1.0000000000000002 / 1.0 (123.2684093%), Shamaness Marble 1.0 / 0.9999999999999974 (101.5327841%), Reindeer's Spear 0.9999999999999999 / 0.9999999999999998 (129.8906624%).  `test_baked_pairs_golden` re-checks it from the golden.  (The workbook has only 4 artifact slots, so a 5th equipped artifact is silently dropped by the workbook; the chain therefore carries no live artifact and the case builder asserts <= 4 slots.)
Bowmaster-specific semantics reproduced (spec docstring): (1) `baked_fd_form="factor"`: the baked-in Final Damage artifacts are a factor on the artifact bucket `(1 + agg/100)` (`fd_baked_factor`, helper cells in column U) - i.e. on the whole product, which is also a bump of the bracket `(1 + (typed + Mortal Blow)/100)` by the same factor; the Final Damage +1% step bumps the FULL bracket including Mortal Blow (`mult_extra` -> `model.mortal_blow_bonus`; the table's Current / New include it; the ratio is exactly 1.01); (2) eleven passive deltas (`PASSIVE_DELTA_SLOT`): Critical Shot (Crit Rate, also Ring of Cycles' threshold), Archer Mastery + Bow Acceleration (Attack Speed), Physical Training, Bow Mastery, Reckless Hunt: Bow + Armor Break (Final Damage), Armor Break's Defense Penetration (hook `def_pen_delta`: added to the typed Def Pen BEFORE Reindeer's dose), Bow Expert (Skill + Max Damage), Soul Arrow: Bow (Attack%, hook `attack_mult_delta`, also in the strip's `A0`, the companion snapshot and the phase ratios), each gated by its own unlock level (Lv118 case: Bow Expert 120 / Armor Break 125 locked); (3) Illusion Step's Lv118 boost is re-derived from the block's own `E` (fixed earlier), so the engine's own-level `coeff_pct` is the right model; (4) the strip-rebuild set is the builder's 30 keys; the golden agrees; (5) no Defense stat, "Defense (flat)" prices 0.  Coverage: all 28 stats (the strip-rebuild ones in World Boss AND Enhancement Dungeon; the passive unlock gating at Lv118 Chapter Hunt), 28 of the 29 toggles with a DPS effect (the four baked-in ones from both directions; Book of Ancient / Athena / Bottle / Ring both directions in `S/WB140/b`), CDR 0.5 / 1 / 2 / 3.5 / 5, both companion tables and the Summoning-Time table (Breakthrough), the Summoning Time 12.9 candidate flip, Soul Contract in Chapter Hunt.  Not covered: PvP (Soul Pouch's baked Final Damage is the one toggle with an effect only there).  2.5-4.3 min per 8-block evaluation (4.0-6.4 GB), the companion tables case 11.8 min at 8.0 GB (kept separate from the CDR case, 6.8 min at 5.3 GB), 52 min for the 12.
Note: `Bowmaster/~$Bowmaster-DPS-Calculator.xlsx` (an Excel lock file from 2026-11-17) exists, so the workbook may be open on the user's machine: close it before the next build.

## Paladin: Sensitivity in the engine (2026-11-22; three workbook gaps fixed, one semantic documented)

`engine/sens_specs/paladin.py` + the `_sens` hooks and `model()` of `engine/classes/paladin.py` (no-ops without `_sens`: `test_paladin.py` 295 bit-exact, `test_paladin_artifacts.py` 64 green; `crit_rate_bonus` is now 0 and the artifact bucket is `art_crit_rate`, `crit_rate_total` exposed; new `final_damage_all` = Summary R_FD_ALL) + `tests/golden/test_paladin_sensitivity.py` (12 slimmed-copy evaluations, 824 values, engine == workbook within rel 1e-9, worst 7.1e-11 on one `units_per_1pct`) + `api/tests/test_sensitivity_classes.py`.  The three gaps the Dark Knight port found, checked in Paladin's `build_stat_block` (Paladin HAD all three; builder changes are Sensitivity-only: after ONE full rebuild every other sheet is formula-identical, 0 Input diffs, `cyc.py` 0 cyclic components):
- **Shamaness Marble equip row - FIXED**: `shamaness_marble_delta_block` was defined and never read (row inert).  `bdi_block` now adds it, through a block-local helper cell (column U, 5th skill row: the first version inlined it and pushed the longest Sensitivity formula, T1628, to 8201 > the 8192 cap; with the helper it is 7595): every buff uptime, the weakens' windows and the strip's buff durations follow the toggle.  `bdi_toggle_wired=True`.
- **Athena's Gloves equip row - FIXED**: `s_aps` read `attack_speed_with_delta` (no Athena term); it now reads `attack_speed_total_block` (Actions Per Second, Divine Judgment's 10/APS interval, Peach Tree / Silver Pendant, the startup delay, the companion's `aps`), and `athena_gloves_equipped` joined `STATUS_REBUILD_KEYS` (the direct Attack Speed moves Vessel of Light's rate -> the strip's A0).  `athena_as_in_aps=True`.
- **Reindeer's Spear equip row - FIXED**: the rows' `K` formula read `Inputs!def_pen + delta` instead of `def_pen_total_block`; it now reads the latter.  `reindeer_dose_in_rows=True`.
Verified against toggled copies (chain `I/WB140/*`, World Boss, baked stats typed into the Inputs, adding row in the state without the artifact, removing row in the state with it, true delta = Summary Total difference): Athena's Gloves add/true 1.000000000000000, rem/true 1.000000000000000 (% Gain 132.0140963); Reindeer's Spear 1.0000000000 / 1.0000000000 (129.1853714); Bottle of Emotion (126.1773077) and Cursed Doll (107.1793702, typed Final Damage inside the additive bucket): identical from both directions and == the true delta (rel <= 4e-16).
- **Shamaness Marble is exact EXCEPT for the passive-delta residual** (documented semantic, NOT a wiring gap): the row's add/true is 1.0284 and rem/true 1.0273 (% Gain 104.922 / 104.923 - not direction-invariant).  Cause: Paladin's baked-in passives are time-averaged with Combat Orders' temporary skill-level bonus (3rd job: its own value, 4th job: +18 from Lv104), and a block adds `unlocked x (F of the block's own state - the MAIN sheet's F)` per passive row (Parashock Guard -> Attack% bucket, Paladin Expert -> Skill Damage / Max Damage, Weapon Acceleration / Physical Training / Weapon Mastery); +12% Buff Duration lengthens Combat Orders' uptime, so the block sees a larger Parashock Guard / Paladin Expert value than the toggled copy, which keeps the typed Inputs value.  It is the same mechanism as the documented ~1.6e-4 Breakthrough Cooldown Decrease / ~4.5e-5 Buff Duration residual (above), and any toggle / sweep that moves Combat Orders' uptime or schedule has it (Cooldown Decrease, Buff Duration, Shamaness Marble, Soul Contract's cooldown cut, Hexagon Necklace's stacks through Combat Orders' own engine run).  Proof that it is the ONLY difference: the engine with `passive_deltas_in_model=False` (no passive delta in blocks) gives add/true and rem/true 0.999999999999996 / 0.999999999999997 for Shamaness (`test_toggle_direction_invariance`, `_no_passive_residual`).  Whether the block or the typed copy is "right" is a modelling choice (in game the passives' level does follow Combat Orders); it was left as documented, 2.8% of that one row's gain.
Paladin-specific block semantics reproduced (spec docstring): (1) `baked_fd_form="typed"`: the typed `Inputs!final_damage` shares the additive bucket `(1 + (typed + Divine Shield + Guardian + Divine Blessing + Greater Vessel)/100)` (Guardian / Divine Blessing in the strip's own bucket while it is on), so the baked-in Final Damage artifacts are a factor on the TYPED value (also in the strip's `fd_scale` and the companion snapshot) and the Final Damage +1% step bumps the full bucket (`mult_extra` -> `model.final_damage_all`: Current / New include it; exactly 1.01 without strip and companion); (2) **passive deltas in the MODEL** (`SensSpec.passive_deltas_in_model`, new): the class computes `passive_values` at its own state and every block receives the main model's as `_sens["passive_ref"]`, because the delta moves with the block's own Combat Orders uptime and not only with swept skill levels (2nd-job rows are known before Combat Orders' uptime, the 3rd / 4th-job rows after; a block that reuses the main strip reads the main strip's Combat Orders cast count, like the workbook's R column); each row is gated by its own unlock level (Lv118 case: Paladin Expert 120 locked); (3) the CDR milestone blocks, the Summoning-Time / companion blocks and the Breakthrough Cooldown Decrease residual are reproduced to rel 1e-9.  Coverage: all 28 stats (strip-rebuild stats in World Boss AND Enhancement Dungeon, Cooldown Decrease / Buff Duration also in Chapter Hunt, Breakthrough and World Boss), 27 toggles (the 5 baked-in ones from both directions; Hexagon / Horn Flute / Glass Shoes, Soul Contract in Chapter Hunt, Ring of Cycles, Book of Ancient, Bottle, Reindeer, Cursed Doll live), CDR 0.5 / 1 / 2 / 3.5 / 5, both companion tables and the Summoning-Time table (Breakthrough), the Summoning Time 12.9 candidate flip, Lv118 passive gating.  Not covered: PvP (Paladin has no Defense % input), Lv200.  3-14.5 min per evaluation (peak 5-9.3 GB; the companion-table case 13.2 GB, 14.5 min: split it next time), 72 min in total, run one at a time.


## Shadower: Sensitivity in the engine (2026-11-23; two workbook gaps fixed, Reindeer already correct; LEAN golden)

`engine/sens_specs/shadower.py` + the `_sens` hooks and `model()` of `engine/classes/shadower.py` (no-ops without `_sens`: `test_shadower.py` 391 bit-exact, `test_shadower_artifacts.py` 75 green; `crit_rate_bonus` stays Dark Sight's live Crit Rate, the artifact crit rate is `art_crit_rate`, `crit_rate_total`, `comp_host`, `summon_time_inc`, `e1` exposed) + `tests/golden/test_shadower_sensitivity.py` (7 slimmed-copy evaluations, 599 values, engine == workbook within rel 1e-9: worst 7.1e-11 on one `units_per_1pct` = 1/(tiny gain), every other value <= ~2e-12; `shadower_sens_cases.py`, `shadower_sensitivity_golden.json`) + `api/tests/test_sensitivity_classes.py` (Shadower is in `registry.SENSITIVITY_CLASSES`).  The user chose a LEANER golden than the earlier classes (7 evaluations instead of 12, 6.9-7.9 GB each except the Breakthrough tables case, 11.5 GB; the Breakthrough case's 6284 s were swapping on a loaded machine, ~5 min otherwise); the test Inputs are the golden `STATS_S` values, the user's committed Inputs were not touched (0 Input / ArtifactsInput / PotentialCubes diffs after the rebuild).  Static scan of `build_stat_block` first (no workbook evaluation), then ONE full rebuild (every non-Sensitivity sheet formula-identical, 0 Input diffs, 685 Sensitivity cells changed, longest formula 7481 unchanged (Sensitivity T1845; cap 8192), `cyc.py` 0 cyclic components):
- **Athena Pierce's Old Gloves equip row - Shadower HAD the gap, FIXED**: `s_aps` read `attack_speed_with_delta` (typed + passive delta, no Athena term; the unused variable is removed); it now reads `attack_speed_total_block` (Actions Per Second, Meso / Blood Money stacks, Peach Tree / Silver Pendant, the startup delay, Meso Mastery's `1-exp(-0.75 x APS x 5)` in the strip's `A0`, the companion's `aps`).  `athena_gloves_equipped` was ALREADY in `STATUS_REBUILD_KEYS` (the strip re-solves).  Real value (Lv140 World Boss, stat set S, state with Shamaness typed): +4.357e9 (129.279%); the old form read +3.648e9 (124.514%).  `athena_as_in_aps=True`.
- **Shamaness Marble equip row - Shadower HAD the gap, FIXED (was inert)**: `shamaness_marble_delta_block` was defined (after `bdi_block`) and never read, so the row was 0 (+ potential).  `bdi_block` now is a block-local helper cell (column U, 6th row of the block: swept value + the toggle's own delta; a cell, not inline text, keeps the uptime / strip formulas under the 8192 cap - Paladin's inline first version hit 8201); every consumer reads `bdi_block` (`buff_uptime_block`, `fd_cross_scale` and the strip's buff durations, `status_engine_host`), nothing in the block calls `ib("buff_duration_increase_pct")` directly (checked).  Real value (state 0): +3.426e8 (102.356%, was 0).  `bdi_toggle_wired=True`.
- **Reindeer's Spear equip row - already correct**: the K formula reads `def_pen_total_block` (rows' defense reduction, boss-branch correction and companion).  `reindeer_dose_in_rows=True`.
- **Bug-19 scan (Skills-sheet formulas reading main-sheet cells)**: clean - the only live reads are `IB("level")` (never swept) and Cruel Stab's `6 + basic_attack_target_increase`, which the block replaces by its own `cruel_stab_targets_expr`.  **Soul Contract**: two real cooldown call sites exist (main Calc, Sensitivity block, both multiply `(1 - soul_contract_pct/100)`); the buff uptimes / strip cooldowns read the rows' own `Q` (`1/Q`), so every use follows.
Verified with toggled states (golden chain `I/WB140/0..3`: state k has the first k chain artifacts equipped with their baked-in stats typed into the Inputs; World Boss, pure boss content; the adding row is read in the state without the artifact, the removing row in the state with it, true delta = Summary Total difference): adding / true, removing / true and % Gain: Shamaness Marble 0.9999999999999982 / 0.9999999999999979 (102.3561428190), Athena's Gloves 1.000000000000001 / 0.9999999999999998 (129.2789916653), Reindeer's Spear 1.0000000000000002 / 0.9999999999999999 (130.0050112606); identical % Gain from both directions to 2e-16.  `test_baked_chain_golden` re-checks it from the golden.  Bottle of Emotion and Cursed Doll (typed Final Damage as a factor on the artifact bucket) are read adding in state 3 and removing in the Enhancement Dungeon case (slot equipped, nothing typed: engine == workbook); their toggled-copy equality and the live artifacts' (Hexagon, Candle, Secret Map, Alliance Badge, Charm, Old Music Box, Ring of Cycles), Book of Ancient's, Star Rock's and Lit Lamp's are ENGINE-ONLY (`test_toggle_direction_invariance`: adding row == compute() Total difference == removing row, rel 1e-9, % Gain 1e-11) - a fifth / sixth chain state per artifact was outside the lean budget.
Shadower-specific semantics reproduced (spec docstring): (1) `baked_fd_form="factor"`: the typed `Inputs!final_damage` is its OWN factor in K (`(1 + (typed + passive deltas)/100) x (1 + artifact bucket/100)`, Into Darkness / Smokescreen separate), the baked-in Final Damage artifacts are a factor on the artifact bucket (`fd_baked_factor`, helper cells in column U; column Z is `CastsInFight(averaged)`), so there is no `mult_extra` and the Final Damage +1% step is exactly x1.01 (also with the strip on: it never reads the typed value); (2) ten passive deltas (`PASSIVE_DELTA_SLOT`): Agile Daggers (Attack Speed), Channel Karma (Attack%, hook `attack_mult_delta`: the additive bucket next to Dark Sight (Attack) / Steal / Meso Mastery, the strip's `A0`, the companion's k1 and the phase ratios), Dagger Mastery (Min Damage), Critical Edge (Crit Rate - also Ring of Cycles' threshold - AND Crit Damage), Physical Training, Dagger Expert (Skill + Max Damage), Shadower Instinct + Shadow Shifter's self Final Damage (additive with each other; Shadow Shifter's Lv118 mastery +10 cancels in the delta), each gated by its own unlock level (the Lv118 case: Dagger Expert 120 / Shadower Instinct 125 locked); (3) `incoming_hit_rate` (Shadow Shifter, +1 hit/s) is the class's own 29th sweep stat; (4) Dark Sight (Crit) is the live crit-rate source (`model.crit_rate_bonus`): Ring of Cycles' threshold and Book of Ancient's removal reference include it; (5) no Defense stat, "Defense (flat)" prices 0; (6) the strip-rebuild set is the builder's 30 keys (the spec == builder test checks it).  Coverage: all 29 stats (the strip-rebuild ones in World Boss AND Enhancement Dungeon; Cooldown Decrease / Buff Duration in World Boss, Cooldown Decrease in Breakthrough), 16 of the 29 artifact toggles with a DPS effect (7 of the 36 have none) (the three chain artifacts from both directions, Bottle / Cursed Doll / Clear Spring Water in both directions across cases, Book of Ancient, Ring of Cycles, Hexagon, Candle, Star Rock, Charm, Lit Lamp, Arwen's Glass Shoes, Horn Flute, Soul Contract in Chapter Hunt), CDR 1 / 3.5 / 5 (Chapter Hunt), both companion tables and the Summoning-Time table (Breakthrough, level-varied companions, Summoning Time 12.9 candidate flip), Lv118 passive gating.  Not covered by a workbook evaluation (lean budget): PvP (Soul Pouch's baked Final Damage is the one toggle with an effect only there), the other 13 toggles with an effect (Contract of Darkness, Rainbow Snail Shell, Chalice, Old Music Box, Silver Pendant, Fire Flower, Soul Pouch, Icy Soul Rock, Flaming Lava, Sayram's Necklace, Peach Tree, Alliance Badge, Secret Map: live artifacts whose engine rows are checked engine-only for direction invariance where listed above, and whose equipped-state effects are in the artifact golden), CDR 0.5 / 2 and the other CDR milestones (same block code), Lv200.
- **Test-data note (not a bug)**: the committed workbook's PotentialCubes sheet (the user's data, left in the scratch copy) lists a boots line "Companion Summoning Time Increase % 12", so the Summoning-Time table's b0 = Inputs value - 12; the Breakthrough case carries `companion_potential_lines_pct = 12` (`test_potential_lines_are_the_workbooks` re-reads the workbook).  Without it the table rows between x = 5 and 12 differ (boss-phase factor 1.0 vs 1.17), which looked like a bug until the lines were found.

## Night Lord: Sensitivity in the engine (2026-11-23; one workbook gap fixed, lean golden)

`engine/sens_specs/night_lord.py` + the `_sens` hooks and `model()` of `engine/classes/night_lord.py` (no-ops without `_sens`: `test_night_lord.py` 380 bit-exact, `test_night_lord_artifacts.py` 73 green; new attributes `e1`, `comp_host`, `summon_time_inc`, `crit_rate_total` (= Inputs + Critical Throw Lv47 + Dark Sight (Crit Rate) average + the artifact bucket, CLAUDE.md item 13); hooks incl. `boss_damage_delta` (Enveloping Darkness), `attack_mult_delta` (Expert Throwing Star Handling: joins the additive Attack% bucket, the strip's A0, the companion snapshot) and `crit_damage_delta` (Critical Throw)) + `tests/golden/test_night_lord_sensitivity.py` (10 slimmed-copy evaluations, 699 values, engine == workbook within rel 1e-9: worst 7.1e-11 on one `units_per_1pct` (a 1/(% gain - 100) quotient), everything else <= 2.7e-11; `night_lord_sens_cases.py`, `night_lord_sensitivity_golden.json`) + `api/tests/test_sensitivity_classes.py`.  The lean golden is a USER BUDGET decision (Corsair has 12 evaluations): the World Boss chain `I/WB140/0..4` (+ the 3b branch) carries all 29 stats once (strip-rebuild stats also in `S/ED140`), 19 toggles, the CDR subset / Soul Contract are in the Lv118 Chapter Hunt case, the tables have a case of their own (`C/BT140`: 11.75 GB resident, over the 8 GB budget; the Companion Comparison + Summoning-Time tables cannot be split; the first version had them next to 8 blocks: 10.5 GB and 6449 s, split).
Static scan of `build_stat_block` for the known patterns (no workbook evaluation first; builder changes are Sensitivity-only: after ONE full rebuild every non-Sensitivity sheet is formula-identical, 0 Input / ArtifactsInput / CompanionsInput / PotentialCubes diffs, longest formula 7519 (Sensitivity T1845, unchanged; cap 8192), `cyc.py` 0 cyclic components):
- **Shamaness Marble equip row - Night Lord HAD the gap, FIXED (was inert)**: `shamaness_marble_delta_block` was defined and never read (`bdi_block = ib("buff_duration_increase_pct")`), so the row was 0 (+ potential).  Every Buff Duration reader of the block goes through `bdi_block` (the buff uptimes, Alchemic Adrenaline's window, the strip's buff durations; no Skills-sheet formula reads the Input), so `bdi_block` now adds a block-local helper cell (`U{row_header+8}` = the what-if delta).  Real value at the golden state (Lv140 World Boss, nothing equipped): +3.17% (was +0%).  `bdi_toggle_wired=True`.
- **Athena's Gloves equip row - already correct**: `s_aps_pre` and `s_aps` read `attack_speed_total_block` (typed + passive delta + direct Attack Speed), so Alchemic Adrenaline's accumulate time, Peach Tree / Silver Pendant, the cast rate and the companion follow.  NOT in `STATUS_REBUILD_KEYS` and it does not need to be: unlike Corsair (Quickdraw's attack-speed-scaled cooldown) nothing the timeline strip consumes reads the Actions Per Second (checked: engine block with the strip reused vs re-solved is bit-identical for the toggle in both directions, and for an Attack Speed sweep with Peach Tree equipped).  `athena_as_in_aps=True`.
- **Reindeer's Spear equip row - already correct**: the K formula reads `def_pen_total_block` (rows' defense reduction, the boss-branch correction and the companion).  `reindeer_dose_in_rows=True`.
- **Bug 19 (Skills-sheet formulas reading main cells)**: the only one is Assassin's Mark's `MasteryFinalDamage%` (reads the MAIN `Calc!F` of Night Lord's Mark), already re-pointed by `mastery_final_block_expr` (2026-11-21).  Showdown's `6 + basic_attack_target_increase` Skills cell is not read by the blocks (they use their own `basic_targets_expr` and Calc!S); the other Skills formulas read only the level.
- **Soul Contract**: applied at both real cooldown call sites (main `Calc!Q`, block `Q`), every uptime / the strip / the player-stun entries read `1/Q`: none missing (Chapter Hunt case `S/CH118`, toggled-copy equal).
Night Lord-specific semantics reproduced (spec docstring): (1) `baked_fd_form="factor"`: the baked-in Final Damage artifacts are a factor on the artifact bucket (`fd_baked_factor`); the typed `Inputs!final_damage` + the two passive deltas (Dark Harmony, Shadow Shifter's self buff) is its own bracket, Frailty Curse / Alchemic Adrenaline are separate factors, no live additive source shares the typed bracket (`mult_extra` empty: the +1% step is exactly x1.01); (2) ten passive deltas (`PASSIVE_DELTA_SLOT`), each gated by its unlock level (Lv118 case: Claw Expert 120 / Dark Harmony 125 locked, Shadow Shifter 115 on); (3) Gust Charm's stun (Lv35) exists with no companion chosen, so the strip and the companion host exist from Lv35; (4) `incoming_hit_rate` is a plain +1 stat; (5) no Defense stat in the sweep ("Defense (flat)" prices 0).
Verified with toggled states (golden chain `I/WB140/*`: state k has the first k chain artifacts equipped with their baked-in stats typed into the Inputs; World Boss, pure boss): the workbook row of each baked-in artifact read from BOTH directions equals Summary Total(with) - Total(without), rel diff <= 3.1e-15, identical % Gain to 12 digits: Shamaness Marble 103.1663%, Athena's Gloves 129.6731%, Reindeer's Spear 132.3890%, Bottle of Emotion 146.6864%, Cursed Doll 114.0000%.  `test_baked_chain_golden` re-checks it from the golden.
- **Observation, not changed (reuse semantics, replicated by engine and workbook)**: `attack_speed` is not in `STATUS_REBUILD_KEYS`, but Peach Tree / Silver Pendant (a function of the Actions Per Second) feed the boss bucket the strip weighs its casts with; at the golden state reuse == re-solve to the last bit, so it is only a theoretical approximation.


## Dawn Warrior (engine-native, no workbook)

Dawn Warrior (Cygnus Knight, STR main / DEX sub) is the first class that exists ONLY in the engine / web app: there is no workbook, builder or verify script, so nothing is cross-checked against Excel.  Files:
`engine/data/dawn_warrior.py` (data + one flagged note per row, `ROW_NOTES`), `engine/classes/dawn_warrior.py` (model, built on Hero's), `engine/sens_specs/dawn_warrior.py` (Sensitivity / cubes spec).  The
live site data (`maplestoryidle.info`) has no Dawn Warrior rows: the ONLY source is the user's in-game text (character level 120, skill bonuses +67 / +67 / +81 / +121 = total levels 127 / 157 / 201 / 181).  The independent
real-game check is `tests/golden/test_dawn_warrior_displayed.py`: every displayed number of the 11 active skills, the 16 passives and the cooldowns (51 values) is reproduced EXACTLY by the engine's own coefficient function
`trunc_1dp(base x factor[idx][total level])` (the game truncates to 1 decimal): damage idx 12, basic attack / active buffs idx 21, passives idx 22, Call of Cygnus idx 23; every base is a round number.
The kit is modelled from level 100 up like every other class (the basic attack, Celestial Vision III, is the 4th-job one: unlocked at 100, ABSENT below it exactly like Hero's Raging Blow; Luna Divide is a basic-attack effect, so it starts there too).

**Treated as "already in the stat screen"** (the Inputs come from the in-game stat screen, which contains always-on passives and stat masteries; Hero's "Magic Critical pattern": only their Sensitivity level DELTA is modelled, as `PASSIVE_LEVELS` in the spec):
Soul Speed (Attack Speed 5 + the Lv44 +7 pp mastery), Physical Training (Basic Attack Damage), Sword Mastery (Min Damage Multiplier), Divine Hand (Attack %), Inner Shout (Final Damage), Soul Pledge (Attack % + Crit Damage),
Unpredictable (Basic Attack Damage + Final Damage), Student of the Blade (Skill Damage + Max Damage Multiplier); masteries Main Stat +30, Critical Rate +5 %, Soul of the Guardian's Attack +5 %, Basic Attack Damage +15 %,
Accuracy, Max Damage Multiplier +10 %, Skill Damage +15 %, Basic Attack Target Increase +1 (the `basic_attack_target_increase` input).  Not modelled at all (no DPS mechanic): Soul of the Guardian (Max HP / Defense), Will of Steel
(damage taken / HP recovery), Elemental Harmony's +10 % movement Speed, MP costs (project-wide).  LIVE in the model (conditional / timed / per-skill): Soul Elemental, Soul Blessing, Soul Blessing II / III, Equinox Cycle, Equinox Mastery,
Master of the Sword, Call of Cygnus, Elemental Harmony (Attack Speed), True Sight's and Impaling Rays' damage-taken debuffs, Luna Divide, every damage row and every skill-specific mastery (damage % MULTIPLIES the skill, the Celestial Vision III
chain 10/11/12/13/14/15 is a raw tier sum then one multiplier, the two +10 % Boss Monster Damage tiers are that row's own boss mastery; cooldown masteries cut the BASE cooldown before Skill Cooldown Decrease: Sol Rush 26 x 0.7 - 1.5 = 16.7, shown "(-9.3)").
The stat screen is assumed to be read WITHOUT the timed buffs (Soul Elemental / Equinox Cycle Attack %, Soul Blessing II crit, Soul Blessing III / Master of the Sword Final Damage, Elemental Harmony Attack Speed): they are added as live terms (Hero's Spirit Blade / Enrage convention).

**FLAGGED ASSUMPTIONS** (each is also in the row's `ROW_NOTES`; the user can check each in game):
1. **Master of the Sword's Final Damage applies to LUNA DIVIDE only** (user-confirmed target; shown 327.5 % at total level 181 = 190 x idx 21), as a per-row multiplier `1 + pct/100` (the Maple Hero / Call of Cygnus convention; user-confirmed 2026-11-23: 190 % Final Damage = x2.9).  The Lv118 mastery "boost by 80 %" is read as +80 % OF the boost (x1.8, 589.6 % at level 120), not +80 percentage points; the Lv134 "+8 % Final Damage during Equinox Cycle" is added to the additive Final Damage bucket at its time-average (x Cycle uptime) for every row, Equinox-only rows included (a full-strength bump on those rows would sit outside the typed bucket and make the Final Damage +1 % sweep inexact; it would add ~0.8 % to their damage).
2. **Call of Cygnus** (Cosmic Matter 80 / Cosmic Shower 25 / Sol Rush 30, idx 23) is a per-skill Final Damage multiplier `1 + pct/100`, multiplicative with the Final Damage bucket (like Maple Hero; user-confirmed 2026-11-23), applied to both Cosmic Matter rows, both Sol Rush rows (incl. enhanced) and every Cosmic Shower tick.  Check: Cosmic Matter's real damage in game vs the app's row.
3. **Luna Divide** = one trigger (2 hits) per Celestial Vision III swing while Equinox Cycle is up (the only Basic Attack skill in the model); counted in the BASIC attack damage bucket ("[Basic Attack Effect]"); max targets 5 +2 (Lv49) +2 (Equinox Mastery) +1 (Master of the Sword) = 10; damage 70 x idx 21 x (1 + 40 %) from Lv72 / Lv94.  Equinox-only rows (Luna Divide, Equinox Slash, enhanced Sol Rush) get the Cycle's Attack % and Equinox Mastery's +16 Basic Attack Damage at FULL strength (Luna Divide / Slash / enhanced Sol Rush only exist while the Cycle is up), every other row the time-average.
4. **Equinox Slash** is cast only inside Equinox Cycle: casts per window = floor(window / its own cooldown) + 1 (first cast at the window start; overlapping windows merged; fixed fights counted exactly, steady state `min(1/cd, casts/cycle cooldown)`); cooldown 11 s, -30 % at Lv126 (cuts the base); +3 targets at Lv126.  In the Status/KO timeline it is a UNIFORM row (not an optimiser group), because the optimiser could place it outside the Cycle.
5. **Sol Rush**: the share of casts made during the Cycle (= its uptime) are the enhanced version (430 x2, 8 targets, 1.5 s stun), the rest normal (300 x2, 7 targets, 1 s); the player's Sol Rush stun duration in `PLAYER_STUN` is the same uptime mix.
6. **Cosmic Shower** (280 / tick, 0.3 s, 0.2 s from Lv104, 15 s, ONE random target per tick, so no target-count multiplier): same-target decay -20 % per strike up to 4 times (x0.2 floor).  Boss / PvP: always the same target (1, 0.8, 0.6, 0.4, 0.2, 0.2 ... = 0.2267 average over 75 ticks); normal monsters: the next tick repeats the target with probability 1 / Max Enemies In Range (the cap is the only pack size the app knows; 999 = no decay), window-average factor for every cast (also the truncated last window and the timeline's dot weights).  The window is not extended by Buff Duration Increase.
7. **Impaling Rays' pierce** (1300 x3, 5 s after the cast) exists only on stun-immune enemies = the boss branch (and PvP, which uses the boss branch); normal monsters get no such hit; casts whose pierce would land after the fight ends are not counted; the Lv113 +100 % mastery is assumed to apply to it; the 1.5 s stun is still counted as player stun for Status Effect Damage (project convention: stun-immunity is not modelled).
8. **Impaling Rays - Weaken (Lv138)**: +15 % damage taken on stun-immune enemies for 10 s joins the BOSS-branch monster-damage-taken term additively (uptime = 10 s x (1 + Buff Duration) / effective cooldown); modelled, not left out.
9. **True Sight** debuff (10 x idx 21, 15 s) = additive term of both Boss and Normal Monster Damage buckets.  Outside the Status/KO timeline its uptime is the cooldown uptime; in the timeline (fixed-length fights with the engine on) the optimiser places the casts, valuing each at its own damage PLUS the debuff's estimated benefit (boss damage per second of the other rows at their averaged cast rates x duration x pct / (100 + the boss damage-taken term): an estimate used only for the decision), and the debuff uptime then follows the engine's cast count (regular spacing assumed).
10. **Timed buffs** (Soul Elemental 12 s x1.5 from Lv21, Equinox Cycle 15 s x1.3 from Lv54, Elemental Harmony 15 s) are cast on cooldown from t = 0 and averaged by their uptime (Buff Duration Increase extends them), NOT placed by the timeline optimiser (`STATUS_BUFFS = []`); Soul Blessing II's Crit Rate / Crit Damage and Soul Blessing III's Final Damage are averaged by Soul Elemental's uptime (no correlation between them modelled).  Elemental Harmony (Attack Speed +15 %) is non-scaling because the game shows no level.
11. **Soul Blessing III** (Final Damage 20 x idx 22, +10 pp at Lv130) is gated by character level 125.  **Soul Blessing II**'s +10 pp Critical Damage (Lv82) and **Equinox Cycle**'s +30 % duration / **Soul Elemental**'s +50 % duration are applied as read from the mastery text.
12. **Basic attack below level 100**: absent (Hero's convention; the user supplied only the 4th-job Celestial Vision III).  The Status/KO timeline's "basic attack a cast replaces" is 0 below level 100.
13. **Equip-toggle / Sensitivity**: the passives' level deltas follow Hero's pattern (`attack_mult_delta` is applied to the typed ATTACK %, not to the live bucket); the Final Damage +1 % sweep bumps `final_damage + final_damage_extra` exactly (ratio 1.01 to 1e-14, also with the Status/KO strip on: the strip has no engine-timed buff).
14. **Companion host**: Equinox Mastery's time-averaged Basic Attack Damage is added to the host's basic-attack bucket; the Attack % snapshot has Soul Elemental and Equinox Cycle fully up.
15. **Fixed on-cooldown stun casts (Sol Rush, Impaling Rays) vs KO windows** (same as Hero's Rush): a cooldown cut can move a Sol Rush cast out of a short KO window (Enhancement Dungeon, 25 s fight: Sol Rush's Lv90 cooldown cut moves the 2nd cast from t = 24.5 s inside the final 4.5 s KO window to t = 16.7 s: -10 % total, identical in Hero at its Lv90 Rush cut).

**Verification** (2026-11-23): displayed-value test 51/51; all 10 content types compute; level sweep 1..200 at the default inputs and at a realistic stat set (with and without a companion): no DPS decrease at any unlock / mastery threshold except the one in item 15 (Enhancement Dungeon, level 90); equip-toggle direction invariance for 16 artifacts (World Boss, add-vs-true-delta and both directions <= 8e-15); Final Damage +1 % sweep exactly 101 (Chapter Hunt, World Boss with the strip, Breakthrough, levels 130 and 134); `tests/golden/test_engine_native.py --class dawn_warrior` 8/8; `engine.sensitivity.run` (stats / artifacts / companions / cdr), the cube optimizer (`engine.cubes`) and the API (`/api/classes`, schema, defaults, compute, sensitivity, cubes, equipment-compare) answer.

## Night Walker (engine-native, no workbook, PUBLISHED, scaling confirmed by the user's readings)

Night Walker (Cygnus Knight, LUK main / DEX sub thief) exists ONLY in the engine / web app (no workbook).  It was built with `PUBLISHED = False` and flipped to `PUBLISHED = True` on 2026-11-24, after the user supplied higher-level in-game readings that confirm every growth curve (below); the engine-native snapshot `tests/golden/night_walker_snapshot.json` is now required and the web fixtures include it.  Files:
`engine/data/night_walker.py` (data; `CURVES` = (base, factor index, job step) of every scaled number, `PROVISIONAL` = {} (empty), `CONFIRMED_BY_READINGS` = the curves resolved by the user's readings, `ROW_NOTES`), `engine/classes/night_walker.py` (model, built on Dawn Warrior's with Night Lord's proc rules), `engine/sens_specs/night_walker.py` (Sensitivity / cubes spec),
`tests/golden/test_night_walker_displayed.py`, `data/cygnus/night_walker_ingame.md` (the user's level-1 transcription; screenshots stay in `/Users/yaniv/private/night_walker`).  Registered in `engine/__init__.py` CLASSES, `engine/sens_specs/__init__.py` CLASS_IDS, `api/registry.py` FAMILIES ("Thief").
Sources: the user's LEVEL-1 pop-ups (fresh character, "Lv. 1" everywhere, so the shown values are the BASE values at factor 1.0), his higher-level readings (character level 128, pop-ups "Lv. A + B", total skill level 151 / 219 / 279 / 322 per job tier; 35 values, table in `data/cygnus/night_walker_ingame.md` "Scaling readings") and the live site table (`data/ref_maplestoryidle_info/site_job_skill_impact_all.json`, job `night-walker`: real ratioE3 / factorIndex of the damage lines, the stat operations, ModSkillStat / SetServantSkill operations, cooldowns, durations, unlock levels).
The kit is modelled from level 100 up like every class (the basic attack, Quintuple Star, is 4th job: unlocked at 100 and ABSENT below it).  NOT modelled: Quad Star (3rd-job basic attack, user correction), Lucky Seven, Triple Throw, Shadow Jump, MP costs (project-wide).

**Curves confirmed by the user's readings** (`D.CONFIRMED_BY_READINGS`; displayed = trunc_1dp(base x factor[idx][total level] / 1000), reproduced EXACTLY by `tests/golden/test_night_walker_displayed.py`, which runs in the default extended factor mode: the 4th-job readings are at total level 322 > 300, where the engine continues each linear curve; nothing is provisional any more):
| skill | base (tenths of %) | idx / step | evidence (shown @ total level) |
| --- | --- | --- | --- |
| Quintuple Star | 2900 (290 %) | 21 / 4 | 663.5 % @322 |
| Shadow Spark explosion | 3300 (330 %) | 12 / 2 | 691.3 % @219 (the shuriken line, site-confirmed, 460.9 % @219 with the same idx) |
| Shadow Bat | 360 (36 %) | 21 / 1 | 57.7 % @151 |
| Bat Affinity (bat damage 90 %) | 900 | 21 / 2 | 168.8 % @219 |
| Bat Affinity II explosion | 3000 (300 %) | 21 / 3 | 634.8 % @279 |
| Mark of Darkness | 380 (38 %) | **12** / 1 | 66.6 % @151 (idx 21 would give 60.9 %: the earlier "passive-status DoT" guess was WRONG) |
| Adaptive Darkness (per stack 75 %) | 750 | **12** / 2 | 157.1 % @219 (idx 21 was wrong) |
| Adaptive Darkness II (per stack 145 %) | 1450 | **12** / 3 | 347.2 % @279 (idx 21 was wrong) |
Also reproduced (site-confirmed or non-DPS values, same method): Dark Elemental Attack 16 % @151, Shadow Spark 460.9 % @219, Shadow Double 36.7 % @279 (idx 22 confirmed), Darkness Ascending Attack 52.9 % / HP 7.3 % @279, Shadow Stitch 7438.5 % @322, Dark Evasion FD 45.7 % / damage taken 39.3 % @322, Shadow Momentum 7.3 @279, Call of Cygnus 1082.4 / 1353 @322 (idx 23), Bat Affinity III / Adaptive Darkness III FD 343.2 @322, every stat passive (idx 22) at 219 / 279 / 322, plus the cooldown readings with Skill Cooldown Decrease 3.5 s (Darkness Ascending 36(-14.3) = 36 x 0.3 + 3.5).  Modelled kit NOT covered by readings: Dark Omen has no scaling number.  The pop-ups of Lucky Seven (41.7 % @151), Triple Throw (75 % x 5 targets x 3 @219) and Quad Star (80 -> 169.2 % @279) were also seen: their masteries exist in game, the skills are not modelled.
Site-confirmed (asserted against the site JSON by the displayed-value test, not hand-copied): Shadow Spark 2200 idx 12, Shadow Stitch 28500 idx 12, Dark Elemental Attack 100 idx 21, Darkness Ascending Attack 250 idx 21, Dark Evasion FD 200 idx 21, Elemental Harmony AS 150 non-scaling, Shadow Momentum 40 per stack idx 22, Call of Cygnus (Shadow Bat 1200 / Shadow Spark 1500 on BOTH Spark lines) idx 23, Bat Affinity III FD 1500 idx 21, Adaptive Darkness III FD 1500 idx 21, Shadow Double's 20 % share (SetServantSkill 200, idx 22, step 3; the transcription lists it as non-scaling "20 %", the site table says it scales with factor 22), every sensitivity passive (value / idx 22 / step / unlock level), every unlock level, cooldown and duration used.

**Treated as "already in the stat screen"** (the Inputs come from the in-game stat screen; only their Sensitivity level DELTA is modelled, `PASSIVE_LEVELS`): Agile Throwing (Attack Speed), Physical Training (Basic Attack Damage), Throwing Mastery (Min Damage), Critical Throw (Crit Rate + Crit Damage), Enveloping Darkness (Boss Damage), Spirit Projection (Attack % and its Lv98 mastery Final Damage +5 %), Vitality Siphon (Attack %), Throwing Expert (Skill Damage + Max Damage), Dark Blessing (Final Damage + Defense Penetration); masteries Main Stat +30, Critical Rate +5, Basic Attack Damage +15, Accuracy, Max Damage +10, Skill Damage +15, Basic Attack Target +1 (the `basic_attack_target_increase` input).  No DPS mechanic: Max HP, Darkness Ascending's HP recovery, Dark Evasion's damage-taken reduction, Vitality Siphon's barrier, Elemental Harmony's +10 % Speed.  LIVE (conditional / timed / per-skill): Dark Elemental, Darkness Ascending, Dark Evasion, Elemental Harmony (Attack Speed), Shadow Momentum, Shadow Double, Call of Cygnus, Bat Affinity I-III, Adaptive Darkness I-III, Shadow Bat, Dark Omen, Mark of Darkness (+ Weaken), every damage row and every skill-specific mastery (damage % MULTIPLIES the skill; the Quintuple Star chain 10/11/12/13/14/15 is a raw tier sum then one multiplier; +10 / +10 Boss Damage is that row's boss mastery; cooldown masteries cut the BASE cooldown before Skill Cooldown Decrease: Darkness Ascending 36 x 0.7 at Lv78).

**FLAGGED ASSUMPTIONS** (each is also in `D.ROW_NOTES`; the user can check each in game):
1. **Unlock levels** of Dark Elemental (10) and Shadow Bat (15) are the SITE's `requiredLevel` (the user's grids show no "Lv." label for them: unlocked for the screenshot character).  All other unlock levels were matched to icons by ORDER (user to confirm, esp. Critical Throw 45, Adaptive Darkness II 72 vs Shadow Momentum 74) and agree with the site.
2. **Shadow Bat's roll**: once per ATTACK per ENEMY HIT (q = 1-(1-c)^N, N = 1 on boss / PvP), c = 20 % (+15 pp Lv24), 1 s internal cooldown (rate = X/(1+ICD*X), separately for the boss and normal branch), triggered by Quintuple Star, Shadow Spark and Shadow Stitch (action-costing damage skills; Shadow Spark's explosion, bats and DoT ticks do not roll).  Check: bats per second on a boss.
3. **Bat attack ladder**: a bat attacks 3 times (+1 Bat Affinity Lv40, +2 Lv138 = 6), each at ONE random target, damage 36 % (90 % from Bat Affinity, x1.5 from Lv44) for the first attack and every further attack 25 % LESS THAN THE FIRST down to a floor of 25 %: 1, .75, .5, .25, .25, .25 (linear reading of "decreases by 25% on each attack, up to 25%"; alternatives: multiplicative 25 % per step, or total decrease capped at 25 %).  A bat always completes all its attacks (also with a single enemy).  Counted as Skill Damage with Call of Cygnus' 1 + pct/100.
4. **Bat Affinity II's explosion** (300 %, +50 % Lv73) happens on the FIRST attack of every bat (also Dark Omen's), on 3 targets (+1 Lv94) that include the main target (one hit on a boss, never 0).  Bat Affinity III's Final Damage +150 % (x1.5 boost from Lv118, the same "+50 % of the boost" reading as Dawn's Master of the Sword) is a per-row factor 1 + pct/100; Call of Cygnus does NOT apply to the explosion (site: Shadow Bat only).
5. **Dark Omen** (cooldown 38 s, action-costing): floor(5 s / 0.7 s) = 7 bats per cast (10 at 0.5 s from Lv108), +4 at once from Lv130, each feeding the same bat rows as a proc bat (no roll, no ICD, first attack explodes); the pack window is not extended by Buff Duration Increase.
6. **Mark of Darkness** (the largest approximation): only while Dark Elemental is up (12 s, x1.5 from Lv21, cooldown 28 s) every attack (Quintuple Star / Spark / Stitch) rolls once per enemy hit (20 %, x2 on non-boss from Lv72); a mark lasts 5 s, ticks every 1 s at 38 % -> 75 % (Adaptive Darkness) -> 145 % x1.5 from Lv82 (Adaptive Darkness II), the three levels all growing with idx 12 (confirmed by the user's readings 66.6 / 157.1 / 347.2), x the Adaptive Darkness III Final Damage factor 1 + (150 % x1.5 from Lv122) x idx 21; each mark has its OWN timer; at most 1 / 2 / 3 / 4 marks per enemy (Lv50 / Lv54 / Lv72), marks beyond the cap are lost.  The expected number of live marks is Poisson per Dark Elemental window, integrated in CLOSED FORM (ramp up, plateau, ramp down incl. the 5 s after the buff ends; verified against numeric integration and a Monte-Carlo run); fixed fights use the exact cast count and truncate the last window at the fight end, steady state uses window / effective cooldown, overlapping windows (duration >= cooldown) use the stationary count.  Boss branch = one target; normal branch = every enemy in range with the attacks spread over them (marks per enemy = chance x sum of attack rates x P(enemy hit)); the normal row's targets multiplier is 1 because the tick count already sums over enemies.  Attack rates are constants inside a window (no correlation between the discrete Spark / Stitch casts and the window).  The Attack % / Final Damage buffs act at their time-average on the ticks.  **Check in game**: marks on a boss with Dark Elemental up (stack count, tick damage), and whether marks beyond the cap refresh instead of being lost.
7. **Adaptive Darkness III Weaken** (Lv134): +5 % damage taken while the target carries a mark = 5 x (time share with at least one mark), a separate term in each branch's own Boss / Normal Monster Damage bucket (boss branch: boss time share, normal branch: the average over enemies).  It needs the attack rates, which need the timeline's casts: with the engine on it is first pre-estimated from steady-state rates (for the engine's per-cast weights) and then recomputed from the final rates.
8. **Shadow Double**: the clone adds 20 % x factor 22 (step 3, site SetServantSkill op) of Quintuple Star's damage while up (15 s, x1.3 from Lv104, cooldown 30 s), same lines / targets / boss mastery as the original; only the basic attack is mimicked (the other Basic-Attack-Effect skills are not modelled).  The Lv68 Basic Attack Damage +10 counts at its time-average on Quintuple Star and at FULL strength on the clone's own row (it only exists then).  The clone's hits do NOT roll Shadow Bat / Mark of Darkness (they are servant projectiles) and are NOT mirrored by companions (CLAUDE.md / memory "Shadow Partner mirrors the player only": the companion's unit is the plain Quintuple Star hit; the Basic Attack Damage average is added to the host's `bad`, as Dawn's Equinox Mastery).
9. **Shadow Momentum** (Attack Speed +4 % x factor 22 per stack, 2 s, max 5, +10 Attack while up from Lv90): a "skill activation" = every action-costing cooldown cast (Spark, Stitch, Dark Omen, Dark Elemental, Darkness Ascending, Dark Evasion, Shadow Double, Elemental Harmony; basic attacks do NOT count), at the steady-state rate; each stack lives 2 s on its own (a refresh of the whole state would give fewer stacks), so the live count is Poisson(2 x rate) capped at 5: Attack Speed x mean stacks (~0.55 stacks, ~2 % Attack Speed at default cooldowns), Attack +10 x P(at least one stack).  Check: stack count in game.
10. **Timed buffs** (Dark Elemental Attack 10 x idx 21, Darkness Ascending Attack 25, Dark Evasion Final Damage 20, Shadow Double, Elemental Harmony Attack Speed 15) are cast on cooldown from t = 0 and averaged by their uptime (Buff Duration Increase extends them), NOT placed by the timeline optimiser (`STATUS_BUFFS = []`); the Attack % terms (+ Shadow Momentum's) share ONE additive bucket with the Attack % artifacts, Dark Evasion's Final Damage joins the typed Final Damage bucket additively.  Elemental Harmony (Attack Speed +15 %) is non-scaling because the game shows no level.
11. **Call of Cygnus** (Shadow Bat 120, Shadow Spark 150 on both lines, idx 23) is a per-skill Final Damage multiplier 1 + pct/100 (Maple Hero convention, as Dawn); the SHOWN values are confirmed (1082.4 / 1353 at total level 322, idx 23) but that the game applies them as a damage multiplier 1 + pct/100 (~x11.8 / x14.5 at total level 322) is still the flagged reading: check Shadow Spark's / the bats' real damage in game.
12. **Shadow Spark's stun** (1 s from Lv49) is the player's own stun for the Status Effect Damage / KO timeline (cast on cooldown from t = 0).  Quintuple Star, Shadow Double, the bats, explosions and marks are uniform rows of the timeline; Shadow Spark (both lines) and Shadow Stitch are the optimiser's cast groups.
13. **Quintuple Star** = the only modelled basic attack (Lv100+): 5 lines (6 from Lv136), 6 + Basic Attack Target Increase targets.
14. **Level-sweep decreases** that are understood (all below level 100, none at 100-200): (a) Lv49 in KO contents: the stun turns Shadow Spark into a fixed on-cooldown cast (project convention, as Hero's Rush / Dawn's Sol Rush) instead of optimiser-placed casts inside the KO windows (allow-listed for World Boss without companion in `tests/golden/native_level_allowlist.json`; the same effect shows in Enhancement Dungeon and, in default-stat sets, in other boss content); (b) Lv63 in fixed-length contents with no companion: Shadow Double adds one more startup-delay buff cast, which in a 40 s fight lowers Shadow Spark's exact cast count 3 -> 2 (the project's Buff-Casting Startup Delay discretisation; only the default / weak stat sets, nothing below level 100 matters for the late-game numbers).
15. **Sensitivity**: the passives' level deltas follow Dawn's / Hero's pattern (`attack_mult_delta` is applied to the typed ATTACK %; `def_pen_delta` is Dark Blessing's Defense Penetration, additive onto the typed value before Reindeer's dose); the Final Damage +1 % sweep bumps `final_damage + final_damage_extra` exactly (the engine-native check passes); `SENSITIVITY_CLASSES` in `api/registry.py` was NOT extended (the API asks `engine.sensitivity.supports`, which is true; Dawn Warrior is listed there, Blaze Wizard is not).

**Verification** (2026-11-24): displayed-value test (re-run after the readings): 138 values reproduced (32 level-1 values, 35 higher-level readings at total level 151 / 219 / 279 / 322 through the engine's own level resolution, 8 cooldown readings with Skill Cooldown Decrease 3.5, timings / masteries / buff derived values) + 138 site-table facts equal to the engine data (12 site-confirmed curves, 8 confirmed by the readings, 0 PROVISIONAL, asserted to be exactly the CURVES the site does not cover); engine-native snapshot `tests/golden/night_walker_snapshot.json` created 2026-11-24 (330 cases, 41772 leaves, 1.49 MB, EXTENDED factor mode); `tests/run_all.py --class night_walker` all green (displayed, snapshot, engine-native 8/8, API); [earlier verification of the unpublished build:] `tests/golden/test_engine_native.py --class night_walker` 8/8 (spec, hooks no-ops, API shape, Final Damage +1 % exact, equip-toggle direction invariance of 16 pairs, 36 artifacts finite, 10 content types x 2 stat sets x companion on/off, level sweep 1-200 x 3 fights with the one allow-listed decrease above); extra scratch runs: level sweep 1-200 x 10 contents x {default, late, weak} stats x {no companion, Blaze Wizard Lv10} = 12000 runs finite and non-negative, decreases only at Lv49 / Lv63 (item 14); 400-case random fuzz (random level, content, every stat, 0-5 random artifacts at random stars, random companion) with no NaN / negative / exception; blank (None) inputs in every content type; the generic snapshot matrix (326 cases incl. sensitivity, cube / equipment / potential pricing) computes finite with NO snapshot written; every non-hook Sensitivity row equals a direct re-run with the swept input (World Boss / Chapter Hunt / Chapter Boss, with and without artifacts; only the main-stat channel and the skill-level rows differ, by design); the API (TestClient, `MSI_INCLUDE_UNPUBLISHED=1`) lists `night_walker` and answers schema / defaults / compute / sensitivity (+ meta) / cubes (+ meta) / equipment-compare with 200, and with the variable off the class is hidden (404).

## Blaze Wizard (engine-native, no workbook, PROVISIONAL, UNPUBLISHED)

Blaze Wizard (Cygnus Knight, INT main / LUK sub mage) is the second class that exists ONLY in the engine / web app and the first one whose scaling is NOT known: the user supplied LEVEL-1 pop-ups only (fresh character, "Lv. 1" on every pop-up = the BASE
value, factor 1.0; transcription in `data/cygnus/blaze_wizard_ingame.md`, screenshots outside the repo in `/Users/yaniv/private/Blaze_Wizzard`).  A level-1 reading fixes each base EXACTLY but says nothing about the growth curve, and the site's job-skill-impact
table (`maplestoryidle.info`) has NO Blaze Wizard rows, so **every factor index is a convention** (Dawn Warrior's: burst damage 12; basic attack, additional-damage procs and active buffs / debuffs 21; passives 22; per-skill Final Damage "Call of Cygnus" 23) and
every skill's job step (which tier's skill level scales it) is inferred from its unlock level.  Files: `engine/data/blaze_wizard.py` (`CURVES` = ONE place per skill to edit (base, idx, step), `PROVISIONAL` = the set of unresolved skills, `ROW_NOTES`, `FLAGS`),
`engine/classes/blaze_wizard.py` (model, built on Dawn Warrior's; `PUBLISHED = False`), `engine/sens_specs/blaze_wizard.py` (Sensitivity / cubes spec).  **The class is hidden from the API and the live site (publish gate) and has NO snapshot, NO web fixtures and NO deploy until the
user supplies one higher-level reading per skill** (displayed value + total skill level, like the Dawn Warrior text); then each skill's (base, idx) is resolved uniquely, moved out of `PROVISIONAL`, a second reading is added to `tests/golden/test_blaze_wizard_displayed.py`,
`update_goldens.py --create --class blaze_wizard` writes the snapshot, `PUBLISHED = True`, fixtures, full `tests/run_all.py`, `deploy/redeploy.sh` (CLAUDE.md "Adding an engine-native class" step 6).
The kit is modelled from level 100 up like every other class: Final Orbital Flame (the 4th-job basic attack) unlocks at 100 and is ABSENT below it; no 3rd-job / earlier basic attack is modelled.

**PROVISIONAL curves** (base = the level-1 value in tenths of a percent, the repo's BaseDamage unit; idx = FactorTable column; step = job tier), all 37 of them:
damage idx 12: Flame Vortex 2600 (step 2), Flame Tempest 3000 (3), Cinder Maelstrom 2700 (3), Blazing Extinction Lion 12000 / Fox 16000 (4), Towering Inferno Lion 13500 / Fox 24000 / Fox boss flame strikes 5500 (4);
idx 21: Final Orbital Flame 2900 (4, basic attack), Orbital Explosion 500 (2, additional-damage proc like Luna Divide / Meteor Proc), Flame Elemental Attack 150 (1), Flashfire Attack 120 (2), Fire Lion Normal Monster Damage 200 (2), Flame Fox Boss Monster Damage 200 (2),
Fires of Creation Final Damage 30 (2), Burning Conduit Final Damage 50 (4); idx 22 (passives): Greater Flame Elemental damage 200 (2), Grand Flame Elemental Basic Attack Damage 150 (3), Final Flame Elemental Def Pen 30 / Crit Damage 280 (4), Fire Repulsion Attack 30 (1),
Word of Fire Attack Speed 50 (2), Spell Control Min Damage 150 (2), Brilliant Enlightenment Min 100 / Max 200 (3), Burning Focus Crit Rate 80 / Crit Damage 160 (3), Liberated Magic Final Damage 150 (3), Phoenix Run Final Damage 100 (4), Flame Barrier Attack 50 (4),
Pure Magic Skill Damage 150 / Max Damage 200 (4), Wild Blaze Final Damage 120 (4); idx 23 (Call of Cygnus, 4th job): Flame Vortex 600, Flame Tempest 350, Cinder Maelstrom 300, Orbital Explosion 700.
Mastery values (+70 % Flame Vortex, the +10 pp / +3 pp / +5 pp additions, +9 % weaken, ...) are fixed numbers and do not scale.

**Treated as "already in the stat screen"** (the Inputs come from the in-game stat screen, which contains always-on passives and stat masteries; only their Sensitivity level DELTA is modelled, `PASSIVE_LEVELS` in the spec, Dawn Warrior's pattern):
Fire Repulsion (Attack +3, +5 pp at Lv24; its Defense is not a DPS stat), Word of Fire (Attack Speed +5), Controlled Burn's Lv49 mastery (Attack Speed +7 while MP >= 35 %), Spell Control (Min Damage +15), Brilliant Enlightenment (Min +10 / Max +20), Burning Focus (Crit Rate +8, Crit Damage +16),
Liberated Magic (Final Damage +15 while MP >= 35 %), Phoenix Run (Final Damage +10, x2 from Lv118), Flame Barrier (Attack +5, +10 pp at Lv134), Pure Magic (Skill Damage +15, Max Damage +20), Wild Blaze (Final Damage +12 and Buff Duration +6, the latter is the typed
Buff Duration Increase input), **Fires of Creation's Final Damage +3 (+3 pp at Lv104) while equipped**; masteries Main Stat +30, Critical Rate +5, Basic Attack Damage +15, Accuracy, Max Damage Multiplier +10, Skill Damage +15, Basic Attack Target +1 (Lv64: the `basic_attack_target_increase` input).
Not modelled at all (no DPS mechanic): Fire Repulsion's Defense, Controlled Burn's MP recovery, Liberated Magic's MP cost, Flame Barrier's barrier, Phoenix Run's immunity / Max HP recovery, Elemental Harmony's +10 % movement Speed, MP costs (project-wide), allied players' parts of Burning Conduit (+35 % damage,
+10 % Basic Attack Damage, +15 % Critical Damage at Lv122).  LIVE (conditional / timed / per-skill): Flame Elemental and its Greater / Grand / Final sub-effects, Flashfire, Burning Conduit's own Final Damage, Fires of Creation's Lion / Fox damage terms and Fox Defense Penetration, Call of Cygnus,
Orbital Explosion, Cinder Maelstrom's weaken, Elemental Harmony (Attack Speed), every damage row and every skill-specific mastery (damage % MULTIPLIES the skill, the Final Orbital Flame chain 10/11/12/13/14/15 is a raw tier sum then one multiplier, the two +10 % Boss Monster Damage tiers are its own boss mastery).

**FLAGGED ASSUMPTIONS** (each is also in `ROW_NOTES` / `FLAGS` of the data module; what the user can check in game is in italics):
1. **Every curve is a convention** (above): base exact, idx / step guessed.  *One higher-level reading per skill resolves it (displayed value + total level).*  The convention can be wrong per skill (e.g. Orbital Explosion's 50 % could be idx 12 like a burst, Fires of Creation's +20 % / +3 % idx 22 like a passive, Greater Flame Elemental's damage idx 21).
2. **Unlock levels by icon ORDER**, never confirmed: actives (grid: 3 level-less icons, 30, 35, 50, 60, 60, 63, 69, 100, 103, 110, 115 = 14 icons for the 11 transcribed actives) Flame Vortex 30, Flashfire 35, Fires of Creation 50, Flame Tempest 60, Cinder Maelstrom 63 (the extra 60 / 69 / level-less icons are not DPS skills of this model), Final Orbital Flame 100,
   Blazing Extinction 103, Towering Inferno 110, Burning Conduit 115; passives (none, none, 33, 38, 40, 43, 45, 66, 72, 74, 75, 100, 105, 107, 117, 120, 125) Orbital Explosion 45, Greater Flame Elemental 40, Grand Flame Elemental 74, Final Flame Elemental 105, Call of Cygnus 100.  Job steps follow: Flame Elemental / Fire Repulsion 1st job;
   Flame Vortex, Flashfire, Fires of Creation, Orbital Explosion, Greater Flame Elemental, Word of Fire, Spell Control 2nd; Flame Tempest, Cinder Maelstrom, Grand Flame Elemental, Brilliant Enlightenment, Burning Focus, Liberated Magic 3rd; everything from Lv100 4th.  *Check the Skill window: Cinder Maelstrom 63 vs 69, Flame Tempest 60 (2nd or 3rd job), Fires of Creation 50.*
3. **Stat identity INT main / LUK sub** is assumed (a mage like FP-Mage / Ice-Lightning Mage).  *Check the stat screen.*
4. **Stat-screen classification** (above).  The stat screen is assumed to be read WITHOUT the timed buffs (Flame Elemental, Flashfire, Burning Conduit, Elemental Harmony) and WITHOUT an incarnate effect that depends on the target (Fire Lion's Normal Monster Damage, Flame Fox's Boss Monster Damage / Def Pen) - those are added live;
   everything always-on is assumed to be inside the typed values (Fires of Creation's Final Damage "while equipped" and Liberated Magic's "MP >= 35 %" included: MP is not modelled project-wide, so the condition is assumed to hold).  *If the stat screen does NOT show Fires of Creation's / Liberated Magic's / Phoenix Run's / Wild Blaze's Final Damage, those four become live Final Damage terms (a one-line change).*
5. **Fires of Creation = a per-branch incarnate**: the game summons the Flame Fox against a boss and the Fire Lion otherwise, so the BOSS / PvP branch uses the Fox (Boss Monster Damage +20 scaled, Defense Penetration +5 from Lv94, the Fox variants of Blazing Extinction / Towering Inferno incl. the boss flame strikes) and the NORMAL-monster branch the Lion (Normal Monster Damage +20 scaled,
   +1 Basic Attack target from Lv73, the Lion variants, +150 % Normal Monster Damage on Towering Inferno from Lv138).  Boss / PvP rows have a zero normal branch and vice versa.  In Breakthrough / Hero Dungeon the two incarnates alternate with the content's time weight.  The 3 s swap (a cooldown skill) is NOT charged as an action.  PvP uses the boss-branch rows (Fox: its Def Pen counts) but, as for every class, neither Boss nor Normal Monster Damage buckets.
   *Check: does the game keep the Fox for the whole boss fight and the Lion for the whole pack fight, and does a player swap manually between them?*
6. **Blazing Extinction**: one cast per cooldown (32 s, CDR applies); Lion row = 1200 per strike on 9 targets, 6 strikes in 3 s (7 from Lv126: interval 0.5 -> 0.4); Fox row = 1600 on 3 targets, 7 strikes in 5 s (10 from Lv126: 0.7 -> 0.5); whole strikes only (`floor(window / interval)`, the repo convention); the 3 / 5 s windows are not extended by Buff Duration Increase; the +50 % Lv108 mastery
   multiplies both.  *Check the real strike count of the orb (does the first strike land at 0 s or after one interval?).*
7. **Towering Inferno**: Lion 1350 x5 hits on 12 targets (normal branch only), Fox 2400 x2 hits on 4 targets (boss branch) + on bosses 3 flame strikes of 550 x2 each (4 from Lv138), modelled as a second row sharing the cast; the Lv113 +50 % mastery is assumed to apply to ALL of them (incl. the flame strikes).  *Check the strikes' damage in game.*
8. **Orbital Explosion** (passive, Lv45): fire energy 15 s "at the start of battle ... activates every 30 s" = windows [0,15) [30,45) [60,75) (exact in fixed fights, 15/30 in steady state, one window in PvP; neither Skill Cooldown Decrease nor Buff Duration applies to this fixed interval); while it is up every BASIC ATTACK (Final Orbital Flame only; absent below Lv100, so the proc is too) rolls 60 % per enemy hit
   (one roll per attack per enemy hit, CLAUDE.md proc rules: q = 1-(1-0.6)^N with N = enemies the basic attack hits, 1 on boss / PvP) for an explosion of 2 hits x 50 % on 5 targets, at most one explosion per 1 s ICD (steady rate X/(1+X) inside the window); +50 % damage at Lv54 (multiplies); Call of Cygnus +70 % Final Damage (per-skill multiplier); counted as SKILL damage (no [Basic Attack Effect]
   tag, like FP-Mage's Meteor Proc); it is NOT placed by the Status/KO timeline (a uniform row).  *Check: does the proc only trigger from Final Orbital Flame, and what does an explosion hit in game?*
9. **Flame Elemental** (Attack +15, 12 s x1.5 from Lv21 = 18 s, CD 28) is cast on cooldown from t = 0 and averaged by its uptime (no engine-timed buff: `STATUS_BUFFS = []`).  Its sub-effects count ONLY for that uptime and are averaged the same way: Greater Flame Elemental's "damage +20 % (+10 pp at Lv44)" joins the Damage % bucket (the same bucket as the typed Damage %), Grand Flame Elemental's Basic Attack Damage +15 the basic-attack bucket (also the companion
   host's), its Lv82 "Skill Damage +15" the skill bucket, Final Flame Elemental's Critical Damage +28 the crit-damage total, its Lv130 "+3 Final Damage" the additive Final Damage bucket (Final Damage +1 % sweep stays exactly 101), its Defense Penetration +3 is averaged in percentage points and combined with the typed value by diminishing returns (an approximation of the exact time split).
   *Check: is Greater Flame Elemental's "damage" the Damage % stat or Final Damage / Damage Amp?*
10. **Mastery "+X pp" additions are raw numbers**, not scaled by the skill level (Greater Flame Elemental +10, Fire Repulsion +5, Fires of Creation Final Damage +3, Flame Barrier +10, Fox Def Pen +5, Final Flame Elemental +3): they are fixed numbers in the mastery pop-up.  Phoenix Run's Lv118 "boost +100 %" is read as x2 of its value (Sensitivity: a second copy of the same curve from Lv118).
11. **Flashfire** (Attack +12 while the 30 s mark lasts, CD 10): a recast TELEPORTS to the mark and removes it, so the model casts it when the mark expires (period = max(effective cooldown, effective duration = 30 s x (1 + Buff Duration))) and counts 100 % uptime; teleporting is ignored.  The brief's variant (cast on cooldown every 10 s, uptime min(1, 30/cd)) has the same uptime but over-charges actions.
    *Check: how do players actually use it (cast once and fight at the mark?).*
12. **Burning Conduit**: only YOUR Final Damage +5 (idx 21, 20 s, CD 40) is modelled, averaged inside the additive Final Damage bucket (Dawn Warrior's convention); the allied parts (+35 % damage, +10 % Basic Attack Damage, +15 % Critical Damage at Lv122) are ignored.
13. **Call of Cygnus** (Flame Vortex 60, Flame Tempest 35, Cinder Maelstrom 30, Orbital Explosion 70) is a per-skill Final Damage multiplier `1 + pct/100` (Maple Hero / Dawn Warrior convention, user-confirmed there), multiplicative with the Final Damage bucket, applied to every hit of those rows.  Blazing Extinction / Towering Inferno / the basic attack have none.
14. **Cinder Maelstrom**: stun 1.5 s and Flame Tempest's Lv90 stun (1 s) feed the player-stun timeline (on-cooldown casts from t = 0, Dawn Warrior / Hero convention; stun immunity is not modelled); its Lv98 weaken (+9 % damage taken, 14 s) is a damage-taken term of BOTH branches (True Sight convention) with the cooldown uptime, in the timeline too (the cast is fixed on cooldown).
15. **Elemental Harmony**: Attack Speed +15 for 15 s, CD 60, NON-scaling (the game shows no level); averaged by uptime; the +10 % movement Speed is ignored.
16. **Basic attack**: Final Orbital Flame 290 % x5 hits (6 from Lv136), targets 6 + Basic Attack Target Increase input (the Lv64 mastery is in that input) and +1 in the NORMAL branch from Lv73 while the Lion is out; chain raw tiers 10/11/12/13/14/15 at 102/106/116/120/128/132 summed then x(1 + m/100); +10 / +10 % Boss Monster Damage at 111 / 124.
17. **Companion host**: the host has ONE Defense Penetration value (the branch-time-weighted mix of the Fox and Lion branches' values); Flame Elemental and Flashfire fully up in the Attack % snapshot; Grand Flame Elemental's time-averaged Basic Attack Damage is added to the host's basic-attack bucket and its Skill Damage to the host's skill bucket.
18. **Timeline / cast economy**: Flame Elemental, Flashfire, Burning Conduit and Elemental Harmony are actively cast buffs (the startup delay counts four sequential casts in fixed fights, so each extra buff can cost a damage-skill cast at an integer boundary: with the "late" stat set in Chapter Boss the Lv35 unlock of Flashfire lowers the total by 8 % because Flame Vortex drops from 5 to 4 casts (the only skill at that level);
    this is the repo's exact-cast convention, not a Blaze Wizard rule, and is outside the engine-native level-sweep fights).  The timeline places the cooldown casts of Flame Vortex, Flame Tempest, Cinder Maelstrom, Blazing Extinction (Fox) and Towering Inferno (Fox + boss strikes, one cast); the Fire Lion rows are the normal branch (the strip is boss-only, normal-only rows get the uniform factor) and the basic attack and Orbital Explosion are uniform rows.
19. **Sensitivity deltas**: the passives of the "stat screen" list above add their level delta in skill-level blocks (`PASSIVE_LEVELS`); Wild Blaze's +6 % Buff Duration and the masteries' raw values have no delta.  The Final Damage +1 % sweep bumps `final_damage + final_damage_extra` exactly (101.000, also with the strip on).

**Not verified / limits**: the screenshots were not re-read for this build (the transcription in `data/cygnus/blaze_wizard_ingame.md`, reviewed by the user, is the source); no number can be checked above level 1; the shared companion model divides by zero when Min Damage and Max Damage are both 0 (every class; irrelevant for real inputs).

**Verification** (2026-11-24, unpublished): `tests/golden/test_blaze_wizard_displayed.py` 172 level-1 values reproduced (coefficients through `SkillLevels.coeff_pct` at total level 1 with truncation, the model's resolved buff / row / Call of Cygnus values, hits / targets / cooldowns / windows / intervals, uptimes, masteries, unlock levels vs the icon grids; NO site cross-check exists);
`python3 tests/run_all.py --class blaze_wizard` green (the snapshot job is skipped: unpublished); `tests/golden/test_engine_native.py --class blaze_wizard` 8/8 (spec, hooks no-ops, API shape, Final Damage +1 % = 101.000 exactly in Chapter Hunt and World Boss with the strip, 16 equip-toggle pairs direction-invariant, 36 artifacts finite / 7 no-effect unchanged, 40 content runs, level sweep 1..200 in World Boss / Chapter Hunt (companion) / Breakthrough (companion) with NO decrease and no allow-list entry);
extra: level sweep 1..200 over all 10 content types x 3 stat sets x with / without companion (12000 runs): the only decrease is the Chapter Boss Lv35 startup-delay cast drop of item 18; 400-case random fuzz (all fields, content types, companions, 0-5 artifacts) without NaN / negative / error; Sensitivity "New Total" equals a plain re-run with the swept value for every stat except the main-stat / skill-level / crit-rate / attack-speed
blocks (block-only terms by design) and Final Damage (bumps the whole bucket by design) with Bottle of Emotion + Reindeer's Spear at star 5 in World Boss, Chapter Hunt and Breakthrough; `engine.sensitivity.run` (stats / artifacts / companions / summon_time / cdr), the cube / equipment pricing (`snapshot_common.run_cubes`) and the API through TestClient with `MSI_INCLUDE_UNPUBLISHED=1`
(`/api/classes` lists it, schema, defaults, compute, sensitivity, sensitivity/meta, cubes/meta answer 200) answer; without the variable the API lists 13 classes and every route 404s.
