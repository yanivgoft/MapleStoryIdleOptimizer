# Golden refresh log

Every line below is a refresh of golden JSON files FROM THE CURRENT ENGINE (`python3 tests/golden/update_goldens.py ... --write --reason "..."`).

**A refreshed golden pins the ENGINE's own behaviour.** The goldens were originally frozen from the Excel verify scripts / workbooks (independent implementations
of the model); once a value has been refreshed here it is no longer an independent workbook value, only a regression pin of the engine as it was at the commit in
the table.  Review every refresh like a code change (the dry-run summary shows which fields moved and by how much).  The JSON files carry no refresh marker: this
table is the only provenance.  `HEAD` is the git commit the engine was built on; `+dirty` = uncommitted changes under engine/ at the time.

| date | class | kind | HEAD | cases changed | values changed | max rel diff | reason |
|---|---|---|---|---|---|---|---|
| 2026-11-23 | dawn_warrior | snapshot | 40ab345+dirty | 320 | 320 | 0.000e+00 | engine-native snapshot: pins the engine, no independent source; CREATED; initial engine-native snapshot of Dawn Warrior (in-game numbers verified by the displayed-value test); pins the engine |
| 2026-11-24 | night_walker | snapshot | 474f927+dirty | 330 | 330 | 0.000e+00 | engine-native snapshot: pins the engine, no independent source; CREATED; initial snapshot after scaling confirmed by the user's readings |
| 2026-11-24 | dawn_warrior | snapshot | 474f927+dirty | 3 | 82 | 1.000e+00 | engine-native snapshot: pins the engine, no independent source; growth curves extended past level 300 (linear continuation, confirmed by Night Walker readings at total level 322) |
| 2026-11-25 | dawn_warrior | snapshot | 55a5804+dirty | 2 | 66 | 2.592e-05 | engine-native snapshot: pins the engine, no independent source; cube pricing: Skill Cooldown Decrease / Buff Duration / Summoning Time priced on the real model at the exact totals (engine/cubes.py ExactCurve, 2026-11-25) instead of the CDR-table interpolation / linear rate (C/CH-late-nocomp milestone EVs move <= 2.6e-5 relative), plus the new per-row line_loss / row_loss fields (cube snapshot rows) |
| 2026-11-25 | night_walker | snapshot | 55a5804+dirty | 2 | 34 | 1.700e-09 | engine-native snapshot: pins the engine, no independent source; cube pricing: Skill Cooldown Decrease / Buff Duration / Summoning Time priced on the real model at the exact totals (engine/cubes.py ExactCurve, 2026-11-25) instead of the CDR-table interpolation / linear rate (C/CH-late-nocomp milestone EVs move <= 2.6e-5 relative), plus the new per-row line_loss / row_loss fields (cube snapshot rows) |
