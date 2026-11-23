# Running the web app locally

Two processes: the stateless API (`api/`, FastAPI over `engine/`) and the static front end (`web/`, React + Vite).

## 1. API (port 8000)

```bash
python3 -m venv .venv
.venv/bin/pip install -r api/requirements-dev.txt
.venv/bin/uvicorn api.main:app --reload --port 8000      # run from the repository root
# http://localhost:8000/api/health   http://localhost:8000/api/docs
```

All 12 classes are served (engine/__init__.py `CLASSES`).  Classes appear automatically: every `engine/classes/<id>.py` exposing `compute` / `defaults` / `schema` is served.  Config via `MSI_*`
environment variables (CORS origins, rate limits, body-size cap, stat-values cache / timeout): see `api/README.md`.

Stat values: `POST /api/classes/{id}/sensitivity` (+ `GET .../sensitivity/meta`) is served for all 12 classes (`registry.SENSITIVITY_CLASSES`; a class outside that list would answer 501 and show `status.stat_values: false`).  It costs ~0.5-1 s, so it has its own per-IP limit (`MSI_RATE_LIMIT_SENS_PER_MIN`, 20), an in-memory LRU+TTL cache (`MSI_SENS_CACHE_ENTRIES` 128,
`MSI_SENS_CACHE_TTL_S` 600; `X-Cache` header), `MSI_SENS_WORKERS` (2) parallel evaluations and a `MSI_SENS_TIMEOUT_S` (30) guard (504).

Companions tab: `POST .../sensitivity` also accepts the extra keys `companion_levels` ({companion name: 0-18}, 0 = not unlocked) and `companion_potential_lines_pct` (summoning-time % of boots lines already
inside the Inputs value); the web **Companions** tab owns the per-companion levels (the Calculator's companion dropdown lists only the companions you own there; see `web/README.md`).

Cubes, Equipment compare and artifact potentials: `GET .../cubes/meta`, `POST .../cubes`, `POST .../equipment-compare`, `POST .../artifact-potentials` - same gate as stat values (all 12 classes; a class outside `SENSITIVITY_CLASSES` would answer 501; the
web tabs say "not available for this class yet").  `/cubes` (a full 30-row call is ~3-6 s; the UI asks 6 rows at a time) has its own per-IP limit (`MSI_RATE_LIMIT_CUBES_PER_MIN`, 20), worker pool (`MSI_CUBES_WORKERS`, 2),
timeout (`MSI_CUBES_TIMEOUT_S`, 45 -> 504) and per-row LRU+TTL cache (`MSI_CUBES_CACHE_ENTRIES` 256, `MSI_CUBES_CACHE_TTL_S` 600; `X-Cache: HIT | PARTIAL | MISS`); the two live ones share `MSI_RATE_LIMIT_COMPARE_PER_MIN` (60).
Details in `api/README.md`.

Artifacts: the game has **5 artifact slots** (2026-11-23); `schema.artifacts.max_slots` = 5 and `inputs.artifacts` accepts up to 5 equipped artifacts (a 6th entry is a 422 "at most 5 slots").  The Excel workbooks keep 4 slot
rows, so results with 5 equipped are the engine's own composition of the verified per-artifact effects (see `engine/README.md`); up to 4 equipped stay bit-exact with the workbooks.  The web **Artifacts** tab is one
table of all 36 artifacts (star level, potential lines + gains; see `web/README.md`) and the artifacts you have equipped are an input of the Calculator tab (an "Equipped artifacts" section with 5 slot dropdowns, one set PER CONTENT TYPE, saved with the profile); its equip ranking sends `artifact_stars` (the star of every artifact) with the sensitivity request.

## 2. Web (port 5173)

```bash
cd web
npm install
npm run dev            # http://localhost:5173, uses VITE_API_URL (default http://localhost:8000)
# or, without the API:   npm run dev:mock   (all 12 classes from src/fixtures; numbers only scale with Flat ATTACK / companion choice;
#                         the Stat values tab shows each stat-values class's fixed fixture, the cube tabs serve real-engine fixtures, equipment / potential edits are recomputed)
```

## Tests

```bash
.venv/bin/python -m pytest api/tests -q        # API: all 12 classes (list, schema, defaults, compute, companions, golden totals), validation, limits, CORS, stat values and cube features (golden vs engine, 501, cache, own rate limits, timeouts)
python3 tests/golden/test_fp_mage.py           # engine vs golden (engine's own tests)
(cd web && npm test && npm run build)          # front end: formatter, form logic, profiles, render smoke, stat-values ranking / loader / tables, cube tabs (logic, runner, mock, render), type-check + production build
```

## Accounts (optional)

Google sign-in + cloud-saved profiles (Firebase Auth + Firestore, straight from the browser; the API stays stateless and untouched).  Off unless `VITE_FIREBASE_*` are set at build time; setup: `deploy/README.md` ("Accounts setup"), behaviour and
tests: `web/README.md` ("Accounts"), design: `APP_ACCOUNTS_DESIGN.md`.  Rules + their emulator tests: `deploy/firebase/firestore.rules`, `deploy/firebase/rules-test/` (`npm run test:emulator`, needs Java).

## Import from your Excel workbook

Profiles tab > "Import from Excel (.xlsx)": the browser reads the values you typed into your own `<Class>-DPS-Calculator.xlsx` (Inputs, ArtifactsInput, CompanionsInput: including the star level and potential lines of every artifact and, from the Inputs sheet's Slot rows, the equipped artifacts of every content type; PotentialCubes: the cube gear of the 15 slots x 2 tracks; Equipment Compare and CubeData are not imported) and saves them as a new profile after a preview.
The file never leaves the browser (only the class schema is fetched).  Details: `web/README.md` ("Import from Excel"); the workbook layout map is generated by `python3 web/scripts/gen_xlsx_map.py`.

## Container (API only)

```bash
docker build -f api/Dockerfile -t msi-api .    # repository root as the build context
docker run --rm -p 8080:8080 -e MSI_CORS_ORIGINS=http://localhost:5173 msi-api
```

The front end is a static bundle (`web/dist` after `npm run build`; set `VITE_API_URL` at build time to the deployed API URL).

## Privacy policy
A short policy is part of the Help tab (`PRIVACY` in `web/src/content/help.tsx`, id `help-privacy`), linked from the footer and the sign-in dialog and reachable at `/#privacy`. Keep it in sync with what the app really stores (it says: no analytics/ads/tracking cookies; signed-out data stays in the browser; the stateless API keeps only a ~10 minute in-memory cache and standard host logs; with an account: Google id + e-mail, saved profiles, theme / last class in Firebase).
