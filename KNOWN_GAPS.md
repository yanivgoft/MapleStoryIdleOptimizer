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
- **Horn Flute**: only the character's own Final Damage portion is modeled — the Companion's own
  damage isn't modeled anywhere in this project (no companion DPS exists at all). Companion summon
  timing (t=7s, 30s active) given directly by the user; 0 in PvP/Chapter Hunt (no discrete
  battle-start event in either, matching Candle/Rainbow Snail Shell's existing convention).
- **Arwen's Glass Shoes**: purely extends Companion summoning duration — no character-applicable
  portion at all (unlike Horn Flute) — always 0, flagged, since companions aren't modeled.
- **Alliance Badge / Charm of the Undead**: real, live Attack%, same shared bucket as every other
  skill/artifact Attack% source. Charm of the Undead's periodic uptime (5s active every 10s,
  starting at t=10s) is a new pattern for this project (distinct from Hexagon Necklace's monotonic
  ramp) — verified by hand against the user's own timing description.
- **Sayram's Necklace**: the wiki's 2+-target/1-target gating is ignored entirely per the user —
  both the Normal Monster Damage and Boss Monster Damage bonuses are always granted simultaneously,
  feeding the existing branch-specific `boss_damage%`/`normal_damage%` buckets directly.
- **Ancient Text Piece**: gated on "[Guild Conquest]", a content type this project doesn't model at
  all — always 0.
- **Fire Flower**: the wiki's real per-nearby-target scaling (capped at 10) is replaced with a
  fixed assumption per the user — always exactly 10 targets against normal monsters, always
  exactly 1 against boss/PvP.
- **Lunar Dew / Pig's Ribbon**: pure defensive/recovery procs (HP/MP regen, damage immunity) with
  no DPS effect at all — always 0, per the user.
- **Chalice**: the real mechanic (2%-chance-per-hit proc, 100% on a boss kill, granting a 30s Final
  Damage buff, re-appliable) collapses to a single simplified model per the user: always active
  during exactly the last 30 seconds of the fight (`[MAX(0,duration-30), duration]`), relevant
  whenever `monster_type` is `"normal"` or `"breakthrough"` — 0 in pure boss-only content and PvP.
  Uses branch-specific overlap math against the same `boss_appear_time` concept Candle already
  uses (generalized to handle pure-"normal" content, where there's no boss phase at all); verified
  against hand-worked numbers for Breakthrough, Hero Dungeon, and pure-normal content.
- **Pink Bean's Giant Rib / Horntail's Scale / Zakum's Stone Piece**: each has a generic-looking
  "+Final Damage%" clause on the wiki, but these are raid-boss-specific artifacts for content this
  project doesn't model at all — always 0, unconditionally, per the user.
- **Mushmom's Cap** (the user's "Mushroom Cap"): Accuracy-vs-target's-Evasion conditional damage,
  not modeled (same category as Cursed Doll's ignored accuracy behavior) — always 0.
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

