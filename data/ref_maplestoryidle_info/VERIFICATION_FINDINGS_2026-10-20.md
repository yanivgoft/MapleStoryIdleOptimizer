# Class-by-class data verification — started 2026-10-20

Method: for each class, compared OUR workbook (Skills sheet + UNLOCK_LEVEL dict in the build script) against
  (1) maplestoryidle.info — patched text (base + AUGUST_13_SKILL_UPDATES overlay), masteries, AND the game tables
      (assets/data/job-skill-impact.json: ratioE3, factorIndex, hitCount/maxHitCount, cooldownMs, trigger rules);
  (2) idle.maplestorywiki.net — Skills overview, Mastery page, individual skill pages (fetched 2026-10-20);
  (3) official Aug 13 patch notes (aug13_patch_notes_class_changes.md, transcribed from ~/Downloads PDF).
Raw data lives next to this file (site_*.json). The wiki is PRE-patch for text (matches site "BASE"), so a
wiki-vs-site(patched) difference that the patch notes explain is NOT a conflict.

Verified globally: FactorTable F12/F21/F22/F23 columns in the workbooks == the site's skillLevelFactors for levels 1-300 (exact).

Legend: [OURS-WRONG] = ours disagrees with every available source (fix proposed);
        [CONFLICT] = sources disagree with each other -> needs user decision.

---------------------------------------------------------------------------------------------------
## EXECUTIVE SUMMARY (read this first)

A. Stale mastery levels (all of Bowmaster, Marksman, Night Lord): the wiki Mastery page (also as of the Sep-6 snapshot in ~/Downloads), the site, and the official patch notes all agree on one table;
   ours uses an older/shifted one (e.g. basic-attack damage chain 98/104/113/118/126/130 vs the real 102/106/116/120/128/132; boss 108/122 vs 111/124; Strike 134 vs 136; many 2nd-4th job masteries 2 levels early).
   Shadower, Hero, DK, Paladin, IL, FP, Bishop, Buccaneer, Corsair already use the current table for the basic-attack chain.
B. FP-Mage only: Flame Sweep damage mastery is summed as raw tiers (75% total) instead of cumulative-delta (15%) like every other class.
C. Buccaneer: Sea Serpent Burst (7s cooldown) modeled as firing on every basic attack; Greater Sea Serpent I/II (430% damage, +targets, +100% FD) not implemented; Speed Infusion missing; several unlock levels/factorIndices assumed.
D. Corsair: mastery table was "role-mapped" from Buccaneer; real table (site) differs (Blackboot +50 not +80; Scurvy/All Aboard/Siege/Rapid Fire damage masteries missing); many unlock levels/factorIndices differ.
E. Ice/Lightning: Blizzard Final Attack should trigger off ANY attack (30%, 1s ICD) like FP's Meteor Proc, not just Blizzard casts.
F. Shadower: Assassinate factorIndex 21 -> 12 (patch change); Meso Mastery (Lv75) unmodeled.
G. Hero/DK/Paladin: Rush/Beam Blade/Evil Eye/Gungnir/Noble Demand etc. damage & reuse masteries missing; Hero Puncture/ERB mastery attribution; DK Final Attack mastery missing; Paladin buff factorIndices.
H. Bowmaster: Quiver Cartridge HitsPerCast=3 (should be 1), Hurricane/Flash Mirage targets, Phoenix duration, missing masteries (see section).

DECISIONS NEEDED FROM THE USER (sources disagree, or the unit/mechanic is ambiguous):
  1. Sharp Eyes (Bowmaster, Marksman): +20 Crit Rate (wiki) vs Crit Damage only (site + game table). Ours adds +20 Crit Rate.
  2. Concentration/Focused Fury: 10 stacks (wiki) vs 7 (site); per-stack value scales with level (game table f22) but ours is flat.
  3. Mortal Blow: 40 hits (wiki + table) vs 50 (site text); ours assumes always on.
  4. Arrow Platter damage: 50% (wiki curve) vs 97.7% (site text); table has no ratio.
  5. Quiver Cartridge tick: "0.4 times" (wiki) vs "0.4 sec" interval reduction (site).
  6. Illusion Step Attack: 14% (text) vs 28% (table); Lv118 mastery meaning.
  7. Unit of the 3 "N*(1+0.005x)%" masteries (Snipe-Empowered 5700, DK Spectral Shadows 2200, Bowmaster Drain 1050): ours enter them as TENTHS of a percent (570/220), while Blizzard/Meteor FA (950) and Nautilus FA (850) are entered as literal percent.
  8. Cross Over Chains / Hex "+100% / +50% Attack" (DK): percentage points (ours) or relative?
  9. Hero: which of Puncture/ERB masteries sit at 108/122/134/138 (site by name vs earlier description-based re-attribution) and the Puncture damage-taken mastery value (+50% vs +20%).
 10. IL / FP masteries at L126-138 (garbled names/descriptions on the wiki) — in-game text needed.
 11. FP-Mage Flame Sweep mastery: raw 10/11/12/13/14/15 (75%) vs deltas (15%).
 12. Shadow Partner 60% (site) vs 84% (wiki); Shadow Shifter FD (site) vs Attack (wiki); Night Lord Venom unlock 74 vs 72; Quad Star cooldown 13s (site text) vs 10s (table + wiki).
 13. Shadower Assassinate finishing blow current ratio; Smokescreen L113 ally-crit self-inclusion.
 14. Paladin Combat Orders masteries (25%p vs 15%p; +18 4th-job levels) — model or not.
 15. Bishop Triumph Feather 18s cooldown (table only).
 16. FP Poison Mist interval mastery (0.5 sec vs 50%); Mist Eruption explosion structure after the patch; Flame Haze burst hits (3?).
 17. Hero Combo Attack chance (table+wiki 40% vs site 30%); Scaring Sword chance (25% vs 35%); Magic Crash weaken (10% vs 15%).

---------------------------------------------------------------------------------------------------
## BOWMASTER
[OURS-WRONG]
- Quiver Cartridge HitsPerCast = 3 (6 after Lv107) -> should be 1. Game table: hitCount 1, targets 3 (+3 Enchanted Quiver), OnTimer 1000ms.
  Wrongly multiplies Quiver DPS by 3x (6x after Lv107) on single-target/boss.
- Quiver Cartridge has MasteryNormalDamage% = 200 with no basis in any source -> remove (or user confirms).
- Quiver Cartridge missing mastery "Quiver Cartridge - Damage +50%" at Lv44.
- Hurricane NormalMonsterTargets 7 -> 11 (patch notes 7->11; site text; game table maxHitCount 11). Factor 12 / 8000 now CONFIRMED by game table
  (note still says FLAGGED ASSUMPTION).
- Flash Mirage targets 5 (+1 at Lv136) -> 7 base (patch notes 5->7; table: main-target line + line with maxHit 6 = 7 total). Flash Mirage II adds +4 targets
  at Lv110 (table: MaxHitCount +4 on the 2nd line) which our formula never adds (only its FD is applied) -> 11; mastery "FM II - Enhance & Target" +1 at **Lv138** (ours 136; patch notes +3->+1 at Lv138).
  Factor 21/5500 now CONFIRMED by table. Cooldown 5s confirmed by table.
- Arrow Stream mastery levels (site + wiki + Sep-6 wiki PDF agree): Damage chain 102/106/116/120/128/132 (ours 98/104/113/118/126/130);
  Boss Damage 111/124 (ours 108/122); Strike +1 at 136 (ours 134). Note 102 is the first valid level (skill unlocks at 100); ours 98 is below the unlock.
- Phoenix: mastery levels Target +3 @78, Strike Interval -30% @82, Normal Monster +100%p @94, Reuse -40% @104 (ours 76/80/92/102; patch notes explicitly say Reuse is Lv.104).
  Duration is 30s at ALL levels (patch notes 20s->30s); ours uses 20s below Lv102.
- Missing masteries: Arrow Platter - Damage +50% @73; Flash Mirage II - Reuse -40% FM cooldown @122; Sharp Eyes - Persistence +50% duration @126;
  Mortal Blow - Persistence +5s @90; Illusion Step - Enhance @118; Enchanted Quiver - Drain @130 (30% chance, 1050*(1+0.004*skillLv)% extra damage on Quiver hit).
- FINAL ATTACK/ADV FINAL ATTACK mastery levels already correct (54 / 113).
[CONFLICT]
- Sharp Eyes: wiki = allied Crit RATE +20% and Crit Damage +40%; site text + game table = Crit DAMAGE only (allies: 20% of your crit dmg; self +40%);
  the game table has NO crit-rate stat. Ours adds a flat +20 Crit Rate (Summary R_CRIT_RATE_BONUS) -> unsupported by site/table.
- Concentration ("Focused Fury"): wiki = 10 stacks, site (base AND patched) = 7 stacks. Game table: per-stack value = 30 (3%) with factorIndex 22 (SCALES with level), ours is flat 30 total.
- Mortal Blow trigger count: wiki 40, game table 40, site descriptions 50. Ours note says 40 but models always-on.
- Arrow Platter damage: wiki(Quiver_Flow curve) 50% at Lv1 -> 100%; site text 97.7% (both base and patched). Game table only has a projectile id (no ratio).
- Quiver Cartridge tick: wiki "up to 0.4 TIMES faster", site (base+patched) "interval improves by up to 0.4 SEC". Ours uses 1/(1+0.4*AS/150) (wiki wording).
- Illusion Step: text 14% (+evasion phase) but game table Attack value = 280 (28%?) with no duration.

---------------------------------------------------------------------------------------------------
## MARKSMAN
[OURS-WRONG] (same pattern; Marksman was NOT updated when Bowmaster's FA/AFA levels were)
- Empowered Piercing Arrow masteries: Damage chain 102/106/116/120/128/132 (ours 98/104/113/118/126/130); Boss 111/124 (ours 108/122); Strike @136 (ours 134).
- Final Attack: Crossbow mastery @54 (ours 52); Advanced Final Attack mastery @113 (ours 111).
- Bolt Burst - Damage +50% @68 (ours 66).
- Frostprey: Target +2 @78 (ours 76), Damage +50% @82 (ours 80), Normal Monster +100%p @94 (ours 92), Reuse -40% @104 (ours 102; ours explicitly chose the wiki over the patch
  notes' "Lv.104" earlier — wiki, site, and patch notes now ALL say 104).
- Snipe - Damage +50% @108 (ours 106). Bolt Surplus - Damage +50% @122 (ours 120); Strike&Target @138 (ours 136). Arrow Illusion - Damage +50% @130 (ours 128).
- Missing: Sharp Eyes - Persistence @126 (+50% duration), Illusion Step - Enhance @118, Mortal Blow - Persistence @90.
- Snipe - Empowered (@134): text = "5700*(1+0.005*skillLv)% damage" (literally 5700%, base Snipe is 3800%). Ours adds 570*(F12/1000) percentage points = 570% -> **possible 10x too small**
  (earlier session read "5700" as tenths-of-percent). Needs user confirmation.
[CONFLICT]  same Sharp Eyes crit-rate / Mortal Blow 40-vs-50 / Illusion Step 14%-vs-280 issues as Bowmaster.
[NOTE] Blink Bolt modeled as always-on +Attack (flagged assumption in ours; cd 10s, duration 30s, toggle mechanic) — unchanged, just a reminder.

---------------------------------------------------------------------------------------------------
## NIGHT LORD
[OURS-WRONG]
- Showdown masteries: same as Bowmaster (102/106/116/120/128/132, boss 111/124, strike 136).
- Mark of Assassin: unlock level 43 (ours 40); Damage +80% mastery @44 (ours 42).
- Triple Throw +100% @73 (ours 71). Shadow Partner +100% @68 (ours 66). Alchemic Adrenaline Persistence @90 (ours 88).
- Dark Flare Strike +1 @78 (ours 76); Reuse -30% @94 (ours 92). (Strike Interval @104 correct.)
- Quad Star Reuse @108 (ours 106); Damage +50% @134 (ours 132). Sudden Raid +50% @126 (ours 124). Toxic Venom +100% @130 (ours 128).
- Missing: Critical Throw L49 (+8%p crit rate; baked in Inputs?), Frailty Curse - Critical @113 (crit-damage-taken +30%) not modeled.
[CONFLICT]
- Venom unlock level: site text+table 74, wiki 72, ours 72.
- Shadow Partner damage: site 60% vs wiki 84% (ours 84, base 840 tenths). Not in patch notes.
- Shadow Shifter passive: site text "Final Damage +10%" (and mastery "Final Damage +10%p"), wiki "Attack +10%"; ours models Attack%. Game table lists no FD/Attack stat for it.
- Alchemic Adrenaline mastery @90: site (base+patched) "duration +5 sec AND Final Damage +6%p", wiki "duration +5 sec" only. Ours: duration only.
- Quad Star cooldown: site TEXT 13s vs site game-table 10s vs wiki 10s (ours 10 = table).
- Alchemic Adrenaline: base site text "10 hits / FD 10%", wiki "7 hits / FD 10%"; patch notes say 7->5 and 10->15 (so wiki's "7" is right pre-patch; site base "10" is wrong but irrelevant after patch).

---------------------------------------------------------------------------------------------------
## SHADOWER  (mastery levels already match site/wiki/patch notes — Shadower was built from the current table)
[OURS-WRONG]
- Assassinate base hit uses factorIndex 21; game table says **factorIndex 12** (ratio 14000, hitCount 2, cd 13s). The Aug-13 note "base hit damage now increases more significantly
  with skill level" is exactly this change; ours still uses the pre-patch wiki curve (see its note: "no numeric override — using the wiki's own current curve").
- Dark Flare: Strike +1 mastery @78 (ours 76); Reuse -30% @94 (ours 92). (Strike Interval @104 is correct.)
- Meso Mastery (Lv75 passive) is not modeled at all: Meso Explosion's generation chance +25%p (50% -> 75%) and "+25% Attack for 5s whenever Meso is generated"
  (near-permanent at normal attack rates). Our Meso/Blood-Money stack averages use 0.5 chance; with Meso Mastery it should be 0.75 (Blood Money 0.75*0.5).
[CONFLICT]
- Shadow Partner damage: site 60% vs wiki 84% (ours 84). Shadow Shifter: site "Final Damage +10%" vs wiki "Attack +10%" (ours Attack%).
- Assassinate finishing blow: ours = +3000% every 2nd cast (factor 12/30000) from the PRE-patch text; the patched site text no longer states the number and the
  finishing-blow variant (skill 104022) is not in the game tables. Current value unknown.
- Smokescreen L113 mastery: site says it raises *allied players'* Critical Damage +30%; ours treats it as self-inclusive (feeds Crit Damage accumulator). Please confirm self is included.
[OK] Everything else matched: Cruel Stab 2900/21 + all mastery levels (102/106/116/120/128/132, 111/124, 136); Phase Dash 4500/12, 9 targets, +80% @73; Meso Explosion 2700/12 +100% @90;
  Blood Money 3600/12 (+50%/+50% @122/@138, target multipliers 2x/3x); Sudden Raid 14000/12 + 3600/12 DoT, +50% @126; Into Darkness 20%/f21; Smokescreen 13%/f22; Toxic Venom 6000/21 +100% @130;
  Venom 450/21 (unlock 72 matches site+wiki); Maple Hero ratios 15/50/50/40; Shadower Instinct 20%/f22; Dagger Expert; Channel Karma; Steal.

---------------------------------------------------------------------------------------------------
## HERO
[OURS-WRONG]
- Mastery attribution of the swapped Puncture / Enhanced Raging Blow rows. Both the wiki and the site agree on the NAME->LEVEL pairs: Puncture-Damage @108, Enhanced Raging Blow-Damage @122,
  Puncture-Weaken @134, Enhanced Raging Blow-Damage @138. The wiki's description column is shifted (shows the other skill's text). Earlier sessions re-attributed "by effect description"
  (ERB damage +50% @108, Puncture damage +50% @122, ERB combo FD @134, Puncture dmg-taken +20 @138). The site pairs names with matching text (Puncture +50% @108, ERB +50% @122,
  Puncture damage-taken effect +50% @134, ERB combo FD +50%/excess stack @138). Cross-class pattern strongly supports the SITE: every class's 103-unlock skill gets masteries at 108 & 134,
  and every 107-unlock skill gets them at 122 & 138 (Quad Star/Assassinate/Snipe/Hurricane 108+134; NLM/Blood Money/Bolt Surplus/ERB 122+138). => swap to the site's assignment.
  The Puncture "damage taken" mastery VALUE conflicts: site "+50% of the effect" vs wiki desc "+20%".
- Enhanced Raging Blow baseDamage 6105 -> 6100 (game table ratioE3 6100; 6105 came from rescaling 5500*610/550 with a 5-tenths residual).
- Missing masteries (all four sources list them): Beam Blade - Damage +50% @73, Strike +1 @94, Reuse -30% cd @104; Rush - Damage +80% @68, Reuse -30% cd @90;
  Spirit Blade - Reuse -30% cd @44 (ours cooldown 45 flat); Combo Attack - Attack +1.5%p/stack @49; Combo Synergy - +1%p FD/stack @82; Advanced Combo - max stacks +1 @118
  and +1% Defense Penetration per combo stack @130; Self Recovery - Final Damage +5% when HP>=50% @98. (Ours says Rush's masteries are "folded into the base curve" — they are not.)
- Puncture wound "damage taken +10%": patched to apply to ALL targets (was boss only); ours applies it as MasteryBossDamage% only. Should also apply to normal monsters.
[CONFLICT]
- Combo Attack trigger chance: game table 40% (OnAttack 400) + wiki 40%, but site description says 30%. Ours 40.
- Scaring Sword proc chance: site 25% vs wiki 35% (ours 35); not in patch notes; linked passive not in tables.
- Magic Crash weaken mastery @126: site 10% (game table also 10%/15s) vs wiki desc 15%. Ours does not model it.
[OK] Raging Blow 2900/21 + chain levels (102/106/116/120/128/132, 111/124, 136), Final Attack/AFA 54/113; Puncture 9000/12 10 targets cd17; wound 1500/12; ERB targets 12 cd 17;
  Magic Crash 48000/12 9 targets; Beam Blade 2500/12; Rush 6000/12; Flash Slash 350%/f12 (+50% @39); Enrage 12s interval / 7s; Power Stance FD 15%; Maple Hero 20/30/80.

---------------------------------------------------------------------------------------------------
## DARK KNIGHT
[OURS-WRONG]
- Final Attack - Damage +50% @54 is MISSING (ours' note says "DK's mastery table has no Final Attack tier, confirmed absent" — the wiki Mastery rows and the site both list it @54).
- Gungnir's Descent - Damage +50% @108 is missing (the Lv134 "-50% base, +4 strikes" rebalance IS modeled and matches the site).
- Evil Eye - Reuse -30% cooldown @104 missing (ours cooldown 30 flat). Rush - Damage +80% @68 and Rush - Reuse -30% cd @90 missing (same as Hero).
- Magic Crash - Weaken @126: ours uses +15 (wiki figure), applied three times (SkillMastery/Boss/Normal buckets). Site text AND game table say 10% (table: Weakness 10% for 15s). 
- Hex of the Evil Eye mastery @82: site "Boss Monster Damage +20% for allies during the summon" vs wiki "Accuracy +20 for allies" (name+desc differ). Ours: nothing (comment says "+20 Accuracy not modeled").
[CONFLICT / NEEDS IN-GAME CHECK]
- Percent-vs-percentage-point: Cross Over Chains @73 "additionally increases Attack by 100%" and Hex @98 "...Attack by 50%" are written with plain "%" (other masteries explicitly say "%p"). Ours adds +100 / +50 PERCENTAGE POINTS
  (Cross Over Chains becomes ~115% Attack, Hex ~65%). If these are relative (x2 / x1.5) the buffs are ~3-4x overstated.
- Revenge of the Evil Eye - Spectral Shadows @138: wiki text "2200*(1+0.005x)% damage" (site just says "scaling damage"). Ours uses 220*(F12/1000) i.e. treats 2200 as TENTHS of a percent (=220%).
  Same unit question as Marksman Snipe-Empowered (5700 -> ours 570) and Bowmaster Enchanted Quiver Drain (1050, not modeled).
- Hyper Body cooldown: site TEXT 45s vs game table 30s vs wiki 30s (ours 30, = table).
[OK] Dark Impale chain (102/106/116/120/128/132, 111/124, 136), AFA 113; Evil Eye Shock 70%x6 f12, +50% @44, +3 targets & +100% FD @75 (f22 1000); Evil Eye of Dominant 60%/s f21, +50% @78, +3 targets @94;
  Revenge 850%x2 f12 cd5 +50% @122; Rush/Gungnir/Magic Crash base tuples; Dark Resonance 30%/f21, cd 32, +40% duration @130 (boss +20% folded in); Lord of Darkness patched (10%/40%/8s/3s);
  Maple Hero 40/30/30; Final Pact; Barricade; Power Stance.

---------------------------------------------------------------------------------------------------
## PALADIN  (no per-skill wiki pages exist; the site's game tables now let us CONFIRM the previously "FLAGGED ASSUMPTION" tuples)
[OURS-WRONG]
- FactorIndex for three active buffs: Guardian (FD 10%), Divine Blessing (FD 12%), HP Recovery (Attack 12%) — game table says **factorIndex 21**; ours use 22 ("buffs -> 22" convention).
  (Greater Vessel of Light, Vessel of Light, Divine Shield are f22 in the table = ours OK.)
- Missing masteries: Divine Judgment - Damage +50% @130; Noble Demand - Reuse -30% cd @94; Rush - Damage +80% @68 and Rush - Reuse -30% cd @90 (same gap as Hero/DK);
  Vessel of Light - Attack +5%p @49; Greater Vessel - Final Damage +10%p @118; Divine Blessing - FD +12%p @126; HP Recovery - Attack +10%p @78 (site).
- Divine Mark - Damage +50% @122: ours applies it to the main hit only ("wiki doesn't specify"); the site says "Divine Mark damage +50%" (whole skill) — likely both parts.
- Combat Orders is declared "no DPS-relevant mechanic" in the build script, but its masteries are DPS-relevant: @82 "+25%p damage for the duration" (game table: AttackPower 25%) and @104 "+18 levels to 4th-job skills";
  base skill gives +18 levels to 3rd-job skills for 25s (cd 35s). Not modeled.
- Divine Judgment's own +30% Basic Attack Damage (5s per 10 basic attacks; table: BaseAttackPower 30%, factorIndex 21) is flagged/unmodeled in ours; only the 850%x4 brand is modeled.
  Brand ratio 850% / 4 hits / 4 targets comes from description only (projectile 24070 not in tables).
[CONFLICT (site/table vs wiki)]
- Combat Orders damage boost: site+table 25%p vs wiki 15%p; HP Recovery attack mastery: site 10%p vs wiki 5%p; Parashock Guard mastery: site 10%p vs wiki 5%p.
- Combat Orders text: site "also reduces MP cost by 20%" (table: MpConsumeRatio -20%) vs wiki without. (MP not modeled.)
[CONFIRMED by game table] Close Combat 4600/f12 cd18 7 targets (+10% Weakness 10s); Heaven's Hammer 7800/f12 5 hits 7 targets cd18; Divine Mark 4600/f12 x6 + 4000/f12 x4, 8 targets, cd16, Weakness 20% @138;
  Rush 6000/f12; Magic Crash 48000/f12 9 targets cd28; Blast 2900/f21 and chain levels; Final Attack 350/f21, mastery @54; Maple Hero 20/30/80/150(FA); Divine Shield 15% FD f22.
  Divine Mark Weaken/Close Combat Weaken/Noble Demand debuff durations (10s) match the table.

---------------------------------------------------------------------------------------------------
## ICE/LIGHTNING MAGE
[OURS-WRONG]
- Blizzard - Final Attack (Lv113 mastery) is modeled to proc ONLY off Blizzard's own casts (RollsPerCast=3 per 33s cast, cooldown = Blizzard's cooldown). The mastery text is
  "[Blizzard in Slot] When attacking, deals 950%... with a 30% chance" (identical wording to FP-Mage's Meteor Shower FA) and the patch notes add "Cooldown set to 1s" — i.e. ANY attack can trigger it
  at 30% with a 1s internal cooldown. FP-Mage's equivalent (METEOR_PROC) is correctly multi-trigger; IL's is not => large undercount (~0.3 procs/s of 950% vs ~0.02/s).
- Blizzard masteries: site has "Blizzard and Blizzard Final Attack damage +50%" @134 (the FA row would also get +50%); ours has "Blizzard damage +40%" @130 only, and does not boost the FA row.
[CONFLICT — masteries L126/L130/L134/L138 are garbled on the wiki; needs in-game check]
  names (wiki+site agree): L126 Frozen Orb-Strike Interval, L130 Elquines-Strike Interval, L134 Blizzard-Damage, L138 Elquines-Damage&Target.
  descriptions: wiki L126 "Elquines strike interval -0.2%", L130 "Blizzard damage +40%", L134 "Frozen Orb strike interval by 50 sec", L138 "Elquines +50% dmg, +3 targets".
  site: L126 "Frozen Orb strike interval -0.2 sec", L130 "(Elquines-Strike Interval) Blizzard damage +40%", L134 "Blizzard & Blizzard FA damage +50%", L138 same as wiki.
  Ours: Elquines interval x0.8 @126, Blizzard +40% @130, Frozen Orb interval x0.5 @134 (reassigned by description, "user-confirmed 20%"). Pattern argument (103-unlock skill -> 108/118, 107 -> 122/126,
  115 -> 130/138) favors the NAMES: Frozen Orb @126, Elquines @130, Blizzard @134. Please confirm in game.
- Arcane Aim (Lv120): FD +3%/stack (f22) with 25% proc, 5 stacks — ours models it multiplicatively as (1+F/100)^5 (documented); the row's note still describes Buff Duration (copy of Buff Mastery) — doc fix only.
- Same unit question as Marksman/DK: Blizzard FA uses the LITERAL-percent reading (950% -> baseDamage 9500 tenths), whereas Snipe-Empowered (5700), DK Spectral Shadows (2200) were entered as tenths (570 / 220).
  Consistency says those two are 10x low.
[CONFIRMED by game table] Chain Lightning 2900/f21 + chain levels; Thunder Bolt 1800/f12 8 targets cd18 (+70% @39); Glacier Wall 2900/f12 8 targets cd22 (+80% @68, Reuse @90);
  Blizzard 6000/f12 3 hits 7 targets cd33; Magic Guard 12%/f21; Meditation 20%/f21; Infinity FD 15% + 1%/s (f21); Elemental Reset 12%/f22 (25% trigger); Maple Hero 20/30/100;
  Freezing Breath cd40 (projectile ratio not in tables; 800% from text); Frozen Break/Frost Clutch (3%/4% per Frost stack, assumed 5 stacks steady-state);
  Buff Mastery 10% (f22, scales with level) — NOT added on top of Inputs (user-confirmed, fixed earlier today).

---------------------------------------------------------------------------------------------------
## FIRE/POISON MAGE
[OURS-WRONG / INCONSISTENT WITH ALL OTHER CLASSES]
- Basic Attack (Flame Sweep) damage mastery chain is summed as RAW tier values: {102:10, 106:11, 116:12, 120:13, 128:14, 132:15} = 75% total (33% at Lv117).
  Every other class (including Ice/Lightning and Bishop, the other mages) uses DELTAS {10,1,1,1,1,1} = 15% total (12% at Lv117) — CLAUDE.md structural-bug #2 describes exactly this fix;
  FP-Mage was never corrected and its note even states "75% total". At Lv117 this adds ~21 percentage points to the Flame Sweep coefficient (~+5% Basic Attack DPS).
  (The first-job chain "+15%,+20%,+20%" proves the tiers are NOT all cumulative displays, so please confirm which convention the in-game tooltip uses before I change it.)
- Flame Haze (burst) HitsPerCast = 3 has no source: base AND patched text say a single explosion "deal 1200% damage to up to 10 targets" (no "N times"); projectile data not in tables.
- Ifrit masteries: site gives "+5s duration, +1 target" at Lv126 (listed under the name "Flame Haze - Burn") AND "+10s, +3 targets" at Lv138; ours only models the Lv138 step.
- Meteor Shower +50% @134 (ours) — neither source states it under Meteor Shower: wiki desc at L130 = "Meteor Shower damage +20%", site/wiki desc at L134 = "[Flame Haze in Slot] ... inflicts Burn with a 50% chance".
  Same cyclic name/description shuffle as Ice/Lightning (see there) for L126/L130/L134/L138: names = [Flame Haze-Burn, Ifrit-Burn Damage, Meteor Shower-Damage, Ifrit-Persistence&Target].
[CONFLICT]
- Poison Mist strike-interval mastery @104: site "-0.5 sec" (0.8s -> 0.3s) vs wiki "-50%" (0.8s -> 0.4s). Ours 0.4.
- Mist Eruption structure: patch says explodes TWICE per fog, 4s cooldown after each explosion (3s after the Lv108 mastery, which also adds +1 explosion). Ours uses 3 explosions (4 at Lv108) on normal monsters and 1 on bosses.
- Poison Breath: site text 160%, wiki 200%, GAME TABLE 200% (ours 200 = table). Elemental Drain: site text 8%, wiki 12%, GAME TABLE 12% (ours 12 = table). Site text is the odd one out here.
- Flame Haze burn (patched): interval 1s -> 0.5s and boss duration 30s -> 20s are in ours (0.5, 20/10). Creeping Toxin (Poison stacks @73) not modeled beyond the explosion row.
[CONFIRMED by game table] Flame Sweep 2900/f21 and chain levels (102/106/116/120/128/132, 111/124, 136); Poison Mist 1600/f12 x3 cd35 (+50% @68, Reuse @90); Meteor Shower 6000/f12 x3, 7 targets, cd33;
  Meteor FA 950%/30%/1s (f21); Mist Eruption cd 4s; Infinity f21; Element Amp 15%/f22; Elemental Reset 12%/f22; Fervent Drain 4%/stack f22; Arcane Aim 3%/f22 x5 stacks;
  Maple Hero ratios 10/10/50/150/80; Buff Mastery 10% (not added again).

---------------------------------------------------------------------------------------------------
## BISHOP  (built from current data; almost everything matches)
[CONFLICT / NEEDS CHECK]
- Triumph Feather: the GAME TABLE lists a **cooldown of 18000ms** on the passive (#63050, trigger OnAttack 15%) that neither text mentions. If that is an internal cooldown on starting the 10s "angel power"
  window, max uptime is 10/18 = 56% — ours models stage 1 as a pure 15%(25% @78)-per-attack queueing process (near-100% uptime at normal attack rates), which would then overstate Feather DPS up to ~1.8x.
  (Other passives with a table cooldown do match their text: Lord of Darkness 3s, Bolt Surplus 0.1s, Aggressive Resistance 10s.) Please check in game / tooltip.
- Angel Ray hit structure: text "3 times ... 680% damage 2 time(s) each" (= 6 hits, ours); game table lists two damage lines (hitCount 2 and hitCount 1, 3 ticks). Keeping 6 from the text.
- Heal / Heal-Attack HP conditions: site says HP >= 30%, wiki 70% / 50% (ours ignores the condition, always on).
[CONFIRMED by game table] Big Bang 2900/f21 + chain levels; Angel Ray 6800/f12 (+50% @108, boss proc @122); Genesis 7000/f12 (+50% @118, Reuse @126); Bahamut 35000/f12 (+50%/+3 targets @130, Reuse @138);
  Heal 10%/f21, Bless 16%/f21 (+30% @44), Holy Magic Shell 15%/f21, Advanced Blessing 7%/f21 (+4% @113), Holy Symbol 15% NMD f22 (+25% @90, +50% duration @98), Divine Protection 25%/f22,
  Infinity, Blood of the Divine 5%/f22 (+20% crit dmg at full HP, +15% AS @134), Maple Hero (Triumph Feather 50%), Holy Fountain cd 30 / boss dmg +20% @68, Triumph Feather ratios (150%, 2->3 hits @104, +50% @73, 7 targets @94).

---------------------------------------------------------------------------------------------------
## BUCCANEER  (site is a game capture here; the game tables answer many of the old "FLAGGED ASSUMPTION" rows)
[OURS-WRONG — high impact]
- Sea Serpent Burst has a **7s cooldown** in the site (text cd "7 sec", game table cooldownMs 7000, and the masteries "Greater Sea Serpent I - Reuse -2s" @78 / "Greater Sea Serpent II - Strike & Reuse -2s" @118
  are cooldown reductions, so 7s -> 5s -> 3s). Ours fires Sea Serpent Burst / Serpent Assault on EVERY basic attack (probability split by an Assault-Mode duty cycle), i.e. no cooldown at all,
  and drives the whole Serpent Scale (5 scales -> Assault Mode) economy off that rate. Overcounts the whole Serpent kit by roughly (basic-attack rate x cooldown) = ~7-17x on the proc frequency.
- Greater Sea Serpent I (Lv72) / II (Lv110) are not actually implemented although the notes claim they are: Sea Serpent Burst stays at 130% / 5 targets in the row.
  GSS I: damage -> **430%** (scales with GSS I level) and +2 targets (7). GSS II: +2 more targets and **Final Damage +100%** (table: ModSkillStat on the Sea Serpent Burst variant, factor f22).
  Ours instead doubled **Serpent Assault**'s base (4800 = 2 x 2400) for GSS II; the table shows Serpent Assault (#113051) only receives Maple Hero.
- Speed Infusion (Lv107 active, cd 35s): "+20% Attack Speed and Final Damage +20% of Attack Speed for 15s" (table: AttackSpeed 20%, f21) is completely MISSING from the workbook.
- Sea Serpent's Rage uses factorIndex 12; game table says **factorIndex 21** (ratio 17000, 2 hits, max 8 targets, Weakness 15%/5s f21).
- Crossbones / Time Leap factorIndex 22 -> game table **21**.  Crossbones DefPen +5% (f21) not modeled (no live DefPen mechanism).
- Unlock levels (site req): Serpent Assault 69 (ours 60), Serpent Scale 66 (60), Octopunch 103 (100), Nautilus Strike 105 (103), Roll of the Dice 74 (66), Crossbones 115 (ours 107), Time Leap 125 (ours 115),
  Sea Serpent's Rage 117 (110), Raging Serpent Assault 120 (110), Quick Motion 15 (10), Shadow Heart 10 (15).  A Lv117 character does NOT own Time Leap (125), Raging Serpent Assault (120) or — if the site is right — Crossbones would be fine (115).
- Maple Hero: game table gives Corkscrew Blow **40%** (ratio 40/60 of Serpent Assault's 60%, f23) — now closable (the "truncated text" gap is resolved).
- Missing masteries: Octopunch - Reuse -30% cd @134; Roll of the Dice - Attack +5%p @90; Serpent Scale - Persistence (+5s Assault) @94 and Stack (+1 scale) @104 are in the duty-cycle function (levels 94/104 ok);
  Groggy Mastery FD +5%/5s @98 (conditional); Time Leap - Grant (+10%p own FD boost) @138.
- Serpent Scale "+2% FD per scale, up to 5 stacks" (pre-Assault) is not modeled (stated in the row note).
- Nautilus Strike - Final Attack uses the LITERAL percent reading (850% -> 8500 tenths) — consistent with Blizzard/Meteor FA.
[CONFIRMED by game table] Hook Bomber chain; Corkscrew Blow 3400/f12 cd21 (+80% @73); Octopunch 9000/f12 x3 (+2 on boss) cd16 (+50% @108); Nautilus Strike 19500/f12 x5, 15 targets, cd33 (+50% @126);
  Nautilus FA 30%/1s; Sea Serpent's Rage +100% @122, Raging Serpent Assault +50% @130; Groggy FD 8%/f22; Roll of the Dice mean 2.5% (f22); Time Leap FD 15% (patched).

---------------------------------------------------------------------------------------------------
## CORSAIR  (no wiki Mastery page; masteries in ours were "role-mapped" from Buccaneer — the site now gives the real table)
[OURS-WRONG]
- Blackboot Bill - Damage is **+50% @73** (ours +80, role-mapped from Corkscrew Blow).
- Missing real masteries: Scurvy Summons - Dual Pistol Crew damage +50% @49; Siege Bomber - Damage +50% @82 (and Setup @68: +1 cannon, first cast cd -15s); All Aboard - Sharpshooter Crew damage +50% @78;
  All Aboard - Strike Interval -30% (both crews) @94; Rapid Fire - Damage +70% @130; Broadside - Bombardment @118 (all attacks become 1900% x3 on 8 targets) and Setup @138; Swift Fire - Weaken @54 (+3%/strike, max 3 stacks);
  Roll of the Dice +5%p @90; Fullmetal Jacket DefPen @98; Ahoy Mateys - FD +20% for 20s after Scurvy Summons @122 (this one IS modeled).
- Ahoy Mateys is a Lv107 passive giving Dual Pistol Crew +250% FD and Sharpshooter Crew +100% FD with **factorIndex 21** (table); ours helper = factor 22 and unlock 120.
- factorIndex: Majestic Presence is **21** (ours 12); Jolly Roger FD is **21** (ours 22). Majestic Presence also has a 0.5s internal cooldown (table + site "cd 0.5 sec"); ours has none.
- Unlock levels (site req): Swift Fire 33 (ours 35), Scurvy Summons 35 (40), All Aboard 69 (45), Siege Bomber 63 (66), Blackboot Bill 66 (63), Brain Scrambler 103 (100), Nautilus Strike 105 (103),
  Rapid Fire 117 (107), Majestic Presence 120 (125), Ahoy Mateys 107 (120), Quickdraw 125 (117), Roll of the Dice 74 (66), Agile Guns 40 (33), Infinity Blast 45 (40), Quick Motion 15 (10), Shadow Heart 10 (15).
- Quickdraw (Lv125): "every 3rd Eight-Legs Easton doubles its damage (table: a second 5800 line) and cuts Brain Scrambler/Rapid Fire cooldown 1.5s" — unmodeled (known). Table shows the doubling is a real second damage line.
[CONFIRMED by game table] Eight-Legs Easton chain levels; Swift Fire 1800/f12 17s (+50% @39), 8 targets; Brain Scrambler 29000/f12 x2 cd18 (+100% @108); Nautilus Strike; Rapid Fire 18000/f12 x7 cd17 9 targets;
  Blackboot Bill 1700/f12 x4 9 targets cd23; Majestic Presence 1800%, 25%, 6 targets; Broadside cd 20s (5000% burst, 330% every 2s sustained); Siege Bomber cd 22s; Maple Hero 20/40/80;
  Cross Cut Blast 12%/f22, Fullmetal Jacket 10%/f22, Infinity Blast 12%/f22.

---------------------------------------------------------------------------------------------------
## CROSS-CLASS AUTOMATED CHECKS (added at the end)
- (baseDamage, factorIndex) tuple scan of every workbook row against the game tables found these factorIndex mismatches (all listed above under their class): Paladin Guardian/Divine Blessing/HP Recovery (22 -> 21),
  Buccaneer Sea Serpent's Rage (12 -> 21), Crossbones (22 -> 21), Time Leap (22 -> 21), Serpent Scale FD (22 -> 21), Corsair Majestic Presence (12 -> 21), Jolly Roger (22 -> 21), Ahoy Mateys (22 -> 21),
  Shadower Assassinate (21 -> 12), **FP-Mage Meditation (22 -> 21; IL/Bishop use 21 correctly)**.
- Buccaneer/Corsair first-job rows store the site's game-capture numbers as if they were level-1 values (Corsair Shadow Heart 54 vs table 50, Quick Motion 65 vs 60, Double Shot 29.4%; Buccaneer Quick Motion 61, Somersault 26.6%).
  The game table's level-1 values are 50 / 60 / 26%. These are Magic-Critical-pattern rows baked into Inputs, so only the Skill-Level-Bonus Sensitivity delta is affected (minor).
- UNLOCK_LEVEL tables vs the site's `reqLevel`: matches everywhere except Night Lord (Mark of Assassin 43 vs ours 40; Venom 74 site/table vs ours 72 [wiki 72]) and the Buccaneer/Corsair lists above.
- Per-level curves: `FactorTable` F12/F21/F22/F23 == site `skillLevelFactors` for levels 1-300 in all 12 workbooks (checked on Bowmaster; the table is generated from one shared JSON, so identical everywhere).

---------------------------------------------------------------------------------------------------
## USER DECISIONS (2026-10-21) — authoritative; apply these when fixing
 1. Sharp Eyes: site/game table is truth -> Crit Damage only, REMOVE the +20 Crit Rate (Bowmaster + Marksman).
 2. Concentration: site -> 7 stacks; apply per-level scaling (game table factor 22).
 3. Mortal Blow: site -> 50 hits.
 4. Arrow Platter: keep 50% at level 1. Evidence: site's 97.7% == 50% x F12 at skill level 191 (F12(191)=1955), i.e. the site number was captured at a high skill level, not level 1.
 5. Quiver Cartridge tick: site wording -> interval improves by up to 0.4 SEC (1s -> 0.6s at the AS cap).
 6. Illusion Step: site/table -> Attack 28% (280, f22) at Lv118+ mastery semantics: attack does not disappear and is doubled during Illusion Step (i.e. table value 280 is the doubled one; base 140 = 14%).  (confirm when implementing)
 7. Snipe-Empowered 5700, DK Spectral Shadows 2200, Bowmaster Drain 1050: enter as LITERAL percent (x10 vs current tenths entries) to match Blizzard/Meteor/Nautilus FA.
 8. Cross Over Chains / Hex: evidence = site and wiki both say plain "%" while every other additive-points mastery says "%p" (25 other examples) -> RELATIVE (x2 / x1.5), not +100/+50 points. (Pending user confirmation; user said values looked inflated.)
 9. Hero Puncture/ERB: align by NAMES: Puncture-Damage +50% @108, ERB-Damage +50% @122, Puncture-Weaken @134 (damage-taken effect +50% per site), ERB combo FD +50%/excess stack @138.
10. IL/FP masteries L126-138: need in-game text (see reply).
11. FP Flame Sweep tiers: pending explanation/test.
12. Take the SITE's data: Shadow Partner 60%, Shadow Shifter = Final Damage, Night Lord Venom unlock 74, Magic Crash weaken 10%, Scaring Sword 25%. (Quad Star cd and Combo Attack chance: site text and site game table disagree with each other — pending.)
13. Bishop Triumph Feather: 18s cooldown on the angel-power window.

## USER DECISIONS, ROUND 2 (2026-10-21)
10. In-game mastery texts (user-provided):
    FP: Flame Haze-Burn @126 = fire skills inflict Flame Haze Burn with 5% chance (ours 5% OK); Ifrit-Burn Damage @130 = +20% per Burn (ours OK); Meteor Shower-Damage @134 = +50% (ours OK);
        Ifrit-Persistence & Target @138 = +10s duration, +3 targets (ours OK).  => FP L126-138 needs NO change (my "Ifrit L126 +5s/+1" finding was a wiki/site garble — IGNORE it).
    IL: Frozen Orb-Strike Interval @126 = -0.2 SEC (0.5s -> 0.3s) [ours: x0.5 @134 -> CHANGE]; Blizzard-Damage @134 = +50% to Blizzard AND Blizzard Final Attack [ours: +40% @130 -> CHANGE, and FA row must get it too];
        Elquines-Damage&Target @138 = +50%, +3 targets [ours OK]; Elquines-Strike Interval @130 = unknown to user. Wiki only has an orphaned line "Decreases the Elquines strike interval by 0.2%" (shown under the L126 row);
        an earlier session recorded the user confirming "20%, not 0.2%" -> proposal: -20% (4s -> 3.2s) at L130 (names say 130, ours currently 126).
11. Flame Sweep-style damage chains: OPTION A (every tier is its own add-on; 10+11+12+13+14+15 = 75% at max) is correct for ALL classes. The delta convention ({10,1,1,1,1,1}) in the other 11 classes is a BUG
    (CLAUDE.md structural-bug #2 is wrong and must be reversed). FP-Mage already correct. Fix: use raw {102:10,106:11,116:12,120:13,128:14,132:15} (Bowmaster/Marksman/NL: new levels 102/106/116/120/128/132).
12. Where the site contradicts itself, take table+wiki: Quad Star cooldown 10s; Hero Combo Attack chance 40%.
    Poison Breath / Elemental Drain: user's in-game values (363% / 19.8% @ Lv163) == game table (200% x F12, 12% x F21) -> table/wiki right, site text (160%/8%) wrong; ours already correct. (Poison Breath's +70% mastery is on top.)
Other answers:
 - Paladin Parashock Guard Lv98 mastery: user says it is "+10% more for the skill used, NOT a passive baked into Inputs" -> model the +10%p as a live Attack% term (not baked in Inputs).
 - FP Poison Mist fog interval mastery: -50% (0.8s -> 0.4s) = ours, keep.
 - FP Flame Haze burst: 3 lines of damage = ours (3 hits), keep.
 - FP Mist Eruption: explosions happen when a target dies AND when the fog ends -> 4 on normal monsters, 1 on boss = ours, keep.
 - Corsair Quickdraw second effect (every 3rd Easton doubled; -1.5s on Brain Scrambler/Rapid Fire): MODEL IT (do not skip); level-gate at 125.
