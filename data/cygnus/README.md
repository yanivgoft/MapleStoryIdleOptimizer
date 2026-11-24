# Cygnus classes: in-game source data

Each class has a `<class>_ingame.md` transcribed (by read-only agents, reviewed by the user) from the user's screenshots, which stay OUTSIDE the repository:
`/Users/yaniv/private/night_walker`, `/Users/yaniv/private/Blaze_Wizzard` (Skills/ pop-ups + 2 unlock grids, Masteries/ pop-ups). Dawn Warrior's source is the text in KNOWN_GAPS / `engine/data/dawn_warrior.py`.

## Method (see CLAUDE.md "Adding an engine-native class", memory `cygnus-engine-native-classes`)
* The game shows `trunc_1dp(base x factor[idx][total level])`. Level-1 pop-ups (fresh characters: "Lv. 1") give the BASE exactly (factor 1.0) but say nothing about the growth curve `idx` (1..23, `data/factor_table.json`).
* Where the curve comes from: (1) the site's job-skill-impact table (`data/ref_maplestoryidle_info/site_job_skill_impact_all.json`: has Night Walker with factorIndex for ~22 skills, NO Blaze Wizard); (2) conventions proven on Dawn Warrior:
  burst damage 12, basic attack / active buffs and debuffs 21, passives 22, per-skill-FD helper (Call of Cygnus) 23; (3) sibling classes.
* A curve that is only a convention is PROVISIONAL until the user provides a higher-level reading (displayed value + total level) for that skill; then base and idx are resolved uniquely (same method as Dawn Warrior).
* Unlock levels were read from two Skill-window grids with icons only: the icon -> skill assignment is BY ORDER and must be confirmed by the user.
* Not modelled in any class: basic attacks below level 100 (e.g. Night Walker's Lucky Seven / Triple Throw / Quad Star), MP costs.
* New classes stay `PUBLISHED = False` until the scaling is confirmed (see CLAUDE.md).
