# Porting guide: Companions + Status Effect Damage / KO timeline (FP-Mage reference -> the other 11 classes)

> **STATUS (2026-11-18): the port is COMPLETE for all 12 classes** (FP-Mage reference + Hero, ILM, Bowmaster, Paladin, Dark Knight, Buccaneer, Corsair, Marksman, Night Lord, Shadower, Bishop),
> back-ports of the Sensitivity-block recipe (last section) applied everywhere, and the companion cast-timing rule rolled out (see CLAUDE.md). This file is kept as the recipe for any
> future class or for re-porting; the `git diff HEAD -- src/build_fp_mage_workbook.py` references below describe the original FP-Mage-vs-HEAD diff and no longer apply once committed -
> use the finished builders (e.g. `src/build_shadower_workbook.py`, `src/build_bishop_workbook.py`) as the template instead.

FP-Mage is the reference implementation (finished and verified 2026-11-14).  Everything below is already in
`src/build_fp_mage_workbook.py` / `src/verify_fp_mage_workbook.py`; the port copies and adapts it into one other class's
`src/build_<class>_workbook.py` / `src/verify_<class>_workbook.py`.

Reference diff (this is the port recipe):
    git diff HEAD -- src/build_fp_mage_workbook.py     # ~800 lines of builder changes
    git diff HEAD -- src/verify_fp_mage_workbook.py    # ~250 lines
Start by running `patch -p1 -F3` of that diff (with the file name rewritten) on the target builder - roughly half the hunks apply as is, the
rest are class-specific and need manual adaptation.  Read KNOWN_GAPS.md "Companions" and "Status Effect Damage, KO phases ..." sections and
CLAUDE.md first.

## Shared, class-agnostic modules (DO NOT edit these in a class port; report needed changes instead)
* `src/companion_kits.py`     - all 16 companions' kits as data rows
* `src/companion_model.py`    - Excel formula generator of the companion chain (`cells(host)`); the HOST dict is the class interface
* `src/companion_python_model.py` - plain-Python mirror (`run(host, choice, lvl, inc)`) used by verify scripts and the cube script
* `src/status_timeline.py`    - Status Effect / KO timeline engine (`solve` = Python reference, `cells` = Excel strip generator, `Layout`)
* `src/potential_cubes_ev.py` - generic cube EV script (class folders hold identical copies; copy `src/` -> class folder at the end)
After a port, copy `src/companion_kits.py src/companion_python_model.py src/potential_cubes_ev.py` into the class folder (already done for old versions).

## What a class port must contain (checklist; names are FP-Mage's, mirror them)
1. Inputs: new row `status_effect_damage` right after `normal_damage` (rows below shift by one; add the SELF-DETECTING migration in
   `load_existing_workbook_state` - see FP), row `companion_choice` (+ dropdown), `companion_summon_time_increase_pct` becomes live (label).
   Keep `IN` row numbers consistent; check every hard-coded row number in the builder / verify script.
2. Sheets: `CompanionKits` (data), `Companion` (host + chain, cmp columns, b0+X pot columns, exported host values), `CompanionsInput`
   (levels + comparison + potential-line table), `Timeline` (status engine strip).  Sheet order as in FP `main()`.
3. Companion host: `companion_host_main()` / `companion_host_export()` / block host in `build_stat_block`: the class's own pipeline numbers:
   `unit` (= Calc!N/F of the Basic Attack row), `bad`/`sd` buckets, `aps`, `avgbuff`, `attack_bucket_avg`, `avgbuff_snap`, Hexagon/Chalice/
   Charm/Horn terms, `boss_pct`/`norm_pct`, `extra_boss`/`extra_norm` (Reindeer's Spear / Contract of Darkness / boss-only FD composition),
   crit/min/max/defense/def_pen/taken_bucket, `player_boss`/`player_norm`/`player_uniform_boss`/`player_basic_*`.  Class-specific multipliers
   that are part of "the player's snapshot" (e.g. a class buff that is a separate factor in Summary) must be in `avgbuff` AND in `avgbuff_snap`.
4. Calc: columns W (timing factor boss), X (normal), Y (per-cast boss damage); `apply_status_columns`; rate overrides for DoT / eruption-like rows
   (`STATUS_FS_KEYS`), `R` (casts) overridden by the engine's counts, Summary `R_AVGBUFF` and `R_STARTUP_TIME` engine hooks.
   Per-cast weights (Calc!Y) must NOT depend on cast counts (circular reference otherwise).
5. Engine spec: `STATUS_BUFFS` (class buffs that matter: Attack% buffs 'atk', Final Damage ramps 'ramp'), `STATUS_GROUPS` (every cooldown skill with
   its burst / dot / end-of-window rows), `STATUS_UNIFORM_ROWS` (rows spread uniformly: basic, procs, ...).  Derive them from the class's own
   SKILL_ROWS; rows whose damage depends on special class mechanics keep their own formulas and only get the timing factor.
6. Totals: Summary Total / boss-only / normal-only totals and the Per-Skill breakdown include the companion; Sensitivity blocks include the companion
   chain + strip (`STATUS_REBUILD_KEYS` blocks re-run their own strip; others read the main strip).
7. Horn Flute: `artifact_horn_flute_expr(eq, content, star, uptime)` with `Companion!horn_uptime` (damage share), `horn_avg`/`horn_full` host keys.
8. Sensitivity: STAT_SWEEP entries `status_effect_damage` (after normal_damage) and `companion_summon_time_increase_pct`; Companion Comparison
   table, summoning-time breakdown table, `COMPANION_POT_*` mapping for the potential-line stat; `STATUS_STRIPS_START` row allocation.
9. verify script: the engine (`status_timeline.solve`) + companion mirror, `timing_factors`, `blend_branches` factors, ENGINE_N overrides for casts.
10. Docs: KNOWN_GAPS (class section), README sheet line, the class's own notes.

## Pitfalls already paid for (do not rediscover)
* Excel formula cap is 8192 characters: after building, scan every sheet for the longest formula (FP: Companion <= 6400, Sensitivity <= 7500).
  Same-sheet refs must be unqualified inside the Companion sheet (the main column uses `$B$row`).
* A formula that INDEXes a range containing its own cell is a circular reference (Excel; `formulas` silently drops it).  Use ranges that end on the previous row.
  Run `data/porting/helpers/cyc.py <workbook.xlsx>` (static cycle detector) after every build: must print `cyclic components 0`.
* Excel `0^0` = `#NUM!` (the `formulas` package returns 1): the companion's `cap` is floored at 1 because "max enemies in range" is blank in boss/PvP content.
* Per-cast engine weights must not read R / BAPS / cast counts; `apply_status_columns` in a Sensitivity block must run AFTER the block's buff-uptime
  definitions (phase factor uses the block's own bucket average).
* Boss/normal weight rule (user): a weight is a weight on RELATIVE gains (ratio blend), never dollar totals; companion tables use `companion_weighted_ratio`.
* Hero Dungeon is timed: stun does NOT extend it (only Chapter Breakthrough has the extension); both have the normal-then-boss phase split.
* `status_timeline._dp` / the Excel `take` cells now use a 1e-9 relative tie tolerance (found by the Hero port: exact ties between buff placements were resolved differently by Excel and Python).
* Re-run-own-strip blocks (`STATUS_REBUILD_KEYS`) must ALSO include every artifact equip toggle that feeds the strip's Attack% bucket or Charm profile: Charm of the Undead, Old Music Box, Secret Map, Reindeer's Spear, Alliance Badge, Bottle of Emotion (plus Hexagon); otherwise their Sensitivity rows read the main strip and come out wrong (Charm: -1.8k vs +78k true in Hero).
* Stats the class sweeps that change cast times / buff windows (CDR, buff duration, status effect, companion summon time, Hexagon equip, Shamaness Marble)
  need their own strip in the Sensitivity block (`STATUS_REBUILD_KEYS`).
* `sv.py` clears artifact slots (verify scripts do not model artifacts); hand-check artifacts separately (Hexagon/Charm/Horn Flute) with equipped copies.

## Verification checklist (every class)
1. Build: zero error cells in a `formulas` evaluation (`NOSENS` copy) for several contents; cycle detector clean; longest formula < 8192.
2. `python3 data/porting/helpers/sv.py <ClassDir> <suffix> --set=content_type=... --set=companion_choice=... --set=companion_level=10 --set=status_effect_damage=...`
   prints `... OK` (verify script == workbook) for at least: Chapter Boss, World Boss, Enhancement Dungeon (KO engine), Breakthrough, Hero Dungeon,
   Chapter Hunt, an EXP/Equipment dungeon, PvP - with a stunning companion (Blaze Wizard / Wind Archer) and one without (Bow Master).
3. Sensitivity-vs-main (`helpers/sens_comp.py`, ~1.5 h per run, run ONCE at the end): World Boss + Breakthrough, keys `damage,status_effect_damage,
   skill_cooldown_decrease,companion_summon_time_increase_pct` -> `ALL OK`.
4. Hand checks with artifacts equipped (Hexagon + Charm + Horn Flute): Horn Flute equip gain plausible; Sensitivity row == total delta of the toggled copy.
5. Class-specific: every row that exists only in this class (summons, stacks, specials) still equals its pre-port value in contents where the engine is off
   (Chapter Hunt) - compare Summary totals before/after the port with the companion set to "None" and status effect 0 in a steady-state content.

## Dev helpers (data/porting/helpers/, copies of the /tmp tools used for FP)
* `sv.py`          verify script vs workbook for any class (see above).  Copies the workbook, so it is safe to run while others build.
* `cyc.py`         static circular-reference detector.
* `sens_comp.py`   Sensitivity block total vs full-model re-evaluation (usage in its docstring; env WB/CT/COMP/CLVL/SED/ARTS/KEEP).
* `test_strip.py`/`hosts.py`  standalone engine strip vs Python reference (synthetic).
A `formulas` evaluation of a full workbook takes 6-40 minutes and several GB: run ONE evaluation at a time per agent, never rebuild a workbook while
a `sens_comp.py` run on it is in progress (it re-reads the file per key).

## The PLAYER's own stunning skills (added 2026-11-14; Hero is the reference implementation, see `git diff` of src/build_hero_workbook.py / verify_hero_workbook.py)
User rule: skills that stun/freeze are modelled as stun windows too (Status Effect Damage applies, and in Chapter Breakthrough they lengthen the boss phase,
exactly like the companion's stuns; Hero Dungeon is timed - no extension).  Game data (site tables, patched):
| class | skill (Calc row) | cooldown | stun | notes |
|---|---|---|---|---|
| Hero | Rush | 22 s (Reuse mastery Lv90 -30% already in Calc!Q) | 2.5 s, 12 targets | |
| Paladin | Rush | 22 s | 2.5 s | |
| Dark Knight | Rush; Evil Eye Shock | 22 s; 18 s | 2.5 s; 1.5 s | Evil Eye Shock needs the Evil Eye summon (assume it is up) |
| Ice-Lightning | Glacier Wall | 22 s (Reuse Lv90 -30%) | freeze 2 s | Frost (slow) from Freezing Effect is NOT a stun |
| Bishop | Angel Ray | 17 s | 1 s | |
| Bowmaster | Covering Fire | 19 s | 1 s | stun comes from the Lv49 mastery (`min_level=49`) |
| Marksman | Covering Fire; Bolt Burst; Frostprey | 19 s; 21 s; 60 s | 1 s (Lv49); 1.5 s (Lv98 mastery); Frostprey freezes 1 s with 10% chance every 1.5 s for 30 s | Frostprey = `typ="periodic"` (tick 1.5, win 30, p 0.1) |
| Night Lord | Gust Charm | 24 s | 2 s | |
| Shadower | Phase Dash | 23 s | 2 s | |
| Corsair | Blackboot Bill | 23 s | 2 s | |
| Buccaneer | Corkscrew Blow | 21 s | 1.8 s | |
| FP-Mage | - | - | - | no stunning skill |
Wiring (all shared machinery already exists):
1. `STATUS_PLAYER_STUN = [dict(id=..., row=<Calc row key>, typ="cast"|"periodic", dur=..., p=1.0, [tick, win], [min_level])]` in the builder.
2. `stl.player_stun_entries(STATUS_PLAYER_STUN, cell, t0, level_expr)` -> host key `"pst"` in `companion_host_main()` (t0 = Summary startup cell), in the block host
   (block-local cells, `startup_ref`) and, with t0 "0", `pl_stun=` in `status_engine_host`; the engine groups of those casts get `fixed=True, t0="0"` (cast on cooldown, not optimised).
3. `companion_host_export()` appends `stl.player_stun_export(h["pst"])` (the cube script rebuilds `pst` from the exported pst<k>_* values).
4. verify script: build `PST` numeric entries (same cooldowns incl. level-gated masteries, `t0` = startup unless the engine is on), put them in the stub host and `comp_host["pst"]`,
   combine `stun_vector = min(1, companion + stl.pl_stun_vector(PST, T, NB))`, mark the same groups fixed, and run the companion mirror also when the companion is "None" but a player stun exists
   (its Breakthrough extension still counts).  `hasstun` is also true when any player stun skill is unlocked.
Verified shapes: engine content (World Boss) with fixed stun group, Breakthrough with companion None (player extension), Chapter Hunt (uniform factor).

## Gap found by the Buccaneer port (apply in every port; the earlier ports FP-Mage/Hero/Ice-Lightning/Bowmaster/Paladin/Dark Knight need the back-port)
1. A Sensitivity block's own companion chain pins candidate 0 to the summon time the main sheet chose (`fixed_s`, `fixed_tend`, `fixed_e`), but the strip's stun vector uses candidate-0 timing (`s_0`, `W_0`).  When
   the chosen summon is not candidate 0 (default World Boss: earliest summon 7 s) the block's stun windows differ from the main strip.  Fix: re-running blocks must read the main sheet's `s_0` / `W_0`
   (`companion_main_ref("s_0")`, `("W_0")`) for the stun vector (and `Tend_0` where used); only the Summoning-Time block keeps its own.
2. The Hexagon and Horn Flute equip toggles change what the candidate summon times are worth: those two blocks must run the full 3-candidate search (not `fixed_s`).  Same for any other toggle
   that changes the companion's snapshot value (Charm/Attack% toggles feed the snapshot: check with the toggled-copy test).
3. Any other block can still diverge if the chosen candidate flips between the base and the swept value (documented limitation).
Check with the toggled-copy test for Hexagon, Charm, Horn Flute and with the `status_effect_damage` / CDR blocks (ratio must be 1.00000000).
4. (Corsair port) Skill Cooldown Decrease changes cast timing, so the CDR block and the CDR-milestone blocks must ALSO run the full 3-candidate search (ratio was 0.99972562 at World Boss with `fixed_s`, 1.00000000 with the full search).
   Full list needing the full search: Hexagon, Horn Flute, Summoning Time, Skill Cooldown Decrease (+ its milestone blocks).
5. Known engine limits (shared, not class bugs): different skills may be cast in the same 1-second bin; whole-bin cooldown spacing under-casts fractional cooldowns (Corsair Quickdraw); DoT windows are truncated at fight end (averaged model only truncated the last cast), so engine-on totals differ from the old averaged ones by design (document the % shift per class).
