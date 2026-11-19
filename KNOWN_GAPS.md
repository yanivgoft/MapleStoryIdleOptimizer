# Known Gaps & Assumptions

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
  **Chapter Hunt (steady state, updated 2026-11-07):** modeled as a renewal process instead: 100 kills/min (`CHALICE_KILLS_PER_MINUTE`)
  x 2% proc chance per kill (`CHALICE_PROC_CHANCE`), the 30s timer resets on a new proc, so the buff is on iff at least one of the
  last 50 kills procced: uptime = 1-0.98^50 = 63.6% (not the 'on for 1 of every 30s' point estimate, and not 0 as before) -> Chalice
  adds 63.6% x the star value (19.07% at star 5) to the normal-branch Final Damage; total DPS x1.1907 at star 5. Assumes proc per
  KILL (not per hit) and a refresh (not stacking) on re-proc; fixed-duration normal content (EXP/Equipment/Weapon/Enhancement
  dungeons) and Breakthrough/Hero Dungeon keep the last-30-seconds model.
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
reuses the main strip's cast counts and timing factors (its own damage numbers still change, the schedule does not - a second-order approximation, e.g. Meditation's level).

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
