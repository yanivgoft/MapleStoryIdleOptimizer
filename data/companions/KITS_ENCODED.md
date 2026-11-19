# Encoded companion kits (generated from src/companion_kits.py - review against your sheet)

Every row below is what the workbook's CompanionKits sheet contains.  `[action]` = the cast uses one action slot.  Rows marked _ASSUMED_ / TO CONFIRM need your answer.


## Wind Archer

- `basic` (basic, Lv1): 290% x5 lines on 6 targets
- `fd_lv5` (stat, Lv5): fd +25% (companion)  - _universal companion Final Damage skill_
- `fd_lv8` (stat, Lv8): fd +25% (companion)  - _universal companion Final Damage skill_
- `fd_lv10` (stat, Lv10): fd +25% (companion)  - _universal companion Final Damage skill_
- `special` (hit, Lv1): 465% x15 lines  - _15 spirit arrows on summon (310% x1.5 expected), 1 random target each_
- `trifling` (echo, Lv1): 465% x3 lines  - _Trifling Wind: 3 spirit arrows per skill activation (incl. the summon special)_
- `vortex` (hit, Lv1): cd 19s [action] stun 1.2s 2300% x2 lines on 8 targets  - _Spiraling Vortex (stun 1.2 s)_
- `pinpoint` (hit, Lv1): cd 18s [action] 2500% x2 lines  - _Pinpoint Pierce 1550% + 3450% on one target (avg 2500% x2 lines)_
- `pinpoint_debuff` (stat, Lv1): cd 18s dur 8s dmg_taken +25% (monster)  - _the second arrow's target takes +25% damage for 8 s_
- `song` (hit, Lv4): cd 25s [action] 780% x13 lines on 4 targets  - _Song of Heaven, 13 arrows_
- `song_cb` (echo, Lv4, g_ct=CB): cd 25s 465% x2 lines  - _[Chapter Boss] 2 spirit arrows per Song cast_
- `storm` (proc, Lv3): 35% per any attack, icd 0.5s: 750% x1 on 5 targets  - _Storm Bringer_
- `storm_cb` (echoproc, Lv3, g_ct=CB): 465% x2 lines  - _[Chapter Boss] 2 spirit arrows per giant arrow_
- `whispers` (stat, Lv1): atk +15% (player+companion)  - _Whispers of the Wind: +15% Attack, companion and player_
- `windwalk` (stat, Lv2): fd +15% (companion)  - _Wind Walk: companion Final Damage +15%_
- `windwalk_cb` (stat, Lv2, g_ct=CB): fd +5% (player)  - _[Chapter Boss] player Final Damage +5% while summoned_

## Dawn Warrior

- `basic` (basic, Lv1): 290% x5 lines on 6 targets
- `fd_lv5` (stat, Lv5): fd +25% (companion)  - _universal companion Final Damage skill_
- `fd_lv8` (stat, Lv8): fd +25% (companion)  - _universal companion Final Damage skill_
- `fd_lv10` (stat, Lv10): fd +25% (companion)  - _universal companion Final Damage skill_
- `event_fd` (stat, Lv1): fd +25% (companion)  - _event passive (assumed always on)_
- `sum_atk_p` (stat, Lv1): dur 10s atk +15% (player)  - _summoning effect: player Attack +15% for 10 s_
- `sum_atk_c` (stat, Lv1): atk +15% (companion)  - _summoning effect: companion Attack +15% for the summoning duration_
- `sum_cd_p` (stat, Lv1): dur 10s crit_dmg +15% (player)  - _summoning effect: player Crit Damage +15% for 10 s_
- `sum_cd_c` (stat, Lv1): crit_dmg +15% (companion)
- `a1_1` (hit, Lv1): cd 15s [action] 710% x2 lines  - _dark matter 710% x2 on 1 target_
- `a1_2` (hit, Lv1): cd 15s 1120% x3 lines on 6 targets  - _then explodes 1120% x3 on 6 targets_
- `a2_hi` (dot, Lv1, g_hp=ge50): cd 20s dur 10s tick 0.3s [action] 230% x1 lines  - _meteor shower 230% every 0.3 s for 10 s, 1 random target_
- `a2_lo` (dot, Lv1, g_hp=lt50): cd 20s dur 10s tick 0.3s 690% x1 lines  - _x3 damage when the target HP is below 50%_
- `a3` (hit, Lv4): cd 23s [action] stun 1.5s 1800% x3 lines on 10 targets  - _1800% x3 on 10 targets, stun 1.5 s_
- `a3_lo` (hit, Lv4, g_hp=lt50): cd 23s 5000% x1 lines on 10 targets  - _if the target HP is below 50%: +5000% after 5 s_
- `a3_taken` (stat, Lv4, g_hp=lt50): cd 23s dur 10s dmg_taken +10% (monster)  - _and +10% damage taken for 10 s_
- `p1` (proc, Lv1): 50% per basic attack, icd 0s: 220% x2 on 6 targets  - _Basic Attack: 50% for 220% x2 on 6 targets_
- `p2` (stat, Lv1): skill_dmg +20% (player+companion)
- `p3` (stat, Lv2): fd +5% (player+companion)
- `p4` (stat, Lv3): def_pen +15% (companion)
- `p4_lo` (stat, Lv3, g_hp=lt50): def_pen +15% (companion)  - _doubled against a boss below 50% HP_

## Blaze Wizard

- `basic` (basic, Lv1): 290% x5 lines on 6 targets
- `fd_lv5` (stat, Lv5): fd +25% (companion)  - _universal companion Final Damage skill_
- `fd_lv8` (stat, Lv8): fd +25% (companion)  - _universal companion Final Damage skill_
- `fd_lv10` (stat, Lv10): fd +25% (companion)  - _universal companion Final Damage skill_
- `event_fd` (stat, Lv1): fd +25% (companion)  - _event passive (assumed always on)_
- `sum_taken` (stat, Lv1, g_ct=notBT): dur 30s dmg_taken_n +10% (monster)  - _summoning effect: non-boss enemies take +10% for 30 s_
- `sum_taken_bt` (stat, Lv1, g_ct=BT): dur 30s dmg_taken_n +30% (monster)  - _[Chapter Breakthrough] applied x3 = +30%_
- `a1` (hit, Lv1, g_ct=notBT): cd 9s [action] 920% x5 lines on 7 targets  - _fire pillars 920% x5 on 7 targets_
- `a1_bt` (hit, Lv1, g_ct=BT): cd 9s [action] 920% x5 lines on 14 targets  - _[Breakthrough] max targets x2_
- `a2` (hit, Lv1, g_ct=notBT): cd 16s [action] stun 1.5s 1170% x3 lines on 12 targets  - _phoenix 1170% x3 on 12 targets, stun 1.5 s_
- `a2_bt` (hit, Lv1, g_ct=BT): cd 16s [action] stun 4.5s 1170% x3 lines on 12 targets  - _[Breakthrough] stun 1.5 s x3 = 4.5 s (user, 2026-11-14)_
- `a3` (dot, Lv4, g_ct=notBT): cd 12s dur 5s tick 0.5s [action] 430% x1 lines on 12 targets  - _fire orb 430% every 0.5 s for 5 s on 12 targets_
- `a3_bt` (dot, Lv4, g_ct=BT): cd 12s dur 5s tick 0.5s [action] 860% x1 lines on 12 targets  - _[Breakthrough] damage doubled_
- `p1_p` (stat, Lv1): atk +12% (player)
- `p1_c` (stat, Lv1): atk +20% (companion)
- `p2` (proc, Lv1, g_ct=notBT): 50% per basic attack, icd 2s: 300% x2 on 8 targets  - _Basic Attack: 50% for 300% x2 on 8 targets, 2 s cooldown_
- `p2_bt` (proc, Lv1, g_ct=BT): 50% per basic attack, icd 0.5s: 300% x2 on 8 targets  - _[Breakthrough] 0.5 s cooldown_
- `p3_n` (stat, Lv2): norm_dmg +8% (player+companion)
- `p3_b` (stat, Lv2): boss_dmg +8% (player+companion)  - _when a boss monster is present: Boss Monster Damage +8% (and Normal +8% more)_
- `p4` (stat, Lv3): skill_dmg +25% (companion)
- `p4_bt` (stat, Lv3, g_ct=BT): skill_dmg +25% (player)  - _[Breakthrough] player Skill Damage +25% in battle_

## IL Mage

- `basic` (basic, Lv1): 290% x5 lines on 6 targets
- `fd_lv5` (stat, Lv5): fd +25% (companion)  - _universal companion Final Damage skill_
- `fd_lv8` (stat, Lv8): fd +25% (companion)  - _universal companion Final Damage skill_
- `fd_lv10` (stat, Lv10): fd +25% (companion)  - _universal companion Final Damage skill_
- `special` (hit, Lv1): stun 3s 300% x5 lines on 10 targets  - _summoning effect 300% x5 on 10 targets, freezes 3 s_
- `a1` (stat, Lv1): cd 30s dur 15s [action] atk +20% (player+companion)  - _Attack +20% companion and player for 15 s_
- `a2` (dot, Lv1): cd 15s dur 10s tick 2s [action] 600% x3 lines on 8 targets  - _lightning ball 600% x3 on 8 targets every 2 s for 10 s_
- `a3` (dot, Lv4): cd 30s dur 5s tick 0.5s [action] 800% x1 lines on 10 targets  - _frost breath 800% every 0.5 s for 5 s on 10 targets_
- `a3_taken` (stat, Lv4): cd 30s dur 5s dmg_taken +15% (monster)
- `p3` (stat, Lv2): norm_dmg +15% (player)
- `p4` (dot, Lv3): tick 5s 800% x3 lines on 5 targets  - _frost spears every 5 s: 800% x3 on 5 targets_

## FP Mage

- `basic` (basic, Lv1): 290% x5 lines on 6 targets
- `fd_lv5` (stat, Lv5): fd +25% (companion)  - _universal companion Final Damage skill_
- `fd_lv8` (stat, Lv8): fd +25% (companion)  - _universal companion Final Damage skill_
- `fd_lv10` (stat, Lv10): fd +25% (companion)  - _universal companion Final Damage skill_
- `special` (hit, Lv1): 300% x5 lines on 10 targets  - _summoning effect 300% x5 on 10 targets_
- `special_taken` (stat, Lv1): dur 10s dmg_taken +25% (monster)  - _and +25% damage taken for 10 s_
- `a1` (dot, Lv1): cd 15s dur 10s tick 1s [action] 300% x1 lines on 10 targets  - _poison fog 300% every 1 s for 10 s (cooldown 15 s: user)_
- `a1_taken` (stat, Lv1): cd 15s dur 10s dmg_taken +15% (monster)
- `a2` (hit, Lv1): cd 17s [action] 600% x3 lines on 5 targets  - _meteors 600% x3 on 5 targets (cooldown 17 s: user)_
- `a3` (dot, Lv4): cd 30s dur 30s tick 4s [action] 3500% x1 lines on 3 targets  - _Ifrit 30 s, 3500% every 4 s on 3 targets (cooldown 30 s: user)_
- `p1` (stat, Lv1): atk +15% (player)
- `p2` (dot, Lv1): tick 1s 100% x3 lines on 3 targets  - _wall of fire, 100% every 1 s on 3 targets; modelled like the regular FP-Mage: 3 walls up for the whole summon (user 2026-11-12)_
- `p3` (stat, Lv2): fd_pt +3% (companion)  - _Final Damage +3% per nearby target up to 10 (1 target on a boss)_
- `p4` (dot, Lv3): cd 15s dur 10s tick 5s 2000% x1 lines on 10 targets  - _the fog explodes every 5 s: 2000% on 10 targets (only while the fog exists)_

## Bishop

- `basic` (basic, Lv1): 290% x5 lines on 6 targets
- `fd_lv5` (stat, Lv5): fd +25% (companion)  - _universal companion Final Damage skill_
- `fd_lv8` (stat, Lv8): fd +25% (companion)  - _universal companion Final Damage skill_
- `fd_lv10` (stat, Lv10): fd +25% (companion)  - _universal companion Final Damage skill_
- `a1` (stat, Lv1): cd 15s dur 10s [action] atk +15% (player)  - _recovery skill; Attack +15% while HP >= 30% (assumed true) for 10 s_
- `a2` (stat, Lv1): cd 27s dur 15s [action] atk +20% (player)  - _Attack +20% for 15 s_
- `a3` (hit, Lv4): cd 11s [action] 650% x6 lines on 10 targets  - _pillar of light 650% x6 on 10 targets (cooldown 11 s: user)_
- `p1` (stat, Lv1): max_dmg +24% (player)
- `p2` (stat, Lv1): fd +8% (player+companion)  - _Final Damage +8% for 5 s when MP >= 50% after the 2 s recovery (assumed always) - applies to the player AND the companion (user, 2026-11-12)_
- `p3` (proc, Lv2): 20% per any attack, icd 3s: 2600% x1 on 7 targets  - _angel: 20% for 2600% on 7 random targets, 3 s cooldown_
- `p4_cd` (stat, Lv3): crit_dmg +40% (player+companion)  - _per 10% of current HP +4% crit damage (full HP assumed: x10)_
- `p4_as` (stat, Lv3): as +20% (player+companion)  - _and +2% attack speed per 10% HP_

## Night Walker

- `basic` (basic, Lv1): 290% x5 lines on 6 targets
- `fd_lv5` (stat, Lv5): fd +25% (companion)  - _universal companion Final Damage skill_
- `fd_lv8` (stat, Lv8): fd +25% (companion)  - _universal companion Final Damage skill_
- `fd_lv10` (stat, Lv10): fd +25% (companion)  - _universal companion Final Damage skill_
- `a1_1` (hit, Lv1): cd 14s [action] stun 1s 1400% x1 lines on 7 targets  - _shuriken 1400% on up to 7 enemies in front_
- `a1_2` (hit, Lv1): cd 14s 2100% x1 lines on 7 targets  - _explosion along its path 2100% on up to 7_
- `a2` (stat, Lv1): cd 21s dur 8s [action] atk +40% (player)  - _player Attack +40% for 8 s_
- `a3` (stat, Lv4): cd 23s dur 15s [action] fd +10% (player)  - _player Final Damage +10% for 15 s_
- `p1` (proc, Lv1): 30% per any attack, icd 0s: 500% x1  - _30% for +500% on the target_
- `p2` (proc, Lv1): 50% per any attack, icd 1s: 600% x1  - _50% for +600% on the target, 1 s cooldown_
- `p3` (stack, Lv2): as +5% (player), 0% per skill attack, 2s, max 5 stacks  - _each companion skill activation: player Attack Speed +5% for 2 s, up to 5 stacks_
- `p4` (proc, Lv3): 30% per any attack, icd 0s: 800% x1  - _30% for +800% on the target_

## Hero

- `basic` (basic, Lv1): 290% x5 lines on 6 targets
- `fd_lv5` (stat, Lv5): fd +25% (companion)  - _universal companion Final Damage skill_
- `fd_lv8` (stat, Lv8): fd +25% (companion)  - _universal companion Final Damage skill_
- `fd_lv10` (stat, Lv10): fd +25% (companion)  - _universal companion Final Damage skill_
- `a1` (hit, Lv1): cd 22s [action] stun 2s 2400% x1 lines on 7 targets  - _2400% on 7 targets in front, stun 2 s_
- `a2` (hit, Lv1): cd 9s [action] 750% x4 lines on 8 targets  - _750% x4 on 8 targets_
- `a3` (hit, Lv4): cd 19s [action] 1100% x3 lines on 5 targets  - _1100% x3 on 5 targets near the main target_
- `a3_def` (stat, Lv4): cd 19s dur 10s mon_def +10% (monster)
- `a3_taken` (stat, Lv4): cd 19s dur 10s dmg_taken +10% (monster)
- `p2` (stack, Lv1): atk +5% (player+companion), 40% per any attack, 10s, max 5 stacks  - _combo: Attack +5% per stack for 10 s, 40% per attack, up to 5_
- `p4` (stat, Lv3): fd +15% (companion)

## Paladin

- `basic` (basic, Lv1): 290% x5 lines on 6 targets
- `fd_lv5` (stat, Lv5): fd +25% (companion)  - _universal companion Final Damage skill_
- `fd_lv8` (stat, Lv8): fd +25% (companion)  - _universal companion Final Damage skill_
- `fd_lv10` (stat, Lv10): fd +25% (companion)  - _universal companion Final Damage skill_
- `a1` (hit, Lv1): cd 18s [action] 2300% x1 lines on 7 targets
- `a1_def` (stat, Lv1): cd 18s dur 10s mon_def +10% (monster)
- `a2` (hit, Lv1): cd 25s [action] 3900% x1 lines on 8 targets
- `a2_taken` (stat, Lv1): cd 25s dur 10s dmg_taken +10% (monster)
- `a3` (stat, Lv4): cd 30s dur 10s [action] fd +8% (player+companion)
- `p1` (stat, Lv1): mon_def +10% (monster)  - _nearby targets -10% defense_
- `p2` (stack, Lv1): crit_dmg +15% (player+companion), 15% per basic attack, 10s, max 1 stacks  - _basic attack: 15% for crit damage +15% for 10 s_
- `p3` (stat, Lv2): cd 10s dur 6s atk +10% (player)  - _barrier every 10 s lasting 6 s: Attack +10% while active_
- `p4_bad` (stat, Lv3): bad +15% (player)
- `p4` (proc, Lv3): 35% per basic attack, icd 5s: 650% x4 on 4 targets  - _divine brand 650% x4 on 4 targets_

## Dark Knight

- `basic` (basic, Lv1): 290% x5 lines on 6 targets
- `fd_lv5` (stat, Lv5): fd +25% (companion)  - _universal companion Final Damage skill_
- `fd_lv8` (stat, Lv8): fd +25% (companion)  - _universal companion Final Damage skill_
- `fd_lv10` (stat, Lv10): fd +25% (companion)  - _universal companion Final Damage skill_
- `a2` (hit, Lv1): cd 18s [action] 2100% x1 lines on 12 targets  - _rush: 2100% on 12 targets in the path_
- `a3` (hit, Lv4): cd 17s [action] stun 2s 3600% x1 lines on 5 targets  - _rock explosion 3600% on 5 targets, stun 2 s (cooldown 17 s: user)_
- `p1` (stat, Lv1): as +25% (companion)  - _companion attack speed +25%_
- `p2` (stat, Lv1): dmg_taken +15% (monster)  - _Evil Eye: 6 nearby targets take +15% (applied to all hits here)_
- `p3` (proc, Lv2): 20% per any attack, icd 3s: 290% x6 on 8 targets  - _Evil Eye Shock_
- `p4` (proc, Lv3): 100% per any attack, icd 5s: 1000% x2  - _Revenge brand 1000% x2, 5 s cooldown_

## Bow Master

- `basic` (basic, Lv1): 290% x5 lines on 6 targets
- `fd_lv5` (stat, Lv5): fd +25% (companion)  - _universal companion Final Damage skill_
- `fd_lv8` (stat, Lv8): fd +25% (companion)  - _universal companion Final Damage skill_
- `fd_lv10` (stat, Lv10): fd +25% (companion)  - _universal companion Final Damage skill_
- `sum_as` (stat, Lv1): dur 20s as +20% (player)  - _summoning effect: player Attack Speed +20% for 20 s_
- `a1` (hit, Lv1): cd 13s [action] 1000% x3 lines  - _retreats and attacks 3 times, 1000% each_
- `a1_def` (stat, Lv1): cd 13s dur 10s mon_def +15% (monster)
- `a2` (dot, Lv1): cd 30s dur 20s tick 3s [action] 1400% x1 lines on 3 targets  - _Phoenix 20 s, 1400% every 3 s on 3 targets, cooldown 30 s (user, 2026-11-12)_
- `a3` (hit, Lv4): cd 23s [action] 800% x20 lines  - _20 arrows, 800% each_
- `p1` (stat, Lv1): crit_rate +15% (player+companion)
- `p2` (dot, Lv1): tick 1s 145% x1 lines  - _magic arrow 145% every 1 s on a random nearby target_
- `p2_taken` (stat, Lv1): dmg_taken +5% (monster)  - _and +5% damage taken for 3 s (refreshed every second)_
- `p3` (stack, Lv2): atk +1.5% (companion), 10% per any attack, 10s, max 100 stacks  - _each strike: 10% for Attack +1.5% for 10 s, up to 100 stacks (user, 2026-11-12)_
- `p4` (ramp, Lv3): def_pen +1% (companion), ramp lin  - _def pen +1% per second, no cap_

## Marksman

- `basic` (basic, Lv1): 290% x5 lines on 6 targets
- `fd_lv5` (stat, Lv5): fd +25% (companion)  - _universal companion Final Damage skill_
- `fd_lv8` (stat, Lv8): fd +25% (companion)  - _universal companion Final Damage skill_
- `fd_lv10` (stat, Lv10): fd +25% (companion)  - _universal companion Final Damage skill_
- `a1` (hit, Lv1): cd 13s [action] 1000% x3 lines
- `a2` (hit, Lv1): cd 16s [action] stun 1s 1300% x3 lines on 8 targets
- `a3` (hit, Lv4): cd 12s [action] stun 2s 4200% x1 lines  - _marks the target; the next cast on it stuns 2 s_
- `p1` (stat, Lv1): crit_rate +15% (player+companion)
- `p3` (stat, Lv2, g_ct=notPvP): fd +20% (companion)
- `p3_pvp` (stat, Lv2, g_ct=PvP): fd +40% (companion)  - _x2 in Arena (PvP)_

## Night Lord

- `basic` (basic, Lv1): 290% x5 lines on 6 targets
- `fd_lv5` (stat, Lv5): fd +25% (companion)  - _universal companion Final Damage skill_
- `fd_lv8` (stat, Lv8): fd +25% (companion)  - _universal companion Final Damage skill_
- `fd_lv10` (stat, Lv10): fd +25% (companion)  - _universal companion Final Damage skill_
- `special_n` (hit, Lv1, g_br=nonboss): 300% x4 lines on 8 targets  - _summoning effect 300% x4 on 8 targets_
- `special_b` (hit, Lv1, g_br=boss): 900% x4 lines  - _x3 against a boss_
- `a1` (hit, Lv1): cd 11s [action] 1100% x3 lines on 10 targets  - _1100% x3 on 10 targets_
- `a1_dot` (dot, Lv1): cd 11s dur 10s tick 1s 100% x1 lines on 10 targets  - _then 100% every 1 s for 10 s_
- `a1_def` (stat, Lv1): cd 11s dur 10s mon_def_b +15% (monster)  - _boss: defense -15% (duration 10 s, user 2026-11-12)_
- `a2` (hit, Lv1): cd 10s [action] 1300% x4 lines
- `a3_n` (stat, Lv4): cd 30s dur 20s [action] dmg_taken_n +10% (monster)
- `a3_b` (stat, Lv4): cd 30s dur 20s dmg_taken_b +20% (monster)  - _boss: the damage-taken effect is doubled_
- `p2` (stat, Lv1): boss_dmg +15% (player)
- `p3` (ramp, Lv2): fd +1.5% (companion), ramp exp cap 15s  - _Final Damage x1.015 per second up to 15 s_
- `p4` (proc, Lv3, g_br=boss): 35% per any attack, icd 0s: 1000% x1  - _when the companion attacks a boss: 35% for 1000%, no cooldown_

## Shadower

- `basic` (basic, Lv1): 290% x5 lines on 6 targets
- `fd_lv5` (stat, Lv5): fd +25% (companion)  - _universal companion Final Damage skill_
- `fd_lv8` (stat, Lv8): fd +25% (companion)  - _universal companion Final Damage skill_
- `fd_lv10` (stat, Lv10): fd +25% (companion)  - _universal companion Final Damage skill_
- `special` (hit, Lv1): 580% x5 lines  - _summoning effect 580% x5 on 1 target_
- `a2` (hit, Lv1): cd 19s [action] stun 2s 650% x3 lines on 8 targets
- `a3` (hit, Lv4): cd 13s [action] stun 1s 1400% x2 lines  - _vital point 1400% x2_
- `a3_fin` (hit, Lv4): cd 13s 3000% x1 lines  - _finishing blow +3000% (30% to stun 1 s)_
- `p1` (stat, Lv1): crit_dmg +15% (player)
- `p2` (stat, Lv1): as +15% (player)
- `p4` (stunhit, Lv3): 5000% x1 lines  - _a target that gets stunned/frozen takes 5000%_

## Buccaneer

- `basic` (basic, Lv1): 290% x5 lines on 6 targets
- `fd_lv5` (stat, Lv5): fd +25% (companion)  - _universal companion Final Damage skill_
- `fd_lv8` (stat, Lv8): fd +25% (companion)  - _universal companion Final Damage skill_
- `fd_lv10` (stat, Lv10): fd +25% (companion)  - _universal companion Final Damage skill_
- `sum_as` (stat, Lv1): dur 15s as +15% (player+companion)
- `sum_cd` (stat, Lv1): dur 15s crit_dmg +15% (player+companion)
- `a1_p` (stat, Lv1): cd 25s dur 12s [action] fd +15% (player)
- `a1_c` (stat, Lv1): cd 25s dur 12s fd +30% (companion)  - _also: Serpent Assault 100% chance for the duration_
- `a2` (hit, Lv3, g_br=nonboss): cd 16s [action] 900% x3 lines on 4 targets  - _Octopunch (Lv3) 900% x3 on 4 targets_
- `a2_b` (hit, Lv3, g_br=boss): cd 16s 900% x5 lines  - _boss: the same damage 2 more times_
- `p1_cr` (stat, Lv1): crit_rate +15% (player)  - _Lv1 passive: player crit rate +15%_
- `p1_cd` (stat, Lv1): crit_dmg +10% (player)
- `p2` (proc, Lv1-1): 40% per basic attack, icd 3s: 1050% x3 on 9 targets  - _Sea Serpent Burst (replaced at Lv2); Assault 100% during the Lv1 active_
- `p4` (proc, Lv2): 50% per basic attack, icd 3s: 1750% x3 on 12 targets  - _Serpent Assault replaces it at Lv2_
- `p5` (hit, Lv3): cd 16s 1700% x2 lines on 8 targets  - _Lv3: with Octopunch a sea serpent adds 1700% x2 on 8 targets_
- `p5_mark` (stat, Lv3): cd 16s dur 10s dmg_taken +15% (monster)  - _assault mark: +15% damage taken for 10 s_

## Corsair

- `basic` (basic, Lv1): 290% x5 lines on 6 targets
- `fd_lv5` (stat, Lv5): fd +25% (companion)  - _universal companion Final Damage skill_
- `fd_lv8` (stat, Lv8): fd +25% (companion)  - _universal companion Final Damage skill_
- `fd_lv10` (stat, Lv10): fd +25% (companion)  - _universal companion Final Damage skill_
- `special` (hit, Lv1): stun 3s 300% x5 lines on 10 targets  - _summoning effect 300% x5 on 10 targets, stun 3 s_
- `a1` (dot, Lv1): cd 25s dur 20s tick 3s [action] 950% x2 lines  - _dual pistol crew 20 s: 950% x2 every 3 s_
- `a2` (dot, Lv1): cd 15s dur 30s tick 2.5s [action] 1200% x1 lines on 4 targets  - _fixed cannon 30 s, 1200% every 2.5 s on 4 targets (a second cannon stacks)_
- `a3` (hit, Lv4): cd 20s [action] 3800% x2 lines on 5 targets  - _battleship 3800% x2 on 5 targets_
- `a3_dot` (dot, Lv4): cd 20s dur 30s tick 3s 3300% x1 lines on 5 targets  - _then 3300% every 3 s for 30 s (targets in front: 5, user 2026-11-12)_
- `p1` (stat, Lv1): as +10% (player+companion)
- `p2` (stat, Lv1): atk +10% (companion)
- `p3` (dot, Lv2): tick 4s 1000% x3 lines on 3 targets  - _Sharpshooter crew every 4 s: 1000% x3 on 3 targets_
- `p4` (stat, Lv3): skill_dmg +15% (player+companion)
