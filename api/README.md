# api/ - stateless FastAPI layer over `engine/`

Pure HTTP wrapper: no database, no sessions.  Everything a request needs is in the request.

```
GET  /api/health
GET  /api/classes                                  [{id, name, family, stat_identity, artifacts_modelled, status}]  (every class, discovered from engine/classes/*.py - the first 12 are workbook-verified, the Cygnus classes engine-native;
                                                   status = {companions, artifacts, stat_values}: what is modelled)
GET  /api/classes/{id}/schema                      engine schema(): fields (label/group/type/unit/default/applicable/options/computed), dps_rows, artifacts
GET  /api/classes/{id}/defaults?content_type=...   workbook defaults resolved for a content type
POST /api/classes/{id}/compute                     body: inputs dict -> engine result (total_dps, boss_dps, normal_dps, skills, companion, derived, ...)
POST /api/classes/{id}/sensitivity                 body: the compute inputs + optional which / companion_comparison_level / artifact_stars -> stat values (below); 501 for classes without them
GET  /api/classes/{id}/sensitivity/meta            stat list (key, label, type, step, semantic note), artifact toggle list, parts, CDR milestones, metric definitions
GET  /api/classes/{id}/cubes/meta                  slots, rarities, stat options per slot, pity caps (Potential vs Bonus Potential), milestones + the equipment-compare and artifact-potential tables
POST /api/classes/{id}/cubes                       body: the compute inputs + gear (+ only) -> cube optimizer rows (below); 501 for classes without stat values
POST /api/classes/{id}/equipment-compare           body: the compute inputs + current / new equip -> Total DPS gain of each, delta
POST /api/classes/{id}/artifact-potentials         body: the compute inputs + potentials -> DPS gain of every artifact potential line, per artifact total
GET  /api/docs                                     Swagger UI
```

A class is any `engine/classes/<id>.py` exposing `compute`, `defaults`, `schema`; it appears at startup (a module that fails to import is
logged and skipped).

## Compute inputs and validation

Body = flat inputs dict (`schema().fields[].key`).  Missing keys take the content type's defaults; `null` on a numeric field reads as 0; fields
that do not apply to the content type are forced to `null`; computed fields are ignored; unknown keys are rejected.  An optional
`"artifacts": [{"key": <id or display name or "(none)">, "star": 0..5|"Not Unlocked"|null}, ...]` (<= 5 slots = `schema.artifacts.max_slots`; the workbooks have 4, see `engine/README.md` "Fifth artifact slot") is accepted for classes whose
schema says `artifacts_modelled`; for every other class `artifacts` gets a clear
`422 {field: "artifacts", message: "artifacts are not modelled for this class yet"}`.  Types/enums/ranges are checked against the schema (`api/validation.py`): numeric bounds are each field's own `min` / `max`
(`engine/common/schema.py` `FIELD_BOUNDS`, deliberately permissive; a blank Level / PvP Fight Length is 'is required'); `chapter_stage` may also arrive as a JSON number; bad input gives

```json
422 {"detail": "Invalid inputs", "errors": [{"field": "level", "message": "must be between 1 and 300"}, ...]}
```

An engine failure is `500 {"detail": "computation failed for these inputs"}` (the traceback goes to the log only).  Other statuses: 404 unknown
class, 413 body too large, 429 rate limited (+ `Retry-After`).

## Stat values (`/sensitivity`)

`POST /api/classes/{id}/sensitivity` runs `engine.sensitivity.run` on the validated inputs (same body and validator as `/compute`, including `artifacts`) and returns its
result: `baseline_total`, `normal_weight` and the requested parts `stats` (27 rows: `current`, `new`, `dps_gain`, `pct_gain`, `units_per_1pct` = units of the stat for +1% DPS,
**lower = more valuable per unit**, `null` = n/a), `artifacts` (36 equip toggles + ranking), `companions`, `summon_time`, `cdr`.  Extra optional body keys (everything else is a
compute input): `which` (non-empty list of `stats | artifacts | companions | summon_time | cdr`, default all; the UI asks for `stats` first and the rest lazily),
`companion_comparison_level` (whole number, level of every companion in the comparison table; default: the chosen companion's level), `companion_levels` (`{companion name: 0..18}`, 0 = not unlocked, a
companion left out takes `companion_comparison_level` / the chosen companion's level; the web Companions tab sends all 16), `companion_potential_lines_pct` (number >= 0: summoning-time % of boots lines already
inside `companion_summon_time_increase_pct`; the `summon_time` table measures against none of them) and `artifact_stars` (`{artifact id: 0..5 |
"Not Unlocked" | null}`, stars of artifacts that are not equipped).  NaN / inf become `null`.

* `501 {"detail": "stat values are not modelled for this class yet"}` for classes without a sensitivity module (checked before validation; `GET .../sensitivity/meta` too).  The
  capability is `engine.sensitivity.supports(class_module)` if the engine grows one, else `registry.SENSITIVITY_CLASSES` (today `("fp_mage",)`; the single place to extend);
  it also drives `status.stat_values` in `GET /api/classes`.
* Validation errors are the same `422 {"detail": "Invalid inputs", "errors": [{field, message}]}` (extra keys included: `which`, `companion_comparison_level`, `companion_levels.<name>`, `companion_potential_lines_pct`, `artifact_stars.<id>`).
* A call costs ~0.5-1 s, so: its own per-IP limit (`MSI_RATE_LIMIT_SENS_PER_MIN`, default 20 per window, on top of the general limit; cache hits count too), an in-memory LRU+TTL result
  cache keyed by a hash of (class, canonical validated inputs, extras) - response header `X-Cache: HIT | MISS` -, at most `MSI_SENS_WORKERS` (2) evaluations at a time and a
  `504 {"detail": "stat values took longer than N s; try again"}` guard after `MSI_SENS_TIMEOUT_S` (the worker thread cannot be killed; it finishes in the background and its result is
  discarded).  `GET .../sensitivity/meta` is static, cheap and not part of the sensitivity limit.

## Cubes, Equipment compare, Artifact potentials

Same capability gate as `/sensitivity` (`registry.SENSITIVITY_CLASSES`, today FP-Mage; the stat prices come from the sensitivity module): every other class answers
`501 {"detail": "... is not modelled for this class yet"}` on all four routes (checked before validation), and the web tabs show "not available for this class yet".  All three bodies
are the compute inputs (same validator, incl. `artifacts`) plus extra keys (anything else is a compute input; 422 `{detail: "Invalid inputs", errors: [{field, message}]}` as everywhere).
The code is `api/features.py` (validation, meta, pricing caches, the three computations); the maths is `engine/cubes.py`, `equipment.py`, `potentials.py`.

* `GET .../cubes/meta` (static, cheap, not rate limited with the others): `slots` [{key, label}] (15), `potential_types`, `rarities` [{key, label}] (`normal` .. `mystic`), `stats` (every stat selectable on a line),
  `stats_by_slot` (what the slot can roll; Skill Cooldown Decrease only on the hat, Buff Duration Increase only on the belt, like the other slot-exclusive lines), `roll_values` {`ALL` | slot: {rarity: {line `1`..`3`: {stat: [[value, prime], ...]}}}} (the values a line can show, prime first then descending: the pool shared by every slot once + each slot's own additions, ~18 KB / ~2 KB gzipped; a client merges `ALL` and the slot), `pity_caps` {Potential | Bonus Potential: {rarity: cap}} (**separate tables**, CLAUDE.md item 17), `upgrade_rates`, `milestones` (24 cube counts), `max_cubes`,
  `csv_columns`, `limits`, `equipment` {stats (21), lines (5)} and `artifact_potentials` {rarities, stats, values {stat: {rarity: value}}, line_min_star, artifacts [{key, label, rank, lines, default_star}]}.
* `POST .../cubes`: extra keys `gear` = list of `{slot, potential_type: "Potential"|"Bonus Potential", rarity: normal|rare|epic|unique|legendary|mystic (case-insensitive), pity: whole number >= 0,
  lines: [{stat, value} x <= 3]}` (any row may be omitted = normal, pity 0, no lines; a (slot, type) pair once; stats from `meta.stats` or "(none)"; values 0 .. 1e6) and `only` = which rows to compute (slot ids
  = both tracks, and / or `{slot, potential_type}` objects; default all 30).  The engine always sees the whole gear (the other rows' summoning-time lines move the pricing), `only` just limits the work, so the UI
  asks a few slots at a time and shows rows as they arrive.  Answer: `{class_id, baseline_total, milestones, csv_columns, backend, notes, rows: [engine.cubes.recommend row: slot, potential_type, rarity, pity, lines,
  current_value(_pct), line_loss[3] / line_loss_pct[3] / row_loss(_pct) (real DPS lost by removing one held line / the row's lines), smallest_n, n_for_50pct, n_for_75pct, milestone_ev{n}, milestone_ev_pct{n}, ev_pct_by_cubes[0..max_cubes]]}` in the script's CSV order (Potential first, then Bonus Potential, each by smallest N, never-positive last);
  `ev_pct_by_cubes` (added 2026-11-24, 6 significant digits, index n = EV as % of Total DPS after n cubes) lets the web app price an exact typed cube count without another request (~8 KB per row: a 6-row chunk grows from ~9 KB to ~57 KB, gzip from ~3.7 KB to ~24.5 KB; clients fall back to the milestones when it is absent).  `null` = not reached within `max_cubes`.  A character's prices (sensitivity stats + CDR + summon-time parts, ~1 s) are built once and cached, so every later chunk of the same character costs only its own rows
  (~0.2 s per row without numpy; the full 30 rows ~3-6 s).  Results are cached PER ROW (key = hash of class, validated inputs, the gear's total summoning-time %, the row's own state and the summoning time on the
  other rows) in an LRU+TTL cache: `X-Cache: HIT` (all rows cached) / `PARTIAL` / `MISS`; editing one slot re-computes only that slot.
* `POST .../equipment-compare`: extra keys `current` / `new` = `{attack: number >= 0 (the fixed Attack line), lines: [{stat, value} x <= 5]}` (stats from `meta.equipment.stats` or "(none)").  Answer: the engine's
  `compare` (`current` / `new` {rows (6: stat, value, gain, first, group, factor), total_gain, pct}, `delta_pct`, `delta_dps`, `better`) + `baseline_total`, `crit_rate_total`, `crit_priced_as_crit_damage`
  (Critical Rate priced as Critical Damage at a live crit total >= 100% unless Ring of Cycles / Book of Ancient is equipped) and `rate_by_stat`.
* `POST .../artifact-potentials`: extra key `potentials` = `{artifact id: {star?: 0..5 | "Not Unlocked" | null, lines: [{rarity: Rare|Epic|Unique|Legendary|Mystic|Mystic (Prime), stat}]}}` (<= 2 lines for Epic /
  Unique artifacts, 3 for Legendary; line n counts from star 1 / 2 / 5; an artifact in `artifacts` takes its slot's star unless the entry has its own `star`; unlisted artifacts are at the workbook default).  Answer:
  `{class_id, baseline_total, rows: [engine.potentials.potential_table row for all 36 artifacts: key, label, rank, equipped, star, lines [{rarity, stat, active, gain}], total]}`.  The `total`s are exactly what
  `engine.sensitivity` takes as `inputs["artifact_potential_gain"]`.  **`include_potentials` on `/sensitivity` was deliberately NOT added**: it would need a second stats run inside every sensitivity call and change
  that endpoint's cache key; the client can show both numbers side by side instead (`/sensitivity` stays byte-for-byte as before; an unknown key there is still a 422).
* Protections: `/cubes` has its own per-IP limit (`MSI_RATE_LIMIT_CUBES_PER_MIN`, 20: a full UI Calculate is 5 requests; cache hits count), its own worker pool (`MSI_CUBES_WORKERS`, 2 evaluations at a time, the rest queue)
  and `504 {"detail": "cube optimizer took longer than N s; try again"}` after `MSI_CUBES_TIMEOUT_S` (45; the worker thread finishes in the background, a timed-out chunk is not cached).  `equipment-compare` and
  `artifact-potentials` are cheap once the character's stat prices are cached (the live UI calls them while you type), so they share a looser per-IP limit (`MSI_RATE_LIMIT_COMPARE_PER_MIN`, 60); a cache miss runs one
  sensitivity `stats` pass in the sensitivity worker pool under `MSI_SENS_TIMEOUT_S` (504 `equipment compare took longer than ...`).  500 never leaks a trace; 429 carries `Retry-After`.

## Configuration (environment)

| variable | default | meaning |
|---|---|---|
| `PORT` | 8080 (Docker) | listen port (Cloud Run sets it) |
| `MSI_CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | comma list of allowed origins (`*` = any) |
| `MSI_RATE_LIMIT_PER_MINUTE` | 120 | per-IP sliding window on `/api/*` except health; 0 disables (in memory, per instance) |
| `MSI_RATE_LIMIT_WINDOW_S` | 60 | window length |
| `MSI_MAX_BODY_BYTES` | 65536 | request body cap |
| `MSI_RATE_LIMIT_SENS_PER_MIN` | 20 | per-IP limit of `POST .../sensitivity` (same window as above); 0 disables |
| `MSI_SENS_CACHE_ENTRIES` | 128 | LRU size of the sensitivity result cache; 0 disables |
| `MSI_SENS_CACHE_TTL_S` | 600 | lifetime of a cached sensitivity result |
| `MSI_SENS_TIMEOUT_S` | 30 | request guard of `/sensitivity` (504 after this) |
| `MSI_SENS_WORKERS` | 2 | sensitivity evaluations running at the same time |
| `MSI_RATE_LIMIT_CUBES_PER_MIN` | 20 | per-IP limit of `POST .../cubes` (same window); 0 disables |
| `MSI_RATE_LIMIT_COMPARE_PER_MIN` | 60 | per-IP limit of `POST .../equipment-compare` and `.../artifact-potentials`; 0 disables |
| `MSI_CUBES_CACHE_ENTRIES` | 256 | LRU size of the per-row cube result cache (a full call = 30 rows); 0 disables it and the pricing caches |
| `MSI_CUBES_CACHE_TTL_S` | 600 | lifetime of a cached cube row / character pricing |
| `MSI_CUBES_TIMEOUT_S` | 45 | request guard of `/cubes` (504 after this) |
| `MSI_CUBES_WORKERS` | 2 | cube evaluations running at the same time |
| `MSI_PROXY_HOPS` | 0 | trusted reverse proxies in front; >0 reads the client IP from `X-Forwarded-For` (verify the right count on Cloud Run before relying on it) |
| `MSI_LOG_LEVEL` | INFO | one JSON line per request (`event`, `id`, `method`, `path`, `status`, `ms`, `ip`) on stdout |
| `MSI_INCLUDE_UNPUBLISHED` | unset | `1` = also serve the classes whose engine module exports `PUBLISHED = False` (classes under development). Unset (production, the Docker image, `deploy/`) = they are hidden: not in `GET /api/classes`, every `/api/classes/<id>/...` route answers 404 `unknown class`, `/api/health` does not count them. `tests/run_all.py` and `api/tests/conftest.py` set it so such a class is still tested; `web/scripts/gen_fixtures.py --include-unpublished` sets it for fixture generation |

## Run / test

```bash
python3 -m venv .venv && .venv/bin/pip install -r api/requirements-dev.txt
.venv/bin/uvicorn api.main:app --reload --port 8000          # from the REPOSITORY ROOT
.venv/bin/python -m pytest api/tests -q                      # FP-Mage golden + validation/limits/CORS (test_api.py); every class the API lists: list, schema, defaults x10 content types,
                                                             # compute, companions, artifacts 422, golden totals (test_all_classes.py); stat values (test_sensitivity.py): golden vs the engine,
                                                             # which / options, 501, meta, cache hit + expiry, own rate limit, validation, 500 / 504;
                                                             # cube features (test_cubes.py): golden vs engine.cubes / equipment / potentials, meta, 501, validation, row cache, own limits, 500 / 504, worker cap
```

## Docker (Cloud Run)

`api/Dockerfile` (python:3.11-slim) must be built with the repository root as context:
`docker build -f api/Dockerfile -t msi-api .`  It copies `engine/`, the three `src/` modules the engine imports (`companion_kits`,
`companion_python_model`, `status_timeline`), `data/factor_table.json`, `data/cube_potential_data.json` (the cube roll tables) and the API modules (`cache`, `features`, `main`, `middleware`, `registry`, `settings`, `validation`), and runs `uvicorn` on `$PORT`.  The ignore rules
are in `api/Dockerfile.dockerignore` (BuildKit's per-Dockerfile ignore file; a builder that only reads a `.dockerignore` at the context
root needs that file copied there).  Not built or run so far.
